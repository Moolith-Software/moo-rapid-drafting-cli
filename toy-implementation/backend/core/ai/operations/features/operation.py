"""
Have an AI build or refine a feature by editing a workspace.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.ai import harnesses
from core.errors import AppError

from . import prompts, schemas


@dataclass
class FeatureResult:
    """Shape of result after implementing code changes from AI model"""

    summary: dict
    session_id: str
    harness: harnesses.HarnessName  # the harness that owns session_id


def add_feature(
    workspace: Path,
    user_request: str,
    session_id: str | None = None,
    session_harness: harnesses.HarnessName | None = None,
) -> FeatureResult:
    """Build a feature that has not been started yet."""
    return _run(
        workspace,
        prompts.add(user_request),
        schemas.FEATURE_SCHEMA,
        schemas.parse_feature_summary,
        session_id,
        session_harness,
    )


def prewarm_ai_session(workspace: Path) -> FeatureResult:
    """
    Run a throwaway turn so the prompt cache is warm and the thread has a
    rollout to resume. Read-only, so it cannot leave the workspace dirty.
    """
    return _run(
        workspace,
        prompts.prime(),
        schemas.PRIMING_SCHEMA,
        schemas.parse_priming_ack,
        None,
        None,
        read_only=True,
    )


def refine_feature(
    workspace: Path,
    recap: str,
    user_request: str,
    session_id: str | None = None,
    session_harness: harnesses.HarnessName | None = None,
) -> FeatureResult:
    """Apply a follow-up request to a feature that already ran."""
    return _run(
        workspace,
        prompts.refine(recap, user_request),
        schemas.REFINEMENT_SCHEMA,
        schemas.parse_refinement_summary,
        session_id,
        session_harness,
    )


def _run(
    workspace: Path,
    prompt: str,
    output_schema: dict,
    parse: Callable[[str], dict],
    session_id: str | None,
    session_harness: harnesses.HarnessName | None,
    read_only: bool = False,
) -> FeatureResult:
    harness = harnesses.create_harness()
    # A session only means something to the harness that made it. If the
    # configured harness has changed since, start fresh, as a missing session does.
    if session_id and session_harness != harness.name:
        print(
            f"{harness.tags} session {session_id} belongs to {session_harness} - starting fresh",
            flush=True,
        )
        session_id = None
    outcome = harness.run_turn(
        workspace,
        prompt,
        output_schema,
        session_id=session_id,
        read_only=read_only,
    )
    # A turn that did not finish has already raised, so reaching here means the
    # harness has something to show for it.
    #
    # Raises BadOutputError if the reply is not the shape we asked for
    try:
        summary = parse(outcome.text)
    except AppError as exc:
        harness.tag(exc)
        raise
    return FeatureResult(
        summary=summary, session_id=outcome.session_id, harness=outcome.harness
    )
