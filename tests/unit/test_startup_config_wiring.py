"""The startup seam that folds a dashboard-saved config into the running environment.

`apply_operator_config` is the reason a saved document has any effect; these tests prove the CLI
actually calls it at the process boundary, keeps the shell-first precedence `load_local_environment`
establishes, and stays out of the way when there is no data root or no document to read.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from minekin_core import bootstrap
from minekin_core.config import DATA_ROOT_VARIABLE
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.goal_spec import GOAL_PRODUCT_VARIABLE, GOAL_QUANTITY_VARIABLE
from minekin_core.domain.model_access import MODEL_VARIABLE
from minekin_core.domain.operator_config import (
    CONFIG_FILE_NAME,
    OperatorConfig,
    save_operator_config,
)

_TRACKED_NAMES = (GOAL_PRODUCT_VARIABLE, GOAL_QUANTITY_VARIABLE, MODEL_VARIABLE)


@pytest.fixture
def clean_goal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _TRACKED_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_a_saved_document_folds_into_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_goal_env: None
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    save_operator_config(
        tmp_path,
        OperatorConfig(
            goal_product_id="minecraft:stick",
            goal_quantity=4,
            model_name="some/model",
        ),
    )

    bootstrap.apply_persisted_config()

    assert os.environ[GOAL_PRODUCT_VARIABLE] == "minecraft:stick"
    assert os.environ[GOAL_QUANTITY_VARIABLE] == "4"
    assert os.environ[MODEL_VARIABLE] == "some/model"


def test_a_shell_value_outranks_the_saved_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_goal_env: None
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    monkeypatch.setenv(GOAL_PRODUCT_VARIABLE, "minecraft:from_the_shell")
    save_operator_config(tmp_path, OperatorConfig(goal_product_id="minecraft:stick"))

    bootstrap.apply_persisted_config()

    assert os.environ[GOAL_PRODUCT_VARIABLE] == "minecraft:from_the_shell"


def test_no_data_root_folds_in_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_goal_env: None
) -> None:
    monkeypatch.delenv(DATA_ROOT_VARIABLE, raising=False)

    bootstrap.apply_persisted_config()  # a machine with no MINEKIN_HOME yet must still run

    assert os.environ.get(GOAL_PRODUCT_VARIABLE) is None


def test_data_root_without_a_document_folds_in_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_goal_env: None
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    assert not (tmp_path / CONFIG_FILE_NAME).exists()

    bootstrap.apply_persisted_config()  # an absent file is an empty config, not a fault

    assert os.environ.get(GOAL_PRODUCT_VARIABLE) is None


def test_a_corrupt_document_raises_rather_than_running_on_a_guess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_goal_env: None
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    (tmp_path / CONFIG_FILE_NAME).write_text("{ not json", encoding="utf-8")

    with pytest.raises(MinekinError):
        bootstrap.apply_persisted_config()
