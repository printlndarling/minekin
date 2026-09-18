from __future__ import annotations

import math
from dataclasses import replace

import pytest

from minekin_core.adapters.bridge.perception import admit_first_snapshot, decode_entities
from minekin_core.domain.ids import Generation
from minekin_core.domain.perception import (
    EntityCandidate,
    EntityReason,
    IntegrityViolation,
    InventoryStackValue,
    InventoryValue,
    SelfStateValue,
    SnapshotAdmission,
    SnapshotReason,
    admit_snapshot,
    filter_visible_entities,
    inventory_violations,
    self_state_violations,
)
from minekin_core.domain.session_material import (
    RecordedSessionMaterial,
    ReportedSessionIdentity,
)
from minekin_core.generated.minekin.v1 import observation_pb2, session_pb2

RECORDED = RecordedSessionMaterial(
    identity_candidate_id="prism-parity",
    username="Kin",
    uuid_argv="8f40376bc23f3ef1b5535564eea75639",
    client_id_present=False,
    xuid_present=False,
)
REPORTED = ReportedSessionIdentity(
    identity_candidate_id="prism-parity",
    username="Kin",
    uuid="8f40376b-c23f-3ef1-b553-5564eea75639",
    account_type="offline",
    client_id_present=False,
    xuid_present=False,
    credential_values_exposed=False,
)
HEALTHY = SelfStateValue(health=20.0, max_health=20.0, food=20, saturation=5.0, alive=True)
LOADED = InventoryValue(
    revision=1,
    stacks=(InventoryStackValue(slot=0, item_id="minecraft:stone", count=64),),
)


def entity(
    *,
    observation_id: str = "obs-1",
    entity_type: str = "minecraft:zombie",
    position: tuple[float, float, float] = (1.0, 0.0, 1.0),
    line_of_sight: bool = True,
) -> EntityCandidate:
    return EntityCandidate(
        observation_id=observation_id,
        entity_type=entity_type,
        relative_x=position[0],
        relative_y=position[1],
        relative_z=position[2],
        line_of_sight=line_of_sight,
    )


def admit(
    *,
    authoritative: bool = True,
    snapshot_generation: int = 7,
    generation: int = 7,
    game_tick: int = 100,
    entities: tuple[EntityCandidate, ...] = (),
    reported: ReportedSessionIdentity = REPORTED,
    radius_blocks: float = 64.0,
    self_state: SelfStateValue = HEALTHY,
    inventory: InventoryValue = LOADED,
) -> SnapshotAdmission:
    return admit_snapshot(
        authoritative=authoritative,
        snapshot_generation=snapshot_generation,
        generation=Generation(generation),
        game_tick=game_tick,
        entities=entities,
        recorded=RECORDED,
        reported=reported,
        self_state=self_state,
        inventory=inventory,
        radius_blocks=radius_blocks,
    )


def snapshot(
    *,
    generation: int = 7,
    game_tick: int = 100,
    authoritative: bool = True,
    entities: tuple[EntityCandidate, ...] = (),
    session: ReportedSessionIdentity = REPORTED,
    self_state: SelfStateValue = HEALTHY,
    inventory: InventoryValue = LOADED,
) -> observation_pb2.InitialObservation:
    message = observation_pb2.InitialObservation(
        generation=generation,
        game_tick=game_tick,
        authoritative=authoritative,
        session_identity=session_pb2.SessionIdentityReport(
            identity_candidate_id=session.identity_candidate_id,
            session_username=session.username,
            session_uuid=session.uuid,
            session_account_type=session.account_type,
            session_xuid_present=session.xuid_present,
            session_client_id_present=session.client_id_present,
            credential_values_exposed=session.credential_values_exposed,
        ),
        self=observation_pb2.SelfState(
            health=self_state.health,
            max_health=self_state.max_health,
            food=self_state.food,
            saturation=self_state.saturation,
            alive=self_state.alive,
        ),
        inventory=observation_pb2.InventorySummary(revision=inventory.revision),
    )
    for stack in inventory.stacks:
        message.inventory.stacks.add(slot=stack.slot, item_id=stack.item_id, count=stack.count)
    for candidate in entities:
        message.visible_entities.add(
            observation_id=candidate.observation_id,
            entity_type=candidate.entity_type,
            relative_x=candidate.relative_x,
            relative_y=candidate.relative_y,
            relative_z=candidate.relative_z,
            line_of_sight=candidate.line_of_sight,
        )
    return message


