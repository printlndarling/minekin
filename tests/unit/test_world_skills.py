"""The four S2 skills sequenced over a fake sender and a real store.

A skill is only a sequence — check, send, wait for the next admitted reading,
conclude — so these tests hand it a sender that records and a store whose
readings arrive on a timer, and then ask the two questions that matter about
every skill: what it refused before the wire, and what word it concluded from
the readings. `CONFIRMED` must only appear when a post-reading says so,
`UNKNOWN` must never buy a second side-effecting click, and the release of the
mine key must arrive on every path that stops.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Final

from google.protobuf.message import Message

from minekin_core.adapters.bridge.ipc import (
    AIM_CAPABILITY,
    AIM_INPUT_TYPE,
    GUI_CAPABILITY,
    GUI_CLICK_INPUT_TYPE,
    HOTBAR_CAPABILITY,
    MINE_CAPABILITY,
    MINE_INPUT_TYPE,
    MOVE_CAPABILITY,
    MOVE_INPUT_TYPE,
    SCREEN_CAPABILITY,
    monotonic_ns,
)
from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.application.world_skills import (
    ActionAuthority,
    WorldSkills,
)
from minekin_core.domain.perception import (
    AimFace,
    AimKind,
    AimTargetValue,
    BlockTargetValue,
    EntityCandidate,
    GuiScreenValue,
    InventoryStackValue,
    InventoryValue,
    SelfStateValue,
    WorldObservationValue,
)
from minekin_core.domain.world_actions import ActionResultClass

ALL_CAPABILITIES: Final = frozenset(
    {
        AIM_CAPABILITY,
        MINE_CAPABILITY,
        HOTBAR_CAPABILITY,
        SCREEN_CAPABILITY,
        GUI_CAPABILITY,
        MOVE_CAPABILITY,
    }
)
PLANKS = "minecraft:oak_planks"
PICKAXE = "minecraft:wooden_pickaxe"


class RecordingSender:
    """The transport as the skills see it: it remembers rather than answers.

    The ActionResult each command would earn is deliberately absent — §4 says the
    readings decide, and a fake that echoed success would let a skill pass a test
    it could never pass against a client.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, Message]] = []
        self.on_send: Callable[[str], None] | None = None

    async def send_control(self, message_type: str, message: Message) -> None:
        self.sent.append((message_type, message))
        if self.on_send is not None:
            self.on_send(message_type)

    def types(self) -> list[str]:
        return [message_type for message_type, _ in self.sent]


def authority() -> ActionAuthority:
    return ActionAuthority(
        lease_id="lease-1",
        generation=1,
        deadline_monotonic_ns=monotonic_ns() + 60_000_000_000,
    )


def state(*, yaw: float | None = None, pitch: float | None = None) -> SelfStateValue:
    return SelfStateValue(
        health=20.0,
        max_health=20.0,
        food=20,
        saturation=5.0,
        alive=True,
        yaw_degrees=yaw,
        pitch_degrees=pitch,
    )


def target() -> BlockTargetValue:
    return BlockTargetValue(x=4, y=-2, z=9, face=AimFace.UP)


def inventory(revision: int, *pairs: tuple[int, str, int]) -> InventoryValue:
    return InventoryValue(
        revision=revision,
        stacks=tuple(
            InventoryStackValue(slot=slot, item_id=item_id, count=count)
            for slot, item_id, count in pairs
        ),
    )


def reading(
    *,
    tick: int = 100,
    state_value: SelfStateValue | None = None,
    aim: AimTargetValue | None = None,
    inventory_value: InventoryValue | None = None,
    entities: tuple[EntityCandidate, ...] = (),
    gui: GuiScreenValue | None = None,
) -> WorldObservationValue:
    return WorldObservationValue(
        generation=1,
        game_tick=tick,
        self_state=state_value if state_value is not None else state(yaw=0.0, pitch=0.0),
        aim=aim,
        inventory=inventory_value if inventory_value is not None else inventory(100),
        visible_entities=entities,
        mining=None,
        gui=gui,
    )


def block_aim() -> AimTargetValue:
    return AimTargetValue(
        game_tick=100,
        kind=AimKind.BLOCK,
        block=target(),
        targeted_block_id="minecraft:oak_log",
        distance=2.0,
    )


def miss_aim(tick: int) -> AimTargetValue:
    return AimTargetValue(game_tick=tick, kind=AimKind.MISS)


def skill_with(
    store: WorldObservationStore,
    capabilities: frozenset[str] = ALL_CAPABILITIES,
) -> tuple[WorldSkills, RecordingSender]:
    sender = RecordingSender()
    return WorldSkills(sender=sender, observations=store, capabilities=capabilities), sender


