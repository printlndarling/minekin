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

from minekin_core import config
from minekin_core.adapters.bridge import ipc
from minekin_core.adapters.launcher import process
from minekin_core.domain import budget

BRIDGE_ROOT = Path(__file__).resolve().parents[2] / "bridge" / "src" / "main" / "java"
WORKER = BRIDGE_ROOT / "org" / "minekin" / "bridge" / "runtime" / "BridgeIpcWorker.java"
CLIENT = BRIDGE_ROOT / "org" / "minekin" / "bridge" / "MinekinBridgeClient.java"
ADMISSION_CONTROLLER = (
    BRIDGE_ROOT / "org" / "minekin" / "bridge" / "runtime" / "ClientAdmissionController.java"
)
INPUT_CONTROLLER = (
    BRIDGE_ROOT / "org" / "minekin" / "bridge" / "input" / "BridgeInputController.java"
)
METRICS = BRIDGE_ROOT / "org" / "minekin" / "bridge" / "runtime" / "BridgeMetrics.java"
HANDSHAKE_GATE = BRIDGE_ROOT / "org" / "minekin" / "bridge" / "protocol" / "HandshakeGate.java"

_TYPE_CONSTANT = re.compile(r'String\s+(\w+_TYPE)\s*=\s*"([^"]+)"')
_LABEL_CONSTANT = re.compile(r'String\s+(\w+_LABEL)\s*=\s*"([^"]+)"')
_CAPABILITY = re.compile(r'String\s+(\w+_CAPABILITY)\s*=\s*"([^"]+)"')
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


def test_the_first_snapshot_request_core_lends_is_the_one_the_bridge_reads() -> None:
    """The one variable whose *value* Core never looks at, and why that needs a pin.

    `ADMIT-070` asks for a first snapshot Core refuses, and the only route from the
    runner to the client JVM is the forwarded list — the launcher hands the client no
    other environment. So the two spellings have to agree, and one side drifting is
    not a crash: the Bridge reads nothing, reports `authoritative=true`, and a run
    somebody set up to show a refusal shows an ordinary admission instead. A name
    missing from the list is the same fault in the other direction, and it is checked
    here because nothing else in the product reads the name it lends.
    """

    declared = _constants(ADMISSION_CONTROLLER, _ENVIRONMENT_CONSTANT)

    assert declared == {
        "NON_AUTHORITATIVE_FIRST_SNAPSHOT_ENVIRONMENT_VARIABLE": (
            config.BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT_VARIABLE
        )
    }
    assert config.BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT_VARIABLE in config.FORWARDED_VARIABLES


def test_the_movement_capability_vocabulary_is_shared() -> None:
    declared = set(_INPUT_CAPABILITY.findall(INPUT_CONTROLLER.read_text(encoding="utf-8")))

    assert declared
    assert declared == ipc.MOVEMENT_CAPABILITIES


def test_the_budget_series_labels_are_spelled_the_same_on_both_sides() -> None:
    """The run document files these under the Bridge's own words.

    Core decides what a label means — the aggregate for a series is keyed by it and a
    label it does not know is refused — so a rename on the Java side alone would not
    fail anything. It would make every window arrive as an unknown label, and the run
    document would read as a Bridge that reported nothing, which is a shape the
    refusal path is designed to be distinguishable from and would not be.
    """

    declared = _constants(METRICS, _LABEL_CONSTANT)

    assert declared, f"no label constants found in {METRICS}"
    assert declared == {"TICK_LABEL": budget.TICK_LABEL, "INTERVAL_LABEL": budget.INTERVAL_LABEL}
    assert set(declared.values()) == set(budget.BUDGET_LABELS)


def test_the_capability_vocabulary_is_spelled_the_same_on_both_sides() -> None:
    """What may be negotiated, and the names two processes have to agree on first.

    Capabilities are how this pair agrees what may happen at all: Core offers a set,
    the Bridge accepts a subset, and every command is then gated on the capability
    that covers it. So a rename on one side alone is not a cosmetic drift — Core
    offers something the Bridge never accepts, or the Bridge refuses a command it had
    already negotiated, and both arrive as a protocol violation rather than as a
    rename. That is the failure this file exists for, and it was covered for message
    types and for the movement flags but not for the six identifiers themselves.

    Compared by constant *name* rather than as two sets of strings, because a name is
    what says which capability moved: `{"a","b"} != {"a","c"}` says something
    differs, and `LOOK_CAPABILITY: ('control.look.v1', 'control.look.v2')` says which.
    """

    declared = _constants(HANDSHAKE_GATE, _CAPABILITY)

    assert declared, f"no capability constants found in {HANDSHAKE_GATE}"
    mismatches = {
        name: (value, getattr(ipc, name, None))
        for name, value in declared.items()
        if getattr(ipc, name, None) != value
    }
    assert not mismatches, f"Java and Python disagree about {mismatches}"
    # Both directions, because they are different faults: one side naming a capability
    # the other never heard of, and a capability one side dropped while the other kept
    # offering it. The second is invisible to the comparison above, which only walks
    # what the Java side declares.
    from_python = {
        name
        for name in dir(ipc)
        if name.endswith("_CAPABILITY") and isinstance(getattr(ipc, name), str)
    }
    assert from_python, "no capability constants found in ipc.py; this check would pass"
    assert from_python == set(declared), (
        f"one side names capabilities the other does not: {sorted(from_python ^ set(declared))}"
    )
