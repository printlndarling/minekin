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
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from google.protobuf.message import Message

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
    SCREEN_CAPABILITY,
    SCREEN_INPUT_TYPE,
    USE_CAPABILITY,
    USE_INPUT_TYPE,
    monotonic_ns,
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
from minekin_core.domain.world_actions import (
    ActionRefusal,
    ActionResultClass,
    SkillOutcome,
    angle_error_degrees,
    angle_to_degrees,
    gui_click_refusal,
    hotbar_slot_refusal,
    item_total,
    mine_target_refusal,
    seen_drops,
    use_target_refusal,
    verify_block_broken,
    verify_craft,
    verify_hotbar_change,
    verify_item_collected,
    verify_use_effect,
)
from minekin_core.generated.minekin.v1 import control_pb2

#: How close a turned angle has to be before the turn counts as arrived. Not a
#: clamp: the Bridge still owns the 20-degrees-per-command bound; this is only
#: the tolerance under which "facing the thing" is true of two float reads.
AIM_ARRIVAL_TOLERANCE_DEGREES: Final[float] = 2.0

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
    yaw_degrees: float = 0.0
    pitch_degrees: float = 0.0
    item_id: str = ""
    slot: int = -1
    recipe_id: str = ""
    product_id: str = ""
    expected_drop_item: str = ""
    expected_item_id: str = ""
    walk_seconds: float = 1.0
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


def _wire_target(target: BlockTargetValue) -> control_pb2.BlockTarget:
    face = _WIRE_FACES.get(target.face.value)
    if face is None:
        raise ValueError(f"the client reported a face this build cannot name: {target.face}")
    return control_pb2.BlockTarget(x=target.x, y=target.y, z=target.z, face=face)


def _chase_details(steps: int, newest: WorldObservationValue) -> dict[str, str]:
    """What the chase did, in the field the run document already carries for it.

    `post_tick` keeps its meaning — the reading that confirmed the pickup, so a
    null still says nothing confirmed it — and these two say whether anything
    arrived at all: how many steps went out, and the newest reading they were
    concluded against. Without them a `NO_CONFIRMING_OBSERVATION` cannot be told
    apart from the channel going silent, and the two are answered by changing
    different things.
    """

    return {"steps": str(steps), "newest_checked_tick": str(newest.game_tick)}


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
    ) -> None:
        self._sender = sender
        self._observations = observations
        self._capabilities = capabilities
        self._action_id = action_id
        self._client_exit = client_exit

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
        chain = pre
        while True:
            post = await self._wait_until(
                _newer_reading(chain.game_tick), deadline, action_id=action_id
            )
            if post is None:
                # Either the window ran out or it is still open; only a closed
                # window ends the wait.
                if monotonic_ns() >= deadline:
                    await self._send_mine(authority, action_id, target, mining=False)
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
                await self._send_mine(authority, action_id, target, mining=False)
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
        await self._walk_toward(action_id, authority, first_drops[0], walk_seconds)
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
                    details=_chase_details(steps, post),
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
            await self._walk_toward(action_id, authority, drops[0], CHASE_STEP_SECONDS)
        return SkillOutcome(
            result=ActionResultClass.UNKNOWN,
            reason=chase_reason,
            action_id=action_id,
            pre_tick=pre.game_tick,
            details=_chase_details(steps, chain),
        )

    async def _walk_toward(
        self,
        action_id: str,
        authority: ActionAuthority,
        drop: EntityCandidate,
        walk_seconds: float,
    ) -> None:
        """Aim at where this reading says the drop is, step, and stop."""

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
        await self._send_walk(action_id, authority, forward=1.0)
        await self._sleep(walk_seconds)
        # The same named release the movement contract already guarantees — a
        # walk with no stop would be a Kin still walking into whatever is there,
        # and that is true of the last step of a chase as much as of the first.
        await self._send_walk(action_id, authority, forward=0.0)

    async def _send_walk(
        self, action_id: str, authority: ActionAuthority, *, forward: float
    ) -> None:
        await self._sender.send_control(
            MOVE_INPUT_TYPE,
            control_pb2.MoveInput(
                action_id=action_id,
                lease_id=authority.lease_id,
                generation=authority.generation,
                forward=forward,
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
        filled = await self._wait_until(
            _newer_reading(current.game_tick), deadline, action_id=action_id
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
        if chain.gui is None or chain.gui.sync_id is None:
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
        await self._sleep(USE_TAP_SECONDS)
        await self._send_use(authority, action_id, use=False)
        deadline = monotonic_ns() + timeout_ns
        post = await self._wait_until(_newer_reading(pre.game_tick), deadline, action_id=action_id)
        if post is None:
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

    def _require(self, capability: str) -> SkillOutcome | None:
        """The named refusal when the session was never negotiated for it.

        Asked before any command is built: the same `CAPABILITY_NOT_GRANTED`
        word answers on either side of the channel, and a skill that sent and
        then noticed would put the refusal in the Bridge's mouth.
        """

        if capability in self._capabilities:
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

        remaining_ns = deadline - monotonic_ns()
        if remaining_ns <= 0:
            return None
        gone = self._client_exit()
        if gone is not None:
            raise ClientProcessExited(gone, action_id=action_id)
        return await self._outlive_client(
            self._observations.wait_until(predicate, timeout_s=remaining_ns / 1_000_000_000),
            action_id=action_id,
        )

    async def _outlive_client(
        self, wait: Awaitable[WorldObservationValue | None], *, action_id: str
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
                gone = self._client_exit()
                if gone is not None:
                    raise ClientProcessExited(gone, action_id=action_id)
        finally:
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)

    async def _sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        await asyncio.sleep(seconds)


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
