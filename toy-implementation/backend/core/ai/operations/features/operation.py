"""
Have an AI build or refine a feature by editing a workspace.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ....errors import AppError
from ... import providers
from . import prompts, schemas


@dataclass
class FeatureResult:
    """Shape of result after implementing code changes from AI model"""

    summary: dict
    session_id: str


def add_feature(
    workspace: Path,
    user_request: str,
    session_id: str | None = None,
    fork_from: str | None = None,
) -> FeatureResult:
    """Build a feature that has not been started yet."""
    return _run(
        workspace,
        prompts.add(user_request),
        schemas.FEATURE_SCHEMA,
        schemas.parse_feature_summary,
        session_id,
        fork_from,
    )


def refine_feature(
    workspace: Path,
    recap: str,
    user_request: str,
    session_id: str | None = None,
) -> FeatureResult:
    """Apply a follow-up request to a feature that already ran."""
    return _run(
        workspace,
        prompts.refine(recap, user_request),
        schemas.REFINEMENT_SCHEMA,
        schemas.parse_refinement_summary,
        session_id,
        None,
    )


def _run(
    workspace: Path,
    prompt: str,
    output_schema: dict,
    parse: Callable[[str], dict],
    session_id: str | None,
    fork_from: str | None,
) -> FeatureResult:
    provider = providers.create_provider()
    outcome = provider.run_turn(
        workspace,
        prompt,
        output_schema,
        session_id=session_id,
        fork_from=fork_from,
    )
    # A turn that did not finish has already raised, so reaching here means the
    # provider has something to show for it.
    #
    # Raises BadOutput if the reply is not the shape we asked for
    try:
        summary = parse(outcome.text)
    except AppError as exc:
        raise provider.tag(exc)
    return FeatureResult(summary=summary, session_id=outcome.session_id)
