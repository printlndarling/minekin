"""The milestone is an argument. These cells are the proof, and one of them reads the product.

`goal_spec` is the seam that let the fixed wooden pickaxe leave `minekin_core`: a standing goal is
a product id, a count, the raw item it is built from and a heading, and the operator of a session
supplies them. So the two properties worth pinning are the two that would silently come back if this
module were written carelessly:

**No default item.** An unset `MINEKIN_GOAL_PRODUCT` means no standing goal, not a goal the code
remembers. A Kin that quietly wanted a pickaxe whenever the operator said nothing would pass every
test below and still be the old build.

**A malformed name refuses.** An operator who typed `MINEKIN_GOAL_QUANTITY=zero` meant to set a
goal; a run that carried on without one would report success against the wrong sentence.

The last cell reads the shipped modules for the three fixture item names, because the request this
slice answers was that the product not depend on them, and a claim like that should be checked
rather than asserted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError, Retryability
from minekin_core.domain.goal_spec import (
    GOAL_DIRECTION_VARIABLE,
    GOAL_PRODUCT_VARIABLE,
    GOAL_QUANTITY_VARIABLE,
    GOAL_SOURCE_ITEM_VARIABLE,
    Milestone,
    milestone_from_environment,
)
from minekin_core.domain.perception import (
    InventoryStackValue,
    InventoryValue,
    SelfStateValue,
    WorldObservationValue,
)
from minekin_core.domain.recipe_catalog import CRAFT_RECIPE_UNAVAILABLE

PICKAXE = "minecraft:wooden_pickaxe"
LOG = "minecraft:oak_log"
PLANKS = "minecraft:oak_planks"
STICK = "minecraft:stick"
IRON = "minecraft:iron_sword"


# ----------------------------------------------------------------- the four words an operator says


def test_nobody_named_a_goal_so_there_is_none() -> None:
    """`None` is the honest answer to an unset variable and not a fallback.

    A blank and a whitespace-only value are the same answer: an operator who cleared the line means
    the Kin has no standing craft target, and the session that follows is the no-milestone shape the
    mind already supports.
    """

    for raw in ("", "   ", "\t"):
        environ = {GOAL_PRODUCT_VARIABLE: raw}
        assert milestone_from_environment(environ) is None
    assert milestone_from_environment({}) is None


def test_an_operator_supplies_the_whole_milestone_and_this_side_only_checks_the_spellings() -> None:
    environ = {
        GOAL_PRODUCT_VARIABLE: PICKAXE,
        GOAL_QUANTITY_VARIABLE: "3",
        GOAL_SOURCE_ITEM_VARIABLE: LOG,
        GOAL_DIRECTION_VARIABLE: "hold_three_wooden_pickaxes",
    }

    milestone = milestone_from_environment(environ)

    assert milestone is not None
    assert milestone == Milestone(
        product_id=PICKAXE, quantity=3, source_item_id=LOG, direction="hold_three_wooden_pickaxes"
    )
    assert milestone.label == "hold_three_wooden_pickaxes"


def test_only_the_product_is_required_and_everything_else_has_an_answer() -> None:
    """One of the item is the default count because that is what a milestone means; the source and
    the heading stay empty rather than becoming guesses — an empty source is the mind hunting for
    whatever it can see, which is a different behavior from hunting for one named item."""

    milestone = milestone_from_environment({GOAL_PRODUCT_VARIABLE: PLANKS})

    assert milestone is not None
    assert (milestone.quantity, milestone.source_item_id, milestone.direction) == (1, "", "")


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        (GOAL_PRODUCT_VARIABLE, "Wooden Pickaxe"),
        (GOAL_PRODUCT_VARIABLE, "wooden_pickaxe"),
        (GOAL_PRODUCT_VARIABLE, "minecraft:"),
        (GOAL_SOURCE_ITEM_VARIABLE, "a tree"),
        (GOAL_QUANTITY_VARIABLE, "zero"),
        (GOAL_QUANTITY_VARIABLE, "1.5"),
        (GOAL_QUANTITY_VARIABLE, "0"),
        (GOAL_QUANTITY_VARIABLE, "4000"),
    ],
)
def test_a_value_that_is_not_what_the_variable_names_refuses_the_run(
    variable: str, value: str
) -> None:
    """A typo in a goal is an operator's mistake, said once, at the moment it is read.

    `CONFIG` with `OPERATOR_ACTION` retryability is the same shape the model configuration refuses
    with, and for the same reason: nothing this process does can fix it, and a Kin that played
    anyway would be reporting a run the operator did not ask for. The refusal names the variable and
    the value it holds, which is safe because a goal is not a credential.
    """

    with pytest.raises(MinekinError) as caught:
        milestone_from_environment({GOAL_PRODUCT_VARIABLE: PICKAXE, variable: value})

    error = caught.value
    assert error.category is ErrorCategory.CONFIG
    assert error.retryability is Retryability.OPERATOR_ACTION
    assert error.exit_code is ExitCode.CONFIG
    assert error.safe_message.startswith("GOAL_NOT_CONFIGURED:")
    assert variable in error.safe_message


# ---------------------------------------------------------------------------------- what it answers


def test_a_heading_is_derived_from_the_product_rather_than_kept_by_this_module() -> None:
    """Two sessions with two products cannot print the same sentence about themselves, which is what
    a constant heading would guarantee."""

    assert Milestone(product_id=PICKAXE).label == "hold_wooden_pickaxe"
    assert Milestone(product_id=PLANKS).label == "hold_oak_planks"
    assert Milestone(product_id="minekin:thing").label == "hold_thing"
    assert Milestone(product_id="minecraft:").label == "hold_the_goal_product"
    assert Milestone(product_id=PICKAXE, direction="gather_and_craft").label == "gather_and_craft"


def test_the_milestone_answers_with_the_catalogs_order_and_the_readings_count() -> None:
    """The arithmetic is the catalog's, reached through this seam: the order is the table's build
    order, a reading is what trims it, and an uncurated product is the name of the precondition
    rather than an invented plan.

    The trimmed row is the whole reason the seam takes a reading at all: a bag holding five planks
    owes no planks and still owes the sticks, and the satisfied row survives at zero because naming
    what is left is the caller's job — this method restates the table, it does not decide what to
    run. `held` is the world's number and nobody else's claim.
    """

    pickaxe = Milestone(product_id=PICKAXE, quantity=1)
    planned = pickaxe.plan()
    sword = Milestone(product_id=IRON)

    assert isinstance(planned, tuple)
    assert [step.product_id for step in planned] == [PLANKS, STICK, PICKAXE]
    halfway = pickaxe.plan(reading((PLANKS, 5)))
    assert isinstance(halfway, tuple)
    assert [(step.product_id, step.required_total) for step in halfway] == [
        (PLANKS, 0),
        (STICK, 2),
        (PICKAXE, 1),
    ]
    assert sword.plan() == CRAFT_RECIPE_UNAVAILABLE
    assert pickaxe.held(reading((PICKAXE, 1))) == 1
    assert pickaxe.held(reading((PLANKS, 4))) == 0


def test_a_milestone_written_as_a_document_carries_its_own_label() -> None:
    document = Milestone(product_id=PLANKS, quantity=8, source_item_id=LOG).as_document()

    assert document == {
        "product_id": PLANKS,
        "quantity": 8,
        "source_item_id": LOG,
        "direction": "hold_oak_planks",
    }


# --------------------------------------------------------------- the product path names no fixture


@pytest.mark.parametrize(
    "module",
    ["application/player_mind.py", "domain/goal_spec.py"],
)
def test_the_shipped_mind_and_goal_never_name_a_fixture_item(module: str) -> None:
    """`oak_planks`, `stick` and `wooden_pickaxe` are test and demo parameters.

    The check reads the shipped source because the claim it tests is a negative one about it, and
    the names are ones a future change could reintroduce by accident in a docstring. The catalog is
    deliberately not included: its four curated rows are the only place in the product where an item
    is allowed to appear, which is the whole of the knowledge-source rule.
    """

    source = (Path(__file__).resolve().parents[2] / "src" / "minekin_core" / module).read_text(
        encoding="utf-8"
    )

    for name in ("oak_planks", "oak_log", "stick", "wooden_pickaxe", "crafting_table"):
        assert name not in source, f"{module} names {name}"


# -------------------------------------------------------------------------------------- the helpers


def reading(*stacks: tuple[str, int]) -> WorldObservationValue:
    """A bag and nothing else: the milestone's own arithmetic never reads further than that."""

    return WorldObservationValue(
        generation=1,
        game_tick=100,
        self_state=SelfStateValue(
            health=20.0,
            max_health=20.0,
            food=20,
            saturation=5.0,
            alive=True,
            x=0.0,
            y=64.0,
            z=0.0,
            yaw_degrees=0.0,
            pitch_degrees=0.0,
        ),
        aim=None,
        inventory=InventoryValue(
            revision=1,
            stacks=tuple(
                InventoryStackValue(slot=slot, item_id=item_id, count=count)
                for slot, (item_id, count) in enumerate(stacks)
            ),
        ),
        visible_entities=(),
        mining=None,
        gui=None,
    )
