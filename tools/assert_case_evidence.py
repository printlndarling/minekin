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

from minekin_core.cli.init import DATABASE_NAME, kin_directory
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
HELLO_ACCEPTED = "BridgeHelloAccepted"
JOIN_OBSERVED = "JoinObserved"
PLAYABLE_ESTABLISHED = "PlayableEstablished"
INPUT_LEASE_GRANTED = "InputLeaseGranted"

_LEDGER_COLUMNS = (
    "position, event_id, event_type, schema_version, kin_id, run_id, "
    "client_instance_id, session_id, generation, world_context_id, sequence, "
    "correlation_id, causation_id, monotonic_ns, observed_at_utc, source, "
    "trust_class, payload_json, payload_hash"
)


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

    run_document: Mapping[str, object]
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


def read_run_material(
    *, run_document: Path, data_root: Path, server_directory: Path, username: str
) -> RunMaterial:
    """Read a finished run's material, refusing anything that is not readable.

    The ledger is looked up from the data root by the identity the run document
    carries, and a missing database is *not* an error here: a case that never
    needs Core's own record must still be judgeable on a host where the ledger is
    gone. What it must never be is indistinguishable from a ledger that was read
    and had nothing in it — hence `ledger_readable`, which the assertions that
    need one check before reporting that they saw nothing.
    """

    try:
        document = json.loads(run_document.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Unreadable(f"{run_document} is not readable run document JSON: {error}") from error
    if not isinstance(document, dict):
        raise Unreadable(f"{run_document} is not a run document object")
    run = cast(dict[str, object], document)

    kin, identifier = run.get("kin_id"), run.get("run_id")
    if not isinstance(kin, str) or not isinstance(identifier, str):
        raise Unreadable(f"{run_document} names no run to look up in the ledger")

    events: list[Mapping[str, object]] = []
    readable = False
    database = kin_directory(data_root, KinId(kin)) / DATABASE_NAME
    if database.is_file():
        try:
            events = [cast(Mapping[str, object], row) for row in ledger_rows(database, identifier)]
        except sqlite3.Error as error:
            raise Unreadable(f"{database} cannot be read for this run: {error}") from error
        readable = True

    # A run with no world to join has no server, and its absence is a fact about
    # the run rather than a reason the run cannot be judged.
    log_path = server_directory / "server.log"
    server_log = ""
    if log_path.is_file():
        try:
            server_log = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise Unreadable(f"{log_path} cannot be read: {error}") from error

    cache_path = server_directory / "usercache.json"
    identities: dict[str, str] = {}
    if cache_path.is_file():
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
        run_document=run,
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


#: Every assertion a case manifest may name, and what performs it. A name that is
#: not here cannot be judged, which the verdict reports rather than passing over.
ASSERTIONS: dict[str, Callable[[RunMaterial], str | None]] = {
    "server_observed_join_identity": server_observed_join_identity,
    "first_snapshot_admitted": first_snapshot_admitted,
    "leave_after_join_observed": leave_after_join_observed,
    "handshake_accepted_by_core": handshake_accepted_by_core,
    "stayed_observe_only": stayed_observe_only,
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
    parser.add_argument("--run-document", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--server-directory", type=Path, required=True)
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
