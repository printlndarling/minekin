from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

from minekin_core.adapters.sqlite.connection import (
    SCHEMA_VERSION,
    connect_reader,
    supports_multi_connection_wal,
)
from minekin_core.adapters.sqlite.event_store import SQLiteEventStore, payload_digest
from minekin_core.adapters.sqlite.writer import SQLiteWriter, WriteDeadlineExceeded
from minekin_core.application.ports.event_store import (
    EventEnvelope,
    JsonValue,
    OutboxItem,
    Projection,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.events import EventSource, TrustClass


def _event(*, payload_hash: str | None = None) -> EventEnvelope:
    payload: JsonValue = {"state": "PREPARING"}
    return EventEnvelope(
        event_id="event-1",
        event_type="SessionPreparing",
        schema_version=1,
        kin_id="kin-1",
        run_id="run-1",
        sequence=1,
        correlation_id="corr-1",
        monotonic_ns=100,
        observed_at_utc="2026-09-18T00:00:00Z",
        source=EventSource.CORE,
        trust_class=TrustClass.CORE,
        payload=payload,
        payload_hash=payload_hash or payload_digest(payload),
        session_id="session-1",
        generation=1,
    )


def test_writer_owns_connection_on_a_dedicated_thread(tmp_path: Path) -> None:
    async def scenario() -> None:
        writer = SQLiteWriter(tmp_path / "core.sqlite3")
        await writer.start()
        try:
            writer_thread = await writer.execute(lambda _connection: threading.get_ident())
            assert writer_thread == writer.thread_ident
            assert writer_thread != threading.get_ident()
        finally:
            await writer.aclose()

    asyncio.run(scenario())


def test_schema_v1_event_outbox_and_projection_round_trip(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = tmp_path / "core.sqlite3"
        async with SQLiteWriter(database) as writer:
            store = SQLiteEventStore(database, writer)
            item = OutboxItem(
                outbox_id="outbox-1",
                effect_type="PREPARE_BUNDLE",
                idempotency_key="prepare-1",
                payload={"profile": "p0"},
                created_at_utc="2026-09-18T00:00:00Z",
            )
            await store.append_with_outbox([_event()], item)
            assert await store.read_all() == (_event(),)
            assert await store.pending_outbox() == (item,)

            projection = Projection(
                name="session",
                key="kin-1",
                last_event_position=1,
                value={"state": "PREPARING"},
                updated_at_utc="2026-09-18T00:00:01Z",
            )
            await store.put_projection(projection)
            assert await store.get_projection("session", "kin-1") == projection
            await store.mark_outbox_complete("outbox-1", "2026-09-18T00:00:02Z")
            assert await store.pending_outbox() == ()

        reader = connect_reader(database)
        try:
            assert reader.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert reader.execute("SELECT COUNT(*) FROM event").fetchone()[0] == 1
        finally:
            reader.close()

    asyncio.run(scenario())


def test_event_and_outbox_rollback_together_on_bad_payload_hash(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = tmp_path / "core.sqlite3"
        async with SQLiteWriter(database) as writer:
            store = SQLiteEventStore(database, writer)
            item = OutboxItem(
                outbox_id="outbox-1",
                effect_type="START_CLIENT",
                idempotency_key="start-1",
                payload={},
                created_at_utc="2026-09-18T00:00:00Z",
            )
            with pytest.raises(ValueError, match="payload hash mismatch"):
                await store.append_with_outbox([_event(payload_hash="0" * 64)], item)
            assert await store.read_all() == ()
            assert await store.pending_outbox() == ()

    asyncio.run(scenario())


def test_expired_write_is_rejected_before_execution(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with SQLiteWriter(tmp_path / "core.sqlite3") as writer:
            with pytest.raises(WriteDeadlineExceeded):
                await writer.execute(lambda _connection: None, deadline_ns=time.monotonic_ns() - 1)

    asyncio.run(scenario())


def test_oracle_source_is_rejected_before_persistence() -> None:
    with pytest.raises(ValueError, match="oracle"):
        replace(_event(), source=EventSource.SERVER_ORACLE_TEST_ONLY)


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ((3, 51, 3), True),
        ((3, 53, 1), True),
        ((3, 50, 7), True),
        ((3, 44, 6), True),
        ((3, 50, 6), False),
        ((3, 49, 9), False),
    ],
)
def test_wal_runtime_gate(version: tuple[int, int, int], expected: bool) -> None:
    assert supports_multi_connection_wal(version) is expected


def test_a_ledger_row_that_does_not_match_its_digest_names_the_event(tmp_path: Path) -> None:
    """The read-path counterpart of the write-path check, and it says which row.

    A stored row whose payload no longer hashes to its recorded digest is a
    storage fault. It used to surface as a bare ValueError, which the CLI
    redacts, so the event id — the one thing that makes it investigable — was
    thrown away with the message.
    """

    database = tmp_path / "core.sqlite3"

    async def write_a_row() -> None:
        async with SQLiteWriter(database) as writer:
            await SQLiteEventStore(database, writer).append([_event()])

    asyncio.run(write_a_row())

    corruption = sqlite3.connect(database)
    try:
        corruption.execute("UPDATE event SET payload_json = '{\"tampered\": true}'")
        corruption.commit()
    finally:
        corruption.close()

    async def read_it_back() -> object:
        async with SQLiteWriter(database) as writer:
            return await SQLiteEventStore(database, writer).read_all()

    with pytest.raises(MinekinError, match="payload hash mismatch") as raised:
        asyncio.run(read_it_back())

    assert raised.value.category is ErrorCategory.STORAGE
    assert "event-1" in raised.value.safe_message


def test_a_reader_refuses_a_file_that_is_not_a_ledger(tmp_path: Path) -> None:
    """Named here rather than discovered later as "no such table: kin_identity".

    That driver message is what the CLI redacts, so a foreign database used to
    arrive as "unexpected internal failure".
    """

    foreign = tmp_path / "someone-elses.sqlite3"
    creator = sqlite3.connect(foreign)
    creator.execute("CREATE TABLE their_notes (body TEXT)")
    creator.commit()
    creator.close()

    with pytest.raises(MinekinError, match="not a Minekin ledger") as raised:
        connect_reader(foreign)

    assert raised.value.category is ErrorCategory.STORAGE


def test_an_unmigrated_database_is_not_readable(tmp_path: Path) -> None:
    """Nothing here produces one, so reading it would be guessing.

    `connect_writer` migrates in the same call that opens it, so a file without
    the schema is what a rolled-back migration leaves behind.
    """

    half = tmp_path / "half-initialised.sqlite3"
    sqlite3.connect(half).close()

    with pytest.raises(MinekinError, match="migration did not complete"):
        connect_reader(half)


def test_a_reviewed_ledger_is_still_readable(tmp_path: Path) -> None:
    """The validation must not refuse the files it exists to protect."""

    database = tmp_path / "core.sqlite3"

    async def write_a_row() -> None:
        async with SQLiteWriter(database) as writer:
            await SQLiteEventStore(database, writer).append([_event()])

    asyncio.run(write_a_row())

    connection = connect_reader(database)
    try:
        assert connection.execute("SELECT count(*) FROM event ").fetchone()[0] == 1
    finally:
        connection.close()
