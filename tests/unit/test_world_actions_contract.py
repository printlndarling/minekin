"""§3's named refusals and §4's confirm-vs-not-confirm pairs, as one table.

Every row here is a decision the Core makes either before the wire (a refusal
that names itself) or from two observations (a verdict that is only as strong as
the readings compared). The pairs are the point: each `CONFIRMED` has a sibling
where the same-looking change arrives without the synced evidence behind it, and
the verdict must stay `UNKNOWN` there. A verification that could not tell those
apart would be a Kin that believes a wish.
"""

from __future__ import annotations

import math

import pytest

from minekin_core.domain.perception import (
    AimFace,
    AimKind,
    AimTargetValue,
    BlockTargetValue,
    EntityCandidate,
    GuiScreenValue,
    InventoryStackValue,
    InventoryValue,
    MiningProgressValue,
    SelfStateValue,
    WorldObservationValue,
)
from minekin_core.domain.world_actions import (
    ActionRefusal,
    ActionResultClass,
    angle_error_degrees,
    angle_to_degrees,
    gui_click_refusal,
    hotbar_slot_refusal,
    item_total,
    mine_target_refusal,
    seen_drops,
    verify_block_broken,
    verify_craft,
    verify_hotbar_change,
    verify_item_collected,
)

HEALTHY = SelfStateValue(health=20.0, max_health=20.0, food=20, saturation=5.0, alive=True)


def stacks(*pairs: tuple[int, str, int]) -> InventoryValue:
    return InventoryValue(
        revision=100,
        stacks=tuple(
            InventoryStackValue(slot=slot, item_id=item_id, count=count)
            for slot, item_id, count in pairs
        ),
    )


def block(x: int = 4, y: int = -2, z: int = 9, face: AimFace = AimFace.UP) -> BlockTargetValue:
    return BlockTargetValue(x=x, y=y, z=z, face=face)


def aimed_at(target: BlockTargetValue, state_id: str = "minecraft:oak_log") -> AimTargetValue:
    return AimTargetValue(
        game_tick=100, kind=AimKind.BLOCK, block=target, targeted_block_id=state_id, distance=2.0
    )


def reading(
    *,
    tick: int = 100,
    aim: AimTargetValue | None = None,
    inventory: InventoryValue | None = None,
    entities: tuple[EntityCandidate, ...] = (),
    mining: MiningProgressValue | None = None,
    gui: GuiScreenValue | None = None,
    state: SelfStateValue | None = None,
) -> WorldObservationValue:
    return WorldObservationValue(
        generation=1,
        game_tick=tick,
        self_state=state if state is not None else HEALTHY,
        aim=aim,
        inventory=inventory if inventory is not None else stacks(),
        visible_entities=entities,
        mining=mining,
        gui=gui,
    )


def dropped(item_id: str = "minecraft:oak_log", count: int = 1) -> EntityCandidate:
    return EntityCandidate(
        observation_id=f"obs-{item_id}-{count}",
        entity_type="minecraft:item",
        relative_x=1.0,
        relative_y=-1.0,
        relative_z=1.0,
        line_of_sight=True,
        item_id=item_id,
        item_count=count,
    )


# ---------------------------------------------------------------------------
# §3: the three named refusals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slot", [0, 3, 8])
def test_a_hotbar_slot_inside_the_nine_passes(slot: int) -> None:
    assert hotbar_slot_refusal(slot).accepted


@pytest.mark.parametrize("slot", [-1, 9, 12, True, False, "2", None])
def test_everything_that_is_not_one_of_the_nine_is_named(slot: object) -> None:
    decision = hotbar_slot_refusal(slot)
    assert decision.refusal is ActionRefusal.HOTBAR_SLOT_OUT_OF_RANGE
    assert decision.as_document() == {
        "accepted": False,
        "refusal": "HOTBAR_SLOT_OUT_OF_RANGE",
    }


