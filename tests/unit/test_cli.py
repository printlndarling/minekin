from __future__ import annotations

import io
import json
import sqlite3
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from minekin_core.adapters.launcher.launch_plan import find_workspace_root
from minekin_core.adapters.sqlite.connection import SQLiteCompatibilityError
from minekin_core.bootstrap import main, run
from minekin_core.cli.doctor import diagnose
from minekin_core.cli.parser import parse_args
from minekin_core.config import RuntimeRequirements
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError


@pytest.mark.parametrize(
    ("argv", "command"),
    [
        (["init", "--kin-id", "kin-1"], "init"),
        (["doctor"], "doctor"),
        (["bundle", "verify", "--profile", "profile.json"], "bundle"),
        (["launch-plan", "--profile", "profile.json", "--dry-run"], "launch-plan"),
        (["session", "start", "--profile", "profile.json"], "session"),
        (["session", "status"], "session"),
        (["session", "stop"], "session"),
        (["evidence", "verify", "run-1"], "evidence"),
        (["replay", "evidence/run-1"], "replay"),
    ],
)
def test_frozen_cli_schema_parses(argv: list[str], command: str) -> None:
    assert parse_args(argv).command == command


def test_launch_plan_requires_explicit_dry_run() -> None:
    with pytest.raises(SystemExit) as raised:
        parse_args(["launch-plan", "--profile", "profile.json"])
    assert raised.value.code == ExitCode.USAGE


def test_session_start_naming_no_server_is_exactly_what_it_used_to_be() -> None:
    """The saved-world option is additive: absent means "leave the client at the menu"."""

    assert parse_args(["session", "start", "--profile", "profile.json"]).server_profile is None


def test_session_start_can_name_the_saved_world_to_join() -> None:
    parsed = parse_args(
        [
            "session",
            "start",
            "--profile",
            "profile.json",
            "--server-profile",
            "server.json",
        ]
    )

    assert parsed.profile == "profile.json"
    assert parsed.server_profile == "server.json"


def test_session_start_naming_no_world_is_exactly_what_it_used_to_be() -> None:
    """The world to seed is additive too: absent means "nothing was placed here"."""

    parsed = parse_args(["session", "start", "--profile", "profile.json"])

    assert parsed.world_save is None
    assert parsed.world_name is None


def test_session_start_publishes_only_when_asked() -> None:
    """Hosting is an intent, not a side effect of being in a world.

    Publishing is a lifecycle change to the server in the client's own process —
    measured to grant the host cheats and a permission level — so it is asked for
    rather than done whenever a world happened to be seeded.
    """

    assert parse_args(["session", "start", "--profile", "profile.json"]).open_lan is False
    assert (
        parse_args(["session", "start", "--profile", "profile.json", "--open-lan"]).open_lan is True
    )


def test_session_start_can_name_the_port_it_publishes_on() -> None:
    """Zero asks the client to choose; a fixture names one so a joiner can be pointed."""

    assert parse_args(["session", "start", "--profile", "p.json"]).open_lan_port == 0
    assert (
        parse_args(
            ["session", "start", "--profile", "p.json", "--open-lan-port", "25570"]
        ).open_lan_port
        == 25570
    )


def test_session_start_can_name_the_world_to_seed_and_enter() -> None:
    parsed = parse_args(
        [
            "session",
            "start",
            "--profile",
            "profile.json",
            "--world-save",
            "prepared-world",
            "--world-name",
            "prepared-world",
        ]
    )

    assert parsed.world_save == Path("prepared-world")
    assert parsed.world_name == "prepared-world"


def test_replay_is_dispatched_rather_than_placeheld(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The last frozen command with nowhere to dispatch to, and the rule it was keeping.

    `evidence verify` left the placeholder list when it got an implementation, and
    `replay` was the entry left in it. What that test was really asserting — a path
    argument this cannot use is an answer rather than a side effect — is asserted here
    rather than dropped along with the placeholder. `NOT_A_BUNDLE` is that answer: there
    is material at that path and it is not a bundle, so the classification is storage.
    """

    monkeypatch.chdir(tmp_path)
    stdout = io.StringIO()
    stderr = io.StringIO()

    assert run(["replay", "missing-evidence"], stdout=stdout, stderr=stderr) == ExitCode.STORAGE

    report = json.loads(stdout.getvalue())
    assert report["command"] == "replay"
    assert report["status"] == "invalid"
    assert report["category"] == "STORAGE"
    assert report["reason"] == "NOT_A_BUNDLE"
    assert stderr.getvalue() == ""
    assert list(tmp_path.iterdir()) == []


def test_init_without_a_stated_root_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`init` left the placeholder list, so its own no-side-effect rule is asserted here."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MINEKIN_HOME", raising=False)
    monkeypatch.setenv("MINEKIN_USERNAME", "Kin")

    with pytest.raises(MinekinError):
        run(["init", "--kin-id", "kin-1"], stdout=io.StringIO(), stderr=io.StringIO())

    assert list(tmp_path.iterdir()) == []


def test_session_start_without_a_stated_root_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`session start` left the placeholder list, so its own rule is asserted here."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MINEKIN_HOME", raising=False)

    with pytest.raises(MinekinError):
        run(
            ["session", "start", "--profile", "missing.json"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )

    assert list(tmp_path.iterdir()) == []


def test_doctor_is_read_only_and_reports_requirements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run(
        command: Sequence[str],
        *,
        capture_output: bool,
        check: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, check, text, timeout
        return subprocess.CompletedProcess(command, 0, "", 'openjdk version "21.0.5"')

    report = diagnose(RuntimeRequirements(), which=lambda _name: "/read-only/java", run=fake_run)
    assert report.ok
    assert {check.name for check in report.checks} == {
        "python",
        "java",
        "protobuf",
        "sqlite",
        "workspace",
    }
    assert list(tmp_path.iterdir()) == []


def test_doctor_fails_when_java_version_is_not_the_frozen_major() -> None:
    def fake_run(
        command: Sequence[str],
        *,
        capture_output: bool,
        check: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, check, text, timeout
        return subprocess.CompletedProcess(command, 0, "", 'java version "17.0.12"')

    report = diagnose(RuntimeRequirements(), which=lambda _name: "java", run=fake_run)
    assert not report.ok
    assert next(check for check in report.checks if check.name == "java").summary.startswith(
        "Java 17"
    )


def test_an_unsupported_sqlite_is_reported_as_a_storage_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gate is deliberate, so its refusal has to reach the operator.

    A stock Linux distribution ships a SQLite older than the frozen WAL safety
    set. That refusal travelled as an unclassified exception, and the CLI
    redacted it to "unexpected internal failure" — so the message saying exactly
    what was wrong never appeared.
    """

    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv("MINEKIN_USERNAME", "Kin")
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 45, 1))
    monkeypatch.setattr(sqlite3, "sqlite_version", "3.45.1")

    # `main` is where an exception becomes the document the operator reads.
    code = main(["init", "--kin-id", "kin-01"])
    document = json.loads(capsys.readouterr().err)

    assert code == int(ExitCode.STORAGE)
    assert document["category"] == "STORAGE"
    assert "3.45.1" in document["message"]
    # Naming what would satisfy the gate is what makes it actionable.
    assert "3.51.3" in document["message"]


