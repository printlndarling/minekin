"""What recovery may replay, checked against the crash fixture that predicted it.

The fixture was committed before this policy existed, and it states what recovery
must do at its crash point. These tests read those expectations rather than
restating them, so the fixture is the contract and not decoration: change what
recovery does and one of these fails.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from minekin_core.application.ports.event_store import OutboxItem
from minekin_core.domain.recovery import (
    BUNDLE_FETCH,
    CONNECT_WORLD,
    INPUT_LEASE,
    MAX_ATTEMPTS,
    RELEASE_ALL,
    START_CLIENT,
    STOP_SESSION,
    RecoveryAction,
    recover_plan,
    recovery_action,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CRASH_FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "crash" / "pending-outbox.v1.json"

REVIEWED_EFFECTS = (
    BUNDLE_FETCH,
    START_CLIENT,
    CONNECT_WORLD,
    INPUT_LEASE,
    RELEASE_ALL,
    STOP_SESSION,
)


def _items(fixture: dict[str, Any]) -> list[OutboxItem]:
    return [
        OutboxItem(
            outbox_id=str(entry["outbox_id"]),
            effect_type=str(entry["effect_type"]),
            idempotency_key=str(entry["idempotency_key"]),
            payload=None,
            created_at_utc="2026-01-01T00:00:00Z",
            status=str(entry["status"]),
            attempts=int(entry["attempts"]),
        )
        for entry in fixture["outbox"]
    ]


def _fixture() -> dict[str, Any]:
    return json.loads(CRASH_FIXTURE.read_text(encoding="utf-8"))


def test_the_fixtures_three_expectations_are_what_the_policy_does() -> None:
    fixture = _fixture()
    expected = fixture["expected_recovery"]

    decisions = {decision.effect_type: decision for decision in recover_plan(_items(fixture))}

    # reconcile_client_process_identity: ask whether the client is still there
    # rather than starting another one.
    assert expected["reconcile_client_process_identity"] is True
    assert decisions["START_CLIENT"].action is RecoveryAction.RECONCILE
    assert decisions["START_CLIENT"].replayable is False

    # replay_input_lease: false. A lease is not persisted, so an item naming one
    # can only be a stale intent to press keys.
    assert expected["replay_input_lease"] is False
    assert recovery_action(INPUT_LEASE).action is RecoveryAction.INVALIDATE
    assert recovery_action(INPUT_LEASE).replayable is False

    # invalidate_historical_generation: true. The generation is over, and a
    # reconnect is a new one rather than a resumed one.
    assert expected["invalidate_historical_generation"] is True
    assert recovery_action(CONNECT_WORLD).action is RecoveryAction.INVALIDATE


@pytest.mark.parametrize("effect_type", REVIEWED_EFFECTS)
def test_every_reviewed_effect_is_decided_rather_than_refused(effect_type: str) -> None:
    """A reviewed effect that recovered as FAIL_CLOSED would stop every run."""

    decision = recovery_action(effect_type)

    assert decision.action is not RecoveryAction.FAIL_CLOSED, decision.reason
    assert decision.reason


def test_an_effect_this_build_does_not_know_is_refused() -> None:
    """The safe reading of "I do not know what this was going to do" is not "do it"."""

    decision = recovery_action("SOMETHING_FROM_A_LATER_VERSION")

    assert decision.action is RecoveryAction.FAIL_CLOSED
    assert not decision.replayable


def test_only_the_idempotent_effects_are_replayable() -> None:
    replayable = {
        effect_type for effect_type in REVIEWED_EFFECTS if recovery_action(effect_type).replayable
    }

    assert replayable == {BUNDLE_FETCH, RELEASE_ALL, STOP_SESSION}


def test_an_effect_that_keeps_failing_stops_being_retried() -> None:
    """Retrying forever is a way of never failing cleanly."""

    assert recovery_action(BUNDLE_FETCH, MAX_ATTEMPTS - 1).action is RecoveryAction.RETRY
    assert recovery_action(BUNDLE_FETCH, MAX_ATTEMPTS).action is RecoveryAction.FAIL_CLOSED


@pytest.mark.parametrize("effect_type", [CONNECT_WORLD, INPUT_LEASE])
def test_an_effect_that_may_never_be_replayed_is_not_retried_later_either(
    effect_type: str,
) -> None:
    """Attempts do not turn an invalidated effect into a retryable one."""

    assert recovery_action(effect_type, MAX_ATTEMPTS * 10).action is RecoveryAction.INVALIDATE


def test_a_negative_attempt_count_is_refused() -> None:
    with pytest.raises(ValueError, match="attempts"):
        recovery_action(START_CLIENT, -1)


def test_the_plan_keeps_the_order_the_ledger_holds() -> None:
    items = [
        OutboxItem(
            outbox_id=f"outbox-{index}",
            effect_type=effect_type,
            idempotency_key=f"key-{index}",
            payload=None,
            created_at_utc="2026-01-01T00:00:00Z",
        )
        for index, effect_type in enumerate(REVIEWED_EFFECTS)
    ]

    assert [decision.effect_type for decision in recover_plan(items)] == list(REVIEWED_EFFECTS)
