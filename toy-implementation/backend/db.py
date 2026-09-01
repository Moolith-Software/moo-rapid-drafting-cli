"""
SQLite storage for features.

One table, `features`, mirroring the schema from the flow diagram. We keep it
deliberately simple: plain sqlite3 (no ORM), JSON stored as TEXT, and small
helper functions that return plain dicts. This is a prototype, so readability
beats cleverness.
"""

import json
import sqlite3
import time
from pathlib import Path
from core import statuses


# The database lives next to this file, under data/.
DB_PATH = Path(__file__).parent / "data" / "app.db"


# --- storage ----------------------------------------------------------------


def connect() -> sqlite3.Connection:
    """Open a connection with row access by column name."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the features table if needed, then apply lightweight migrations."""
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS features (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id      INTEGER,                       -- set for nested / refinement lineage
            code_folder_name TEXT NOT NULL,               -- the CoW workspace folder name
            feature        TEXT NOT NULL,                 -- the original (possibly rough) feature request
            file_changes   TEXT NOT NULL DEFAULT '[]',    -- JSON: list of {path, kind}, deterministic
            summary        TEXT NOT NULL DEFAULT '{}',     -- JSON: FeatureSummary (AI human-readable layer)
            refinements    TEXT NOT NULL DEFAULT '[]',    -- JSON: [{refinement_id, user_request, file_changes, summary}]
            status         TEXT NOT NULL DEFAULT 'initializing',
            progress       TEXT NOT NULL DEFAULT '',       -- latest live status line (for polling)
            codex_session_id TEXT,                        -- Codex thread/session id (for resume/fork)
            is_dirty       INTEGER NOT NULL DEFAULT 0,    -- the workspace has been edited; never goes back to 0
            created_at     REAL NOT NULL
        )
        """
    )
    conn.commit()

    # Migration: add columns that older databases may be missing.
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(features)")}
    if "codex_session_id" not in existing:
        conn.execute("ALTER TABLE features ADD COLUMN codex_session_id TEXT")
        conn.commit()
    if "is_dirty" not in existing:
        conn.execute(
            "ALTER TABLE features ADD COLUMN is_dirty INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    conn.close()


# --- core / features  ---------------------------------------------------------------


def create_feature(
    feature_request: str = "",
    parent_id: int | None = None,
    status: str = statuses.INITIALIZING,
) -> int:
    """
    Insert a fresh feature row and return its id.

    `code_folder_name` is left empty for whoever clones the workspace to fill
    in, because the folder is named after the id this insert is what creates.
    """
    conn = connect()
    cur = conn.execute(
        """
        INSERT INTO features (parent_id, code_folder_name, feature, status, created_at)
        VALUES (:parent_id, '', :feature_request, :status, :created_at)
        """,
        {
            "parent_id": parent_id,
            "feature_request": feature_request,
            "status": status,
            "created_at": time.time(),
        },
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def claim_ready(feature_request: str, parent_id: int | None = None) -> int | None:
    """
    Hand a preloaded environment to a request, or None when none is available or in ready state.

    Selects and updates in one statement, so two requests can never claim the
    same environment. `parent_id IS :parent_id` matches null-safely, so a request for a
    child only ever gets an environment cloned from that same parent.

    Right now, it returns ascending results (oldest environments), even though the AI
    provider's cache is only guaranteed for 30 minutes after its last write or reuse.
    Otherwise, DESC would never pick up the eldest workspaces. No reaper implemented
    either to automatically prune workspaces/preview environments  older than 30 minutes.
    """
    conn = connect()
    row = conn.execute(
        """
        UPDATE features SET feature = :feature_request, status = :taken, progress = ''
        WHERE id = (
            SELECT id FROM features
            WHERE status = :wanted AND feature = '' AND is_dirty = 0
              AND parent_id IS :parent_id
            ORDER BY created_at LIMIT 1
        )
        RETURNING id
        """,
        {
            "feature_request": feature_request,
            "taken": statuses.QUEUED,
            "wanted": statuses.READY,
            "parent_id": parent_id,
        },
    ).fetchone()
    conn.commit()
    conn.close()
    return row["id"] if row else None


def claim_for_refine(feature_id: int) -> int | None:
    """
    Reserve a feature for refinement, or None when it cannot be refined.

    Checks and transitions in one statement, so of two refine requests for the
    same feature only one ever starts a turn — the other sees None.

    A failed feature is refinable, which is how a failed run gets retried
    """
    conn = connect()
    row = conn.execute(
        """
        UPDATE features SET status = :taken, progress = ''
        WHERE id = :feature_id
          AND status IN (:completed, :failed)
          AND code_folder_name != ''
        RETURNING id
        """,
        {
            "taken": statuses.QUEUED,
            "feature_id": feature_id,
            "completed": statuses.COMPLETED,
            "failed": statuses.FAILED,
        },
    ).fetchone()
    conn.commit()
    conn.close()
    return row["id"] if row else None


def update_feature(feature_id: int, **fields) -> None:
    """
    Patch arbitrary columns on a feature. JSON columns are encoded automatically,
    so callers can pass Python lists/dicts directly.
    """
    if not fields:
        return
    for col in _JSON_COLUMNS:
        if col in fields and not isinstance(fields[col], str):
            fields[col] = json.dumps(fields[col])

    assignments = ", ".join(f"{key} = :{key}" for key in fields)
    conn = connect()
    conn.execute(
        f"UPDATE features SET {assignments} WHERE id = :feature_id",
        {**fields, "feature_id": feature_id},
    )
    conn.commit()
    conn.close()


def set_status(feature_id: int, status: str, progress: str) -> None:
    """Record a pipeline state change (what /status reports)."""
    update_feature(feature_id, status=status, progress=progress)


def get_feature(feature_id: int) -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM features WHERE id = :feature_id", {"feature_id": feature_id}
    ).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def list_features() -> list[dict]:
    conn = connect()
    rows = conn.execute("SELECT * FROM features ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# --- row encoding -----------------------------------------------------------


# JSON columns we transparently encode on write.
_JSON_COLUMNS = ("file_changes", "refinements", "summary")


def _normalize_summary(raw) -> dict:
    """
    Decode the summary column into a FeatureSummary-shaped dict, tolerating old
    rows that stored a plain string (or empty) before we moved to structured JSON.
    """
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
        return {"feature_title": "", "summary": str(value), "highlights": []}
    except (json.JSONDecodeError, TypeError):
        return {"feature_title": "", "summary": raw or "", "highlights": []}


def _row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["file_changes"] = json.loads(data["file_changes"])
    data["refinements"] = json.loads(data["refinements"])
    data["summary"] = _normalize_summary(data["summary"])
    data["is_dirty"] = bool(data["is_dirty"])
    return data
