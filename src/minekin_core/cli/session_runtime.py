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
from collections.abc import Awaitable, Callable, Mapping
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
from minekin_core.generated.minekin.v1 import control_pb2, observation_pb2

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
    actions_applied: int = 0
    actions_refused: int = 0
    release_failed: bool = False
    input_refusal: str = ""
    #: The reason Core abandoned a connection attempt, empty when it abandoned
    #: none. Recorded on the document for the same reason `input_refusal` is: §5
    #: names no event for "the attempt was given up on", and inventing a ledger
    #: fact would put a word in the contract that the contract does not have.
    connection_cancelled: str = ""
    #: Whether the cancel could not be delivered. Its own flag rather than the
    #: release's: they are two different things Core owed the Bridge.
    connection_cancel_failed: bool = False
    #: The world this run put in the client's game directory, when it put one
    #: there: the level it was told to enter and a digest of the bytes as they
    #: were handed over. §5 names no session event for "a world was placed here"
    #: — it is a fact about the launch rather than about the session — so it lives
    #: on the document, and it is the name the contract asks a host's world to
    #: have ("seed_or_snapshot_id") rather than a description of one.
    world_snapshot: Mapping[str, object] | None = None
    #: What the Bridge last said about publishing the world this Kin hosts: the
    #: contract's phase and the port it named, or null for a run that never asked.
    #: A fact about the world rather than about the session, so it lives on the
    #: document beside the snapshot and not in the ledger.
    lan_publication: Mapping[str, object] | None = None

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
            # Whether the Bridge carried out what it was told to do. A
            # refused command is the difference between a Kin that did not
            # move and a Kin that was never able to.
            "actions_applied": self.actions_applied,
            "actions_refused": self.actions_refused,
            # Whether the session could say goodbye. The Bridge releases on its
            # own when the channel goes, so this is about Core's side of the
            # promise and is recorded rather than assumed.
            "input_release_failed": self.release_failed,
            # Why this run never held the input, in the arbiter's words. Empty
            # when it held what it asked for. The document rather than the
            # ledger, because a refusal means no release is ever sent and the
            # release is what would have carried it.
            "input_refusal": self.input_refusal,
            # What Core decided about an attempt that outlived its own deadline,
            # in the wire enum's words. Empty when no attempt was abandoned.
            "connection_cancelled": self.connection_cancelled,
            "connection_cancel_failed": self.connection_cancel_failed,
            # Which world this run seeded, if any: null rather than an empty
            # object, because a run that seeded nothing has no world to name.
            "world_snapshot": (None if self.world_snapshot is None else dict(self.world_snapshot)),
            # What the Bridge said about publishing this Kin's world, and null for
            # every run that never asked it to. The port is the fact a joiner needs
            # and the phase is whether there is one to join.
            "lan_publication": (
                None if self.lan_publication is None else dict(self.lan_publication)
            ),
        }


#: The contract's host event set, as the run document spells it. Closed on purpose:
#: a phase Core cannot name is a report it must count rather than believe.
_LAN_PHASES: dict[int, str] = {
    observation_pb2.HOST_PHASE_LAN_OPENED: "LAN_OPENED",
    observation_pb2.HOST_PHASE_LAN_OPEN_FAILED: "LAN_OPEN_FAILED",
}


