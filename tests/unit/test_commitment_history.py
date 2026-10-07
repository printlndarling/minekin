"""Unfinished commitments read back from the same ledger that recorded them.

Slice B's consumer half: the resume packet loads "未完成承诺及期限" through one
deterministic query, and a recorded commitment survives a restart because it is a
ledger row, not session state. Like the sibling retrievers, the packet carries
references and bounded text, skips rows that do not survive their own digest, and
states its bounds instead of silently truncating.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import cast

import pytest

from minekin_core.adapters.sqlite.commitment_history import (
    MAX_TEXT_CARRY_CHARS,
    RECORD_LIMIT,
    SCAN_LIMIT,
    read_unfinished_commitments,
)
from minekin_core.adapters.sqlite.connection import migrate
from minekin_core.adapters.sqlite.session_log import (
    COMMITMENT_RECORDED,
    COMMITMENT_REJECTED,
    SessionEventLog,
)
from minekin_core.application.ports.clock import FakeClock
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.cli.session import mind_for_run
from minekin_core.domain.events import EventSource, TrustClass


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "kin.sqlite3"
    with sqlite3.connect(path, isolation_level=None) as connection:
        migrate(connection)
    return path


def _event(
    database: Path,
    *,
    event_type: str = COMMITMENT_RECORDED,
    kin_id: str = "kin-one",
    run_id: str = "run-a",
    payload: dict[str, JsonValue] | None = None,
    trust_class: str = "MODEL_SUGGESTED",
    source: str = "CORE",
    corrupt: bool = False,
) -> None:
    default: dict[str, JsonValue] = {
        "text": "come back to the cave",
        "due": "before the next night",
        "evidence_ref": "tick=650;generation=3",
        "observation_ref": "tick=650;generation=3",
    }
    body: dict[str, JsonValue] = payload if payload is not None else default
    digest = "0" * 64 if corrupt else payload_digest(body)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO event(event_id,event_type,schema_version,kin_id,run_id,sequence,"
            "correlation_id,monotonic_ns,observed_at_utc,source,trust_class,"
            "payload_json,payload_hash) "
            "VALUES (?, ?, 1, ?, ?, '1', 'test', 0, "
            "'2026-10-07T00:00:00+00:00', ?, ?, ?, ?)",
            (
                f"event-{abs(hash((run_id, event_type, json.dumps(body)))) % 10**12}",
                event_type,
                kin_id,
                run_id,
                source,
                trust_class,
                json.dumps(body),
                digest,
            ),
        )


@pytest.mark.parametrize(
    "source,trust_class",
    [
        ("BRIDGE", "MODEL_SUGGESTED"),
        ("OPERATOR_CLI", "OPERATOR"),
        ("CORE", "PLAYER_CHAT"),
        ("CORE", "UNTRUSTED_WORLD_CONTENT"),
    ],
)
def test_commitment_recall_requires_the_judging_writer_without_upgrading_model_text(
    tmp_path: Path, source: str, trust_class: str
) -> None:
    database = _database(tmp_path)
    _event(database, run_id="accepted-model", trust_class="MODEL_SUGGESTED")
    _event(database, run_id="core-intent", trust_class="CORE")
    _event(database, run_id="not-accepted", source=source, trust_class=trust_class)
    before = database.read_bytes()
    packet = read_unfinished_commitments(database, kin_id="kin-one")
    records = cast("list[dict[str, object]]", packet["records"])
    assert [(record["run_id"], record["trust_class"]) for record in records] == [
        ("core-intent", "CORE"),
        ("accepted-model", "MODEL_SUGGESTED"),
    ]
    assert packet["skipped_unreadable"] == 1
    resumed = mind_for_run("kin-one", {}, kin_dir=database.parent)
    assert resumed.session_history["commitments"] == packet
    assert database.read_bytes() == before


def test_recorded_commitments_read_back_newest_first_with_their_sources(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _event(database, run_id="run-old")
    _event(
        database,
        run_id="run-new",
        payload={
            "text": "keep the axe in the hotbar",
            "due": "",
            "evidence_ref": "event-elsewhere",
            "observation_ref": "tick=900;generation=4",
        },
    )

    packet = read_unfinished_commitments(database, kin_id="kin-one")

    assert packet["status"] == "found"
    assert packet["retriever_version"] == "commitments-v1"
    assert packet["reading_rule"] == "remembered_intent_revalidate"
    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["run-new", "run-old"]
    assert records[0]["text"] == "keep the axe in the hotbar"
    assert records[0]["due"] == ""
    assert records[0]["evidence_ref"] == "event-elsewhere"
    assert records[1]["due"] == "before the next night"
    assert records[0]["source"] == "CORE"
    assert records[0]["trust_class"] == "MODEL_SUGGESTED"
    assert records[0]["observed_at_utc"] == "2026-10-07T00:00:00+00:00"


def test_nothing_recorded_reads_not_retrieved_and_a_missing_ledger_says_so(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)

    empty = read_unfinished_commitments(database, kin_id="kin-one")
    assert empty["status"] == "not_retrieved"
    assert empty["records"] == []

    missing = read_unfinished_commitments(tmp_path / "absent.sqlite3", kin_id="kin-one")
    assert missing["status"] == "ledger_missing"
    assert missing["records"] == []


def test_rejections_and_malformed_rows_are_not_commitments(tmp_path: Path) -> None:
    """The ledger keeps the verdicts beside the commitments; only the recorded ones
    read back, and a row whose payload does not survive its own digest or its field
    checks is skipped and counted rather than trusted or silently dropped."""

    database = _database(tmp_path)
    _event(
        database,
        event_type=COMMITMENT_REJECTED,
        payload={"reason_code": "COMMITMENT_NO_EVIDENCE", "text_chars": 12, "due_chars": 0},
    )
    _event(database, run_id="run-corrupt", corrupt=True)
    _event(database, run_id="run-unshaped", payload={"text": 12, "due": "", "evidence_ref": ""})
    _event(database, run_id="run-good")

    packet = read_unfinished_commitments(database, kin_id="kin-one")

    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["run-good"]
    assert packet["skipped_unreadable"] == 2


def test_the_bounds_are_stated_and_never_silently_exceeded(tmp_path: Path) -> None:
    database = _database(tmp_path)
    for index in range(RECORD_LIMIT + 3):
        _event(database, run_id=f"run-{index:02d}")

    packet = read_unfinished_commitments(database, kin_id="kin-one", limit=RECORD_LIMIT)

    records = cast("list[dict[str, object]]", packet["records"])
    assert len(records) == RECORD_LIMIT
    assert packet["records_omitted_within_scan"] == 3
    assert packet["scan_limit"] == SCAN_LIMIT


def test_a_text_past_the_carry_bound_is_clipped_not_dropped(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _event(
        database,
        payload={
            "text": "x" * (MAX_TEXT_CARRY_CHARS + 100),
            "due": "",
            "evidence_ref": "tick=1;generation=1",
            "observation_ref": "tick=1;generation=1",
        },
    )

    packet = read_unfinished_commitments(database, kin_id="kin-one")

    records = cast("list[dict[str, object]]", packet["records"])
    assert len(records) == 1
    text = records[0]["text"]
    assert isinstance(text, str)
    assert len(text) == MAX_TEXT_CARRY_CHARS
    assert text.endswith("…")
    assert packet["skipped_unreadable"] == 0


def test_the_read_is_scoped_by_kin(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _event(database, kin_id="kin-two", run_id="other-kin")
    _event(database, run_id="this-kin")

    packet = read_unfinished_commitments(database, kin_id="kin-one")

    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["this-kin"]


def test_a_commitment_written_through_the_real_writer_reads_back_after_a_restart(
    tmp_path: Path,
) -> None:
    """The whole ledger road, writer to reader: the session log's own reviewed-event
    API accepts the record and the trust label, and a fresh read — the next session —
    finds the row. Nothing here is session state: the commitment survives a restart
    because it is a ledger row, which is exactly what slice B promises."""

    database = _database(tmp_path)
    log = SessionEventLog(database, clock=FakeClock())
    asyncio.run(
        log.record_session_event(
            event_type=COMMITMENT_RECORDED,
            kin_id="kin-one",
            run_id="run-live",
            session_id="session-1",
            generation=1,
            payload={
                "text": "come back to the cave",
                "due": "before the next night",
                "evidence_ref": "tick=650;generation=3",
                "observation_ref": "tick=650;generation=3",
            },
            source=EventSource.CORE,
            trust_class=TrustClass.MODEL_SUGGESTED,
        )
    )

    packet = read_unfinished_commitments(database, kin_id="kin-one")

    assert packet["status"] == "found"
    records = cast("list[dict[str, object]]", packet["records"])
    assert len(records) == 1
    assert records[0]["run_id"] == "run-live"
    assert records[0]["trust_class"] == "MODEL_SUGGESTED"
    assert records[0]["text"] == "come back to the cave"
    assert records[0]["due"] == "before the next night"