def test_the_compatibility_error_carries_its_own_message() -> None:
    error = SQLiteCompatibilityError("SQLite 3.45.1 is outside the safety set")

    assert error.safe_message == "SQLite 3.45.1 is outside the safety set"
    assert error.category is ErrorCategory.STORAGE
    assert error.exit_code is ExitCode.STORAGE


def test_a_foreign_database_is_reported_rather_than_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator's mistake is a file in the wrong place, and it is sayable."""

    kin = tmp_path / "kin" / "kin-01"
    kin.mkdir(parents=True)
    foreign = sqlite3.connect(kin / "kin.sqlite3")
    foreign.execute("CREATE TABLE their_notes (body TEXT)")
    foreign.commit()
    foreign.close()
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv("MINEKIN_USERNAME", "Kin")

    code = main(["session", "status"])
    document = json.loads(capsys.readouterr().err)

    assert code == int(ExitCode.STORAGE)
    assert "not a Minekin ledger" in document["message"]


# ---------------------------------------------------------------------------
# The checkout the runner exists to provide
# ---------------------------------------------------------------------------


def workspace_check(start: Path) -> Any:
    """The workspace line of a real report, with the host kept out of it.

    Asked through `diagnose` rather than by calling the check directly: what a reader
    of a doctor report acts on is the report, and a test that reached past it would
    keep passing if the check stopped being wired into one. `which` returns nothing so
    the java check answers without running anything, and `run` refuses rather than
    shells out — a workspace test that quietly depended on the host's JDK would be a
    different test on every machine.
    """

    def refuse(*_arguments: Any, **_keywords: Any) -> Any:
        raise AssertionError("the workspace check must not run a subprocess")

    report = diagnose(
        RuntimeRequirements(), which=lambda _name: None, run=refuse, workspace_start=start
    )
    return next(check for check in report.checks if check.name == "workspace")


def test_a_healthy_host_is_not_a_host_that_can_start_a_session(tmp_path: Path) -> None:
    """The other checks can all be green on a machine that cannot run this.

    The controlled runner mounts the repository read-only instead of installing a
    wheel, and the reason is written where that is done: finding the workspace needs
    `bridge/` and `proto/` beside the source. So "python, java, protobuf and sqlite are
    right" is not the same claim as "this host can launch a client", and a diagnostic
    that reported only the first would be answering a question nobody asked while the
    real one went unanswered until a session was already under way.
    """

    lonely = tmp_path / "site-packages" / "minekin_core"
    lonely.mkdir(parents=True)

    check = workspace_check(lonely)

    assert check.name == "workspace"
    assert check.ok is False
    # The refusal says what is missing and what to do about it, on one line, because
    # the report is a list of one-line summaries.
    assert "no Minekin workspace found" in check.summary
    assert "which an installed wheel does not carry" in check.summary
    assert "\n" not in check.summary


def test_the_workspace_check_asks_the_question_the_planner_asks(tmp_path: Path) -> None:
    """A check that could pass while `build_launch_plan` refuses is worse than none.

    Both markers are required and one of them is not enough, so this builds the
    half-present tree the check has to be unhappy about rather than only the empty one.
    """

    half = tmp_path / "checkout" / "src" / "minekin_core"
    half.mkdir(parents=True)
    (tmp_path / "checkout" / "bridge").mkdir()

    assert workspace_check(half).ok is False
    with pytest.raises(MinekinError, match="no Minekin workspace found"):
        find_workspace_root(half)

    (tmp_path / "checkout" / "proto").mkdir()

    assert workspace_check(half).ok is True
    assert find_workspace_root(half) == tmp_path / "checkout"


def test_the_workspace_check_reads_the_checkout_without_changing_it(tmp_path: Path) -> None:
    """Doctor is read-only, and that is a property of the new check too."""

    root = tmp_path / "checkout"
    (root / "src" / "minekin_core").mkdir(parents=True)
    (root / "bridge").mkdir()
    (root / "proto").mkdir()
    before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))

    check = workspace_check(root / "src" / "minekin_core")

    assert check.ok is True
    assert check.summary == f"workspace at {root}"
    assert sorted(path.relative_to(root).as_posix() for path in root.rglob("*")) == before
