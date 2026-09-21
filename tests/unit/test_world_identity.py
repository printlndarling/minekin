"""What makes a world the same world, one rule at a time.

The commit-recovery contract lists six observations and what each of them means for a
world's identity, and each has a test named after the rule rather than after the
function. Three of them are HOSTCOMMIT-110, which asks for exactly these three
outcomes: a rebuilt name is a new world, another save behind the same address is not
decided here, and a changed port is not a change at all.

The rest are the two invariants that keep the record honest — a parent epoch has to
come before the epoch it precedes, and an identity offered where none is made is
refused rather than dropped.
"""

from __future__ import annotations

import pytest

from minekin_core.domain.ids import Generation, OpaqueId, WorldContextId
from minekin_core.domain.world_identity import (
    IdentityOutcome,
    WorldChange,
    WorldLineage,
    WorldTransition,
    first_lineage,
    lineage_for,
)

WORLD = OpaqueId("world-1")
CONTEXT = WorldContextId("context-1")
OTHER_WORLD = OpaqueId("world-2")
OTHER_CONTEXT = WorldContextId("context-2")


def lineage() -> WorldLineage:
    return first_lineage(
        hosted_world_id=WORLD,
        world_context_id=CONTEXT,
        storage_slot="world-kin-01-proposal-p0-0001",
        bundle_id="p0-core-1.21.4",
        evidence="join:run-1",
    )


def changed(
    change: WorldChange, **overrides: object
) -> tuple[WorldLineage | None, IdentityOutcome]:
    arguments: dict[str, object] = {"evidence": "join:run-2"}
    arguments.update(overrides)
    return lineage_for(lineage(), change, **arguments)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# The contract's six rules
# ---------------------------------------------------------------------------


def test_an_ordinary_restart_keeps_the_world_and_the_epoch() -> None:
    """Continuing the same save is the same world in the same epoch."""

    after, outcome = changed(WorldChange.RESTART_SAME_SAVE)

    assert outcome is IdentityOutcome.UNCHANGED
    assert after is not None
    assert after.hosted_world_id == WORLD
    assert after.world_context_id == CONTEXT
    assert after.world_epoch == Generation(1)
    assert after.transition is WorldTransition.CONTINUE


def test_a_rollback_keeps_the_world_and_takes_a_new_epoch() -> None:
    """The facts after the rollback point stop being current, and the world does not change.

    The epoch is what says so; the identity is untouched. That is the whole reason the
    two are separate fields, and a rollback that moved the identity would throw away a
    Kin's world to correct a mistake inside it.
    """

    after, outcome = changed(WorldChange.ROLLBACK_FROM_BACKUP, checkpoint_id="checkpoint-3")

    assert outcome is IdentityOutcome.SAME_WORLD_NEW_EPOCH
    assert after is not None
    assert after.hosted_world_id == WORLD
    assert after.world_epoch == Generation(2)
    assert after.parent_epoch == Generation(1)
    assert after.transition is WorldTransition.ROLLBACK
    assert after.source_checkpoint_id == "checkpoint-3"


def test_a_copy_is_a_new_world_that_records_where_it_came_from() -> None:
    """A fork is about this world and is not this world, so it descends from it."""

    after, outcome = changed(WorldChange.COPY_INTO_TWO_WORLDS, new_identity=(OTHER_WORLD, CONTEXT))

    assert outcome is IdentityOutcome.NEW_WORLD
    assert after is not None
    assert after.hosted_world_id == OTHER_WORLD
    assert after.world_context_id == CONTEXT, "a fork is still about this world"
    assert after.world_epoch == Generation(1), "a new world starts at its first epoch"
    assert after.parent_epoch == Generation(1), "and says what it descends from"
    assert after.transition is WorldTransition.FORK


def test_rebuilding_a_name_makes_a_new_world() -> None:
    """HOSTCOMMIT-110's first outcome: 同名重建得出的是一个新世界。

    Deleting a save and rebuilding one under the same name makes two worlds that share
    a name and nothing else. Merging them would hand the Kin the new world's inventory
    and the old world's map.
    """

    after, outcome = changed(
        WorldChange.REBUILD_SAME_NAME, new_identity=(OTHER_WORLD, OTHER_CONTEXT)
    )

    assert outcome is IdentityOutcome.NEW_WORLD_AND_CONTEXT
    assert after is not None
    assert after.hosted_world_id == OTHER_WORLD
    assert after.world_context_id == OTHER_CONTEXT
    assert after.world_epoch == Generation(1)
    assert after.transition is WorldTransition.REPLACE


