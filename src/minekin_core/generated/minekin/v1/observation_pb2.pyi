from minekin_core.generated.minekin.v1 import session_pb2 as _session_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ConnectionPhase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CONNECTION_PHASE_UNSPECIFIED: _ClassVar[ConnectionPhase]
    CONNECTION_PHASE_RESOLVING: _ClassVar[ConnectionPhase]
    CONNECTION_PHASE_LOGIN_NEGOTIATING: _ClassVar[ConnectionPhase]
    CONNECTION_PHASE_PLAY_INIT: _ClassVar[ConnectionPhase]
    CONNECTION_PHASE_JOIN_SEEN: _ClassVar[ConnectionPhase]
    CONNECTION_PHASE_PLAYABLE: _ClassVar[ConnectionPhase]
    CONNECTION_PHASE_DISCONNECTED: _ClassVar[ConnectionPhase]
    CONNECTION_PHASE_FAILED: _ClassVar[ConnectionPhase]
    CONNECTION_PHASE_CANCELLED: _ClassVar[ConnectionPhase]

class AdmissionFailureReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ADMISSION_FAILURE_REASON_UNSPECIFIED: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_ADDRESS_INVALID: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_DNS_FAILED: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_ADDRESS_POLICY_BLOCKED: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_CONNECT_TIMEOUT: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_PROTOCOL_MISMATCH: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_WHITELIST_REJECTED: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_RESOURCE_PACK_BLOCKED: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_FIRST_SNAPSHOT_TIMEOUT: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_WORLD_BINDING_MISMATCH: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_CONTROL_LOST: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_CANCELLED: _ClassVar[AdmissionFailureReason]
    ADMISSION_FAILURE_REASON_INTERNAL_INVARIANT: _ClassVar[AdmissionFailureReason]
CONNECTION_PHASE_UNSPECIFIED: ConnectionPhase
CONNECTION_PHASE_RESOLVING: ConnectionPhase
CONNECTION_PHASE_LOGIN_NEGOTIATING: ConnectionPhase
CONNECTION_PHASE_PLAY_INIT: ConnectionPhase
CONNECTION_PHASE_JOIN_SEEN: ConnectionPhase
CONNECTION_PHASE_PLAYABLE: ConnectionPhase
CONNECTION_PHASE_DISCONNECTED: ConnectionPhase
CONNECTION_PHASE_FAILED: ConnectionPhase
CONNECTION_PHASE_CANCELLED: ConnectionPhase
ADMISSION_FAILURE_REASON_UNSPECIFIED: AdmissionFailureReason
ADMISSION_FAILURE_REASON_ADDRESS_INVALID: AdmissionFailureReason
ADMISSION_FAILURE_REASON_DNS_FAILED: AdmissionFailureReason
ADMISSION_FAILURE_REASON_ADDRESS_POLICY_BLOCKED: AdmissionFailureReason
ADMISSION_FAILURE_REASON_CONNECT_TIMEOUT: AdmissionFailureReason
ADMISSION_FAILURE_REASON_PROTOCOL_MISMATCH: AdmissionFailureReason
ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH: AdmissionFailureReason
ADMISSION_FAILURE_REASON_WHITELIST_REJECTED: AdmissionFailureReason
ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN: AdmissionFailureReason
ADMISSION_FAILURE_REASON_RESOURCE_PACK_BLOCKED: AdmissionFailureReason
ADMISSION_FAILURE_REASON_FIRST_SNAPSHOT_TIMEOUT: AdmissionFailureReason
ADMISSION_FAILURE_REASON_WORLD_BINDING_MISMATCH: AdmissionFailureReason
ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT: AdmissionFailureReason
ADMISSION_FAILURE_REASON_CONTROL_LOST: AdmissionFailureReason
ADMISSION_FAILURE_REASON_CANCELLED: AdmissionFailureReason
ADMISSION_FAILURE_REASON_INTERNAL_INVARIANT: AdmissionFailureReason

class ConnectionLifecycle(_message.Message):
    __slots__ = ("generation", "server_profile_id", "server_profile_revision", "phase", "failure_reason", "terminal")
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    SERVER_PROFILE_ID_FIELD_NUMBER: _ClassVar[int]
    SERVER_PROFILE_REVISION_FIELD_NUMBER: _ClassVar[int]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    FAILURE_REASON_FIELD_NUMBER: _ClassVar[int]
    TERMINAL_FIELD_NUMBER: _ClassVar[int]
    generation: int
    server_profile_id: str
    server_profile_revision: str
    phase: ConnectionPhase
    failure_reason: AdmissionFailureReason
    terminal: bool
    def __init__(self, generation: _Optional[int] = ..., server_profile_id: _Optional[str] = ..., server_profile_revision: _Optional[str] = ..., phase: _Optional[_Union[ConnectionPhase, str]] = ..., failure_reason: _Optional[_Union[AdmissionFailureReason, str]] = ..., terminal: bool = ...) -> None: ...

