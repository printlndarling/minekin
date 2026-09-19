"""Materialising the asset view, and what is refused while building it."""

from __future__ import annotations

import hashlib
import io
import stat
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore, store_relative_path
from minekin_core.adapters.launcher.assets import materialise_assets
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.process import resolve_plan_path
from minekin_core.domain.errors import ErrorCategory, MinekinError

OBJECT = b"an asset object\n"
SECOND_OBJECT = b"another object\n"
INDEX = b'{"objects": {}}\n'


def _digest(payload: bytes) -> str:
    return hashlib.sha1(payload).hexdigest()


def _asset(payload: bytes = OBJECT, *, path: str | None = None) -> Artifact:
    digest = _digest(payload)
    return Artifact(
        coordinate=f"asset:{digest[:8]}",
        path=path if path is not None else f"assets/objects/{digest[:2]}/{digest}",
        url=f"https://example.invalid/{digest}",
        size=len(payload),
        sha1=digest,
        kind="asset",
    )


def _index(payload: bytes = INDEX, *, path: str = "assets/indexes/19.json") -> Artifact:
    return Artifact(
        coordinate="asset-index:19",
        path=path,
        url="https://example.invalid/19.json",
        size=len(payload),
        sha1=_digest(payload),
        kind="asset-index",
    )


def _plan(
    *artifacts: Artifact,
    index: Artifact,
    assets_dir: str = "bundle/assets",
    index_name: str = "19",
) -> dict[str, Any]:
    return {
        "artifacts": [
            asdict(artifact) | {"store_path": store_relative_path(artifact)}
            for artifact in (*artifacts, index)
        ],
        "runtime": {
            "assets_dir": assets_dir,
            "assets_index_name": index_name,
            "asset_index": store_relative_path(index),
        },
    }


def _store(tmp_path: Path, *artifacts: Artifact, payloads: dict[str, bytes]) -> ArtifactStore:
    store = ArtifactStore(tmp_path / "artifact-store")
    for artifact in artifacts:
        store.install(artifact, io.BytesIO(payloads[artifact.coordinate]))
    return store


def _run_root(tmp_path: Path) -> Path:
    return tmp_path / "run"


def _overlay(tmp_path: Path) -> Path:
    overlay = _run_root(tmp_path) / "session" / "session-01" / "generation-1"
    overlay.mkdir(parents=True, exist_ok=True)
    return overlay


def _materialise(tmp_path: Path, plan: dict[str, Any], store: ArtifactStore):
    return materialise_assets(
        plan, run_root=_run_root(tmp_path), overlay=_overlay(tmp_path), store=store
    )


def test_the_objects_and_the_index_land_where_the_client_reads_them(tmp_path: Path) -> None:
    """`--assetsDir` and `--assetIndex` are two arguments; this is what they mean."""

    first, second, index = _asset(), _asset(b"another object\n"), _index()
    store = _store(
        tmp_path,
        first,
        second,
        index,
        payloads={
            first.coordinate: OBJECT,
            second.coordinate: b"another object\n",
            index.coordinate: INDEX,
        },
    )

    view = _materialise(tmp_path, _plan(first, second, index=index), store)

    assert view.directory == _run_root(tmp_path) / "bundle" / "assets"
    assert view.objects == 2
    assert view.copied == 3
    assert view.index == view.directory / "indexes" / "19.json"
    assert view.index.read_bytes() == INDEX
    assert (view.directory / "objects" / first.sha1[:2] / first.sha1).read_bytes() == OBJECT
    assert (
        view.directory / "objects" / second.sha1[:2] / second.sha1
    ).read_bytes() == SECOND_OBJECT

    # And the directory is the one the plan's own path names, resolved the way
    # the launch resolves it.
    assert view.directory == resolve_plan_path(
        _run_root(tmp_path), _overlay(tmp_path), "bundle/assets"
    )


def test_the_files_are_read_only(tmp_path: Path) -> None:
    """The view is a copy of the store, and nothing should be writing to it."""

    index = _index()
    store = _store(tmp_path, index, payloads={index.coordinate: INDEX})

    view = _materialise(tmp_path, _plan(index=index), store)

    assert not view.index.stat().st_mode & stat.S_IWUSR
    assert not view.index.stat().st_mode & stat.S_IWOTH


