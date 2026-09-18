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

    def as_document(self) -> dict[str, object]:
        return {
            "admitted": self.admitted,
            "reasons": [reason.value for reason in self.reasons],
            "game_tick": self.game_tick,
            "session": self.session.as_document(),
            "visible_world": self.visible_world.as_document(),
        }


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
    radius_blocks: float = DEFAULT_OBSERVATION_RADIUS_BLOCKS,
) -> SnapshotAdmission:
    """Decide whether a first snapshot may become the basis of PLAYABLE.

    The visible world is filtered either way, because the rejection counts are
    evidence. The accepted entities are withheld unless the snapshot is admitted.
    """

    visible_world = filter_visible_entities(entities, radius_blocks=radius_blocks)
    session = compare_session_material(recorded, reported)

    reasons: set[SnapshotReason] = set()
    if not authoritative:
        reasons.add(SnapshotReason.NOT_AUTHORITATIVE)
    if not _is_current_generation(generation, snapshot_generation):
        reasons.add(SnapshotReason.GENERATION_MISMATCH)
    if not session.matched:
        reasons.add(SnapshotReason.SESSION_MATERIAL_MISMATCH)

    admitted = not reasons
    return SnapshotAdmission(
        admitted=admitted,
        reasons=tuple(sorted(reasons)),
        visible_world=visible_world if admitted else VisibleWorld((), visible_world.rejected),
        session=session,
        game_tick=game_tick,
    )
