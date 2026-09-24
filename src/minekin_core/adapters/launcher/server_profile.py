"""Trusted Server Profile loading.

A profile is a pinned, reviewed input document, not a value supplied by chat,
web content or model output. The frozen v1 schema is deliberately narrower than
Minecraft's own address handling: the only accepted hosts are the two loopback
literals, so a profile cannot express an arbitrary address, a name that DNS could
rebind, or a LAN scan target. Anything outside that set is rejected rather than
resolved.

The v2 schema adds the managed remote target: one explicit, normalized IP
literal the operator has authorized in this very document, plus a version
policy. Loading a v2 profile is still not connecting — the session start path
consumes v1 documents only until the switch card wires v2 in, and every v2
endpoint is expressed as a single-address policy that a resolved address must
satisfy again.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from minekin_core.domain.admission import AddressPolicy, decide_endpoint
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

PROFILE_SCHEMA_VERSION = 1
MINECRAFT_VERSION = "1.21.4"

PROFILE_SCHEMA_VERSION_V2 = 2
_VERSION_POLICY_MODES = frozenset({"explicit_allowlist"})
_MC_VERSION = re.compile(r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")
_MIN_AUTHORIZATION_BASIS = 4
_V2_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "profile_id",
        "host",
        "port",
        "auth_mode",
        "version_policy",
        "resource_pack_policy",
        "target_authorization",
    }
)
_V2_OPTIONAL_KEYS = frozenset({"pinned_bundle_id"})
_V2_POLICY_KEYS = frozenset({"mode", "allowed_versions"})
_V2_AUTHORIZATION_KEYS = frozenset({"granted_by", "basis"})

_RESOURCE_PACK_POLICIES = frozenset({"deny", "prompt"})
_PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]+$")
_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "profile_id",
        "host",
        "port",
        "auth_mode",
        "minecraft_version",
        "visibility",
        "resource_pack_policy",
    }
)


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.profile",
        "load",
        ErrorCategory.ADMISSION,
        Retryability.OPERATOR_ACTION,
        message,
    )


@dataclass(frozen=True, slots=True)
class ServerProfile:
    """One validated, immutable admission target."""

    profile_id: str
    host: str
    port: int
    auth_mode: str
    minecraft_version: str
    visibility: str
    resource_pack_policy: str
    revision: str

    @property
    def is_loopback(self) -> bool:
        return decide_endpoint(AddressPolicy.p0_loopback(), self.host, self.port).allowed

    def endpoint(self) -> str:
        """The socket endpoint, with IPv6 bracketed the way a client needs it."""

        return f"[{self.host}]:{self.port}" if ":" in self.host else f"{self.host}:{self.port}"

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "host": self.host,
            "port": self.port,
            "auth_mode": self.auth_mode,
            "minecraft_version": self.minecraft_version,
            "visibility": self.visibility,
            "resource_pack_policy": self.resource_pack_policy,
            "revision": self.revision,
        }


def _text(document: dict[str, object], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise _reject(f"server profile {key} must be a non-empty string")
    return value


def _read_object_document(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    if ".minecraft" in {part.lower() for part in resolved.parts}:
        raise _reject("host .minecraft paths are forbidden")
    try:
        document = json.loads(resolved.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject("server profile is not readable UTF-8 JSON") from error
    if not isinstance(document, dict):
        raise _reject("server profile must be an object")
    return cast("dict[str, object]", document)


def _sub_object(document: dict[str, object], key: str) -> dict[str, object]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise _reject(f"server profile {key} must be an object")
    return cast("dict[str, object]", value)


def _exact_keys(
    document: dict[str, object], required: frozenset[str], name: str, extra_allowed: frozenset[str]
) -> None:
    unknown = sorted(set(document) - required - extra_allowed)
    if unknown:
        raise _reject(f"server profile {name} has unreviewed fields: " + ", ".join(unknown))
    missing = sorted(required - set(document))
    if missing:
        raise _reject(f"server profile {name} is missing fields: " + ", ".join(missing))


def _port(document: dict[str, object]) -> int:
    value = document.get("port")
    # bool is an int subclass; a JSON `true` port must not validate.
    if isinstance(value, bool) or not isinstance(value, int):
        raise _reject("server profile port must be an integer")
    if not 1 <= value <= 65535:
        raise _reject("server profile port must be within 1-65535")
    return value


def load_server_profile(path: Path) -> ServerProfile:
    """Load and validate a frozen v1 loopback profile; every deviation is fail-closed."""

    profile = _read_object_document(path)

    unknown = sorted(set(profile) - _REQUIRED_KEYS)
    if unknown:
        raise _reject("server profile has unreviewed fields: " + ", ".join(unknown))
    missing = sorted(_REQUIRED_KEYS - set(profile))
    if missing:
        raise _reject("server profile is missing fields: " + ", ".join(missing))

    schema_version = profile["schema_version"]
    # `True == 1` in Python and a JSON float with a zero fraction is a schema-valid
    # integer, but neither is a usable revision for a pinned document.
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise _reject("server profile schema_version must be an integer")
    if schema_version != PROFILE_SCHEMA_VERSION:
        raise _reject("server profile schema_version is not the reviewed revision")

    profile_id = _text(profile, "profile_id")
    if not _PROFILE_ID.fullmatch(profile_id):
        raise _reject("server profile profile_id is not a lowercase reference")

    host = _text(profile, "host")
    port = _port(profile)
    decision = decide_endpoint(AddressPolicy.p0_loopback(), host, port)
    if not decision.allowed:
        reasons = ", ".join(reason.value for reason in decision.reasons)
        raise _reject(
            f"P0 admits only a saved loopback profile ({reasons}); no LAN scan or DNS name"
        )

    if _text(profile, "auth_mode") != "offline":
        raise _reject("P0 has no online-mode admission path")

    if _text(profile, "minecraft_version") != MINECRAFT_VERSION:
        raise _reject("server profile minecraft_version is outside the pinned bundle")

    if _text(profile, "visibility") != "isolated_test_only":
        raise _reject("server profile visibility is not isolated_test_only")

    resource_packs = _text(profile, "resource_pack_policy")
    if resource_packs not in _RESOURCE_PACK_POLICIES:
        raise _reject("server profile resource_pack_policy is not reviewed")

    canonical = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    return ServerProfile(
        profile_id=profile_id,
        host=host,
        port=port,
        auth_mode="offline",
        minecraft_version=MINECRAFT_VERSION,
        visibility="isolated_test_only",
        resource_pack_policy=resource_packs,
        revision=hashlib.sha256(canonical).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class ManagedTargetProfile:
    """One operator-authorized remote target with its version policy.

    The saved literal is the whole address policy: whatever a later probe or
    resolution produces must satisfy it again before anything connects to it.
    """

    profile_id: str
    host: str
    port: int
    auth_mode: str
    version_policy_mode: str
    allowed_versions: tuple[str, ...]
    pinned_bundle_id: str | None
    resource_pack_policy: str
    authorization_granted_by: str
    authorization_basis: str
    revision: str

    @property
    def is_loopback(self) -> bool:
        return decide_endpoint(AddressPolicy.p0_loopback(), self.host, self.port).allowed

    def address_policy(self) -> AddressPolicy:
        return AddressPolicy.for_explicit_target(self.host)

    def endpoint(self) -> str:
        return f"[{self.host}]:{self.port}" if ":" in self.host else f"{self.host}:{self.port}"

    def as_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "schema_version": PROFILE_SCHEMA_VERSION_V2,
            "profile_id": self.profile_id,
            "host": self.host,
            "port": self.port,
            "auth_mode": self.auth_mode,
            "version_policy": {
                "mode": self.version_policy_mode,
                "allowed_versions": list(self.allowed_versions),
            },
            "resource_pack_policy": self.resource_pack_policy,
            "target_authorization": {
                "granted_by": self.authorization_granted_by,
                "basis": self.authorization_basis,
            },
            "revision": self.revision,
        }
        if self.pinned_bundle_id is not None:
            document["pinned_bundle_id"] = self.pinned_bundle_id
        return document


def _reference(document: dict[str, object], key: str) -> str:
    value = _text(document, key)
    if not _PROFILE_ID.fullmatch(value):
        raise _reject(f"server profile {key} is not a lowercase reference")
    return value


def _literal_host(document: dict[str, object]) -> str:
    host = _text(document, "host")
    try:
        parsed = ipaddress.ip_address(host)
    except ValueError as error:
        raise _reject(
            "server profile host must be an explicit IP literal, not a resolvable name"
        ) from error
    if str(parsed) != host:
        raise _reject("server profile host must be the normalized form of its literal")
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        # An embedded IPv4 hides an A-family endpoint behind a v6 policy and
        # slips past the v4-shaped unconditional blocks; require the real family.
        raise _reject("server profile host must not be an IPv4-mapped IPv6 literal")
    return host


def _version_policy(document: dict[str, object]) -> tuple[str, tuple[str, ...]]:
    policy = _sub_object(document, "version_policy")
    _exact_keys(policy, _V2_POLICY_KEYS, "version_policy", frozenset())
    mode = _text(policy, "mode")
    if mode not in _VERSION_POLICY_MODES:
        raise _reject("server profile version_policy mode is not reviewed")
    versions = policy["allowed_versions"]
    if isinstance(versions, bool) or not isinstance(versions, list):
        raise _reject("server profile version_policy allowed_versions must be an array")
    candidates = cast("list[object]", versions)
    if not candidates:
        raise _reject("server profile version_policy allowed_versions must not be empty")
    resolved: list[str] = []
    for entry in candidates:
        if not isinstance(entry, str) or not _MC_VERSION.fullmatch(entry):
            raise _reject("server profile version_policy entries must be release versions")
        if entry in resolved:
            raise _reject("server profile version_policy entries must be distinct")
        resolved.append(entry)
    return mode, tuple(resolved)


def _target_authorization(document: dict[str, object]) -> tuple[str, str]:
    authorization = _sub_object(document, "target_authorization")
    _exact_keys(authorization, _V2_AUTHORIZATION_KEYS, "target_authorization", frozenset())
    granted_by = _reference(authorization, "granted_by")
    basis = _text(authorization, "basis")
    if len(basis) < _MIN_AUTHORIZATION_BASIS:
        raise _reject("server profile target_authorization basis is too short to review")
    return granted_by, basis


def load_managed_target_profile(path: Path) -> ManagedTargetProfile:
    """Load a v2 managed remote profile; saving a target is not connecting to it.

    Nothing in this module reaches the network: the v2 document is validated
    and its single-target address policy derived, and the session start path
    keeps consuming v1 documents until the switch card wires this one in.
    """

    document = _read_object_document(path)

    unknown = sorted(set(document) - _V2_REQUIRED_KEYS - _V2_OPTIONAL_KEYS)
    if unknown:
        raise _reject("server profile has unreviewed fields: " + ", ".join(unknown))
    missing = sorted(_V2_REQUIRED_KEYS - set(document))
    if missing:
        raise _reject("server profile is missing fields: " + ", ".join(missing))

    schema_version = document["schema_version"]
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise _reject("server profile schema_version must be an integer")
    if schema_version != PROFILE_SCHEMA_VERSION_V2:
        raise _reject("server profile schema_version is not the reviewed revision")

    profile_id = _reference(document, "profile_id")
    host = _literal_host(document)
    port = _port(document)

    if _text(document, "auth_mode") != "offline":
        raise _reject("v2 profiles have no online-mode admission path")

    mode, allowed_versions = _version_policy(document)

    pinned: str | None = None
    if "pinned_bundle_id" in document:
        pinned = _reference(document, "pinned_bundle_id")

    resource_packs = _text(document, "resource_pack_policy")
    if resource_packs not in _RESOURCE_PACK_POLICIES:
        raise _reject("server profile resource_pack_policy is not reviewed")

    granted_by, basis = _target_authorization(document)

    # Re-check the saved endpoint against the very policy this profile exports.
    # For a literal it can only fail on the unconditional blocks, which is the
    # point: an operator cannot pin the metadata address even "explicitly".
    decision = decide_endpoint(AddressPolicy.for_explicit_target(host), host, port)
    if not decision.allowed:
        reasons = ", ".join(reason.value for reason in decision.reasons)
        raise _reject(f"server profile target is refused by the address policy ({reasons})")

    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return ManagedTargetProfile(
        profile_id=profile_id,
        host=host,
        port=port,
        auth_mode="offline",
        version_policy_mode=mode,
        allowed_versions=allowed_versions,
        pinned_bundle_id=pinned,
        resource_pack_policy=resource_packs,
        authorization_granted_by=granted_by,
        authorization_basis=basis,
        revision=hashlib.sha256(canonical).hexdigest(),
    )