@dataclass(slots=True)
class _Progress:
    applied: int = 0
    ignored: int = 0
    snapshots_admitted: int = 0
    snapshot_rejections: set[str] = field(default_factory=lambda: set[str]())
    entities_admitted: int = 0
    entities_rejected: int = 0
    actions_applied: int = 0
    actions_refused: int = 0
    release_failed: bool = False
    connection_cancelled: str = ""
    connection_cancel_failed: bool = False
    #: The last thing the Bridge said about publishing the world this Kin hosts.
    #: A report rather than a command's echo: it arrives when it arrives, and an
    #: attempt is answered by the outcome it ends in.
    lan_publication: Mapping[str, object] | None = None


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
    on_playable: Callable[[], Awaitable[None]] | None = None,
    on_wind_down: Callable[[], Awaitable[None]] | None = None,
    until_input_release: Callable[[], Awaitable[object]] | None = None,
    on_input_release: Callable[[], Awaitable[None]] | None = None,
    until_connection_deadline: Callable[[], Awaitable[object]] | None = None,
    on_connection_deadline: Callable[[], Awaitable[None]] | None = None,
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

    `on_playable` runs once, on the transition the snapshot admission produced:
    it is the first moment a session may be given input, and *only* the caller can
    send one, because which movement, under which lease and for how long are all
    decisions this module has no inputs for. It is awaited in the reader, so it is
    a command being sent rather than something being waited for.

    `until_input_release` completes when the caller's authorisation to drive the
    client should end, and `on_input_release` is what it does about that. The
    caller owns the moment because only the caller knows it: a lease is granted
    with a deadline, and Core is the side that granted it. The runtime owns the
    task, because a task started inside a callback is a task nobody cancels —
    and this one has to be cancelled, or a run that has ended would still be
    scheduled to act.

    `until_connection_deadline` and `on_connection_deadline` are the same shape
    for the same reason: a connection attempt carries its own deadline, and the
    side that issued it is the side that knows when it has passed. What it does
    about that is not this module's decision either — but nothing about it ends
    the run, and that is what the two branches have in common: each fires, is
    answered, and then the session carries on.

    `on_wind_down` is the last chance to speak to the Bridge: it runs after the
    generation is closed and before the transport is, which is the only order in
    which a release can both be honest about the generation it belongs to and still
    reach the Bridge. A failure there is recorded rather than raised, because the
    Bridge releases everything it holds when the channel goes away — that is §12's
    second watchdog, and this call only makes it explicit.

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
    # Assigned on every path; reported after the wind-down, because whether the
    # session could say goodbye to its Bridge is part of how the run ended and a
    # report built before that would be a report of a different run.
    outcome: SessionOutcome
    connection_state: ConnectionState | None = None
    try:
        failure = await _authenticate(host, handshake_timeout)
        if failure is not None:
            _wind_down(session, failed=True)
            outcome = failure
        else:
            if on_handshake is not None:
                await on_handshake()
            session.advance(SessionState.READY_MENU)
            # Before the reader starts, so a command that provokes an immediate
            # report cannot race the task that is supposed to read it.
            if on_ready is not None:
                await on_ready()

            reader = asyncio.create_task(
                _read_events(
                    host, session, connections, progress, on_connection, on_playable, recorded
                ),
                name="minekin-bridge-events",
            )
            client = asyncio.create_task(_awaited(until_client_exit), name="minekin-client-exit")
            # Branches that fire without ending the run: each is a moment the
            # caller owns, and the runtime does what it asks and goes back to
            # waiting — which is why the wait is a loop rather than a race.
            branches: dict[asyncio.Task[None], Callable[[], Awaitable[None]]] = {}
            if until_input_release is not None and on_input_release is not None:
                branches[
                    asyncio.create_task(_awaited(until_input_release), name="minekin-input-release")
                ] = on_input_release
            if until_connection_deadline is not None and on_connection_deadline is not None:
                branches[
                    asyncio.create_task(
                        _awaited(until_connection_deadline), name="minekin-connection-deadline"
                    )
                ] = on_connection_deadline
            watched: set[asyncio.Task[None]] = {reader, client, *branches}
            try:
                while True:
                    finished, _ = await asyncio.wait(watched, return_when=asyncio.FIRST_COMPLETED)
                    if reader in finished or client in finished:
                        break
                    # The caller's moment arrived and nothing else ended: do the one
                    # thing it asked for, then keep supervising. The task is dropped
                    # from the set because it is done, and a done task left in the
                    # set would make the very next wait return immediately.
                    for task in [item for item in finished if item in branches]:
                        watched.discard(task)
                        answer = branches[task]
                        try:
                            await answer()
                        except (OSError, RuntimeError):
                            # The wind-down's rule, for the same reason: the Bridge
                            # releases everything it holds when the channel goes, so
                            # a command Core cannot deliver is recorded, not raised.
                            # A transport that has already gone must not turn into a
                            # run that failed for an unrelated reason.
                            if answer is on_input_release:
                                progress.release_failed = True
                            else:
                                progress.connection_cancel_failed = True
            finally:
                branches_done = list(branches)
                for task in (reader, client, *branches_done):
                    task.cancel()
                # A cancelled watcher may be blocked in a thread the caller owns;
                # gather with return_exceptions so this wait cannot hang or raise
                # before the transport is closed.
                await asyncio.gather(reader, client, *branches_done, return_exceptions=True)

            if reader in finished:
                error = reader.exception()
                if isinstance(error, IpcProtocolError):
                    # The Bridge broke the negotiated contract. Anything else is a
                    # bug in this process and must not be folded into a network
                    # outcome, so it propagates and the CLI reports an internal
                    # invariant.
                    _wind_down(session, failed=True)
                    outcome = SessionOutcome.BRIDGE_LOST
                elif error is not None:
                    # A payload, state-machine, or callback failure is a Core
                    # invariant error, not a normal client exit. Preserve the
                    # original exception and traceback for the CLI boundary.
                    raise error
                else:
                    raise RuntimeError("Bridge event reader stopped without a terminal outcome")
            else:
                _wind_down(session, failed=False)
                outcome = SessionOutcome.CLIENT_EXITED
    finally:
        # §13: invalidate the generation before the transport stops, so a late
        # report from the closed socket cannot advance a session that is
        # already winding down.
        active = connections.active
        # Read *before* the close: how the attempt ended is part of the report,
        # and after the generation is closed there is no attempt left to ask.
        connection_state = None if active is None else active.state
        if active is not None:
            connections.close(active.generation)
        if on_wind_down is not None:
            try:
                await on_wind_down()
            except (OSError, RuntimeError):
                progress.release_failed = True
        await host.close()

    return _report(outcome, session, connection_state, progress)


