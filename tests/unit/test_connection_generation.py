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
