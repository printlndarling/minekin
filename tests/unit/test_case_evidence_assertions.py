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
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"
REVIEWED_CASE = CASES / "core-020.json"
OBSERVE_ONLY_CASE = CASES / "core-010.json"
MOVEMENT_CASE = CASES / "core-040.json"
LOST_RUNTIME_CASE = CASES / "core-060.json"
BLACK_HOLE_CASE = CASES / "admit-110.json"
REFUSED_CASE = CASES / "admit-100.json"
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
USERNAME = "Kin"
# The UUID a real run's server recorded for this name, read back from the
# `usercache.json` vanilla wrote next to its log. Asserted below to be what the
# rule derives, so the fixture cannot drift away from vanilla's own algorithm.
RECORDED_UUID = "8f40376b-c23f-3ef1-b553-5564eea75639"

JOINED = f"[19:28:12] [Server thread/INFO]: {USERNAME} joined the game"
LEFT = f"[19:28:40] [Server thread/INFO]: {USERNAME} left the game"


class _Material(Protocol):
    kin_id: str
    run_id: str
    overlay: object
    run_document: Mapping[str, object]
    ledger_events: tuple[Mapping[str, object], ...]
    ledger_readable: bool
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

    #: The server's own answers, one per probe that asked for this shape. Public
    #: because it is how this module reads a position or a rotation, and a case
    #: about a turn reads the other one.
    def probe_readings(self, log: str, components: int) -> tuple[tuple[float, ...], ...]: ...

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


def event(event_type: str, **payload: object) -> Mapping[str, object]:
    """One ledger row, carrying the fields a case reads."""

    return {
        "event_type": event_type,
        "run_id": RUN_ID,
        "payload_json": json.dumps(payload, sort_keys=True),
    }


HANDSHAKE = "BridgeHelloAccepted"


def material(
    *,
    document: dict[str, object] | None = None,
    log: str = f"{JOINED}\n{LEFT}\n",
    client_log: str = "",
    identities: Mapping[str, str] | None = None,
    username: str = USERNAME,
    events: tuple[Mapping[str, object], ...] = (),
    ledger_readable: bool = True,
) -> _Material:
    return ASSERTER_MODULE.RunMaterial(
        kin_id="kin-01",
        run_id=RUN_ID,
        overlay=None,
        run_document=run_document() if document is None else document,
        client_log=client_log,
        ledger_events=events,
        ledger_readable=ledger_readable,
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

    for path in (
        REVIEWED_CASE,
        OBSERVE_ONLY_CASE,
        MOVEMENT_CASE,
        LOST_RUNTIME_CASE,
        BLACK_HOLE_CASE,
        REFUSED_CASE,
    ):
        declared = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))[
            "assertions"
        ]
        assert isinstance(declared, list)
        for name in cast(list[object], declared):
            assert str(name) in ASSERTER_MODULE.ASSERTIONS, f"{path.name} names {name}"


def observe_only_case() -> dict[str, object]:
    """The reviewed L1 case: to the main menu, handshake, still observing."""

    return cast(dict[str, object], json.loads(OBSERVE_ONLY_CASE.read_text(encoding="utf-8")))


def no_world_document(**run_overrides: object) -> dict[str, object]:
    """The run document a session with no server profile prints, as measured."""

    measured: dict[str, object] = {
        "connection_state": None,
        "snapshots_admitted": 0,
        "events_applied": 0,
        "outcome": "BRIDGE_LOST",
    }
    measured.update(run_overrides)
    return run_document(**measured)


def test_a_session_that_only_observed_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        observe_only_case(), material(document=no_world_document(), events=(event(HANDSHAKE),))
    )

    assert verdict.result == "PASS"
    assert verdict.observed == ("handshake_accepted_by_core", "stayed_observe_only")


def test_the_handshake_is_read_from_core_s_own_record() -> None:
    """Measured: the Bridge writes nothing to the client's log without a world.

    So the client cannot be asked whether the handshake happened. Core can, and
    its answer is the one the ledger holds.
    """

    without = ASSERTER_MODULE.evaluate(
        observe_only_case(), material(document=no_world_document(), events=())
    )
    with_it = ASSERTER_MODULE.evaluate(
        observe_only_case(), material(document=no_world_document(), events=(event(HANDSHAKE),))
    )

    assert without.failures == (
        "handshake_accepted_by_core:HANDSHAKE_NOT_RECORDED",
        "stayed_observe_only:NO_HANDSHAKE_TO_OBSERVE_FROM",
    )
    assert with_it.result == "PASS"


