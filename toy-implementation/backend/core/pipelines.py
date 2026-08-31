"""
The two feature pipelines: adding a feature, and refining one.

This module is only the *order* of the steps. Each step lives elsewhere:

    core.environments     get a runnable environment ready (its own copy of the code)
    core.ai.operations.features     ask the AI to build or refine it
    core.changes          work out what actually changed on disk
    db                    record status and results

Both pipelines run on a background thread, so the HTTP request returns straight
away and the frontend polls for status.

A feature is modelled two ways at once, and they stay in step:

    code    a child clones its parent's workspace
    session a child forks its parent's session; a refinement resumes its own
"""

import time

import db
import preview

from . import changes, environments, errors, statuses
from . import workspace_manager as workspaces
from .ai.operations import features as feature_ai


def preload_environment(parent_id: int | None = None, feature: str = "") -> dict | None:
    """
    Build an environment before anyone asks for one.

    The frontend calls this on hover, so the slow parts — cloning, connecting,
    warming the prompt cache, starting the preview — are already done by the
    time a request is typed.
    """
    started = time.monotonic()
    try:
        feature_id = db.create_feature(feature=feature, parent_id=parent_id)
    except Exception as exc:
        # Without a row there is nowhere to record this, so the log is all there
        # is. `wrap` is what writes it.
        errors.wrap(exc)
        return None

    try:
        parent = db.get_feature(parent_id) if parent_id else None
        env = environments.prepare_workspace(feature_id, parent)
        db.update_feature(feature_id, code_folder_name=env.folder)

        # Read-only, so it cannot edit anything and leave the environment dirty, caching only
        result = feature_ai.prewarm_ai_session(env.workspace)
        preview.start_preview(f"feature-{feature_id}", env.workspace)

        db.update_feature(
            feature_id,
            codex_session_id=result.session_id,
            status=statuses.READY,
            progress="Ready.",
        )
        print(
            f"[pipeline] preload_environment {feature_id} ready in "
            f"{time.monotonic() - started:.2f}s",
            flush=True,
        )
    except Exception as exc:
        db.update_feature(
            feature_id,
            is_dirty=False,  # read-only priming cannot have edited anything
            status=statuses.FAILED,
            progress=errors.wrap(exc).status_line(),
        )
    return db.get_feature(feature_id)


def run_add(user_request: str, parent_id: int | None = None) -> None:
    """
    Have the AI build a feature, then record the result.
    """
    feature = db.claim_ready(user_request)
    if feature is None:  # nobody hovered, so build one now — created already claimed
        feature = preload_environment(parent_id, feature=user_request)
        # Either no row exists to run against, or the build failed and already wrote
        # why on the row. Returning leaves that reason in place
        if feature is None or feature["status"] != statuses.READY:
            return

    feature_id = feature["id"]
    try:
        workspace = workspaces.path_for(feature["code_folder_name"])

        db.set_status(feature_id, statuses.RUNNING, "Implementing the feature…")
        before = changes.snapshot(workspace)
        result = feature_ai.add_feature(
            workspace,
            user_request,
            session_id=feature["codex_session_id"],
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
        if feature["status"] != statuses.COMPLETED:
            raise errors.InvalidFeature(
                f"cannot refine this feature row: status is {feature['status']!r}, "
                f"expected {statuses.COMPLETED!r}"
            )
        workspace = workspaces.path_for(feature["code_folder_name"])
        recap = _recap(feature)

        db.set_status(feature_id, statuses.REFINING, "Refining the feature…")
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
                "the refinement AI reported success but no files changed"
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
        db.update_feature(
            feature_id,
            is_dirty=True,  # assumed to be dirty since it uses the same workspace as run_add
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
