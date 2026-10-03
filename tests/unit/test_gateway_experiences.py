"""Readonly personal history exposes results and references, not free-form payloads."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from gateway.identity import identity_read, saved_experiences_read
from gateway_support import KIN_ID, seed_kin
from minekin_core.application.ports.clock import FakeClock
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.cli.init import DATABASE_NAME, kin_directory


def test_identity_projects_personal_outcomes_without_mutating_ledger(tmp_path: Path) -> None:
    seed_kin(tmp_path, with_marker=False)
    directory = kin_directory(tmp_path, KIN_ID)
    database = directory / DATABASE_NAME
    assert saved_experiences_read(directory, str(KIN_ID)) == {"value": []}
    payload: dict[str, JsonValue] = {
        "skill": "consume_item",
        "result": "UNKNOWN",
        "reason": "NO_CONFIRMING_OBSERVATION",
        "decision_source": "model",
        "goal": "private-canary",
        "arguments": {"x": 9},
    }
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO event(event_id,event_type,schema_version,kin_id,run_id,sequence,"
            "correlation_id,monotonic_ns,observed_at_utc,source,trust_class,"
            "payload_json,payload_hash) "
            "VALUES ('experience-one', 'SkillStepRecorded', 1, ?, 'past-run', '1', 'test', 0, "
            "'2026-10-04T00:00:00+00:00', 'CORE', 'CORE', ?, ?)",
            (str(KIN_ID), json.dumps(payload), payload_digest(payload)),
        )
    before = database.read_bytes()
    result = identity_read(tmp_path, kin_selector=None, clock=FakeClock(), csrf_token="test")
    records = result["experiences"]["value"]
    assert len(records) == 1
    assert records[0]["event_id"] == "experience-one"
    assert records[0]["result"] == "UNKNOWN"
    assert "private-canary" not in json.dumps(result)
    assert "arguments" not in json.dumps(records)
    assert database.read_bytes() == before
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE event SET payload_hash=? WHERE event_id='experience-one'", ("0" * 64,)
        )
    result = saved_experiences_read(directory, str(KIN_ID))
    assert "EXPERIENCES_INVALID_RECORD" in result["gap"]["reason"]
    assert "value" not in result


def test_missing_ledger_is_not_an_empty_history_and_is_not_created(tmp_path: Path) -> None:
    result = saved_experiences_read(tmp_path / "absent", "kin-one")
    assert "EXPERIENCES_LEDGER_MISSING" in result["gap"]["reason"]
    assert not (tmp_path / "absent").exists()
