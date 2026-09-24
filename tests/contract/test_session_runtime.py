"""The supervised session, against a real loopback Bridge and real machines.

These run the actual host, the actual classifier and the actual session table
together. They cannot say what a real Fabric client would do; they can say that
a session which never gets a handshake, gets a wrong one, or loses its Bridge
ends in the state §7's table allows, and that a session which is driven normally
follows the reported phases to PLAYABLE and stops when the client does.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from bridge_peer import (  # type: ignore[import-not-found]
    close_writers,
    connect,
    envelope,
    hello,
    read_frame,
    session,
    write_frame,
)
from minekin_core.adapters.bridge.ipc import (
    ACTION_RESULT_TYPE,
    BRIDGE_HELLO_TYPE,
    BUDGET_WINDOW_TYPE,
    CONNECTION_LIFECYCLE_TYPE,
    HOST_LIFECYCLE_TYPE,
    INITIAL_OBSERVATION_TYPE,
    RELEASE_ALL_INPUTS_TYPE,
    BridgeIpcHost,
    BridgeSession,
)
from minekin_core.adapters.launcher.offline_session import OFFLINE_SESSION_CANDIDATES
from minekin_core.cli.session_runtime import SessionOutcome, SessionRun, supervise_session
from minekin_core.domain.connection import ConnectionGenerations, ConnectionState
from minekin_core.domain.ids import OpaqueId
from minekin_core.domain.session_material import RecordedSessionMaterial
from minekin_core.domain.session_state import SessionState, SessionStateMachine
from minekin_core.generated.minekin.v1 import (
    control_pb2,
    envelope_pb2,
    observation_pb2,
    session_pb2,
)

# What the Launcher recorded for this Kin. Stated rather than read back from a
# launch: this test drives the runtime directly, so there is no launch to read it
# from — and the snapshot below has to match it, which is the check under test.
RECORDED = RecordedSessionMaterial(
    identity_candidate_id=OFFLINE_SESSION_CANDIDATES[0].candidate_id,
    username="Kin",
    uuid_argv="8f40376b-c23f-3ef1-b553-5564eea75639",
    client_id_present=False,
    xuid_present=False,
)

PROFILE = OpaqueId("local-test")
REVISION = "c" * 64
TERMINAL = frozenset(
    {
        observation_pb2.CONNECTION_PHASE_DISCONNECTED,
        observation_pb2.CONNECTION_PHASE_FAILED,
        observation_pb2.CONNECTION_PHASE_CANCELLED,
    }
)


async def _wait_until(predicate: Callable[[], bool], timeout: float = 3.0) -> None:
    """Poll a condition the other side of the loopback will make true."""

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise TimeoutError("the condition never held")
        await asyncio.sleep(0.005)


async def _note(collected: list[Any], value: Any = True) -> None:
    """An asynchronous callback that records only that it was called, and with what."""

    collected.append(value)


def _in_handshake() -> tuple[SessionStateMachine, ConnectionGenerations]:
    """A session that has started its client and is waiting for the Bridge."""

    machine = SessionStateMachine()
    for target in (
        SessionState.PREPARING,
        SessionState.STARTING_CLIENT,
        SessionState.WAITING_BRIDGE,
        SessionState.HANDSHAKING,
    ):
        machine.advance(target)
    connections = ConnectionGenerations()
    connections.begin(PROFILE, REVISION)
    return machine, connections


class Peer:
    """The managed client's half of the loopback, for one test at a time."""

    def __init__(self, descriptor: session_pb2.BridgeBootstrapDescriptor, bridge: BridgeSession):
        self.descriptor = descriptor
        self.bridge = bridge
        self.control_writer: asyncio.StreamWriter | None = None
        self.event_writer: asyncio.StreamWriter | None = None
        self.core_hello: session_pb2.CoreHello | None = None
        self.sequence = 0

    async def prove(self, *, proof: str | None = None) -> None:
        control_reader, self.control_writer = await connect(
            self.descriptor, envelope_pb2.CHANNEL_CONTROL
        )
        _event_reader, self.event_writer = await connect(
            self.descriptor, envelope_pb2.CHANNEL_EVENT
        )
        await write_frame(
            self.control_writer,
            envelope(
                self.bridge,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                hello(self.bridge, proof=proof).SerializeToString(deterministic=True),
            ),
        )
        core = await asyncio.wait_for(read_frame(control_reader), 2)
        self.core_hello = session_pb2.CoreHello.FromString(core.payload)

    async def snapshot(
        self, *, generation: int = 1, authoritative: bool = True, tick: int = 1
    ) -> None:
        """Send a first snapshot Core should admit, and which the launch agrees with.

        `authoritative` is the one dial a caller turns to keep the identity report
        matching while the snapshot is still refused: what is not an authoritative
        observation is not a perception problem, and a comparison that agrees has to
        reach the record either way.
        """

        assert self.event_writer is not None
        self.sequence += 1
        snapshot = observation_pb2.InitialObservation(
            generation=generation,
            game_tick=tick,
            authoritative=authoritative,
            self=observation_pb2.SelfState(
                health=20.0,
                max_health=20.0,
                food=20,
                saturation=5.0,
                on_ground=True,
                alive=True,
                current_screen="GameMenuScreen",
            ),
            inventory=observation_pb2.InventorySummary(revision=1),
            session_identity=session_pb2.SessionIdentityReport(
                identity_candidate_id=RECORDED.identity_candidate_id,
                session_username=RECORDED.username,
                session_uuid=RECORDED.uuid_argv,
                session_account_type="LEGACY",
                session_client_id_present=RECORDED.client_id_present,
                session_xuid_present=RECORDED.xuid_present,
                credential_values_exposed=False,
            ),
        )
        await write_frame(
            self.event_writer,
            envelope(
                self.bridge,
                INITIAL_OBSERVATION_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                self.sequence,
                snapshot.SerializeToString(deterministic=True),
            ),
        )

    async def report(self, phase: observation_pb2.ConnectionPhase, *, generation: int = 1) -> None:
        assert self.event_writer is not None
        self.sequence += 1
        lifecycle = observation_pb2.ConnectionLifecycle(
            generation=generation,
            server_profile_id=str(PROFILE),
            server_profile_revision=REVISION,
            phase=phase,
            terminal=phase in TERMINAL,
        )
        await write_frame(
            self.event_writer,
            envelope(
                self.bridge,
                CONNECTION_LIFECYCLE_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                self.sequence,
                lifecycle.SerializeToString(deterministic=True),
            ),
        )

    async def report_lan(
        self,
        *,
        port: int = 0,
        phase: observation_pb2.HostPhase = observation_pb2.HOST_PHASE_LAN_OPENED,
    ) -> None:
        """Host-control's report about publishing the world this Kin hosts.

        The management side's own output, produced by the side that is allowed to
        read server truth in order to manage the world — which is why gate 3 does
        not let it become what the Kin knows. The phase is what a caller varies:
        the contract has one failure for this event, and what Core does with an
        incoherent report is a different question from what a Bridge sends.
        """

        assert self.event_writer is not None
        self.sequence += 1
        await write_frame(
            self.event_writer,
            envelope(
                self.bridge,
                HOST_LIFECYCLE_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                self.sequence,
                observation_pb2.HostLifecycle(
                    request_id="open-lan-1",
                    generation=1,
                    phase=phase,
                    bound_port=port,
                ).SerializeToString(deterministic=True),
            ),
        )

    async def report_budget(
        self,
        *,
        label: str = "tick",
        window: int = 1,
        recorded: int = 3,
        micros: tuple[int, ...] = (100, 200, 300),
    ) -> None:
        """One window of the Bridge's own callback budget, as the wire carries it.

        The Bridge's report about itself rather than about the world, which is what
        gate 3 makes management-only: a reader of the run learns what the callbacks
        cost and learns nothing about where the Kin was.
        """

        assert self.event_writer is not None
        self.sequence += 1
        await write_frame(
            self.event_writer,
            envelope(
                self.bridge,
                BUDGET_WINDOW_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                self.sequence,
                observation_pb2.CallbackBudgetWindow(
                    label=label,
                    window=window,
                    opened_at_nanos=window * 10_000_000_000,
                    recorded=recorded,
                    micros=list(micros),
                ).SerializeToString(deterministic=True),
            ),
        )

    async def snapshot_without_identity(self, tick: int) -> None:
        """A snapshot that says nothing about who is running: refused, with reasons."""

        assert self.event_writer is not None
        self.sequence += 1
        await write_frame(
            self.event_writer,
            envelope(
                self.bridge,
                INITIAL_OBSERVATION_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                self.sequence,
                observation_pb2.InitialObservation(
                    generation=1, game_tick=tick, authoritative=True
                ).SerializeToString(deterministic=True),
            ),
        )

    async def action_result(
        self, *, status: control_pb2.ActionStatus, action_id: str = "walk-1"
    ) -> None:
        """The Bridge's answer to one input command."""

        assert self.event_writer is not None
        self.sequence += 1
        await write_frame(
            self.event_writer,
            envelope(
                self.bridge,
                ACTION_RESULT_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                self.sequence,
                control_pb2.ActionResult(
                    action_id=action_id,
                    generation=1,
                    status=status,
                    reason_code=(
                        "" if status == control_pb2.ACTION_STATUS_ACCEPTED else "STALE_GENERATION"
                    ),
                ).SerializeToString(deterministic=True),
            ),
        )

    async def close(self) -> None:
        await close_writers(
            *(writer for writer in (self.control_writer, self.event_writer) if writer is not None)
        )


