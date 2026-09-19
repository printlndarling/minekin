from __future__ import annotations

import pytest

from minekin_core.adapters.bridge.admission import (
    AdmissionOutcome,
    LifecycleDisposition,
    apply_lifecycle,
)
from minekin_core.domain.connection import (
    CallbackDisposition,
    ConnectionGenerations,
    ConnectionState,
)
from minekin_core.domain.ids import Generation, OpaqueId
from minekin_core.generated.minekin.v1 import observation_pb2

PROFILE = OpaqueId("p0-controlled-offline-loopback")
REVISION = "a" * 64

RESOLVING = observation_pb2.CONNECTION_PHASE_RESOLVING
LOGIN_NEGOTIATING = observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING
PLAY_INIT = observation_pb2.CONNECTION_PHASE_PLAY_INIT
JOIN_SEEN = observation_pb2.CONNECTION_PHASE_JOIN_SEEN
PLAYABLE = observation_pb2.CONNECTION_PHASE_PLAYABLE
DISCONNECTED = observation_pb2.CONNECTION_PHASE_DISCONNECTED
FAILED = observation_pb2.CONNECTION_PHASE_FAILED

NO_REASON = observation_pb2.ADMISSION_FAILURE_REASON_UNSPECIFIED
WHITELIST_REJECTED = observation_pb2.ADMISSION_FAILURE_REASON_WHITELIST_REJECTED
DNS_FAILED = observation_pb2.ADMISSION_FAILURE_REASON_DNS_FAILED
CANCELLED_REASON = observation_pb2.ADMISSION_FAILURE_REASON_CANCELLED

PROGRESS = (RESOLVING, LOGIN_NEGOTIATING, PLAY_INIT, JOIN_SEEN, PLAYABLE)
TERMINAL_PHASES = (DISCONNECTED, FAILED, observation_pb2.CONNECTION_PHASE_CANCELLED)


def report(
    phase: observation_pb2.ConnectionPhase,
    *,
    generation: int = 1,
    reason: observation_pb2.AdmissionFailureReason = NO_REASON,
    terminal: bool | None = None,
    profile_id: str = str(PROFILE),
    revision: str = REVISION,
) -> observation_pb2.ConnectionLifecycle:
    return observation_pb2.ConnectionLifecycle(
        generation=generation,
        server_profile_id=profile_id,
        server_profile_revision=revision,
        phase=phase,
        failure_reason=reason,
        terminal=phase in TERMINAL_PHASES if terminal is None else terminal,
    )


def drive(
    connections: ConnectionGenerations, *phases: observation_pb2.ConnectionPhase
) -> list[AdmissionOutcome]:
    return [apply_lifecycle(connections, report(phase)) for phase in phases]


def test_the_reported_phases_are_what_make_an_attempt_playable() -> None:
    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcomes = drive(connections, *PROGRESS)

    assert [outcome.disposition for outcome in outcomes] == [LifecycleDisposition.APPLIED] * len(
        PROGRESS
    )
    assert [outcome.decision.disposition for outcome in outcomes if outcome.decision] == [
        CallbackDisposition.ADVANCED
    ] * len(PROGRESS)
    assert connections.active is not None
    assert connections.active.state is ConnectionState.PLAYABLE


def test_a_reason_is_carried_through_as_a_stable_token() -> None:
    """Core classifies on it, so the wire enum name is the classification."""

    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcome = apply_lifecycle(connections, report(FAILED, reason=WHITELIST_REJECTED))

    assert outcome.disposition is LifecycleDisposition.APPLIED
    assert outcome.decision is not None
    assert outcome.decision.disposition is CallbackDisposition.FAILED
    assert outcome.failure_reason == "ADMISSION_FAILURE_REASON_WHITELIST_REJECTED"
    assert connections.active is not None
    assert connections.active.state is ConnectionState.FAILED


def test_a_disconnect_is_applied_without_a_reason() -> None:
    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)
    drive(connections, *PROGRESS)

    outcome = apply_lifecycle(connections, report(DISCONNECTED))

    assert outcome.disposition is LifecycleDisposition.APPLIED
    assert outcome.failure_reason == ""
    assert connections.active is not None
    assert connections.active.state is ConnectionState.DISCONNECTED


