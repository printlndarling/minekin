from __future__ import annotations

import asyncio
import struct
from pathlib import Path

import pytest

from bridge_peer import (  # type: ignore[import-not-found]
    close_writers,
    connect,
    core_proof,
    endpoint,
    envelope,
    hello,
    read_frame,
    session,
    write_frame,
)
from minekin_core.adapters.bridge.admission import (
    LifecycleDisposition,
    accept_snapshot,
    apply_lifecycle,
)
from minekin_core.adapters.bridge.ipc import (
    ADMISSION_CAPABILITY,
    BRIDGE_HELLO_TYPE,
    CONNECT_WORLD_TYPE,
    CONNECTION_LIFECYCLE_TYPE,
    CORE_HELLO_TYPE,
    HANDSHAKE_CAPABILITY,
    HEARTBEAT_TYPE,
    LOOK_CAPABILITY,
    LOOK_INPUT_TYPE,
    MOVE_CAPABILITY,
    MOVE_INPUT_TYPE,
    RELEASE_ALL_INPUTS_TYPE,
    USE_CAPABILITY,
    USE_INPUT_TYPE,
    BridgeIpcHost,
    BridgeSession,
    IpcProtocolError,
)
from minekin_core.cli.session import InputPlan
from minekin_core.domain.connection import (
    CallbackDisposition,
    ConnectionGenerations,
    ConnectionState,
)
from minekin_core.domain.ids import Generation, OpaqueId
from minekin_core.domain.input_control import InputLease, InputPriority
from minekin_core.domain.session_state import (
    SessionState,
    SessionStateMachine,
    advance_for_connection,
)
from minekin_core.generated.minekin.v1 import (
    control_pb2,
    envelope_pb2,
    observation_pb2,
    session_pb2,
)

LEASE_DEADLINE = 5_000_000_000


def lease() -> InputLease:
    """One lease authorising everything the plan below asks for."""

    return InputLease(
        lease_id="lease-1",
        generation=Generation(7),
        client_instance_id="client-1",
        issued_monotonic_ns=1,
        deadline_monotonic_ns=LEASE_DEADLINE,
        priority=InputPriority.NORMAL,
        capabilities=frozenset({MOVE_CAPABILITY, LOOK_CAPABILITY, USE_CAPABILITY}),
    )


