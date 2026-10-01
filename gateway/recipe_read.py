"""A read that surfaces the recipe catalog's own coverage boundary, so a panel cannot over-claim.

Criterion 6 asks that the recipe knowledge source and its support boundary be explicit — that the
small curated catalog never be presented as a universal crafting source. Core already models that
boundary as data: `recipe_coverage()` returns the game version, the covered products, the
watched/curated split, and `universal=False`, each read off the `RECIPES` rows themselves. What was
missing is a caller. Until now the only surface that reached this boundary was a goal projection
(`gateway.goal_read`), which answers one product at a time; nothing exposed the whole covered region
so an operator could see, in one place, which crafts the Kin has watched happen and which are still
only curated claims.

This read is that caller, and it adds no knowledge of its own — it renders `recipe_coverage()` plus
the per-row facts (grid shape, ingredients, provenance) exactly as the catalog holds them. Two
honesty properties survive the mapping and are the reason this path exists: `universal` is the
catalog's hard-wired `False`, copied rather than inferred so a future caller cannot turn a finite
fallback into a general source by omission; and each row's `provenance` distinguishes a craft seen
on the controlled server from one lifted from the game's data, so a panel that shows a recipe can
show how much it actually stands behind it. A product outside the cover is not listed here at all —
it is answered elsewhere by `CRAFT_RECIPE_UNAVAILABLE`, and this finite table making no room for it
is the boundary.

It is a GET only, and it has no write partner: the catalog is product data, not operator settings,
so there is nothing on this path to authorize. Unlike the identity, config, session and goal reads
it echoes no `csrfToken` — a token exists to guard a write, and a read with no write to pair with
has none to hand out. The loopback/same-origin posture the other reads rely on is inherited from
the server that mounts it.
"""

from __future__ import annotations

from typing import Any, Final

from gateway.readmodel import STALE_AFTER_MS
from minekin_core.application.ports.clock import Clock
from minekin_core.domain.recipe_catalog import (
    PLAYER_GRID_SIDE,
    RECIPES,
    Recipe,
    recipe_coverage,
)

#: The read that reports the catalog's coverage boundary. GET only, and unlike the settings reads it
#: has no write sibling — the recipe table is product knowledge, not something the operator edits.
RECIPE_PATH: Final = "/api/v1/dashboard/recipe-coverage"

SCHEMA: Final = "kin-dashboard-recipe/1.0.0"


def recipe_read(*, clock: Clock) -> dict[str, Any]:
    """The whole covered region as data: version, coverage split, and one row per known craft.

    `covered` is split into `live_confirmed` and `curated_unwatched` so a reader sees which
    crafts the Kin has watched and which are still only a claim from the game's data; `universal`
    is copied straight from the boundary's hard-wired `False`. The rows carry the grid shape and a
    `fits_player_grid` flag derived from `PLAYER_GRID_SIDE`, so a panel can mark a three-by-three
    recipe (a pickaxe) as beyond the two-by-two grid this build can open without re-deriving the fit
    rule. A read of a table with no rows would still be honest — it simply has nothing to cover.
    """

    coverage = recipe_coverage()
    return {
        "schemaVersion": SCHEMA,
        "observedAt": clock.utc_now().isoformat(),
        "staleAfterMs": STALE_AFTER_MS,
        "game_version": coverage.game_version,
        "universal": coverage.universal,
        "player_grid_side": PLAYER_GRID_SIDE,
        "covered": sorted(coverage.covered),
        "live_confirmed": sorted(coverage.live_confirmed),
        "curated_unwatched": sorted(coverage.curated_only),
        "recipes": [_row(recipe) for _, recipe in sorted(RECIPES.items())],
    }


def _row(recipe: Recipe) -> dict[str, Any]:
    """One catalog row as the panel shows it: shape, cost, yield, provenance, and whether the
    grid this build opens can hold it.

    `fits_player_grid` is computed from `PLAYER_GRID_SIDE` rather than stored so a grid-side change
    (the day a skill places a worktable) re-flavors every row at once instead of leaving a per-row
    flag to rot. `provenance` is the enum's value string, which is what `recipe_coverage` already
    splits on and what a reader distinguishes watched from curated by.
    """

    return {
        "product_id": recipe.product_id,
        "recipe_id": recipe.recipe_id,
        "grid_width": recipe.grid_width,
        "grid_height": recipe.grid_height,
        "yields": recipe.yields,
        "fits_player_grid": recipe.fits(PLAYER_GRID_SIDE),
        "provenance": recipe.provenance.value,
        "ingredients": [
            {"item_id": item_id, "count": count} for item_id, count in recipe.ingredients
        ],
    }
