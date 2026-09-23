"""
The OpenAI Codex harness.

Codex does the real work: it reads the codebase, decides which files matter, and
writes edits directly to disk. We hand it a workspace and a prompt, and get back
one turn's result.

A *turn* is one input and its complete result. Inside a single turn the agent may
make dozens of model and tool calls - reading files, editing, checking the build
- until it decides it is done.

A *thread* is a conversation that remembers previous turns. Which one we open:

    no session yet    -> thread_start                fresh session
    a stored session  -> thread_resume(session_id)   linear continuation

A child feature gets its parent's code, not its conversation: its warm-up
turn starts a fresh thread like any other environment.

Auth lives in a project-local CODEX_HOME so Codex never picks up a stale global
`codex login`. That folder also stores the session files our session ids point
at, which makes it durable state rather than a cache.
"""

import os
import threading
from pathlib import Path

from openai_codex import (
    Codex,
    CodexConfig,
    InvalidRequestError,
    Sandbox,
    ServerBusyError,
    Thread,
    TransportClosedError,
    TurnHandle,
    TurnResult,
)
from openai_codex.types import TurnStatus
from pydantic import ValidationError

from constants.paths import BACKEND_DIR
from core.errors import (
    AppError,
    AuthRejectedError,
    ConfigError,
    QuotaExceededError,
    TurnFailedError,
    TurnTimeoutError,
    UnknownAIError,
)
from core.utils import mentions, readable_duration

from .types import MAX_TURN_TIMEOUT, Harness, HarnessName, TurnOutcome

# Default location, at the backend root rather than beside this file - stored
# session ids point into it, so it must not move when this module does.
CODEX_HOME = BACKEND_DIR / ".codex_home"

# How hard the model should think. Every harness names these differently,
# > gpt-5.6 rejects the SDK's "minimal" and accepts a "max" the SDK's enum does not list
REASONING_EFFORT = "medium"  # none | low | medium | high | xhigh


def _classify(exc: Exception) -> AppError:
    """
    Work out which failure a failed turn was, from its message since RuntimeError
    is all that it throws, ordered by precedence.
    """
    message = str(exc)

    if mentions(message, "invalid_json_schema", "codex_output_schema"):
        return ConfigError(f"codex rejected our output schema: {message}")

    if mentions(message, "invalid_api_key", "unauthorized"):
        return AuthRejectedError(message)

    if mentions(message, "usage limit", "quota", "rate limit"):
        return QuotaExceededError(message)

    # unclassified turn failure
    return TurnFailedError(message)


def _translate(exc: Exception) -> AppError:
    """
    Turn anything the SDK throws into one of our codes, ordered by precedence.

    A turn can die for perfectly ordinary reasons - the server was
    busy, the subprocess went away - and that is still considered a failed run

    The last case is deliberately open: anything unrecognised, a bug of our own
    included, is named here rather than left to escape as an unexpected error.
    """
    if isinstance(exc, RuntimeError):  # run time errors matched against keywords
        return _classify(exc)

    if isinstance(exc, (ServerBusyError, TransportClosedError)):
        return TurnFailedError(f"{type(exc).__name__}: {exc}")

    if isinstance(exc, ValidationError):
        return UnknownAIError(f"unexpected response shape: {exc}")

    return UnknownAIError(f"{type(exc).__name__}: {exc}")


class CodexHarness(Harness):
    name = HarnessName.CODEX_SDK

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
        session_id: str | None = None,
        read_only: bool = False,
    ) -> TurnOutcome:
        try:
            with self._connect() as codex:
                thread = self._open_thread(codex, workspace, session_id, read_only)
                handle = thread.turn(
                    prompt,
                    output_schema=output_schema,
                    model=self.model,
                    effort=REASONING_EFFORT,
                )
                result = self._wait_for_result(handle)
        except AppError as exc:
            self.tag(exc)
            raise
        except Exception as exc:
            raise self.tag(_translate(exc)) from exc

        if result.usage:  # logged for cost/cache visibility; nothing stores it
            print(
                f"{self.tags} {thread.id} usage: {result.usage.model_dump()}",
                flush=True,
            )

        # edge case in case result was interrupted, don't want a false positive success
        if result.status != TurnStatus.completed:
            raise self.tag(
                TurnFailedError(f"turn ended as {result.status.value} (external)")
            )

        return TurnOutcome(
            text=result.final_response or "", session_id=thread.id, harness=self.name
        )

    def _wait_for_result(self, handle: TurnHandle) -> TurnResult:
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
                raise TurnTimeoutError(
                    f"no result after {readable_duration(self.timeout)} (watchdog)"
                ) from None
            raise
        finally:
            watchdog.cancel()

        if expired.is_set():  # interrupted cleanly rather than by raising
            raise TurnTimeoutError(
                f"no result after {readable_duration(self.timeout)} (watchdog)"
            )
        return result

    def _connect(self) -> Codex:
        """
        Open a Codex client with our credentials.

        Built per turn rather than held on the instance: the SDK client owns a
        child process, and keeping one alive between turns would leak it.
        """
        CODEX_HOME.mkdir(parents=True, exist_ok=True)
        try:
            codex = Codex(
                CodexConfig(env={**os.environ, "CODEX_HOME": str(CODEX_HOME)})
            )
        except (FileNotFoundError, PermissionError) as exc:
            raise ConfigError(f"codex runtime unavailable: {exc}") from exc
        except OSError as exc:  # anything else that stopped the subprocess starting
            raise ConfigError(f"could not start codex: {exc}") from exc
        except Exception as exc:
            raise ConfigError(
                f"codex runtime handshake failed: {type(exc).__name__}: {exc}"
            ) from exc

        try:
            codex.login_api_key(self.api_key)
        except Exception as exc:
            codex.close()
            raise ConfigError(
                f"codex login failed: {type(exc).__name__}: {exc}"
            ) from exc
        except BaseException:
            codex.close()
            raise
        return codex

    def _open_thread(
        self,
        codex: Codex,
        workspace: Path,
        session_id: str | None,
        read_only: bool = False,
    ) -> Thread:
        """
        Continue or start a conversation - see the module docstring.

        A stored session may be gone: pruned, or CODEX_HOME cleared. Codex says
        so here, before any turn runs, so we fall back to a fresh session and
        lose the conversation history - never the work, which is on disk.
        """
        sandbox = Sandbox.read_only if read_only else Sandbox.workspace_write
        options = {"cwd": str(workspace), "sandbox": sandbox}
        if session_id:
            try:
                return codex.thread_resume(session_id, **options)
            except InvalidRequestError:
                print(
                    f"{self.tags} session {session_id} not found - starting fresh",
                    flush=True,
                )
        return codex.thread_start(**options)