async def _supervise(
    host: BridgeIpcHost,
    machine: SessionStateMachine,
    connections: ConnectionGenerations,
    *,
    exit_event: asyncio.Event,
    timeout: float = 8.0,
    recorded: RecordedSessionMaterial | None = RECORDED,
    on_playable: Callable[[], Awaitable[None]] | None = None,
    on_wind_down: Callable[[], Awaitable[None]] | None = None,
    until_input_release: Callable[[], Awaitable[object]] | None = None,
    on_input_release: Callable[[], Awaitable[None]] | None = None,
    until_connection_deadline: Callable[[], Awaitable[object]] | None = None,
    on_connection_deadline: Callable[[], Awaitable[None]] | None = None,
    on_session_identity: Callable[[int, Mapping[str, object]], Awaitable[None]] | None = None,
) -> SessionRun:
    return await asyncio.wait_for(
        supervise_session(
            host=host,
            session=machine,
            connections=connections,
            handshake_timeout=3.0,
            until_client_exit=exit_event.wait,
            recorded=recorded,
            on_playable=on_playable,
            on_wind_down=on_wind_down,
            until_input_release=until_input_release,
            on_input_release=on_input_release,
            until_connection_deadline=until_connection_deadline,
            on_connection_deadline=on_connection_deadline,
            on_session_identity=on_session_identity,
        ),
        timeout,
    )


