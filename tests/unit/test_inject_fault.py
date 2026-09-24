"""The fault helper: who it kills, what it proves, and what it refuses to do.

The helper is the only thing in this repository that signals another process, so
every test here is about a refusal as much as about a kill: a target it cannot
name uniquely is not signalled, a target whose identity moved between the look
and the signal is not signalled, and a target that is still there afterwards is
not reported as killed.

`/proc` is injected rather than read, because the real one is not available on
every host this suite runs on and a test that needed it would be a test of the
host. The stat lines are the shape Linux actually writes, including a `comm`
with spaces and parentheses in it — the field the naive parse gets wrong.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from minekin_core.adapters.evidence.promotion import load_case_manifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "core-060.json"

CASE_ID = "CORE-060"
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
KIN_ID = "kin-01"
SESSION_ID = "f030bbeadf464c188c2921ede35e4c9f"
GENERATION = 1
ROOT_PID = 4200
CLI_PID = 4242
JVM_PID = 4300
CLIENT_PID = 4320


def load(name: str) -> ModuleType:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module(f"tools.{name}")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


HELPER = load("inject_fault")
RECORD = load("fault_injection")


def stat_line(pid: int, comm: str, ppid: int, starttime: int, state: str = "S") -> str:
    """A `/proc/<pid>/stat` line with the fields the helper reads, in place.

    Fields 1..4 then 5..21 as filler then the start time at 22 — which is where
    the kernel puts it, and the reason the parse has to start from the end of
    `comm` rather than from the beginning of the line.
    """

    return " ".join([str(pid), f"({comm})", state, str(ppid), *(["0"] * 17), str(starttime)])


class FakeProcfs:
    """A `/proc` the tests can hold still and then change underneath a read.

    `hook` is called before every read, so a test can make a process disappear or
    have its identity change between two reads — which is the only way to write
    the TOCTOU and confirmation cases deterministically.
    """

    def __init__(self, processes: Mapping[int, Mapping[str, object]]) -> None:
        self.processes: dict[int, dict[str, object]] = {
            pid: dict(entry) for pid, entry in processes.items()
        }
        self.hook: Callable[[int, str], None] | None = None

    def _before(self, pid: int, name: str) -> None:
        if self.hook is not None:
            self.hook(pid, name)

    def children(self, pid: int) -> tuple[int, ...]:
        self._before(pid, "children")
        entry = self.processes.get(pid)
        if entry is None:
            return ()
        return tuple(cast(list[int], entry.get("children", [])))

    def read_bytes(self, pid: int, name: str) -> bytes | None:
        self._before(pid, name)
        entry = self.processes.get(pid)
        if entry is None:
            return None
        if name == "stat":
            return str(entry["stat"]).encode()
        if name == "cmdline":
            argv = cast(list[str], entry.get("cmdline", []))
            return b"\0".join(item.encode() for item in argv) + (b"\0" if argv else b"")
        if name == "environ":
            # The real file has no entry for a process nobody gave an environment,
            # and an empty one for a process that has one but nothing in it; the
            # difference is not worth modelling here.
            items = cast(list[str], entry.get("environ", []))
            return b"\0".join(item.encode() for item in items) + (b"\0" if items else b"")
        return None

    def read_link(self, pid: int, name: str) -> str | None:
        self._before(pid, name)
        entry = self.processes.get(pid)
        if entry is None:
            return None
        if name == "exe":
            value = entry.get("exe")
            return None if value is None else str(value)
        if name == "ns/pid":
            value = entry.get("ns")
            return None if value is None else str(value)
        return None


def build_procs() -> dict[int, dict[str, object]]:
    """An `xvfb-run` subtree with the CLI in it, and a `run_controlled_server` one.

    The shapes are the ones the harness really produces, and the order matters:
    the wrapper's first child is the X server, not the runtime. That is what made
    `pgrep -P <wrapper> | head -1` wrong — it names the first child, and the
    runtime is not it.
    """

    procs: dict[int, dict[str, object]] = {
        ROOT_PID: {
            "stat": stat_line(ROOT_PID, "xvfb-run", 1, 5551000),
            "cmdline": [
                "/usr/bin/xvfb-run",
                "-a",
                "python",
                "-m",
                "minekin_core",
                "session",
                "start",
            ],
            "exe": "/usr/bin/dash",
            "ns": "pid:[4026531836]",
            "children": [ROOT_PID + 1, CLI_PID],
            "starttime": 5551000,
        },
        ROOT_PID + 1: {
            "stat": stat_line(ROOT_PID + 1, "Xvfb", ROOT_PID, 5551100),
            "cmdline": ["Xvfb", ":99", "-screen", "0", "1280x720x24"],
            "exe": "/usr/bin/Xvfb",
            "ns": "pid:[4026531836]",
            "children": [],
            "starttime": 5551100,
        },
        CLI_PID: {
            "stat": stat_line(CLI_PID, "python3", ROOT_PID, 5551212),
            "cmdline": ["python", "-m", "minekin_core", "session", "start", "--profile", "p.json"],
            "exe": "/opt/minekin/bin/python3.12",
            "ns": "pid:[4026531836]",
            "children": [],
            "starttime": 5551212,
        },
    }
    return procs


def server_procs() -> dict[int, dict[str, object]]:
    """The controlled-server tool with its one JVM under it."""

    return {
        ROOT_PID: {
            "stat": stat_line(ROOT_PID, "python3", 1, 5552000),
            "cmdline": ["python", "/src/tools/run_controlled_server.py", "--directory", "/data/x"],
            "exe": "/opt/minekin/bin/python3.12",
            "ns": "pid:[4026531836]",
            "children": [JVM_PID],
            "starttime": 5552000,
        },
        JVM_PID: {
            "stat": stat_line(JVM_PID, "java", ROOT_PID, 5552100),
            "cmdline": ["java", "-Xmx2G", "-jar", "/server/server.jar", "nogui"],
            "exe": "/opt/java/bin/java",
            "ns": "pid:[4026531836]",
            "children": [],
            "starttime": 5552100,
        },
    }


def session_procs() -> dict[int, dict[str, object]]:
    """One managed session: the wrapper, the runtime under it, and the client.

    The client is a child of the runtime, which is how the real launch works —
    the CLI builds the plan and spawns the JVM itself — so both roles are found
    under the same root. That is the shape that makes the two predicates matter:
    a role that matched "a Java process under the session wrapper" would find the
    client when asked for the server, and vice versa.
    """

    procs = build_procs()
    procs[CLIENT_PID] = {
        "stat": stat_line(CLIENT_PID, "java", CLI_PID, 5551300),
        "cmdline": [
            "/opt/java/bin/java",
            "-Djava.library.path=/data/session/natives",
            "-cp",
            "/data/artifact-store/blobs/sha1/aa/a.jar:/data/bundle/x.jar",
            "net.fabricmc.loader.impl.launch.knot.KnotClient",
            "--username",
            "Kin",
            "--gameDir",
            "/data/session/game",
        ],
        "exe": "/opt/java/bin/java",
        "ns": "pid:[4026531836]",
        "children": [],
        "starttime": 5551300,
    }
    cast(list[int], procs[CLI_PID]["children"]).append(CLIENT_PID)
    return procs


def ledger_for(tmp_path: Path, kin: str = KIN_ID) -> Path:
    directory = tmp_path / kin
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "kin.sqlite3"
    path.write_bytes(b"")
    return path


def _never_kill(pid: int) -> str | None:
    """A signal that is never sent, for a test that only reads the selection."""

    return None


def _never_sleep(seconds: float) -> None:
    """A wait that does not wait: the confirmation loop is bounded by looks."""


class Clock:
    """A monotonic clock that only moves when something asks it for the time."""

    def __init__(self) -> None:
        self.value = 1_700_000_000_000

    def __call__(self) -> int:
        self.value += 7
        return self.value


def inject(
    procfs: FakeProcfs,
    tmp_path: Path,
    *,
    role: str = "runtime_controller",
    root_pid: int = ROOT_PID,
    ledger: Path | None = None,
    case_file: Path | None = CASE,
    case_id: str = CASE_ID,
    kin_id: str = KIN_ID,
    kill: Callable[[int], str | None] | None = None,
    sleep: Callable[[float], None] | None = None,
    rounds: int = 8,
) -> dict[str, object]:
    return cast(
        dict[str, object],
        HELPER.inject(
            root_pid=root_pid,
            root_starttime_ticks=5552000 if role == "server_jvm" else 5551000,
            root_pid_namespace_inode="pid:[4026531836]",
            role=role,
            case_id=case_id,
            case_file=case_file,
            ledger=ledger if ledger is not None else ledger_for(tmp_path),
            kin_id=kin_id,
            run_id=RUN_ID,
            session_id=SESSION_ID,
            generation=GENERATION,
            procfs=procfs,
            kill=kill if kill is not None else _never_kill,
            monotonic_ns=Clock(),
            sleep=sleep if sleep is not None else _never_sleep,
            rounds=rounds,
        ),
    )


def outcome(document: Mapping[str, object]) -> str:
    return str(document["outcome"])


def reasons(document: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(cast(list[str], document["reasons"]))


def target_of(document: Mapping[str, object]) -> Mapping[str, object]:
    value = document["target"]
    assert isinstance(value, Mapping)
    return cast(Mapping[str, object], value)


def test_a_stat_line_with_parens_in_comm_is_parsed_from_the_end() -> None:
    """`comm` is user-controlled and may hold spaces and parentheses."""

    parsed = HELPER.parse_stat(stat_line(4242, "my (weird) proc", 4200, 99, state="R"))

    assert parsed.comm == "my (weird) proc"
    assert parsed.parent_pid == 4200
    assert parsed.starttime_ticks == 99
    assert parsed.state == "R"


def test_a_cmdline_is_the_arguments_the_kernel_kept() -> None:
    assert HELPER.parse_cmdline(b"python\0-m\0minekin_core\0session\0start\0") == (
        "python",
        "-m",
        "minekin_core",
        "session",
        "start",
    )
    assert HELPER.parse_cmdline(b"") == ()


def test_the_runtime_is_found_under_the_wrapper_rather_than_assumed_a_child() -> None:
    """The CLI is a grandchild: `xvfb-run` is between the harness and the runtime."""

    found = HELPER.find_candidates(FakeProcfs(build_procs()), ROOT_PID, "runtime_controller")

    assert found == (CLI_PID,)


def test_runtime_matching_requires_the_exact_module_command() -> None:
    """Words scattered through another command line are not a runtime."""

    procs = build_procs()
    cast(list[str], procs[CLI_PID]["cmdline"])[:] = [
        "python",
        "-m",
        "minekin_core",
        "evidence",
        "verify",
        "session",
        "start",
    ]

    assert HELPER.find_candidates(FakeProcfs(procs), ROOT_PID, "runtime_controller") == ()


def test_the_server_is_the_jvm_under_the_tool_rather_than_the_tool() -> None:
    found = HELPER.find_candidates(FakeProcfs(server_procs()), ROOT_PID, "server_jvm")

    assert found == (JVM_PID,)


@pytest.mark.parametrize(
    "argv",
    [
        ["javac", "-jar", "/server/server.jar"],
        ["java", "-jar", "/tmp/unrelated.jar"],
        ["java", "com.example.Unrelated"],
    ],
)
def test_an_unrelated_java_family_process_is_not_the_server(argv: list[str]) -> None:
    procs = server_procs()
    procs[JVM_PID]["cmdline"] = argv
    procs[JVM_PID]["exe"] = f"/opt/java/bin/{argv[0]}"

    assert HELPER.find_candidates(FakeProcfs(procs), ROOT_PID, "server_jvm") == ()


def test_the_client_is_the_jvm_the_runtime_started() -> None:
    found = HELPER.find_candidates(FakeProcfs(session_procs()), ROOT_PID, "client_jvm")

    assert found == (CLIENT_PID,)


def test_one_session_subtree_yields_each_role_exactly_once() -> None:
    """Both roles live under the same wrapper, so the predicates have to be exact.

    A role described as "the Java process under the session" would answer the
    wrong question here: the client is a JVM and so is the runtime's own Python
    process is not — but the server predicate would match nothing while a loose
    client predicate would also match the server, and either way the helper would
    be reporting a kill of whichever one it happened to name.
    """

    procs = FakeProcfs(session_procs())

    assert HELPER.find_candidates(procs, ROOT_PID, "runtime_controller") == (CLI_PID,)
    assert HELPER.find_candidates(procs, ROOT_PID, "client_jvm") == (CLIENT_PID,)


def test_the_server_jvm_is_not_the_client() -> None:
    """The dedicated server is a JVM too; the main class is what tells them apart."""

    procs = server_procs()

    assert HELPER.find_candidates(FakeProcfs(procs), ROOT_PID, "client_jvm") == ()


@pytest.mark.parametrize(
    "argv",
    [
        # The dedicated server: a JVM, launched from a jar, not a client.
        ["java", "-Xmx2G", "-jar", "/server/server.jar", "nogui"],
        # A JVM running something else entirely.
        ["java", "com.example.Unrelated"],
        # The client's main class as part of another argument is not the client.
        ["java", "-Dminekin.main=net.fabricmc.loader.impl.launch.knot.KnotClient", "-jar", "x.jar"],
        # The right name in the right place, but not a JVM at all.
        ["python", "net.fabricmc.loader.impl.launch.knot.KnotClient"],
    ],
)
def test_an_unrelated_process_is_not_the_client(argv: list[str]) -> None:
    procs = session_procs()
    procs[CLIENT_PID]["cmdline"] = argv
    procs[CLIENT_PID]["exe"] = f"/opt/bin/{Path(argv[0]).name}"

    assert HELPER.find_candidates(FakeProcfs(procs), ROOT_PID, "client_jvm") == ()


def test_the_client_kill_is_recorded_as_its_own_role_and_supervisor(tmp_path: Path) -> None:
    """The record names the client as the target, not the runtime it runs under."""

    procfs = FakeProcfs(session_procs())
    signalled: list[int] = []

    def kill(pid: int) -> str | None:
        signalled.append(pid)
        del procfs.processes[pid]
        return None

    document = inject(procfs, tmp_path, role="client_jvm", kill=kill)

    assert signalled == [CLIENT_PID]
    assert outcome(document) == "INJECTED"
    assert target_of(document)["role"] == "client_jvm"
    assert target_of(document)["comm"] == "java"
    supervisor = cast(Mapping[str, object], document["supervisor"])
    assert supervisor["role"] == "client_jvm_root"
    # The runtime is untouched: it is the process that has to notice.
    assert CLI_PID in procfs.processes
    assert RECORD.validate(document) == ()


def test_two_runtimes_are_ambiguous_rather_than_the_first_one() -> None:
    procs = build_procs()
    second = CLI_PID + 10
    procs[second] = {
        "stat": stat_line(second, "python3", ROOT_PID, 5551300),
        "cmdline": ["python", "-m", "minekin_core", "session", "start"],
        "exe": "/opt/minekin/bin/python3.12",
        "ns": "pid:[4026531836]",
        "children": [],
        "starttime": 5551300,
    }
    cast(list[int], procs[ROOT_PID]["children"]).append(second)

    found = HELPER.find_candidates(FakeProcfs(procs), ROOT_PID, "runtime_controller")

    assert len(found) == 2


def test_an_unknown_root_is_refused_before_anything_is_looked_for(tmp_path: Path) -> None:
    document = inject(FakeProcfs(build_procs()), tmp_path, root_pid=999999)

    assert outcome(document) == "AMBIGUOUS"
    assert "ROOT_NOT_FOUND" in reasons(document)
    assert document["signal"] is None
    assert RECORD.validate(document) == ()


def test_a_reused_root_pid_is_refused_before_its_subtree_is_walked(tmp_path: Path) -> None:
    procs = build_procs()
    procs[ROOT_PID]["stat"] = stat_line(ROOT_PID, "unrelated", 1, 9999999)
    signalled: list[int] = []

    document = inject(FakeProcfs(procs), tmp_path, kill=lambda pid: signalled.append(pid) and None)

    assert signalled == []
    assert outcome(document) == "AMBIGUOUS"
    assert reasons(document) == ("ROOT_IDENTITY_MISMATCH",)


def test_a_kill_that_lands_records_the_identity_that_went_away(tmp_path: Path) -> None:
    procfs = FakeProcfs(build_procs())
    signalled: list[int] = []

    def kill(pid: int) -> str | None:
        signalled.append(pid)
        del procfs.processes[pid]
        return None

    document = inject(procfs, tmp_path, kill=kill)

    assert signalled == [CLI_PID]
    assert outcome(document) == "INJECTED"
    assert reasons(document) == ()
    assert document["confirmation_strength"] == "IDENTITY_DISAPPEARED"
    confirmation = cast(Mapping[str, object], document["confirmation"])
    assert confirmation["method"] == "PROC_ENTRY_ABSENT"
    assert confirmation["wait_status_available"] is False
    assert confirmation["pid_reused"] is False
    signal = cast(Mapping[str, object], document["signal"])
    assert signal["name"] == "SIGKILL"
    assert signal["number"] == 9
    assert signal["result"] == "DELIVERED"
    assert target_of(document)["pid"] == CLI_PID
    assert target_of(document)["starttime_ticks"] == 5551212
    assert target_of(document)["role"] == "runtime_controller"
    assert RECORD.validate(document) == ()


def test_the_record_names_the_run_it_is_about(tmp_path: Path) -> None:
    procfs = FakeProcfs(build_procs())

    document = inject(procfs, tmp_path, kill=lambda pid: (procfs.processes.pop(pid, None), None)[1])

    assert document["attribution"] == {
        "kin_id": KIN_ID,
        "run_id": RUN_ID,
        "session_id": SESSION_ID,
        "generation": GENERATION,
    }
    case = cast(Mapping[str, object], document["case"])
    assert case["case_id"] == CASE_ID
    assert len(str(case["case_version"])) == 64


def test_the_supervisor_is_named_and_its_exit_status_is_not_invented(tmp_path: Path) -> None:
    """The helper is not the supervisor's parent, so it cannot reap it."""

    procfs = FakeProcfs(build_procs())
    document = inject(procfs, tmp_path, kill=lambda pid: (procfs.processes.pop(pid, None), None)[1])

    supervisor = cast(Mapping[str, object], document["supervisor"])
    assert supervisor["pid"] == ROOT_PID
    assert supervisor["role"] == "runtime_controller_root"
    assert supervisor["exit_status"] is None
    assert supervisor["observed"] is False


