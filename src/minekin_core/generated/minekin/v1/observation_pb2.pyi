from minekin_core.generated.minekin.v1 import control_pb2 as _control_pb2
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
    ADMISSION_FAILURE_REASON_CONNECTION_REFUSED: _ClassVar[AdmissionFailureReason]

class HostPhase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HOST_PHASE_UNSPECIFIED: _ClassVar[HostPhase]
    HOST_PHASE_LAN_OPENED: _ClassVar[HostPhase]
    HOST_PHASE_LAN_OPEN_FAILED: _ClassVar[HostPhase]

class AimTargetKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    AIM_TARGET_KIND_UNSPECIFIED: _ClassVar[AimTargetKind]
    AIM_TARGET_KIND_MISS: _ClassVar[AimTargetKind]
    AIM_TARGET_KIND_BLOCK: _ClassVar[AimTargetKind]
    AIM_TARGET_KIND_ENTITY: _ClassVar[AimTargetKind]
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
ADMISSION_FAILURE_REASON_CONNECTION_REFUSED: AdmissionFailureReason
HOST_PHASE_UNSPECIFIED: HostPhase
HOST_PHASE_LAN_OPENED: HostPhase
HOST_PHASE_LAN_OPEN_FAILED: HostPhase
AIM_TARGET_KIND_UNSPECIFIED: AimTargetKind
AIM_TARGET_KIND_MISS: AimTargetKind
AIM_TARGET_KIND_BLOCK: AimTargetKind
AIM_TARGET_KIND_ENTITY: AimTargetKind

class HostLifecycle(_message.Message):
    __slots__ = ("request_id", "generation", "phase", "bound_port")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    BOUND_PORT_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    generation: int
    phase: HostPhase
    bound_port: int
    def __init__(self, request_id: _Optional[str] = ..., generation: _Optional[int] = ..., phase: _Optional[_Union[HostPhase, str]] = ..., bound_port: _Optional[int] = ...) -> None: ...

class ConnectionLifecycle(_message.Message):
    __slots__ = ("generation", "server_profile_id", "server_profile_revision", "phase", "failure_reason", "terminal", "applied_resource_pack_policy")
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    SERVER_PROFILE_ID_FIELD_NUMBER: _ClassVar[int]
    SERVER_PROFILE_REVISION_FIELD_NUMBER: _ClassVar[int]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    FAILURE_REASON_FIELD_NUMBER: _ClassVar[int]
    TERMINAL_FIELD_NUMBER: _ClassVar[int]
    APPLIED_RESOURCE_PACK_POLICY_FIELD_NUMBER: _ClassVar[int]
    generation: int
    server_profile_id: str
    server_profile_revision: str
    phase: ConnectionPhase
    failure_reason: AdmissionFailureReason
    terminal: bool
    applied_resource_pack_policy: _control_pb2.ResourcePackPolicy
    def __init__(self, generation: _Optional[int] = ..., server_profile_id: _Optional[str] = ..., server_profile_revision: _Optional[str] = ..., phase: _Optional[_Union[ConnectionPhase, str]] = ..., failure_reason: _Optional[_Union[AdmissionFailureReason, str]] = ..., terminal: bool = ..., applied_resource_pack_policy: _Optional[_Union[_control_pb2.ResourcePackPolicy, str]] = ...) -> None: ...

class CallbackBudgetWindow(_message.Message):
    __slots__ = ("label", "window", "opened_at_nanos", "recorded", "micros")
    LABEL_FIELD_NUMBER: _ClassVar[int]
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    OPENED_AT_NANOS_FIELD_NUMBER: _ClassVar[int]
    RECORDED_FIELD_NUMBER: _ClassVar[int]
    MICROS_FIELD_NUMBER: _ClassVar[int]
    label: str
    window: int
    opened_at_nanos: int
    recorded: int
    micros: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, label: _Optional[str] = ..., window: _Optional[int] = ..., opened_at_nanos: _Optional[int] = ..., recorded: _Optional[int] = ..., micros: _Optional[_Iterable[int]] = ...) -> None: ...

