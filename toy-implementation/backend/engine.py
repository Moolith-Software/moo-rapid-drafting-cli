from pathlib import Path

import db
import schemas
import codex_runner
from changes import diff_snapshots, snapshot
from workspace_manager import (
    WorkspaceCopyError,
    clone_base,
    clone_from,
    new_folder_name,
    path_for,
)

# The structured response contract we ask Codex to fill (human-readable only).
OUTPUT_SCHEMA = schemas.FeatureSummary.model_json_schema()


# --- Status Emit -----------------------------------------------------------


def emit(
    feature_id: int, status: str | None = None, progress: str | None = None
) -> None:
    """Write the current status/progress to the DB so the /status endpoint sees it."""
    fields = {}
    if status is not None:
        fields["status"] = status
    if progress is not None:
        fields["progress"] = progress
    if fields:
        db.update_feature(feature_id, **fields)


# --- Pre-cache / Warm (placeholder) ----------------------------------------


def warm(workspace: Path) -> None:
    """
    Placeholder for the 'warm the LLM on this codebase' box.

    OpenAI applies prompt caching automatically on repeated prefixes, and Codex
    reads files via tool calls rather than a static prompt prefix, so there is no
    single codebase blob to pre-warm here. Kept to stay faithful to the diagram.
    """
    return None


# --- Setup preview / build tools (placeholder) -----------------------------


def setup_preview(workspace: Path) -> None:
    """
    Placeholder for the 'setup preview / build tools' box. Real previewing is
    handled on demand by preview.py (each workspace is a runnable CoW clone).
    """
    return None


# --- Execute AI + full pipelines -------------------------------------------


def run_add(feature_id: int) -> None:
    """
    Full 'features/add' pipeline for a new feature. Run on a background thread.
    A child (parent_id set) CoW-clones the parent's workspace AND forks the
    parent's Codex session; a top-level feature clones base/ and starts fresh.
    """
    feature = db.get_feature(feature_id)
    try:
        emit(
            feature_id,
            status="copying",
            progress="Cloning the codebase (copy-on-write)…",
        )
        # Assign the workspace name now, with a per-clone UUID so the target is
        # always fresh — the copy never has to overwrite/delete anything. Record
        # the pointer on the row before cloning.
        folder = new_folder_name(feature_id)
        db.update_feature(feature_id, code_folder_name=folder)

        fork_from = None
        if feature["parent_id"]:
            parent = db.get_feature(feature["parent_id"])
            workspace = clone_from(parent["code_folder_name"], folder)
            fork_from = parent.get("codex_session_id")  # branch the session too
        else:
            workspace = clone_base(folder)

        emit(feature_id, status="warming", progress="Preparing the model…")
        warm(workspace)
        setup_preview(workspace)

        emit(
            feature_id, status="running", progress="Codex is implementing the feature…"
        )
        before = snapshot(workspace)
        result = _execute(
            feature_id, workspace, _add_prompt(feature["feature"]), fork_from=fork_from
        )
        after = snapshot(workspace)

        _finish(feature_id, result, file_changes=diff_snapshots(before, after))
    except WorkspaceCopyError as exc:  # clone step failed — report it distinctly
        detail = f": {exc.message}" if exc.message else ""
        emit(feature_id, status="failed", progress=f"[{exc.code}] {exc.title}{detail}")
    except Exception as exc:  # any other failure (Codex, DB, snapshot, …)
        emit(feature_id, status="failed", progress=f"Error: {exc}")