def store_with(*values: WorldObservationValue) -> WorldObservationStore:
    store = WorldObservationStore(expected_generation=1)
    for value in values:
        admitted = store.admit(value, ())
        assert admitted
    return store


async def admit_later(store: WorldObservationStore, value: WorldObservationValue) -> None:
    await asyncio.sleep(0.02)
    store.admit(value, ())


# ---------------------------------------------------------------------------
# Capability refusals: each named skill, before it touches the wire
# ---------------------------------------------------------------------------


def test_each_skill_refuses_its_ungranted_capability_by_name() -> None:
    async def scenario() -> None:
        skills, sender = skill_with(store_with(reading()), capabilities=frozenset())
        lease = authority()

        outcomes = [
            await skills.turn_to(yaw_degrees=10.0, pitch_degrees=0.0, authority=lease),
            await skills.break_seen_block(authority=lease),
            await skills.collect_dropped(
                item_id="minecraft:oak_log", authority=lease, walk_seconds=0.0
            ),
            await skills.craft(
                recipe_id="r", materials={PLANKS: 1}, product_id=PICKAXE, authority=lease
            ),
            await skills.select_hotbar(slot=3, authority=lease),
        ]
        for outcome in outcomes:
            assert outcome.result is ActionResultClass.FAILED
            assert outcome.reason == "CAPABILITY_NOT_GRANTED"
        assert sender.sent == []

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# turn_to
# ---------------------------------------------------------------------------


def test_turn_concludes_confirmed_only_from_a_reading_that_arrived() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100, state_value=state(yaw=0.0, pitch=0.0)))
        skills, sender = skill_with(store)

        outcome = await skills.turn_to(yaw_degrees=0.0, pitch_degrees=0.0, authority=authority())
        assert outcome.result is ActionResultClass.CONFIRMED
        assert sender.types() == [AIM_INPUT_TYPE]

    asyncio.run(scenario())


def test_turn_reports_started_when_the_window_closes_mid_turn() -> None:
    """A long turn is the client's to pace: STARTED + AIM_IN_PROGRESS is the
    contract's normal answer, and the Core neither clamps the ask nor pretends
    it arrived."""

    async def scenario() -> None:
        store = store_with(reading(tick=100, state_value=state(yaw=0.0, pitch=0.0)))
        skills, sender = skill_with(store)

        outcome = await skills.turn_to(
            yaw_degrees=90.0,
            pitch_degrees=0.0,
            authority=authority(),
            timeout_ns=50_000_000,
        )
        assert outcome.result is ActionResultClass.STARTED
        assert outcome.reason == "AIM_IN_PROGRESS"
        assert AIM_INPUT_TYPE in sender.types()

    asyncio.run(scenario())


def test_turn_re_asks_the_same_target_across_readings_and_fails_a_stall() -> None:
    """STARTED then continue: each newer reading restarts the ask against itself,
    and a gap that stops closing is the AIM_STALLED failure, not another round of
    optimistic sending.

    The readings come back *because* an ask went out, on the sender's own hook:
    a stall is a claim about two different readings, so a timer that admitted
    them whenever it felt like it could let the second verdict rest on the same
    observation twice.
    """

    async def scenario() -> None:
        store = store_with(reading(tick=100, state_value=state(yaw=0.0, pitch=0.0)))
        skills, sender = skill_with(store)
        replies = iter(
            (
                reading(tick=110, state_value=state(yaw=40.0, pitch=0.0)),
                reading(tick=120, state_value=state(yaw=40.0, pitch=0.0)),
            )
        )

        def answer(_message_type: str) -> None:
            store.admit(next(replies), ())

        sender.on_send = answer

        outcome = await skills.turn_to(
            yaw_degrees=90.0,
            pitch_degrees=0.0,
            authority=authority(),
            timeout_ns=2_000_000_000,
        )
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "AIM_STALLED"
        assert sender.types().count(AIM_INPUT_TYPE) == 2

    asyncio.run(scenario())


def test_an_angle_that_cannot_be_arrived_at_is_refused_before_the_wire() -> None:
    async def scenario() -> None:
        store = store_with(reading())
        skills, sender = skill_with(store)

        outcome = await skills.turn_to(yaw_degrees=0.0, pitch_degrees=120.0, authority=authority())
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "AIM_ANGLE_IMPOSSIBLE"
        assert sender.sent == []

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# break_seen_block
# ---------------------------------------------------------------------------


