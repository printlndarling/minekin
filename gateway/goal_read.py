"""The third sanctioned read on the Dashboard surface: the standing goal and what it implies.

A goal is already *set* through this product — `gateway.config_write` persists the four goal
fields, `apply_persisted_config` folds them into the process environment, and a launched session
reads them back as a `Milestone` (the chain `tests/unit/test_startup_config_wiring.py` pins). What
was missing is the view the operator needs to trust that setting: Stage D asks for a panel that can
"提交目标、查看进展", and criterion 4 asks that a configured target read back accurately. Nothing
here adds a second way to write a goal — that would duplicate the config path the identity rule in
`server.py` is built to keep to exactly three holes. It only reads the goal the operator already
saved and projects what it means.

The projection deliberately stops short of claiming progress it cannot see. Core's ledger carries
per-step `goal` strings, not a live inventory snapshot, so this read does not say how many of the
product the bag holds and cannot assert the milestone is met — a `CONFIRMED` belongs to a synced
reading, and inventing one here would be the exact "UNKNOWN 转述为 CONFIRMED" this project refuses.
What it *can* answer from the saved fields alone is the two things the panel is for: which milestone
the next session will work toward (label, product, quantity, source item), and whether the curated
recipe catalog can even build it — the plan the product implies, or the one named precondition
(`CRAFT_RECIPE_UNAVAILABLE`) that says the product sits outside the catalog's declared cover. That
last is the criterion-6 boundary made visible: a goal the small curated set cannot serve is shown as
a boundary, never as a silent green.

The secret and origin boundaries are inherited, not re-drawn: the goal fields hold no credential,
the same loopback/same-origin read posture the other `*_read` functions rely on, and the per-process
`csrfToken` is echoed only so this payload has the shape the other reads have.

"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from gateway.readmodel import STALE_AFTER_MS
from minekin_core.application.ports.clock import Clock
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.goal_spec import Milestone
from minekin_core.domain.operator_config import OperatorConfig, load_operator_config
from minekin_core.domain.recipe_catalog import BuildStep

#: The read that projects the operator's saved goal. It is a GET only — setting a goal stays
#: the config write's job, so this path cannot become a fourth hole in the write-refusing face.
GOAL_PATH: Final = "/api/v1/dashboard/goal"

SCHEMA: Final = "kin-dashboard-goal/1.0.0"


def goal_read(root: Path, *, clock: Clock, csrf_token: str) -> dict[str, Any]:
    """The saved milestone and the build plan the catalog implies for it, or the reason it stops.

    A run document has no goal is a supported shape rather than a fault: an unset product comes
    back as `configured: false` with a null projection, which is the panel's honest empty state.
    A hand-edited document that will not parse is reported through `loadError` with an empty
    projection the same way `config_read` does, so the surface stays usable and the operator is
    told the file is unreadable rather than being shown a goal that was never saved.
    """

    load_error: str | None = None
    try:
        config = load_operator_config(root)
    except MinekinError as error:
        config = OperatorConfig()
        load_error = error.safe_message

    fields = config.as_document()["fields"]
    assert isinstance(fields, dict)  # the document's own shape; narrowed for the projection

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
    planned = milestone.plan()
    if isinstance(planned, str):
        return {
            **base,
            "configured": True,
            "milestone": milestone.as_document(),
            "plan": None,
            "precondition": planned,
        }
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
