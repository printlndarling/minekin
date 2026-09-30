"""What the Kin wants, what it is therefore allowed to try, and what the world said back.

This is §3 of `docs/s3-minimal-player-mind.md`: one long-running direction, one current
intent, two needs read from player-equivalent observation, and failure attribution that
changes the next ask rather than repeating it. It contains no keystrokes. A decision becomes
a `SkillPlan` and the S2 seam (`application.skill_plan`) is what runs it, because "the mind
chose it" and "it happened" are two different claims and only the second is worth a log line.

The provider is a structural protocol declared here rather than imported from
`adapters/model`: the frozen dependency direction forbids this layer from naming an adapter,
and a one-method port is exactly the kind of seam both sides should describe alone.

`off` is a supported shape, not a degraded one. When there is no model — no credentials, a
stopped endpoint, a spend already at the cap — the provider's named refusal is recorded and
the local reflection below picks the next step from the same feasible set the model was
offered. Such a run reports a decision source of `local_reflection` in every projection of
it, so nobody reading the dashboard can mistake a deterministic shortlist for a model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Protocol

from minekin_core.application.skill_plan import (
    SKILL_ARGUMENT_MISSING,
    SKILL_UNKNOWN,
    SkillPlan,
)
from minekin_core.application.world_skills import SkillCall
from minekin_core.domain.model_access import (
    MAX_REASON_CHARS,
    CostLedger,
    Decision,
    DecisionRequest,
    ModelUnavailable,
    UnavailableReason,
)
from minekin_core.domain.perception import WorldObservationValue
from minekin_core.domain.recipe_catalog import (
    CRAFT_GRID_TOO_SMALL,
    CRAFT_MATERIALS_MISSING,
    PLAYER_GRID_SIDE,
    RECIPES,
    Recipe,
)
from minekin_core.domain.world_actions import (
    ActionResultClass,
    SkillOutcome,
    item_total,
    seen_drops,
)

#: The one long-running direction S3 ships: get a wooden pickaxe and keep holding it.
#: Phrased as a milestone rather than a task because its completion condition is a reading
#: of the inventory, which is the only place §4 lets a goal be closed.
LONG_TERM_DIRECTION: Final = "hold_a_wooden_pickaxe"
GOAL_PRODUCT_ID: Final = "minecraft:wooden_pickaxe"
#: The raw resource the milestone is built from, and the only drop this mind looks for.
SOURCE_ITEM_ID: Final = "minecraft:oak_log"

#: How many times one skill may fail the same way before the mind stops calling it that
#: way. Two is a retry and a second attempt; a third identical failure against the same
#: world state is a different problem, and replaying the click is what §3 forbids.
RETRY_BUDGET_PER_SIGNATURE: Final = 2

#: The heading a scan turns to between intents. The pitch is the one the operator-written
#: plan uses: a trunk seen from a few blocks away sits below eye level.
SCAN_YAW_STEP_DEGREES: Final = 45.0
SCAN_PITCH_DEGREES: Final = -18.0

#: Reused verbatim from the skill layer so the word for "there was nothing to read" is the
#: same on both sides of this module, as it already is on both sides of the IPC channel.
NO_LATEST_OBSERVATION: Final = "NO_LATEST_OBSERVATION"
NO_CONFIRMING_OBSERVATION: Final = "NO_CONFIRMING_OBSERVATION"
# `CRAFT_MATERIALS_MISSING` and `CRAFT_GRID_TOO_SMALL` are imported from the recipe catalog
# rather than restated here: one word per precondition, defined once, whoever asks.
#: The mind's own two holds. Both say "do nothing"; only one of them says the run should
#: go on waiting, and the projection shows which.
GOAL_ACHIEVED: Final = "GOAL_ACHIEVED"
NO_FEASIBLE_SKILL: Final = "NO_FEASIBLE_SKILL"

DECISION_FROM_MODEL: Final = "model"
DECISION_FROM_LOCAL: Final = "local_reflection"

#: Which refusal words mean which of §3's four attributions. Anything unlisted lands in
#: `ACTION_NOT_EFFECTIVE`: the four codes are deliberately coarse, and the skill's own
#: `reason` is kept beside the code so the distinction a fix needs is never lost.
#: A grid that cannot hold the shape is `SKILL_NOT_IMPLEMENTED` rather than a missing
#: resource: more wood would not move it, and the thing that is absent is a skill for the
#: screen the recipe needs.
_NOT_IMPLEMENTED_REASONS: Final = frozenset(
    {SKILL_UNKNOWN, SKILL_ARGUMENT_MISSING, CRAFT_GRID_TOO_SMALL}
)
_UNREADABLE_REASONS: Final = frozenset({NO_LATEST_OBSERVATION, NO_CONFIRMING_OBSERVATION})
_ABSENT_REASONS: Final = frozenset(
    {"NO_SEEN_DROP", CRAFT_MATERIALS_MISSING, "MINE_TARGET_NOT_AIMED"}
)

#: The order the feasible set is reported in, and so the order a scan of it reads. Listed
#: once here because a model's offer and the local fallback have to be the same list, not
#: two lists that happen to agree today.
SKILL_OFFER: Final = (
    "break_seen_block",
    "collect_dropped",
    "craft_take_result",
    "select_hotbar",
    "turn_to",
)


@dataclass(frozen=True, slots=True)
class CraftStage:
    """One link of the milestone chain: what it makes, how many, and what it costs."""

    product_id: str
    required_total: int
    #: The game's own recipe, read out of the catalog by product id. The stage does not carry
    #: an ingredient list of its own so there is exactly one place a recipe can be wrong.
    recipe: Recipe

    @property
    def materials(self) -> tuple[tuple[str, int], ...]:
        return self.recipe.ingredients


def _fixture_stage(product_id: str, required_total: int) -> CraftStage:
    return CraftStage(
        product_id=product_id, required_total=required_total, recipe=RECIPES[product_id]
    )


#: A DEMO FIXTURE, not the product's recipe knowledge: the game facts live in
#: `domain.recipe_catalog`, and what is declared here is only the demo's own milestone — how
#: many of each thing the scripted 1.20.1 trunk run is meant to be holding. It is a tuple in
#: build order rather than a lookup because "which craft is next" is answered by position: a
#: mind that could reach for any recipe could also invent one, and §2 says it may not. A real
#: goal selection replaces this table; it does not need new recipe code.
CRAFT_CHAIN: Final[tuple[CraftStage, ...]] = (
    _fixture_stage("minecraft:oak_planks", 3),
    _fixture_stage("minecraft:stick", 2),
    _fixture_stage(GOAL_PRODUCT_ID, 1),
)


class FailureCode(StrEnum):
    """§3's four real, judgeable attributions, and nothing else."""

    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    SKILL_NOT_IMPLEMENTED = "SKILL_NOT_IMPLEMENTED"
    ACTION_NOT_EFFECTIVE = "ACTION_NOT_EFFECTIVE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class MindDecisionKind(StrEnum):
    """Whether there is something to run, nothing to run yet, or nothing left to run."""

    INTENT = "INTENT"
    HOLD = "HOLD"
    BLOCKED = "BLOCKED"


