"""Deciding whether a finished run's evidence satisfies the case it was run for.

After a run ends, three things are read together: the server's own log, the
server's own user cache, and Core's own run document. The case's declared
assertions are then evaluated against them, and the verdict is a list of names —
which were expected, which were seen, and which were expected and not seen.

This is a tool rather than product code because of what it reads. The server log
and `usercache.json` are server truth, and the validation contract puts them
outside every product path: the managed client is never allowed to learn what
the server thinks of it. Doing the comparison here is what keeps it in the test
domain instead of in the Kin's belief.

It decides and does not write. Whatever seals a bundle asks this module and
records its answer verbatim, so the verdict and the sealed record cannot come
apart — there is one place that turns evidence into a judgement, and a bundle
that disagreed with it would have to have been written by something else.

Exit codes: 0 judged and held, 1 judged and failed, 2 could not judge. A case
naming an assertion nothing implements cannot be judged, and that is not the
same answer as "failed" — it is the answer that says nothing was checked.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from minekin_core.cli.init import DATABASE_NAME, KIN_DIRECTORY, kin_directory, run_root
from minekin_core.cli.session import session_overlay_path
from minekin_core.domain.cases import parse_case_manifest
from minekin_core.domain.ids import KinId
from minekin_core.domain.offline_identity import offline_player_uuid

# The record's reader lives beside this file, and this is the module that judges
# it. One reader, so the shape a record is sealed in and the shape it is judged by
# cannot be two dialects of the same idea.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fault_injection
from fault_injection import (
    CLIENT_JVM,
    DELIVERED,
    IDENTITY_DISAPPEARED,
    INJECTED,
    NO_METHOD,
    RUNTIME_CONTROLLER,
    SERVER_JVM,
    SIGKILL,
    FaultInjectionError,
)

EXIT_HELD = 0
EXIT_FAILED = 1
EXIT_UNJUDGED = 2

# Vanilla writes both of these through the same `[Server thread/INFO]` logger, so
# the pattern is the log's shape rather than a guess about its wording: the
# bracketed time, the thread, the level, then the sentence.
_LINE = r"\[[^\]]*\] \[Server thread/INFO\]: {name} {event}"

RUN_DOCUMENT_KEY = "run"

# The reviewed session event types this module needs to name. They are the
# ledger's vocabulary, and a case that reads Core's own record has to speak it.
PROCESS_STARTED = "SessionProcessStarted"
SESSION_INTERRUPTED = "SessionInterrupted"
HELLO_ACCEPTED = "BridgeHelloAccepted"
JOIN_OBSERVED = "JoinObserved"
PLAYABLE_ESTABLISHED = "PlayableEstablished"
INPUT_LEASE_GRANTED = "InputLeaseGranted"
INPUT_RELEASED = "InputReleased"
INPUT_REFUSED = "InputRefused"

#: The reviewed capability a move is granted under, and the reason a lease that
#: simply ran out records.
MOVE_CAPABILITY = "control.move.v1"
TIMEOUT = "TIMEOUT"

#: What reconciliation reports when it finished and nothing was left to decide.
#: The word is the producer's (`RecoveryReport.as_dict`), named here rather than
#: spelled out at the comparison so the two cannot drift apart quietly.
RECONCILED = "reconciled"

#: The arbiter's own word for "this session has not admitted a snapshot, so it may
#: not be driven", and the connection phase a run is in when that is the answer:
#: it has joined, and it is not playable. The pair is what makes "asked too early"
#: a fact about a run rather than a reading of its intent.
NOT_PLAYABLE = "NOT_PLAYABLE"
JOIN_SEEN_PHASE = "JOIN_SEEN"

#: What the Bridge writes when it acts on an input at all. Measured on real runs:
#: `bridge pressed use.hand` and `bridge applied 0047d1b8…: holding [move.forward]`
#: — one line per press, which is what makes "nothing was ever held" a claim the
#: client's own log can support rather than a claim about Core's intentions.
_BRIDGE_PRESS = re.compile(r"bridge (?:pressed [\w.]+|applied \w+: holding \[[^\]]*\])")

#: The reason the Bridge records when the runtime it was talking to went away,
#: and the line it writes when it lets go. Measured, from a run whose Core was
#: killed: `bridge released 1 input(s) after IPC_LOST`.
IPC_LOST = "IPC_LOST"
_BRIDGE_RELEASE = re.compile(r"released (\d+) input\(s\) after ([A-Z_]+)")
_PLAY_ENDED_RELEASE = re.compile(r"released (\d+) input\(s\) after LEFT_PLAYABLE \(PLAY_ENDED\)")

#: What the Bridge writes when it acts on a cancel. Measured in a run against a
#: black hole, after the attempt reached `LOGIN_NEGOTIATING` and stayed there.
CANCEL_LINE = "bridge is cancelling the client's connection"

#: The category the Bridge gives a server that refuses the Kin, and the phase
#: Core records it under. Measured: the ledger holds
#: `SessionInterrupted {phase: FAILED, reason: …WHITELIST_REJECTED}`, and the
#: client's own log holds the Bridge's line naming the same category. The
#: server's sentence never enters a product event; the category is what does.
WHITELIST_REJECTED = "ADMISSION_FAILURE_REASON_WHITELIST_REJECTED"
REFUSAL_LINE = f"bridge classified the login failure as {WHITELIST_REJECTED}"

#: What counts as having walked. Measured: vanilla survival walking is about 4.3
#: blocks per second, and the thing this has to tell a step apart from is a shove
#: — a summoned pig wandering into the Kin moves it well under a block, so the
#: threshold is the gap between the two, not a tuned number. The harness uses the
#: same number to decide when to stop waiting, for the same reason.
MINIMUM_STEP_BLOCKS = 2.0

#: The connection states that claim the session is in a world. Everything else —
#: the phases before a join, and the terminal states an attempt ends in — is not
#: a world this run was ever in.
WORLD_CLAIMING_STATES = frozenset({"PLAYABLE", "JOIN_SEEN"})

#: What the server answers when it is asked where something is. Vanilla replies
#: to a data query with `has the following entity data: [x, y, z]` for a position
#: and `[yaw, pitch]` for a rotation: two components or three, and that is what
#: tells the two readings apart.
_PROBE = re.compile(r"has the following entity data: \[([^\]]*)\]")

#: What the server says when it is asked whether the block in front of the Kin is
#: still what the harness placed there. A predicate rather than a value, for a
#: measured reason: `data get block` answers for block entities and a note block
#: is not one — this pinned server replies "The target block is not a block
#: entity". `execute if block` answers `Test passed` or `Test failed` either way,
#: so the words below are what the harness has the server say on the way.
BLOCK_INITIAL = "minekin-target-initial"
BLOCK_CHANGED = "minekin-target-changed"
_BLOCK = re.compile(rf"{BLOCK_INITIAL}|{BLOCK_CHANGED}")

_LEDGER_COLUMNS = (
    "position, event_id, event_type, schema_version, kin_id, run_id, "
    "client_instance_id, session_id, generation, world_context_id, sequence, "
    "correlation_id, causation_id, monotonic_ns, observed_at_utc, source, "
    "trust_class, payload_json, payload_hash"
)


def probe_readings(log: str, components: int) -> tuple[tuple[float, ...], ...]:
    """The server's own answers, one per probe that asked for this shape."""

    readings: list[tuple[float, ...]] = []
    for match in _PROBE.finditer(log):
        parts = [part.strip().rstrip("df") for part in match.group(1).split(",")]
        if len(parts) != components:
            continue
        try:
            readings.append(tuple(float(part) for part in parts))
        except ValueError:
            continue
    return tuple(readings)


def _sentence(name: str, event: str) -> re.Pattern[str]:
    return re.compile(_LINE.format(name=re.escape(name), event=re.escape(event)))


class Unreadable(Exception):
    """The material a case needs is not there or is not readable."""


def ledger_rows(database: Path, run_id: str) -> list[dict[str, object]]:
    """This run's events, as the ledger recorded them.

    Read-only, and scoped by run id: the ledger is one file for every run a Kin
    has ever had, and a case judged against another run's events would be judged
    against nothing. A missing database is not raised here — the caller decides
    whether a case needs the ledger at all, and a run whose ledger cannot be read
    must look different from a run that recorded nothing.
    """

    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            f"SELECT {_LEDGER_COLUMNS} FROM event WHERE run_id = ? ORDER BY position",
            (run_id,),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def timeline_bytes(events: Sequence[Mapping[str, object]]) -> bytes:
    """The same rows as a sealed artifact: one JSON object per line."""

    return "".join(json.dumps(dict(event), sort_keys=True) + "\n" for event in events).encode(
        "utf-8"
    )


