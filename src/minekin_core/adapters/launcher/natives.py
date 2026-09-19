"""Putting the pinned native libraries where the client will look for them.

A native is not a class container, so the plan names it apart from the classpath:
`native_artifacts` are the jars, `native_extract_excludes` is what not to take out
of them, and `natives_dir` is where the client is told to look — it reaches the
client as `-Djava.library.path=<overlay>/natives`. Nothing extracted them.

The failure that produces is a long way from its cause: the Loader resolves the
whole classpath, starts Minecraft, and only when the render thread first touches
LWJGL does it say `UnsatisfiedLinkError: Failed to locate library: liblwjgl.so`.
Everything before that looks like a working launch, which is why this is worth a
module of its own rather than a line in the start path.

Entries are written through a staging name and replaced into place, so a reader
never sees half a library, and every entry name is refused unless it stays inside
the natives directory — a jar is attacker-reachable input in the general case,
and `../` in an entry name is the classic way out of one.
"""

from __future__ import annotations

import hashlib
import os
import uuid
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, cast

from minekin_core.adapters.launcher.artifacts import ArtifactStore, store_relative_path
from minekin_core.adapters.launcher.launch_plan import artifacts_from_plan
from minekin_core.adapters.launcher.process import resolve_plan_path
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.natives",
        "extract",
        ErrorCategory.SUPPLY_CHAIN,
        Retryability.OPERATOR_ACTION,
        message,
    )


def materialise_natives(
    plan: Mapping[str, Any], *, run_root: Path, overlay: Path, store: ArtifactStore
) -> tuple[Path, ...]:
    """Extract every native the plan declares into the overlay's natives directory.

    Only the artifacts the plan names as natives are opened: the classpath jars
    are not native containers, and reading them for libraries would turn a
    mistake in the plan into files in a directory the client loads code from.
    """

    declared = _declared_natives(plan)
    excludes = _excludes(plan)
    # Where the client is told to look, resolved the way the launch resolves it:
    # one statement of what a plan path means, so the launch and this cannot
    # come to different answers about the same directory.
    target = resolve_plan_path(run_root, overlay, _natives_directory(plan))
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    digests: dict[str, str] = {}
    for artifact in artifacts_from_plan(plan):
        if store_relative_path(artifact) not in declared:
            continue
        # A native that is not in the store refuses in the store's own words,
        # which are the ones that say to fetch it.
        source = store.verify(artifact)
        for name, payload in _contents(source, excludes=excludes):
            digest = hashlib.sha256(payload).hexdigest()
            previous = digests.get(name)
            if previous is not None and previous != digest:
                raise _reject(
                    f"two pinned natives contain different {name}: {source.name} "
                    "disagrees with a jar already extracted into this session"
                )
            digests[name] = digest
            written.append(_place(target, name, payload))
    if not written:
        # An empty natives directory is exactly the failure this exists to stop,
        # so it is refused here rather than reported by a client much later.
        raise _reject(
            "the plan declares natives but none of them contained a library; "
            "the client would be given a library path with nothing in it"
        )
    return tuple(written)


def _natives_directory(plan: Mapping[str, Any]) -> str:
    directories = _runtime(plan, "natives_dir")
    if len(directories) != 1 or not isinstance(directories[0], str) or not directories[0]:
        raise _reject("launch plan runtime.natives_dir must name one directory")
    return directories[0]


def _declared_natives(plan: Mapping[str, Any]) -> set[str]:
    values = _runtime(plan, "native_artifacts")
    if not values:
        raise _reject("the launch plan declares no natives to extract")
    declared: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value:
            raise _reject("a native artifact entry is not a path")
        declared.add(value)
    return declared


def _excludes(plan: Mapping[str, Any]) -> tuple[str, ...]:
    excludes: list[str] = []
    for value in _runtime(plan, "native_extract_excludes"):
        if not isinstance(value, str) or not value:
            raise _reject("a native extraction exclude is not a prefix")
        excludes.append(value)
    return tuple(excludes)


def _runtime(plan: Mapping[str, Any], key: str) -> list[object]:
    runtime = plan.get("runtime")
    if not isinstance(runtime, dict):
        raise _reject("launch plan runtime must be an object")
    value = cast(dict[str, Any], runtime).get(key)
    if isinstance(value, str):
        return [value]
    return list(cast(list[object], value or []))


def _contents(jar: Path, *, excludes: Sequence[str]) -> Iterator[tuple[str, bytes]]:
    try:
        with zipfile.ZipFile(jar) as archive:
            for info in archive.infolist():
                if info.is_dir() or _excluded(info.filename, excludes):
                    continue
                yield entry_relative_path(info.filename), archive.read(info)
    except zipfile.BadZipFile as error:
        raise _reject(f"{jar.name} is not a readable jar") from error


def _excluded(name: str, excludes: Sequence[str]) -> bool:
    return any(name.startswith(prefix) for prefix in excludes)


def entry_relative_path(name: str) -> str:
    """The entry's path inside the natives directory, or a refusal.

    Refused outright: an absolute name, any `..` part, and anything carrying a
    backslash or a colon — on Windows those make a join with the natives
    directory produce a path with a drive of its own, which is the same escape
    by another route.
    """

    if "\\" in name or ":" in name:
        raise _reject(f"a native entry names a path outside the natives directory: {name}")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise _reject(f"a native entry names a path outside the natives directory: {name}")
    return path.as_posix()


def _place(target: Path, name: str, payload: bytes) -> Path:
    """Write one entry through a staging name so a reader never sees half a file."""

    destination = target / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{uuid.uuid4().hex}.part")
    try:
        staging.write_bytes(payload)
        os.replace(staging, destination)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    return destination
