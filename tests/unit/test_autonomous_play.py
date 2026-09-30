"""The loop plays one intent per reading, and stops for a reason the projection can name.

`test_player_mind.py` judges what the mind asks and `test_skill_plan.py` judges how a step is
run. What is under test here is the turn between them: that a run asks once, acts once, then
reads again; that the milestone chain is walked *by the loop* rather than by a plan someone
wrote; that a decision claiming the goal did not finish anything; and that every way the loop
can end arrives as a word rather than as silence or a stack trace. The chain test runs against
the shipped `off` provider, because that is the shape a machine without model credentials can
actually demonstrate.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import cast

from google.protobuf.message import Message

from minekin_core.adapters.model import OffModelProvider
from minekin_core.application.autonomous_play import (
    CONTROL_CHANNEL_LOST,
    DEFAULT_STEP_BUDGET,
    GOAL_HELD_IN_HAND,
    NO_FRESH_OBSERVATION,
    STEP_BUDGET_SPENT,
    AutonomousAsk,
    AutonomousRun,
    run_autonomous_loop,
)
from minekin_core.application.player_mind import (
    CRAFT_MATERIALS_MISSING,
    GOAL_ACHIEVED,
    NO_LATEST_OBSERVATION,
    SKILL_OFFER,
    PlayerMind,
    mind_for,
)
from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.application.world_skills import (
    DEFAULT_STEP_TIMEOUT_NS,
    ActionAuthority,
    WorldSkills,
)
from minekin_core.domain.control_vocabulary import (
    AIM_CAPABILITY,
    GUI_CAPABILITY,
    HOTBAR_CAPABILITY,
    MINE_CAPABILITY,
    MOVE_CAPABILITY,
    SCREEN_CAPABILITY,
)
from minekin_core.domain.model_access import (
    CostLedger,
    Decision,
    ModelUnavailable,
    UnavailableReason,
)
from minekin_core.domain.perception import (
    InventoryStackValue,
    InventoryValue,
    SelfStateValue,
    WorldObservationValue,
)
from minekin_core.domain.world_actions import ActionResultClass, SkillOutcome

LOG = "minecraft:oak_log"
PLANKS = "minecraft:oak_planks"
STICK = "minecraft:stick"
PICKAXE = "minecraft:wooden_pickaxe"
CAP = 1_000_000

ALL_CAPABILITIES = frozenset(
    {AIM_CAPABILITY, MINE_CAPABILITY, HOTBAR_CAPABILITY, SCREEN_CAPABILITY, GUI_CAPABILITY}
)
AUTHORITY = ActionAuthority(lease_id="lease-1", generation=1, deadline_monotonic_ns=10**15)


class _NullSender:
    """The transport a tape never reaches: nothing is built, so nothing is sent."""

    async def send_control(self, message_type: str, message: Message) -> None:
        del message_type, message
        raise AssertionError("the tape answers before a command is built")


def reading(
    *,
    tick: int = 100,
    items: tuple[tuple[int, str, int], ...] = (),
    selected_slot: int | None = None,
) -> WorldObservationValue:
    return WorldObservationValue(
        generation=1,
        game_tick=tick,
        self_state=SelfStateValue(
            health=20.0,
            max_health=20.0,
            food=20,
            saturation=5.0,
            alive=True,
            yaw_degrees=0.0,
            pitch_degrees=0.0,
            selected_slot=selected_slot,
        ),
        aim=None,
        inventory=InventoryValue(
            revision=tick,
            stacks=tuple(
                InventoryStackValue(slot=slot, item_id=item_id, count=count)
                for slot, item_id, count in items
            ),
        ),
        visible_entities=(),
        mining=None,
        gui=None,
    )


class Stage:
    """The world as the loop sees it: a newest reading, and what replaces each action."""

    def __init__(self, *readings: WorldObservationValue | None) -> None:
        self.current: WorldObservationValue | None = readings[0] if readings else None
        self.follow_ups = list(readings[1:])

    @property
    def latest(self) -> WorldObservationValue | None:
        return self.current

    def advance(self) -> None:
        if self.follow_ups:
            self.current = self.follow_ups.pop(0)


class TapeSkills(WorldSkills):
    """The skills as a tape: each answer is scripted, and the world moves when it is given.

    Subclasses the real skills rather than standing in for them, so the argument names
    `perform_skill` passes are checked by the same signatures the client path uses.
    """

    def __init__(
        self,
        stage: Stage,
        outcomes: dict[str, SkillOutcome],
        breaks: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__(
            sender=_NullSender(),
            observations=WorldObservationStore(),
            capabilities=ALL_CAPABILITIES,
        )
        self.stage = stage
        self.outcomes = outcomes
        self.breaks = breaks
        self.ran: list[tuple[str, dict[str, object]]] = []

    async def _answer(self, name: str, **kwargs: object) -> SkillOutcome:
        if name in self.breaks:
            raise ConnectionError("the bridge closed")
        if name not in self.outcomes:
            raise AssertionError(f"the tape has no outcome for {name}")
        self.ran.append((name, kwargs))
        self.stage.advance()
        return self.outcomes[name]

    async def turn_to(
        self,
        *,
        yaw_degrees: float,
        pitch_degrees: float,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, timeout_ns
        return await self._answer("turn_to", yaw_degrees=yaw_degrees, pitch_degrees=pitch_degrees)

    async def break_seen_block(
        self,
        *,
        authority: ActionAuthority,
        expected_drop_item: str | None = None,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, timeout_ns
        return await self._answer("break_seen_block", expected_drop_item=expected_drop_item)

    async def collect_dropped(
        self,
        *,
        item_id: str,
        authority: ActionAuthority,
        walk_seconds: float = 1.0,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, walk_seconds, timeout_ns
        return await self._answer("collect_dropped", item_id=item_id)

    async def craft(
        self,
        *,
        recipe_id: str,
        materials: Mapping[str, int],
        product_id: str,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, timeout_ns
        return await self._answer(
            "craft", recipe_id=recipe_id, product_id=product_id, materials=dict(materials)
        )

    async def select_hotbar(
        self,
        *,
        slot: int,
        authority: ActionAuthority,
        expected_item_id: str | None = None,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, timeout_ns
        return await self._answer("select_hotbar", slot=slot, expected_item_id=expected_item_id)


class _OneShotProvider:
    """Answers the first ask and refuses by name after that, like an endpoint that went quiet."""

    def __init__(self, answer: Decision | ModelUnavailable) -> None:
        self.answer = answer
        self.used = False

    def decide(self, request: object) -> Decision | ModelUnavailable:
        del request
        if self.used:
            return ModelUnavailable(UnavailableReason.TRANSPORT_FAILURE)
        self.used = True
        return self.answer


def confirmed() -> SkillOutcome:
    return SkillOutcome(result=ActionResultClass.CONFIRMED, reason="", action_id="a-1")


def failed(reason: str = "MINING_STALLED") -> SkillOutcome:
    return SkillOutcome(result=ActionResultClass.FAILED, reason=reason, action_id="a-1")


def off_mind() -> PlayerMind:
    return mind_for(
        OffModelProvider(),
        CostLedger(run_cost_cap=CAP),
        kin_id="kin-01",
        model_enabled=False,
    )


def run(
    stage: Stage,
    skills: TapeSkills,
    mind: PlayerMind,
    *,
    step_budget: int = DEFAULT_STEP_BUDGET,
) -> AutonomousRun:
    """One turn of the loop, asked for the authority only after the mind has chosen."""

    return asyncio.run(
        run_autonomous_loop(
            mind=mind,
            skills=skills,
            observations=stage,
            authority=AUTHORITY,
            step_budget=step_budget,
        )
    )


# ------------------------------------------------------------------------ the closed loop


def test_the_loop_walks_the_whole_milestone_chain_without_a_written_plan() -> None:
    # Every reading is what the previous confirmed step would leave behind. Nothing here names
    # a skill: the order comes from the mind, and the stopping comes from a reading.
    stage = Stage(
        reading(tick=100, items=((0, LOG, 3),)),
        reading(tick=140, items=((0, LOG, 2), (1, PLANKS, 4))),
        reading(tick=180, items=((0, LOG, 2), (1, PLANKS, 4), (2, STICK, 2))),
        reading(tick=220, items=((0, LOG, 2), (1, PLANKS, 1), (3, PICKAXE, 1))),
        reading(tick=260, items=((0, LOG, 2), (1, PLANKS, 1), (3, PICKAXE, 1)), selected_slot=3),
    )
    skills = TapeSkills(stage, {"craft": confirmed(), "select_hotbar": confirmed()})
    mind = off_mind()

    result = run(stage, skills, mind)

    assert result.stop_reason == GOAL_HELD_IN_HAND
    assert [name for name, _ in skills.ran] == ["craft", "craft", "craft", "select_hotbar"]
    assert [kwargs.get("recipe_id") for _, kwargs in skills.ran] == [
        PLANKS,
        STICK,
        PICKAXE,
        None,
    ]
    assert skills.ran[3][1] == {"slot": 3, "expected_item_id": PICKAXE}
    assert mind.goal_met is True
    assert len(result.steps) == 4


def test_a_decision_that_claims_the_tool_does_not_end_the_run() -> None:
    # The provider says the craft finishes the milestone; the bag says it did not. The run
    # keeps going and the direction stays unmet, which is the whole of §4's rule.
    stage = Stage(
        reading(tick=100, items=((0, PLANKS, 3), (1, STICK, 2))),
        reading(tick=140, items=((0, PLANKS, 3), (1, STICK, 2))),
        reading(tick=180, items=((0, PLANKS, 3), (1, STICK, 2))),
    )
    skills = TapeSkills(stage, {"craft": confirmed()})
    mind = mind_for(
        _OneShotProvider(
            Decision(skill_id="craft", reason="this finishes the pickaxe", intent_generation=1)
        ),
        CostLedger(run_cost_cap=CAP),
    )

    result = run(stage, skills, mind, step_budget=2)

    assert result.stop_reason == STEP_BUDGET_SPENT
    assert mind.goal_met is False
    assert [name for name, _ in skills.ran] == ["craft", "craft"]


# ------------------------------------------------------------------------- its named endings


def test_a_reading_that_has_not_moved_stops_the_loop_before_it_asks_again() -> None:
    stage = Stage(reading(tick=100, items=((0, LOG, 3),)))
    skills = TapeSkills(stage, {"craft": failed()})
    mind = off_mind()

    result = run(stage, skills, mind)

    # The tape had no follow-up, so the world is the one the first intent was already built on.
    assert [name for name, _ in skills.ran] == ["craft"]
    assert result.stop_reason == NO_FRESH_OBSERVATION
    assert len(result.steps) == 1


def test_nothing_to_read_ends_the_run_with_the_mind_s_own_word() -> None:
    stage = Stage(None)
    skills = TapeSkills(stage, {})
    mind = off_mind()

    result = run(stage, skills, mind)

    assert result.stop_reason == NO_LATEST_OBSERVATION
    assert result.steps == ()
    assert skills.ran == []


def test_the_milestone_held_in_hand_before_the_first_ask_needs_no_step() -> None:
    stage = Stage(reading(items=((3, PICKAXE, 1),), selected_slot=3))
    skills = TapeSkills(stage, {})
    mind = off_mind()

    result = run(stage, skills, mind)

    assert result.stop_reason == GOAL_ACHIEVED
    assert result.steps == ()


def test_a_channel_that_goes_out_from_under_a_step_ends_the_run_by_name() -> None:
    stage = Stage(reading(items=((0, LOG, 3),)))
    skills = TapeSkills(stage, {"craft": confirmed()}, breaks=frozenset({"craft"}))
    mind = off_mind()

    result = run(stage, skills, mind)

    assert result.stop_reason == CONTROL_CHANNEL_LOST
    assert result.steps == ()


def test_the_step_budget_bounds_one_turn_rather_than_the_session() -> None:
    stage = Stage(*[reading(tick=100 + step) for step in range(10)])
    skills = TapeSkills(stage, {"turn_to": confirmed()})
    mind = off_mind()

    result = run(stage, skills, mind, step_budget=4)

    assert result.stop_reason == STEP_BUDGET_SPENT
    assert len(result.steps) == 4
    assert [name for name, _ in skills.ran] == ["turn_to"] * 4


# ---------------------------------------------------------------------------- the projection


def step_rows(document: dict[str, object]) -> list[dict[str, object]]:
    """Reach into the run document the way the gateway will: rows inside rows."""

    return cast(list[dict[str, object]], document["steps"])


def mind_row(document: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], document["mind"])


def intent_row(row: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], row["intent"])


def test_the_run_document_says_who_chose_and_what_the_world_said() -> None:
    stage = Stage(
        reading(tick=100, items=((0, LOG, 3),)),
        reading(tick=140, items=((0, LOG, 2), (1, PLANKS, 4))),
    )
    skills = TapeSkills(stage, {"craft": confirmed()})
    mind = off_mind()

    document = run(stage, skills, mind).as_document()

    # Two crafts went out, one for the planks the first reading could afford and one for the
    # sticks the second could; the run ended because the tape ran out of world, not because the
    # mind ran out of ideas.
    assert document["stop_reason"] == NO_FRESH_OBSERVATION
    assert document["confirmed"] == 2
    steps = step_rows(document)
    assert steps[0]["result"] == ActionResultClass.CONFIRMED.value
    assert steps[0]["attribution"] is None
    assert intent_row(steps[0])["source"] == "local_reflection"
    assert steps[0]["result_observation_ref"] == "tick=140;generation=1"
    assert steps[1]["result_observation_ref"] == steps[0]["result_observation_ref"]
    block = mind_row(document)
    assert block["direction"] == "hold_a_wooden_pickaxe"
    assert block["goal_met"] is False
    assert block["model_refusal"] == "MODEL_NOT_CONFIGURED"
    assert block["model_calls"] == 0


def test_a_step_that_failed_carries_its_attribution_into_the_document() -> None:
    stage = Stage(
        reading(tick=100, items=((0, LOG, 3),)),
        reading(tick=140, items=((0, LOG, 3),)),
    )
    skills = TapeSkills(stage, {"craft": failed(CRAFT_MATERIALS_MISSING)})
    mind = off_mind()

    document = run(stage, skills, mind).as_document()

    step = step_rows(document)[0]
    assert step["result"] == ActionResultClass.FAILED.value
    assert step["attribution"] == "RESOURCE_UNAVAILABLE"
    assert mind_row(document)["failure_attribution"] == "RESOURCE_UNAVAILABLE"


def test_the_ask_covers_the_whole_offer_and_nothing_the_offer_does_not_use() -> None:
    """The lease is decided before the mind chooses, so it has to cover every name it may be
    offered — and only those: a run that also held `use` or `look` would be a run holding a
    key nobody told it to hold."""

    ask = AutonomousAsk(skills=SKILL_OFFER, step_budget=DEFAULT_STEP_BUDGET, step_seconds=7.5)

    assert ask.capabilities == frozenset(
        {
            AIM_CAPABILITY,
            MINE_CAPABILITY,
            MOVE_CAPABILITY,
            SCREEN_CAPABILITY,
            GUI_CAPABILITY,
            HOTBAR_CAPABILITY,
        }
    )
    assert ask.lease_seconds == DEFAULT_STEP_BUDGET * 7.5


def test_an_ask_over_an_unknown_name_authorises_no_invented_capability() -> None:
    """A name outside the five is refused by the CLI's own skill-name check rather than by the
    union, so the union has to answer `None` as no capabilities and not as a stack trace."""

    assert AutonomousAsk(skills=("fly",), step_budget=1, step_seconds=1.0).capabilities == (
        frozenset()
    )
