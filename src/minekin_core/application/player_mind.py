"""What the Kin wants, what it is therefore allowed to try, and what the world said back.

This is §3 of `docs/s3-minimal-player-mind.md`: one standing milestone, one current intent, two
needs read from player-equivalent observation, and failure attribution that changes the next ask
rather than repeating it. It contains no keystrokes. A decision becomes a `SkillPlan` and the S2
seam (`application.skill_plan`) is what runs it, because "the mind chose it" and "it happened" are
two different claims and only the second is worth a log line.

**The milestone is an argument, not a constant.** This module used to name a wooden pickaxe and
derive its build order at import time, which made the goal a second source of truth about what the
Kin is for and made a new product a code change. It now takes a `domain.goal_spec.Milestone` — a
product id, a quantity, the raw item it is built from — from whoever builds the mind, and holds no
default of its own. `None` is a supported milestone: a Kin with no standing craft target still
breaks what it is aimed at, picks up what it sees and looks around, and a remote answerer may still
ask it for a craft, which this side resolves and judges exactly as it judges one the standing
milestone implied. Every function here is therefore written against a product it was handed.

**The ask is data, and this layer is the only reader of it.** `domain.skill_parameters` declares
what a behavior takes and what a legal value is; `domain.model_access.compose_decision` refuses an
answer that does not match; `domain.recipe_catalog` answers what a product costs; the reading
decides whether the bag can pay; and a later reading decides whether it happened. What the mind
does with an argument is turn one ask into one call — `_call_for` is the single place where a
`target_item` becomes a `recipe_id` and a `materials` map, so no parameter has two readers that
could disagree about it. The `DecisionRequest` also carries `observation_summary`, built here from
the newest reading, because an answerer asked to choose a product has to be shown what the Kin
holds; the summary names items and counts and no coordinates, and it is the same reading the
precondition checks run against.

The provider is a structural protocol declared here rather than imported from
`adapters/model`: the frozen dependency direction forbids this layer from naming an adapter, and a
one-method port is exactly the kind of seam both sides should describe alone.

Who decides is a policy the operator selects, never something inherited from whether a model
happens to be reachable. Under `DecisionPolicy.MODEL` — the default — every ordinary step is the
model's: a timeout, a missing credential, a spent cap, or an answer this side refuses is a named
stop with the reason kept, never a silent switch to the rule order below. The one thing that
still moves without a decision is the bounded step out of damage being taken now
(`_imminent_protection`); death, hunger and combat are conditions the deciding layer owns, not
reflexes. Under the explicitly selected `DecisionPolicy.RULES` — the offline strategy the old
demos run on — the order in `_reflect` decides every step and no provider is consulted; those
runs report a decision source of `local_reflection` in every projection, so nobody reading the
dashboard can mistake a deterministic order for a model.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Protocol

from minekin_core.application.skill_plan import (
    SKILL_ARGUMENT_MISSING,
    SKILL_UNKNOWN,
    SkillPlan,
)
from minekin_core.application.world_skills import (
    FIGHT_MIN_HEALTH,
    RETREAT_FLEE_SECONDS,
    SkillCall,
)
from minekin_core.domain.danger_catalog import (
    ATTACK_REACH_BLOCKS,
    attackable_hostile,
    nearest_hostile,
)
from minekin_core.domain.daylight import time_of_day
from minekin_core.domain.decision_policy import DecisionPolicy
from minekin_core.domain.goal_spec import Milestone
from minekin_core.domain.model_access import (
    MAX_REASON_CHARS,
    CostLedger,
    Decision,
    DecisionRequest,
    ModelUnavailable,
    UnavailableReason,
)
from minekin_core.domain.perception import EntityCandidate, WorldObservationValue
from minekin_core.domain.persona import PersonaManifest
from minekin_core.domain.recipe_catalog import (
    CRAFT_GRID_TOO_SMALL,
    CRAFT_MATERIALS_MISSING,
    CRAFT_RECIPE_UNAVAILABLE,
    PLAYER_GRID_SIDE,
    RECIPES,
    BuildStep,
    OwedStep,
    Recipe,
    build_plan,
    grid_enabler_for,
    largest_grid_in_plan,
    plan_needs_larger_grid,
)
from minekin_core.domain.skill_parameters import (
    BEHAVIOR_PARAMETERS,
    HOTBAR_SLOT_COUNT,
    MAX_QUANTITY,
    validate_arguments,
)
from minekin_core.domain.visible_entities import (
    SUMMARY_ENTITY_LIMIT,
    nearest_visible,
    rendered_entities,
)
from minekin_core.domain.world_actions import (
    CONSUME_REFUSAL_REASONS,
    ActionRefusal,
    ActionResultClass,
    SkillOutcome,
    angle_to_degrees,
    consume_candidate,
    consume_item_refusal,
    item_total,
    reachable_food_items,
    reachable_weapons,
    use_target_refusal,
    use_target_signature,
)


class CraftKnowledge(Protocol):
    """Version knowledge can propose a payable batch, or the first owed step toward a bigger
    one, and never grant input authority."""

    def knows_product(self, product_id: str) -> bool: ...

    def available(
        self, reading: WorldObservationValue, *, grid_side: int
    ) -> Mapping[str, Recipe]: ...

    def refusal_for(
        self, product_id: str, reading: WorldObservationValue, *, grid_side: int
    ) -> str: ...

    def step_toward(
        self,
        product_id: str,
        reading: WorldObservationValue,
        *,
        quantity: int = 1,
        grid_side: int,
        preferred: tuple[str, ...] = (),
    ) -> BuildStep | str: ...

    def owed_chain(
        self,
        product_id: str,
        reading: WorldObservationValue,
        *,
        quantity: int = 1,
        grid_side: int,
        preferred: tuple[str, ...] = (),
    ) -> tuple[OwedStep, ...] | str: ...

    def enabler_to_stand_up(
        self,
        product_id: str,
        reading: WorldObservationValue,
        *,
        quantity: int = 1,
        grid_side: int,
        preferred: tuple[str, ...] = (),
    ) -> tuple[Recipe, int] | None: ...

    def missing_raw(
        self,
        product_id: str,
        reading: WorldObservationValue,
        *,
        quantity: int = 1,
        grid_side: int,
        preferred: tuple[str, ...] = (),
    ) -> Mapping[str, int]: ...

    def as_document(self) -> dict[str, object]: ...


#: How many times one skill may fail the same way before the mind stops calling it that
#: way. Two is a retry and a second attempt; a third identical failure against the same
#: world state is a different problem, and replaying the click is what §3 forbids.
RETRY_BUDGET_PER_SIGNATURE: Final = 2

#: The heading a scan turns to between intents. The pitch is swept, not fixed: a single
#: near-horizon angle only ever catches a trunk a few blocks ahead, and it can never look
#: down far enough to land on the block directly under the player — which is the face a
#: placement needs and the reason a Kin holding a table stalled with no `use_target` to make.
#: Steep in both directions so one of them is "down" whatever way the client counts it, and
#: stepping the ask rather than repeating `-18` also keeps a signature's retry budget from
#: collapsing on an identical turn.
SCAN_YAW_STEP_DEGREES: Final = 45.0
SCAN_PITCH_CYCLE_DEGREES: Final = (-18.0, 55.0, -55.0)

#: The scan's phase drift: every complete 8-heading circle shifts the next circle by this much.
#: Without it the scan is exactly periodic in 24 steps (8 headings x 3 pitches) — a live run
#: died, respawned, and then swept that same 24-step cycle for 23 turns without ever landing a
#: heading within half a block of a trunk three blocks away (a log there subtends ±9.5°, and a
#: 45° grid can sit up to 22.5° off), so the identical miss repeated forever. The drift visits
#: the 45° grid, then the 15° midpoints, then the 30° midpoints: 24 headings covering every
#: multiple of 15° exactly once before the cycle repeats — the crosshair is guaranteed to sweep
#: a ≥1-block-wide target within ~3.8 blocks (half-width ≥ 7.5°).
SCAN_YAW_DRIFT_DEGREES: Final = 15.0

#: The pitch ladder a resource re-aim sweeps while it holds the trunk's recalled heading is
#: computed per reading by `PlayerMind._reacquire_probe` — one and two cells' worth of angle at
#: the distance the reading reports (`0, ±Δ, ±2Δ`, `Δ = atan(1/d)`). An earlier fixed ladder
#: (0, ±30, ±55, ±85) was measured against a column at three blocks, where its standing members
#: sit ±16..20° from a remembered cell: none of the fixed probes hit them, and a live run turned
#: away from a trunk with a usable log still standing in it. The ladder stays the same kind of
#: look the blind scan issues — a bounded set of pitches pinned to a heading the crosshair
#: reported, NOT a neighbouring cell's coordinates, so which block (if any) each probe reveals
#: stays the client's word and not the mind's inference.

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
#: A hotbar ask whose named expectation the reading contradicts: the ask is inapplicable as
#: written and is refused by its own name — never answered with another slot or another item.
SELECT_ITEM_NOT_IN_SLOT: Final = "SELECT_ITEM_NOT_IN_SLOT"

PLAYER_DEAD: Final = "PLAYER_DEAD"
DECISION_PRECONDITION_CHANGED: Final = "DECISION_PRECONDITION_CHANGED"
DECISION_FROM_MODEL: Final = "model"
DECISION_FROM_LOCAL: Final = "local_reflection"


#: Which refusal words mean which of §3's four attributions. Anything unlisted lands in
#: `ACTION_NOT_EFFECTIVE`: the four codes are deliberately coarse, and the skill's own
#: `reason` is kept beside the code so the distinction a fix needs is never lost.
#: A grid that cannot hold the shape is `SKILL_NOT_IMPLEMENTED` rather than a missing
#: resource: more wood would not move it, and the thing that is absent is a skill for the
#: screen the recipe needs. A product the table has no row for is absent in the same way —
#: no reading makes it craftable, and the missing thing is curated knowledge, not material.
#: The consume refusals split the same way: a food the curated table has no row for is
#: missing knowledge, while a short bag, a full hunger bar, a bag-only stack and a
#: crosshair on something are all facts a later reading can answer differently.
_NOT_IMPLEMENTED_REASONS: Final = frozenset(
    {
        SKILL_UNKNOWN,
        SKILL_ARGUMENT_MISSING,
        CRAFT_GRID_TOO_SMALL,
        CRAFT_RECIPE_UNAVAILABLE,
        ActionRefusal.CONSUME_ITEM_NOT_KNOWN_FOOD.value,
    }
)
_UNREADABLE_REASONS: Final = frozenset({NO_LATEST_OBSERVATION, NO_CONFIRMING_OBSERVATION})
_ABSENT_REASONS: Final = frozenset(
    {
        "NO_SEEN_DROP",
        CRAFT_MATERIALS_MISSING,
        "MINE_TARGET_NOT_AIMED",
        ActionRefusal.CONSUME_ITEM_MISSING.value,
        ActionRefusal.CONSUME_ITEM_NOT_IN_HOTBAR.value,
        ActionRefusal.CONSUME_NOT_HUNGRY.value,
        ActionRefusal.CONSUME_AIM_NOT_CLEAR.value,
    }
)

#: Which named preconditions the world can still undo. The two sets decide what a refusal
#: costs the skill, and the line is drawn by whether a later reading could answer differently:
#: a short bag can be filled, so charging the craft skill for `CRAFT_MATERIALS_MISSING` would
#: exclude the very skill the gathered wood was going to be spent on — the Kin is sent to the
#: trunk and then told it may never craft. The other two are facts about the screen and the
#: table; replaying the same click is what §3 forbids, so the first word takes the skill off
#: the offer for the rest of the run.
#:
#: A reroute name spends no budget at all, which is honest about what bounds it: a mind whose
#: reading keeps paying for a craft the skill keeps refusing is stopped by the run's own step
#: budget, not by this one. The name going into the document is what makes that loop visible
#: instead of merely finite. Every consume refusal reroutes for the same reading of the rule:
#: what it refused was one candidate — this bag, this bar, this aim — and a later frame (or a
#: later answer) may name a different one, so excluding the whole skill would forbid the meal
#: that is one reading away.
_PRECONDITION_REROUTE: Final = (
    frozenset({CRAFT_MATERIALS_MISSING, DECISION_PRECONDITION_CHANGED, PLAYER_DEAD})
    | CONSUME_REFUSAL_REASONS
)
_PRECONDITION_DEAD_END: Final = frozenset({CRAFT_GRID_TOO_SMALL, CRAFT_RECIPE_UNAVAILABLE})


def _checked_offer(offer: tuple[str, ...]) -> tuple[str, ...]:
    """The offer, after the check that makes it the same list the arguments are judged from.

    A skill can only be offered if `domain.skill_parameters` declares what it takes: an answerer
    given a name with no declaration would be asked to fill in a shape nobody can check, and the
    refusal it came back with would be this build's fault rather than the endpoint's.
    """

    missing = sorted(name for name in offer if name not in BEHAVIOR_PARAMETERS)
    if missing:
        raise LookupError(f"offered skills with no declared parameters: {', '.join(missing)}")
    return offer


#: The order the feasible set is reported in, and so the order a scan of it reads. Listed once here
#: because a model's offer and the rule order have to be the same list, not two lists that
#: happen to agree today. `close_screen` is deliberately absent from this standing list: it is the
#: one skill whose every reading is already a success *when no window is standing*, so offering it
#: then would invite a step spent to change nothing. It is offered in exactly the one case where a
#: step it takes does change the world — a container open on the client — which `feasible_skill_ids`
#: detects off the newest reading rather than from this list.
SKILL_OFFER: Final = _checked_offer(
    (
        "break_seen_block",
        "collect_dropped",
        "consume_item",
        "fight_back",
        "respawn",
        "retreat",
        "approach_entity",
        "look_at_entity",
        "trade",
        "craft_take_result",
        "select_hotbar",
        "use_target",
        "turn_to",
    )
)

#: The skills the mind does not START while a threat is on it (see `PlayerMind._threat`) —
#: the swings, the blind walks to drops and the screen work are the steps a night slime
#: killed the Kin in (run-89, nine `Kin was slain by Slime`). What remains is honest: face
#: the threat, eat, close a screen already open, respawn. Suppression withholds starts, not
#: finishes: a close_screen or consume already in flight is not this filter's business.
DANGER_SUPPRESSED: Final = frozenset(
    {
        "break_seen_block",
        "collect_dropped",
        "craft_take_result",
        "select_hotbar",
        "use_target",
    }
)

#: The one skill that ends a standing window, and so the only world step worth leaving it for.
#: Named once so the feasible set, the local reflection and the call builder agree on it.
CLOSE_SCREEN: Final = "close_screen"

#: The screen-handler id the 1.20.1 client reports while a placed crafting table's window is
#: open, and the grid that window holds. This is read off the observation rather than assumed:
#: the player's own inventory reports an empty `screen_id` with handler id 0 (see `screen_open`),
#: while the table opens a real, typed `CraftingScreenHandler` the Bridge names
#: `minecraft:crafting`. A non-empty id paired with a live handler is therefore the only reading
#: that can say the Kin is standing inside a three-by-three — and
#: `recipe_catalog.PLAYER_GRID_SIDE` is the honest two-by-two default for every other screen.
#: Nothing here opens that window; this is the reading's answer to "what grid can the next click
#: fill", which the offer and the craft precondition both consult.
CRAFTING_TABLE_SCREEN_ID: Final = "minecraft:crafting"
CRAFTING_TABLE_GRID_SIDE: Final = 3


def screen_open(reading: WorldObservationValue) -> bool:
    """Whether this reading says a container is standing on the client.

    The one fact that distinguishes 'nothing is open' from 'my inventory is' is a handler id, not a
    screen name: the live client reports the player's own crafting window with an empty screen id
    while still giving its handler an id (see `world_skills._window_sync_id`), and `0` is a legal
    handler id for the player inventory, so its absence — not its value — is the only reading that
    can say there is no window. The skill layer closes on the same test, so the mind that decides
    *whether* to leave and the skill that leaves cannot disagree about whether there was anything to
    leave.
    """

    return reading.gui is not None and reading.gui.sync_id is not None


def crafting_grid_side(reading: WorldObservationValue) -> int:
    """The side of the crafting grid this reading says the Kin is standing inside.

    Two for every screen but the crafting table's — the inventory grid the craft skills open
    themselves, and the outside world where no window is up yet. Three the moment the client names a
    typed `minecraft:crafting` handler with a live id, because that placed table is the only screen
    this build can reach that holds a three-by-three shape. A shape's precondition is judged against
    the screen that is actually open rather than against a constant, which is why
    `CRAFT_GRID_TOO_SMALL` can stop being a permanent dead end: it is only true while no table
    window is standing, and a later reading that opens one answers it differently. Reading the size
    is not opening it — reaching this state is the general use key's job, and nothing here assumes
    it.
    """

    gui = reading.gui
    if gui is not None and gui.sync_id is not None and gui.screen_id == CRAFTING_TABLE_SCREEN_ID:
        return CRAFTING_TABLE_GRID_SIDE
    return PLAYER_GRID_SIDE


def owed_steps(
    reading: WorldObservationValue,
    product_id: str,
    quantity: int = 1,
    *,
    grid_side: int | None = None,
) -> tuple[BuildStep, ...] | str:
    """The steps still outstanding for one product on this reading, in build order.

    The plan is the catalog's and the credit is the reading's: the inventory is handed to
    `build_plan`, so a step is listed only while the bag holds less of its product than the ask
    consumes. That is what closes an ask from a reading rather than from a decision — a bag holding
    the product owes nothing, including the ingredients that already went into it, which no fixed
    shopping list could tell from the same inventory.

    `grid_side` is forwarded to `build_plan` and, when handed over, makes the plan reserve a
    grid-enabler (a crafting table) as its own owed step so a wider shape has something to be laid
    out in. Left unset the plan is purely about ingredients, which is what a surface that describes
    a goal rather than acts on it wants — the act path (`step_to_run`, `blocker_for`) passes the
    side it is working in so the enabler's cost is charged before the terminal craft.
    """

    planned = build_plan(
        product_id, quantity=quantity, inventory=reading.inventory, grid_side=grid_side
    )
    if isinstance(planned, str):
        return planned
    return tuple(step for step in planned if step.required_total > 0)


def step_to_run(
    reading: WorldObservationValue,
    product_id: str,
    quantity: int = 1,
    *,
    grid_side: int = PLAYER_GRID_SIDE,
) -> BuildStep | None:
    """The first step still owed whose shape the screen being opened can hold and whose materials
    this bag can pay for.

    Strictly in build order, and a step is only returned when its materials are already in the
    bag: the precondition check the contract asks for happens here, before a command is built, so
    a craft that cannot be honoured is never sent. The grid is checked in the same place for the
    same reason — a three-by-three shape clicked into the inventory's two-by-two is a command the
    world can only shrug at, and a `CONFIRMED` verdict belongs to crafts that could have happened.

    The ask may name the product at the end of the chain while the step that runs now is one of its
    ingredients' crafts. That is not a substitution: it is what an order means, and the run
    document says which step it ran and which ask it was running toward.
    """

    needed = owed_steps(reading, product_id, quantity, grid_side=grid_side)
    if isinstance(needed, str):
        return None
    craftable: frozenset[str] = (
        reading.gui.craftable_recipe_ids if reading.gui is not None else frozenset()
    )
    for step in needed:
        if step.recipe.recipe_id in craftable:
            # The client attests this recipe is craftable in the screen it is standing in — the
            # grid shape and the bag both pay, read from the world's recipe book rather than
            # inferred from the curated table. This only ever names a step runnable; an empty or
            # absent report (no screen open, or a Bridge that does not yet surface the book)
            # falls through to the curated checks below, so behaviour is unchanged until the
            # world actually speaks.
            return step
        if not step.recipe.fits(grid_side):
            continue
        affordable = all(
            item_total(reading.inventory, item_id) >= count for item_id, count in step.materials
        )
        if affordable:
            return step
    return None


def blocker_for(
    reading: WorldObservationValue,
    product_id: str,
    quantity: int = 1,
    *,
    grid_side: int = PLAYER_GRID_SIDE,
) -> str:
    """Why no craft can run toward this ask on this reading, named by the precondition, or empty.

    The distinction is not decoration: `CRAFT_MATERIALS_MISSING` sends the Kin back to the resource,
    and `CRAFT_GRID_TOO_SMALL` says the ask needs a screen this build has no skill for. A mind that
    got the first word for the second fact would gather wood it already has enough of until the
    harness stopped it. `GOAL_ACHIEVED` is the empty answer for an ask the bag already satisfies,
    and the caller turns that into a hold rather than a click that would waste materials.
    """

    if step_to_run(reading, product_id, quantity, grid_side=grid_side) is not None:
        return ""
    needed = owed_steps(reading, product_id, quantity, grid_side=grid_side)
    if isinstance(needed, str):
        return needed
    if not needed:
        return GOAL_ACHIEVED
    if any(step.recipe.fits(grid_side) for step in needed):
        return CRAFT_MATERIALS_MISSING
    return CRAFT_GRID_TOO_SMALL


def craft_options(
    reading: WorldObservationValue, *, grid_side: int = PLAYER_GRID_SIDE
) -> tuple[str, ...]:
    """Which products in the curated table this bag could be moving toward right now.

    Read out of the table rather than from a list of items this module knows, so a new curated row
    is a new option here without a line of code changing and an item nobody has curated is absent
    because it is absent — not because somebody deleted a name. This is what makes an ask checkable
    in the operator's own terms: it is the list the answerer is shown, and it is the same list the
    precondition is judged from.
    """

    return tuple(
        product_id
        for product_id in RECIPES
        if step_to_run(reading, product_id, grid_side=grid_side) is not None
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


def goal_held(milestone: Milestone | None, reading: WorldObservationValue) -> bool:
    """Whether a reading says the standing milestone is met. No milestone, nothing met."""

    return (
        reading.self_state.alive
        and milestone is not None
        and milestone.held(reading) >= milestone.quantity
    )


def goal_slot(milestone: Milestone | None, reading: WorldObservationValue) -> int | None:
    if milestone is None:
        return None
    for stack in reading.inventory.stacks:
        if stack.item_id == milestone.product_id:
            return stack.slot
    return None


def goal_in_hand(milestone: Milestone | None, reading: WorldObservationValue) -> bool:
    """Whether the milestone quantity is held and its item is selected.

    The direction is *hold* the thing, not obtain it once, so "in hand" is the condition that ends
    a run rather than "in the bag somewhere". An unread `selected_slot` counts as not in hand: the
    ask that follows is the cheap one, and it is filed against a reading that did not say the item
    was already held.
    """

    if milestone is None or not goal_held(milestone, reading):
        return False
    return any(
        stack.item_id == milestone.product_id and stack.slot == reading.self_state.selected_slot
        for stack in reading.inventory.stacks
    )


def enabler_to_stand_up(
    milestone: Milestone | None,
    reading: WorldObservationValue,
    *,
    grid_side: int = PLAYER_GRID_SIDE,
) -> tuple[Recipe, int] | None:
    """The held grid-enabler a still-unmet milestone needs stood up, with its slot, or `None`.

    A milestone whose plan reserves a wider-grid enabler (a crafting table) reaches its
    three-by-three shape by placing and opening that item, not by crafting it again — the craft
    is what `step_to_run` already returns while the item is missing. Once it is crafted and in
    the bag while the goal product is not, this names the held recipe so the general
    select-then-use path can bring it to hand, place it, and open the window the terminal craft
    needs. Everything is read off `Recipe.opens_grid_side` via `grid_enabler_for` and the plan's
    own largest shape the current grid cannot hold — no product name is hardcoded and no per-item
    chain is written, so a newly curated wider grid becomes reachable by adding a catalog row.
    `None` when there is no milestone, when the goal is already met, when nothing is owed above
    the current grid (a wide window is up, or the plan fits), when this table knows no enabler
    for that shape, or when the enabler is not yet held — the last is the crafting step, not a
    placement.
    """

    if milestone is None or goal_held(milestone, reading):
        return None
    owed = owed_steps(reading, milestone.product_id, milestone.quantity, grid_side=grid_side)
    if isinstance(owed, str) or not owed:
        return None
    needed_side = largest_grid_in_plan(owed)
    if needed_side <= grid_side:
        return None
    enabler = grid_enabler_for(needed_side, within_side=grid_side)
    if enabler is None:
        return None
    for stack in reading.inventory.stacks:
        if stack.item_id == enabler.product_id:
            return (enabler, stack.slot)
    return None


def select_target(
    milestone: Milestone | None,
    reading: WorldObservationValue,
    *,
    grid_side: int = PLAYER_GRID_SIDE,
) -> tuple[str, int] | None:
    """Which item to bring to hand now, and its slot — the goal itself, then a held enabler.

    The `hold` direction ends when the goal product is in the selected slot, so that is the first
    thing select is for. But a milestone that still owes a wider-grid craft gets there by standing
    a table up, and that needs the table in hand before the use key can place it; with the goal
    not yet held and the enabler held but not selected, the enabler is what select should reach
    for. `None` when there is nothing to switch to — no milestone, the goal already in hand, or the
    enabler already selected (so the use key, not another number key, is the step).
    """

    if milestone is None:
        return None
    if goal_held(milestone, reading) and not goal_in_hand(milestone, reading):
        slot = goal_slot(milestone, reading)
        if slot is not None:
            return (milestone.product_id, slot)
    enabler = enabler_to_stand_up(milestone, reading, grid_side=grid_side)
    if enabler is not None and enabler[1] != reading.self_state.selected_slot:
        return (enabler[0].product_id, enabler[1])
    return None


def hotbar_choice_available(reading: WorldObservationValue) -> bool:
    """Whether the reading shows any of the nine HUD slots holding something.

    The generic half of the selection offer: the number keys address those nine slots
    whatever the standing goal, so a valid choice exists whenever one of them carries an
    item — independent of any gather target. Whether to select, and which slot, is the
    deciding layer's call; this only says the slots are there.
    """

    return any(0 <= stack.slot < HOTBAR_SLOT_COUNT for stack in reading.inventory.stacks)


def shortfalls(
    milestone: Milestone | None, reading: WorldObservationValue
) -> tuple[BuildStep, ...] | str:
    """The steps the standing milestone still owes on this reading, in build order.

    A view of `owed_steps` with the milestone's own product and quantity; no milestone owes
    nothing, which is the same answer an ask already satisfied gives.
    """

    if milestone is None:
        return ()
    return owed_steps(reading, milestone.product_id, milestone.quantity)


def next_craft(
    milestone: Milestone | None,
    reading: WorldObservationValue,
    *,
    grid_side: int = PLAYER_GRID_SIDE,
) -> BuildStep | None:
    """The step the standing milestone can run now, or `None`.

    A view of `step_to_run` for the milestone's product; the ask itself is what decides which
    product that is, and a model's ask is answered in `_call_for` rather than here.
    """

    if milestone is None:
        return None
    return step_to_run(reading, milestone.product_id, milestone.quantity, grid_side=grid_side)


def craft_blocker(
    milestone: Milestone | None,
    reading: WorldObservationValue,
    *,
    grid_side: int = PLAYER_GRID_SIDE,
) -> str:
    """Why the standing milestone cannot be advanced by a craft on this reading, or empty.

    `GOAL_ACHIEVED` is mapped back to empty here and only here: the milestone view answers "is
    there an obstacle", and a met milestone is not an obstacle. An ask keeps the name, because the
    question an ask answers is why nothing ran, and "this bag already has four of them" is the
    answer.
    """

    if milestone is None:
        return ""
    blocker = blocker_for(reading, milestone.product_id, milestone.quantity, grid_side=grid_side)
    return "" if blocker == GOAL_ACHIEVED else blocker


def consume_offerable(reading: WorldObservationValue) -> bool:
    """Whether this reading supports a meal right now.

    Two questions asked of one reading, on purpose: is there a curated food the hotbar
    can reach (`consume_candidate`), and does the skill's own precondition admit it here
    (`consume_item_refusal`) — a full hunger bar, a crosshair resting on something, or a
    stack only the wider bag holds each take the offer away, and the asker then reaches
    for a turn or a gather instead of a meal that cannot happen. An offer computed from
    an older frame would be a model choosing inside a set the skill is about to refuse,
    so both halves are judged against the same reading the skill will see.
    """

    candidate = consume_candidate(reading)
    return candidate is not None and consume_item_refusal(reading, candidate).accepted


def feasible_skill_ids(
    milestone: Milestone | None, reading: WorldObservationValue
) -> tuple[str, ...]:
    """What this reading supports — the only set a model gets to choose inside.

    `turn_to` is offered whenever there is a reading at all, because it is the conservative
    action: it changes what is in view without spending a resource or leaving a block broken
    halfway. A mind with nothing else to do looks around rather than stalls.

    `craft_take_result` is offered on the table's own answer — whether some curated product has a
    step this bag can pay for — and not on the milestone's, which is what lets an ask that came
    from an answerer be honoured in a session that has no standing goal at all. `collect_dropped`
    is offered for any dropped item in view, not only for one the milestone names, for the same
    reason: the ask chooses among what the summary shows, and this side only judges whether the
    world could carry it out. `use_target` is offered on the skill's own precondition — it fires
    the use key on whatever the crosshair reports, so a placement against a block and the opening
    of a standing table or door are one step here, and only a `MISS`/`UNREAD` aim is not. The mind
    does not guess a target the client never rendered, and it is never offered while a window holds
    the input. This is how a goal whose last craft needs a three-by-three reaches that shape by
    general means: select the table, aim the ground, use to place it, aim the table, use to open it,
    then the recipe click the open window now carries — not a per-product chain.

    A standing container rewrites most of the offer. The crosshair and hot-bar skills this build
    sends to the world — the break, the walk to a drop, the turn, the number key — all act through
    inputs a window has taken: the same click that would break a block becomes the `GUI_CONFLICT`
    that leaves the Kin inside a window holding the keyboard, and the observation stream that goes
    quiet afterwards is the run reading its way into a `CLIENT_EXITED`. So the world actions drop
    out while a handler is up, and leaving it is always offered. But a container is the one screen
    the recipe click runs *through*, so `craft_take_result` stays offered whenever the table's
    answer for the grid this open window holds says a step is payable — which is how a
    three-by-three shape gets crafted inside the very window it needs, rather than only ever being
    refused against the inventory's two-by-two. Once the handler is gone the next reading opens the
    world set again — the contract's "close the screen when needed, then allow world actions" as a
    decision rather than a hardcoded tail on the craft.
    """

    if not reading.self_state.alive:
        return ("respawn",) if reading.self_state.respawn_available is True else ()
    if screen_open(reading):
        if goal_in_hand(milestone, reading):
            return (CLOSE_SCREEN,)
        offer = [CLOSE_SCREEN]
        if craft_options(reading, grid_side=crafting_grid_side(reading)):
            offer.append("craft_take_result")
        # An open merchant's offer list is what a trade choice is made between; whether to
        # take one (and WHICH) is the deciding layer's judgement, this side only says the
        # rows are there.
        if reading.gui is not None and reading.gui.trade_offers:
            offer.append("trade")
        return tuple(offer)
    feasible = {
        "break_seen_block" if reading.aim is not None and reading.aim.block is not None else "",
        "collect_dropped" if _nearest_drop(reading) is not None else "",
        "consume_item" if consume_offerable(reading) else "",
        # Offered for ANY rendered body in sight inside attack reach -- the game's type id
        # is shown, and what the body means (kill it? it is a slime; leave it? it is a pig;
        # hit it anyway? the model may say so) is the deciding layer's judgement. Only the
        # reach bound is this side's: a swing further out cannot land, and a swing at
        # nothing is the stand-still step the night soaks died in.
        "fight_back"
        if reading.self_state.alive
        and not screen_open(reading)
        and nearest_visible(reading, within=ATTACK_REACH_BLOCKS) is not None
        else "",
        # Facing any rendered body in sight: the leg every entity interaction starts from,
        # offered generically for the same reason the fight is -- the meaning is the call.
        "look_at_entity"
        if reading.self_state.alive and not screen_open(reading) and nearest_visible(reading)
        else "",
        # Walking to a rendered body, offered beside the look for the same reason: any
        # visible body can be gone to, and whether it is worth going to is the call.
        "approach_entity"
        if reading.self_state.alive and not screen_open(reading) and nearest_visible(reading)
        else "",
        "craft_take_result"
        if craft_options(reading, grid_side=crafting_grid_side(reading))
        else "",
        # Offered only when the client itself renders a hostile in sight within reach: a
        # retreat without a visible threat has no bearing to take, and a name that guesses
        # one is a step the world never showed.
        "retreat"
        if reading.self_state.alive
        and not screen_open(reading)
        and nearest_hostile(reading) is not None
        else "",
        # The generic selection capability: a valid choice exists whenever the nine HUD slots
        # the number keys address hold something, whatever the standing goal — it is not
        # hidden because a gather target happens to point at one of them. The choice itself
        # (which slot, and whether it is worth selecting) is the deciding layer's.
        "select_hotbar"
        if select_target(milestone, reading, grid_side=crafting_grid_side(reading)) is not None
        or hotbar_choice_available(reading)
        else "",
        "use_target" if use_target_refusal(reading).accepted else "",
        "turn_to",
    }
    return tuple(name for name in SKILL_OFFER if name in feasible)


def needs_from(milestone: Milestone | None, reading: WorldObservationValue) -> dict[str, int]:
    """The two needs §3 allows, as ordering numbers and nothing else.

    `resource_security` is about the ask, not about a particular item: holding the thing the
    milestone wants is more secure than holding something a craft could turn into, which is more
    secure than holding what the mind cannot do anything with. With no milestone standing the
    middle rung is the table's answer — some craft could run — so the needs say something about
    the reading rather than about a product this module used to name. `safety` reads health and
    food and only orders actions — no number here generates a line of dialogue.
    """

    if goal_held(milestone, reading):
        resource_security = 1
    elif craft_options(reading, grid_side=crafting_grid_side(reading)) or (
        milestone is not None and milestone.held(reading) > 0
    ):
        resource_security = 5
    else:
        resource_security = 9
    return {"resource_security": resource_security, "safety": safety_need(reading)}


def safety_need(reading: WorldObservationValue) -> int:
    """The current body's urgency, without consulting goals or recipe knowledge."""
    health = reading.self_state.health
    max_health = reading.self_state.max_health or 1.0
    food = reading.self_state.food
    if not reading.self_state.alive:
        return 9
    elif health < max_health * 0.5 or food <= 2:
        return 7
    elif health < max_health * 0.9 or food <= 6:
        return 3
    return 1


