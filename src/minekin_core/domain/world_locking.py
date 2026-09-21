"""Which of two locks a hosted world needs, and when neither may be taken.

The storage contract's "double single-writer" section: a world holds a Minekin
supervisor lease *and* the vanilla `LevelStorage.Session` lock, and either one
failing means the world may not start. They answer different questions — the lease
is "has Minekin already started a session for this world", the vanilla lock is "is
the save open by some other process" — so a rule that only asked one of them would
be a rule about half of the ways two processes can end up in one world.

Three things the contract says are rules here rather than prose:

- A second instance gets `WORLD_IN_USE`, and only one side enters CREATING or
  LOADING. The state machine's `PREPARED -> LOCKED` edge takes the *word*
  `SUPERVISOR_AND_LOCK`; this is what decides whether that word is true, which is
  the same division the rest of this repository uses between a report and a reader
  that checks it.
- A lease is reclaimable only once the old owner is *confirmed* gone. "The process
  is not there any more" and "nobody could tell whether it is" are different
  findings: the first is the recovery path the contract describes, and the second
  is not a reason to start — it is the reason the contract says to confirm first.
- Seeing a `session.lock` file is not knowing that the lock is held. The contract
  refuses to call a leftover file proof that a process is alive, and it forbids
  deleting one on sight; so the vanilla lock's state is an *observation* here, with
  `UNKNOWN` as a value rather than as a false negative.

What is not here: which process the lease names, and whether it is still running.
That belongs to the launcher, which owns process identity — the same split the
recovery policy already draws for a pending effect — so this module is handed the
observation rather than making it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from minekin_core.domain.ids import Generation, SessionId


class LockObservation(StrEnum):
    """What was observed about one of the two locks."""

    #: Held by something. For the lease that is another run; for the vanilla lock it
    #: is another process with the save open.
    HELD = "HELD"
    #: Free: the lease is absent or expired, or the vanilla lock is acquirable.
    FREE = "FREE"
    #: Nobody could tell. A leftover `session.lock` file is this, not `HELD`: the
    #: contract says a file proves nothing about whether a process is alive.
    UNKNOWN = "UNKNOWN"


class LockRefusal(StrEnum):
    """Why a world may not be locked by this run. One reason each."""

    #: Another run holds the lease and its owner is alive. The contract names this
    #: outcome; it is the answer a losing instance of a start race reports.
    WORLD_IN_USE = "WORLD_IN_USE"
    #: The lease itself could not be read, or is reported as held with no record
    #: behind it. Nothing can be checked against it, which is not the same finding as
    #: a lease whose owner could not be checked.
    LEASE_UNREADABLE = "LEASE_UNREADABLE"
    #: Another run holds the lease and whether its owner is still running could not
    #: be established. Not a reason to start, and not a reason to reclaim either.
    LEASE_OWNER_UNKNOWN = "LEASE_OWNER_UNKNOWN"
    #: The vanilla lock is held, so the save is open somewhere else.
    SESSION_LOCK_HELD = "SESSION_LOCK_HELD"
    #: The vanilla lock could not be read. Fail closed rather than assume it is
    #: free, because assuming that is what opens one save in two processes.
    SESSION_LOCK_UNKNOWN = "SESSION_LOCK_UNKNOWN"


@dataclass(frozen=True, slots=True)
class SupervisorLease:
    """What a lease records, as the contract lists it.

    The key is the pair: a lease is about one world of one Kin, so a record that
    named only the world would let two Kins' worlds be confused for one, and one
    that named only the Kin would let two of its worlds be.
    """

    kin_id: str
    hosted_world_id: str
    session_id: SessionId
    generation: Generation
    #: The owner's process identity: a pid alone is a number that gets reused, which
    #: is why the start time travels with it.
    pid: int
    started_ticks: int
    bundle_id: str

    def as_document(self) -> dict[str, object]:
        return {
            "kin_id": self.kin_id,
            "hosted_world_id": self.hosted_world_id,
            "session_id": str(self.session_id),
            "generation": int(self.generation),
            "pid": self.pid,
            "started_ticks": self.started_ticks,
            "bundle_id": self.bundle_id,
        }


@dataclass(frozen=True, slots=True)
class LockDecision:
    """Whether this run may lock the world, and which path it is taking."""

    admitted: bool
    #: True when the lease was taken over from an owner that is gone, rather than
    #: found free. Recorded because "we reclaimed a dead session's world" and "we
    #: started a world nobody had opened" are different facts about a run.
    reclaimed: bool = False
    refusal: LockRefusal | None = None
    detail: str = ""

    def __str__(self) -> str:
        if self.admitted:
            return "RECLAIMED" if self.reclaimed else "LOCKED"
        return f"{self.refusal}: {self.detail}" if self.detail else str(self.refusal)

    def as_document(self) -> dict[str, object]:
        return {
            "admitted": self.admitted,
            "reclaimed": self.reclaimed,
            "refusal": None if self.refusal is None else self.refusal.value,
            "detail": self.detail,
        }


def _refuse(refusal: LockRefusal, detail: str) -> LockDecision:
    return LockDecision(False, False, refusal, detail)


def admit_locking(
    *,
    lease: SupervisorLease | None,
    lease_observation: LockObservation,
    owner_is_running: bool | None,
    session_lock: LockObservation,
) -> LockDecision:
    """Whether this run may take both locks for one hosted world.

    `lease` is the record found on disk, or None when there is none. `owner_is_running`
    is what the launcher established about the process that record names: True,
    False, or None when it could not be established — the third is not a synonym for
    False, which is the whole reason the recovery path can be told apart from the
    guess.
    """

    if lease_observation is LockObservation.UNKNOWN:
        return _refuse(
            LockRefusal.LEASE_UNREADABLE,
            "the supervisor lease could not be read, so this run cannot tell whether "
            "the world is already held",
        )

    reclaimed = False
    record = lease
    if record is not None:
        if owner_is_running is True:
            return _refuse(
                LockRefusal.WORLD_IN_USE,
                f"{record.hosted_world_id} is held by session {record.session_id} "
                f"(pid {record.pid}, started at {record.started_ticks})",
            )
        if owner_is_running is None:
            return _refuse(
                LockRefusal.LEASE_OWNER_UNKNOWN,
                "the lease names an owner whose process identity could not be checked, "
                "and a lease is reclaimed only once the old owner is confirmed gone",
            )
        # The owner is gone. The contract's recovery path, and not the same thing as
        # a lease that was never taken: the caller gets to record which it was.
        reclaimed = True
    elif lease_observation is LockObservation.HELD:
        # A lease reported as held with no record behind it: there is nothing to name
        # and nothing to check the owner against, which is the unknown case and not a
        # reason to start.
        return _refuse(
            LockRefusal.LEASE_UNREADABLE,
            "a supervisor lease is held but no record of it could be read, so its "
            "owner cannot be checked",
        )

    if session_lock is LockObservation.HELD:
        return _refuse(
            LockRefusal.SESSION_LOCK_HELD,
            "the save is open in another process, so this run may not start a server against it",
        )
    if session_lock is not LockObservation.FREE:
        return _refuse(
            LockRefusal.SESSION_LOCK_UNKNOWN,
            "the vanilla session lock could not be read; a leftover lock file is not "
            "evidence that a process is alive, and it is not evidence that none is",
        )
    return LockDecision(True, reclaimed=reclaimed)
