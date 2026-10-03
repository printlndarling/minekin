"""Preparation must join without controls and wait for post-clear player HUD."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from tools import prepare_hungry_kin as preparation
from tools.prepare_hungry_kin import observation_arguments, ready_hud

from minekin_core.adapters.launcher.orphans import Liveness
from minekin_core.cli.status import ObservedState

BASE = ["session", "start", "--profile", "bundle.json", "--server-profile", "server.json"]
NOW = datetime(2026, 10, 4, tzinfo=UTC)


def marker() -> dict[str, object]:
    return {
        "state": "ready",
        "player": "Kin",
        "food": 6,
        "effectClearConfirmed": True,
        "mealGivenConfirmed": True,
        "observedAt": (NOW - timedelta(seconds=2)).isoformat(),
    }


def row() -> dict[str, object]:
    return {
        "source": "BRIDGE",
        "trust_class": "BRIDGE_FILTERED",
        "observed_at_utc": (NOW - timedelta(seconds=1)).isoformat(),
        "payload_json": json.dumps({"health": 20, "food": 6}),
    }


def test_observer_removes_all_controls_and_preserves_join_arguments() -> None:
    assert observation_arguments(
        [
            *BASE,
            "--autonomous",
            "--autonomous-steps",
            "20",
            "--hold-jump",
            "--hold-sneak",
            "--skill-plan",
            "eat.json",
            "--skill-step-seconds",
            "5",
            "--hold-forward-seconds",
            "1",
            "--hold-use-seconds",
            "1",
            "--hold-strafe",
            "-1",
            "--hold-at",
            "playable",
            "--look-yaw-degrees",
            "90",
            "--look-pitch-degrees",
            "10",
            "--handshake-timeout-seconds",
            "60",
        ]
    ) == [*BASE, "--handshake-timeout-seconds", "60"]


@pytest.mark.parametrize(
    "arguments",
    [
        ["session", "stop"],
        [*BASE, "--unknown"],
        [*BASE, "--skill-plan"],
        [*BASE, "--profile", "other.json"],
        [*BASE, "--auto-bundle", "registry.json"],
        [*BASE, "--hold-forward-seconds", "--autonomous"],
        ["session", "start", "--profile", "bundle.json"],
    ],
)
def test_unrecognized_or_ambiguous_start_is_refused(arguments: list[str]) -> None:
    with pytest.raises(ValueError):
        observation_arguments(arguments)


def test_only_fresh_post_preparation_hud_is_ready() -> None:
    assert ready_hud(marker(), "Kin", row(), now=NOW)
    old = row()
    old["observed_at_utc"] = (NOW - timedelta(seconds=3)).isoformat()
    assert not ready_hud(marker(), "Kin", old, now=NOW)
    assert not ready_hud(marker(), "Kin", row(), now=NOW + timedelta(seconds=11))
    assert not ready_hud(marker(), "Kin", row(), now=NOW - timedelta(seconds=2))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("state", "preparing"),
        ("player", "OtherKin"),
        ("food", True),
        ("food", 7),
        ("effectClearConfirmed", False),
        ("mealGivenConfirmed", False),
        ("observedAt", "invalid"),
        ("observedAt", "2026-10-04T00:00:00"),
    ],
)
def test_marker_is_not_enough_without_matching_confirmations(key: str, value: object) -> None:
    invalid = marker()
    invalid[key] = value
    assert not ready_hud(invalid, "Kin", row(), now=NOW)


@pytest.mark.parametrize(
    "payload",
    [
        {"health": 0, "food": 6},
        {"health": True, "food": 6},
        {"health": float("nan"), "food": 6},
        {"health": 20, "food": 7},
        {"health": 20, "food": True},
        {"health": 20, "food": 6.0},
        {"health": 20, "food": -1},
        {},
        [],
    ],
)
def test_invalid_or_unready_body_is_refused(payload: object) -> None:
    invalid = row()
    invalid["payload_json"] = json.dumps(payload)
    assert not ready_hud(marker(), "Kin", invalid, now=NOW)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("source", "CORE"),
        ("trust_class", "UNTRUSTED"),
        ("payload_json", "broken"),
    ],
)
def test_non_player_or_broken_evidence_is_refused(key: str, value: object) -> None:
    invalid = row()
    invalid[key] = value
    assert not ready_hud(marker(), "Kin", invalid, now=NOW)


@pytest.mark.parametrize("owned", [True, False])
def test_preparation_stops_only_its_observer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owned: bool
) -> None:
    directory = tmp_path / "server-runs" / "run-1"
    directory.mkdir(parents=True)
    (directory / "server.properties").write_text(
        "server-ip=127.0.0.1\nserver-port=25566\nonline-mode=false\ndifficulty=easy\n"
    )
    database = tmp_path / "ledger.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE event(position INTEGER PRIMARY KEY,event_type TEXT,run_id TEXT,"
            "session_id TEXT,source TEXT,trust_class TEXT,observed_at_utc TEXT,payload_json TEXT)"
        )
    state = {"started": False, "stopped": False}

    class FakeProcess:
        pid = 42

        def __init__(self, argv: list[str], **kwargs: object) -> None:
            assert argv[3:] == BASE
            assert cast(dict[str, str], kwargs["env"])["MINEKIN_MODEL_PROVIDER"] == "off"
            state["started"] = True
            timestamp = datetime.now(UTC).isoformat()
            prepared = marker()
            prepared["observedAt"] = timestamp
            (directory / "meal-ready.json").write_text(json.dumps(prepared))
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "INSERT INTO event VALUES(1,?, 'run', 'session', 'CORE','CORE', ?, '{}')",
                    (preparation.PROCESS_STARTED, timestamp),
                )
                connection.execute(
                    "INSERT INTO event VALUES(2,?, 'run', 'session', "
                    "'BRIDGE','BRIDGE_FILTERED', ?, ?)",
                    (
                        preparation.PLAYER_STATE_OBSERVED,
                        timestamp,
                        json.dumps({"health": 20, "food": 6}),
                    ),
                )

        def poll(self) -> int | None:
            return 0 if state["stopped"] else None

        def wait(self, *, timeout: int) -> int:
            assert timeout == 30 and state["stopped"]
            return 0

    def status(*args: object, **kwargs: object) -> SimpleNamespace:
        active = state["started"] and not state["stopped"]
        return SimpleNamespace(
            state=ObservedState.RUNNING if active else ObservedState.IDLE,
            clients=[SimpleNamespace(pid=43, session_id="session", liveness=Liveness.ALIVE)]
            if active
            else [],
        )

    def stop(*args: object, **kwargs: object) -> SimpleNamespace:
        state["stopped"] = True
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO event VALUES(3,?, 'run', 'session', 'CORE','CORE', ?, ?)",
                (
                    preparation.CLIENT_EXITED,
                    datetime.now(UTC).isoformat(),
                    json.dumps({"outcome": "STOPPED_ON_REQUEST"}),
                ),
            )
        return SimpleNamespace(
            outcome=SimpleNamespace(complete=True),
            release=SimpleNamespace(unconfirmed=()),
            as_dict=lambda: {"status": "stopped"},
        )

    def profile(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(is_loopback=True, auth_mode="offline", host="127.0.0.1", port=25566)

    def select(*args: object) -> str:
        return "Kin"

    def database_path(*args: object) -> Path:
        return database

    def descendant(*args: object) -> bool:
        return owned

    def reader(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection

    monkeypatch.setattr(preparation.sys, "platform", "linux")
    monkeypatch.setattr(
        preparation,
        "load_session_server_profile",
        profile,
    )
    monkeypatch.setattr(preparation, "data_root", lambda: tmp_path)
    monkeypatch.setattr(preparation, "kin_selector", lambda: "Kin")
    monkeypatch.setattr(preparation, "select_kin", select)
    monkeypatch.setattr(preparation, "database_for", database_path)
    monkeypatch.setattr(preparation, "connect_reader", reader)
    monkeypatch.setattr(preparation, "read_status", status)
    monkeypatch.setattr(preparation, "stop_session", stop)
    monkeypatch.setattr(preparation, "descendant_of", descendant)
    monkeypatch.setattr(preparation.subprocess, "Popen", FakeProcess)
    if owned:
        result = preparation.prepare(directory, "Kin", [*BASE, "--autonomous"])
        assert result["state"] == "ready" and result["observerExitCode"] == 0
        assert state["stopped"]
    else:
        with pytest.raises(RuntimeError, match="ownership unavailable"):
            preparation.prepare(directory, "Kin", BASE)
        assert not state["stopped"]
