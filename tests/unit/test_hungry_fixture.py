"""Meal setup must never serve food while its drain effect remains active."""

from __future__ import annotations

import pytest
from tools.hungry_fixture import HungryFixture


def test_preparation_waits_for_low_food_clear_ack_and_give_ack() -> None:
    fixture = HungryFixture("Kin")
    log = "Kin has the following entity data: 0\n"
    assert fixture.begin(log, 0) == [
        "effect give Kin minecraft:hunger 10 200",
        "data get entity Kin foodLevel",
    ]
    assert fixture.update(log, 0.1) == []  # Old low-food evidence cannot advance it.
    log += "[Server thread/INFO]: Kin has the following entity data: 7\n"
    assert fixture.update(log, 0.2) == []
    log += "[Server thread/INFO]: Kin has the following entity data: 6\n"
    assert fixture.update(log, 0.3) == ["effect clear Kin minecraft:hunger"]
    assert fixture.phase == "clearing"
    assert fixture.update(log, 5) == []  # Time alone does not confirm clearing.
    log += "[Server thread/INFO]: Removed effect Hunger from Kin\n"
    assert fixture.update(log, 5.1) == ["give Kin minecraft:apple 3"]
    assert fixture.phase == "serving"
    assert fixture.update(log, 5.2) == []
    log += "[Server thread/INFO]: Gave 3 [Apple] to Kin\n"
    assert fixture.update(log, 5.3) == []
    assert fixture.phase == "ready"
    assert fixture.food == 6
    assert fixture.update(log, 100) == []


@pytest.mark.parametrize("value", ["-1", "21", "7", "6.5", "0 trailing"])
def test_invalid_or_insufficient_food_never_triggers_clear(value: str) -> None:
    fixture = HungryFixture("Kin")
    fixture.begin("", 0)
    fixture.update(f"Kin has the following entity data: {value}\n", 0.1)
    assert fixture.phase == "draining"


def test_partial_lines_are_read_only_after_completion() -> None:
    fixture = HungryFixture("Kin")
    fixture.begin("", 0)
    log = "Kin has the following entity data: 6"
    assert fixture.update(log, 0.1) == []
    assert fixture.update(log + "\n", 0.2) == ["effect clear Kin minecraft:hunger"]


def test_wrong_player_and_wrong_effect_do_not_confirm_clear() -> None:
    fixture = HungryFixture("Kin")
    fixture.begin("", 0)
    log = "OtherKin has the following entity data: 0\n"
    fixture.update(log, 0.1)
    assert fixture.phase == "draining"
    log += "Kin has the following entity data: 6\n"
    fixture.update(log, 0.2)
    log += "Removed effect Speed from Kin\nRemoved effect Hunger from OtherKin\n"
    assert fixture.update(log, 0.3) == []
    assert fixture.phase == "clearing"


def test_wrong_item_and_recipient_do_not_confirm_give() -> None:
    fixture = HungryFixture("Kin")
    fixture.begin("", 0)
    log = "Kin has the following entity data: 6\n"
    fixture.update(log, 0.1)
    log += "Removed effect Hunger from Kin\n"
    fixture.update(log, 0.2)
    log += "Gave 3 [Stick] to Kin\nGave 3 [Apple] to OtherKin\n"
    fixture.update(log, 0.3)
    assert fixture.phase == "serving"


@pytest.mark.parametrize("phase", ["draining", "clearing", "serving"])
def test_each_phase_has_a_shared_bounded_deadline(phase: str) -> None:
    fixture = HungryFixture("Kin")
    fixture.begin("", 10)
    fixture.phase = phase
    with pytest.raises(TimeoutError, match=phase):
        fixture.update("", 70)


def test_queries_are_bounded_and_begin_is_single_use() -> None:
    fixture = HungryFixture("Kin")
    assert fixture.update("", 0) == []
    fixture.begin("", 0)
    assert fixture.update("", 0.24) == []
    assert fixture.update("", 0.25) == ["data get entity Kin foodLevel"]
    assert fixture.update("", 0.26) == []
    with pytest.raises(ValueError, match="only once"):
        fixture.begin("", 1)