def _nearest_drop(reading: WorldObservationValue) -> EntityCandidate | None:
    """The nearest dropped item in view, whatever it is.

    Deliberately not filtered to one item id: an ask may name anything the summary shows, and the
    question this answers is whether there is a thing on the ground to walk to at all. The list is
    the Bridge's own radius-and-occlusion answer, so nothing here sees more than the client did.
    """

    drops = _visible_item_entities(reading)
    if not drops:
        return None
    return min(
        drops,
        key=lambda entity: math.dist(
            (entity.relative_x, entity.relative_y, entity.relative_z), (0.0, 0.0, 0.0)
        ),
    )


def observation_summary(
    milestone: Milestone | None, reading: WorldObservationValue
) -> dict[str, object]:
    """What this side read, in the fields an answerer needs in order to fill an argument in.

    The point of the summary is that a choice about a product is a choice about a number the Kin
    holds: asked to name a `target_item` while blind, an answerer can only guess, and a guess is
    then refused as a missing recipe or an unaffordable bag — which reads like a bad decision and
    is a badly-posed question. So the counts come from the same reading every precondition check
    below is made against, and nothing else does.

    What is not here is the world's geometry: no coordinates, no block positions, no entity ids,
    no session material. Relative offsets are what the Bridge renders and the mind walks to, which
    is not a fact an answerer can use — it has no map — and a name-and-number view is what lets the
    ask be checked against the reading afterwards instead of argued about.

    `craft_options` is the table's answer for this bag, not a list of items this module knows, so a
    session with a new curated row shows it without a code change and a session with no milestone
    still has something true to say about what the bag could become. `consumable_items` is the
    same kind of answer for the food table: the meals this build can act on within the hotbar's
    reach — it states the curated boundary to the answerer instead of letting it guess at foods
    the skill would refuse by name, and it leaves out bag-only stacks for the same reason it
    exists: a listed item is one the skill can actually run for.
    """

    counts: dict[str, int] = {}
    for stack in reading.inventory.stacks:
        counts[stack.item_id] = counts.get(stack.item_id, 0) + stack.count
    dropped: dict[str, int] = {}
    for entity in _visible_item_entities(reading):
        item_id = entity.item_id or ""
        dropped[item_id] = dropped.get(item_id, 0) + (entity.item_count or 0)
    aim = reading.aim
    side = crafting_grid_side(reading)
    summary: dict[str, object] = {
        "game_tick": reading.game_tick,
        "time_of_day": time_of_day(reading.game_tick),
        # The generic entity reading: nearest rendered bodies first, each with the type the
        # game names, the horizontal distance a player would judge, and whether the Kin can
        # see it. What any of them MEANS -- hostile, animal, trader, worth hitting -- is the
        # answerer's judgement; this side contributes the reading, not the verdict.
        "visible_entities": [
            {
                "entity_type": entity.entity_type,
                "distance_blocks": round(math.hypot(entity.relative_x, entity.relative_z), 1),
                "line_of_sight": bool(entity.line_of_sight),
            }
            for entity in rendered_entities(reading)[:SUMMARY_ENTITY_LIMIT]
        ],
        "inventory": dict(sorted(counts.items())),
        # The player's own HUD row: which of the nine number-key slots holds what. A slot the
        # model may name in `select_hotbar` has to be visible to the model, the same way the
        # hotbar is visible to the player — counts alone would make every slot a guess.
        "hotbar": [
            {"slot": stack.slot, "item_id": stack.item_id, "count": stack.count}
            for stack in sorted(reading.inventory.stacks, key=lambda stack: stack.slot)
            if 0 <= stack.slot < HOTBAR_SLOT_COUNT
        ],
        "selected_slot": reading.self_state.selected_slot,
        "yaw_degrees": reading.self_state.yaw_degrees,
        "pitch_degrees": reading.self_state.pitch_degrees,
        "screen_open": screen_open(reading),
        "screen_id": "" if reading.gui is None else reading.gui.screen_id,
        # What an open merchant offers, each row with its index (the button a choice
        # names) and whether this bag can pay it right now -- the numbers the choice is
        # made of, read off the same screen the click will land on.
        "trade_offers": [
            {
                "offer_index": index,
                "first_item_id": offer.first_item_id,
                "first_count": offer.first_count,
                "second_item_id": offer.second_item_id,
                "second_count": offer.second_count,
                "sell_item_id": offer.sell_item_id,
                "sell_count": offer.sell_count,
                "uses": offer.uses,
                "max_uses": offer.max_uses,
                "disabled": offer.disabled,
                "payable": (
                    not offer.disabled
                    and offer.uses < offer.max_uses
                    and item_total(reading.inventory, offer.first_item_id) >= offer.first_count
                    and (
                        not offer.second_item_id
                        or item_total(reading.inventory, offer.second_item_id) >= offer.second_count
                    )
                ),
            }
            for index, offer in enumerate(() if reading.gui is None else reading.gui.trade_offers)
        ],
        "held_item": reading.self_state.main_hand_item_id or "",
        "aimed_block": aim.targeted_block_id if aim is not None and aim.block is not None else "",
        "dropped_items": dict(sorted(dropped.items())),
        "crafting_grid_side": side,
        "craft_options": list(craft_options(reading, grid_side=side)),
        "consumable_items": list(reachable_food_items(reading)),
        # The weapons a number key can bring to hand, the same actionable view the meal
        # list gives: a fight names its target, and what it will be holding is this
        # build's table's choice among these.
        "wieldable_items": list(reachable_weapons(reading)),
        "health": reading.self_state.health,
        "max_health": reading.self_state.max_health,
        "food": reading.self_state.food,
        "alive": reading.self_state.alive,
        "respawn_available": reading.self_state.respawn_available,
    }
    if milestone is not None:
        summary["goal"] = {
            "product_id": milestone.product_id,
            "quantity": milestone.quantity,
            "held": milestone.held(reading),
            "direction": milestone.label,
        }
        # A goal-level fact read off the catalog and this reading, not a product name this module
        # remembers: the outstanding plan holds a shape the currently readable grid cannot, so the
        # last craft needs a larger grid the Kin has to stand up. Once a wider window is up `side`
        # answers three and the flag clears itself — no per-item chain, no guess.
        material_plan = owed_steps(
            reading, milestone.product_id, milestone.quantity, grid_side=side
        )
        summary["craft_plan_source"] = "curated_catalog"
        summary["craft_plan"] = (
            [
                {
                    "product_id": step.product_id,
                    "required_total": step.required_total,
                    "materials": dict(step.materials),
                    "fits_current_grid": step.recipe.fits(side),
                }
                for step in material_plan
            ]
            if isinstance(material_plan, tuple)
            else []
        )
        needed = owed_steps(reading, milestone.product_id, milestone.quantity)
        summary["larger_grid_needed"] = isinstance(needed, tuple) and plan_needs_larger_grid(
            needed, grid_side=side
        )
        # The same catalog answer, but as the item the Kin can act on: the largest shape the plan
        # lays out that this grid cannot hold decides which grid-enabler opens it, and whether the
        # bag already holds one tells the answerer whether the next step is to craft it or to
        # select, place and open the one it has. Read off `Recipe.opens_grid_side`, never a product
        # name this module remembers — a newly curated wider grid surfaces here as a row would.
        if isinstance(needed, tuple):
            needed_side = largest_grid_in_plan(needed)
            enabler = (
                grid_enabler_for(needed_side, within_side=side) if needed_side > side else None
            )
            if enabler is not None:
                summary["grid_enabler"] = {
                    "product_id": enabler.product_id,
                    "opens_grid_side": enabler.opens_grid_side,
                    "held": item_total(reading.inventory, enabler.product_id),
                    "in_hand": enabler.product_id == reading.self_state.main_hand_item_id,
                }
    return summary


