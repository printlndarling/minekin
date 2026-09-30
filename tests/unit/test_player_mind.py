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

import pytest

from minekin_core.adapters.model import OffModelProvider
from minekin_core.application.player_mind import (
    CRAFT_MATERIALS_MISSING,
    DECISION_FROM_LOCAL,
    DECISION_FROM_MODEL,
    GOAL_ACHIEVED,
    GOAL_BUILD_PLAN,
    LONG_TERM_DIRECTION,
    NO_FEASIBLE_SKILL,
    NO_LATEST_OBSERVATION,
    RETRY_BUDGET_PER_SIGNATURE,
    SCAN_YAW_STEP_DEGREES,
    FailureCode,
    MindDecisionKind,
    PlayerMind,
    attribute_failure,
    craft_blocker,
    feasible_skill_ids,
    mind_for,
    needs_from,
    next_craft,
    shortfalls,
)
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
    InventoryStackValue,
    InventoryValue,
    SelfStateValue,
    WorldObservationValue,
)
from minekin_core.domain.recipe_catalog import (
    CRAFT_GRID_TOO_SMALL,
    CRAFT_RECIPE_UNAVAILABLE,
    PLAYER_GRID_SIDE,
)
from minekin_core.domain.world_actions import ActionResultClass, SkillOutcome, skill_capabilities

