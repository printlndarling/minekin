"""Reading the standing goal back: what it is, and what the catalog can do with it.

`gateway.config_write` already lets an operator *set* a goal; these tests pin the separate promise
the goal-read makes — that the panel can show the saved milestone accurately and honestly. The
honest half is the sharper one to test: this surface has no live bag, so it must never print a
number that reads as progress-toward-completion, and a product outside the curated catalog's
declared cover must come back as that boundary, not as an empty plan a reader would guess at. The
plan it does return is gross (no reading folded in), so the arithmetic is the catalog's and the test
compares against `build_plan`, not a hand-typed count.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from gateway.goal_read import GOAL_PATH, SCHEMA, goal_read
from gateway.server import GatewayServer, ReadRequestHandler, ReadService
from minekin_core.application.ports.clock import FakeClock
from minekin_core.domain.operator_config import OperatorConfig, save_operator_config
from minekin_core.domain.recipe_catalog import CRAFT_GRID_TOO_SMALL, CRAFT_RECIPE_UNAVAILABLE

TABLE = "minecraft:crafting_table"
PLANKS = "minecraft:oak_planks"
LOG = "minecraft:oak_log"
PICKAXE = "minecraft:wooden_pickaxe"
_TIMEOUT = 10


def _read(tmp_path: Path, fields: dict[str, Any]) -> dict[str, Any]:
    if fields:
        save_operator_config(tmp_path, OperatorConfig(**fields))
    return goal_read(tmp_path, clock=FakeClock(), csrf_token="token-abc")


def test_an_unset_goal_reads_as_a_supported_empty_state(tmp_path: Path) -> None:
    document = _read(tmp_path, {})

    assert document["schemaVersion"] == SCHEMA
    assert document["configured"] is False
    assert document["milestone"] is None
    assert document["plan"] is None
    assert document["precondition"] is None
    assert document["csrfToken"] == "token-abc"
    assert document["loadError"] is None


def test_a_goal_within_the_cover_reads_back_its_milestone_and_gross_plan(tmp_path: Path) -> None:
    document = _read(tmp_path, {"goal_product_id": TABLE, "goal_quantity": 2})

    assert document["configured"] is True
    milestone = document["milestone"]
    assert milestone["product_id"] == TABLE
    assert milestone["quantity"] == 2
    # An empty direction derives the label from the product path rather than falling back to a
    # constant, so two products cannot print the same sentence about themselves.
    assert milestone["direction"] == "hold_crafting_table"

    shaped = [(step["product_id"], step["required_total"]) for step in document["plan"]]
    assert shaped == [(PLANKS, 8), (TABLE, 2)]
    assert document["precondition"] is None


def test_a_step_carries_the_materials_it_eats_not_a_claim_of_what_is_held(tmp_path: Path) -> None:
    document = _read(tmp_path, {"goal_product_id": TABLE})

    planks_step = document["plan"][0]
    assert planks_step["materials"] == [{"item_id": LOG, "count": 1}]
    # The quantity defaulted to a single item, so one table owes four planks, not eight.
    assert planks_step["required_total"] == 4


def test_a_product_outside_the_cover_reads_as_the_named_boundary_not_an_empty_plan(
    tmp_path: Path,
) -> None:
    document = _read(tmp_path, {"goal_product_id": "minecraft:diamond_pickaxe"})

    assert document["configured"] is True
    assert document["plan"] is None
    assert document["precondition"] == CRAFT_RECIPE_UNAVAILABLE


def test_a_goal_needing_a_larger_grid_reads_as_the_named_grid_boundary(tmp_path: Path) -> None:
    """A pickaxe is in the catalog, but its last step is a 3-by-3 shape the two-by-two grid this
    build opens cannot hold. Rather than print a plan the Kin could not finish, the read reports
    the distinct grid boundary — a different word from the out-of-cover one, so the panel can say
    which limit the operator is hitting."""

    document = _read(tmp_path, {"goal_product_id": PICKAXE})

    assert document["configured"] is True
    assert document["milestone"]["product_id"] == PICKAXE
    assert document["plan"] is None
    assert document["precondition"] == CRAFT_GRID_TOO_SMALL


def test_the_read_never_claims_a_progress_it_cannot_see(tmp_path: Path) -> None:
    """The property that keeps this honest: with no live reading folded in, the payload cannot
    carry a key that would read as "the bag holds N" or "the milestone is met"."""

    document = _read(tmp_path, {"goal_product_id": TABLE, "goal_quantity": 3})

    for forbidden in ("held", "satisfied", "confirmed", "progressPercent", "completed"):
        assert forbidden not in document
        assert forbidden not in document["milestone"]


def test_an_ordinary_source_and_direction_are_carried_through(tmp_path: Path) -> None:
    document = _read(
        tmp_path,
        {
            "goal_product_id": PLANKS,
            "goal_source_item_id": LOG,
            "goal_direction": "hold_some_planks",
        },
    )

    milestone = document["milestone"]
    assert milestone["source_item_id"] == LOG
    assert milestone["direction"] == "hold_some_planks"


@pytest.fixture
def base_url(tmp_path: Path) -> Iterator[tuple[str, Path]]:  # type: ignore[no-untyped-def]
    service = ReadService(root=tmp_path, kin_selector=None, clock=FakeClock())
    ReadRequestHandler.service = service
    server = GatewayServer(("127.0.0.1", 0), ReadRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", tmp_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=_TIMEOUT)


def test_the_goal_read_route_serves_the_saved_milestone(
    base_url: tuple[str, Path],
) -> None:
    url, root = base_url
    save_operator_config(root, OperatorConfig(goal_product_id=TABLE, goal_quantity=2))

    with urllib.request.urlopen(url + GOAL_PATH, timeout=_TIMEOUT) as response:
        status = int(response.status)
        document = json.loads(response.read().decode("utf-8"))

    assert status == 200
    assert document["schemaVersion"] == SCHEMA
    assert document["configured"] is True
    assert document["milestone"]["product_id"] == TABLE


def test_a_post_to_the_goal_route_is_refused_as_not_a_write(
    base_url: tuple[str, Path],
) -> None:
    """The goal stays a read: it is not the fourth hole in the write-refusing face.

    A POST here must get `405` exactly like a PUT would, which is the security fact the route
    table's verb scan rests on — a sanctioned write is only where `authorize_write` runs, and no
    goal path belongs on that list.
    """

    url, _root = base_url
    request = urllib.request.Request(url + GOAL_PATH, data=b"{}", method="POST")

    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request, timeout=_TIMEOUT)

    assert caught.value.code == 405


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
