from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.adapters.launcher.offline_session import OFFLINE_SESSION_CANDIDATES
from minekin_core.adapters.launcher.process import (
    RUN_ROOT_PREFIXES,
    argument_digest,
    build_process_spec,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.ids import OpaqueId
from minekin_core.domain.offline_identity import OfflineIdentityMaterial

PROFILE = Path(__file__).resolve().parents[1] / "fixtures/runtime-input/bundle-p0-core-1.21.4.json"
# Resolved once so the expected strings match on any host platform.
RUN_ROOT = Path("/srv/minekin/run").resolve()
JAVA = Path("/usr/lib/jvm/temurin-21/bin/java")
OFF_A = OFFLINE_SESSION_CANDIDATES[0]


def material(username: str = "Kin") -> OfflineIdentityMaterial:
    return OfflineIdentityMaterial(
        local_profile_id=OpaqueId("kin-01"),
        identity_revision=1,
        username=username,
        created_at="2026-09-19T00:00:00Z",
    )


def plan() -> dict[str, Any]:
    return build_launch_plan(PROFILE)


def spec(plan_document: dict[str, Any] | None = None, **overrides: object):
    arguments: dict[str, object] = {
        "run_root": RUN_ROOT,
        "material": material(),
        "candidate": OFF_A,
        "java_executable": JAVA,
    }
    arguments.update(overrides)
    return build_process_spec(plan_document or plan(), **arguments)  # type: ignore[arg-type]


def element_after(argv: tuple[str, ...], option: str) -> str:
    return argv[argv.index(option) + 1]


def test_the_command_line_starts_with_the_java_executable_and_ends_with_the_game() -> None:
    built = spec()

    assert built.main_class == "net.fabricmc.loader.impl.launch.knot.KnotClient"
    assert built.main_class in built.argv
    assert element_after(built.argv, "--username") == "Kin"
    assert element_after(built.argv, "--userType") == "offline"


def test_every_path_bearing_jvm_argument_is_absolutised() -> None:
    built = spec()

    for argument in built.argv:
        if argument.startswith("-D") and "=" in argument:
            value = argument.split("=", 1)[1]
            if value.startswith(RUN_ROOT_PREFIXES):
                pytest.fail(f"{argument!r} was left relative")


def test_no_argument_survives_as_a_run_root_relative_path() -> None:
    built = spec()

    offenders = [item for item in built.argv if item.startswith(RUN_ROOT_PREFIXES)]
    assert offenders == []


def test_the_classpath_is_rebuilt_entry_by_entry() -> None:
    document = plan()
    built = spec(document)

    joined = element_after(built.argv, "-cp")
    expected = [str(RUN_ROOT / entry) for entry in document["runtime"]["classpath"]]

    # Compared as a whole: splitting on ":" would break Windows drive letters.
    assert joined == ":".join(expected)
    assert len(built.argv[built.argv.index("-cp") + 1].split("artifact-store")) - 1 == len(expected)


def test_the_natives_directory_is_absolute_in_every_argument_that_names_it() -> None:
    built = spec()

    named = [item for item in built.argv if item.endswith("=session/natives")]
    assert named == []
    pointing = [
        item for item in built.argv if item.split("=", 1)[-1] == str(RUN_ROOT / "session/natives")
    ]
    assert len(pointing) == 4


def test_an_argument_left_as_a_relative_plan_path_is_refused() -> None:
    """A relative path would resolve against the game directory, not the run root."""

    document = copy.deepcopy(plan())
    document["runtime"]["jvm_args"].append("session/orphan")

    with pytest.raises(MinekinError, match="left as a run-root-relative path"):
        spec(document)


def test_the_client_runs_inside_the_session_game_directory() -> None:
    built = spec()

    assert built.working_directory == RUN_ROOT / "session/game"
    assert element_after(built.argv, "--gameDir") == str(built.working_directory)
    assert element_after(built.argv, "--assetsDir") == str(RUN_ROOT / "bundle/assets")


def test_the_empty_client_credentials_stay_their_own_elements() -> None:
    """The frozen offline parity is an explicit empty element after each option."""

    built = spec()

    assert element_after(built.argv, "--clientId") == ""
    assert element_after(built.argv, "--accessToken") == "0"
    assert built.argv[built.argv.index("--xuid") + 2] == "--userType"


def test_a_class_name_that_contains_a_dot_minecraft_is_not_a_path() -> None:
    """`net.minecraft.client.main.Main` is Fabric's emulation flag, not a directory."""

    built = spec()

    assert any("net.minecraft.client.main.Main" in item for item in built.argv)


def test_an_argument_that_really_names_the_host_minecraft_directory_is_refused() -> None:
    document = copy.deepcopy(plan())
    document["runtime"]["jvm_args"].append("-Dhostmods=/home/operator/.minecraft/mods")

    with pytest.raises(MinekinError, match=r"host \.minecraft directory"):
        spec(document)


@pytest.mark.parametrize("path", ["/etc/passwd", "../outside/game", "elsewhere/game"])
def test_an_environment_path_outside_the_reviewed_prefixes_is_refused(path: str) -> None:
    document = copy.deepcopy(plan())
    document["runtime"]["game_dir"] = path

    with pytest.raises(MinekinError, match=r"run-root|outside the reviewed"):
        spec(document)


def test_a_relative_run_root_is_refused() -> None:
    with pytest.raises(MinekinError, match="absolute path") as raised:
        spec(run_root=Path("relative/run"))

    assert raised.value.category is ErrorCategory.CONFIG


def test_a_cp_option_without_its_classpath_is_refused() -> None:
    """The next element must not be mistaken for the classpath and swallowed."""

    document = copy.deepcopy(plan())
    arguments = document["runtime"]["jvm_args"]
    del arguments[arguments.index("-cp") + 1]

    with pytest.raises(MinekinError, match="not followed by a classpath"):
        spec(document)


def test_a_trailing_cp_option_is_refused() -> None:
    document = copy.deepcopy(plan())
    document["runtime"]["jvm_args"] = ["-Djava.library.path=session/natives", "-cp"]

    with pytest.raises(MinekinError, match="no classpath element"):
        spec(document)


def test_a_different_identity_produces_a_different_command_line() -> None:
    first = spec()
    second = spec(material=material("Notch"))

    assert first.argv != second.argv
    assert first.as_document()["argv_digest"] != second.as_document()["argv_digest"]
    assert element_after(second.argv, "--username") == "Notch"


def test_the_same_inputs_produce_the_same_digest() -> None:
    assert spec().as_document()["argv_digest"] == spec().as_document()["argv_digest"]


def test_the_digest_cannot_be_confused_by_argument_boundaries() -> None:
    """A NUL join keeps ["a b"] and ["a", "b"] apart, where a space join would not."""

    assert argument_digest(("a b",)) != argument_digest(("a", "b"))


def test_the_evidence_document_names_what_was_invoked_without_dumping_it() -> None:
    document = spec().as_document()

    assert document == {
        "java_executable": str(JAVA),
        "working_directory": str(RUN_ROOT / "session/game"),
        "run_root": str(RUN_ROOT),
        "main_class": "net.fabricmc.loader.impl.launch.knot.KnotClient",
        "argv_length": len(spec().argv),
        "argv_digest": document["argv_digest"],
    }
    assert isinstance(document["argv_digest"], str)
    assert json.dumps(document)  # evidence documents must be serialisable
