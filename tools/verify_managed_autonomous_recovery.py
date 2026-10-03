"""Local managed autonomy recovery with a decision test double, never real LLM evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from tools.verify_managed_session_lifecycle import Fixture


def gateway_identity(fixture: Fixture) -> dict[str, Any]:
    argv = [
        "python",
        "-m",
        "gateway.server",
        "--data-root",
        "/data",
        "--kin",
        fixture.kin,
        "--host",
        "0.0.0.0",
        "--port",
        "8789",
    ]
    expected = b"\0".join(s.encode() for s in argv) + b"\0"
    return json.loads(
        fixture.docker(
            "import pathlib,json; "
            f"a={expected!r}; "
            "paths=pathlib.Path('/proc').glob('[0-9]*/cmdline'); "
            "p=[x.parent for x in paths if x.read_bytes()==a]; "
            "assert len(p)==1; "
            "entries=(p[0]/'environ').read_bytes().split(b'\\0'); "
            "e=dict(x.split(b'=',1) for x in entries if b'=' in x); "
            "print(json.dumps({'supervisorPid':int(p[0].name),"
            "'environmentFile':e.get(b'MINEKIN_ENV_FILE',b'').decode() or None}))"
        )
    )


def rows(fixture: Fixture, session_id: str) -> list[dict[str, Any]]:
    return json.loads(
        fixture.docker(
            "import sqlite3,json; "
            f"c=sqlite3.connect('file:/data/kin/{fixture.kin}/kin.sqlite3?mode=ro',uri=True); "
            "c.row_factory=sqlite3.Row; "
            "q='select position,event_type,payload_json,run_id,session_id from event "
            "where session_id=? order by position'; "
            f"print(json.dumps([dict(r) for r in c.execute(q,({session_id!r},)).fetchall()]))"
        )
    )


def endpoint(fixture: Fixture, path: str, *, post: bool = False) -> dict[str, Any]:
    return json.loads(
        fixture.docker(
            "import urllib.request,json; "
            f"r=urllib.request.Request('http://127.0.0.1:18991{path}',"
            f"method={'POST' if post else 'GET'!r}); "
            "o=urllib.request.build_opener(urllib.request.ProxyHandler({})); "
            "print(o.open(r,timeout=3).read().decode())"
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--kin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = Fixture("http://127.0.0.1:8789", args.container, args.kin)
    assert fixture.request("session")["state"] == "idle"
    assert (
        fixture.docker(
            "from pathlib import Path; print((Path('/data')/'operator-config.json').exists())"
        )
        == "False"
    ), (
        "This test requires the unconfigured controlled fixture; "
        "it never replaces saved user settings"
    )
    original = gateway_identity(fixture)
    token = uuid.uuid4().hex
    environment_file = f"/data/control-tests/{token}/control.env"
    contents = (
        "MINEKIN_MODEL_PROVIDER=openai_compatible\n"
        "MINEKIN_MODEL_BASE_URL=http://127.0.0.1:18991/v1\n"
        "MINEKIN_MODEL=control-path-test-double\n"
        "MINEKIN_MODEL_API_KEY_ENV=\n"
        "MINEKIN_MODEL_TIMEOUT_MS=1500\n"
        "MINEKIN_MODEL_RUN_COST_CAP=100000\n"
        "MINEKIN_GOAL_PRODUCT=\n"
    )
    fixture.docker(
        "from pathlib import Path; "
        f"p=Path({environment_file!r}); p.parent.mkdir(parents=True); p.write_text({contents!r}); "
        "print('created credential-free fixture configuration')"
    )
    server = subprocess.Popen(
        [
            "docker",
            "exec",
            fixture.container,
            "python",
            "-m",
            "tools.control_model_fixture",
            "--control-token",
            token,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    result: dict[str, Any] = {"decisionSource": "control_path_test_double", "cases": {}}

    def save() -> None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    changed = False
    job_id: str | None = None
    try:
        for _ in range(30):
            if server.poll() is not None:
                raise RuntimeError("Decision fixture failed to start")
            try:
                assert endpoint(fixture, "/health")["instanceId"] == token
                break
            except subprocess.CalledProcessError:
                time.sleep(0.25)
        else:
            raise TimeoutError("Decision fixture did not become ready")
        changed = True
        fixture.restart_gateway(original, environment_file=environment_file)
        identity = gateway_identity(fixture)
        fixture.docker(
            "import os; from pathlib import Path; "
            "from minekin_core.config import load_local_environment; "
            "from minekin_core.domain.model_access import model_config; "
            f"raw=Path('/proc/{identity['supervisorPid']}/environ').read_bytes().split(b'\\0'); "
            "e=dict(x.decode().split('=',1) for x in raw if b'=' in x); "
            "load_local_environment(e); c=model_config(e); "
            "assert c.enabled and c.base_url=='http://127.0.0.1:18991/v1' and not c.api_key_env; "
            "print('credential-free test model configuration verified')"
        )
        for case in ("managed_cancel", "owned_client_disconnect"):
            calls_before = len(endpoint(fixture, "/health")["calls"])
            job_id = fixture.start(300, autonomous_steps=64)
            joined = fixture.wait(job_id, joined=True)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                before = rows(fixture, joined["sessionId"])
                grant = any(r["event_type"] == "InputLeaseGranted" for r in before)
                released = any(r["event_type"] == "InputReleased" for r in before)
                called = len(endpoint(fixture, "/health")["calls"]) > calls_before
                if grant and not released and called:
                    break
                assert fixture.request("session/job")["job"]["phase"] in {"supervising", "stopping"}
                time.sleep(0.25)
            else:
                raise TimeoutError("Managed autonomy did not hold input and call the test double")
            result["cases"][case] = {"jobId": job_id, "before": before}
            save()
            if case == "managed_cancel":
                fixture.request("session/stop", {"confirm": True})
            else:
                fixture.kill_client(joined)
            ended = fixture.wait(job_id)
            after = rows(fixture, joined["sessionId"])
            result["cases"][case].update(job=ended, after=after)
            save()
            if case == "managed_cancel":
                assert (
                    ended["outcome"] == "STOPPED_ON_REQUEST"
                    and ended["inputReleaseFailed"] is False
                )
                assert any(
                    r["event_type"] == "InputReleased"
                    and json.loads(r["payload_json"]).get("had_lease") is True
                    for r in after
                )
            else:
                assert ended["phase"] == "failed" and ended["clientExitCode"] == -9
            print(json.dumps({"case": case, "jobId": job_id, "phase": ended["phase"]}), flush=True)
            job_id = None
        result["passed"] = True
    finally:
        if changed:
            if fixture.request("session")["state"] != "idle":
                current = fixture.request("session/job")["job"]
                assert job_id is not None and current["jobId"] == job_id, (
                    "Cleanup refuses to stop a session that replaced the fixture job"
                )
                fixture.token = fixture.request("server")["csrfToken"]
                fixture.request("session/stop", {"confirm": True})
            if job_id is not None:
                fixture.wait_idle(job_id)
            fixture.restart_gateway(
                gateway_identity(fixture), environment_file=original["environmentFile"]
            )
            result["originalGatewayConfigurationRestored"] = True
        endpoint(fixture, f"/control/{token}/stop", post=True)
        server.communicate(timeout=10)
        save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
