"""Read a bounded window of personal attempts, not remembered world facts."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast

from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_log import SKILL_STEP_RECORDED
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.world_actions import ActionResultClass, skill_capabilities

MAX_EXPERIENCES = 8


def read_skill_experiences(
    database: Path, *, kin_id: str, exclude_run_id: str = ""
) -> dict[str, object]:
    """Return recent same-Kin outcome claims with references; never execute them.

    A past CONFIRMED outcome is not evidence of today's inventory, terrain or
    permissions. No coordinates, arguments, goals or free-form model/chat text
    enter this packet. An invalid row invalidates the window rather than silently
    selecting an older success. The original ledger is never repaired or rewritten.
    """
    packet: dict[str, object] = {
        "retriever_version": "skill-experiences-v1",
        "status": "not_retrieved",
        "freshness": "historical",
        "current_world_applicability": "unknown",
        "world_facts": "not_retrieved",
        "records": [],
    }
    if not database.is_file():
        packet["status"] = "ledger_missing"
        return packet
    try:
        connection = connect_reader(database)
        try:
            rows = connection.execute(
                "SELECT position,event_id,run_id,session_id,observed_at_utc,"
                "substr(payload_json,1,4097) AS payload_json,payload_hash "
                "FROM event WHERE kin_id=? AND run_id<>? AND event_type=? "
                "AND source='CORE' AND trust_class='CORE' ORDER BY position DESC LIMIT ?",
                (kin_id, exclude_run_id, SKILL_STEP_RECORDED, MAX_EXPERIENCES),
            ).fetchall()
        finally:
            connection.close()
    except (sqlite3.Error, MinekinError, OSError):
        packet["status"] = "ledger_unavailable"
        return packet
    records: list[dict[str, object]] = []
    try:
        for row in rows:
            if len(row["payload_json"]) > 4096:
                raise ValueError("experience payload exceeds budget")
            raw: object = json.loads(row["payload_json"])
            if not isinstance(raw, dict):
                raise ValueError("invalid experience payload")
            payload = cast("dict[str, JsonValue]", raw)
            if payload_digest(payload) != row["payload_hash"]:
                raise ValueError("experience digest mismatch")
            skill = payload.get("skill")
            if skill_capabilities(skill) is None:
                raise ValueError("unknown historical skill")
            result = ActionResultClass(str(payload.get("result", "")))
            reason = payload.get("reason", "")
            if not isinstance(reason, str) or not re.fullmatch(r"[A-Z0-9_]{0,96}", reason):
                raise ValueError("experience reason is not a bounded code")
            decision_source = payload.get("decision_source", "")
            if decision_source not in ("model", "local_reflection", "OPERATOR_PLAN", ""):
                raise ValueError("unknown decision source")
            for key in ("event_id", "run_id", "session_id"):
                value = row[key]
                if value is None and key == "session_id":
                    continue
                if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
                    raise ValueError("experience reference is not bounded")
            when = row["observed_at_utc"]
            if (
                not isinstance(when, str)
                or len(when) > 40
                or datetime.fromisoformat(when).tzinfo is None
            ):
                raise ValueError("experience timestamp is not timezone-aware")
            records.append(
                {
                    "event_id": row["event_id"],
                    "event_position": row["position"],
                    "run_id": row["run_id"],
                    "session_id": row["session_id"],
                    "observed_at_utc": when,
                    "source": "CORE",
                    "trust_class": "CORE",
                    "skill": skill,
                    "result": result.value,
                    "reason": reason,
                    "decision_source": decision_source,
                }
            )
    except (ValueError, TypeError, UnicodeError):
        packet["status"] = "invalid_record"
        return packet
    packet["records"] = records
    if records:
        packet["status"] = "found"
    return packet
