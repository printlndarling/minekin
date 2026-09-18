from minekin_core.generated.minekin.v1 import session_pb2 as _session_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

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
