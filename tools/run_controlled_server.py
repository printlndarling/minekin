"""Start a pinned vanilla server exactly as the reviewed profile describes it.

The controlled test domain is a vanilla dedicated server on loopback with
`online-mode=false`, and a profile fixture says so. This runs it: it verifies the
pinned jar, writes the settings the profile implies, starts the JVM, waits for the
server to report itself ready, and stops it again.

Which server that is is keyed by `--version`, and each key is its own reviewed
recipe: the profile it implies, the jar bytes it pins, and the resource-pack
format it accepts. A version nobody has reviewed has no entry, and a version whose
pack format nobody has checked refuses a pack rather than being handed a number
carried over from another version.

It exists because the server half of the controlled environment needs nothing but
Java, unlike the client half. What it does *not* do is accept the EULA on anyone's
behalf — that is the operator's to accept, so it must be asked for explicitly.

Whether that server answers a status ping is asked for the same way. It is closed by
default, and closing it is what every sealed run this harness has started has meant;
so a run that needs the *server's own* reading of its target opts in by name with
`--enable-status`, and the tool then reports what it wrote by reading the settings
file back rather than by repeating what it meant to write. A request to open it on
something that is not the loopback offline channel above is refused before a run
directory exists.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import signal
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from minekin_core.adapters.launcher.server_profile import SessionServerProfile

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class ServerRecipe:
    """One reviewed version's controlled server: what it is, and what it pins.

    The profile is read through the same admission door a session reads its join
    target through, so a harness cannot start a server the product would refuse to
    connect to: the version, the loopback address and the offline auth mode are
    checked by the loader rather than assumed here.
    """

    version: str
    profile: Path
    jar_sha1: str
    jar_size: int
    #: What this version's server tells a client its resource pack is formatted as.
    #: `None` means nobody has reviewed it, so a run that asks for a pack is refused
    #: rather than given the number another version happens to use.
    resource_pack_format: int | None


#: The reviewed server recipes, keyed by the Minecraft version they serve. Adding an
#: entry is a review, not a default: the jar digest and the pack format both have to
#: be measured for that version.
SERVER_RECIPES: dict[str, ServerRecipe] = {
    "1.21.4": ServerRecipe(
        version="1.21.4",
        profile=(
            REPOSITORY_ROOT
            / "tests"
            / "fixtures"
            / "runtime-input"
            / "controlled-offline-server.json"
        ),
        jar_sha1="4707d00eb834b446575d89a61a11b5d548d8c001",
        jar_size=56_880_250,
        resource_pack_format=46,
    ),
    "1.20.1": ServerRecipe(
        version="1.20.1",
        profile=(
            REPOSITORY_ROOT
            / "tests"
            / "fixtures"
            / "runtime-input"
            / "controlled-offline-server-1.20.1.json"
        ),
        jar_sha1="84194a2f286ef7c14ed7ce0090dba59902951553",
        jar_size=47_791_053,
        resource_pack_format=None,
    ),
}
DEFAULT_SERVER_VERSION = "1.21.4"

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

#: Whether the controlled server answers a status ping, for a run that names nothing.
#: `false` is what every run this harness has ever started has written, and a domain
#: whose whole purpose is to be joined by one named Kin has no reason to announce
#: itself to whoever asks. So opening it is something a caller *names* — the
#: `--enable-status` switch below — rather than a default that moves underneath an
#: existing run. A check that has to read the server's own answer about its target
#: (the auto path resolving a bundle, or a probe that wants the version off the wire
#: rather than off a log line) is exactly the caller that names it.
DEFAULT_ENABLE_STATUS = False


#: The pack a case serves when it wants the client to *refuse* one. Built rather than
#: checked in, and built with a fixed timestamp on every entry: the URL handed to the
#: server carries the pack's SHA-1, so two runs that produced different bytes would be
#: two different scenarios. That is the lesson the Bridge jar already taught — a zip
#: written with the time of the write cannot be pinned to anything.
RESOURCE_PACK_NAME = "minekin-domain-pack.zip"


@dataclass(frozen=True, slots=True)
class ServedResourcePack:
    """Where a pack is being served, and what a client should find there."""

    url: str
    sha1: str


def resource_pack_zip(pack_format: int) -> bytes:
    """The smallest thing a client will accept as a resource pack."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        entry = zipfile.ZipInfo("pack.mcmeta", date_time=(1980, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(
            entry,
            json.dumps(
                {
                    "pack": {
                        "pack_format": pack_format,
                        "description": "Minekin controlled test domain",
                    }
                },
                sort_keys=True,
            ).encode("utf-8"),
        )
    return buffer.getvalue()


