"""
macOS - every branch is its own sparse disk image.

Branching clones a single image file, however many files are inside it, and
`hdiutil attach` mounts the clone as an ordinary folder.

    cloning/assets/macos-pristine.sparseimage   the pristine image: shipped, empty
    workspaces/
        _base.sparseimage                 the base: the pristine image with the
                                          source app copied in, read-only
        feature-3-a1b2c3d4.sparseimage    a branch
        .mounts/feature-3-a1b2c3d4/       where that branch is mounted while open
"""

import ctypes
import os
import shutil
import subprocess
import threading
from pathlib import Path

from core.errors import CopyUnavailableError, WorkspaceExistsError

from .base import WorkspaceDriver

# Shipped uncompressed on purpose; see assets/README.md.
PRISTINE = Path(__file__).parent / "assets" / "macos-pristine.sparseimage"


class SparseImages(WorkspaceDriver):
    """Sparse disk images, cloned with clonefile(2) and mounted with hdiutil."""

    name = "macos-sparse-images"

    def __init__(self, root: Path):
        super().__init__(root)
        self.mount_root = root / ".mounts"
        self.base_image = root / "_base.sparseimage"
        self._lock = threading.Lock()  # stops two threads mounting one image

    # --- Setup ---

    def build_base(self, source: Path) -> None:
        """Build the base once: the pristine image with the app copied in."""
        if self.base_image.exists():
            return
        if not source.is_dir():
            raise CopyUnavailableError(f"no base app to copy in: {source}")
        self.root.mkdir(parents=True, exist_ok=True)

        # Built under a temporary name, so a crash mid-copy can't leave a
        # half-filled image that later looks like a finished base.
        building = self.root / "_base.building.sparseimage"
        building.unlink(missing_ok=True)
        try:
            self._clone_pristine(building)
            self._copy_app_in(source, building)
            building.rename(self.base_image)
            self.base_image.chmod(0o444)  # the base is written once, here
        except Exception:
            building.unlink(missing_ok=True)
            raise

    def sweep(self) -> int:
        """Unmount every mounted image, and return how many."""
        if not self.mount_root.is_dir():
            return 0
        closed = 0
        with self._lock:
            for mount in list(self.mount_root.iterdir()):
                if os.path.ismount(mount):
                    closed += 1
                self._detach(mount.name)  # also removes an empty leftover folder
        return closed

    # --- Core cloning functions ---

    def clone_base(self, folder: str) -> Path:
        return self._clone(self.base_image, folder)

    def clone_from(self, source_folder: str, folder: str) -> Path:
        return self._clone(self.root / f"{source_folder}.sparseimage", folder)

    # --- Using a workspace ---

    def open(self, folder: str) -> Path:
        """Mount a branch's image, unless it already is, and return where."""
        image = self.root / f"{folder}.sparseimage"
        if not image.exists():
            raise CopyUnavailableError(f"no such workspace: {folder}")
        mount = self.mount_root / folder
        with self._lock:
            mount.mkdir(parents=True, exist_ok=True)
            if not os.path.ismount(mount):
                run_hdiutil(
                    "attach", str(image), "-nobrowse", "-mountpoint", str(mount)
                )
        return mount

    def close(self, folder: str) -> None:
        """
        Unmount a branch. Its image and files survive.

        Only the preview calls this, because its dev server is the last thing
        using a branch. Branches nobody closes stay mounted (~10 MB each) until
        sweep() on the next start; 60+ at once measured fine.
        """
        with self._lock:
            self._detach(folder)

    # --- Not built yet ---

    def destroy(self, folder: str) -> None:  # noqa: V105 - required by the contract; nothing calls destroy() yet
        """
        TODO: unmount the branch, then delete its image.

        The only way to get space back: an image never shrinks, and
        `hdiutil compact` fails with "Function not implemented".
        """

    # --- Helpers ---

    def _clone_pristine(self, dest: Path) -> None:
        """Clone the shipped pristine image to `dest`, ready to copy the app into."""
        if not PRISTINE.exists():
            raise CopyUnavailableError(f"shipped image missing: {PRISTINE}")
        copy_on_write(PRISTINE, dest)  # needs the same APFS volume as workspaces/
        dest.chmod(0o644)

    def _copy_app_in(self, source: Path, image: Path) -> None:
        """Mount `image`, copy everything inside `source` into it, then unmount."""
        folder = image.stem  # "_base.building", mounted like any branch
        mount = self.open(folder)
        try:
            copy_directory(source, mount)
        finally:
            self.close(folder)

    def _clone(self, source: Path, folder: str) -> Path:
        """
        Clone the base or a branch into a new branch, and mount it.

        Never replaces an existing branch: a taken name raises WorkspaceExistsError.
        """
        dest = self.root / f"{folder}.sparseimage"
        if dest.exists():
            raise WorkspaceExistsError(str(dest))
        if not source.exists():
            raise CopyUnavailableError(f"nothing to clone from: {source}")

        # The source may be mounted with writes still in memory; sync flushes
        # them. It can't help if something is still writing, so callers clone a
        # parent whose turn has finished.
        subprocess.run(["sync"], check=False)

        # Creates nothing when it fails, so there is nothing to clean up - and
        # deleting `dest` here could delete someone else's branch.
        copy_on_write(source, dest)
        try:
            dest.chmod(0o644)  # clones inherit the base's read-only 0444
            return self.open(folder)
        except Exception:
            dest.unlink(missing_ok=True)  # the clone succeeded, so it's ours
            raise

    def _detach(self, folder: str) -> None:
        """Unmount an image if it's mounted, then remove its mount folder."""
        mount = self.mount_root / folder
        if os.path.ismount(mount):
            try:
                run_hdiutil("detach", str(mount), "-quiet")
            except CopyUnavailableError:
                run_hdiutil("detach", str(mount), "-force", "-quiet")
        shutil.rmtree(mount, ignore_errors=True)


# --- macOS commands ---

# clonefile(2) has no Python wrapper, so we call it from the C library.
_libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)


def copy_on_write(source: Path, dest: Path) -> None:
    """Clone `source` to `dest` without copying its data, or raise saying why not."""
    if _libc.clonefile(bytes(source), bytes(dest), 0) != 0:
        raise CopyUnavailableError(f"{dest}: {os.strerror(ctypes.get_errno())}")


def copy_directory(source: Path, dest: Path) -> None:
    """Copy everything inside `source` into `dest`, or raise saying why not."""
    # ditto is macOS's built-in copy command; it keeps symlinks and permissions.
    proc = subprocess.run(
        ["ditto", str(source), str(dest)], capture_output=True, text=True
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()
        raise CopyUnavailableError(
            f"copying {source}: {detail[-1] if detail else proc.returncode}"
        )


def run_hdiutil(*args: str) -> str:
    """Run hdiutil, or raise with whatever it complained about."""
    proc = subprocess.run(["hdiutil", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise CopyUnavailableError(
            f"hdiutil {args[0]}: {detail[-1] if detail else proc.returncode}"
        )
    return proc.stdout
