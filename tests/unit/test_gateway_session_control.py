"""The third authorized Dashboard write, and the first control verb: stopping a session.

The point of these tests is the *boundary*, not the happy path. Stop is offered because Core's
`stop_session` already performs it safely and only ends activity; it is the one control verb this
surface exposes, and `start`/`pause`/`resume`/`move` stay absent from the route table. The tests
prove the read mirrors the write's own predicate (an idle Kin is not stoppable), that the same
source/auth layering the settings writes use guards the POST, and — the architectural claim — that
this layer never terminates a process itself: it delegates to `stop_session`, and a refused stop
reaches Core not at all.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gateway.identity import CSRF_HEADER
from gateway.server import GatewayServer, ReadRequestHandler, ReadService
from gateway.session_control import (
    SCHEMA,
    SESSION_PATH,
    SESSION_STOP_PATH,
    session_read,
    stop_from_request,
)
from gateway_support import joined_run
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.status import ObservedState

REQUEST_TIMEOUT_SECONDS = 10


def _service(root: Path) -> ReadService:
    return ReadService(root=root, kin_selector=None, clock=FakeClock())


@pytest.fixture
def base_url(tmp_path: Path) -> Iterator[tuple[str, ReadService, Path]]:
    joined_run(tmp_path)
    service = _service(tmp_path)
    ReadRequestHandler.service = service
    server = GatewayServer(("127.0.0.1", 0), ReadRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", service, tmp_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=REQUEST_TIMEOUT_SECONDS)


def get(url: str) -> tuple[int, Any]:
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        return int(error.code), json.loads(raw) if raw else None


def post(url: str, *, body: dict[str, Any] | None, headers: dict[str, str]) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        return int(error.code), json.loads(raw) if raw else None


def _headers(base_url: str, service: ReadService, *, origin: str | None = None) -> dict[str, str]:
    host = base_url.split("://", 1)[1]
    return {
        "Origin": origin if origin is not None else base_url,
        "Host": host,
        "Content-Type": "application/json",
        CSRF_HEADER: service.csrf_token,
    }


def _fake_status(state: ObservedState):
    """A `read_status` stand-in: the read and write only ever look at `.state`."""

    def fake(_root: Path, *, kin_selector: str | None = None) -> SimpleNamespace:
        return SimpleNamespace(state=state)

    return fake


def _recording_stop(called: list[str]):
    """A `stop_session` stand-in that records it was reached, returning no report."""

    def fake(_root: Path, *, kin_selector: str | None = None) -> SimpleNamespace:
        called.append("stop")
        return SimpleNamespace(as_dict=lambda: {"reached": True})

    return fake


# --------------------------------------------------------------------------------------
# The session read
# --------------------------------------------------------------------------------------


def test_the_session_read_reports_the_state_and_the_stop_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("gateway.session_control.read_status", _fake_status(ObservedState.RUNNING))

    document = session_read(tmp_path, kin_selector=None, clock=FakeClock(), csrf_token="tok")

    assert document["schemaVersion"] == SCHEMA
    assert document["state"] == "running"
    assert document["stopAllowed"] is True
    assert document["availableControls"] == ["stop"]
    assert document["csrfToken"] == "tok"
    assert document["observedAt"]
    assert document["staleAfterMs"]


def test_an_idle_kin_is_not_offered_a_stop_button(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("gateway.session_control.read_status", _fake_status(ObservedState.IDLE))

    document = session_read(tmp_path, kin_selector=None, clock=FakeClock(), csrf_token="tok")

    assert document["state"] == "idle"
    assert document["stopAllowed"] is False


def test_the_read_names_the_three_controls_it_does_not_offer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """start/pause/resume are recorded as gaps with reasons, never faked into availability."""

    monkeypatch.setattr("gateway.session_control.read_status", _fake_status(ObservedState.IDLE))
    document = session_read(tmp_path, kin_selector=None, clock=FakeClock(), csrf_token="tok")

    assert set(document["unavailableControls"]) == {"start", "pause", "resume"}
    assert all(reason for reason in document["unavailableControls"].values())
    assert "stop" not in document["unavailableControls"]


def test_the_session_read_serves_over_http_with_the_handed_out_token(
    base_url: tuple[str, ReadService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url, service, _root = base_url
    monkeypatch.setattr("gateway.session_control.read_status", _fake_status(ObservedState.RUNNING))

    status, document = get(url + SESSION_PATH)

    assert status == 200
    assert document["schemaVersion"] == SCHEMA
    assert document["csrfToken"] == service.csrf_token
    assert document["state"] == "running"
    assert document["stopAllowed"] is True
    # Served through `ReadService`, which composes the managed-start surface
    # (`gateway/session_jobs.py`) onto this module's stop-only read: the base read
    # still offers `stop` alone (and its own test above pins that), while the panel
    # sees the two verbs the Gateway can actually carry out.
    assert document["availableControls"] == ["stop", "start"]
    assert set(document["unavailableControls"]) == {"pause", "resume"}


# --------------------------------------------------------------------------------------
# The stop write, over HTTP: the source/auth layering the settings writes use
# --------------------------------------------------------------------------------------


def test_a_stop_without_the_csrf_token_is_refused(base_url: tuple[str, ReadService, Path]) -> None:
    url, service, _root = base_url
    headers = _headers(url, service)
    del headers[CSRF_HEADER]

    status, result = post(url + SESSION_STOP_PATH, body={"confirm": True}, headers=headers)

    assert status == 401
    assert result["error"] == "missing_or_bad_csrf_token"


def test_a_stop_from_a_foreign_origin_is_refused(
    base_url: tuple[str, ReadService, Path],
) -> None:
    url, service, _root = base_url

    status, result = post(
        url + SESSION_STOP_PATH,
        body={"confirm": True},
        headers=_headers(url, service, origin="http://evil.example"),
    )

    assert status == 403
    assert result["error"] == "cross_origin"


def test_a_form_encoded_stop_is_refused_before_the_body_is_read(
    base_url: tuple[str, ReadService, Path],
) -> None:
    url, service, _root = base_url
    headers = _headers(url, service)
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    status, result = post(url + SESSION_STOP_PATH, body={"confirm": True}, headers=headers)

    assert status == 415
    assert result["error"] == "unsupported_media_type"


def test_reading_the_stop_path_is_a_404(base_url: tuple[str, ReadService, Path]) -> None:
    url, _service, _root = base_url
    status, body = get(url + SESSION_STOP_PATH)

    assert status == 404
    assert str(body["error"]).startswith(SESSION_STOP_PATH)


def test_saving_the_session_read_path_is_a_405(base_url: tuple[str, ReadService, Path]) -> None:
    url, service, _root = base_url
    status, _body = post(url + SESSION_PATH, body={"confirm": True}, headers=_headers(url, service))

    assert status == 405


# --------------------------------------------------------------------------------------
# The stop request handling: explicit confirmation, the idle refusal, and delegation
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ({}, "explicit confirmation"),
        ({"confirm": False}, "explicit confirmation"),
        ({"confirm": "yes"}, "explicit confirmation"),
        ({"confirm": True, "extra": 1}, "unexpected field(s)"),
    ],
)
def test_an_implicit_or_malformed_stop_is_refused_and_reaches_core_not_at_all(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: dict[str, Any],
    needle: str,
) -> None:
    """A stop that is not an explicit confirmation never reaches Core's termination logic."""

    called: list[str] = []
    monkeypatch.setattr("gateway.session_control.stop_session", _recording_stop(called))

    status, result = stop_from_request(tmp_path, kin_selector=None, body=body)

    assert status == 400
    assert result["error"] == "invalid_request"
    assert needle in result["message"]
    assert called == []


