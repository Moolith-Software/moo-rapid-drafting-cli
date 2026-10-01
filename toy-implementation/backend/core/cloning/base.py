"""
The contract every cloning driver implements.

Kept apart from driver.py so a driver can inherit the contract without
importing the module that chooses between drivers. base.py imports nothing
from this package, driver.py and the three drivers import base.py, and nothing
points back the other way.
"""

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpaceUsed:
    """The workspaces folder, and the filesystem it sits on, in MB."""

    # What the files report, adding up shared data once per file that shares
    # it. A fresh clone looks as big as what it was cloned from.
    logical_mb: float  # noqa: V107 - filled by space_used()
    # What the disk actually spends: shared data counted once.
    actual_mb: float
    # The whole filesystem the folder sits on, not just our share of it.
    filesystem_capacity_mb: float  # noqa: V107 - filled by space_used()
    filesystem_used_mb: float  # noqa: V107 - filled by space_used()
    filesystem_free_mb: float  # noqa: V107 - filled by space_used()


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
        """Release every open workspace; return how many. Runs at startup and shutdown."""

    # --- Core cloning functions ---

    @abstractmethod
    def clone_base(self, folder: str) -> Path:
        """
        Clone the base into a new branch named `folder`, opened and ready.

        Never replaces an existing branch: a taken name raises WorkspaceExistsError.
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

    # --- Space ---

    def space_used(self) -> SpaceUsed:
        """The folder's logical and actual size, and its filesystem's, in MB."""
        logical, actual = self.workspace_size_bytes()
        # The folder may not exist before the base is built; its parent does.
        disk = shutil.disk_usage(self.root if self.root.exists() else self.root.parent)

        def mb(n: int) -> float:
            return round(n / (1024 * 1024), 2)

        return SpaceUsed(
            logical_mb=mb(logical),
            actual_mb=mb(actual),
            filesystem_capacity_mb=mb(disk.total),
            filesystem_used_mb=mb(disk.used),
            filesystem_free_mb=mb(disk.free),
        )

    @abstractmethod
    def workspace_size_bytes(self) -> tuple[int, int]:
        """(logical, actual) bytes used by the whole workspaces folder."""

    # --- Not built yet ---

    @abstractmethod  # noqa: V105 - on the contract; nothing calls destroy() yet
    def destroy(self, folder: str) -> None:
        """Delete a branch and reclaim its space. Not built on any driver yet."""
