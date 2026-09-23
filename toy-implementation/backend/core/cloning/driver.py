"""
How this machine's cloning driver is picked.
"""

import sys
from pathlib import Path

from core.errors import CopyUnavailableError

from .base import WorkspaceDriver


def get_driver(root: Path) -> WorkspaceDriver:
    """
    The driver for this operating system

    workspaces.py calls this once, when it is first imported, and keeps the
    result for the life of the app.
    """
    # Imported per platform rather than at the top, since they contain incompatible imports
    if sys.platform == "darwin":
        from .macos import SparseImages as driver_class  # noqa: PLC0415
    elif sys.platform.startswith("linux"):
        from .linux import BtrfsImage as driver_class  # noqa: PLC0415
    elif sys.platform == "win32":
        from .windows import VirtualDisks as driver_class  # noqa: PLC0415
    else:
        raise CopyUnavailableError(f"no copy-on-write driver for {sys.platform}")

    try:
        return driver_class(root)
    except TypeError as exc:
        # A driver that hasn't implemented every method can't be created.
        raise CopyUnavailableError(
            f"{driver_class.__name__} is incomplete: {exc}"
        ) from exc
