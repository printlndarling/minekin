"""Running one managed session until it ends.

`cli/session.py` gets a session ready and started; this module owns what happens
next. It is the §10 task tree from the internal architecture, scoped to the
parts that exist today: the bounded handshake wait, the Bridge event stream, and
ending the run when the client does.

It lives in the composition root rather than in `application/` because it has to
name a concrete transport, the concrete session machines and the concrete
supervisor at once, and §2 already reserves the entrypoints layer as the only
one allowed to know all of them. A port-shaped version would need an `Any`-typed
seam with exactly one implementation behind it.

No bare `create_task`: every task started here is awaited or cancelled and its
failure becomes the run's outcome, because a session whose event reader died
quietly looks exactly like a session where nothing is happening.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from minekin_core.adapters.bridge.admission import accept_snapshot, apply_lifecycle
from minekin_core.adapters.bridge.ipc import BridgeIpcHost, IpcProtocolError
from minekin_core.adapters.bridge.perception import admit_first_snapshot
from minekin_core.domain.connection import (
    CallbackDisposition,
    ConnectionGenerations,
    ConnectionState,
)
from minekin_core.domain.session_material import RecordedSessionMaterial
from minekin_core.domain.session_state import (
    SessionState,
    SessionStateMachine,
    advance_for_connection,
)
from minekin_core.generated.minekin.v1 import observation_pb2

# A disposition worth reporting: the attempt moved, or it came to a stop. A
# stale generation is what a reconnect leaves behind and says nothing about the
# connection the session is actually in.
_REPORTED_DISPOSITIONS = frozenset({CallbackDisposition.ADVANCED, CallbackDisposition.FAILED})


class SessionOutcome(StrEnum):
    """How a run ended, as a stable token for evidence."""

    CLIENT_EXITED = "CLIENT_EXITED"
    BRIDGE_LOST = "BRIDGE_LOST"
    HANDSHAKE_TIMEOUT = "HANDSHAKE_TIMEOUT"
    HANDSHAKE_FAILED = "HANDSHAKE_FAILED"


@dataclass(frozen=True, slots=True)
class SessionRun:
    outcome: SessionOutcome
    session_state: SessionState
    connection_state: ConnectionState | None
    events_applied: int
    events_ignored: int
    snapshots_admitted: int = 0
    snapshot_rejections: tuple[str, ...] = ()
    entities_admitted: int = 0
    entities_rejected: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": "ended",
            "outcome": self.outcome.value,
            "session_state": self.session_state.value,
            "connection_state": (
                None if self.connection_state is None else self.connection_state.value
            ),
            "events_applied": self.events_applied,
            "events_ignored": self.events_ignored,
            # A first snapshot that was not admitted is the difference between a
            # Kin that could not see and a Kin that saw nothing, so the count and
            # the reasons are reported rather than folded into "ignored".
            "snapshots_admitted": self.snapshots_admitted,
            "snapshot_rejections": list(self.snapshot_rejections),
            # What the Kin could see, and what was proposed and dropped. A
            # snapshot with no entities is either an empty world or a filter that
            # dropped everything, and those are different facts.
            "entities_admitted": self.entities_admitted,
            "entities_rejected": self.entities_rejected,
        }


@dataclass(slots=True)
class _Progress:
    applied: int = 0
    ignored: int = 0
    snapshots_admitted: int = 0
    snapshot_rejections: set[str] = field(default_factory=lambda: set[str]())
    entities_admitted: int = 0
    entities_rejected: int = 0


async def supervise_session(
    *,
    host: BridgeIpcHost,
    session: SessionStateMachine,
    connections: ConnectionGenerations,
    handshake_timeout: float,
    until_client_exit: Callable[[], Awaitable[object]],
    on_handshake: Callable[[], Awaitable[None]] | None = None,
    on_ready: Callable[[], Awaitable[None]] | None = None,
    on_connection: Callable[[ConnectionState, str], Awaitable[None]] | None = None,
    recorded: RecordedSessionMaterial | None = None,
) -> SessionRun:
    """Wait for the handshake, follow the Bridge, and stop when the client does.

    `until_client_exit` completes when the managed client is gone; the caller
    owns how it knows, because "the process ended" and "the operator asked to
    stop" both end a run and the runtime should not have to tell them apart. Its
    result is ignored, so an `Event.wait` is a fine thing to pass.

    `on_ready` runs once the session has reached the menu, before a single report
    is read. It is the caller's chance to act on a client that has proved itself
    and is not yet doing anything — asking it to connect to a world is that. The
    runtime does not send the command itself because which world, and under which
    profile, is a decision it has no inputs for.

    The callbacks report what this run observed — that the Bridge proved its
    session, and which connection state an attempt reached *and why it stopped
    there*. The reason is the Bridge's stable classification, not a server's
    words, and it travels with the state because a failure whose category is
    dropped is a failure nobody can act on. They say nothing about how that
    becomes a ledger entry: which event type and which trust class a fact
    deserves is a decision this module has no business making.
    """

    if handshake_timeout <= 0:
        raise ValueError("handshake_timeout must be positive")

    progress = _Progress()
    try:
        failure = await _authenticate(host, handshake_timeout)
        if failure is not None:
            _wind_down(session, failed=True)
            return _report(failure, session, connections, progress)

        if on_handshake is not None:
            await on_handshake()
        session.advance(SessionState.READY_MENU)
        # Before the reader starts, so a command that provokes an immediate
        # report cannot race the task that is supposed to read it.
        if on_ready is not None:
            await on_ready()

        reader = asyncio.create_task(
            _read_events(host, session, connections, progress, on_connection, recorded),
            name="minekin-bridge-events",
        )
        client = asyncio.create_task(_client_exited(until_client_exit), name="minekin-client-exit")
        try:
            finished, _ = await asyncio.wait({reader, client}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (reader, client):
                task.cancel()
            # A cancelled client watcher may be blocked in a thread the caller
            # owns; gather with return_exceptions so this wait cannot hang or
            # raise before the transport is closed.
            await asyncio.gather(reader, client, return_exceptions=True)

        if reader in finished:
            error = reader.exception()
            if isinstance(error, IpcProtocolError):
                # The Bridge broke the negotiated contract. Anything else is a
                # bug in this process and must not be folded into a network
                # outcome, so it propagates and the CLI reports an internal
                # invariant.
                _wind_down(session, failed=True)
                return _report(SessionOutcome.BRIDGE_LOST, session, connections, progress)
            if error is not None:
                # A payload, state-machine, or callback failure is a Core
                # invariant error, not a normal client exit. Preserve the
                # original exception and traceback for the CLI boundary.
                raise error
            raise RuntimeError("Bridge event reader stopped without a terminal outcome")

        _wind_down(session, failed=False)
        return _report(SessionOutcome.CLIENT_EXITED, session, connections, progress)
    finally:
        # §13: invalidate the generation before the transport stops, so a late
        # report from the closed socket cannot advance a session that is
        # already winding down.
        active = connections.active
        if active is not None:
            connections.close(active.generation)
        await host.close()


async def _client_exited(until_client_exit: Callable[[], Awaitable[object]]) -> None:
    """Adapt the caller's awaitable to the `None` this module waits on."""

    await until_client_exit()


