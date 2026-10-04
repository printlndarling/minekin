"""Demand planning must credit observed stock before exploring recipe alternatives."""

import json
import zipfile
from pathlib import Path

from tests.unit.test_public_craft_runtime import reading

from minekin_core.adapters.public_craft_knowledge import PublicCraftKnowledge
from minekin_core.adapters.public_recipe_archive import load_recipe_knowledge
from minekin_core.domain.recipe_catalog import BuildStep


def knowledge(
    tmp_path: Path, recipes: dict[str, tuple[list[object], str, int]]
) -> PublicCraftKnowledge:
    path = tmp_path / "recipes.jar"
    with zipfile.ZipFile(path, "w") as jar:
        jar.writestr("version.json", json.dumps({"id": "1.20.1"}))
        for name, (ingredients, product, count) in recipes.items():
            jar.writestr(
                f"data/minecraft/recipes/{name}.json",
                json.dumps(
                    {
                        "type": "minecraft:crafting_shapeless",
                        "ingredients": ingredients,
                        "result": {"item": product, "count": count},
                    }
                ),
            )
    return PublicCraftKnowledge(load_recipe_knowledge(path, game_version="1.20.1"))


def item(name: str) -> dict[str, str]:
    return {"item": f"minecraft:{name}"}


def test_owned_cycle_ingredient_does_not_expand_back_into_goal(tmp_path: Path) -> None:
    source = knowledge(
        tmp_path,
        {
            "ingot": ([item("nugget")] * 9, "minecraft:ingot", 1),
            "nugget": ([item("ingot")], "minecraft:nugget", 9),
        },
    )
    step = source.step_toward("minecraft:ingot", reading({"minecraft:nugget": 9}), grid_side=3)
    assert isinstance(step, BuildStep)
    assert step.recipe.product_id == "minecraft:ingot"
    assert (
        source.missing_raw("minecraft:ingot", reading({"minecraft:nugget": 9}), grid_side=3) == {}
    )


def test_alternative_uses_owned_raw_material_instead_of_alphabetical_branch(tmp_path: Path) -> None:
    source = knowledge(
        tmp_path,
        {
            "acacia_planks": ([item("acacia_log")], "minecraft:acacia_planks", 4),
            "oak_planks": ([item("oak_log")], "minecraft:oak_planks", 4),
            "stick": ([[item("acacia_planks"), item("oak_planks")]] * 2, "minecraft:stick", 4),
        },
    )
    frame = reading({"minecraft:oak_log": 1})
    step = source.step_toward("minecraft:stick", frame, grid_side=2)
    assert isinstance(step, BuildStep)
    assert step.recipe.product_id == "minecraft:oak_planks"
    assert source.missing_raw("minecraft:stick", frame, grid_side=2) == {}
    chain = source.owed_chain("minecraft:stick", frame, grid_side=2)
    assert not isinstance(chain, str)
    assert [entry.product_id for entry in chain] == ["minecraft:oak_planks", "minecraft:stick"]


def test_cyclic_variant_does_not_poison_valid_variant(tmp_path: Path) -> None:
    source = knowledge(
        tmp_path,
        {
            "a_cycle": ([item("target")], "minecraft:target", 1),
            "z_valid": ([item("raw")], "minecraft:target", 1),
        },
    )
    step = source.step_toward("minecraft:target", reading({"minecraft:raw": 1}), grid_side=2)
    assert isinstance(step, BuildStep)
    assert step.recipe.recipe_id == "minecraft:z_valid"


def test_shared_stock_and_batch_surplus_are_not_double_spent(tmp_path: Path) -> None:
    source = knowledge(
        tmp_path,
        {
            "planks": ([item("log")], "minecraft:planks", 4),
            "target": ([item("planks")] * 3, "minecraft:target", 1),
        },
    )
    frame = reading({"minecraft:log": 1})
    assert source.missing_raw("minecraft:target", frame, quantity=2, grid_side=2) == {
        "minecraft:log": 1
    }


def test_payable_or_cells_reserve_the_only_option_for_a_later_cell(tmp_path: Path) -> None:
    source = knowledge(
        tmp_path,
        {
            "target": ([[item("a"), item("b")], item("a")], "minecraft:target", 1),
        },
    )
    frame = reading({"minecraft:a": 1, "minecraft:b": 1})
    assert source.missing_raw("minecraft:target", frame, grid_side=2) == {}
    assert isinstance(source.step_toward("minecraft:target", frame, grid_side=2), BuildStep)


def test_unfunded_cycle_still_refuses(tmp_path: Path) -> None:
    source = knowledge(
        tmp_path,
        {
            "a": ([item("b")], "minecraft:a", 1),
            "b": ([item("a")], "minecraft:b", 1),
        },
    )
    assert source.owed_chain("minecraft:a", reading({}), grid_side=2) == "CRAFT_RECIPE_UNAVAILABLE"
