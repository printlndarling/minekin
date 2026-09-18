from __future__ import annotations

import pytest

from minekin_core.domain.ids import Generation
from minekin_core.domain.input_control import (
    InputArbiter,
    InputLease,
    InputPriority,
    InputRefusal,
    InputRequest,
    ReleaseReason,
)
from minekin_core.domain.time import MonotonicInstant

LOOK = "control.look.v1"
MOVE = "control.move.v1"
CLIENT = "client-01"
LEASE_ID = "lease-01"

ISSUED = MonotonicInstant(1_000)
DEADLINE = MonotonicInstant(10_000)


def started(*, playable: bool = True, generation: int = 1) -> InputArbiter:
    arbiter = InputArbiter(Generation(generation))
    arbiter.set_playable(playable)
    return arbiter


def lease(
    *,
    lease_id: str = LEASE_ID,
    generation: int = 1,
    priority: InputPriority = InputPriority.NORMAL,
    capabilities: frozenset[str] = frozenset({LOOK, MOVE}),
    deadline_ns: int = DEADLINE.nanoseconds,
) -> InputLease:
    return InputLease(
        lease_id=lease_id,
        generation=Generation(generation),
        client_instance_id=CLIENT,
        issued_monotonic_ns=ISSUED.nanoseconds,
        deadline_monotonic_ns=deadline_ns,
        priority=priority,
        capabilities=capabilities,
    )


def request(
    *,
    lease_id: str = LEASE_ID,
    generation: int = 1,
    capability: str = LOOK,
    deadline_ns: int = DEADLINE.nanoseconds,
) -> InputRequest:
    return InputRequest(
        lease_id=lease_id,
        generation=Generation(generation),
        capability=capability,
        deadline_monotonic_ns=deadline_ns,
    )


def granted(**kwargs: object) -> InputArbiter:
    arbiter = started()
    assert arbiter.grant(lease(**kwargs)).accepted  # type: ignore[arg-type]
    return arbiter


def test_a_request_under_a_granted_lease_is_authorised() -> None:
    arbiter = granted()

    decision = arbiter.decide(request(), now=ISSUED)

    assert decision.accepted
    assert decision.refusals == ()
    assert decision.as_document() == {"accepted": True, "refusals": []}


def test_without_a_lease_nothing_is_authorised() -> None:
    arbiter = started()

    decision = arbiter.decide(request(), now=ISSUED)

    assert decision.refusals == (InputRefusal.NO_LEASE,)


def test_a_lease_expires_at_its_deadline() -> None:
    arbiter = granted()

    beyond = DEADLINE.nanoseconds + 1_000
    assert arbiter.decide(
        request(deadline_ns=beyond), now=MonotonicInstant(DEADLINE.nanoseconds - 1)
    ).accepted
    assert arbiter.decide(request(deadline_ns=beyond), now=DEADLINE).refusals == (
        InputRefusal.LEASE_EXPIRED,
    )


def test_an_action_that_outlived_its_own_deadline_is_refused() -> None:
    arbiter = granted()

    decision = arbiter.decide(request(deadline_ns=500), now=ISSUED)

    assert decision.refusals == (InputRefusal.REQUEST_DEADLINE_PASSED,)


def test_a_capability_the_lease_does_not_cover_is_refused() -> None:
    arbiter = granted(capabilities=frozenset({LOOK}))

    assert arbiter.decide(request(capability=LOOK), now=ISSUED).accepted
    assert arbiter.decide(request(capability=MOVE), now=ISSUED).refusals == (
        InputRefusal.CAPABILITY_NOT_LEASED,
    )


def test_a_new_generation_ends_the_lease_it_replaced() -> None:
    """A lease belongs to one connection, so a new one starts with no authorisation."""

    arbiter = granted()

    arbiter.begin_connection()

    assert arbiter.current is None
    assert arbiter.decide(request(generation=2), now=ISSUED).refusals == (InputRefusal.NO_LEASE,)


def test_an_action_claiming_another_generation_is_refused() -> None:
    arbiter = granted()

    decision = arbiter.decide(request(generation=2), now=ISSUED)

    assert decision.refusals == (InputRefusal.GENERATION_MISMATCH,)


def test_a_lease_for_another_generation_cannot_be_granted() -> None:
    arbiter = started(generation=2)

    decision = arbiter.grant(lease(generation=1))

    assert decision.refusals == (InputRefusal.GENERATION_MISMATCH,)
    assert arbiter.current is None


def test_leaving_playable_ends_the_lease() -> None:
    arbiter = granted()

    outcome = arbiter.set_playable(False)

    assert outcome is not None
    assert outcome.reason is ReleaseReason.PHASE_LEFT_PLAYABLE
    assert outcome.had_lease
    assert arbiter.current is None
    assert arbiter.decide(request(), now=ISSUED).refusals == (InputRefusal.NO_LEASE,)


def test_a_lease_cannot_be_granted_outside_playable() -> None:
    arbiter = started(playable=False)

    decision = arbiter.grant(lease())

    assert decision.refusals == (InputRefusal.NOT_PLAYABLE,)


