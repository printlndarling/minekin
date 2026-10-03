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

`off` is a supported shape, not a degraded one. When there is no model — no credentials, a
stopped endpoint, a spend already at the cap — the provider's named refusal is recorded and the
local reflection below picks the next step from the same feasible set the model was
offered. Such a run reports a decision source of `local_reflection` in every projection of
it, so nobody reading the dashboard can mistake a deterministic shortlist for a model.
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
from minekin_core.application.world_skills import SkillCall
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
    Recipe,
    build_plan,
    grid_enabler_for,
    largest_grid_in_plan,
    plan_needs_larger_grid,
)
from minekin_core.domain.skill_parameters import BEHAVIOR_PARAMETERS, MAX_QUANTITY
from minekin_core.domain.world_actions import (
    ActionResultClass,
    SkillOutcome,
    angle_to_degrees,
    item_total,
    use_target_refusal,
    use_target_signature,
)

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

#: The pitch angles a resource re-aim probes while it holds the trunk's recalled heading. Measured
#: on a live run: `collect` parks the Kin beside the block it just broke, so aiming at that vacated
#: cell points steeply DOWN, while the members of a vertical trunk that still stand are near the
#: horizon or above it — a ±18° wobble off the vacated cell's own steep pitch never crossed the
#: horizon and found nothing, and only the blind scan's `+55` look-up landed the next log. So these
#: probes are absolute pitch angles that span that up-range, held at the recalled yaw. They are the
#: same kind of fixed look the blind scan already issues, only pinned to a heading the crosshair
#: reported — a bounded set of generic angles, NOT a neighbouring cell's coordinates, so which
#: block (if any) each probe reveals stays the client's word and not the mind's inference: the line
#: §5 draws between "look again along a heading I saw" and "recall a cell I never saw."
#: Bounded, so a trunk whose column is entirely gone sweeps these few angles, then clears the memory
#: and falls back to the blind scan rather than looping here forever.
REACQUIRE_PITCH_SWEEP_DEGREES: Final = (0.0, 55.0, -55.0, 30.0, -30.0, 85.0, -85.0)

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
_NOT_IMPLEMENTED_REASONS: Final = frozenset(
    {SKILL_UNKNOWN, SKILL_ARGUMENT_MISSING, CRAFT_GRID_TOO_SMALL, CRAFT_RECIPE_UNAVAILABLE}
)
_UNREADABLE_REASONS: Final = frozenset({NO_LATEST_OBSERVATION, NO_CONFIRMING_OBSERVATION})
_ABSENT_REASONS: Final = frozenset(
    {"NO_SEEN_DROP", CRAFT_MATERIALS_MISSING, "MINE_TARGET_NOT_AIMED"}
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
#: instead of merely finite.
_PRECONDITION_REROUTE: Final = frozenset({CRAFT_MATERIALS_MISSING, DECISION_PRECONDITION_CHANGED})
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
#: because a model's offer and the local fallback have to be the same list, not two lists that
#: happen to agree today. `close_screen` is deliberately absent from this standing list: it is the
#: one skill whose every reading is already a success *when no window is standing*, so offering it
#: then would invite a step spent to change nothing. It is offered in exactly the one case where a
#: step it takes does change the world — a container open on the client — which `feasible_skill_ids`
#: detects off the newest reading rather than from this list.
SKILL_OFFER: Final = _checked_offer(
    (
        "break_seen_block",
        "collect_dropped",
        "craft_take_result",
        "select_hotbar",
        "use_target",
        "turn_to",
    )
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

    return milestone is not None and milestone.held(reading) >= milestone.quantity


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
        return ()
    if screen_open(reading):
        if goal_in_hand(milestone, reading):
            return (CLOSE_SCREEN,)
        offer = [CLOSE_SCREEN]
        if craft_options(reading, grid_side=crafting_grid_side(reading)):
            offer.append("craft_take_result")
        return tuple(offer)
    feasible = {
        "break_seen_block" if reading.aim is not None and reading.aim.block is not None else "",
        "collect_dropped" if _nearest_drop(reading) is not None else "",
        "craft_take_result"
        if craft_options(reading, grid_side=crafting_grid_side(reading))
        else "",
        "select_hotbar"
        if select_target(milestone, reading, grid_side=crafting_grid_side(reading)) is not None
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
    still has something true to say about what the bag could become.
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
        "inventory": dict(sorted(counts.items())),
        "selected_slot": reading.self_state.selected_slot,
        "yaw_degrees": reading.self_state.yaw_degrees,
        "pitch_degrees": reading.self_state.pitch_degrees,
        "screen_open": screen_open(reading),
        "screen_id": "" if reading.gui is None else reading.gui.screen_id,
        "held_item": reading.self_state.main_hand_item_id or "",
        "aimed_block": aim.targeted_block_id if aim is not None and aim.block is not None else "",
        "dropped_items": dict(sorted(dropped.items())),
        "crafting_grid_side": side,
        "craft_options": list(craft_options(reading, grid_side=side)),
        "health": reading.self_state.health,
        "max_health": reading.self_state.max_health,
        "food": reading.self_state.food,
        "alive": reading.self_state.alive,
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


def _asked_quantity(arguments: Mapping[str, object], milestone: Milestone | None) -> int:
    """How many of a product the ask wants: the answer's number, or the milestone's, then one.

    The bounds are re-checked rather than trusted, even though `compose_decision` judged them,
    because the local fallback reaches here with no answer at all and the same arithmetic then has
    to hold. A quantity is capped at a stack because that is what the ask vocabulary says, and a
    plan that wanted more is a sequence of asks, not one of them.
    """

    asked = _asked_number(arguments, "quantity")
    if asked is not None and asked.is_integer() and 1 <= asked <= MAX_QUANTITY:
        return int(asked)
    if milestone is not None:
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
    persona: PersonaManifest | None = None
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
    #: Which `REACQUIRE_PITCH_SWEEP_DEGREES` offset the resource re-aim is on. It advances once per
    #: re-aim turn and resets when the block is re-armed (a `break_seen_block` follows a landed
    #: aim) or when the sweep exhausts and the memory clears — so the sweep is bounded and repeats
    #: only while a real aim is being chased, never across a felled trunk.
    reaim_probe: int = field(default=0, init=False)

    observed_drop_ids: set[tuple[int, str]] = field(
        default_factory=set[tuple[int, str]], init=False
    )
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

    def observe(self, reading: WorldObservationValue | None) -> None:
        """Say whether the direction is met, off a reading, because nothing else may say it.

        The skill that crafted the product already reached a `CONFIRMED` verdict of its own, and
        that verdict was itself derived from a pair of readings — this is a later one, taken after
        the intent was recorded. §4 closes a goal on the world's word, not on a decision's
        self-report, so it reads the inventory here. It reads it in both directions: the milestone
        is *holding* the thing, so a later reading that no longer has enough of one un-closes it and
        the Kin goes back to work rather than reporting an item it has lost.
        """

        if reading is not None:
            self.goal_met = goal_held(self.goal, reading)

    def next_intent(self, reading: WorldObservationValue | None) -> MindIntent:
        """Ask — of the model, or of the reflection below — what to do about this reading.

        The answer's arguments go to `_call_for` with the skill it names, and the reading decides:
        an ask this bag cannot pay for, or for a shape this screen cannot hold, becomes a hold
        filed under the name of that precondition rather than a click and not a silent substitution
        of the local choice. That is the local half of "本地负责前提判断" and it is what the run
        document is read for afterwards.
        """

        if reading is None:
            return self._hold(NO_LATEST_OBSERVATION, None)
        self.observe(reading)
        if not reading.self_state.alive:
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
        contents = _inventory_contents(reading)
        if contents != self.empty_container_inventory:
            self.empty_container_aim = None
        feasible = tuple(
            name for name in feasible_skill_ids(self.goal, reading) if name not in self.excluded
        )
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
        summary["recent_actions"] = list(self.recent_results)
        summary["view_search"] = self._view_search_summary(reading)
        request = DecisionRequest(
            observation_ref=observation_ref(reading),
            needs=needs_from(self.goal, reading),
            active_goal=self.direction,
            feasible_skill_ids=feasible,
            observation_summary=summary,
            persona_seed=self.persona_seed,
            persona=self.persona,
            budget_remaining_micro=self.ledger.remaining(),
            intent_generation=self.intent_generation,
        )
        answer = self.provider.decide(request)
        needs = needs_from(self.goal, reading)
        refusal = ""
        reason = ""
        arguments: Mapping[str, object] = {}
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
                arguments = answer.arguments
            else:
                refusal = UnavailableReason.DECISION_OUT_OF_BOUNDS.value
                skill, source = self._reflect(feasible, needs, reading), DECISION_FROM_LOCAL
        else:
            refusal = answer.reason.value
            skill, source = self._reflect(feasible, needs, reading), DECISION_FROM_LOCAL
        self.last_model_refusal = refusal
        plan, built_reason, honoured = self._call_for(skill, reading, arguments)
        if plan is None and built_reason == GOAL_ACHIEVED:
            # A model can ask for a quantity or intermediate product already held.
            # That closes its request, not the standing milestone checked above.
            built_reason = "REQUEST_ALREADY_SATISFIED"
        if (
            plan is None
            and self.goal is not None
            and built_reason in {"REQUEST_ALREADY_SATISFIED", CRAFT_MATERIALS_MISSING}
        ):
            self.last_precondition = built_reason
            refusal = refusal or built_reason
            self.last_model_refusal = refusal
            source, reason = DECISION_FROM_LOCAL, ""
            remaining = feasible
            # Every candidate comes from the observation's offer, and each is tried
            # once. An invalid model craft cannot stop an otherwise payable route,
            # or trap reflection retrying the same unaffordable craft indefinitely.
            while remaining and plan is None:
                skill = self._reflect(remaining, needs, reading)
                plan, built_reason, honoured = self._call_for(skill, reading, {})
                remaining = tuple(name for name in remaining if name != skill)
        if plan is None:
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
        """The order the local layer uses when no model answered.

        Finish what the inventory is short of, pick up what is already on the ground, break
        what is aimed at, then look — the look staying ahead of the use keeps the no-model
        fallback as conservative as it was, right-clicking the aimed block only as the last
        resort before the set is given up on. Reading the same two inputs a model was offered,
        the fallback cannot do something the model was not permitted to, and because it can act
        on every skill in that set it can also exhaust every one: a reading whose offers all keep
        failing reaches `NO_FEASIBLE_SKILL` instead of replaying a skill the run has already given
        up on. `safety` holds a Kin back from starting a break when it is badly hurt, because a
        broken trunk is not what a half-health reading is asking for.

        Stand up a selected wider-grid enabler once the bag can pay the remaining
        material debt. Premature setup can occupy the face or sightline needed for
        further gathering, and closing that window loses its grid context. The catalog's
        blocker and grid metadata select the transition, never a product-specific chain.
        Gathering with a named raw resource is conservative: a different block under the crosshair
        does not prove that breaking it yields the wanted item. A model may still choose the generic
        break for another reason, while the local gather looks again instead of excavating ground.
        """

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
        if "select_hotbar" in feasible:
            return "select_hotbar"
        if "craft_take_result" in feasible:
            return "craft_take_result"
        enabler = enabler_to_stand_up(self.goal, reading, grid_side=crafting_grid_side(reading))
        if (
            "use_target" in feasible
            and enabler is not None
            and reading.self_state.selected_slot == enabler[1]
            and self.goal is not None
            and blocker_for(
                reading,
                self.goal.product_id,
                self.goal.quantity,
                grid_side=crafting_grid_side(reading),
            )
            == CRAFT_GRID_TOO_SMALL
        ):
            return "use_target"
        if "collect_dropped" in feasible and needs.get("resource_security", 0) >= 5:
            return "collect_dropped"
        if (
            "break_seen_block" in feasible
            and needs.get("safety", 0) < 7
            and (
                self.goal is None
                or not self.goal.source_item_id
                or (
                    reading.aim is not None
                    and reading.aim.targeted_block_id == self.goal.source_item_id
                )
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

        if skill == "craft_take_result":
            target = self._asked_product(arguments, reading)
            if not target:
                return None, NO_FEASIBLE_SKILL, {}
            quantity = _asked_quantity(arguments, self.goal)
            ask: dict[str, object] = {"target_item": target, "quantity": quantity}
            side = crafting_grid_side(reading)
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
        if skill == "collect_dropped":
            item_id = _asked_text(arguments, "item_id") or self._resource_id(reading)
            if not item_id:
                return None, "NO_SEEN_DROP", {}
            return (
                SkillPlan((SkillCall(name="collect_dropped", item_id=item_id),)),
                f"collect the {item_id} in view",
                {"item_id": item_id},
            )
        if skill == "break_seen_block":
            if reading.aim is None or reading.aim.block is None:
                return None, "MINE_TARGET_NOT_AIMED", {}
            block = reading.aim.block
            self.last_target_block = (block.x, block.y, block.z)
            # A landed aim ends the current re-aim sweep; the next lost-block turn starts a fresh
            # one from this block, rather than resuming an old sweep at a stale offset.
            self.reaim_probe = 0
            expected = _asked_text(arguments, "expected_drop_item")
            if not expected:
                expected = self.goal.source_item_id if self.goal is not None else ""
            return (
                SkillPlan((SkillCall(name="break_seen_block", expected_drop_item=expected),)),
                f"break the block in view for {expected or 'what it drops'}",
                {"expected_drop_item": expected},
            )
        if skill == "select_hotbar":
            if self.goal is None:
                return None, NO_FEASIBLE_SKILL, {}
            target = select_target(self.goal, reading, grid_side=crafting_grid_side(reading))
            if target is None:
                return None, "NO_SELECT_TARGET", {}
            item_id, slot = target
            reason = (
                f"hold the {item_id} in hand"
                if item_id == self.goal.product_id
                else f"select the {item_id} to stand it up"
            )
            return (
                SkillPlan((SkillCall(name="select_hotbar", slot=slot, expected_item_id=item_id),)),
                reason,
                {"slot": slot, "expected_item_id": item_id},
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
            yaw = (self.scan_step * SCAN_YAW_STEP_DEGREES) % 360.0
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
        pitches = SCAN_PITCH_CYCLE_DEGREES
        source = "body_angles"
        position = (reading.self_state.x, reading.self_state.y, reading.self_state.z)
        if (
            self.last_target_block is not None
            and self.goal is not None
            and blocker_for(
                reading,
                self.goal.product_id,
                self.goal.quantity,
                grid_side=crafting_grid_side(reading),
            )
            == CRAFT_MATERIALS_MISSING
            and all(value is not None for value in position)
        ):
            x, y, z = position
            assert x is not None and y is not None and z is not None
            bx, by, bz = self.last_target_block
            try:
                yaw, _ = angle_to_degrees(dx=bx + 0.5 - x, dy=by + 0.5 - y, dz=bz + 0.5 - z)
            except ValueError:
                pass
            else:
                pitches = REACQUIRE_PITCH_SWEEP_DEGREES
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
        feasible set and the fallback would otherwise blind-scan for the tree again. A player does
        not scan for a tree they were just felling; they face back toward it. This reproduces that
        single move from what the reading already reported: the block's own cell (remembered from
        the crosshair, never chunk-scanned) and the player's position, turned to the client's angle
        units by the same geometry the walk skill uses on a visible drop.

        It fires only while the standing milestone still owes its raw material — the reroute word
        `blocker_for` already uses for "go back to the resource" — so it never re-aims at a trunk
        the bag has finished paying for. It is a bounded sweep rather than a single turn: it holds
        the recalled cell's heading and steps through `REACQUIRE_PITCH_SWEEP_DEGREES`, so a column
        whose reported block is now broken still gets its standing neighbours back in the
        crosshair. If a probe lands the crosshair on a block, building the next `break_seen_block`
        re-arms the memory and resets the sweep; when the probes run out with nothing seen the
        memory clears and the blind scan resumes, which is what bounds a felled tree from looping
        the turn. Every angle here is either the recalled heading or a generic pitch the blind scan
        already uses — the mind never names a cell the crosshair did not report, the line §5 draws.
        """

        if self.goal is None or self.last_target_block is None:
            return None
        if blocker_for(
            reading,
            self.goal.product_id,
            self.goal.quantity,
            grid_side=crafting_grid_side(reading),
        ) != (CRAFT_MATERIALS_MISSING):
            self.reaim_probe = 0
            return None
        self_x, self_y, self_z = reading.self_state.x, reading.self_state.y, reading.self_state.z
        if self_x is None or self_y is None or self_z is None:
            self.reaim_probe = 0
            return None
        block_x, block_y, block_z = self.last_target_block
        # The trunk's heading is the recalled cell's horizontal bearing — data the crosshair itself
        # reported, so holding it is the authorized memory. The cell's own pitch is discarded: the
        # standing column sits near the horizon or above it once the reported block is gone, so the
        # probes below are absolute generic pitches pinned to this heading, not an offset off the
        # vacated cell's (steeply-down) angle.
        try:
            yaw, _ = angle_to_degrees(
                dx=block_x + 0.5 - self_x,
                dy=block_y + 0.5 - self_y,
                dz=block_z + 0.5 - self_z,
            )
        except ValueError:
            self.reaim_probe = 0
            self.last_target_block = None
            return None
        if self.reaim_probe >= len(REACQUIRE_PITCH_SWEEP_DEGREES):
            # The bounded sweep ran out without the crosshair landing a block: the column is gone
            # (or was never there), so clear the memory and let the blind scan resume — a felled
            # tree must not strand the run in an endless re-aim.
            self.reaim_probe = 0
            self.last_target_block = None
            return None
        # A generic absolute pitch the blind scan already issues, only pinned to the recalled
        # heading: it names no neighbouring cell, it looks along a bearing the mind saw, and the
        # crosshair says what is there.
        pitch = REACQUIRE_PITCH_SWEEP_DEGREES[self.reaim_probe]
        self.reaim_probe += 1
        return (
            SkillPlan((SkillCall(name="turn_to", yaw_degrees=yaw, pitch_degrees=pitch),)),
            "turn back to the resource block this mind was breaking",
            {"yaw_degrees": yaw, "pitch_degrees": pitch},
        )

    def _asked_product(
        self, arguments: Mapping[str, object], reading: WorldObservationValue
    ) -> str:
        """Which product a craft ask is for: the answer's, then the milestone's, then the table's.

        The last rung is what lets a session with no standing milestone honour a craft ask at all —
        and it is the table's own first option, not a default item this module remembers, so a
        reflection with nothing to work toward still starts from a product the reading can pay for.
        """

        asked = _asked_text(arguments, "target_item")
        if asked:
            return asked
        if self.goal is not None:
            return self.goal.product_id
        options = craft_options(reading)
        return options[0] if options else ""

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
            "persona_context": None if self.persona is None else self.persona.decision_context(),
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
    goal: Milestone | None = None,
    model_enabled: bool = True,
    persona: PersonaManifest | None = None,
) -> PlayerMind:
    """Build a mind for one session from what the session already resolved.

    A function rather than a longer argument list at the call site, because the four things a
    caller has to settle first — which provider this operator configured, what is left of the run
    cap, whose persona this is, and what the Kin is working toward — are the same four the CLI
    already reads for the model and identity surfaces.

    `goal` has no default item. A caller that names none gets a mind that breaks what it is aimed
    at, collects what it sees, looks around, and crafts only what an ask tells it to.
    """

    return PlayerMind(
        provider=provider,
        ledger=ledger,
        kin_id=kin_id,
        persona_seed=persona_seed,
        goal=goal,
        model_enabled=model_enabled,
        persona=persona,
    )
