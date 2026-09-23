from __future__ import annotations

import pytest

from minekin_core.adapters.bridge.admission import (
    AdmissionOutcome,
    LifecycleDisposition,
    accept_snapshot,
    apply_lifecycle,
)
from minekin_core.domain.connection import (
    CallbackDisposition,
    ConnectionGenerations,
    ConnectionState,
)
from minekin_core.domain.ids import Generation, OpaqueId
from minekin_core.generated.minekin.v1 import control_pb2, observation_pb2

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
CONNECTION_REFUSED = observation_pb2.ADMISSION_FAILURE_REASON_CONNECTION_REFUSED
CANCELLED_REASON = observation_pb2.ADMISSION_FAILURE_REASON_CANCELLED

#: The reasons whose necessary action, in the admission contract's table, is "no
#: connection is created" — the parse/resolve stage. A refusal can never be one of
#: them, so the test below holds the classification against this set rather than
#: only against its own name.
NO_CONNECTION_CREATED = frozenset(
    {
        observation_pb2.ADMISSION_FAILURE_REASON_ADDRESS_INVALID,
        DNS_FAILED,
        observation_pb2.ADMISSION_FAILURE_REASON_ADDRESS_POLICY_BLOCKED,
    }
)

# The phases the Bridge reports. PLAYABLE is deliberately not one of them:
# it is Core's conclusion about a snapshot it admitted, not a phase a Bridge
# can announce.
PROGRESS = (RESOLVING, LOGIN_NEGOTIATING, PLAY_INIT, JOIN_SEEN)
TERMINAL_PHASES = (DISCONNECTED, FAILED, observation_pb2.CONNECTION_PHASE_CANCELLED)


def report(
    phase: int,
    *,
    generation: int = 1,
    reason: int = NO_REASON,
    terminal: bool | None = None,
    profile_id: str = str(PROFILE),
    revision: str = REVISION,
    policy: int = control_pb2.RESOURCE_PACK_POLICY_UNSPECIFIED,
) -> observation_pb2.ConnectionLifecycle:
    return observation_pb2.ConnectionLifecycle(
        generation=generation,
        server_profile_id=profile_id,
        server_profile_revision=revision,
        phase=phase,  # type: ignore[arg-type]
        failure_reason=reason,  # type: ignore[arg-type]
        terminal=phase in TERMINAL_PHASES if terminal is None else terminal,
        applied_resource_pack_policy=policy,  # type: ignore[arg-type]
    )


def drive(
    connections: ConnectionGenerations, *phases: observation_pb2.ConnectionPhase
) -> list[AdmissionOutcome]:
    return [apply_lifecycle(connections, report(phase)) for phase in phases]


def test_the_reported_phases_are_what_make_an_attempt_join() -> None:
    connections = ConnectionGenerations()
    attempt = connections.begin(PROFILE, REVISION)

    outcomes = drive(connections, *PROGRESS)

    assert [outcome.disposition for outcome in outcomes] == [LifecycleDisposition.APPLIED] * len(
        PROGRESS
    )
    assert [outcome.decision.disposition for outcome in outcomes if outcome.decision] == [
        CallbackDisposition.ADVANCED
    ] * len(PROGRESS)
    assert connections.active is not None
    assert connections.active.state is ConnectionState.JOIN_SEEN

    # And only the Runtime's own acceptance of a snapshot carries it further.
    decision = accept_snapshot(connections, attempt.generation)

    assert decision.disposition is CallbackDisposition.ADVANCED
    assert connections.active.state is ConnectionState.PLAYABLE


def test_a_bridge_claiming_playable_is_not_evidence_of_a_snapshot() -> None:
    """The contract puts the acceptance with the Runtime, so this is withheld.

    A Bridge that could mark itself playable would admit a session no snapshot
    was ever checked for, which is the one thing the snapshot boundary exists to
    prevent.
    """

    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)
    drive(connections, *PROGRESS)

    outcome = apply_lifecycle(connections, report(PLAYABLE))

    assert outcome.disposition is LifecycleDisposition.WITHHELD
    assert outcome.decision is None
    assert connections.active is not None
    assert connections.active.state is ConnectionState.JOIN_SEEN


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


