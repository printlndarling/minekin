from __future__ import annotations

import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.recipe import validate_bundle_recipe
from minekin_core.bootstrap import run
from minekin_core.domain.errors import ExitCode, MinekinError

ROOT = Path(__file__).parents[2]
PROFILE = ROOT / "tests" / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"


def test_fixed_mod_recipe_validates_source_identity() -> None:
    audit = validate_bundle_recipe(PROFILE, ROOT)
    assert audit.fixed_mods == ("fabric-api", "minekin-bridge")
    assert len(audit.bridge_source_sha256) == 64
    assert audit.blockers == ("minekin-bridge: build required",)


def test_unknown_mod_is_rejected(tmp_path: Path) -> None:
    recipe = json.loads(PROFILE.read_bytes())
    recipe["artifacts"].append(
        {
            "name": "unknown-mod",
            "kind": "mod",
            "verification": "sha256",
            "digest": "0" * 64,
            "size": 1,
            "source": "https://example.invalid/mod.jar",
            "license": "NOASSERTION",
        }
    )
    candidate = tmp_path / "recipe.json"
    candidate.write_text(json.dumps(recipe), encoding="utf-8")
    with pytest.raises(MinekinError, match="fixed mod set"):
        validate_bundle_recipe(candidate, ROOT)


def test_bundle_verify_cli_is_read_only() -> None:
    from io import StringIO

    stdout, stderr = StringIO(), StringIO()
    code = run(["bundle", "verify", "--profile", str(PROFILE)], stdout=stdout, stderr=stderr)
    report = json.loads(stdout.getvalue())
    assert code == ExitCode.OK
    assert report["status"] == "valid_recipe"
    assert report["launchable"] is False
    assert report["blockers"] == ["minekin-bridge: build required"]
    assert stderr.getvalue() == ""
