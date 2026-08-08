"""
The Feature Engine — the boxes from the flow diagram, one function each:

  Copy Codebase       -> clone_base() / clone_from()   (macOS copy-on-write)
  Pre-cache / Warm     -> warm()                        (placeholder, see note)
  Setup preview/build  -> setup_preview()               (placeholder, see note)
  Execute AI           -> codex_runner.run_codex()      (does the real editing)
  Status Emit          -> emit()                        (writes status to SQLite)

`run_add` and `run_refine` string these together and are meant to be launched on
a background thread so the HTTP request returns immediately and the frontend
polls for status.
"""

import hashlib
import subprocess
import time
from pathlib import Path

import db
from codex_runner import run_codex

BACKEND_DIR = Path(__file__).parent
BASE_DIR = BACKEND_DIR.parent / "base"            # the pristine seed codebase
WORKSPACES_DIR = BACKEND_DIR / "workspaces"       # per-feature CoW clones live here

# Files/dirs we ignore when detecting what Codex changed.
SKIP = {"node_modules", "dist", ".git", ".DS_Store"}


# --- Status Emit -----------------------------------------------------------

def emit(feature_id: int, status: str | None = None, progress: str | None = None) -> None:
    """Write the current status/progress to the DB so the /status endpoint sees it."""
    fields = {}
    if status is not None:
        fields["status"] = status
    if progress is not None:
        fields["progress"] = progress
    if fields:
        db.update_feature(feature_id, **fields)


# --- Copy Codebase (copy-on-write) -----------------------------------------

def clone_base(folder_name: str) -> Path:
    """CoW-clone the pristine base/ into workspaces/<folder_name>."""
    return _cow_copy(BASE_DIR, WORKSPACES_DIR / folder_name)


def clone_from(source_folder: str, folder_name: str) -> Path:
    """CoW-clone an existing workspace (e.g. a parent feature) into a new one."""
    return _cow_copy(WORKSPACES_DIR / source_folder, WORKSPACES_DIR / folder_name)


def _cow_copy(source: Path, dest: Path) -> Path:
    """
    Clone `source` to `dest` using APFS copy-on-write (`cp -c`). This is near
    instant and takes no extra disk until files are modified, so cloning the
    whole app (node_modules and all) is cheap. Falls back to a normal copy if
    the filesystem does not support clonefile.
    """
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        subprocess.run(["rm", "-rf", str(dest)], check=True)
    result = subprocess.run(["cp", "-c", "-R", str(source), str(dest)])
    if result.returncode != 0:  # not APFS? fall back to a plain copy
        subprocess.run(["cp", "-R", str(source), str(dest)], check=True)
    return dest


# --- Pre-cache / Warm (placeholder) ----------------------------------------

def warm(workspace: Path) -> None:
    """
    Placeholder for the 'warm the LLM on this codebase' box.

    OpenAI applies prompt caching automatically on repeated prefixes, so there is
    no explicit warm call to make with the Codex CLI. In a fuller build this is
    where you would prime a cache across several parallel features at once. We
    keep the step here to stay faithful to the diagram.
    """
    return None


# --- Setup preview / build tools (placeholder) -----------------------------

def setup_preview(workspace: Path) -> None:
    """
    Placeholder for the 'setup preview / build tools' box.

    Because each workspace is a CoW clone of base/ (which already has
    node_modules), it is immediately runnable — you can `cd` into it and
    `npm run dev` to preview. Automating a managed dev server is out of scope for
    this prototype.
    """
    return None


# --- Execute AI + full pipelines -------------------------------------------

