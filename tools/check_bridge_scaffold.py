"""Validate the Bridge build pins without resolving Minecraft artifacts."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge"

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


def check_verification_metadata() -> None:
    """Verification stays on, and the list of things exempt from it does not grow.

    Two assertions rather than one. The first is that the metadata is still a
    *verification* metadata file: a change that relaxed both at once would leave the
    trusted list looking unchanged while nothing was verified at all.
    """

    root = ElementTree.parse(BRIDGE / "gradle" / "verification-metadata.xml").getroot()
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


def main() -> None:
    require_text(
        BRIDGE / "gradle" / "libs.versions.toml",
        (
            "1.21.4",
            "0.16.9",
            "0.119.4+1.21.4",
            "1.21.4+build.8",
            "1.9.2",
            "4.36.2",
            "0.10.0",
        ),
    )
    require_text(
        BRIDGE / "gradle" / "wrapper" / "gradle-wrapper.properties",
        ("gradle-8.12.1-bin.zip", "distributionSha256Sum=", "validateDistributionUrl=true"),
    )
    require_text(
        BRIDGE / "build.gradle.kts",
        (
            "JavaLanguageVersion.of(21)",
            "lockAllConfigurations",
            "alias(libs.plugins.protobuf)",
            'srcDir("../proto")',
            'option("lite")',
            # The control-boundary contract's sixth case is a sentence about the
            # build: server state injected into the sources, a class, a mixin or an
            # access widener must make the *build* fail. The gate that decides that
            # has to be attached to `check` for the sentence to be true, and an
            # attachment nothing pins is an attachment somebody can delete in a
            # commit that looks like a build tweak — leaving the artifact gate
            # passing when it is run by hand and absent from every build.
            "checkHostBoundaryArtifacts",
            "dependsOn(checkHostBoundaryArtifacts)",
        ),
    )
    require_text(
        BRIDGE / "gradle.lockfile",
        (
            "com.google.protobuf:protobuf-javalite:4.36.2=",
            "net.fabricmc:fabric-loader:0.16.9=",
        ),
    )
    require_text(BRIDGE / "settings-gradle.lockfile", ("empty=incomingCatalogForLibs0",))
    check_verification_metadata()
    require_text(
        BRIDGE / "gradle" / "verification-metadata.xml",
        (
            '<component group="com.google.protobuf" name="protobuf-javalite" version="4.36.2">',
            '<component group="fabric-loom" name="fabric-loom.gradle.plugin" version="1.9.2">',
            '<component group="net.fabricmc" name="fabric-loader" version="0.16.9">',
        ),
    )
    manifest = json.loads((BRIDGE / "src" / "main" / "resources" / "fabric.mod.json").read_text())
    if manifest["environment"] != "client" or manifest["id"] != "minekin_bridge":
        raise SystemExit("Fabric manifest must remain a client-only minekin_bridge mod")
    if manifest["depends"] != {
        "fabricloader": "=0.16.9",
        "fabric-api": "=0.119.4+1.21.4",
        "java": ">=21",
        "minecraft": "=1.21.4",
    }:
        raise SystemExit("Bridge manifest dependencies are not the reviewed p0-core set")
    require_text(
        BRIDGE
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
    print("Minekin Bridge scaffold pins: OK")


if __name__ == "__main__":
    main()
