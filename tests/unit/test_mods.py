"""Placing the fixed mod set, and what happens when it is not what was pinned."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.mods import MODS_DIRECTORY, install_fixed_mods
from minekin_core.cli import session as session_module
from minekin_core.cli.session import session_overlay_path, start_session
from minekin_core.domain.errors import ErrorCategory, MinekinError
from session_support import (
    PAYLOAD,
    PROFILE,
    fabricated,
    kin_root,
    run_root,
    stub_supervisor,  # type: ignore[import-not-found]
)

BRIDGE_BYTES = b"a reviewed bridge build\n"
API_BYTES = b"a fetched fabric api jar\n"
BRIDGE_SOURCE = "workspace:bridge/build/libs/minekin-bridge-0.0.0.jar"
# The store keeps a fetched artifact under the basename of its URL, so the
# fake URL has to end the way a real one does.
API_URL = (
    "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/"
    "0.119.4+1.21.4/fabric-api-0.119.4+1.21.4.jar"
)


def _record(name: str, payload: bytes, source: str, *, sha1: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "name": name,
        "kind": "bridge" if source.startswith("workspace:") else "mod",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "source": source,
    }
    if sha1 is not None:
        record["sha1"] = sha1
    return record


def _workspace(tmp_path: Path, payload: bytes = BRIDGE_BYTES) -> Path:
    root = tmp_path / "workspace"
    jar = root / "bridge/build/libs/minekin-bridge-0.0.0.jar"
    jar.parent.mkdir(parents=True, exist_ok=True)
    jar.write_bytes(payload)
    return root


def _api_store(tmp_path: Path) -> tuple[ArtifactStore, str]:
    store = ArtifactStore(tmp_path / "artifact-store")
    artifact = Artifact(
        coordinate="fabric-api",
        path=Path(API_URL).name,
        url=API_URL,
        size=len(API_BYTES),
        sha1=hashlib.sha1(API_BYTES).hexdigest(),
        kind="mod",
    )
    store.install(artifact, io.BytesIO(API_BYTES))
    return store, artifact.sha1


def _plan(tmp_path: Path, *, api_sha1: str | None) -> dict[str, Any]:
    return {
        "fixed_mods": [
            _record("minekin-bridge", BRIDGE_BYTES, BRIDGE_SOURCE),
            _record("fabric-api", API_BYTES, API_URL, sha1=api_sha1),
        ]
    }


def _overlay(tmp_path: Path) -> Path:
    overlay = tmp_path / "run" / "session" / "session-01" / "generation-1"
    overlay.mkdir(parents=True)
    return overlay


def test_both_a_built_mod_and_a_fetched_one_are_placed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    store, api_sha1 = _api_store(tmp_path)
    overlay = _overlay(tmp_path)

    placed = install_fixed_mods(
        _plan(tmp_path, api_sha1=api_sha1),
        overlay=overlay,
        store=store,
        workspace_root=workspace,
    )

    assert {path.name for path in placed} == {
        "minekin-bridge-0.0.0.jar",
        "fabric-api-0.119.4+1.21.4.jar",
    }
    assert {path.name for path in (overlay / MODS_DIRECTORY).iterdir()} == {
        path.name for path in placed
    }
    assert (overlay / MODS_DIRECTORY / "minekin-bridge-0.0.0.jar").read_bytes() == BRIDGE_BYTES


def test_a_mod_that_was_never_built_names_the_build(tmp_path: Path) -> None:
    store, api_sha1 = _api_store(tmp_path)
    overlay = _overlay(tmp_path)

    with pytest.raises(MinekinError, match="minekin-bridge has not been built") as raised:
        install_fixed_mods(
            _plan(tmp_path, api_sha1=api_sha1),
            overlay=overlay,
            store=store,
            workspace_root=tmp_path / "empty-workspace",
        )

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_a_mod_that_is_not_the_reviewed_bytes_is_refused(tmp_path: Path) -> None:
    """Size alone would pass a rebuild that changed without the pin moving."""

    workspace = _workspace(tmp_path, BRIDGE_BYTES.replace(b"reviewed", b"replaced"))
    store, api_sha1 = _api_store(tmp_path)

    with pytest.raises(MinekinError, match="not the reviewed build") as raised:
        install_fixed_mods(
            _plan(tmp_path, api_sha1=api_sha1),
            overlay=_overlay(tmp_path),
            store=store,
            workspace_root=workspace,
        )

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_a_mod_of_the_wrong_size_is_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, BRIDGE_BYTES + b"extra")
    store, api_sha1 = _api_store(tmp_path)

    with pytest.raises(MinekinError, match="bytes, not the reviewed"):
        install_fixed_mods(
            _plan(tmp_path, api_sha1=api_sha1),
            overlay=_overlay(tmp_path),
            store=store,
            workspace_root=workspace,
        )


def test_a_fetched_mod_that_is_not_in_the_store_is_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    store, _api_sha1 = _api_store(tmp_path)

    with pytest.raises(MinekinError, match="fabric-api is not in the content-addressed store"):
        install_fixed_mods(
            _plan(tmp_path, api_sha1="f" * 40),
            overlay=_overlay(tmp_path),
            store=store,
            workspace_root=workspace,
        )


def test_a_plan_with_no_mods_is_refused_rather_than_silently_starting_vanilla(
    tmp_path: Path,
) -> None:
    store, _ = _api_store(tmp_path)

    with pytest.raises(MinekinError, match="names no fixed mods"):
        install_fixed_mods(
            {"fixed_mods": []},
            overlay=_overlay(tmp_path),
            store=store,
            workspace_root=_workspace(tmp_path),
        )


def test_a_started_session_finds_its_mods_in_the_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The end of the chain: the client's game directory holds the mod jars."""

    root = kin_root(tmp_path)
    plan, artifact = fabricated()
    workspace = _workspace(tmp_path)
    # The session's own store, which is not the one the other tests build.
    store = ArtifactStore(run_root(tmp_path) / "artifact-store")
    store.install(artifact, io.BytesIO(PAYLOAD))
    api = Artifact(
        coordinate="fabric-api",
        path=Path(API_URL).name,
        url=API_URL,
        size=len(API_BYTES),
        sha1=hashlib.sha1(API_BYTES).hexdigest(),
        kind="mod",
    )
    store.install(api, io.BytesIO(API_BYTES))
    plan["fixed_mods"] = _plan(tmp_path, api_sha1=api.sha1)["fixed_mods"]

    def this_plan(
        _profile: Path,
        *,
        workspace_root: Path | None = None,
        world_name: str | None = None,
    ) -> dict[str, Any]:
        return plan

    def built_bridge(_root: Path) -> Path:
        return workspace

    def this_workspace(_start: Path) -> Path:
        return workspace

    monkeypatch.setattr(session_module, "build_launch_plan", this_plan)
    # Only the readiness check is stood in for: placing the mods is the step
    # under test, so it runs for real against the plan's own pins.
    monkeypatch.setattr(session_module, "require_built_bridge", built_bridge)
    monkeypatch.setattr(session_module, "find_workspace_root", this_workspace)

    # The fabricated plan declares no natives, and extraction has its own tests;
    # this one is about where the mods end up.
    def nothing_to_materialise(*_args: object, **_kwargs: object) -> tuple[Path, ...]:
        return ()

    monkeypatch.setattr(session_module, "materialise_natives", nothing_to_materialise)
    monkeypatch.setattr(session_module, "materialise_assets", nothing_to_materialise)

    launch = start_session(
        root=root,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=stub_supervisor,
    )

    overlay = session_overlay_path(run_root(tmp_path), "session-01", 1)
    assert Path(launch.overlay) == overlay
    assert {path.name for path in (overlay / MODS_DIRECTORY).iterdir()} == {
        "minekin-bridge-0.0.0.jar",
        "fabric-api-0.119.4+1.21.4.jar",
    }
    assert (overlay / MODS_DIRECTORY / "minekin-bridge-0.0.0.jar").read_bytes() == BRIDGE_BYTES
