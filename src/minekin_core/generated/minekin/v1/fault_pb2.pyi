from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ErrorCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ERROR_CATEGORY_UNSPECIFIED: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_CONFIG: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_SUPPLY_CHAIN: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_STORAGE: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_PROCESS: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_IPC_PROTOCOL: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_IPC_BACKPRESSURE: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_SESSION: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_ADMISSION: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_PERCEPTION_BOUNDARY: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_CONTROL_SAFETY: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_TIMEOUT: _ClassVar[ErrorCategory]
    ERROR_CATEGORY_INTERNAL_INVARIANT: _ClassVar[ErrorCategory]

class Retryability(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RETRYABILITY_UNSPECIFIED: _ClassVar[Retryability]
    RETRYABILITY_NEVER: _ClassVar[Retryability]
    RETRYABILITY_SAFE: _ClassVar[Retryability]
    RETRYABILITY_NEW_GENERATION: _ClassVar[Retryability]
    RETRYABILITY_OPERATOR_ACTION: _ClassVar[Retryability]
ERROR_CATEGORY_UNSPECIFIED: ErrorCategory
ERROR_CATEGORY_CONFIG: ErrorCategory
ERROR_CATEGORY_SUPPLY_CHAIN: ErrorCategory
ERROR_CATEGORY_STORAGE: ErrorCategory
ERROR_CATEGORY_PROCESS: ErrorCategory
ERROR_CATEGORY_IPC_PROTOCOL: ErrorCategory
ERROR_CATEGORY_IPC_BACKPRESSURE: ErrorCategory
ERROR_CATEGORY_SESSION: ErrorCategory
ERROR_CATEGORY_ADMISSION: ErrorCategory
ERROR_CATEGORY_PERCEPTION_BOUNDARY: ErrorCategory
ERROR_CATEGORY_CONTROL_SAFETY: ErrorCategory
ERROR_CATEGORY_TIMEOUT: ErrorCategory
ERROR_CATEGORY_INTERNAL_INVARIANT: ErrorCategory
RETRYABILITY_UNSPECIFIED: Retryability
RETRYABILITY_NEVER: Retryability
RETRYABILITY_SAFE: Retryability
RETRYABILITY_NEW_GENERATION: Retryability
RETRYABILITY_OPERATOR_ACTION: Retryability

class Fault(_message.Message):
    __slots__ = ("fault_id", "component", "operation", "category", "retryability", "redacted_summary", "evidence_ref", "terminal")
    FAULT_ID_FIELD_NUMBER: _ClassVar[int]
    COMPONENT_FIELD_NUMBER: _ClassVar[int]
    OPERATION_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    RETRYABILITY_FIELD_NUMBER: _ClassVar[int]
    REDACTED_SUMMARY_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_REF_FIELD_NUMBER: _ClassVar[int]
    TERMINAL_FIELD_NUMBER: _ClassVar[int]
    fault_id: str
    component: str
    operation: str
    category: ErrorCategory
    retryability: Retryability
    redacted_summary: str
    evidence_ref: str
    terminal: bool
    def __init__(self, fault_id: _Optional[str] = ..., component: _Optional[str] = ..., operation: _Optional[str] = ..., category: _Optional[_Union[ErrorCategory, str]] = ..., retryability: _Optional[_Union[Retryability, str]] = ..., redacted_summary: _Optional[str] = ..., evidence_ref: _Optional[str] = ..., terminal: bool = ...) -> None: ...