class ResourcePackServer:
    """Serves one pack, on loopback, at one path, until it is stopped.

    Vanilla fetches a required resource pack over HTTP, so a domain that wants a
    client to refuse one has to serve it from somewhere. One path and one pack: a
    server that answered any path would make "the client fetched the pack" and "the
    client fetched something" the same observation.
    """

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        payload = self._payload

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != f"/{RESOURCE_PACK_NAME}":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            # The base class's own signature, name and all: an override that narrowed
            # it would not be the method http.server calls.
            def log_message(self, format: str, *args: object) -> None:
                # The run's log is the harness's record of the session, and a client
                # fetching a pack it is about to refuse is not an event in it.
                return

        return Handler

    @property
    def served(self) -> ServedResourcePack:
        port = int(self._server.server_address[1])
        return ServedResourcePack(
            url=f"http://127.0.0.1:{port}/{RESOURCE_PACK_NAME}",
            sha1=hashlib.sha1(self._payload).hexdigest(),
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def _online_mode_text(profile: SessionServerProfile, online_mode: bool | None) -> str:
    """The one derivation of what the server will say about session verification.

    Shared by the settings that get written and by the switch that is refused before
    anything is written, so a refusal cannot disagree with the file it prevented.
    """

    if online_mode is None:
        return "false" if profile.auth_mode == "offline" else "true"
    return "true" if online_mode else "false"


def status_switch_refusal(
    profile: SessionServerProfile, *, online_mode: bool | None, enable_status: bool
) -> str | None:
    """Why this run may not open the status port, or `None` when it may.

    Asked of the same two rules the controlled channel already rests on — a saved
    loopback address, and a server whose clients authenticate offline — rather than
    of a new policy invented here. Both are the rules the module docstring states and
    the profile loader enforces for every run; this only declines to *widen* the
    channel by name. A status reply says out loud that a server is there and what it
    calls itself, which is worth nothing on a loopback port inside one container and
    worth a great deal anywhere else, so the answer to a target outside the domain,
    or to a server the client is required to fail to join, is a refusal written before
    a directory exists rather than a setting nobody re-reads.
    """

    if not enable_status:
        return None
    if not profile.is_loopback:
        return (
            "--enable-status asks the controlled server to answer a status ping, and this "
            "run's profile names a target that is not loopback; the controlled domain is "
            "loopback-only (P0 admits only a saved loopback profile, no LAN scan or DNS "
            "name), so the switch is refused rather than made to advertise a server from "
            "outside the domain"
        )
    if _online_mode_text(profile, online_mode) == "true":
        return (
            "--enable-status asks the controlled server to answer a status ping, and this "
            "run forces the server to require session verification; that is the one shape "
            "this tool documents as a server its client must never get into "
            "(AUTH_MODE_MISMATCH), and a server that announces itself there is offering the "
            "join the case exists to measure a refusal of"
        )
    return None


def read_back_enable_status(directory: Path) -> str:
    """What the settings file on disk actually says about answering status.

    Read from the file rather than returned from the argument that produced it,
    because the reading is worth nothing as a copy of the intent: the thing a caller
    needs to see is the setting the server will start up and read. `unreadable` when
    the file or the line is not there, which is the same word the domain runner prints
    for the same missing line, so the two sides of the harness name one absence.
    """

    try:
        lines = (directory / "server.properties").read_text(encoding="utf-8").splitlines()
    except OSError:
        return "unreadable"
    written = [
        value for key, _, value in (line.partition("=") for line in lines) if key == "enable-status"
    ]
    return written[-1] if written else "unreadable"


def properties_for(
    profile: object,
    *,
    level_seed: str,
    online_mode: bool | None = None,
    resource_pack: ServedResourcePack | None = None,
    enable_status: bool = DEFAULT_ENABLE_STATUS,
    difficulty: str = "normal",
) -> dict[str, str]:
    """The server settings the frozen profile implies, plus one refusal to imply.

    `online-mode` is derived from the profile's `auth_mode`, which describes how *our*
    client authenticates, because a controlled run wants the two to agree. The
    override exists for the one case that needs them to disagree: an offline client
    dialling a server that requires session verification, which the supply-chain
    contract says must end in `AUTH_MODE_MISMATCH` and must never be worked around.
    The switch is here rather than in the profile because the product deliberately has
    no online-mode admission path: the point of that case is that the client cannot
    satisfy the server, not that it should try.

    `enable_status` is the other switch, and it is a plain opt-in with the reviewed
    default on the silent side: a run that wants this server to answer a status ping
    says so through `--enable-status`, and every other run gets exactly the settings
    file it has always got.
    """

    from minekin_core.adapters.launcher.server_profile import SessionServerProfile

    assert isinstance(profile, SessionServerProfile)
    if difficulty not in {"peaceful", "easy", "normal", "hard"}:
        raise ValueError("difficulty must be peaceful, easy, normal or hard")
    return {
        "online-mode": _online_mode_text(profile, online_mode),
        # A pack the client is required to have, served by this harness for the case
        # where the profile's policy is to refuse one. Empty when nothing is served,
        # which is what every other run has.
        "require-resource-pack": "true" if resource_pack is not None else "false",
        "resource-pack": "" if resource_pack is None else resource_pack.url,
        "resource-pack-sha1": "" if resource_pack is None else resource_pack.sha1,
        "server-ip": profile.host,
        "server-port": str(profile.port),
        "gamemode": "survival",
        "force-gamemode": "true",
        "difficulty": difficulty,
        "hardcore": "false",
        "pvp": "true",
        "enable-rcon": "false",
        "enable-query": "false",
        # The one switch here that the profile does not imply, and so the one a caller
        # has to name. See `DEFAULT_ENABLE_STATUS`.
        "enable-status": "true" if enable_status else "false",
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


#: The phases a `--time-phase` schedule may name, as the tick each sets. Numbers rather
#: than the console's own day/noon/night words: the word is a promise about the sky the
#: server is free to redefine between versions, while the number is what the run record
#: can be read against afterwards.
TIME_PHASES = {
    "day": 1000,
    "noon": 6000,
    "sunset": 12000,
    "night": 14000,
    "midnight": 18000,
}


def parse_time_phases(specs: list[str]) -> list[tuple[float, str]]:
    """The `(seconds after the first join, console line)` schedule, or a refusal.

    One in-game day is twenty real minutes, so a run that wants several days of
    survival — nights with the threats they bring — spends an hour to see three.
    The schedule compresses the wall clock without lying about the sky: each line
    is a real `time set` the server applies to the real world clock, so spawning,
    light and the observation's own `game_tick` all move as they would if the days
    had simply passed. Seconds are measured from the moment a player first joined,
    which is when there is a world for a Kin to survive in; a schedule therefore
    cannot fire into an unjoined server and mistake the quiet for calm.
    """

    schedule: list[tuple[float, str]] = []
    seen: set[float] = set()
    for spec in specs:
        seconds_text, separator, phase = spec.partition(":")
        if not separator or phase not in TIME_PHASES:
            raise SystemExit(
                f"not a SECONDS:PHASE time phase: {spec!r} "
                f"(phases: {', '.join(sorted(TIME_PHASES))})"
            )
        try:
            seconds = float(seconds_text)
        except ValueError:
            raise SystemExit(f"not a number of seconds: {spec!r}") from None
        if not seconds > 0:
            raise SystemExit(f"a time phase at {seconds:g}s is not after the join: {spec!r}")
        if seconds in seen:
            raise SystemExit(f"two time phases at +{seconds:g}s would race: {spec!r}")
        seen.add(seconds)
        schedule.append((seconds, f"time set {TIME_PHASES[phase]}"))
    return sorted(schedule)


#: The server's own line when anyone joins: the anchor the time schedule counts from.
#: Not tied to a probed name, because the schedule is about the world's clock and not
#: about which account is standing in it.
PLAYER_JOINED = re.compile(r"\b[A-Za-z0-9_]{1,16} joined the game\b")


def any_player_joined(log: Path) -> bool:
    """Whether the server has said anyone is in the world."""

    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return PLAYER_JOINED.search(text) is not None


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


def probe_console_commands(players: list[str]) -> list[str]:
    """Every console line one probe tick owes, in the order the server must read them.

    Position then rotation, per named kin, and the pair stays adjacent because a
    look shows up in exactly one of the two: asking both kins one half first would
    let the second half land after the kin had turned again. One name therefore
    yields the same two lines in the same order the tool asked them before this
    could take more than one, and no name yields no line at all.

    The reason more than one name is worth the repetition is a reading a single
    name cannot give: one run has to be able to ask a still entity and a moving one
    in the same tick, or "the joiner walked" and "the whole world drifted" are the
    same bytes in the log.
    """

    commands: list[str] = []
    for player in players:
        commands.append(position_probe_command(player))
        commands.append(rotation_probe_command(player))
    return commands


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


def resource_trunk_commands(player: str) -> list[str]:
    """The three console lines that stack a breakable resource in front of a player.

    The controlled world is flat and fixed-seed (see `FIXED_WORLD_SEED` and the
    `minecraft:flat` `level-type`), so it grows no trees and a world-skill run whose
    first step is `break_seen_block` would have nothing in the Kin's look to break.
    This puts the resource there itself, three blocks ahead of the named kin, and
    every choice is settled by measurement rather than preference:

    * **`minecraft:oak_log`, because it is the one block the plan can work with.** A
      full cube, so the look's ray cannot miss it at any distance — the same reason
      `use_target_command` abandoned the lever for a note block. It is breakable bare-
      handed, which is what a survival Kin holding nothing has, and its drop is the
      item the plan then walks to collect: `collect_dropped` reaches for exactly the
      thing the breaking left behind.

    * **Three blocks, for the same geometry `use_target_command` documents.** The reach
      is four and a half blocks and the Kin walks into what is in front of it, so three
      blocks out is within reach without being inside the body, and the walk-and-stop it
      forces is the one the harness waits for.

    * **Three stacked, feet / eye / above-eye (`^ ^ ^3`, `^ ^1 ^3`, `^ ^2 ^3`).** One
      log yields four planks and the plan spends five, so a single block could not
      carry the craft; three logs stacked at those relative heights put the whole trunk
      in the look without the Kin having to aim up or down to reach all of it.

    `keep` rather than `replace`, for the reason this tool already gives above: if a
    space is not free the command says so instead of carving the world to make the test
    pass. Unlike the use target, these are written once — the point of a resource is
    that breaking it makes it go away and leave a drop, so re-placing it every turn
    would erase the very change the run exists to observe.
    """

    _checked_player(player)
    return [
        f"execute at {player} run setblock ^ ^ ^3 minecraft:oak_log keep",
        f"execute at {player} run setblock ^ ^1 ^3 minecraft:oak_log keep",
        f"execute at {player} run setblock ^ ^2 ^3 minecraft:oak_log keep",
    ]


def meal_commands(player: str) -> list[str]:
    """Begin a bounded hunger preparation, before any food is handed out.

    The runner polls foodLevel, explicitly clears Hunger at food <= 6, then
    gives three apples only after the server confirms that specific clear.
    meal-ready.json is written only after the give acknowledgement. This is
    test setup, not a player observation or proof of a successful consume.
    """

    _checked_player(player)
    from tools.hungry_fixture import HungryFixture

    return HungryFixture(player).begin("", 0)


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


def verify_jar(path: Path, recipe: ServerRecipe) -> None:
    """The jar must be the bytes this version's recipe pins, or nothing starts."""

    if not path.is_file():
        raise SystemExit(f"{path} is missing; download the pinned server jar first")
    if path.stat().st_size != recipe.jar_size:
        raise SystemExit(f"the {recipe.version} server jar is not the pinned artifact")
    with path.open("rb") as stream:
        digest = _sha1(stream)
    if digest != recipe.jar_sha1:
        raise SystemExit(f"the {recipe.version} server jar is not the pinned artifact")


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
    parser.add_argument(
        "--version",
        choices=sorted(SERVER_RECIPES),
        default=DEFAULT_SERVER_VERSION,
        help=(
            "which reviewed server recipe to run: it picks the profile, the pinned jar "
            f"digest and the resource-pack format (default: {DEFAULT_SERVER_VERSION})"
        ),
    )
    parser.add_argument("--accept-eula", action="store_true")
    parser.add_argument("--ready-timeout", type=float, default=DEFAULT_READY_TIMEOUT_S)
    parser.add_argument("--keep-running", action="store_true")
    parser.add_argument(
        "--summon",
        default=None,
        metavar="ENTITY_TYPE",
        help="put one entity at the world spawn, so the world is not empty",
    )
    parser.add_argument(
        "--time-phase",
        action="append",
        default=[],
        metavar="SECONDS:PHASE",
        help=(
            "set the world clock to a phase this many seconds after the first join; "
            "repeat for a schedule (phases: " + ", ".join(sorted(TIME_PHASES)) + ")"
        ),
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
        "--resource-trunk",
        action="store_true",
        help=(
            "stack three oak logs in the probed player's look, so a world-skill run has "
            "a breakable resource in front of it on the flat world; written once, at the "
            "same moment the use target is owed, and refused alongside --use-target"
        ),
    )
    parser.add_argument(
        "--hungry-kin",
        action="store_true",
        help=(
            "feed the probed player three apples and drain its hunger bar to nothing "
            "with one short steep hunger effect, so a world-skill run has a low bar "
            "and a meal the number key can reach; written once, at the join, and "
            "refused alongside --use-target, which keeps a block where the meal "
            "needs a clear crosshair"
        ),
    )
    parser.add_argument(
        "--probe-player",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "make the server report this player's position, so a run can show "
            "movement; may be repeated, and every named kin is then asked on the "
            "same tick, so one run can hold one still while another moves"
        ),
    )
    parser.add_argument(
        "--probe-every-seconds",
        type=float,
        default=5.0,
        help="how often the position probe is asked (default 5)",
    )
    parser.add_argument(
        "--resource-pack",
        action="store_true",
        help=(
            "serve a resource pack and require it, so a client whose profile policy is "
            "to refuse one is refused by the server; the pack is built here and served "
            "on loopback, and its sha1 goes into the server's settings"
        ),
    )
    parser.add_argument(
        "--online-mode",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "force the server's online-mode instead of deriving it from the profile; "
            "a case uses this to make an offline client meet a server that requires "
            "session verification, which must end in AUTH_MODE_MISMATCH. Omit to "
            "derive it from the profile, as every other run does"
        ),
    )
    parser.add_argument(
        "--difficulty", choices=("peaceful", "easy", "normal", "hard"), default="normal"
    )
    parser.add_argument(
        "--enable-status",
        action="store_true",
        help=(
            "write enable-status=true so this server answers a status ping; without it "
            f"the run gets the reviewed default (enable-status="
            f"{str(DEFAULT_ENABLE_STATUS).lower()}), which is what every sealed run so "
            "far has started with. The value actually written is read back out of the "
            "settings file and printed. Refused for a target that is not the loopback "
            "offline domain, or for a server forced to require session verification"
        ),
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
    if args.hungry_kin and args.difficulty == "peaceful":
        print(
            "--hungry-kin requires a difficulty that preserves hunger; peaceful refused",
            file=sys.stderr,
        )
        return 2
    if args.probe_every_seconds <= 0:
        print("--probe-every-seconds must be positive", file=sys.stderr)
        return 2
    if len(set(args.probe_player)) != len(args.probe_player):
        # Refused rather than deduplicated: two names that are the same name ask one
        # kin twice, and a run that reports "still Kin, moving Kin" from one entity
        # is the one failure this harness cannot tell apart from a real contrast.
        print(
            "--probe-player names must be distinct, a repeated one asks the same kin "
            f"twice: {args.probe_player}",
            file=sys.stderr,
        )
        return 2
    if args.kill_after_join_seconds <= 0:
        print("--kill-after-join-seconds must be positive", file=sys.stderr)
        return 2

    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(stop_signal, request_clean_stop)

    from minekin_core.adapters.launcher.server_profile import load_session_server_profile
    from minekin_core.config import java_executable

    recipe = SERVER_RECIPES[args.version]
    # The same admission door the session joins through, so this harness cannot start
    # a server the product would refuse to connect to.
    profile = load_session_server_profile(recipe.profile, minecraft_version=recipe.version)
    # Asked of the profile and of this run's own overrides, and answered before
    # anything at all is written: a switch that cannot be safe on this channel is a
    # refusal, not a setting that lands in a run directory and gets read by a server.
    refused = status_switch_refusal(
        profile, online_mode=args.online_mode, enable_status=args.enable_status
    )
    if refused is not None:
        print(refused, file=sys.stderr)
        return 2
    pack_server: ResourcePackServer | None = None
    if args.resource_pack:
        if recipe.resource_pack_format is None:
            print(
                f"the resource pack format for Minecraft {recipe.version} has not been"
                " reviewed; refusing to serve a pack with a number borrowed from another"
                " version",
                file=sys.stderr,
            )
            return 2
        pack_server = ResourcePackServer(resource_pack_zip(recipe.resource_pack_format))
        pack_server.start()
    properties = properties_for(
        profile,
        level_seed=FIXED_WORLD_SEED,
        online_mode=args.online_mode,
        resource_pack=None if pack_server is None else pack_server.served,
        enable_status=args.enable_status,
        difficulty=args.difficulty,
    )
    verify_jar(args.jar, recipe)
    write_configuration(
        args.directory,
        properties,
        allowed_players=tuple(args.allow_player),
    )
    # The value reported is the value the file holds, taken back off the disk: what
    # the server will read when it starts is the fact a run needs, and repeating the
    # argument that produced it would only prove this script agrees with itself.
    written_status = read_back_enable_status(args.directory)
    print(
        f"enable-status: asked for {'true' if args.enable_status else 'false'},"
        f" the settings written say {written_status}"
    )

    summon = None if args.summon is None else summon_command(args.summon)
    time_phases = parse_time_phases(args.time_phase)
    probe_players = list(args.probe_player)
    probe = probe_console_commands(probe_players)
    if args.use_target and not probe_players:
        # Refused rather than defaulted: "in front of" is in front of somebody,
        # and a block in front of nobody is a block this run never asked about.
        raise SystemExit("--use-target needs --probe-player to put it in front of")
    if args.use_target and len(probe_players) > 1:
        # Same reason, one step further: the block goes into one kin's look, so two
        # names leave the run unable to say whose walk it stopped.
        raise SystemExit(
            "--use-target puts a block in front of one kin's look, and "
            f"{len(probe_players)} --probe-player names do not say which: {probe_players}"
        )
    if args.resource_trunk and not probe_players:
        # The same shape as `--use-target`: the trunk is stacked in somebody's look,
        # and a trunk in front of nobody is a resource this run never aimed at.
        raise SystemExit("--resource-trunk needs --probe-player to put it in front of")
    if args.resource_trunk and len(probe_players) > 1:
        # And the same one step further: the trunk goes into one kin's look, so two
        # names leave the run unable to say whose breaking it is waiting for.
        raise SystemExit(
            "--resource-trunk stacks blocks in front of one kin's look, and "
            f"{len(probe_players)} --probe-player names do not say which: {probe_players}"
        )
    if args.resource_trunk and args.use_target:
        # Both ask for a block in the one kin's look, and a look holding two does not
        # say which one the Kin is meant to break — the note block is pressed, the oak
        # log is broken, and a run carrying both cannot tell the two scenes apart.
        raise SystemExit(
            "--resource-trunk and --use-target both put a block in the same kin's look, "
            "and two blocks do not say which one the Kin is supposed to break"
        )
    if args.hungry_kin and not probe_players:
        # The shape `--use-target` and `--resource-trunk` share: a meal is given to
        # somebody, and a meal given to nobody is a bar this run never read.
        raise SystemExit("--hungry-kin needs --probe-player to feed")
    if args.hungry_kin and len(probe_players) > 1:
        # One kin, for the same reason one look is one look: two fed names leave the
        # run unable to say whose bar the meal was for.
        raise SystemExit(
            "--hungry-kin feeds one kin, and "
            f"{len(probe_players)} --probe-player names do not say which: {probe_players}"
        )
    if args.hungry_kin and args.use_target:
        # The meal's Core-side precondition needs the crosshair on nothing (a use that
        # lands on a block goes to the block first), and `--use-target` keeps a block
        # where the Kin is looking; together they would make every meal a refusal.
        raise SystemExit(
            "--hungry-kin needs the crosshair to land on nothing for a meal, and "
            "--use-target keeps a block where the kin is looking; the pair would "
            "make every meal a refusal"
        )
    target = None if not args.use_target else use_target_command(probe_players[0])
    initial_block = None if not args.use_target else initial_block_probe_command(probe_players[0])
    resource_trunk = None if not args.resource_trunk else resource_trunk_commands(probe_players[0])
    from tools.hungry_fixture import HungryFixture

    meal = None if not args.hungry_kin else HungryFixture(probe_players[0])
    #: Whether the trunk's three logs have gone in. Kept once, and the whole reason it
    #: is once rather than a cadence: unlike the use target the trunk is not re-placed
    #: while the Kin turns, because its breaking is the observation the run wants.
    trunk_placed = False
    #: Whether the meal has been served. Written once for the trunk's own reason: the
    #: apples are the resource the run eats, and re-giving them would refill the bag the
    #: confirmation is counting down.
    meal_served = False
    meal_player = probe_players[0] if args.hungry_kin else ""
    asked_about_block = args.use_target
    #: Every block the server has said it placed, oldest first. A list rather than
    #: one position because the block is placed again and again while the Kin
    #: turns: only the one it is looking at when a press lands can be touched.
    blocks: list[tuple[int, int, int]] = []
    placements = 0
    #: The names whose owed-at-join burst has happened. Kept per name rather than as
    #: one flag for the reason the comment below the loop gives: five seconds after a
    #: join is five seconds of a moving Kin, and the second kin joins on its own clock.
    bursted: set[str] = set()
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
    # The `--time-phase` clock: when the first join happened, and which scheduled line is
    # next. Untouched when no schedule was given, so runs without one pay nothing.
    time_anchor: float | None = None
    next_time_phase = 0
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
                    joined = [
                        name
                        for name in probe_players
                        if name not in bursted and has_joined(log, name)
                    ]
                    if (
                        probe
                        and process.stdin is not None
                        and (time.monotonic() >= next_probe or joined)
                    ):
                        if joined:
                            bursted.update(joined)
                        # Every block the server has said it placed, which is the
                        # only way to ask about one of them later without knowing
                        # the world's geometry.
                        for position in placed_blocks(log):
                            if position not in blocks:
                                blocks.append(position)
                        if (
                            target is not None
                            and bursted
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
                        if resource_trunk is not None and bursted and not trunk_placed:
                            # The same owed-at-join moment as the use target, and for the
                            # same measured reason: `setblock` at a player who has not
                            # joined fails with "No entity was found", a line in a console
                            # nobody reads. But written once and never again — the trunk is
                            # the resource the Kin breaks, and re-placing it each turn would
                            # erase the drop the plan is there to collect.
                            trunk_placed = True
                            for line in resource_trunk:
                                process.stdin.write((line + "\n").encode())
                                process.stdin.flush()
                            print(
                                f"placed the resource trunk for {probe_players[0]}: "
                                "three minecraft:oak_log blocks stacked in its look at "
                                "^ ^3 (feet ^ ^ ^3, eye ^ ^1 ^3, above-eye ^ ^2 ^3)"
                            )
                        for command in probe:
                            process.stdin.write((command + "\n").encode())
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
                    if meal is not None and not meal_served and process.stdin is not None:
                        text = log.read_text(encoding="utf-8", errors="replace")
                        commands = []
                        if meal.phase == "waiting_join":
                            if has_joined(log, meal_player):
                                commands = meal.begin(text, time.monotonic())
                        else:
                            commands = meal.update(text, time.monotonic())
                        for line in commands:
                            process.stdin.write((line + "\n").encode())
                            process.stdin.flush()
                        if meal.phase == "ready":
                            marker = {
                                "state": "ready",
                                "player": meal_player,
                                "food": meal.food,
                                "effectClearConfirmed": True,
                                "mealGivenConfirmed": True,
                                "observedAt": datetime.now(UTC).isoformat(),
                            }
                            marker_path = args.directory / "meal-ready.json"
                            pending_marker = args.directory / "meal-ready.pending.json"
                            pending_marker.write_text(json.dumps(marker), encoding="utf-8")
                            pending_marker.replace(marker_path)
                            meal_served = True
                            print(f"hungry fixture ready for {meal_player}; hunger effect cleared")
                    # The `--time-phase` schedule: anchored at the first join, one line
                    # written per due phase. A console write from here, like the other
                    # fixtures — the server stays the only side that changes the world.
                    if time_phases and process.stdin is not None:
                        if time_anchor is None and any_player_joined(log):
                            time_anchor = time.monotonic()
                            print("time phases anchored: a player is in the world")
                        if time_anchor is not None:
                            elapsed = time.monotonic() - time_anchor
                            while (
                                next_time_phase < len(time_phases)
                                and elapsed >= time_phases[next_time_phase][0]
                            ):
                                seconds, line = time_phases[next_time_phase]
                                process.stdin.write((line + "\n").encode())
                                process.stdin.flush()
                                print(f"time phase at +{seconds:g}s after join: {line}")
                                next_time_phase += 1
                    time.sleep(0.1)
                return process.returncode
        finally:
            stop(process)
            if pack_server is not None:
                pack_server.stop()

    print(f"Controlled server: OK (ready, then stopped; {log} holds the run)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        # Only reachable outside the `--keep-running` wait: a stop signal that
        # arrives while the server is merely being started. The world is already
        # saved by the `finally` above, so this is the exit code, not a rescue.
        print("stopped by signal", file=sys.stderr)
        raise SystemExit(130) from None