def test_a_session_follows_the_reported_phases_and_stops_with_the_client(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)

        async def client() -> None:
            await peer.prove()
            assert peer.core_hello is not None
            await peer.snapshot_without_identity(tick=1)
            for phase in (
                observation_pb2.CONNECTION_PHASE_RESOLVING,
                observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING,
                observation_pb2.CONNECTION_PHASE_PLAY_INIT,
                observation_pb2.CONNECTION_PHASE_JOIN_SEEN,
            ):
                await peer.report(phase)
            # PLAYABLE is not a phase on that list: it is Core's conclusion about
            # a snapshot it admitted, so the snapshot is what carries the session
            # the rest of the way.
            await peer.snapshot()
            await _wait_until(lambda: machine.state is SessionState.PLAYABLE)
            await peer.report(observation_pb2.CONNECTION_PHASE_DISCONNECTED)
            # Wait for the report to be applied rather than for the state to be
            # READY_MENU, which is where the handshake already left it.
            await _wait_until(
                lambda: (
                    connections.active is not None
                    and connections.active.state is ConnectionState.DISCONNECTED
                )
            )
            assert machine.state is SessionState.READY_MENU
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(host, machine, connections, exit_event=exit_event)
        await running

        assert run.outcome is SessionOutcome.CLIENT_EXITED
        assert run.events_applied == 6
        assert run.events_ignored == 0
        # A snapshot that does not describe the recorded identity is refused, and
        # the refusal says why: this is the difference between a Kin that could not
        # see and one that saw nothing.
        assert "SESSION_MATERIAL_MISMATCH" in run.snapshot_rejections
        assert run.connection_state is ConnectionState.DISCONNECTED
        assert run.session_state is SessionState.STOPPED
        # §13: the attempt is invalidated on the way out, so a late report from
        # the closed channel cannot advance anything.
        assert connections.active is None

    asyncio.run(scenario())


