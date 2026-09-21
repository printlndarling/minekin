"""What makes a world the same world, and what makes it a different one.

The commit-recovery contract states this as a list of rules and the list is the
authority: an ordinary restart continuing the same save keeps the identity and the
epoch, a rollback from an old backup keeps the identity and takes a new epoch, copying
a save into two worlds that are meant to develop independently makes two identities,
and deleting a save to rebuild one under the same name makes a new world and a new
context. A LAN port change is not an identity change at all, and a remote address
that turns out to hold a different save proves nothing — the address is not identity,
so that one goes to review rather than being decided here.

The rules that make this worth writing down are the two negative ones, because both
are ways a world gets quietly merged with another:

- A **display name** may not merge two worlds. Rebuilding a deleted save under the
  same name is a new world; only the name is the same.
- Neither may a **seed, a level name, a MOTD, a player name or a directory name**.
  None of them is a key on its own, which is why none of them is a field of the
  record: an identity that could be derived from what a person typed is an identity a
  person can collide with.

The epoch is what carries "these are the same world but not the same reality": the
facts after a rollback point stop being current, and the contract's word for the
result is that the Kin may still remember it happened, but it is not their stuff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from minekin_core.domain.ids import Generation, OpaqueId, WorldContextId

_SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


class WorldTransition(StrEnum):
    """How one world-epoch follows another, as the contract's lineage record says."""

    #: The same save, carried on. Same identity, same epoch.
    CONTINUE = "CONTINUE"
    #: An old checkpoint put back. Same identity, new epoch: what happened after the
    #: checkpoint is no longer current.
    ROLLBACK = "ROLLBACK"
    #: A save restored as a copy rather than as this world.
    RESTORE_COPY = "RESTORE_COPY"
    #: A deleted save rebuilt under the same name. A new world that happens to be
    #: called what the old one was called.
    REPLACE = "REPLACE"
    #: A save copied so that two worlds may develop independently from here.
    FORK = "FORK"


class WorldChange(StrEnum):
    """What was observed, named the way the contract's rules name it.

    Six observations rather than five transitions, because two of the contract's rules
    are about changes that are *not* transitions: a LAN port change leaves the world
    alone, and a remote address holding another save is not evidence of anything.
    """

    RESTART_SAME_SAVE = "RESTART_SAME_SAVE"
    ROLLBACK_FROM_BACKUP = "ROLLBACK_FROM_BACKUP"
    COPY_INTO_TWO_WORLDS = "COPY_INTO_TWO_WORLDS"
    REBUILD_SAME_NAME = "REBUILD_SAME_NAME"
    LAN_PORT_CHANGED = "LAN_PORT_CHANGED"
    REMOTE_SAME_ADDRESS_OTHER_SAVE = "REMOTE_SAME_ADDRESS_OTHER_SAVE"


class IdentityOutcome(StrEnum):
    """What the observation comes to, one answer per rule."""

    #: The same world, the same epoch: nothing about its identity moved.
    UNCHANGED = "UNCHANGED"
    #: The same world in a new epoch. The lineage record is rewritten, the identity is
    #: not.
    SAME_WORLD_NEW_EPOCH = "SAME_WORLD_NEW_EPOCH"
    #: A different world, recorded as descending from this one.
    NEW_WORLD = "NEW_WORLD"
    #: A different world *and* a different logical context: the same name is all the
    #: two have in common.
    NEW_WORLD_AND_CONTEXT = "NEW_WORLD_AND_CONTEXT"
    #: Not decided here. The address is not identity, so what this is has to be
    #: reconciled before anything may call it a world — and until then it is a
    #: *candidate*, which is what the activation gate is for.
    REVIEW = "REVIEW"
    #: This change makes a different world and no identity was given for it. Refused
    #: rather than recorded, because a lineage with a made-up identity is a world
    #: nobody can find again.
    MISSING_NEW_IDENTITY = "MISSING_NEW_IDENTITY"
    #: An identity was offered for a change that makes none. Refused rather than
    #: ignored, because an argument dropped in silence is how a caller comes to
    #: believe it created something.
    UNEXPECTED_NEW_IDENTITY = "UNEXPECTED_NEW_IDENTITY"


#: Which transition each observed change is, when it is one at all.
_TRANSITION_FOR: Final[dict[WorldChange, WorldTransition]] = {
    WorldChange.RESTART_SAME_SAVE: WorldTransition.CONTINUE,
    WorldChange.ROLLBACK_FROM_BACKUP: WorldTransition.ROLLBACK,
    WorldChange.COPY_INTO_TWO_WORLDS: WorldTransition.FORK,
    WorldChange.REBUILD_SAME_NAME: WorldTransition.REPLACE,
}

#: The changes that make a different world, and which of them also make a different
#: logical context. A fork descends from this world and is still *about* it; a rebuild
#: shares only the name.
_NEW_WORLD: Final[dict[WorldChange, IdentityOutcome]] = {
    WorldChange.COPY_INTO_TWO_WORLDS: IdentityOutcome.NEW_WORLD,
    WorldChange.REBUILD_SAME_NAME: IdentityOutcome.NEW_WORLD_AND_CONTEXT,
}


