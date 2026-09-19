from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.launch_plan import build_launch_plan, find_workspace_root
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.recipe import source_tree_sha256
from minekin_core.bootstrap import run
from minekin_core.domain.errors import ExitCode, MinekinError

PROFILE = Path(__file__).parents[1] / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"


def test_the_path_a_plan_declares_is_the_path_the_store_writes(tmp_path: Path) -> None:
    """The readiness check and the launch have to agree about where the store is.

    They did not. The plan restated the store's layout rather than asking it, and
    the restatement was missing the part of the layout that says these are blobs
    — so every classpath entry named a file that was never written, while the
    readiness check, which asks the store, passed. What a client saw was a main
    class it could not find, and nothing in the suite compared the two.
    """

    plan = build_launch_plan(PROFILE)
    store = ArtifactStore(tmp_path / "artifact-store")

    for record in plan["artifacts"]:
        artifact = Artifact(
            coordinate=record["coordinate"],
            path=record["path"],
            url=record["url"],
            size=record["size"],
            sha1=record["sha1"],
            kind=record["kind"],
        )
        assert Path(tmp_path / record["store_path"]) == store.path_for(artifact)

    # The classpath is a subset of those paths rather than its own set, so a
    # classpath entry that no artifact answers for cannot be declared.
    declared = {record["store_path"] for record in plan["artifacts"]}
    assert set(plan["runtime"]["classpath"]) <= declared
    assert set(plan["runtime"]["native_artifacts"]) <= declared


def test_launch_plan_is_deterministic_and_has_independent_arguments() -> None:
    first = build_launch_plan(PROFILE)
    assert first == build_launch_plan(PROFILE)
    assert first["bundle"]["main_class"] == "net.fabricmc.loader.impl.launch.knot.KnotClient"
    assert first["runtime"]["classpath"]
    assert len(first["artifacts"]) == 4119
    assert len(first["runtime"]["classpath"]) == 69
    # One ASM, and it is Fabric's. Both of them on the classpath is not a
    # difference of degree: the Loader refuses to start when it finds two
    # copies of a class it needs, which is what it did here.
    asm = [
        Path(entry).name
        for entry in first["runtime"]["classpath"]
        if Path(entry).name in {"asm-9.6.jar", "asm-9.7.1.jar"}
    ]
    assert asm == ["asm-9.7.1.jar"]
    assert all("/asm-9.6.jar" not in item["store_path"] for item in first["artifacts"])
    assert len(first["runtime"]["native_artifacts"]) == 9
    assert first["runtime"]["asset_index"].endswith("/19.json")
    assert first["runtime"]["logging_config"].endswith("/client-1.21.2.xml")
    assert sum(item["kind"] == "asset" for item in first["artifacts"]) == 4039
    assert all("${" not in item for item in first["runtime"]["jvm_args"])
    assert all(
        item["kind"] in {"literal", "placeholder"} for item in first["runtime"]["game_arg_template"]
    )
    assert all(item["url"].startswith("https://") for item in first["artifacts"])
    assert first["blockers"] == []
    assert first["launchable"]


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


def _write_tree(root: Path, files: dict[str, str], *, newline: str = "\n") -> Path:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", newline).encode())
    return root


def test_the_digest_does_not_depend_on_which_platform_checked_the_tree_out(
    tmp_path: Path,
) -> None:
    """`core.autocrlf` hands the same commit CRLF on Windows and LF elsewhere.

    The digest answers "did the source change?". A whitelist of suffixes let it
    answer "was this checked out on Windows?" instead: it covered `build.gradle.kts`
    and the `.java` sources but not `gradle/verification-metadata.xml`, so one
    commit hashed differently on each platform and the recipe could not be
    reproduced from both at once.
    """

    files = {
        "build.gradle.kts": "plugins { `java-library` }\n",
        "gradle/verification-metadata.xml": "<verification-metadata/>\n",
        "gradle.lockfile": "org.example:library:1.0=compileClasspath\n",
        "gradle/wrapper/gradle-wrapper.properties": "distributionUrl=https\\://x/y.zip\n",
        "gradlew": '#!/bin/sh\nexec java "$@"\n',
        "src/main/java/Main.java": "public class Main {}\n",
    }

    unix = source_tree_sha256(_write_tree(tmp_path / "unix", files))
    windows = source_tree_sha256(_write_tree(tmp_path / "windows", files, newline="\r\n"))

    assert unix == windows


def test_a_binary_file_is_hashed_byte_for_byte(tmp_path: Path) -> None:
    """Line normalisation must not reach a jar, or two jars could share one digest."""

    tree = tmp_path / "tree"
    tree.mkdir()
    artifact = tree / "gradle-wrapper.jar"
    # These two differ only by the CRLF that normalisation would erase.
    artifact.write_bytes(b"PK\x03\x04\x00\x00\r\n")
    with_crlf = source_tree_sha256(tree)

    artifact.write_bytes(b"PK\x03\x04\x00\x00\n")

    assert source_tree_sha256(tree) != with_crlf
