"""Driving the fetcher over a plan, with the network replaced by a fake opener."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import BinaryIO

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.fetch import ArtifactFetcher
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.provision import (
    missing_artifacts,
    provision_bundle,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError


def _artifact(name: str, payload: bytes) -> Artifact:
    return Artifact(
        coordinate=name,
        path=f"{name}.jar",
        url=f"https://example.invalid/{name}.jar",
        size=len(payload),
        sha1=hashlib.sha1(payload).hexdigest(),
        kind="library",
    )


def _plan(*artifacts: Artifact) -> dict[str, object]:
    return {
        "artifacts": [
            {
                "coordinate": artifact.coordinate,
                "path": artifact.path,
                "url": artifact.url,
                "size": artifact.size,
                "sha1": artifact.sha1,
                "kind": artifact.kind,
            }
            for artifact in artifacts
        ]
    }


def _serving(payloads: dict[str, bytes]):
    def opener(url: str, timeout: float) -> BinaryIO:
        del timeout
        return io.BytesIO(payloads[url])

    return opener


def test_a_missing_artifact_is_fetched_and_a_present_one_is_reused(tmp_path: Path) -> None:
    wanted, already = b"the wanted bytes", b"the bytes already here"
    first, second = _artifact("wanted", wanted), _artifact("already", already)
    store = ArtifactStore(tmp_path / "store")
    store.install(second, io.BytesIO(already))
    fetcher = ArtifactFetcher(store, opener=_serving({first.url: wanted}))

    report = provision_bundle(_plan(first, second), store, fetcher=fetcher)

    assert report.complete
    assert report.installed == ("wanted",)
    assert report.reused == ("already",)
    assert store.verify(first) == store.path_for(first)


def test_an_artifact_the_upstream_will_not_serve_is_reported_and_the_pass_continues(
    tmp_path: Path,
) -> None:
    """One broken upstream should not hide how much else is missing."""

    first, second = _artifact("first", b"one"), _artifact("second", b"two")
    store = ArtifactStore(tmp_path / "store")
    fetcher = ArtifactFetcher(store, opener=_serving({}))  # nothing is served

    report = provision_bundle(_plan(first, second), store, fetcher=fetcher)

    assert not report.complete
    assert [failure.coordinate for failure in report.failed] == ["first", "second"]
    assert report.as_dict()["status"] == "incomplete"


def test_the_budget_refuses_before_anything_is_fetched(tmp_path: Path) -> None:
    artifact = _artifact("big", b"x" * 4096)
    store = ArtifactStore(tmp_path / "store")
    asked: list[str] = []

    def opener(url: str, timeout: float) -> BinaryIO:
        del timeout
        asked.append(url)
        return io.BytesIO(b"")

    fetcher = ArtifactFetcher(store, opener=opener)

    with pytest.raises(MinekinError, match="over the 100 byte budget") as raised:
        provision_bundle(_plan(artifact), store, fetcher=fetcher, max_bytes=100)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert asked == []


def test_a_full_store_is_never_refused_for_its_size(tmp_path: Path) -> None:
    """The budget bounds what a pass fetches, not what it finds."""

    payload = b"already here"
    artifact = _artifact("present", payload)
    store = ArtifactStore(tmp_path / "store")
    store.install(artifact, io.BytesIO(payload))

    report = provision_bundle(_plan(artifact), store, max_bytes=1)

    assert report.reused == ("present",)
    assert report.installed == ()


def test_missing_artifacts_names_what_the_store_cannot_vouch_for(tmp_path: Path) -> None:
    payload = b"present"
    there, absent = _artifact("there", payload), _artifact("absent", b"nope")
    store = ArtifactStore(tmp_path / "store")
    store.install(there, io.BytesIO(payload))

    missing = missing_artifacts(_plan(there, absent), store)

    assert [artifact.coordinate for artifact in missing] == ["absent"]


def test_a_plan_with_no_artifacts_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="names no artifacts"):
        provision_bundle({"artifacts": []}, ArtifactStore(tmp_path / "store"))


def test_a_non_positive_budget_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_bytes"):
        provision_bundle({"artifacts": []}, ArtifactStore(tmp_path / "store"), max_bytes=0)
