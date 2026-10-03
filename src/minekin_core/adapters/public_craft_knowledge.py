"""Bind public recipe knowledge to observed inventory, without crafting permissions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from minekin_core.adapters.public_recipe_archive import (
    IngredientOption,
    PublicRecipe,
    RecipeKnowledge,
)
from minekin_core.domain.perception import WorldObservationValue
from minekin_core.domain.recipe_catalog import (
    CRAFT_GRID_TOO_SMALL,
    CRAFT_MATERIALS_MISSING,
    CRAFT_RECIPE_UNAVAILABLE,
    BuildStep,
    Recipe,
    RecipeProvenance,
)


def _inventory_counts(reading: WorldObservationValue) -> Counter[str]:
    """One item's total across stacks, summed rather than overwritten per stack."""

    counts: Counter[str] = Counter()
    for stack in reading.inventory.stacks:
        counts[stack.item_id] += stack.count
    return counts


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
            return CRAFT_RECIPE_UNAVAILABLE
        fitting = tuple(row for row in recipes if max(row.width, row.height) <= grid_side)
        if not fitting:
            return CRAFT_GRID_TOO_SMALL
        counts = _inventory_counts(reading)
        payable = tuple(
            row
            for row in fitting
            if self.knowledge.materials_for(row.recipe_id, counts) is not None
        )
        if not payable:
            return CRAFT_MATERIALS_MISSING
        if (
            reading.gui is not None
            and reading.gui.sync_id is not None
            and not any(row.recipe_id in reading.gui.craftable_recipe_ids for row in payable)
        ):
            return "GUI_RECIPE_UNKNOWN"
        return ""

    def available(self, reading: WorldObservationValue, *, grid_side: int) -> Mapping[str, Recipe]:
        counts = _inventory_counts(reading)
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

    def step_toward(
        self,
        product_id: str,
        reading: WorldObservationValue,
        *,
        quantity: int = 1,
        grid_side: int,
    ) -> BuildStep | str:
        """The first owed craft on the way to `quantity` of a product, or what blocks it.

        This generalises the direct batch `available` answers: where that only ever offers a
        craft this bag can pay for in one go, this walks the archive's own recipes down through
        every craftable ingredient, multiplies each layer out of its own `result.count`, and
        returns the nearest owed step this bag can actually run — so a pickaxe whose sticks are
        missing is answered with the stick craft, not with `CRAFT_MATERIALS_MISSING` about a bag
        that can pay for everything but the shape.

        The reading's own counts pay the cells first (shared across a tag's alternatives, the
        same capacity rule `materials_for` applies), and only what is left over is demanded from
        whichever alternative the archive can craft rather than gather. A cell whose tag the
        archive does not know is never planned around: it can only ever refuse at payability,
        never get a guessed item.

        Refusal words keep `refusal_for`'s meaning and its precedence — grid before bag before an
        open window's recipe book — and `CRAFT_RECIPE_UNAVAILABLE` covers both a product the
        archive cannot answer for and a recipe graph that eats itself. The plan is knowledge-side
        arithmetic on one reading, not admission: the caller still judges the step against a
        fresh frame and the GUI, and only a later reading's inventory confirms anything.
        """

        rows_by_product: dict[str, list[PublicRecipe]] = {}
        for row in self.knowledge.recipes:
            rows_by_product.setdefault(row.product_id, []).append(row)
        if product_id not in rows_by_product:
            return CRAFT_RECIPE_UNAVAILABLE
        book: frozenset[str] = (
            frozenset() if reading.gui is None else reading.gui.craftable_recipe_ids
        )

        def variant(product: str) -> PublicRecipe | None:
            """One deterministic recipe per product: a book-named, fitting, smaller row wins."""

            rows = rows_by_product.get(product)
            if not rows:
                return None
            fitting = [row for row in rows if max(row.width, row.height) <= grid_side] or rows
            return min(
                fitting,
                key=lambda row: (
                    row.recipe_id not in book,
                    max(row.width, row.height),
                    row.recipe_id,
                ),
            )

        def cell_items(cell: tuple[IngredientOption, ...]) -> tuple[str, ...]:
            items: set[str] = set()
            for option in cell:
                if option.kind == "item":
                    items.add(option.identifier)
                else:
                    items.update(self.knowledge.item_tags.get(option.identifier, ()))
            return tuple(sorted(items))

        order: list[str] = []
        visited: set[str] = set()

        def visit(product: str, path: frozenset[str]) -> str | None:
            """Depth-first over craftable ingredients only: a step is never listed before what
            it eats, and a recipe that eats itself refuses by name."""

            if product in path:
                return CRAFT_RECIPE_UNAVAILABLE
            if product in visited:
                return None
            row = variant(product)
            if row is None:
                return None  # gathered rather than crafted: the plan ends where the archive does
            for cell in row.slots:
                for item in cell_items(cell):
                    if item not in rows_by_product:
                        continue
                    failure = visit(item, path | {product})
                    if failure is not None:
                        return failure
            visited.add(product)
            order.append(product)
            return None

        failure = visit(product_id, frozenset())
        if failure is not None:
            return failure

        counts = _inventory_counts(reading)
        pool = Counter(counts)
        gross: dict[str, int] = {product_id: quantity}
        owed: dict[str, int] = {}
        for product in reversed(order):
            row = variant(product)
            assert row is not None  # only products the archive answers for enter `order`
            still = max(0, gross.get(product, 0) - pool.get(product, 0))
            owed[product] = still
            if still == 0:
                continue
            batches = -(-still // row.count)
            for cell in row.slots:
                if not cell:
                    continue
                candidates = cell_items(cell)
                if not candidates:
                    continue  # unknown tag: payability refuses this step, never a guess
                taken = 0
                for item in sorted(candidates, key=lambda item: (-pool.get(item, 0), item)):
                    if taken >= batches:
                        break
                    used = min(batches - taken, pool.get(item, 0))
                    if used:
                        pool[item] -= used
                        taken += used
                missing = batches - taken
                if missing:
                    demand = next(
                        (item for item in candidates if item in rows_by_product),
                        candidates[0],
                    )
                    gross[demand] = gross.get(demand, 0) + missing

        owed_products = [product for product in order if owed.get(product, 0) > 0]
        if not owed_products:
            # The bag already covers the ask; a caller short of the product never sees this
            # branch, and the word is the one a missing step is mapped to anyway.
            return CRAFT_MATERIALS_MISSING

        gui_report = reading.gui is not None and reading.gui.sync_id is not None
        for product in owed_products:
            for row in sorted(
                rows_by_product[product],
                key=lambda row: (row.recipe_id not in book, row.recipe_id),
            ):
                if max(row.width, row.height) > grid_side:
                    continue
                cells = self.knowledge.materials_for(row.recipe_id, counts)
                if cells is None:
                    continue
                if gui_report and row.recipe_id not in book:
                    continue
                materials = Counter(item for item in cells if item is not None)
                return BuildStep(
                    recipe=Recipe(
                        product_id=row.product_id,
                        recipe_id=row.recipe_id,
                        ingredients=tuple(sorted(materials.items())),
                        grid_width=row.width,
                        grid_height=row.height,
                        yields=row.count,
                        provenance=RecipeProvenance.PUBLIC_VERSION,
                    ),
                    required_total=owed[product],
                )

        if not any(
            max(row.width, row.height) <= grid_side
            for product in owed_products
            for row in rows_by_product[product]
        ):
            return CRAFT_GRID_TOO_SMALL
        if gui_report and any(
            max(row.width, row.height) <= grid_side
            and self.knowledge.materials_for(row.recipe_id, counts) is not None
            for product in owed_products
            for row in rows_by_product[product]
        ):
            # Payable steps exist; every one of them is one the open window does not name.
            return "GUI_RECIPE_UNKNOWN"
        return CRAFT_MATERIALS_MISSING

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
            "multi_stage_planner": "stepwise",
        }
