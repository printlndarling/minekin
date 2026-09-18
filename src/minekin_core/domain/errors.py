"""Stable error taxonomy, process exit codes, and log redaction."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any, cast


class ErrorCategory(StrEnum):
    CONFIG = "CONFIG"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    STORAGE = "STORAGE"
    PROCESS = "PROCESS"
    IPC_PROTOCOL = "IPC_PROTOCOL"
    IPC_BACKPRESSURE = "IPC_BACKPRESSURE"
    SESSION = "SESSION"
    ADMISSION = "ADMISSION"
    PERCEPTION_BOUNDARY = "PERCEPTION_BOUNDARY"
    CONTROL_SAFETY = "CONTROL_SAFETY"
    TIMEOUT = "TIMEOUT"
    INTERNAL_INVARIANT = "INTERNAL_INVARIANT"


class Retryability(StrEnum):
    NEVER = "NEVER"
    SAFE = "SAFE"
    NEW_GENERATION = "NEW_GENERATION"
    OPERATOR_ACTION = "OPERATOR_ACTION"


class ExitCode(IntEnum):
    OK = 0
    USAGE = 2
    CONFIG = 10
    SUPPLY_CHAIN = 11
    STORAGE = 12
    PROCESS = 13
    IPC_PROTOCOL = 14
    IPC_BACKPRESSURE = 15
    SESSION = 16
    ADMISSION = 17
    PERCEPTION_BOUNDARY = 18
    CONTROL_SAFETY = 19
    TIMEOUT = 20
    INTERNAL_INVARIANT = 70
    INTERRUPTED = 130


_EXIT_BY_CATEGORY = {category: ExitCode[category.name] for category in ErrorCategory}
_SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|password|passwd|secret|token|credential|session[_-]?key|nonce)",
    re.IGNORECASE,
)
_INLINE_SECRET = re.compile(
    r"(?i)(\b(?:bearer|basic)\s+)[^\s,;]+|"
    r"((?:access[_-]?token|refresh[_-]?token|password|secret|session[_-]?key)\s*[=:]\s*)[^\s,;&]+"
)


def exit_code_for(category: ErrorCategory) -> ExitCode:
    return _EXIT_BY_CATEGORY[category]


def redact_text(value: str, *, secrets: tuple[str, ...] = ()) -> str:
    """Redact known literals and common inline credentials without logging them."""

    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")

    def replacement(match: re.Match[str]) -> str:
        prefix = match.group(1) or match.group(2) or ""
        return f"{prefix}<redacted>"

    return _INLINE_SECRET.sub(replacement, redacted)


def redact_data(value: object, *, secrets: tuple[str, ...] = ()) -> object:
    """Return a recursively redacted copy suitable for diagnostics/evidence."""

    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {
            str(key): (
                "<redacted>"
                if _SENSITIVE_KEY.search(str(key))
                else redact_data(item, secrets=secrets)
            )
            for key, item in mapping.items()
        }
    if isinstance(value, list):
        items = cast(list[object], value)
        return [redact_data(item, secrets=secrets) for item in items]
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return tuple(redact_data(item, secrets=secrets) for item in items)
    if isinstance(value, str):
        return redact_text(value, secrets=secrets)
    return value


@dataclass(frozen=True, slots=True)
class MinekinError(Exception):
    component: str
    operation: str
    category: ErrorCategory
    retryability: Retryability
    safe_message: str
    evidence_ref: str | None = None
    context: Mapping[str, object] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        if not self.component or not self.operation or not self.safe_message:
            raise ValueError("component, operation, and safe_message are required")
        Exception.__init__(self, self.safe_message)

    @property
    def exit_code(self) -> ExitCode:
        return exit_code_for(self.category)

    def diagnostic(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "operation": self.operation,
            "category": self.category.value,
            "retryability": self.retryability.value,
            "message": redact_text(self.safe_message),
            "evidence_ref": self.evidence_ref,
            "context": redact_data(self.context),
        }


def fail_closed(error: BaseException, *, component: str, operation: str) -> MinekinError:
    """Convert an unknown exception without copying its potentially sensitive text."""

    if isinstance(error, MinekinError):
        return error
    return MinekinError(
        component=component,
        operation=operation,
        category=ErrorCategory.INTERNAL_INVARIANT,
        retryability=Retryability.NEVER,
        safe_message="unexpected internal failure",
        context={"exception_type": type(error).__name__},
    )
