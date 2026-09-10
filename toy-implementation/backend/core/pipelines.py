"""
The two feature pipelines: adding a feature, and refining one.

This module is only the *order* of the steps. Each step lives elsewhere:

    core.environments     get a runnable environment ready (its own copy of the code)
    core.ai.operations.features     ask the AI to build or refine it
    core.changes          work out what actually changed on disk
    db                    record status and results

Which row to work on is settled in main.py, in the request thread: it claims a
warm environment or creates an empty row, and passes the id here. So every
function below starts from a row that already exists.

Both pipelines run on a background thread, so the HTTP request returns straight
away and the frontend polls for status.

Lineage is a code relationship, not a conversational one:

    code    a child clones its parent's workspace, so it starts from that code
    session a child opens a fresh session; only a refinement resumes its own
"""

import time

import db
import preview

from . import changes, environments, errors, statuses
from . import workspace_manager as workspaces
from .ai.operations import features as feature_ai


def preload_environment(parent_id: int | None = None) -> None:
    """
    Build an environment before anyone asks for one.

    The frontend calls this on hover, so the slow parts — cloning, connecting,
    warming the prompt cache, starting the preview — are already done by the
    time a request is typed.
    """
    try:
        feature_id = db.create_feature(parent_id=parent_id)
    except Exception as exc:
        # Nobody is waiting on this one, so there is no row and no caller to
        # tell. The log is the only record. `wrap` is what writes it.
        errors.wrap(exc)
        return
    build_environment(feature_id)


def build_environment(feature_id: int) -> dict | None:
    """
    Give an existing row a workspace and a warm AI session.

    A row nobody has claimed joins the warm pool, so it ends `ready`.
    Otherwise, it is already claimed so will skip in the next step from `initializing` to `building`

    Returns the finished row, or None when the build failed
    """
    started = time.monotonic()
    row = db.get_feature(feature_id)
    try:
        db.set_status(feature_id, statuses.INITIALIZING, "Preparing the environment…")

        parent = db.get_feature(row["parent_id"]) if row["parent_id"] else None
        env = environments.prepare_workspace(feature_id, parent)
        db.update_feature(
            feature_id,
            code_folder_name=env.folder,
            cloned_from_version=parent["workspace_version"] if parent else None,
        )

        # Read-only, so it cannot edit anything and leave the environment dirty, caching only
        result = feature_ai.prewarm_ai_session(env.workspace)
        preview.start_preview(f"feature-{feature_id}", env.workspace)

        db.update_feature(feature_id, codex_session_id=result.session_id)
        if not row["feature"]:  # no request attached, so it joins the warm pool
            db.update_feature(feature_id, status=statuses.READY, progress="Ready.")

        print(
            f"[pipeline] environment {feature_id} ready in "
            f"{time.monotonic() - started:.2f}s",
            flush=True,
        )
    except Exception as exc:
        db.update_feature(
            feature_id,
            status=statuses.FAILED,
            progress=errors.wrap(exc).status_line(),
        )
        return None
    return db.get_feature(feature_id)


def run_add(feature_id: int) -> None:
    """
    Have the AI build a feature, then record the result.

    The row arrives already taken: either a warm environment that was waiting,
    or an empty row that still needs one built.
    """
    row = db.get_feature(feature_id)
    if not row[
        "code_folder_name"
    ]:  # arrived without a 'ready' environment, so build one now
        row = build_environment(feature_id)
        if row is None:  # the build failed and already wrote why on the row
            return

    try:
        workspace = workspaces.path_for(row["code_folder_name"])

        db.bump_workspace_version(feature_id)
        db.set_status(feature_id, statuses.BUILDING, "Implementing the feature…")
        before = changes.snapshot(workspace)
        result = feature_ai.add_feature(
            workspace,
            row["feature"],
            session_id=row["codex_session_id"],
        )
        after = changes.snapshot(workspace)
        file_changes = changes.diff_snapshots(before, after)

        # Deterministically check if any file actually changed, which is always expected
        if not file_changes:
            raise errors.NoChanges(
                "the AI reported success for adding the feature, but no files changed"
            )

        db.update_feature(
            feature_id,
            file_changes=file_changes,
            summary=result.summary,
            codex_session_id=result.session_id,
            status=statuses.COMPLETED,
            progress="Done.",
        )

    except Exception as exc:
        db.update_feature(
            feature_id,
            status=statuses.FAILED,
            progress=errors.wrap(exc).status_line(),
        )


def run_refine(feature_id: int, user_request: str) -> None:
    """
    Apply a follow-up request to a feature that already ran.

    Resumes the feature's own session, so the AI continues from its real history
    rather than being re-briefed, and edits the same workspace in place.

    main.py reserved the row before submitting this, so it is known refinable
    and no second refinement can be running against the same workspace.
    """
    row = db.get_feature(feature_id)
    try:
        workspace = workspaces.path_for(row["code_folder_name"])
        recap = _recap(row)

        db.bump_workspace_version(feature_id)
        db.set_status(feature_id, statuses.REFINING, "Refining the feature…")
        before = changes.snapshot(workspace)
        result = feature_ai.refine_feature(
            workspace,
            recap,
            user_request,
            session_id=row["codex_session_id"],
        )
        after = changes.snapshot(workspace)
        file_changes = changes.diff_snapshots(before, after)

        if not file_changes:
            raise errors.NoChanges(
                "the refinement AI reported success but no files changed"
            )

        db.update_feature(
            feature_id,
            refinements=_append_refinement(row, user_request, file_changes, result),
            codex_session_id=result.session_id,
            status=statuses.COMPLETED,
            progress="Done.",
        )

    except Exception as exc:
        db.update_feature(
            feature_id,
            status=statuses.FAILED,
            progress=errors.wrap(exc).status_line(),
        )


# --- recording -------------------------------------------------------------


def _recap(row: dict) -> str:
    """
    What the feature does so far — the first turn, then each refinement in order.
    Only place we have this is history is here, otherwise model wouldn't see these changes.
    """
    story = [row["summary"].get("summary") or row["feature"]]
    for refinement in row["refinements"]:
        summary = refinement.get("summary")
        if isinstance(summary, dict) and summary.get("summary"):
            story.append(summary["summary"])
    return " ".join(story)


def _append_refinement(
    row: dict, user_request: str, file_changes: list, result
) -> list:
    """Add this refinement to the feature's history."""
    refinements = row["refinements"]
    return refinements + [
        {
            "refinement_id": len(refinements) + 1,
            "user_request": user_request,
            "file_changes": file_changes,
            "summary": result.summary,
        }
    ]
