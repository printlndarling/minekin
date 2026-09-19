from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
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
