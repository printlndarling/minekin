"""A refused live probe must not claim that local actions replaced the model."""

import pytest
from tools import probe_real_model_decision as probe

from minekin_core.domain.model_access import (
    CostLedger,
    DecisionRequest,
    ModelConfig,
    ModelUnavailable,
    UnavailableReason,
)


def test_provider_rejection_is_reported_as_a_hold_without_claiming_local_fallback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Provider:
        def decide(self, request: DecisionRequest) -> ModelUnavailable:
            return ModelUnavailable(UnavailableReason.PROVIDER_STATUS, 400)

    monkeypatch.setattr(probe.config, "load_local_environment", lambda: None)
    monkeypatch.setattr(probe, "model_config", lambda: ModelConfig(provider="openai_compatible"))

    def provider_for(config: ModelConfig, *, ledger: CostLedger) -> Provider:
        return Provider()

    monkeypatch.setattr(probe, "model_provider_for", provider_for)
    assert probe.main([]) == 1
    captured = capsys.readouterr()
    assert "kind=HOLD source=none" in captured.err
    assert "refusal=PROVIDER_STATUS" in captured.err
    assert "no executable model decision" in captured.err
    assert "fell back locally" not in captured.err
    assert '"kind": "HOLD"' in captured.out
