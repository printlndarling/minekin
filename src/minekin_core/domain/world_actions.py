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
    SCREEN_CAPABILITY,
)
from minekin_core.domain.perception import (
    AimKind,
    BlockTargetValue,
    EntityCandidate,
    InventoryValue,
    WorldObservationValue,
)

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
    "select_hotbar": frozenset({HOTBAR_CAPABILITY}),
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
