"""The mind asks inside what the readings allow, and only the readings say whether it worked.

These cover §3 of `docs/s3-minimal-player-mind.md` at the layer that owns it: the feasible set
one reading supports, the two needs derived from player-equivalent fields, the precondition
check that stops an unaffordable craft from ever becoming a command, the four failure
attributions and the retry budget that acts on them, and the rule that the direction closes on
a later reading rather than on a decision's own claim. Both shapes are exercised — a scripted
provider that answers, and the shipped `off` provider that refuses by name — because `off` is a
product capability and its path is the one a machine without credentials walks.

Nothing here needs a client. The skills' verdicts are tested where they are produced; what is
tested is which verdicts change the next ask.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import cast

import pytest

from minekin_core.adapters.model import OffModelProvider
from minekin_core.application.player_mind import (
    CLOSE_SCREEN,
    CRAFT_MATERIALS_MISSING,
    DECISION_FROM_LOCAL,
    DECISION_FROM_MODEL,
    GOAL_ACHIEVED,
    NO_FEASIBLE_SKILL,
    NO_LATEST_OBSERVATION,
    RETREAT_FLEE_SECONDS,
    RETRY_BUDGET_PER_SIGNATURE,
    SCAN_PITCH_CYCLE_DEGREES,
    SCAN_YAW_DRIFT_DEGREES,
    SCAN_YAW_STEP_DEGREES,
    FailureCode,
    MindDecisionKind,
    PlayerMind,
    attribute_failure,
    blocker_for,
    craft_blocker,
    craft_options,
    crafting_grid_side,
    feasible_skill_ids,
    mind_for,
    needs_from,
    next_craft,
    observation_summary,
    screen_open,
    select_target,
    shortfalls,
    step_to_run,
)
from minekin_core.domain.goal_spec import Milestone
from minekin_core.domain.model_access import (
    CallOutcome,
    CostLedger,
    Decision,
    DecisionRequest,
    ModelUnavailable,
    UnavailableReason,
)
from minekin_core.domain.perception import (
    AimFace,
    AimKind,
    AimTargetValue,
    BlockTargetValue,
    EntityCandidate,
    GuiScreenValue,
    InventoryStackValue,
    InventoryValue,
    SelfStateValue,
    WorldObservationValue,
)
from minekin_core.domain.recipe_catalog import (
    CRAFT_GRID_TOO_SMALL,
    CRAFT_RECIPE_UNAVAILABLE,
    PLAYER_GRID_SIDE,
    BuildStep,
    build_plan,
)
from minekin_core.domain.world_actions import (
    ActionResultClass,
    SkillOutcome,
    angle_to_degrees,
    skill_capabilities,
)

LOG = "minecraft:oak_log"
PLANKS = "minecraft:oak_planks"
STICK = "minecraft:stick"
PICKAXE = "minecraft:wooden_pickaxe"
TABLE = "minecraft:crafting_table"
COAL = "minecraft:coal"
CAP = 1_000_000

#: The pickaxe is a test parameter here, not a fact about the product: nothing in
#: `minekin_core` names it any more, and every one of these cells passes the milestone in the
#: way an operator's environment would. A second milestone over the same reading — see
#: `PLANK_GOAL` — is what says the arithmetic was never about this item.
GOAL = Milestone(product_id=PICKAXE, source_item_id=LOG, direction="hold_a_wooden_pickaxe")
PLANK_GOAL = Milestone(product_id=PLANKS, source_item_id=LOG, quantity=8)


def plan_of(product_id: str) -> tuple[BuildStep, ...]:
    """The milestone's build order, taken from the catalog rather than written out here.

    A test that restates `planks, sticks, pickaxe` by hand proves nothing about the order; this
    asks the same table the mind asks, so a wrong row in the table fails where it is written.
    """

    planned = build_plan(product_id)
    assert isinstance(planned, tuple)
    return planned


PICKAXE_PLAN = plan_of(PICKAXE)


def state(
    *,
    health: float = 20.0,
    food: int = 20,
    alive: bool = True,
    selected_slot: int | None = None,
) -> SelfStateValue:
    return SelfStateValue(
        health=health,
        max_health=20.0,
        food=food,
        saturation=5.0,
        alive=alive,
        x=0.0,
        y=64.0,
        z=0.0,
        yaw_degrees=0.0,
        pitch_degrees=0.0,
        selected_slot=selected_slot,
    )


def bag(*pairs: tuple[int, str, int]) -> InventoryValue:
    return InventoryValue(
        revision=7,
        stacks=tuple(
            InventoryStackValue(slot=slot, item_id=item_id, count=count)
            for slot, item_id, count in pairs
        ),
    )


def block_aim() -> AimTargetValue:
    return AimTargetValue(
        game_tick=100,
        kind=AimKind.BLOCK,
        block=BlockTargetValue(x=4, y=-2, z=9, face=AimFace.UP),
        targeted_block_id=LOG,
        distance=2.0,
    )


def drop(item_id: str = LOG, *, at: float = 1.0) -> EntityCandidate:
    return EntityCandidate(
        observation_id=f"e-{item_id}-{at}",
        entity_type="minecraft:item",
        relative_x=at,
        relative_y=0.5,
        relative_z=0.0,
        line_of_sight=True,
        item_id=item_id,
        item_count=1,
    )


def reading(
    *,
    tick: int = 100,
    aim: AimTargetValue | None = None,
    items: tuple[tuple[int, str, int], ...] = (),
    entities: tuple[EntityCandidate, ...] = (),
    self_state: SelfStateValue | None = None,
    gui: GuiScreenValue | None = None,
) -> WorldObservationValue:
    return WorldObservationValue(
        generation=1,
        game_tick=tick,
        self_state=self_state if self_state is not None else state(),
        aim=aim,
        inventory=bag(*items),
        visible_entities=entities,
        mining=None,
        gui=gui,
    )


class ScriptedProvider:
    """Answers from a queue and keeps every ask it was handed, in order."""

    def __init__(self, *answers: Decision | ModelUnavailable) -> None:
        self.answers = list(answers)
        self.requests: list[DecisionRequest] = []

    def decide(self, request: DecisionRequest) -> Decision | ModelUnavailable:
        self.requests.append(request)
        if not self.answers:
            return ModelUnavailable(UnavailableReason.NOTHING_FEASIBLE)
        return self.answers.pop(0)


def mind_with(
    *answers: Decision | ModelUnavailable, goal: Milestone | None = GOAL
) -> tuple[PlayerMind, CostLedger]:
    """A mind over a scripted provider and one milestone, which the caller names.

    The milestone is a parameter of the helper rather than a constant inside it because the point
    of these cells is that the same mind runs a different product: a test that could only be run
    about a pickaxe would be testing the fixture, not the interface.
    """

    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(
        ScriptedProvider(*answers), ledger, kin_id="kin-01", persona_seed="seed-9", goal=goal
    )
    return mind, ledger


def outcome(result: ActionResultClass, reason: str = "") -> SkillOutcome:
    return SkillOutcome(result=result, reason=reason, action_id="a-1")


# --------------------------------------------------------------------------- the feasible set


def test_a_log_block_in_view_offers_the_mine_and_a_look() -> None:
    assert set(feasible_skill_ids(GOAL, reading(aim=block_aim()))) == {
        "break_seen_block",
        "use_target",
        "turn_to",
    }


def test_nothing_in_view_offers_only_the_conservative_look() -> None:
    assert feasible_skill_ids(GOAL, reading()) == ("turn_to",)


def test_any_seen_drop_offers_collecting_and_the_ask_names_which() -> None:
    """Collecting is offered for what is on the ground, not for one item the product remembers.

    The narrowing used to be here: a coal drop did not offer collecting because the milestone was
    built from a log. With the ask carried as a parameter the offer is the honest one — there is a
    thing in view to walk to — and the choice of which is the ask's, checked against the summary
    that showed it.
    """

    assert "collect_dropped" in feasible_skill_ids(GOAL, reading(entities=(drop(),)))
    assert "collect_dropped" in feasible_skill_ids(
        GOAL, reading(entities=(drop("minecraft:coal"),))
    )
    assert "collect_dropped" not in feasible_skill_ids(GOAL, reading())


def test_a_craft_is_offered_only_when_the_bag_can_already_pay_for_it() -> None:
    one_log = reading(items=((0, LOG, 1),))
    stage = next_craft(GOAL, one_log)
    assert stage is not None
    assert stage.product_id == PLANKS
    assert "craft_take_result" in feasible_skill_ids(GOAL, one_log)


def test_no_craft_is_offered_when_every_stage_is_short_of_materials() -> None:
    assert next_craft(GOAL, reading()) is None
    assert "craft_take_result" not in feasible_skill_ids(GOAL, reading())


def test_the_plan_is_walked_in_build_order() -> None:
    # Three planks pay for the sticks the pickaxe needs, and for none more planks: the log the
    # first step would cost is not in the bag, so the next step the reading supports is sticks.
    assert next_craft(GOAL, reading(items=((0, PLANKS, 3),))) == PICKAXE_PLAN[1]
    assert next_craft(GOAL, reading(items=((0, PICKAXE, 1),))) is None


def test_a_stage_the_open_grid_cannot_hold_is_never_offered_as_a_craft() -> None:
    """The pickaxe is a three-by-three shape and the only screen the craft skill opens is the
    inventory's two-by-two. Offering it anyway was a command the world could only shrug at;
    the reading that pays for it is now the reading that says it cannot run."""

    paid = reading(items=((0, PLANKS, 3), (1, STICK, 2)))

    assert next_craft(GOAL, paid) is None
    assert next_craft(GOAL, paid, grid_side=3) == PICKAXE_PLAN[2]
    assert "craft_take_result" not in feasible_skill_ids(GOAL, paid)


def test_the_blocked_craft_names_the_precondition_that_is_true_of_the_reading() -> None:
    assert craft_blocker(GOAL, reading(items=((0, LOG, 1),))) == ""
    assert craft_blocker(GOAL, reading()) == CRAFT_MATERIALS_MISSING
    # Planks and sticks enough for the tool but no table stood up: the plan now reserves the
    # crafting table as its own owed step, and this bag is one plank short of that two-by-two
    # shape. The true precondition is a material shortage for the enabler, not a wall the grid
    # can never clear — that is the whole point of threading the grid side into the act path.
    assert (
        craft_blocker(GOAL, reading(items=((0, PLANKS, 3), (1, STICK, 2))))
        == CRAFT_MATERIALS_MISSING
    )
    # The same ingredients with the table already in the bag: the only step owed is the
    # three-by-three the inventory grid cannot hold, so the refusal is now the grid word.
    assert (
        craft_blocker(GOAL, reading(items=((0, PLANKS, 3), (1, STICK, 2), (2, TABLE, 1))))
        == CRAFT_GRID_TOO_SMALL
    )
    # The whole job already in the bag, in whatever shape the crafts left it: nothing is owed,
    # so no precondition is being asked about. The planks that went into the tool are not
    # counted against it — that is the difference between a plan netted off a reading and a
    # shopping list, and the reason a finished run can stop instead of gathering again.
    assert (
        craft_blocker(GOAL, reading(items=((0, PLANKS, 3), (1, STICK, 2), (2, PICKAXE, 1)))) == ""
    )
    assert craft_blocker(GOAL, reading(items=((0, PICKAXE, 1),))) == ""


def test_a_milestone_closed_from_a_reading_asks_for_no_craft() -> None:
    """One pickaxe, with nothing left of the planks that made it: the goal product is held, so
    the plan owes nothing, so there is no craft to offer and nothing to be blocked about. This
    is §4 closing a direction on the world's word, reached through the recipe table rather
    than through a fixture that listed the intermediates as things to keep holding."""

    finished = reading(items=((0, PICKAXE, 1),))

    assert shortfalls(GOAL, finished) == ()
    assert next_craft(GOAL, finished) is None
    assert "craft_take_result" not in feasible_skill_ids(GOAL, finished)


def test_a_model_asking_for_a_craft_the_grid_cannot_hold_produces_no_craft_command() -> None:
    """The offer is built from the same resolution as the command, so an endpoint that asks
    for `craft_take_result` on a reading whose only shortfall needs three by three gets the
    out-of-bounds refusal and the conservative look — never a click into a grid that cannot
    hold the shape."""

    paid = reading(items=((0, PLANKS, 3), (1, STICK, 2)))
    mind, _ = mind_with(
        Decision(skill_id="craft_take_result", reason="make the pickaxe", intent_generation=1)
    )

    intent = mind.next_intent(paid)

    assert [call.name for call in intent.plan.calls] == ["turn_to"]
    assert intent.model_refusal == "DECISION_OUT_OF_BOUNDS"


def test_the_milestone_plan_is_the_catalogs_and_not_a_list_typed_in_here() -> None:
    """The mind asks what a pickaxe implies and takes the answer: planks, then sticks, then the
    tool, the counts multiplied out of each recipe's own yield. Five planks where the demo
    fixture said three, because the stick batch the pickaxe eats is itself made of them — the
    kind of thing a hand-written table gets wrong in a way no reading would notice."""

    assert [step.recipe.recipe_id for step in PICKAXE_PLAN] == [PLANKS, STICK, PICKAXE]
    assert [step.required_total for step in PICKAXE_PLAN] == [5, 2, 1]
    assert PICKAXE_PLAN[2].recipe.grid_width == 3
    assert not PICKAXE_PLAN[2].recipe.fits(PLAYER_GRID_SIDE)


def test_a_bag_partway_through_the_plan_is_credited_rather_than_asked_to_start_again() -> None:
    """Five planks is the whole job's worth of planks, so the only steps still owed are the
    sticks and the tool — and the craft the reading supports is the stick one, which is what
    those five planks were for."""

    halfway = reading(items=((0, PLANKS, 5),))

    owed = shortfalls(GOAL, halfway)
    assert not isinstance(owed, str)
    assert [(step.product_id, step.required_total) for step in owed] == [(STICK, 2), (PICKAXE, 1)]
    assert next_craft(GOAL, halfway) == owed[0]


def test_an_aiming_that_is_a_miss_does_not_offer_a_mine() -> None:
    miss = AimTargetValue(game_tick=100, kind=AimKind.MISS)
    assert "break_seen_block" not in feasible_skill_ids(GOAL, reading(aim=miss))
    # The use key shares the break's precondition: a crosshair that reports nothing is a Kin
    # right-clicking at empty air, so the same refusal that withholds the mine withholds the use.
    assert "use_target" not in feasible_skill_ids(GOAL, reading(aim=miss))


def test_an_aimed_block_offers_the_use_and_an_empty_hands_still_offer_the_look() -> None:
    """A block in the crosshair is a thing the client rendered, so the use is a live option — the
    general means by which a table this bag crafted gets selected, placed and opened on the way to
    a three-by-three shape. The offer is the same on a plain block aim regardless of the bag: what
    is placed is the hand's, which is the skill's concern, not this gate's."""

    offer = feasible_skill_ids(GOAL, reading(aim=block_aim()))
    assert "use_target" in offer
    assert "turn_to" in offer


