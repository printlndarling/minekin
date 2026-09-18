"""Trusted Server Profile loading.

A profile is a pinned, reviewed input document, not a value supplied by chat,
web content or model output. The frozen v1 schema is deliberately narrower than
Minecraft's own address handling: the only accepted hosts are the two loopback
literals, so a profile cannot express an arbitrary address, a name that DNS could
rebind, or a LAN scan target. Anything outside that set is rejected rather than
resolved.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

PROFILE_SCHEMA_VERSION = 1
MINECRAFT_VERSION = "1.21.4"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})
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
        return self.host in _LOOPBACK_HOSTS

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


def _port(document: dict[str, object]) -> int:
    value = document.get("port")
    # bool is an int subclass; a JSON `true` port must not validate.
    if isinstance(value, bool) or not isinstance(value, int):
        raise _reject("server profile port must be an integer")
    if not 1 <= value <= 65535:
        raise _reject("server profile port must be within 1-65535")
    return value


def load_server_profile(path: Path) -> ServerProfile:
    """Load and validate one trusted profile; every deviation is fail-closed."""

    resolved = path.resolve()
    if ".minecraft" in {part.lower() for part in resolved.parts}:
        raise _reject("host .minecraft paths are forbidden")
    try:
        document = json.loads(resolved.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject("server profile is not readable UTF-8 JSON") from error
    if not isinstance(document, dict):
        raise _reject("server profile must be an object")
    profile = cast(dict[str, object], document)

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
    if host not in _LOOPBACK_HOSTS:
        raise _reject("P0 admits only a saved loopback profile; no LAN scan or DNS name")

    port = _port(profile)

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
