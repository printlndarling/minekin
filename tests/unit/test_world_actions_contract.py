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
    best_wieldable_weapon,
    consume_candidate,
    consume_item_refusal,
    gui_click_refusal,
    hotbar_slot_for_item,
    hotbar_slot_refusal,
    item_total,
    mine_target_refusal,
    reachable_food_items,
    reachable_weapons,
    seen_drops,
    use_target_refusal,
    use_target_signature,
    verify_block_broken,
    verify_consume_effect,
    verify_craft,
    verify_hotbar_change,
    verify_item_collected,
    verify_use_effect,
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


# ---------------------------------------------------------------------------
# §3: the use key's named refusal — it fires on what the crosshair reports
# ---------------------------------------------------------------------------


def aimed_entity(observation_id: str = "obs-villager") -> AimTargetValue:
    return AimTargetValue(
        game_tick=100,
        kind=AimKind.ENTITY,
        entity_observation_id=observation_id,
        entity_type="minecraft:villager",
        distance=2.0,
    )


def test_a_use_on_a_seen_block_or_entity_passes() -> None:
    assert use_target_refusal(reading(aim=aimed_at(block()))).accepted
    assert use_target_refusal(reading(aim=aimed_entity())).accepted


@pytest.mark.parametrize(
    "observation",
    [
        None,
        reading(),  # aim never populated
        reading(aim=AimTargetValue(game_tick=100, kind=AimKind.MISS)),
        reading(aim=AimTargetValue(game_tick=100, kind=AimKind.UNREAD)),
    ],
)
def test_a_use_at_empty_air_or_an_unread_aim_is_named(
    observation: WorldObservationValue | None,
) -> None:
    decision = use_target_refusal(observation)
    assert decision.refusal is ActionRefusal.USE_TARGET_NOT_AIMED
    assert decision.as_document() == {
        "accepted": False,
        "refusal": "USE_TARGET_NOT_AIMED",
    }


# ---------------------------------------------------------------------------
# §3: the general placement precondition — no block lands in the player's own cell
# ---------------------------------------------------------------------------


def standing(x: float = 0.5, y: float = 64.0, z: float = 0.5) -> SelfStateValue:
    """A player whose feet fill (0, 64, 0) and whose head fills (0, 65, 0)."""

    return SelfStateValue(
        health=20.0, max_health=20.0, food=20, saturation=5.0, alive=True, x=x, y=y, z=z
    )


def test_placing_against_the_floor_under_your_own_feet_is_named() -> None:
    # The real 3x3 gap: a Kin aims straight down, the crosshair is on the block
    # below its feet, and the UP face opens onto the very cell it stands in.
    obs = reading(state=standing(), aim=aimed_at(block(0, 63, 0, AimFace.UP)))
    decision = use_target_refusal(obs)
    assert decision.refusal is ActionRefusal.PLACEMENT_TARGET_IN_SELF
    assert decision.as_document() == {
        "accepted": False,
        "refusal": "PLACEMENT_TARGET_IN_SELF",
    }


def test_placing_against_a_free_neighbour_face_is_allowed() -> None:
    # Two cells over: the same UP face now opens onto air the player is not in.
    assert use_target_refusal(
        reading(state=standing(), aim=aimed_at(block(2, 63, 0, AimFace.UP)))
    ).accepted


def test_placement_collision_spreads_to_the_head_cell_and_side_faces() -> None:
    # Aim at the feet cell itself with UP -> the head cell; a WEST face of the
    # block east of the player lands back in the feet cell. Both are refused.
    assert not use_target_refusal(
        reading(state=standing(), aim=aimed_at(block(0, 64, 0, AimFace.UP)))
    ).accepted
    assert not use_target_refusal(
        reading(state=standing(), aim=aimed_at(block(1, 64, 0, AimFace.WEST)))
    ).accepted


def test_a_player_leaning_over_a_boundary_refuses_the_neighbour_cell_it_shares() -> None:
    # The server blocks a placement into ANY cell the 0.6-wide player box touches, not
    # only the cell the feet floor into. A Kin standing at x=0.9 has its box spanning
    # [0.6, 1.2], so it leans into cell 1; a WEST face of the block at x=2 opens onto
    # (1, 64, 0) — a cell the player is partly in, which the floor-of-center model read
    # as free and the hand spent a server-bounced click on. Now named. (Fails before the
    # box-span fix, where only cells {0} were occupied.)
    decision = use_target_refusal(
        reading(state=standing(x=0.9), aim=aimed_at(block(2, 64, 0, AimFace.WEST)))
    )
    assert decision.refusal is ActionRefusal.PLACEMENT_TARGET_IN_SELF