async def _authenticate(host: BridgeIpcHost, timeout: float) -> SessionOutcome | None:
    """Prove the session, or say how it failed. `None` means the Bridge is up."""

    try:
        await host.authenticate(timeout)
    except TimeoutError:
        return SessionOutcome.HANDSHAKE_TIMEOUT
    except (OSError, RuntimeError):
        # The transport closed, or the Bridge proved the wrong identity. Both
        # are the handshake failing closed, and the host has already torn itself
        # down by the time this returns.
        return SessionOutcome.HANDSHAKE_FAILED
    return None


async def _read_events(
    host: BridgeIpcHost,
    session: SessionStateMachine,
    connections: ConnectionGenerations,
    progress: _Progress,
    on_connection: Callable[[ConnectionState, str], Awaitable[None]] | None,
    recorded: RecordedSessionMaterial | None,
) -> None:
    """Apply every reported phase until the channel ends or the run is cancelled."""

    while True:
        event = await host.receive_event()
        message = event.message
        if isinstance(message, observation_pb2.InitialObservation):
            await _admit_first_snapshot(
                message, session, connections, progress, on_connection, recorded
            )
            continue
        if not isinstance(message, observation_pb2.ConnectionLifecycle):
            # Counted rather than dropped silently: an event type this build
            # does not act on is a fact about the run, not noise.
            progress.ignored += 1
            continue
        outcome = apply_lifecycle(connections, message)
        if outcome.accepted:
            progress.applied += 1
        decision = outcome.decision
        if decision is None:
            continue
        advance_for_connection(session, decision)
        if (
            on_connection is not None
            and decision.disposition in _REPORTED_DISPOSITIONS
            and decision.current_state is not None
        ):
            await on_connection(decision.current_state, outcome.failure_reason)


