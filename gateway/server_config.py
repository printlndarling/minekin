"""Persist an operator-selected endpoint and explicitly probe its reviewed version support."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from gateway.identity import refusal
from minekin_core.adapters.launcher.server_profile import load_managed_target_profile
from minekin_core.application.ports.clock import Clock
from minekin_core.cli.auto_session import host_os_arch
from minekin_core.cli.server_probe import run_probe
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.version_resolution import load_reviewed_registry, resolve

SERVER_CONFIG_PATH = "/api/v1/dashboard/server"
SERVER_SAVE_PATH = "/api/v1/dashboard/server/save"
SERVER_PROBE_PATH = "/api/v1/dashboard/server/probe"
SCHEMA = "kin-dashboard-server/1.0.0"
MAX_BODY_BYTES = 1024
REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "tests/fixtures/registry/reviewed-tested-bundles.json"
)


def _database(root: Path) -> Path:
    return root / "dashboard-settings.sqlite3"


def _settings(root: Path) -> tuple[int, dict[str, Any] | None]:
    path = _database(root)
    if not path.exists():
        return 0, None
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute(
            "SELECT revision,host,port FROM server_settings WHERE id=1"
        ).fetchone()
    return (0, None) if row is None else (row[0], {"host": row[1], "port": row[2]})


def server_read(root: Path, *, clock: Clock, csrf_token: str) -> dict[str, Any]:
    error = None
    try:
        revision, fields = _settings(root)
    except (sqlite3.Error, OSError):
        revision, fields = 0, None
        error = "Server settings could not be read."
    return {
        "schemaVersion": SCHEMA,
        "revision": revision,
        "fields": fields,
        "authMode": "offline",
        "csrfToken": csrf_token,
        "observedAt": clock.utc_now().isoformat(),
        "loadError": error,
    }


def _validated_fields(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("fields must contain exactly host and port")
    fields = cast(dict[str, object], raw)
    if set(fields) != {"host", "port"}:
        raise ValueError("fields must contain exactly host and port")
    host, port = fields["host"], fields["port"]
    if not isinstance(host, str) or len(host) > 64:
        raise ValueError("host must be a normalized IP literal")
    try:
        address = ipaddress.ip_address(host)
    except ValueError as error:
        raise ValueError("host must be an IP literal; DNS names are not supported") from error
    if str(address) != host or (isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped):
        raise ValueError("host must be a normalized unmapped IP literal")
    if address.is_unspecified or address.is_multicast or address.is_link_local:
        raise ValueError("host is not a usable explicit server target")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be a whole number between 1 and 65535")
    return {"host": host, "port": port}


def save_from_request(root: Path, *, body: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    if set(body) != {"revision", "fields"}:
        return refusal(400, "invalid_request", "revision and fields are required", schema=SCHEMA)
    expected = body["revision"]
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        return refusal(
            400, "invalid_request", "revision must be a nonnegative integer", schema=SCHEMA
        )
    try:
        fields = _validated_fields(body["fields"])
    except ValueError as error:
        return refusal(400, "invalid_server_config", str(error), schema=SCHEMA)
    root.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_database(root), timeout=5) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS server_settings (id INTEGER PRIMARY KEY CHECK(id=1), "
            "revision INTEGER NOT NULL, host TEXT NOT NULL, port INTEGER NOT NULL)"
        )
        row = connection.execute("SELECT revision FROM server_settings WHERE id=1").fetchone()
        current = 0 if row is None else row[0]
        if current != expected:
            return refusal(
                409,
                "server_config_changed",
                "Server settings changed; reload before saving.",
                schema=SCHEMA,
            )
        revision = current + 1
        connection.execute(
            "INSERT INTO server_settings VALUES (1,?,?,?) ON CONFLICT(id) DO UPDATE SET "
            "revision=excluded.revision,host=excluded.host,port=excluded.port",
            (revision, fields["host"], fields["port"]),
        )
    return 200, {
        "schemaVersion": SCHEMA,
        "revision": revision,
        "fields": fields,
        "authMode": "offline",
    }


def profile_snapshot(
    root: Path, fields: dict[str, Any], revision: int, *, minecraft_version: str | None = None
) -> Path:
    registry = load_reviewed_registry(json.loads(REGISTRY_PATH.read_bytes()))
    versions = sorted({entry.version_text for entry in registry.entries})
    if minecraft_version is not None:
        if minecraft_version not in versions:
            raise ValueError("Requested version is not in the reviewed registry")
        versions = [minecraft_version]
    document = {
        "schema_version": 2,
        "profile_id": "dashboard-server",
        **fields,
        "auth_mode": "offline",
        "resource_pack_policy": "deny",
        "version_policy": {"mode": "explicit_allowlist", "allowed_versions": versions},
        "target_authorization": {
            "granted_by": "operator",
            "basis": f"Explicit Dashboard probe of saved revision {revision}",
        },
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    directory = root / "server-profiles"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{hashlib.sha256(payload).hexdigest()}.json"
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as error:
        if path.read_bytes() != payload:
            raise ValueError("Saved profile snapshot does not match its content digest") from error
    load_managed_target_profile(path)
    return path


def probe_from_request(root: Path, *, body: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    if (
        set(body) != {"revision", "confirm", "allowRemote"}
        or body.get("confirm") is not True
        or not isinstance(body.get("allowRemote"), bool)
    ):
        return refusal(
            400,
            "invalid_request",
            "revision, confirm=true and allowRemote boolean are required",
            schema=SCHEMA,
        )
    revision, fields = _settings(root)
    if fields is None:
        return refusal(409, "server_not_configured", "Save a server endpoint first.", schema=SCHEMA)
    expected = body["revision"]
    if isinstance(expected, bool) or not isinstance(expected, int) or expected != revision:
        return refusal(
            409,
            "server_config_changed",
            "Server settings changed; reload before probing.",
            schema=SCHEMA,
        )
    if fields["host"] not in {"127.0.0.1", "::1"} and body["allowRemote"] is not True:
        return refusal(
            403,
            "remote_probe_not_authorized",
            "Explicit authorization of this saved remote endpoint is required.",
            schema=SCHEMA,
        )
    try:
        path = profile_snapshot(root, _validated_fields(fields), revision)
        observation = run_probe(path, timeout_s=5)
        registry = load_reviewed_registry(json.loads(REGISTRY_PATH.read_bytes()))
        decision = resolve(registry, observation, os_arch=host_os_arch())
    except (MinekinError, ValueError):
        return refusal(
            400,
            "server_probe_refused",
            "The saved target or registry could not be validated.",
            schema=SCHEMA,
        )
    return 200, {
        "schemaVersion": SCHEMA,
        "revision": revision,
        "fields": fields,
        "outcome": observation.outcome.value,
        "protocol": observation.protocol,
        "serverVersion": observation.version_text,
        "supportStatus": decision.status.value,
        "supportReasons": [reason.value for reason in decision.reasons],
        "bundleId": None if decision.bundle is None else decision.bundle.bundle_id,
        "minecraftVersion": None if decision.bundle is None else decision.bundle.version_text,
        "osArch": decision.os_arch,
    }
