from __future__ import annotations

import io
import json
from datetime import UTC
from pathlib import Path

import pytest

from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.identity_store import read_identity_root
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.application.ports.clock import FakeClock
from minekin_core.bootstrap import main, run
from minekin_core.cli.init import DATABASE_NAME, RUN_DIRECTORY, initialise_identity
from minekin_core.config import (
    DATA_ROOT_VARIABLE,
    USERNAME_VARIABLE,
    configured_username,
    data_root,
)
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError
from minekin_core.domain.ids import KinId

KIN_ID = KinId("kin-01")


def test_the_data_root_is_read_from_the_environment() -> None:
    root = data_root({DATA_ROOT_VARIABLE: str(Path("/srv/minekin").resolve())})

    assert root.is_absolute()
    assert root.name == "minekin"


@pytest.mark.parametrize("value", ["", "   "])
def test_a_missing_data_root_is_refused_rather_than_defaulted(value: str) -> None:
    with pytest.raises(MinekinError, match="required and has no default") as raised:
        data_root({DATA_ROOT_VARIABLE: value})

    assert raised.value.category is ErrorCategory.CONFIG
    assert DATA_ROOT_VARIABLE in raised.value.safe_message


def test_the_data_root_has_no_default_at_all() -> None:
    with pytest.raises(MinekinError, match="required and has no default"):
        data_root({})


@pytest.mark.parametrize("value", ["relative/root", "./here", "../up"])
def test_a_relative_data_root_is_refused(value: str) -> None:
    with pytest.raises(MinekinError, match="absolute path") as raised:
        data_root({DATA_ROOT_VARIABLE: value})

    assert raised.value.category is ErrorCategory.CONFIG


def test_the_username_is_read_from_the_environment() -> None:
    assert configured_username({USERNAME_VARIABLE: "Kin"}) == "Kin"


@pytest.mark.parametrize(
    "value", ["", "   ", "ab", "waytoolongforvanilla", "with space", "with-dash"]
)
def test_an_unusable_username_is_refused(value: str) -> None:
    with pytest.raises(MinekinError) as raised:
        configured_username({USERNAME_VARIABLE: value})

    assert raised.value.category is ErrorCategory.CONFIG


def test_the_username_has_no_default_at_all() -> None:
    with pytest.raises(MinekinError, match="required and has no default"):
        configured_username({})


def test_init_creates_the_identity_root_and_the_run_directory(tmp_path: Path) -> None:
    report = initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())

    assert report.kin_id == "kin-01"
    assert report.username == "Kin"
    assert Path(report.database).is_file()
    assert Path(report.run_root).is_dir()
    assert Path(report.run_root) == tmp_path / "kin" / "kin-01" / RUN_DIRECTORY


def test_the_persisted_identity_matches_the_reported_one(tmp_path: Path) -> None:
    report = initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())

    root = read_identity_root(connect_reader(Path(report.database)))

    assert str(root.kin_id) == report.kin_id
    assert root.material.username == report.username
    assert root.material.identity_revision == report.identity_revision
    # The offline UUID is derived, not stored, so it must still be the reviewed one.
    assert root.material.uuid_id128 == "8f40376bc23f3ef1b5535564eea75639"


def test_a_second_init_is_refused_without_touching_the_first(tmp_path: Path) -> None:
    first = initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())

    with pytest.raises(MinekinError, match="already exists") as raised:
        initialise_identity(KIN_ID, root=tmp_path, username="Notch", clock=FakeClock())

    assert raised.value.category is ErrorCategory.CONFIG
    assert read_identity_root(connect_reader(Path(first.database))).material.username == "Kin"


def test_init_leaves_no_database_behind_when_it_refuses(tmp_path: Path) -> None:
    database = tmp_path / "kin" / "kin-01" / DATABASE_NAME
    database.parent.mkdir(parents=True)
    database.write_bytes(b"")

    with pytest.raises(MinekinError, match="already exists"):
        initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())

    assert database.read_bytes() == b""


def test_a_second_kin_gets_its_own_root(tmp_path: Path) -> None:
    first = initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())
    second = initialise_identity(
        KinId("kin-02"), root=tmp_path, username="Notch", clock=FakeClock()
    )

    assert first.database != second.database
    assert first.run_root != second.run_root


def test_the_report_is_evidence_ready(tmp_path: Path) -> None:
    report = initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())

    assert report.as_dict() == {
        "schema_version": 1,
        "status": "created",
        "kin_id": "kin-01",
        "username": "Kin",
        "identity_revision": 1,
        "database": str(tmp_path / "kin" / "kin-01" / DATABASE_NAME),
        "run_root": str(tmp_path / "kin" / "kin-01" / RUN_DIRECTORY),
    }


def test_the_cli_creates_a_kin_when_the_operator_has_stated_where_and_who(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")
    stdout, stderr = io.StringIO(), io.StringIO()

    code = run(["init", "--kin-id", "kin-01"], stdout=stdout, stderr=stderr)

    assert code == int(ExitCode.OK)
    assert json.loads(stdout.getvalue())["status"] == "created"


def test_the_cli_refuses_to_create_a_kin_without_a_data_root(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(DATA_ROOT_VARIABLE, raising=False)
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")

    code = main(["init", "--kin-id", "kin-01"])

    assert code == int(ExitCode.CONFIG)
    assert DATA_ROOT_VARIABLE in capsys.readouterr().err


def test_the_cli_refuses_to_create_a_kin_without_a_username(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    monkeypatch.delenv(USERNAME_VARIABLE, raising=False)

    code = main(["init", "--kin-id", "kin-01"])

    assert code == int(ExitCode.CONFIG)
    assert USERNAME_VARIABLE in capsys.readouterr().err


@pytest.mark.parametrize("kin_id", ["", "with space", "semi;colon", "slash/name"])
def test_the_cli_refuses_an_unusable_kin_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kin_id: str,
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")

    code = main(["init", "--kin-id", kin_id])

    assert code == int(ExitCode.CONFIG)
    assert "kin-id" in capsys.readouterr().err


@pytest.mark.parametrize("kin_id", ["-leading"])
def test_argparse_rejects_a_kin_id_that_is_not_a_value(
    kin_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")

    with pytest.raises(SystemExit):
        run(["init", "--kin-id", kin_id], stdout=io.StringIO(), stderr=io.StringIO())


def test_init_writes_nothing_outside_the_stated_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The only directories created are the ones the operator named."""

    root = tmp_path / "home"
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(root))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")

    run(["init", "--kin-id", "kin-01"], stdout=io.StringIO(), stderr=io.StringIO())

    assert sorted(path.name for path in tmp_path.iterdir()) == ["home"]


def test_the_system_clock_reports_monotonic_and_aware_utc() -> None:
    clock = SystemClock()

    first = clock.monotonic()
    second = clock.monotonic()
    now = clock.utc_now()

    assert second >= first
    assert now.value.tzinfo is not None
    assert now.value.utcoffset() is not None
    assert now.isoformat().endswith("Z")


def test_the_system_clock_timestamp_is_accepted_by_the_identity_record(tmp_path: Path) -> None:
    report = initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=SystemClock())

    root = read_identity_root(connect_reader(Path(report.database)))

    assert root.material.created_at.endswith("Z")
    assert "T" in root.material.created_at
    assert len(root.material.created_at) >= 20


def test_the_fake_clock_keeps_identity_creation_deterministic(tmp_path: Path) -> None:
    from datetime import datetime

    stamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    report = initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock(utc=stamp))

    root = read_identity_root(connect_reader(Path(report.database)))

    assert root.material.created_at == "2026-01-02T03:04:05Z"
