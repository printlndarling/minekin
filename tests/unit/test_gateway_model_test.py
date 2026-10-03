"""Model connectivity is an explicit authorized call, never a game action or mock success."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

import gateway.model_test as model_test
from gateway.identity import CSRF_HEADER
from gateway.server import GatewayServer, ReadRequestHandler, ReadService
from minekin_core.application.ports.clock import FakeClock
from minekin_core.domain.operator_config import OperatorConfig, config_path, save_operator_config


@pytest.fixture
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    env = {"MINEKIN_ENV_FILE": str(tmp_path / "absent.env")}
    monkeypatch.setenv("MINEKIN_ENV_FILE", env["MINEKIN_ENV_FILE"])
    for name in tuple(model_test.os.environ):
        if name.startswith("MINEKIN_MODEL_"):
            monkeypatch.delenv(name)
    return env


def test_off_is_unavailable_without_a_call_or_a_config_write(
    tmp_path: Path,
    clean_env: dict[str, str],
) -> None:
    save_operator_config(tmp_path, OperatorConfig(model_provider="off"))
    before = config_path(tmp_path).read_bytes()
    status, result = model_test.test_from_request(
        tmp_path, body={"confirm": True}, environ=clean_env
    )
    assert status == 200
    assert result["status"] == "unavailable"
    assert result["reason"] == "MODEL_NOT_CONFIGURED"
    assert result["modelCalls"] == result["estimatedCostMicro"] == 0
    assert config_path(tmp_path).read_bytes() == before


@pytest.mark.parametrize(
    "body", [{}, {"confirm": False}, {"confirm": 1}, {"confirm": True, "key": "no"}]
)
def test_probe_requires_exact_confirmation(tmp_path: Path, body: dict[str, Any]) -> None:
    assert model_test.test_from_request(tmp_path, body=body)[0] == 400


@pytest.mark.parametrize("valid", [True, False])
def test_local_endpoint_proves_one_structured_decision_and_redacts_model_prose(
    tmp_path: Path,
    clean_env: dict[str, str],
    valid: bool,
) -> None:
    calls: list[str] = []

    class Endpoint(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            calls.append(self.path)
            content = {
                "skill_id": "turn_to" if valid else "not_offered",
                "reason": "private-prose",
                "intent_generation": 1,
                "arguments": {"yaw_degrees": 0, "pitch_degrees": 0},
            }
            payload = json.dumps(
                {
                    "choices": [
                        {"message": {"content": json.dumps(content)}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        save_operator_config(
            tmp_path,
            OperatorConfig(
                model_provider="openai_compatible",
                model_name="local-stub",
                model_base_url=f"http://127.0.0.1:{server.server_port}",
                model_timeout_ms=60_000,
            ),
        )
        status, result = model_test.test_from_request(
            tmp_path, body={"confirm": True}, environ=clean_env
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert status == 200
    assert result["status"] == ("connected" if valid else "unavailable")
    assert result["reason"] == ("" if valid else "DECISION_OUT_OF_BOUNDS")
    assert result["timeoutMs"] == 20_000
    assert result["modelCalls"] == 1
    assert result["estimatedCostMicro"] > 0
    assert calls == ["/chat/completions"]
    assert "private-prose" not in json.dumps(result)
    assert "local-stub" not in json.dumps(result)


def test_unresolved_key_is_named_without_returning_credentials(
    tmp_path: Path,
    clean_env: dict[str, str],
) -> None:
    save_operator_config(
        tmp_path,
        OperatorConfig(
            model_provider="openai_compatible",
            model_name="no-call",
            model_base_url="https://example.invalid",
            model_api_key_env="MISSING_TEST_KEY",
        ),
    )
    _, result = model_test.test_from_request(tmp_path, body={"confirm": True}, environ=clean_env)
    assert result["reason"] == "KEY_UNRESOLVED"
    assert result["status"] == "unavailable"
    assert "MISSING_TEST_KEY" not in json.dumps(result)


@pytest.fixture
def gateway(tmp_path: Path, clean_env: dict[str, str]) -> Iterator[tuple[str, ReadService]]:
    service = ReadService(root=tmp_path, kin_selector=None, clock=FakeClock())
    ReadRequestHandler.service = service
    server = GatewayServer(("127.0.0.1", 0), ReadRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", service
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize("authorized", [True, False])
def test_http_test_uses_the_same_origin_and_csrf_gate(
    gateway: tuple[str, ReadService],
    authorized: bool,
) -> None:
    base, service = gateway
    headers = {
        "Content-Type": "application/json",
        "Origin": base,
        CSRF_HEADER: service.csrf_token if authorized else "wrong",
    }
    request = urllib.request.Request(
        base + model_test.MODEL_TEST_PATH, data=b'{"confirm":true}', headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            status, result = response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        status, result = error.code, json.loads(error.read())
    assert status == (200 if authorized else 401)
    if authorized:
        assert result["status"] == "unavailable"
        assert result["modelCalls"] == 0


def test_duplicate_probe_is_rejected_while_the_first_is_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ReadService(root=tmp_path, kin_selector=None, clock=FakeClock())
    started, release = threading.Event(), threading.Event()

    def pending(*args: Any, **kwargs: Any) -> tuple[int, dict[str, Any]]:
        started.set()
        assert release.wait(timeout=3)
        return 200, {"status": "connected"}

    monkeypatch.setattr("gateway.server.test_from_request", pending)
    thread = threading.Thread(target=service.test_model, args=({"confirm": True},))
    thread.start()
    try:
        assert started.wait(timeout=3)
        status, result = service.test_model({"confirm": True})
    finally:
        release.set()
        thread.join(timeout=3)
    assert status == 409
    assert result["error"] == "model_test_in_progress"
