"""SQLite connection policy and ordered schema migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import Final

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

APPLICATION_ID = 1_296_783_694  # ASCII "MKIN"
APPLICATION_VERSION = "0.0.0"
SCHEMA_VERSION = 2
MIN_SQLITE_VERSION = (3, 37, 0)  # STRICT tables were introduced in 3.37.
WAL_SAFE_VERSION = (3, 51, 3)
WAL_BACKPORTS = {(3, 50, 7), (3, 44, 6)}

# Applied in order, each exactly once. A migration file contains only its own
# DDL; the runner owns the bookkeeping rows and the version bump, so a new
# migration cannot forget to record itself.
MIGRATIONS: Final[tuple[tuple[int, str], ...]] = (
    (1, "0001_initial.sql"),
    (2, "0002_identity_root.sql"),
)

_V1_TABLES: Final[frozenset[str]] = frozenset(
    {"schema_version", "schema_migration", "event", "outbox", "projection"}
)
_EXPECTED_TABLES: Final[Mapping[int, frozenset[str]]] = MappingProxyType(
    {
        1: _V1_TABLES,
        2: _V1_TABLES | {"kin_identity"},
    }
)


class SQLiteCompatibilityError(MinekinError):
    """The database or SQLite runtime cannot safely implement this schema.

    A `MinekinError` rather than a bare `RuntimeError`, because every message
    here says what is wrong and what would satisfy the gate. As an unclassified
    exception the CLI redacted all of them to "unexpected internal failure" —
    which is what a stock Linux host actually got, since its SQLite is older
    than the frozen WAL safety set.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            component="sqlite",
            operation="connect",
            category=ErrorCategory.STORAGE,
            retryability=Retryability.OPERATOR_ACTION,
            safe_message=message,
        )


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
        accepted = " or ".join(".".join(map(str, backport)) for backport in sorted(WAL_BACKPORTS))
        raise SQLiteCompatibilityError(
            f"SQLite {sqlite3.sqlite_version} is outside the validated multi-connection WAL "
            f"safety set: this build accepts {'.'.join(map(str, WAL_SAFE_VERSION))} or newer, "
            f"or the backports {accepted}"
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
    migrate(connection)
    return connection


def assert_reviewed_ledger(connection: sqlite3.Connection) -> None:
    """Refuse a file that is not a ledger this build wrote.

    Nothing here migrates or creates: a reader opens with `mode=ro`. So a file
    that is not a reviewed ledger is either somebody else's database or the
    remains of a migration that rolled back, and both are better named here than
    discovered later as "no such table: kin_identity" — which is what the driver
    says, and what the CLI redacts.

    An unmigrated database is *not* readable on purpose. Nothing in this build
    produces one: `connect_writer` migrates in the same call that opens it, so a
    file without the schema is a state only a failed init leaves behind.
    """

    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version not in _EXPECTED_TABLES:
        raise SQLiteCompatibilityError(
            f"database schema version {version} is not one this build knows: this is "
            f"not a Minekin ledger, or a migration did not complete"
        )
    _validate_schema(connection, version)


def connect_reader(path: Path, *, busy_timeout_ms: int = 5_000) -> sqlite3.Connection:
    """Open a query-only connection to a reviewed ledger, creating nothing."""

    uri = f"{path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms:d}")
    try:
        assert_reviewed_ledger(connection)
    except BaseException:
        connection.close()
        raise
    return connection


def migrate(connection: sqlite3.Connection) -> None:
    """Bring a database up to `SCHEMA_VERSION`, or refuse to touch it."""

    application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
    if application_id not in (0, APPLICATION_ID):
        raise SQLiteCompatibilityError(
            f"database application_id {application_id} is not Minekin ({APPLICATION_ID})"
        )
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version > SCHEMA_VERSION:
        raise SQLiteCompatibilityError(
            f"database schema v{version} is newer than supported v{SCHEMA_VERSION}"
        )
    if version == SCHEMA_VERSION:
        _validate_schema(connection, version)
        return

    if version == 0 and _existing_tables(connection):
        raise SQLiteCompatibilityError(
            "unversioned database contains tables; refusing an implicit destructive migration"
        )

    for target, filename in MIGRATIONS:
        if target <= version:
            continue
        _apply_migration(connection, target, filename)
        version = target
    _validate_schema(connection, version)


def _existing_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _apply_migration(connection: sqlite3.Connection, target: int, filename: str) -> None:
    migration = (
        files("minekin_core.adapters.sqlite")
        .joinpath("migrations", filename)
        .read_text(encoding="utf-8")
    )
    stamp = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
    script = "\n".join(
        [
            "BEGIN IMMEDIATE;",
            migration,
            "INSERT INTO schema_version(singleton, version, applied_at_utc) "
            f"VALUES (1, {target}, {stamp}) "
            "ON CONFLICT(singleton) DO UPDATE SET "
            f"version = {target}, applied_at_utc = {stamp};",
            "INSERT INTO schema_migration("
            "migration_id, from_version, to_version, application_version, "
            "started_at_utc, completed_at_utc, backup_ref"
            f") VALUES ({target}, {target - 1}, {target}, '{APPLICATION_VERSION}', "
            f"{stamp}, {stamp}, NULL);",
            f"PRAGMA user_version = {target};",
            "COMMIT;",
        ]
    )
    try:
        connection.executescript(script)
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise


def _validate_schema(connection: sqlite3.Connection, version: int) -> None:
    if int(connection.execute("PRAGMA application_id").fetchone()[0]) != APPLICATION_ID:
        raise SQLiteCompatibilityError("Minekin application_id is missing")
    missing = _EXPECTED_TABLES[version] - _existing_tables(connection)
    if missing:
        raise SQLiteCompatibilityError(f"schema v{version} is missing tables: {sorted(missing)!r}")
    row = connection.execute("SELECT version FROM schema_version WHERE singleton = 1").fetchone()
    if row is None or int(row[0]) != version:
        raise SQLiteCompatibilityError("schema_version table disagrees with PRAGMA user_version")
    applied = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if applied != version:
        raise SQLiteCompatibilityError(
            f"PRAGMA user_version is v{applied} but the schema was validated as v{version}"
        )
