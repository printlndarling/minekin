"""What the Core refuses before the wire, and what a reading has to say after.

Two halves of the S2 action contract live here because they are the same
question asked of the same value objects: what may this Kin ask, and what may it
believe.

The refusals are the ones §3 names, decided against the last observation rather
than against a hope: mining something the crosshair is not on, selecting a slot
outside the nine, and clicking a container that is not the one the client
reports. The angle clamp on a turn is deliberately *not* here — that bound is
the client's, and a Core that pre-cut a turn into twenty-degree steps would be
a second clock for the same rule. Core may ask for the whole turn and must take
`STARTED` plus `AIM_IN_PROGRESS` as the normal answer that it is not done yet.

The verifications are the four rows of §4, each comparing the observation made
before the action with a later one. None of them can manufacture a `CONFIRMED`
from a command that was sent, a client that answered, or a window that opened:
only a synced change in the readings confirms, and everything that is not
confirmed comes back `UNKNOWN` or `FAILED` — never a silent retry, which the
frozen contract forbids for anything with a side effect.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from minekin_core.domain.control_vocabulary import (
    AIM_CAPABILITY,
    GUI_CAPABILITY,
    HOTBAR_CAPABILITY,
    MINE_CAPABILITY,
    MOVE_CAPABILITY,
    RESPAWN_CAPABILITY,
    SCREEN_CAPABILITY,
    USE_CAPABILITY,
)
from minekin_core.domain.food_catalog import is_known_food, nutrition_for
from minekin_core.domain.perception import (
    HOTBAR_SLOT_COUNT,
    MAX_FOOD,
    AimFace,
    AimKind,
    BlockTargetValue,
    EntityCandidate,
    InventoryValue,
    SelfStateValue,
    WorldObservationValue,
)

#: The block a placement lands in, given the face of the aim block the client
#: clicked: Minecraft puts the new block in the air cell touching that face, not
#: in the solid one. DOWN/NORTH/WEST carry the negative axis; the enum's own
#: wording, not a per-item table, so every placeable rides the same geometry.
FACE_PLACEMENT_OFFSET: Final[Mapping[str, tuple[int, int, int]]] = {
    AimFace.DOWN.value: (0, -1, 0),
    AimFace.UP.value: (0, 1, 0),
    AimFace.NORTH.value: (0, 0, -1),
    AimFace.SOUTH.value: (0, 0, 1),
    AimFace.WEST.value: (-1, 0, 0),
    AimFace.EAST.value: (1, 0, 0),
}

#: What each skill asks authorisation for, keyed by the skill's own name. The
#: mapping is in the domain rather than at the call site because the same list
#: answers two different questions — what a lease has to cover before the skill
#: runs, and what a Bridge that never negotiated it refuses — and those are one
#: fact about the skill, not two about the callers.
#:
#: `collect_dropped` needs movement *and* the aim: it turns toward a drop that is
#: already on the visible list and then walks. `craft` needs the screen and the
#: GUI and not the aim, because opening one's own inventory is not a look.
SKILL_CAPABILITIES: Final[Mapping[str, frozenset[str]]] = {
    "turn_to": frozenset({AIM_CAPABILITY}),
    "break_seen_block": frozenset({MINE_CAPABILITY}),
    "collect_dropped": frozenset({MOVE_CAPABILITY, AIM_CAPABILITY}),
    "craft": frozenset({SCREEN_CAPABILITY, GUI_CAPABILITY}),
    "craft_take_result": frozenset({SCREEN_CAPABILITY, GUI_CAPABILITY}),
    # Leaving a window touches no container, so it asks for the screen and not
    # for the click that operates one.
    "close_screen": frozenset({SCREEN_CAPABILITY}),
    "select_hotbar": frozenset({HOTBAR_CAPABILITY}),
    # Right-clicking what the crosshair is on — the use key the contract already
    # routes as a baseline capability. It covers both placing what is in hand and
    # activating what is aimed at, because the wire deliberately offers one use
    # key rather than a separate door per product (see `ScreenControl`'s comment).
    "use_target": frozenset({USE_CAPABILITY}),
    "respawn": frozenset({RESPAWN_CAPABILITY}),
    # Eating is the number key plus the use key held: the food has to be brought
    # to hand (a hotbar select) before the meal can start, and the meal itself is
    # the use key under the lease. Both are declared even though a food already
    # in hand needs no select — a skill that sometimes sends a message must
    # declare it always, or the lease that covers it would depend on which frame
    # happened to be read.
    "consume_item": frozenset({HOTBAR_CAPABILITY, USE_CAPABILITY}),
    # A retreat turns away from a hostile the reading reported and takes one step:
    # the same two capabilities a collect walks with, because it is the same walk,
    # pointed away instead of toward.
    "retreat": frozenset({MOVE_CAPABILITY, AIM_CAPABILITY}),
    # A fight aims at a reported entity and holds the attack key with no block named: the
    # aim a retreat takes plus the key a mine holds, pointed at the thing instead of away
    # from it. Same two capabilities, because it is the same look and the same key.
    "fight_back": frozenset({MINE_CAPABILITY, AIM_CAPABILITY}),
    # A trade selects a row of the open merchant's list and takes its result: two screen
    # clicks, the same pair a craft ends with.
    "trade": frozenset({SCREEN_CAPABILITY, GUI_CAPABILITY}),
    # Facing a rendered body is the aim a fight takes, without the key: the leg every
    # interaction with an entity (a trade, later more) starts from.
    "look_at_entity": frozenset({AIM_CAPABILITY}),
}


def skill_capabilities(name: object) -> frozenset[str] | None:
    """The capabilities one skill name needs, or `None` for a name that is not a
    skill. `None` is an answer rather than an error: an unknown name has to be
    refused by whoever asked for it, and a lookup that raised would put the
    operator's typo in a stack trace."""

    if not isinstance(name, str):
        return None
    return SKILL_CAPABILITIES.get(name)


