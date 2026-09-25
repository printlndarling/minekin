"""The Bridge half of the loopback seam, shared by the contract tests.

Kept as plain functions rather than fixtures so a test can call them with
different arguments, and so a failure points at the call rather than at fixture
setup.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import struct
from collections.abc import Collection

from minekin_core.adapters.bridge.ipc import BridgeSession
from minekin_core.generated.minekin.v1 import (
    envelope_pb2,
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
        minecraft_version="1.21.4",
        fabric_loader_version="0.16.9",
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
            bridge_session.minecraft_version,
            bridge_session.fabric_loader_version,
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
        minecraft_version=bridge_session.minecraft_version,
        fabric_loader_version=bridge_session.fabric_loader_version,
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