def test_a_second_pass_copies_nothing(tmp_path: Path) -> None:
    """The bytes are the same for every generation, so they are copied once."""

    first, index = _asset(), _index()
    store = _store(
        tmp_path, first, index, payloads={first.coordinate: OBJECT, index.coordinate: INDEX}
    )
    plan = _plan(first, index=index)

    first_pass = _materialise(tmp_path, plan, store)
    second_pass = _materialise(tmp_path, plan, store)

    assert first_pass.copied == 2
    assert second_pass.copied == 0
    assert second_pass.objects == 1


def test_a_file_that_is_there_at_the_wrong_size_is_replaced(tmp_path: Path) -> None:
    """Something that is not the object is not "already there"."""

    first, index = _asset(), _index()
    store = _store(
        tmp_path, first, index, payloads={first.coordinate: OBJECT, index.coordinate: INDEX}
    )
    plan = _plan(first, index=index)
    view = _materialise(tmp_path, plan, store)
    destination = view.directory / "objects" / first.sha1[:2] / first.sha1
    destination.chmod(0o600)
    destination.write_bytes(b"truncated")

    second_pass = _materialise(tmp_path, plan, store)

    assert second_pass.copied == 1
    assert destination.read_bytes() == OBJECT


def test_an_object_the_plan_puts_outside_the_assets_directory_is_refused(
    tmp_path: Path,
) -> None:
    """The plan's view path and the directory it gives the client have to agree."""

    stray, index = _asset(path="assets/../../etc/passwd"), _index()
    store = _store(
        tmp_path, stray, index, payloads={stray.coordinate: OBJECT, index.coordinate: INDEX}
    )

    with pytest.raises(MinekinError, match="outside the assets directory") as raised:
        _materialise(tmp_path, _plan(stray, index=index), store)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert not (_run_root(tmp_path) / "etc").exists()


def test_an_index_that_is_not_where_the_index_name_says_is_refused(tmp_path: Path) -> None:
    """The client is told `--assetIndex 19`, so the index has to be 19.json."""

    index = _index(path="assets/indexes/07.json")
    store = _store(tmp_path, index, payloads={index.coordinate: INDEX})

    with pytest.raises(MinekinError, match="not where the index name says") as raised:
        _materialise(tmp_path, _plan(index=index), store)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_an_object_that_is_not_in_the_store_is_refused(tmp_path: Path) -> None:
    first, index = _asset(), _index()
    store = _store(tmp_path, index, payloads={index.coordinate: INDEX})

    with pytest.raises(MinekinError, match="missing from the content-addressed store"):
        _materialise(tmp_path, _plan(first, index=index), store)


def test_a_plan_with_no_assets_is_refused(tmp_path: Path) -> None:
    index = _index()
    store = _store(tmp_path, index, payloads={index.coordinate: INDEX})
    plan = _plan(index=index)
    # A plan with artifacts, none of which is an asset.
    plan["artifacts"] = [entry for entry in plan["artifacts"] if entry["kind"] != "asset-index"] + [
        {
            "coordinate": "com.mojang:minecraft:1.21.4",
            "path": "versions/1.21.4/1.21.4.jar",
            "url": "https://example.invalid/1.21.4.jar",
            "size": 1,
            "sha1": "0" * 40,
            "kind": "client",
            "store_path": "artifact-store/blobs/sha1/00/" + "0" * 40 + "/1.21.4.jar",
        }
    ]

    with pytest.raises(MinekinError, match="names no assets to materialise"):
        _materialise(tmp_path, plan, store)


def test_an_assets_directory_outside_the_plan_roots_is_refused(tmp_path: Path) -> None:
    index = _index()
    store = _store(tmp_path, index, payloads={index.coordinate: INDEX})

    with pytest.raises(MinekinError, match="outside the reviewed plan path roots"):
        _materialise(tmp_path, _plan(index=index, assets_dir="elsewhere/assets"), store)
