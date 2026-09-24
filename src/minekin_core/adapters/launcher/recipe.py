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
# digest below is that pin. The bytes it names were rebuilt on Windows with JDK
# 21.0.12.1+1-LTS-4 after the Bridge gained the non-authoritative first-snapshot
# switch; the cross-platform demonstration (Windows and Linux x86_64 with Temurin
# 21.0.12+8 building one jar) was made for the bytes this pin replaced, and it
# has not been repeated for these.
#
# The consequence is a stricter rule than the source digest alone: changing the
# Bridge source is not allowed to "just work". The jar has to be rebuilt and
# this pin renewed, because a plan that names this digest and ships other bytes
# is the failure the pin exists to catch.
BRIDGE_JAR_SHA256 = "faeec4a9df83abb9ca0404863e04d20cfd87ac0f3afd5e74b6858e3e15372f55"
BRIDGE_JAR_SIZE = 1_308_525
BRIDGE_JAR_RELATIVE_PATH = "bridge/build/libs/minekin-bridge-0.0.0.jar"

# The second bundle. These are the reviewed pins for Minecraft 1.20.1, each one
# re-fetched and re-hashed from its authoritative upstream (see
# `docs/version-license-matrix.md`), not copied from the 1.21.4 stack.
MINECRAFT_1201_VERSION = "1.20.1"
MINECRAFT_1201_METADATA_SHA1 = "599695fee750ab157846886c6e69583003f22d07"
MINECRAFT_1201_JAVA_MAJOR = 17
FABRIC_LOADER_1201 = "0.19.5"
FABRIC_API_1201_VERSION = "0.92.12+1.20.1"
FABRIC_YARN_1201 = "1.20.1+build.10"
FABRIC_API_1201_URL = (
    "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/"
    "0.92.12+1.20.1/fabric-api-0.92.12+1.20.1.jar"
)
FABRIC_API_1201_SIZE = 2_137_232
FABRIC_API_1201_SHA256 = "4197ff4fbdac13cffccd267c1bc59e9fbabb2b5683a9d5f8023f4b5ea16a1c1e"
FABRIC_API_1201_SHA1 = "3e9cdd3e2f827ca9a259df9eb8e31949437b6bd4"

# The 1.20.1 Bridge lives in its own source root, `bridge-1201/`, rather than
# inside `bridge/`: the 1.21.4 recipe pins `source_digest` over that tree, so
# adding a second version's sources there would silently move the pinned
# identity of a bundle that has already been accepted. Its jar is pinned the
# same way 1.21.4's is — built twice, once on Windows with JDK 21.0.12.1+1-LTS-4
# and once in a Linux x86_64 Temurin 21 container, both producing the digest
# below from an empty Gradle cache with dependency verification enforced.
BRIDGE_1201_JAR_SHA256 = "9e162d8359a886394ddd80db87477d9196ef3d2972e7a4d942df54a2f1e349bc"
BRIDGE_1201_JAR_SIZE = 1_308_469
BRIDGE_1201_JAR_RELATIVE_PATH = "bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar"


@dataclass(frozen=True, slots=True)
class BridgeIdentity:
    """One reviewed Minecraft version's Bridge: which root builds it and what bytes
    that root's reviewed build produced.

    The source root has to be part of the identity rather than a constant, because
    a digest pinned for one root says nothing about another's build.
    """

    source_root: str
    jar_relative_path: str
    jar_sha256: str
    jar_size: int


def bridge_identity(minecraft_version: str) -> BridgeIdentity:
    """The reviewed Bridge for a version, or a refusal for one nothing pins.

    Read from the module constants rather than from a frozen table, because the
    tests that stand in for a reviewed build renew those constants; a snapshot
    taken at import would keep the real pins and the tests would pass without
    checking anything.
    """

    if minecraft_version == "1.21.4":
        return BridgeIdentity(
            source_root="bridge",
            jar_relative_path=BRIDGE_JAR_RELATIVE_PATH,
            jar_sha256=BRIDGE_JAR_SHA256,
            jar_size=BRIDGE_JAR_SIZE,
        )
    if minecraft_version == MINECRAFT_1201_VERSION:
        return BridgeIdentity(
            source_root="bridge-1201",
            jar_relative_path=BRIDGE_1201_JAR_RELATIVE_PATH,
            jar_sha256=BRIDGE_1201_JAR_SHA256,
            jar_size=BRIDGE_1201_JAR_SIZE,
        )
    raise _reject(f"no reviewed Bridge jar is pinned for Minecraft {minecraft_version}")


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
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and not any(part in {".gradle", "build"} for part in path.relative_to(root).parts)
        ),
        # Ordered by the path's own text rather than by the platform's idea of
        # path order. `sorted()` compares `Path` objects with `WindowsPath.__lt__`
        # on Windows, which is case-insensitive, and `PosixPath.__lt__` on Linux,
        # which is not — so a file and a directory whose names differ only in case
        # swap places between platforms and the same source tree hashes
        # differently on each. That is precisely the failure the comment below is
        # about, arriving by a second route. Codepoint order is the same
        # everywhere, and it is what both platforms must agree on.
        key=lambda path: path.relative_to(root).as_posix(),
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


