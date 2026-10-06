"""Goal-anchored recall reads the ledger's own anchors and never invents a story."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

from minekin_core.adapters.sqlite.connection import migrate
from minekin_core.adapters.sqlite.goal_history import (
    MAX_REASON_CHARS,
    RECORD_LIMIT,
    SCAN_LIMIT,
    recall_goal_history,
)
from minekin_core.adapters.sqlite.session_log import SKILL_STEP_RECORDED
from minekin_core.application.ports.event_store import JsonValue, payload_digest


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "kin.sqlite3"
    with sqlite3.connect(path, isolation_level=None) as connection:
        migrate(connection)
    return path


def _step(
    database: Path,
    *,
    position_hint: int,
    run_id: str = "old-run",
    kin_id: str = "kin-one",
    product_id: str = "minecraft:wooden_pickaxe",
    skill: str = "craft_take_result",
    result: str = "CONFIRMED",
    reason: str = "",
    goal_product_id: str = "",
    goal: str = "",
    corrupt: bool = False,
) -> None:
    del position_hint
    payload: dict[str, JsonValue] = {
        "skill": skill,
        "result": result,
        "reason": reason,
        "product_id": product_id,
        "goal_product_id": goal_product_id,
        "goal": goal,
    }
    digest = "0" * 64 if corrupt else payload_digest(payload)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO event(event_id,event_type,schema_version,kin_id,run_id,sequence,"
            "correlation_id,monotonic_ns,observed_at_utc,source,trust_class,"
            "payload_json,payload_hash) "
            "VALUES (?, ?, 1, ?, ?, '1', 'test', 0, "
            "'2026-10-03T00:00:00+00:00', 'CORE', 'CORE', ?, ?)",
            (
                f"event-{abs(hash((run_id, skill, result, reason))) % 10**12}",
                SKILL_STEP_RECORDED,
                kin_id,
                run_id,
                json.dumps(payload),
                digest,
            ),
        )


def test_recall_returns_anchored_steps_newest_first_with_sources(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _step(database, position_hint=1, run_id="run-a", skill="break_seen_block", result="CONFIRMED")
    _step(database, position_hint=2, run_id="run-b", result="INTERRUPTED", reason="PLAYER_DEAD")
    _step(database, position_hint=3, run_id="run-c", product_id="minecraft:stick")

    packet = recall_goal_history(database, kin_id="kin-one", product_id="minecraft:wooden_pickaxe")

    assert packet["status"] == "found"
    records = cast("list[dict[str, object]]", packet["records"])
    # Newest first: run-b's interruption sits above run-a's break, and the
    # stick's step is not this anchor's business.
    assert [record["run_id"] for record in records] == ["run-b", "run-a"]
    assert records[0]["result"] == "INTERRUPTED"
    assert records[0]["reason"] == "PLAYER_DEAD"
    assert records[0]["source"] == "CORE"
    assert records[0]["trust_class"] == "CORE"
    assert packet["records_omitted_within_scan"] == 1


def test_the_anchor_scopes_the_goal_not_only_its_final_product(tmp_path: Path) -> None:
    """A run toward the pickaxe spends its steps on logs, planks and the table —
    the goal's episodes are those steps, not only a pickaxe craft that may not
    exist yet. Scoped by the goal the step was taken under, the recall answers
    "what have I tried toward this goal"; steps of other runs answer only for
    their own goals.
    """

    database = _database(tmp_path)
    _step(
        database,
        position_hint=1,
        run_id="run-toward",
        product_id="minecraft:oak_planks",
        goal_product_id="minecraft:wooden_pickaxe",
    )
    _step(
        database,
        position_hint=2,
        run_id="run-other",
        product_id="minecraft:oak_planks",
        goal_product_id="minecraft:oak_planks",
    )

    packet = recall_goal_history(database, kin_id="kin-one", product_id="minecraft:wooden_pickaxe")

    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["run-toward"]
    assert records[0]["product_id"] == "minecraft:oak_planks"


def test_a_goal_label_written_before_the_explicit_field_still_matches(tmp_path: Path) -> None:
    """Rows written before the explicit goal field exist could only name their
    goal the way the mind wrote it then (`hold_<product>`); the reader honors
    that label for exactly one product, so the recall is not blind to its own
    near past."""

    database = _database(tmp_path)
    _step(
        database,
        position_hint=1,
        run_id="run-legacy",
        product_id="minecraft:oak_planks",
        goal="hold_wooden_pickaxe",
    )
    _step(
        database,
        position_hint=2,
        run_id="run-other-goal",
        product_id="minecraft:stick",
        goal="hold_wooden_sword",
    )

    packet = recall_goal_history(database, kin_id="kin-one", product_id="minecraft:wooden_pickaxe")

    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["run-legacy"]


def test_recall_concludes_not_retrieved_without_an_anchor_or_a_hit(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _step(database, position_hint=1, product_id="minecraft:stick")

    no_anchor = recall_goal_history(database, kin_id="kin-one", product_id="")
    assert no_anchor["status"] == "no_anchor"
    assert no_anchor["records"] == []

    no_hit = recall_goal_history(database, kin_id="kin-one", product_id="minecraft:wooden_pickaxe")
    assert no_hit["status"] == "not_retrieved"
    assert no_hit["records"] == []

    missing = recall_goal_history(
        tmp_path / "absent.sqlite3", kin_id="kin-one", product_id="minecraft:wooden_pickaxe"
    )
    assert missing["status"] == "ledger_missing"


def test_unreadable_rows_are_skipped_and_counted_not_trusted(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _step(database, position_hint=1, run_id="run-bad", corrupt=True)
    _step(database, position_hint=2, run_id="run-good")

    packet = recall_goal_history(database, kin_id="kin-one", product_id="minecraft:wooden_pickaxe")

    assert packet["status"] == "found"
    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["run-good"]
    assert packet["skipped_unreadable"] == 1


def test_recall_is_scoped_by_kin_and_excludes_the_current_run(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _step(database, position_hint=1, run_id="other-kin", kin_id="kin-two")
    _step(database, position_hint=2, run_id="this-run")
    _step(database, position_hint=3, run_id="old-run")

    packet = recall_goal_history(
        database,
        kin_id="kin-one",
        product_id="minecraft:wooden_pickaxe",
        exclude_run_id="this-run",
    )

    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["old-run"]


def test_the_record_bound_is_stated_and_never_silently_exceeded(tmp_path: Path) -> None:
    database = _database(tmp_path)
    for index in range(RECORD_LIMIT + 3):
        _step(database, position_hint=index, run_id=f"run-{index:02d}")

    packet = recall_goal_history(
        database, kin_id="kin-one", product_id="minecraft:wooden_pickaxe", limit=RECORD_LIMIT
    )

    records = cast("list[dict[str, object]]", packet["records"])
    assert len(records) == RECORD_LIMIT
    assert packet["records_omitted_within_scan"] == 3
    assert packet["scan_limit"] == SCAN_LIMIT


def test_a_reason_past_the_bound_is_carried_clipped(tmp_path: Path) -> None:
    """A long reason is clipped, not dropped.

    Found live: the first recall scan skipped 45 rows as "unreadable" because
    their free-text reasons exceeded the bound — real history lost to a display
    limit. The bound still holds (the reader caps the text), but the row is
    carried with an ellipsis and its references, so a reader can find the full
    row by position.
    """

    database = _database(tmp_path)
    _step(database, position_hint=1, run_id="run-loud", reason="x" * (MAX_REASON_CHARS + 100))

    packet = recall_goal_history(database, kin_id="kin-one", product_id="minecraft:wooden_pickaxe")

    records = cast("list[dict[str, object]]", packet["records"])
    assert [record["run_id"] for record in records] == ["run-loud"]
    reason = records[0]["reason"]
    assert isinstance(reason, str)
    assert len(reason) == MAX_REASON_CHARS
    assert reason.endswith("…")
    assert packet["skipped_unreadable"] == 0
