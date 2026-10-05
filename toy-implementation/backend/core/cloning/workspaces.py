"""
Per-feature workspaces, each a copy-on-write clone of the base image or of a
parent feature.
Owns the workspaces dir, folder naming, and cloning only, not features,
the database, or the AI.
"""

import uuid
from pathlib import Path

from core.errors import WorkspaceStorageFullError
from settings import SETTINGS

from .base import SpaceUsed
from .driver import get_driver

# The app build_base() copies in; ships with the code, so it is found from here.
SOURCE_APP_DIR = Path(__file__).resolve().parents[3] / "base"

# Chosen once, by platform. Raises here rather than at the first clone, so an
# unsupported host fails at startup with a reason instead of mid-feature.
_driver = get_driver(SETTINGS.paths.workspaces_dir)


def driver_name() -> str:
    """Which driver is doing the copying - for logs and benchmarks."""
    return _driver.name


def new_folder_name(feature_id: int) -> str:
    """
    Build a fresh workspace folder name for a feature using UUID
    Every clone doesn't overwrite/delete or clash with some other one
    """
    return f"feature-{feature_id}-{uuid.uuid4().hex[:8]}"


""" Setup """


def build_base() -> None:
    """
    Build the base from base/, unless it is built already. The only slow call.

    Nothing calls this yet: the add-project endpoint will, once per project,
    passing that project's own source folder rather than SOURCE_APP_DIR.
    clone_base() expects the base to exist, and cloning is O(1) precisely
    because this copy happened once.
    """
    _driver.build_base(SOURCE_APP_DIR)


def sweep() -> int:
    """
    Close every open workspace, and return how many.

    At startup it cleans up after a killed process, which releases nothing, so
    its workspaces stay open and hold memory. At shutdown it closes whatever no
    preview owned, such as a build that failed midway.
    """
    return _driver.sweep()


def space_used() -> SpaceUsed:
    """The workspaces folder's logical and actual size, and its filesystem's, in MB."""
    return _driver.space_used()


""" Core cloning functions """


def clone_base(folder_name: str) -> Path:
    """CoW-clone the base into a new branch named <folder_name>, opened."""
    _ensure_room()
    return _driver.clone_base(folder_name)


def clone_from(source_folder: str, folder_name: str) -> Path:
    """CoW-clone an existing workspace (e.g. a parent feature) into a new one."""
    _ensure_room()
    return _driver.clone_from(source_folder, folder_name)


def _ensure_room() -> None:
    """
    Refuse a new workspace once the folder is already over max_size_gb.

    Only stops new clones: a turn already running may still push it past.
    """
    limit_gb = SETTINGS.workspaces.max_size_gb
    used_gb = _driver.space_used().actual_mb / 1024
    if used_gb >= limit_gb:
        raise WorkspaceStorageFullError(
            f"{used_gb:,.2f} GB used of the {limit_gb:,.2f} GB limit in "
            f"{SETTINGS.paths.workspaces_dir}. Raise settings.workspaces.max_size_gb "
            f"to allow more, or delete workspaces to free space."
        )


""" Using a workspace """


def open_workspace(folder_name: str) -> Path:
    """
    Make a workspace usable and return its path. Idempotent.

    On Linux this only checks; on macOS it mounts.
    """
    return _driver.open(folder_name)


def close_workspace(folder_name: str) -> None:
    """
    Release a workspace. The workspace and its contents survive.

    Only the preview calls this, because the dev server outlives the turn that
    created it and is the last thing using the workspace. A turn deliberately
    does not close on its way out - it would unmount the volume Vite is serving.
    """
    _driver.close(folder_name)
