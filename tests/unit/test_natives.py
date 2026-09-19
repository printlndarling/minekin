"""Extracting the pinned natives, and what is refused on the way out of a jar."""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore, store_relative_path
from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.natives import (
    NATIVES_DIRECTORY,
    entry_relative_path,
    materialise_natives,
    natives_directory,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError

PROFILE = Path(__file__).parents[1] / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"
LIBRARY = b"\x7fELF a shared library\n"
EXCLUDES = ["META-INF/"]


def _jar(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
        # A directory entry, which a real natives jar has and which is not a file.
        archive.writestr("org/", b"")
    return buffer.getvalue()


def _hostile_jar(*names: str) -> bytes:
    """A jar whose entry names are exactly what is given, with nothing rewritten.

    `ZipInfo` replaces a backslash with a slash as it is constructed — right for
    a zip written on Windows, wrong for this test: what a reader may see is what
    is in the file, whatever happened to write it.
    """

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            info = zipfile.ZipInfo("placeholder")
            info.filename = name
            archive.writestr(info, LIBRARY)
    return buffer.getvalue()


def _native(payload: bytes, *, coordinate: str = "org.lwjgl:lwjgl:3.3.3") -> Artifact:
    return Artifact(
        coordinate=coordinate,
        path="org/lwjgl/lwjgl/3.3.3/lwjgl-3.3.3-natives-linux.jar",
        url="https://example.invalid/lwjgl-natives-linux.jar",
        size=len(payload),
        sha1=hashlib.sha1(payload).hexdigest(),
        kind="native",
    )


def _plan(*artifacts: Artifact, natives: tuple[Artifact, ...] | None = None) -> dict[str, Any]:
    declared = artifacts if natives is None else natives
    return {
        "artifacts": [
            asdict(artifact) | {"store_path": store_relative_path(artifact)}
            for artifact in artifacts
        ],
        "runtime": {
            "natives_dir": "session/natives",
            "native_artifacts": [store_relative_path(artifact) for artifact in declared],
            "native_extract_excludes": list(EXCLUDES),
        },
    }


def _store(tmp_path: Path, *artifacts: Artifact, payloads: dict[str, bytes]) -> ArtifactStore:
    store = ArtifactStore(tmp_path / "artifact-store")
    for artifact in artifacts:
        store.install(artifact, io.BytesIO(payloads[artifact.coordinate]))
    return store


def _overlay(tmp_path: Path) -> Path:
    overlay = tmp_path / "run" / "session" / "session-01" / "generation-1"
    overlay.mkdir(parents=True)
    return overlay


def test_the_libraries_land_where_the_plan_tells_the_client_to_look(tmp_path: Path) -> None:
    """`java.library.path` names a directory, so something has to fill it."""

    payload = _jar({"liblwjgl.so": LIBRARY, "META-INF/MANIFEST.MF": b"manifest"})
    native = _native(payload)
    store = _store(tmp_path, native, payloads={native.coordinate: payload})
    overlay = _overlay(tmp_path)

    written = materialise_natives(_plan(native), overlay=overlay, store=store)

    assert [path.name for path in written] == ["liblwjgl.so"]
    assert (overlay / NATIVES_DIRECTORY / "liblwjgl.so").read_bytes() == LIBRARY
    # The directory entry in the jar is not a file, and the excluded prefix is
    # not extracted.
    assert sorted(item.name for item in (overlay / NATIVES_DIRECTORY).iterdir()) == ["liblwjgl.so"]

    # And that is the directory the plan's own paths name: the plan says where
    # relative to the session root, and the overlay is the session root.
    plan = build_launch_plan(PROFILE)
    declared = PurePosixPath(plan["runtime"]["natives_dir"])
    assert declared.parts[0] == "session"
    assert natives_directory(overlay) == overlay / PurePosixPath(*declared.parts[1:])
    assert f"-Djava.library.path={declared}" in plan["runtime"]["jvm_args"]


def test_a_second_native_that_agrees_is_not_a_conflict(tmp_path: Path) -> None:
    payload = _jar({"liblwjgl.so": LIBRARY})
    first, second = (
        _native(payload, coordinate="org.lwjgl:lwjgl:3.3.3"),
        _native(payload, coordinate="org.lwjgl:lwjgl-glfw:3.3.3"),
    )
    store = _store(
        tmp_path,
        first,
        second,
        payloads={first.coordinate: payload, second.coordinate: payload},
    )

    written = materialise_natives(_plan(first, second), overlay=_overlay(tmp_path), store=store)

    assert len(written) == 2


def test_two_natives_that_disagree_about_a_library_are_refused(tmp_path: Path) -> None:
    """Whichever of them ran second would win, and nothing would say so."""

    first_payload = _jar({"liblwjgl.so": LIBRARY})
    second_payload = _jar({"liblwjgl.so": LIBRARY.replace(b"shared", b"other!")})
    first = _native(first_payload, coordinate="org.lwjgl:lwjgl:3.3.3")
    second = _native(second_payload, coordinate="org.lwjgl:lwjgl-glfw:3.3.3")
    store = _store(
        tmp_path,
        first,
        second,
        payloads={first.coordinate: first_payload, second.coordinate: second_payload},
    )

    with pytest.raises(MinekinError, match="disagrees with a jar already extracted") as raised:
        materialise_natives(_plan(first, second), overlay=_overlay(tmp_path), store=store)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


@pytest.mark.parametrize(
    "name",
    [
        "../escape.so",
        "lib/../../escape.so",
        "/absolute.so",
        "C:/drive.so",
    ],
)
def test_an_entry_that_points_outside_the_natives_directory_is_refused(
    tmp_path: Path, name: str
) -> None:
    """A jar is input from an upstream; an entry name is not a path to trust."""

    payload = _hostile_jar(name)
    native = _native(payload)
    store = _store(tmp_path, native, payloads={native.coordinate: payload})
    overlay = _overlay(tmp_path)

    with pytest.raises(MinekinError, match="outside the natives directory") as raised:
        materialise_natives(_plan(native), overlay=overlay, store=store)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert not (overlay.parent / "escape.so").exists()


@pytest.mark.parametrize(
    "name",
    [
        r"lib\windows.so",
        r"..\escape.so",
        r"C:\drive.so",
        r"\\server\share\lib.so",
    ],
)
def test_a_backslash_entry_is_refused_where_the_rule_lives(name: str) -> None:
    """A jar cannot carry this name on Windows, and Windows is not the target.

    `zipfile` replaces `os.sep` with `/` both when it writes and when it reads,
    so on Windows a backslash in an entry name is invisible to a reader and no
    jar built here can test it. On Linux `os.sep` is `/`, nothing rewrites the
    name, and a join with the natives directory would let it out — which is the
    platform this runs on, so the rule is checked where it is decided.
    """

    with pytest.raises(MinekinError, match="outside the natives directory"):
        entry_relative_path(name)


def test_an_artifact_the_plan_does_not_call_a_native_is_not_opened(tmp_path: Path) -> None:
    """The classpath jars are not native containers, and this is what says so."""

    native_payload = _jar({"liblwjgl.so": LIBRARY})
    library_payload = _jar({"libsmuggled.so": LIBRARY})
    native = _native(native_payload)
    library = Artifact(
        coordinate="com.mojang:minecraft:1.21.4",
        path="versions/1.21.4/1.21.4.jar",
        url="https://example.invalid/1.21.4.jar",
        size=len(library_payload),
        sha1=hashlib.sha1(library_payload).hexdigest(),
        kind="client",
    )
    store = _store(
        tmp_path,
        native,
        library,
        payloads={native.coordinate: native_payload, library.coordinate: library_payload},
    )
    overlay = _overlay(tmp_path)

    written = materialise_natives(
        _plan(native, library, natives=(native,)), overlay=overlay, store=store
    )

    assert [path.name for path in written] == ["liblwjgl.so"]
    assert not (overlay / NATIVES_DIRECTORY / "libsmuggled.so").exists()


def test_a_native_that_is_not_in_the_store_is_refused(tmp_path: Path) -> None:
    payload = _jar({"liblwjgl.so": LIBRARY})
    native = _native(payload)
    store = ArtifactStore(tmp_path / "artifact-store")

    with pytest.raises(MinekinError, match="missing from the content-addressed store"):
        materialise_natives(_plan(native), overlay=_overlay(tmp_path), store=store)


def test_a_plan_with_no_natives_is_refused(tmp_path: Path) -> None:
    """The client is told to look in a directory; an empty one is the failure."""

    payload = _jar({"liblwjgl.so": LIBRARY})
    native = _native(payload)
    store = _store(tmp_path, native, payloads={native.coordinate: payload})

    with pytest.raises(MinekinError, match="declares no natives to extract"):
        materialise_natives(_plan(native, natives=()), overlay=_overlay(tmp_path), store=store)


def test_a_native_that_yields_no_library_is_refused(tmp_path: Path) -> None:
    payload = _jar({"META-INF/MANIFEST.MF": b"manifest"})
    native = _native(payload)
    store = _store(tmp_path, native, payloads={native.coordinate: payload})

    with pytest.raises(MinekinError, match="none of them contained a library"):
        materialise_natives(_plan(native), overlay=_overlay(tmp_path), store=store)


def test_a_jar_that_is_not_a_jar_is_refused(tmp_path: Path) -> None:
    payload = b"not a zip at all"
    native = _native(payload)
    store = _store(tmp_path, native, payloads={native.coordinate: payload})

    with pytest.raises(MinekinError, match="not a readable jar"):
        materialise_natives(_plan(native), overlay=_overlay(tmp_path), store=store)
