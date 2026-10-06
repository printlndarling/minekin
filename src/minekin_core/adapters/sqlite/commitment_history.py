"""Unfinished commitments, read deterministically from the ledger that recorded them.

Slice B of `docs/memory-gateway-implementation-plan.md`: the resume packet must be
able to carry "未完成承诺及期限" through a structured query — an intention recorded
two sessions ago is remembered because it is a row, not because a model was asked
to remember it. The writer is the judging site (`commitment.judge_commitment_candidate`
plus the session layer's own event), so this reader never judges; it carries, with
references, and refuses to invent.

"Unfinished" is currently every recorded commitment, and the docstring says so on
purpose: nothing writes a completion yet, so a filter here would be an inference.
When completion exists it lands as its own event type beside `CommitmentRecorded`
and the filter arrives with it — history is never rewritten to make a list shorter.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_log import COMMITMENT_RECORDED
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.domain.errors import MinekinError

#: How many ledger rows one read may scan, and how many records one packet may carry.
#: Bounded like the sibling retrievers: a resume packet is a summary input, not an
#: archive, and the accounts say what the bound left out.
SCAN_LIMIT: int = 64
RECORD_LIMIT: int = 8
#: The longest commitment text a record carries forward. The writer already bounds
#: at `commitment.MAX_COMMITMENT_CHARS`; this is the reader's own ceiling for rows
#: that arrived another way, clipped with an ellipsis rather than dropped — the
#: goal-history lesson, applied before it bites.
MAX_TEXT_CARRY_CHARS: int = 240
MAX_DUE_CARRY_CHARS: int = 64
MAX_REF_CHARS: int = 128


def read_unfinished_commitments(
    database: Path,
    *,
    kin_id: str,
    limit: int = RECORD_LIMIT,
) -> dict[str, object]:
    """Recent commitments, newest first, with their citations and sources.

    The current run's own rows are included on purpose: a mind that re-reads its
    offer mid-run sees what it promised itself three steps ago, and the row's
    `run_id` is what tells it apart from an older session's.
    """

    packet: dict[str, object] = {
        "retriever_version": "commitments-v1",
        "status": "not_retrieved",
        "freshness": "historical",
        # The reading rule the offer's discipline is written against: a remembered
        # intention is not a current fact and not permission — recheck before acting.
        "reading_rule": "remembered_intent_revalidate",
        "scan_limit": SCAN_LIMIT,
        "record_limit": limit,
        "records_omitted_within_scan": 0,
        "skipped_unreadable": 0,
        "records": [],
    }
    if not database.is_file():
        packet["status"] = "ledger_missing"
        return packet
    try:
        connection = connect_reader(database)
        try:
            rows = connection.execute(
                "SELECT position,event_id,run_id,observed_at_utc,source,trust_class,"
                "substr(payload_json,1,4097) AS payload_json,payload_hash "
                "FROM event WHERE kin_id=? AND event_type=? "
                "ORDER BY position DESC LIMIT ?",
                (kin_id, COMMITMENT_RECORDED, SCAN_LIMIT),
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
        if len(records) >= limit:
            omitted += 1
            continue
        records.append(decoded)
    packet["records"] = records
    packet["records_omitted_within_scan"] = omitted
    packet["skipped_unreadable"] = skipped
    if records:
        packet["status"] = "found"
    return packet


def _record(row: sqlite3.Row) -> dict[str, object] | None:
    """One bounded record with its reference, or None for a row not carried.

    The checks are the ledger's own: bounded payload, digest match, and only the
    fields this packet promises, each held to a length. Free text is clipped with
    an ellipsis rather than rejected — a long intention is still an intention.
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
        fields: dict[str, str] = {}
        for key in ("text", "due", "evidence_ref", "observation_ref"):
            field = payload.get(key, "")
            if not isinstance(field, str):
                return None
            fields[key] = field
        if not fields["text"] or not fields["evidence_ref"]:
            return None
        carried_text = (
            fields["text"]
            if len(fields["text"]) <= MAX_TEXT_CARRY_CHARS
            else fields["text"][: MAX_TEXT_CARRY_CHARS - 1] + "…"
        )
        carried_due = (
            fields["due"]
            if len(fields["due"]) <= MAX_DUE_CARRY_CHARS
            else fields["due"][: MAX_DUE_CARRY_CHARS - 1] + "…"
        )
        for key in ("evidence_ref", "observation_ref"):
            if len(fields[key]) > MAX_REF_CHARS:
                return None
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
        "event_id": row["event_id"],
        "event_position": row["position"],
        "run_id": row["run_id"],
        "observed_at_utc": row["observed_at_utc"],
        "source": row["source"],
        "trust_class": row["trust_class"],
        "text": carried_text,
        "due": carried_due,
        "evidence_ref": fields["evidence_ref"],
        "observation_ref": fields["observation_ref"],
    }
