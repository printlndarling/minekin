"""The S2 skill surface: turn, break what was seen, collect, craft.

Four skills, and every one of them starts from a reading the client actually
made — §5's "all premised on having seen". There is no chunk scan here, no
pathfinding, no teleport and no creative give, because the wire has no field for
any of them and this layer will not improvise one.

What a skill may do and what it may *believe* are different modules: the named
refusals and the reading-verdicts live in `domain/world_actions`, and this
module only sequences them — check, send, wait for the next admitted
observation, conclude. A skill never reports `CONFIRMED` because the Bridge
answered `SUCCEEDED`: that answer means the client let go of the key, and every
row of §4 is about what the world looked like afterwards. Equally, a conclusion
of `UNKNOWN` is returned as `UNKNOWN` — the contract forbids auto-retrying a
click with a side effect on that word, and a skill that quietly retried would be
indistinguishable from a Kin that crafted the same pickaxe twice. Only steering
is re-sent while a skill works: the turn re-asks its angle because §3 names
`STARTED` + `AIM_IN_PROGRESS` as that skill's normal answer, and a collect
re-steps toward a drop it has not picked up yet, because walking to a thing is
the same class of command and a player chases what it can still see.

The lease is the caller's: like `InputPlan`, a skill asks under a lease it was
handed (`ActionAuthority`) and never arms the watchdog itself, so one arbiter
stays the only thing that decides who may drive the client.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Final, Protocol

from google.protobuf.message import Message

from minekin_core.application.action_outcomes import (
    ACCEPTED as ACTION_ACCEPTED,
)
from minekin_core.application.action_outcomes import (
    CANCELLED as ACTION_CANCELLED,
)
from minekin_core.application.action_outcomes import (
    FAILED as ACTION_FAILED,
)
from minekin_core.application.action_outcomes import (
    STARTED as ACTION_STARTED,
)
from minekin_core.application.action_outcomes import (
    SUCCEEDED as ACTION_SUCCEEDED,
)
from minekin_core.application.action_outcomes import ActionOutcomeRegistry
from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.domain.control_vocabulary import (
    AIM_CAPABILITY,
    AIM_INPUT_TYPE,
    CAPABILITY_NOT_GRANTED,
    GUI_CAPABILITY,
    GUI_CLICK_INPUT_TYPE,
    HOTBAR_CAPABILITY,
    HOTBAR_SELECT_INPUT_TYPE,
    MINE_CAPABILITY,
    MINE_INPUT_TYPE,
    MOVE_CAPABILITY,
    MOVE_INPUT_TYPE,
    RESPAWN_CAPABILITY,
    RESPAWN_INPUT_TYPE,
    SAY_CAPABILITY,
    SAY_INPUT_TYPE,
    SCREEN_CAPABILITY,
    SCREEN_INPUT_TYPE,
    USE_CAPABILITY,
    USE_INPUT_TYPE,
    monotonic_ns,
)
from minekin_core.domain.danger_catalog import (
    ATTACK_REACH_BLOCKS,
    nearest_hostile,
)
from minekin_core.domain.ids import OpaqueId
from minekin_core.domain.perception import (
    AimFace,
    AimKind,
    BlockTargetValue,
    EntityCandidate,
    InventoryValue,
    WorldObservationValue,
)
from minekin_core.domain.skill_parameters import MAX_SAY_CHARS
from minekin_core.domain.visible_entities import nearest_visible
from minekin_core.domain.world_actions import (
    ActionRefusal,
    ActionResultClass,
    SkillOutcome,
    angle_error_degrees,
    angle_to_degrees,
    consume_item_refusal,
    gui_click_refusal,
    hotbar_slot_for_item,
    hotbar_slot_refusal,
    item_total,
    mine_target_refusal,
    seen_drops,
    use_target_refusal,
    verify_block_broken,
    verify_consume_effect,
    verify_craft,
    verify_hotbar_change,
    verify_item_collected,
    verify_trade,
    verify_use_effect,
)
from minekin_core.generated.minekin.v1 import control_pb2

#: How close a turned angle has to be before the turn counts as arrived. Not a
#: clamp: the Bridge still owns the 20-degrees-per-command bound; this is only
#: the tolerance under which "facing the thing" is true of two float reads.
AIM_ARRIVAL_TOLERANCE_DEGREES: Final[float] = 2.0

#: How long one retreat step holds the forward key, and how far the body must have moved
#: for the step to count. Short by design: a retreat from a threat in sight is one step,
#: not a journey -- the mind re-reads the world between steps.
RETREAT_STEP_SECONDS: Final[float] = 1.5
#: How long the escape holds when the caller says it is hurt or names the hold itself:
#: about seventeen blocks of ground, past the eight-block threat reach and then some. The
#: one-step hold lost ground to pursuers that strike again in ten seconds -- measured on
#: the 2026-10-05 survival soak, 37 deaths around the world spawn in one night, almost all
#: landing between readings of a Kin that stood and scanned. The escalation is bounded: one
#: walk the caller named, and the mind re-reads the world after it either way.
RETREAT_FLEE_SECONDS: Final[float] = 4.0
#: The bounds a named hold has to sit inside. Below the floor a "step" the world can confirm
#: is not guaranteed; above the ceiling it stops being a step away and becomes a journey.
RETREAT_HOLD_MIN_SECONDS: Final[float] = 0.5
RETREAT_HOLD_MAX_SECONDS: Final[float] = 5.0
RETREAT_CONFIRM_BLOCKS: Final[float] = 0.5
#: What a retreat does when the world refused its step. A fresh frame that shows the
#: body in the same place is that refusal -- not slowness -- and one hop is the same
#: answer the other walkers give a wall. `RETREAT_STEP_SETTLE_SECONDS` is how long each
#: wait slice for that frame lives (past a bridge report cadence, so a frame that was
#: coming is not mistaken for silence), the reserve keeps a concluding frame affordable
#: after the hop, and the floor keeps the hop a hop.
RETREAT_STEP_SETTLE_SECONDS: Final[float] = 1.2
RETREAT_HOP_RESERVE_SECONDS: Final[float] = 0.8
RETREAT_MIN_HOP_SECONDS: Final[float] = 0.2
RETREAT_PATH_BLOCKED: Final[str] = "RETREAT_PATH_BLOCKED"
#: How long one fight holds the attack key, and the bounds a named swing sits inside. A
#: player's swing lands about twice a second, so this is a handful of swings at a naked
#: hostile -- and still short enough to re-read the world with the thing maybe still in it.
FIGHT_SWING_SECONDS: Final[float] = 3.0
FIGHT_SWING_MIN_SECONDS: Final[float] = 0.5
FIGHT_SWING_MAX_SECONDS: Final[float] = 8.0
#: How many presses one swing window may spend on a target that keeps dodging the
#: press frame. The operator's decision (2026-10-06): a bounded re-press inside the
#: window, and the bound's end concludes by the refusal's own name.
FIGHT_MAX_PRESS_ATTEMPTS: Final[int] = 3

#: How many chat lines one run may send. A cap, not a silence rule: the mind
#: chooses every line, and this is the executor's bound on how much a single run
#: can put into other people's screens — a chatty loop that keeps re-asking is
#: refused by name (`SAY_BUDGET_EXHAUSTED`) instead of talking forever.
SAY_BUDGET_PER_RUN: Final[int] = 20

#: The HUD line under which a fight breaks off: a body trading below it is the death the
#: soaks died, so the swing releases and the next decision may leave instead. The mind
#: reads the same number as its fight-or-flight line.
FIGHT_MIN_HEALTH: Final[float] = 13.0

#: The client's own standing eye height above its feet (1.20.1's constant). Entity offsets on
#: the wire are feet-to-feet, so an aim "at" an entity from the eye must drop by this much or
#: the ray flies over anything shorter than the eye: measured live on the fight run
#: b2e3ebeaa70b404ea5aaa3a12f1e96f1 -- a slime two blocks out stayed under a level aim, the
#: crosshair never read it, and the bridge refused every swing MINE_TARGET_NOT_AIMED (the
#: no-target guard doing exactly its job against an aim that was not on the thing).
EYE_HEIGHT_BLOCKS: Final[float] = 1.62

#: Why a skill stops waiting. The observation cadence is a constant of the
#: Bridge's build (10 tick), so a skill that never saw a newer reading inside
#: its own window is reporting the channel's silence, not the world's.
DEFAULT_STEP_TIMEOUT_NS: Final[int] = 5_000_000_000

#: How often a step's wait asks the launcher's supervisor about the client process.
#: The readings answer on the client's own cadence, so asking about the process far
#: more often costs nothing and bounds how long a step can keep waiting for a
#: verdict from a JVM that has already exited.
CLIENT_EXIT_POLL_S: Final[float] = 0.25

#: The reason a step carries when the thing that ended its wait was the client's own
#: exit rather than a reading. Named apart from `NO_CONFIRMING_OBSERVATION` because
#: the second is a channel that may still answer and the first is a process that
#: never will, and a plan that cannot tell them the same is a plan that retries.
CLIENT_EXITED: Final[str] = "CLIENT_EXITED"

#: How long one *correction* step of a chase lasts, in seconds. The plan's own
#: `walk_seconds` sizes the first approach to a drop; after that the Kin is
#: adjusting its position, and a full second approach per reading would spend the
#: whole step window walking. This is the same kind of internal sizing as the
#: turn's re-ask: it does not decide whether the pickup worked.
CHASE_STEP_SECONDS: Final[float] = 0.5

#: The window a chase needs left over, after the step's own walk, before it sends
#: another one: at least one observation interval (the Bridge reports every 10
#: tick), so the step has a newer reading to be concluded on rather than being
#: sent into a deadline that has already closed. A caller may ask for a
#: zero-second walk — the unit tests do — and without this floor such a chase
#: would re-send until the timeout.
CHASE_STEP_MIN_REMAINING_NS: Final[int] = 600_000_000

#: How many escapes one `close_screen` step may send. The craft leaves the window
#: open on purpose (its own contract forbids confirming a click before a frame says
#: the click landed), and the escape that closes it is a single key whose effect the
#: next frame may not have caught yet: a client that was still mid-frame when the
#: reading was taken reports the window standing, and the one reading after that says
#: it is gone. Sending the escape once and concluding on the first contradicting frame
#: is what turned a working escape into a `SCREEN_STILL_OPEN`. This re-sends the same
#: escape while frames keep arriving that still show the window — it never adds a
#: different action, so the ban on retrying a side-effecting click is not crossed,
#: only the number of times the player's own key goes out is bounded.
CLOSE_SCREEN_MAX_ESCAPES: Final[int] = 3

#: How long `use_target` holds the use key before letting go. The client
#: registers the use on its own tick, so a short press-and-release is exactly one
#: interaction; a longer hold is a player still pressing the button, which on a
#: block place repeats the placement and on nothing at all is a Kin leaving a key
#: down. The release is sent before the wait either way, so the tap ends even when
#: the reading never comes.
USE_TAP_SECONDS: Final[float] = 0.25

#: The longest `consume_item` holds the use key — a cap, not a fixed wait. The hold
#: ends on the first reading that shows the meal (bar up and stack down on one synced
#: frame), so a responsive channel releases within about one observation of the
#: completion; this cap only decides when nothing ever confirms. Eating is the one use
#: that *is* a hold: vanilla completes one item after 32 client ticks of continuous use
#: (1.6 s at 20 tps — 16 ticks for a snack-speed food like dried kelp), the client
#: starts counting on the tick after the key goes down, and it restarts the meal while
#: the key stays down. 2.5 s clears the slower completion plus one observation interval
#: (~0.5 s) even when a hitch stretches it, which is what keeps the release honest:
#: a second consecutive bite needs another full 16/32 ticks, so the frame that concludes
#: the hold always arrives before one could complete — one call confirms one item even
#: on a snack, where a blind hold of this length could have finished two. On the
#: no-confirmation path (a channel that answers nothing) the cap can still let a snack
#: complete twice; meals cannot, because two 32-tick completions would need 3.2 s and
#: the cap is below it.
CONSUME_HOLD_SECONDS: Final[float] = 2.5

#: How much nearer the nearest sighting of a drop has to come between two
#: corrections for a walk to count as closing on it. A correction that leaves the
#: drop no nearer is a step into a wall or a hole, not progress, and re-firing it is
#: the blind repeat the mind is meant to avoid rather than a chase.
COLLECT_CLOSE_APPROACH_METERS: Final[float] = 0.25

#: How many corrections in a row may fail to close before the step concludes the
#: approach has stalled. One is a reading taken mid-stride; this many is a Kin that
#: is not getting there, and it should stop spending the window walking and let the
#: mind re-aim or move somewhere else.
COLLECT_MAX_STALLED_CORRECTIONS: Final[int] = 3

#: How close an approach walks to a body before stopping (arm's reach, minus a step), how
#: long each step walks, and the most steps one approach takes before it concludes. Bounded
#: on purpose: a body behind a wall would otherwise be walked at until the whole window ran.
APPROACH_STOP_BLOCKS: Final[float] = 2.5
APPROACH_STEP_SECONDS: Final[float] = 1.0
#: The longest one step may walk, and the slice of the window kept back for the aim-ask
#: and the frame that follows it. Measured live (run 5afcfe84...: two one-second steps
#: toward a trader 11 blocks out, then APPROACH_NOT_CONFIRMED on the plan's five-second
#: window): walking the longest step the remaining budget supports -- instead of a fixed
#: one-second stride -- is what lets one call actually close a dozen blocks.
APPROACH_MAX_STEP_SECONDS: Final[float] = 2.5
APPROACH_WINDOW_RESERVE_SECONDS: Final[float] = 1.2
APPROACH_MAX_STEPS: Final[int] = 6

#: What a blocked step costs and what the walk does about it. A step that closed
#: less than this moved nothing — a reading caught mid-stride still shows a stride's
#: worth of closing, so this is a wall, not slowness. The answer is the one move the
#: game gives every walker for a one-block rise: hold jump for the next step. Two
#: blocked steps in a row (the first arming the hop, the second saying the hop did
#: not clear it) end the approach under its own name rather than walking at a wall
#: until the window runs out.
WALK_HOP_STALL_BLOCKS: Final[float] = 0.1
APPROACH_MAX_BLOCKED_STEPS: Final[int] = 2
APPROACH_PATH_BLOCKED: Final[str] = "APPROACH_PATH_BLOCKED"

#: What a `move_to` will walk for and how close it counts as arrived, in blocks,
#: and the coordinate bound beyond which a "place" is a mistake in the asking
#: rather than somewhere to walk. One call is a bounded errand, not a journey: a
#: place farther than this is refused by name, and the mind can chain steps.
MOVETO_ARRIVAL_BLOCKS: Final[float] = 1.0
MOVETO_MAX_BLOCKS: Final[float] = 64.0
MOVETO_MAX_COORDINATE: Final[float] = 30_000_000.0
MOVETO_MAX_STEPS: Final[int] = 12

#: How long a `collect` waits for a felled item to register as a rendered entity
#: before it concludes the drop is not in view. A `break` that CONFIRMED on the same
#: tick can leave the very next frame still empty — the failure `collect` used to end
#: on without ever stepping. This is a bounded settle, capped by the step's own
#: timeout; it parks on the store's wake and re-checks only readings the client admits,
#: so it waits for a fact the world will report rather than aiming at a cell the
#: crosshair did not see. A drop already in the first reading never enters it.
#:
#: The window has to span a whole report period to do its job: the Bridge publishes on a
#: 10-tick cadence (~500 ms at 20 tps), so a settle shorter than that returns before the
#: *next* frame is admitted and the drop it was waiting for could never have been seen.
#: An earlier 400 ms value did exactly that — it starved the autonomous loop, which then
#: saw the same `observation_ref` the failed `collect` was built on and stopped on
#: NO_FRESH_OBSERVATION before the mind could re-aim. This clears two cadences with margin
#: so a genuinely-registering drop is caught and, when it is not, real time has passed and
#: a fresh reading lets the mind re-aim instead of the loop stalling on the old one.
COLLECT_DROP_SETTLE_NS: Final[int] = 1_200_000_000

#: The two ways a chase ends because the world moved out from under it rather than
#: because the channel went quiet — both kept distinct from `NO_CONFIRMING_OBSERVATION`
#: so a reader can tell "it stopped being reachable" from "nothing ever arrived".
DROP_OUT_OF_VIEW: Final[str] = "DROP_OUT_OF_VIEW"
COLLECT_APPROACH_STALLED: Final[str] = "COLLECT_APPROACH_STALLED"

#: The wire's face enum, keyed by the domain token that names it. Closed
#: mapping: a face this build cannot spell is a refusal here, not a default on
#: the channel.
_WIRE_FACES: Final[dict[str, control_pb2.BlockFace]] = {
    AimFace.NOT_READ.value: control_pb2.BLOCK_FACE_UNSPECIFIED,
    AimFace.UNKNOWN.value: control_pb2.BLOCK_FACE_UNKNOWN,
    AimFace.DOWN.value: control_pb2.BLOCK_FACE_DOWN,
    AimFace.UP.value: control_pb2.BLOCK_FACE_UP,
    AimFace.NORTH.value: control_pb2.BLOCK_FACE_NORTH,
    AimFace.SOUTH.value: control_pb2.BLOCK_FACE_SOUTH,
    AimFace.WEST.value: control_pb2.BLOCK_FACE_WEST,
    AimFace.EAST.value: control_pb2.BLOCK_FACE_EAST,
}


class ControlSender(Protocol):
    """The transport as a skill sees it, named the way the host names it."""

    async def send_control(self, message_type: str, message: Message) -> None: ...


@dataclass(frozen=True, slots=True)
class ActionAuthority:
    """The lease the skill's commands go out under.

    Held by the caller because the arbiter that granted it is the only thing
    that knows whether it is still valid; a skill that invented its own lease
    would be a second door around the one that guards the input.
    """

    lease_id: str
    generation: int
    deadline_monotonic_ns: int


@dataclass(frozen=True, slots=True)
class SkillCall:
    """One skill named with everything it needs.

    The flat shape is deliberate: five skills, nine possible arguments, and a
    caller that has to say which of them it means without a branch per skill.
    Which arguments a name requires is `application.skill_plan`'s business, and
    the defaults here are what a call carries when nobody said — `slot=-1` is
    outside the nine on purpose, so a call that forgot its slot meets the
    contract's own `HOTBAR_SLOT_OUT_OF_RANGE` rather than a new word.

    `materials` is a tuple of pairs rather than a mapping so the call stays
    hashable: a plan is compared, keyed and re-read as evidence of what was asked
    for, and a dict field would make each of those a mutable surprise.
    """

    name: str
    #: A place to walk to, in the frame the client reports the body in; only
    #: `move_to` reads them, and the skill's own refusals name a silly value.
    x: float = 0.0
    z: float = 0.0
    yaw_degrees: float = 0.0
    pitch_degrees: float = 0.0
    item_id: str = ""
    slot: int = -1
    recipe_id: str = ""
    product_id: str = ""
    expected_drop_item: str = ""
    expected_item_id: str = ""
    walk_seconds: float = 1.0
    #: A retreat's hold, when the caller named one; zero is "nobody said", which is the
    #: skill's own default step.
    hold_seconds: float = 0.0
    #: A fight's swing time, when the caller named one; zero is the skill's own default hold.
    swing_seconds: float = 0.0
    #: The entity kind a fight aims for when the caller named one; empty is "the nearest
    #: rendered body in reach", and the type is never a filter of this side's choosing.
    target_entity_type: str = ""
    #: Which row of an open merchant's offer list a trade takes; -1 is "nobody said",
    #: which the plan layer refuses before a skill is ever asked.
    offer_index: int = -1
    #: How close an approach stops, in blocks; zero is the skill's own default reach.
    stop_within: float = 0.0
    #: The one line a `say` call speaks — the only free text a plan carries. Empty
    #: is "nobody said", which the skill refuses by name before the wire.
    text: str = ""
    materials: tuple[tuple[str, int], ...] = ()
    craft_all: bool = True


def _refusal_outcome(
    reason: str, action_id: str, pre: WorldObservationValue | None
) -> SkillOutcome:
    return SkillOutcome(
        result=ActionResultClass.FAILED,
        reason=reason,
        action_id=action_id,
        pre_tick=None if pre is None else pre.game_tick,
    )


def _say_text_refusal(text: object) -> str:
    """The Bridge's own rules re-checked before the wire — the same three words.

    Blank, past `MAX_SAY_CHARS`, or command-shaped (a leading slash the server
    would parse into an execution) is refused here first, so the common case never
    spends a wire round-trip to learn what this side already knew; the Bridge's
    identical checks stay as the second lock on the same door, and the words are
    spelled the same on both sides because the same line must read the same.
    """

    if not isinstance(text, str) or not text.strip():
        return ActionRefusal.SAY_TEXT_EMPTY.value
    if len(text) > MAX_SAY_CHARS:
        return ActionRefusal.SAY_TEXT_TOO_LONG.value
    if text.lstrip().startswith("/"):
        return ActionRefusal.SAY_TEXT_IS_A_COMMAND.value
    return ""


def _wire_target(target: BlockTargetValue) -> control_pb2.BlockTarget:
    face = _WIRE_FACES.get(target.face.value)
    if face is None:
        raise ValueError(f"the client reported a face this build cannot name: {target.face}")
    return control_pb2.BlockTarget(x=target.x, y=target.y, z=target.z, face=face)


def _chase_details(
    steps: int, newest: WorldObservationValue, *, item_id: str, jumps: int = 0
) -> dict[str, str]:
    """What the chase did, in the field the run document already carries for it.

    `post_tick` keeps its meaning — the reading that confirmed the pickup, so a
    null still says nothing confirmed it — and these two say whether anything
    arrived at all: how many steps went out, and the newest reading they were
    concluded against. Without them a `NO_CONFIRMING_OBSERVATION` cannot be told
    apart from the channel going silent, and the two are answered by changing
    different things. `jumps` is written only when hops went out, so a chase
    that never met a blocked step keeps the shape it always had.
    """

    details = {"steps": str(steps), "newest_checked_tick": str(newest.game_tick)}
    if jumps:
        details["jumps"] = str(jumps)
    drops = seen_drops(newest.visible_entities, item_id)
    if drops:
        nearest = min(drops, key=_drop_approach_distance)
        details["nearest_drop_horizontal_meters"] = f"{_drop_approach_distance(nearest):.3f}"
        details["nearest_drop_vertical_meters"] = f"{nearest.relative_y:.3f}"
    return details


def _drop_approach_distance(drop: EntityCandidate) -> float:
    """How far this sighting of the drop still lies along the ground the walk can
    cross — the horizontal offset's magnitude. Used to tell a walk that closed on
    the item from one that fired into a wall and left the drop exactly as far away.

    Horizontal, not three-dimensional, because the walk that closes on a drop only
    moves along the ground plane. A drop resting below the player — the block having
    broken at their feet, or the item lying in a hollow — carries a vertical offset
    no forward step can shrink, so a 3D measure would read that floor as an approach
    that never nears and call a closing chase stalled. The pickup itself is confirmed
    by the inventory delta, not by this number; this one only decides whether to keep
    walking or hand the move back, and that choice belongs to the plane the step moves."""

    return math.hypot(drop.relative_x, drop.relative_z)


def _craft_details(
    pre: WorldObservationValue,
    newest: WorldObservationValue,
    *,
    gui_open: bool,
    craft_all: bool,
) -> dict[str, str]:
    """Which of the three ways a craft can end without a word is the one that
    happened, in the field the run document already carries.

    The craft's `NO_CONFIRMING_OBSERVATION` has always been the least readable
    row in the demo: the client's tick stopped, or every frame was refused on
    the way in, or frames arrived whose inventory was never re-synced, are three
    different things to fix. These three say which: the newest tick read against
    the skill's own pre-tick answers the first two, and the revision pair answers
    the third — `verify_craft` can only conclude on a rise in the synced
    revision, so a pair that never moved means no frame worth concluding on
    ever reached it.

    `craft_all` names which click went out, because the two recipe clicks are
    different transactions: the plain one leaves the result on the cursor, which
    the synced inventory does not report, so a window can watch materials fall
    and still have nothing to confirm on.
    """

    return {
        "newest_checked_tick": str(newest.game_tick),
        "pre_inventory_revision": str(pre.inventory.revision),
        "newest_inventory_revision": str(newest.inventory.revision),
        "gui_open": "true" if gui_open else "false",
        "craft_all": "true" if craft_all else "false",
    }


def _take_result_details(
    pre: WorldObservationValue,
    newest: WorldObservationValue,
    *,
    gui_open: bool,
    clicks: list[str],
    deposit_slot: int | None = None,
) -> dict[str, str]:
    """Which clicks went out and which reading each was decided from.

    The transaction has three possible clicks, and each one that did not happen
    has a reading that says why it did not need to or could not. `clicks` is
    that sentence in order; `deposit_slot` names the slot the newest reading
    said was empty when the cursor click went out, so a later argument about
    what the cursor held can be had against bytes rather than memory.
    """

    details = {
        "newest_checked_tick": str(newest.game_tick),
        "pre_inventory_revision": str(pre.inventory.revision),
        "newest_inventory_revision": str(newest.inventory.revision),
        "gui_open": "true" if gui_open else "false",
        "craft_all": "false",
        "clicks": "+".join(clicks),
    }
    if deposit_slot is not None:
        details["deposit_slot"] = str(deposit_slot)
    return details


def _window_sync_id(observation: WorldObservationValue) -> str:
    """The handler id the reading says was standing, or ``""`` for no window.

    A `screen_id` cannot be the whole report: the live client names the player's own
    crafting window with an empty screen id while still giving its handler an id,
    so the id pair is the only field that distinguishes 'nothing was open' from
    'my inventory was' — and a `SCREEN_STILL_OPEN` argued without it is unreadable.
    """

    if observation.gui is None or observation.gui.sync_id is None:
        return ""
    return str(observation.gui.sync_id)


def _close_screen_details(
    pre: WorldObservationValue,
    newest: WorldObservationValue,
    *,
    already_closed: bool = False,
    escapes: int = 0,
) -> dict[str, str]:
    """Which window the skill set out to leave, and what the newest reading says
    is standing now.

    A close has only one fact to be concluded on — whether a handler id is still
    reported — and the two readings that answer it are the pre-state's window and
    the newest one. Naming both means a `SCREEN_STILL_OPEN` can be argued against
    the window the client reported rather than against the one Core asked about.

    `escapes` is how many times the player's own key went out. A close that sent one
    escape and gave up is a different thing to fix from one that sent three and still
    found the window standing, and the run document should say which it saw.
    """

    open_now = newest.gui is not None and newest.gui.sync_id is not None
    details = {
        "newest_checked_tick": str(newest.game_tick),
        "pre_screen_id": pre.gui.screen_id if pre.gui is not None else "",
        "pre_sync_id": _window_sync_id(pre),
        "newest_screen_id": newest.gui.screen_id if open_now and newest.gui is not None else "",
        "newest_sync_id": _window_sync_id(newest),
        "screen_open": "true" if open_now else "false",
        "escapes": str(escapes),
    }
    if already_closed:
        details["already_closed"] = "true"
    return details


def _use_details(
    pre: WorldObservationValue,
    newest: WorldObservationValue,
    *,
    held_item_id: str | None,
) -> dict[str, str]:
    """What the use key was holding, and which of its two effects the reading saw.

    A use confirms two different ways — a window opened, or the held item's synced
    count fell — and the run document should say which happened rather than leave
    it to be inferred from the item in hand. The two window handler ids are the
    same pair `close_screen` reports, so a use that opened a container and a close
    that found it standing can be read against each other; `held_item_id` names
    what was in hand at the ask, so a later argument about the placement is had
    against bytes rather than memory.
    """

    return {
        "newest_checked_tick": str(newest.game_tick),
        "held_item_id": held_item_id or "",
        "pre_sync_id": _window_sync_id(pre),
        "newest_sync_id": _window_sync_id(newest),
    }


def _consume_details(
    pre: WorldObservationValue,
    newest: WorldObservationValue,
    *,
    item_id: str,
) -> dict[str, str]:
    """What the two readings the verdict compared actually said, in the step's own
    fields — the hunger bar and the stack on either side of the meal.

    These are the same two facts `verify_consume_effect` concluded from, so the run
    document can be read without re-deriving them from frames that are gone: the
    player-visible health/hunger observations become durable at the one place they
    decided something. `newest_checked_tick` is the same word `_use_details` uses for
    the frame an expired wait was concluded against, so a confirmed step and an
    unknown one name their final reading the same way.
    """

    return {
        "newest_checked_tick": str(newest.game_tick),
        "item_id": item_id,
        "food_before": str(pre.self_state.food),
        "food_after": str(newest.self_state.food),
        "health_before": f"{pre.self_state.health:.1f}",
        "health_after": f"{newest.self_state.health:.1f}",
        "item_before": str(item_total(pre.inventory, item_id)),
        "item_after": str(item_total(newest.inventory, item_id)),
    }


def _player_screen_slot(inventory_slot: int) -> int | None:
    """One slot of the player's own inventory in the open screen's numbering.

    The synced reading reports `PlayerInventory` slots — the nine first — while
    a GUI click lands on the handler the screen opened: result 0, grid 1..4,
    then the twenty-seven, then the nine, then the armor. This mapping is that
    difference for the thirty-six carryable slots, and nothing else.
    """

    if 0 <= inventory_slot < 9:
        return inventory_slot + 32
    if 9 <= inventory_slot < 36:
        return inventory_slot - 4
    return None


def _first_empty_screen_slot(inventory: InventoryValue) -> int | None:
    """The first of the thirty-six a reading says carries nothing, or `None`.
    The bridge lists only non-empty stacks, so absence is the report of empty."""

    taken = {stack.slot for stack in inventory.stacks}
    for slot in range(36):
        if slot not in taken:
            return _player_screen_slot(slot)
    return None


def _newer_reading(game_tick: int) -> Callable[[WorldObservationValue], bool]:
    """A predicate on the tick it was made against, not on a variable that can
    still move: the wait chains across readings, and a closure over the loop's
    own name would judge each slice against whichever tick the loop happened to
    hold when it ran."""

    return lambda latest: latest.game_tick > game_tick


def _drop_arrives(item_id: str) -> Callable[[WorldObservationValue], bool]:
    """Whether this reading's own visible list reports the dropped item — the single
    fact the settle wait parks for, and nothing more. It reaches only as far as the
    client rendered and asks no question about an item it did not report."""

    return lambda latest: bool(seen_drops(latest.visible_entities, item_id))


def _meal_arrives(
    *, pre: WorldObservationValue, item_id: str
) -> Callable[[WorldObservationValue], bool]:
    """The predicate both of `consume_item`'s waits conclude on: a later reading whose
    own synced frame shows the meal — the bar up and the stack down, exactly the
    verdict the step reports. One predicate for the hold cap and the remaining step
    window, so the frame that ends the hold is never re-judged by a second rule."""

    def arrived(candidate: WorldObservationValue) -> bool:
        return (
            verify_consume_effect(pre=pre, post=candidate, item_id=item_id)
            is ActionResultClass.CONFIRMED
        )

    return arrived


def _turn_reading(
    game_tick: int, yaw_degrees: float, pitch_degrees: float
) -> Callable[[WorldObservationValue], bool]:
    """A reading worth concluding on for a turn: a newer one, or this same one
    already facing the ask — a player already looking at the thing does not owe
    the Kin a tick of waiting."""

    def predicate(latest: WorldObservationValue) -> bool:
        if latest.game_tick > game_tick:
            return True
        return latest.game_tick == game_tick and _angle_arrived(latest, yaw_degrees, pitch_degrees)

    return predicate


class ClientProcessExited(RuntimeError):
    """The client this run started has exited, so no later reading can arrive.

    A skill's verdict comes from a reading the client makes after the command, and a
    gone client will never make one. Waiting out the step would spend the whole
    timeout to conclude `UNKNOWN` about a fact Core can already prove from its own
    child process, so the wait gives up and names this instead. It derives from
    `RuntimeError` because a wait that reaches a caller which does not ask after the
    client must still end the run rather than hang.
    """

    def __init__(self, exit_code: int, *, action_id: str) -> None:
        super().__init__(f"the client process exited with code {exit_code}")
        self.exit_code = exit_code
        #: The ask this step was waiting on when the process went, empty when nothing
        #: had been sent yet. Core made that id itself and the command carrying it had
        #: already left, so an exit that does not name it drops the one fact about the
        #: in-flight command that this run still holds.
        self.action_id = action_id


class PlayerDied(RuntimeError):
    """An admitted body observation ended this action before its confirmation."""

    def __init__(self, *, action_id: str, game_tick: int) -> None:
        super().__init__("PLAYER_DEAD")
        self.action_id = action_id
        self.game_tick = game_tick
        self.release_failed = False


class SessionStopRequested(RuntimeError):
    """The operator asked this run to stop while an action was in flight.

    The step ends now, `INTERRUPTED` with this name, rather than waiting out its
    window: the run is being taken away, and the seconds left in the window are
    exactly the span in which the release the stopper is waiting for has to go
    out. A step that kept driving the client until its own timeout would also
    leave behind a timeout reason for an end that was not one. Derives from
    `RuntimeError` for the client-exit reason: a wait that reaches a caller which
    does not ask about stops must end the run rather than hang.
    """

    def __init__(self, *, action_id: str) -> None:
        super().__init__("SESSION_STOP_REQUESTED")
        self.action_id = action_id


def _client_still_running() -> int | None:
    return None


class WorldSkills:
    """The four S2 skills over one sender, one lease-holder and one store."""

    def __init__(
        self,
        *,
        sender: ControlSender,
        observations: WorldObservationStore,
        capabilities: frozenset[str],
        action_id: Callable[[], str] = lambda: OpaqueId.new().value,
        client_exit: Callable[[], int | None] = _client_still_running,
        stop_requested: Callable[[], bool] | None = None,
        action_outcomes: ActionOutcomeRegistry | None = None,
    ) -> None:
        self._sender = sender
        self._observations = observations
        self._capabilities = capabilities
        self._action_id = action_id
        self._client_exit = client_exit
        #: The operator's ask, as the session owns it. `None` means this run has
        #: nobody who could ask — the same shape `client_exit`'s default has for a
        #: caller that manages no process.
        self._stop_requested = stop_requested
        #: The session's per-action outcomes, when the caller has one: the Bridge's
        #: own answer for a press, which a swing reads before pressing again — and
        #: what the say skill reads for its confirmation, because speech has no
        #: world acknowledgement to conclude from.
        self._action_outcomes = action_outcomes
        #: How many say attempts this run has spent. An attempt counts even when
        #: the line is refused or never answered, because the bound exists so a
        #: failing send cannot loop forever — it is a run budget, not a rate, and
        #: every line inside it is still the mind's own choice.
        self._says_sent = 0
        self._body_start: ContextVar[int | None] = ContextVar("body_start", default=None)

    @asynccontextmanager
    async def body_attempt(self) -> AsyncGenerator[None]:
        """Scope an execution to the life observed at its start, including nested skills."""
        token = self._body_start.set(self._observations.death_count)
        try:
            yield
        finally:
            self._body_start.reset(token)

    def check_interruption(self, action_id: str) -> None:
        """Raise when the operator's ask or the body has ended this action.

        Two facts, one check, because they land at the same call sites and mean the
        same thing to a step: the reading that would answer it will not come the way
        it was going to. The ask is checked first — a run being taken away ends with
        the stop named, whatever the body was doing at the time — and it is checked
        wherever readings are, not only at the step boundary, so a chase or a fight
        is interrupted inside its window rather than after it.
        """

        if self._stop_requested is not None and self._stop_requested():
            raise SessionStopRequested(action_id=action_id)
        started = self._body_start.get()
        if started is not None and self._observations.death_count != started:
            tick = self._observations.last_death_tick
            assert tick is not None
            raise PlayerDied(action_id=action_id, game_tick=tick)

    @property
    def supports_respawn(self) -> bool:
        return RESPAWN_CAPABILITY in self._capabilities

    async def wait_for_respawn_availability(
        self, *, authority: ActionAuthority, timeout_ns: int
    ) -> WorldObservationValue | None:
        """Wait for the visible death-screen button without outliving a stop or client.

        No input has been sent yet, so interruption carries no action id. A dead
        body is expected here; the operator and process checks still apply.
        """
        self.check_interruption("")
        gone = self._client_exit()
        if gone is not None:
            raise ClientProcessExited(gone, action_id="")
        result = await self._outlive_client(
            self._observations.wait_until(
                lambda latest: (
                    latest.generation != authority.generation
                    or latest.self_state.alive
                    or latest.self_state.respawn_available is True
                ),
                timeout_s=min(timeout_ns / 1_000_000_000, 2.0),
            ),
            action_id="",
            allow_dead=True,
        )
        self.check_interruption("")
        gone = self._client_exit()
        if gone is not None:
            raise ClientProcessExited(gone, action_id="")
        return result

    def supports_say(self) -> bool:
        return SAY_CAPABILITY in self._capabilities

    def client_exit_code(self) -> int | None:
        """What the launcher's supervisor says about the client process, right now.

        `None` while it runs. The plan executor asks before a command goes out, so a
        Kin whose client is already gone is refused by name instead of timing out.
        """

        return self._client_exit()

    async def turn_to(
        self,
        *,
        yaw_degrees: float,
        pitch_degrees: float,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Aim at an absolute angle and conclude only when a reading says the
        angles arrived.

        The ask is not pre-cut into client-sized steps: one long turn goes out
        as one absolute target, and the client's `STARTED` + `AIM_IN_PROGRESS`
        answer is handled the way §3 says it must be — re-read the next
        observation and re-ask the same target against it, never assume the
        turn finished because it was asked.
        """

        capability = self._require(AIM_CAPABILITY)
        if capability is not None:
            return capability
        pre = self._observations.latest
        action_id = self._action_id()
        if not math.isfinite(yaw_degrees) or not -90.0 <= pitch_degrees <= 90.0:
            # Not the client's per-command clamp — a pitch past straight up or
            # down has no angle to arrive at, and a Core that sent one would be
            # starting a turn it can never conclude.
            return _refusal_outcome("AIM_ANGLE_IMPOSSIBLE", action_id, pre)
        deadline = monotonic_ns() + timeout_ns
        best_error: float | None = None
        sent_once = False
        while True:
            await self._sender.send_control(
                AIM_INPUT_TYPE,
                control_pb2.AimInput(
                    action_id=action_id,
                    lease_id=authority.lease_id,
                    generation=authority.generation,
                    yaw_degrees=yaw_degrees,
                    pitch_degrees=pitch_degrees,
                    deadline_monotonic_ns=authority.deadline_monotonic_ns,
                ),
            )
            sent_once = True
            base = pre
            if base is None:
                # Asked to turn before any reading had arrived: wait out the
                # window once, and the arriving reading becomes the pre-state.
                base = await self._wait_until(lambda latest: True, deadline, action_id=action_id)
            if base is None:
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="NO_LATEST_OBSERVATION",
                    action_id=action_id,
                )
            pre = base
            post = await self._wait_until(
                _turn_reading(base.game_tick, yaw_degrees, pitch_degrees),
                deadline,
                action_id=action_id,
            )
            if post is None:
                remaining = deadline - monotonic_ns()
                if remaining <= 0:
                    # The turn went out and the client is answering it in its
                    # own time. `STARTED` is the honest word after one send:
                    # not done, not failed, still the same action.
                    reached = ActionResultClass.STARTED if sent_once else ActionResultClass.UNKNOWN
                    return SkillOutcome(
                        result=reached,
                        reason="AIM_IN_PROGRESS",
                        action_id=action_id,
                        pre_tick=pre.game_tick,
                    )
                continue
            if _angle_arrived(post, yaw_degrees, pitch_degrees):
                return SkillOutcome(
                    result=ActionResultClass.CONFIRMED,
                    reason="",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=post.game_tick,
                )
            error = _angle_error(post, yaw_degrees, pitch_degrees)
            if error is None:
                # The reading carries no angles: there is nothing to conclude
                # from and no progress to watch. Keep the window running; only
                # the timeout may call this anything.
                continue
            if best_error is not None and error >= best_error - 1e-6:
                # The gap stopped closing while still wide: the client stopped
                # turning short of the ask, which is a failure to report rather
                # than a stall to retry blind.
                return SkillOutcome(
                    result=ActionResultClass.FAILED,
                    reason="AIM_STALLED",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=post.game_tick,
                )
            best_error = error
            # The next ask is aimed from this reading, not from the one before
            # it: a stall has to be a gap that stopped closing across two
            # readings, and a loop that kept its old base would call the same
            # observation stalled the moment it looked at it twice.
            pre = post

    async def break_seen_block(
        self,
        *,
        authority: ActionAuthority,
        expected_drop_item: str | None = None,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Mine the block the last observation's crosshair reports, and let the
        later observations say whether it fell."""

        capability = self._require(MINE_CAPABILITY)
        if capability is not None:
            return capability
        pre = self._observations.latest
        action_id = self._action_id()
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        aim = pre.aim
        block = aim.block if aim is not None and aim.kind is AimKind.BLOCK else None
        if block is None or not mine_target_refusal(pre, block, mining=True).accepted:
            # The §5 promise is that this skill's target is the block it *saw*.
            # With no block under the crosshair — or a crosshair since moved off
            # it, which the domain's face-tolerant check decides — there is
            # nothing to break, and the refusal is the §3 one, made before the
            # wire and carrying the §3 name.
            return _refusal_outcome(ActionRefusal.MINE_TARGET_NOT_AIMED.value, action_id, pre)
        target = block
        await self._send_mine(authority, action_id, target, mining=True)
        deadline = monotonic_ns() + timeout_ns
        async with self._release_on_exit(
            lambda: self._send_mine(authority, action_id, target, mining=False)
        ):
            chain = pre
            while True:
                post = await self._wait_until(
                    _newer_reading(chain.game_tick), deadline, action_id=action_id
                )
                if post is None:
                    # Either the window ran out or it is still open; only a closed
                    # window ends the wait.
                    if monotonic_ns() >= deadline:
                        return SkillOutcome(
                            result=ActionResultClass.UNKNOWN,
                            reason="NO_CONFIRMING_OBSERVATION",
                            action_id=action_id,
                            pre_tick=pre.game_tick,
                        )
                    continue
                verdict = verify_block_broken(
                    pre=chain,
                    post=post,
                    target=target,
                    expected_drop_item=expected_drop_item,
                )
                if verdict is not ActionResultClass.UNKNOWN:
                    # Whatever the reading said, the key comes back the way every
                    # hold ends: the same named stop, not a lease left to lapse.
                    return SkillOutcome(
                        result=verdict,
                        reason="" if verdict is ActionResultClass.CONFIRMED else "MINING_STALLED",
                        action_id=action_id,
                        pre_tick=pre.game_tick,
                        post_tick=post.game_tick,
                    )
                chain = post

    async def collect_dropped(
        self,
        *,
        item_id: str,
        authority: ActionAuthority,
        walk_seconds: float = 1.0,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Walk toward a drop that is on the visible list, and let the synced
        inventory say whether it came away. Nothing unseen is ever aimed at.

        The walk is chased, not fired once: a player that steps toward an item
        and does not have it looks at where the item is now and takes another
        step, and a Kin that stopped after one blind walk was a client that
        never looked again. Only movement is repeated here — §4's ban on
        auto-retrying a side-effecting click covers the craft click, not how the
        Kin gets to a thing it already sees — and the number of steps this sent
        is named in `details`, so the run document shows what went out.
        """

        for capability in (MOVE_CAPABILITY, AIM_CAPABILITY):
            refusal = self._require(capability)
            if refusal is not None:
                return refusal
        pre = self._observations.latest
        action_id = self._action_id()
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        deadline = monotonic_ns() + timeout_ns
        first_drops = seen_drops(pre.visible_entities, item_id)
        if not first_drops:
            # The felled item becomes a rendered entity a beat after the block breaks, so a
            # `break` that CONFIRMED on the same tick can leave this reading's list still
            # empty. Before concluding there is nothing to walk to, wait a short, bounded
            # settle for a newer reading the client admits that does report the drop. It parks
            # on the store's wake and re-checks only what the client rendered — it never aims
            # at a cell the crosshair did not see, so §5 holds. A drop already in the first
            # reading skips this entirely, leaving every confirmed collect on the exact path it
            # already ran.
            appeared = await self._wait_until(
                _drop_arrives(item_id),
                min(deadline, monotonic_ns() + COLLECT_DROP_SETTLE_NS),
                action_id=action_id,
            )
            if appeared is None:
                return _refusal_outcome("NO_SEEN_DROP", action_id, pre)
            pre = appeared
            first_drops = seen_drops(pre.visible_entities, item_id)
        chain = pre
        # The plan sizes the approach; the corrections after it are this module's
        # own short steps, so a whole window is not spent walking.
        steps = 1
        chase_reason = "NO_CONFIRMING_OBSERVATION"
        last_distance = _drop_approach_distance(first_drops[0])
        stalled = 0
        jumps = 0
        if not await self._walk_toward(
            action_id, authority, first_drops[0], walk_seconds, deadline
        ):
            latest = self._observations.latest
            if (
                latest is not None
                and verify_item_collected(pre=pre, post=latest, item_id=item_id)
                is ActionResultClass.CONFIRMED
            ):
                return SkillOutcome(
                    result=ActionResultClass.CONFIRMED,
                    reason="",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=latest.game_tick,
                    details=_chase_details(0, latest, item_id=item_id),
                )
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="COLLECT_AIM_NOT_CONFIRMED",
                action_id=action_id,
                pre_tick=pre.game_tick,
            )
        while True:
            post = await self._wait_until(
                _newer_reading(chain.game_tick), deadline, action_id=action_id
            )
            if post is None:
                break
            chain = post
            verdict = verify_item_collected(pre=pre, post=post, item_id=item_id)
            if verdict is not ActionResultClass.UNKNOWN:
                return SkillOutcome(
                    result=verdict,
                    reason="" if verdict is ActionResultClass.CONFIRMED else "DROP_NO_LONGER_SEEN",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=post.game_tick,
                    details=_chase_details(steps, post, item_id=item_id, jumps=jumps),
                )
            drops = seen_drops(post.visible_entities, item_id)
            if not drops:
                # The drop left the client's own view without ever arriving in the
                # bag. There is nothing to aim at, and standing to listen out the
                # rest of the window buys nothing: conclude so the mind re-scans for
                # where it went rather than replaying a walk toward an empty spot.
                chase_reason = DROP_OUT_OF_VIEW
                break
            walk_ns = round(CHASE_STEP_SECONDS * 1_000_000_000)
            if deadline - monotonic_ns() < walk_ns + CHASE_STEP_MIN_REMAINING_NS:
                # The correction no longer fits with a reading to conclude on: stop
                # here with the window's remaining silence, not a fresh stall signal.
                break
            distance = _drop_approach_distance(drops[0])
            if distance > last_distance - COLLECT_CLOSE_APPROACH_METERS:
                # A correction that did not bring the nearest sighting nearer along
                # the ground: the step is not closing on the item. One is a reading
                # caught mid-stride; this many is an approach that has stalled, and
                # the next move is a different one, not the same walk fired again.
                stalled += 1
                if stalled >= COLLECT_MAX_STALLED_CORRECTIONS:
                    chase_reason = COLLECT_APPROACH_STALLED
                    break
            else:
                stalled = 0
            last_distance = distance
            steps += 1
            # A step that just failed to close gets the walker's own answer to a
            # one-block rise: the next step holds jump. The reading after it says
            # whether the hop cleared the way, and the stall count above still
            # ends the chase by name if it did not.
            hop = stalled >= 1
            jumps += 1 if hop else 0
            if not await self._walk_toward(
                action_id, authority, drops[0], CHASE_STEP_SECONDS, deadline, hop=hop
            ):
                chase_reason = "COLLECT_AIM_NOT_CONFIRMED"
                break
        return SkillOutcome(
            result=ActionResultClass.UNKNOWN,
            reason=chase_reason,
            action_id=action_id,
            pre_tick=pre.game_tick,
            details=_chase_details(steps, chain, item_id=item_id, jumps=jumps),
        )

    async def _walk_toward(
        self,
        action_id: str,
        authority: ActionAuthority,
        drop: EntityCandidate,
        walk_seconds: float,
        deadline: int,
        *,
        hop: bool = False,
    ) -> bool:
        """Wait for the observed walking heading, then step and stop within the same budget.

        `hop` holds the jump key for this one step — the caller's answer to a
        previous step that closed nothing, which in this game is what clears a
        one-block rise. The release lets it go with the forward key: a jump that
        outlived its step would be its own kind of stuck.
        """

        yaw, pitch = angle_to_degrees(dx=drop.relative_x, dy=drop.relative_y, dz=drop.relative_z)
        await self._sender.send_control(
            AIM_INPUT_TYPE,
            control_pb2.AimInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                yaw_degrees=yaw,
                pitch_degrees=pitch,
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )
        arrived = await self._wait_until(
            lambda candidate: (
                candidate.self_state.yaw_degrees is not None
                and angle_error_degrees(
                    from_yaw=candidate.self_state.yaw_degrees,
                    to_yaw=yaw,
                    from_pitch=0.0,
                    to_pitch=0.0,
                )
                <= AIM_ARRIVAL_TOLERANCE_DEGREES
            ),
            deadline,
            action_id=action_id,
        )
        if arrived is None or deadline - monotonic_ns() < round(walk_seconds * 1_000_000_000):
            return False
        await self._send_walk(action_id, authority, forward=1.0, jump=hop)
        async with self._release_on_exit(
            lambda: self._send_walk(action_id, authority, forward=0.0)
        ):
            await self._sleep(walk_seconds, action_id=action_id)
        # The same named release the movement contract already guarantees — a
        # walk with no stop would be a Kin still walking into whatever is there,
        # and that is true of the last step of a chase as much as of the first.
        return True

    async def _send_walk(
        self,
        action_id: str,
        authority: ActionAuthority,
        *,
        forward: float,
        jump: bool = False,
    ) -> None:
        await self._sender.send_control(
            MOVE_INPUT_TYPE,
            control_pb2.MoveInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                forward=forward,
                jump=jump,
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )

    async def craft(
        self,
        *,
        recipe_id: str,
        materials: Mapping[str, int],
        product_id: str,
        authority: ActionAuthority,
        craft_all: bool = True,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """The 2x2 surface: check the materials are in the synced inventory,
        open the player's own screen through its real key path, click the
        recipe the game actually has — and confirm only on materials down and
        product up, both on the same synced revision.

        `craft_all` defaults to the transaction that finishes the job. The plain
        recipe click is the recipe book's single pick, which leaves the result on
        the cursor; the cursor is not part of the synced inventory the Kin reads,
        so a window spent watching that click can see materials fall and still
        never see a product. The craft-all click is the one that puts the result
        where the next reading can find it, which is also why it is spelled out
        in `details` rather than left implied.
        """

        for capability in (SCREEN_CAPABILITY, GUI_CAPABILITY):
            refusal = self._require(capability)
            if refusal is not None:
                return refusal
        pre = self._observations.latest
        action_id = self._action_id()
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        short = any(item_total(pre.inventory, item) < want for item, want in materials.items())
        if short:
            # §5's precondition, answered in the pre-state's own words: a Kin
            # that has not seen the planks does not open a window to wish.
            return _refusal_outcome("CRAFT_MATERIALS_MISSING", action_id, pre)
        deadline = monotonic_ns() + timeout_ns
        if pre.gui is None or pre.gui.sync_id is None:
            await self._sender.send_control(
                SCREEN_INPUT_TYPE,
                control_pb2.ScreenInput(
                    action_id=action_id,
                    lease_id=authority.lease_id,
                    generation=authority.generation,
                    control=control_pb2.SCREEN_CONTROL_OPEN_INVENTORY,
                    deadline_monotonic_ns=authority.deadline_monotonic_ns,
                ),
            )
            opened = await self._wait_until(
                lambda latest: latest.gui is not None and latest.gui.sync_id is not None,
                deadline,
                action_id=action_id,
            )
            if opened is None:
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="SCREEN_NOT_CONFIRMED",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    details=_craft_details(
                        pre,
                        self._observations.latest or pre,
                        gui_open=False,
                        craft_all=craft_all,
                    ),
                )
        screen = self._observations.latest
        if screen is None or screen.gui is None or screen.gui.sync_id is None:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="SCREEN_NOT_CONFIRMED",
                action_id=action_id,
                pre_tick=pre.game_tick,
                details=_craft_details(
                    pre,
                    screen or pre,
                    gui_open=False,
                    craft_all=craft_all,
                ),
            )
        refusal = gui_click_refusal(screen, screen.gui.sync_id)
        if refusal.refusal is not None:
            return _refusal_outcome(refusal.refusal.value, action_id, screen)
        await self._sender.send_control(
            GUI_CLICK_INPUT_TYPE,
            control_pb2.GuiClickInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                sync_id=screen.gui.sync_id,
                recipe=control_pb2.GuiRecipeClick(recipe_id=recipe_id, craft_all=craft_all),
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )
        # One click, one wait. The click has a side effect, and the contract's
        # rule for an inconclusive side-effecting click is the word `unknown`,
        # not a second click.
        chain = pre
        while True:
            post = await self._wait_until(
                _newer_reading(chain.game_tick), deadline, action_id=action_id
            )
            if post is None:
                if monotonic_ns() >= deadline:
                    return SkillOutcome(
                        result=ActionResultClass.UNKNOWN,
                        reason="NO_CONFIRMING_OBSERVATION",
                        action_id=action_id,
                        pre_tick=pre.game_tick,
                        details=_craft_details(pre, chain, gui_open=True, craft_all=craft_all),
                    )
                continue
            verdict = verify_craft(
                pre=pre, post=post, material_ids=tuple(materials), product_id=product_id
            )
            if verdict is not ActionResultClass.UNKNOWN:
                return SkillOutcome(
                    result=verdict,
                    reason="",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=post.game_tick,
                    details=_craft_details(pre, post, gui_open=True, craft_all=craft_all),
                )
            chain = post

    async def craft_take_result(
        self,
        *,
        recipe_id: str,
        materials: Mapping[str, int],
        product_id: str,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Finish the craft by clicking the result slot, not by trusting the
        recipe book's hand-off.

        Both recipe-book clicks were measured and neither ends where the Kin can
        read: the plain one leaves the product on the cursor, which the synced
        inventory does not report, and the craft-all one has never produced a
        confirming frame on the live bytes. This is the third way a player
        crafts: let the game fill the grid — it still owns the shape — and then
        shift-click result slot 0, the same click that puts a stack in the
        player's own hand.

        Every later click is decided from a reading and none is retried. The
        deposit exists only when the frames say the quick-move could not have
        delivered — materials gone, product unseen — and it aims at a slot the
        newest reading says is empty, because left-clicking an occupied one
        would trade the cursor for whatever stands there. If no slot reads
        empty the skill stops by name rather than gambling on a swap.
        """

        for capability in (SCREEN_CAPABILITY, GUI_CAPABILITY):
            refusal = self._require(capability)
            if refusal is not None:
                return refusal
        pre = self._observations.latest
        action_id = self._action_id()
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        if any(item_total(pre.inventory, item) < want for item, want in materials.items()):
            return _refusal_outcome("CRAFT_MATERIALS_MISSING", action_id, pre)
        deadline = monotonic_ns() + timeout_ns
        clicks: list[str] = []
        if pre.gui is None or pre.gui.sync_id is None:
            await self._sender.send_control(
                SCREEN_INPUT_TYPE,
                control_pb2.ScreenInput(
                    action_id=action_id,
                    lease_id=authority.lease_id,
                    generation=authority.generation,
                    control=control_pb2.SCREEN_CONTROL_OPEN_INVENTORY,
                    deadline_monotonic_ns=authority.deadline_monotonic_ns,
                ),
            )
            opened = await self._wait_until(
                lambda latest: latest.gui is not None and latest.gui.sync_id is not None,
                deadline,
                action_id=action_id,
            )
            if opened is None:
                screen = self._observations.latest or pre
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="SCREEN_NOT_CONFIRMED",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    details=_take_result_details(pre, screen, gui_open=False, clicks=clicks),
                )
        current = self._observations.latest
        if current is None or current.gui is None or current.gui.sync_id is None:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="SCREEN_NOT_CONFIRMED",
                action_id=action_id,
                pre_tick=pre.game_tick,
                details=_take_result_details(pre, current or pre, gui_open=False, clicks=clicks),
            )
        refusal = gui_click_refusal(current, current.gui.sync_id)
        if refusal.refusal is not None:
            return _refusal_outcome(refusal.refusal.value, action_id, current)
        await self._sender.send_control(
            GUI_CLICK_INPUT_TYPE,
            control_pb2.GuiClickInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                sync_id=current.gui.sync_id,
                recipe=control_pb2.GuiRecipeClick(recipe_id=recipe_id, craft_all=False),
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )
        clicks.append("recipe_fill")
        fill_sync_id = current.gui.sync_id
        # A new game tick can arrive before the server has populated the grid.
        # Inventory material leaving the same live handler is the visible fill
        # evidence available in this observation schema; an unchanged frame is
        # not permission to click an empty result slot. Never replay the fill.
        filled = await self._wait_until(
            lambda latest: (
                latest.game_tick > current.game_tick
                and (
                    latest.gui is None
                    or latest.gui.sync_id != fill_sync_id
                    or (
                        latest.inventory.revision > current.inventory.revision
                        and any(
                            item_total(latest.inventory, item) < item_total(current.inventory, item)
                            for item in materials
                        )
                    )
                )
            ),
            deadline,
            action_id=action_id,
        )
        if filled is None:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="NO_CONFIRMING_OBSERVATION",
                action_id=action_id,
                pre_tick=pre.game_tick,
                details=_take_result_details(pre, current, gui_open=True, clicks=clicks),
            )
        chain = filled
        if chain.gui is None or chain.gui.sync_id != fill_sync_id:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="SCREEN_NOT_CONFIRMED",
                action_id=action_id,
                pre_tick=pre.game_tick,
                details=_take_result_details(pre, chain, gui_open=False, clicks=clicks),
            )
        refusal = gui_click_refusal(chain, chain.gui.sync_id)
        if refusal.refusal is not None:
            return _refusal_outcome(refusal.refusal.value, action_id, chain)
        await self._sender.send_control(
            GUI_CLICK_INPUT_TYPE,
            control_pb2.GuiClickInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                sync_id=chain.gui.sync_id,
                slot=control_pb2.GuiSlotClick(
                    slot_id=0,
                    button=1,
                    mode=control_pb2.SLOT_CLICK_MODE_QUICK_MOVE,
                ),
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )
        clicks.append("result_quick_move")
        deposit_slot: int | None = None
        while True:
            post = await self._wait_until(
                _newer_reading(chain.game_tick), deadline, action_id=action_id
            )
            if post is None:
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="NO_CONFIRMING_OBSERVATION",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    details=_take_result_details(
                        pre, chain, gui_open=True, clicks=clicks, deposit_slot=deposit_slot
                    ),
                )
            verdict = verify_craft(
                pre=pre, post=post, material_ids=tuple(materials), product_id=product_id
            )
            if verdict is not ActionResultClass.UNKNOWN:
                return SkillOutcome(
                    result=verdict,
                    reason="",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=post.game_tick,
                    details=_take_result_details(
                        pre, post, gui_open=True, clicks=clicks, deposit_slot=deposit_slot
                    ),
                )
            gone = all(
                item_total(post.inventory, item) < item_total(pre.inventory, item)
                for item in materials
            )
            if gone and "cursor_deposit" not in clicks:
                empty = _first_empty_screen_slot(post.inventory)
                if empty is None:
                    return SkillOutcome(
                        result=ActionResultClass.UNKNOWN,
                        reason="CRAFT_NO_EMPTY_SLOT",
                        action_id=action_id,
                        pre_tick=pre.game_tick,
                        details=_take_result_details(pre, post, gui_open=True, clicks=clicks),
                    )
                if post.gui is None or post.gui.sync_id is None:
                    return SkillOutcome(
                        result=ActionResultClass.UNKNOWN,
                        reason="SCREEN_NOT_CONFIRMED",
                        action_id=action_id,
                        pre_tick=pre.game_tick,
                        details=_take_result_details(pre, post, gui_open=False, clicks=clicks),
                    )
                refusal = gui_click_refusal(post, post.gui.sync_id)
                if refusal.refusal is not None:
                    return _refusal_outcome(refusal.refusal.value, action_id, post)
                deposit_slot = empty
                await self._sender.send_control(
                    GUI_CLICK_INPUT_TYPE,
                    control_pb2.GuiClickInput(
                        action_id=action_id,
                        lease_id=authority.lease_id,
                        generation=authority.generation,
                        sync_id=post.gui.sync_id,
                        slot=control_pb2.GuiSlotClick(
                            slot_id=empty,
                            button=0,
                            mode=control_pb2.SLOT_CLICK_MODE_PICK,
                        ),
                        deadline_monotonic_ns=authority.deadline_monotonic_ns,
                    ),
                )
                clicks.append("cursor_deposit")
            chain = post

    async def close_screen(
        self,
        *,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Let go of the window the craft left standing, and conclude only on the
        reading that reports no handler.

        Every screen skill here ends with the window open — the craft's own
        contract forbids confirming a click before a frame says so — and none of
        them had a way back out, so a chain that stopped mid-craft left the
        player inside a container holding the keyboard. Closing is the client's
        own escape, named in the contract this build already answers, and the one
        fact that confirms it is the absence of a sync id: `0` is a legal handler
        for the player's inventory, so no id is the only reading that can say
        there is no window.
        """

        capability = self._require(SCREEN_CAPABILITY)
        if capability is not None:
            return capability
        pre = self._observations.latest
        action_id = self._action_id()
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        if pre.gui is None or pre.gui.sync_id is None:
            # The world already reads as asked. Nothing went out, because there
            # was nothing to escape.
            return SkillOutcome(
                result=ActionResultClass.CONFIRMED,
                reason="",
                action_id=action_id,
                pre_tick=pre.game_tick,
                post_tick=pre.game_tick,
                details=_close_screen_details(pre, pre, already_closed=True),
            )
        deadline = monotonic_ns() + timeout_ns
        escapes = 0
        watch_from = pre.game_tick
        while escapes < CLOSE_SCREEN_MAX_ESCAPES:
            escapes += 1
            await self._sender.send_control(
                SCREEN_INPUT_TYPE,
                control_pb2.ScreenInput(
                    action_id=action_id,
                    lease_id=authority.lease_id,
                    generation=authority.generation,
                    control=control_pb2.SCREEN_CONTROL_CLOSE,
                    deadline_monotonic_ns=authority.deadline_monotonic_ns,
                ),
            )
            # Wait for the next frame and read the window off it, rather than
            # waiting for the window to be gone. A frame that still reports the
            # handler is the reason the escape may not have landed yet — so the
            # loop sends it again; only a frame that reports no handler confirms it,
            # and only silence stops the listening.
            newer = await self._wait_until(
                _newer_reading(watch_from),
                deadline,
                action_id=action_id,
            )
            if newer is None:
                break
            watch_from = newer.game_tick
            if newer.gui is None or newer.gui.sync_id is None:
                return SkillOutcome(
                    result=ActionResultClass.CONFIRMED,
                    reason="",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=newer.game_tick,
                    details=_close_screen_details(pre, newer, escapes=escapes),
                )
        newest = self._observations.latest or pre
        if newest.game_tick > pre.game_tick:
            # Frames arrived and every one of them still reports the window, after
            # the bounded escapes. That is the reading contradicting the escape, not
            # a channel that never spoke.
            return SkillOutcome(
                result=ActionResultClass.FAILED,
                reason="SCREEN_STILL_OPEN",
                action_id=action_id,
                pre_tick=pre.game_tick,
                post_tick=newest.game_tick,
                details=_close_screen_details(pre, newest, escapes=escapes),
            )
        return SkillOutcome(
            result=ActionResultClass.UNKNOWN,
            reason="NO_CONFIRMING_OBSERVATION",
            action_id=action_id,
            pre_tick=pre.game_tick,
            details=_close_screen_details(pre, newest, escapes=escapes),
        )

    async def select_hotbar(
        self,
        *,
        slot: int,
        authority: ActionAuthority,
        expected_item_id: str | None = None,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Put one of the nine in hand — the number key, not the whole
        inventory — and let the next `self` reading say whose hand it was.

        Not one of §5's four, but the §4 hotbar row needs a sender to be a
        pair, and the next observation is the only answer either way.
        """

        capability = self._require(HOTBAR_CAPABILITY)
        if capability is not None:
            return capability
        action_id = self._action_id()
        refusal = hotbar_slot_refusal(slot)
        if refusal.refusal is not None:
            return _refusal_outcome(refusal.refusal.value, action_id, None)
        pre = self._observations.latest
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        await self._sender.send_control(
            HOTBAR_SELECT_INPUT_TYPE,
            control_pb2.HotbarSelectInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                slot=slot,
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )
        deadline = monotonic_ns() + timeout_ns
        post = await self._wait_until(
            lambda latest: latest.game_tick > pre.game_tick, deadline, action_id=action_id
        )
        if post is None:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="NO_CONFIRMING_OBSERVATION",
                action_id=action_id,
                pre_tick=pre.game_tick,
            )
        return SkillOutcome(
            result=verify_hotbar_change(
                pre=pre, post=post, slot=slot, expected_item_id=expected_item_id
            ),
            reason="",
            action_id=action_id,
            pre_tick=pre.game_tick,
            post_tick=post.game_tick,
        )

    async def use_target(
        self,
        *,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Right-click what the last observation's crosshair reports, and let the
        later readings say whether the world answered.

        The one general interaction skill: it places what is in hand against a
        block and activates an entity the client rendered, because the wire offers
        a single use key rather than a per-product door (§5's "no chunk scan" still
        holds — the target is the aim the client already read). It *taps*: press,
        the short hold the client needs to register one use, then release, rather
        than holding the key across the wait. A held use repeats a placement on
        every tick, and a Kin that stops on an unknown must not leave the button
        down — so the release goes out before the wait, and a channel that never
        answers still ends with the key let go.

        Nothing here decides the verdict: `verify_use_effect` concludes from the
        readings, and this method only presses the key and hands back what the
        after-picture said.
        """

        capability = self._require(USE_CAPABILITY)
        if capability is not None:
            return capability
        pre = self._observations.latest
        action_id = self._action_id()
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        refusal = use_target_refusal(pre)
        if refusal.refusal is not None:
            # §5 bounds this the way it bounds mining: the use fires on a thing the
            # client *saw*, and a crosshair on empty air or an aim never read is
            # the §3 refusal made before the wire, not a click into a hole.
            return _refusal_outcome(refusal.refusal.value, action_id, pre)
        held = pre.self_state.main_hand_item_id
        await self._send_use(authority, action_id, use=True)
        async with self._release_on_exit(lambda: self._send_use(authority, action_id, use=False)):
            await self._sleep(USE_TAP_SECONDS, action_id=action_id)
        deadline = monotonic_ns() + timeout_ns
        post = await self._wait_until(
            lambda candidate: (
                verify_use_effect(pre=pre, post=candidate, held_item_id=held)
                is ActionResultClass.CONFIRMED
            ),
            deadline,
            action_id=action_id,
        )
        if post is None:
            # A newer unchanged frame is not the final answer while the original
            # observation budget is still open. At expiry retain the latest frame
            # for an honest UNKNOWN, without sending another side-effecting tap.
            post = self._observations.latest
            if post is None or post.game_tick <= pre.game_tick:
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="NO_CONFIRMING_OBSERVATION",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                )
        return SkillOutcome(
            result=verify_use_effect(pre=pre, post=post, held_item_id=held),
            reason="",
            action_id=action_id,
            pre_tick=pre.game_tick,
            post_tick=post.game_tick,
            details=_use_details(pre, post, held_item_id=held),
        )

    async def consume_item(
        self,
        *,
        item_id: str,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Eat one known food: bring it to hand, hold the use key until the readings
        say the meal landed (bounded), and conclude from that same frame.

        The wire has no eat verb and does not need one: a player eats by holding the use
        key with the food in hand while the crosshair is on nothing — the same key
        `use_target` taps, held for the client's own eating time instead, under the same
        lease that already ends every held key. The hold ends on the first reading that
        shows the meal — the bar up and the stack down on one synced frame, the exact
        verdict this step reports — and never runs past `CONSUME_HOLD_SECONDS` when no
        reading does. The release therefore goes out even when the channel never answers,
        and because a second consecutive bite would need another full 16/32 ticks of
        held use, cancelling it is what makes one call confirm one item.

        Every phase is judged against the reading that precedes it: the refusal decides
        from `pre`, the selection has to be confirmed by a later `self` reading before
        the press, and the press's precondition is re-asked of the newest reading there
        is. One window (`timeout_ns`) covers all of it — the selection prep, the held
        meal and the concluding wait — because that is the window the plan's lease was
        sized for (`sequence_lease_seconds` grants `timeout + STEP_LEASE_HEADROOM_S`),
        and a step that quietly spent two windows could outlive its own lease.

        Nothing here decides the verdict: `verify_consume_effect` concludes from the
        readings, and this method only presses the key and hands back what the
        after-picture said. A hold that confirms nothing is `UNKNOWN`, and no second
        press follows it: one meal attempt per call, the same rule every side effect
        lives under.
        """

        for capability_name in (HOTBAR_CAPABILITY, USE_CAPABILITY):
            capability = self._require(capability_name)
            if capability is not None:
                return capability
        action_id = self._action_id()
        # One window for the whole skill, the way every other multi-send step spends
        # its own: the selection prep, the held meal and the concluding wait all draw
        # from this deadline, so the step can never outlive the lease headroom the plan
        # sized for a single wait window.
        deadline = monotonic_ns() + timeout_ns
        pre = self._observations.latest
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        refusal = consume_item_refusal(pre, item_id)
        if refusal.refusal is not None:
            return _refusal_outcome(refusal.refusal.value, action_id, pre)
        if pre.self_state.main_hand_item_id != item_id:
            slot = hotbar_slot_for_item(pre.inventory, item_id)
            # The refusal above admits only an item already held or one the hotbar can
            # reach, so the slot exists for every ask that gets this far.
            assert slot is not None
            selected = await self.select_hotbar(
                slot=slot,
                authority=authority,
                expected_item_id=item_id,
                # The selection gets what is left of the one window, so a slow
                # selection shortens the meal ahead rather than extending the step.
                timeout_ns=max(0, deadline - monotonic_ns()),
            )
            if selected.result is not ActionResultClass.CONFIRMED:
                # The number key's own verdict, kept verbatim and labelled with the
                # phase it belonged to: a selection that never confirmed is not a meal
                # that failed, and the reader of the document should not have to infer
                # which of the two steps the reading was about.
                return SkillOutcome(
                    result=selected.result,
                    reason=selected.reason,
                    action_id=selected.action_id,
                    pre_tick=selected.pre_tick,
                    post_tick=selected.post_tick,
                    details={**selected.details, "phase": "select_hotbar"},
                )
            pre = self._observations.latest
            if pre is None:
                return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        refusal = consume_item_refusal(pre, item_id)
        if refusal.refusal is not None:
            # Re-asked of the freshest frame, so a hunger bar that filled or an aim
            # that drifted between selection and press is named before the key goes
            # down rather than after a click it could not justify.
            return _refusal_outcome(refusal.refusal.value, action_id, pre)
        hold_ns = min(
            int(CONSUME_HOLD_SECONDS * 1_000_000_000),
            max(0, deadline - monotonic_ns()),
        )
        await self._send_use(authority, action_id, use=True)
        async with self._release_on_exit(lambda: self._send_use(authority, action_id, use=False)):
            post = await self._wait_until(
                _meal_arrives(pre=pre, item_id=item_id),
                monotonic_ns() + hold_ns,
                action_id=action_id,
            )
        if post is None:
            # Nothing confirmed while the key was down, so the wait continues on what
            # is left of the step's own window — the release has already gone out, and
            # no second press follows whatever the remaining window says.
            post = await self._wait_until(
                _meal_arrives(pre=pre, item_id=item_id),
                deadline,
                action_id=action_id,
            )
        if post is None:
            # A newer unchanged frame is not the final answer while the window is
            # still open. At expiry retain the latest frame for an honest UNKNOWN —
            # the key is already up, and no second press follows.
            post = self._observations.latest
            if post is None or post.game_tick <= pre.game_tick:
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="NO_CONFIRMING_OBSERVATION",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                )
        result = verify_consume_effect(pre=pre, post=post, item_id=item_id)
        return SkillOutcome(
            result=result,
            reason="NO_CONFIRMING_OBSERVATION" if result is ActionResultClass.UNKNOWN else "",
            action_id=action_id,
            pre_tick=pre.game_tick,
            post_tick=post.game_tick,
            details=_consume_details(pre, post, item_id=item_id),
        )

    async def respawn(
        self, *, authority: ActionAuthority, timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS
    ) -> SkillOutcome:
        """Ask once for the visible respawn affordance, then read the new live body."""
        pre = self._observations.latest
        if RESPAWN_CAPABILITY not in self._capabilities:
            return SkillOutcome(
                result=ActionResultClass.FAILED,
                reason=CAPABILITY_NOT_GRANTED,
                action_id="",
                details={"capability": RESPAWN_CAPABILITY},
            )
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", "", pre)
        if pre.generation != authority.generation:
            return _refusal_outcome("WORLD_GENERATION_CHANGED", "", pre)
        if pre.self_state.alive:
            return _refusal_outcome("RESPAWN_ALREADY_ALIVE", "", pre)
        if pre.self_state.respawn_available is not True:
            return _refusal_outcome("RESPAWN_UNAVAILABLE", "", pre)
        action_id = self._action_id()
        await self._sender.send_control(
            RESPAWN_INPUT_TYPE,
            control_pb2.RespawnInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )
        post = await self._outlive_client(
            self._observations.wait_until(
                lambda latest: (
                    latest.game_tick > pre.game_tick
                    and (latest.generation != authority.generation or latest.self_state.alive)
                ),
                timeout_s=timeout_ns / 1_000_000_000,
            ),
            action_id=action_id,
            allow_dead=True,
        )
        self.check_interruption(action_id)
        if post is None:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="RESPAWN_NOT_CONFIRMED",
                action_id=action_id,
                pre_tick=pre.game_tick,
            )
        if post.generation != authority.generation:
            return SkillOutcome(
                result=ActionResultClass.INTERRUPTED,
                reason="WORLD_GENERATION_CHANGED",
                action_id=action_id,
                pre_tick=pre.game_tick,
                post_tick=post.game_tick,
            )
        return SkillOutcome(
            result=ActionResultClass.CONFIRMED,
            reason="",
            action_id=action_id,
            pre_tick=pre.game_tick,
            post_tick=post.game_tick,
        )

    async def say(
        self,
        text: str,
        *,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """One chat line through the client's own send, confirmed by the client accepting it.

        Speech has no world acknowledgement — no later reading can say a line was
        heard — so this skill's confirmation is the one fact that exists: the client
        accepted the line for sending. That fact arrives as the Bridge's own
        `ActionResult` for this action id, read from the same per-action registry a
        swing reads its refusals from; `CLIENT_SENT` is the reason word, and nothing
        stronger is ever claimed. A caller with no registry keeps the optimistic
        shape the swing kept for its registry-less calls: the send call returned, so
        the step concludes on that. The refusals a bad line earns are named the same
        here as on the Bridge, because the same line must read the same whichever
        side of the channel stopped it.
        """

        if SAY_CAPABILITY not in self._capabilities:
            return SkillOutcome(
                result=ActionResultClass.FAILED,
                reason=CAPABILITY_NOT_GRANTED,
                action_id="",
                details={"capability": SAY_CAPABILITY},
            )
        refusal = _say_text_refusal(text)
        if refusal:
            return _refusal_outcome(refusal, "", self._observations.latest)
        if self._says_sent >= SAY_BUDGET_PER_RUN:
            return _refusal_outcome(
                ActionRefusal.SAY_BUDGET_EXHAUSTED.value, "", self._observations.latest
            )
        action_id = self._action_id()
        self._says_sent += 1
        await self._sender.send_control(
            SAY_INPUT_TYPE,
            control_pb2.SayInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
                text=text,
            ),
        )
        pre_tick = (
            None if self._observations.latest is None else self._observations.latest.game_tick
        )
        if self._action_outcomes is None:
            return SkillOutcome(
                result=ActionResultClass.CONFIRMED,
                reason="CLIENT_SENT",
                action_id=action_id,
                pre_tick=pre_tick,
            )
        outcome = await self._await_action_outcome(action_id, timeout_ns=timeout_ns)
        self.check_interruption(action_id)
        if outcome is None:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="SAY_NOT_CONFIRMED",
                action_id=action_id,
                pre_tick=pre_tick,
            )
        status, reason_code = outcome
        if status in (ACTION_FAILED, ACTION_CANCELLED):
            return SkillOutcome(
                result=ActionResultClass.FAILED,
                reason=reason_code or "SAY_REFUSED",
                action_id=action_id,
                pre_tick=pre_tick,
            )
        return SkillOutcome(
            result=ActionResultClass.CONFIRMED,
            reason="CLIENT_SENT",
            action_id=action_id,
            pre_tick=pre_tick,
        )

    async def _await_action_outcome(
        self, action_id: str, *, timeout_ns: int
    ) -> tuple[str, str] | None:
        """Poll the per-action registry until the Bridge answers for this id, or the window ends.

        The operator's ask and the body's end are checked every turn of the wait:
        a stop must interrupt inside this window, not after it — the same rule the
        skill windows already follow, applied to the one wait whose only reading
        is a registry entry. Measured (2026-10-07): with the check standing only
        after the wait, a stop that had already been asked ran out the whole
        window first.
        """

        outcomes = self._action_outcomes
        assert outcomes is not None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_ns / 1_000_000_000
        while True:
            outcome = outcomes.latest(action_id)
            if outcome is not None:
                return outcome
            self.check_interruption(action_id)
            if loop.time() >= deadline:
                return None
            await asyncio.sleep(0.05)

    async def retreat(
        self,
        *,
        authority: ActionAuthority,
        hold_seconds: float = 0.0,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Turn away from the nearest visible hostile and take one bounded step.

        The response run-89 never had: a night slime slew a Kin that kept working. With a
        hostile in sight the bearing is the reported offset's own geometry, reversed; the step
        is one hold of the same forward key `collect_dropped` walks with, released through the
        same named exit; and only a later frame whose position actually moved confirms it, so a
        step the world refused reads UNKNOWN rather than done.

        Without a visible hostile the step still exists when the caller names how long to hold
        it: a hit that arrived between readings left damage the skill can no longer see, so the
        named hold is the caller's claim -- walk the heading the body already faces, because the
        deaths in the 2026-10-05 soak (37 in one night around the spawn) all landed on a Kin
        that stood and scanned. A call with neither threat nor hold asks for nothing and is
        refused by name. One step per call on purpose: the mind re-reads the world between
        steps, and a retreat that has arrived keeps being reconsidered from what the next
        reading shows.
        """

        for capability in (MOVE_CAPABILITY, AIM_CAPABILITY):
            refusal = self._require(capability)
            if refusal is not None:
                return refusal
        pre = self._observations.latest
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", "", pre)
        if pre.generation != authority.generation:
            return _refusal_outcome("WORLD_GENERATION_CHANGED", "", pre)
        if pre.gui is not None and pre.gui.sync_id is not None:
            return _refusal_outcome("RETREAT_SCREEN_OPEN", "", pre)
        if hold_seconds and not (
            math.isfinite(hold_seconds)
            and RETREAT_HOLD_MIN_SECONDS <= hold_seconds <= RETREAT_HOLD_MAX_SECONDS
        ):
            return _refusal_outcome("RETREAT_HOLD_INVALID", "", pre)
        hostile = nearest_hostile(pre)
        if hostile is None and not hold_seconds:
            return _refusal_outcome("RETREAT_THREAT_NOT_VISIBLE", "", pre)
        hold = hold_seconds if hold_seconds else RETREAT_STEP_SECONDS
        action_id = self._action_id()
        deadline = monotonic_ns() + timeout_ns
        hostile_type = ""
        if hostile is not None:
            entity, _distance = hostile
            toward_yaw, _ = angle_to_degrees(
                dx=entity.relative_x, dy=entity.relative_y, dz=entity.relative_z
            )
            away_yaw = ((toward_yaw + 360.0) % 360.0) - 180.0
            if not await self._aim_until_arrived(
                action_id, authority, away_yaw, 0.0, base=pre, deadline=deadline
            ):
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="NO_CONFIRMING_OBSERVATION",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                )
            bearing = "away_from_visible_hostile"
            hostile_type = entity.entity_type
        else:
            # No bearing to take and none invented: the hold itself is the claim, and the
            # walk goes the way the body already faces -- standing still is what the deaths
            # were made of.
            bearing = "current_heading_on_named_hold"
        await self._send_walk(action_id, authority, forward=1.0)
        async with self._release_on_exit(
            lambda: self._send_walk(action_id, authority, forward=0.0)
        ):
            await self._sleep(hold, action_id=action_id)
        # The frames after the step, one slice at a time: a frame that shows the
        # body moved is the confirmation, and a frame that shows it in the same
        # place is the step the world refused. That refusal gets the walker's one
        # answer to a wall — a second step with jump held — and a further frame
        # that still shows no movement ends the retreat by name instead of walking
        # at the wall for the rest of the window. Silence stays `NOT_CONFIRMED`:
        # no frame said the world refused anything.
        hops = 0
        seen_tick = pre.game_tick
        post: WorldObservationValue | None = None
        while True:
            remaining_s = (deadline - monotonic_ns()) / 1_000_000_000
            if remaining_s <= 0:
                break
            fresh = await self._outlive_client(
                self._observations.wait_until(
                    _newer_reading(seen_tick),
                    timeout_s=min(remaining_s, RETREAT_STEP_SETTLE_SECONDS),
                ),
                action_id=action_id,
            )
            self.check_interruption(action_id)
            if fresh is None:
                # This slice said nothing; the deadline, not the slice, ends the wait.
                continue
            seen_tick = fresh.game_tick
            if fresh.generation != authority.generation or _walked_away(pre, fresh):
                post = fresh
                break
            if hops >= 1:
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason=RETREAT_PATH_BLOCKED,
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=fresh.game_tick,
                    details={
                        "hostile": hostile_type,
                        "bearing": bearing,
                        "hold_seconds": f"{hold:g}",
                        "jumps": str(hops),
                        "newest_checked_tick": str(fresh.game_tick),
                    },
                )
            hops = 1
            hop_seconds = min(
                hold, max(RETREAT_MIN_HOP_SECONDS, remaining_s - RETREAT_HOP_RESERVE_SECONDS)
            )
            await self._send_walk(action_id, authority, forward=1.0, jump=True)
            async with self._release_on_exit(
                lambda: self._send_walk(action_id, authority, forward=0.0)
            ):
                await self._sleep(hop_seconds, action_id=action_id)
        if post is None:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="RETREAT_NOT_CONFIRMED",
                action_id=action_id,
                pre_tick=pre.game_tick,
            )
        if post.generation != authority.generation:
            return SkillOutcome(
                result=ActionResultClass.INTERRUPTED,
                reason="WORLD_GENERATION_CHANGED",
                action_id=action_id,
                pre_tick=pre.game_tick,
                post_tick=post.game_tick,
            )
        moved = _horizontal_movement(pre, post)
        assert moved is not None  # the loop only accepts a frame that reports movement
        details = {
            "moved_blocks": f"{moved:.2f}",
            "hostile": hostile_type,
            "bearing": bearing,
            "hold_seconds": f"{hold:g}",
            "newest_checked_tick": str(post.game_tick),
        }
        if hops:
            details["jumps"] = str(hops)
        return SkillOutcome(
            result=ActionResultClass.CONFIRMED,
            reason="",
            action_id=action_id,
            pre_tick=pre.game_tick,
            post_tick=post.game_tick,
            details=details,
        )

    async def fight_back(
        self,
        *,
        authority: ActionAuthority,
        swing_seconds: float = 0.0,
        target_entity_type: str = "",
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Face the nearest rendered entity the reading reports in reach and swing at it.

        The other half of the 2026-10-05 night soaks' question: retreating walked the body
        away, and a camp that followed it never stopped. The target is the reported offset
        of a visible, in-sight hostile inside attack reach, aimed at with the same geometry
        a retreat reverses; the swings are one bounded hold of the same attack key the mine
        path holds, released through the same named exit, with NO block named -- the wire
        allows that only for an entity. Confirmation is the honest sentence and no more:
        a later reading no longer renders that entity, which is not the same claim as
        "it died" -- it may equally have left the view, and the next decision reads
        whatever is there. One hold per call on purpose: the mind re-reads the world
        between swings.
        """

        for capability in (MINE_CAPABILITY, AIM_CAPABILITY):
            refusal = self._require(capability)
            if refusal is not None:
                return refusal
        pre = self._observations.latest
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", "", pre)
        if pre.generation != authority.generation:
            return _refusal_outcome("WORLD_GENERATION_CHANGED", "", pre)
        if pre.gui is not None and pre.gui.sync_id is not None:
            return _refusal_outcome("FIGHT_SCREEN_OPEN", "", pre)
        if swing_seconds and not (
            math.isfinite(swing_seconds)
            and FIGHT_SWING_MIN_SECONDS <= swing_seconds <= FIGHT_SWING_MAX_SECONDS
        ):
            return _refusal_outcome("FIGHT_SWING_INVALID", "", pre)
        if nearest_visible(pre, line_of_sight=True) is None:
            return _refusal_outcome("FIGHT_THREAT_NOT_VISIBLE", "", pre)
        # Generic on purpose: ANY rendered body in reach is a legitimate target when the
        # deciding layer asked for it -- hostile, animal, trader, it is not this layer's
        # judgement what the type means. A named kind narrows the same scan; the local
        # reflex's choice to swing only at curated hostiles lives in the mind, not here.
        swing = swing_seconds if swing_seconds else FIGHT_SWING_SECONDS
        action_id = self._action_id()
        deadline = monotonic_ns() + timeout_ns
        wanted_kinds = frozenset({target_entity_type}) if target_entity_type else None
        target = nearest_visible(pre, kinds=wanted_kinds, within=ATTACK_REACH_BLOCKS)
        if target is None:
            # A body visible but just out of reach is a body that may be one hop away --
            # the enemy every fight is against moves itself. So the step spends its own
            # window asking the newest reading again, and when one reports the wanted
            # body in reach the aim and the swing follow from THAT frame. A window that
            # ends with nothing in reach refuses by the same name, decided on the latest
            # reading: the ask had its whole lease, so the words are earned.
            latest = await self._outlive_client(
                self._observations.wait_until(
                    lambda reading: (
                        reading.generation == authority.generation
                        and nearest_visible(reading, kinds=wanted_kinds, within=ATTACK_REACH_BLOCKS)
                        is not None
                    ),
                    timeout_s=max(0.1, (deadline - monotonic_ns()) / 1_000_000_000),
                ),
                action_id=action_id,
            )
            if latest is None:
                return _refusal_outcome(
                    "FIGHT_THREAT_OUT_OF_REACH", action_id, self._observations.latest or pre
                )
            pre = latest
            target = nearest_visible(pre, kinds=wanted_kinds, within=ATTACK_REACH_BLOCKS)
            assert target is not None
        entity, _distance = target
        yaw, pitch = angle_to_degrees(
            dx=entity.relative_x,
            dy=entity.relative_y - EYE_HEIGHT_BLOCKS,
            dz=entity.relative_z,
        )
        # A fight request authorizes attacking, not choosing equipment. The deciding
        # layer can issue select_hotbar first; this skill must preserve that choice,
        # including a weaker tool, an ordinary item or an empty hand.
        weapon_id = pre.self_state.main_hand_item_id or ""
        if not await self._aim_until_arrived(
            action_id, authority, yaw, pitch, base=pre, deadline=deadline
        ):
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="NO_CONFIRMING_OBSERVATION",
                action_id=action_id,
                pre_tick=pre.game_tick,
            )
        swing_verdict, presses, press_refusals = await self._swing_on_target(
            action_id,
            authority,
            entity,
            swing_seconds=swing,
            deadline=deadline,
        )
        if swing_verdict == "exhausted":
            # Every bounded press was refused by the Bridge's own aim gate: the
            # step concludes with the refusal's name and the attempt count.
            return SkillOutcome(
                result=ActionResultClass.FAILED,
                reason="MINE_TARGET_NOT_AIMED",
                action_id=action_id,
                pre_tick=pre.game_tick,
                details={
                    "target": entity.entity_type,
                    "swing_seconds": f"{swing:g}",
                    "presses": str(presses),
                    "press_refusals": str(press_refusals),
                },
            )
        post = await self._outlive_client(
            self._observations.wait_until(
                lambda latest: (
                    latest.game_tick > pre.game_tick
                    and (
                        latest.generation != authority.generation
                        or _target_unseen(entity.observation_id)(latest)
                    )
                ),
                timeout_s=max(0.1, (deadline - monotonic_ns()) / 1_000_000_000),
            ),
            action_id=action_id,
        )
        self.check_interruption(action_id)
        if post is None:
            details: dict[str, str] = {}
            if presses:
                details["presses"] = str(presses)
            if press_refusals:
                details["press_refusals"] = str(press_refusals)
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="FIGHT_NOT_CONFIRMED",
                action_id=action_id,
                pre_tick=pre.game_tick,
                details=details,
            )
        if post.generation != authority.generation:
            return SkillOutcome(
                result=ActionResultClass.INTERRUPTED,
                reason="WORLD_GENERATION_CHANGED",
                action_id=action_id,
                pre_tick=pre.game_tick,
                post_tick=post.game_tick,
            )
        confirmed_details = {
            "target": entity.entity_type,
            "swing_seconds": f"{swing:g}",
            "newest_checked_tick": str(post.game_tick),
            # The actual hand at the checked start of this action, not a catalog
            # recommendation or a claim that a weapon caused the outcome.
            "weapon": weapon_id,
        }
        # A fight that had to re-press says so: the refusals are why it may have
        # taken more than one frame to get a swing away.
        if presses:
            confirmed_details["presses"] = str(presses)
        if press_refusals:
            confirmed_details["press_refusals"] = str(press_refusals)
        return SkillOutcome(
            result=ActionResultClass.CONFIRMED,
            reason="",
            action_id=action_id,
            pre_tick=pre.game_tick,
            post_tick=post.game_tick,
            details=confirmed_details,
        )

    async def approach_entity(
        self,
        *,
        authority: ActionAuthority,
        target_entity_type: str = "",
        stop_within: float = 0.0,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Walk to a rendered body until the reading reports it within a named distance.

        The walk a collect takes toward a drop, pointed at any rendered entity: aim at the
        body's reported offset (re-asked until it lands), take one bounded step, then let
        the next reading size the next step -- a body that moves keeps being walked at from
        where it now is. CONFIRMED only when a reading reports the distance at or inside
        `stop_within`; a body that left the view mid-walk, or one the steps never closed
        on, concludes by name, and every step walks for a bounded time under the same
        named release as every other walk in this class.
        """

        for capability in (MOVE_CAPABILITY, AIM_CAPABILITY):
            refusal = self._require(capability)
            if refusal is not None:
                return refusal
        pre = self._observations.latest
        action_id = self._action_id()
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        if pre.generation != authority.generation:
            return _refusal_outcome("WORLD_GENERATION_CHANGED", action_id, pre)
        if pre.gui is not None and pre.gui.sync_id is not None:
            return _refusal_outcome("APPROACH_SCREEN_OPEN", action_id, pre)
        stop = stop_within if stop_within else APPROACH_STOP_BLOCKS
        if not math.isfinite(stop) or not 0.5 <= stop <= 8.0:
            return _refusal_outcome("APPROACH_STOP_INVALID", action_id, pre)
        first = nearest_visible(
            pre,
            kinds=frozenset({target_entity_type}) if target_entity_type else None,
        )
        if first is None:
            return _refusal_outcome("APPROACH_ENTITY_NOT_VISIBLE", action_id, pre)
        entity, distance = first
        deadline = monotonic_ns() + timeout_ns
        if distance <= stop:
            return SkillOutcome(
                result=ActionResultClass.CONFIRMED,
                reason="",
                action_id=action_id,
                pre_tick=pre.game_tick,
                post_tick=pre.game_tick,
                details={
                    "target": entity.entity_type,
                    "distance_blocks": f"{distance:.2f}",
                    "steps": "0",
                    "newest_checked_tick": str(pre.game_tick),
                },
            )
        steps = 0
        current = pre
        # A step that closes none of the gap gets the walker's answer to a wall:
        # the next step holds jump, and the reading after it decides. `jumps` is
        # the count of hops that actually went out, kept for the outcome.
        blocked = 0
        jumps = 0
        last_distance = distance
        while steps < APPROACH_MAX_STEPS:
            if monotonic_ns() >= deadline:
                break
            listed = next(
                (
                    candidate
                    for candidate in current.visible_entities
                    if candidate.observation_id == entity.observation_id
                ),
                None,
            )
            if listed is None:
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="APPROACH_ENTITY_GONE",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=current.game_tick,
                    details={
                        "target": entity.entity_type,
                        "steps": str(steps),
                        "newest_checked_tick": str(current.game_tick),
                    },
                )
            yaw, pitch = angle_to_degrees(
                dx=listed.relative_x,
                dy=listed.relative_y - EYE_HEIGHT_BLOCKS,
                dz=listed.relative_z,
            )
            if not await self._aim_until_arrived(
                action_id, authority, yaw, pitch, base=current, deadline=deadline
            ):
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="NO_CONFIRMING_OBSERVATION",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=current.game_tick,
                    details={"target": entity.entity_type, "steps": str(steps)},
                )
            remaining_s = (deadline - monotonic_ns()) / 1_000_000_000
            step_seconds = min(
                APPROACH_MAX_STEP_SECONDS,
                max(APPROACH_STEP_SECONDS, remaining_s - APPROACH_WINDOW_RESERVE_SECONDS),
            )
            hop = blocked >= 1
            jumps += 1 if hop else 0
            await self._send_walk(action_id, authority, forward=1.0, jump=hop)
            async with self._release_on_exit(
                lambda: self._send_walk(action_id, authority, forward=0.0)
            ):
                await self._sleep(step_seconds, action_id=action_id)
            steps += 1
            nxt = await self._wait_until(
                _newer_reading(current.game_tick), deadline, action_id=action_id
            )
            if nxt is None:
                break
            current = nxt
            listed_now = next(
                (
                    candidate
                    for candidate in current.visible_entities
                    if candidate.observation_id == entity.observation_id
                ),
                None,
            )
            if listed_now is None:
                continue  # the next loop pass names it gone
            now_distance = math.hypot(listed_now.relative_x, listed_now.relative_z)
            if now_distance <= stop:
                details = {
                    "target": entity.entity_type,
                    "distance_blocks": f"{now_distance:.2f}",
                    "steps": str(steps),
                    "newest_checked_tick": str(current.game_tick),
                }
                if jumps:
                    details["jumps"] = str(jumps)
                return SkillOutcome(
                    result=ActionResultClass.CONFIRMED,
                    reason="",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=current.game_tick,
                    details=details,
                )
            if last_distance - now_distance < WALK_HOP_STALL_BLOCKS:
                # The step closed nothing: a wall (or a rise the hop failed to
                # clear). The first one arms the next step's hop; this many in a
                # row ends the approach by name rather than walking at a wall
                # until the window runs out.
                blocked += 1
            else:
                blocked = 0
            last_distance = now_distance
            if blocked >= APPROACH_MAX_BLOCKED_STEPS:
                details = {
                    "target": entity.entity_type,
                    "distance_blocks": f"{now_distance:.2f}",
                    "steps": str(steps),
                    "newest_checked_tick": str(current.game_tick),
                }
                if jumps:
                    details["jumps"] = str(jumps)
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason=APPROACH_PATH_BLOCKED,
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=current.game_tick,
                    details=details,
                )
        latest = self._observations.latest or current
        return SkillOutcome(
            result=ActionResultClass.UNKNOWN,
            reason="APPROACH_NOT_CONFIRMED",
            action_id=action_id,
            pre_tick=pre.game_tick,
            post_tick=latest.game_tick,
            details={
                "target": entity.entity_type,
                "steps": str(steps),
                "newest_checked_tick": str(latest.game_tick),
            },
        )

    async def move_to(
        self,
        *,
        x: float,
        z: float,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Walk to a named place on the ground and confirm by the body's own readings.

        The place is a coordinate in the same frame the client reports the body in —
        the x/z a retreat measures movement against — so the bearing is computed
        from where the body says it is to where the caller said to go, re-aimed as
        the steps close on it. The step loop is the approach's, with the same
        blocked-step answer (one hop, then a named end), and arrival is a reading
        inside `MOVETO_ARRIVAL_BLOCKS`. A place past `MOVETO_MAX_BLOCKS` is refused
        by name rather than walked at for a window it cannot reach, and a reading
        that never says where the body is refuses too — absence is not zero.
        """

        for capability in (MOVE_CAPABILITY, AIM_CAPABILITY):
            refusal = self._require(capability)
            if refusal is not None:
                return refusal
        pre = self._observations.latest
        action_id = self._action_id()
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        if pre.generation != authority.generation:
            return _refusal_outcome("WORLD_GENERATION_CHANGED", action_id, pre)
        if pre.gui is not None and pre.gui.sync_id is not None:
            return _refusal_outcome("MOVE_SCREEN_OPEN", action_id, pre)
        if (
            not math.isfinite(x)
            or not math.isfinite(z)
            or abs(x) > MOVETO_MAX_COORDINATE
            or abs(z) > MOVETO_MAX_COORDINATE
        ):
            return _refusal_outcome("MOVE_TARGET_INVALID", action_id, pre)
        position = _horizontal_position(pre)
        if position is None:
            return _refusal_outcome("MOVE_POSITION_UNKNOWN", action_id, pre)
        px, pz = position
        distance = math.hypot(x - px, z - pz)
        if distance > MOVETO_MAX_BLOCKS:
            return SkillOutcome(
                result=ActionResultClass.FAILED,
                reason="MOVE_TARGET_TOO_FAR",
                action_id=action_id,
                pre_tick=pre.game_tick,
                details={"distance_blocks": f"{distance:.2f}"},
            )
        steps = 0
        jumps = 0

        def arrived(current: WorldObservationValue, distance: float) -> SkillOutcome:
            details = {
                "target": f"{x:.2f},{z:.2f}",
                "distance_blocks": f"{distance:.2f}",
                "steps": str(steps),
                "newest_checked_tick": str(current.game_tick),
            }
            if jumps:
                details["jumps"] = str(jumps)
            return SkillOutcome(
                result=ActionResultClass.CONFIRMED,
                reason="",
                action_id=action_id,
                pre_tick=pre.game_tick,
                post_tick=current.game_tick,
                details=details,
            )

        if distance <= MOVETO_ARRIVAL_BLOCKS:
            return arrived(pre, distance)
        deadline = monotonic_ns() + timeout_ns
        blocked = 0
        current = pre
        last_distance = distance
        while steps < MOVETO_MAX_STEPS:
            if monotonic_ns() >= deadline:
                break
            position = _horizontal_position(current)
            if position is None:
                # The reading that carried the body stopped saying where it is;
                # without that this walk cannot re-aim, and inventing a bearing
                # would be steering at nothing. Both refusals are named.
                return _refusal_outcome("MOVE_POSITION_UNKNOWN", action_id, current)
            px, pz = position
            bearing, _ = angle_to_degrees(dx=x - px, dy=0.0, dz=z - pz)
            if not await self._aim_until_arrived(
                action_id, authority, bearing, 0.0, base=current, deadline=deadline
            ):
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="NO_CONFIRMING_OBSERVATION",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=current.game_tick,
                    details={"target": f"{x:.2f},{z:.2f}", "steps": str(steps)},
                )
            # Turning can take several frames. Position or screen changes during
            # that wait must be read before pressing forward.
            latest = self._observations.latest
            reason = (
                "NO_LATEST_OBSERVATION"
                if latest is None
                else "WORLD_GENERATION_CHANGED"
                if latest.generation != authority.generation
                else "MOVE_SCREEN_OPEN"
                if latest.gui is not None and latest.gui.sync_id is not None
                else "MOVE_POSITION_UNKNOWN"
                if _horizontal_position(latest) is None
                else ""
            )
            if reason:
                return SkillOutcome(
                    result=ActionResultClass.FAILED,
                    reason=reason,
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=None if latest is None else latest.game_tick,
                )
            assert latest is not None
            current = latest
            position = _horizontal_position(current)
            assert position is not None
            last_distance = math.hypot(x - position[0], z - position[1])
            if last_distance <= MOVETO_ARRIVAL_BLOCKS:
                return arrived(current, last_distance)
            next_bearing, _ = angle_to_degrees(dx=x - position[0], dy=0.0, dz=z - position[1])
            if not _angle_arrived(current, next_bearing, 0.0):
                continue  # displacement changed the bearing; aim again before walking
            if monotonic_ns() >= deadline:
                break
            remaining_s = (deadline - monotonic_ns()) / 1_000_000_000
            step_seconds = min(
                APPROACH_MAX_STEP_SECONDS,
                max(APPROACH_STEP_SECONDS, remaining_s - APPROACH_WINDOW_RESERVE_SECONDS),
            )
            hop = blocked >= 1
            jumps += 1 if hop else 0
            await self._send_walk(action_id, authority, forward=1.0, jump=hop)
            async with self._release_on_exit(
                lambda: self._send_walk(action_id, authority, forward=0.0)
            ):
                await self._sleep(step_seconds, action_id=action_id)
            steps += 1
            nxt = await self._wait_until(
                _newer_reading(current.game_tick), deadline, action_id=action_id
            )
            if nxt is None:
                break
            current = nxt
            position = _horizontal_position(current)
            if position is None:
                continue  # the next loop pass names it unknown
            px, pz = position
            now_distance = math.hypot(x - px, z - pz)
            if now_distance <= MOVETO_ARRIVAL_BLOCKS:
                return arrived(current, now_distance)
            if last_distance - now_distance < WALK_HOP_STALL_BLOCKS:
                blocked += 1
            else:
                blocked = 0
            last_distance = now_distance
            if blocked >= APPROACH_MAX_BLOCKED_STEPS:
                details = {
                    "target": f"{x:.2f},{z:.2f}",
                    "distance_blocks": f"{now_distance:.2f}",
                    "steps": str(steps),
                    "newest_checked_tick": str(current.game_tick),
                }
                if jumps:
                    details["jumps"] = str(jumps)
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="MOVE_PATH_BLOCKED",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=current.game_tick,
                    details=details,
                )
        latest = self._observations.latest or current
        return SkillOutcome(
            result=ActionResultClass.UNKNOWN,
            reason="MOVE_NOT_CONFIRMED",
            action_id=action_id,
            pre_tick=pre.game_tick,
            post_tick=latest.game_tick,
            details={
                "target": f"{x:.2f},{z:.2f}",
                "steps": str(steps),
                "newest_checked_tick": str(latest.game_tick),
            },
        )

    async def look_at_entity(
        self,
        *,
        authority: ActionAuthority,
        target_entity_type: str = "",
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Face the nearest rendered body in sight, or the nearest of a named kind.

        The "look at it" leg any entity interaction starts from -- the same aim a fight
        takes before its swing, without the key -- and generic the same way: any rendered
        body in sight can be faced, and whether it is worth facing is the caller's call.
        No walking: a body out of arm's reach is beyond this step, and the caller composes
        more steps (or the world moves it) from the next reading.
        """

        capability = self._require(AIM_CAPABILITY)
        if capability is not None:
            return capability
        pre = self._observations.latest
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", "", pre)
        if pre.generation != authority.generation:
            return _refusal_outcome("WORLD_GENERATION_CHANGED", "", pre)
        if pre.gui is not None and pre.gui.sync_id is not None:
            return _refusal_outcome("LOOK_ENTITY_SCREEN_OPEN", "", pre)
        target = nearest_visible(
            pre,
            kinds=frozenset({target_entity_type}) if target_entity_type else None,
        )
        if target is None:
            return _refusal_outcome("LOOK_ENTITY_NOT_VISIBLE", "", pre)
        entity, distance = target
        yaw, pitch = angle_to_degrees(
            dx=entity.relative_x,
            dy=entity.relative_y - EYE_HEIGHT_BLOCKS,
            dz=entity.relative_z,
        )
        action_id = self._action_id()
        deadline = monotonic_ns() + timeout_ns
        if not await self._aim_until_arrived(
            action_id, authority, yaw, pitch, base=pre, deadline=deadline
        ):
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="NO_CONFIRMING_OBSERVATION",
                action_id=action_id,
                pre_tick=pre.game_tick,
            )
        post = self._observations.latest
        post_tick = (
            post.game_tick if post is not None and post.game_tick > pre.game_tick else pre.game_tick
        )
        return SkillOutcome(
            result=ActionResultClass.CONFIRMED,
            reason="",
            action_id=action_id,
            pre_tick=pre.game_tick,
            post_tick=post_tick,
            details={
                "target": entity.entity_type,
                "distance_blocks": f"{distance:.1f}",
                "newest_checked_tick": str(post_tick),
            },
        )

    async def trade(
        self,
        *,
        offer_index: int,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        """Take one row of the open merchant's offer list: select it, then quick-move the result.

        Two clicks, the same pair a craft ends with: a button click naming the row (the
        screen's own vocabulary, validated by the screen), then a quick move on the
        result slot -- the merchant screen's slot 2 -- which is the click that pays the
        asks and delivers the payout. Both preconditions are read, never assumed: the row
        exists in the reading's offer list, is not disabled or out of uses, and this bag
        can pay its asks right now; a click the numbers do not support is refused by name
        rather than spent. The verdict is the world's, `verify_trade`'s row: asks down and
        payout up on one synced revision, or UNKNOWN.
        """

        for capability in (SCREEN_CAPABILITY, GUI_CAPABILITY):
            refusal = self._require(capability)
            if refusal is not None:
                return refusal
        pre = self._observations.latest
        action_id = self._action_id()
        if pre is None:
            return _refusal_outcome("NO_LATEST_OBSERVATION", action_id, pre)
        if pre.gui is None or pre.gui.sync_id is None:
            return _refusal_outcome("TRADE_SCREEN_NOT_OPEN", action_id, pre)
        offers = pre.gui.trade_offers
        if offer_index < 0 or offer_index >= len(offers):
            return _refusal_outcome("TRADE_OFFER_UNKNOWN", action_id, pre)
        offer = offers[offer_index]
        if offer.disabled or offer.uses >= offer.max_uses:
            return _refusal_outcome("TRADE_OFFER_SPENT", action_id, pre)
        if item_total(pre.inventory, offer.first_item_id) < offer.first_count or (
            offer.second_item_id
            and item_total(pre.inventory, offer.second_item_id) < offer.second_count
        ):
            return _refusal_outcome("TRADE_INSUFFICIENT_MATERIALS", action_id, pre)
        refusal = gui_click_refusal(pre, pre.gui.sync_id)
        if refusal.refusal is not None:
            return _refusal_outcome(refusal.refusal.value, action_id, pre)
        deadline = monotonic_ns() + timeout_ns
        clicks: list[str] = []
        await self._sender.send_control(
            GUI_CLICK_INPUT_TYPE,
            control_pb2.GuiClickInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                sync_id=pre.gui.sync_id,
                button=control_pb2.GuiButtonClick(button_id=offer_index),
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )
        clicks.append("offer_select")
        selected = await self._wait_until(
            _newer_reading(pre.game_tick), deadline, action_id=action_id
        )
        if selected is None:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="NO_CONFIRMING_OBSERVATION",
                action_id=action_id,
                pre_tick=pre.game_tick,
                details=_trade_details(pre, None, offer_index, clicks),
            )
        if selected.gui is None or selected.gui.sync_id != pre.gui.sync_id:
            return SkillOutcome(
                result=ActionResultClass.UNKNOWN,
                reason="SCREEN_NOT_CONFIRMED",
                action_id=action_id,
                pre_tick=pre.game_tick,
                details=_trade_details(pre, selected, offer_index, clicks),
            )
        await self._sender.send_control(
            GUI_CLICK_INPUT_TYPE,
            control_pb2.GuiClickInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                sync_id=selected.gui.sync_id,
                slot=control_pb2.GuiSlotClick(
                    slot_id=2,
                    button=1,
                    mode=control_pb2.SLOT_CLICK_MODE_QUICK_MOVE,
                ),
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )
        clicks.append("result_quick_move")
        chain = selected
        while True:
            post = await self._wait_until(
                _newer_reading(chain.game_tick), deadline, action_id=action_id
            )
            if post is None:
                return SkillOutcome(
                    result=ActionResultClass.UNKNOWN,
                    reason="TRADE_NOT_CONFIRMED",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    details=_trade_details(pre, chain, offer_index, clicks),
                )
            verdict = verify_trade(
                pre=pre,
                post=post,
                first_item_id=offer.first_item_id,
                second_item_id=offer.second_item_id,
                sell_item_id=offer.sell_item_id,
            )
            if verdict is not ActionResultClass.UNKNOWN:
                return SkillOutcome(
                    result=verdict,
                    reason="",
                    action_id=action_id,
                    pre_tick=pre.game_tick,
                    post_tick=post.game_tick,
                    details=_trade_details(pre, post, offer_index, clicks),
                )
            chain = post

    def _require(self, capability: str) -> SkillOutcome | None:
        """The named refusal when the session was never negotiated for it.

        Asked before any command is built: the same `CAPABILITY_NOT_GRANTED`
        word answers on either side of the channel, and a skill that sent and
        then noticed would put the refusal in the Bridge's mouth.
        """

        if capability in self._capabilities:
            latest = self._observations.latest
            if latest is not None and not latest.self_state.alive:
                return _refusal_outcome("PLAYER_DEAD", "", latest)
            return None
        return SkillOutcome(
            result=ActionResultClass.FAILED,
            reason=CAPABILITY_NOT_GRANTED,
            action_id="",
            details={"capability": capability},
        )

    async def _send_mine(
        self,
        authority: ActionAuthority,
        action_id: str,
        target: BlockTargetValue,
        *,
        mining: bool,
    ) -> None:
        await self._sender.send_control(
            MINE_INPUT_TYPE,
            control_pb2.MineInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                mining=mining,
                target=_wire_target(target),
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )

    async def _swing_on_target(
        self,
        action_id: str,
        authority: ActionAuthority,
        entity: EntityCandidate,
        *,
        swing_seconds: float,
        deadline: int,
    ) -> tuple[str, int, int]:
        """Hold the attack key on a moving target until it leaves the view or the window ends.

        A hostile that hops moves off a fixed ray within a second: measured live on the
        summon run 9a4a82c3..., the fight aim arrived exactly at the computed angles and the
        bridge still refused the press MINE_TARGET_NOT_AIMED, because by press time the
        slime was no longer under the crosshair. So the press is gated on the client's own
        crosshair reading naming THIS entity -- the phrase the wire already carries -- and
        while the key is held the aim is re-derived from every newer reading, because
        tracking a hopping body is what a hand does with a mouse.

        With the operator's decision of 2026-10-06, a refused press is answered the way the
        refusal asks for: each press carries its OWN action id, so the Bridge's own answer
        for that press (the `ActionResult` the session's outcome registry holds) can never
        be confused with a walk's or an aim's; a refusal re-arms the press for the next
        frame that names the target, up to `FIGHT_MAX_PRESS_ATTEMPTS`, and the bound's end
        concludes the swing by the refusal's own name instead of swinging at nothing. The
        release goes through the same named exit as every other hold in this class, under
        the accepted press's id, and only if a press was accepted.

        The caller's post-wait still decides the verdict (`_target_unseen`); this method
        only operates the key honestly in between. The verdict it hands back is
        ("exhausted" | "ended", presses sent, refusals seen).
        """

        pressed_id = ""
        awaiting = ""
        presses = 0
        refusals = 0
        walking = False
        window_end = min(deadline, monotonic_ns() + round(swing_seconds * 1_000_000_000))

        async def release() -> None:
            if walking:
                await self._send_walk(action_id, authority, forward=0.0)
            if pressed_id:
                await self._send_swing(authority, pressed_id, swing=False)

        def ended() -> tuple[str, int, int]:
            """The swing is over; read the last press's fate before saying so.

            A refusal that arrived for the final press must not be left unread
            just because no further frame came: the bound's end is exactly the
            fact this step is named for.
            """

            nonlocal refusals, pressed_id, awaiting
            if awaiting and self._action_outcomes is not None:
                outcome = self._action_outcomes.latest(awaiting)
                if outcome is not None and outcome[0] in (
                    ACTION_ACCEPTED,
                    ACTION_STARTED,
                    ACTION_SUCCEEDED,
                ):
                    # An acceptance on the final frame still owns the release.
                    pressed_id = awaiting
                    awaiting = ""
                elif outcome is not None and outcome[0] in (ACTION_FAILED, ACTION_CANCELLED):
                    refusals += 1
                    awaiting = ""
                    if presses >= FIGHT_MAX_PRESS_ATTEMPTS:
                        return ("exhausted", presses, refusals)
            return ("ended", presses, refusals)

        try:
            current = self._observations.latest
            while current is not None:
                if monotonic_ns() >= window_end:
                    return ended()
                if _target_unseen(entity.observation_id)(current):
                    return ended()
                health = current.self_state.health
                if health < FIGHT_MIN_HEALTH:
                    # The body dropped under the trading line mid-swing: break it off now
                    # and let the next decision leave. Standing in the exchange below
                    # this line is the death the soaks died, not a fight.
                    return ended()
                if awaiting and self._action_outcomes is not None:
                    outcome = self._action_outcomes.latest(awaiting)
                    if outcome is not None and outcome[0] in (
                        ACTION_ACCEPTED,
                        ACTION_STARTED,
                        ACTION_SUCCEEDED,
                    ):
                        pressed_id = awaiting
                        awaiting = ""
                    elif outcome is not None and outcome[0] in (ACTION_FAILED, ACTION_CANCELLED):
                        refusals += 1
                        awaiting = ""
                        if presses >= FIGHT_MAX_PRESS_ATTEMPTS:
                            return ("exhausted", presses, refusals)
                if not walking:
                    # Walk it down: a slime that hops away is followed while the key is
                    # held, and standing still between hops was where its hits landed.
                    walking = True
                    await self._send_walk(action_id, authority, forward=1.0)
                listed = next(
                    (
                        candidate
                        for candidate in current.visible_entities
                        if candidate.observation_id == entity.observation_id
                    ),
                    None,
                )
                if listed is not None:
                    track_yaw, track_pitch = angle_to_degrees(
                        dx=listed.relative_x,
                        dy=listed.relative_y - EYE_HEIGHT_BLOCKS,
                        dz=listed.relative_z,
                    )
                    await self._sender.send_control(
                        AIM_INPUT_TYPE,
                        control_pb2.AimInput(
                            action_id=action_id,
                            lease_id=authority.lease_id,
                            generation=authority.generation,
                            yaw_degrees=track_yaw,
                            pitch_degrees=track_pitch,
                            deadline_monotonic_ns=authority.deadline_monotonic_ns,
                        ),
                    )
                if (
                    not pressed_id
                    and not awaiting
                    and _crosshair_on(current, entity.observation_id)
                ):
                    press_id = self._action_id()
                    presses += 1
                    await self._send_swing(authority, press_id, swing=True)
                    if self._action_outcomes is not None:
                        # Learn this press's fate before pressing again; a session
                        # with no registry keeps the old optimistic hold.
                        awaiting = press_id
                    else:
                        pressed_id = press_id
                base_tick = current.game_tick
                nxt = await self._wait_until(
                    lambda latest, since=base_tick: latest.game_tick > since,
                    window_end,
                    action_id=action_id,
                )
                if nxt is None:
                    return ended()
                current = nxt
            return ended()
        finally:
            await release()

    async def _aim_until_arrived(
        self,
        action_id: str,
        authority: ActionAuthority,
        yaw_degrees: float,
        pitch_degrees: float,
        *,
        base: WorldObservationValue,
        deadline: int,
    ) -> bool:
        """Re-ask one absolute heading until a reading reports the angles arrived.

        One aim command moves the client at most `WorldActions.MAX_AIM_DEGREES_PER_COMMAND`
        and answers STARTED when there is further to go, so a caller that sends once and
        then waits is waiting for a step the client was never asked to take. Measured live
        on the fight runs (b2e3ebeaa70b..., b77dac8d...): every away or body aim further
        than one clamp timed out with NO_CONFIRMING_OBSERVATION while the scan turns --
        which re-ask, the loop `turn_to` has had from the start -- arrived. The same shape
        here: send, re-read the next frame, re-ask the same target from it, and never
        assume the turn finished because it was asked.

        True when a reading shows the angles arrived; False when the deadline ran out
        first. Both callers file an unarrived aim the same way, so no separate stall
        verdict is needed here beyond the deadline.
        """

        while True:
            await self._sender.send_control(
                AIM_INPUT_TYPE,
                control_pb2.AimInput(
                    action_id=action_id,
                    lease_id=authority.lease_id,
                    generation=authority.generation,
                    yaw_degrees=yaw_degrees,
                    pitch_degrees=pitch_degrees,
                    deadline_monotonic_ns=authority.deadline_monotonic_ns,
                ),
            )
            post = await self._wait_until(
                _turn_reading(base.game_tick, yaw_degrees, pitch_degrees),
                deadline,
                action_id=action_id,
            )
            if post is None:
                if monotonic_ns() >= deadline:
                    return False
                continue
            base = post
            if _angle_arrived(post, yaw_degrees, pitch_degrees):
                return True

    async def _send_swing(self, authority: ActionAuthority, action_id: str, *, swing: bool) -> None:
        """The attack key with NO block named: a swing at whatever the crosshair is on.

        Not `_send_mine`: a mine names the block it must be aimed at, and the wire refuses
        a swing at anything but an entity precisely so a dig can never be asked for by
        accident. The empty target is the whole difference between the two calls.
        """

        await self._sender.send_control(
            MINE_INPUT_TYPE,
            control_pb2.MineInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                mining=swing,
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )

    async def _send_use(self, authority: ActionAuthority, action_id: str, *, use: bool) -> None:
        await self._sender.send_control(
            USE_INPUT_TYPE,
            control_pb2.UseInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                use=use,
                deadline_monotonic_ns=authority.deadline_monotonic_ns,
            ),
        )

    async def _wait_until(
        self,
        predicate: Callable[[WorldObservationValue], bool],
        deadline: int,
        *,
        action_id: str,
    ) -> WorldObservationValue | None:
        """Run the store's predicate wait inside the caller's own deadline.

        A slice at most — the store answers as soon as a reading (including the
        current one) satisfies the predicate, and `None` only when the deadline
        runs out first. That is the whole of the observation-reading protocol:
        act, then let the next admitted words of the client decide.

        The one thing that can end the wait besides those two is the client process
        itself going away, which is asked of the supervisor in `client_exit`: no
        reading will ever arrive afterwards, so a step that kept waiting would be
        spending its window to conclude about a JVM that is gone.

        The caller names the ask it is waiting on, and says so with the empty string
        when it has sent nothing yet — that difference is the fact the exit row
        carries, and a default here would let a site decide it by accident.
        """

        self._check_alive(action_id)
        remaining_ns = deadline - monotonic_ns()
        if remaining_ns <= 0:
            return None
        gone = self._client_exit()
        if gone is not None:
            raise ClientProcessExited(gone, action_id=action_id)

        def observed(candidate: WorldObservationValue) -> bool:
            self.check_interruption(action_id)
            return not candidate.self_state.alive or predicate(candidate)

        post = await self._outlive_client(
            self._observations.wait_until(observed, timeout_s=remaining_ns / 1_000_000_000),
            action_id=action_id,
        )
        self._check_alive(action_id)
        return post

    def _check_alive(self, action_id: str) -> None:
        self.check_interruption(action_id)
        latest = self._observations.latest
        if latest is not None and not latest.self_state.alive:
            raise PlayerDied(action_id=action_id, game_tick=latest.game_tick)

    @asynccontextmanager
    async def _release_on_exit(
        self, release: Callable[[], Awaitable[None]]
    ) -> AsyncGenerator[None]:
        """Attempt the held key's stop on success, death, cancellation or failure.

        A failed stop send must not replace an already observed death or process
        exit. It is not a Bridge acknowledgement; session wind-down still owns
        the lease release and records transport failure independently.
        """
        try:
            yield
        except BaseException as interrupted:
            try:
                await release()
            except (OSError, RuntimeError):
                if isinstance(interrupted, PlayerDied):
                    interrupted.release_failed = True
            raise
        else:
            await release()

    async def _outlive_client(
        self,
        wait: Awaitable[WorldObservationValue | None],
        *,
        action_id: str,
        allow_dead: bool = False,
    ) -> WorldObservationValue | None:
        """Let the client's own exit interrupt a wait, and cancel the wait for it.

        The store is the only thing that can answer a skill, so the wait is not
        replaced — it is raced. Whichever ends first decides, and a client that is
        still running changes nothing about how long the wait may take.
        """

        pending = asyncio.ensure_future(wait)
        try:
            while True:
                finished, _ = await asyncio.wait({pending}, timeout=CLIENT_EXIT_POLL_S)
                if finished:
                    return pending.result()
                if allow_dead:
                    self.check_interruption(action_id)
                else:
                    self._check_alive(action_id)
                gone = self._client_exit()
                if gone is not None:
                    raise ClientProcessExited(gone, action_id=action_id)
        finally:
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)

    async def _sleep(self, seconds: float, *, action_id: str) -> None:
        if seconds <= 0:
            return
        await self._wait_until(
            lambda candidate: False,
            monotonic_ns() + round(seconds * 1_000_000_000),
            action_id=action_id,
        )