def test_the_session_reaches_playable_before_the_client_leaves(tmp_path: Path) -> None:
    """The phases are not decoration: they are what moves the session."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)
        reached: list[SessionState] = []
        reported: list[ConnectionState] = []
        handshakes: list[bool] = []

        async def client() -> None:
            await peer.prove()
            for phase, expected in (
                (observation_pb2.CONNECTION_PHASE_RESOLVING, SessionState.CONNECTING),
                (observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING, SessionState.CONNECTING),
                (observation_pb2.CONNECTION_PHASE_PLAY_INIT, SessionState.CONNECTING),
                (observation_pb2.CONNECTION_PHASE_JOIN_SEEN, SessionState.JOINED_UNVERIFIED),
            ):
                await peer.report(phase)
                await _wait_until(lambda state=expected: machine.state is state)
                reached.append(machine.state)
            await peer.snapshot()
            await _wait_until(lambda: machine.state is SessionState.PLAYABLE)
            reached.append(machine.state)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        await asyncio.wait_for(
            supervise_session(
                host=host,
                session=machine,
                connections=connections,
                handshake_timeout=3.0,
                until_client_exit=exit_event.wait,
                on_handshake=lambda: _note(handshakes),
                on_connection=lambda state, reason: _note(reported, (state, reason)),
                recorded=RECORDED,
            ),
            8,
        )
        await running

        assert reached == [
            SessionState.CONNECTING,
            SessionState.CONNECTING,
            SessionState.CONNECTING,
            SessionState.JOINED_UNVERIFIED,
            SessionState.PLAYABLE,
        ]
        # The runtime reports every phase the attempt moved to, including the
        # ones that are only progress, and the classification that came with it.
        # Which of them deserve a ledger entry is the caller's question, not this
        # module's — but a failure whose category is dropped on the way is a
        # failure nobody can act on, so the reason travels with the state.
        assert reported == [
            (ConnectionState.RESOLVING, ""),
            (ConnectionState.LOGIN_NEGOTIATING, ""),
            (ConnectionState.PLAY_INIT, ""),
            (ConnectionState.JOIN_SEEN, ""),
            (ConnectionState.PLAYABLE, ""),
        ]
        assert handshakes == [True]

    asyncio.run(scenario())


def test_a_bridge_that_never_arrives_times_out(tmp_path: Path) -> None:
    async def scenario() -> None:
        host = BridgeIpcHost(session())
        await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()

        run = await asyncio.wait_for(
            supervise_session(
                host=host,
                session=machine,
                connections=connections,
                handshake_timeout=0.2,
                until_client_exit=asyncio.Event().wait,
            ),
            5,
        )

        assert run.outcome is SessionOutcome.HANDSHAKE_TIMEOUT
        assert run.events_applied == 0
        assert run.session_state is SessionState.STOPPED

    asyncio.run(scenario())


def test_a_bridge_that_cannot_prove_itself_is_refused(tmp_path: Path) -> None:
    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        peer = Peer(descriptor, bridge)

        running = asyncio.create_task(peer.prove(proof="0" * 64))
        run = await _supervise(host, machine, connections, exit_event=asyncio.Event(), timeout=5.0)
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)

        assert run.outcome is SessionOutcome.HANDSHAKE_FAILED
        assert run.session_state is SessionState.STOPPED

    asyncio.run(scenario())


def test_a_bridge_lost_at_the_menu_stops_the_session_rather_than_failing_it(
    tmp_path: Path,
) -> None:
    """§7 gives READY_MENU no outlet to FAILED, and this is the case it means."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        peer = Peer(descriptor, bridge)

        async def client() -> None:
            await peer.prove()
            # Both sockets go away with no disconnect report, which is the fault
            # the Bridge's own watchdog exists to survive from the other side.
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(host, machine, connections, exit_event=asyncio.Event())
        await running

        assert run.outcome is SessionOutcome.BRIDGE_LOST
        assert run.session_state is SessionState.STOPPED
        assert connections.active is None

    asyncio.run(scenario())


def test_a_rejected_handshake_timeout_is_not_a_positive_window(tmp_path: Path) -> None:
    async def scenario() -> None:
        host = BridgeIpcHost(session())
        await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()

        with pytest.raises(ValueError, match="positive"):
            await supervise_session(
                host=host,
                session=machine,
                connections=connections,
                handshake_timeout=0,
                until_client_exit=asyncio.Event().wait,
            )
        await host.close()

    asyncio.run(scenario())


def test_a_join_that_skips_the_login_phases_fails_the_attempt_closed(tmp_path: Path) -> None:
    """Reporting JOIN without the login phases in between reaches nothing.

    The connection machine only advances PLAY_INIT -> JOIN_SEEN, so a client
    that jumps straight to reporting a join fails its own attempt. This is the
    rule that keeps a JOIN from meaning "some screen said so".
    """

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)

        async def client() -> None:
            await peer.prove()
            await peer.report(observation_pb2.CONNECTION_PHASE_RESOLVING)
            await peer.report(observation_pb2.CONNECTION_PHASE_JOIN_SEEN)
            await _wait_until(lambda: machine.state is SessionState.FAILED)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(host, machine, connections, exit_event=exit_event)
        await running

        assert run.outcome is SessionOutcome.CLIENT_EXITED
        assert run.connection_state is ConnectionState.FAILED
        # FAILED winds down through STOPPING, which §7 allows; it never reaches
        # PLAYABLE, and no input lease could have been granted on the way.
        assert run.session_state is SessionState.STOPPED

    asyncio.run(scenario())


def test_an_internal_event_reader_failure_is_not_reported_as_client_exit() -> None:
    class ExplodingHost:
        closed = False

        async def authenticate(self, _timeout: float) -> object:
            return object()

        async def receive_event(self) -> object:
            raise ValueError("broken event decoder")

        async def close(self) -> None:
            self.closed = True

    async def scenario() -> None:
        host = ExplodingHost()
        machine, connections = _in_handshake()

        with pytest.raises(ValueError, match="broken event decoder"):
            await supervise_session(
                host=host,  # type: ignore[arg-type]
                session=machine,
                connections=connections,
                handshake_timeout=1,
                until_client_exit=asyncio.Event().wait,
            )

        assert host.closed
        assert connections.active is None

    asyncio.run(scenario())