#: The contract's five result classes, lifted out of the wire's seven-status
#: `ActionResult` into the vocabulary the skill layer concludes with. The wire's
#: `ACCEPTED` is not a result — it is a receipt — and a turn that is still
#: turning is `STARTED` here and `STARTED` there with `AIM_IN_PROGRESS` as its
#: named reason, which is what makes "not yet" and "not ever" two answers.
class ActionResultClass(StrEnum):
    STARTED = "STARTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"
    UNKNOWN = "UNKNOWN"


#: Named local refusals, spelled exactly as §3 spells the Bridge's side of them,
#: because the pair is the point: the same word answers on either side of the
#: channel, and a run that was refused early reads the same as one the client
#: refused late.
class ActionRefusal(StrEnum):
    MINE_TARGET_NOT_AIMED = "MINE_TARGET_NOT_AIMED"
    HOTBAR_SLOT_OUT_OF_RANGE = "HOTBAR_SLOT_OUT_OF_RANGE"
    GUI_SYNC_ID_MISMATCH = "GUI_SYNC_ID_MISMATCH"
    USE_TARGET_NOT_AIMED = "USE_TARGET_NOT_AIMED"
    #: A placement whose only target is the air the player already stands in. The
    #: server would drop the block back, so the click is a no-op with a side
    #: effect spent; Core names it before the wire rather than banking an UNKNOWN.
    PLACEMENT_TARGET_IN_SELF = "PLACEMENT_TARGET_IN_SELF"
    #: The consume skill's own words, all decided against the last reading before a
    #: key is pressed. Eating has no dedicated wire message — it is the use key held
    #: with a food in hand and nothing in the crosshair's way — so every one of these
    #: is a Core-side precondition, and they exist for the same reason the others do:
    #: the run document has to say *why* no meal happened, in a word the ledger can
    #: be searched for. `CONSUME_ITEM_NOT_KNOWN_FOOD` names the curated table's
    #: boundary (see `domain/food_catalog.py`); it is not a claim about the game.
    CONSUME_ITEM_MISSING = "CONSUME_ITEM_MISSING"
    CONSUME_ITEM_NOT_KNOWN_FOOD = "CONSUME_ITEM_NOT_KNOWN_FOOD"
    CONSUME_ITEM_NOT_IN_HOTBAR = "CONSUME_ITEM_NOT_IN_HOTBAR"
    CONSUME_NOT_HUNGRY = "CONSUME_NOT_HUNGRY"
    CONSUME_AIM_NOT_CLEAR = "CONSUME_AIM_NOT_CLEAR"


#: The consume refusals as the strings a run carries. Kept beside the enum because the
#: mind's reroute tables are keyed by the string token every ledger row carries, and a
#: second spelling of a refusal is the one way those two could drift apart.
CONSUME_REFUSAL_REASONS: Final[frozenset[str]] = frozenset(
    {
        ActionRefusal.CONSUME_ITEM_MISSING.value,
        ActionRefusal.CONSUME_ITEM_NOT_KNOWN_FOOD.value,
        ActionRefusal.CONSUME_ITEM_NOT_IN_HOTBAR.value,
        ActionRefusal.CONSUME_NOT_HUNGRY.value,
        ActionRefusal.CONSUME_AIM_NOT_CLEAR.value,
    }
)


