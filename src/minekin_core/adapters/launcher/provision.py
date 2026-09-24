"""Filling the content-addressed store from a reviewed plan.

`ArtifactFetcher` knows how to move bytes, and nothing drove it: the store could
never fill, so every start refused for a reason the operator could not act on.
This is the driver. It reads the artifacts a plan names, works out which are
missing, and hands exactly those to the fetcher.

The budget is explicit and it refuses rather than truncating. Filling p0-core is
about a gigabyte, and discovering that halfway through a run is not a good way
to find out.

`require_reviewed_plan` is the same job with a reviewed entry in front of it: it
hands back the plan one registry entry pins, and refuses an entry whose recipe,
plan or bridge digest does not match what is on disk. A recipe that describes
itself as tested is not what gets installed here — only an entry the review
marked `tested` is.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.fetch import ArtifactFetcher, FetchFailure
from minekin_core.adapters.launcher.launch_plan import (
    artifacts_from_plan,
    build_launch_plan,
    find_workspace_root,
)
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.mods import fetched_mod_artifact
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.version_resolution import (
    BundleStatus,
    RegistryEntry,
    load_reviewed_registry,
)


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.provision",
        "fetch",
        ErrorCategory.SUPPLY_CHAIN,
        Retryability.OPERATOR_ACTION,
        message,
    )


@dataclass(frozen=True, slots=True)
class ProvisionReport:
    installed: tuple[str, ...]
    reused: tuple[str, ...]
    failed: tuple[FetchFailure, ...]

    @property
    def complete(self) -> bool:
        return not self.failed

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": "complete" if self.complete else "incomplete",
            "installed": len(self.installed),
            "reused": len(self.reused),
            "failed": [
                {
                    "coordinate": failure.coordinate,
                    "url": failure.url,
                    "category": failure.category.value,
                    "reason": failure.reason,
                }
                for failure in self.failed
            ],
        }


def plan_fetch_set(plan: Mapping[str, Any]) -> tuple[Artifact, ...]:
    """Everything the plan says has to be fetched, mods included.

    The fixed mods are not in the artifact list, because a mod is loaded from
    the game directory rather than from the classpath — but a fetched one still
    has to reach the store before it can be placed there, and nothing else
    fetches it. Without this a full fetch leaves `install_fixed_mods` refusing
    fabric-api as a missing download.
    """

    records = cast(Iterable[Mapping[str, Any]], plan.get("fixed_mods") or ())
    mods = (fetched_mod_artifact(record) for record in records)
    return (*artifacts_from_plan(plan), *(mod for mod in mods if mod is not None))


def missing_artifacts(plan: Mapping[str, Any], store: ArtifactStore) -> tuple[Artifact, ...]:
    """The artifacts the plan names that the store cannot already vouch for."""

    missing: list[Artifact] = []
    for artifact in plan_fetch_set(plan):
        try:
            store.verify(artifact)
        except MinekinError:
            missing.append(artifact)
    return tuple(missing)


def provision_bundle(
    plan: Mapping[str, Any],
    store: ArtifactStore,
    *,
    fetcher: ArtifactFetcher | None = None,
    max_bytes: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> ProvisionReport:
    """Fetch everything the plan names that is not already verified.

    `max_bytes` bounds what this pass is allowed to *fetch*, not what it is
    allowed to find. A store that is already full costs nothing and is never
    refused for its size.
    """

    if max_bytes is not None and max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    missing = missing_artifacts(plan, store)
    needed = sum(artifact.size for artifact in missing)
    if max_bytes is not None and needed > max_bytes:
        raise _reject(
            f"fetching the missing {len(missing)} of {len(plan_fetch_set(plan))} "
            f"artifacts needs {needed} bytes, over the {max_bytes} byte budget; "
            f"raise the budget deliberately rather than by accident"
        )
    outcome = (fetcher or ArtifactFetcher(store)).fetch(
        plan_fetch_set(plan), on_progress=on_progress
    )
    return ProvisionReport(
        installed=outcome.installed,
        reused=outcome.reused,
        failed=outcome.failed,
    )


def _reviewed_digest(path: Path) -> str:
    """Hash a checked-out file the way the fixture manifest does.

    Text only, so a Windows and a Linux checkout of the same recipe agree: the
    reviewed digest has to be comparable to the bytes on disk without the answer
    depending on how the clone was made.
    """

    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return hashlib.sha256(raw).hexdigest()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _plan_bridge_digest(plan: Mapping[str, Any]) -> str | None:
    """The sha256 the plan carries for its bridge jar, or None if it names none."""

    for value in cast(list[object], plan.get("fixed_mods") or []):
        if not isinstance(value, dict):
            continue
        record = cast(dict[str, object], value)
        if record.get("kind") != "bridge":
            continue
        digest = record.get("sha256")
        return digest if isinstance(digest, str) else None
    return None


def reviewed_entry(registry_path: Path, bundle_id: str) -> RegistryEntry:
    """The one registry entry a bundle id names, refusing to guess a nearby one."""

    try:
        document = json.loads(registry_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject(
            f"{registry_path.name} is not readable UTF-8 JSON; an installation needs the "
            f"reviewed registry itself, not a placeholder for it"
        ) from error
    registry = load_reviewed_registry(document)
    entry = registry.by_id().get(bundle_id)
    if entry is None:
        raise _reject(
            f"{bundle_id} is not an entry of the reviewed registry at revision {registry.revision}"
        )
    return entry


def require_reviewed_plan(
    entry: RegistryEntry, *, workspace_root: Path | None = None
) -> dict[str, Any]:
    """The launch plan one entry pins, refusing what the entry cannot vouch for.

    Three digests have to agree before anything is fetched: the recipe file on disk
    against `recipe_digest`, the plan built from it against `launch_plan_digest`, and
    the bridge the plan carries against `bridge_digest`. The last two overlap — the
    plan digest already covers its own fixed mods — and that is deliberate: an entry
    whose bridge citation disagrees with its plan citation is internally broken, and a
    refusal naming which citation moved is shorter to act on than "a digest differed".

    A recipe that calls itself `tested` is not what this checks. The entry's status is
    the review's word, so that is what the gate reads.
    """

    if entry.status is not BundleStatus.TESTED:
        raise _reject(
            f"{entry.bundle_id} is `{entry.status.value}` in the reviewed registry, not "
            f"`tested`; only a reviewed tested combination may be installed"
        )
    root = workspace_root or find_workspace_root(Path(__file__).resolve())
    recipe_path = root / entry.recipe_path
    try:
        actual_recipe = _reviewed_digest(recipe_path)
    except OSError as error:
        raise _reject(
            f"recipe {entry.recipe_path} named by {entry.bundle_id} is not readable"
        ) from error
    if actual_recipe != entry.recipe_digest:
        raise _reject(
            f"recipe {entry.recipe_path} digests to {actual_recipe}, not the reviewed "
            f"{entry.recipe_digest}"
        )
    plan = build_launch_plan(recipe_path.resolve(), workspace_root=root)
    if plan["plan_sha256"] != entry.launch_plan_digest:
        raise _reject(
            f"the launch plan built from {entry.recipe_path} digests to {plan['plan_sha256']}, "
            f"not the reviewed {entry.launch_plan_digest}"
        )
    bridge = _plan_bridge_digest(plan)
    if bridge != entry.bridge_digest:
        raise _reject(
            f"the launch plan carries bridge {bridge}, not the reviewed {entry.bridge_digest}"
        )
    return plan
