"""The frozen replay fixture finally has a consumer, and what it does without one.

`tests/fixtures/replay/session-preparing.v1.json` was committed at W00 with both a
stream and the projection it should produce, and nothing read it — deliberately, as
"commit the fixture and its expectation first, then the implementation". This is the
implementation's tests, and the first one is the point: the expectation and the
projector agree, so the fixture is a contract rather than a document.

The rest are about the two ways this can be useless, which are worth separate tests
because they are separate claims. A replay that reads a payload it has not held to the
recorded digest is replaying the bytes it was handed. And a bundle cannot be replayed
at all, which is not a defect in the projector: Core's ledger records what happened, not
which state the session moved to, so a real run's timeline has nothing in it to fold.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from minekin_core.adapters.sqlite.event_store import payload_digest
from minekin_core.application.ports.event_store import JsonValue

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/replay_evidence.py"
FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "replay" / "session-preparing.v1.json"


def run_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def replay_fixture(path: Path) -> subprocess.CompletedProcess[str]:
    return run_tool("--fixture", str(path))


def rewritten(tmp_path: Path, edit: object) -> Path:
    """The frozen fixture with one change, so a test can ask what catches it."""

    document = cast(dict[str, object], json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert callable(edit)
    edit(document)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


def timeline(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    directory = tmp_path / "bundle"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "bridge-trace.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return directory


def test_the_frozen_fixture_projects_to_what_it_says_it_should() -> None:
    """The fixture's expectation is a contract now, not a comment."""

    result = replay_fixture(FIXTURE)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["expected"] == report["projected"]
    assert report["projected"] == {"state": "PREPARING", "last_event_position": 1}
    assert report["disagreements"] == []


def test_a_payload_that_is_not_the_one_that_was_digested_is_refused(tmp_path: Path) -> None:
    """A replay that trusts the payload it is handed is not replaying the record."""

    def swap_the_payload(document: dict[str, object]) -> None:
        events = cast(list[dict[str, object]], document["events"])
        events[0]["payload"] = {"state": "PLAYABLE"}

    result = replay_fixture(rewritten(tmp_path, swap_the_payload))

    assert result.returncode == 2
    assert "is not the one that was reviewed" in result.stderr


def test_an_expectation_the_stream_does_not_produce_is_a_disagreement(tmp_path: Path) -> None:
    """The negative control for the hash check: the check runs, and then so does this."""

    def move_the_expectation(document: dict[str, object]) -> None:
        cast(dict[str, object], document["expected_projection"])["state"] = "PLAYABLE"

    result = replay_fixture(rewritten(tmp_path, move_the_expectation))

    assert result.returncode == 1
    assert "state:expected=PLAYABLE,projected=PREPARING" in result.stderr


def test_an_event_with_no_state_is_refused_rather_than_skipped(tmp_path: Path) -> None:
    """The digest is recomputed so the hash check passes and the projector is what refuses.

    Otherwise this would be a second test of the hash check wearing the name of a test
    about the projector, and the refusal under test would never run.
    """

    def drop_the_state(document: dict[str, object]) -> None:
        events = cast(list[dict[str, object]], document["events"])
        payload = {"note": "no state here"}
        events[0]["payload"] = payload
        events[0]["payload_hash"] = payload_digest(cast(JsonValue, payload))

    result = replay_fixture(rewritten(tmp_path, drop_the_state))

    assert result.returncode == 2
    assert "names no session state" in result.stderr


def test_a_bundle_whose_timeline_records_no_states_is_unreplayable(tmp_path: Path) -> None:
    """The finding, as a refusal a person can read: the ledger says what happened.

    This is what makes `replay <evidence-dir>` an entry point rather than a promise.
    It will project the moment Core records transitions; deriving a mapping from event
    names to states in the meantime would be a guess wearing the shape of a check.
    """

    directory = timeline(
        tmp_path,
        [
            {"event_type": "SessionProcessStarted", "payload": {}},
            {"event_type": "PlayableEstablished", "payload": {}},
        ],
    )

    result = run_tool(str(directory))

    assert result.returncode == 2
    assert "none of them records a session state" in result.stderr
    assert "sealed 2 event(s)" in result.stderr


def test_a_directory_with_no_timeline_is_unreplayable(tmp_path: Path) -> None:
    (tmp_path / "bundle").mkdir()

    result = run_tool(str(tmp_path / "bundle"))

    assert result.returncode == 2
    assert "there is no event stream here to replay" in result.stderr


def test_a_timeline_that_does_carry_states_is_projected(tmp_path: Path) -> None:
    """The negative control for the refusal above: nothing else is blocking it."""

    directory = timeline(
        tmp_path,
        [
            {"event_type": "SessionPreparing", "payload": {"state": "PREPARING"}},
            {"event_type": "SessionStartingClient", "payload": {"state": "STARTING_CLIENT"}},
        ],
    )

    result = run_tool(str(directory))

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["projected"] == {
        "state": "STARTING_CLIENT",
        "last_event_position": 2,
    }


def test_giving_both_a_bundle_and_a_fixture_is_refused(tmp_path: Path) -> None:
    result = run_tool(str(tmp_path), "--fixture", str(FIXTURE))

    assert result.returncode == 2
    assert "exactly one of" in result.stderr