class DecisionProvider(Protocol):
    """The half of `ModelProvider` this module may ask of it.

    Structural on purpose: `adapters/model` satisfies it without importing it, and a test
    hands over an object of its own making without importing either.
    """

    def decide(self, request: DecisionRequest) -> Decision | ModelUnavailable: ...


def attribute_failure(outcome: SkillOutcome) -> FailureCode:
    """Which of the four codes the readings support for this outcome.

    `UNKNOWN` outranks its own reason: the skill could not tell whether the world changed,
    which is `INSUFFICIENT_INFORMATION` whatever word it was filed under.
    """

    if outcome.result is ActionResultClass.UNKNOWN:
        return FailureCode.INSUFFICIENT_INFORMATION
    if outcome.reason in _UNREADABLE_REASONS:
        return FailureCode.INSUFFICIENT_INFORMATION
    if outcome.reason in _NOT_IMPLEMENTED_REASONS:
        return FailureCode.SKILL_NOT_IMPLEMENTED
    if outcome.reason in _ABSENT_REASONS:
        return FailureCode.RESOURCE_UNAVAILABLE
    return FailureCode.ACTION_NOT_EFFECTIVE


def goal_held(reading: WorldObservationValue) -> bool:
    return item_total(reading.inventory, GOAL_PRODUCT_ID) > 0


