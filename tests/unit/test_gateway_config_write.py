"""The second authorized Dashboard write: persisting operator settings.

The whole-project goal's Phase D excepts exactly this into the read-only Dashboard alongside
the identity rename. These tests prove the point of the exception rather than its happy path:
the same source/auth layering the rename uses (loopback host, same origin, JSON content type,
the CSRF token the config read handed out), the closed field set, the atomic replace that a
refused or malformed save must never leave half-applied, and — the boundary that makes this
safe to expose at all — that a credential-shaped value is refused while a key can never be read
back out of the response.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from gateway.config_write import (
    CONFIG_PATH,
    CONFIG_SAVE_PATH,
    SCHEMA,
    config_read,
    save_from_request,
)
from gateway.identity import CSRF_HEADER, IDENTITY_PATH
from gateway.server import GatewayServer, ReadRequestHandler, ReadService
from minekin_core.application.ports.clock import FakeClock
from minekin_core.domain.operator_config import load_operator_config

REQUEST_TIMEOUT_SECONDS = 10

VALID_FIELDS = {
    "model_provider": "openai_compatible",
    "model_base_url": "https://api.commandcode.ai",
    "model_name": "deepseek-chat",
    "goal_product_id": "minecraft:oak_planks",
    "goal_quantity": 4,
}


def _service(root: Path) -> ReadService:
    return ReadService(root=root, kin_selector=None, clock=FakeClock())


@pytest.fixture
def base_url(tmp_path: Path) -> Iterator[tuple[str, ReadService, Path]]:
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


# --------------------------------------------------------------------------------------
# The config read route
# --------------------------------------------------------------------------------------


def test_the_config_read_projects_the_schema_vocabulary_and_token(
    base_url: tuple[str, ReadService, Path],
) -> None:
    url, _service, _root = base_url
    status, document = get(url + CONFIG_PATH)

    assert status == 200
    assert document["schemaVersion"] == SCHEMA
    assert document["fields"] == {}
    assert "model_provider" in document["knownFields"]
    assert "model_timeout_ms" in document["intFields"]
    assert set(document["providers"]) >= {"off", "openai_compatible"}
    assert document["csrfToken"]
    assert document["loadError"] is None
    assert document["maxBodyBytes"]


def test_the_config_read_hands_out_this_process_s_csrf_token(
    base_url: tuple[str, ReadService, Path],
) -> None:
    url, service, _root = base_url
    _status, document = get(url + CONFIG_PATH)

    assert document["csrfToken"] == service.csrf_token


# --------------------------------------------------------------------------------------
# The config save write, over HTTP
# --------------------------------------------------------------------------------------


def test_a_same_origin_config_save_lands_and_persists(
    base_url: tuple[str, ReadService, Path],
) -> None:
    url, service, root = base_url

    status, result = post(
        url + CONFIG_SAVE_PATH,
        body={"fields": VALID_FIELDS},
        headers=_headers(url, service),
    )

    assert status == 200, result
    assert result["status"] == "saved"
    assert result["fields"] == VALID_FIELDS

    stored = load_operator_config(root)
    assert stored.model_provider == "openai_compatible"
    assert stored.goal_product_id == "minecraft:oak_planks"
    assert stored.goal_quantity == 4

    _status, refreshed = get(url + CONFIG_PATH)
    assert refreshed["fields"] == VALID_FIELDS


def test_a_saved_key_reference_persists_as_a_name_not_a_value(
    base_url: tuple[str, ReadService, Path],
) -> None:
    """The closest a field comes to a secret is the *name* of the variable that holds it."""

    url, service, root = base_url
    body = dict(VALID_FIELDS, model_api_key_env="MINEKIN_MODEL_API_KEY")

    status, _result = post(
        url + CONFIG_SAVE_PATH, body={"fields": body}, headers=_headers(url, service)
    )
    assert status == 200

    stored = load_operator_config(root)
    assert stored.model_api_key_env == "MINEKIN_MODEL_API_KEY"
    # The closed field set has no slot for a key's value, only for the reference name.
    saved_fields = cast("dict[str, object]", stored.as_document()["fields"])
    assert set(saved_fields) <= {
        "model_provider",
        "model_base_url",
        "model_name",
        "model_api_key_env",
        "model_timeout_ms",
        "model_run_cost_cap",
        "goal_product_id",
        "goal_quantity",
        "goal_source_item_id",
        "goal_direction",
    }


def test_a_config_save_without_the_csrf_token_is_refused_and_writes_nothing(
    base_url: tuple[str, ReadService, Path],
) -> None:
    url, service, root = base_url
    headers = _headers(url, service)
    del headers[CSRF_HEADER]

    status, result = post(url + CONFIG_SAVE_PATH, body={"fields": VALID_FIELDS}, headers=headers)

    assert status == 401
    assert result["error"] == "missing_or_bad_csrf_token"
    assert load_operator_config(root).is_empty()


def test_a_config_save_from_a_foreign_origin_is_refused(
    base_url: tuple[str, ReadService, Path],
) -> None:
    url, service, root = base_url

    status, result = post(
        url + CONFIG_SAVE_PATH,
        body={"fields": VALID_FIELDS},
        headers=_headers(url, service, origin="http://evil.example"),
    )

    assert status == 403
    assert result["error"] == "cross_origin"
    assert load_operator_config(root).is_empty()


def test_a_form_encoded_config_save_is_refused_before_the_body_is_read(
    base_url: tuple[str, ReadService, Path],
) -> None:
    url, service, _root = base_url
    headers = _headers(url, service)
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    status, result = post(url + CONFIG_SAVE_PATH, body={"fields": VALID_FIELDS}, headers=headers)

    assert status == 415
    assert result["error"] == "unsupported_media_type"


def test_saving_a_read_route_is_a_405_not_a_write(base_url: tuple[str, ReadService, Path]) -> None:
    url, service, _root = base_url
    status, _body = post(
        url + IDENTITY_PATH, body={"fields": VALID_FIELDS}, headers=_headers(url, service)
    )

    assert status == 405


def test_reading_the_save_path_is_a_404(base_url: tuple[str, ReadService, Path]) -> None:
    url, _service, _root = base_url
    status, body = get(url + CONFIG_SAVE_PATH)

    assert status == 404
    assert str(body["error"]).startswith(CONFIG_SAVE_PATH)


# --------------------------------------------------------------------------------------
# The field set and the secret boundary, at the request-handling layer
# --------------------------------------------------------------------------------------


def test_a_credential_shaped_value_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    status, result = save_from_request(
        tmp_path,
        body={"fields": {"model_name": "sk-" + "a" * 40}},
    )

    assert status == 400
    assert result["error"] == "invalid_config"
    assert "credential" in result["message"]
    assert load_operator_config(tmp_path).is_empty()


def test_an_unknown_field_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    status, result = save_from_request(tmp_path, body={"fields": {"shell_command": "rm -rf"}})

    assert status == 400
    assert result["error"] == "invalid_config"
    assert "not a configurable field" in result["message"]
    assert load_operator_config(tmp_path).is_empty()


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ({}, "must carry a `fields` object"),
        ({"fields": "not-a-map"}, "must be an object"),
        ({"fields": VALID_FIELDS, "extra": 1}, "unexpected field(s) at top level"),
        ({"fields": {"goal_quantity": 0}}, "between 1 and"),
        ({"fields": {"model_provider": "nonsense"}}, "unknown provider"),
    ],
)
def test_a_malformed_config_is_refused_and_leaves_nothing_stored(
    tmp_path: Path, body: dict[str, Any], needle: str
) -> None:
    status, result = save_from_request(tmp_path, body=body)

    assert status == 400
    assert result["error"] == "invalid_config"
    assert needle in result["message"]
    assert load_operator_config(tmp_path).is_empty()


def test_a_save_replaces_the_whole_document(tmp_path: Path) -> None:
    save_from_request(tmp_path, body={"fields": VALID_FIELDS})

    status, result = save_from_request(tmp_path, body={"fields": {"model_provider": "off"}})

    assert status == 200
    assert result["fields"] == {"model_provider": "off"}
    assert load_operator_config(tmp_path).goal_product_id == ""


def test_the_config_read_reports_a_hand_broken_document_without_raising(tmp_path: Path) -> None:
    from minekin_core.domain import operator_config

    # A file the reader will not accept: the panel still gets a usable vocabulary plus a reason.
    (tmp_path / operator_config.CONFIG_FILE_NAME).write_text("{not json", encoding="utf-8")

    document = config_read(tmp_path, clock=FakeClock(), csrf_token="tok")

    assert document["fields"] == {}
    assert document["loadError"]
    assert document["knownFields"]
