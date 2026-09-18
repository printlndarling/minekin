"""Deterministic, side-effect-free W10 launch-plan construction."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.metadata import Artifact, TargetPlatform, load_pinned_metadata
from minekin_core.adapters.launcher.recipe import validate_bundle_recipe
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

_PLACEHOLDER = re.compile(r"^\$\{([a-zA-Z0-9_]+)\}$")


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.plan", "build", ErrorCategory.SUPPLY_CHAIN, Retryability.OPERATOR_ACTION, message
    )


def _load_object(path: Path) -> dict[str, Any]:
    if ".minecraft" in {part.lower() for part in path.resolve().parts}:
        raise _reject("host .minecraft paths are forbidden")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject("bundle profile is not readable UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise _reject("bundle profile must be an object")
    return cast(dict[str, Any], value)


def _metadata_path(profile_path: Path, profile: dict[str, Any], key: str) -> Path:
    metadata_value = profile.get("metadata")
    if not isinstance(metadata_value, dict):
        raise _reject(f"bundle profile metadata.{key} is required")
    metadata = cast(dict[str, object], metadata_value)
    path_value = metadata.get(key)
    if not isinstance(path_value, str):
        raise _reject(f"bundle profile metadata.{key} is required")
    return (profile_path.parent / path_value).resolve()


def _store_path(artifact: Artifact) -> str:
    return f"artifact-store/sha1/{artifact.sha1[:2]}/{artifact.sha1}/{Path(artifact.path).name}"


def _typed_arguments(arguments: tuple[str, ...]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for argument in arguments:
        match = _PLACEHOLDER.fullmatch(argument)
        if match:
            result.append({"kind": "placeholder", "name": match.group(1)})
        elif "${" in argument:
            raise _reject("embedded or malformed argument placeholder is forbidden")
        else:
            result.append({"kind": "literal", "value": argument})
    return result


def build_launch_plan(profile_path: Path, *, workspace_root: Path | None = None) -> dict[str, Any]:
    profile_path = profile_path.resolve()
    workspace_root = workspace_root or Path(__file__).resolve().parents[4]
    recipe_audit = validate_bundle_recipe(profile_path, workspace_root)
    profile = _load_object(profile_path)
    runtime_value = profile.get("runtime")
    if not isinstance(runtime_value, dict):
        raise _reject("bundle profile runtime must be an object")
    runtime = cast(dict[str, object], runtime_value)
    if runtime.get("os_arch") != "linux-x86_64":
        raise _reject("W10 currently accepts only the reviewed linux-x86_64 target")
    metadata = load_pinned_metadata(
        _metadata_path(profile_path, profile, "version_manifest"),
        _metadata_path(profile_path, profile, "version_json"),
        _metadata_path(profile_path, profile, "fabric_profile"),
        _metadata_path(profile_path, profile, "asset_index"),
        target=TargetPlatform("linux", "x86_64"),
    )
    ordered = [
        metadata.client,
        *metadata.libraries,
        *metadata.fabric_libraries,
        metadata.asset_index,
        *metadata.asset_objects,
        metadata.logging_config,
    ]
    by_path: dict[str, Artifact] = {}
    for artifact in ordered:
        existing = by_path.get(artifact.path)
        if existing is not None and existing.sha1 != artifact.sha1:
            raise _reject("two artifacts claim the same immutable path")
        by_path.setdefault(artifact.path, artifact)
    artifacts = list(by_path.values())
    classpath = [
        _store_path(artifact)
        for artifact in [metadata.client, *metadata.libraries, *metadata.fabric_libraries]
        if artifact.kind != "native"
    ]
    native_artifacts = [
        _store_path(artifact) for artifact in metadata.libraries if artifact.kind == "native"
    ]
    replacements = {
        "${natives_directory}": "session/natives",
        "${launcher_name}": "minekin",
        "${launcher_version}": "0.0.0",
        "${classpath}": ":".join(classpath),
    }
    jvm_args: list[str] = []
    for argument in metadata.jvm_arguments:
        resolved = argument
        for placeholder, replacement in replacements.items():
            resolved = resolved.replace(placeholder, replacement)
        jvm_args.append(resolved)
    jvm_args.append(
        metadata.logging_argument.replace("${path}", _store_path(metadata.logging_config))
    )
    if any("${" in argument for argument in jvm_args):
        raise _reject("JVM argument contains an unresolved placeholder")
    recipe_artifacts_value = profile.get("artifacts")
    if not isinstance(recipe_artifacts_value, list):
        raise _reject("bundle profile artifacts must be an array")
    blockers: list[str] = []
    for item_value in cast(list[object], recipe_artifacts_value):
        if not isinstance(item_value, dict):
            raise _reject("bundle profile artifact must be an object")
        item = cast(dict[str, object], item_value)
        if item.get("verification") == "build_required":
            name = item.get("name")
            if not isinstance(name, str):
                raise _reject("bundle profile artifact name is required")
            blockers.append(f"{name}: build required")
    fabric = cast(dict[str, Any], profile["fabric"])
    plan: dict[str, Any] = {
        "schema_version": 1,
        "status": "dry_run",
        "launchable": not blockers,
        "blockers": blockers,
        "bundle": {
            "minecraft": metadata.version,
            "java_major": metadata.java_major,
            "os_arch": runtime["os_arch"],
            "fabric_loader": fabric["loader"],
            "fabric_api": fabric["api"],
            "main_class": metadata.fabric_main_class,
        },
        "artifacts": [asdict(item) | {"store_path": _store_path(item)} for item in artifacts],
        "runtime": {
            "jvm_args": jvm_args,
            "game_arg_template": _typed_arguments(metadata.game_arguments),
            "classpath": classpath,
            "native_artifacts": native_artifacts,
            "native_extract_excludes": ["META-INF/"],
            "asset_index": _store_path(metadata.asset_index),
            "assets_index_name": metadata.asset_index_id,
            "assets_dir": "bundle/assets",
            "logging_config": _store_path(metadata.logging_config),
            "natives_dir": "session/natives",
            "game_dir": "session/game",
            "version_type": metadata.version_type,
        },
        "metadata": {
            "base_sha256": metadata.base_metadata_sha256,
            "fabric_sha256": metadata.fabric_metadata_sha256,
        },
        "fixed_mods": list(recipe_audit.fixed_mods),
        "bridge_source_sha256": recipe_audit.bridge_source_sha256,
    }
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    plan["plan_sha256"] = hashlib.sha256(canonical).hexdigest()
    return plan


def game_environment(plan: Mapping[str, Any]) -> dict[str, str]:
    """The non-session game argument values: paths and version identity.

    Session material is deliberately absent. It is joined at launch time so one
    reviewed bundle can serve an identity revision it was not built against.
    """

    runtime_value = plan.get("runtime")
    bundle_value = plan.get("bundle")
    if not isinstance(runtime_value, dict) or not isinstance(bundle_value, dict):
        raise _reject("launch plan is missing its runtime or bundle section")
    runtime = cast(dict[str, Any], runtime_value)
    bundle = cast(dict[str, Any], bundle_value)
    environment = {
        "version_name": bundle.get("minecraft"),
        "version_type": runtime.get("version_type"),
        "game_directory": runtime.get("game_dir"),
        "assets_root": runtime.get("assets_dir"),
        "assets_index_name": runtime.get("assets_index_name"),
    }
    for name, value in environment.items():
        if not isinstance(value, str) or not value:
            raise _reject(f"launch plan has no {name} game argument value")
    return cast(dict[str, str], environment)
