"""The standing milestone a Kin works toward, supplied as an argument instead of baked in.

S3 shipped with one goal written into the product: a wooden pickaxe, and a build order derived
from it at import time. That made the milestone a second source of truth about what the Kin is
for — the operator, the demo script and the CLI had no way to say anything else — and it meant a
new product was a code change rather than an argument. This module is the seam that replaces it:
a milestone is a product id, a quantity, the raw item it is built from and a heading, and Core
holds no value of its own. Whoever runs a session supplies one, or supplies none and gets a Kin
with no standing craft target, which is a supported shape rather than a broken one (an
answerer may still ask for a craft, and the local layer still resolves and judges it).

Nothing here picks the milestone. A demo names one because a demo is a piece of theatre about a
specific item, a test names several because the point of the interface is that the item is a
parameter, and an operator names one in the environment. The arithmetic those names lean on stays
in `recipe_catalog`, which is keyed by product id and read by whoever has a product to ask about —
it is not grown per item and no product is named by it here.

The reading of the environment follows the house rule from `model_access`: the environment is
passed in as a mapping, the default argument is the process's own, and a malformed value is an
operator's mistake named in a `MinekinError` with `OPERATOR_ACTION` retryability. Only the id
spellings and the quantity are checked; whether the catalog knows the product is deliberately not
answered here, because a goal nobody has curated yet is still a goal the run document can state,
and the refusal for it belongs to the precondition path that already speaks
`CRAFT_RECIPE_UNAVAILABLE`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.perception import WorldObservationValue
from minekin_core.domain.recipe_catalog import BuildStep, build_plan
from minekin_core.domain.skill_parameters import MAX_QUANTITY, is_item_id
from minekin_core.domain.world_actions import item_total

#: The product the Kin is working toward, as the game spells it. Absent means no standing goal.
GOAL_PRODUCT_VARIABLE: Final = "MINEKIN_GOAL_PRODUCT"
#: How many of it the milestone counts as met. Absent means one.
GOAL_QUANTITY_VARIABLE: Final = "MINEKIN_GOAL_QUANTITY"
#: The raw item the mind looks for and picks up on the way, when the crafts it knows cannot pay
#: for themselves yet. Absent means the mind has no resource to hunt for.
GOAL_SOURCE_ITEM_VARIABLE: Final = "MINEKIN_GOAL_SOURCE_ITEM"
#: The heading shown in the run document. Absent means one derived from the product id.
GOAL_DIRECTION_VARIABLE: Final = "MINEKIN_GOAL_DIRECTION"


@dataclass(frozen=True, slots=True)
class Milestone:
    """What the Kin works toward, in the two terms a reading can settle: an item and a count."""

    product_id: str
    quantity: int = 1
    source_item_id: str = ""
    direction: str = ""

    @property
    def label(self) -> str:
        """The heading for the run document — the product's own path, not a name this module keeps.

        Derived rather than defaulted to a constant so that two sessions with two products
        cannot print the same sentence about themselves.
        """

        if self.direction:
            return self.direction
        path = self.product_id.partition(":")[2]
        joined = "_".join(part for part in path.replace("-", "_").split("_") if part)
        return f"hold_{joined}" if joined else "hold_the_goal_product"

    def plan(self, reading: WorldObservationValue | None = None) -> tuple[BuildStep, ...] | str:
        """The order of crafts that leads to this milestone, or the precondition that stops it.

        With a reading the counts are net of what the bag already holds, which is what lets a
        later reading — not a plan author — close the milestone.
        """

        return build_plan(
            self.product_id,
            quantity=self.quantity,
            inventory=None if reading is None else reading.inventory,
        )

    def held(self, reading: WorldObservationValue) -> int:
        return item_total(reading.inventory, self.product_id)

    def as_document(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "quantity": self.quantity,
            "source_item_id": self.source_item_id,
            "direction": self.label,
        }


def milestone_from_environment(
    environ: Mapping[str, str] | None = None,
) -> Milestone | None:
    """The operator's standing milestone, or `None` when nobody named one.

    `None` is the honest answer to an unset `MINEKIN_GOAL_PRODUCT` and is not a fallback to some
    default item: a build that quietly wanted a pickaxe whenever the environment said nothing is
    the thing this module exists to remove. A malformed value refuses rather than being dropped —
    an operator who typed `MINEKIN_GOAL_QUANTITY=zero` means to set a goal, and a Kin that ran the
    demo anyway without one would report success on the wrong sentence.
    """

    source = os.environ if environ is None else environ
    product = source.get(GOAL_PRODUCT_VARIABLE, "").strip()
    if not product:
        return None
    if not is_item_id(product):
        raise _reject(
            "resolve",
            f"{GOAL_PRODUCT_VARIABLE} is {_shown(product)}, which is not an item id the game "
            "spells (a lowercase namespace, a colon, a lowercase path)",
        )

    quantity = _quantity(source.get(GOAL_QUANTITY_VARIABLE, "").strip())
    resource = source.get(GOAL_SOURCE_ITEM_VARIABLE, "").strip()
    if resource and not is_item_id(resource):
        raise _reject(
            "resolve",
            f"{GOAL_SOURCE_ITEM_VARIABLE} is {_shown(resource)}, which is not an item id the "
            "game spells (a lowercase namespace, a colon, a lowercase path)",
        )
    direction = source.get(GOAL_DIRECTION_VARIABLE, "").strip()

    return Milestone(
        product_id=product, quantity=quantity, source_item_id=resource, direction=direction
    )


def _quantity(raw: str) -> int:
    """A whole number of items between one and a stack, or a refusal naming the variable."""

    if not raw:
        return 1
    try:
        quantity = int(raw)
    except ValueError:
        raise _reject(
            "resolve",
            f"{GOAL_QUANTITY_VARIABLE} is {_shown(raw)}, which is not a whole number of items",
        ) from None
    if not 1 <= quantity <= MAX_QUANTITY:
        raise _reject(
            "resolve",
            f"{GOAL_QUANTITY_VARIABLE} is {quantity}, outside the one-to-{MAX_QUANTITY} the ask "
            "vocabulary allows for a single stack",
        )
    return quantity


def _shown(value: str) -> str:
    """The value, quoted and bounded — these four variables hold no secret, which is the only
    reason naming them in a refusal is safe."""

    return repr(value[:64])


def _reject(operation: str, safe_message: str) -> MinekinError:
    return MinekinError(
        component="goal",
        operation=operation,
        category=ErrorCategory.CONFIG,
        retryability=Retryability.OPERATOR_ACTION,
        safe_message=f"GOAL_NOT_CONFIGURED: {safe_message}",
    )
