from __future__ import annotations

import io
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from minekin_core.bootstrap import run
from minekin_core.cli.doctor import diagnose
from minekin_core.cli.parser import parse_args
from minekin_core.config import RuntimeRequirements
from minekin_core.domain.errors import ExitCode


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
        ["init", "--kin-id", "kin-1"],
        ["bundle", "verify", "--profile", "missing.json"],
        ["launch-plan", "--profile", "missing.json", "--dry-run"],
        ["session", "start", "--profile", "missing.json"],
        ["session", "status"],
        ["session", "stop"],
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
