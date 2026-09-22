"""
Making a cheap copy of the app, one driver per operating system.

    driver.py    the WorkspaceDriver contract and get_driver(). Start here.
    macos.py     one sparse image per branch, cloned with clonefile(2)
    linux.py     one btrfs image holding every branch, mounted once. UNVERIFIED
    windows.py   undecided; a placeholder that can't be created yet

The drivers differ in more than mechanism. On macOS a branch must be mounted
before it is a path, so open/close cost 277 ms; on Linux a subvolume is already
a path, so they are free. Callers pair open/close regardless and never learn
which they are on.
"""

from .driver import WorkspaceDriver, get_driver

__all__ = ["WorkspaceDriver", "get_driver"]
