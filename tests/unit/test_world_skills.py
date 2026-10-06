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
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final, cast

import pytest
from google.protobuf.message import Message

from minekin_core.adapters.bridge.ipc import (
    AIM_CAPABILITY,
    AIM_INPUT_TYPE,
    GUI_CAPABILITY,
    GUI_CLICK_INPUT_TYPE,
    HOTBAR_CAPABILITY,
    HOTBAR_SELECT_INPUT_TYPE,
    MINE_CAPABILITY,
    MINE_INPUT_TYPE,
    MOVE_CAPABILITY,
    MOVE_INPUT_TYPE,
    SCREEN_CAPABILITY,
    SCREEN_INPUT_TYPE,
    USE_CAPABILITY,
    USE_INPUT_TYPE,
    monotonic_ns,
)
from minekin_core.application.skill_plan import perform_skill
from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.application.world_skills import (
    CLOSE_SCREEN_MAX_ESCAPES,
    COLLECT_MAX_STALLED_CORRECTIONS,
    EYE_HEIGHT_BLOCKS,
    ActionAuthority,
    ClientProcessExited,
    SessionStopRequested,
    SkillCall,
    WorldSkills,
)
from minekin_core.domain.control_vocabulary import RESPAWN_CAPABILITY, RESPAWN_INPUT_TYPE
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
    TradeOfferValue,
    WorldObservationValue,
)
from minekin_core.domain.world_actions import ActionResultClass, angle_to_degrees
from minekin_core.generated.minekin.v1 import control_pb2

ALL_CAPABILITIES: Final = frozenset(
    {
        AIM_CAPABILITY,
        MINE_CAPABILITY,
        HOTBAR_CAPABILITY,
        SCREEN_CAPABILITY,
        GUI_CAPABILITY,
        MOVE_CAPABILITY,
        USE_CAPABILITY,
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


def merchant_gui(*, sync_id: int = 4) -> GuiScreenValue:
    return GuiScreenValue(
        screen_id="minecraft:merchant",
        sync_id=sync_id,
        trade_offers=(
            TradeOfferValue(
                first_item_id="minecraft:emerald",
                first_count=3,
                second_item_id="",
                second_count=0,
                sell_item_id="minecraft:bread",
                sell_count=2,
                uses=4,
                max_uses=12,
                disabled=False,
            ),
            TradeOfferValue(
                first_item_id="minecraft:wheat",
                first_count=20,
                second_item_id="minecraft:emerald",
                second_count=1,
                sell_item_id="minecraft:emerald",
                sell_count=1,
                uses=0,
                max_uses=16,
                disabled=False,
            ),
        ),
    )


def slime_aim(tick: int, entity_id: str = "slime-100") -> AimTargetValue:
    return AimTargetValue(
        game_tick=tick,
        kind=AimKind.ENTITY,
        entity_observation_id=entity_id,
        entity_type="minecraft:slime" if entity_id.startswith("slime") else "",
        distance=2.0,
    )


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
            await skills.use_target(authority=lease),
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
            item_id="minecraft:oak_log",
            authority=authority(),
            walk_seconds=0.0,
            timeout_ns=50_000_000,
        )
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "NO_SEEN_DROP"
        assert sender.sent == []

    asyncio.run(scenario())


def test_collect_waits_a_short_settle_for_a_felled_drop_to_register_before_refusing() -> None:
    async def scenario() -> None:
        # The failure a real run ended on: the `break` CONFIRMED on the same tick, so the
        # very next frame had not yet rendered the item, and the old `collect` refused
        # without ever stepping. A bounded settle for the newer reading that does report
        # the drop turns that instant refusal into the walk the item was about to get.
        drop_arrives = reading(
            tick=110,
            inventory_value=inventory(100),
            entities=(oak_log_drop(tick=110, distance=2.0),),
        )
        came_away = reading(
            tick=120,
            inventory_value=inventory(120, (0, "minecraft:oak_log", 1)),
            entities=(),
        )
        store = store_with(reading(tick=100, inventory_value=inventory(100), entities=()))
        skills, sender = skill_with(store)
        queued = [came_away]

        def answer(message_type: str) -> None:
            if message_type == AIM_INPUT_TYPE and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        # The item registers a beat after the break, exactly as the run reported it.
        arrival = asyncio.create_task(admit_later(store, drop_arrives))
        try:
            outcome = await skills.collect_dropped(
                item_id="minecraft:oak_log",
                authority=authority(),
                walk_seconds=0.0,
                timeout_ns=10_000_000_000,
            )
        finally:
            await arrival

        assert outcome.result is ActionResultClass.CONFIRMED
        # The settled, newer reading — not the empty first frame — is what it chased, and
        # it stepped toward the drop rather than refusing (the whole point of the settle).
        assert outcome.pre_tick == 110
        assert outcome.post_tick == 120
        assert sender.types().count(AIM_INPUT_TYPE) >= 1

    asyncio.run(scenario())


def test_collect_settle_spans_a_full_report_cadence_before_refusing() -> None:
    async def scenario() -> None:
        # The Bridge publishes on a 10-tick cadence (~500 ms), so the frame that first
        # renders a felled drop can land a full report period after the break CONFIRMED.
        # An earlier settle window shorter than that cadence returned before this reading
        # was admitted, refused NO_SEEN_DROP on the stale tick, and starved the autonomous
        # loop into NO_FRESH_OBSERVATION before the mind could re-aim. The settle now clears
        # the cadence, so a drop that registers on the second frame is still caught.
        drop_arrives = reading(
            tick=110,
            inventory_value=inventory(100),
            entities=(oak_log_drop(tick=110, distance=2.0),),
        )
        came_away = reading(
            tick=120,
            inventory_value=inventory(120, (0, "minecraft:oak_log", 1)),
            entities=(),
        )
        store = store_with(reading(tick=100, inventory_value=inventory(100), entities=()))
        skills, sender = skill_with(store)
        queued = [came_away]

        def answer(message_type: str) -> None:
            if message_type == AIM_INPUT_TYPE and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        # A whole report period after the break — past the old 400 ms window, inside the
        # cadence-spanning one — the item finally appears on the visible list.
        arrival = asyncio.create_task(admit_after(store, 0.6, drop_arrives))
        try:
            outcome = await skills.collect_dropped(
                item_id="minecraft:oak_log",
                authority=authority(),
                walk_seconds=0.0,
                timeout_ns=10_000_000_000,
            )
        finally:
            await arrival

        assert outcome.result is ActionResultClass.CONFIRMED
        # The settled second-cadence reading is what it chased, not the empty first frame.
        assert outcome.pre_tick == 110
        assert outcome.post_tick == 120

    asyncio.run(scenario())


def oak_log_drop(*, tick: int, distance: float = 2.0, vertical: float = 0.0) -> EntityCandidate:
    return EntityCandidate(
        observation_id=f"drop-{tick}",
        entity_type="item",
        relative_x=0.0,
        relative_y=vertical,
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
        assert outcome.details == {
            "steps": "1",
            "newest_checked_tick": "100",
            "nearest_drop_horizontal_meters": "2.000",
            "nearest_drop_vertical_meters": "0.000",
        }

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
            # Readings keep arriving and the drop keeps being reported at the SAME
            # distance with the inventory on the same revision: the walk is not
            # closing on it. That is a stalled approach, not a silent channel, and
            # not a chase worth firing into a wall until the window runs out.
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
            timeout_ns=3_000_000_000,
        )

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "COLLECT_APPROACH_STALLED"
        # Bounded: it stops after the corrections that failed to close, not after the
        # whole window; and the step count says exactly how many walks it fired.
        assert int(outcome.details["steps"]) == COLLECT_MAX_STALLED_CORRECTIONS
        assert int(outcome.details["newest_checked_tick"]) > 100

    asyncio.run(scenario())


def test_collect_stops_when_the_reachable_drop_leaves_the_client_view() -> None:
    """The drop went out of the client's own render without a synced inventory rise,
    so nothing confirms the pickup and nothing is left to aim at. Concluding here,
    instead of standing and listening out the window, is what lets the mind re-scan.
    """

    async def scenario() -> None:
        store = store_with(
            reading(
                tick=100,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=100),),
            )
        )
        skills, sender = skill_with(store)

        def answer(message_type: str) -> None:
            if message_type != AIM_INPUT_TYPE:
                return
            # A newer tick with the item gone, on the SAME revision — neither a
            # confirmed rise nor a confirmed loss, so the reading cannot settle it.
            store.admit(reading(tick=110, inventory_value=inventory(100), entities=()), ())

        sender.on_send = answer
        outcome = await skills.collect_dropped(
            item_id="minecraft:oak_log",
            authority=authority(),
            walk_seconds=0.0,
            timeout_ns=1_500_000_000,
        )

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "DROP_OUT_OF_VIEW"
        assert outcome.details == {"steps": "1", "newest_checked_tick": "110"}

    asyncio.run(scenario())


def test_collect_keeps_chasing_while_the_drop_gets_nearer_and_confirms() -> None:
    """A closing approach is not a stall: the nearest sighting shrinks across
    corrections, so the chase continues and the synced rise confirms the pickup.
    This is the control the stall test needs to show the reachability guard fires
    only on a walk that is genuinely not arriving."""

    async def scenario() -> None:
        store = store_with(
            reading(
                tick=100,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=100, distance=2.5),),
            )
        )
        skills, sender = skill_with(store)
        queued = [
            reading(
                tick=110,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=110, distance=1.5),),
            ),
            reading(
                tick=120,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=120, distance=0.5),),
            ),
            reading(
                tick=130,
                inventory_value=inventory(130, (0, "minecraft:oak_log", 1)),
                entities=(),
            ),
        ]

        def answer(message_type: str) -> None:
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
        assert outcome.post_tick == 130
        assert int(outcome.details["steps"]) == 3

    asyncio.run(scenario())


