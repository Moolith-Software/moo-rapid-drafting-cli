"""
The backend's top-level controls, grouped by what they govern
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Mock until Tauri supplies the real one: the backend folder this file sits in,
# which is where data/ and workspaces/ already live.
_APP_DATA_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AICodeChanges:
    harness: str = "codex_sdk"  # codex_sdk | mock
    provider: str = "openai"
    model: str = "gpt-5.6"
    # How hard the model should think. Every harness names these differently;
    # gpt-5.6 rejects the SDK's "minimal" and accepts a "max" its enum does not list.
    reasoning_effort: str = "medium"  # none | low | medium | high | xhigh
    turn_timeout_minutes: int = 20

    @property
    def key(self) -> str:
        # Read on access, not at import: main.py loads .env after its imports.
        return (os.environ.get("OPENAI_API_KEY") or "").strip()


@dataclass(frozen=True)
class Concurrency:
    # The pools are built once at startup, so changing these needs a restart.
    max_parallel_features: int = 16
    max_parallel_preloads: int = 8


@dataclass(frozen=True)
class Paths:
    # TODO: once the Tauri shell exists, it resolves app_data_dir() (the per-OS
    # folder for our bundle identifier) and passes it in. Until then this mocks
    # it with the backend folder, so data/ and workspaces/ stay where they are.
    app_data_dir: Path = _APP_DATA_DIR

    # Read once at startup; changing it needs a restart. Changing it while
    # features exist orphans them: the features table stores only
    # code_folder_name, relative to this folder, so every existing row would
    # point at a workspace that is no longer there. Either refuse the change
    # while features exist, or move the folder as part of it.
    #
    # On macOS it must sit on an APFS volume, the same one as the base image,
    # or clonefile(2) cannot clone and every branch becomes a full copy.
    workspaces_dir: Path = _APP_DATA_DIR / "workspaces"


@dataclass(frozen=True)
class Workspaces:
    # Once the workspaces folder is already over this size, no new workspace
    # is created. A turn already running may still push it past.
    max_size_gb: int = 16


@dataclass(frozen=True)
class Settings:
    # TODO: implement default project_id, update relevant endpoints to use it when set
    default_project_id: int | None = None  # noqa: V107 - nothing reads it until projects exist; see the TODO above
    ai_code_changes: AICodeChanges = field(default_factory=AICodeChanges)
    concurrency: Concurrency = field(default_factory=Concurrency)
    paths: Paths = field(default_factory=Paths)
    workspaces: Workspaces = field(default_factory=Workspaces)


SETTINGS = Settings()
