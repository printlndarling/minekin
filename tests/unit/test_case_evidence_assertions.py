"""Judging a finished run against the case it was run for.

The material here is shaped like the real thing rather than like the parser: the
log line is the one vanilla wrote in the runner (`[19:28:12] [Server
thread/INFO]: Kin joined the game`), the user cache entry is the one vanilla
wrote next to it, and the run document is the one `session start` prints. A test
that invented its own shapes would pass while the asserter read nothing.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest

from minekin_core.domain.offline_identity import offline_player_uuid

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ASSERTER = REPOSITORY_ROOT / "tools" / "assert_case_evidence.py"
REVIEWED_CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "core-020.json"
USERNAME = "Kin"
# The UUID a real run's server recorded for this name, read back from the
# `usercache.json` vanilla wrote next to its log. Asserted below to be what the
# rule derives, so the fixture cannot drift away from vanilla's own algorithm.
RECORDED_UUID = "8f40376b-c23f-3ef1-b553-5564eea75639"

JOINED = f"[19:28:12] [Server thread/INFO]: {USERNAME} joined the game"
LEFT = f"[19:28:40] [Server thread/INFO]: {USERNAME} left the game"


class _Material(Protocol):
    run_document: Mapping[str, object]
    server_log: str
    server_identities: Mapping[str, str]
    username: str


class _Verdict(Protocol):
    expected: tuple[str, ...]
    observed: tuple[str, ...]
    failures: tuple[str, ...]
    unimplemented: tuple[str, ...]
    result: str


class _Asserter(Protocol):
    #: The material record, constructed rather than read.
    RunMaterial: Callable[..., _Material]
    Unreadable: type[Exception]
    ASSERTIONS: Mapping[str, Callable[[_Material], str | None]]
    EXIT_HELD: int
    EXIT_FAILED: int
    EXIT_UNJUDGED: int

    def evaluate(self, case: Mapping[str, object], material: _Material) -> _Verdict: ...


class _Implementation(Protocol):
    target: str


class _Checker(Protocol):
    IMPLEMENTATIONS: Mapping[str, _Implementation]
    RUNTIME_ASSERTER: str


def load(name: str) -> ModuleType:
    """One `tools/` module, by the same route `python tools/x.py` would take."""

    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module(f"tools.{name}")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


ASSERTER_MODULE = cast(_Asserter, load("assert_case_evidence"))
CHECKER = cast(_Checker, load("check_case_assertions"))


def run_document(**run_overrides: object) -> dict[str, object]:
    run: dict[str, object] = {
        "schema_version": 1,
        "status": "ended",
        "outcome": "CLIENT_EXITED",
        "session_state": "STOPPED",
        "connection_state": "PLAYABLE",
        "events_applied": 4,
        "events_ignored": 0,
        "snapshots_admitted": 1,
        "snapshot_rejections": [],
        "entities_admitted": 0,
        "entities_rejected": 0,
        "actions_applied": 0,
        "actions_refused": 0,
        "input_release_failed": False,
        "input_refusal": "",
    }
    run.update(run_overrides)
    return {
        "schema_version": 1,
        "status": "started",
        "kin_id": "kin-01",
        "run_id": "5c1f9a7b2d3e4f6089abcdef01234567",
        "session_id": "session-01",
        "generation": 1,
        "overlay": "/data/kin/kin-01/run/session/session-01/generation-1",
        "pid": 41,
        "started_at": "2026-09-19T19:28:00Z",
        "argv_digest": "e" * 64,
        "recovery": {"invalidated": [], "waiting": [], "status": "reconciled"},
        "run": run,
    }


def material(
    *,
    document: dict[str, object] | None = None,
    log: str = f"{JOINED}\n{LEFT}\n",
    identities: Mapping[str, str] | None = None,
    username: str = USERNAME,
) -> _Material:
    return ASSERTER_MODULE.RunMaterial(
        run_document=run_document() if document is None else document,
        server_log=log,
        server_identities={USERNAME: RECORDED_UUID} if identities is None else identities,
        username=username,
    )


def reviewed_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(REVIEWED_CASE.read_text(encoding="utf-8")))


def test_the_recorded_uuid_is_the_one_vanilla_derives_for_the_name() -> None:
    """If this fails the fixture is stale, not the code: the rule is vanilla's."""

    assert str(offline_player_uuid(USERNAME)) == RECORDED_UUID


def test_a_run_that_did_everything_the_case_asks_for_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(reviewed_case(), material())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()
    assert verdict.unimplemented == ()


def test_the_reviewed_case_names_only_assertions_the_asserter_performs() -> None:
    """A name in a manifest and a name in the registry have to be one name."""

    declared = reviewed_case()["assertions"]
    assert isinstance(declared, list)
    for name in cast(list[object], declared):
        assert str(name) in ASSERTER_MODULE.ASSERTIONS


def test_a_kin_that_never_joined_fails_every_assertion_that_needs_it() -> None:
    log = '[19:28:12] [Server thread/INFO]: Done (0.512s)! For help, type "help"\n'

    verdict = ASSERTER_MODULE.evaluate(reviewed_case(), material(log=log))

    assert verdict.result == "FAIL"
    assert verdict.failures == (
        "server_observed_join_identity:JOIN_NOT_LOGGED",
        "first_snapshot_admitted:JOIN_NOT_LOGGED",
        "leave_after_join_observed:JOIN_NOT_LOGGED",
    )