def test_a_mine_on_the_aimed_block_passes_and_anything_else_is_named() -> None:
    target = block()
    pre = reading(aim=aimed_at(target))
    assert mine_target_refusal(pre, target, mining=True).accepted

    elsewhere = reading(aim=aimed_at(block(x=99)))
    assert (
        mine_target_refusal(elsewhere, target, mining=True).refusal
        is ActionRefusal.MINE_TARGET_NOT_AIMED
    )
    missed = reading(aim=AimTargetValue(game_tick=100, kind=AimKind.MISS))
    assert (
        mine_target_refusal(missed, target, mining=True).refusal
        is ActionRefusal.MINE_TARGET_NOT_AIMED
    )
    assert (
        mine_target_refusal(None, target, mining=True).refusal
        is ActionRefusal.MINE_TARGET_NOT_AIMED
    )


def test_letting_go_of_the_mine_key_is_never_refused() -> None:
    """The release path is the single one the lease contract guarantees; refusing
    a stop would be a Kin still digging at a block nobody aimed at."""

    target = block()
    no_aim = reading(aim=None)
    assert mine_target_refusal(no_aim, target, mining=False).accepted
    assert mine_target_refusal(None, target, mining=False).accepted


def test_an_unread_face_agrees_with_the_requested_face_but_coordinates_still_rule() -> None:
    target = block()
    not_read = reading(aim=aimed_at(block(face=AimFace.NOT_READ)))
    assert mine_target_refusal(not_read, target, mining=True).accepted
    moved = reading(aim=aimed_at(block(face=AimFace.NOT_READ, z=40)))
    assert (
        mine_target_refusal(moved, target, mining=True).refusal
        is ActionRefusal.MINE_TARGET_NOT_AIMED
    )


@pytest.mark.parametrize("sync_id", [7, 0])
def test_a_gui_click_matching_the_observed_handler_passes(sync_id: int) -> None:
    open_screen = reading(gui=GuiScreenValue(screen_id="crafting", sync_id=sync_id))
    assert gui_click_refusal(open_screen, sync_id).accepted


@pytest.mark.parametrize(
    ("observation", "sync_id"),
    [
        (None, 3),
        (reading(), 3),  # no screen open at all
        (reading(gui=GuiScreenValue(screen_id="sign", sync_id=None)), 3),  # no handler
        (reading(gui=GuiScreenValue(screen_id="crafting", sync_id=4)), 3),  # stale id
        (reading(gui=GuiScreenValue(screen_id="crafting", sync_id=4)), True),  # not an int
    ],
)
def test_no_click_rides_a_handler_the_client_is_not_reporting(
    observation: WorldObservationValue | None, sync_id: object
) -> None:
    decision = gui_click_refusal(observation, sync_id)
    assert decision.refusal is ActionRefusal.GUI_SYNC_ID_MISMATCH


# ---------------------------------------------------------------------------
# §4 row one: the block broke — or it did not
# ---------------------------------------------------------------------------

TARGET = block()


def test_break_confirms_when_the_crosshair_no_longer_names_the_block() -> None:
    pre = reading(aim=aimed_at(TARGET))
    post = reading(tick=110, aim=AimTargetValue(game_tick=110, kind=AimKind.MISS))
    assert verify_block_broken(pre=pre, post=post, target=TARGET) is ActionResultClass.CONFIRMED


def test_break_confirms_when_the_same_spot_renders_a_different_block() -> None:
    pre = reading(aim=aimed_at(TARGET, "minecraft:oak_log"))
    post = reading(tick=110, aim=aimed_at(TARGET, "minecraft:air"))
    assert verify_block_broken(pre=pre, post=post, target=TARGET) is ActionResultClass.CONFIRMED


def test_break_confirms_when_the_expected_drop_appears() -> None:
    pre = reading(aim=aimed_at(TARGET))
    post = reading(tick=110, aim=aimed_at(TARGET), entities=(dropped(),))
    assert (
        verify_block_broken(
            pre=pre,
            post=post,
            target=TARGET,
            expected_drop_item="minecraft:oak_log",
        )
        is ActionResultClass.CONFIRMED
    )


def test_no_new_reading_confirms_nothing() -> None:
    pre = reading(aim=aimed_at(TARGET))
    same = reading(tick=100, aim=aimed_at(TARGET))
    assert verify_block_broken(pre=pre, post=same, target=TARGET) is ActionResultClass.UNKNOWN


