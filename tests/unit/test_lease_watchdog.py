from __future__ import annotations

from minekin_core.domain.ids import Generation
from minekin_core.domain.input_control import InputLease, InputPriority
from minekin_core.domain.lease_watchdog import LeaseWatchdog
from minekin_core.domain.time import MonotonicInstant

CAPABILITY = "control.move.v1"
START = MonotonicInstant(1_000_000)


def moment(offset_ns: int) -> MonotonicInstant:
    return MonotonicInstant(START.nanoseconds + offset_ns)


def lease(*, lease_id: str = "lease-1", term_ns: int = 5_000_000_000) -> InputLease:
    return InputLease(
        lease_id=lease_id,
        generation=Generation(1),
        client_instance_id="client-1",
        issued_monotonic_ns=START.nanoseconds,
        deadline_monotonic_ns=START.nanoseconds + term_ns,
        priority=InputPriority.NORMAL,
        capabilities=frozenset({CAPABILITY}),
    )


def test_a_watchdog_that_was_never_armed_never_lapses() -> None:
    """Nothing was authorised, so there is nothing whose term can run out."""

    watchdog = LeaseWatchdog()

    assert not watchdog.armed
    assert watchdog.current is None
    assert watchdog.lapsed(moment(60_000_000_000)) is None


def test_the_lease_lapses_at_its_deadline_and_not_before() -> None:
    watchdog = LeaseWatchdog()
    granted = lease(term_ns=5_000_000_000)
    watchdog.arm(granted)

    assert watchdog.armed
    assert watchdog.lapsed(moment(4_999_999_999)) is None
    # Exactly at the deadline is already over: the lease promised the time up to
    # that instant, and the instant itself belongs to the end of it.
    assert watchdog.lapsed(moment(5_000_000_000)) is granted
    assert not watchdog.armed


def test_a_lapse_is_reported_once_and_not_once_per_tick() -> None:
    """A caller that released on every tick would send a release per tick."""

    watchdog = LeaseWatchdog()
    watchdog.arm(lease(term_ns=1))

    assert watchdog.lapsed(moment(10)) is not None
    assert watchdog.lapsed(moment(20)) is None
    assert watchdog.lapsed(moment(30)) is None


def test_arming_a_new_lease_replaces_the_deadline_of_the_old_one() -> None:
    """Two leases cannot both be the one in force."""

    watchdog = LeaseWatchdog()
    watchdog.arm(lease(lease_id="short", term_ns=1))
    later = lease(lease_id="long", term_ns=60_000_000_000)
    watchdog.arm(later)

    # The replaced lease's deadline has long passed, and it must not end the one
    # that replaced it.
    assert watchdog.lapsed(moment(1_000)) is None
    assert watchdog.current is later
    assert watchdog.lapsed(moment(60_000_000_000)) is later


def test_a_disarmed_watchdog_forgets_the_lease_it_held() -> None:
    watchdog = LeaseWatchdog()
    watchdog.arm(lease(term_ns=1))
    watchdog.disarm()

    assert not watchdog.armed
    assert watchdog.current is None
    assert watchdog.lapsed(moment(10)) is None


def test_a_lapsed_lease_can_be_armed_again_only_by_arming_it() -> None:
    """Nothing re-arms a watchdog implicitly: a second hold is a second grant."""

    watchdog = LeaseWatchdog()
    first = lease(term_ns=1)
    watchdog.arm(first)
    assert watchdog.lapsed(moment(10)) is first
    assert watchdog.lapsed(moment(20)) is None

    watchdog.arm(lease(lease_id="second", term_ns=2))
    assert watchdog.lapsed(moment(30)) is not None
