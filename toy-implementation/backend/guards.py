"""
Preconditions for the /core endpoints.
"""

from fastapi import HTTPException

import db
from core import statuses


def check_parent(parent_id: int | None) -> None:
    """
    Validate parent row, it should exist and be in 'completed' status
    """
    if parent_id is None:
        return
    parent = db.get_feature(parent_id)
    if parent is None:
        raise HTTPException(404, f"parent feature {parent_id} not found")
    if parent["status"] != statuses.COMPLETED:
        raise HTTPException(
            409, f"parent feature {parent_id} is {parent['status']}, not completed"
        )


def check_no_children(feature_id: int) -> None:
    """
    Make sure a parent has no children, blocking refinements so there are no divergences.
    """
    branched = db.count_children(feature_id)
    if branched:
        raise HTTPException(
            409,
            f"feature {feature_id} has {branched} feature(s) branched from it; "
            "branch it again and refine that instead",
        )
