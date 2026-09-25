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
from minekin_core.adapters.bridge.session_report import decode_session_identity
from minekin_core.domain.budget import BudgetLedger, read_window
from minekin_core.domain.connection import (
    CallbackDisposition,
    ConnectionGenerations,
    ConnectionState,
)
from minekin_core.domain.host_publication import (
    HostPublicationDecision,
    HostPublicationPhase,
    host_publication,
)
from minekin_core.domain.information_class import admit_to_cognition
from minekin_core.domain.session_material import (
    RecordedSessionMaterial,
    identity_ledger_record,
)
from minekin_core.domain.session_state import (
    SessionState,
    SessionStateMachine,
    connection_transition_target,
)
from minekin_core.generated.minekin.v1 import control_pb2, observation_pb2

# A disposition worth reporting: the attempt moved, or it came to a stop. A
# stale generation is what a reconnect leaves behind and says nothing about the
# connection the session is actually in.
_REPORTED_DISPOSITIONS = frozenset({CallbackDisposition.ADVANCED, CallbackDisposition.FAILED})
TransitionRecorder = Callable[[SessionState, SessionState], Awaitable[None]]


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

    #: The class of the information this run let the Kin perceive, empty when it
    #: perceived none. The contract's third gate says only player-equivalent
    #: information reaches the Kin's own mind; recording the class on the document
    #: is what makes that a fact about a run rather than a claim about the code.
    perceived_information_class: str = ""
    #: What was refused entry to the cognition path, by reason. A management-only
    #: DTO being counted here is the gate working: the control side reported
    #: something and the Kin's model of the world did not take it in.
    cognition_refusals: Mapping[str, int] = field(default_factory=dict[str, int])
    #: Host lifecycle reports that were not recorded, by reason. A report saying the
    #: world is published on a port that is not one is the shape a joiner acts on, so
    #: "it arrived and was refused" is a fact about the run rather than silence.
    host_report_refusals: Mapping[str, int] = field(default_factory=dict[str, int])
    #: What the Bridge's own callbacks cost, aggregated as the windows arrive. The
    #: contract asks the prototype to record callback wall time and its P50/P95/P99;
    #: this is where that measurement stops being a log line and becomes evidence the
    #: bundle can be verified against.
    budgets: Mapping[str, object] = field(default_factory=dict[str, object])

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
            # What the Kin was allowed to know, in the gate's own words, and what
            # the gate kept out of its model of the world. Recorded rather than
            # assumed: "only player-equivalent information reached the mind" is the
            # kind of statement that stays true in the code and stops being true in
            # the runs, and this is the field that would show it.
            "perceived_information_class": self.perceived_information_class,
            "cognition_refusals": dict(self.cognition_refusals),
            # What the Bridge reported about publishing this Kin's world and Core
            # refused to record, by reason. Empty for a run whose reports were all
            # coherent, which is the usual case and not the same as "no report".
            "host_report_refusals": dict(self.host_report_refusals),
            # What the Bridge's own callbacks cost this run. Aggregated rather than
            # raw, so the document does not grow with how long the Kin ran, and
            # carrying the windows that did not arrive as ordinals rather than as a
            # count, so a dropped window is visible in the evidence itself.
            "budgets": dict(self.budgets),
        }


