"""The record a fault-injection run leaves, for the tests that judge and seal it.

One shape, in one place, because two suites read it from opposite ends: the
asserter decides whether it confirms a kill and the sealer reads it once and
seals it. A copy per suite would let a record be sealable but unjudgeable, or the
reverse, without either suite noticing.

There are two kinds of record, and both live here for the same reason. The kill
record is the older one and the stronger: a process was signalled and watched out
of `/proc`. The request record says less, and has to — a run handed the managed
client a name to report by, and a live process's environment is what it can point
at. A run of either kind seals under the same artifact name, so a test that wants
to know whether the judge can tell them apart needs both from one place.

The values are the ones a real run produces — the pid and the start time it was
recorded under, and a confirmation that watched that pair leave `/proc` — rather
than invented ones, because the mutation tests below start from a record that
satisfies the case.
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
KIN_ID = "kin-01"
SESSION_ID = "session-01"
GENERATION = 1
CASE_ID = "CORE-060"
SUBJECT = "BRIDGE_FIRST_SNAPSHOT_AUTHORITY"
REQUEST_VARIABLE = "MINEKIN_BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT"
CLIENT_PID = 4320
CLIENT_STARTTIME_TICKS = 5551300


def fault_record(*, case_version: str = "a" * 64, **overrides: object) -> dict[str, object]:
    """What `tools/inject_fault.py` wrote, with named fields replaced.

    A nested override is merged into its section rather than replacing it, so a
    test can break one field of `target` or `confirmation` without restating the
    rest of the section.
    """

    executable = "/opt/minekin/bin/python3.12"
    argv = ["python", "-m", "minekin_core", "session", "start"]
    identity_digest = hashlib.sha256(
        (executable + "\0" + "\0".join(argv)).encode("utf-8")
    ).hexdigest()
    document: dict[str, object] = {
        "schema_version": 1,
        "case": {"case_id": CASE_ID, "case_version": case_version},
        "attribution": {
            "kin_id": KIN_ID,
            "run_id": RUN_ID,
            "session_id": SESSION_ID,
            "generation": GENERATION,
        },
        "target": {
            "role": "runtime_controller",
            "pid": 4242,
            "starttime_ticks": 5551212,
            "state": "S",
            "comm": "python3",
            "pid_namespace_inode": "pid:[4026531836]",
            "exe_path": executable,
            "cmdline": argv,
            "identity_digest": identity_digest,
            "parent": {"pid": 4200, "comm": "xvfb-run", "starttime_ticks": 5551000},
        },
        "signal": {"name": "SIGKILL", "number": 9, "result": "DELIVERED", "error": None},
        "outcome": "INJECTED",
        "reasons": [],
        "confirmation_strength": "IDENTITY_DISAPPEARED",
        "confirmation": {
            "method": "PROC_ENTRY_ABSENT",
            "observations": 3,
            "pid_reused": False,
            "wait_status_available": False,
        },
        "attempted_at_monotonic_ns": 1_700_000_000_123,
        "confirmed_at_monotonic_ns": 1_700_000_000_456,
        "recorded_at_monotonic_ns": 1_700_000_000_500,
        "supervisor": {
            "pid": 4200,
            "role": "runtime_controller_root",
            "starttime_ticks": 5551000,
            "pid_namespace_inode": "pid:[4026531836]",
            "exit_status": None,
            "observed": False,
        },
    }
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(document.get(key), Mapping):
            section = dict(cast(Mapping[str, object], document[key]))
            section.update(cast(Mapping[str, object], value))
            document[key] = section
        else:
            document[key] = value
    return document


def request_record(
    *,
    case_version: str = "a" * 64,
    value: str = "1",
    observed: bool = True,
    **overrides: object,
) -> dict[str, object]:
    """What `tools/inject_fault.py request` wrote, with named fields replaced.

    Built by the tool's own builder rather than written out: the fields a hand-made
    fixture would most plausibly flatter — `asked`, and which method the effect was
    seen by — are derived there, so a fixture that invented them would judge the
    reader against a shape no writer produces.
    """

    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))
    from tools.fault_injection import request_document

    document = request_document(
        subject=SUBJECT,
        value=value,
        attribution={
            "kin_id": KIN_ID,
            "run_id": RUN_ID,
            "session_id": SESSION_ID,
            "generation": GENERATION,
        },
        observed=observed,
        pid=CLIENT_PID if observed else None,
        starttime_ticks=CLIENT_STARTTIME_TICKS if observed else None,
        detail=(
            f"the managed client JVM at pid {CLIENT_PID} carries {REQUEST_VARIABLE}={value}"
            if observed
            else f"no managed client JVM below this run's root carries {REQUEST_VARIABLE}={value}"
        ),
        attempted_at_monotonic_ns=1_700_000_000_123,
        recorded_at_monotonic_ns=1_700_000_000_500,
        reasons=() if observed else ("REQUEST_NOT_IN_CLIENT_ENVIRON",),
        case={"case_id": CASE_ID, "case_version": case_version},
    )
    for key, value_override in overrides.items():
        if isinstance(value_override, Mapping) and isinstance(document.get(key), Mapping):
            section = dict(cast(Mapping[str, object], document[key]))
            section.update(cast(Mapping[str, object], value_override))
            document[key] = section
        else:
            document[key] = value_override
    return document
