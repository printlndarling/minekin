"""Managed-client launcher port and recording fake."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Launcher(Protocol):
    async def prepare(self, request: Any) -> Any: ...
    async def start(self, request: Any) -> Any: ...
    async def stop(self, request: Any) -> Any: ...


class FakeLauncher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.results: dict[str, Any] = {}

    async def _call(self, operation: str, request: Any) -> Any:
        self.calls.append((operation, request))
        result = self.results.get(operation)
        if isinstance(result, BaseException):
            raise result
        return result

    async def prepare(self, request: Any) -> Any:
        return await self._call("prepare", request)

    async def start(self, request: Any) -> Any:
        return await self._call("start", request)

    async def stop(self, request: Any) -> Any:
        return await self._call("stop", request)
