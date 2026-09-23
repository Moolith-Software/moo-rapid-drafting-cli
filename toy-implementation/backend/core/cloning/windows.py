"""
Windows - not implemented. The design is not settled, and guessing would be
worse than failing loudly.

Two candidate routes, neither verified:

    block-clone a .vhdx on ReFS   the direct analog of the macOS driver.
                                  FSCTL_DUPLICATE_EXTENTS_TO_FILE clones the
                                  one container file in constant time, and the
                                  result is a *peer* rather than a child - so
                                  there is no differencing chain for reads to
                                  walk, and space follows ReFS cluster
                                  granularity (4-64 KB).

    differencing .vhdx            works on plain NTFS, needs no Dev Drive, but
                                  allocates a minimum 1 MB per touched block
                                  (256x coarser than APFS) and grows a parent
                                  chain that every read must walk.

A third, simplest option is per-file ReFS block cloning with no image at all:
no mounting and no runtime elevation, but O(files) metadata - the very thing
the image design exists to avoid. It makes a reasonable unconfigured fallback.

BLOCKED ON FOUR QUESTIONS, none answerable from macOS:

    1. Does Mount-DiskImage require elevation? Run it from a non-elevated
       shell; try AttachVirtualDisk with NO_DRIVE_LETTER before concluding.
    2. Is Dev Drive (ReFS) available on Windows 11 Home? This decides whether
       the preferred route exists for consumer machines at all.
    3. Does ReFS block-cloning degrade at high clone counts? Reference
       counting may fall back to real copies past some threshold.
    4. What does a differencing child actually allocate for a 10-file edit?

Questions 1, 3 and 4 run on a free GitHub Actions windows-latest runner.
Question 2 needs real Windows 11 Home.
#BLACKBOX-NEEDS_REVIEW
"""

from .base import WorkspaceDriver


class VirtualDisks(WorkspaceDriver):
    """
    Placeholder. Inherits the contract and implements none of it, so it can't
    be created: on Windows, get_driver() reports it as incomplete.
    """

    name = "windows-virtual-disks"