@pytest.mark.parametrize(
    ("event_type", "reason"),
    [
        ("JoinObserved", "JOINED_A_WORLD"),
        ("PlayableEstablished", "SNAPSHOT_ADMITTED"),
        ("InputLeaseGranted", "INPUT_LEASED"),
    ],
)
def test_anything_that_drove_the_client_is_not_observation_only(
    event_type: str, reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(
        observe_only_case(),
        material(document=no_world_document(), events=(event(HANDSHAKE), event(event_type))),
    )

    assert f"stayed_observe_only:{reason}" in verdict.failures
    assert verdict.result == "FAIL"


def test_a_snapshot_core_admitted_is_found_without_the_ledger_saying_so() -> None:
    """The two records are checked against each other, not just one of them."""

    verdict = ASSERTER_MODULE.evaluate(
        observe_only_case(),
        material(document=no_world_document(snapshots_admitted=1), events=(event(HANDSHAKE),)),
    )

    assert verdict.failures == ("stayed_observe_only:SNAPSHOT_ADMITTED",)


def test_a_connection_state_is_a_world_even_when_no_event_says_so() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        observe_only_case(),
        material(
            document=no_world_document(connection_state="PLAYABLE"),
            events=(event(HANDSHAKE),),
        ),
    )

    assert verdict.failures == ("stayed_observe_only:CONNECTION_STATE:PLAYABLE",)


def test_an_unreadable_ledger_is_not_a_ledger_that_recorded_nothing() -> None:
    """The two answers mean different things and must not be the same string."""

    verdict = ASSERTER_MODULE.evaluate(
        observe_only_case(), material(document=no_world_document(), ledger_readable=False)
    )

    assert verdict.failures == (
        "handshake_accepted_by_core:LEDGER_UNREADABLE",
        "stayed_observe_only:LEDGER_UNREADABLE",
    )


# The walk a real run produced: the server's own readings, verbatim from a server
# log, and the ledger events a hold leaves behind. The rotation readings are the
# same words as the position readings and are told apart by their shape, which is
# what these tests are built from rather than invented.
WALK_READINGS = (
    "has the following entity data: [-7.5d, -60.0d, 4.5d]\n"
    "has the following entity data: [0.0f, 0.0f]\n"
    "has the following entity data: [-7.5d, -60.0d, 17.663647774198928d]\n"
    "has the following entity data: [0.0f, 0.0f]\n"
    "has the following entity data: [-7.5d, -60.0d, 17.663647774198928d]\n"
)

LEASE = event(
    "InputLeaseGranted", capability="control.move.v1", lease_id="e4929e876af04ea29aad535e4142ee70"
)
RELEASE = event("InputReleased", generation=1, had_lease=True, reason="TIMEOUT")


def movement_case() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(MOVEMENT_CASE.read_text(encoding="utf-8")),
    )


def walked(**run_overrides: object) -> _Material:
    return material(
        document=run_document(**run_overrides),
        log=WALK_READINGS,
        events=(event("PlayableEstablished"), LEASE, RELEASE),
    )


def test_a_walk_that_the_server_saw_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(), walked(actions_applied=1, actions_refused=0)
    )

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


def test_a_rotation_reading_is_not_a_position_reading() -> None:
    """Two components or three is what tells them apart, and nothing else does."""

    readings = ASSERTER_MODULE.probe_readings(WALK_READINGS, 3)

    assert len(readings) == 3
    assert all(len(reading) == 3 for reading in readings)


def test_the_displacement_is_measured_by_the_server_not_the_client() -> None:
    """A run whose document is a perfect report of a walk it never walked."""

    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log="has the following entity data: [-7.5d, -60.0d, 4.5d]\n",
            events=(LEASE, RELEASE),
        ),
    )

    assert verdict.failures == ("the_server_saw_the_kin_move:NO_SERVER_READINGS",)


