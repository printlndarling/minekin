"""The frozen P0 managed-client session state machine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from minekin_core.domain.connection import CallbackDecision, CallbackDisposition, ConnectionState


class SessionState(StrEnum):
    STOPPED = "STOPPED"
    PREPARING = "PREPARING"
    STARTING_CLIENT = "STARTING_CLIENT"
    WAITING_BRIDGE = "WAITING_BRIDGE"
    HANDSHAKING = "HANDSHAKING"
    READY_MENU = "READY_MENU"
    CONNECTING = "CONNECTING"
    JOINED_UNVERIFIED = "JOINED_UNVERIFIED"
    PLAYABLE = "PLAYABLE"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


_TRANSITIONS: Final[Mapping[SessionState, frozenset[SessionState]]] = MappingProxyType(
    {
        SessionState.STOPPED: frozenset({SessionState.PREPARING}),
        SessionState.PREPARING: frozenset({SessionState.STARTING_CLIENT, SessionState.FAILED}),
        SessionState.STARTING_CLIENT: frozenset({SessionState.WAITING_BRIDGE, SessionState.FAILED}),
        SessionState.WAITING_BRIDGE: frozenset(
            {SessionState.HANDSHAKING, SessionState.STOPPING, SessionState.FAILED}
        ),
        SessionState.HANDSHAKING: frozenset(
            {SessionState.READY_MENU, SessionState.STOPPING, SessionState.FAILED}
        ),
        SessionState.READY_MENU: frozenset({SessionState.CONNECTING, SessionState.STOPPING}),
        SessionState.CONNECTING: frozenset(
            {
                SessionState.JOINED_UNVERIFIED,
                SessionState.READY_MENU,
                SessionState.FAILED,
            }
        ),
        SessionState.JOINED_UNVERIFIED: frozenset(
            {SessionState.PLAYABLE, SessionState.READY_MENU, SessionState.FAILED}
        ),
        SessionState.PLAYABLE: frozenset(
            {SessionState.STOPPING, SessionState.READY_MENU, SessionState.FAILED}
        ),
        SessionState.STOPPING: frozenset({SessionState.STOPPED, SessionState.FAILED}),
        SessionState.FAILED: frozenset({SessionState.STOPPING, SessionState.PREPARING}),
    }
)


class IllegalSessionTransition(ValueError):
    def __init__(self, source: SessionState, target: SessionState) -> None:
        self.source = source
        self.target = target
        super().__init__(f"illegal session transition: {source.value} -> {target.value}")


def allowed_transitions(state: SessionState) -> frozenset[SessionState]:
    return _TRANSITIONS[state]


def can_transition(source: SessionState, target: SessionState) -> bool:
    return target in _TRANSITIONS[source]


def require_transition(source: SessionState, target: SessionState) -> None:
    if not can_transition(source, target):
        raise IllegalSessionTransition(source, target)


@dataclass(slots=True)
class SessionStateMachine:
    """Small mutable holder; services remain responsible for persisting transitions."""

    state: SessionState = SessionState.STOPPED

    @property
    def allowed(self) -> frozenset[SessionState]:
        return allowed_transitions(self.state)

    def can_advance(self, target: SessionState) -> bool:
        return can_transition(self.state, target)

    def validate_advance(self, target: SessionState) -> SessionState:
        """Validate a move before its caller persists the corresponding fact.

        The returned state is the exact source that must be recorded with the
        target. Callers that await durable I/O between validation and ``advance``
        must still apply the move synchronously immediately after that I/O.
        """

        require_transition(self.state, target)
        return self.state

    def advance(self, target: SessionState) -> SessionState:
        require_transition(self.state, target)
        previous = self.state
        self.state = target
        return previous


# What a connection attempt being in each state means for the session. The four
# admission phases before a JOIN are all one thing to the session: a connection
# in flight. The session table above, not this map, decides whether the session
# may actually go there — so a report that skips a step (a JOIN with no
# CONNECTING before it) is refused rather than fast-forwarded.
_SESSION_FOR_CONNECTION: Final[Mapping[ConnectionState, SessionState]] = MappingProxyType(
    {
        ConnectionState.REQUEST_ACCEPTED: SessionState.CONNECTING,
        ConnectionState.RESOLVING: SessionState.CONNECTING,
        ConnectionState.LOGIN_NEGOTIATING: SessionState.CONNECTING,
        ConnectionState.PLAY_INIT: SessionState.CONNECTING,
        ConnectionState.JOIN_SEEN: SessionState.JOINED_UNVERIFIED,
        ConnectionState.PLAYABLE: SessionState.PLAYABLE,
        ConnectionState.DISCONNECTED: SessionState.READY_MENU,
        ConnectionState.FAILED: SessionState.FAILED,
    }
)

# Decisions that are about the attempt the session is currently running. A
# stale or already-closed generation is diagnostic only: it is exactly what a
# reconnect leaves behind, and letting it move the session is the bug the
# generation gate exists to prevent.
_DECIDES_FOR_SESSION: Final[frozenset[CallbackDisposition]] = frozenset(
    {
        CallbackDisposition.ADVANCED,
        CallbackDisposition.FAILED,
        CallbackDisposition.OUT_OF_ORDER,
        CallbackDisposition.FUTURE_GENERATION,
    }
)


def session_state_for_connection(state: ConnectionState | None) -> SessionState | None:
    if state is None:
        return None
    return _SESSION_FOR_CONNECTION[state]


def advance_for_connection(
    machine: SessionStateMachine, decision: CallbackDecision
) -> SessionState | None:
    """Move the session to whatever this connection decision implies.

    Returns the state the session left, or ``None`` when nothing moved — either
    because the decision does not speak for the current attempt, or because the
    session is already where it would put it.

    Raises ``IllegalSessionTransition`` when the frozen table forbids the move.
    That is not defensiveness: the table enumerates every legal session jump, so
    an attempt trying to reach a state the session cannot reach from here means
    the two machines disagree about what happened, and guessing would paper over
    the disagreement.
    """

    target = connection_transition_target(machine, decision)
    if target is None:
        return None
    return machine.advance(target)


def connection_transition_target(
    machine: SessionStateMachine, decision: CallbackDecision
) -> SessionState | None:
    """Return the validated target implied by a connection decision, if any.

    This keeps the generation/disposition rules in the domain while allowing the
    runtime to durably record the move before applying it to the mutable machine.
    """

    if decision.disposition not in _DECIDES_FOR_SESSION:
        return None
    target = session_state_for_connection(decision.current_state)
    if target is None or target is machine.state:
        return None
    machine.validate_advance(target)
    return target