#: A block face the client did not name cannot disagree with anything, so an
#: aimed face of `NOT_READ` or `UNKNOWN` matches any requested face and the
#: coordinates still have to agree. That is all of the tolerance there is:
#: mismatched coordinates are refused whatever the faces say.
_FACE_AGNOSTIC: Final = frozenset({"NOT_READ", "UNKNOWN"})


@dataclass(frozen=True, slots=True)
class ActionRefusalDecision:
    """Refused or not, with the name. Returned rather than raised because the
    refusal is the normal product of a stale plan, and a stale plan is evidence,
    not a fault."""

    refusal: ActionRefusal | None

    @property
    def accepted(self) -> bool:
        return self.refusal is None

    def as_document(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "refusal": None if self.refusal is None else self.refusal.value,
        }


#: What a finished skill hands back: one of the contract's five words, the
#: reading it compared, and the action id the commands carried. The reason is a
#: stable token, never prose — §3's named refusals and §4's verdicts are
#: evidence only while they are the same strings a run can be searched for.
@dataclass(frozen=True, slots=True)
class SkillOutcome:
    result: ActionResultClass
    reason: str
    action_id: str
    pre_tick: int | None = None
    post_tick: int | None = None
    details: Mapping[str, str] = field(default_factory=dict[str, str])


def hotbar_slot_refusal(slot: object) -> ActionRefusalDecision:
    """0..8 or nothing: this is the hotbar, not the whole inventory."""

    if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= 8:
        return ActionRefusalDecision(ActionRefusal.HOTBAR_SLOT_OUT_OF_RANGE)
    return ActionRefusalDecision(None)


def mine_target_refusal(
    observation: WorldObservationValue | None,
    target: BlockTargetValue,
    *,
    mining: bool,
) -> ActionRefusalDecision:
    """A hold on the attack key may only start on the block the crosshair reports.

    Letting go (`mining=False`) is always allowed: the release path is the single
    one the lease contract already guarantees, and refusing a stop to make a
    point would be a Kin still digging.
    """

    if not mining:
        return ActionRefusalDecision(None)
    aim = observation.aim if observation is not None else None
    if (
        aim is None
        or aim.kind is not AimKind.BLOCK
        or aim.block is None
        or not _same_block(aim.block, target)
    ):
        return ActionRefusalDecision(ActionRefusal.MINE_TARGET_NOT_AIMED)
    return ActionRefusalDecision(None)


def gui_click_refusal(
    observation: WorldObservationValue | None,
    sync_id: object,
) -> ActionRefusalDecision:
    """No click goes out against a handler the client is not reporting.

    No observation, no screen, and a screen whose sync id was never read are all
    the same refusal: there is nothing to match, and the contract's rule is that
    a stale syncId never rides into the next container.
    """

    gui = observation.gui if observation is not None else None
    if (
        isinstance(sync_id, bool)
        or not isinstance(sync_id, int)
        or gui is None
        or gui.sync_id is None
        or gui.sync_id != sync_id
    ):
        return ActionRefusalDecision(ActionRefusal.GUI_SYNC_ID_MISMATCH)
    return ActionRefusalDecision(None)


def _placement_cell(block: BlockTargetValue) -> tuple[int, int, int] | None:
    """The air cell a block placed against `block`'s clicked face would land in.

    `None` when the client named no face (`NOT_READ`/`UNKNOWN`): with no direction
    there is no cell to collide with, and an un-named face stays the tolerant
    match §4 already grants rather than becoming a phantom refusal.
    """

    offset = FACE_PLACEMENT_OFFSET.get(block.face.value)
    if offset is None:
        return None
    return (block.x + offset[0], block.y + offset[1], block.z + offset[2])


PLAYER_COLLISION_HALF_WIDTH = 0.3
PLAYER_COLLISION_HEIGHT = 1.8


