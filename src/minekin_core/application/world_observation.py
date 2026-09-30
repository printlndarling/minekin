"""The latest coherent world observation, kept for whoever acts next.

The action contract says every outcome is checked against a reading that arrives
*after* the action, and the S2 spec says the Bridge publishes those readings on
a fixed tick cadence rather than on request. So someone has to hold the newest
one. This is that someone, and it deliberately holds only the newest coherent
reading plus its own counts — the same shape `_Progress` holds the last LAN
publication in, and for the same reason: a second source of truth about what
the client last said would be a second thing to fall out of agreement with the
channel.

It is not a cache of history and not a queue: a skill takes `latest()` as its
pre-state, then `wait_for_newer(...)` to see what the world says after. An
observation that fails the coherence rules in `domain/perception` is counted
with its findings and dropped — an incoherent reading cannot silently become a
post-state.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final

from minekin_core.domain.perception import IntegrityViolation, WorldObservationValue

NO_GENERATION: Final = -1


@dataclass(frozen=True, slots=True)
class ObservationRefusal:
    """A reading that arrived and was not taken, and why."""

    game_tick: int
    generation: int
    violations: tuple[IntegrityViolation, ...]
    stale_generation: bool = False


@dataclass(slots=True)
class WorldObservationStore:
    """One session's latest player-equivalent reading, generation-gated.

    `expected_generation` is the connection generation observations are admitted
    from, in the same sense a lifecycle report is gated by it: a reading from a
    closed generation describes a world this session is no longer in. `None`
    means no attempt is active and nothing is admitted.
    """

    expected_generation: int | None = None
    _latest: WorldObservationValue | None = field(default=None, init=False)
    _refusals: tuple[ObservationRefusal, ...] = field(default=(), init=False)
    _accepted: int = field(default=0, init=False)
    _wake: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    @property
    def latest(self) -> WorldObservationValue | None:
        return self._latest

    @property
    def accepted_count(self) -> int:
        return self._accepted

    @property
    def refused(self) -> Sequence[ObservationRefusal]:
        return self._refusals

    def admit(self, value: WorldObservationValue, violations: Sequence[IntegrityViolation]) -> bool:
        """Take one decoded reading, or count it as refused. Returns which."""

        stale = self.expected_generation is None or value.generation != self.expected_generation
        if violations or stale:
            self._refusals += (
                ObservationRefusal(
                    game_tick=value.game_tick,
                    generation=value.generation,
                    violations=tuple(violations),
                    stale_generation=stale and not violations,
                ),
            )
            return False
        # Ticks are the Bridge's clock: never go backwards, so a replayed or
        # reordered frame cannot turn a post-state back into a pre-state.
        if self._latest is not None and value.game_tick <= self._latest.game_tick:
            return False
        self._latest = value
        self._accepted += 1
        self._wake.set()
        return True

    async def wait_until(
        self,
        predicate: Callable[[WorldObservationValue], bool],
        *,
        timeout_s: float,
    ) -> WorldObservationValue | None:
        """The newest admitted reading the predicate holds of, or `None` on
        timeout.

        A predicate that holds of the *current* reading is answered immediately,
        because the fact it asks for is already here: a waiter that demanded a
        fresher tick would be waiting for the client to contradict a truth it
        just reported. After that it parks on the store's wake and re-checks the
        store, never a captured value, so a wake belonging to another waiter
        costs a loop rather than delivering a stale reading.
        """

        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while True:
            current = self._latest
            if current is not None and predicate(current):
                return current
            remaining = deadline - loop.time()
            if remaining <= 0:
                return None
            self._wake.clear()
            current = self._latest
            if current is not None and predicate(current):
                continue
            try:
                await asyncio.wait_for(self._wake.wait(), remaining)
            except TimeoutError:
                return None

    async def wait_for_newer(
        self, pre: WorldObservationValue, *, timeout_s: float
    ) -> WorldObservationValue | None:
        """The next admitted reading *after* `pre`, or `None` on timeout.

        The waiter's tick comparison, not a wake count: two readings admitted in
        one step still deliver exactly the one fact the skill needs — the world
        after the action.
        """

        return await self.wait_until(
            lambda latest: latest.game_tick > pre.game_tick, timeout_s=timeout_s
        )

    async def wait_for_screen(
        self, *, has_sync_id: bool, timeout_s: float
    ) -> WorldObservationValue | None:
        """The newest admitted reading whose screen state matches, or `None`.

        `has_sync_id=True` waits for a screen the client reports a handler for —
        the precondition every GUI click is checked against — and the reading it
        returns is the caller's own evidence for the sync id it then names.
        """

        return await self.wait_until(
            lambda latest: (
                latest.gui is not None and (latest.gui.sync_id is not None) == has_sync_id
            ),
            timeout_s=timeout_s,
        )
