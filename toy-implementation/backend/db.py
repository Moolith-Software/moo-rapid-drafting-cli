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
from contextlib import contextmanager
from pathlib import Path
from core import errors, statuses


# The database lives next to this file, under data/.
DB_PATH = Path(__file__).parent / "data" / "app.db"


# --- storage ----------------------------------------------------------------


@contextmanager
def _session(*, write: bool = False):
    """
    One connection, one transaction, always closed — and the single place a
    storage failure becomes an AppError.
    """
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)  # 5s busy_timeout by default
        conn.row_factory = sqlite3.Row
    except (OSError, sqlite3.Error) as exc:
        raise errors.DatabaseUnavailable(f"{type(exc).__name__}: {exc}") from exc

    try:
        if write:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise errors.DatabaseError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        conn.close()


def init_db() -> None:
    """
    Enable WAL, create the features table if needed, then apply lightweight
    migrations.
    """
    with _session() as conn:
        # WAL lives in the database file, so it is set once here rather than per connection
        mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if mode != "wal":
            raise errors.DatabaseError(
                f"could not enable WAL; journal_mode is {mode!r}"
            )

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

        # Migration: add columns that older databases may be missing.
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(features)")}
        if "codex_session_id" not in existing:
            conn.execute("ALTER TABLE features ADD COLUMN codex_session_id TEXT")
        if "is_dirty" not in existing:
            conn.execute(
                "ALTER TABLE features ADD COLUMN is_dirty INTEGER NOT NULL DEFAULT 0"
            )


# --- core / features  ---------------------------------------------------------------


def create_feature(parent_id: int | None = None) -> int:
    """
    Insert an empty preload row and return its id.

    `code_folder_name` is left empty for whoever clones the workspace to fill
    in, because the folder is named after the id this insert is what creates.
    """
    with _session() as conn:
        cur = conn.execute(
            """
            INSERT INTO features
                (parent_id, code_folder_name, feature, status, created_at)
            VALUES (:parent_id, '', '', :status, :created_at)
            """,
            {
                "parent_id": parent_id,
                "status": statuses.INITIALIZING,
                "created_at": time.time(),
            },
        )
        return cur.lastrowid


def reserve_features(
    feature_requests: list[str], parent_id: int | None = None
) -> list[tuple[int, str]]:
    """
    Reserve a queued row for every request, and return each id next to the
    request it was given, in the order the requests came in.

    A request takes a preloaded environment when one is free, and gets a fresh
    empty row when none is. Both land in `queued`, and run_add tells them apart
    by whether the row already has a workspace.

    Both halves below already know which request went to which row while they
    are writing it, so they hand that back rather than only the ids.

    One connection and one commit however long the batch is, which is the point:
    several hundred requests reserve in about the time a single one used to.
    """
    if not feature_requests:
        return []

    # write=True enables immediate True which blocks other writers in parallel until complete
    with _session(write=True) as conn:
        # Claim what we can, create fresh rows for the rest, return in order
        claimed = _claim_ready(conn, feature_requests, parent_id)
        uncovered = feature_requests[len(claimed) :]
        created = _create_queued(conn, uncovered, parent_id)
    return claimed + created


def _claim_ready(
    conn: sqlite3.Connection, feature_requests: list[str], parent_id: int | None
) -> list[int]:
    """
    Match preloaded environments that are available to feature requests coming in.

    `parent_id IS :parent_id` matches null-safely, so a request for a child only
    ever gets an environment cloned from that same parent.

    Oldest first, even though the AI provider's cache is only guaranteed for 30
    minutes after its last write or reuse. Newest first would leave the eldest
    workspaces never picked up, and there is no reaper yet to prune workspaces
    or preview environments older than 30 minutes.
    """
    ready = [
        row["id"]
        for row in conn.execute(
            """
            SELECT id FROM features
            WHERE status = :wanted AND feature = '' AND is_dirty = 0
              AND parent_id IS :parent_id
            ORDER BY created_at
            LIMIT :count
            """,
            {
                "wanted": statuses.READY,
                "parent_id": parent_id,
                "count": len(feature_requests),
            },
        )
    ]
    taken = list(zip(ready, feature_requests))
    conn.executemany(
        """
        UPDATE features SET feature = :feature_request, status = :taken, progress = ''
        WHERE id = :feature_id
        """,
        [
            {
                "feature_request": feature_request,
                "taken": statuses.QUEUED,
                "feature_id": feature_id,
            }
            for feature_id, feature_request in taken
        ],
    )
    return taken


def _create_queued(
    conn: sqlite3.Connection, feature_requests: list[str], parent_id: int | None
) -> list[tuple[int, str]]:
    """
    Create an already-claimed row for every request where no environment was available
    and return each id next to its request. These carry no workspace, which tells the
    worker to initialize a fresh environment.
    """
    created_at = time.time()
    rows = []
    for feature_request in feature_requests:
        cur = conn.execute(
            """
            INSERT INTO features (parent_id, code_folder_name, feature, status, created_at)
            VALUES (:parent_id, '', :feature_request, :status, :created_at)
            """,
            {
                "parent_id": parent_id,
                "feature_request": feature_request,
                "status": statuses.QUEUED,
                "created_at": created_at,
            },
        )
        rows.append((cur.lastrowid, feature_request))
    return rows


def claim_for_refine(feature_id: int) -> int | None:
    """
    Reserve a feature for refinement, or None when it cannot be refined.

    Checks and transitions in one statement, so of two refine requests for the
    same feature only one ever starts a turn — the other sees None.

    A failed feature is refinable, which is how a failed run gets retried
    """
    with _session() as conn:
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
    with _session() as conn:
        conn.execute(
            f"UPDATE features SET {assignments} WHERE id = :feature_id",
            {**fields, "feature_id": feature_id},
        )


def set_status(feature_id: int, status: str, progress: str) -> None:
    """Record a pipeline state change (what /status reports)."""
    update_feature(feature_id, status=status, progress=progress)


def get_feature(feature_id: int) -> dict | None:
    with _session() as conn:
        row = conn.execute(
            "SELECT * FROM features WHERE id = :feature_id",
            {"feature_id": feature_id},
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_features() -> list[dict]:
    with _session() as conn:
        rows = conn.execute(
            "SELECT * FROM features ORDER BY created_at DESC"
        ).fetchall()
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
