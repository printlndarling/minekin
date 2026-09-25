"""The `session start --auto-bundle` path: decide what may run, then hand off.

Every part of this decision already existed and had no caller: the probe reads a target,
the resolver picks the one reviewed registry entry it matches, the V06 gate proves that
entry's recipe/plan/bridge digests, the installer fills the content-addressed store, and
`session start` launches. What was missing is the caller that runs them in one order and
stops at the first step that does not line up. That caller is this module, and it never
touches a JVM itself — `bootstrap.py` hands the recipe returned here to
`start_and_supervise`, the same function the explicit `--profile` path calls.

The refusals are the deliverable. Three version facts have to agree (what the target was
observed as, what the registry says may run against it, and what the recipe claims its
client will be), and the old client has to be *shown* stopped before a new one starts.
Neither is allowed to degrade into a guess, so each mismatch ends here with a stable
category, and nothing is launched, downloaded or killed on the way out.
"""

from __future__ import annotations

import json
import platform
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.launch_plan import find_workspace_root
from minekin_core.adapters.launcher.orphans import (
    Liveness,
    default_cmdline,
    default_probe,
    session_claims,
    stop_recorded_clients,
    terminate_process,
)
from minekin_core.adapters.launcher.provision import (
    missing_artifacts,
    plan_fetch_set,
    provision_bundle,
    require_reviewed_plan,
)
from minekin_core.cli.server_probe import run_probe
from minekin_core.cli.session import launched_minecraft_version
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.version_probe import ProbeObservation
from minekin_core.domain.version_resolution import (
    RegistryEntry,
    ResolutionDecision,
    ResolutionStatus,
    ReviewedBundleRegistry,
    load_reviewed_registry,
    resolve,
)

#: The same wait the read-only `server probe` command defaults to. Two probes of one
#: target are the price of this path, and a longer read is a different question.
DEFAULT_PROBE_TIMEOUT_S = 5.0
#: How long a stopped client gets to actually be gone. `stop_recorded_clients` only sends
#: the signal, and a start that raced the exit would mean two clients in one world.
DEFAULT_STOP_WAIT_S = 30.0
_STOP_POLL_S = 0.25


def _reject(
    message: str,
    category: ErrorCategory = ErrorCategory.CONFIG,
    *,
    reason: str,
) -> MinekinError:
    return MinekinError(
        "cli.auto_session",
        "session start --auto-bundle",
        category,
        Retryability.OPERATOR_ACTION,
        f"{message} [{reason}]",
    )


def host_os_arch(*, system: str | None = None, machine: str | None = None) -> str:
    """The `os_arch` token this host is matched against in the reviewed registry.

    Spelled the way the reviewed entries spell it (`linux-x86_64`) rather than guessed
    at: an architecture with no tested bundle is the resolver's refusal to make, and it
    can only make it if this says what the host actually is.
    """

    return f"{(system or platform.system()).lower()}-{machine or platform.machine()}"


def load_registry(registry_path: Path) -> ReviewedBundleRegistry:
    """Read one reviewed bundle registry document, refusing anything less strict."""

    try:
        document = json.loads(registry_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject(
            f"{registry_path.name} is not readable UTF-8 JSON; the automatic path needs the "
            f"reviewed registry itself, not a placeholder for it",
            ErrorCategory.SUPPLY_CHAIN,
            reason="REGISTRY_UNREADABLE",
        ) from error
    return load_reviewed_registry(document)


@dataclass(frozen=True, slots=True)
class AutoBundleDecision:
    """What this path chose, what it cost, and which recipe the launcher should read."""

    bundle_id: str
    version_text: str
    protocol: int
    recipe: Path
    registry_revision: str
    profile_id: str
    profile_revision: str
    fetch_set: int
    installed: int
    reused: int
    stopped_pids: tuple[int, ...]
    plan: Mapping[str, Any]

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "auto-bundle-decision",
            "status": "ready",
            "bundle_id": self.bundle_id,
            "version_text": self.version_text,
            "protocol": self.protocol,
            "recipe_path": str(self.recipe),
            "registry_revision": self.registry_revision,
            "profile_id": self.profile_id,
            "profile_revision": self.profile_revision,
            "launch_plan_digest": self.plan["plan_sha256"],
            "fetch_set": self.fetch_set,
            "installed": self.installed,
            "reused": self.reused,
            "stopped": list(self.stopped_pids),
        }


