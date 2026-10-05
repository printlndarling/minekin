"""The day-cycle bands the mind and its answerer share."""

import pytest

from minekin_core.domain.daylight import time_of_day


@pytest.mark.parametrize(
    ("tick", "band"),
    [
        (0, "day"),
        (1_000, "day"),
        (11_999, "day"),
        (12_000, "sunset"),
        (12_999, "sunset"),
        (13_000, "night"),
        (15_000, "night"),
        (22_999, "night"),
        (23_000, "sunrise"),
        (23_999, "sunrise"),
        (24_000, "day"),
    ],
)
def test_the_bands_meet_at_their_vanilla_ticks(tick: int, band: str) -> None:
    assert time_of_day(tick) == band


def test_a_multi_day_clock_reads_by_its_time_of_day_and_not_its_age() -> None:
    """`game_tick` counts from world creation; banding takes the day cycle's remainder, so the
    fourth day's noon reads as noon instead of day-count arithmetic leaking into a band name."""
    assert time_of_day(3 * 24_000 + 6_000) == "day"
    assert time_of_day(7 * 24_000 + 15_000) == "night"
    # The wrap: the same phase one day later is the same band.
    assert time_of_day(24_000 + 15_000) == time_of_day(15_000)


def test_a_reading_that_never_happened_has_no_band() -> None:
    assert time_of_day(None) is None
