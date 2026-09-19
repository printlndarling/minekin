from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.orphans import Liveness, write_marker
from minekin_core.adapters.launcher.process import argument_digest
from minekin_core.adapters.launcher.supervisor import ProcessIdentity
from minekin_core.adapters.sqlite.connection import connect_writer
from minekin_core.adapters.sqlite.session_log import SessionEventLog
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.application.ports.clock import FakeClock
from minekin_core.bootstrap import main, run
from minekin_core.cli.init import initialise_identity
from minekin_core.cli.session import database_for, session_overlay_path
from minekin_core.cli.status import ObservedState, observe_state, read_status
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError
from minekin_core.domain.ids import KinId

KIN_ID = KinId("kin-01")


def probe(answer: Liveness) -> Callable[[int], Liveness]:
    def answer_with(_pid: int) -> Liveness:
        return answer

    return answer_with


#: What the recorded marker hashed, and readers standing in for `/proc`, so a
#: test decides identity without reading the host's real command lines.
OURS_ARGV = ("java", "-jar", "ours.jar")
OURS_DIGEST = argument_digest(OURS_ARGV)


def reads_ours(_pid: int) -> bytes | None:
    return b"\0".join(argument.encode() for argument in OURS_ARGV) + b"\0"


def reads_foreign(_pid: int) -> bytes | None:
    return b"/usr/bin/something-else\0--totally\0"


def reads_nothing(_pid: int) -> bytes | None:
    return None


def kin_root(tmp_path: Path) -> Path:
    """A Kin's data root, created once however many times a test asks for it."""

    if not (tmp_path / "kin" / "kin-01" / "kin.sqlite3").exists():
        initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())
    return tmp_path


def run_root(tmp_path: Path) -> Path:
    return tmp_path / "kin" / "kin-01" / "run"


def record_client(tmp_path: Path, *, session_id: str = "session-01", pid: int = 4242) -> Path:
    overlay = session_overlay_path(run_root(tmp_path), session_id, 1)
    overlay.mkdir(parents=True)
    return write_marker(
        overlay,
        identity=ProcessIdentity(
            pid=pid, started_at="2026-01-01T00:00:00Z", argv_digest=OURS_DIGEST
        ),
        session_id=session_id,
        generation=1,
    )


def test_a_kin_with_no_recorded_client_is_idle(tmp_path: Path) -> None:
    kin_root(tmp_path)

    report = read_status(tmp_path)

    assert report.state is ObservedState.IDLE
    assert report.clients == ()
    assert report.kin_id == "kin-01"


def test_a_live_client_is_running(tmp_path: Path) -> None:
    kin_root(tmp_path)
    record_client(tmp_path)

    report = read_status(tmp_path, probe=probe(Liveness.ALIVE), cmdline=reads_ours)

    assert report.state is ObservedState.RUNNING
    assert report.clients[0].pid == 4242
    assert report.clients[0].liveness is Liveness.ALIVE


def test_a_client_the_host_cannot_ask_about_is_unresolved(tmp_path: Path) -> None:
    """Consistent with `start`, which refuses in exactly this case."""

    kin_root(tmp_path)
    record_client(tmp_path)

    report = read_status(tmp_path, probe=probe(Liveness.UNKNOWN))

    assert report.state is ObservedState.UNRESOLVED


def test_a_finished_client_leaves_the_kin_idle(tmp_path: Path) -> None:
    kin_root(tmp_path)
    record_client(tmp_path)

    assert read_status(tmp_path, probe=probe(Liveness.GONE)).state is ObservedState.IDLE


def test_a_live_pid_with_a_foreign_command_line_reads_idle(tmp_path: Path) -> None:
    """The number was reused, so no client of ours is running and none is stuck."""

    kin_root(tmp_path)
    record_client(tmp_path)

    report = read_status(tmp_path, probe=probe(Liveness.ALIVE), cmdline=reads_foreign)

    assert report.state is ObservedState.IDLE
    assert report.clients[0].liveness is Liveness.GONE


def test_a_live_pid_whose_command_line_cannot_be_read_is_unresolved(tmp_path: Path) -> None:
    """Consistent with `start`, which refuses in exactly this case."""

    kin_root(tmp_path)
    record_client(tmp_path)

    report = read_status(tmp_path, probe=probe(Liveness.ALIVE), cmdline=reads_nothing)

    assert report.state is ObservedState.UNRESOLVED
    assert report.clients[0].liveness is Liveness.UNKNOWN