def _resolved_entry(decision: ResolutionDecision) -> RegistryEntry:
    """The one tested bundle a resolution settled on, or the refusal it stopped at.

    The category follows where the doubt lives: a target that could not be read, or that
    several endpoints could mean, is an admission problem, while a protocol no reviewed
    entry covers is a supply-chain one. Either way the resolver's own reason tokens are
    what the operator sees, because those are the stable names this path refuses under.
    """

    if decision.status is ResolutionStatus.RESOLVED and decision.bundle is not None:
        return decision.bundle
    category = (
        ErrorCategory.SUPPLY_CHAIN
        if decision.status is ResolutionStatus.UNSUPPORTED
        else ErrorCategory.ADMISSION
    )
    candidates = ", ".join(decision.candidates) if decision.candidates else "none"
    raise _reject(
        f"{decision.status.value}: {decision.detail or 'the resolver named no bundle'}; "
        f"reasons={','.join(reason.value for reason in decision.reasons)} "
        f"candidates={candidates}",
        category,
        reason=decision.reasons[0].value if decision.reasons else decision.status.value,
    )


def require_agreeing_facts(
    *, observation: ProbeObservation, entry: RegistryEntry, recipe: Path
) -> None:
    """Three documents have to name one version before anything is fetched or launched."""

    if observation.version_text is not None and observation.version_text != entry.version_text:
        # A resolution that settled on this entry already checked the display text
        # against the protocol it arrived on, so reaching here means the two readings of
        # the same target disagreed. A target that names no version at all is not a
        # disagreement: the resolver indexes on the protocol, and it is V05's frozen
        # judgement whether that is enough — this path does not tighten it.
        raise _reject(
            f"the target was observed as {observation.version_text!r} but {entry.bundle_id} "
            f"is reviewed for {entry.version_text!r}",
            ErrorCategory.ADMISSION,
            reason="RESOLVED_TEXT_DISAGREES",
        )
    claimed = launched_minecraft_version(recipe)
    if claimed != entry.version_text:
        raise _reject(
            f"the recipe behind {entry.bundle_id} launches {claimed!r}, not the reviewed "
            f"{entry.version_text!r}",
            ErrorCategory.SUPPLY_CHAIN,
            reason="LAUNCHED_VERSION_DISAGREES",
        )


def _provision(
    plan: Mapping[str, Any],
    store: ArtifactStore,
    *,
    max_bytes: int | None,
    on_progress: Callable[[int, int], None] | None,
) -> tuple[int, int]:
    """Install what the plan names and the store lacks, under a declared budget."""

    missing = missing_artifacts(plan, store)
    if missing and max_bytes is None:
        needed = sum(artifact.size for artifact in missing)
        raise _reject(
            f"{len(missing)} of {len(plan_fetch_set(plan))} artifacts are missing and would "
            f"cost {needed} bytes; pass --max-bytes deliberately rather than let a session "
            f"start download them by accident",
            ErrorCategory.SUPPLY_CHAIN,
            reason="BUDGET_UNDECLARED",
        )
    report = provision_bundle(plan, store, max_bytes=max_bytes, on_progress=on_progress)
    if not report.complete:
        first = report.failed[0]
        raise _reject(
            f"the store could not be completed: {first.coordinate} failed with "
            f"{first.category.value}; nothing launches against a partial store",
            ErrorCategory.SUPPLY_CHAIN,
            reason=f"PROVISION_{first.category.value}",
        )
    return len(report.installed), len(report.reused)


def _ask_target(timeout_s: float) -> Callable[[Path], ProbeObservation]:
    """The read-only probe this path performs when the caller supplies no other way to ask."""

    def ask(path: Path) -> ProbeObservation:
        return run_probe(path, timeout_s=timeout_s)

    return ask


