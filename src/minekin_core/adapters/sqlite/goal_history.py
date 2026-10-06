"""Deterministic goal-anchored recall over the step ledger.

The memory contract's first slice (docs/memory-gateway-implementation-plan.md):
"what have I recently tried for this product, and where did it stop?" — answered
from the same append-only ledger the other retrievers read, keyed on a value the
step wrote itself (`product_id`, see `SkillStep`), never guessed from reasons or
skill names. Like the sibling retrievers this packet carries evidence with its
sources and refuses to invent: no anchor, no ledger, or no hit all read as such,
and a row whose payload does not survive its own digest is skipped and counted
rather than silently dropped or trusted.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_log import SKILL_STEP_RECORDED
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.domain.errors import MinekinError

#: How many ledger rows one recall may scan, and how many records one packet may
#: carry. Bounded on purpose: a recall is a summary input, not a replay archive,
#: and the accounts say what the bound left out.
SCAN_LIMIT: int = 64
RECORD_LIMIT: int = 8
#: The longest reason a record may carry forward. A step's reason is free text,
#: so a longer one is clipped with an ellipsis rather than dropped — found live:
#: skipping long-reason rows loses whole runs of real history to a display bound
#: (the first recall scan lost 45), and the row's position still finds the full
#: text for anyone who wants it.
MAX_REASON_CHARS: int = 240


def recall_goal_history(
    database: Path,
    *,
    kin_id: str,
    product_id: str,
    exclude_run_id: str = "",
    limit: int = RECORD_LIMIT,
) -> dict[str, object]:
    """Recent steps anchored on one product, newest first, with their sources."""

    packet: dict[str, object] = {
        "retriever_version": "goal-history-v1",
        "status": "not_retrieved",
        "freshness": "historical",
        "current_world_applicability": "unknown",
        "anchor": {"kind": "goal_scope", "value": product_id},
        "scan_limit": SCAN_LIMIT,
        "record_limit": limit,
        "records_omitted_within_scan": 0,
        "skipped_unreadable": 0,
        "records": [],
    }
    if not product_id:
        # Nothing was asked for, so nothing is claimed about it.
        packet["status"] = "no_anchor"
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
        finally:
            connection.close()
    except (sqlite3.Error, MinekinError, OSError):
        packet["status"] = "ledger_unavailable"
        return packet
    records: list[dict[str, object]] = []
    skipped = 0
    omitted = 0
    for row in rows:
        decoded = _record(row)
        if decoded is None:
            skipped += 1
            continue
        if not _scopes_the_goal(decoded, product_id):
            omitted += 1
            continue
        if len(records) >= limit:
            omitted += 1
            continue
        records.append(cast("dict[str, object]", decoded["record"]))
    packet["records"] = records
    packet["records_omitted_within_scan"] = omitted
    packet["skipped_unreadable"] = skipped
    if records:
        packet["status"] = "found"
    return packet


def _record(row: sqlite3.Row) -> dict[str, object] | None:
    """One bounded record with its reference, or None for a row not carried.

    A None is not a verdict about history — the caller counts it as unreadable —
    and the checks are the ledger's own: bounded payload, digest match, and only
    the fields this packet promises, each held to a length.
    """

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
        anchor = payload.get("product_id")
        if not isinstance(anchor, str) or len(anchor) > 128:
            return None
        scopes: dict[str, str] = {}
        for key in ("goal_product_id", "goal"):
            value = payload.get(key, "")
            if not isinstance(value, str) or len(value) > 128:
                return None
            scopes[key] = value
        for key in ("skill", "result"):
            field = payload.get(key, "")
            if not isinstance(field, str) or len(field) > MAX_REASON_CHARS:
                return None
        reason = payload.get("reason", "")
        if not isinstance(reason, str):
            return None
        clipped_reason = (
            reason if len(reason) <= MAX_REASON_CHARS else reason[: MAX_REASON_CHARS - 1] + "…"
        )
        for key in ("event_id", "run_id"):
            reference = row[key]
            if reference is not None and (not isinstance(reference, str) or len(reference) > 128):
                return None
        when = row["observed_at_utc"]
        if not isinstance(when, str) or len(when) > 40:
            return None
    except (TypeError, ValueError, UnicodeError):
        return None
    return {
        "anchor": anchor,
        "goal_product_id": scopes["goal_product_id"],
        "goal": scopes["goal"],
        "record": {
            "event_id": row["event_id"],
            "event_position": row["position"],
            "run_id": row["run_id"],
            "observed_at_utc": row["observed_at_utc"],
            "source": row["source"],
            "trust_class": row["trust_class"],
            "skill": payload["skill"],
            "result": payload["result"],
            "reason": clipped_reason,
            "product_id": anchor,
        },
    }


def _scopes_the_goal(decoded: dict[str, object], product_id: str) -> bool:
    """Whether one decoded row is an episode of the asked-for goal.

    Three ways a row can belong: it made the goal's product, it was taken under
    the goal the mind recorded explicitly, or — for rows written before that
    field existed — it carries the goal label the mind wrote then
    (`hold_<product>`). The label is honored for exactly one product, so a
    near-miss cannot borrow another goal's history.
    """

    if decoded.get("anchor") == product_id or decoded.get("goal_product_id") == product_id:
        return True
    short = product_id.split(":", 1)[-1]
    return decoded.get("goal") == f"hold_{short}"
