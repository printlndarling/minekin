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
from minekin_core.application.autonomous_play import MAX_STEP_BUDGET
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
        {"autonomousSteps": MAX_STEP_BUDGET + 1},
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
                # `winerror` is Windows-only in typeshed, but the production classifier
                # reads it with `getattr` and this simulation has to carry the same shape
                # on every platform the suite runs on — including the Linux CI that
                # type-checks this very assignment.
                error.winerror = winerror  # pyright: ignore[reportAttributeAccessIssue]
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


def test_the_saved_decision_policy_rides_into_the_managed_launch_environment(
    jobs: session_jobs.SessionJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dashboard-saved policy is a name the launch reads, not a panel decoration: the
    environment handed to the supervised session carries the operator's explicit `rules`."""

    from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE
    from minekin_core.domain.operator_config import OperatorConfig, save_operator_config

    monkeypatch.delenv(DECISION_POLICY_VARIABLE, raising=False)
    save_operator_config(jobs.root, OperatorConfig(decision_policy="rules"))
    captured: list[dict[str, str]] = []

    def prepare(**kwargs: Any) -> Any:
        return SimpleNamespace(installed=0, reused=1, recipe=Path("unused"))

    async def launch(**kwargs: Any) -> Any:
        captured.append(dict(kwargs["model_environment"]))
        return SimpleNamespace(session_id="test", run_id="run"), SessionRun(
            outcome=SessionOutcome.CLIENT_EXITED,
            session_state=SessionState.STOPPED,
            connection_state=None,
            events_applied=0,
            events_ignored=0,
            client_exit_code=0,
        )

    monkeypatch.setattr(session_jobs, "prepare_auto_bundle_start", prepare)
    monkeypatch.setattr(session_jobs, "start_and_supervise", launch)
    try:
        assert jobs.start(body())[0] == 202
        deadline = time.monotonic() + 3
        while jobs.read()["job"]["phase"] in session_jobs.ACTIVE and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        jobs.close()

    assert captured
    assert captured[0][DECISION_POLICY_VARIABLE] == "rules"


def test_provider_off_alone_does_not_select_the_rules_in_the_managed_environment(
    jobs: session_jobs.SessionJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE
    from minekin_core.domain.operator_config import OperatorConfig, save_operator_config

    monkeypatch.delenv(DECISION_POLICY_VARIABLE, raising=False)
    save_operator_config(jobs.root, OperatorConfig(model_provider="off"))
    captured: list[dict[str, str]] = []

    def prepare(**kwargs: Any) -> Any:
        return SimpleNamespace(installed=0, reused=1, recipe=Path("unused"))

    async def launch(**kwargs: Any) -> Any:
        captured.append(dict(kwargs["model_environment"]))
        return SimpleNamespace(session_id="test", run_id="run"), SessionRun(
            outcome=SessionOutcome.CLIENT_EXITED,
            session_state=SessionState.STOPPED,
            connection_state=None,
            events_applied=0,
            events_ignored=0,
            client_exit_code=0,
        )

    monkeypatch.setattr(session_jobs, "prepare_auto_bundle_start", prepare)
    monkeypatch.setattr(session_jobs, "start_and_supervise", launch)
    try:
        assert jobs.start(body())[0] == 202
        deadline = time.monotonic() + 3
        while jobs.read()["job"]["phase"] in session_jobs.ACTIVE and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        jobs.close()

    assert captured
    # No name chosen: the model policy's named stop is what a missing provider means, and the
    # rules are never selected in the operator's place.
    assert DECISION_POLICY_VARIABLE not in captured[0]


def _run_job_to_end(
    jobs: session_jobs.SessionJobs, monkeypatch: pytest.MonkeyPatch, captured: list[dict[str, str]]
) -> None:
    def prepare(**kwargs: Any) -> Any:
        return SimpleNamespace(installed=0, reused=1, recipe=Path("unused"))

    async def launch(**kwargs: Any) -> Any:
        captured.append(dict(kwargs["model_environment"]))
        return SimpleNamespace(session_id="test", run_id="run"), SessionRun(
            outcome=SessionOutcome.CLIENT_EXITED,
            session_state=SessionState.STOPPED,
            connection_state=None,
            events_applied=0,
            events_ignored=0,
            client_exit_code=0,
        )

    monkeypatch.setattr(session_jobs, "prepare_auto_bundle_start", prepare)
    monkeypatch.setattr(session_jobs, "start_and_supervise", launch)
    try:
        assert jobs.start(body())[0] == 202
        deadline = time.monotonic() + 3
        while jobs.read()["job"]["phase"] in session_jobs.ACTIVE and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        jobs.close()


def test_saved_rules_with_an_explicit_shell_model_captures_model_not_the_saved_value(
    jobs: session_jobs.SessionJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The independent counterexample: the saved document says rules while the environment
    says model. The launch runs model (environment wins), the job records the mode it actually
    ran -- model, source environment -- and the saved value stays rules."""

    from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE
    from minekin_core.domain.operator_config import (
        OperatorConfig,
        load_operator_config,
        save_operator_config,
    )

    monkeypatch.setenv(DECISION_POLICY_VARIABLE, "model")
    save_operator_config(jobs.root, OperatorConfig(decision_policy="rules"))
    captured: list[dict[str, str]] = []

    _run_job_to_end(jobs, monkeypatch, captured)

    assert captured[0][DECISION_POLICY_VARIABLE] == "model"
    record = jobs.read()["job"]
    assert record["decisionPolicy"] == "model"
    assert record["decisionPolicySource"] == "environment"
    # The saved document is untouched by the launch and still says rules.
    assert load_operator_config(jobs.root).decision_policy == "rules"


def test_saved_model_with_an_explicit_shell_rules_captures_rules(
    jobs: session_jobs.SessionJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE
    from minekin_core.domain.operator_config import OperatorConfig, save_operator_config

    monkeypatch.setenv(DECISION_POLICY_VARIABLE, "rules")
    save_operator_config(jobs.root, OperatorConfig(decision_policy="model"))
    captured: list[dict[str, str]] = []

    _run_job_to_end(jobs, monkeypatch, captured)

    record = jobs.read()["job"]
    assert record["decisionPolicy"] == "rules"
    assert record["decisionPolicySource"] == "environment"


def test_a_saved_choice_alone_is_captured_with_the_config_source(
    jobs: session_jobs.SessionJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE
    from minekin_core.domain.operator_config import OperatorConfig, save_operator_config

    monkeypatch.delenv(DECISION_POLICY_VARIABLE, raising=False)
    save_operator_config(jobs.root, OperatorConfig(decision_policy="rules"))
    captured: list[dict[str, str]] = []

    _run_job_to_end(jobs, monkeypatch, captured)

    record = jobs.read()["job"]
    assert record["decisionPolicy"] == "rules"
    assert record["decisionPolicySource"] == "config"


@pytest.mark.parametrize("provider", ["", "off"])
def test_a_launch_with_no_choice_anywhere_captures_the_model_default(
    jobs: session_jobs.SessionJobs,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE
    from minekin_core.domain.operator_config import OperatorConfig, save_operator_config

    monkeypatch.delenv(DECISION_POLICY_VARIABLE, raising=False)
    save_operator_config(jobs.root, OperatorConfig(model_provider=provider))
    captured: list[dict[str, str]] = []

    _run_job_to_end(jobs, monkeypatch, captured)

    record = jobs.read()["job"]
    assert record["decisionPolicy"] == "model"
    assert record["decisionPolicySource"] == "default"


def test_the_job_snapshot_survives_a_later_config_change(
    jobs: session_jobs.SessionJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The captured mode is a fact about this launch: changing the saved document afterwards
    must not rewrite the job record of what ran."""

    from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE
    from minekin_core.domain.operator_config import OperatorConfig, save_operator_config

    monkeypatch.delenv(DECISION_POLICY_VARIABLE, raising=False)
    save_operator_config(jobs.root, OperatorConfig(decision_policy="rules"))
    captured: list[dict[str, str]] = []

    _run_job_to_end(jobs, monkeypatch, captured)

    save_operator_config(jobs.root, OperatorConfig(decision_policy="model"))

    record = jobs.read()["job"]
    assert record["decisionPolicy"] == "rules"
    assert record["decisionPolicySource"] == "config"


def test_a_job_record_from_before_this_field_reads_with_no_policy_recorded(
    jobs: session_jobs.SessionJobs,
) -> None:
    """An old record is not defaulted: no field is fabricated, so the read side can say
    not-recorded instead of guessing model or rules from today's configuration."""

    from minekin_core.cli.init import run_root
    from minekin_core.cli.session import select_kin

    # The same path the store derives, staged with a legacy record (no private access).
    directory = run_root(jobs.root, select_kin(jobs.root, jobs.kin_selector)) / "dashboard-jobs"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "latest.json").write_text(
        json.dumps(
            {
                "schemaVersion": session_jobs.SCHEMA,
                "jobId": "a" * 32,
                "phase": "ended",
                "reason": "",
                "fields": {"host": "127.0.0.1", "port": 25566},
                "serverRevision": 1,
                "installed": 0,
                "total": 3,
                "outcome": "STOPPED_ON_REQUEST",
                "inputReleaseFailed": False,
            }
        ),
        encoding="utf-8",
    )

    record = jobs.read()["job"]

    assert "decisionPolicy" not in record
    assert "decisionPolicySource" not in record


def test_an_invalid_environment_policy_is_refused_before_any_worker_or_prepare(
    jobs: session_jobs.SessionJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A misspelled policy is a named refusal at the start boundary -- before a job exists,
    before any thread, and before any bundle preparation runs."""

    from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE

    monkeypatch.setenv(DECISION_POLICY_VARIABLE, "sometimes")
    prepared: list[str] = []

    def prepare(**kwargs: Any) -> Any:
        prepared.append("prepare")
        return SimpleNamespace(installed=0, reused=1, recipe=Path("unused"))

    monkeypatch.setattr(session_jobs, "prepare_auto_bundle_start", prepare)

    status, result = jobs.start(body())

    assert status == 400
    assert result["error"] == "invalid_decision_policy"
    assert DECISION_POLICY_VARIABLE in result["message"]
    assert prepared == []
    assert jobs.read()["job"] is None
    jobs.close()


def test_an_invalid_saved_document_policy_is_refused_at_the_same_boundary(
    jobs: session_jobs.SessionJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even a hand-edited document bypassing the save-time validator is refused where the
    launch reads it, not after a download."""

    from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE
    from minekin_core.domain.operator_config import CONFIG_FILE_NAME

    monkeypatch.delenv(DECISION_POLICY_VARIABLE, raising=False)
    (jobs.root / CONFIG_FILE_NAME).write_text(
        json.dumps(
            {
                "schemaVersion": "minekin-operator-config/1.1",
                "fields": {"decision_policy": "sometimes"},
            }
        ),
        encoding="utf-8",
    )
    prepared: list[str] = []

    def prepare(**kwargs: Any) -> Any:
        prepared.append("prepare")
        return SimpleNamespace(installed=0, reused=1, recipe=Path("unused"))

    monkeypatch.setattr(session_jobs, "prepare_auto_bundle_start", prepare)

    status, result = jobs.start(body())

    assert status == 400
    assert result["error"] == "invalid_decision_policy"
    assert prepared == []
    assert jobs.read()["job"] is None
    jobs.close()
