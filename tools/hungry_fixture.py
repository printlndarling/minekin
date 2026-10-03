"""Test-only meal preparation: observe hunger, confirm clearing, then serve food."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class HungryFixture:
    player: str
    phase: str = "waiting_join"
    food: int | None = None
    _deadline: float | None = None
    _last_query: float = -1
    _cursor: int = 0
    _food_pattern: re.Pattern[str] = field(init=False)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", self.player):
            raise ValueError("A checked vanilla player name is required")
        self._food_pattern = re.compile(
            rf"(?<![A-Za-z0-9_]){re.escape(self.player)} has the following entity data: ([0-9]+)$"
        )

    def begin(self, log: str, now: float) -> list[str]:
        if self.phase != "waiting_join":
            raise ValueError("Preparation can begin only once")
        self.phase, self._deadline, self._cursor = "draining", now + 60, len(log)
        self._last_query = now
        return [
            f"effect give {self.player} minecraft:hunger 10 200",
            f"data get entity {self.player} foodLevel",
        ]

    def update(self, log: str, now: float) -> list[str]:
        if self.phase in {"waiting_join", "ready"}:
            return []
        if self._deadline is not None and now >= self._deadline:
            raise TimeoutError(f"Meal preparation timed out in phase {self.phase}")
        end = log.rfind("\n") + 1
        fresh = log[self._cursor : end].splitlines()
        self._cursor = max(self._cursor, end)
        if self.phase == "draining":
            for line in fresh:
                match = self._food_pattern.search(line)
                if match is not None and 0 <= int(match[1]) <= 6:
                    self.food = int(match[1])
                    self.phase = "clearing"
                    return [f"effect clear {self.player} minecraft:hunger"]
            if now - self._last_query >= 0.25:
                self._last_query = now
                return [f"data get entity {self.player} foodLevel"]
        elif self.phase == "clearing":
            if any(line.endswith(f"Removed effect Hunger from {self.player}") for line in fresh):
                self.phase = "serving"
                return [f"give {self.player} minecraft:apple 3"]
        elif self.phase == "serving":
            if any(line.endswith(f"Gave 3 [Apple] to {self.player}") for line in fresh):
                self.phase = "ready"
        return []
