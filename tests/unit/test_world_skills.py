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
from typing import Final, cast

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
    SCREEN_INPUT_TYPE,
    monotonic_ns,
)
from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.application.world_skills import (
    CLOSE_SCREEN_MAX_ESCAPES,
    ActionAuthority,
    ClientProcessExited,
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
from minekin_core.generated.minekin.v1 import control_pb2

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
LOG = "minecraft:oak_log"
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


async def admit_after(
    store: WorldObservationStore, delay: float, value: WorldObservationValue
) -> None:
    await asyncio.sleep(delay)
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
            await skills.craft_take_result(
                recipe_id="r", materials={PLANKS: 1}, product_id=PLANKS, authority=lease
            ),
            await skills.close_screen(authority=lease),
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


def test_craft_names_channel_silence_as_the_reason_a_click_was_left_unconfirmed() -> None:
    async def scenario() -> None:
        loaded = inventory(100, (0, PLANKS, 6), (1, "minecraft:stick", 2))
        store = store_with(
            reading(
                tick=100,
                inventory_value=loaded,
                gui=GuiScreenValue(screen_id="crafting", sync_id=3),
            )
        )
        skills, _sender = skill_with(store)

        outcome = await skills.craft(
            recipe_id="wooden_pickaxe",
            materials={PLANKS: 3, "minecraft:stick": 2},
            product_id=PICKAXE,
            authority=authority(),
            timeout_ns=50_000_000,
        )

        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"
        # The newest reading it concluded on is its own pre-state: nothing newer
        # ever reached the skill, which is the client's silence.
        assert outcome.details == {
            "newest_checked_tick": "100",
            "pre_inventory_revision": "100",
            "newest_inventory_revision": "100",
            "gui_open": "true",
            "craft_all": "true",
        }

    asyncio.run(scenario())


def test_craft_names_a_channel_that_kept_reporting_without_resyncing_the_inventory() -> None:
    """The other half of the same question, and the one the demo actually needs:
    frames arriving all the way through the window whose synced revision never
    moves. `verify_craft` may only conclude on a rise in that revision, so this
    is the reading that says the answer is on the client's inventory sync, not in
    the tick rate or the perception gate."""

    async def scenario() -> None:
        loaded = inventory(100, (0, PLANKS, 6), (1, "minecraft:stick", 2))
        store = store_with(
            reading(
                tick=100,
                inventory_value=loaded,
                gui=GuiScreenValue(screen_id="crafting", sync_id=3),
            )
        )
        skills, _sender = skill_with(store)
        reporting = reading(
            tick=110,
            inventory_value=inventory(100, (0, PLANKS, 6), (1, "minecraft:stick", 2)),
            gui=GuiScreenValue(screen_id="crafting", sync_id=3),
        )

        task = asyncio.create_task(admit_later(store, reporting))
        outcome = await skills.craft(
            recipe_id="wooden_pickaxe",
            materials={PLANKS: 3, "minecraft:stick": 2},
            product_id=PICKAXE,
            authority=authority(),
            timeout_ns=600_000_000,
        )
        await task

        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"
        assert outcome.details["newest_checked_tick"] == "110"
        assert outcome.details["pre_inventory_revision"] == "100"
        assert outcome.details["newest_inventory_revision"] == "100"

    asyncio.run(scenario())


def test_craft_reports_the_window_was_never_seen_open() -> None:
    async def scenario() -> None:
        loaded = inventory(100, (0, PLANKS, 6), (1, "minecraft:stick", 2))
        store = store_with(reading(tick=100, inventory_value=loaded))
        skills, sender = skill_with(store)

        outcome = await skills.craft(
            recipe_id="wooden_pickaxe",
            materials={PLANKS: 3, "minecraft:stick": 2},
            product_id=PICKAXE,
            authority=authority(),
            timeout_ns=50_000_000,
        )

        assert outcome.reason == "SCREEN_NOT_CONFIRMED"
        # The screen open went out and no reading ever reported a window, so no
        # recipe click was sent — and `gui_open` says which of the two ends of
        # the craft's window this failure sits at.
        assert outcome.details["gui_open"] == "false"
        assert outcome.details["newest_checked_tick"] == "100"
        assert GUI_CLICK_INPUT_TYPE not in [message_type for message_type, _ in sender.sent]

    asyncio.run(scenario())


def test_craft_sends_the_click_that_leaves_the_result_in_the_inventory() -> None:
    """The default is the transaction that finishes the job.

    A plain recipe click is the recipe book's single pick: it leaves one result on
    the cursor, and the cursor is not part of the synced inventory the Kin reads.
    A window spent on that click can watch the materials fall and still never see a
    product, which is the shape the demo kept reporting. The craft-all click is the
    one whose result lands where the next reading can find it."""

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

        await skills.craft(
            recipe_id="wooden_pickaxe",
            materials={PLANKS: 3, "minecraft:stick": 2},
            product_id=PICKAXE,
            authority=authority(),
            timeout_ns=50_000_000,
        )

        clicks = [
            message for message_type, message in sender.sent if message_type == GUI_CLICK_INPUT_TYPE
        ]
        assert len(clicks) == 1
        assert cast(control_pb2.GuiClickInput, clicks[0]).recipe.craft_all is True

    asyncio.run(scenario())


def test_a_caller_can_ask_for_the_single_pick_and_the_run_says_which_went_out() -> None:
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

        outcome = await skills.craft(
            recipe_id="wooden_pickaxe",
            materials={PLANKS: 3, "minecraft:stick": 2},
            product_id=PICKAXE,
            authority=authority(),
            craft_all=False,
            timeout_ns=50_000_000,
        )

        clicks = [
            message for message_type, message in sender.sent if message_type == GUI_CLICK_INPUT_TYPE
        ]
        assert cast(control_pb2.GuiClickInput, clicks[0]).recipe.craft_all is False
        assert outcome.details["craft_all"] == "false"

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# craft_take_result: the fill click, the result-slot click, and — only if a
# reading says the product is stuck out of the synced inventory — the click
# that empties the cursor into a slot the reading says is empty.
# ---------------------------------------------------------------------------


def _player_screen_store(*pairs: tuple[int, str, int]) -> WorldObservationStore:
    return store_with(
        reading(
            tick=100,
            inventory_value=inventory(100, *pairs),
            gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
        )
    )


def _gui_clicks(sender: RecordingSender) -> list[control_pb2.GuiClickInput]:
    return [
        cast(control_pb2.GuiClickInput, message)
        for message_type, message in sender.sent
        if message_type == GUI_CLICK_INPUT_TYPE
    ]


def test_craft_take_result_refuses_before_the_wire_when_materials_are_short() -> None:
    async def scenario() -> None:
        store = _player_screen_store((0, PLANKS, 1))
        skills, sender = skill_with(store)

        outcome = await skills.craft_take_result(
            recipe_id="oak_planks",
            materials={LOG: 1},
            product_id=PLANKS,
            authority=authority(),
        )
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "CRAFT_MATERIALS_MISSING"
        assert sender.sent == []

    asyncio.run(scenario())


def test_craft_take_result_confirms_from_the_quick_move_alone_when_the_product_arrives() -> None:
    """The transaction that the plain recipe click never finished: fill through
    the recipe book, then shift-click result slot 0. When the shift-click puts
    the product where the synced reading can see it, there is nothing to deposit
    and the skill sends exactly two clicks."""

    async def scenario() -> None:
        store = _player_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)
        fill = reading(
            tick=110,
            inventory_value=inventory(101),
            gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
        )
        done = reading(
            tick=120,
            inventory_value=inventory(102, (0, PLANKS, 4)),
            gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
        )
        first = asyncio.create_task(admit_after(store, 0.01, fill))
        second = asyncio.create_task(admit_after(store, 0.05, done))

        outcome = await skills.craft_take_result(
            recipe_id="oak_planks",
            materials={LOG: 1},
            product_id=PLANKS,
            authority=authority(),
            timeout_ns=2_000_000_000,
        )
        await first
        await second

        assert outcome.result is ActionResultClass.CONFIRMED
        clicks = _gui_clicks(sender)
        assert len(clicks) == 2
        assert clicks[0].recipe.craft_all is False
        assert clicks[0].recipe.recipe_id == "oak_planks"
        assert clicks[1].slot.slot_id == 0
        assert clicks[1].slot.mode == control_pb2.SLOT_CLICK_MODE_QUICK_MOVE

    asyncio.run(scenario())


