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


@dataclass(slots=True)
class _PlanningStock:
    """Private simulated reservations; never promoted to an observed inventory."""

    pool: Counter[str]
    order: list[str]
    owed: Counter[str]
    chosen: dict[str, PublicRecipe]
    raw: Counter[str]

    def copy(self) -> _PlanningStock:
        return _PlanningStock(
            self.pool.copy(),
            self.order.copy(),
            self.owed.copy(),
            self.chosen.copy(),
            self.raw.copy(),
        )

    def cost(self) -> tuple[int, int, int]:
        return sum(self.raw.values()), len(self.order), sum(self.owed.values())


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
        """The dependency-ordered owed counts over the archive, for this reading's bag.

        The reading's inventory and open-screen book bound to `_owed_plan_for_counts` — the
        same arithmetic the reserve check replans with on a reduced stock.
        """

        book: frozenset[str] = (
            frozenset() if reading.gui is None else reading.gui.craftable_recipe_ids
        )
        return self._owed_plan_for_counts(
            product_id,
            _inventory_counts(reading),
            quantity=quantity,
            grid_side=grid_side,
            book=book,
        )

    def _owed_plan_for_counts(
        self,
        product_id: str,
        counts: Mapping[str, int],
        *,
        quantity: int,
        grid_side: int,
        book: frozenset[str],
    ) -> _PublicOwedPlan | str:
        """The dependency-ordered owed counts over the archive, or the name that stops the walk.

        Shared by `step_toward` (which selects the nearest runnable step) and
        `enabler_to_stand_up` (which reads the widest owed shape), so both answer from one
        arithmetic. Inventory is reserved before expanding unmet demand. Alternative branches
        are tried on isolated simulated stock, preferring fewer missing raw inputs. This is a
        bounded heuristic, not a globally optimal search. Surplus pays later cells, without
        becoming a live inventory fact. Unknown tags and unfunded cyclic branches refuse;
        one cyclic variant does not invalidate a different usable variant.
        """

        rows_by_product: dict[str, list[PublicRecipe]] = {}
        for row in self.knowledge.recipes:
            rows_by_product.setdefault(row.product_id, []).append(row)
        if (
            product_id not in rows_by_product
            or type(quantity) is not int
            or not 0 < quantity <= 4096
        ):
            return CRAFT_RECIPE_UNAVAILABLE

        def cell_items(cell: tuple[IngredientOption, ...]) -> tuple[str, ...]:
            items: set[str] = set()
            for option in cell:
                if option.kind == "item":
                    items.add(option.identifier)
                else:
                    items.update(self.knowledge.item_tags.get(option.identifier, ()))
            return tuple(sorted(items))

        remaining = 20_000

        def demand(
            product: str, count: int, stock: _PlanningStock, path: frozenset[str]
        ) -> _PlanningStock | None:
            nonlocal remaining
            remaining -= 1
            if remaining < 0 or len(path) >= 32:
                return None
            stock = stock.copy()
            used = min(count, stock.pool[product])
            stock.pool[product] -= used
            if product in stock.chosen:
                stock.owed[product] += used
            missing = count - used
            if not missing:
                return stock  # observed/reserved stock pays before any cycle expansion
            if product in path:
                return None
            rows = rows_by_product.get(product)
            if not rows:
                stock.raw[product] += missing
                return stock
            best: _PlanningStock | None = None
            for row in sorted(
                rows,
                key=lambda row: (
                    self.knowledge.materials_for(row.recipe_id, stock.pool) is None,
                    row.recipe_id not in book,
                    max(row.width, row.height) > grid_side,
                    max(row.width, row.height),
                    row.recipe_id,
                ),
            ):
                # A product is represented by one variant in the public chain.
                if product in stock.chosen and stock.chosen[product] != row:
                    continue
                candidate = stock.copy()
                batches = -(-missing // row.count)
                payable = self.knowledge.materials_for(row.recipe_id, stock.pool)
                if payable is not None and batches == 1:
                    # Use the capacity matcher for a fully funded batch; a greedy
                    # OR-cell reservation could steal a later cell's only option.
                    for item in payable:
                        if item is not None:
                            candidate.pool[item] -= 1
                            if item in candidate.chosen:
                                candidate.owed[item] += 1
                    if product not in candidate.chosen:
                        candidate.order.append(product)
                    candidate.chosen[product] = row
                    candidate.owed[product] += missing
                    candidate.pool[product] += row.count - missing
                    return candidate
                viable = True
                for cell in row.slots:
                    if not cell:
                        continue
                    items = cell_items(cell)
                    # Share observed stock across alternatives and across cells.
                    need = batches
                    for item in sorted(items, key=lambda item: (-candidate.pool[item], item)):
                        take = min(need, candidate.pool[item])
                        candidate.pool[item] -= take
                        if item in candidate.chosen:
                            candidate.owed[item] += take
                        need -= take
                    if not need:
                        continue
                    child_best: _PlanningStock | None = None
                    for item in items:
                        child = demand(item, need, candidate, path | {product})
                        if child is not None and (
                            child_best is None or child.cost() < child_best.cost()
                        ):
                            child_best = child
                    if child_best is None:
                        viable = False
                        break
                    candidate = child_best
                if not viable:
                    continue
                if product not in candidate.chosen:
                    candidate.order.append(product)
                candidate.chosen[product] = row
                candidate.owed[product] += missing
                candidate.pool[product] += batches * row.count - missing
                if best is None or candidate.cost() < best.cost():
                    best = candidate
            return best

        planned = demand(
            product_id,
            quantity,
            _PlanningStock(Counter(counts), [], Counter(), {}, Counter()),
            frozenset(),
        )
        if planned is None or remaining < 0:
            return CRAFT_RECIPE_UNAVAILABLE
        return _PublicOwedPlan(
            order=tuple(planned.order),
            owed=MappingProxyType(dict(planned.owed)),
            chosen=MappingProxyType(dict(planned.chosen)),
            rows_by_product=MappingProxyType(
                {product: tuple(rows) for product, rows in rows_by_product.items()}
            ),
            raw_shortfall=MappingProxyType(dict(planned.raw)),
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
        gui_report = reading.gui is not None and reading.gui.sync_id is not None
        owed_products = [product for product in plan.order if plan.owed.get(product, 0) > 0]
        if not owed_products:
            # The bag already covers the ask; a caller short of the product never sees this
            # branch, and the word is the one a missing step is mapped to anyway.
            return CRAFT_MATERIALS_MISSING

        step = self._first_runnable_step(
            plan, counts, grid_side=grid_side, book=book, gui_report=gui_report
        )
        if step is not None:
            return step

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
                held = counts.get(enabler.product_id, 0) > 0
                if not held and not all(
                    counts.get(item_id, 0) >= count for item_id, count in enabler.ingredients
                ):
                    # The enabler's own cost may itself be payable through a craft — a banked
                    # log into the planks — so plan the first short ingredient and run that
                    # step before giving the gather word. One ingredient at a time is the
                    # real shape (the curated openers have one); more would need the shared
                    # stock arithmetic the owed plan already does for products.
                    short = next(
                        (item_id, count)
                        for item_id, count in enabler.ingredients
                        if counts.get(item_id, 0) < count
                    )
                    ingredient_plan = self._owed_plan_for_counts(
                        short[0], counts, quantity=short[1], grid_side=grid_side, book=book
                    )
                    if not isinstance(ingredient_plan, str):
                        first = self._first_runnable_step(
                            ingredient_plan,
                            counts,
                            grid_side=grid_side,
                            book=book,
                            gui_report=gui_report,
                        )
                        if first is not None:
                            return first
                    return CRAFT_MATERIALS_MISSING
                if not held and gui_report and enabler.recipe_id not in book:
                    return "GUI_RECIPE_UNKNOWN"
                reserved = Counter(counts)
                if not held:
                    for item_id, count in enabler.ingredients:
                        reserved[item_id] -= count
                # What the bag still owes once the enabler is paid, planned and walked at
                # the grid the enabler opens — the crafts it is for must be directly
                # runnable inside that window, because a placed table cannot be reselected.
                reduced = self._owed_plan_for_counts(
                    product_id, reserved, quantity=quantity, grid_side=widest, book=book
                )
                leading: BuildStep | None = None
                if not isinstance(reduced, str):
                    leading = self._first_runnable_step(
                        reduced, reserved, grid_side=widest, book=book, gui_report=gui_report
                    )
                if leading is not None and leading.product_id != product_id:
                    # An earlier step is still owed on the reserved stock — turning a banked
                    # log into the planks the wide craft needs, say: do it first, so the
                    # window opens on a bag the wide craft can actually use.
                    return leading
                if leading is not None:
                    # The wide craft itself is what the reserved bag can run: the enabler is
                    # the move — craft it, or stand the held one up. Either way the four
                    # planks it costs are already accounted for above.
                    if held:
                        return CRAFT_GRID_TOO_SMALL
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

    def _first_runnable_step(
        self,
        plan: _PublicOwedPlan,
        counts: Mapping[str, int],
        *,
        grid_side: int,
        book: frozenset[str],
        gui_report: bool,
    ) -> BuildStep | None:
        """The plan's first owed step this bag can run on the given stock, or None.

        The walk `step_toward` has always done — build order, the open window's book last —
        lifted so the reserve check can ask it of a reduced stock: whatever it answers is what
        a bag missing the enabler's cost would do next, and the enabler may only be spent when
        the answer is the wide craft itself.
        """

        for product in (product for product in plan.order if plan.owed.get(product, 0) > 0):
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
        return None

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
