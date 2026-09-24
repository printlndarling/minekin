"""Deterministic, side-effect-free W10 launch-plan construction."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.artifacts import store_relative_path
from minekin_core.adapters.launcher.metadata import (
    Artifact,
    TargetPlatform,
    load_pinned_metadata,
)
from minekin_core.adapters.launcher.recipe import validate_bundle_recipe
from minekin_core.adapters.launcher.saves import level_name_is_usable
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

_PLACEHOLDER = re.compile(r"^\$\{([a-zA-Z0-9_]+)\}$")

# A directory holding both of these is a workspace checkout rather than an
# installed copy. Counting parent directories instead is an accident of nesting
# depth that happens to work from the source tree and silently points inside
# site-packages once the package is installed.
WORKSPACE_MARKERS: tuple[str, ...] = ("bridge", "proto")

# Plan paths name one of two roots. The run root holds the immutable store and
# the read-only bundle; `session/` names the writable overlay for one session
# generation. The launch-plan contract puts the client's game directory at the
# overlay itself, not at a shared directory beside it, so `session/` with
# nothing after it is the overlay root and `session/natives` is a directory
# inside the overlay.
SESSION_PREFIX: str = "session/"
SESSION_OVERLAY_PATH: str = "session/"
SESSION_NATIVES_PATH: str = "session/natives"


def _reject(message: str, category: ErrorCategory = ErrorCategory.SUPPLY_CHAIN) -> MinekinError:
    """A plan that cannot be built. Supply chain by default; CONFIG for bad inputs.

    The category is not decoration: it is the exit code, and the same bad level
    name is refused here and in `launcher.saves`. Two categories for one input
    would mean two exit codes for it, decided by which check happened to run
    first.
    """

    return MinekinError("launcher.plan", "build", category, Retryability.OPERATOR_ACTION, message)


def find_workspace_root(start: Path) -> Path:
    """Walk up from `start` to the checkout that holds the Bridge and the protos."""

    for candidate in (start, *start.parents):
        if all((candidate / marker).is_dir() for marker in WORKSPACE_MARKERS):
            return candidate
    raise _reject(
        f"no Minekin workspace found above {start}: verifying a bundle recipe needs the "
        f"Bridge source tree, which an installed wheel does not carry. Run this from a "
        f"checkout, or pass the workspace root explicitly."
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
    """Ask the store where it will put this, rather than restating it.

    Restated, the two drifted: the plan left out the part of the store's layout
    that says these are blobs, and every classpath entry it produced named a
    file that was never written. Nothing compared the readiness check, which
    used the store, with the launch, which used the plan.
    """

    return store_relative_path(artifact)


#: The reviewed client argument that enters a singleplayer world without a menu.
#: Measured against the pinned 1.21.4 client: `RunArgs$QuickPlay` carries a
#: `singleplayer` field beside `multiplayer`, `realms` and `path`, and the
#: argument names are Mojang's own (`--quickPlaySingleplayer <level id>`).
QUICK_PLAY_SINGLEPLAYER = "--quickPlaySingleplayer"


def _game_argument_template(
    arguments: tuple[str, ...], world_name: str | None
) -> list[dict[str, str]]:
    """The metadata's game arguments, plus the world this run is asked to enter."""

    template = _typed_arguments(arguments)
    if world_name is None:
        return template
    # Refused rather than escaped, for two reasons that are not the same one:
    # this becomes an argv element, so a name that could be read as another
    # option is not a name this client may accept; and it also names the level
    # `saves/` will hold, so the rule that decides that is asked rather than
    # restated here. A plan that promised `--quickPlaySingleplayer a/b` would be
    # naming a launch that cannot be what it says.
    if world_name.startswith("-") or not level_name_is_usable(world_name):
        raise _reject(f"{world_name!r} is not a usable level name to enter", ErrorCategory.CONFIG)
    return [
        *template,
        {"kind": "literal", "value": QUICK_PLAY_SINGLEPLAYER},
        {"kind": "literal", "value": world_name},
    ]


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


