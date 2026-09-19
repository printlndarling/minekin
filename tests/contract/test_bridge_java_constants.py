"""Pin the strings the Python runtime and the Java Bridge must agree on.

Both sides hard-code the envelope message types and the name of the variable
that carries the bootstrap descriptor path. Nothing else checks that they agree:
the offline Java check compiles the Bridge against stubs, and the loopback
contract test *is* the Python side, so a rename on the Java side alone stays
invisible until a real client fails to start. That is the one failure this
repository cannot reproduce locally, so it is worth a check that reads both
sources and compares them.

This reads source, not behaviour. It cannot tell whether the Bridge handles a
message, only that the two processes call it the same thing.
"""

from __future__ import annotations

import re
from pathlib import Path

from minekin_core.adapters.bridge import ipc
from minekin_core.adapters.launcher import process

BRIDGE_ROOT = Path(__file__).resolve().parents[2] / "bridge" / "src" / "main" / "java"
WORKER = BRIDGE_ROOT / "org" / "minekin" / "bridge" / "runtime" / "BridgeIpcWorker.java"
CLIENT = BRIDGE_ROOT / "org" / "minekin" / "bridge" / "MinekinBridgeClient.java"
INPUT_CONTROLLER = (
    BRIDGE_ROOT / "org" / "minekin" / "bridge" / "input" / "BridgeInputController.java"
)

_TYPE_CONSTANT = re.compile(r'String\s+(\w+_TYPE)\s*=\s*"([^"]+)"')
_ENVIRONMENT_CONSTANT = re.compile(r'String\s+(\w*ENVIRONMENT_VARIABLE)\s*=\s*"([^"]+)"')
_INPUT_CAPABILITY = re.compile(r'public static final String\s+\w+\s*=\s*"(move\.[^"]+)"')


def _constants(path: Path, pattern: re.Pattern[str]) -> dict[str, str]:
    assert path.is_file(), f"{path} is missing; this check would silently pass"
    return dict(pattern.findall(path.read_text(encoding="utf-8")))


def test_the_envelope_message_types_are_spelled_the_same_on_both_sides() -> None:
    declared = _constants(WORKER, _TYPE_CONSTANT)

    # A parse that found nothing would make every comparison below vacuous.
    assert declared, f"no message type constants found in {WORKER}"

    mismatches = {
        name: (value, getattr(ipc, name, None))
        for name, value in declared.items()
        if getattr(ipc, name, None) != value
    }
    assert not mismatches, f"Java and Python disagree about {mismatches}"


def test_the_descriptor_variable_the_bridge_reads_is_the_one_core_sets() -> None:
    declared = _constants(CLIENT, _ENVIRONMENT_CONSTANT)

    assert declared, f"no environment variable constants found in {CLIENT}"
    assert set(declared.values()) == {process.BRIDGE_DESCRIPTOR_VARIABLE}


def test_the_movement_capability_vocabulary_is_shared() -> None:
    declared = set(_INPUT_CAPABILITY.findall(INPUT_CONTROLLER.read_text(encoding="utf-8")))

    assert declared
    assert declared == ipc.MOVEMENT_CAPABILITIES
