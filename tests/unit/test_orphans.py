from __future__ import annotations

import io
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from session_support import (
    PROFILE,
    fake_plan,
    kin_root,
    ready_data_root,
    run_root,
    stub_supervisor,
)

from minekin_core.adapters.launcher.orphans import (
    MARKER_NAME,
    IdentityProof,
    Liveness,
    StopOutcome,
    default_cmdline,
    default_probe,
    prove_process_identity,
    require_no_unresolved_client,
    session_claims,
    stop_recorded_clients,
    write_marker,
)
from minekin_core.adapters.launcher.process import argument_digest
from minekin_core.adapters.launcher.supervisor import ProcessIdentity
from minekin_core.bootstrap import main, run
from minekin_core.cli.session import session_overlay_path, start_session
from minekin_core.config import USERNAME_VARIABLE
from minekin_core.domain.errors import (
    ErrorCategory,
    ExitCode,
    MinekinError,
)
from minekin_core.domain.ids import KinId

KIN_ID = KinId("kin-01")


def identity(pid: int = 4242, *, argv_digest: str = "a" * 64) -> ProcessIdentity:
    return ProcessIdentity(pid=pid, started_at="2026-01-01T00:00:00Z", argv_digest=argv_digest)


def marked(
    tmp_path: Path,
    pid: int = 4242,
    *,
    session_id: str = "session-01",
    argv_digest: str = "a" * 64,
) -> Path:
    root = run_root(kin_root(tmp_path))
    overlay = session_overlay_path(root, session_id, 1)
    overlay.mkdir(parents=True)
    return write_marker(
        overlay,
        identity=identity(pid, argv_digest=argv_digest),
        session_id=session_id,
        generation=1,
    )


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


def test_start_session_refuses_while_a_previous_client_is_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready_data_root(tmp_path, monkeypatch)
    runs = run_root(kin_root(tmp_path))
    overlay = session_overlay_path(runs, "session-00", 1)
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

    assert not session_overlay_path(runs, "session-01", 1).exists()


def test_a_resolved_previous_client_does_not_block_a_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready_data_root(tmp_path, monkeypatch)
    runs = run_root(kin_root(tmp_path))
    overlay = session_overlay_path(runs, "session-00", 1)
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
    ready_data_root(tmp_path, monkeypatch)

    launch = start_session(
        root=tmp_path,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=stub_supervisor,
        probe=probe(Liveness.GONE),
    )

    runs = run_root(kin_root(tmp_path))
    marker = session_overlay_path(runs, "session-01", 1) / MARKER_NAME
    document = json.loads(marker.read_bytes())

    assert document["session_id"] == "session-01"
    assert document["identity"]["pid"] == 4242
    assert document["identity"]["argv_digest"] == launch.argv_digest


def test_the_cli_surfaces_an_unresolved_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The orphan refusal reaches the operator as a PROCESS exit code, not a crash."""

    ready_data_root(tmp_path, monkeypatch)
    monkeypatch.setattr("minekin_core.bootstrap.build_launch_plan", fake_plan)
    overlay = session_overlay_path(run_root(tmp_path), "session-00", 1)
    overlay.mkdir(parents=True)
    write_marker(overlay, identity=identity(), session_id="session-00", generation=1)
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")

    code = main(["session", "start", "--profile", str(PROFILE)])

    assert code == int(ExitCode.PROCESS)
    assert MARKER_NAME in capsys.readouterr().err


# --- proving that a live pid is the client we recorded -------------------------


def test_the_recorded_digest_is_exactly_what_proc_reports() -> None:
    """The round trip the whole proof rests on: our NUL join is /proc's format."""

    argv = ("/usr/lib/jvm/temurin-21/bin/java", "-cp", "a.jar", "--username", "Kin")
    recorded = argument_digest(argv)

    proof = prove_process_identity(
        4242, recorded, read_cmdline=lambda pid: b"\0".join(a.encode() for a in argv) + b"\0"
    )

    assert proof is IdentityProof.PROVEN


def test_a_reused_pid_is_not_mistaken_for_ours() -> None:
    proof = prove_process_identity(
        4242,
        argument_digest(("/usr/bin/java", "-jar", "ours.jar")),
        read_cmdline=lambda pid: b"/usr/bin/something-else\0--totally\0",
    )

    assert proof is IdentityProof.NOT_OURS


def test_an_unreadable_command_line_is_not_a_verdict() -> None:
    """`None` means the platform could not be asked, which is not the same as no."""

    assert prove_process_identity(4242, "a" * 64, read_cmdline=lambda pid: None) is (
        IdentityProof.UNVERIFIABLE
    )