def test_a_target_that_survives_is_not_reported_as_killed(tmp_path: Path) -> None:
    document = inject(FakeProcfs(build_procs()), tmp_path, kill=lambda pid: None)

    assert outcome(document) == "NOT_INJECTED"
    assert "TARGET_DISAPPEARANCE_UNCONFIRMED" in reasons(document)
    assert document["confirmation_strength"] == "NONE"
    assert document["confirmed_at_monotonic_ns"] is None
    assert RECORD.validate(document) == ()


def test_an_unparseable_present_proc_entry_is_not_proof_of_death(tmp_path: Path) -> None:
    """A failed read is uncertainty, not the same observation as ENOENT."""

    procfs = FakeProcfs(build_procs())

    def kill(pid: int) -> str | None:
        procfs.processes[pid]["stat"] = "present but incomplete"
        return None

    document = inject(procfs, tmp_path, kill=kill, rounds=2)

    assert outcome(document) == "NOT_INJECTED"
    assert reasons(document) == ("TARGET_DISAPPEARANCE_UNCONFIRMED",)
    assert document["confirmation"] is None


def test_a_transient_process_state_change_does_not_change_identity(tmp_path: Path) -> None:
    """R/S transitions between identity reads are normal and must not randomise a run."""

    procfs = FakeProcfs(build_procs())
    reads = {"count": 0}

    def hook(pid: int, name: str) -> None:
        if pid == CLI_PID and name == "stat":
            reads["count"] += 1
            if reads["count"] == 2:
                procfs.processes[pid]["stat"] = stat_line(pid, "python3", ROOT_PID, 5551212, "R")

    procfs.hook = hook

    def kill(pid: int) -> str | None:
        del procfs.processes[pid]
        return None

    document = inject(procfs, tmp_path, kill=kill)

    assert outcome(document) == "INJECTED"


