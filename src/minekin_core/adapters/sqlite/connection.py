"""SQLite connection policy and schema-v1 migration."""

from __future__ import annotations

import sqlite3
from importlib.resources import files
from pathlib import Path

APPLICATION_ID = 1_296_783_694  # ASCII "MKIN"
SCHEMA_VERSION = 1
MIN_SQLITE_VERSION = (3, 37, 0)  # STRICT tables were introduced in 3.37.
WAL_SAFE_VERSION = (3, 51, 3)
WAL_BACKPORTS = {(3, 50, 7), (3, 44, 6)}


class SQLiteCompatibilityError(RuntimeError):
    """The database or SQLite runtime cannot safely implement this schema."""


def supports_multi_connection_wal(version: tuple[int, int, int]) -> bool:
    """Apply the frozen SQLite WAL-corruption safety gate from the P0 plan."""

    return version >= WAL_SAFE_VERSION or version in WAL_BACKPORTS


def connect_writer(path: Path, *, busy_timeout_ms: int = 5_000) -> sqlite3.Connection:
    if sqlite3.sqlite_version_info < MIN_SQLITE_VERSION:
        required = ".".join(map(str, MIN_SQLITE_VERSION))
        raise SQLiteCompatibilityError(
            f"SQLite {required} or newer is required; found {sqlite3.sqlite_version}"
        )
    if not supports_multi_connection_wal(sqlite3.sqlite_version_info):
        raise SQLiteCompatibilityError(
            "SQLite runtime is outside the validated multi-connection WAL safety set: "
            f"{sqlite3.sqlite_version}"
        )
    if busy_timeout_ms < 0:
        raise ValueError("busy_timeout_ms cannot be negative")
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms:d}")
    journal_mode = str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0])
    if journal_mode.casefold() != "wal":
        connection.close()
        raise SQLiteCompatibilityError(f"WAL mode unavailable (journal_mode={journal_mode!r})")
    connection.execute("PRAGMA synchronous = FULL")
    migrate_to_v1(connection)
    return connection


def connect_reader(path: Path, *, busy_timeout_ms: int = 5_000) -> sqlite3.Connection:
    """Open a query-only connection without accidentally creating a database."""

    uri = f"{path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms:d}")
    return connection


def migrate_to_v1(connection: sqlite3.Connection) -> None:
    application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if application_id not in (0, APPLICATION_ID):
        raise SQLiteCompatibilityError(
            f"database application_id {application_id} is not Minekin ({APPLICATION_ID})"
        )
    if version > SCHEMA_VERSION:
        raise SQLiteCompatibilityError(
            f"database schema v{version} is newer than supported v{SCHEMA_VERSION}"
        )
    if version == SCHEMA_VERSION:
        _validate_v1(connection)
        return

    existing_tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if existing_tables:
        raise SQLiteCompatibilityError(
            "unversioned database contains tables; refusing an implicit destructive migration"
        )

    migration = (
        files("minekin_core.adapters.sqlite")
        .joinpath("migrations", "0001_initial.sql")
        .read_text(encoding="utf-8")
    )
    script = "\n".join(
        [
            "BEGIN IMMEDIATE;",
            migration,
            "INSERT INTO schema_version(singleton, version, applied_at_utc) "
            "VALUES (1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));",
            "INSERT INTO schema_migration("
            "migration_id, from_version, to_version, application_version, "
            "started_at_utc, completed_at_utc, backup_ref"
            ") VALUES (1, 0, 1, '0.0.0', "
            "strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), "
            "strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), NULL);",
            "COMMIT;",
        ]
    )
    try:
        connection.executescript(script)
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    _validate_v1(connection)


def _validate_v1(connection: sqlite3.Connection) -> None:
    if int(connection.execute("PRAGMA application_id").fetchone()[0]) != APPLICATION_ID:
        raise SQLiteCompatibilityError("Minekin application_id is missing")
    expected = {"schema_version", "schema_migration", "event", "outbox", "projection"}
    actual = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    missing = expected - actual
    if missing:
        raise SQLiteCompatibilityError(f"schema v1 is missing tables: {sorted(missing)!r}")
    row = connection.execute("SELECT version FROM schema_version WHERE singleton = 1").fetchone()
    if row is None or int(row[0]) != SCHEMA_VERSION:
        raise SQLiteCompatibilityError("schema_version table disagrees with PRAGMA user_version")
