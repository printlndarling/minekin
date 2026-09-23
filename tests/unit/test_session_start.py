from __future__ import annotations

import io
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from minekin_core import bootstrap as bootstrap_module
from minekin_core.adapters.launcher.artifacts import ArtifactStore, SessionOverlayStore
from minekin_core.adapters.launcher.orphans import Liveness
from minekin_core.adapters.launcher.supervisor import ProcessSupervisor
from minekin_core.application.ports.clock import FakeClock
from minekin_core.bootstrap import main, run
from minekin_core.cli import session as session_module
from minekin_core.cli.init import initialise_identity
from minekin_core.cli.session import (
    SessionLaunch,
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
from minekin_core.domain.offline_identity import offline_player_uuid
from session_support import (
    PAYLOAD,
    PROFILE,
    fabricated,
    fake_plan,
    stand_in_for_the_built_workspace,  # type: ignore[import-not-found]
    stub_supervisor,
)

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


def test_the_reviewed_profile_is_sound_but_still_cannot_start(tmp_path: Path) -> None:
    """The recipe no longer blocks; what it needs is a build and a store, not an edit.

    Its Bridge is pinned by digest rather than `build_required`, so the plan is
    launchable. The refusals that remain are about this host: the jar has to
    exist and the artifacts have to be fetched, and both are checked at start
    time rather than baked into the plan's own digest.
    """

    from minekin_core.adapters.launcher.launch_plan import build_launch_plan

    plan = build_launch_plan(PROFILE)

    assert plan["launchable"] is True
    assert plan["blockers"] == []
    # A locally built jar is not something to fetch, so it is not in the list of
    # artifacts the store has to hold.
    assert all("minekin-bridge" not in str(item["coordinate"]) for item in plan["artifacts"])

    with pytest.raises(MinekinError, match="are not in the store yet") as raised:
        require_store_complete(plan, ArtifactStore(tmp_path / "artifact-store"))

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


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
    stand_in_for_the_built_workspace(monkeypatch)
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
    stand_in_for_the_built_workspace(monkeypatch)

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
    stand_in_for_the_built_workspace(monkeypatch)
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


class _StopAfterCapture(Exception):
    """Raised by the stubbed launcher so the CLI stops before it needs a result."""


def test_the_cli_lends_the_client_the_hosts_display_and_not_the_whole_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A managed client is given an environment rather than inheriting one.

    A client with no `DISPLAY` cannot open a window at all, so the virtual
    display the controlled runner provides reaches it only through here — and
    the list of what may be lent is a list in the code, because a forwarded
    value is by definition one the operator's host chose.
    """

    java = tmp_path / "java"
    java.write_text("#!/bin/sh", encoding="utf-8")
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")
    monkeypatch.setenv("MINEKIN_JAVA", str(java))
    monkeypatch.setenv("DISPLAY", ":99")
    monkeypatch.setenv("LD_PRELOAD", "/host/evil.so")
    captured: dict[str, object] = {}

    async def capture(*args: object, **kwargs: object) -> object:
        del args
        captured.update(kwargs)
        raise _StopAfterCapture

    monkeypatch.setattr(bootstrap_module, "start_and_supervise", capture)

    with pytest.raises(_StopAfterCapture):
        run(
            ["session", "start", "--profile", str(PROFILE)],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )

    assert captured["forward_environment"] == {"DISPLAY": ":99"}


def test_the_cli_refuses_a_session_when_no_kin_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")

    code = main(["session", "start", "--profile", str(PROFILE)])

    assert code == int(ExitCode.CONFIG)
    assert "init" in capsys.readouterr().err


def test_the_cli_refuses_a_run_id_that_no_bundle_answers_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`evidence verify` left the placeholder list, so its refusal is asserted here."""

    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))

    code = main(["evidence", "verify", "missing-run"])

    assert code == int(ExitCode.CONFIG)
    assert "no evidence bundle for run missing-run" in capsys.readouterr().err


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
            "SELECT event_type, run_id, session_id, source, trust_class, payload_json "
            "FROM event ORDER BY position"
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
    stand_in_for_the_built_workspace(monkeypatch)
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
    assert [row["event_type"] for row in rows] == ["AuthPolicyFrozen", "SessionProcessStarted"]
    assert all(row["run_id"] == launch.run_id for row in rows)
    assert all(row["session_id"] == "session-01" for row in rows)
    assert rows[0]["source"] == "CORE"
    assert rows[0]["trust_class"] == "CORE"
    assert json.loads(str(rows[0]["payload_json"])) == {
        "auth_mode": "offline",
        "online_adapter_enabled": False,
        "server_profile_id": None,
        "server_profile_revision": None,
    }


