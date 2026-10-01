"""
The SQLite connection, and the migrations that shape it.

Plain sqlite3, no ORM. Every query lives in a repository module next to this
one; this file only opens connections and brings the schema up to date.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from core import errors
from settings import SETTINGS

DB_PATH = SETTINGS.paths.app_data_dir / "data" / "app.db"

# Numbered .sql files, applied in order: 0001_create_features.sql, 0002_...
# TODO: will need to be updated later
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


@contextmanager
def session(*, write: bool = False) -> Iterator[sqlite3.Connection]:
    """
    One connection, one transaction, always closed - and the single place a
    storage failure becomes an AppError.
    """
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)  # 5s busy_timeout by default
        conn.row_factory = sqlite3.Row
        # Off by default, and silently ignored once a transaction is open, so it
        # belongs here and not next to the WAL pragma in init_db.
        conn.execute("PRAGMA foreign_keys = ON")
    except (OSError, sqlite3.Error) as exc:
        raise errors.DatabaseUnavailableError(f"{type(exc).__name__}: {exc}") from exc

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
    Enable WAL, then apply any migrations this database has not had yet.
    """
    with session() as conn:
        # WAL lives in the database file, so it is set once here rather than per connection
        mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if mode != "wal":
            raise errors.DatabaseError(
                f"could not enable WAL; journal_mode is {mode!r}"
            )
        migrate(conn)


def migrate(conn: sqlite3.Connection) -> None:
    """
    Run every migration numbered above the database's `user_version`, in order.

    `user_version` is a spare integer SQLite keeps in the file header, so it
    records the last migration applied without a table of its own. Each file
    and its version bump commit together: a migration that fails leaves the
    database at the version before it, and the next startup tries it again.
    """
    applied = conn.execute("PRAGMA user_version").fetchone()[0]
    migrations = sorted(
        (int(path.name.split("_", 1)[0]), path) for path in MIGRATIONS_DIR.glob("*.sql")
    )
    for version, path in migrations:
        if version <= applied:
            continue
        conn.executescript(
            f"BEGIN;\n{path.read_text()}\nPRAGMA user_version = {version};\nCOMMIT;"
        )
        print(f"[db] applied migration {path.name}", flush=True)
