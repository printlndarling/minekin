"""The interim weapon table, pinned where it is written.

Like the food table, this is a boundary as much as a list: it says which items this
build recognises as hand weapons and how they order against each other, and its whole
product claim is that nothing outside it is ever chosen into the hand before a fight.
The values are used for **ordering only** -- the biggest number wins the hand -- and
they never confirm anything: the world's own next reading is the only thing that says
a hit landed. These cells keep the boundary honest: rows are weapons with positive
damage, the lookups are type- and value-strict, and the mapping cannot be widened at
runtime.
"""

from __future__ import annotations

from typing import cast

import pytest

from minekin_core.domain.weapon_catalog import WEAPONS, attack_damage_for, is_known_weapon


def test_every_row_is_a_weapon_with_damage() -> None:
    assert WEAPONS
    for item_id, damage in WEAPONS.items():
        assert item_id.startswith("minecraft:")
        assert damage > 0
        assert is_known_weapon(item_id)
        assert attack_damage_for(item_id) == damage


def test_the_table_orders_axes_above_swords_above_pickaxes() -> None:
    # The one thing the table is used for is ordering: 1.20.1 attack damage puts a
    # stone axe (9) above a wooden sword (4) above a wooden pickaxe (2), and bare
    # hands are below every row of it.
    axe = attack_damage_for("minecraft:stone_axe")
    sword = attack_damage_for("minecraft:wooden_sword")
    pick = attack_damage_for("minecraft:wooden_pickaxe")
    assert axe is not None and sword is not None and pick is not None
    assert axe > sword > pick
    assert (axe, sword, pick) == (9, 4, 2)


def test_anything_outside_the_table_is_not_a_weapon_for_this_build() -> None:
    for item_id in ("minecraft:oak_log", "minecraft:stone", "minecraft:stick"):
        assert not is_known_weapon(item_id)
        assert attack_damage_for(item_id) is None
    # Strict about types as well as values: an endpoint's answer or a reading is not
    # guaranteed to be a string, and a non-string must not read like a statement
    # about weapons.
    assert not is_known_weapon(None)
    assert not is_known_weapon(4)
    assert attack_damage_for(None) is None


def test_the_table_cannot_be_widened_at_runtime() -> None:
    with pytest.raises(TypeError):
        cast("dict[str, int]", WEAPONS)["minecraft:stone_axe"] = 99
