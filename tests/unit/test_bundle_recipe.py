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
CANDIDATE_PROFILE = ROOT / "tests" / "fixtures" / "runtime-input" / "bundle-candidate-1.20.1.json"


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


@pytest.mark.parametrize(
    ("artifact_name", "field"),
    [
        ("fabric-api", "digest"),
        ("minekin-bridge", "digest"),
        ("minekin-bridge", "source_digest"),
    ],
)
def test_any_tampered_recipe_digest_is_rejected(
    tmp_path: Path, artifact_name: str, field: str
) -> None:
    """Every digest the reviewed recipe carries is enforced, not decorative.

    One parametrisation per digest, so "tampering with any digest is refused" is a
    claim about the list rather than about one field of it: a value nothing reads
    can disagree with what is actually fetched or built without anything noticing,
    and that is the same shape `test_an_unreviewed_fabric_pin_is_rejected` exists
    for one section over.
    """

    recipe = json.loads(PROFILE.read_bytes())
    artifact = next(item for item in recipe["artifacts"] if item["name"] == artifact_name)
    digest = artifact[field]
    artifact[field] = ("0" if digest[0] != "0" else "1") + digest[1:]
    candidate = tmp_path / "recipe.json"
    candidate.write_text(json.dumps(recipe), encoding="utf-8")

    with pytest.raises(MinekinError) as raised:
        validate_bundle_recipe(candidate, ROOT)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


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


def test_the_1201_candidate_verifies_end_to_end_against_its_own_build() -> None:
    """`bundle verify` reaches the 1.20.1 candidate's own metadata and stays honest.

    The command runs the whole plan build, so it proves the metadata parser resolves
    the candidate against its version pins, not 1.21.4's, and that its Bridge names
    a jar the 1.20.1 root actually built. Nothing in the recipe is `tested`: that is
    the bundle's `status`, and the card that proves a real server accepts it is the
    one that changes it.
    """

    from io import StringIO

    stdout, stderr = StringIO(), StringIO()
    code = run(
        ["bundle", "verify", "--profile", str(CANDIDATE_PROFILE)], stdout=stdout, stderr=stderr
    )
    report = json.loads(stdout.getvalue())
    assert code == ExitCode.OK
    assert report["status"] == "valid_recipe"
    assert report["launchable"] is True
    assert report["blockers"] == []
    assert stderr.getvalue() == ""


def test_the_1201_candidate_recipe_is_not_labelled_tested() -> None:
    """The one label that would be an untrue claim, checked on the committed file."""

    assert json.loads(CANDIDATE_PROFILE.read_bytes())["status"] == "candidate"


def test_the_1201_candidate_plan_names_its_reviewed_bundle() -> None:
    from minekin_core.adapters.launcher.launch_plan import build_launch_plan

    plan = build_launch_plan(CANDIDATE_PROFILE)
    assert plan["status"] == "dry_run"
    assert plan["bundle"]["minecraft"] == "1.20.1"
    assert plan["bundle"]["java_major"] == 17
    assert plan["bundle"]["fabric_loader"] == "0.19.5"


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

    # The 1.20.1 candidate is a second Gradle root, so it has a second catalog. A
    # recipe pin that drifted from the build that produced its jar would be a
    # digest nobody can reproduce, which is what this pair of checks is for.
    candidate_catalog = tomllib.loads(
        (ROOT / "bridge-1201" / "gradle" / "libs.versions.toml").read_text(encoding="utf-8")
    )
    candidate_versions = candidate_catalog["versions"]

    assert candidate_versions["minecraft"] == recipe_module.MINECRAFT_1201_VERSION
    assert candidate_versions["fabric-loader"] == recipe_module.FABRIC_LOADER_1201
    assert candidate_versions["fabric-api"] == recipe_module.FABRIC_API_1201_VERSION
    assert candidate_versions["yarn"] == recipe_module.FABRIC_YARN_1201


