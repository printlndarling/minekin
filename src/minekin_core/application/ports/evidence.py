"""Evidence sink port and in-memory fake."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EvidenceSink(Protocol):
    async def record(self, item: Any) -> None: ...
    async def flush(self) -> Any: ...


class FakeEvidenceSink:
    def __init__(self) -> None:
        self.items: list[Any] = []
        self.flush_count = 0

    async def record(self, item: Any) -> None:
        self.items.append(item)

    async def flush(self) -> tuple[Any, ...]:
        self.flush_count += 1
        return tuple(self.items)