def test_a_shove_is_not_a_step() -> None:
    """Measured: walking is 4.3 blocks a second, a wandering pig is well under one."""

    shuffled = (
        "has the following entity data: [-7.5d, -60.0d, 4.5d]\n"
        "has the following entity data: [-6.2d, -60.0d, 5.1d]\n"
    )

    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=shuffled,
            events=(LEASE, RELEASE),
        ),
    )

    assert verdict.failures == ("the_server_saw_the_kin_move:MOVED_LESS_THAN_A_STEP:1.43",)


def test_a_lease_for_something_else_is_not_a_lease_to_move() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=WALK_READINGS,
            events=(event("InputLeaseGranted", capability="control.look.v1"), RELEASE),
        ),
    )

    assert verdict.failures == ("move_input_was_leased:LEASE_IS_NOT_FOR_A_MOVE:control.look.v1",)


def test_an_input_with_no_lease_at_all_is_named() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=WALK_READINGS,
            events=(event("PlayableEstablished"), RELEASE),
        ),
    )

    assert "move_input_was_leased:NO_LEASE_GRANTED" in verdict.failures


@pytest.mark.parametrize(
    ("applied", "refused", "reason"),
    [(0, 0, "NOTHING_WAS_APPLIED"), (1, 2, "ACTIONS_REFUSED:2")],
)
def test_what_the_bridge_did_with_the_command_is_what_is_reported(
    applied: int, refused: int, reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=applied, actions_refused=refused),
            log=WALK_READINGS,
            events=(LEASE, RELEASE),
        ),
    )

    assert f"the_bridge_carried_the_input_out:{reason}" in verdict.failures


def test_a_release_for_another_reason_is_not_the_hold_ending() -> None:
    """The channel going away is a different fact about a different cause."""

    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=WALK_READINGS,
            events=(LEASE, event("InputReleased", generation=1, had_lease=True, reason="EXPLICIT")),
        ),
    )

    assert (
        "the_lease_expired_and_was_released:RELEASED_FOR_ANOTHER_REASON:EXPLICIT"
        in verdict.failures
    )


def test_a_hold_that_was_never_released_is_named() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=WALK_READINGS,
            events=(LEASE,),
        ),
    )

    assert "the_lease_expired_and_was_released:NO_RELEASE_RECORDED" in verdict.failures


# The line a real run's Bridge wrote when its Core was killed, verbatim from the
# client's own log. This is the L5 evidence: nobody on Core's side was left to
# record anything.
IPC_LOSS = "bridge released 1 input(s) after IPC_LOST"

# A stopped Kin, as the server reported it: it moved, then it did not.
STOPPED_READINGS = (
    "has the following entity data: [-4.5d, -60.0d, 5.636875278936468d]\n"
    "has the following entity data: [-4.5d, -60.0d, 26.390491106420708d]\n"
    "has the following entity data: [-4.5d, -60.0d, 26.399332810280036d]\n"
    "has the following entity data: [-4.5d, -60.0d, 26.399332810280036d]\n"
)


def lost_runtime_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(LOST_RUNTIME_CASE.read_text(encoding="utf-8")))


def killed(**overrides: object) -> _Material:
    """A run whose Core was killed: no run document, and the ledger is the record."""

    arguments: dict[str, object] = {
        "document": {},
        "log": STOPPED_READINGS,
        "client_log": IPC_LOSS,
        "events": (event("PlayableEstablished"), LEASE),
    }
    arguments.update(overrides)
    return material(**arguments)  # type: ignore[arg-type]


def test_a_kin_that_let_go_when_its_runtime_died_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_runtime_case(), killed())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


@pytest.mark.parametrize(
    ("client_log", "reason"),
    [
        ("", "NO_CLIENT_LOG"),
        ("bridge held 1 input(s)\n", "RELEASE_NOT_LOGGED"),
        (
            "bridge released 1 input(s) after CORE_REQUEST\n",
            "RELEASED_FOR_ANOTHER_REASON:CORE_REQUEST",
        ),
        ("bridge released 0 input(s) after IPC_LOST\n", "HELD_NOTHING_WHEN_THE_RUNTIME_WENT_AWAY"),
    ],
)
def test_a_release_that_is_not_the_runtime_going_away_is_named(
    client_log: str, reason: str
) -> None:
    """The reason is the check: only a lost runtime is a lost runtime."""

    verdict = ASSERTER_MODULE.evaluate(lost_runtime_case(), killed(client_log=client_log))

    assert f"the_bridge_released_the_input_when_the_ipc_was_lost:{reason}" in verdict.failures