def test_a_zombie_has_terminated_even_though_its_proc_entry_is_still_there(
    tmp_path: Path,
) -> None:
    """SIGKILL cannot be handled, so a zombie is a killed process awaiting a reap."""

    procfs = FakeProcfs(build_procs())

    def kill(pid: int) -> str | None:
        procfs.processes[pid]["stat"] = stat_line(pid, "python3", 4200, 5551212, state="Z")
        return None

    document = inject(procfs, tmp_path, kill=kill)

    confirmation = cast(Mapping[str, object], document["confirmation"])
    assert outcome(document) == "INJECTED"
    assert confirmation["method"] == "PROC_STATE_ZOMBIE"


def test_a_reused_pid_is_told_apart_from_the_process_that_was_killed(tmp_path: Path) -> None:
    """The same pid with a different start time is a different process."""

    procfs = FakeProcfs(build_procs())

    def kill(pid: int) -> str | None:
        procfs.processes[pid]["stat"] = stat_line(pid, "unrelated", 1, 5559999)
        return None

    document = inject(procfs, tmp_path, kill=kill)

    confirmation = cast(Mapping[str, object], document["confirmation"])
    assert outcome(document) == "INJECTED"
    assert confirmation["method"] == "PROC_PID_REUSED"
    assert confirmation["pid_reused"] is True