def _jar(workspace: Path, payload: bytes, relative_path: str) -> Path:
    path = workspace / relative_path
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
    jar = _jar(tmp_path, payload, BRIDGE_JAR_RELATIVE_PATH)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(recipe_module, "BRIDGE_JAR_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(recipe_module, "BRIDGE_JAR_SIZE", len(payload))
    try:
        assert require_built_bridge(tmp_path, "1.21.4") == jar
    finally:
        monkeypatch.undo()


def test_the_1201_bridge_is_read_at_its_own_roots_path(tmp_path: Path) -> None:
    """One root's reviewed bytes are not the other's, and neither path is shared."""

    payload = b"a reviewed 1.20.1 bridge build\n"
    jar = _jar(tmp_path, payload, recipe_module.BRIDGE_1201_JAR_RELATIVE_PATH)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        recipe_module, "BRIDGE_1201_JAR_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(recipe_module, "BRIDGE_1201_JAR_SIZE", len(payload))
    try:
        assert require_built_bridge(tmp_path, recipe_module.MINECRAFT_1201_VERSION) == jar
        with pytest.raises(MinekinError, match="has not been built"):
            require_built_bridge(tmp_path, "1.21.4")
    finally:
        monkeypatch.undo()


def test_a_version_with_no_reviewed_bridge_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="no reviewed Bridge jar is pinned") as raised:
        require_built_bridge(tmp_path, "1.19.4")

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_a_missing_bridge_jar_names_the_build_that_has_not_happened(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="has not been built") as raised:
        require_built_bridge(tmp_path, "1.21.4")

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert str(tmp_path) in raised.value.safe_message


def test_a_bridge_jar_of_the_wrong_size_is_refused(tmp_path: Path) -> None:
    _jar(tmp_path, b"not the reviewed build\n", BRIDGE_JAR_RELATIVE_PATH)

    with pytest.raises(MinekinError, match="bytes, not the reviewed") as raised:
        require_built_bridge(tmp_path, "1.21.4")

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_a_bridge_jar_of_the_right_size_but_the_wrong_bytes_is_refused(tmp_path: Path) -> None:
    """Size alone would pass a rebuilt jar that changed without the pin moving."""

    _jar(tmp_path, b"x" * BRIDGE_JAR_SIZE, BRIDGE_JAR_RELATIVE_PATH)

    with pytest.raises(MinekinError, match="not the reviewed build of this source") as raised:
        require_built_bridge(tmp_path, "1.21.4")

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def _candidate_1201() -> dict[str, object]:
    """A faithful 1.20.1 candidate recipe: reviewed pins, reviewed Bridge build."""

    return {
        "schema_version": 1,
        "bundle_name": "p0-core-1.20.1-linux-x86_64",
        "status": "candidate",
        "launchable": False,
        "minecraft": {
            "version": recipe_module.MINECRAFT_1201_VERSION,
            "version_metadata_sha1": recipe_module.MINECRAFT_1201_METADATA_SHA1,
        },
        "runtime": {"java_major": 17, "os_arch": "linux-x86_64"},
        "fabric": {
            "loader": recipe_module.FABRIC_LOADER_1201,
            "api": recipe_module.FABRIC_API_1201_VERSION,
            "yarn": recipe_module.FABRIC_YARN_1201,
        },
        "artifacts": [
            {
                "name": "fabric-api",
                "kind": "mod",
                "verification": "sha256",
                "digest": recipe_module.FABRIC_API_1201_SHA256,
                "size": recipe_module.FABRIC_API_1201_SIZE,
                "source": recipe_module.FABRIC_API_1201_URL,
                "license": "Apache-2.0",
            },
            {
                "name": "minekin-bridge",
                "kind": "bridge",
                "verification": "sha256",
                "digest": recipe_module.BRIDGE_1201_JAR_SHA256,
                "size": recipe_module.BRIDGE_1201_JAR_SIZE,
                "source": "workspace:bridge-1201",
                "source_digest": source_tree_sha256(ROOT / "bridge-1201"),
                "license": "NOASSERTION",
            },
        ],
    }


def _write_candidate(tmp_path: Path, recipe: dict[str, object]) -> Path:
    path = tmp_path / "recipe-1.20.1.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    return path


