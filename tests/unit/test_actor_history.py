"""Actor-anchored recall reads one account's own lines and never merges by name.

The account key landed with the chat card; this is its first deterministic
reader — the memory contract's rule that people are keyed by stable account
identity, display names are only attributes, and similar nicknames must never
merge, as a query. Matching is exact on the key: two people who share a display
name have two histories, a renamed account keeps one, and a line that carried
no key belongs to nobody stable and is never borrowed into someone's history.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

from minekin_core.adapters.sqlite.actor_history import (
    RECORD_LIMIT,
    SCAN_LIMIT,
    recall_actor_history,
)
from minekin_core.adapters.sqlite.connection import migrate
from minekin_core.adapters.sqlite.session_log import PLAYER_CHAT_OBSERVED
from minekin_core.application.ports.event_store import JsonValue, payload_digest

KEY = "f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2"


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "kin.sqlite3"
    with sqlite3.connect(path, isolation_level=None) as connection:
        migrate(connection)
    return path


def _chat(
    database: Path,
    *,
    kin_id: str = "kin-one",
    run_id: str = "run-a",
    sender: str = "Alex",
    sender_id: str = KEY,
    text: str = "hello",
    tick: int = 100,
    corrupt: bool = False,
) -> None:
    payload: dict[str, JsonValue] = {
        "sender": sender,
        "sender_id": sender_id,
        "text": text,
        "game_tick": tick,
    }
    digest = "0" * 64 if corrupt else payload_digest(payload)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO event(event_id,event_type,schema_version,kin_id,run_id,sequence,"
            "correlation_id,monotonic_ns,observed_at_utc,source,trust_class,"
            "payload_json,payload_hash) "
            "VALUES (?, ?, 1, ?, ?, '1', 'test', 0, "
            "'2026-10-07T00:00:00+00:00', 'BRIDGE', 'PLAYER_CHAT', ?, ?)",
            (
                f"event-{abs(hash((run_id, sender, text, tick))) % 10**12}",
                PLAYER_CHAT_OBSERVED,
                kin_id,
                run_id,
                json.dumps(payload),
                digest,
            ),
        )


def test_recall_returns_the_accounts_own_lines_newest_first(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _chat(database, run_id="run-old", text="first visit", tick=90)
    _chat(database, run_id="run-new", text="i am back", tick=200)

    packet = recall_actor_history(database, kin_id="kin-one", sender_id=KEY)

    assert packet["status"] == "found"
    assert packet["retriever_version"] == "actor-history-v1"
    assert packet["anchor"] == {"kind": "actor_key", "value": KEY}
    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["run-new", "run-old"]
    assert records[0]["text"] == "i am back"
    assert records[0]["sender"] == "Alex"
    assert records[0]["source"] == "BRIDGE"
    assert records[0]["trust_class"] == "PLAYER_CHAT"


def test_two_people_sharing_a_name_have_two_histories(tmp_path: Path) -> None:
    """The whole point of the key: same display name, different accounts, and a
    renamed account keeps its own history — names are never the join."""

    database = _database(tmp_path)
    other_key = "11111111-2222-4333-8444-555555555555"
    _chat(database, sender="Alex", sender_id=KEY, text="mine is the cave")
    _chat(database, sender="Alex", sender_id=other_key, text="mine is the hill")

    packet = recall_actor_history(database, kin_id="kin-one", sender_id=KEY)

    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["text"] for record in records] == ["mine is the cave"]


def test_a_line_without_a_key_never_joins_a_keyed_history(tmp_path: Path) -> None:
    """A keyless line belongs to nobody stable; it is not borrowed into the
    history of whoever happens to share its name."""

    database = _database(tmp_path)
    _chat(database, sender_id="", sender="Alex", text="who am i")
    _chat(database, sender_id=KEY, text="keyed")

    packet = recall_actor_history(database, kin_id="kin-one", sender_id=KEY)

    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["text"] for record in records] == ["keyed"]


def test_no_key_no_hit_and_no_ledger_all_read_as_themselves(tmp_path: Path) -> None:
    database = _database(tmp_path)

    no_anchor = recall_actor_history(database, kin_id="kin-one", sender_id="")
    assert no_anchor["status"] == "no_anchor"
    assert no_anchor["records"] == []

    no_hit = recall_actor_history(database, kin_id="kin-one", sender_id=KEY)
    assert no_hit["status"] == "not_retrieved"
    assert no_hit["records"] == []

    missing = recall_actor_history(tmp_path / "absent.sqlite3", kin_id="kin-one", sender_id=KEY)
    assert missing["status"] == "ledger_missing"


def test_unreadable_rows_are_skipped_and_counted_and_bounds_are_stated(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _chat(database, run_id="run-bad", corrupt=True)
    for index in range(RECORD_LIMIT + 2):
        _chat(database, run_id=f"run-{index:02d}", text=f"line {index}")

    packet = recall_actor_history(database, kin_id="kin-one", sender_id=KEY, limit=RECORD_LIMIT)

    records = cast("list[dict[str, object]]", packet["records"])
    assert len(records) == RECORD_LIMIT
    assert packet["skipped_unreadable"] == 1
    assert packet["records_omitted_within_scan"] == 2
    assert packet["scan_limit"] == SCAN_LIMIT


def test_the_recall_is_scoped_by_kin_and_can_exclude_a_run(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _chat(database, kin_id="kin-two", run_id="other-kin", text="not ours")
    _chat(database, run_id="this-run", text="now")
    _chat(database, run_id="old-run", text="then")

    packet = recall_actor_history(
        database, kin_id="kin-one", sender_id=KEY, exclude_run_id="this-run"
    )

    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["old-run"]
