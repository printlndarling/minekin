"""HUD recording respects admission, cadence, run boundaries and bounded public fields."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from typing import cast

import pytest

from gateway.readmodel import EventRow, self_state_group
from minekin_core.adapters.bridge.ipc import WORLD_OBSERVATION_TYPE, BridgeIpcHost
from minekin_core.adapters.bridge.world_observation import decode_world_observation
from minekin_core.adapters.sqlite.session_log import CLIENT_EXITED, PLAYER_STATE_OBSERVED
from minekin_core.application.physiology import PhysiologySampler
from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.cli import session_runtime
from minekin_core.domain.connection import ConnectionGenerations
from minekin_core.domain.ids import OpaqueId
from minekin_core.domain.perception import WorldObservationValue
from minekin_core.domain.session_state import SessionStateMachine
from minekin_core.generated.minekin.v1 import observation_pb2


def wire(
    tick: int = 100, *, generation: int = 1, health: float = 18
) -> observation_pb2.WorldObservation:
    return observation_pb2.WorldObservation(
        generation=generation,
        game_tick=tick,
        self=observation_pb2.SelfState(
            health=health, max_health=20, food=12, saturation=0, alive=True
        ),
        inventory=observation_pb2.InventorySummary(revision=tick),
    )


def test_hud_sampler_is_bounded_and_restarts_its_cadence_for_a_new_generation() -> None:
    sampler = PhysiologySampler()
    value = decode_world_observation(wire())
    assert sampler.sample(value) == {
        "health": 18,
        "max_health": 20,
        "food": 12,
        "game_tick": 100,
        "generation": 1,
    }
    assert sampler.sample(replace(value, game_tick=199)) is None
    assert sampler.sample(replace(value, game_tick=200)) is not None
    assert sampler.sample(replace(value, generation=2, game_tick=1)) is not None


def test_only_admitted_observations_reach_the_hud_callback() -> None:
    messages = iter(
        [wire(), wire(100), wire(110, generation=2), wire(120, health=float("nan")), wire(130)]
    )

    class Host:
        async def receive_event(self) -> object:
            try:
                message = next(messages)
            except StopIteration:
                raise EOFError("end of test stream") from None
            return SimpleNamespace(
                message=message, envelope=SimpleNamespace(message_type=WORLD_OBSERVATION_TYPE)
            )

    accepted: list[int] = []

    async def observed(reading: WorldObservationValue) -> None:
        accepted.append(reading.game_tick)

    async def run() -> None:
        connections = ConnectionGenerations()
        connections.begin(OpaqueId("controlled-profile"), "a" * 64)
        with pytest.raises(EOFError):
            await session_runtime._read_events(  # pyright: ignore[reportPrivateUsage]
                cast(BridgeIpcHost, Host()),
                SessionStateMachine(),
                connections,
                session_runtime._Progress(),  # pyright: ignore[reportPrivateUsage]
                None,
                None,
                None,
                None,
                world_observations=WorldObservationStore(),
                on_world_observation=observed,
            )

    asyncio.run(run())
    assert accepted == [100, 130]


def row(
    position: int,
    *,
    event_type: str = PLAYER_STATE_OBSERVED,
    run_id: str = "current",
    health: object = 18,
    food: object = 12,
) -> EventRow:
    return EventRow(
        position,
        f"event-{position}",
        event_type,
        "2026-10-04T00:00:00Z",
        run_id,
        "session",
        1,
        position,
        {"health": health, "max_health": 20, "food": food, "unexpected_secret": "canary"},
    )


def test_projection_exposes_only_hud_numbers_and_preserves_provenance() -> None:
    result = self_state_group([row(1)], "core://hud/current", alive=True)
    assert result["value"] == {"health": 18, "food": 12}
    assert result["sourceRef"] == "core://hud/current"
    assert result["observedAt"] == "2026-10-04T00:00:00Z"
    assert result["staleAfterMs"] == 10000
    assert "canary" not in str(result)


@pytest.mark.parametrize(
    "health,food", [(float("nan"), 12), (True, 12), (21, 12), (18, 21), (18, True)]
)
def test_malformed_hud_records_are_not_current_facts(health: object, food: object) -> None:
    assert (
        self_state_group([row(1, health=health, food=food)], "hud", alive=True)["status"]
        == "unknown"
    )


def test_closed_clients_and_new_runs_do_not_reuse_old_hud_values() -> None:
    sample = row(1)
    assert self_state_group([sample], "hud", alive=False)["status"] == "unknown"
    ended = row(2, event_type=CLIENT_EXITED)
    assert self_state_group([sample, ended], "hud", alive=True)["status"] == "unknown"
    next_run = row(3, event_type="SessionProcessStarted", run_id="new")
    assert self_state_group([sample, ended, next_run], "hud", alive=True)["status"] == "unavailable"
