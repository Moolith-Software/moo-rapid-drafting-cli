"""
Linux — one btrfs image, mounted once; every workspace is a subvolume inside it.

Rather than one image per workspace as on macOS, Linux gets a *single* store
image containing a copy-on-write filesystem, loop-mounted once at startup.
Branching is then `BTRFS_IOC_SNAP_CREATE_V2` — a snapshot of one B-tree root,
constant time and constant metadata no matter how many files are inside.

    workspaces/
        store.img              sparse; btrfs inside; grows as clones diverge
        .mounts/               where it is mounted, once, for the whole run
            _base/             subvolume built from the source app
            feature-3-a1b2c3/  a branch: snapshot of _base or of another branch

Two things fall out of putting the filesystem inside an image rather than
relying on the host's:

    the host filesystem stops mattering    ext4, xfs, zfs underneath — it is
                                           just a file. Debian and Ubuntu
                                           default to ext4, which has no
                                           reflink, so this is what makes them
                                           work at all.

    no per-workspace mount                 a subvolume is a path the moment it
                                           exists, so open() only checks and
                                           close() does nothing. macOS pays
                                           277 ms to open a workspace; here it
                                           is free.

The image is sparse and sized generously up front, so it occupies only what has
been written and grows on its own as clones diverge — no resizing step.

WHAT THIS STILL NEEDS:

    root, once      loop-mounting requires CAP_SYS_ADMIN. Once the store is
                    mounted, everything else — snapshot, read, write — is
                    unprivileged.

    btrfs-progs     `mkfs.btrfs` formats the store on first run, and is the
                    only thing that needs it — snapshots go through ioctls
                    directly. A ~2 MB package, already present on Fedora and
                    openSUSE, `apt install btrfs-progs` on Debian and Ubuntu.

    the btrfs kernel module. Nothing in user space can substitute for it.
                    RHEL/CentOS 8+ removed btrfs entirely and cannot mount the
                    store at all.

NOTHING SHIPS. The store is created locally by `truncate` + `mkfs.btrfs`, which
costs one download of zero bytes. Shipping a pre-made image looks appealing —
an empty btrfs image compresses to almost nothing — but decompressing it writes
every zero byte back out, so a 16 G artifact lands as 16 G of real disk rather
than a sparse file. Creating it locally is both smaller to distribute and
correct on arrival, and it lets the ceiling be a local choice.

UNVERIFIED — written on a Mac against the kernel's ioctl contract, never run.
The ioctl numbers, the sparse-file behaviour under btrfs, and unprivileged
snapshot creation all want confirming on a real Linux box before this is
trusted.
#BLACKBOX-NEEDS_REVIEW
"""

import fcntl
import os
import struct
import subprocess
from pathlib import Path
from shutil import which

from ..errors import CopyUnavailable, WorkspaceExists
from .driver import WorkspaceDriver

# Ceiling for the store, not its size on disk. The file is sparse: it measures
# 0 bytes at creation and grows by itself as workspaces diverge, so this costs
# nothing to set generously and nothing is ever downloaded at this size.
#
# Sized once rather than grown, because growing a btrfs filesystem means
# truncate + `losetup -c` + `btrfs filesystem resize`, and that last step would
# need btrfs-progs at runtime rather than only at first format.
#
# 16 G against a worst case of ~13 G (1,000 branches all installing
# dependencies; realistically ~1 G). Override for a small disk; `df` inside the
# store reports whatever is set here.
STORE_SIZE = os.environ.get("WORKSPACE_STORE_SIZE", "16G")

