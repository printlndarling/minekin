"""The frozen replay fixture's consumer, and the one reading both entry points share.

`tests/fixtures/replay/session-preparing.v1.json` was committed at W00 with both a
stream and the projection it should produce, and nothing read it — deliberately, as
"commit the fixture and its expectation first, then the implementation". The fixture
tests here are that implementation's contract, and the first one is the point: the
expectation and the projector agree, so the fixture is a contract rather than a
document. A fixture is a repository artifact and only this tool reads one, so this half
stays test tooling.

The other half is about a sealed bundle, which is no longer this tool's own reading.
`minekin replay <evidence-dir>` and this tool read one through the same deep module
(`adapters/evidence/trace.py`), so the test that matters most is the one that would
catch the two drifting apart: the same bytes, read twice, classified the same way. And
a bundle is *sealed* here rather than hand-written, because the reading holds what it
parses to the size and digest the manifest declares — a directory with a
`bridge-trace.jsonl` dropped into it is undeclared material now, not a bundle.

The timelines below are the dialects that exist: `walk` is a ledger stating the moves it
records `from`/`to`, and `fixture_dialect` is the W00 fixture's shape, which a bundle
folding it must *not* project. The last group is about the entry point itself — what an
operator's exit code says when a bundle cannot be read at all.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from bundle_support import (
    fixture_dialect,
    ledger_row,
    seal_bundle,
    transition_row,
    walk,
)
from minekin_core.adapters.evidence.bundle import DIGEST_NAME
from minekin_core.adapters.evidence.trace import LEDGER_TIMELINE_ARTIFACT
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.bootstrap import run as run_cli
from minekin_core.domain.errors import ErrorCategory, ExitCode, exit_code_for

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/replay_evidence.py"
FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "replay" / "session-preparing.v1.json"

#: A timeline of the kind a real run seals today: rows that record what happened and
#: none that records where the session went.
RECORDS_NO_STATES = ledger_row(event_type="SessionProcessStarted", payload={}) + ledger_row(
    event_type="PlayableEstablished", payload={}
)

#: What a real timeline will look like once the ledger records transitions: ordinary
#: rows, and rows stating the move they recorded, in one stream.
MIXED_LEDGER = (
    ledger_row(event_type="SessionProcessStarted", payload={})
    + transition_row("STOPPED", "PREPARING")
    + ledger_row(event_type="BridgeHelloAccepted", payload={"generation": 1})
    + transition_row("PREPARING", "STARTING_CLIENT")
)


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


def bundle(tmp_path: Path, timeline: bytes) -> Path:
    """A sealed bundle holding this timeline, at the address its run id produces."""

    return seal_bundle(tmp_path, {LEDGER_TIMELINE_ARTIFACT: timeline})


def report_of(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result.stdout))


def replay_via_cli(directory: Path) -> tuple[int, dict[str, object], str]:
    """The same bundle through the product entry point, as `main` would run it."""

    stdout, stderr = io.StringIO(), io.StringIO()
    code = run_cli(["replay", str(directory)], stdout=stdout, stderr=stderr)
    return code, cast(dict[str, object], json.loads(stdout.getvalue())), stderr.getvalue()


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


def test_a_bundle_whose_timeline_records_no_states_is_stably_incomplete(tmp_path: Path) -> None:
    """The finding, as an answer a person can read: the ledger says what happened.

    This is what makes `replay <evidence-dir>` an entry point rather than a promise.
    It will project the moment Core records transitions; deriving a mapping from event
    names to states in the meantime would be a guess wearing the shape of a check.
    """

    result = run_tool(str(bundle(tmp_path, RECORDS_NO_STATES)))

    assert result.returncode == 2
    report = report_of(result)
    assert report["status"] == "semantic_incomplete"
    assert report["category"] == "SESSION"
    assert report["reason"] == "NO_STATE_TRANSITIONS"
    assert report["projected"] is None
    assert report["events"] == 2
    assert "records no transition" in result.stderr


def test_a_bundle_whose_timeline_is_the_fixture_dialect_projects_nothing(tmp_path: Path) -> None:
    """The W00 dialect is a fixture's shape, and a bundle holding it is not a ledger.

    The fixture's tool reads its own dialect from a fixture, and that is where it stays:
    the same rows sealed into a bundle are ordinary events, so the answer is the stable
    "this records no transition" rather than a projection the ledger never recorded.
    """

    result = run_tool(str(bundle(tmp_path, fixture_dialect("PREPARING", "STARTING_CLIENT"))))

    assert result.returncode == 2
    report = report_of(result)
    assert report["reason"] == "NO_STATE_TRANSITIONS"
    assert report["category"] == "SESSION"
    assert report["projected"] is None


def test_a_directory_that_is_not_a_bundle_is_refused_as_storage(tmp_path: Path) -> None:
    (tmp_path / "bundle").mkdir()

    result = run_tool(str(tmp_path / "bundle"))

    assert result.returncode == 2
    report = report_of(result)
    assert report["category"] == "STORAGE"
    assert report["status"] == "invalid"
    assert report["reason"] == "NOT_A_BUNDLE"


def test_a_bundle_whose_own_digest_file_is_corrupt_is_storage_rather_than_a_crash(
    tmp_path: Path,
) -> None:
    """The severe half of the taxonomy leak: a read failure must not read as a bug here.

    `bundle.sha256` is decoded as ASCII when a bundle is verified, and a byte that is
    not ASCII raises out of that decode. Through the real entry point that used to be an
    internal fault — a claim about this process — when what happened is that the bytes on
    disk are not the bundle that was sealed. `replay` says `STORAGE` and exits 12.
    """

    stdout, stderr = io.StringIO(), io.StringIO()
    pathological = b"\xc3\x28\xff\xfe\n"

    directory = seal_bundle(tmp_path, {LEDGER_TIMELINE_ARTIFACT: walk("STOPPED", "PREPARING")})
    (directory / DIGEST_NAME).write_bytes(pathological)

    code = run_cli(["replay", str(directory)], stdout=stdout, stderr=stderr)

    assert code == int(ExitCode.STORAGE), stderr.getvalue()
    report = cast(dict[str, object], json.loads(stdout.getvalue()))
    assert report["status"] == "invalid"
    assert report["category"] == "STORAGE"
    assert report["reason"] == "BUNDLE_CANNOT_BE_READ"
    assert report["projected"] is None
    assert stderr.getvalue() == ""


def test_a_bundle_that_declares_no_timeline_is_refused_as_storage(tmp_path: Path) -> None:
    """It holds up and says nothing about the run's own timeline: no stream to read."""

    directory = seal_bundle(tmp_path, {"server/server.log": b"Kin joined\n"})

    result = run_tool(str(directory))

    assert result.returncode == 2
    report = report_of(result)
    assert report["reason"] == "NO_TIMELINE_IS_DECLARED"
    assert report["category"] == "STORAGE"
    assert "there is no event stream here to replay" in result.stderr


