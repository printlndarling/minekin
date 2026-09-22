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
from pathlib import Path
from typing import Protocol

from minekin_core.adapters.launcher import launch_plan
from minekin_core.adapters.launcher.launch_plan import find_workspace_root
from minekin_core.adapters.sqlite.connection import supports_multi_connection_wal
from minekin_core.config import P0_REQUIREMENTS, RuntimeRequirements
from minekin_core.domain.errors import MinekinError

_JAVA_VERSION = re.compile(r'(?:java|openjdk) version "(?P<major>\d+)(?:[.]|\")')
_WHITESPACE = re.compile(r"\s+")


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


def _workspace_check(start: Path | None = None) -> DiagnosticCheck:
    """Whether the checkout this product needs is where the product looks for it.

    The controlled runner mounts the repository read-only rather than installing a
    wheel, and the reason is written down where that is done: `find_workspace_root`
    needs `bridge/` and `proto/` beside the source, and an installed wheel does not
    carry them. So a host can have this project's Python, Java, protobuf and SQLite
    all correct — every other check here green — and still be unable to start a
    session, because the checkout is not where the product looks for it.

    That failure used to appear only at `session start`, after a client had been
    launched, and it is exactly the shape a diagnostic exists to remove: the
    environment says yes and the thing the environment is for says no. Asked from
    the same place the product asks it, so that a check which passes here cannot
    pass while `build_launch_plan` would refuse.
    """

    origin = Path(launch_plan.__file__).resolve() if start is None else start
    try:
        root = find_workspace_root(origin)
    except MinekinError as error:
        return DiagnosticCheck("workspace", False, _one_line(error.safe_message))
    return DiagnosticCheck("workspace", True, f"workspace at {root}")


def _one_line(message: str) -> str:
    """A refusal on one line, because the report is a list of summaries.

    The message itself is not shortened: it is the part that says which marker is
    missing and why a wheel cannot substitute for it, and a check that fails without
    saying what to do about it is only half a check.
    """

    return _WHITESPACE.sub(" ", message).strip()


def diagnose(
    requirements: RuntimeRequirements = P0_REQUIREMENTS,
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: CommandRunner = _run_command,
    workspace_start: Path | None = None,
) -> DoctorReport:
    """Inspect the host without changing it or contacting the network."""

    return DoctorReport(
        checks=(
            _python_check(requirements),
            _java_check(requirements, which=which, run=run),
            _protobuf_check(requirements),
            _sqlite_check(),
            _workspace_check(workspace_start),
        )
    )