def previous_run_rows(database: Path, run_id: str) -> tuple[str, list[dict[str, object]]]:
    """The run this one followed in the same ledger, and that run's events.

    A restart is only a restart because something ran before it, and the ledger is
    where that is: the run whose last row sits immediately before this run's first.
    Order is the ledger's own `position` and never a clock — the ledger is the one
    record of the order its rows were written in.

    Returns an empty name when this run is the first for its Kin, or when the
    ledger holds nothing for it at all: "there was nothing before this" and "this
    run is not in the ledger" are different failures, and the caller already has
    `ledger_readable` for the second.
    """

    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        found = connection.execute(
            "SELECT run_id FROM event WHERE position < "
            "(SELECT MIN(position) FROM event WHERE run_id = ?) "
            "ORDER BY position DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if found is None:
            return "", []
        previous = str(found["run_id"])
        rows = connection.execute(
            f"SELECT {_LEDGER_COLUMNS} FROM event WHERE run_id = ? ORDER BY position",
            (previous,),
        ).fetchall()
    finally:
        connection.close()
    return previous, [dict(row) for row in rows]


@dataclass(frozen=True, slots=True)
class RunMaterial:
    """What a finished run left behind, as the asserter reads it.

    Two records of the same run that do not know about each other: Core's own
    run document, and the ledger Core kept as it went. The server's log and the
    server's user cache are the third party in the room, and they are the only
    one allowed to say what the game did.
    """

    #: Which run this is. Read from the document when there is one and from the
    #: ledger when there is not, so both kinds of run are named the same way.
    kin_id: str
    run_id: str
    #: Where the client kept its game directory, which is where its logs are:
    #: from the document when it says, and from the ledger's own record of the
    #: session it started otherwise.
    overlay: Path | None
    run_document: Mapping[str, object]
    #: What the client wrote, which is where the Bridge's own lines are.
    client_log: str
    #: This run's ledger events, in the order they were recorded.
    ledger_events: tuple[Mapping[str, object], ...]
    #: False when there is no readable ledger at all. Assertions that need one say
    #: so rather than reading an empty list as "this never happened".
    ledger_readable: bool
    #: The run this one followed in the same Kin's ledger, and that run's events.
    #: A case about a restart reads what the crash left behind, and this is where
    #: that is: without it, a restart cannot be told from a first run that merely
    #: looks quiet. Empty when this run is the Kin's first.
    previous_run_id: str
    previous_run_events: tuple[Mapping[str, object], ...]
    server_log: str
    #: The name-to-UUID map the *server* wrote when somebody logged in. The
    #: client's own claim about who it is is not evidence of who the server saw.
    server_identities: Mapping[str, str]
    username: str
    #: The record the harness wrote when it killed a process, or None for a run
    #: that injected no fault. Read once and carried, so a case about a fault is
    #: judged against the same bytes that were sealed rather than against a file
    #: that may have been rewritten in between.
    fault_injection: Mapping[str, object] | None = None
    #: A bounded soak's samples, exactly as the harness wrote them, and the record
    #: of what it was asked for. Empty for a run that did not soak — which is not
    #: the same shape as a soak that produced nothing.
    soak_samples: str = ""
    soak_summary: Mapping[str, object] | None = None
    #: The reviewed case being evaluated.  `evaluate` fills these from the same
    #: manifest that declares the assertions, so a trace attributed to another
    #: case (or another revision of this case) cannot satisfy this one.
    expected_case_id: str | None = None
    expected_case_version: str | None = None

    def recorded(self, event_type: str) -> tuple[Mapping[str, object], ...]:
        """Every event of one type this run recorded."""

        return tuple(event for event in self.ledger_events if event.get("event_type") == event_type)

    def has(self, event_type: str) -> bool:
        return bool(self.recorded(event_type))

    def run(self) -> Mapping[str, object]:
        value = self.run_document.get(RUN_DOCUMENT_KEY)
        if not isinstance(value, Mapping):
            raise Unreadable("the run document carries no run section")
        return cast(Mapping[str, object], value)

    def join_line(self) -> int | None:
        """Where the server logged this Kin joining, or None if it never did."""

        found = _sentence(self.username, "joined the game").search(self.server_log)
        return None if found is None else found.start()

    def leave_line(self) -> int | None:
        found = _sentence(self.username, "left the game").search(self.server_log)
        return None if found is None else found.start()


def _ledger_run(events: Sequence[Mapping[str, object]], kin: str) -> Mapping[str, object]:
    """What one ledger row says about the run that wrote it."""

    for event in events:
        if event.get("event_type") == PROCESS_STARTED:
            return payload(event)
    return {}


def _overlay_for(data_root: Path, kin: str, events: Sequence[Mapping[str, object]]) -> Path | None:
    """Where a run's client kept its own logs, from the ledger's own record.

    The session and generation come out of the run's first event, which is the
    launcher's own account of what it started. A run whose Core was killed has no
    document to say where its overlay was, and the ledger is the record that
    survived it.
    """

    started = _ledger_run(events, kin)
    session_id, generation = started.get("session_id"), started.get("generation")
    if (
        not isinstance(session_id, str)
        or isinstance(generation, bool)
        or not isinstance(generation, int)
    ):
        return None
    return session_overlay_path(run_root(data_root, KinId(kin)), session_id, generation)


def read_run_material(
    *,
    run_document: Path | None,
    data_root: Path,
    server_directory: Path | None,
    username: str,
    run_id: str | None = None,
    fault_injection: Mapping[str, object] | None = None,
    soak_samples: str = "",
    soak_summary: Mapping[str, object] | None = None,
) -> RunMaterial:
    """Read a finished run's material, refusing anything that is not readable.

    A run is named either by the document Core printed at its end or by its run
    id, and the second exists because a run whose Core was killed never printed
    one: the whole point of that case is that nothing was left to print. What the
    document would have said about the run's identity is then read from the
    ledger, which is Core's own record of the same run up to the moment it
    stopped being able to write.

    The ledger is looked up from the data root, and a missing database is *not*
    an error here: a case that never needs Core's own record must still be
    judgeable on a host where the ledger is gone. What it must never be is
    indistinguishable from a ledger that was read and had nothing in it — hence
    `ledger_readable`, which the assertions that need one check before reporting
    that they saw nothing.
    """

    run: dict[str, object] = {}
    if run_document is not None:
        try:
            document = json.loads(run_document.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise Unreadable(
                f"{run_document} is not readable run document JSON: {error}"
            ) from error
        if not isinstance(document, dict):
            raise Unreadable(f"{run_document} is not a run document object")
        run = cast(dict[str, object], document)

    kin_value, identifier_value = run.get("kin_id"), run.get("run_id")
    named_run = identifier_value if isinstance(identifier_value, str) else ""
    if not named_run:
        named_run = run_id if run_id is not None else ""
    kin = kin_value if isinstance(kin_value, str) else ""
    if not kin:
        held = sorted(
            path.name
            for path in (data_root / KIN_DIRECTORY).glob("*")
            if (path / DATABASE_NAME).is_file()
        )
        kin = held[0] if len(held) == 1 else ""
    if not kin or not named_run:
        raise Unreadable("no run is named: neither a run document nor a run id")

    events: list[Mapping[str, object]] = []
    readable = False
    previous_id = ""
    previous_events: list[Mapping[str, object]] = []
    database = kin_directory(data_root, KinId(kin)) / DATABASE_NAME
    if database.is_file():
        try:
            events = [cast(Mapping[str, object], row) for row in ledger_rows(database, named_run)]
            # Read in the same breath as this run's own rows, from the same
            # ledger: the two are one reading of one file, and a case that asks
            # what came before this run is asking about that file, not about a
            # second source that could disagree with it.
            previous_id, before = previous_run_rows(database, named_run)
            previous_events = [cast(Mapping[str, object], row) for row in before]
        except sqlite3.Error as error:
            raise Unreadable(f"{database} cannot be read for this run: {error}") from error
        readable = True

    # A run with no world to join has no server at all, which is a fact about the
    # run rather than a reason it cannot be judged — so there is no server
    # directory to name, and nothing to read from one.
    overlay_value = run.get("overlay")
    overlay = (
        Path(overlay_value)
        if isinstance(overlay_value, str) and overlay_value
        else _overlay_for(data_root, kin, events)
    )

    # The Bridge's own account of what it did lives in the client's output, and
    # for a run whose Core was killed that is the only place the release appears:
    # there is nobody left on Core's side to have recorded it.
    client_log = ""
    if overlay is not None:
        for name in ("stdout.log", "latest.log"):
            candidate = overlay / "logs" / name
            if candidate.is_file():
                client_log += candidate.read_text(encoding="utf-8", errors="replace")

    server_log = ""
    log_path = None if server_directory is None else server_directory / "server.log"
    if log_path is not None and log_path.is_file():
        try:
            server_log = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise Unreadable(f"{log_path} cannot be read: {error}") from error

    cache_path = None if server_directory is None else server_directory / "usercache.json"
    identities: dict[str, str] = {}
    if cache_path is not None and cache_path.is_file():
        try:
            entries = json.loads(cache_path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise Unreadable(f"{cache_path} is not readable JSON: {error}") from error
        if not isinstance(entries, list):
            raise Unreadable(f"{cache_path} is not a list of identities")
        for entry in cast(list[object], entries):
            if not isinstance(entry, Mapping):
                continue
            item = cast(Mapping[str, object], entry)
            name, identifier = item.get("name"), item.get("uuid")
            if isinstance(name, str) and isinstance(identifier, str):
                identities[name] = identifier

    return RunMaterial(
        kin_id=kin,
        run_id=named_run,
        overlay=overlay,
        run_document=run,
        client_log=client_log,
        ledger_events=tuple(events),
        ledger_readable=readable,
        previous_run_id=previous_id,
        previous_run_events=tuple(previous_events),
        server_log=server_log,
        server_identities=identities,
        username=username,
        fault_injection=fault_injection,
        soak_samples=soak_samples,
        soak_summary=soak_summary,
    )


def _integer(run: Mapping[str, object], key: str) -> int | None:
    value = run.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text(run: Mapping[str, object], key: str) -> str | None:
    value = run.get(key)
    return value if isinstance(value, str) else None


def server_observed_join_identity(material: RunMaterial) -> str | None:
    """The server logged this name joining, under the UUID the name derives to.

    Vanilla derives an offline player's UUID from the name alone, so the
    comparison needs no configured copy of it: the rule is the check. A server
    that recorded a different UUID recorded a different player.
    """

    if material.join_line() is None:
        return "JOIN_NOT_LOGGED"
    recorded = material.server_identities.get(material.username)
    if recorded is None:
        return "IDENTITY_NOT_RECORDED"
    expected = str(offline_player_uuid(material.username))
    if recorded != expected:
        return f"IDENTITY_UUID_MISMATCH:{recorded}"
    return None


#: The client's own line when it publishes a world. The number is the port it was
#: asked for — measured: 1.21.4 stores the request and reports it back — which is why
#: the run's record of the port is checked against this line rather than trusted.
_SERVING = re.compile(r"Started serving on (\d+)")


def _lan_publication(run: Mapping[str, object]) -> Mapping[str, object] | None:
    value = run.get("lan_publication")
    return cast("Mapping[str, object]", value) if isinstance(value, Mapping) else None


def the_run_says_which_world_it_hosted(material: RunMaterial) -> str | None:
    """Core's record names the world the Kin was placed in, by its bytes.

    The other half of HOST-030's "the local world and the LAN result are two facts":
    the address it is reachable at is one of them, and which world it is, is the other.
    A run that published something without this block is a run where nobody can say
    what was published.
    """

    raw = material.run().get("world_snapshot")
    if not isinstance(raw, Mapping):
        return "NO_WORLD_SNAPSHOT_RECORDED"
    snapshot = cast("Mapping[str, object]", raw)
    name = snapshot.get("level_name")
    if not isinstance(name, str) or not name.strip():
        return "WORLD_SNAPSHOT_HAS_NO_LEVEL_NAME"
    digest = snapshot.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        return f"WORLD_SNAPSHOT_IS_NOT_A_DIGEST:{digest!r}"
    return None


#: The lines the *integrated server* writes when a player arrives or leaves. A hosting
#: client's log carries them, because the server runs inside that client: which is why
#: a hosted world's account can be read from the material the run already keeps, with no
#: second copy of anybody's words.
_OTHER_JOINED = re.compile(r"\[Server thread/INFO\]: (\w+) joined the game")
_OTHER_LEFT = re.compile(r"\[Server thread/INFO\]: (\w+) left the game")


def _other_names(material: RunMaterial, pattern: re.Pattern[str]) -> tuple[str, ...]:
    """Every name a line names, except this run's own Kin."""

    return tuple(name for name in pattern.findall(material.client_log) if name != material.username)


#: The line the Bridge writes when it asks vanilla to dial an address, which carries
#: the host and port the profile named. It is the only place a joining client's own log
#: says what it connected to.
_DIALLED = re.compile(r"bridge asked vanilla to connect to (\S+):(\d+) for generation (\d+)")


def the_first_snapshot_of_the_world_it_dialled_was_admitted(
    material: RunMaterial,
) -> str | None:
    """Core admitted a first authoritative snapshot of the address this client dialled.

    Both halves come from the joining client's own material: the address from the line
    the Bridge wrote when it asked vanilla to connect, and the admission from the run
    document. Only a loopback literal is accepted, because that is the only kind of
    address the frozen profile schema admits — a run that dialled anything else is not
    this case, whatever it then admitted.

    What the *world* saw is a different claim and a different run's: `HOST-040` is where
    the world answers for itself, because only the world can.
    """

    found = _DIALLED.search(material.client_log)
    if found is None:
        return "NO_CONNECTION_WAS_DIALLED"
    host, port, _generation = found.groups()
    if host not in {"127.0.0.1", "::1"}:
        return f"DIALLED_SOMETHING_BUT_A_LOOPBACK_LITERAL:{host}"
    if int(port) < 1:
        return f"DIALLED_A_PORT_THAT_IS_NOT_ONE:{port}"
    run = material.run()
    admitted = _integer(run, "snapshots_admitted")
    if admitted is None:
        return "SNAPSHOT_COUNT_MISSING"
    if admitted < 1:
        return f"NO_SNAPSHOT_WAS_ADMITTED:{admitted}"
    state = _text(run, "connection_state")
    if state != "PLAYABLE":
        return f"NEVER_BECAME_PLAYABLE:{state}"
    return None


def another_kin_joined_the_world_this_run_hosted(material: RunMaterial) -> str | None:
    """Somebody other than this Kin arrived in the world this run was hosting.

    The world's account, and only the world can give it: a client cannot say whether
    another player arrived. It also requires that this run published a world at all —
    composed from the assertion that checks it rather than restated, so the two cannot
    drift apart.
    """

    if core_was_told_the_world_was_published(material) is not None:
        return "THIS_RUN_DID_NOT_PUBLISH_A_WORLD"
    if not _other_names(material, _OTHER_JOINED):
        return "NO_OTHER_KIN_EVER_JOINED"
    return None


def the_world_saw_that_kin_leave_again(material: RunMaterial) -> str | None:
    """Everyone who arrived in this world also left it.

    A visitor still connected when the run ends is a different fact from one that came
    and went, and only the world knows which happened.
    """

    arrived = set(_other_names(material, _OTHER_JOINED))
    departed = set(_other_names(material, _OTHER_LEFT))
    still_there = sorted(arrived - departed)
    if still_there:
        return f"STILL_IN_THE_WORLD:{','.join(still_there)}"
    return None


def core_was_told_the_world_was_published(material: RunMaterial) -> str | None:
    """Core's own record says the Kin's world is published, and on which port.

    The run document rather than the ledger, and deliberately: publishing is not one of
    §5's session events, so it has nowhere else to be. It sits beside `world_snapshot`
    rather than inside it — the world that was hosted and the address it is reachable at
    are two facts, which is what the contract asks HOST-030 to keep apart.
    """

    publication = _lan_publication(material.run())
    if publication is None:
        return "NO_LAN_PUBLICATION_RECORDED"
    phase = publication.get("phase")
    if phase != "LAN_OPENED":
        return f"LAN_NOT_OPENED:{phase}"
    port = publication.get("port")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        return f"LAN_PORT_IS_NOT_A_PORT:{port}"
    return None


def the_client_published_the_world_on_the_port_it_was_given(material: RunMaterial) -> str | None:
    """What the client wrote and what Core recorded name the same port.

    Two accounts of one fact that do not know about each other: the line the client
    logged when it bound, and the port the Bridge reported back over the wire. This is
    the assertion that would have caught the bug this feature was built through — the
    first version asked the client for a system-chosen port, so its log said `0` while
    Core recorded where the world really was, and only a run showed the difference.
    """

    publication = _lan_publication(material.run())
    if publication is None:
        return "NO_LAN_PUBLICATION_RECORDED"
    recorded = publication.get("port")
    found = _SERVING.search(material.client_log)
    if found is None:
        return "CLIENT_NEVER_SAID_IT_WAS_SERVING"
    served = int(found.group(1))
    if served != recorded:
        return f"PORT_MISMATCH:client={served},core={recorded}"
    return None


def first_snapshot_admitted(material: RunMaterial) -> str | None:
    """Core admitted a first authoritative snapshot of a world the Kin joined.

    Both halves are required. A snapshot without a join is a snapshot of
    something, and a join without a snapshot is a client that arrived and could
    not see — the difference between the two is the whole of what L2 asks.
    """

    run = material.run()
    if material.join_line() is None:
        return "JOIN_NOT_LOGGED"
    admitted = _integer(run, "snapshots_admitted")
    if admitted is None:
        return "SNAPSHOT_COUNT_MISSING"
    if admitted < 1:
        # A first snapshot that was refused is not a snapshot: the reasons are in
        # the document and they are why this names a count rather than a flag.
        return "NO_SNAPSHOT_ADMITTED"
    state = _text(run, "connection_state")
    if state != "PLAYABLE":
        return f"CONNECTION_NOT_PLAYABLE:{state}"
    return None


def handshake_accepted_by_core(material: RunMaterial) -> str | None:
    """Core accepted this client's hello, in Core's own record.

    Measured: on a session that never joins a world the Bridge writes nothing at
    all to the client's log, so the client cannot be asked whether the handshake
    happened. Core can — `BridgeHelloAccepted` is written after it verified the
    proof, which makes this the one side of the handshake that does not rest on
    the other side's word for it.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    return None if material.has(HELLO_ACCEPTED) else "HANDSHAKE_NOT_RECORDED"


def stayed_observe_only(material: RunMaterial) -> str | None:
    """The Kin observed, and was never driven.

    Observation only is a claim about what did *not* happen — no join, no
    admitted snapshot, no input lease — and each of those is checked in both
    records where both exist, because a session that was handed the input is
    exactly what the claim denies.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    if not material.has(HELLO_ACCEPTED):
        # With no handshake nothing was observing, so "it only observed" would be
        # true for the wrong reason.
        return "NO_HANDSHAKE_TO_OBSERVE_FROM"
    for event_type, reason in (
        (JOIN_OBSERVED, "JOINED_A_WORLD"),
        (PLAYABLE_ESTABLISHED, "SNAPSHOT_ADMITTED"),
        (INPUT_LEASE_GRANTED, "INPUT_LEASED"),
    ):
        if material.has(event_type):
            return reason
    run = material.run()
    if _integer(run, "snapshots_admitted"):
        return "SNAPSHOT_ADMITTED"
    state = _text(run, "connection_state")
    if state is not None:
        return f"CONNECTION_STATE:{state}"
    return None


def leave_after_join_observed(material: RunMaterial) -> str | None:
    """The Kin left the world, after having joined it.

    Ordered rather than merely present: a leave recorded before the join is a
    different event — a stale line, or a log that is not this run's — and
    counting it would let a run that never ended pass by accident.

    The server's line is the whole of it, and the first version that also
    demanded Core report `CLIENT_EXITED` was asserting the harness rather than
    the Kin: measured, the harness ends a session by terminating the client, so
    the IPC channel closes before Core can see the client's own exit and Core
    records `BRIDGE_LOST`. That is Core's verdict on how the run was ended, not
    on whether the Kin left the game, and the contract asks for the departure the
    *server* observed.
    """

    joined = material.join_line()
    left = material.leave_line()
    if joined is None:
        return "JOIN_NOT_LOGGED"
    if left is None:
        return "LEAVE_NOT_LOGGED"
    if left < joined:
        return "LEAVE_BEFORE_JOIN"
    return None


def payload(event: Mapping[str, object]) -> Mapping[str, object]:
    """One ledger row's payload, as the event recorded it."""

    raw = event.get("payload_json")
    if not isinstance(raw, str):
        return {}
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return cast(Mapping[str, object], document) if isinstance(document, Mapping) else {}


def move_input_was_leased(material: RunMaterial) -> str | None:
    """Core granted a lease for the move capability in this run.

    The capability is checked rather than assumed: a lease is an authorisation
    for *one* thing, and a run that was leased something else did not get to move
    because it was allowed to.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    grants = material.recorded(INPUT_LEASE_GRANTED)
    if not grants:
        return "NO_LEASE_GRANTED"
    capabilities = {str(payload(event).get("capability")) for event in grants}
    if MOVE_CAPABILITY not in capabilities:
        return f"LEASE_IS_NOT_FOR_A_MOVE:{','.join(sorted(capabilities))}"
    return None


def the_bridge_carried_the_input_out(material: RunMaterial) -> str | None:
    """Core's own record of what the Bridge did with the command."""

    run = material.run()
    applied = _integer(run, "actions_applied")
    refused = _integer(run, "actions_refused")
    if applied is None or refused is None:
        return "ACTION_COUNTS_MISSING"
    if refused:
        return f"ACTIONS_REFUSED:{refused}"
    if applied < 1:
        return "NOTHING_WAS_APPLIED"
    return None


def _horizontal(before: tuple[float, ...], after: tuple[float, ...]) -> float:
    """How far apart two of the server's position readings are, ignoring height.

    Height is deliberately not part of it: a Kin standing at spawn can be reported
    twice with different Y, so counting any two readings that differ would accept
    a fall at spawn as a walk.
    """

    return ((after[0] - before[0]) ** 2 + (after[2] - before[2]) ** 2) ** 0.5


def the_server_saw_the_kin_move(material: RunMaterial) -> str | None:
    """The Kin's displacement, measured by the server rather than by the Kin.

    What the client believes it did is not evidence that it moved: the server's
    own readings are, and this is the point of the whole chain — an input that
    was legal and carried out is still not a movement until the world says so.
    """

    positions = probe_readings(material.server_log, 3)
    if len(positions) < 2:
        return "NO_SERVER_READINGS"
    horizontal = _horizontal(positions[0], positions[-1])
    if horizontal < MINIMUM_STEP_BLOCKS:
        return f"MOVED_LESS_THAN_A_STEP:{horizontal:.2f}"
    return None


def the_lease_expired_and_was_released(material: RunMaterial) -> str | None:
    """The input was taken back when the hold's own deadline passed.

    A release for any other reason — a channel that went away, a session ending —
    is a different fact about a different cause, so the reason is checked rather
    than the event's presence.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    releases = material.recorded(INPUT_RELEASED)
    if not releases:
        return "NO_RELEASE_RECORDED"
    reasons = {str(payload(event).get("reason")) for event in releases}
    if TIMEOUT not in reasons:
        return f"RELEASED_FOR_ANOTHER_REASON:{','.join(sorted(reasons))}"
    return None


def the_bridge_released_the_input_when_the_ipc_was_lost(material: RunMaterial) -> str | None:
    """The client's own line, because Core was not there to write one.

    Measured in a real run whose Core was killed: `bridge released 1 input(s)
    after IPC_LOST`. The *reason* is what this checks: a release after
    `CORE_REQUEST` is the lease expiring while Core is alive, and one after
    `LEFT_PLAYABLE` is the session ending. Only a lost runtime is a lost runtime.

    The count matters too — "released nothing after IPC_LOST" is the Bridge
    saying it was holding nothing, which would make the letting go vacuous.
    """

    if not material.client_log:
        return "NO_CLIENT_LOG"
    releases = _BRIDGE_RELEASE.findall(material.client_log)
    if not releases:
        return "RELEASE_NOT_LOGGED"
    reasons = {reason for _, reason in releases}
    if IPC_LOST not in reasons:
        return f"RELEASED_FOR_ANOTHER_REASON:{','.join(sorted(reasons))}"
    if not any(int(count) > 0 for count, reason in releases if reason == IPC_LOST):
        return "HELD_NOTHING_WHEN_THE_RUNTIME_WENT_AWAY"
    return None


def the_server_saw_the_kin_stop_after_the_move(material: RunMaterial) -> str | None:
    """The world's answer: it moved, and then it was not moving.

    Both halves are required. A Kin that never moved did not stop, and a Kin
    still moving with nothing left to be holding it is the failure this case
    exists to rule out — the keys that were never released.

    Two readings that agree is the ordinary shape, and a measured run showed the
    other one: the kill lands mid-stride, the client leaves, and the last two
    readings differ because there was never a reading after the stop. A client
    that has left the game is not holding keys either, so a leave counts — the
    same rule the harness waits on, for the same reason.
    """

    positions = probe_readings(material.server_log, 3)
    if len(positions) < 2:
        return "NO_SERVER_READINGS"
    moved = _horizontal(positions[0], positions[-1])
    if moved < MINIMUM_STEP_BLOCKS:
        return f"NEVER_MOVED:{moved:.2f}"
    if positions[-2] != positions[-1] and material.leave_line() is None:
        return "STILL_MOVING_AFTER_THE_RUNTIME_WENT_AWAY"
    return None


def _object(value: object) -> Mapping[str, object] | None:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else None


def _positive(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _coordinate(value: object) -> int | None:
    """A session generation, whichever side of the ledger it was read from.

    The row's own `generation` column is TEXT — a uint64 does not fit SQLite's
    signed INTEGER, so the writer stores decimal text — while the payload carries
    the same fact as a JSON number. Comparing them as they arrive would never
    match once, so every real run would look unattributed while the unit tests,
    which hand-build rows with an int, stayed green. The two spellings are one
    fact, and this is the one place that knows it.
    """

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return _positive(value)
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return _positive(int(value))
    return None


def _session_from(events: Sequence[Mapping[str, object]]) -> tuple[str, int] | None:
    """The session and generation the first row that carries one recorded.

    The row carries the coordinate twice — its own columns and the payload — and
    both copies have to agree, because a row whose two copies disagree does not
    say which session it belongs to.

    Takes rows rather than material because the same question is asked of two row
    sets: this run's, and the run this one followed.
    """

    for recorded in events:
        if recorded.get("event_type") != PROCESS_STARTED:
            continue
        recorded_payload = payload(recorded)
        session = recorded_payload.get("session_id")
        generation = _coordinate(recorded_payload.get("generation"))
        if (
            isinstance(session, str)
            and session
            and generation is not None
            and recorded.get("session_id") == session
            and _coordinate(recorded.get("generation")) == generation
        ):
            return session, generation
    return None


def _ledger_session(material: RunMaterial) -> tuple[str, int] | None:
    """The session and generation this run's ledger recorded, if it did."""

    return _session_from(material.ledger_events)


def _belongs_to_session(event: Mapping[str, object], session: tuple[str, int]) -> bool:
    """Whether a ledger row is attributed to the exact session coordinate."""

    return (event.get("session_id"), _coordinate(event.get("generation"))) == session


def _confirmed_sigkill(
    material: RunMaterial, *, expected_role: str, require_session: bool
) -> str | None:
    """Cross-check one SIGKILL record against the run that presents it.

    Runtime and server runs use the same signed vocabulary and attribution.  The
    role is the only distinction; keeping the checks here makes it impossible for
    one role to quietly accept a weaker meaning of SIGKILL than the other.

    A server-kill run requires the ledger session coordinate: unlike the legacy
    runtime case, it was designed after structured fault attribution existed and
    has no reason to accept an unbound session/generation pair.
    """

    record = material.fault_injection
    if record is None:
        return "NO_FAULT_INJECTION_RECORD"

    case = _object(record.get("case"))
    if case is None:
        return "NO_CASE_ATTRIBUTION"
    if case.get("case_id") != material.expected_case_id:
        return f"FAULT_RECORD_IS_ANOTHER_CASE:{case.get('case_id')}"
    if case.get("case_version") != material.expected_case_version:
        return f"FAULT_RECORD_IS_ANOTHER_CASE_VERSION:{case.get('case_version')}"

    target = _object(record.get("target"))
    if target is None:
        return "NO_TARGET"
    role = target.get("role")
    if role != expected_role:
        return f"WRONG_TARGET_ROLE:{role}"

    signal = _object(record.get("signal"))
    name = None if signal is None else signal.get("name")
    if name != SIGKILL:
        return f"NOT_A_SIGKILL:{name}"
    if signal is None or signal.get("number") != 9:
        return f"WRONG_SIGKILL_NUMBER:{None if signal is None else signal.get('number')}"
    if signal.get("result") != DELIVERED:
        return f"SIGKILL_WAS_NOT_DELIVERED:{signal.get('result')}"

    outcome = record.get("outcome")
    if outcome != INJECTED:
        return f"NOT_INJECTED:{outcome}"

    strength = record.get("confirmation_strength")
    if strength != IDENTITY_DISAPPEARED:
        return f"CONFIRMATION_NOT_IDENTITY_DISAPPEARED:{strength}"

    confirmation = _object(record.get("confirmation"))
    method = None if confirmation is None else confirmation.get("method")
    observations = None if confirmation is None else confirmation.get("observations")
    if method in (None, NO_METHOD) or _positive(observations) is None:
        return "NOTHING_CONFIRMED_THE_TARGET_DIED"
    if confirmation is not None and confirmation.get("wait_status_available") is not False:
        # The helper is not the parent, so a wait status is not something it can
        # have observed. Accepting one would be accepting the false claim this
        # whole record exists to prevent.
        return "CLAIMED_A_WAIT_STATUS_IT_CANNOT_HAVE"

    attribution = _object(record.get("attribution"))
    if attribution is None:
        return "NO_ATTRIBUTION"
    if attribution.get("run_id") != material.run_id:
        return f"FAULT_RECORD_IS_ANOTHER_RUN:{attribution.get('run_id')}"
    if attribution.get("kin_id") != material.kin_id:
        return f"FAULT_RECORD_IS_ANOTHER_KIN:{attribution.get('kin_id')}"
    if not material.ledger_readable:
        # The ledger is what the run id, the kin and the session were cross-checked
        # against; without it the attribution is only the record's own word.
        return "LEDGER_UNREADABLE"
    recorded_session = _ledger_session(material)
    if require_session and recorded_session is None:
        return "NO_SESSION_ATTRIBUTION_IN_LEDGER"
    if (
        recorded_session is not None
        and (
            attribution.get("session_id"),
            attribution.get("generation"),
        )
        != recorded_session
    ):
        return (
            "FAULT_RECORD_IS_ANOTHER_SESSION:"
            f"{attribution.get('session_id')}/{attribution.get('generation')}"
        )
    return None


def runtime_controller_sigkill_was_confirmed(material: RunMaterial) -> str | None:
    """The harness confirmed that this run's runtime-controller identity died.

    This is about the harness rather than the Kin or world, and exists because an
    older harness used to report a kill that never occurred.  The helper is not
    the target's parent, so a claimed wait status is rejected.
    """

    return _confirmed_sigkill(material, expected_role=RUNTIME_CONTROLLER, require_session=False)


def server_jvm_sigkill_was_confirmed(material: RunMaterial) -> str | None:
    """The helper delivered SIGKILL to this run's exact server JVM identity."""

    return _confirmed_sigkill(material, expected_role=SERVER_JVM, require_session=True)


def client_jvm_sigkill_was_confirmed(material: RunMaterial) -> str | None:
    """The helper delivered SIGKILL to this run's exact client JVM identity.

    The client is the boundary where the Bridge dies with the target, so unlike
    the runtime and the server cases there is no release log in the killed
    process to read afterwards. This record is the part that says a *named*
    process died rather than that a channel went quiet.
    """

    return _confirmed_sigkill(material, expected_role=CLIENT_JVM, require_session=True)


def the_server_log_has_no_graceful_shutdown(material: RunMaterial) -> str | None:
    """The server's own log ended without either vanilla shutdown marker."""

    if not material.server_log:
        return "NO_SERVER_LOG"
    for marker in ("Stopping the server", "All dimensions are saved"):
        if marker in material.server_log:
            return f"GRACEFUL_SHUTDOWN_LOGGED:{marker}"
    return None


def _killed_session_witnesses(
    material: RunMaterial,
) -> tuple[tuple[str, int], tuple[int, ...], tuple[int, ...], tuple[tuple[int, str], ...]] | str:
    """What the ledger says about a session that was killed while holding input.

    One implementation because two cases read the same facts out of the same
    ledger: which session this run was, that it was in a world, that it held a
    move lease, and where it recorded the ending. The binding is what must not
    drift — every witness has to belong to the *same* session coordinate, or one
    generation's kill could borrow another generation's world loss. What each
    case then requires of those witnesses is its own: the server boundary wants
    the world-loss phase, the client boundary wants an ending of any kind.

    Returns the coordinate and the four index lists, or the reason it cannot.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    session = _ledger_session(material)
    if session is None:
        return "NO_SESSION_ATTRIBUTION_IN_LEDGER"
    playable = tuple(
        index
        for index, item in enumerate(material.ledger_events)
        if item.get("event_type") == PLAYABLE_ESTABLISHED and _belongs_to_session(item, session)
    )
    if not playable:
        return "NO_PLAYABLE_WORLD_RECORDED"
    leases = tuple(
        index
        for index, item in enumerate(material.ledger_events)
        if item.get("event_type") == INPUT_LEASE_GRANTED
        and _belongs_to_session(item, session)
        and payload(item).get("capability") == MOVE_CAPABILITY
    )
    if not leases:
        return "NO_MOVE_LEASE_FOR_KILLED_SESSION"
    interrupted = tuple(
        (index, str(payload(item).get("phase")))
        for index, item in enumerate(material.ledger_events)
        if item.get("event_type") == SESSION_INTERRUPTED and _belongs_to_session(item, session)
    )
    if not interrupted:
        return "NO_WORLD_LOSS_RECORDED"
    return session, playable, leases, interrupted


def the_ledger_recorded_world_loss(material: RunMaterial) -> str | None:
    """The killed session held move input in a playable world, then lost it.

    The world loss is a `DISCONNECTED` phase: the server ended the session. A
    lease granted after the disconnect would make it look as though input was
    held when the server died, so the three are ordered and not merely present.
    """

    witnesses = _killed_session_witnesses(material)
    if isinstance(witnesses, str):
        return witnesses
    _, playable, leases, interrupted = witnesses
    disconnected = [index for index, phase in interrupted if phase == "DISCONNECTED"]
    if not disconnected:
        phases = ",".join(sorted({phase for _, phase in interrupted}))
        return f"INTERRUPTED_WITHOUT_WORLD_LOSS:{phases}"
    if not any(
        established < leased < lost
        for established in playable
        for leased in leases
        for lost in disconnected
    ):
        return "WORLD_LOSS_SEQUENCE_INVALID"
    return None


def the_ledger_recorded_the_session_ending(material: RunMaterial) -> str | None:
    """The runtime noticed its client was gone, in its own record.

    This is the half a killed *client* needs and a killed *server* does not: the
    process holding the input is gone, so Core is the only one left that can say
    the session ended. Which event it writes is not prescribed — measured, the
    transport-lost path wins the race against the process watcher and Core
    records an interruption with the outcome `BRIDGE_LOST` — so this asks for an
    ending bound to this session, after the lease that was already granted.
    """

    witnesses = _killed_session_witnesses(material)
    if isinstance(witnesses, str):
        return witnesses
    _, _, leases, interrupted = witnesses
    if not any(leased < index for leased in leases for index, _ in interrupted):
        return "SESSION_ENDING_BEFORE_THE_LEASE"
    return None


def the_bridge_released_input_when_play_ended(material: RunMaterial) -> str | None:
    """The client released a nonzero hold because it left playable state."""

    if not material.client_log:
        return "NO_CLIENT_LOG"
    releases = _BRIDGE_RELEASE.findall(material.client_log)
    if not releases:
        return "RELEASE_NOT_LOGGED"
    if not any(reason == "LEFT_PLAYABLE" for _, reason in releases):
        return "NO_LEFT_PLAYABLE_RELEASE"
    play_ended = _PLAY_ENDED_RELEASE.findall(material.client_log)
    if not play_ended:
        return "NO_PLAY_ENDED_RELEASE"
    if not any(int(count) > 0 for count in play_ended):
        return "HELD_NOTHING_WHEN_PLAY_ENDED"
    return None


def the_previous_run_left_the_kin_holding_input(material: RunMaterial) -> str | None:
    """The run before this one granted a move lease and never released it.

    A restart is evidence about a recovery only if there was something to recover
    from, and this is what a crash leaves in the record: a runtime that died with
    input still held. It is read from the same ledger as everything else — a Kin
    has one ledger across all its runs — rather than from the harness saying it
    crashed something, so a restart that merely followed an ordinary exit cannot
    pass by looking quiet.

    The absent release is the substance and not an oversight: `InputReleased` is
    Core's own event, and a Core that had written one would have been alive to
    write the rest of the run too.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    if not material.previous_run_id:
        return "NO_PREVIOUS_RUN"
    leases = [
        index
        for index, item in enumerate(material.previous_run_events)
        if item.get("event_type") == INPUT_LEASE_GRANTED
        and payload(item).get("capability") == MOVE_CAPABILITY
    ]
    if not leases:
        return "PREVIOUS_RUN_GRANTED_NO_MOVE_LEASE"
    releases = [
        index
        for index, item in enumerate(material.previous_run_events)
        if item.get("event_type") == INPUT_RELEASED
    ]
    if any(released > leased for leased in leases for released in releases):
        return "PREVIOUS_RUN_RELEASED_ITS_INPUT"
    return None


def the_restart_runs_as_a_new_session(material: RunMaterial) -> str | None:
    """This run is a new session rather than the dead one resumed.

    §7's transient state — the session, its generation, and the lease that hangs
    off them — does not survive a run, and the record says so: this run names a
    different session than the run before it. A restart that reused the dead
    session's coordinate would be claiming to continue something that ended.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    if not material.previous_run_id:
        return "NO_PREVIOUS_RUN"
    session = _ledger_session(material)
    if session is None:
        return "NO_SESSION_ATTRIBUTION_IN_LEDGER"
    before = _session_from(material.previous_run_events)
    if before is None:
        return "PREVIOUS_RUN_HAS_NO_SESSION_ATTRIBUTION"
    if before == session:
        return f"SAME_SESSION_AS_THE_DEAD_RUN:{session[0]}"
    return None


def the_restart_reconciled_before_it_started(material: RunMaterial) -> str | None:
    """The runtime read its outbox and settled it before anything else happened.

    §13 puts reconciliation before the first side effect, and §8's outbox is why:
    an effect that was recorded and never settled is one nobody can reconcile
    afterwards. Measured on a crash that lands after the world is up, the report
    is `{"invalidated": [], "waiting": [], "status": "reconciled"}` — the hold the
    dead run left was never an *unsettled* effect, so there was nothing for the
    restart to undo.

    `invalidated` is deliberately not required to be empty: entries there would be
    the restart closing out effects it must never replay, which is the report
    working, not failing. What is required is that nothing is still waiting to be
    looked at in the world, because a restart that begins on top of that answered
    a question about the world by not asking it.
    """

    recovery = _object(material.run_document.get("recovery"))
    if recovery is None:
        return "NO_RECOVERY_REPORT"
    status = recovery.get("status")
    if status != RECONCILED:
        return f"NOT_RECONCILED:{status}"
    waiting = recovery.get("waiting")
    if not isinstance(waiting, list):
        return "RECOVERY_WAITING_IS_NOT_A_LIST"
    held = cast(list[object], waiting)
    if held:
        return f"EFFECTS_STILL_WAITING:{len(held)}"
    return None


def _soak_samples(material: RunMaterial) -> tuple[tuple[str, int, int, int], ...] | None:
    """The samples a bounded soak wrote, as (label, rss_kb, threads, elapsed_s).

    A line that does not parse is not a sample, and a soak whose file holds lines
    that do not parse is one whose measurement cannot be read at all — the caller
    distinguishes "no soak happened" from "the soak's numbers are not readable",
    because only the first is a legitimate reason for a case not to see any.
    """

    if not material.soak_samples.strip():
        return None
    samples: list[tuple[str, int, int, int]] = []
    for line in material.soak_samples.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 4 or fields[0] not in ("client", "server"):
            return None
        try:
            samples.append((fields[0], int(fields[1]), int(fields[2]), int(fields[3])))
        except ValueError:
            return None
    return tuple(samples)


def the_soak_held_for_the_duration_it_was_asked_for(material: RunMaterial) -> str | None:
    """The run was asked for a bounded soak, and the measurement covers it.

    Both halves are read, and neither stands in for the other: the record says
    what the harness was asked to do and whether it finished, and the samples say
    how far into the soak they actually reach. A soak that stopped early leaves
    samples that stop early — which is the thing a baseline cannot hide, since
    "we ran for ten minutes" is exactly the claim that would otherwise be the
    harness's own word.

    The tolerance is one interval: the last look lands before the deadline is
    reached, so requiring the final second exactly would fail every honest run.
    """

    summary = _object(material.soak_summary)
    if summary is None:
        return "NO_SOAK_SUMMARY"
    requested = _positive(summary.get("requested_seconds"))
    interval = _positive(summary.get("interval_seconds"))
    if requested is None or interval is None:
        return "SOAK_SUMMARY_INCOMPLETE"
    if summary.get("ended_early") is True:
        return "SOAK_ENDED_EARLY"
    samples = _soak_samples(material)
    if samples is None:
        return "NO_SOAK_SAMPLES"
    reached = max(elapsed for _, _, _, elapsed in samples)
    if reached + interval < requested:
        return f"SOAK_SHORTER_THAN_REQUESTED:{reached}/{requested}"
    return None


def both_jvms_were_sampled_throughout_the_soak(material: RunMaterial) -> str | None:
    """Both processes were looked at, on the whole length of the soak.

    Counted per label rather than in total: a client sampled once at the start
    and a server sampled fifty times is fifty-one samples and not a baseline of
    two processes. The count is also what makes a missing process visible — a JVM
    that died halfway leaves its label short, which is the failure a soak exists
    to catch.

    Two samples is the floor because one reading is a number and not a span.
    """

    summary = _object(material.soak_summary)
    if summary is None:
        return "NO_SOAK_SUMMARY"
    samples = _soak_samples(material)
    if samples is None:
        return "NO_SOAK_SAMPLES"
    counts = {
        label: sum(1 for sample in samples if sample[0] == label) for label in ("client", "server")
    }
    if not counts["client"]:
        return "CLIENT_WAS_NEVER_SAMPLED"
    if not counts["server"]:
        return "SERVER_WAS_NEVER_SAMPLED"
    minimum = min(counts["client"], counts["server"])
    if minimum < 2:
        return f"TOO_FEW_SAMPLES:{counts['client']}/{counts['server']}"
    # Both processes have to reach the end of the soak, not merely to appear in
    # it: one that stopped being sampled halfway is one that stopped being there.
    interval = _positive(summary.get("interval_seconds"))
    reached = max(elapsed for _, _, _, elapsed in samples)
    for label in ("client", "server"):
        last = max(elapsed for name, _, _, elapsed in samples if name == label)
        if interval is not None and last + 2 * interval < reached:
            return f"{label.upper()}_STOPPED_BEING_SAMPLED:{last}/{reached}"
    return None


def the_attempt_was_abandoned_at_its_deadline(material: RunMaterial) -> str | None:
    """Core gave up on the attempt, in Core's own words, for its own reason.

    The run document carries it because §5 names no ledger event for "the attempt
    was given up on" — and writing `SessionInterrupted` would say the session was
    interrupted, which is false: it is still here.
    """

    run = material.run()
    cancelled = _text(run, "connection_cancelled")
    if cancelled is None:
        return "NO_CONNECTION_RECORD"
    if not cancelled:
        return "NO_ATTEMPT_WAS_ABANDONED"
    if cancelled != TIMEOUT:
        return f"ABANDONED_FOR_ANOTHER_REASON:{cancelled}"
    return None


def no_world_was_joined(material: RunMaterial) -> str | None:
    """Nothing was joined, and the record is asked rather than the client.

    A connection that was accepted is not a join: the contract says TCP, INIT and
    screen state may not be counted as one on their own. What would count is a
    join the Bridge reported, a snapshot Core admitted, and a connection state
    that means the session is *in* the world — so those are what are checked, in
    both records where both exist. An attempt that ended in `FAILED` or
    `DISCONNECTED` is an attempt that did not join, and demanding that the state
    be empty would call a refused login a join.
    """

    if material.has(JOIN_OBSERVED):
        return "THE_BRIDGE_REPORTED_A_JOIN"
    if material.has(PLAYABLE_ESTABLISHED):
        return "CORE_ADMITTED_A_SNAPSHOT"
    run = material.run()
    if _integer(run, "snapshots_admitted"):
        return "SNAPSHOT_ADMITTED"
    state = _text(run, "connection_state")
    if state in WORLD_CLAIMING_STATES:
        return f"CONNECTION_STATE:{state}"
    return None


def the_refusal_was_classified_in_the_ledger(material: RunMaterial) -> str | None:
    """The server said no, and Core recorded the phase and the category together.

    The category is the Bridge's classification of what the server said, not the
    server's sentence: the contract keeps arbitrary server text out of product
    events, so a category is the only thing that can travel. Measured, a refused
    login lands as `phase: FAILED` with `reason: …WHITELIST_REJECTED`.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    for event in material.recorded(SESSION_INTERRUPTED):
        seen = payload(event)
        if seen.get("phase") == "FAILED" and seen.get("reason") == WHITELIST_REJECTED:
            return None
    return "NO_CLASSIFIED_REFUSAL"


def the_bridge_classified_the_refusal(material: RunMaterial) -> str | None:
    """The client's own log, where the classification was made.

    The ledger says what Core recorded; this says the Bridge recognised it. Both
    are needed: a ledger entry with no classification behind it would be Core
    guessing, and a classification that never reached the ledger would be a fact
    nobody can act on later.
    """

    if not material.client_log:
        return "NO_CLIENT_LOG"
    if REFUSAL_LINE not in material.client_log:
        return "THE_BRIDGE_DID_NOT_CLASSIFY_IT"
    return None


def the_cancel_reached_the_client_and_was_acted_on(material: RunMaterial) -> str | None:
    """The other side of the cancel: the Bridge did what Core asked it to.

    Core recording that it gave up is half the story — the world it gave up on
    might still have a client dialling it forever. Measured, the Bridge's own line
    in the client's log is `bridge is cancelling the client's connection`, after
    an attempt that reached `LOGIN_NEGOTIATING` and stayed there.

    What is *not* claimed here is that the run continued afterwards. The harness
    ends a session by terminating the client, so every run this seals ends
    `BRIDGE_LOST` whatever happened before, and an assertion about the ending
    would be an assertion about the harness.
    """

    if not material.client_log:
        return "NO_CLIENT_LOG"
    if CANCEL_LINE not in material.client_log:
        return "THE_BRIDGE_NEVER_CANCELLED_IT"
    return None


def the_server_saw_the_kin_turn(material: RunMaterial) -> str | None:
    """Two headings, in the server's own readings.

    A turn is not a movement, so no *position* reading can show one: what shows
    it is the rotation the server reports. How many degrees were asked for is the
    harness's own comparison against the run's command line; what is readable
    from the material is that the Kin's heading changed and the world saw it.

    Standing still is deliberately *not* part of this. A run may walk and turn at
    once — the harness does — and demanding stillness here would make the case
    assert something about the run rather than about the turn.
    """

    headings = probe_readings(material.server_log, 2)
    if len(headings) < 2:
        return "NO_SERVER_READINGS"
    if len({reading[0] for reading in headings}) < 2:
        return "NO_TURN_OBSERVED"
    return None


def the_server_saw_the_block_change(material: RunMaterial) -> str | None:
    """The block in front of the Kin changed state, in the server's own answer.

    A key held at nothing changes nothing. The harness puts a block in front of the
    Kin — a note block, placed with note zero — asks the server whether it is still
    in that state in the same breath as putting it there, and then asks about the
    same block, by the coordinates the server itself named when it placed it, over
    and over afterwards. Both halves of the change are therefore the server's own
    words about one block, and neither is the client's idea of what it touched.

    Asked as a predicate rather than read as a value, so a block and a block that
    changed are told apart by what came back rather than by what was asked: a block
    the harness never managed to place answers neither question, and one that was
    placed and then left alone answers the first one every time.
    """

    readings = _BLOCK.findall(material.server_log)
    if not readings:
        return "THE_BLOCK_WAS_NEVER_ASKED_ABOUT"
    if BLOCK_CHANGED not in readings:
        return "THE_BLOCK_NEVER_CHANGED"
    if BLOCK_INITIAL not in readings:
        # The harness places it in that state, so its absence is not "the Kin was
        # quick": it means this run cannot say what the block was before.
        return "THE_BLOCK_WAS_NEVER_IN_ITS_PLACED_STATE"
    return None


def input_was_refused_before_the_world_was_playable(material: RunMaterial) -> str | None:
    """Core asked to drive the Kin too early, and the answer is on the record.

    The contract's L4 rule is that a lease is granted only after the join *and*
    the first snapshot. This is the half of it that shows the rule is *enforced*
    rather than merely never broken: the run asked at the join, and the arbiter
    said no. Both halves of the answer are read — the phase it was refused in and
    the arbiter's own reason — because a refusal with neither is a refusal nobody
    can act on, and because "refused, at some point, for some reason" would also
    be true of a run refused for something else entirely.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    refusals = material.recorded(INPUT_REFUSED)
    if not refusals:
        return "NO_REFUSAL_RECORDED"
    phases: set[str] = set()
    for event in refusals:
        recorded = payload(event)
        reasons = recorded.get("refusals")
        phases.add(str(recorded.get("phase")))
        if (
            recorded.get("phase") == JOIN_SEEN_PHASE
            and isinstance(reasons, list)
            and NOT_PLAYABLE in reasons
        ):
            return None
    return f"REFUSED_OTHERWISE:{','.join(sorted(phases))}"


def no_lease_was_granted(material: RunMaterial) -> str | None:
    """Nothing was authorised: no lease reached the client, so no key could be held.

    One side of "the Kin was never driven". A lease is the only thing that lets
    Core send an input, so a run with none to its name could not have driven
    anything — and this names the capability it would have carried, because a
    lease for something else would be a different run.
    """

    if not material.ledger_readable:
        return "LEDGER_UNREADABLE"
    granted = material.recorded(INPUT_LEASE_GRANTED)
    if not granted:
        return None
    capabilities = sorted({str(payload(event).get("capability")) for event in granted})
    return f"LEASE_GRANTED:{','.join(capabilities)}"


def the_bridge_never_pressed_a_key(material: RunMaterial) -> str | None:
    """The other side of the same fact, in the other side's own words.

    Core's refusal is Core's account of a decision. This is the client saying that
    nothing was ever held: every press and every hold the Bridge performs is
    logged, measured on real runs (`bridge pressed use.hand`, `bridge applied
    …: holding [move.forward]`), so the absence of those lines is a fact about the
    client rather than an inference from the absence of a lease.
    """

    if not material.client_log:
        return "NO_CLIENT_LOG"
    pressed = _BRIDGE_PRESS.search(material.client_log)
    if pressed is not None:
        return f"KEY_WAS_PRESSED:{pressed.group(0)}"
    return None


def the_server_saw_the_kin_arrive_and_never_move(material: RunMaterial) -> str | None:
    """The world's own account: the Kin reached it, and it never went anywhere.

    A claim about what did not happen needs a record that would have shown it
    happening. The server was asked where the Kin is on the same cadence as any
    other run, and every answer is the same place — measured against the same
    threshold that separates a step from a shove, so "it never moved" is the same
    rule as "it moved", read the other way.
    """

    if material.join_line() is None:
        return "JOIN_NOT_LOGGED"
    positions = probe_readings(material.server_log, 3)
    if len(positions) < 2:
        # One reading is a place, not a stillness: "it did not move" is a claim
        # about two moments, and the same standard the walk is held to.
        return "NO_SERVER_READINGS"
    for reading in positions[1:]:
        moved = _horizontal(positions[0], reading)
        if moved >= MINIMUM_STEP_BLOCKS:
            return f"THE_KIN_MOVED:{moved:.2f}"
    return None


#: Every assertion a case manifest may name, and what performs it. A name that is
#: not here cannot be judged, which the verdict reports rather than passing over.
ASSERTIONS: dict[str, Callable[[RunMaterial], str | None]] = {
    "server_observed_join_identity": server_observed_join_identity,
    "first_snapshot_admitted": first_snapshot_admitted,
    "the_run_says_which_world_it_hosted": the_run_says_which_world_it_hosted,
    "core_was_told_the_world_was_published": core_was_told_the_world_was_published,
    "the_first_snapshot_of_the_world_it_dialled_was_admitted": (
        the_first_snapshot_of_the_world_it_dialled_was_admitted
    ),
    "another_kin_joined_the_world_this_run_hosted": (another_kin_joined_the_world_this_run_hosted),
    "the_world_saw_that_kin_leave_again": the_world_saw_that_kin_leave_again,
    "the_client_published_the_world_on_the_port_it_was_given": (
        the_client_published_the_world_on_the_port_it_was_given
    ),
    "leave_after_join_observed": leave_after_join_observed,
    "handshake_accepted_by_core": handshake_accepted_by_core,
    "stayed_observe_only": stayed_observe_only,
    "move_input_was_leased": move_input_was_leased,
    "the_bridge_carried_the_input_out": the_bridge_carried_the_input_out,
    "the_server_saw_the_kin_move": the_server_saw_the_kin_move,
    "the_lease_expired_and_was_released": the_lease_expired_and_was_released,
    "the_bridge_released_the_input_when_the_ipc_was_lost": (
        the_bridge_released_the_input_when_the_ipc_was_lost
    ),
    "the_server_saw_the_kin_stop_after_the_move": the_server_saw_the_kin_stop_after_the_move,
    "runtime_controller_sigkill_was_confirmed": runtime_controller_sigkill_was_confirmed,
    "server_jvm_sigkill_was_confirmed": server_jvm_sigkill_was_confirmed,
    "client_jvm_sigkill_was_confirmed": client_jvm_sigkill_was_confirmed,
    "the_ledger_recorded_the_session_ending": the_ledger_recorded_the_session_ending,
    "the_previous_run_left_the_kin_holding_input": the_previous_run_left_the_kin_holding_input,
    "the_soak_held_for_the_duration_it_was_asked_for": (
        the_soak_held_for_the_duration_it_was_asked_for
    ),
    "both_jvms_were_sampled_throughout_the_soak": both_jvms_were_sampled_throughout_the_soak,
    "the_restart_runs_as_a_new_session": the_restart_runs_as_a_new_session,
    "the_restart_reconciled_before_it_started": the_restart_reconciled_before_it_started,
    "the_server_log_has_no_graceful_shutdown": the_server_log_has_no_graceful_shutdown,
    "the_ledger_recorded_world_loss": the_ledger_recorded_world_loss,
    "the_bridge_released_input_when_play_ended": the_bridge_released_input_when_play_ended,
    "the_attempt_was_abandoned_at_its_deadline": the_attempt_was_abandoned_at_its_deadline,
    "no_world_was_joined": no_world_was_joined,
    "the_cancel_reached_the_client_and_was_acted_on": (
        the_cancel_reached_the_client_and_was_acted_on
    ),
    "the_refusal_was_classified_in_the_ledger": the_refusal_was_classified_in_the_ledger,
    "the_bridge_classified_the_refusal": the_bridge_classified_the_refusal,
    "the_server_saw_the_kin_turn": the_server_saw_the_kin_turn,
    "the_server_saw_the_block_change": the_server_saw_the_block_change,
    "input_was_refused_before_the_world_was_playable": (
        input_was_refused_before_the_world_was_playable
    ),
    "no_lease_was_granted": no_lease_was_granted,
    "the_bridge_never_pressed_a_key": the_bridge_never_pressed_a_key,
    "the_server_saw_the_kin_arrive_and_never_move": (the_server_saw_the_kin_arrive_and_never_move),
}


@dataclass(frozen=True, slots=True)
class Verdict:
    """Which assertions were expected, which held, and why the rest did not."""

    expected: tuple[str, ...]
    observed: tuple[str, ...]
    failures: tuple[str, ...]
    unimplemented: tuple[str, ...]

    @property
    def result(self) -> str:
        # Nothing was asserted, or something expected could not be checked: the
        # answer is "not judged" rather than "passed", because a bundle that
        # asserts nothing has proven nothing.
        if self.unimplemented or not self.expected:
            return "INCOMPLETE"
        return "FAIL" if self.failures else "PASS"

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "assert case evidence",
            "result": self.result,
            "expected": list(self.expected),
            "observed": list(self.observed),
            "failures": list(self.failures),
            "unimplemented": list(self.unimplemented),
        }


def declared_assertions(case: Mapping[str, object]) -> tuple[str, ...]:
    """The assertion names a case manifest declares, in its own order."""

    value = case.get("assertions")
    if not isinstance(value, list):
        raise Unreadable("the case manifest declares no assertions")
    return tuple(str(item) for item in cast(list[object], value))


def evaluate(case: Mapping[str, object], material: RunMaterial) -> Verdict:
    """Evaluate every assertion the case declares against one run's material."""

    definition, _ = parse_case_manifest(dict(case))
    if definition is not None:
        material = replace(
            material,
            expected_case_id=definition.case_id,
            expected_case_version=definition.digest,
        )
    expected = declared_assertions(case)
    observed: list[str] = []
    failures: list[str] = []
    unimplemented: list[str] = []
    for name in expected:
        assertion = ASSERTIONS.get(name)
        if assertion is None:
            unimplemented.append(name)
            continue
        reason = assertion(material)
        if reason is None:
            observed.append(name)
        else:
            failures.append(f"{name}:{reason}")
    return Verdict(
        expected=expected,
        observed=tuple(observed),
        failures=tuple(failures),
        unimplemented=tuple(unimplemented),
    )


def _reject(message: str) -> int:
    report = {"schema_version": 1, "status": "unreadable", "message": message}
    print(json.dumps(report), file=sys.stderr)
    return EXIT_UNJUDGED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Judge one finished run's evidence against the case it was run for."
    )
    parser.add_argument("--case", type=Path, required=True, help="the case manifest to judge by")
    parser.add_argument(
        "--run-document",
        type=Path,
        default=None,
        help="what Core printed at the end; absent for a run that never printed one",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="names the run when there is no document, as a killed Core leaves none",
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument(
        "--server-directory",
        type=Path,
        default=None,
        help="the server run's directory; absent for a run that joined no world",
    )
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--fault-injection",
        type=Path,
        default=None,
        help="the harness's record of the fault it injected, when it injected one",
    )
    parser.add_argument(
        "--fault-injection-json",
        default=None,
        help=(
            "the same record as text, which is how the sealer hands over the exact "
            "snapshot it is about to seal rather than a path it read twice"
        ),
    )
    parser.add_argument(
        "--soak-samples",
        type=Path,
        default=None,
        help="a bounded soak's samples, as the harness wrote them",
    )
    parser.add_argument(
        "--soak-samples-json",
        default=None,
        help="the same samples as text, for the sealer's snapshot of what it seals",
    )
    parser.add_argument(
        "--soak-summary",
        type=Path,
        default=None,
        help="what the harness was asked to soak and what it did",
    )
    parser.add_argument(
        "--soak-summary-json",
        default=None,
        help="the same summary as text, for the sealer's snapshot of what it seals",
    )
    args = parser.parse_args(argv)

    if args.fault_injection is not None and args.fault_injection_json is not None:
        return _reject("name the fault record by its path or by its text, not both")
    try:
        if args.fault_injection is not None:
            fault_injection_record = fault_injection.read_record(args.fault_injection).document
        elif args.fault_injection_json is not None:
            fault_injection_record = fault_injection.parse_record(args.fault_injection_json)
        else:
            fault_injection_record = None
    except FaultInjectionError as error:
        return _reject(str(error))

    if args.soak_samples is not None and args.soak_samples_json is not None:
        return _reject("name the soak's samples by their path or by their text, not both")
    if args.soak_summary is not None and args.soak_summary_json is not None:
        return _reject("name the soak's summary by its path or by its text, not both")
    soak_samples = ""
    if args.soak_samples is not None:
        try:
            soak_samples = args.soak_samples.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            return _reject(f"{args.soak_samples} is not readable soak samples: {error}")
    elif args.soak_samples_json is not None:
        soak_samples = args.soak_samples_json
    soak_summary: Mapping[str, object] | None = None
    summary_text = args.soak_summary_json
    if args.soak_summary is not None:
        try:
            summary_text = args.soak_summary.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            return _reject(f"{args.soak_summary} is not a readable soak summary: {error}")
    if summary_text is not None:
        try:
            parsed = json.loads(summary_text)
        except json.JSONDecodeError as error:
            return _reject(f"the soak summary is not readable JSON: {error}")
        if not isinstance(parsed, Mapping):
            return _reject("the soak summary is not an object")
        soak_summary = cast(Mapping[str, object], parsed)

    try:
        case = json.loads(args.case.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return _reject(f"{args.case} is not readable JSON: {error}")
    if not isinstance(case, dict):
        return _reject(f"{args.case} is not a case manifest object")

    try:
        material = read_run_material(
            run_document=args.run_document,
            run_id=args.run_id,
            data_root=args.data_root,
            server_directory=args.server_directory,
            username=args.username,
            fault_injection=fault_injection_record,
            soak_samples=soak_samples,
            soak_summary=soak_summary,
        )
        verdict = evaluate(cast(Mapping[str, object], case), material)
    except Unreadable as error:
        return _reject(str(error))

    print(json.dumps(verdict.as_document(), sort_keys=True))
    if verdict.result == "PASS":
        return EXIT_HELD
    return EXIT_FAILED if verdict.result == "FAIL" else EXIT_UNJUDGED


if __name__ == "__main__":
    raise SystemExit(main())