def test_a_refused_connection_is_a_tcp_stage_failure_and_not_a_resolve_one() -> None:
    """The one failure class this repository can produce locally, end to end.

    Every other reason in the table needs a server or a resolver to happen at all,
    but a refusal is what a loopback port with nothing listening produces — and it
    is the class whose token was wrong until it was given its own value. The
    assertion is written against the contract's own stage list, so it fails if the
    refusal is ever filed back under a reason that means "no connection was
    created": a refusal is what came back from a connection that was made.
    """

    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcome = apply_lifecycle(connections, report(FAILED, reason=CONNECTION_REFUSED))

    assert outcome.disposition is LifecycleDisposition.APPLIED
    assert outcome.decision is not None
    assert outcome.decision.disposition is CallbackDisposition.FAILED
    assert outcome.failure_reason == "ADMISSION_FAILURE_REASON_CONNECTION_REFUSED"
    assert CONNECTION_REFUSED not in NO_CONNECTION_CREATED


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


def test_an_unknown_wire_phase_is_rejected_before_state_changes() -> None:
    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcome = apply_lifecycle(connections, report(123_456))

    assert outcome.disposition is LifecycleDisposition.UNKNOWN_PHASE
    assert outcome.decision is None
    assert connections.active is not None
    assert connections.active.state is ConnectionState.REQUEST_ACCEPTED


def test_an_unknown_wire_reason_is_rejected_before_state_changes() -> None:
    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcome = apply_lifecycle(connections, report(FAILED, reason=123_456))

    assert outcome.disposition is LifecycleDisposition.UNKNOWN_REASON
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


@pytest.mark.parametrize(
    ("wire_policy", "token"),
    [
        (control_pb2.RESOURCE_PACK_POLICY_DENY, "deny"),
        (control_pb2.RESOURCE_PACK_POLICY_PROMPT, "prompt"),
    ],
)
def test_a_named_resource_pack_policy_is_carried_through_as_a_stable_token(
    wire_policy: int,
    token: str,
) -> None:
    """The policy reaches Core as the ledger's own spelling, not as a re-derivation.

    `deny` and `prompt` are the two tokens a trusted Server Profile uses, so the
    judge can compare the profile it sealed with the fact this run reported
    without a third vocabulary that could drift from both.
    """

    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcome = apply_lifecycle(connections, report(RESOLVING, policy=wire_policy))

    assert outcome.disposition is LifecycleDisposition.APPLIED
    assert outcome.resource_pack_policy == token


def test_a_report_that_names_no_resource_pack_policy_says_nothing_about_one() -> None:
    """The absent case is a phase that did not create a connection, not "deny".

    Every phase after the first names nothing, and a Bridge from before this
    field existed names nothing at all. Reading either as a policy would put a
    fact about the client's connection in the ledger that nobody reported.
    """

    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    unnamed = apply_lifecycle(connections, report(LOGIN_NEGOTIATING))

    assert unnamed.disposition is LifecycleDisposition.APPLIED
    assert unnamed.resource_pack_policy == ""


def test_a_resource_pack_policy_is_carried_by_every_report_that_names_one() -> None:
    """No dedupe here: two reports that name a policy are two facts.

    An attempt normally names its policy once, but a run that reported two
    different values must show both rather than keep whichever Core saw first.
    Deciding what a pair of values means is the reader's job; silently merging
    them would be Core's opinion.
    """

    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    first = apply_lifecycle(
        connections, report(RESOLVING, policy=control_pb2.RESOURCE_PACK_POLICY_DENY)
    )
    second = apply_lifecycle(
        connections, report(LOGIN_NEGOTIATING, policy=control_pb2.RESOURCE_PACK_POLICY_PROMPT)
    )

    assert first.resource_pack_policy == "deny"
    assert second.resource_pack_policy == "prompt"


def test_an_unknown_resource_pack_policy_is_rejected_before_state_changes() -> None:
    """A report this build cannot read in one part is not readable in the others."""

    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)

    outcome = apply_lifecycle(connections, report(RESOLVING, policy=123_456))

    assert outcome.disposition is LifecycleDisposition.UNKNOWN_POLICY
    assert outcome.decision is None
    assert outcome.resource_pack_policy == ""
    assert connections.active is not None
    assert connections.active.state is ConnectionState.REQUEST_ACCEPTED
