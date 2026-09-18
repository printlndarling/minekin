from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.orphans import (
    MARKER_NAME,
    Liveness,
    default_probe,
    require_no_unresolved_client,
    session_claims,
    write_marker,
)
from minekin_core.adapters.launcher.supervisor import ProcessIdentity, ProcessSupervisor
from minekin_core.application.ports.clock import FakeClock
from minekin_core.bootstrap import main
from minekin_core.cli import session as session_module
from minekin_core.cli.init import initialise_identity
from minekin_core.cli.session import session_overlay_path, start_session
from minekin_core.config import USERNAME_VARIABLE
from minekin_core.domain.errors import (
    ErrorCategory,
    ExitCode,
    MinekinError,
)
from minekin_core.domain.ids import KinId

PROFILE = Path(__file__).resolve().parents[1] / "fixtures/runtime-input/bundle-p0-core-1.21.4.json"
KIN_ID = KinId("kin-01")
PAYLOAD = b"client jar bytes\n"


def identity(pid: int = 4242) -> ProcessIdentity:
    return ProcessIdentity(pid=pid, started_at="2026-01-01T00:00:00Z", argv_digest="a" * 64)


def run_root(tmp_path: Path) -> Path:
    """The Kin's run root, created once however many times a test asks for it."""

    root = tmp_path / "kin" / "kin-01" / "run"
    if not (tmp_path / "kin" / "kin-01" / "kin.sqlite3").exists():
        initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())
    return root


def marked(tmp_path: Path, pid: int = 4242, *, session_id: str = "session-01") -> Path:
    root = run_root(tmp_path)
    overlay = session_overlay_path(root, session_id, 1)
    overlay.mkdir(parents=True)
    return write_marker(overlay, identity=identity(pid), session_id=session_id, generation=1)


def probe(answer: Liveness) -> Callable[[int], Liveness]:
    def answer_with(_pid: int) -> Liveness:
        return answer

    return answer_with


def test_a_recorded_process_is_found_with_the_probes_answer(tmp_path: Path) -> None:
    marked(tmp_path, pid=7777)

    claims = session_claims(run_root(tmp_path), probe=probe(Liveness.ALIVE))

    assert len(claims) == 1
    assert claims[0].session_id == "session-01"
    assert claims[0].generation == 1
    assert claims[0].identity.pid == 7777
    assert claims[0].liveness is Liveness.ALIVE
    assert not claims[0].resolved


def test_the_probe_is_asked_about_the_recorded_pid(tmp_path: Path) -> None:
    marked(tmp_path, pid=7777)
    seen: list[int] = []

    def recording(pid: int) -> Liveness:
        seen.append(pid)
        return Liveness.GONE

    session_claims(run_root(tmp_path), probe=recording)

    assert seen == [7777]


@pytest.mark.parametrize("answer", [Liveness.ALIVE, Liveness.UNKNOWN])
def test_an_unresolved_claim_refuses_a_new_start(tmp_path: Path, answer: Liveness) -> None:
    """UNKNOWN refuses too: "probably gone" is not a reason to add a second player."""

    marked(tmp_path)

    with pytest.raises(MinekinError, match="confirm it is gone") as raised:
        require_no_unresolved_client(run_root(tmp_path), probe=probe(answer))

    assert raised.value.category is ErrorCategory.PROCESS


def test_a_finished_claim_does_not_refuse_a_new_start(tmp_path: Path) -> None:
    marked(tmp_path)

    require_no_unresolved_client(run_root(tmp_path), probe=probe(Liveness.GONE))


def test_the_refusal_names_the_session_and_the_marker_to_remove(tmp_path: Path) -> None:
    marked(tmp_path, session_id="session-09")

    with pytest.raises(MinekinError, match=MARKER_NAME) as raised:
        require_no_unresolved_client(run_root(tmp_path), probe=probe(Liveness.ALIVE))

    assert "session-09" in raised.value.safe_message
    assert "4242" in raised.value.safe_message


def test_a_root_without_markers_is_unresolved_free(tmp_path: Path) -> None:
    run_root(tmp_path)

    require_no_unresolved_client(run_root(tmp_path), probe=probe(Liveness.ALIVE))
    assert session_claims(run_root(tmp_path)) == ()


def test_an_unreadable_marker_is_an_operator_problem(tmp_path: Path) -> None:
    marker = marked(tmp_path)
    marker.write_bytes(b"{ not json")

    with pytest.raises(MinekinError, match="not a readable process marker"):
        session_claims(run_root(tmp_path))


def test_a_marker_with_an_unreviewed_schema_is_refused(tmp_path: Path) -> None:
    marker = marked(tmp_path)
    document = json.loads(marker.read_bytes())
    document["schema_version"] = 99
    marker.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(MinekinError, match="unreviewed marker schema"):
        session_claims(run_root(tmp_path))


def test_a_marker_without_an_identity_is_refused(tmp_path: Path) -> None:
    marker = marked(tmp_path)
    document = json.loads(marker.read_bytes())
    del document["identity"]
    marker.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(MinekinError, match="no recorded process identity"):
        session_claims(run_root(tmp_path))


def test_a_marker_without_a_session_id_is_refused(tmp_path: Path) -> None:
    marker = marked(tmp_path)
    document = json.loads(marker.read_bytes())
    document["session_id"] = ""
    marker.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(MinekinError, match="no session id"):
        session_claims(run_root(tmp_path))


def test_the_marker_records_what_was_started(tmp_path: Path) -> None:
    marker = marked(tmp_path, pid=5150)

    document = json.loads(marker.read_bytes())

    assert document["schema_version"] == 1
    assert document["session_id"] == "session-01"
    assert document["generation"] == 1
    assert document["identity"] == identity(5150).as_document()


