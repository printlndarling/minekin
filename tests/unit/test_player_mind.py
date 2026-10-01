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
    RETRY_BUDGET_PER_SIGNATURE,
    SCAN_YAW_STEP_DEGREES,
    FailureCode,
    MindDecisionKind,
    PlayerMind,
    attribute_failure,
    craft_blocker,
    craft_options,
    feasible_skill_ids,
    mind_for,
    needs_from,
    next_craft,
    screen_open,
    shortfalls,
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
from minekin_core.domain.world_actions import ActionResultClass, SkillOutcome, skill_capabilities

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
    assert (
        craft_blocker(GOAL, reading(items=((0, PLANKS, 3), (1, STICK, 2)))) == CRAFT_GRID_TOO_SMALL
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


# --------------------------------------------------------------- the standing container


def test_an_open_container_narrows_the_offer_to_leaving_it() -> None:
    """A reading that would otherwise offer the break, the collect and the craft offers only the
    exit — the world actions it displaces are exactly the ones that, sent while the window holds
    the input, become the `GUI_CONFLICT` the run reads back as a silent stream. The narrowing is
    the whole fix: it is what lets the Kin leave the screen before it tries to act on the world,
    rather than hardcoding a close onto the tail of the craft."""

    crowded = reading(
        aim=block_aim(),
        items=((0, PLANKS, 5),),
        entities=(drop(),),
        gui=GuiScreenValue(screen_id="", sync_id=7),
    )

    assert feasible_skill_ids(GOAL, crowded) == (CLOSE_SCREEN,)


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


def test_an_ask_the_bag_cannot_pay_for_holds_the_materials_word() -> None:
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

    assert intent.kind is MindDecisionKind.HOLD
    assert intent.reason == CRAFT_MATERIALS_MISSING


def test_an_ask_for_a_shape_the_open_grid_cannot_hold_holds_the_grid_word() -> None:
    """A bag that has already paid for the whole chain but the tool: the only step owed is the
    three-by-three, and the screen this build opens is two-by-two. Nothing is clicked, and the
    word is the one no later reading can undo — which the reroute table acts on downstream."""

    mind, _ = mind_with(
        Decision(
            skill_id="craft_take_result",
            reason="make the pickaxe",
            intent_generation=1,
            arguments={"target_item": PICKAXE, "quantity": 1},
        )
    )

    intent = mind.next_intent(reading(items=((0, PLANKS, 5), (1, STICK, 2))))

    assert intent.kind is MindDecisionKind.HOLD
    assert intent.reason == CRAFT_GRID_TOO_SMALL


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
    assert mind.next_intent(hurt).skill == "turn_to"
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

    for _ in range(RETRY_BUDGET_PER_SIGNATURE + 1):
        intent = mind.next_intent(subject)
        mind.record_result(intent, failing, subject)
    # `turn_to` is always offered, so the run keeps a way to look; the blocked shape only
    # arrives once even that has spent its budget.
    for _ in range(RETRY_BUDGET_PER_SIGNATURE + 1):
        intent = mind.next_intent(subject)
        mind.record_result(intent, failing, subject)

    assert set(mind.excluded) == {"break_seen_block", "turn_to"}
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


def test_the_scan_turns_instead_of_stalling_when_there_is_nothing_to_grasp() -> None:
    mind, _ = mind_with()
    yaw_of = [mind.next_intent(reading()).plan.calls[0].yaw_degrees for _ in range(3)]

    assert yaw_of == [SCAN_YAW_STEP_DEGREES, 2 * SCAN_YAW_STEP_DEGREES, 3 * SCAN_YAW_STEP_DEGREES]


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
