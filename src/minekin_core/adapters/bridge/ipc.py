"""Authenticated local IPC host for the thin Minecraft Bridge.

The launcher owns creation of this object and delivers its one-time descriptor
to the managed client.  The public methods deliberately exchange generated
protobuf messages rather than Minecraft or runtime objects.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import struct
import time
from collections.abc import Collection
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from google.protobuf.message import Message

from minekin_core.generated.minekin.v1 import (
    control_pb2,
    envelope_pb2,
    observation_pb2,
    session_pb2,
)

PROTOCOL_MAJOR: Final = 1
PROTOCOL_MINOR: Final = 0
HANDSHAKE_CAPABILITY: Final = "session.handshake.v1"
ADMISSION_CAPABILITY: Final = "admission.connect.v1"
MIN_FRAME_BYTES: Final = 1024
MAX_FRAME_BYTES: Final = 16 * 1024 * 1024
DEFAULT_MAX_FRAME_BYTES: Final = 1024 * 1024
DEFAULT_HEARTBEAT_INTERVAL_MS: Final = 500
BRIDGE_HELLO_TYPE: Final = "minekin.v1.BridgeHello"
CORE_HELLO_TYPE: Final = "minekin.v1.CoreHello"
HEARTBEAT_TYPE: Final = "minekin.v1.Heartbeat"
CONNECT_WORLD_TYPE: Final = "minekin.v1.ConnectWorld"
CANCEL_CONNECTION_TYPE: Final = "minekin.v1.CancelConnection"
CONNECTION_LIFECYCLE_TYPE: Final = "minekin.v1.ConnectionLifecycle"
# Core does not send this yet: the name is pinned here because the Bridge
# handles it and a rename on either side would otherwise be invisible until a
# real client failed to let go of a key.
RELEASE_ALL_INPUTS_TYPE: Final = "minekin.v1.ReleaseAllInputs"
INITIAL_OBSERVATION_TYPE: Final = "minekin.v1.InitialObservation"
_UINT64_MAX: Final = (1 << 64) - 1
_CONTROL_TYPES: Final = frozenset({CONNECT_WORLD_TYPE, CANCEL_CONNECTION_TYPE, HEARTBEAT_TYPE})
_EVENT_TYPES: Final = {
    CONNECTION_LIFECYCLE_TYPE: observation_pb2.ConnectionLifecycle,
    INITIAL_OBSERVATION_TYPE: observation_pb2.InitialObservation,
}


class IpcProtocolError(RuntimeError):
    """An untrusted peer violated the frozen local IPC contract."""


@dataclass(frozen=True, slots=True)
class BridgeSession:
    kin_id: str
    session_id: str
    generation: int
    client_instance_id: str
    bundle_digest: str
    bridge_digest: str
    launch_nonce: bytes
    session_key: bytes
    capabilities: frozenset[str] = frozenset({HANDSHAKE_CAPABILITY, ADMISSION_CAPABILITY})
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES
    heartbeat_interval_ms: int = DEFAULT_HEARTBEAT_INTERVAL_MS

    def __post_init__(self) -> None:
        for value, label in (
            (self.kin_id, "kin_id"),
            (self.session_id, "session_id"),
            (self.client_instance_id, "client_instance_id"),
        ):
            if not value or value.isspace():
                raise ValueError(f"{label} is required")
        for value, label in (
            (self.bundle_digest, "bundle_digest"),
            (self.bridge_digest, "bridge_digest"),
        ):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError(f"{label} must be a lowercase SHA-256 digest")
        if not 1 <= self.generation <= _UINT64_MAX:
            raise ValueError("generation must be a positive uint64")
        if len(self.launch_nonce) != 32 or len(self.session_key) != 32:
            raise ValueError("launch nonce and session key must be 256-bit")
        if HANDSHAKE_CAPABILITY not in self.capabilities or any(
            not capability for capability in self.capabilities
        ):
            raise ValueError("capabilities must contain the handshake capability")
        if not MIN_FRAME_BYTES <= self.max_frame_bytes <= MAX_FRAME_BYTES:
            raise ValueError("max_frame_bytes is outside the reviewed bounds")
        if not 100 <= self.heartbeat_interval_ms <= 10_000:
            raise ValueError("heartbeat interval is outside the reviewed bounds")


@dataclass(frozen=True, slots=True)
class BridgeEvent:
    envelope: envelope_pb2.Envelope
    message: Message


class _EnvelopeStream:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        channel: envelope_pb2.Channel,
        max_frame_bytes: int,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.channel = channel
        self.max_frame_bytes = max_frame_bytes
        self._write_lock = asyncio.Lock()

    async def read(self) -> envelope_pb2.Envelope:
        try:
            header = await self.reader.readexactly(4)
        except asyncio.IncompleteReadError as error:
            raise IpcProtocolError("IPC channel closed before a complete frame header") from error
        length = struct.unpack(">I", header)[0]
        if not 1 <= length <= self.max_frame_bytes:
            raise IpcProtocolError("IPC frame length is outside the configured bound")
        try:
            payload = await self.reader.readexactly(length)
        except asyncio.IncompleteReadError as error:
            raise IpcProtocolError("IPC channel closed with a partial frame") from error
        envelope = envelope_pb2.Envelope()
        try:
            envelope.ParseFromString(payload)
        except Exception as error:
            raise IpcProtocolError("IPC frame is not a protobuf envelope") from error
        if envelope.channel != self.channel:
            raise IpcProtocolError("framed envelope uses the wrong IPC channel")
        return envelope

    async def write(self, envelope: envelope_pb2.Envelope) -> None:
        if envelope.channel != self.channel:
            raise ValueError("envelope is assigned to the wrong IPC channel")
        payload = envelope.SerializeToString(deterministic=True)
        if not 1 <= len(payload) <= self.max_frame_bytes:
            raise IpcProtocolError("serialized IPC frame is outside the configured bound")
        async with self._write_lock:
            self.writer.write(struct.pack(">I", len(payload)) + payload)
            await self.writer.drain()

    async def close(self) -> None:
        self.writer.close()
        # Proactor transports on Windows can leave wait_closed pending while a
        # peer process is wedged. Shutdown must remain bounded even then.
        with suppress(asyncio.TimeoutError, ConnectionError, RuntimeError):
            await asyncio.wait_for(self.writer.wait_closed(), 1.0)


class BridgeIpcHost:
    """Own two loopback listeners and one authenticated Bridge session."""

    def __init__(
        self,
        session: BridgeSession,
        *,
        event_queue_capacity: int = 32,
    ) -> None:
        if event_queue_capacity < 1:
            raise ValueError("event_queue_capacity must be positive")
        self.session = session
        self._events: asyncio.Queue[BridgeEvent | BaseException] = asyncio.Queue(
            event_queue_capacity
        )
        self._control_server: asyncio.Server | None = None
        self._event_server: asyncio.Server | None = None
        self._control_future: asyncio.Future[_EnvelopeStream] | None = None
        self._event_future: asyncio.Future[_EnvelopeStream] | None = None
        self._control: _EnvelopeStream | None = None
        self._event: _EnvelopeStream | None = None
        self._event_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        # Heartbeats and application commands share one sender-side sequence.
        # The stream lock serialises bytes, not sequence allocation, so this
        # lock must cover allocation, write, and increment together.
        self._control_send_lock = asyncio.Lock()
        self._control_sequence = 1
        self._event_sequence = 1
        self._closed = False
        self._authenticated = False

    async def prepare(self, descriptor_path: Path) -> session_pb2.BridgeBootstrapDescriptor:
        """Bind loopback endpoints and exclusively write the one-time descriptor."""

        if self._control_server is not None or self._closed:
            raise RuntimeError("IPC host may be prepared exactly once")
        loop = asyncio.get_running_loop()
        self._control_future = loop.create_future()
        self._event_future = loop.create_future()
        self._control_server = await asyncio.start_server(
            lambda reader, writer: self._accept(reader, writer, envelope_pb2.CHANNEL_CONTROL),
            "127.0.0.1",
            0,
            limit=self.session.max_frame_bytes + 4,
        )
        try:
            self._event_server = await asyncio.start_server(
                lambda reader, writer: self._accept(reader, writer, envelope_pb2.CHANNEL_EVENT),
                "127.0.0.1",
                0,
                limit=self.session.max_frame_bytes + 4,
            )
            descriptor = self._descriptor()
            _write_descriptor_once(descriptor_path, descriptor)
            return descriptor
        except BaseException:
            await self.close()
            raise

    async def authenticate(self, timeout: float = 5.0) -> session_pb2.BridgeHello:
        """Accept both channels and complete the single-use control handshake."""

        if self._control_future is None or self._event_future is None:
            raise RuntimeError("prepare must run before authenticate")
        if self._authenticated:
            raise RuntimeError("Bridge session is already authenticated")
        try:
            control, event = await asyncio.wait_for(
                asyncio.gather(self._control_future, self._event_future), timeout
            )
            self._control, self._event = control, event
            envelope = await asyncio.wait_for(control.read(), timeout)
            self._validate_envelope(
                envelope,
                channel=envelope_pb2.CHANNEL_CONTROL,
                sequence=1,
                allowed_types={BRIDGE_HELLO_TYPE},
            )
            hello = session_pb2.BridgeHello.FromString(envelope.payload)
            accepted = self._validate_bridge_hello(hello)
            core_hello = self._core_hello(accepted)
            await asyncio.wait_for(
                self._send_control(CORE_HELLO_TYPE, core_hello, reply_to=envelope.correlation_id),
                timeout,
            )
            self._authenticated = True
            self._event_task = asyncio.create_task(self._read_events(), name="minekin-ipc-events")
            self._heartbeat_task = asyncio.create_task(
                self._send_heartbeats(), name="minekin-ipc-heartbeats"
            )
            return hello
        except BaseException:
            await self.close()
            raise

    async def send_control(self, message_type: str, message: Message) -> None:
        if not self._authenticated:
            raise RuntimeError("Bridge session is not authenticated")
        if message_type not in _CONTROL_TYPES - {HEARTBEAT_TYPE}:
            raise ValueError("control message type is not admitted")
        expected_type: type[Message]
        if message_type == CONNECT_WORLD_TYPE:
            expected_type = control_pb2.ConnectWorld
        else:
            expected_type = control_pb2.CancelConnection
        if not isinstance(message, expected_type):
            raise TypeError(f"{message_type} payload has the wrong protobuf type")
        if ADMISSION_CAPABILITY not in self.session.capabilities:
            raise RuntimeError("admission capability was not negotiated")
        await self._send_control(message_type, message)

    async def receive_event(self) -> BridgeEvent:
        if not self._authenticated:
            raise RuntimeError("Bridge session is not authenticated")
        item = await self._events.get()
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        streams = {stream for stream in (self._control, self._event) if stream is not None}
        for future in (self._control_future, self._event_future):
            if future is not None and future.done() and not future.cancelled():
                with suppress(BaseException):
                    streams.add(future.result())
        for task in (self._heartbeat_task, self._event_task):
            if task is not None:
                task.cancel()
        # Close transports before awaiting reader tasks. On Windows a pending
        # Proactor read is not guaranteed to finish from cancellation alone.
        for stream in streams:
            stream.writer.close()
        tasks = [task for task in (self._heartbeat_task, self._event_task) if task is not None]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for server in (self._control_server, self._event_server):
            if server is not None:
                server.close()
                await server.wait_closed()
        if streams:
            await asyncio.gather(*(stream.close() for stream in streams), return_exceptions=True)

    def _accept(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        channel: envelope_pb2.Channel,
    ) -> None:
        future = (
            self._control_future if channel == envelope_pb2.CHANNEL_CONTROL else self._event_future
        )
        if future is None or future.done() or self._closed:
            writer.close()
            return
        peer = writer.get_extra_info("peername")
        sock = writer.get_extra_info("sockname")
        if not _is_loopback_pair(peer, sock):
            writer.close()
            return
        future.set_result(_EnvelopeStream(reader, writer, channel, self.session.max_frame_bytes))

    def _descriptor(self) -> session_pb2.BridgeBootstrapDescriptor:
        if self._control_server is None or self._event_server is None:
            raise RuntimeError("listeners are not ready")
        control_port = _server_port(self._control_server)
        event_port = _server_port(self._event_server)
        return session_pb2.BridgeBootstrapDescriptor(
            protocol=envelope_pb2.ProtocolVersion(major=PROTOCOL_MAJOR, minor=PROTOCOL_MINOR),
            kin_id=self.session.kin_id,
            session_id=self.session.session_id,
            generation=self.session.generation,
            client_instance_id=self.session.client_instance_id,
            bundle_digest=self.session.bundle_digest,
            bridge_digest=self.session.bridge_digest,
            launch_nonce=self.session.launch_nonce,
            session_key=self.session.session_key,
            advertised_capabilities=[
                session_pb2.Capability(name=name, version=1)
                for name in sorted(self.session.capabilities)
            ],
            endpoints=[
                _tcp_endpoint(envelope_pb2.CHANNEL_CONTROL, control_port),
                _tcp_endpoint(envelope_pb2.CHANNEL_EVENT, event_port),
            ],
            max_frame_bytes=self.session.max_frame_bytes,
        )

    def _validate_bridge_hello(self, hello: session_pb2.BridgeHello) -> frozenset[str]:
        capabilities = _capability_names(hello.capabilities)
        expected_proof = _bridge_proof(self.session)
        valid = (
            hello.HasField("protocol")
            and hello.protocol.major == PROTOCOL_MAJOR
            and hello.protocol.minor == PROTOCOL_MINOR
            and hello.launch_nonce == self.session.launch_nonce.hex()
            and hello.kin_id == self.session.kin_id
            and hello.session_id == self.session.session_id
            and hello.generation == self.session.generation
            and hello.client_instance_id == self.session.client_instance_id
            and hello.bundle_digest == self.session.bundle_digest
            and hello.bridge_digest == self.session.bridge_digest
            and hello.minecraft_version == "1.21.4"
            and hello.fabric_loader_version == "0.16.9"
            and hello.phase == session_pb2.BRIDGE_PHASE_IPC_CONNECTING
            and capabilities == self.session.capabilities
            and len(hello.proof) == 64
            and hmac.compare_digest(hello.proof, expected_proof)
        )
        if not valid:
            raise IpcProtocolError("BridgeHello identity or proof was rejected")
        return capabilities

    def _core_hello(self, accepted: Collection[str]) -> session_pb2.CoreHello:
        proof = _core_proof(self.session, accepted)
        return session_pb2.CoreHello(
            protocol=envelope_pb2.ProtocolVersion(major=PROTOCOL_MAJOR, minor=PROTOCOL_MINOR),
            session_id=self.session.session_id,
            generation=self.session.generation,
            accepted_capabilities=[
                session_pb2.Capability(name=name, version=1) for name in sorted(accepted)
            ],
            heartbeat_interval_ms=self.session.heartbeat_interval_ms,
            max_frame_bytes=self.session.max_frame_bytes,
            proof=proof,
        )

    async def _send_control(
        self,
        message_type: str,
        message: Message,
        *,
        reply_to: str = "",
    ) -> None:
        if self._control is None:
            raise RuntimeError("control channel is not connected")
        async with self._control_send_lock:
            sequence = self._control_sequence
            if sequence > _UINT64_MAX:
                raise IpcProtocolError("control sequence exhausted")
            envelope = self._envelope(
                message_type,
                envelope_pb2.CHANNEL_CONTROL,
                sequence,
                message.SerializeToString(deterministic=True),
                reply_to=reply_to,
            )
            await self._control.write(envelope)
            self._control_sequence += 1

    async def _send_heartbeats(self) -> None:
        interval = self.session.heartbeat_interval_ms / 1000
        try:
            while True:
                await asyncio.sleep(interval)
                heartbeat = session_pb2.Heartbeat(
                    generation=self.session.generation,
                    monotonic_ns=_monotonic_ns(),
                    phase=session_pb2.BRIDGE_PHASE_OBSERVE_ONLY,
                )
                await self._send_control(HEARTBEAT_TYPE, heartbeat)
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._publish_terminal(error)

    async def _read_events(self) -> None:
        if self._event is None:
            raise RuntimeError("event channel is not connected")
        try:
            while True:
                envelope = await self._event.read()
                self._validate_envelope(
                    envelope,
                    channel=envelope_pb2.CHANNEL_EVENT,
                    sequence=self._event_sequence,
                    allowed_types=set(_EVENT_TYPES),
                )
                message_type = _EVENT_TYPES[envelope.message_type]
                message = message_type.FromString(envelope.payload)
                self._events.put_nowait(BridgeEvent(envelope, message))
                self._event_sequence += 1
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._publish_terminal(error)

    def _publish_terminal(self, error: BaseException) -> None:
        try:
            self._events.put_nowait(error)
        except asyncio.QueueFull:
            # A full queue is itself the fault. Replace buffered observations so
            # the consumer cannot mistake stale state for a healthy channel.
            while not self._events.empty():
                self._events.get_nowait()
            self._events.put_nowait(IpcProtocolError("event queue overflowed"))

    def _validate_envelope(
        self,
        envelope: envelope_pb2.Envelope,
        *,
        channel: envelope_pb2.Channel,
        sequence: int,
        allowed_types: set[str],
    ) -> None:
        valid = (
            envelope.HasField("protocol")
            and envelope.protocol.major == PROTOCOL_MAJOR
            and envelope.protocol.minor <= PROTOCOL_MINOR
            and envelope.channel == channel
            and envelope.sequence == sequence
            and envelope.message_type in allowed_types
            and envelope.kin_id == self.session.kin_id
            and envelope.session_id == self.session.session_id
            and envelope.generation == self.session.generation
            and envelope.client_instance_id == self.session.client_instance_id
            and envelope.monotonic_ns > 0
            and bool(envelope.payload)
        )
        if not valid:
            raise IpcProtocolError("IPC envelope violates the negotiated connection")

    def _envelope(
        self,
        message_type: str,
        channel: envelope_pb2.Channel,
        sequence: int,
        payload: bytes,
        *,
        reply_to: str = "",
    ) -> envelope_pb2.Envelope:
        return envelope_pb2.Envelope(
            protocol=envelope_pb2.ProtocolVersion(major=PROTOCOL_MAJOR, minor=PROTOCOL_MINOR),
            message_type=message_type,
            channel=channel,
            sequence=sequence,
            reply_to=reply_to,
            kin_id=self.session.kin_id,
            session_id=self.session.session_id,
            generation=self.session.generation,
            client_instance_id=self.session.client_instance_id,
            monotonic_ns=_monotonic_ns(),
            payload=payload,
        )


def _tcp_endpoint(channel: envelope_pb2.Channel, port: int) -> session_pb2.IpcEndpoint:
    return session_pb2.IpcEndpoint(
        channel=channel,
        transport=session_pb2.ENDPOINT_TRANSPORT_LOOPBACK_TCP,
        host="127.0.0.1",
        port=port,
    )


def _write_descriptor_once(path: Path, descriptor: session_pb2.BridgeBootstrapDescriptor) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor_bytes = descriptor.SerializeToString(deterministic=True)
    descriptor_fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor_fd, "wb", closefd=False) as stream:
            stream.write(descriptor_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            os.chmod(path, 0o600)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        os.close(descriptor_fd)


def _bridge_proof(session: BridgeSession) -> str:
    context = "\0".join(
        (
            "minekin-bridge-hello-v1",
            str(PROTOCOL_MAJOR),
            str(PROTOCOL_MINOR),
            session.kin_id,
            session.session_id,
            str(session.generation),
            session.client_instance_id,
            session.bundle_digest,
            session.bridge_digest,
            "1.21.4",
            "0.16.9",
            ",".join(sorted(session.capabilities)),
            session.launch_nonce.hex(),
        )
    ).encode()
    return hmac.new(session.session_key, context, hashlib.sha256).hexdigest()


def _core_proof(session: BridgeSession, capabilities: Collection[str]) -> bytes:
    context = "\0".join(
        (
            "minekin-core-hello-v1",
            str(PROTOCOL_MAJOR),
            str(PROTOCOL_MINOR),
            session.session_id,
            str(session.generation),
            ",".join(sorted(capabilities)),
            str(session.heartbeat_interval_ms),
            str(session.max_frame_bytes),
            session.launch_nonce.hex(),
        )
    ).encode()
    return hmac.new(session.session_key, context, hashlib.sha256).digest()


def _capability_names(values: Collection[session_pb2.Capability]) -> frozenset[str]:
    names: set[str] = set()
    for value in values:
        if value.version != 1 or not value.name or value.name in names:
            raise IpcProtocolError("capabilities must be unique reviewed v1 names")
        names.add(value.name)
    return frozenset(names)


def _server_port(server: asyncio.Server) -> int:
    sockets = server.sockets
    if not sockets or len(sockets) != 1:
        raise RuntimeError("loopback IPC listener does not own exactly one socket")
    address = cast(tuple[object, ...], sockets[0].getsockname())
    if len(address) < 2 or not isinstance(address[1], int):
        raise RuntimeError("loopback IPC listener has no TCP port")
    return address[1]


def _is_loopback_pair(peer: object, local: object) -> bool:
    peer_address = cast(tuple[object, ...], peer) if isinstance(peer, tuple) else ()
    local_address = cast(tuple[object, ...], local) if isinstance(local, tuple) else ()
    return bool(
        peer_address
        and peer_address[0] == "127.0.0.1"
        and local_address
        and local_address[0] == "127.0.0.1"
    )


def _monotonic_ns() -> int:
    return max(1, time.monotonic_ns())
