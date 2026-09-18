"""Validate the Bridge build pins without resolving Minecraft artifacts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge"


def require_text(path: Path, expected: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [item for item in expected if item not in text]
    if missing:
        raise SystemExit(f"{path.relative_to(ROOT)} is missing pins: {', '.join(missing)}")


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
