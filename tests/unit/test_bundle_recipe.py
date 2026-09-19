from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher import recipe as recipe_module
from minekin_core.adapters.launcher.recipe import (
    BRIDGE_JAR_RELATIVE_PATH,
    BRIDGE_JAR_SIZE,
    require_built_bridge,
    source_tree_sha256,
    validate_bundle_recipe,
)
from minekin_core.bootstrap import run
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError

ROOT = Path(__file__).parents[2]
PROFILE = ROOT / "tests" / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"


def test_fixed_mod_recipe_validates_source_identity() -> None:
    audit = validate_bundle_recipe(PROFILE, ROOT)
    assert [mod.name for mod in audit.fixed_mods] == ["fabric-api", "minekin-bridge"]
    assert len(audit.bridge_source_sha256) == 64
    # Nothing is blocked any more: the recipe pins the jar instead of saying it has
    # yet to be pinned, and whether that jar exists is asked at start time.
    assert audit.blockers == ()


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
    assert report["launchable"] is True
    assert report["blockers"] == []
    assert stderr.getvalue() == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [("yarn", "1.21.4+build.9"), ("api", "0.119.5+1.21.4"), ("loader", "0.17.0")],
)
def test_an_unreviewed_fabric_pin_is_rejected(tmp_path: Path, field: str, value: str) -> None:
    """Every value in the recipe's fabric section is enforced, not decorative.

    The section is what a reviewer reads to learn what the bundle is made of, so
    a value nothing checks can silently disagree with what is actually used.
    """

    recipe = json.loads(PROFILE.read_bytes())
    recipe["fabric"][field] = value
    candidate = tmp_path / "recipe.json"
    candidate.write_text(json.dumps(recipe), encoding="utf-8")

    with pytest.raises(MinekinError, match=f"fabric.{field} is not the reviewed value"):
        validate_bundle_recipe(candidate, ROOT)


def test_the_recipe_pins_agree_with_the_bridge_version_catalog() -> None:
    """Two lists of the same versions would drift; this makes the drift loud."""

    import tomllib

    from minekin_core.adapters.launcher import recipe as recipe_module

    catalog = tomllib.loads(
        (ROOT / "bridge" / "gradle" / "libs.versions.toml").read_text(encoding="utf-8")
    )
    versions = catalog["versions"]

    assert versions["minecraft"] == "1.21.4"
    assert versions["fabric-loader"] == "0.16.9"
    assert versions["fabric-api"] == recipe_module.FABRIC_API_VERSION
    assert versions["yarn"] == recipe_module.FABRIC_YARN


def _jar(workspace: Path, payload: bytes) -> Path:
    path = workspace / BRIDGE_JAR_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_the_source_digest_does_not_depend_on_how_the_platform_sorts_paths(
    tmp_path: Path,
) -> None:
    """`sorted()` on `Path` objects is case-insensitive on Windows and not on Linux.

    That is the same failure the content normalisation exists for, arriving by a
    second route: a file and a directory whose names differ only in case change
    places between platforms, and the same source tree then hashes differently on
    each. `Zebra.txt` beside `apple.txt` is exactly such a pair, and this asserts
    the order the function is supposed to use rather than the one the platform
    happens to have.
    """

    root = tmp_path / "bridge"
    root.mkdir()
    (root / "Zebra.txt").write_text("zebra", encoding="utf-8")
    (root / "apple.txt").write_text("apple", encoding="utf-8")

    expected = hashlib.sha256()
    for name in ("Zebra.txt", "apple.txt"):  # codepoint order, on any platform
        expected.update(name.encode())
        expected.update(bytes([0]))
        expected.update((root / name).read_bytes())
        expected.update(bytes([0]))

    assert source_tree_sha256(root) == expected.hexdigest()


def test_a_built_bridge_is_only_accepted_at_the_pinned_digest(tmp_path: Path) -> None:
    payload = b"a reviewed bridge build\n"
    jar = _jar(tmp_path, payload)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(recipe_module, "BRIDGE_JAR_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(recipe_module, "BRIDGE_JAR_SIZE", len(payload))
    try:
        assert require_built_bridge(tmp_path) == jar
    finally:
        monkeypatch.undo()


def test_a_missing_bridge_jar_names_the_build_that_has_not_happened(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="has not been built") as raised:
        require_built_bridge(tmp_path)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert str(tmp_path) in raised.value.safe_message


def test_a_bridge_jar_of_the_wrong_size_is_refused(tmp_path: Path) -> None:
    _jar(tmp_path, b"not the reviewed build\n")

    with pytest.raises(MinekinError, match="bytes, not the reviewed") as raised:
        require_built_bridge(tmp_path)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_a_bridge_jar_of_the_right_size_but_the_wrong_bytes_is_refused(tmp_path: Path) -> None:
    """Size alone would pass a rebuilt jar that changed without the pin moving."""

    _jar(tmp_path, b"x" * BRIDGE_JAR_SIZE)

    with pytest.raises(MinekinError, match="not the reviewed build of this source") as raised:
        require_built_bridge(tmp_path)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