def test_an_identity_that_moved_between_the_look_and_the_signal_is_not_signalled(
    tmp_path: Path,
) -> None:
    """TOCTOU: a pid is a reusable number, so the identity is re-read first."""

    procfs = FakeProcfs(build_procs())
    reads = {"count": 0}
    signalled: list[int] = []

    def hook(pid: int, name: str) -> None:
        if pid != CLI_PID or name != "stat":
            return
        reads["count"] += 1
        if reads["count"] == 2:
            procfs.processes[CLI_PID]["stat"] = stat_line(CLI_PID, "python3", 4200, 5557777)

    procfs.hook = hook

    document = inject(procfs, tmp_path, kill=lambda pid: signalled.append(pid) and None)

    assert signalled == []
    assert outcome(document) == "AMBIGUOUS"
    assert "TARGET_IDENTITY_CHANGED_BEFORE_SIGNAL" in reasons(document)
    assert document["signal"] is None
    assert RECORD.validate(document) == ()


def test_a_root_that_moved_before_the_signal_refuses_the_kill(tmp_path: Path) -> None:
    procfs = FakeProcfs(build_procs())
    root_reads = {"count": 0}
    signalled: list[int] = []

    def hook(pid: int, name: str) -> None:
        if pid == ROOT_PID and name == "stat":
            root_reads["count"] += 1
            if root_reads["count"] == 2:
                procfs.processes[ROOT_PID]["stat"] = stat_line(ROOT_PID, "unrelated", 1, 9999999)

    procfs.hook = hook
    document = inject(procfs, tmp_path, kill=lambda pid: signalled.append(pid) and None)

    assert signalled == []
    assert outcome(document) == "AMBIGUOUS"
    assert reasons(document) == ("ROOT_IDENTITY_CHANGED_BEFORE_SIGNAL",)