async def _drive_to_playable(peer: Peer, machine: SessionStateMachine) -> None:
    """Prove the session and take it to PLAYABLE, the way a real client does."""

    await peer.prove()
    for phase in (
        observation_pb2.CONNECTION_PHASE_RESOLVING,
        observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING,
        observation_pb2.CONNECTION_PHASE_PLAY_INIT,
        observation_pb2.CONNECTION_PHASE_JOIN_SEEN,
    ):
        await peer.report(phase)
        await _wait_until(lambda: machine.state is not SessionState.CONNECTING)
    await peer.snapshot()
    await _wait_until(lambda: machine.state is SessionState.PLAYABLE)


def test_control_is_offered_once_on_the_transition_and_not_per_snapshot(
    tmp_path: Path,
) -> None:
    """A hook that fired per snapshot would send the command again each time."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)
        offered: list[bool] = []

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            # A second snapshot for a session that is already playable changes
            # nothing, and it is the shape a real client produces when it
            # re-reports. It must not be read as a second session starting.
            await peer.snapshot()
            await asyncio.sleep(0.05)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(
            host,
            machine,
            connections,
            exit_event=exit_event,
            on_playable=lambda: _note(offered),
        )
        await running

        assert offered == [True]
        assert run.outcome is SessionOutcome.CLIENT_EXITED

    asyncio.run(scenario())


def test_an_action_result_is_counted_as_the_bridge_answered(tmp_path: Path) -> None:
    """A refused command and an applied one are different facts about a run."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            await peer.action_result(status=control_pb2.ACTION_STATUS_ACCEPTED)
            await peer.action_result(status=control_pb2.ACTION_STATUS_FAILED)
            await asyncio.sleep(0.05)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(host, machine, connections, exit_event=exit_event)
        await running

        assert run.actions_applied == 1
        assert run.actions_refused == 1
        # Counted as answers, not as unhandled noise: an event this build does
        # not act on is a fact about the run, and these two are acted on.
        assert run.events_ignored == 0
        document = run.as_dict()
        assert document["actions_applied"] == 1
        assert document["input_release_failed"] is False

    asyncio.run(scenario())


def test_a_management_report_does_not_become_what_the_kin_knows(tmp_path: Path) -> None:
    """Gate 3, wired: the control side's output is refused the Kin's model of the world.

    Both classes travel in this run, and the document says which one the Kin was
    allowed to know. The management report is *not* dropped — Core needs it to
    report on the world this Kin hosts, and the run keeps the port — so the claim
    is not that nothing happened. It is that the cognition path took in only the
    snapshot, and that what it refused was counted where a reader can see it.
    """

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            await peer.report_lan(port=25565)
            await asyncio.sleep(0.05)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(host, machine, connections, exit_event=exit_event)
        await running

        document = run.as_dict()

        # What the Kin perceived: the snapshot, and nothing else.
        assert document["perceived_information_class"] == "PLAYER_EQUIVALENT"
        assert document["cognition_refusals"] == {"MANAGEMENT_ONLY_DTO": 1}
        # And the report still reached the document, as a fact about the world
        # rather than as something the Kin knows.
        assert document["lan_publication"] == {"phase": "LAN_OPENED", "port": 25565}

    asyncio.run(scenario())


