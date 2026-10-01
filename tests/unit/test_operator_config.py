"""The operator-config seam: persistence, the secret boundary, version policy, env overlay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from minekin_core.domain.errors import MinekinError
from minekin_core.domain.operator_config import (
    CONFIG_FILE_NAME,
    SCHEMA_VERSION,
    ConfigRefusal,
    OperatorConfig,
    apply_operator_config,
    config_path,
    load_operator_config,
    save_operator_config,
)


def _full_config() -> OperatorConfig:
    return OperatorConfig(
        model_provider="openai_compatible",
        model_base_url="https://example.test/v1",
        model_name="some/model",
        model_api_key_env="MINEKIN_COMMANDCODE_API_KEY",
        model_timeout_ms=8000,
        model_run_cost_cap=200000,
        goal_product_id="minecraft:stick",
        goal_quantity=4,
        goal_source_item_id="minecraft:oak_log",
        goal_direction="hold_a_stick",
    )


def test_empty_config_writes_no_fields_and_fills_nothing(tmp_path: Path) -> None:
    config = OperatorConfig()
    assert config.is_empty()
    assert config.to_environment() == {}
    saved = save_operator_config(tmp_path, config)
    document = json.loads(config_path(tmp_path).read_text(encoding="utf-8"))
    assert document["fields"] == {}
    assert saved.is_empty()
    environ: dict[str, str] = {}
    assert apply_operator_config(config, environ) == ()
    assert environ == {}


def test_save_load_round_trips_every_field(tmp_path: Path) -> None:
    original = _full_config()
    save_operator_config(tmp_path, original)
    loaded = load_operator_config(tmp_path)
    assert loaded == original


def test_document_is_versioned_and_holds_no_key_value(tmp_path: Path) -> None:
    save_operator_config(tmp_path, _full_config())
    text = config_path(tmp_path).read_text(encoding="utf-8")
    document = json.loads(text)
    assert document["schemaVersion"] == SCHEMA_VERSION
    # The key's *name* is stored; its value never is, and no field is called a key.
    assert document["fields"]["model_api_key_env"] == "MINEKIN_COMMANDCODE_API_KEY"
    assert "sk-" not in text


def test_write_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    save_operator_config(tmp_path, _full_config())
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != CONFIG_FILE_NAME]
    assert leftovers == []


def test_a_credential_shaped_value_is_refused(tmp_path: Path) -> None:
    # 40+ chars of token in a field that holds only names/urls/ids: refused before it reaches disk.
    leaked = "x" * 48
    config = OperatorConfig(model_name=leaked)
    with pytest.raises(ConfigRefusal) as raised:
        save_operator_config(tmp_path, config)
    assert raised.value.field == "model_name"
    assert not config_path(tmp_path).exists()


def test_api_key_env_must_be_a_bare_name_not_a_key(tmp_path: Path) -> None:
    with pytest.raises(ConfigRefusal):
        save_operator_config(tmp_path, OperatorConfig(model_api_key_env="super:secret:blob"))
    # A real variable name is accepted.
    save_operator_config(tmp_path, OperatorConfig(model_api_key_env="MINEKIN_COMMANDCODE_API_KEY"))


def test_unknown_provider_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigRefusal):
        save_operator_config(tmp_path, OperatorConfig(model_provider="magic"))


def test_bad_item_id_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigRefusal):
        save_operator_config(tmp_path, OperatorConfig(goal_product_id="NotAnItemId"))


def test_goal_quantity_is_bounded_to_one_ask(tmp_path: Path) -> None:
    with pytest.raises(ConfigRefusal):
        save_operator_config(
            tmp_path, OperatorConfig(goal_product_id="minecraft:stick", goal_quantity=999999)
        )
    with pytest.raises(ConfigRefusal):
        # bool is an int subclass; a JSON true must not read as a count.
        save_operator_config(tmp_path, OperatorConfig(goal_quantity=True))  # type: ignore[arg-type]


def test_absent_file_is_an_empty_config(tmp_path: Path) -> None:
    assert load_operator_config(tmp_path) == OperatorConfig()


def test_malformed_json_is_a_named_error(tmp_path: Path) -> None:
    config_path(tmp_path).write_text("{ not json", encoding="utf-8")
    with pytest.raises(MinekinError):
        load_operator_config(tmp_path)


def test_a_different_major_is_refused_by_name(tmp_path: Path) -> None:
    config_path(tmp_path).write_text(
        json.dumps({"schemaVersion": "minekin-operator-config/2.0", "fields": {}}), encoding="utf-8"
    )
    with pytest.raises(MinekinError):
        load_operator_config(tmp_path)


def test_a_later_minor_and_unknown_fields_are_read_forward(tmp_path: Path) -> None:
    config_path(tmp_path).write_text(
        json.dumps(
            {
                "schemaVersion": "minekin-operator-config/1.4",
                "fields": {"model_provider": "off", "a_field_from_the_future": 7},
            }
        ),
        encoding="utf-8",
    )
    loaded = load_operator_config(tmp_path)
    assert loaded.model_provider == "off"
    assert loaded.model_name == ""


def test_apply_fills_only_names_absent_from_the_environment() -> None:
    config = _full_config()
    environ = {"MINEKIN_MODEL_PROVIDER": "off"}  # operator exported it; the file must lose
    applied = apply_operator_config(config, environ)
    assert environ["MINEKIN_MODEL_PROVIDER"] == "off"
    assert environ["MINEKIN_GOAL_PRODUCT"] == "minecraft:stick"
    assert environ["MINEKIN_MODEL_TIMEOUT_MS"] == "8000"
    # The already-set name is not reported as applied, and only names come back — never values.
    assert "MINEKIN_MODEL_PROVIDER" not in applied
    assert "MINEKIN_MODEL_BASE_URL" in applied
    assert all(environ[name] for name in applied)


def test_to_environment_uses_the_readers_own_variable_names() -> None:
    env = _full_config().to_environment()
    assert env["MINEKIN_MODEL_BASE_URL"] == "https://example.test/v1"
    assert env["MINEKIN_GOAL_SOURCE_ITEM"] == "minecraft:oak_log"
