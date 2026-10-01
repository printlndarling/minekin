"""Starting a managed session from a reviewed profile.

The command refuses far more often than it starts, and that is the point: a run
that begins with a missing artifact or a half-downloaded store produces evidence
nobody can trust, so readiness is checked before anything is created.

This is the composition root for a launch. Every step it uses is built and tested
on its own, so what is left here is the order and the refusal rules.
"""

from __future__ import annotations

import asyncio
import json
import time
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
    session_claims,
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
from minekin_core.adapters.launcher.server_profile import (
    SessionServerProfile,
    load_session_server_profile,
)
from minekin_core.adapters.launcher.stop_request import (
    StopRelease,
    StopRequest,
    read_receipt,
    read_request,
    write_receipt,
    write_request,
)
from minekin_core.adapters.launcher.supervisor import ProcessIdentity, ProcessSupervisor
from minekin_core.adapters.model import model_provider_for
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.identity_store import read_identity_root
from minekin_core.adapters.sqlite.session_log import (
    AUTH_POLICY_FROZEN,
    AUTONOMOUS_RUN_HALTED,
    CLIENT_EXITED,
    HELLO_ACCEPTED,
    INPUT_LEASE_GRANTED,
    INPUT_REFUSED,
    INPUT_RELEASED,
    JOIN_OBSERVED,
    PLAYABLE_ESTABLISHED,
    RESOURCE_PACK_POLICY_APPLIED,
    SESSION_IDENTITY_COMPARED,
    SESSION_INTERRUPTED,
    SESSION_STATE_TRANSITIONED,
    SKILL_STEP_RECORDED,
    SessionEventLog,
    reconcile_outbox_async,
)
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.application.autonomous_play import (
    DEFAULT_STEP_BUDGET,
    AutonomousAsk,
    AutonomousRun,
    AutonomousStep,
    run_autonomous_loop,
)
from minekin_core.application.player_mind import PlayerMind, mind_for
from minekin_core.application.recovery_service import RecoveryReport
from minekin_core.application.skill_plan import (
    SkillPlan,
    SkillSequence,
    SkillStep,
    run_skill_plan,
    sequence_lease_seconds,
)
from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.application.world_skills import (
    DEFAULT_STEP_TIMEOUT_NS,
    ActionAuthority,
    WorldSkills,
)
from minekin_core.cli.init import DATABASE_NAME, KIN_DIRECTORY, kin_directory, run_root
from minekin_core.cli.session_runtime import (
    SessionOutcome,
    SessionRun,
    advance_session,
    supervise_session,
)
from minekin_core.config import configured_persona_seed
from minekin_core.domain.auth_policy import AuthPolicy
from minekin_core.domain.connection import ConnectionGenerations, ConnectionState
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.goal_spec import milestone_from_environment
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
from minekin_core.domain.model_access import cost_ledger_for, model_config
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
    # A stop we honored: the client left because we let go and the stopper terminated
    # it, which is the §5 event for a run ending with its client — not an interruption.
    # §5 names no event for "stopped on request", so this reuses the true one rather
    # than inventing a ledger fact the contract does not carry.
    SessionOutcome.STOPPED_ON_REQUEST: CLIENT_EXITED,
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

# How long `session stop` waits, per live client, for that client's own session to
# confirm it took the keys back before the command terminates the process. Bounded
# because the answer comes from another process that may be gone already, and a
# stop that can never be answered must still stop — it just has to say so.
DEFAULT_STOP_RELEASE_TIMEOUT_S = 5.0

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
    profile: SessionServerProfile,
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
    # The version is part of the ask: each reviewed version's Bridge is a
    # different root's build, and its own pin is the only one that fits it.
    require_built_bridge(
        find_workspace_root(Path(__file__).resolve()),
        str(plan["bundle"]["minecraft"]),
    )

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

