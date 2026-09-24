"""Validate the Bridge build pins without resolving Minecraft artifacts.

One entry per Bridge source root. Each root is a complete Loom project of its own
because the launcher hashes a root as a whole into the recipe that pins it, so a
second Minecraft version cannot live inside the first root's tree. That makes the
pins a per-root fact, and the gate reads them per root: a new root joins this file
by saying what was reviewed for it, not by relaxing what another root already pins.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RootPins:
    """What was reviewed for one Bridge source root."""

    root: Path
    #: Strings the version catalogue must contain.
    versions: tuple[str, ...]
    #: Strings the build script must contain, including the release level it compiles
    #: to and the gate attachment that makes the boundary contract a build fact.
    build: tuple[str, ...]
    #: Locked coordinates the lockfile must carry.
    lockfile: tuple[str, ...]
    #: Components the verification metadata must pin.
    metadata_components: tuple[str, ...]
    #: The manifest's dependency block, asserted as an exact mapping rather than as
    #: substrings: this is what the loader enforces at runtime.
    manifest_depends: dict[str, str]


#: Shared pins: Loom, protobuf and the Gradle wrapper are the same for every root, so
#: they stay in the strings below rather than becoming a per-root exception.
_COMMON_BUILD_PINS = (
    "lockAllConfigurations",
    "alias(libs.plugins.protobuf)",
    'srcDir("../proto")',
    'option("lite")',
    # The control-boundary contract's sixth case is a sentence about the build: server
    # state injected into the sources, a class, a mixin or an access widener must make
    # the *build* fail. The gate that decides that has to be attached to `check` for the
    # sentence to be true, and an attachment nothing pins is an attachment somebody can
    # delete in a commit that looks like a build tweak — leaving the artifact gate
    # passing when it is run by hand and absent from every build.
    "checkHostBoundaryArtifacts",
    "dependsOn(checkHostBoundaryArtifacts)",
)

BRIDGE_ROOTS = (
    RootPins(
        root=ROOT / "bridge",
        versions=(
            "1.21.4",
            "0.16.9",
            "0.119.4+1.21.4",
            "1.21.4+build.8",
            "1.9.2",
            "4.36.2",
            "0.10.0",
        ),
        build=("JavaLanguageVersion.of(21)", "options.release = 21", *_COMMON_BUILD_PINS),
        lockfile=(
            "com.google.protobuf:protobuf-javalite:4.36.2=",
            "net.fabricmc:fabric-loader:0.16.9=",
        ),
        metadata_components=(
            '<component group="com.google.protobuf" name="protobuf-javalite" version="4.36.2">',
            '<component group="fabric-loom" name="fabric-loom.gradle.plugin" version="1.9.2">',
            '<component group="net.fabricmc" name="fabric-loader" version="0.16.9">',
        ),
        manifest_depends={
            "fabricloader": "=0.16.9",
            "fabric-api": "=0.119.4+1.21.4",
            "java": ">=21",
            "minecraft": "=1.21.4",
        },
    ),
    RootPins(
        root=ROOT / "bridge-1201",
        versions=(
            "1.20.1",
            "0.19.5",
            "0.92.12+1.20.1",
            "1.20.1+build.10",
            "1.9.2",
            "4.36.2",
            "0.10.0",
        ),
        build=("JavaLanguageVersion.of(21)", "options.release = 17", *_COMMON_BUILD_PINS),
        lockfile=(
            "com.google.protobuf:protobuf-javalite:4.36.2=",
            "net.fabricmc:fabric-loader:0.19.5=",
        ),
        metadata_components=(
            '<component group="com.google.protobuf" name="protobuf-javalite" version="4.36.2">',
            '<component group="fabric-loom" name="fabric-loom.gradle.plugin" version="1.9.2">',
            '<component group="net.fabricmc" name="fabric-loader" version="0.19.5">',
        ),
        manifest_depends={
            "fabricloader": "=0.19.5",
            "fabric-api": "=0.92.12+1.20.1",
            "java": ">=17",
            "minecraft": "=1.20.1",
        },
    ),
)

#: The XML namespace Gradle's verification metadata is written in.
VERIFICATION_NAMESPACE = "https://schema.gradle.org/dependency-verification"

#: What Gradle's dependency verification is told *not* to verify, as an exact set.
#:
#: Loom synthesizes both namespaces and writes every zip entry in a remapped
#: dependency jar with the time of that remap, so a recorded digest for one can
#: never be satisfied by a fresh build — on any platform, including the machine that
#: recorded it. A control that can only ever fail is not a control, and the honest
#: configuration is to trust what is *built* while everything *fetched* stays
#: verified: the mappings, the Minecraft jars, Fabric's API and loader, and every
#: native.
#:
#: Checked as an exact set rather than as "at least these strings appear", because
#: widening it trusts artifacts without verifying them and that is the change this
#: guard exists to make visible.
TRUSTED_ARTIFACTS: tuple[dict[str, str], ...] = (
    {"group": "net_fabricmc_yarn_.*", "regex": "true"},
    {"group": "net.minecraft", "name": "minecraft-merged-.*", "regex": "true"},
)


def require_text(path: Path, expected: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [item for item in expected if item not in text]
    if missing:
        raise SystemExit(f"{path.relative_to(ROOT)} is missing pins: {', '.join(missing)}")


def check_verification_metadata(bridge: Path) -> None:
    """Verification stays on, and the list of things exempt from it does not grow.

    Two assertions rather than one. The first is that the metadata is still a
    *verification* metadata file: a change that relaxed both at once would leave the
    trusted list looking unchanged while nothing was verified at all.
    """

    root = ElementTree.parse(bridge / "gradle" / "verification-metadata.xml").getroot()
    verifying = root.find(f".//{{{VERIFICATION_NAMESPACE}}}verify-metadata")
    if verifying is None or (verifying.text or "").strip() != "true":
        raise SystemExit("dependency verification must stay on for the Bridge build")

    found = [dict(element.attrib) for element in root.iter(f"{{{VERIFICATION_NAMESPACE}}}trust")]
    expected = [dict(entry) for entry in TRUSTED_ARTIFACTS]
    if found != expected:
        raise SystemExit(
            "the exemptions from dependency verification are not the reviewed ones: "
            f"{found!r} rather than {expected!r}; everything on this list is trusted "
            "without being verified, so widening it is a deliberate change"
        )


def check_root(pins: RootPins) -> None:
    bridge = pins.root
    require_text(bridge / "gradle" / "libs.versions.toml", pins.versions)
    require_text(
        bridge / "gradle" / "wrapper" / "gradle-wrapper.properties",
        ("gradle-8.12.1-bin.zip", "distributionSha256Sum=", "validateDistributionUrl=true"),
    )
    require_text(bridge / "build.gradle.kts", pins.build)
    require_text(bridge / "gradle.lockfile", pins.lockfile)
    require_text(bridge / "settings-gradle.lockfile", ("empty=incomingCatalogForLibs0",))
    check_verification_metadata(bridge)
    require_text(bridge / "gradle" / "verification-metadata.xml", pins.metadata_components)
    manifest = json.loads((bridge / "src" / "main" / "resources" / "fabric.mod.json").read_text())
    if manifest["environment"] != "client" or manifest["id"] != "minekin_bridge":
        raise SystemExit("Fabric manifest must remain a client-only minekin_bridge mod")
    if manifest["depends"] != pins.manifest_depends:
        raise SystemExit(
            f"Bridge manifest dependencies of {bridge.name} are not the reviewed set for "
            f"its Minecraft version: {manifest['depends']!r} rather than "
            f"{pins.manifest_depends!r}"
        )
    require_text(
        bridge
        / "src"
        / "main"
        / "java"
        / "org"
        / "minekin"
        / "bridge"
        / "MinekinBridgeClient.java",
        (
            "MINEKIN_BRIDGE_DESCRIPTOR",
            "ClientTickEvents.END_CLIENT_TICK.register",
            "ClientLifecycleEvents.CLIENT_STOPPING.register",
            "created.start()",
        ),
    )


def main() -> None:
    for pins in BRIDGE_ROOTS:
        check_root(pins)
    print(f"Minekin Bridge scaffold pins: OK ({len(BRIDGE_ROOTS)} root(s))")


if __name__ == "__main__":
    main()
