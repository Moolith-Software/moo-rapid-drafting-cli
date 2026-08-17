"""
Per-feature workspace folders, each a CoW clone (`cp -c`, APFS-only) of base/
or a parent feature. Owns the workspaces dir, folder naming, and cloning —
nothing about features, the database, or the AI.
"""

import subprocess
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
BASE_DIR = BACKEND_DIR.parent / "base"  # the pristine seed codebase
WORKSPACES_DIR = BACKEND_DIR / "workspaces"  # per-feature CoW clones live here


class WorkspaceCopyError(Exception):
    """Raised when _cow_copy fails. Distinct type so callers can tell clone
    failures apart from Codex/AI errors. `message` adds detail beyond `title`."""

    def __init__(self, code: int, title: str, message: str = ""):
        super().__init__(message or title)  # str(exc) is never empty
        self.code = code
        self.title = title
        self.message = message


def new_folder_name(feature_id: int) -> str:
    """
    Build a fresh workspace folder name for a feature using UUID
    Every clone doesn't overwrite/delete or clash with some other one
    """
    return f"feature-{feature_id}-{uuid.uuid4().hex[:8]}"


def path_for(folder_name: str) -> Path:
    """Absolute path of a workspace folder."""
    return WORKSPACES_DIR / folder_name


""" Core cloning functions """


def clone_base(folder_name: str) -> Path:
    """CoW-clone the pristine base/ into workspaces/<folder_name>."""
    return _cow_copy(BASE_DIR, path_for(folder_name))


def clone_from(source_folder: str, folder_name: str) -> Path:
    """CoW-clone an existing workspace (e.g. a parent feature) into a new one."""
    return _cow_copy(path_for(source_folder), path_for(folder_name))


def _cow_copy(source: Path, dest: Path) -> Path:
    """
    Clone `source` to `dest` via APFS copy-on-write (`cp -c`) — near-instant
    and cheap even for a full node_modules tree (macos only).

    CREATE-ONLY: `dest` should always be a fresh path, so an existing `dest`
    or a failed clone (non-APFS volume) raises rather than silently falling
    back to a slow full copy.  Dest should not exist though already since we
    are using uuid's in the folder.
    """
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise WorkspaceCopyError(1000, "Workspace already exists")
    if subprocess.run(["cp", "-c", "-R", str(source), str(dest)]).returncode != 0:
        raise WorkspaceCopyError(
            1001, "Copy-on-write unavailable", f"{dest} is likely not on an APFS volume"
        )
    return dest
