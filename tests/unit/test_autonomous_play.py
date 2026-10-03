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
import time
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import cast

import pytest
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
    AutonomousStep,
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
    CLIENT_EXITED,
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
    USE_CAPABILITY,
)
from minekin_core.domain.goal_spec import Milestone
from minekin_core.domain.model_access import (
    CostLedger,
    Decision,
    ModelUnavailable,
    UnavailableReason,
)
from minekin_core.domain.perception import (
    AimKind,
    AimTargetValue,
    GuiScreenValue,
    InventoryStackValue,
    InventoryValue,
    SelfStateValue,
    WorldObservationValue,
)
from minekin_core.domain.recipe_catalog import coverage_of, learned_catalog
from minekin_core.domain.world_actions import ActionResultClass, SkillOutcome

LOG = "minecraft:oak_log"
PLANKS = "minecraft:oak_planks"
STICK = "minecraft:stick"
PICKAXE = "minecraft:wooden_pickaxe"
TABLE = "minecraft:crafting_table"
CAP = 1_000_000

#: The milestone these cells walk the loop against. It is a parameter of the fixture and not a
#: constant of the product: `PlayerMind` now asks its caller what to hold, so a run built without
#: one would be a Kin with nothing to craft toward, and the chain below would never be asked for.
#: Another item id standing in for this one changes nothing in the loop — that reuse is what
#: `test_player_mind.py` pins, and the live run names it in the harness.
GOAL = Milestone(product_id=PICKAXE, source_item_id=LOG)

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
    food: int = 20,
    aim: AimTargetValue | None = None,
) -> WorldObservationValue:
    return WorldObservationValue(
        generation=1,
        game_tick=tick,
        self_state=SelfStateValue(
            health=20.0,
            max_health=20.0,
            food=food,
            saturation=5.0,
            alive=True,
            yaw_degrees=0.0,
            pitch_degrees=0.0,
            selected_slot=selected_slot,
        ),
        aim=aim,
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

    async def craft_take_result(
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
            "craft_take_result",
            recipe_id=recipe_id,
            product_id=product_id,
            materials=dict(materials),
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

    async def close_screen(
        self,
        *,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, timeout_ns
        return await self._answer("close_screen")

    async def consume_item(
        self,
        *,
        item_id: str,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, timeout_ns
        return await self._answer("consume_item", item_id=item_id)


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


class _BlockingProvider:
    """An endpoint that answers over a *synchronous* round-trip, like `urllib.urlopen`.

    It samples a shared heartbeat counter the moment the call starts and the moment it ends. A
    `next_intent` that ran on the event loop would freeze that counter for the whole sleep —
    which is the exact mechanism that starved the stop-request watcher and forced the SIGTERM.
    """

    def __init__(self, answer: Decision, *, delay: float, probe: Callable[[], int]) -> None:
        self.answer = answer
        self.delay = delay
        self.probe = probe
        self.ticks_at_start = 0
        self.ticks_at_end = 0

    def decide(self, request: object) -> Decision:
        del request
        self.ticks_at_start = self.probe()
        time.sleep(self.delay)
        self.ticks_at_end = self.probe()
        return self.answer


def confirmed() -> SkillOutcome:
    return SkillOutcome(result=ActionResultClass.CONFIRMED, reason="", action_id="a-1")


def failed(reason: str = "MINING_STALLED") -> SkillOutcome:
    return SkillOutcome(result=ActionResultClass.FAILED, reason=reason, action_id="a-1")


def off_mind(goal: Milestone | None = GOAL) -> PlayerMind:
    """A mind on the shipped `off` provider, holding the milestone the fixture names.

    The goal is an argument here rather than a default the product carries: which of these cells
    walks a craft chain and which one wanders a world with nothing to want is decided by what the
    caller hands in, and the loop's own behaviour must read the same either way.
    """

    return mind_for(
        OffModelProvider(),
        CostLedger(run_cost_cap=CAP),
        kin_id="kin-01",
        goal=goal,
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


def test_the_loop_walks_the_plan_and_stands_up_the_grid_enabler() -> None:
    # Every reading is what the previous confirmed step would leave behind. Nothing here names
    # a skill: the order comes from the mind, and so does the stopping — by the step budget once
    # every craft the two-by-two grid can pay for has run.
    stage = Stage(
        reading(tick=100, items=((0, LOG, 1),)),
        reading(tick=140, items=((0, PLANKS, 4),)),
        reading(tick=180, items=((0, PLANKS, 4), (1, STICK, 2))),
    )
    skills = TapeSkills(stage, {"craft_take_result": confirmed()})
    mind = off_mind()

    result = run(stage, skills, mind, step_budget=3)

    # The mind asks for the transaction whose product lands where a reading can see it: the
    # recipe click alone leaves the result on the cursor or in the grid, and 2026-09-30's two
    # live runs showed nothing coming back from either, so a chain built on it cannot close.
    assert all(name == "craft_take_result" for name, _ in skills.ran)
    # Each of those calls was answered as an order: the ask names the milestone's product on every
    # step, and the plan says which ingredient craft the reading could run for it. Two vocabularies
    # on one document, which is what lets a reader tell what was wanted from what was clicked.
    assert [dict(step.intent.arguments) for step in result.steps] == [
        {"target_item": PICKAXE, "quantity": 1}
    ] * 3
    # The plan for a three-by-three tool reserves the crafting table as its own owed step — the
    # general grid-enabler the catalog declares through `opens_grid_side`, not a name hardcoded
    # here. So the chain the off-model loop walks is planks, then the sticks the tool eats, then
    # the table itself: the last is a two-by-two shape this grid CAN hold, and the step the pickaxe
    # dead-ended on before the enabler existed is now a payable craft rather than a wall.
    assert [kwargs.get("recipe_id") for _, kwargs in skills.ran] == [PLANKS, STICK, TABLE]
    # The run ends on the budget, not on `CRAFT_GRID_TOO_SMALL`: standing a wider grid up is a
    # runnable plan now, so the terminal craft is reached by placing the table (select, then the
    # use key) rather than refused against the inventory. That place-then-open is judged against a
    # live reading in the mind's offer, not by this tape, which carries only the craft outcome.
    assert result.stop_reason == STEP_BUDGET_SPENT
    assert mind.goal_met is False
    assert len(result.steps) == 3


def test_the_loop_closes_on_a_reading_that_shows_the_tool_held() -> None:
    """Where the tool came from is not this loop's business; what ends the direction is a
    reading that shows it in the selected slot. The bag here gets the pickaxe from outside the
    skills this build has — no recipe in the inventory's two-by-two grid makes it — which is
    precisely why a reading, and not a step's own claim, is what closes the run."""

    stage = Stage(
        reading(tick=100, items=((3, PICKAXE, 1),)),
        reading(tick=140, items=((3, PICKAXE, 1),), selected_slot=3),
    )
    skills = TapeSkills(stage, {"select_hotbar": confirmed()})
    mind = off_mind()

    result = run(stage, skills, mind)

    assert [name for name, _ in skills.ran] == ["select_hotbar"]
    assert skills.ran[0][1] == {"slot": 3, "expected_item_id": PICKAXE}
    assert result.stop_reason == GOAL_HELD_IN_HAND
    assert mind.goal_met is True


def test_a_decision_that_claims_the_tool_does_not_end_the_run() -> None:
    # The provider says the craft finishes the milestone; the bag says it did not. The run
    # keeps going and the direction stays unmet, which is the whole of §4's rule.
    stage = Stage(
        reading(tick=100, items=((0, LOG, 1), (1, PLANKS, 1), (2, STICK, 2))),
        reading(tick=140, items=((0, LOG, 1), (1, PLANKS, 1), (2, STICK, 2))),
        reading(tick=180, items=((0, LOG, 1), (1, PLANKS, 1), (2, STICK, 2))),
    )
    skills = TapeSkills(stage, {"craft_take_result": confirmed()})
    mind = mind_for(
        _OneShotProvider(
            Decision(
                skill_id="craft_take_result",
                reason="this finishes the pickaxe",
                intent_generation=1,
            )
        ),
        CostLedger(run_cost_cap=CAP),
    )

    result = run(stage, skills, mind, step_budget=2)

    assert result.stop_reason == STEP_BUDGET_SPENT
    assert mind.goal_met is False
    assert [name for name, _ in skills.ran] == ["craft_take_result", "craft_take_result"]


def test_a_blocking_model_round_trip_does_not_freeze_the_event_loop() -> None:
    """The real provider answers over a blocking socket call, so `next_intent` must leave the loop.

    This is the regression behind the exit-143 diagnosis: run on the loop, a round-trip that
    sleeps for its `timeout_ms` would stall every other task the supervision needs — the IPC
    reader delivering the confirming frame, and the stop-request watcher that releases keys over
    a still-live channel — which is exactly how a cooperative stop became a forced SIGTERM. A
    heartbeat task runs throughout; the provider samples it at the start and end of its own
    blocking call. If the loop were frozen the two samples would be equal; they must not be.
    """

    stage = Stage(
        reading(tick=100, items=((0, LOG, 1), (1, PLANKS, 2))),
        reading(tick=140, items=((0, LOG, 1), (1, PLANKS, 2))),
    )
    skills = TapeSkills(stage, {"craft_take_result": confirmed()})

    ticks = {"n": 0}
    provider = _BlockingProvider(
        Decision(skill_id="craft_take_result", reason="off the loop", intent_generation=1),
        delay=0.25,
        probe=lambda: ticks["n"],
    )
    mind = mind_for(provider, CostLedger(run_cost_cap=CAP))

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(0.02)
            ticks["n"] += 1

    async def play() -> None:
        pulse = asyncio.create_task(heartbeat())
        try:
            await run_autonomous_loop(
                mind=mind,
                skills=skills,
                observations=stage,
                authority=AUTHORITY,
                step_budget=1,
            )
        finally:
            pulse.cancel()

    asyncio.run(play())

    assert provider.ticks_at_end > provider.ticks_at_start


# ------------------------------------------------------------------------- its named endings


def test_a_reading_that_has_not_moved_stops_the_loop_before_it_asks_again() -> None:
    stage = Stage(reading(tick=100, items=((0, LOG, 3),)))
    skills = TapeSkills(stage, {"craft_take_result": failed()})
    mind = off_mind()

    result = run(stage, skills, mind)

    # The tape had no follow-up, so the world is the one the first intent was already built on.
    assert [name for name, _ in skills.ran] == ["craft_take_result"]
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
    skills = TapeSkills(
        stage, {"craft_take_result": confirmed()}, breaks=frozenset({"craft_take_result"})
    )
    mind = off_mind()

    result = run(stage, skills, mind)

    assert result.stop_reason == CONTROL_CHANNEL_LOST
    assert result.steps == ()


def test_a_lost_channel_names_the_error_that_lost_it() -> None:
    """Which error ended the channel is a fact the run has to carry out of the loop.

    `CONTROL_CHANNEL_LOST` says the loop stopped; only the error's own name says whether the
    bridge closed a socket or refused a write, and after the channel is gone no later reading
    can answer that — the run that lost it is the only witness.
    """

    stage = Stage(reading(items=((0, LOG, 3),)))
    skills = TapeSkills(
        stage, {"craft_take_result": confirmed()}, breaks=frozenset({"craft_take_result"})
    )
    mind = off_mind()

    result = run(stage, skills, mind)

    assert result.stop_detail == "ConnectionError"
    assert result.as_document()["stop_detail"] == "ConnectionError"


def test_a_stop_the_world_caused_names_no_channel_error() -> None:
    """A run that stopped for a reading's own reason carried no error, and says so empty.

    The name belongs to the channel branch alone; inventing one elsewhere would let a reader
    mistake a stalled world for a lost bridge.
    """

    stage = Stage(None)
    skills = TapeSkills(stage, {})
    mind = off_mind()

    result = run(stage, skills, mind)

    assert result.stop_reason == NO_LATEST_OBSERVATION
    assert result.stop_detail == ""


@pytest.mark.parametrize("step_budget", [4, 48])
def test_the_step_budget_bounds_one_turn_rather_than_the_session(step_budget: int) -> None:
    stage = Stage(*[reading(tick=100 + step) for step in range(step_budget + 6)])
    skills = TapeSkills(stage, {"turn_to": confirmed()})
    mind = off_mind()

    result = run(stage, skills, mind, step_budget=step_budget)

    assert result.stop_reason == STEP_BUDGET_SPENT
    assert len(result.steps) == step_budget
    assert [name for name, _ in skills.ran] == ["turn_to"] * step_budget


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
    skills = TapeSkills(stage, {"craft_take_result": confirmed()})
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
    assert block["direction"] == "hold_wooden_pickaxe"
    assert block["milestone"] == GOAL.as_document()
    assert block["goal_met"] is False
    assert block["model_refusal"] == "MODEL_NOT_CONFIGURED"
    assert block["model_calls"] == 0


def test_a_step_that_failed_carries_its_attribution_into_the_document() -> None:
    stage = Stage(
        reading(tick=100, items=((0, LOG, 3),)),
        reading(tick=140, items=((0, LOG, 3),)),
    )
    skills = TapeSkills(stage, {"craft_take_result": failed(CRAFT_MATERIALS_MISSING)})
    mind = off_mind()

    document = run(stage, skills, mind).as_document()

    step = step_rows(document)[0]
    assert step["result"] == ActionResultClass.FAILED.value
    assert step["attribution"] == "RESOURCE_UNAVAILABLE"
    assert mind_row(document)["failure_attribution"] == "RESOURCE_UNAVAILABLE"


def test_the_same_loop_walks_a_milestone_other_than_the_fixture_one() -> None:
    """One item stands in for another and the loop does not notice.

    The pickaxe is a parameter of these cells, not a constant of this module's subject, so the
    honest check is that a different milestone is walked by the same code and closes on *its*
    being held. The arguments ride along in the intent: what the ask named is what the step was
    built for, and that is the half a live run has to agree with.
    """

    stage = Stage(
        reading(tick=100, items=((0, PLANKS, 5),)),
        reading(tick=140, items=((3, STICK, 4),), selected_slot=3),
    )
    skills = TapeSkills(stage, {"craft_take_result": confirmed()})
    mind = off_mind(goal=Milestone(product_id=STICK, source_item_id=PLANKS))

    result = run(stage, skills, mind)
    document = result.as_document()

    assert result.stop_reason == GOAL_HELD_IN_HAND
    step = step_rows(document)[0]
    assert intent_row(step)["skill"] == "craft_take_result"
    assert intent_row(step)["arguments"] == {"target_item": STICK, "quantity": 1}
    assert mind_row(document)["direction"] == "hold_stick"


def test_a_mind_with_no_milestone_still_asks_and_never_stops_on_a_held_item() -> None:
    """A session that named no goal is a shape of run, not a misconfiguration.

    Nothing in Core wants the pickaxe on the Kin's own behalf, so the loop has to keep working off
    the readings alone when the milestone is absent — and it must not end on `GOAL_HELD_IN_HAND`,
    because no item was ever asked to be held. The run document says so in the same two fields a
    reader of a run with a goal reads.
    """

    stage = Stage(
        reading(tick=100, items=((0, LOG, 3),)),
        reading(tick=140, items=((0, LOG, 2), (1, PLANKS, 4)), selected_slot=0),
    )
    skills = TapeSkills(stage, {"craft_take_result": confirmed()})

    document = run(stage, skills, off_mind(goal=None)).as_document()

    block = mind_row(document)
    assert document["stop_reason"] == NO_FRESH_OBSERVATION
    assert block["milestone"] is None
    assert block["direction"] == ""
    assert block["goal_met"] is False
    assert intent_row(step_rows(document)[0])["skill"] == "craft_take_result"


def test_the_ask_covers_the_whole_offer_and_nothing_the_offer_does_not_use() -> None:
    """The lease is decided before the mind chooses, so it has to cover every name it may be
    offered — and only those: a run that also held `look` would be a run holding a key nobody
    told it to hold, while `use` belongs here because `use_target` is now part of the offer."""

    ask = AutonomousAsk(skills=SKILL_OFFER, step_budget=DEFAULT_STEP_BUDGET, step_seconds=7.5)

    assert ask.capabilities == frozenset(
        {
            AIM_CAPABILITY,
            MINE_CAPABILITY,
            MOVE_CAPABILITY,
            SCREEN_CAPABILITY,
            GUI_CAPABILITY,
            HOTBAR_CAPABILITY,
            USE_CAPABILITY,
        }
    )
    assert ask.lease_seconds == DEFAULT_STEP_BUDGET * 7.5


def test_an_ask_over_an_unknown_name_authorises_no_invented_capability() -> None:
    """A name outside the five is refused by the CLI's own skill-name check rather than by the
    union, so the union has to answer `None` as no capabilities and not as a stack trace."""

    assert AutonomousAsk(skills=("fly",), step_budget=1, step_seconds=1.0).capabilities == (
        frozenset()
    )


def test_a_step_that_lost_its_client_ends_the_run_by_name() -> None:
    """A dead JVM is not a stalled world.

    The loop would otherwise keep the mind asking a client that can no longer answer,
    and the document would read as a mind that tried everything rather than a run whose
    process exited. The step is still recorded, with the exit code the supervisor gave.
    """

    stage = Stage(reading(items=((0, LOG, 3),)))
    skills = TapeSkills(
        stage,
        {
            "craft_take_result": SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason=CLIENT_EXITED,
                action_id="",
                details={"exit_code": "143"},
            )
        },
    )

    result = run(stage, skills, off_mind())

    assert result.stop_reason == CLIENT_EXITED
    assert result.stop_detail == "143"
    assert len(result.steps) == 1
    assert result.steps[0].outcome.reason == CLIENT_EXITED


def test_a_run_reads_which_crafts_the_world_confirmed_and_grows_coverage_from_them() -> None:
    """The dynamic recipe source's first wired edge, end to end. The same loop that stands up the
    grid enabler answers the next question without any hand-editing: which products did the world
    *say* it crafted? On this tape planks, sticks and the table each come back `CONFIRMED`, so the
    run reports exactly those three — and feeding them to `learned_catalog` moves the crafting
    table, until now only a curated claim, onto the watched side. The pickaxe is the honest
    residue: its shape needs a 3x3 grid this two-by-two tape never opened, so it was never
    confirmed and stays curated. Coverage thus grows from readings, and the boundary a reader sees
    after a run is that run's own, recomputed — not a table somebody marked watched."""

    stage = Stage(
        reading(tick=100, items=((0, LOG, 1),)),
        reading(tick=140, items=((0, PLANKS, 4),)),
        reading(tick=180, items=((0, PLANKS, 4), (1, STICK, 2))),
    )
    skills = TapeSkills(stage, {"craft_take_result": confirmed()})

    result = run(stage, skills, off_mind(), step_budget=3)

    assert result.confirmed_craft_products() == frozenset({PLANKS, STICK, TABLE})

    learned = coverage_of(learned_catalog(result.confirmed_craft_products()))
    assert TABLE in learned.live_confirmed
    assert TABLE not in learned.curated_only
    assert learned.curated_only == frozenset({PICKAXE})


def test_step_document_keeps_the_execution_readings_needed_to_diagnose_unknowns() -> None:
    intent = off_mind().next_intent(reading())
    outcome = SkillOutcome(
        result=ActionResultClass.UNKNOWN,
        reason="NO_CONFIRMING_OBSERVATION",
        action_id="craft-1",
        pre_tick=100,
        details={"pre_inventory_revision": "100", "newest_inventory_revision": "130"},
    )
    step = AutonomousStep(intent, outcome, None, "tick=130;generation=1")
    document = step.as_document()
    assert document["details"] == dict(outcome.details)


def test_a_goal_already_in_hand_still_closes_the_crafting_window_before_success() -> None:
    opened = replace(
        reading(tick=100, items=((0, PICKAXE, 1),), selected_slot=0),
        gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=1),
    )
    closed = reading(tick=110, items=((0, PICKAXE, 1),), selected_slot=0)
    stage = Stage(opened, closed)
    skills = TapeSkills(stage, {"close_screen": confirmed()})
    outcome = run(stage, skills, off_mind(), step_budget=3)
    assert outcome.stop_reason == GOAL_HELD_IN_HAND
    assert [name for name, _ in skills.ran] == ["close_screen"]
    assert stage.latest is not None and stage.latest.gui is None


def test_model_choice_is_rechecked_when_a_screen_opens_during_decision() -> None:
    stage = Stage(
        reading(tick=100),
        replace(reading(tick=120), gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=1)),
    )
    skills = TapeSkills(stage, {"turn_to": confirmed()})

    class OpeningScreenProvider:
        def decide(self, request: object) -> Decision:
            del request
            stage.advance()
            return Decision(
                skill_id="turn_to",
                reason="inspect",
                intent_generation=1,
                arguments={"yaw_degrees": 0.0, "pitch_degrees": 30.0},
            )

    mind = mind_for(OpeningScreenProvider(), CostLedger(run_cost_cap=CAP))
    result = run(stage, skills, mind, step_budget=1)
    assert skills.ran == []
    assert result.steps[0].outcome.result is ActionResultClass.INTERRUPTED
    assert result.steps[0].outcome.reason == "DECISION_PRECONDITION_CHANGED"
    assert mind.attempts == {}


def test_the_loop_eats_when_the_bar_is_low_and_the_bag_holds_a_meal() -> None:
    """A hungry Kin with no milestone still lives: the local layer reaches for the
    meal the reading supports, the step runs the consume skill the plan names, and
    the run goes on afterwards — the same loop, one more skill in its offer."""

    miss_aim = AimTargetValue(game_tick=100, kind=AimKind.MISS)
    later_miss = AimTargetValue(game_tick=140, kind=AimKind.MISS)
    stage = Stage(
        reading(tick=100, items=((0, "minecraft:apple", 2),), food=4, aim=miss_aim),
        reading(tick=140, items=((0, "minecraft:apple", 1),), food=8, aim=later_miss),
    )
    skills = TapeSkills(stage, {"consume_item": confirmed(), "turn_to": confirmed()})
    mind = off_mind(goal=None)

    result = run(stage, skills, mind, step_budget=2)

    assert next(name for name, _ in skills.ran) == "consume_item"
    assert skills.ran[0][1] == {"item_id": "minecraft:apple"}
    assert result.steps[0].intent.arguments == {"target_item": "minecraft:apple"}
    assert result.steps[0].outcome.result is ActionResultClass.CONFIRMED
    assert result.stop_reason == STEP_BUDGET_SPENT
    assert mind.goal_met is False
