"""The player-equivalence boundary for what the client reports.

Kin may act on what a player could have seen. The Bridge proposes candidates and
this filter decides which of them the Runtime is allowed to treat as observed —
both for the join-time first snapshot and for the recurring S2 `WorldObservation`
values below, which share the HUD, inventory and entity rules because they are
the same client state read a second time, not a second source of truth.

Two properties matter more than the individual rules. The filter never guesses:
a candidate it cannot confirm is dropped and counted, so a false rejection is
visible instead of silent. And a snapshot that is not admitted yields no
entities at all, so a caller that forgets to check `admitted` still cannot act
on an unconfirmed world.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from minekin_core.domain.ids import Generation
from minekin_core.domain.session_material import (
    RecordedSessionMaterial,
    ReportedSessionIdentity,
    SessionMaterialVerdict,
    compare_session_material,
)

# Relative positions are reported from the local player, so this is a rendering
# and tracking range rather than a vision rule. The exact value still has to be
# calibrated against a real 1.21.4 client; until then it is deliberately
# generous, because the line-of-sight rule is the one doing the work.
DEFAULT_OBSERVATION_RADIUS_BLOCKS: Final[float] = 64.0

# Vanilla scales the HUD uses. A reading outside these is not a player state, so
# it is a broken or fabricated observation rather than something to clamp.
MAX_FOOD: Final[int] = 20
MAX_STACK_COUNT: Final[int] = 64


class EntityReason(StrEnum):
    """Why a proposed entity was not passed up, as a stable evidence token."""

    MISSING_IDENTITY = "MISSING_IDENTITY"
    DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
    NO_LINE_OF_SIGHT = "NO_LINE_OF_SIGHT"
    NOT_FINITE = "NOT_FINITE"
    TOO_FAR = "TOO_FAR"


class SnapshotReason(StrEnum):
    """Why a first snapshot was not admitted."""

    NOT_AUTHORITATIVE = "NOT_AUTHORITATIVE"
    GENERATION_MISMATCH = "GENERATION_MISMATCH"
    SESSION_MATERIAL_MISMATCH = "SESSION_MATERIAL_MISMATCH"
    SELF_STATE_INCOHERENT = "SELF_STATE_INCOHERENT"
    INVENTORY_INVALID = "INVENTORY_INVALID"


class IntegrityViolation(StrEnum):
    """The specific finding behind a self-state or inventory rejection."""

    SELF_NOT_FINITE = "SELF_NOT_FINITE"
    MAX_HEALTH_NOT_POSITIVE = "MAX_HEALTH_NOT_POSITIVE"
    HEALTH_OUT_OF_RANGE = "HEALTH_OUT_OF_RANGE"
    FOOD_OUT_OF_RANGE = "FOOD_OUT_OF_RANGE"
    SATURATION_NEGATIVE = "SATURATION_NEGATIVE"
    ALIVE_DISAGREES_WITH_HEALTH = "ALIVE_DISAGREES_WITH_HEALTH"
    INVENTORY_REVISION_UNSET = "INVENTORY_REVISION_UNSET"
    STACK_COUNT_OUT_OF_RANGE = "STACK_COUNT_OUT_OF_RANGE"
    STACK_ITEM_MISSING = "STACK_ITEM_MISSING"
    STACK_SLOT_DUPLICATED = "STACK_SLOT_DUPLICATED"
    # The S2 reading surface. Each is something the Bridge can legitimately get
    # wrong on the client thread, and which a Kin must not act through.
    YAW_OUT_OF_RANGE = "YAW_OUT_OF_RANGE"
    PITCH_OUT_OF_RANGE = "PITCH_OUT_OF_RANGE"
    SELECTED_SLOT_OUT_OF_RANGE = "SELECTED_SLOT_OUT_OF_RANGE"
    MAIN_HAND_WITHOUT_SLOT = "MAIN_HAND_WITHOUT_SLOT"
    AIM_KIND_UNREAD = "AIM_KIND_UNREAD"
    AIM_BLOCK_WITHOUT_TARGET = "AIM_BLOCK_WITHOUT_TARGET"
    AIM_BLOCK_STATE_MISSING = "AIM_BLOCK_STATE_MISSING"
    AIM_ENTITY_WITHOUT_ID = "AIM_ENTITY_WITHOUT_ID"
    AIM_TARGETED_BLOCK_ID_MISSING = "AIM_TARGETED_BLOCK_ID_MISSING"
    AIM_DISTANCE_NOT_FINITE = "AIM_DISTANCE_NOT_FINITE"
    MINING_PROGRESS_OUT_OF_RANGE = "MINING_PROGRESS_OUT_OF_RANGE"
    ENTITY_ITEM_ON_NON_ITEM = "ENTITY_ITEM_ON_NON_ITEM"
    ENTITY_ITEM_INCOHERENT = "ENTITY_ITEM_INCOHERENT"


# The client renders a dropped item as this entity type, and the item fields of a
# `VisibleEntity` are only ever about such an entity. Named from the client's own
# entity id rather than inferred, because "an entity's hidden inventory is not
# part of what looking at it shows" is the rule, and the rule needs a subject.
DROPPED_ITEM_ENTITY_TYPE: Final[str] = "minecraft:item"

# The vanilla look-angle and hotbar ranges. A reading outside them is not a
# player state, so it is rejected rather than clamped, as the HUD fields above.
MAX_YAW_DEGREES: Final[float] = 180.0
MAX_PITCH_DEGREES: Final[float] = 90.0
HOTBAR_SLOT_COUNT: Final[int] = 9


@dataclass(frozen=True, slots=True)
class SelfStateValue:
    """The HUD fields coherence is decided from, not a mirror of the message.

    The S2 fields are `None` when the Bridge did not read them — "no position"
    and "position zero" are different facts and only one of them is ordinary —
    while the HUD fields keep the first snapshot's always-reported shape.
    """

    health: float
    max_health: float
    food: int
    saturation: float
    alive: bool
    x: float | None = None
    y: float | None = None
    z: float | None = None
    yaw_degrees: float | None = None
    pitch_degrees: float | None = None
    #: 0-based hotbar index of the stack in hand. `None` means the hotbar was not
    #: read at all; it is never 0 for the same reason an empty hand is not slot 0.
    selected_slot: int | None = None
    #: `None` means the hand is empty — per the S2 contract the Bridge reports an
    #: empty hand by leaving this absent, not by naming a fake item. "The hotbar
    #: was not read at all" is `selected_slot` being `None`, not this.
    main_hand_item_id: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryStackValue:
    """One summary stack: what coherence needs, without the item damage or NBT."""

    slot: int
    item_id: str
    count: int


@dataclass(frozen=True, slots=True)
class InventoryValue:
    revision: int
    stacks: tuple[InventoryStackValue, ...]


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    """One proposed observation, before the filter decides anything about it."""

    observation_id: str
    entity_type: str
    relative_x: float
    relative_y: float
    relative_z: float
    line_of_sight: bool
    #: What a dropped item is and how many, filled only for entities the client
    #: renders as items. An entity's hidden inventory is not "seen", so nothing
    #: else carries these, and `None` on both means the entity is not an item.
    #: There are no entity world coordinates on this surface — deliberately: a
    #: world position would locate every entity the renderer holds, seen or not,
    #: so navigation composes `SelfState`'s position with the relative offset.
    item_id: str | None = None
    item_count: int | None = None


@dataclass(frozen=True, slots=True)
class EntityRejection:
    observation_id: str
    reason: EntityReason


@dataclass(frozen=True, slots=True)
class VisibleWorld:
    """What the Runtime is allowed to treat as observed, plus what it is not."""

    accepted: tuple[EntityCandidate, ...]
    rejected: tuple[EntityRejection, ...]

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    def rejections_for(self, reason: EntityReason) -> tuple[EntityRejection, ...]:
        return tuple(item for item in self.rejected if item.reason is reason)

    def as_document(self) -> dict[str, object]:
        return {
            "accepted": [entity.observation_id for entity in self.accepted],
            "rejected": [item.reason.value for item in self.rejected],
        }


EMPTY_WORLD: Final[VisibleWorld] = VisibleWorld(accepted=(), rejected=())


@dataclass(frozen=True, slots=True)
class SnapshotAdmission:
    """The verdict on a first snapshot, and the only entities that may be used."""

    admitted: bool
    reasons: tuple[SnapshotReason, ...]
    visible_world: VisibleWorld
    session: SessionMaterialVerdict
    game_tick: int
    integrity: tuple[IntegrityViolation, ...] = ()

    def as_document(self) -> dict[str, object]:
        return {
            "admitted": self.admitted,
            "reasons": [reason.value for reason in self.reasons],
            "game_tick": self.game_tick,
            "integrity": [violation.value for violation in self.integrity],
            "session": self.session.as_document(),
            "visible_world": self.visible_world.as_document(),
        }


def self_state_violations(state: SelfStateValue) -> tuple[IntegrityViolation, ...]:
    """Check the HUD reading against what vanilla can actually report.

    Values are rejected rather than clamped: a health of 300 is not a player at
    full health, it is a reading nobody should act on. The S2 fields are checked
    only when the Bridge read them — an absent position is a reported absence, not
    a violation, and the rules below are the same reject-don't-clamp rules with a
    finiteness gate before every range.
    """

    violations: set[IntegrityViolation] = set()
    position = tuple(value for value in (state.x, state.y, state.z) if value is not None)
    if not all(
        math.isfinite(value)
        for value in (state.health, state.max_health, state.saturation, *position)
    ):
        violations.add(IntegrityViolation.SELF_NOT_FINITE)
    if isinstance(state.max_health, bool) or not state.max_health > 0:
        violations.add(IntegrityViolation.MAX_HEALTH_NOT_POSITIVE)
    # NaN compares false against every bound, so a non-finite health would slip
    # through the range check below.
    if not math.isfinite(state.health) or not 0 <= state.health <= state.max_health:
        violations.add(IntegrityViolation.HEALTH_OUT_OF_RANGE)
    # `bool` is an `int`, so a JSON `true` would otherwise pass as food 1.
    if isinstance(state.food, bool) or not 0 <= state.food <= MAX_FOOD:
        violations.add(IntegrityViolation.FOOD_OUT_OF_RANGE)
    if math.isfinite(state.saturation) and state.saturation < 0:
        violations.add(IntegrityViolation.SATURATION_NEGATIVE)
    if state.alive != (state.health > 0):
        violations.add(IntegrityViolation.ALIVE_DISAGREES_WITH_HEALTH)
    for value, limit, token in (
        (state.yaw_degrees, MAX_YAW_DEGREES, IntegrityViolation.YAW_OUT_OF_RANGE),
        (state.pitch_degrees, MAX_PITCH_DEGREES, IntegrityViolation.PITCH_OUT_OF_RANGE),
    ):
        # A non-finite angle is a broken read, not an out-of-range one, and the
        # finiteness rule above already calls it out as SELF_NOT_FINITE only for
        # position; angles get their own token because the refusal means different
        # things to whoever steers the client.
        if value is not None and (not math.isfinite(value) or abs(value) > limit):
            violations.add(token)
    if state.selected_slot is not None and (
        isinstance(state.selected_slot, bool) or not 0 <= state.selected_slot < HOTBAR_SLOT_COUNT
    ):
        violations.add(IntegrityViolation.SELECTED_SLOT_OUT_OF_RANGE)
    if state.main_hand_item_id is not None and state.selected_slot is None:
        # The hand's stack comes out of the hotbar, so an item in hand with no
        # slot read is a pair of reports that cannot both be true of one client.
        violations.add(IntegrityViolation.MAIN_HAND_WITHOUT_SLOT)
    return tuple(sorted(violations))


def inventory_violations(inventory: InventoryValue) -> tuple[IntegrityViolation, ...]:
    """Check the inventory summary before anything treats it as the real contents."""

    violations: set[IntegrityViolation] = set()
    # Revision zero means the Bridge never populated the summary, so nothing here
    # can be correlated with a known inventory state.
    if isinstance(inventory.revision, bool) or inventory.revision < 1:
        violations.add(IntegrityViolation.INVENTORY_REVISION_UNSET)

    slots: set[int] = set()
    for stack in inventory.stacks:
        if not stack.item_id.strip():
            violations.add(IntegrityViolation.STACK_ITEM_MISSING)
        if isinstance(stack.count, bool) or not 1 <= stack.count <= MAX_STACK_COUNT:
            violations.add(IntegrityViolation.STACK_COUNT_OUT_OF_RANGE)
        if stack.slot in slots:
            # Two stacks in one slot means the summary does not describe a real
            # inventory, so its counts cannot be trusted either.
            violations.add(IntegrityViolation.STACK_SLOT_DUPLICATED)
        slots.add(stack.slot)
    return tuple(sorted(violations))


class AimKind(StrEnum):
    """What the client's crosshair was on, in the reader's own words.

    `MISS` is "looked and saw nothing"; the absence of a whole `AimTargetValue`
    from the observation is "the Bridge never looked". A plan that treats those
    alike would break a block nobody saw, which is why they are two different
    facts in this type rather than one nullable field with a zero variant.
    """

    MISS = "MISS"
    BLOCK = "BLOCK"
    ENTITY = "ENTITY"
    #: A target record arrived but named no branch: the wire's UNSPECIFIED. It is
    #: not `MISS` — `MISS` is a read that saw nothing — and an observation holding
    #: it fails coherence rather than being routed on.
    UNREAD = "UNREAD"


class AimFace(StrEnum):
    """The block face the client's own hit result carries.

    `NOT_READ` is the wire's unspecified value — a face the Bridge did not name —
    and `UNKNOWN` is the client's own word for a hit that carries no face. They
    are not folded together because they came from different sides of the read.
    """

    NOT_READ = "NOT_READ"
    UNKNOWN = "UNKNOWN"
    DOWN = "DOWN"
    UP = "UP"
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    WEST = "WEST"
    EAST = "EAST"


@dataclass(frozen=True, slots=True)
class BlockTargetValue:
    """One block, and the face of it the client means. Position only, never a
    neighbour searched around it."""

    x: int
    y: int
    z: int
    face: AimFace


@dataclass(frozen=True, slots=True)
class AimTargetValue:
    """One read of the crosshair. Only the branch `kind` selects is filled; the
    decoder leaves the other branch's fields empty rather than inventing them."""

    game_tick: int
    kind: AimKind
    block: BlockTargetValue | None = None
    #: What the client is rendering under the crosshair, as the game names the
    #: block (`minecraft:oak_log`) — the targeting, not the block's state: no
    #: property list and no neighbours, and absent for anything but a block hit.
    targeted_block_id: str = ""
    entity_observation_id: str = ""
    entity_type: str = ""
    distance: float | None = None