def test_loopback_handshake_heartbeat_commands_and_events(tmp_path: Path) -> None:
    async def scenario() -> None:
        bridge_session = session()
        host = BridgeIpcHost(bridge_session)
        descriptor_path = tmp_path / "private" / "bridge-bootstrap.pb"
        descriptor = await host.prepare(descriptor_path)
        assert descriptor_path.read_bytes() == descriptor.SerializeToString(deterministic=True)
        assert {value.host for value in descriptor.endpoints} == {"127.0.0.1"}
        assert {value.port for value in descriptor.endpoints} == {
            endpoint(descriptor, envelope_pb2.CHANNEL_CONTROL).port,
            endpoint(descriptor, envelope_pb2.CHANNEL_EVENT).port,
        }
        assert all(value.port > 0 for value in descriptor.endpoints)
        assert {value.name for value in descriptor.advertised_capabilities} == {
            HANDSHAKE_CAPABILITY,
            ADMISSION_CAPABILITY,
            MOVE_CAPABILITY,
            LOOK_CAPABILITY,
            USE_CAPABILITY,
        }

        control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        value = hello(bridge_session)
        await write_frame(
            control_writer,
            envelope(
                bridge_session,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                value.SerializeToString(deterministic=True),
            ),
        )
        authenticated = await host.authenticate()
        assert authenticated == value

        core_envelope = await asyncio.wait_for(read_frame(control_reader), 1)
        assert core_envelope.sequence == 1
        assert core_envelope.message_type == CORE_HELLO_TYPE
        core_hello = session_pb2.CoreHello.FromString(core_envelope.payload)
        accepted = {value.name for value in core_hello.accepted_capabilities}
        assert core_hello.proof == core_proof(
            bridge_session,
            accepted,
            core_hello.heartbeat_interval_ms,
            core_hello.max_frame_bytes,
        )

        heartbeat_envelope = await asyncio.wait_for(read_frame(control_reader), 1)
        assert heartbeat_envelope.sequence == 2
        assert heartbeat_envelope.message_type == HEARTBEAT_TYPE
        heartbeat = session_pb2.Heartbeat.FromString(heartbeat_envelope.payload)
        assert heartbeat.generation == bridge_session.generation
        assert heartbeat.monotonic_ns > 0

        command = control_pb2.ConnectWorld(
            request_id="connect-1",
            generation=1,
            server_profile_id="local-test",
            server_profile_revision="c" * 64,
            original_host="127.0.0.1",
            port=25565,
            resource_pack_policy=control_pb2.RESOURCE_PACK_POLICY_DENY,
            deadline_monotonic_ns=100,
        )
        await host.send_control(CONNECT_WORLD_TYPE, command)
        command_envelope = await asyncio.wait_for(read_frame(control_reader), 1)
        assert command_envelope.sequence == 3
        assert control_pb2.ConnectWorld.FromString(command_envelope.payload) == command

        release = control_pb2.ReleaseAllInputs(
            action_id="release-1", generation=1, reason_code="EXPLICIT"
        )
        await host.send_control(RELEASE_ALL_INPUTS_TYPE, release)
        release_envelope = await asyncio.wait_for(read_frame(control_reader), 1)
        assert release_envelope.sequence == 4
        assert release_envelope.message_type == RELEASE_ALL_INPUTS_TYPE
        assert control_pb2.ReleaseAllInputs.FromString(release_envelope.payload) == release

        lifecycle = observation_pb2.ConnectionLifecycle(
            generation=1,
            server_profile_id="local-test",
            server_profile_revision="c" * 64,
            phase=observation_pb2.CONNECTION_PHASE_RESOLVING,
        )
        await write_frame(
            event_writer,
            envelope(
                bridge_session,
                CONNECTION_LIFECYCLE_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                1,
                lifecycle.SerializeToString(deterministic=True),
            ),
        )
        event = await asyncio.wait_for(host.receive_event(), 1)
        assert event.message == lifecycle
        assert event.envelope.sequence == 1

        await host.close()
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())


def test_bad_bridge_proof_fails_closed(tmp_path: Path) -> None:
    async def scenario() -> None:
        bridge_session = session()
        host = BridgeIpcHost(bridge_session)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        _control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        value = hello(bridge_session, proof="0" * 64)
        await write_frame(
            control_writer,
            envelope(
                bridge_session,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                value.SerializeToString(deterministic=True),
            ),
        )

        with pytest.raises(IpcProtocolError, match="proof was rejected"):
            await host.authenticate()
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())


def test_control_send_rejects_a_message_type_payload_mismatch(tmp_path: Path) -> None:
    async def scenario() -> None:
        bridge_session = session()
        host = BridgeIpcHost(bridge_session)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        _control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        value = hello(bridge_session)
        await write_frame(
            control_writer,
            envelope(
                bridge_session,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                value.SerializeToString(deterministic=True),
            ),
        )
        await host.authenticate()

        with pytest.raises(TypeError, match="wrong protobuf type"):
            await host.send_control(CONNECT_WORLD_TYPE, control_pb2.CancelConnection())

        await host.close()
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())


def test_no_control_command_can_be_sent_before_the_bridge_proves_itself(
    tmp_path: Path,
) -> None:
    """The earliest of the moments an input may not be sent at.

    CORE-050 asks that inputs before the handshake, before the join and before the
    first snapshot are all refused. This is the first of the three and the only one
    no run can reach: before the Bridge has proved its session there is no channel
    to refuse a *command* on, so what refuses is the transport, and it refuses
    every command rather than only the input ones. Asserted for an input and for a
    command that is not one, because a gate that only covers inputs is a gate
    somebody will route around.
    """

    async def scenario() -> None:
        host = BridgeIpcHost(session())
        await host.prepare(tmp_path / "descriptor.pb")

        with pytest.raises(RuntimeError, match="not authenticated"):
            await host.send_control(
                MOVE_INPUT_TYPE,
                control_pb2.MoveInput(action_id="a", lease_id="l", generation=1),
            )
        with pytest.raises(RuntimeError, match="not authenticated"):
            await host.send_control(
                RELEASE_ALL_INPUTS_TYPE,
                control_pb2.ReleaseAllInputs(action_id="a", generation=1),
            )

    asyncio.run(scenario())


