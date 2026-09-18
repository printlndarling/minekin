"""The player-equivalence boundary for the first snapshot.

Kin may act on what a player could have seen. The Bridge proposes candidates and
this filter decides which of them the Runtime is allowed to treat as observed.

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


@dataclass(frozen=True, slots=True)
class SelfStateValue:
    """The HUD fields coherence is decided from, not a mirror of the message."""

    health: float
    max_health: float
    food: int
    saturation: float
    alive: bool


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
    full health, it is a reading nobody should act on.
    """

    violations: set[IntegrityViolation] = set()
    if not all(
        math.isfinite(value) for value in (state.health, state.max_health, state.saturation)
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
