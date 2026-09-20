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
import importlib
import json
import stat
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from fault_support import fault_record
from minekin_core.adapters.evidence.bundle import unseal_bundle, verify_bundle
from minekin_core.adapters.evidence.promotion import load_case_manifest
from minekin_core.adapters.sqlite.connection import connect_writer
from minekin_core.adapters.sqlite.session_log import (
    HELLO_ACCEPTED,
    INPUT_LEASE_GRANTED,
    PLAYABLE_ESTABLISHED,
    SessionEventLog,
)
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.evidence import EMPTY_DOCUMENT_SHA256, NO_WORLD
from minekin_core.domain.ids import KinId

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


def sealed_tool() -> Any:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module("tools.seal_run_evidence")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


SEALER = sealed_tool()


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
        "bridge-trace.jsonl",
        "client/stdout.log",
        "orchestrator-trace.json",
        "run-document.json",
        "server/server.log",
        "server/server.properties",
        "server/usercache.json",
    }


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
