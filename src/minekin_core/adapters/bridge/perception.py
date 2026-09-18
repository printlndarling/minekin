"""Decode a first snapshot from the wire and put it through the boundary filter."""

from __future__ import annotations

from minekin_core.adapters.bridge.session_report import decode_session_identity
from minekin_core.domain.ids import Generation
from minekin_core.domain.perception import (
    DEFAULT_OBSERVATION_RADIUS_BLOCKS,
    EntityCandidate,
    SnapshotAdmission,
    admit_snapshot,
)
from minekin_core.domain.session_material import RecordedSessionMaterial
from minekin_core.generated.minekin.v1 import observation_pb2


def decode_entities(
    snapshot: observation_pb2.InitialObservation,
) -> tuple[EntityCandidate, ...]:
    return tuple(
        EntityCandidate(
            observation_id=entity.observation_id,
            entity_type=entity.entity_type,
            relative_x=entity.relative_x,
            relative_y=entity.relative_y,
            relative_z=entity.relative_z,
            line_of_sight=entity.line_of_sight,
        )
        for entity in snapshot.visible_entities
    )


def admit_first_snapshot(
    snapshot: observation_pb2.InitialObservation,
    *,
    generation: Generation,
    recorded: RecordedSessionMaterial,
    radius_blocks: float = DEFAULT_OBSERVATION_RADIUS_BLOCKS,
) -> SnapshotAdmission:
    """The one path from a wire snapshot to entities the Runtime may act on."""

    return admit_snapshot(
        authoritative=snapshot.authoritative,
        snapshot_generation=snapshot.generation,
        generation=generation,
        game_tick=snapshot.game_tick,
        entities=decode_entities(snapshot),
        recorded=recorded,
        reported=decode_session_identity(snapshot.session_identity),
        radius_blocks=radius_blocks,
    )