def run_add(feature_id: int) -> None:
    """
    Full 'features/add' pipeline for a brand new feature. Run on a background
    thread. Emits status at every step so the frontend can poll along.
    """
    feature = db.get_feature(feature_id)
    try:
        emit(feature_id, status="copying", progress="Cloning the codebase (copy-on-write)…")
        if feature["parent_id"]:
            parent = db.get_feature(feature["parent_id"])
            workspace = clone_from(parent["code_folder_name"], feature["code_folder_name"])
        else:
            workspace = clone_base(feature["code_folder_name"])

        emit(feature_id, status="warming", progress="Preparing the model…")
        warm(workspace)
        setup_preview(workspace)

        emit(feature_id, status="running", progress="Codex is implementing the feature…")
        before = snapshot(workspace)
        result = run_codex(
            workspace,
            _add_prompt(feature["feature"]),
            on_progress=lambda line: emit(feature_id, progress=line),
        )
        after = snapshot(workspace)
        changes = diff_snapshots(before, after)

        if result["ok"]:
            emit(feature_id, status="completed", progress="Done.")
            db.update_feature(
                feature_id,
                file_changes=changes,
                summary=result["summary"] or f"Applied {len(changes)} file change(s).",
            )
        else:
            emit(feature_id, status="failed", progress=f"Codex exited with code {result['exit_code']}.")
    except Exception as exc:  # keep the row honest if anything blows up
        emit(feature_id, status="failed", progress=f"Error: {exc}")


def run_refine(feature_id: int, user_request: str) -> None:
    """
    Full 'features/refine' pipeline. Re-runs Codex on the SAME workspace so the
    refinement builds on the prior change, then appends a refinement object (with
    an AI-written summary) to the feature.
    """
    feature = db.get_feature(feature_id)
    workspace = WORKSPACES_DIR / feature["code_folder_name"]
    try:
        emit(feature_id, status="running", progress="Codex is refining the feature…")
        before = snapshot(workspace)
        result = run_codex(
            workspace,
            _refine_prompt(feature, user_request),
            on_progress=lambda line: emit(feature_id, progress=line),
        )
        after = snapshot(workspace)
        changes = diff_snapshots(before, after)

        refinements = feature["refinements"]
        refinements.append({
            "refinement_id": len(refinements) + 1,
            "user_request": user_request,
            "file_changes": changes,
            "summary": result["summary"] or f"Applied {len(changes)} file change(s).",
        })
        db.update_feature(feature_id, refinements=refinements)
        emit(
            feature_id,
            status="completed" if result["ok"] else "failed",
            progress="Done." if result["ok"] else f"Codex exited with code {result['exit_code']}.",
        )
    except Exception as exc:
        emit(feature_id, status="failed", progress=f"Error: {exc}")


def _add_prompt(feature: str) -> str:
    return (
        "You are editing an existing Vue 3 + TypeScript + Vite app.\n"
        "Implement the following feature request by editing the files directly.\n"
        "Match the existing code style and keep the app building.\n"
        "When you are done, briefly summarise what you changed in plain English.\n\n"
        f"Feature request:\n{feature}"
    )


def _refine_prompt(feature: dict, user_request: str) -> str:
    history = feature["summary"] or feature["feature"]
    return (
        "You are refining a change you made earlier to this Vue 3 + TypeScript app.\n"
        f"The feature so far:\n{history}\n\n"
        "Apply the following refinement by editing the files directly, keeping the "
        "existing style, and keeping the app building. When done, briefly summarise "
        "what you changed in plain English.\n\n"
        f"Refinement request:\n{user_request}"
    )


# --- Change detection (snapshot diff, since workspaces aren't git repos) ----

def snapshot(root: Path) -> dict:
    """Map every source file (relative path -> content hash), skipping SKIP dirs."""
    out = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP for part in path.relative_to(root).parts):
            continue
        rel = str(path.relative_to(root))
        out[rel] = hashlib.md5(path.read_bytes()).hexdigest()
    return out


def diff_snapshots(before: dict, after: dict) -> list[dict]:
    """Compare two snapshots into a list of {path, kind} where kind is created/edited/deleted."""
    changes = []
    for path, digest in after.items():
        if path not in before:
            changes.append({"path": path, "kind": "created"})
        elif before[path] != digest:
            changes.append({"path": path, "kind": "edited"})
    for path in before:
        if path not in after:
            changes.append({"path": path, "kind": "deleted"})
    return sorted(changes, key=lambda c: c["path"])
