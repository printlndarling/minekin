"""The model demo loader forwards literal values without executing configuration."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from tools import run_real_model_demo
from tools.run_real_model_demo import goal_environment, model_environment


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


def test_model_demo_goal_changes_product_and_quantity_without_changing_actions() -> None:
    assert goal_environment("minecraft:oak_planks", 8, "minecraft:oak_log") == {
        "MINEKIN_DEMO_GOAL_PRODUCT": "minecraft:oak_planks",
        "MINEKIN_DEMO_GOAL_QUANTITY": "8",
        "MINEKIN_DEMO_GOAL_SOURCE_ITEM": "minecraft:oak_log",
    }


@pytest.mark.parametrize("quantity", [0, -1, 65, True])
def test_model_demo_goal_refuses_invalid_quantity(quantity: int) -> None:
    with pytest.raises(ValueError, match="quantity"):
        goal_environment("minecraft:stick", quantity, "minecraft:oak_log")


def test_model_demo_goal_refuses_non_identifier_before_starting() -> None:
    with pytest.raises(ValueError, match="identifiers"):
        goal_environment("minecraft:stick;command", 1, "minecraft:oak_log")


@pytest.mark.parametrize(
    "profile", ["", "/src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json"]
)
def test_model_demo_uses_auto_registry_or_explicit_candidate_and_forwards_goal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    config = tmp_path / "model.env"
    config.write_text("MINEKIN_MODEL=example-model\n")
    captured: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        assert command[-1] == "--autonomous"
        return SimpleNamespace(returncode=0)

    argv = [
        "model-demo",
        "--model-env",
        str(config),
        "--log",
        str(tmp_path / "run.log"),
        "--bash",
        str(tmp_path / "bash"),
        "--goal-product",
        "minecraft:oak_planks",
        "--goal-quantity",
        "8",
    ]
    if profile:
        argv.extend(["--bundle-profile", profile])
    monkeypatch.setattr("sys.argv", argv)
    monkeypatch.setattr(run_real_model_demo.subprocess, "run", fake_run)
    assert run_real_model_demo.main() == 0
    assert captured["env"]["MINEKIN_DEMO_BUNDLE_PROFILE"] == profile
    assert captured["env"]["MINEKIN_DEMO_GOAL_PRODUCT"] == "minecraft:oak_planks"
    assert captured["env"]["MINEKIN_DEMO_GOAL_QUANTITY"] == "8"