def _occupied_cells(self_state: SelfStateValue) -> frozenset[tuple[int, int, int]]:
    """Every block cell the standing player's collision box overlaps, not just the
    two its feet column floors to.

    A player box is 0.6 wide and 1.8 tall centered on the reported position, so it
    reaches `PLAYER_COLLISION_HALF_WIDTH` to each side and `PLAYER_COLLISION_HEIGHT`
    up. The server refuses a block placed into ANY cell the box touches — including
    the neighbour cell a Kin straddling a boundary leans into, which a floor-of-center
    model reads as free and the hand then spends a doomed click on. An absent
    position reads as no cells, so the check stays silent rather than guessing the
    origin. For a player standing at a cell center the span is exactly the feet cell
    and the head cell above it, so the common case is unchanged.
    """

    if self_state.x is None or self_state.y is None or self_state.z is None:
        return frozenset()
    xs = range(
        math.floor(self_state.x - PLAYER_COLLISION_HALF_WIDTH),
        math.floor(self_state.x + PLAYER_COLLISION_HALF_WIDTH) + 1,
    )
    ys = range(
        math.floor(self_state.y),
        math.floor(self_state.y + PLAYER_COLLISION_HEIGHT) + 1,
    )
    zs = range(
        math.floor(self_state.z - PLAYER_COLLISION_HALF_WIDTH),
        math.floor(self_state.z + PLAYER_COLLISION_HALF_WIDTH) + 1,
    )
    return frozenset((x, y, z) for x in xs for y in ys for z in zs)


def placement_target_in_self(observation: WorldObservationValue | None) -> bool:
    """Whether the only thing the crosshair offers is the air the player is in.

    A block places into the cell touching the clicked face. When that cell is one
    of the two the standing player already occupies, the server rejects the block
    and the hand keeps it — so a use there is a spent click that can never
    confirm. This is the general placement precondition, item-agnostic: it is the
    same geometry whether the hand holds a crafting table, a torch, or a slab.
    """

    if observation is None:
        return False
    aim = observation.aim
    if aim is None or aim.kind is not AimKind.BLOCK or aim.block is None:
        return False
    cell = _placement_cell(aim.block)
    return cell is not None and cell in _occupied_cells(observation.self_state)


def use_target_refusal(observation: WorldObservationValue | None) -> ActionRefusalDecision:
    """The use key may only fire on something the crosshair actually reports.

    §5's "all premised on having seen" bounds this skill the same way it bounds
    mining: a `MISS` (the ray hit nothing) or an `UNREAD` aim (the client never
    populated it) is a Kin right-clicking at empty air, and a placement there is
    a different act than the one the plan asked for. A block or an entity is a
    thing the client rendered, so either may be used — placing against the block
    or activating the villager, chest or door are the same key on the wire.

    Beyond seeing, a block aim must have somewhere to put the block: if the face
    it is aimed at opens only onto the cell the player is standing in, the use is
    refused with `PLACEMENT_TARGET_IN_SELF` rather than spending a click the
    server will bounce. Activation of the aimed block is untouched — it acts on
    the block under the crosshair, never on the air in front of it.
    """

    aim = observation.aim if observation is not None else None
    if aim is None or aim.kind not in (AimKind.BLOCK, AimKind.ENTITY):
        return ActionRefusalDecision(ActionRefusal.USE_TARGET_NOT_AIMED)
    if placement_target_in_self(observation):
        return ActionRefusalDecision(ActionRefusal.PLACEMENT_TARGET_IN_SELF)
    return ActionRefusalDecision(None)


def use_target_signature(observation: WorldObservationValue | None) -> tuple[object, ...] | None:
    """Which thing the crosshair is on, as a hashable identity — for the mind to tell a
    repeat click from a fresh one, never for the world to be edited.

    §5 bounds the use key to "the thing already seen", and §4 forbids replaying a
    side-effecting click. Those two meet at placement: a `use_target` that returned
    `UNKNOWN` against a given block-and-face (or a given entity) tells the Kin that the
    click there did nothing, and firing the same key at the SAME target again is the
    gambling-by-repetition the contract rules out, not a new attempt. This names the
    target the client reported so a later reading can be compared against the one that
    was already spent on: a moved aim reads differently and re-opens the step, a held
    aim reads identically and the mind reaches for the turn instead.

    `None` for the aims no click could land on anyway — nothing seen, or a `MISS`/`UNREAD`
    ray — so a caller never treats "there was no target" as a target it has tried.
    """

    aim = observation.aim if observation is not None else None
    if aim is None:
        return None
    if aim.kind is AimKind.BLOCK and aim.block is not None:
        return ("block", aim.block.x, aim.block.y, aim.block.z, aim.block.face.value)
    if aim.kind is AimKind.ENTITY:
        return ("entity", aim.entity_observation_id)
    return None


def hotbar_slot_for_item(inventory: InventoryValue, item_id: str) -> int | None:
    """The first hotbar slot (0..8) holding the item, or `None` when only the wider bag
    does — or holds nothing of it at all.

    The summary's slot numbers are the client's own: 0..8 are the nine a number key can
    reach, anything higher lives in the bag proper, and §3's hotbar rule is that moving
    something between the two is a container click this build does not make behind the
    player's back. So a meal in the bag and not the hotbar stays refused by name.
    """

    for stack in inventory.stacks:
        if stack.item_id == item_id and 0 <= stack.slot < HOTBAR_SLOT_COUNT:
            return stack.slot
    return None


