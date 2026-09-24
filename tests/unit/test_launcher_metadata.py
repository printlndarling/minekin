from __future__ import annotations

import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.metadata import (
    FABRIC_MAIN_CLASS,
    VERSION_METADATA_SHA1,
    Artifact,
    PinnedMetadata,
    TargetPlatform,
    library_key,
    load_pinned_metadata,
    parse_pinned_metadata,
)
from minekin_core.domain.errors import MinekinError

FIXTURES = Path(__file__).parents[1] / "fixtures" / "launcher"
TARGET = TargetPlatform("linux", "x86_64")


def _raw(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_pinned_metadata_resolves_linux_x86_64() -> None:
    metadata = load_pinned_metadata(
        FIXTURES / "version_manifest_v2.json",
        FIXTURES / "1.21.4.json",
        FIXTURES / "fabric-loader-0.16.9.json",
        FIXTURES / "asset-index-19.json",
        target=TARGET,
    )

    assert metadata.version == "1.21.4"
    assert metadata.java_major == 21
    assert metadata.fabric_main_class == FABRIC_MAIN_CLASS
    assert metadata.client.sha1 == "a7e5a6024bfd3cd614625aa05629adf760020304"
    assert metadata.asset_index_id == "19"
    assert metadata.asset_index.sha1 == "8d07e20a532738f3ee13392a23871abb5927fd79"
    assert len(metadata.asset_objects) == 4039
    assert sum(item.size for item in metadata.asset_objects) == 421_518_376
    assert metadata.logging_config.kind == "logging"
    assert metadata.source_library_count == 113
    assert len(metadata.libraries) == 70
    assert sum(item.kind == "native" for item in metadata.libraries) == 9
    assert len(metadata.fabric_coordinates) == 8
    assert "-cp" in metadata.jvm_arguments
    assert "${classpath}" in metadata.jvm_arguments
    assert all(artifact.url.startswith("https://") for artifact in metadata.libraries)
    assert all(artifact.size > 0 for artifact in metadata.libraries)


def test_version_metadata_tampering_fails_closed() -> None:
    version = _raw("1.21.4.json") + b"\n"
    with pytest.raises(MinekinError, match="digest"):
        parse_pinned_metadata(
            _raw("version_manifest_v2.json"),
            version,
            _raw("fabric-loader-0.16.9.json"),
            _raw("asset-index-19.json"),
            target=TARGET,
        )


def test_manifest_cannot_redirect_the_pinned_version() -> None:
    manifest = json.loads(_raw("version_manifest_v2.json"))
    entry = next(item for item in manifest["versions"] if item["id"] == "1.21.4")
    entry["url"] = "https://example.invalid/1.21.4.json"
    with pytest.raises(MinekinError, match="pinned metadata identity"):
        parse_pinned_metadata(
            json.dumps(manifest).encode(),
            _raw("1.21.4.json"),
            _raw("fabric-loader-0.16.9.json"),
            _raw("asset-index-19.json"),
            target=TARGET,
        )


def test_asset_index_tampering_fails_closed() -> None:
    with pytest.raises(MinekinError, match="asset index digest"):
        parse_pinned_metadata(
            _raw("version_manifest_v2.json"),
            _raw("1.21.4.json"),
            _raw("fabric-loader-0.16.9.json"),
            _raw("asset-index-19.json") + b"\n",
            target=TARGET,
        )


def test_fabric_profile_inheritance_is_exact() -> None:
    fabric = json.loads(_raw("fabric-loader-0.16.9.json"))
    fabric["inheritsFrom"] = "1.21.5"
    with pytest.raises(MinekinError, match="inheritance"):
        parse_pinned_metadata(
            _raw("version_manifest_v2.json"),
            _raw("1.21.4.json"),
            json.dumps(fabric).encode(),
            _raw("asset-index-19.json"),
            target=TARGET,
        )


def test_unknown_target_is_rejected_before_rule_evaluation() -> None:
    with pytest.raises(MinekinError, match="target OS"):
        TargetPlatform("plan9", "x86_64")


def test_version_metadata_sha1_pin_is_the_reviewed_value() -> None:
    import hashlib

    assert hashlib.sha1(_raw("1.21.4.json")).hexdigest() == VERSION_METADATA_SHA1


def _pinned() -> PinnedMetadata:
    return load_pinned_metadata(
        FIXTURES / "version_manifest_v2.json",
        FIXTURES / "1.21.4.json",
        FIXTURES / "fabric-loader-0.16.9.json",
        FIXTURES / "asset-index-19.json",
        target=TARGET,
    )


def test_the_fabric_profile_replaces_the_libraries_it_restates() -> None:
    """Two versions of one library on the classpath stops the Loader outright.

    Minecraft ships ASM 9.6 and Fabric 0.16.9 states ASM 9.7.1, so this is not a
    question of which one wins: the Loader refuses to start when it finds two
    copies of a class it needs, and that is what it did.
    """

    metadata = _pinned()

    parent = {library_key(item): item for item in metadata.libraries}
    resolved = {library_key(item): item for item in metadata.resolved_libraries}

    assert parent["org.ow2.asm:asm"].coordinate == "org.ow2.asm:asm:9.6"
    assert resolved["org.ow2.asm:asm"].coordinate == "org.ow2.asm:asm:9.7.1"
    assert resolved["org.ow2.asm:asm"] in metadata.fabric_libraries

    # It replaces rather than filters: nothing else the parent stated is gone,
    # and the only artifact that changed is the one the profile restated.
    assert set(parent) <= set(resolved)
    assert len(resolved) == len(parent) + len(metadata.fabric_libraries) - 1


def test_a_native_is_a_build_of_the_library_it_overrides() -> None:
    """The classifier says which build, not which artifact, so it is not the key."""

    native = Artifact(
        coordinate="org.lwjgl:lwjgl:3.3.3:natives-linux",
        path="org/lwjgl/lwjgl/3.3.3/lwjgl-3.3.3-natives-linux.jar",
        url="https://example.invalid/lwjgl-natives.jar",
        size=1,
        sha1="0" * 40,
        kind="native",
    )

    assert library_key(native) == "org.lwjgl:lwjgl"


def test_pinned_metadata_resolves_the_reviewed_1201_candidate() -> None:
    """The 1.20.1 candidate parses against its own pins, not 1.21.4's.

    Every figure here was read from the pinned upstream documents and the two
    Fabric libs the profile ships without a checksum resolve through the
    registry to their Maven .jar.sha1 digests.
    """

    metadata = load_pinned_metadata(
        FIXTURES / "version_manifest_v2.json",
        FIXTURES / "1.20.1.json",
        FIXTURES / "fabric-loader-0.19.5.json",
        FIXTURES / "asset-index-5.json",
        target=TARGET,
        version="1.20.1",
    )

    assert metadata.version == "1.20.1"
    assert metadata.java_major == 17
    assert metadata.client.sha1 == "0c3ec587af28e5a785c0b4a7b8a30f9a8f78f838"
    assert metadata.asset_index_id == "5"
    assert metadata.asset_index.sha1 == "78fe335ef048443d060bc53ace10bb0f41af7d50"
    assert len(metadata.asset_objects) == 3598
    assert sum(item.size for item in metadata.asset_objects) == 650_534_850
    assert metadata.source_library_count == 88
    assert len(metadata.libraries) == 52
    assert sum(item.kind == "native" for item in metadata.libraries) == 7
    assert len(metadata.fabric_coordinates) == 8

    by_coordinate = {item.coordinate: item for item in metadata.fabric_libraries}
    assert by_coordinate["net.fabricmc:intermediary:1.20.1"].sha1 == (
        "97d0bff94981e37bd7a4362deee53c9a84e3fb21"
    )
    assert by_coordinate["net.fabricmc:intermediary:1.20.1"].size == 573365
    assert by_coordinate["net.fabricmc:fabric-loader:0.19.5"].sha1 == (
        "ff9e65cffca4a67f31523e1807fe0855940fcbfa"
    )
    assert by_coordinate["net.fabricmc:fabric-loader:0.19.5"].size == 1984980


def test_1201_metadata_fails_closed_against_a_mismatched_digest() -> None:
    """Feeding the 1.21.4 bytes to the 1.20.1 pins is refused, not quietly accepted."""

    with pytest.raises(MinekinError, match="digest does not match the pinned SHA-1"):
        parse_pinned_metadata(
            _raw("version_manifest_v2.json"),
            _raw("1.21.4.json"),
            _raw("fabric-loader-0.19.5.json"),
            _raw("asset-index-5.json"),
            target=TARGET,
            version="1.20.1",
        )


def test_an_unreviewed_version_has_no_pins() -> None:
    with pytest.raises(MinekinError, match="no reviewed metadata pins"):
        parse_pinned_metadata(
            _raw("version_manifest_v2.json"),
            _raw("1.20.1.json"),
            _raw("fabric-loader-0.19.5.json"),
            _raw("asset-index-5.json"),
            target=TARGET,
            version="1.19.2",
        )