def test_every_command_a_plan_can_send_reaches_the_peer(tmp_path: Path) -> None:
    """Whatever a plan can ask for, the host can send.

    Written because the two disagreed: `UseInput` was admitted into the control
    type set, advertised as a capability and bindable on the Bridge, and the
    host's table of payload classes had no entry for it — so a run that used
    something died with a `KeyError` out of the send path, after the movement
    command had already gone out and been recorded. A second copy of the same
    names is one place to add a message and one place to forget it, which is why
    the table is now the only copy; this is the test that would have noticed.
    """

    async def scenario() -> None:
        bridge_session = session()
        host = BridgeIpcHost(bridge_session)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        value = hello(bridge_session)
        await write_frame(
            control_writer,
            envelope(
                bridge_session,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                value.SerializeToString(deterministic=True),
            ),
        )
        await host.authenticate()

        plan = InputPlan(hold_seconds=8.0, use_seconds=8.0, look=True, yaw_degrees=45.0)
        plan.action_id = "action-1"
        commands = plan.commands(lease(), LEASE_DEADLINE)
        # The order is the plan's, and it is stable so that a run's ledger reads
        # in the order the client was told to do things.
        assert [name for _, name, _ in commands] == [
            MOVE_INPUT_TYPE,
            USE_INPUT_TYPE,
            LOOK_INPUT_TYPE,
        ]

        for _, message_type, message in commands:
            await host.send_control(message_type, message)
            frame = await _frame_of_type(control_reader, message_type)
            assert frame.payload == message.SerializeToString(deterministic=True)

        await host.close()
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())


async def _frame_of_type(reader: asyncio.StreamReader, message_type: str) -> envelope_pb2.Envelope:
    """The next control frame of this type, skipping the heartbeats in between."""

    for _ in range(32):
        frame = await asyncio.wait_for(read_frame(reader), 1)
        if frame.message_type == message_type:
            return frame
    raise AssertionError(f"no {message_type} frame arrived")


def test_control_sequence_allocation_is_atomic_across_concurrent_senders() -> None:
    class PausingStream:
        def __init__(self) -> None:
            self.sequences: list[int] = []
            self.first_started = asyncio.Event()
            self.release_first = asyncio.Event()

        async def write(self, value: envelope_pb2.Envelope) -> None:
            self.sequences.append(value.sequence)
            if len(self.sequences) == 1:
                self.first_started.set()
                await self.release_first.wait()

    async def scenario() -> None:
        host = BridgeIpcHost(session())
        stream = PausingStream()
        host._control = stream  # type: ignore[assignment]  # pyright: ignore[reportPrivateUsage]
        first = asyncio.create_task(
            host._send_control(  # pyright: ignore[reportPrivateUsage]
                HEARTBEAT_TYPE, session_pb2.Heartbeat(generation=1)
            )
        )
        await stream.first_started.wait()
        second = asyncio.create_task(
            host._send_control(  # pyright: ignore[reportPrivateUsage]
                HEARTBEAT_TYPE, session_pb2.Heartbeat(generation=1)
            )
        )
        await asyncio.sleep(0)

        assert stream.sequences == [1]
        stream.release_first.set()
        await asyncio.gather(first, second)
        assert stream.sequences == [1, 2]

    asyncio.run(scenario())


def test_oversize_frame_header_is_rejected_before_allocation(tmp_path: Path) -> None:
    async def scenario() -> None:
        bridge_session = session()
        host = BridgeIpcHost(bridge_session)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        _control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        control_writer.write(struct.pack(">I", bridge_session.max_frame_bytes + 1))
        await control_writer.drain()

        with pytest.raises(IpcProtocolError, match="frame length"):
            await host.authenticate()
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())


