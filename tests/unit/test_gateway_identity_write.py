"""The one authorized Dashboard write: renaming a stopped Kin's identity.

`docs/stable-player-name-2026-09-29.md` excepts exactly this from the read-only Dashboard.
The tests here prove the whole point of the exception rather than its happy path: the
source/auth layering (loopback host, same origin, JSON content type, the CSRF token the
identity read handed out), the request validation, the stopped-session guard, the compare-
and-swap against a stale revision, and — the part a half-built endpoint always forgets —
that every refusal and every failure leaves the stored identity byte-for-byte where it was.
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

import gateway.identity
from gateway.identity import (
    CSRF_HEADER,
    IDENTITY_PATH,
    RENAME_PATH,
    authorize_write,
    identity_read,
    rename_from_request,
)
from gateway.server import GatewayServer, ReadRequestHandler, ReadService
from gateway_support import seed_kin
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.rename import show_identity
from minekin_core.cli.status import ObservedState, StatusReport

REQUEST_TIMEOUT_SECONDS = 10
NEW_NAME = "Renamed"


def _service(root: Path) -> ReadService:
    return ReadService(root=root, kin_selector=None, clock=FakeClock())


@pytest.fixture
def stopped_root(tmp_path: Path) -> Path:
    """A Kin with an identity and no live session marker, so a rename is allowed."""

    seed_kin(tmp_path, with_marker=False)
    return tmp_path


@pytest.fixture
def base_url(stopped_root: Path) -> Iterator[tuple[str, ReadService]]:
    service = _service(stopped_root)
    ReadRequestHandler.service = service
    server = GatewayServer(("127.0.0.1", 0), ReadRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", service
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=REQUEST_TIMEOUT_SECONDS)


def get(url: str) -> tuple[int, Any]:
    with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return int(response.status), json.loads(response.read().decode("utf-8"))


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


# --------------------------------------------------------------------------------------
# The identity read route
# --------------------------------------------------------------------------------------


def test_the_identity_read_shows_the_stored_name_uuid_and_revision(
    base_url: tuple[str, ReadService],
) -> None:
    url, _service = base_url
    status, document = get(url + IDENTITY_PATH)

    assert status == 200
    assert document["schemaVersion"] == "kin-dashboard-identity/1.0.0"
    assert document["username"] == "Kin"
    assert document["uuidCanonical"]
    assert isinstance(document["identityRevision"], int)
    assert document["state"] == ObservedState.IDLE.value
    assert document["renameAllowed"] is True
    assert document["notice"]
    assert document["csrfToken"]


def test_the_identity_read_hands_out_this_process_s_csrf_token(
    base_url: tuple[str, ReadService],
) -> None:
    url, service = base_url
    _status, document = get(url + IDENTITY_PATH)

    assert document["csrfToken"] == service.csrf_token


# --------------------------------------------------------------------------------------
# The rename write, over HTTP
# --------------------------------------------------------------------------------------


def test_a_confirmed_same_origin_rename_lands_and_bumps_the_revision(
    base_url: tuple[str, ReadService],
) -> None:
    url, service = base_url
    revision = get(url + IDENTITY_PATH)[1]["identityRevision"]

    status, result = post(
        url + RENAME_PATH,
        body={"username": NEW_NAME, "confirm": True, "expectedRevision": revision},
        headers=_headers(url, service),
    )

    assert status == 200, result
    assert result["status"] == "renamed"
    assert result["before"]["username"] == "Kin"
    assert result["after"]["username"] == NEW_NAME
    assert result["uuidChanged"] is True

    _status, refreshed = get(url + IDENTITY_PATH)
    assert refreshed["username"] == NEW_NAME
    assert refreshed["identityRevision"] == revision + 1


def test_a_rename_without_the_csrf_token_is_refused_and_changes_nothing(
    base_url: tuple[str, ReadService],
) -> None:
    url, service = base_url
    headers = _headers(url, service)
    del headers[CSRF_HEADER]

    status, result = post(
        url + RENAME_PATH,
        body={"username": NEW_NAME, "confirm": True, "expectedRevision": 1},
        headers=headers,
    )

    assert status == 401
    assert result["error"] == "missing_or_bad_csrf_token"
    assert get(url + IDENTITY_PATH)[1]["username"] == "Kin"


def test_a_rename_from_a_foreign_origin_is_refused(base_url: tuple[str, ReadService]) -> None:
    url, service = base_url

    status, result = post(
        url + RENAME_PATH,
        body={"username": NEW_NAME, "confirm": True, "expectedRevision": 1},
        headers=_headers(url, service, origin="http://evil.example"),
    )

    assert status == 403
    assert result["error"] == "cross_origin"
    assert get(url + IDENTITY_PATH)[1]["username"] == "Kin"


def test_a_form_encoded_rename_is_refused_before_the_body_is_read(
    base_url: tuple[str, ReadService],
) -> None:
    url, service = base_url
    headers = _headers(url, service)
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    status, result = post(
        url + RENAME_PATH,
        body={"username": NEW_NAME, "confirm": True, "expectedRevision": 1},
        headers=headers,
    )

    assert status == 415
    assert result["error"] == "unsupported_media_type"


def test_renaming_a_read_route_is_a_405_not_a_rename(base_url: tuple[str, ReadService]) -> None:
    """The rename is the only hole in an otherwise write-refusing surface."""

    url, service = base_url
    status, _body = post(
        url + "/api/v1/dashboard/snapshot",
        body={"username": NEW_NAME, "confirm": True, "expectedRevision": 1},
        headers=_headers(url, service),
    )

    assert status == 405


# --------------------------------------------------------------------------------------
# The guards, at the request-handling layer
# --------------------------------------------------------------------------------------


def test_a_rename_while_the_session_runs_is_refused_without_writing(
    stopped_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway.identity, "read_status", running_status)

    status, result = rename_from_request(
        stopped_root,
        kin_selector=None,
        body={"username": NEW_NAME, "confirm": True, "expectedRevision": 1},
    )

    assert status == 409
    assert result["error"] == "session_not_stopped"
    assert show_identity(stopped_root, _kin_id(stopped_root)).username == "Kin"


def running_status(*_args: object, **_kwargs: object) -> StatusReport:
    return SimpleNamespace(state=ObservedState.RUNNING)  # type: ignore[return-value]


def _kin_id(root: Path) -> Any:
    from minekin_core.cli.session import select_kin

    return select_kin(root, None)


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ({"username": "ab", "confirm": True, "expectedRevision": 1}, "valid Minecraft name"),
        ({"username": "has space", "confirm": True, "expectedRevision": 1}, "valid Minecraft"),
        ({"username": NEW_NAME, "expectedRevision": 1}, "confirmation"),
        ({"username": NEW_NAME, "confirm": False, "expectedRevision": 1}, "confirmation"),
        ({"username": NEW_NAME, "confirm": True}, "expectedRevision"),
        ({"username": NEW_NAME, "confirm": True, "expectedRevision": 0}, "starts at one"),
        ({"username": NEW_NAME, "confirm": True, "expectedRevision": True}, "integer"),
        ({"username": NEW_NAME, "confirm": True, "expectedRevision": "1"}, "integer"),
        (
            {"username": NEW_NAME, "confirm": True, "expectedRevision": 1, "extra": 2},
            "unexpected field",
        ),
    ],
)
def test_a_malformed_rename_is_refused_and_leaves_the_identity_alone(
    stopped_root: Path, body: dict[str, Any], needle: str
) -> None:
    status, result = rename_from_request(stopped_root, kin_selector=None, body=body)

    assert status == 400
    assert result["error"] == "invalid_request"
    assert needle in result["message"]
    assert show_identity(stopped_root, _kin_id(stopped_root)).username == "Kin"


def test_rename_to_the_current_name_is_idempotent_and_writes_nothing(
    stopped_root: Path,
) -> None:
    view = show_identity(stopped_root, _kin_id(stopped_root))

    status, result = rename_from_request(
        stopped_root,
        kin_selector=None,
        body={
            "username": view.username,
            "confirm": True,
            "expectedRevision": view.identity_revision,
        },
    )

    assert status == 200
    assert result["status"] == "unchanged"
    assert result["uuidChanged"] is False
    assert show_identity(stopped_root, _kin_id(stopped_root)).identity_revision == (
        view.identity_revision
    )


def test_a_rename_against_a_stale_revision_is_refused_atomically(stopped_root: Path) -> None:
    view = show_identity(stopped_root, _kin_id(stopped_root))

    status, result = rename_from_request(
        stopped_root,
        kin_selector=None,
        body={
            "username": NEW_NAME,
            "confirm": True,
            "expectedRevision": view.identity_revision + 5,
        },
    )

    assert status == 409
    assert result["error"] == "stale_revision"
    after = show_identity(stopped_root, _kin_id(stopped_root))
    assert after.username == view.username
    assert after.identity_revision == view.identity_revision


# --------------------------------------------------------------------------------------
# The source/auth layer, as one pure decision
# --------------------------------------------------------------------------------------


GOOD_HOST = "127.0.0.1:8787"
GOOD_ORIGIN = "http://127.0.0.1:8787"


def _auth(**overrides: Any) -> tuple[int, dict[str, Any]] | None:
    arguments: dict[str, Any] = {
        "origin": GOOD_ORIGIN,
        "host": GOOD_HOST,
        "content_type": "application/json",
        "supplied_token": "tok",
        "csrf_token": "tok",
    }
    arguments.update(overrides)
    return authorize_write(**arguments)


def test_a_correctly_sourced_request_passes_every_layer() -> None:
    assert _auth() is None


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1.evil.example", None, ""])
def test_a_non_loopback_host_is_refused(host: str | None) -> None:
    refusal = _auth(host=host)
    assert refusal is not None
    assert refusal[0] == 403
    assert refusal[1]["error"] == "forbidden_host"


@pytest.mark.parametrize("origin", ["http://evil.example", "null", "", None])
def test_a_cross_origin_request_is_refused(origin: str | None) -> None:
    refusal = _auth(origin=origin)
    assert refusal is not None
    assert refusal[0] == 403
    assert refusal[1]["error"] == "cross_origin"


def test_a_non_json_content_type_is_refused() -> None:
    refusal = _auth(content_type="application/x-www-form-urlencoded")
    assert refusal is not None
    assert refusal[0] == 415
    assert refusal[1]["error"] == "unsupported_media_type"


@pytest.mark.parametrize("supplied", [None, "", "wrong"])
def test_a_missing_or_wrong_csrf_token_is_refused(supplied: str | None) -> None:
    refusal = _auth(supplied_token=supplied)
    assert refusal is not None
    assert refusal[0] == 401
    assert refusal[1]["error"] == "missing_or_bad_csrf_token"


def test_the_authorization_layer_runs_before_body_parsing(stopped_root: Path) -> None:
    """A request that fails a source check is refused even if its JSON would have passed."""

    refusal = _auth(origin="http://evil.example", supplied_token=None)
    assert refusal is not None
    assert refusal[0] == 403
    assert refusal[1]["error"] == "cross_origin"


def test_identity_read_reports_rename_forbidden_while_running(
    stopped_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway.identity, "read_status", running_status)

    document = identity_read(
        stopped_root,
        kin_selector=None,
        clock=FakeClock(),
        csrf_token="tok",
    )

    assert document["state"] == ObservedState.RUNNING.value
    assert document["renameAllowed"] is False