def run_refine(feature_id: int, user_request: str) -> None:
    """
    Full 'features/refine' pipeline. Resumes the feature's OWN Codex session so
    the refinement builds on the prior turn's real history, then appends a
    refinement object (with an AI-written summary) to the feature.
    """
    feature = db.get_feature(feature_id)
    workspace = path_for(feature["code_folder_name"])
    try:
        emit(feature_id, status="running", progress="Codex is refining the feature…")
        before = snapshot(workspace)
        result = _execute(
            feature_id,
            workspace,
            _refine_prompt(feature, user_request),
            session_id=feature.get("codex_session_id"),
        )
        after = snapshot(workspace)
        changes = diff_snapshots(before, after)

        refinements = feature["refinements"]
        refinements.append(
            {
                "refinement_id": len(refinements) + 1,
                "user_request": user_request,
                "file_changes": changes,
                "summary": _parse_summary(result["final_response"]),
            }
        )
        _log_usage(feature_id, result["usage"])
        db.update_feature(
            feature_id, refinements=refinements, codex_session_id=result["session_id"]
        )
        emit(
            feature_id,
            status="completed" if result["ok"] else "failed",
            progress="Done." if result["ok"] else f"Codex error: {result['error']}",
        )
    except Exception as exc:
        emit(feature_id, status="failed", progress=f"Error: {exc}")


def _execute(feature_id, workspace, prompt, session_id=None, fork_from=None) -> dict:
    """
    Run one Codex turn, with a fallback: if resuming/forking a prior session
    fails (it was GC'd or .codex_home was cleared), retry as a fresh session on
    the current code snapshot — correct, minus history/cache for that turn.
    """

    def prog(line: str) -> None:
        emit(feature_id, progress=line)

    try:
        return codex_runner.run_turn(
            workspace=workspace,
            prompt=prompt,
            output_schema=OUTPUT_SCHEMA,
            on_progress=prog,
            session_id=session_id,
            fork_from=fork_from,
        )
    except Exception:
        if session_id or fork_from:  # we had a prior session to lose — recover fresh
            prog(
                "Prior Codex session unavailable — starting fresh from the code snapshot…"
            )
            return codex_runner.run_turn(
                workspace=workspace,
                prompt=prompt,
                output_schema=OUTPUT_SCHEMA,
                on_progress=prog,
            )
        raise


def _finish(feature_id: int, result: dict, file_changes: list) -> None:
    """Store the deterministic diff + structured summary + session id, set status."""
    _log_usage(feature_id, result["usage"])
    db.update_feature(
        feature_id,
        file_changes=file_changes,
        summary=_parse_summary(result["final_response"]),
        codex_session_id=result["session_id"],
    )
    emit(
        feature_id,
        status="completed" if result["ok"] else "failed",
        progress="Done." if result["ok"] else f"Codex error: {result['error']}",
    )


def _parse_summary(final_response: str) -> dict:
    """Validate Codex's reply against FeatureSummary; fall back to raw text."""
    try:
        return schemas.FeatureSummary.model_validate_json(final_response).model_dump()
    except Exception:
        return schemas.FeatureSummary(
            feature_title="",
            summary=final_response.strip() or "(no summary returned)",
            highlights=[],
        ).model_dump()


def _log_usage(feature_id: int, usage: dict) -> None:
    """Print token usage so we can watch cached-vs-fresh across fork/resume."""
    if usage:
        print(f"[feature {feature_id}] token usage: {usage}", flush=True)


def _add_prompt(feature: str) -> str:
    return (
        "You are editing an existing Vue 3 + TypeScript + Vite app.\n"
        "Apply all changes by editing files directly on disk. Match the existing "
        "code style and keep the app building.\n"
        "Do NOT include file contents, code, or a list of changed files in your "
        "response — changed files are detected automatically from the filesystem. "
        "Your response is only the human-readable summary.\n\n"
        f"Feature request:\n{feature}"
    )


def _refine_prompt(feature: dict, user_request: str) -> str:
    # Resuming a session already carries the real history; we include a compact
    # recap so the fresh-session fallback still has context.
    recap = feature["summary"].get("summary") or feature["feature"]
    return (
        "You are refining a feature in this Vue 3 + TypeScript app, continuing "
        "your earlier work.\n"
        f"What the feature does so far: {recap}\n\n"
        "Apply the refinement by editing files directly on disk, keeping the "
        "existing style and keeping the app building.\n"
        "Do NOT include file contents or a change list in your response — changes "
        "are detected from the filesystem. Your response is only the "
        "human-readable summary.\n\n"
        f"Refinement request:\n{user_request}"
    )
