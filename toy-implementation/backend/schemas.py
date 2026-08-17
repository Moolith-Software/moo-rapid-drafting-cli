"""
The response contract for the human-readable layer.

This Pydantic model is the ONLY structured thing we ask Codex to return. It
covers the narrative ("what did this feature do?"), stored in the DB. It does
NOT describe file changes — those are detected deterministically from the
filesystem (see changes.snapshot / diff_snapshots), so the model is never trusted
as the source of truth for what changed.

Reused two ways:
  FeatureSummary.model_json_schema()      -> the output_schema handed to Codex
  FeatureSummary.model_validate_json(txt) -> parse + validate Codex's reply
"""

from pydantic import BaseModel, ConfigDict, Field


class FeatureSummary(BaseModel):
    # OpenAI's strict structured outputs reject a schema unless it sets
    # `additionalProperties: false` and lists every property in `required`.
    # extra="forbid" is what makes Pydantic emit the former.
    model_config = ConfigDict(extra="forbid")

    feature_title: str = Field(
        description="A short, clean, human-readable name for this feature (a few words)."
    )
    summary: str = Field(
        description="One or two plain-English sentences describing what changed."
    )
    # Required, not defaulted: strict structured outputs demand that every
    # property appear in the schema's `required` list, and Pydantic only puts a
    # field there if it has no default. Always answered — empty list if nothing
    # stands out.
    highlights: list[str] = Field(
        description="A few short bullet points of notable changes. Plain text. "
        "Use an empty list if there is nothing notable.",
    )
