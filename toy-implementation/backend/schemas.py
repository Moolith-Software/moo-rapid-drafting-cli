"""
API Contracts
"""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

import constants

# Basic Field Checks
Request = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=constants.MAX_REQUEST_CHARS
    ),
]


class PreloadEnvironmentBody(BaseModel):
    count: int = Field(1, ge=1, le=constants.MAX_ENVIRONMENTS)
    parent_id: int | None = Field(None, ge=1)


class AddBody(BaseModel):
    feature_requests: Annotated[
        list[Request], Field(min_length=1, max_length=constants.MAX_ADD_FEATURES)
    ]
    parent_id: int | None = Field(None, ge=1)


# Trim the original 'feature' response, otherwise 10K chars could become a 10mb response
ECHOED_REQUEST_CHARS = 1000


class QueuedFeature(BaseModel):
    feature_id: int
    feature_request: str  # shortened; see ECHOED_REQUEST_CHARS

    @field_validator("feature_request")
    @classmethod
    def _shorten(cls, value: str) -> str:
        if len(value) <= ECHOED_REQUEST_CHARS:
            return value
        return value[: ECHOED_REQUEST_CHARS - 1] + "…"


class AddResponse(BaseModel):
    """What /core/add hands back: one entry per request, in the order sent."""

    features: list[QueuedFeature]
    status: str


class RefineBody(BaseModel):
    feature_id: int = Field(ge=1)
    user_request: Request
