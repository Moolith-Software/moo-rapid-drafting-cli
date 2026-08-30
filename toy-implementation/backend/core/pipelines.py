"""
The two feature pipelines: adding a feature, and refining one.

This module is only the *order* of the steps. Each step lives elsewhere:

    core.instances        get a runnable instance ready (its own copy of the code)
    core.ai.operations.features     ask the AI to build or refine it
    core.changes          work out what actually changed on disk
    db                    record status and results

Both pipelines run on a background thread, so the HTTP request returns straight
away and the frontend polls for status.

A feature is modelled two ways at once, and they stay in step:

    code    a child clones its parent's workspace
    session a child forks its parent's session; a refinement resumes its own
"""

import db

from . import changes, errors, instances, statuses
from . import workspace_manager as workspaces
from .ai.operations import features as feature_ai


def run_add(feature_id: int) -> None:
    """Prepare an instance, have the AI add the feature, record the result."""
    try:
        feature = db.get_feature(feature_id)
        if not feature:  # feature_id should always be valid
            print(
                f"[pipeline] feature {feature_id} not found — "
                "cannot write status or message to the db",
                flush=True,
            )
            return
        db.set_status(feature_id, statuses.PREPARING, "Preparing a workspace…")
        parent = db.get_feature(feature["parent_id"]) if feature["parent_id"] else None
        instance = instances.prepare(feature_id, parent)
        workspace = instance.workspace
        db.update_feature(feature_id, code_folder_name=instance.folder)

        db.set_status(feature_id, statuses.RUNNING, "Implementing the feature…")
        before = changes.snapshot(workspace)
        result = feature_ai.add_feature(
            workspace,
            feature["feature"],
            session_id=instance.session_id,
            fork_from=instance.fork_from,
        )
        after = changes.snapshot(workspace)
        file_changes = changes.diff_snapshots(before, after)

        # Deterministically check if any file actually changed, which is always expected
        if not file_changes:
            raise errors.NoChanges(
                "the AI reported success for adding the feature  but no files changed"
            )

        db.update_feature(
            feature_id,
            file_changes=file_changes,
            summary=result.summary,
            codex_session_id=result.session_id,
            is_dirty=True,
            status=statuses.COMPLETED,
            progress="Done.",
        )

    except Exception as exc:
        try:
            edited = bool(changes.diff_snapshots(before, changes.snapshot(workspace)))
        except Exception:
            edited = False
        db.update_feature(
            feature_id,
            is_dirty=edited,
            status=statuses.FAILED,
            progress=errors.wrap(exc).status_line(),
        )


def run_refine(feature_id: int, user_request: str) -> None:
    """
    Apply a follow-up request to a feature that already ran.

    Resumes the feature's own session, so the AI continues from its real history
    rather than being re-briefed, and edits the same workspace in place.
    """
    try:
        feature = db.get_feature(feature_id)
        if not feature:
            # Nothing to report against: a status write targets this row, so with
            # no row there is nowhere to record the failure. Log and stop.
            print(
                f"[pipeline] feature {feature_id} not found — "
                "cannot write status or message to the db",
                flush=True,
            )
            return
        db.set_status(feature_id, statuses.RUNNING, "Refining the feature…")
        workspace = workspaces.path_for(feature["code_folder_name"])
        recap = _recap(feature)

        before = changes.snapshot(workspace)
        result = feature_ai.refine_feature(
            workspace,
            recap,
            user_request,
            session_id=feature["codex_session_id"],
        )
        after = changes.snapshot(workspace)
        file_changes = changes.diff_snapshots(before, after)

        if not file_changes:
            raise errors.NoChanges(
                "the refinement reported success but no files changed"
            )

        db.update_feature(
            feature_id,
            refinements=_append_refinement(feature, user_request, file_changes, result),
            codex_session_id=result.session_id,
            is_dirty=True,
            status=statuses.COMPLETED,
            progress="Done.",
        )

    except Exception as exc:
        try:  # unbound if it failed before there was a workspace to snapshot
            edited = bool(changes.diff_snapshots(before, changes.snapshot(workspace)))
        except Exception:
            edited = False
        db.update_feature(
            feature_id,
            is_dirty=edited,
            status=statuses.FAILED,
            progress=errors.wrap(exc).status_line(),
        )


# --- recording -------------------------------------------------------------


def _recap(feature: dict) -> str:
    """
    What the feature does so far — the first turn, then each refinement in order.
    Only place we have this is history is here, otherwise model wouldn't see these changes.
    """
    story = [feature["summary"].get("summary") or feature["feature"]]
    for refinement in feature["refinements"]:
        summary = refinement.get("summary")
        if isinstance(summary, dict) and summary.get("summary"):
            story.append(summary["summary"])
    return " ".join(story)


def _append_refinement(
    feature: dict, user_request: str, file_changes: list, result
) -> list:
    """Add this refinement to the feature's history."""
    refinements = feature["refinements"]
    return refinements + [
        {
            "refinement_id": len(refinements) + 1,
            "user_request": user_request,
            "file_changes": file_changes,
            "summary": result.summary,
        }
    ]