def test_break_refuses_a_block_the_crosshair_is_not_on_before_the_wire() -> None:
    async def scenario() -> None:
        store = store_with(reading(aim=None))
        skills, sender = skill_with(store)

        outcome = await skills.break_seen_block(authority=authority())
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "MINE_TARGET_NOT_AIMED"
        assert sender.sent == []

    asyncio.run(scenario())


def test_break_confirms_from_the_reading_and_releases_the_key() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100, aim=block_aim()))
        skills, sender = skill_with(store)
        after = reading(tick=110, aim=miss_aim(110))

        task = asyncio.create_task(admit_later(store, after))
        outcome = await skills.break_seen_block(authority=authority(), timeout_ns=2_000_000_000)
        await task

        assert outcome.result is ActionResultClass.CONFIRMED
        mine_messages = [
            message for message_type, message in sender.sent if message_type == MINE_INPUT_TYPE
        ]
        assert len(mine_messages) == 2
        assert mine_messages[0].mining is True  # type: ignore[attr-defined]
        assert mine_messages[1].mining is False  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_break_without_a_confirming_reading_ends_unknown_with_the_key_released() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100, aim=block_aim()))
        skills, sender = skill_with(store)

        outcome = await skills.break_seen_block(authority=authority(), timeout_ns=50_000_000)

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"
        mine_messages = [
            message for message_type, message in sender.sent if message_type == MINE_INPUT_TYPE
        ]
        assert [message.mining for message in mine_messages] == [True, False]  # type: ignore[attr-defined]

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# collect_dropped
# ---------------------------------------------------------------------------


def test_collect_refuses_to_walk_toward_a_drop_it_never_saw() -> None:
    async def scenario() -> None:
        store = store_with(reading(entities=()))
        skills, sender = skill_with(store)

        outcome = await skills.collect_dropped(
            item_id="minecraft:oak_log", authority=authority(), walk_seconds=0.0
        )
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "NO_SEEN_DROP"
        assert sender.sent == []

    asyncio.run(scenario())


def oak_log_drop(*, tick: int, distance: float = 2.0) -> EntityCandidate:
    return EntityCandidate(
        observation_id=f"drop-{tick}",
        entity_type="item",
        relative_x=0.0,
        relative_y=0.0,
        relative_z=distance,
        line_of_sight=True,
        item_id="minecraft:oak_log",
        item_count=1,
    )


def test_collect_chases_a_drop_it_can_still_see_and_confirms_on_the_later_rise() -> None:
    async def scenario() -> None:
        # One blind step is what this skill used to end on: the reading after it
        # said the log was still on the ground half a block ahead, and the skill
        # waited out its window instead of taking the next step.
        still_there = reading(
            tick=110,
            inventory_value=inventory(100),
            entities=(oak_log_drop(tick=110, distance=0.6),),
        )
        came_away = reading(
            tick=120,
            inventory_value=inventory(120, (0, "minecraft:oak_log", 1)),
            entities=(),
        )
        store = store_with(
            reading(
                tick=100,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=100),),
            )
        )
        skills, sender = skill_with(store)
        queued = [still_there, came_away]

        def answer(message_type: str) -> None:
            # Each step is answered by the next reading, the way the client
            # reports every 10 tick: the first answer is "still on the ground".
            if message_type == AIM_INPUT_TYPE and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.collect_dropped(
            item_id="minecraft:oak_log",
            authority=authority(),
            walk_seconds=0.0,
            timeout_ns=10_000_000_000,
        )

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.pre_tick == 100
        assert outcome.post_tick == 120
        assert outcome.details["steps"] == "2"
        # Two steps, and each one of them stopped: a chase that left the key
        # down would be a Kin still walking when it reports.
        assert sender.types().count(AIM_INPUT_TYPE) == 2
        moves = [
            message for message_type, message in sender.sent if message_type == MOVE_INPUT_TYPE
        ]
        assert [message.forward for message in moves] == [1.0, 0.0, 1.0, 0.0]  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_collect_reports_that_no_newer_reading_arrived_when_the_channel_was_silent() -> None:
    async def scenario() -> None:
        store = store_with(
            reading(
                tick=100,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=100),),
            )
        )
        skills, _sender = skill_with(store)

        outcome = await skills.collect_dropped(
            item_id="minecraft:oak_log",
            authority=authority(),
            walk_seconds=0.0,
            timeout_ns=50_000_000,
        )

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"
        assert outcome.post_tick is None
        # The newest reading it concluded on is the pre-state itself: nothing
        # newer ever arrived, which is the channel's silence and not the world's.
        assert outcome.details == {"steps": "1", "newest_checked_tick": "100"}

    asyncio.run(scenario())


