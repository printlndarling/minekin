"""Thin Bridge transport port and queue-backed fake."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Bridge(Protocol):
    async def send_control(self, message: Any) -> None: ...
    async def receive_event(self) -> Any: ...
    async def release_all(self, request: Any) -> None: ...
    async def close(self) -> None: ...


class FakeBridge:
    def __init__(self) -> None:
        self.controls: list[Any] = []
        self.releases: list[Any] = []
        self.events: asyncio.Queue[Any] = asyncio.Queue()
        self.closed = False

    async def send_control(self, message: Any) -> None:
        self.controls.append(message)

    async def receive_event(self) -> Any:
        return await self.events.get()

    async def emit(self, event: Any) -> None:
        await self.events.put(event)

    async def release_all(self, request: Any) -> None:
        self.releases.append(request)

    async def close(self) -> None:
        self.closed = True
