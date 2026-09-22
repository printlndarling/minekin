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
from typing import Any, Protocol, cast

import pytest

from fault_support import fault_record
from minekin_core.adapters.evidence.promotion import load_case_manifest
from minekin_core.adapters.sqlite.connection import connect_writer
from minekin_core.domain.offline_identity import offline_player_uuid

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ASSERTER = REPOSITORY_ROOT / "tools" / "assert_case_evidence.py"
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"
REVIEWED_CASE = CASES / "core-020.json"
OBSERVE_ONLY_CASE = CASES / "core-010.json"
MOVEMENT_CASE = CASES / "core-040.json"
LOST_RUNTIME_CASE = CASES / "core-060.json"
LOST_SERVER_CASE = CASES / "core-060-server-001.json"
LOST_CLIENT_CASE = CASES / "core-060-client-001.json"
RESTART_CASE = CASES / "core-090.json"
SOAK_CASE = CASES / "core-100.json"
#: The session the run before the restart wrote under. Every witness the restart
#: case reads about the crash is bound to it.
DEAD_SESSION = "session-00"
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
    #: The document of the run that hosted a world this one joined, already read:
    #: None when none was given, which is not the same as one that names no world.
    world_run_document: Mapping[str, object] | None
    #: The record the harness wrote when it killed a process, or None when this
    #: run injected no fault. Judged with the rest rather than beside it.
    fault_injection: Mapping[str, object] | None


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
#: The other side of the block reading: what the harness asks the server, and the
#: words it has the server say. Loaded here because the material below is built
#: from those words rather than from a copy of them.
SERVER_TOOL = load("run_controlled_server")


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


def event(
    event_type: str,
    *,
    row_session_id: str = "session-01",
    row_generation: int | str = 1,
    **payload: object,
) -> Mapping[str, object]:
    """One ledger row, carrying the fields a case reads.

    The generation column is written as text, which is what the ledger really
    holds — the writer stores the decimal string because a uint64 does not fit
    SQLite's signed INTEGER — while the payload of the rows that carry a
    coordinate holds the number. A fixture that wrote both as ints would let a
    cross-check comparing them as they arrive pass here and match nothing on a
    real run.
    """

    return {
        "event_type": event_type,
        "run_id": RUN_ID,
        "session_id": row_session_id,
        "generation": str(row_generation),
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
    previous: tuple[str, tuple[Mapping[str, object], ...]] = ("", ()),
    fault_injection: Mapping[str, object] | None = None,
    soak: tuple[str, Mapping[str, object] | None] = ("", None),
    world_run_document: Mapping[str, object] | None = None,
) -> _Material:
    previous_run_id, previous_run_events = previous
    soak_samples, soak_summary = soak
    return ASSERTER_MODULE.RunMaterial(
        kin_id="kin-01",
        run_id=RUN_ID,
        overlay=None,
        run_document=run_document() if document is None else document,
        client_log=client_log,
        ledger_events=events,
        ledger_readable=ledger_readable,
        previous_run_id=previous_run_id,
        previous_run_events=previous_run_events,
        server_log=log,
        server_identities={USERNAME: RECORDED_UUID} if identities is None else identities,
        username=username,
        fault_injection=fault_injection,
        soak_samples=soak_samples,
        soak_summary=soak_summary,
        world_run_document=world_run_document,
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
        REFUSED_EARLY_CASE,
        LOST_RUNTIME_CASE,
        LOST_SERVER_CASE,
        LOST_CLIENT_CASE,
        RESTART_CASE,
        SOAK_CASE,
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


# The readings a real CORE-040 produced, verbatim from a server log: the walk,
# the turn and the block, each as the server answered it. The rotation readings
# are the same words as the position readings and are told apart by their shape,
# which is what these tests are built from rather than invented.
#
# The block is asked about as a predicate, not read as data, and the words are
# the harness's own: measured on this pinned server, `data get block … powered`
# answers "The target block is not a block entity", so the question goes the
# other way round — `execute if block`, whose answer is `Test passed` either way
# unless the command has the server say which state it was asked about.
def block_reading(word: str) -> str:
    """One answer to one block question, as the server writes it."""

    return f"[19:28:12] [Server thread/INFO]: [Server] {word}\n"


CORE_040_READINGS = (
    # Standing at spawn, facing north, the lever in front of the Kin unpowered.
    "has the following entity data: [-7.5d, -60.0d, 4.5d]\n"
    "has the following entity data: [0.0f, 0.0f]\n"
    + block_reading(SERVER_TOOL.BLOCK_INITIAL)
    # Walking, then turning while still walking, with the use key held.
    + "has the following entity data: [-7.5d, -60.0d, 17.663647774198928d]\n"
    "has the following entity data: [45.0f, 0.0f]\n"
    + block_reading(SERVER_TOOL.BLOCK_CHANGED)
    # Stopped where it was, facing where it turned to.
    + "has the following entity data: [-7.5d, -60.0d, 17.663647774198928d]\n"
    "has the following entity data: [45.0f, 0.0f]\n" + block_reading(SERVER_TOOL.BLOCK_CHANGED)
)

#: The same log with no block reading in it at all, which is what a run whose
#: harness never placed a lever looks like.
NO_BLOCK_READINGS = "".join(
    line for line in CORE_040_READINGS.splitlines(keepends=True) if "minekin-target" not in line
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
        log=CORE_040_READINGS,
        events=(event("PlayableEstablished"), LEASE, RELEASE),
    )


def test_a_walk_that_the_server_saw_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(), walked(actions_applied=1, actions_refused=0)
    )

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


def test_the_case_the_walk_is_judged_by_names_every_kind_of_input_it_covers() -> None:
    """CORE-040 is move/look/use, so the manifest has to ask about all three."""

    assert movement_case()["assertions"] == [
        "move_input_was_leased",
        "the_bridge_carried_the_input_out",
        "the_server_saw_the_kin_move",
        "the_lease_expired_and_was_released",
        "the_server_saw_the_kin_turn",
        "the_server_saw_the_block_change",
    ]


def test_a_reading_that_is_not_a_position_is_not_a_position() -> None:
    """Two components or three is what tells them apart, and nothing else does."""

    readings = ASSERTER_MODULE.probe_readings(CORE_040_READINGS, 3)

    assert len(readings) == 3
    assert all(len(reading) == 3 for reading in readings)
    assert len(ASSERTER_MODULE.probe_readings(CORE_040_READINGS, 2)) == 3


def test_the_displacement_is_measured_by_the_server_not_the_client() -> None:
    """A run whose document is a perfect report of a walk it never walked.

    The turn and the block are supplied, so that the reading the server is
    missing is the only thing this material is missing: one position is not a
    displacement, however the run describes itself.
    """

    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=(
                "has the following entity data: [-7.5d, -60.0d, 4.5d]\n"
                "has the following entity data: [0.0f, 0.0f]\n"
                "has the following entity data: [45.0f, 0.0f]\n"
                "minekin-target-initial\n"
                "minekin-target-changed\n"
            ),
            events=(LEASE, RELEASE),
        ),
    )

    assert verdict.failures == ("the_server_saw_the_kin_move:NO_SERVER_READINGS",)


def test_a_shove_is_not_a_step() -> None:
    """Measured: walking is 4.3 blocks a second, a wandering pig is well under one."""

    shuffled = (
        "has the following entity data: [-7.5d, -60.0d, 4.5d]\n"
        "has the following entity data: [-6.2d, -60.0d, 5.1d]\n"
        "has the following entity data: [0.0f, 0.0f]\n"
        "has the following entity data: [45.0f, 0.0f]\n"
        "minekin-target-initial\n"
        "minekin-target-changed\n"
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


def test_a_turn_the_server_never_saw_is_named() -> None:
    """A Kin that walked and used something, with a heading that never changed."""

    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=(
                "has the following entity data: [-7.5d, -60.0d, 4.5d]\n"
                "has the following entity data: [45.0f, 0.0f]\n"
                "minekin-target-initial\n"
                "has the following entity data: [-7.5d, -60.0d, 17.663647774198928d]\n"
                "has the following entity data: [45.0f, 0.0f]\n"
                "minekin-target-changed\n"
            ),
            events=(LEASE, RELEASE),
        ),
    )

    assert verdict.failures == ("the_server_saw_the_kin_turn:NO_TURN_OBSERVED",)


def test_a_lever_that_was_never_pulled_is_named() -> None:
    """The use key held at a lever that stayed exactly as the harness placed it."""

    untouched = CORE_040_READINGS.replace("minekin-target-changed", "")
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=untouched,
            events=(LEASE, RELEASE),
        ),
    )

    assert verdict.failures == ("the_server_saw_the_block_change:THE_BLOCK_NEVER_CHANGED",)


def test_a_block_that_was_never_in_its_placed_state_is_not_a_block_that_changed() -> None:
    """A block already moved on when the first question was asked proves nothing.

    The harness places it in a known state, so a run that never hears that state
    cannot say what the block was before the Kin touched it — and "it is something
    else now" is then a fact about the world rather than about the Kin.
    """

    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=CORE_040_READINGS.replace("minekin-target-initial", ""),
            events=(LEASE, RELEASE),
        ),
    )

    assert verdict.failures == (
        "the_server_saw_the_block_change:THE_BLOCK_WAS_NEVER_IN_ITS_PLACED_STATE",
    )


def test_a_block_nobody_asked_about_is_not_a_block_that_changed() -> None:
    """Silence from the server is not the server saying the world did not change."""

    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=NO_BLOCK_READINGS,
            events=(LEASE, RELEASE),
        ),
    )

    assert verdict.failures == ("the_server_saw_the_block_change:THE_BLOCK_WAS_NEVER_ASKED_ABOUT",)


# The other side of the same fact: what the harness asks the server, and whether
# the words it has the server say are the words this asserter reads. Nothing else
# checks that they are one string, and measured, the previous pair were not: the
# harness asked `data get block … powered`, which this server answers with "The
# target block is not a block entity" for a lever.
TARGET_AT = (-7, -60, 4)


def test_the_block_the_harness_asks_about_is_the_block_the_asserter_reads() -> None:
    """The whole round trip, from the console line to the case holding."""

    commands = SERVER_TOOL.block_probe_commands(TARGET_AT)
    # The block's own coordinates, not a place relative to the Kin: the Kin walks,
    # and a relative question would walk with it.
    assert all(f"{TARGET_AT[0]} {TARGET_AT[1]} {TARGET_AT[2]}" in command for command in commands)
    assert all("^ ^" not in command for command in commands)
    # Questions whose answers are `Test passed` either way, unless the server is
    # made to say which state it was asked about.
    assert all(
        command.endswith("run say " + word)
        for command, word in zip(
            commands, (SERVER_TOOL.BLOCK_INITIAL, SERVER_TOOL.BLOCK_CHANGED), strict=True
        )
    )

    # What the server would write, in the order a run produces it: the block is
    # placed in its first state and the Kin moves it on, so that answer comes
    # first.
    said = "".join(
        f"[19:28:12] [Server thread/INFO]: [Server] {command.rsplit(' ', 1)[-1]}\n"
        for command in commands
    )
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=NO_BLOCK_READINGS + said,
            events=(LEASE, RELEASE),
        ),
    )

    assert verdict.failures == ()
    assert verdict.result == "PASS"


def test_the_before_of_the_change_is_asked_where_the_block_was_just_put() -> None:
    """The one reading that has to be relative, and why it can be."""

    placed = SERVER_TOOL.use_target_command(USERNAME)
    command = SERVER_TOOL.initial_block_probe_command(USERNAME)

    # The same place, asked about in the same breath: whatever offset the block
    # went to, the first question is about that offset and not another.
    offset = placed.split("setblock ", 1)[1].split(" minecraft:", 1)[0]
    assert offset == "^ ^1 ^3"
    assert command.startswith(f"execute at {USERNAME} if block ")
    assert f"if block {offset} " in command
    assert command.endswith(SERVER_TOOL.BLOCK_INITIAL)