class SelfState(_message.Message):
    __slots__ = ("health", "max_health", "food", "saturation", "on_ground", "alive", "current_screen", "x", "y", "z", "yaw_degrees", "pitch_degrees", "selected_slot", "main_hand_item_id", "respawn_available")
    HEALTH_FIELD_NUMBER: _ClassVar[int]
    MAX_HEALTH_FIELD_NUMBER: _ClassVar[int]
    FOOD_FIELD_NUMBER: _ClassVar[int]
    SATURATION_FIELD_NUMBER: _ClassVar[int]
    ON_GROUND_FIELD_NUMBER: _ClassVar[int]
    ALIVE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SCREEN_FIELD_NUMBER: _ClassVar[int]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    Z_FIELD_NUMBER: _ClassVar[int]
    YAW_DEGREES_FIELD_NUMBER: _ClassVar[int]
    PITCH_DEGREES_FIELD_NUMBER: _ClassVar[int]
    SELECTED_SLOT_FIELD_NUMBER: _ClassVar[int]
    MAIN_HAND_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    RESPAWN_AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    health: float
    max_health: float
    food: int
    saturation: float
    on_ground: bool
    alive: bool
    current_screen: str
    x: float
    y: float
    z: float
    yaw_degrees: float
    pitch_degrees: float
    selected_slot: int
    main_hand_item_id: str
    respawn_available: bool
    def __init__(self, health: _Optional[float] = ..., max_health: _Optional[float] = ..., food: _Optional[int] = ..., saturation: _Optional[float] = ..., on_ground: bool = ..., alive: bool = ..., current_screen: _Optional[str] = ..., x: _Optional[float] = ..., y: _Optional[float] = ..., z: _Optional[float] = ..., yaw_degrees: _Optional[float] = ..., pitch_degrees: _Optional[float] = ..., selected_slot: _Optional[int] = ..., main_hand_item_id: _Optional[str] = ..., respawn_available: bool = ...) -> None: ...

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
    __slots__ = ("observation_id", "entity_type", "relative_x", "relative_y", "relative_z", "line_of_sight", "item_id", "item_count")
    OBSERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    ENTITY_TYPE_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_X_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_Y_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_Z_FIELD_NUMBER: _ClassVar[int]
    LINE_OF_SIGHT_FIELD_NUMBER: _ClassVar[int]
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    ITEM_COUNT_FIELD_NUMBER: _ClassVar[int]
    observation_id: str
    entity_type: str
    relative_x: float
    relative_y: float
    relative_z: float
    line_of_sight: bool
    item_id: str
    item_count: int
    def __init__(self, observation_id: _Optional[str] = ..., entity_type: _Optional[str] = ..., relative_x: _Optional[float] = ..., relative_y: _Optional[float] = ..., relative_z: _Optional[float] = ..., line_of_sight: bool = ..., item_id: _Optional[str] = ..., item_count: _Optional[int] = ...) -> None: ...

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

class AimTarget(_message.Message):
    __slots__ = ("game_tick", "kind", "block", "targeted_block_id", "entity_observation_id", "entity_type", "distance")
    GAME_TICK_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    BLOCK_FIELD_NUMBER: _ClassVar[int]
    TARGETED_BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    ENTITY_OBSERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    ENTITY_TYPE_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_FIELD_NUMBER: _ClassVar[int]
    game_tick: int
    kind: AimTargetKind
    block: _control_pb2.BlockTarget
    targeted_block_id: str
    entity_observation_id: str
    entity_type: str
    distance: float
    def __init__(self, game_tick: _Optional[int] = ..., kind: _Optional[_Union[AimTargetKind, str]] = ..., block: _Optional[_Union[_control_pb2.BlockTarget, _Mapping]] = ..., targeted_block_id: _Optional[str] = ..., entity_observation_id: _Optional[str] = ..., entity_type: _Optional[str] = ..., distance: _Optional[float] = ...) -> None: ...

class MiningProgress(_message.Message):
    __slots__ = ("game_tick", "target", "progress")
    GAME_TICK_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    game_tick: int
    target: _control_pb2.BlockTarget
    progress: float
    def __init__(self, game_tick: _Optional[int] = ..., target: _Optional[_Union[_control_pb2.BlockTarget, _Mapping]] = ..., progress: _Optional[float] = ...) -> None: ...