def test_descriptor_is_exclusive_and_never_overwrites_session_material(tmp_path: Path) -> None:
    async def scenario() -> None:
        descriptor_path = tmp_path / "descriptor.pb"
        descriptor_path.write_bytes(b"do-not-overwrite")
        host = BridgeIpcHost(session())

        with pytest.raises(FileExistsError):
            await host.prepare(descriptor_path)
        assert descriptor_path.read_bytes() == b"do-not-overwrite"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "change",
    [
        {"launch_nonce": b"short"},
        {"session_key": b"short"},
        {"generation": 0},
        {"max_frame_bytes": 100},
        {"heartbeat_interval_ms": 99},
        {"capabilities": frozenset({ADMISSION_CAPABILITY})},
    ],
)
def test_session_configuration_rejects_unsafe_bounds(change: dict[str, object]) -> None:
    values: dict[str, object] = {
        "kin_id": "kin-1",
        "session_id": "session-1",
        "generation": 7,
        "client_instance_id": "client-1",
        "bundle_digest": "a" * 64,
        "bridge_digest": "b" * 64,
        "launch_nonce": b"n" * 32,
        "session_key": b"k" * 32,
    }
    values.update(change)

    with pytest.raises(ValueError):
        BridgeSession(**values)  # type: ignore[arg-type]


def test_reported_phases_drive_the_generation_gated_attempt(tmp_path: Path) -> None:
    """The real host and the real classifier, with nothing hand-written between them.

    The unit tests for the classifier name the wire enums directly. This runs the
    same classifier against bytes that came off the loopback event channel, so a
    renamed or renumbered phase fails here rather than only in a real client run.
    """

    async def scenario() -> None:
        bridge_session = session()
        host = BridgeIpcHost(bridge_session)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        value = hello(bridge_session)
        await write_frame(
            control_writer,
            envelope(
                bridge_session,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                value.SerializeToString(deterministic=True),
            ),
        )
        await host.authenticate()
        await asyncio.wait_for(read_frame(control_reader), 1)

        profile_id = OpaqueId("local-test")
        revision = "c" * 64
        connections = ConnectionGenerations()
        attempt = connections.begin(profile_id, revision)

        # PLAYABLE is deliberately absent: it is not a phase a Bridge reports.
        admission_phases = (
            observation_pb2.CONNECTION_PHASE_RESOLVING,
            observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING,
            observation_pb2.CONNECTION_PHASE_PLAY_INIT,
            observation_pb2.CONNECTION_PHASE_JOIN_SEEN,
        )
        reached: list[ConnectionState] = []
        session_states: list[SessionState] = []
        # A session that has finished its Bridge handshake sits in READY_MENU.
        session_machine = SessionStateMachine()
        for target in (
            SessionState.PREPARING,
            SessionState.STARTING_CLIENT,
            SessionState.WAITING_BRIDGE,
            SessionState.HANDSHAKING,
            SessionState.READY_MENU,
        ):
            session_machine.advance(target)

        async def send_phase(sequence: int, phase: observation_pb2.ConnectionPhase) -> None:
            """Put one report on the wire and apply what comes back off it."""

            lifecycle = observation_pb2.ConnectionLifecycle(
                generation=int(attempt.generation),
                server_profile_id=str(profile_id),
                server_profile_revision=revision,
                phase=phase,
                terminal=phase
                in {
                    observation_pb2.CONNECTION_PHASE_DISCONNECTED,
                    observation_pb2.CONNECTION_PHASE_FAILED,
                    observation_pb2.CONNECTION_PHASE_CANCELLED,
                },
            )
            await write_frame(
                event_writer,
                envelope(
                    bridge_session,
                    CONNECTION_LIFECYCLE_TYPE,
                    envelope_pb2.CHANNEL_EVENT,
                    sequence,
                    lifecycle.SerializeToString(deterministic=True),
                ),
            )
            event = await asyncio.wait_for(host.receive_event(), 1)
            assert isinstance(event.message, observation_pb2.ConnectionLifecycle)
            outcome = apply_lifecycle(connections, event.message)
            assert outcome.disposition is LifecycleDisposition.APPLIED, outcome
            assert outcome.decision is not None
            assert connections.active is not None
            reached.append(connections.active.state)
            advance_for_connection(session_machine, outcome.decision)
            session_states.append(session_machine.state)

        # The host demands a contiguous event sequence, so this also re-checks the
        # ordering rule the Bridge's writer has to satisfy.
        for sequence, phase in enumerate(admission_phases, start=1):
            await send_phase(sequence, phase)

        # The attempt is joined and no further report on this channel can move it:
        # the contract puts the acceptance with the Runtime, so PLAYABLE comes from
        # a snapshot Core validated, not from a phase a Bridge announced.
        decision = accept_snapshot(connections, attempt.generation)
        assert decision.disposition is CallbackDisposition.ADVANCED
        assert connections.active is not None
        reached.append(connections.active.state)
        advance_for_connection(session_machine, decision)
        session_states.append(session_machine.state)

        await send_phase(len(admission_phases) + 1, observation_pb2.CONNECTION_PHASE_DISCONNECTED)

        assert reached == [
            ConnectionState.RESOLVING,
            ConnectionState.LOGIN_NEGOTIATING,
            ConnectionState.PLAY_INIT,
            ConnectionState.JOIN_SEEN,
            ConnectionState.PLAYABLE,
            ConnectionState.DISCONNECTED,
        ]
        # Four admission phases collapse to one session state, so the session only
        # moves when the connection reaches a phase that means something new.
        assert session_states == [
            SessionState.CONNECTING,
            SessionState.CONNECTING,
            SessionState.CONNECTING,
            SessionState.JOINED_UNVERIFIED,
            SessionState.PLAYABLE,
            SessionState.READY_MENU,
        ]

        await host.close()
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())