#: The contract's host event set, as the run document spells it. Closed on purpose:
#: a phase Core cannot name is a report it must count rather than believe. The wire
#: numbers are lifted to `domain/host_publication.py`'s tokens here and nowhere else,
#: so the rule about ports is stated without a wire number in it.
_LAN_PHASES: dict[int, HostPublicationPhase] = {
    observation_pb2.HOST_PHASE_LAN_OPENED: HostPublicationPhase.LAN_OPENED,
    observation_pb2.HOST_PHASE_LAN_OPEN_FAILED: HostPublicationPhase.LAN_OPEN_FAILED,
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
    #: The class of what the Kin perceived, and why anything else was kept out of
    #: its model of the world. The gate runs on every event, so these are facts
    #: about the run rather than about the code path that happened to be taken.
    perceived_information_class: str = ""
    cognition_refusals: dict[str, int] = field(default_factory=dict[str, int])
    #: Host lifecycle reports that were not recorded, by reason. A report saying the
    #: world is published on a port that is not one is the shape a joiner would act
    #: on, so it is a fact about the run that it arrived and was refused.
    host_report_refusals: dict[str, int] = field(default_factory=dict[str, int])
    #: The Bridge's own callback budget, folded window by window as it arrives. A
    #: ledger rather than a list because what the document keeps of it is bounded:
    #: one aggregate per label, one ordinal per window that never made it.
    budgets: BudgetLedger = field(default_factory=BudgetLedger)


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
    on_transition: TransitionRecorder | None = None,
    on_playable: Callable[[], Awaitable[None]] | None = None,
    on_resource_pack_policy: Callable[[int, str], Awaitable[None]] | None = None,
    on_session_identity: Callable[[int, Mapping[str, object]], Awaitable[None]] | None = None,
    on_wind_down: Callable[[], Awaitable[None]] | None = None,
    until_input_release: Callable[[], Awaitable[object]] | None = None,
    on_input_release: Callable[[], Awaitable[None]] | None = None,
    until_connection_deadline: Callable[[], Awaitable[object]] | None = None,
    on_connection_deadline: Callable[[], Awaitable[None]] | None = None,
    until_stop_request: Callable[[], Awaitable[object]] | None = None,
    on_stop_request: Callable[[], Awaitable[None]] | None = None,
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

    `on_resource_pack_policy` runs for every accepted report that names the
    resource-pack policy its connection was created with. The runtime does not
    decide what that fact is worth or where it is kept — it is the Bridge's word
    about the client's own connection, and only the caller can say which source to
    record it under.

    `on_session_identity` runs for every first-snapshot comparison the runtime could
    make, with the attempt's generation and the record of what was compared against
    what. It fires whether or not the snapshot was admitted, because a run that read
    the client's identity and refused it and a run that never looked are different
    facts, and only the record itself can tell a reader which one happened. Which
    event and which trust class that record deserves is again the caller's call.

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

    `until_stop_request` and `on_stop_request` are that shape once more, for the
    moment this runtime cannot see coming on its own: an operator in another
    process asking for this run to stop. Nothing about it ends the run either —
    the client is still the thing whose exit ends a run — but it is the last
    moment at which a release can still reach a live Bridge, which is why the
    answer to it is awaited here rather than left to the wind-down.

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
            await _wind_down(session, failed=True, on_transition=on_transition)
            outcome = failure
        else:
            if on_handshake is not None:
                await on_handshake()
            await advance_session(session, SessionState.READY_MENU, on_transition)
            # Before the reader starts, so a command that provokes an immediate
            # report cannot race the task that is supposed to read it.
            if on_ready is not None:
                await on_ready()

            reader = asyncio.create_task(
                _read_events(
                    host,
                    session,
                    connections,
                    progress,
                    on_connection,
                    on_transition,
                    on_playable,
                    recorded,
                    on_resource_pack_policy,
                    on_session_identity,
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
            if until_stop_request is not None and on_stop_request is not None:
                branches[
                    asyncio.create_task(_awaited(until_stop_request), name="minekin-stop-request")
                ] = on_stop_request
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
                            if answer is on_input_release or answer is on_stop_request:
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
                    await _wind_down(session, failed=True, on_transition=on_transition)
                    outcome = SessionOutcome.BRIDGE_LOST
                elif error is not None:
                    # A payload, state-machine, or callback failure is a Core
                    # invariant error, not a normal client exit. Preserve the
                    # original exception and traceback for the CLI boundary.
                    raise error
                else:
                    raise RuntimeError("Bridge event reader stopped without a terminal outcome")
            else:
                await _wind_down(session, failed=False, on_transition=on_transition)
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
    on_transition: TransitionRecorder | None,
    on_playable: Callable[[], Awaitable[None]] | None,
    recorded: RecordedSessionMaterial | None,
    on_resource_pack_policy: Callable[[int, str], Awaitable[None]] | None = None,
    on_session_identity: Callable[[int, Mapping[str, object]], Awaitable[None]] | None = None,
) -> None:
    """Apply every reported phase until the channel ends or the run is cancelled."""

    playable_reported = False
    while True:
        event = await host.receive_event()
        message = event.message
        # The contract's third gate, asked before anything is done with the payload.
        # What the Kin may know is decided by the type the sender declared and not
        # by the shape of the bytes, because a management DTO's own bytes decode as
        # an observation — `tests/unit/test_information_class.py` holds that pair —
        # so a router that recognised observations by their shape would let the
        # control side's reading of the world become the Kin's own.
        #
        # A refusal is counted rather than dropped. Management-only information is
        # still handled below, because Core needs it to report on the world this Kin
        # hosts; what the refusal records is that the Kin's model of the world did
        # not take it in.
        knowledge = admit_to_cognition(event.envelope.message_type)
        if knowledge.refusal is not None:
            reason = knowledge.refusal.value
            progress.cognition_refusals[reason] = progress.cognition_refusals.get(reason, 0) + 1
        if isinstance(message, observation_pb2.InitialObservation):
            if not knowledge.admitted:
                # Unreachable through the table as it stands, and kept because the
                # table is editable: reclassifying the first snapshot must silence
                # the Kin's perception rather than quietly feed it something else.
                continue
            perceived = await _admit_first_snapshot(
                message,
                session,
                connections,
                progress,
                on_connection,
                on_transition,
                recorded,
                on_session_identity,
            )
            # The class is recorded only for a snapshot the filter admitted, so the
            # document says what the Kin was actually allowed to know rather than
            # what it was offered.
            if perceived and knowledge.information_class is not None:
                progress.perceived_information_class = knowledge.information_class.value
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
            publication = lan_publication(message)
            if publication.recorded is None:
                # Counted by reason rather than folded into "ignored": a report this
                # build could not record is either a phase it cannot name or a port
                # that is not one, and those are different findings about the Bridge.
                reason = str(publication.refusal)
                progress.host_report_refusals[reason] = (
                    progress.host_report_refusals.get(reason, 0) + 1
                )
            else:
                progress.lan_publication = publication.recorded.as_document()
            continue
        if isinstance(message, observation_pb2.CallbackBudgetWindow):
            # The Bridge's own cost, reported on a cadence rather than per tick. It
            # is judged before it is recorded for the reason every other report here
            # is: a window this build cannot read is a fact about the run, and once
            # it is folded into a series that fact is indistinguishable from a
            # number somebody measured.
            window, refusal = read_window(message)
            if refusal is not None:
                progress.budgets.refuse(refusal)
            elif window is not None:
                progress.budgets.observe(window)
            continue
        if not isinstance(message, observation_pb2.ConnectionLifecycle):
            # Counted rather than dropped silently: an event type this build
            # does not act on is a fact about the run, not noise.
            progress.ignored += 1
            continue
        outcome = apply_lifecycle(connections, message)
        if outcome.accepted:
            progress.applied += 1
        if (
            outcome.accepted
            and outcome.resource_pack_policy
            and on_resource_pack_policy is not None
        ):
            # The Bridge's own word about the record its client connected with,
            # handed over before anything else is done with the report: a later
            # branch that stops at `decision is None` would otherwise drop it.
            await on_resource_pack_policy(int(message.generation), outcome.resource_pack_policy)
        decision = outcome.decision
        if decision is None:
            continue
        target = connection_transition_target(session, decision)
        if target is not None:
            await advance_session(session, target, on_transition)
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
    on_transition: TransitionRecorder | None,
    recorded: RecordedSessionMaterial | None,
    on_session_identity: Callable[[int, Mapping[str, object]], Awaitable[None]] | None = None,
) -> bool:
    """Let an admitted snapshot, and not a Bridge's word, make an attempt playable.

    The contract puts the acceptance here: the Bridge sends the first
    authoritative snapshot and the Runtime validates it before anything is marked
    PLAYABLE. A snapshot that is not admitted changes nothing and yields no
    entities — it is counted with its reasons rather than dropped, because "the
    Kin could not see" and "the Kin saw nothing" are different facts about a run.

    Returns whether the perception filter admitted the snapshot, which is the one
    thing the caller needs to know about what the Kin perceived. It is not the same
    question as whether the attempt advanced: a snapshot can be admitted and still
    not move an attempt whose generation has closed.

    Whatever the verdict, the comparison itself is handed to `on_session_identity`
    while the report and the record are both in hand.
    """

    attempt = connections.active
    if attempt is None or recorded is None:
        progress.ignored += 1
        return False
    admission = admit_first_snapshot(snapshot, generation=attempt.generation, recorded=recorded)
    if on_session_identity is not None:
        # Handed over before the verdict is acted on, so a snapshot refused for a
        # reason unrelated to identity still leaves the comparison on the record.
        await on_session_identity(
            attempt.generation.value,
            identity_ledger_record(
                recorded,
                decode_session_identity(snapshot.session_identity),
                admission.session,
            ),
        )
    # Counted either way: the filter runs whether or not the snapshot is admitted,
    # and "the Kin proposed six things and could confirm two" is evidence about
    # the world rather than about the verdict.
    progress.entities_rejected += len(admission.visible_world.rejected)
    if not admission.admitted:
        progress.snapshot_rejections.update(reason.value for reason in admission.reasons)
        return False
    decision = accept_snapshot(connections, attempt.generation)
    if decision.disposition is not CallbackDisposition.ADVANCED or decision.current_state is None:
        progress.ignored += 1
        return True
    progress.applied += 1
    progress.snapshots_admitted += 1
    progress.entities_admitted += len(admission.visible_world.accepted)
    await advance_session(session, SessionState.PLAYABLE, on_transition)
    if on_connection is not None:
        await on_connection(decision.current_state, "")
    return True


def lan_publication(lifecycle: observation_pb2.HostLifecycle) -> HostPublicationDecision:
    """The Bridge's report as the run document may keep it, or why it may not.

    The phase travels as a stable token rather than as the wire enum's spelling, the
    way the connection phases do, so that renaming an enum value cannot silently
    change a fact about a world. The decision itself — including the two refusals a
    report can earn on the reading side — is
    `domain/host_publication.host_publication`'s.
    """

    return host_publication(
        phase=_LAN_PHASES.get(lifecycle.phase), bound_port=int(lifecycle.bound_port)
    )


async def _wind_down(
    session: SessionStateMachine,
    *,
    failed: bool,
    on_transition: TransitionRecorder | None,
) -> None:
    """Leave the session in §7's outlets, in the only order the table allows.

    A Bridge lost while the session is merely at the menu is not a failure: the
    frozen table gives READY_MENU no outlet to FAILED, because a client sitting
    in the menu whose control channel died is a session to stop, not a session
    that broke. Inside a connection it is a failure, and the table agrees.
    """

    if failed and session.can_advance(SessionState.FAILED):
        await advance_session(session, SessionState.FAILED, on_transition)
    if session.can_advance(SessionState.STOPPING):
        await advance_session(session, SessionState.STOPPING, on_transition)
    if session.can_advance(SessionState.STOPPED):
        await advance_session(session, SessionState.STOPPED, on_transition)


async def advance_session(
    session: SessionStateMachine,
    target: SessionState,
    on_transition: TransitionRecorder | None,
) -> SessionState:
    """Persist a validated transition before applying it in memory.

    Shielding the append closes the cancellation window: if cancellation arrives
    after SQLite commits, the in-memory machine is advanced before cancellation
    propagates, so a durable fact never describes a move this process skipped.
    """

    source = session.validate_advance(target)
    if on_transition is not None:
        append = asyncio.ensure_future(on_transition(source, target))
        try:
            await asyncio.shield(append)
        except asyncio.CancelledError:
            await append
            session.advance(target)
            raise
    session.advance(target)
    return source


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
        perceived_information_class=progress.perceived_information_class,
        cognition_refusals=dict(progress.cognition_refusals),
        host_report_refusals=dict(progress.host_report_refusals),
        budgets=progress.budgets.as_document(),
    )