class SelfState(_message.Message):
    __slots__ = ("health", "max_health", "food", "saturation", "on_ground", "alive", "current_screen")
    HEALTH_FIELD_NUMBER: _ClassVar[int]
    MAX_HEALTH_FIELD_NUMBER: _ClassVar[int]
    FOOD_FIELD_NUMBER: _ClassVar[int]
    SATURATION_FIELD_NUMBER: _ClassVar[int]
    ON_GROUND_FIELD_NUMBER: _ClassVar[int]
    ALIVE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SCREEN_FIELD_NUMBER: _ClassVar[int]
    health: float
    max_health: float
    food: int
    saturation: float
    on_ground: bool
    alive: bool
    current_screen: str
    def __init__(self, health: _Optional[float] = ..., max_health: _Optional[float] = ..., food: _Optional[int] = ..., saturation: _Optional[float] = ..., on_ground: bool = ..., alive: bool = ..., current_screen: _Optional[str] = ...) -> None: ...

class InventoryStack(_message.Message):
    __slots__ = ("slot", "item_id", "count", "damage")
    SLOT_FIELD_NUMBER: _ClassVar[int]
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    DAMAGE_FIELD_NUMBER: _ClassVar[int]
    slot: int
    item_id: str
    count: int
    damage: int
    def __init__(self, slot: _Optional[int] = ..., item_id: _Optional[str] = ..., count: _Optional[int] = ..., damage: _Optional[int] = ...) -> None: ...

class InventorySummary(_message.Message):
    __slots__ = ("revision", "stacks")
    REVISION_FIELD_NUMBER: _ClassVar[int]
    STACKS_FIELD_NUMBER: _ClassVar[int]
    revision: int
    stacks: _containers.RepeatedCompositeFieldContainer[InventoryStack]
    def __init__(self, revision: _Optional[int] = ..., stacks: _Optional[_Iterable[_Union[InventoryStack, _Mapping]]] = ...) -> None: ...

class VisibleEntity(_message.Message):
    __slots__ = ("observation_id", "entity_type", "relative_x", "relative_y", "relative_z", "line_of_sight")
    OBSERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    ENTITY_TYPE_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_X_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_Y_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_Z_FIELD_NUMBER: _ClassVar[int]
    LINE_OF_SIGHT_FIELD_NUMBER: _ClassVar[int]
    observation_id: str
    entity_type: str
    relative_x: float
    relative_y: float
    relative_z: float
    line_of_sight: bool
    def __init__(self, observation_id: _Optional[str] = ..., entity_type: _Optional[str] = ..., relative_x: _Optional[float] = ..., relative_y: _Optional[float] = ..., relative_z: _Optional[float] = ..., line_of_sight: bool = ...) -> None: ...

class InitialObservation(_message.Message):
    __slots__ = ("generation", "game_tick", "self", "inventory", "visible_entities", "authoritative", "session_identity")
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    GAME_TICK_FIELD_NUMBER: _ClassVar[int]
    SELF_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_FIELD_NUMBER: _ClassVar[int]
    VISIBLE_ENTITIES_FIELD_NUMBER: _ClassVar[int]
    AUTHORITATIVE_FIELD_NUMBER: _ClassVar[int]
    SESSION_IDENTITY_FIELD_NUMBER: _ClassVar[int]
    generation: int
    game_tick: int
    self: SelfState
    inventory: InventorySummary
    visible_entities: _containers.RepeatedCompositeFieldContainer[VisibleEntity]
    authoritative: bool
    session_identity: _session_pb2.SessionIdentityReport
    def __init__(self_, generation: _Optional[int] = ..., game_tick: _Optional[int] = ..., self: _Optional[_Union[SelfState, _Mapping]] = ..., inventory: _Optional[_Union[InventorySummary, _Mapping]] = ..., visible_entities: _Optional[_Iterable[_Union[VisibleEntity, _Mapping]]] = ..., authoritative: bool = ..., session_identity: _Optional[_Union[_session_pb2.SessionIdentityReport, _Mapping]] = ...) -> None: ...
