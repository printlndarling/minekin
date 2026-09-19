"""Process bootstrap and CLI exit-code mapping."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.cli.doctor import diagnose
from minekin_core.cli.init import initialise_identity
from minekin_core.cli.parser import parse_args
from minekin_core.cli.session import start_and_supervise, stop_session
from minekin_core.cli.session_runtime import SessionOutcome, SessionRun
from minekin_core.cli.status import read_status
from minekin_core.config import configured_username, data_root, java_executable, kin_selector
from minekin_core.domain.errors import (
    ErrorCategory,
    ExitCode,
    MinekinError,
    Retryability,
    fail_closed,
)
from minekin_core.domain.ids import KinId, SessionId

# A run that ended because the client left is the command succeeding; anything
# else is why it did not.
_OUTCOME_EXIT_CODES: dict[SessionOutcome, ExitCode] = {
    SessionOutcome.CLIENT_EXITED: ExitCode.OK,
    SessionOutcome.BRIDGE_LOST: ExitCode.IPC_PROTOCOL,
    SessionOutcome.HANDSHAKE_FAILED: ExitCode.IPC_PROTOCOL,
    SessionOutcome.HANDSHAKE_TIMEOUT: ExitCode.TIMEOUT,
}


def _exit_code_for(run: SessionRun) -> ExitCode:
    return _OUTCOME_EXIT_CODES[run.outcome]


def _command_name(args: argparse.Namespace) -> str:
    parts = [str(args.command)]
    for attribute in ("bundle_command", "session_command", "evidence_command"):
        value = getattr(args, attribute, None)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts)


def _emit(value: object, stream: TextIO) -> None:
    print(json.dumps(value, sort_keys=True), file=stream)


def run(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Parse and execute one CLI command.

    Commands that are frozen but not implemented fail before reading their path
    arguments or creating persistent state, and say so on stderr.
    """

    args = parse_args(argv)
    if args.command == "doctor":
        report = diagnose()
        _emit(report.as_dict(), stdout)
        return int(ExitCode.OK if report.ok else ExitCode.CONFIG)

    if args.command == "init":
        try:
            kin_id = KinId(str(args.kin_id))
        except ValueError as error:
            raise MinekinError(
                "cli",
                "init",
                ErrorCategory.CONFIG,
                Retryability.OPERATOR_ACTION,
                f"--kin-id is not a usable identifier: {error}",
            ) from error
        report = initialise_identity(
            kin_id,
            root=data_root(),
            username=configured_username(),
            clock=SystemClock(),
        )
        _emit(report.as_dict(), stdout)
        return int(ExitCode.OK)

    if args.command == "session" and args.session_command == "start":
        launch, run = asyncio.run(
            start_and_supervise(
                root=data_root(),
                profile=Path(args.profile),
                java_executable=java_executable(),
                session_id=SessionId.new().value,
                generation=1,
                kin_selector=kin_selector(),
            )
        )
        _emit({**launch.as_dict(), "run": run.as_dict()}, stdout)
        return int(_exit_code_for(run))

    if args.command == "session" and args.session_command == "status":
        report = read_status(data_root(), kin_selector=kin_selector())
        _emit(report.as_dict(), stdout)
        return int(ExitCode.OK)

    if args.command == "session" and args.session_command == "stop":
        stopped = stop_session(data_root(), kin_selector=kin_selector())
        _emit(stopped.as_dict(), stdout)
        return int(ExitCode.OK if stopped.outcome.complete else ExitCode.PROCESS)

    if args.command == "launch-plan":
        _emit(build_launch_plan(Path(args.profile)), stdout)
        return int(ExitCode.OK)

    if args.command == "bundle" and args.bundle_command == "verify":
        plan = build_launch_plan(Path(args.profile))
        _emit(
            {
                "schema_version": 1,
                "status": "valid_recipe",
                "launchable": plan["launchable"],
                "blockers": plan["blockers"],
                "plan_sha256": plan["plan_sha256"],
            },
            stdout,
        )
        return int(ExitCode.OK)

    command = _command_name(args)
    _emit(
        {
            "schema_version": 1,
            "status": "not_implemented",
            "command": command,
            "message": "command is frozen but not implemented in W00",
        },
        stderr,
    )
    return int(ExitCode.USAGE)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except KeyboardInterrupt:
        return int(ExitCode.INTERRUPTED)
    except SystemExit:
        raise
    except BaseException as error:
        converted = fail_closed(error, component="cli", operation="dispatch")
        _emit(converted.diagnostic(), sys.stderr)
        return int(converted.exit_code)
