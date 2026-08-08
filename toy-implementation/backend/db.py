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

# The database lives next to this file, under data/.
DB_PATH = Path(__file__).parent / "data" / "app.db"


def connect() -> sqlite3.Connection:
    """Open a connection with row access by column name."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the features table if it does not exist yet."""
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS features (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id      INTEGER,                       -- set for nested / refinement lineage
            code_folder_name TEXT NOT NULL,               -- the CoW workspace folder name
            feature        TEXT NOT NULL,                 -- the original feature request
            file_changes   TEXT NOT NULL DEFAULT '[]',    -- JSON: list of {path, kind}
            summary        TEXT NOT NULL DEFAULT '',       -- AI-written human-readable summary
            refinements    TEXT NOT NULL DEFAULT '[]',    -- JSON: [{refinement_id, user_request, file_changes, summary}]
            status         TEXT NOT NULL DEFAULT 'initialized',
            progress       TEXT NOT NULL DEFAULT '',       -- latest live status line (for polling)
            created_at     REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


# JSON columns we transparently decode when reading a row out.
_JSON_COLUMNS = ("file_changes", "refinements")


def _row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    for col in _JSON_COLUMNS:
        data[col] = json.loads(data[col])
    return data


def create_feature(feature: str, code_folder_name: str, parent_id: int | None) -> dict:
    """Insert a fresh feature row and return it."""
    conn = connect()
    cur = conn.execute(
        """
        INSERT INTO features (parent_id, code_folder_name, feature, status, created_at)
        VALUES (?, ?, ?, 'initialized', ?)
        """,
        (parent_id, code_folder_name, feature, time.time()),
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