def test_the_block_goes_where_the_client_s_own_look_goes() -> None:
    """Geometry, and the reason it is this geometry rather than another.

    Every part of it was measured against this client, and the two earlier scenes
    were both wrong in ways no log showed:

    * **Which layer.** The eyes are at 1.62, so the layer the look travels through
      is the one above the feet — and local coordinates are measured from the feet
      with a forward axis that is *horizontal*: a run whose Kin was pitched ten
      degrees down still had `^ ^ ^2` land in the feet layer, and an `anchored
      eyes` in front of it changed nothing either.
    * **Which block.** A lever's shape is six sixteenths of a block tall and the
      eye is 0.62 of the way up its own, so a level look passes five thousandths
      of a block under a standing lever. A pitched look reaches it only within a
      narrow band of distances, and this run is walking: the walk carries the ray
      along itself, so every lever is at the right distance for a tenth of a
      second. A note block is a full cube and cannot be missed at any distance.
    * **How far.** Three blocks, so the Kin walks into it and stops — which is
      what turns a moving aim into a still one, and is also the walk-and-stop the
      harness waits for.
    """

    placed = SERVER_TOOL.use_target_command(USERNAME)

    assert f"execute at {USERNAME} run setblock ^ ^1 ^3 " in placed
    assert "minecraft:note_block[note=0]" in placed
    # `keep`, so a block that is already there is reported rather than carved out.
    assert placed.endswith(" keep")


def test_the_block_the_asserter_reads_is_the_one_the_harness_asks_about() -> None:
    """One string, not two: the questions name the block the placement named."""

    placed = SERVER_TOOL.use_target_command(USERNAME)
    assert "minecraft:note_block" in placed

    for command in SERVER_TOOL.block_probe_commands(TARGET_AT):
        assert "minecraft:note_block" in command


def test_the_block_s_own_coordinates_come_from_the_server_s_own_reply(tmp_path: Path) -> None:
    """Measured, verbatim: `Changed the block at -7, -60, 4`."""

    log = tmp_path / "server.log"
    log.write_text(
        '[23:09:12] [Server thread/INFO]: Done (3.489s)! For help, type "help"\n'
        "[23:09:13] [Server thread/INFO]: Changed the block at -7, -60, 4\n",
        encoding="utf-8",
    )

    assert SERVER_TOOL.placed_blocks(log) == (TARGET_AT,)


def test_every_block_a_run_put_down_is_still_asked_about(tmp_path: Path) -> None:
    """A run places several, and the ones the Kin has walked past are evidence."""

    log = tmp_path / "server.log"
    log.write_text(
        "[23:09:13] [Server thread/INFO]: Changed the block at -7, -60, 4\n"
        "[23:09:14] [Server thread/INFO]: Changed the block at -5, -60, 6\n",
        encoding="utf-8",
    )

    assert SERVER_TOOL.placed_blocks(log) == (TARGET_AT, (-5, -60, 6))


def test_a_server_that_placed_nothing_has_no_coordinates_to_ask_about(tmp_path: Path) -> None:
    """`keep` refuses a space that is taken, and says so instead of carving."""

    log = tmp_path / "server.log"
    log.write_text("[23:09:13] [Server thread/INFO]: Could not set the block\n", encoding="utf-8")

    assert SERVER_TOOL.placed_blocks(log) == ()
    assert SERVER_TOOL.block_spoken_of(log) is False


def test_the_harness_stops_putting_blocks_down_once_the_server_has_answered(
    tmp_path: Path,
) -> None:
    """The bound on a scene that is set up again and again until it is used."""

    said = tmp_path / "server.log"
    said.write_text(
        f"[19:28:12] [Server thread/INFO]: [Server] {SERVER_TOOL.BLOCK_INITIAL}\n",
        encoding="utf-8",
    )
    assert SERVER_TOOL.block_spoken_of(said) is False
    assert SERVER_TOOL.MAX_USE_TARGETS > 0

    said.write_text(
        said.read_text(encoding="utf-8")
        + f"[19:28:13] [Server thread/INFO]: [Server] {SERVER_TOOL.BLOCK_CHANGED}\n",
        encoding="utf-8",
    )
    assert SERVER_TOOL.block_spoken_of(said) is True


def test_a_block_in_front_of_a_name_that_is_not_a_name_is_refused() -> None:
    """The name goes to the console, where a newline is a second command."""

    with pytest.raises(SystemExit, match="not a vanilla player name"):
        SERVER_TOOL.use_target_command("Kin; op @a")


def test_a_lease_for_something_else_is_not_a_lease_to_move() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=CORE_040_READINGS,
            events=(event("InputLeaseGranted", capability="control.look.v1"), RELEASE),
        ),
    )

    assert verdict.failures == ("move_input_was_leased:LEASE_IS_NOT_FOR_A_MOVE:control.look.v1",)


def test_an_input_with_no_lease_at_all_is_named() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=1, actions_refused=0),
            log=CORE_040_READINGS,
            events=(event("PlayableEstablished"), RELEASE),
        ),
    )

    assert "move_input_was_leased:NO_LEASE_GRANTED" in verdict.failures


@pytest.mark.parametrize(
    ("applied", "refused", "reason"),
    [
        # The counts are not readable at all. `_integer` answers None for an absent
        # field and for a null one alike, so this row stands for both shapes: a
        # document written before Core counted actions, and a partial write.
        (None, 0, "ACTION_COUNTS_MISSING"),
        (0, 0, "NOTHING_WAS_APPLIED"),
        (1, 2, "ACTIONS_REFUSED:2"),
    ],
)
def test_what_the_bridge_did_with_the_command_is_what_is_reported(
    applied: int | None, refused: int | None, reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(
        movement_case(),
        material(
            document=run_document(actions_applied=applied, actions_refused=refused),
            log=CORE_040_READINGS,
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
            log=CORE_040_READINGS,
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
            log=CORE_040_READINGS,
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
    """A run whose Core was killed: no run document, and the ledger is the record.

    The fault record is part of the shape rather than an extra: a run of this case
    is a run whose runtime was killed, and since the case was reviewed it has had
    to say so in a record the helper wrote. Every mutation test below starts from
    this and breaks one field of it.
    """

    arguments: dict[str, object] = {
        "document": {},
        "log": STOPPED_READINGS,
        "client_log": IPC_LOSS,
        "events": (event("PlayableEstablished"), LEASE),
        "fault_injection": fault_record(case_version=load_case_manifest(LOST_RUNTIME_CASE).digest),
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


@pytest.mark.parametrize(
    ("server_log", "reason"),
    [
        # One reading: the world never said where this Kin was twice, so it cannot be
        # asked whether it moved. A log that cannot answer is not a Kin that stood
        # still.
        ("has the following entity data: [-4.5d, -60.0d, 5.0d]\n", "NO_SERVER_READINGS"),
        # Two readings that agree: it stood still, and the world says so — which is
        # still not the "moved and then stopped" this case is about.
        (
            "has the following entity data: [-4.5d, -60.0d, 5.0d]\n"
            "has the following entity data: [-4.5d, -60.0d, 5.0d]\n",
            "NEVER_MOVED:0.00",
        ),
    ],
)
def test_a_kin_that_never_moved_did_not_stop(server_log: str, reason: str) -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_runtime_case(), killed(log=server_log))

    assert verdict.failures == (f"the_server_saw_the_kin_stop_after_the_move:{reason}",)


# The record shape itself lives in one place, `tests/fault_support.py`, because
# the sealer reads the same shape from the other end.


def sigkill_was_confirmed(**overrides: object) -> dict[str, object]:
    """The same kill, judged: the assertion's own name, and its reasons."""

    verdict = ASSERTER_MODULE.evaluate(
        lost_runtime_case(),
        killed(
            fault_injection=fault_record(
                case_version=load_case_manifest(LOST_RUNTIME_CASE).digest, **overrides
            )
        ),
    )
    return {
        "result": verdict.result,
        "observed": verdict.observed,
        "failures": verdict.failures,
    }


def test_a_confirmed_runtime_kill_is_the_injection_the_case_asks_for() -> None:
    """One kill, and the three things it left behind: a lease, a release, a stop.

    The fault record is judged *with* the rest rather than beside it: the case's
    answer is the conjunction, so a run that let go of its keys without a
    confirmed kill is not a run whose runtime died.
    """

    verdict = ASSERTER_MODULE.evaluate(
        lost_runtime_case(),
        killed(
            fault_injection=fault_record(case_version=load_case_manifest(LOST_RUNTIME_CASE).digest)
        ),
    )

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()
    assert "runtime_controller_sigkill_was_confirmed" in verdict.observed


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"case": {"case_id": "CORE-999"}}, "FAULT_RECORD_IS_ANOTHER_CASE:CORE-999"),
        (
            {"case": {"case_version": "0" * 64}},
            "FAULT_RECORD_IS_ANOTHER_CASE_VERSION:" + "0" * 64,
        ),
        ({"target": {"role": "server_jvm"}}, "WRONG_TARGET_ROLE:server_jvm"),
        (
            {"signal": {"name": "SIGTERM", "number": 15, "result": "DELIVERED", "error": None}},
            "NOT_A_SIGKILL:SIGTERM",
        ),
        ({"outcome": "AMBIGUOUS"}, "NOT_INJECTED:AMBIGUOUS"),
        ({"outcome": "NOT_INJECTED"}, "NOT_INJECTED:NOT_INJECTED"),
        (
            {"confirmation_strength": "NONE", "confirmation": None},
            "CONFIRMATION_NOT_IDENTITY_DISAPPEARED:NONE",
        ),
        (
            {"confirmation": {"method": "NONE", "observations": 0}},
            "NOTHING_CONFIRMED_THE_TARGET_DIED",
        ),
    ],
)
def test_a_kill_that_is_not_the_one_the_case_asks_for_is_named(
    overrides: dict[str, object], reason: str
) -> None:
    """The reason is the check: every way of *not* confirming a kill is separate."""

    verdict = sigkill_was_confirmed(**overrides)

    assert verdict["result"] == "FAIL"
    assert f"runtime_controller_sigkill_was_confirmed:{reason}" in cast(
        tuple[str, ...], verdict["failures"]
    )


def test_a_record_that_names_another_run_is_not_this_run_s_kill() -> None:
    """The record and the ledger have to be about the same run, not just a kill."""

    verdict = sigkill_was_confirmed(attribution={"run_id": "0" * 32})

    assert verdict["result"] == "FAIL"
    assert (
        "runtime_controller_sigkill_was_confirmed:FAULT_RECORD_IS_ANOTHER_RUN:" + "0" * 32
        in cast(tuple[str, ...], verdict["failures"])
    )


def test_a_kill_with_no_record_at_all_is_not_a_confirmed_kill() -> None:
    """A kill run that sealed no record has proven the kill only by assertion.

    Which is what this case used to do: the harness said it killed the runtime and
    the readings were read as if it had.
    """

    verdict = ASSERTER_MODULE.evaluate(lost_runtime_case(), killed(fault_injection=None))

    assert verdict.result == "FAIL"
    assert verdict.failures == (
        "runtime_controller_sigkill_was_confirmed:NO_FAULT_INJECTION_RECORD",
    )


def test_a_record_about_another_session_is_not_this_run_s_kill() -> None:
    """The ledger is what the session half of the attribution is checked against."""

    verdict = ASSERTER_MODULE.evaluate(
        lost_runtime_case(),
        killed(
            events=(
                event("SessionProcessStarted", session_id="session-01", generation=1),
                event("PlayableEstablished"),
                LEASE,
            ),
            fault_injection=fault_record(
                case_version=load_case_manifest(LOST_RUNTIME_CASE).digest,
                attribution={"session_id": "session-99"},
            ),
        ),
    )

    assert verdict.result == "FAIL"
    assert (
        "runtime_controller_sigkill_was_confirmed:"
        "FAULT_RECORD_IS_ANOTHER_SESSION:session-99/1" in verdict.failures
    )


def test_a_wait_status_is_not_something_a_record_may_claim() -> None:
    """The helper is not the parent, so it cannot have reaped what it killed."""

    verdict = sigkill_was_confirmed(
        confirmation={
            "method": "PROC_ENTRY_ABSENT",
            "observations": 1,
            "wait_status_available": True,
        }
    )

    assert verdict["result"] == "FAIL"
    assert "runtime_controller_sigkill_was_confirmed:CLAIMED_A_WAIT_STATUS_IT_CANNOT_HAVE" in cast(
        tuple[str, ...], verdict["failures"]
    )


# The three independent witnesses a real server kill leaves behind: the server
# log ends without vanilla's shutdown lines, Core records the playable world
# becoming disconnected, and the Bridge releases what it held before reporting
# that the play connection ended.
ABRUPT_SERVER_LOG = f"{JOINED}\n[19:28:30] [Server thread/INFO]: [Kin: 26.4d]\n"
PLAY_ENDED_RELEASE = "bridge released 1 input(s) after LEFT_PLAYABLE (PLAY_ENDED)"

