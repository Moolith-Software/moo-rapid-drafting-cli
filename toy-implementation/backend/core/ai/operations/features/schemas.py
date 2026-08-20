"""
This Pydantic model is structured response we ask Codex to return. It
covers the narrative ("what feature was added?"), stored in the DB.

Note: specific file changes are detected deterministically from the filesystem

This module owns both directions of the contract:
  OUTPUT_SCHEMA   -> the shape we ask Codex for
  parse_feature_summary() -> validating what it sends back
"""

from pydantic import BaseModel, ConfigDict, Field


class FeatureSummary(BaseModel):
    # OpenAI's strict structured outputs reject a schema unless it sets
    # `additionalProperties: false` and lists every property in `required`.
    # extra="forbid" is what makes Pydantic emit the former.
    model_config = ConfigDict(extra="forbid")

    feature_title: str = Field(
        description="A short, clean, human-readable title for this feature (max one sentence)."
    )
    summary: str = Field(
        description="One or two plain-English sentences describing what was added."
    )
    highlights: list[str] = Field(
        description="A few short bullet points of notable changes. Plain text. "
        "Use an empty list if there is nothing notable.",
    )


# Handed to Codex as `output_schema` on every turn.
OUTPUT_SCHEMA = FeatureSummary.model_json_schema()


def parse_feature_summary(reply: str) -> dict:
    """
    Turn Codex's reply into a FeatureSummary dict.

    The schema constrains the reply, but it arrives as a *string* we still have
    to parse. If that ever fails, keep the raw text as the summary rather than
    failing a turn whose file edits already succeeded.
    """
    try:
        return FeatureSummary.model_validate_json(reply).model_dump()
    except Exception:
        return FeatureSummary(
            feature_title="",
            summary=reply.strip() or "(no summary returned)",
            highlights=[],
        ).model_dump()
