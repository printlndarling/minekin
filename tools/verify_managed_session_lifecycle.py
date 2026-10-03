"""Exercise bounded Gateway jobs against an explicitly named local Docker fixture.

No model calls, identity changes, remote targets or automatic replay. Crash/restart
injection only targets the session this tool just started and its fixture Gateway.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class Fixture:
    def __init__(self, base: str, container: str, kin: str) -> None:
        parsed = urlsplit(base)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != 8789:
            raise ValueError("Only the explicit local fixture Gateway 127.0.0.1:8789 is accepted")
        self.base, self.container, self.kin = base.rstrip("/"), container, kin
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", container) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,96}", kin
        ):
            raise ValueError("An explicit fixture container and Kin identifier are required")
        self.token = ""
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base + "/api/v1/dashboard/" + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Origin": self.base,
                "X-Minekin-CSRF-Token": self.token,
            },
            method="GET" if body is None else "POST",
        )
        with self.http.open(request, timeout=15) as response:
            return json.loads(response.read())

    def docker(self, code: str) -> str:
        result = subprocess.run(
            ["docker", "exec", self.container, "python", "-c", code],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()

    def start(self, seconds: int) -> str:
        config = self.request("server")
        if config["fields"] != {"host": "127.0.0.1", "port": 25566}:
            raise ValueError("Save the controlled loopback endpoint before this test")
        self.token = config["csrfToken"]
        assert self.request("session")["state"] == "idle"
        result = self.request(
            "session/start",
            {
                "confirm": True,
                "serverRevision": config["revision"],
                "allowRemote": False,
                "maxDownloadBytes": 0,
                "durationSeconds": seconds,
                "autonomousSteps": 0,
            },
        )
        return result["jobId"]

    def wait(self, job_id: str, *, joined: bool = False, timeout: float = 120) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self.request("session/job")["job"]
            assert job["jobId"] == job_id, "Another job replaced this fixture run"
            if joined:
                snapshot = self.request("snapshot")
                if (
                    snapshot["session"].get("value", {}).get("sessionId", {}).get("value")
                    == job.get("sessionId")
                    and snapshot["world"].get("value", {}).get("joined", {}).get("value") is True
                ):
                    return job
                assert job["phase"] in {"preparing", "supervising", "stopping"}, job
            elif job["phase"] not in {"preparing", "supervising", "stopping"}:
                assert self.request("session")["state"] == "idle", (
                    "An owned client remained after the job ended"
                )
                return job
            time.sleep(0.25)
        raise TimeoutError("The existing fixture job did not reach the requested observation")

    def kill_client(self, job: dict[str, Any]) -> None:
        # Proven from the recorded session claim inside the container, not an arbitrary PID.
        self.docker(
            "from pathlib import Path; import os,signal; "
            "from minekin_core.adapters.launcher.orphans import session_claims,Liveness; "
            f"r=Path('/data/kin')/{self.kin!r}/'run'; "
            f"s={job['sessionId']!r}; "
            "c=[c for c in session_claims(r) if c.session_id==s and c.liveness is Liveness.ALIVE]; "
            "assert len(c)==1; pid=c[0].identity.pid; fd=os.pidfd_open(pid); "
            "again=[x for x in session_claims(r) if x.session_id==s and x.identity.pid==pid "
            "and x.liveness is Liveness.ALIVE]; "
            "assert len(again)==1; signal.pidfd_send_signal(fd,signal.SIGKILL); os.close(fd)"
        )

    def wait_idle(self, job_id: str, *, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            assert self.request("session/job")["job"]["jobId"] == job_id, (
                "Another job replaced this fixture during cleanup"
            )
            if self.request("session")["state"] == "idle":
                return
            time.sleep(0.25)
        raise TimeoutError("The stopped fixture client remained alive after the cleanup deadline")

    def restart_gateway(self, job: dict[str, Any]) -> None:
        argv = [
            "python",
            "-m",
            "gateway.server",
            "--data-root",
            "/data",
            "--kin",
            self.kin,
            "--host",
            "0.0.0.0",
            "--port",
            "8789",
        ]
        expected = b"\0".join(value.encode() for value in argv) + b"\0"
        self.docker(
            "import pathlib,os,signal; "
            f"a={expected!r}; "
            "paths=pathlib.Path('/proc').glob('[0-9]*/cmdline'); "
            "p=[int(x.parent.name) for x in paths if x.read_bytes()==a]; "
            f"assert len(p)==1 and p[0]=={job['supervisorPid']!r}; "
            "fd=os.pidfd_open(p[0]); "
            "assert pathlib.Path(f'/proc/{p[0]}/cmdline').read_bytes()==a; "
            "signal.pidfd_send_signal(fd,signal.SIGKILL); os.close(fd)"
        )
        subprocess.run(
            ["docker", "exec", "--detach", self.container, "xvfb-run", "-a", *argv],
            check=True,
            capture_output=True,
            timeout=30,
        )
        for _ in range(60):
            try:
                self.token = self.request("server")["csrfToken"]
                return
            except OSError:
                time.sleep(0.25)
        raise TimeoutError("The replacement Gateway did not become readable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", default="http://127.0.0.1:8789")
    parser.add_argument("--container", required=True)
    parser.add_argument("--kin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--restart-gateway",
        action="store_true",
        help="Inject loss of the exact fixture Gateway process",
    )
    parser.add_argument(
        "--only-restart", action="store_true", help="Run only the Gateway-loss case"
    )
    args = parser.parse_args()
    if args.only_restart and not args.restart_gateway:
        parser.error("--only-restart requires --restart-gateway")
    fixture = Fixture(args.gateway, args.container, args.kin)
    results: dict[str, Any] = {}

    if not args.only_restart:
        job_id = fixture.start(300)
        before = fixture.request("session/job")["job"]
        assert before["phase"] == "preparing", "Preparation raced this cancellation test"
        fixture.request("session/stop", {"confirm": True})
        result = fixture.wait(job_id)
        assert result["reason"] == "START_CANCELLED" and result["outcome"] is None
        results["preparing_cancel"] = result
        print(
            json.dumps({"case": "preparing_cancel", "jobId": job_id, "phase": result["phase"]}),
            flush=True,
        )

        job_id = fixture.start(80)
        fixture.wait(job_id, joined=True)
        result = fixture.wait(job_id)
        assert (
            result["outcome"] == "STOPPED_ON_REQUEST" and result["reason"] == "RUN_DURATION_EXPIRED"
        )
        assert result["inputReleaseFailed"] is False
        results["duration_expired"] = result
        print(
            json.dumps({"case": "duration_expired", "jobId": job_id, "phase": result["phase"]}),
            flush=True,
        )

        job_id = fixture.start(300)
        joined = fixture.wait(job_id, joined=True)
        fixture.kill_client(joined)
        result = fixture.wait(job_id)
        assert result["phase"] == "failed" and result["clientExitCode"] == -9
        results["owned_client_killed"] = result
        print(
            json.dumps({"case": "owned_client_killed", "jobId": job_id, "phase": result["phase"]}),
            flush=True,
        )

    if args.restart_gateway:
        job_id = fixture.start(300)
        joined = fixture.wait(job_id, joined=True)

        def fingerprint() -> str:
            return fixture.docker(
                "from pathlib import Path; import hashlib,json; "
                f"r=Path('/data/kin')/{fixture.kin!r}/'run'; "
                "digest=hashlib.sha256((r/'dashboard-jobs/latest.json').read_bytes()).hexdigest(); "
                "count=len(list((r/'session').glob('*/generation-1'))); "
                "print(json.dumps({'recordDigest':digest,'overlays':count}))"
            )

        before = fingerprint()
        fixture.restart_gateway(joined)
        observed = fixture.request("session/job")["job"]
        assert observed["jobId"] == job_id and observed["phase"] == "interrupted"
        for _ in range(3):
            fixture.request("snapshot")
            fixture.request("session/job")
        assert fingerprint() == before, "Read after restart created or rewrote a session"
        stopped = None
        if fixture.request("session")["state"] != "idle":
            stopped = fixture.request("session/stop", {"confirm": True})
        fixture.wait_idle(job_id)
        results["gateway_restart"] = {
            "job": observed,
            "stop": stopped,
            "unchanged": json.loads(before),
        }
        print(
            json.dumps({"case": "gateway_restart", "jobId": job_id, "phase": observed["phase"]}),
            flush=True,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
