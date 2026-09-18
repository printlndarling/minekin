"""The golden schema file must describe what the migrations actually build.

`schema.sql` is documentation, so nothing breaks when it drifts — which is
exactly why it did. This test makes the drift loud: it applies the golden file
to one database and the migrations to another, then compares what SQLite ended
up with.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from minekin_core.adapters.sqlite.connection import SCHEMA_VERSION, connect_writer

GOLDEN = Path(__file__).resolve().parents[2] / "src/minekin_core/adapters/sqlite/schema.sql"


def schema_of(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row[0]): str(row[1])
        for row in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def test_the_golden_schema_builds_every_object_the_migrations_build(tmp_path: Path) -> None:
    golden_connection = sqlite3.connect(":memory:", isolation_level=None)
    golden_connection.executescript(GOLDEN.read_text(encoding="utf-8"))
    migrated_connection = connect_writer(tmp_path / "kin.sqlite3")

    golden = schema_of(golden_connection)
    migrated = schema_of(migrated_connection)

    assert sorted(golden) == sorted(migrated), (
        "schema.sql and migrations/ describe different tables; "
        f"only in schema.sql: {sorted(set(golden) - set(migrated))}, "
        f"only in migrations: {sorted(set(migrated) - set(golden))}"
    )
    differing = sorted(name for name in golden if golden[name] != migrated[name])
    assert differing == [], f"schema.sql DDL differs from the migration DDL for {differing}"
    golden_connection.close()
    migrated_connection.close()


def test_the_golden_schema_declares_the_current_version(tmp_path: Path) -> None:
    golden_connection = sqlite3.connect(":memory:", isolation_level=None)
    golden_connection.executescript(GOLDEN.read_text(encoding="utf-8"))

    assert golden_connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    golden_connection.close()


def test_the_golden_schema_uses_the_frozen_application_id(tmp_path: Path) -> None:
    migrated_connection = connect_writer(tmp_path / "kin.sqlite3")
    golden_connection = sqlite3.connect(":memory:", isolation_level=None)
    golden_connection.executescript(GOLDEN.read_text(encoding="utf-8"))

    assert (
        golden_connection.execute("PRAGMA application_id").fetchone()[0]
        == (migrated_connection.execute("PRAGMA application_id").fetchone()[0])
    )
    golden_connection.close()
    migrated_connection.close()