def _goal_slot(reading: WorldObservationValue) -> int | None:
    for stack in reading.inventory.stacks:
        if stack.item_id == GOAL_PRODUCT_ID:
            return stack.slot
    return None


def goal_in_hand(reading: WorldObservationValue) -> bool:
    """Whether the milestone item is the slot the player has selected.

    The direction is *hold* the tool, not obtain it once, so "in hand" is the condition that
    ends the run rather than "in the bag somewhere". An unread `selected_slot` counts as not
    in hand: the ask that follows is the cheap one, and it is filed against a reading that
    did not say the tool was already held.
    """

    slot = _goal_slot(reading)
    return slot is not None and slot == reading.self_state.selected_slot


def shortfalls(reading: WorldObservationValue) -> tuple[CraftStage, ...]:
    """The chain stages this reading does not yet hold enough of, in build order."""

    return tuple(
        stage
        for stage in CRAFT_CHAIN
        if item_total(reading.inventory, stage.product_id) < stage.required_total
    )


def next_craft(
    reading: WorldObservationValue, *, grid_side: int = PLAYER_GRID_SIDE
) -> CraftStage | None:
    """The first stage still needed whose materials this inventory can pay for and whose shape
    the grid being opened can hold.

    Strictly in chain order, and a stage is only offered when its materials are already in
    the bag: the precondition check the contract asks for happens here, before a command is
    built, so a craft that cannot be honoured is never sent. The grid is checked in the same
    place for the same reason — a three-by-three shape clicked into the inventory's
    two-by-two is a command the world can only shrug at, and a `CONFIRMED` verdict belongs to
    crafts that could have happened.
    """

    for stage in shortfalls(reading):
        if not stage.recipe.fits(grid_side):
            continue
        affordable = all(
            item_total(reading.inventory, item_id) >= count for item_id, count in stage.materials
        )
        if affordable:
            return stage
    return None


def craft_blocker(reading: WorldObservationValue, *, grid_side: int = PLAYER_GRID_SIDE) -> str:
    """Why no craft can run on this reading, in the name of the precondition, or empty.

    The distinction is not decoration: `CRAFT_MATERIALS_MISSING` sends the Kin back to the
    trunk, and `CRAFT_GRID_TOO_SMALL` says the milestone needs a screen this build has no
    skill for. A mind that got the first word for the second fact would gather wood it already
    has enough of until the harness stopped it.
    """

    if next_craft(reading, grid_side=grid_side) is not None:
        return ""
    needed = shortfalls(reading)
    if not needed:
        return ""
    if any(stage.recipe.fits(grid_side) for stage in needed):
        return CRAFT_MATERIALS_MISSING
    return CRAFT_GRID_TOO_SMALL


def feasible_skill_ids(reading: WorldObservationValue) -> tuple[str, ...]:
    """What this reading supports — the only set a model gets to choose inside.

    `turn_to` is offered whenever there is a reading at all, because it is the conservative
    action: it changes what is in view without spending a resource or leaving a block broken
    halfway. A mind with nothing else to do looks around rather than stalls.
    """

    feasible = {
        "break_seen_block" if reading.aim is not None and reading.aim.block is not None else "",
        "collect_dropped" if seen_drops(reading.visible_entities, SOURCE_ITEM_ID) else "",
        "craft_take_result" if next_craft(reading) is not None else "",
        "select_hotbar"
        if _goal_slot(reading) not in (None, reading.self_state.selected_slot)
        else "",
        "turn_to",
    }
    return tuple(name for name in SKILL_OFFER if name in feasible)


def needs_from(reading: WorldObservationValue) -> dict[str, int]:
    """The two needs §3 allows, as ordering numbers and nothing else.

    `resource_security` is about the milestone, not about wood: holding planks is less
    secure than holding the tool those planks were meant to become. `safety` reads health and
    food and only orders actions — no number here generates a line of dialogue.
    """

    if goal_held(reading):
        resource_security = 1
    elif item_total(reading.inventory, CRAFT_CHAIN[0].product_id) > 0:
        resource_security = 5
    else:
        resource_security = 9
    health = reading.self_state.health
    max_health = reading.self_state.max_health or 1.0
    food = reading.self_state.food
    if not reading.self_state.alive:
        safety = 9
    elif health < max_health * 0.5 or food <= 2:
        safety = 7
    elif health < max_health * 0.9 or food <= 6:
        safety = 3
    else:
        safety = 1
    return {"resource_security": resource_security, "safety": safety}


