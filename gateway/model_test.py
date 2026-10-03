"""One explicit, bounded model decision probe; no decision reaches the game."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from gateway.identity import refusal
from minekin_core.adapters.model import model_provider_for
from minekin_core.config import load_local_environment
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.model_access import (
    Decision,
    DecisionRequest,
    cost_ledger_for,
    model_config,
)
from minekin_core.domain.operator_config import apply_operator_config, load_operator_config

MODEL_TEST_PATH = "/api/v1/dashboard/model/test"
SCHEMA = "kin-dashboard-model-test/1.0.0"
MAX_BODY_BYTES = 128
MAX_TIMEOUT_MS = 20_000


def test_from_request(
    root: Path,
    *,
    body: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    if set(body) != {"confirm"} or body.get("confirm") is not True:
        return refusal(400, "invalid_request", "confirm=true is required", schema=SCHEMA)
    started = time.monotonic_ns()
    source = dict(os.environ if environ is None else environ)
    try:
        load_local_environment(source)
        apply_operator_config(load_operator_config(root), source)
        config = model_config(source)
    except (MinekinError, OSError, UnicodeError):
        return refusal(
            400,
            "invalid_model_config",
            "Model configuration could not be read or validated.",
            schema=SCHEMA,
        )
    config = replace(config, timeout_ms=min(config.timeout_ms, MAX_TIMEOUT_MS))
    ledger = cost_ledger_for(config)
    provider = model_provider_for(config, source, ledger)
    request = DecisionRequest(
        observation_ref="dashboard:model-connection-test",
        active_goal=(
            "Connection test only. Choose turn_to with yaw_degrees=0, pitch_degrees=0. "
            "No action will execute."
        ),
        feasible_skill_ids=("turn_to",),
        observation_summary={"connection_test": True, "game_actions_enabled": False},
        budget_remaining_micro=ledger.remaining(),
    )
    answer = provider.decide(request)
    return 200, {
        "schemaVersion": SCHEMA,
        "status": "connected" if isinstance(answer, Decision) else "unavailable",
        "reason": "" if isinstance(answer, Decision) else answer.reason.value,
        "elapsedMs": max(0, (time.monotonic_ns() - started) // 1_000_000),
        "timeoutMs": config.timeout_ms,
        "modelCalls": len(ledger.records),
        "estimatedCostMicro": ledger.spent,
    }