def test_a_candidate_that_execs_out_of_the_role_is_not_signalled(tmp_path: Path) -> None:
    procfs = FakeProcfs(build_procs())
    candidate_reads = {"count": 0}
    signalled: list[int] = []

    def hook(pid: int, name: str) -> None:
        if pid == CLI_PID and name == "stat":
            candidate_reads["count"] += 1
            if candidate_reads["count"] == 1:
                procfs.processes[CLI_PID]["cmdline"] = [
                    "python",
                    "-m",
                    "minekin_core",
                    "evidence",
                    "verify",
                ]

    procfs.hook = hook
    document = inject(procfs, tmp_path, kill=lambda pid: signalled.append(pid) and None)

    assert signalled == []
    assert outcome(document) == "AMBIGUOUS"
    assert reasons(document) == ("TARGET_NO_LONGER_MATCHES_ROLE:runtime_controller",)


def test_two_candidates_are_not_signalled_at_all(tmp_path: Path) -> None:
    procs = build_procs()
    procs[CLI_PID + 10] = {
        "stat": stat_line(CLI_PID + 10, "python3", ROOT_PID, 5551300),
        "cmdline": ["python", "-m", "minekin_core", "session", "start"],
        "exe": "/opt/minekin/bin/python3.12",
        "ns": "pid:[4026531836]",
        "children": [],
        "starttime": 5551300,
    }
    cast(list[int], procs[ROOT_PID]["children"]).append(CLI_PID + 10)
    signalled: list[int] = []

    document = inject(FakeProcfs(procs), tmp_path, kill=lambda pid: signalled.append(pid) and None)

    assert signalled == []
    assert outcome(document) == "AMBIGUOUS"
    assert any(reason.startswith("MULTIPLE_CANDIDATES") for reason in reasons(document))


