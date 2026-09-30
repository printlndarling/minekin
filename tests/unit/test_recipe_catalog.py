"""Where a product id stops being a guess.

A recipe is knowledge about the game, not about Minekin, and the design rule the catalog is
built to hold is that nobody invents one at runtime: not a model, not a skill, not a plan
author in a hurry. What lives here is curated, and what these tests pin down is the shape of
the answer when the curated set cannot serve the ask — three named preconditions, one per
reason a craft cannot run, rather than an empty outcome a caller would have to interpret.

Nothing here reads the world. The bag is passed in as an argument precisely so that the
material check is a decision made *from a reading* by whoever holds one, and never a claim
this module makes about a world it has not seen. The same argument covers the counts a plan is
netted to: `build_plan` can say what a pickaxe owes, and only a caller that has been handed an
inventory can say what this Kin still owes.
"""

from __future__ import annotations

import pytest

from minekin_core.domain import recipe_catalog
from minekin_core.domain.perception import InventoryStackValue, InventoryValue
from minekin_core.domain.recipe_catalog import (
    CRAFT_GRID_TOO_SMALL,
    CRAFT_MATERIALS_MISSING,
    CRAFT_RECIPE_UNAVAILABLE,
    PLAYER_GRID_SIDE,
    RECIPES,
    BuildStep,
    Recipe,
    build_plan,
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


# ------------------------------------------------------------------ what a goal implies, in order


def shaped(plan: object) -> list[tuple[str, int]]:
    """The plan as `(product, how many it still wants)`, which is every decision a caller makes
    from it. Written once so the tests below say the order and the counts and nothing else."""

    assert isinstance(plan, tuple)
    return [(step.product_id, step.required_total) for step in plan]


def test_a_goal_product_becomes_the_build_order_its_recipes_imply() -> None:
    planned = build_plan(PICKAXE)

    assert shaped(planned) == [(PLANKS, 5), (STICK, 2), (PICKAXE, 1)]
    assert [step.recipe.recipe_id for step in planned] == [PLANKS, STICK, PICKAXE]


def test_the_counts_come_from_the_recipes_yields_not_from_a_number_somebody_typed_in() -> None:
    """Five planks, where the demo fixture said three: the pickaxe eats three and the one stick
    batch it also eats eats two more. `yields` is the only thing that turns a shape into a
    count, and a plan that skipped it would send the Kin back to the trunk for a load that
    cannot finish the job — a wrong number is the failure mode this whole module exists to have
    no room for."""

    planks = build_plan(PICKAXE)[0]

    assert (planks.product_id, planks.required_total) == (PLANKS, 5)
    assert planks.recipe.yields == 4
    assert planks.materials == ((LOG, 1),)


def test_the_same_call_answers_for_products_no_chain_names() -> None:
    """The reuse the slice is judged on: three different goals, one call, no per-goal code."""

    assert shaped(build_plan(TABLE)) == [(PLANKS, 4), (TABLE, 1)]
    assert shaped(build_plan(STICK)) == [(PLANKS, 2), (STICK, 1)]
    assert shaped(build_plan(PLANKS)) == [(PLANKS, 1)]


def test_an_ingredient_nobody_crafts_stops_the_plan_there_instead_of_inventing_a_craft() -> None:
    """Oak logs are gathered, not crafted, and the plan's last step is allowed to cost them:
    the thing a caller acts on is 'break a trunk', which is a skill it already has."""

    planned = build_plan(PLANKS)

    assert shaped(planned) == [(PLANKS, 1)]
    assert planned[0].materials == ((LOG, 1),)


def test_asking_for_more_scales_the_counts_without_repeating_a_step() -> None:
    """Five sticks is two batches and four planks. The step's number stays what the goal owes
    rather than what the batches leave over, because a caller compares it to an inventory."""

    assert shaped(build_plan(STICK, quantity=5)) == [(PLANKS, 4), (STICK, 5)]


def test_a_bag_that_holds_part_of_the_plan_is_credited_against_it() -> None:
    """Netting, which is the difference between a plan and a script: three planks and two
    sticks is exactly one pickaxe's worth of intermediates, so the only step still owed is the
    pickaxe. Four planks is one short of what the whole job eats, so planks stay on the list
    with the remainder — not with the gross figure."""

    assert shaped(build_plan(PICKAXE, inventory=bag((PLANKS, 3), (STICK, 2)))) == [
        (PLANKS, 0),
        (STICK, 0),
        (PICKAXE, 1),
    ]
    assert shaped(build_plan(PICKAXE, inventory=bag((PLANKS, 4)))) == [
        (PLANKS, 1),
        (STICK, 2),
        (PICKAXE, 1),
    ]


def test_a_bag_that_already_holds_the_goal_leaves_no_step_outstanding() -> None:
    assert shaped(build_plan(PICKAXE, inventory=bag((PICKAXE, 1)))) == [
        (PLANKS, 0),
        (STICK, 0),
        (PICKAXE, 0),
    ]


def test_a_goal_the_table_cannot_answer_for_is_refused_by_name() -> None:
    assert build_plan("minecraft:diamond_pickaxe") == CRAFT_RECIPE_UNAVAILABLE


def test_a_recipe_that_eats_itself_is_refused_by_name_rather_than_recursed_into(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing curated today loops, and a wrong row is the realistic way a plan meets one. The
    alternative is a `RecursionError` where the caller was promised one of the named words."""

    monkeypatch.setattr(
        recipe_catalog,
        "RECIPES",
        {
            PLANKS: Recipe(
                product_id=PLANKS,
                recipe_id=PLANKS,
                ingredients=((STICK, 1),),
                grid_width=1,
                grid_height=1,
                yields=4,
            ),
            STICK: Recipe(
                product_id=STICK,
                recipe_id=STICK,
                ingredients=((PLANKS, 1),),
                grid_width=1,
                grid_height=2,
                yields=4,
            ),
        },
    )

    assert build_plan(PLANKS) == CRAFT_RECIPE_UNAVAILABLE
    assert build_plan(STICK) == CRAFT_RECIPE_UNAVAILABLE


def test_the_plan_orders_steps_without_deciding_which_grid_they_run_in() -> None:
    """Which screen holds a shape is a fact about the reading, not about the recipe, and a
    resolver that dropped the three-by-three step here would hide the two steps that do fit —
    the Kin would be told to gather for a job its grid cannot ever show. `resolve_craft`, and
    the mind that holds a reading, are where a grid gets named."""

    planned = build_plan(PICKAXE)

    assert not planned[-1].recipe.fits(PLAYER_GRID_SIDE)
    assert planned[-1].recipe.fits(3)
    assert all(step.recipe.fits(PLAYER_GRID_SIDE) for step in planned[:-1])


def test_a_step_carries_no_knowledge_but_the_recipe_it_was_read_from() -> None:
    """A step is a recipe plus a count. It re-declares neither the product id nor the
    ingredients, so there stays exactly one place a game fact can be wrong."""

    planned = build_plan(TABLE)

    assert all(isinstance(step, BuildStep) for step in planned)
    assert all(step.product_id == step.recipe.product_id for step in planned)
    assert all(step.materials == step.recipe.ingredients for step in planned)
