"""The hosted world's creation and close lifecycle, and who may move it.

The storage-lifecycle contract draws this as a state diagram and the diagram is the
authority: REQUESTED, PREPARED, LOCKED, CREATING, HOST_PLAYABLE, LAN_OPEN, QUIESCING,
SAVING, CLOSED, with QUARANTINED and RECOVERY_REQUIRED for the two ways it stops
being a clean run. The table below is that diagram and nothing else.

What this module adds to the diagram is the rule the control-boundary contract puts
around every completion of a host command: `session_id + generation + world_epoch +
expected_state` are re-verified each time, and a completion that does not match all
four is recorded as `STALE_COMPLETION` and may not move the world. The contract's own
sentence for it is that a cancelled creation, a failed resource-pack load, a pending
warning or an expired callback "都不能伪造成功" — none of them may forge a success.

Two of those refusals are the reasons this is a module rather than a comment:

- `DUPLICATE_CREATION`, because "不得重复建档" is a rule about a *second* creation and
  the table alone would call it a generic illegal jump. Naming it is what makes the
  distinction readable in a report, and a world created twice under one epoch is a
  thing a Kin would have to be told about.
- `STALE_COMPLETION`, because a callback crossing a generation is the normal case
  rather than an exotic one: the launcher is faster than the client, so a completion
  from the attempt before this one arrives after this one started.

The four coordinates are checked in order of how much they say. A different session
is another conversation entirely; an older epoch or generation is this world's own
history; a newer one is something that happened while we were not looking. Each gets
its own disposition, because "why was this refused" is the question an operator asks
and a single `REJECTED` would not answer it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from minekin_core.domain.ids import Generation, OpaqueId


class HostedWorldState(StrEnum):
    """Where a hosted world is, as the storage-lifecycle contract draws it."""

    REQUESTED = "REQUESTED"
    PREPARED = "PREPARED"
    LOCKED = "LOCKED"
    CREATING = "CREATING"
    HOST_PLAYABLE = "HOST_PLAYABLE"
    LAN_OPEN = "LAN_OPEN"
    QUIESCING = "QUIESCING"
    SAVING = "SAVING"
    CLOSED = "CLOSED"
    #: The load or create failed. The world is not lost — that is the difference
    #: between this and RECOVERY_REQUIRED — but it is not a world to run in.
    QUARANTINED = "QUARANTINED"
    #: A save that did not finish cleanly. Whatever is on disk is unknown until
    #: someone reconciles it, so nothing may continue from here.
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    #: The manifest exists and the save it names does not. A loading state, which is
    #: why it is not on the creation diagram: it is what loading finds.
    MISSING_SAVE = "MISSING_SAVE"


class WorldSignal(StrEnum):
    """What a completion says happened.

    Named after the condition the contract's diagram labels its edges with rather
    than after a channel or a function, because that is the level the diagram is
    drawn at: an edge is taken when the condition holds, whoever observed it.
    """

    MANIFEST_AND_QUOTA = "MANIFEST_AND_QUOTA"
    SUPERVISOR_AND_LOCK = "SUPERVISOR_AND_LOCK"
    CREATE_STARTED = "CREATE_STARTED"
    LOCAL_JOIN_AND_SNAPSHOT = "LOCAL_JOIN_AND_SNAPSHOT"
    LOAD_OR_CREATE_FAILED = "LOAD_OR_CREATE_FAILED"
    LAN_OPENED = "LAN_OPENED"
    LOCAL_ONLY_OR_STOP = "LOCAL_ONLY_OR_STOP"
    CLOSE_REQUESTED = "CLOSE_REQUESTED"
    INPUTS_REVOKED = "INPUTS_REVOKED"
    FLUSH_AND_STOP = "FLUSH_AND_STOP"
    CRASH_OR_ERROR = "CRASH_OR_ERROR"


#: The diagram, edge for edge. Anything not here is not a move this world makes.
_TRANSITIONS: Final[Mapping[tuple[HostedWorldState, WorldSignal], HostedWorldState]] = (
    MappingProxyType(
        {
            (HostedWorldState.REQUESTED, WorldSignal.MANIFEST_AND_QUOTA): (
                HostedWorldState.PREPARED
            ),
            (HostedWorldState.PREPARED, WorldSignal.SUPERVISOR_AND_LOCK): HostedWorldState.LOCKED,
            (HostedWorldState.LOCKED, WorldSignal.CREATE_STARTED): HostedWorldState.CREATING,
            (HostedWorldState.CREATING, WorldSignal.LOCAL_JOIN_AND_SNAPSHOT): (
                HostedWorldState.HOST_PLAYABLE
            ),
            (HostedWorldState.CREATING, WorldSignal.LOAD_OR_CREATE_FAILED): (
                HostedWorldState.QUARANTINED
            ),
            (HostedWorldState.HOST_PLAYABLE, WorldSignal.LAN_OPENED): HostedWorldState.LAN_OPEN,
            (HostedWorldState.HOST_PLAYABLE, WorldSignal.LOCAL_ONLY_OR_STOP): (
                HostedWorldState.QUIESCING
            ),
            (HostedWorldState.LAN_OPEN, WorldSignal.CLOSE_REQUESTED): HostedWorldState.QUIESCING,
            (HostedWorldState.QUIESCING, WorldSignal.INPUTS_REVOKED): HostedWorldState.SAVING,
            (HostedWorldState.SAVING, WorldSignal.FLUSH_AND_STOP): HostedWorldState.CLOSED,
            (HostedWorldState.SAVING, WorldSignal.CRASH_OR_ERROR): (
                HostedWorldState.RECOVERY_REQUIRED
            ),
        }
    )
)

#: The signals that bring a world into existence. Asked separately from the table
#: because the rule they carry — a world is created once per epoch — is about a
#: second one, and the table alone would call that an illegal jump.
_CREATES: Final[frozenset[WorldSignal]] = frozenset(
    {
        WorldSignal.CREATE_STARTED,
        WorldSignal.LOCAL_JOIN_AND_SNAPSHOT,
        WorldSignal.LOAD_OR_CREATE_FAILED,
    }
)

#: The states in which the world has been created: the contract turns the manifest
#: from PREPARED to CREATED/ACTIVE only once the local player actually joined and a
#: snapshot was accepted, and everything from there on is a world that exists.
_WORLD_EXISTS: Final[frozenset[HostedWorldState]] = frozenset(
    {
        HostedWorldState.HOST_PLAYABLE,
        HostedWorldState.LAN_OPEN,
        HostedWorldState.QUIESCING,
        HostedWorldState.SAVING,
        HostedWorldState.CLOSED,
        HostedWorldState.RECOVERY_REQUIRED,
    }
)


class HostDisposition(StrEnum):
    """What became of one completion, one reason each."""

    ADVANCED = "ADVANCED"
    #: From a different session. Another conversation's completion, however much it
    #: looks like one of ours.
    WRONG_SESSION = "WRONG_SESSION"
    #: Older epoch or generation than the world is on: the attempt before this one.
    STALE_COMPLETION = "STALE_COMPLETION"
    #: Newer than the world is on — a rollback or a recovery that happened while this
    #: completion was in flight, so it cannot be about the world that exists now.
    FUTURE_EPOCH = "FUTURE_EPOCH"
    #: The sender's idea of the current state is not the world's, so what it is
    #: completing is not what is happening.
    UNEXPECTED_STATE = "UNEXPECTED_STATE"
    #: A second creation under an epoch that already has a world.
    DUPLICATE_CREATION = "DUPLICATE_CREATION"
    #: The table has no edge for this signal from this state.
    ILLEGAL_SIGNAL = "ILLEGAL_SIGNAL"


@dataclass(frozen=True, slots=True)
class HostedWorld:
    """One world a Kin hosts, in the epoch it is currently in.

    Immutable, and admitted to rather than mutated: a completion either produces the
    next record or is refused, and a refused one leaves nothing behind. That is the
    property the contract is after when it says an expired callback may not move the
    world — a machine that could half-apply one would leave the record somewhere the
    diagram does not allow.
    """

    kin_id: OpaqueId
    hosted_world_id: OpaqueId
    storage_slot: str
    #: The creation profile this world was made from, so a completion carrying a
    #: different one is completing something else.
    profile_digest: str
    session_id: OpaqueId
    generation: Generation
    #: Incremented by a rollback, so the facts after a rollback point can be marked
    #: as no longer current. Two epochs of one world are two realities.
    world_epoch: Generation
    state: HostedWorldState = HostedWorldState.REQUESTED

    @property
    def has_a_world(self) -> bool:
        """Whether this world has been created.

        One definition, asked of the same set the duplicate rule uses: "the world
        exists" is one thing in this domain rather than two.
        """

        return self.state in _WORLD_EXISTS

    @property
    def settled(self) -> bool:
        """Whether no completion can move this world: it is waiting on a decision.

        Derived from the table rather than listed. A listed set is a second statement
        of what the diagram says, and it drifted the first time it was compared: the
        listed version called RECOVERY_REQUIRED unsettled, when the diagram has no
        edge out of it either — recovery is precisely a decision somebody outside the
        machine has to make.
        """

        return not any((self.state, signal) in _TRANSITIONS for signal in WorldSignal)


@dataclass(frozen=True, slots=True)
class HostCompletion:
    """One asynchronous completion of a host command, as its caller describes it."""

    session_id: OpaqueId
    generation: Generation
    world_epoch: Generation
    #: The state the sender believed the world was in when it acted. Checked against
    #: the world's, because a completion whose sender was looking at another state is
    #: completing another moment.
    expected_state: HostedWorldState
    signal: WorldSignal


@dataclass(frozen=True, slots=True)
class HostDecision:
    disposition: HostDisposition
    previous_state: HostedWorldState
    current_state: HostedWorldState

    @property
    def changed_state(self) -> bool:
        return self.previous_state != self.current_state


def admit(world: HostedWorld, completion: HostCompletion) -> tuple[HostedWorld, HostDecision]:
    """Take one completion, or refuse it and leave the world exactly as it was.

    The four coordinates are checked before the table, and in the order of how much
    they say: a different session is not this world's conversation at all, an older
    epoch or generation is this world's own past, and a newer one is something that
    happened to this world while the completion was in flight. Only then is the
    signal itself considered.
    """

    def refused(disposition: HostDisposition) -> tuple[HostedWorld, HostDecision]:
        return world, HostDecision(disposition, world.state, world.state)

    if completion.session_id != world.session_id:
        return refused(HostDisposition.WRONG_SESSION)
    if completion.generation < world.generation or completion.world_epoch < world.world_epoch:
        return refused(HostDisposition.STALE_COMPLETION)
    if completion.generation > world.generation or completion.world_epoch > world.world_epoch:
        return refused(HostDisposition.FUTURE_EPOCH)
    if completion.expected_state is not world.state:
        return refused(HostDisposition.UNEXPECTED_STATE)
    if world.has_a_world and completion.signal in _CREATES:
        return refused(HostDisposition.DUPLICATE_CREATION)
    target = _TRANSITIONS.get((world.state, completion.signal))
    if target is None:
        return refused(HostDisposition.ILLEGAL_SIGNAL)
    return (
        replace(world, state=target),
        HostDecision(HostDisposition.ADVANCED, world.state, target),
    )
