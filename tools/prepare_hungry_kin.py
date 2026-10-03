"""Prepare a local hunger fixture with an observation-only managed client.

The server marker remains test-only. Fresh HUD evidence comes from the ordinary
Bridge admission path; neither is a consume success or a model decision.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from minekin_core.adapters.launcher.orphans import Liveness
from minekin_core.adapters.launcher.server_profile import load_session_server_profile
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_log import (
    CLIENT_EXITED,
    INPUT_LEASE_GRANTED,
    PLAYER_STATE_OBSERVED,
    PROCESS_STARTED,
)
from minekin_core.cli.session import database_for, select_kin, stop_session
from minekin_core.cli.status import ObservedState, read_status
from minekin_core.config import data_root, kin_selector

KEEP_VALUES = frozenset(
    {
        "--profile",
        "--auto-bundle",
        "--max-bytes",
        "--server-profile",
        "--connection-timeout-seconds",
        "--handshake-timeout-seconds",
        "--identity-candidate",
    }
)
DROP_VALUES = frozenset(
    {
        "--skill-plan",
        "--skill-step-seconds",
        "--autonomous-steps",
        "--hold-forward-seconds",
        "--hold-use-seconds",
        "--hold-strafe",
        "--hold-at",
        "--look-yaw-degrees",
        "--look-pitch-degrees",
    }
)
DROP_FLAGS = frozenset({"--autonomous", "--hold-jump", "--hold-sneak"})


def observation_arguments(arguments: list[str]) -> list[str]:
    if arguments[:2] != ["session", "start"]:
        raise ValueError("Preparation requires a managed session start")
    result = arguments[:2]
    seen: set[str] = set()
    index = 2
    while index < len(arguments):
        flag = arguments[index]
        if flag in seen:
            raise ValueError(f"Repeated preparation argument: {flag}")
        seen.add(flag)
        if flag in DROP_FLAGS:
            index += 1
            continue
        if flag not in KEEP_VALUES | DROP_VALUES or index + 1 >= len(arguments):
            raise ValueError(f"Unsupported preparation argument: {flag}")
        value = arguments[index + 1]
        if value.startswith("--"):
            raise ValueError(f"Missing preparation argument value: {flag}")
        if flag in KEEP_VALUES:
            result.extend([flag, value])
        index += 2
    if "--server-profile" not in seen or len(seen & {"--profile", "--auto-bundle"}) != 1:
        raise ValueError("One bundle source and a controlled server profile are required")
    return result


def ready_hud(
    marker: dict[str, Any], player: str, row: dict[str, Any], *, now: datetime | None = None
) -> bool:
    if (
        marker.get("state") != "ready"
        or marker.get("player") != player
        or marker.get("effectClearConfirmed") is not True
        or marker.get("mealGivenConfirmed") is not True
        or type(marker.get("food")) is not int
        or not 0 <= marker["food"] <= 6
        or row.get("source") != "BRIDGE"
        or row.get("trust_class") != "BRIDGE_FILTERED"
    ):
        return False
    try:
        prepared = datetime.fromisoformat(marker["observedAt"])
        observed = datetime.fromisoformat(row["observed_at_utc"])
        payload = json.loads(row["payload_json"])
        health, food = payload["health"], payload["food"]
        return (
            prepared.utcoffset() is not None
            and observed.utcoffset() is not None
            and prepared <= observed
            and 0 <= ((now or datetime.now(UTC)) - observed).total_seconds() <= 10
            and isinstance(health, (int, float))
            and not isinstance(health, bool)
            and math.isfinite(health)
            and health > 0
            and type(food) is int
            and 0 <= food <= 6
        )
    except (ValueError, TypeError, KeyError, OverflowError):
        return False


def descendant_of(pid: int, parent: int) -> bool:
    """Bounded Linux ancestry proof for this tool's own Core child."""
    seen: set[int] = set()
    for _ in range(64):
        if pid == parent:
            return True
        if pid <= 1 or pid in seen:
            return False
        seen.add(pid)
        try:
            status = Path(f"/proc/{pid}/status").read_text()
            pid = int(
                next(line.split()[1] for line in status.splitlines() if line.startswith("PPid:"))
            )
        except (OSError, ValueError, StopIteration):
            return False
    return False


