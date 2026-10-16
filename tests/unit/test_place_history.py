"""World-scoped place recall reads the ledger's own anchors and never guesses a world."""

from __future__ import annotations

import itertools
import json
import sqlite3
from pathlib import Path
from typing import cast

import pytest

from minekin_core.adapters.sqlite.connection import migrate
from minekin_core.adapters.sqlite.place_history import (
    RECORD_LIMIT,
    recall_place_history,
)
from minekin_core.adapters.sqlite.session_log import AUTH_POLICY_FROZEN, SKILL_STEP_RECORDED
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.cli.session import mind_for_run

WORLD = "local-1201"
_ids = itertools.count(1)


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "kin.sqlite3"
    with sqlite3.connect(path, isolation_level=None) as connection:
        migrate(connection)
    return path


def _insert(
    database: Path,
    *,
    event_type: str,
    run_id: str,
    payload: dict[str, JsonValue],
    kin_id: str = "kin-one",
    source: str = "CORE",
    trust_class: str = "CORE",
    corrupt: bool = False,
) -> None:
    digest = "0" * 64 if corrupt else payload_digest(payload)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO event(event_id,event_type,schema_version,kin_id,run_id,sequence,"
            "correlation_id,monotonic_ns,observed_at_utc,source,trust_class,"
            "payload_json,payload_hash) "
            "VALUES (?, ?, 1, ?, ?, '1', 'test', 0, "
            "'2026-10-03T00:00:00+00:00', ?, ?, ?, ?)",
            (
                f"event-{next(_ids)}",
                event_type,
                kin_id,
                run_id,
                source,
                trust_class,
                json.dumps(payload),
                digest,
            ),
        )


def _world(database: Path, run_id: str, profile: str = WORLD) -> None:
    _insert(
        database,
        event_type=AUTH_POLICY_FROZEN,
        run_id=run_id,
        payload={"server_profile_id": profile, "server_profile_revision": "1"},
    )


def _step(
    database: Path,
    run_id: str,
    place: object,
    *,
    skill: str = "break_seen_block",
    source: str = "CORE",
    trust_class: str = "CORE",
    corrupt: bool = False,
) -> None:
    payload = cast(
        "dict[str, JsonValue]",
        {"skill": skill, "result": "CONFIRMED", "reason": "", "place": place},
    )
    _insert(
        database,
        event_type=SKILL_STEP_RECORDED,
        run_id=run_id,
        payload=payload,
        source=source,
        trust_class=trust_class,
        corrupt=corrupt,
    )


def _places(packet: dict[str, object]) -> list[object]:
    return [record["place"] for record in cast("list[dict[str, object]]", packet["records"])]