def test_a_failed_start_records_a_failure_and_still_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = initialised(tmp_path)
    _, artifact = fabricated()
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)
    stand_in_for_the_built_workspace(monkeypatch)
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
    assert [row["event_type"] for row in rows] == ["AuthPolicyFrozen", "SessionProcessFailed"]
    assert json.loads(str(rows[1]["payload_json"]))["category"] == "PROCESS"


def test_a_refusal_before_the_launcher_leaves_no_ledger_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operator error is not a run outcome, so no run has begun."""

    root = initialised(tmp_path)
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)
    stand_in_for_the_built_workspace(monkeypatch)

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


def test_a_kin_directory_that_cannot_be_an_identifier_is_named(tmp_path: Path) -> None:
    """`KinId(...)` would raise a bare ValueError, which the CLI redacts.

    "the directory is called `my kin`" is the whole diagnosis, and it is not
    derivable from "unexpected internal failure".
    """

    (tmp_path / "kin" / "my kin").mkdir(parents=True)

    with pytest.raises(MinekinError, match="not a usable Kin name") as raised:
        select_kin(tmp_path, None)

    assert raised.value.category is ErrorCategory.CONFIG
    assert "my kin" in raised.value.safe_message


def test_a_start_with_no_ledger_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`session status` already guards this; a start should say the same thing."""

    (tmp_path / "kin" / "kin-01").mkdir(parents=True)
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")

    code = main(["session", "start", "--profile", str(PROFILE)])
    document = json.loads(capsys.readouterr().err)

    assert code == int(ExitCode.CONFIG)
    assert "run `minekin init` first" in document["message"]


def _ready_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A data root whose store is complete, so only the world can refuse."""

    root = initialised(tmp_path)
    _, artifact = fabricated()
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)
    stand_in_for_the_built_workspace(monkeypatch)
    ArtifactStore(tmp_path / "kin" / "kin-01" / "run" / "artifact-store").install(
        artifact, io.BytesIO(PAYLOAD)
    )
    return root


def _save(tmp_path: Path, *, level_dat: bool = True) -> Path:
    save = tmp_path / "prepared-world"
    save.mkdir()
    if level_dat:
        (save / "level.dat").write_bytes(b"a level.dat\n")
    return save


def test_a_world_name_with_no_save_behind_it_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A name with nothing behind it is not a world, and the refusal comes first."""

    root = _ready_root(tmp_path, monkeypatch)

    with pytest.raises(MinekinError, match="--world-save says which one") as raised:
        start_session(
            root=root,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=1,
            supervisor_factory=stub_supervisor,
            world_name="prepared-world",
        )

    assert raised.value.exit_code is ExitCode.CONFIG
    assert not (tmp_path / "kin" / "kin-01" / "run" / "session" / "session-01").exists()


def test_a_save_with_no_name_to_give_it_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _ready_root(tmp_path, monkeypatch)

    with pytest.raises(MinekinError, match="not enterable"):
        start_session(
            root=root,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=1,
            supervisor_factory=stub_supervisor,
            world_save=_save(tmp_path),
        )

    assert not (tmp_path / "kin" / "kin-01" / "run" / "session" / "session-01").exists()


def test_a_save_that_is_not_a_world_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checked before anything is created: an overlay is not where this is discovered."""

    root = _ready_root(tmp_path, monkeypatch)

    with pytest.raises(MinekinError, match=r"has no level\.dat"):
        start_session(
            root=root,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=1,
            supervisor_factory=stub_supervisor,
            world_save=_save(tmp_path, level_dat=False),
            world_name="prepared-world",
        )

    assert not (tmp_path / "kin" / "kin-01" / "run" / "session" / "session-01").exists()


def test_a_world_is_placed_in_the_overlay_a_host_will_run_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The game directory is the overlay, so this is the only place vanilla will look."""

    root = _ready_root(tmp_path, monkeypatch)
    save = _save(tmp_path)

    launch = start_session(
        root=root,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=stub_supervisor,
        world_save=save,
        world_name="prepared-world",
    )

    overlay = Path(launch.overlay)
    assert overlay == session_overlay_path(tmp_path / "kin" / "kin-01" / "run", "session-01", 1)
    assert (overlay / "saves" / "prepared-world" / "level.dat").is_file()


