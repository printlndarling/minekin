"""The transitional curated roster of entity types the mind treats as threats.

A small table, not a claim about every hostile in the game — the same boundary the food
catalog keeps: names come from the client's own report (`EntityCandidate.entity_type` on a
visible, in-sight entity), never from a hidden entity list, and an entity this table does
not name is simply not treated as a threat, never guessed into or out of one. The roster
grows one data row at a time; no code below it names an entity type.

The range is the melee reach a hostile closes in a few seconds, measured against the run
that motivated the table: run-89 (2026-10-05), where a night slime slew the Kin nine times
before it had any response at all. A threat beyond the range is a fact for the summary,
not a reason to stop working.
"""

from __future__ import annotations

import math
from typing import Final

from minekin_core.domain.perception import EntityCandidate, WorldObservationValue

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


def nearest_hostile(reading: WorldObservationValue) -> tuple[EntityCandidate, float] | None:
    """The nearest visible, in-sight hostile within range: the reported entity and its
    horizontal distance.

    Only what the client rendered counts: an item entity is not a threat, a hostile out of
    line of sight is not proven to be on this body, and one beyond the range is a fact for
    the summary rather than a stop-work alarm. None when no such entity is visible. The
    entity travels with the answer because a retreat needs its reported offset, and naming
    the offset again outside this scan would be a second reader of the same list.
    """

    nearest: tuple[EntityCandidate, float] | None = None
    for entity in reading.visible_entities:
        if entity.item_id is not None or not entity.line_of_sight:
            continue
        if entity.entity_type not in HOSTILE_ENTITY_TYPES:
            continue
        distance = math.hypot(entity.relative_x, entity.relative_z)
        if distance > THREAT_RANGE_BLOCKS:
            continue
        if nearest is None or distance < nearest[1]:
            nearest = (entity, distance)
    return nearest
