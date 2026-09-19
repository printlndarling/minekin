"""Argument parser for the frozen P0 command surface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minekin",
        description="Minekin P0 control-plane command line",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="initialize one Kin identity")
    init_parser.add_argument("--kin-id", required=True, metavar="KIN_ID")

    commands.add_parser("doctor", help="run read-only host diagnostics")

    bundle_parser = commands.add_parser("bundle", help="inspect an immutable version bundle")
    bundle_commands = bundle_parser.add_subparsers(dest="bundle_command", required=True)
    bundle_verify = bundle_commands.add_parser("verify", help="verify a bundle profile")
    bundle_verify.add_argument("--profile", required=True, metavar="PATH")

    launch_plan = commands.add_parser("launch-plan", help="construct a client launch plan")
    launch_plan.add_argument("--profile", required=True, metavar="PATH")
    launch_plan.add_argument(
        "--dry-run",
        required=True,
        action="store_true",
        help="print a plan without starting Java (the only P0 launch-plan mode)",
    )

    session_parser = commands.add_parser("session", help="manage the client session")
    session_commands = session_parser.add_subparsers(dest="session_command", required=True)
    session_start = session_commands.add_parser("start", help="start a managed session")
    session_start.add_argument("--profile", required=True, metavar="PATH")
    # §15's surface lists `session start --profile ...`; this is an optional
    # second input document rather than a new verb, because the alternative —
    # a `session connect` command — would have to re-open a session that is
    # already running in another process, and the client only has one Bridge.
    # Without it the session behaves exactly as it did before: the client comes
    # up, proves itself, and stays at the menu.
    session_start.add_argument(
        "--server-profile",
        default=None,
        metavar="PATH",
        help="connect the client to this saved Server Profile after the handshake",
    )
    # The third optional input document, and the same reasoning as the second:
    # a run that should hold a movement key is a property of this run, not of a
    # session that would have to be re-opened in another process to change it.
    # It is a hold rather than a walk for a measured reason: what bounds it is the
    # lease and the session, and a run that ends takes the key with it.
    session_start.add_argument(
        "--hold-forward-seconds",
        type=float,
        default=None,
        metavar="SECONDS",
        help=(
            "hold the forward key for this long from the moment the session is "
            "playable, then let the lease lapse (needs --server-profile)"
        ),
    )
    session_commands.add_parser("status", help="read the current projection")
    session_commands.add_parser("stop", help="idempotently stop the current session")

    evidence_parser = commands.add_parser("evidence", help="inspect run evidence")
    evidence_commands = evidence_parser.add_subparsers(dest="evidence_command", required=True)
    evidence_verify = evidence_commands.add_parser("verify", help="verify one evidence run")
    evidence_verify.add_argument("run_id", metavar="RUN_ID")

    replay = commands.add_parser("replay", help="replay an evidence directory")
    replay.add_argument("evidence_dir", metavar="EVIDENCE_DIR")
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)