def test_the_same_neighbour_cell_stays_free_for_a_centered_player() -> None:
    # Control against over-refusal: the identical (2,64,0).WEST target lands on (1,64,0),
    # but a player centered at x=0.5 has a box spanning only [0.2, 0.8] and never reaches
    # cell 1, so the placement is allowed. Only the boundary straddle changes the verdict.
    assert use_target_refusal(
        reading(state=standing(x=0.5), aim=aimed_at(block(2, 64, 0, AimFace.WEST)))
    ).accepted


def test_use_target_signature_names_the_aimed_target_and_reads_nothing_as_none() -> None:
    """The identity the repeat guard compares on: the block-and-face (or the entity) the
    crosshair reports, and `None` for an aim no click could land on — so "there was no
    target" is never mistaken for "this target was already tried".

    A changed coordinate, a changed face, or a changed entity each read differently, which
    is what lets a re-aimed placement ask reopen; the same target reads the same.
    """

    lower = block(4, -2, 9, AimFace.UP)
    assert use_target_signature(reading(aim=aimed_at(lower))) == ("block", 4, -2, 9, "UP")
    assert use_target_signature(reading(aim=aimed_at(lower))) == use_target_signature(
        reading(aim=aimed_at(lower))
    )
    # The face the block is placed against is part of the target, not decoration.
    assert use_target_signature(reading(aim=aimed_at(block(4, -2, 9, AimFace.NORTH)))) != (
        "block",
        4,
        -2,
        9,
        "UP",
    )
    assert use_target_signature(reading(aim=aimed_entity("obs-1"))) == ("entity", "obs-1")
    assert use_target_signature(reading(aim=aimed_entity("obs-1"))) != use_target_signature(
        reading(aim=aimed_entity("obs-2"))
    )
    assert use_target_signature(reading()) is None
    assert use_target_signature(None) is None
    assert (
        use_target_signature(reading(aim=AimTargetValue(game_tick=100, kind=AimKind.MISS))) is None
    )


def test_an_unnamed_face_or_entity_aim_stays_tolerant() -> None:
    # NOT_READ names no direction, so there is no cell to collide with; an
    # entity is activated on the thing itself, never the air in front of it.
    assert use_target_refusal(
        reading(state=standing(), aim=aimed_at(block(0, 63, 0, AimFace.NOT_READ)))
    ).accepted
    assert use_target_refusal(reading(state=standing(), aim=aimed_entity())).accepted


def test_an_absent_position_refuses_nothing() -> None:
    # "No position" is not "position zero": with no feet cell to compare the
    # placement precondition stays silent rather than guessing the origin.
    assert use_target_refusal(reading(aim=aimed_at(block(0, -1, 0, AimFace.UP)))).accepted


# ---------------------------------------------------------------------------
# §4 row five: the use key answered — a window opened or the hand spent one
# ---------------------------------------------------------------------------


def test_use_confirms_when_a_window_opens_that_was_not_standing() -> None:
    pre = reading(aim=aimed_entity())
    post = reading(
        tick=110,
        aim=aimed_entity(),
        gui=GuiScreenValue(screen_id="chest", sync_id=3),
    )
    assert verify_use_effect(pre=pre, post=post, held_item_id=None) is ActionResultClass.CONFIRMED


def test_use_confirms_when_the_held_item_count_drops_on_a_synced_revision() -> None:
    pre = reading(
        aim=aimed_at(block()),
        inventory=stacks((0, "minecraft:oak_planks", 5)),
        state=in_hand(0, "minecraft:oak_planks"),
    )
    post = reading(
        tick=110,
        aim=aimed_at(block()),
        inventory=InventoryValue(
            revision=110,
            stacks=(InventoryStackValue(slot=0, item_id="minecraft:oak_planks", count=4),),
        ),
        state=in_hand(0, "minecraft:oak_planks"),
    )
    assert (
        verify_use_effect(pre=pre, post=post, held_item_id="minecraft:oak_planks")
        is ActionResultClass.CONFIRMED
    )