def test_craft_take_result_deposits_a_product_the_reading_says_is_stuck_outside_the_inventory() -> (
    None
):
    """The §5.10 shape: materials fell and no frame ever shows the product. That
    is the cursor, and the synced inventory cannot see it — so one left-click on
    a slot the newest reading says is empty puts it where the next reading can.
    The deposit goes to the first empty slot in the nine the player already
    counts in the same coordinates the reading reports, mapped into the open
    screen's numbering."""

    async def scenario() -> None:
        store = _player_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)
        fill = reading(
            tick=110,
            inventory_value=inventory(101),
            gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
        )
        still_stuck = reading(
            tick=120,
            inventory_value=inventory(102),
            gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
        )
        deposited = reading(
            tick=130,
            inventory_value=inventory(103, (0, PLANKS, 4)),
            gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
        )
        tasks = [
            asyncio.create_task(admit_after(store, 0.01, fill)),
            asyncio.create_task(admit_after(store, 0.05, still_stuck)),
            asyncio.create_task(admit_after(store, 0.10, deposited)),
        ]

        outcome = await skills.craft_take_result(
            recipe_id="oak_planks",
            materials={LOG: 1},
            product_id=PLANKS,
            authority=authority(),
            timeout_ns=2_000_000_000,
        )
        for task in tasks:
            await task

        assert outcome.result is ActionResultClass.CONFIRMED
        clicks = _gui_clicks(sender)
        assert len(clicks) == 3
        assert clicks[2].slot.slot_id == 32
        assert clicks[2].slot.mode == control_pb2.SLOT_CLICK_MODE_PICK
        assert clicks[2].slot.button == 0
        assert outcome.details["deposit_slot"] == "32"

    asyncio.run(scenario())


