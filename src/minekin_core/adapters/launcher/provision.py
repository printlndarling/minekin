"""Filling the content-addressed store from a reviewed plan.

`ArtifactFetcher` knows how to move bytes, and nothing drove it: the store could
never fill, so every start refused for a reason the operator could not act on.
This is the driver. It reads the artifacts a plan names, works out which are
missing, and hands exactly those to the fetcher.

The budget is explicit and it refuses rather than truncating. Filling p0-core is
about a gigabyte, and discovering that halfway through a run is not a good way
to find out.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.fetch import ArtifactFetcher, FetchFailure
from minekin_core.adapters.launcher.launch_plan import artifacts_from_plan
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability


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


def missing_artifacts(plan: Mapping[str, Any], store: ArtifactStore) -> tuple[Artifact, ...]:
    """The artifacts the plan names that the store cannot already vouch for."""

    missing: list[Artifact] = []
    for artifact in artifacts_from_plan(plan):
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
            f"fetching the missing {len(missing)} of {len(artifacts_from_plan(plan))} "
            f"artifacts needs {needed} bytes, over the {max_bytes} byte budget; "
            f"raise the budget deliberately rather than by accident"
        )
    outcome = (fetcher or ArtifactFetcher(store)).fetch(artifacts_from_plan(plan))
    return ProvisionReport(
        installed=outcome.installed,
        reused=outcome.reused,
        failed=outcome.failed,
    )
