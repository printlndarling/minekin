from __future__ import annotations

import sqlite3
from importlib.resources import files
from pathlib import Path

import pytest

from minekin_core.adapters.sqlite.connection import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    SQLiteCompatibilityError,
    connect_writer,
    migrate,
)
from minekin_core.adapters.sqlite.identity_store import (
    create_identity_root,
    read_identity_root,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.ids import KinId, OpaqueId
from minekin_core.domain.offline_identity import OfflineIdentityMaterial

KIN_ID = KinId("kin-01")


def material(username: str = "Kin") -> OfflineIdentityMaterial:
    return OfflineIdentityMaterial(
        local_profile_id=OpaqueId("kin-01"),
        identity_revision=1,
        username=username,
        created_at="2026-09-19T00:00:00Z",
    )


def migration_sql(filename: str) -> str:
    return (
        files("minekin_core.adapters.sqlite")
        .joinpath("migrations", filename)
        .read_text(encoding="utf-8")
    )


def build_v1_database(path: Path) -> None:
    """A database exactly as the previous schema version left it, with one event."""

    hash_value = "0" * 64
    stamp = "2026-09-18T00:00:00.000Z"
    connection = sqlite3.connect(path, isolation_level=None)
    connection.executescript(
        "\n".join(
            [
                "BEGIN IMMEDIATE;",
                migration_sql("0001_initial.sql"),
                "INSERT INTO schema_version(singleton, version, applied_at_utc) "
                f"VALUES (1, 1, '{stamp}');",
                "INSERT INTO schema_migration("
                "migration_id, from_version, to_version, application_version, "
                "started_at_utc, completed_at_utc, backup_ref"
                f") VALUES (1, 0, 1, '0.0.0', '{stamp}', '{stamp}', NULL);",
                "INSERT INTO event("
                "event_id, event_type, schema_version, kin_id, run_id, sequence, "
                "correlation_id, monotonic_ns, observed_at_utc, source, trust_class, "
                "payload_json, payload_hash"
                ") VALUES ('evt-1', 'SessionStarted', 1, 'kin-01', 'run-01', '1', "
                f"'corr-01', 0, '{stamp}', 'CORE', 'TRUST_CLASS_CORE', '{{}}', '{hash_value}');",
                "COMMIT;",
            ]
        )
    )
    connection.close()


def test_a_fresh_database_migrates_to_the_current_schema(tmp_path: Path) -> None:
    connection = connect_writer(tmp_path / "kin.sqlite3")

    assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == SCHEMA_VERSION
    assert (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='kin_identity'"
        ).fetchone()
        is not None
    )
    connection.close()


def test_every_migration_records_its_own_bookkeeping_row(tmp_path: Path) -> None:
    connection = connect_writer(tmp_path / "kin.sqlite3")

    rows = connection.execute(
        "SELECT migration_id, from_version, to_version FROM schema_migration ORDER BY migration_id"
    ).fetchall()

    assert [(row[0], row[1], row[2]) for row in rows] == [(1, 0, 1), (2, 1, 2)]
    connection.close()


def test_reopening_an_existing_database_is_a_no_op(tmp_path: Path) -> None:
    path = tmp_path / "kin.sqlite3"
    connect_writer(path).close()
    first = connect_writer(path)
    create_identity_root(first, kin_id=KIN_ID, material=material())
    first.close()

    second = connect_writer(path)

    assert second.execute("SELECT count(*) FROM schema_migration").fetchone()[0] == 2
    assert read_identity_root(second).kin_id == KIN_ID
    second.close()


def test_a_v1_database_upgrades_without_losing_rows(tmp_path: Path) -> None:
    path = tmp_path / "kin.sqlite3"
    build_v1_database(path)

    connection = connect_writer(path)

    assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert connection.execute("SELECT event_id FROM event").fetchone()[0] == "evt-1"
    assert connection.execute("SELECT count(*) FROM kin_identity").fetchone()[0] == 0
    connection.close()