def test_a_held_count_falling_without_a_synced_revision_is_unknown() -> None:
    pre = reading(
        aim=aimed_at(block()),
        inventory=stacks((0, "minecraft:oak_planks", 5)),
        state=in_hand(0, "minecraft:oak_planks"),
    )
    # The same revision as `stacks` stamps (100), so a decrease here is a wish,
    # not the server's move.
    post = reading(
        tick=110,
        aim=aimed_at(block()),
        inventory=stacks((0, "minecraft:oak_planks", 4)),
        state=in_hand(0, "minecraft:oak_planks"),
    )
    assert (
        verify_use_effect(pre=pre, post=post, held_item_id="minecraft:oak_planks")
        is ActionResultClass.UNKNOWN
    )


def test_an_empty_handed_use_with_the_window_standing_closed_is_unknown() -> None:
    # Nothing was in hand to consume and no window opened; the absence of a
    # synced change is not proof the click failed — a door that needs a key reads
    # the same as a frame that has not arrived yet.
    pre = reading(aim=aimed_at(block()))
    post = reading(tick=110, aim=aimed_at(block()))
    assert verify_use_effect(pre=pre, post=post, held_item_id=None) is ActionResultClass.UNKNOWN


def test_a_use_never_concludes_failed_from_absent_evidence() -> None:
    pre = reading(aim=aimed_at(block()), inventory=stacks((0, "minecraft:dirt", 3)))
    post = reading(
        tick=110,
        aim=aimed_at(block()),
        inventory=InventoryValue(
            revision=110,
            stacks=(InventoryStackValue(slot=0, item_id="minecraft:dirt", count=3),),
        ),
    )
    verdict = verify_use_effect(pre=pre, post=post, held_item_id="minecraft:dirt")
    assert verdict is ActionResultClass.UNKNOWN
    assert verdict is not ActionResultClass.FAILED


def test_no_new_reading_confirms_a_use() -> None:
    pre = reading(aim=aimed_at(block()))
    same = reading(tick=100, aim=aimed_at(block()))
    assert verify_use_effect(pre=pre, post=same, held_item_id=None) is ActionResultClass.UNKNOWN


# ---------------------------------------------------------------------------
# §3/§4: the consume row — a meal is one frame with the bar up and the stack
# down, and every way of not earning that frame is named or stays unknown.
# ---------------------------------------------------------------------------


def hungry_state(
    *,
    food: int = 8,
    selected_slot: int | None = None,
    main_hand: str | None = None,
) -> SelfStateValue:
    return SelfStateValue(
        health=20.0,
        max_health=20.0,
        food=food,
        saturation=5.0,
        alive=True,
        selected_slot=selected_slot,
        main_hand_item_id=main_hand,
    )


def miss(tick: int = 100) -> AimTargetValue:
    return AimTargetValue(game_tick=tick, kind=AimKind.MISS)


def inventory_at(revision: int, *pairs: tuple[int, str, int]) -> InventoryValue:
    return InventoryValue(
        revision=revision,
        stacks=tuple(
            InventoryStackValue(slot=slot, item_id=item_id, count=count)
            for slot, item_id, count in pairs
        ),
    )


def test_the_meal_candidate_prefers_the_largest_reachable_food() -> None:
    pre = reading(
        inventory=stacks(
            (1, "minecraft:carrot", 3),
            (4, "minecraft:bread", 5),
            (12, "minecraft:pumpkin_pie", 1),
        )
    )
    # The pie restores more than the bread, but it sits in the bag proper — a
    # number key cannot reach slot 12, so it is not a candidate this build can
    # act on, and the bread is.
    assert consume_candidate(pre) == "minecraft:bread"

    tie = reading(inventory=stacks((2, "minecraft:golden_apple", 1), (0, "minecraft:apple", 1)))
    assert consume_candidate(tie) == "minecraft:apple"

    assert consume_candidate(reading(inventory=stacks((0, "minecraft:stone", 4)))) is None


def test_the_hotbar_lookup_ignores_the_wider_bag() -> None:
    bag = inventory_at(100, (12, "minecraft:apple", 1), (3, "minecraft:bread", 1))
    assert hotbar_slot_for_item(bag, "minecraft:bread") == 3
    assert hotbar_slot_for_item(bag, "minecraft:apple") is None
    assert hotbar_slot_for_item(bag, "minecraft:stone") is None


