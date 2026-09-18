"""Identifiers and counters crossing asynchronous boundaries.

Opaque identifiers are deliberately not interchangeable.  Generation and sequence
numbers start at one: zero is the protobuf/default "not supplied" value.  Both are
unsigned 64-bit values and overflow is an invariant failure, never a wraparound.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UINT64_MAX = (1 << 64) - 1


@dataclass(frozen=True, slots=True)
class OpaqueId:
    """A log-safe, path-independent opaque identifier."""

    value: str

    def __post_init__(self) -> None:
        if not _ID_PATTERN.fullmatch(self.value):
            raise ValueError("identifier must be 1-128 ASCII letters, digits, '.', '_', ':' or '-'")

    @classmethod
    def new(cls):
        return cls(uuid.uuid4().hex)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class KinId(OpaqueId):
    """Persistent identity root; it must not be derived from a player name."""


@dataclass(frozen=True, slots=True)
class RunId(OpaqueId):
    """One minekin-core process lifetime."""


@dataclass(frozen=True, slots=True)
class ClientInstanceId(OpaqueId):
    """One managed JVM process instance."""


@dataclass(frozen=True, slots=True)
class SessionId(OpaqueId):
    """One target-world session."""


@dataclass(frozen=True, slots=True)
class WorldContextId(OpaqueId):
    """A confirmed world identity, not merely host:port."""


@dataclass(frozen=True, slots=True)
class CorrelationId(OpaqueId):
    """Connects a command, its events, and its evidence."""


@dataclass(frozen=True, slots=True)
class EventId(OpaqueId):
    """Unique append-only event identity."""


@dataclass(frozen=True, slots=True)
class CommandId(OpaqueId):
    """Unique command-attempt identity."""


@dataclass(frozen=True, slots=True)
class LeaseId(OpaqueId):
    """Unique, generation-bound input lease identity."""


@dataclass(frozen=True, order=True, slots=True)
class Generation:
    """Monotonic connection-attempt generation within a session."""

    value: int

    def __post_init__(self) -> None:
        _validate_positive_uint64(self.value, "generation")

    def next(self) -> Generation:
        if self.value == _UINT64_MAX:
            raise OverflowError("generation exhausted uint64 range")
        return Generation(self.value + 1)

    def accepts(self, candidate: Generation) -> bool:
        """Return whether an asynchronous result belongs to this generation."""

        return type(candidate) is Generation and candidate == self

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True, order=True, slots=True)
class Sequence:
    """Per-sender, per-channel monotonic message sequence."""

    value: int

    def __post_init__(self) -> None:
        _validate_positive_uint64(self.value, "sequence")

    def next(self) -> Sequence:
        if self.value == _UINT64_MAX:
            raise OverflowError("sequence exhausted uint64 range")
        return Sequence(self.value + 1)

    def __int__(self) -> int:
        return self.value


def _validate_positive_uint64(value: int, label: str) -> None:
    if isinstance(value, bool):
        raise TypeError(f"{label} must be an integer")
    if not 1 <= value <= _UINT64_MAX:
        raise ValueError(f"{label} must be in uint64 range 1..{_UINT64_MAX}")
