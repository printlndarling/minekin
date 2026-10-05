"""Weapon setup must not report ready until the server confirmed both gives."""

from __future__ import annotations

import pytest
from tools.armed_fixture import ArmedFixture


def test_arming_gives_both_weapons_once_and_reads_their_acks() -> None:
    fixture = ArmedFixture("minekin")
    assert fixture.begin("", 0) == [
        "give minekin minecraft:wooden_pickaxe 1",
        "give minekin minecraft:stone_axe 1",
    ]
    assert fixture.phase == "arming"
    assert fixture.update("", 0.1) == []
    log = "[Server thread/INFO]: Gave 1 [Wooden Pickaxe] to minekin\n"
    assert fixture.update(log, 0.2) == []
    assert fixture.phase == "arming"  # One ack is not the pair.
    log += "[Server thread/INFO]: Gave 1 [Stone Axe] to minekin\n"
    assert fixture.update(log, 0.3) == []
    assert fixture.phase == "ready"
    assert fixture.armed == ("Wooden Pickaxe", "Stone Axe")
    assert fixture.update(log, 100) == []


def test_wrong_item_count_and_recipient_do_not_confirm_a_give() -> None:
    fixture = ArmedFixture("minekin")
    fixture.begin("", 0)
    log = (
        "Gave 1 [Stone Pickaxe] to minekin\n"
        "Gave 64 [Wooden Pickaxe] to minekin\n"
        "Gave 1 [Stone Axe] to OtherKin\n"
    )
    fixture.update(log, 0.1)
    assert fixture.phase == "arming"


def test_partial_lines_are_read_only_after_completion() -> None:
    fixture = ArmedFixture("minekin")
    fixture.begin("", 0)
    log = "Gave 1 [Wooden Pickaxe] to minekin"
    assert fixture.update(log, 0.1) == []
    assert fixture.phase == "arming"
    log += "\n"
    fixture.update(log, 0.2)
    assert fixture.phase == "arming"  # Only the pickaxe landed so far.
    log += "Gave 1 [Stone Axe] to minekin\n"
    fixture.update(log, 0.3)
    assert fixture.phase == "ready"


def test_the_arming_phase_has_a_bounded_deadline() -> None:
    fixture = ArmedFixture("minekin")
    fixture.begin("", 10)
    with pytest.raises(TimeoutError, match="arming"):
        fixture.update("", 10 + 61)


def test_begin_is_single_use_and_the_name_is_checked() -> None:
    fixture = ArmedFixture("minekin")
    fixture.begin("", 0)
    with pytest.raises(ValueError, match="once"):
        fixture.begin("", 0)
    for bad in ("x", "bad name", "a" * 17):
        with pytest.raises(ValueError, match="vanilla player name"):
            ArmedFixture(bad)