def _crosshair_on(observation: WorldObservationValue, entity_id: str) -> bool:
    """Whether this reading's crosshair is on the named entity, in the client's own words.

    The same sentence the swing guard in the Bridge checks a moment later: a press decided
    from a reading that said the crosshair was on the thing is the closest a hold can come
    to asking while looking.
    """

    aim = observation.aim
    return aim is not None and aim.kind is AimKind.ENTITY and aim.entity_observation_id == entity_id


def _trade_details(
    pre: WorldObservationValue,
    post: WorldObservationValue | None,
    offer_index: int,
    clicks: list[str],
) -> dict[str, str]:
    """The trade's own words: which row, which clicks reached the screen, and what the
    inventory revision and the payout item read before and after — nothing inferred."""

    sell_item = ""
    if pre.gui is not None and 0 <= offer_index < len(pre.gui.trade_offers):
        sell_item = pre.gui.trade_offers[offer_index].sell_item_id
    details = {
        "offer_index": str(offer_index),
        "sell_item_id": sell_item,
        "sell_count_before": str(item_total(pre.inventory, sell_item)) if sell_item else "",
        "clicks": "+".join(clicks),
        "pre_inventory_revision": str(pre.inventory.revision),
    }
    if post is not None:
        details["newest_inventory_revision"] = str(post.inventory.revision)
        details["sell_count_after"] = (
            str(item_total(post.inventory, sell_item)) if sell_item else ""
        )
        details["newest_checked_tick"] = str(post.game_tick)
    return details


