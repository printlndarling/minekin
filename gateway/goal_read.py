"""Project the saved goal and its curated material plan, including wider-grid prerequisites.

The catalog supplies public recipe knowledge, not current inventory or live completion. A known
wider-grid enabler is costed into the plan; an unsupported recipe or grid remains a named boundary.
No read starts a session or performs a game action.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, cast

from gateway.readmodel import STALE_AFTER_MS
from minekin_core.application.ports.clock import Clock
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.goal_spec import Milestone
from minekin_core.domain.operator_config import OperatorConfig, load_operator_config
from minekin_core.domain.recipe_catalog import (
    CRAFT_GRID_TOO_SMALL,
    PLAYER_GRID_SIDE,
    BuildStep,
    build_plan,
    grid_enabler_for,
    largest_grid_in_plan,
    plan_needs_larger_grid,
)

#: The read that projects the operator's saved goal. It is a GET only — setting a goal stays
#: the config write's job, so this path cannot become a fourth hole in the write-refusing face.
GOAL_PATH: Final = "/api/v1/dashboard/goal"

SCHEMA: Final = "kin-dashboard-goal/1.0.0"


def goal_read(root: Path, *, clock: Clock, csrf_token: str) -> dict[str, Any]:
    """Read the saved milestone and gross recipe costs, never fabricated live progress."""

    load_error: str | None = None
    try:
        config = load_operator_config(root)
    except MinekinError as error:
        config = OperatorConfig()
        load_error = error.safe_message

    raw_fields = config.as_document()["fields"]
    assert isinstance(raw_fields, dict)  # the document's own shape; runtime guard
    fields = cast("dict[str, Any]", raw_fields)  # narrowed for the projection

    base = {
        "schemaVersion": SCHEMA,
        "loadError": load_error,
        "csrfToken": csrf_token,
        "observedAt": clock.utc_now().isoformat(),
        "staleAfterMs": STALE_AFTER_MS,
    }

    product = str(fields.get("goal_product_id", ""))
    if not product:
        return {**base, "configured": False, "milestone": None, "plan": None, "precondition": None}

    milestone = Milestone(
        product_id=product,
        quantity=int(fields.get("goal_quantity") or 1),
        source_item_id=str(fields.get("goal_source_item_id", "")),
        direction=str(fields.get("goal_direction", "")),
    )
    planned = build_plan(
        milestone.product_id, quantity=milestone.quantity, grid_side=PLAYER_GRID_SIDE
    )
    if isinstance(planned, str):
        return {
            **base,
            "configured": True,
            "milestone": milestone.as_document(),
            "plan": None,
            "precondition": planned,
        }
    enabler = (
        grid_enabler_for(largest_grid_in_plan(planned)) if plan_needs_larger_grid(planned) else None
    )
    if plan_needs_larger_grid(planned) and enabler is None:
        return {
            **base,
            "configured": True,
            "milestone": milestone.as_document(),
            "plan": None,
            "precondition": CRAFT_GRID_TOO_SMALL,
        }
    if enabler is not None:
        enabling_step = next(row for row in planned if row.product_id == enabler.product_id)
        ordered: list[BuildStep] = []
        for row in planned:
            if not row.recipe.fits(PLAYER_GRID_SIDE) and enabling_step not in ordered:
                ordered.append(enabling_step)
            if row not in ordered:
                ordered.append(row)
        planned = tuple(ordered)
    return {
        **base,
        "configured": True,
        "milestone": milestone.as_document(),
        "plan": [_step(row) for row in planned],
        "precondition": None,
    }


def _step(step: BuildStep) -> dict[str, Any]:
    """One owed build step as the panel shows it: what it makes, how many, and what it eats.

    The counts here are the plan's gross figures — no reading is folded in — because this
    surface has no live bag to net them against. A caller that wants the remainder owed must
    supply a reading; this one only says what the goal implies, which is the whole question a
    pre-run panel can answer.
    """

    return {
        "product_id": step.product_id,
        "required_total": step.required_total,
        "materials": [{"item_id": item_id, "count": count} for item_id, count in step.materials],
    }