def test_craft_take_result_refuses_a_deposit_click_when_no_slot_is_read_empty() -> None:
    """Clicking a slot the reading does not say is empty would trade the cursor
    for whatever stands there. With the nine and the twenty-seven all occupied,
    the skill stops at two clicks and names why."""

    async def scenario() -> None:
        occupied = tuple((slot, "minecraft:stone", 1) for slot in range(1, 36))
        every_slot = tuple((slot, "minecraft:stone", 1) for slot in range(36))
        store = _player_screen_store((0, LOG, 1), *occupied)
        skills, sender = skill_with(store)
        fill = reading(
            tick=110,
            inventory_value=inventory(101, *every_slot),
            gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
        )
        stuck = reading(
            tick=120,
            inventory_value=inventory(102, *every_slot),
            gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
        )
        tasks = [
            asyncio.create_task(admit_after(store, 0.01, fill)),
            asyncio.create_task(admit_after(store, 0.05, stuck)),
        ]

        outcome = await skills.craft_take_result(
            recipe_id="oak_planks",
            materials={LOG: 1},
            product_id=PLANKS,
            authority=authority(),
            timeout_ns=2_000_000_000,
        )
        for task in tasks:
            await task

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "CRAFT_NO_EMPTY_SLOT"
        assert len(_gui_clicks(sender)) == 2

    asyncio.run(scenario())


def test_craft_take_result_reports_silence_without_a_second_click() -> None:
    async def scenario() -> None:
        store = _player_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)

        outcome = await skills.craft_take_result(
            recipe_id="oak_planks",
            materials={LOG: 1},
            product_id=PLANKS,
            authority=authority(),
            timeout_ns=50_000_000,
        )

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"
        clicks = _gui_clicks(sender)
        assert len(clicks) == 1
        assert outcome.details["newest_checked_tick"] == "100"

    asyncio.run(scenario())


def test_craft_take_result_stops_when_the_window_closes_after_the_fill_click() -> None:
    async def scenario() -> None:
        store = _player_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)
        closed = reading(tick=110, inventory_value=inventory(101))
        task = asyncio.create_task(admit_later(store, closed))

        outcome = await skills.craft_take_result(
            recipe_id="oak_planks",
            materials={LOG: 1},
            product_id=PLANKS,
            authority=authority(),
            timeout_ns=2_000_000_000,
        )
        await task

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "SCREEN_NOT_CONFIRMED"
        assert outcome.details["gui_open"] == "false"
        assert len(_gui_clicks(sender)) == 1

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


# ---------------------------------------------------------------------------
# close_screen: the window the craft left open is closed by the player's own
# escape, and only a reading that reports no handler confirms it
# ---------------------------------------------------------------------------


