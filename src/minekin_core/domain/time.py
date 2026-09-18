"""Explicit monotonic and wall-clock time semantics.

Only :class:`MonotonicInstant` participates in timeout decisions.  UTC timestamps
exist for human audit and may jump independently when the system clock is adjusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, order=True, slots=True)
class MonotonicInstant:
    nanoseconds: int

    def __post_init__(self) -> None:
        if isinstance(self.nanoseconds, bool):
            raise TypeError("monotonic nanoseconds must be an integer")
        if self.nanoseconds < 0:
            raise ValueError("monotonic nanoseconds cannot be negative")

    def plus(self, duration_ns: int) -> MonotonicInstant:
        if isinstance(duration_ns, bool):
            raise TypeError("duration_ns must be an integer")
        if duration_ns < 0:
            raise ValueError("duration_ns cannot be negative")
        return MonotonicInstant(self.nanoseconds + duration_ns)


@dataclass(frozen=True, order=True, slots=True)
class UtcInstant:
    value: datetime

    def __post_init__(self) -> None:
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise ValueError("UTC instant must be timezone-aware")
        object.__setattr__(self, "value", self.value.astimezone(UTC))

    def isoformat(self) -> str:
        return self.value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, order=True, slots=True)
class Deadline:
    """An absolute local monotonic deadline; it is never serialized as wall time."""

    at: MonotonicInstant

    @classmethod
    def after(cls, now: MonotonicInstant, duration_ns: int) -> Deadline:
        return cls(now.plus(duration_ns))

    @property
    def monotonic_ns(self) -> int:
        return self.at.nanoseconds

    def is_expired(self, now: MonotonicInstant) -> bool:
        return now >= self.at

    def remaining_ns(self, now: MonotonicInstant) -> int:
        return max(0, self.at.nanoseconds - now.nanoseconds)