def test_an_aim_that_never_moved_and_showed_no_drop_is_still_unknown() -> None:
    pre = reading(aim=aimed_at(TARGET))
    post = reading(tick=110, aim=aimed_at(TARGET))
    assert verify_block_broken(pre=pre, post=post, target=TARGET) is ActionResultClass.UNKNOWN


def test_a_break_bar_stuck_between_two_ticks_fails() -> None:
    stalled = MiningProgressValue(game_tick=100, target=TARGET, progress=0.4)
    same_bar = MiningProgressValue(game_tick=110, target=TARGET, progress=0.4)
    pre = reading(aim=aimed_at(TARGET), mining=stalled)
    post = reading(tick=110, aim=aimed_at(TARGET), mining=same_bar)
    assert verify_block_broken(pre=pre, post=post, target=TARGET) is ActionResultClass.FAILED


def test_a_break_bar_moving_is_not_a_failure_to_report() -> None:
    pre_mining = MiningProgressValue(game_tick=100, target=TARGET, progress=0.4)
    post_mining = MiningProgressValue(game_tick=110, target=TARGET, progress=0.7)
    pre = reading(aim=aimed_at(TARGET), mining=pre_mining)
    post = reading(tick=110, aim=aimed_at(TARGET), mining=post_mining)
    assert verify_block_broken(pre=pre, post=post, target=TARGET) is ActionResultClass.UNKNOWN


# ---------------------------------------------------------------------------
# §4 row two: the drop was collected — or somebody else took it
# ---------------------------------------------------------------------------


def test_collect_confirms_on_a_synced_rise_and_a_shrinking_drop() -> None:
    pre = reading(inventory=stacks((0, "minecraft:oak_log", 3)), entities=(dropped(count=2),))
    post = reading(
        tick=110,
        inventory=InventoryValue(
            revision=110,
            stacks=(InventoryStackValue(slot=0, item_id="minecraft:oak_log", count=5),),
        ),
        entities=(dropped(count=1),),
    )
    assert (
        verify_item_collected(pre=pre, post=post, item_id="minecraft:oak_log")
        is ActionResultClass.CONFIRMED
    )


def test_a_rise_without_a_synced_revision_is_worth_nothing() -> None:
    pre = reading(inventory=stacks((0, "minecraft:oak_log", 3)), entities=(dropped(count=2),))
    post = reading(
        tick=110,
        inventory=stacks((0, "minecraft:oak_log", 5)),
        entities=(dropped(count=1),),
    )
    assert (
        verify_item_collected(pre=pre, post=post, item_id="minecraft:oak_log")
        is ActionResultClass.UNKNOWN
    )


def test_a_drop_vanishing_with_no_rise_failed_somebody_else() -> None:
    pre = reading(inventory=stacks((0, "minecraft:oak_log", 3)), entities=(dropped(),))
    post = reading(tick=110, inventory=InventoryValue(revision=110, stacks=()), entities=())
    assert (
        verify_item_collected(pre=pre, post=post, item_id="minecraft:oak_log")
        is ActionResultClass.FAILED
    )


def test_a_rise_with_the_drop_still_full_is_unknown_not_confirmed() -> None:
    pre = reading(inventory=stacks((0, "minecraft:oak_log", 3)), entities=(dropped(count=3),))
    post = reading(
        tick=110,
        inventory=InventoryValue(
            revision=110,
            stacks=(InventoryStackValue(slot=0, item_id="minecraft:oak_log", count=5),),
        ),
        entities=(dropped(count=3),),
    )
    assert (
        verify_item_collected(pre=pre, post=post, item_id="minecraft:oak_log")
        is ActionResultClass.UNKNOWN
    )


# ---------------------------------------------------------------------------
# §4 row three: the craft happened in the synced inventory — or it did not
# ---------------------------------------------------------------------------

WORKBENCH = stacks((0, "minecraft:oak_planks", 6), (1, "minecraft:stick", 2))


