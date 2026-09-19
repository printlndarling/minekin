from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.process import (
    ClientProcessSpec,
    client_environment,
    redirect_targets,
)
from minekin_core.adapters.launcher.supervisor import (
    ProcessSupervisor,
    parse_process_identity,
)
from minekin_core.application.ports.clock import FakeClock
from minekin_core.domain.errors import ErrorCategory, MinekinError


def spec(tmp_path: Path, script: str, **overrides: object) -> ClientProcessSpec:
    """A real process, using the running interpreter as the stand-in for java."""

    overlay = tmp_path / "session" / "session-01" / "generation-1"
    overlay.mkdir(parents=True, exist_ok=True)
    arguments: dict[str, object] = {
        "argv": ("-c", script),
        "working_directory": overlay,
        "java_executable": Path(sys.executable),
        "run_root": tmp_path,
        "main_class": "probe",
        "environment": client_environment(overlay),
        "session_directories": redirect_targets(overlay),
    }
    arguments.update(overrides)
    return ClientProcessSpec(**arguments)  # type: ignore[arg-type]


def supervisor(tmp_path: Path, **kwargs: object) -> ProcessSupervisor:
    return ProcessSupervisor(clock=FakeClock(), **kwargs)  # type: ignore[arg-type]


PRINT_ENVIRONMENT = "import json,os;print(json.dumps(dict(os.environ)))"
PRINT_CWD = "import os;print(os.getcwd())"
SLEEP = "import time;time.sleep(30)"


def run_to_exit(
    run: ProcessSupervisor, document: ClientProcessSpec, *, timeout_s: float = 10.0
) -> None:
    """Let a short-lived child finish before stopping it.

    `stop()` terminates a process that is still running, which is what the
    shutdown tests want and the opposite of what an output test wants.
    """

    run.start(document)
    deadline = time.monotonic() + timeout_s
    while run.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    run.stop()


def wait_for_log(path: Path, *, contains: str = "", timeout_s: float = 10.0) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text and (not contains or contains in text):
                return text
        time.sleep(0.05)
    raise AssertionError(f"{path} never produced {contains!r}")


def test_a_real_process_is_started_and_identified(tmp_path: Path) -> None:
    run = supervisor(tmp_path)
    identity = run.start(spec(tmp_path, PRINT_CWD))

    assert identity.pid > 0
    assert len(identity.argv_digest) == 64
    assert identity.started_at.endswith("Z")
    assert identity.as_document()["pid"] == identity.pid

    run.stop()


def test_the_child_runs_inside_the_session_game_directory(tmp_path: Path) -> None:
    run = supervisor(tmp_path, log_directory=tmp_path / "logs")
    run_to_exit(run, spec(tmp_path, PRINT_CWD))

    printed = wait_for_log(tmp_path / "logs" / "stdout.log")

    assert printed == str(tmp_path / "session" / "session-01" / "generation-1")


def test_the_child_receives_exactly_the_named_environment(tmp_path: Path) -> None:
    """Nothing is inherited implicitly, so the host's own facts cannot leak in."""

    run = supervisor(tmp_path, log_directory=tmp_path / "logs")
    run_to_exit(run, spec(tmp_path, PRINT_ENVIRONMENT))
    overlay = tmp_path / "session" / "session-01" / "generation-1"

    environment = json.loads(wait_for_log(tmp_path / "logs" / "stdout.log"))

    # The working directory is the overlay, so the redirected variables point
    # inside it rather than at a directory beside it.
    assert environment["HOME"] == str(overlay)
    assert environment["XDG_CACHE_HOME"] == str(overlay / "xdg-cache")
    assert environment["TMPDIR"] == str(overlay / "tmp")
    assert "MINEKIN_FORWARDED" not in environment


def test_a_forwarded_host_variable_reaches_the_child(tmp_path: Path) -> None:
    overlay = tmp_path / "session" / "session-01" / "generation-1"
    overlay.mkdir(parents=True)
    environment = client_environment(overlay, forward={"MINEKIN_FORWARDED": ":99"})
    run = supervisor(tmp_path, log_directory=tmp_path / "logs")

    run_to_exit(run, spec(tmp_path, PRINT_ENVIRONMENT, environment=environment))

    printed = json.loads(wait_for_log(tmp_path / "logs" / "stdout.log"))

    assert printed["MINEKIN_FORWARDED"] == ":99"


def test_the_standard_streams_are_captured(tmp_path: Path) -> None:
    run = supervisor(tmp_path, log_directory=tmp_path / "logs")
    run_to_exit(run, spec(tmp_path, "import sys;print('out');print('err',file=sys.stderr)"))

    assert wait_for_log(tmp_path / "logs" / "stdout.log") == "out"
    assert wait_for_log(tmp_path / "logs" / "stderr.log") == "err"