def test_collect_chases_a_drop_that_rests_below_the_walk_path() -> None:
    """A drop lying below the ground the Kin walks on closes on the horizontal plane
    while its three-dimensional offset plateaus at the vertical floor. The reachability
    guard measures the plane the step actually moves, so this approach keeps chasing to
    the confirming rise instead of calling it stalled after the allowed corrections —
    the false stall that left the logged live run never reaching craft."""

    async def scenario() -> None:
        store = store_with(
            reading(
                tick=100,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=100, distance=2.0, vertical=-3.0),),
            )
        )
        skills, sender = skill_with(store)
        # Each sighting is nearer along the ground by 0.4 (> the 0.25 close gate) yet
        # the total offset barely shrinks past the 3-block drop, so a 3D measure would
        # read the last of these as stalled. The chase continues and then confirms.
        queued = [
            reading(
                tick=110,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=110, distance=1.6, vertical=-3.0),),
            ),
            reading(
                tick=120,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=120, distance=1.2, vertical=-3.0),),
            ),
            reading(
                tick=130,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=130, distance=0.8, vertical=-3.0),),
            ),
            reading(
                tick=140,
                inventory_value=inventory(100),
                entities=(oak_log_drop(tick=140, distance=0.4, vertical=-3.0),),
            ),
            reading(
                tick=150,
                inventory_value=inventory(150, (0, "minecraft:oak_log", 1)),
                entities=(),
            ),
        ]

        def answer(message_type: str) -> None:
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
        assert outcome.reason == ""
        assert outcome.post_tick == 150
        # More walks than a stall would ever allow, and every one of them fired.
        assert int(outcome.details["steps"]) == COLLECT_MAX_STALLED_CORRECTIONS + 2
        assert sender.types().count(AIM_INPUT_TYPE) == COLLECT_MAX_STALLED_CORRECTIONS + 2

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
        replies = iter((fill, still_stuck, deposited))

        def answer(message_type: str) -> None:
            if message_type == GUI_CLICK_INPUT_TYPE:
                # Each frame answers its corresponding click. Independent timers
                # can overwrite the cursor frame before a loaded loop reads it.
                assert store.admit(next(replies), ())

        sender.on_send = answer

        outcome = await skills.craft_take_result(
            recipe_id="oak_planks",
            materials={LOG: 1},
            product_id=PLANKS,
            authority=authority(),
            timeout_ns=2_000_000_000,
        )
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
            cast(control_pb2.ScreenInput, command).control == control_pb2.SCREEN_CONTROL_CLOSE
            for _, command in sender.sent
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


def test_a_stop_request_ends_a_step_that_keeps_getting_readings() -> None:
    """The operator's ask interrupts like the client's exit does, and for the same
    reason: after it, nobody will send the reading that would answer the wait.

    A stop that interrupted only *between* steps would let a chase — or a fight, or
    a walk — keep driving the client for the rest of its window after the operator
    asked for the run to end, which is exactly the span in which the release the
    stopper is waiting for must go out. So the ask is checked where the readings
    are, not only at the step boundary.
    """

    async def scenario() -> None:
        store = store_with(
            reading(tick=100, inventory_value=inventory(100), entities=(oak_log_drop(tick=100),))
        )
        asked = [False]
        skills = WorldSkills(
            sender=RecordingSender(),
            observations=store,
            capabilities=ALL_CAPABILITIES,
            stop_requested=lambda: asked[0],
        )

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

        async def ask() -> None:
            await asyncio.sleep(0.06)
            asked[0] = True

        feeding = asyncio.create_task(feed())
        asking = asyncio.create_task(ask())

        raised: SessionStopRequested | None = None
        try:
            await skills.collect_dropped(
                item_id=LOG, authority=authority(), walk_seconds=0.01, timeout_ns=60_000_000_000
            )
        except SessionStopRequested as stop:
            raised = stop
        await feeding
        await asking

        assert raised is not None
        # The step's own id travels with the stop, because the command carrying it
        # may already have reached the client and the release that follows is the
        # receipt a stopper reads.
        assert raised.action_id != ""

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


# ---------------------------------------------------------------------------
# use_target: the one general interaction key — it taps, and a reading concludes
# ---------------------------------------------------------------------------


def hand_state(*, item: str | None, slot: int = 0) -> SelfStateValue:
    return SelfStateValue(
        health=20.0,
        max_health=20.0,
        food=20,
        saturation=5.0,
        alive=True,
        selected_slot=slot,
        main_hand_item_id=item,
    )


def entity_aim() -> AimTargetValue:
    return AimTargetValue(
        game_tick=100,
        kind=AimKind.ENTITY,
        entity_observation_id="obs-villager",
        entity_type="minecraft:villager",
        distance=2.0,
    )


def test_use_refuses_a_crosshair_on_air_before_the_wire() -> None:
    async def scenario() -> None:
        store = store_with(reading(aim=None))
        skills, sender = skill_with(store)

        outcome = await skills.use_target(authority=authority())
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "USE_TARGET_NOT_AIMED"
        assert sender.sent == []

    asyncio.run(scenario())


def test_use_reports_no_latest_observation_from_an_empty_store() -> None:
    async def scenario() -> None:
        skills, sender = skill_with(store_with())

        outcome = await skills.use_target(authority=authority())
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "NO_LATEST_OBSERVATION"
        assert sender.sent == []

    asyncio.run(scenario())


def test_use_taps_press_then_release_and_confirms_on_the_opened_window() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100, aim=entity_aim()))
        skills, sender = skill_with(store)
        opened = reading(
            tick=110,
            aim=entity_aim(),
            gui=GuiScreenValue(screen_id="minecraft:chest", sync_id=3),
        )
        task = asyncio.create_task(admit_later(store, opened))

        outcome = await skills.use_target(authority=authority(), timeout_ns=2_000_000_000)
        await task

        assert outcome.result is ActionResultClass.CONFIRMED
        assert sender.types() == [USE_INPUT_TYPE, USE_INPUT_TYPE]
        presses = [cast(control_pb2.UseInput, message).use for _, message in sender.sent]
        assert presses == [True, False]
        assert outcome.details["newest_sync_id"] == "3"

    asyncio.run(scenario())


def test_use_confirms_on_a_synced_held_item_decrease() -> None:
    async def scenario() -> None:
        store = store_with(
            reading(
                tick=100,
                aim=block_aim(),
                state_value=hand_state(item=PLANKS),
                inventory_value=inventory(101, (0, PLANKS, 5)),
            )
        )
        skills, sender = skill_with(store)
        spent = reading(
            tick=110,
            aim=block_aim(),
            state_value=hand_state(item=PLANKS),
            inventory_value=inventory(110, (0, PLANKS, 4)),
        )
        task = asyncio.create_task(admit_later(store, spent))

        outcome = await skills.use_target(authority=authority(), timeout_ns=2_000_000_000)
        await task

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.details["held_item_id"] == PLANKS
        # One tap only: the decrease was read on the frame after the release, so no
        # second click is fired to chase a confirmation that already arrived.
        assert sender.types() == [USE_INPUT_TYPE, USE_INPUT_TYPE]

    asyncio.run(scenario())


def test_a_use_the_channel_never_answers_is_unknown_and_fires_no_second_click() -> None:
    """§4: no reading, no verdict — and the tap already let go of the key before
    the wait, so a silent channel ends with the button up and exactly one
    press/release pair rather than a repeated side-effecting click."""

    async def scenario() -> None:
        store = store_with(reading(tick=100, aim=block_aim()))
        skills, sender = skill_with(store)

        outcome = await skills.use_target(authority=authority(), timeout_ns=20_000_000)

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"
        assert sender.types() == [USE_INPUT_TYPE, USE_INPUT_TYPE]

    asyncio.run(scenario())


def test_a_use_with_no_confirmed_change_is_unknown_never_failed() -> None:
    async def scenario() -> None:
        store = store_with(
            reading(
                tick=100,
                aim=block_aim(),
                state_value=hand_state(item=PLANKS),
                inventory_value=inventory(101, (0, PLANKS, 5)),
            )
        )
        skills, sender = skill_with(store)
        # A newer reading, but the same revision and count and no window: a use
        # that cannot be told from a frame that has not arrived yet.
        unchanged = reading(
            tick=110,
            aim=block_aim(),
            state_value=hand_state(item=PLANKS),
            inventory_value=inventory(101, (0, PLANKS, 5)),
        )
        task = asyncio.create_task(admit_later(store, unchanged))

        outcome = await skills.use_target(authority=authority(), timeout_ns=2_000_000_000)
        await task

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.result is not ActionResultClass.FAILED
        # The world never moved, but the tap still let go of the key: exactly one
        # press/release pair, and no second click chasing an unverdicted change.
        assert sender.types() == [USE_INPUT_TYPE, USE_INPUT_TYPE]

    asyncio.run(scenario())


def test_use_waits_for_a_later_effect_after_an_unchanged_newer_frame() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100, aim=entity_aim()))
        skills, sender = skill_with(store)

        async def report() -> None:
            # A newer frame can precede the game's effect. The tap must not be
            # replayed, but the remaining observation window is still usable.
            await asyncio.sleep(0.30)
            store.admit(reading(tick=110, aim=entity_aim()), ())
            await asyncio.sleep(0.05)
            store.admit(
                reading(
                    tick=120,
                    aim=entity_aim(),
                    gui=GuiScreenValue(screen_id="minecraft:crafting", sync_id=3),
                ),
                (),
            )

        task = asyncio.create_task(report())
        outcome = await skills.use_target(authority=authority(), timeout_ns=500_000_000)
        await task
        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 120
        assert sender.types() == [USE_INPUT_TYPE, USE_INPUT_TYPE]

    asyncio.run(scenario())


