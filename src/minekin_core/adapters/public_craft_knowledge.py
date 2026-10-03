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
    OwedStep,
    Recipe,
    RecipeProvenance,
    grid_enabler_for,
)


def _inventory_counts(reading: WorldObservationValue) -> Counter[str]:
    """One item's total across stacks, summed rather than overwritten per stack."""

    counts: Counter[str] = Counter()
    for stack in reading.inventory.stacks:
        counts[stack.item_id] += stack.count
    return counts


@dataclass(frozen=True, slots=True)
class _PublicOwedPlan:
    """One product's dependency-ordered owed counts over the archive, keyed by product."""

    order: tuple[str, ...]
    owed: Mapping[str, int]
    chosen: Mapping[str, PublicRecipe]
    rows_by_product: Mapping[str, tuple[PublicRecipe, ...]]
    #: The raw floor (items the archive has no recipe for) this plan cannot pay from the bag:
    #: everything above it is a craft, and what is left over is what a gather would bring back.
    raw_shortfall: Mapping[str, int]


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

    def _owed_plan(
        self, product_id: str, reading: WorldObservationValue, *, quantity: int, grid_side: int
    ) -> _PublicOwedPlan | str:
        """The dependency-ordered owed counts over the archive, or the name that stops the walk.

        Shared by `step_toward` (which selects the nearest runnable step) and
        `enabler_to_stand_up` (which reads the widest owed shape), so both answer from one
        arithmetic. The walk is the archive's own graph in demand order: every craftable
        ingredient an earlier step, counts multiplied out of each recipe's `result.count`, and
        the reading's counts paying cells first across a tag's alternatives — only what the bag
        cannot cover is demanded from whichever alternative the archive can craft. Cells whose
        tag the archive does not know are never planned around. A recipe graph that eats itself
        refuses with `CRAFT_RECIPE_UNAVAILABLE`.
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
        chosen: dict[str, PublicRecipe] = {}
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
            chosen[product] = row
            order.append(product)
            return None

        failure = visit(product_id, frozenset())
        if failure is not None:
            return failure

        pool = Counter(_inventory_counts(reading))
        gross: dict[str, int] = {product_id: quantity}
        owed: dict[str, int] = {}
        for product in reversed(order):
            row = chosen[product]
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
        shortfall: dict[str, int] = {}
        for item_id, demanded in gross.items():
            if item_id in rows_by_product:
                continue  # a craft, not a gather: its own node already answered for it
            missing = demanded - pool.get(item_id, 0)
            if missing > 0:
                shortfall[item_id] = missing
        return _PublicOwedPlan(
            order=tuple(order),
            owed=MappingProxyType(dict(owed)),
            chosen=MappingProxyType(dict(chosen)),
            rows_by_product=MappingProxyType(
                {product: tuple(rows) for product, rows in rows_by_product.items()}
            ),
            raw_shortfall=MappingProxyType(shortfall),
        )

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
        every craftable ingredient and returns the nearest owed step this bag can actually run —
        so a pickaxe whose sticks are missing is answered with the stick craft, not with
        `CRAFT_MATERIALS_MISSING` about a bag that can pay for everything but the shape.

        When every owed step's shape is wider than the grid this reading opens, the curated
        grid-opener rows answer the same question they answer for curated plans: an item whose
        product opens a wide enough grid and can be made inside the current one becomes this
        plan's next craft; once it is already held the word is `CRAFT_GRID_TOO_SMALL` — placing
        and opening it is the mind's move, not a second craft — and while its own materials are
        short the word is `CRAFT_MATERIALS_MISSING`, which is the gather, not a dead end.

        Refusal words keep `refusal_for`'s meaning and its precedence — grid before bag before
        an open window's recipe book — and `CRAFT_RECIPE_UNAVAILABLE` covers both a product the
        archive cannot answer for and a recipe graph that eats itself. The plan is
        knowledge-side arithmetic on one reading, not admission: the caller still judges the
        step against a fresh frame and the GUI, and only a later reading's inventory confirms
        anything.
        """

        plan = self._owed_plan(product_id, reading, quantity=quantity, grid_side=grid_side)
        if isinstance(plan, str):
            return plan
        counts = _inventory_counts(reading)
        book: frozenset[str] = (
            frozenset() if reading.gui is None else reading.gui.craftable_recipe_ids
        )
        owed_products = [product for product in plan.order if plan.owed.get(product, 0) > 0]
        if not owed_products:
            # The bag already covers the ask; a caller short of the product never sees this
            # branch, and the word is the one a missing step is mapped to anyway.
            return CRAFT_MATERIALS_MISSING

        gui_report = reading.gui is not None and reading.gui.sync_id is not None
        for product in owed_products:
            for row in sorted(
                plan.rows_by_product[product],
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
                    required_total=plan.owed[product],
                )

        widest = max(
            (
                max(plan.chosen[product].width, plan.chosen[product].height)
                for product in owed_products
            ),
            default=0,
        )
        if widest > grid_side:
            enabler = grid_enabler_for(widest, within_side=grid_side)
            if enabler is not None:
                if counts.get(enabler.product_id, 0) > 0:
                    # Held: standing it up is the mind's next move, not a second craft.
                    return CRAFT_GRID_TOO_SMALL
                if all(counts.get(item_id, 0) >= count for item_id, count in enabler.ingredients):
                    if gui_report and enabler.recipe_id not in book:
                        return "GUI_RECIPE_UNKNOWN"
                    return BuildStep(recipe=enabler, required_total=1)
                return CRAFT_MATERIALS_MISSING

        if not any(
            max(row.width, row.height) <= grid_side
            for product in owed_products
            for row in plan.rows_by_product[product]
        ):
            return CRAFT_GRID_TOO_SMALL
        if gui_report and any(
            max(row.width, row.height) <= grid_side
            and self.knowledge.materials_for(row.recipe_id, counts) is not None
            for product in owed_products
            for row in plan.rows_by_product[product]
        ):
            # Payable steps exist; every one of them is one the open window does not name.
            return "GUI_RECIPE_UNKNOWN"
        return CRAFT_MATERIALS_MISSING

    def owed_chain(
        self,
        product_id: str,
        reading: WorldObservationValue,
        *,
        quantity: int = 1,
        grid_side: int,
    ) -> tuple[OwedStep, ...] | str:
        """Every owed craft on the way to a product, in build order, or the name that stops
        the walk.

        The listing view of `_owed_plan`: each entry carries what it owes and whether the grid
        being read can hold it, and resolves its own batch cost against this reading only when
        the bag can pay it (`materials` is `None` otherwise — a refusal word, not an empty
        price). `step_toward` is this list's first runnable position; this is what a decision
        context shows so a multi-step goal reads as a chain rather than as one step with no
        idea what comes after it.
        """

        plan = self._owed_plan(product_id, reading, quantity=quantity, grid_side=grid_side)
        if isinstance(plan, str):
            return plan
        counts = _inventory_counts(reading)
        entries: list[OwedStep] = []
        for product in plan.order:
            owed = plan.owed.get(product, 0)
            if owed <= 0:
                continue
            row = plan.chosen[product]
            cells = self.knowledge.materials_for(row.recipe_id, counts)
            materials = (
                None
                if cells is None
                else tuple(sorted(Counter(item for item in cells if item is not None).items()))
            )
            entries.append(
                OwedStep(
                    product_id=row.product_id,
                    required_total=owed,
                    fits_grid_side=max(row.width, row.height) <= grid_side,
                    materials=materials,
                )
            )
        return tuple(entries)

    def enabler_to_stand_up(
        self,
        product_id: str,
        reading: WorldObservationValue,
        *,
        quantity: int = 1,
        grid_side: int,
    ) -> tuple[Recipe, int] | None:
        """The held grid-opener this plan needs stood up, with its slot, or `None`.

        The same question `player_mind.enabler_to_stand_up` asks of a curated plan, asked of
        this one: while the product is not yet held and a still-owed step's shape is wider than
        the grid being read, `None` means either there is nothing to stand up (the plan fits,
        or an opener for that shape is unknown to the curated rows) or the opener is still a
        craft — which is `step_toward`'s step. When the bag already holds one, its recipe and
        slot are returned for the general select-place-open path. No product name is hardcoded
        here; a newly curated opener row becomes reachable without a change.
        """

        counts = _inventory_counts(reading)
        if counts.get(product_id, 0) >= quantity:
            return None
        plan = self._owed_plan(product_id, reading, quantity=quantity, grid_side=grid_side)
        if isinstance(plan, str):
            return None
        needed = max(
            (
                max(plan.chosen[product].width, plan.chosen[product].height)
                for product in plan.order
                if plan.owed.get(product, 0) > 0
            ),
            default=0,
        )
        if needed <= grid_side:
            return None
        enabler = grid_enabler_for(needed, within_side=grid_side)
        if enabler is None:
            return None
        for stack in reading.inventory.stacks:
            if stack.item_id == enabler.product_id:
                return (enabler, stack.slot)
        return None

    def missing_raw(
        self, product_id: str, reading: WorldObservationValue, *, quantity: int = 1, grid_side: int
    ) -> Mapping[str, int]:
        """The raw floor this plan cannot pay from the bag, as item counts, or empty.

        Raw means an item the archive has no recipe for: everything above it is an owed craft
        (`step_toward`'s business), and what is left over here is what a gather would have to
        bring back. This is the plan's selection basis for a gathering route — which resource
        to go find — and it is knowledge-side arithmetic on one reading, never a claim that
        the world has or lacks anything: the caller still gathers through observed blocks.
        A cell whose tag offers several alternatives is resolved to the plan's own deterministic
        candidate, which satisfies the recipe without asserting the sibling alternatives are
        wrong. Refused plans (unknown product, self-eating recipes) have no floor to name and
        answer with an empty mapping, same as a fully paid one.
        """

        plan = self._owed_plan(product_id, reading, quantity=quantity, grid_side=grid_side)
        if isinstance(plan, str):
            return {}
        return plan.raw_shortfall

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
