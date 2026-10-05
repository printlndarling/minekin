"""Every entity the client rendered, as one generic scan.

Recognition is the client's, and it is generic on purpose: an entity arrives with the
game's own type id, its offset from the Kin, whether the Kin can see it, and an item id
when it renders as a dropped stack. Nothing here decides what an entity *means* -- hostile,
animal, trader are readings of the moment, judged by whoever decides (the model, when one
is configured; the local backstop's curated roster when not), never by this module. It is
the one place the rendered list is read for a nearby-entity question, so every reader --
the model-facing summary, the attack offer, the danger scan -- sees the same list.

Only what the client rendered counts, and only the fields it renders: no world
coordinates, no entity inventories, no health of another body.
"""

from __future__ import annotations

import math
from typing import Final

from minekin_core.domain.perception import EntityCandidate, WorldObservationValue

#: How many entities one model-facing summary row carries. Nearest first, because the
#: nearest few are what a decision between "it, me, or the work" is actually about; a
#: crowd beyond this is a count, not a list.
SUMMARY_ENTITY_LIMIT: Final = 12


def rendered_entities(reading: WorldObservationValue) -> tuple[EntityCandidate, ...]:
    """Every non-item entity the client rendered, nearest first.

    A dropped stack is an entity on the wire, and it is not a body: the item path has its
    own reader (`dropped_items`), so an item id here would be the same fact twice with two
    chances to disagree. Ties keep the client's own order — the list is a reading, and it
    does not sort by anything the client did not say.
    """

    bodies = [entity for entity in reading.visible_entities if entity.item_id is None]
    return tuple(sorted(bodies, key=lambda e: math.hypot(e.relative_x, e.relative_z)))


def nearest_visible(
    reading: WorldObservationValue,
    *,
    kinds: frozenset[str] | set[str] | None = None,
    within: float | None = None,
    line_of_sight: bool = True,
) -> tuple[EntityCandidate, float] | None:
    """The nearest rendered entity matching the filter, with its horizontal distance.

    `kinds` is the caller's own judgement of which types it is asking about (or None for
    any); `within` bounds the horizontal distance; `line_of_sight` keeps the default that
    the Kin can actually see the body — a fact the client renders. The entity travels with
    the answer because bearings are taken from its offsets, and naming the offset again
    outside this scan would be a second reader of the same list.
    """

    nearest: tuple[EntityCandidate, float] | None = None
    for entity in rendered_entities(reading):
        if kinds is not None and entity.entity_type not in kinds:
            continue
        if line_of_sight and not entity.line_of_sight:
            continue
        distance = math.hypot(entity.relative_x, entity.relative_z)
        if within is not None and distance > within:
            continue
        if nearest is None or distance < nearest[1]:
            nearest = (entity, distance)
    return nearest