async def _awaited(moment: Callable[[], Awaitable[object]]) -> None:
    """Adapt a caller's awaitable to the `None` this module waits on.

    The caller owns *when* its moment arrives — a client exiting, a lease
    lapsing, a deadline passing — and returns something this module has no use
    for. Only the timing is shared, so only the timing is adapted.
    """

    await moment()


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
    on_playable: Callable[[], Awaitable[None]] | None,
    recorded: RecordedSessionMaterial | None,
) -> None:
    """Apply every reported phase until the channel ends or the run is cancelled."""

    playable_reported = False
    while True:
        event = await host.receive_event()
        message = event.message
        if isinstance(message, observation_pb2.InitialObservation):
            await _admit_first_snapshot(
                message, session, connections, progress, on_connection, recorded
            )
            # Once, and on the transition rather than on the state: a second
            # snapshot is not a second session starting to walk, and a hook that
            # fired per snapshot would send the command again each time.
            if (
                not playable_reported
                and on_playable is not None
                and session.state is SessionState.PLAYABLE
            ):
                playable_reported = True
                await on_playable()
            continue
        if isinstance(message, control_pb2.ActionResult):
            if message.status == control_pb2.ACTION_STATUS_ACCEPTED:
                progress.actions_applied += 1
            else:
                progress.actions_refused += 1
            continue
        if isinstance(message, observation_pb2.HostLifecycle):
            reported = lan_publication(message)
            if reported is None:
                # A phase this build does not know is not a fact it may record:
                # "published on port X" is what a joiner acts on.
                progress.ignored += 1
            else:
                progress.lan_publication = reported
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


def lan_publication(lifecycle: observation_pb2.HostLifecycle) -> dict[str, object] | None:
    """The Bridge's report as the run document keeps it, or None if it says nothing.

    The phase travels as the wire enum's own word without its prefix, the way the
    connection phases do: a stable token that does not change when somebody renames
    an enum value's spelling.
    """

    phase = _LAN_PHASES.get(lifecycle.phase)
    if phase is None:
        return None
    return {"phase": phase, "port": int(lifecycle.bound_port)}


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
    connection_state: ConnectionState | None,
    progress: _Progress,
) -> SessionRun:
    return SessionRun(
        outcome=outcome,
        session_state=session.state,
        connection_state=connection_state,
        events_applied=progress.applied,
        events_ignored=progress.ignored,
        snapshots_admitted=progress.snapshots_admitted,
        snapshot_rejections=tuple(sorted(progress.snapshot_rejections)),
        entities_admitted=progress.entities_admitted,
        entities_rejected=progress.entities_rejected,
        actions_applied=progress.actions_applied,
        actions_refused=progress.actions_refused,
        release_failed=progress.release_failed,
        connection_cancelled=progress.connection_cancelled,
        connection_cancel_failed=progress.connection_cancel_failed,
        lan_publication=progress.lan_publication,
    )