async def _admit_first_snapshot(
    snapshot: observation_pb2.InitialObservation,
    session: SessionStateMachine,
    connections: ConnectionGenerations,
    progress: _Progress,
    on_connection: Callable[[ConnectionState, str], Awaitable[None]] | None,
    recorded: RecordedSessionMaterial | None,
) -> None:
    """Let an admitted snapshot, and not a Bridge's word, make an attempt playable.

    The contract puts the acceptance here: the Bridge sends the first
    authoritative snapshot and the Runtime validates it before anything is marked
    PLAYABLE. A snapshot that is not admitted changes nothing and yields no
    entities — it is counted with its reasons rather than dropped, because "the
    Kin could not see" and "the Kin saw nothing" are different facts about a run.
    """

    attempt = connections.active
    if attempt is None or recorded is None:
        progress.ignored += 1
        return
    admission = admit_first_snapshot(snapshot, generation=attempt.generation, recorded=recorded)
    # Counted either way: the filter runs whether or not the snapshot is admitted,
    # and "the Kin proposed six things and could confirm two" is evidence about
    # the world rather than about the verdict.
    progress.entities_rejected += len(admission.visible_world.rejected)
    if not admission.admitted:
        progress.snapshot_rejections.update(reason.value for reason in admission.reasons)
        return
    decision = accept_snapshot(connections, attempt.generation)
    if decision.disposition is not CallbackDisposition.ADVANCED or decision.current_state is None:
        progress.ignored += 1
        return
    progress.applied += 1
    progress.snapshots_admitted += 1
    progress.entities_admitted += len(admission.visible_world.accepted)
    advance_for_connection(session, decision)
    if on_connection is not None:
        await on_connection(decision.current_state, "")


def _wind_down(session: SessionStateMachine, *, failed: bool) -> None:
    """Leave the session in §7's outlets, in the only order the table allows.

    A Bridge lost while the session is merely at the menu is not a failure: the
    frozen table gives READY_MENU no outlet to FAILED, because a client sitting
    in the menu whose control channel died is a session to stop, not a session
    that broke. Inside a connection it is a failure, and the table agrees.
    """

    if failed and session.can_advance(SessionState.FAILED):
        session.advance(SessionState.FAILED)
    if session.can_advance(SessionState.STOPPING):
        session.advance(SessionState.STOPPING)
    if session.can_advance(SessionState.STOPPED):
        session.advance(SessionState.STOPPED)


def _report(
    outcome: SessionOutcome,
    session: SessionStateMachine,
    connections: ConnectionGenerations,
    progress: _Progress,
) -> SessionRun:
    active = connections.active
    return SessionRun(
        outcome=outcome,
        session_state=session.state,
        connection_state=None if active is None else active.state,
        events_applied=progress.applied,
        events_ignored=progress.ignored,
        snapshots_admitted=progress.snapshots_admitted,
        snapshot_rejections=tuple(sorted(progress.snapshot_rejections)),
        entities_admitted=progress.entities_admitted,
        entities_rejected=progress.entities_rejected,
    )
