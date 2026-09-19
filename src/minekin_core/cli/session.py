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
from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.adapters.launcher.metadata import Artifact
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
from minekin_core.adapters.launcher.supervisor import ProcessIdentity, ProcessSupervisor
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.identity_store import read_identity_root
from minekin_core.adapters.sqlite.session_log import SessionEventLog
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.cli.init import DATABASE_NAME, KIN_DIRECTORY, kin_directory, run_root
from minekin_core.cli.session_runtime import SessionRun, supervise_session
from minekin_core.domain.connection import ConnectionGenerations
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.ids import ClientInstanceId, KinId, RunId
from minekin_core.domain.session_state import SessionState, SessionStateMachine

SupervisorFactory = Callable[[Path], ProcessSupervisor]

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


def _artifact_from(entry: Mapping[str, Any]) -> Artifact:
    """Read one plan artifact, refusing a malformed entry rather than coercing it."""

    try:
        size = entry["size"]
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("size")
        return Artifact(
            coordinate=str(entry["coordinate"]),
            path=str(entry["path"]),
            url=str(entry["url"]),
            size=size,
            sha1=str(entry["sha1"]),
            kind=str(entry.get("kind", "library")),
        )
    except (KeyError, TypeError) as error:
        raise _reject(
            f"launch plan artifact entry is malformed: {error}", ErrorCategory.SUPPLY_CHAIN
        ) from error


def require_store_complete(plan: Mapping[str, Any], store: ArtifactStore) -> None:
    """Every artifact the plan names must already be in the store, verified.

    All of them, not only the ones in argv: a missing asset makes the client fail
    in ways that look like a rendering bug rather than a missing download.
    """

    entries = cast(list[Mapping[str, Any]], plan.get("artifacts", []))
    if not entries:
        raise _reject("launch plan names no artifacts", ErrorCategory.SUPPLY_CHAIN)
    missing: list[str] = []
    for entry in entries:
        artifact = _artifact_from(entry)
        try:
            store.verify(artifact)
        except MinekinError:
            missing.append(artifact.coordinate)
    if missing:
        raise _reject(
            f"{len(missing)} of {len(entries)} artifacts are not in the store yet, "
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
    connection = connect_reader(database)
    try:
        identity = read_identity_root(connection)
    finally:
        connection.close()

    runs = run_root(root, kin_id)
    plan = build_launch_plan(profile)
    require_launchable(plan)
    require_store_complete(plan, ArtifactStore(runs / "artifact-store"))

    # Before anything is created: a second client on top of a live one shares the
    # overlay and appears to the server as a second player.
    require_no_unresolved_client(runs, probe=probe)

    overlays = SessionOverlayStore(runs / "session")
    overlay = overlays.create(session_id, generation)
    if overlay != session_overlay_path(runs, session_id, generation):
        # The supervisor's log directory was named from this path already.
        raise _reject("the session overlay was created somewhere unexpected")

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
        bridge_session=bridge_session,
        bridge_descriptor=descriptor,
    )


def launch_prepared(prepared: PreparedSession) -> SessionLaunch:
    """Spawn the prepared client and record it.

    The ledger records what the launcher did, after it did it. Refusals before
    this point are operator errors rather than run outcomes, so they leave no
    entry: a run only begins once a process does.
    """

    try:
        process = prepared.supervisor.start(prepared.spec)
    except MinekinError as error:
        prepared.ledger.record_process_failed(
            kin_id=prepared.kin_id,
            run_id=prepared.run_id,
            session_id=prepared.session_id,
            generation=prepared.generation,
            error=error,
        )
        raise
    write_marker(
        prepared.overlay,
        identity=process,
        session_id=prepared.session_id,
        generation=prepared.generation,
    )
    prepared.ledger.record_process_started(
        kin_id=prepared.kin_id,
        run_id=prepared.run_id,
        session_id=prepared.session_id,
        generation=prepared.generation,
        client_instance_id=prepared.client_instance_id,
        argv_digest=process.argv_digest,
    )
    return SessionLaunch(
        session_id=prepared.session_id,
        generation=prepared.generation,
        kin_id=prepared.kin_id,
        run_id=prepared.run_id,
        overlay=str(prepared.overlay),
        identity=process,
        argv_digest=process.argv_digest,
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
    prepared = prepare_session(
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
        host_bridge=True,
    )
    if prepared.bridge_session is None or prepared.bridge_descriptor is None:
        raise _reject("the session was prepared without a Bridge session to host")

    session.advance(SessionState.STARTING_CLIENT)
    host = BridgeIpcHost(prepared.bridge_session)
    # Written before the spawn: the client reads it during its own startup, and
    # a client that finds no descriptor refuses to come up at all.
    # Written before the spawn: the client reads it during its own startup, and
    # a client that finds no descriptor refuses to come up at all.
    await host.prepare(prepared.bridge_descriptor)

    # Off the loop, for two reasons: launching is blocking work, and the ledger
    # opens its own writer through `asyncio.run`, which cannot be nested inside
    # a loop that is already running. §9 wants the fsync off this loop anyway.
    launch = await asyncio.to_thread(launch_prepared, prepared)
    session.advance(SessionState.WAITING_BRIDGE)
    session.advance(SessionState.HANDSHAKING)

    async def until_client_exit() -> None:
        while prepared.supervisor.running():
            await asyncio.sleep(exit_poll_s)

    run = await supervise_session(
        host=host,
        session=session,
        connections=ConnectionGenerations(),
        handshake_timeout=handshake_timeout,
        until_client_exit=until_client_exit,
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