class GuiScreen(_message.Message):
    __slots__ = ("screen_id", "sync_id", "craftable_recipe_ids", "trade_offers")
    SCREEN_ID_FIELD_NUMBER: _ClassVar[int]
    SYNC_ID_FIELD_NUMBER: _ClassVar[int]
    CRAFTABLE_RECIPE_IDS_FIELD_NUMBER: _ClassVar[int]
    TRADE_OFFERS_FIELD_NUMBER: _ClassVar[int]
    screen_id: str
    sync_id: int
    craftable_recipe_ids: _containers.RepeatedScalarFieldContainer[str]
    trade_offers: _containers.RepeatedCompositeFieldContainer[TradeOffer]
    def __init__(self, screen_id: _Optional[str] = ..., sync_id: _Optional[int] = ..., craftable_recipe_ids: _Optional[_Iterable[str]] = ..., trade_offers: _Optional[_Iterable[_Union[TradeOffer, _Mapping]]] = ...) -> None: ...

class TradeOffer(_message.Message):
    __slots__ = ("first_item_id", "first_count", "second_item_id", "second_count", "sell_item_id", "sell_count", "uses", "max_uses", "disabled")
    FIRST_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    FIRST_COUNT_FIELD_NUMBER: _ClassVar[int]
    SECOND_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    SECOND_COUNT_FIELD_NUMBER: _ClassVar[int]
    SELL_ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    SELL_COUNT_FIELD_NUMBER: _ClassVar[int]
    USES_FIELD_NUMBER: _ClassVar[int]
    MAX_USES_FIELD_NUMBER: _ClassVar[int]
    DISABLED_FIELD_NUMBER: _ClassVar[int]
    first_item_id: str
    first_count: int
    second_item_id: str
    second_count: int
    sell_item_id: str
    sell_count: int
    uses: int
    max_uses: int
    disabled: bool
    def __init__(self, first_item_id: _Optional[str] = ..., first_count: _Optional[int] = ..., second_item_id: _Optional[str] = ..., second_count: _Optional[int] = ..., sell_item_id: _Optional[str] = ..., sell_count: _Optional[int] = ..., uses: _Optional[int] = ..., max_uses: _Optional[int] = ..., disabled: bool = ...) -> None: ...

class PlayerChatMessage(_message.Message):
    __slots__ = ("game_tick", "sender", "text", "sender_id")
    GAME_TICK_FIELD_NUMBER: _ClassVar[int]
    SENDER_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    SENDER_ID_FIELD_NUMBER: _ClassVar[int]
    game_tick: int
    sender: str
    text: str
    sender_id: str
    def __init__(self, game_tick: _Optional[int] = ..., sender: _Optional[str] = ..., text: _Optional[str] = ..., sender_id: _Optional[str] = ...) -> None: ...

class WorldObservation(_message.Message):
    __slots__ = ("generation", "game_tick", "self", "aim", "inventory", "visible_entities", "mining", "gui", "chat", "chat_omitted")
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    GAME_TICK_FIELD_NUMBER: _ClassVar[int]
    SELF_FIELD_NUMBER: _ClassVar[int]
    AIM_FIELD_NUMBER: _ClassVar[int]
    INVENTORY_FIELD_NUMBER: _ClassVar[int]
    VISIBLE_ENTITIES_FIELD_NUMBER: _ClassVar[int]
    MINING_FIELD_NUMBER: _ClassVar[int]
    GUI_FIELD_NUMBER: _ClassVar[int]
    CHAT_FIELD_NUMBER: _ClassVar[int]
    CHAT_OMITTED_FIELD_NUMBER: _ClassVar[int]
    generation: int
    game_tick: int
    self: SelfState
    aim: AimTarget
    inventory: InventorySummary
    visible_entities: _containers.RepeatedCompositeFieldContainer[VisibleEntity]
    mining: MiningProgress
    gui: GuiScreen
    chat: _containers.RepeatedCompositeFieldContainer[PlayerChatMessage]
    chat_omitted: int
    def __init__(self_, generation: _Optional[int] = ..., game_tick: _Optional[int] = ..., self: _Optional[_Union[SelfState, _Mapping]] = ..., aim: _Optional[_Union[AimTarget, _Mapping]] = ..., inventory: _Optional[_Union[InventorySummary, _Mapping]] = ..., visible_entities: _Optional[_Iterable[_Union[VisibleEntity, _Mapping]]] = ..., mining: _Optional[_Union[MiningProgress, _Mapping]] = ..., gui: _Optional[_Union[GuiScreen, _Mapping]] = ..., chat: _Optional[_Iterable[_Union[PlayerChatMessage, _Mapping]]] = ..., chat_omitted: _Optional[int] = ...) -> None: ...
