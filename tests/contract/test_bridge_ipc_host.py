from __future__ import annotations

import asyncio
import hashlib
import hmac
import struct
from collections.abc import Collection
from pathlib import Path

import pytest

from minekin_core.adapters.bridge.ipc import (
    ADMISSION_CAPABILITY,
    HANDSHAKE_CAPABILITY,
    BridgeIpcHost,
    BridgeSession,
    IpcProtocolError,
)
from minekin_core.generated.minekin.v1 import (
    control_pb2,
    envelope_pb2,
    observation_pb2,
    session_pb2,
)


def session() -> BridgeSession:
    return BridgeSession(
        kin_id="kin-1",
        session_id="session-1",
        generation=7,
        client_instance_id="client-1",
        bundle_digest="a" * 64,
        bridge_digest="b" * 64,
        launch_nonce=b"n" * 32,
        session_key=b"k" * 32,
        heartbeat_interval_ms=100,
    )


def endpoint(
    descriptor: session_pb2.BridgeBootstrapDescriptor, channel: envelope_pb2.Channel
) -> session_pb2.IpcEndpoint:
    return next(value for value in descriptor.endpoints if value.channel == channel)


async def connect(
    descriptor: session_pb2.BridgeBootstrapDescriptor, channel: envelope_pb2.Channel
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    value = endpoint(descriptor, channel)
    return await asyncio.open_connection(value.host, value.port)


async def write_frame(writer: asyncio.StreamWriter, envelope: envelope_pb2.Envelope) -> None:
    payload = envelope.SerializeToString(deterministic=True)
    writer.write(struct.pack(">I", len(payload)) + payload)
    await writer.drain()


async def read_frame(reader: asyncio.StreamReader) -> envelope_pb2.Envelope:
    length = struct.unpack(">I", await reader.readexactly(4))[0]
    return envelope_pb2.Envelope.FromString(await reader.readexactly(length))


def envelope(
    bridge_session: BridgeSession,
    message_type: str,
    channel: envelope_pb2.Channel,
    sequence: int,
    payload: bytes,
) -> envelope_pb2.Envelope:
    return envelope_pb2.Envelope(
        protocol=envelope_pb2.ProtocolVersion(major=1, minor=0),
        message_type=message_type,
        channel=channel,
        sequence=sequence,
        kin_id=bridge_session.kin_id,
        session_id=bridge_session.session_id,
        generation=bridge_session.generation,
        client_instance_id=bridge_session.client_instance_id,
        monotonic_ns=1,
        payload=payload,
    )


def bridge_proof(bridge_session: BridgeSession) -> str:
    context = "\0".join(
        (
            "minekin-bridge-hello-v1",
            "1",
            "0",
            bridge_session.kin_id,
            bridge_session.session_id,
            str(bridge_session.generation),
            bridge_session.client_instance_id,
            bridge_session.bundle_digest,
            bridge_session.bridge_digest,
            "1.21.4",
            "0.16.9",
            ",".join(sorted(bridge_session.capabilities)),
            bridge_session.launch_nonce.hex(),
        )
    ).encode()
    return hmac.new(bridge_session.session_key, context, hashlib.sha256).hexdigest()


def hello(bridge_session: BridgeSession, *, proof: str | None = None) -> session_pb2.BridgeHello:
    return session_pb2.BridgeHello(
        protocol=envelope_pb2.ProtocolVersion(major=1, minor=0),
        launch_nonce=bridge_session.launch_nonce.hex(),
        proof=bridge_proof(bridge_session) if proof is None else proof,
        kin_id=bridge_session.kin_id,
        session_id=bridge_session.session_id,
        generation=bridge_session.generation,
        client_instance_id=bridge_session.client_instance_id,
        bundle_digest=bridge_session.bundle_digest,
        bridge_digest=bridge_session.bridge_digest,
        minecraft_version="1.21.4",
        fabric_loader_version="0.16.9",
        capabilities=[
            session_pb2.Capability(name=name, version=1)
            for name in sorted(bridge_session.capabilities)
        ],
        phase=session_pb2.BRIDGE_PHASE_IPC_CONNECTING,
    )


def core_proof(
    bridge_session: BridgeSession,
    capabilities: Collection[str],
    heartbeat_ms: int,
    frame_bytes: int,
) -> bytes:
    context = "\0".join(
        (
            "minekin-core-hello-v1",
            "1",
            "0",
            bridge_session.session_id,
            str(bridge_session.generation),
            ",".join(sorted(capabilities)),
            str(heartbeat_ms),
            str(frame_bytes),
            bridge_session.launch_nonce.hex(),
        )
    ).encode()
    return hmac.new(bridge_session.session_key, context, hashlib.sha256).digest()


async def close_writers(*writers: asyncio.StreamWriter) -> None:
    for writer in writers:
        writer.close()
    await asyncio.gather(*(writer.wait_closed() for writer in writers), return_exceptions=True)


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
        }

        control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        value = hello(bridge_session)
        await write_frame(
            control_writer,
            envelope(
                bridge_session,
                "BridgeHello",
                envelope_pb2.CHANNEL_CONTROL,
                1,
                value.SerializeToString(deterministic=True),
            ),
        )
        authenticated = await host.authenticate()
        assert authenticated == value

        core_envelope = await asyncio.wait_for(read_frame(control_reader), 1)
        assert core_envelope.sequence == 1
        assert core_envelope.message_type == "CoreHello"
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
        assert heartbeat_envelope.message_type == "Heartbeat"
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
        await host.send_control("ConnectWorld", command)
        command_envelope = await asyncio.wait_for(read_frame(control_reader), 1)
        assert command_envelope.sequence == 3
        assert control_pb2.ConnectWorld.FromString(command_envelope.payload) == command

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
                "ConnectionLifecycle",
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
                "BridgeHello",
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
                "BridgeHello",
                envelope_pb2.CHANNEL_CONTROL,
                1,
                value.SerializeToString(deterministic=True),
            ),
        )
        await host.authenticate()

        with pytest.raises(TypeError, match="wrong protobuf type"):
            await host.send_control("ConnectWorld", control_pb2.CancelConnection())

        await host.close()
        await close_writers(control_writer, event_writer)

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
