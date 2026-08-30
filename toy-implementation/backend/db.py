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
            status         TEXT NOT NULL DEFAULT 'initialized',
            progress       TEXT NOT NULL DEFAULT '',       -- latest live status line (for polling)
            codex_session_id TEXT,                        -- Codex thread/session id (for resume/fork)
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
    conn.close()


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
    return data


def create_feature(feature: str, code_folder_name: str, parent_id: int | None) -> dict:
    """Insert a fresh feature row and return it."""
    conn = connect()
    cur = conn.execute(
        """
        INSERT INTO features (parent_id, code_folder_name, feature, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (parent_id, code_folder_name, feature, statuses.INITIALIZED, time.time()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return get_feature(new_id)


def get_feature(feature_id: int) -> dict | None:
    conn = connect()
    row = conn.execute("SELECT * FROM features WHERE id = ?", (feature_id,)).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def list_features() -> list[dict]:
    conn = connect()
    rows = conn.execute("SELECT * FROM features ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def set_status(feature_id: int, status: str, progress: str) -> None:
    """Record a pipeline state change (what /status reports)."""
    update_feature(feature_id, status=status, progress=progress)


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

    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [feature_id]
    conn = connect()
    conn.execute(f"UPDATE features SET {assignments} WHERE id = ?", values)
    conn.commit()
    conn.close()