#: The row that names the session this run belongs to. Every witness the server
#: case reads is bound to that coordinate, so a ledger without it cannot say
#: which session was killed — and that is its own failure, tested on its own.
STARTED = event("SessionProcessStarted", session_id="session-01", generation=1)


def lost_server_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(LOST_SERVER_CASE.read_text(encoding="utf-8")))


def killed_server(**overrides: object) -> _Material:
    definition = load_case_manifest(LOST_SERVER_CASE)
    record = fault_record(
        case_version=definition.digest,
        case={"case_id": definition.case_id},
        target={"role": "server_jvm"},
        supervisor={"role": "server_jvm_root"},
    )
    arguments: dict[str, object] = {
        "document": run_document(connection_state="DISCONNECTED"),
        "log": ABRUPT_SERVER_LOG,
        "client_log": PLAY_ENDED_RELEASE,
        "events": (
            STARTED,
            event("PlayableEstablished"),
            LEASE,
            event("SessionInterrupted", phase="DISCONNECTED"),
        ),
        "fault_injection": record,
    }
    arguments.update(overrides)
    return material(**arguments)  # type: ignore[arg-type]


def test_a_confirmed_server_kill_with_world_loss_and_release_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_server_case(), killed_server())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        # A whole section missing, rather than a field wrong inside one. The record
        # is a cross-check of what was killed against the run that presents it, and a
        # section that is not there is the one shape the per-field rows above cannot
        # reach: they all start from a record that names a case, a target and a run.
        ({"case": None}, "NO_CASE_ATTRIBUTION"),
        ({"target": None}, "NO_TARGET"),
        ({"attribution": None}, "NO_ATTRIBUTION"),
        ({"case": {"case_id": "CORE-060"}}, "FAULT_RECORD_IS_ANOTHER_CASE:CORE-060"),
        (
            {"case": {"case_version": "0" * 64}},
            "FAULT_RECORD_IS_ANOTHER_CASE_VERSION:" + "0" * 64,
        ),
        ({"target": {"role": "runtime_controller"}}, "WRONG_TARGET_ROLE:runtime_controller"),
        (
            {"signal": {"name": "SIGTERM", "number": 15, "result": "DELIVERED"}},
            "NOT_A_SIGKILL:SIGTERM",
        ),
        ({"signal": {"number": 15}}, "WRONG_SIGKILL_NUMBER:15"),
        ({"signal": {"result": "FAILED"}}, "SIGKILL_WAS_NOT_DELIVERED:FAILED"),
        ({"outcome": "AMBIGUOUS"}, "NOT_INJECTED:AMBIGUOUS"),
        (
            {"confirmation_strength": "NONE", "confirmation": None},
            "CONFIRMATION_NOT_IDENTITY_DISAPPEARED:NONE",
        ),
        (
            {"confirmation": {"wait_status_available": True}},
            "CLAIMED_A_WAIT_STATUS_IT_CANNOT_HAVE",
        ),
        ({"attribution": {"run_id": "0" * 32}}, "FAULT_RECORD_IS_ANOTHER_RUN:" + "0" * 32),
        ({"attribution": {"kin_id": "kin-02"}}, "FAULT_RECORD_IS_ANOTHER_KIN:kin-02"),
        (
            {"attribution": {"session_id": "session-02"}},
            "FAULT_RECORD_IS_ANOTHER_SESSION:session-02/1",
        ),
        (
            {"attribution": {"generation": 2}},
            "FAULT_RECORD_IS_ANOTHER_SESSION:session-01/2",
        ),
    ],
)
def test_a_server_kill_record_must_be_exactly_attributed_and_confirmed(
    overrides: dict[str, object], reason: str
) -> None:
    base = cast(dict[str, object], killed_server().fault_injection)
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
            section = dict(cast(Mapping[str, object], base[key]))
            section.update(cast(Mapping[str, object], value))
            base[key] = section
        else:
            base[key] = value

    verdict = ASSERTER_MODULE.evaluate(lost_server_case(), killed_server(fault_injection=base))

    assert verdict.result == "FAIL"
    assert f"server_jvm_sigkill_was_confirmed:{reason}" in verdict.failures


def test_a_server_kill_requires_ledger_session_attribution() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        lost_server_case(),
        killed_server(
            events=(
                event("PlayableEstablished"),
                LEASE,
                event("SessionInterrupted", phase="DISCONNECTED"),
            )
        ),
    )

    assert "server_jvm_sigkill_was_confirmed:NO_SESSION_ATTRIBUTION_IN_LEDGER" in verdict.failures


def test_an_unreadable_ledger_cannot_bind_a_server_kill_to_a_session() -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_server_case(), killed_server(ledger_readable=False))

    assert "server_jvm_sigkill_was_confirmed:LEDGER_UNREADABLE" in verdict.failures
    assert "the_ledger_recorded_world_loss:LEDGER_UNREADABLE" in verdict.failures


def test_a_generation_is_the_same_generation_in_both_of_its_spellings() -> None:
    """The row's column is text and the payload's number is one fact.

    Measured against the writer rather than assumed: `event_store` stores
    `str(generation)` because a uint64 does not fit SQLite's signed INTEGER, and
    the payload of the row that carries the coordinate holds the number. A
    cross-check comparing the two as they arrive would match nothing on a real
    run and report every one of them as unattributed, so both spellings are
    pinned here against the same session.
    """

    rows = (
        event("SessionProcessStarted", row_generation="1", session_id="session-01", generation=1),
        event("PlayableEstablished", row_generation="1"),
        event("InputLeaseGranted", row_generation="1", capability="control.move.v1"),
        event("SessionInterrupted", row_generation="1", phase="DISCONNECTED"),
    )

    verdict = ASSERTER_MODULE.evaluate(lost_server_case(), killed_server(events=rows))

    assert verdict.result == "PASS"
    assert "the_ledger_recorded_world_loss" not in " ".join(verdict.failures)


def test_a_row_whose_column_contradicts_its_payload_attributes_to_neither() -> None:
    """The coordinate written twice has to agree with itself, or it names nothing."""

    verdict = ASSERTER_MODULE.evaluate(
        lost_server_case(),
        killed_server(
            events=(
                event(
                    "SessionProcessStarted",
                    row_session_id="session-02",
                    session_id="session-01",
                    generation=1,
                ),
                event("PlayableEstablished"),
                LEASE,
                event("SessionInterrupted", phase="DISCONNECTED"),
            )
        ),
    )

    assert "server_jvm_sigkill_was_confirmed:NO_SESSION_ATTRIBUTION_IN_LEDGER" in verdict.failures
    assert "the_ledger_recorded_world_loss:NO_SESSION_ATTRIBUTION_IN_LEDGER" in verdict.failures


@pytest.mark.parametrize("marker", ["Stopping the server", "All dimensions are saved"])
def test_a_graceful_server_shutdown_is_not_a_kill_run(marker: str) -> None:
    verdict = ASSERTER_MODULE.evaluate(
        lost_server_case(), killed_server(log=f"{ABRUPT_SERVER_LOG}{marker}\n")
    )

    assert f"the_server_log_has_no_graceful_shutdown:GRACEFUL_SHUTDOWN_LOGGED:{marker}" in (
        verdict.failures
    )


def test_an_absent_server_log_cannot_prove_an_abrupt_shutdown() -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_server_case(), killed_server(log=""))

    assert "the_server_log_has_no_graceful_shutdown:NO_SERVER_LOG" in verdict.failures


@pytest.mark.parametrize(
    ("events", "reason"),
    [
        ((STARTED,), "NO_PLAYABLE_WORLD_RECORDED"),
        ((STARTED, event("PlayableEstablished"), LEASE), "NO_WORLD_LOSS_RECORDED"),
        (
            (
                STARTED,
                event("PlayableEstablished"),
                event("SessionInterrupted", phase="DISCONNECTED"),
            ),
            "NO_MOVE_LEASE_FOR_KILLED_SESSION",
        ),
        (
            (
                STARTED,
                event("PlayableEstablished"),
                LEASE,
                event("SessionInterrupted", phase="FAILED"),
            ),
            "INTERRUPTED_WITHOUT_WORLD_LOSS:FAILED",
        ),
        (
            (
                STARTED,
                event("SessionInterrupted", phase="DISCONNECTED"),
                event("PlayableEstablished"),
                LEASE,
            ),
            "WORLD_LOSS_SEQUENCE_INVALID",
        ),
        (
            (
                STARTED,
                event("PlayableEstablished"),
                event("SessionInterrupted", phase="DISCONNECTED"),
                LEASE,
            ),
            "WORLD_LOSS_SEQUENCE_INVALID",
        ),
    ],
)
def test_the_ledger_must_record_the_playable_world_being_lost(
    events: tuple[Mapping[str, object], ...], reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_server_case(), killed_server(events=events))

    assert f"the_ledger_recorded_world_loss:{reason}" in verdict.failures


@pytest.mark.parametrize(
    "mismatched_event",
    [
        event("PlayableEstablished", row_session_id="session-02"),
        event("InputLeaseGranted", row_generation=2, capability="control.move.v1"),
        event(
            "SessionInterrupted",
            row_session_id="session-02",
            phase="DISCONNECTED",
        ),
    ],
)
def test_server_kill_witnesses_must_belong_to_the_killed_session(
    mismatched_event: Mapping[str, object],
) -> None:
    event_type = str(mismatched_event["event_type"])
    matching = {
        "PlayableEstablished": event("PlayableEstablished"),
        "InputLeaseGranted": LEASE,
        "SessionInterrupted": event("SessionInterrupted", phase="DISCONNECTED"),
    }
    matching[event_type] = mismatched_event
    verdict = ASSERTER_MODULE.evaluate(
        lost_server_case(),
        killed_server(
            events=(
                STARTED,
                matching["PlayableEstablished"],
                matching["InputLeaseGranted"],
                matching["SessionInterrupted"],
            )
        ),
    )

    assert any(
        failure.startswith("the_ledger_recorded_world_loss:") for failure in verdict.failures
    )


@pytest.mark.parametrize(
    ("client_log", "reason"),
    [
        ("", "NO_CLIENT_LOG"),
        ("bridge held 1 input(s)\n", "RELEASE_NOT_LOGGED"),
        (
            "bridge released 1 input(s) after IPC_LOST\n",
            "NO_LEFT_PLAYABLE_RELEASE",
        ),
        (
            "bridge released 1 input(s) after LEFT_PLAYABLE (GUI_OPENED)\n",
            "NO_PLAY_ENDED_RELEASE",
        ),
        (
            "bridge released 0 input(s) after LEFT_PLAYABLE (PLAY_ENDED)\n",
            "HELD_NOTHING_WHEN_PLAY_ENDED",
        ),
    ],
)
def test_the_bridge_must_release_held_input_because_play_ended(
    client_log: str, reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_server_case(), killed_server(client_log=client_log))

    assert f"the_bridge_released_input_when_play_ended:{reason}" in verdict.failures


# The client boundary, from the run that measured it: the ledger is
# `SessionProcessStarted → BridgeHelloAccepted → JoinObserved → PlayableEstablished
# → InputLeaseGranted{control.move.v1} → InputReleased{EXPLICIT} →
# SessionInterrupted{outcome: BRIDGE_LOST}`, and the server logged the Kin leaving.
#
# The release is Core's own event and cannot be the Bridge's: the Bridge is a mod
# inside the process that was killed. Measured once with the Kin dead a second
# before the kill — a slime got it — which is why nothing here depends on the Kin
# being alive when the client dies.
def lost_client_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(LOST_CLIENT_CASE.read_text(encoding="utf-8")))


def killed_client(**overrides: object) -> _Material:
    definition = load_case_manifest(LOST_CLIENT_CASE)
    record = fault_record(
        case_version=definition.digest,
        case={"case_id": definition.case_id},
        target={"role": "client_jvm"},
        supervisor={"role": "client_jvm_root"},
    )
    arguments: dict[str, object] = {
        # The world is what the server's own log says it is, so the join and the
        # leave are the measured lines and not a paraphrase of them.
        "log": f"{JOINED}\n{LEFT}\n",
        "events": (
            STARTED,
            event("BridgeHelloAccepted"),
            event("JoinObserved", phase="JOIN_SEEN"),
            event("PlayableEstablished", phase="PLAYABLE"),
            LEASE,
            event("InputReleased", had_lease=True, reason="EXPLICIT"),
            event("SessionInterrupted", outcome="BRIDGE_LOST"),
        ),
        "fault_injection": record,
    }
    arguments.update(overrides)
    return material(**arguments)  # type: ignore[arg-type]


