# pyright: reportUnknownMemberType=false

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from minekin_core.adapters.launcher.server_profile import load_server_profile
from minekin_core.domain.errors import MinekinError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (REPOSITORY_ROOT / "schemas" / "server-profile.schema.json").read_text(encoding="utf-8")
)
VALID: dict[str, Any] = {
    "schema_version": 1,
    "profile_id": "p0-controlled-offline-loopback",
    "host": "127.0.0.1",
    "port": 25565,
    "auth_mode": "offline",
    "minecraft_version": "1.21.4",
    "visibility": "isolated_test_only",
    "resource_pack_policy": "deny",
}


def replace(key: str, value: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def mutate(document: dict[str, Any]) -> dict[str, Any]:
        document[key] = value
        return document

    return mutate


def drop(key: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def mutate(document: dict[str, Any]) -> dict[str, Any]:
        document.pop(key, None)
        return document

    return mutate


MUTATIONS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "valid": lambda document: document,
    "host-localhost": replace("host", "localhost"),
    "host-private": replace("host", "10.0.0.1"),
    "host-second-loopback": replace("host", "127.0.0.2"),
    "host-wildcard": replace("host", "0.0.0.0"),
    "host-ipv6-loopback": replace("host", "::1"),
    "host-missing": drop("host"),
    "port-zero": replace("port", 0),
    "port-too-large": replace("port", 65536),
    "port-string": replace("port", "25565"),
    "port-bool": replace("port", True),
    "port-float": replace("port", 25565.0),
    "auth-online": replace("auth_mode", "online"),
    "version-drift": replace("minecraft_version", "1.21.3"),
    "visibility-public": replace("visibility", "public"),
    "resource-packs-allow": replace("resource_pack_policy", "allow"),
    "schema-two": replace("schema_version", 2),
    "schema-bool": replace("schema_version", True),
    "schema-missing": drop("schema_version"),
    "profile-id-uppercase": replace("profile_id", "P0-Controlled"),
    "profile-id-single-char": replace("profile_id", "a"),
    "extra-field": replace("server_listing", []),
}


# Cases where the product rule is deliberately stricter than the frozen schema:
# Draft 2020-12 counts a float with a zero fraction as an integer, which is not a
# usable pinned port. Every other case must agree exactly, so a new divergence
# fails here instead of passing unnoticed.
KNOWN_STRICTER = frozenset({"port-float"})


@pytest.mark.parametrize("name", MUTATIONS)
def test_product_validation_agrees_with_the_frozen_schema(name: str, tmp_path: Path) -> None:
    """The hand-written loader must accept exactly what the frozen schema accepts.

    jsonschema is a test-only dependency, so this can check the product rule
    against the reviewed document instead of against a second reading of it.
    """

    document = MUTATIONS[name](dict(VALID))
    schema_errors = list(Draft202012Validator(SCHEMA).iter_errors(document))

    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    try:
        load_server_profile(path)
    except MinekinError:
        loader_accepted = False
    else:
        loader_accepted = True

    if name in KNOWN_STRICTER:
        assert not loader_accepted, f"{name}: expected the stricter product rule to reject"
        assert not schema_errors, f"{name}: the schema tightened too; drop the exception"
        return

    assert loader_accepted == (not schema_errors), (
        f"{name}: schema_errors={[error.message for error in schema_errors]}"
    )
