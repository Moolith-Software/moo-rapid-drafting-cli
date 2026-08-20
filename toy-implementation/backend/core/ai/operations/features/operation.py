"""
Have an AI build or refine a feature by editing a workspace
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ... import providers
from ...providers import Provider
from . import prompts, schemas


@dataclass
class FeatureResult:
    """What the pipeline needs after the AI has had its turn."""

    ok: bool
    summary: dict  # a FeatureSummary; see schemas.parse_feature_summary
    session_id: str  # store this to resume or fork later
    usage: dict = field(default_factory=dict)
    error: str | None = None


def implement(
    workspace: Path,
    feature: str,
    on_progress: Callable[[str], None],
    session_id: str | None = None,
    fork_from: str | None = None,
    provider: Provider | None = None,
) -> FeatureResult:
    """Build a feature that has not been started yet."""
    return _run(
        workspace, prompts.add(feature), on_progress, session_id, fork_from, provider
    )


def refine(
    workspace: Path,
    recap: str,
    user_request: str,
    on_progress: Callable[[str], None],
    session_id: str | None = None,
    provider: Provider | None = None,
) -> FeatureResult:
    """Apply a follow-up request to a feature that already ran."""
    return _run(
        workspace,
        prompts.refine(recap, user_request),
        on_progress,
        session_id,
        None,
        provider,
    )


def _run(
    workspace: Path,
    prompt: str,
    on_progress: Callable[[str], None],
    session_id: str | None,
    fork_from: str | None,
    provider: Provider | None,
) -> FeatureResult:
    # Pass a provider to pin this call to one; otherwise build the configured one.
    provider = provider or providers.create_provider()
    on_progress(f"Using the {provider.name} provider…")
    outcome = provider.run_turn(
        workspace,
        prompt,
        schemas.OUTPUT_SCHEMA,
        on_progress,
        session_id=session_id,
        fork_from=fork_from,
    )
    return FeatureResult(
        ok=outcome.ok,
        summary=schemas.parse_feature_summary(outcome.text),
        session_id=outcome.session_id,
        usage=outcome.usage,
        error=outcome.error,
    )
