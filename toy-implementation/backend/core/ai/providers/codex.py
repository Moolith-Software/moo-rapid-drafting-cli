"""
The OpenAI Codex provider.

Codex does the real work: it reads the codebase, decides which files matter, and
writes edits directly to disk. We hand it a workspace and a prompt, and get back
one turn's result.

A *turn* is one input and its complete result. Inside a single turn the agent may
make dozens of model and tool calls — reading files, editing, checking the build
— until it decides it is done.

A *thread* is a conversation that remembers previous turns. Which one we open
mirrors our feature tree:

    new feature   -> thread_start                 fresh session
    child feature -> thread_fork(parent_session)  branch; parent left untouched
    refinement    -> thread_resume(own_session)   linear continuation

Auth lives in a project-local CODEX_HOME so Codex never picks up a stale global
`codex login`. That folder also stores the session files our session ids point
at, which makes it durable state rather than a cache.
"""

import os
import threading
from pathlib import Path
from typing import Callable

from openai_codex import Codex, CodexConfig, Sandbox

from ...errors import TurnTimeout
from .types import DEFAULT_TIMEOUT_SECONDS, Provider, TurnOutcome

# Default location, at the backend root rather than beside this file — stored
# session ids point into it, so it must not move when this module does.
DEFAULT_HOME = Path(__file__).resolve().parents[3] / ".codex_home"


class CodexProvider(Provider):
    name = "codex"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        home: Path = DEFAULT_HOME,
    ):
        super().__init__(model=model, timeout=timeout)
        self.api_key = api_key  # Codex-specific
        self.home = home  # Codex-specific

    def run_turn(
        self,
        workspace: Path,
        prompt: str,
        output_schema: dict,
        on_progress: Callable[[str], None],
        session_id: str | None = None,
        fork_from: str | None = None,
    ) -> TurnOutcome:
        try:
            return self._attempt(
                workspace, prompt, output_schema, session_id, fork_from
            )
        except TurnTimeout:
            raise  # never retry a timeout — that would double the wait
        except Exception:
            if not (session_id or fork_from):
                raise
            # The stored session is gone — pruned, or CODEX_HOME was cleared. The
            # code on disk is still correct, so run it as a new session. We lose
            # the conversation history, not the work.
            on_progress("Previous Codex session unavailable — starting a fresh one.")
            return self._attempt(workspace, prompt, output_schema, None, None)

    def _attempt(
        self,
        workspace: Path,
        prompt: str,
        output_schema: dict,
        session_id: str | None,
        fork_from: str | None,
    ) -> TurnOutcome:
        """One connection, one thread, one turn."""
        with self._connect() as codex:
            thread = self._open_thread(codex, workspace, session_id, fork_from)
            handle = thread.turn(prompt, output_schema=output_schema, model=self.model)
            result = self._wait_for_result(handle)

        usage = result.usage.model_dump() if result.usage else {}
        print(f"[codex] {thread.id} usage: {usage}", flush=True)

        return TurnOutcome(
            ok=result.error is None,
            text=result.final_response or "",
            session_id=thread.id,
            usage=usage,
            error=str(result.error) if result.error else None,
        )

    def _wait_for_result(self, handle):
        """
        Wait for the turn, interrupting it if it outruns `self.timeout`.

        The SDK has no timeout option, and signals are unavailable because turns
        run on a background thread (`signal.signal` only works on the main one).
        So a watchdog timer calls the SDK's own `interrupt()`, which is the
        supported way to stop an active turn.
        """
        expired = threading.Event()

        def stop() -> None:
            expired.set()
            handle.interrupt()

        watchdog = threading.Timer(self.timeout, stop)
        watchdog.start()
        try:
            result = handle.run()
        except Exception:
            if expired.is_set():
                raise TurnTimeout(f"no result after {self.timeout:.0f}s") from None
            raise
        finally:
            watchdog.cancel()

        if expired.is_set():  # interrupted cleanly rather than by raising
            raise TurnTimeout(f"no result after {self.timeout:.0f}s")
        return result

    def _connect(self) -> Codex:
        """
        Open a Codex client with our credentials.

        Built per turn rather than held on the instance: the SDK client owns a
        child process, and keeping one alive between turns would leak it.
        """
        self.home.mkdir(parents=True, exist_ok=True)
        codex = Codex(CodexConfig(env={**os.environ, "CODEX_HOME": str(self.home)}))
        codex.login_api_key(self.api_key)
        return codex

    def _open_thread(self, codex: Codex, workspace: Path, session_id, fork_from):
        """Branch, continue, or start a conversation — see the module docstring."""
        options = dict(cwd=str(workspace), sandbox=Sandbox.workspace_write)
        if fork_from:
            return codex.thread_fork(fork_from, **options)
        if session_id:
            return codex.thread_resume(session_id, **options)
        return codex.thread_start(**options)
