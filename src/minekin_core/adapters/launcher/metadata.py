"""Strict parsing for the pinned Minecraft and Fabric launcher metadata."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

MINECRAFT_VERSION = "1.21.4"
VERSION_METADATA_SHA1 = "d152a3712859b294a2dff641f99a7fe219cd3aec"
VERSION_METADATA_URL = (
    f"https://piston-meta.mojang.com/v1/packages/{VERSION_METADATA_SHA1}/{MINECRAFT_VERSION}.json"
)
BASE_MAIN_CLASS = "net.minecraft.client.main.Main"
FABRIC_LOADER = "0.16.9"
FABRIC_MAIN_CLASS = "net.fabricmc.loader.impl.launch.knot.KnotClient"
JAVA_MAJOR = 21
ASSET_INDEX_SHA1 = "8d07e20a532738f3ee13392a23871abb5927fd79"

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_KNOWN_OS_NAMES = frozenset({"linux", "osx", "windows"})
_KNOWN_RULE_FEATURES = frozenset(
    {
        "has_custom_resolution",
        "has_quick_plays_support",
        "is_demo_user",
        "is_quick_play_multiplayer",
        "is_quick_play_realms",
        "is_quick_play_singleplayer",
    }
)


def _reject(message: str, *, context: Mapping[str, object] | None = None) -> MinekinError:
    return MinekinError(
        component="launcher.metadata",
        operation="parse",
        category=ErrorCategory.SUPPLY_CHAIN,
        retryability=Retryability.OPERATOR_ACTION,
        safe_message=message,
        context=context or {},
    )


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _reject(f"{field} must be an object")
    return cast(dict[str, Any], value)


def _array(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise _reject(f"{field} must be an array")
    return cast(list[Any], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _reject(f"{field} must be a non-empty string")
    return value


def _integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _reject(f"{field} must be an integer")
    return value


def _https_url(value: object, field: str) -> str:
    url = _text(value, field)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise _reject(f"{field} must be an authority-only HTTPS URL")
    return url


def _load_json(raw: bytes, field: str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject(f"{field} is not valid UTF-8 JSON") from error
    return _object(decoded, field)


@dataclass(frozen=True, slots=True)
class TargetPlatform:
    os_name: str
    architecture: str

    def __post_init__(self) -> None:
        if self.os_name not in _KNOWN_OS_NAMES:
            raise _reject("target OS is not supported", context={"os_name": self.os_name})
        if self.architecture not in {"x86", "x86_64", "arm64"}:
            raise _reject(
                "target architecture is not supported",
                context={"architecture": self.architecture},
            )


@dataclass(frozen=True, slots=True)
class Artifact:
    coordinate: str
    path: str
    url: str
    size: int
    sha1: str
    kind: str = "library"


@dataclass(frozen=True, slots=True)
class PinnedMetadata:
    version: str
    java_major: int
    base_main_class: str
    fabric_main_class: str
    asset_index_id: str
    client: Artifact
    asset_index: Artifact
    asset_objects: tuple[Artifact, ...]
    logging_config: Artifact
    logging_argument: str
    source_library_count: int
    libraries: tuple[Artifact, ...]
    jvm_arguments: tuple[str, ...]
    game_arguments: tuple[str, ...]
    base_metadata_sha256: str
    fabric_metadata_sha256: str
    fabric_coordinates: tuple[str, ...]
    fabric_libraries: tuple[Artifact, ...]


_FABRIC_CHECKSUM_REGISTRY = {
    "net.fabricmc:intermediary:1.21.4": ("de610a8c6216662541bf345ba07ab8d099e1ec25", 701826),
    "net.fabricmc:fabric-loader:0.16.9": ("7eaa23079ac1569963e488054db124c7eb984f05", 1387357),
}


def _maven_artifact(entry: Mapping[str, Any]) -> Artifact:
    coordinate = _text(entry.get("name"), "Fabric library.name")
    parts = coordinate.split(":")
    if len(parts) != 3 or not all(parts):
        raise _reject("Fabric library coordinate is not group:artifact:version")
    group, name, version = parts
    relative = f"{group.replace('.', '/')}/{name}/{version}/{name}-{version}.jar"
    base_url = _https_url(entry.get("url"), f"Fabric library {coordinate}.url")
    sha1 = entry.get("sha1")
    size = entry.get("size")
    if sha1 is None or size is None:
        registered = _FABRIC_CHECKSUM_REGISTRY.get(coordinate)
        if registered is None:
            raise _reject("Fabric library has no reviewed checksum sidecar")
        sha1, size = registered
    return _artifact(
        {"path": relative, "url": f"{base_url.rstrip('/')}/{relative}", "sha1": sha1, "size": size},
        coordinate,
    )


def _rule_matches(rule: Mapping[str, Any], target: TargetPlatform) -> bool:
    unknown = set(rule) - {"action", "os", "features"}
    if unknown:
        raise _reject("metadata rule has unknown fields", context={"fields": sorted(unknown)})
    action = _text(rule.get("action"), "rule.action")
    if action not in {"allow", "disallow"}:
        raise _reject("metadata rule action is unknown", context={"action": action})

    os_constraint = rule.get("os")
    if os_constraint is not None:
        os_rule = _object(os_constraint, "rule.os")
        unknown_os = set(os_rule) - {"name", "arch", "version"}
        if unknown_os:
            raise _reject(
                "metadata OS rule has unknown fields", context={"fields": sorted(unknown_os)}
            )
        if "version" in os_rule:
            raise _reject("host OS version rules require an explicitly registered runtime")
        name = os_rule.get("name")
        if name is not None:
            name = _text(name, "rule.os.name")
            if name not in _KNOWN_OS_NAMES:
                raise _reject("metadata rule names an unknown OS", context={"os_name": name})
            if name != target.os_name:
                return False
        arch = os_rule.get("arch")
        if arch is not None and _text(arch, "rule.os.arch") != target.architecture:
            return False

    features = rule.get("features")
    if features is not None:
        feature_map = _object(features, "rule.features")
        unknown_features = set(feature_map) - _KNOWN_RULE_FEATURES
        if unknown_features:
            raise _reject(
                "metadata rule names an unknown feature",
                context={"features": sorted(unknown_features)},
            )
        # W10 never enables demo, custom resolution, or quick-play features.
        if any(bool(required) for required in feature_map.values()):
            return False
    return True


def rules_allow(rules: object, target: TargetPlatform) -> bool:
    if rules is None:
        return True
    values = _array(rules, "rules")
    allowed = False
    for value in values:
        rule = _object(value, "rule")
        if _rule_matches(rule, target):
            allowed = _text(rule.get("action"), "rule.action") == "allow"
    return allowed


def _arguments(values: object, target: TargetPlatform, field: str) -> tuple[str, ...]:
    result: list[str] = []
    for index, value in enumerate(_array(values, field)):
        if isinstance(value, str):
            result.append(value)
            continue
        entry = _object(value, f"{field}[{index}]")
        if set(entry) != {"rules", "value"}:
            raise _reject(f"{field}[{index}] has an unknown shape")
        if not rules_allow(entry["rules"], target):
            continue
        argument = entry["value"]
        if isinstance(argument, str):
            result.append(argument)
        else:
            result.extend(
                _text(item, f"{field}[{index}].value")
                for item in _array(argument, f"{field}[{index}].value")
            )
    return tuple(result)


def _artifact(
    value: object,
    coordinate: str,
    kind: str = "library",
    *,
    default_path: str | None = None,
) -> Artifact:
    data = _object(value, f"artifact {coordinate}")
    sha1 = _text(data.get("sha1"), f"artifact {coordinate}.sha1")
    if not _SHA1.fullmatch(sha1):
        raise _reject("artifact SHA-1 is malformed", context={"coordinate": coordinate})
    size = _integer(data.get("size"), f"artifact {coordinate}.size")
    if size <= 0:
        raise _reject("artifact size must be positive", context={"coordinate": coordinate})
    path_value = data.get("path", default_path)
    path = _text(path_value, f"artifact {coordinate}.path")
    if path.startswith(("/", "\\")) or ".." in Path(path).parts or "\\" in path:
        raise _reject("artifact path is unsafe", context={"coordinate": coordinate})
    return Artifact(
        coordinate=coordinate,
        path=path,
        url=_https_url(data.get("url"), f"artifact {coordinate}.url"),
        size=size,
        sha1=sha1,
        kind=kind,
    )


def _validate_manifest(raw: bytes) -> None:
    manifest = _load_json(raw, "version manifest")
    matches: list[dict[str, Any]] = []
    for item in _array(manifest.get("versions"), "version manifest.versions"):
        entry = _object(item, "version manifest entry")
        if entry.get("id") == MINECRAFT_VERSION:
            matches.append(entry)
    if len(matches) != 1:
        raise _reject("version manifest must contain exactly one pinned version")
    entry = matches[0]
    if entry.get("sha1") != VERSION_METADATA_SHA1 or entry.get("url") != VERSION_METADATA_URL:
        raise _reject("version manifest does not match the pinned metadata identity")


def parse_pinned_metadata(
    manifest_raw: bytes,
    version_raw: bytes,
    fabric_raw: bytes,
    asset_index_raw: bytes,
    *,
    target: TargetPlatform,
) -> PinnedMetadata:
    """Validate pinned upstream responses and resolve the target-specific base plan."""

    _validate_manifest(manifest_raw)
    actual_sha1 = hashlib.sha1(version_raw).hexdigest()
    if actual_sha1 != VERSION_METADATA_SHA1:
        raise _reject(
            "version metadata digest does not match the pinned SHA-1",
            context={"actual_sha1": actual_sha1},
        )
    version = _load_json(version_raw, "version metadata")
    if version.get("id") != MINECRAFT_VERSION:
        raise _reject("version metadata id does not match the bundle recipe")
    java = _object(version.get("javaVersion"), "javaVersion")
    if _integer(java.get("majorVersion"), "javaVersion.majorVersion") != JAVA_MAJOR:
        raise _reject("version metadata requires an unexpected Java major")
    if version.get("mainClass") != BASE_MAIN_CLASS:
        raise _reject("base main class is not the reviewed entrypoint")

    downloads = _object(version.get("downloads"), "downloads")
    client = _artifact(
        downloads.get("client"),
        "com.mojang:minecraft:1.21.4",
        "client",
        default_path="versions/1.21.4/1.21.4.jar",
    )
    assets = _object(version.get("assetIndex"), "assetIndex")
    asset_index_id = _text(assets.get("id"), "assetIndex.id")
    if assets.get("sha1") != ASSET_INDEX_SHA1:
        raise _reject("asset index identity differs from the reviewed response")
    asset_index = _artifact(
        assets,
        f"com.mojang:assets:{asset_index_id}",
        "asset-index",
        default_path=f"assets/indexes/{asset_index_id}.json",
    )
    if hashlib.sha1(asset_index_raw).hexdigest() != ASSET_INDEX_SHA1:
        raise _reject("asset index digest does not match the pinned SHA-1")
    asset_index_document = _load_json(asset_index_raw, "asset index")
    asset_values = _object(asset_index_document.get("objects"), "asset index.objects")
    asset_objects: list[Artifact] = []
    total_asset_size = 0
    for logical_name, raw_object in sorted(asset_values.items()):
        asset_object = _object(raw_object, f"asset object {logical_name}")
        digest = _text(asset_object.get("hash"), f"asset object {logical_name}.hash")
        size = _integer(asset_object.get("size"), f"asset object {logical_name}.size")
        if not _SHA1.fullmatch(digest) or size <= 0:
            raise _reject("asset object identity is malformed")
        total_asset_size += size
        asset_objects.append(
            Artifact(
                coordinate=f"asset:{logical_name}",
                path=f"assets/objects/{digest[:2]}/{digest}",
                url=f"https://resources.download.minecraft.net/{digest[:2]}/{digest}",
                size=size,
                sha1=digest,
                kind="asset",
            )
        )
    if total_asset_size != _integer(assets.get("totalSize"), "assetIndex.totalSize"):
        raise _reject("asset index total size differs from version metadata")

    logging = _object(version.get("logging"), "logging")
    logging_client = _object(logging.get("client"), "logging.client")
    if logging_client.get("type") != "log4j2-xml":
        raise _reject("logging configuration type is not reviewed")
    logging_file = _object(logging_client.get("file"), "logging.client.file")
    logging_id = _text(logging_file.get("id"), "logging.client.file.id")
    logging_config = _artifact(
        logging_file,
        f"com.mojang:logging:{logging_id}",
        "logging",
        default_path=f"logging/{logging_id}",
    )
    logging_argument = _text(logging_client.get("argument"), "logging.client.argument")
    if logging_argument != "-Dlog4j.configurationFile=${path}":
        raise _reject("logging JVM argument is not the reviewed template")

    source_libraries = _array(version.get("libraries"), "libraries")
    if len(source_libraries) != 113:
        raise _reject(
            "version metadata library count differs from the reviewed response",
            context={"library_count": len(source_libraries)},
        )
    libraries: list[Artifact] = []
    for item in source_libraries:
        library = _object(item, "library")
        coordinate = _text(library.get("name"), "library.name")
        if not rules_allow(library.get("rules"), target):
            continue
        library_downloads = _object(library.get("downloads"), f"library {coordinate}.downloads")
        kind = "native" if ":natives-" in coordinate else "library"
        libraries.append(_artifact(library_downloads.get("artifact"), coordinate, kind))

    arguments = _object(version.get("arguments"), "arguments")
    jvm_arguments = _arguments(arguments.get("jvm"), target, "arguments.jvm")
    game_arguments = _arguments(arguments.get("game"), target, "arguments.game")

    fabric = _load_json(fabric_raw, "Fabric profile")
    if fabric.get("inheritsFrom") != MINECRAFT_VERSION:
        raise _reject("Fabric profile inheritance does not match the pinned Minecraft version")
    if fabric.get("mainClass") != FABRIC_MAIN_CLASS:
        raise _reject("Fabric profile main class is not the reviewed Knot client")
    fabric_library_entries = [
        _object(item, "Fabric library")
        for item in _array(fabric.get("libraries"), "Fabric libraries")
    ]
    coordinates = tuple(
        _text(item.get("name"), "Fabric library.name") for item in fabric_library_entries
    )
    if f"net.fabricmc:fabric-loader:{FABRIC_LOADER}" not in coordinates:
        raise _reject("Fabric profile does not contain the pinned loader")
    if f"net.fabricmc:intermediary:{MINECRAFT_VERSION}" not in coordinates:
        raise _reject("Fabric profile does not contain the pinned intermediary mappings")
    fabric_arguments = _object(fabric.get("arguments"), "Fabric arguments")
    jvm_arguments += _arguments(fabric_arguments.get("jvm", []), target, "Fabric arguments.jvm")
    game_arguments += _arguments(fabric_arguments.get("game", []), target, "Fabric arguments.game")

    return PinnedMetadata(
        version=MINECRAFT_VERSION,
        java_major=JAVA_MAJOR,
        base_main_class=BASE_MAIN_CLASS,
        fabric_main_class=FABRIC_MAIN_CLASS,
        asset_index_id=asset_index_id,
        client=client,
        asset_index=asset_index,
        asset_objects=tuple(asset_objects),
        logging_config=logging_config,
        logging_argument=logging_argument,
        source_library_count=len(source_libraries),
        libraries=tuple(libraries),
        jvm_arguments=jvm_arguments,
        game_arguments=game_arguments,
        base_metadata_sha256=hashlib.sha256(version_raw).hexdigest(),
        fabric_metadata_sha256=hashlib.sha256(fabric_raw).hexdigest(),
        fabric_coordinates=coordinates,
        fabric_libraries=tuple(_maven_artifact(item) for item in fabric_library_entries),
    )


def load_pinned_metadata(
    manifest_path: Path,
    version_path: Path,
    fabric_path: Path,
    asset_index_path: Path,
    *,
    target: TargetPlatform,
) -> PinnedMetadata:
    return parse_pinned_metadata(
        manifest_path.read_bytes(),
        version_path.read_bytes(),
        fabric_path.read_bytes(),
        asset_index_path.read_bytes(),
        target=target,
    )
