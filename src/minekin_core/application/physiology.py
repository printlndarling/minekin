"""Bounded HUD sampling after the session admits a coherent player observation."""

from __future__ import annotations

from dataclasses import dataclass

from minekin_core.domain.perception import WorldObservationValue


@dataclass(slots=True)
class PhysiologySampler:
    generation: int | None = None
    last_tick: int | None = None

    def sample(self, reading: WorldObservationValue) -> dict[str, int | float] | None:
        # One sample per 100 game ticks, including an immediate first sample per
        # generation. Decisions still use every admitted frame in memory.
        if (
            self.generation == reading.generation
            and self.last_tick is not None
            and reading.game_tick - self.last_tick < 100
        ):
            return None
        self.generation, self.last_tick = reading.generation, reading.game_tick
        return {
            "health": reading.self_state.health,
            "max_health": reading.self_state.max_health,
            "food": reading.self_state.food,
            "game_tick": reading.game_tick,
            "generation": reading.generation,
        }
