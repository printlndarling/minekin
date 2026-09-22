"""Sealing a finished run: judge it, collect it, seal it, read it back.

The run here is fabricated but its shapes are not. The run document is the one
`session start` prints, the server's log is the line vanilla writes, the user
cache is the entry vanilla records, the ledger is the real one written by the
real event log, and the profile and server profile are the reviewed fixtures the
harness actually runs with. What is not real is the run itself — the container
one is a separate, manual check — so a failure here is about the sealing path and
not about Minecraft.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import shutil
import stat
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from fault_support import fault_record
from minekin_core.adapters.evidence.bundle import unseal_bundle, verify_bundle
from minekin_core.adapters.evidence.promotion import load_case_manifest
from minekin_core.adapters.launcher.server_profile import load_server_profile
from minekin_core.adapters.sqlite.connection import connect_writer
from minekin_core.adapters.sqlite.session_log import (
    HELLO_ACCEPTED,
    INPUT_LEASE_GRANTED,
    PLAYABLE_ESTABLISHED,
    SessionEventLog,
)
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.domain.budget import (
    INTERVAL_LABEL,
    TICK_LABEL,
    BudgetLedger,
    read_window,
)
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.evidence import EMPTY_DOCUMENT_SHA256, NO_WORLD
from minekin_core.domain.ids import KinId
from minekin_core.generated.minekin.v1 import observation_pb2

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROFILE = REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"
SERVER_PROFILE = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "controlled-offline-server.json"
)
CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "core-020.json"
OBSERVE_ONLY_CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "core-010.json"
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
SESSION_ID = "f030bbeadf464c188c2921ede35e4c9f"
KIN = KinId("kin-01")
#: The Kin that hosted the world CORE-030's client joined, and that run's own id. A
#: host document is another run's account, so it is another Kin's run: the assertion
#: refuses a document that names this run's own Kin as its host.
OTHER_KIN = KinId("kin-02")
OTHER_KIN_RUN_ID = "9a1c2b3d4e5f60718293a4b5c6d7e8f9"
USERNAME = "Kin"
RECORDED_UUID = "8f40376b-c23f-3ef1-b553-5564eea75639"

SERVER_PROPERTIES = """level-seed=minekin-p0-controlled
online-mode=false
white-list=true
"""

SERVER_LOG = (
    "[20:39:00] [Server thread/INFO]: Starting minecraft server version 1.21.4\n"
    '[20:39:01] [Server thread/INFO]: Done (0.512s)! For help, type "help"\n'
    f"[20:39:52] [Server thread/INFO]: {USERNAME} joined the game\n"
    f"[20:40:31] [Server thread/INFO]: {USERNAME} left the game\n"
)


def sealed_tool(name: str = "seal_run_evidence") -> Any:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module(f"tools.{name}")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


SEALER = sealed_tool()
ASSERTER = sealed_tool("assert_case_evidence")
REJUDGE = sealed_tool("rejudge_evidence")
REPORT = sealed_tool("report_promotion")


@pytest.fixture(autouse=True)
def _leave_bundles_writable(tmp_path: Path) -> Iterator[None]:
    yield
    for found in sorted(tmp_path.rglob("manifest.json")):
        unseal_bundle(found.parent)


def run_document(overlay: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "started",
        "kin_id": str(KIN),
        "run_id": RUN_ID,
        "session_id": SESSION_ID,
        "generation": 1,
        "overlay": str(overlay),
        "pid": 184,
        "started_at": "2026-09-19T20:39:52.332759Z",
        "argv_digest": "f52431b722c014efa5dc1f0c2ffb09de84bd24679ffd2eb9a573b3cb7cc9b7e2",
        "recovery": {"invalidated": [], "waiting": [], "status": "reconciled"},
        "run": {
            "schema_version": 1,
            "status": "ended",
            "outcome": "BRIDGE_LOST",
            "session_state": "STOPPED",
            "connection_state": "PLAYABLE",
            "events_applied": 5,
            "events_ignored": 0,
            "snapshots_admitted": 1,
            "snapshot_rejections": [],
            "entities_admitted": 4,
            "entities_rejected": 0,
            "actions_applied": 0,
            "actions_refused": 0,
            "input_release_failed": False,
            "input_refusal": "",
        },
    }


def write_ledger(
    data_root: Path,
    events: tuple[str, ...] = (HELLO_ACCEPTED, PLAYABLE_ESTABLISHED),
    prior_run_id: str = "",
) -> Path:
    """A real ledger, written by the real event log.

    `prior_run_id` writes a run *before* this one — the crash a restart follows —
    which is the shape a case about recovery reads.
    """

    database = data_root / "kin" / str(KIN) / "kin.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    connect_writer(database).close()
    log = SessionEventLog(database, clock=SystemClock())
    if prior_run_id:
        for event_type in (HELLO_ACCEPTED, PLAYABLE_ESTABLISHED, INPUT_LEASE_GRANTED):
            asyncio.run(
                log.record_session_event(
                    event_type=event_type,
                    kin_id=str(KIN),
                    run_id=prior_run_id,
                    session_id="the-dead-session",
                    generation=1,
                    payload={},
                    source=EventSource.CORE,
                    trust_class=TrustClass.CORE,
                )
            )
    for event_type in events:
        asyncio.run(
            log.record_session_event(
                event_type=event_type,
                kin_id=str(KIN),
                run_id=RUN_ID,
                session_id=SESSION_ID,
                generation=1,
                payload={},
                source=EventSource.CORE,
                trust_class=TrustClass.CORE,
            )
        )
    # A second run's event, which must not travel into this run's timeline.
    asyncio.run(
        log.record_session_event(
            event_type=PLAYABLE_ESTABLISHED,
            kin_id=str(KIN),
            run_id="0" * 32,
            session_id="another-session",
            generation=1,
            payload={},
            source=EventSource.CORE,
            trust_class=TrustClass.CORE,
        )
    )
    return database


def finished_run_in(tmp_path: Path, **ledger: object) -> tuple[Path, Path, Path]:
    """A data root, a server directory, and the run document that describes them.

    `**ledger` goes to `write_ledger`, which is how a test asks for a run that
    followed another one.
    """

    data_root = tmp_path / "data"
    write_ledger(data_root, **ledger)  # type: ignore[arg-type]
    overlay = data_root / "kin" / str(KIN) / "run" / "session" / SESSION_ID / "generation-1"
    (overlay / "logs").mkdir(parents=True)
    (overlay / "logs" / "stdout.log").write_text(
        '<log4j:Event logger="minekin-bridge" level="INFO"><log4j:Message><![CDATA['
        "bridge released 1 input(s)]]></log4j:Message></log4j:Event>\n",
        encoding="utf-8",
    )
    server = tmp_path / "server-runs" / "run-59"
    server.mkdir(parents=True)
    (server / "server.log").write_text(SERVER_LOG, encoding="utf-8")
    (server / "server.properties").write_text(SERVER_PROPERTIES, encoding="utf-8")
    (server / "usercache.json").write_text(
        json.dumps([{"name": USERNAME, "uuid": RECORDED_UUID}]), encoding="utf-8"
    )
    path = tmp_path / "session.json"
    path.write_text(json.dumps(run_document(overlay)), encoding="utf-8")
    return data_root, server, path


@pytest.fixture
def finished_run(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A data root, a server directory, and the run document that describes them."""

    return finished_run_in(tmp_path)