def test_a_late_action_from_a_replaced_lease_is_diagnostic_only() -> None:
    arbiter = granted()
    arbiter.withdraw(ReleaseReason.SUPERSEDED)
    assert arbiter.grant(lease(lease_id="lease-02")).accepted

    decision = arbiter.decide(request(lease_id=LEASE_ID), now=ISSUED)

    assert InputRefusal.LEASE_SUPERSEDED in decision.refusals


def test_one_input_owner_at_a_time() -> None:
    arbiter = granted()

    decision = arbiter.grant(lease(lease_id="lease-02"))

    assert decision.refusals == (InputRefusal.LEASE_ACTIVE,)
    assert arbiter.current is not None
    assert arbiter.current.lease_id == LEASE_ID


def test_a_more_important_holder_takes_the_input_away() -> None:
    """The reflex path must be able to preempt a task that is holding the input."""

    arbiter = granted()

    decision = arbiter.grant(lease(lease_id="lease-urgent", priority=InputPriority.EMERGENCY))

    assert decision.accepted
    assert arbiter.current is not None
    assert arbiter.current.lease_id == "lease-urgent"
    assert arbiter.current.priority is InputPriority.EMERGENCY


def test_an_equal_priority_does_not_preempt() -> None:
    arbiter = granted()

    assert arbiter.grant(lease(lease_id="lease-02", priority=InputPriority.NORMAL)).refusals == (
        InputRefusal.LEASE_ACTIVE,
    )


def test_regranting_the_same_lease_is_not_a_conflict() -> None:
    arbiter = granted()

    assert arbiter.grant(lease()).accepted


def test_every_release_reason_leaves_no_lease_behind() -> None:
    """The invariant the whole module exists for: nothing is left holding input."""

    for reason in ReleaseReason:
        arbiter = granted()

        outcome = arbiter.withdraw(reason)

        assert arbiter.current is None, reason
        assert outcome.reason is reason
        assert outcome.had_lease
        assert arbiter.decide(request(), now=ISSUED).refusals == (InputRefusal.NO_LEASE,), reason


def test_withdrawing_twice_is_harmless() -> None:
    arbiter = granted()
    arbiter.withdraw(ReleaseReason.IPC_LOST)

    second = arbiter.withdraw(ReleaseReason.IPC_LOST)

    assert not second.had_lease
    assert arbiter.current is None


def test_withdrawing_without_a_lease_still_reports_a_release() -> None:
    """The Bridge must release keys whether or not Core believed it held any."""

    arbiter = started()

    outcome = arbiter.withdraw(ReleaseReason.TIMEOUT)

    assert outcome.had_lease is False
    assert outcome.generation == Generation(1)
    assert outcome.as_document() == {"generation": 1, "reason": "TIMEOUT", "had_lease": False}


def test_a_generation_is_never_reused() -> None:
    arbiter = started()

    seen = [int(arbiter.generation)]
    for _ in range(5):
        seen.append(int(arbiter.begin_connection()))

    assert seen == [1, 2, 3, 4, 5, 6]
    assert len(set(seen)) == len(seen)


def test_beginning_a_connection_also_leaves_playable() -> None:
    arbiter = granted()

    arbiter.begin_connection()

    assert not arbiter.playable
    assert arbiter.grant(lease(generation=2)).refusals == (InputRefusal.NOT_PLAYABLE,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lease_id", ""),
        ("client_instance_id", ""),
        ("capabilities", frozenset[str]()),
        ("deadline_monotonic_ns", ISSUED.nanoseconds),
    ],
)
def test_an_unusable_lease_cannot_be_constructed(field: str, value: object) -> None:
    arguments: dict[str, object] = {
        "lease_id": LEASE_ID,
        "generation": Generation(1),
        "client_instance_id": CLIENT,
        "issued_monotonic_ns": ISSUED.nanoseconds,
        "deadline_monotonic_ns": DEADLINE.nanoseconds,
        "priority": InputPriority.NORMAL,
        "capabilities": frozenset({LOOK}),
    }
    arguments[field] = value

    with pytest.raises(ValueError):
        InputLease(**arguments)  # type: ignore[arg-type]


def test_the_release_document_is_evidence_ready() -> None:
    arbiter = granted()

    outcome = arbiter.withdraw(ReleaseReason.CLIENT_DIED)

    assert outcome.as_document() == {
        "generation": 1,
        "reason": "CLIENT_DIED",
        "had_lease": True,
    }


def test_several_reasons_are_collected_in_a_stable_order() -> None:
    """One refusal should explain the whole situation, not just its first cause."""

    arbiter = started()
    assert arbiter.grant(lease(capabilities=frozenset({LOOK}))).accepted

    decision = arbiter.decide(
        request(lease_id="other", capability=MOVE, deadline_ns=500),
        now=MonotonicInstant(20_000),
    )

    assert decision.refusals == tuple(sorted(decision.refusals))
    assert set(decision.refusals) == {
        InputRefusal.LEASE_SUPERSEDED,
        InputRefusal.LEASE_EXPIRED,
        InputRefusal.CAPABILITY_NOT_LEASED,
        InputRefusal.REQUEST_DEADLINE_PASSED,
    }