def test_craft_confirms_when_materials_down_and_product_up_share_a_revision() -> None:
    pre = reading(inventory=WORKBENCH)
    post = reading(
        tick=110,
        inventory=InventoryValue(
            revision=110,
            stacks=(
                InventoryStackValue(slot=0, item_id="minecraft:oak_planks", count=2),
                InventoryStackValue(slot=2, item_id="minecraft:wooden_pickaxe", count=1),
            ),
        ),
    )
    assert (
        verify_craft(
            pre=pre,
            post=post,
            material_ids=("minecraft:oak_planks", "minecraft:stick"),
            product_id="minecraft:wooden_pickaxe",
        )
        is ActionResultClass.CONFIRMED
    )


def test_a_material_still_above_its_recipe_cost_still_counts_as_consumed() -> None:
    # A Kin with six planks spends three of them, leaving three. Comparing the
    # later count against the recipe's requirement instead of against what the
    # pre-state held would call that `3 < 3` — no decrease — and the craft would
    # never confirm for anyone who had ever stacked wood.
    pre = reading(inventory=WORKBENCH)
    post = reading(
        tick=110,
        inventory=InventoryValue(
            revision=110,
            stacks=(
                InventoryStackValue(slot=0, item_id="minecraft:oak_planks", count=3),
                InventoryStackValue(slot=2, item_id="minecraft:oak_stick", count=1),
            ),
        ),
    )
    assert (
        verify_craft(
            pre=pre,
            post=post,
            material_ids=("minecraft:oak_planks",),
            product_id="minecraft:oak_stick",
        )
        is ActionResultClass.CONFIRMED
    )


def test_a_packet_sent_and_a_window_opened_is_not_a_craft() -> None:
    pre = reading(inventory=WORKBENCH)
    unchanged = reading(tick=110, inventory=InventoryValue(revision=110, stacks=WORKBENCH.stacks))
    assert (
        verify_craft(
            pre=pre,
            post=unchanged,
            material_ids=("minecraft:oak_planks", "minecraft:stick"),
            product_id="minecraft:wooden_pickaxe",
        )
        is ActionResultClass.UNKNOWN
    )


def test_a_product_appearing_without_the_materials_losing_is_not_confirmed() -> None:
    pre = reading(inventory=WORKBENCH)
    post = reading(
        tick=110,
        inventory=InventoryValue(
            revision=110,
            stacks=(
                InventoryStackValue(slot=0, item_id="minecraft:oak_planks", count=6),
                InventoryStackValue(slot=1, item_id="minecraft:stick", count=2),
                InventoryStackValue(slot=2, item_id="minecraft:wooden_pickaxe", count=1),
            ),
        ),
    )
    assert (
        verify_craft(
            pre=pre,
            post=post,
            material_ids=("minecraft:oak_planks", "minecraft:stick"),
            product_id="minecraft:wooden_pickaxe",
        )
        is ActionResultClass.UNKNOWN
    )


# ---------------------------------------------------------------------------
# §4 row four: the hand changed — or the reading still points at the old slot
# ---------------------------------------------------------------------------


def in_hand(slot: int, item: str | None) -> SelfStateValue:
    return SelfStateValue(
        health=20.0,
        max_health=20.0,
        food=20,
        saturation=5.0,
        alive=True,
        selected_slot=slot,
        main_hand_item_id=item,
    )


def test_hotbar_change_confirms_when_the_next_reading_names_the_slot() -> None:
    pre = reading(state=in_hand(0, "minecraft:stone"))
    post = reading(tick=110, state=in_hand(4, "minecraft:oak_log"))
    assert verify_hotbar_change(pre=pre, post=post, slot=4) is ActionResultClass.CONFIRMED
    assert (
        verify_hotbar_change(pre=pre, post=post, slot=4, expected_item_id="minecraft:oak_log")
        is ActionResultClass.CONFIRMED
    )


def test_a_reading_that_still_points_at_the_old_slot_is_exactly_unknown() -> None:
    pre = reading(state=in_hand(0, "minecraft:stone"))
    post = reading(tick=110, state=in_hand(0, "minecraft:stone"))
    assert verify_hotbar_change(pre=pre, post=post, slot=4) is ActionResultClass.UNKNOWN


