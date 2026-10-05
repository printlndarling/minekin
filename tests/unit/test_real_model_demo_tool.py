"""The model demo loader forwards literal values without executing configuration."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from tools import run_real_model_demo
from tools.run_real_model_demo import child_policy_environment, goal_environment, model_environment

from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE


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
        captured["command"] = list(command)
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
    if profile.startswith("/"):
        # A POSIX-looking profile cannot ride the environment across the MSYS boundary (MSYS
        # rewrites it against its install root); it is exported inside the script text instead,
        # and the env copy is blanked so nothing converts anything.
        assert captured["env"]["MINEKIN_DEMO_BUNDLE_PROFILE"] == ""
        script = captured["command"][-1]
        assert f"export MINEKIN_DEMO_BUNDLE_PROFILE={profile}" in script
        assert script.endswith("test-orchestrator/runner/demo.sh --autonomous")
    else:
        assert captured["env"]["MINEKIN_DEMO_BUNDLE_PROFILE"] == profile
        assert captured["command"][-1] == "--autonomous"
    assert captured["env"]["MINEKIN_DEMO_GOAL_PRODUCT"] == "minecraft:oak_planks"
    assert captured["env"]["MINEKIN_DEMO_GOAL_QUANTITY"] == "8"


# --------------------------------------------------- the real-model entry names the model policy


@pytest.mark.parametrize("parent", ["", "model", " MODEL "])
def test_the_model_demo_names_the_model_policy_for_the_child(parent: str) -> None:
    """This entry point runs a real model: unset or an explicit `model` becomes an explicit
    `model` in the child, so nothing downstream can inherit a stale rules value by accident."""

    environ = {} if parent == "" else {DECISION_POLICY_VARIABLE: parent}
    assert child_policy_environment(environ) == {DECISION_POLICY_VARIABLE: "model"}


def test_an_explicit_parent_rules_policy_is_refused_not_silently_overridden() -> None:
    with pytest.raises(ValueError, match=DECISION_POLICY_VARIABLE):
        child_policy_environment({DECISION_POLICY_VARIABLE: "rules"})


def test_a_misspelled_parent_policy_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="must be one of"):
        child_policy_environment({DECISION_POLICY_VARIABLE: "sometimes"})


def test_the_model_demo_writes_model_into_the_actual_child_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "model.env"
    config.write_text("MINEKIN_MODEL=example-model\n")
    monkeypatch.delenv(DECISION_POLICY_VARIABLE, raising=False)
    captured: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "sys.argv",
        [
            "model-demo",
            "--model-env",
            str(config),
            "--log",
            str(tmp_path / "run.log"),
            "--bash",
            str(tmp_path / "bash"),
        ],
    )
    monkeypatch.setattr(run_real_model_demo.subprocess, "run", fake_run)
    assert run_real_model_demo.main() == 0
    assert captured["env"][DECISION_POLICY_VARIABLE] == "model"


def test_an_explicit_rules_parent_is_refused_before_any_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The independent counterexample: a parent environment that explicitly says rules must
    not silently reach the child. The tool refuses by name before any subprocess exists --
    the model environment stand-in returning nothing changes nothing about that order."""

    monkeypatch.setenv(DECISION_POLICY_VARIABLE, "rules")

    def no_model_configuration(path: Path) -> dict[str, str]:
        del path
        return {}

    monkeypatch.setattr(run_real_model_demo, "model_environment", no_model_configuration)
    calls: list[Any] = []

    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_real_model_demo.subprocess, "run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "model-demo",
            "--model-env",
            str(tmp_path / "missing.env"),
            "--log",
            str(tmp_path / "run.log"),
            "--bash",
            str(tmp_path / "bash"),
        ],
    )

    with pytest.raises(SystemExit) as raised:
        run_real_model_demo.main()

    assert raised.value.code != 0
    assert calls == []
    assert DECISION_POLICY_VARIABLE in capsys.readouterr().err


def test_a_misspelled_parent_policy_is_refused_before_any_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(DECISION_POLICY_VARIABLE, "sometimes")
    calls: list[Any] = []

    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_real_model_demo.subprocess, "run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "model-demo",
            "--model-env",
            str(tmp_path / "missing.env"),
            "--log",
            str(tmp_path / "run.log"),
            "--bash",
            str(tmp_path / "bash"),
        ],
    )

    with pytest.raises(SystemExit) as raised:
        run_real_model_demo.main()

    assert raised.value.code != 0
    assert calls == []
    assert "must be one of" in capsys.readouterr().err
