from __future__ import annotations

import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.metadata import (
    FABRIC_MAIN_CLASS,
    VERSION_METADATA_SHA1,
    TargetPlatform,
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
        target=TARGET,
    )

    assert metadata.version == "1.21.4"
    assert metadata.java_major == 21
    assert metadata.fabric_main_class == FABRIC_MAIN_CLASS
    assert metadata.client.sha1 == "a7e5a6024bfd3cd614625aa05629adf760020304"
    assert metadata.asset_index_id == "19"
    assert metadata.source_library_count == 113
    assert len(metadata.libraries) == 70
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
            target=TARGET,
        )


def test_unknown_target_is_rejected_before_rule_evaluation() -> None:
    with pytest.raises(MinekinError, match="target OS"):
        TargetPlatform("plan9", "x86_64")


def test_version_metadata_sha1_pin_is_the_reviewed_value() -> None:
    import hashlib

    assert hashlib.sha1(_raw("1.21.4.json")).hexdigest() == VERSION_METADATA_SHA1
