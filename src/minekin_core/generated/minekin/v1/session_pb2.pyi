from minekin_core.generated.minekin.v1 import envelope_pb2 as _envelope_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BridgePhase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BRIDGE_PHASE_UNSPECIFIED: _ClassVar[BridgePhase]
    BRIDGE_PHASE_MOD_LOADED: _ClassVar[BridgePhase]
    BRIDGE_PHASE_IPC_CONNECTING: _ClassVar[BridgePhase]
    BRIDGE_PHASE_OBSERVE_ONLY: _ClassVar[BridgePhase]
    BRIDGE_PHASE_CONNECTING_WORLD: _ClassVar[BridgePhase]
    BRIDGE_PHASE_PLAYABLE: _ClassVar[BridgePhase]
    BRIDGE_PHASE_SAFE_STOP: _ClassVar[BridgePhase]

class EndpointTransport(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ENDPOINT_TRANSPORT_UNSPECIFIED: _ClassVar[EndpointTransport]
    ENDPOINT_TRANSPORT_UNIX_DOMAIN_SOCKET: _ClassVar[EndpointTransport]
    ENDPOINT_TRANSPORT_LOOPBACK_TCP: _ClassVar[EndpointTransport]
BRIDGE_PHASE_UNSPECIFIED: BridgePhase
BRIDGE_PHASE_MOD_LOADED: BridgePhase
BRIDGE_PHASE_IPC_CONNECTING: BridgePhase
BRIDGE_PHASE_OBSERVE_ONLY: BridgePhase
BRIDGE_PHASE_CONNECTING_WORLD: BridgePhase
BRIDGE_PHASE_PLAYABLE: BridgePhase
BRIDGE_PHASE_SAFE_STOP: BridgePhase
ENDPOINT_TRANSPORT_UNSPECIFIED: EndpointTransport
ENDPOINT_TRANSPORT_UNIX_DOMAIN_SOCKET: EndpointTransport
ENDPOINT_TRANSPORT_LOOPBACK_TCP: EndpointTransport

class Capability(_message.Message):
    __slots__ = ("name", "version")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    name: str
    version: int
    def __init__(self, name: _Optional[str] = ..., version: _Optional[int] = ...) -> None: ...

class BridgeHello(_message.Message):
    __slots__ = ("protocol", "launch_nonce", "proof", "kin_id", "session_id", "generation", "client_instance_id", "bundle_digest", "bridge_digest", "minecraft_version", "fabric_loader_version", "capabilities", "phase")
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    LAUNCH_NONCE_FIELD_NUMBER: _ClassVar[int]
    PROOF_FIELD_NUMBER: _ClassVar[int]
    KIN_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    CLIENT_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    BUNDLE_DIGEST_FIELD_NUMBER: _ClassVar[int]
    BRIDGE_DIGEST_FIELD_NUMBER: _ClassVar[int]
    MINECRAFT_VERSION_FIELD_NUMBER: _ClassVar[int]
    FABRIC_LOADER_VERSION_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    protocol: _envelope_pb2.ProtocolVersion
    launch_nonce: str
    proof: str
    kin_id: str
    session_id: str
    generation: int
    client_instance_id: str
    bundle_digest: str
    bridge_digest: str
    minecraft_version: str
    fabric_loader_version: str
    capabilities: _containers.RepeatedCompositeFieldContainer[Capability]
    phase: BridgePhase
    def __init__(self, protocol: _Optional[_Union[_envelope_pb2.ProtocolVersion, _Mapping]] = ..., launch_nonce: _Optional[str] = ..., proof: _Optional[str] = ..., kin_id: _Optional[str] = ..., session_id: _Optional[str] = ..., generation: _Optional[int] = ..., client_instance_id: _Optional[str] = ..., bundle_digest: _Optional[str] = ..., bridge_digest: _Optional[str] = ..., minecraft_version: _Optional[str] = ..., fabric_loader_version: _Optional[str] = ..., capabilities: _Optional[_Iterable[_Union[Capability, _Mapping]]] = ..., phase: _Optional[_Union[BridgePhase, str]] = ...) -> None: ...

class CoreHello(_message.Message):
    __slots__ = ("protocol", "session_id", "generation", "accepted_capabilities", "heartbeat_interval_ms", "max_frame_bytes", "proof")
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    MAX_FRAME_BYTES_FIELD_NUMBER: _ClassVar[int]
    PROOF_FIELD_NUMBER: _ClassVar[int]
    protocol: _envelope_pb2.ProtocolVersion
    session_id: str
    generation: int
    accepted_capabilities: _containers.RepeatedCompositeFieldContainer[Capability]
    heartbeat_interval_ms: int
    max_frame_bytes: int
    proof: bytes
    def __init__(self, protocol: _Optional[_Union[_envelope_pb2.ProtocolVersion, _Mapping]] = ..., session_id: _Optional[str] = ..., generation: _Optional[int] = ..., accepted_capabilities: _Optional[_Iterable[_Union[Capability, _Mapping]]] = ..., heartbeat_interval_ms: _Optional[int] = ..., max_frame_bytes: _Optional[int] = ..., proof: _Optional[bytes] = ...) -> None: ...

class Heartbeat(_message.Message):
    __slots__ = ("generation", "monotonic_ns", "phase")
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    generation: int
    monotonic_ns: int
    phase: BridgePhase
    def __init__(self, generation: _Optional[int] = ..., monotonic_ns: _Optional[int] = ..., phase: _Optional[_Union[BridgePhase, str]] = ...) -> None: ...

class IpcEndpoint(_message.Message):
    __slots__ = ("channel", "transport", "unix_socket_path", "host", "port")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    TRANSPORT_FIELD_NUMBER: _ClassVar[int]
    UNIX_SOCKET_PATH_FIELD_NUMBER: _ClassVar[int]
    HOST_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    channel: _envelope_pb2.Channel
    transport: EndpointTransport
    unix_socket_path: str
    host: str
    port: int
    def __init__(self, channel: _Optional[_Union[_envelope_pb2.Channel, str]] = ..., transport: _Optional[_Union[EndpointTransport, str]] = ..., unix_socket_path: _Optional[str] = ..., host: _Optional[str] = ..., port: _Optional[int] = ...) -> None: ...

class BridgeBootstrapDescriptor(_message.Message):
    __slots__ = ("protocol", "kin_id", "session_id", "generation", "client_instance_id", "bundle_digest", "bridge_digest", "launch_nonce", "session_key", "advertised_capabilities", "endpoints", "max_frame_bytes")
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    KIN_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    CLIENT_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    BUNDLE_DIGEST_FIELD_NUMBER: _ClassVar[int]
    BRIDGE_DIGEST_FIELD_NUMBER: _ClassVar[int]
    LAUNCH_NONCE_FIELD_NUMBER: _ClassVar[int]
    SESSION_KEY_FIELD_NUMBER: _ClassVar[int]
    ADVERTISED_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    ENDPOINTS_FIELD_NUMBER: _ClassVar[int]
    MAX_FRAME_BYTES_FIELD_NUMBER: _ClassVar[int]
    protocol: _envelope_pb2.ProtocolVersion
    kin_id: str
    session_id: str
    generation: int
    client_instance_id: str
    bundle_digest: str
    bridge_digest: str
    launch_nonce: bytes
    session_key: bytes
    advertised_capabilities: _containers.RepeatedCompositeFieldContainer[Capability]
    endpoints: _containers.RepeatedCompositeFieldContainer[IpcEndpoint]
    max_frame_bytes: int
    def __init__(self, protocol: _Optional[_Union[_envelope_pb2.ProtocolVersion, _Mapping]] = ..., kin_id: _Optional[str] = ..., session_id: _Optional[str] = ..., generation: _Optional[int] = ..., client_instance_id: _Optional[str] = ..., bundle_digest: _Optional[str] = ..., bridge_digest: _Optional[str] = ..., launch_nonce: _Optional[bytes] = ..., session_key: _Optional[bytes] = ..., advertised_capabilities: _Optional[_Iterable[_Union[Capability, _Mapping]]] = ..., endpoints: _Optional[_Iterable[_Union[IpcEndpoint, _Mapping]]] = ..., max_frame_bytes: _Optional[int] = ...) -> None: ...
