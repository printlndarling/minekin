"""The transitional curated roster of hostile types — the LOCAL backstop's knowledge.

A small table, not a claim about every hostile in the game — the same boundary the food
catalog keeps: names come from the client's own report (`EntityCandidate.entity_type` on a
visible, in-sight entity), never from a hidden entity list, and an entity this table does
not name is simply not treated as a threat, never guessed into or out of one. The roster
grows one data row at a time; no code below it names an entity type.

What this table is NOT: the gate on what may be done about a rendered entity. Recognition
is generic (`domain.visible_entities`: every rendered body with its type, distance and
line of sight), the generic behaviors take any named target, and what an entity MEANS for
this moment — hit it, leave it, keep working — is the deciding layer's judgement (the
model's when one is configured). This roster only teaches the no-model reflex which
rendered bodies to flinch from; it narrows nothing the model is shown or may choose.

The range is the melee reach a hostile closes in a few seconds, measured against the run
that motivated the table: run-89 (2026-10-05), where a night slime slew the Kin nine times
before it had any response at all. A threat beyond the range is a fact for the summary,
not a reason to stop working.
"""

from __future__ import annotations

from typing import Final

from minekin_core.domain.perception import EntityCandidate, WorldObservationValue
from minekin_core.domain.visible_entities import nearest_visible

#: Entity types (the game's own namespaced ids) whose visible presence near the Kin stops
#: stand-still work. Curated, version-agnostic at the id level: an id no world uses is
#: simply never matched.
HOSTILE_ENTITY_TYPES: Final = frozenset(
    {
        "minecraft:slime",
        "minecraft:magma_cube",
        "minecraft:zombie",
        "minecraft:husk",
        "minecraft:drowned",
        "minecraft:zombified_piglin",
        "minecraft:skeleton",
        "minecraft:stray",
        "minecraft:creeper",
        "minecraft:spider",
        "minecraft:cave_spider",
        "minecraft:witch",
        "minecraft:enderman",
        "minecraft:silverfish",
        "minecraft:phantom",
        "minecraft:pillager",
        "minecraft:vindicator",
        "minecraft:ravager",
        "minecraft:blaze",
        "minecraft:ghast",
    }
)

#: Horizontal reach, in blocks, for a visible hostile to count as a threat to the body.
THREAT_RANGE_BLOCKS: Final = 8.0

#: How far a swing can land, in blocks: the survival attack range a player's arm has. A
#: hostile inside the threat range but outside this one is a reason to move, not to swing.
ATTACK_REACH_BLOCKS: Final = 3.0


def nearest_hostile(reading: WorldObservationValue) -> tuple[EntityCandidate, float] | None:
    """The nearest visible, in-sight hostile within range: the reported entity and its
    horizontal distance.

    The generic scan (`domain.visible_entities`) with this table's roster as the kinds
    filter — one reader of the rendered list, and the roster is this catalog's whole
    contribution. None when no such entity is visible; the entity travels with the answer
    because a retreat needs its reported offset.
    """

    return nearest_visible(
        reading,
        kinds=HOSTILE_ENTITY_TYPES,
        within=THREAT_RANGE_BLOCKS,
    )


def attackable_hostile(reading: WorldObservationValue) -> tuple[EntityCandidate, float] | None:
    """The nearest visible hostile a swing could land on, for the LOCAL backstop.

    The same scan as `nearest_hostile`, narrowed to attack reach. The model's fight offer
    does NOT come from here — it is generic (`nearest_visible` over any body), because what
    may be hit is the model's judgement; this name exists so the no-model reflex does not
    punch a passing pig.
    """

    return nearest_visible(
        reading,
        kinds=HOSTILE_ENTITY_TYPES,
        within=ATTACK_REACH_BLOCKS,
    )
