"""Strict validation of the single reviewed P0 bundle recipe."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

FABRIC_API_URL = (
    "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/"
    "0.119.4+1.21.4/fabric-api-0.119.4+1.21.4.jar"
)
FABRIC_API_SIZE = 2_149_128
FABRIC_API_SHA256 = "d183bacb845167f09264c2f90322b7ecffe8826debda6f60e597889264bef4af"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        component="launcher.recipe",
        operation="verify",
        category=ErrorCategory.SUPPLY_CHAIN,
        retryability=Retryability.OPERATOR_ACTION,
        safe_message=message,
    )


def source_tree_sha256(root: Path) -> str:
    if not root.is_dir() or root.is_symlink():
        raise _reject("Bridge source root is missing or is a symlink")
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and not any(part in {".gradle", "build"} for part in path.relative_to(root).parts)
    )
    if not files:
        raise _reject("Bridge source tree is empty")
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        content = path.read_bytes()
        if (
            path.suffix in {".bat", ".java", ".json", ".kts", ".properties", ".toml"}
            or path.name == "gradlew"
        ):
            content = content.replace(b"\r\n", b"\n")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RecipeAudit:
    bundle_name: str
    fixed_mods: tuple[str, ...]
    bridge_source_sha256: str
    blockers: tuple[str, ...]


def _objects(value: object, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise _reject(f"{field} must be an array")
    result: list[dict[str, Any]] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise _reject(f"{field} entries must be objects")
        result.append(cast(dict[str, Any], item))
    return result


def validate_bundle_recipe(profile_path: Path, workspace_root: Path) -> RecipeAudit:
    try:
        value = json.loads(profile_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject("bundle recipe is not readable UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise _reject("bundle recipe must be an object")
    profile = cast(dict[str, Any], value)
    expected_pins = {
        "minecraft": ("version", "1.21.4"),
        "runtime": ("java_major", 21),
        "fabric": ("loader", "0.16.9"),
    }
    for section_name, (field, expected) in expected_pins.items():
        section = profile.get(section_name)
        if not isinstance(section, dict):
            raise _reject(f"bundle recipe {section_name} must be an object")
        section_value = cast(dict[str, object], section)
        if section_value.get(field) != expected:
            raise _reject(f"bundle recipe {section_name}.{field} is not the reviewed value")

    artifacts = _objects(profile.get("artifacts"), "artifacts")
    by_name: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        name = artifact.get("name")
        if not isinstance(name, str) or name in by_name:
            raise _reject("bundle recipe artifact names must be unique strings")
        by_name[name] = artifact
    if set(by_name) != {"fabric-api", "minekin-bridge"}:
        raise _reject("bundle recipe fixed mod set is not exactly p0-core")

    fabric_api = by_name["fabric-api"]
    required_api = {
        "kind": "mod",
        "verification": "sha256",
        "digest": FABRIC_API_SHA256,
        "size": FABRIC_API_SIZE,
        "source": FABRIC_API_URL,
        "license": "Apache-2.0",
    }
    if any(fabric_api.get(key) != expected for key, expected in required_api.items()):
        raise _reject("Fabric API artifact identity is not the reviewed release")

    bridge = by_name["minekin-bridge"]
    if any(
        bridge.get(key) != expected
        for key, expected in {
            "kind": "bridge",
            "verification": "build_required",
            "source": "workspace:bridge",
            "license": "NOASSERTION",
        }.items()
    ):
        raise _reject("Bridge build recipe is not the reviewed workspace source")
    actual_source_digest = source_tree_sha256(workspace_root / "bridge")
    if bridge.get("source_digest") != actual_source_digest:
        raise _reject("Bridge source tree digest differs from the bundle recipe")
    bundle_name = profile.get("bundle_name")
    if not isinstance(bundle_name, str) or not bundle_name:
        raise _reject("bundle_name is required")
    return RecipeAudit(
        bundle_name=bundle_name,
        fixed_mods=("fabric-api", "minekin-bridge"),
        bridge_source_sha256=actual_source_digest,
        blockers=("minekin-bridge: build required",),
    )