def test_a_frame_that_stops_halfway_is_refused(tmp_path: Path) -> None:
    """A half frame is a broken channel, not a shorter message.

    The length header is the only thing that says how long a frame is, so a
    channel that ends inside one has to be read as a fault. A reader that returned
    what it had would hand a truncated protobuf upstream, and a truncated protobuf
    parses as a *different message* far more often than it fails to parse — which
    is the difference between a channel that is down and a channel that is lying.
    """

    async def scenario() -> None:
        host = BridgeIpcHost(session())
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        _control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)

        control_writer.write(struct.pack(">I", 256) + b"\x00" * 16)
        await control_writer.drain()
        control_writer.close()

        with pytest.raises(IpcProtocolError, match="partial frame"):
            await host.authenticate()

        await host.close()
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())


def test_a_flood_of_events_fails_closed_rather_than_dropping_them(tmp_path: Path) -> None:
    """A consumer that cannot keep up is told so, and is not handed stale state.

    The queue is bounded, so a Bridge that floods it is a fault rather than a
    memory problem — and what the bound does with the overflow is the part worth
    pinning. It throws away what was buffered and leaves one error behind, because
    a consumer that went on reading would otherwise act on observations from
    before the gap without ever learning that there was one. That is the same
    shape a slow consumer gets: a slow consumer *is* a flood from the other side.
    """

    async def scenario() -> None:
        bridge_session = session()
        host = BridgeIpcHost(bridge_session, event_queue_capacity=2)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        await write_frame(
            control_writer,
            envelope(
                bridge_session,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                hello(bridge_session).SerializeToString(deterministic=True),
            ),
        )
        await host.authenticate()
        await asyncio.wait_for(read_frame(control_reader), 1)

        lifecycle = observation_pb2.ConnectionLifecycle(
            generation=bridge_session.generation,
            server_profile_id="local-test",
            server_profile_revision="c" * 64,
            phase=observation_pb2.CONNECTION_PHASE_RESOLVING,
        )
        for sequence in range(1, 9):
            await write_frame(
                event_writer,
                envelope(
                    bridge_session,
                    CONNECTION_LIFECYCLE_TYPE,
                    envelope_pb2.CHANNEL_EVENT,
                    sequence,
                    lifecycle.SerializeToString(deterministic=True),
                ),
            )

        # Two events fit; the third does not, and what the consumer can read
        # afterwards is the error rather than the two that were waiting.
        delivered = 0
        with pytest.raises(IpcProtocolError, match="event queue overflowed"):
            for _ in range(16):
                await host.receive_event()
                delivered += 1
        assert delivered <= 2

        await host.close()
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())
