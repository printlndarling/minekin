from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.launch_plan import build_launch_plan, find_workspace_root
from minekin_core.adapters.launcher.recipe import source_tree_sha256
from minekin_core.bootstrap import run
from minekin_core.domain.errors import ExitCode, MinekinError

PROFILE = Path(__file__).parents[1] / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"


def test_launch_plan_is_deterministic_and_has_independent_arguments() -> None:
    first = build_launch_plan(PROFILE)
    assert first == build_launch_plan(PROFILE)
    assert first["bundle"]["main_class"] == "net.fabricmc.loader.impl.launch.knot.KnotClient"
    assert first["runtime"]["classpath"]
    assert len(first["artifacts"]) == 4120
    assert len(first["runtime"]["classpath"]) == 70
    assert len(first["runtime"]["native_artifacts"]) == 9
    assert first["runtime"]["asset_index"].endswith("/19.json")
    assert first["runtime"]["logging_config"].endswith("/client-1.21.2.xml")
    assert sum(item["kind"] == "asset" for item in first["artifacts"]) == 4039
    assert all("${" not in item for item in first["runtime"]["jvm_args"])
    assert all(
        item["kind"] in {"literal", "placeholder"} for item in first["runtime"]["game_arg_template"]
    )
    assert all(item["url"].startswith("https://") for item in first["artifacts"])
    assert first["blockers"] == ["minekin-bridge: build required"]
    assert not first["launchable"]


def test_cli_emits_plan_without_writing_or_starting_java(tmp_path: Path) -> None:
    stdout, stderr = io.StringIO(), io.StringIO()
    before = sorted(tmp_path.iterdir())
    code = run(
        ["launch-plan", "--profile", str(PROFILE), "--dry-run"], stdout=stdout, stderr=stderr
    )
    assert code == ExitCode.OK
    assert json.loads(stdout.getvalue())["status"] == "dry_run"
    assert stderr.getvalue() == ""
    assert sorted(tmp_path.iterdir()) == before


def test_the_workspace_root_is_found_by_marker_not_by_nesting_depth() -> None:
    """Counting parents works from the source tree and points into site-packages once installed."""

    found = find_workspace_root(Path(__file__).resolve())

    assert (found / "bridge").is_dir()
    assert (found / "proto").is_dir()
    assert found == Path(__file__).resolve().parents[2]


def test_the_workspace_search_walks_up_from_a_deep_path() -> None:
    deep = Path(__file__).resolve().parents[2] / "src" / "minekin_core" / "adapters"

    assert find_workspace_root(deep) == Path(__file__).resolve().parents[2]


def test_a_tree_without_the_bridge_or_the_protos_has_no_workspace(tmp_path: Path) -> None:
    (tmp_path / "site-packages" / "minekin_core").mkdir(parents=True)

    with pytest.raises(MinekinError, match="no Minekin workspace found") as raised:
        find_workspace_root(tmp_path / "site-packages" / "minekin_core")

    # The message must name where it looked, or an installed wheel is undiagnosable.
    assert "minekin_core" in raised.value.safe_message
    assert "installed wheel" in raised.value.safe_message


@pytest.mark.parametrize("marker", ["bridge", "proto"])
def test_half_a_workspace_is_not_a_workspace(tmp_path: Path, marker: str) -> None:
    (tmp_path / marker).mkdir()

    with pytest.raises(MinekinError, match="no Minekin workspace found"):
        find_workspace_root(tmp_path)


def test_the_missing_source_root_is_named() -> None:
    """`Bridge source root is missing` without a path sends the reader hunting."""

    missing = Path("/nonexistent/bridge")
    with pytest.raises(MinekinError, match="Bridge source root is missing") as raised:
        source_tree_sha256(missing)

    assert str(missing) in raised.value.safe_message


def test_the_plan_uses_the_finder_when_no_root_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the wiring, not just the helper: the default must not be a parent count."""

    import minekin_core.adapters.launcher.launch_plan as module

    monkeypatch.setattr(module, "WORKSPACE_MARKERS", ("no-such-marker",))

    with pytest.raises(MinekinError, match="no Minekin workspace found"):
        build_launch_plan(PROFILE)
