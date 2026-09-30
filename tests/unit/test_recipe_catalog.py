"""Where a product id stops being a guess.

A recipe is knowledge about the game, not about Minekin, and the design rule the catalog is
built to hold is that nobody invents one at runtime: not a model, not a skill, not a plan
author in a hurry. What lives here is curated, and what these tests pin down is the shape of
the answer when the curated set cannot serve the ask — three named preconditions, one per
reason a craft cannot run, rather than an empty outcome a caller would have to interpret.

Nothing here reads the world. The bag is passed in as an argument precisely so that the
material check is a decision made *from a reading* by whoever holds one, and never a claim
this module makes about a world it has not seen.
"""

from __future__ import annotations

from minekin_core.domain.perception import InventoryStackValue, InventoryValue
from minekin_core.domain.recipe_catalog import (
    CRAFT_GRID_TOO_SMALL,
    CRAFT_MATERIALS_MISSING,
    CRAFT_RECIPE_UNAVAILABLE,
    PLAYER_GRID_SIDE,
    RECIPES,
    Recipe,
    resolve_craft,
)

LOG = "minecraft:oak_log"
PLANKS = "minecraft:oak_planks"
STICK = "minecraft:stick"
TABLE = "minecraft:crafting_table"
PICKAXE = "minecraft:wooden_pickaxe"


def bag(*pairs: tuple[str, int]) -> InventoryValue:
    return InventoryValue(
        revision=7,
        stacks=tuple(
            InventoryStackValue(slot=slot, item_id=item_id, count=count)
            for slot, (item_id, count) in enumerate(pairs)
        ),
    )


def test_a_product_resolves_to_the_recipe_the_game_uses_for_it() -> None:
    resolved = resolve_craft(PLANKS)

    assert isinstance(resolved, Recipe)
    assert (resolved.recipe_id, resolved.product_id) == (PLANKS, PLANKS)
    assert resolved.ingredients == ((LOG, 1),)
    assert resolved.yields == 4


def test_the_same_resolver_answers_for_a_recipe_no_fixture_elsewhere_names() -> None:
    """The reuse the slice is judged on: a product that appears in no chain, no demo plan and
    no mind constant still resolves through the one call, and says whether the grid the skill
    opens can hold it."""

    resolved = resolve_craft(TABLE)

    assert isinstance(resolved, Recipe)
    assert resolved.ingredients == ((PLANKS, 4),)
    assert resolved.fits(PLAYER_GRID_SIDE)


def test_an_unlisted_product_is_refused_by_name_rather_than_invented() -> None:
    assert resolve_craft("minecraft:diamond_pickaxe") == CRAFT_RECIPE_UNAVAILABLE


def test_a_bag_that_cannot_pay_is_refused_by_name() -> None:
    assert resolve_craft(STICK, inventory=bag((PLANKS, 1))) == CRAFT_MATERIALS_MISSING
    assert isinstance(resolve_craft(STICK, inventory=bag((PLANKS, 2))), Recipe)


def test_a_shape_the_open_grid_cannot_hold_is_refused_by_name() -> None:
    assert resolve_craft(PICKAXE, grid_side=PLAYER_GRID_SIDE) == CRAFT_GRID_TOO_SMALL

    on_table = resolve_craft(PICKAXE, grid_side=3, inventory=bag((PLANKS, 3), (STICK, 2)))
    assert isinstance(on_table, Recipe)
    assert on_table.ingredients == ((PLANKS, 3), (STICK, 2))


def test_the_grid_is_checked_before_the_bag_so_the_lasting_obstacle_is_the_one_named() -> None:
    """An empty bag and an impossible shape are both true of the same reading. The one that
    says something a fresh stack of planks would not change is the more useful answer, and a
    mind that was told "materials missing" would go gather wood it already has enough of."""

    assert resolve_craft(PICKAXE, grid_side=PLAYER_GRID_SIDE, inventory=bag()) == (
        CRAFT_GRID_TOO_SMALL
    )


def test_a_square_grid_holds_a_tall_recipe_because_the_player_may_rotate_it() -> None:
    stick = RECIPES[STICK]

    assert (stick.grid_width, stick.grid_height) == (1, 2)
    assert stick.fits(2)
    assert not stick.fits(1)


def test_the_player_grid_is_the_two_by_two_the_inventory_screen_opens() -> None:
    assert PLAYER_GRID_SIDE == 2


def test_every_entry_names_itself_by_product_and_costs_a_positive_amount() -> None:
    """A catalog read by product id is only honest if the product id is the key, and a
    recipe whose ingredient count is zero would let a resolver claim an item is free."""

    for product_id, recipe in RECIPES.items():
        assert recipe.product_id == product_id
        assert recipe.recipe_id
        assert recipe.yields >= 1
        assert recipe.grid_width >= 1 and recipe.grid_height >= 1
        assert all(count >= 1 for _, count in recipe.ingredients)
        assert recipe.fits(3)
