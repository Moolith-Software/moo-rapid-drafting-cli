"""
The contract every cloning driver implements.

Kept apart from driver.py so a driver can inherit the contract without
importing the module that chooses between drivers. base.py imports nothing
from this package, driver.py and the three drivers import base.py, and nothing
points back the other way.
"""

from abc import ABC, abstractmethod
from pathlib import Path


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

    # --- Not built yet ---

    @abstractmethod  # noqa: V105 — on the contract; nothing calls destroy() yet
    def destroy(self, folder: str) -> None:
        """Delete a branch and reclaim its space. Not built on any driver yet."""