def test_an_unversioned_database_with_tables_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "foreign.sqlite3"
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("CREATE TABLE something(id INTEGER PRIMARY KEY)")
    connection.close()

    reopened = sqlite3.connect(path, isolation_level=None)
    with pytest.raises(SQLiteCompatibilityError, match="unversioned database contains tables"):
        migrate(reopened)
    reopened.close()


def test_a_newer_schema_is_refused_rather_than_downgraded(tmp_path: Path) -> None:
    path = tmp_path / "kin.sqlite3"
    connection = connect_writer(path)
    connection.close()

    future = sqlite3.connect(path, isolation_level=None)
    future.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    future.close()

    check = sqlite3.connect(path, isolation_level=None)
    with pytest.raises(SQLiteCompatibilityError, match="newer than supported"):
        migrate(check)
    check.close()


def test_a_foreign_application_id_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "other.sqlite3"
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute(f"PRAGMA application_id = {APPLICATION_ID + 1}")
    connection.close()

    check = sqlite3.connect(path, isolation_level=None)
    with pytest.raises(SQLiteCompatibilityError, match="not Minekin"):
        migrate(check)
    check.close()


def test_the_identity_root_round_trips(tmp_path: Path) -> None:
    connection = connect_writer(tmp_path / "kin.sqlite3")

    created = create_identity_root(connection, kin_id=KIN_ID, material=material())
    read_back = read_identity_root(connection)

    assert read_back == created
    assert read_back.material.username == "Kin"
    assert read_back.material.uuid_id128 == "8f40376bc23f3ef1b5535564eea75639"
    connection.close()


def test_a_second_identity_root_is_refused(tmp_path: Path) -> None:
    """An operator mistake must not silently re-point an existing Kin."""

    connection = connect_writer(tmp_path / "kin.sqlite3")
    create_identity_root(connection, kin_id=KIN_ID, material=material())

    with pytest.raises(MinekinError, match="already has an identity root") as raised:
        create_identity_root(connection, kin_id=KinId("kin-02"), material=material("Notch"))

    assert raised.value.category is ErrorCategory.STORAGE
    assert read_identity_root(connection).kin_id == KIN_ID
    connection.close()


def test_a_missing_identity_root_is_refused_rather_than_created(tmp_path: Path) -> None:
    connection = connect_writer(tmp_path / "kin.sqlite3")

    with pytest.raises(MinekinError, match="only an explicit init") as raised:
        read_identity_root(connection)

    assert raised.value.category is ErrorCategory.STORAGE
    assert connection.execute("SELECT count(*) FROM kin_identity").fetchone()[0] == 0
    connection.close()


def test_an_unknown_uuid_algorithm_is_refused(tmp_path: Path) -> None:
    """A rule change must be visible, not silently produce a different identity."""

    connection = connect_writer(tmp_path / "kin.sqlite3")
    create_identity_root(connection, kin_id=KIN_ID, material=material())
    connection.execute("UPDATE kin_identity SET uuid_algorithm = 'md5-loose'")

    with pytest.raises(MinekinError, match="unknown offline UUID algorithm"):
        read_identity_root(connection)
    connection.close()


def test_a_corrupt_identity_row_is_refused(tmp_path: Path) -> None:
    connection = connect_writer(tmp_path / "kin.sqlite3")
    create_identity_root(connection, kin_id=KIN_ID, material=material())
    connection.execute("UPDATE kin_identity SET username = 'not a valid name'")

    with pytest.raises(MinekinError, match="not readable as an offline identity"):
        read_identity_root(connection)
    connection.close()


def test_the_identity_root_holds_no_transient_state(tmp_path: Path) -> None:
    """Whatever must not survive a restart has no column to live in."""

    connection = connect_writer(tmp_path / "kin.sqlite3")
    columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(kin_identity)").fetchall()
    }

    assert columns == {
        "singleton",
        "kin_id",
        "local_profile_id",
        "identity_revision",
        "username",
        "uuid_algorithm",
        "created_at_utc",
    }
    connection.close()