def test_a_confirmed_client_kill_with_a_session_ending_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_client_case(), killed_client())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


def test_a_client_kill_record_must_be_exactly_attributed_and_confirmed() -> None:
    base = cast(dict[str, object], killed_client().fault_injection)
    target = dict(cast(Mapping[str, object], base["target"]))
    target["role"] = "server_jvm"
    base["target"] = target

    verdict = ASSERTER_MODULE.evaluate(lost_client_case(), killed_client(fault_injection=base))

    assert "client_jvm_sigkill_was_confirmed:WRONG_TARGET_ROLE:server_jvm" in verdict.failures


@pytest.mark.parametrize(
    ("events", "reason"),
    [
        (
            (STARTED, event("PlayableEstablished"), LEASE),
            "NO_WORLD_LOSS_RECORDED",
        ),
        (
            (
                STARTED,
                event("SessionInterrupted", outcome="BRIDGE_LOST"),
                event("PlayableEstablished"),
                LEASE,
            ),
            "SESSION_ENDING_BEFORE_THE_LEASE",
        ),
        (
            (
                event("PlayableEstablished"),
                LEASE,
                event("SessionInterrupted", outcome="BRIDGE_LOST"),
            ),
            "NO_SESSION_ATTRIBUTION_IN_LEDGER",
        ),
        (
            (STARTED, event("PlayableEstablished")),
            "NO_MOVE_LEASE_FOR_KILLED_SESSION",
        ),
    ],
)
def test_a_client_kill_needs_a_session_that_ended_after_the_lease(
    events: tuple[Mapping[str, object], ...], reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_client_case(), killed_client(events=events))

    assert f"the_ledger_recorded_the_session_ending:{reason}" in verdict.failures


def test_an_unreadable_ledger_cannot_bind_a_client_kill_to_a_session() -> None:
    verdict = ASSERTER_MODULE.evaluate(lost_client_case(), killed_client(ledger_readable=False))

    assert "client_jvm_sigkill_was_confirmed:LEDGER_UNREADABLE" in verdict.failures
    assert "the_ledger_recorded_the_session_ending:LEDGER_UNREADABLE" in verdict.failures


def test_a_client_kill_still_needs_the_world_to_have_seen_the_kin_leave() -> None:
    """The process being gone is half of it; the world noticing is the other half."""

    verdict = ASSERTER_MODULE.evaluate(lost_client_case(), killed_client(log=f"{JOINED}\n"))

    assert "leave_after_join_observed:LEAVE_NOT_LOGGED" in verdict.failures


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


def test_a_document_that_never_recorded_a_cancellation_is_not_a_deadline() -> None:
    """The field is absent, not empty: what a document written before Core recorded
    why a connection ended looks like.

    Reading that absence as "no attempt was abandoned" would turn a missing record
    into a satisfied clause, which is the substitution this assertion exists to
    refuse — so the absent shape gets its own reason rather than the empty one's.
    """

    document = document_without(
        no_world_document(connection_cancelled="TIMEOUT"), "connection_cancelled"
    )

    verdict = ASSERTER_MODULE.evaluate(black_hole_case(), never_answered(document=document))

    assert "the_attempt_was_abandoned_at_its_deadline:NO_CONNECTION_RECORD" in verdict.failures


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


def test_a_client_log_that_does_not_classify_it_is_not_evidence_that_it_did() -> None:
    """The branch above is the defensive one; this is the one a real run reaches.

    `the_bridge_classified_the_refusal` refuses twice: when there is no client log
    at all, and when there is one that does not carry the Bridge's own line. Only
    the first was ever exercised, and it is the one a run cannot produce — the
    client always writes a log. The second is what a Bridge that saw a refusal and
    never classified it actually leaves behind, which is exactly the fact this
    assertion exists to notice.
    """

    log = "[19:28:12] [Render thread/INFO]: [minekin-bridge] nothing about a refusal\n"

    verdict = ASSERTER_MODULE.evaluate(refused_case(), refused(client_log=log))

    assert verdict.failures == ("the_bridge_classified_the_refusal:THE_BRIDGE_DID_NOT_CLASSIFY_IT",)


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
        # The count is not there at all. This is a different fact from a count of
        # zero, and it is the one a document written before the counter existed
        # carries — so the assertion names the missing count rather than reading it
        # as nothing admitted.
        (None, "PLAYABLE", "SNAPSHOT_COUNT_MISSING"),
        (0, "PLAYABLE", "NO_SNAPSHOT_ADMITTED"),
        (1, "CONNECTING", "CONNECTION_NOT_PLAYABLE:CONNECTING"),
        (1, None, "CONNECTION_NOT_PLAYABLE:None"),
    ],
)
def test_a_join_without_an_admitted_first_snapshot_is_not_a_join(
    snapshots: int | None, state: str | None, reason: str
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


FAULT_ONLY_CASE: dict[str, object] = {
    "schema_version": 1,
    "case_id": "CORE-060",
    "work_package": "W70",
    "mandatory": False,
    "inputs": [],
    "assertions": ["runtime_controller_sigkill_was_confirmed"],
}


def fault_case(tmp_path: Path) -> Path:
    """A case that asks for the fault record and nothing else."""

    path = tmp_path / "fault-only.json"
    path.write_text(json.dumps(FAULT_ONLY_CASE), encoding="utf-8")
    return path


def ledger_for(tmp_path: Path) -> Path:
    """A real ledger with no events in it, so the material can be read at all."""

    directory = tmp_path / "kin" / "kin-01"
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "kin.sqlite3"
    connect_writer(database).close()
    return database


def test_the_fault_record_travels_by_path_and_as_text_the_same_way(tmp_path: Path) -> None:
    """Two ways to hand it over, one judgement: the sealer uses the second.

    The sealer reads the file once, seals those bytes and passes the same text to
    the asserter, so the judgement cannot be about a file that changed in between.
    Both routes have to reach the same answer for that to mean anything.
    """

    run = write_material(tmp_path, run_document(), f"{JOINED}\n{LEFT}\n")
    ledger_for(tmp_path)
    record = tmp_path / "fault-injection.json"
    case_path = fault_case(tmp_path)
    record.write_text(
        json.dumps(fault_record(case_version=load_case_manifest(case_path).digest)),
        encoding="utf-8",
    )
    base = [
        "--case",
        str(case_path),
        *arguments_for(tmp_path, run)[2:],
    ]

    by_path = run_cli(*base, "--fault-injection", str(record))
    by_text = run_cli(*base, "--fault-injection-json", record.read_text(encoding="utf-8"))
    both = run_cli(*base, "--fault-injection", str(record), "--fault-injection-json", "{}")

    assert by_path.returncode == ASSERTER_MODULE.EXIT_HELD, by_path.stderr
    assert json.loads(by_path.stdout)["result"] == "PASS"
    assert by_text.stdout == by_path.stdout
    assert both.returncode == ASSERTER_MODULE.EXIT_UNJUDGED


def test_the_command_refuses_a_fault_record_a_reader_would_refuse(tmp_path: Path) -> None:
    """The judged document and the sealed one go through one reader."""

    run = write_material(tmp_path, run_document(), f"{JOINED}\n{LEFT}\n")
    ledger_for(tmp_path)
    record = tmp_path / "fault-injection.json"
    case_path = fault_case(tmp_path)
    broken = fault_record(case_version=load_case_manifest(case_path).digest)
    broken["outcome"] = "MAYBE"
    record.write_text(json.dumps(broken), encoding="utf-8")

    result = run_cli(
        "--case",
        str(case_path),
        "--run-document",
        str(run),
        "--data-root",
        str(tmp_path),
        "--server-directory",
        str(tmp_path),
        "--username",
        USERNAME,
        "--fault-injection",
        str(record),
    )

    assert result.returncode == ASSERTER_MODULE.EXIT_UNJUDGED
    assert "INVALID_OUTCOME" in result.stderr


def test_the_registry_and_the_asserter_name_the_same_assertions() -> None:
    """An implementation nothing can reach, or a registration nothing performs."""

    registered = {
        name
        for name, implementation in CHECKER.IMPLEMENTATIONS.items()
        if implementation.target == CHECKER.RUNTIME_ASSERTER
    }
    assert registered == set(ASSERTER_MODULE.ASSERTIONS)


# A run that asked for its hold at the join: the world was real, the Kin was
# there, and nothing was ever driven. The readings are the shape a stillness wait
# produces — the same place, asked twice — and the client's log is the one a run
# writes when the Bridge never presses anything.
REFUSED_EARLY_CASE = CASES / "core-050.json"
JOIN_OBSERVED = "JoinObserved"
INPUT_REFUSED = "InputRefused"
INPUT_LEASED = "InputLeaseGranted"
NOT_PLAYABLE = "NOT_PLAYABLE"
STILL_READINGS = (
    JOINED + "\n"
    "has the following entity data: [-6.5d, -60.0d, 7.5d]\n"
    "has the following entity data: [0.0f, 0.0f]\n"
    "has the following entity data: [-6.5d, -60.0d, 7.5d]\n"
    "has the following entity data: [0.0f, 0.0f]\n"
)


def refused_early_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(REFUSED_EARLY_CASE.read_text(encoding="utf-8")))


def refusal(phase: str = "JOIN_SEEN", *reasons: str) -> Mapping[str, object]:
    return event(
        INPUT_REFUSED,
        phase=phase,
        capabilities=["control.move.v1"],
        refusals=list(reasons or (NOT_PLAYABLE,)),
    )


def asked_too_early(**overrides: object) -> _Material:
    """A run that joined, asked, was refused, and was never driven."""

    arguments: dict[str, object] = {
        "document": run_document(actions_applied=0, actions_refused=0, snapshots_admitted=1),
        "log": STILL_READINGS,
        "client_log": "bridge is waiting for the handshake\n",
        "events": (event(JOIN_OBSERVED), refusal()),
    }
    arguments.update(overrides)
    return material(**arguments)  # type: ignore[arg-type]


def test_a_run_that_asked_too_early_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(refused_early_case(), asked_too_early())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


def test_a_run_that_never_asked_is_not_evidence_that_it_was_refused() -> None:
    """The refusal is the evidence, so a run without one proves nothing at all."""

    verdict = ASSERTER_MODULE.evaluate(
        refused_early_case(), asked_too_early(events=(event(JOIN_OBSERVED),))
    )

    assert "input_was_refused_before_the_world_was_playable:NO_REFUSAL_RECORDED" in verdict.failures


def test_a_refusal_in_another_phase_is_not_a_refusal_at_the_join() -> None:
    """Asked at the wrong moment and refused is a different run.

    The phase is half the claim: "refused, at some point, for some reason" would
    also be true of a run that asked once the world was real and was turned down
    for something else entirely.
    """

    verdict = ASSERTER_MODULE.evaluate(
        refused_early_case(),
        asked_too_early(events=(event(JOIN_OBSERVED), refusal("PLAYABLE", "LEASE_ACTIVE"))),
    )

    assert "input_was_refused_before_the_world_was_playable:REFUSED_OTHERWISE:PLAYABLE" in (
        verdict.failures
    )


def test_a_refusal_that_does_not_say_why_is_not_a_refusal_on_the_record() -> None:
    """The arbiter's reasons are the actionable half of a refusal."""

    verdict = ASSERTER_MODULE.evaluate(
        refused_early_case(),
        asked_too_early(events=(event(JOIN_OBSERVED), refusal("JOIN_SEEN", "LEASE_ACTIVE"))),
    )

    assert "input_was_refused_before_the_world_was_playable:REFUSED_OTHERWISE:JOIN_SEEN" in (
        verdict.failures
    )


def test_a_lease_anywhere_is_not_a_run_that_was_never_driven() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        refused_early_case(),
        asked_too_early(
            events=(
                event(JOIN_OBSERVED),
                refusal(),
                event(INPUT_LEASED, capability="control.move.v1"),
            )
        ),
    )

    assert "no_lease_was_granted:LEASE_GRANTED:control.move.v1" in verdict.failures


