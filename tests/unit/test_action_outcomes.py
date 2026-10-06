"""Per-action outcomes are bounded, newest-first, and matched by exact name."""

from __future__ import annotations

from minekin_core.application.action_outcomes import (
    ACCEPTED,
    FAILED,
    ActionOutcomeRegistry,
)


def test_the_newest_outcome_for_an_id_is_the_one_read_back() -> None:
    registry = ActionOutcomeRegistry()
    registry.record("a" * 32, status=ACCEPTED)
    registry.record("a" * 32, status=FAILED, reason_code="MINE_TARGET_NOT_AIMED")

    assert registry.latest("a" * 32) == (FAILED, "MINE_TARGET_NOT_AIMED")
    assert registry.refused("a" * 32, "MINE_TARGET_NOT_AIMED")
    # A different refusal name for the same id is not this one: the registry
    # never generalizes a reason.
    assert not registry.refused("a" * 32, "GUI_CONFLICT")
    assert registry.latest("b" * 32) is None


def test_the_registry_is_bounded_and_prunes_the_oldest_id() -> None:
    registry = ActionOutcomeRegistry()
    for index in range(ActionOutcomeRegistry.CAPACITY + 5):
        registry.record(f"{index:032d}", status=ACCEPTED)

    # The five oldest ids fell out; the newest is still readable.
    assert registry.latest(f"{0:032d}") is None
    assert registry.latest(f"{ActionOutcomeRegistry.CAPACITY + 4:032d}") == (ACCEPTED, "")


def test_a_re_touched_id_moves_to_the_newest_side() -> None:
    registry = ActionOutcomeRegistry()
    registry.record(f"{0:032d}", status=ACCEPTED)
    for index in range(1, ActionOutcomeRegistry.CAPACITY):
        registry.record(f"{index:032d}", status=ACCEPTED)
    # Touch the oldest again, then overflow by one: the second-oldest leaves.
    registry.record(f"{0:032d}", status=FAILED, reason_code="MINE_TARGET_NOT_AIMED")
    registry.record(f"{ActionOutcomeRegistry.CAPACITY:032d}", status=ACCEPTED)

    assert registry.latest(f"{0:032d}") == (FAILED, "MINE_TARGET_NOT_AIMED")
    assert registry.latest(f"{1:032d}") is None


def test_empty_ids_and_statuses_are_not_recorded() -> None:
    registry = ActionOutcomeRegistry()
    registry.record("", status=ACCEPTED)
    registry.record("a" * 32, status="")

    assert registry.latest("") is None
    assert registry.latest("a" * 32) is None
