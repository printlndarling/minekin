"""What a fault-injection run records, and the reader that refuses a bad one.

A fault injection is the one place in this repository where the harness ends a
process it does not own, so the record of it has to carry its own proof: which
run it was part of, which process was chosen, what was signalled, and how the
death was confirmed. Anything less makes "the runtime was killed" a claim about
the harness's intentions rather than a fact about a process.

The one thing this helper can *not* produce is a wait status. It is not the
parent of the process it kills — the process was started by the session wrapper,
not by the helper — so there is no `waitpid` to call and no exit status to read.
The honest strength is therefore `IDENTITY_DISAPPEARED`, confirmed by watching
the recorded pid *and* its start time leave `/proc`, and `WAIT_STATUS` is
reserved for a future helper that really is the parent. This module refuses a
document that claims the stronger one, rather than leaving the distinction to a
reader's good faith.

Two kinds of record live here, told apart by `category`, and a record with no
`category` at all is the first kind — which is what every sealed bundle written
before the second kind existed holds. The second is a *request* the harness made
of a process it does not end: `ADMIT-070` asks the client to report one snapshot
as not authoritative, and the thing to be evidenced is that the ask reached the
process, not that a process died. It keeps its own field names rather than
borrowing `target`, `signal` and `confirmation`, because those three say
"something was killed", and a record that said it about a snapshot report would
be the one kind of lie this file exists to make impossible. Both kinds share the
one-read discipline, because both are sealed as `fault-injection.json`.

Nothing here imports the product: this is orchestration, and the record is
evidence about the harness. `tools/` is where it belongs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import cast

SCHEMA_VERSION = 1

#: The processes a fault injection may target. `runtime_controller` is the CLI
#: that holds the runtime and the launcher in one process — this repository has
#: no separate launcher — `server_jvm` is the dedicated server, and `client_jvm`
#: is the managed Minecraft client the Fabric Bridge runs inside. The last one is
#: its own boundary rather than a second way of naming the runtime: when the
#: client dies, the Bridge dies with it, so nothing in that process is left to
#: release a key or to report a phase.
RUNTIME_CONTROLLER = "runtime_controller"
SERVER_JVM = "server_jvm"
CLIENT_JVM = "client_jvm"
ROLES = (RUNTIME_CONTROLLER, SERVER_JVM, CLIENT_JVM)

#: What became of the attempt. Only `INJECTED` means the fault happened.
INJECTED = "INJECTED"
NOT_INJECTED = "NOT_INJECTED"
AMBIGUOUS = "AMBIGUOUS"
OUTCOMES = (INJECTED, NOT_INJECTED, AMBIGUOUS)

#: How strong the confirmation is. The helper produces only the first, because
#: it cannot reap the process it killed; `WAIT_STATUS` is reserved and refused.
IDENTITY_DISAPPEARED = "IDENTITY_DISAPPEARED"
WAIT_STATUS = "WAIT_STATUS"
NO_CONFIRMATION = "NONE"
CONFIRMATION_STRENGTHS = (IDENTITY_DISAPPEARED, WAIT_STATUS, NO_CONFIRMATION)

#: How the disappearance was seen. The pid's `/proc` entry went away, the
#: process is a zombie awaiting a reap, or its pid was reused by a process with a
#: different start time — which is the only way a bare pid could have lied.
PROC_ENTRY_ABSENT = "PROC_ENTRY_ABSENT"
PROC_STATE_ZOMBIE = "PROC_STATE_ZOMBIE"
PROC_PID_REUSED = "PROC_PID_REUSED"
NO_METHOD = "NONE"
CONFIRMATION_METHODS = (PROC_ENTRY_ABSENT, PROC_STATE_ZOMBIE, PROC_PID_REUSED, NO_METHOD)

SIGKILL = "SIGKILL"
SIGNAL_NAMES = (SIGKILL,)
DELIVERED = "DELIVERED"
FAILED = "FAILED"
SIGNAL_RESULTS = (DELIVERED, FAILED)

RUNTIME_CONTROLLER_ROOT = "runtime_controller_root"
SERVER_JVM_ROOT = "server_jvm_root"
CLIENT_JVM_ROOT = "client_jvm_root"
SUPERVISOR_ROLES = (RUNTIME_CONTROLLER_ROOT, SERVER_JVM_ROOT, CLIENT_JVM_ROOT)

#: The two kinds of record this file can hold. A record that names no `category`
#: is a `PROCESS_SIGKILL` one, which is what every bundle sealed before the second
#: kind existed says — so reading those keeps meaning exactly what it meant.
PROCESS_SIGKILL = "PROCESS_SIGKILL"
CLIENT_REPORT_REQUEST = "CLIENT_REPORT_REQUEST"
CATEGORIES = (PROCESS_SIGKILL, CLIENT_REPORT_REQUEST)

#: The one request the second kind can be about, and the name it travels as. Stated
#: here as a pair rather than as two free strings because a record that named one
#: subject with another subject's variable would be a record about nothing.
BRIDGE_FIRST_SNAPSHOT_AUTHORITY = "BRIDGE_FIRST_SNAPSHOT_AUTHORITY"
NON_AUTHORITATIVE_FIRST_SNAPSHOT_VARIABLE = "MINEKIN_BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT"
ENVIRONMENT_VARIABLE_FOR_SUBJECT = {
    BRIDGE_FIRST_SNAPSHOT_AUTHORITY: NON_AUTHORITATIVE_FIRST_SNAPSHOT_VARIABLE
}

#: How the effect of a request was seen. The helper reads the environment of the
#: process the harness launched — which is the process the managed client JVM is
#: started *from*, so the name is inherited rather than merely intended. That is a
#: fact about a `/proc` entry, not about a log line: the record says the ask got
#: that far, and Core's own run document says what it did with it.
PROC_CHILD_ENVIRON = "PROC_CHILD_ENVIRON"
NOT_OBSERVED = "NOT_OBSERVED"
REQUEST_EFFECT_METHODS = (PROC_CHILD_ENVIRON, NOT_OBSERVED)

#: The spellings of a yes and of a no, and nothing else. `None` for a value outside
#: both lists, which is the case the product's own Bridge also refuses loudly: an
#: injection switch whose meaning a reader has to guess is how a run ends up being
#: evidence for a scenario nobody asked for.
YES_VALUES = ("1", "true")
NO_VALUES = ("", "0", "false")

#: Which supervisor role belongs to which target role. Defined once because both
#: ends use it — the helper builds a record from it and the reader checks a record
#: against it — and two copies of a pairing is two chances to disagree about the
#: process a record is actually about.
SUPERVISOR_FOR_ROLE = {
    RUNTIME_CONTROLLER: RUNTIME_CONTROLLER_ROOT,
    SERVER_JVM: SERVER_JVM_ROOT,
    CLIENT_JVM: CLIENT_JVM_ROOT,
}

#: The product's own rule for an opaque identifier, so a run named here is named
#: the way the ledger names it.
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CASE_ID = re.compile(r"^[A-Z][A-Z0-9-]+-[0-9]{3}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACE = re.compile(r"^pid:\[[0-9]+\]$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]*(:.+)?$")
_STATES = frozenset("RSDTZtWXKPI")

_KEYS = frozenset(
    {
        "schema_version",
        "case",
        "attribution",
        "target",
        "signal",
        "outcome",
        "reasons",
        "confirmation_strength",
        "confirmation",
        "attempted_at_monotonic_ns",
        "confirmed_at_monotonic_ns",
        "recorded_at_monotonic_ns",
        "supervisor",
    }
)
_ATTRIBUTION_KEYS = frozenset({"kin_id", "run_id", "session_id", "generation"})
#: The keys of a request record, which shares only its attribution with a kill
#: record. `target`, `signal`, `confirmation` and `supervisor` are absent on
#: purpose: a snapshot report has no process that died, no pid whose disappearance
#: could be watched, and no supervisor whose exit status could be waited for, so
#: filling those in for a request would say something untrue about a run.
_REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "category",
        "case",
        "attribution",
        "request",
        "effect",
        "reasons",
        "attempted_at_monotonic_ns",
        "recorded_at_monotonic_ns",
    }
)
_REQUEST_SECTION_KEYS = frozenset({"subject", "environment_variable", "value", "asked"})
_EFFECT_KEYS = frozenset({"observed", "method", "pid", "starttime_ticks", "detail"})
_TARGET_KEYS = frozenset(
    {
        "role",
        "pid",
        "starttime_ticks",
        "state",
        "comm",
        "pid_namespace_inode",
        "exe_path",
        "cmdline",
        "identity_digest",
        "parent",
    }
)
_PARENT_KEYS = frozenset({"pid", "comm", "starttime_ticks"})
_SIGNAL_KEYS = frozenset({"name", "number", "result", "error"})
_CONFIRMATION_KEYS = frozenset({"method", "observations", "pid_reused", "wait_status_available"})
_SUPERVISOR_KEYS = frozenset(
    {"pid", "role", "starttime_ticks", "pid_namespace_inode", "exit_status", "observed"}
)


class FaultInjectionError(Exception):
    """The record is not there, not readable, or not a record this tool accepts."""


@dataclass(frozen=True, slots=True)
class FaultInjectionRecord:
    """One validated record, with the bytes it was read from.

    The bytes travel with the parsed document so that whatever seals the record
    seals exactly what was validated, instead of reading the file a second time
    and trusting that it did not change in between.
    """

    path: Path
    raw: bytes
    document: Mapping[str, object]


def _is_int(value: object) -> bool:
    """A JSON integer. `bool` is an `int` in Python, and is not one here."""

    return isinstance(value, int) and not isinstance(value, bool)


def _integer(value: object) -> int | None:
    return cast(int, value) if _is_int(value) else None


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _section(value: object, keys: frozenset[str]) -> Mapping[str, object] | None:
    """An object with exactly these keys, or None."""

    item = _object(value)
    return item if item is not None and frozenset(item) == keys else None


def _object(value: object) -> Mapping[str, object] | None:
    """An object with string keys, or None — the one place JSON becomes typed."""

    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else None


def _list_of_text(value: object) -> list[object] | None:
    return cast(list[object], value) if isinstance(value, list) else None


def _oid(value: object) -> bool:
    text = _text(value)
    return text is not None and _ID.fullmatch(text) is not None


def _case_violations(value: object) -> bool:
    """Whether the `case` section is absent or a usable attribution."""

    if value is None:
        return True
    section = _section(value, frozenset({"case_id", "case_version"}))
    if section is None:
        return False
    case_id, case_version = _text(section["case_id"]), _text(section["case_version"])
    return (
        case_id is not None
        and _CASE_ID.fullmatch(case_id) is not None
        and case_version is not None
        and _HEX64.fullmatch(case_version) is not None
    )


def _attribution_is_usable(value: object) -> bool:
    section = _section(value, _ATTRIBUTION_KEYS)
    if section is None:
        return False
    generation = _integer(section["generation"])
    return (
        _oid(section["kin_id"])
        and _oid(section["run_id"])
        and _oid(section["session_id"])
        and generation is not None
        and generation >= 1
    )


def _target_is_usable(value: object) -> bool:
    section = _section(value, _TARGET_KEYS)
    if section is None:
        return False
    parent = _section(section["parent"], _PARENT_KEYS)
    if parent is None:
        return False
    parent_pid, parent_start = _integer(parent["pid"]), _integer(parent["starttime_ticks"])
    argv = _list_of_text(section["cmdline"])
    role, state = _text(section["role"]), _text(section["state"])
    namespace = _text(section["pid_namespace_inode"])
    digest = _text(section["identity_digest"])
    exe_path, comm = _text(section["exe_path"]), _text(section["comm"])
    starttime = _integer(section["starttime_ticks"])
    calculated_digest = None
    if exe_path is not None and argv is not None and all(isinstance(item, str) for item in argv):
        material = exe_path + "\0" + "\0".join(cast(list[str], argv))
        calculated_digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return (
        role in ROLES
        and (_integer(section["pid"]) or 0) > 1
        and starttime is not None
        and starttime >= 0
        and state is not None
        and len(state) == 1
        and state in _STATES
        and comm is not None
        and bool(comm)
        and namespace is not None
        and _NAMESPACE.fullmatch(namespace) is not None
        and exe_path is not None
        and bool(exe_path)
        and argv is not None
        and bool(argv)
        # An argv element may be empty, and a real client's is: the frozen
        # offline launch passes an empty value as its own element (`--clientId`
        # followed by an empty one), which is exactly what the launcher contract
        # requires so that an empty value cannot be mistaken for an absent
        # option. Requiring every element to be non-empty made a real client's
        # identity unrecordable — and, because a refusal that names a target is
        # also validated before it is written, it made the reason for refusing
        # unrecordable too.
        and all(_text(item) is not None for item in argv)
        and digest is not None
        and _HEX64.fullmatch(digest) is not None
        and digest == calculated_digest
        and parent_pid is not None
        and parent_pid > 0
        and isinstance(parent["comm"], str)
        and parent_start is not None
        and parent_start >= 0
    )


def _signal_is_usable(value: object) -> bool:
    if value is None:
        return True
    section = _section(value, _SIGNAL_KEYS)
    if section is None:
        return False
    if _text(section["name"]) not in SIGNAL_NAMES:
        return False
    if _integer(section["number"]) != 9:
        return False
    result, error = _text(section["result"]), section["error"]
    if result not in SIGNAL_RESULTS:
        return False
    if result == DELIVERED:
        return error is None
    return isinstance(error, str) and bool(error)


def _reasons_are_usable(value: object) -> bool:
    items = _list_of_text(value)
    if items is None:
        return False
    return all(
        _text(item) is not None and _REASON.fullmatch(cast(str, item)) is not None for item in items
    )


def _confirmation_is_usable(value: object) -> bool:
    if value is None:
        return True
    section = _section(value, _CONFIRMATION_KEYS)
    if section is None:
        return False
    observations = _integer(section["observations"])
    method = _text(section["method"])
    return (
        method in CONFIRMATION_METHODS
        and observations is not None
        and observations >= 0
        and isinstance(section["pid_reused"], bool)
        and section["pid_reused"] is (method == PROC_PID_REUSED)
        and isinstance(section["wait_status_available"], bool)
        and section["wait_status_available"] is False
    )


def _supervisor_is_usable(value: object) -> bool:
    section = _section(value, _SUPERVISOR_KEYS)
    if section is None:
        return False
    pid = _integer(section["pid"])
    exit_status = section["exit_status"]
    observed = section["observed"]
    starttime = _integer(section["starttime_ticks"])
    namespace = _text(section["pid_namespace_inode"])
    return (
        pid is not None
        and pid > 0
        and _text(section["role"]) in SUPERVISOR_ROLES
        and starttime is not None
        and starttime >= 0
        and namespace is not None
        and _NAMESPACE.fullmatch(namespace) is not None
        and isinstance(observed, bool)
        and (exit_status is None or _is_int(exit_status))
        # Observed and recorded are the same statement, said twice on purpose: a
        # supervisor whose exit status was not obtained is not one that exited.
        and (observed == (exit_status is not None))
    )


def _outcome_violations(record: Mapping[str, object]) -> frozenset[str]:
    """The rules that tie the outcome to what was actually seen.

    These are the ones a schema cannot state: whether the outcome, the signal and
    the confirmation tell the same story is a comparison between fields, and it
    is the comparison that matters. An `INJECTED` document whose own confirmation
    is missing is the exact failure the record exists to make impossible.
    """

    found: set[str] = set()
    outcome = _text(record.get("outcome"))
    if outcome not in OUTCOMES:
        found.add("INVALID_OUTCOME")
    strength = _text(record.get("confirmation_strength"))
    if strength not in CONFIRMATION_STRENGTHS:
        found.add("INVALID_CONFIRMATION_STRENGTH")

    confirmation = record.get("confirmation")
    section = _object(confirmation)
    claims_wait = section is not None and section.get("wait_status_available") is True
    if strength == WAIT_STATUS or claims_wait:
        # No document this helper writes may claim a wait status: it is not the
        # parent of what it killed, so it has no exit status to report.
        found.add("WAIT_STATUS_UNAVAILABLE")

    target = _object(record.get("target"))
    supervisor = _object(record.get("supervisor"))
    if target is not None and supervisor is not None:
        target_role = _text(target.get("role"))
        expected_supervisor = (
            SUPERVISOR_FOR_ROLE.get(target_role) if target_role is not None else None
        )
        if expected_supervisor is not None and supervisor.get("role") != expected_supervisor:
            found.add("SUPERVISOR_ROLE_MISMATCH")

    listed = _list_of_text(record.get("reasons")) or []
    signal = _object(record.get("signal"))
    delivered = signal is not None and signal.get("result") == DELIVERED
    confirmed_at = record.get("confirmed_at_monotonic_ns")

    if outcome == INJECTED:
        if listed:
            found.add("REASONS_NOT_FOR_THIS_OUTCOME")
        method = section.get("method") if section is not None else None
        observations = section.get("observations") if section is not None else None
        consistent = (
            record.get("target") is not None
            and delivered
            and strength == IDENTITY_DISAPPEARED
            and method in (PROC_ENTRY_ABSENT, PROC_STATE_ZOMBIE, PROC_PID_REUSED)
            and _is_int(observations)
            and cast(int, observations) >= 1
            and _is_int(confirmed_at)
        )
        if not consistent:
            found.add("CONFIRMATION_NOT_FOR_THIS_OUTCOME")
    elif outcome in (AMBIGUOUS, NOT_INJECTED):
        if not listed:
            found.add("REASONS_MISSING")
        quiet = (
            confirmed_at is None
            and strength == NO_CONFIRMATION
            and confirmation is None
            and (outcome != AMBIGUOUS or signal is None)
        )
        if not quiet:
            found.add("CONFIRMATION_NOT_FOR_THIS_OUTCOME")
    return frozenset(found)


def yes_or_no(value: object) -> bool | None:
    """What a switch's value means, or None when it means neither a yes nor a no.

    Both ends of the record use this — the writer, so that a `0` cannot be filed as
    an injection, and the reader, so that a document cannot say `asked: true` about
    a value that says no. Kept here rather than in the caller because the answer has
    to be the same on both sides of that hand-off.
    """

    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text in YES_VALUES:
        return True
    if text in NO_VALUES:
        return False
    return None


def _request_is_usable(value: object) -> bool:
    section = _section(value, _REQUEST_SECTION_KEYS)
    if section is None:
        return False
    subject = _text(section["subject"])
    if subject not in ENVIRONMENT_VARIABLE_FOR_SUBJECT:
        return False
    if _text(section["environment_variable"]) != ENVIRONMENT_VARIABLE_FOR_SUBJECT[subject]:
        return False
    meaning = yes_or_no(section["value"])
    asked = section["asked"]
    return meaning is not None and isinstance(asked, bool) and asked is meaning


def _effect_is_usable(value: object) -> bool:
    section = _section(value, _EFFECT_KEYS)
    if section is None:
        return False
    observed = section["observed"]
    method, detail = _text(section["method"]), _text(section["detail"])
    if not isinstance(observed, bool) or method not in REQUEST_EFFECT_METHODS:
        return False
    # The sentence the effect is told in is required either way: an observation that
    # saw nothing still has to say what it looked for and failed to find.
    if detail is None or not detail:
        return False
    pid, starttime = _integer(section["pid"]), _integer(section["starttime_ticks"])
    if observed:
        return (
            method == PROC_CHILD_ENVIRON
            and pid is not None
            and pid > 1
            and starttime is not None
            and starttime >= 0
        )
    return method == NOT_OBSERVED and pid is None and starttime is None


def _request_violations(record: Mapping[str, object]) -> frozenset[str]:
    """The rules that tie what was asked to what was seen, for a request record.

    The kill rules cannot stand in for these: `INJECTED` there means a process is
    gone, and nothing here claims that. What this states instead is that an effect
    presupposes a request — `asked: false` beside `observed: true` is the exact
    false positive the reviewed scenario would otherwise allow, because it is how a
    run handed `0` would read as one handed `1`.
    """

    found: set[str] = set()
    request = _object(record.get("request"))
    effect = _object(record.get("effect"))
    listed = _list_of_text(record.get("reasons")) or []
    if request is not None and effect is not None:
        asked = request.get("asked") is True
        observed = effect.get("observed") is True
        if observed and not asked:
            found.add("EFFECT_WITHOUT_REQUEST")
        if observed and listed:
            found.add("REASONS_NOT_FOR_THIS_OUTCOME")
        if not observed and not listed:
            found.add("REASONS_MISSING")
    return frozenset(found)


def validate(document: object) -> tuple[str, ...]:
    """Every rule the record must satisfy, as codes naming what is wrong.

    Names rather than prose: the sealer refuses a record by naming the rule it
    broke, and a test that mutates one field has to be able to say which field it
    expects to be caught for.
    """

    if not isinstance(document, Mapping):
        return ("NOT_AN_OBJECT",)
    record = cast(Mapping[str, object], document)
    found: set[str] = set()

    # A record that names no category is a kill record, and reading one is exactly
    # what it was before request records existed. The explicit spelling is accepted
    # so that a writer can say which kind it wrote instead of leaning on absence.
    declared = record.get("category")
    is_request = declared == CLIENT_REPORT_REQUEST
    if declared is not None and declared not in CATEGORIES:
        found.add("INVALID_CATEGORY")
    if is_request:
        keys: frozenset[str] = _REQUEST_KEYS
    elif declared is None:
        keys = _KEYS
    else:
        # A kill record may name its category, but only the request record carries
        # it as a field of its own.
        keys = _KEYS | frozenset({"category"})

    if set(record) - keys:
        found.add("UNKNOWN_FIELD")
    if keys - set(record):
        found.add("MISSING_FIELD")
    if not (_is_int(record.get("schema_version")) and record["schema_version"] == SCHEMA_VERSION):
        found.add("SCHEMA_VERSION_UNSUPPORTED")
    if not _case_violations(record.get("case")):
        found.add("INVALID_CASE")
    if not _attribution_is_usable(record.get("attribution")):
        found.add("INVALID_ATTRIBUTION")
    if not _reasons_are_usable(record.get("reasons")):
        found.add("INVALID_REASONS")

    attempted = _integer(record.get("attempted_at_monotonic_ns"))
    recorded = _integer(record.get("recorded_at_monotonic_ns"))
    clock_ordered = (
        attempted is not None and attempted >= 0 and recorded is not None and recorded >= attempted
    )
    if not clock_ordered:
        found.add("INVALID_CLOCK")

    if is_request:
        if not _request_is_usable(record.get("request")):
            found.add("INVALID_REQUEST")
        if not _effect_is_usable(record.get("effect")):
            found.add("INVALID_EFFECT")
        found |= _request_violations(record)
        return tuple(sorted(found))

    if record.get("target") is not None and not _target_is_usable(record.get("target")):
        found.add("INVALID_TARGET")
    if not _confirmation_is_usable(record.get("confirmation")):
        found.add("INVALID_CONFIRMATION")
    if not _supervisor_is_usable(record.get("supervisor")):
        found.add("INVALID_SUPERVISOR")

    # A signal is absent for a kill that never happened, and present otherwise;
    # `_signal_is_usable` already holds the pair of result and error together.
    if not _signal_is_usable(record.get("signal")):
        found.add("INVALID_SIGNAL")

    if clock_ordered and attempted is not None and recorded is not None:
        confirmed = record.get("confirmed_at_monotonic_ns", None)
        if confirmed is not None:
            confirmed_at = _integer(confirmed)
            if confirmed_at is None or confirmed_at < attempted or confirmed_at > recorded:
                found.add("CLOCK_ORDER_INVALID")

    found |= _outcome_violations(record)
    return tuple(sorted(found))


def request_document(
    *,
    subject: str,
    value: str,
    attribution: Mapping[str, object],
    observed: bool,
    pid: int | None,
    starttime_ticks: int | None,
    detail: str,
    attempted_at_monotonic_ns: int,
    recorded_at_monotonic_ns: int,
    reasons: tuple[str, ...] = (),
    case: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """One request record, built in the shape this module's reader accepts.

    The writer derives `asked` from the value and the method from whether anything
    was seen, rather than taking either as an argument: those two are the fields a
    hand-written document would most plausibly get wrong in the flattering
    direction, and a builder that lets a caller state them independently is a
    builder that lets a run claim an injection it was not asked for. The
    attribution is the helper's own section rather than four arguments, because
    what makes a run nameable is the ledger's question, not this file's.
    """

    meaning = yes_or_no(value)
    if meaning is None:
        raise FaultInjectionError(f"INVALID_VALUE: {value!r} names neither a yes nor a no")
    environment_variable = ENVIRONMENT_VARIABLE_FOR_SUBJECT.get(subject)
    if environment_variable is None:
        raise FaultInjectionError(f"UNKNOWN_SUBJECT: {subject} is not a request this tool knows")
    method = PROC_CHILD_ENVIRON if observed else NOT_OBSERVED
    return {
        "schema_version": SCHEMA_VERSION,
        "category": CLIENT_REPORT_REQUEST,
        "case": case,
        "attribution": dict(attribution),
        "request": {
            "subject": subject,
            "environment_variable": environment_variable,
            "value": value,
            "asked": meaning,
        },
        "effect": {
            "observed": observed,
            "method": method,
            "pid": pid,
            "starttime_ticks": starttime_ticks,
            "detail": detail,
        },
        "reasons": list(reasons),
        "attempted_at_monotonic_ns": attempted_at_monotonic_ns,
        "recorded_at_monotonic_ns": recorded_at_monotonic_ns,
    }


def dump_record(document: Mapping[str, object]) -> bytes:
    """The record as the bytes that get written, one way and no other."""

    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def parse_record(text: str) -> Mapping[str, object]:
    """One record from text a caller already holds, validated the same way.

    The sealer reads the file once and hands the bytes it is about to seal to the
    asserter, so the judgement and the artifact are the same snapshot. This is the
    half of that hand-off that turns the text back into a record.
    """

    try:
        document = _object(json.loads(text))
    except json.JSONDecodeError as error:
        raise FaultInjectionError(f"NOT_JSON: the record is not JSON: {error}") from error
    if document is None:
        raise FaultInjectionError("NOT_AN_OBJECT: the record is not an object")
    violations = validate(document)
    if violations:
        raise FaultInjectionError(
            "INVALID: the record is not one this tool accepts: " + ", ".join(violations)
        )
    return document


def read_record(path: Path) -> FaultInjectionRecord:
    """Read one record, refusing anything that is not exactly a record.

    Symlinks are refused rather than followed: the sealer has to be able to say
    that the bytes it sealed are the bytes it judged, and a name that resolves to
    a file somebody else can swap is not that.
    """

    try:
        before = path.lstat()
    except OSError as error:
        raise FaultInjectionError(f"UNREADABLE: {path} cannot be read: {error}") from error
    if stat.S_ISLNK(before.st_mode):
        raise FaultInjectionError(
            f"SYMLINK: {path} is a symlink; the record must be the file it names"
        )
    if not stat.S_ISREG(before.st_mode):
        raise FaultInjectionError(f"NOT_A_FILE: {path} is not a regular file")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise FaultInjectionError(f"UNREADABLE: {path} cannot be read: {error}") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise FaultInjectionError(f"NOT_A_FILE: {path} is not a regular file")
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise FaultInjectionError(
                f"CHANGED: {path} changed between inspection and open; refusing the record"
            )
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            raw = stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FaultInjectionError(f"NOT_JSON: {path} is not UTF-8 text: {error}") from error
    return FaultInjectionRecord(path=path, raw=raw, document=parse_record(text))


def write_record(path: Path, document: Mapping[str, object]) -> None:
    """Write one record, whole, and never over a symlink.

    Written beside itself and renamed, so a reader never sees half a record: the
    sealer runs while the harness may still be annotating, and a partial file
    would be judged as a complete one with fields missing.
    """

    violations = validate(document)
    if violations:
        raise FaultInjectionError(
            "INVALID: refusing to write a record that is not one: " + ", ".join(violations)
        )
    try:
        if stat.S_ISLNK(path.lstat().st_mode):
            raise FaultInjectionError(f"SYMLINK: {path} is a symlink; refusing to write through it")
    except FileNotFoundError:
        pass
    except OSError as error:
        raise FaultInjectionError(f"UNREADABLE: {path} cannot be inspected: {error}") from error

    payload = dump_record(document)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".partial")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    except BaseException:
        with suppress(OSError):
            os.unlink(temporary)
        raise