# --------------------------------------------------------------- the standing container


def test_an_open_container_drops_the_world_actions_and_keeps_the_recipe_click() -> None:
    """A reading that would otherwise offer the break and the collect loses both while a window
    holds the input — they are exactly the actions that, sent into a standing screen, become the
    `GUI_CONFLICT` the run reads back as a silent stream. What survives is the exit and, because a
    container is the one screen the recipe click runs through, a craft this bag can pay for: the
    narrowing stops the crosshair/hot-bar skills, not the handler click, and it is what lets the
    Kin leave the screen before acting on the world rather than hardcoding a close onto the tail
    of the craft."""

    crowded = reading(
        aim=block_aim(),
        items=((0, PLANKS, 5),),
        entities=(drop(),),
        gui=GuiScreenValue(screen_id="", sync_id=7),
    )

    offer = feasible_skill_ids(GOAL, crowded)
    assert CLOSE_SCREEN in offer
    assert "craft_take_result" in offer
    assert "break_seen_block" not in offer
    assert "collect_dropped" not in offer
    assert "turn_to" not in offer


def test_a_container_with_nothing_to_craft_narrows_the_offer_to_leaving_it() -> None:
    """The other half of the same rule: with no curated step the open window can hold, the
    container leaves only the exit, exactly as before the recipe click was allowed inside a
    screen — the craft is offered on the table's answer, never by default."""

    empty_handed = reading(
        aim=block_aim(),
        entities=(drop(),),
        gui=GuiScreenValue(screen_id="", sync_id=7),
    )

    assert feasible_skill_ids(GOAL, empty_handed) == (CLOSE_SCREEN,)


def test_a_three_by_three_step_is_refused_in_the_inventory_and_allowed_at_the_table() -> None:
    """The full pickaxe step is the one curated shape the player's own grid cannot hold, so the
    same bag is a `CRAFT_GRID_TOO_SMALL` in the inventory and a runnable step inside a table
    window — and it is the reading, not a constant, that decides which."""

    nearly = reading(
        items=((0, PLANKS, 3), (1, STICK, 2), (2, TABLE, 1))
    )  # table stood, everything but the tool
    assert crafting_grid_side(nearly) == PLAYER_GRID_SIDE
    assert step_to_run(nearly, PICKAXE, grid_side=PLAYER_GRID_SIDE) is None
    assert blocker_for(nearly, PICKAXE, grid_side=PLAYER_GRID_SIDE) == CRAFT_GRID_TOO_SMALL

    at_table = reading(
        items=((0, PLANKS, 3), (1, STICK, 2)),
        gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=3),
    )
    assert crafting_grid_side(at_table) == 3
    step = step_to_run(at_table, PICKAXE, grid_side=crafting_grid_side(at_table))
    assert step is not None and step.recipe.recipe_id == PICKAXE


def test_the_fallback_stands_up_a_held_enabler_instead_of_gathering_more() -> None:
    """The no-model fallback used to break or scan whenever the crosshair still saw a block, even
    once the bag could already pay for the tool — so it chopped redundant logs and never reached the
    three-by-three. `CRAFT_GRID_TOO_SMALL` is the catalog's word for "every shape this screen holds
    is paid and the only step left needs a wider one," and it can only be reached while the enabler
    is in the bag (owing a table would say `CRAFT_MATERIALS_MISSING`). Standing that table up is the
    next progress, so the fallback right-clicks it rather than gathering — keyed on the blocker word
    and the aim, never a product name. The table sits in the selected slot, so this reading is past
    selecting and into placement."""

    table_selected = reading(
        items=((0, PLANKS, 3), (1, STICK, 2), (2, TABLE, 1)),
        aim=block_aim(),
        entities=(drop(),),
        self_state=state(selected_slot=2),
    )
    mind, _ = mind_with()

    intent = mind.next_intent(table_selected)

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.source == DECISION_FROM_LOCAL
    assert intent.skill == "use_target"
    # The break and the collect stayed offered — the fallback chose to stand the table up over them.
    assert {"break_seen_block", "collect_dropped"} <= set(feasible_skill_ids(GOAL, table_selected))


def test_the_fallback_still_gathers_when_the_wider_step_is_short_of_materials() -> None:
    """The stand-up branch must not fire while a material is genuinely owed. With no table in the
    bag the pickaxe's blocker is `CRAFT_MATERIALS_MISSING`, not the grid word, so the same aimed
    block is still worth breaking — this is the control that keeps the positive cell from being an
    always-use quirk rather than a precondition answer."""

    no_table = reading(
        items=((0, PLANKS, 3), (1, STICK, 2)),
        aim=block_aim(),
        self_state=state(selected_slot=0),
    )
    assert blocker_for(no_table, PICKAXE, grid_side=PLAYER_GRID_SIDE) == CRAFT_MATERIALS_MISSING
    mind, _ = mind_with()

    intent = mind.next_intent(no_table)

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.source == DECISION_FROM_LOCAL
    assert intent.skill == "break_seen_block"


def test_the_client_recipe_book_is_the_authority_the_curated_grid_defers_to() -> None:
    """#47 dynamic source: when the observation's client-reported book names a recipe, the world
    attests it is craftable in the screen being stood in, so the curated grid stand-in is not
    consulted. A reading that reports `minecraft:wooden_pickaxe` craftable yields the step even
    though the caller handed the two-by-two stand-in — the reading, not the constant, decides.
    The same book left empty (no screen, or a Bridge that does not yet surface it) falls through
    to the curated checks, so nothing is offered until the world actually speaks."""

    attested = reading(
        items=((0, PLANKS, 3), (1, STICK, 2)),
        gui=GuiScreenValue(
            screen_id="minecraft:crafting", sync_id=3, craftable_recipe_ids=frozenset({PICKAXE})
        ),
    )
    step = step_to_run(attested, PICKAXE, grid_side=PLAYER_GRID_SIDE)
    assert step is not None and step.recipe.recipe_id == PICKAXE

    silent = reading(
        items=((0, PLANKS, 3), (1, STICK, 2)),
        gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=3),
    )
    assert step_to_run(silent, PICKAXE, grid_side=PLAYER_GRID_SIDE) is None


def test_a_foreign_recipe_in_the_world_set_opens_no_offer_and_clears_no_blocker() -> None:
    """The other control for #47's world-authority branch. The book is trusted only where it names
    a recipe this ask actually owes: an id from elsewhere in the book must not conjure a step, and
    it must not persuade `blocker_for` that the goal is reachable. The defers-to-authority test
    proves an attested owed id opens the offer; this proves a foreign id on an empty bag opens
    nothing — so the branch keys on the recipe identity, not on the book merely being non-empty."""

    FOREIGN = "minecraft:furnace"
    owed = build_plan(PICKAXE, quantity=1, grid_side=PLAYER_GRID_SIDE)
    assert isinstance(owed, tuple)
    assert FOREIGN not in {step.recipe.recipe_id for step in owed}

    foreign = reading(
        items=(),
        gui=GuiScreenValue(
            screen_id="minecraft:crafting", sync_id=3, craftable_recipe_ids=frozenset({FOREIGN})
        ),
    )
    assert step_to_run(foreign, PICKAXE, grid_side=PLAYER_GRID_SIDE) is None
    assert blocker_for(foreign, PICKAXE, grid_side=PLAYER_GRID_SIDE) != ""


def test_a_standing_table_window_offers_the_three_by_three_craft() -> None:
    """The offer and the precondition agree: once the reading says a three-by-three window is up
    and the bag holds the last ingredients, the mind gets `craft_take_result` to click while the
    window stands, and the world actions a screen displaces stay gone."""

    at_table = reading(
        items=((0, PLANKS, 3), (1, STICK, 2)),
        entities=(drop(),),
        gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=3),
    )

    assert set(feasible_skill_ids(GOAL, at_table)) == {CLOSE_SCREEN, "craft_take_result"}


def test_a_window_is_the_handler_not_the_screen_name() -> None:
    """The player's own crafting window reports an empty screen id while its handler is live, and
    `0` is a legal handler id — so only the handler's *absence* says there is nothing to leave."""

    assert screen_open(reading(gui=GuiScreenValue(screen_id="", sync_id=0)))
    assert not screen_open(
        reading(gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=None))
    )
    assert not screen_open(reading())


def test_a_screen_with_no_handler_leaves_the_full_offer_standing() -> None:
    """The inverse half: `sync_id=None` is a reading that says no window is up, so the world
    actions are offered again rather than a close that would spend a step to change nothing."""

    subject = reading(aim=block_aim(), items=((0, PLANKS, 5),))

    assert feasible_skill_ids(GOAL, subject) != (CLOSE_SCREEN,)
    assert set(feasible_skill_ids(GOAL, subject)) == {
        "break_seen_block",
        "craft_take_result",
        "use_target",
        "turn_to",
    }