def test_a_live_client_outranks_an_unanswerable_one(tmp_path: Path) -> None:
    kin_root(tmp_path)
    record_client(tmp_path, session_id="session-01", pid=1)
    record_client(tmp_path, session_id="session-02", pid=2)

    def by_pid(pid: int) -> Liveness:
        return Liveness.ALIVE if pid == 1 else Liveness.UNKNOWN

    report = read_status(tmp_path, probe=by_pid, cmdline=reads_ours)

    assert report.state is ObservedState.RUNNING
    assert [client.session_id for client in report.clients] == ["session-01", "session-02"]


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        ((), ObservedState.IDLE),
        ((Liveness.GONE,), ObservedState.IDLE),
        ((Liveness.GONE, Liveness.GONE), ObservedState.IDLE),
        ((Liveness.ALIVE,), ObservedState.RUNNING),
        ((Liveness.UNKNOWN,), ObservedState.UNRESOLVED),
        ((Liveness.UNKNOWN, Liveness.GONE), ObservedState.UNRESOLVED),
        ((Liveness.UNKNOWN, Liveness.ALIVE), ObservedState.RUNNING),
    ],
)
def test_the_observed_state_follows_the_liveness_answers(
    answers: tuple[Liveness, ...], expected: ObservedState
) -> None:
    from minekin_core.cli.status import ClientSummary

    clients = tuple(
        ClientSummary(
            session_id=f"session-{index}",
            generation=1,
            overlay=f"/run/session-{index}/generation-1",
            pid=index + 1,
            liveness=answer,
        )
        for index, answer in enumerate(answers)
    )

    assert observe_state(clients) is expected


def test_the_ledger_summary_reports_what_was_recorded(tmp_path: Path) -> None:
    kin_root(tmp_path)
    SessionEventLog(database_for(tmp_path, KIN_ID), clock=SystemClock()).record_process_started(
        kin_id="kin-01",
        run_id="run-01",
        session_id="session-01",
        generation=1,
        client_instance_id="client-01",
        argv_digest="a" * 64,
    )

    report = read_status(tmp_path)

    assert report.ledger.events_recorded == 1
    assert report.ledger.last_event_type == "SessionProcessStarted"
    assert report.ledger.last_observed_at_utc is not None


def test_an_empty_ledger_reports_nothing_rather_than_zeroes(tmp_path: Path) -> None:
    kin_root(tmp_path)

    ledger = read_status(tmp_path).ledger

    assert ledger.events_recorded == 0
    assert ledger.last_event_type is None
    assert ledger.last_observed_at_utc is None


def test_reading_status_creates_no_kin(tmp_path: Path) -> None:
    """The command reports; only `init` creates."""

    with pytest.raises(MinekinError, match="run `minekin init` first"):
        read_status(tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_reading_status_reports_a_missing_database_rather_than_creating_one(
    tmp_path: Path,
) -> None:
    (tmp_path / "kin" / "kin-01").mkdir(parents=True)

    with pytest.raises(MinekinError, match="run `minekin init` first") as raised:
        read_status(tmp_path)

    assert raised.value.category is ErrorCategory.STORAGE
    assert not database_for(tmp_path, KIN_ID).exists()


def test_the_report_is_stable_across_reads(tmp_path: Path) -> None:
    """Asking twice cannot change the answer, which is what read-only means here."""

    kin_root(tmp_path)
    record_client(tmp_path)

    first = read_status(tmp_path, probe=probe(Liveness.GONE)).as_dict()
    second = read_status(tmp_path, probe=probe(Liveness.GONE)).as_dict()

    assert first == second


def test_the_report_document_is_evidence_ready(tmp_path: Path) -> None:
    kin_root(tmp_path)
    record_client(tmp_path, session_id="session-07", pid=99)

    document = read_status(tmp_path, probe=probe(Liveness.GONE)).as_dict()

    assert document == {
        "schema_version": 1,
        "command": "session status",
        "status": "ok",
        "kin_id": "kin-01",
        "state": "idle",
        "clients": [
            {
                "session_id": "session-07",
                "generation": 1,
                "overlay": str(session_overlay_path(run_root(tmp_path), "session-07", 1)),
                "pid": 99,
                "liveness": "GONE",
            }
        ],
        "ledger": {
            "events_recorded": 0,
            "last_event_type": None,
            "last_observed_at_utc": None,
        },
    }


def test_the_cli_reports_the_current_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kin_root(tmp_path)
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    stdout, stderr = io.StringIO(), io.StringIO()

    code = run(["session", "status"], stdout=stdout, stderr=stderr)

    assert code == int(ExitCode.OK)
    assert json.loads(stdout.getvalue())["state"] == "idle"


def test_the_cli_refuses_a_status_without_a_kin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))

    code = main(["session", "status"])

    assert code == int(ExitCode.CONFIG)
    assert "init" in capsys.readouterr().err


def test_the_cli_leaves_no_writer_thread_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A status read must not open the write connection at all."""

    import threading

    kin_root(tmp_path)
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))

    run(["session", "status"], stdout=io.StringIO(), stderr=io.StringIO())

    assert [t for t in threading.enumerate() if "sqlite-writer" in t.name] == []


def test_a_status_read_does_not_touch_the_ledger(tmp_path: Path) -> None:
    kin_root(tmp_path)
    connection = connect_writer(database_for(tmp_path, KIN_ID))
    try:
        before = int(connection.execute("SELECT count(*) FROM event").fetchone()[0])
    finally:
        connection.close()

    read_status(tmp_path)

    connection = connect_writer(database_for(tmp_path, KIN_ID))
    try:
        after = int(connection.execute("SELECT count(*) FROM event").fetchone()[0])
    finally:
        connection.close()
    assert before == after == 0
