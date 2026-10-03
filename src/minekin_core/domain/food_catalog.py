"""Which items this build knows how to eat, until a version-exact source is wired.

Eating needs one piece of knowledge the readings cannot supply: which items are food.
A player recognises bread as a meal from the game's own content, and this table is that
recognition written down — but only as far as this build has curated it. The boundary is
deliberately small and hand-checked against vanilla **1.20.1** (the product line's
version), and it does not claim to be the game's food registry:

- An item missing from this table is refused by name (`CONSUME_ITEM_NOT_KNOWN_FOOD`,
  see `world_actions.consume_item_refusal`) — that word says *this build has no curated
  row*, not *the game considers the item inedible*. No reading and no model answer can
  widen the table at runtime.
- The values are vanilla 1.20.1 hunger points, and they are used for **ordering only**
  (the local layer prefers the larger meal when several foods are at hand). They never
  confirm anything: §4's confirmation is the world's own next reading.
- Deliberately out of scope in this increment, recorded here so its absence is a fact
  rather than an oversight: items that return a container (stews, honey bottle), items
  whose point is an effect rather than hunger (suspicious stew, chorus fruit's
  teleport), and the always-edible flag those effect items carry — the skill rests on
  "the hunger bar has room", and an item that can be eaten at full hunger would confirm
  on a bar that does not move.

The step this table is a transition to is named rather than assumed: the client's own
item registry can answer `Item#isFood()` for the version it is running, and the Bridge
already publishes a re-read of that client every ten ticks — a future revision can
carry an `is_food` bit per inventory stack and retire this table the way the recipe
catalog is slated to hand over to the recipe book. Until that field exists on the wire,
nothing here may pretend the knowledge came from the world.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

#: Item id -> vanilla 1.20.1 hunger points. Sorted for a diff that reads; every row was
#: checked by hand against the version's food component values, which is exactly the kind
#: of knowledge the recipe catalog is allowed to hold and `domain/` is the only home for.
FOODS: Final[Mapping[str, int]] = MappingProxyType(
    {
        "minecraft:apple": 4,
        "minecraft:baked_potato": 5,
        "minecraft:beetroot": 1,
        "minecraft:bread": 5,
        "minecraft:carrot": 3,
        "minecraft:cooked_beef": 8,
        "minecraft:cooked_chicken": 6,
        "minecraft:cooked_cod": 5,
        "minecraft:cooked_mutton": 6,
        "minecraft:cooked_porkchop": 8,
        "minecraft:cooked_rabbit": 5,
        "minecraft:cooked_salmon": 6,
        "minecraft:cookie": 2,
        "minecraft:dried_kelp": 1,
        "minecraft:glow_berries": 2,
        "minecraft:golden_apple": 4,
        "minecraft:melon_slice": 2,
        "minecraft:potato": 1,
        "minecraft:pumpkin_pie": 8,
        "minecraft:raw_beef": 3,
        "minecraft:raw_chicken": 2,
        "minecraft:raw_cod": 2,
        "minecraft:raw_mutton": 2,
        "minecraft:raw_porkchop": 3,
        "minecraft:raw_rabbit": 3,
        "minecraft:raw_salmon": 2,
        "minecraft:sweet_berries": 2,
    }
)


def is_known_food(item_id: object) -> bool:
    """Whether this build has a curated row for the item. A type-strict lookup on
    purpose: the id arrives from an endpoint's answer or an inventory reading, and a
    caller that handed in a non-string would otherwise get a `False` that reads like a
    statement about food rather than about the type."""

    return isinstance(item_id, str) and item_id in FOODS


def nutrition_for(item_id: object) -> int | None:
    """The curated hunger points, or `None` for anything this table has no row for."""

    if not isinstance(item_id, str):
        return None
    return FOODS.get(item_id)
