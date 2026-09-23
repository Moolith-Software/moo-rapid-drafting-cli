"""
Deterministic change detection for a workspace.

Codex edits files directly on disk rather than handing back a list of changes, so
we work out what actually changed by hashing the tree before and after a turn and
diffing the two snapshots. This is the source of truth for a feature's file
changes — the model's own summary is narrative only and is never trusted here.

We don't assume Workspaces are already git repos even if they might be,
hence the hand-rolled snapshot instead of a git diff.
"""

import hashlib
from pathlib import Path

# Files/dirs we ignore when detecting what Codex changed.
SKIP = {"node_modules", "dist", ".git", ".DS_Store"}


def snapshot(root: Path) -> dict:
    """Map every source file (relative path -> content hash), skipping SKIP dirs."""
    out = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP for part in path.relative_to(root).parts):
            continue
        rel = str(path.relative_to(root))
        out[rel] = hashlib.md5(path.read_bytes()).hexdigest()
    return out


def diff_snapshots(before: dict, after: dict) -> list[dict]:
    """Compare two snapshots into a list of {path, kind} where kind is created/edited/deleted."""
    changes = []
    for path, digest in after.items():
        if path not in before:
            changes.append({"path": path, "kind": "created"})
        elif before[path] != digest:
            changes.append({"path": path, "kind": "edited"})
    changes.extend(
        {"path": path, "kind": "deleted"} for path in before if path not in after
    )
    return sorted(changes, key=lambda c: c["path"])