def test_collect_does_not_walk_before_the_observed_heading_reaches_the_drop() -> None:
    async def scenario() -> None:
        item = EntityCandidate(
            observation_id="west-drop",
            entity_type="minecraft:item",
            relative_x=2.0,
            relative_y=0.0,
            relative_z=0.0,
            line_of_sight=True,
            item_id="minecraft:oak_log",
            item_count=1,
        )
        store = store_with(reading(tick=100, entities=(item,)))
        skills, sender = skill_with(store)
        aimed = asyncio.Event()

        def answer(message_type: str) -> None:
            if message_type == AIM_INPUT_TYPE:
                aimed.set()
            if message_type == MOVE_INPUT_TYPE:
                move = cast(control_pb2.MoveInput, sender.sent[-1][1])
                if move.forward:
                    assert store.latest is not None
                    assert store.latest.self_state.yaw_degrees == -90.0
                else:
                    store.admit(
                        reading(
                            tick=130,
                            state_value=state(yaw=-90.0, pitch=0.0),
                            inventory_value=inventory(130, (0, "minecraft:oak_log", 1)),
                        ),
                        (),
                    )

        async def turn_report() -> None:
            await aimed.wait()
            await asyncio.sleep(0)
            store.admit(
                reading(tick=120, entities=(item,), state_value=state(yaw=-90.0, pitch=0.0)), ()
            )

        sender.on_send = answer
        reporting = asyncio.create_task(turn_report())
        result = await skills.collect_dropped(
            item_id="minecraft:oak_log",
            authority=authority(),
            walk_seconds=0.0,
            timeout_ns=500_000_000,
        )
        await reporting
        assert result.result is ActionResultClass.CONFIRMED
        assert sender.types() == [AIM_INPUT_TYPE, MOVE_INPUT_TYPE, MOVE_INPUT_TYPE]

    asyncio.run(scenario())


def test_result_slot_waits_for_observed_recipe_fill_before_clicking() -> None:
    async def scenario() -> None:
        store = _player_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)
        recipe_sent = asyncio.Event()

        def answer(message_type: str) -> None:
            if message_type != GUI_CLICK_INPUT_TYPE:
                return
            click = _gui_clicks(sender)[-1]
            if click.HasField("recipe"):
                store.admit(
                    reading(
                        tick=110,
                        inventory_value=inventory(110, (0, LOG, 1)),
                        gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
                    ),
                    (),
                )
                recipe_sent.set()
            elif click.HasField("slot"):
                assert store.latest is not None
                assert store.latest.inventory.stacks == ()
                store.admit(
                    reading(
                        tick=130,
                        inventory_value=inventory(130, (0, PLANKS, 4)),
                        gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
                    ),
                    (),
                )

        async def server_fill() -> None:
            await recipe_sent.wait()
            await asyncio.sleep(0.05)
            store.admit(
                reading(
                    tick=120,
                    inventory_value=inventory(120),
                    gui=GuiScreenValue(screen_id="PlayerScreen", sync_id=0),
                ),
                (),
            )

        sender.on_send = answer
        fill = asyncio.create_task(server_fill())
        outcome = await skills.craft_take_result(
            recipe_id="oak_planks",
            materials={LOG: 1},
            product_id=PLANKS,
            authority=authority(),
            timeout_ns=500_000_000,
        )
        await fill
        assert outcome.result is ActionResultClass.CONFIRMED
        assert len(_gui_clicks(sender)) == 2

    asyncio.run(scenario())


def test_collect_confirms_natural_pickup_even_if_the_heading_never_finishes() -> None:
    async def scenario() -> None:
        item = EntityCandidate(
            observation_id="nearby-drop",
            entity_type="minecraft:item",
            relative_x=1.0,
            relative_y=0.0,
            relative_z=0.0,
            line_of_sight=True,
            item_id=LOG,
            item_count=1,
        )
        store = store_with(reading(tick=100, entities=(item,)))
        skills, sender = skill_with(store)

        def answer(message_type: str) -> None:
            if message_type == AIM_INPUT_TYPE:
                store.admit(reading(tick=110, inventory_value=inventory(110, (0, LOG, 1))), ())

        sender.on_send = answer
        outcome = await skills.collect_dropped(
            item_id=LOG, authority=authority(), walk_seconds=0.0, timeout_ns=20_000_000
        )
        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 110
        assert sender.types() == [AIM_INPUT_TYPE]

    asyncio.run(scenario())


def test_recipe_fill_interrupted_by_another_handler_never_clicks_its_slot_zero() -> None:
    async def scenario() -> None:
        store = _player_screen_store((0, LOG, 1))
        skills, sender = skill_with(store)
        changed = reading(
            tick=110,
            inventory_value=inventory(110),
            gui=GuiScreenValue(screen_id="minecraft:chest", sync_id=9),
        )
        task = asyncio.create_task(admit_later(store, changed))
        outcome = await skills.craft_take_result(
            recipe_id="oak_planks",
            materials={LOG: 1},
            product_id=PLANKS,
            authority=authority(),
            timeout_ns=500_000_000,
        )
        await task
        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "SCREEN_NOT_CONFIRMED"
        clicks = _gui_clicks(sender)
        assert len(clicks) == 1
        assert clicks[0].HasField("recipe")
        assert clicks[0].sync_id == 0

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# The consume row: the number key when needed, then the use key held for the
# meal's own duration, concluded only by one frame with the bar up and the
# stack down.
# ---------------------------------------------------------------------------


def _hungry_state(
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
        yaw_degrees=0.0,
        pitch_degrees=0.0,
        selected_slot=selected_slot,
        main_hand_item_id=main_hand,
    )


def test_consume_refuses_its_preconditions_before_the_wire() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100, state_value=_hungry_state(), aim=miss_aim(100)))
        skills, sender = skill_with(store)

        outcome = await skills.consume_item(item_id="minecraft:apple", authority=authority())

        assert (outcome.result, outcome.reason) == (
            ActionResultClass.FAILED,
            "CONSUME_ITEM_MISSING",
        )
        assert sender.sent == []

    asyncio.run(scenario())