def test_a_model_that_asks_to_leave_the_screen_becomes_a_close_plan() -> None:
    """The ask is honoured inside the narrowed offer: one call, no arguments, and the capability
    the skill layer names for a step that only touches the screen."""

    mind, _ = mind_with(
        Decision(skill_id=CLOSE_SCREEN, reason="out of the window", intent_generation=1)
    )
    intent = mind.next_intent(
        reading(
            aim=block_aim(), items=((0, PLANKS, 5),), gui=GuiScreenValue(screen_id="", sync_id=7)
        )
    )

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.source == DECISION_FROM_MODEL
    assert intent.skill == CLOSE_SCREEN
    assert intent.arguments == {}
    assert [call.name for call in intent.plan.calls] == [CLOSE_SCREEN]
    assert intent.capabilities == skill_capabilities(CLOSE_SCREEN)


def test_a_model_that_asks_to_use_the_aimed_block_becomes_a_use_plan() -> None:
    """The general place/interact is honoured the same way: one parameterless call carrying the
    use capability, because the ask is 'right-click the thing in the crosshair' and which thing
    that is belongs to the reading, not to a per-product chain. This is the step a three-by-three
    ask uses to put its table down and open it without the mind naming the table at all."""

    mind, _ = mind_with(
        Decision(skill_id="use_target", reason="use what is in view", intent_generation=1)
    )
    intent = mind.next_intent(reading(aim=block_aim(), items=((0, PLANKS, 5),)))

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.source == DECISION_FROM_MODEL
    assert intent.skill == "use_target"
    assert intent.arguments == {}
    assert [call.name for call in intent.plan.calls] == ["use_target"]
    assert intent.capabilities == skill_capabilities("use_target")


def test_a_use_spent_on_one_target_is_not_replayed_until_the_aim_moves() -> None:
    """The repeat a side-effecting click may never be, guarded from the reading rather than
    the retry count.

    Run `37368eba` fired three placements at a crosshair that kept reading the same block and
    returned nothing each time — the goal's "不停重跑赌模型选对角度" made concrete. Here the
    second ask for `use_target` arrives over the SAME aim the first spent on; the offer holds
    `break_seen_block` and `turn_to` besides it, so the mind turns the use key away and reaches
    for another act. A moved aim reads as a different target and the step opens again — the
    guard redirects, it does not strand.
    """

    moved = AimTargetValue(
        game_tick=100,
        kind=AimKind.BLOCK,
        block=BlockTargetValue(x=5, y=-2, z=9, face=AimFace.UP),
        targeted_block_id=LOG,
        distance=2.0,
    )
    mind, _ = mind_with(
        Decision(skill_id="use_target", reason="place what is in hand", intent_generation=1),
        Decision(skill_id="use_target", reason="place it again", intent_generation=2),
        Decision(skill_id="use_target", reason="place against the new block", intent_generation=3),
    )

    first = mind.next_intent(reading(aim=block_aim()))
    assert first.skill == "use_target"
    assert mind.last_use_aim is not None
    mind.record_result(first, outcome(ActionResultClass.UNKNOWN), reading(aim=block_aim()))

    same = mind.next_intent(reading(aim=block_aim()))
    assert same.skill != "use_target"

    after_turn = mind.next_intent(reading(aim=moved))
    assert after_turn.skill == "use_target"


def test_the_repeat_guard_clears_once_a_step_confirms() -> None:
    """A confirmed act renews the offer: the target the Kin finally did something to should not
    stay quarantined, and a fresh block aim is not the spent one anyway."""

    mind, _ = mind_with(
        Decision(skill_id="use_target", reason="place", intent_generation=1),
        Decision(skill_id="use_target", reason="open the placed table", intent_generation=2),
    )
    first = mind.next_intent(reading(aim=block_aim()))
    assert first.skill == "use_target"
    mind.record_result(first, outcome(ActionResultClass.CONFIRMED), reading(aim=block_aim()))
    assert mind.last_use_aim is None

    second = mind.next_intent(reading(aim=block_aim()))
    assert second.skill == "use_target"


def test_the_off_mind_leaves_an_open_screen_before_it_looks() -> None:
    """`off` walks the same narrowing: the local reflection sees only `close_screen` in the offer
    and chooses it, so a machine with no credentials still steps out of a stuck window instead of
    sending a crosshair click into it."""

    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(OffModelProvider(), ledger, goal=GOAL)
    intent = mind.next_intent(reading(aim=block_aim(), gui=GuiScreenValue(screen_id="", sync_id=3)))

    assert intent.source == DECISION_FROM_LOCAL
    assert intent.skill == CLOSE_SCREEN
    assert [call.name for call in intent.plan.calls] == [CLOSE_SCREEN]


def test_a_closed_reading_gives_the_world_actions_back() -> None:
    """The whole point of narrowing rather than banning: the next reading, with no handler, offers
    the break again — leave the window, then act on the world, as a two-reading sequence the mind
    closes on its own."""

    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(OffModelProvider(), ledger, goal=GOAL)

    open_reading = reading(aim=block_aim(), gui=GuiScreenValue(screen_id="", sync_id=3))
    closed_reading = reading(aim=block_aim())

    assert mind.next_intent(open_reading).skill == CLOSE_SCREEN
    assert mind.next_intent(closed_reading).skill == "break_seen_block"


# --------------------------------------------------------------------------------- the needs


def test_resource_security_reads_the_milestone_not_the_wood() -> None:
    assert needs_from(GOAL, reading())["resource_security"] == 9
    with_wood = reading(items=((0, PLANKS, 3),))
    assert needs_from(GOAL, with_wood)["resource_security"] == 5
    assert needs_from(GOAL, reading(items=((0, PICKAXE, 1),)))["resource_security"] == 1


def test_safety_reads_the_health_and_food_it_was_given() -> None:
    assert needs_from(GOAL, reading())["safety"] == 1
    assert needs_from(GOAL, reading(self_state=state(health=8.0)))["safety"] == 7
    assert needs_from(GOAL, reading(self_state=state(food=2)))["safety"] == 7
    assert needs_from(GOAL, reading(self_state=state(health=0.0, alive=False)))["safety"] == 9


# -------------------------------------------------------------------------- the ask it builds


def test_the_ask_carries_only_what_the_local_layer_computed() -> None:
    provider = ScriptedProvider()
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(provider, ledger, kin_id="kin-01", persona_seed="seed-9", goal=GOAL)
    subject = reading(aim=block_aim(), items=((0, LOG, 1),))
    mind.next_intent(subject)

    request = provider.requests[0]
    assert request.observation_ref == "tick=100;generation=1"
    assert request.active_goal == GOAL.label
    assert set(request.feasible_skill_ids) == {
        "break_seen_block",
        "craft_take_result",
        "use_target",
        "turn_to",
    }
    assert request.needs == needs_from(GOAL, subject)
    assert request.persona_seed == "seed-9"
    assert request.budget_remaining_micro == ledger.remaining()
    assert request.intent_generation == 1
    assert mind.next_intent(subject).intent_generation == 2
    assert provider.requests[1].intent_generation == 2


def test_a_choice_inside_the_offer_becomes_a_plan_with_arguments() -> None:
    mind, _ = mind_with(
        Decision(skill_id="collect_dropped", reason="it is on the ground", intent_generation=1)
    )
    intent = mind.next_intent(reading(entities=(drop(),), aim=block_aim()))

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.source == DECISION_FROM_MODEL
    assert intent.skill == "collect_dropped"
    assert intent.reason == "it is on the ground"
    assert intent.model_refusal == ""
    call = intent.plan.calls[0]
    assert call.name == "collect_dropped"
    assert call.item_id == LOG
    assert intent.capabilities == skill_capabilities("collect_dropped")


# ------------------------------------------------------------------- the arguments an ask carries


@pytest.mark.parametrize(
    ("milestone", "target", "quantity", "items", "ran", "cost"),
    [
        # The pickaxe milestone, an ask for sticks: the argument chose the product.
        (GOAL, STICK, 2, ((0, PLANKS, 5),), STICK, ((PLANKS, 2),)),
        # A planks milestone of eight, an ask for the four planks one log's batch yields.
        (PLANK_GOAL, PLANKS, 4, ((0, LOG, 3),), PLANKS, ((LOG, 1),)),
        # No standing milestone at all, and a product neither of the other two rows names.
        (None, TABLE, 1, ((0, PLANKS, 8),), TABLE, ((PLANKS, 4),)),
    ],
)
def test_the_same_craft_code_honours_a_different_product_every_time(
    milestone: Milestone | None,
    target: str,
    quantity: int,
    items: tuple[tuple[int, str, int], ...],
    ran: str,
    cost: tuple[tuple[str, int], ...],
) -> None:
    """One implementation, three products, and no line of Core that names any of them.

    This is the reuse proof the interface exists for: the ask says which item and how many, the
    catalog supplies the recipe, and the reading says whether it can be paid. The milestone varies
    across the rows — including the one with no milestone — so a pass cannot be the old
    pickaxe-specific order showing up again under a new argument name.
    """

    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="the ask names it",
            intent_generation=1,
            arguments={"target_item": target, "quantity": quantity},
        ),
        goal=milestone,
    )

    intent = mind.next_intent(reading(items=items))

    assert intent.source == DECISION_FROM_MODEL
    assert intent.model_refusal == ""
    assert intent.skill == "craft_take_result"
    assert intent.arguments == {"target_item": target, "quantity": quantity}
    call = intent.plan.calls[0]
    assert (call.recipe_id, call.product_id) == (ran, ran)
    assert call.materials == cost
    assert intent.reason == "the ask names it"


def test_an_ask_for_a_product_the_table_does_not_know_holds_the_uncurated_word() -> None:
    """`minecraft:iron_sword` is a well-spelled item id, so the port honours the argument and this
    side refuses it by the name of the precondition: no recipe was curated. The Kin is not sent
    clicking at a grid that holds no such shape, and no new row was needed to say so."""

    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="make me a sword",
            intent_generation=1,
            arguments={"target_item": "minecraft:iron_sword", "quantity": 1},
        )
    )

    intent = mind.next_intent(reading(items=((0, PLANKS, 5),)))

    assert intent.kind is MindDecisionKind.HOLD
    assert intent.reason == CRAFT_RECIPE_UNAVAILABLE
    assert intent.plan.calls == ()


def test_an_ask_the_bag_cannot_pay_for_reroutes_with_the_materials_word() -> None:
    """The offer was built from a craft the bag *can* pay for (two planks make sticks), while the
    ask named a product whose chain it cannot (a table wants four planks). The two questions are
    separate, so the answer is honoured as a choice and refused as a plan, under the word that
    sends the Kin back to the resource rather than the one that gives the skill up."""

    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="make a crafting table",
            intent_generation=1,
            arguments={"target_item": TABLE, "quantity": 1},
        )
    )

    intent = mind.next_intent(reading(items=((0, PLANKS, 2),)))

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.skill == "craft_take_result"
    assert intent.plan.calls[0].product_id == STICK
    assert intent.source == DECISION_FROM_LOCAL
    assert intent.model_refusal == CRAFT_MATERIALS_MISSING
    assert mind.last_precondition == CRAFT_MATERIALS_MISSING


def test_an_ask_for_a_three_by_three_selects_the_stood_enabler() -> None:
    """The pickaxe is a three-by-three shape and the inventory grid cannot hold it, so the bare
    craft ask is out of bounds — but with the table already in the bag the ask is no longer the
    terminal wall it was before the grid enabler existed. The mind reroutes to the general next
    step: select the enabler so a later reading can place and open it. Nothing here names a
    table as a special case; the choice comes from `opens_grid_side` and the enabler-aware
    `select_target`, and the terminal `CRAFT_GRID_TOO_SMALL` word is still asserted at the
    craft-precondition level in `test_the_blocked_craft_names_the_precondition_...`."""

    table_and_materials = reading(items=((0, PLANKS, 3), (1, STICK, 2), (2, TABLE, 1)))
    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="make the pickaxe",
            intent_generation=1,
            arguments={"target_item": PICKAXE, "quantity": 1},
        )
    )

    intent = mind.next_intent(table_and_materials)

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.skill == "select_hotbar"
    assert intent.arguments == {"slot": 2, "expected_item_id": TABLE}


