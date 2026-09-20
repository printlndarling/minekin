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
    fault_injection: Mapping[str, object] | None = None,
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
        fault_injection=fault_injection,
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
    [(0, 0, "NOTHING_WAS_APPLIED"), (1, 2, "ACTIONS_REFUSED:2")],
)
def test_what_the_bridge_did_with_the_command_is_what_is_reported(
    applied: int, refused: int, reason: str
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


def test_a_kin_that_never_moved_did_not_stop() -> None:
    verdict = ASSERTER_MODULE.evaluate(
        lost_runtime_case(), killed(log="has the following entity data: [-4.5d, -60.0d, 5.0d]\n")
    )

    assert verdict.failures == ("the_server_saw_the_kin_stop_after_the_move:NO_SERVER_READINGS",)


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