def test_a_visible_entity_is_passed_up() -> None:
    world = filter_visible_entities((entity(),))

    assert [item.observation_id for item in world.accepted] == ["obs-1"]
    assert world.rejected == ()


def test_an_entity_behind_a_wall_is_dropped_and_counted() -> None:
    """Occlusion is the rule the whole filter exists for."""

    world = filter_visible_entities((entity(line_of_sight=False),))

    assert world.accepted == ()
    assert world.rejected_count == 1
    assert world.rejected[0].reason is EntityReason.NO_LINE_OF_SIGHT


def test_nothing_about_a_dropped_candidate_reaches_the_accepted_set() -> None:
    world = filter_visible_entities(
        (entity(line_of_sight=False, position=(3.0, 4.0, 12.0)),),
    )

    assert world.accepted == ()
    assert world.as_document()["accepted"] == []


@pytest.mark.parametrize(
    "position",
    [(float("nan"), 0.0, 0.0), (0.0, math.inf, 0.0), (0.0, 0.0, -math.inf)],
)
def test_a_non_finite_position_is_rejected_before_the_range_check(
    position: tuple[float, float, float],
) -> None:
    """NaN compares false against every bound, so the range rule alone would admit it."""

    world = filter_visible_entities((entity(position=position),))

    assert world.accepted == ()
    assert world.rejected[0].reason is EntityReason.NOT_FINITE


def test_a_distant_entity_is_dropped() -> None:
    world = filter_visible_entities((entity(position=(100.0, 0.0, 0.0)),), radius_blocks=64.0)

    assert world.accepted == ()
    assert world.rejected[0].reason is EntityReason.TOO_FAR


def test_an_entity_just_inside_the_radius_is_kept() -> None:
    world = filter_visible_entities((entity(position=(63.9, 0.0, 0.0)),), radius_blocks=64.0)

    assert len(world.accepted) == 1


@pytest.mark.parametrize("observation_id", ["", "   "])
def test_an_entity_without_a_target_token_is_dropped(observation_id: str) -> None:
    world = filter_visible_entities((entity(observation_id=observation_id),))

    assert world.rejected[0].reason is EntityReason.MISSING_IDENTITY


def test_an_ambiguous_target_token_drops_both_occurrences() -> None:
    """An ambiguous identifier is worse than a missing one: upper layers act on it."""

    world = filter_visible_entities(
        (
            entity(observation_id="obs-1"),
            entity(observation_id="obs-1", position=(2.0, 0.0, 2.0)),
        )
    )

    assert world.accepted == ()
    assert world.rejected_count == 2
    assert world.rejections_for(EntityReason.DUPLICATE_IDENTITY) != ()


def test_occlusion_misses_and_distance_misses_are_reported_separately() -> None:
    world = filter_visible_entities(
        (
            entity(observation_id="near"),
            entity(observation_id="hidden", line_of_sight=False),
            entity(observation_id="far", position=(200.0, 0.0, 0.0)),
        )
    )

    assert [item.observation_id for item in world.accepted] == ["near"]
    assert len(world.rejections_for(EntityReason.NO_LINE_OF_SIGHT)) == 1
    assert len(world.rejections_for(EntityReason.TOO_FAR)) == 1
    assert world.rejections_for(EntityReason.NOT_FINITE) == ()


def test_an_admitted_snapshot_hands_up_its_visible_world() -> None:
    admission = admit(entities=(entity(),))

    assert admission.admitted
    assert admission.reasons == ()
    assert [item.observation_id for item in admission.visible_world.accepted] == ["obs-1"]


def test_a_non_authoritative_snapshot_is_not_admitted() -> None:
    admission = admit(authoritative=False, entities=(entity(),))

    assert not admission.admitted
    assert admission.reasons == (SnapshotReason.NOT_AUTHORITATIVE,)


@pytest.mark.parametrize("snapshot_generation", [0, 6, 8])
def test_a_snapshot_from_another_generation_is_not_admitted(snapshot_generation: int) -> None:
    admission = admit(snapshot_generation=snapshot_generation)

    assert not admission.admitted
    assert admission.reasons == (SnapshotReason.GENERATION_MISMATCH,)