def test_a_1201_candidate_recipe_validates_against_its_own_bridge_root(
    tmp_path: Path,
) -> None:
    audit = validate_bundle_recipe(_write_candidate(tmp_path, _candidate_1201()), ROOT)
    assert [mod.name for mod in audit.fixed_mods] == ["fabric-api", "minekin-bridge"]
    assert audit.fixed_mods[0].sha256 == recipe_module.FABRIC_API_1201_SHA256
    assert audit.fixed_mods[1].sha256 == recipe_module.BRIDGE_1201_JAR_SHA256
    assert audit.fixed_mods[1].source == f"workspace:{recipe_module.BRIDGE_1201_JAR_RELATIVE_PATH}"
    # Nothing is blocked: the 1.20.1 jar has been built and pinned. What the
    # candidate lacks is a real server accepting it, and that is its `status`,
    # not an unbuilt artifact.
    assert audit.blockers == ()
    # The source identity is the 1.20.1 root's own. Reading the neighbouring
    # 1.21.4 root here would let a jar built from the wrong tree pass.
    assert audit.bridge_source_sha256 == source_tree_sha256(ROOT / "bridge-1201")
    assert audit.bridge_source_sha256 != source_tree_sha256(ROOT / "bridge")


def test_a_candidate_bridge_naming_the_other_root_build_is_rejected(tmp_path: Path) -> None:
    recipe = _candidate_1201()
    bridge = next(a for a in recipe["artifacts"] if a["name"] == "minekin-bridge")  # type: ignore[index]
    bridge["source"] = "workspace:bridge"  # type: ignore[index]
    with pytest.raises(MinekinError, match="candidate Bridge jar pin"):
        validate_bundle_recipe(_write_candidate(tmp_path, recipe), ROOT)


def test_a_candidate_bridge_of_an_unreviewed_digest_is_rejected(tmp_path: Path) -> None:
    recipe = _candidate_1201()
    bridge = next(a for a in recipe["artifacts"] if a["name"] == "minekin-bridge")  # type: ignore[index]
    bridge["digest"] = "0" * 64  # type: ignore[index]
    with pytest.raises(MinekinError, match="candidate Bridge jar pin"):
        validate_bundle_recipe(_write_candidate(tmp_path, recipe), ROOT)


def test_a_candidate_bridge_still_declared_unbuilt_is_rejected(tmp_path: Path) -> None:
    recipe = _candidate_1201()
    bridge = next(a for a in recipe["artifacts"] if a["name"] == "minekin-bridge")  # type: ignore[index]
    bridge["verification"] = "build_required"  # type: ignore[index]
    del bridge["digest"]  # type: ignore[index]
    del bridge["size"]  # type: ignore[index]
    with pytest.raises(MinekinError, match="candidate Bridge jar pin"):
        validate_bundle_recipe(_write_candidate(tmp_path, recipe), ROOT)


def test_a_candidate_bridge_source_digest_of_the_other_root_is_rejected(tmp_path: Path) -> None:
    recipe = _candidate_1201()
    bridge = next(a for a in recipe["artifacts"] if a["name"] == "minekin-bridge")  # type: ignore[index]
    bridge["source_digest"] = source_tree_sha256(ROOT / "bridge")  # type: ignore[index]
    with pytest.raises(MinekinError, match="candidate Bridge source tree digest"):
        validate_bundle_recipe(_write_candidate(tmp_path, recipe), ROOT)


@pytest.mark.parametrize(
    ("field", "value"),
    [("yarn", "1.20.1+build.99"), ("api", "0.92.13+1.20.1"), ("loader", "0.16.9")],
)
def test_an_unreviewed_1201_fabric_pin_is_rejected(tmp_path: Path, field: str, value: str) -> None:
    recipe = _candidate_1201()
    recipe["fabric"][field] = value  # type: ignore[index]
    with pytest.raises(MinekinError, match=f"fabric.{field} is not the reviewed value"):
        validate_bundle_recipe(_write_candidate(tmp_path, recipe), ROOT)


def test_a_tampered_1201_fabric_api_digest_is_rejected(tmp_path: Path) -> None:
    recipe = _candidate_1201()
    api = next(a for a in recipe["artifacts"] if a["name"] == "fabric-api")  # type: ignore[index]
    api["digest"] = "0" * 64  # type: ignore[index]
    with pytest.raises(MinekinError, match="Fabric API artifact identity"):
        validate_bundle_recipe(_write_candidate(tmp_path, recipe), ROOT)
