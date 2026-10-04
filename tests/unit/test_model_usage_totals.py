"""Runtime accounting stays numeric, bounded, explicit about missing usage."""

from pathlib import Path

import pytest

from gateway.readmodel import build_snapshot
from gateway_support import joined_run, record
from minekin_core.adapters.sqlite.session_log import SKILL_STEP_RECORDED
from minekin_core.application.ports.clock import FakeClock
from minekin_core.domain.model_access import CallOutcome, CostLedger, UnavailableReason
from minekin_core.domain.model_usage import ModelUsageTotals


def ledger() -> CostLedger:
    value = CostLedger(
        1000,
        request_micro_per_million_tokens=1_000_000,
        response_micro_per_million_tokens=2_000_000,
    )
    value.record_call(
        "openai_compatible",
        "canary-secret",
        1,
        CallOutcome.OK,
        request_tokens=10,
        response_tokens=20,
    )
    value.record_call("openai_compatible", "canary-secret", 2, CallOutcome.UNAVAILABLE)
    value.record_call(
        "openai_compatible",
        "canary-secret",
        3,
        CallOutcome.UNAVAILABLE,
        reason=UnavailableReason.RUN_COST_CAP_REACHED,
    )
    return value


def test_capture_reports_partial_estimate_without_exporting_model_identity() -> None:
    totals = ModelUsageTotals.capture(ledger())
    assert totals.calls == 2
    assert totals.spent_estimate_micro == 50
    assert totals.incomplete_usage_calls == 1
    assert totals.cap_refusals == 1
    assert ModelUsageTotals.from_payload(totals.as_document()) == totals
    assert "canary-secret" not in str(totals.as_document()) + totals.summary()
    assert "不是供应商账单" in totals.summary()


@pytest.mark.parametrize(
    "changes",
    [
        {"calls": True},
        {"calls": -1},
        {"calls": 2**63},
        {"calls": "2"},
        {"incomplete_usage_calls": 3},
        {"run_cap_micro": 0},
        {"schema_version": True},
        {"basis": "actual_bill"},
        {"api_key": "canary-secret"},
    ],
)
def test_invalid_or_secret_bearing_payload_is_not_projected(changes: dict[str, object]) -> None:
    payload = ModelUsageTotals.capture(ledger()).as_document()
    payload.update(changes)
    assert ModelUsageTotals.from_payload(payload) is None


def test_unsealed_step_carries_its_own_cost_without_borrowing_other_runs(tmp_path: Path) -> None:
    joined_run(tmp_path)
    record(
        tmp_path,
        SKILL_STEP_RECORDED,
        {
            "step_index": 1,
            "skill": "turn_to",
            "result": "CONFIRMED",
            "model_usage": ModelUsageTotals.capture(ledger()).as_document(),
        },
    )
    snapshot = build_snapshot(tmp_path, clock=FakeClock())
    cost = snapshot["skillSteps"]["value"]["modelCost"]
    assert "账本调用 2" in cost["value"]
    assert "50/1000" in cost["value"]
    assert "usage 不完整 1" in cost["value"]
    # A later row lacking accounting must not inherit an older row's numeric claim.
    record(
        tmp_path, SKILL_STEP_RECORDED, {"step_index": 2, "skill": "turn_to", "result": "UNKNOWN"}
    )
    later = build_snapshot(tmp_path, clock=FakeClock())
    assert later["skillSteps"]["value"]["modelCost"]["gap"]["status"] == "not_wired"


def test_bad_usage_is_unknown_not_free(tmp_path: Path) -> None:
    joined_run(tmp_path)
    record(
        tmp_path,
        SKILL_STEP_RECORDED,
        {
            "step_index": 1,
            "skill": "turn_to",
            "result": "CONFIRMED",
            "model_usage": {"calls": 0},
        },
    )
    snapshot = build_snapshot(tmp_path, clock=FakeClock())
    assert snapshot["skillSteps"]["value"]["modelCost"]["gap"]["status"] == "unknown"