# How long one skill step may wait, by default, for the reading that confirms it.
# Taken from the skill layer's own constant rather than restated: the Bridge
# publishes readings on a fixed tick cadence, so the sensible window is a property
# of that cadence and one number for both places is the only version that cannot
# drift.
DEFAULT_SKILL_STEP_TIMEOUT_S = DEFAULT_STEP_TIMEOUT_NS / 1_000_000_000

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
    #: The skills this run asks after the hold, if it asks any. Carried here
    #: rather than kept beside the plan because the lease is one object covering
    #: everything the run asks for: a plan that walks and then crafts needs a
    #: lease that authorises both, and the list of what a lease covers is
    #: computed from the plan's own fields.
    skill_plan: SkillPlan | None = None
    #: How long one step may wait for the reading that confirms it. A knob rather
    #: than a constant because the honest number belongs to the machine: mining a
    #: log and waiting for the world to say so is slow on a shared host, and a
    #: step that ran out its window is reported as `UNKNOWN` rather than retried.
    skill_step_seconds: float = DEFAULT_SKILL_STEP_TIMEOUT_S
    #: What the run hands the mind instead of a plan: the bounds the lease has to
    #: cover before anything is chosen. Its own field rather than a flagged-up
    #: `skill_plan`, because an autonomous run has no plan — the point of the ask
    #: is that the steps are not known yet, while the capabilities they may need
    #: are, and the lease is decided once, up front.
    autonomous: AutonomousAsk | None = None
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
        if self.skill_plan is not None:
            wanted |= self.skill_plan.capabilities
        if self.autonomous is not None:
            wanted |= self.autonomous.capabilities
        return frozenset(wanted)

    @property
    def lease_seconds(self) -> float:
        """How long the authorisation lasts. A hold owns its duration; a look does not.

        One lease covers everything this run asks for, so it has to last as long
        as the longest of them: a lease that covered the movement and lapsed
        before the use did would take a key back that was still wanted, and the
        release is one instruction for all of them either way.

        A skill plan is the longest of them by construction, because its steps
        run one after another under this same lease rather than holding their
        own. The plan's own arithmetic is what says how long that is.
        """

        holds = [value for value in (self.hold_seconds, self.use_seconds) if value is not None]
        if self.skill_plan is not None:
            holds.append(sequence_lease_seconds(self.skill_plan.calls, self.skill_step_seconds))
        if self.autonomous is not None:
            holds.append(self.autonomous.lease_seconds)
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


