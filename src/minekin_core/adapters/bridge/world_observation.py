"""Decode the recurring `WorldObservation` into the domain's own values.

The rule this module exists for is the S2 contract's first sentence about
reading: absence is not zero. Every `optional` scalar on the wire is asked with
`HasField` and decoded to `None` when it was not sent, because a yaw of 0.0
invented for a read that never happened is a direction nobody observed, and a
missing `sync_id` that decodes to 0 would open a click path onto the player's
own inventory.

Unlike the first-snapshot decode, this one does not adjudicate: it maps, and
`domain/perception.world_observation_violations` decides what the mapped shape
is allowed to mean. That split is deliberate — the snapshot decoder could gate
PLAYABLE on its verdict, while a recurring observation is one reading in a
stream, and its consumer (the store, then the skill that verifies a result)
needs the value and the findings apart.
"""

from __future__ import annotations

from collections.abc import Sequence

from minekin_core.domain.perception import (
    MAX_CHAT_SENDER_CHARS,
    MAX_CHAT_TEXT_CHARS,
    AimFace,
    AimKind,
    AimTargetValue,
    BlockTargetValue,
    ChatMessageValue,
    EntityCandidate,
    GuiScreenValue,
    InventoryStackValue,
    InventoryValue,
    MiningProgressValue,
    SelfStateValue,
    TradeOfferValue,
    WorldObservationValue,
)
from minekin_core.generated.minekin.v1 import control_pb2, observation_pb2

_AIM_KINDS: dict[int, AimKind] = {
    observation_pb2.AIM_TARGET_KIND_UNSPECIFIED: AimKind.UNREAD,
    observation_pb2.AIM_TARGET_KIND_MISS: AimKind.MISS,
    observation_pb2.AIM_TARGET_KIND_BLOCK: AimKind.BLOCK,
    observation_pb2.AIM_TARGET_KIND_ENTITY: AimKind.ENTITY,
}
#: `UNKNOWN` is the client's word for a hit with no face; `NOT_READ` is this
#: build's word for a face the Bridge left at the proto3 default. Keeping them
#: apart is what lets a reader tell "the ray hit something faceless" from "the
#: face never arrived".
_AIM_FACES: dict[int, AimFace] = {
    control_pb2.BLOCK_FACE_UNSPECIFIED: AimFace.NOT_READ,
    control_pb2.BLOCK_FACE_UNKNOWN: AimFace.UNKNOWN,
    control_pb2.BLOCK_FACE_DOWN: AimFace.DOWN,
    control_pb2.BLOCK_FACE_UP: AimFace.UP,
    control_pb2.BLOCK_FACE_NORTH: AimFace.NORTH,
    control_pb2.BLOCK_FACE_SOUTH: AimFace.SOUTH,
    control_pb2.BLOCK_FACE_WEST: AimFace.WEST,
    control_pb2.BLOCK_FACE_EAST: AimFace.EAST,
}


def decode_self_state(
    message: observation_pb2.SelfState,
) -> SelfStateValue:
    """The HUD fields plus the S2 read, with every absent field left absent."""

    return SelfStateValue(
        health=message.health,
        max_health=message.max_health,
        food=message.food,
        saturation=message.saturation,
        alive=message.alive,
        respawn_available=(
            message.respawn_available if message.HasField("respawn_available") else None
        ),
        x=message.x if message.HasField("x") else None,
        y=message.y if message.HasField("y") else None,
        z=message.z if message.HasField("z") else None,
        yaw_degrees=message.yaw_degrees if message.HasField("yaw_degrees") else None,
        pitch_degrees=message.pitch_degrees if message.HasField("pitch_degrees") else None,
        selected_slot=(int(message.selected_slot) if message.HasField("selected_slot") else None),
        main_hand_item_id=(
            message.main_hand_item_id if message.HasField("main_hand_item_id") else None
        ),
    )


def decode_inventory(summary: observation_pb2.InventorySummary) -> InventoryValue:
    return InventoryValue(
        revision=summary.revision,
        stacks=tuple(
            InventoryStackValue(slot=stack.slot, item_id=stack.item_id, count=stack.count)
            for stack in summary.stacks
        ),
    )


