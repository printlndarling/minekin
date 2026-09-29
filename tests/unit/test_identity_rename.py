"""The explicit, confirmed identity rename and the guards around it.

These cover the contract the stable-name decision opened: the only way a persisted
identity changes its name is a deliberate, stopped-session rename that commits a
new revision atomically, resolves the UUID consequence, and leaves every past run
recorded exactly as it played.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from minekin_core.adapters.sqlite.connection import connect_reader, connect_writer
from minekin_core.adapters.sqlite.identity_store import read_identity_root
from minekin_core.application.ports.clock import FakeClock
from minekin_core.bootstrap import run
from minekin_core.cli.init import initialise_identity
from minekin_core.cli.rename import rename_identity, show_identity
from minekin_core.cli.status import ObservedState
from minekin_core.config import DATA_ROOT_VARIABLE
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError
from minekin_core.domain.ids import KinId
from minekin_core.domain.offline_identity import offline_player_uuid

KIN_ID = KinId("kin-01")
ORIGINAL = "Kin"


def _seed(tmp_path: Path, *, username: str = ORIGINAL) -> Path:
    report = initialise_identity(KIN_ID, root=tmp_path, username=username, clock=FakeClock())
    return Path(report.database)


def test_rename_commits_a_new_revision_and_survives_reopening(tmp_path: Path) -> None:
    _seed(tmp_path)

    report = rename_identity(KIN_ID, root=tmp_path, username="Notch")

    assert report.status == "renamed"
    assert report.before.username == ORIGINAL
    assert report.after.username == "Notch"
    assert report.after.identity_revision == 2
    assert report.after.uuid_canonical == str(offline_player_uuid("Notch"))
    assert report.uuid_changed is True

    connection = connect_reader(_database(tmp_path))
    try:
        material = read_identity_root(connection).material
    finally:
        connection.close()
    assert material.username == "Notch"
    assert material.identity_revision == 2


def _database(tmp_path: Path) -> Path:
    return tmp_path / "kin" / str(KIN_ID) / "kin.sqlite3"


def test_the_kin_id_and_created_at_survive_a_rename(tmp_path: Path) -> None:
    _seed(tmp_path)
    connection = connect_writer(_database(tmp_path))
    try:
        before = read_identity_root(connection)
    finally:
        connection.close()

    rename_identity(KIN_ID, root=tmp_path, username="Notch")

    after = read_identity_root(connect_reader(_database(tmp_path)))
    assert after.kin_id == before.kin_id == KIN_ID
    assert after.material.created_at == before.material.created_at
    assert after.material.local_profile_id != before.material.local_profile_id


def test_renaming_to_the_current_name_is_idempotent_and_writes_nothing(tmp_path: Path) -> None:
    _seed(tmp_path)

    report = rename_identity(KIN_ID, root=tmp_path, username=ORIGINAL)

    assert report.status == "unchanged"
    assert report.after.identity_revision == 1
    assert report.uuid_changed is False
    material = read_identity_root(connect_reader(_database(tmp_path))).material
    assert material.identity_revision == 1
    assert material.local_profile_id.value == f"{KIN_ID}-r1"


@pytest.mark.parametrize("bad", ["ab", "too long username!!", "with space", ""])
def test_an_invalid_name_is_refused_before_anything_changes(tmp_path: Path, bad: str) -> None:
    _seed(tmp_path)

    with pytest.raises(MinekinError) as raised:
        rename_identity(KIN_ID, root=tmp_path, username=bad)

    assert raised.value.category is ErrorCategory.CONFIG
    material = read_identity_root(connect_reader(_database(tmp_path))).material
    assert material.username == ORIGINAL
    assert material.identity_revision == 1


def test_a_stale_expected_revision_is_refused_and_does_not_clobber(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Land one rename, then try to rename against the revision the caller first read.
    rename_identity(KIN_ID, root=tmp_path, username="Notch")

    with pytest.raises(MinekinError) as raised:
        rename_identity(KIN_ID, root=tmp_path, username="Alice", expected_revision=1)

    assert raised.value.category is ErrorCategory.STORAGE
    material = read_identity_root(connect_reader(_database(tmp_path))).material
    assert material.username == "Notch"  # the newer rename stands
    assert material.identity_revision == 2


def test_rename_leaves_every_prior_run_record_untouched(tmp_path: Path) -> None:
    database = _seed(tmp_path)
    stamp = "2026-09-18T00:00:00.000Z"
    writer = connect_writer(database)
    writer.execute(
        "INSERT INTO event(event_id, event_type, schema_version, kin_id, run_id, sequence, "
        "correlation_id, monotonic_ns, observed_at_utc, source, trust_class, payload_json, "
        "payload_hash) VALUES ('evt-1', 'SessionIdentityCompared', 1, ?, 'run-01', '1', "
        "'corr-01', 0, ?, 'CORE', 'TRUST_CLASS_CORE', ?, ?)",
        (str(KIN_ID), stamp, json.dumps({"username": ORIGINAL}), "0" * 64),
    )
    writer.close()

    rename_identity(KIN_ID, root=tmp_path, username="Notch")

    reader = connect_reader(database)
    try:
        row = reader.execute(
            "SELECT kin_id, payload_json FROM event WHERE event_id = 'evt-1'"
        ).fetchone()
    finally:
        reader.close()
    # The past run still names the identity it actually played under.
    assert row["kin_id"] == str(KIN_ID)
    assert json.loads(str(row["payload_json"]))["username"] == ORIGINAL


def test_a_failed_rename_write_is_atomic(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Two renames in a row from the same reviewed revision: only the first lands.
    first = rename_identity(KIN_ID, root=tmp_path, username="Notch")
    with pytest.raises(MinekinError):
        rename_identity(KIN_ID, root=tmp_path, username="Alice", expected_revision=1)
    material = read_identity_root(connect_reader(_database(tmp_path))).material
    assert material.username == first.after.username == "Notch"
    assert material.identity_revision == 2


# --- service reads -----------------------------------------------------------


def test_show_identity_reports_the_stored_name_and_offline_uuid(tmp_path: Path) -> None:
    _seed(tmp_path)

    view = show_identity(tmp_path, KIN_ID)

    assert view.username == ORIGINAL
    assert view.uuid_canonical == str(offline_player_uuid(ORIGINAL))
    assert view.identity_revision == 1


# --- CLI write surface -------------------------------------------------------


def _init_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))


def _fake_read_status(state: ObservedState):
    def status(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(state=state)

    return status


def test_cli_rename_without_confirmation_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_env(monkeypatch, tmp_path)
    _seed(tmp_path)

    code = run(
        ["identity", "rename", "--kin-id", str(KIN_ID), "--username", "Notch"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == int(ExitCode.USAGE)
    material = read_identity_root(connect_reader(_database(tmp_path))).material
    assert material.username == ORIGINAL


def test_cli_rename_refuses_a_running_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import minekin_core.bootstrap as bootstrap

    _init_env(monkeypatch, tmp_path)
    _seed(tmp_path)
    monkeypatch.setattr(
        bootstrap,
        "read_status",
        _fake_read_status(ObservedState.RUNNING),
    )

    err = io.StringIO()
    code = run(
        ["identity", "rename", "--kin-id", str(KIN_ID), "--username", "Notch", "--confirm"],
        stdout=io.StringIO(),
        stderr=err,
    )

    assert code == int(ExitCode.CONTROL_SAFETY)
    assert "SESSION_NOT_STOPPED" in err.getvalue()
    material = read_identity_root(connect_reader(_database(tmp_path))).material
    assert material.username == ORIGINAL


def test_cli_rename_of_a_stopped_kin_lands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import minekin_core.bootstrap as bootstrap

    _init_env(monkeypatch, tmp_path)
    _seed(tmp_path)
    monkeypatch.setattr(bootstrap, "read_status", _fake_read_status(ObservedState.IDLE))

    out = io.StringIO()
    code = run(
        ["identity", "rename", "--kin-id", str(KIN_ID), "--username", "Notch", "--confirm"],
        stdout=out,
        stderr=io.StringIO(),
    )

    assert code == int(ExitCode.OK)
    report = json.loads(out.getvalue())
    assert report["status"] == "renamed"
    assert report["after"]["username"] == "Notch"
    material = read_identity_root(connect_reader(_database(tmp_path))).material
    assert material.username == "Notch"


def test_cli_identity_show_prints_the_stored_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_env(monkeypatch, tmp_path)
    _seed(tmp_path)

    out = io.StringIO()
    code = run(["identity", "show", "--kin-id", str(KIN_ID)], stdout=out, stderr=io.StringIO())

    assert code == int(ExitCode.OK)
    assert json.loads(out.getvalue())["username"] == ORIGINAL