def test_an_empty_command_line_is_not_ours() -> None:
    assert prove_process_identity(4242, "a" * 64, read_cmdline=lambda pid: b"\0") is (
        IdentityProof.NOT_OURS
    )


def test_the_real_reader_admits_this_platform_cannot_be_asked() -> None:
    import os

    if os.name == "posix":
        pytest.skip("this platform exposes the command line")
    assert default_cmdline(4242) is None
    assert prove_process_identity(4242, "a" * 64) is IdentityProof.UNVERIFIABLE


# --- stopping -----------------------------------------------------------------


def reads_our_command_line(_pid: int) -> bytes | None:
    return b"java" + bytes([0]) + b"-jar" + bytes([0]) + b"ours.jar" + bytes([0])


def reads_a_foreign_command_line(_pid: int) -> bytes | None:
    return b"someone-else" + bytes([0])


def reads_nothing(_pid: int) -> bytes | None:
    return None


class Recorder:
    """Stands in for `terminate`, so a test never signals a real process."""

    def __init__(self) -> None:
        self.pids: list[int] = []

    def __call__(self, pid: int) -> None:
        self.pids.append(pid)


def stop(
    tmp_path: Path, *, proof: IdentityProof, answered: Liveness = Liveness.ALIVE
) -> tuple[StopOutcome, Recorder]:
    terminate = Recorder()
    digest = argument_digest(("java", "-jar", "ours.jar"))
    marked(tmp_path, pid=4242, argv_digest=digest)
    readers: dict[IdentityProof, Callable[[int], bytes | None]] = {
        IdentityProof.PROVEN: reads_our_command_line,
        IdentityProof.NOT_OURS: reads_a_foreign_command_line,
        IdentityProof.UNVERIFIABLE: reads_nothing,
    }
    outcome = stop_recorded_clients(
        run_root(kin_root(tmp_path)),
        probe=probe(answered),
        read_cmdline=readers[proof],
        terminate=terminate,
    )
    return outcome, terminate


def test_a_proven_client_is_asked_to_stop(tmp_path: Path) -> None:
    outcome, terminate = stop(tmp_path, proof=IdentityProof.PROVEN)

    assert outcome.terminated == (4242,)
    assert terminate.pids == [4242]
    assert outcome.complete


def test_a_reused_pid_is_left_alone(tmp_path: Path) -> None:
    """Signalling it would kill an unrelated process; the operator is told instead."""

    outcome, terminate = stop(tmp_path, proof=IdentityProof.NOT_OURS)

    assert terminate.pids == []
    assert outcome.left_alone == (4242,)
    assert outcome.terminated == ()
    assert outcome.complete


def test_an_unverifiable_client_is_not_stopped_and_not_called_done(tmp_path: Path) -> None:
    outcome, terminate = stop(tmp_path, proof=IdentityProof.UNVERIFIABLE)

    assert terminate.pids == []
    assert outcome.unresolved == (4242,)
    assert not outcome.complete


def test_a_finished_client_needs_no_stopping(tmp_path: Path) -> None:
    outcome, terminate = stop(tmp_path, proof=IdentityProof.PROVEN, answered=Liveness.GONE)

    assert terminate.pids == []
    assert outcome.as_document() == {"terminated": [], "left_alone": [], "unresolved": []}
    assert outcome.complete


def test_stopping_a_kin_with_nothing_recorded_succeeds(tmp_path: Path) -> None:
    kin_root(tmp_path)
    terminate = Recorder()

    outcome = stop_recorded_clients(run_root(kin_root(tmp_path)), terminate=terminate)

    assert outcome.complete
    assert terminate.pids == []


def test_the_stop_document_is_evidence_ready(tmp_path: Path) -> None:
    outcome, _ = stop(tmp_path, proof=IdentityProof.PROVEN)

    assert outcome.as_document() == {
        "terminated": [4242],
        "left_alone": [],
        "unresolved": [],
    }


def test_the_cli_reports_a_kin_with_nothing_to_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stopping is idempotent, so an idle Kin is success rather than an error."""

    kin_root(tmp_path)
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    stdout = io.StringIO()

    code = run(["session", "stop"], stdout=stdout, stderr=io.StringIO())

    assert code == int(ExitCode.OK)
    assert json.loads(stdout.getvalue())["status"] == "stopped"


def test_the_cli_reports_a_client_it_could_not_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not being able to prove identity is not success; it is a PROCESS failure."""

    marked(tmp_path)
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    stdout = io.StringIO()

    code = run(["session", "stop"], stdout=stdout, stderr=io.StringIO())

    assert code == int(ExitCode.PROCESS)
    assert json.loads(stdout.getvalue())["unresolved"] == [4242]
