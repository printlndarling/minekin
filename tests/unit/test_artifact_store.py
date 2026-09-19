from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.artifacts import (
    ArtifactStore,
    BundleEntry,
    BundleStore,
    SessionOverlayStore,
)
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.domain.errors import MinekinError


def _artifact(payload: bytes, *, path: str = "example/demo.jar") -> Artifact:
    return Artifact(
        coordinate="example:demo:1",
        path=path,
        url="https://example.invalid/demo.jar",
        size=len(payload),
        sha1=hashlib.sha1(payload).hexdigest(),
    )


def test_install_is_content_addressed_read_only_and_idempotent(tmp_path: Path) -> None:
    payload = b"verified artifact"
    artifact = _artifact(payload)
    store = ArtifactStore(tmp_path / "artifacts")

    installed = store.install(artifact, io.BytesIO(payload))

    assert installed == store.path_for(artifact)
    assert installed.read_bytes() == payload
    assert installed.stat().st_mode & 0o222 == 0
    assert store.install(artifact, io.BytesIO(b"unused")) == installed


def test_failed_integrity_is_quarantined_and_never_published(tmp_path: Path) -> None:
    artifact = _artifact(b"expected")
    store = ArtifactStore(tmp_path / "artifacts")

    with pytest.raises(MinekinError, match="digest"):
        store.install(artifact, io.BytesIO(b"tampered"))

    assert not store.path_for(artifact).exists()
    quarantined = list(store.quarantine.rglob("payload.part"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == b"tampered"


def test_bundle_publish_is_atomic_immutable_and_verifiable(tmp_path: Path) -> None:
    payload = b"client"
    artifact = _artifact(payload, path="versions/1.21.4/client.jar")
    artifacts = ArtifactStore(tmp_path / "artifacts")
    artifacts.install(artifact, io.BytesIO(payload))
    bundles = BundleStore(tmp_path / "bundles", artifacts)

    plan = {"schema_version": 1, "plan_sha256": "abc"}
    entries = [BundleEntry("classpath/client.jar", artifact)]
    bundle_id = bundles.bundle_id_for(plan, entries)
    bundle = bundles.publish(bundle_id, plan, entries)

    assert bundle == bundles.verify(bundle_id)
    assert (bundle / "classpath" / "client.jar").read_bytes() == payload
    assert (bundle / "classpath" / "client.jar").stat().st_mode & 0o222 == 0
    manifest = json.loads((bundle / "bundle-manifest.json").read_bytes())
    assert manifest["bundle_id"] == bundle_id
    assert not any(bundles.staging.iterdir())


def test_bundle_rejects_duplicate_or_traversing_view_paths(tmp_path: Path) -> None:
    payload = b"client"
    artifact = _artifact(payload)
    artifacts = ArtifactStore(tmp_path / "artifacts")
    artifacts.install(artifact, io.BytesIO(payload))
    bundles = BundleStore(tmp_path / "bundles", artifacts)

    with pytest.raises(MinekinError, match="unsafe"):
        entries = [BundleEntry("../escape.jar", artifact)]
        bundles.bundle_id_for({}, entries)
    assert not (tmp_path / "escape.jar").exists()


def test_bundle_verification_detects_tampering_and_undeclared_files(tmp_path: Path) -> None:
    payload = b"client"
    artifact = _artifact(payload)
    artifacts = ArtifactStore(tmp_path / "artifacts")
    artifacts.install(artifact, io.BytesIO(payload))
    bundles = BundleStore(tmp_path / "bundles", artifacts)
    plan = {"schema_version": 1}
    entries = [BundleEntry("classpath/client.jar", artifact)]
    bundle_id = bundles.bundle_id_for(plan, entries)
    bundle = bundles.publish(bundle_id, plan, entries)
    installed = bundle / "classpath" / "client.jar"
    installed.chmod(installed.stat().st_mode | 0o200)
    installed.write_bytes(b"tampered")

    with pytest.raises(MinekinError, match="digest"):
        bundles.verify(bundle_id)


def test_session_overlay_is_generation_scoped_and_writable(tmp_path: Path) -> None:
    overlays = SessionOverlayStore(tmp_path / "sessions")

    first = overlays.create("session-01", 1)
    second = overlays.create("session-01", 2)

    assert first != second
    # The overlay is the client's run directory, so it carries the directories a
    # Minecraft client expects, `mods` among them.
    assert {path.name for path in first.iterdir()} == {
        "cache",
        "crash-reports",
        "ipc",
        "logs",
        "mods",
        "server-resource-packs",
        "session.json",
    }
    probe = first / "logs" / "probe.txt"
    probe.write_text("writable", encoding="utf-8")
    assert probe.read_text(encoding="utf-8") == "writable"
    with pytest.raises(MinekinError, match="already exists"):
        overlays.create("session-01", 1)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_managed_root_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    link = root / "sessions"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks requires an unavailable OS privilege")
    with pytest.raises(MinekinError, match="symlink"):
        SessionOverlayStore(link)
