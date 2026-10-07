"""Actor-anchored recall: what one account said before, by its stable key.

The account key landed with the chat card (`PlayerChatObserved.sender_id`);
this is its first deterministic reader — the memory contract's rule that people
are keyed by stable account identity while display names are only attributes,
so similar nicknames never merge. Matching is exact on the key and never falls
back to the name: two people who share a display name have two histories, a
renamed account keeps one history, and a line that carried no key belongs to
nobody stable and is never borrowed into someone's. Like the sibling
retrievers the packet carries references and bounded text, skips rows that do
not survive their own digest, and states its bounds rather than silently
truncating.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Final, cast

from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_log import PLAYER_CHAT_OBSERVED
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.domain.errors import MinekinError

#: How many ledger rows one recall may scan, and how many records one packet may
#: carry. Bounded like the sibling retrievers: a decision input, not an archive.
SCAN_LIMIT: Final[int] = 64
RECORD_LIMIT: Final[int] = 8
#: The longest line a record carries forward; the writer caps at the same number,
#: and a pathological row is clipped with an ellipsis rather than dropped.
MAX_TEXT_CARRY_CHARS: Final[int] = 256
#: The longest sender name or account key a record carries; both are re-checked
#: where they were written, and a row past either bound is skipped as unreadable
#: rather than carried clipped — an attribution is exact or it is nothing.
MAX_SENDER_CHARS: Final[int] = 64


def recall_actor_history(
    database: Path,
    *,
    kin_id: str,
    sender_id: str,
    exclude_run_id: str = "",
    limit: int = RECORD_LIMIT,
) -> dict[str, object]:
    """One account's recent lines, newest first, with their sources.

    The current run's own rows are included by default: "what have we been
    saying" reads the conversation so far, and a caller that wants only earlier
    sessions passes `exclude_run_id`.
    """

    packet: dict[str, object] = {
        "retriever_version": "actor-history-v1",
        "status": "not_retrieved",
        "freshness": "historical",
        "anchor": {"kind": "actor_key", "value": sender_id},
        "scan_limit": SCAN_LIMIT,
        "record_limit": limit,
        "records_omitted_within_scan": 0,
        "skipped_unreadable": 0,
        "records": [],
    }
    if not sender_id:
        # No key is no anchor: a recall must not be asked for "whoever shares a
        # name with nobody in particular".
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
                (kin_id, exclude_run_id, PLAYER_CHAT_OBSERVED, SCAN_LIMIT),
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
        if decoded["sender_id"] != sender_id:
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

    The checks are the ledger's own: bounded payload, digest match, and only the
    fields this packet promises, each held to a length. The key itself is
    matched exactly by the caller, never normalised.
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
        for key in ("sender", "sender_id", "text"):
            field = payload.get(key, "")
            if not isinstance(field, str):
                return None
            fields[key] = field
        if not fields["sender"]:
            # A nameless row has no attribution to carry; a KEYLESS row is
            # readable and simply not this actor's — the caller's exact match
            # classifies it as omitted, not unreadable.
            return None
        if len(fields["sender"]) > MAX_SENDER_CHARS or len(fields["sender_id"]) > MAX_SENDER_CHARS:
            return None
        carried_text = (
            fields["text"]
            if len(fields["text"]) <= MAX_TEXT_CARRY_CHARS
            else fields["text"][: MAX_TEXT_CARRY_CHARS - 1] + "…"
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
        "sender_id": fields["sender_id"],
        "record": {
            "event_id": row["event_id"],
            "event_position": row["position"],
            "run_id": row["run_id"],
            "observed_at_utc": row["observed_at_utc"],
            "source": row["source"],
            "trust_class": row["trust_class"],
            "sender": fields["sender"],
            "text": carried_text,
        },
    }
