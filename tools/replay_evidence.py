"""Replaying an event stream: fold it through the state machine, compare the result.

Two things can be replayed, and they are honest about being different.

A **fixture** states both a stream and the projection it should produce, so replaying
it is a complete check: the stream is read, each event's payload is held to the digest
recorded beside it, the states are folded through the frozen machine, and the result is
compared with what the fixture says it should be. That fixture has been frozen since
W00 and read by nothing; this is its consumer, which is what "commit the fixture and
its expectation first, then the implementation" was waiting for.

An **evidence bundle** carries a timeline — Core's own ledger events, sealed as
`bridge-trace.jsonl` — and replaying it can only project what those rows actually say.
They record what happened, not which state the machine moved to, so a real run's
timeline has no states in it and this refuses rather than deriving a mapping from event
names to states. That mapping would be a guess about the recorder wearing the shape of
a check, and the run document already records the state the machine reached. This is
the finding the todo was missing, and it is a finding about what Core records rather
than about what a projector can do.

Exit codes: 0 the projection is what was expected, 1 it is not, 2 nothing could be
projected (and the reason is printed).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# The reading of a sealed timeline lives beside this file, and the projector lives in
# the domain. Imported rather than restated: a second spelling of an artifact name
# would read as "this run had no timeline" instead of failing.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from assert_case_evidence import LEDGER_TIMELINE_ARTIFACT  # noqa: E402
from minekin_core.adapters.sqlite.event_store import payload_digest  # noqa: E402
from minekin_core.application.ports.event_store import JsonValue  # noqa: E402
from minekin_core.domain.replay import (  # noqa: E402
    IllegalSessionTransition,
    ReplayRefused,
    SessionProjection,
    project_session,
)

EXIT_AGREES = 0
EXIT_DISAGREES = 1
EXIT_UNREPLAYABLE = 2


def _object(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReplayRefused(f"{what} is not an object")
    return cast(Mapping[str, object], value)


def _events(value: object, what: str) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        raise ReplayRefused(f"{what} is not a list of events")
    return [
        _object(item, f"{what}[{index}]") for index, item in enumerate(cast(list[object], value))
    ]


def verify_payloads(events: Sequence[Mapping[str, object]]) -> None:
    """Hold every payload to the digest recorded beside it.

    A replay that projects whatever payload it was handed is replaying the bytes it
    was given rather than the ones that were recorded, which is the difference between
    a check and a re-run.
    """

    for position, event in enumerate(events, start=1):
        recorded = event.get("payload_hash")
        if not isinstance(recorded, str) or not recorded:
            raise ReplayRefused(f"event {position} records no payload digest")
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            raise ReplayRefused(f"event {position} carries no payload object to digest")
        # `payload` came out of `json.loads`, so it is JSON; the alias is what the
        # store's own reader takes, and this is the same reader.
        actual = payload_digest(cast(JsonValue, payload))
        if actual != recorded:
            raise ReplayRefused(
                f"event {position} records payload digest {recorded} and its payload is "
                f"{actual} — the stream is not the one that was reviewed"
            )


def compare(expected: Mapping[str, object], projection: SessionProjection) -> list[str]:
    """Every part of the expected projection that this stream does not produce."""

    found: list[str] = []
    if expected.get("state") != projection.state.value:
        found.append(f"state:expected={expected.get('state')},projected={projection.state.value}")
    if expected.get("last_event_position") != projection.last_event_position:
        found.append(
            "last_event_position:"
            f"expected={expected.get('last_event_position')},projected={projection.last_event_position}"
        )
    return found


def replay_fixture(path: Path) -> dict[str, object]:
    """Replay a frozen fixture, whose expectation is part of the fixture itself."""

    try:
        document = _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except OSError as error:
        raise ReplayRefused(f"cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ReplayRefused(f"{path} is not JSON: {error}") from error
    events = _events(document.get("events"), f"{path}'s events")
    verify_payloads(events)
    expected = _object(document.get("expected_projection"), f"{path}'s expected_projection")
    projection = project_session(events)
    return {
        "schema_version": 1,
        "command": "replay evidence",
        "source": str(path),
        "events": len(events),
        "expected": dict(expected),
        "projected": projection.as_document(),
        "disagreements": compare(expected, projection),
    }


def replay_bundle(directory: Path) -> dict[str, object]:
    """Replay a sealed bundle's own timeline, or say why it cannot be replayed."""

    timeline = directory / LEDGER_TIMELINE_ARTIFACT
    if not timeline.is_file():
        raise ReplayRefused(
            f"{directory} holds no {LEDGER_TIMELINE_ARTIFACT} — there is no event stream "
            "here to replay"
        )
    rows = [
        _object(json.loads(line), f"{timeline} line {number}")
        for number, line in enumerate(timeline.read_text(encoding="utf-8").splitlines(), start=1)
        if line.strip()
    ]
    # Named here rather than left to the projector's refusal, because this is the
    # finding: a real ledger records what happened, not which state the machine moved
    # to, so a run's timeline has nothing in it to fold.
    if not any(
        isinstance(row.get("payload"), Mapping)
        and isinstance(cast(Mapping[str, object], row["payload"]).get("state"), str)
        for row in rows
    ):
        raise ReplayRefused(
            f"{directory} sealed {len(rows)} event(s) and none of them records a session "
            "state — the ledger says what happened, not where the session went, so this "
            "timeline cannot be projected and no mapping from event names to states is "
            "derived to make it look as though it could"
        )
    projection = project_session(rows)
    return {
        "schema_version": 1,
        "command": "replay evidence",
        "source": str(directory),
        "events": len(rows),
        "projected": projection.as_document(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "bundle",
        type=Path,
        nargs="?",
        default=None,
        help="a sealed bundle directory to replay",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="replay a frozen fixture, whose events and expectation travel together",
    )
    arguments = parser.parse_args(argv)
    if (arguments.bundle is None) == (arguments.fixture is None):
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "unreplayable",
                    "message": "give exactly one of a bundle directory or --fixture",
                }
            ),
            file=sys.stderr,
        )
        return EXIT_UNREPLAYABLE
    try:
        report = (
            replay_fixture(arguments.fixture)
            if arguments.fixture is not None
            else replay_bundle(arguments.bundle)
        )
    except (ReplayRefused, IllegalSessionTransition) as error:
        print(
            json.dumps({"schema_version": 1, "status": "unreplayable", "message": str(error)}),
            file=sys.stderr,
        )
        return EXIT_UNREPLAYABLE
    print(json.dumps(report, sort_keys=True, indent=2))
    found = cast(list[str], report.get("disagreements", []))
    if found:
        for item in found:
            print(item, file=sys.stderr)
        print(
            f"replay evidence: the stream does not produce the projection ({len(found)} part(s))",
            file=sys.stderr,
        )
        return EXIT_DISAGREES
    print(
        f"Replay evidence: OK ({report['source']} projects to what it says it should)",
        file=sys.stderr,
    )
    return EXIT_AGREES


if __name__ == "__main__":
    raise SystemExit(main())
