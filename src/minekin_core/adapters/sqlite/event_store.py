"""SQLite implementation of the append-only event/outbox port."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from minekin_core.application.ports.event_store import (
    EventEnvelope,
    JsonValue,
    OutboxItem,
    Projection,
)
from minekin_core.domain.events import EventSource, TrustClass

from .connection import connect_reader
from .writer import SQLiteWriter


def canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def payload_digest(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class SQLiteEventStore:
    def __init__(self, path: str | Path, writer: SQLiteWriter) -> None:
        self._path = Path(path)
        self._writer = writer

    async def append(self, events: Iterable[EventEnvelope]) -> None:
        materialized = tuple(events)
        await self._writer.execute(lambda connection: _insert_events(connection, materialized))

    async def append_with_outbox(self, events: Iterable[EventEnvelope], item: OutboxItem) -> None:
        materialized = tuple(events)

        def operation(connection: sqlite3.Connection) -> None:
            _insert_events(connection, materialized)
            connection.execute(
                """
                INSERT INTO outbox(
                    outbox_id, effect_type, idempotency_key, payload_json, status,
                    attempts, created_at_utc, completed_at_utc, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.outbox_id,
                    item.effect_type,
                    item.idempotency_key,
                    canonical_json(item.payload),
                    item.status,
                    item.attempts,
                    item.created_at_utc,
                    item.completed_at_utc,
                    item.last_error,
                ),
            )

        await self._writer.execute(operation)

    async def read_all(self) -> tuple[EventEnvelope, ...]:
        return await asyncio.to_thread(self._read_all_sync)

    def _read_all_sync(self) -> tuple[EventEnvelope, ...]:
        connection = connect_reader(self._path)
        try:
            rows = connection.execute("SELECT * FROM event ORDER BY position").fetchall()
            return tuple(_event_from_row(row) for row in rows)
        finally:
            connection.close()

    async def pending_outbox(self, *, limit: int = 100) -> tuple[OutboxItem, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        return await asyncio.to_thread(self._pending_outbox_sync, limit)

    def _pending_outbox_sync(self, limit: int) -> tuple[OutboxItem, ...]:
        connection = connect_reader(self._path)
        try:
            rows = connection.execute(
                "SELECT * FROM outbox WHERE status = 'pending' "
                "ORDER BY created_at_utc, outbox_id LIMIT ?",
                (limit,),
            ).fetchall()
            return tuple(_outbox_from_row(row) for row in rows)
        finally:
            connection.close()

    async def mark_outbox_complete(self, outbox_id: str, completed_at_utc: str) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            row = connection.execute(
                "SELECT status FROM outbox WHERE outbox_id = ?", (outbox_id,)
            ).fetchone()
            if row is None:
                raise KeyError(outbox_id)
            if str(row[0]) == "completed":
                return
            connection.execute(
                "UPDATE outbox SET status = 'completed', completed_at_utc = ? WHERE outbox_id = ?",
                (completed_at_utc, outbox_id),
            )

        await self._writer.execute(operation)

    async def put_projection(self, projection: Projection) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            row = connection.execute(
                "SELECT last_event_position FROM projection "
                "WHERE projection_name = ? AND projection_key = ?",
                (projection.name, projection.key),
            ).fetchone()
            if row is not None and int(row[0]) > projection.last_event_position:
                raise ValueError("projection event position cannot move backwards")
            connection.execute(
                """
                INSERT INTO projection(
                    projection_name, projection_key, last_event_position,
                    value_json, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(projection_name, projection_key) DO UPDATE SET
                    last_event_position = excluded.last_event_position,
                    value_json = excluded.value_json,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    projection.name,
                    projection.key,
                    projection.last_event_position,
                    canonical_json(projection.value),
                    projection.updated_at_utc,
                ),
            )

        await self._writer.execute(operation)

    async def get_projection(self, name: str, key: str) -> Projection | None:
        return await asyncio.to_thread(self._get_projection_sync, name, key)

    def _get_projection_sync(self, name: str, key: str) -> Projection | None:
        connection = connect_reader(self._path)
        try:
            row = connection.execute(
                "SELECT * FROM projection WHERE projection_name = ? AND projection_key = ?",
                (name, key),
            ).fetchone()
            if row is None:
                return None
            return Projection(
                name=str(row["projection_name"]),
                key=str(row["projection_key"]),
                last_event_position=int(row["last_event_position"]),
                value=cast(JsonValue, json.loads(str(row["value_json"]))),
                updated_at_utc=str(row["updated_at_utc"]),
            )
        finally:
            connection.close()


def _insert_events(connection: sqlite3.Connection, events: tuple[EventEnvelope, ...]) -> None:
    for event in events:
        actual_hash = payload_digest(event.payload)
        if event.payload_hash != actual_hash:
            raise ValueError(f"payload hash mismatch for event {event.event_id}")
        connection.execute(
            """
            INSERT INTO event(
                event_id, event_type, schema_version, kin_id, run_id,
                client_instance_id, session_id, generation, world_context_id,
                sequence, correlation_id, causation_id, monotonic_ns,
                observed_at_utc, source, trust_class, payload_json, payload_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.schema_version,
                event.kin_id,
                event.run_id,
                event.client_instance_id,
                event.session_id,
                str(event.generation) if event.generation is not None else None,
                event.world_context_id,
                str(event.sequence),
                event.correlation_id,
                event.causation_id,
                event.monotonic_ns,
                event.observed_at_utc,
                event.source.value,
                event.trust_class.value,
                canonical_json(event.payload),
                event.payload_hash,
            ),
        )


def _event_from_row(row: sqlite3.Row) -> EventEnvelope:
    payload = cast(JsonValue, json.loads(str(row["payload_json"])))
    stored_hash = str(row["payload_hash"])
    if payload_digest(payload) != stored_hash:
        raise ValueError(f"stored payload hash mismatch for event {row['event_id']}")
    return EventEnvelope(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        schema_version=int(row["schema_version"]),
        kin_id=str(row["kin_id"]),
        run_id=str(row["run_id"]),
        client_instance_id=_optional_text(row["client_instance_id"]),
        session_id=_optional_text(row["session_id"]),
        generation=int(row["generation"]) if row["generation"] is not None else None,
        world_context_id=_optional_text(row["world_context_id"]),
        sequence=int(row["sequence"]),
        correlation_id=str(row["correlation_id"]),
        causation_id=_optional_text(row["causation_id"]),
        monotonic_ns=int(row["monotonic_ns"]),
        observed_at_utc=str(row["observed_at_utc"]),
        source=EventSource(str(row["source"])),
        trust_class=TrustClass(str(row["trust_class"])),
        payload=payload,
        payload_hash=stored_hash,
    )


def _outbox_from_row(row: sqlite3.Row) -> OutboxItem:
    return OutboxItem(
        outbox_id=str(row["outbox_id"]),
        effect_type=str(row["effect_type"]),
        idempotency_key=str(row["idempotency_key"]),
        payload=cast(JsonValue, json.loads(str(row["payload_json"]))),
        status=str(row["status"]),
        attempts=int(row["attempts"]),
        created_at_utc=str(row["created_at_utc"]),
        completed_at_utc=_optional_text(row["completed_at_utc"]),
        last_error=_optional_text(row["last_error"]),
    )


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)
