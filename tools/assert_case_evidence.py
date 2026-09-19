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
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from minekin_core.cli.init import DATABASE_NAME, KIN_DIRECTORY, kin_directory, run_root
from minekin_core.cli.session import session_overlay_path
from minekin_core.domain.ids import KinId
from minekin_core.domain.offline_identity import offline_player_uuid

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


def ledger_timeline(database: Path, run_id: str) -> bytes:
    """This run's events, exported as they were recorded."""

    return timeline_bytes(ledger_rows(database, run_id))


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
    server_log: str
    #: The name-to-UUID map the *server* wrote when somebody logged in. The
    #: client's own claim about who it is is not evidence of who the server saw.
    server_identities: Mapping[str, str]
    username: str

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
    database = kin_directory(data_root, KinId(kin)) / DATABASE_NAME
    if database.is_file():
        try:
            events = [cast(Mapping[str, object], row) for row in ledger_rows(database, named_run)]
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
        server_log=server_log,
        server_identities=identities,
        username=username,
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
    args = parser.parse_args(argv)

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
