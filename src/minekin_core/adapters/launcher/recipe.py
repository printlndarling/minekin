"""Strict validation of the single reviewed P0 bundle recipe."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

# The recipe's `fabric` section is what a reviewer reads to learn what the bundle
# is made of, so every value in it is pinned rather than decorative: `api` and
# `yarn` used to be unchecked, which let the readable statement disagree with the
# enforced one.
FABRIC_API_VERSION = "0.119.4+1.21.4"
FABRIC_YARN = "1.21.4+build.8"
FABRIC_API_URL = (
    "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/"
    "0.119.4+1.21.4/fabric-api-0.119.4+1.21.4.jar"
)
FABRIC_API_SIZE = 2_149_128
FABRIC_API_SHA256 = "d183bacb845167f09264c2f90322b7ecffe8826debda6f60e597889264bef4af"
# The content-addressed store keys by SHA-1 because that is what the upstream
# metadata publishes. The recipe pins SHA-256, so both are recorded: the pin is
# the stronger claim, and the SHA-1 is how the store finds the file. The value
# is the one the bootstrap contract and the supply-chain check already record.
FABRIC_API_SHA1 = "1c7871b6af04edc8b8f0dbad12606d67f6118a11"
# The Bridge is Minekin's own artifact, so no upstream publishes a digest for
# it: the supply-chain contract says an own artifact without one gets a fixed
# SHA-256 instead, and TLS is not accepted as the only integrity guarantee. The
# digest below is that pin, and it was shown to be reproducible off this
# machine: Windows with JDK 21.0.12.1+1-LTS-4 and Linux x86_64 with Temurin
# 21.0.12+8 both build this exact jar.
#
# The consequence is a stricter rule than the source digest alone: changing the
# Bridge source is not allowed to "just work". The jar has to be rebuilt and
# this pin renewed, because a plan that names this digest and ships other bytes
# is the failure the pin exists to catch.
BRIDGE_JAR_SHA256 = "afa12034611da7fffc79babd8af24314d3b72bbfcbe18e7f96fcdc9fd0c7b947"
BRIDGE_JAR_SIZE = 1_220_234
BRIDGE_JAR_RELATIVE_PATH = "bridge/build/libs/minekin-bridge-0.0.0.jar"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        component="launcher.recipe",
        operation="verify",
        category=ErrorCategory.SUPPLY_CHAIN,
        retryability=Retryability.OPERATOR_ACTION,
        safe_message=message,
    )


def _looks_binary(content: bytes) -> bool:
    """Git's own test: a NUL byte in the first 8000 bytes means binary."""

    return b"\0" in content[:8000]


def source_tree_sha256(root: Path) -> str:
    if not root.is_dir() or root.is_symlink():
        raise _reject(f"Bridge source root is missing or is a symlink: {root}")
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
        # The digest must answer "did the source change?", not "which platform
        # checked it out?". `core.autocrlf` rewrites some text files to CRLF on
        # Windows and leaves them LF elsewhere, and a whitelist of suffixes
        # decides that by accident: it listed `.java` and `.kts` but not `.xml`,
        # so `gradle/verification-metadata.xml` alone made one commit hash
        # differently on each platform and the recipe could not be reproduced
        # from both. Normalise whatever git would call text instead of guessing
        # by name, and leave true binaries byte-for-byte.
        if not _looks_binary(content):
            content = content.replace(b"\r\n", b"\n")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class FixedMod:
    """One mod the client must load, with everything needed to place it.

    `source` is either the pinned URL to fetch from or `workspace:<path>` for an
    artifact this repository builds. `sha1` is present only for a fetched mod,
    because it is the store's key there rather than a second opinion about the
    bytes.
    """

    name: str
    kind: str
    sha256: str
    size: int
    source: str
    sha1: str | None = None


@dataclass(frozen=True, slots=True)
class RecipeAudit:
    bundle_name: str
    fixed_mods: tuple[FixedMod, ...]
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
    expected_pins = (
        ("minecraft", "version", "1.21.4"),
        ("runtime", "java_major", 21),
        ("fabric", "loader", "0.16.9"),
        ("fabric", "api", FABRIC_API_VERSION),
        ("fabric", "yarn", FABRIC_YARN),
    )
    for section_name, field, expected in expected_pins:
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
            "verification": "sha256",
            "source": "workspace:bridge",
            "license": "NOASSERTION",
            "digest": BRIDGE_JAR_SHA256,
            "size": BRIDGE_JAR_SIZE,
        }.items()
    ):
        raise _reject("Bridge jar pin is not the reviewed build of the workspace source")
    actual_source_digest = source_tree_sha256(workspace_root / "bridge")
    if bridge.get("source_digest") != actual_source_digest:
        raise _reject("Bridge source tree digest differs from the bundle recipe")
    bundle_name = profile.get("bundle_name")
    if not isinstance(bundle_name, str) or not bundle_name:
        raise _reject("bundle_name is required")
    return RecipeAudit(
        bundle_name=bundle_name,
        fixed_mods=(
            FixedMod(
                name="fabric-api",
                kind="mod",
                sha256=FABRIC_API_SHA256,
                size=FABRIC_API_SIZE,
                source=FABRIC_API_URL,
                sha1=FABRIC_API_SHA1,
            ),
            FixedMod(
                name="minekin-bridge",
                kind="bridge",
                sha256=BRIDGE_JAR_SHA256,
                size=BRIDGE_JAR_SIZE,
                source=f"workspace:{BRIDGE_JAR_RELATIVE_PATH}",
            ),
        ),
        bridge_source_sha256=actual_source_digest,
        # Nothing is blocked: the recipe now pins the jar rather than saying it
        # has yet to be pinned. Whether that jar exists is a fact about the
        # build host, not about the plan, and `require_built_bridge` asks it at
        # start time — putting it here would make the plan's own digest depend
        # on what the machine happened to have built.
        blockers=(),
    )


def require_built_bridge(workspace_root: Path) -> Path:
    """The built Bridge jar, or a refusal saying what is wrong with it.

    A missing jar is a build that has not happened; a jar that is the wrong size
    or the wrong bytes is a different thing entirely, and both are refused here
    rather than discovered by a client that will not load the Bridge.
    """

    jar = workspace_root / BRIDGE_JAR_RELATIVE_PATH
    if not jar.is_file():
        raise _reject(
            f"the Bridge jar has not been built: {jar} is missing; "
            f"run `./gradlew build` in the bridge directory"
        )
    size = jar.stat().st_size
    if size != BRIDGE_JAR_SIZE:
        raise _reject(
            f"the Bridge jar is {size} bytes, not the reviewed {BRIDGE_JAR_SIZE}; "
            f"the pin no longer describes this build"
        )
    digest = hashlib.sha256(jar.read_bytes()).hexdigest()
    if digest != BRIDGE_JAR_SHA256:
        raise _reject(
            f"the Bridge jar is not the reviewed build of this source: {digest} is not "
            f"the pinned digest"
        )
    return jar