def test_a_server_that_recorded_a_different_uuid_recorded_a_different_player() -> None:
    other = "00000000-0000-3000-8000-000000000000"

    verdict = ASSERTER_MODULE.evaluate(reviewed_case(), material(identities={USERNAME: other}))

    assert verdict.result == "FAIL"
    assert verdict.failures == (f"server_observed_join_identity:IDENTITY_UUID_MISMATCH:{other}",)


def test_a_join_the_server_logged_but_never_cached_is_not_an_observed_identity() -> None:
    verdict = ASSERTER_MODULE.evaluate(reviewed_case(), material(identities={}))

    assert verdict.result == "FAIL"
    assert "server_observed_join_identity:IDENTITY_NOT_RECORDED" in verdict.failures


def test_a_run_document_without_its_run_section_cannot_be_judged() -> None:
    document = run_document()
    document.pop("run")

    with pytest.raises(ASSERTER_MODULE.Unreadable):
        ASSERTER_MODULE.evaluate(reviewed_case(), material(document=document))


@pytest.mark.parametrize(
    ("snapshots", "state", "reason"),
    [
        (0, "PLAYABLE", "NO_SNAPSHOT_ADMITTED"),
        (1, "CONNECTING", "CONNECTION_NOT_PLAYABLE:CONNECTING"),
        (1, None, "CONNECTION_NOT_PLAYABLE:None"),
    ],
)
def test_a_join_without_an_admitted_first_snapshot_is_not_a_join(
    snapshots: int, state: str | None, reason: str
) -> None:
    document = run_document(snapshots_admitted=snapshots, connection_state=state)

    verdict = ASSERTER_MODULE.evaluate(reviewed_case(), material(document=document))

    assert f"first_snapshot_admitted:{reason}" in verdict.failures
    # The other two assertions do not depend on it and still hold.
    assert verdict.result == "FAIL"
    assert "server_observed_join_identity" in verdict.observed


def test_a_leave_logged_before_the_join_is_not_this_run_s_end() -> None:
    verdict = ASSERTER_MODULE.evaluate(reviewed_case(), material(log=f"{LEFT}\n{JOINED}\n"))

    assert "leave_after_join_observed:LEAVE_BEFORE_JOIN" in verdict.failures


def test_an_ending_that_is_not_a_clean_exit_says_which_one_it_was() -> None:
    document = run_document(outcome="BRIDGE_LOST")

    verdict = ASSERTER_MODULE.evaluate(reviewed_case(), material(document=document))

    assert "leave_after_join_observed:OUTCOME_NOT_A_CLEAN_EXIT:BRIDGE_LOST" in verdict.failures


def test_an_assertion_nothing_implements_makes_the_whole_verdict_incomplete() -> None:
    """Not FAIL: a case whose checks cannot be performed has proven nothing."""

    case = reviewed_case() | {"assertions": ["server_observed_join_identity", "kin_is_happy"]}

    verdict = ASSERTER_MODULE.evaluate(case, material())

    assert verdict.result == "INCOMPLETE"
    assert verdict.unimplemented == ("kin_is_happy",)
    assert verdict.observed == ("server_observed_join_identity",)


def test_a_case_that_asserts_nothing_cannot_pass() -> None:
    case: dict[str, object] = dict(reviewed_case())
    case["assertions"] = []

    verdict = ASSERTER_MODULE.evaluate(case, material())

    assert verdict.result == "INCOMPLETE"
    assert verdict.expected == ()


def write_material(tmp_path: Path, document: dict[str, object], log: str) -> Path:
    (tmp_path / "server.log").write_text(log, encoding="utf-8")
    (tmp_path / "usercache.json").write_text(
        json.dumps([{"name": USERNAME, "uuid": RECORDED_UUID}]), encoding="utf-8"
    )
    path = tmp_path / "session.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ASSERTER), *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def arguments_for(tmp_path: Path, run: Path) -> list[str]:
    return [
        "--case",
        str(REVIEWED_CASE),
        "--run-document",
        str(run),
        "--server-directory",
        str(tmp_path),
        "--username",
        USERNAME,
    ]


def test_the_command_exits_held_when_the_case_holds(tmp_path: Path) -> None:
    run = write_material(tmp_path, run_document(), f"{JOINED}\n{LEFT}\n")

    result = run_cli(*arguments_for(tmp_path, run))

    assert result.returncode == ASSERTER_MODULE.EXIT_HELD, result.stderr
    report = json.loads(result.stdout)
    assert report["result"] == "PASS"
    assert report["failures"] == []


def test_the_command_exits_failed_when_the_case_fails(tmp_path: Path) -> None:
    run = write_material(tmp_path, run_document(), f"{JOINED}\n")

    result = run_cli(*arguments_for(tmp_path, run))

    assert result.returncode == ASSERTER_MODULE.EXIT_FAILED
    assert json.loads(result.stdout)["result"] == "FAIL"


def test_the_command_exits_unjudged_when_the_material_is_unreadable(tmp_path: Path) -> None:
    run = write_material(tmp_path, run_document(), f"{JOINED}\n{LEFT}\n")
    run.unlink()

    result = run_cli(*arguments_for(tmp_path, run))

    assert result.returncode == ASSERTER_MODULE.EXIT_UNJUDGED
    assert json.loads(result.stderr)["status"] == "unreadable"


def test_the_registry_and_the_asserter_name_the_same_assertions() -> None:
    """An implementation nothing can reach, or a registration nothing performs."""

    registered = {
        name
        for name, implementation in CHECKER.IMPLEMENTATIONS.items()
        if implementation.target == CHECKER.RUNTIME_ASSERTER
    }
    assert registered == set(ASSERTER_MODULE.ASSERTIONS)
