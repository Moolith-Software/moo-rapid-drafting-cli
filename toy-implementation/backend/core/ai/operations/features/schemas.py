"""
The structured responses we ask Codex to return, and the parsing function

Note: specific file changes are detected deterministically from the filesystem

"""

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.errors import BadOutputError

# OpenAI's strict structured outputs reject a schema unless it sets
# `additionalProperties: false` and lists every property in `required`.
# extra="forbid" is what makes Pydantic emit the former.
_STRICT = ConfigDict(extra="forbid")

_HIGHLIGHTS = Field(
    description="A few short bullet points of notable changes. Plain text. "
    "Use an empty list if there is nothing notable.",
)


class FeatureSummary(BaseModel):
    """What the AI reports after building a feature for the first time."""

    model_config = _STRICT

    feature_title: str = Field(  # noqa: V107 - a key in the JSON the model returns; never read as an attribute
        description="A short, clean, human-readable title for this feature (max one sentence)."
    )
    summary: str = Field(
        description="One or two plain-English sentences describing what was added."
    )
    highlights: list[str] = _HIGHLIGHTS  # noqa: V107 - a key in the JSON the model returns; never read as an attribute


class RefinementSummary(BaseModel):
    """
    What the AI reports after changing a feature that already exists.

    No title: the feature was named on its first turn and a refinement does not
    rename it.
    """

    model_config = _STRICT

    summary: str = Field(
        description="One or two plain-English sentences describing what this "
        "refinement changed about the existing feature."
    )
    highlights: list[str] = _HIGHLIGHTS  # noqa: V107 - a key in the JSON the model returns; never read as an attribute


class PrimingAck(BaseModel):
    """
    Warm-up the LLM with a caching trick.
    """

    model_config = _STRICT

    understood: bool = Field(description="Always true.")  # noqa: V107 - a key in the JSON the model returns; never read as an attribute


FEATURE_SCHEMA = FeatureSummary.model_json_schema()
REFINEMENT_SCHEMA = RefinementSummary.model_json_schema()
PRIMING_SCHEMA = PrimingAck.model_json_schema()


def parse_feature_summary(reply: str) -> dict:
    """Read the reply to a turn that built a feature."""
    return _parse(FeatureSummary, reply)


def parse_refinement_summary(reply: str) -> dict:
    """Read the reply to a turn that refined a feature."""
    return _parse(RefinementSummary, reply)


def parse_priming_ack(reply: str) -> dict:
    """Read the reply to a warm-up turn."""
    return _parse(PrimingAck, reply)


def _parse(model: type[BaseModel], reply: str) -> dict:
    """
    Turn the AI's reply into a dict of the given shape.

    The schema constrains the reply, but it arrives as a *string* we still have
    to parse. A reply that does not match means the turn did not really produce
    what we asked for - an agent that trailed off mid-thought, or a harness that
    does not enforce schemas - so it raises rather than passing off prose as a
    summary.
    """
    if not reply.strip():
        raise BadOutputError("the AI returned an empty reply")

    try:
        return model.model_validate_json(reply).model_dump()
    except ValidationError as exc:
        if any(error["type"] == "json_invalid" for error in exc.errors()):
            raise BadOutputError(f"reply was not valid JSON: {reply[:120]!r}") from exc
        raise BadOutputError(
            f"reply did not match the schema: {reply[:120]!r}"
        ) from exc
