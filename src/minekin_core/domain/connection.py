"""Generation-bound admission state for one managed client connection.

Socket, DNS, Netty and Minecraft callbacks arrive asynchronously.  This module
owns the small piece of mutable truth they are not allowed to infer themselves:
which connection generation is current, and which event may advance it.  A
callback from a closed or older generation is evidence only; it can never make a
newer attempt playable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from minekin_core.domain.ids import Generation, OpaqueId

_SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


class ConnectionState(StrEnum):
    REQUEST_ACCEPTED = "REQUEST_ACCEPTED"
    RESOLVING = "RESOLVING"
    LOGIN_NEGOTIATING = "LOGIN_NEGOTIATING"
    PLAY_INIT = "PLAY_INIT"
    JOIN_SEEN = "JOIN_SEEN"
    PLAYABLE = "PLAYABLE"
    FAILED = "FAILED"


class ConnectionSignal(StrEnum):
    RESOLUTION_STARTED = "RESOLUTION_STARTED"
    ENDPOINT_ALLOWED = "ENDPOINT_ALLOWED"
    LOGIN_ACCEPTED = "LOGIN_ACCEPTED"
    JOIN_OBSERVED = "JOIN_OBSERVED"
    SNAPSHOT_ACCEPTED = "SNAPSHOT_ACCEPTED"
    FAILURE = "FAILURE"


class CallbackDisposition(StrEnum):
    ADVANCED = "ADVANCED"
    FAILED = "FAILED"
    CLOSED = "CLOSED"
    STALE_GENERATION = "STALE_GENERATION"
    FUTURE_GENERATION = "FUTURE_GENERATION"
    CLOSED_GENERATION = "CLOSED_GENERATION"
    OUT_OF_ORDER = "OUT_OF_ORDER"


_ADVANCES: Final[MappingProxyType[tuple[ConnectionState, ConnectionSignal], ConnectionState]] = (
    MappingProxyType(
        {
            (ConnectionState.REQUEST_ACCEPTED, ConnectionSignal.RESOLUTION_STARTED): (
                ConnectionState.RESOLVING
            ),
            (ConnectionState.RESOLVING, ConnectionSignal.ENDPOINT_ALLOWED): (
                ConnectionState.LOGIN_NEGOTIATING
            ),
            (ConnectionState.LOGIN_NEGOTIATING, ConnectionSignal.LOGIN_ACCEPTED): (
                ConnectionState.PLAY_INIT
            ),
            (ConnectionState.PLAY_INIT, ConnectionSignal.JOIN_OBSERVED): (
                ConnectionState.JOIN_SEEN
            ),
            (ConnectionState.JOIN_SEEN, ConnectionSignal.SNAPSHOT_ACCEPTED): (
                ConnectionState.PLAYABLE
            ),
        }
    )
)


@dataclass(frozen=True, slots=True)
class ConnectionAttempt:
    generation: Generation
    server_profile_id: OpaqueId
    server_profile_revision: str
    state: ConnectionState = ConnectionState.REQUEST_ACCEPTED

    def __post_init__(self) -> None:
        if not _SHA256.fullmatch(self.server_profile_revision):
            raise ValueError("server_profile_revision must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class CallbackDecision:
    disposition: CallbackDisposition
    generation: Generation
    previous_state: ConnectionState | None
    current_state: ConnectionState | None

    @property
    def changed_state(self) -> bool:
        return self.previous_state != self.current_state


@dataclass(slots=True)
class ConnectionGenerations:
    """Allocate generations and gate every asynchronous connection callback."""

    _last_generation: Generation | None = None
    _active: ConnectionAttempt | None = None

    @property
    def active(self) -> ConnectionAttempt | None:
        return self._active

    @property
    def last_generation(self) -> Generation | None:
        return self._last_generation

    def begin(self, profile_id: OpaqueId, profile_revision: str) -> ConnectionAttempt:
        if self._active is not None:
            raise ValueError("the current connection generation must be closed before reconnecting")
        generation = (
            Generation(1) if self._last_generation is None else self._last_generation.next()
        )
        attempt = ConnectionAttempt(generation, profile_id, profile_revision)
        self._last_generation = generation
        self._active = attempt
        return attempt

    def apply(self, generation: Generation, signal: ConnectionSignal) -> CallbackDecision:
        attempt = self._active
        if attempt is None:
            return CallbackDecision(
                CallbackDisposition.CLOSED_GENERATION,
                generation,
                None,
                None,
            )
        if not attempt.generation.accepts(generation):
            if generation > attempt.generation:
                previous = attempt.state
                self._active = replace(attempt, state=ConnectionState.FAILED)
                return CallbackDecision(
                    CallbackDisposition.FUTURE_GENERATION,
                    generation,
                    previous,
                    ConnectionState.FAILED,
                )
            return CallbackDecision(
                CallbackDisposition.STALE_GENERATION,
                generation,
                attempt.state,
                attempt.state,
            )

        previous = attempt.state
        if signal is ConnectionSignal.FAILURE:
            if previous in {ConnectionState.PLAYABLE, ConnectionState.FAILED}:
                return CallbackDecision(
                    CallbackDisposition.OUT_OF_ORDER,
                    generation,
                    previous,
                    previous,
                )
            self._active = replace(attempt, state=ConnectionState.FAILED)
            return CallbackDecision(
                CallbackDisposition.FAILED,
                generation,
                previous,
                ConnectionState.FAILED,
            )

        target = _ADVANCES.get((previous, signal))
        if target is None:
            # A callback from the current generation in an impossible order is
            # not merely late: treating it as progress could grant input early.
            # Fail this attempt closed and require a new generation.
            current = previous
            if previous is not ConnectionState.FAILED:
                self._active = replace(attempt, state=ConnectionState.FAILED)
                current = ConnectionState.FAILED
            return CallbackDecision(
                CallbackDisposition.OUT_OF_ORDER,
                generation,
                previous,
                current,
            )

        self._active = replace(attempt, state=target)
        return CallbackDecision(
            CallbackDisposition.ADVANCED,
            generation,
            previous,
            target,
        )

    def close(self, generation: Generation) -> CallbackDecision:
        """Invalidate before the caller cancels a channel or network handler."""

        attempt = self._active
        if attempt is None:
            return CallbackDecision(
                CallbackDisposition.CLOSED_GENERATION,
                generation,
                None,
                None,
            )
        if not attempt.generation.accepts(generation):
            if generation > attempt.generation:
                return CallbackDecision(
                    CallbackDisposition.FUTURE_GENERATION,
                    generation,
                    attempt.state,
                    attempt.state,
                )
            return CallbackDecision(
                CallbackDisposition.STALE_GENERATION,
                generation,
                attempt.state,
                attempt.state,
            )
        previous = attempt.state
        self._active = None
        return CallbackDecision(
            CallbackDisposition.CLOSED,
            generation,
            previous,
            None,
        )