def _candidate_1201_audit(profile: dict[str, Any], workspace_root: Path) -> RecipeAudit | None:
    """Validate a reviewed 1.20.1 *candidate* recipe, or return None if it is not one.

    `candidate` is the bundle's acceptance status, not a statement about its
    artifacts: the Bridge jar is pinned like 1.21.4's, because `bridge-1201/` has
    been built and its bytes measured, while no 1.20.1 client has entered a real
    server under acceptance. So a plan built from this recipe can be launched —
    which is what the card that proves it needs — and nothing here calls it
    `tested`.
    """

    version_section = profile.get("minecraft")
    if not isinstance(version_section, dict) or (
        cast(dict[str, object], version_section).get("version") != MINECRAFT_1201_VERSION
    ):
        return None

    expected_pins = (
        ("minecraft", "version", MINECRAFT_1201_VERSION),
        ("runtime", "java_major", MINECRAFT_1201_JAVA_MAJOR),
        ("fabric", "loader", FABRIC_LOADER_1201),
        ("fabric", "api", FABRIC_API_1201_VERSION),
        ("fabric", "yarn", FABRIC_YARN_1201),
    )
    for section_name, field, expected in expected_pins:
        section = profile.get(section_name)
        if not isinstance(section, dict):
            raise _reject(f"bundle recipe {section_name} must be an object")
        if cast(dict[str, object], section).get(field) != expected:
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
        "digest": FABRIC_API_1201_SHA256,
        "size": FABRIC_API_1201_SIZE,
        "source": FABRIC_API_1201_URL,
        "license": "Apache-2.0",
    }
    if any(fabric_api.get(key) != expected for key, expected in required_api.items()):
        raise _reject("Fabric API artifact identity is not the reviewed release")

    bridge = by_name["minekin-bridge"]
    identity = bridge_identity(MINECRAFT_1201_VERSION)
    if any(
        bridge.get(key) != expected
        for key, expected in {
            "kind": "bridge",
            "verification": "sha256",
            "source": f"workspace:{identity.source_root}",
            "license": "NOASSERTION",
            "digest": identity.jar_sha256,
            "size": identity.jar_size,
        }.items()
    ):
        raise _reject("candidate Bridge jar pin is not the reviewed build of the 1.20.1 root")
    candidate_source_digest = source_tree_sha256(workspace_root / identity.source_root)
    if bridge.get("source_digest") != candidate_source_digest:
        raise _reject("candidate Bridge source tree digest differs from the bundle recipe")

    bundle_name = profile.get("bundle_name")
    if not isinstance(bundle_name, str) or not bundle_name:
        raise _reject("bundle_name is required")
    return RecipeAudit(
        bundle_name=bundle_name,
        fixed_mods=(
            FixedMod(
                name="fabric-api",
                kind="mod",
                sha256=FABRIC_API_1201_SHA256,
                size=FABRIC_API_1201_SIZE,
                source=FABRIC_API_1201_URL,
                sha1=FABRIC_API_1201_SHA1,
            ),
            FixedMod(
                name="minekin-bridge",
                kind="bridge",
                sha256=identity.jar_sha256,
                size=identity.jar_size,
                source=f"workspace:{identity.jar_relative_path}",
            ),
        ),
        bridge_source_sha256=candidate_source_digest,
        # Nothing is blocked either: the recipe pins the 1.20.1 jar as it pins
        # 1.21.4's. What the candidate lacks is a real server accepting it, and
        # that is its `status`, not an unbuilt artifact.
        blockers=(),
    )


def validate_bundle_recipe(profile_path: Path, workspace_root: Path) -> RecipeAudit:
    try:
        value = json.loads(profile_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject("bundle recipe is not readable UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise _reject("bundle recipe must be an object")
    profile = cast(dict[str, Any], value)
    candidate = _candidate_1201_audit(profile, workspace_root)
    if candidate is not None:
        return candidate
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
    identity = bridge_identity("1.21.4")
    if any(
        bridge.get(key) != expected
        for key, expected in {
            "kind": "bridge",
            "verification": "sha256",
            "source": f"workspace:{identity.source_root}",
            "license": "NOASSERTION",
            "digest": identity.jar_sha256,
            "size": identity.jar_size,
        }.items()
    ):
        raise _reject("Bridge jar pin is not the reviewed build of the workspace source")
    actual_source_digest = source_tree_sha256(workspace_root / identity.source_root)
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
                sha256=identity.jar_sha256,
                size=identity.jar_size,
                source=f"workspace:{identity.jar_relative_path}",
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


def require_built_bridge(workspace_root: Path, minecraft_version: str) -> Path:
    """The built Bridge jar for one Minecraft version, or a refusal saying what is
    wrong with it.

    A missing jar is a build that has not happened; a jar that is the wrong size
    or the wrong bytes is a different thing entirely, and both are refused here
    rather than discovered by a client that will not load the Bridge. The version
    is a required argument because each one's jar is a different root's build: a
    default would let a plan for one version be checked against the other's pin.
    """

    identity = bridge_identity(minecraft_version)
    jar = workspace_root / identity.jar_relative_path
    if not jar.is_file():
        raise _reject(
            f"the Bridge jar has not been built: {jar} is missing; "
            f"run `./gradlew build` in the {identity.source_root} directory"
        )
    size = jar.stat().st_size
    if size != identity.jar_size:
        raise _reject(
            f"the Bridge jar is {size} bytes, not the reviewed {identity.jar_size}; "
            f"the pin no longer describes this build"
        )
    digest = hashlib.sha256(jar.read_bytes()).hexdigest()
    if digest != identity.jar_sha256:
        raise _reject(
            f"the Bridge jar is not the reviewed build of this source: {digest} is not "
            f"the pinned digest"
        )
    return jar
