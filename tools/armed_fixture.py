"""Test-only weapon preparation: give the probed kin a pair of weapons once it joined.

The fight's named lever reads *which* weapon the skill brought to hand, and the flat
controlled world hands out nothing: this fixture is where the weapons come from. It
gives a deliberately unequal pair -- a wooden pickaxe (curated damage 2) and a stone
axe (curated damage 9) -- so the run can say the table chose the bigger number rather
than merely choosing the only stack there was. Both land in the hotbar's first free
slots, where a number key can reach them.

Written once, when the probed player has joined, and confirmed off the server's own
`Gave ...` lines before the fixture reports ready: a run that reads an empty hand after
this fixture has said ready is a race this side did not leave open. Unlike the meal
fixture there is no status effect to drain first -- weapons are not consumed by being
held, and the first plan step (a walk) gives the gives seconds of lead time -- so the
state machine is two phases: join, then both acks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: What the fixture gives, in order: (item id, the display name vanilla prints in its
#: `Gave 1 [<display>] to <player>` acknowledgement). The pair is unequal on purpose;
#: see the module docstring.
ARMORY: tuple[tuple[str, str], ...] = (
    ("minecraft:wooden_pickaxe", "Wooden Pickaxe"),
    ("minecraft:stone_axe", "Stone Axe"),
)


@dataclass(slots=True)
class ArmedFixture:
    player: str
    phase: str = "waiting_join"
    armed: tuple[str, ...] | None = None
    _deadline: float | None = None
    _cursor: int = 0
    _pending: dict[str, re.Pattern[str]] = field(init=False)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", self.player):
            raise ValueError("A checked vanilla player name is required")
        self._pending = {
            display: re.compile(rf"Gave 1 \[{re.escape(display)}\] to {re.escape(self.player)}$")
            for _item_id, display in ARMORY
        }

    def begin(self, log: str, now: float) -> list[str]:
        if self.phase != "waiting_join":
            raise ValueError("Preparation can begin only once")
        self.phase, self._deadline, self._cursor = "arming", now + 60, len(log)
        return [f"give {self.player} {item_id} 1" for item_id, _display in ARMORY]

    def update(self, log: str, now: float) -> list[str]:
        if self.phase in {"waiting_join", "ready"}:
            return []
        if self._deadline is not None and now >= self._deadline:
            raise TimeoutError(f"Weapon preparation timed out in phase {self.phase}")
        end = log.rfind("\n") + 1
        fresh = log[self._cursor : end].splitlines()
        self._cursor = max(self._cursor, end)
        for line in fresh:
            for display, pattern in tuple(self._pending.items()):
                if pattern.search(line) is not None:
                    del self._pending[display]
        if not self._pending:
            self.phase = "ready"
            self.armed = tuple(display for _item_id, display in ARMORY)
        return []