def test_an_ask_for_a_three_by_three_builds_the_enabler_it_still_owes() -> None:
    """The same ask against a bag that can pay for the crafting table but has not stood one up:
    the plan reserves that two-by-two shape as its own owed step, it fits the grid this build can
    open, and its materials are in the bag — so the ask advances by crafting the table rather than
    dead-ending on a grid word. This is the general mechanism replacing the per-product wall: no
    name here is hardcoded to a table, only the catalog's `opens_grid_side`."""

    payable_for_table = reading(items=((0, PLANKS, 5), (1, STICK, 2)))
    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="make the pickaxe",
            intent_generation=1,
            arguments={"target_item": PICKAXE, "quantity": 1},
        )
    )

    intent = mind.next_intent(payable_for_table)

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.reason != CRAFT_GRID_TOO_SMALL


def test_an_ask_names_the_drop_it_wants_even_when_the_milestone_named_another() -> None:
    """The milestone says this goal is built from logs; the answer says go and get the coal. The
    argument wins, because the ask vocabulary is what an answerer is offered and the milestone is
    only a default — and the walk is still this side's to plan and the world's to confirm."""

    mind, _ = mind_with(
        Decision(
            skill_id="collect_dropped",
            reason="it is on the ground",
            intent_generation=1,
            arguments={"item_id": COAL},
        )
    )

    intent = mind.next_intent(reading(entities=(drop(COAL),)))

    assert intent.skill == "collect_dropped"
    assert intent.arguments == {"item_id": COAL}
    assert intent.plan.calls[0].item_id == COAL


def test_an_ask_of_an_angle_replaces_the_scan_step() -> None:
    """With no argument the look is the mind's own incremental scan; with one it is the angle that
    was asked for, unchanged. The two are the same skill over different parameters, which is the
    difference between a behavior interface and a fixed routine."""

    mind, _ = mind_with(
        Decision(
            skill_id="turn_to",
            reason="look east and down",
            intent_generation=1,
            arguments={"yaw_degrees": 90.0, "pitch_degrees": -45.0},
        )
    )

    intent = mind.next_intent(reading())

    call = intent.plan.calls[0]
    assert (call.yaw_degrees, call.pitch_degrees) == (90.0, -45.0)


def test_a_local_choice_carries_the_arguments_the_milestone_and_reading_imply() -> None:
    """An ask nobody put to a model still gets its parameters filled, from the milestone and the
    reading, and the document says which: `source=local` beside an `arguments` map that names the
    product the mind was working toward. Without this the fallback would be a second, undocumented
    way of deciding what a craft is for."""

    provider = OffModelProvider()
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(provider, ledger, goal=PLANK_GOAL, model_enabled=False)

    intent = mind.next_intent(reading(items=((0, LOG, 1),)))

    assert intent.source == DECISION_FROM_LOCAL
    assert intent.skill == "craft_take_result"
    assert intent.arguments == {"target_item": PLANKS, "quantity": 8}
    assert intent.plan.calls[0].product_id == PLANKS
    assert intent.as_document()["arguments"] == {"target_item": PLANKS, "quantity": 8}
    assert mind.as_document()["executing_arguments"] == {"target_item": PLANKS, "quantity": 8}
    assert mind.as_document()["milestone"] == PLANK_GOAL.as_document()


# ------------------------------------------------------------------------- the summary an ask reads


def test_the_ask_shows_the_counts_an_argument_has_to_be_chosen_from() -> None:
    """Asked to name a `target_item`, an answerer can only guess if it is not told what the bag
    holds — and a guess comes back refused as a missing recipe or a short bag, which reads like a
    bad decision and is a badly-posed question. So the counts travel: the same reading the
    precondition is judged from, in fields a choice is made of.

    What does not travel is the geometry. No coordinates, no entity ids, no block positions: the
    answerer has no map and no keys, and §2's promise is a pointer plus a summary, not a view.
    """

    provider = ScriptedProvider()
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(provider, ledger, kin_id="kin-01", persona_seed="seed-9", goal=GOAL)
    subject = reading(items=((0, LOG, 2), (1, PLANKS, 5)), entities=(drop(COAL),))

    mind.next_intent(subject)

    summary = provider.requests[0].observation_summary
    assert summary["game_tick"] == 100
    assert summary["time_of_day"] == "day"
    assert summary["inventory"] == {LOG: 2, PLANKS: 5}
    assert summary["dropped_items"] == {COAL: 1}
    assert summary["crafting_grid_side"] == PLAYER_GRID_SIDE
    assert summary["craft_options"] == list(craft_options(subject))
    assert summary["goal"] == {
        "product_id": PICKAXE,
        "quantity": 1,
        "held": 0,
        "direction": GOAL.label,
    }
    for absent in ("x", "y", "z", "relative_x", "entities", "coordinates", "session"):
        assert absent not in summary


def test_the_summary_names_the_time_of_day_from_the_world_clock() -> None:
    """A threat that has never been seen and a night the clock will turn are both real parts of
    survival, and only one of them is visible in this reading — so the model-facing summary
    carries the band name `time_of_day` beside the raw tick. The tick here is on day three:
    the name comes from the day cycle's remainder, not from the world's age."""

    provider = ScriptedProvider()
    mind = mind_for(provider, CostLedger(run_cost_cap=CAP), kin_id="kin-01", persona_seed="seed-9")

    mind.next_intent(reading(tick=2 * 24_000 + 15_000))

    summary = provider.requests[0].observation_summary
    assert summary["game_tick"] == 63_000
    assert summary["time_of_day"] == "night"


def test_a_session_with_no_milestone_asks_about_the_world_and_not_about_a_goal() -> None:
    """No standing product means no `goal` field rather than a fabricated one: the summary keeps
    saying what the bag could become, because that is the table's answer and not the milestone's,
    and an answerer told about a goal the session does not have would be deciding a fiction."""

    provider = ScriptedProvider()
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(provider, ledger, kin_id="kin-01", persona_seed="seed-9")

    mind.next_intent(reading(items=((0, PLANKS, 5),)))

    summary = provider.requests[0].observation_summary
    assert "goal" not in summary
    assert STICK in cast("list[str]", summary["craft_options"])


def test_the_ask_says_when_the_owed_plan_needs_a_larger_grid() -> None:
    """Whether the goal's remaining work fits the grid the client can open is a goal-level fact
    read off the catalog and this reading, not a product name this module carries: the last craft
    of a pickaxe is a three-by-three shape a two-by-two hand grid cannot hold, so the summary says
    a larger grid is needed and the Kin reaches it by general means rather than a hand-craft that
    could only shrug. A goal the hand grid can finish carries the flag as false, and it clears on
    its own once a wider window is what the reading reports."""

    pickaxe_provider = ScriptedProvider()
    mind = mind_for(
        pickaxe_provider,
        CostLedger(run_cost_cap=CAP),
        kin_id="kin-01",
        persona_seed="seed-9",
        goal=GOAL,
    )
    mind.next_intent(reading(items=((0, PLANKS, 8), (1, STICK, 2))))
    assert pickaxe_provider.requests[0].observation_summary["larger_grid_needed"] is True

    hand = Milestone(product_id=PLANKS, source_item_id=LOG)
    planks_provider = ScriptedProvider()
    planks_mind = mind_for(
        planks_provider,
        CostLedger(run_cost_cap=CAP),
        kin_id="kin-02",
        persona_seed="seed-8",
        goal=hand,
    )
    planks_mind.next_intent(reading(items=((0, LOG, 3),)))
    assert planks_provider.requests[0].observation_summary["larger_grid_needed"] is False


# ------------------------------------------------------------- refusals take the local path


def test_the_off_provider_leaves_a_named_refusal_and_a_local_choice() -> None:
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(OffModelProvider(), ledger, model_enabled=False, goal=GOAL)
    intent = mind.next_intent(reading(aim=block_aim()))

    assert intent.source == DECISION_FROM_LOCAL
    assert intent.skill == "break_seen_block"
    assert intent.model_refusal == UnavailableReason.MODEL_NOT_CONFIGURED.value
    # `off` asks nothing, so it costs nothing: the ledger stays empty rather than filling
    # with refusals that would read as a failing model.
    assert ledger.calls == 0
    assert ledger.spent == 0
    document = mind.as_document()
    assert document["decision_source"] == DECISION_FROM_LOCAL
    assert document["model_refusal"] == "MODEL_NOT_CONFIGURED"
    assert document["model_enabled"] is False


def test_the_local_order_finishes_the_chain_before_it_looks() -> None:
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(OffModelProvider(), ledger, goal=GOAL)

    assert (
        mind.next_intent(reading(items=((0, LOG, 1), (1, PLANKS, 1), (2, STICK, 2)))).skill
        == "craft_take_result"
    )
    assert mind.next_intent(reading(entities=(drop(),))).skill == "collect_dropped"
    hurt = reading(aim=block_aim(), self_state=state(health=6.0))
    # A hit already taken outranks the chain the way a rendered threat does: with nothing
    # hostile in the reading, the drop is the evidence and leaving is the step.
    assert mind.next_intent(hurt).skill == "retreat"
    assert mind.next_intent(reading(aim=block_aim())).skill == "break_seen_block"


def test_a_choice_outside_the_offer_is_refused_by_name_and_not_run() -> None:
    mind, _ = mind_with(Decision(skill_id="fly_to_the_log", reason="sure", intent_generation=1))
    intent = mind.next_intent(reading())

    assert intent.skill == "turn_to"
    assert intent.source == DECISION_FROM_LOCAL
    assert intent.model_refusal == UnavailableReason.DECISION_OUT_OF_BOUNDS.value
    assert {call.name for call in intent.plan.calls} == {"turn_to"}


def test_a_late_answer_takes_the_same_conservative_path_as_a_timeout() -> None:
    mind, _ = mind_with(ModelUnavailable(UnavailableReason.STALE_GENERATION))
    subject = reading(aim=block_aim())
    intent = mind.next_intent(subject)

    assert intent.model_refusal == "STALE_GENERATION"
    assert intent.source == DECISION_FROM_LOCAL
    assert mind.direction == GOAL.label
    assert mind.goal_met is False


def test_the_cost_cap_refuses_calls_and_not_playing() -> None:
    ledger = CostLedger(run_cost_cap=10)
    ledger.record_call(
        "openai_compatible",
        "some-model",
        1,
        CallOutcome.UNAVAILABLE,
        reason=UnavailableReason.RUN_COST_CAP_REACHED,
    )
    mind = mind_for(
        OffModelProvider(reason=UnavailableReason.RUN_COST_CAP_REACHED),
        ledger,
        model_enabled=False,
        goal=GOAL,
    )
    intent = mind.next_intent(reading(aim=block_aim(), items=((0, LOG, 1),)))

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.model_refusal == "RUN_COST_CAP_REACHED"
    document = mind.as_document()
    assert document["model_cap_refusals"] == 1
    assert document["model_calls"] == 0


# ---------------------------------------------------------------- results and their attribution


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("NO_SEEN_DROP", FailureCode.RESOURCE_UNAVAILABLE),
        (CRAFT_MATERIALS_MISSING, FailureCode.RESOURCE_UNAVAILABLE),
        ("MINE_TARGET_NOT_AIMED", FailureCode.RESOURCE_UNAVAILABLE),
        ("SKILL_UNKNOWN", FailureCode.SKILL_NOT_IMPLEMENTED),
        ("SKILL_ARGUMENT_MISSING", FailureCode.SKILL_NOT_IMPLEMENTED),
        (CRAFT_GRID_TOO_SMALL, FailureCode.SKILL_NOT_IMPLEMENTED),
        (CRAFT_RECIPE_UNAVAILABLE, FailureCode.SKILL_NOT_IMPLEMENTED),
        ("NO_CONFIRMING_OBSERVATION", FailureCode.INSUFFICIENT_INFORMATION),
        ("MINING_STALLED", FailureCode.ACTION_NOT_EFFECTIVE),
        ("SCREEN_NOT_CONFIRMED", FailureCode.ACTION_NOT_EFFECTIVE),
    ],
)
def test_a_failure_is_attributed_to_one_of_the_four_codes(
    reason: str, expected: FailureCode
) -> None:
    assert attribute_failure(outcome(ActionResultClass.FAILED, reason)) is expected