def test_collect_reports_the_frames_a_failed_chase_did_look_at() -> None:
    async def scenario() -> None:
        store = store_with(
            reading(
                tick=100,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=100),),
            )
        )
        skills, sender = skill_with(store)
        next_tick = 110

        def answer(message_type: str) -> None:
            # Readings keep arriving and the drop keeps being visible with the
            # inventory on the same revision: nothing here has been picked up,
            # and that is a different story from a silent channel.
            nonlocal next_tick
            if message_type != AIM_INPUT_TYPE:
                return
            store.admit(
                reading(
                    tick=next_tick,
                    inventory_value=inventory(100),
                    entities=(oak_log_drop(tick=next_tick),),
                ),
                (),
            )
            next_tick += 10

        sender.on_send = answer
        outcome = await skills.collect_dropped(
            item_id="minecraft:oak_log",
            authority=authority(),
            walk_seconds=0.0,
            timeout_ns=1_500_000_000,
        )

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"
        assert int(outcome.details["steps"]) >= 2
        assert int(outcome.details["newest_checked_tick"]) > 100

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# craft: one click, materials proven from the synced inventory
# ---------------------------------------------------------------------------


def test_craft_refuses_when_the_synced_inventory_is_short_of_materials() -> None:
    async def scenario() -> None:
        store = store_with(
            reading(tick=100, inventory_value=inventory(100, (0, PLANKS, 1))),
        )
        skills, sender = skill_with(store)

        outcome = await skills.craft(
            recipe_id="wooden_pickaxe",
            materials={PLANKS: 3, "minecraft:stick": 2},
            product_id=PICKAXE,
            authority=authority(),
        )
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "CRAFT_MATERIALS_MISSING"
        assert sender.sent == []

    asyncio.run(scenario())


def test_craft_never_retries_an_inconclusive_click() -> None:
    """One GuiClickInput, however many readings arrive while the window runs and
    none of them confirm: the contract's answer to an inconclusive side-effecting
    click is the word `unknown`, and a second click would be indistinguishable
    from having crafted the pickaxe twice."""

    async def scenario() -> None:
        loaded = inventory(100, (0, PLANKS, 6), (1, "minecraft:stick", 2))
        store = store_with(
            reading(
                tick=100,
                inventory_value=loaded,
                gui=GuiScreenValue(screen_id="crafting", sync_id=3),
            )
        )
        skills, sender = skill_with(store)
        unchanged = reading(
            tick=110,
            inventory_value=inventory(110, (0, PLANKS, 6), (1, "minecraft:stick", 2)),
            gui=GuiScreenValue(screen_id="crafting", sync_id=3),
        )

        task = asyncio.create_task(admit_later(store, unchanged))
        outcome = await skills.craft(
            recipe_id="wooden_pickaxe",
            materials={PLANKS: 3, "minecraft:stick": 2},
            product_id=PICKAXE,
            authority=authority(),
            timeout_ns=600_000_000,
        )
        await task

        assert outcome.result is ActionResultClass.UNKNOWN
        clicks = [
            message_type for message_type, _ in sender.sent if message_type == GUI_CLICK_INPUT_TYPE
        ]
        assert len(clicks) == 1

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# select_hotbar: the §4 row's sender, refusing the tenth slot before the wire
# ---------------------------------------------------------------------------


def test_hotbar_selection_outside_the_nine_is_refused_before_the_wire() -> None:
    async def scenario() -> None:
        store = store_with(reading())
        skills, sender = skill_with(store)

        outcome = await skills.select_hotbar(slot=9, authority=authority())
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "HOTBAR_SLOT_OUT_OF_RANGE"
        assert sender.sent == []

    asyncio.run(scenario())


def test_hotbar_selection_confirms_from_the_next_self_reading() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100, state_value=state(yaw=0.0, pitch=0.0)))
        # selected_slot lives on the state; rebuild with the slot the pre-hand has.
        pre = store.latest
        assert pre is not None
        store_with_aim = store  # same store; the skill reads latest itself
        skills, sender = skill_with(store_with_aim)
        after = reading(
            tick=110,
            state_value=SelfStateValue(
                health=20.0,
                max_health=20.0,
                food=20,
                saturation=5.0,
                alive=True,
                selected_slot=4,
                main_hand_item_id="minecraft:stone",
            ),
        )

        task = asyncio.create_task(admit_later(store, after))
        outcome = await skills.select_hotbar(
            slot=4, authority=authority(), timeout_ns=2_000_000_000
        )
        await task

        assert outcome.result is ActionResultClass.CONFIRMED
        assert sender.types()[0] == "minekin.v1.HotbarSelectInput"

    asyncio.run(scenario())
