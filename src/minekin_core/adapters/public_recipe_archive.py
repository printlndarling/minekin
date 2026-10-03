"""Read public version recipe knowledge, never a running server's recipe registry.

Archives are not executed or extracted. Item tags and alternatives stay symbolic:
this knowledge cannot claim ingredients are owned, a recipe is unlocked, or a
craft is feasible. The GUI/observation layer must independently establish those.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

_ID = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+\Z")
_ENTRY = re.compile(r"data/([a-z0-9_.-]+)/recipes/([a-z0-9_./-]+)\.json\Z")
_TAG_ENTRY = re.compile(r"data/([a-z0-9_.-]+)/tags/items/([a-z0-9_./-]+)\.json\Z")
_MAX_ARCHIVE = 256 * 1024 * 1024
_MAX_NESTED = 64 * 1024 * 1024
_MAX_JSON = 64 * 1024
_MAX_RECIPES = 8192
_MAX_TOTAL_JSON = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class IngredientOption:
    kind: str  # item or tag; tags are not silently replaced with a guessed item.
    identifier: str


@dataclass(frozen=True, slots=True)
class PublicRecipe:
    recipe_id: str
    product_id: str
    count: int
    recipe_type: str
    width: int
    height: int
    # Row-major cells for shaped recipes (empty tuple = empty cell), or unordered
    # occupied cells for shapeless recipes. Each cell holds OR alternatives.
    slots: tuple[tuple[IngredientOption, ...], ...]
    document_sha256: str


@dataclass(frozen=True, slots=True)
class RecipeKnowledge:
    game_version: str
    archive_sha256: str
    digest_matched: bool
    recipes: tuple[PublicRecipe, ...]
    unsupported_types: Mapping[str, int]
    item_tags: Mapping[str, tuple[str, ...]]

    def for_product(self, product_id: str) -> tuple[PublicRecipe, ...]:
        """All source recipes producing an item; do not guess a preferred variant."""
        return tuple(recipe for recipe in self.recipes if recipe.product_id == product_id)

    def materials_for(
        self, recipe_id: str, inventory: Mapping[str, int]
    ) -> tuple[str | None, ...] | None:
        """Match one batch to caller-supplied counts, retaining empty shaped cells.

        This is public-knowledge planning, NOT current-server craft admission. A
        missing tag is unknown and fails closed; available OR alternatives share
        inventory capacity, so one item cannot pay two cells. No inventory facts
        are saved or fabricated. The caller still checks freshness and GUI state.
        """
        recipe = next((row for row in self.recipes if row.recipe_id == recipe_id), None)
        if recipe is None or any(
            type(count) is not int or count < 0 for count in inventory.values()
        ):
            return None
        candidates: dict[int, tuple[str, ...]] = {}
        for index, slot in enumerate(recipe.slots):
            if not slot:
                continue
            items: set[str] = set()
            for option in slot:
                if option.kind == "item":
                    items.add(option.identifier)
                elif option.identifier not in self.item_tags:
                    return None
                else:
                    items.update(self.item_tags[option.identifier])
            candidates[index] = tuple(sorted(item for item in items if inventory.get(item, 0) > 0))
        allocated: dict[str, list[int]] = {}
        selected: dict[int, str] = {}

        def assign(index: int, seen: set[str]) -> bool:
            # Capacity-constrained bipartite matching; at most nine occupied cells.
            for item in candidates[index]:
                if item in seen:
                    continue
                seen.add(item)
                owners = allocated.setdefault(item, [])
                if len(owners) < inventory[item]:
                    owners.append(index)
                    selected[index] = item
                    return True
                for offset, previous in enumerate(tuple(owners)):
                    if assign(previous, seen):
                        owners[offset] = index
                        selected[index] = item
                        return True
            return False

        if any(not assign(index, set()) for index in candidates):
            return None
        return tuple(selected.get(index) for index in range(len(recipe.slots)))


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("RECIPE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _json(archive: zipfile.ZipFile, name: str) -> tuple[Any, bytes]:
    info = archive.getinfo(name)
    if info.file_size > _MAX_JSON:
        raise ValueError("RECIPE_DOCUMENT_TOO_LARGE")
    raw = archive.read(info)
    return json.loads(raw, object_pairs_hook=_object), raw


def _identifier(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 256
        or not _ID.fullmatch(value)
        or any(segment in {".", ".."} for segment in value.split(":", 1)[1].split("/"))
    ):
        raise ValueError("RECIPE_INVALID_IDENTIFIER")
    return value


def _ingredient(value: Any) -> tuple[IngredientOption, ...]:
    variants = cast(list[Any], value) if isinstance(value, list) else [value]
    if not 1 <= len(variants) <= 64:
        raise ValueError("RECIPE_INVALID_INGREDIENT")
    options: list[IngredientOption] = []
    for variant in variants:
        if not isinstance(variant, dict):
            raise ValueError("RECIPE_INVALID_INGREDIENT")
        option = cast(dict[str, Any], variant)
        if set(option) not in ({"item"}, {"tag"}):
            raise ValueError("RECIPE_INVALID_INGREDIENT")
        kind = next(iter(option))
        options.append(IngredientOption(kind, _identifier(option[kind])))
    return tuple(options)


def _recipe(recipe_id: str, document: dict[str, Any], raw: bytes) -> PublicRecipe:
    result = document.get("result")
    if not isinstance(result, dict):
        raise ValueError("RECIPE_INVALID_RESULT")
    result = cast(dict[str, Any], result)
    product = _identifier(result.get("item"))
    count = result.get("count", 1)
    if type(count) is not int or not 1 <= count <= 64:
        raise ValueError("RECIPE_INVALID_COUNT")
    recipe_type = document["type"]
    if recipe_type == "minecraft:crafting_shapeless":
        ingredients = document.get("ingredients")
        if not isinstance(ingredients, list):
            raise ValueError("RECIPE_INVALID_SHAPE")
        ingredients = cast(list[Any], ingredients)
        if not 1 <= len(ingredients) <= 9:
            raise ValueError("RECIPE_INVALID_SHAPE")
        slots = tuple(_ingredient(value) for value in ingredients)
        # Minimum square capacity, not a manufactured placement order.
        width = height = 1 if len(slots) == 1 else 2 if len(slots) <= 4 else 3
    else:
        pattern, keys = document.get("pattern"), document.get("key")
        if not isinstance(pattern, list) or not isinstance(keys, dict):
            raise ValueError("RECIPE_INVALID_SHAPE")
        pattern = cast(list[Any], pattern)
        keys = cast(dict[str, Any], keys)
        if (
            not 1 <= len(pattern) <= 3
            or any(not isinstance(row, str) for row in pattern)
            or any(len(key) != 1 or key == " " for key in keys)
        ):
            raise ValueError("RECIPE_INVALID_SHAPE")
        pattern = cast(list[str], pattern)
        width, height = len(pattern[0]), len(pattern)
        if not 1 <= width <= 3 or any(len(row) != width for row in pattern):
            raise ValueError("RECIPE_INVALID_SHAPE")
        used = set("".join(pattern)) - {" "}
        if not used or used != set(keys):
            raise ValueError("RECIPE_INVALID_SHAPE")
        parsed = {key: _ingredient(value) for key, value in keys.items()}
        slots = tuple(parsed[cell] if cell != " " else () for row in pattern for cell in row)
    return PublicRecipe(
        recipe_id,
        product,
        count,
        recipe_type,
        width,
        height,
        slots,
        hashlib.sha256(raw).hexdigest(),
    )


def _read_recipes(
    archive: zipfile.ZipFile, version: str
) -> tuple[tuple[PublicRecipe, ...], Counter[str]]:
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("RECIPE_DUPLICATE_ARCHIVE_ENTRY")
    metadata, _ = _json(archive, "version.json")
    if not isinstance(metadata, dict) or cast(dict[str, Any], metadata).get("id") != version:
        raise ValueError("RECIPE_VERSION_MISMATCH")
    entries = sorted(name for name in names if _ENTRY.fullmatch(name))
    if not entries or len(entries) > _MAX_RECIPES:
        raise ValueError("RECIPE_ARCHIVE_EMPTY_OR_TOO_LARGE")
    if sum(archive.getinfo(name).file_size for name in entries) > _MAX_TOTAL_JSON:
        raise ValueError("RECIPE_ARCHIVE_TOO_LARGE")
    recipes: list[PublicRecipe] = []
    unsupported: Counter[str] = Counter()
    for name in entries:
        match = _ENTRY.fullmatch(name)
        assert match is not None
        recipe_id = _identifier(f"{match[1]}:{match[2]}")
        document, raw = _json(archive, name)
        if not isinstance(document, dict):
            raise ValueError("RECIPE_INVALID_DOCUMENT")
        document = cast(dict[str, Any], document)
        recipe_type = _identifier(document.get("type"))
        if recipe_type not in {"minecraft:crafting_shaped", "minecraft:crafting_shapeless"}:
            unsupported[recipe_type] += 1
            continue
        recipes.append(_recipe(recipe_id, document, raw))
    return tuple(recipes), unsupported


def _read_tags(archive: zipfile.ZipFile) -> Mapping[str, tuple[str, ...]]:
    entries = sorted(name for name in archive.namelist() if _TAG_ENTRY.fullmatch(name))
    if (
        len(entries) > _MAX_RECIPES
        or sum(archive.getinfo(name).file_size for name in entries) > _MAX_TOTAL_JSON
    ):
        raise ValueError("RECIPE_TAG_SOURCE_TOO_LARGE")
    definitions: dict[str, tuple[tuple[str, bool], ...]] = {}
    for name in entries:
        match = _TAG_ENTRY.fullmatch(name)
        assert match is not None
        tag_id = _identifier(f"{match[1]}:{match[2]}")
        document, _ = _json(archive, name)
        if not isinstance(document, dict):
            raise ValueError("RECIPE_INVALID_TAG")
        document = cast(dict[str, Any], document)
        values = document.get("values")
        if not isinstance(values, list):
            raise ValueError("RECIPE_INVALID_TAG")
        values = cast(list[Any], values)
        if len(values) > 4096:
            raise ValueError("RECIPE_TAG_SOURCE_TOO_LARGE")
        parsed: list[tuple[str, bool]] = []
        for value in values:
            required = True
            if isinstance(value, dict):
                entry = cast(dict[str, Any], value)
                required = entry.get("required", True)
                if type(required) is not bool or set(entry) - {"id", "required"}:
                    raise ValueError("RECIPE_INVALID_TAG")
                value = entry.get("id")
            if not isinstance(value, str):
                raise ValueError("RECIPE_INVALID_TAG")
            reference = value.startswith("#")
            identifier = _identifier(value[1:] if reference else value)
            parsed.append((("#" if reference else "") + identifier, required))
        definitions[tag_id] = tuple(parsed)
    expanded: dict[str, tuple[str, ...]] = {}

    def expand(tag_id: str, ancestors: frozenset[str]) -> tuple[str, ...]:
        if tag_id in ancestors or len(ancestors) >= 32:
            raise ValueError("RECIPE_TAG_CYCLE_OR_DEPTH")
        if tag_id in expanded:
            return expanded[tag_id]
        items: set[str] = set()
        for identifier, required in definitions[tag_id]:
            if not identifier.startswith("#"):
                items.add(identifier)
            elif identifier[1:] in definitions:
                items.update(expand(identifier[1:], ancestors | {tag_id}))
            elif required:
                raise ValueError("RECIPE_TAG_REFERENCE_MISSING")
            if len(items) > 4096:
                raise ValueError("RECIPE_TAG_SOURCE_TOO_LARGE")
        expanded[tag_id] = tuple(sorted(items))
        return expanded[tag_id]

    for tag_id in definitions:
        expand(tag_id, frozenset())
    return MappingProxyType(expanded)


def load_recipe_knowledge(
    path: Path, *, game_version: str, expected_sha256: str | None = None
) -> RecipeKnowledge:
    """Read a direct client/server JAR or version-bundled server JAR, with size limits.

    Optional SHA-256 binds the supplied bytes to a caller's trusted download record.
    Without it the source is content-addressed but its publisher is NOT authenticated.
    This adapter supports public shaped/shapeless knowledge only, not special crafts,
    smelting, or current server overrides. No recipe is marked live-confirmed.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", game_version):
        raise ValueError("RECIPE_INVALID_VERSION")
    if expected_sha256 is not None and not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("RECIPE_INVALID_DIGEST")
    if not path.is_file() or path.stat().st_size > _MAX_ARCHIVE:
        raise ValueError("RECIPE_ARCHIVE_MISSING_OR_TOO_LARGE")
    # One bounded snapshot binds the digest and parsed data to the same bytes.
    with path.open("rb") as stream:
        raw = stream.read(_MAX_ARCHIVE + 1)
    if len(raw) > _MAX_ARCHIVE:
        raise ValueError("RECIPE_ARCHIVE_TOO_LARGE")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("RECIPE_DIGEST_MISMATCH")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("RECIPE_DUPLICATE_ARCHIVE_ENTRY")
            if any(_ENTRY.fullmatch(name) for name in names):
                recipes, unsupported = _read_recipes(archive, game_version)
                tags = _read_tags(archive)
            else:
                name = f"META-INF/versions/{game_version}/server-{game_version}.jar"
                if archive.getinfo(name).file_size > _MAX_NESTED:
                    raise ValueError("RECIPE_NESTED_ARCHIVE_TOO_LARGE")
                with zipfile.ZipFile(io.BytesIO(archive.read(name))) as nested:
                    recipes, unsupported = _read_recipes(nested, game_version)
                    tags = _read_tags(nested)
    except (
        zipfile.BadZipFile,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        RecursionError,
        RuntimeError,
    ) as exc:
        raise ValueError("RECIPE_ARCHIVE_INVALID") from exc
    return RecipeKnowledge(
        game_version,
        digest,
        expected_sha256 is not None,
        recipes,
        MappingProxyType(unsupported),
        tags,
    )
