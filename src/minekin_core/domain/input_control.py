"""Who may drive the client, and what happens when they may not.

A lease is not a permission slip for one action; it is the whole authorisation to
touch the input at all, bound to one connection generation, one client instance,
one capability set and one deadline. Everything that can go wrong is checked here
rather than in the Bridge, because the Bridge's job is to apply what it is told
and to let go the moment it is told to stop.

The invariant that matters most is the last one: whatever invalidates a lease —
a new generation, leaving PLAYABLE, an expiry, a lost control channel, a death, a
GUI taking focus — the answer is the same, and it is always "release every key".
A client that keeps a movement key down while nothing holds a lease is how an
automated player walks into lava unattended.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from minekin_core.domain.ids import Generation
from minekin_core.domain.time import MonotonicInstant


class InputPriority(IntEnum):
    """The wire's own ordering; the domain cannot express an unspecified one."""

    NORMAL = 1
    URGENT = 2
    EMERGENCY = 3


class InputRefusal(StrEnum):
    """Why an input was not authorised, as a stable evidence token."""

    NO_LEASE = "NO_LEASE"
    LEASE_SUPERSEDED = "LEASE_SUPERSEDED"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    LEASE_ACTIVE = "LEASE_ACTIVE"
    GENERATION_MISMATCH = "GENERATION_MISMATCH"
    CAPABILITY_NOT_LEASED = "CAPABILITY_NOT_LEASED"
    REQUEST_DEADLINE_PASSED = "REQUEST_DEADLINE_PASSED"
    NOT_PLAYABLE = "NOT_PLAYABLE"


class ReleaseReason(StrEnum):
    """What invalidated the lease. Every one of them means the same thing."""

    EXPLICIT = "EXPLICIT"
    IPC_LOST = "IPC_LOST"
    CLIENT_DIED = "CLIENT_DIED"
    GUI_CONFLICT = "GUI_CONFLICT"
    TIMEOUT = "TIMEOUT"
    GENERATION_CHANGED = "GENERATION_CHANGED"
    PHASE_LEFT_PLAYABLE = "PHASE_LEFT_PLAYABLE"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class InputLease:
    """One authorisation to drive the client."""

    lease_id: str
    generation: Generation
    client_instance_id: str
    issued_monotonic_ns: int
    deadline_monotonic_ns: int
    priority: InputPriority
    capabilities: frozenset[str]

    def __post_init__(self) -> None:
        if not self.lease_id:
            raise ValueError("lease_id is required")
        if not self.client_instance_id:
            raise ValueError("client_instance_id is required")
        if self.deadline_monotonic_ns <= self.issued_monotonic_ns:
            raise ValueError("a lease deadline must be after it was issued")
        if not self.capabilities:
            # A lease that authorises nothing is a mistake, not a safety measure.
            raise ValueError("a lease must authorise at least one capability")

    def expired(self, now: MonotonicInstant) -> bool:
        return now.nanoseconds >= self.deadline_monotonic_ns

    def authorises(self, capability: str) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True, slots=True)
class InputRequest:
    """One action, carrying the lease it claims to act under."""

    lease_id: str
    generation: Generation
    capability: str
    deadline_monotonic_ns: int


@dataclass(frozen=True, slots=True)
class InputDecision:
    accepted: bool
    refusals: tuple[InputRefusal, ...]

    def as_document(self) -> dict[str, object]:
        return {"accepted": self.accepted, "refusals": [item.value for item in self.refusals]}


@dataclass(frozen=True, slots=True)
class ReleaseOutcome:
    """What must be sent to the Bridge after a lease ends."""

    generation: Generation
    reason: ReleaseReason
    had_lease: bool

    def as_document(self) -> dict[str, object]:
        return {
            "generation": int(self.generation),
            "reason": self.reason.value,
            "had_lease": self.had_lease,
        }


class InputArbiter:
    """The only thing that decides whether the client's input may be touched."""

    def __init__(self, generation: Generation, *, playable: bool = False) -> None:
        self._generation = generation
        self._playable = playable
        self._lease: InputLease | None = None

    @property
    def generation(self) -> Generation:
        return self._generation

    @property
    def playable(self) -> bool:
        return self._playable

    @property
    def current(self) -> InputLease | None:
        return self._lease

    def begin_connection(self) -> Generation:
        """Allocate the next generation, which is never a repeat of an earlier one."""

        self._generation = self._generation.next()
        self._lease = None
        self._playable = False
        return self._generation

    def set_playable(self, playable: bool) -> ReleaseOutcome | None:
        """Entering or leaving PLAYABLE; leaving it ends any lease."""

        if self._playable and not playable:
            return self.withdraw(ReleaseReason.PHASE_LEFT_PLAYABLE)
        self._playable = playable
        return None

    def grant(self, lease: InputLease) -> InputDecision:
        """Take or replace the input, or refuse to disturb a more important holder."""

        refusals: set[InputRefusal] = set()
        if lease.generation != self._generation:
            refusals.add(InputRefusal.GENERATION_MISMATCH)
        if not self._playable:
            refusals.add(InputRefusal.NOT_PLAYABLE)
        if (
            self._lease is not None
            and lease.priority <= self._lease.priority
            and self._lease.lease_id != lease.lease_id
        ):
            # Equal or lower priority does not get to take the input away.
            refusals.add(InputRefusal.LEASE_ACTIVE)
        if refusals:
            return InputDecision(accepted=False, refusals=tuple(sorted(refusals)))
        self._lease = lease
        return InputDecision(accepted=True, refusals=())

    def decide(self, request: InputRequest, *, now: MonotonicInstant) -> InputDecision:
        """Authorise one action, collecting every reason it cannot be applied."""

        lease = self._lease
        if lease is None:
            return InputDecision(accepted=False, refusals=(InputRefusal.NO_LEASE,))

        refusals: set[InputRefusal] = set()
        if request.lease_id != lease.lease_id:
            # A late action from a lease that has already ended is diagnostic only.
            refusals.add(InputRefusal.LEASE_SUPERSEDED)
        if request.generation != lease.generation:
            # A lease can only exist for the current generation: `grant` checks it
            # and `begin_connection` clears it, so only the request can be stale.
            refusals.add(InputRefusal.GENERATION_MISMATCH)
        if lease.expired(now):
            refusals.add(InputRefusal.LEASE_EXPIRED)
        if not self._playable:
            refusals.add(InputRefusal.NOT_PLAYABLE)
        if not lease.authorises(request.capability):
            refusals.add(InputRefusal.CAPABILITY_NOT_LEASED)
        if now.nanoseconds >= request.deadline_monotonic_ns:
            refusals.add(InputRefusal.REQUEST_DEADLINE_PASSED)
        return InputDecision(accepted=not refusals, refusals=tuple(sorted(refusals)))

    def withdraw(self, reason: ReleaseReason = ReleaseReason.EXPLICIT) -> ReleaseOutcome:
        """End the lease. Idempotent, and always means "release every key"."""

        had_lease = self._lease is not None
        self._lease = None
        return ReleaseOutcome(generation=self._generation, reason=reason, had_lease=had_lease)