def reachable_food_items(observation: WorldObservationValue) -> tuple[str, ...]:
    """Every curated food this reading can actually bring to hand, one entry per item
    id, sorted — the bag-wide table view filtered to what a number key can select.

    A stack the hotbar (0..8) already carries, or the held hand, qualifies; one the
    wider bag alone holds does not, because no skill here moves items between the two
    and listing it would invite exactly the ask the skill refuses by name
    (`CONSUME_ITEM_NOT_IN_HOTBAR`). The same kind of answer `craft_options` gives for
    what the bag could pay for, and never a claim about the world.
    """

    held = observation.self_state.main_hand_item_id
    reachable = {
        stack.item_id
        for stack in observation.inventory.stacks
        if is_known_food(stack.item_id) and 0 <= stack.slot < HOTBAR_SLOT_COUNT
    }
    if held is not None and is_known_food(held):
        reachable.add(held)
    return tuple(sorted(reachable))


def consume_candidate(observation: WorldObservationValue) -> str | None:
    """The meal this build would reach for from this reading, or `None` when there is
    no candidate at all.

    Candidate selection is a fact about the *build's* table and the *bag's* counters, not
    about the world's answer — whether a meal can actually happen is
    `consume_item_refusal`'s question, asked on the same reading. Only hotbar-reachable
    foods qualify (a number key has to be able to bring the stack to hand; see
    `hotbar_slot_for_item`), and the order is deterministic: the largest curated meal
    first, ties broken by the item id so two readings over the same bag pick the same
    food.
    """

    best: tuple[int, str] | None = None
    for stack in observation.inventory.stacks:
        if not 0 <= stack.slot < HOTBAR_SLOT_COUNT:
            continue
        points = nutrition_for(stack.item_id)
        if points is None:
            continue
        if best is None or points > best[0] or (points == best[0] and stack.item_id < best[1]):
            best = (points, stack.item_id)
    return None if best is None else best[1]


def consume_item_refusal(observation: WorldObservationValue, item_id: str) -> ActionRefusalDecision:
    """Every reason not to hold the use key on this item, decided against this reading.

    The consume skill has no wire-side twin to disagree with: there is no eat message,
    only the use key held, so all of its preconditions live here and answer with the
    same kind of named token as the ones the Bridge owns for other skills. In order:

    - the item has to be in the bag at all (`CONSUME_ITEM_MISSING`) and in the curated
      table (`CONSUME_ITEM_NOT_KNOWN_FOOD`; the table's boundary is a fact about this
      build, stated as one);
    - the hunger bar has to have room (`CONSUME_NOT_HUNGRY`) — a full bar is the one
      state where a meal demonstrably changes nothing, and §4's confirmation below reads
      the bar, so a "meal" at a full bar could never be told from a wish. Items that can
      be eaten at full hunger are outside this build's curated table for exactly that
      reason (see `food_catalog`);
    - the stack has to be bringable to hand (`CONSUME_ITEM_NOT_IN_HOTBAR`), which the
      held item trivially is;
    - the crosshair has to be on nothing (`CONSUME_AIM_NOT_CLEAR`). This is the one
      precondition that is not about the meal: the use key fires at what the crosshair
      reports first, so a door, a trapdoor or a chest under the aim would take the click
      instead of the mouth — a side effect the contract's no-replay rule makes expensive.
      A positive `MISS` is the client saying "I looked and there is nothing"; an unread
      aim is not that statement and is refused the same way.
    """

    if item_total(observation.inventory, item_id) <= 0:
        return ActionRefusalDecision(ActionRefusal.CONSUME_ITEM_MISSING)
    if not is_known_food(item_id):
        return ActionRefusalDecision(ActionRefusal.CONSUME_ITEM_NOT_KNOWN_FOOD)
    if observation.self_state.food >= MAX_FOOD:
        return ActionRefusalDecision(ActionRefusal.CONSUME_NOT_HUNGRY)
    held = observation.self_state.main_hand_item_id == item_id
    if not held and hotbar_slot_for_item(observation.inventory, item_id) is None:
        return ActionRefusalDecision(ActionRefusal.CONSUME_ITEM_NOT_IN_HOTBAR)
    aim = observation.aim
    if aim is None or aim.kind is not AimKind.MISS:
        return ActionRefusalDecision(ActionRefusal.CONSUME_AIM_NOT_CLEAR)
    return ActionRefusalDecision(None)


