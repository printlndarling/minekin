"""Kill one process belonging to this run, and record the proof that it died.

This is the only thing in the repository that signals a process it did not
start, and it exists because the two ways that used to be done here were both
wrong in the same way: they guessed. `pkill -f "minekin_core session start"`
searches every process in the container, so a second session's runtime, or the
`session stop` a harness ran afterwards, is as good a match as the one the run
means. `pgrep -P <tool> | head -1` assumes the first child is the JVM, and it is
not: the tool has a wrapper, and a JVM may be a grandchild. Neither of those can
say *which* process it killed, and a fault injection that cannot name its target
has not injected anything.

So the target is not searched for. It is derived: from a pid this run already
holds (the session wrapper, or the server tool), by walking that process's
descendants in `/proc`, and then by requiring that exactly *one* of them matches
the role's own command line. Zero is a refusal and more than one is a refusal,
and a refusal never signals anything.

What the helper can prove is bounded, and the bound is written down rather than
papered over. It is not the parent of the process it kills, so `waitpid` is not
available to it and it can never report an exit status or a termination signal.
What it can do is record the pid's identity — the pid, its start time from
`/proc/<pid>/stat`, its pid namespace, its resolved executable and its argv — and
then watch for that identity to leave `/proc`. `pid` alone is not an identity;
`pid` plus `starttime_ticks` is, which is why the confirmation tells a reused pid
apart from a survived process instead of trusting a bare number. The resulting
`confirmation_strength` is `IDENTITY_DISAPPEARED` and never `WAIT_STATUS`.

Nothing about ordering is decided by the clock. The record carries
`CLOCK_MONOTONIC` readings because a reader wants to know when things happened,
but what makes the confirmation a confirmation is the sequence of `/proc`
observations — the bounded poll, and the observation that ended it — not the
timestamps. A wall clock would be worse than useless here for the same reason.

The exit status of the process the target was found under *is* recorded when the
runner has it: the runner is the one that `wait`s, so it annotates the record
afterwards with `annotate`. Until then the record says the status was not
observed, which is the truth rather than a zero standing in for it.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

# The record's own shape and reader live beside this file, and the sealer imports
# them by the same route so the writer and the reader cannot be two dialects.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fault_injection
from fault_injection import (
    AMBIGUOUS,
    DELIVERED,
    FAILED,
    IDENTITY_DISAPPEARED,
    INJECTED,
    NO_CONFIRMATION,
    NOT_INJECTED,
    PROC_ENTRY_ABSENT,
    PROC_PID_REUSED,
    PROC_STATE_ZOMBIE,
    RUNTIME_CONTROLLER,
    SERVER_JVM,
    SIGKILL,
    FaultInjectionError,
)

#: How many times the confirmation looks before giving up, and how long it waits
#: between looks. Ten seconds is far longer than a SIGKILL needs; the bound is
#: there so a target that somehow survives ends the run with an answer rather
#: than hanging it.
DEFAULT_ROUNDS = 200
DEFAULT_INTERVAL = 0.05

#: A walk that finds this many descendants has left the subtree it was given, or
#: something is forking in a loop. Either way the answer is "cannot tell", not
#: "keep going".
MAX_DESCENDANTS = 4096

#: SIGKILL's number. Written out rather than read from the `signal` module, which
#: does not define it on Windows: this helper reads `/proc` and so only ever runs
#: on Linux, but the suite that tests its decisions runs everywhere, and an import
#: that fails on the test host would leave those decisions untested.
SIGKILL_NUMBER = 9

#: The role a supervisor play in the record, from the role of its target.
_SUPERVISOR_ROLE = {RUNTIME_CONTROLLER: "runtime_controller_root", SERVER_JVM: "server_jvm_root"}

#: What an observation of the target found. `ALIVE` is not in the record's
#: vocabulary: it is the state that keeps the poll going.
_ALIVE = "ALIVE"

# A present proc entry that could not be parsed is not an absent process.  The
# distinction is deliberately internal: callers keep polling and ultimately
# refuse to confirm the fault instead of turning a transient/partial read into
# proof of death.
_UNREADABLE = "UNREADABLE"


class Procfs(Protocol):
    """The three `/proc` questions this helper asks, so a test can answer them."""

    def children(self, pid: int) -> tuple[int, ...]: ...

    def read_bytes(self, pid: int, name: str) -> bytes | None: ...

    def read_link(self, pid: int, name: str) -> str | None: ...


class _WalkTooLarge(Exception):
    """The descendant walk ran away; the subtree it was given was not one."""


@dataclass(frozen=True, slots=True)
class StatLine:
    """The fields of `/proc/<pid>/stat` this helper reads."""

    comm: str
    state: str
    parent_pid: int
    starttime_ticks: int


@dataclass(frozen=True, slots=True)
class ProcIdentity:
    """Everything that makes a pid a process rather than a number.

    A pid is reusable, so `/proc/<pid>` alone cannot say whether the process
    behind it is the one that was looked at. The start time can: it is read from
    the same stat line as the pid and is never reissued within a boot.
    """

    pid: int
    comm: str
    state: str
    parent_pid: int
    starttime_ticks: int
    exe_path: str
    cmdline: tuple[str, ...]
    pid_namespace_inode: str

    def digest(self) -> str:
        """A digest of the executable and the arguments, which is what it *is*."""

        material = self.exe_path + "\0" + "\0".join(self.cmdline)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class RealProcfs:
    """`/proc`, read the way the kernel documents it.

    Descendants come from `/proc/<pid>/task/*/children`, which is scoped to one
    process: the tree is walked outward from a pid the run already holds, and
    nothing here ever looks for a candidate across the container. The scan that
    fills in when the kernel was built without `CONFIG_PROC_CHILDREN` answers the
    same question — who is this pid's parent — for the pids already in hand.
    """

    def children(self, pid: int) -> tuple[int, ...]:
        found: set[int] = set()
        for task in sorted(Path(f"/proc/{pid}/task").glob("*")):
            try:
                listed = (task / "children").read_text(encoding="ascii", errors="replace")
            except OSError:
                continue
            found.update(int(token) for token in listed.split() if token.isdigit())
        if found:
            return tuple(sorted(found))
        return self._children_by_parent_scan(pid)

    def read_bytes(self, pid: int, name: str) -> bytes | None:
        try:
            return Path(f"/proc/{pid}/{name}").read_bytes()
        except OSError:
            return None

    def read_link(self, pid: int, name: str) -> str | None:
        try:
            return os.readlink(f"/proc/{pid}/{name}")
        except OSError:
            return None

    def _children_by_parent_scan(self, pid: int) -> tuple[int, ...]:
        found: list[int] = []
        try:
            entries = list(Path("/proc").iterdir())
        except OSError:
            return ()
        for entry in entries:
            if not entry.name.isdigit():
                continue
            raw = self.read_bytes(int(entry.name), "stat")
            if raw is None:
                continue
            try:
                parsed = parse_stat(raw.decode("utf-8", errors="replace"))
            except ValueError:
                continue
            if parsed.parent_pid == pid:
                found.append(int(entry.name))
        return tuple(sorted(found))


def parse_stat(text: str) -> StatLine:
    """One `/proc/<pid>/stat` line, parsed from the end of `comm` forwards.

    `comm` is the process's own name, it may contain spaces and parentheses, and
    it is the reason a naive split on whitespace reads the wrong fields. The
    kernel brackets it between the first `(` and the last `)`, so the fields
    after it are counted from there: `state` is field 3 and therefore the first
    token after the bracket, and the start time is field 22.
    """

    opening, closing = text.find("("), text.rfind(")")
    if opening < 0 or closing < opening:
        raise ValueError("this is not a /proc stat line: comm is not bracketed")
    fields = text[closing + 2 :].split()
    if len(fields) < 20:
        raise ValueError("this is not a /proc stat line: too few fields after comm")
    return StatLine(
        comm=text[opening + 1 : closing],
        state=fields[0],
        parent_pid=int(fields[1]),
        starttime_ticks=int(fields[19]),
    )


def parse_cmdline(raw: bytes) -> tuple[str, ...]:
    """The arguments the kernel kept, which is what the process was started as."""

    if not raw:
        return ()
    parts = raw.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    return tuple(part.decode("utf-8", errors="replace") for part in parts)


def read_identity(procfs: Procfs, pid: int) -> ProcIdentity | None:
    """This pid's identity, or None when there is no process to name.

    A zombie is an identity too — it is a process that has terminated and is
    waiting to be reaped — but it has no argv and no executable link, so it is
    read from the stat line alone. It never matches a role, and it is exactly
    what the confirmation must be able to see.
    """

    raw = procfs.read_bytes(pid, "stat")
    if raw is None:
        return None
    try:
        parsed = parse_stat(raw.decode("utf-8", errors="replace"))
    except ValueError:
        return None
    namespace = procfs.read_link(pid, "ns/pid")
    if namespace is None:
        return None
    cmdline = parse_cmdline(procfs.read_bytes(pid, "cmdline") or b"")
    if parsed.state == "Z":
        return ProcIdentity(
            pid=pid,
            comm=parsed.comm,
            state=parsed.state,
            parent_pid=parsed.parent_pid,
            starttime_ticks=parsed.starttime_ticks,
            exe_path="",
            cmdline=cmdline,
            pid_namespace_inode=namespace,
        )
    exe_path = procfs.read_link(pid, "exe")
    if not cmdline or not exe_path:
        return None
    return ProcIdentity(
        pid=pid,
        comm=parsed.comm,
        state=parsed.state,
        parent_pid=parsed.parent_pid,
        starttime_ticks=parsed.starttime_ticks,
        exe_path=exe_path,
        cmdline=cmdline,
        pid_namespace_inode=namespace,
    )


def observe(procfs: Procfs, pid: int, starttime_ticks: int) -> str:
    """What is behind this pid now: alive, gone, reaped, or somebody else."""

    raw = procfs.read_bytes(pid, "stat")
    if raw is None:
        return PROC_ENTRY_ABSENT
    try:
        parsed = parse_stat(raw.decode("utf-8", errors="replace"))
    except ValueError:
        return _UNREADABLE
    if parsed.starttime_ticks != starttime_ticks:
        return PROC_PID_REUSED
    if parsed.state == "Z":
        return PROC_STATE_ZOMBIE
    return _ALIVE


def descendants(procfs: Procfs, root_pid: int) -> tuple[int, ...]:
    """Every process below this one, breadth first, root excluded."""

    seen = {root_pid}
    ordered: list[int] = []
    queue = [root_pid]
    while queue:
        pid = queue.pop(0)
        for child in procfs.children(pid):
            if child in seen:
                continue
            seen.add(child)
            ordered.append(child)
            queue.append(child)
            if len(ordered) > MAX_DESCENDANTS:
                raise _WalkTooLarge(f"more than {MAX_DESCENDANTS} descendants of {root_pid}")
    return tuple(ordered)


def _is_runtime_controller(argv: Sequence[str]) -> bool:
    """`python -m minekin_core session start`, and not some other Core command.

    `session stop` is the same module and the same verb-less prefix, and killing
    it would be killing a different invocation of the same program — so `stop` is
    excluded by name rather than by hoping it never appears.
    """

    return any(
        argv[index : index + 4] == ("-m", "minekin_core", "session", "start")
        for index in range(len(argv) - 3)
    )


def same_process_identity(before: ProcIdentity, after: ProcIdentity | None) -> bool:
    """Whether two reads name the same signal target.

    `/proc/<pid>/stat` state is intentionally excluded: an ordinary process can
    move between runnable and sleeping between consecutive reads.  PID,
    start-time, namespace, executable and argv are the stable identity fields;
    requiring the transient state to match made a valid injection fail at
    random without adding any protection against PID reuse.
    """

    if after is None:
        return False
    return (
        before.pid,
        before.comm,
        before.parent_pid,
        before.starttime_ticks,
        before.exe_path,
        before.cmdline,
        before.pid_namespace_inode,
    ) == (
        after.pid,
        after.comm,
        after.parent_pid,
        after.starttime_ticks,
        after.exe_path,
        after.cmdline,
        after.pid_namespace_inode,
    )


def _is_server_jvm(argv: Sequence[str], exe_path: str) -> bool:
    """The pinned dedicated-server JVM, not merely any Java-family program."""

    names = [Path(exe_path).name] if exe_path else []
    if argv:
        names.append(Path(argv[0]).name)
    is_java = any(name == "java" for name in names)
    launches_server = any(
        argv[index] == "-jar" and argv[index + 1] == "/server/server.jar"
        for index in range(len(argv) - 1)
    )
    return is_java and launches_server


def identity_matches_role(identity: ProcIdentity, role: str) -> bool:
    """Apply the role predicate to one already captured identity snapshot."""

    if role == RUNTIME_CONTROLLER:
        return _is_runtime_controller(identity.cmdline)
    return _is_server_jvm(identity.cmdline, identity.exe_path)


def matches_role(procfs: Procfs, pid: int, role: str) -> bool:
    argv = parse_cmdline(procfs.read_bytes(pid, "cmdline") or b"")
    if not argv:
        return False
    if role == RUNTIME_CONTROLLER:
        # Only the command line is consulted, so that looking for a candidate
        # never reads an identity: the target's identity is read exactly twice,
        # once to record it and once to re-check it before the signal.
        return _is_runtime_controller(argv)
    return _is_server_jvm(argv, procfs.read_link(pid, "exe") or "")


def find_candidates(procfs: Procfs, root_pid: int, role: str) -> tuple[int, ...]:
    """Every descendant of `root_pid` that is this role, by its own command line."""

    return tuple(pid for pid in descendants(procfs, root_pid) if matches_role(procfs, pid, role))


def _case_section(
    case_id: str, case_file: Path | None, reasons: list[str]
) -> Mapping[str, object] | None:
    """The case this run was executed for, from the case itself rather than a guess."""

    if not case_id:
        return None
    if case_file is None:
        reasons.append("CASE_FILE_UNREADABLE")
        return None
    # Imported here rather than at module scope: this is the only place the
    # helper needs the product, and the record it writes does not depend on it.
    from minekin_core.adapters.evidence.promotion import load_case_manifest
    from minekin_core.domain.errors import MinekinError

    try:
        definition = load_case_manifest(case_file)
    except (OSError, MinekinError):
        reasons.append("CASE_FILE_UNREADABLE")
        return None
    if definition.case_id != case_id:
        reasons.append(f"CASE_FILE_MISMATCH:{definition.case_id}")
        return None
    return {"case_id": definition.case_id, "case_version": definition.digest}


def _attribution(
    *,
    ledger: Path,
    kin_id: str,
    run_id: str,
    session_id: str,
    generation: int,
    reasons: list[str],
) -> Mapping[str, object]:
    """Which run this is, cross-checked against the ledger's own place on disk.

    The caller reads the ledger, because the ledger is the product's record and
    the tool that owns the run is the one that reads it. What is checked here is
    the one thing the path can disagree with: a ledger under `kin-09` that claims
    to be about `kin-01` is a run that cannot be named, and a record that cannot
    name its run cannot be judged against it.
    """

    if not ledger.is_file():
        reasons.append("LEDGER_UNREADABLE")
    elif ledger.parent.name != kin_id:
        # The directory is named rather than interpolated blindly: a path with no
        # directory component has an empty name, and a reason ending in a bare
        # colon is not a reason this repository's reader accepts — so the helper
        # would refuse to write a record it had just built.
        reasons.append(f"LEDGER_NOT_THE_KIN:{ledger.parent.name or 'NO_DIRECTORY'}")
    for field, value in (("kin_id", kin_id), ("run_id", run_id), ("session_id", session_id)):
        if not value:
            reasons.append(f"ATTRIBUTION_INCOMPLETE:{field}")
    if generation < 1:
        reasons.append("ATTRIBUTION_INCOMPLETE:generation")
    return {
        "kin_id": kin_id,
        "run_id": run_id,
        "session_id": session_id,
        "generation": generation,
    }


def _document(
    *,
    case: Mapping[str, object] | None,
    attribution: Mapping[str, object],
    target: Mapping[str, object] | None,
    signal_section: Mapping[str, object] | None,
    outcome: str,
    reasons: Sequence[str],
    strength: str,
    confirmation: Mapping[str, object] | None,
    attempted: int,
    confirmed: int | None,
    supervisor: Mapping[str, object],
    recorded: int,
) -> dict[str, object]:
    return {
        "schema_version": fault_injection.SCHEMA_VERSION,
        "case": None if case is None else dict(case),
        "attribution": dict(attribution),
        "target": None if target is None else dict(target),
        "signal": None if signal_section is None else dict(signal_section),
        "outcome": outcome,
        "reasons": list(reasons),
        "confirmation_strength": strength,
        "confirmation": None if confirmation is None else dict(confirmation),
        "attempted_at_monotonic_ns": attempted,
        "confirmed_at_monotonic_ns": confirmed,
        "recorded_at_monotonic_ns": recorded,
        "supervisor": dict(supervisor),
    }


def _refusal(
    *,
    case: Mapping[str, object] | None,
    attribution: Mapping[str, object],
    target: Mapping[str, object] | None,
    reasons: Sequence[str],
    supervisor: Mapping[str, object],
    attempted: int,
    recorded: int,
) -> dict[str, object]:
    """A document for a kill that was refused: nothing was signalled, and it says so."""

    return _document(
        case=case,
        attribution=attribution,
        target=target,
        signal_section=None,
        outcome=AMBIGUOUS,
        reasons=reasons,
        strength=NO_CONFIRMATION,
        confirmation=None,
        attempted=attempted,
        confirmed=None,
        supervisor=supervisor,
        recorded=recorded,
    )


def _supervisor(
    root_pid: int,
    role: str,
    root_starttime_ticks: int,
    root_pid_namespace_inode: str,
    *,
    exit_status: int | None = None,
    observed: bool = False,
) -> Mapping[str, object]:
    return {
        "pid": root_pid,
        "role": _SUPERVISOR_ROLE[role],
        "starttime_ticks": root_starttime_ticks,
        "pid_namespace_inode": root_pid_namespace_inode,
        "exit_status": exit_status,
        "observed": observed,
    }


def _parent_of(procfs: Procfs, identity: ProcIdentity) -> Mapping[str, object]:
    """The target's parent, as far as it can be named.

    The parent is the process the walk came through, so it is already known by
    pid; its own identity is recorded when it can be read and left empty when it
    cannot, rather than filled with a plausible zero.
    """

    parent = read_identity(procfs, identity.parent_pid)
    return {
        "pid": identity.parent_pid,
        "comm": "" if parent is None else parent.comm,
        "starttime_ticks": 0 if parent is None else parent.starttime_ticks,
    }


def inject(
    *,
    root_pid: int,
    root_starttime_ticks: int,
    root_pid_namespace_inode: str,
    role: str,
    case_id: str,
    case_file: Path | None,
    ledger: Path,
    kin_id: str,
    run_id: str,
    session_id: str,
    generation: int,
    procfs: Procfs,
    kill: Callable[[int], str | None],
    monotonic_ns: Callable[[], int],
    sleep: Callable[[float], None],
    rounds: int = DEFAULT_ROUNDS,
    interval: float = DEFAULT_INTERVAL,
) -> dict[str, object]:
    """Find this run's process for `role`, kill it, and return the record.

    Pure with respect to the world except for `kill`: the record is returned
    rather than written, so what it says can be judged without a run happening.
    """

    attempted = monotonic_ns()
    reasons: list[str] = []
    case = _case_section(case_id, case_file, reasons)
    attribution = _attribution(
        ledger=ledger,
        kin_id=kin_id,
        run_id=run_id,
        session_id=session_id,
        generation=generation,
        reasons=reasons,
    )
    supervisor = _supervisor(
        root_pid,
        role,
        root_starttime_ticks,
        root_pid_namespace_inode,
    )
    if reasons:
        # Nothing is signalled on a run that cannot be named: a fault injection
        # whose record does not say which run it belongs to proves nothing about
        # that run, and the point of this helper is that it fails closed.
        return _refusal(
            case=case,
            attribution=attribution,
            target=None,
            reasons=reasons,
            supervisor=supervisor,
            attempted=attempted,
            recorded=monotonic_ns(),
        )

    root_identity = read_identity(procfs, root_pid)
    if root_identity is None:
        return _refusal(
            case=case,
            attribution=attribution,
            target=None,
            reasons=["ROOT_NOT_FOUND"],
            supervisor=supervisor,
            attempted=attempted,
            recorded=monotonic_ns(),
        )
    if (
        root_identity.starttime_ticks != root_starttime_ticks
        or root_identity.pid_namespace_inode != root_pid_namespace_inode
    ):
        return _refusal(
            case=case,
            attribution=attribution,
            target=None,
            reasons=["ROOT_IDENTITY_MISMATCH"],
            supervisor=supervisor,
            attempted=attempted,
            recorded=monotonic_ns(),
        )

    try:
        candidates = list(find_candidates(procfs, root_pid, role))
    except _WalkTooLarge:
        return _refusal(
            case=case,
            attribution=attribution,
            target=None,
            reasons=["DESCENDANT_WALK_TOO_LARGE"],
            supervisor=supervisor,
            attempted=attempted,
            recorded=monotonic_ns(),
        )
    if len(candidates) != 1:
        reason = (
            f"NO_CANDIDATE_FOR_ROLE:{role}"
            if not candidates
            else "MULTIPLE_CANDIDATES:" + ",".join(str(found) for found in candidates)
        )
        return _refusal(
            case=case,
            attribution=attribution,
            target=None,
            reasons=[reason],
            supervisor=supervisor,
            attempted=attempted,
            recorded=monotonic_ns(),
        )

    pid = candidates[0]
    identity = read_identity(procfs, pid)
    if identity is None:
        return _refusal(
            case=case,
            attribution=attribution,
            target=None,
            reasons=["TARGET_IDENTITY_UNREADABLE"],
            supervisor=supervisor,
            attempted=attempted,
            recorded=monotonic_ns(),
        )
    if not identity_matches_role(identity, role):
        return _refusal(
            case=case,
            attribution=attribution,
            target=None,
            reasons=[f"TARGET_NO_LONGER_MATCHES_ROLE:{role}"],
            supervisor=supervisor,
            attempted=attempted,
            recorded=monotonic_ns(),
        )
    target = {
        "role": role,
        "pid": identity.pid,
        "starttime_ticks": identity.starttime_ticks,
        "state": identity.state,
        "comm": identity.comm,
        "pid_namespace_inode": identity.pid_namespace_inode,
        "exe_path": identity.exe_path,
        "cmdline": list(identity.cmdline),
        "identity_digest": identity.digest(),
        "parent": _parent_of(procfs, identity),
    }

    # Re-read before signalling. A pid is a number the kernel reissues, and the
    # gap between the look and the signal is long enough for the process to have
    # died and its pid to have been handed to somebody else — where a signal
    # aimed at the intended target would land on an unrelated process.
    if not same_process_identity(root_identity, read_identity(procfs, root_pid)):
        return _refusal(
            case=case,
            attribution=attribution,
            target=target,
            reasons=["ROOT_IDENTITY_CHANGED_BEFORE_SIGNAL"],
            supervisor=supervisor,
            attempted=attempted,
            recorded=monotonic_ns(),
        )
    if not same_process_identity(identity, read_identity(procfs, pid)):
        return _refusal(
            case=case,
            attribution=attribution,
            target=target,
            reasons=["TARGET_IDENTITY_CHANGED_BEFORE_SIGNAL"],
            supervisor=supervisor,
            attempted=attempted,
            recorded=monotonic_ns(),
        )

    error = kill(pid)
    signalled_at = monotonic_ns()
    if error is not None:
        return _document(
            case=case,
            attribution=attribution,
            target=target,
            signal_section={
                "name": SIGKILL,
                "number": SIGKILL_NUMBER,
                "result": FAILED,
                "error": error,
            },
            outcome=NOT_INJECTED,
            reasons=[f"SIGNAL_FAILED:{error}"],
            strength=NO_CONFIRMATION,
            confirmation=None,
            attempted=attempted,
            confirmed=None,
            supervisor=supervisor,
            recorded=signalled_at,
        )

    confirmation_section, confirmed = _confirm(
        procfs=procfs,
        pid=pid,
        starttime_ticks=identity.starttime_ticks,
        sleep=sleep,
        rounds=rounds,
        interval=interval,
        monotonic_ns=monotonic_ns,
    )
    signal_section = {
        "name": SIGKILL,
        "number": SIGKILL_NUMBER,
        "result": DELIVERED,
        "error": None,
    }
    if confirmation_section is None:
        return _document(
            case=case,
            attribution=attribution,
            target=target,
            signal_section=signal_section,
            outcome=NOT_INJECTED,
            reasons=["TARGET_DISAPPEARANCE_UNCONFIRMED"],
            strength=NO_CONFIRMATION,
            confirmation=None,
            attempted=attempted,
            confirmed=None,
            supervisor=supervisor,
            recorded=monotonic_ns(),
        )
    return _document(
        case=case,
        attribution=attribution,
        target=target,
        signal_section=signal_section,
        outcome=INJECTED,
        reasons=[],
        strength=IDENTITY_DISAPPEARED,
        confirmation=confirmation_section,
        attempted=attempted,
        confirmed=confirmed,
        supervisor=supervisor,
        recorded=monotonic_ns(),
    )


def _confirm(
    *,
    procfs: Procfs,
    pid: int,
    starttime_ticks: int,
    sleep: Callable[[float], None],
    rounds: int,
    interval: float,
    monotonic_ns: Callable[[], int],
) -> tuple[Mapping[str, object] | None, int | None]:
    """Watch for the recorded identity to leave `/proc`, and count the looks.

    The count — not the elapsed time — is what bounds this and what the record
    carries. `PROC_PID_REUSED` is a confirmation rather than a failure: the pid
    came back with a different start time, which means the process that had the
    old one is gone. That is the whole reason the start time is recorded.
    """

    for look in range(1, rounds + 1):
        found = observe(procfs, pid, starttime_ticks)
        if found in (_ALIVE, _UNREADABLE):
            sleep(interval)
            continue
        return (
            {
                "method": found,
                "observations": look,
                "pid_reused": found == PROC_PID_REUSED,
                "wait_status_available": False,
            },
            monotonic_ns(),
        )
    return None, None


def annotate(
    document: Mapping[str, object], *, exit_status: int, supervisor_pid: int | None = None
) -> dict[str, object]:
    """Add the supervisor's exit status, once the runner has waited for it.

    The helper cannot reap the supervisor — it is nobody's parent here — so the
    status is only knowable to the process that started it. This refuses to
    write a status against a record that named a different supervisor, because
    the number is only meaningful next to the process it came from.
    """

    violations = fault_injection.validate(document)
    if violations:
        raise FaultInjectionError("INVALID: " + ", ".join(violations))
    supervisor = dict(cast(Mapping[str, object], document["supervisor"]))
    if supervisor_pid is not None and supervisor["pid"] != supervisor_pid:
        raise FaultInjectionError(
            f"SUPERVISOR_MISMATCH: the record names {supervisor['pid']}, not {supervisor_pid}"
        )
    supervisor["exit_status"] = exit_status
    supervisor["observed"] = True
    annotated = dict(document)
    annotated["supervisor"] = supervisor
    violations = fault_injection.validate(annotated)
    if violations:
        raise FaultInjectionError("INVALID: " + ", ".join(violations))
    return annotated


def _signal_error(error: OSError) -> str:
    name = errno.errorcode.get(error.errno or 0, "EUNKNOWN")
    return str(name)


def real_kill(pid: int) -> str | None:
    """SIGKILL, reporting the kernel's refusal rather than raising it."""

    try:
        os.kill(pid, SIGKILL_NUMBER)
    except OSError as error:
        return _signal_error(error)
    return None


