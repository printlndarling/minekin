"""The read-only `server probe` command.

Peeks at a saved profile's schema version, strict-loads it with the matching
loader, and runs one Server List Ping probe against it. Nothing here creates a
session, a JVM or a lease, and the observation document is the whole answer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from minekin_core.adapters.launcher.server_probe import probe_profile
from minekin_core.adapters.launcher.server_profile import (
    PROFILE_SCHEMA_VERSION,
    PROFILE_SCHEMA_VERSION_V2,
    ManagedTargetProfile,
    ServerProfile,
    load_managed_target_profile,
    load_server_profile,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.version_probe import ProbeObservation, ProbeOutcome

ProbeProfile = ServerProfile | ManagedTargetProfile


def _fail(message: str) -> MinekinError:
    return MinekinError(
        "cli",
        "server probe",
        ErrorCategory.CONFIG,
        Retryability.OPERATOR_ACTION,
        message,
    )


def _peek_schema_version(path: Path) -> int:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _fail(f"the saved profile could not be read: {error}") from error
    if not isinstance(parsed, dict):
        raise _fail("the saved profile is not an object")
    document = cast("dict[str, object]", parsed)
    version = document.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise _fail("the saved profile has no integer schema_version")
    return version


def load_profile_for_probe(path: Path) -> ProbeProfile:
    """Dispatch on the saved schema version; each loader then does its own strict read."""

    version = _peek_schema_version(path)
    if version == PROFILE_SCHEMA_VERSION:
        return load_server_profile(path)
    if version == PROFILE_SCHEMA_VERSION_V2:
        return load_managed_target_profile(path)
    raise _fail(f"schema_version {version} has no probe loader")


def run_probe(path: Path, *, timeout_s: float) -> ProbeObservation:
    """Probe one saved profile and return its observation."""

    return probe_profile(load_profile_for_probe(path), timeout_s=timeout_s)


def probe_exit_ok(observation: ProbeObservation) -> bool:
    return observation.outcome is ProbeOutcome.OBSERVED
