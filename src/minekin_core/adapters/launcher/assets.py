"""Materialising the asset view the client reads.

The plan gives the client `--assetsDir bundle/assets` and `--assetIndex 19`, and
the client then reads `<assetsDir>/indexes/19.json` and, for every object that
index names, `<assetsDir>/objects/<hh>/<hash>`. The store keeps those objects
under its own content-addressed layout, which the client does not speak, so
something has to turn one into the other. Nothing did, and the client said so
once, in a line that does not read like a missing step: "Can't open the resource
index file: .../bundle/assets/indexes/19.json".

The view is per *run* rather than per generation. It is read-only, it is the
same bytes for every session of the Kin, and copying a few hundred megabytes
once is worth not copying them again for every generation — so a view that is
already there is left alone.

The files are copies rather than hard links to the store, which they could be,
because a hard link would make a corrupted view and a corrupted *store* the same
bytes: the store is what every later verification hashes, and it is worth more
than the disk this saves.

`BundleStore` publishes to `<root>/<bundle_id>/...` and this view is not that:
the plan names a stable `bundle/assets`, and the plan is what the client was
given, so the view goes where the plan says.
"""

from __future__ import annotations

import os
import shutil
import stat
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.launch_plan import artifacts_from_plan
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.process import resolve_plan_path
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

ASSETS_DIRECTORY = "assets"
_ASSET_KINDS = frozenset({"asset", "asset-index"})


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.assets",
        "materialise",
        ErrorCategory.SUPPLY_CHAIN,
        Retryability.OPERATOR_ACTION,
        message,
    )


@dataclass(frozen=True, slots=True)
class AssetView:
    """What a materialised view holds, for a caller that wants to report it."""

    directory: Path
    index: Path
    objects: int
    copied: int


def materialise_assets(
    plan: Mapping[str, Any], *, run_root: Path, overlay: Path, store: ArtifactStore
) -> AssetView:
    """Copy the asset view out of the store, leaving anything already there."""

    runtime = _runtime(plan)
    index_name = _text(runtime, "assets_index_name")

    assets_directory = resolve_plan_path(run_root, overlay, _text(runtime, "assets_dir"))
    view_root = assets_directory.parent
    index_source = _text(runtime, "asset_index")
    assets = [item for item in artifacts_from_plan(plan) if item.kind in _ASSET_KINDS]
    if not assets:
        raise _reject("the launch plan names no assets to materialise")

    index_record = _record(plan, index_source)
    expected_index = assets_directory / "indexes" / f"{index_name}.json"
    if view_root / _text(index_record, "path") != expected_index:
        raise _reject(
            "the plan's asset index is not where the index name says the client will "
            f"read it: {index_name} names {expected_index}"
        )

    objects = 0
    copied = 0
    index: Path | None = None
    for artifact in assets:
        # Resolved before it is compared: `bundle/assets/../../etc/passwd` is
        # inside the assets directory as a string and outside it as a path.
        destination = (view_root / artifact.path).resolve()
        if not destination.is_relative_to(assets_directory):
            # The plan's own view path has to stay inside the directory the
            # client is given, or the two disagree about where assets live.
            raise _reject(
                f"the plan names {artifact.path} outside the assets directory it "
                f"gives the client: {assets_directory}"
            )
        if _already_there(destination, artifact):
            placed = destination
        else:
            placed = _place(store.verify(artifact), destination)
            copied += 1
        if artifact.kind == "asset-index":
            index = placed
        else:
            objects += 1
    if index is None:
        raise _reject("the plan names no asset index to materialise")
    return AssetView(directory=assets_directory, index=index, objects=objects, copied=copied)


def _runtime(plan: Mapping[str, Any]) -> dict[str, Any]:
    value = plan.get("runtime")
    if not isinstance(value, dict):
        raise _reject("launch plan runtime must be an object")
    return cast(dict[str, Any], value)


def _text(section: Mapping[str, Any], key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value:
        raise _reject(f"launch plan {key} is required")
    return value


def _record(plan: Mapping[str, Any], store_path: str) -> Mapping[str, Any]:
    entries = cast(list[object], plan.get("artifacts") or [])
    if not entries:
        raise _reject("the launch plan names no assets to materialise")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        record = cast(Mapping[str, Any], entry)
        if record.get("store_path") == store_path:
            return record
    raise _reject("the plan names an asset index that is not one of its artifacts")


def _already_there(destination: Path, artifact: Artifact) -> bool:
    """True when this view already holds the artifact, complete.

    Only files this function wrote get here: it writes through a staging name
    and replaces, so a file that exists at the right size is a whole one, and
    one at the wrong size is not trusted.
    """

    if destination.is_symlink() or not destination.is_file():
        return False
    return destination.stat().st_size == artifact.size


def _place(source: Path, destination: Path) -> Path:
    """Copy the verified blob in through a staging name, then make it read-only."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{uuid.uuid4().hex}.part")
    try:
        shutil.copyfile(source, staging)
        staging.chmod(staging.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        os.replace(staging, destination)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    return destination
