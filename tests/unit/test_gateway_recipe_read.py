"""Reading the catalog's coverage boundary back: the version, the watched/curated split, and rows.

`gateway.goal_read` answers what the catalog implies for one saved product. This surface answers
the whole covered region at once, and the promise it must keep is criterion 6's: a small curated
catalog is allowed as a fallback *only* because it says out loud what it does and does not stand
behind. The sharpest things to pin are therefore the honesty properties, not the row count —
`universal` must be the catalog's hard-wired `False` and not a value a caller could flip, the
live/curated split must be derived from the rows so a watched craft and a curated claim are visibly
different kinds of knowing, and a three-by-three row must carry a `fits_player_grid: false` so the
panel can name the grid limit without re-deriving it. And because this read has no write partner,
it must echo no `csrfToken` — a token guards a write, and handing one out here would imply a hole
that does not exist.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from gateway.readmodel import STALE_AFTER_MS
from gateway.recipe_read import RECIPE_PATH, SCHEMA, recipe_read
from gateway.server import GatewayServer, ReadRequestHandler, ReadService
from minekin_core.application.ports.clock import FakeClock
from minekin_core.domain.recipe_catalog import (
    CATALOG_GAME_VERSION,
    PLAYER_GRID_SIDE,
    RECIPES,
    recipe_coverage,
)

PLANKS = "minecraft:oak_planks"
STICK = "minecraft:stick"
TABLE = "minecraft:crafting_table"
PICKAXE = "minecraft:wooden_pickaxe"
_TIMEOUT = 10


def _rows(document: dict) -> dict[str, dict]:  # type: ignore[no-untyped-def]
    return {row["product_id"]: row for row in document["recipes"]}


def test_the_read_names_its_schema_and_the_version_it_describes() -> None:
    document = recipe_read(clock=FakeClock())

    assert document["schemaVersion"] == SCHEMA
    assert document["game_version"] == CATALOG_GAME_VERSION == "1.20.1"
    assert document["player_grid_side"] == PLAYER_GRID_SIDE
    assert document["staleAfterMs"] == STALE_AFTER_MS
    assert "observedAt" in document


def test_the_boundary_is_reported_not_a_universal_source() -> None:
    """The criterion-6 property: this catalog claims to know every craft, and the field says so."""

    document = recipe_read(clock=FakeClock())

    assert document["universal"] is False


def test_the_covered_region_splits_watched_from_curated() -> None:
    """`covered` is exactly the live plus curated subsets, read off the rows' own provenance."""

    document = recipe_read(clock=FakeClock())
    covered = set(document["covered"])
    live = set(document["live_confirmed"])
    curated = set(document["curated_unwatched"])

    assert covered == live | curated
    assert live & curated == set()
    assert covered == set(RECIPES)
    # The two crafts watched on the controlled server are the only live ones in this build; the
    # worktable and pickaxe are curated claims, and that distinction is the point of the split.
    assert live == {PLANKS, STICK}
    assert curated == {TABLE, PICKAXE}


def test_a_three_by_three_row_is_marked_beyond_the_grid_this_build_opens() -> None:
    """A pickaxe fits no two-by-two grid, and the row says so rather than leaving the reader to
    re-derive the shape rule — the same boundary `goal_read` surfaces as CRAFT_GRID_TOO_SMALL."""

    document = recipe_read(clock=FakeClock())
    rows = _rows(document)

    pickaxe = rows[PICKAXE]
    assert (pickaxe["grid_width"], pickaxe["grid_height"]) == (3, 3)
    assert pickaxe["fits_player_grid"] is False
    assert pickaxe["provenance"] == "curated_unwatched"

    # A one-by-two stick does fit (rotation aside, the longer side decides it), and a watched row
    # reports itself as watched.
    assert rows[STICK]["fits_player_grid"] is True
    assert rows[PLANKS]["provenance"] == "live_confirmed"


def test_a_row_carries_its_cost_and_yield_as_the_catalog_holds_them() -> None:
    document = recipe_read(clock=FakeClock())
    planks = _rows(document)[PLANKS]

    assert planks["recipe_id"] == PLANKS
    assert planks["yields"] == 4
    assert planks["ingredients"] == [{"item_id": "minecraft:oak_log", "count": 1}]


def test_the_read_has_no_csrf_token_because_it_has_no_write_partner() -> None:
    """Every other dashboard read echoes the per-process token so its write can check it. This one
    guards nothing: the recipe table is product data, not operator settings, so a token here would
    imply a fourth write hole that does not exist."""

    document = recipe_read(clock=FakeClock())

    assert "csrfToken" not in document


def test_the_payload_is_derived_from_the_coverage_function() -> None:
    """The rows and the split are the same computation `recipe_coverage()` reports, so a new
    `RECIPES` entry lands here without a second list somebody could forget."""

    document = recipe_read(clock=FakeClock())
    coverage = recipe_coverage()

    assert set(document["covered"]) == set(coverage.covered)
    assert set(document["live_confirmed"]) == set(coverage.live_confirmed)
    assert len(document["recipes"]) == len(coverage.covered)


@pytest.fixture
def base_url(tmp_path: Path) -> Iterator[str]:
    service = ReadService(root=tmp_path, kin_selector=None, clock=FakeClock())
    ReadRequestHandler.service = service
    server = GatewayServer(("127.0.0.1", 0), ReadRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=_TIMEOUT)


def test_the_recipe_route_serves_the_boundary_over_http(base_url: str) -> None:
    with urllib.request.urlopen(base_url + RECIPE_PATH, timeout=_TIMEOUT) as response:
        status = int(response.status)
        document = json.loads(response.read().decode("utf-8"))

    assert status == 200
    assert document["schemaVersion"] == SCHEMA
    assert document["universal"] is False
    assert "csrfToken" not in document


def test_a_post_to_the_recipe_route_is_refused_as_not_a_write(base_url: str) -> None:
    """Coverage stays a read: a POST gets `405`, the same answer a PUT would get, because the write
    surface is only where `authorize_write` runs and this path is not on it."""

    request = urllib.request.Request(base_url + RECIPE_PATH, data=b"{}", method="POST")

    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request, timeout=_TIMEOUT)

    assert caught.value.code == 405


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
