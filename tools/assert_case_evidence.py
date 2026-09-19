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
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from minekin_core.domain.offline_identity import offline_player_uuid

EXIT_HELD = 0
EXIT_FAILED = 1
EXIT_UNJUDGED = 2

# Vanilla writes both of these through the same `[Server thread/INFO]` logger, so
# the pattern is the log's shape rather than a guess about its wording: the
# bracketed time, the thread, the level, then the sentence.
_LINE = r"\[[^\]]*\] \[Server thread/INFO\]: {name} {event}"

RUN_DOCUMENT_KEY = "run"


def _sentence(name: str, event: str) -> re.Pattern[str]:
    return re.compile(_LINE.format(name=re.escape(name), event=re.escape(event)))


class Unreadable(Exception):
    """The material a case needs is not there or is not readable."""


@dataclass(frozen=True, slots=True)
class RunMaterial:
    """What a finished run left behind, as the asserter reads it."""

    run_document: Mapping[str, object]
    server_log: str
    #: The name-to-UUID map the *server* wrote when somebody logged in. The
    #: client's own claim about who it is is not evidence of who the server saw.
    server_identities: Mapping[str, str]
    username: str

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


def read_run_material(*, run_document: Path, server_directory: Path, username: str) -> RunMaterial:
    """Read a finished run's material, refusing anything that is not readable."""

    try:
        document = json.loads(run_document.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Unreadable(f"{run_document} is not readable JSON: {error}") from error
    if not isinstance(document, dict):
        raise Unreadable(f"{run_document} is not a run document object")

    log_path = server_directory / "server.log"
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
        run_document=cast(Mapping[str, object], document),
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


def leave_after_join_observed(material: RunMaterial) -> str | None:
    """The Kin left the world, after having joined it, at the run's own ending.

    Ordered rather than merely present: a leave recorded before the join is a
    different event — a stale line, or a log that is not this run's — and
    counting it would let a run that never ended pass by accident.
    """

    joined = material.join_line()
    left = material.leave_line()
    if joined is None:
        return "JOIN_NOT_LOGGED"
    if left is None:
        return "LEAVE_NOT_LOGGED"
    if left < joined:
        return "LEAVE_BEFORE_JOIN"
    outcome = _text(material.run(), "outcome")
    if outcome != "CLIENT_EXITED":
        return f"OUTCOME_NOT_A_CLEAN_EXIT:{outcome}"
    return None


#: Every assertion a case manifest may name, and what performs it. A name that is
#: not here cannot be judged, which the verdict reports rather than passing over.
ASSERTIONS: dict[str, Callable[[RunMaterial], str | None]] = {
    "server_observed_join_identity": server_observed_join_identity,
    "first_snapshot_admitted": first_snapshot_admitted,
    "leave_after_join_observed": leave_after_join_observed,
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
