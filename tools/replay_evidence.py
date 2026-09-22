"""Replaying an event stream: fold it through the state machine, compare the result.

Two things can be replayed, and they are honest about being different.

A **fixture** states both a stream and the projection it should produce, so replaying
it is a complete check: the stream is read, each event's payload is held to the digest
recorded beside it, the states are folded through the frozen machine, and the result is
compared with what the fixture says it should be. That fixture has been frozen since
W00 and read by nothing; this is its consumer, which is what "commit the fixture and
its expectation first, then the implementation" was waiting for. A fixture is a
repository artifact, so this path is test tooling and stays here.

An **evidence bundle** carries a timeline — Core's own ledger events, sealed as
`bridge-trace.jsonl` — and reading it is the same act `minekin replay <evidence-dir>`
performs, so it is the same code: `replay_sealed_bundle` in the product, which verifies
the bundle against the size and digest the manifest declares for its timeline before
parsing a byte of it. A real run's rows record what happened; a move is read only from a
row that states one explicitly (`from`/`to`), so a bundle sealed before the ledger
recorded transitions has nothing in it to fold — reported as the stable
`semantic_incomplete` result, not as a guess about what the event names must have meant.

The exit codes here stay this tool's own (0 projected, 1 the stream does not produce
the projection, 2 nothing could be projected). Which of the two kinds of refusal it
was is in the report, as `category`: `STORAGE` when the bytes are not the bytes that
were sealed, `SESSION` when they are and do not amount to a session history.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# The reading of a sealed timeline lives in the product, and the projector lives in
# the domain. Imported rather than restated: a second spelling of an artifact name
# would read as "this run had no timeline" instead of failing.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from minekin_core.adapters.evidence.trace import replay_sealed_bundle  # noqa: E402
from minekin_core.application.ports.event_store import JsonValue, payload_digest  # noqa: E402
from minekin_core.domain.replay import (  # noqa: E402
    IllegalSessionTransition,
    ReplayRefused,
    ReplayStatus,
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
    """Read a sealed bundle's own timeline, through the reading the product uses."""

    return {
        **replay_sealed_bundle(directory).as_dict(),
        "command": "replay evidence",
        "source": str(directory),
    }


def _refused(message: str) -> int:
    print(
        json.dumps({"schema_version": 1, "status": "unreplayable", "message": message}),
        file=sys.stderr,
    )
    return EXIT_UNREPLAYABLE


def _report_fixture(path: Path) -> int:
    try:
        report = replay_fixture(path)
    except (ReplayRefused, IllegalSessionTransition) as error:
        return _refused(str(error))
    print(json.dumps(report, sort_keys=True, indent=2))
    found = cast(list[str], report["disagreements"])
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


def _report_bundle(directory: Path) -> int:
    report = replay_bundle(directory)
    print(json.dumps(report, sort_keys=True, indent=2))
    if report["status"] != ReplayStatus.PROJECTED.value:
        print(
            f"replay evidence: nothing could be projected [{report['category']}] "
            f"{report['reason']}: {report['message']}",
            file=sys.stderr,
        )
        return EXIT_UNREPLAYABLE
    print(
        f"Replay evidence: OK ({report['source']} projects {report['events']} event(s))",
        file=sys.stderr,
    )
    return EXIT_AGREES


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
        return _refused("give exactly one of a bundle directory or --fixture")
    if arguments.fixture is not None:
        return _report_fixture(arguments.fixture)
    return _report_bundle(arguments.bundle)


if __name__ == "__main__":
    raise SystemExit(main())
