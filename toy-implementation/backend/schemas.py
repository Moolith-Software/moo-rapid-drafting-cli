"""
API Contracts
"""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# Basic Field Checks
Request = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PreloadEnvironmentBody(BaseModel):
    count: int = Field(1, ge=1, le=1000)  # 1000 is assumed maximum # of environments
    parent_id: int | None = None


class AddBody(BaseModel):
    feature: Request
    parent_id: int | None = None


class RefineBody(BaseModel):
    id: int
    user_request: Request