def _inject_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root-pid", type=int, required=True)
    parser.add_argument("--root-starttime-ticks", type=int, required=True)
    parser.add_argument("--root-pid-namespace-inode", required=True)
    parser.add_argument("--role", choices=[RUNTIME_CONTROLLER, SERVER_JVM], required=True)
    parser.add_argument("--case", default="", help="the reviewed case, or empty for none")
    parser.add_argument("--case-file", type=Path, default=None)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--kin-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--record", type=Path, required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Kill one process belonging to this run, with the proof sealed beside it."
    )
    modes = parser.add_subparsers(dest="mode", required=True)
    _inject_arguments(modes.add_parser("inject", help="find the target, kill it, record it"))
    annotate_parser = modes.add_parser("annotate", help="record the supervisor's exit status")
    annotate_parser.add_argument("--record", type=Path, required=True)
    annotate_parser.add_argument("--supervisor-pid", type=int, default=None)
    annotate_parser.add_argument("--supervisor-exit-status", type=int, required=True)
    args = parser.parse_args(argv)

    try:
        if args.mode == "annotate":
            record = fault_injection.read_record(args.record)
            annotated = annotate(
                record.document,
                exit_status=args.supervisor_exit_status,
                supervisor_pid=args.supervisor_pid,
            )
            fault_injection.write_record(args.record, annotated)
            print(
                json.dumps(
                    {
                        "status": "annotated",
                        "record": str(args.record),
                        "outcome": annotated["outcome"],
                    },
                    sort_keys=True,
                )
            )
            return 0

        if args.record.exists():
            print(
                json.dumps(
                    {
                        "status": "refused",
                        "message": (
                            f"{args.record} already holds a record; two injections are one too many"
                        ),
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        document = inject(
            root_pid=args.root_pid,
            root_starttime_ticks=args.root_starttime_ticks,
            root_pid_namespace_inode=args.root_pid_namespace_inode,
            role=args.role,
            case_id=args.case,
            case_file=args.case_file,
            ledger=args.ledger,
            kin_id=args.kin_id,
            run_id=args.run_id,
            session_id=args.session_id,
            generation=args.generation,
            procfs=RealProcfs(),
            kill=real_kill,
            monotonic_ns=time.monotonic_ns,
            sleep=time.sleep,
        )
        fault_injection.write_record(args.record, document)
    except FaultInjectionError as error:
        print(
            json.dumps({"status": "refused", "message": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        return 2

    print(
        json.dumps(
            {
                "status": "recorded",
                "record": str(args.record),
                "outcome": document["outcome"],
                "reasons": document["reasons"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
