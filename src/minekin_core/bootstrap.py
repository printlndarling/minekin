"""Process bootstrap and CLI exit-code mapping."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import TextIO

from minekin_core.cli.doctor import diagnose
from minekin_core.cli.parser import parse_args
from minekin_core.domain.errors import ExitCode, fail_closed


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

    W00 intentionally implements only diagnostics. Every other frozen command
    fails before reading its path arguments or creating persistent state.
    """

    args = parse_args(argv)
    if args.command == "doctor":
        report = diagnose()
        _emit(report.as_dict(), stdout)
        return int(ExitCode.OK if report.ok else ExitCode.CONFIG)

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