def launched_minecraft_version(profile: Path) -> str:
    """The version a launcher profile document says its client will run.

    Read here rather than taken from the prepared session because the target the
    session may join is checked against it *before* anything is created, and a run
    that has already built an overlay is the wrong place to discover that the two
    documents name different versions. This is the document's own claim, not a
    verdict on it: the recipe audit inside preparation is what proves the claim
    belongs to a reviewed bundle, and it still runs on the launch path.
    """

    try:
        parsed = json.loads(profile.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject("the launcher profile is not readable UTF-8 JSON") from error
    if not isinstance(parsed, dict):
        raise _reject("the launcher profile must be an object")
    minecraft = cast("dict[str, object]", parsed).get("minecraft")
    if not isinstance(minecraft, dict):
        raise _reject("the launcher profile has no minecraft section")
    version = cast("dict[str, object]", minecraft).get("version")
    if not isinstance(version, str) or not version:
        raise _reject("the launcher profile has no minecraft.version")
    return version


def _mind_for_run(kin_id: str) -> PlayerMind:
    """The mind for one run, from what this operator's environment configures.

    Built here rather than passed in from `bootstrap`: the run's own cost account has
    to be the one the session's spend projection reads, and only this module knows
    when the run starts. A configured-but-disabled model still builds a mind — it
    answers with `MODEL_NOT_CONFIGURED` and the run documents that, which is the
    honest reading of "no credentials" and not a reason to refuse to play.

    The milestone comes from `MINEKIN_GOAL_PRODUCT` and its three companions, and an
    environment that names none gets a Kin with no standing craft target. Core holds no
    default product to fall back to: the demo that wants a pickaxe says so, in the harness.
    """

    config = model_config()
    ledger = cost_ledger_for(config)
    return mind_for(
        model_provider_for(config, ledger=ledger),
        ledger,
        kin_id=kin_id,
        persona_seed=configured_persona_seed() or "",
        goal=milestone_from_environment(),
        model_enabled=config.enabled,
    )


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
    skill_plan: SkillPlan | None = None,
    skill_step_seconds: float = DEFAULT_SKILL_STEP_TIMEOUT_S,
    autonomous: AutonomousAsk | None = None,
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

    target: SessionServerProfile | None = None
    if server_profile is not None:
        if connection_timeout <= 0:
            raise _reject("the connection timeout must be positive")
        # Read before anything is created: an unusable profile is an operator
        # error, and a run that has already built an overlay should not be the
        # thing that discovers one.
        target = load_session_server_profile(
            server_profile, minecraft_version=launched_minecraft_version(profile)
        )

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

    # Where `session stop` leaves its asks for this Kin: the same directory the
    # stopper writes into, because the two processes share no channel but the run's
    # own files.
    stop_requests_at = run_root(root, KinId(prepared.kin_id))

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
        if hold_forward is None
        and not wants_look
        and hold_use is None
        and skill_plan is None
        and autonomous is None
        else InputPlan(
            hold_seconds=hold_forward,
            use_seconds=hold_use,
            strafe=0.0 if hold_strafe is None else hold_strafe,
            jump=hold_jump,
            sneak=hold_sneak,
            look=wants_look,
            yaw_degrees=0.0 if look_yaw_degrees is None else look_yaw_degrees,
            pitch_degrees=0.0 if look_pitch_degrees is None else look_pitch_degrees,
            skill_plan=skill_plan,
            skill_step_seconds=skill_step_seconds,
            autonomous=autonomous,
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
    if skill_step_seconds <= 0:
        # A step with no window would confirm nothing and report nothing: the
        # wait is what turns a sent command into a reading.
        raise _reject("--skill-step-seconds must be positive")
    if skill_plan is not None and hold_at == HOLD_AT_JOIN:
        # The two asks are incompatible rather than merely redundant: `join`
        # grants the lease before the first snapshot, and a skill spends that
        # lease waiting for a later snapshot that the phase guarantees will not
        # have arrived. Refused by name rather than left to produce a run full of
        # `UNKNOWN`.
        raise _reject("--hold-at join cannot carry a skill plan: a skill needs the world")
    if autonomous is not None and skill_plan is not None:
        # One run, one source of the next step: a plan says what happens after
        # this step, an autonomous ask says the Kin decides it from the reading
        # that follows. Both would run whichever hook fired first and leave the
        # other's verdict with nothing behind it.
        raise _reject("--autonomous cannot also carry --skill-plan")
    if autonomous is not None and hold_at == HOLD_AT_JOIN:
        # The reason the plan's guard gives, in the ask's own words: the phase
        # grants the lease before the server's world has reached the client, and
        # a decision is made from a reading that cannot have arrived yet.
        raise _reject("--hold-at join cannot carry --autonomous: a decision needs the world")
    if autonomous is not None and not 1 <= autonomous.step_budget <= DEFAULT_STEP_BUDGET:
        # The budget bounds one turn and the caller may ask for another, so a
        # bigger number is not a longer run — it is a shape nothing here runs.
        raise _reject(f"--autonomous-steps must be between 1 and {DEFAULT_STEP_BUDGET}")
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

    # The readings the skills act on and conclude from, and the two cells the
    # hooks below fill in for the run document to read afterwards. A store only
    # when a plan will read it, because the runtime gates observation intake on
    # its presence.
    observations = (
        WorldObservationStore() if skill_plan is not None or autonomous is not None else None
    )
    skill_outcome: list[SkillSequence | None] = [None]
    skill_stop: list[str] = [""]
    autonomous_outcome: list[AutonomousRun | None] = [None]

    async def until_skills_ready() -> None:
        """Wait for the lease this run's plan runs under, then hand over.

        The same event the hold's watcher waits on, because it is the same
        authorisation: `present_the_plan` sets it only once the lease is granted
        and armed, so a plan that begins here begins under a lease the arbiter
        will still answer for.
        """

        if plan is None:
            return
        await plan.playable.wait()

    async def on_run_skills() -> None:
        """Do the plan's steps under the granted lease and keep the readings' verdicts.

        This runs *beside* the event reader rather than inside `on_playable`, and
        the reason is the wait: a skill spends its whole life looking for a newer
        reading, and `on_playable` is awaited by the very task that delivers
        readings. The hold's own watcher is the other end of the lease — if it
        lapses mid-plan, the arbiter says so at the next step and the sequence
        stops with that reason rather than driving a client it no longer may.
        """

        if plan is None or plan.arbiter is None or plan.lease is None or observations is None:
            # The checker's hazard: `playable` is only set once a lease exists.
            # A refusal to *start* is already recorded by `present_the_plan`, so
            # nothing is added here and the reason stays in `plan.refusal`.
            return
        # One of the two asks, never both: `--autonomous` refuses beside a
        # `--skill-plan`, because an operator-written sequence and a mind that
        # writes its own are answers to different questions. The capability set
        # below is therefore exactly the one this run was asked for.
        ask: SkillPlan | AutonomousAsk | None = skill_plan if skill_plan is not None else autonomous
        if ask is None:
            # The checker's hazard again, and only it: the store this hook needs
            # exists for one of the two asks, and the guard above left without one.
            return
        lease = plan.lease
        deadline = plan.deadline_monotonic_ns
        now = MonotonicInstant(monotonic_ns())
        # Ask the arbiter again, at this instant, for each capability the ask
        # needs. The grant said a lease exists; the per-capability answer is what
        # says this particular kind of command may go out *now*, which is the
        # difference between an authorised Kin and one whose window closed.
        already_sent = {capability for capability, _, _ in plan.commands(lease, deadline)}
        for capability in sorted(ask.capabilities):
            authorised = plan.arbiter.decide(
                InputRequest(
                    lease_id=lease.lease_id,
                    generation=lease.generation,
                    capability=capability,
                    deadline_monotonic_ns=deadline,
                ),
                now=now,
            )
            if not authorised.accepted:
                skill_stop[0] = ",".join(item.value for item in authorised.refusals)
                await record_refusal(ConnectionState.PLAYABLE.value, authorised.refusals)
                return
            if capability not in already_sent:
                # Only the capabilities the hold did not already announce get a
                # row here: a plan that both walks and mines holds one lease for
                # both, and a second `granted` for the walk would read as a
                # second authorisation. The per-step ids are on the run document,
                # where the verdicts are.
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
        skills = WorldSkills(
            sender=host,
            observations=observations,
            capabilities=bridge_session.capabilities,
            # The supervisor owns the child process, so it is the only thing that can
            # say whether the client a step is waiting for still exists. A step whose
            # client has exited ends on that fact rather than on its timeout.
            client_exit=prepared.supervisor.poll,
        )
        authority = ActionAuthority(
            lease_id=lease.lease_id,
            generation=int(lease.generation),
            deadline_monotonic_ns=deadline,
        )
        timeout_ns = int(plan.skill_step_seconds * 1_000_000_000)
        mind = _mind_for_run(str(prepared.kin_id))
        # One counter across whichever ask this run carries: the ledger reader's question
        # is "which step of the sequence is this", and a scripted plan and a mind-written
        # one both answer it with a position rather than with a timestamp nobody aligns.
        step_index = [0]

        async def record_skill_step(payload: dict[str, Any]) -> None:
            step_index[0] += 1
            await record(
                SKILL_STEP_RECORDED,
                {"step_index": step_index[0], **payload},
                source=EventSource.CORE,
                trust_class=TrustClass.CORE,
            )

        async def on_autonomous_step(step: AutonomousStep) -> None:
            # The goal is the mind's own direction rather than a name the operator typed:
            # the run document is the only other place it appears, and nothing downstream
            # of this process can read that until the run is sealed.
            await record_skill_step(
                {
                    "skill": step.intent.skill,
                    "result": step.outcome.result.value,
                    "reason": step.outcome.reason,
                    "action_id": step.outcome.action_id,
                    "attribution": ("" if step.attribution is None else step.attribution.value),
                    "decision_source": step.intent.source,
                    "model_refusal": step.intent.model_refusal,
                    "goal": mind.direction,
                }
            )

        async def on_plan_step(step: SkillStep) -> None:
            # A scripted sequence has no goal and no model to refuse, so the two names the
            # mind would carry are written empty rather than omitted: an omitted field reads
            # as a projection bug, an empty one reads as the answer this run actually has.
            await record_skill_step(
                {
                    "skill": step.name,
                    "result": step.outcome.result.value,
                    "reason": step.outcome.reason,
                    "action_id": step.outcome.action_id,
                    "attribution": "",
                    "decision_source": "OPERATOR_PLAN",
                    "model_refusal": "",
                    "goal": "",
                }
            )

        try:
            if isinstance(ask, AutonomousAsk):
                # The mind writes the steps and the readings conclude from them, so
                # what lands on the document is the whole exchange rather than an
                # operator's rows: each intent, the later reading's verdict, and the
                # word that ended the run.
                autonomous_outcome[0] = await run_autonomous_loop(
                    mind=mind,
                    skills=skills,
                    observations=observations,
                    authority=authority,
                    step_budget=ask.step_budget,
                    timeout_ns=timeout_ns,
                    on_step=on_autonomous_step,
                )
                halted = autonomous_outcome[0]
                # The name the mind stopped on is a fact per run, not per step, and it is the
                # only thing that separates "the channel went" from "the mind ran out of things
                # it was willing to try". The ledger has to be able to say which.
                # `last_precondition` carries the mind's own field name and the word the world
                # said, not the coarse code: an excluded skill plus `CRAFT_GRID_TOO_SMALL` is a
                # missing screen, the same exclusion plus `CRAFT_MATERIALS_MISSING` would be a
                # bag that never filled, and a reader cannot tell them apart from the list alone.
                await record(
                    AUTONOMOUS_RUN_HALTED,
                    {
                        "goal": mind.direction,
                        "stop_reason": halted.stop_reason,
                        "error": halted.stop_detail,
                        "steps": len(halted.steps),
                        "confirmed": halted.as_document()["confirmed"],
                        "excluded_skills": sorted(mind.excluded),
                        "last_precondition": mind.last_precondition,
                    },
                    source=EventSource.CORE,
                    trust_class=TrustClass.CORE,
                )
            else:
                skill_outcome[0] = await run_skill_plan(
                    skills,
                    ask,
                    authority=authority,
                    timeout_ns=timeout_ns,
                    on_step=on_plan_step,
                )
        except (OSError, RuntimeError):
            # The channel went out from under the Kin. Nothing is re-raised: the
            # Bridge releases what it holds when the channel closes, so a step
            # Core could not deliver is a recorded ending, not a run that failed
            # for a reason nobody asked about.
            skill_stop[0] = "CONTROL_CHANNEL_LOST"

    async def until_stop_request() -> None:
        """Wait for the operator to ask, from another process, that this run stop.

        Polled rather than signalled: the stopper is a different process and the one
        thing between them is this run's directory. The exit poll's own interval is
        reused because both questions — is the client gone, has the operator asked —
        are asked of the same filesystem at the same cost, and the ask is addressed
        to this client's pid so a request left by an earlier life of this session
        cannot be mistaken for one aimed at this one.
        """

        while True:
            request = read_request(
                stop_requests_at,
                session_id=prepared.session_id,
                generation=prepared.generation,
                pid=launch.identity.pid,
            )
            if request is not None:
                asked_to_stop[0] = request
                return
            await asyncio.sleep(exit_poll_s)

    async def on_stop_request() -> None:
        """Let go now, while the Bridge is still there to be told.

        This is the whole point of the branch. The wind-down's release is the run's
        last act, and a run that another process is stopping reaches it only after
        that process has terminated the client — so the command lands on a channel
        whose receiver is gone, which is what two sealed runs recorded as
        `input_release_failed`. Answered here, the release goes out over a live
        channel and the receipt is what tells the stopper it may terminate. Nothing
        is written when the send fails: the stopper then reports that it asked and
        got no answer rather than claiming the Bridge was told.
        """

        request = asked_to_stop[0]
        if request is None:
            # The watcher completes only once it has read a request, so this is the
            # checker's hazard rather than the run's.
            return
        if plan is None or plan.arbiter is None:
            # Nothing was ever granted, so there is nothing to withdraw. Still
            # answered: the stopper has to learn that this session saw the ask and
            # is not going to send, instead of waiting out its deadline for nothing.
            write_receipt(
                stop_requests_at,
                request=request,
                released_at=SystemClock().utc_now().isoformat(),
                release=StopRelease.NOTHING_HELD,
            )
            return
        plan.watchdog.disarm()
        await release_inputs(plan.arbiter, ReleaseReason.EXPLICIT)
        stop_released[0] = request.request_id
        write_receipt(
            stop_requests_at,
            request=request,
            released_at=SystemClock().utc_now().isoformat(),
            release=StopRelease.SENT,
        )

    async def on_wind_down() -> None:
        """Take the input back, whatever ended the run.

        Unconditional for the reason the arbiter documents: a Bridge that holds
        nothing is not evidence that the client is holding nothing, so the release
        goes out even when Core believes it granted no lease. The reason code is
        Core's own withdrawal — a session ending is not a fault in the input.

        The one exception is the release this run already sent in answer to a stop
        request: that ask and its receipt name the same command, and sending it
        twice would put two answers on the channel for one ask.
        """

        if plan is None or plan.arbiter is None:
            return
        plan.watchdog.disarm()
        if stop_released[0]:
            return
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

    async def on_session_identity(generation: int, compared: Mapping[str, object]) -> None:
        await record(
            SESSION_IDENTITY_COMPARED,
            {"session_id": prepared.session_id, "generation": generation, **compared},
            # Core's own conclusion, in the same sense the accepted handshake is: it
            # is what this side decided about a report it received, not the report.
            # The observed fields are the Bridge's words about the live Session and
            # this row cannot make them truer than that — what it cannot be is a
            # restatement of the launch arguments, since no argv text reaches it.
            source=EventSource.CORE,
            trust_class=TrustClass.CORE,
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
    # Also cells, for the same reason: the stop-request hooks write them and the
    # wind-down reads one. The request is the ask this run answers; the id recorded
    # there is the receipt's, and it is what makes the wind-down skip a release this
    # run has already sent.
    asked_to_stop: list[StopRequest | None] = [None]
    stop_released: list[str] = [""]

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
        on_session_identity=on_session_identity,
        on_wind_down=on_wind_down,
        # Only when a hold was asked for: with no lease there is no moment, and a
        # watcher that never completes is a task that exists to be cancelled.
        until_input_release=None if plan is None else until_input_release,
        on_input_release=None if plan is None else on_input_release,
        # Only when a world was named: with no attempt there is no deadline, and
        # a watcher that never completes is a task that exists to be cancelled.
        until_connection_deadline=None if target is None else until_connection_deadline,
        on_connection_deadline=None if target is None else on_connection_deadline,
        # Always armed: an operator's ask needs no lease and no world to be worth
        # answering, and a session that never reads one leaves the stopper waiting
        # out its deadline instead of learning that nobody was listening.
        until_stop_request=until_stop_request,
        on_stop_request=on_stop_request,
        recorded=prepared.recorded,
        # The readings only have somewhere to go once a plan will read them, and
        # the plan's own branch is armed for the same reason: with no plan there is
        # a watcher that can never fire.
        world_observations=observations,
        until_skills_ready=(
            None if (skill_plan is None and autonomous is None) else until_skills_ready
        ),
        on_run_skills=(None if (skill_plan is None and autonomous is None) else on_run_skills),
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
    if skill_plan is not None:
        sequence = skill_outcome[0]
        # What the plan asked, what each step's later reading said, and where it
        # gave up — on the document, because §5 names no event for a skill's
        # verdict and the verdict is the readings' conclusion rather than a fact
        # Core decided when it sent a command. `skill_stop` wins over the
        # sequence's own marker because "nothing ran" has no last step.
        run = replace(
            run,
            skill_plan=tuple(call.name for call in skill_plan.calls),
            skills=(
                () if sequence is None else tuple(step.as_document() for step in sequence.steps)
            ),
            skill_stop=skill_stop[0] or ("" if sequence is None else sequence.stopped_at),
        )
    if autonomous is not None:
        # The mind's own account of the turn — which intent it formed on which reading,
        # what the later reading said about it, and the word that ended the run — on the
        # document for the same reason the plan's verdicts are: §5 names no event for a
        # conclusion the readings reached. A run that never got to ask has no steps, and
        # its `stop_reason` is whatever `skill_stop` recorded, which is the honest shape
        # of "asked for a mind, never got a lease to run one under".
        run = replace(
            run,
            autonomous=(
                autonomous_outcome[0]
                if autonomous_outcome[0] is not None
                else AutonomousRun(stop_reason=skill_stop[0])
            ).as_document(),
        )
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
class StopReleaseReport:
    """What the live clients answered, before any of them was terminated.

    Keyed by pid, because a pid is what the stopper proved to be this Kin's client
    and what the stop document already names.
    """

    #: Asked to let go of the client's inputs.
    asked: tuple[int, ...]
    #: Answered that Core's release went out over a live channel.
    released: tuple[int, ...]
    #: Answered that it holds nothing, so nothing is coming.
    nothing_held: tuple[int, ...]
    #: Asked and never answered within the deadline — the stop went ahead anyway.
    unconfirmed: tuple[int, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "asked": list(self.asked),
            "released": list(self.released),
            "nothing_held": list(self.nothing_held),
            "unconfirmed": list(self.unconfirmed),
        }


#: What a stop reports when no client was live to be asked.
NOTHING_TO_RELEASE = StopReleaseReport(asked=(), released=(), nothing_held=(), unconfirmed=())


def ask_live_clients_to_release(
    runs: Path,
    *,
    probe: Callable[[int], Liveness] = default_probe,
    cmdline: Callable[[int], bytes | None] = default_cmdline,
    timeout_s: float = DEFAULT_STOP_RELEASE_TIMEOUT_S,
    poll_s: float = DEFAULT_EXIT_POLL_S,
) -> StopReleaseReport:
    """Ask every client this Kin recorded as live to release its inputs, and wait.

    One round of asks and then one wait shared by all of them: the clients are
    stopped together, so asking one at a time would make the total wait the sum of
    the individual ones. The deadline is spent whether or not the answers arrive —
    a session that is not listening is a fact to report, not a reason to leave a
    client running forever.
    """

    # `ALIVE` out of `session_claims` already means the command line matched the
    # marker, so these are pids this Kin may ask about; an unresolved one is left to
    # the stopper's own refusal, which is the same rule as before.
    requests = {
        claim.identity.pid: write_request(
            runs,
            session_id=claim.session_id,
            generation=claim.generation,
            pid=claim.identity.pid,
            request_id=OpaqueId.new().value,
            requested_at=SystemClock().utc_now().isoformat(),
        )
        for claim in session_claims(runs, probe=probe, cmdline=cmdline)
        if claim.liveness is Liveness.ALIVE
    }
    if not requests:
        return NOTHING_TO_RELEASE

    answers: dict[int, StopRelease] = {}
    deadline = monotonic_ns() + int(timeout_s * 1_000_000_000)
    while True:
        for pid, request in requests.items():
            if pid not in answers:
                receipt = read_receipt(runs, request=request)
                if receipt is not None:
                    answers[pid] = receipt.release
        if len(answers) == len(requests) or monotonic_ns() >= deadline:
            unconfirmed = tuple(pid for pid in requests if pid not in answers)
            return StopReleaseReport(
                asked=tuple(requests),
                released=tuple(
                    pid for pid, release in answers.items() if release is StopRelease.SENT
                ),
                nothing_held=tuple(
                    pid for pid, release in answers.items() if release is StopRelease.NOTHING_HELD
                ),
                unconfirmed=unconfirmed,
            )
        time.sleep(poll_s)


@dataclass(frozen=True, slots=True)
class StopReport:
    kin_id: str
    outcome: StopOutcome
    release: StopReleaseReport = NOTHING_TO_RELEASE

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "session stop",
            "status": "stopped" if self.outcome.complete else "blocked",
            "kin_id": self.kin_id,
            "release": self.release.as_document(),
            **self.outcome.as_document(),
        }


def stop_session(
    root: Path,
    *,
    kin_selector: str | None = None,
    probe: Callable[[int], Liveness] = default_probe,
    read_cmdline: Callable[[int], bytes | None] = default_cmdline,
    terminate: Callable[[int], None] = terminate_process,
    release_timeout_s: float = DEFAULT_STOP_RELEASE_TIMEOUT_S,
) -> StopReport:
    """Stop the clients this Kin recorded, as far as they can be identified.

    Stopping is idempotent: a Kin with nothing running is already stopped. What is
    not idempotent is touching a process that cannot be shown to be ours, so that
    is reported rather than done.

    The ask comes first and the terminate after it, because the only process that
    can put a release on a live Bridge's channel is the session holding that channel
    — and that channel dies with the client being terminated. Waiting for the receipt
    is what makes the order real instead of intended.
    """

    kin_id = select_kin(root, kin_selector)
    runs = run_root(root, kin_id)
    release = ask_live_clients_to_release(
        runs,
        probe=probe,
        cmdline=read_cmdline,
        timeout_s=release_timeout_s,
    )
    outcome = stop_recorded_clients(
        runs,
        probe=probe,
        read_cmdline=read_cmdline,
        terminate=terminate,
    )
    return StopReport(kin_id=str(kin_id), outcome=outcome, release=release)