def test_an_unreadable_result_is_insufficient_information_whatever_word_it_was_filed_under() -> (
    None
):
    # The reason is a stall, but the result class says the readings could not settle it,
    # and that is the whole of the diagnosis.
    assert attribute_failure(outcome(ActionResultClass.UNKNOWN, "MINING_STALLED")) is (
        FailureCode.INSUFFICIENT_INFORMATION
    )


def test_a_skill_that_keeps_failing_the_same_way_stops_being_asked() -> None:
    mind, _ = mind_with()
    subject = reading(aim=block_aim())
    failing = outcome(ActionResultClass.FAILED, "MINING_STALLED")

    for _ in range(RETRY_BUDGET_PER_SIGNATURE):
        intent = mind.next_intent(subject)
        assert intent.skill == "break_seen_block"
        assert mind.record_result(intent, failing, subject) is FailureCode.ACTION_NOT_EFFECTIVE
        assert "break_seen_block" not in mind.excluded

    intent = mind.next_intent(subject)
    assert mind.record_result(intent, failing, subject) is FailureCode.ACTION_NOT_EFFECTIVE
    assert "break_seen_block" in mind.excluded

    after = mind.next_intent(subject)
    assert "break_seen_block" not in {call.name for call in after.plan.calls}
    assert mind.as_document()["excluded_skills"] == ["break_seen_block"]


def test_an_emptied_offer_blocks_instead_of_replaying() -> None:
    mind, _ = mind_with()
    subject = reading(aim=block_aim())
    failing = outcome(ActionResultClass.FAILED, "MINING_STALLED")

    # The reflection acts on every skill the offer can carry on this reading, in its own order:
    # the break, then the conservative look, then the use on the aimed block as the last resort.
    # Each spends its budget in turn, so the blocked shape only arrives once even the last of them
    # is given up on — which is the guarantee that an offer the world refuses does not replay
    # forever.
    for _ in range(RETRY_BUDGET_PER_SIGNATURE + 1):
        intent = mind.next_intent(subject)
        mind.record_result(intent, failing, subject)
    for _ in range(RETRY_BUDGET_PER_SIGNATURE + 1):
        intent = mind.next_intent(subject)
        mind.record_result(intent, failing, subject)
    for _ in range(RETRY_BUDGET_PER_SIGNATURE + 1):
        intent = mind.next_intent(subject)
        mind.record_result(intent, failing, subject)

    assert set(mind.excluded) == {"break_seen_block", "use_target", "turn_to"}
    assert mind.next_intent(subject).reason == NO_FEASIBLE_SKILL
    assert mind.next_intent(subject).kind is MindDecisionKind.BLOCKED


def test_a_confirmation_clears_the_history_it_was_building_up() -> None:
    mind, _ = mind_with()
    subject = reading(aim=block_aim())
    failing = outcome(ActionResultClass.FAILED, "MINING_STALLED")

    intent = mind.next_intent(subject)
    mind.record_result(intent, failing, subject)
    intent = mind.next_intent(subject)
    mind.record_result(intent, failing, subject)
    assert mind.attempts == {("break_seen_block", FailureCode.ACTION_NOT_EFFECTIVE): 2}

    intent = mind.next_intent(subject)
    assert mind.record_result(intent, outcome(ActionResultClass.CONFIRMED), subject) is None
    assert mind.attempts == {}
    assert mind.last_failure is None
    assert mind.as_document()["failure_attribution"] == ""


# ------------------------------------------------------ what each named precondition changes


def test_a_short_bag_changes_the_ask_without_spending_the_craft_skill() -> None:
    """The skill checks its materials against the newest reading, so a craft refused for a short
    bag is a fact about the bag and not about the skill: the ask that follows is the one that
    fixes it, and once the bag pays again the same skill is offered with its budget untouched.
    Charging three refusals to `craft_take_result` would exclude the very skill the gathered
    wood was going to be spent on — the Kin is sent to the trunk and then told it may never
    craft again."""

    mind, _ = mind_with()
    can_pay = reading(items=((0, LOG, 1),))
    a_drop_in_view = reading(entities=(drop(),))
    refused = outcome(ActionResultClass.FAILED, CRAFT_MATERIALS_MISSING)

    for _ in range(RETRY_BUDGET_PER_SIGNATURE + 1):
        intent = mind.next_intent(can_pay)
        assert intent.skill == "craft_take_result"
        assert (
            mind.record_result(intent, refused, a_drop_in_view) is FailureCode.RESOURCE_UNAVAILABLE
        )
        assert mind.attempts == {}
        assert "craft_take_result" not in mind.excluded

    assert mind.next_intent(a_drop_in_view).skill == "collect_dropped"
    assert mind.next_intent(can_pay).skill == "craft_take_result"
    document = mind.as_document()
    assert document["last_precondition"] == CRAFT_MATERIALS_MISSING
    assert document["excluded_skills"] == []

    intent = mind.next_intent(can_pay)
    assert mind.record_result(intent, outcome(ActionResultClass.CONFIRMED), can_pay) is None
    assert mind.as_document()["last_precondition"] == ""


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (CRAFT_GRID_TOO_SMALL, FailureCode.SKILL_NOT_IMPLEMENTED),
        (CRAFT_RECIPE_UNAVAILABLE, FailureCode.SKILL_NOT_IMPLEMENTED),
    ],
)
def test_a_precondition_no_reading_can_undo_gives_the_skill_up_on_the_first_word(
    reason: str, expected: FailureCode
) -> None:
    """Neither name is something the world can change by being waited on: no amount of wood makes
    a three-by-three shape fit a two-by-two grid, and no reading makes an uncurated product
    craftable. Asking the same skill a second time would be the replay §3 forbids, so the first
    word is enough to take the skill off the offer for the run — and the word, not just the
    coarse code, is what the document carries."""

    mind, _ = mind_with()
    can_pay = reading(items=((0, LOG, 1),))
    intent = mind.next_intent(can_pay)
    assert intent.skill == "craft_take_result"

    assert mind.record_result(intent, outcome(ActionResultClass.FAILED, reason), None) is expected
    assert "craft_take_result" in mind.excluded
    assert mind.attempts == {}
    document = mind.as_document()
    assert document["excluded_skills"] == ["craft_take_result"]
    assert document["last_precondition"] == reason

    after = mind.next_intent(can_pay)
    assert after.skill != "craft_take_result"
    assert after.skill == "turn_to"


# -------------------------------------------------------------------- the goal and its readings


def test_a_decision_that_claims_the_goal_does_not_close_it() -> None:
    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result", reason="this finishes the pickaxe", intent_generation=1
        )
    )
    subject = reading(items=((0, LOG, 1), (1, PLANKS, 1), (2, STICK, 2)))
    intent = mind.next_intent(subject)

    assert intent.skill == "craft_take_result"
    assert "this finishes the pickaxe" in intent.reason
    assert mind.goal_met is False

    # The craft confirms, and the goal still waits for a reading that shows the tool.
    mind.record_result(intent, outcome(ActionResultClass.CONFIRMED), None)
    assert mind.goal_met is False

    later = reading(tick=140, items=((0, PICKAXE, 1),))
    mind.record_result(intent, outcome(ActionResultClass.CONFIRMED), later)
    assert mind.goal_met is True


def test_a_reading_that_loses_the_tool_sends_the_mind_back_to_work() -> None:
    mind, _ = mind_with()
    held = reading(items=((3, PICKAXE, 1),), self_state=state(selected_slot=3))
    mind.observe(held)
    assert mind.goal_met is True

    lost = reading(tick=200, items=((0, LOG, 1),))
    mind.observe(lost)
    assert mind.goal_met is False
    assert mind.next_intent(lost).skill == "craft_take_result"


def test_holding_the_tool_in_hand_is_the_end_of_the_run_not_another_ask() -> None:
    mind, _ = mind_with()
    in_hand = reading(items=((3, PICKAXE, 1),), self_state=state(selected_slot=3))
    intent = mind.next_intent(in_hand)

    assert intent.kind is MindDecisionKind.HOLD
    assert intent.reason == GOAL_ACHIEVED
    assert intent.plan.calls == ()


def test_a_tool_in_the_bag_but_not_in_hand_is_the_one_ask() -> None:
    mind, _ = mind_with()
    not_in_hand = reading(items=((3, PICKAXE, 1),), self_state=state(selected_slot=0))
    intent = mind.next_intent(not_in_hand)

    assert intent.skill == "select_hotbar"
    call = intent.plan.calls[0]
    assert call.slot == 3
    assert call.expected_item_id == PICKAXE
    assert intent.reason == f"hold the {PICKAXE} in hand"


def test_a_mind_with_nothing_to_read_holds_and_says_why() -> None:
    mind, _ = mind_with()
    intent = mind.next_intent(None)

    assert intent.kind is MindDecisionKind.HOLD
    assert intent.reason == NO_LATEST_OBSERVATION
    assert intent.observation_ref == ""


def slime(*, at: float = 2.0, los: bool = True) -> EntityCandidate:
    return EntityCandidate(
        observation_id="e-slime",
        entity_type="minecraft:slime",
        relative_x=at,
        relative_y=0.0,
        relative_z=0.0,
        line_of_sight=los,
    )


def test_a_visible_hostile_stops_the_stand_still_work() -> None:
    """Run-89: a night slime slew the Kin nine times while it kept mining and crafting. A
    hostile the client renders in sight within reach withholds the starts that stand still --
    the swing, the walk to a drop, the screen work -- leaving the honest remainder: face it,
    eat, close, respawn. A hostile out of sight or out of reach is a fact, not a stop-work
    alarm."""

    mind, _ = mind_with()
    observed = reading(aim=block_aim(), entities=(slime(),))
    assert mind.next_intent(observed).skill == "retreat"

    behind_the_camera = reading(aim=block_aim(), entities=(slime(los=False),))
    assert mind.next_intent(behind_the_camera).skill == "break_seen_block"

    far_away = reading(aim=block_aim(), entities=(slime(at=20.0),))
    assert mind.next_intent(far_away).skill == "break_seen_block"


def test_a_health_drop_is_a_hit_even_with_nothing_in_view() -> None:
    mind, _ = mind_with()
    provider = cast(ScriptedProvider, mind.provider)
    mind.observe(reading(self_state=state(health=20.0)))
    observed = reading(tick=200, aim=block_aim(), self_state=state(health=15.0))

    # The drop is the whole evidence, and it buys a step: nothing hostile is rendered, so
    # there is no bearing to take -- the mind leaves on a named hold from where it stands.
    intent = mind.next_intent(observed)
    assert intent.skill == "retreat"
    assert intent.arguments["hold_seconds"] == RETREAT_FLEE_SECONDS
    assert intent.plan.calls[0].hold_seconds == RETREAT_FLEE_SECONDS
    summary = cast(dict[str, object], provider.requests[-1].observation_summary)
    assert summary["danger"] == {"recent_damage": True}
    assert provider.requests[-1].needs["safety"] >= 7

    # The next unhurt reading is not a hit: the flag is about the pair of readings, not a
    # latched alarm, and the work is offered again.
    recovered = reading(tick=300, aim=block_aim(), self_state=state(health=15.0))
    assert mind.next_intent(recovered).skill == "break_seen_block"