def test_every_session_generation_is_scanned(tmp_path: Path) -> None:
    root = run_root(tmp_path)
    for session_id, generation in (("session-a", 1), ("session-a", 2), ("session-b", 1)):
        overlay = session_overlay_path(root, session_id, generation)
        overlay.mkdir(parents=True)
        write_marker(overlay, identity=identity(), session_id=session_id, generation=generation)

    claims = session_claims(root, probe=probe(Liveness.GONE))

    assert [(claim.session_id, claim.generation) for claim in claims] == [
        ("session-a", 1),
        ("session-a", 2),
        ("session-b", 1),
    ]


def test_the_default_probe_refuses_to_guess_on_a_platform_it_cannot_ask() -> None:
    """On Windows `os.kill(pid, 0)` reports a reaped process as still present."""

    import os

    if os.name == "posix":
        pytest.skip("this platform can answer the question")
    assert default_probe(4242) is Liveness.UNKNOWN


def test_the_default_probe_calls_a_pid_that_cannot_exist_gone() -> None:
    assert default_probe(0) is Liveness.GONE
    assert default_probe(-1) is Liveness.GONE


def test_a_real_client_is_still_recorded_when_the_platform_cannot_ask(tmp_path: Path) -> None:
    """A probe is never trusted blindly: what was recorded is what gets reported."""

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        marked(tmp_path, pid=child.pid)

        claims = session_claims(run_root(tmp_path))

        assert [claim.identity.pid for claim in claims] == [child.pid]
        assert claims[0].liveness in {Liveness.ALIVE, Liveness.UNKNOWN}
    finally:
        child.kill()
        child.wait()


def fabricated() -> tuple[dict[str, Any], Artifact]:
    artifact = Artifact(
        coordinate="example:client:1.21.4",
        path="versions/1.21.4/client.jar",
        url="https://example.invalid/client.jar",
        size=len(PAYLOAD),
        sha1=hashlib.sha1(PAYLOAD).hexdigest(),
        kind="client",
    )
    store_path = f"artifact-store/sha1/{artifact.sha1[:2]}/{artifact.sha1}/client.jar"
    plan: dict[str, Any] = {
        "launchable": True,
        "blockers": [],
        "bundle": {"main_class": "example.Main", "minecraft": "1.21.4"},
        "runtime": {
            "jvm_args": ["-cp", store_path, "-Djava.library.path=session/natives"],
            "classpath": [store_path],
            "natives_dir": "session/natives",
            "game_dir": "session/game",
            "assets_dir": "bundle/assets",
            "assets_index_name": "19",
            "version_type": "release",
            "game_arg_template": [
                {"kind": "literal", "value": "--username"},
                {"kind": "placeholder", "name": "auth_player_name"},
            ],
        },
        "artifacts": [asdict(artifact)],
    }
    return plan, artifact


def fake_plan(_profile: Path, *, workspace_root: Path | None = None) -> dict[str, Any]:
    return fabricated()[0]


class StubProcess:
    pid = 4242

    def poll(self) -> int:
        return 0


def stub_supervisor(log_directory: Path) -> ProcessSupervisor:
    def spawn(*args: object, **kwargs: object) -> object:
        return StubProcess()

    return ProcessSupervisor(clock=FakeClock(), spawn=cast(Any, spawn), log_directory=log_directory)


def ready_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = run_root(tmp_path)
    _, artifact = fabricated()
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)
    ArtifactStore(root / "artifact-store").install(artifact, io.BytesIO(PAYLOAD))
    return root


def test_start_session_refuses_while_a_previous_client_is_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = ready_run(tmp_path, monkeypatch)
    overlay = session_overlay_path(root, "session-00", 1)
    overlay.mkdir(parents=True)
    write_marker(overlay, identity=identity(), session_id="session-00", generation=1)

    with pytest.raises(MinekinError, match="confirm it is gone"):
        start_session(
            root=tmp_path,
            profile=PROFILE,
            java_executable=Path("/usr/bin/java"),
            session_id="session-01",
            generation=1,
            supervisor_factory=stub_supervisor,
            probe=probe(Liveness.ALIVE),
        )

    assert not session_overlay_path(root, "session-01", 1).exists()


def test_a_resolved_previous_client_does_not_block_a_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = ready_run(tmp_path, monkeypatch)
    overlay = session_overlay_path(root, "session-00", 1)
    overlay.mkdir(parents=True)
    write_marker(overlay, identity=identity(), session_id="session-00", generation=1)

    launch = start_session(
        root=tmp_path,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=stub_supervisor,
        probe=probe(Liveness.GONE),
    )

    assert launch.session_id == "session-01"


def test_start_session_records_the_client_it_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = ready_run(tmp_path, monkeypatch)

    launch = start_session(
        root=tmp_path,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=stub_supervisor,
        probe=probe(Liveness.GONE),
    )

    marker = session_overlay_path(root, "session-01", 1) / MARKER_NAME
    document = json.loads(marker.read_bytes())

    assert document["session_id"] == "session-01"
    assert document["identity"]["pid"] == 4242
    assert document["identity"]["argv_digest"] == launch.argv_digest


def test_the_cli_surfaces_an_unresolved_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The orphan refusal reaches the operator as a PROCESS exit code, not a crash."""

    ready_run(tmp_path, monkeypatch)
    monkeypatch.setattr("minekin_core.bootstrap.build_launch_plan", fake_plan)
    overlay = session_overlay_path(run_root(tmp_path), "session-00", 1)
    overlay.mkdir(parents=True)
    write_marker(overlay, identity=identity(), session_id="session-00", generation=1)
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")

    code = main(["session", "start", "--profile", str(PROFILE)])

    assert code == int(ExitCode.PROCESS)
    assert MARKER_NAME in capsys.readouterr().err
