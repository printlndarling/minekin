"""Which of two locks a hosted world needs before a server may start against it.

The storage contract asks for both a supervisor lease and the vanilla session lock,
and HOST-010 is the race they exist to settle: two starts for one world, one winner.
The tests below are about the ways that race can be lost honestly and the ways it can
be lost by guessing — which is the whole content of the rule, because neither lock
can be read as a boolean.

Two of them are about the difference between "no" and "nobody checked": a lease
whose owner could not be confirmed gone is not reclaimed, and a lock file that could
not be read is not a free lock. Those are the two refusals that look like caution and
are actually the contract's own words — confirm before reclaiming, and never treat a
leftover `session.lock` as evidence either way.
"""

from __future__ import annotations

import pytest

from minekin_core.domain.ids import Generation, SessionId
from minekin_core.domain.world_locking import (
    LockObservation,
    LockRefusal,
    SupervisorLease,
    admit_locking,
)

WORLD = "hosted-world-1"


def lease(**overrides: object) -> SupervisorLease:
    baseline: dict[str, object] = {
        "kin_id": "kin-1",
        "hosted_world_id": WORLD,
        "session_id": SessionId("session-1"),
        "generation": Generation(1),
        "pid": 4242,
        "started_ticks": 987654,
        "bundle_id": "p0-core-1.21.4",
    }
    baseline.update(overrides)
    return SupervisorLease(**baseline)  # type: ignore[arg-type]


def lock(
    *,
    found: SupervisorLease | None = None,
    observed: LockObservation = LockObservation.FREE,
    owner_is_running: bool | None = None,
    session_lock: LockObservation = LockObservation.FREE,
):
    return admit_locking(
        lease=found,
        lease_observation=observed,
        owner_is_running=owner_is_running,
        session_lock=session_lock,
    )


# ---------------------------------------------------------------------------
# HOST-010: the race
# ---------------------------------------------------------------------------


def test_a_second_run_is_refused_while_the_first_is_alive() -> None:
    """HOST-010's own outcome: one side of the race gets `WORLD_IN_USE`.

    The refusal names the holder, because "the world is in use" without saying by
    which session leaves an operator with nothing to look up.
    """

    decision = lock(
        found=lease(),
        observed=LockObservation.HELD,
        owner_is_running=True,
        session_lock=LockObservation.FREE,
    )

    assert decision.admitted is False
    assert decision.refusal is LockRefusal.WORLD_IN_USE
    assert "session-1" in decision.detail and "4242" in decision.detail


def test_a_save_open_in_another_process_is_refused() -> None:
    """The other lock, and the reason both are held: it is a different question.

    Nobody holds the lease here, and the world still may not start — a Minecraft
    that is not Minekin has the save open, which the lease knows nothing about.
    """

    decision = lock(observed=LockObservation.FREE, session_lock=LockObservation.HELD)

    assert decision.admitted is False
    assert decision.refusal is LockRefusal.SESSION_LOCK_HELD


def test_a_world_nobody_holds_is_locked_without_reclaiming() -> None:
    """The ordinary path, and it is a different fact from a reclaim."""

    decision = lock()

    assert decision.admitted is True
    assert decision.reclaimed is False
    assert decision.as_document() == {
        "admitted": True,
        "reclaimed": False,
        "refusal": None,
        "detail": "",
    }


def test_a_lease_whose_owner_is_gone_is_reclaimed_rather_than_refused() -> None:
    """The recovery path the contract describes, and it says so on the decision.

    "We took over a dead session's world" and "we opened a world nobody had" are
    different facts about a run, and the difference is only knowable here.
    """

    decision = lock(
        found=lease(),
        observed=LockObservation.HELD,
        owner_is_running=False,
        session_lock=LockObservation.FREE,
    )

    assert decision.admitted is True
    assert decision.reclaimed is True
    assert str(decision) == "RECLAIMED"


@pytest.mark.parametrize("observed", [LockObservation.HELD, LockObservation.FREE])
def test_a_lease_whose_owner_could_not_be_checked_is_not_reclaimed(
    observed: LockObservation,
) -> None:
    """The confirm-first rule, and it holds even when the lease looks expired.

    An expired-looking lease whose process is still there is exactly the state a
    half-dead run leaves, and starting a second server against it is what the two
    locks exist to prevent.
    """

    decision = lock(found=lease(), observed=observed, owner_is_running=None)

    assert decision.admitted is False
    assert decision.refusal is LockRefusal.LEASE_OWNER_UNKNOWN


def test_a_lease_that_could_not_be_read_is_not_a_reason_to_start() -> None:
    """An unreadable lease is its own finding, not the owner's."""

    decision = lock(observed=LockObservation.UNKNOWN, owner_is_running=None)

    assert decision.admitted is False
    assert decision.refusal is LockRefusal.LEASE_UNREADABLE


def test_a_lease_reported_held_with_no_record_behind_it_is_not_a_reason_to_start() -> None:
    """Held, and nothing to check it against: the same answer, and the same reason."""

    decision = lock(found=None, observed=LockObservation.HELD, owner_is_running=None)

    assert decision.admitted is False
    assert decision.refusal is LockRefusal.LEASE_UNREADABLE


def test_a_lock_file_that_cannot_be_read_is_not_a_free_lock() -> None:
    """The contract's two sentences about `session.lock`, as one refusal.

    A leftover file is not proof that a process is alive, and it is not proof that
    none is. Both of those are the same statement about what a file can show, and
    the answer to "the lock could not be read" is to stop rather than to start on a
    guess — reading `UNKNOWN` as free is how one save ends up open in two processes.
    """

    unknown = lock(session_lock=LockObservation.UNKNOWN)
    free = lock(session_lock=LockObservation.FREE)

    assert unknown.admitted is False
    assert unknown.refusal is LockRefusal.SESSION_LOCK_UNKNOWN
    assert free.admitted is True, "the two are different answers, which is the point"


def test_a_lease_records_the_world_it_holds_and_who_holds_it() -> None:
    """The contract's fields, including the key being the pair rather than one of it."""

    document = lease().as_document()

    assert document == {
        "kin_id": "kin-1",
        "hosted_world_id": WORLD,
        "session_id": "session-1",
        "generation": 1,
        "pid": 4242,
        "started_ticks": 987654,
        "bundle_id": "p0-core-1.21.4",
    }
    assert lease(hosted_world_id="hosted-world-2") != lease()
    assert lease(kin_id="kin-2") != lease()