@dataclass(frozen=True, slots=True)
class WorldLineage:
    """One world-epoch, and where it came from.

    The contract's fields and only those. No port, no address, no name: every one of
    those can change while the world stays the same world, and the contract is
    explicit that none of them is a key.
    """

    world_context_id: WorldContextId
    hosted_world_id: OpaqueId
    world_epoch: Generation
    #: The epoch this one follows, or None for the first. A rollback's parent is the
    #: epoch it rolled back from, which is how a reader can tell the two apart.
    parent_epoch: Generation | None
    transition: WorldTransition
    source_checkpoint_id: str
    storage_slot: str
    bundle_id: str
    activated_by_evidence: str

    def __post_init__(self) -> None:
        # Deliberately *not* checked here: that a parent epoch is lower than this one.
        # It is true of a rollback, where both numbers are epochs of one world, and it
        # is false of a fork or a rebuild, where the parent is an epoch of a world that
        # no longer exists under this identity. A comparison between two worlds'
        # counters is not an invariant, and the first version of this check refused a
        # legitimate fork — which is what the test for it was for.
        if not self.storage_slot or not self.bundle_id:
            raise ValueError("a lineage names the slot and the bundle it was built from")

    def as_document(self) -> dict[str, object]:
        return {
            "world_context_id": str(self.world_context_id),
            "hosted_world_id": str(self.hosted_world_id),
            "world_epoch": int(self.world_epoch),
            "parent_epoch": None if self.parent_epoch is None else int(self.parent_epoch),
            "transition": self.transition.value,
            "source_checkpoint_id": self.source_checkpoint_id,
            "storage_slot": self.storage_slot,
            "bundle_id": self.bundle_id,
            "activated_by_evidence": self.activated_by_evidence,
        }


def first_lineage(
    *,
    hosted_world_id: OpaqueId,
    world_context_id: WorldContextId,
    storage_slot: str,
    bundle_id: str,
    evidence: str,
) -> WorldLineage:
    """A world that has no predecessor, at its first epoch."""

    return WorldLineage(
        world_context_id=world_context_id,
        hosted_world_id=hosted_world_id,
        world_epoch=Generation(1),
        parent_epoch=None,
        transition=WorldTransition.CONTINUE,
        source_checkpoint_id="",
        storage_slot=storage_slot,
        bundle_id=bundle_id,
        activated_by_evidence=evidence,
    )


def lineage_for(
    previous: WorldLineage,
    change: WorldChange,
    *,
    evidence: str,
    new_identity: tuple[OpaqueId, WorldContextId] | None = None,
    checkpoint_id: str = "",
) -> tuple[WorldLineage | None, IdentityOutcome]:
    """What this observation makes of the world that was there before it.

    Returns the lineage to record and what it came to, or no lineage at all when the
    answer is that this is not a world yet. A caller that offers an identity for a
    change that makes none is refused rather than ignored, and one that makes a world
    without offering an identity is refused rather than given one: both are ways a
    caller comes to believe it created something it did not.
    """

    if change is WorldChange.LAN_PORT_CHANGED:
        # The same world, and nothing is rewritten: a port is where a world is
        # listening, not what it is.
        return (
            (None, IdentityOutcome.UNEXPECTED_NEW_IDENTITY)
            if new_identity
            else (
                previous,
                IdentityOutcome.UNCHANGED,
            )
        )
    if change is WorldChange.REMOTE_SAME_ADDRESS_OTHER_SAVE:
        # An address is not identity. Deciding this here would be deciding on the one
        # piece of evidence the contract rules out.
        return None, IdentityOutcome.REVIEW

    makes_a_world = _NEW_WORLD.get(change)
    if makes_a_world is not None:
        if new_identity is None:
            return None, IdentityOutcome.MISSING_NEW_IDENTITY
        hosted_world_id, context_id = new_identity
        return (
            replace(
                previous,
                world_context_id=context_id,
                hosted_world_id=hosted_world_id,
                world_epoch=Generation(1),
                parent_epoch=previous.world_epoch,
                transition=_TRANSITION_FOR[change],
                source_checkpoint_id=checkpoint_id,
                activated_by_evidence=evidence,
            ),
            makes_a_world,
        )
    if new_identity is not None:
        return None, IdentityOutcome.UNEXPECTED_NEW_IDENTITY
    if change is WorldChange.ROLLBACK_FROM_BACKUP:
        return (
            replace(
                previous,
                world_epoch=previous.world_epoch.next(),
                parent_epoch=previous.world_epoch,
                transition=WorldTransition.ROLLBACK,
                source_checkpoint_id=checkpoint_id,
                activated_by_evidence=evidence,
            ),
            IdentityOutcome.SAME_WORLD_NEW_EPOCH,
        )
    assert change is WorldChange.RESTART_SAME_SAVE, change
    return (
        replace(previous, transition=WorldTransition.CONTINUE, activated_by_evidence=evidence),
        IdentityOutcome.UNCHANGED,
    )
