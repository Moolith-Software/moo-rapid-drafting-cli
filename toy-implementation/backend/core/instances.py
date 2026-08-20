"""
Getting a runnable instance ready.

An *instance* is everything a turn needs before it can start: a private copy of
the app, and whichever provider session it should continue from. Preparing one is
the slow part of adding a feature, and it is independent of what the user
actually asked for — which is what makes it worth doing in advance.

Today `prepare()` is called inline by the pipeline. Later a pool can call the
same function ahead of time and hand the result to `run_add`, which does not need
to know the difference.

One constraint shapes this: a provider session does not exist until a turn has
actually run on it — starting a thread and never using it leaves nothing to
resume. So `session_id` is optional. An instance prepared in advance carries one
only if it was primed with a real turn; otherwise the first turn simply starts a
fresh session, which is exactly what happens today.
"""

from dataclasses import dataclass
from pathlib import Path

from . import workspace_manager as workspaces


@dataclass
class Instance:
    """A prepared workspace, and how its first turn should join a conversation."""

    folder: str  # workspace folder name; stored on the feature row
    workspace: Path  # where the code actually is
    session_id: str | None = None  # resume this session, if one is ready
    fork_from: str | None = None  # or branch from a parent feature's session


def prepare(feature_id: int, parent: dict | None = None) -> Instance:
    """
    Give a feature its own copy of the code.

    A top-level feature clones the pristine base app. A child clones its parent's
    workspace and reports the parent's session so its first turn can fork it,
    leaving the parent's own history untouched.
    """
    folder = workspaces.new_folder_name(feature_id)

    if parent is None:
        return Instance(folder=folder, workspace=workspaces.clone_base(folder))

    workspace = workspaces.clone_from(parent["code_folder_name"], folder)
    return Instance(
        folder=folder, workspace=workspace, fork_from=parent["codex_session_id"]
    )
