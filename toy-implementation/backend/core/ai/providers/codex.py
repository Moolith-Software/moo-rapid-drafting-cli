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

from openai_codex import Codex, CodexConfig, InvalidRequestError, Sandbox
from openai_codex.types import TurnStatus

from ...errors import TurnTimeout
from .types import MAX_TURN_TIMEOUT, Provider, TurnOutcome

# Default location, at the backend root rather than beside this file — stored
# session ids point into it, so it must not move when this module does.
CODEX_HOME = Path(__file__).resolve().parents[3] / ".codex_home"

# How hard the model should think. Every provider names these differently,
# > gpt-5.6 rejects the SDK's "minimal" and accepts a "max" the SDK's enum does not list
REASONING_EFFORT = "medium"  # none | low | medium | high | xhigh


def _readable(seconds: float) -> str:
    """Time limits are set in seconds; say them the way a person reads them."""
    return f"{seconds / 60:.0f} minutes" if seconds >= 60 else f"{seconds:.0f}s"


class CodexProvider(Provider):
    name = "codex"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        timeout: float = MAX_TURN_TIMEOUT,
    ):
        super().__init__(model=model, timeout=timeout)
        self.api_key = api_key

    def run_turn(
        self,
        workspace: Path,
        prompt: str,
        output_schema: dict,
        on_progress: Callable[[str], None],
        session_id: str | None = None,
        fork_from: str | None = None,
    ) -> TurnOutcome:
        with self._connect() as codex:
            thread = self._open_thread(codex, workspace, session_id, fork_from)
            handle = thread.turn(
                prompt,
                output_schema=output_schema,
                model=self.model,
                effort=REASONING_EFFORT,
            )
            result = self._wait_for_result(handle)

        if result.usage:  # logged for cost/cache visibility; nothing stores it
            print(f"[codex] {thread.id} usage: {result.usage.model_dump()}", flush=True)

        # A turn can end without an error and still not be finished: `interrupted`
        # is what our own watchdog produces, and what a half-answered turn looks
        # like. Only `completed` counts as success.
        finished = result.status == TurnStatus.completed
        return TurnOutcome(
            ok=finished and result.error is None,
            text=result.final_response or "",
            session_id=thread.id,
            error=(
                str(result.error)
                if result.error
                else None
                if finished
                else f"turn ended as {result.status.value}"
            ),
        )

    def _wait_for_result(self, handle):
        """
        Wait for the turn, interrupting it if it outruns `self.timeout`.

        The SDK has no timeout option, and signals are unavailable because turns
        run on a background thread (`signal.signal` only works on the main one).
        So a watchdog timer calls the SDK's own `interrupt()`, which is the
        supported way to stop an active turn.
        """
        limit = _readable(self.timeout)
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
                raise TurnTimeout(f"no result after {limit}") from None
            raise
        finally:
            watchdog.cancel()

        if expired.is_set():  # interrupted cleanly rather than by raising
            raise TurnTimeout(f"no result after {limit}")
        return result

    def _connect(self) -> Codex:
        """
        Open a Codex client with our credentials.

        Built per turn rather than held on the instance: the SDK client owns a
        child process, and keeping one alive between turns would leak it.
        """
        CODEX_HOME.mkdir(parents=True, exist_ok=True)
        codex = Codex(CodexConfig(env={**os.environ, "CODEX_HOME": str(CODEX_HOME)}))
        codex.login_api_key(self.api_key)
        return codex

    def _open_thread(
        self,
        codex: Codex,
        workspace: Path,
        session_id: str | None,
        fork_from: str | None,
    ):
        """
        Branch, continue, or start a conversation — see the module docstring.

        A stored session may be gone: pruned, or CODEX_HOME cleared. Codex says
        so here, before any turn runs, so we fall back to a fresh session and
        lose the conversation history — never the work, which is on disk.
        """
        options = dict(cwd=str(workspace), sandbox=Sandbox.workspace_write)
        try:
            if fork_from:
                return codex.thread_fork(fork_from, **options)
            if session_id:
                return codex.thread_resume(session_id, **options)
        except InvalidRequestError:
            print(
                f"[codex] session {session_id or fork_from} not found — starting fresh",
                flush=True,
            )
        return codex.thread_start(**options)