def test_a_respawn_makes_the_next_step_off_the_death_spot() -> None:
    """The 2026-10-05 soak: 37 deaths in one night, every respawn back into the same camp
    with nothing hostile rendered between the hops -- the reading offered another scan and
    the Kin died scanning. A CONFIRMED respawn now puts 'leave' in the offer until the
    first CONFIRMED step that is not one, and the leave is a named hold: the one leg of
    retreat that needs no bearing, because the ground itself is the evidence."""

    mind, _ = mind_with()
    dead = reading(self_state=replace(state(alive=False), respawn_available=True))
    respawn = mind.next_intent(dead)
    assert respawn.skill == "respawn"
    mind.record_result(respawn, outcome(ActionResultClass.CONFIRMED), reading(tick=150))

    leaving = mind.next_intent(reading(tick=160, aim=block_aim()))
    assert leaving.skill == "retreat"
    assert leaving.arguments["hold_seconds"] == RETREAT_FLEE_SECONDS
    assert leaving.plan.calls[0].hold_seconds == RETREAT_FLEE_SECONDS
    assert leaving.reason == "get off the spot the last death happened on"
    mind.record_result(leaving, outcome(ActionResultClass.CONFIRMED), reading(tick=200))

    # The spot has been left: the ordinary order resumes on the next calm reading.
    assert mind.next_intent(reading(tick=210, aim=block_aim())).skill == "break_seen_block"


def test_a_hit_with_a_threat_in_sight_escalates_the_hold() -> None:
    """A rendered threat takes the reading's own bearing; a hit already taken says the
    one-step hold is not enough ground, so the same step walks for the long hold."""

    mind, _ = mind_with()
    mind.observe(reading(self_state=state(health=20.0)))
    hit = reading(tick=200, entities=(slime(),), self_state=state(health=12.0))

    intent = mind.next_intent(hit)

    assert intent.skill == "retreat"
    assert intent.plan.calls[0].hold_seconds == RETREAT_FLEE_SECONDS
    assert intent.reason == "step away from the nearest visible threat"


def test_a_fresh_hit_refunds_the_retreat_step_the_budget_spent() -> None:
    """A reflex is not a step the world refused forever: its precondition is danger, and
    danger arrives as new evidence -- a fresh hit (or a fresh respawn) replenishes it the
    way a newly visible drop replenishes the collect. Without this, run-98's third night
    died four times with `retreat` already excluded and no step left that could answer."""

    mind, _ = mind_with()
    hit = reading(tick=200, entities=(slime(),), self_state=state(health=12.0))
    for tick in (200, 220, 240):
        intent = mind.next_intent(replace(hit, game_tick=tick))
        assert intent.skill == "retreat", tick
        mind.record_result(
            intent,
            outcome(ActionResultClass.UNKNOWN, "RETREAT_NOT_CONFIRMED"),
            replace(hit, game_tick=tick + 5),
        )

    # The budget is spent: re-seeing the same situation no longer offers the step.
    assert "retreat" in mind.excluded
    assert mind.next_intent(replace(hit, game_tick=300)).skill != "retreat"

    # A fresh hit is new evidence, and it refunds the reflex on the spot.
    worse = reading(tick=400, entities=(slime(),), self_state=state(health=6.0))
    assert mind.next_intent(worse).skill == "retreat"
    assert "retreat" not in mind.excluded


def test_a_named_hold_from_the_model_is_honoured() -> None:
    mind, _ = mind_with(
        Decision(
            skill_id="retreat",
            reason="keep moving while it is dark",
            intent_generation=1,
            arguments={"hold_seconds": 3.0},
        )
    )
    intent = mind.next_intent(reading(entities=(slime(),)))

    assert intent.skill == "retreat"
    assert intent.plan.calls[0].hold_seconds == 3.0
    assert intent.arguments["hold_seconds"] == 3.0


def test_the_scan_turns_instead_of_stalling_when_there_is_nothing_to_grasp() -> None:
    mind, _ = mind_with()
    calls = [mind.next_intent(reading()).plan.calls[0] for _ in range(3)]
    yaw_of = [call.yaw_degrees for call in calls]
    pitch_of = [call.pitch_degrees for call in calls]

    assert yaw_of == [SCAN_YAW_STEP_DEGREES, 2 * SCAN_YAW_STEP_DEGREES, 3 * SCAN_YAW_STEP_DEGREES]
    # The pitch steps through a steep-sweep cycle rather than repeating one horizon angle, so
    # a blind scan can eventually look at the block under the player and hand a placement a face.
    assert pitch_of == list(SCAN_PITCH_CYCLE_DEGREES)
    assert any(-90.0 <= p <= 90.0 for p in pitch_of)
    assert max(abs(p) for p in pitch_of) > 45.0


def test_a_full_scan_cycle_covers_all_twenty_four_fifteen_degree_headings() -> None:
    """45° steps alone repeat identically every 24 turns (8 headings x 3 pitches), so a target
    sitting in a gap between headings — a log three blocks out subtends ±9.5°, a gap can be
    22.5° wide — is missed by the same 24-step cycle forever; a live post-respawn run swept 23
    turns of one such cycle without landing on the trunk it was standing in front of. The phase
    drift makes the cycle visit the 45° grid, then both midpoints: all 24 multiples of 15°, each
    exactly once — within half a block at the scan's working distance."""
    mind, _ = mind_with()
    yaws = [mind.next_intent(reading()).plan.calls[0].yaw_degrees % 360.0 for _ in range(24)]

    assert sorted(yaws) == [pytest.approx(15.0 * k % 360.0) for k in range(24)]
    # The drift is what breaks the old resonance: the second circle is not the first again.
    assert set(yaws[:8]).isdisjoint(yaws[8:16])
    assert pytest.approx(0.0) == SCAN_YAW_STEP_DEGREES % SCAN_YAW_DRIFT_DEGREES


def test_a_fresh_projection_names_every_gap_instead_of_filling_it() -> None:
    mind, _ = mind_with()
    document = mind.as_document()

    assert document["direction"] == GOAL.label
    assert document["goal_met"] is False
    assert document["current_intent"] is None
    assert document["executing_skill"] == ""
    assert document["last_result"] == ""
    assert document["failure_attribution"] == ""
    assert document["model_refusal"] == ""
    assert document["model_calls"] == 0
    assert document["model_spent_micro"] == 0
    assert document["excluded_skills"] == []


def test_the_projection_reports_the_result_the_world_gave_and_where_it_came_from() -> None:
    mind, _ = mind_with()
    subject = reading(aim=block_aim())
    intent = mind.next_intent(subject)
    mind.record_result(intent, outcome(ActionResultClass.FAILED, "MINING_STALLED"), subject)

    document = mind.as_document()
    assert document["current_intent"] == intent.as_document()
    assert document["executing_skill"] == "break_seen_block"
    assert document["intent_observation_ref"] == "tick=100;generation=1"
    assert document["last_result"] == ActionResultClass.FAILED.value
    assert document["last_result_reason"] == "MINING_STALLED"
    assert document["failure_attribution"] == "ACTION_NOT_EFFECTIVE"


# --------------------------------------------------------------- #50 resource re-acquisition


def aim_at(block: BlockTargetValue) -> AimTargetValue:
    return AimTargetValue(
        game_tick=100, kind=AimKind.BLOCK, block=block, targeted_block_id=LOG, distance=5.0
    )


#: A log block a few steps north of the default player position (0, 64, 0) — the shape of the
#: trunk a `break_seen_block` was aimed at before a `collect` walked the Kin off it.
NEAR_LOG = BlockTargetValue(x=0, y=64, z=5, face=AimFace.UP)


def reacquire_ladder() -> list[float]:
    """The rungs `_reacquire_probe` computes for NEAR_LOG: its column, one and two cells' worth
    of angle per rung at the five-and-a-half-block distance the reading reports."""

    cell = math.degrees(math.atan2(1.0, math.hypot(0.5, 5.5)))
    return [0.0, cell, -cell, 2.0 * cell, -2.0 * cell]


def test_the_mind_faces_back_to_the_log_block_it_was_breaking() -> None:
    """A collect walks the player off the trunk, the crosshair loses it, and the fallback turns
    back to the cell it was just breaking instead of blind-scanning for it — §5's re-acquisition
    done the way a player recalls a tree, aimed by the same geometry the walk skill uses on a
    visible drop, off only the block the crosshair itself once reported.
    """

    mind, _ = mind_with()
    armed = mind.next_intent(reading(aim=aim_at(NEAR_LOG)))
    assert armed.skill == "break_seen_block"
    assert mind.last_target_block == (0, 64, 5)

    turned = mind.next_intent(reading())
    assert turned.skill == "turn_to"
    assert turned.source == DECISION_FROM_LOCAL
    expected_yaw, _ = angle_to_degrees(dx=0.5, dy=0.5, dz=5.5)
    call = turned.plan.calls[0]
    # The heading is the recalled cell's own bearing; the first probe is the ladder's horizon
    # rung (the sweep no longer aims at the vacated cell's steep angle — a live run showed that
    # angle points at the ground beside a trunk whose members stand above it).
    assert call.yaw_degrees == pytest.approx(expected_yaw)
    assert call.pitch_degrees == pytest.approx(reacquire_ladder()[0])
    # The turn stays inside the client's own units, so it is a legal look and not a clamp.
    assert -180.0 <= call.yaw_degrees <= 180.0
    assert -90.0 <= call.pitch_degrees <= 90.0
    # It is a real re-aim, not the blind sweep's whole-multiple-of-45 heading.
    assert call.yaw_degrees != pytest.approx(SCAN_YAW_STEP_DEGREES)


def test_the_re_aim_sweep_is_bounded_so_a_felled_tree_resumes_scanning() -> None:
    """The re-aim sweeps a bounded set of pitch angles at the recalled heading rather than turning
    once: if none of them lands the crosshair on a block (the trunk is gone), the memory clears and
    the next look falls back to the blind sweep, so a felled tree cannot strand the run re-aiming
    at an empty cell forever.
    """

    mind, _ = mind_with()
    mind.next_intent(reading(aim=aim_at(NEAR_LOG)))
    assert mind.last_target_block == (0, 64, 5)

    # Each empty reading fires exactly one probe of the sweep and leaves the memory armed.
    for _ in range(len(reacquire_ladder())):
        stepped = mind.next_intent(reading())
        assert stepped.skill == "turn_to"
        assert mind.last_target_block == (0, 64, 5)
    assert mind.reaim_probe == len(reacquire_ladder())

    # Offsets spent with nothing seen: the memory clears and the blind sweep (a whole multiple of
    # the scan step) resumes rather than another re-aim at the empty heading.
    after = mind.next_intent(reading())
    assert after.skill == "turn_to"
    assert after.plan.calls[0].yaw_degrees % SCAN_YAW_STEP_DEGREES == pytest.approx(0.0)
    assert mind.last_target_block is None
    assert mind.reaim_probe == 0


def test_the_re_aim_sweep_holds_the_recalled_heading_and_steps_only_the_pitch() -> None:
    """§5's boundary made observable: across the sweep the heading stays the recalled block's own
    bearing (never the blind scan's wandering multiple of 45) while only the pitch steps through the
    fixed offsets. A different pitch is a fresh look along a heading the crosshair already reported,
    not a new cell the mind inferred.
    """

    mind, _ = mind_with()
    mind.next_intent(reading(aim=aim_at(NEAR_LOG)))
    held_yaw, _ = angle_to_degrees(dx=0.5, dy=0.5, dz=5.5)

    seen_pitch: list[float] = []
    for _ in range(len(reacquire_ladder())):
        stepped = mind.next_intent(reading())
        call = stepped.plan.calls[0]
        assert call.yaw_degrees == pytest.approx(held_yaw)
        assert -180.0 <= call.yaw_degrees <= 180.0
        assert -90.0 <= call.pitch_degrees <= 90.0
        seen_pitch.append(call.pitch_degrees)

    # The pitch walks the recalled column's cell offsets at the measured distance while the
    # heading stays pinned to the recalled bearing, so the probes are distinct looks not a re-aim
    # at the vacated cell's steep-down angle.
    assert seen_pitch == pytest.approx(reacquire_ladder())
    assert len(set(seen_pitch)) == len(reacquire_ladder())


