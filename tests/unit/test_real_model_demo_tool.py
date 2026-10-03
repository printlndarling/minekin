"""The model demo loader forwards literal values without executing configuration."""

from pathlib import Path

import pytest
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
