from __future__ import annotations

import io
import json
import sqlite3
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from minekin_core.adapters.sqlite.connection import SQLiteCompatibilityError
from minekin_core.bootstrap import main, run
from minekin_core.cli.doctor import diagnose
from minekin_core.cli.parser import parse_args
from minekin_core.config import RuntimeRequirements
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError


@pytest.mark.parametrize(
    ("argv", "command"),
    [
        (["init", "--kin-id", "kin-1"], "init"),
        (["doctor"], "doctor"),
        (["bundle", "verify", "--profile", "profile.json"], "bundle"),
        (["launch-plan", "--profile", "profile.json", "--dry-run"], "launch-plan"),
        (["session", "start", "--profile", "profile.json"], "session"),
        (["session", "status"], "session"),
        (["session", "stop"], "session"),
        (["evidence", "verify", "run-1"], "evidence"),
        (["replay", "evidence/run-1"], "replay"),
    ],
)
def test_frozen_cli_schema_parses(argv: list[str], command: str) -> None:
    assert parse_args(argv).command == command


def test_launch_plan_requires_explicit_dry_run() -> None:
    with pytest.raises(SystemExit) as raised:
        parse_args(["launch-plan", "--profile", "profile.json"])
    assert raised.value.code == ExitCode.USAGE


@pytest.mark.parametrize(
    "argv",
    [
        ["evidence", "verify", "missing-run"],
        ["replay", "missing-evidence"],
    ],
)
def test_w00_placeholders_fail_without_touching_path_arguments(
    argv: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    stdout = io.StringIO()
    stderr = io.StringIO()

    assert run(argv, stdout=stdout, stderr=stderr) == ExitCode.USAGE
    assert stdout.getvalue() == ""
    assert json.loads(stderr.getvalue())["status"] == "not_implemented"
    assert list(tmp_path.iterdir()) == []


def test_init_without_a_stated_root_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`init` left the placeholder list, so its own no-side-effect rule is asserted here."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MINEKIN_HOME", raising=False)
    monkeypatch.setenv("MINEKIN_USERNAME", "Kin")

    with pytest.raises(MinekinError):
        run(["init", "--kin-id", "kin-1"], stdout=io.StringIO(), stderr=io.StringIO())

    assert list(tmp_path.iterdir()) == []


def test_session_start_without_a_stated_root_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`session start` left the placeholder list, so its own rule is asserted here."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MINEKIN_HOME", raising=False)

    with pytest.raises(MinekinError):
        run(
            ["session", "start", "--profile", "missing.json"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )

    assert list(tmp_path.iterdir()) == []


def test_doctor_is_read_only_and_reports_requirements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run(
        command: Sequence[str],
        *,
        capture_output: bool,
        check: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, check, text, timeout
        return subprocess.CompletedProcess(command, 0, "", 'openjdk version "21.0.5"')

    report = diagnose(RuntimeRequirements(), which=lambda _name: "/read-only/java", run=fake_run)
    assert report.ok
    assert {check.name for check in report.checks} == {"python", "java", "protobuf", "sqlite"}
    assert list(tmp_path.iterdir()) == []


def test_doctor_fails_when_java_version_is_not_the_frozen_major() -> None:
    def fake_run(
        command: Sequence[str],
        *,
        capture_output: bool,
        check: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, check, text, timeout
        return subprocess.CompletedProcess(command, 0, "", 'java version "17.0.12"')

    report = diagnose(RuntimeRequirements(), which=lambda _name: "java", run=fake_run)
    assert not report.ok
    assert next(check for check in report.checks if check.name == "java").summary.startswith(
        "Java 17"
    )


def test_an_unsupported_sqlite_is_reported_as_a_storage_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gate is deliberate, so its refusal has to reach the operator.

    A stock Linux distribution ships a SQLite older than the frozen WAL safety
    set. That refusal travelled as an unclassified exception, and the CLI
    redacted it to "unexpected internal failure" — so the message saying exactly
    what was wrong never appeared.
    """

    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv("MINEKIN_USERNAME", "Kin")
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 45, 1))
    monkeypatch.setattr(sqlite3, "sqlite_version", "3.45.1")

    # `main` is where an exception becomes the document the operator reads.
    code = main(["init", "--kin-id", "kin-01"])
    document = json.loads(capsys.readouterr().err)

    assert code == int(ExitCode.STORAGE)
    assert document["category"] == "STORAGE"
    assert "3.45.1" in document["message"]
    # Naming what would satisfy the gate is what makes it actionable.
    assert "3.51.3" in document["message"]


def test_the_compatibility_error_carries_its_own_message() -> None:
    error = SQLiteCompatibilityError("SQLite 3.45.1 is outside the safety set")

    assert error.safe_message == "SQLite 3.45.1 is outside the safety set"
    assert error.category is ErrorCategory.STORAGE
    assert error.exit_code is ExitCode.STORAGE


def test_a_foreign_database_is_reported_rather_than_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator's mistake is a file in the wrong place, and it is sayable."""

    kin = tmp_path / "kin" / "kin-01"
    kin.mkdir(parents=True)
    foreign = sqlite3.connect(kin / "kin.sqlite3")
    foreign.execute("CREATE TABLE their_notes (body TEXT)")
    foreign.commit()
    foreign.close()
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv("MINEKIN_USERNAME", "Kin")

    code = main(["session", "status"])
    document = json.loads(capsys.readouterr().err)

    assert code == int(ExitCode.STORAGE)
    assert "not a Minekin ledger" in document["message"]