def test_the_bridges_own_callback_cost_reaches_the_run_document(tmp_path: Path) -> None:
    """W20's measurement, taken from the wire and filed as evidence it can be checked in.

    The contract asks the prototype to record callback wall time and its P50/P95/P99,
    and the stop condition for this phase is tick/render stutter — which is a claim
    nobody can make without the numbers. What this checks is that the numbers have
    somewhere to arrive and a shape to arrive in, and it is deliberately the whole of
    what it checks: no threshold is asserted, because the contract says thresholds
    come after a measurement and this is the measurement being made possible.

    Two facts about the run are asserted here and neither is about the Bridge's code.
    A window that never arrived is a hole in the ordinals, and a series this build
    cannot name is a refusal rather than a series — and both are visible in the
    document rather than inferred from it.
    """

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            for label in ("tick", "tick_interval"):
                for window in (1, 2, 3):
                    await peer.report_budget(
                        label=label,
                        window=window,
                        recorded=100,
                        micros=tuple(range(100)),
                    )
            # Window 4 is built by the Bridge and never delivered, which is what a full
            # outbox leaves behind. Window 5 is the next one it did deliver.
            await peer.report_budget(label="tick", window=5, recorded=1, micros=(4_000,))
            await peer.report_budget(label="tick_interval", window=5, recorded=1, micros=(50_000,))
            # A label this build has never heard of.
            await peer.report_budget(label="render", window=5)
            await asyncio.sleep(0.05)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(host, machine, connections, exit_event=exit_event)
        await running

        document = run.as_dict()
        budgets = cast(dict[str, Any], document["budgets"])
        by_label = cast(dict[str, dict[str, Any]], budgets["series"])
        tick = by_label["tick"]
        interval = by_label["tick_interval"]

        assert budgets["percentile_method"] == "nearest-rank"
        # Four windows for each of the two series arrived; the eighth report named a
        # series this build does not know and is a refusal instead of a series.
        assert budgets["received_windows"] == 8
        assert budgets["report_refusals"] == {"UNKNOWN_LABEL": 1}
        # Window 4 is missing from both series, and that is the whole evidence that the
        # Bridge built it: the ordinals are taken when a window closes, not when it is
        # published, so the delivered ones carry a hole exactly where it was.
        assert tick["missing_windows"] == [4]
        assert interval["missing_windows"] == [4]
        # Three hundreds of samples plus the one from window 5.
        assert tick["recorded_samples"] == 301
        # Nearest-rank over 0..99 three times over, then the single large sample:
        # ceil(0.50 * 301) = 151, so index 150 is 50.
        assert tick["p50"] == 50
        assert tick["maximum_micros"] == 4_000
        assert interval["maximum_micros"] == 50_000
        # The cost of the Bridge's own callbacks did not become what the Kin knows. It
        # is a measurement of this repository's machinery, so it is management-only,
        # and the count is of the gate refusing rather than of a router dropping them.
        # Nine reports travelled and every one of them was refused the Kin's model.
        assert document["perceived_information_class"] == "PLAYER_EQUIVALENT"
        assert document["cognition_refusals"] == {"MANAGEMENT_ONLY_DTO": 9}

    asyncio.run(scenario())


def test_a_refused_snapshot_is_never_the_basis_for_a_lease(tmp_path: Path) -> None:
    """The negative half of the first-snapshot gate, pinned where it can be pinned.

    The contract's gate is "a first snapshot that fails grants no lease", and its
    two halves are already measured separately: the admission filter refuses the
    snapshot with its reasons (the test above), and the arbiter refuses input before
    the world is playable (CORE-040's `input_was_refused_before_the_world_was_playable`,
    measured in a real run). What this adds is the composition: with only a refused
    snapshot, the session never reaches PLAYABLE, so the hook that presents an input
    plan — the one that asks the arbiter for a lease — is never reached at all. The
    run that would need the arbiter to refuse cannot be reached.

    What it still cannot say is that a *real* client can hand over an identity-less
    snapshot; there is no switch for that in the domain, which is why the item stays
    open.
    """

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)
        offered: list[bool] = []

        async def client() -> None:
            await peer.prove()
            for phase in (
                observation_pb2.CONNECTION_PHASE_RESOLVING,
                observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING,
                observation_pb2.CONNECTION_PHASE_PLAY_INIT,
                observation_pb2.CONNECTION_PHASE_JOIN_SEEN,
            ):
                await peer.report(phase)
                await _wait_until(lambda: machine.state is not SessionState.CONNECTING)
            # The only snapshot this session ever gets, and it does not describe the
            # identity the launch recorded.
            await peer.snapshot_without_identity(tick=1)
            await asyncio.sleep(0.05)
            # Seen, and not verified: the state the gate exists to keep it in.
            assert machine.state is SessionState.JOINED_UNVERIFIED
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(
            host, machine, connections, exit_event=exit_event, on_playable=lambda: _note(offered)
        )
        await running

        document = run.as_dict()

        assert offered == [], "nothing asked for input, so nothing could be granted a lease"
        assert run.snapshots_admitted == 0
        assert run.snapshot_rejections, "the refusal is reported rather than silent"
        assert document["actions_applied"] == 0 and document["actions_refused"] == 0

    asyncio.run(scenario())