def _inventory_contents(reading: WorldObservationValue) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for stack in reading.inventory.stacks:
        counts[stack.item_id] = counts.get(stack.item_id, 0) + stack.count
    return tuple(sorted(counts.items()))


def _visible_item_entities(reading: WorldObservationValue) -> tuple[EntityCandidate, ...]:
    """The rendered entities the client reports as dropped items, item fields and all."""

    return tuple(
        entity
        for entity in reading.visible_entities
        if entity.item_id and entity.item_count is not None
    )


def _asked_text(arguments: Mapping[str, object], key: str) -> str:
    """One argument as the text this side will use, or empty for "the answer did not say".

    Nothing coerces: a value that is not a string is not a statement about an item, and an empty
    return sends the caller to its own source — the milestone, then the reading — which is the
    order the ask vocabulary's defaults are defined by.
    """

    value = arguments.get(key)
    return value if isinstance(value, str) else ""


def _asked_number(arguments: Mapping[str, object], key: str) -> float | None:
    """One argument as a number, or `None`. `bool` is not a number here, whatever Python says."""

    value = arguments.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _asked_quantity(
    arguments: Mapping[str, object],
    milestone: Milestone | None,
    *,
    policy: DecisionPolicy,
) -> int:
    """How many of a product the ask wants: the answer's number, then — for the rule strategy
    only — the milestone's, then one.

    The bounds are re-checked rather than trusted, even though `compose_decision` judged them,
    because the rule strategy reaches here with no answer at all and the same arithmetic then has
    to hold. A quantity is capped at a stack because that is what the ask vocabulary says, and a
    plan that wanted more is a sequence of asks, not one of them. The milestone rung is the
    rules' own default and is never taken for a model's ask: the operator's quantity is not the
    model's decision.
    """

    asked = _asked_number(arguments, "quantity")
    if asked is not None and asked.is_integer() and 1 <= asked <= MAX_QUANTITY:
        return int(asked)
    if policy is DecisionPolicy.RULES and milestone is not None:
        return milestone.quantity
    return 1