def decode_visible_entities(
    entities: Sequence[observation_pb2.VisibleEntity],
) -> tuple[EntityCandidate, ...]:
    return tuple(
        EntityCandidate(
            observation_id=entity.observation_id,
            entity_type=entity.entity_type,
            relative_x=entity.relative_x,
            relative_y=entity.relative_y,
            relative_z=entity.relative_z,
            line_of_sight=entity.line_of_sight,
            item_id=entity.item_id if entity.HasField("item_id") else None,
            item_count=int(entity.item_count) if entity.HasField("item_count") else None,
        )
        for entity in entities
    )


def decode_block_target(target: control_pb2.BlockTarget) -> BlockTargetValue:
    return BlockTargetValue(
        x=target.x,
        y=target.y,
        z=target.z,
        face=_AIM_FACES.get(target.face, AimFace.NOT_READ),
    )


def decode_aim(aim: observation_pb2.AimTarget) -> AimTargetValue:
    return AimTargetValue(
        game_tick=aim.game_tick,
        kind=_AIM_KINDS.get(aim.kind, AimKind.UNREAD),
        # Only the branch the kind selects; an absent submessage is not decoded
        # into a zero-position block, which is the same rule the scalars follow.
        block=decode_block_target(aim.block) if aim.HasField("block") else None,
        targeted_block_id=aim.targeted_block_id,
        entity_observation_id=aim.entity_observation_id,
        entity_type=aim.entity_type,
        distance=aim.distance if aim.HasField("distance") else None,
    )


def decode_mining(mining: observation_pb2.MiningProgress) -> MiningProgressValue:
    return MiningProgressValue(
        game_tick=mining.game_tick,
        target=decode_block_target(mining.target),
        progress=mining.progress,
    )


def decode_gui(gui: observation_pb2.GuiScreen) -> GuiScreenValue:
    return GuiScreenValue(
        screen_id=gui.screen_id,
        sync_id=int(gui.sync_id) if gui.HasField("sync_id") else None,
        craftable_recipe_ids=frozenset(gui.craftable_recipe_ids),
        trade_offers=tuple(
            TradeOfferValue(
                first_item_id=offer.first_item_id,
                first_count=offer.first_count,
                second_item_id=offer.second_item_id,
                second_count=offer.second_count,
                sell_item_id=offer.sell_item_id,
                sell_count=offer.sell_count,
                uses=offer.uses,
                max_uses=offer.max_uses,
                disabled=offer.disabled,
            )
            for offer in gui.trade_offers
        ),
    )


def decode_chat(
    messages: Sequence[observation_pb2.PlayerChatMessage],
) -> tuple[ChatMessageValue, ...]:
    """The drained player-chat lines, held to their bounds again at this edge.

    The Bridge already holds the same bounds before sending; they are re-applied
    here because the wire is a stranger, not because the Bridge is doubted. A
    line past the text bound is clipped with an ellipsis — a long line is still
    a line — while a line with no sender or a sender past its bound is skipped:
    an unattributable quote would make every later reader guess whose words it
    is, and a guess about attribution is the one thing this surface may not ask
    of its readers. Order is the wire's own (oldest first).
    """

    carried: list[ChatMessageValue] = []
    for message in messages:
        sender = message.sender
        if not sender or len(sender) > MAX_CHAT_SENDER_CHARS or not message.text:
            continue
        text = message.text
        clipped = (
            text if len(text) <= MAX_CHAT_TEXT_CHARS else text[: MAX_CHAT_TEXT_CHARS - 1] + "…"
        )
        carried.append(ChatMessageValue(game_tick=message.game_tick, sender=sender, text=clipped))
    return tuple(carried)


def decode_world_observation(
    message: observation_pb2.WorldObservation,
) -> WorldObservationValue:
    """The one path from a wire observation to the domain value.

    Submessages are gated by `HasField`, so an aim the Bridge never read stays
    `None` rather than becoming a MISS, and a mining state nobody is in stays
    `None` rather than becoming a break at zero on block (0, 0, 0).
    """

    return WorldObservationValue(
        generation=message.generation,
        game_tick=message.game_tick,
        self_state=decode_self_state(message.self),
        aim=decode_aim(message.aim) if message.HasField("aim") else None,
        inventory=decode_inventory(message.inventory),
        visible_entities=decode_visible_entities(message.visible_entities),
        mining=decode_mining(message.mining) if message.HasField("mining") else None,
        gui=decode_gui(message.gui) if message.HasField("gui") else None,
        chat=decode_chat(message.chat),
        chat_omitted=(int(message.chat_omitted) if message.HasField("chat_omitted") else 0),
    )