def test_consume_selects_the_slot_then_holds_the_use_key_until_one_frame_confirms(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr("minekin_core.application.world_skills.CONSUME_HOLD_SECONDS", 0.01)

    async def scenario() -> None:
        first = reading(
            tick=100,
            state_value=_hungry_state(),
            aim=miss_aim(100),
            inventory_value=inventory(100, (3, "minecraft:apple", 2)),
        )
        store = store_with(first)
        skills, sender = skill_with(store)
        chosen = reading(
            tick=110,
            state_value=_hungry_state(selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(110),
            inventory_value=inventory(105, (3, "minecraft:apple", 2)),
        )
        eaten = reading(
            tick=130,
            state_value=_hungry_state(food=12, selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(130),
            inventory_value=inventory(125, (3, "minecraft:apple", 1)),
        )
        selecting = asyncio.create_task(admit_later(store, chosen))
        eating = asyncio.create_task(admit_after(store, 0.05, eaten))

        outcome = await skills.consume_item(item_id="minecraft:apple", authority=authority())
        await selecting
        await eating

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 130
        assert sender.types() == [HOTBAR_SELECT_INPUT_TYPE, USE_INPUT_TYPE, USE_INPUT_TYPE]
        assert cast(control_pb2.UseInput, sender.sent[1][1]).use is True
        assert cast(control_pb2.UseInput, sender.sent[2][1]).use is False
        assert outcome.details["food_before"] == "8"
        assert outcome.details["food_after"] == "12"
        assert outcome.details["item_before"] == "2"
        assert outcome.details["item_after"] == "1"

    asyncio.run(scenario())


def test_consume_with_the_food_already_in_hand_sends_no_number_key(monkeypatch: Any) -> None:
    monkeypatch.setattr("minekin_core.application.world_skills.CONSUME_HOLD_SECONDS", 0.01)

    async def scenario() -> None:
        first = reading(
            tick=100,
            state_value=_hungry_state(selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(100),
            inventory_value=inventory(100, (3, "minecraft:apple", 2)),
        )
        store = store_with(first)
        skills, sender = skill_with(store)
        eaten = reading(
            tick=120,
            state_value=_hungry_state(food=12, selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(120),
            inventory_value=inventory(120, (3, "minecraft:apple", 1)),
        )
        task = asyncio.create_task(admit_later(store, eaten))

        outcome = await skills.consume_item(item_id="minecraft:apple", authority=authority())
        await task

        assert outcome.result is ActionResultClass.CONFIRMED
        assert sender.types() == [USE_INPUT_TYPE, USE_INPUT_TYPE]

    asyncio.run(scenario())


def test_consume_unknown_buys_no_second_press(monkeypatch: Any) -> None:
    monkeypatch.setattr("minekin_core.application.world_skills.CONSUME_HOLD_SECONDS", 0.01)

    async def scenario() -> None:
        first = reading(
            tick=100,
            state_value=_hungry_state(selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(100),
            inventory_value=inventory(100, (3, "minecraft:apple", 2)),
        )
        store = store_with(first)
        skills, sender = skill_with(store)

        outcome = await skills.consume_item(
            item_id="minecraft:apple", authority=authority(), timeout_ns=60_000_000
        )

        assert (outcome.result, outcome.reason) == (
            ActionResultClass.UNKNOWN,
            "NO_CONFIRMING_OBSERVATION",
        )
        assert sender.types() == [USE_INPUT_TYPE, USE_INPUT_TYPE]

    asyncio.run(scenario())


@pytest.mark.parametrize("food_after,item_after", [(0, 1), (8, 2)])
def test_consume_newer_nonconfirming_frame_keeps_a_reason(
    monkeypatch: Any, food_after: int, item_after: int
) -> None:
    """An item disappearing without a bar rise must not become unexplained success."""
    monkeypatch.setattr("minekin_core.application.world_skills.CONSUME_HOLD_SECONDS", 0.01)

    async def scenario() -> None:
        first = reading(
            tick=100,
            state_value=_hungry_state(food=8, selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(100),
            inventory_value=inventory(100, (3, "minecraft:apple", 2)),
        )
        store = store_with(first)
        skills, sender = skill_with(store)
        newer = reading(
            tick=120,
            state_value=_hungry_state(
                food=food_after, selected_slot=3, main_hand="minecraft:apple"
            ),
            aim=miss_aim(120),
            inventory_value=inventory(120, (3, "minecraft:apple", item_after)),
        )
        task = asyncio.create_task(admit_after(store, 0.005, newer))
        outcome = await skills.consume_item(
            item_id="minecraft:apple", authority=authority(), timeout_ns=200_000_000
        )
        await task
        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "NO_CONFIRMING_OBSERVATION"
        assert outcome.post_tick == 120
        assert sender.types() == [USE_INPUT_TYPE, USE_INPUT_TYPE]

    asyncio.run(scenario())


def test_consume_refuses_a_full_bar_and_an_occupied_crosshair_before_the_wire() -> None:
    async def scenario() -> None:
        full = reading(
            tick=100,
            state_value=_hungry_state(food=20, selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(100),
            inventory_value=inventory(100, (3, "minecraft:apple", 2)),
        )
        store = store_with(full)
        skills, sender = skill_with(store)
        outcome = await skills.consume_item(item_id="minecraft:apple", authority=authority())
        assert (outcome.result, outcome.reason) == (
            ActionResultClass.FAILED,
            "CONSUME_NOT_HUNGRY",
        )

        aimed = reading(
            tick=110,
            state_value=_hungry_state(selected_slot=3, main_hand="minecraft:apple"),
            aim=block_aim(),
            inventory_value=inventory(110, (3, "minecraft:apple", 2)),
        )
        store.admit(aimed, ())
        outcome = await skills.consume_item(item_id="minecraft:apple", authority=authority())
        assert (outcome.result, outcome.reason) == (
            ActionResultClass.FAILED,
            "CONSUME_AIM_NOT_CLEAR",
        )
        assert sender.sent == []

    asyncio.run(scenario())


def test_consume_releases_as_soon_as_a_reading_confirms(monkeypatch: Any) -> None:
    """The hold is a cap, not a fixed wait: the release follows the frame that shows
    the meal. That is what keeps one call to one item even on a snack-speed food —
    a blind hold of the full cap could have finished a second bite, because a client
    restarts the meal as long as the key stays down."""

    monkeypatch.setattr("minekin_core.application.world_skills.CONSUME_HOLD_SECONDS", 6.0)

    async def scenario() -> None:
        first = reading(
            tick=100,
            state_value=_hungry_state(selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(100),
            inventory_value=inventory(100, (3, "minecraft:apple", 2)),
        )
        store = store_with(first)
        skills, sender = skill_with(store)
        eaten = reading(
            tick=120,
            state_value=_hungry_state(food=12, selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(120),
            inventory_value=inventory(120, (3, "minecraft:apple", 1)),
        )
        task = asyncio.create_task(admit_after(store, 0.05, eaten))

        started = time.monotonic()
        outcome = await skills.consume_item(item_id="minecraft:apple", authority=authority())
        elapsed = time.monotonic() - started
        await task

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 120
        assert sender.types() == [USE_INPUT_TYPE, USE_INPUT_TYPE]
        # Six seconds of hold were allowed and a confirming frame arrived at ~0.05 s;
        # a release that waited out the cap would be the defect this pins.
        assert elapsed < 2.0

    asyncio.run(scenario())


def test_consume_rechecks_the_bar_between_selection_and_press(monkeypatch: Any) -> None:
    """The frame that confirms the selection is the frame the press is judged against:
    a bar that filled meanwhile is named before the key goes down, rather than spent on
    a meal the world no longer owes."""

    monkeypatch.setattr("minekin_core.application.world_skills.CONSUME_HOLD_SECONDS", 0.01)

    async def scenario() -> None:
        first = reading(
            tick=100,
            state_value=_hungry_state(),
            aim=miss_aim(100),
            inventory_value=inventory(100, (3, "minecraft:apple", 2)),
        )
        store = store_with(first)
        skills, sender = skill_with(store)
        filled = reading(
            tick=110,
            state_value=_hungry_state(food=20, selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(110),
            inventory_value=inventory(110, (3, "minecraft:apple", 2)),
        )
        task = asyncio.create_task(admit_later(store, filled))

        outcome = await skills.consume_item(item_id="minecraft:apple", authority=authority())
        await task

        assert (outcome.result, outcome.reason) == (
            ActionResultClass.FAILED,
            "CONSUME_NOT_HUNGRY",
        )
        assert sender.types() == [HOTBAR_SELECT_INPUT_TYPE]

    asyncio.run(scenario())


def test_consume_labels_a_selection_that_never_confirmed_with_its_phase() -> None:
    async def scenario() -> None:
        first = reading(
            tick=100,
            state_value=_hungry_state(),
            aim=miss_aim(100),
            inventory_value=inventory(100, (3, "minecraft:apple", 2)),
        )
        store = store_with(first)
        skills, sender = skill_with(store)

        outcome = await skills.consume_item(
            item_id="minecraft:apple", authority=authority(), timeout_ns=60_000_000
        )

        assert (outcome.result, outcome.reason) == (
            ActionResultClass.UNKNOWN,
            "NO_CONFIRMING_OBSERVATION",
        )
        # The reader of a failed meal should not have to infer which of the two steps
        # the verdict was about.
        assert outcome.details["phase"] == "select_hotbar"
        assert sender.types() == [HOTBAR_SELECT_INPUT_TYPE]

    asyncio.run(scenario())


def test_consume_spends_one_window_across_both_phases(monkeypatch: Any) -> None:
    """One `timeout_ns` covers selection, hold and the concluding wait: a slow
    selection shortens the meal ahead instead of the step outliving the lease the
    plan sized for a single wait window."""

    monkeypatch.setattr("minekin_core.application.world_skills.CONSUME_HOLD_SECONDS", 6.0)

    async def scenario() -> None:
        first = reading(
            tick=100,
            state_value=_hungry_state(),
            aim=miss_aim(100),
            inventory_value=inventory(100, (3, "minecraft:apple", 2)),
        )
        store = store_with(first)
        skills, sender = skill_with(store)
        chosen = reading(
            tick=110,
            state_value=_hungry_state(selected_slot=3, main_hand="minecraft:apple"),
            aim=miss_aim(110),
            inventory_value=inventory(105, (3, "minecraft:apple", 2)),
        )
        task = asyncio.create_task(admit_later(store, chosen))

        started = time.monotonic()
        outcome = await skills.consume_item(
            item_id="minecraft:apple", authority=authority(), timeout_ns=400_000_000
        )
        elapsed = time.monotonic() - started
        await task

        # The selection consumed a slice of the 0.4 s window and the hold cap could
        # only use what was left; a skill that granted the hold a second full window
        # (a patched cap of six seconds) would run past two seconds here.
        assert outcome.result is ActionResultClass.UNKNOWN
        assert sender.types() == [HOTBAR_SELECT_INPUT_TYPE, USE_INPUT_TYPE, USE_INPUT_TYPE]
        assert elapsed < 1.5

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "name",
    [
        "turn_to",
        "break_seen_block",
        "collect_dropped",
        "craft",
        "craft_take_result",
        "close_screen",
        "select_hotbar",
        "use_target",
        "consume_item",
    ],
)
def test_dead_body_refuses_every_skill_before_any_command(name: str) -> None:
    async def scenario() -> None:
        dead = replace(state(), health=0.0, alive=False)
        store = store_with(reading(state_value=dead))
        skills, sender = skill_with(store)
        outcome = await perform_skill(
            skills,
            SkillCall(
                name=name,
                item_id="minecraft:apple",
                slot=0,
                recipe_id="minecraft:oak_planks",
                product_id=PLANKS,
                materials=((LOG, 1),),
            ),
            authority=authority(),
            timeout_ns=1_000_000,
        )
        assert sender.sent == []
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "PLAYER_DEAD"

    asyncio.run(scenario())


def test_death_during_consumption_interrupts_instead_of_confirming_inventory_loss() -> None:
    async def scenario() -> None:
        first = reading(
            state_value=_hungry_state(selected_slot=0, main_hand="minecraft:apple"),
            aim=miss_aim(100),
            inventory_value=inventory(100, (0, "minecraft:apple", 2)),
        )
        dead = reading(
            tick=120,
            state_value=replace(state(), health=0.0, alive=False),
            aim=miss_aim(120),
            inventory_value=inventory(120),
        )
        store = store_with(first)
        skills, sender = skill_with(store)

        def die_after_press(message_type: str) -> None:
            if message_type == USE_INPUT_TYPE:
                message = cast(control_pb2.UseInput, sender.sent[-1][1])
                if message.use:
                    assert store.admit(dead, ())

        sender.on_send = die_after_press
        outcome = await perform_skill(
            skills,
            SkillCall(name="consume_item", item_id="minecraft:apple"),
            authority=authority(),
            timeout_ns=1_000_000_000,
        )
        assert outcome.result is ActionResultClass.INTERRUPTED
        assert outcome.reason == "PLAYER_DEAD"
        assert outcome.post_tick == 120
        assert [
            cast(control_pb2.UseInput, m).use for t, m in sender.sent if t == USE_INPUT_TYPE
        ] == [True, False]
        assert outcome.action_id

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("name", "message_type", "field"),
    [
        ("break_seen_block", MINE_INPUT_TYPE, "mining"),
        ("collect_dropped", MOVE_INPUT_TYPE, "forward"),
        ("use_target", USE_INPUT_TYPE, "use"),
        ("consume_item", USE_INPUT_TYPE, "use"),
    ],
)
@pytest.mark.parametrize("interruption", ["death", "cancel"])
def test_held_action_stops_on_death_or_cancellation(
    name: str, message_type: str, field: str, interruption: str
) -> None:
    async def scenario() -> None:
        first = reading(aim=block_aim(), entities=(oak_log_drop(tick=100),))
        if name == "consume_item":
            first = reading(
                state_value=_hungry_state(selected_slot=0, main_hand="minecraft:apple"),
                aim=miss_aim(100),
                inventory_value=inventory(100, (0, "minecraft:apple", 2)),
            )
        dead = reading(
            tick=120, state_value=replace(state(), health=0.0, alive=False), aim=miss_aim(120)
        )
        store = store_with(first)
        skills, sender = skill_with(store)
        pressed = asyncio.Event()

        def interrupt_after_press(sent_type: str) -> None:
            if sent_type == message_type and getattr(sender.sent[-1][1], field):
                pressed.set()
                if interruption == "death":
                    assert store.admit(dead, ())

        sender.on_send = interrupt_after_press
        pending = asyncio.create_task(
            perform_skill(
                skills,
                SkillCall(
                    name=name,
                    item_id="minecraft:apple" if name == "consume_item" else LOG,
                    walk_seconds=1.0,
                ),
                authority=authority(),
                timeout_ns=5_000_000_000,
            )
        )
        await asyncio.wait_for(pressed.wait(), timeout=1)
        if interruption == "cancel":
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        else:
            outcome = await asyncio.wait_for(pending, timeout=1)
            assert outcome.result is ActionResultClass.INTERRUPTED
            assert outcome.reason == "PLAYER_DEAD" and outcome.post_tick == 120
        assert [getattr(m, field) for t, m in sender.sent if t == message_type] == [1, 0]

    asyncio.run(scenario())


def test_failed_stop_send_cannot_replace_observed_death() -> None:
    async def scenario() -> None:
        first = reading(
            state_value=_hungry_state(selected_slot=0, main_hand="minecraft:apple"),
            aim=miss_aim(100),
            inventory_value=inventory(100, (0, "minecraft:apple", 2)),
        )
        dead = reading(
            tick=120, state_value=replace(state(), health=0.0, alive=False), aim=miss_aim(120)
        )
        store = store_with(first)

        class LostReleaseSender(RecordingSender):
            async def send_control(self, message_type: str, message: Message) -> None:
                await super().send_control(message_type, message)
                if message_type == USE_INPUT_TYPE:
                    if cast(control_pb2.UseInput, message).use:
                        assert store.admit(dead, ())
                    else:
                        raise ConnectionError("fixture stop transport unavailable")

        sender = LostReleaseSender()
        skills = WorldSkills(sender=sender, observations=store, capabilities=ALL_CAPABILITIES)
        outcome = await perform_skill(
            skills,
            SkillCall(name="consume_item", item_id="minecraft:apple"),
            authority=authority(),
            timeout_ns=1_000_000_000,
        )
        assert outcome.reason == "PLAYER_DEAD" and outcome.result is ActionResultClass.INTERRUPTED
        assert outcome.details == {"release_send_failed": "true"}
        assert len(sender.sent) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("prior_death", [False, True])
def test_consumption_uses_deaths_since_its_start_even_when_latest_is_live(
    prior_death: bool,
) -> None:
    async def scenario() -> None:
        first = reading(
            state_value=_hungry_state(selected_slot=0, main_hand="minecraft:apple"),
            aim=miss_aim(100),
            inventory_value=inventory(100, (0, "minecraft:apple", 2)),
        )
        dead = reading(tick=110, state_value=replace(state(), health=0.0, alive=False))
        revived = replace(first, game_tick=120)
        store = store_with(first)
        if prior_death:
            assert store.admit(dead, ())
            assert store.admit(revived, ())
        skills, sender = skill_with(store)
        eaten = reading(
            tick=140,
            state_value=replace(first.self_state, food=20),
            aim=miss_aim(140),
            inventory_value=inventory(140, (0, "minecraft:apple", 1)),
        )

        def answer(message_type: str) -> None:
            if (
                message_type == USE_INPUT_TYPE
                and cast(control_pb2.UseInput, sender.sent[-1][1]).use
            ):
                if not prior_death:
                    assert store.admit(dead, ())
                assert store.admit(eaten, ())

        sender.on_send = answer
        outcome = await perform_skill(
            skills,
            SkillCall(name="consume_item", item_id="minecraft:apple"),
            authority=authority(),
            timeout_ns=1_000_000_000,
        )
        assert outcome.result is (
            ActionResultClass.CONFIRMED if prior_death else ActionResultClass.INTERRUPTED
        )
        if not prior_death:
            assert outcome.reason == "PLAYER_DEAD"
            assert outcome.post_tick == 110
        assert [
            cast(control_pb2.UseInput, m).use for t, m in sender.sent if t == USE_INPUT_TYPE
        ] == [True, False]

    asyncio.run(scenario())


def test_transient_death_wakes_an_in_progress_held_wait_before_its_deadline() -> None:
    async def scenario() -> None:
        first = reading(
            state_value=_hungry_state(selected_slot=0, main_hand="minecraft:apple"),
            aim=miss_aim(100),
            inventory_value=inventory(100, (0, "minecraft:apple", 2)),
        )
        store = store_with(first)
        skills, sender = skill_with(store)
        loop = asyncio.get_running_loop()

        def transition() -> None:
            assert store.admit(
                reading(tick=110, state_value=replace(state(), health=0, alive=False)), ()
            )
            # A newer live reading with no food gain leaves the ordinary wait
            # predicate false; the retained death must wake and interrupt it.
            assert store.admit(replace(first, game_tick=120), ())

        def answer(message_type: str) -> None:
            if (
                message_type == USE_INPUT_TYPE
                and cast(control_pb2.UseInput, sender.sent[-1][1]).use
            ):
                loop.call_soon(transition)

        sender.on_send = answer
        outcome = await asyncio.wait_for(
            perform_skill(
                skills,
                SkillCall(name="consume_item", item_id="minecraft:apple"),
                authority=authority(),
                timeout_ns=2_000_000_000,
            ),
            timeout=0.5,
        )
        assert outcome.reason == "PLAYER_DEAD"
        assert outcome.post_tick == 110
        assert [
            cast(control_pb2.UseInput, m).use for t, m in sender.sent if t == USE_INPUT_TYPE
        ] == [True, False]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "condition",
    ["no_permission", "no_observation", "alive", "unread", "unavailable", "wrong_generation"],
)
def test_respawn_refuses_before_any_request_unless_the_visible_action_is_available(
    condition: str,
) -> None:
    async def scenario() -> None:
        body = replace(state(), health=0, alive=False, respawn_available=True)
        pre = reading(state_value=body)
        caps = ALL_CAPABILITIES | {RESPAWN_CAPABILITY}
        store = WorldObservationStore(expected_generation=1)
        expected = {
            "no_permission": "CAPABILITY_NOT_GRANTED",
            "no_observation": "NO_LATEST_OBSERVATION",
            "alive": "RESPAWN_ALREADY_ALIVE",
            "unread": "RESPAWN_UNAVAILABLE",
            "unavailable": "RESPAWN_UNAVAILABLE",
            "wrong_generation": "WORLD_GENERATION_CHANGED",
        }[condition]
        if condition == "no_permission":
            caps = ALL_CAPABILITIES
        elif condition == "alive":
            pre = reading()
        elif condition == "unread":
            pre = replace(pre, self_state=replace(body, respawn_available=None))
        elif condition == "unavailable":
            pre = replace(pre, self_state=replace(body, respawn_available=False))
        elif condition == "wrong_generation":
            store.expected_generation = 2
            pre = replace(pre, generation=2)
        if condition != "no_observation":
            assert store.admit(pre, ())
        skills, sender = skill_with(store, caps)
        outcome = await perform_skill(
            skills, SkillCall(name="respawn"), authority=authority(), timeout_ns=1_000_000
        )
        assert outcome.reason == expected
        assert sender.sent == []

    asyncio.run(scenario())


@pytest.mark.parametrize("answer", ["live", "still_dead", "generation"])
def test_respawn_requests_once_and_only_confirms_a_new_same_generation_live_reading(
    answer: str,
) -> None:
    async def scenario() -> None:
        pre = reading(state_value=replace(state(), health=0, alive=False, respawn_available=True))
        store = store_with(pre)
        skills, sender = skill_with(store, ALL_CAPABILITIES | {RESPAWN_CAPABILITY})

        def reply(message_type: str) -> None:
            if message_type != RESPAWN_INPUT_TYPE:
                return
            if answer == "live":
                assert store.admit(reading(tick=120), ())
            elif answer == "generation":
                store.expected_generation = 2
                assert store.admit(replace(reading(tick=120), generation=2), ())
            else:
                assert store.admit(replace(pre, game_tick=120), ())

        sender.on_send = reply
        outcome = await perform_skill(
            skills, SkillCall(name="respawn"), authority=authority(), timeout_ns=5_000_000
        )
        assert len(sender.sent) == 1
        assert sender.types() == [RESPAWN_INPUT_TYPE]
        command = cast(control_pb2.RespawnInput, sender.sent[0][1])
        assert command.lease_id == "lease-1"
        assert command.generation == 1
        assert (
            outcome.result
            is {
                "live": ActionResultClass.CONFIRMED,
                "still_dead": ActionResultClass.UNKNOWN,
                "generation": ActionResultClass.INTERRUPTED,
            }[answer]
        )
        if answer == "still_dead":
            assert outcome.reason == "RESPAWN_NOT_CONFIRMED"
        else:
            assert outcome.post_tick == 120

    asyncio.run(scenario())


def slime_entity(*, tick: int, at: float = 2.0, los: bool = True) -> EntityCandidate:
    return EntityCandidate(
        observation_id=f"slime-{tick}",
        entity_type="minecraft:slime",
        relative_x=at,
        relative_y=0.0,
        relative_z=0.0,
        line_of_sight=los,
    )


def positioned(
    *,
    tick: int,
    x: float = 0.0,
    z: float = 0.0,
    yaw: float | None = 0.0,
    pitch: float = 0.0,
    entities: tuple[EntityCandidate, ...] = (),
    aim: AimTargetValue | None = None,
) -> WorldObservationValue:
    return reading(
        tick=tick,
        state_value=SelfStateValue(
            health=20.0,
            max_health=20.0,
            food=20,
            saturation=5.0,
            alive=True,
            x=x,
            y=64.0,
            z=z,
            yaw_degrees=yaw,
            pitch_degrees=pitch,
        ),
        entities=entities,
        aim=aim,
    )


def test_retreat_turns_away_from_a_visible_hostile_steps_and_names_its_release() -> None:
    async def scenario() -> None:
        store = store_with(positioned(tick=100, entities=(slime_entity(tick=100),)))
        skills, sender = skill_with(store)
        away_yaw, _ = angle_to_degrees(dx=-2.0, dy=0.0, dz=0.0)
        queued = [
            positioned(tick=110, yaw=away_yaw),
            positioned(tick=120, x=-1.5),
        ]

        def answer(message_type: str) -> None:
            if message_type in (AIM_INPUT_TYPE, MOVE_INPUT_TYPE) and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.retreat(authority=authority(), timeout_ns=10_000_000_000)

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 120
        assert outcome.details["moved_blocks"] == "1.50"
        assert outcome.details["hostile"] == "minecraft:slime"
        aims = [message for kind, message in sender.sent if kind == AIM_INPUT_TYPE]
        # Away is the reported offset's own bearing, reversed -- the same geometry collect
        # walks toward a drop with, pointed the other way.
        assert len(aims) == 1
        assert aims[0].yaw_degrees == pytest.approx(away_yaw)  # type: ignore[attr-defined]
        moves = [message for kind, message in sender.sent if kind == MOVE_INPUT_TYPE]
        # One step, and it stopped: a retreat that left the key down would be a Kin still
        # walking when it reports.
        assert [message.forward for message in moves] == [1.0, 0.0]  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_retreat_refuses_by_name_when_no_hostile_is_visible() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100))
        skills, sender = skill_with(store)

        outcome = await skills.retreat(authority=authority(), timeout_ns=1_000_000_000)

        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "RETREAT_THREAT_NOT_VISIBLE"
        assert sender.sent == []

    asyncio.run(scenario())


def test_retreat_reads_unknown_when_the_body_never_moved() -> None:
    async def scenario() -> None:
        store = store_with(positioned(tick=100, entities=(slime_entity(tick=100),)))
        skills, sender = skill_with(store)
        away_yaw, _ = angle_to_degrees(dx=-2.0, dy=0.0, dz=0.0)
        queued = [
            positioned(tick=110, yaw=away_yaw),
            positioned(tick=120, x=0.0),
        ]

        def answer(message_type: str) -> None:
            if message_type in (AIM_INPUT_TYPE, MOVE_INPUT_TYPE) and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.retreat(authority=authority(), timeout_ns=2_000_000_000)

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "RETREAT_NOT_CONFIRMED"
        moves = [message for kind, message in sender.sent if kind == MOVE_INPUT_TYPE]
        assert [message.forward for message in moves] == [1.0, 0.0]  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_retreat_keeps_moving_on_a_named_hold_with_nothing_in_sight() -> None:
    """The blind leg: a hit that landed between readings leaves no hostile to take a
    bearing from, so the caller names the hold and the walk goes where the body faces.
    No aim is sent -- there is no bearing this reading supports, and inventing one would
    be a step the world never showed."""

    async def scenario() -> None:
        store = store_with(positioned(tick=100))
        skills, sender = skill_with(store)
        queued = [positioned(tick=120, x=-6.0)]

        def answer(message_type: str) -> None:
            if message_type == MOVE_INPUT_TYPE and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.retreat(
            authority=authority(), hold_seconds=1.0, timeout_ns=10_000_000_000
        )

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.details["bearing"] == "current_heading_on_named_hold"
        assert outcome.details["hostile"] == ""
        assert outcome.details["hold_seconds"] == "1"
        assert outcome.details["moved_blocks"] == "6.00"
        aims = [message for kind, message in sender.sent if kind == AIM_INPUT_TYPE]
        assert aims == []
        moves = [message for kind, message in sender.sent if kind == MOVE_INPUT_TYPE]
        assert [message.forward for message in moves] == [1.0, 0.0]  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_fight_back_aims_at_the_hostile_swings_without_a_block_and_ends_unseen() -> None:
    """The whole fight: aim at the reported offset, hold the attack key with NO block named
    (the wire allows that only for an entity), and confirm on the honest sentence -- a later
    reading no longer renders that entity, which is not the claim that it died."""

    async def scenario() -> None:
        slime = slime_entity(tick=100)
        store = store_with(positioned(tick=100, entities=(slime,)))
        skills, sender = skill_with(store)
        # The offset is feet-to-feet; the aim is from the eye, so the pitch drops by the
        # eye height or the ray flies over anything shorter than the eye (the measured
        # MINE_TARGET_NOT_AIMED refusals of run b2e3ebeaa70b...).
        yaw, pitch = angle_to_degrees(
            dx=slime.relative_x,
            dy=slime.relative_y - EYE_HEIGHT_BLOCKS,
            dz=slime.relative_z,
        )
        # The arrival frame also carries the entity and the client's own crosshair reading
        # naming it: the press is gated on that phrase (the slime hop of run 9a4a82c3...
        # walked off a stale ray between aim and press, and the bridge refused it).
        queued = [
            positioned(tick=110, yaw=yaw, pitch=pitch, entities=(slime,), aim=slime_aim(110)),
            positioned(tick=120),
        ]

        def answer(message_type: str) -> None:
            if message_type in (AIM_INPUT_TYPE, MINE_INPUT_TYPE) and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.fight_back(
            authority=authority(), swing_seconds=1.0, timeout_ns=10_000_000_000
        )

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 120
        assert outcome.details["target"] == "minecraft:slime"
        assert outcome.details["swing_seconds"] == "1"
        aims = [message for kind, message in sender.sent if kind == AIM_INPUT_TYPE]
        # First the arrival ask, then one tracked correction from the newest reading while
        # the key is held: aiming at a body that hops is a hand's job, not one sentence.
        assert len(aims) >= 1
        assert aims[0].yaw_degrees == pytest.approx(yaw)  # type: ignore[attr-defined]
        # Down at the body, not level from the eye: the pitch is the eye-height correction.
        assert pitch > 10.0
        assert aims[0].pitch_degrees == pytest.approx(pitch)  # type: ignore[attr-defined]
        mines = [message for kind, message in sender.sent if kind == MINE_INPUT_TYPE]
        # One hold and one release, and no block target on either: naming a block would
        # make this a dig, which the wire refuses against an entity on purpose.
        assert [message.mining for message in mines] == [True, False]  # type: ignore[attr-defined]
        assert not any(message.HasField("target") for message in mines)
        # Walk it down while the key is held, and stop walking on the same exit: standing
        # between hops is where the slime's hits landed (the summon deaths of run-5).
        moves = [message for kind, message in sender.sent if kind == MOVE_INPUT_TYPE]
        assert [message.forward for message in moves] == [1.0, 0.0]  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_fight_back_breaks_off_mid_swing_when_the_body_drops_under_the_line() -> None:
    """A body that drops under the trading line mid-swing ends the fight there: the
    releases go out (attack and walk both) and the verdict stays the honest UNKNOWN,
    so the next decision re-reads a world it may want to leave."""

    async def scenario() -> None:
        slime = slime_entity(tick=100)
        store = store_with(positioned(tick=100, entities=(slime,)))
        skills, sender = skill_with(store)
        yaw, pitch = angle_to_degrees(
            dx=slime.relative_x,
            dy=slime.relative_y - EYE_HEIGHT_BLOCKS,
            dz=slime.relative_z,
        )
        hurt = replace(
            positioned(tick=120, entities=(slime,), aim=slime_aim(120)).self_state,
            health=8.0,
        )
        queued = [
            positioned(tick=110, yaw=yaw, pitch=pitch, entities=(slime,), aim=slime_aim(110)),
            replace(positioned(tick=120, entities=(slime,), aim=slime_aim(120)), self_state=hurt),
        ]

        def answer(message_type: str) -> None:
            if message_type in (AIM_INPUT_TYPE, MINE_INPUT_TYPE) and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.fight_back(
            authority=authority(), swing_seconds=5.0, timeout_ns=2_000_000_000
        )

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "FIGHT_NOT_CONFIRMED"
        mines = [message for kind, message in sender.sent if kind == MINE_INPUT_TYPE]
        moves = [message for kind, message in sender.sent if kind == MOVE_INPUT_TYPE]
        assert [message.mining for message in mines] == [True, False]  # type: ignore[attr-defined]
        assert [message.forward for message in moves] == [1.0, 0.0]  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_fight_back_honours_a_named_entity_kind_over_the_nearest_body() -> None:
    """The caller's judgement picks the body: with a slime and a pig both in reach, a fight
    for the pig aims at the pig -- the skill holds no roster of its own, only the scan."""

    async def scenario() -> None:
        from minekin_core.domain.perception import EntityCandidate

        slime = slime_entity(tick=100, at=1.5)
        pig_entity = EntityCandidate(
            observation_id="pig-100",
            entity_type="minecraft:pig",
            relative_x=2.5,
            relative_y=0.0,
            relative_z=0.0,
            line_of_sight=True,
        )
        store = store_with(positioned(tick=100, entities=(slime, pig_entity)))
        skills, sender = skill_with(store)
        pig_yaw, pig_pitch = angle_to_degrees(
            dx=pig_entity.relative_x,
            dy=pig_entity.relative_y - EYE_HEIGHT_BLOCKS,
            dz=pig_entity.relative_z,
        )
        queued = [
            positioned(
                tick=110,
                yaw=pig_yaw,
                pitch=pig_pitch,
                entities=(slime, pig_entity),
                aim=slime_aim(110, entity_id="pig-100"),
            ),
            positioned(tick=120, entities=(slime,)),
        ]

        def answer(message_type: str) -> None:
            if message_type in (AIM_INPUT_TYPE, MINE_INPUT_TYPE) and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.fight_back(
            authority=authority(),
            swing_seconds=1.0,
            target_entity_type="minecraft:pig",
            timeout_ns=10_000_000_000,
        )

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.details["target"] == "minecraft:pig"
        aims = [message for kind, message in sender.sent if kind == AIM_INPUT_TYPE]
        assert aims[0].yaw_degrees == pytest.approx(pig_yaw)  # type: ignore[attr-defined]

    asyncio.run(scenario())


def trader_entity(*, tick: int, at: float) -> EntityCandidate:
    return EntityCandidate(
        observation_id="trader-100",
        entity_type="minecraft:wandering_trader",
        relative_x=at,
        relative_y=0.0,
        relative_z=0.0,
        line_of_sight=True,
    )


def test_approach_entity_walks_until_the_reading_reports_it_within_the_named_distance() -> None:
    """The walk the live trade run measured missing: aim at the body's reported offset,
    step, re-read, repeat -- and CONFIRMED only when a reading reports the distance at or
    inside the stop."""

    async def scenario() -> None:
        start = trader_entity(tick=100, at=6.0)
        store = store_with(positioned(tick=100, entities=(start,)))
        skills, sender = skill_with(store)
        yaw, pitch = angle_to_degrees(
            dx=start.relative_x, dy=start.relative_y - EYE_HEIGHT_BLOCKS, dz=start.relative_z
        )
        closer = trader_entity(tick=120, at=4.0)
        yaw2, pitch2 = angle_to_degrees(
            dx=closer.relative_x, dy=closer.relative_y - EYE_HEIGHT_BLOCKS, dz=closer.relative_z
        )
        queued = [
            positioned(tick=110, yaw=yaw, pitch=pitch, entities=(start,)),
            positioned(tick=120, entities=(closer,)),
            positioned(tick=130, yaw=yaw2, pitch=pitch2, entities=(closer,)),
            positioned(tick=140, entities=(trader_entity(tick=140, at=2.0),)),
        ]
        moves_sent = 0

        def answer(message_type: str) -> None:
            nonlocal moves_sent
            if message_type == MOVE_INPUT_TYPE:
                moves_sent += 1
                if moves_sent % 2 == 0:
                    # The release of each walk; nothing new enters the world for it.
                    return
            if message_type in (AIM_INPUT_TYPE, MOVE_INPUT_TYPE) and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.approach_entity(
            authority=authority(),
            target_entity_type="minecraft:wandering_trader",
            stop_within=2.5,
            timeout_ns=10_000_000_000,
        )

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 140
        assert outcome.details["target"] == "minecraft:wandering_trader"
        assert outcome.details["distance_blocks"] == "2.00"
        assert outcome.details["steps"] == "2"
        moves = [message for kind, message in sender.sent if kind == MOVE_INPUT_TYPE]
        # Two steps walked and the key let go after each: [hold, release] twice, each walk
        # the longest the remaining budget supports rather than a fixed stride.
        assert [message.forward for message in moves] == [1.0, 0.0, 1.0, 0.0]  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_approach_entity_concludes_by_name_on_refusals_and_a_body_already_within() -> None:
    async def scenario() -> None:
        empty_store = store_with(reading(tick=100))
        empty, empty_sender = skill_with(empty_store)
        outcome = await empty.approach_entity(authority=authority(), timeout_ns=1_000_000_000)
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "APPROACH_ENTITY_NOT_VISIBLE"
        assert empty_sender.sent == []

        inside_store = store_with(positioned(tick=100, entities=(trader_entity(tick=100, at=2.0),)))
        inside, inside_sender = skill_with(inside_store)
        outcome = await inside.approach_entity(authority=authority(), timeout_ns=1_000_000_000)
        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.details["steps"] == "0"
        assert inside_sender.sent == []

        bad_stop, bad_sender = skill_with(
            store_with(positioned(tick=100, entities=(trader_entity(tick=100, at=6.0),)))
        )
        outcome = await bad_stop.approach_entity(
            authority=authority(), stop_within=0.1, timeout_ns=1_000_000_000
        )
        assert outcome.reason == "APPROACH_STOP_INVALID"
        assert bad_sender.sent == []

    asyncio.run(scenario())


def test_trade_selects_the_row_then_quick_moves_the_result_and_confirms_on_the_payout() -> None:
    """The whole trade: a button click naming the row (the screen's vocabulary), then a
    quick move on the merchant's result slot -- and CONFIRMED only when a later reading
    shows the ask down and the payout up on one synced revision."""

    async def scenario() -> None:
        store = store_with(
            reading(
                tick=100,
                gui=merchant_gui(),
                inventory_value=inventory(100, (0, "minecraft:emerald", 5)),
            )
        )
        skills, sender = skill_with(store)
        after_select = reading(
            tick=110,
            gui=merchant_gui(),
            inventory_value=inventory(100, (0, "minecraft:emerald", 5)),
        )
        paid = reading(
            tick=130,
            gui=merchant_gui(),
            inventory_value=inventory(130, (0, "minecraft:emerald", 2), (1, "minecraft:bread", 2)),
        )
        queued = [after_select, paid]

        def answer(message_type: str) -> None:
            if message_type == GUI_CLICK_INPUT_TYPE and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.trade(offer_index=0, authority=authority(), timeout_ns=5_000_000_000)

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.post_tick == 130
        assert outcome.details["clicks"] == "offer_select+result_quick_move"
        assert outcome.details["offer_index"] == "0"
        assert outcome.details["sell_item_id"] == "minecraft:bread"
        assert outcome.details["sell_count_before"] == "0"
        assert outcome.details["sell_count_after"] == "2"
        clicks = [message for kind, message in sender.sent if kind == GUI_CLICK_INPUT_TYPE]
        assert clicks[0].WhichOneof("click") == "button"  # type: ignore[attr-defined]
        assert clicks[0].button.button_id == 0  # type: ignore[attr-defined]
        assert clicks[1].WhichOneof("click") == "slot"  # type: ignore[attr-defined]
        assert clicks[1].slot.slot_id == 2  # type: ignore[attr-defined]
        assert clicks[1].slot.mode == control_pb2.SLOT_CLICK_MODE_QUICK_MOVE  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_trade_refuses_by_name_outside_the_rows_it_read() -> None:
    async def scenario() -> None:
        closed, closed_sender = skill_with(store_with(reading(tick=100)))
        outcome = await closed.trade(offer_index=0, authority=authority(), timeout_ns=1_000_000_000)
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "TRADE_SCREEN_NOT_OPEN"
        assert closed_sender.sent == []

        open_store = store_with(reading(tick=100, gui=merchant_gui()))
        opn, opn_sender = skill_with(open_store)
        outcome = await opn.trade(offer_index=7, authority=authority(), timeout_ns=1_000_000_000)
        assert outcome.reason == "TRADE_OFFER_UNKNOWN"
        assert opn_sender.sent == []

        empty_bag, bag_sender = skill_with(store_with(reading(tick=100, gui=merchant_gui())))
        outcome = await empty_bag.trade(
            offer_index=0, authority=authority(), timeout_ns=1_000_000_000
        )
        assert outcome.reason == "TRADE_INSUFFICIENT_MATERIALS"
        assert bag_sender.sent == []

    asyncio.run(scenario())


def test_look_at_entity_faces_the_named_kind_and_confirms_on_arrival() -> None:
    async def scenario() -> None:
        slime = slime_entity(tick=100, at=2.5)
        pig_body = EntityCandidate(
            observation_id="pig-100",
            entity_type="minecraft:pig",
            relative_x=1.0,
            relative_y=0.0,
            relative_z=0.0,
            line_of_sight=True,
        )
        store = store_with(positioned(tick=100, entities=(pig_body, slime)))
        skills, sender = skill_with(store)
        yaw, pitch = angle_to_degrees(
            dx=slime.relative_x,
            dy=slime.relative_y - EYE_HEIGHT_BLOCKS,
            dz=slime.relative_z,
        )
        queued = [positioned(tick=110, yaw=yaw, pitch=pitch, entities=(pig_body, slime))]

        def answer(message_type: str) -> None:
            if message_type == AIM_INPUT_TYPE and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.look_at_entity(
            authority=authority(),
            target_entity_type="minecraft:slime",
            timeout_ns=5_000_000_000,
        )

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.details["target"] == "minecraft:slime"
        aims = [message for kind, message in sender.sent if kind == AIM_INPUT_TYPE]
        assert aims[0].yaw_degrees == pytest.approx(yaw)  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_fight_back_refuses_by_name_without_a_target_or_with_a_bad_swing() -> None:
    async def scenario() -> None:
        empty, empty_sender = skill_with(store_with(reading(tick=100)))
        outcome = await empty.fight_back(authority=authority(), timeout_ns=1_000_000_000)
        assert outcome.result is ActionResultClass.FAILED
        assert outcome.reason == "FIGHT_THREAT_NOT_VISIBLE"
        assert empty_sender.sent == []

        far = store_with(positioned(tick=100, entities=(slime_entity(tick=100, at=5.0),)))
        far_skills, far_sender = skill_with(far)
        outcome = await far_skills.fight_back(authority=authority(), timeout_ns=1_000_000_000)
        assert outcome.reason == "FIGHT_THREAT_OUT_OF_REACH"
        assert far_sender.sent == []

        near = store_with(positioned(tick=100, entities=(slime_entity(tick=100),)))
        near_skills, near_sender = skill_with(near)
        for swing in (0.2, 9.0, float("nan")):
            outcome = await near_skills.fight_back(
                authority=authority(), swing_seconds=swing, timeout_ns=1_000_000_000
            )
            assert outcome.result is ActionResultClass.FAILED, swing
            assert outcome.reason == "FIGHT_SWING_INVALID", swing
        assert near_sender.sent == []

    asyncio.run(scenario())


def test_fight_back_reads_unknown_when_the_entity_is_still_rendered() -> None:
    async def scenario() -> None:
        slime = slime_entity(tick=100)
        store = store_with(positioned(tick=100, entities=(slime,)))
        skills, sender = skill_with(store)
        yaw, pitch = angle_to_degrees(
            dx=slime.relative_x,
            dy=slime.relative_y - EYE_HEIGHT_BLOCKS,
            dz=slime.relative_z,
        )
        # The SAME entity (same observation_id -- the uuid the wire uses) still rendered:
        # the swings ran and the thing is still there, so nothing is confirmed.
        queued = [
            positioned(tick=110, yaw=yaw, pitch=pitch, entities=(slime,), aim=slime_aim(110)),
            positioned(tick=120, entities=(slime,), aim=slime_aim(120)),
        ]

        def answer(message_type: str) -> None:
            if message_type in (AIM_INPUT_TYPE, MINE_INPUT_TYPE) and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.fight_back(
            authority=authority(), swing_seconds=1.0, timeout_ns=2_000_000_000
        )

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == "FIGHT_NOT_CONFIRMED"
        mines = [message for kind, message in sender.sent if kind == MINE_INPUT_TYPE]
        assert [message.mining for message in mines] == [True, False]  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_retreat_refuses_a_hold_outside_its_bounds() -> None:
    async def scenario() -> None:
        store = store_with(reading(tick=100))
        skills, sender = skill_with(store)

        for hold in (0.2, 5.5, float("nan")):
            outcome = await skills.retreat(
                authority=authority(), hold_seconds=hold, timeout_ns=1_000_000_000
            )
            assert outcome.result is ActionResultClass.FAILED, hold
            assert outcome.reason == "RETREAT_HOLD_INVALID", hold
        assert sender.sent == []

    asyncio.run(scenario())


# ------------------------------------------------- the weapon the fight brings to hand


def _armed_state(
    *,
    selected_slot: int,
    main_hand: str,
    yaw: float | None = None,
    pitch: float | None = None,
) -> SelfStateValue:
    return SelfStateValue(
        health=20.0,
        max_health=20.0,
        food=20,
        saturation=5.0,
        alive=True,
        yaw_degrees=yaw,
        pitch_degrees=pitch,
        selected_slot=selected_slot,
        main_hand_item_id=main_hand,
    )


@pytest.mark.parametrize("held_item", ["minecraft:wooden_pickaxe", "minecraft:oak_log"])
def test_fight_back_preserves_the_chosen_hand_even_with_a_stronger_weapon_available(
    held_item: str,
) -> None:
    """Attacking is not permission to choose equipment: the selected pickaxe stays
    in hand even when the local catalog rates a reachable axe higher."""

    async def scenario() -> None:
        slime = slime_entity(tick=100)
        armed = inventory(100, (1, held_item, 1), (2, "minecraft:stone_axe", 1))
        store = store_with(
            reading(
                tick=100,
                state_value=_armed_state(selected_slot=1, main_hand=held_item),
                inventory_value=armed,
                entities=(slime,),
            )
        )
        skills, sender = skill_with(store)
        yaw, pitch = angle_to_degrees(
            dx=slime.relative_x,
            dy=slime.relative_y - EYE_HEIGHT_BLOCKS,
            dz=slime.relative_z,
        )
        queued = [
            reading(
                tick=110,
                state_value=_armed_state(
                    selected_slot=1, main_hand=held_item, yaw=yaw, pitch=pitch
                ),
                inventory_value=armed,
                entities=(slime,),
                aim=slime_aim(110),
            ),
            reading(tick=120),
        ]

        def answer(message_type: str) -> None:
            if (
                message_type in (HOTBAR_SELECT_INPUT_TYPE, AIM_INPUT_TYPE, MINE_INPUT_TYPE)
                and queued
            ):
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.fight_back(
            authority=authority(), swing_seconds=1.0, timeout_ns=100_000_000
        )

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.details["weapon"] == held_item
        assert HOTBAR_SELECT_INPUT_TYPE not in sender.types()

    asyncio.run(scenario())


def test_fight_back_fights_bare_handed_when_no_curated_weapon_is_reachable() -> None:
    """No curated weapon in the hotbar's reach: no number key is pressed and the swing
    proceeds exactly as before, with the empty weapon name in the details saying why."""

    async def scenario() -> None:
        slime = slime_entity(tick=100)
        store = store_with(
            reading(
                tick=100,
                inventory_value=inventory(100, (0, "minecraft:oak_log", 3)),
                entities=(slime,),
            )
        )
        skills, sender = skill_with(store)
        yaw, pitch = angle_to_degrees(
            dx=slime.relative_x,
            dy=slime.relative_y - EYE_HEIGHT_BLOCKS,
            dz=slime.relative_z,
        )
        queued = [
            positioned(tick=110, yaw=yaw, pitch=pitch, entities=(slime,), aim=slime_aim(110)),
            positioned(tick=120),
        ]

        def answer(message_type: str) -> None:
            if message_type in (AIM_INPUT_TYPE, MINE_INPUT_TYPE) and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer
        outcome = await skills.fight_back(
            authority=authority(), swing_seconds=1.0, timeout_ns=10_000_000_000
        )

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.details["weapon"] == ""
        assert sender.types()[0] != HOTBAR_SELECT_INPUT_TYPE

    asyncio.run(scenario())


def test_fight_back_does_not_select_a_weapon_even_when_aim_cannot_be_confirmed() -> None:
    """A missing aim confirmation cannot authorize an unrelated equipment change."""

    async def scenario() -> None:
        slime = slime_entity(tick=100)
        store = store_with(
            reading(
                tick=100,
                inventory_value=inventory(100, (2, "minecraft:stone_axe", 1)),
                entities=(slime,),
            )
        )
        skills, sender = skill_with(store)

        outcome = await skills.fight_back(
            authority=authority(), swing_seconds=1.0, timeout_ns=60_000_000
        )

        assert (outcome.result, outcome.reason) == (
            ActionResultClass.UNKNOWN,
            "NO_CONFIRMING_OBSERVATION",
        )
        assert "phase" not in outcome.details
        assert HOTBAR_SELECT_INPUT_TYPE not in sender.types()
        assert sender.types()[0] == AIM_INPUT_TYPE

    asyncio.run(scenario())


def test_fight_back_waits_bounded_for_a_body_to_come_into_reach() -> None:
    """A body visible but just out of reach is a body that may be one hop away. The step
    spends its own window asking the newest reading again; when one reports it in reach,
    the swing follows from that frame and confirms through the same world sentence."""

    async def scenario() -> None:
        far = slime_entity(tick=100, at=5.0)
        near = slime_entity(tick=200, at=2.0)
        store = store_with(positioned(tick=100, entities=(far,)))
        skills, sender = skill_with(store)
        yaw, pitch = angle_to_degrees(
            dx=near.relative_x,
            dy=near.relative_y - EYE_HEIGHT_BLOCKS,
            dz=near.relative_z,
        )
        queued = [
            positioned(
                tick=210,
                yaw=yaw,
                pitch=pitch,
                entities=(near,),
                aim=slime_aim(210, entity_id="slime-200"),
            ),
            positioned(tick=220),
        ]

        def answer(message_type: str) -> None:
            if message_type in (AIM_INPUT_TYPE, MINE_INPUT_TYPE) and queued:
                store.admit(queued.pop(0), ())

        sender.on_send = answer

        async def admit_near() -> None:
            store.admit(positioned(tick=200, entities=(near,)), ())

        task = asyncio.create_task(admit_near())
        outcome = await skills.fight_back(
            authority=authority(), swing_seconds=1.0, timeout_ns=3_000_000_000
        )
        await task

        assert outcome.result is ActionResultClass.CONFIRMED
        assert outcome.details["target"] == "minecraft:slime"
        mines = [message for kind, message in sender.sent if kind == MINE_INPUT_TYPE]
        assert [message.mining for message in mines] == [True, False]  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_fight_back_refuses_by_name_when_nothing_enters_reach_within_the_window() -> None:
    """The wait is bounded by the step's own window: a threat that never comes into
    reach is the same named refusal, decided on the latest reading."""

    async def scenario() -> None:
        far = slime_entity(tick=100, at=5.0)
        store = store_with(positioned(tick=100, entities=(far,)))
        skills, sender = skill_with(store)

        outcome = await skills.fight_back(
            authority=authority(), swing_seconds=1.0, timeout_ns=60_000_000
        )

        assert (outcome.result, outcome.reason) == (
            ActionResultClass.FAILED,
            "FIGHT_THREAT_OUT_OF_REACH",
        )
        assert sender.types() == []

    asyncio.run(scenario())