def test_a_timeline_that_is_not_the_bytes_that_were_sealed_is_refused_as_storage(
    tmp_path: Path,
) -> None:
    directory = bundle(tmp_path, walk("STOPPED", "PREPARING"))
    (directory / LEDGER_TIMELINE_ARTIFACT).write_bytes(walk("STOPPED", "PLAYABLE"))

    result = run_tool(str(directory))

    assert result.returncode == 2
    report = report_of(result)
    assert report["category"] == "STORAGE"
    assert report["violations"] == [f"ARTIFACT_DIGEST_MISMATCH:{LEDGER_TIMELINE_ARTIFACT}"]


def test_a_timeline_that_does_carry_moves_is_projected(tmp_path: Path) -> None:
    """The negative control for the refusals above: nothing else is blocking it."""

    result = run_tool(str(bundle(tmp_path, walk("STOPPED", "PREPARING", "STARTING_CLIENT"))))

    assert result.returncode == 0, result.stderr
    assert report_of(result)["projected"] == {
        "state": "STARTING_CLIENT",
        "last_event_position": 2,
    }


def test_a_mixed_ledger_projects_the_moves_in_it_and_nothing_else(tmp_path: Path) -> None:
    """The shape a real timeline will have: ordinary events and stated moves together."""

    result = run_tool(str(bundle(tmp_path, MIXED_LEDGER)))

    assert result.returncode == 0, result.stderr
    report = report_of(result)
    assert report["events"] == 4
    assert report["projected"] == {"state": "STARTING_CLIENT", "last_event_position": 4}


def test_giving_both_a_bundle_and_a_fixture_is_refused(tmp_path: Path) -> None:
    result = run_tool(str(tmp_path), "--fixture", str(FIXTURE))

    assert result.returncode == 2
    assert "exactly one of" in result.stderr


@pytest.mark.parametrize(
    "timeline",
    [
        walk("STOPPED", "PREPARING", "STARTING_CLIENT"),
        MIXED_LEDGER,
        RECORDS_NO_STATES,
        fixture_dialect("PREPARING"),
    ],
)
def test_the_product_cli_and_the_tool_read_one_bundle_the_same_way(
    tmp_path: Path, timeline: bytes
) -> None:
    """The acceptance, as one claim: the same bytes are read by one module.

    Two entry points and one reading, so every part of the answer has to agree — and if
    they ever stop agreeing, this is the test that says which of them moved. The exit
    codes are deliberately *not* compared with each other: the tool keeps its own
    0/1/2 for the operator who runs tools, and the product CLI's code is the error
    category, which is the taxonomy a script branches on.
    """

    directory = bundle(tmp_path, timeline)

    result = run_tool(str(directory))
    code, cli_report, stderr = replay_via_cli(directory)

    tool_report = report_of(result)
    for part in (
        "status",
        "category",
        "reason",
        "message",
        "run_id",
        "bundle_digest",
        "trace",
        "trace_sha256",
        "trace_size",
        "events",
        "projected",
    ):
        assert cli_report[part] == tool_report[part], part
    assert stderr == ""
    category = tool_report["category"]
    expected = ExitCode.OK if category is None else exit_code_for(ErrorCategory(str(category)))
    assert code == int(expected)


def test_the_product_cli_exits_with_the_category_the_refusal_was_classified_as(
    tmp_path: Path,
) -> None:
    """Integrity is `STORAGE` and semantic incompleteness is `SESSION`, as exit codes."""

    no_states = bundle(tmp_path / "no-states", RECORDS_NO_STATES)
    tampered = bundle(tmp_path / "tampered", walk("STOPPED", "PREPARING"))
    (tampered / LEDGER_TIMELINE_ARTIFACT).write_bytes(walk("STOPPED", "PLAYABLE"))

    session_code, session_report, _ = replay_via_cli(no_states)
    storage_code, storage_report, _ = replay_via_cli(tampered)

    assert (session_code, session_report["category"]) == (int(ExitCode.SESSION), "SESSION")
    assert (storage_code, storage_report["category"]) == (int(ExitCode.STORAGE), "STORAGE")