def test_every_identity_comparison_the_runtime_could_make_reaches_the_caller(
    tmp_path: Path,
) -> None:
    """The record of who the client turned out to be is handed over whatever it says.

    OFFLINE-010/020/030's evidence needs a row per attempt saying what the launch
    claimed and what the client reported, and the claim is only evidence if it
    survives a run that *disagreed*. So the runtime passes the comparison to its
    caller before it acts on the verdict: all three snapshots below go through one
    session — one that reports nothing, one that agrees with the launch and is
    refused anyway for being a non-authoritative observation, and one that is
    admitted — and each produces its own record. The middle case is the one a
    shortcut would miss: a caller that only learned about identity when perception
    succeeded could not tell a client which lied from a client which was not
    looked at.
    """

    async def scenario() -> tuple[list[tuple[int, Mapping[str, object]]], SessionRun]:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)
        compared: list[tuple[int, Mapping[str, object]]] = []

        async def record(generation: int, comparison: Mapping[str, object]) -> None:
            compared.append((generation, comparison))

        async def client() -> None:
            await peer.prove()
            for phase in (
                observation_pb2.CONNECTION_PHASE_RESOLVING,
                observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING,
                observation_pb2.CONNECTION_PHASE_PLAY_INIT,
                observation_pb2.CONNECTION_PHASE_JOIN_SEEN,
            ):
                await peer.report(phase)
                await _wait_until(lambda: machine.state is not SessionState.CONNECTING)
            await peer.snapshot_without_identity(tick=1)
            await _wait_until(lambda: len(compared) == 1)
            await peer.snapshot(tick=2, authoritative=False)
            await _wait_until(lambda: len(compared) == 2)
            await peer.snapshot(tick=3)
            await _wait_until(lambda: machine.state is SessionState.PLAYABLE)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(
            host, machine, connections, exit_event=exit_event, on_session_identity=record
        )
        await running

        return compared, run

    compared, run = asyncio.run(scenario())

    # Two of the three snapshots were refused, and the agreeing comparison below is
    # not one of them turning into an admission: the verdict and the perception
    # filter answered different questions.
    assert run.snapshots_admitted == 1
    assert {"SESSION_MATERIAL_MISMATCH", "NOT_AUTHORITATIVE"} <= set(run.snapshot_rejections)
    # One per snapshot, on the generation the attempt was made under — and not one
    # for the handshake or the join, which say nothing about identity.
    assert [generation for generation, _ in compared] == [1, 1, 1]
    silent, non_authoritative, admitted = (record for _, record in compared)

    # The report-less client is compared field by field rather than summed up as
    # "no identity": an empty report fails on what it leaves out *and* on the two
    # fields that then do not line up, and a reader has to see all three.
    assert silent["matched"] is False
    assert silent["mismatches"] == ["report_incomplete", "username", "uuid"]
    assert silent["session_username"] == "" and silent["session_uuid"] == ""
    # The attribution still names the candidate this launch used, because that is
    # Core's own record and not something the report was asked to echo.
    assert silent["identity_candidate_id"] == RECORDED.identity_candidate_id

    # A snapshot refused for a reason outside identity is compared as agreeing —
    # the two verdicts are about different things and neither may borrow the other.
    assert non_authoritative["matched"] is True
    assert non_authoritative["mismatches"] == []

    assert admitted["matched"] is True
    assert admitted["mismatches"] == []
    assert admitted["session_username"] == RECORDED.username
    assert admitted["session_uuid"] == RECORDED.uuid_argv
    assert admitted["observed_account_type"] == "LEGACY"
    assert admitted["client_id_present"] is False
    assert admitted["xuid_present"] is False
    assert admitted["credential_values_exposed"] is False


def test_a_lan_failure_does_not_end_the_session_or_name_a_port(tmp_path: Path) -> None:
    """HOST-030's second half: being in a world and publishing it are two facts.

    The contract makes "the LAN attempt failed" a separate outcome from "the local
    world started", and the run document is where that separation has to be visible.
    A run whose publish failed goes on to be playable and ends when the client
    leaves — and the publication record carries no port, because a failure that
    named one would claim both that nothing is listening and that something is.
    """

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            await peer.report_lan(phase=observation_pb2.HOST_PHASE_LAN_OPEN_FAILED)
            await asyncio.sleep(0.05)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(host, machine, connections, exit_event=exit_event)
        await running

        document = run.as_dict()

        assert document["lan_publication"] == {"phase": "LAN_OPEN_FAILED", "port": None}
        assert document["host_report_refusals"] == {}, "a coherent failure is recorded"
        # The session went on: the failure was about publishing, not about the world
        # the Kin is in. It was in a playable world before the report arrived, and it
        # ended the way an ordinary run ends — because the client left.
        assert document["snapshots_admitted"] == 1
        assert document["connection_state"] == "PLAYABLE"
        assert run.outcome is SessionOutcome.CLIENT_EXITED
        assert document["session_state"] == "STOPPED"

    asyncio.run(scenario())


def test_a_publication_that_names_no_address_is_counted_rather_than_recorded(
    tmp_path: Path,
) -> None:
    """The writer's side of the rule the joiner's asserter already enforces.

    The Bridge refuses to report this (`LanPublication` has tests of its own), and
    the report arrives over a boundary the contract treats as fallible. The run
    document is what a joiner reads, so "published on port 0" must not reach it —
    and the refusal has to be visible, because a report nobody recorded and a report
    that never arrived look identical from outside.
    """

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            await peer.report_lan(port=0)
            await asyncio.sleep(0.05)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(host, machine, connections, exit_event=exit_event)
        await running

        document = run.as_dict()

        assert document["lan_publication"] is None
        assert document["host_report_refusals"] == {"PORT_NOT_AN_ADDRESS": 1}

    asyncio.run(scenario())


