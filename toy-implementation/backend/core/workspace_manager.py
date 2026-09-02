"""
Per-feature workspace folders, each a CoW clone (`clonefile(2)`, APFS-only)
of base/ or a parent feature. Owns the workspaces dir, folder naming, and
cloning — nothing about features, the database, or the AI.
"""

import ctypes
import os
import shutil
import uuid
from pathlib import Path

from .errors import CopyUnavailable, WorkspaceExists

BACKEND_DIR = Path(__file__).resolve().parents[1]  # this file lives in core/
BASE_DIR = BACKEND_DIR.parent / "base"  # the pristine seed codebase
WORKSPACES_DIR = BACKEND_DIR / "workspaces"  # per-feature CoW clones live here

# clonefile(2) clones a whole tree in one syscall, and has no stdlib wrapper.
_libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
_libc.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
_libc.clonefile.restype = ctypes.c_int


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
    Clone `source` to `dest` via APFS copy-on-write (`clonefile(2)`) —
    near-instant and cheap even for a full node_modules tree (macos only).

    CREATE-ONLY: `dest` should always be a fresh path, so an existing `dest`
    or a failed clone (non-APFS volume) raises rather than silently falling
    back to a slow full copy.  Dest should not exist though already since we
    are using uuid's in the folder.
    """
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise WorkspaceExists(str(dest))
    if _libc.clonefile(bytes(source), bytes(dest), 0) != 0:
        reason = os.strerror(ctypes.get_errno())
        shutil.rmtree(dest, ignore_errors=True)  # discard any half-cloned tree
        raise CopyUnavailable(f"{dest}: {reason}")
    return dest
