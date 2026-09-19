"""The test server runner must preserve the frozen isolation boundary."""

from __future__ import annotations

import importlib
import json
import signal
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest

from minekin_core.adapters.launcher.server_profile import ServerProfile, load_server_profile
from minekin_core.domain.offline_identity import offline_player_uuid

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/run_controlled_server.py"


class _Runner(Protocol):
    PROFILE: Path

    def properties_for(self, profile: ServerProfile, *, level_seed: str) -> dict[str, str]: ...

    def write_configuration(
        self,
        directory: Path,
        properties: dict[str, str],
        *,
        allowed_players: tuple[str, ...],
    ) -> None: ...

    def verify_jar(self, path: Path) -> None: ...

    def summon_command(self, entity_type: str) -> str: ...

    def main(self) -> int: ...

    def request_clean_stop(self, signum: int, frame: object) -> None: ...


def _load_runner() -> _Runner:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        module: ModuleType = importlib.import_module("tools.run_controlled_server")
    finally:
        sys.path.pop(0)
    return cast(_Runner, module)


RUNNER = _load_runner()


def test_server_properties_are_private_vanilla_survival() -> None:
    properties = RUNNER.properties_for(load_server_profile(RUNNER.PROFILE), level_seed="fixed-seed")

    assert properties["server-ip"] == "127.0.0.1"
    assert properties["online-mode"] == "false"
    assert properties["white-list"] == "true"
    assert properties["enforce-whitelist"] == "true"
    assert properties["gamemode"] == "survival"
    assert properties["force-gamemode"] == "true"
    assert properties["difficulty"] == "normal"
    assert properties["pvp"] == "true"
    assert properties["enable-rcon"] == "false"
    assert properties["enable-query"] == "false"
    assert properties["enable-command-block"] == "false"
    assert properties["broadcast-console-to-ops"] == "false"
    assert properties["level-seed"] == "fixed-seed"
    # A domain exists to be connected to, and vanilla's default of 60 seconds
    # pauses it while it waits — a paused server stops processing connections.
    assert properties["pause-when-empty-seconds"] == "0"


def test_configuration_whitelists_only_named_offline_players(tmp_path: Path) -> None:
    directory = tmp_path / "run"

    RUNNER.write_configuration(
        directory,
        RUNNER.properties_for(load_server_profile(RUNNER.PROFILE), level_seed="fixed-seed"),
        allowed_players=("Kin_One", "Fixture2", "Kin_One"),
    )

    whitelist = json.loads((directory / "whitelist.json").read_text(encoding="utf-8"))
    assert whitelist == [
        {"uuid": str(offline_player_uuid("Fixture2")), "name": "Fixture2"},
        {"uuid": str(offline_player_uuid("Kin_One")), "name": "Kin_One"},
    ]
    assert (directory / "eula.txt").read_text(encoding="utf-8").endswith("eula=true\n")
    assert json.loads((directory / "ops.json").read_text(encoding="utf-8")) == []


def test_configuration_never_overwrites_an_existing_run(tmp_path: Path) -> None:
    directory = tmp_path / "run"
    directory.mkdir()
    evidence = directory / "server.log"
    evidence.write_text("old evidence", encoding="utf-8")

    with pytest.raises(SystemExit, match="not empty"):
        RUNNER.write_configuration(directory, {}, allowed_players=())

    assert evidence.read_text(encoding="utf-8") == "old evidence"


def test_case_colliding_player_names_leave_no_run_directory(tmp_path: Path) -> None:
    directory = tmp_path / "run"

    with pytest.raises(SystemExit, match="differ only by case"):
        RUNNER.write_configuration(directory, {}, allowed_players=("Kin_One", "kin_one"))

    assert not directory.exists()


def test_unpinned_server_jar_is_rejected_before_launch(tmp_path: Path) -> None:
    jar = tmp_path / "server.jar"
    jar.write_bytes(b"not minecraft")

    with pytest.raises(SystemExit, match="not the pinned artifact"):
        RUNNER.verify_jar(jar)


def test_eula_must_be_explicit_before_the_directory_is_created(tmp_path: Path) -> None:
    directory = tmp_path / "run"
    result = subprocess.run(
        [
            sys.executable,
            TOOL,
            "--directory",
            str(directory),
            "--jar",
            str(tmp_path / "missing.jar"),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "must be accepted by the operator" in result.stderr
    assert not directory.exists()


def test_a_summon_is_a_console_line_and_never_a_second_command() -> None:
    """The console is a channel where an unchecked string is another command."""

    assert RUNNER.summon_command("minecraft:pig") == "summon minecraft:pig ~ ~ ~"
    assert RUNNER.summon_command("pig") == "summon pig ~ ~ ~"

    for injection in (
        "pig\nstop",
        "pig; stop",
        "pig `stop`",
        "pig\n",
        "Pig",
        "",
        "pig pig",
    ):
        with pytest.raises(SystemExit, match="not a vanilla entity id"):
            RUNNER.summon_command(injection)


def test_the_tool_takes_a_clean_stop_from_sigterm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SIGTERM, because the SIGINT this used to rely on never arrived.

    A background job of a non-interactive shell inherits SIGINT set to ignore —
    measured in the runner image — so `kill -INT` on the tool was a no-op and a
    domain run's server kept running until the container was killed. SIGTERM's
    default kills without saving. Both are now the clean stop.
    """

    saved = signal.getsignal(signal.SIGTERM)
    saved_int = signal.getsignal(signal.SIGINT)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            TOOL,
            "--directory",
            str(tmp_path / "run"),
            "--jar",
            str(tmp_path / "missing.jar"),
            "--accept-eula",
        ],
    )
    try:
        # The jar check is what fails, and it fails after the handlers are
        # installed: a tool that is killed while still starting up has to save
        # the world too.
        with pytest.raises(SystemExit, match="is missing"):
            RUNNER.main()
        assert signal.getsignal(signal.SIGTERM) is RUNNER.request_clean_stop
        assert signal.getsignal(signal.SIGINT) is RUNNER.request_clean_stop
    finally:
        signal.signal(signal.SIGTERM, saved)
        signal.signal(signal.SIGINT, saved_int)

    with pytest.raises(KeyboardInterrupt):
        RUNNER.request_clean_stop(signal.SIGTERM, None)