def test_the_wind_down_hook_can_still_reach_the_bridge(tmp_path: Path) -> None:
    """The last chance to speak exists because the transport is still open."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)
        spoke: list[bool] = []

        async def release() -> None:
            await host.send_control(
                RELEASE_ALL_INPUTS_TYPE,
                control_pb2.ReleaseAllInputs(
                    action_id="release-1", generation=1, reason_code="EXPLICIT"
                ),
            )
            spoke.append(True)

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(
            host, machine, connections, exit_event=exit_event, on_wind_down=release
        )
        await running

        assert spoke == [True]
        assert run.release_failed is False

    asyncio.run(scenario())


def test_a_connection_deadline_that_fires_does_not_end_the_run(tmp_path: Path) -> None:
    """The branch the runtime owns: a moment arrives, it is answered, the run goes on."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)
        answered: list[bool] = []

        async def deadline_passed() -> None:
            return None

        async def cancel_it() -> None:
            answered.append(True)

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            # The deadline fired before the client left, and the run is still
            # here to see it: that is the whole claim.
            while not answered:
                await asyncio.sleep(0.01)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(
            host,
            machine,
            connections,
            exit_event=exit_event,
            until_connection_deadline=deadline_passed,
            on_connection_deadline=cancel_it,
        )
        await running

        assert answered == [True]
        assert run.outcome is SessionOutcome.CLIENT_EXITED
        assert run.connection_cancel_failed is False

    asyncio.run(scenario())


def test_a_cancel_that_cannot_be_delivered_is_recorded_rather_than_raised(
    tmp_path: Path,
) -> None:
    """Its own flag: a release and a cancel are two different things Core owed."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)

        async def deadline_passed() -> None:
            return None

        async def failing_cancel() -> None:
            raise OSError("the transport went first")

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(
            host,
            machine,
            connections,
            exit_event=exit_event,
            until_connection_deadline=deadline_passed,
            on_connection_deadline=failing_cancel,
        )
        await running

        assert run.outcome is SessionOutcome.CLIENT_EXITED
        assert run.connection_cancel_failed is True
        assert run.release_failed is False

    asyncio.run(scenario())


def test_a_wind_down_that_cannot_say_goodbye_is_recorded_rather_than_raised(
    tmp_path: Path,
) -> None:
    """The Bridge releases on its own when the channel goes; this is Core's side."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)

        async def failing_release() -> None:
            raise OSError("the transport went first")

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(
            host, machine, connections, exit_event=exit_event, on_wind_down=failing_release
        )
        await running

        # The run ended the way the client ending it ends, and the failed goodbye
        # is a fact in the document rather than an exception over the top of it.
        assert run.outcome is SessionOutcome.CLIENT_EXITED
        assert run.release_failed is True

    asyncio.run(scenario())


def test_a_release_moment_does_not_end_the_run(tmp_path: Path) -> None:
    """A lease lapsing is one more thing in a session, not the end of one."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)
        playable = asyncio.Event()
        fired: list[bool] = []

        async def until_release() -> None:
            await playable.wait()

        async def on_release() -> None:
            fired.append(True)

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            playable.set()
            await _wait_until(lambda: fired == [True])
            # The session is still playable and still supervised: the runtime did
            # what the caller asked and went back to waiting, rather than reading
            # the caller's moment as the client leaving.
            assert machine.state is SessionState.PLAYABLE
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(
            host,
            machine,
            connections,
            exit_event=exit_event,
            until_input_release=until_release,
            on_input_release=on_release,
        )
        await running

        assert fired == [True]
        assert run.outcome is SessionOutcome.CLIENT_EXITED
        assert run.connection_state is ConnectionState.PLAYABLE

    asyncio.run(scenario())


def test_a_release_that_cannot_be_sent_is_recorded_rather_than_raised(tmp_path: Path) -> None:
    """The Bridge releases on its own when the channel goes; this is Core's side."""

    async def scenario() -> None:
        bridge = session()
        host = BridgeIpcHost(bridge)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        machine, connections = _in_handshake()
        exit_event = asyncio.Event()
        peer = Peer(descriptor, bridge)
        playable = asyncio.Event()

        async def until_release() -> None:
            await playable.wait()

        async def failing_release() -> None:
            raise OSError("the control channel went first")

        async def client() -> None:
            await _drive_to_playable(peer, machine)
            playable.set()
            await asyncio.sleep(0.05)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        run = await _supervise(
            host,
            machine,
            connections,
            exit_event=exit_event,
            until_input_release=until_release,
            on_input_release=failing_release,
        )
        await running

        assert run.outcome is SessionOutcome.CLIENT_EXITED
        assert run.release_failed is True

    asyncio.run(scenario())