def test_no_candidate_is_not_a_kill(tmp_path: Path) -> None:
    document = inject(FakeProcfs({ROOT_PID: build_procs()[ROOT_PID]}), tmp_path)

    assert outcome(document) == "AMBIGUOUS"
    assert reasons(document) == ("NO_CANDIDATE_FOR_ROLE:runtime_controller",)


def test_a_signal_the_kernel_refused_is_not_a_kill(tmp_path: Path) -> None:
    document = inject(FakeProcfs(build_procs()), tmp_path, kill=lambda pid: "EPERM")

    assert outcome(document) == "NOT_INJECTED"
    assert reasons(document) == ("SIGNAL_FAILED:EPERM",)
    signal = cast(Mapping[str, object], document["signal"])
    assert signal["result"] == "FAILED"
    assert signal["error"] == "EPERM"


def test_a_ledger_that_belongs_to_another_kin_is_refused(tmp_path: Path) -> None:
    """The path and the recorded kin have to be the same kin."""

    document = inject(FakeProcfs(build_procs()), tmp_path, ledger=ledger_for(tmp_path, "kin-09"))

    assert outcome(document) == "AMBIGUOUS"
    assert any(reason.startswith("LEDGER_NOT_THE_KIN") for reason in reasons(document))


def test_a_refusal_is_always_a_record_the_reader_accepts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The helper may not build a record its own reader would then refuse.

    Measured on the command line before this was checked here: a ledger path with
    no directory component produced the reason `LEDGER_NOT_THE_KIN:`, whose empty
    detail does not match the record's own reason pattern — so the helper wrote
    nothing at all and the run had no record to be judged on.
    """

    monkeypatch.chdir(tmp_path)
    (tmp_path / "kin.sqlite3").write_bytes(b"")

    document = inject(FakeProcfs(build_procs()), tmp_path, ledger=Path("kin.sqlite3"))

    assert outcome(document) == "AMBIGUOUS"
    assert reasons(document) == ("LEDGER_NOT_THE_KIN:NO_DIRECTORY",)
    assert RECORD.validate(document) == ()


def test_a_case_file_that_is_not_the_named_case_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "core-999.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "CORE-999",
                "work_package": "W70",
                "mandatory": False,
                "inputs": [],
                "assertions": ["move_input_was_leased"],
            }
        ),
        encoding="utf-8",
    )

    document = inject(FakeProcfs(build_procs()), tmp_path, case_file=path, case_id=CASE_ID)

    assert outcome(document) == "AMBIGUOUS"
    assert reasons(document) == ("CASE_FILE_MISMATCH:CORE-999",)


def test_the_case_version_is_the_one_the_case_actually_has(tmp_path: Path) -> None:
    """The record and the bundle must name the same case version, or neither counts."""

    definition = load_case_manifest(CASE)

    procfs = FakeProcfs(build_procs())
    document = inject(procfs, tmp_path, kill=lambda pid: (procfs.processes.pop(pid, None), None)[1])

    case = cast(Mapping[str, object], document["case"])
    assert case["case_version"] == definition.digest


def test_a_run_that_names_no_case_records_no_case(tmp_path: Path) -> None:
    """A kill run nobody attributed to a case borrows nothing to fill the field."""

    procfs = FakeProcfs(build_procs())
    document = inject(
        procfs,
        tmp_path,
        case_file=None,
        case_id="",
        kill=lambda pid: (procfs.processes.pop(pid, None), None)[1],
    )

    assert document["case"] is None
    assert outcome(document) == "INJECTED"
    assert RECORD.validate(document) == ()


def test_the_server_case_is_recorded_the_same_way_though_no_case_claims_it_yet(
    tmp_path: Path,
) -> None:
    """The trace can be produced and validated; this phase claims no case for it."""

    procfs = FakeProcfs(server_procs())
    signalled: list[int] = []

    def kill(pid: int) -> str | None:
        signalled.append(pid)
        del procfs.processes[pid]
        return None

    document = inject(procfs, tmp_path, role="server_jvm", kill=kill)

    assert signalled == [JVM_PID]
    assert outcome(document) == "INJECTED"
    assert target_of(document)["role"] == "server_jvm"
    assert target_of(document)["comm"] == "java"
    supervisor = cast(Mapping[str, object], document["supervisor"])
    assert supervisor["role"] == "server_jvm_root"
    assert RECORD.validate(document) == ()


def test_the_confirmation_is_asked_until_the_identity_is_gone(tmp_path: Path) -> None:
    """The loop is bounded by observations, and the count is recorded."""

    procfs = FakeProcfs(build_procs())
    steps = {"n": 0}

    def kill(pid: int) -> str | None:
        return None

    def sleep(seconds: float) -> None:
        steps["n"] += 1
        if steps["n"] >= 3:
            del procfs.processes[CLI_PID]

    document = inject(procfs, tmp_path, kill=kill, sleep=sleep, rounds=20)

    confirmation = cast(Mapping[str, object], document["confirmation"])
    assert outcome(document) == "INJECTED"
    assert confirmation["observations"] == 4
    assert steps["n"] == 3


def test_the_time_of_the_attempt_comes_before_the_time_of_the_confirmation(
    tmp_path: Path,
) -> None:
    procfs = FakeProcfs(build_procs())
    document = inject(procfs, tmp_path, kill=lambda pid: (procfs.processes.pop(pid, None), None)[1])

    attempted = cast(int, document["attempted_at_monotonic_ns"])
    confirmed = cast(int, document["confirmed_at_monotonic_ns"])
    assert attempted <= confirmed <= cast(int, document["recorded_at_monotonic_ns"])


def test_annotate_records_the_supervisor_s_later_exit_without_touching_the_rest(
    tmp_path: Path,
) -> None:
    procfs = FakeProcfs(build_procs())
    document = inject(procfs, tmp_path, kill=lambda pid: (procfs.processes.pop(pid, None), None)[1])

    annotated = HELPER.annotate(document, exit_status=137, supervisor_pid=ROOT_PID)

    supervisor = cast(Mapping[str, object], annotated["supervisor"])
    assert supervisor["exit_status"] == 137
    assert supervisor["observed"] is True
    assert annotated["outcome"] == "INJECTED"
    assert annotated["reasons"] == []
    assert RECORD.validate(annotated) == ()


def test_annotate_refuses_a_status_for_a_different_supervisor(tmp_path: Path) -> None:
    procfs = FakeProcfs(build_procs())
    document = inject(procfs, tmp_path, kill=lambda pid: (procfs.processes.pop(pid, None), None)[1])

    # The helper's own class, because it imports the record module by name while
    # this file imports it as `tools.fault_injection`: one file, two modules.
    with pytest.raises(HELPER.FaultInjectionError, match="SUPERVISOR_MISMATCH"):
        HELPER.annotate(document, exit_status=0, supervisor_pid=ROOT_PID + 1)


def test_the_helper_never_reaches_for_a_process_outside_the_tree_it_was_given(
    tmp_path: Path,
) -> None:
    """A second session in the same container is not this run's session."""

    procs = build_procs()
    stranger = 7000
    procs[stranger] = {
        "stat": stat_line(stranger, "python3", 1, 5559999),
        "cmdline": ["python", "-m", "minekin_core", "session", "start"],
        "exe": "/opt/minekin/bin/python3.12",
        "ns": "pid:[4026531836]",
        "children": [],
        "starttime": 5559999,
    }

    found = HELPER.find_candidates(FakeProcfs(procs), ROOT_PID, "runtime_controller")

    assert found == (CLI_PID,)
    assert str(stranger) not in found


