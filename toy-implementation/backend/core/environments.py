"""
Getting a runnable environment ready.

An *environment* is what a turn needs before it can start: a clone of the
code.
"""

from dataclasses import dataclass
from pathlib import Path

from . import workspace_manager as workspaces


@dataclass
class Environment:
    """A clone of the code either from base or parent, ready for a turn to run in."""

    folder: str  # workspace folder name; stored on the feature row
    workspace: Path  # where the code actually is


def prepare_workspace(feature_id: int, parent: dict | None = None) -> Environment:
    """
    Give a feature its own copy of the code.

    A top-level feature clones the base. A child clones its parent's
    workspace and nothing else: it inherits the code, then starts its own
    conversation with the harness about it. Only a refinement continues
    an existing agent turn/conversation thread.
    """
    folder = workspaces.new_folder_name(feature_id)

    if parent is None:
        return Environment(folder=folder, workspace=workspaces.clone_base(folder))

    workspace = workspaces.clone_from(parent["code_folder_name"], folder)
    return Environment(folder=folder, workspace=workspace)
