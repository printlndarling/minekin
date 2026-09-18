"""Append-only event store and transactional-outbox contracts.

The small ``append``/``read_all`` surface remains useful to application services
which do not cause an external side effect.  Commands which *do* cause one use
``append_with_outbox`` so the fact that a command was accepted and the work to be
performed cannot be separated by a process crash.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from minekin_core.domain.events import EventSource, TrustClass

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Persistable form of the P0 event envelope.

    ``payload_hash`` is the lowercase SHA-256 of canonical UTF-8 JSON.  It is
    checked by adapters before a write and after a read.
    """

    event_id: str
    event_type: str
    schema_version: int
    kin_id: str
    run_id: str
    sequence: int
    correlation_id: str
    monotonic_ns: int
    observed_at_utc: str
    source: EventSource
    trust_class: TrustClass
    payload: JsonValue
    payload_hash: str
    client_instance_id: str | None = None
    session_id: str | None = None
    generation: int | None = None
    world_context_id: str | None = None
    causation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.source.allowed_in_product_store:
            raise ValueError("test oracle events cannot enter the product event store")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if self.sequence < 1:
            raise ValueError("sequence must be positive")


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """An event and its monotonically increasing database position."""

    position: int
    envelope: EventEnvelope


@dataclass(frozen=True, slots=True)
class OutboxItem:
    """A committed external-side-effect request."""

    outbox_id: str
    effect_type: str
    idempotency_key: str
    payload: JsonValue
    created_at_utc: str
    status: str = "pending"
    attempts: int = 0
    completed_at_utc: str | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class Projection:
    """Rebuildable derived state, covered through an event position."""

    name: str
    key: str
    last_event_position: int
    value: JsonValue
    updated_at_utc: str


@runtime_checkable
class EventStore(Protocol):
    async def append(self, events: Iterable[EventEnvelope]) -> None: ...
    async def read_all(self) -> tuple[EventEnvelope, ...]: ...

    async def append_with_outbox(
        self, events: Iterable[EventEnvelope], item: OutboxItem
    ) -> None: ...

    async def pending_outbox(self, *, limit: int = 100) -> tuple[OutboxItem, ...]: ...

    async def mark_outbox_complete(self, outbox_id: str, completed_at_utc: str) -> None: ...

    async def put_projection(self, projection: Projection) -> None: ...

    async def get_projection(self, name: str, key: str) -> Projection | None: ...


class FakeEventStore:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []
        self.outbox: dict[str, OutboxItem] = {}
        self.projections: dict[tuple[str, str], Projection] = {}

    async def append(self, events: Iterable[EventEnvelope]) -> None:
        self.events.extend(events)

    async def read_all(self) -> tuple[EventEnvelope, ...]:
        return tuple(self.events)

    async def append_with_outbox(self, events: Iterable[EventEnvelope], item: OutboxItem) -> None:
        if item.outbox_id in self.outbox:
            raise ValueError(f"duplicate outbox_id: {item.outbox_id}")
        if any(
            existing.idempotency_key == item.idempotency_key for existing in self.outbox.values()
        ):
            raise ValueError(f"duplicate idempotency_key: {item.idempotency_key}")
        materialized = tuple(events)
        event_ids = {event.event_id for event in self.events}
        if any(event.event_id in event_ids for event in materialized):
            raise ValueError("duplicate event_id")
        self.events.extend(materialized)
        self.outbox[item.outbox_id] = item

    async def pending_outbox(self, *, limit: int = 100) -> tuple[OutboxItem, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        return tuple(item for item in self.outbox.values() if item.status == "pending")[:limit]

    async def mark_outbox_complete(self, outbox_id: str, completed_at_utc: str) -> None:
        item = self.outbox.get(outbox_id)
        if item is None:
            raise KeyError(outbox_id)
        if item.status == "completed":
            return
        self.outbox[outbox_id] = OutboxItem(
            outbox_id=item.outbox_id,
            effect_type=item.effect_type,
            idempotency_key=item.idempotency_key,
            payload=item.payload,
            created_at_utc=item.created_at_utc,
            status="completed",
            attempts=item.attempts,
            completed_at_utc=completed_at_utc,
            last_error=item.last_error,
        )

    async def put_projection(self, projection: Projection) -> None:
        current = self.projections.get((projection.name, projection.key))
        if current is not None and projection.last_event_position < current.last_event_position:
            raise ValueError("projection event position cannot move backwards")
        self.projections[(projection.name, projection.key)] = projection

    async def get_projection(self, name: str, key: str) -> Projection | None:
        return self.projections.get((name, key))
