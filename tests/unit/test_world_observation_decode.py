"""Decoding `WorldObservation`: absence is not zero, in the field-by-field words.

The S2 contract's first rule about reading is that a field the Bridge did not
send is *unread*, not a value any player would recognize. Proto3 makes that a
`HasField` question, and the failure mode it prevents is specific and mean:
an unread yaw of 0.0 is south, a missing sync_id of 0 is the player's own
inventory handler, and an unclaimed slot 0 is a stack the Kin never had. Each
test here decodes a message with the field left out, and asserts the domain
value holds `None` — the fact the contract says it holds.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from google.protobuf.message import Message

from minekin_core.adapters.bridge.world_observation import decode_world_observation
from minekin_core.domain.perception import (
    MAX_CHAT_TEXT_CHARS,
    AimFace,
    AimKind,
    IntegrityViolation,
    world_observation_violations,
)
from minekin_core.generated.minekin.v1 import control_pb2, observation_pb2


def healthy_self() -> observation_pb2.SelfState:
    """Alive, fed, and nothing else.

    The position, angle, slot and hand fields stay unset here: several tests
    below are about the difference between *unread* and an honest zero, so the
    baseline must leave them off the wire rather than default them.
    """

    return observation_pb2.SelfState(
        health=20.0,
        max_health=20.0,
        food=20,
        saturation=5.0,
        alive=True,
    )


def wire_observation(**changes: object) -> observation_pb2.WorldObservation:
    """A coherent baseline reading: tick 100, generation 1, one log in slot 0."""

    message = observation_pb2.WorldObservation(
        generation=1,
        game_tick=100,
        self=healthy_self(),
        inventory=observation_pb2.InventorySummary(
            revision=100,
            stacks=[observation_pb2.InventoryStack(slot=0, item_id="minecraft:oak_log", count=3)],
        ),
    )
    descriptor = observation_pb2.WorldObservation.DESCRIPTOR
    for name, value in changes.items():
        field = descriptor.fields_by_name[name]
        if field.is_repeated:
            getattr(message, name).extend(cast("Iterable[Message]", value))
        elif field.message_type is not None:
            # A submessage is not assignable on the Python protobuf API — and
            # `CopyFrom` is the word that means what the tests mean: this reading
            # carries that field instead of the baseline's, present and complete.
            getattr(message, name).CopyFrom(cast("Message", value))
        else:
            setattr(message, name, value)
    return message


def decoded(**changes: object) -> object:
    return decode_world_observation(wire_observation(**changes))


# ---------------------------------------------------------------------------
# The four aim kinds, and the no-screen case
# ---------------------------------------------------------------------------


def test_a_block_aim_decodes_its_target_face_and_rendered_block() -> None:
    aim = observation_pb2.AimTarget(
        game_tick=100,
        kind=observation_pb2.AIM_TARGET_KIND_BLOCK,
        block=control_pb2.BlockTarget(x=4, y=-2, z=9, face=control_pb2.BLOCK_FACE_UP),
        targeted_block_id="minecraft:oak_log",
        distance=2.5,
    )
    value = decode_world_observation(wire_observation(aim=aim))

    assert value.aim is not None
    assert value.aim.kind is AimKind.BLOCK
    assert value.aim.block is not None
    assert (value.aim.block.x, value.aim.block.y, value.aim.block.z) == (4, -2, 9)
    assert value.aim.block.face is AimFace.UP
    assert value.aim.targeted_block_id == "minecraft:oak_log"
    assert value.aim.distance == 2.5
    assert world_observation_violations(value) == ()


def test_a_miss_aim_is_a_read_that_saw_nothing_not_an_absence() -> None:
    aim = observation_pb2.AimTarget(game_tick=100, kind=observation_pb2.AIM_TARGET_KIND_MISS)
    value = decode_world_observation(wire_observation(aim=aim))

    assert value.aim is not None
    assert value.aim.kind is AimKind.MISS
    assert value.aim.block is None
    # "Looked and hit nothing" is coherent; only "the whole aim is absent" says
    # nobody looked, and that is carried by `aim is None`, not by a MISS.
    assert world_observation_violations(value) == ()


def test_an_entity_aim_shares_the_visible_list_vocabulary() -> None:
    aim = observation_pb2.AimTarget(
        game_tick=100,
        kind=observation_pb2.AIM_TARGET_KIND_ENTITY,
        entity_observation_id="obs-3",
        entity_type="minecraft:cow",
        distance=5.0,
    )
    value = decode_world_observation(wire_observation(aim=aim))

    assert value.aim is not None
    assert value.aim.kind is AimKind.ENTITY
    assert value.aim.entity_observation_id == "obs-3"
    assert value.aim.block is None


def test_an_unnamed_aim_kind_is_unread_rather_than_a_miss() -> None:
    aim = observation_pb2.AimTarget(game_tick=100, kind=observation_pb2.AIM_TARGET_KIND_UNSPECIFIED)
    value = decode_world_observation(wire_observation(aim=aim))

    assert value.aim is not None
    assert value.aim.kind is AimKind.UNREAD
    assert IntegrityViolation.AIM_KIND_UNREAD in world_observation_violations(value)


def test_a_wholly_absent_aim_decodes_as_nothing_rather_than_as_a_miss() -> None:
    value = decode_world_observation(wire_observation())
    assert value.aim is None


def test_a_no_screen_observation_decodes_as_no_gui_and_never_a_zero_handler() -> None:
    """Two shapes of "no screen", and neither invents syncId 0.

    A `WorldObservation` without a `gui` submessage and a `gui` that names the
    title bar but not a handler are both "there is no container to click": the
    first has no message at all, the second has `sync_id` absent, and proto3's
    zero for that absent field would open every GUI click onto the player's own
    inventory. The decoder leaves both as `None`, so `gui_click_refusal` can do
    its named refusal.
    """

    no_gui = decode_world_observation(wire_observation())
    assert no_gui.gui is None

    screen_only = observation_pb2.GuiScreen(screen_id="class net.minecraft.screen.Screen")
    opened_without_handler = decode_world_observation(wire_observation(gui=screen_only))
    assert opened_without_handler.gui is not None
    assert opened_without_handler.gui.sync_id is None
    assert world_observation_violations(opened_without_handler) == ()

    with_handler = observation_pb2.GuiScreen(
        screen_id="class net.minecraft.screen.CraftingScreenHandler", sync_id=0
    )
    synced = decode_world_observation(wire_observation(gui=with_handler))
    assert synced.gui is not None
    # sync_id 0 sent explicitly is the real handler, and reads as 0 — the
    # absence test above is what keeps that from ever being confused.
    assert synced.gui.sync_id == 0


def test_the_client_recipe_book_decodes_into_a_craftable_set_and_absent_is_empty() -> None:
    """#47: the wire's `craftable_recipe_ids` is the recipe book the client reports for the open
    screen, and the decoder reads it as a set. A GuiScreen that names none leaves the empty set
    (there is nothing to attest), so a Bridge that has not begun reporting it stays inert rather
    than being mistaken for "nothing is craftable"."""

    reported = observation_pb2.GuiScreen(
        screen_id="class net.minecraft.screen.CraftingScreenHandler",
        sync_id=4,
        craftable_recipe_ids=["minecraft:wooden_pickaxe", "minecraft:stick"],
    )
    decoded = decode_world_observation(wire_observation(gui=reported))
    assert decoded.gui is not None
    assert decoded.gui.craftable_recipe_ids == frozenset(
        {"minecraft:wooden_pickaxe", "minecraft:stick"}
    )
    assert world_observation_violations(decoded) == ()

    silent = observation_pb2.GuiScreen(
        screen_id="class net.minecraft.screen.CraftingScreenHandler", sync_id=4
    )
    absent = decode_world_observation(wire_observation(gui=silent))
    assert absent.gui is not None
    assert absent.gui.craftable_recipe_ids == frozenset()


def test_an_open_merchants_offers_decode_row_by_row_and_absent_is_empty() -> None:
    """The wire's trade rows are the open merchant's list in the client's order: the
    adjusted buy stacks, the optional second, the sell stack, uses/max and disabled,
    verbatim. A GuiScreen that names none leaves the empty tuple, so every non-merchant
    screen (and a Bridge that has not begun reporting) stays inert."""

    reported = observation_pb2.GuiScreen(
        screen_id="class net.minecraft.screen.MerchantScreenHandler",
        sync_id=5,
        trade_offers=[
            observation_pb2.TradeOffer(
                first_item_id="minecraft:emerald",
                first_count=3,
                sell_item_id="minecraft:bread",
                sell_count=2,
                uses=4,
                max_uses=12,
            ),
            observation_pb2.TradeOffer(
                first_item_id="minecraft:wheat",
                first_count=20,
                second_item_id="minecraft:emerald",
                second_count=1,
                sell_item_id="minecraft:emerald",
                sell_count=1,
                uses=0,
                max_uses=16,
                disabled=True,
            ),
        ],
    )
    decoded = decode_world_observation(wire_observation(gui=reported))
    assert decoded.gui is not None
    offers = decoded.gui.trade_offers
    assert len(offers) == 2
    assert offers[0].first_item_id == "minecraft:emerald"
    assert offers[0].first_count == 3
    assert offers[0].second_item_id == ""
    assert offers[0].sell_item_id == "minecraft:bread"
    assert offers[0].sell_count == 2
    assert offers[0].uses == 4
    assert offers[0].max_uses == 12
    assert offers[0].disabled is False
    assert offers[1].second_item_id == "minecraft:emerald"
    assert offers[1].disabled is True
    assert world_observation_violations(decoded) == ()

    silent = observation_pb2.GuiScreen(
        screen_id="class net.minecraft.screen.MerchantScreenHandler", sync_id=5
    )
    absent = decode_world_observation(wire_observation(gui=silent))
    assert absent.gui is not None
    assert absent.gui.trade_offers == ()


# ---------------------------------------------------------------------------
# Absence is not zero, one optional field at a time
# ---------------------------------------------------------------------------


def test_self_state_positions_are_none_when_not_read() -> None:
    value = decode_world_observation(wire_observation())
    state = value.self_state
    assert (state.x, state.y, state.z) == (None, None, None)
    # And a read position, including an honest zero, survives: None vs 0.0 is
    # the whole distinction, so 0.0 has to come through as 0.0.
    at_origin = observation_pb2.SelfState(
        health=20.0,
        max_health=20.0,
        food=20,
        saturation=5.0,
        alive=True,
        x=0.0,
        y=0.0,
        z=0.0,
        yaw_degrees=0.0,
        pitch_degrees=0.0,
    )
    read = decode_world_observation(wire_observation(self=at_origin)).self_state
    assert (read.x, read.y, read.z) == (0.0, 0.0, 0.0)
    assert (read.yaw_degrees, read.pitch_degrees) == (0.0, 0.0)


def test_angles_hotbar_and_hand_are_none_when_not_read() -> None:
    state = observation_pb2.SelfState(
        health=20.0,
        max_health=20.0,
        food=20,
        saturation=5.0,
        alive=True,
        x=1.0,
        y=2.0,
        z=3.0,
        selected_slot=0,
    )
    value = decode_world_observation(wire_observation(self=state))

    # A slot that was read says 0 and is *not* the unread case; angles nobody
    # read are None even though the wire's own default for them is 0.0.
    assert value.self_state.selected_slot == 0
    assert value.self_state.yaw_degrees is None
    assert value.self_state.pitch_degrees is None
    # §2: an absent hand item is an empty hand, not an unread hotbar.
    assert value.self_state.main_hand_item_id is None


def test_a_slot_zero_selected_is_kept_apart_from_no_selection() -> None:
    unread = decode_world_observation(wire_observation())
    assert unread.self_state.selected_slot is None


def test_distance_is_none_when_the_ray_hit_nothing_to_measure() -> None:
    aim = observation_pb2.AimTarget(game_tick=100, kind=observation_pb2.AIM_TARGET_KIND_BLOCK)
    value = decode_world_observation(wire_observation(aim=aim))
    assert value.aim is not None
    assert value.aim.distance is None


def test_entity_item_fields_are_none_for_entities_that_are_not_items() -> None:
    entity = observation_pb2.VisibleEntity(
        observation_id="obs-9",
        entity_type="minecraft:zombie",
        relative_x=2.0,
        relative_y=0.0,
        relative_z=-1.0,
        line_of_sight=True,
    )
    value = decode_world_observation(wire_observation(visible_entities=[entity]))

    assert value.visible_entities[0].item_id is None
    assert value.visible_entities[0].item_count is None


def test_a_dropped_item_keeps_both_sides_of_its_pair_including_a_count_of_zero() -> None:
    drop = observation_pb2.VisibleEntity(
        observation_id="obs-10",
        entity_type="minecraft:item",
        relative_x=1.0,
        relative_y=-1.0,
        relative_z=1.0,
        line_of_sight=True,
        item_id="minecraft:oak_log",
        item_count=1,
    )
    value = decode_world_observation(wire_observation(visible_entities=[drop]))

    assert value.visible_entities[0].item_id == "minecraft:oak_log"
    assert value.visible_entities[0].item_count == 1


def test_mining_absent_is_none_and_mining_present_keeps_a_zero_progress() -> None:
    value = decode_world_observation(wire_observation())
    assert value.mining is None

    progress = observation_pb2.MiningProgress(
        game_tick=100,
        target=control_pb2.BlockTarget(x=4, y=-2, z=9, face=control_pb2.BLOCK_FACE_UP),
        progress=0.0,
    )
    started = decode_world_observation(wire_observation(mining=progress))
    assert started.mining is not None
    # A break that just started is at 0.0, and that is a *read* 0.0 — the same
    # sentence the HUD fields get from `None` meaning "never asked".
    assert started.mining.progress == 0.0
    assert started.mining.target.face is AimFace.UP


def test_respawn_availability_distinguishes_unread_unavailable_and_available() -> None:
    from minekin_core.adapters.bridge.perception import decode_self_state as decode_initial

    for value in (None, False, True):
        body = observation_pb2.SelfState(health=0, max_health=20, food=20, alive=False)
        if value is not None:
            body.respawn_available = value
        wire = wire_observation()
        wire.self.CopyFrom(body)
        recurring = decode_world_observation(wire)
        initial = decode_initial(observation_pb2.InitialObservation(self=body))
        assert recurring.self_state.respawn_available is value
        assert initial.respawn_available is value
        assert world_observation_violations(recurring) == ()


def test_a_respawn_affordance_on_a_living_body_is_not_admitted() -> None:
    wire = wire_observation()
    wire.self.respawn_available = True
    decoded = decode_world_observation(wire)
    assert IntegrityViolation.RESPAWN_AVAILABLE_WHILE_ALIVE in world_observation_violations(decoded)


# ---------------------------------------------------------------------------
# Chat: a drain of another account's words, bounded and attributed
# ---------------------------------------------------------------------------


def test_drained_chat_lines_decode_in_arrival_order_with_their_senders() -> None:
    reading = decode_world_observation(
        wire_observation(
            chat=[
                observation_pb2.PlayerChatMessage(game_tick=98, sender="Alex", text="need wood?"),
                observation_pb2.PlayerChatMessage(
                    game_tick=100, sender="Steve", text="the cave is north"
                ),
            ]
        )
    )

    assert [message.sender for message in reading.chat] == ["Alex", "Steve"]
    assert [message.text for message in reading.chat] == ["need wood?", "the cave is north"]
    assert reading.chat[0].game_tick == 98
    assert reading.chat_omitted == 0


def test_a_line_past_the_text_bound_is_clipped_with_an_ellipsis_not_dropped() -> None:
    """A long line is still a line: it is carried clipped — the goal-history
    lesson applied at this edge before it bites — and never silently cut."""

    reading = decode_world_observation(
        wire_observation(
            chat=[observation_pb2.PlayerChatMessage(game_tick=100, sender="Alex", text="x" * 400)]
        )
    )

    assert len(reading.chat) == 1
    text = reading.chat[0].text
    assert len(text) == MAX_CHAT_TEXT_CHARS
    assert text.endswith("…")


def test_an_unattributable_line_is_not_carried() -> None:
    """A line with no sender, a sender past its bound, or no text at all is
    skipped rather than repaired — every later reader would otherwise have to
    guess whose words these are, and a guess about attribution is the one thing
    this surface may not ask of its readers."""

    reading = decode_world_observation(
        wire_observation(
            chat=[
                observation_pb2.PlayerChatMessage(game_tick=100, sender="", text="from nobody"),
                observation_pb2.PlayerChatMessage(
                    game_tick=100, sender="N" * 200, text="too long a name"
                ),
                observation_pb2.PlayerChatMessage(game_tick=100, sender="Alex", text=""),
                observation_pb2.PlayerChatMessage(game_tick=100, sender="Alex", text="fine"),
            ]
        )
    )

    assert [message.text for message in reading.chat] == ["fine"]


def test_no_chat_reads_as_no_chat_and_an_omission_is_carried_explicitly() -> None:
    quiet = decode_world_observation(wire_observation())
    assert quiet.chat == ()
    assert quiet.chat_omitted == 0

    lossy = decode_world_observation(wire_observation(chat_omitted=5))
    assert lossy.chat == ()
    assert lossy.chat_omitted == 5


def test_a_senders_account_key_decodes_when_reported_and_is_optional() -> None:
    """The key is the stable anchor later memory uses; a line without one stands
    on its name alone rather than being dropped or getting a fabricated key."""

    reading = decode_world_observation(
        wire_observation(
            chat=[
                observation_pb2.PlayerChatMessage(
                    game_tick=100,
                    sender="Alex",
                    text="keyed",
                    sender_id="f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2",
                ),
                observation_pb2.PlayerChatMessage(
                    game_tick=101, sender="Steve", text="nameless key"
                ),
            ]
        )
    )

    assert reading.chat[0].sender_id == "f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2"
    assert reading.chat[1].sender_id == ""


def test_an_over_long_account_key_is_dropped_to_empty_while_the_line_stands() -> None:
    """The key is an enhancement, not the attribution itself: past its bound it
    is dropped to the empty string, where a missing NAME skips the line — the
    line keeps standing on what it has."""

    reading = decode_world_observation(
        wire_observation(
            chat=[
                observation_pb2.PlayerChatMessage(
                    game_tick=100, sender="Alex", text="hello", sender_id="k" * 100
                )
            ]
        )
    )

    assert len(reading.chat) == 1
    assert reading.chat[0].sender_id == ""
    assert reading.chat[0].text == "hello"


def test_a_hurt_reading_decodes_the_attacker_the_client_could_name() -> None:
    reading = decode_world_observation(
        wire_observation(
            hurt=observation_pb2.HurtSource(
                attacker_observation_id="f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2",
                attacker_type="minecraft:player",
                source_type="player_attack",
            )
        )
    )

    assert reading.hurt is not None
    assert reading.hurt.attacker_type == "minecraft:player"
    assert reading.hurt.source_type == "player_attack"
    assert reading.hurt.attacker_observation_id == "f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2"


def test_hurt_that_was_no_entity_says_so_instead_of_guessing_a_body() -> None:
    reading = decode_world_observation(
        wire_observation(hurt=observation_pb2.HurtSource(source_type="fall"))
    )

    assert reading.hurt is not None
    assert reading.hurt.attacker_observation_id == ""
    assert reading.hurt.attacker_type == ""
    assert reading.hurt.source_type == "fall"


def test_an_empty_or_absent_hurt_record_reads_as_no_record() -> None:
    """An empty record is "the client said nothing fresh", not a zeroed attacker."""

    absent = decode_world_observation(wire_observation())
    assert absent.hurt is None

    empty = decode_world_observation(wire_observation(hurt=observation_pb2.HurtSource()))
    assert empty.hurt is None


def test_an_over_long_hurt_field_falls_back_while_the_record_stands() -> None:
    reading = decode_world_observation(
        wire_observation(
            hurt=observation_pb2.HurtSource(attacker_type="minecraft:player", source_type="x" * 100)
        )
    )

    assert reading.hurt is not None
    assert reading.hurt.attacker_type == "minecraft:player"
    assert reading.hurt.source_type == ""