def _open_screen_store(*pairs: tuple[int, str, int]) -> WorldObservationStore:
    """The player's own 2x2 window, open, at tick 100 — the state every craft
    skill ends in and no skill so far had a way out of."""

    return store_with(
        reading(
            tick=100,
            inventory_value=inventory(101, *pairs),
            gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=3),
        )
    )


def test_close_screen_confirms_only_from_a_reading_that_reports_no_window() -> None:
    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)
        closed = reading(tick=110, inventory_value=inventory(102, (0, LOG, 1)))
        task = asyncio.create_task(admit_later(store, closed))

        outcome = await skills.close_screen(authority=authority(), timeout_ns=2_000_000_000)
        await task

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 110
        assert outcome.details["screen_open"] == "false"
        assert outcome.details["pre_sync_id"] == "3"
        assert outcome.details["newest_sync_id"] == ""
        assert sender.types() == [SCREEN_INPUT_TYPE]
        command = sender.sent[0][1]
        assert isinstance(command, control_pb2.ScreenInput)
        assert command.control == control_pb2.SCREEN_CONTROL_CLOSE

    asyncio.run(scenario())


def test_closing_a_window_is_not_a_click_and_needs_no_click_capability() -> None:
    """The guard is the screen's, not the GUI's: an escape that lands while no
    container is open touches nothing, so a Kin that was never granted the click
    capability can still stop holding the window it is standing in."""

    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        skills, sender = skill_with(store, capabilities=frozenset({SCREEN_CAPABILITY}))
        closed = reading(tick=110, inventory_value=inventory(102, (0, LOG, 1)))
        task = asyncio.create_task(admit_later(store, closed))

        outcome = await skills.close_screen(authority=authority(), timeout_ns=2_000_000_000)
        await task

        assert outcome.result is ActionResultClass.CONFIRMED
        assert sender.types() == [SCREEN_INPUT_TYPE]

    asyncio.run(scenario())


def test_close_screen_says_the_window_was_already_out_of_the_way() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100, inventory_value=inventory(101)))
        skills, sender = skill_with(store)

        outcome = await skills.close_screen(authority=authority(), timeout_ns=50_000_000)

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.reason == ""
        assert outcome.details["screen_open"] == "false"
        assert outcome.details["already_closed"] == "true"
        assert sender.sent == []

    asyncio.run(scenario())


def test_close_screen_reports_channel_silence_as_no_confirming_observation() -> None:
    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)

        outcome = await skills.close_screen(authority=authority(), timeout_ns=50_000_000)

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"
        assert outcome.details["screen_open"] == "true"
        assert outcome.details["newest_checked_tick"] == "100"
        assert outcome.details["pre_sync_id"] == "3"
        assert outcome.details["newest_sync_id"] == "3"
        assert sender.types() == [SCREEN_INPUT_TYPE]

    asyncio.run(scenario())


def test_close_screen_fails_when_every_later_reading_still_reports_the_window() -> None:
    """A frame that arrives and says the window is still there is not silence:
    it is the reading that contradicts the escape, and §4 lets the skill say so.

    One escape that a frame contradicts is not enough to conclude on — the client
    may still have been mid-frame — so the skill re-sends the same player's key
    while frames keep arriving that still show the window, and concludes
    `SCREEN_STILL_OPEN` only once the frames it has seen have all contradicted it
    and no newer one is coming inside the window.
    """

    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)
        still = reading(
            tick=110,
            inventory_value=inventory(102, (0, LOG, 1)),
            gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=3),
        )
        task = asyncio.create_task(admit_later(store, still))

        outcome = await skills.close_screen(authority=authority(), timeout_ns=200_000_000)
        await task

        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "SCREEN_STILL_OPEN"
        assert outcome.details["newest_screen_id"] == "minecraft:crafting"
        assert outcome.details["newest_sync_id"] == "3"
        # The contradicting frame bought exactly one more escape, then silence ended
        # the listening — two sends, both the same player's key, no other action.
        assert sender.types() == [SCREEN_INPUT_TYPE, SCREEN_INPUT_TYPE]
        assert all(
            command.control == control_pb2.SCREEN_CONTROL_CLOSE for _, command in sender.sent
        )

    asyncio.run(scenario())