def _same_block(a: BlockTargetValue, b: BlockTargetValue) -> bool:
    if (a.x, a.y, a.z) != (b.x, b.y, b.z):
        return False
    if a.face.value in _FACE_AGNOSTIC or b.face.value in _FACE_AGNOSTIC:
        return True
    return a.face is b.face


def item_total(inventory: InventoryValue, item_id: str) -> int:
    """How many of one item the summary holds. The only count a verification is
    allowed to compare, because it is the count the synced readings agree on."""

    return sum(stack.count for stack in inventory.stacks if stack.item_id == item_id)


def _dropped_count(observation: WorldObservationValue, item_id: str) -> int:
    total = 0
    for entity in observation.visible_entities:
        if entity.item_id == item_id and entity.item_count is not None:
            total += entity.item_count
    return total


def _newer(pre: WorldObservationValue, post: WorldObservationValue) -> bool:
    return post.game_tick > pre.game_tick


def _inventory_synced(pre: WorldObservationValue, post: WorldObservationValue) -> bool:
    # The inventory summary's revision is the game tick it was read at, so a
    # later revision is the only evidence that the counts changed on the server
    # and not just in a wish.
    return post.inventory.revision > pre.inventory.revision


def verify_block_broken(
    *,
    pre: WorldObservationValue,
    post: WorldObservationValue,
    target: BlockTargetValue,
    expected_drop_item: str | None = None,
) -> ActionResultClass:
    """§4 row one. Confirms when a newer read under the crosshair no longer
    names the target block — the hit slid to another block behind it, the ray
    now misses, or the same coordinates render something else — or when the
    expected drop appears. Everything else is "not yet" or "not this": a stalled
    break fails, and a lost aim read, an aim handed to an entity or no new
    reading at all stays unknown.

    The block the target was made of is read out of `pre`'s own aim rather than
    passed in: a caller-supplied name can contradict the reading it is supposed
    to come from, and the direction that mistake goes in is a confirmed break
    that never happened.
    """

    if not _newer(pre, post):
        return ActionResultClass.UNKNOWN
    post_aim = post.aim
    still_on_target = (
        post_aim is not None
        and post_aim.kind is AimKind.BLOCK
        and post_aim.block is not None
        and _same_block(post_aim.block, target)
    )
    if post_aim is not None and not still_on_target and post_aim.kind is not AimKind.ENTITY:
        # The read is there and it is no longer this block: the break moved what
        # the crosshair lands on. `MISS` is "looked and the ray hit nothing",
        # which is what the target's own hole reads as.
        return ActionResultClass.CONFIRMED
    pre_aim = pre.aim
    if (
        still_on_target
        and post_aim is not None
        and pre_aim is not None
        and pre_aim.targeted_block_id
        and post_aim.targeted_block_id
        and post_aim.targeted_block_id != pre_aim.targeted_block_id
    ):
        return ActionResultClass.CONFIRMED
    if (
        expected_drop_item is not None
        and _dropped_count(pre, expected_drop_item) == 0
        and _dropped_count(post, expected_drop_item) > 0
    ):
        return ActionResultClass.CONFIRMED
    pre_mining = pre.mining
    post_mining = post.mining
    if (
        pre_mining is not None
        and post_mining is not None
        and _same_block(pre_mining.target, post_mining.target)
        and _same_block(pre_mining.target, target)
        and math.isclose(pre_mining.progress, post_mining.progress)
    ):
        # The bar the player can see did not move between two named ticks. That
        # is the contract's "mining progress not moving", and it is a failure to
        # report rather than an unknown to wait out.
        return ActionResultClass.FAILED
    return ActionResultClass.UNKNOWN


def verify_item_collected(
    *,
    pre: WorldObservationValue,
    post: WorldObservationValue,
    item_id: str,
) -> ActionResultClass:
    """§4 row two. The synced total has to rise *and* the seen drop to dwindle;
    a drop gone with no rise (taken, burned, expired) is a failure, and a rise
    without a synced revision is worth nothing."""

    if not _newer(pre, post) or not _inventory_synced(pre, post):
        return ActionResultClass.UNKNOWN
    rose = item_total(post.inventory, item_id) > item_total(pre.inventory, item_id)
    dwindled = _dropped_count(post, item_id) < _dropped_count(pre, item_id)
    if rose and (dwindled or _dropped_count(pre, item_id) == 0):
        # Nothing was ever seen on the ground: the row's "drop decreased" arm is
        # about a drop that was seen, and a picked-up stack with no earlier
        # sighting can only be read off the synced rise.
        return ActionResultClass.CONFIRMED
    if rose:
        return ActionResultClass.UNKNOWN
    if _dropped_count(pre, item_id) > 0 and _dropped_count(post, item_id) == 0:
        return ActionResultClass.FAILED
    return ActionResultClass.UNKNOWN


