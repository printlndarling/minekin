"""Read a bounded window of personal attempts, not remembered world facts."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import cast

from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_log import SKILL_STEP_RECORDED
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.world_actions import ActionResultClass, skill_capabilities

MAX_EXPERIENCES = 8
MAX_SCAN = 64
MAX_PATTERNS = 8
CONTEXT_BUDGET_BYTES = 16_384


def read_skill_experiences(
    database: Path, *, kin_id: str, exclude_run_id: str = ""
) -> dict[str, object]:
    """Return recent same-Kin outcome claims with references; never execute them.

    A past CONFIRMED outcome is not evidence of today's inventory, terrain or
    permissions. No coordinates, arguments, goals or free-form model/chat text
    enter this packet. An invalid row invalidates the scanned window rather than silently
    selecting an older success. The original ledger is never repaired or rewritten.
    """
    packet: dict[str, object] = {
        "retriever_version": "skill-experiences-v2",
        "status": "not_retrieved",
        "freshness": "historical",
        "current_world_applicability": "unknown",
        "world_facts": "not_retrieved",
        "game_version_applicability": "unknown",
        "context_budget_bytes": CONTEXT_BUDGET_BYTES,
        "scan_limit": MAX_SCAN,
        "scanned_records": 0,
        "older_records_not_scanned": False,
        "records_omitted_within_scan": 0,
        "patterns_omitted_within_scan": 0,
        "records": [],
        "patterns": [],
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
                (kin_id, exclude_run_id, SKILL_STEP_RECORDED, MAX_SCAN + 1),
            ).fetchall()
        finally:
            connection.close()
    except (sqlite3.Error, MinekinError, OSError):
        packet["status"] = "ledger_unavailable"
        return packet
    records: list[dict[str, object]] = []
    packet["older_records_not_scanned"] = len(rows) > MAX_SCAN
    try:
        for row in rows[:MAX_SCAN]:
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
    # Summaries are deterministic projections of validated events, not model
    # stories or lifetime success rates. Keep contradictory result classes and
    # their latest references rather than laundering UNKNOWN into success.
    by_skill: dict[str, list[dict[str, object]]] = {}
    for record in records:
        by_skill.setdefault(str(record["skill"]), []).append(record)
    patterns: list[dict[str, object]] = []
    for skill, attempts in list(by_skill.items())[:MAX_PATTERNS]:
        latest: dict[str, object] = {}
        for attempt in attempts:
            latest.setdefault(str(attempt["result"]), attempt["event_id"])
        patterns.append(
            {
                "skill": skill,
                "source": "CORE",
                "trust_class": "CORE",
                "freshness": "historical",
                "current_world_applicability": "unknown",
                "result_counts": dict(Counter(str(attempt["result"]) for attempt in attempts)),
                "reason_counts": dict(
                    Counter(str(attempt["reason"]) for attempt in attempts if attempt["reason"])
                ),
                "latest_by_result": latest,
            }
        )
    visible = records[:MAX_EXPERIENCES]
    packet["records"] = visible
    packet["patterns"] = patterns
    packet["scanned_records"] = len(records)
    packet["records_omitted_within_scan"] = len(records) - len(visible)
    packet["patterns_omitted_within_scan"] = len(by_skill) - len(patterns)
    if records:
        packet["status"] = "found"
    # Bound the actual UTF-8 model context, including references and metadata.
    # Omission is explicit; the original ledger remains untouched and retrievable.
    while len(json.dumps(packet, ensure_ascii=False).encode("utf-8")) > CONTEXT_BUDGET_BYTES:
        if patterns:
            patterns.pop()
            packet["patterns_omitted_within_scan"] = len(by_skill) - len(patterns)
        else:
            visible.pop()
            packet["records_omitted_within_scan"] = len(records) - len(visible)
    return packet