def test_a_re_aim_is_refused_when_the_bag_owes_a_grid_not_a_resource() -> None:
    """The gate is the specific 'go back to the raw item' precondition, not any hold. A bag that
    has the material but no table owes a screen the re-aim cannot fix, so it must not steer the
    Kin back to a log it no longer needs — and a refusal leaves the memory intact.
    """

    mind, _ = mind_with()
    mind.last_target_block = (0, 64, 5)
    paid_but_small_grid = reading(items=((0, PLANKS, 3), (1, STICK, 2), (2, TABLE, 1)))
    assert blocker_for(paid_but_small_grid, PICKAXE) == CRAFT_GRID_TOO_SMALL
    reached = mind.next_intent(paid_but_small_grid)
    # A bag that already has the material but owes a 3-by-3 grid reaches for the table it holds, not
    # back to a log it no longer needs — and the re-aim memory survives, which a fired re-aim would
    # have cleared. So the grid debt never steers the Kin to the resource cell.
    assert reached.skill != "turn_to"
    assert mind.last_target_block == (0, 64, 5)


def test_a_re_aim_is_refused_with_no_standing_goal_or_no_position() -> None:
    """Both halves of the geometry must actually be present: a Kin with no standing milestone has
    no resource to return to, and a reading that never reported a position has no offset to aim
    from. Neither is a gamble — each falls back to the blind sweep.
    """

    mindless = mind_for(ScriptedProvider(), CostLedger(run_cost_cap=CAP), goal=None)
    mindless.last_target_block = (0, 64, 5)
    turned = mindless.next_intent(reading())
    # With no standing milestone there is no raw material to return to, so the fallback blind-scans
    # and the memory survives — the same observable proof of a refusal used above.
    assert turned.skill == "turn_to"
    assert turned.plan.calls[0].yaw_degrees % SCAN_YAW_STEP_DEGREES == pytest.approx(0.0)
    assert mindless.last_target_block == (0, 64, 5)

    located = mind_for(ScriptedProvider(), CostLedger(run_cost_cap=CAP), goal=GOAL)
    located.last_target_block = (0, 64, 5)
    no_position = reading(
        self_state=SelfStateValue(
            health=20.0,
            max_health=20.0,
            food=20,
            saturation=5.0,
            alive=True,
            x=None,
            y=None,
            z=None,
        )
    )
    turned = located.next_intent(no_position)
    # A reading that never reported a position has no offset to aim from, so even with the goal and
    # the memory present the turn falls back to the blind sweep rather than a doomed re-aim.
    assert turned.skill == "turn_to"
    assert turned.plan.calls[0].yaw_degrees % SCAN_YAW_STEP_DEGREES == pytest.approx(0.0)
    assert located.last_target_block == (0, 64, 5)


def test_the_re_aim_landing_on_a_block_re_arms_breaking_so_more_than_one_log_is_reachable() -> None:
    """The whole point of the re-aim is a gather that continues: after the look turns back and a
    later reading puts a block under the crosshair again, a break is offered and re-arms the
    memory with that cell, so the Kin can fell a second log rather than stalling on the first.
    This walks the handoff across three readings — arm, blind-turn-with-nothing-in-view, re-face —
    so the memory re-arms for a second log, which the single-refusal cells above do not exercise.
    """

    mind, _ = mind_with()
    mind.next_intent(reading(aim=aim_at(NEAR_LOG)))
    assert mind.last_target_block == (0, 64, 5)

    turned = mind.next_intent(reading())
    assert turned.skill == "turn_to"
    # The first probe of the sweep keeps the memory armed — a single empty look is not yet proof
    # the trunk is gone.
    assert mind.last_target_block == (0, 64, 5)
    assert mind.reaim_probe == 1

    # The turn put the next block of the same trunk under the crosshair (a different face).
    refaced = mind.next_intent(
        reading(tick=120, aim=aim_at(BlockTargetValue(x=0, y=64, z=5, face=AimFace.NORTH)))
    )
    assert refaced.skill == "break_seen_block"
    assert mind.last_target_block == (0, 64, 5)


def test_collect_fallback_uses_a_visible_item_when_goal_resource_is_not_in_view() -> None:
    mind, _ = mind_with()
    observed = reading(entities=(drop("minecraft:dirt"),))
    intent = mind.next_intent(observed)
    assert intent.skill == "collect_dropped"
    assert intent.plan.calls[0].item_id == "minecraft:dirt"
    assert intent.arguments["item_id"] == "minecraft:dirt"


def test_collect_fallback_prefers_the_goal_resource_when_it_is_visible() -> None:
    mind, _ = mind_with()
    observed = reading(entities=(drop("minecraft:dirt", at=0.5), drop(LOG, at=2.0)))
    intent = mind.next_intent(observed)
    assert intent.skill == "collect_dropped"
    assert intent.plan.calls[0].item_id == LOG


def test_local_gather_does_not_break_a_visible_block_unrelated_to_the_goal_resource() -> None:
    mind, _ = mind_with()
    observed = reading(aim=replace(block_aim(), targeted_block_id="minecraft:dirt"))
    # The generic break remains available to a model for a reasoned goal, but a
    # local gather must not invent oak drops from the ground under the crosshair.
    assert "break_seen_block" in feasible_skill_ids(GOAL, observed)
    assert mind.next_intent(observed).skill == "turn_to"


def test_local_setup_gathers_remaining_materials_before_standing_up_the_grid_enabler() -> None:
    mind, _ = mind_with()
    observed = reading(
        items=((0, PLANKS, 2), (1, STICK, 4), (6, TABLE, 1)),
        self_state=replace(state(selected_slot=6), main_hand_item_id=TABLE),
        aim=block_aim(),
    )
    assert blocker_for(observed, PICKAXE) == CRAFT_MATERIALS_MISSING
    assert mind.next_intent(observed).skill == "break_seen_block"


def test_local_setup_leaves_an_unselected_table_in_the_bag_until_the_debt_is_paid() -> None:
    """The local fallback stood the enabler up the moment it was crafted: select -> place -> open
    while the pickaxe was still one plank short (live run a7c2ffd4, steps 15-17). The window was
    then closed for gathering — world actions need it gone — and the next wide craft re-crafted a
    second table, because a placed table cannot be reselected; the run ended one plank short of
    the tool. The enabler goes to hand only once the remaining material debt is paid — the same
    CRAFT_GRID_TOO_SMALL gate the use key already waits for, and the sentence `_reflect`'s own
    docstring already promised. Once the debt is paid, selecting is the right move again, which
    the second half pins."""

    mind, _ = mind_with()
    observed = reading(
        items=((0, PLANKS, 2), (1, STICK, 4), (6, TABLE, 1)),
        self_state=state(selected_slot=0),
        aim=aim_at(NEAR_LOG),
    )
    assert blocker_for(observed, PICKAXE) == CRAFT_MATERIALS_MISSING

    intent = mind.next_intent(observed)

    assert intent.skill != "select_hotbar"
    assert intent.skill == "break_seen_block"

    paid = reading(
        items=((0, PLANKS, 3), (1, STICK, 2), (6, TABLE, 1)),
        self_state=state(selected_slot=0),
        aim=aim_at(NEAR_LOG),
    )
    assert blocker_for(paid, PICKAXE) == CRAFT_GRID_TOO_SMALL
    assert mind.next_intent(paid).skill == "select_hotbar"


def test_reacquisition_sweeps_the_recalled_columns_cell_offsets() -> None:
    mind, _ = mind_with()
    mind.next_intent(reading(aim=aim_at(NEAR_LOG)))
    pitches: list[float] = []
    while True:
        intent = mind.next_intent(reading())
        if mind.last_target_block is None:
            # This call was the one that exhausted the ladder: its turn is the blind scan's,
            # not a rung.
            break
        pitches.append(intent.plan.calls[0].pitch_degrees)
    # One rung per cell of the recalled column at the measured distance, then the memory clears:
    # the ladder covers the block standing above or below the vacated cell — which the old fixed
    # ladder could not at three blocks, turning away from a trunk with a usable log still in it.
    assert pitches == pytest.approx(reacquire_ladder())
    # Only a subsequent client reading, not the sweep, can make the overhead
    # block a mine target. The successful sighting re-arms the normal break.
    observed = mind.next_intent(
        reading(
            aim=aim_at(
                BlockTargetValue(
                    x=0,
                    y=67,
                    z=5,
                    face=AimFace.DOWN,
                )
            )
        )
    )
    assert observed.skill == "break_seen_block"
    assert mind.last_target_block == (0, 67, 5)


def test_local_mind_uses_the_open_wider_grid_before_closing_it() -> None:
    mind, _ = mind_with()
    selected = reading(
        items=((0, PLANKS, 3), (1, STICK, 2), (6, TABLE, 1)),
        self_state=replace(state(selected_slot=6), main_hand_item_id=TABLE),
        aim=block_aim(),
    )
    opening = mind.next_intent(selected)
    assert opening.skill == "use_target"
    opened = reading(
        tick=110,
        items=((0, PLANKS, 3), (1, STICK, 2)),
        gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=1),
    )
    mind.record_result(
        opening,
        SkillOutcome(
            result=ActionResultClass.CONFIRMED,
            reason="",
            action_id="open-1",
            pre_tick=100,
            post_tick=110,
        ),
        opened,
    )
    crafting = mind.next_intent(opened)
    assert crafting.skill == "craft_take_result"
    assert crafting.plan.calls[0].product_id == PICKAXE
    finished = reading(
        tick=120,
        items=((0, PICKAXE, 1),),
        gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=1),
    )
    mind.record_result(
        crafting,
        SkillOutcome(
            result=ActionResultClass.CONFIRMED,
            reason="",
            action_id="craft-1",
            pre_tick=110,
            post_tick=120,
        ),
        finished,
    )
    assert mind.next_intent(finished).skill == "close_screen"


def test_model_summary_carries_body_angles_screen_and_catalog_material_debt() -> None:
    provider = ScriptedProvider()
    mind = mind_for(provider, CostLedger(run_cost_cap=CAP), goal=GOAL)
    subject = reading(items=((0, LOG, 1),))
    mind.next_intent(subject)
    summary = provider.requests[0].observation_summary
    assert summary["yaw_degrees"] == subject.self_state.yaw_degrees
    assert summary["pitch_degrees"] == subject.self_state.pitch_degrees
    assert summary["screen_open"] is False
    assert summary["craft_plan_source"] == "curated_catalog"
    assert summary["craft_plan"]


def test_empty_container_cycle_requires_material_or_target_change_before_reopening() -> None:
    mind, _ = mind_with(
        Decision(skill_id="use_target", reason="open", intent_generation=1),
        Decision(skill_id="close_screen", reason="no materials", intent_generation=2),
        Decision(skill_id="use_target", reason="open again", intent_generation=3),
        Decision(skill_id="use_target", reason="materials changed", intent_generation=4),
    )
    provider = cast(ScriptedProvider, mind.provider)
    before = reading(aim=block_aim())
    opened = reading(
        tick=120, aim=block_aim(), gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=1)
    )
    first = mind.next_intent(before)
    mind.record_result(first, outcome(ActionResultClass.CONFIRMED), opened)
    close = mind.next_intent(opened)
    closed = reading(tick=140, aim=block_aim())
    mind.record_result(close, outcome(ActionResultClass.CONFIRMED), closed)
    rerouted = mind.next_intent(closed)
    assert "use_target" not in provider.requests[-1].feasible_skill_ids
    assert rerouted.skill != "use_target"
    changed = reading(tick=160, aim=block_aim(), items=((0, LOG, 1),))
    assert mind.next_intent(changed).skill == "use_target"


def test_dead_player_stops_before_model_call_or_screen_action() -> None:
    provider = ScriptedProvider()
    mind = mind_for(provider, CostLedger(run_cost_cap=CAP), goal=GOAL)
    dead = reading(
        self_state=state(health=0.0, alive=False), gui=GuiScreenValue(screen_id="", sync_id=0)
    )
    intent = mind.next_intent(dead)
    assert intent.kind is MindDecisionKind.HOLD
    assert intent.reason == "PLAYER_DEAD"
    assert provider.requests == []
    assert intent.plan.calls == ()