def test_the_right_slot_with_the_wrong_item_in_hand_is_not_confirmed() -> None:
    pre = reading(state=in_hand(0, "minecraft:stone"))
    post = reading(tick=110, state=in_hand(4, "minecraft:dirt"))
    assert (
        verify_hotbar_change(pre=pre, post=post, slot=4, expected_item_id="minecraft:oak_log")
        is ActionResultClass.UNKNOWN
    )


def test_an_unread_hotbar_cannot_confirm_a_hand_change() -> None:
    pre = reading(state=in_hand(0, "minecraft:stone"))
    post = reading(tick=110)  # selected_slot None
    assert verify_hotbar_change(pre=pre, post=post, slot=4) is ActionResultClass.UNKNOWN


# ---------------------------------------------------------------------------
# The geometry a turn is computed from — and one pure inventory helper
# ---------------------------------------------------------------------------


def test_angle_to_degrees_inverts_the_client_look_formula() -> None:
    cases = [
        # (offset, expected yaw, expected pitch): MC yaw 0 is +Z (south), -90 is +X.
        ((0.0, 0.0, 1.0), 0.0, 0.0),
        ((1.0, 0.0, 0.0), -90.0, 0.0),
        ((0.0, 0.0, -1.0), 180.0, 0.0),
        ((0.0, 1.0, 0.0), 0.0, -90.0),
        ((0.0, -1.0, 0.0), 0.0, 90.0),
    ]
    for (dx, dy, dz), yaw, pitch in cases:
        got_yaw, got_pitch = angle_to_degrees(dx=dx, dy=dy, dz=dz)
        assert math.isclose(got_yaw, yaw, abs_tol=1e-9), (dx, dy, dz)
        assert math.isclose(got_pitch, pitch, abs_tol=1e-9), (dx, dy, dz)


def test_angle_to_degrees_refuses_a_direction_that_does_not_exist() -> None:
    with pytest.raises(ValueError):
        angle_to_degrees(dx=0.0, dy=0.0, dz=0.0)
    with pytest.raises(ValueError):
        angle_to_degrees(dx=math.nan, dy=0.0, dz=1.0)


def test_angle_error_wraps_yaw_at_the_180_boundary() -> None:
    assert math.isclose(
        angle_error_degrees(from_yaw=179.0, to_yaw=-179.0, from_pitch=0.0, to_pitch=0.0), 2.0
    )
    assert math.isclose(
        angle_error_degrees(from_yaw=0.0, to_yaw=0.0, from_pitch=-30.0, to_pitch=10.0), 40.0
    )


def test_item_total_sums_every_stack_of_one_kind() -> None:
    inventory = stacks(
        (0, "minecraft:oak_log", 3), (5, "minecraft:oak_log", 64), (9, "minecraft:stone", 12)
    )
    assert item_total(inventory, "minecraft:oak_log") == 67
    assert item_total(inventory, "minecraft:dirt") == 0


def test_seen_drops_reports_only_the_item_seen_nearest_first() -> None:
    far = EntityCandidate(
        observation_id="obs-far",
        entity_type="minecraft:item",
        relative_x=9.0,
        relative_y=0.0,
        relative_z=0.0,
        line_of_sight=True,
        item_id="minecraft:oak_log",
        item_count=1,
    )
    near = EntityCandidate(
        observation_id="obs-near",
        entity_type="minecraft:item",
        relative_x=1.0,
        relative_y=0.0,
        relative_z=0.0,
        line_of_sight=True,
        item_id="minecraft:oak_log",
        item_count=1,
    )
    cow = EntityCandidate(
        observation_id="obs-cow",
        entity_type="minecraft:cow",
        relative_x=0.5,
        relative_y=0.0,
        relative_z=0.0,
        line_of_sight=True,
    )
    ordered = seen_drops((far, cow, near), "minecraft:oak_log")
    assert tuple(entity.observation_id for entity in ordered) == ("obs-near", "obs-far")
