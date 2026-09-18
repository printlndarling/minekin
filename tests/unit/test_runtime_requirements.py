from __future__ import annotations

import re
import tomllib
from pathlib import Path

from minekin_core.config import P0_REQUIREMENTS

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPOSITORY_ROOT / "pyproject.toml"
GENERATED_PROTOCOL = (
    REPOSITORY_ROOT / "src" / "minekin_core" / "generated" / "minekin" / "v1" / "envelope_pb2.py"
)

# The generated module asserts the runtime it needs at import time. That is the
# authority the doctor has to agree with.
_RUNTIME_VERSION = re.compile(
    r"ValidateProtobufRuntimeVersion\(\s*_runtime_version\.Domain\.PUBLIC,\s*"
    r"(\d+),\s*(\d+),\s*(\d+),"
)
_DECLARED_FLOOR = re.compile(r"^protobuf>=(\d+)\.(\d+)")


def declared_protobuf_floor() -> tuple[int, int]:
    document = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dependencies = document["project"]["dependencies"]
    specifiers = [
        dependency
        for dependency in dependencies
        if isinstance(dependency, str) and dependency.startswith("protobuf")
    ]
    assert len(specifiers) == 1, f"expected one protobuf dependency, got {specifiers}"
    match = _DECLARED_FLOOR.match(specifiers[0])
    assert match is not None, f"protobuf dependency has no lower bound: {specifiers[0]}"
    return (int(match.group(1)), int(match.group(2)))


def generated_runtime_floor() -> tuple[int, int, int]:
    match = _RUNTIME_VERSION.search(GENERATED_PROTOCOL.read_text(encoding="utf-8"))
    assert match is not None, "generated gencode no longer asserts a runtime version"
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def test_doctor_protobuf_floor_matches_the_declared_dependency() -> None:
    assert P0_REQUIREMENTS.protobuf_min == declared_protobuf_floor()


def test_doctor_protobuf_floor_admits_every_runtime_the_gencode_needs() -> None:
    required = generated_runtime_floor()

    assert P0_REQUIREMENTS.protobuf_min >= required[:2]
    assert P0_REQUIREMENTS.supports_protobuf(required[:2])


def test_supports_protobuf_excludes_the_runtime_the_gencode_rejects() -> None:
    required = generated_runtime_floor()
    below = (required[0], required[1] - 1)

    assert not P0_REQUIREMENTS.supports_protobuf(below)
    assert not P0_REQUIREMENTS.supports_protobuf(P0_REQUIREMENTS.protobuf_max_exclusive)