def seal_it(
    data_root: Path, server: Path, document: Path, **overrides: object
) -> dict[str, object]:
    arguments: dict[str, object] = {
        "data_root": data_root,
        "case": CASE,
        "profile": PROFILE,
        "server_profile": SERVER_PROFILE,
        "run_document_path": document,
        "server_directory": server,
        "username": USERNAME,
        "renderer_display": "llvmpipe (LLVM 20.1.2, 256 bits)",
    }
    arguments.update(overrides)
    return cast(dict[str, object], SEALER.seal(**arguments))


def test_a_finished_run_seals_at_the_address_its_run_id_names(
    finished_run: tuple[Path, Path, Path],
) -> None:
    data_root, server, document = finished_run

    report = seal_it(data_root, server, document)

    expected = data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID
    assert report["status"] == "sealed"
    assert report["result"] == "PASS"
    assert report["evidence_directory"] == str(expected)
    assert expected.is_dir()
    # And the bundle the run produced is one the verifier accepts.
    verification = verify_bundle(expected)
    assert verification.verified
    assert verification.sealed
    assert verification.bundle_digest == report["bundle_digest"]


def test_the_manifest_carries_the_reviewed_case_s_own_version(
    finished_run: tuple[Path, Path, Path],
) -> None:
    data_root, server, document = finished_run

    seal_it(data_root, server, document)

    manifest = json.loads(
        (data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID / "manifest.json").read_bytes()
    )
    reviewed = json.loads(CASE.read_bytes())
    # The version is the definition's own digest, so a change to the case is a
    # change to the version and no old run can be read as evidence for the new one.
    assert manifest["case_id"] == reviewed["case_id"]
    assert manifest["case_version"] != ""
    assert manifest["test_run_id"] == RUN_ID


def test_the_manifest_s_digests_are_the_ones_that_were_measured(
    finished_run: tuple[Path, Path, Path],
) -> None:
    data_root, server, document = finished_run

    seal_it(data_root, server, document, server_jar=None)

    manifest = json.loads(
        (data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID / "manifest.json").read_bytes()
    )
    bundle = manifest["bundle"]
    assert bundle["minecraft"] == "1.21.4"
    assert bundle["loader"] == "0.16.9"
    assert bundle["fabric_api"] == "0.119.4+1.21.4"
    # The protocol schema is the `proto/` tree, hashed by the recipe's own rule.
    assert bundle["protocol_schema_digest"] == SEALER.protocol_schema_digest(REPOSITORY_ROOT)
    assert manifest["world"]["seed_or_snapshot_id"] == "minekin-p0-controlled"
    assert manifest["identity"]["server_observed_name_uuid"] == f"{USERNAME}/{RECORDED_UUID}"
    # The profile is named without saying where it lives on this host.
    assert str(REPOSITORY_ROOT) not in manifest["identity"]["configured_profile"]


