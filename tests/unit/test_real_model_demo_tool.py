"""The model demo loader forwards literal values without executing configuration."""

from pathlib import Path

import pytest
from tools.run_real_model_demo import model_environment


def test_model_environment_selects_model_and_only_referenced_credential(tmp_path: Path) -> None:
    config = tmp_path / "model.env"
    config.write_text(
        "MINEKIN_MODEL_PROVIDER=off\n"
        'MINEKIN_MODEL="example model"\n'
        "MINEKIN_MODEL_API_KEY_ENV=SELECTED_KEY\n"
        'SELECTED_KEY="secret with spaces"\n'
        "UNRELATED_KEY=other-secret\n"
    )
    assert model_environment(config) == {
        "MINEKIN_MODEL_PROVIDER": "off",
        "MINEKIN_MODEL": "example model",
        "MINEKIN_MODEL_API_KEY_ENV": "SELECTED_KEY",
        "SELECTED_KEY": "secret with spaces",
    }


def test_model_environment_preserves_shell_expression_as_literal(tmp_path: Path) -> None:
    config = tmp_path / "model.env"
    marker = tmp_path / "must-not-exist"
    expression = f"$(touch {marker})"
    config.write_text(f'MINEKIN_MODEL="{expression}"\n')
    assert model_environment(config)["MINEKIN_MODEL"] == expression
    assert not marker.exists()


@pytest.mark.parametrize(
    "credential_name", ["PATH", "PYTHONPATH", "HOME", "CODEX_HOME", "bad-name"]
)
def test_model_environment_refuses_process_control_name(
    tmp_path: Path, credential_name: str
) -> None:
    config = tmp_path / "model.env"
    config.write_text(f"MINEKIN_MODEL_API_KEY_ENV={credential_name}\n")
    with pytest.raises(ValueError, match="invalid model credential variable"):
        model_environment(config)
