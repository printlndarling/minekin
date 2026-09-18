"""Read-only diagnostics for the P0 host."""

from __future__ import annotations

import importlib.metadata
import re
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Protocol

from minekin_core.adapters.sqlite.connection import supports_multi_connection_wal
from minekin_core.config import P0_REQUIREMENTS, RuntimeRequirements

_JAVA_VERSION = re.compile(r'(?:java|openjdk) version "(?P<major>\d+)(?:[.]|\")')


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    ok: bool
    summary: str


@dataclass(frozen=True, slots=True)
class DoctorReport:
    checks: tuple[DiagnosticCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "doctor",
            "status": "ok" if self.ok else "failed",
            "checks": [asdict(check) for check in self.checks],
        }


class CommandRunner(Protocol):
    def __call__(
        self,
        command: Sequence[str],
        *,
        capture_output: bool,
        check: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]: ...


def _run_command(
    command: Sequence[str],
    *,
    capture_output: bool,
    check: bool,
    text: bool,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    if not text:
        raise ValueError("doctor requires text subprocess output")
    return subprocess.run(
        command,
        capture_output=capture_output,
        check=check,
        text=True,
        timeout=timeout,
    )


def _python_check(requirements: RuntimeRequirements) -> DiagnosticCheck:
    version = (sys.version_info.major, sys.version_info.minor)
    full_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return DiagnosticCheck(
        name="python",
        ok=requirements.supports_python(version),
        summary=f"Python {full_version}",
    )


def _protobuf_check(requirements: RuntimeRequirements) -> DiagnosticCheck:
    try:
        version = importlib.metadata.version(requirements.protobuf_distribution)
    except importlib.metadata.PackageNotFoundError:
        return DiagnosticCheck("protobuf", False, "protobuf distribution is not installed")
    numeric = version.split(".")
    try:
        major_minor = (int(numeric[0]), int(numeric[1]))
    except (IndexError, ValueError):
        return DiagnosticCheck("protobuf", False, f"protobuf has an invalid version: {version}")
    return DiagnosticCheck(
        "protobuf", requirements.supports_protobuf(major_minor), f"protobuf {version}"
    )


def _sqlite_check() -> DiagnosticCheck:
    version = sqlite3.sqlite_version_info
    return DiagnosticCheck(
        "sqlite",
        supports_multi_connection_wal(version),
        f"SQLite {sqlite3.sqlite_version} (multi-connection WAL safety gate)",
    )


def _java_check(
    requirements: RuntimeRequirements,
    *,
    which: Callable[[str], str | None],
    run: CommandRunner,
) -> DiagnosticCheck:
    java = which("java")
    if java is None:
        return DiagnosticCheck("java", False, "Java executable was not found")
    try:
        completed = run(
            [java, "-version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        return DiagnosticCheck("java", False, "Java version could not be read")

    output = f"{completed.stdout}\n{completed.stderr}"
    match = _JAVA_VERSION.search(output)
    if completed.returncode != 0 or match is None:
        return DiagnosticCheck("java", False, "Java version could not be identified")
    major = int(match.group("major"))
    return DiagnosticCheck(
        "java",
        major == requirements.java_major,
        f"Java {major} (required: {requirements.java_major})",
    )


def diagnose(
    requirements: RuntimeRequirements = P0_REQUIREMENTS,
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: CommandRunner = _run_command,
) -> DoctorReport:
    """Inspect the host without changing it or contacting the network."""

    return DoctorReport(
        checks=(
            _python_check(requirements),
            _java_check(requirements, which=which, run=run),
            _protobuf_check(requirements),
            _sqlite_check(),
        )
    )