def test_places_from_this_world_come_back_newest_first_with_their_sources(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    _world(database, "run-a")
    _step(database, "run-a", {"x": 1, "y": 64, "z": 2})
    _step(database, "run-a", {"x": 5, "y": 64, "z": 9}, skill="collect_dropped")
    before = database.read_bytes()

    packet = recall_place_history(database, kin_id="kin-one", current_server_profile_id=WORLD)

    assert packet["status"] == "found"
    assert packet["current_world_applicability"] == "same_profile"
    assert packet["freshness"] == "historical"
    assert _places(packet) == [{"x": 5, "y": 64, "z": 9}, {"x": 1, "y": 64, "z": 2}]
    first = cast("list[dict[str, object]]", packet["records"])[0]
    assert first["skill"] == "collect_dropped"
    assert first["run_id"] == "run-a"
    assert first["server_profile_id"] == WORLD
    assert (first["source"], first["trust_class"]) == ("CORE", "CORE")
    # Reading is all it does.
    assert database.read_bytes() == before


def test_a_coordinate_from_another_world_or_an_unnamed_one_is_never_carried(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    _world(database, "here")
    _world(database, "elsewhere", profile="friends-server")
    _step(database, "here", {"x": 1, "y": 64, "z": 1})
    _step(database, "elsewhere", {"x": 2, "y": 64, "z": 2})
    _step(database, "no-world", {"x": 3, "y": 64, "z": 3})

    packet = recall_place_history(database, kin_id="kin-one", current_server_profile_id=WORLD)
    assert _places(packet) == [{"x": 1, "y": 64, "z": 1}]
    assert packet["records_from_other_worlds"] == 1
    assert packet["records_without_world"] == 1

    elsewhere = recall_place_history(
        database, kin_id="kin-one", current_server_profile_id="friends-server"
    )
    assert _places(elsewhere) == [{"x": 2, "y": 64, "z": 2}]


@pytest.mark.parametrize("current", ["", "Not A Profile!"])
def test_a_run_that_names_no_world_gets_no_coordinates_at_all(tmp_path: Path, current: str) -> None:
    database = _database(tmp_path)
    _world(database, "run-a")
    _step(database, "run-a", {"x": 1, "y": 64, "z": 1})
    packet = recall_place_history(database, kin_id="kin-one", current_server_profile_id=current)
    assert packet["status"] == "world_unknown"
    assert packet["current_world_applicability"] == "unknown"
    assert packet["records"] == []


def test_one_spot_is_one_place_and_the_bound_says_what_it_left_out(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _world(database, "run-a")
    _step(database, "run-a", {"x": 0, "y": 64, "z": 0})
    for x in range(RECORD_LIMIT + 2):
        _step(database, "run-a", {"x": x, "y": 64, "z": 0})
    packet = recall_place_history(database, kin_id="kin-one", current_server_profile_id=WORLD)
    places = _places(packet)
    assert len(places) == RECORD_LIMIT
    assert places[0] == {"x": RECORD_LIMIT + 1, "y": 64, "z": 0}
    assert len({json.dumps(place, sort_keys=True) for place in places}) == RECORD_LIMIT
    # Two beyond the bound plus the older visit to x=0.
    assert packet["records_omitted_within_scan"] == 3


def test_forged_corrupt_or_malformed_rows_are_skipped_and_counted(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _world(database, "run-a")
    _step(database, "run-a", {"x": 1, "y": 64, "z": 1})
    _step(database, "run-a", {"x": 2, "y": 64, "z": 2}, corrupt=True)
    _step(database, "run-a", {"x": 3, "y": 64, "z": 3}, source="BRIDGE")
    _step(database, "run-a", {"x": 4, "y": 64, "z": 4}, trust_class="MODEL_SUGGESTED")
    _step(database, "run-a", {"x": True, "y": 64, "z": 5})
    _step(database, "run-a", {"x": 6, "y": 64})
    _step(database, "run-a", {"x": 7.5, "y": 64, "z": 7})
    _step(database, "run-a", {"x": 40_000_000, "y": 64, "z": 8})
    # An honest absence is neither a place nor an unreadable row.
    _step(database, "run-a", None)
    packet = recall_place_history(database, kin_id="kin-one", current_server_profile_id=WORLD)
    assert _places(packet) == [{"x": 1, "y": 64, "z": 1}]
    assert packet["skipped_unreadable"] == 7


def test_the_current_run_and_other_kins_are_not_history(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _world(database, "now")
    _step(database, "now", {"x": 1, "y": 64, "z": 1})
    _insert(
        database,
        event_type=SKILL_STEP_RECORDED,
        run_id="now",
        kin_id="kin-two",
        payload={"skill": "turn_to", "result": "CONFIRMED", "place": {"x": 9, "y": 9, "z": 9}},
    )
    packet = recall_place_history(
        database, kin_id="kin-one", current_server_profile_id=WORLD, exclude_run_id="now"
    )
    assert packet["status"] == "not_retrieved"
    assert packet["records"] == []


def test_missing_ledger_reads_as_missing(tmp_path: Path) -> None:
    packet = recall_place_history(
        tmp_path / "absent.sqlite3", kin_id="kin-one", current_server_profile_id=WORLD
    )
    assert packet["status"] == "ledger_missing"


def test_the_mind_resumes_with_the_place_packet_for_the_world_it_was_told(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    _world(database, "run-a")
    _step(database, "run-a", {"x": 1, "y": 64, "z": 1})
    told = mind_for_run("kin-one", {}, kin_dir=database.parent, current_server_profile_id=WORLD)
    assert told.session_history["place_history"] == recall_place_history(
        database, kin_id="kin-one", current_server_profile_id=WORLD
    )
    untold = mind_for_run("kin-one", {}, kin_dir=database.parent)
    place_packet = cast("dict[str, object]", untold.session_history["place_history"])
    assert place_packet["status"] == "world_unknown"


def test_the_model_is_told_a_remembered_place_is_memory_not_a_walk_target() -> None:
    from minekin_core.adapters.model.openai_compatible import SYSTEM_PROMPT

    assert "session_history.place_history" in SYSTEM_PROMPT
    assert "it never widens what move_to may name" in SYSTEM_PROMPT
