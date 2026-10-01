"""Which craft a product id stands for, and what has to be true before that craft can run.

The skill layer is already parameterised — `craft` and `craft_take_result` take a recipe id and
a material map and know nothing about wood — so the open question was never *how* a craft is
performed but *who decides the recipe*. This module is that decision, made once, as data: a
table keyed by product id, read by whoever has a product to ask about. Nobody else names a
recipe at runtime. A model in particular may not: a recipe id it invents comes back from the
client as `REFUSED_GUI_RECIPE_UNKNOWN`, and an ingredient list it invents is a click that
spends the wrong items, and neither of those is a fact a later world reading can be argued
into existence.

Three things can make a craft impossible, and each has one word: nobody knows that product,
the grid being opened cannot hold that shape, this bag cannot pay for it. A resolver that
answered those with an empty result would push the interpretation onto every caller, which is
how a build ends up with five slightly different ways of saying "no".

The same table answers the second question a goal raises, which is not whether one craft can
run but what has to run before it: `build_plan` walks the recipes in demand order and
multiplies the counts out of each recipe's own yield, so wanting an item is a product id and a
quantity rather than a list somebody wrote out by hand. A hand-written build order is the one
place this repository could have the wrong arithmetic and nothing in the world would notice.

The numbers here are facts about one Minecraft version, and each row carries, as data rather
than as a comment, the way this build came to hold it: watched crafted on the controlled server,
or curated from the game's own data and not yet watched. `recipe_coverage` reports that boundary —
the version, the covered products, the watched/curated split, and `universal=False` — so no caller
mistakes this finite fallback for a general crafting source. A product outside the cover is
answered with `CRAFT_RECIPE_UNAVAILABLE`, never with a guess. In
`docs/recipe-knowledge-gui-contract.md` these rows are the first of its three objects: public
knowledge about a craft, which is what lets the Kin *intend* one. They are not the account's
recipe book and they are not a confirmation of anything — whether a craft happened is still
judged only by the inventory in a later reading, never by this table having been read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from minekin_core.domain.perception import InventoryValue
from minekin_core.domain.world_actions import item_total

#: The side of the square grid the craft skills actually open. `craft_take_result` opens the
#: inventory screen, whose crafting grid is two by two, and this build has no skill that
#: places or opens a crafting table, so three by three is not a screen the Kin is in. An
#: observation carries no grid size — `GuiScreenValue` names only the screen and its sync id —
#: so this constant is the honest stand-in, and a caller that one day reads a real size passes
#: it as an argument instead of editing this line.
PLAYER_GRID_SIDE: Final = 2

#: The product id is not in the catalog. The caller asked for an item this build has no recipe
#: for, which is a missing piece of curated knowledge, not a world condition to retry.
CRAFT_RECIPE_UNAVAILABLE: Final = "CRAFT_RECIPE_UNAVAILABLE"
#: The recipe is known and fits the grid, but the inventory handed over cannot pay for it.
CRAFT_MATERIALS_MISSING: Final = "CRAFT_MATERIALS_MISSING"
#: The recipe needs a larger grid than the one being opened. Nothing about the bag would make
#: this true, so it is checked before the bag: gathering more wood is the wrong response to a
#: shape that does not fit.
CRAFT_GRID_TOO_SMALL: Final = "CRAFT_GRID_TOO_SMALL"

#: The single game version these rows claim to describe. A craft is a fact about a version, and
#: a catalog that did not name its own would let a 1.21.4 server be answered with 1.20.1 shapes
#: and call that knowledge. `recipe_coverage` reports it so no caller has to trust a comment.
CATALOG_GAME_VERSION: Final = "1.20.1"


class RecipeProvenance(StrEnum):
    """How this build came to hold a row — watched in the game, or curated and not yet watched.

    The distinction is the boundary criterion 6 asks for, kept as data rather than prose so a
    panel, a run document, or a verifier can read exactly which crafts the Kin has seen happen
    and which are still only a claim lifted from the game's data. A curated row is not a lie: it
    is a recipe the resolver will honour, marked with the one thing that is still missing — a
    live run that crafted it and read the result back.
    """

    #: Watched being crafted on the controlled 1.20.1 server, `CONFIRMED` by the readings after.
    LIVE_CONFIRMED = "live_confirmed"
    #: Curated from the game's own 1.20.1 data; no live run has confirmed this craft end to end.
    CURATED_UNWATCHED = "curated_unwatched"


@dataclass(frozen=True, slots=True)
class Recipe:
    """One curated craft: what it is called in the game, what it costs, and how big it is."""

    product_id: str
    #: The identifier the recipe book answers to. For vanilla crafting recipes it happens to
    #: equal the output item id, and it is kept as its own field rather than derived so that a
    #: future recipe with a different name (`minecraft:planks_from_logs` and its like) is a new
    #: row here and not a change of assumption everywhere downstream.
    recipe_id: str
    #: Ingredient id and count per batch, in the order the recipe lists them. A tuple of pairs
    #: rather than a map so a recipe stays hashable, the same reason `SkillCall.materials` is.
    ingredients: tuple[tuple[str, int], ...]
    grid_width: int
    grid_height: int
    #: How many products one batch makes. Not used by the precondition checks — the world's
    #: later readings decide whether an item arrived — but it is the number a caller needs to
    #: reason about how many batches to ask for, and a catalog without it would be a catalog
    #: that cannot say what one log is worth.
    yields: int
    #: How this build came to hold the row: watched in the game, or curated and not yet watched.
    #: Not used by any precondition check either — it is the coverage boundary made readable, so
    #: a caller can tell a craft it has seen from one it has only been told, without parsing a
    #: comment. See `recipe_coverage`.
    provenance: RecipeProvenance

    def fits(self, grid_side: int) -> bool:
        """Whether this shape can be laid out in a `grid_side` by `grid_side` grid.

        The longer side decides it: the player may rotate a recipe, so a one-by-two stick
        counts as fitting a two-by-two grid, and a two-by-one does too.
        """

        return max(self.grid_width, self.grid_height) <= grid_side


#: The whole of this build's recipe knowledge, keyed by product. Two of these rows have been
#: watched being crafted on the controlled 1.20.1 server (planks from a log, sticks from
#: planks, both `CONFIRMED` by the readings after them); the other two are curated from the
#: game's own data. That distinction is not left in this comment — each row carries a
#: `provenance`, and `recipe_coverage` reports the boundary as data.
RECIPES: Final[Mapping[str, Recipe]] = MappingProxyType(
    {
        "minecraft:oak_planks": Recipe(
            product_id="minecraft:oak_planks",
            recipe_id="minecraft:oak_planks",
            ingredients=(("minecraft:oak_log", 1),),
            grid_width=1,
            grid_height=1,
            yields=4,
            provenance=RecipeProvenance.LIVE_CONFIRMED,
        ),
        "minecraft:stick": Recipe(
            product_id="minecraft:stick",
            recipe_id="minecraft:stick",
            ingredients=(("minecraft:oak_planks", 2),),
            grid_width=1,
            grid_height=2,
            yields=4,
            provenance=RecipeProvenance.LIVE_CONFIRMED,
        ),
        "minecraft:crafting_table": Recipe(
            product_id="minecraft:crafting_table",
            recipe_id="minecraft:crafting_table",
            ingredients=(("minecraft:oak_planks", 4),),
            grid_width=2,
            grid_height=2,
            yields=1,
            provenance=RecipeProvenance.CURATED_UNWATCHED,
        ),
        "minecraft:wooden_pickaxe": Recipe(
            product_id="minecraft:wooden_pickaxe",
            recipe_id="minecraft:wooden_pickaxe",
            ingredients=(("minecraft:oak_planks", 3), ("minecraft:stick", 2)),
            grid_width=3,
            grid_height=3,
            yields=1,
            provenance=RecipeProvenance.CURATED_UNWATCHED,
        ),
    }
)


@dataclass(frozen=True, slots=True)
class CoverageBoundary:
    """What this catalog honestly claims to know, as data rather than as a comment.

    A panel or a run document renders from this instead of from a prose paragraph, which is the
    only way criterion 6 holds: the small curated set is allowed as a fallback precisely because
    it says so out loud — the version it describes, the products it covers, which of those it has
    watched, and above all `universal=False`. Nothing here promises a craft the table cannot name;
    an out-of-cover product is answered with `CRAFT_RECIPE_UNAVAILABLE`, not a guess.
    """

    game_version: str
    #: Every product id the resolver can answer for — the whole of the covered region.
    covered: frozenset[str]
    #: The covered subset watched being crafted on the controlled server.
    live_confirmed: frozenset[str]
    #: The covered subset curated from the game's data and not yet watched; the first live run
    #: that crafts one and reads the result is what moves it into `live_confirmed`.
    curated_only: frozenset[str]
    #: Whether this catalog claims to know every craft in the game. It never does, and the field
    #: is hard-wired to `False` so a caller cannot mistake a finite fallback for a universal
    #: source the way a bare product list would allow.
    universal: bool


def recipe_coverage() -> CoverageBoundary:
    """The catalog's boundary, computed from the rows themselves.

    Derived rather than written so a row cannot be marked watched in one place and curated in
    another: `covered` is the keys, and the provenance field on each row decides the split. A new
    recipe is only ever a new `RECIPES` entry, and the boundary follows it without a second list
    somebody could forget to update.
    """

    live = frozenset(
        product_id
        for product_id, recipe in RECIPES.items()
        if recipe.provenance is RecipeProvenance.LIVE_CONFIRMED
    )
    return CoverageBoundary(
        game_version=CATALOG_GAME_VERSION,
        covered=frozenset(RECIPES),
        live_confirmed=live,
        curated_only=frozenset(RECIPES) - live,
        universal=False,
    )


def resolve_craft(
    product_id: str,
    *,
    inventory: InventoryValue | None = None,
    grid_side: int = PLAYER_GRID_SIDE,
) -> Recipe | str:
    """The recipe for a product, or the name of the precondition that makes it unrunnable.

    A `Recipe` on success; one of the three `CRAFT_*` tokens otherwise. The checks run from the
    most lasting to the most fleeting — unknown product, then the grid, then the bag — because
    the answer a caller acts on should be the obstacle that more wood would not move: a bag
    that cannot pay and a shape that does not fit are both true of the same reading, and
    sending a mind off to gather logs against the second is a run spent on the wrong thing.

    `inventory` is optional and never defaulted to "affordable": the material check is only
    made when a caller hands over an actual reading, because a resolver that guessed at the
    bag would be the thing in this build that claims to know what the Kin is holding.
    """

    recipe = RECIPES.get(product_id)
    if recipe is None:
        return CRAFT_RECIPE_UNAVAILABLE
    if not recipe.fits(grid_side):
        return CRAFT_GRID_TOO_SMALL
    if inventory is not None and any(
        item_total(inventory, item_id) < count for item_id, count in recipe.ingredients
    ):
        return CRAFT_MATERIALS_MISSING
    return recipe


@dataclass(frozen=True, slots=True)
class BuildStep:
    """One position in a build order: the craft to run, and how many of its product the goal
    still wants."""

    recipe: Recipe
    #: Items of `recipe.product_id` still outstanding, which is a demand rather than a
    #: production target: a batch that yields four is asked for by a goal that owes two. The
    #: caller compares this to an inventory, so rounding it up to whole batches here would
    #: promise a bag that stays short after the last craft.
    required_total: int

    @property
    def product_id(self) -> str:
        return self.recipe.product_id

    @property
    def materials(self) -> tuple[tuple[str, int], ...]:
        """One batch's cost. The game only ever pays one batch at a time, so a check against
        the bag is a check against these counts and not against `required_total`, which is the
        number of products the goal wants across however many batches that takes."""

        return self.recipe.ingredients


def build_plan(
    product_id: str,
    *,
    quantity: int = 1,
    inventory: InventoryValue | None = None,
) -> tuple[BuildStep, ...] | str:
    """The order of crafts that leads from a bag to `quantity` of a product, or a name.

    `CRAFT_RECIPE_UNAVAILABLE` if the table cannot answer for the goal or for something it
    eats; otherwise one step per craftable item, ingredients before the products that consume
    them. The caller asks about a product and receives a sequence of recipes — it does not
    hand over the recipes, and neither does a model.

    The counts are multiplied out of `yields`, which is the only arithmetic that turns a
    shape into a number of items: a pickaxe eats three planks and two sticks, and those two
    sticks are one batch, which eats two more planks, so the job is five planks and not the
    three a glance at the pickaxe alone would say.

    `inventory` is optional in the same sense `resolve_craft` means it: with no bag handed over
    every count is the gross one, and with a bag each step's count is what that bag still
    owes once the items already held are credited. Crediting happens before a step's demand is
    pushed onto its ingredients, so a partially-built job is short only the remainder, and a
    finished one asks for nothing — which is what lets a later reading, rather than a plan
    author, decide that the work is over.
    """

    if product_id not in RECIPES:
        return CRAFT_RECIPE_UNAVAILABLE

    order: list[str] = []
    visited: set[str] = set()

    def visit(product: str, path: frozenset[str]) -> str | None:
        """Depth-first, appending after the ingredients so a recipe is never listed before
        something it eats. A row that eats its own product is a wrong row, not a world
        condition, and the word for it is the one the caller already handles."""

        if product in path:
            return CRAFT_RECIPE_UNAVAILABLE
        recipe = RECIPES.get(product)
        if recipe is None or product in visited:
            return None  # gathered rather than crafted: the plan ends where the table does.
        for item_id, _ in recipe.ingredients:
            failure = visit(item_id, path | {product})
            if failure is not None:
                return failure
        visited.add(product)
        order.append(product)
        return None

    if visit(product_id, frozenset()) is not None:
        return CRAFT_RECIPE_UNAVAILABLE

    gross = dict.fromkeys(order, 0)
    gross[product_id] = quantity
    owed: dict[str, int] = {}
    for product in reversed(order):
        recipe = RECIPES[product]
        still_needed = gross[product]
        if inventory is not None:
            still_needed -= item_total(inventory, product)
        still_needed = max(still_needed, 0)
        owed[product] = still_needed
        if still_needed == 0:
            continue
        batches = _batches_for(still_needed, recipe.yields)
        for item_id, count in recipe.ingredients:
            if item_id in gross:
                gross[item_id] += batches * count

    return tuple(
        BuildStep(recipe=RECIPES[product], required_total=owed[product]) for product in order
    )


def plan_needs_larger_grid(
    steps: tuple[BuildStep, ...],
    *,
    grid_side: int = PLAYER_GRID_SIDE,
) -> bool:
    """Whether any step lays out a shape the `grid_side` screen cannot hold.

    `build_plan` answers what has to be crafted and never whether a single craft is runnable on
    the grid being opened — that question belongs to `resolve_craft`, made against a live reading.
    A caller with only a plan (a pre-run panel with no bag) still wants to know if the goal's last
    step is a three-by-three shape this build cannot open, so the check lives here, read off each
    step's own `recipe.fits`. A newly curated 3×3 row is caught by this without a line of the
    caller changing.
    """

    return any(not step.recipe.fits(grid_side) for step in steps)


def _batches_for(items: int, yields: int) -> int:
    """How many whole batches of a recipe make at least `items` — the ceiling division a plan's
    counts are built out of, written once so the rounding is not re-invented per caller."""

    return -(-items // yields)
