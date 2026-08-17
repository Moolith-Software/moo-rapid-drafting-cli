"""
Thin wrapper around the OpenAI Codex Python SDK (`openai-codex`).

Codex is the agent that does the real work: it traverses the codebase, decides
which files matter, sends them to OpenAI, and writes edits back to disk. The SDK
wraps the same Codex engine as the CLI, but gives us typed results, structured
output, and — crucially — thread management (fork / resume) for our feature tree.

One `run_turn` call = one turn (one input → the agent's full autonomous loop →
one result). We choose the thread up front:

  fresh feature   -> thread_start                (new session)
  child feature   -> thread_fork(parent_session) (branch; parent left untouched)
  refinement      -> thread_resume(own_session)  (linear continuation)

Auth: we log in with the API key into a project-local CODEX_HOME, so Codex never
falls back to a stale global `codex login` session.

Note: we use the blocking `thread.run()` for an authoritative TurnResult. The SDK
also offers `thread.turn().stream()` for live token-level notifications — a good
upgrade for finer progress once we can observe the event flow with a real key.
"""

import os
from pathlib import Path
from typing import Callable

from openai_codex import Codex, CodexConfig, Sandbox

# Project-local Codex home: isolates auth + persisted session ("rollout") files
# from the user's global ~/.codex. Session ids we store in the DB point in here,
# so this directory is durable state, not a throwaway.
CODEX_HOME = Path(__file__).parent / ".codex_home"


def run_turn(
    *,
    workspace: Path,
    prompt: str,
    output_schema: dict,
    on_progress: Callable[[str], None],
    session_id: str | None = None,
    fork_from: str | None = None,
) -> dict:
    """
    Run one Codex turn over `workspace`. Exactly one of the thread modes applies:
    fork_from (branch), session_id (resume), or neither (fresh start).

    Returns {ok, final_response, session_id, usage, error}. Blocks until the turn
    finishes, so call from a background thread.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — add it to backend/.env")

    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    config = CodexConfig(env={**os.environ, "CODEX_HOME": str(CODEX_HOME)})

    with Codex(config) as codex:
        codex.login_api_key(api_key)  # write API-key auth into our CODEX_HOME

        cwd = str(workspace)
        if fork_from:
            thread = codex.thread_fork(fork_from, cwd=cwd, sandbox=Sandbox.workspace_write)
        elif session_id:
            thread = codex.thread_resume(session_id, cwd=cwd, sandbox=Sandbox.workspace_write)
        else:
            thread = codex.thread_start(cwd=cwd, sandbox=Sandbox.workspace_write)

        on_progress("Codex is working…")
        result = thread.run(prompt, output_schema=output_schema)

        return {
            "ok": result.error is None,
            "final_response": result.final_response or "",
            "session_id": thread.id,
            "usage": _usage_dict(result.usage),
            "error": str(result.error) if result.error else None,
        }


def _usage_dict(usage) -> dict:
    """Best-effort dict of token usage (fields vary), for cache-hit logging."""
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        try:
            return usage.model_dump()
        except Exception:
            pass
    return {
        k: getattr(usage, k)
        for k in dir(usage)
        if not k.startswith("_") and isinstance(getattr(usage, k, None), (int, float))
    }