def test_a_cancellation_closes_the_attempt_core_holds() -> None:
    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)
    drive(connections, RESOLVING)

    outcome = apply_lifecycle(connections, report(observation_pb2.CONNECTION_PHASE_CANCELLED))

    assert outcome.disposition is LifecycleDisposition.CLOSED
    assert outcome.decision is not None
    assert outcome.decision.disposition is CallbackDisposition.CLOSED
    assert connections.active is None


@pytest.mark.parametrize("phase", PROGRESS)
def test_a_report_about_another_profile_cannot_advance_this_attempt(
    phase: observation_pb2.ConnectionPhase,
) -> None:
    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)
    drive(connections, RESOLVING)

    outcome = apply_lifecycle(connections, report(phase, revision="b" * 64))

    assert outcome.disposition is LifecycleDisposition.FOREIGN_PROFILE
    assert outcome.decision is None
    assert connections.active is not None
    assert connections.active.state is ConnectionState.RESOLVING


@pytest.mark.parametrize(
    ("phase", "reason", "terminal"),
    [
        (FAILED, NO_REASON, True),
        (FAILED, CANCELLED_REASON, True),
        (RESOLVING, DNS_FAILED, False),
        (DISCONNECTED, DNS_FAILED, True),
        (RESOLVING, NO_REASON, True),
        (FAILED, WHITELIST_REJECTED, False),
        (observation_pb2.CONNECTION_PHASE_CANCELLED, DNS_FAILED, True),
        (observation_pb2.CONNECTION_PHASE_CANCELLED, CANCELLED_REASON, False),
    ],
)
def test_a_report_whose_parts_disagree_is_refused(
    phase: observation_pb2.ConnectionPhase,
    reason: observation_pb2.AdmissionFailureReason,
    terminal: bool,
) -> None:
    """Refused, not repaired: an unreadable report has no classification."""

    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcome = apply_lifecycle(connections, report(phase, reason=reason, terminal=terminal))

    assert outcome.disposition is LifecycleDisposition.MISPAIRED_REASON
    assert outcome.decision is None
    assert connections.active is not None
    assert connections.active.state is ConnectionState.REQUEST_ACCEPTED


def test_an_unspecified_phase_is_not_a_phase() -> None:
    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcome = apply_lifecycle(connections, report(observation_pb2.CONNECTION_PHASE_UNSPECIFIED))

    assert outcome.disposition is LifecycleDisposition.UNKNOWN_PHASE
    assert outcome.decision is None
    assert connections.active is not None
    assert connections.active.state is ConnectionState.REQUEST_ACCEPTED


def test_a_generation_that_is_not_a_positive_uint64_is_refused() -> None:
    """The Bridge refuses generation 0 too; a peer that sends it must not crash Core."""

    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcome = apply_lifecycle(connections, report(RESOLVING, generation=0))

    assert outcome.disposition is LifecycleDisposition.INVALID_GENERATION
    assert outcome.decision is None
    assert connections.active is not None
    assert connections.active.state is ConnectionState.REQUEST_ACCEPTED


def test_a_report_with_no_attempt_to_bind_to_is_not_applied() -> None:
    connections = ConnectionGenerations()

    outcome = apply_lifecycle(connections, report(RESOLVING))

    assert outcome.disposition is LifecycleDisposition.UNBOUND
    assert outcome.decision is None


def test_a_late_report_from_the_previous_generation_cannot_move_the_new_one() -> None:
    """The reconnect rule, end to end: the old generation reports into a new attempt."""

    connections = ConnectionGenerations()
    first = connections.begin(PROFILE, REVISION)
    drive(connections, RESOLVING)
    apply_lifecycle(connections, report(observation_pb2.CONNECTION_PHASE_CANCELLED))
    second = connections.begin(PROFILE, REVISION)

    late = apply_lifecycle(connections, report(JOIN_SEEN, generation=int(first.generation)))

    assert second.generation == Generation(2)
    assert late.disposition is LifecycleDisposition.APPLIED
    assert late.decision is not None
    assert late.decision.disposition is CallbackDisposition.STALE_GENERATION
    assert not late.decision.changed_state
    assert connections.active is not None
    assert connections.active.state is ConnectionState.REQUEST_ACCEPTED
