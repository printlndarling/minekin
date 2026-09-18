from __future__ import annotations

import io
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
from session_support import (  # type: ignore[import-not-found]
    PAYLOAD,
    PROFILE,
    fabricated,
    fake_plan,
    stub_supervisor,
)

from minekin_core.adapters.launcher.artifacts import ArtifactStore, SessionOverlayStore
from minekin_core.adapters.launcher.supervisor import ProcessSupervisor
from minekin_core.application.ports.clock import FakeClock
from minekin_core.bootstrap import main, run
from minekin_core.cli import session as session_module
from minekin_core.cli.init import initialise_identity
from minekin_core.cli.session import (
    database_for,
    require_launchable,
    require_store_complete,
    select_kin,
    session_overlay_path,
    start_session,
)
from minekin_core.config import USERNAME_VARIABLE
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError
from minekin_core.domain.ids import KinId

KIN_ID = KinId("kin-01")


def initialised(tmp_path: Path) -> Path:
    initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())
    return tmp_path


def test_select_kin_takes_the_only_kin_in_the_root(tmp_path: Path) -> None:
    initialised(tmp_path)

    assert select_kin(tmp_path, None) == KIN_ID


def test_select_kin_refuses_an_empty_root(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="run `minekin init` first"):
        select_kin(tmp_path, None)


def test_select_kin_refuses_to_guess_between_two(tmp_path: Path) -> None:
    initialised(tmp_path)
    initialise_identity(KinId("kin-02"), root=tmp_path, username="Notch", clock=FakeClock())

    with pytest.raises(MinekinError, match="more than one Kin") as raised:
        select_kin(tmp_path, None)

    assert "kin-01" in raised.value.safe_message and "kin-02" in raised.value.safe_message


def test_an_explicit_selector_resolves_the_ambiguity(tmp_path: Path) -> None:
    initialised(tmp_path)
    initialise_identity(KinId("kin-02"), root=tmp_path, username="Notch", clock=FakeClock())

    assert select_kin(tmp_path, "kin-02") == KinId("kin-02")


def test_an_unknown_selector_is_refused(tmp_path: Path) -> None:
    initialised(tmp_path)

    with pytest.raises(MinekinError, match="holds no Kin named"):
        select_kin(tmp_path, "kin-99")


def test_the_reviewed_profile_is_not_launchable_yet() -> None:
    """It names a Bridge that has not been built, and says so."""

    from minekin_core.adapters.launcher.launch_plan import build_launch_plan

    with pytest.raises(MinekinError, match="not launchable yet") as raised:
        require_launchable(build_launch_plan(PROFILE))

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert "minekin-bridge" in raised.value.safe_message


def test_a_plan_that_claims_nothing_is_not_launchable() -> None:
    with pytest.raises(MinekinError, match="not launchable yet"):
        require_launchable({"launchable": False, "blockers": []})


def test_an_empty_store_is_refused_with_the_first_missing_artifact(tmp_path: Path) -> None:
    plan, artifact = fabricated()

    with pytest.raises(MinekinError, match="are not in the store yet") as raised:
        require_store_complete(plan, ArtifactStore(tmp_path / "store"))

    assert artifact.coordinate in raised.value.safe_message
    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_a_complete_store_is_accepted(tmp_path: Path) -> None:
    plan, artifact = fabricated()
    store = ArtifactStore(tmp_path / "store")
    store.install(artifact, io.BytesIO(PAYLOAD))

    require_store_complete(plan, store)


def test_a_plan_with_no_artifacts_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="names no artifacts"):
        require_store_complete({"artifacts": []}, ArtifactStore(tmp_path / "store"))


def test_a_malformed_artifact_entry_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="malformed"):
        require_store_complete(
            {"artifacts": [{"coordinate": "x"}]}, ArtifactStore(tmp_path / "store")
        )


def test_the_overlay_path_matches_what_the_store_creates(tmp_path: Path) -> None:
    """The supervisor's log directory is named from this path before it exists."""

    created = SessionOverlayStore(tmp_path / "session").create("session-01", 1)

    assert created == session_overlay_path(tmp_path, "session-01", 1)


def test_start_session_composes_the_steps_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = initialised(tmp_path)
    _, artifact = fabricated()
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)
    runs = tmp_path / "kin" / "kin-01" / "run"
    ArtifactStore(runs / "artifact-store").install(artifact, io.BytesIO(PAYLOAD))

    launch = start_session(
        root=root,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=stub_supervisor,
    )

    assert launch.kin_id == "kin-01"
    assert launch.identity.pid == 4242
    assert Path(launch.overlay).is_dir()
    assert session_overlay_path(runs, "session-01", 1) == Path(launch.overlay)
    assert launch.as_dict()["status"] == "started"