def observation_ref(reading: WorldObservationValue) -> str:
    """A reference to one reading, not a copy of it.

    Tick and generation together identify it inside a session and say nothing about its
    contents, which is what keeps the model's world to what §2 promises: a pointer to the
    summary, never the summary's items or coordinates.
    """

    return f"tick={reading.game_tick};generation={reading.generation}"


@dataclass(frozen=True, slots=True)
class MindIntent:
    """One decision, in the shape the session needs to lease and run it.

    `plan` carries the arguments a chosen skill cannot invent — which recipe, which item,
    which slot — filled from the reading this intent was built on. `observation_ref` names
    that reading, so the projection can say what the ask was based on rather than implying
    it was based on whatever the world looks like now.
    """

    kind: MindDecisionKind
    plan: SkillPlan
    reason: str
    source: str = ""
    intent_generation: int = 0
    observation_ref: str = ""
    model_refusal: str = ""

    @property
    def skill(self) -> str:
        return self.plan.calls[0].name if self.plan.calls else ""

    @property
    def capabilities(self) -> frozenset[str]:
        """What running this intent would need leased, which is the plan's own union."""

        return self.plan.capabilities

    def as_document(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "skill": self.skill,
            "reason": self.reason,
            "source": self.source,
            "intent_generation": self.intent_generation,
            "observation_ref": self.observation_ref,
            "model_refusal": self.model_refusal,
        }


