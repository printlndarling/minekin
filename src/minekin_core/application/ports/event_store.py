"""Append-only event store port and in-memory fake."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EventStore(Protocol):
    async def append(self, events: Iterable[Any]) -> None: ...
    async def read_all(self) -> tuple[Any, ...]: ...


class FakeEventStore:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def append(self, events: Iterable[Any]) -> None:
        self.events.extend(events)

    async def read_all(self) -> tuple[Any, ...]:
        return tuple(self.events)
