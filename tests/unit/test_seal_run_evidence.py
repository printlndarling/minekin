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
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from minekin_core.adapters.evidence.bundle import unseal_bundle, verify_bundle
from minekin_core.adapters.sqlite.connection import connect_writer
from minekin_core.adapters.sqlite.session_log import (
    HELLO_ACCEPTED,
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
    data_root: Path, events: tuple[str, ...] = (HELLO_ACCEPTED, PLAYABLE_ESTABLISHED)
) -> Path:
    """A real ledger, written by the real event log."""

    database = data_root / "kin" / str(KIN) / "kin.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    connect_writer(database).close()
    log = SessionEventLog(database, clock=SystemClock())
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


@pytest.fixture
def finished_run(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A data root, a server directory, and the run document that describes them."""

    data_root = tmp_path / "data"
    write_ledger(data_root)
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