#: The name the Bridge reads, spelled here rather than inline so that a test that
#: asks whether it arrived is asking about the same string the product declares.
REQUEST_VARIABLE = "MINEKIN_BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT"
SUBJECT = "BRIDGE_FIRST_SNAPSHOT_AUTHORITY"


def client_procs(environ: Mapping[int, list[str]] | None = None) -> dict[int, dict[str, object]]:
    """The session subtree with each process's own environment hung on it."""

    procs = session_procs()
    for pid, items in (environ or {}).items():
        procs[pid]["environ"] = list(items)
    return procs


def request(
    procfs: FakeProcfs,
    tmp_path: Path,
    *,
    value: str = "1",
    subject: str = SUBJECT,
    root_pid: int = ROOT_PID,
    ledger: Path | None = None,
    case_id: str = CASE_ID,
    case_file: Path | None = CASE,
) -> dict[str, object]:
    return cast(
        dict[str, object],
        HELPER.record_request(
            root_pid=root_pid,
            root_starttime_ticks=5551000,
            root_pid_namespace_inode="pid:[4026531836]",
            subject=subject,
            value=value,
            case_id=case_id,
            case_file=case_file,
            ledger=ledger if ledger is not None else ledger_for(tmp_path),
            kin_id=KIN_ID,
            run_id=RUN_ID,
            session_id=SESSION_ID,
            generation=GENERATION,
            procfs=procfs,
            monotonic_ns=Clock(),
        ),
    )


