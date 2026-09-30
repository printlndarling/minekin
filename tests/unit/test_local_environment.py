"""The operator's local `.env`: names in, values never out.

The environment is the interface this project reads (`config.py` says so at the top),
so a file that carries those names only has to reach the environment before the first
reader does — and it must do that without ever letting a value be shown, logged or
overruled by a half-typed line.
"""

from __future__ import annotations

from pathlib import Path

from minekin_core.config import (
    LOCAL_ENV_FILE_NAME,
    LOCAL_ENV_FILE_VARIABLE,
    load_local_environment,
    local_environment_path,
    parse_local_environment,
)


def test_the_named_file_is_the_one_the_operator_points_at(tmp_path: Path) -> None:
    pointed = tmp_path / "operator.env"
    environ = {LOCAL_ENV_FILE_VARIABLE: str(pointed)}

    assert local_environment_path(environ=environ, cwd=tmp_path) == pointed


def test_the_default_is_dot_env_in_the_working_directory(tmp_path: Path) -> None:
    assert local_environment_path(environ={}, cwd=tmp_path) == tmp_path / LOCAL_ENV_FILE_NAME


def test_comments_blanks_and_export_are_not_variables() -> None:
    parsed = parse_local_environment(
        "\n".join(
            [
                "# a comment naming MODEL_API_KEY=not-a-value",
                "",
                "export MINEKIN_MODEL=openai-model",
                "MINEKIN_MODEL_BASE_URL=https://example.invalid/v1",
                "not a variable",
                "=no name",
            ]
        )
    )

    assert parsed == {
        "MINEKIN_MODEL": "openai-model",
        "MINEKIN_MODEL_BASE_URL": "https://example.invalid/v1",
    }


def test_quotes_are_the_file_s_delimiters_not_part_of_the_value() -> None:
    parsed = parse_local_environment(
        'A="quoted"\nB=\'single\'\nC=bare\nD="has = inside"\nE=trailing   \n'
    )

    assert parsed == {
        "A": "quoted",
        "B": "single",
        "C": "bare",
        "D": "has = inside",
        "E": "trailing",
    }


def test_loading_fills_the_environment_without_showing_a_value(tmp_path: Path) -> None:
    (tmp_path / LOCAL_ENV_FILE_NAME).write_text(
        "MINEKIN_MODEL_API_KEY_ENV=MINEKIN_PROVIDER_API_KEY\n", encoding="utf-8"
    )
    environ: dict[str, str] = {}

    loaded = load_local_environment(environ=environ, cwd=tmp_path)

    assert loaded == ("MINEKIN_MODEL_API_KEY_ENV",)
    assert environ == {"MINEKIN_MODEL_API_KEY_ENV": "MINEKIN_PROVIDER_API_KEY"}


def test_a_variable_the_operator_exported_outranks_the_file(tmp_path: Path) -> None:
    (tmp_path / LOCAL_ENV_FILE_NAME).write_text("MINEKIN_HOME=/from/the/file\n", encoding="utf-8")
    environ: dict[str, str] = {"MINEKIN_HOME": "/from/the/shell"}

    loaded = load_local_environment(environ=environ, cwd=tmp_path)

    assert loaded == ()
    assert environ == {"MINEKIN_HOME": "/from/the/shell"}


def test_no_file_is_not_an_error(tmp_path: Path) -> None:
    environ: dict[str, str] = {}

    assert load_local_environment(environ=environ, cwd=tmp_path) == ()
    assert environ == {}


def test_a_pointed_at_file_that_is_not_there_is_not_an_error(tmp_path: Path) -> None:
    environ = {LOCAL_ENV_FILE_VARIABLE: str(tmp_path / "absent.env")}

    assert load_local_environment(environ=environ, cwd=tmp_path) == ()