def test_reachable_food_items_lists_the_hotbar_meals_once_each() -> None:
    pre = reading(
        inventory=inventory_at(
            100,
            (0, "minecraft:apple", 2),
            (9, "minecraft:apple", 1),
            (1, "minecraft:bread", 1),
            (2, "minecraft:stone", 4),
        )
    )
    # Slot 9 is the wider bag, which no number key reaches: the second apple adds
    # nothing, and one entry per reachable item id comes back.
    assert reachable_food_items(pre) == ("minecraft:apple", "minecraft:bread")

    # A whole curated food the hotbar cannot reach is left out — it would only be
    # an ask the skill refuses by name (`CONSUME_ITEM_NOT_IN_HOTBAR`).
    bag_only = reading(
        inventory=inventory_at(100, (12, "minecraft:apple", 2), (1, "minecraft:bread", 1))
    )
    assert reachable_food_items(bag_only) == ("minecraft:bread",)

    # The hand's own item is reachable by definition, whatever the stack list says.
    held = reading(
        state=hungry_state(selected_slot=4, main_hand="minecraft:apple"),
        inventory=inventory_at(100, (1, "minecraft:bread", 1)),
    )
    assert reachable_food_items(held) == ("minecraft:apple", "minecraft:bread")


def test_reachable_weapons_lists_the_hotbar_weapons_once_each_and_picks_the_best() -> None:
    pre = reading(
        inventory=inventory_at(
            100,
            (0, "minecraft:wooden_sword", 1),
            (9, "minecraft:stone_axe", 1),
            (1, "minecraft:stone_axe", 1),
            (2, "minecraft:oak_log", 4),
        )
    )
    # Slot 9 is the wider bag, which no number key reaches: the second axe adds
    # nothing, and one entry per reachable item id comes back.
    assert reachable_weapons(pre) == ("minecraft:stone_axe", "minecraft:wooden_sword")
    # The most damage wins the hand -- the stone axe's 9 over the wooden sword's 4 --
    # and the answer carries the damage the ordering was made of.
    assert best_wieldable_weapon(pre) == ("minecraft:stone_axe", 9)

    # A whole curated weapon the hotbar cannot reach is left out: no skill moves
    # items between bag and hotbar, so naming it would only invite an ask the fight
    # cannot honour.
    bag_only = reading(
        inventory=inventory_at(
            100, (12, "minecraft:stone_axe", 1), (1, "minecraft:wooden_sword", 1)
        )
    )
    assert reachable_weapons(bag_only) == ("minecraft:wooden_sword",)
    assert best_wieldable_weapon(bag_only) == ("minecraft:wooden_sword", 4)

    # The hand's own weapon is reachable by definition, whatever the stack list says.
    held = reading(
        state=hungry_state(selected_slot=4, main_hand="minecraft:wooden_sword"),
        inventory=inventory_at(100, (1, "minecraft:stone_axe", 1)),
    )
    assert reachable_weapons(held) == ("minecraft:stone_axe", "minecraft:wooden_sword")
    assert best_wieldable_weapon(held) == ("minecraft:stone_axe", 9)

    # Nothing curated in reach: bare hands, and the empty answer is a fact about this
    # build's table, not about the bag.
    bare = reading(inventory=inventory_at(100, (0, "minecraft:oak_log", 1)))
    assert reachable_weapons(bare) == ()
    assert best_wieldable_weapon(bare) is None