def test_a_request_the_client_carries_is_recorded_as_an_effect(
    tmp_path: Path,
) -> None:
    """The effect is read out of `/proc`, not out of what the client printed."""

    procs = client_procs({CLIENT_PID: ["PATH=/usr/bin", f"{REQUEST_VARIABLE}=1"]})

    document = request(FakeProcfs(procs), tmp_path)

    assert document["category"] == "CLIENT_REPORT_REQUEST"
    assert document["request"] == {
        "subject": SUBJECT,
        "environment_variable": REQUEST_VARIABLE,
        "value": "1",
        "asked": True,
    }
    effect = cast(Mapping[str, object], document["effect"])
    assert effect["observed"] is True
    assert effect["method"] == "PROC_CHILD_ENVIRON"
    assert effect["pid"] == CLIENT_PID
    assert effect["starttime_ticks"] == 5551300
    assert str(REQUEST_VARIABLE) in str(effect["detail"])
    assert document["reasons"] == []
    # A record a reader would refuse is not a record.
    assert RECORD.validate(document) == ()
    # And it is not a kill: the fields that would claim one are absent, not empty.
    assert "target" not in document
    assert "signal" not in document
    assert "outcome" not in document
    assert "confirmation_strength" not in document


def test_a_request_the_client_does_not_carry_says_which_look_failed(
    tmp_path: Path,
) -> None:
    """A request that did not arrive is recordable, and it is not an effect."""

    procs = client_procs({CLIENT_PID: ["PATH=/usr/bin"]})

    document = request(FakeProcfs(procs), tmp_path)

    effect = cast(Mapping[str, object], document["effect"])
    assert effect["observed"] is False
    assert effect["method"] == "NOT_OBSERVED"
    assert effect["pid"] is None
    assert effect["starttime_ticks"] is None
    assert document["reasons"] == ["REQUEST_NOT_IN_CLIENT_ENVIRON"]
    assert RECORD.validate(document) == ()


def test_a_second_client_carrying_the_name_is_too_many_to_attribute(
    tmp_path: Path,
) -> None:
    """The hosting-and-joining shape must not credit one client with the other's name."""

    procs = client_procs({CLIENT_PID: [f"{REQUEST_VARIABLE}=1"]})
    second = CLIENT_PID + 10
    procs[second] = {
        "stat": stat_line(second, "java", CLI_PID, 5551400),
        "cmdline": ["/opt/java/bin/java", "net.fabricmc.loader.impl.launch.knot.KnotClient"],
        "exe": "/opt/java/bin/java",
        "ns": "pid:[4026531836]",
        "children": [],
        "starttime": 5551400,
        "environ": [f"{REQUEST_VARIABLE}=1"],
    }
    cast(list[int], procs[CLI_PID]["children"]).append(second)

    document = request(FakeProcfs(procs), tmp_path)

    assert document["reasons"] == ["CLIENT_JVM_AMBIGUOUS"]
    effect = cast(Mapping[str, object], document["effect"])
    assert effect["observed"] is False
    assert RECORD.validate(document) == ()


def test_a_request_is_not_hunted_for_on_a_run_that_cannot_be_named(
    tmp_path: Path,
) -> None:
    """An observation attributed to no tree is filed under a tree by mistake."""

    procs = client_procs({CLIENT_PID: [f"{REQUEST_VARIABLE}=1"]})

    document = request(FakeProcfs(procs), tmp_path, root_pid=999999)

    assert "ROOT_NOT_FOUND" in cast(list[str], document["reasons"])
    effect = cast(Mapping[str, object], document["effect"])
    assert effect["observed"] is False
    # Said in the record, not only implied by the absence: the environment of a
    # client that exists was never looked inside, and that is not the same story as
    # looking and not finding.
    assert "not looked for" in str(effect["detail"])


def test_a_request_for_a_subject_this_tool_does_not_know_is_refused(
    tmp_path: Path,
) -> None:
    """The subject picks the variable, so an unknown one picks nothing to check.

    The error is named from the helper's own namespace: `inject_fault.py` imports
    `fault_injection` as a sibling module, which is a different module object from
    the `tools.fault_injection` this suite loads, and a test that compared the two
    classes would fail for that reason rather than for a reason worth knowing.
    """

    procs = client_procs({CLIENT_PID: [f"{REQUEST_VARIABLE}=1"]})

    with pytest.raises(HELPER.fault_injection.FaultInjectionError, match="UNKNOWN_SUBJECT"):
        request(FakeProcfs(procs), tmp_path, subject="SOMETHING_ELSE")


def test_a_request_record_round_trips_through_the_channel_that_seals_it(
    tmp_path: Path,
) -> None:
    """The record the helper builds is the record the sealer's reader accepts.

    `read_record` is the exact call `seal_run_evidence.py` makes on the file this
    run writes, including the symlink and swap refusals. Going through it here is
    what lets a request be said in the bundle rather than in the run's console
    output, which is the requirement the frozen criteria put on this scenario.
    """

    procs = client_procs({CLIENT_PID: [f"{REQUEST_VARIABLE}=1"]})
    document = request(FakeProcfs(procs), tmp_path)
    path = tmp_path / "fault-injection.json"

    RECORD.write_record(path, document)
    read = RECORD.read_record(path)

    assert read.document == document
    assert read.raw == RECORD.dump_record(document)