def test_a_running_process_reports_running_and_no_exit_code(tmp_path: Path) -> None:
    run = supervisor(tmp_path)
    run.start(spec(tmp_path, SLEEP))

    assert run.running()
    assert run.poll() is None

    run.stop()


def test_stopping_terminates_a_running_process(tmp_path: Path) -> None:
    run = supervisor(tmp_path)
    run.start(spec(tmp_path, SLEEP))

    outcome = run.stop(timeout_s=10.0)

    assert not run.running()
    assert outcome.identity.pid > 0
    # SIGTERM on POSIX leaves a negative code; TerminateProcess on Windows does not.
    assert isinstance(outcome.exit_code, int)


def test_stopping_a_finished_process_reports_its_code(tmp_path: Path) -> None:
    run = supervisor(tmp_path)
    run.start(spec(tmp_path, "raise SystemExit(3)"))
    deadline = time.monotonic() + 10
    while run.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)

    outcome = run.stop()

    assert outcome.exit_code == 3


def test_a_second_start_is_refused(tmp_path: Path) -> None:
    run = supervisor(tmp_path)
    run.start(spec(tmp_path, SLEEP))

    with pytest.raises(MinekinError, match="already managed") as raised:
        run.start(spec(tmp_path, SLEEP))

    assert raised.value.category is ErrorCategory.PROCESS
    run.stop()


def test_stopping_without_a_process_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="no client process") as raised:
        supervisor(tmp_path).stop()

    assert raised.value.category is ErrorCategory.PROCESS


def test_a_non_positive_stop_timeout_is_refused(tmp_path: Path) -> None:
    run = supervisor(tmp_path)
    run.start(spec(tmp_path, SLEEP))

    with pytest.raises(ValueError, match="timeout_s"):
        run.stop(timeout_s=0)

    run.stop()


def test_an_unstartable_executable_is_reported_as_a_process_failure(tmp_path: Path) -> None:
    run = supervisor(tmp_path)
    missing = tmp_path / "not-a-real-java"

    with pytest.raises(MinekinError, match="could not be started") as raised:
        run.start(spec(tmp_path, PRINT_CWD, java_executable=missing))

    assert raised.value.category is ErrorCategory.PROCESS


def test_the_session_directories_are_redirected_into_the_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / "session" / "session-01" / "generation-1"
    overlay.mkdir(parents=True)

    environment = client_environment(overlay, forward={"DISPLAY": ":99"})

    assert environment["DISPLAY"] == ":99"
    assert environment["HOME"] == str(overlay)
    assert all(
        not value.startswith(str(Path.home())) or str(tmp_path) in value
        for value in environment.values()
    )


@pytest.mark.parametrize("name", ["HOME", "XDG_DATA_HOME", "TMPDIR"])
def test_a_redirected_variable_cannot_be_forwarded_over(tmp_path: Path, name: str) -> None:
    overlay = tmp_path / "session" / "session-01" / "generation-1"
    overlay.mkdir(parents=True)

    with pytest.raises(MinekinError, match="already redirected"):
        client_environment(overlay, forward={name: "/host/place"})


def test_a_forwarded_value_naming_the_host_minecraft_is_refused(tmp_path: Path) -> None:
    overlay = tmp_path / "session" / "session-01" / "generation-1"
    overlay.mkdir(parents=True)

    with pytest.raises(MinekinError, match=r"host \.minecraft"):
        client_environment(overlay, forward={"MODS": "/home/operator/.minecraft/mods"})


def test_a_recorded_identity_round_trips(tmp_path: Path) -> None:
    run = supervisor(tmp_path)
    identity = run.start(spec(tmp_path, SLEEP))
    run.stop()

    assert parse_process_identity(dict(identity.as_document())) == identity


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"pid": 0, "started_at": "x", "argv_digest": "a" * 64}, "usable pid"),
        ({"pid": True, "started_at": "x", "argv_digest": "a" * 64}, "usable pid"),
        ({"pid": 1, "started_at": "", "argv_digest": "a" * 64}, "start time"),
        ({"pid": 1, "started_at": "x", "argv_digest": "short"}, "argument digest"),
        ({}, "usable pid"),
    ],
)
def test_a_malformed_recorded_identity_is_refused(
    document: dict[str, object], message: str
) -> None:
    with pytest.raises(MinekinError, match=message):
        parse_process_identity(document)


def test_the_supervisor_does_not_share_the_host_environment(tmp_path: Path) -> None:
    """A variable set for this process must not appear in the child by default."""

    os.environ["MINEKIN_HOST_ONLY_PROBE"] = "leaked"
    try:
        run = supervisor(tmp_path, log_directory=tmp_path / "logs")
        run_to_exit(run, spec(tmp_path, PRINT_ENVIRONMENT))

        printed = json.loads(wait_for_log(tmp_path / "logs" / "stdout.log"))
        assert "MINEKIN_HOST_ONLY_PROBE" not in printed
    finally:
        del os.environ["MINEKIN_HOST_ONLY_PROBE"]