def test_a_snapshot_for_another_identity_is_not_admitted() -> None:
    admission = admit(reported=replace(REPORTED, username="Notch"))

    assert not admission.admitted
    assert admission.reasons == (SnapshotReason.SESSION_MATERIAL_MISMATCH,)


def test_every_reason_is_collected_in_a_stable_order() -> None:
    admission = admit(
        authoritative=False,
        snapshot_generation=3,
        reported=replace(REPORTED, uuid="not-a-uuid"),
    )

    assert admission.reasons == tuple(sorted(admission.reasons))
    assert set(admission.reasons) == {
        SnapshotReason.NOT_AUTHORITATIVE,
        SnapshotReason.GENERATION_MISMATCH,
        SnapshotReason.SESSION_MATERIAL_MISMATCH,
    }


def test_a_rejected_snapshot_hands_up_nothing() -> None:
    """A caller that forgets to check `admitted` still cannot act on the world."""

    admission = admit(authoritative=False, entities=(entity(),))

    assert admission.visible_world.accepted == ()


def test_a_rejected_snapshot_still_reports_what_it_dropped() -> None:
    admission = admit(
        authoritative=False,
        entities=(entity(), entity(observation_id="hidden", line_of_sight=False)),
    )

    assert admission.visible_world.accepted == ()
    assert admission.visible_world.rejected_count == 1


def test_the_admission_document_is_evidence_ready() -> None:
    admission = admit(
        authoritative=False,
        entities=(entity(), entity(observation_id="hidden", line_of_sight=False)),
    )

    assert admission.as_document() == {
        "admitted": False,
        "reasons": ["NOT_AUTHORITATIVE"],
        "game_tick": 100,
        "integrity": [],
        "session": {
            "matched": True,
            "mismatches": [],
            "observed_account_type": "offline",
        },
        "visible_world": {"accepted": [], "rejected": ["NO_LINE_OF_SIGHT"]},
    }


def test_the_wire_snapshot_decodes_and_is_admitted() -> None:
    admission = admit_first_snapshot(
        snapshot(entities=(entity(), entity(observation_id="hidden", line_of_sight=False))),
        generation=Generation(7),
        recorded=RECORDED,
    )

    assert admission.admitted
    assert [item.observation_id for item in admission.visible_world.accepted] == ["obs-1"]
    assert admission.visible_world.rejected_count == 1


def test_a_wire_snapshot_without_a_session_report_is_not_admitted() -> None:
    admission = admit_first_snapshot(
        observation_pb2.InitialObservation(generation=7, game_tick=1, authoritative=True),
        generation=Generation(7),
        recorded=RECORDED,
    )

    assert not admission.admitted
    assert SnapshotReason.SESSION_MATERIAL_MISMATCH in admission.reasons


def test_an_empty_entity_list_decodes_to_an_empty_world() -> None:
    assert decode_entities(observation_pb2.InitialObservation()) == ()


def test_a_healthy_self_state_has_no_violations() -> None:
    assert self_state_violations(HEALTHY) == ()


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (replace(HEALTHY, max_health=0.0), IntegrityViolation.MAX_HEALTH_NOT_POSITIVE),
        (replace(HEALTHY, max_health=-1.0), IntegrityViolation.MAX_HEALTH_NOT_POSITIVE),
        (replace(HEALTHY, health=21.0), IntegrityViolation.HEALTH_OUT_OF_RANGE),
        (replace(HEALTHY, health=-1.0), IntegrityViolation.HEALTH_OUT_OF_RANGE),
        (replace(HEALTHY, health=float("nan")), IntegrityViolation.HEALTH_OUT_OF_RANGE),
        (replace(HEALTHY, food=21), IntegrityViolation.FOOD_OUT_OF_RANGE),
        (replace(HEALTHY, food=-1), IntegrityViolation.FOOD_OUT_OF_RANGE),
        # `True` is an int, so without the bool guard it would read as food 1.
        (replace(HEALTHY, food=True), IntegrityViolation.FOOD_OUT_OF_RANGE),
        (replace(HEALTHY, saturation=-0.1), IntegrityViolation.SATURATION_NEGATIVE),
        (replace(HEALTHY, health=0.0), IntegrityViolation.ALIVE_DISAGREES_WITH_HEALTH),
        (
            replace(HEALTHY, alive=False),
            IntegrityViolation.ALIVE_DISAGREES_WITH_HEALTH,
        ),
    ],
)
def test_an_impossible_hud_reading_is_flagged(
    state: SelfStateValue, expected: IntegrityViolation
) -> None:
    assert expected in self_state_violations(state)


