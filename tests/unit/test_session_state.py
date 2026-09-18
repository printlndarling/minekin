import pytest

from minekin_core.domain.session_state import (
    IllegalSessionTransition,
    SessionState,
    SessionStateMachine,
    allowed_transitions,
)


def test_happy_path_to_playable_and_stop() -> None:
    machine = SessionStateMachine()
    for target in (
        SessionState.PREPARING,
        SessionState.STARTING_CLIENT,
        SessionState.WAITING_BRIDGE,
        SessionState.HANDSHAKING,
        SessionState.READY_MENU,
        SessionState.CONNECTING,
        SessionState.JOINED_UNVERIFIED,
        SessionState.PLAYABLE,
        SessionState.STOPPING,
        SessionState.STOPPED,
    ):
        machine.advance(target)
    assert machine.state is SessionState.STOPPED


def test_every_state_has_exact_frozen_outlets() -> None:
    assert allowed_transitions(SessionState.READY_MENU) == frozenset(
        {SessionState.CONNECTING, SessionState.STOPPING}
    )
    assert allowed_transitions(SessionState.FAILED) == frozenset(
        {SessionState.STOPPING, SessionState.PREPARING}
    )


def test_unlisted_transition_is_rejected_without_mutation() -> None:
    machine = SessionStateMachine(SessionState.PLAYABLE)
    with pytest.raises(IllegalSessionTransition):
        machine.advance(SessionState.HANDSHAKING)
    assert machine.state is SessionState.PLAYABLE


def test_self_transition_is_not_implicitly_allowed() -> None:
    with pytest.raises(IllegalSessionTransition):
        SessionStateMachine().advance(SessionState.STOPPED)
