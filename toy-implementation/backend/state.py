"""
Facts about the machine the backend is running on, detected once at startup.
"""

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class OperatingSystem:
    # macos | linux | windows | unknown. Detection never raises: the code that
    # needs a supported OS (the cloning driver) decides what "unknown" means.
    name: str
    # The raw value, kept for error messages and logs
    platform: str

    @classmethod
    def detect(cls) -> OperatingSystem:
        platform = sys.platform
        if platform == "darwin":
            name = "macos"
        elif platform.startswith("linux"):
            name = "linux"
        elif platform == "win32":
            name = "windows"
        else:
            name = "unknown"
        return cls(name=name, platform=platform)

    @property
    def is_macos(self) -> bool:
        return self.name == "macos"

    @property
    def is_linux(self) -> bool:
        return self.name == "linux"

    @property
    def is_windows(self) -> bool:
        return self.name == "windows"


@dataclass(frozen=True)
class State:
    os: OperatingSystem


STATE = State(os=OperatingSystem.detect())