def verify_craft(
    *,
    pre: WorldObservationValue,
    post: WorldObservationValue,
    material_ids: Sequence[str],
    product_id: str,
) -> ActionResultClass:
    """§4 row three. Materials down and product up, both on the same synced
    revision, or nothing was confirmed — sending the packet, opening the window
    and clicking the slot are all events on the way, not the craft.

    The baseline is read out of `pre` rather than passed in, on purpose: the
    contract's word is that the material *decreased*, and a caller-supplied
    number invites the recipe's requirement (crafting consumes 3 planks) to be
    handed in where the pre-action total belongs (the Kin had 6). That mistake
    does not fail loudly — it just stops confirming.
    """

    if not _newer(pre, post) or not _inventory_synced(pre, post):
        return ActionResultClass.UNKNOWN
    materials_down = bool(material_ids) and all(
        item_total(post.inventory, item_id) < item_total(pre.inventory, item_id)
        for item_id in material_ids
    )
    product_up = item_total(post.inventory, product_id) > item_total(pre.inventory, product_id)
    if materials_down and product_up:
        return ActionResultClass.CONFIRMED
    return ActionResultClass.UNKNOWN


def verify_trade(
    *,
    pre: WorldObservationValue,
    post: WorldObservationValue,
    first_item_id: str,
    second_item_id: str,
    sell_item_id: str,
) -> ActionResultClass:
    """§4 row three, for a merchant: the asks down and the payout up on one synced
    revision, or nothing was confirmed.

    The item IDs rather than amounts, for `verify_craft`'s own reason: the contract's
    word is that the ask *decreased* and the payout *increased*, and handing in the
    offer's numbers where the pre-action totals belong would stop confirming without
    failing. The second ask is optional because most offers ask for one item; when
    the row named one it must come down too.
    """

    if not _newer(pre, post) or not _inventory_synced(pre, post):
        return ActionResultClass.UNKNOWN
    first_down = item_total(post.inventory, first_item_id) < item_total(
        pre.inventory, first_item_id
    )
    second_down = not second_item_id or item_total(post.inventory, second_item_id) < item_total(
        pre.inventory, second_item_id
    )
    sell_up = item_total(post.inventory, sell_item_id) > item_total(pre.inventory, sell_item_id)
    if first_down and second_down and sell_up:
        return ActionResultClass.CONFIRMED
    return ActionResultClass.UNKNOWN


def verify_hotbar_change(
    *,
    pre: WorldObservationValue,
    post: WorldObservationValue,
    slot: int,
    expected_item_id: str | None = None,
) -> ActionResultClass:
    """§4 row four. The later reading has to name the slot — and, when the
    caller could say what should be in hand, that item. A reading that still
    points at the old slot is exactly what the contract calls `unknown`."""

    if not _newer(pre, post):
        return ActionResultClass.UNKNOWN
    state = post.self_state
    if state.selected_slot is None or state.selected_slot != slot:
        return ActionResultClass.UNKNOWN
    if expected_item_id is None:
        return ActionResultClass.CONFIRMED
    if state.main_hand_item_id == expected_item_id:
        return ActionResultClass.CONFIRMED
    return ActionResultClass.UNKNOWN


def verify_use_effect(
    *,
    pre: WorldObservationValue,
    post: WorldObservationValue,
    held_item_id: str | None,
) -> ActionResultClass:
    """The use key's own row, and it has two confirming readings because the key
    does two different things depending on what the crosshair was on.

    Activating something — a villager, a chest, a door, a furnace — opens a
    handler, so a window that was not standing in `pre` and is standing in `post`
    is the effect. Placing what is in hand consumes one of it, so a *decrease* in
    the synced total of the held item is the effect. Either confirms; nothing else
    does, and neither is invented.

    The held-item arm is deliberately the mirror of `verify_craft`'s product
    check rather than a new count: it compares the two synced readings' totals of
    the item the pre-state's hand actually held (`held_item_id`, read out of
    `pre`, never passed in from a plan), and it requires a moved revision before
    it will believe a change is the server's and not a wish.

    `UNKNOWN` is the floor, never `FAILED`. A use on a block that was out of
    reach, a door that needs a key the Kin does not hold, or a placement landing
    on an already-occupied face is a real world the reading cannot distinguish
    from "the frame after the click has not arrived yet" — and §4's rule is that
    only a synced change confirms, so the absence of one is not proof of a
    failure. A skill that concluded `FAILED` here would be retrying a click with
    a side effect, which the contract forbids.
    """

    if not _newer(pre, post):
        return ActionResultClass.UNKNOWN
    pre_open = pre.gui is not None and pre.gui.sync_id is not None
    post_open = post.gui is not None and post.gui.sync_id is not None
    if post_open and not pre_open:
        return ActionResultClass.CONFIRMED
    if (
        held_item_id is not None
        and _inventory_synced(pre, post)
        and item_total(post.inventory, held_item_id) < item_total(pre.inventory, held_item_id)
    ):
        return ActionResultClass.CONFIRMED
    return ActionResultClass.UNKNOWN


