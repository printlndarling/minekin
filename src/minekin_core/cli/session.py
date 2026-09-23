"""Starting a managed session from a reviewed profile.

The command refuses far more often than it starts, and that is the point: a run
that begins with a missing artifact or a half-downloaded store produces evidence
nobody can trust, so readiness is checked before anything is created.

This is the composition root for a launch. Every step it uses is built and tested
on its own, so what is left here is the order and the refusal rules.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, cast

from google.protobuf.message import Message

from minekin_core.adapters.bridge.bootstrap import bridge_session_for, descriptor_path
from minekin_core.adapters.bridge.ipc import (
    ADMISSION_CAPABILITY,
    CANCEL_CONNECTION_TYPE,
    CONNECT_WORLD_TYPE,
    LOOK_CAPABILITY,
    LOOK_INPUT_TYPE,
    MOVE_CAPABILITY,
    MOVE_INPUT_TYPE,
    OPEN_LAN_TYPE,
    RELEASE_ALL_INPUTS_TYPE,
    USE_CAPABILITY,
    USE_INPUT_TYPE,
    BridgeIpcHost,
    BridgeSession,
    monotonic_ns,
)
from minekin_core.adapters.launcher.artifacts import ArtifactStore, SessionOverlayStore
from minekin_core.adapters.launcher.assets import materialise_assets
from minekin_core.adapters.launcher.game_options import prepare_game_options
from minekin_core.adapters.launcher.launch_plan import (
    artifacts_from_plan,
    build_launch_plan,
    find_workspace_root,
)
from minekin_core.adapters.launcher.mods import install_fixed_mods
from minekin_core.adapters.launcher.natives import materialise_natives
from minekin_core.adapters.launcher.offline_session import (
    candidate_by_id,
    recorded_material,
)
from minekin_core.adapters.launcher.orphans import (
    Liveness,
    StopOutcome,
    default_cmdline,
    default_probe,
    require_no_unresolved_client,
    stop_recorded_clients,
    terminate_process,
    write_marker,
)
from minekin_core.adapters.launcher.process import ClientProcessSpec, build_process_spec
from minekin_core.adapters.launcher.recipe import require_built_bridge
from minekin_core.adapters.launcher.saves import (
    LEVEL_DAT,
    player_data_path,
    seed_world,
    settings_digest,
)
from minekin_core.adapters.launcher.server_profile import ServerProfile, load_server_profile
from minekin_core.adapters.launcher.supervisor import ProcessIdentity, ProcessSupervisor
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.identity_store import read_identity_root
from minekin_core.adapters.sqlite.session_log import (
    AUTH_POLICY_FROZEN,
    CLIENT_EXITED,
    HELLO_ACCEPTED,
    INPUT_LEASE_GRANTED,
    INPUT_REFUSED,
    INPUT_RELEASED,
    JOIN_OBSERVED,
    PLAYABLE_ESTABLISHED,
    RESOURCE_PACK_POLICY_APPLIED,
    SESSION_INTERRUPTED,
    SESSION_STATE_TRANSITIONED,
    SessionEventLog,
    reconcile_outbox_async,
)
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.application.recovery_service import RecoveryReport
from minekin_core.cli.init import DATABASE_NAME, KIN_DIRECTORY, kin_directory, run_root
from minekin_core.cli.session_runtime import (
    SessionOutcome,
    SessionRun,
    advance_session,
    supervise_session,
)
from minekin_core.domain.auth_policy import AuthPolicy
from minekin_core.domain.connection import ConnectionGenerations, ConnectionState
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.ids import ClientInstanceId, KinId, OpaqueId, RunId
from minekin_core.domain.input_control import (
    InputArbiter,
    InputLease,
    InputPriority,
    InputRefusal,
    InputRequest,
    ReleaseOutcome,
    ReleaseReason,
)
from minekin_core.domain.lease_watchdog import LeaseWatchdog
from minekin_core.domain.recovery import START_CLIENT
from minekin_core.domain.session_material import RecordedSessionMaterial
from minekin_core.domain.session_state import SessionState, SessionStateMachine
from minekin_core.domain.time import Deadline, MonotonicInstant
from minekin_core.generated.minekin.v1 import control_pb2

SupervisorFactory = Callable[[Path], ProcessSupervisor]

#: What reconciliation reports when there was nothing left over. Named rather
#: than built in a default, so the default is a value and not an expression.
NOTHING_TO_RECONCILE = RecoveryReport(invalidated=(), waiting=())

# The connection states that are a fact §5 names, and who concluded each one.
# The three phases before a join are progress towards one, not facts themselves,
# so they are deliberately absent and the recorder ignores them.
#
# The trust class follows the conclusion, not the channel. A join is the Bridge
# reporting what its client did, so it is the Bridge's filtered word. Being
# playable is Core's own conclusion from a snapshot it admitted — §6 says trust
# may not be self-declared, and recording Core's verdict as the Bridge's report
# would name the wrong source for the strongest fact in the session.
_CONNECTION_EVENTS: dict[ConnectionState, tuple[str, EventSource, TrustClass]] = {
    ConnectionState.JOIN_SEEN: (JOIN_OBSERVED, EventSource.BRIDGE, TrustClass.BRIDGE_FILTERED),
    ConnectionState.PLAYABLE: (PLAYABLE_ESTABLISHED, EventSource.CORE, TrustClass.CORE),
    ConnectionState.DISCONNECTED: (
        SESSION_INTERRUPTED,
        EventSource.BRIDGE,
        TrustClass.BRIDGE_FILTERED,
    ),
    ConnectionState.FAILED: (SESSION_INTERRUPTED, EventSource.BRIDGE, TrustClass.BRIDGE_FILTERED),
}

_OUTCOME_EVENTS: dict[SessionOutcome, str] = {
    SessionOutcome.CLIENT_EXITED: CLIENT_EXITED,
    SessionOutcome.BRIDGE_LOST: SESSION_INTERRUPTED,
    SessionOutcome.HANDSHAKE_FAILED: SESSION_INTERRUPTED,
    SessionOutcome.HANDSHAKE_TIMEOUT: SESSION_INTERRUPTED,
}

# One managed session's own directory inside the overlay, created for it by
# SessionOverlayStore. The descriptor carries a session key, so it goes here
# rather than anywhere the operator or the host can point at.
IPC_DIRECTORY = "ipc"

# How long the managed client has to prove its session before Core gives up.
DEFAULT_HANDSHAKE_TIMEOUT_S = 30.0

# How often the supervisor is asked whether the client is still there. Polling
# rather than blocking in a thread: a thread parked on the child would keep the
# event loop's executor alive at shutdown and hang the process.
DEFAULT_EXIT_POLL_S = 0.2

# How long a requested connection may take before Core stops meaning it. The
# value rides inside `ConnectWorld` so the Bridge can refuse a command that is
# already stale when it reads it, and `on_connection_deadline` below sends
# `CancelConnection(TIMEOUT)` when it passes: the same deadline, held by both
# sides, because the side that issued it is the side that knows when it passed.
DEFAULT_CONNECTION_TIMEOUT_S = 30.0

# The wire enum's word for "this attempt ran out of time", without its prefix:
# the run document records stable tokens, and the prefix belongs to the wire.
CONNECTION_CANCEL_TIMEOUT = "TIMEOUT"

# How long the client has to get into the world it was asked to host before Core
# stops asking. The Bridge holds the command until the world exists, so this is a
# bound on how long a client may take to enter a world it was launched into, not on
# how long a bind takes.
DEFAULT_LAN_OPEN_TIMEOUT_S = 60.0

# The profile's word for a resource-pack policy, and the wire enum it means.
# Both spellings are reviewed; nothing else is admitted, because an unrecognised
# policy silently mapped to "deny" would be a policy the operator did not choose.
_RESOURCE_PACK_POLICIES: dict[str, control_pb2.ResourcePackPolicy] = {
    "deny": control_pb2.RESOURCE_PACK_POLICY_DENY,
    "prompt": control_pb2.RESOURCE_PACK_POLICY_PROMPT,
}


def open_lan_command(
    *, request_id: str, generation: int, deadline_monotonic_ns: int, port: int = 0
) -> control_pb2.OpenLan:
    """The one command that asks a proved client to publish the world it hosts.

    `port` is usually zero, which asks the client to choose one and report it. A
    fixture names one instead, because the client that is going to *join* needs a
    server profile with a fixed port and neither client can be configured from the
    other's report.
    There is no field for cheats and none for the game mode, here or on the wire,
    because publishing grants both and the policy is that a command may not raise
    either — the policy is enforced by there being nothing to set.

    The deadline is in this process's monotonic clock, and it means something on the
    other side because the envelope carrying it is stamped from the same clock.
    """

    if not 0 <= port <= 65535:
        raise _reject(f"{port} is not a port: 0 asks the client to choose, 1-65535 names one")
    return control_pb2.OpenLan(
        request_id=request_id,
        generation=generation,
        port=port,
        deadline_monotonic_ns=deadline_monotonic_ns,
    )


def connect_world_command(
    profile: ServerProfile,
    *,
    request_id: str,
    generation: int,
    deadline_monotonic_ns: int,
) -> control_pb2.ConnectWorld:
    """The one command that asks a proved client to join a saved world.

    Everything the client acts on comes from the reviewed profile: the host, the
    port and the resource-pack policy. This is where "which server" stops being a
    decision and becomes a message, so a version of this that took a host from
    its caller would be a version that let a caller pick any target.

    The deadline is in the monotonic clock of this process, and it is meaningful
    on the other side because the envelope carrying it is stamped from the same
    clock: the difference between the two is a duration, which is the only thing
    two processes with different origins can agree on.
    """

    try:
        policy = _RESOURCE_PACK_POLICIES[profile.resource_pack_policy]
    except KeyError as error:
        raise _reject(
            "the server profile names an unreviewed resource pack policy: "
            f"{profile.resource_pack_policy!r}"
        ) from error
    return control_pb2.ConnectWorld(
        request_id=request_id,
        generation=generation,
        server_profile_id=profile.profile_id,
        server_profile_revision=profile.revision,
        original_host=profile.host,
        port=profile.port,
        resource_pack_policy=policy,
        deadline_monotonic_ns=deadline_monotonic_ns,
    )


def _reject(message: str, category: ErrorCategory = ErrorCategory.CONFIG) -> MinekinError:
    return MinekinError("cli.session", "start", category, Retryability.OPERATOR_ACTION, message)


def default_supervisor_factory(log_directory: Path) -> ProcessSupervisor:
    return ProcessSupervisor(clock=SystemClock(), log_directory=log_directory)


@dataclass(frozen=True, slots=True)
class SessionLaunch:
    session_id: str
    generation: int
    kin_id: str
    run_id: str
    overlay: str
    identity: ProcessIdentity
    argv_digest: str
    #: What reconciliation did to the previous run's leftovers, if anything.
    recovery: RecoveryReport = NOTHING_TO_RECONCILE

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": "started",
            "kin_id": self.kin_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "generation": self.generation,
            "overlay": self.overlay,
            "pid": self.identity.pid,
            "started_at": self.identity.started_at,
            "argv_digest": self.argv_digest,
            "recovery": self.recovery.as_dict(),
        }


def select_kin(root: Path, selector: str | None) -> KinId:
    """Which Kin this root belongs to.

    A root holding exactly one Kin needs no selector; anything else is ambiguous
    and must be stated rather than guessed, because starting the wrong Kin is not
    something a later step can undo.
    """

    base = root / KIN_DIRECTORY
    candidates = (
        sorted(path.name for path in base.iterdir() if path.is_dir()) if base.is_dir() else []
    )
    # A directory that cannot be an identifier was not put there by `init`, and
    # `KinId(...)` would raise a bare ValueError that the CLI redacts. Name it
    # here instead, because "the directory is called `my kin`" is the whole
    # diagnosis and it is not derivable from "unexpected internal failure".
    # A directory that cannot be an identifier was not put there by `init`, and
    # `KinId(...)` would raise a bare ValueError that the CLI redacts. Name it
    # here instead, because "the directory is called `my kin`" is the whole
    # diagnosis and it is not derivable from "unexpected internal failure".
    for candidate in candidates:
        try:
            KinId(candidate)
        except ValueError as error:
            raise _reject(
                f"this root holds a directory that is not a usable Kin name: "
                f"{candidate!r} ({error})"
            ) from error
    if selector:
        if selector not in candidates:
            raise _reject(f"this root holds no Kin named {selector!r}")
        return KinId(selector)
    if not candidates:
        raise _reject(f"no Kin exists under {base}; run `minekin init` first")
    if len(candidates) > 1:
        raise _reject(
            f"this root holds more than one Kin ({', '.join(candidates)}); select one explicitly"
        )
    return KinId(candidates[0])


def database_for(root: Path, kin_id: KinId) -> Path:
    return kin_directory(root, kin_id) / DATABASE_NAME


def session_overlay_path(run_root: Path, session_id: str, generation: int) -> Path:
    """Where the overlay for one session generation lives.

    The path is a function of its inputs rather than something to be discovered,
    so the supervisor's log directory can be named before the overlay exists.
    """

    return run_root / "session" / session_id / f"generation-{generation}"


def require_launchable(plan: Mapping[str, Any]) -> None:
    """Refuse before creating anything when the plan already knows it cannot run."""

    if plan.get("launchable") is not True:
        blockers = cast(list[object], plan.get("blockers", []))
        listed = ", ".join(str(item) for item in blockers) or "unspecified"
        raise _reject(
            f"the bundle profile is not launchable yet: {listed}", ErrorCategory.SUPPLY_CHAIN
        )


def require_store_complete(plan: Mapping[str, Any], store: ArtifactStore) -> None:
    """Every artifact the plan names must already be in the store, verified.

    All of them, not only the ones in argv: a missing asset makes the client fail
    in ways that look like a rendering bug rather than a missing download.
    """

    artifacts = artifacts_from_plan(plan)
    missing: list[str] = []
    for artifact in artifacts:
        try:
            store.verify(artifact)
        except MinekinError:
            missing.append(artifact.coordinate)
    if missing:
        raise _reject(
            f"{len(missing)} of {len(artifacts)} artifacts are not in the store yet, "
            f"starting with {missing[0]}; fetch them before starting a session",
            ErrorCategory.SUPPLY_CHAIN,
        )


@dataclass(frozen=True, slots=True)
class PreparedSession:
    """A launch that is ready to spawn: overlay created, spec built, nothing started."""

    kin_id: str
    session_id: str
    generation: int
    run_id: str
    client_instance_id: str
    overlay: Path
    spec: ClientProcessSpec
    supervisor: ProcessSupervisor
    ledger: SessionEventLog
    auth_policy: AuthPolicy
    recovery: RecoveryReport = NOTHING_TO_RECONCILE
    bridge_session: BridgeSession | None = None
    bridge_descriptor: Path | None = None
    #: What this launch actually put in the client's argv, read back from the
    #: resolved arguments rather than re-derived — the first snapshot is checked
    #: against it, so a value encoded in the wrong slot is caught there.
    recorded: RecordedSessionMaterial | None = None
    #: The world this launch placed in the client's game directory, when it
    #: placed one: the level it will enter and the digest of the bytes it was
    #: given. None for every run that is not a host.
    world_snapshot: dict[str, str] | None = None


def start_session(
    *,
    root: Path,
    profile: Path,
    java_executable: Path,
    session_id: str,
    generation: int,
    kin_selector: str | None = None,
    supervisor_factory: SupervisorFactory = default_supervisor_factory,
    forward_environment: Mapping[str, str] | None = None,
    event_log: SessionEventLog | None = None,
    probe: Callable[[int], Liveness] = default_probe,
    cmdline: Callable[[int], bytes | None] = default_cmdline,
    world_save: Path | None = None,
    world_name: str | None = None,
    identity_candidate: str | None = None,
) -> SessionLaunch:
    """Read the identity, prove readiness, then create the overlay and start."""

    return launch_prepared(
        prepare_session(
            root=root,
            profile=profile,
            java_executable=java_executable,
            session_id=session_id,
            generation=generation,
            kin_selector=kin_selector,
            supervisor_factory=supervisor_factory,
            forward_environment=forward_environment,
            event_log=event_log,
            probe=probe,
            cmdline=cmdline,
            world_save=world_save,
            world_name=world_name,
            identity_candidate=identity_candidate,
        )
    )


def prepare_session(
    *,
    root: Path,
    profile: Path,
    java_executable: Path,
    session_id: str,
    generation: int,
    kin_selector: str | None = None,
    supervisor_factory: SupervisorFactory = default_supervisor_factory,
    forward_environment: Mapping[str, str] | None = None,
    event_log: SessionEventLog | None = None,
    probe: Callable[[int], Liveness] = default_probe,
    cmdline: Callable[[int], bytes | None] = default_cmdline,
    host_bridge: bool = False,
    world_save: Path | None = None,
    world_name: str | None = None,
    identity_candidate: str | None = None,
    auth_policy: AuthPolicy | None = None,
) -> PreparedSession:
    """Prepare a launch, for a caller that is not already running a loop."""

    return asyncio.run(
        prepare_session_async(
            root=root,
            profile=profile,
            java_executable=java_executable,
            session_id=session_id,
            generation=generation,
            kin_selector=kin_selector,
            supervisor_factory=supervisor_factory,
            forward_environment=forward_environment,
            event_log=event_log,
            probe=probe,
            cmdline=cmdline,
            host_bridge=host_bridge,
            world_save=world_save,
            world_name=world_name,
            identity_candidate=identity_candidate,
            auth_policy=auth_policy,
        )
    )


async def prepare_session_async(
    *,
    root: Path,
    profile: Path,
    java_executable: Path,
    session_id: str,
    generation: int,
    kin_selector: str | None = None,
    supervisor_factory: SupervisorFactory = default_supervisor_factory,
    forward_environment: Mapping[str, str] | None = None,
    event_log: SessionEventLog | None = None,
    probe: Callable[[int], Liveness] = default_probe,
    cmdline: Callable[[int], bytes | None] = default_cmdline,
    host_bridge: bool = False,
    world_save: Path | None = None,
    world_name: str | None = None,
    identity_candidate: str | None = None,
    auth_policy: AuthPolicy | None = None,
) -> PreparedSession:
    """Everything a launch needs, with the overlay already created and nothing started.

    Split from the spawn so a caller can do work that must happen *between* the
    overlay existing and the client running — hosting the Bridge IPC session is
    exactly that: the descriptor has to be in the overlay before the client
    reads it, and the overlay must not exist before the readiness checks pass.
    """

    kin_id = select_kin(root, kin_selector)
    database = database_for(root, kin_id)
    # `connect_reader` opens with mode=ro, so a missing file surfaces as a
    # driver error the CLI redacts. `session status` already guards this; a
    # start should say the same thing rather than something less useful.
    if not database.is_file():
        raise _reject(f"{database} is missing; run `minekin init` first")
    connection = connect_reader(database)
    try:
        identity = read_identity_root(connection)
    finally:
        connection.close()

    # §13 puts reconciliation before a new run starts: what did not end cleanly
    # is marked, and the effects that cannot survive a restart are closed rather
    # than left for a later start to pick up.
    recovery = await reconcile_outbox_async(database, clock=SystemClock())

    # A world save without a name to give it, or a name with nothing to seed, is
    # an operator error and is refused before anything is created — the same rule
    # the readiness checks follow, because a run that has already built an overlay
    # should not be the thing that discovers one.
    if world_name is not None and world_save is None:
        raise _reject("--world-name names a world to seed; --world-save says which one")
    if world_save is not None and world_name is None:
        raise _reject("--world-save needs --world-name: a world with no name is not enterable")
    # Listed separately rather than folded into the check below, so a path that
    # does not exist is not reported as a directory that is missing a file.
    if world_save is not None and not world_save.is_dir():
        raise _reject(f"{world_save} is not a directory to seed a world from")
    if world_save is not None and not (world_save / LEVEL_DAT).is_file():
        raise _reject(f"{world_save} is not a world: it has no {LEVEL_DAT}")
    # The same predicate `seed_world` applies, asked here so that a world which is
    # not a clean start is refused before an overlay exists rather than after one
    # is built. One rule, two moments.
    if world_save is not None and player_data_path(world_save, identity.material.uuid).is_file():
        raise _reject(
            f"{world_save} already holds this Kin, so it is not a clean world to "
            f"start from; it would load this Kin as that run left them"
        )

    runs = run_root(root, kin_id)
    plan = build_launch_plan(profile, world_name=world_name)
    require_launchable(plan)
    require_store_complete(plan, ArtifactStore(runs / "artifact-store"))
    # The recipe pins the jar the reviewed source builds, so the launch asks the
    # workspace for it rather than trusting whatever a build happened to leave.
    require_built_bridge(find_workspace_root(Path(__file__).resolve()))

    # Before anything is created: a second client on top of a live one shares the
    # overlay and appears to the server as a second player.
    require_no_unresolved_client(runs, probe=probe, cmdline=cmdline)

    overlays = SessionOverlayStore(runs / "session")
    overlay = overlays.create(session_id, generation)
    if overlay != session_overlay_path(runs, session_id, generation):
        # The supervisor's log directory was named from this path already.
        raise _reject("the session overlay was created somewhere unexpected")

    # A fresh game directory is a first run, and vanilla's first run shows the
    # accessibility onboarding screen before anything else — before the title
    # screen, and before any world it was asked to enter. One file is what makes
    # the directory not a first run.
    prepare_game_options(overlay)

    # The overlay is the client's game directory, so the fixed mods go into its
    # mods/ before the client can start looking for them.
    install_fixed_mods(
        plan,
        overlay=overlay,
        store=ArtifactStore(runs / "artifact-store"),
        workspace_root=find_workspace_root(Path(__file__).resolve()),
    )

    # The natives are not on the classpath: the plan names them apart from it and
    # the client is given their directory as `java.library.path`. Nothing else
    # takes them out of their jars, and a client that cannot load LWJGL says so
    # only once it has already started, as a missing `liblwjgl.so`.
    materialise_natives(
        plan,
        run_root=runs,
        overlay=overlay,
        store=ArtifactStore(runs / "artifact-store"),
    )

    # The client reads its assets from `bundle/assets`, and the store keeps them
    # under a layout the client does not speak. This is the view it does speak,
    # and it is per run because the bytes are the same for every generation.
    materialise_assets(
        plan,
        run_root=runs,
        overlay=overlay,
        store=ArtifactStore(runs / "artifact-store"),
    )

    # The world a host session opens has to be in the client's game directory
    # before the client looks, which is now: the overlay exists and nothing has
    # started. It is the same shape as the mods and the assets above, and it is
    # what makes a session able to *host* at all — a client at the title screen is
    # running no integrated server for anything to join.
    world_snapshot: dict[str, str] | None = None
    if world_save is not None and world_name is not None:
        _, digest = seed_world(
            overlay=overlay,
            save=world_save,
            level_name=world_name,
            player=identity.material.uuid,
        )
        world_snapshot = {
            "level_name": world_name,
            "digest": digest,
            # The world's own settings, so a bundle can say what a run started
            # from when there is no server profile to say it.
            "settings_digest": settings_digest(world_save),
        }

    run_id = RunId.new().value
    client_instance_id = ClientInstanceId.new().value
    bridge_session: BridgeSession | None = None
    descriptor: Path | None = None
    if host_bridge:
        bridge_session = bridge_session_for(
            plan,
            kin_id=kin_id,
            session_id=session_id,
            generation=generation,
            client_instance_id=client_instance_id,
        )
        descriptor = descriptor_path(overlay / IPC_DIRECTORY)

    supervisor = supervisor_factory(overlay / "logs")
    # Which reviewed candidate this run is testing. Absent is the first, which is
    # what every run used before the option existed; an id that matches nothing is
    # refused by `candidate_by_id` rather than falling back, because a run that
    # asked for OFF-B and silently got OFF-A would seal a bundle for a scenario
    # that did not happen.
    policy = auth_policy if auth_policy is not None else AuthPolicy()
    policy.require_offline_launch()
    candidate = candidate_by_id(identity_candidate)
    spec = build_process_spec(
        plan,
        run_root=runs,
        overlay=overlay,
        material=identity.material,
        candidate=candidate,
        java_executable=java_executable,
        forward_environment=forward_environment,
        bridge_descriptor=descriptor,
    )
    ledger = event_log if event_log is not None else SessionEventLog(database, clock=SystemClock())
    return PreparedSession(
        kin_id=str(identity.kin_id),
        session_id=session_id,
        generation=generation,
        run_id=run_id,
        client_instance_id=client_instance_id,
        overlay=overlay,
        spec=spec,
        supervisor=supervisor,
        ledger=ledger,
        auth_policy=policy,
        recovery=recovery,
        bridge_session=bridge_session,
        bridge_descriptor=descriptor,
        recorded=recorded_material(candidate, spec.argv),
        world_snapshot=world_snapshot,
    )


def launch_prepared(prepared: PreparedSession) -> SessionLaunch:
    """Spawn the prepared client, for a caller that is not running a loop."""

    return asyncio.run(launch_prepared_async(prepared))


async def launch_prepared_async(prepared: PreparedSession) -> SessionLaunch:
    """Spawn the prepared client and record it.

    The ledger records what the launcher did, after it did it. Refusals before
    this point are operator errors rather than run outcomes, so they leave no
    entry: a run only begins once a process does.
    """

    # The same immutable policy that admitted the offline process specification
    # is committed before that process exists. A failed spawn still has a policy
    # fact, while an earlier preparation refusal has no run to attribute one to.
    await prepared.ledger.record_session_event(
        event_type=AUTH_POLICY_FROZEN,
        kin_id=prepared.kin_id,
        run_id=prepared.run_id,
        session_id=prepared.session_id,
        generation=prepared.generation,
        payload=prepared.auth_policy.as_event_payload(),
        source=EventSource.CORE,
        trust_class=TrustClass.CORE,
    )

    # §8: the intent is committed before the effect is attempted, so a crash in
    # between leaves something on the ledger to reconcile. The key is the run,
    # which is new for every launch, so a repeat of this effect is a new request
    # rather than a duplication of this one.
    intent = await prepared.ledger.open_effect(
        effect_type=START_CLIENT, idempotency_key=prepared.run_id
    )
    try:
        process = prepared.supervisor.start(prepared.spec)
    except MinekinError as error:
        await prepared.ledger.record_process_failed_async(
            kin_id=prepared.kin_id,
            run_id=prepared.run_id,
            session_id=prepared.session_id,
            generation=prepared.generation,
            error=error,
        )
        # The attempt has a result, so the effect is finished: a failed start is
        # not something for the next run to replay.
        await prepared.ledger.settle_effect(intent)
        raise
    write_marker(
        prepared.overlay,
        identity=process,
        session_id=prepared.session_id,
        generation=prepared.generation,
    )
    await prepared.ledger.record_process_started_async(
        kin_id=prepared.kin_id,
        run_id=prepared.run_id,
        session_id=prepared.session_id,
        generation=prepared.generation,
        client_instance_id=prepared.client_instance_id,
        argv_digest=process.argv_digest,
    )
    await prepared.ledger.settle_effect(intent)
    return SessionLaunch(
        session_id=prepared.session_id,
        generation=prepared.generation,
        kin_id=prepared.kin_id,
        run_id=prepared.run_id,
        overlay=str(prepared.overlay),
        identity=process,
        argv_digest=process.argv_digest,
        recovery=prepared.recovery,
    )


# The most a single look command may ask for. The Bridge bounds a turn at the
# same number; this is the earlier refusal, before a client is started for it.
MAX_LOOK_DEGREES = 360.0

# How long a look's authorisation lasts. A look is one instant's work, so its
# lease is only long enough to carry the command and be withdrawn.
DEFAULT_LOOK_LEASE_S = 5.0

# When a run asks for its hold. `playable` is the only moment that can succeed:
# the lease means "the client may be driven", and the first snapshot is what makes
# that true. `join` exists because a run has to be able to ask *too early* and have
# the answer recorded — the contract's invariant is "no lease before the join and
# the first snapshot", and an invariant nothing is ever allowed to test is a
# comment. A run that asks at the join is refused, and that refusal is the
# evidence.
HOLD_AT_PLAYABLE = "playable"
HOLD_AT_JOIN = "join"
HOLD_PHASES = (HOLD_AT_PLAYABLE, HOLD_AT_JOIN)


@dataclass
class InputPlan:
    """What this run asks the client to do, the lease that authorises it, and its clock.

    Both kinds of input arrive here because they share everything except what they
    send: one lease, one arbiter, one release. A hold is a duration and a look is
    a delta, and the duration is the caller's because it is what the lease was
    granted for — the authorisation carries the moment it lapses, and that moment
    is the only thing that ends a hold. Until that existed the deadline was
    written into the lease and read by nobody, so a short move lasted exactly as
    long as the run did.
    """

    hold_seconds: float | None = None
    #: How long the use key is held, when this run asks for it. Its own duration
    #: rather than a boolean for the same reason a movement hold has one: what
    #: ends it is the lease lapsing, and a hold with no length would be a key held
    #: until something else went wrong.
    use_seconds: float | None = None
    strafe: float = 0.0
    jump: bool = False
    sneak: bool = False
    yaw_degrees: float = 0.0
    pitch_degrees: float = 0.0
    look: bool = False
    arbiter: InputArbiter | None = None
    lease: InputLease | None = None
    watchdog: LeaseWatchdog = field(default_factory=LeaseWatchdog)
    playable: asyncio.Event = field(default_factory=asyncio.Event)
    deadline_monotonic_ns: int = 0
    action_id: str = ""
    # The arbiter's own words for why no lease was granted, when it refused.
    # Kept rather than dropped: a run that was asked to walk and did not is a
    # fact about the run, and the reason is the only part of it worth having.
    refusal: str = ""

    @property
    def capabilities(self) -> frozenset[str]:
        """What this plan needs authorising for, and nothing it does not.

        A look is its own capability because a client can be steerable without
        being turnable; a plan that asks for both holds one lease covering both.
        """

        wanted: set[str] = set()
        if self.hold_seconds is not None:
            wanted.add(MOVE_CAPABILITY)
        if self.look:
            wanted.add(LOOK_CAPABILITY)
        if self.use_seconds is not None:
            wanted.add(USE_CAPABILITY)
        return frozenset(wanted)

    @property
    def lease_seconds(self) -> float:
        """How long the authorisation lasts. A hold owns its duration; a look does not.

        One lease covers everything this run asks for, so it has to last as long
        as the longest of them: a lease that covered the movement and lapsed
        before the use did would take a key back that was still wanted, and the
        release is one instruction for all of them either way.
        """

        holds = [value for value in (self.hold_seconds, self.use_seconds) if value is not None]
        return max(holds) if holds else DEFAULT_LOOK_LEASE_S

    def commands(self, lease: InputLease, deadline_ns: int) -> list[tuple[str, str, Message]]:
        """The commands this plan sends, in a stable order, and what authorises each."""

        outstanding: list[tuple[str, str, Message]] = []
        if self.hold_seconds is not None:
            outstanding.append(
                (
                    MOVE_CAPABILITY,
                    MOVE_INPUT_TYPE,
                    control_pb2.MoveInput(
                        action_id=self.action_id,
                        lease_id=lease.lease_id,
                        generation=int(lease.generation),
                        forward=1.0,
                        strafe=self.strafe,
                        jump=self.jump,
                        sneak=self.sneak,
                        deadline_monotonic_ns=deadline_ns,
                    ),
                )
            )
        if self.use_seconds is not None:
            outstanding.append(
                (
                    USE_CAPABILITY,
                    USE_INPUT_TYPE,
                    control_pb2.UseInput(
                        action_id=self.action_id,
                        lease_id=lease.lease_id,
                        generation=int(lease.generation),
                        use=True,
                        deadline_monotonic_ns=deadline_ns,
                    ),
                )
            )
        if self.look:
            outstanding.append(
                (
                    LOOK_CAPABILITY,
                    LOOK_INPUT_TYPE,
                    control_pb2.LookInput(
                        action_id=self.action_id,
                        lease_id=lease.lease_id,
                        generation=int(lease.generation),
                        delta_yaw_degrees=self.yaw_degrees,
                        delta_pitch_degrees=self.pitch_degrees,
                        deadline_monotonic_ns=deadline_ns,
                    ),
                )
            )
        return outstanding


async def start_and_supervise(
    *,
    root: Path,
    profile: Path,
    java_executable: Path,
    session_id: str,
    generation: int,
    kin_selector: str | None = None,
    supervisor_factory: SupervisorFactory = default_supervisor_factory,
    forward_environment: Mapping[str, str] | None = None,
    event_log: SessionEventLog | None = None,
    probe: Callable[[int], Liveness] = default_probe,
    cmdline: Callable[[int], bytes | None] = default_cmdline,
    handshake_timeout: float = DEFAULT_HANDSHAKE_TIMEOUT_S,
    exit_poll_s: float = DEFAULT_EXIT_POLL_S,
    server_profile: Path | None = None,
    connection_timeout: float = DEFAULT_CONNECTION_TIMEOUT_S,
    hold_forward: float | None = None,
    hold_use: float | None = None,
    hold_strafe: float | None = None,
    hold_jump: bool = False,
    hold_sneak: bool = False,
    hold_at: str = HOLD_AT_PLAYABLE,
    look_yaw_degrees: float | None = None,
    look_pitch_degrees: float | None = None,
    world_save: Path | None = None,
    world_name: str | None = None,
    identity_candidate: str | None = None,
    open_lan: bool = False,
    open_lan_timeout: float = DEFAULT_LAN_OPEN_TIMEOUT_S,
    open_lan_port: int = 0,
) -> tuple[SessionLaunch, SessionRun]:
    """Start a managed session with a live Bridge and stay with it until it ends.

    Everything here runs in one event loop on purpose. The host's listening
    sockets belong to the loop that created them, so preparing it in one
    `asyncio.run` and supervising in another would leave the transport behind on
    a loop that has already closed.

    `server_profile` is optional. Without it the client comes up, proves itself
    and is left at the menu, which is what every run before this one did. With
    it, the client is asked to join the saved world as soon as it is at the menu
    — and the request is made by *this* process, because the session is only
    reachable while this process is hosting it.
    """

    target: ServerProfile | None = None
    if server_profile is not None:
        if connection_timeout <= 0:
            raise _reject("the connection timeout must be positive")
        # Read before anything is created: an unusable profile is an operator
        # error, and a run that has already built an overlay should not be the
        # thing that discovers one.
        target = load_server_profile(server_profile)

    session = SessionStateMachine()
    prepared = await prepare_session_async(
        root=root,
        profile=profile,
        java_executable=java_executable,
        session_id=session_id,
        generation=generation,
        kin_selector=kin_selector,
        supervisor_factory=supervisor_factory,
        forward_environment=forward_environment,
        event_log=event_log,
        probe=probe,
        cmdline=cmdline,
        host_bridge=True,
        world_save=world_save,
        world_name=world_name,
        identity_candidate=identity_candidate,
        auth_policy=(
            AuthPolicy.from_profile(profile_id=target.profile_id, revision=target.revision)
            if target is not None
            else AuthPolicy()
        ),
    )
    if prepared.bridge_session is None or prepared.bridge_descriptor is None:
        raise _reject("the session was prepared without a Bridge session to host")

    async def record_transition(source: SessionState, target: SessionState) -> None:
        await prepared.ledger.record_session_event(
            event_type=SESSION_STATE_TRANSITIONED,
            kin_id=prepared.kin_id,
            run_id=prepared.run_id,
            session_id=prepared.session_id,
            generation=prepared.generation,
            payload={"from": source.value, "to": target.value},
            source=EventSource.CORE,
            trust_class=TrustClass.CORE,
        )

    # Preparation must succeed before a durable session identity exists. Record
    # the beginning of the managed lifecycle immediately after the ledger is
    # available, then persist every later move at its validated transition seam.
    await advance_session(session, SessionState.PREPARING, record_transition)
    # Bound to a local for the closures below: the guard above has established it,
    # and a closure reading the attribute again is a read a checker cannot narrow.
    bridge_session = prepared.bridge_session
    if target is not None and ADMISSION_CAPABILITY not in prepared.bridge_session.capabilities:
        # Refused before the client starts, because a session that cannot be
        # asked to connect is not the session the operator asked for.
        raise _reject(
            "this Bridge session was negotiated without "
            f"{ADMISSION_CAPABILITY}, so no connection can be requested"
        )
    wants_look = look_yaw_degrees is not None or look_pitch_degrees is not None
    # The axes and the keys are modifiers of the hold: a duration is what makes a
    # hold exist, and asking to hold an axis without one is a run that means
    # nothing rather than a run with a default duration nobody chose.
    axis_asked = hold_strafe is not None or hold_jump or hold_sneak
    if axis_asked and hold_forward is None:
        raise _reject("holding an axis needs --hold-forward-seconds: it is the hold's length")
    plan = (
        None
        if hold_forward is None and not wants_look and hold_use is None
        else InputPlan(
            hold_seconds=hold_forward,
            use_seconds=hold_use,
            strafe=0.0 if hold_strafe is None else hold_strafe,
            jump=hold_jump,
            sneak=hold_sneak,
            look=wants_look,
            yaw_degrees=0.0 if look_yaw_degrees is None else look_yaw_degrees,
            pitch_degrees=0.0 if look_pitch_degrees is None else look_pitch_degrees,
        )
    )
    if plan is not None and server_profile is None:
        # Input with no world to drive would be a lever that does nothing: the
        # operator asked for something this run cannot express.
        raise _reject("asking for input needs --server-profile: there is no world to drive")
    if hold_use is not None and hold_use <= 0:
        raise _reject("--hold-use-seconds must be positive")
    if hold_at not in HOLD_PHASES:
        raise _reject(f"--hold-at must be one of {', '.join(HOLD_PHASES)}")
    if plan is None and hold_at != HOLD_AT_PLAYABLE:
        # A phase with no request behind it: the operator asked *when* to ask
        # without asking for anything.
        raise _reject("--hold-at needs a hold to be asked for")
    if hold_forward is not None and hold_forward <= 0:
        # A lease deadline already past is not a hold, it is a refusal dressed as
        # one, and the run would report a Kin that never moved.
        raise _reject("--hold-forward-seconds must be positive")
    if hold_strafe is not None and not -1.0 <= hold_strafe <= 1.0:
        # The Bridge refuses an out-of-range axis rather than clamping it; an
        # operator who typed one should hear about it before a client starts.
        raise _reject("--hold-strafe is bounded to -1..1")
    for degrees, flag in (
        (look_yaw_degrees, "--look-yaw-degrees"),
        (look_pitch_degrees, "--look-pitch-degrees"),
    ):
        # Refused here rather than in the Bridge: the Bridge bounds a turn at a
        # full turn either way, and an operator who asked for more should be told
        # before a client is started for it.
        if degrees is not None and not -MAX_LOOK_DEGREES <= degrees <= MAX_LOOK_DEGREES:
            raise _reject(f"{flag} is bounded to {MAX_LOOK_DEGREES} degrees either way")
    if plan is not None:
        missing = sorted(plan.capabilities - prepared.bridge_session.capabilities)
        if missing:
            raise _reject(
                "this Bridge session was negotiated without "
                + ", ".join(missing)
                + ", so the client cannot be driven"
            )

    await advance_session(session, SessionState.STARTING_CLIENT, record_transition)
    host = BridgeIpcHost(prepared.bridge_session)
    # Written before the spawn: the client reads it during its own startup, and
    # a client that finds no descriptor refuses to come up at all.
    await host.prepare(prepared.bridge_descriptor)

    launch = await launch_prepared_async(prepared)
    await advance_session(session, SessionState.WAITING_BRIDGE, record_transition)
    await advance_session(session, SessionState.HANDSHAKING, record_transition)

    async def record(
        event_type: str,
        payload: dict[str, Any],
        *,
        source: EventSource,
        trust_class: TrustClass,
    ) -> None:
        await prepared.ledger.record_session_event(
            event_type=event_type,
            kin_id=prepared.kin_id,
            run_id=prepared.run_id,
            session_id=prepared.session_id,
            generation=prepared.generation,
            payload=payload,
            source=source,
            trust_class=trust_class,
        )

    async def on_handshake() -> None:
        # Core verified the proof, so this is Core's conclusion rather than the
        # Bridge's word.
        await record(HELLO_ACCEPTED, {}, source=EventSource.CORE, trust_class=TrustClass.CORE)

    async def on_ready() -> None:
        """Ask the proved client to join the saved world, if one was named.

        The generation is opened here rather than at the handshake, because a
        generation is an *attempt*: nothing has been attempted until a command
        is on its way out. Opened here, it is also the generation the Bridge's
        reports will be gated against, which is what turns them from `UNBOUND`
        into applied facts.
        """

        if open_lan:
            # Asked at the menu, before a single report has arrived, and held by the
            # Bridge until the client is in its world: the two do not arrive in a
            # fixed order, and the command carries the deadline for the difference.
            # The session's own generation, because hosting is not an attempt at a
            # connection — a host has nothing to attempt.
            await host.send_control(
                OPEN_LAN_TYPE,
                open_lan_command(
                    request_id=OpaqueId.new().value,
                    generation=generation,
                    port=open_lan_port,
                    deadline_monotonic_ns=Deadline.after(
                        MonotonicInstant(monotonic_ns()),
                        int(open_lan_timeout * 1_000_000_000),
                    ).monotonic_ns,
                ),
            )

        if target is None:
            return
        attempt = connections.begin(OpaqueId(target.profile_id), target.revision)
        if plan is not None:
            # Bound to the generation the command goes out under, because that is
            # the generation the Bridge gates the plan against.
            plan.arbiter = InputArbiter(attempt.generation)
        # Kept here rather than recomputed later: the deadline that rides inside
        # the command is the same deadline Core holds itself to, and two
        # computations of it would be two deadlines.
        attempt_deadline[0] = Deadline.after(
            MonotonicInstant(monotonic_ns()),
            int(connection_timeout * 1_000_000_000),
        ).monotonic_ns
        command = connect_world_command(
            target,
            request_id=OpaqueId.new().value,
            generation=attempt.generation.value,
            deadline_monotonic_ns=attempt_deadline[0],
        )
        await host.send_control(CONNECT_WORLD_TYPE, command)

    async def until_connection_deadline() -> None:
        """Wait out the attempt's own deadline, if an attempt was made at all."""

        if attempt_deadline[0] is None:
            # No attempt, no deadline: this waits for something that will never
            # come, which is a promise rather than a poll, and it is cancelled
            # with the rest when the run ends.
            await asyncio.Event().wait()
            return
        remaining = attempt_deadline[0] - monotonic_ns()
        if remaining > 0:
            await asyncio.sleep(remaining / 1_000_000_000)

    async def on_connection_deadline() -> None:
        """Core stops meaning the attempt, and says so on the wire.

        The deadline rides inside `ConnectWorld` so the Bridge can refuse a
        command that is already stale by the time it reads one. This is the other
        half of the same deadline, and until now nothing did it: Core sent a
        deadline and then waited forever for a client that might be sitting in a
        black hole.

        The generation is closed *after* the cancel goes out, so the Bridge's
        answer — a `CANCELLED` phase, or nothing at all — cannot move a session
        that has already stopped meaning the attempt. Closing it is the same act
        the wind-down performs, for the same reason.
        """

        active = connections.active
        if active is None or not active.in_flight:
            # An attempt that already ended needs no cancelling, and one that
            # never started leaves nothing to cancel.
            return
        if active.reached_world:
            # An attempt that got as far as a world has nothing left for a
            # deadline to bound: what it was waiting for happened. Cancelling here
            # would close a connection the Kin is using. Measured, and it is why
            # this is here rather than in the deadline's arithmetic: the default
            # thirty seconds expires while a Kin is walking, and the cancel that
            # followed did two things — it closed a healthy connection, and
            # because a cancel clears the generation the Bridge needs to attribute
            # a later report, it also made the world's own death unreportable.
            return
        await host.send_control(
            CANCEL_CONNECTION_TYPE,
            control_pb2.CancelConnection(
                request_id=OpaqueId.new().value,
                generation=int(active.generation),
                reason=control_pb2.CONNECTION_CANCEL_REASON_TIMEOUT,
            ),
        )
        connections.close(active.generation)
        # Kept for the run document, which is replaced into after the supervisor
        # returns: the value belongs to the run, and only this caller knows it —
        # the same shape `input_refusal` has, for the same reason.
        cancelled[0] = CONNECTION_CANCEL_TIMEOUT

    async def record_refusal(phase: str, refusals: tuple[InputRefusal, ...]) -> None:
        """The arbiter said no, and this is the run's record of having asked.

        A ledger event rather than only the run document's `input_refusal`: a run
        can ask at two moments, and a single field would keep whichever answer
        came last. The reasons are the arbiter's own tokens — a refusal whose
        category is dropped is a refusal nobody can act on.
        """

        reasons = [item.value for item in refusals]
        if plan is not None:
            plan.refusal = ",".join(reasons)
        await record(
            INPUT_REFUSED,
            {
                "phase": phase,
                "capabilities": sorted(() if plan is None else plan.capabilities),
                "refusals": reasons,
            },
            source=EventSource.CORE,
            trust_class=TrustClass.CORE,
        )

    async def present_the_plan(phase: str) -> None:
        """Ask the arbiter for this run's input, at one phase, and record its answer.

        Two callers and one body, because what a run asks for is the same at both
        moments and only *when* it asks differs: at the join — which is too early,
        and is how "no lease before the join and the first snapshot" is tested
        rather than assumed — and once the snapshot has been admitted, which is the
        only moment that can succeed.
        """

        if plan is None or plan.arbiter is None:
            return
        issued = monotonic_ns()
        deadline = issued + int(plan.lease_seconds * 1_000_000_000)
        lease = InputLease(
            lease_id=OpaqueId.new().value,
            generation=plan.arbiter.generation,
            client_instance_id=bridge_session.client_instance_id,
            issued_monotonic_ns=issued,
            deadline_monotonic_ns=deadline,
            priority=InputPriority.NORMAL,
            # What this plan needs, and nothing else: a look-only run holds a lease
            # that cannot move the client, and a movement authorisation is not a
            # blanket permission to drive it.
            capabilities=plan.capabilities,
        )
        granted = plan.arbiter.grant(lease)
        if not granted.accepted:
            await record_refusal(phase, granted.refusals)
            return
        plan.action_id = OpaqueId.new().value
        for capability, message_type, message in plan.commands(lease, deadline):
            # Authorised one capability at a time, at this instant: the arbiter
            # answers for an action, so a plan that asks for two things is two
            # answers, and the one that is refused is the one not sent.
            authorised = plan.arbiter.decide(
                InputRequest(
                    lease_id=lease.lease_id,
                    generation=lease.generation,
                    capability=capability,
                    deadline_monotonic_ns=deadline,
                ),
                now=MonotonicInstant(issued),
            )
            if not authorised.accepted:
                await record_refusal(phase, authorised.refusals)
                return
            try:
                await host.send_control(message_type, message)
            except (OSError, RuntimeError):
                # The transport went while the session was being made playable. The
                # run is over by another road, and a ledger entry here would record
                # a grant that never reached the client.
                plan.refusal = "CONTROL_CHANNEL_LOST"
                return
            await record(
                INPUT_LEASE_GRANTED,
                {
                    "capability": capability,
                    "lease_id": lease.lease_id,
                    "action_id": plan.action_id,
                    "deadline_monotonic_ns": deadline,
                    "priority": InputPriority.NORMAL.name,
                },
                source=EventSource.CORE,
                trust_class=TrustClass.CORE,
            )
        plan.lease = lease
        # Armed only now, on a lease that was granted and sent: a watchdog armed
        # before that would lapse an authorisation the client never received.
        plan.deadline_monotonic_ns = deadline
        plan.watchdog.arm(lease)
        plan.playable.set()

    async def on_playable() -> None:
        """Ask for this run's input, under one lease, once the session may be driven."""

        if plan is None or plan.arbiter is None:
            return
        # The arbiter refuses to authorise anything for a session that is not
        # playable, and this is the moment that becomes true. Nothing says it on
        # the arbiter's behalf: it is a decision this run makes, and Core is the
        # only side that knows the snapshot was admitted.
        plan.arbiter.set_playable(True)
        if hold_at != HOLD_AT_PLAYABLE:
            # This run named the phase it asks at, and it has already asked. Asking
            # again here would turn one refusal into a refusal followed by a grant,
            # which is a different run from the one the operator asked for.
            return
        await present_the_plan(ConnectionState.PLAYABLE.value)

    async def release_inputs(arbiter: InputArbiter, reason: ReleaseReason) -> ReleaseOutcome:
        """Withdraw the lease and tell the Bridge, in that order, for one reason.

        One path for both endings — the term running out and the run winding down —
        because release every key is one instruction, and a second copy of it is a
        second place for it to drift.
        """

        outcome = arbiter.withdraw(reason)
        await host.send_control(
            RELEASE_ALL_INPUTS_TYPE,
            control_pb2.ReleaseAllInputs(
                action_id=OpaqueId.new().value,
                generation=int(outcome.generation),
                reason_code=reason.value,
            ),
        )
        # Recorded here rather than by the callers: the first version wrote it in
        # the wind-down only, so the release that the lease deadline sent — the
        # one the whole feature is about — reached the Bridge and left no trace in
        # the ledger. The comment above says a second copy is a second place to
        # drift, and this was the drift.
        await record(
            INPUT_RELEASED,
            outcome.as_document(),
            source=EventSource.CORE,
            trust_class=TrustClass.CORE,
        )
        return outcome

    async def until_input_release() -> None:
        """Wait out the lease: the moment the session was playable, plus its term.

        Its own clock rather than the runtime's, because the duration is what the
        lease was granted for and the runtime has no inputs for it. Waiting for
        playable first matters: the deadline is measured from the grant, and the
        grant happens whenever the snapshot happens to be admitted.
        """

        if plan is None:
            return
        await plan.playable.wait()
        remaining = plan.deadline_monotonic_ns - monotonic_ns()
        if remaining > 0:
            await asyncio.sleep(remaining / 1_000_000_000)

    async def on_input_release() -> None:
        """The term is over: stop being allowed to drive the client.

        Asked of the watchdog rather than assumed, so a lapse belonging to a lease
        that has since been replaced cannot release the one that replaced it.
        """

        if plan is None or plan.arbiter is None:
            return
        lapsed = plan.watchdog.lapsed(MonotonicInstant(monotonic_ns()))
        current = plan.arbiter.current
        if lapsed is None or current is None or lapsed.lease_id != current.lease_id:
            return
        await release_inputs(plan.arbiter, ReleaseReason.TIMEOUT)

    async def on_wind_down() -> None:
        """Take the input back, whatever ended the run.

        Unconditional for the reason the arbiter documents: a Bridge that holds
        nothing is not evidence that the client is holding nothing, so the release
        goes out even when Core believes it granted no lease. The reason code is
        Core's own withdrawal — a session ending is not a fault in the input.
        """

        if plan is None or plan.arbiter is None:
            return
        plan.watchdog.disarm()
        await release_inputs(plan.arbiter, ReleaseReason.EXPLICIT)

    async def on_connection(state: ConnectionState, reason: str) -> None:
        recorded = _CONNECTION_EVENTS.get(state)
        if recorded is None:
            # A phase that only moves the session closer to a join is not a fact
            # §5 names, and inventing one would put noise in the ledger.
            return
        event_type, source, trust_class = recorded
        payload: dict[str, Any] = {"phase": state.value}
        if reason:
            # The Bridge's stable classification of why the attempt stopped —
            # never the server's words, which have no channel into a product
            # event. A failure with no category is one nobody can act on.
            payload["reason"] = reason
        await record(event_type, payload, source=source, trust_class=trust_class)
        if state is ConnectionState.JOIN_SEEN and hold_at == HOLD_AT_JOIN:
            # Asked *after* the join is recorded, so the ledger reads in the order
            # the run lived it: the world the Kin joined, and then the answer to a
            # request for input made before there was anything to drive.
            await present_the_plan(state.value)

    async def on_resource_pack_policy(generation: int, policy: str) -> None:
        await record(
            RESOURCE_PACK_POLICY_APPLIED,
            {"generation": generation, "resource_pack_policy": policy},
            # The Bridge read this off the record its own client connected with, so
            # it is the Bridge's filtered word and not Core's inference from the
            # command Core sent: the whole point of the row is that a build which
            # applied something else would have to report that something else.
            source=EventSource.BRIDGE,
            trust_class=TrustClass.BRIDGE_FILTERED,
        )

    async def until_client_exit() -> None:
        while prepared.supervisor.running():
            await asyncio.sleep(exit_poll_s)

    # One instance, shared with the runtime: the generation a report is gated
    # against is the generation the command was sent under, and there is only
    # one place that knows both.
    connections = ConnectionGenerations()
    # Two cells rather than locals because the hooks below close over them: the
    # deadline of the attempt that was actually started, and the reason Core
    # abandoned one — both are facts only this caller holds.
    attempt_deadline: list[int | None] = [None]
    cancelled: list[str] = [""]

    run = await supervise_session(
        host=host,
        session=session,
        connections=connections,
        handshake_timeout=handshake_timeout,
        until_client_exit=until_client_exit,
        on_handshake=on_handshake,
        on_ready=on_ready,
        on_connection=on_connection,
        on_transition=record_transition,
        on_playable=on_playable,
        on_resource_pack_policy=on_resource_pack_policy,
        on_wind_down=on_wind_down,
        # Only when a hold was asked for: with no lease there is no moment, and a
        # watcher that never completes is a task that exists to be cancelled.
        until_input_release=None if plan is None else until_input_release,
        on_input_release=None if plan is None else on_input_release,
        # Only when a world was named: with no attempt there is no deadline, and
        # a watcher that never completes is a task that exists to be cancelled.
        until_connection_deadline=None if target is None else until_connection_deadline,
        on_connection_deadline=None if target is None else on_connection_deadline,
        recorded=prepared.recorded,
    )
    if cancelled[0]:
        # The same shape `input_refusal` has: only this caller knows Core gave up
        # on the attempt, and the run document is where a fact with no ledger
        # event of its own lives.
        run = replace(run, connection_cancelled=cancelled[0])
    if prepared.world_snapshot is not None:
        # This caller is the only one that knows a world was placed in the
        # client's game directory, and the run document is where a fact with no
        # ledger event of its own lives.
        run = replace(run, world_snapshot=prepared.world_snapshot)
    if plan is not None and plan.refusal:
        # Only this caller knows why the input was never taken: the runtime sees
        # commands and answers, not the arbiter's reasons. Recorded on the run
        # rather than left in a hook, so "the Kin was told to walk and could not"
        # survives even when there was nothing to release.
        run = replace(run, input_refusal=plan.refusal)
    # How the run ended is Core's own observation, whatever the Bridge reported
    # along the way.
    await record(
        _OUTCOME_EVENTS[run.outcome],
        {"outcome": run.outcome.value},
        source=EventSource.CORE,
        trust_class=TrustClass.CORE,
    )
    return launch, run


@dataclass(frozen=True, slots=True)
class StopReport:
    kin_id: str
    outcome: StopOutcome

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "session stop",
            "status": "stopped" if self.outcome.complete else "blocked",
            "kin_id": self.kin_id,
            **self.outcome.as_document(),
        }


def stop_session(
    root: Path,
    *,
    kin_selector: str | None = None,
    probe: Callable[[int], Liveness] = default_probe,
    read_cmdline: Callable[[int], bytes | None] = default_cmdline,
    terminate: Callable[[int], None] = terminate_process,
) -> StopReport:
    """Stop the clients this Kin recorded, as far as they can be identified.

    Stopping is idempotent: a Kin with nothing running is already stopped. What is
    not idempotent is touching a process that cannot be shown to be ours, so that
    is reported rather than done.
    """

    kin_id = select_kin(root, kin_selector)
    outcome = stop_recorded_clients(
        run_root(root, kin_id),
        probe=probe,
        read_cmdline=read_cmdline,
        terminate=terminate,
    )
    return StopReport(kin_id=str(kin_id), outcome=outcome)
