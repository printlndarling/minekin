"""Time-of-day names over the absolute world clock the client reports.

`WorldObservation.game_tick` is the client world's own time (`ClientWorld.getTime()`): the
count of ticks since the world was made, repeating a 24000-tick day cycle. That reading is the
whole clock a player has — the sky darkening, not a hidden schedule — so naming the band is a
look at public state, and the number itself stays untouched beside the name.

The bands are the vanilla sky's own: full day until 12000, dusk to 13000 (shade is already dark
enough for hostiles to spawn in it), night to 23000, dawn back to day at 24000/0. These are
named bands, not spawn guarantees: spawning is the client's light-level decision, and this
module refuses to guess it from the clock alone. A survival behaviour treats "night" as "the
outdoors is a place where threats may appear unseen", never as "a monster exists now".
"""

from __future__ import annotations

from typing import Final

DAY_CYCLE_TICKS: Final = 24_000
SUNSET_START_TICK: Final = 12_000
NIGHT_START_TICK: Final = 13_000
DAWN_START_TICK: Final = 23_000


def time_of_day(game_tick: int | None) -> str | None:
    """The named band this world tick falls in, or None when the reading never happened.

    The tick is taken modulo the day cycle, so a world that has run for several in-game days
    reads exactly as a fresh one at the same time of day.
    """
    if game_tick is None:
        return None
    phase = game_tick % DAY_CYCLE_TICKS
    if phase < SUNSET_START_TICK:
        return "day"
    if phase < NIGHT_START_TICK:
        return "sunset"
    if phase < DAWN_START_TICK:
        return "night"
    return "sunrise"