@dataclass(frozen=True, slots=True)
class MiningProgressValue:
    """The player-visible break animation, 0..1 — not a tick-remaining estimate."""

    game_tick: int
    target: BlockTargetValue
    progress: float


@dataclass(frozen=True, slots=True)
class GuiScreenValue:
    """The open screen and its handler id. `sync_id` is `None` when no screen is
    open, because 0 is a legal handler id (the player's own inventory) and cannot
    double as "there is none".

    `craftable_recipe_ids` is the recipe book the *client* reports for the grid it has
    open: the namespaced ids it can craft right now, given the items in that grid. It is
    empty when no crafting screen is open (there is then no grid whose availability the
    client can speak for). This is the world's answer to "can this be made now" — the
    curated catalog only names products and infers grid shapes; whether a given bag and
    a given grid can actually pay is read from here, and a product the client does not
    name here is answered as not-craftable-now, never guessed.
    """

    screen_id: str
    sync_id: int | None
    craftable_recipe_ids: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class WorldObservationValue:
    """The recurring player-equivalent view, at the tick the Bridge names.

    A decoded message, not an adjudicated one: `world_observation_violations` is
    what decides whether this reading may be acted through.
    """

    generation: int
    game_tick: int
    self_state: SelfStateValue
    aim: AimTargetValue | None
    inventory: InventoryValue
    visible_entities: tuple[EntityCandidate, ...]
    mining: MiningProgressValue | None
    gui: GuiScreenValue | None


