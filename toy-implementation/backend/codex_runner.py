"""
Thin wrapper around the OpenAI Codex CLI (`codex exec`).

Codex is the agent that does the real work: it traverses the codebase, decides
which files matter, sends them to OpenAI, and writes the edits back to disk. We
just point it at a folder, hand it a prompt, and stream its progress.

We run it non-interactively:

    codex exec -C <dir> -s workspace-write --skip-git-repo-check --json \
               -o <last-message-file> "<prompt>"

  -s workspace-write   let it edit files inside the folder (nothing outside)
  --skip-git-repo-check the CoW clone is not a git repo, that's fine
  --json               emit one JSON event per line so we can show live status
  -o <file>            write the agent's final message (our summary) to a file
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

# Point Codex at a clean, project-local config dir instead of the user's global
# ~/.codex. That global dir may hold a stale `codex login` (ChatGPT) session whose
# expired token Codex prefers over OPENAI_API_KEY — causing "Failed to refresh
# token" errors. With an empty CODEX_HOME and no stored login, Codex falls back to
# OPENAI_API_KEY (from backend/.env) and talks to api.openai.com directly.
CODEX_HOME = Path(__file__).parent / ".codex_home"


def run_codex(workspace: Path, prompt: str, on_progress: Callable[[str], None]) -> dict:
    """
    Run Codex over `workspace` with `prompt`. Calls `on_progress(line)` with a
    short human-readable string as the agent works. Blocks until Codex exits, so
    call this from a background thread.

    Returns {"ok": bool, "summary": str, "exit_code": int}.
    """
    # A temp file to capture the agent's final message = our summary text.
    summary_file = Path(tempfile.mktemp(suffix="-codex-summary.txt"))

    cmd = [
        "codex", "exec",
        "-C", str(workspace),
        "-s", "workspace-write",
        "--skip-git-repo-check",
        "--json",
        "-o", str(summary_file),
    ]
    model = os.environ.get("CODEX_MODEL")
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)

    # Isolate Codex in a project-local CODEX_HOME and log in with our API key.
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "CODEX_HOME": str(CODEX_HOME)}
    _ensure_login(env)

    proc = subprocess.Popen(
        cmd,
        cwd=str(workspace),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
        env=env,
    )

    # Stream stdout line by line, turning each JSON event into a status blurb.
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        blurb = _summarize_event(line)
        if blurb:
            on_progress(blurb)

    proc.wait()

    summary = ""
    if summary_file.exists():
        summary = summary_file.read_text(encoding="utf-8").strip()
        summary_file.unlink(missing_ok=True)

    return {"ok": proc.returncode == 0, "summary": summary, "exit_code": proc.returncode}


def _ensure_login(env: dict) -> None:
    """
    Write our API key into CODEX_HOME/auth.json via `codex login --with-api-key`.

    This Codex version does not send OPENAI_API_KEY as a bearer on its own — the
    key must be stored by an explicit login. We do it before every run so the
    stored auth always matches the current key in backend/.env.
    """
    api_key = env.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — add it to backend/.env")
    subprocess.run(
        ["codex", "login", "--with-api-key"],
        input=api_key,
        text=True,
        env=env,
        capture_output=True,
        check=True,
    )


def _summarize_event(line: str) -> str:
    """
    Turn one `--json` event line into a short status string for the UI. The event
    schema can shift between Codex versions, so we stay defensive: pull the first
    useful text we find, otherwise fall back to the event type name.
    """
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return line[:120]  # not JSON? show the raw text, truncated

    # Events are typically {"type": "...", "msg"/"item": {...}}. Dig for text.
    kind = event.get("type") or event.get("msg", {}).get("type") or "working"
    payload = event.get("item") or event.get("msg") or event

    for key in ("text", "message", "command", "title", "reasoning"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, str) and value.strip():
            return f"{kind}: {value.strip()[:120]}"

    return str(kind)
