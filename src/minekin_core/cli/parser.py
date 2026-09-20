"""Argument parser for the frozen P0 command surface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path


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
    # How long this run is willing to wait for that world. The default is the
    # reviewed one; a scenario that wants to watch Core give up has to be able to
    # ask for less, because the client has its own read timeout and a test whose
    # two clocks are the same length is a race rather than a test.
    session_start.add_argument(
        "--connection-timeout-seconds",
        type=float,
        default=None,
        metavar="SECONDS",
        help="how long to wait for the named world before giving up on the attempt",
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
    # The look, which is the other half of what a run may ask for. Two flags
    # because they are two axes and one of them may be left alone: a look of
    # exactly zero degrees is not a look, so absent has to be expressible.
    # The rest of the movement axes, as modifiers of the hold: the duration flag
    # is what makes a hold exist at all, and these say what is held. Each is a
    # field of MoveInput, so none of them is a new concept on the wire — what
    # they verify is that the binding the Bridge presses for each name is the
    # one vanilla calls that thing, which no unit test can decide.
    session_start.add_argument(
        "--hold-strafe",
        type=float,
        default=None,
        metavar="AXIS",
        help="hold the strafe axis too, -1 left to 1 right (needs --hold-forward-seconds)",
    )
    session_start.add_argument(
        "--hold-jump",
        action="store_true",
        help="hold the jump key for the length of the hold",
    )
    session_start.add_argument(
        "--hold-sneak",
        action="store_true",
        help="hold the sneak key for the length of the hold",
    )
    # And the one input that is not an axis at all: using whatever is in front of
    # the Kin. It is a hold for the same reason the movement keys are — the lease
    # is what ends it — and its own flag rather than part of the hold, because a
    # run may ask for either without the other.
    session_start.add_argument(
        "--hold-use-seconds",
        type=float,
        default=None,
        metavar="SECONDS",
        help="hold the use key for this long once the session is playable",
    )
    # When this run asks for its hold. `playable` is the only moment that can
    # succeed, so it is the default; `join` asks before the first snapshot and is
    # refused, which is how "no lease before the world is real" is tested rather
    # than assumed. The refusal is recorded either way.
    session_start.add_argument(
        "--hold-at",
        choices=("playable", "join"),
        default="playable",
        metavar="PHASE",
        help="when to ask for the hold: playable (default) or join, which is refused",
    )
    session_start.add_argument(
        "--look-yaw-degrees",
        type=float,
        default=None,
        metavar="DEGREES",
        help="turn the view this far (positive is right) once the session is playable",
    )
    session_start.add_argument(
        "--look-pitch-degrees",
        type=float,
        default=None,
        metavar="DEGREES",
        help="tilt the view this far (positive is up) once the session is playable",
    )
    # A world to place in this client's game directory, and the level name to
    # give it. Both, or neither: a save with no name is not enterable, and a name
    # with nothing behind it is not a world. This is what a session that is meant
    # to *host* an integrated world needs — vanilla finds its worlds in
    # `saves/<level>` inside the game directory, and the game directory is this
    # session's overlay.
    session_start.add_argument(
        "--world-save",
        type=Path,
        default=None,
        metavar="PATH",
        help="a prepared save to seed into this session's game directory (needs --world-name)",
    )
    session_start.add_argument(
        "--world-name",
        default=None,
        metavar="LEVEL",
        help=(
            "the level name to seed and enter; the client starts in that world "
            "rather than at the title screen (needs --world-save)"
        ),
    )
    # A session that is meant to *host*: the client is in a world (see --world-save)
    # and Core asks the Bridge to publish it. Asked for rather than done whenever a
    # world was seeded, because publishing is a lifecycle change to the server in the
    # client's own process — measured to grant the host cheats and a permission level
    # — and an operator's intent to host is a different thing from an operator's
    # intent to be in a world.
    session_start.add_argument(
        "--open-lan",
        action="store_true",
        help="ask the client to publish the world it is hosting, once it is in it",
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
