"""Noticing a Bridge that has gone quiet, and stopping the input because of it.

The Bridge's own watchdog is the guarantee that keys come up: it lives in the
process holding the keys and needs nobody's permission to let go. This is the
second layer, and it exists because the first layer is inside a process that can
die, hang, or lose its socket. Core cannot release keys itself, so what it can do
is stop authorising input — which is the part that must not depend on the Bridge
cooperating.

Two failures look identical from here and are treated the same way: a dead Bridge
and a live Bridge whose packets stopped arriving. Core cannot tell them apart, and
a client holding a movement key while nothing can contradict it is the case both
watchdogs exist to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass

from minekin_core.domain.ids import Generation
from minekin_core.domain.time import MonotonicInstant

# How many consecutive intervals may pass without a heartbeat before the channel
# is considered lost. More than one, because a single missed interval is ordinary
# scheduling noise rather than a dead peer.
DEFAULT_TOLERATED_MISSES = 3


@dataclass(frozen=True, slots=True)
class ControlHeartbeat:
    """What the Bridge reports periodically, in its own monotonic clock."""

    generation: Generation
    monotonic_ns: int


class ControlWatchdog:
    """Arms when the session becomes playable and expires when heartbeats stop."""

    def __init__(
        self,
        interval_ms: int,
        *,
        tolerated_misses: int = DEFAULT_TOLERATED_MISSES,
    ) -> None:
        if interval_ms <= 0:
            raise ValueError("a heartbeat interval must be positive")
        if tolerated_misses < 1:
            raise ValueError("at least one interval must be tolerated")
        self._interval_ns = interval_ms * 1_000_000
        self._tolerance_ns = self._interval_ns * tolerated_misses
        self._generation: Generation | None = None
        self._deadline_ns: int | None = None
        self._last_ns: int | None = None

    @property
    def armed(self) -> bool:
        return self._deadline_ns is not None

    @property
    def interval_ns(self) -> int:
        return self._interval_ns

    def arm(self, generation: Generation, now: MonotonicInstant) -> None:
        """Start watching, before any heartbeat has arrived.

        Arming before the first heartbeat is the fail-closed choice: a Bridge that
        dies during startup never sends one, and a watchdog that waits to be told
        about it would never notice.
        """

        self._generation = generation
        self._last_ns = None
        self._deadline_ns = now.nanoseconds + self._tolerance_ns

    def disarm(self) -> None:
        """Stop watching, for a session that is no longer playable."""

        self._generation = None
        self._deadline_ns = None
        self._last_ns = None

    def observe(self, heartbeat: ControlHeartbeat) -> bool:
        """Accept a heartbeat, or ignore it and say so.

        An ignored heartbeat must be *ignored*: letting an old generation's packet
        extend the deadline would make a closed connection look alive.
        """

        if self._generation is None:
            return False
        if heartbeat.generation != self._generation:
            return False
        if self._last_ns is not None and heartbeat.monotonic_ns < self._last_ns:
            # A reordered packet is not new information about the Bridge's health.
            return False
        self._last_ns = heartbeat.monotonic_ns
        self._deadline_ns = heartbeat.monotonic_ns + self._tolerance_ns
        return True

    def deadline_ns(self) -> int | None:
        return self._deadline_ns

    def has_expired(self, now: MonotonicInstant) -> bool:
        """Whether the channel is considered lost. An unarmed watchdog never is."""

        if self._deadline_ns is None:
            return False
        return now.nanoseconds >= self._deadline_ns