def test_close_screen_recovers_when_a_second_escape_lands_after_a_contradicting_frame() -> None:
    """The recovery this fix exists for: the first frame still reports the window,
    the next one after a re-sent escape reports it gone, and that is a close — not a
    `SCREEN_STILL_OPEN` earned by concluding on the first contradiction."""

    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)

        def answer(message_type: str) -> None:
            escapes = len(sender.types())
            if escapes == 1:
                # The first escape is contradicted by the next frame.
                store.admit(
                    reading(
                        tick=110,
                        inventory_value=inventory(102, (0, LOG, 1)),
                        gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=3),
                    ),
                    (),
                )
            else:
                # The re-sent escape lands: a newer reading reports no handler.
                store.admit(reading(tick=120, inventory_value=inventory(103, (0, LOG, 1))), ())

        sender.on_send = answer
        outcome = await skills.close_screen(authority=authority(), timeout_ns=2_000_000_000)

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 120
        assert outcome.details["screen_open"] == "false"
        assert outcome.details["escapes"] == "2"
        assert sender.types() == [SCREEN_INPUT_TYPE, SCREEN_INPUT_TYPE]

    asyncio.run(scenario())


def test_close_screen_stops_re_sending_the_escape_after_a_bounded_number() -> None:
    """The re-send is bounded: a window that every frame keeps reporting is not
    escaped by an endless drum of the same key, and the step concludes rather than
    spending its whole lease holding it."""

    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)

        def contradict(message_type: str) -> None:
            tick = 101 + len(sender.types())
            store.admit(
                reading(
                    tick=tick,
                    inventory_value=inventory(101 + tick - 100, (0, LOG, 1)),
                    gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=3),
                ),
                (),
            )

        sender.on_send = contradict
        outcome = await skills.close_screen(authority=authority(), timeout_ns=2_000_000_000)

        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "SCREEN_STILL_OPEN"
        assert outcome.details["escapes"] == str(CLOSE_SCREEN_MAX_ESCAPES)
        assert sender.types() == [SCREEN_INPUT_TYPE] * CLOSE_SCREEN_MAX_ESCAPES

    asyncio.run(scenario())


def test_an_unnamed_window_is_still_a_window_the_close_has_to_answer_for() -> None:
    """The live shape the names cannot describe on their own.

    The client reports the player's own crafting window with an empty `screen_id`
    and a present handler id, so an empty name is not evidence of an empty screen —
    and a skill that concluded from `screen_id` alone would confirm a close that
    never happened. The handler id is what the row has to carry.
    """

    async def scenario() -> None:
        store = store_with(
            reading(
                tick=100,
                inventory_value=inventory(101, (0, LOG, 1)),
                gui=GuiScreenValue(screen_id="", sync_id=7),
            )
        )
        skills, sender = skill_with(store)
        still = reading(
            tick=110,
            inventory_value=inventory(102, (0, LOG, 1)),
            gui=GuiScreenValue(screen_id="", sync_id=7),
        )
        task = asyncio.create_task(admit_later(store, still))

        outcome = await skills.close_screen(authority=authority(), timeout_ns=200_000_000)
        await task

        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "SCREEN_STILL_OPEN"
        assert outcome.details["screen_open"] == "true"
        assert outcome.details["newest_screen_id"] == ""
        assert outcome.details["newest_sync_id"] == "7"
        assert sender.types() == [SCREEN_INPUT_TYPE, SCREEN_INPUT_TYPE]

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# The client's own exit, asked beside the readings
# ---------------------------------------------------------------------------


class ClientAnswer:
    """The supervisor's answer about the child process, changed by hand.

    `None` is a client that runs; a number is one the operating system has already
    finished. This is not the world's word — the readings still decide every verdict,
    and it only says whether a reading can still arrive at all.
    """

    def __init__(self, code: int | None = None) -> None:
        self.code = code

    def __call__(self) -> int | None:
        return self.code

    def go_after(self, delay: float, code: int) -> None:
        asyncio.get_running_loop().call_later(delay, self._set, code)

    def _set(self, code: int) -> None:
        self.code = code


def skills_with_client(store: WorldObservationStore, client: ClientAnswer) -> WorldSkills:
    return WorldSkills(
        sender=RecordingSender(),
        observations=store,
        capabilities=ALL_CAPABILITIES,
        client_exit=client,
    )


def test_the_skills_answer_what_the_supervisor_said_about_the_client() -> None:
    assert skills_with_client(store_with(reading()), ClientAnswer(143)).client_exit_code() == 143
    assert skills_with_client(store_with(reading()), ClientAnswer()).client_exit_code() is None


