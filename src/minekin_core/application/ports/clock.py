"""Clock port and deterministic fake."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from minekin_core.domain.time import MonotonicInstant, UtcInstant


@runtime_checkable
class Clock(Protocol):
    def monotonic(self) -> MonotonicInstant: ...

    def utc_now(self) -> UtcInstant: ...


class FakeClock:
    def __init__(
        self,
        monotonic_ns: int = 0,
        utc: datetime = datetime(2000, 1, 1, tzinfo=UTC),
    ) -> None:
        self._monotonic = MonotonicInstant(monotonic_ns)
        self._utc = UtcInstant(utc)

    def monotonic(self) -> MonotonicInstant:
        return self._monotonic

    def utc_now(self) -> UtcInstant:
        return self._utc

    def advance(self, nanoseconds: int) -> None:
        self._monotonic = self._monotonic.plus(nanoseconds)
        self._utc = UtcInstant(self._utc.value + timedelta(microseconds=nanoseconds / 1000))

    def set_utc(self, value: datetime) -> None:
        """Allow wall-clock jumps while leaving monotonic time untouched."""

        self._utc = UtcInstant(value)
