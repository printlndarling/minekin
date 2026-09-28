"""Reading the authorised movement window through the tool that reports it.

`tools/read_move_window.py` decides nothing: it re-reads a run through the same
functions that judge it, and prints the grant, the release, the server's answers on
either side and the displacement credited as the walk. What has to be true, then, is
that every `--control` it offers actually changes the thing it claims to change — a
reviewer who reads "the in-window answers were deleted" needs to know the deletion
landed, and one who reads "a death written after its first in-window answer" needs to
know the gate read that line rather than sailing past it. A control that derived
nothing would still print a verdict, so only a measurement of what each derivation did
to the credited reading or the verdict can tell a real counterexample from a
decorative one.

The log lines are the ones the pinned 1.20.1 server wrote in the runner: the bracketed
clock, `[Server thread/INFO]`, the name, then the answer's trailing `d` per component —
with the orientation pair, two components, sitting next to it and carrying no position.
The window is the measured two-second hold read off a sealed ledger rather than an
invented one, because a fixture with a wider window would let a reading the input was
never authorised for count as the end of the walk, which is the defect the window
exists to close.

The material is a real sealed bundle shape rather than a hand-fed function call, since
the reader's whole use is a bundle a campaign left behind: three artifacts, under the
names the sealer wrote them with, are what has to turn back into a window.
"""

from __future__ import annotations

import importlib
import json
import sys
from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

JOINER = "Kin2"
KIN_ID = "kin-m82-join-0928"
RUN_ID = "1025f9d5852c4e97b0da03de9bae56f8"
#: One bounded forward hold, taken from a sealed joiner bundle's own ledger rows.
GRANT_AT = "2026-09-28T13:10:37.008321Z"
RELEASE_AT = "2026-09-28T13:10:39.008287Z"
WINDOW_SECONDS = 1.999966


def load(name: str) -> Any:
    """One `tools/` module, by the same route `python tools/x.py` would take."""

    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module(f"tools.{name}")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


ASSERTER: Any = load("assert_case_evidence")
READER: Any = load("read_move_window")


def horizontal(before: tuple[float, float, float], after: tuple[float, float, float]) -> float:
    """The step's own distance, computed here rather than off the judged helper.

    These tests check the number a report quotes, and a check that reused the formula
    under test could not catch that formula being wrong.
    """

    return ((after[0] - before[0]) ** 2 + (after[2] - before[2]) ** 2) ** 0.5


def position(clock: str, x: str, z: str) -> str:
    return (
        f"[{clock}] [Server thread/INFO]: {JOINER} has the following entity data: "
        f"[{x}d, -60.0d, {z}d]\n"
    )


def orientation(clock: str, yaw: str, pitch: str) -> str:
    """The second half of one probe's answer, which carries no position at all."""

    return (
        f"[{clock}] [Server thread/INFO]: {JOINER} has the following entity data: "
        f"[{yaw}f, {pitch}f]\n"
    )


def server_line(clock: str, sentence: str) -> str:
    return f"[{clock}] [Server thread/INFO]: {sentence}\n"


#: The lines the two tail controls write, spelled out here the way the log's own lines
#: are: a derivation whose output nobody can name is a derivation nothing can catch.
def derived_death_line() -> str:
    return server_line("13:10:38", f"{JOINER} {READER.DEATH_SENTENCE}")


def derived_departure_line() -> str:
    return server_line("13:10:38", f"{JOINER} {READER.DEPARTURE_SENTENCE}")