def observation_ref(reading: WorldObservationValue) -> str:
    """A reference to one reading, not a copy of it.

    Tick and generation together identify it inside a session and say nothing about its
    contents. The summary that goes with it travels as a separate field of the request; this is
    the handle that ties an answer back to the bytes it was made from, which is what lets a
    reader check the ask against the reading rather than against whatever the world looks like
    now.
    """

    return f"tick={reading.game_tick};generation={reading.generation}"


@dataclass(frozen=True, slots=True)
class MindIntent:
    """One decision, in the shape the session needs to lease and run it.

    `arguments` is the ask as this side honoured it: the keys the chosen skill declares, with the
    values that came from the answer — or, for a step the local reflection chose, the values the
    milestone and the reading imply. It is kept beside `plan` rather than folded into it because
    the two are different claims: the ask says what was wanted, the call says which craft that
    turned into, and a run that ended with the wrong item in hand is argued about from those two
    numbers and nothing else.

    `plan` carries what a chosen skill cannot invent — which recipe, which item, which slot —
    filled from the reading this intent was built on. `observation_ref` names that reading, so the
    projection can say what the ask was based on rather than implying it was based on whatever the
    world looks like now.
    """

    kind: MindDecisionKind
    plan: SkillPlan
    reason: str
    source: str = ""
    intent_generation: int = 0
    observation_ref: str = ""
    model_refusal: str = ""
    arguments: Mapping[str, object] = field(default_factory=dict[str, object])
    #: Input provenance for a model-selected step, not proof of a trait causing it.
    #: Local reflection does not currently consult personality and must not claim it did.
    persona_context_ref: str | None = None

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
            "arguments": dict(self.arguments),
            "persona_context_ref": self.persona_context_ref,
        }


