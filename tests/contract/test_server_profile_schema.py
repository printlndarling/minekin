# pyright: reportUnknownMemberType=false

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from minekin_core.adapters.launcher.server_profile import (
    load_managed_target_profile,
    load_server_profile,
)
from minekin_core.domain.errors import MinekinError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (REPOSITORY_ROOT / "schemas" / "server-profile.schema.json").read_text(encoding="utf-8")
)
SCHEMA_V2 = json.loads(
    (REPOSITORY_ROOT / "schemas" / "server-profile-v2.schema.json").read_text(encoding="utf-8")
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


VALID_V2: dict[str, Any] = {
    "schema_version": 2,
    "profile_id": "managed-remote-example-docu",
    "host": "198.51.100.20",
    "port": 25565,
    "auth_mode": "offline",
    "version_policy": {"mode": "explicit_allowlist", "allowed_versions": ["1.20.1"]},
    "resource_pack_policy": "deny",
    "target_authorization": {
        "granted_by": "operator-local",
        "basis": "explicitly approved by the operator against the private profile",
    },
}

MUTATIONS_V2: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "valid": lambda document: document,
    "host-localhost": replace("host", "localhost"),
    "host-ipv4-prefix": replace("host", "198.51.100.0/24"),
    "host-wildcard": replace("host", "0.0.0.0"),
    "host-unspecified-v6": replace("host", "::"),
    "host-link-local": replace("host", "169.254.169.254"),
    "host-loopback": replace("host", "127.0.0.1"),
    "host-ipv6-docu": replace("host", "2001:db8::1"),
    "host-partial": replace("host", "1.2.3"),
    "host-leading-zero": replace("host", "198.51.100.020"),
    "host-unnormalized": replace("host", "::0:0"),
    "host-uppercase": replace("host", "2001:DB8::1"),
    "host-mapped-loopback": replace("host", "::ffff:127.0.0.1"),
    "host-missing": drop("host"),
    "port-zero": replace("port", 0),
    "port-too-large": replace("port", 65536),
    "port-string": replace("port", "25565"),
    "port-bool": replace("port", True),
    "port-float": replace("port", 25565.0),
    "auth-online": replace("auth_mode", "online"),
    "schema-one": replace("schema_version", 1),
    "schema-three": replace("schema_version", 3),
    "schema-bool": replace("schema_version", True),
    "schema-missing": drop("schema_version"),
    "profile-id-uppercase": replace("profile_id", "Managed-Remote"),
    "policy-mode-unknown": replace(
        "version_policy", {"mode": "auto", "allowed_versions": ["1.20.1"]}
    ),
    "policy-empty": replace(
        "version_policy", {"mode": "explicit_allowlist", "allowed_versions": []}
    ),
    "policy-not-list": replace(
        "version_policy", {"mode": "explicit_allowlist", "allowed_versions": "1.20.1"}
    ),
    "policy-garbage-version": replace(
        "version_policy", {"mode": "explicit_allowlist", "allowed_versions": ["latest"]}
    ),
    "policy-noncanonical-version": replace(
        "version_policy", {"mode": "explicit_allowlist", "allowed_versions": ["01.20"]}
    ),
    "policy-duplicate": replace(
        "version_policy", {"mode": "explicit_allowlist", "allowed_versions": ["1.20.1", "1.20.1"]}
    ),
    "policy-missing-mode": replace("version_policy", {"allowed_versions": ["1.20.1"]}),
    "policy-extra-key": replace(
        "version_policy",
        {"mode": "explicit_allowlist", "allowed_versions": ["1.20.1"], "prefer": "newest"},
    ),
    "policy-bool-entry": replace(
        "version_policy", {"mode": "explicit_allowlist", "allowed_versions": [True]}
    ),
    "policy-string": replace("version_policy", "explicit_allowlist"),
    "pinned-valid": replace("pinned_bundle_id", "p0-core-1.20.1"),
    "pinned-uppercase": replace("pinned_bundle_id", "Pinned"),
    "pinned-empty": replace("pinned_bundle_id", ""),
    "resource-packs-allow": replace("resource_pack_policy", "allow"),
    "authorization-missing": drop("target_authorization"),
    "authorization-granted-uppercase": replace(
        "target_authorization", {"granted_by": "Operator", "basis": "explicitly approved"}
    ),
    "authorization-short-basis": replace(
        "target_authorization", {"granted_by": "operator-local", "basis": "ok"}
    ),
    "authorization-extra-key": replace(
        "target_authorization",
        {"granted_by": "operator-local", "basis": "explicitly approved", "expires": "never"},
    ),
    "authorization-missing-basis": replace(
        "target_authorization", {"granted_by": "operator-local"}
    ),
    "authorization-string": replace("target_authorization", "trust me"),
    "v1-visibility-field": replace("visibility", "isolated_test_only"),
    "v1-minecraft-version": replace("minecraft_version", "1.20.1"),
}

# Where the product rule is deliberately stricter than the v2 schema: JSON Schema
# cannot express "a parseable, normalized IP literal", so the charset pattern
# stands in and the loader does the real parsing; the unconditional address
# blocks are a product rule no JSON Schema would carry. A float port diverges
# the way it does for v1. Any new divergence fails here instead of passing
# unnoticed.
KNOWN_STRICTER_V2 = frozenset(
    {
        "port-float",
        "host-partial",
        "host-leading-zero",
        "host-unnormalized",
        "host-uppercase",
        "host-mapped-loopback",
        "host-wildcard",
        "host-unspecified-v6",
        "host-link-local",
    }
)


@pytest.mark.parametrize("name", MUTATIONS_V2)
def test_product_validation_agrees_with_the_v2_schema(name: str, tmp_path: Path) -> None:
    """The v2 loader must accept exactly what the reviewed v2 schema accepts."""

    document = MUTATIONS_V2[name](json.loads(json.dumps(VALID_V2)))
    schema_errors = list(Draft202012Validator(SCHEMA_V2).iter_errors(document))

    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    try:
        load_managed_target_profile(path)
    except MinekinError:
        loader_accepted = False
    else:
        loader_accepted = True

    if name in KNOWN_STRICTER_V2:
        assert not loader_accepted, f"{name}: expected the stricter product rule to reject"
        assert not schema_errors, f"{name}: the schema tightened too; drop the exception"
        return

    assert loader_accepted == (not schema_errors), (
        f"{name}: schema_errors={[error.message for error in schema_errors]}"
    )
