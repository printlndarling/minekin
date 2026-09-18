from __future__ import annotations

import io
import json
from pathlib import Path

from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.bootstrap import run
from minekin_core.domain.errors import ExitCode

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
