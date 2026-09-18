"""Frozen P0 runtime requirements used by read-only diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeRequirements:
    """Versions that a Minekin P0 host must provide.

    This is deliberately configuration data rather than environment discovery.
    In particular, importing this module never creates a run directory or invokes
    a package manager.
    """

    python_min: tuple[int, int] = (3, 12)
    python_max_exclusive: tuple[int, int] = (3, 14)
    java_major: int = 21
    protobuf_distribution: str = "protobuf"
    protobuf_min: tuple[int, int] = (5, 29)
    protobuf_max_exclusive: tuple[int, int] = (7, 0)

    def supports_python(self, version: tuple[int, int]) -> bool:
        return self.python_min <= version < self.python_max_exclusive

    def supports_protobuf(self, version: tuple[int, int]) -> bool:
        return self.protobuf_min <= version < self.protobuf_max_exclusive


P0_REQUIREMENTS = RuntimeRequirements()