def build_launch_plan(
    profile_path: Path,
    *,
    workspace_root: Path | None = None,
    world_name: str | None = None,
) -> dict[str, Any]:
    """The reviewed plan for one managed client, plus what this run asks of it.

    `world_name` is the one thing a caller may add to the reviewed metadata's game
    arguments: it makes the client enter that singleplayer world instead of
    stopping at the title screen, which is what a session that is meant to host a
    LAN world needs — a client at the title screen is running no integrated
    server for anything to join. It is a *literal* in the plan's own template, so
    the plan still says exactly which command line it will produce, and the plan's
    digest therefore names the launch rather than the scenario that asked for it.
    """
    profile_path = profile_path.resolve()
    workspace_root = workspace_root or find_workspace_root(Path(__file__).resolve())
    recipe_audit = validate_bundle_recipe(profile_path, workspace_root)
    profile = _load_object(profile_path)
    runtime_value = profile.get("runtime")
    if not isinstance(runtime_value, dict):
        raise _reject("bundle profile runtime must be an object")
    runtime = cast(dict[str, object], runtime_value)
    if runtime.get("os_arch") != "linux-x86_64":
        raise _reject("W10 currently accepts only the reviewed linux-x86_64 target")
    minecraft_value = profile.get("minecraft")
    if not isinstance(minecraft_value, dict) or not isinstance(
        cast(dict[str, object], minecraft_value).get("version"), str
    ):
        raise _reject("bundle profile minecraft.version is required")
    recipe_version = cast(str, cast(dict[str, object], minecraft_value)["version"])
    metadata = load_pinned_metadata(
        _metadata_path(profile_path, profile, "version_manifest"),
        _metadata_path(profile_path, profile, "version_json"),
        _metadata_path(profile_path, profile, "fabric_profile"),
        _metadata_path(profile_path, profile, "asset_index"),
        target=TargetPlatform("linux", "x86_64"),
        version=recipe_version,
    )
    ordered = [
        metadata.client,
        *metadata.resolved_libraries,
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
        for artifact in [metadata.client, *metadata.resolved_libraries]
        if artifact.kind != "native"
    ]
    native_artifacts = [
        _store_path(artifact)
        for artifact in metadata.resolved_libraries
        if artifact.kind == "native"
    ]
    replacements = {
        "${natives_directory}": SESSION_NATIVES_PATH,
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
            "game_arg_template": _game_argument_template(metadata.game_arguments, world_name),
            "classpath": classpath,
            "native_artifacts": native_artifacts,
            "native_extract_excludes": ["META-INF/"],
            "asset_index": _store_path(metadata.asset_index),
            "assets_index_name": metadata.asset_index_id,
            "assets_dir": "bundle/assets",
            "logging_config": _store_path(metadata.logging_config),
            "natives_dir": SESSION_NATIVES_PATH,
            # The contract makes the session overlay the client's game directory
            # rather than a sibling of it, so `session/` alone names the overlay.
            "game_dir": SESSION_OVERLAY_PATH,
            "version_type": metadata.version_type,
        },
        "metadata": {
            "base_sha256": metadata.base_metadata_sha256,
            "fabric_sha256": metadata.fabric_metadata_sha256,
        },
        "fixed_mods": [asdict(mod) for mod in recipe_audit.fixed_mods],
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


def artifacts_from_plan(plan: Mapping[str, Any]) -> tuple[Artifact, ...]:
    """Read back the artifacts a plan names, refusing a malformed entry.

    Every consumer of a plan needs this and none of them should coerce a broken
    entry into a plausible one: a wrong size or a missing digest that is read as
    a default is a verification that silently stops verifying.
    """

    entries = cast(list[object], plan.get("artifacts") or [])
    if not entries:
        raise _reject("launch plan names no artifacts")
    artifacts: list[Artifact] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise _reject("launch plan artifact entry is malformed: not an object")
        artifacts.append(_artifact_from(cast(Mapping[str, Any], entry)))
    return tuple(artifacts)


def _artifact_from(entry: Mapping[str, Any]) -> Artifact:
    try:
        size = entry["size"]
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("size")
        return Artifact(
            coordinate=str(entry["coordinate"]),
            path=str(entry["path"]),
            url=str(entry["url"]),
            size=size,
            sha1=str(entry["sha1"]),
            kind=str(entry.get("kind", "library")),
        )
    except (KeyError, TypeError) as error:
        raise _reject(f"launch plan artifact entry is malformed: {error}") from error
