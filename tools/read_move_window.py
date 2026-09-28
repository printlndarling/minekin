#!/usr/bin/env python3
"""Read the movement window a run authorised, and what the world answered inside it.

`tools/assert_case_evidence.py` judges a sealed bundle against a case. This tool
answers the question a reviewer asks first, which is not "did it pass" but "what was
authorised, what did the server see while it was authorised, and which of its answers
were credited as the ends of that window". It prints the ledger's grant and release,
the server's stamped position readings placed on either side of them, the displacement
between the window's ends, and the assertion's own verdict name.

Nothing here decides anything the case does not already decide: the verdict comes from
`the_server_saw_the_kin_move`, the same function the judge dispatches, so a reading
taken with this tool cannot quietly disagree with a bundle's verdict.

The `--control` switches exist because P1's acceptance asks for counterexamples, not
only a pass. Each takes this run's real bytes, derives a variant of the *server's log*
(the ledger, and so the authorised window, stays the run's own), and reports what the
same assertion would then say and which reading it would credit as the endpoint. That
is how a reviewer checks that a verdict rests on the answers inside the authorisation
rather than on gravity, a wander after the release, or a position frozen over a corpse.
A control never writes to the volume and is never evidence of anything; it names its
own derivation.

Usage:

    # a sealed bundle, as the campaign left it
    uv run python tools/read_move_window.py --bundle DIR

    # a run that is only on the volume yet (inside the runner container)
    MINEKIN_RUNNER_DATA=VOLUME bash test-orchestrator/runner/run.sh --shell \\
        "python tools/read_move_window.py --data-root /data --kin KIN \\
            --username Kin2 --server-directory /data/server-runs/run-1"

    # the counterexamples, from the same material
    ... --all-controls
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# The asserter this tool reads through lives beside it, and one reader of the window
# is the whole point: an attribution re-implemented here would be free to drift from
# the one that judges. Same route `assert_case_evidence.py` itself takes for its
# sibling, so `python tools/read_move_window.py` and `tools.read_move_window` both work.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from assert_case_evidence import (
    MINIMUM_STEP_BLOCKS,
    MoveWindow,
    RunMaterial,
    StampedPosition,
    _horizontal,  # pyright: ignore[reportPrivateUsage]
    move_window_attribution,
    read_run_material,
    read_sealed_material,
    stamped_position_readings,
    the_server_saw_the_kin_move,
)

#: The sentence the vanilla server writes when a player dies, and the one it writes
#: when a player leaves. P1's acceptance names both as things that end a walk's
#: evidence, so each gets a control of its own rather than one shared shape.
DEATH_SENTENCE = "was slain by Zombie"
DEPARTURE_SENTENCE = "left the game"

PASS_LABEL = "the window carries a step"

CONTROLS = (
    "whole-log-pair",
    "drop-window-readings",
    "first-window-reading-only",
    "death-before-tail",
    "departure-before-tail",
)

TAIL_CONTROLS = ("death-before-tail", "departure-before-tail")


def _clock(moment: float | None) -> str:
    if moment is None:
        return "-"
    return datetime.fromtimestamp(moment, UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _position(reading: StampedPosition | None) -> str:
    if reading is None:
        return "-"
    x, y, z = reading.position
    return f"{reading.clock} ({x:.2f}, {y:.2f}, {z:.2f})"


def _drop(log: str, readings: Sequence[StampedPosition]) -> str:
    """The log with whole answer lines removed, matched by where they were written."""

    pieces: list[str] = []
    cursor = 0
    for offset in sorted({reading.line for reading in readings}):
        end = log.find("\n", offset)
        pieces.append(log[cursor:offset])
        cursor = len(log) if end == -1 else end
    pieces.append(log[cursor:])
    return "".join(pieces)


def _write_after(log: str, reading: StampedPosition, line: str) -> str:
    """The log with one server line written directly after an existing answer.

    The stamp is the answer's own, because a derived line with no stamp would be
    skipped rather than read — and the thing under test is a gate on what is read.
    """

    end = log.find("\n", reading.line)
    end = len(log) if end == -1 else end
    return f"{log[:end]}\n{reading.clock} [Server thread/INFO]: {line}{log[end:]}"


def _without_sentence_after(log: str, sentence: str, after_line: int) -> str:
    """The log with this sentence's later occurrences dropped, keeping any earlier one.

    A control that writes a departure has to be the only one that decides, so a
    pre-existing line with the same words after the anchor is removed. Removals after
    the anchor cannot shift it, which is what makes the sentence land where the note
    says it did. A line before the anchor stays: it is the run's own fact rather than
    this derivation's, and the gate already cuts the window at it.
    """

    kept: list[str] = []
    offset = 0
    for line in log.splitlines(keepends=True):
        if not (sentence in line and offset >= after_line):
            kept.append(line)
        offset += len(line)
    return "".join(kept)


def derive(material: RunMaterial, control: str, window: MoveWindow) -> tuple[RunMaterial, str]:
    """The material one control asks about, and what the derivation did to it."""

    inside = window.inside
    if control == "whole-log-pair":
        return (
            material,
            "no derivation — the run's own log, measured by its ends instead of the window's",
        )
    if control == "drop-window-readings":
        if not inside:
            return material, "nothing to drop: this window already answers nothing"
        return (
            replace(material, server_log=_drop(material.server_log, inside)),
            f"the {len(inside)} answer(s) the server gave inside the window were deleted",
        )
    if control == "first-window-reading-only":
        if len(inside) < 2:
            return material, f"nothing to cut down: the window answers {len(inside)} reading(s)"
        return (
            replace(material, server_log=_drop(material.server_log, inside[1:])),
            f"only the first of the {len(inside)} in-window answers was left standing",
        )
    if control in TAIL_CONTROLS:
        if len(inside) < 2:
            return material, "no tail to gate: the window answers fewer than two readings"
        sentence = DEATH_SENTENCE if control == "death-before-tail" else DEPARTURE_SENTENCE
        name = material.username
        log = _without_sentence_after(material.server_log, sentence, inside[0].line)
        variant = replace(
            material,
            server_log=_write_after(log, inside[0], f"{name} {sentence}"),
        )
        why = (
            "a dead player keeps reporting one position, so everything past it is "
            "a corpse's coordinates"
            if control == "death-before-tail"
            else "a departed player is nobody the world can still report a position for"
        )
        return variant, (
            f"{name} {sentence} written after its first in-window answer, so everything past it "
            f"is not an endpoint at all — {why}"
        )
    raise ValueError(f"unknown control {control!r}")


def whole_log_pair(material: RunMaterial) -> str:
    """What the ends of the log — not the ends of the window — say about distance.

    This is the shape that let #68 through: a displacement anywhere in the run
    satisfied a judgement about a two-second authorised hold. Printed as a
    comparison, never as a verdict.
    """

    readings = stamped_position_readings(material.server_log)
    if len(readings) < 2:
        return f"the log answers {len(readings)} reading(s); there is no first/last pair"
    first, last = readings[0], readings[-1]
    distance = _horizontal(first.position, last.position)
    edge = "clears" if distance >= MINIMUM_STEP_BLOCKS else "falls short of"
    return (
        f"{first.clock} -> {last.clock} = {distance:.2f} blocks, which {edge} "
        f"the {MINIMUM_STEP_BLOCKS}-block step"
    )


def _credited(window: MoveWindow) -> str:
    if window.start is None or window.endpoint is None:
        return f"nothing credited: {window.failure or 'no authorised pair'}"
    distance = _horizontal(window.start.position, window.endpoint.position)
    return f"{_position(window.start)} -> {_position(window.endpoint)} = {distance:.2f} blocks"


def read_material(arguments: argparse.Namespace) -> tuple[RunMaterial, str]:
    if arguments.bundle is not None:
        return read_sealed_material(arguments.bundle), str(arguments.bundle)
    server_directory = (
        None if arguments.server_directory is None else Path(arguments.server_directory)
    )
    material = read_run_material(
        run_document=None if arguments.run_document is None else Path(arguments.run_document),
        data_root=Path(arguments.data_root),
        server_directory=server_directory,
        username=arguments.username or "",
        run_id=arguments.run_id,
        kin_id=arguments.kin or "",
    )
    return material, f"live run under {arguments.data_root}"


def report(material: RunMaterial, source: str, controls: Sequence[str]) -> dict[str, Any]:
    window = move_window_attribution(
        material.ledger_events, material.server_log, username=material.username
    )
    readings = stamped_position_readings(material.server_log)
    verdict = the_server_saw_the_kin_move(material)
    span = "-" if window.window_seconds is None else f"{window.window_seconds:.3f} s"

    lines = [
        f"material     : {source}",
        f"identity     : kin={material.kin_id} run={material.run_id} username={material.username}",
        f"ledger       : {'readable' if material.ledger_readable else 'NOT READABLE'}",
        f"grant        : {_clock(window.granted_at)}",
        f"release      : {_clock(window.released_at)}",
        f"window       : {span}",
        f"readings     : {len(readings)} stamped answer(s) in the server's log",
        f"before grant : {_position(window.before)}",
        f"inside       : {len(window.inside)} answer(s)",
        f"after release: {_position(window.after)}",
        f"start        : {_position(window.start)}",
        f"endpoint     : {_position(window.endpoint)}",
        f"credited     : {_credited(window)}",
        f"verdict      : {PASS_LABEL if verdict is None else verdict}",
        f"comparison   : {whole_log_pair(material)}",
    ]
    payload: dict[str, Any] = {
        "source": source,
        "kin_id": material.kin_id,
        "run_id": material.run_id,
        "username": material.username,
        "granted_at_utc": window.granted_at,
        "released_at_utc": window.released_at,
        "window_seconds": window.window_seconds,
        "stamped_readings": len(readings),
        "inside_window": len(window.inside),
        "start": None if window.start is None else asdict(window.start),
        "endpoint": None if window.endpoint is None else asdict(window.endpoint),
        "threshold_blocks": MINIMUM_STEP_BLOCKS,
        "attribution_failure": window.failure,
        "verdict": verdict,
        "whole_log_pair": whole_log_pair(material),
        "controls": [],
    }

    for control in controls:
        variant, note = derive(material, control, window)
        outcome = the_server_saw_the_kin_move(variant)
        gated = move_window_attribution(
            variant.ledger_events, variant.server_log, username=variant.username
        )
        entry: dict[str, Any] = {
            "control": control,
            "derivation": note,
            "verdict": outcome,
            "credited": _credited(gated),
            "whole_log_pair": whole_log_pair(variant),
        }
        if control in TAIL_CONTROLS:
            # The same bytes attributed without the name gate — the shape that counted
            # a frozen post-death position, or a departed player's last report, as the
            # end of a walk. The line below prints that reading as "ungated".
            ungated = move_window_attribution(variant.ledger_events, variant.server_log)
            without_gate = _credited(ungated)
            entry["credited_without_the_gate"] = without_gate
            lines.append(f"control      : {control} — {note}")
            lines.append(f"             would judge: {PASS_LABEL if outcome is None else outcome}")
            lines.append(f"             credited   : {entry['credited']}")
            lines.append(f"             ungated    : {without_gate}")
        else:
            lines.append(f"control      : {control} — {note}")
            lines.append(f"             would judge: {PASS_LABEL if outcome is None else outcome}")
            lines.append(f"             credited   : {entry['credited']}")
        payload["controls"].append(entry)
    print("\n".join(lines))
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read the authorised movement window of one run.")
    parser.add_argument("--bundle", type=Path, help="a sealed bundle directory")
    parser.add_argument("--data-root", help="the runner data root a live run sits under")
    parser.add_argument("--kin", help="the Kin whose ledger the run wrote")
    parser.add_argument(
        "--run-id", help="the run to attribute, when no run document is handed over"
    )
    parser.add_argument("--username", help="the account the world was asked about")
    parser.add_argument("--server-directory", help="the directory holding the live server.log")
    parser.add_argument("--run-document", help="the JSON document Core printed at the run's end")
    parser.add_argument(
        "--control",
        action="append",
        choices=CONTROLS,
        default=[],
        help="repeatable; each names its own derivation",
    )
    parser.add_argument("--all-controls", action="store_true", help="run every control")
    parser.add_argument(
        "--json", action="store_true", help="also print the reading as one JSON line"
    )
    arguments = parser.parse_args(argv)

    if (arguments.bundle is None) == (arguments.data_root is None):
        parser.error("name exactly one of --bundle (a sealed bundle) or --data-root (a live run)")

    controls = list(CONTROLS) if arguments.all_controls else list(arguments.control)

    try:
        material, source = read_material(arguments)
    except Exception as error:
        location = str(arguments.bundle or arguments.data_root)
        print(f"read_move_window: {location} cannot be read: {error}", file=sys.stderr)
        return 2
    if not material.ledger_readable:
        print(
            "read_move_window: this run's ledger could not be read, so no window can be attributed "
            "to it — said rather than reported as an empty window",
            file=sys.stderr,
        )
        return 2

    payload = report(material, source, controls)
    if arguments.json:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