#: A walk the world saw: standing at the authorisation's opening edge, then two answers
#: inside the hold six blocks apart, then one unrequested drift after the key was taken
#: back. Every distance below is a whole number of blocks on purpose.
def walked_log() -> str:
    return (
        server_line("13:10:31", f"{JOINER} joined the game")
        + position("13:10:36", "-3.5", "-3.5")
        + orientation("13:10:36", "0.0", "0.0")
        # Written before the grant opened, so it is the last reading the input did not
        # cause — the window's start.
        + position("13:10:37", "-3.5", "-3.4")
        + position("13:10:38", "-6.5", "-3.4")
        + orientation("13:10:38", "45.0", "-20.0")
        + position("13:10:39", "-9.5", "-3.4")
        + orientation("13:10:39", "45.0", "-20.0")
        # After the release: a shove, a wander, gravity — whatever it is, the input is
        # not credited with it.
        + position("13:10:41", "-19.5", "-3.5")
    )


#: The shape P1's acceptance names. The Kin stopped where it was authorised to stop,
#: and the server went on reporting that same place and then a far one. Nothing inside
#: the hold moved; only the tail is large.
def stopped_then_distant_log() -> str:
    return (
        server_line("13:10:31", f"{JOINER} joined the game")
        + position("13:10:37", "-3.5", "-3.5")
        + position("13:10:38", "-3.5", "-3.5")
        + position("13:10:39", "-19.5", "-3.5")
    )


#: A world that answered only outside the hold: a sampling gap, not a walk.
def still_log() -> str:
    return (
        server_line("13:10:31", f"{JOINER} joined the game")
        + position("13:10:36", "-3.5", "-3.5")
        + position("13:10:45", "-19.5", "-3.5")
        + server_line("13:10:50", f"{JOINER} left the game")
    )


def ledger_row(event_type: str, at_utc: str, **payload: object) -> str:
    return json.dumps(
        {
            "event_type": event_type,
            "kin_id": KIN_ID,
            "run_id": RUN_ID,
            "observed_at_utc": at_utc,
            "payload_json": json.dumps(payload, sort_keys=True),
        },
        sort_keys=True,
    )