class BtrfsImage(WorkspaceDriver):
    """A single loop-mounted btrfs image; branches are subvolumes in it."""

    name = "linux-btrfs-image"

    def __init__(self, root: Path):
        super().__init__(root)
        self.store_image = root / "store.img"
        self._mount_root: Path | None = None  # resolved on first use, then cached

    # --- Setup ---

    def build_base(self, source: Path) -> None:
        """
        Create the store image if absent, mount it, and build `_base` once.

        Idempotent at each step, so a half-finished previous run resumes rather
        than starting over.
        """
        if not source.is_dir():
            raise CopyUnavailable(f"no base app to copy in: {source}")
        self.root.mkdir(parents=True, exist_ok=True)

        self._ensure_mounted()

        base = self.mount_root / "_base"
        if base.is_dir():
            return
        create_subvolume(self.mount_root, base.name)
        # cp -a rather than shutil: preserves modes, links and timestamps, and
        # is what the macOS driver's `ditto` does there.
        subprocess.run(["cp", "-a", f"{source}/.", str(base)], check=True)

    def sweep(self) -> int:
        """Nothing to close — no per-workspace handles are ever held."""
        return 0

    # --- Core cloning functions ---

    def clone_base(self, folder: str) -> Path:
        return self._snapshot(self.mount_root / "_base", folder)

    def clone_from(self, source_folder: str, folder: str) -> Path:
        return self._snapshot(self.mount_root / source_folder, folder)

    # --- Using a workspace ---

    def open(self, folder: str) -> Path:
        """
        A subvolume is already a path — this only makes sure the store is up.

        Free, unlike the macOS equivalent, which is why Linux has no mount
        lifecycle to manage.
        """
        self._ensure_mounted()
        path = self.mount_root / folder
        if not path.is_dir():
            raise CopyUnavailable(f"no such workspace: {folder}")
        return path

    def close(self, folder: str) -> None:
        """Nothing to release — the store stays mounted for the whole run."""

    # --- Not built yet ---

    def destroy(self, folder: str) -> None:
        """
        TODO: BTRFS_IOC_SNAP_DESTROY_V2 on the subvolume.

        Deliberately a no-op for now. Cheaper here than on macOS — deleting a
        subvolume frees exactly the blocks it diverged, with no high-water mark
        to work around.
        """

    # --- Helpers ---

    @property
    def mount_root(self) -> Path:
        """
        The directory subvolumes live in.

        On a host that is *already* btrfs — Fedora, openSUSE, Garuda, or anyone
        who chose it at install — that is the workspaces directory itself. No
        image, no mkfs.btrfs, no root: snapshots are unprivileged, so such a
        host needs nothing installed and nothing elevated.

        Anywhere else it is a loop-mounted image standing in for a btrfs host,
        which is what makes ext4 distributions work at all.
        """
        if self._mount_root is None:
            self.root.mkdir(parents=True, exist_ok=True)
            native = fstype(self.root) == "btrfs"
            self._mount_root = self.root if native else self.root / ".mounts"
        return self._mount_root

    def _ensure_image(self) -> None:
        """
        Create and format the store, once.

        Built locally rather than shipped: an empty btrfs image compresses to
        almost nothing, but decompressing it writes every zero back out, so the
        artifact would arrive as STORE_SIZE of real disk instead of a sparse
        file. `truncate` costs nothing and `mkfs.btrfs` writes a few megabytes.
        """
        if self.store_image.exists():
            return

        if which("mkfs.btrfs") is None:
            raise CopyUnavailable(
                "mkfs.btrfs is not installed — the workspace store is formatted "
                "once on first run and needs it. Install btrfs-progs "
                "(`apt install btrfs-progs`, `dnf install btrfs-progs`); it is "
                "already present on Fedora and openSUSE. Nothing needs it "
                "afterwards — snapshots go through ioctls."
            )
        building = self.store_image.with_suffix(".building")
        building.unlink(missing_ok=True)
        try:
            # Sparse: allocates nothing now, grows as workspaces diverge.
            subprocess.run(["truncate", "-s", STORE_SIZE, str(building)], check=True)
            subprocess.run(["mkfs.btrfs", "-q", str(building)], check=True)
            building.rename(self.store_image)
        except subprocess.CalledProcessError as exc:
            building.unlink(missing_ok=True)
            raise CopyUnavailable(f"could not create the store image: {exc}") from exc

    def _ensure_mounted(self) -> None:
        """
        Make sure the store is usable, mounting an image only if we need one.

        Returns immediately on a btrfs host — there is nothing to mount, which
        is the whole point of that path. Otherwise this is the one place root
        is required; if a setup step or an fstab entry mounted it already,
        everything downstream runs unprivileged.
        """
        if self.mount_root == self.root:  # already btrfs — nothing to stand in for
            return

        self._ensure_image()
        self.mount_root.mkdir(parents=True, exist_ok=True)
        if os.path.ismount(self.mount_root):
            if fstype(self.mount_root) != "btrfs":
                raise CopyUnavailable(
                    f"{self.mount_root} is mounted but is not btrfs — unmount it first"
                )
            return

        proc = subprocess.run(
            ["mount", "-o", "loop", str(self.store_image), str(self.mount_root)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise CopyUnavailable(
                f"could not mount the workspace store: {proc.stderr.strip()}\n"
                f"    loop-mounting needs root once per boot. Either run:\n"
                f"        sudo mount -o loop {self.store_image} {self.mount_root}\n"
                f"    or add it to /etc/fstab. Everything after this is unprivileged.\n"
                f"    On RHEL/CentOS 8+ btrfs was removed from the kernel and this "
                f"cannot work at all."
            )

    def _snapshot(self, source: Path, folder: str) -> Path:
        dest = self.mount_root / folder
        if dest.exists():
            raise WorkspaceExists(str(dest))
        if not source.is_dir():
            raise CopyUnavailable(f"nothing to clone from: {source}")

        snapshot(self.mount_root, source, folder)
        return dest


# --- Linux commands ---

# The btrfs volume ioctls, built the way <linux/btrfs.h> builds them:
#
#     #define BTRFS_IOC_SNAP_CREATE_V2 \
#         _IOW(BTRFS_IOCTL_MAGIC, 23, struct btrfs_ioctl_vol_args_v2)
#
# _IOW, not _IOWR — the kernel writes `transid` back, which tempts you into
# _IOWR, but the header says otherwise and the number has to match exactly.
# Getting it wrong yields ENOTTY, not a useful error.
#
# btrfs_ioctl_vol_args_v2 is 4096 bytes: s64 fd, u64 transid, u64 flags,
# u64 unused[4], char name[4040].
#
# The _IOC layout below is the asm-generic one — correct for x86, x86_64, arm,
# arm64, riscv and s390. Alpha, MIPS, PowerPC, PA-RISC and SPARC encode
# direction and size differently, so this would need reworking there.
VOL_ARGS_V2 = 4096
BTRFS_IOCTL_MAGIC = 0x94


def _IOW(nr: int, size: int) -> int:
    """asm-generic _IOW: direction 1, then size, type and command number."""
    return (1 << 30) | (size << 16) | (BTRFS_IOCTL_MAGIC << 8) | nr


SNAP_CREATE_V2 = _IOW(23, VOL_ARGS_V2)  # 0x50009417
SUBVOL_CREATE_V2 = _IOW(24, VOL_ARGS_V2)  # 0x50009418


def _vol_ioctl(parent: Path, request: int, name: str, src_fd: int = 0) -> None:
    """
    Issue a vol_args_v2 ioctl against the directory `name` will be created in.

    The buffer must be mutable: at 4096 bytes it is past the limit for
    fcntl.ioctl's read-only path, and the kernel writes transid back into it.
    """
    args = bytearray(
        struct.pack("=qQQ4Q4040s", src_fd, 0, 0, 0, 0, 0, 0, name.encode())
    )
    fd = os.open(parent, os.O_RDONLY)
    try:
        fcntl.ioctl(fd, request, args, True)
    except OSError as exc:
        raise CopyUnavailable(f"btrfs ioctl for {name}: {exc.strerror}") from exc
    finally:
        os.close(fd)


def create_subvolume(parent: Path, name: str) -> None:
    """Create an empty subvolume `name` inside `parent`."""
    _vol_ioctl(parent, SUBVOL_CREATE_V2, name)


def snapshot(parent: Path, source: Path, name: str) -> None:
    """Snapshot `source` into `parent/name`. O(1) regardless of contents."""
    src_fd = os.open(source, os.O_RDONLY)
    try:
        _vol_ioctl(parent, SNAP_CREATE_V2, name, src_fd)
    finally:
        os.close(src_fd)


def fstype(path: Path) -> str:
    """
    Filesystem type holding `path`, from /proc/self/mountinfo, or "" if unknown.

    Matches the longest mountpoint that is a prefix of `path`, so a nested
    mount wins over the root filesystem it sits inside.
    """
    target = str(path.resolve())
    best_type, best_len = "", -1
    try:
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            fields, _, rest = line.partition(" - ")
            mountpoint = fields.split()[4]
            if target != mountpoint and not target.startswith(
                mountpoint.rstrip("/") + "/"
            ):
                continue
            if len(mountpoint) > best_len:
                best_type, best_len = (rest.split()[0] if rest else ""), len(mountpoint)
    except (OSError, IndexError):
        return ""
    return best_type
