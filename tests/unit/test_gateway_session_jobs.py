from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gateway import session_jobs
from gateway.server import ReadService
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.init import initialise_identity
from minekin_core.cli.session_runtime import SessionOutcome, SessionRun
from minekin_core.domain.ids import KinId
from minekin_core.domain.session_state import SessionState


def body(**changes: Any) -> dict[str, Any]:
    return {
        "confirm": True,
        "serverRevision": 1,
        "allowRemote": False,
        "durationSeconds": 30,
        "maxDownloadBytes": 0,
        "autonomousSteps": 0,
        **changes,
    }


@pytest.fixture
def jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> session_jobs.SessionJobs:
    initialise_identity(KinId("kin-job"), root=tmp_path, username="minekin", clock=FakeClock())

    def java(env: Any) -> Path:
        return Path(sys.executable)

    def probe(*args: Any, **kwargs: Any) -> tuple[int, dict[str, Any]]:
        return 200, {
            "supportStatus": "RESOLVED",
            "fields": {"host": "127.0.0.1", "port": 25566},
            "revision": 1,
            "minecraftVersion": "1.20.1",
        }

    monkeypatch.setattr(session_jobs, "java_executable", java)
    monkeypatch.setattr(
        session_jobs.server_config,
        "probe_from_request",
        probe,
    )
    return session_jobs.SessionJobs(tmp_path, "kin-job")


@pytest.mark.parametrize(
    "change",
    [
        {"confirm": False},
        {"durationSeconds": True},
        {"durationSeconds": 0},
        {"maxDownloadBytes": -1},
        {"autonomousSteps": 65},
        {"arbitraryPath": "secret"},
    ],
)
def test_invalid_start_does_not_create_worker(
    jobs: session_jobs.SessionJobs, change: dict[str, Any]
) -> None:
    assert jobs.start(body(**change))[0] == 400
    assert jobs.read()["job"] is None


def test_two_gateways_cannot_launch_the_same_kin_and_cancel_is_not_replayed(
    jobs: session_jobs.SessionJobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started, release = threading.Event(), threading.Event()
    launches: list[str] = []

    def prepare(**kwargs: Any) -> Any:
        started.set()
        assert release.wait(3)
        return SimpleNamespace(installed=0, reused=1, recipe=Path("unused"))

    async def launch(**kwargs: Any) -> Any:
        launches.append("launched")
        raise AssertionError("Cancelled preparation must not launch")

    monkeypatch.setattr(session_jobs, "prepare_auto_bundle_start", prepare)
    monkeypatch.setattr(session_jobs, "start_and_supervise", launch)
    try:
        assert jobs.start(body())[0] == 202
        assert started.wait(3)
        other = session_jobs.SessionJobs(jobs.root, jobs.kin_selector)
        assert other.start(body())[0] == 409
        service = ReadService(root=jobs.root, kin_selector=jobs.kin_selector, clock=FakeClock())
        assert service.stop({"confirm": False})[0] == 400
        assert not list((jobs.root / "kin/kin-job/run/dashboard-jobs").glob("*.cancel"))
        assert other.request_stop()
        release.set()
    finally:
        release.set()
        jobs.close()
    assert launches == []
    assert jobs.read()["job"]["reason"] == "START_CANCELLED"
    fresh = session_jobs.SessionJobs(jobs.root, jobs.kin_selector)
    assert fresh.read()["job"]["phase"] == "ended"
    assert launches == []


@pytest.mark.parametrize("exit_code,phase", [(0, "ended"), (-9, "failed"), (None, "failed")])
def test_client_exit_requires_a_confirmed_clean_code(
    jobs: session_jobs.SessionJobs,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int | None,
    phase: str,
) -> None:
    def prepare(**kwargs: Any) -> Any:
        return SimpleNamespace(installed=0, reused=1, recipe=Path("unused"))

    async def launch(**kwargs: Any) -> Any:
        return SimpleNamespace(session_id="test", run_id="run"), SessionRun(
            outcome=SessionOutcome.CLIENT_EXITED,
            session_state=SessionState.STOPPED,
            connection_state=None,
            events_applied=0,
            events_ignored=0,
            client_exit_code=exit_code,
        )

    monkeypatch.setattr(session_jobs, "prepare_auto_bundle_start", prepare)
    monkeypatch.setattr(session_jobs, "start_and_supervise", launch)
    try:
        assert jobs.start(body())[0] == 202
        deadline = time.monotonic() + 3
        while jobs.read()["job"]["phase"] in session_jobs.ACTIVE and time.monotonic() < deadline:
            time.sleep(0.01)
        result = jobs.read()["job"]
        assert result["phase"] == phase
        assert result["clientExitCode"] == exit_code
        assert result["reason"] == ("" if phase == "ended" else "CLIENT_EXITED")
    finally:
        jobs.close()


def test_expired_preparation_never_launches_and_names_the_deadline(
    jobs: session_jobs.SessionJobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [0.0]
    monkeypatch.setattr(
        session_jobs, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=time.sleep)
    )

    def prepare(**kwargs: Any) -> Any:
        clock[0] = 2.0
        return SimpleNamespace(installed=0, reused=1, recipe=Path("unused"))

    monkeypatch.setattr(session_jobs, "prepare_auto_bundle_start", prepare)
    try:
        assert jobs.start(body(durationSeconds=1))[0] == 202
        deadline = time.monotonic() + 3
        while jobs.read()["job"]["phase"] in session_jobs.ACTIVE and time.monotonic() < deadline:
            time.sleep(0.01)
        result = jobs.read()["job"]
        assert result["reason"] == "RUN_DURATION_EXPIRED"
        assert result["outcome"] is None
        assert result["phase"] == "ended"
    finally:
        jobs.close()


@pytest.mark.parametrize(
    "winerror,failures,expected_calls", [(32, 2, 4), (33, 11, 11), (None, 1, 1)]
)
def test_job_publication_retries_only_bounded_windows_sharing_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    winerror: int | None,
    failures: int,
    expected_calls: int,
) -> None:
    original = Path.replace
    calls: list[Path] = []

    def replace(path: Path, target: Path) -> Path:
        calls.append(target)
        if len(calls) <= failures:
            error = PermissionError("injected reader conflict")
            if winerror is not None:
                error.winerror = winerror
            raise error
        return original(path, target)

    monkeypatch.setattr(Path, "replace", replace)
    job = {"jobId": "test", "phase": "preparing"}
    if winerror == 32:
        session_jobs.SessionJobs._publish(tmp_path, job)  # pyright: ignore[reportPrivateUsage]
        assert json.loads((tmp_path / "latest.json").read_text()) == job
        assert json.loads((tmp_path / "test.json").read_text()) == job
    else:
        with pytest.raises(PermissionError):
            session_jobs.SessionJobs._publish(tmp_path, job)  # pyright: ignore[reportPrivateUsage]
        assert not (tmp_path / "latest.json").exists()
    assert len(calls) == expected_calls