def test_the_ledger_export_is_this_run_s_timeline_and_nothing_else(
    finished_run: tuple[Path, Path, Path],
) -> None:
    data_root, server, document = finished_run

    seal_it(data_root, server, document)

    lines = [
        json.loads(line)
        for line in (
            data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID / "bridge-trace.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [line["event_type"] for line in lines] == [HELLO_ACCEPTED, PLAYABLE_ESTABLISHED]
    assert {line["run_id"] for line in lines} == {RUN_ID}
    # Records rather than a rewriting: the identity and timing the ledger holds
    # come through, and the payload hash it rests on comes with them.
    assert [line["position"] for line in lines] == sorted(line["position"] for line in lines)
    assert all(len(line["payload_hash"]) == 64 for line in lines)


def test_a_run_that_followed_another_carries_the_run_before_it(tmp_path: Path) -> None:
    """A case about a restart reads the crash, so the bundle has to hold it.

    The judgement is reached on the same reading of the ledger that this export
    is made from, and a bundle that held only half of that reading would be one
    nobody else could reproduce.
    """

    dead_run = "b" * 32
    data_root, server, document = finished_run_in(tmp_path, prior_run_id=dead_run)

    report = seal_it(data_root, server, document)

    assert "previous-run-trace.jsonl" in cast(list[str], report["artifacts"])
    lines = [
        json.loads(line)
        for line in (
            data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID / "previous-run-trace.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [line["event_type"] for line in lines] == [
        HELLO_ACCEPTED,
        PLAYABLE_ESTABLISHED,
        INPUT_LEASE_GRANTED,
    ]
    assert {line["run_id"] for line in lines} == {dead_run}


def test_a_first_run_has_nothing_before_it_to_carry(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """An artifact that says "the run before this one" would be naming nothing."""

    data_root, server, document = finished_run

    report = seal_it(data_root, server, document)

    assert "previous-run-trace.jsonl" not in cast(list[str], report["artifacts"])
    assert not (
        data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID / "previous-run-trace.jsonl"
    ).exists()


def test_the_artifacts_include_the_client_s_own_output_and_the_server_s(
    finished_run: tuple[Path, Path, Path],
) -> None:
    data_root, server, document = finished_run

    report = seal_it(data_root, server, document)

    assert set(cast(list[str], report["artifacts"])) == {
        "asserter-inputs.json",
        "bridge-trace.jsonl",
        "client/stdout.log",
        "orchestrator-trace.json",
        "run-document.json",
        "server/server.log",
        "server/server.properties",
        "server/usercache.json",
    }


def test_the_bundle_records_the_inputs_the_judgement_was_made_with(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """A verdict can be reached a second time only from the same inputs.

    Which Kin, which run, which name the server saw and which run came before are not
    in any document — a run whose Core was killed never wrote the one that would have
    said — so a bundle that did not record them could be re-judged only by guessing.
    """

    data_root, server, document = finished_run

    seal_it(data_root, server, document)

    sealed = data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID / "asserter-inputs.json"
    assert sealed.is_file()
    recorded = json.loads(sealed.read_bytes())

    assert recorded["schema_version"] == 1
    assert recorded["run_id"] == RUN_ID
    assert recorded["kin_id"] == str(KIN)
    assert recorded["username"] == USERNAME


def test_a_run_that_fails_its_case_is_still_sealed(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """A failing run keeps its evidence: a bundle never written proves nothing."""

    data_root, server, document = finished_run
    (server / "server.log").write_text(
        "[20:39:01] [Server thread/INFO]: Done (0.512s)!\n", encoding="utf-8"
    )

    report = seal_it(data_root, server, document)

    assert report["status"] == "sealed"
    assert report["result"] == "FAIL"
    assert cast(list[str], report["failures"]) == [
        "first_snapshot_admitted:JOIN_NOT_LOGGED",
        "leave_after_join_observed:JOIN_NOT_LOGGED",
        "server_observed_join_identity:JOIN_NOT_LOGGED",
    ]
    assert verify_bundle(data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID).verified


def test_a_run_id_is_never_sealed_twice(finished_run: tuple[Path, Path, Path]) -> None:
    """A corrected result is a new run, and the second attempt says so."""

    data_root, server, document = finished_run
    seal_it(data_root, server, document)

    with pytest.raises(Exception, match="already holds a bundle"):
        seal_it(data_root, server, document)


def test_an_artifact_name_that_could_escape_the_bundle_is_refused(
    finished_run: tuple[Path, Path, Path],
) -> None:
    _, server, _ = finished_run
    found: dict[str, bytes] = {}

    with pytest.raises(SEALER.Unsealable, match="cannot be a path inside a bundle"):
        SEALER._artifact(server / "server.log", "../escape.log", found)


def test_the_seed_is_read_from_the_server_rather_than_configured(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """Vanilla rewrites the properties; the run directory is what it settled on."""

    _, server, _ = finished_run
    assert SEALER.world_seed(server) == "minekin-p0-controlled"

    (server / "server.properties").write_text("level-seed=\n", encoding="utf-8")
    assert SEALER.world_seed(server) == "unrecorded"

    (server / "server.properties").unlink()
    assert SEALER.world_seed(server) == "unrecorded"


def test_an_unreadable_run_document_is_not_sealed(
    finished_run: tuple[Path, Path, Path],
) -> None:
    data_root, server, document = finished_run
    document.unlink()

    with pytest.raises(SEALER.Unsealable, match="not a readable run document"):
        seal_it(data_root, server, document)


def no_world_run(tmp_path: Path) -> tuple[Path, Path]:
    """A run that joined nothing: a real ledger with only the handshake in it."""

    data_root = tmp_path / "no-world" / "data"
    write_ledger(data_root, events=(HELLO_ACCEPTED,))
    overlay = data_root / "kin" / str(KIN) / "run" / "session" / SESSION_ID / "generation-1"
    (overlay / "logs").mkdir(parents=True)
    document = no_world_document(overlay)
    path = tmp_path / "no-world" / "session.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return data_root, path


def no_world_document(overlay: Path) -> dict[str, object]:
    document = run_document(overlay)
    run = cast(dict[str, object], document["run"])
    run.update(
        {
            "connection_state": None,
            "snapshots_admitted": 0,
            "events_applied": 0,
            "entities_admitted": 0,
        }
    )
    return document


# The case a joining client is judged by: its own first snapshot, admitted.
JOIN_CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "core-030.json"


def joined_run(tmp_path: Path) -> tuple[Path, Path]:
    """A run in which this Kin joined a world another Kin was hosting.

    The shape that made the old guard wrong: no server profile to read the world out
    of, and a record that plainly shows one — the address the Bridge dialled, in the
    client's own log, and the snapshot Core admitted.
    """

    data_root = tmp_path / "joined" / "data"
    write_ledger(data_root, events=(HELLO_ACCEPTED, PLAYABLE_ESTABLISHED))
    overlay = data_root / "kin" / str(KIN) / "run" / "session" / SESSION_ID / "generation-1"
    (overlay / "logs").mkdir(parents=True)
    (overlay / "logs" / "stdout.log").write_text(
        '<log4j:Event logger="minekin-bridge" level="INFO"><log4j:Message><![CDATA['
        "bridge asked vanilla to connect to 127.0.0.1:25570 for generation 1 "
        "(finishedLoading=true, screen=none, overlay=none)"
        "]]></log4j:Message></log4j:Event>\n",
        encoding="utf-8",
    )
    document = run_document(overlay)
    run = cast(dict[str, object], document["run"])
    run.update({"connection_state": "PLAYABLE", "snapshots_admitted": 1})
    path = tmp_path / "joined" / "session.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return data_root, path


def test_a_run_that_joined_no_world_seals_the_absence_of_one(tmp_path: Path) -> None:
    """The contract's third kind, because the other two would be a claim about
    a world nobody visited."""

    data_root, document = no_world_run(tmp_path)

    report = SEALER.seal(
        data_root=data_root,
        case=OBSERVE_ONLY_CASE,
        profile=PROFILE,
        server_profile=None,
        run_document_path=document,
        server_directory=None,
        username=USERNAME,
    )

    assert report["result"] == "PASS"
    manifest = json.loads(
        (data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID / "manifest.json").read_bytes()
    )
    assert manifest["world"] == {
        "kind": NO_WORLD,
        "server_config_digest": EMPTY_DOCUMENT_SHA256,
        "seed_or_snapshot_id": NO_WORLD,
    }
    assert manifest["bundle"]["server_jar_sha1"] == ""
    assert manifest["identity"]["server_observed_name_uuid"] == ""
    assert "server/server.log" not in {record["path"] for record in manifest["artifacts"]}
    # No world joined means no hosting run to carry, which is not the same as a
    # hosting run whose document happened to be empty.
    assert "host-run-document.json" not in {record["path"] for record in manifest["artifacts"]}
    assert verify_bundle(data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID).verified


# A case whose only assertion is the fault record. The CORE-060 run fixture is
# heavier than this test needs — a lease, a lost IPC release and two server
# readings — and what is under test here is where the record goes, not what the
# rest of that case proves.
FAULT_CASE: dict[str, object] = {
    "schema_version": 1,
    "case_id": "CORE-060",
    "work_package": "W70",
    "mandatory": False,
    "inputs": [],
    "assertions": ["runtime_controller_sigkill_was_confirmed"],
}


def fault_case(tmp_path: Path) -> Path:
    path = tmp_path / "core-060-partial.json"
    path.write_text(json.dumps(FAULT_CASE), encoding="utf-8")
    return path


def fault_record_file(
    tmp_path: Path, *, case: Path = CASE, **overrides: object
) -> tuple[Path, bytes]:
    """A record on disk, and the exact bytes it holds."""

    path = tmp_path / "fault-injection.json"
    written = (
        json.dumps(
            fault_record(case_version=load_case_manifest(case).digest, **overrides),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    path.write_bytes(written)
    return path, written


def test_a_kill_run_seals_the_record_that_confirms_it(
    finished_run: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """The record is evidence, so it is sealed beside the run rather than kept."""

    data_root, server, document = finished_run
    case = fault_case(tmp_path)
    record, written = fault_record_file(tmp_path, case=case)

    report = seal_it(
        data_root,
        server,
        document,
        case=case,
        fault_injection_path=record,
    )

    assert report["result"] == "PASS", report["failures"]
    assert "fault-injection.json" in cast(list[str], report["artifacts"])
    bundle = data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID
    assert (bundle / "fault-injection.json").read_bytes() == written
    assert verify_bundle(bundle).verified


def test_the_judge_is_given_the_bytes_that_are_sealed_rather_than_the_path(
    finished_run: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """One reading of the file, used twice: as the judgement and as the artifact.

    The sealer hands the asserter the text rather than the path, so a record that
    changed between the two would not be judged as one thing and sealed as
    another — which is the whole reason the flag is not simply forwarded.
    """

    data_root, server, document = finished_run
    case = fault_case(tmp_path)
    _, written = fault_record_file(tmp_path, case=case)
    text = written.decode("utf-8")

    verdict = SEALER.run_asserter(
        case=case,
        run_document=document,
        run_id=None,
        data_root=data_root,
        server_directory=server,
        username=USERNAME,
        fault_injection=text,
    )

    assert verdict["result"] == "PASS", verdict["failures"]
    sealed = SEALER.collect_artifacts(
        overlay=None,
        server_directory=None,
        run_document=b"",
        fault_injection=written,
        soak_samples=b"",
        soak_summary=b"",
        orchestrator={},
    )
    assert sealed["fault-injection.json"] == written
    assert sealed["fault-injection.json"].decode("utf-8") == text


def test_a_soak_is_judged_and_sealed_from_the_same_bytes() -> None:
    """The same rule as the fault record, for the same reason: one reading.

    A soak is a measurement, and a measurement quoted from a live file is a claim
    about one — the distribution has to be computed from what the bundle holds.
    """

    samples = "client 512000 40 0\nclient 514048 41 600\nserver 921600 30 0\n"
    summary = json.dumps(
        {
            "schema_version": 1,
            "requested_seconds": 600,
            "interval_seconds": 10,
            "samples": {"client": 2, "server": 1},
            "ended_early": False,
            "failed_samples": False,
        }
    )

    sealed = SEALER.collect_artifacts(
        overlay=None,
        server_directory=None,
        run_document=b"",
        fault_injection=b"",
        soak_samples=samples.encode("utf-8"),
        soak_summary=summary.encode("utf-8"),
        orchestrator={},
    )

    assert sealed["soak-samples.txt"].decode("utf-8") == samples
    assert json.loads(sealed["soak-summary.json"])["requested_seconds"] == 600


def test_a_record_a_reader_would_refuse_stops_the_seal(
    finished_run: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """A record that is not one is not something to seal and hope about."""

    data_root, server, document = finished_run
    case = fault_case(tmp_path)
    record, _ = fault_record_file(tmp_path, case=case, outcome="MAYBE")

    with pytest.raises(SEALER.Unsealable, match="cannot be sealed"):
        seal_it(
            data_root,
            server,
            document,
            case=case,
            fault_injection_path=record,
        )

    assert not (data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID).exists()


class _Link:
    """A `lstat` answer that says "symlink", whatever the host allows."""

    st_mode = stat.S_IFLNK | 0o777


def _symlink_lstat(self: Path) -> _Link:
    return _Link()


def test_a_symlinked_record_stops_the_seal(
    finished_run: tuple[Path, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, server, document = finished_run
    case = fault_case(tmp_path)
    record, _ = fault_record_file(tmp_path, case=case)
    monkeypatch.setattr("pathlib.Path.lstat", _symlink_lstat)

    with pytest.raises(SEALER.Unsealable, match="SYMLINK"):
        seal_it(
            data_root,
            server,
            document,
            case=case,
            fault_injection_path=record,
        )


def test_a_case_that_demands_a_confirmed_kill_fails_without_one(
    finished_run: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """The assertion is judged with the rest, so its failure is the run's verdict."""

    data_root, server, document = finished_run

    report = seal_it(data_root, server, document, case=fault_case(tmp_path))

    assert report["result"] == "FAIL"
    assert cast(list[str], report["failures"]) == [
        "runtime_controller_sigkill_was_confirmed:NO_FAULT_INJECTION_RECORD"
    ]
    assert verify_bundle(data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID).verified


def test_a_fault_record_about_another_run_cannot_stand_for_this_one(
    finished_run: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Sealing it is allowed; counting it for this run is not."""

    data_root, server, document = finished_run
    case = fault_case(tmp_path)
    record, _ = fault_record_file(tmp_path, case=case, attribution={"run_id": "0" * 32})

    report = seal_it(
        data_root,
        server,
        document,
        case=case,
        fault_injection_path=record,
    )

    assert report["result"] == "FAIL"
    assert cast(list[str], report["failures"]) == [
        "runtime_controller_sigkill_was_confirmed:FAULT_RECORD_IS_ANOTHER_RUN:" + "0" * 32
    ]


def test_a_bundle_may_not_call_a_world_it_joined_no_world(tmp_path: Path) -> None:
    """Measured against Core's own document, not against the operator's word."""

    data_root, document = no_world_run(tmp_path)
    loaded = cast(dict[str, Any], json.loads(document.read_bytes()))
    loaded["run"]["connection_state"] = "PLAYABLE"
    document.write_text(json.dumps(loaded), encoding="utf-8")

    with pytest.raises(SEALER.Unsealable, match="the record shows a world"):
        SEALER.seal(
            data_root=data_root,
            case=OBSERVE_ONLY_CASE,
            profile=PROFILE,
            server_profile=None,
            run_document_path=document,
            server_directory=None,
            username=USERNAME,
        )


def test_the_same_run_seals_once_the_world_it_joined_is_named(tmp_path: Path) -> None:
    """The guard above, with the one thing it was missing: the world's name.

    A client that joined another Kin's world has no server profile either, and it
    shows exactly the record the guard refuses — a connection and an admitted
    snapshot. What separates it from the lie is that the world it was in is named,
    by the run that hosted it. Measured: without this the joining client's own run
    could not be sealed at all (CORE-030, the first real join).
    """

    data_root, document = joined_run(tmp_path)
    hosted = tmp_path / "host-session.json"
    hosted.write_text(json.dumps(hosting_run()), encoding="utf-8")

    report = SEALER.seal(
        data_root=data_root,
        case=JOIN_CASE,
        profile=PROFILE,
        server_profile=None,
        run_document_path=document,
        server_directory=None,
        world_run_document_path=hosted,
        username=USERNAME,
    )

    assert report["result"] == "PASS"
    manifest = json.loads(
        (data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID / "manifest.json").read_bytes()
    )
    assert manifest["world"] == {
        "kind": "lan",
        "server_config_digest": FROZEN_WORLD_SETTINGS,
        "seed_or_snapshot_id": SNAPSHOT_DIGEST,
    }
    # And the document those digests came from travels with the bundle: a reader can
    # check the world block against the run that measured it without hunting for it.
    sealed = data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID
    host_document = json.loads((sealed / "host-run-document.json").read_bytes())
    assert host_document["run"]["world_snapshot"]["digest"] == SNAPSHOT_DIGEST
    assert host_document["run"]["world_snapshot"]["settings_digest"] == FROZEN_WORLD_SETTINGS
    # The hosting run's document is sealed *beside* this run's own, under its own name.
    # Two documents, two artifacts: a reader who wants to know what this run's Core
    # recorded must not be handed somebody else's account.
    assert json.loads((sealed / "run-document.json").read_bytes())["run_id"] == RUN_ID
    assert host_document["run_id"] == OTHER_KIN_RUN_ID
    assert verify_bundle(sealed).verified


def test_the_judge_is_given_the_host_document_the_sealer_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One reading, not two: the file is replaced after it is read, and nothing moves.

    This is the seam the whole case rests on. The sealer hands the asserter the text
    it read — never the path — so the verdict, the manifest's world block and the
    sealed artifact are one reading of one file. A second reader would have been free
    to see a different document, and this is how that would look.
    """

    data_root, document = joined_run(tmp_path)
    hosted = tmp_path / "host-session.json"
    original = json.dumps(hosting_run())
    hosted.write_text(original, encoding="utf-8")

    # The document that would make the verdict FAIL, were it read a second time: the
    # same shape, a different world, and the same port.
    replaced = json.dumps(hosting_run(world_settings="0" * 64))
    handed: dict[str, object] = {}
    real = SEALER.run_asserter

    def replacing(**arguments: Any) -> dict[str, object]:
        handed.update(arguments)
        hosted.write_text(replaced, encoding="utf-8")
        return real(**arguments)

    monkeypatch.setattr(SEALER, "run_asserter", replacing)
    report = SEALER.seal(
        data_root=data_root,
        case=JOIN_CASE,
        profile=PROFILE,
        server_profile=None,
        run_document_path=document,
        server_directory=None,
        world_run_document_path=hosted,
        username=USERNAME,
    )

    # The judge was handed text, and it is the text of the document that was read.
    assert handed["world_run_document"] == original
    assert "world_run_document_path" not in handed
    sealed = data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID
    assert report["result"] == "PASS"
    assert (sealed / "host-run-document.json").read_text(encoding="utf-8") == original


def test_one_bad_host_document_is_the_same_document_in_all_three_places(tmp_path: Path) -> None:
    """The artifact, the manifest's world block and the verdict read one document.

    Measured with a host document that is well-formed, names a world, and names
    another one: the world block it records is that other world, the artifact sealed
    beside it is the document that said so, and the verdict is the failure that
    document deserves. A bundle can carry the wrong world and say so; what it must
    never do is carry one document and be judged on another.
    """

    data_root, document = joined_run(tmp_path)
    hosted = tmp_path / "host-session.json"
    elsewhere = hosting_run(world_settings="0" * 64)
    hosted.write_text(json.dumps(elsewhere), encoding="utf-8")

    report = SEALER.seal(
        data_root=data_root,
        case=JOIN_CASE,
        profile=PROFILE,
        server_profile=None,
        run_document_path=document,
        server_directory=None,
        world_run_document_path=hosted,
        username=USERNAME,
    )

    assert report["result"] == "FAIL"
    assert cast(list[str], report["failures"]) == [
        "the_world_this_run_joined_is_the_one_the_case_names:"
        "THE_WORLD_THIS_RUN_JOINED_IS_ANOTHER_WORLD:" + "0" * 64
    ]
    sealed = data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID
    manifest = json.loads((sealed / "manifest.json").read_bytes())
    assert manifest["world"] == {
        "kind": "lan",
        "server_config_digest": "0" * 64,
        "seed_or_snapshot_id": SNAPSHOT_DIGEST,
    }
    assert (
        json.loads((sealed / "host-run-document.json").read_bytes())["run"]["world_snapshot"][
            "settings_digest"
        ]
        == "0" * 64
    )
    # A failed case keeps its evidence, and the evidence still verifies: what failed is
    # the run, not the sealing of it.
    assert verify_bundle(sealed).verified


def test_a_host_document_swapped_for_another_world_is_caught(tmp_path: Path) -> None:
    """The bundle is read back against itself, so the world block cannot be rewritten.

    The attack this closes: keep a passing bundle and replace the hosting run's
    document with one that names another world. The artifact's own digest is in the
    manifest, so the document cannot change without that digest changing — and the
    manifest's digest is in `bundle.sha256`, so the world block cannot be rewritten to
    match without the bundle digest changing too.
    """

    data_root, document = joined_run(tmp_path)
    hosted = tmp_path / "host-session.json"
    hosted.write_text(json.dumps(hosting_run()), encoding="utf-8")
    SEALER.seal(
        data_root=data_root,
        case=JOIN_CASE,
        profile=PROFILE,
        server_profile=None,
        run_document_path=document,
        server_directory=None,
        world_run_document_path=hosted,
        username=USERNAME,
    )
    sealed = data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID
    unseal_bundle(sealed)
    (sealed / "host-run-document.json").write_text(
        json.dumps(hosting_run(world_settings="0" * 64)), encoding="utf-8"
    )

    assert verify_bundle(sealed).violations == ("ARTIFACT_DIGEST_MISMATCH:host-run-document.json",)

    # And rewriting the manifest to accept the new bytes is rewriting the bundle: the
    # digest `bundle.sha256` holds is the manifest's, which is the whole point of it.
    manifest_path = sealed / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    digest = hashlib.sha256((sealed / "host-run-document.json").read_bytes()).hexdigest()
    records = cast(list[dict[str, object]], manifest["artifacts"])
    for record in records:
        if record["path"] == "host-run-document.json":
            record["sha256"] = digest
    manifest_path.write_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )

    assert "BUNDLE_DIGEST_MISMATCH" in verify_bundle(sealed).violations


def test_a_world_run_that_is_not_a_document_stops_the_seal(tmp_path: Path) -> None:
    """The exemption is an input, so it is read like one: unreadable is refused."""

    data_root, document = joined_run(tmp_path)
    hosted = tmp_path / "host-session.json"
    hosted.write_text("[]", encoding="utf-8")

    with pytest.raises(SEALER.Unsealable, match="is not a run document object"):
        SEALER.seal(
            data_root=data_root,
            case=JOIN_CASE,
            profile=PROFILE,
            server_profile=None,
            run_document_path=document,
            server_directory=None,
            world_run_document_path=hosted,
            username=USERNAME,
        )


# --- what the bundle says about the world a run had -----------------------------
SETTINGS_DIGEST = "b7b5c62b1d0a44f1cbb0a4d5f5a5b6a2b2e0a9a1f4f7c2d3e4a5b6c7d8e9f0a1"
SNAPSHOT_DIGEST = "aac62c39872dd515dcb0d062a4b8ba5a5c6a333f29a4e1833e1d12686339be15"
#: The digest of the world fixture CORE-030 starts from — `level.dat`'s own SHA-256,
#: as `tests/fixtures/manifest.sha256` records it. Spelled out rather than recomputed
#: here, for the reason the asserter's tests give: a fixture whose bytes changed
#: without this constant changing has to be a failure, and a digest taken from the
#: file would agree with whatever it found.
FROZEN_WORLD_SETTINGS = "3bdd4affd45b65b90dbb7cd25ae34581b6beaf42edcf2324f63f187b5023c00c"


def hosting_run(*, world_settings: str = FROZEN_WORLD_SETTINGS) -> dict[str, object]:
    """The run that hosted the world CORE-030's client joined.

    Every part of it is something the join case binds to, and the assertion refuses
    each on its own: the world is the fixture the case names, it was published on the
    port the joining client dialled, and the run that published it is not the run that
    joined. A document built for this case has to be all three.
    """

    document = hosted_run(kin_id=str(OTHER_KIN), run_id=OTHER_KIN_RUN_ID)
    cast(dict[str, object], document["run"])["world_snapshot"] = {
        "level_name": "kinworld",
        "digest": SNAPSHOT_DIGEST,
        "settings_digest": world_settings,
    }
    return document


def hosted_run(**overrides: object) -> dict[str, object]:
    """A run document for a session the Kin hosted rather than joined.

    No connection at all: a Kin in its own world has nothing to connect to, which is
    exactly the shape the old guard could not tell from "this run had no world".
    """

    document: dict[str, object] = {
        "schema_version": 1,
        "status": "started",
        "kin_id": str(KIN),
        "run_id": RUN_ID,
        "overlay": "/data/kin/kin-01/run/session/session-01/generation-1",
        "run": {
            "schema_version": 1,
            "status": "ended",
            "outcome": "BRIDGE_LOST",
            "session_state": "STOPPED",
            "connection_state": None,
            "snapshots_admitted": 0,
            "world_snapshot": {
                "level_name": "kinworld",
                "digest": SNAPSHOT_DIGEST,
                "settings_digest": SETTINGS_DIGEST,
            },
            "lan_publication": {"phase": "LAN_OPENED", "port": 25570},
        },
    }
    document.update(overrides)
    return document


def test_a_world_the_kin_hosted_is_not_recorded_as_no_world() -> None:
    """The bug this exists for: a hosted world sealed as `kind: none`.

    Measured: the guard that refuses to call a joined world "none" looks for a
    *connection*, and a Kin in its own world has none — so the bundle denied a world
    the run's own document recorded, with the digest of nothing where a world's
    configuration belongs.
    """

    record = SEALER._world_record(None, None, hosted_run(), None, USERNAME)

    assert record.kind == "lan"
    assert record.name == SNAPSHOT_DIGEST
    assert record.config_digest == SETTINGS_DIGEST


def test_a_run_with_no_world_at_all_is_still_recorded_as_none() -> None:
    """The negative control: the old behaviour is right for a run that had no world."""

    record = SEALER._world_record(None, None, {"run": {"connection_state": None}}, None, USERNAME)

    assert record.kind == "none"
    assert record.name == "none"
    assert record.config_digest == SEALER.EMPTY_DOCUMENT_SHA256


def test_a_hosted_world_without_its_settings_is_refused_rather_than_guessed() -> None:
    """The two fields mean different things, so one cannot stand in for the other."""

    document = hosted_run()
    cast(dict[str, object], document["run"])["world_snapshot"] = {
        "level_name": "kinworld",
        "digest": SNAPSHOT_DIGEST,
    }

    with pytest.raises(SEALER.Unsealable, match="does not name the world's settings"):
        SEALER._world_record(None, None, document, None, USERNAME)


def test_a_dedicated_run_still_records_the_profile_and_the_world_it_generated() -> None:
    """The path that already worked, pinned so the new one cannot displace it."""

    profile = load_server_profile(SERVER_PROFILE)

    record = SEALER._world_record(profile, None, {}, None, USERNAME)

    assert record.kind == "dedicated"
    assert record.config_digest == profile.revision


def test_a_hosted_world_whose_bytes_are_not_named_is_refused() -> None:
    """`lan` with no world named is the escape hatch the contract warns about.

    The same rule as the settings above, for the other field: a bundle that says a
    world was published and cannot say which one is a bundle nobody can reproduce.
    """

    document = hosted_run()
    cast(dict[str, object], document["run"])["world_snapshot"] = {
        "level_name": "kinworld",
        "settings_digest": SETTINGS_DIGEST,
    }

    with pytest.raises(SEALER.Unsealable, match="does not name the world's bytes"):
        SEALER._world_record(None, None, document, None, USERNAME)


def test_a_run_that_joined_another_runs_world_is_named_by_that_runs_document() -> None:
    """The joining client has no snapshot of its own, and the world's identity is
    recorded where it was measured: on the run that hosted it.

    Without this a bundle for a join could only say it joined *a* world, and the
    alternative — refusing to name one — is the escape hatch the contract closes.
    """

    record = SEALER._world_record(None, None, {"run": {}}, hosted_run(), USERNAME)

    assert record.kind == "lan"
    assert record.name == SNAPSHOT_DIGEST
    assert record.config_digest == SETTINGS_DIGEST


def test_a_world_run_that_recorded_no_world_is_refused_rather_than_called_none() -> None:
    """Saying there is a world and then recording none is the same lie as before."""

    with pytest.raises(SEALER.Unsealable, match="did not record a world of its own"):
        SEALER._world_record(None, None, {"run": {}}, {"run": {}}, USERNAME)


def test_a_host_document_that_was_given_and_says_nothing_is_not_the_absence_of_one() -> None:
    """The difference between an empty document and None is the whole of this guard.

    Measured false positive: a host document that is literally `{}` was read by
    truthiness, so `_world_record` fell through to `kind: none` — beside the artifact
    of the very document that failed to name a world, in a run whose own record says
    it was in one (`PLAYABLE`, an admitted snapshot). The caller handed over a document;
    "it says nothing" is a refusal, not "there was nothing to hand over", and only the
    second is allowed to reach the no-world branch.
    """

    joined = {"run": {"connection_state": "PLAYABLE", "snapshots_admitted": 1}}

    with pytest.raises(SEALER.Unsealable, match="did not record a world of its own"):
        SEALER._world_record(None, None, joined, {}, USERNAME)

    # The negative control in the same breath: with no document given, the same empty
    # record is still the third kind, which is what a run that joined nothing has.
    assert SEALER._world_record(None, None, {"run": {}}, None, USERNAME).kind == "none"


def test_a_run_that_joined_a_world_the_case_does_not_name_cannot_seal_as_none(
    tmp_path: Path,
) -> None:
    """The same hole the other way round: through `seal`, with the run's own record.

    The guard in `seal` is satisfied by *naming* a host document, so an empty one used
    to walk past it and produce a `kind: none` bundle for a run whose document reports
    a connection and an admitted snapshot. Refused now, and refused before anything is
    written: a bundle that denies a world the run lived in is worse than no bundle.
    """

    data_root, document = joined_run(tmp_path)
    hosted = tmp_path / "empty-host-session.json"
    hosted.write_text("{}", encoding="utf-8")

    with pytest.raises(SEALER.Unsealable, match="did not record a world of its own"):
        SEALER.seal(
            data_root=data_root,
            case=JOIN_CASE,
            profile=PROFILE,
            server_profile=None,
            run_document_path=document,
            server_directory=None,
            world_run_document_path=hosted,
            username=USERNAME,
        )

    assert not (data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID).exists()


def test_a_run_in_its_own_world_is_not_read_as_a_join() -> None:
    """Precedence: the snapshot on this run's own document wins.

    A host that also carries a world document (it should not, but the fields are
    independent) must still be recorded as the world it seeded, not as somebody
    else's.
    """

    record = SEALER._world_record(None, None, hosted_run(), {"run": {}}, USERNAME)

    assert record.name == SNAPSHOT_DIGEST


# ---------------------------------------------------------------------------
# Reading a sealed bundle back, and reaching its verdict a second time
# ---------------------------------------------------------------------------


def bundle_of(data_root: Path) -> Path:
    return data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID


def tamper_with_the_verdict(bundle: Path, edit: Any) -> None:
    """Change the sealed verdict and make the bundle hold up again.

    Regenerating the digest file is not cheating — it is what the attack looks like.
    A reader who can change the manifest can change the digest beside it, and the
    question this test asks is which of the two checks catches that.
    """

    unseal_bundle(bundle)
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    edit(manifest)
    payload = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    (bundle / "manifest.json").write_bytes(payload)
    (bundle / "bundle.sha256").write_text(
        f"{hashlib.sha256(payload).hexdigest()}\n", encoding="ascii"
    )


def test_a_sealed_bundle_re_judged_produces_the_verdict_it_records(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """The whole claim: these bytes, judged again, answer what the bundle says they did."""

    data_root, server, document = finished_run
    sealed = seal_it(data_root, server, document)
    assert sealed["result"] == "PASS"
    bundle = bundle_of(data_root)
    manifest = json.loads((bundle / "manifest.json").read_bytes())["assertions"]

    report = REJUDGE.rejudge(bundle, CASE.parent)

    assert report["disagreements"] == []
    assert report["recorded"] == {
        "result": "PASS",
        "expected": manifest["expected"],
        "observed": manifest["observed"],
        "failures": [],
    }
    assert report["recorded"] == {
        "result": report["re_judged"]["result"],
        "expected": report["re_judged"]["expected"],
        "observed": report["re_judged"]["observed"],
        "failures": report["re_judged"]["failures"],
    }


def test_the_sealed_material_is_the_material_the_verdict_was_reached_on(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """A re-judge is a second opinion only if it is handed the same reading.

    Every field the judge sees has to survive the round trip through the bundle —
    including the client's two streams, concatenated in the order the judge read
    them, and the ledger's rows, which are sealed as a timeline rather than as the
    database they came out of.
    """

    data_root, server, document = finished_run
    seal_it(data_root, server, document)
    live = ASSERTER.read_run_material(
        run_document=document,
        data_root=data_root,
        server_directory=server,
        username=USERNAME,
    )

    sealed = ASSERTER.read_sealed_material(bundle_of(data_root))

    assert sealed.kin_id == live.kin_id
    assert sealed.run_id == live.run_id
    assert sealed.username == live.username
    assert sealed.previous_run_id == live.previous_run_id
    assert sealed.run_document == live.run_document
    assert sealed.client_log == live.client_log
    assert sealed.ledger_events == live.ledger_events
    assert sealed.ledger_readable == live.ledger_readable
    assert sealed.server_log == live.server_log
    assert sealed.server_identities == live.server_identities
    # The one field that is deliberately not carried: a path into the machine the run
    # happened on. What the assertions read out of that directory is its logs, and
    # those are sealed under their own names.
    assert sealed.overlay is None


def test_a_verdict_the_bytes_do_not_produce_is_caught(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """The hole this exists to close, and the check it closes it against.

    Dropping one observed assertion leaves a manifest that is still a valid PASS with
    a non-empty observation list, and regenerating the digest makes it verify. So
    `verify_bundle` says yes to a bundle whose verdict the bytes do not support, and
    the re-judge is what says no.
    """

    data_root, server, document = finished_run
    seal_it(data_root, server, document)
    bundle = bundle_of(data_root)

    def drop_one_observation(manifest: dict[str, Any]) -> None:
        observed = manifest["assertions"]["observed"]
        assert len(observed) > 1
        manifest["assertions"]["observed"] = observed[:-1]

    tamper_with_the_verdict(bundle, drop_one_observation)

    assert verify_bundle(bundle).verified, "the tampered bundle still verifies — that is the hole"
    report = REJUDGE.rejudge(bundle, CASE.parent)

    assert report["disagreements"], report
    assert any(item.startswith("OBSERVED:") for item in report["disagreements"])


def test_a_claimed_pass_over_a_failing_run_is_caught(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """The same hole at its most useful: a verdict rewritten to look like a pass.

    The run here genuinely fails — the server's log never says the Kin joined, so the
    identity assertion cannot hold — and the tamper rewrites the manifest to claim
    every assertion held. Regenerating the digest makes it verify; the re-judge is
    what says the bytes never supported that.
    """

    data_root, server, document = finished_run
    (server / "server.log").write_text(
        "[20:39:01] [Server thread/INFO]: Done (0.512s)!\n", encoding="utf-8"
    )
    sealed = seal_it(data_root, server, document)
    assert sealed["result"] == "FAIL"
    bundle = bundle_of(data_root)

    def claim_a_pass(manifest: dict[str, Any]) -> None:
        manifest["assertions"]["failures"] = []
        manifest["assertions"]["observed"] = manifest["assertions"]["expected"]
        manifest["result"] = "PASS"

    tamper_with_the_verdict(bundle, claim_a_pass)

    assert verify_bundle(bundle).verified, "the tampered bundle still verifies — that is the hole"
    report = REJUDGE.rejudge(bundle, CASE.parent)

    assert report["recorded"]["result"] == "PASS"
    assert report["re_judged"]["result"] == "FAIL"
    assert any(item.startswith("RESULT:") for item in report["disagreements"]), report


def test_a_bundle_sealed_against_another_case_version_cannot_be_re_judged(
    tmp_path: Path, finished_run: tuple[Path, Path, Path]
) -> None:
    """The criteria moved, so the recorded verdict answers a question nobody asks now.

    Refusing is the point: re-judging it against today's case would produce a
    disagreement and read as a tampered bundle, when what happened is that the case
    changed. A version mismatch is a different answer from a mismatch of verdicts.
    """

    data_root, server, document = finished_run
    seal_it(data_root, server, document)
    cases = tmp_path / "cases"
    shutil.copytree(CASE.parent, cases)
    moved = cases / "core-020.json"
    case_document = json.loads(moved.read_text(encoding="utf-8"))
    case_document["assertion_digests"] = dict.fromkeys(case_document["assertions"], "0" * 64)
    moved.write_text(json.dumps(case_document), encoding="utf-8")

    with pytest.raises(REJUDGE.Unresolvable, match="the criteria moved"):
        REJUDGE.rejudge(bundle_of(data_root), cases)


def test_a_bundle_without_the_judges_inputs_cannot_be_re_judged(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """Without them a re-judge would be guessing, and a guess is not a second reading."""

    data_root, server, document = finished_run
    seal_it(data_root, server, document)
    bundle = bundle_of(data_root)
    unseal_bundle(bundle)
    (bundle / "asserter-inputs.json").unlink()

    with pytest.raises(ASSERTER.Unreadable, match="does not record the inputs"):
        ASSERTER.read_sealed_material(bundle)


def test_the_promotion_report_re_judges_each_bundle_it_counts(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """The report is the only caller that can, so it is the one that does.

    The gate is judged against the real requirement, so one sealed bundle cannot make
    `W40` promotable — eleven of the twelve cases it requires are not answered for.
    What this asks is the narrower thing the report is uniquely able to do: reach the
    sealed verdict a second time.
    """

    data_root, server, document = finished_run
    seal_it(data_root, server, document)

    report = REPORT.report(data_root=data_root, cases_dir=CASE.parent, gated="W40")
    requirement = cast(dict[str, object], report["work_packages"]["W40"]["requirement"])

    bundles = cast(list[dict[str, object]], report["evidence"]["bundles"])
    assert [item["re_judged"] for item in bundles] == ["AGREES"]
    assert requirement["satisfied"] is False
    assert report["status"] == "blocked"


def test_the_promotion_report_refuses_a_verdict_the_bytes_do_not_support(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """The point of the whole step: such a bundle must not promote a package.

    The run fails — the server's log never says the Kin joined — and the manifest is
    rewritten to claim every assertion held. The bundle verifies, so nothing before
    the re-judge can refuse it, and `W40`'s only mandatory case is this one.
    """

    data_root, server, document = finished_run
    (server / "server.log").write_text(
        "[20:39:01] [Server thread/INFO]: Done (0.512s)!\n", encoding="utf-8"
    )
    seal_it(data_root, server, document)
    bundle = bundle_of(data_root)

    def claim_a_pass(manifest: dict[str, Any]) -> None:
        manifest["assertions"]["failures"] = []
        manifest["assertions"]["observed"] = manifest["assertions"]["expected"]
        manifest["result"] = "PASS"

    tamper_with_the_verdict(bundle, claim_a_pass)

    report = REPORT.report(data_root=data_root, cases_dir=CASE.parent, gated="W40")

    packages = cast(dict[str, dict[str, object]], report["work_packages"])
    assert report["status"] == "blocked"
    assert "EVIDENCE_DISAGREES_WITH_ITS_BYTES" in cast(list[str], packages["W40"]["blocks"])
    # Among the cases the gate is still missing, the one this bundle claims to be is
    # the one the disagreement is about.
    assert "CORE-020" in cast(list[str], packages["W40"]["blocking_cases"])
    listed = cast(list[dict[str, object]], report["evidence"]["bundles"])
    assert listed[0]["verified"] is True
    assert listed[0]["re_judged"] == "DISAGREES"
    assert "RESULT:" in cast(str, listed[0]["re_judge_reason"])


def test_the_callback_budget_is_part_of_the_sealed_record(
    finished_run: tuple[Path, Path, Path],
) -> None:
    """What the Bridge's callbacks cost travels as evidence, which means it seals.

    The run document is where a run's account of itself lives, so the budget's shape
    belongs there rather than in a file of its own — and the question a test has to
    answer is not whether a new key can be written. It is whether a bundle carrying it
    still verifies, and whether the aggregate read back is the one the run reached
    rather than something re-derived at the far end.

    Built from real wire messages, so the shape under test is the one the Bridge
    sends and not a hand-written approximation of it.
    """

    data_root, server, document = finished_run
    ledger = BudgetLedger()
    for label in (TICK_LABEL, INTERVAL_LABEL):
        for window in (1, 2, 4):
            reported, refusal = read_window(
                observation_pb2.CallbackBudgetWindow(
                    label=label,
                    window=window,
                    opened_at_nanos=window * 10_000_000_000,
                    recorded=100,
                    micros=range(100),
                )
            )
            assert refusal is None
            assert reported is not None
            ledger.observe(reported)

    payload = cast(dict[str, Any], json.loads(document.read_bytes()))
    payload["run"]["budgets"] = ledger.as_document()
    document.write_text(json.dumps(payload), encoding="utf-8")

    report = seal_it(data_root, server, document)

    assert report["status"] == "sealed"
    bundle = data_root / "kin" / str(KIN) / "run" / "evidence" / RUN_ID
    assert verify_bundle(bundle).verified
    sealed = cast(dict[str, Any], json.loads((bundle / "run-document.json").read_bytes()))
    budgets = sealed["run"]["budgets"]

    assert budgets["percentile_method"] == "nearest-rank"
    assert budgets["received_windows"] == 6
    # Window 3 never arrived, and the bundle says so by ordinal rather than by count:
    # the manifest protects these bytes, so a hole here is as tamper-evident as any
    # other claim the run made about itself.
    assert budgets["series"][TICK_LABEL]["missing_windows"] == [3]
    assert budgets["series"][TICK_LABEL]["recorded_samples"] == 300
    assert budgets["series"][INTERVAL_LABEL]["missing_windows"] == [3]
