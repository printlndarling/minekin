from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Channel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CHANNEL_UNSPECIFIED: _ClassVar[Channel]
    CHANNEL_CONTROL: _ClassVar[Channel]
    CHANNEL_EVENT: _ClassVar[Channel]

class EventSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EVENT_SOURCE_UNSPECIFIED: _ClassVar[EventSource]
    EVENT_SOURCE_CORE: _ClassVar[EventSource]
    EVENT_SOURCE_BRIDGE: _ClassVar[EventSource]
    EVENT_SOURCE_LAUNCHER: _ClassVar[EventSource]
    EVENT_SOURCE_OPERATOR_CLI: _ClassVar[EventSource]
    EVENT_SOURCE_SERVER_ORACLE_TEST_ONLY: _ClassVar[EventSource]

class TrustClass(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRUST_CLASS_UNSPECIFIED: _ClassVar[TrustClass]
    TRUST_CLASS_CORE: _ClassVar[TrustClass]
    TRUST_CLASS_BRIDGE_FILTERED: _ClassVar[TrustClass]
    TRUST_CLASS_LAUNCHER: _ClassVar[TrustClass]
    TRUST_CLASS_OPERATOR: _ClassVar[TrustClass]
    TRUST_CLASS_UNTRUSTED_WORLD_CONTENT: _ClassVar[TrustClass]
CHANNEL_UNSPECIFIED: Channel
CHANNEL_CONTROL: Channel
CHANNEL_EVENT: Channel
EVENT_SOURCE_UNSPECIFIED: EventSource
EVENT_SOURCE_CORE: EventSource
EVENT_SOURCE_BRIDGE: EventSource
EVENT_SOURCE_LAUNCHER: EventSource
EVENT_SOURCE_OPERATOR_CLI: EventSource
EVENT_SOURCE_SERVER_ORACLE_TEST_ONLY: EventSource
TRUST_CLASS_UNSPECIFIED: TrustClass
TRUST_CLASS_CORE: TrustClass
TRUST_CLASS_BRIDGE_FILTERED: TrustClass
TRUST_CLASS_LAUNCHER: TrustClass
TRUST_CLASS_OPERATOR: TrustClass
TRUST_CLASS_UNTRUSTED_WORLD_CONTENT: TrustClass

class ProtocolVersion(_message.Message):
    __slots__ = ("major", "minor")
    MAJOR_FIELD_NUMBER: _ClassVar[int]
    MINOR_FIELD_NUMBER: _ClassVar[int]
    major: int
    minor: int
    def __init__(self, major: _Optional[int] = ..., minor: _Optional[int] = ...) -> None: ...

class Envelope(_message.Message):
    __slots__ = ("protocol", "message_type", "channel", "sequence", "correlation_id", "reply_to", "kin_id", "run_id", "client_instance_id", "session_id", "generation", "world_context_id", "monotonic_ns", "observed_at_utc", "game_tick", "deadline_monotonic_ns", "lease_id", "trace_id", "payload", "event_id", "event_type", "payload_schema_version", "causation_id", "source", "trust_class", "payload_hash")
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    REPLY_TO_FIELD_NUMBER: _ClassVar[int]
    KIN_ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    WORLD_CONTEXT_ID_FIELD_NUMBER: _ClassVar[int]
    MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    OBSERVED_AT_UTC_FIELD_NUMBER: _ClassVar[int]
    GAME_TICK_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_SCHEMA_VERSION_FIELD_NUMBER: _ClassVar[int]
    CAUSATION_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    TRUST_CLASS_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_HASH_FIELD_NUMBER: _ClassVar[int]
    protocol: ProtocolVersion
    message_type: str
    channel: Channel
    sequence: int
    correlation_id: str
    reply_to: str
    kin_id: str
    run_id: str
    client_instance_id: str
    session_id: str
    generation: int
    world_context_id: str
    monotonic_ns: int
    observed_at_utc: str
    game_tick: int
    deadline_monotonic_ns: int
    lease_id: str
    trace_id: str
    payload: bytes
    event_id: str
    event_type: str
    payload_schema_version: int
    causation_id: str
    source: EventSource
    trust_class: TrustClass
    payload_hash: bytes
    def __init__(self, protocol: _Optional[_Union[ProtocolVersion, _Mapping]] = ..., message_type: _Optional[str] = ..., channel: _Optional[_Union[Channel, str]] = ..., sequence: _Optional[int] = ..., correlation_id: _Optional[str] = ..., reply_to: _Optional[str] = ..., kin_id: _Optional[str] = ..., run_id: _Optional[str] = ..., client_instance_id: _Optional[str] = ..., session_id: _Optional[str] = ..., generation: _Optional[int] = ..., world_context_id: _Optional[str] = ..., monotonic_ns: _Optional[int] = ..., observed_at_utc: _Optional[str] = ..., game_tick: _Optional[int] = ..., deadline_monotonic_ns: _Optional[int] = ..., lease_id: _Optional[str] = ..., trace_id: _Optional[str] = ..., payload: _Optional[bytes] = ..., event_id: _Optional[str] = ..., event_type: _Optional[str] = ..., payload_schema_version: _Optional[int] = ..., causation_id: _Optional[str] = ..., source: _Optional[_Union[EventSource, str]] = ..., trust_class: _Optional[_Union[TrustClass, str]] = ..., payload_hash: _Optional[bytes] = ...) -> None: ...