def test_a_client_that_was_driven_is_not_a_client_that_was_left_alone() -> None:
    """Core's refusal is Core's account; the client is asked too."""

    verdict = ASSERTER_MODULE.evaluate(
        refused_early_case(),
        asked_too_early(
            client_log="bridge pressed use.hand\nbridge applied 0047d1b8…: holding [use.hand]\n"
        ),
    )

    assert "the_bridge_never_pressed_a_key:KEY_WAS_PRESSED:bridge pressed use.hand" in (
        verdict.failures
    )


def test_a_kin_that_moved_is_not_a_kin_that_was_never_driven() -> None:
    """The world's own account, read against the same threshold as a walk."""

    walked_away = STILL_READINGS + "has the following entity data: [-6.5d, -60.0d, 21.5d]\n"
    verdict = ASSERTER_MODULE.evaluate(refused_early_case(), asked_too_early(log=walked_away))

    assert "the_server_saw_the_kin_arrive_and_never_move:THE_KIN_MOVED:14.00" in verdict.failures


def test_one_reading_is_a_place_and_not_a_stillness() -> None:
    """Two moments are what "it did not move" is a claim about."""

    one = JOINED + "\n" + "has the following entity data: [-6.5d, -60.0d, 7.5d]\n"
    verdict = ASSERTER_MODULE.evaluate(refused_early_case(), asked_too_early(log=one))

    assert "the_server_saw_the_kin_arrive_and_never_move:NO_SERVER_READINGS" in verdict.failures


# The restart half of CORE-090: a crash run whose ledger stops at the lease, then
# this run. Measured on the pair, the dead run's rows are
# `SessionProcessStarted → BridgeHelloAccepted → JoinObserved → PlayableEstablished
# → InputLeaseGranted{control.move.v1}` and nothing after them — no release, and no
# interruption, because the Core that would have written either was killed. The
# restart gets its own session, admits a new snapshot, asks for nothing, and the
# world reads the same position twice.
def restart_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(RESTART_CASE.read_text(encoding="utf-8")))


def the_dead_run() -> tuple[Mapping[str, object], ...]:
    """What the run before the restart wrote, as the ledger recorded it."""

    return (
        event(
            "SessionProcessStarted",
            row_session_id=DEAD_SESSION,
            session_id=DEAD_SESSION,
            generation=1,
        ),
        event("BridgeHelloAccepted", row_session_id=DEAD_SESSION),
        event("JoinObserved", row_session_id=DEAD_SESSION, phase="JOIN_SEEN"),
        event("PlayableEstablished", row_session_id=DEAD_SESSION, phase="PLAYABLE"),
        event("InputLeaseGranted", row_session_id=DEAD_SESSION, capability="control.move.v1"),
    )


def restarted(**overrides: object) -> _Material:
    """The run that started after the crash."""

    arguments: dict[str, object] = {
        "document": run_document(
            actions_applied=0,
            actions_refused=0,
            snapshots_admitted=1,
            connection_state="PLAYABLE",
        ),
        "log": STILL_READINGS,
        "events": (
            STARTED,
            event("BridgeHelloAccepted"),
            event("JoinObserved", phase="JOIN_SEEN"),
            event("PlayableEstablished", phase="PLAYABLE"),
            event("SessionInterrupted", outcome="BRIDGE_LOST"),
        ),
        "previous": ("d" * 32, the_dead_run()),
    }
    arguments.update(overrides)
    return material(**arguments)  # type: ignore[arg-type]


def test_a_restart_after_a_crash_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(restart_case(), restarted())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


def test_a_restart_without_a_run_before_it_is_not_a_recovery() -> None:
    """The crash is what the case is about, and the ledger is where it is read."""

    verdict = ASSERTER_MODULE.evaluate(restart_case(), restarted(previous=("", ())))

    assert "the_previous_run_left_the_kin_holding_input:NO_PREVIOUS_RUN" in verdict.failures
    assert "the_restart_runs_as_a_new_session:NO_PREVIOUS_RUN" in verdict.failures


def test_a_previous_run_that_ended_cleanly_is_not_a_crash() -> None:
    quiet = (
        *the_dead_run(),
        event("InputReleased", row_session_id=DEAD_SESSION, had_lease=True, reason="EXPLICIT"),
        event("SessionInterrupted", row_session_id=DEAD_SESSION, outcome="BRIDGE_LOST"),
    )

    verdict = ASSERTER_MODULE.evaluate(restart_case(), restarted(previous=("d" * 32, quiet)))

    assert "the_previous_run_left_the_kin_holding_input:PREVIOUS_RUN_RELEASED_ITS_INPUT" in (
        verdict.failures
    )


def test_a_previous_run_that_never_held_input_is_not_a_crash_mid_hold() -> None:
    never_held = tuple(row for row in the_dead_run() if row["event_type"] != "InputLeaseGranted")

    verdict = ASSERTER_MODULE.evaluate(restart_case(), restarted(previous=("d" * 32, never_held)))

    assert "the_previous_run_left_the_kin_holding_input:PREVIOUS_RUN_GRANTED_NO_MOVE_LEASE" in (
        verdict.failures
    )


def test_a_restart_that_reused_the_dead_session_is_not_a_restart() -> None:
    """§7's transient state does not survive a run, and the coordinate says so."""

    replayed = tuple(dict(row, session_id=DEAD_SESSION) for row in restarted().ledger_events)
    replayed = tuple(
        dict(row, payload_json=json.dumps({"session_id": DEAD_SESSION, "generation": 1}))
        if row["event_type"] == "SessionProcessStarted"
        else row
        for row in replayed
    )

    verdict = ASSERTER_MODULE.evaluate(restart_case(), restarted(events=replayed))

    assert f"the_restart_runs_as_a_new_session:SAME_SESSION_AS_THE_DEAD_RUN:{DEAD_SESSION}" in (
        verdict.failures
    )


@pytest.mark.parametrize(
    ("recovery", "reason"),
    [
        (None, "NO_RECOVERY_REPORT"),
        ({"status": "pending", "invalidated": [], "waiting": []}, "NOT_RECONCILED:pending"),
        (
            {"status": "reconciled", "invalidated": [], "waiting": "none"},
            "RECOVERY_WAITING_IS_NOT_A_LIST",
        ),
        (
            {"status": "reconciled", "invalidated": [], "waiting": ["effect-1"]},
            "EFFECTS_STILL_WAITING:1",
        ),
    ],
)
def test_the_restart_must_have_reconciled_before_it_started(recovery: object, reason: str) -> None:
    document = run_document(
        actions_applied=0, actions_refused=0, snapshots_admitted=1, connection_state="PLAYABLE"
    )
    if recovery is None:
        del document["recovery"]
    else:
        document["recovery"] = recovery

    verdict = ASSERTER_MODULE.evaluate(restart_case(), restarted(document=document))

    assert f"the_restart_reconciled_before_it_started:{reason}" in verdict.failures


def test_a_restart_that_never_asked_is_still_not_a_kin_that_was_never_driven() -> None:
    """The stillness is the world's fact, so a world that moved the Kin fails it."""

    walked = STILL_READINGS + "has the following entity data: [-6.5d, -60.0d, 21.5d]\n"

    verdict = ASSERTER_MODULE.evaluate(restart_case(), restarted(log=walked))

    assert any(
        failure.startswith("the_server_saw_the_kin_arrive_and_never_move:")
        for failure in verdict.failures
    )


# The L6 baseline: a bounded soak in a world that was admitted and stayed. The
# samples are the sampler's own shape — label, RSS in KB, threads, and how far
# into the soak the look happened — and the summary is what the harness was asked
# for. Neither is trusted for the other's job: the summary says what was asked,
# the samples say how far the measurement actually reaches.
SOAK_SECONDS = 600
SOAK_INTERVAL = 10


def soak_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(SOAK_CASE.read_text(encoding="utf-8")))


def soak_summary(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": 1,
        "requested_seconds": SOAK_SECONDS,
        "interval_seconds": SOAK_INTERVAL,
        "passes": 61,
        "samples": {"client": 61, "server": 61},
        "ended_early": False,
        "failed_samples": False,
    }
    document.update(overrides)
    return document


def soak_lines(client: int = 61, server: int = 61, span: int = SOAK_SECONDS) -> str:
    """Samples for both processes, spread over `span` seconds."""

    lines: list[str] = []
    for label, count in (("client", client), ("server", server)):
        for index in range(count):
            elapsed = 0 if count == 1 else round(index * span / (count - 1))
            lines.append(f"{label} {520000 + index * 128} {40 + index % 3} {elapsed}")
    return "\n".join(lines) + "\n"


def soaked(**overrides: object) -> _Material:
    arguments: dict[str, object] = {
        "document": run_document(snapshots_admitted=1, connection_state="PLAYABLE"),
        "events": (STARTED, event("PlayableEstablished", phase="PLAYABLE")),
        "soak": (soak_lines(), soak_summary()),
    }
    arguments.update(overrides)
    return material(**arguments)  # type: ignore[arg-type]


def test_a_bounded_soak_of_a_verified_world_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(soak_case(), soaked())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


@pytest.mark.parametrize(
    ("soak", "reason"),
    [
        (("", None), "the_soak_held_for_the_duration_it_was_asked_for:NO_SOAK_SUMMARY"),
        (
            (soak_lines(), soak_summary(ended_early=True)),
            "the_soak_held_for_the_duration_it_was_asked_for:SOAK_ENDED_EARLY",
        ),
        (
            (soak_lines(span=300), soak_summary()),
            "the_soak_held_for_the_duration_it_was_asked_for:SOAK_SHORTER_THAN_REQUESTED:300/600",
        ),
        (
            ("client 1 2 3\nclient 1 2 3\n", soak_summary()),
            "both_jvms_were_sampled_throughout_the_soak:SERVER_WAS_NEVER_SAMPLED",
        ),
        (
            ("server 1 2 3\nserver 1 2 3\n", soak_summary()),
            "both_jvms_were_sampled_throughout_the_soak:CLIENT_WAS_NEVER_SAMPLED",
        ),
        (
            ("client 1 2 0\nserver 1 2 0\n", soak_summary()),
            "both_jvms_were_sampled_throughout_the_soak:TOO_FEW_SAMPLES:1/1",
        ),
        (
            (soak_lines() + "not a sample line\n", soak_summary()),
            "the_soak_held_for_the_duration_it_was_asked_for:NO_SOAK_SAMPLES",
        ),
    ],
)
def test_a_soak_that_did_not_measure_what_it_claims_does_not_hold(
    soak: tuple[str, Mapping[str, object] | None], reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(soak_case(), soaked(soak=soak))

    assert reason in verdict.failures


def test_a_process_that_stopped_being_sampled_is_not_a_baseline_of_it() -> None:
    """It appeared in the soak and then it was gone — which is the failure L6 catches."""

    lines = "".join(f"client 520000 40 {index * 10}\n" for index in range(30)) + "".join(
        f"server 900000 30 {index * 10}\n" for index in range(61)
    )

    verdict = ASSERTER_MODULE.evaluate(soak_case(), soaked(soak=(lines, soak_summary())))

    assert "both_jvms_were_sampled_throughout_the_soak:CLIENT_STOPPED_BEING_SAMPLED:290/600" in (
        verdict.failures
    )


def test_a_soak_of_a_world_that_was_never_verified_is_not_a_baseline() -> None:
    """The session has to have been in an admitted world for its resources to mean anything."""

    verdict = ASSERTER_MODULE.evaluate(
        soak_case(), soaked(document=run_document(snapshots_admitted=0, connection_state=""))
    )

    assert any(failure.startswith("first_snapshot_admitted:") for failure in verdict.failures)


# --- HOST-030: a Kin publishes the world it is hosting -------------------------
HOST_CASE = CASES / "host-030.json"
# The line the client wrote in the runner when it bound the port it was given.
SERVED_ON = "[20:19:39] [Render thread/INFO]: Started serving on 25570"
LEVEL_DIGEST = "aac62c39872dd515dcb0d062a4b8ba5a5c6a333f29a4e1833e1d12686339be15"
#: The digest of the frozen world this case starts from: the run records it over
#: `tests/fixtures/saves/kinworld/level.dat`, and the assertion that checks it reads
#: the frozen manifest. Spelled out rather than hashed here on purpose — a fixture
#: whose bytes changed without this constant changing has to be a failure, and a test
#: that recomputed the digest would agree with whatever it found.
LEVEL_SETTINGS_DIGEST = "3bdd4affd45b65b90dbb7cd25ae34581b6beaf42edcf2324f63f187b5023c00c"


def host_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(HOST_CASE.read_text(encoding="utf-8")))