def test_start_session_refuses_before_creating_an_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Readiness is checked first, so a refusal leaves no session directory behind."""

    root = initialised(tmp_path)
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)

    with pytest.raises(MinekinError, match="not in the store yet"):
        start_session(
            root=root,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=1,
            supervisor_factory=stub_supervisor,
        )

    assert not (tmp_path / "kin" / "kin-01" / "run" / "session" / "session-01").exists()


def test_start_session_uses_the_persisted_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = initialised(tmp_path)
    _, artifact = fabricated()
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)
    runs = tmp_path / "kin" / "kin-01" / "run"
    ArtifactStore(runs / "artifact-store").install(artifact, io.BytesIO(PAYLOAD))
    seen: list[str] = []

    def factory(log_directory: Path) -> ProcessSupervisor:
        capture(log_directory)
        return stub_supervisor(log_directory)

    def capture(log_directory: Path) -> None:
        seen.append(str(log_directory))

    start_session(
        root=root,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=factory,
    )

    assert seen == [str(session_overlay_path(runs, "session-01", 1) / "logs")]
    assert database_for(root, KIN_ID).is_file()


def test_the_cli_refuses_a_session_when_no_kin_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")

    code = main(["session", "start", "--profile", str(PROFILE)])

    assert code == int(ExitCode.CONFIG)
    assert "init" in capsys.readouterr().err


def test_the_cli_reports_a_frozen_but_unimplemented_session_subcommand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    stdout, stderr = io.StringIO(), io.StringIO()

    code = run(["session", "stop"], stdout=stdout, stderr=stderr)

    assert code == int(ExitCode.USAGE)
    assert json.loads(stderr.getvalue())["status"] == "not_implemented"


def test_the_launch_document_is_evidence_ready() -> None:
    from minekin_core.adapters.launcher.supervisor import ProcessIdentity
    from minekin_core.cli.session import SessionLaunch

    launch = SessionLaunch(
        session_id="session-01",
        generation=1,
        kin_id="kin-01",
        run_id="run-01",
        overlay="/run/session/session-01/generation-1",
        identity=ProcessIdentity(pid=7, started_at="2026-01-01T00:00:00Z", argv_digest="a" * 64),
        argv_digest="a" * 64,
    )

    document: Mapping[str, object] = launch.as_dict()

    assert document["pid"] == 7
    assert document["kin_id"] == "kin-01"
    assert json.dumps(document)


def stored_events(database_path: Path) -> list[dict[str, object]]:
    import sqlite3

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT event_type, run_id, session_id, payload_json FROM event ORDER BY position"
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def test_a_started_event_reaches_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = initialised(tmp_path)
    _, artifact = fabricated()
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)
    runs = tmp_path / "kin" / "kin-01" / "run"
    ArtifactStore(runs / "artifact-store").install(artifact, io.BytesIO(PAYLOAD))

    launch = start_session(
        root=root,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=stub_supervisor,
    )

    rows = stored_events(database_for(root, KIN_ID))
    assert [row["event_type"] for row in rows] == ["SessionProcessStarted"]
    assert rows[0]["run_id"] == launch.run_id
    assert rows[0]["session_id"] == "session-01"


def test_a_failed_start_records_a_failure_and_still_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = initialised(tmp_path)
    _, artifact = fabricated()
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)
    runs = tmp_path / "kin" / "kin-01" / "run"
    ArtifactStore(runs / "artifact-store").install(artifact, io.BytesIO(PAYLOAD))

    def refusing_supervisor(log_directory: Path) -> ProcessSupervisor:
        def spawn(*args: object, **kwargs: object) -> object:
            raise OSError("no such file")

        return ProcessSupervisor(
            clock=FakeClock(), spawn=cast(Any, spawn), log_directory=log_directory
        )

    with pytest.raises(MinekinError, match="could not be started"):
        start_session(
            root=root,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=1,
            supervisor_factory=refusing_supervisor,
        )

    rows = stored_events(database_for(root, KIN_ID))
    assert [row["event_type"] for row in rows] == ["SessionProcessFailed"]
    assert json.loads(str(rows[0]["payload_json"]))["category"] == "PROCESS"


def test_a_refusal_before_the_launcher_leaves_no_ledger_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operator error is not a run outcome, so no run has begun."""

    root = initialised(tmp_path)
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)

    with pytest.raises(MinekinError, match="not in the store yet"):
        start_session(
            root=root,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=1,
            supervisor_factory=stub_supervisor,
        )

    assert stored_events(database_for(root, KIN_ID)) == []
