from __future__ import annotations

import pytest

from minekin_core.domain.connection import (
    CallbackDisposition,
    ConnectionGenerations,
    ConnectionSignal,
    ConnectionState,
)
from minekin_core.domain.ids import Generation, OpaqueId

PROFILE = OpaqueId("p0-controlled-offline-loopback")
REVISION = "a" * 64


def test_join_and_authoritative_snapshot_are_both_required_for_playable() -> None:
    connections = ConnectionGenerations()
    attempt = connections.begin(PROFILE, REVISION)

    for signal in (
        ConnectionSignal.RESOLUTION_STARTED,
        ConnectionSignal.ENDPOINT_ALLOWED,
        ConnectionSignal.LOGIN_ACCEPTED,
    ):
        connections.apply(attempt.generation, signal)

    assert connections.active is not None
    assert connections.active.state is ConnectionState.PLAY_INIT
    connections.apply(attempt.generation, ConnectionSignal.JOIN_OBSERVED)
    assert connections.active is not None
    assert connections.active.state is ConnectionState.JOIN_SEEN
    connections.apply(attempt.generation, ConnectionSignal.SNAPSHOT_ACCEPTED)
    assert connections.active is not None
    assert connections.active.state is ConnectionState.PLAYABLE


def test_reconnect_allocates_a_new_generation_and_old_callback_is_diagnostic_only() -> None:
    connections = ConnectionGenerations()
    first = connections.begin(PROFILE, REVISION)
    connections.close(first.generation)
    second = connections.begin(PROFILE, REVISION)

    decision = connections.apply(first.generation, ConnectionSignal.SNAPSHOT_ACCEPTED)

    assert second.generation == Generation(2)
    assert decision.disposition is CallbackDisposition.STALE_GENERATION
    assert not decision.changed_state
    assert connections.active is not None
    assert connections.active.state is ConnectionState.REQUEST_ACCEPTED


def test_close_invalidates_before_late_callbacks_arrive() -> None:
    connections = ConnectionGenerations()
    attempt = connections.begin(PROFILE, REVISION)

    closed = connections.close(attempt.generation)
    late = connections.apply(attempt.generation, ConnectionSignal.RESOLUTION_STARTED)

    assert closed.changed_state
    assert closed.current_state is None
    assert late.disposition is CallbackDisposition.CLOSED_GENERATION
    assert connections.active is None


def test_current_generation_out_of_order_callback_fails_closed() -> None:
    connections = ConnectionGenerations()
    attempt = connections.begin(PROFILE, REVISION)

    decision = connections.apply(attempt.generation, ConnectionSignal.JOIN_OBSERVED)

    assert decision.disposition is CallbackDisposition.OUT_OF_ORDER
    assert decision.changed_state
    assert connections.active is not None
    assert connections.active.state is ConnectionState.FAILED


def test_unallocated_future_generation_callback_fails_current_attempt() -> None:
    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    decision = connections.apply(Generation(2), ConnectionSignal.RESOLUTION_STARTED)

    assert decision.disposition is CallbackDisposition.FUTURE_GENERATION
    assert connections.active is not None
    assert connections.active.state is ConnectionState.FAILED


def test_failure_is_terminal_until_generation_is_explicitly_closed() -> None:
    connections = ConnectionGenerations()
    attempt = connections.begin(PROFILE, REVISION)

    decision = connections.apply(attempt.generation, ConnectionSignal.FAILURE)

    assert decision.disposition is CallbackDisposition.FAILED
    assert connections.active is not None
    assert connections.active.state is ConnectionState.FAILED
    with pytest.raises(ValueError, match="must be closed"):
        connections.begin(PROFILE, REVISION)


def test_stale_close_cannot_cancel_the_current_attempt() -> None:
    connections = ConnectionGenerations()
    first = connections.begin(PROFILE, REVISION)
    connections.close(first.generation)
    second = connections.begin(PROFILE, REVISION)

    decision = connections.close(first.generation)

    assert decision.disposition is CallbackDisposition.STALE_GENERATION
    assert connections.active is second


@pytest.mark.parametrize("revision", ["", "A" * 64, "a" * 63, "g" * 64])
def test_profile_revision_must_be_a_canonical_sha256(revision: str) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        ConnectionGenerations().begin(PROFILE, revision)


def _drive_to(connections: ConnectionGenerations, *signals: ConnectionSignal) -> Generation:
    attempt = connections.begin(PROFILE, REVISION)
    for signal in signals:
        connections.apply(attempt.generation, signal)
    return attempt.generation


_IN_PLAY = (
    ConnectionSignal.RESOLUTION_STARTED,
    ConnectionSignal.ENDPOINT_ALLOWED,
    ConnectionSignal.LOGIN_ACCEPTED,
)
_JOINED = (*_IN_PLAY, ConnectionSignal.JOIN_OBSERVED)
_PLAYABLE = (*_JOINED, ConnectionSignal.SNAPSHOT_ACCEPTED)


