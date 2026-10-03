"""The interim food table, pinned where it is written.

The table is a *boundary* as much as a list: it says which items this build knows how to
eat, and its whole product claim is that nothing outside it is ever attempted by the
consume skill. These cells keep that boundary honest — the rows are foods with positive
points, the lookups are type- and value-strict, the mapping cannot be widened at runtime,
and the product path (the mind, the skill, the refusals) names no food itself, exactly the
way the recipe catalog is the only place in the product a recipe may live.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from minekin_core.domain.food_catalog import FOODS, is_known_food, nutrition_for


def test_every_row_is_a_food_with_points() -> None:
    assert FOODS
    for item_id, points in FOODS.items():
        assert item_id.startswith("minecraft:")
        assert points > 0
        assert is_known_food(item_id)
        assert nutrition_for(item_id) == points


def test_anything_outside_the_table_is_not_food_for_this_build() -> None:
    for item_id in ("minecraft:oak_log", "minecraft:stone", "minecraft:potion"):
        assert not is_known_food(item_id)
        assert nutrition_for(item_id) is None
    # The lookups are strict about types as well as values: an endpoint's answer or a
    # reading is not guaranteed to be a string, and a non-string must not read like a
    # statement about food.
    assert not is_known_food(None)
    assert not is_known_food(4)
    assert nutrition_for(None) is None


def test_the_table_cannot_be_widened_at_runtime() -> None:
    with pytest.raises(TypeError):
        cast("dict[str, int]", FOODS)["minecraft:apple"] = 99


@pytest.mark.parametrize(
    "module",
    ["application/player_mind.py", "application/world_skills.py", "domain/world_actions.py"],
)
def test_the_product_path_never_names_a_food(module: str) -> None:
    source = (Path(__file__).resolve().parents[2] / "src" / "minekin_core" / module).read_text(
        encoding="utf-8"
    )
    for item_id in FOODS:
        assert item_id not in source, f"{module} names {item_id}"
