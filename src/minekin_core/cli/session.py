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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.bridge.bootstrap import bridge_session_for, descriptor_path
from minekin_core.adapters.bridge.ipc import BridgeIpcHost, BridgeSession
from minekin_core.adapters.launcher.artifacts import ArtifactStore, SessionOverlayStore
from minekin_core.adapters.launcher.assets import materialise_assets
from minekin_core.adapters.launcher.launch_plan import (
    artifacts_from_plan,
    build_launch_plan,
    find_workspace_root,
)
from minekin_core.adapters.launcher.mods import install_fixed_mods
from minekin_core.adapters.launcher.natives import materialise_natives
from minekin_core.adapters.launcher.offline_session import OFFLINE_SESSION_CANDIDATES
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
from minekin_core.adapters.launcher.supervisor import ProcessIdentity, ProcessSupervisor
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.identity_store import read_identity_root
from minekin_core.adapters.sqlite.session_log import (
    CLIENT_EXITED,
    HELLO_ACCEPTED,
    JOIN_OBSERVED,
    PLAYABLE_ESTABLISHED,
    SESSION_INTERRUPTED,
    SessionEventLog,
    reconcile_outbox_async,
)
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.application.recovery_service import RecoveryReport
from minekin_core.cli.init import DATABASE_NAME, KIN_DIRECTORY, kin_directory, run_root
from minekin_core.cli.session_runtime import SessionOutcome, SessionRun, supervise_session
from minekin_core.domain.connection import ConnectionGenerations, ConnectionState
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.ids import ClientInstanceId, KinId, RunId
from minekin_core.domain.recovery import START_CLIENT
from minekin_core.domain.session_state import SessionState, SessionStateMachine

SupervisorFactory = Callable[[Path], ProcessSupervisor]

#: What reconciliation reports when there was nothing left over. Named rather
#: than built in a default, so the default is a value and not an expression.
NOTHING_TO_RECONCILE = RecoveryReport(invalidated=(), waiting=())

# The connection states that are a fact §5 names. The three phases before a join
# are progress towards one, not facts themselves, so they are deliberately
# absent and the recorder ignores them.
_CONNECTION_EVENTS: dict[ConnectionState, str] = {
    ConnectionState.JOIN_SEEN: JOIN_OBSERVED,
    ConnectionState.PLAYABLE: PLAYABLE_ESTABLISHED,
    ConnectionState.DISCONNECTED: SESSION_INTERRUPTED,
    ConnectionState.FAILED: SESSION_INTERRUPTED,
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
    recovery: RecoveryReport = NOTHING_TO_RECONCILE
    bridge_session: BridgeSession | None = None
    bridge_descriptor: Path | None = None


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

    runs = run_root(root, kin_id)
    plan = build_launch_plan(profile)
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
    spec = build_process_spec(
        plan,
        run_root=runs,
        overlay=overlay,
        material=identity.material,
        candidate=OFFLINE_SESSION_CANDIDATES[0],
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
        recovery=recovery,
        bridge_session=bridge_session,
        bridge_descriptor=descriptor,
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
) -> tuple[SessionLaunch, SessionRun]:
    """Start a managed session with a live Bridge and stay with it until it ends.

    Everything here runs in one event loop on purpose. The host's listening
    sockets belong to the loop that created them, so preparing it in one
    `asyncio.run` and supervising in another would leave the transport behind on
    a loop that has already closed.
    """

    session = SessionStateMachine()
    session.advance(SessionState.PREPARING)
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
    )
    if prepared.bridge_session is None or prepared.bridge_descriptor is None:
        raise _reject("the session was prepared without a Bridge session to host")

    session.advance(SessionState.STARTING_CLIENT)
    host = BridgeIpcHost(prepared.bridge_session)
    # Written before the spawn: the client reads it during its own startup, and
    # a client that finds no descriptor refuses to come up at all.
    await host.prepare(prepared.bridge_descriptor)

    launch = await launch_prepared_async(prepared)
    session.advance(SessionState.WAITING_BRIDGE)
    session.advance(SessionState.HANDSHAKING)

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

    async def on_connection(state: ConnectionState) -> None:
        event_type = _CONNECTION_EVENTS.get(state)
        if event_type is None:
            # A phase that only moves the session closer to a join is not a fact
            # §5 names, and inventing one would put noise in the ledger.
            return
        await record(
            event_type,
            {"phase": state.value},
            source=EventSource.BRIDGE,
            trust_class=TrustClass.BRIDGE_FILTERED,
        )

    async def until_client_exit() -> None:
        while prepared.supervisor.running():
            await asyncio.sleep(exit_poll_s)

    run = await supervise_session(
        host=host,
        session=session,
        connections=ConnectionGenerations(),
        handshake_timeout=handshake_timeout,
        until_client_exit=until_client_exit,
        on_handshake=on_handshake,
        on_connection=on_connection,
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