@dataclass
class PlayerMind:
    """The smallest thing that can want a product and be told it does not have it.

    Mutable and single-threaded by design: this is one Kin's running state — the milestone, the
    generation it is on, which skills have spent their retries — read by exactly one session loop.
    Nothing about the world is cached here beyond the one reading an intent was built on;
    `WorldObservationStore` stays the only judge of what things look like.

    `goal` is supplied, not assumed: whoever builds the mind says what the Kin is working toward,
    and `None` means it is working toward nothing in particular. That is the whole of the milestone
    surface — the mind never asks what a pickaxe is, only what it was handed.
    """

    provider: DecisionProvider
    ledger: CostLedger
    kin_id: str = ""
    persona_seed: str = ""
    goal: Milestone | None = None
    model_enabled: bool = True
    #: Who decides ordinary steps. `MODEL` by default: the provider answers, and its failure is
    #: a named stop, not a fallback. `RULES` is the explicitly selected offline strategy.
    policy: DecisionPolicy = DecisionPolicy.MODEL
    persona: PersonaManifest | None = None
    session_history: Mapping[str, object] = field(default_factory=dict[str, object])
    craft_knowledge: CraftKnowledge | None = None
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
    last_precondition: str = field(default="", init=False)
    last_model_refusal: str = field(default="", init=False)
    #: The crosshair target the last *sent* `use_target` click was aimed at. A repeat
    #: ask against this exact target is the doomed second click §4 forbids, so the mind
    #: withholds the use key until the aim reads differently — the turn, not a gamble.
    last_use_aim: tuple[object, ...] | None = field(default=None, init=False)
    #: The absolute coordinates of the block the last `break_seen_block` was aimed at, kept so a
    #: later `collect` that walked the player off the trunk can turn back to face it. A real
    #: player remembers which tree they were felling; re-aiming at a block already seen is the
    #: same player-equivalent geometry the walk skill uses on a visible drop, not the forbidden
    #: chunk scan — it recalls only a cell the crosshair itself once reported. Used at most once
    #: per remembered block (see `_call_for`), so a felled tree that leaves no block in view
    #: cannot strand the run in a re-aim loop: the memory clears and the blind scan resumes.
    last_target_block: tuple[int, int, int] | None = field(default=None, init=False)
    #: Which rung of the re-aim ladder (`_reacquire_probe`) the resource re-aim is on. It advances
    #: once per re-aim turn and resets when the block is re-armed (a `break_seen_block` follows a
    #: landed aim) or when the sweep exhausts and the memory clears — so the sweep is bounded and
    #: repeats only while a real aim is being chased, never across a felled trunk.
    reaim_probe: int = field(default=0, init=False)

    observed_drop_ids: set[tuple[int, str]] = field(
        default_factory=set[tuple[int, str]], init=False
    )
    #: The last observed health, and whether the newest reading came in lower: the drop is the
    #: one damage signal a reading carries with no attacker in view. Set in `observe`, so the
    #: comparison is between two readings of the world and never a reading against itself.
    last_health: float | None = field(default=None, init=False)
    recent_damage: bool = field(default=False, init=False)
    #: True from a CONFIRMED respawn until the first CONFIRMED step that is not one. The
    #: spot the death happened on is the one place the next reading has already proven
    #: dangerous (the 2026-10-05 soak: 37 deaths, every respawn back into the same camp),
    #: so the first thing this mind does with a body again is carry it off that spot.
    just_respawned: bool = field(default=False, init=False)
    empty_container_aim: tuple[object, ...] | None = field(default=None, init=False)
    empty_container_inventory: tuple[tuple[str, int], ...] = field(default=(), init=False)
    recent_results: list[dict[str, object]] = field(
        default_factory=list[dict[str, object]], init=False
    )

    def __post_init__(self) -> None:
        if self.persona is not None and self.persona.kin_id != self.kin_id:
            raise ValueError("the persisted persona must belong to this Kin")

    @property
    def direction(self) -> str:
        """The heading the run document prints, which is the milestone's and not this module's."""

        return "" if self.goal is None else self.goal.label

    def holds_goal(self, reading: WorldObservationValue) -> bool:
        """Whether the standing milestone is in hand on this reading — the loop's stop condition.

        A method rather than a module function at the call site because the caller has the mind and
        not the milestone: a session with no standing goal never stops on a held item, and the place
        that decides which item would is this one.
        """

        return goal_in_hand(self.goal, reading)

    def public_crafts(self, reading: WorldObservationValue) -> Mapping[str, Recipe]:
        if self.craft_knowledge is None:
            return {}
        return self.craft_knowledge.available(reading, grid_side=crafting_grid_side(reading))

    def _threat(self, reading: WorldObservationValue) -> dict[str, object] | None:
        """What this reading says about being in danger, or None when it says nothing.

        Two signals, both player-visible: a hostile entity the client renders in sight within
        reach (`nearest_hostile`), and a health lower than the previous reading's — the drop
        that means a hit landed even when the attacker is behind the camera. The summary
        carries this to a model as a fact; `DANGER_SUPPRESSED` and the safety tier act on it.
        """

        hostile = nearest_hostile(reading)
        if hostile is None and not self.recent_damage:
            return None
        threat: dict[str, object] = {"recent_damage": self.recent_damage}
        if hostile is not None:
            threat["nearest_hostile"] = {
                "entity_type": hostile[0].entity_type,
                "distance_blocks": round(hostile[1], 2),
            }
        return threat

    def _needs(self, reading: WorldObservationValue) -> dict[str, int]:
        """`needs_from` with the danger overlay: a threat reads at the badly-hurt tier.

        The same number the break guard already honours, so every consumer of `needs` — the
        local order and the request sent to a model — sees the escalation from one seam.
        """

        needs = needs_from(self.goal, reading)
        if self._threat(reading) is not None:
            needs["safety"] = max(needs["safety"], 7)
        return needs

    def _imminent_protection(
        self, feasible: tuple[str, ...], reading: WorldObservationValue
    ) -> str | None:
        """The one step local code may take without a decision, or `None`.

        Scope, stated because the words stretch easily: this is not a reflex family. Death,
        hunger and combat are ordinary conditions the deciding layer owns — an automatic
        respawn, an automatic meal or an automatic swing would each be local code making a
        choice that was asked of the model. What survives is the narrow row of the original
        table: damage being taken *now* — a health drop between the last two readings, or a
        hostile the client renders inside swing reach — buys one bounded step away, and
        nothing else. The step is still the retreat skill's own: a named hold, released
        through the same named exit, confirmed only by a later reading that the body moved.
        """

        if "retreat" not in feasible:
            return None
        if self.recent_damage or attackable_hostile(reading) is not None:
            return "retreat"
        return None

    def _goal_craft_blocker(self, reading: WorldObservationValue) -> str:
        """The standing goal's craft obstacle on this reading, from whichever plan is bound.

        One word per obstacle, from the same source the ask will be answered by: the curated
        table when nothing else is configured, the version archive when it is. Callers that act
        on `CRAFT_MATERIALS_MISSING` or `CRAFT_GRID_TOO_SMALL` (the re-aim, the enabler
        placement) therefore keep their meaning for imported products too, instead of reading a
        curated-only `CRAFT_RECIPE_UNAVAILABLE`.
        """

        if self.goal is None:
            return ""
        side = crafting_grid_side(reading)
        if self.craft_knowledge is not None:
            step = self.craft_knowledge.step_toward(
                self.goal.product_id,
                reading,
                quantity=self.goal.quantity,
                grid_side=side,
                preferred=self._preferred_raw(),
            )
            return step if isinstance(step, str) else ""
        return blocker_for(reading, self.goal.product_id, self.goal.quantity, grid_side=side)

    def _enabler_to_stand_up(self, reading: WorldObservationValue) -> tuple[Recipe, int] | None:
        """The held grid-opener the goal needs stood up, from whichever plan is bound."""

        if self.goal is None:
            return None
        side = crafting_grid_side(reading)
        if self.craft_knowledge is not None:
            return self.craft_knowledge.enabler_to_stand_up(
                self.goal.product_id,
                reading,
                quantity=self.goal.quantity,
                grid_side=side,
                preferred=self._preferred_raw(),
            )
        return enabler_to_stand_up(self.goal, reading, grid_side=side)

    def _preferred_raw(self) -> tuple[str, ...]:
        """The goal's configured source item as the plan's ordered route start.

        Among equivalent tag alternatives — any log, any plank, either stone — the operator
        named the resource this run starts from, and the model-facing floor should read that
        name before the archive's alphabetical first member. Empty when no goal names a
        source; the plan stays deterministic either way.
        """

        if self.goal is not None and self.goal.source_item_id:
            return (self.goal.source_item_id,)
        return ()

    def _gather_wants(self, reading: WorldObservationValue) -> frozenset[str]:
        """The raw items a local gather would be for, from whichever plan is bound.

        The milestone's own source name is what a curated run has always used; with version
        knowledge bound, the plan's uncoverable floor (`missing_raw`) joins it, so the local
        break follows what the recipe arithmetic is short of instead of one remembered name.
        It stays a name match against the crosshair's own report — a block nobody said drops
        the wanted item is not broken — which is the conservatism the contract keeps.
        """

        wanted: set[str] = set()
        if self.goal is not None and self.goal.source_item_id:
            wanted.add(self.goal.source_item_id)
        if self.goal is not None and self.craft_knowledge is not None:
            wanted.update(
                self.craft_knowledge.missing_raw(
                    self.goal.product_id,
                    reading,
                    quantity=self.goal.quantity,
                    grid_side=crafting_grid_side(reading),
                )
            )
        return frozenset(wanted)

    def _select_target(self, reading: WorldObservationValue) -> tuple[str, int] | None:
        """Which held item the goal wants in hand — its product, or the grid-opener."""

        if self.goal is None:
            return None
        if goal_held(self.goal, reading) and not goal_in_hand(self.goal, reading):
            slot = goal_slot(self.goal, reading)
            if slot is not None:
                return (self.goal.product_id, slot)
        enabler = self._enabler_to_stand_up(reading)
        if enabler is not None and enabler[1] != reading.self_state.selected_slot:
            return (enabler[0].product_id, enabler[1])
        return None

    def _rule_arguments(self, skill: str, reading: WorldObservationValue) -> Mapping[str, object]:
        """The defaults the rule strategy's own choice implies — built here and only here.

        The one parameter map the rules fill in for themselves is a hotbar selection's slot,
        derived from the milestone or the held enabler. A model's ask never borrows it: an
        answer that did not name its slot is refused by name, not answered with the goal's.
        """

        if skill == "select_hotbar":
            target = self._select_target(reading)
            if target is not None:
                item_id, slot = target
                return {"slot": slot, "expected_item_id": item_id}
        return {}

    def craft_options_for(self, reading: WorldObservationValue) -> tuple[str, ...]:
        if self.craft_knowledge is not None:
            return tuple(sorted(self.public_crafts(reading)))
        return craft_options(reading, grid_side=crafting_grid_side(reading))

    def feasible_skills(self, reading: WorldObservationValue) -> tuple[str, ...]:
        feasible = feasible_skill_ids(self.goal, reading)
        if self.craft_knowledge is None:
            return feasible
        added = [name for name in feasible if name != "craft_take_result"]
        if (
            reading.self_state.alive
            and not (screen_open(reading) and goal_in_hand(self.goal, reading))
            and self.craft_options_for(reading)
        ):
            added.append("craft_take_result")
        if (
            reading.self_state.alive
            and not screen_open(reading)
            and "select_hotbar" not in added
            and (self._select_target(reading) is not None or hotbar_choice_available(reading))
        ):
            # The curated offer only names a select target for curated plans; an imported
            # goal's held grid-opener is the same move and must be offered all the same --
            # and so is the generic "these nine slots hold something" case.
            added.append("select_hotbar")
        return tuple(added)

    def observe(self, reading: WorldObservationValue | None) -> None:
        """Say whether the direction is met, off a reading, because nothing else may say it.

        The skill that crafted the product already reached a `CONFIRMED` verdict of its own, and
        that verdict was itself derived from a pair of readings — this is a later one, taken after
        the intent was recorded. §4 closes a goal on the world's word, not on a decision's
        self-report, so it reads the inventory here. It reads it in both directions: the milestone
        is *holding* the thing, so a later reading that no longer has enough of one un-closes it and
        the Kin goes back to work rather than reporting an item it has lost.
        """

        self.goal_met = reading is not None and goal_held(self.goal, reading)
        if reading is not None:
            # The one damage signal a reading carries by itself: a health the previous reading
            # did not show. Kept here rather than in `needs_from` because a drop is a fact
            # about two readings, not about one.
            health = reading.self_state.health
            self.recent_damage = self.last_health is not None and health < self.last_health
            self.last_health = health

    def next_intent(self, reading: WorldObservationValue | None) -> MindIntent:
        """Ask — of the model, or of the reflection below — what to do about this reading.

        The answer's arguments go to `_call_for` with the skill it names, and the reading decides:
        an ask this bag cannot pay for, or for a shape this screen cannot hold, becomes a hold
        filed under the name of that precondition rather than a click and not a silent substitution
        of the local choice. That is the local half of "本地负责前提判断" and it is what the run
        document is read for afterwards.
        """

        self.observe(reading)
        if reading is None:
            return self._hold(NO_LATEST_OBSERVATION, None)
        if not reading.self_state.alive and reading.self_state.respawn_available is not True:
            return self._hold(PLAYER_DEAD, reading)
        if self.holds_goal(reading) and not screen_open(reading):
            return self._hold(GOAL_ACHIEVED, reading)
        drop_ids = {
            (reading.generation, entity.observation_id)
            for entity in _visible_item_entities(reading)
        }
        if drop_ids - self.observed_drop_ids:
            # A newly visible drop changes the approach problem. Pose/tick changes or
            # re-seeing the same failed entity do not replenish its retry budget.
            self.excluded.discard("collect_dropped")
            for code in FailureCode:
                self.attempts.pop(("collect_dropped", code), None)
            self.observed_drop_ids.update(drop_ids)
        if "retreat" in self.excluded and (self.recent_damage or self.just_respawned):
            # The same rule one step further out: a reflex's whole precondition is danger,
            # and danger arrives as new evidence -- a fresh hit or a fresh respawn refunds
            # the step the way a newly visible drop refunds the collect. Without this the
            # budget spent in one bad window excluded the only danger response for the rest
            # of the run: measured on the third night of the 2026-10-05 soak
            # (run 161f530ac2fe47e189ac00761de23ca3), four deaths after the exclusion and
            # no step left that could answer one.
            self.excluded.discard("retreat")
            for code in FailureCode:
                self.attempts.pop(("retreat", code), None)
        contents = _inventory_contents(reading)
        if contents != self.empty_container_inventory:
            self.empty_container_aim = None
        feasible = tuple(
            name for name in self.feasible_skills(reading) if name not in self.excluded
        )
        if (
            reading.self_state.alive
            and not screen_open(reading)
            and "retreat" not in feasible
            and (self.recent_damage or self.just_respawned)
        ):
            # A threat the client renders is not the only thing worth leaving: a health
            # drop is damage a hit already did, and a respawn is a spot the world has
            # already proven deadly around. Both outrank staying -- the 2026-10-05 soak
            # died 37 times in one night with nothing hostile ever in sight (the kills
            # landed between readings), because the offer needed a rendered hostile to
            # exist at all. The step is still the skill's: a named hold, and the world's
            # next reading decides whether another follows.
            feasible = (*feasible, "retreat")
        if (
            not screen_open(reading)
            and self.empty_container_aim is not None
            and use_target_signature(reading) == self.empty_container_aim
        ):
            feasible = tuple(name for name in feasible if name != "use_target")
        # A second use-key click at the exact crosshair target the last one was spent on
        # — and did nothing to — is the repeat the contract forbids, not a fresh attempt.
        # Withhold it only while something else remains to reach for (the turn to change
        # the aim), so the guard redirects rather than strands the run.
        if (
            len(feasible) > 1
            and "use_target" in feasible
            and self.last_use_aim is not None
            and use_target_signature(reading) == self.last_use_aim
        ):
            feasible = tuple(name for name in feasible if name != "use_target")
        threat = self._threat(reading)
        # The model sees the WHOLE offer; the local backstop sees what the curated danger
        # reading leaves. Choosing what a rendered entity MEANS for this moment -- hit it,
        # leave it, keep working past it -- is the judgement the model exists for, so the
        # curated roster never narrows what the model is shown or may choose; it teaches
        # only the rule order (and the imminent-protection gate) which bodies to flinch from.
        local_feasible = feasible
        if threat is not None:
            local_feasible = tuple(name for name in feasible if name not in DANGER_SUPPRESSED)
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
        summary = observation_summary(self.goal, reading)
        if self.craft_knowledge is not None:
            summary["craft_options"] = list(self.craft_options_for(reading))
            summary["public_recipe_knowledge"] = self.craft_knowledge.as_document()
            if self.goal is not None:
                step = self.craft_knowledge.step_toward(
                    self.goal.product_id,
                    reading,
                    quantity=self.goal.quantity,
                    grid_side=crafting_grid_side(reading),
                    preferred=self._preferred_raw(),
                )
                summary["craft_plan_source"] = "public_version_stepwise"
                summary["multi_stage_plan_available"] = True
                chain = self.craft_knowledge.owed_chain(
                    self.goal.product_id,
                    reading,
                    quantity=self.goal.quantity,
                    grid_side=crafting_grid_side(reading),
                    preferred=self._preferred_raw(),
                )
                summary["craft_plan"] = (
                    []
                    if isinstance(chain, str)
                    else [
                        {
                            "product_id": entry.product_id,
                            "required_total": entry.required_total,
                            "fits_current_grid": entry.fits_grid_side,
                            **(
                                {"materials": dict(entry.materials)}
                                if entry.materials is not None
                                else {}
                            ),
                        }
                        for entry in chain
                    ]
                )
                reason = step if isinstance(step, str) else ""
                summary["larger_grid_needed"] = reason == CRAFT_GRID_TOO_SMALL
                summary["goal_recipe_refusal"] = reason
                enabler = self._enabler_to_stand_up(reading)
                if enabler is None:
                    summary.pop("grid_enabler", None)
                else:
                    summary["grid_enabler"] = {
                        "product_id": enabler[0].product_id,
                        "opens_grid_side": enabler[0].opens_grid_side,
                        "held": item_total(reading.inventory, enabler[0].product_id),
                        "in_hand": enabler[0].product_id == reading.self_state.main_hand_item_id,
                    }
                missing = self.craft_knowledge.missing_raw(
                    self.goal.product_id,
                    reading,
                    quantity=self.goal.quantity,
                    grid_side=crafting_grid_side(reading),
                    preferred=self._preferred_raw(),
                )
                if missing:
                    # Which resource a gather would have to bring back, so a route can be
                    # chosen from the plan instead of from one remembered source item.
                    summary["missing_raw"] = dict(missing)
        summary["recent_actions"] = list(self.recent_results)
        summary["view_search"] = self._view_search_summary(reading)
        if threat is not None:
            summary["danger"] = threat
        request = DecisionRequest(
            observation_ref=observation_ref(reading),
            needs=self._needs(reading),
            active_goal=self.direction,
            feasible_skill_ids=feasible,
            observation_summary=summary,
            persona_seed=self.persona_seed,
            persona=self.persona,
            session_history=self.session_history,
            budget_remaining_micro=self.ledger.remaining(),
            intent_generation=self.intent_generation,
        )
        refusal = ""
        reason = ""
        arguments: Mapping[str, object] = {}
        needs = self._needs(reading)
        skill: str = ""
        source: str = ""
        if self.policy is DecisionPolicy.RULES:
            # The explicitly selected rule strategy: the order in `_reflect` is the decider
            # and the provider is never consulted, so no model call is spent or recorded.
            # The one rule-constructed parameter map (the hotbar default) is built here and
            # only here -- a model's ask never has its parameters filled from the milestone.
            skill = self._reflect(local_feasible, needs, reading)
            source = DECISION_FROM_LOCAL
            arguments = self._rule_arguments(skill, reading)
        else:
            answer = self.provider.decide(request)
            if isinstance(answer, Decision) and answer.skill_id in feasible:
                # The shipped port already files an out-of-bounds skill or an illegal ask as
                # a `ModelUnavailable`; this branch is for a provider that built its own
                # `Decision`, and the argument check runs here so an ask this side cannot
                # honour is refused by name instead of reaching the wire as a click.
                honoured_arguments = validate_arguments(answer.skill_id, answer.arguments)
                if isinstance(honoured_arguments, str):
                    refusal = honoured_arguments
                else:
                    skill, source, reason = (
                        answer.skill_id,
                        DECISION_FROM_MODEL,
                        answer.reason[:MAX_REASON_CHARS],
                    )
                    arguments = honoured_arguments
            elif isinstance(answer, Decision):
                refusal = UnavailableReason.DECISION_OUT_OF_BOUNDS.value
            else:
                refusal = answer.reason.value
            self.last_model_refusal = refusal
            if not skill:
                # The deciding layer was asked and did not answer with something this side
                # can run. No ordinary behaviour is substituted for its choice -- that would
                # be the silent switch to the rule order the contract forbids, and a payable
                # merchant row or an owed craft is not a decision. The only thing that still
                # moves is the bounded step out of damage being taken now; otherwise the run
                # stops under the named reason with the refusal kept beside it.
                protection = self._imminent_protection(local_feasible, reading)
                if protection is None:
                    return self._hold(refusal, reading, model_refusal=refusal)
                skill, source, reason, arguments = protection, DECISION_FROM_LOCAL, "", {}
        plan, built_reason, honoured = self._call_for(skill, reading, arguments)
        if plan is None and built_reason == GOAL_ACHIEVED:
            # An ask for a quantity or intermediate product already held closes that request,
            # not the standing milestone checked above.
            built_reason = "REQUEST_ALREADY_SATISFIED"
        if (
            plan is None
            and self.policy is DecisionPolicy.RULES
            and (
                built_reason in CONSUME_REFUSAL_REASONS
                or (
                    self.goal is not None
                    and built_reason in {"REQUEST_ALREADY_SATISFIED", CRAFT_MATERIALS_MISSING}
                )
                or (
                    built_reason == CRAFT_GRID_TOO_SMALL
                    and self._enabler_to_stand_up(reading) is not None
                )
            )
        ):
            # The rule order repairs its own choice from the offer's remaining candidates,
            # one try each -- that is the rules strategy deciding again, never a model's ask
            # being replaced. Under the model policy this repair does not exist: the reason
            # is reported and the run stops.
            self.last_precondition = built_reason
            source, reason = DECISION_FROM_LOCAL, ""
            remaining = local_feasible
            while remaining and plan is None:
                skill = self._reflect(remaining, needs, reading)
                plan, built_reason, honoured = self._call_for(
                    skill, reading, self._rule_arguments(skill, reading)
                )
                remaining = tuple(name for name in remaining if name != skill)
        if plan is None:
            if self.policy is DecisionPolicy.MODEL:
                # The reason a model's ask could not become a command goes back beside the
                # refusal, so the document says which decision met which obstacle.
                self.last_precondition = built_reason
                self.last_model_refusal = refusal or built_reason
                return self._hold(built_reason, reading, model_refusal=refusal or built_reason)
            return self._hold(built_reason, reading)
        # A `use_target` plan that was built past its precondition is a click about to spend
        # on this exact target; remember which one so a repeat ask can be turned away before
        # the world is asked to do the impossible twice.
        if skill == "use_target":
            self.last_use_aim = use_target_signature(reading)
        intent = MindIntent(
            kind=MindDecisionKind.INTENT,
            plan=plan,
            reason=reason or built_reason,
            source=source,
            intent_generation=self.intent_generation,
            observation_ref=request.observation_ref,
            model_refusal=refusal,
            arguments=honoured,
            persona_context_ref=(
                str(self.persona.decision_context()["manifest_sha256"])
                if source == DECISION_FROM_MODEL and self.persona is not None
                else None
            ),
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

        A named precondition is decided by that question rather than by the retry budget: if a
        later reading could answer differently, the skill keeps its whole budget and only the
        name is filed, because the ask that follows is the one that changes the world; if no
        reading could, the skill is given up on the first telling rather than replayed until
        the count runs out. Both branches leave the same `last_precondition` behind for the
        document, so the difference is readable after the run rather than inferable from a
        missing skill.
        """

        self.last_result = outcome
        self.recent_results.append(
            {
                "skill": intent.skill,
                "arguments": dict(intent.arguments),
                "result": outcome.result.value,
                "reason": outcome.reason,
                "executed_product_id": (
                    intent.plan.calls[0].product_id if intent.plan.calls else ""
                ),
                "inventory_after": (
                    dict(_inventory_contents(reading_after)) if reading_after is not None else None
                ),
            }
        )
        del self.recent_results[:-6]
        if (
            intent.skill == "use_target"
            and outcome.result is ActionResultClass.CONFIRMED
            and reading_after is not None
            and screen_open(reading_after)
            and not craft_options(reading_after, grid_side=crafting_grid_side(reading_after))
        ):
            # Opening an unaffordable container and closing it paid no material debt.
            # Keep that target spent until inventory contents or the target change.
            self.empty_container_aim = self.last_use_aim
            self.empty_container_inventory = _inventory_contents(reading_after)
        if outcome.result is ActionResultClass.CONFIRMED:
            for code in FailureCode:
                self.attempts.pop((intent.skill, code), None)
            self.last_failure = None
            self.last_precondition = ""
            self.last_use_aim = None
            self.just_respawned = intent.skill == "respawn"
            self.observe(reading_after)
            return None
        failure = attribute_failure(outcome)
        self.last_failure = failure
        if outcome.reason in _PRECONDITION_REROUTE or outcome.reason in _PRECONDITION_DEAD_END:
            self.last_precondition = outcome.reason
            if outcome.reason in _PRECONDITION_DEAD_END:
                self.excluded.add(intent.skill)
            return failure
        key = (intent.skill, failure)
        count = self.attempts.get(key, 0) + 1
        self.attempts[key] = count
        if count > RETRY_BUDGET_PER_SIGNATURE:
            self.excluded.add(intent.skill)
            del self.attempts[key]
        return failure

    def _reflect(
        self, feasible: tuple[str, ...], needs: Mapping[str, int], reading: WorldObservationValue
    ) -> str:
        """The order the explicitly selected rule strategy decides in (`DecisionPolicy.RULES`).

        This is the offline decider the old demos run on, never a fallback: under the model
        policy a failed or refused answer stops the run by name instead of arriving here.
        A hungry Kin eats before it works: when `safety` says the reading itself is asking
        for care and the offer carries a meal, that meal goes first. Finish what the
        inventory is short of, pick up what is already on the ground, break
        what is aimed at, then look — the look staying ahead of the use keeps the rule order
        as conservative as it was, right-clicking the aimed block only as the last resort
        before the set is given up on. Because the order can act on every skill in the offer
        it can also exhaust every one: a reading whose offers all keep failing reaches
        `NO_FEASIBLE_SKILL` instead of replaying a skill the run has already given up on.
        `safety` holds a Kin back from starting a break when it is badly hurt, because a
        broken trunk is not what a half-health reading is asking for.

        Stand up a selected wider-grid enabler once the bag can pay the remaining
        material debt. Premature setup can occupy the face or sightline needed for
        further gathering, and closing that window loses its grid context. The catalog's
        blocker and grid metadata select the transition, never a product-specific chain.
        Gathering with a named raw resource is conservative: a different block under the crosshair
        does not prove that breaking it yields the wanted item, and with version knowledge bound
        the names are the plan's own uncoverable floor rather than one remembered source item. A
        model may still choose the generic break for another reason, while the local gather looks
        again instead of excavating ground.
        """

        if "respawn" in feasible:
            return "respawn"
        # No trade branch: which row of an open merchant's list to take is a purchase, and a
        # payable row is a fact about the offer, not an intent. The row only ever comes from
        # an explicit `offer_index` -- the model's ask or an operator's plan.
        if "close_screen" in feasible:
            if (
                "craft_take_result" in feasible
                and self.goal is not None
                and crafting_grid_side(reading) > PLAYER_GRID_SIDE
                and next_craft(
                    self.goal,
                    reading,
                    grid_side=crafting_grid_side(reading),
                )
                is not None
            ):
                return "craft_take_result"
            return "close_screen"
        if (
            "fight_back" in feasible
            and (reading.self_state.health or 0.0) >= FIGHT_MIN_HEALTH
            and attackable_hostile(reading) is not None
        ):
            # A hostile in reach with a body whole enough to trade: hit it. Leaving
            # against a pursuer that keeps pace means its next hit is already on the way --
            # measured live on the summon run cfbdfa76...: with a fresh hit vetoing the
            # fight, forty retreats in two minutes never ended the chase, and two deaths
            # landed inside it. A swing the reading says can land is the step that ends
            # one; only a body under the trading line still leaves.
            return "fight_back"
        if "retreat" in feasible:
            # Nothing to hit inside reach (a threat further out, a fresh hit with a low
            # body, or ground a death just proved deadly): leave. Every slime death
            # happened in a step that stood still (run-89), and leaving is the whole
            # response this build has — the next reading decides whether another step
            # follows.
            return "retreat"
        if "consume_item" in feasible and needs.get("safety", 0) >= 3:
            return "consume_item"
        if "select_hotbar" in feasible:
            standing_up = self._select_target(reading)
            holding_product = (
                standing_up is not None
                and self.goal is not None
                and standing_up[0] == self.goal.product_id
            )
            # The rules may only select a slot they can derive a target for: the generic
            # offer now carries select whenever the HUD holds anything, and without this a
            # reading whose table is already in hand would have the rule order name a
            # selection with no slot to name instead of pressing the use key.
            # The enabler goes to hand only once the bag can pay the remaining material debt:
            # `CRAFT_GRID_TOO_SMALL` is the catalog's word for "every shape this screen holds is
            # paid and the wider one is what is missing" — the same gate the use key waits for
            # below. Standing it up early spends the same four planks again later: a live run
            # selected the freshly-crafted table while the pickaxe was one plank short, placed
            # and opened it, closed it to gather, and then re-crafted a second table because a
            # placed table cannot be reselected — one plank short of the tool at the budget's end.
            if standing_up is not None and (
                holding_product or self._goal_craft_blocker(reading) == CRAFT_GRID_TOO_SMALL
            ):
                return "select_hotbar"
        if "craft_take_result" in feasible and self.goal is not None:
            # Only a standing milestone tells the rules what to make. With no goal there is
            # nothing this side was told to craft, and the table's first payable row would be
            # code picking a product -- a decision, not an execution.
            return "craft_take_result"
        enabler = self._enabler_to_stand_up(reading)
        if (
            "use_target" in feasible
            and enabler is not None
            and reading.self_state.selected_slot == enabler[1]
            and self._goal_craft_blocker(reading) == CRAFT_GRID_TOO_SMALL
        ):
            return "use_target"
        if "collect_dropped" in feasible and needs.get("resource_security", 0) >= 5:
            return "collect_dropped"
        wants = self._gather_wants(reading)
        if (
            "break_seen_block" in feasible
            and needs.get("safety", 0) < 7
            and (
                self.goal is None
                or not wants
                or (reading.aim is not None and reading.aim.targeted_block_id in wants)
            )
        ):
            return "break_seen_block"
        if "collect_dropped" in feasible:
            return "collect_dropped"
        if "turn_to" in feasible:
            return "turn_to"
        return "use_target"

    def _call_for(
        self, skill: str, reading: WorldObservationValue, arguments: Mapping[str, object]
    ) -> tuple[SkillPlan | None, str, Mapping[str, object]]:
        """Turn one ask into one call, from this reading, or say why there is nothing to run.

        This is the single place where the ask vocabulary becomes the plan-document vocabulary: a
        `target_item` becomes a recipe id and a materials map by way of `recipe_catalog`, a
        `quantity` becomes the count the plan is net of this bag, and an item id becomes the drop
        this mind walks to. Values the answer did not state are supplied here — never in the
        reader of a plan, and never by an adapter — so a document's `arguments` says what the ask
        was and its `plan` says what ran, which are two different sentences.

        The `None` branches guard a provider that answered with a skill the feasible set did not
        carry: the shipped providers cannot (the port judges the answer against the offer), but
        this is the boundary where an operator's endpoint speaks, and a mind that crashed on a bad
        answer would turn a provider bug into a stopped session. They refuse with a precondition
        name, which is what the projection and the attribution table already read.
        """

        if skill == "trade":
            asked_index = _asked_number(arguments, "offer_index")
            offers = () if reading.gui is None else reading.gui.trade_offers
            if asked_index is None or not asked_index.is_integer():
                # The row is the choice, and there is no default row: "the first one this bag
                # can pay" is a fact about the offer, not a purchase intent, and filling it
                # in here would be this side deciding what to buy.
                return None, SKILL_ARGUMENT_MISSING, {}
            index = int(asked_index)
            if not 0 <= index < len(offers):
                return None, NO_FEASIBLE_SKILL, {}
            offer = offers[index]
            ask_offer: dict[str, object] = {"offer_index": index}
            return (
                SkillPlan((SkillCall(name="trade", offer_index=index),)),
                (
                    f"trade {offer.first_count}x{offer.first_item_id} for "
                    f"{offer.sell_count}x{offer.sell_item_id}"
                ),
                ask_offer,
            )
        if skill == "approach_entity":
            named_body = arguments.get("target_entity_type")
            body_kind = named_body if isinstance(named_body, str) and named_body else ""
            body = nearest_visible(reading, kinds=frozenset({body_kind}) if body_kind else None)
            if body is None:
                return None, NO_FEASIBLE_SKILL, {}
            asked_stop = _asked_number(arguments, "stop_within")
            ask_walk: dict[str, object] = {}
            if body_kind:
                ask_walk["target_entity_type"] = body_kind
            if asked_stop is not None:
                ask_walk["stop_within"] = asked_stop
            return (
                SkillPlan(
                    (
                        SkillCall(
                            name="approach_entity",
                            target_entity_type=body_kind,
                            stop_within=asked_stop or 0.0,
                        ),
                    )
                ),
                f"walk to the {body_kind or body[0].entity_type}",
                ask_walk,
            )
        if skill == "look_at_entity":
            named_kind = arguments.get("target_entity_type")
            kind = named_kind if isinstance(named_kind, str) and named_kind else ""
            target = nearest_visible(reading, kinds=frozenset({kind}) if kind else None)
            if target is None:
                return None, NO_FEASIBLE_SKILL, {}
            ask_look: dict[str, object] = {"target_entity_type": kind} if kind else {}
            return (
                SkillPlan((SkillCall(name="look_at_entity", target_entity_type=kind),)),
                f"face the {kind or target[0].entity_type}",
                ask_look,
            )
        if skill == "fight_back":
            named = arguments.get("target_entity_type")
            kind = named if isinstance(named, str) and named else ""
            target = nearest_visible(
                reading,
                kinds=frozenset({kind}) if kind else None,
                within=ATTACK_REACH_BLOCKS,
            )
            if target is None:
                # Nothing in reach to swing at (or nothing of the named kind): the same
                # no-op the feasible set never offers, refused here for a provider that
                # named it anyway.
                return None, NO_FEASIBLE_SKILL, {}
            swing = _asked_number(arguments, "swing_seconds")
            ask: dict[str, object] = {"swing_seconds": swing} if swing is not None else {}
            if kind:
                ask["target_entity_type"] = kind
            return (
                SkillPlan(
                    (
                        SkillCall(
                            name="fight_back",
                            swing_seconds=swing or 0.0,
                            target_entity_type=kind,
                        ),
                    )
                ),
                f"swing at the {kind or target[0].entity_type} in reach",
                ask,
            )
        if skill == "retreat":
            asked_hold = _asked_number(arguments, "hold_seconds")
            hostile = nearest_hostile(reading)
            hurt = self.recent_damage or self.just_respawned
            if hostile is None and asked_hold is None and not hurt:
                # Nothing visible to leave, nothing said about what to do about it: the
                # same no-op the feasible set never offers, refused here for a provider
                # that named it anyway.
                return None, NO_FEASIBLE_SKILL, {}
            if hostile is not None:
                hold = (
                    asked_hold
                    if asked_hold is not None
                    else (RETREAT_FLEE_SECONDS if hurt else 0.0)
                )
                reason = "step away from the nearest visible threat"
            else:
                # No bearing from the reading -- the damage is what the last two readings
                # disagreed about, so walk the heading the body already faces and let the
                # hold be the name of the claim.
                hold = RETREAT_FLEE_SECONDS if asked_hold is None else asked_hold
                reason = (
                    "get off the spot the last death happened on"
                    if self.just_respawned and not self.recent_damage
                    else "keep moving -- hurt, with nothing hostile in sight"
                )
            ask: dict[str, object] = {"hold_seconds": hold} if hold else {}
            return (
                SkillPlan((SkillCall(name="retreat", hold_seconds=hold),)),
                reason,
                ask,
            )
        if skill == "respawn":
            return SkillPlan((SkillCall(name="respawn"),)), "use the visible respawn button", {}
        if skill == "craft_take_result":
            target = self._asked_product(arguments)
            if not target:
                return None, NO_FEASIBLE_SKILL, {}
            quantity = _asked_quantity(arguments, self.goal, policy=self.policy)
            ask: dict[str, object] = {"target_item": target, "quantity": quantity}
            side = crafting_grid_side(reading)
            if item_total(reading.inventory, target) >= quantity:
                return None, GOAL_ACHIEVED, ask
            if self.craft_knowledge is not None:
                step = self.craft_knowledge.step_toward(
                    target,
                    reading,
                    quantity=quantity,
                    grid_side=side,
                    preferred=self._preferred_raw(),
                )
                if not isinstance(step, str):
                    toward = (
                        f"craft {target} from public version knowledge; GUI confirmation required"
                        if step.product_id == target
                        else (
                            f"craft {step.product_id} toward {target} from public version "
                            "knowledge; GUI confirmation required"
                        )
                    )
                    return (
                        SkillPlan(
                            (
                                SkillCall(
                                    name="craft_take_result",
                                    recipe_id=step.recipe.recipe_id,
                                    product_id=step.product_id,
                                    materials=step.materials,
                                ),
                            )
                        ),
                        toward,
                        ask,
                    )
                return None, step, ask
            step = step_to_run(reading, target, quantity, grid_side=side)
            if step is None:
                return (
                    None,
                    blocker_for(reading, target, quantity, grid_side=side)
                    or CRAFT_MATERIALS_MISSING,
                    ask,
                )
            return (
                SkillPlan(
                    (
                        SkillCall(
                            name="craft_take_result",
                            recipe_id=step.recipe.recipe_id,
                            product_id=step.product_id,
                            materials=step.materials,
                        ),
                    )
                ),
                (
                    f"craft {step.product_id}"
                    if step.product_id == target
                    else f"craft {step.product_id} toward {target}"
                ),
                ask,
            )
        if skill == "consume_item":
            # The ask may name the meal or leave it to this side; an answerer that named
            # nothing (and the rule order always names nothing) gets the reading's own
            # candidate — the largest curated food the hotbar can reach. Whatever the
            # name is, the skill's own precondition judges it against this same reading,
            # so a model's wrong guess becomes the skill's named refusal rather than a
            # key pressed on something that was never food.
            target = _asked_text(arguments, "target_item") or (consume_candidate(reading) or "")
            if not target:
                return None, ActionRefusal.CONSUME_ITEM_MISSING.value, {}
            refusal = consume_item_refusal(reading, target)
            if refusal.refusal is not None:
                return None, refusal.refusal.value, {"target_item": target}
            return (
                SkillPlan((SkillCall(name="consume_item", item_id=target),)),
                f"eat the {target} to answer the hunger bar",
                {"target_item": target},
            )
        if skill == "collect_dropped":
            item_id = _asked_text(arguments, "item_id") or self._resource_id(reading)
            if not item_id:
                return None, "NO_SEEN_DROP", {}
            walk = _asked_number(arguments, "walk_seconds")
            honoured_collect: dict[str, object] = {"item_id": item_id}
            if walk is None:
                # Nobody said: the skill's own default step, not a number this side invents.
                collect_plan = SkillPlan((SkillCall(name="collect_dropped", item_id=item_id),))
            else:
                honoured_collect["walk_seconds"] = walk
                collect_plan = SkillPlan(
                    (SkillCall(name="collect_dropped", item_id=item_id, walk_seconds=float(walk)),)
                )
            return (collect_plan, f"collect the {item_id} in view", honoured_collect)
        if skill == "break_seen_block":
            if reading.aim is None or reading.aim.block is None:
                return None, "MINE_TARGET_NOT_AIMED", {}
            block = reading.aim.block
            self.last_target_block = (block.x, block.y, block.z)
            # A landed aim ends the current re-aim sweep; the next lost-block turn starts a fresh
            # one from this block, rather than resuming an old sweep at a stale offset.
            self.reaim_probe = 0
            expected = _asked_text(arguments, "expected_drop_item")
            if not expected and self.policy is DecisionPolicy.RULES and self.goal is not None:
                # The rule strategy may borrow the milestone's source item as its own
                # expectation; a model's ask without one is an ask with no expectation, and
                # the operator's goal is not the model's belief about what the block drops.
                expected = self.goal.source_item_id
            return (
                SkillPlan((SkillCall(name="break_seen_block", expected_drop_item=expected),)),
                f"break the block in view for {expected or 'what it drops'}",
                {"expected_drop_item": expected},
            )
        if skill == "select_hotbar":
            asked_slot = _asked_number(arguments, "slot")
            if asked_slot is None or not asked_slot.is_integer():
                # The slot is the choice. There is no default slot and no goal substitution:
                # an ask that did not name one is refused by name. (The rule strategy's own
                # default is constructed in `_rule_arguments`, and only there.)
                return None, SKILL_ARGUMENT_MISSING, {}
            slot = int(asked_slot)
            if not 0 <= slot < HOTBAR_SLOT_COUNT:
                return None, ActionRefusal.HOTBAR_SLOT_OUT_OF_RANGE.value, {}
            expected_item = _asked_text(arguments, "expected_item_id")
            if expected_item and not any(
                stack.item_id == expected_item and stack.slot == slot
                for stack in reading.inventory.stacks
            ):
                # The expectation is part of the ask: selecting that slot while the reading
                # says it holds something else would be answering a different ask, and this
                # side never swaps in another slot or another item.
                return (
                    None,
                    SELECT_ITEM_NOT_IN_SLOT,
                    {"slot": slot, "expected_item_id": expected_item},
                )
            honoured_select: dict[str, object] = {"slot": slot}
            if expected_item:
                honoured_select["expected_item_id"] = expected_item
            if not expected_item:
                reason = f"select hotbar slot {slot}"
            elif self.goal is not None and expected_item == self.goal.product_id:
                reason = f"hold the {expected_item} in hand"
            else:
                reason = f"select the {expected_item} in slot {slot}"
            return (
                SkillPlan(
                    (SkillCall(name="select_hotbar", slot=slot, expected_item_id=expected_item),)
                ),
                reason,
                honoured_select,
            )
        if skill == "use_target":
            # The use key carries no argument: it acts on what the crosshair reports and what the
            # hand already holds, so the preconditions are the aim the skill itself checks. A
            # provider that answered use_target against a MISS/UNREAD aim, or one that can only
            # place into the player's own cell, is refused with the skill's own token — so the
            # mind falls through to a turn rather than spending a doomed click.
            refusal = use_target_refusal(reading)
            if refusal.refusal is not None:
                return None, refusal.refusal.value, {}
            return (
                SkillPlan((SkillCall(name="use_target"),)),
                "use the key on the thing in the crosshair — place against it, or open it",
                {},
            )
        if skill == CLOSE_SCREEN:
            # No argument to honour and nothing to read first: the skill checks its own pre-state
            # and closes on the reading that reports no handler. The mind only reaches here when
            # this reading already showed a window, so the step is never spent to change nothing.
            return (
                SkillPlan((SkillCall(name=CLOSE_SCREEN),)),
                "leave the open screen so the world can be acted on again",
                {},
            )
        self.scan_step += 1
        yaw = _asked_number(arguments, "yaw_degrees")
        pitch = _asked_number(arguments, "pitch_degrees")
        if yaw is None:
            reaim = self._reaim_at_resource(reading)
            if reaim is not None:
                return reaim
            yaw = (
                self.scan_step * SCAN_YAW_STEP_DEGREES
                + ((self.scan_step - 1) // 8 % 3) * SCAN_YAW_DRIFT_DEGREES
            ) % 360.0
        if pitch is None:
            pitch = SCAN_PITCH_CYCLE_DEGREES[(self.scan_step - 1) % len(SCAN_PITCH_CYCLE_DEGREES)]
        return (
            SkillPlan(
                (SkillCall(name="turn_to", yaw_degrees=yaw, pitch_degrees=pitch),),
            ),
            "look for the next thing the milestone needs",
            {"yaw_degrees": yaw, "pitch_degrees": pitch},
        )

    def _view_search_summary(self, reading: WorldObservationValue) -> dict[str, object]:
        """Camera suggestions from public body state and a previously observed crosshair cell.

        The remembered cell may now be empty. Its bearing is a place to look again, never a
        claim that a neighbouring block exists. Suggestions do not execute or replace model asks.
        """
        yaw = ((reading.self_state.yaw_degrees or 0.0) + SCAN_YAW_STEP_DEGREES) % 360.0
        pitches: tuple[float, ...] = SCAN_PITCH_CYCLE_DEGREES
        source = "body_angles"
        if (
            self.last_target_block is not None
            and self.goal is not None
            and self._goal_craft_blocker(reading) == CRAFT_MATERIALS_MISSING
        ):
            probe = self._reacquire_probe(reading)
            if probe is not None:
                yaw, pitches = probe
                source = "previously_seen_crosshair_cell"
        return {
            "source": source,
            "target_presence": "unconfirmed",
            "suggested_yaw_degrees": yaw,
            "suggested_pitch_degrees": pitches[self.scan_step % len(pitches)],
            "pitch_candidates_degrees": list(pitches),
        }

    def _reaim_at_resource(
        self, reading: WorldObservationValue
    ) -> tuple[SkillPlan, str, Mapping[str, object]] | None:
        """Turn back to the resource block this mind was just breaking, if that is the hold.

        A `collect` walks the player toward the drop it saw, and the fixed crosshair angle that
        pointed at the trunk now points at whatever is ahead — so `break_seen_block` leaves the
        feasible set and the rule order would otherwise blind-scan for the tree again. A player does
        not scan for a tree they were just felling; they face back toward it. This reproduces that
        single move from what the reading already reported: the block's own cell (remembered from
        the crosshair, never chunk-scanned) and the player's position, turned to the client's angle
        units by the same geometry the walk skill uses on a visible drop.

        It fires only while the standing milestone still owes its raw material — the reroute word
        `blocker_for` already uses for "go back to the resource" — so it never re-aims at a trunk
        the bag has finished paying for. It is a bounded sweep rather than a single turn: it holds
        the recalled cell's heading and steps the pitch ladder `_reacquire_probe` computes for the
        distance the reading reports, so a column whose reported block is now broken still gets
        its standing neighbours back in the crosshair — the offsets are one and two cells' worth
        of angle at that measured distance, not a fixed ladder that misses a column standing at
        three blocks. If a probe lands the crosshair on a block, building the next
        `break_seen_block` re-arms the memory and resets the sweep; when the probes run out with
        nothing seen the memory clears and the blind scan resumes, which is what bounds a felled
        tree from looping the turn.
        """

        if self.goal is None or self.last_target_block is None:
            return None
        if self._goal_craft_blocker(reading) != CRAFT_MATERIALS_MISSING:
            self.reaim_probe = 0
            return None
        if (
            reading.self_state.x is None
            or reading.self_state.y is None
            or reading.self_state.z is None
        ):
            # A reading that never reported a position has no offset to aim from: the memory
            # stays, the sweep resets, and this look falls back to the blind scan.
            self.reaim_probe = 0
            return None
        probe = self._reacquire_probe(reading)
        if probe is None:
            # The recalled geometry itself is unusable (a degenerate angle): the memory is worth
            # nothing, so it clears rather than being retried forever.
            self.reaim_probe = 0
            self.last_target_block = None
            return None
        yaw, ladder = probe
        if self.reaim_probe >= len(ladder):
            # The bounded sweep ran out without the crosshair landing a block: the column is gone
            # (or was never there), so clear the memory and let the blind scan resume — a felled
            # tree must not strand the run in an endless re-aim.
            self.reaim_probe = 0
            self.last_target_block = None
            return None
        # A pitch pinned to the recalled heading, one cell of the standing column per rung: it
        # names no neighbouring cell, it looks along a bearing the mind saw, and the crosshair
        # says what is there.
        pitch = ladder[self.reaim_probe]
        self.reaim_probe += 1
        return (
            SkillPlan((SkillCall(name="turn_to", yaw_degrees=yaw, pitch_degrees=pitch),)),
            "turn back to the resource block this mind was breaking",
            {"yaw_degrees": yaw, "pitch_degrees": pitch},
        )

    def _reacquire_probe(
        self, reading: WorldObservationValue
    ) -> tuple[float, tuple[float, ...]] | None:
        """The recalled cell's bearing and the pitch ladder that sweeps its column.

        The trunk's heading is the recalled cell's horizontal bearing — data the crosshair
        itself reported, so holding it is the authorized memory — and the rungs are the angles
        one and two cells above or below that bearing at the distance this reading reports:
        `Δ = atan(1 block / d)`, so 0, ±Δ, ±2Δ. The cell's own pitch is discarded (the standing
        column sits near the horizon or above the reported cell once that one is broken). A
        fixed ladder could not do this: at three blocks a column's members are ±16..20° apart
        from the remembered cell, and no fixed probe of ±30/±55 hit them — a live run turned
        away from a trunk with a usable log still standing in it. None when the geometry is
        unusable (no recall, or an undefined angle), which the callers treat as clearing the
        memory.
        """

        if self.last_target_block is None:
            return None
        self_x, self_y, self_z = reading.self_state.x, reading.self_state.y, reading.self_state.z
        if self_x is None or self_y is None or self_z is None:
            return None
        block_x, block_y, block_z = self.last_target_block
        try:
            yaw, _ = angle_to_degrees(
                dx=block_x + 0.5 - self_x,
                dy=block_y + 0.5 - self_y,
                dz=block_z + 0.5 - self_z,
            )
        except ValueError:
            return None
        horizontal = math.hypot(block_x + 0.5 - self_x, block_z + 0.5 - self_z)
        cell = math.degrees(math.atan2(1.0, max(horizontal, 0.5)))
        ladder: list[float] = []
        for offset in (0.0, cell, -cell, 2.0 * cell, -2.0 * cell):
            if -90.0 <= offset <= 90.0 and not any(
                math.isclose(offset, seen, abs_tol=1e-6) for seen in ladder
            ):
                ladder.append(offset)
        return yaw, tuple(ladder)

    def _asked_product(self, arguments: Mapping[str, object]) -> str:
        """Which product a craft ask is for: the answer's, or the standing milestone's.

        There is no third rung, and the milestone rung belongs to the rule strategy alone: an
        ask that names no product is refused by name rather than code picking one — the
        table's first payable option is a fact about the table, not a decision.
        """

        asked = _asked_text(arguments, "target_item")
        if asked:
            return asked
        if self.policy is DecisionPolicy.RULES and self.goal is not None:
            return self.goal.product_id
        return ""

    def _resource_id(self, reading: WorldObservationValue) -> str:
        """The item to pick up: the visible goal resource, or the nearest visible drop.

        A standing goal may say what it is built from; with no such name the mind takes what it can
        see, which is the item-agnostic answer and the one the summary already showed.
        """

        # A milestone names what is wanted, not what this observation saw. The
        # feasible offer permits collecting any visible drop; asking for an absent
        # goal resource would deterministically spend that skill's retry budget.
        if (
            self.goal is not None
            and self.goal.source_item_id
            and any(
                candidate.item_id == self.goal.source_item_id
                for candidate in _visible_item_entities(reading)
            )
        ):
            return self.goal.source_item_id
        drop = _nearest_drop(reading)
        return "" if drop is None or drop.item_id is None else drop.item_id

    def _hold(
        self,
        reason: str,
        reading: WorldObservationValue | None,
        *,
        model_refusal: str = "",
    ) -> MindIntent:
        """A named stop. `model_refusal` carries the deciding layer's own word for a hold that
        happened because its answer never landed, so the run document says which decision met
        which obstacle instead of only the stop's name.
        """

        intent = MindIntent(
            kind=MindDecisionKind.HOLD,
            plan=SkillPlan(()),
            reason=reason,
            observation_ref="" if reading is None else observation_ref(reading),
            model_refusal=model_refusal,
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
            "persona_context": None if self.persona is None else self.persona.decision_context(),
            "session_history": dict(self.session_history),
            "public_recipe_knowledge": None
            if self.craft_knowledge is None
            else self.craft_knowledge.as_document(),
            "milestone": None if self.goal is None else self.goal.as_document(),
            "goal_met": self.goal_met,
            "current_intent": None if intent is None else intent.as_document(),
            "executing_skill": "" if intent is None else intent.skill,
            "executing_arguments": {} if intent is None else dict(intent.arguments),
            "intent_observation_ref": "" if intent is None else intent.observation_ref,
            "decision_source": "" if intent is None else intent.source,
            "last_result": "" if result is None else result.result.value,
            "last_result_reason": "" if result is None else result.reason,
            "failure_attribution": "" if self.last_failure is None else self.last_failure.value,
            "last_precondition": self.last_precondition,
            "decision_policy": self.policy.value,
            "model_enabled": self.model_enabled,
            "model_refusal": self.last_model_refusal,
            "intent_generation": self.intent_generation,
            "excluded_skills": sorted(self.excluded),
            "retry_budget": RETRY_BUDGET_PER_SIGNATURE,
            "model_calls": self.ledger.calls,
            "model_spent_micro": self.ledger.spent,
            "model_cap_refusals": self.ledger.cap_refusals,
            # The newest call's redacted diagnostics -- attempts, the per-attempt budget,
            # elapsed time, the failed phase and the reason -- so a run that stopped on a
            # model failure carries the facts a timeout claim has to stand on instead of
            # only the word TIMEOUT.
            "last_model_call": (
                None if not self.ledger.records else self.ledger.records[-1].as_document()
            ),
        }


def mind_for(
    provider: DecisionProvider,
    ledger: CostLedger,
    *,
    kin_id: str = "",
    persona_seed: str = "",
    goal: Milestone | None = None,
    model_enabled: bool = True,
    policy: DecisionPolicy = DecisionPolicy.MODEL,
    persona: PersonaManifest | None = None,
    session_history: Mapping[str, object] | None = None,
    craft_knowledge: CraftKnowledge | None = None,
) -> PlayerMind:
    """Build a mind for one session from what the session already resolved.

    A function rather than a longer argument list at the call site, because the four things a
    caller has to settle first — which provider this operator configured, what is left of the run
    cap, whose persona this is, and what the Kin is working toward — are the same four the CLI
    already reads for the model and identity surfaces.

    `goal` has no default item. A caller that names none gets a mind that breaks what it is aimed
    at, collects what it sees, looks around, and crafts only what an ask tells it to — under the
    model policy every one of those steps is the model's; under the explicitly selected rules
    policy the order in `_reflect` decides them.

    `policy` defaults to `DecisionPolicy.MODEL` because autonomy is the product and the rules
    are a strategy the operator opts into; neither `off` nor a missing key selects it here.
    """

    return PlayerMind(
        provider=provider,
        ledger=ledger,
        kin_id=kin_id,
        persona_seed=persona_seed,
        goal=goal,
        model_enabled=model_enabled,
        policy=policy,
        persona=persona,
        session_history={} if session_history is None else dict(session_history),
        craft_knowledge=craft_knowledge,
    )