def prepare(directory: Path, player: str, arguments: list[str]) -> dict[str, Any]:
    if sys.platform != "linux":
        raise ValueError("The controlled Docker preparation requires Linux process ownership")
    observer = observation_arguments(arguments)
    profile = load_session_server_profile(
        Path(observer[observer.index("--server-profile") + 1]), minecraft_version="1.20.1"
    )
    if not profile.is_loopback or profile.auth_mode != "offline":
        raise ValueError("Only the controlled offline loopback fixture is accepted")
    if (
        not directory.is_absolute()
        or directory.parent.name != "server-runs"
        or not re.fullmatch(r"run-[0-9]+", directory.name)
        or not re.fullmatch(r"[A-Za-z0-9_]{3,16}", player)
        or (directory / "meal-ready.json").exists()
    ):
        raise ValueError("A fresh numbered server fixture and checked player are required")
    properties = dict(
        line.split("=", 1)
        for line in (directory / "server.properties").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    if (
        properties.get("server-ip") != profile.host
        or properties.get("server-port") != str(profile.port)
        or properties.get("online-mode") != "false"
        or properties.get("difficulty") not in {"easy", "normal", "hard"}
    ):
        raise ValueError("Saved fixture settings do not match the hunger test target")
    root, selector = data_root(), kin_selector()
    if read_status(root, kin_selector=selector).state is not ObservedState.IDLE:
        raise ValueError("The fixture Kin must be idle before preparation")
    database = database_for(root, select_kin(root, selector))
    with closing(connect_reader(database)) as connection:
        baseline = int(
            connection.execute("SELECT COALESCE(MAX(position),0) FROM event").fetchone()[0]
        )
    environment = dict(os.environ)
    environment.update(MINEKIN_MODEL_PROVIDER="off", MINEKIN_GOAL_PRODUCT="")
    report: dict[str, Any] = {"state": "preparing", "modelCalls": False, "inputRequested": False}
    report_path = directory / "meal-preparation.json"
    # Files belong to the numbered test server run, never an operator log target.
    with (
        (directory / "meal-observer.stdout").open("w") as stdout,
        (directory / "meal-observer.stderr").open("w") as stderr,
    ):
        process = subprocess.Popen(
            [sys.executable, "-m", "minekin_core", *observer],
            env=environment,
            stdout=stdout,
            stderr=stderr,
        )
        deadline = time.monotonic() + 150
        try:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Preparation observer exited before readiness")
                with closing(connect_reader(database)) as connection:
                    runs = connection.execute(
                        "SELECT run_id,session_id FROM event WHERE position>? AND event_type=?",
                        (baseline, PROCESS_STARTED),
                    ).fetchall()
                    if len(runs) > 1:
                        raise RuntimeError("Concurrent session detected; preparation refused")
                    if runs:
                        report.update(runId=runs[0]["run_id"], sessionId=runs[0]["session_id"])
                        rows = connection.execute(
                            "SELECT source,trust_class,observed_at_utc,payload_json FROM event "
                            "WHERE position>? AND run_id=? AND event_type=? "
                            "ORDER BY position DESC LIMIT 1",
                            (baseline, report["runId"], PLAYER_STATE_OBSERVED),
                        ).fetchall()
                        marker_path = directory / "meal-ready.json"
                        if rows and marker_path.is_file():
                            marker = json.loads(marker_path.read_text(encoding="utf-8"))
                            if ready_hud(marker, player, dict(rows[0])):
                                report.update(state="ready", readyAt=datetime.now(UTC).isoformat())
                                break
                time.sleep(0.1)
            else:
                raise TimeoutError("No fresh low-food HUD after confirmed meal preparation")
        finally:
            status = read_status(root, kin_selector=selector)
            current = [client for client in status.clients if client.liveness is not Liveness.GONE]
            if any(
                client.liveness is not Liveness.ALIVE
                or client.session_id != report.get("sessionId")
                or not descendant_of(client.pid, process.pid)
                for client in current
            ):
                report["cleanup"] = "OWNERSHIP_UNCONFIRMED"
                report_path.write_text(json.dumps(report), encoding="utf-8")
                raise RuntimeError(
                    "Observer cleanup ownership unavailable; no other client was stopped"
                )
            if current:
                stopped = stop_session(root, kin_selector=selector)
                report["stop"] = stopped.as_dict()
                if not stopped.outcome.complete or stopped.release.unconfirmed:
                    report["cleanup"] = "STOP_UNCONFIRMED"
            elif process.poll() is None:
                process.terminate()  # Our own Popen child, with no recorded live client.
            try:
                report["observerExitCode"] = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                report["cleanup"] = "CORE_EXIT_TIMEOUT"
                report_path.write_text(json.dumps(report), encoding="utf-8")
                raise RuntimeError("Observer Core did not finish within cleanup deadline") from None
            report_path.write_text(json.dumps(report), encoding="utf-8")
    if (
        report["observerExitCode"] != 0
        or report.get("cleanup") is not None
        or read_status(root, kin_selector=selector).state is not ObservedState.IDLE
    ):
        raise RuntimeError("Observation preparation did not finish cleanly")
    with closing(connect_reader(database)) as connection:
        held = connection.execute(
            "SELECT COUNT(*) FROM event WHERE run_id=? AND event_type=?",
            (report["runId"], INPUT_LEASE_GRANTED),
        ).fetchone()[0]
        ended = connection.execute(
            "SELECT payload_json FROM event WHERE run_id=? AND event_type=? "
            "ORDER BY position DESC LIMIT 1",
            (report["runId"], CLIENT_EXITED),
        ).fetchone()
    if held != 0 or ended is None or json.loads(ended[0]).get("outcome") != "STOPPED_ON_REQUEST":
        raise RuntimeError("Preparation did not prove an unheld, expected session end")
    report.update(inputLeaseEvents=held, outcome="STOPPED_ON_REQUEST")
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-directory", type=Path, required=True)
    parser.add_argument("--player", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    prepare(args.server_directory, args.player, command)
    print("Hungry fixture and fresh player HUD ready; observation-only session stopped")


if __name__ == "__main__":
    main()