def write_bundle(
    directory: Path,
    *,
    log: str = walked_log(),
    timeline: tuple[str, ...] | None = None,
) -> Path:
    """A bundle holding exactly the artifacts the reader needs, under the sealer's names.

    `timeline` left as None writes the grant and the release the hold really had. `()`
    leaves the file absent, which is a bundle saying nothing about Core's record — a
    different fact from a timeline that holds no rows.
    """

    rows = (
        (
            ledger_row("InputLeaseGranted", GRANT_AT, capability="control.move.v1"),
            ledger_row("InputReleased", RELEASE_AT, had_lease=True, reason="TIMEOUT"),
        )
        if timeline is None
        else timeline
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "asserter-inputs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kin_id": KIN_ID,
                "run_id": RUN_ID,
                "username": JOINER,
                "previous_run_id": "",
                "probed_players": [JOINER],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    server = directory / "server"
    server.mkdir(exist_ok=True)
    (server / "server.log").write_text(log, encoding="utf-8")
    if rows:
        (directory / "bridge-trace.jsonl").write_text(
            "".join(row + "\n" for row in rows), encoding="utf-8"
        )
    return directory


def material(tmp_path: Path, **bundle_changes: Any) -> Any:
    return ASSERTER.read_sealed_material(write_bundle(tmp_path / "bundle", **bundle_changes))


def window_of(item: Any) -> Any:
    return ASSERTER.move_window_attribution(item.ledger_events, item.server_log, username=JOINER)


def credited(item: Any) -> float | None:
    """How far the window credits this Kin with having walked, or None for no pair."""

    window = window_of(item)
    if window.start is None or window.endpoint is None:
        return None
    return horizontal(window.start.position, window.endpoint.position)


def clocks(log: str) -> tuple[str, ...]:
    return tuple(reading.clock for reading in ASSERTER.stamped_position_readings(log))


def positions(log: str) -> tuple[tuple[float, float, float], ...]:
    return tuple(reading.position for reading in ASSERTER.stamped_position_readings(log))


# --- the reader reads the judgement, not a copy of it ---------------------------------


def test_the_reader_reports_the_verdict_the_judge_gives(tmp_path: Path) -> None:
    """A reading that could quietly disagree with a bundle's verdict is worse than none.

    The tool imports the asserter's functions instead of re-implementing them, and this
    is the check that it does: one material, two callers, one answer.
    """

    item = material(tmp_path)
    payload = READER.report(item, "bundle", [])

    judged = ASSERTER.the_server_saw_the_kin_move(item)
    assert judged is None
    assert payload["verdict"] == judged
    assert payload["attribution_failure"] is None
    assert payload["inside_window"] == 2
    # Five position answers, and the three orientation pairs the same probes wrote are
    # not among them: a reader that took a pair for a place would count eight.
    assert payload["stamped_readings"] == 5
    assert payload["window_seconds"] == pytest.approx(WINDOW_SECONDS)
    assert payload["threshold_blocks"] == 2.0


def test_the_window_start_is_the_last_reading_before_the_grant(tmp_path: Path) -> None:
    """Where the walk is credited from, and how far it is credited with having gone."""

    item = material(tmp_path)
    window = window_of(item)

    # The probe that landed just before the authorisation opened is both the last
    # reading outside it and the walk's start — the same answer, counted once.
    assert window.before is not None and window.before.clock == "[13:10:37]"
    assert window.start is window.before
    assert window.endpoint is not None and window.endpoint.clock == "[13:10:39]"
    assert window.after is not None and window.after.clock == "[13:10:41]"
    assert credited(item) == pytest.approx(6.0)


# --- each control changes what it says it changes ------------------------------------


def test_deleting_the_in_window_answers_refuses_by_naming_the_window(tmp_path: Path) -> None:
    """The bite, measured: with the authorised answers gone the walk has no endpoint.

    The other half is that the remaining log is not short of distance — sixteen blocks
    still sit between its first and last reading — so `NO_READING_INSIDE_WINDOW` can
    only have come from where those answers were, not from how far the Kin got.
    """

    item = material(tmp_path)
    variant, note = READER.derive(item, "drop-window-readings", window_of(item))

    assert note == "the 2 answer(s) the server gave inside the window were deleted"
    assert ASSERTER.the_server_saw_the_kin_move(variant) == "NO_READING_INSIDE_WINDOW"
    assert credited(variant) is None
    # Exactly the two in-window answers went; the join line, the reading before the
    # grant and the drift after the release are all still where the server wrote them.
    assert clocks(variant.server_log) == ("[13:10:36]", "[13:10:37]", "[13:10:41]")
    assert f"{JOINER} joined the game" in variant.server_log
    assert variant.server_log.startswith("[13:10:31] [Server thread/INFO]:")
    assert horizontal(positions(variant.server_log)[0], positions(variant.server_log)[-1]) == (
        pytest.approx(16.0)
    )


def test_keeping_only_the_first_in_window_answer_changes_the_end_of_the_walk(
    tmp_path: Path,
) -> None:
    """The number of authorised answers is what the distance is measured across.

    This one still passes — three blocks is a step — and says so. It is here for the
    credit: drop the second answer and the endpoint moves from six blocks along to
    three, which is how a reviewer sees that a verdict quotes the window's own far end
    rather than the log's.
    """

    item = material(tmp_path)
    variant, note = READER.derive(item, "first-window-reading-only", window_of(item))

    assert note == "only the first of the 2 in-window answers was left standing"
    assert ASSERTER.the_server_saw_the_kin_move(variant) is None
    assert window_of(variant).endpoint is not None
    assert window_of(variant).endpoint.clock == "[13:10:38]"
    assert credited(variant) == pytest.approx(3.0)
    assert credited(item) == pytest.approx(6.0)


def test_a_death_written_after_the_first_answer_ends_the_walk_at_that_answer(
    tmp_path: Path,
) -> None:
    """The derived sentence has to be read by the gate it is supposed to exercise.

    Proved by the difference between two readings of one set of bytes: attributed to
    this Kin the window ends at the answer the death follows and the far report is gone;
    attributed to nobody it still credits a corpse's coordinates sixteen blocks on. A
    derived line the log reader skipped would leave both of those identical — and a line
    that was itself parsed as a position answer would have changed the readings instead.
    """

    item = material(tmp_path, log=stopped_then_distant_log())
    variant, note = READER.derive(item, "death-before-tail", window_of(item))

    assert f"{JOINER} {READER.DEATH_SENTENCE}" in note
    assert clocks(variant.server_log) == clocks(item.server_log)
    # Written where the note says it was: the line the server's own answer is followed
    # by, with nothing between them.
    assert position("13:10:38", "-3.5", "-3.5") + derived_death_line() in variant.server_log
    assert window_of(variant).endpoint is not None
    assert window_of(variant).endpoint.clock == "[13:10:38]"
    assert ASSERTER.the_server_saw_the_kin_move(variant) == (
        "MOVED_LESS_THAN_A_STEP_IN_WINDOW:0.00"
    )
    ungated = ASSERTER.move_window_attribution(variant.ledger_events, variant.server_log)
    assert ungated.endpoint is not None and ungated.endpoint.clock == "[13:10:39]"
    assert ungated.start is not None and ungated.endpoint is not None
    assert horizontal(ungated.start.position, ungated.endpoint.position) == pytest.approx(16.0)
    # Without the death in the log at all, that far reading is exactly what the
    # judgement credits — the counterexample is the sentence, not the distance.
    assert ASSERTER.the_server_saw_the_kin_move(item) is None


def test_a_death_in_a_log_that_really_walked_shortens_the_credit_without_refusing_it(
    tmp_path: Path,
) -> None:
    """The honest reading of the real bundle's third control, at fixture scale.

    Measured on the sealed joiner run this card re-sealed: with the death written after
    its first in-window answer the case still passes, because what the world saw before
    that sentence was already a step (4.57 blocks against the window's 8.58). So this
    control is an attribution check rather than a refusal on such a log, and the refusal
    shape is the one above, where nothing in the window moved.
    """

    item = material(tmp_path)
    variant, _ = READER.derive(item, "death-before-tail", window_of(item))

    assert ASSERTER.the_server_saw_the_kin_move(variant) is None
    assert credited(variant) == pytest.approx(3.0)
    assert credited(item) == pytest.approx(6.0)


def test_a_departure_ends_the_walk_the_same_way_and_is_written_only_once(
    tmp_path: Path,
) -> None:
    """Session end is the same refusal in a different sentence — and one sentence only.

    The run's own later `left the game` is removed first: with two departures the
    earlier one would decide and the derived line would prove nothing about where the
    gate cut. That the count lands on one, and that the one sits against its anchor with
    nothing between, is what makes the derivation single-valued — the removal happens
    past the anchor, so no offset the reader compares has shifted underneath it.
    """

    item = material(
        tmp_path,
        log=stopped_then_distant_log() + server_line("13:10:44", f"{JOINER} left the game"),
    )
    variant, _ = READER.derive(item, "departure-before-tail", window_of(item))

    assert item.server_log.count("left the game") == 1
    assert variant.server_log.count("left the game") == 1
    assert "13:10:44" not in variant.server_log
    assert position("13:10:38", "-3.5", "-3.5") + derived_departure_line() in variant.server_log
    assert window_of(variant).endpoint is not None
    assert window_of(variant).endpoint.clock == "[13:10:38]"
    assert ASSERTER.the_server_saw_the_kin_move(variant) == (
        "MOVED_LESS_THAN_A_STEP_IN_WINDOW:0.00"
    )


def test_the_whole_log_pair_is_measured_by_its_ends_and_named_as_a_comparison(
    tmp_path: Path,
) -> None:
    """#68's escape shape: printed as a comparison, never as a verdict.

    The first and last reading of the walk's log are sixteen blocks apart while the
    authorised window holds six — exactly the gap that let an unrequested drift satisfy
    a judgement about a two-second hold. The derivation is honestly labelled as no
    derivation at all, because the bytes are the run's own.
    """

    item = material(tmp_path)
    variant, note = READER.derive(item, "whole-log-pair", window_of(item))

    assert variant is item
    assert note.startswith("no derivation")
    comparison = READER.whole_log_pair(item)
    assert "16.00 blocks" in comparison
    assert "clears" in comparison
    assert str(ASSERTER.MINIMUM_STEP_BLOCKS) in comparison


def test_a_log_that_answered_once_has_no_whole_log_pair_to_quote(tmp_path: Path) -> None:
    """The comparison says it cannot be made rather than quoting one reading as a span.

    One stamped answer is what a run whose probe only landed once looks like; a
    first/last pair taken from it would be that reading subtracted from itself, and the
    report would print "0.00 blocks" as though it had measured something.
    """

    item = replace(material(tmp_path), server_log=position("13:10:36", "-3.5", "-3.5"))

    assert "there is no first/last pair" in READER.whole_log_pair(item)


# --- refusals to derive, named rather than silently handed back ----------------------


def test_a_window_that_answers_nothing_is_said_to_answer_nothing(tmp_path: Path) -> None:
    """A control over a log that cannot carry it returns the run's bytes and says why.

    Without the notes the three guards would be indistinguishable from a derivation that
    worked: a reviewer would read "would judge NO_READING_INSIDE_WINDOW" against a log
    that was never touched and take it for a counterexample.
    """

    item = material(tmp_path, log=still_log())
    window = window_of(item)
    assert window.failure == "NO_READING_INSIDE_WINDOW"

    dropped, drop_note = READER.derive(item, "drop-window-readings", window)
    first, first_note = READER.derive(item, "first-window-reading-only", window)
    tail, tail_note = READER.derive(item, "death-before-tail", window)

    assert drop_note == "nothing to drop: this window already answers nothing"
    assert first_note == "nothing to cut down: the window answers 0 reading(s)"
    assert tail_note == "no tail to gate: the window answers fewer than two readings"
    assert dropped is item and first is item and tail is item


def test_an_unnamed_control_refuses_before_touching_the_material(tmp_path: Path) -> None:
    """A typo must not read as "no derivation" and hand back the run's verdict.

    `--control` gets its refusal from the parser; `derive` is what anything else in the
    repository would call, so both halves have to say no.
    """

    item = material(tmp_path)
    with pytest.raises(ValueError, match="unknown control"):
        READER.derive(item, "drop-the-threshold", window_of(item))


def test_no_control_widens_the_window_or_moves_the_goalposts(tmp_path: Path) -> None:
    """Every derivation edits the server's log and nothing else.

    The authorisation comes from the ledger, so a control that could change it could
    manufacture the very thing the judgement exists to distrust. The window's two instants
    and the distance threshold are checked across all five controls rather than for one.
    """

    item = material(tmp_path)
    reference = window_of(item)

    for control in READER.CONTROLS:
        variant, _ = READER.derive(item, control, reference)
        assert variant.ledger_events == item.ledger_events, control
        assert variant.username == item.username, control
        assert variant.run_id == item.run_id, control
        after = ASSERTER.move_window_attribution(
            variant.ledger_events, variant.server_log, username=variant.username
        )
        assert after.granted_at == reference.granted_at, control
        assert after.released_at == reference.released_at, control
    assert ASSERTER.MINIMUM_STEP_BLOCKS == 2.0


# --- the command a reviewer runs -----------------------------------------------------


def test_the_command_reads_a_sealed_bundle_and_prints_the_window(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = write_bundle(tmp_path / "a8690e61")

    assert READER.main(["--bundle", str(bundle), "--json"]) == 0

    printed = capsys.readouterr().out
    payload = json.loads(printed.strip().splitlines()[-1])
    assert payload["verdict"] is None
    assert payload["inside_window"] == 2
    assert "grant        : 2026-09-28T13:10:37.008321Z" in printed
    assert "release      : 2026-09-28T13:10:39.008287Z" in printed
    assert "window       : 2.000 s" in printed
    assert (
        "credited     : [13:10:37] (-3.50, -60.00, -3.40) -> "
        "[13:10:39] (-9.50, -60.00, -3.40) = 6.00 blocks" in printed
    )
    assert "verdict      : the window carries a step" in printed


def test_every_control_is_printed_with_its_own_derivation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = write_bundle(tmp_path / "bundle")

    assert READER.main(["--bundle", str(bundle), "--all-controls"]) == 0

    printed = capsys.readouterr().out
    payload = READER.report(
        ASSERTER.read_sealed_material(bundle), str(bundle), list(READER.CONTROLS)
    )
    assert printed.count("control      :") == len(READER.CONTROLS)
    for control in READER.CONTROLS:
        assert f"control      : {control}" in printed
    assert len(payload["controls"]) == len(READER.CONTROLS)
    for entry in payload["controls"]:
        assert entry["derivation"], entry["control"]
        assert entry["credited"], entry["control"]
        tail = entry["control"] in READER.TAIL_CONTROLS
        assert ("credited_without_the_gate" in entry) is tail


def test_a_bundle_that_recorded_inputs_but_no_ledger_is_a_refusal_not_an_empty_window(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ "The run authorised nothing" and "the run's record is missing" are different facts."""

    bundle = write_bundle(tmp_path / "bundle", timeline=())

    assert READER.main(["--bundle", str(bundle)]) == 2
    assert "ledger could not be read" in capsys.readouterr().err


def test_a_directory_that_is_not_a_bundle_is_named_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "not-a-bundle"

    assert READER.main(["--bundle", str(missing)]) == 2
    assert "cannot be read" in capsys.readouterr().err


def test_exactly_one_of_the_two_materials_is_asked_for(tmp_path: Path) -> None:
    bundle = write_bundle(tmp_path / "bundle")

    with pytest.raises(SystemExit) as both:
        READER.main(["--bundle", str(bundle), "--data-root", str(tmp_path)])
    assert both.value.code == 2

    with pytest.raises(SystemExit) as neither:
        READER.main([])
    assert neither.value.code == 2

    with pytest.raises(SystemExit) as unknown:
        READER.main(["--bundle", str(bundle), "--control", "lower-the-threshold"])
    assert unknown.value.code == 2


def test_a_live_run_is_asked_for_by_name_and_reaches_the_reader_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reader's other half is handed a Kin root and a server directory, not a bundle.

    Only the argument mapping is checked: a sealed bundle records the names the run used,
    a live run has to be told them, and getting that wrong reads one Kin's log against
    another's ledger. The bytes a campaign leaves on the volume belong to a runner, not
    to a unit test, so the reading itself is exercised above through the bundle.
    """

    seen: dict[str, Any] = {}

    def pretend(**arguments: Any) -> Any:
        seen.update(arguments)
        return material(tmp_path)

    monkeypatch.setattr(READER, "read_run_material", pretend)
    arguments = Namespace(
        bundle=None,
        data_root=str(tmp_path),
        kin=KIN_ID,
        run_id=RUN_ID,
        username=JOINER,
        server_directory=str(tmp_path / "server-runs" / "run-1"),
        run_document=None,
    )

    item, source = READER.read_material(arguments)

    assert seen == {
        "data_root": tmp_path,
        "server_directory": tmp_path / "server-runs" / "run-1",
        "username": JOINER,
        "run_id": RUN_ID,
        "kin_id": KIN_ID,
        "run_document": None,
    }
    assert source == f"live run under {tmp_path}"
    assert item.username == JOINER