def test_two_generations_of_a_session_each_get_their_own_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Overlays are per generation, so generation 2 is a fresh world, not the played one.

    Generation 1's client is reported gone rather than resolved for real, so the
    second start is not refused by the orphan guard: what is under test here is
    which world each generation's game directory holds.
    """

    root = _ready_root(tmp_path, monkeypatch)
    save = _save(tmp_path)

    def gone(_pid: int) -> Liveness:
        return Liveness.GONE

    def start(generation: int) -> SessionLaunch:
        return start_session(
            root=root,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=generation,
            supervisor_factory=stub_supervisor,
            probe=gone,
            world_save=save,
            world_name="prepared-world",
        )

    first = start(1)
    # Generation 1's overlay is where the client played, so the world in it is no
    # longer the one that was handed over.
    (Path(first.overlay) / "saves" / "prepared-world" / "level.dat").write_bytes(b"played in\n")

    second = start(2)

    second_world = Path(second.overlay) / "saves" / "prepared-world" / "level.dat"
    assert Path(second.overlay) != Path(first.overlay)
    assert second_world.read_bytes() == b"a level.dat\n"


def test_a_world_save_that_is_not_there_is_named_as_a_missing_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typo'd path is not a directory that happens to be missing a file."""

    root = _ready_root(tmp_path, monkeypatch)
    missing = tmp_path / "no-such-world"

    with pytest.raises(MinekinError, match="is not a directory to seed a world from") as raised:
        start_session(
            root=root,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=1,
            supervisor_factory=stub_supervisor,
            world_save=missing,
            world_name="prepared-world",
        )

    assert str(missing) in raised.value.safe_message
    assert not (tmp_path / "kin" / "kin-01" / "run" / "session" / "session-01").exists()


def test_a_started_session_is_not_a_first_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The overlay is a fresh game directory, and a first run stops at onboarding.

    Vanilla shows the accessibility screen for a directory that has never been run,
    and that screen is in front of everything else — including a world this session
    was asked to enter. Measured in the runner: without this file the client's log
    ends at the texture atlases and the seeded world is never touched.
    """

    root = _ready_root(tmp_path, monkeypatch)

    launch = start_session(
        root=root,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=stub_supervisor,
    )

    options = Path(launch.overlay) / "options.txt"
    assert options.is_file()
    assert "onboardAccessibility:true" in options.read_text(encoding="utf-8")


def test_a_world_this_kin_is_already_in_is_refused_before_anything_is_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A world a Kin has been in holds them as that run left them.

    Measured: a save from an earlier run carried a dead Kin, the client went
    straight to the death screen, and the run looked like a run — so this is
    refused at the operator's own moment rather than discovered in a world.
    """

    root = _ready_root(tmp_path, monkeypatch)
    save = _save(tmp_path)
    history = save / "playerdata" / f"{offline_player_uuid('Kin')}.dat"
    history.parent.mkdir()
    history.write_bytes(b"health zero\n")

    with pytest.raises(MinekinError, match="already holds this Kin") as raised:
        start_session(
            root=root,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=1,
            supervisor_factory=stub_supervisor,
            world_save=save,
            world_name="prepared-world",
        )

    assert raised.value.exit_code is ExitCode.CONFIG
    # Nothing was created, including the overlay: the refusal is made where the
    # operator can still change their mind about the world.
    assert not (tmp_path / "kin" / "kin-01" / "run" / "session" / "session-01").exists()


def test_the_port_a_host_publishes_on_is_either_named_or_chosen_by_the_client() -> None:
    """A number that is not a port is refused here rather than sent and refused there."""

    from minekin_core.cli.session import open_lan_command

    command = open_lan_command(
        request_id="lan-1", generation=1, deadline_monotonic_ns=1, port=25570
    )

    assert command.port == 25570
    assert command.generation == 1
    for bad in (-1, 65536):
        with pytest.raises(MinekinError, match="is not a port") as raised:
            open_lan_command(request_id="lan-1", generation=1, deadline_monotonic_ns=1, port=bad)
        assert raised.value.exit_code is ExitCode.CONFIG
