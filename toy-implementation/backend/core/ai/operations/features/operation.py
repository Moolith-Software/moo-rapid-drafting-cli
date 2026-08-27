"""
Have an AI build or refine a feature by editing a workspace.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ....errors import ProviderFailed
from ... import providers
from . import prompts, schemas


@dataclass
class FeatureResult:
    """Shape of result after implementing code changes from AI model"""

    summary: dict
    session_id: str


def add_feature(
    workspace: Path,
    feature: str,
    on_progress: Callable[[str], None],
    session_id: str | None = None,
    fork_from: str | None = None,
) -> FeatureResult:
    """Build a feature that has not been started yet."""
    return _run(workspace, prompts.add(feature), on_progress, session_id, fork_from)


def refine_feature(
    workspace: Path,
    recap: str,
    user_request: str,
    on_progress: Callable[[str], None],
    session_id: str | None = None,
) -> FeatureResult:
    """Apply a follow-up request to a feature that already ran."""
    return _run(
        workspace,
        prompts.refine(recap, user_request),
        on_progress,
        session_id,
        None,
    )


def _run(
    workspace: Path,
    prompt: str,
    on_progress: Callable[[str], None],
    session_id: str | None,
    fork_from: str | None,
) -> FeatureResult:
    provider = providers.create_provider()
    on_progress(f"Using the {provider.name} provider…")
    outcome = provider.run_turn(
        workspace,
        prompt,
        schemas.OUTPUT_SCHEMA,
        on_progress,
        session_id=session_id,
        fork_from=fork_from,
    )
    if not outcome.ok:
        raise ProviderFailed(outcome.error or "the turn did not finish")

    # Raises BadOutput if the reply is not the shape we asked for.
    summary = schemas.parse_feature_summary(outcome.text)
    return FeatureResult(summary=summary, session_id=outcome.session_id)