def world_observation_violations(
    observation: WorldObservationValue,
) -> tuple[IntegrityViolation, ...]:
    """Everything incoherent about one recurring reading, in the existing style.

    The self-state and inventory rules are the first snapshot's, unchanged; what
    is added here is what only the S2 surface can get wrong: an aim that claims a
    branch it did not fill, item fields on an entity the client does not render
    as an item, a break progress outside the animation's own range.
    """

    violations: set[IntegrityViolation] = set(self_state_violations(observation.self_state))
    violations.update(inventory_violations(observation.inventory))
    aim = observation.aim
    if aim is not None:
        if aim.kind is AimKind.UNREAD:
            violations.add(IntegrityViolation.AIM_KIND_UNREAD)
        if aim.kind is AimKind.BLOCK:
            if aim.block is None:
                violations.add(IntegrityViolation.AIM_BLOCK_WITHOUT_TARGET)
            elif not aim.targeted_block_id.strip():
                violations.add(IntegrityViolation.AIM_TARGETED_BLOCK_ID_MISSING)
        if aim.kind is AimKind.ENTITY and not aim.entity_observation_id.strip():
            violations.add(IntegrityViolation.AIM_ENTITY_WITHOUT_ID)
        if aim.distance is not None and not math.isfinite(aim.distance):
            violations.add(IntegrityViolation.AIM_DISTANCE_NOT_FINITE)
    mining = observation.mining
    if mining is not None and (
        not math.isfinite(mining.progress) or not 0.0 <= mining.progress <= 1.0
    ):
        violations.add(IntegrityViolation.MINING_PROGRESS_OUT_OF_RANGE)
    for entity in observation.visible_entities:
        if entity.item_id is not None or entity.item_count is not None:
            if entity.entity_type != DROPPED_ITEM_ENTITY_TYPE:
                # An entity's hidden inventory is not part of what looking at it
                # shows, so item fields on anything the client does not render as
                # a dropped item are a read from somewhere else.
                violations.add(IntegrityViolation.ENTITY_ITEM_ON_NON_ITEM)
            elif entity.item_id is None or entity.item_count is None:
                # The pair identifies the stack a player picks up; half of it
                # says nothing about what is on the ground.
                violations.add(IntegrityViolation.ENTITY_ITEM_INCOHERENT)
            elif not entity.item_id.strip():
                violations.add(IntegrityViolation.ENTITY_ITEM_INCOHERENT)
    return tuple(sorted(violations))


