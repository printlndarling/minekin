from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ResourcePackPolicy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RESOURCE_PACK_POLICY_UNSPECIFIED: _ClassVar[ResourcePackPolicy]
    RESOURCE_PACK_POLICY_DENY: _ClassVar[ResourcePackPolicy]
    RESOURCE_PACK_POLICY_PROMPT: _ClassVar[ResourcePackPolicy]

class ConnectionCancelReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CONNECTION_CANCEL_REASON_UNSPECIFIED: _ClassVar[ConnectionCancelReason]
    CONNECTION_CANCEL_REASON_OPERATOR: _ClassVar[ConnectionCancelReason]
    CONNECTION_CANCEL_REASON_TIMEOUT: _ClassVar[ConnectionCancelReason]
    CONNECTION_CANCEL_REASON_NEW_GENERATION: _ClassVar[ConnectionCancelReason]
    CONNECTION_CANCEL_REASON_SESSION_STOPPING: _ClassVar[ConnectionCancelReason]

class InputPriority(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INPUT_PRIORITY_UNSPECIFIED: _ClassVar[InputPriority]
    INPUT_PRIORITY_NORMAL: _ClassVar[InputPriority]
    INPUT_PRIORITY_URGENT: _ClassVar[InputPriority]
    INPUT_PRIORITY_EMERGENCY: _ClassVar[InputPriority]

class ActionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACTION_STATUS_UNSPECIFIED: _ClassVar[ActionStatus]
    ACTION_STATUS_ACCEPTED: _ClassVar[ActionStatus]
    ACTION_STATUS_STARTED: _ClassVar[ActionStatus]
    ACTION_STATUS_SUCCEEDED: _ClassVar[ActionStatus]
    ACTION_STATUS_FAILED: _ClassVar[ActionStatus]
    ACTION_STATUS_CANCELLED: _ClassVar[ActionStatus]
    ACTION_STATUS_UNKNOWN_AFTER_DISCONNECT: _ClassVar[ActionStatus]

class BlockFace(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BLOCK_FACE_UNSPECIFIED: _ClassVar[BlockFace]
    BLOCK_FACE_UNKNOWN: _ClassVar[BlockFace]
    BLOCK_FACE_DOWN: _ClassVar[BlockFace]
    BLOCK_FACE_UP: _ClassVar[BlockFace]
    BLOCK_FACE_NORTH: _ClassVar[BlockFace]
    BLOCK_FACE_SOUTH: _ClassVar[BlockFace]
    BLOCK_FACE_WEST: _ClassVar[BlockFace]
    BLOCK_FACE_EAST: _ClassVar[BlockFace]

class ScreenControl(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SCREEN_CONTROL_UNSPECIFIED: _ClassVar[ScreenControl]
    SCREEN_CONTROL_OPEN_INVENTORY: _ClassVar[ScreenControl]
    SCREEN_CONTROL_CLOSE: _ClassVar[ScreenControl]

class SlotClickMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SLOT_CLICK_MODE_UNSPECIFIED: _ClassVar[SlotClickMode]
    SLOT_CLICK_MODE_PICK: _ClassVar[SlotClickMode]
    SLOT_CLICK_MODE_QUICK_MOVE: _ClassVar[SlotClickMode]
    SLOT_CLICK_MODE_SWAP: _ClassVar[SlotClickMode]
    SLOT_CLICK_MODE_THROW: _ClassVar[SlotClickMode]
RESOURCE_PACK_POLICY_UNSPECIFIED: ResourcePackPolicy
RESOURCE_PACK_POLICY_DENY: ResourcePackPolicy
RESOURCE_PACK_POLICY_PROMPT: ResourcePackPolicy
CONNECTION_CANCEL_REASON_UNSPECIFIED: ConnectionCancelReason
CONNECTION_CANCEL_REASON_OPERATOR: ConnectionCancelReason
CONNECTION_CANCEL_REASON_TIMEOUT: ConnectionCancelReason
CONNECTION_CANCEL_REASON_NEW_GENERATION: ConnectionCancelReason
CONNECTION_CANCEL_REASON_SESSION_STOPPING: ConnectionCancelReason
INPUT_PRIORITY_UNSPECIFIED: InputPriority
INPUT_PRIORITY_NORMAL: InputPriority
INPUT_PRIORITY_URGENT: InputPriority
INPUT_PRIORITY_EMERGENCY: InputPriority
ACTION_STATUS_UNSPECIFIED: ActionStatus
ACTION_STATUS_ACCEPTED: ActionStatus
ACTION_STATUS_STARTED: ActionStatus
ACTION_STATUS_SUCCEEDED: ActionStatus
ACTION_STATUS_FAILED: ActionStatus
ACTION_STATUS_CANCELLED: ActionStatus
ACTION_STATUS_UNKNOWN_AFTER_DISCONNECT: ActionStatus
BLOCK_FACE_UNSPECIFIED: BlockFace
BLOCK_FACE_UNKNOWN: BlockFace
BLOCK_FACE_DOWN: BlockFace
BLOCK_FACE_UP: BlockFace
BLOCK_FACE_NORTH: BlockFace
BLOCK_FACE_SOUTH: BlockFace
BLOCK_FACE_WEST: BlockFace
BLOCK_FACE_EAST: BlockFace
SCREEN_CONTROL_UNSPECIFIED: ScreenControl
SCREEN_CONTROL_OPEN_INVENTORY: ScreenControl
SCREEN_CONTROL_CLOSE: ScreenControl
SLOT_CLICK_MODE_UNSPECIFIED: SlotClickMode
SLOT_CLICK_MODE_PICK: SlotClickMode
SLOT_CLICK_MODE_QUICK_MOVE: SlotClickMode
SLOT_CLICK_MODE_SWAP: SlotClickMode
SLOT_CLICK_MODE_THROW: SlotClickMode

class ConnectWorld(_message.Message):
    __slots__ = ("request_id", "generation", "server_profile_id", "server_profile_revision", "original_host", "port", "resource_pack_policy", "deadline_monotonic_ns")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    SERVER_PROFILE_ID_FIELD_NUMBER: _ClassVar[int]
    SERVER_PROFILE_REVISION_FIELD_NUMBER: _ClassVar[int]
    ORIGINAL_HOST_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_PACK_POLICY_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    generation: int
    server_profile_id: str
    server_profile_revision: str
    original_host: str
    port: int
    resource_pack_policy: ResourcePackPolicy
    deadline_monotonic_ns: int
    def __init__(self, request_id: _Optional[str] = ..., generation: _Optional[int] = ..., server_profile_id: _Optional[str] = ..., server_profile_revision: _Optional[str] = ..., original_host: _Optional[str] = ..., port: _Optional[int] = ..., resource_pack_policy: _Optional[_Union[ResourcePackPolicy, str]] = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...

class CancelConnection(_message.Message):
    __slots__ = ("request_id", "generation", "reason")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    generation: int
    reason: ConnectionCancelReason
    def __init__(self, request_id: _Optional[str] = ..., generation: _Optional[int] = ..., reason: _Optional[_Union[ConnectionCancelReason, str]] = ...) -> None: ...

class InputLease(_message.Message):
    __slots__ = ("lease_id", "generation", "client_instance_id", "issued_monotonic_ns", "deadline_monotonic_ns", "priority", "capabilities")
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    CLIENT_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    ISSUED_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    lease_id: str
    generation: int
    client_instance_id: str
    issued_monotonic_ns: int
    deadline_monotonic_ns: int
    priority: InputPriority
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, lease_id: _Optional[str] = ..., generation: _Optional[int] = ..., client_instance_id: _Optional[str] = ..., issued_monotonic_ns: _Optional[int] = ..., deadline_monotonic_ns: _Optional[int] = ..., priority: _Optional[_Union[InputPriority, str]] = ..., capabilities: _Optional[_Iterable[str]] = ...) -> None: ...

class LookInput(_message.Message):
    __slots__ = ("action_id", "lease_id", "generation", "delta_yaw_degrees", "delta_pitch_degrees", "deadline_monotonic_ns")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    DELTA_YAW_DEGREES_FIELD_NUMBER: _ClassVar[int]
    DELTA_PITCH_DEGREES_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    lease_id: str
    generation: int
    delta_yaw_degrees: float
    delta_pitch_degrees: float
    deadline_monotonic_ns: int
    def __init__(self, action_id: _Optional[str] = ..., lease_id: _Optional[str] = ..., generation: _Optional[int] = ..., delta_yaw_degrees: _Optional[float] = ..., delta_pitch_degrees: _Optional[float] = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...

class MoveInput(_message.Message):
    __slots__ = ("action_id", "lease_id", "generation", "forward", "strafe", "jump", "sneak", "deadline_monotonic_ns")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    FORWARD_FIELD_NUMBER: _ClassVar[int]
    STRAFE_FIELD_NUMBER: _ClassVar[int]
    JUMP_FIELD_NUMBER: _ClassVar[int]
    SNEAK_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    lease_id: str
    generation: int
    forward: float
    strafe: float
    jump: bool
    sneak: bool
    deadline_monotonic_ns: int
    def __init__(self, action_id: _Optional[str] = ..., lease_id: _Optional[str] = ..., generation: _Optional[int] = ..., forward: _Optional[float] = ..., strafe: _Optional[float] = ..., jump: bool = ..., sneak: bool = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...

class UseInput(_message.Message):
    __slots__ = ("action_id", "lease_id", "generation", "use", "deadline_monotonic_ns")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    USE_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    lease_id: str
    generation: int
    use: bool
    deadline_monotonic_ns: int
    def __init__(self, action_id: _Optional[str] = ..., lease_id: _Optional[str] = ..., generation: _Optional[int] = ..., use: bool = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...

class ReleaseAllInputs(_message.Message):
    __slots__ = ("action_id", "generation", "reason_code")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    REASON_CODE_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    generation: int
    reason_code: str
    def __init__(self, action_id: _Optional[str] = ..., generation: _Optional[int] = ..., reason_code: _Optional[str] = ...) -> None: ...

class ActionResult(_message.Message):
    __slots__ = ("action_id", "generation", "status", "reason_code", "evidence_ref")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    REASON_CODE_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_REF_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    generation: int
    status: ActionStatus
    reason_code: str
    evidence_ref: str
    def __init__(self, action_id: _Optional[str] = ..., generation: _Optional[int] = ..., status: _Optional[_Union[ActionStatus, str]] = ..., reason_code: _Optional[str] = ..., evidence_ref: _Optional[str] = ...) -> None: ...

class OpenLan(_message.Message):
    __slots__ = ("request_id", "generation", "port", "deadline_monotonic_ns")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    generation: int
    port: int
    deadline_monotonic_ns: int
    def __init__(self, request_id: _Optional[str] = ..., generation: _Optional[int] = ..., port: _Optional[int] = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...

class BlockTarget(_message.Message):
    __slots__ = ("x", "y", "z", "face")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    Z_FIELD_NUMBER: _ClassVar[int]
    FACE_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    z: int
    face: BlockFace
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., z: _Optional[int] = ..., face: _Optional[_Union[BlockFace, str]] = ...) -> None: ...

class AimInput(_message.Message):
    __slots__ = ("action_id", "lease_id", "generation", "yaw_degrees", "pitch_degrees", "deadline_monotonic_ns")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    YAW_DEGREES_FIELD_NUMBER: _ClassVar[int]
    PITCH_DEGREES_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    lease_id: str
    generation: int
    yaw_degrees: float
    pitch_degrees: float
    deadline_monotonic_ns: int
    def __init__(self, action_id: _Optional[str] = ..., lease_id: _Optional[str] = ..., generation: _Optional[int] = ..., yaw_degrees: _Optional[float] = ..., pitch_degrees: _Optional[float] = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...

class MineInput(_message.Message):
    __slots__ = ("action_id", "lease_id", "generation", "mining", "target", "deadline_monotonic_ns")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    MINING_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    lease_id: str
    generation: int
    mining: bool
    target: BlockTarget
    deadline_monotonic_ns: int
    def __init__(self, action_id: _Optional[str] = ..., lease_id: _Optional[str] = ..., generation: _Optional[int] = ..., mining: bool = ..., target: _Optional[_Union[BlockTarget, _Mapping]] = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...

class HotbarSelectInput(_message.Message):
    __slots__ = ("action_id", "lease_id", "generation", "slot", "deadline_monotonic_ns")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    SLOT_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    lease_id: str
    generation: int
    slot: int
    deadline_monotonic_ns: int
    def __init__(self, action_id: _Optional[str] = ..., lease_id: _Optional[str] = ..., generation: _Optional[int] = ..., slot: _Optional[int] = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...

class ScreenInput(_message.Message):
    __slots__ = ("action_id", "lease_id", "generation", "control", "deadline_monotonic_ns")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    CONTROL_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    lease_id: str
    generation: int
    control: ScreenControl
    deadline_monotonic_ns: int
    def __init__(self, action_id: _Optional[str] = ..., lease_id: _Optional[str] = ..., generation: _Optional[int] = ..., control: _Optional[_Union[ScreenControl, str]] = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...

class GuiSlotClick(_message.Message):
    __slots__ = ("slot_id", "button", "mode")
    SLOT_ID_FIELD_NUMBER: _ClassVar[int]
    BUTTON_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    slot_id: int
    button: int
    mode: SlotClickMode
    def __init__(self, slot_id: _Optional[int] = ..., button: _Optional[int] = ..., mode: _Optional[_Union[SlotClickMode, str]] = ...) -> None: ...

class GuiRecipeClick(_message.Message):
    __slots__ = ("recipe_id", "craft_all")
    RECIPE_ID_FIELD_NUMBER: _ClassVar[int]
    CRAFT_ALL_FIELD_NUMBER: _ClassVar[int]
    recipe_id: str
    craft_all: bool
    def __init__(self, recipe_id: _Optional[str] = ..., craft_all: bool = ...) -> None: ...

class GuiClickInput(_message.Message):
    __slots__ = ("action_id", "lease_id", "generation", "sync_id", "slot", "recipe", "deadline_monotonic_ns")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    SYNC_ID_FIELD_NUMBER: _ClassVar[int]
    SLOT_FIELD_NUMBER: _ClassVar[int]
    RECIPE_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_MONOTONIC_NS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    lease_id: str
    generation: int
    sync_id: int
    slot: GuiSlotClick
    recipe: GuiRecipeClick
    deadline_monotonic_ns: int
    def __init__(self, action_id: _Optional[str] = ..., lease_id: _Optional[str] = ..., generation: _Optional[int] = ..., sync_id: _Optional[int] = ..., slot: _Optional[_Union[GuiSlotClick, _Mapping]] = ..., recipe: _Optional[_Union[GuiRecipeClick, _Mapping]] = ..., deadline_monotonic_ns: _Optional[int] = ...) -> None: ...
