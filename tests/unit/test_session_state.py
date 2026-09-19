import pytest

from minekin_core.domain.connection import CallbackDecision, CallbackDisposition, ConnectionState
from minekin_core.domain.ids import Generation
from minekin_core.domain.session_state import (
    IllegalSessionTransition,
    SessionState,
    SessionStateMachine,
    advance_for_connection,
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


def _ready_machine() -> SessionStateMachine:
    machine = SessionStateMachine()
    for target in (
        SessionState.PREPARING,
        SessionState.STARTING_CLIENT,
        SessionState.WAITING_BRIDGE,
        SessionState.HANDSHAKING,
        SessionState.READY_MENU,
    ):
        machine.advance(target)
    return machine


def _decision(
    disposition: CallbackDisposition,
    current: ConnectionState | None,
    previous: ConnectionState | None = None,
) -> CallbackDecision:
    return CallbackDecision(
        disposition=disposition,
        generation=Generation(1),
        previous_state=previous if previous is not None else current,
        current_state=current,
    )


def test_the_admission_phases_walk_the_session_to_playable() -> None:
    machine = _ready_machine()

    assert (
        advance_for_connection(
            machine, _decision(CallbackDisposition.ADVANCED, ConnectionState.RESOLVING)
        )
        is SessionState.READY_MENU
    )
    assert machine.state is SessionState.CONNECTING
    advance_for_connection(
        machine, _decision(CallbackDisposition.ADVANCED, ConnectionState.JOIN_SEEN)
    )
    assert machine.state is SessionState.JOINED_UNVERIFIED
    advance_for_connection(
        machine, _decision(CallbackDisposition.ADVANCED, ConnectionState.PLAYABLE)
    )
    assert machine.state is SessionState.PLAYABLE


@pytest.mark.parametrize(
    "phase",
    [
        ConnectionState.REQUEST_ACCEPTED,
        ConnectionState.RESOLVING,
        ConnectionState.LOGIN_NEGOTIATING,
        ConnectionState.PLAY_INIT,
    ],
)
def test_every_phase_before_a_join_is_the_same_session_state(phase: ConnectionState) -> None:
    """Four admission phases, one session state: a later one is not a new jump."""

    machine = _ready_machine()
    advance_for_connection(machine, _decision(CallbackDisposition.ADVANCED, phase))

    assert machine.state is SessionState.CONNECTING
    assert advance_for_connection(machine, _decision(CallbackDisposition.ADVANCED, phase)) is None


def test_a_disconnect_returns_the_session_to_the_menu() -> None:
    machine = _ready_machine()
    for phase in (
        ConnectionState.RESOLVING,
        ConnectionState.JOIN_SEEN,
        ConnectionState.PLAYABLE,
    ):
        advance_for_connection(machine, _decision(CallbackDisposition.ADVANCED, phase))

    previous = advance_for_connection(
        machine, _decision(CallbackDisposition.ADVANCED, ConnectionState.DISCONNECTED)
    )

    assert previous is SessionState.PLAYABLE
    assert machine.state is SessionState.READY_MENU


def test_an_attempt_that_fails_closed_fails_the_session() -> None:
    machine = _ready_machine()
    advance_for_connection(
        machine, _decision(CallbackDisposition.ADVANCED, ConnectionState.RESOLVING)
    )

    advance_for_connection(machine, _decision(CallbackDisposition.FAILED, ConnectionState.FAILED))

    assert machine.state is SessionState.FAILED


def test_an_impossible_report_from_the_current_generation_fails_the_session() -> None:
    """The connection machine already failed that attempt closed; the session follows."""

    machine = _ready_machine()
    advance_for_connection(
        machine, _decision(CallbackDisposition.ADVANCED, ConnectionState.RESOLVING)
    )

    advance_for_connection(
        machine, _decision(CallbackDisposition.OUT_OF_ORDER, ConnectionState.FAILED)
    )

    assert machine.state is SessionState.FAILED


@pytest.mark.parametrize(
    "disposition",
    [CallbackDisposition.STALE_GENERATION, CallbackDisposition.CLOSED_GENERATION],
)
def test_a_report_that_speaks_for_another_generation_moves_nothing(
    disposition: CallbackDisposition,
) -> None:
    """This is what a reconnect leaves behind; it is the whole point of the gate."""

    machine = _ready_machine()

    moved = advance_for_connection(
        machine, _decision(disposition, ConnectionState.PLAYABLE, ConnectionState.RESOLVING)
    )

    assert moved is None
    assert machine.state is SessionState.READY_MENU


def test_a_join_that_skips_the_connect_step_is_refused() -> None:
    """The frozen table lists every legal jump; guessing is how PLAYABLE gets granted early."""

    machine = _ready_machine()

    with pytest.raises(IllegalSessionTransition):
        advance_for_connection(
            machine, _decision(CallbackDisposition.ADVANCED, ConnectionState.JOIN_SEEN)
        )

    assert machine.state is SessionState.READY_MENU


def test_a_failure_after_playable_does_not_move_the_session() -> None:
    """The connection machine declines to rewrite an observed disconnect as a failure."""

    machine = _ready_machine()
    for phase in (ConnectionState.RESOLVING, ConnectionState.JOIN_SEEN, ConnectionState.PLAYABLE):
        advance_for_connection(machine, _decision(CallbackDisposition.ADVANCED, phase))
    assert machine.state is SessionState.PLAYABLE

    moved = advance_for_connection(
        machine, _decision(CallbackDisposition.OUT_OF_ORDER, ConnectionState.PLAYABLE)
    )

    assert moved is None
    assert machine.state is SessionState.PLAYABLE


def test_a_closed_connection_has_no_session_state_to_imply() -> None:
    machine = _ready_machine()

    moved = advance_for_connection(
        machine, _decision(CallbackDisposition.CLOSED, None, ConnectionState.RESOLVING)
    )

    assert moved is None
    assert machine.state is SessionState.READY_MENU
