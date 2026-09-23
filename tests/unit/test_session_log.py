from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_log import (
    AUTH_POLICY_FROZEN,
    PROCESS_FAILED,
    PROCESS_STARTED,
    SessionEventLog,
)
from minekin_core.adapters.sqlite.writer import SQLiteWriter
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.init import initialise_identity
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError, Retryability
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.ids import KinId

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

KIN_ID = KinId("kin-01")


def database(tmp_path: Path) -> Path:
    """The Kin's ledger, created once however many times a test asks for it."""

    path = tmp_path / "kin" / "kin-01" / "kin.sqlite3"
    if not path.exists():
        initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())
    return path


def log(tmp_path: Path) -> SessionEventLog:
    return SessionEventLog(database(tmp_path), clock=FakeClock())


def stored(database_path: Path) -> list[dict[str, object]]:
    import sqlite3

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT event_type, kin_id, run_id, sequence, source, trust_class, "
            "payload_json, payload_hash, session_id, generation "
            "FROM event ORDER BY position"
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def test_a_started_event_is_recorded_with_its_hash(tmp_path: Path) -> None:
    path = database(tmp_path)

    envelope = log(tmp_path).record_process_started(
        kin_id="kin-01",
        run_id="run-01",
        session_id="session-01",
        generation=1,
        client_instance_id="client-01",
        argv_digest="a" * 64,
    )

    rows = stored(path)
    assert len(rows) == 1
    assert rows[0]["event_type"] == PROCESS_STARTED
    assert rows[0]["source"] == EventSource.LAUNCHER.value
    assert rows[0]["trust_class"] == TrustClass.LAUNCHER.value
    assert rows[0]["session_id"] == "session-01"
    # `sequence` and `generation` are TEXT: uint64 does not fit SQLite's signed
    # INTEGER, so the ledger stores the decimal form and checks it with a CHECK.
    assert rows[0]["generation"] == "1"
    assert rows[0]["sequence"] == "1"
    # The recorded hash must be the canonical-JSON digest of the payload.
    payload = json.loads(str(rows[0]["payload_json"]))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert rows[0]["payload_hash"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert envelope.event_type == PROCESS_STARTED


def test_auth_policy_cannot_be_frozen_twice_or_after_process_start(tmp_path: Path) -> None:
    ledger = log(tmp_path)

    def freeze(run_id: str) -> None:
        asyncio.run(
            ledger.record_session_event(
                event_type=AUTH_POLICY_FROZEN,
                kin_id="kin-01",
                run_id=run_id,
                session_id="session-01",
                generation=1,
                payload={"auth_mode": "offline", "online_adapter_enabled": False},
                source=EventSource.CORE,
                trust_class=TrustClass.CORE,
            )
        )

    freeze("run-01")
    with pytest.raises(ValueError, match="frozen once"):
        freeze("run-01")

    ledger.record_process_started(
        kin_id="kin-01",
        run_id="run-02",
        session_id="session-01",
        generation=1,
        client_instance_id="client-01",
        argv_digest="a" * 64,
    )
    with pytest.raises(ValueError, match="before this run starts"):
        freeze("run-02")
    assert [row["event_type"] for row in stored(database(tmp_path))] == [
        AUTH_POLICY_FROZEN,
        PROCESS_STARTED,
    ]


def test_the_sequence_continues_within_one_run(tmp_path: Path) -> None:
    ledger = log(tmp_path)

    ledger.record_process_started(
        kin_id="kin-01",
        run_id="run-01",
        session_id="session-01",
        generation=1,
        client_instance_id="client-01",
        argv_digest="a" * 64,
    )
    second = ledger.record_process_started(
        kin_id="kin-01",
        run_id="run-01",
        session_id="session-02",
        generation=2,
        client_instance_id="client-02",
        argv_digest="b" * 64,
    )

    assert [row["sequence"] for row in stored(database(tmp_path))] == ["1", "2"]
    assert second.sequence == 2


def test_a_different_run_starts_its_own_sequence(tmp_path: Path) -> None:
    ledger = log(tmp_path)
    ledger.record_process_started(
        kin_id="kin-01",
        run_id="run-01",
        session_id="session-01",
        generation=1,
        client_instance_id="client-01",
        argv_digest="a" * 64,
    )

    other = ledger.record_process_started(
        kin_id="kin-01",
        run_id="run-02",
        session_id="session-01",
        generation=1,
        client_instance_id="client-02",
        argv_digest="a" * 64,
    )

    assert other.sequence == 1


def test_a_failed_event_records_the_classification_but_not_the_raw_text(tmp_path: Path) -> None:
    """The ledger takes the already-redacted message, never the exception body."""

    error = MinekinError(
        "launcher.process",
        "supervise",
        ErrorCategory.PROCESS,
        Retryability.OPERATOR_ACTION,
        "the client process could not be started: OSError",
    )

    log(tmp_path).record_process_failed(
        kin_id="kin-01",
        run_id="run-01",
        session_id="session-01",
        generation=1,
        error=error,
    )

    row = stored(database(tmp_path))[0]
    payload = json.loads(str(row["payload_json"]))
    assert row["event_type"] == PROCESS_FAILED
    assert payload["category"] == "PROCESS"
    assert payload["retryability"] == "OPERATOR_ACTION"
    assert payload["reason"] == error.safe_message
    assert "Traceback" not in str(row["payload_json"])


def test_the_writer_thread_is_released_after_each_record(tmp_path: Path) -> None:
    """A leaked writer thread would keep the process alive after the CLI returns."""

    ledger = log(tmp_path)
    ledger.record_process_started(
        kin_id="kin-01",
        run_id="run-01",
        session_id="session-01",
        generation=1,
        client_instance_id="client-01",
        argv_digest="a" * 64,
    )

    import threading

    assert [thread for thread in threading.enumerate() if "sqlite-writer" in thread.name] == []


def test_the_ledger_rejects_an_oracle_trusted_event() -> None:
    """The product ledger must not accept a test-oracle event, by construction."""

    from minekin_core.application.ports.event_store import EventEnvelope

    with pytest.raises(ValueError, match="oracle events cannot enter"):
        EventEnvelope(
            event_id="event-01",
            event_type="OracleSaidSo",
            schema_version=1,
            kin_id="kin-01",
            run_id="run-01",
            sequence=1,
            correlation_id="corr-01",
            monotonic_ns=0,
            observed_at_utc="2026-01-01T00:00:00Z",
            source=EventSource.SERVER_ORACLE_TEST_ONLY,
            trust_class=TrustClass.CORE,
            payload={},
            payload_hash="a" * 64,
        )


def test_the_reader_connection_sees_the_recorded_event(tmp_path: Path) -> None:
    """The event is committed, not just written to a connection that closes."""

    path = database(tmp_path)
    log(tmp_path).record_process_started(
        kin_id="kin-01",
        run_id="run-01",
        session_id="session-01",
        generation=1,
        client_instance_id="client-01",
        argv_digest="a" * 64,
    )

    connection = connect_reader(path)
    try:
        count = connection.execute("SELECT count(*) FROM event").fetchone()[0]
    finally:
        connection.close()

    assert count == 1


def test_the_exit_code_for_a_failed_launch_is_the_process_category(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from minekin_core.bootstrap import main

    database(tmp_path)
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv("MINEKIN_JAVA", str(Path("relative/java").absolute()))
    monkeypatch.chdir(tmp_path)

    code = main(["session", "start", "--profile", "missing.json"])

    assert code != int(ExitCode.OK)
    assert capsys.readouterr().err


def test_writers_are_closed_so_no_thread_outlives_the_call(tmp_path: Path) -> None:
    """Belt and braces for the writer lifecycle: start, use, close."""

    async def round_trip() -> tuple[object, ...]:
        writer = SQLiteWriter(database(tmp_path))
        await writer.start()
        try:
            from minekin_core.adapters.sqlite.event_store import SQLiteEventStore

            return await SQLiteEventStore(database(tmp_path), writer).read_all()
        finally:
            await writer.aclose()

    assert asyncio.run(round_trip()) == ()


def _writer_threads() -> list[str]:
    import threading

    return [thread.name for thread in threading.enumerate() if "sqlite-writer" in thread.name]


def test_a_ledger_that_cannot_open_does_not_leave_its_writer_thread_behind(
    tmp_path: Path,
) -> None:
    """The thread is started by the constructor, so a failed `start()` still owns one.

    Closing it has to sit in the same `try` that starts it. A non-daemon thread
    parked on an empty queue is invisible until the interpreter tries to exit, at
    which point it hangs — which is exactly what happened once a join report
    began being written from a task the session cancels on its way out, and it is
    what this pins.
    """

    unusable = tmp_path / "not-a-database.sqlite3"
    unusable.write_bytes(b"this is not a SQLite file\n")
    ledger = SessionEventLog(unusable, clock=FakeClock())
    before = _writer_threads()

    with pytest.raises(sqlite3.DatabaseError):
        asyncio.run(
            ledger.record_session_event(
                event_type=PROCESS_STARTED,
                kin_id="kin-01",
                run_id="run-01",
                session_id="session-01",
                generation=1,
                payload={},
                source=EventSource.CORE,
                trust_class=TrustClass.CORE,
            )
        )

    assert _writer_threads() == before
