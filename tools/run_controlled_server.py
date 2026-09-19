"""Start the pinned vanilla server exactly as the frozen profile describes it.

The controlled test domain is a vanilla 1.21.4 dedicated server on loopback with
`online-mode=false`, and the profile fixture says so. This runs it: it verifies the
pinned jar, writes the settings the profile implies, starts the JVM, waits for the
server to report itself ready, and stops it again.

It exists because the server half of the controlled environment needs nothing but
Java, unlike the client half. What it does *not* do is accept the EULA on anyone's
behalf — that is the operator's to accept, so it must be asked for explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import BinaryIO

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "controlled-offline-server.json"
)
SERVER_SHA1 = "4707d00eb834b446575d89a61a11b5d548d8c001"
SERVER_SIZE = 56_880_250

# The world is fixed rather than random so that a run is reproducible, and flat so
# that generating it costs nothing on a machine that is not a runner.
FIXED_WORLD_SEED = "minekin-p0-controlled"
# A vanilla entity id: `minecraft:pig`, `pig`, and nothing that could be anything
# else. The command goes to the server's console, where a newline would be a
# second command, so the shape is checked rather than escaped.
_ENTITY_ID = re.compile(r"^[a-z0-9_.-]+(:[a-z0-9_./-]+)?$")
#: What the server says when a `setblock` worked, which is where the block it
#: placed is. The coordinates are the point: the Kin moves, the block does not.
_BLOCK_PLACED = re.compile(r"Changed the block at (-?\d+), (-?\d+), (-?\d+)")
#: The two words the block probe has the server say, one per state. Named here
#: because the asserter reads them and the two sides have to be one string.
#: How many times a run will put a block in front of the Kin before it stops
#: trying. Bounded rather than "until it works", because a scene that never gets
#: used is a fact about the run and the log should say so once rather than keep
#: filling up with blocks nobody pressed.
MAX_USE_TARGETS = 12
READY_MARKER = "Done ("
DEFAULT_READY_TIMEOUT_S = 240.0


def properties_for(profile: object, *, level_seed: str) -> dict[str, str]:
    """The server settings the frozen profile implies, and nothing it does not."""

    from minekin_core.adapters.launcher.server_profile import ServerProfile

    assert isinstance(profile, ServerProfile)
    return {
        "online-mode": "false" if profile.auth_mode == "offline" else "true",
        "server-ip": profile.host,
        "server-port": str(profile.port),
        "gamemode": "survival",
        "force-gamemode": "true",
        "difficulty": "normal",
        "hardcore": "false",
        "pvp": "true",
        "enable-rcon": "false",
        "enable-query": "false",
        "enable-status": "false",
        "enable-command-block": "false",
        "broadcast-console-to-ops": "false",
        "white-list": "true",
        "enforce-whitelist": "true",
        "spawn-protection": "0",
        "max-players": "2",
        "view-distance": "4",
        "simulation-distance": "4",
        "level-name": "world",
        "level-seed": level_seed,
        "level-type": "minecraft:flat",
        # Vanilla's default is 60, and it is wrong for this domain specifically:
        # a controlled server is empty for almost its whole life, because the
        # only player is one this launcher starts, and it is empty for exactly
        # the stretch in which that player is booting and connecting. Pausing is
        # a power saving for an idle production server, not for a domain whose
        # purpose is to be joined. (It did not turn out to be the cause of the
        # login failure that was being chased when this was added — that still
        # reproduces with pausing off — so it is a fix for a real wrongness
        # rather than for that symptom.)
        "pause-when-empty-seconds": "0",
        "motd": f"Minekin controlled offline test domain ({profile.profile_id})",
    }


def write_configuration(
    directory: Path,
    properties: dict[str, str],
    *,
    allowed_players: tuple[str, ...],
) -> None:
    """Create one fresh server run; never overwrite evidence from an older run."""

    from minekin_core.domain.offline_identity import is_valid_username, offline_player_uuid

    invalid = sorted({name for name in allowed_players if not is_valid_username(name)})
    if invalid:
        raise SystemExit("invalid vanilla player name(s): " + ", ".join(invalid))
    unique_players: dict[str, str] = {}
    for name in allowed_players:
        folded = name.casefold()
        prior = unique_players.get(folded)
        if prior is not None and prior != name:
            raise SystemExit(f"player names differ only by case: {prior}, {name}")
        unique_players[folded] = name
    if directory.exists() and any(directory.iterdir()):
        raise SystemExit(f"{directory} is not empty; use a fresh run directory")
    directory.mkdir(parents=True, exist_ok=True)

    lines = ["# Generated by tools/run_controlled_server.py from the frozen profile."]
    lines.extend(f"{key}={value}" for key, value in sorted(properties.items()))
    (directory / "server.properties").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (directory / "eula.txt").write_text(
        "# Accepted by the operator via --accept-eula.\neula=true\n", encoding="utf-8"
    )
    whitelist = [
        {"uuid": str(offline_player_uuid(name)), "name": name}
        for name in sorted(unique_players.values(), key=str.casefold)
    ]
    (directory / "whitelist.json").write_text(
        json.dumps(whitelist, indent=2) + "\n", encoding="utf-8"
    )
    (directory / "ops.json").write_text("[]\n", encoding="utf-8")


def summon_command(entity_type: str) -> str:
    """The console line that puts one entity at the world spawn, or a refusal.

    The controlled world is empty and flat, so without this the first snapshot's
    visible world is vacuously empty and the entity path is never exercised by a
    run. It is a console command, which is a channel where an unchecked string is
    a second command, so the entity id is matched against the shape vanilla
    ids have rather than escaped.
    """

    if not _ENTITY_ID.fullmatch(entity_type):
        raise SystemExit(f"not a vanilla entity id: {entity_type!r}")
    return f"summon {entity_type} ~ ~ ~"


def kill_command(player: str) -> str:
    """The console line that kills a player, or a refusal.

    The one release trigger a server can cause is a death: the client shows its
    death screen, the keyboard stops belonging to the world, and the Bridge is
    the only side that can see it. So a run that wants to exercise that has to
    be able to kill the Kin, and only the server can.

    A console command like the others, so the name is checked rather than
    escaped.
    """

    from minekin_core.domain.offline_identity import is_valid_username

    if not is_valid_username(player):
        raise SystemExit(f"not a vanilla player name: {player!r}")
    return f"kill {player}"


def kick_command(player: str) -> str:
    """The console line that disconnects a player, or a refusal.

    A death proves the client lets go when a screen takes the keyboard; a kick
    proves it lets go when the *session* ends, which is a different trigger the
    contract names separately. Only the server can start one, which is what keeps
    the two sides of the evidence independent.
    """

    from minekin_core.domain.offline_identity import is_valid_username

    if not is_valid_username(player):
        raise SystemExit(f"not a vanilla player name: {player!r}")
    return f"kick {player}"


def has_joined(log: Path, player: str) -> bool:
    """Whether the server has said this player is in the world."""

    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return f"{player} joined the game" in text


def request_clean_stop(signum: int, frame: object) -> None:
    """Route a stop signal into the same path Ctrl+C already takes.

    Handled explicitly rather than left to the default, because the default is
    not the same disposition in every process that runs this tool. A background
    job of a non-interactive shell — which is how the domain runner starts it —
    inherits SIGINT set to *ignore*, so the SIGINT that runner sent was a no-op
    and the server it should have stopped kept running until the container was
    killed. SIGTERM's default is the opposite failure: it dies at once, without
    reaching the `stop` that saves the world. Measured in the runner image:
    `SIGINT SIG_IGN`, `SIGTERM SIG_DFL`, and `kill -INT` on such a process
    leaves it alive.

    Both are now the clean stop, and both are installed even where the inherited
    disposition was to ignore, so a caller does not have to know which kind of
    process it started.
    """

    raise KeyboardInterrupt


def position_probe_command(player: str) -> str:
    """The console line that makes the server say where a player is.

    The acceptance for input is that the *server* observes the displacement, and
    a server does not log where anyone walks. Asking it is the only way to get
    its own answer: the reply goes to the console, which is where this runs.

    Like the summon, it is a console command, so the name is checked against the
    shape a vanilla player name has rather than escaped.
    """

    from minekin_core.domain.offline_identity import is_valid_username

    if not is_valid_username(player):
        raise SystemExit(f"not a vanilla player name: {player!r}")
    return f"data get entity {player} Pos"


def rotation_probe_command(player: str) -> str:
    """The console line that makes the server say where a player is looking.

    The other half of what a server can be asked about a Kin, and the only way to
    observe a look: a turn is not a movement, so no position reading will show one.
    Like the others it goes to the console, so the name is checked rather than
    escaped.
    """

    from minekin_core.domain.offline_identity import is_valid_username

    if not is_valid_username(player):
        raise SystemExit(f"not a vanilla player name: {player!r}")
    return f"data get entity {player} Rotation"


def use_target_command(player: str) -> str:
    """The console line that puts a use-able block in front of a player.

    A note block, three blocks ahead in the layer the Kin's eyes are in, and both
    halves of that are settled by measurement rather than by preference:

    * **A block the look cannot miss.** The first version of this put a lever
      there, and a lever's shape is `createCuboidShape(5, 0, 4, 11, 6, 12)` — six
      sixteenths of a block tall, standing on the floor of its block. A standing
      player's eyes are 0.62 of the way up their own block and the shape's top
      edge is at 0.625, so a level look passes five thousandths of a block under
      it; a look tilted down reaches it only within a narrow band of distances;
      and the one thing this run cannot do is stand still, because it is also
      measuring a walk. Walking is along the look, so the Kin carries the ray
      *along itself* and each lever is at the right distance for a tenth of a
      second. A note block is a full cube and the ray cannot miss it at any
      distance — and its `note` is not a state the world can put back.

    * **Three blocks, so the Kin walks into it.** The Kin stops against it, which
      is what turns a moving aim into a still one, and is also the walk-and-stop
      the harness waits for. It stops about 2.7 blocks later, which is more than
      the two blocks that separate a walk from a shove.

    `keep` rather than `replace`: if the space is not free the command says so
    instead of carving a hole in the world for the test to succeed in.
    """

    _checked_player(player)
    return f"execute at {player} run setblock ^ ^1 ^3 minecraft:note_block[note=0] keep"


#: What the block probe has the server say, one state each. Named here because
#: the asserter reads them and the two sides have to be one string. The state is
#: asked as a predicate rather than read as data, for a measured reason: `data get
#: block` answers for block entities and a note block is not one — this pinned
#: server replies "The target block is not a block entity". `execute if block`
#: answers `Test passed` or `Test failed`, and these words are what the command
#: has the server say on the way, because otherwise every answer is the same two
#: words whichever state was asked about.
BLOCK_CHANGED = "minekin-target-changed"
BLOCK_INITIAL = "minekin-target-initial"


def block_probe_commands(position: tuple[int, int, int]) -> tuple[str, str]:
    """The console lines that make the server say whether the block still is what
    it was placed as.

    Asked as a predicate rather than read as data, for a measured reason: `data get
    block` answers for block *entities*, and this pinned server said so when it was
    asked about a note block's `note` — "The target block is not a block entity".
    `execute if block` answers `Test passed` or `Test failed` either way, which is
    why each question has the server *say* which state it asked about.

    The position is the block's own, learned from the server's reply to the
    placement, and not a place relative to the Kin: the Kin walks, and `^ ^1 ^3`
    from a moving player asks about a hillside as soon as it has taken a step.
    """

    x, y, z = position
    return (
        f"execute if block {x} {y} {z} minecraft:note_block[note=0] run say {BLOCK_INITIAL}",
        f"execute unless block {x} {y} {z} minecraft:note_block[note=0] run say {BLOCK_CHANGED}",
    )


def initial_block_probe_command(player: str) -> str:
    """The same question, asked where the block was just put.

    The one moment the "before" of a change can be recorded without knowing the
    world's geometry: the Kin is standing three blocks back from it, in the same
    console burst as the placement, and — because the placement is three blocks
    out and the reach is four and a half — a press that lands before this question
    is answered could already have changed it. Asked relatively for exactly that
    reason: the coordinates are not known until the server has answered the
    placement, and by then the Kin has moved.
    """

    _checked_player(player)
    return (
        f"execute at {player} if block ^ ^1 ^3 minecraft:note_block[note=0] run say {BLOCK_INITIAL}"
    )


def placed_blocks(log: Path) -> tuple[tuple[int, int, int], ...]:
    """Where the server said each block it placed went, in the order it said so.

    Its reply to a `setblock` names the coordinates — measured: `Changed the block
    at -7, -60, 4` — which is the only way this tool can ask about that same block
    later without knowing the world's geometry.
    """

    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    return tuple((int(x), int(y), int(z)) for x, y, z in _BLOCK_PLACED.findall(text))


def block_spoken_of(log: Path) -> bool:
    """Whether the server has yet said the block is no longer what it was placed as."""

    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return BLOCK_CHANGED in text


def _checked_player(player: str) -> None:
    """A console command takes the name, so the name is checked, not escaped."""

    from minekin_core.domain.offline_identity import is_valid_username

    if not is_valid_username(player):
        raise SystemExit(f"not a vanilla player name: {player!r}")


def _sha1(stream: BinaryIO) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def verify_jar(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"{path} is missing; download the pinned server jar first")
    if path.stat().st_size != SERVER_SIZE:
        raise SystemExit("the server jar is not the pinned artifact")
    with path.open("rb") as stream:
        digest = _sha1(stream)
    if digest != SERVER_SHA1:
        raise SystemExit("the server jar is not the pinned artifact")


def wait_for_ready(log: Path, process: subprocess.Popen[bytes], timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if log.is_file() and READY_MARKER in log.read_text(encoding="utf-8", errors="replace"):
            return True
        if process.poll() is not None:
            return False
        time.sleep(0.5)
    return False


def stop(process: subprocess.Popen[bytes], *, timeout_s: float = 60.0) -> None:
    """Ask the server to save and exit, then insist if it does not."""

    if process.poll() is not None:
        return
    if process.stdin is not None:
        try:
            process.stdin.write(b"stop\n")
            process.stdin.flush()
        except (OSError, ValueError):
            pass
    try:
        process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--accept-eula", action="store_true")
    parser.add_argument("--ready-timeout", type=float, default=DEFAULT_READY_TIMEOUT_S)
    parser.add_argument("--keep-running", action="store_true")
    parser.add_argument(
        "--summon",
        default=None,
        metavar="ENTITY_TYPE",
        help="put one entity at the world spawn, so the world is not empty",
    )
    parser.add_argument("--java", type=Path, default=None)
    parser.add_argument(
        "--kick-player",
        default=None,
        metavar="NAME",
        help="disconnect this player once it has joined, so a release has a session cause",
    )
    parser.add_argument(
        "--kill-player",
        default=None,
        metavar="NAME",
        help="kill this player once it has joined, so a release has a cause",
    )
    parser.add_argument(
        "--kill-after-join-seconds",
        type=float,
        default=6.0,
        help="how long after the join to kill it (default 6)",
    )
    parser.add_argument(
        "--use-target",
        action="store_true",
        help="put a block in front of the probed player and ask the server for its state",
    )
    parser.add_argument(
        "--probe-player",
        default=None,
        metavar="NAME",
        help="make the server report this player's position, so a run can show movement",
    )
    parser.add_argument(
        "--probe-every-seconds",
        type=float,
        default=5.0,
        help="how often the position probe is asked (default 5)",
    )
    parser.add_argument(
        "--allow-player",
        action="append",
        default=[],
        help="offline player name to put in whitelist.json; may be repeated",
    )
    args = parser.parse_args()

    if not args.accept_eula:
        print(
            "the Minecraft EULA must be accepted by the operator: pass --accept-eula",
            file=sys.stderr,
        )
        return 2
    if args.ready_timeout <= 0:
        print("--ready-timeout must be positive", file=sys.stderr)
        return 2
    if args.probe_every_seconds <= 0:
        print("--probe-every-seconds must be positive", file=sys.stderr)
        return 2
    if args.kill_after_join_seconds <= 0:
        print("--kill-after-join-seconds must be positive", file=sys.stderr)
        return 2

    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(stop_signal, request_clean_stop)

    from minekin_core.adapters.launcher.server_profile import load_server_profile
    from minekin_core.config import java_executable

    profile = load_server_profile(PROFILE)
    properties = properties_for(profile, level_seed=FIXED_WORLD_SEED)
    verify_jar(args.jar)
    write_configuration(
        args.directory,
        properties,
        allowed_players=tuple(args.allow_player),
    )

    summon = None if args.summon is None else summon_command(args.summon)
    probe = None if args.probe_player is None else position_probe_command(args.probe_player)
    rotation = None if args.probe_player is None else rotation_probe_command(args.probe_player)
    if args.use_target and args.probe_player is None:
        # Refused rather than defaulted: "in front of" is in front of somebody,
        # and a block in front of nobody is a block this run never asked about.
        raise SystemExit("--use-target needs --probe-player to put it in front of")
    target = None if not args.use_target else use_target_command(args.probe_player or "")
    initial_block = (
        None if not args.use_target else initial_block_probe_command(args.probe_player or "")
    )
    asked_about_block = args.use_target
    #: Every block the server has said it placed, oldest first. A list rather than
    #: one position because the block is placed again and again while the Kin
    #: turns: only the one it is looking at when a press lands can be touched.
    blocks: list[tuple[int, int, int]] = []
    placements = 0
    #: Whether the burst that is owed the moment the Kin is in the world has
    #: happened. Kept apart from the cadence for the reason the comment below the
    #: loop gives: five seconds after a join is five seconds of a moving Kin.
    probed_at_join = False
    probed_player = str(args.probe_player or "")
    kill = None if args.kill_player is None else kill_command(args.kill_player)
    kick = None if args.kick_player is None else kick_command(args.kick_player)
    pending: list[tuple[str, str]] = []
    if kill is not None:
        pending.append(("killed", kill))
    if kick is not None:
        pending.append(("kicked", kick))
    watched_player = str(args.kill_player or args.kick_player or "")
    joined_at = None
    # Asked immediately: the join line the server already writes says where the
    # player started, and a probe that waited a full interval would only say it
    # again.
    next_probe = 0.0
    java = args.java or java_executable()
    log = args.directory / "server.log"
    with log.open("wb") as stream:
        process = subprocess.Popen(
            [str(java), "-Xms512M", "-Xmx1024M", "-jar", str(args.jar), "nogui"],
            cwd=str(args.directory),
            stdin=subprocess.PIPE,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
        print(f"started {process.pid}; waiting for {READY_MARKER!r} in {log}")
        try:
            ready = wait_for_ready(log, process, args.ready_timeout)
            if not ready:
                tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
                print("\n".join(tail), file=sys.stderr)
                return 1
            if summon is not None and process.stdin is not None:
                # After ready and before anything connects: the entity has to
                # exist by the time a client takes its first snapshot.
                process.stdin.write((summon + "\n").encode())
                process.stdin.flush()
                print(f"summoned: {args.summon}")
            if args.keep_running:
                print("server is up; press Ctrl+C to stop it cleanly")
                while process.poll() is None:
                    # The first reading is owed the moment the Kin is in the world
                    # rather than at the next tick of the cadence, because the join
                    # is when the scene has to be there. The Core drives the Kin the
                    # instant the world is playable — a fraction of a second later —
                    # and the heading it turns *from* is only visible before that.
                    # Measured on a run that waited for a five second cadence: the
                    # heading it turned from was never sampled, so a turn showed up
                    # as no turn and the case failed on a clock.
                    joined = (
                        not probed_at_join
                        and bool(probed_player)
                        and has_joined(log, probed_player)
                    )
                    if (
                        probe is not None
                        and process.stdin is not None
                        and (time.monotonic() >= next_probe or joined)
                    ):
                        if joined:
                            probed_at_join = True
                        # Every block the server has said it placed, which is the
                        # only way to ask about one of them later without knowing
                        # the world's geometry.
                        for position in placed_blocks(log):
                            if position not in blocks:
                                blocks.append(position)
                        if (
                            target is not None
                            and probed_at_join
                            and placements < MAX_USE_TARGETS
                            and not block_spoken_of(log)
                        ):
                            # Asked repeatedly rather than once, and that is the
                            # whole point of the repetition: the block has to be in
                            # front of the Kin *and* the Kin has to be looking at
                            # it, and at the join it is looking one way and about
                            # to be told to look another. Rather than guess when the
                            # turning has stopped, the tool keeps putting a block
                            # where the Kin is currently looking until the server
                            # says one has been used — the ones placed at the wrong
                            # moment are simply never reached.
                            #
                            # And only once the Kin is in the world: a `setblock` at
                            # a player who has not joined fails with "No entity was
                            # found", which is a line in a console nobody reads, so
                            # the tool would carry on asking about a block that was
                            # never put anywhere. Measured on a run that did exactly
                            # that — zero mentions of it in the log.
                            process.stdin.write((target + "\n").encode())
                            process.stdin.flush()
                            placements += 1
                            print(f"asked the server for a use target, number {placements}")
                            if initial_block is not None:
                                process.stdin.write((initial_block + "\n").encode())
                                process.stdin.flush()
                        process.stdin.write((probe + "\n").encode())
                        process.stdin.flush()
                        if rotation is not None:
                            # Asked alongside the position rather than behind a
                            # flag of its own: they are the two things a server
                            # can be asked about a Kin, and a look shows up in
                            # exactly one of them.
                            process.stdin.write((rotation + "\n").encode())
                            process.stdin.flush()
                        next_probe = time.monotonic() + args.probe_every_seconds
                    # The block the Kin is at, asked far more often than anything
                    # else, and for a measured reason: its state changes on every
                    # use, a held key uses it about every five ticks, and the value
                    # it cycles through comes back around to the one it was placed
                    # with. Which state a run catches by looking once is therefore
                    # a matter of when it looked, and the evidence is not that state
                    # but that the block was ever in another. Catching that needs a
                    # question asked faster than the thing it asks about: two ticks
                    # apart, against a value that holds for five.
                    if asked_about_block and blocks and process.stdin is not None:
                        for question in block_probe_commands(blocks[-1]):
                            process.stdin.write((question + "\n").encode())
                            process.stdin.flush()
                    # Console commands that end a session in the two ways the
                    # contract names separately: a death leaves the client running
                    # with a screen owning the keyboard, and a kick ends the
                    # session. Both are driven from here because only the server
                    # can start either, which is what keeps the evidence two-sided.
                    if pending and process.stdin is not None:
                        if joined_at is None and has_joined(log, watched_player):
                            joined_at = time.monotonic()
                        if (
                            joined_at is not None
                            and time.monotonic() - joined_at >= args.kill_after_join_seconds
                        ):
                            for label, command in pending:
                                process.stdin.write((command + "\n").encode())
                                process.stdin.flush()
                                print(f"{label}: {watched_player}")
                            pending.clear()
                    time.sleep(0.1)
                return process.returncode
        finally:
            stop(process)

    print(f"Controlled server: OK (ready, then stopped; {log} holds the run)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        # Only reachable outside the `--keep-running` wait: a stop signal that
        # arrives while the server is merely being started. The world is already
        # saved by the `finally` above, so this is the exit code, not a rescue.
        print("stopped by signal", file=sys.stderr)
        raise SystemExit(130) from None
