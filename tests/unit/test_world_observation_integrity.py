"""Integrity of the recurring reading, and the store that keeps only what is coherent.

`world_observation_violations` is the same reject-don't-clamp family the first
snapshot's rules belong to, extended to what only the S2 surface can get wrong;
and the store is the one place the newest coherent reading lives, so a skill's
pre-state and its post-state can never come from two different worlds. The
generation gate and the never-backwards tick rule are what make the pair a
before/after rather than two anecdotes.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import replace

import pytest

from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.domain.perception import (
    AimFace,
    AimKind,
    AimTargetValue,
    BlockTargetValue,
    EntityCandidate,
    GuiScreenValue,
    IntegrityViolation,
    InventoryStackValue,
    InventoryValue,
    MiningProgressValue,
    SelfStateValue,
    WorldObservationValue,
    world_observation_violations,
)

HEALTHY = SelfStateValue(health=20.0, max_health=20.0, food=20, saturation=5.0, alive=True)
LOADED = InventoryValue(
    revision=100,
    stacks=(InventoryStackValue(slot=0, item_id="minecraft:oak_log", count=3),),
)


def block(x: int = 4, y: int = -2, z: int = 9, face: AimFace = AimFace.UP) -> BlockTargetValue:
    return BlockTargetValue(x=x, y=y, z=z, face=face)


def aim_block(state_id: str = "minecraft:oak_log") -> AimTargetValue:
    return AimTargetValue(
        game_tick=100, kind=AimKind.BLOCK, block=block(), targeted_block_id=state_id, distance=2.0
    )


def observation(**changes: object) -> WorldObservationValue:
    base = WorldObservationValue(
        generation=1,
        game_tick=100,
        self_state=HEALTHY,
        aim=aim_block(),
        inventory=LOADED,
        visible_entities=(),
        mining=None,
        gui=None,
    )
    return replace(base, **changes)


def drop(
    *,
    entity_type: str = "minecraft:item",
    item_id: str | None = "minecraft:oak_log",
    item_count: int | None = 1,
) -> EntityCandidate:
    return EntityCandidate(
        observation_id="obs-1",
        entity_type=entity_type,
        relative_x=1.0,
        relative_y=-1.0,
        relative_z=1.0,
        line_of_sight=True,
        item_id=item_id,
        item_count=item_count,
    )


# ---------------------------------------------------------------------------
# Each integrity violation the S2 surface can carry
# ---------------------------------------------------------------------------


def test_a_coherent_reading_carries_no_violations() -> None:
    assert world_observation_violations(observation()) == ()


@pytest.mark.parametrize(
    ("state", "token"),
    [
        (replace(HEALTHY, yaw_degrees=181.0), IntegrityViolation.YAW_OUT_OF_RANGE),
        (replace(HEALTHY, yaw_degrees=-180.001), IntegrityViolation.YAW_OUT_OF_RANGE),
        (replace(HEALTHY, pitch_degrees=90.5), IntegrityViolation.PITCH_OUT_OF_RANGE),
        (replace(HEALTHY, pitch_degrees=-90.001), IntegrityViolation.PITCH_OUT_OF_RANGE),
        (
            replace(HEALTHY, yaw_degrees=math.nan),
            IntegrityViolation.YAW_OUT_OF_RANGE,
        ),
        (replace(HEALTHY, selected_slot=9), IntegrityViolation.SELECTED_SLOT_OUT_OF_RANGE),
        (replace(HEALTHY, selected_slot=True), IntegrityViolation.SELECTED_SLOT_OUT_OF_RANGE),
        (replace(HEALTHY, selected_slot=-1), IntegrityViolation.SELECTED_SLOT_OUT_OF_RANGE),
        (
            replace(HEALTHY, main_hand_item_id="minecraft:oak_log"),
            IntegrityViolation.MAIN_HAND_WITHOUT_SLOT,
        ),
        (
            replace(HEALTHY, x=math.inf),
            IntegrityViolation.SELF_NOT_FINITE,
        ),
    ],
)
def test_self_state_violations_on_the_s2_fields(
    state: SelfStateValue, token: IntegrityViolation
) -> None:
    value = world_observation_violations(observation(self_state=state))
    assert token in value


def test_the_hotbar_edge_of_range_is_legal_and_the_first_step_past_is_not() -> None:
    assert (
        world_observation_violations(observation(self_state=replace(HEALTHY, selected_slot=8)))
        == ()
    )
    assert IntegrityViolation.SELECTED_SLOT_OUT_OF_RANGE in world_observation_violations(
        observation(self_state=replace(HEALTHY, selected_slot=9))
    )


@pytest.mark.parametrize(
    ("aim", "token"),
    [
        (
            AimTargetValue(game_tick=100, kind=AimKind.UNREAD),
            IntegrityViolation.AIM_KIND_UNREAD,
        ),
        (
            AimTargetValue(game_tick=100, kind=AimKind.BLOCK, block=None, targeted_block_id="x"),
            IntegrityViolation.AIM_BLOCK_WITHOUT_TARGET,
        ),
        (
            AimTargetValue(game_tick=100, kind=AimKind.BLOCK, block=block(), targeted_block_id=" "),
            IntegrityViolation.AIM_TARGETED_BLOCK_ID_MISSING,
        ),
        (
            AimTargetValue(game_tick=100, kind=AimKind.ENTITY, entity_observation_id=""),
            IntegrityViolation.AIM_ENTITY_WITHOUT_ID,
        ),
        (
            AimTargetValue(game_tick=100, kind=AimKind.MISS, distance=math.nan),
            IntegrityViolation.AIM_DISTANCE_NOT_FINITE,
        ),
    ],
)
def test_aim_violations(aim: AimTargetValue, token: IntegrityViolation) -> None:
    assert token in world_observation_violations(observation(aim=aim))


@pytest.mark.parametrize("progress", [-0.01, 1.01, math.nan, math.inf])
def test_mining_progress_outside_the_animation(progress: float) -> None:
    mining = MiningProgressValue(game_tick=100, target=block(), progress=progress)
    assert IntegrityViolation.MINING_PROGRESS_OUT_OF_RANGE in world_observation_violations(
        observation(mining=mining)
    )


def test_mining_progress_at_both_edges_of_the_animation_is_a_real_read() -> None:
    for progress in (0.0, 1.0):
        mining = MiningProgressValue(game_tick=100, target=block(), progress=progress)
        assert world_observation_violations(observation(mining=mining)) == ()


def test_item_fields_on_an_entity_the_client_does_not_render_as_an_item() -> None:
    value = world_observation_violations(
        observation(visible_entities=(drop(entity_type="minecraft:cow"),))
    )
    assert IntegrityViolation.ENTITY_ITEM_ON_NON_ITEM in value


@pytest.mark.parametrize(("item_id", "item_count"), [("minecraft:oak_log", None), (None, 3)])
def test_half_a_dropped_item_pair_says_nothing_about_the_ground(
    item_id: str | None, item_count: int | None
) -> None:
    entity = drop(item_id=item_id, item_count=item_count)
    value = world_observation_violations(observation(visible_entities=(entity,)))
    assert IntegrityViolation.ENTITY_ITEM_INCOHERENT in value


def test_a_full_dropped_item_pair_is_coherent() -> None:
    assert world_observation_violations(observation(visible_entities=(drop(),))) == ()


# ---------------------------------------------------------------------------
# The store: the latest coherent reading, and nothing that contradicts it
# ---------------------------------------------------------------------------


def reading(tick: int, *, generation: int = 1) -> WorldObservationValue:
    return observation(generation=generation, game_tick=tick)


def admit(store: WorldObservationStore, value: WorldObservationValue) -> bool:
    return store.admit(value, world_observation_violations(value))


def test_the_store_holds_only_the_newest_admitted_reading() -> None:
    store = WorldObservationStore(expected_generation=1)
    assert store.latest is None

    assert admit(store, reading(100)) is True
    assert admit(store, reading(101)) is True

    assert store.latest is not None
    assert store.latest.game_tick == 101
    assert store.accepted_count == 2


def test_an_incoherent_reading_never_becomes_a_post_state() -> None:
    store = WorldObservationStore(expected_generation=1)
    assert admit(store, reading(100)) is True
    bad = observation(game_tick=101, self_state=replace(HEALTHY, yaw_degrees=270.0))

    assert admit(store, bad) is False
    assert store.latest is not None
    assert store.latest.game_tick == 100
    assert store.refused[-1].violations == (IntegrityViolation.YAW_OUT_OF_RANGE,)


def test_a_reading_from_a_closed_generation_is_counted_as_stale() -> None:
    store = WorldObservationStore(expected_generation=1)

    assert admit(store, reading(100, generation=2)) is False
    assert store.refused[-1].stale_generation is True
    assert store.latest is None

    # Re-pointed at the generation that is actually running, the same reading
    # lands: the gate is the generation, not the message.
    store.expected_generation = 2
    assert admit(store, reading(101, generation=2)) is True


def test_ticks_never_go_backwards_in_the_store() -> None:
    """A replayed frame would turn a post-state back into a pre-state, and every
    §4 verification reads the pair as before/after; the Bridge's own clock is the
    only ordering, so the store refuses to be the side that forgets it."""

    store = WorldObservationStore(expected_generation=1)
    assert admit(store, reading(100)) is True
    assert admit(store, reading(99)) is False
    assert admit(store, reading(100)) is False
    assert store.latest is not None
    assert store.latest.game_tick == 100


def test_a_frame_that_is_not_newer_is_counted_and_says_which_tick_it_brought() -> None:
    """The count and the tick together are the point. A skill that timed out with
    `newest_checked_tick == pre_tick` can mean the client stopped producing readings
    or that it kept producing readings whose clock never moved, and the fix for those
    two is on opposite sides of the channel. Only the frame the store refused can say
    which, so the refusal is kept as a number rather than dropped on the floor."""

    store = WorldObservationStore(expected_generation=1)
    assert admit(store, reading(100)) is True
    assert store.stale_tick_count == 0
    assert store.newest_stale_tick is None

    assert admit(store, reading(100)) is False
    assert admit(store, reading(97)) is False

    assert store.stale_tick_count == 2
    assert store.newest_stale_tick == 100
    assert store.accepted_count == 1


def test_a_replayed_frame_is_not_counted_as_a_refused_one() -> None:
    """Two different refusals, two different counters: an incoherent reading says the
    Bridge reported something impossible, a frame on an old tick says only that the
    world has not moved since. Folding the second into the first would let a quiet
    world look like a lying bridge."""

    store = WorldObservationStore(expected_generation=1)
    assert admit(store, reading(100)) is True
    bad = observation(game_tick=101, self_state=replace(HEALTHY, yaw_degrees=270.0))

    assert admit(store, bad) is False
    assert admit(store, reading(100)) is False

    assert store.refusal_count == 1
    assert store.stale_tick_count == 1


def test_wait_for_newer_delivers_the_reading_after_the_action() -> None:
    async def scenario() -> None:
        store = WorldObservationStore(expected_generation=1)
        assert admit(store, reading(100))
        pre = store.latest
        assert pre is not None

        async def later() -> None:
            await asyncio.sleep(0.01)
            assert admit(store, reading(101))

        task = asyncio.create_task(later())
        got = await store.wait_for_newer(pre, timeout_s=1.0)
        await task
        assert got is not None
        assert got.game_tick == 101

    asyncio.run(scenario())


def test_wait_until_answers_a_predicate_the_current_reading_already_holds() -> None:
    """The screen case: a window that was already open when the wait began is
    open now, and a waiter that demanded a fresher tick would be waiting for
    the client to close it and reopen it."""

    async def scenario() -> None:
        store = WorldObservationStore(expected_generation=1)

        assert admit(
            store, replace(reading(100), gui=GuiScreenValue(screen_id="crafting", sync_id=7))
        )

        got = await store.wait_for_screen(has_sync_id=True, timeout_s=0.05)
        assert got is not None
        assert got.gui is not None
        assert got.gui.sync_id == 7

        missed = await store.wait_for_screen(has_sync_id=False, timeout_s=0.05)
        assert missed is None

        none = await store.wait_until(lambda value: False, timeout_s=0.05)
        assert none is None

    asyncio.run(scenario())