#: Distinguishes "this case did not say" from "this case says there is none".
_UNSET = object()


def hosted_world(
    *,
    publication: object = _UNSET,
    client_log: str = SERVED_ON,
    world: object = _UNSET,
) -> _Material:
    """A run that hosted a world, with whatever the case is about varied."""

    if publication is _UNSET:
        publication = {"phase": "LAN_OPENED", "port": 25570}
    if world is _UNSET:
        world = {
            "level_name": "kinworld",
            "digest": LEVEL_DIGEST,
            "settings_digest": LEVEL_SETTINGS_DIGEST,
        }
    return material(
        document=run_document(lan_publication=publication, world_snapshot=world),
        client_log=client_log,
    )


def test_a_published_world_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(host_case(), hosted_world())

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected
    assert verdict.failures == ()


@pytest.mark.parametrize(
    ("hosted", "reasons"),
    [
        (
            # Nothing was recorded at all, so neither account exists.
            {"publication": None},
            (
                "core_was_told_the_world_was_published:NO_LAN_PUBLICATION_RECORDED",
                "the_client_published_the_world_on_the_port_it_was_given:"
                "NO_LAN_PUBLICATION_RECORDED",
            ),
        ),
        (
            {"publication": {"phase": "LAN_OPEN_FAILED", "port": 0}},
            (
                "core_was_told_the_world_was_published:LAN_NOT_OPENED:LAN_OPEN_FAILED",
                "the_client_published_the_world_on_the_port_it_was_given:"
                "PORT_MISMATCH:client=25570,core=0",
            ),
        ),
        (
            {"publication": {"phase": "LAN_OPENED", "port": 0}},
            (
                "core_was_told_the_world_was_published:LAN_PORT_IS_NOT_A_PORT:0",
                "the_client_published_the_world_on_the_port_it_was_given:"
                "PORT_MISMATCH:client=25570,core=0",
            ),
        ),
        (
            {"client_log": "[19:54:53] [Render thread/INFO]: Connecting to 127.0.0.1, 25570"},
            (
                "the_client_published_the_world_on_the_port_it_was_given:"
                "CLIENT_NEVER_SAID_IT_WAS_SERVING",
            ),
        ),
        (
            # What the first version of this feature produced: the client chose its own
            # port, so its log said 0 while Core recorded where the world really was.
            {"client_log": "[20:19:39] [Render thread/INFO]: Started serving on 0"},
            (
                "the_client_published_the_world_on_the_port_it_was_given:"
                "PORT_MISMATCH:client=0,core=25570",
            ),
        ),
    ],
)
def test_a_world_that_was_not_published_does_not_hold(
    hosted: dict[str, Any], reasons: tuple[str, ...]
) -> None:
    verdict = ASSERTER_MODULE.evaluate(host_case(), hosted_world(**hosted))

    assert verdict.result == "FAIL"
    assert verdict.failures == reasons


def test_the_world_and_the_address_it_is_reachable_at_are_two_facts() -> None:
    """HOST-030 asks for the local world and the LAN result to be kept apart.

    Each half fails on its own: a world nobody published fails the publication
    assertions while the world is still named, and a publication that names no world
    fails the other one. Neither block can stand in for the other.
    """

    unpublished = ASSERTER_MODULE.evaluate(
        host_case(), hosted_world(publication={"phase": "LAN_OPEN_FAILED", "port": 0})
    )
    unnamed = ASSERTER_MODULE.evaluate(host_case(), hosted_world(world=None))

    assert unpublished.failures == (
        "core_was_told_the_world_was_published:LAN_NOT_OPENED:LAN_OPEN_FAILED",
        "the_client_published_the_world_on_the_port_it_was_given:PORT_MISMATCH:client=25570,core=0",
    )
    assert "the_run_says_which_world_it_hosted" not in str(unpublished.failures)
    # Both world assertions fail on a run that recorded none, and both are right to:
    # the run says nothing about which world it hosted *and* nothing that matches the
    # world the case starts from. The second one is not implied by the first — a run
    # can name a world that is not this case's, which is the next block of tests.
    assert unnamed.failures == (
        "the_run_says_which_world_it_hosted:NO_WORLD_SNAPSHOT_RECORDED",
        "the_world_this_run_had_is_the_one_the_case_names:THIS_RUN_RECORDED_NO_WORLD_OF_ITS_OWN",
    )


def test_a_world_that_is_not_the_case_s_own_is_refused() -> None:
    """The point of naming the fixture in the case: another world is another run.

    Measured with the assertion rather than argued: the world block below is
    perfectly well-formed, names a level, and is the wrong world.
    """

    elsewhere = {
        "level_name": "kinworld",
        "digest": LEVEL_DIGEST,
        "settings_digest": "0" * 64,
    }

    verdict = ASSERTER_MODULE.evaluate(host_case(), hosted_world(world=elsewhere))

    assert verdict.failures == (
        "the_world_this_run_had_is_the_one_the_case_names:THE_RUN_STARTED_FROM_ANOTHER_WORLD:"
        + "0" * 64,
    )


def test_a_world_without_its_settings_is_not_this_case_s_world() -> None:
    """The field the comparison rests on is required, not optional.

    A run that names a level and a snapshot digest but not the configuration digest
    cannot be checked against a fixture at all, so it fails here rather than passing
    for having said something.
    """

    without_settings = {"level_name": "kinworld", "digest": LEVEL_DIGEST}

    verdict = ASSERTER_MODULE.evaluate(host_case(), hosted_world(world=without_settings))

    assert verdict.failures == (
        "the_world_this_run_had_is_the_one_the_case_names:THE_WORLD_SETTINGS_ARE_NOT_A_DIGEST:None",
    )


@pytest.mark.parametrize(
    ("inputs", "reason"),
    [
        # The case this assertion is written for is the one that names a world.
        (
            ["tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json"],
            "THE_CASE_NAMES_NO_WORLD_FIXTURE",
        ),
        # Named, and nothing in the manifest says what it was reviewed as.
        (
            ["tests/fixtures/saves/nowhere"],
            "THE_CASE_DOES_NOT_PIN_THE_WORLD_FIXTURE:tests/fixtures/saves/nowhere/level.dat",
        ),
        # Two of them, and which one this run started from would be a guess.
        (
            ["tests/fixtures/saves/kinworld", "tests/fixtures/saves/also-here"],
            "THE_CASE_NAMES_MORE_THAN_ONE_WORLD:"
            "tests/fixtures/saves/also-here,tests/fixtures/saves/kinworld",
        ),
    ],
)
def test_a_case_that_does_not_name_one_frozen_world_is_refused(
    inputs: list[str], reason: str
) -> None:
    """Every way of not naming one world fails, and says which way it was.

    A well-formed world block is not enough on its own: the case has to name the world
    it starts from, that world has to be one the manifest frozen, and it has to be one,
    not several. The assertion is only worth having if the case cannot quietly leave
    the comparison out.
    """

    case = host_case()
    case["inputs"] = inputs

    verdict = ASSERTER_MODULE.evaluate(case, hosted_world())

    assert verdict.failures == (f"the_world_this_run_had_is_the_one_the_case_names:{reason}",)


