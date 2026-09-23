"""
Making a cheap copy of the app, one driver per operating system.

    workspaces.py  what the rest of the app calls: clone, open, close, sweep
    base.py      the WorkspaceDriver contract every driver implements. Start here.
    driver.py    get_driver(), which picks the driver for this machine
    macos.py     one sparse image per branch, cloned with clonefile(2)
    linux.py     one btrfs image holding every branch, mounted once. UNVERIFIED
    windows.py   undecided; a placeholder that can't be created yet

The drivers differ in more than mechanism. On macOS a branch must be mounted
before it is a path, so open/close cost 277 ms; on Linux a subvolume is already
a path, so they are free. Callers pair open/close regardless and never learn
which they are on.
"""

from .base import WorkspaceDriver
from .driver import get_driver

__all__ = ["WorkspaceDriver", "get_driver"]