def test_the_release_is_found_among_other_releases() -> None:
    """A run whose lease expired first and whose runtime died after has both."""

    log = (
        "bridge released 1 input(s) after CORE_REQUEST\nbridge released 1 input(s) after IPC_LOST\n"
    )

    verdict = ASSERTER_MODULE.evaluate(lost_runtime_case(), killed(client_log=log))

    assert "the_bridge_released_the_input_when_the_ipc_was_lost" in verdict.observed


def test_a_kin_still_walking_after_its_runtime_died_is_caught() -> None:
    """The failure this case exists for: keys that were never released."""

    still_walking = STOPPED_READINGS.replace(
        "has the following entity data: [-4.5d, -60.0d, 26.399332810280036d]\n"
        "has the following entity data: [-4.5d, -60.0d, 26.399332810280036d]\n",
        "has the following entity data: [-4.5d, -60.0d, 26.399332810280036d]\n"
        "has the following entity data: [-4.5d, -60.0d, 33.0d]\n",
    )

    verdict = ASSERTER_MODULE.evaluate(lost_runtime_case(), killed(log=still_walking))

    assert (
        "the_server_saw_the_kin_stop_after_the_move:STILL_MOVING_AFTER_THE_RUNTIME_WENT_AWAY"
        in verdict.failures
    )


def test_a_kin_that_left_while_still_moving_is_not_still_holding_keys() -> None:
    """Measured: the kill lands mid-stride, so the last two readings differ.

    A client that has left the game is not holding keys either, and the harness
    waits on the same either-or for the same reason.
    """

    left_mid_stride = (
        "has the following entity data: [2.5d, -60.0d, 4.5d]\n"
        "has the following entity data: [2.5d, -60.0d, 22.804278381990635d]\n" + LEFT + "\n"
    )

    verdict = ASSERTER_MODULE.evaluate(lost_runtime_case(), killed(log=left_mid_stride))

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected


def test_a_kin_that_never_moved_did_not_stop() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        lost_runtime_case(), killed(log="has the following entity data: [-4.5d, -60.0d, 5.0d]\n")
    )

    assert verdict.failures == ("the_server_saw_the_kin_stop_after_the_move:NO_SERVER_READINGS",)


# The run a black hole produced: the attempt reached LOGIN_NEGOTIATING and stayed
# there, and the Bridge's own line is what says the cancel arrived.
BLACK_HOLE_CANCEL = "bridge is cancelling the client's connection (screen matches: false)"


def black_hole_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(BLACK_HOLE_CASE.read_text(encoding="utf-8")))


def never_answered(**overrides: object) -> _Material:
    document = no_world_document(connection_cancelled="TIMEOUT", outcome="BRIDGE_LOST")
    arguments: dict[str, object] = {
        "document": document,
        "client_log": BLACK_HOLE_CANCEL,
        "events": (event(HANDSHAKE),),
    }
    arguments.update(overrides)
    return material(**arguments)  # type: ignore[arg-type]


def test_a_target_that_never_answered_gives_core_a_deadline_to_give_up_on() -> None:
    verdict = ASSERTER_MODULE.evaluate(black_hole_case(), never_answered())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