def test_stopping_an_idle_kin_is_a_conflict_not_a_hollow_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An idle Kin reports `session_not_running` rather than run a stop that does nothing."""

    called: list[str] = []
    monkeypatch.setattr("gateway.session_control.read_status", _fake_status(ObservedState.IDLE))
    monkeypatch.setattr("gateway.session_control.stop_session", _recording_stop(called))

    status, result = stop_from_request(tmp_path, kin_selector=None, body={"confirm": True})

    assert status == 409
    assert result["error"] == "session_not_running"
    assert called == []


def test_a_live_stop_delegates_to_core_and_returns_its_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """This layer terminates nothing itself: a live stop is handed to `stop_session`."""

    seen: dict[str, Any] = {}

    def fake_stop(_root: Path, *, kin_selector: str | None = None) -> SimpleNamespace:
        seen["kin_selector"] = kin_selector
        return SimpleNamespace(as_dict=lambda: {"status": "stopped", "kin_id": "kin-01"})

    monkeypatch.setattr("gateway.session_control.read_status", _fake_status(ObservedState.RUNNING))
    monkeypatch.setattr("gateway.session_control.stop_session", fake_stop)

    status, result = stop_from_request(tmp_path, kin_selector=None, body={"confirm": True})

    assert status == 200
    assert result["schemaVersion"] == SCHEMA
    assert result["state"] == "running"
    assert result["report"] == {"status": "stopped", "kin_id": "kin-01"}
    assert seen["kin_selector"] is None