def test_a_fixture_that_is_not_the_bytes_that_were_reviewed_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check is against the manifest, so a fixture that moved is a failure.

    This is the branch that separates a check from a tautology: read the digest off
    the file and it always agrees with itself, which is why the comparison value comes
    from the frozen manifest instead.
    """

    monkeypatch.setattr(
        ASSERTER_MODULE,
        "frozen_digests",
        lambda: {
            "tests/fixtures/saves/kinworld/level.dat": "0" * 64,
        },
    )

    verdict = ASSERTER_MODULE.evaluate(host_case(), hosted_world())

    assert verdict.failures == (
        "the_world_this_run_had_is_the_one_the_case_names:"
        "THE_WORLD_FIXTURE_IS_NOT_THE_BYTES_THAT_WERE_REVIEWED:"
        "tests/fixtures/saves/kinworld/level.dat",
    )


def test_the_case_pin_must_equal_the_reviewed_world_digest() -> None:
    case = host_case()
    case["input_digests"] = {
        "tests/fixtures/saves/kinworld/level.dat": "0" * 64,
    }

    verdict = ASSERTER_MODULE.evaluate(case, hosted_world())

    assert verdict.failures == (
        "the_world_this_run_had_is_the_one_the_case_names:"
        "THE_CASE_PINS_ANOTHER_WORLD_FIXTURE:" + "0" * 64,
    )


# --- HOST-040: a second client joins the world this one hosts -------------------
HOST_JOIN_CASE = CASES / "host-040.json"
HOST_JOINED = f"{JOINED}\n[21:17:35] [Server thread/INFO]: Kin2 joined the game\n"
HOST_WITH_A_VISITOR = f"{HOST_JOINED}[21:17:39] [Server thread/INFO]: Kin2 left the game\n"


def join_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(HOST_JOIN_CASE.read_text(encoding="utf-8")))


def test_a_visitor_that_arrived_and_left_holds() -> None:
    verdict = ASSERTER_MODULE.evaluate(join_case(), hosted_world(client_log=HOST_WITH_A_VISITOR))

    assert verdict.result == "PASS"
    assert verdict.observed == verdict.expected


@pytest.mark.parametrize(
    ("client_log", "reasons"),
    [
        # Nobody else ever arrived, which is what a world nobody could reach looks like.
        (f"{JOINED}\n", ("another_kin_joined_the_world_this_run_hosted:NO_OTHER_KIN_EVER_JOINED",)),
        # And a visitor still in the world when the run ended is a different fact.
        (
            HOST_JOINED,
            ("the_world_saw_that_kin_leave_again:STILL_IN_THE_WORLD:Kin2",),
        ),
    ],
)
def test_a_world_without_a_visitor_does_not_hold(client_log: str, reasons: tuple[str, ...]) -> None:
    verdict = ASSERTER_MODULE.evaluate(join_case(), hosted_world(client_log=client_log))

    assert verdict.result == "FAIL"
    assert verdict.failures == reasons


def test_the_kins_own_arrival_is_not_somebody_elses() -> None:
    """The world logs this Kin joining too, and that is not a visitor.

    The username is what separates them, which is why the assertion takes the run's own
    name out of the list rather than counting lines.
    """

    own = f"{JOINED}\n"

    assert (
        ASSERTER_MODULE.ASSERTIONS["another_kin_joined_the_world_this_run_hosted"](
            hosted_world(client_log=own)
        )
        == "NO_OTHER_KIN_EVER_JOINED"
    )


# --- CORE-030: the world the joining client was in ------------------------------
#: The line the Bridge wrote in the runner, measured: CORE-030's real run dialled the
#: port the hosting run had published. It is the only place this client's own record
#: says where it went.
DIALLED = (
    "bridge asked vanilla to connect to 127.0.0.1:25570 for generation 1 "
    "(finishedLoading=true, screen=none, overlay=none)"
)
HOST_PORT = 25570
#: The id of the run that hosted the world, which is not this run's id: a host
#: document is another run's account, and the bundle seals both side by side.
HOST_RUN_ID = "9a1c2b3d4e5f60718293a4b5c6d7e8f9"
#: An identity of the wrong kind — a number where an id belongs. Truthy and not a
#: string, so it is turned away by the type and by nothing else.
WRONG_KIND_ID = 12345
CORE_JOIN_CASE = CASES / "core-030.json"


def core_join_case() -> dict[str, object]:
    return cast(dict[str, object], json.loads(CORE_JOIN_CASE.read_text(encoding="utf-8")))


def host_document(
    *,
    kin_id: object = "kin-02",
    run_id: object = HOST_RUN_ID,
    world: object = _UNSET,
    publication: object = _UNSET,
) -> dict[str, object]:
    """Another Kin's run document: the run that hosted the world this one joined.

    Shaped like the real thing — the world block and the LAN phase on the `run`
    section, where `session_runtime` writes both — with every part of it variable, so
    a test can break exactly one of the things the assertion binds.

    The two identity fields are `object` for the same reason `world` is: a test has to
    be able to put a value of the wrong *kind* there, which is a shape the assertion
    meets in the wild and treats as its own way of being wrong. A field that is absent
    altogether is a different shape again, and `without_keys` below is how a test
    builds it — passing `None` here would only ever say "present and null".
    """

    if world is _UNSET:
        world = {
            "level_name": "kinworld",
            "digest": LEVEL_DIGEST,
            "settings_digest": LEVEL_SETTINGS_DIGEST,
        }
    if publication is _UNSET:
        publication = {"phase": "LAN_OPENED", "port": HOST_PORT}
    return {
        "schema_version": 1,
        "status": "started",
        "kin_id": kin_id,
        "run_id": run_id,
        "run": {
            "schema_version": 1,
            "status": "ended",
            "world_snapshot": world,
            "lan_publication": publication,
        },
    }


def without_keys(document: Mapping[str, object], *keys: str) -> dict[str, object]:
    """The same document with whole fields taken off it, rather than nulled.

    The distinction the assertion is closed against: a host document with no `kin_id`
    key at all is a different document from one that carries `"kin_id": null`, and a
    reader that answered `.get` with the default would read the two as the same
    absence.
    """

    return {key: value for key, value in document.items() if key not in keys}


def joined_world(
    *,
    document: object = _UNSET,
    world_run_document: object = _UNSET,
    client_log: str = DIALLED,
) -> _Material:
    """A run in which this Kin joined another Kin's world.

    Its own document carries no world block at all, which is what a joining client's
    document really looks like: the world it was in belongs to the run that hosted it.
    `_UNSET` is what separates "this test did not say" from "there is no host
    document", which is the distinction the assertion itself is built on — and typing
    the parameter as `object` is the shape this file already uses for inputs a caller
    varies across a whole union of wrong shapes. `document` is the same idea one run
    over: the joining client's own account, whose admission the first-snapshot
    assertion reads.
    """

    host = (
        host_document()
        if world_run_document is _UNSET
        else cast("Mapping[str, object] | None", world_run_document)
    )
    run = run_document() if document is _UNSET else cast("dict[str, object]", document)
    return material(document=run, client_log=client_log, world_run_document=host)


def test_the_join_case_holds_when_the_host_names_the_case_s_world() -> None:
    verdict = ASSERTER_MODULE.evaluate(core_join_case(), joined_world())

    assert verdict.result == "PASS"
    assert verdict.observed == (
        "the_first_snapshot_of_the_world_it_dialled_was_admitted",
        "the_world_this_run_joined_is_the_one_the_case_names",
    )
    assert verdict.failures == ()


#: The other half of the join, spelled once for the tests below: what this client's
#: own record says about the address it dialled and the snapshot it was admitted into.
FIRST_SNAPSHOT_ASSERTION = "the_first_snapshot_of_the_world_it_dialled_was_admitted"


def dialled(*, host: str = "127.0.0.1", port: int | str = HOST_PORT) -> str:
    """The Bridge's own line, with the address under test put inside it.

    The shape is the measured one, not a paraphrase: the assertion reads host, port
    and generation out of this exact wording, so a test that wrote its own sentence
    would be exercising a parser that has never met a real log.
    `test_the_measured_line_is_what_this_helper_builds` is what holds that claim up.
    """

    return (
        f"bridge asked vanilla to connect to {host}:{port} for generation 1 "
        "(finishedLoading=true, screen=none, overlay=none)"
    )


def document_without(document: dict[str, object], *keys: str) -> dict[str, object]:
    """A document with whole fields taken off its `run` block, rather than nulled.

    The same distinction `without_keys` draws one level up: a block carrying no
    `snapshots_admitted` key at all is a different document from one carrying zero,
    and only the second of those is a run that admitted nothing. Taking a `document`
    rather than building one keeps this usable on the measured shapes too — the
    document a session that never reached a world prints, for instance.
    """

    return {**document, "run": without_keys(cast(Mapping[str, object], document["run"]), *keys)}


def test_the_measured_line_is_what_this_helper_builds() -> None:
    """`DIALLED` was measured off a real run, and this is what keeps it the same line.

    Without this the helper above could drift into its own fiction while every test
    using it kept passing — the line and the thing it is supposed to be a copy of are
    only the same line as long as something says so.
    """

    assert dialled() == DIALLED
    assert dialled(host="::1") == DIALLED.replace("127.0.0.1", "::1")


@pytest.mark.parametrize(
    ("client_log", "reason"),
    [
        # The frozen profile admits a loopback literal and nothing else, so a client
        # that reached an address on the network is not this case — whatever it went
        # on to be admitted into.
        (dialled(host="192.168.1.4"), "DIALLED_SOMETHING_BUT_A_LOOPBACK_LITERAL:192.168.1.4"),
        (dialled(host="localhost"), "DIALLED_SOMETHING_BUT_A_LOOPBACK_LITERAL:localhost"),
        # A port that is not one: `0` is what a listener that never bound writes, and
        # the assertion's subject is an address that was actually dialled.
        (dialled(port=0), "DIALLED_A_PORT_THAT_IS_NOT_ONE:0"),
    ],
)
def test_the_address_it_dialled_must_be_a_loopback_literal_and_a_port(
    client_log: str, reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(core_join_case(), joined_world(client_log=client_log))

    assert f"{FIRST_SNAPSHOT_ASSERTION}:{reason}" in verdict.failures


@pytest.mark.parametrize(
    ("document", "reason"),
    [
        # Admitted and never counted: the count is absent, which is not the same fact
        # as a count of zero — a document written before the counter existed reads
        # this way, and so does a partial write.
        (document_without(run_document(), "snapshots_admitted"), "SNAPSHOT_COUNT_MISSING"),
        # Counted, and the count is nothing.
        (run_document(snapshots_admitted=0), "NO_SNAPSHOT_WAS_ADMITTED:0"),
        # A snapshot was admitted and the session never became playable: a client
        # still dialling, which is not a world anybody was in.
        (run_document(connection_state="CONNECTING"), "NEVER_BECAME_PLAYABLE:CONNECTING"),
    ],
)
def test_an_admitted_snapshot_must_be_counted_and_playable(
    document: dict[str, object], reason: str
) -> None:
    verdict = ASSERTER_MODULE.evaluate(core_join_case(), joined_world(document=document))

    assert f"{FIRST_SNAPSHOT_ASSERTION}:{reason}" in verdict.failures


#: The assertion this block of tests is about, spelled once. Every expected failure
#: below is this name and the reason its own line produced — exactly the shape the
#: case's verdict holds, rather than something this file reassembles.
JOINED_WORLD_ASSERTION = "the_world_this_run_joined_is_the_one_the_case_names"


@pytest.mark.parametrize(
    ("overrides", "failures"),
    [
        # No host document at all: a case that asks this question of a run that cannot
        # answer it has proven nothing.
        (
            {"world_run_document": None},
            (f"{JOINED_WORLD_ASSERTION}:THE_RUN_THAT_HOSTED_THIS_WORLD_WAS_NOT_GIVEN",),
        ),
        # This run's own document handed over as the host's. A join has no world block
        # of its own, so nothing here names a world this client was in.
        (
            {"world_run_document": run_document()},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_IS_THE_SAME_KIN_AS_THIS_RUN:kin-01",),
        ),
        # The two fields that name a run, read closed: for each of them, absent,
        # present with a value of another kind, empty, and this run's own. A document
        # that names no run is nobody's account, and one that names *this* run is not
        # an account of a world this run joined — an absent or empty id used to fall
        # through the comparison and pass, which is exactly the shape a substitution
        # takes.
        (
            {"world_run_document": without_keys(host_document(), "kin_id")},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_HAS_NO_KIN_ID:None",),
        ),
        # Truthy, and not a string: a reader that only asked whether the field was
        # empty would let this one through as an identity.
        (
            {"world_run_document": host_document(kin_id=WRONG_KIND_ID)},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_HAS_NO_KIN_ID:{WRONG_KIND_ID!r}",),
        ),
        (
            {"world_run_document": host_document(kin_id="")},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_HAS_NO_KIN_ID:''",),
        ),
        (
            {"world_run_document": host_document(kin_id="kin-01")},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_IS_THE_SAME_KIN_AS_THIS_RUN:kin-01",),
        ),
        (
            {"world_run_document": without_keys(host_document(), "run_id")},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_HAS_NO_RUN_ID:None",),
        ),
        (
            {"world_run_document": host_document(run_id=WRONG_KIND_ID)},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_HAS_NO_RUN_ID:{WRONG_KIND_ID!r}",),
        ),
        (
            {"world_run_document": host_document(run_id="")},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_HAS_NO_RUN_ID:''",),
        ),
        # Another Kin's name over this run's id — the same substitution as the two
        # lines above, with only the Kin field edited, so only the run id can catch it.
        (
            {"world_run_document": host_document(run_id=RUN_ID)},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_IS_THE_SAME_RUN_AS_THIS_RUN:{RUN_ID}",),
        ),
        # Another Kin's document that records no world: given, and says nothing.
        (
            {"world_run_document": host_document(world=None)},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_RECORDED_NO_WORLD_OF_ITS_OWN",),
        ),
        (
            {"world_run_document": {"kin_id": "kin-02", "run_id": HOST_RUN_ID, "run": {}}},
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_RUN_RECORDED_NO_WORLD_OF_ITS_OWN",),
        ),
        # The world's settings are what the case pins, so a block without them cannot
        # be checked against a fixture at all.
        (
            {
                "world_run_document": host_document(
                    world={"level_name": "kinworld", "digest": LEVEL_DIGEST}
                )
            },
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_WORLD_SETTINGS_ARE_NOT_A_DIGEST:None",),
        ),
        # Sixty-four characters is not a digest, and this field is only worth reading
        # because it is compared against one.
        (
            {
                "world_run_document": host_document(
                    world={
                        "level_name": "kinworld",
                        "digest": LEVEL_DIGEST,
                        "settings_digest": "z" * 64,
                    }
                )
            },
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_WORLD_SETTINGS_ARE_NOT_A_DIGEST:{'z' * 64!r}",),
        ),
        # And the other field is required rather than completed from the settings.
        (
            {
                "world_run_document": host_document(
                    world={
                        "level_name": "kinworld",
                        "settings_digest": LEVEL_SETTINGS_DIGEST,
                    }
                )
            },
            (f"{JOINED_WORLD_ASSERTION}:THE_HOST_WORLD_BYTES_ARE_NOT_A_DIGEST:None",),
        ),
        # A well-formed world block that is another world: the whole point of naming
        # the fixture in the case.
        (
            {
                "world_run_document": host_document(
                    world={
                        "level_name": "kinworld",
                        "digest": LEVEL_DIGEST,
                        "settings_digest": "0" * 64,
                    }
                )
            },
            (f"{JOINED_WORLD_ASSERTION}:THE_WORLD_THIS_RUN_JOINED_IS_ANOTHER_WORLD:" + "0" * 64,),
        ),
        # A world nobody opened is not a world anybody joined.
        (
            {
                "world_run_document": host_document(
                    publication={"phase": "LAN_OPEN_FAILED", "port": 0}
                )
            },
            (f"{JOINED_WORLD_ASSERTION}:LAN_NOT_OPENED:LAN_OPEN_FAILED",),
        ),
        (
            {"world_run_document": host_document(publication=None)},
            (f"{JOINED_WORLD_ASSERTION}:NO_LAN_PUBLICATION_RECORDED",),
        ),
        (
            {"world_run_document": host_document(publication={"phase": "LAN_OPENED", "port": 0})},
            (f"{JOINED_WORLD_ASSERTION}:LAN_PORT_IS_NOT_A_PORT:0",),
        ),
        # Published, and somewhere else: the port is the one fact both runs can be
        # held to, because neither of them saw the other.
        (
            {
                "world_run_document": host_document(
                    publication={"phase": "LAN_OPENED", "port": 25565}
                )
            },
            (
                f"{JOINED_WORLD_ASSERTION}:THE_WORLD_WAS_PUBLISHED_ON_ANOTHER_PORT:"
                "host=25565,dialled=25570",
            ),
        ),
        # A run whose own record never says where it went cannot be bound to anything —
        # and the other half of the case fails with it, which is listed rather than
        # filtered: what the joined half says has to be readable next to it.
        (
            {"client_log": ""},
            (
                "the_first_snapshot_of_the_world_it_dialled_was_admitted:NO_CONNECTION_WAS_DIALLED",
                f"{JOINED_WORLD_ASSERTION}:THE_CLIENT_NEVER_DIALLED_A_PORT",
            ),
        ),
    ],
)
def test_a_join_that_cannot_be_bound_to_the_case_s_world_does_not_hold(
    overrides: dict[str, Any], failures: tuple[str, ...]
) -> None:
    """Every way of failing on its own, measured through the real entry point."""

    verdict = ASSERTER_MODULE.evaluate(core_join_case(), joined_world(**overrides))

    assert verdict.result == "FAIL"
    assert verdict.failures == failures


def test_the_join_case_names_the_world_it_starts_from() -> None:
    """The case is the other end of the comparison, so it has to name one world.

    The same rule HOST-030 is held to, read from the same place: the joined half of the
    claim is checkable only because the case says which world the run began in and pins
    its bytes. Without that the assertion would compare a digest against nothing.
    """

    case = core_join_case()

    assert case["inputs"] == [
        "tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json",
        "tests/fixtures/saves/kinworld",
    ]
    assert case["input_digests"] == {
        "tests/fixtures/saves/kinworld/level.dat": LEVEL_SETTINGS_DIGEST
    }


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        # The case this assertion is written for is the one that names a world.
        (
            {"inputs": ["tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json"]},
            "THE_CASE_NAMES_NO_WORLD_FIXTURE",
        ),
        (
            {"inputs": ["tests/fixtures/saves/nowhere"]},
            "THE_CASE_DOES_NOT_PIN_THE_WORLD_FIXTURE:tests/fixtures/saves/nowhere/level.dat",
        ),
        (
            {"inputs": ["tests/fixtures/saves/kinworld", "tests/fixtures/saves/also-here"]},
            "THE_CASE_NAMES_MORE_THAN_ONE_WORLD:"
            "tests/fixtures/saves/also-here,tests/fixtures/saves/kinworld",
        ),
        # The pin and the reviewed manifest disagree: a fixture changed without the
        # case changing, which is what the pin exists to catch.
        (
            {"input_digests": {"tests/fixtures/saves/kinworld/level.dat": "0" * 64}},
            "THE_CASE_PINS_ANOTHER_WORLD_FIXTURE:" + "0" * 64,
        ),
    ],
)
def test_both_world_assertions_read_one_case(change: dict[str, object], reason: str) -> None:
    """One rule for "which world does this case name", asked by both halves.

    The run below both hosted a world and carried the document of the run it joined,
    which is the shape where both assertions reach the case — and the reason they give
    has to be one reason, spelled the same way. A second parser for the case's own
    recipe would be a second place for the case version to mean something else, and
    this is the test that would go red first.
    """

    case = core_join_case()
    case["assertions"] = [
        "the_world_this_run_had_is_the_one_the_case_names",
        "the_world_this_run_joined_is_the_one_the_case_names",
    ]
    case.update(change)

    verdict = ASSERTER_MODULE.evaluate(case, hosting_and_joined_world())

    assert verdict.failures == (
        f"the_world_this_run_had_is_the_one_the_case_names:{reason}",
        f"the_world_this_run_joined_is_the_one_the_case_names:{reason}",
    )


def hosting_and_joined_world() -> _Material:
    """A run that hosted a world of its own *and* carries the document it joined.

    Not a run anybody wants to have: it is the one shape where both world assertions
    reach the case's recipe, which is what the two tests below are about. The sealer
    records such a run as the world it hosted (its own block wins).
    """

    return material(
        document=run_document(
            world_snapshot={
                "level_name": "kinworld",
                "digest": LEVEL_DIGEST,
                "settings_digest": LEVEL_SETTINGS_DIGEST,
            }
        ),
        client_log=DIALLED,
        world_run_document=host_document(),
    )


def test_a_world_fixture_that_moved_is_refused_by_both_world_assertions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The comparison is against the manifest, so it can fail — for both halves.

    Read the digest off the file and every one of these agrees with itself; the value
    comes from the frozen manifest instead, which is the difference between a check
    and a tautology.
    """

    monkeypatch.setattr(
        ASSERTER_MODULE,
        "frozen_digests",
        lambda: {"tests/fixtures/saves/kinworld/level.dat": "0" * 64},
    )
    case = core_join_case()
    case["assertions"] = [
        "the_world_this_run_had_is_the_one_the_case_names",
        "the_world_this_run_joined_is_the_one_the_case_names",
    ]

    verdict = ASSERTER_MODULE.evaluate(case, hosting_and_joined_world())

    moved = (
        "THE_WORLD_FIXTURE_IS_NOT_THE_BYTES_THAT_WERE_REVIEWED:"
        "tests/fixtures/saves/kinworld/level.dat"
    )
    assert verdict.failures == (
        f"the_world_this_run_had_is_the_one_the_case_names:{moved}",
        f"the_world_this_run_joined_is_the_one_the_case_names:{moved}",
    )


