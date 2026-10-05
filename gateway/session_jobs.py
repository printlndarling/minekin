"""Owned, bounded background sessions; reads never restart a saved job."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, BinaryIO, cast

from gateway import server_config
from gateway.identity import refusal
from minekin_core.application.autonomous_play import MAX_STEP_BUDGET, AutonomousAsk
from minekin_core.application.player_mind import SKILL_OFFER
from minekin_core.cli.auto_session import prepare_auto_bundle_start
from minekin_core.cli.init import run_root
from minekin_core.cli.session import select_kin, start_and_supervise, stop_session
from minekin_core.cli.status import ObservedState, read_status
from minekin_core.config import forwarded_environment, java_executable, load_local_environment
from minekin_core.domain.decision_policy import (
    DECISION_POLICY_VARIABLE,
    KNOWN_POLICIES,
    decision_policy_from_environment,
)
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.model_access import model_config
from minekin_core.domain.operator_config import apply_operator_config, load_operator_config

START_PATH = "/api/v1/dashboard/session/start"
JOB_PATH = "/api/v1/dashboard/session/job"
SCHEMA = "kin-dashboard-session-job/1.0.0"
ACTIVE = {"preparing", "supervising", "stopping"}


class StartCancelled(Exception):
    def __init__(self, reason: str = "START_CANCELLED") -> None:
        self.reason = reason
        super().__init__(reason)


def _lock(path: Path) -> BinaryIO | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            if path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


class SessionJobs:
    def __init__(self, root: Path, kin_selector: str | None) -> None:
        self.root = root
        self.kin_selector = kin_selector
        self._guard = threading.Lock()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    def _directory(self) -> Path:
        return run_root(self.root, select_kin(self.root, self.kin_selector)) / "dashboard-jobs"

    def read(self) -> dict[str, Any]:
        directory = self._directory()
        last = directory / "latest.json"
        if not last.exists():
            return {"schemaVersion": SCHEMA, "job": None}
        try:
            raw = json.loads(last.read_bytes())
            if not isinstance(raw, dict):
                raise ValueError("Invalid job record")
            job = cast(dict[str, Any], raw)
            if job.get("schemaVersion") != SCHEMA:
                raise ValueError("Invalid job record")
            if job.get("phase") in ACTIVE:
                lease = _lock(directory / "owner.lock")
                if lease is not None:
                    lease.close()
                    job = {**job, "phase": "interrupted", "reason": "SUPERVISOR_NOT_RUNNING"}
                elif (directory / f"{job.get('jobId')}.cancel").exists():
                    job = {**job, "phase": "stopping"}
            return {"schemaVersion": SCHEMA, "job": job}
        except (ValueError, OSError):
            return {"schemaVersion": SCHEMA, "job": None, "error": "JOB_RECORD_UNREADABLE"}

    def start(self, body: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        required = {
            "confirm",
            "serverRevision",
            "allowRemote",
            "maxDownloadBytes",
            "durationSeconds",
            "autonomousSteps",
        }
        if (
            set(body) != required
            or body.get("confirm") is not True
            or not isinstance(body.get("allowRemote"), bool)
        ):
            return refusal(
                400, "invalid_request", "An explicit bounded start is required.", schema=SCHEMA
            )
        for name, upper in [
            ("maxDownloadBytes", 2_147_483_648),
            ("durationSeconds", 3600),
            ("autonomousSteps", MAX_STEP_BUDGET),
        ]:
            value = body[name]
            minimum = 1 if name == "durationSeconds" else 0
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= upper
            ):
                return refusal(
                    400,
                    "invalid_request",
                    f"{name} must be an integer in {minimum}..{upper}.",
                    schema=SCHEMA,
                )
        with self._guard:
            if self._thread is not None and self._thread.is_alive():
                return refusal(
                    409, "session_job_active", "A managed job is already active.", schema=SCHEMA
                )
            if (
                read_status(self.root, kin_selector=self.kin_selector).state
                is not ObservedState.IDLE
            ):
                return refusal(
                    409,
                    "session_not_idle",
                    "Stop or resolve the existing client first.",
                    schema=SCHEMA,
                )
            # Same target consent/revision gates as the probe, before a worker or JVM exists.
            status, probe = server_config.probe_from_request(
                self.root,
                body={
                    "revision": body["serverRevision"],
                    "confirm": True,
                    "allowRemote": body["allowRemote"],
                },
            )
            if status != 200:
                return status, probe
            if probe["supportStatus"] != "RESOLVED":
                return refusal(
                    409,
                    "server_not_supported",
                    "No reviewed client matches this target and platform.",
                    schema=SCHEMA,
                )
            profile = server_config.profile_snapshot(
                self.root,
                probe["fields"],
                probe["revision"],
                minecraft_version=probe["minecraftVersion"],
            )
            env = dict(os.environ)
            load_local_environment(env)
            # The name already in the captured environment -- exported by the shell or read
            # from the env file -- outranks the saved document, the same precedence
            # `apply_operator_config` applies below. Recorded only as its source word.
            policy_from_environment = DECISION_POLICY_VARIABLE in env
            applied = apply_operator_config(load_operator_config(self.root), env)
            # Validate the captured configuration without changing Gateway's process environment.
            model_config(env)
            try:
                captured_policy = decision_policy_from_environment(env)
            except ValueError:
                # A misspelled policy is refused by name here -- before a worker exists, before
                # any bundle preparation, and long before a JVM could fail generically.
                return refusal(
                    400,
                    "invalid_decision_policy",
                    f"{DECISION_POLICY_VARIABLE} must be one of: "
                    f"{', '.join(sorted(KNOWN_POLICIES))}",
                    schema=SCHEMA,
                )
            policy_source = (
                "environment"
                if policy_from_environment
                else ("config" if DECISION_POLICY_VARIABLE in applied else "default")
            )
            java = java_executable(env)
            directory = self._directory()
            lease = _lock(directory / "owner.lock")
            if lease is None:
                return refusal(
                    409,
                    "session_job_active",
                    "Another Gateway owns this Kin's managed job.",
                    schema=SCHEMA,
                )
            job_id = uuid.uuid4().hex
            job: dict[str, Any] = {
                "schemaVersion": SCHEMA,
                "jobId": job_id,
                "supervisorPid": os.getpid(),
                "phase": "preparing",
                "reason": "",
                "serverRevision": probe["revision"],
                "fields": probe["fields"],
                # The mode this launch will actually run, captured and validated at the start
                # boundary: environment (shell/env file) > saved document > model default.
                # A fact about this job only -- old records carry neither key, and the read
                # side must not fill them from the latest configuration.
                "decisionPolicy": captured_policy.value,
                "decisionPolicySource": policy_source,
                "autonomousSteps": body["autonomousSteps"],
                "durationSeconds": body["durationSeconds"],
                "installed": 0,
                "total": 0,
                "outcome": None,
                "inputReleaseFailed": None,
            }
            self._cancel.clear()
            try:
                self._publish(directory, job)
                self._thread = threading.Thread(
                    target=self._run,
                    args=(directory, lease, job, profile, java, env, dict(body)),
                    name=f"minekin-session-{job_id}",
                    daemon=False,
                )
                self._thread.start()
            except BaseException:
                lease.close()
                raise
            return 202, {"schemaVersion": SCHEMA, "jobId": job_id, "phase": "preparing"}

    @staticmethod
    def _publish(directory: Path, job: dict[str, Any]) -> None:
        payload = json.dumps(job, separators=(",", ":")).encode()
        for name in (f"{job['jobId']}.json", "latest.json"):
            temporary = directory / f".{name}.{uuid.uuid4().hex}.tmp"
            temporary.write_bytes(payload)
            for attempt in range(11):
                try:
                    temporary.replace(directory / name)
                    break
                except PermissionError as error:
                    # Windows readers can momentarily deny a rename while holding the
                    # old file. Retry only sharing/access violations, with a small bound.
                    if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 10:
                        raise
                    time.sleep(0.01)

    def request_stop(self) -> bool:
        record = self.read().get("job")
        if record is None or record.get("phase") not in ACTIVE:
            return False
        # A shared cancellation request also reaches a worker owned by another Gateway.
        job_id = record.get("jobId", "")
        if (
            not isinstance(job_id, str)
            or len(job_id) != 32
            or any(c not in "0123456789abcdef" for c in job_id)
        ):
            return False
        (self._directory() / f"{job_id}.cancel").write_text("stop", encoding="ascii")
        self._cancel.set()
        return True

    def _run(
        self,
        directory: Path,
        lease: BinaryIO,
        job: dict[str, Any],
        profile: Path,
        java: Path,
        env: dict[str, str],
        body: dict[str, Any],
    ) -> None:
        deadline = time.monotonic() + body["durationSeconds"]
        done = threading.Event()
        session_id = uuid.uuid4().hex
        job["sessionId"] = session_id
        stop_cause: list[str] = []

        def owns_client() -> bool:
            return any(
                client.session_id == session_id
                for client in read_status(self.root, kin_selector=self.kin_selector).clients
                if client.liveness.value in {"ALIVE", "UNKNOWN"}
            )

        def check() -> None:
            if self._cancel.is_set() or (directory / f"{job['jobId']}.cancel").exists():
                raise StartCancelled()
            if time.monotonic() >= deadline:
                raise StartCancelled("RUN_DURATION_EXPIRED")

        def progress(completed: int, total: int) -> None:
            check()
            job.update(installed=completed, total=total)
            self._publish(directory, job)

        def stop_when_requested() -> None:
            while not done.wait(0.2):
                try:
                    check()
                except StartCancelled as cancelled:
                    if owns_client():
                        stop_cause.append(cancelled.reason)
                        stop_session(self.root, kin_selector=self.kin_selector)
                        return

        stopper = threading.Thread(
            target=stop_when_requested, name="minekin-job-stop", daemon=False
        )
        try:
            self._publish(directory, job)
            check()
            decision = prepare_auto_bundle_start(
                registry_path=server_config.REGISTRY_PATH,
                server_profile=profile,
                run_root=run_root(self.root, select_kin(self.root, self.kin_selector)),
                max_bytes=body["maxDownloadBytes"] or None,
                on_progress=progress,
            )
            check()
            job.update(
                phase="supervising",
                installed=decision.installed,
                total=decision.installed + decision.reused,
            )
            self._publish(directory, job)
            config = model_config(env)
            ask = (
                None
                if body["autonomousSteps"] == 0
                else AutonomousAsk(
                    skills=SKILL_OFFER,
                    step_budget=body["autonomousSteps"],
                    step_seconds=20,
                    decision_seconds=config.timeout_ms / 1000,
                )
            )
            stopper.start()
            launch, result = asyncio.run(
                start_and_supervise(
                    root=self.root,
                    profile=decision.recipe,
                    java_executable=java,
                    session_id=session_id,
                    generation=1,
                    kin_selector=self.kin_selector,
                    forward_environment=forwarded_environment(env),
                    server_profile=profile,
                    handshake_timeout=90,
                    autonomous=ask,
                    before_client_launch=check,
                    model_environment=env,
                )
            )
            normal = result.outcome.value == "STOPPED_ON_REQUEST" or (
                result.outcome.value == "CLIENT_EXITED" and result.client_exit_code == 0
            )
            job.update(
                phase="ended" if normal else "failed",
                reason=stop_cause[0] if stop_cause else "" if normal else result.outcome.value,
                outcome=result.outcome.value,
                inputReleaseFailed=result.as_dict()["input_release_failed"],
                sessionId=launch.session_id,
                runId=launch.run_id,
                bridgeLostReason=result.as_dict()["bridge_lost_reason"],
                clientExitCode=result.client_exit_code,
            )
        except StartCancelled as cancelled:
            job.update(phase="ended", reason=cancelled.reason)
        except MinekinError as error:
            job.update(phase="failed", reason=error.category.value)
        except Exception:
            # No provider prose, arbitrary exception text, paths or environment in the API.
            job.update(phase="failed", reason="SESSION_JOB_FAILED")
        finally:
            done.set()
            if stopper.ident is not None:
                stopper.join(timeout=15)
            try:
                if owns_client():
                    report = stop_session(self.root, kin_selector=self.kin_selector)
                    if report.as_dict()["status"] == "blocked":
                        job.update(phase="failed", reason="STOP_UNRESOLVED")
                self._publish(directory, job)
            finally:
                lease.close()

    def close(self) -> None:
        self._cancel.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
