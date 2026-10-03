"""Imported public knowledge reaches model offers and generic calls, not success claims."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Mapping
from pathlib import Path

import pytest

from minekin_core.adapters.public_craft_knowledge import PublicCraftKnowledge
from minekin_core.adapters.public_recipe_archive import load_recipe_knowledge
from minekin_core.application.player_mind import MindDecisionKind, mind_for
from minekin_core.cli.session import mind_for_run
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.goal_spec import Milestone
from minekin_core.domain.model_access import CostLedger, Decision, DecisionRequest
from minekin_core.domain.perception import (
    GuiScreenValue,
    InventoryStackValue,
    InventoryValue,
    SelfStateValue,
    WorldObservationValue,
)
from minekin_core.domain.recipe_catalog import BuildStep, RecipeProvenance


def archive(tmp_path: Path) -> Path:
    path = tmp_path / "public.jar"
    with zipfile.ZipFile(path, "w") as jar:
        jar.writestr("version.json", json.dumps({"id": "1.20.1"}))
        jar.writestr(
            "data/minecraft/tags/items/stone_tool_materials.json",
            json.dumps({"values": ["minecraft:cobblestone", "minecraft:cobbled_deepslate"]}),
        )
        for name, document in {
            "stone_pickaxe": {
                "type": "minecraft:crafting_shaped",
                "pattern": ["XXX", " # ", " # "],
                "key": {
                    "X": {"tag": "minecraft:stone_tool_materials"},
                    "#": {"item": "minecraft:stick"},
                },
                "result": {"item": "minecraft:stone_pickaxe"},
            },
            "bread": {
                "type": "minecraft:crafting_shaped",
                "pattern": ["XXX"],
                "key": {"X": {"item": "minecraft:wheat"}},
                "result": {"item": "minecraft:bread"},
            },
            "oak_planks": {
                "type": "minecraft:crafting_shapeless",
                "ingredients": [{"item": "minecraft:oak_log"}],
                "result": {"item": "minecraft:oak_planks", "count": 4},
            },
            "stick": {
                "type": "minecraft:crafting_shaped",
                "pattern": ["#", "#"],
                "key": {"#": {"item": "minecraft:oak_planks"}},
                "result": {"item": "minecraft:stick", "count": 4},
            },
        }.items():
            jar.writestr(f"data/minecraft/recipes/{name}.json", json.dumps(document))
    return path


def reading(
    items: Mapping[str, int],
    *,
    gui: GuiScreenValue | None = None,
    alive: bool = True,
    selected_slot: int = 0,
) -> WorldObservationValue:
    return WorldObservationValue(
        generation=1,
        game_tick=100,
        self_state=SelfStateValue(
            health=20,
            max_health=20,
            food=20,
            saturation=5,
            alive=alive,
            x=0,
            y=64,
            z=0,
            yaw_degrees=0,
            pitch_degrees=0,
            selected_slot=selected_slot,
        ),
        aim=None,
        inventory=InventoryValue(
            1,
            tuple(
                InventoryStackValue(index, item, count)
                for index, (item, count) in enumerate(items.items())
            ),
        ),
        visible_entities=(),
        mining=None,
        gui=gui,
    )


class Provider:
    def __init__(self, target: str) -> None:
        self.target = target
        self.requests: list[DecisionRequest] = []

    def decide(self, request: DecisionRequest) -> Decision:
        self.requests.append(request)
        return Decision(
            skill_id="craft_take_result",
            reason="make the requested item",
            intent_generation=request.intent_generation,
            arguments={"target_item": self.target, "quantity": 1},
        )


def source(tmp_path: Path) -> PublicCraftKnowledge:
    return PublicCraftKnowledge(load_recipe_knowledge(archive(tmp_path), game_version="1.20.1"))


@pytest.mark.parametrize(
    "target,items,materials",
    [
        (
            "minecraft:stone_pickaxe",
            {"minecraft:cobblestone": 2, "minecraft:cobbled_deepslate": 1, "minecraft:stick": 2},
            {"minecraft:cobblestone": 2, "minecraft:cobbled_deepslate": 1, "minecraft:stick": 2},
        ),
        ("minecraft:bread", {"minecraft:wheat": 3}, {"minecraft:wheat": 3}),
    ],
)
def test_model_parameters_select_different_imported_products_on_same_skill(
    tmp_path: Path, target: str, items: dict[str, int], materials: dict[str, int]
) -> None:
    provider = Provider(target)
    mind = mind_for(provider, CostLedger(run_cost_cap=1000), craft_knowledge=source(tmp_path))
    current = reading(items, gui=GuiScreenValue("minecraft:crafting", 4, frozenset({target})))
    intent = mind.next_intent(current)
    assert intent.kind is MindDecisionKind.INTENT
    assert intent.source == "model"
    assert intent.skill == "craft_take_result"
    call = intent.plan.calls[0]
    assert call.product_id == call.recipe_id == target
    assert dict(call.materials) == materials
    request = provider.requests[0]
    offered = request.observation_summary["craft_options"]
    assert isinstance(offered, list)
    assert target in offered
    assert "craft_take_result" in request.feasible_skill_ids
    assert mind.as_document()["last_result"] == ""
    assert mind.goal_met is False
    assert mind.public_crafts(current)[target].provenance is RecipeProvenance.PUBLIC_VERSION


def test_live_gui_absence_cannot_be_overridden_by_public_or_old_curated_recipe(
    tmp_path: Path,
) -> None:
    provider = Provider("minecraft:oak_planks")
    mind = mind_for(provider, CostLedger(run_cost_cap=1000), craft_knowledge=source(tmp_path))
    current = reading({"minecraft:oak_log": 1}, gui=GuiScreenValue("minecraft:inventory", 0))
    assert mind.public_crafts(current) == {}
    assert mind.craft_options_for(current) == ()
    assert "craft_take_result" not in mind.feasible_skills(current)
    assert mind.craft_knowledge is not None
    assert (
        mind.craft_knowledge.refusal_for("minecraft:oak_planks", current, grid_side=2)
        == "GUI_RECIPE_UNKNOWN"
    )


def test_missing_material_grid_and_dead_player_do_not_get_public_offer(tmp_path: Path) -> None:
    knowledge = source(tmp_path)
    provider = Provider("minecraft:stone_pickaxe")
    mind = mind_for(provider, CostLedger(run_cost_cap=1000), craft_knowledge=knowledge)
    items = {"minecraft:cobblestone": 3, "minecraft:stick": 2}
    assert (
        knowledge.refusal_for("minecraft:stone_pickaxe", reading(items), grid_side=2)
        == "CRAFT_GRID_TOO_SMALL"
    )
    assert "craft_take_result" not in mind.feasible_skills(reading(items))
    assert (
        knowledge.refusal_for(
            "minecraft:stone_pickaxe", reading({"minecraft:cobblestone": 3}), grid_side=3
        )
        == "CRAFT_MATERIALS_MISSING"
    )
    assert mind.feasible_skills(reading(items, alive=False)) == ()


def test_current_inventory_changes_revoke_public_offer(tmp_path: Path) -> None:
    mind = mind_for(
        Provider("minecraft:bread"), CostLedger(run_cost_cap=1000), craft_knowledge=source(tmp_path)
    )
    gui = GuiScreenValue("minecraft:crafting", 4, frozenset({"minecraft:bread"}))
    assert "craft_take_result" in mind.feasible_skills(reading({"minecraft:wheat": 3}, gui=gui))
    assert "craft_take_result" not in mind.feasible_skills(reading({"minecraft:wheat": 2}, gui=gui))


def test_cli_composition_binds_knowledge_to_actual_launch_version(tmp_path: Path) -> None:
    path = archive(tmp_path)
    environment = {"MINEKIN_MODEL_PROVIDER": "off", "MINEKIN_RECIPE_ARCHIVE": str(path)}
    mind = mind_for_run("kin-one", environment, game_version="1.20.1")
    assert mind.craft_knowledge is not None
    assert mind.craft_knowledge.knows_product("minecraft:bread")
    with pytest.raises(MinekinError, match="actual launched game version"):
        mind_for_run("kin-one", environment)
    with pytest.raises(MinekinError, match="RECIPE_VERSION_MISMATCH"):
        mind_for_run("kin-one", environment, game_version="1.21.4")
    with pytest.raises(MinekinError, match="RECIPE_DIGEST_MISMATCH"):
        mind_for_run(
            "kin-one",
            environment | {"MINEKIN_RECIPE_ARCHIVE_SHA256": "0" * 64},
            game_version="1.20.1",
        )


def test_public_goal_resolves_to_the_first_intermediate_craft_step(tmp_path: Path) -> None:
    provider = Provider("minecraft:stone_pickaxe")
    mind = mind_for(provider, CostLedger(run_cost_cap=1000), craft_knowledge=source(tmp_path))
    current = reading({"minecraft:oak_planks": 2, "minecraft:cobblestone": 3})
    intent = mind.next_intent(current)
    assert intent.kind is MindDecisionKind.INTENT
    assert intent.skill == "craft_take_result"
    call = intent.plan.calls[0]
    assert call.product_id == "minecraft:stick"
    assert call.recipe_id == "minecraft:stick"
    assert dict(call.materials) == {"minecraft:oak_planks": 2}
    knowledge = mind.craft_knowledge
    assert knowledge is not None
    step = knowledge.step_toward("minecraft:stone_pickaxe", current, quantity=1, grid_side=2)
    assert isinstance(step, BuildStep)
    assert step.product_id == "minecraft:stick"
    assert step.required_total == 2


def test_public_chain_closes_on_the_product_once_the_layer_is_paid(tmp_path: Path) -> None:
    knowledge = source(tmp_path)
    gui = GuiScreenValue("minecraft:crafting", 4, frozenset({"minecraft:stone_pickaxe"}))
    current = reading({"minecraft:stick": 2, "minecraft:cobblestone": 3}, gui=gui)
    step = knowledge.step_toward("minecraft:stone_pickaxe", current, quantity=1, grid_side=3)
    assert isinstance(step, BuildStep)
    assert step.product_id == "minecraft:stone_pickaxe"
    assert step.recipe.recipe_id == "minecraft:stone_pickaxe"
    assert dict(step.materials) == {"minecraft:cobblestone": 3, "minecraft:stick": 2}


def test_step_toward_names_missing_raw_materials_before_any_layer_can_pay(
    tmp_path: Path,
) -> None:
    knowledge = source(tmp_path)
    current = reading({"minecraft:cobblestone": 3})
    assert (
        knowledge.step_toward("minecraft:stone_pickaxe", current, quantity=1, grid_side=3)
        == "CRAFT_MATERIALS_MISSING"
    )


def test_step_toward_crafts_the_grid_enabler_before_a_wider_product(tmp_path: Path) -> None:
    knowledge = source(tmp_path)
    current = reading({"minecraft:oak_planks": 4, "minecraft:stick": 2})
    step = knowledge.step_toward("minecraft:stone_pickaxe", current, quantity=1, grid_side=2)
    assert isinstance(step, BuildStep)
    assert step.product_id == "minecraft:crafting_table"
    assert step.recipe.recipe_id == "minecraft:crafting_table"
    assert dict(step.materials) == {"minecraft:oak_planks": 4}


def test_step_toward_says_when_the_held_enabler_is_all_that_is_left(tmp_path: Path) -> None:
    knowledge = source(tmp_path)
    current = reading({"minecraft:crafting_table": 1})
    assert (
        knowledge.step_toward("minecraft:stone_pickaxe", current, quantity=1, grid_side=2)
        == "CRAFT_GRID_TOO_SMALL"
    )


def test_step_toward_names_the_enablers_missing_materials(tmp_path: Path) -> None:
    knowledge = source(tmp_path)
    current = reading({"minecraft:stick": 2, "minecraft:cobblestone": 3})
    assert (
        knowledge.step_toward("minecraft:stone_pickaxe", current, quantity=1, grid_side=2)
        == "CRAFT_MATERIALS_MISSING"
    )


def test_missing_raw_names_the_floor_the_plan_cannot_cover(tmp_path: Path) -> None:
    knowledge = source(tmp_path)
    current = reading({"minecraft:cobblestone": 3})
    assert dict(
        knowledge.missing_raw("minecraft:stone_pickaxe", current, quantity=1, grid_side=3)
    ) == {"minecraft:oak_log": 1}


def test_missing_raw_resolves_a_tag_cell_the_plans_own_way(tmp_path: Path) -> None:
    knowledge = source(tmp_path)
    current = reading({"minecraft:cobblestone": 1})
    assert dict(
        knowledge.missing_raw("minecraft:stone_pickaxe", current, quantity=1, grid_side=3)
    ) == {"minecraft:cobbled_deepslate": 2, "minecraft:oak_log": 1}


def test_public_enabler_to_stand_up_reads_the_held_table_and_its_slot(tmp_path: Path) -> None:
    knowledge = source(tmp_path)
    held = reading(
        {"minecraft:crafting_table": 1, "minecraft:cobblestone": 3, "minecraft:stick": 2}
    )
    stand = knowledge.enabler_to_stand_up("minecraft:stone_pickaxe", held, quantity=1, grid_side=2)
    assert stand is not None
    assert stand[0].product_id == "minecraft:crafting_table"
    assert stand[1] == 0
    wide = reading(
        {"minecraft:crafting_table": 1},
        gui=GuiScreenValue("minecraft:crafting", 4, frozenset({"minecraft:stone_pickaxe"})),
    )
    assert (
        knowledge.enabler_to_stand_up("minecraft:stone_pickaxe", wide, quantity=1, grid_side=3)
        is None
    )


def test_step_toward_defers_to_the_open_screen_recipe_book(tmp_path: Path) -> None:
    knowledge = source(tmp_path)
    items = {"minecraft:oak_planks": 2, "minecraft:cobblestone": 3}
    blind = GuiScreenValue("minecraft:crafting", 4, frozenset())
    assert (
        knowledge.step_toward(
            "minecraft:stone_pickaxe", reading(items, gui=blind), quantity=1, grid_side=3
        )
        == "GUI_RECIPE_UNKNOWN"
    )
    named = GuiScreenValue("minecraft:crafting", 4, frozenset({"minecraft:stick"}))
    step = knowledge.step_toward(
        "minecraft:stone_pickaxe", reading(items, gui=named), quantity=1, grid_side=3
    )
    assert isinstance(step, BuildStep)
    assert step.product_id == "minecraft:stick"


class SkillProvider:
    def __init__(self, skill_id: str) -> None:
        self.skill_id = skill_id
        self.requests: list[DecisionRequest] = []

    def decide(self, request: DecisionRequest) -> Decision:
        self.requests.append(request)
        return Decision(
            skill_id=self.skill_id,
            reason="fixture answer",
            intent_generation=request.intent_generation,
            arguments={},
        )


STONE_PICKAXE_GOAL = Milestone(
    product_id="minecraft:stone_pickaxe",
    source_item_id="minecraft:cobblestone",
    direction="hold_a_stone_pickaxe",
)


def test_public_goal_crafts_the_enabler_before_the_wide_product(tmp_path: Path) -> None:
    provider = Provider("minecraft:stone_pickaxe")
    mind = mind_for(
        provider,
        CostLedger(run_cost_cap=1000),
        goal=STONE_PICKAXE_GOAL,
        craft_knowledge=source(tmp_path),
    )
    intent = mind.next_intent(reading({"minecraft:oak_planks": 4, "minecraft:stick": 2}))
    assert intent.kind is MindDecisionKind.INTENT
    call = intent.plan.calls[0]
    assert call.product_id == "minecraft:crafting_table"
    assert dict(call.materials) == {"minecraft:oak_planks": 4}


def test_public_goal_summary_names_the_held_enabler_to_stand_up(tmp_path: Path) -> None:
    provider = SkillProvider("turn_to")
    mind = mind_for(
        provider,
        CostLedger(run_cost_cap=1000),
        goal=STONE_PICKAXE_GOAL,
        craft_knowledge=source(tmp_path),
    )
    current = reading({"minecraft:crafting_table": 1}, selected_slot=3)
    assert "select_hotbar" in mind.feasible_skills(current)
    mind.next_intent(current)
    summary = provider.requests[0].observation_summary
    assert summary["grid_enabler"] == {
        "product_id": "minecraft:crafting_table",
        "opens_grid_side": 3,
        "held": 1,
        "in_hand": False,
    }


def test_public_grid_block_reroutes_into_standing_the_enabler_up(tmp_path: Path) -> None:
    provider = Provider("minecraft:stone_pickaxe")
    mind = mind_for(
        provider,
        CostLedger(run_cost_cap=1000),
        goal=STONE_PICKAXE_GOAL,
        craft_knowledge=source(tmp_path),
    )
    current = reading(
        {
            "minecraft:crafting_table": 1,
            "minecraft:stick": 2,
            "minecraft:cobblestone": 3,
            "minecraft:oak_planks": 2,
        },
        selected_slot=3,
    )
    intent = mind.next_intent(current)
    assert intent.kind is MindDecisionKind.INTENT
    assert intent.skill == "select_hotbar"
    assert intent.source == "local_reflection"
    assert intent.arguments == {"slot": 0, "expected_item_id": "minecraft:crafting_table"}
    assert mind.last_precondition == "CRAFT_GRID_TOO_SMALL"


def test_public_goal_summary_names_the_uncoverable_raw_floor(tmp_path: Path) -> None:
    provider = SkillProvider("turn_to")
    mind = mind_for(
        provider,
        CostLedger(run_cost_cap=1000),
        goal=STONE_PICKAXE_GOAL,
        craft_knowledge=source(tmp_path),
    )
    mind.next_intent(reading({"minecraft:oak_planks": 4, "minecraft:stick": 2}))
    summary = provider.requests[0].observation_summary
    assert summary["missing_raw"] == {"minecraft:cobbled_deepslate": 3}


def test_public_goal_selects_the_held_enabler_to_stand_it_up(tmp_path: Path) -> None:
    provider = SkillProvider("select_hotbar")
    mind = mind_for(
        provider,
        CostLedger(run_cost_cap=1000),
        goal=STONE_PICKAXE_GOAL,
        craft_knowledge=source(tmp_path),
    )
    intent = mind.next_intent(reading({"minecraft:crafting_table": 1}, selected_slot=3))
    assert intent.kind is MindDecisionKind.INTENT
    call = intent.plan.calls[0]
    assert call.name == "select_hotbar"
    assert call.slot == 0
    assert call.expected_item_id == "minecraft:crafting_table"