def verify_consume_effect(
    *,
    pre: WorldObservationValue,
    post: WorldObservationValue,
    item_id: str,
) -> ActionResultClass:
    """The consume row: the hunger bar up and the stack down, on one synced reading.

    Eating has no window to open and no placement to watch — its two effects are the two
    the HUD itself shows. The bar rising is the meal; the stack shrinking is *this* item
    paying for it. Requiring both on the same reading is what keeps either alone from
    confirming: a bar that rose for any other reason (a command, an effect) without the
    stack moving is not this meal, and a stack that shrank without the bar rising is the
    item going somewhere else — dropped, moved, or the click landing on something that
    took it. The revision gate is the usual one: only the server's own sync makes a
    change believable, and both changes live in that same sync.

    `UNKNOWN` is the floor, never `FAILED`, for the same reason `verify_use_effect` has
    that floor: a frame that has not caught up yet and a meal the world genuinely
    declined are indistinguishable from two readings, and the contract forbids retrying
    a click on an unproven side effect. The precondition that the aim was clear means
    the click had no other target to spend itself on; everything else is waiting, and
    §4's rule is that nothing confirms without the sync.
    """

    if not _newer(pre, post) or not _inventory_synced(pre, post):
        return ActionResultClass.UNKNOWN
    eaten = item_total(post.inventory, item_id) < item_total(pre.inventory, item_id)
    restored = post.self_state.food > pre.self_state.food
    if eaten and restored:
        return ActionResultClass.CONFIRMED
    return ActionResultClass.UNKNOWN


def angle_to_degrees(*, dx: float, dy: float, dz: float) -> tuple[float, float]:
    """The look angles a player would aim at a visible offset, in the client's
    own units — the inverse of the client's own look-vector formula, and pure
    geometry: it turns toward something already on the entity list, which is the
    only reason any of this may be aimed at.

    Returns `(yaw, pitch)` with yaw in the client's own (-180..180] and pitch in
    -90..90; a zero-length offset has no direction and is refused by the caller
    checking finiteness of the inputs rather than by a clamp here.
    """

    if not all(math.isfinite(value) for value in (dx, dy, dz)):
        raise ValueError("an aim offset must be three finite numbers")
    if dx == 0.0 and dz == 0.0 and dy == 0.0:
        raise ValueError("an offset of zero has no direction to aim at")
    # (-180..180] rather than the symmetric range: north is one heading, and
    # `atan2` hands back -180 for it when the offset's x carries the sign of
    # zero, so the canonical answer has to be chosen rather than tolerated.
    yaw = 180.0 - ((180.0 - math.degrees(math.atan2(-dx, dz))) % 360.0)
    pitch = math.degrees(math.atan2(-dy, math.hypot(dx, dz)))
    return yaw, pitch


def angle_error_degrees(
    *, from_yaw: float, to_yaw: float, from_pitch: float, to_pitch: float
) -> float:
    """The worst of the two axis gaps, with yaw wrapped. Used to tell a turn
    that arrived from one that stopped twenty degrees short."""

    yaw_gap = abs((to_yaw - from_yaw + 180.0) % 360.0 - 180.0)
    return max(yaw_gap, abs(to_pitch - from_pitch))


def seen_drops(entities: Sequence[EntityCandidate], item_id: str) -> tuple[EntityCandidate, ...]:
    """The visible item stacks of one kind, nearest first. The list is already
    the Bridge's own radius-and-occlusion answer; nothing here looks anything up
    that the client did not render."""

    seen = [
        entity for entity in entities if entity.item_id == item_id and entity.item_count is not None
    ]

    def distance(entity: EntityCandidate) -> float:
        return math.dist((entity.relative_x, entity.relative_y, entity.relative_z), (0.0, 0.0, 0.0))

    return tuple(sorted(seen, key=distance))
