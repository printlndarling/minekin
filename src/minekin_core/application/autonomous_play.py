"""The turn that makes a mind and a skill into a run: read, want, act once, believe the reading.

`PlayerMind` decides; `skill_plan` performs. Neither of them plays. This module is the loop
between the two — one reading, one intent, one skill, one verdict — and it exists as its own
layer because the two halves have to be able to be tested without the third: the mind is
judged on what it asks, the skills on what the readings say about a command, and what is judged
here is only whether a run keeps those two honest to each other.

Three rules the loop is built to keep:

* **One intent, one step.** An intent carries exactly one call, and the next intent is asked
  only after the world has answered. An operator-written plan can chain six skills and stop at
  the first unconfirmed step; a mind does not get to chain at all, because every link in a
  chain it invented is a step nobody re-read the world for.
* **A step needs a newer reading.** Two intents built on the same reading would be the same
  decision twice, and the second one spends the retry budget of the first. When nothing newer
  has arrived, the loop names that and ends rather than spinning.
* **Every exit is a reason.** The run document always carries the word that ended it — the
  milestone held in hand, an offer that ran out, a spend at the cap, a channel lost — because
  "the Kin stopped" has many causes and a projection that cannot tell them apart is the one
  thing a dashboard must not be.

Nothing here holds a lease, an arbiter, or a clock. The caller supplies one authority for the
whole turn, which is where the session's own authorisation lives, so the loop can be run against
a real client and against a tape with the same lines of code.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Protocol

from minekin_core.application.player_mind import (
    DECISION_PRECONDITION_CHANGED,
    NO_LATEST_OBSERVATION,
    PLAYER_DEAD,
    FailureCode,
    MindDecisionKind,
    MindIntent,
    PlayerMind,
    observation_ref,
    safety_need,
    screen_open,
)
from minekin_core.application.skill_plan import perform_skill
from minekin_core.application.world_skills import (
    CLIENT_EXITED,
    DEFAULT_STEP_TIMEOUT_NS,
    ActionAuthority,
    WorldSkills,
)
from minekin_core.domain.perception import WorldObservationValue
from minekin_core.domain.world_actions import (
    ActionResultClass,
    SkillOutcome,
    skill_capabilities,
)

#: The default stays small. Multi-stage crafting can legitimately need more than
#: 24 confirmed actions once gathering, re-aiming and GUI cleanup are counted.
#: An explicit larger budget is bounded separately; it never disables model cost,
#: skill timeout, lease expiry or cooperative cancellation.
DEFAULT_STEP_BUDGET: Final = 24
MAX_STEP_BUDGET: Final = 64


#: The loop's own three endings, beside the reasons an intent already carries.
GOAL_HELD_IN_HAND: Final = "GOAL_HELD_IN_HAND"
NO_FRESH_OBSERVATION: Final = "NO_FRESH_OBSERVATION"
STEP_BUDGET_SPENT: Final = "STEP_BUDGET_SPENT"
#: The same words the session uses when the channel goes: a loop that ended because the Bridge
#: stopped answering has to be filed under the reason a reader already knows.
CONTROL_CHANNEL_LOST: Final = "CONTROL_CHANNEL_LOST"


class ObservationSource(Protocol):
    """The readings as the loop needs them: the newest one, or nothing yet.

    `latest` is a property, the same shape `WorldObservationStore` and the skill layer
    already use. Declaring it as a method would type-check only against a test double that
    happens to define a method, and the wired session store would raise on the first read.
    """

    @property
    def latest(self) -> WorldObservationValue | None: ...

    @property
    def death_count(self) -> int: ...

    async def wait_until(
        self, predicate: Callable[[WorldObservationValue], bool], *, timeout_s: float
    ) -> WorldObservationValue | None: ...


@dataclass(frozen=True, slots=True)
class AutonomousAsk:
    """What the operator authorises before the mind has chosen anything.

    A lease is one object covering everything a run may ask for, so an autonomous run has to
    name its bounds up front: the skills it may be offered, how many steps it may take, and how
    long a step may wait for the reading that confirms it. The capability union is derived from
    the offer rather than typed, because an offer the lease does not cover is a step the arbiter
    would refuse mid-run.
    """

    skills: tuple[str, ...]
    step_budget: int
    step_seconds: float
    decision_seconds: float = 0.0

    @property
    def capabilities(self) -> frozenset[str]:
        wanted: set[str] = set()
        for name in self.skills:
            wanted |= skill_capabilities(name) or frozenset()
        return frozenset(wanted)

    @property
    def lease_seconds(self) -> float:
        """Cover each bounded decision and its following world-confirmation window."""

        return self.step_budget * (self.step_seconds + self.decision_seconds)


@dataclass(frozen=True, slots=True)
class AutonomousStep:
    """One intent, the verdict the readings gave it, and the reading that verdict was taken on."""

    intent: MindIntent
    outcome: SkillOutcome
    attribution: FailureCode | None
    result_ref: str

    def as_document(self) -> dict[str, object]:
        return {
            "intent": self.intent.as_document(),
            "result": self.outcome.result.value,
            "reason": self.outcome.reason,
            "action_id": self.outcome.action_id,
            "attribution": None if self.attribution is None else self.attribution.value,
            "result_observation_ref": self.result_ref,
            "details": dict(self.outcome.details),
        }


@dataclass(frozen=True, slots=True)
class AutonomousRun:
    """Every step one turn of the loop took, and the word that ended it."""

    steps: tuple[AutonomousStep, ...] = ()
    stop_reason: str = ""
    #: The class name of the error that ended a `CONTROL_CHANNEL_LOST` run, empty for every
    #: other stop. The channel's own end is the one fact no later reading can recover — by the
    #: time the loop notices, the witness is gone — so the loop names it as it catches it.
    stop_detail: str = ""
    mind_document: Mapping[str, object] = MappingProxyType({})

    def as_document(self) -> dict[str, object]:
        return {
            "stop_reason": self.stop_reason,
            "stop_detail": self.stop_detail,
            "steps": [step.as_document() for step in self.steps],
            "confirmed": sum(
                1 for step in self.steps if step.outcome.result is ActionResultClass.CONFIRMED
            ),
            "mind": dict(self.mind_document),
        }

    def confirmed_craft_products(self) -> frozenset[str]:
        """Which products the world confirmed were crafted this run, as product ids.

        The seed of a world-derived recipe source: feed these to
        :func:`minekin_core.domain.recipe_catalog.learned_catalog` and the coverage boundary
        reports each one as watched rather than curated. A step counts here only when the reading
        said `CONFIRMED` and the call named a `product_id` — a break or collect step carries no
        product, and an UNKNOWN craft is exactly the inconclusive click the contract forbids
        crediting. This is what a finished run can say about which crafts it saw happen; whether
        the mind's curated catalog itself is edited from it is a separate, still-open question.
        """

        products: set[str] = set()
        for step in self.steps:
            if step.outcome.result is not ActionResultClass.CONFIRMED:
                continue
            for call in step.intent.plan.calls:
                if call.product_id:
                    products.add(call.product_id)
        return frozenset(products)


def _decision_invalidation(
    *,
    mind: PlayerMind,
    intent: MindIntent,
    before: WorldObservationValue | None,
    after: WorldObservationValue | None,
    authority: ActionAuthority,
) -> str:
    if after is None:
        return "OBSERVATION_LOST"
    if after.generation != authority.generation or (
        before is not None and after.generation != before.generation
    ):
        return "WORLD_GENERATION_CHANGED"
    if not after.self_state.alive and intent.skill != "respawn":
        return PLAYER_DEAD
    if intent.skill == "respawn" and (
        after.self_state.alive or after.self_state.respawn_available is not True
    ):
        return "SKILL_PRECONDITION_CHANGED"
    if before is not None:
        previous_safety = safety_need(before)
        current_safety = safety_need(after)
        if current_safety >= 3 and current_safety > previous_safety:
            return "SAFETY_NEED_INCREASED"
    if observation_ref(
        after
    ) != intent.observation_ref and intent.skill not in mind.feasible_skills(after):
        return "SKILL_PRECONDITION_CHANGED"
    return ""


async def run_autonomous_loop(
    *,
    mind: PlayerMind,
    skills: WorldSkills,
    observations: ObservationSource,
    authority: ActionAuthority,
    step_budget: int = DEFAULT_STEP_BUDGET,
    timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    on_step: Callable[[AutonomousStep], Awaitable[None]] | None = None,
) -> AutonomousRun:
    """Play one turn of the loop: keep asking until the world or the mind says stop.

    `authority` is the run's lease, the same object the operator-written plan path hands to every
    step: the authorisation is one thing covering the whole run, and a mind that could ask for a
    fresh one per step would be a mind holding a second door around the arbiter.
    `mind.record_result` is given the newest reading rather than the one the intent was built on
    — the direction closes on what the bag looks like now, which is the only place §4 allows it
    to close.
    """

    steps: list[AutonomousStep] = []
    stop_reason = STEP_BUDGET_SPENT
    stop_detail = ""
    asked_on = ""
    for _ in range(step_budget):
        stop_reason = STEP_BUDGET_SPENT
        reading = observations.latest
        if (
            reading is not None
            and not reading.self_state.alive
            and reading.self_state.respawn_available is False
            and skills.supports_respawn
        ):
            # Vanilla briefly disables its death-screen buttons. Wait only for a
            # newer visible affordance, within the existing step timeout and lease.
            await observations.wait_until(
                lambda latest: (
                    latest.generation != authority.generation
                    or latest.self_state.alive
                    or latest.self_state.respawn_available is True
                ),
                timeout_s=min(timeout_ns / 1_000_000_000, 2.0),
            )
            reading = observations.latest
        if reading is not None and reading.generation != authority.generation:
            mind.observe(reading)
            stop_reason = DECISION_PRECONDITION_CHANGED
            stop_detail = "WORLD_GENERATION_CHANGED"
            break
        death_count = observations.death_count
        current_ref = "" if reading is None else observation_ref(reading)
        if steps and current_ref == asked_on:
            stop_reason = NO_FRESH_OBSERVATION
            break
        # The model call is a blocking socket round-trip (see adapters/model/openai_compatible),
        # so it goes to a worker thread: run here on the loop, a real endpoint would freeze the
        # event loop for its full `timeout_ms`, starving the IPC reader and the stop-request
        # watcher alike — which is how a cooperative release became a forced SIGTERM (exit 143).
        intent = await asyncio.to_thread(mind.next_intent, reading)
        if intent.kind is not MindDecisionKind.INTENT:
            current = observations.latest
            mind.observe(current)
            if observations.death_count != death_count or (
                current is not None and not current.self_state.alive
            ):
                stop_reason = PLAYER_DEAD
            elif current is None:
                stop_reason = NO_LATEST_OBSERVATION
            elif current.generation != authority.generation:
                stop_reason = DECISION_PRECONDITION_CHANGED
                stop_detail = "WORLD_GENERATION_CHANGED"
            else:
                stop_reason = intent.reason
            break
        # The ask is stamped, not the answer: the next turn may not be built on the reading this
        # intent already used, which is what makes a stalled world a named stop instead of a
        # retry loop that spends the mind's budget on one unchanged moment.
        asked_on = intent.observation_ref
        try:
            latest = observations.latest
            invalidation = _decision_invalidation(
                mind=mind,
                intent=intent,
                before=reading,
                after=latest,
                authority=authority,
            )
            if observations.death_count != death_count:
                invalidation = PLAYER_DEAD
            if invalidation:
                # A remote decision can outlive the screen or bag it was asked about.
                # Recheck the current offer without rejecting mere advancing ticks.
                outcome = SkillOutcome(
                    result=ActionResultClass.INTERRUPTED,
                    reason=DECISION_PRECONDITION_CHANGED,
                    action_id="",
                    pre_tick=None if reading is None else reading.game_tick,
                    post_tick=None if latest is None else latest.game_tick,
                    details={"invalidated_by": invalidation},
                )
            else:
                outcome = await perform_skill(
                    skills,
                    intent.plan.calls[0],
                    authority=authority,
                    timeout_ns=timeout_ns,
                )
        except (OSError, RuntimeError) as error:
            stop_reason = CONTROL_CHANNEL_LOST
            stop_detail = type(error).__name__
            break
        after = observations.latest
        attribution = mind.record_result(intent, outcome, after)
        result_ref = "" if after is None else observation_ref(after)
        steps.append(AutonomousStep(intent, outcome, attribution, result_ref))
        if on_step is not None:
            # Reported as it lands rather than when the run ends: the question a reader
            # watching a long run asks is what the Kin is doing *now*, and the answer has
            # to be on the ledger before the next step's reading replaces it.
            await on_step(steps[-1])
        # Reporting can yield to the reader. Keep the step's original result
        # attribution, but conclude the run from the body's current observation.
        current = observations.latest
        mind.observe(current)
        if intent.skill == "respawn" and outcome.result is not ActionResultClass.CONFIRMED:
            stop_reason = outcome.reason or "RESPAWN_NOT_CONFIRMED"
            break
        if outcome.reason == CLIENT_EXITED:
            # The step is on the ledger with the exit code, and no step after it can be
            # concluded either: the client that would have answered it is the process
            # that just went. Spending the mind's budget asking a dead JVM for readings
            # would look, on the document, like a mind that kept trying.
            stop_reason = CLIENT_EXITED
            stop_detail = outcome.details.get("exit_code", "")
            break
        if (
            outcome.reason == PLAYER_DEAD
            or observations.death_count != death_count
            or (current is not None and not current.self_state.alive)
        ):
            stop_reason = PLAYER_DEAD
            if (
                current is not None
                and not current.self_state.alive
                and current.self_state.respawn_available is not None
                and skills.supports_respawn
                and intent.skill != "respawn"
            ):
                continue
            break
        if current is None:
            stop_reason = NO_LATEST_OBSERVATION
            break
        if (
            outcome.details.get("invalidated_by") == "WORLD_GENERATION_CHANGED"
            or current.generation != authority.generation
        ):
            stop_reason = DECISION_PRECONDITION_CHANGED
            stop_detail = "WORLD_GENERATION_CHANGED"
            break
        if mind.holds_goal(current) and not screen_open(current):
            stop_reason = GOAL_HELD_IN_HAND
            break
    return AutonomousRun(
        tuple(steps), stop_reason, stop_detail, MappingProxyType(mind.as_document())
    )