def test_a_step_that_loses_its_client_while_waiting_names_the_exit() -> None:
    """The wait is raced, not replaced: a client that exits ends it by name.

    The step timeout here is a minute and no reading ever comes, because the process
    that would have made it is gone. A skill that could not see that would spend the
    whole window concluding about a silence it had a named reason for.
    """

    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        client = ClientAnswer()
        skills = skills_with_client(store, client)
        client.go_after(0.02, 137)
        started = monotonic_ns()

        raised: ClientProcessExited | None = None
        try:
            await skills.close_screen(authority=authority(), timeout_ns=60_000_000_000)
        except ClientProcessExited as exit_error:
            raised = exit_error

        assert raised is not None
        assert raised.exit_code == 137
        assert monotonic_ns() - started < 10_000_000_000

    asyncio.run(scenario())


def test_a_step_refuses_to_wait_at_all_when_the_client_is_already_gone() -> None:
    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        sender = RecordingSender()
        skills = WorldSkills(
            sender=sender,
            observations=store,
            capabilities=ALL_CAPABILITIES,
            client_exit=ClientAnswer(1),
        )

        raised: ClientProcessExited | None = None
        try:
            await skills.close_screen(authority=authority(), timeout_ns=60_000_000_000)
        except ClientProcessExited as exit_error:
            raised = exit_error

        assert raised is not None
        assert raised.exit_code == 1
        # The ask still went out: this is the wait giving up, not a refusal to act.
        assert sender.types() == [SCREEN_INPUT_TYPE]

    asyncio.run(scenario())


def test_a_live_client_leaves_a_silent_step_to_its_own_deadline() -> None:
    """The watch is inert while the process runs, so the readings still decide."""

    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        skills = skills_with_client(store, ClientAnswer())

        outcome = await skills.close_screen(authority=authority(), timeout_ns=50_000_000)

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"

    asyncio.run(scenario())


def test_a_client_that_exits_ends_a_chase_that_keeps_getting_readings() -> None:
    """Not only a silent channel: a step whose world is moving stops on its client.

    `collect_dropped` re-steps toward a drop it can still see, so its wait is answered
    by reading after reading. The exit has to interrupt that too, or a Kin would walk
    after a log for the length of the window with nobody driving the client.
    """

    async def scenario() -> None:
        store = store_with(
            reading(tick=100, inventory_value=inventory(100), entities=(oak_log_drop(tick=100),))
        )
        client = ClientAnswer()
        skills = skills_with_client(store, client)
        client.go_after(0.06, 143)

        async def feed() -> None:
            for tick in range(101, 140):
                await asyncio.sleep(0.01)
                store.admit(
                    reading(
                        tick=tick,
                        inventory_value=inventory(tick),
                        entities=(oak_log_drop(tick=tick),),
                    ),
                    (),
                )

        feeding = asyncio.create_task(feed())

        raised: ClientProcessExited | None = None
        try:
            await skills.collect_dropped(
                item_id=LOG, authority=authority(), walk_seconds=0.01, timeout_ns=60_000_000_000
            )
        except ClientProcessExited as exit_error:
            raised = exit_error
        await feeding

        assert raised is not None
        assert raised.exit_code == 143

    asyncio.run(scenario())


def test_the_exit_names_the_ask_that_was_in_flight_when_the_client_went() -> None:
    """The step's own id travels with the exit, because it is not a guess.

    Core made that id and the command carrying it had already left for the client, so
    a row that reports the exit without it drops a fact this process still holds — and
    the reader cannot tell "waiting on a click that went out" from "waiting before
    anything was sent", which are different worlds of a run.
    """

    async def scenario() -> None:
        store = _open_screen_store((0, LOG, 1))
        sender = RecordingSender()
        client = ClientAnswer()
        skills = WorldSkills(
            sender=sender,
            observations=store,
            capabilities=ALL_CAPABILITIES,
            client_exit=client,
        )
        client.go_after(0.02, 143)

        raised: ClientProcessExited | None = None
        try:
            await skills.close_screen(authority=authority(), timeout_ns=60_000_000_000)
        except ClientProcessExited as exit_error:
            raised = exit_error

        assert raised is not None
        assert sender.types() == [SCREEN_INPUT_TYPE]
        command = sender.sent[0][1]
        assert isinstance(command, control_pb2.ScreenInput)
        assert raised.action_id == command.action_id
        assert raised.action_id != ""

    asyncio.run(scenario())
