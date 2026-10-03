"""Bind public recipe knowledge to observed inventory, without crafting permissions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from minekin_core.adapters.public_recipe_archive import RecipeKnowledge
from minekin_core.domain.perception import WorldObservationValue
from minekin_core.domain.recipe_catalog import Recipe, RecipeProvenance


@dataclass(frozen=True, slots=True)
class PublicCraftKnowledge:
    knowledge: RecipeKnowledge

    def knows_product(self, product_id: str) -> bool:
        return bool(self.knowledge.for_product(product_id))

    def refusal_for(
        self, product_id: str, reading: WorldObservationValue, *, grid_side: int
    ) -> str:
        recipes = self.knowledge.for_product(product_id)
        if not recipes:
            return "CRAFT_RECIPE_UNAVAILABLE"
        fitting = tuple(row for row in recipes if max(row.width, row.height) <= grid_side)
        if not fitting:
            return "CRAFT_GRID_TOO_SMALL"
        counts: Counter[str] = Counter()
        for stack in reading.inventory.stacks:
            counts[stack.item_id] += stack.count
        payable = tuple(
            row
            for row in fitting
            if self.knowledge.materials_for(row.recipe_id, counts) is not None
        )
        if not payable:
            return "CRAFT_MATERIALS_MISSING"
        if (
            reading.gui is not None
            and reading.gui.sync_id is not None
            and not any(row.recipe_id in reading.gui.craftable_recipe_ids for row in payable)
        ):
            return "GUI_RECIPE_UNKNOWN"
        return ""

    def available(self, reading: WorldObservationValue, *, grid_side: int) -> Mapping[str, Recipe]:
        counts: Counter[str] = Counter()
        for stack in reading.inventory.stacks:
            counts[stack.item_id] += stack.count
        book: frozenset[str] = (
            frozenset() if reading.gui is None else reading.gui.craftable_recipe_ids
        )
        result: dict[str, Recipe] = {}
        # Prefer a variant the current GUI actually names. Public knowledge alone
        # cannot assert that any recipe is unlocked or supported by this server.
        for row in sorted(
            self.knowledge.recipes, key=lambda row: (row.recipe_id not in book, row.recipe_id)
        ):
            if row.product_id in result or max(row.width, row.height) > grid_side:
                continue
            if (
                reading.gui is not None
                and reading.gui.sync_id is not None
                and row.recipe_id not in book
            ):
                continue
            cells = self.knowledge.materials_for(row.recipe_id, counts)
            if cells is None:
                continue
            materials = Counter(item for item in cells if item is not None)
            result[row.product_id] = Recipe(
                product_id=row.product_id,
                recipe_id=row.recipe_id,
                ingredients=tuple(sorted(materials.items())),
                grid_width=row.width,
                grid_height=row.height,
                yields=row.count,
                provenance=RecipeProvenance.PUBLIC_VERSION,
            )
        return MappingProxyType(result)

    def as_document(self) -> dict[str, object]:
        return {
            "source": "PUBLIC_VERSION_ARCHIVE",
            "game_version": self.knowledge.game_version,
            "archive_sha256": self.knowledge.archive_sha256,
            "expected_digest_matched": self.knowledge.digest_matched,
            "recipe_count": len(self.knowledge.recipes),
            "player_recipe_unlocked": "unknown",
            "current_server_compatibility": "unknown",
            "live_confirmed": False,
            "multi_stage_planner": "not_connected",
        }
