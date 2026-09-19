"""The supervised session, against a real loopback Bridge and real machines.

These run the actual host, the actual classifier and the actual session table
together. They cannot say what a real Fabric client would do; they can say that
a session which never gets a handshake, gets a wrong one, or loses its Bridge
ends in the state §7's table allows, and that a session which is driven normally
follows the reported phases to PLAYABLE and stops when the client does.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

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
    BRIDGE_HELLO_TYPE,
    CONNECTION_LIFECYCLE_TYPE,
    BridgeIpcHost,
    BridgeSession,
)
from minekin_core.cli.session_runtime import SessionOutcome, SessionRun, supervise_session
from minekin_core.domain.connection import ConnectionGenerations, ConnectionState
from minekin_core.domain.ids import OpaqueId
from minekin_core.domain.session_state import SessionState, SessionStateMachine
from minekin_core.generated.minekin.v1 import envelope_pb2, observation_pb2, session_pb2

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

    async def observe(self, tick: int) -> None:
        """An event type this build receives but does not act on."""

        assert self.event_writer is not None
        self.sequence += 1
        await write_frame(
            self.event_writer,
            envelope(
                self.bridge,
                "minekin.v1.InitialObservation",
                envelope_pb2.CHANNEL_EVENT,
                self.sequence,
                observation_pb2.InitialObservation(
                    generation=1, game_tick=tick, authoritative=True
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
) -> SessionRun:
    return await asyncio.wait_for(
        supervise_session(
            host=host,
            session=machine,
            connections=connections,
            handshake_timeout=3.0,
            until_client_exit=exit_event.wait,
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
            await peer.observe(tick=1)
            for phase in (
                observation_pb2.CONNECTION_PHASE_RESOLVING,
                observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING,
                observation_pb2.CONNECTION_PHASE_PLAY_INIT,
                observation_pb2.CONNECTION_PHASE_JOIN_SEEN,
                observation_pb2.CONNECTION_PHASE_PLAYABLE,
            ):
                await peer.report(phase)
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
        assert run.events_ignored == 1
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

        async def client() -> None:
            await peer.prove()
            for phase, expected in (
                (observation_pb2.CONNECTION_PHASE_RESOLVING, SessionState.CONNECTING),
                (observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING, SessionState.CONNECTING),
                (observation_pb2.CONNECTION_PHASE_PLAY_INIT, SessionState.CONNECTING),
                (observation_pb2.CONNECTION_PHASE_JOIN_SEEN, SessionState.JOINED_UNVERIFIED),
                (observation_pb2.CONNECTION_PHASE_PLAYABLE, SessionState.PLAYABLE),
            ):
                await peer.report(phase)
                await _wait_until(lambda state=expected: machine.state is state)
                reached.append(machine.state)
            exit_event.set()
            await peer.close()

        running = asyncio.create_task(client())
        await _supervise(host, machine, connections, exit_event=exit_event)
        await running

        assert reached == [
            SessionState.CONNECTING,
            SessionState.CONNECTING,
            SessionState.CONNECTING,
            SessionState.JOINED_UNVERIFIED,
            SessionState.PLAYABLE,
        ]

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
