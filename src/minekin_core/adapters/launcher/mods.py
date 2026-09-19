"""Placing the fixed mod set where the client will load it.

The plan names the mods a managed client must have. Fabric Loader reads them
from `mods/` inside the game directory, and the game directory is the session
overlay, so this is the step that puts them there.

Nothing else does. A plan that names a mod it never places produces a client
that starts vanilla and never reaches the Bridge handshake — a failure that
looks like a timeout at the other end, and one that no amount of reading the
plan would explain.

Every jar is checked against the plan's own pin on the way in. For fabric-api
that pin is a SHA-256 the recipe records alongside the store's SHA-1 key; for
the Bridge it is the digest of the reviewed build. A jar that does not match is
refused rather than copied, because a mod directory is exactly the place where
wrong bytes become a running process.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

MODS_DIRECTORY = "mods"
_WORKSPACE_PREFIX = "workspace:"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.mods",
        "install",
        ErrorCategory.SUPPLY_CHAIN,
        Retryability.OPERATOR_ACTION,
        message,
    )


def mods_directory(overlay: Path) -> Path:
    """Where Fabric Loader looks for mods, given that the overlay is the game dir."""

    if not overlay.is_absolute():
        raise _reject("the session overlay must be an absolute path")
    return overlay.resolve() / MODS_DIRECTORY


def install_fixed_mods(
    plan: Mapping[str, Any],
    *,
    overlay: Path,
    store: ArtifactStore,
    workspace_root: Path,
) -> tuple[Path, ...]:
    """Copy every fixed mod into the overlay, verifying each against its pin."""

    mods = mods_directory(overlay)
    mods.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    for record in _records(plan):
        source = _source_for(record, store=store, workspace_root=workspace_root)
        _require_pin(record, source)
        installed.append(_place(source, mods))
    return tuple(installed)


def _records(plan: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    value = cast(list[object], plan.get("fixed_mods") or [])
    if not value:
        raise _reject("the launch plan names no fixed mods to place")
    records: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise _reject("a fixed mod entry is not an object")
        records.append(cast(Mapping[str, Any], item))
    return records


def _source_for(record: Mapping[str, Any], *, store: ArtifactStore, workspace_root: Path) -> Path:
    """The jar this mod should come from, wherever the recipe says it comes from."""

    name = str(record.get("name", ""))
    source = str(record.get("source", ""))
    if not name or not source:
        raise _reject("a fixed mod entry is missing its name or source")
    if source.startswith(_WORKSPACE_PREFIX):
        jar = workspace_root / source[len(_WORKSPACE_PREFIX) :]
        if not jar.is_file():
            raise _reject(f"{name} has not been built: {jar} is missing")
        return jar
    # A fetched mod: the store keys by SHA-1, so that is what locates it, and
    # its absence is the same "fetch it first" refusal as any other artifact.
    sha1 = record.get("sha1")
    size = record.get("size")
    if not isinstance(sha1, str) or isinstance(size, bool) or not isinstance(size, int):
        raise _reject(f"{name} has no usable store identity")
    try:
        return store.verify(
            Artifact(
                coordinate=source,
                # The store keys by the basename of the artifact's path, and for
                # a fetched mod that basename is the one at the end of its URL.
                path=Path(source).name,
                url=source,
                size=size,
                sha1=sha1,
                kind=str(record.get("kind", "mod")),
            )
        )
    except MinekinError as error:
        raise _reject(f"{name} is not in the content-addressed store yet") from error


def _require_pin(record: Mapping[str, Any], source: Path) -> None:
    """Refuse a jar whose bytes are not the ones the recipe pinned."""

    name = str(record.get("name", ""))
    expected_size = record.get("size")
    expected_digest = record.get("sha256")
    if (
        not isinstance(expected_digest, str)
        or isinstance(expected_size, bool)
        or not isinstance(expected_size, int)
    ):
        raise _reject(f"{name} has no usable digest pin")
    size = source.stat().st_size
    if size != expected_size:
        raise _reject(f"{name} is {size} bytes, not the reviewed {expected_size}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != expected_digest:
        raise _reject(f"{name} is not the reviewed build: {digest} is not the pinned digest")


def _place(source: Path, mods: Path) -> Path:
    """Copy the jar in through a staging name so a reader never sees half a file."""

    target = mods / source.name
    staging = mods / f".{uuid.uuid4().hex}.part"
    try:
        shutil.copyfile(source, staging)
        os.replace(staging, target)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    return target