def test_the_join_case_names_only_assertions_the_tool_performs() -> None:
    """A case naming an assertion nothing performs would look like coverage."""

    asserted = set(cast(list[str], core_join_case()["assertions"]))

    assert asserted <= set(ASSERTER_MODULE.ASSERTIONS)
    assert asserted <= set(CHECKER.IMPLEMENTATIONS)


# --- the same document, handed over two ways ------------------------------------
def join_cli_arguments(tmp_path: Path, run: Path) -> list[str]:
    """The join case, judged from the command line, with no server of its own."""

    return [
        "--case",
        str(CORE_JOIN_CASE),
        "--run-document",
        str(run),
        "--data-root",
        str(tmp_path),
        "--username",
        USERNAME,
    ]


def join_material(tmp_path: Path) -> Path:
    """A joining run's own document, with the line its Bridge wrote in its own log."""

    overlay = tmp_path / "overlay"
    (overlay / "logs").mkdir(parents=True)
    (overlay / "logs" / "stdout.log").write_text(DIALLED, encoding="utf-8")
    document = run_document()
    # The overlay is a fact about the launch rather than about the session, so it sits
    # at the top of the document and not inside the `run` block — which is where a
    # client's own log is found, and the only place its dialled port is written.
    document["overlay"] = str(overlay)
    return write_material(tmp_path, document, f"{JOINED}\n{LEFT}\n")


def test_the_host_document_travels_by_path_and_as_text_the_same_way(tmp_path: Path) -> None:
    """Two ways to hand it over, one judgement: the sealer uses the second.

    The sealer reads the file once, seals those bytes and passes the same text to the
    asserter, so the verdict cannot be about a document that changed in between. Both
    routes have to reach the same answer — the same file, text for text — or that
    would mean nothing.
    """

    run = join_material(tmp_path)
    ledger_for(tmp_path)
    hosted = tmp_path / "host-session.json"
    hosted.write_text(json.dumps(host_document()), encoding="utf-8")

    by_path = run_cli(*join_cli_arguments(tmp_path, run), "--world-run-document", str(hosted))
    by_text = run_cli(
        *join_cli_arguments(tmp_path, run),
        "--world-run-document-json",
        hosted.read_text(encoding="utf-8"),
    )

    assert by_path.returncode == ASSERTER_MODULE.EXIT_HELD, by_path.stderr
    assert json.loads(by_path.stdout)["result"] == "PASS"
    assert by_text.stdout == by_path.stdout


@pytest.mark.parametrize(
    ("written", "extra_json", "message"),
    [
        # Both ways at once: naming one document twice is not naming it.
        ("{}", "{}", "by its path or by its text, not both"),
        # Given, and not a document at all. Unreadable is not the same answer as "the
        # world it joined is not this case's": one is "nothing was checked", the other
        # is "this was checked and failed".
        ("[]", None, "is not a run document object"),
        ("not json", None, "is not readable JSON"),
    ],
)
def test_a_host_document_that_cannot_be_read_is_not_judged(
    tmp_path: Path, written: str, extra_json: str | None, message: str
) -> None:
    run = join_material(tmp_path)
    ledger_for(tmp_path)
    named = tmp_path / "host-session.json"
    named.write_text(written, encoding="utf-8")
    extra = ["--world-run-document", str(named)]
    if extra_json is not None:
        extra += ["--world-run-document-json", extra_json]

    result = run_cli(*join_cli_arguments(tmp_path, run), *extra)

    assert result.returncode == ASSERTER_MODULE.EXIT_UNJUDGED
    assert message in result.stderr


# ---------------------------------------------------------------------------
# The refusal branches that had no test
# ---------------------------------------------------------------------------
#
# Every assertion here refuses on more than one condition, and covering an
# assertion is not the same as covering its conditions: an audit of the asserter's
# returns against this file found reasons that had never once been produced. The
# first one is why the rest are listed: `the_bridge_classified_the_refusal` had one
# test, and it exercised "there is no client log" — the branch a real run cannot
# reach, because the client always writes one — while the branch a run does reach
# had none.


def test_a_summary_that_does_not_say_what_was_asked_is_incomplete() -> None:
    """Absent and unreadable are different, and only one of them was tested.

    A summary that omits or zeroes the request is not a soak that ran short: it is a
    soak whose target cannot be read at all, which is why this says "incomplete"
    rather than measuring a span against nothing.
    """

    verdict = ASSERTER_MODULE.evaluate(
        soak_case(), soaked(soak=(soak_lines(), soak_summary(requested_seconds=0)))
    )

    assert any(
        failure.startswith(
            "the_soak_held_for_the_duration_it_was_asked_for:SOAK_SUMMARY_INCOMPLETE"
        )
        for failure in verdict.failures
    )


def test_a_world_record_with_no_level_name_is_not_the_world_it_hosted() -> None:
    """The record exists and does not say which world, which is the shape a partial
    write leaves behind. The tested branch was the absent record; this is the one that
    reads as a world and names none.
    """

    verdict = ASSERTER_MODULE.evaluate(
        host_case(),
        hosted_world(world={"digest": LEVEL_DIGEST, "settings_digest": LEVEL_SETTINGS_DIGEST}),
    )

    assert any(
        failure.startswith("the_run_says_which_world_it_hosted:WORLD_SNAPSHOT_HAS_NO_LEVEL_NAME")
        for failure in verdict.failures
    )


def test_a_world_digest_that_is_not_a_digest_is_refused() -> None:
    """A name with something else where the digest goes.

    The assertion's subject is what the run *says* about the world, so a field present
    and not a digest is the case it exists for: reading it as a world would make this
    assertion agree with any string.
    """

    verdict = ASSERTER_MODULE.evaluate(
        host_case(),
        hosted_world(world={"level_name": "kinworld", "digest": "not-a-digest"}),
    )

    assert any(
        failure.startswith("the_run_says_which_world_it_hosted:WORLD_SNAPSHOT_IS_NOT_A_DIGEST")
        for failure in verdict.failures
    )


def test_a_world_that_was_never_published_has_no_other_kin_in_it() -> None:
    """The assertion's other branch is "nobody else joined"; this is "there was no
    world to join".

    Both refuse, and only one was tested. The difference matters to a reader: a run
    that published nothing and saw nobody is not a run where the second half was
    checked, and this branch is the one that says so before looking for the join.

    The case is HOST-040 because that is the one that asks this question; HOST-030
    asks its own four and never declares this assertion at all.
    """

    verdict = ASSERTER_MODULE.evaluate(join_case(), hosted_world(publication=None))

    assert any(
        failure.startswith(
            "another_kin_joined_the_world_this_run_hosted:THIS_RUN_DID_NOT_PUBLISH_A_WORLD"
        )
        for failure in verdict.failures
    )


def test_a_previous_run_with_no_session_attribution_is_not_a_session() -> None:
    """The tested branch is this run's ledger carrying no session; this is the run
    before it carrying none.

    The restart case reads the crash out of the *previous* run's events, so a
    previous run whose rows say nothing about which session they belong to is a
    crash this assertion cannot speak about — which is a refusal, not an absence of
    one.
    """

    unattributed = (
        event("BridgeHelloAccepted"),
        event("PlayableEstablished", phase="PLAYABLE"),
        event("InputLeaseGranted", capability="control.move.v1"),
    )

    verdict = ASSERTER_MODULE.evaluate(restart_case(), restarted(previous=("d" * 32, unattributed)))

    assert any(
        failure.startswith(
            "the_restart_runs_as_a_new_session:PREVIOUS_RUN_HAS_NO_SESSION_ATTRIBUTION"
        )
        for failure in verdict.failures
    )
