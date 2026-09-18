from typing import cast

from minekin_core.domain.errors import (
    ErrorCategory,
    ExitCode,
    MinekinError,
    Retryability,
    fail_closed,
    redact_data,
    redact_text,
)


def test_every_error_category_has_a_stable_nonzero_exit_code() -> None:
    codes = {
        MinekinError("core", "op", category, Retryability.NEVER, "safe").exit_code
        for category in ErrorCategory
    }
    assert len(codes) == len(ErrorCategory)
    assert ExitCode.OK not in codes


def test_redaction_is_recursive_and_catches_inline_credentials() -> None:
    value = {
        "access_token": "sentinel-token",
        "nested": ["Authorization: Bearer abc", {"password": "hunter2"}],
    }
    redacted = cast(dict[str, object], redact_data(value))
    assert redacted["access_token"] == "<redacted>"
    nested = cast(list[object], redacted["nested"])
    assert "abc" not in cast(str, nested[0])
    assert cast(dict[str, object], nested[1])["password"] == "<redacted>"
    assert "canary" not in redact_text("secret=canary")


def test_unknown_errors_fail_closed_without_copying_exception_text() -> None:
    converted = fail_closed(
        RuntimeError("access_token=do-not-log"), component="core", operation="run"
    )
    assert converted.category is ErrorCategory.INTERNAL_INVARIANT
    assert converted.retryability is Retryability.NEVER
    assert "do-not-log" not in str(converted.diagnostic())
    assert converted.exit_code is ExitCode.INTERNAL_INVARIANT


def test_known_error_is_preserved() -> None:
    error = MinekinError(
        "bridge", "hello", ErrorCategory.IPC_PROTOCOL, Retryability.NEVER, "bad hello"
    )
    assert fail_closed(error, component="core", operation="run") is error