def filter_visible_entities(
    entities: tuple[EntityCandidate, ...],
    *,
    radius_blocks: float = DEFAULT_OBSERVATION_RADIUS_BLOCKS,
) -> VisibleWorld:
    """Keep only the candidates a player could plausibly have seen.

    A duplicate `observation_id` is rejected for both occurrences: the identifier
    is the token upper layers act on, so an ambiguous token is worse than a
    missing one.
    """

    counts: dict[str, int] = {}
    for entity in entities:
        counts[entity.observation_id] = counts.get(entity.observation_id, 0) + 1

    accepted: list[EntityCandidate] = []
    rejected: list[EntityRejection] = []
    for entity in entities:
        reason = _rejection_reason(entity, counts, radius_blocks)
        if reason is None:
            accepted.append(entity)
        else:
            rejected.append(EntityRejection(entity.observation_id, reason))
    return VisibleWorld(accepted=tuple(accepted), rejected=tuple(rejected))


def _rejection_reason(
    entity: EntityCandidate, counts: dict[str, int], radius_blocks: float
) -> EntityReason | None:
    if not entity.observation_id.strip():
        return EntityReason.MISSING_IDENTITY
    if counts.get(entity.observation_id, 0) > 1:
        return EntityReason.DUPLICATE_IDENTITY
    if not entity.line_of_sight:
        # Occlusion is the whole point: a candidate the client cannot confirm is
        # dropped rather than passed up with an assumed position.
        return EntityReason.NO_LINE_OF_SIGHT
    coordinates = (entity.relative_x, entity.relative_y, entity.relative_z)
    # NaN compares false against every bound, so a naive range check would let a
    # non-finite coordinate through the distance rule below.
    if not all(math.isfinite(value) for value in coordinates):
        return EntityReason.NOT_FINITE
    if math.dist(coordinates, (0.0, 0.0, 0.0)) > radius_blocks:
        return EntityReason.TOO_FAR
    return None