def test_model_recent_result_names_executed_prerequisite_and_inventory_change() -> None:
    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="toward goal",
            intent_generation=1,
            arguments={"target_item": PICKAXE, "quantity": 1},
        ),
    )
    before = reading(items=((0, LOG, 1),))
    intent = mind.next_intent(before)
    assert intent.plan.calls[0].product_id == PLANKS
    after = reading(tick=120, items=((0, PLANKS, 4),))
    mind.record_result(intent, outcome(ActionResultClass.CONFIRMED), after)
    mind.next_intent(after)
    provider = cast(ScriptedProvider, mind.provider)
    recent = cast(
        list[dict[str, object]], provider.requests[-1].observation_summary["recent_actions"]
    )
    result = recent[-1]
    assert cast(dict[str, object], result["arguments"])["target_item"] == PICKAXE
    assert result["executed_product_id"] == PLANKS
    assert result["inventory_after"] == {PLANKS: 4}


def test_search_hint_uses_observed_cell_bearing_without_claiming_remaining_blocks() -> None:
    mind, _ = mind_with()
    provider = cast(ScriptedProvider, mind.provider)
    mind.next_intent(reading())
    initial = cast(dict[str, object], provider.requests[-1].observation_summary["view_search"])
    assert initial["source"] == "body_angles"
    observed = reading(aim=block_aim())
    assert mind.next_intent(observed).skill == "break_seen_block"
    remembered = mind.last_target_block
    assert remembered is not None
    subject = reading()
    mind.next_intent(subject)
    hint = cast(dict[str, object], provider.requests[-1].observation_summary["view_search"])
    assert hint["source"] == "previously_seen_crosshair_cell"
    assert hint["target_presence"] == "unconfirmed"
    x, y, z = remembered
    body = subject.self_state
    assert body.x is not None and body.y is not None and body.z is not None
    cell = math.degrees(math.atan2(1.0, max(math.hypot(x + 0.5 - body.x, z + 0.5 - body.z), 0.5)))
    assert hint["pitch_candidates_degrees"] == pytest.approx(
        [0.0, cell, -cell, 2.0 * cell, -2.0 * cell]
    )
    expected, _ = angle_to_degrees(dx=x + 0.5 - body.x, dy=y + 0.5 - body.y, dz=z + 0.5 - body.z)
    assert hint["suggested_yaw_degrees"] == pytest.approx(expected)
    assert mind.last_target_block == remembered


def test_new_visible_drop_restores_collect_after_old_target_retry_exhaustion() -> None:
    mind, _ = mind_with()
    first = reading(entities=(drop(),))
    failed = outcome(ActionResultClass.UNKNOWN, "COLLECT_APPROACH_STALLED")
    for _ in range(RETRY_BUDGET_PER_SIGNATURE + 1):
        intent = mind.next_intent(first)
        assert intent.skill == "collect_dropped"
        mind.record_result(intent, failed, first)
    assert mind.next_intent(first).skill != "collect_dropped"
    # A changed relative offset of the same entity does not buy more retries.
    moved = reading(entities=(replace(drop(), relative_x=2.0),))
    assert mind.next_intent(moved).skill != "collect_dropped"
    # A newly observed entity is a different approach, rather than an immortal skill ban.
    fresh = reading(entities=(replace(drop(), observation_id="fresh-drop"),))
    assert mind.next_intent(fresh).skill == "collect_dropped"
    assert "collect_dropped" not in mind.excluded
    assert not any(skill == "collect_dropped" for skill, _ in mind.attempts)


def test_reseeing_old_drop_does_not_replenish_exhausted_collect_budget() -> None:
    mind, _ = mind_with()
    old = reading(entities=(drop(),))
    mind.next_intent(old)
    fresh = reading(entities=(replace(drop(), observation_id="fresh-drop"),))
    failed = outcome(ActionResultClass.UNKNOWN, "COLLECT_APPROACH_STALLED")
    for _ in range(RETRY_BUDGET_PER_SIGNATURE + 1):
        intent = mind.next_intent(fresh)
        mind.record_result(intent, failed, fresh)
    assert mind.next_intent(reading()).skill != "collect_dropped"
    assert mind.next_intent(old).skill != "collect_dropped"


def test_selected_goal_item_does_not_finish_an_unmet_quantity() -> None:
    mind, _ = mind_with(goal=PLANK_GOAL)
    subject = reading(items=((0, PLANKS, 4),), self_state=state(selected_slot=0))
    assert not mind.holds_goal(subject)
    assert mind.next_intent(subject).reason != GOAL_ACHIEVED


def test_goal_quantity_can_span_stacks_with_a_later_matching_stack_selected() -> None:
    mind, _ = mind_with(goal=PLANK_GOAL)
    subject = reading(items=((0, PLANKS, 4), (1, PLANKS, 4)), self_state=state(selected_slot=1))
    assert mind.holds_goal(subject)
    assert mind.next_intent(subject).reason == GOAL_ACHIEVED


def test_partial_goal_output_does_not_displace_missing_materials_with_selection() -> None:
    subject = reading(items=((3, PLANKS, 4),), self_state=state(selected_slot=0))
    assert select_target(PLANK_GOAL, subject) is None
    assert "select_hotbar" not in feasible_skill_ids(PLANK_GOAL, subject)


@pytest.mark.parametrize("target,quantity", [(PLANKS, 4), (STICK, 4)])
def test_a_satisfied_model_subgoal_continues_the_outstanding_milestone(
    target: str,
    quantity: int,
) -> None:
    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="finish this subgoal",
            intent_generation=1,
            arguments={"target_item": target, "quantity": quantity},
        ),
        goal=PLANK_GOAL,
    )
    subject = reading(items=((0, PLANKS, 4), (1, LOG, 1), (2, STICK, 4)))
    intent = mind.next_intent(subject)
    assert intent.kind is MindDecisionKind.INTENT
    assert intent.skill == "craft_take_result"
    assert intent.plan.calls[0].product_id == PLANKS
    assert intent.arguments == {"target_item": PLANKS, "quantity": 8}
    assert intent.source == DECISION_FROM_LOCAL
    assert intent.model_refusal == "REQUEST_ALREADY_SATISFIED"
    assert not mind.goal_met


def test_a_satisfied_request_without_a_goal_does_not_claim_goal_success() -> None:
    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="make four",
            intent_generation=1,
            arguments={"target_item": PLANKS, "quantity": 4},
        ),
        goal=None,
    )
    intent = mind.next_intent(reading(items=((0, PLANKS, 4), (1, LOG, 1))))
    assert intent.reason == "REQUEST_ALREADY_SATISFIED"
    assert not mind.goal_met


def test_an_unpayable_goal_craft_reroutes_to_search_instead_of_retrying_craft() -> None:
    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="make eight",
            intent_generation=1,
            arguments={"target_item": PLANKS, "quantity": 8},
        ),
        goal=PLANK_GOAL,
    )
    intent = mind.next_intent(reading(items=((0, PLANKS, 4),)))
    assert intent.kind is MindDecisionKind.INTENT
    assert intent.skill == "turn_to"
    assert intent.source == DECISION_FROM_LOCAL
    assert intent.model_refusal == CRAFT_MATERIALS_MISSING
    assert not mind.goal_met


def test_model_timeout_with_partial_output_still_searches_for_missing_materials() -> None:
    mind, _ = mind_with(ModelUnavailable(UnavailableReason.TIMEOUT), goal=PLANK_GOAL)
    intent = mind.next_intent(reading(items=((0, PLANKS, 4),)))
    assert intent.kind is MindDecisionKind.INTENT
    assert intent.skill == "turn_to"
    assert intent.source == DECISION_FROM_LOCAL
    assert intent.model_refusal == UnavailableReason.TIMEOUT.value
    assert mind.last_precondition == CRAFT_MATERIALS_MISSING


# ------------------------------------------------------------------------------- the meal


def clear_aim() -> AimTargetValue:
    return AimTargetValue(game_tick=100, kind=AimKind.MISS)


def meal_reading(
    *,
    food: int = 4,
    slot: int = 3,
    item: str = "minecraft:apple",
    count: int = 2,
) -> WorldObservationValue:
    return reading(
        aim=clear_aim(),
        items=((slot, item, count),),
        self_state=state(food=food),
    )


def test_a_hungry_reading_offers_a_meal_only_inside_its_preconditions() -> None:
    assert "consume_item" in feasible_skill_ids(None, meal_reading())
    # A full bar is the one state where a meal changes nothing the verdict reads.
    assert "consume_item" not in feasible_skill_ids(None, meal_reading(food=20))
    # A crosshair on a block: the use key would fire there first.
    assert "consume_item" not in feasible_skill_ids(
        None,
        reading(
            aim=block_aim(),
            items=((3, "minecraft:apple", 2),),
            self_state=state(food=8),
        ),
    )
    # In the bag proper: no number key reaches it.
    assert "consume_item" not in feasible_skill_ids(
        None,
        reading(aim=clear_aim(), items=((12, "minecraft:apple", 2),), self_state=state(food=8)),
    )
    # Not a curated food.
    assert "consume_item" not in feasible_skill_ids(
        None,
        reading(aim=clear_aim(), items=((3, "minecraft:stone", 2),), self_state=state(food=8)),
    )


def test_the_local_reflection_eats_before_it_works_when_the_bar_is_low() -> None:
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(OffModelProvider(), ledger, goal=None)

    intent = mind.next_intent(meal_reading(food=4))
    assert intent.kind is MindDecisionKind.INTENT
    assert intent.skill == "consume_item"
    assert intent.source == DECISION_FROM_LOCAL
    assert [call.name for call in intent.plan.calls] == ["consume_item"]
    assert intent.plan.calls[0].item_id == "minecraft:apple"
    assert intent.arguments == {"target_item": "minecraft:apple"}

    # With the bar fine nothing is asking for care, so the local layer does not
    # spend a step on a meal and looks around instead.
    assert mind.next_intent(meal_reading(food=14)).skill == "turn_to"


def test_a_model_meal_the_precondition_refuses_reroutes_to_a_real_candidate() -> None:
    mind, _ = mind_with(
        Decision(
            skill_id="consume_item",
            reason="eat the rock",
            intent_generation=1,
            arguments={"target_item": "minecraft:stone"},
        ),
        goal=None,
    )
    pre = reading(
        aim=clear_aim(),
        items=((3, "minecraft:stone", 1), (4, "minecraft:apple", 2)),
        self_state=state(food=4),
    )

    intent = mind.next_intent(pre)

    assert intent.kind is MindDecisionKind.INTENT
    assert intent.skill == "consume_item"
    assert intent.source == DECISION_FROM_LOCAL
    assert intent.model_refusal == "CONSUME_ITEM_NOT_KNOWN_FOOD"
    assert intent.arguments == {"target_item": "minecraft:apple"}
    assert mind.last_precondition == "CONSUME_ITEM_NOT_KNOWN_FOOD"


def test_a_consume_refusal_costs_no_budget_and_keeps_the_skill_available() -> None:
    mind, _ = mind_with(goal=None)
    pre = meal_reading(food=4)
    intent = mind.next_intent(pre)
    assert intent.skill == "consume_item"

    failure = mind.record_result(
        intent, outcome(ActionResultClass.FAILED, "CONSUME_ITEM_MISSING"), pre
    )

    assert failure is FailureCode.RESOURCE_UNAVAILABLE
    assert mind.last_precondition == "CONSUME_ITEM_MISSING"
    assert "consume_item" not in mind.excluded
    assert "consume_item" in feasible_skill_ids(None, pre)
    assert mind.attempts == {}


def test_the_summary_lists_only_meals_the_hotbar_can_reach() -> None:
    """`consumable_items` is the actionable view, not a bag census: a food only the
    wider bag holds would be a name the model could pick and the skill refuse."""

    pre = reading(
        aim=clear_aim(),
        items=((12, "minecraft:apple", 2), (2, "minecraft:bread", 1)),
        self_state=state(food=14),
    )

    summary = observation_summary(None, pre)

    assert summary["consumable_items"] == ["minecraft:bread"]
