"""
Per-feature workspaces, each a copy-on-write clone of the base image or of a
parent feature.
Owns the workspaces dir, folder naming, and cloning only, not features,
the database, or the AI.
"""

import uuid
from pathlib import Path

from . import cloning

BACKEND_DIR = Path(__file__).resolve().parents[1]
SOURCE_APP_DIR = BACKEND_DIR.parent / "base"  # the app build_base() copies in
WORKSPACES_DIR = BACKEND_DIR / "workspaces"

# Chosen once, by platform. Raises here rather than at the first clone, so an
# unsupported host fails at startup with a reason instead of mid-feature.
_driver = cloning.get_driver(WORKSPACES_DIR)


def driver_name() -> str:
    """Which driver is doing the copying — for logs and benchmarks."""
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
    Close workspaces a previous run left open, and return how many.

    A killed process releases nothing, so its workspaces stay open and hold
    memory. Call once at startup.
    """
    return _driver.sweep()


""" Core cloning functions """


def clone_base(folder_name: str) -> Path:
    """CoW-clone the base into a new branch named <folder_name>, opened."""
    return _driver.clone_base(folder_name)


def clone_from(source_folder: str, folder_name: str) -> Path:
    """CoW-clone an existing workspace (e.g. a parent feature) into a new one."""
    return _driver.clone_from(source_folder, folder_name)


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
    does not close on its way out — it would unmount the volume Vite is serving.
    """
    _driver.close(folder_name)