def _target_unseen(entity_id: str) -> Callable[[WorldObservationValue], bool]:
    """Whether a later reading no longer renders the entity a swing was aimed at.

    The honest sentence and no more: the entity that was rendered is not rendered now --
    it may be dead, it may have left the view, and no reading of the moment tells those
    apart. Both end the swing the same way, and the next decision reads what is there.
    """

    return lambda latest: all(
        candidate.observation_id != entity_id for candidate in latest.visible_entities
    )


def _horizontal_position(observation: WorldObservationValue) -> tuple[float, float] | None:
    """Where the body reports itself on the ground plane, or None.

    None when the reading has no position to report: absence is not the origin,
    and a walk that treated a missing x/z as (0, 0) would steer at wherever that
    happens to be.
    """

    px = observation.self_state.x
    pz = observation.self_state.z
    if px is None or pz is None:
        return None
    return (px, pz)


def _horizontal_movement(
    before: WorldObservationValue, after: WorldObservationValue
) -> float | None:
    """How far the body's horizontal position moved between two readings, or None.

    None when either reading has no position to compare — absence is not zero movement,
    and a retreat must not confirm against a reading that never said where the body is.
    """

    bx, bz = before.self_state.x, before.self_state.z
    ax, az = after.self_state.x, after.self_state.z
    if bx is None or bz is None or ax is None or az is None:
        return None
    return math.hypot(ax - bx, az - bz)


def _walked_away(before: WorldObservationValue, after: WorldObservationValue) -> bool:
    """Whether the later reading shows a real horizontal step since the earlier one."""

    moved = _horizontal_movement(before, after)
    return moved is not None and moved >= RETREAT_CONFIRM_BLOCKS


def _angle_error(
    observation: WorldObservationValue, yaw_degrees: float, pitch_degrees: float
) -> float | None:
    state = observation.self_state
    if state.yaw_degrees is None or state.pitch_degrees is None:
        return None
    return angle_error_degrees(
        from_yaw=state.yaw_degrees,
        to_yaw=yaw_degrees,
        from_pitch=state.pitch_degrees,
        to_pitch=pitch_degrees,
    )


def _angle_arrived(
    observation: WorldObservationValue, yaw_degrees: float, pitch_degrees: float
) -> bool:
    error = _angle_error(observation, yaw_degrees, pitch_degrees)
    return error is not None and error <= AIM_ARRIVAL_TOLERANCE_DEGREES