def test_an_address_that_holds_another_save_is_not_decided_here() -> None:
    """HOSTCOMMIT-110's second outcome: 同地址换档进入待审查。

    An address is not identity — the contract says so in as many words — so a decision
    made here would rest on the one piece of evidence it rules out. No lineage comes
    back, because what this is has not been established yet.
    """

    after, outcome = changed(WorldChange.REMOTE_SAME_ADDRESS_OTHER_SAVE)

    assert outcome is IdentityOutcome.REVIEW
    assert after is None, "a candidate is not a world until something reconciles it"


def test_a_lan_port_change_does_not_move_the_identity() -> None:
    """HOSTCOMMIT-110's third outcome: 端口改变仍是同一个世界。

    A port is where a world is listening. The record comes back unchanged and nothing
    is rewritten — not even the evidence string, because nothing happened to the world.
    """

    before = lineage()
    after, outcome = changed(WorldChange.LAN_PORT_CHANGED)

    assert outcome is IdentityOutcome.UNCHANGED
    assert after == before


# ---------------------------------------------------------------------------
# The record itself
# ---------------------------------------------------------------------------


def test_the_record_names_no_port_no_address_and_no_name() -> None:
    """The contract lists what may not be a key, so none of them is a field.

    Checked as a field list rather than argued: "the port is not part of the identity"
    is a claim that survives exactly as long as nobody adds a field for it.
    """

    assert set(WorldLineage.__dataclass_fields__) == {
        "world_context_id",
        "hosted_world_id",
        "world_epoch",
        "parent_epoch",
        "transition",
        "source_checkpoint_id",
        "storage_slot",
        "bundle_id",
        "activated_by_evidence",
    }
    document = lineage().as_document()

    assert set(document) == set(WorldLineage.__dataclass_fields__)
    assert document["world_epoch"] == 1
    assert document["parent_epoch"] is None


@pytest.mark.parametrize(
    "change",
    [WorldChange.COPY_INTO_TWO_WORLDS, WorldChange.REBUILD_SAME_NAME],
)
def test_a_world_that_descends_from_another_says_so(change: WorldChange) -> None:
    """A new world points at what it came from, and starts at its first epoch.

    There is deliberately no check that the parent epoch is *lower* than this one: a
    fork's parent is an epoch of a world that no longer exists under this identity, so
    the two numbers are not comparable. The check was written, refused a legitimate
    fork, and was removed — which is what this test is here to keep from coming back.
    """

    after, _outcome = changed(change, new_identity=(OTHER_WORLD, OTHER_CONTEXT))

    assert after is not None
    assert after.parent_epoch is not None, "a world that appeared from nowhere is not a lineage"
    assert after.world_epoch == Generation(1)


def test_a_record_that_names_no_slot_or_bundle_is_refused() -> None:
    """The one invariant on the record that survives: a world names where it lives.

    A lineage whose slot or bundle is empty names a world nobody can find, which is
    the failure mode the whole record exists to prevent.
    """

    for field in ("storage_slot", "bundle_id"):
        arguments: dict[str, object] = {
            "world_context_id": CONTEXT,
            "hosted_world_id": WORLD,
            "world_epoch": Generation(1),
            "parent_epoch": None,
            "transition": WorldTransition.CONTINUE,
            "source_checkpoint_id": "",
            "storage_slot": "slot",
            "bundle_id": "p0-core-1.21.4",
            "activated_by_evidence": "join:run-1",
        }
        arguments[field] = ""

        with pytest.raises(ValueError, match="names the slot and the bundle"):
            WorldLineage(**arguments)  # type: ignore[arg-type]


def test_a_change_that_makes_a_world_without_an_identity_is_refused() -> None:
    """Refused rather than given one: a made-up identity is a world nobody finds again."""

    _after, outcome = changed(WorldChange.COPY_INTO_TWO_WORLDS)

    assert outcome is IdentityOutcome.MISSING_NEW_IDENTITY


@pytest.mark.parametrize(
    "change",
    [
        WorldChange.RESTART_SAME_SAVE,
        WorldChange.ROLLBACK_FROM_BACKUP,
        WorldChange.LAN_PORT_CHANGED,
    ],
)
def test_an_identity_offered_where_none_is_made_is_refused(change: WorldChange) -> None:
    """The other half, and the one that hides: an argument dropped in silence.

    A caller that passed a new world id for a restart would go on believing it had
    created something, and this refusal is the only thing that tells it otherwise.
    """

    _after, outcome = changed(change, new_identity=(OTHER_WORLD, OTHER_CONTEXT))

    assert outcome is IdentityOutcome.UNEXPECTED_NEW_IDENTITY