LOG = "minecraft:oak_log"
PLANKS = "minecraft:oak_planks"
STICK = "minecraft:stick"
PICKAXE = "minecraft:wooden_pickaxe"
CAP = 1_000_000


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
) -> WorldObservationValue:
    return WorldObservationValue(
        generation=1,
        game_tick=tick,
        self_state=self_state if self_state is not None else state(),
        aim=aim,
        inventory=bag(*items),
        visible_entities=entities,
        mining=None,
        gui=None,
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


def mind_with(*answers: Decision | ModelUnavailable) -> tuple[PlayerMind, CostLedger]:
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(ScriptedProvider(*answers), ledger, kin_id="kin-01", persona_seed="seed-9")
    return mind, ledger


def outcome(result: ActionResultClass, reason: str = "") -> SkillOutcome:
    return SkillOutcome(result=result, reason=reason, action_id="a-1")


# --------------------------------------------------------------------------- the feasible set


def test_a_log_block_in_view_offers_the_mine_and_a_look() -> None:
    assert set(feasible_skill_ids(reading(aim=block_aim()))) == {"break_seen_block", "turn_to"}


def test_nothing_in_view_offers_only_the_conservative_look() -> None:
    assert feasible_skill_ids(reading()) == ("turn_to",)


def test_a_seen_drop_offers_collecting_and_another_items_does_not() -> None:
    assert "collect_dropped" in feasible_skill_ids(reading(entities=(drop(),)))
    assert "collect_dropped" not in feasible_skill_ids(reading(entities=(drop("minecraft:coal"),)))


def test_a_craft_is_offered_only_when_the_bag_can_already_pay_for_it() -> None:
    one_log = reading(items=((0, LOG, 1),))
    stage = next_craft(one_log)
    assert stage is not None
    assert stage.product_id == PLANKS
    assert "craft_take_result" in feasible_skill_ids(one_log)


def test_no_craft_is_offered_when_every_stage_is_short_of_materials() -> None:
    assert next_craft(reading()) is None
    assert "craft_take_result" not in feasible_skill_ids(reading())


def test_the_plan_is_walked_in_build_order() -> None:
    # Three planks pay for the sticks the pickaxe needs, and for none more planks: the log the
    # first step would cost is not in the bag, so the next step the reading supports is sticks.
    assert next_craft(reading(items=((0, PLANKS, 3),))) == GOAL_BUILD_PLAN[1]
    assert next_craft(reading(items=((0, PICKAXE, 1),))) is None


def test_a_stage_the_open_grid_cannot_hold_is_never_offered_as_a_craft() -> None:
    """The pickaxe is a three-by-three shape and the only screen the craft skill opens is the
    inventory's two-by-two. Offering it anyway was a command the world could only shrug at;
    the reading that pays for it is now the reading that says it cannot run."""

    paid = reading(items=((0, PLANKS, 3), (1, STICK, 2)))

    assert next_craft(paid) is None
    assert next_craft(paid, grid_side=3) == GOAL_BUILD_PLAN[2]
    assert "craft_take_result" not in feasible_skill_ids(paid)


def test_the_blocked_craft_names_the_precondition_that_is_true_of_the_reading() -> None:
    assert craft_blocker(reading(items=((0, LOG, 1),))) == ""
    assert craft_blocker(reading()) == CRAFT_MATERIALS_MISSING
    assert craft_blocker(reading(items=((0, PLANKS, 3), (1, STICK, 2)))) == CRAFT_GRID_TOO_SMALL
    # The whole job already in the bag, in whatever shape the crafts left it: nothing is owed,
    # so no precondition is being asked about. The planks that went into the tool are not
    # counted against it — that is the difference between a plan netted off a reading and a
    # shopping list, and the reason a finished run can stop instead of gathering again.
    assert craft_blocker(reading(items=((0, PLANKS, 3), (1, STICK, 2), (2, PICKAXE, 1)))) == ""
    assert craft_blocker(reading(items=((0, PICKAXE, 1),))) == ""


def test_a_milestone_closed_from_a_reading_asks_for_no_craft() -> None:
    """One pickaxe, with nothing left of the planks that made it: the goal product is held, so
    the plan owes nothing, so there is no craft to offer and nothing to be blocked about. This
    is §4 closing a direction on the world's word, reached through the recipe table rather
    than through a fixture that listed the intermediates as things to keep holding."""

    finished = reading(items=((0, PICKAXE, 1),))

    assert shortfalls(finished) == ()
    assert next_craft(finished) is None
    assert "craft_take_result" not in feasible_skill_ids(finished)


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

    assert [step.recipe.recipe_id for step in GOAL_BUILD_PLAN] == [PLANKS, STICK, PICKAXE]
    assert [step.required_total for step in GOAL_BUILD_PLAN] == [5, 2, 1]
    assert GOAL_BUILD_PLAN[2].recipe.grid_width == 3
    assert not GOAL_BUILD_PLAN[2].recipe.fits(PLAYER_GRID_SIDE)


def test_a_bag_partway_through_the_plan_is_credited_rather_than_asked_to_start_again() -> None:
    """Five planks is the whole job's worth of planks, so the only steps still owed are the
    sticks and the tool — and the craft the reading supports is the stick one, which is what
    those five planks were for."""

    halfway = reading(items=((0, PLANKS, 5),))

    owed = shortfalls(halfway)
    assert not isinstance(owed, str)
    assert [(step.product_id, step.required_total) for step in owed] == [(STICK, 2), (PICKAXE, 1)]
    assert next_craft(halfway) == owed[0]


def test_an_aiming_that_is_a_miss_does_not_offer_a_mine() -> None:
    miss = AimTargetValue(game_tick=100, kind=AimKind.MISS)
    assert "break_seen_block" not in feasible_skill_ids(reading(aim=miss))


# --------------------------------------------------------------------------------- the needs


def test_resource_security_reads_the_milestone_not_the_wood() -> None:
    assert needs_from(reading())["resource_security"] == 9
    with_wood = reading(items=((0, PLANKS, 3),))
    assert needs_from(with_wood)["resource_security"] == 5
    assert needs_from(reading(items=((0, PICKAXE, 1),)))["resource_security"] == 1


def test_safety_reads_the_health_and_food_it_was_given() -> None:
    assert needs_from(reading())["safety"] == 1
    assert needs_from(reading(self_state=state(health=8.0)))["safety"] == 7
    assert needs_from(reading(self_state=state(food=2)))["safety"] == 7
    assert needs_from(reading(self_state=state(health=0.0, alive=False)))["safety"] == 9


# -------------------------------------------------------------------------- the ask it builds


def test_the_ask_carries_only_what_the_local_layer_computed() -> None:
    provider = ScriptedProvider()
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(provider, ledger, kin_id="kin-01", persona_seed="seed-9")
    subject = reading(aim=block_aim(), items=((0, LOG, 1),))
    mind.next_intent(subject)

    request = provider.requests[0]
    assert request.observation_ref == "tick=100;generation=1"
    assert request.active_goal == LONG_TERM_DIRECTION
    assert set(request.feasible_skill_ids) == {
        "break_seen_block",
        "craft_take_result",
        "turn_to",
    }
    assert request.needs == needs_from(subject)
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


# ------------------------------------------------------------- refusals take the local path


def test_the_off_provider_leaves_a_named_refusal_and_a_local_choice() -> None:
    ledger = CostLedger(run_cost_cap=CAP)
    mind = mind_for(OffModelProvider(), ledger, model_enabled=False)
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
    mind = mind_for(OffModelProvider(), ledger)

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
    assert mind.direction == LONG_TERM_DIRECTION
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

    assert document["direction"] == LONG_TERM_DIRECTION
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
