from __future__ import annotations

import pytest

from minekin_core.domain.control_watchdog import (
    DEFAULT_TOLERATED_MISSES,
    ControlHeartbeat,
    ControlWatchdog,
)
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
INTERVAL_MS = 500
TOLERANCE_NS = INTERVAL_MS * 1_000_000 * DEFAULT_TOLERATED_MISSES

START = MonotonicInstant(1_000_000)


def moment(offset_ns: int) -> MonotonicInstant:
    return MonotonicInstant(START.nanoseconds + offset_ns)


def watchdog(generation: int = 1, *, interval_ms: int = INTERVAL_MS) -> ControlWatchdog:
    control = ControlWatchdog(interval_ms)
    control.arm(Generation(generation), START)
    return control


def test_an_unarmed_watchdog_never_expires_and_ignores_heartbeats() -> None:
    control = ControlWatchdog(INTERVAL_MS)

    assert not control.armed
    assert not control.has_expired(moment(10_000_000_000))
    assert not control.observe(ControlHeartbeat(Generation(1), START.nanoseconds))


def test_arming_starts_the_clock_before_any_heartbeat() -> None:
    """A Bridge that dies during startup never sends one, and must still be missed."""

    control = watchdog()

    assert control.armed
    assert control.deadline_ns() == START.nanoseconds + TOLERANCE_NS
    assert not control.has_expired(moment(TOLERANCE_NS - 1))
    assert control.has_expired(moment(TOLERANCE_NS))


def test_a_heartbeat_pushes_the_deadline_out_by_the_tolerance() -> None:
    control = watchdog()
    beat = moment(400_000_000)

    assert control.observe(ControlHeartbeat(Generation(1), beat.nanoseconds))

    assert control.deadline_ns() == beat.nanoseconds + TOLERANCE_NS
    assert not control.has_expired(moment(400_000_000 + TOLERANCE_NS - 1))


def test_a_heartbeat_from_another_generation_neither_counts_nor_extends() -> None:
    """Otherwise a closed connection's packets would keep the new one looking alive."""

    control = watchdog(generation=2)
    before = control.deadline_ns()

    assert not control.observe(ControlHeartbeat(Generation(1), moment(10_000_000_000).nanoseconds))

    assert control.deadline_ns() == before
    assert control.has_expired(moment(TOLERANCE_NS))


def test_a_reordered_heartbeat_is_not_new_information() -> None:
    control = watchdog()
    control.observe(ControlHeartbeat(Generation(1), moment(500_000_000).nanoseconds))

    assert not control.observe(ControlHeartbeat(Generation(1), moment(100_000_000).nanoseconds))
    assert control.deadline_ns() == moment(500_000_000).nanoseconds + TOLERANCE_NS


def test_disarming_stops_watching() -> None:
    control = watchdog()
    control.disarm()

    assert not control.armed
    assert not control.has_expired(moment(10_000_000_000))
    assert not control.observe(ControlHeartbeat(Generation(1), moment(1).nanoseconds))


def test_a_steady_bridge_never_expires() -> None:
    control = watchdog()
    now_ns = 0
    for _ in range(20):
        now_ns += INTERVAL_MS * 1_000_000
        control.observe(ControlHeartbeat(Generation(1), now_ns))
        assert not control.has_expired(MonotonicInstant(START.nanoseconds + now_ns))


@pytest.mark.parametrize("interval_ms", [0, -1])
def test_a_useless_interval_is_refused(interval_ms: int) -> None:
    with pytest.raises(ValueError, match="interval"):
        ControlWatchdog(interval_ms)


def test_tolerating_no_misses_is_refused() -> None:
    with pytest.raises(ValueError, match="tolerated"):
        ControlWatchdog(INTERVAL_MS, tolerated_misses=0)


def test_a_longer_tolerance_survives_a_longer_gap() -> None:
    patient = ControlWatchdog(INTERVAL_MS, tolerated_misses=10)
    patient.arm(Generation(1), START)

    assert not patient.has_expired(moment(TOLERANCE_NS))
    assert patient.has_expired(moment(INTERVAL_MS * 1_000_000 * 10))


# --- the two layers together ---------------------------------------------------


def granted_arbiter() -> InputArbiter:
    arbiter = InputArbiter(Generation(1))
    arbiter.set_playable(True)
    lease = InputLease(
        lease_id="lease-01",
        generation=Generation(1),
        client_instance_id="client-01",
        issued_monotonic_ns=START.nanoseconds,
        deadline_monotonic_ns=START.nanoseconds + 60_000_000_000,
        priority=InputPriority.NORMAL,
        capabilities=frozenset({LOOK}),
    )
    assert arbiter.grant(lease).accepted
    return arbiter


def look_request() -> InputRequest:
    return InputRequest(
        lease_id="lease-01",
        generation=Generation(1),
        capability=LOOK,
        deadline_monotonic_ns=START.nanoseconds + 60_000_000_000,
    )


def test_a_silent_bridge_leaves_nothing_authorised() -> None:
    """The composition the second layer exists for: silence stops the input."""

    arbiter = granted_arbiter()
    control = watchdog()
    assert arbiter.decide(look_request(), now=moment(1_000_000)).accepted

    silent_since = moment(TOLERANCE_NS + 1)
    assert control.has_expired(silent_since)

    arbiter.withdraw(ReleaseReason.TIMEOUT)

    assert arbiter.current is None
    assert arbiter.decide(look_request(), now=silent_since).refusals == (InputRefusal.NO_LEASE,)


def test_a_bridge_that_keeps_talking_leaves_control_where_it_was() -> None:
    """The watchdog must not revoke a lease for a Bridge that is answering."""

    arbiter = granted_arbiter()
    control = watchdog()
    now = moment(INTERVAL_MS * 1_000_000)
    control.observe(ControlHeartbeat(Generation(1), now.nanoseconds))

    assert not control.has_expired(now)
    assert arbiter.decide(look_request(), now=now).accepted
