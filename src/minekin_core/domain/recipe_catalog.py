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

The numbers here are facts about Minecraft 1.20.1, and the comments say which of them this
repository has watched the game confirm and which are still only curated. In
`docs/recipe-knowledge-gui-contract.md` these rows are the first of its three objects: public
knowledge about a craft, which is what lets the Kin *intend* one. They are not the account's
recipe book and they are not a confirmation of anything — whether a craft happened is still
judged only by the inventory in a later reading, never by this table having been read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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

    def fits(self, grid_side: int) -> bool:
        """Whether this shape can be laid out in a `grid_side` by `grid_side` grid.

        The longer side decides it: the player may rotate a recipe, so a one-by-two stick
        counts as fitting a two-by-two grid, and a two-by-one does too.
        """

        return max(self.grid_width, self.grid_height) <= grid_side


#: The whole of this build's recipe knowledge, keyed by product. Two of these rows have been
#: watched being crafted on the controlled 1.20.1 server (planks from a log, sticks from
#: planks, both `CONFIRMED` by the readings after them); the other two are curated from the
#: game's own data and are marked as such by the first live run that uses them.
RECIPES: Final[Mapping[str, Recipe]] = MappingProxyType(
    {
        "minecraft:oak_planks": Recipe(
            product_id="minecraft:oak_planks",
            recipe_id="minecraft:oak_planks",
            ingredients=(("minecraft:oak_log", 1),),
            grid_width=1,
            grid_height=1,
            yields=4,
        ),
        "minecraft:stick": Recipe(
            product_id="minecraft:stick",
            recipe_id="minecraft:stick",
            ingredients=(("minecraft:oak_planks", 2),),
            grid_width=1,
            grid_height=2,
            yields=4,
        ),
        "minecraft:crafting_table": Recipe(
            product_id="minecraft:crafting_table",
            recipe_id="minecraft:crafting_table",
            ingredients=(("minecraft:oak_planks", 4),),
            grid_width=2,
            grid_height=2,
            yields=1,
        ),
        "minecraft:wooden_pickaxe": Recipe(
            product_id="minecraft:wooden_pickaxe",
            recipe_id="minecraft:wooden_pickaxe",
            ingredients=(("minecraft:oak_planks", 3), ("minecraft:stick", 2)),
            grid_width=3,
            grid_height=3,
            yields=1,
        ),
    }
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
