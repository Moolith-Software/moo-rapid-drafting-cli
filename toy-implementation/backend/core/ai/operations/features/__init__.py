"""
The feature operation: build or refine a feature by editing a workspace.

Self-contained - the prompts that ask for the work, the schema of the reply, and
the meaning of that reply all live here.

    operation.py    add_feature() and refine_feature()
    prompts.py      the instructions we send
    schemas.py      the structured reply contract
"""

from .operation import FeatureResult, add_feature, prewarm_ai_session, refine_feature

__all__ = ["FeatureResult", "add_feature", "prewarm_ai_session", "refine_feature"]
