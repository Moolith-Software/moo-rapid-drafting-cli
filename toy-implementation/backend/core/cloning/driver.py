"""
What every cloning driver provides, and how this machine's driver is picked.
"""

import sys
from abc import ABC, abstractmethod
from pathlib import Path

from ..errors import CopyUnavailable


class WorkspaceDriver(ABC):
    """
    How one operating system clones the app, and where the branches live.

    The methods below __init__ are abstract, so a driver missing one can't be
    created.
    """

    #: Short identifier for logs, e.g. "macos-sparse-images".
    name: str

    def __init__(self, root: Path):
        """Every driver is created with the folder its branches live in."""
        self.root = root

    # --- Setup ---

    @abstractmethod
    def build_base(self, source: Path) -> None:
        """
        Copy `source`, the base app, into the base that branches clone from.

        Called once per project, when the project is set up: it copies every
        file, which is what lets every clone after it be O(1).
        """

    @abstractmethod
    def sweep(self) -> int:
        """Release what a killed run left open; return how many. Runs at startup."""

    # --- Core cloning functions ---

    @abstractmethod
    def clone_base(self, folder: str) -> Path:
        """
        Clone the base into a new branch named `folder`, opened and ready.

        Never replaces an existing branch: a taken name raises WorkspaceExists.
        """

    @abstractmethod
    def clone_from(self, source_folder: str, folder: str) -> Path:
        """Clone an existing branch, changes included, into a new branch `folder`."""

    # --- Using a workspace ---

    @abstractmethod
    def open(self, folder: str) -> Path:
        """
        Make a branch usable and return its path. Idempotent.

        macOS mounts an image here (~280 ms); on Linux the path already exists.
        """

    @abstractmethod
    def close(self, folder: str) -> None:
        """Release a branch opened by `open`. Its files survive."""

    # --- Not built yet ---

    @abstractmethod
    def destroy(self, folder: str) -> None:
        """Delete a branch and reclaim its space. Not built on any driver yet."""


def get_driver(root: Path) -> WorkspaceDriver:
    """
    The driver for this operating system

    workspace_manager calls this once, when it is first imported, and keeps the
    result for the life of the app.
    """
    # Imported here, not at the top: each driver file imports this one.
    if sys.platform == "darwin":
        from .macos import SparseImages as driver_class
    elif sys.platform.startswith("linux"):
        from .linux import BtrfsImage as driver_class
    elif sys.platform == "win32":
        from .windows import VirtualDisks as driver_class
    else:
        raise CopyUnavailable(f"no copy-on-write driver for {sys.platform}")

    try:
        return driver_class(root)
    except TypeError as exc:
        # A driver that hasn't implemented every method can't be created.
        raise CopyUnavailable(f"{driver_class.__name__} is incomplete: {exc}") from exc
