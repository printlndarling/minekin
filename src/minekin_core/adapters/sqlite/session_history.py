"""Bounded personal lifecycle history, never remembered world truth or an action replay."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast

from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_log import (
    INPUT_LEASE_GRANTED,
    INPUT_RELEASED,
    SESSION_STATE_TRANSITIONED,
)
from minekin_core.adapters.sqlite.skill_history import read_skill_experiences
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.session_state import SessionState


def read_last_session(
    database: Path, *, kin_id: str, exclude_run_id: str = ""
) -> dict[str, object]:
    """Return one trustworthy historical phase and its event reference, creating nothing.

    This is software lifecycle experience associated with the Kin, not knowledge
    of a server/world. STOPPED alone does not establish confirmed key release or
    a clean world save. Missing or corrupt evidence stays unknown. What the packet
    may say about input comes from the same run's own lease events, and no further
    than they do: `nothing_held` when no lease was ever granted, `released_recorded`
    when a release command was recorded (the Bridge's acknowledgement lives in the
    stop receipt, not the ledger, so `recorded` is the honest word), `not_released`
    when a lease was granted and no release was recorded — the fact a next session
    most needs, because those keys may have been down when the ledger stopped.
    """
    packet: dict[str, object] = {
        "retriever_version": "last-session-v1",
        "status": "not_retrieved",
        "freshness": "historical",
        "current_world_applicability": "unknown",
        "world_facts": "not_retrieved",
        "record": None,
        "skill_experiences": read_skill_experiences(
            database, kin_id=kin_id, exclude_run_id=exclude_run_id
        ),
    }
    if not database.is_file():
        packet["status"] = "ledger_missing"
        return packet
    try:
        connection = connect_reader(database)
        try:
            row = connection.execute(
                "SELECT position,event_id,run_id,session_id,observed_at_utc,"
                "substr(payload_json,1,4097) AS payload_json,payload_hash "
                "FROM event WHERE kin_id=? AND run_id<>? AND event_type=? "
                "AND source='CORE' AND trust_class='CORE' ORDER BY position DESC LIMIT 1",
                (kin_id, exclude_run_id, SESSION_STATE_TRANSITIONED),
            ).fetchone()
            # The same run's own lease facts, from the same ledger the record row
            # came from: read here, while the connection is open, and only for
            # this run — another session's release must not answer for this one.
            granted = False
            released = False
            if row is not None and isinstance(row["run_id"], str):
                lease_row = connection.execute(
                    "SELECT 1 FROM event WHERE kin_id=? AND run_id=? AND event_type=? "
                    "AND source='CORE' AND trust_class='CORE' LIMIT 1",
                    (kin_id, row["run_id"], INPUT_LEASE_GRANTED),
                ).fetchone()
                granted = lease_row is not None
                if granted:
                    release_row = connection.execute(
                        "SELECT 1 FROM event WHERE kin_id=? AND run_id=? AND event_type=? "
                        "AND source='CORE' AND trust_class='CORE' LIMIT 1",
                        (kin_id, row["run_id"], INPUT_RELEASED),
                    ).fetchone()
                    released = release_row is not None
        finally:
            connection.close()
    except (sqlite3.Error, MinekinError, OSError):
        packet["status"] = "ledger_unavailable"
        return packet
    if row is None:
        return packet
    # Do not echo arbitrary payload fields: a forged text field cannot become instructions.
    try:
        if len(row["payload_json"]) > 4096:
            raise ValueError("historical payload exceeds budget")
        raw: object = json.loads(row["payload_json"])
        if not isinstance(raw, dict):
            raise ValueError("invalid historical payload")
        payload = cast("dict[str, JsonValue]", raw)
        if payload_digest(payload) != row["payload_hash"]:
            raise ValueError("historical payload digest mismatch")
        phase = SessionState(str(payload.get("to", "")))
        for key in ("event_id", "run_id", "session_id"):
            value = row[key]
            if value is not None and (
                not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value)
            ):
                raise ValueError("historical reference is not bounded")
        when = row["observed_at_utc"]
        if (
            not isinstance(when, str)
            or len(when) > 40
            or datetime.fromisoformat(when).tzinfo is None
        ):
            raise ValueError("historical timestamp is not timezone-aware")
    except (ValueError, TypeError, UnicodeError):
        packet["status"] = "invalid_record"
        return packet
    packet["status"] = "found"
    packet["record"] = {
        "event_id": row["event_id"],
        "event_position": row["position"],
        "run_id": row["run_id"],
        "session_id": row["session_id"],
        "observed_at_utc": row["observed_at_utc"],
        "source": "CORE",
        "trust_class": "CORE",
        "last_recorded_phase": phase.value,
        "input_release": (
            "nothing_held" if not granted else "released_recorded" if released else "not_released"
        ),
    }
    return packet
