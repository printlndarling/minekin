"""Deterministic, world-scoped recall of the places earlier sessions stood at.

The memory plan's place face (docs/memory-gateway-implementation-plan.md, slice C's
"地点面"): where did this Kin's own steps conclude in earlier sessions, in *this*
world? Answered from the same append-only ledger the sibling retrievers read,
keyed on the value the step wrote itself (`place`, the block floor of the reading
its verdict was taken on) and scoped by the run's own `AuthPolicyFrozen` profile —
never by guessing a world from coordinates, names or timestamps.

A coordinate is only a place inside the world it was read in. So a row is carried
only when its run named the same server profile the caller says is current; a row
from another profile, or from a run that named none, is counted and left out, and a
caller that cannot say which world is current gets `world_unknown` rather than
coordinates that might belong to somewhere else. What the packet carries is a past
occurrence — where the body stood when a verdict was read — never proof that
anything is still there.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import cast

from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_history import recorded_server_profile
from minekin_core.adapters.sqlite.session_log import SKILL_STEP_RECORDED
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.application.world_skills import MOVETO_MAX_COORDINATE
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.events import EventSource, TrustClass

#: How many ledger rows one recall may scan, and how many distinct places one
#: packet may carry. A recall is a summary input, not a map: the accounts say what
#: the bounds left out.
SCAN_LIMIT: int = 128
RECORD_LIMIT: int = 6
_REFERENCE = re.compile(r"[A-Za-z0-9_-]{1,128}")
_PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9._-]+")


def recall_place_history(
    database: Path,
    *,
    kin_id: str,
    current_server_profile_id: str,
    exclude_run_id: str = "",
    limit: int = RECORD_LIMIT,
) -> dict[str, object]:
    """Distinct places earlier runs in the current world concluded at, newest first."""

    packet: dict[str, object] = {
        "retriever_version": "place-history-v1",
        "status": "not_retrieved",
        "freshness": "historical",
        "current_world_applicability": "unknown",
        "anchor": {"kind": "world_scope", "value": current_server_profile_id},
        "scan_limit": SCAN_LIMIT,
        "record_limit": limit,
        "records_omitted_within_scan": 0,
        "records_from_other_worlds": 0,
        "records_without_world": 0,
        "skipped_unreadable": 0,
        "records": [],
    }
    if not current_server_profile_id or not _PROFILE_ID.fullmatch(current_server_profile_id):
        # Nobody said which world this run is in, so no coordinate can be said to
        # belong to it: claiming one would be a guess about where the Kin is.
        packet["status"] = "world_unknown"
        return packet
    if not database.is_file():
        packet["status"] = "ledger_missing"
        return packet
    try:
        connection = connect_reader(database)
        try:
            rows = connection.execute(
                "SELECT position,event_id,run_id,observed_at_utc,source,trust_class,"
                "substr(payload_json,1,4097) AS payload_json,payload_hash "
                "FROM event WHERE kin_id=? AND run_id<>? AND event_type=? "
                "ORDER BY position DESC LIMIT ?",
                (kin_id, exclude_run_id, SKILL_STEP_RECORDED, SCAN_LIMIT),
            ).fetchall()
            # Each run's world is read once, from that run's own frozen policy.
            worlds: dict[str, str] = {}
            for row in rows:
                run_id = row["run_id"]
                if isinstance(run_id, str) and run_id not in worlds:
                    worlds[run_id] = recorded_server_profile(connection, kin_id, run_id)
        finally:
            connection.close()
    except (sqlite3.Error, MinekinError, OSError):
        packet["status"] = "ledger_unavailable"
        return packet
    records: list[dict[str, object]] = []
    seen: set[tuple[int, int, int]] = set()
    skipped = 0
    omitted = 0
    other_world = 0
    no_world = 0
    for row in rows:
        decoded = _record(row)
        if decoded is None:
            skipped += 1
            continue
        place = cast("dict[str, int] | None", decoded["place"])
        if place is None:
            # A step whose reading carried no position is not a place; it is
            # neither unreadable nor out of scope, so it is simply not counted.
            continue
        world = worlds.get(cast("str", decoded["run_id"]), "")
        if not world:
            no_world += 1
            continue
        if world != current_server_profile_id:
            other_world += 1
            continue
        key = (place["x"], place["y"], place["z"])
        if key in seen:
            # The newest row for a spot answers for it; older visits are the
            # same place, not more places.
            omitted += 1
            continue
        if len(records) >= limit:
            omitted += 1
            continue
        seen.add(key)
        records.append({**cast("dict[str, object]", decoded["record"]), "server_profile_id": world})
    packet["records"] = records
    packet["records_omitted_within_scan"] = omitted
    packet["records_from_other_worlds"] = other_world
    packet["records_without_world"] = no_world
    packet["skipped_unreadable"] = skipped
    packet["current_world_applicability"] = "same_profile"
    if records:
        packet["status"] = "found"
    return packet


def _place(value: object) -> dict[str, int] | bool | None:
    """A carried place, None for an honest absence, or False for a malformed one."""

    if value is None:
        return None
    if not isinstance(value, dict) or set(cast("dict[str, object]", value)) != {"x", "y", "z"}:
        return False
    place: dict[str, int] = {}
    for axis, coordinate in cast("dict[str, object]", value).items():
        # bool is an int to Python; a ledger that says `true` did not say a block.
        if not isinstance(coordinate, int) or isinstance(coordinate, bool):
            return False
        if abs(coordinate) > MOVETO_MAX_COORDINATE:
            return False
        place[axis] = coordinate
    return place


def _record(row: sqlite3.Row) -> dict[str, object] | None:
    """One bounded record with its reference, or None for a row not carried."""

    # A matching digest proves payload integrity, not an executed Core step.
    if row["source"] != EventSource.CORE.value or row["trust_class"] != TrustClass.CORE.value:
        return None
    text = row["payload_json"]
    if not isinstance(text, str) or len(text) > 4096:
        return None
    try:
        value: object = json.loads(text)
        if not isinstance(value, dict):
            return None
        payload = cast("dict[str, JsonValue]", value)
        if payload_digest(payload) != row["payload_hash"]:
            return None
        place = _place(payload.get("place"))
        if place is False:
            return None
        for key in ("skill", "result"):
            field = payload.get(key, "")
            if not isinstance(field, str) or len(field) > 128:
                return None
        for key in ("event_id", "run_id"):
            reference = row[key]
            if not isinstance(reference, str) or not _REFERENCE.fullmatch(reference):
                return None
        when = row["observed_at_utc"]
        if not isinstance(when, str) or len(when) > 40:
            return None
    except (TypeError, ValueError, UnicodeError):
        return None
    return {
        "run_id": row["run_id"],
        "place": place,
        "record": {
            "event_id": row["event_id"],
            "event_position": row["position"],
            "run_id": row["run_id"],
            "observed_at_utc": row["observed_at_utc"],
            "source": row["source"],
            "trust_class": row["trust_class"],
            "skill": payload.get("skill", ""),
            "result": payload.get("result", ""),
            "place": place,
        },
    }
