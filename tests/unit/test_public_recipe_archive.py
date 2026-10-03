"""Public knowledge retains source semantics without granting runtime authority."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import zipfile
from collections.abc import Mapping
from itertools import product
from pathlib import Path

import pytest

from minekin_core.adapters.public_recipe_archive import load_recipe_knowledge


def jar(
    documents: dict[str, object],
    *,
    version: str = "1.20.1",
    tags: Mapping[str, object] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("version.json", json.dumps({"id": version}))
        for recipe_id, document in documents.items():
            namespace, name = recipe_id.split(":")
            archive.writestr(f"data/{namespace}/recipes/{name}.json", json.dumps(document))
        for tag_id, document in (tags or {}).items():
            namespace, name = tag_id.split(":")
            archive.writestr(f"data/{namespace}/tags/items/{name}.json", json.dumps(document))
    return buffer.getvalue()


def shaped() -> dict[str, object]:
    return {
        "type": "minecraft:crafting_shaped",
        "pattern": ["XXX", " # ", " # "],
        "key": {"X": {"tag": "minecraft:planks"}, "#": {"item": "minecraft:stick"}},
        "result": {"item": "minecraft:wooden_pickaxe"},
    }


def path_for(tmp_path: Path, raw: bytes) -> Path:
    path = tmp_path / "version.jar"
    path.write_bytes(raw)
    return path


def test_shaped_slots_keep_tags_and_empty_cells(tmp_path: Path) -> None:
    raw = jar({"minecraft:wooden_pickaxe": shaped()})
    knowledge = load_recipe_knowledge(path_for(tmp_path, raw), game_version="1.20.1")
    recipe = knowledge.for_product("minecraft:wooden_pickaxe")[0]
    assert (recipe.width, recipe.height, recipe.count) == (3, 3, 1)
    assert len(recipe.slots) == 9
    assert recipe.slots[0][0].kind == "tag"
    assert recipe.slots[0][0].identifier == "minecraft:planks"
    assert recipe.slots[3] == ()
    assert recipe.slots[4][0].identifier == "minecraft:stick"
    assert knowledge.digest_matched is False
    assert knowledge.for_product("minecraft:unknown") == ()


def test_shapeless_alternatives_and_multiple_recipe_variants_are_not_guessed(
    tmp_path: Path,
) -> None:
    first = {
        "type": "minecraft:crafting_shapeless",
        "ingredients": [[{"item": "minecraft:a"}, {"tag": "minecraft:b"}]],
        "result": {"item": "minecraft:output", "count": 4},
    }
    raw = jar({"minecraft:first": first, "minecraft:second": first})
    knowledge = load_recipe_knowledge(path_for(tmp_path, raw), game_version="1.20.1")
    recipes = knowledge.for_product("minecraft:output")
    assert len(recipes) == 2
    assert [option.kind for option in recipes[0].slots[0]] == ["item", "tag"]
    assert recipes[0].count == 4
    assert recipes[0].document_sha256 == recipes[1].document_sha256


def test_reads_nested_server_archive_with_exact_version_and_digest(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "META-INF/versions/1.20.1/server-1.20.1.jar", jar({"minecraft:tool": shaped()})
        )
    raw = buffer.getvalue()
    knowledge = load_recipe_knowledge(
        path_for(tmp_path, raw),
        game_version="1.20.1",
        expected_sha256=hashlib.sha256(raw).hexdigest(),
    )
    assert knowledge.digest_matched is True
    assert len(knowledge.recipes) == 1


def test_reports_special_recipes_as_unsupported_instead_of_inventing_a_shape(
    tmp_path: Path,
) -> None:
    raw = jar({"minecraft:special": {"type": "minecraft:crafting_special_armordye"}})
    knowledge = load_recipe_knowledge(path_for(tmp_path, raw), game_version="1.20.1")
    assert knowledge.recipes == ()
    assert dict(knowledge.unsupported_types) == {"minecraft:crafting_special_armordye": 1}


@pytest.mark.parametrize("version", ["1.21.4", "../1.20.1"])
def test_refuses_version_mismatch_or_path_injection(tmp_path: Path, version: str) -> None:
    with pytest.raises(ValueError, match=r"RECIPE_.*VERSION"):
        load_recipe_knowledge(
            path_for(tmp_path, jar({"minecraft:tool": shaped()})), game_version=version
        )


def test_refuses_wrong_digest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="RECIPE_DIGEST_MISMATCH"):
        load_recipe_knowledge(
            path_for(tmp_path, jar({"minecraft:tool": shaped()})),
            game_version="1.20.1",
            expected_sha256="0" * 64,
        )


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"pattern": ["XXXX"]}, "SHAPE"),
        ({"key": {"X": {"item": "minecraft:x"}}}, "SHAPE"),
        ({"result": {"item": "minecraft:x", "count": True}}, "COUNT"),
        ({"result": {"item": "minecraft:../secret"}}, "IDENTIFIER"),
        (
            {
                "key": {
                    "X": {"item": "minecraft:x", "tag": "minecraft:y"},
                    "#": {"item": "minecraft:z"},
                }
            },
            "INGREDIENT",
        ),
    ],
)
def test_invalid_supported_recipe_fails_whole_source(
    tmp_path: Path, change: dict[str, object], reason: str
) -> None:
    document = shaped() | change
    with pytest.raises(ValueError, match=f"RECIPE_INVALID_{reason}"):
        load_recipe_knowledge(
            path_for(tmp_path, jar({"minecraft:valid": shaped(), "minecraft:broken": document})),
            game_version="1.20.1",
        )


def test_refuses_duplicate_entries_and_duplicate_json_keys(tmp_path: Path) -> None:
    for duplicate_entry in (False, True):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("version.json", '{"id":"1.20.1","id":"1.20.1"}')
            archive.writestr("data/minecraft/recipes/tool.json", json.dumps(shaped()))
            if duplicate_entry:
                with pytest.warns(UserWarning):
                    archive.writestr("data/minecraft/recipes/tool.json", json.dumps(shaped()))
        with pytest.raises(ValueError, match="RECIPE_DUPLICATE"):
            load_recipe_knowledge(path_for(tmp_path, buffer.getvalue()), game_version="1.20.1")


def test_limits_large_recipe_document(tmp_path: Path) -> None:
    document = shaped() | {"padding": "x" * 65536}
    with pytest.raises(ValueError, match="RECIPE_DOCUMENT_TOO_LARGE"):
        load_recipe_knowledge(
            path_for(tmp_path, jar({"minecraft:tool": document})), game_version="1.20.1"
        )


def test_cli_delivers_source_with_explicit_runtime_unknowns(tmp_path: Path) -> None:
    path = path_for(tmp_path, jar({"minecraft:tool": shaped()}))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.inspect_recipe_knowledge",
            str(path),
            "--version",
            "1.20.1",
            "--product",
            "minecraft:wooden_pickaxe",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["player_recipe_unlocked"] == "unknown"
    assert output["current_materials"] == "not_observed"
    assert output["runtime_planner_connected"] is False
    assert output["recipes"][0]["product_id"] == "minecraft:wooden_pickaxe"


def test_cli_rejects_mismatch_without_emitting_knowledge(tmp_path: Path) -> None:
    path = path_for(tmp_path, jar({"minecraft:tool": shaped()}))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.inspect_recipe_knowledge",
            str(path),
            "--version",
            "1.21.4",
            "--product",
            "minecraft:wooden_pickaxe",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "RECIPE_VERSION_MISMATCH" in result.stderr
    assert result.stdout == ""


def test_public_tags_expand_recursively_and_match_mixed_materials(tmp_path: Path) -> None:
    raw = jar(
        {"minecraft:tool": shaped()},
        tags={
            "minecraft:planks": {"values": ["#minecraft:wood", "minecraft:birch_planks"]},
            "minecraft:wood": {"values": ["minecraft:oak_planks"]},
        },
    )
    knowledge = load_recipe_knowledge(path_for(tmp_path, raw), game_version="1.20.1")
    assert knowledge.item_tags["minecraft:planks"] == (
        "minecraft:birch_planks",
        "minecraft:oak_planks",
    )
    inventory = {"minecraft:oak_planks": 2, "minecraft:birch_planks": 1, "minecraft:stick": 2}
    cells = knowledge.materials_for("minecraft:tool", inventory)
    assert cells is not None
    assert cells.count("minecraft:oak_planks") == 2
    assert cells.count("minecraft:birch_planks") == 1
    assert cells.count("minecraft:stick") == 2
    assert cells.count(None) == 4
    assert inventory == {
        "minecraft:oak_planks": 2,
        "minecraft:birch_planks": 1,
        "minecraft:stick": 2,
    }
    assert knowledge.materials_for("minecraft:tool", inventory | {"minecraft:stick": 1}) is None


def test_alternative_matching_reroutes_instead_of_greedy_false_failure(tmp_path: Path) -> None:
    document = {
        "type": "minecraft:crafting_shapeless",
        "ingredients": [
            [{"item": "minecraft:a"}, {"item": "minecraft:b"}],
            {"item": "minecraft:a"},
        ],
        "result": {"item": "minecraft:output"},
    }
    knowledge = load_recipe_knowledge(
        path_for(tmp_path, jar({"minecraft:recipe": document})), game_version="1.20.1"
    )
    assert knowledge.materials_for("minecraft:recipe", {"minecraft:a": 1, "minecraft:b": 1}) == (
        "minecraft:b",
        "minecraft:a",
    )
    assert knowledge.materials_for("minecraft:recipe", {"minecraft:a": 1}) is None
    assert knowledge.materials_for("minecraft:recipe", {"minecraft:a": True}) is None
    assert knowledge.materials_for("minecraft:recipe", {"minecraft:a": -1}) is None


def test_missing_tag_is_unknown_not_implicitly_any_owned_item(tmp_path: Path) -> None:
    knowledge = load_recipe_knowledge(
        path_for(tmp_path, jar({"minecraft:tool": shaped()})), game_version="1.20.1"
    )
    assert (
        knowledge.materials_for(
            "minecraft:tool", {"minecraft:oak_planks": 64, "minecraft:stick": 64}
        )
        is None
    )
    assert knowledge.materials_for("minecraft:unknown", {}) is None


@pytest.mark.parametrize(
    "tags,reason",
    [
        ({"minecraft:a": {"values": ["#minecraft:a"]}}, "CYCLE_OR_DEPTH"),
        (
            {
                "minecraft:a": {"values": ["#minecraft:b"]},
                "minecraft:b": {"values": ["#minecraft:a"]},
            },
            "CYCLE_OR_DEPTH",
        ),
        ({"minecraft:a": {"values": ["#minecraft:absent"]}}, "REFERENCE_MISSING"),
    ],
)
def test_tag_cycles_and_required_missing_references_are_refused(
    tmp_path: Path, tags: dict[str, object], reason: str
) -> None:
    with pytest.raises(ValueError, match=f"RECIPE_TAG_{reason}"):
        load_recipe_knowledge(
            path_for(tmp_path, jar({"minecraft:tool": shaped()}, tags=tags)), game_version="1.20.1"
        )


def test_optional_missing_tag_is_explicitly_optional(tmp_path: Path) -> None:
    tags = {
        "minecraft:a": {
            "values": [{"id": "#minecraft:missing", "required": False}, "minecraft:stick"]
        }
    }
    knowledge = load_recipe_knowledge(
        path_for(tmp_path, jar({"minecraft:tool": shaped()}, tags=tags)), game_version="1.20.1"
    )
    assert knowledge.item_tags["minecraft:a"] == ("minecraft:stick",)


def test_matching_agrees_with_exhaustive_small_inventory_oracle(tmp_path: Path) -> None:
    alternatives = (("minecraft:a",), ("minecraft:b",), ("minecraft:a", "minecraft:b"))
    for slots in product(alternatives, repeat=3):
        document = {
            "type": "minecraft:crafting_shapeless",
            "ingredients": [[{"item": item} for item in slot] for slot in slots],
            "result": {"item": "minecraft:output"},
        }
        knowledge = load_recipe_knowledge(
            path_for(tmp_path, jar({"minecraft:recipe": document})), game_version="1.20.1"
        )
        for a_count, b_count in product(range(3), repeat=2):
            inventory = {"minecraft:a": a_count, "minecraft:b": b_count}
            possible = any(
                choice.count("minecraft:a") <= a_count and choice.count("minecraft:b") <= b_count
                for choice in product(*slots)
            )
            matched = knowledge.materials_for("minecraft:recipe", inventory)
            assert (matched is not None) == possible
            if matched is not None:
                assert matched.count("minecraft:a") <= a_count
                assert matched.count("minecraft:b") <= b_count
                assert all(item in slot for item, slot in zip(matched, slots, strict=True))