@dataclass
class PlayerMind:
    """The smallest thing that can want a wooden pickaxe and be told it does not have one.

    Mutable and single-threaded by design: this is one Kin's running state — the direction,
    the generation it is on, which skills have spent their retries — read by exactly one
    session loop. Nothing about the world is cached here beyond the one reading an intent was
    built on; `WorldObservationStore` stays the only judge of what things look like.
    """

    provider: DecisionProvider
    ledger: CostLedger
    kin_id: str = ""
    persona_seed: str = ""
    direction: str = LONG_TERM_DIRECTION
    model_enabled: bool = True
    intent_generation: int = 0
    goal_met: bool = field(default=False, init=False)
    scan_step: int = field(default=0, init=False)
    attempts: dict[tuple[str, FailureCode], int] = field(
        default_factory=dict[tuple[str, FailureCode], int], init=False
    )
    excluded: set[str] = field(default_factory=set[str], init=False)
    last_intent: MindIntent | None = field(default=None, init=False)
    last_result: SkillOutcome | None = field(default=None, init=False)
    last_failure: FailureCode | None = field(default=None, init=False)
    last_model_refusal: str = field(default="", init=False)

    def observe(self, reading: WorldObservationValue | None) -> None:
        """Say whether the direction is met, off a reading, because nothing else may say it.

        The skill that crafted the pickaxe already reached a `CONFIRMED` verdict of its own,
        and that verdict was itself derived from a pair of readings — this is a later one,
        taken after the intent was recorded. §4 closes a goal on the world's word, not on a
        decision's self-report, so it reads the inventory here. It reads it in both
        directions: the milestone is *holding* the tool, so a later reading that no longer
        has one un-closes it and the Kin goes back to work rather than reporting a pickaxe it
        has lost.
        """

        if reading is not None:
            self.goal_met = goal_held(reading)

    def next_intent(self, reading: WorldObservationValue | None) -> MindIntent:
        """Ask — of the model, or of the reflection below — what to do about this reading."""

        if reading is None:
            return self._hold(NO_LATEST_OBSERVATION, None)
        self.observe(reading)
        if goal_in_hand(reading):
            return self._hold(GOAL_ACHIEVED, reading)
        feasible = tuple(name for name in feasible_skill_ids(reading) if name not in self.excluded)
        if not feasible:
            intent = MindIntent(
                kind=MindDecisionKind.BLOCKED,
                plan=SkillPlan(()),
                reason=NO_FEASIBLE_SKILL,
                observation_ref=observation_ref(reading),
            )
            self.last_intent = intent
            return intent

        self.intent_generation += 1
        request = DecisionRequest(
            observation_ref=observation_ref(reading),
            needs=needs_from(reading),
            active_goal=self.direction,
            feasible_skill_ids=feasible,
            persona_seed=self.persona_seed,
            budget_remaining_micro=self.ledger.remaining(),
            intent_generation=self.intent_generation,
        )
        answer = self.provider.decide(request)
        needs = needs_from(reading)
        refusal = ""
        reason = ""
        if isinstance(answer, Decision):
            # The shipped port already files this as `DECISION_OUT_OF_BOUNDS`, so the branch
            # is for a provider that answers with a `Decision` it built itself. Keeping the
            # check here means an endpoint that invents a skill gets the same conservative
            # path as one that times out, instead of a plan nobody offered.
            if answer.skill_id in feasible:
                skill, source, reason = (
                    answer.skill_id,
                    DECISION_FROM_MODEL,
                    answer.reason[:MAX_REASON_CHARS],
                )
            else:
                refusal = UnavailableReason.DECISION_OUT_OF_BOUNDS.value
                skill, source = self._reflect(feasible, needs), DECISION_FROM_LOCAL
        else:
            refusal = answer.reason.value
            skill, source = self._reflect(feasible, needs), DECISION_FROM_LOCAL
        self.last_model_refusal = refusal
        plan, built_reason = self._call_for(skill, reading)
        if plan is None:
            return self._hold(built_reason, reading)
        intent = MindIntent(
            kind=MindDecisionKind.INTENT,
            plan=plan,
            reason=reason or built_reason,
            source=source,
            intent_generation=self.intent_generation,
            observation_ref=request.observation_ref,
            model_refusal=refusal,
        )
        self.last_intent = intent
        return intent

    def record_result(
        self,
        intent: MindIntent,
        outcome: SkillOutcome,
        reading_after: WorldObservationValue | None,
    ) -> FailureCode | None:
        """File what the world said, and change the next ask if it said no.

        A confirmation clears the skill's whole retry history: a skill that worked is not one
        to keep a ledger against. A failure attributes, then either leaves the skill available
        or excludes it for the rest of the run — §3's "换方法、等待或放弃", where waiting and
        giving up arrive on their own once the feasible set empties.
        """

        self.last_result = outcome
        if outcome.result is ActionResultClass.CONFIRMED:
            for code in FailureCode:
                self.attempts.pop((intent.skill, code), None)
            self.last_failure = None
            self.observe(reading_after)
            return None
        failure = attribute_failure(outcome)
        self.last_failure = failure
        key = (intent.skill, failure)
        count = self.attempts.get(key, 0) + 1
        self.attempts[key] = count
        if count > RETRY_BUDGET_PER_SIGNATURE:
            self.excluded.add(intent.skill)
            del self.attempts[key]
        return failure

    def _reflect(self, feasible: tuple[str, ...], needs: Mapping[str, int]) -> str:
        """The order the local layer uses when no model answered.

        Finish what the inventory is short of, pick up what is already on the ground, break
        what is aimed at, otherwise look. It reads only the needs and the feasible set — the
        same two inputs a model was offered — so the fallback cannot be doing something the
        model was not permitted to. `safety` holds a Kin back from starting a break when it is
        badly hurt, because a broken trunk is not what a half-health reading is asking for.
        """

        if "select_hotbar" in feasible:
            return "select_hotbar"
        if "craft_take_result" in feasible:
            return "craft_take_result"
        if "collect_dropped" in feasible and needs.get("resource_security", 0) >= 5:
            return "collect_dropped"
        if "break_seen_block" in feasible and needs.get("safety", 0) < 7:
            return "break_seen_block"
        if "collect_dropped" in feasible:
            return "collect_dropped"
        return "turn_to"

    def _call_for(self, skill: str, reading: WorldObservationValue) -> tuple[SkillPlan | None, str]:
        """Attach one skill's arguments from this reading, or say why there is nothing to run.

        The two `None` branches guard a provider that answered with a skill the feasible set
        did not carry: the shipped providers cannot (the port judges the answer against the
        offer), but this is the boundary where an operator's endpoint speaks, and a mind that
        crashed on a bad answer would turn a provider bug into a stopped session.
        """

        if skill == "craft_take_result":
            stage = next_craft(reading)
            if stage is None:
                return None, craft_blocker(reading) or CRAFT_MATERIALS_MISSING
            return (
                SkillPlan(
                    (
                        SkillCall(
                            name="craft_take_result",
                            recipe_id=stage.recipe.recipe_id,
                            product_id=stage.product_id,
                            materials=stage.materials,
                        ),
                    )
                ),
                f"craft {stage.product_id} for {self.direction}",
            )
        if skill == "collect_dropped":
            return (
                SkillPlan((SkillCall(name="collect_dropped", item_id=SOURCE_ITEM_ID),)),
                f"collect the {SOURCE_ITEM_ID} in view",
            )
        if skill == "break_seen_block":
            if reading.aim is None or reading.aim.block is None:
                return None, "MINE_TARGET_NOT_AIMED"
            return (
                SkillPlan((SkillCall(name="break_seen_block", expected_drop_item=SOURCE_ITEM_ID),)),
                f"break the block in view for {SOURCE_ITEM_ID}",
            )
        if skill == "select_hotbar":
            slot = _goal_slot(reading)
            if slot is None:
                return None, GOAL_ACHIEVED
            return (
                SkillPlan(
                    (SkillCall(name="select_hotbar", slot=slot, expected_item_id=GOAL_PRODUCT_ID),)
                ),
                f"hold the {GOAL_PRODUCT_ID} in hand",
            )
        self.scan_step += 1
        return (
            SkillPlan(
                (
                    SkillCall(
                        name="turn_to",
                        yaw_degrees=(self.scan_step * SCAN_YAW_STEP_DEGREES) % 360.0,
                        pitch_degrees=SCAN_PITCH_DEGREES,
                    ),
                )
            ),
            "look for the next thing the milestone needs",
        )

    def _hold(self, reason: str, reading: WorldObservationValue | None) -> MindIntent:
        intent = MindIntent(
            kind=MindDecisionKind.HOLD,
            plan=SkillPlan(()),
            reason=reason,
            observation_ref="" if reading is None else observation_ref(reading),
        )
        self.last_intent = intent
        return intent

    def as_document(self) -> dict[str, object]:
        """§5's fields, with every empty one naming the source that was missing.

        Nothing is invented to fill a gap: a run that never asked a model shows its
        `model_refusal` instead of a silent zero, an intent nobody recorded shows an empty
        result rather than the previous one, and the cost block comes from the ledger, which
        is the only thing that counted the calls.
        """

        intent = self.last_intent
        result = self.last_result
        return {
            "direction": self.direction,
            "goal_met": self.goal_met,
            "current_intent": None if intent is None else intent.as_document(),
            "executing_skill": "" if intent is None else intent.skill,
            "intent_observation_ref": "" if intent is None else intent.observation_ref,
            "decision_source": "" if intent is None else intent.source,
            "last_result": "" if result is None else result.result.value,
            "last_result_reason": "" if result is None else result.reason,
            "failure_attribution": "" if self.last_failure is None else self.last_failure.value,
            "model_enabled": self.model_enabled,
            "model_refusal": self.last_model_refusal,
            "intent_generation": self.intent_generation,
            "excluded_skills": sorted(self.excluded),
            "retry_budget": RETRY_BUDGET_PER_SIGNATURE,
            "model_calls": self.ledger.calls,
            "model_spent_micro": self.ledger.spent,
            "model_cap_refusals": self.ledger.cap_refusals,
        }


def mind_for(
    provider: DecisionProvider,
    ledger: CostLedger,
    *,
    kin_id: str = "",
    persona_seed: str = "",
    model_enabled: bool = True,
) -> PlayerMind:
    """Build a mind for one session from what the session already resolved.

    A function rather than a longer argument list at the call site, because the three things
    a caller has to settle first — which provider this operator configured, what is left of
    the run cap, whose persona this is — are the same three the CLI already reads for the
    model and identity surfaces.
    """

    return PlayerMind(
        provider=provider,
        ledger=ledger,
        kin_id=kin_id,
        persona_seed=persona_seed,
        model_enabled=model_enabled,
    )