def test_the_consume_refusal_walks_its_reasons_in_order() -> None:
    # Nothing of it in the bag at all.
    pre = reading(state=hungry_state(), aim=miss())
    assert (
        consume_item_refusal(pre, "minecraft:apple").refusal is ActionRefusal.CONSUME_ITEM_MISSING
    )
    # Present, but the curated table has no row: this build will not try it.
    pre = reading(state=hungry_state(), aim=miss(), inventory=stacks((3, "minecraft:stone", 1)))
    assert (
        consume_item_refusal(pre, "minecraft:stone").refusal
        is ActionRefusal.CONSUME_ITEM_NOT_KNOWN_FOOD
    )
    # A full bar is the one state where a meal changes nothing the verdict can read.
    pre = reading(
        state=hungry_state(food=20), aim=miss(), inventory=stacks((3, "minecraft:apple", 1))
    )
    assert consume_item_refusal(pre, "minecraft:apple").refusal is ActionRefusal.CONSUME_NOT_HUNGRY
    # In the bag proper, so no number key can bring it to hand.
    pre = reading(state=hungry_state(), aim=miss(), inventory=stacks((12, "minecraft:apple", 1)))
    assert (
        consume_item_refusal(pre, "minecraft:apple").refusal
        is ActionRefusal.CONSUME_ITEM_NOT_IN_HOTBAR
    )
    # The crosshair rests on a block: the use key would fire there first.
    pre = reading(
        state=hungry_state(), aim=aimed_at(block()), inventory=stacks((3, "minecraft:apple", 1))
    )
    assert (
        consume_item_refusal(pre, "minecraft:apple").refusal is ActionRefusal.CONSUME_AIM_NOT_CLEAR
    )
    # No aim read at all is not the positive "looked and saw nothing".
    pre = reading(state=hungry_state(), inventory=stacks((3, "minecraft:apple", 1)))
    assert (
        consume_item_refusal(pre, "minecraft:apple").refusal is ActionRefusal.CONSUME_AIM_NOT_CLEAR
    )
    # A hotbar food under a clear crosshair is the accepted case.
    pre = reading(state=hungry_state(), aim=miss(), inventory=stacks((3, "minecraft:apple", 1)))
    assert consume_item_refusal(pre, "minecraft:apple").accepted
    # One already in hand needs no number key to have a slot.
    pre = reading(
        state=hungry_state(selected_slot=4, main_hand="minecraft:apple"),
        aim=miss(),
        inventory=stacks((4, "minecraft:apple", 1)),
    )
    assert consume_item_refusal(pre, "minecraft:apple").accepted


def test_a_meal_confirms_on_one_frame_with_the_bar_up_and_the_stack_down() -> None:
    pre = reading(
        tick=100, state=hungry_state(food=8), inventory=inventory_at(300, (3, "minecraft:apple", 2))
    )
    post = reading(
        tick=120,
        state=hungry_state(food=12),
        inventory=inventory_at(320, (3, "minecraft:apple", 1)),
    )
    assert (
        verify_consume_effect(pre=pre, post=post, item_id="minecraft:apple")
        is ActionResultClass.CONFIRMED
    )


def test_a_meal_does_not_confirm_on_half_the_evidence() -> None:
    pre = reading(
        tick=100, state=hungry_state(food=8), inventory=inventory_at(300, (3, "minecraft:apple", 2))
    )
    # The bar rose, the stack did not move: not this meal.
    bar_only = reading(
        tick=120,
        state=hungry_state(food=12),
        inventory=inventory_at(320, (3, "minecraft:apple", 2)),
    )
    assert (
        verify_consume_effect(pre=pre, post=bar_only, item_id="minecraft:apple")
        is ActionResultClass.UNKNOWN
    )
    # The stack shrank, the bar did not: the item went somewhere else.
    stack_only = reading(
        tick=120, state=hungry_state(food=8), inventory=inventory_at(320, (3, "minecraft:apple", 1))
    )
    assert (
        verify_consume_effect(pre=pre, post=stack_only, item_id="minecraft:apple")
        is ActionResultClass.UNKNOWN
    )


def test_a_meal_does_not_confirm_without_a_newer_frame_or_a_synced_revision() -> None:
    pre = reading(
        tick=100,
        state=hungry_state(food=8),
        inventory=inventory_at(300, (3, "minecraft:apple", 2)),
    )
    # Both changes present, but the inventory revision never moved: a wish.
    unsynced = reading(
        tick=120,
        state=hungry_state(food=12),
        inventory=inventory_at(300, (3, "minecraft:apple", 1)),
    )
    assert (
        verify_consume_effect(pre=pre, post=unsynced, item_id="minecraft:apple")
        is ActionResultClass.UNKNOWN
    )
    # The same frame is not a later one.
    same = reading(
        tick=100,
        state=hungry_state(food=12),
        inventory=inventory_at(320, (3, "minecraft:apple", 1)),
    )
    assert (
        verify_consume_effect(pre=pre, post=same, item_id="minecraft:apple")
        is ActionResultClass.UNKNOWN
    )