@pytest.mark.parametrize("prelude", [_IN_PLAY, _JOINED, _PLAYABLE])
def test_a_disconnect_ends_the_session_without_inventing_a_reason(
    prelude: tuple[ConnectionSignal, ...],
) -> None:
    """The Bridge reports a closed connection as a phase, not as a failure code."""

    connections = ConnectionGenerations()
    generation = _drive_to(connections, *prelude)

    decision = connections.apply(generation, ConnectionSignal.DISCONNECTED)

    assert decision.disposition is CallbackDisposition.ADVANCED
    assert connections.active is not None
    assert connections.active.state is ConnectionState.DISCONNECTED


def test_a_disconnect_before_the_play_phase_is_out_of_order() -> None:
    """A socket closed mid-login is a login failure that names a reason, not this."""

    connections = ConnectionGenerations()
    generation = _drive_to(connections, ConnectionSignal.RESOLUTION_STARTED)

    decision = connections.apply(generation, ConnectionSignal.DISCONNECTED)

    assert decision.disposition is CallbackDisposition.OUT_OF_ORDER
    assert connections.active is not None
    assert connections.active.state is ConnectionState.FAILED


def test_a_late_report_cannot_turn_a_disconnect_into_a_failure() -> None:
    """Rewriting it as FAILED would put a reason code into evidence that nobody sent."""

    connections = ConnectionGenerations()
    generation = _drive_to(connections, *_PLAYABLE)
    connections.apply(generation, ConnectionSignal.DISCONNECTED)

    decision = connections.apply(generation, ConnectionSignal.FAILURE)

    assert decision.disposition is CallbackDisposition.OUT_OF_ORDER
    assert not decision.changed_state
    assert connections.active is not None
    assert connections.active.state is ConnectionState.DISCONNECTED


def test_a_kick_after_playable_is_a_failure_and_not_a_plain_disconnect() -> None:
    """Measured, not assumed: a server that ends a session sends its reason.

    A vanilla server kicks a client with a disconnect packet carrying
    `You logged in from another location` when the same name logs in again, and
    calling that a plain disconnect records a session the server ended as one
    that simply ended. §7's table already allows `PLAYABLE -> FAILED`; this is
    the connection machine catching up with it rather than the other way round.
    """

    connections = ConnectionGenerations()
    generation = _drive_to(connections, *_PLAYABLE)

    decision = connections.apply(generation, ConnectionSignal.FAILURE)

    assert decision.disposition is CallbackDisposition.FAILED
    assert decision.changed_state
    assert connections.active is not None
    assert connections.active.state is ConnectionState.FAILED


def test_a_failure_after_the_attempt_already_ended_is_still_out_of_order() -> None:
    connections = ConnectionGenerations()
    generation = _drive_to(connections, *_PLAYABLE)
    connections.apply(generation, ConnectionSignal.FAILURE)

    decision = connections.apply(generation, ConnectionSignal.FAILURE)

    assert decision.disposition is CallbackDisposition.OUT_OF_ORDER
    assert connections.active is not None
    assert connections.active.state is ConnectionState.FAILED


def test_a_disconnect_is_closed_explicitly_before_the_next_generation() -> None:
    connections = ConnectionGenerations()
    generation = _drive_to(connections, *_PLAYABLE)
    connections.apply(generation, ConnectionSignal.DISCONNECTED)

    closed = connections.close(generation)
    reconnected = connections.begin(PROFILE, REVISION)

    assert closed.disposition is CallbackDisposition.CLOSED
    assert closed.previous_state is ConnectionState.DISCONNECTED
    assert reconnected.generation == Generation(2)


def test_only_a_world_reached_counts_as_having_reached_a_world() -> None:
    """The distinction a deadline needs, and the one `in_flight` does not make.

    Every phase before PLAYABLE is still an attempt at one, and every phase after
    it is a session that has stopped being an attempt — so "still in flight" is
    true of both ends of that and the deadline cannot be asked of it.
    """

    connections = ConnectionGenerations()
    attempt = connections.begin(PROFILE, REVISION)
    assert connections.active is not None
    assert connections.active.reached_world is False

    for signal in (
        ConnectionSignal.RESOLUTION_STARTED,
        ConnectionSignal.ENDPOINT_ALLOWED,
        ConnectionSignal.LOGIN_ACCEPTED,
        ConnectionSignal.JOIN_OBSERVED,
    ):
        connections.apply(attempt.generation, signal)
        assert connections.active is not None
        assert connections.active.reached_world is False

    connections.apply(attempt.generation, ConnectionSignal.SNAPSHOT_ACCEPTED)
    assert connections.active is not None
    assert connections.active.reached_world is True
    # And it is still "in flight" by the other rule, which is exactly why the
    # deadline cannot use that one.
    assert connections.active.in_flight is True

    connections.apply(attempt.generation, ConnectionSignal.DISCONNECTED)
    assert connections.active is not None
    assert connections.active.reached_world is False
    assert connections.active.in_flight is False
