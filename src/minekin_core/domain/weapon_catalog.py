"""Which items this build knows as hand weapons, until a version-exact source is wired.

Choosing what to hold before a fight needs one piece of knowledge the readings cannot
supply: which items are weapons and how they order against each other. A player reads
that off the game's own content, and this table is that reading written down -- but only
as far as this build has curated it. The boundary is deliberately small and hand-checked
against vanilla **1.20.1** (the product line's version), and it does not claim to be the
game's weapon registry:

- A row's number is vanilla 1.20.1 attack damage, and it is used for **ordering only**
  (the skill brings the biggest number to hand when several weapons are within reach).
  It never confirms anything: §4's confirmation is the world's own next reading, and no
  number here says a swing landed or that a fight can be won.
- An item missing from this table is simply never *chosen* by this build; the fight
  itself still works bare-handed, so an unknown weapon is a missed preference, not a
  refusal. No reading and no model answer can widen the table at runtime.
- Deliberately out of scope in this increment, recorded here so its absence is a fact
  rather than an oversight: shovels and hoes (their 1.20.1 damages are fractional and
  the lowest tier is the bare fist's 1), and everything that is not "hold it and swing
  the attack key" (bows, crossbows, tridents, shields). Enchantments and potion effects
  are not modelled: the table orders the stack, not the moment.

The step this table is a transition to is named rather than assumed: the client's own
item registry can answer an item's attack damage for the version it is running, and the
Bridge already publishes a re-read of that client every ten ticks -- a future revision
can carry a damage number per inventory stack and retire this table the way the recipe
catalog is slated to hand over to the recipe book. Until that field exists on the wire,
nothing here may pretend the knowledge came from the world.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

#: Item id -> vanilla 1.20.1 attack damage. Sorted for a diff that reads; every row was
#: checked by hand against the version's item attribute values, which is exactly the
#: kind of knowledge the recipe catalog is allowed to hold and `domain/` is the only
#: home for.
WEAPONS: Final[Mapping[str, int]] = MappingProxyType(
    {
        "minecraft:diamond_axe": 9,
        "minecraft:diamond_pickaxe": 5,
        "minecraft:diamond_sword": 7,
        "minecraft:golden_axe": 7,
        "minecraft:golden_pickaxe": 2,
        "minecraft:golden_sword": 4,
        "minecraft:iron_axe": 9,
        "minecraft:iron_pickaxe": 4,
        "minecraft:iron_sword": 6,
        "minecraft:netherite_axe": 10,
        "minecraft:netherite_pickaxe": 6,
        "minecraft:netherite_sword": 8,
        "minecraft:stone_axe": 9,
        "minecraft:stone_pickaxe": 3,
        "minecraft:stone_sword": 5,
        "minecraft:wooden_axe": 7,
        "minecraft:wooden_pickaxe": 2,
        "minecraft:wooden_sword": 4,
    }
)


def is_known_weapon(item_id: object) -> bool:
    """Whether this build has a curated row for the item. A type-strict lookup on
    purpose: the id arrives from an endpoint's answer or an inventory reading, and a
    caller that handed in a non-string would otherwise get a `False` that reads like a
    statement about weapons rather than about the type."""

    return isinstance(item_id, str) and item_id in WEAPONS


def attack_damage_for(item_id: object) -> int | None:
    """The curated attack damage, or `None` for anything this table has no row for."""

    if not isinstance(item_id, str):
        return None
    return WEAPONS.get(item_id)