def _is_current_generation(generation: Generation, snapshot_generation: object) -> bool:
    """A snapshot from a closed generation is not merely stale; it is not ours."""

    if isinstance(snapshot_generation, bool) or not isinstance(snapshot_generation, int):
        return False
    if snapshot_generation < 1:
        return False
    return generation.accepts(Generation(snapshot_generation))


def admit_snapshot(
    *,
    authoritative: bool,
    snapshot_generation: int,
    generation: Generation,
    game_tick: int,
    entities: tuple[EntityCandidate, ...],
    recorded: RecordedSessionMaterial,
    reported: ReportedSessionIdentity,
    self_state: SelfStateValue,
    inventory: InventoryValue,
    radius_blocks: float = DEFAULT_OBSERVATION_RADIUS_BLOCKS,
) -> SnapshotAdmission:
    """Decide whether a first snapshot may become the basis of PLAYABLE.

    The visible world is filtered either way, because the rejection counts are
    evidence. The accepted entities are withheld unless the snapshot is admitted.
    """

    visible_world = filter_visible_entities(entities, radius_blocks=radius_blocks)
    session = compare_session_material(recorded, reported)
    self_violations = self_state_violations(self_state)
    inventory_findings = inventory_violations(inventory)
    integrity = tuple(sorted({*self_violations, *inventory_findings}))

    reasons: set[SnapshotReason] = set()
    if not authoritative:
        reasons.add(SnapshotReason.NOT_AUTHORITATIVE)
    if not _is_current_generation(generation, snapshot_generation):
        reasons.add(SnapshotReason.GENERATION_MISMATCH)
    if not session.matched:
        reasons.add(SnapshotReason.SESSION_MATERIAL_MISMATCH)
    if self_violations:
        reasons.add(SnapshotReason.SELF_STATE_INCOHERENT)
    if inventory_findings:
        reasons.add(SnapshotReason.INVENTORY_INVALID)

    admitted = not reasons
    return SnapshotAdmission(
        admitted=admitted,
        reasons=tuple(sorted(reasons)),
        visible_world=visible_world if admitted else VisibleWorld((), visible_world.rejected),
        session=session,
        game_tick=game_tick,
        integrity=integrity,
    )