def _stopped_clients(
    run_root: Path,
    *,
    liveness: Callable[[int], Liveness],
    read_cmdline: Callable[[int], bytes | None],
    terminate: Callable[[int], None],
    sleep: Callable[[float], None],
    wait_s: float,
) -> tuple[int, ...]:
    """Stop this Kin's recorded clients and prove each one is gone before returning.

    Stopping is what makes this a switch rather than a second player: the new session has
    its own overlay directory, but the old client would still be in the same world. A
    process this run cannot prove is its own is reported and never touched — taking over
    or force-killing a stray client is the operator's call (`PROCESS-RECOVERY-001`), so
    this path declines and the caller exits `PROCESS` with nothing new launched.
    """

    outcome = stop_recorded_clients(
        run_root,
        probe=liveness,
        read_cmdline=read_cmdline,
        terminate=terminate,
    )
    blocked = sorted(set(outcome.unresolved) | set(outcome.left_alone))
    if blocked:
        raise _reject(
            f"a recorded client is running that this run cannot prove is its own: {blocked}; "
            f"the new client was not started",
            ErrorCategory.PROCESS,
            reason="OLD_CLIENT_UNPROVEN",
        )

    waited = 0.0
    while True:
        outstanding = [
            claim
            for claim in session_claims(run_root, probe=liveness, cmdline=read_cmdline)
            if not claim.resolved
        ]
        if not outstanding:
            return outcome.terminated
        if waited >= wait_s:
            pids = ", ".join(str(claim.identity.pid) for claim in outstanding)
            raise _reject(
                f"the recorded client(s) {pids} were still running after {wait_s}s; the new "
                f"client was not started",
                ErrorCategory.PROCESS,
                reason="OLD_CLIENT_ALIVE",
            )
        sleep(_STOP_POLL_S)
        waited += _STOP_POLL_S


def prepare_auto_bundle_start(
    *,
    registry_path: Path,
    server_profile: Path,
    run_root: Path,
    max_bytes: int | None = None,
    workspace_root: Path | None = None,
    os_arch: str | None = None,
    probe_target: Callable[[Path], ProbeObservation] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    liveness: Callable[[int], Liveness] = default_probe,
    read_cmdline: Callable[[int], bytes | None] = default_cmdline,
    terminate: Callable[[int], None] = terminate_process,
    sleep: Callable[[float], None] = time.sleep,
    probe_timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
    stop_wait_s: float = DEFAULT_STOP_WAIT_S,
) -> AutoBundleDecision:
    """Probe the target, resolve it to one reviewed bundle, and get the host ready to launch.

    Order is the safety property. The digest gate runs before a byte is fetched, the
    target is asked a second time before anything is stopped, and the old client is
    confirmed gone only at the end — so a run that refuses has neither replaced the
    client the operator was watching nor filled half a store, and never has more than one
    controlled client alive.
    """

    root = workspace_root or find_workspace_root(Path(__file__).resolve())
    architecture = os_arch or host_os_arch()
    ask = probe_target or _ask_target(probe_timeout_s)

    registry = load_registry(registry_path)
    first = ask(server_profile)
    decision = resolve(registry, first, os_arch=architecture)
    entry = _resolved_entry(decision)
    plan = require_reviewed_plan(entry, workspace_root=root)
    recipe = root / entry.recipe_path
    require_agreeing_facts(observation=first, entry=entry, recipe=recipe)

    installed, reused = _provision(
        plan,
        ArtifactStore(run_root / "artifact-store"),
        max_bytes=max_bytes,
        on_progress=on_progress,
    )

    # Asked again on purpose: the world may have moved while the store was being filled,
    # and launching a bundle chosen from a stale reading is the failure this path exists
    # to prevent rather than one to notice afterwards.
    second = ask(server_profile)
    again = _resolved_entry(resolve(registry, second, os_arch=architecture))
    if again.bundle_id != entry.bundle_id:
        raise _reject(
            f"the target resolved to {again.bundle_id} when it was asked a second time, not "
            f"the {entry.bundle_id} this launch was prepared for; the client was not stopped "
            f"and nothing was launched",
            ErrorCategory.ADMISSION,
            reason="TARGET_MOVED",
        )

    stopped = _stopped_clients(
        run_root,
        liveness=liveness,
        read_cmdline=read_cmdline,
        terminate=terminate,
        sleep=sleep,
        wait_s=stop_wait_s,
    )

    return AutoBundleDecision(
        bundle_id=entry.bundle_id,
        version_text=entry.version_text,
        protocol=entry.protocol,
        recipe=recipe,
        registry_revision=registry.revision,
        profile_id=first.profile_id,
        profile_revision=first.profile_revision,
        fetch_set=len(plan_fetch_set(plan)),
        installed=installed,
        reused=reused,
        stopped_pids=stopped,
        plan=plan,
    )