@pytest.mark.parametrize(
    ("cancelled", "reason"),
    [
        ("", "NO_ATTEMPT_WAS_ABANDONED"),
        ("OPERATOR", "ABANDONED_FOR_ANOTHER_REASON:OPERATOR"),
    ],
)
def test_an_attempt_abandoned_for_something_else_is_named(cancelled: str, reason: str) -> None:
    verdict = ASSERTER_MODULE.evaluate(
        black_hole_case(),
        never_answered(document=no_world_document(connection_cancelled=cancelled)),
    )

    assert f"the_attempt_was_abandoned_at_its_deadline:{reason}" in verdict.failures


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"events": (event(HANDSHAKE), event("JoinObserved"))}, "THE_BRIDGE_REPORTED_A_JOIN"),
        (
            {"events": (event(HANDSHAKE), event("PlayableEstablished"))},
            "CORE_ADMITTED_A_SNAPSHOT",
        ),
        ({"document": run_document(snapshots_admitted=1)}, "SNAPSHOT_ADMITTED"),
        (
            {"document": run_document(snapshots_admitted=0, connection_state="PLAYABLE")},
            "CONNECTION_STATE:PLAYABLE",
        ),
    ],
)
def test_a_connection_that_was_accepted_is_not_a_join(
    overrides: dict[str, object], reason: str
) -> None:
    """The contract's own warning: TCP, INIT and screen state may not pass alone."""

    verdict = ASSERTER_MODULE.evaluate(black_hole_case(), never_answered(**overrides))

    assert f"no_world_was_joined:{reason}" in verdict.failures


@pytest.mark.parametrize(
    ("client_log", "reason"),
    [
        ("", "NO_CLIENT_LOG"),
        ("bridge asked vanilla to connect to 127.0.0.1:25565\n", "THE_BRIDGE_NEVER_CANCELLED_IT"),
    ],
)
def test_core_giving_up_is_not_the_same_as_the_client_letting_go(
    client_log: str, reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(black_hole_case(), never_answered(client_log=client_log))

    assert f"the_cancel_reached_the_client_and_was_acted_on:{reason}" in verdict.failures


# The refusal a real server produced, in both records: the Bridge's own line in
# the client's log, and the phase-plus-category Core recorded.
REFUSAL = "bridge classified the login failure as ADMISSION_FAILURE_REASON_WHITELIST_REJECTED"


def refused_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(REFUSED_CASE.read_text(encoding="utf-8")))


def refused(**overrides: object) -> _Material:
    arguments: dict[str, object] = {
        "document": run_document(
            connection_state="FAILED", snapshots_admitted=0, outcome="BRIDGE_LOST"
        ),
        "client_log": REFUSAL,
        "events": (
            event(HANDSHAKE),
            event(
                "SessionInterrupted",
                phase="FAILED",
                reason="ADMISSION_FAILURE_REASON_WHITELIST_REJECTED",
            ),
        ),
    }
    arguments.update(overrides)
    return material(**arguments)  # type: ignore[arg-type]


def test_a_server_that_refuses_the_kin_is_classified_and_recorded() -> None:
    verdict = ASSERTER_MODULE.evaluate(refused_case(), refused())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


def test_a_failed_attempt_is_not_a_world_this_run_was_in() -> None:
    """Measured: a refused login ends with the connection state `FAILED`.

    Demanding an empty state would call that a join, which is the opposite of
    what it is. The states that claim a world are the ones checked.
    """

    verdict = ASSERTER_MODULE.evaluate(refused_case(), refused())

    assert "no_world_was_joined" in verdict.observed


def test_a_refusal_that_was_never_classified_is_named() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        refused_case(),
        refused(events=(event(HANDSHAKE), event("SessionInterrupted", phase="FAILED"))),
    )

    assert "the_refusal_was_classified_in_the_ledger:NO_CLASSIFIED_REFUSAL" in verdict.failures


def test_a_category_that_reached_core_without_the_bridge_making_it_is_not_evidence() -> None:
    """Both records are needed: Core recording is not the Bridge recognising."""

    verdict = ASSERTER_MODULE.evaluate(refused_case(), refused(client_log=""))

    assert verdict.failures == ("the_bridge_classified_the_refusal:NO_CLIENT_LOG",)


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


def test_the_departure_is_the_server_s_fact_and_not_core_s_verdict_on_the_ending() -> None:
    """Measured: the harness ends a session by terminating the client.

    The IPC channel closes before Core can see the client's own exit, so a run
    the harness ended normally records `BRIDGE_LOST`. An assertion that demanded
    `CLIENT_EXITED` was asserting the harness's method, not the Kin's departure.
    """

    document = run_document(outcome="BRIDGE_LOST")

    verdict = ASSERTER_MODULE.evaluate(reviewed_case(), material(document=document))

    assert verdict.result == "PASS"
    assert "leave_after_join_observed" in verdict.observed


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
        "--data-root",
        str(tmp_path),
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