def test_a_dead_player_with_no_health_is_coherent() -> None:
    assert self_state_violations(replace(HEALTHY, health=0.0, alive=False)) == ()


def test_non_finite_self_state_is_flagged_once_without_repeating_itself() -> None:
    violations = self_state_violations(replace(HEALTHY, saturation=float("inf")))

    assert IntegrityViolation.SELF_NOT_FINITE in violations
    assert IntegrityViolation.SATURATION_NEGATIVE not in violations


def test_a_plausible_inventory_has_no_violations() -> None:
    assert inventory_violations(LOADED) == ()


@pytest.mark.parametrize(
    ("inventory", "expected"),
    [
        (replace(LOADED, revision=0), IntegrityViolation.INVENTORY_REVISION_UNSET),
        (replace(LOADED, revision=True), IntegrityViolation.INVENTORY_REVISION_UNSET),
        (
            replace(LOADED, stacks=(InventoryStackValue(slot=0, item_id="", count=1),)),
            IntegrityViolation.STACK_ITEM_MISSING,
        ),
        (
            replace(
                LOADED, stacks=(InventoryStackValue(slot=0, item_id="minecraft:stone", count=0),)
            ),
            IntegrityViolation.STACK_COUNT_OUT_OF_RANGE,
        ),
        (
            replace(
                LOADED, stacks=(InventoryStackValue(slot=0, item_id="minecraft:stone", count=65),)
            ),
            IntegrityViolation.STACK_COUNT_OUT_OF_RANGE,
        ),
        (
            replace(
                LOADED,
                stacks=(
                    InventoryStackValue(slot=3, item_id="minecraft:stone", count=1),
                    InventoryStackValue(slot=3, item_id="minecraft:dirt", count=1),
                ),
            ),
            IntegrityViolation.STACK_SLOT_DUPLICATED,
        ),
    ],
)
def test_an_impossible_inventory_is_flagged(
    inventory: InventoryValue, expected: IntegrityViolation
) -> None:
    assert expected in inventory_violations(inventory)


def test_an_incoherent_self_state_is_not_admitted() -> None:
    admission = admit(entities=(entity(),), self_state=replace(HEALTHY, food=99))

    assert not admission.admitted
    assert admission.reasons == (SnapshotReason.SELF_STATE_INCOHERENT,)
    assert admission.integrity == (IntegrityViolation.FOOD_OUT_OF_RANGE,)
    assert admission.visible_world.accepted == ()


def test_an_invalid_inventory_is_not_admitted() -> None:
    admission = admit(entities=(entity(),), inventory=replace(LOADED, revision=0))

    assert not admission.admitted
    assert admission.reasons == (SnapshotReason.INVENTORY_INVALID,)
    assert admission.integrity == (IntegrityViolation.INVENTORY_REVISION_UNSET,)


def test_both_halves_of_the_finding_are_reported_together() -> None:
    admission = admit(
        self_state=replace(HEALTHY, health=99.0),
        inventory=replace(LOADED, revision=0),
    )

    assert set(admission.reasons) == {
        SnapshotReason.SELF_STATE_INCOHERENT,
        SnapshotReason.INVENTORY_INVALID,
    }
    assert set(admission.integrity) == {
        IntegrityViolation.HEALTH_OUT_OF_RANGE,
        IntegrityViolation.INVENTORY_REVISION_UNSET,
    }


def test_a_coherent_wire_snapshot_carries_its_self_state_and_inventory() -> None:
    admission = admit_first_snapshot(
        snapshot(entities=(entity(),)), generation=Generation(7), recorded=RECORDED
    )

    assert admission.admitted
    assert admission.integrity == ()


def test_an_incoherent_wire_snapshot_is_not_admitted() -> None:
    admission = admit_first_snapshot(
        snapshot(self_state=replace(HEALTHY, alive=False)),
        generation=Generation(7),
        recorded=RECORDED,
    )

    assert not admission.admitted
    assert SnapshotReason.SELF_STATE_INCOHERENT in admission.reasons
