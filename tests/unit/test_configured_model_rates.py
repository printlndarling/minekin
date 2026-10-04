"""Saved rate settings price future ledgers, never rewrite provider bills or old runs."""

from pathlib import Path

import pytest

from gateway.config_write import config_read, save_from_request
from minekin_core.application.ports.clock import FakeClock
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.model_access import (
    MODEL_REQUEST_RATE_VARIABLE,
    MODEL_RESPONSE_RATE_VARIABLE,
    CallOutcome,
    cost_ledger_for,
    model_config,
)
from minekin_core.domain.operator_config import apply_operator_config, load_operator_config


def test_saved_rates_survive_reload_and_price_tokens_with_environment_precedence(
    tmp_path: Path,
) -> None:
    status, _ = save_from_request(
        tmp_path,
        body={
            "fields": {
                "model_provider": "openai_compatible",
                "model_base_url": "https://example.invalid/v1",
                "model_name": "test-model",
                "model_run_cost_cap": 100,
                "model_request_rate": 1_000_000,
                "model_response_rate": 2_000_000,
            }
        },
    )
    assert status == 200
    read = config_read(tmp_path, clock=FakeClock(), csrf_token="test-token")
    assert read["fields"]["model_request_rate"] == 1_000_000
    environment = {MODEL_RESPONSE_RATE_VARIABLE: "3000000"}
    apply_operator_config(load_operator_config(tmp_path), environment)
    ledger = cost_ledger_for(model_config(environment))
    ledger.record_call(
        "openai_compatible", "test-model", 1, CallOutcome.OK, request_tokens=10, response_tokens=20
    )
    assert ledger.spent == 70
    assert ledger.response_micro_per_million_tokens == 3_000_000
    # Subsequent changes create a new ledger; old readings keep their original rate.
    environment[MODEL_RESPONSE_RATE_VARIABLE] = "4000000"
    assert cost_ledger_for(model_config(environment)).response_micro_per_million_tokens == 4_000_000
    assert ledger.spent == 70


def test_zero_is_explicit_and_default_rate_is_not_overridden_by_an_unset_field(
    tmp_path: Path,
) -> None:
    status, _ = save_from_request(tmp_path, body={"fields": {"model_request_rate": 0}})
    assert status == 200
    environment = {
        "MINEKIN_MODEL_PROVIDER": "openai_compatible",
        "MINEKIN_MODEL_BASE_URL": "https://example.invalid/v1",
        "MINEKIN_MODEL": "test",
    }
    apply_operator_config(load_operator_config(tmp_path), environment)
    config = model_config(environment)
    assert config.request_micro_per_million_tokens == 0
    assert config.response_micro_per_million_tokens == 10_000


@pytest.mark.parametrize("bad", [-1, True, "1000", 1.5, 1_000_000_001])
def test_bad_saved_rates_are_refused_without_replacing_valid_configuration(
    tmp_path: Path, bad: object
) -> None:
    assert save_from_request(tmp_path, body={"fields": {"model_request_rate": 200}})[0] == 200
    assert save_from_request(tmp_path, body={"fields": {"model_request_rate": bad}})[0] == 400
    assert load_operator_config(tmp_path).model_request_rate == 200


@pytest.mark.parametrize("bad", ["-1", "1.5", "1000000001", "sk-secret-canary"])
def test_bad_environment_rates_fail_before_call_and_do_not_echo_value(bad: str) -> None:
    with pytest.raises(MinekinError) as caught:
        model_config(
            {
                "MINEKIN_MODEL_PROVIDER": "openai_compatible",
                "MINEKIN_MODEL_BASE_URL": "https://example.invalid/v1",
                "MINEKIN_MODEL": "test",
                MODEL_REQUEST_RATE_VARIABLE: bad,
            }
        )
    assert "MODEL_NUMBER_INVALID" in caught.value.safe_message
    assert "sk-secret-canary" not in caught.value.safe_message
