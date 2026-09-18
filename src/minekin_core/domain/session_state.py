"""The frozen P0 managed-client session state machine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


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

    def advance(self, target: SessionState) -> SessionState:
        require_transition(self.state, target)
        previous = self.state
        self.state = target
        return previous
