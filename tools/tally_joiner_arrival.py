#!/usr/bin/env python3
"""Tally how far a joining client got, and name the way it did not arrive.

A run that reports "the joiner never arrived" has already said several different
things, scattered over the launcher's stderr: whether its launcher was still trying
when the window closed or had walked out earlier, whether the client left a crash
report, whether it got far enough to write down its own conclusion, and which of the
named outcomes that conclusion carried. Nothing in the harness read those
statements back, so one bare line covered a display-library crash at boot, a handshake
that ran out of time, and a lost bridge. This tool reads them and reports the
distribution — one named token per run — so a reviewer can see which of them this
environment actually produces instead of being handed a single undifferentiated failure.

It decides nothing about a case. The tokens are the ones the run already emitted: the
client's own `SessionOutcome` (`src/minekin_core/cli/session_runtime.py:60-66`) and the
branches of `join_the_published_world` (`test-orchestrator/runner/domain.sh:1729-1890`).
The only judgement added here is precedence. The world hearing the arrival outranks
everything, because it is the fact the wait was built to look for; then the joining
client's own conclusion outranks any inference the host side made about it, because the
host cannot see inside the client's process. An outcome token outside the endings this
build can produce is read as no conclusion, so the tool cannot invent a diagnosis.

A run whose arrival was heard reports `ARRIVED` and is kept out of the unarrived
distribution; `--only-unarrived` drops those lines. Every token names the evidence line
it came from, so a classification is checkable rather than trusted, and a log that
mentions no arrival at all reports `ARRIVAL_NOT_REPORTED_IN_THIS_LOG` rather than
quietly counting as a death.

Usage:

    uv run python tools/tally_joiner_arrival.py --dir .tmp/m87 --glob '*.log'
    uv run python tools/tally_joiner_arrival.py --log a.log --log b.log --show-evidence
"""

from __future__ import annotations

import argparse
import glob
import re
from pathlib import Path
from typing import Final

#: The endings this build can report for a joining session. Kept as a closed set so a
#: token outside it is read as no conclusion rather than as a new diagnosis.
JOINER_OUTCOMES: Final = (
    "CLIENT_EXITED",
    "BRIDGE_LOST",
    "HANDSHAKE_TIMEOUT",
    "HANDSHAKE_FAILED",
    "STOPPED_ON_REQUEST",
)

_ARRIVED = re.compile(r"the world heard \S+ arrive")
_NEVER_PLAYABLE = re.compile(r"arrived but never became playable within \d+s")
_LAUNCHER_RUNNING = re.compile(r"never arrived within \d+s, and its launcher was still")
_LAUNCHER_EXITED = re.compile(r"never arrived: its own launcher had already exited")
_BARE_NEVER_ARRIVED = re.compile(r"never arrived within \d+s")
_OUTCOME = re.compile(r"'outcome': '(?P<token>[A-Z_]+)'")
_CRASH_REPORT = re.compile(r"it left a crash report: (?P<path>\S+)")
_NO_SESSION_DIR = re.compile(r"no session directory under (?P<path>\S+)")
_LAST_WORDS_EMPTY = re.compile(r"last words, from \S+: nothing there")


class Reading:
    """One launcher log and the token it was classified to."""

    def __init__(self, source: str, token: str, evidence: list[tuple[int, str]]) -> None:
        self.source = source
        self.token = token
        self.evidence = evidence

    def line(self) -> str:
        return f"{self.token:<38} {self.source}"


def _find(pattern: re.Pattern[str], lines: list[str]) -> tuple[int, str] | None:
    for index, text in enumerate(lines, start=1):
        if pattern.search(text):
            return (index, text.strip())
    return None


def _named_outcome(lines: list[str]) -> tuple[int, str, str] | None:
    """The joining client's own ending, only if it names one of the real ones."""

    for index, text in enumerate(lines, start=1):
        match = _OUTCOME.search(text)
        if match is not None and match.group("token") in JOINER_OUTCOMES:
            return (index, text.strip(), match.group("token"))
    return None


def classify(source: str, text: str) -> Reading:
    """Name how far this run's joining client got, from what the run itself said."""

    lines = text.splitlines()
    evidence: list[tuple[int, str]] = []

    heard = _find(_ARRIVED, lines)
    not_playable = _find(_NEVER_PLAYABLE, lines)
    if heard is not None:
        if not_playable is not None:
            token, anchor = "ARRIVED_BUT_NEVER_PLAYABLE", not_playable
        else:
            token, anchor = "ARRIVED", heard
        return Reading(source, token, [anchor])

    outcome = _named_outcome(lines)
    crash = _find(_CRASH_REPORT, lines)
    launcher_running = _find(_LAUNCHER_RUNNING, lines)
    launcher_exited = _find(_LAUNCHER_EXITED, lines)
    no_session = _find(_NO_SESSION_DIR, lines)
    silent_words = _find(_LAST_WORDS_EMPTY, lines)
    bare = _find(_BARE_NEVER_ARRIVED, lines)

    if outcome is not None:
        index, text_line, token_name = outcome
        # A JVM that walked out on its own while leaving a crash report died at boot,
        # which is a different fix than a session that gave up on the protocol; the
        # report is what tells the two apart, so it is read before the bare token.
        if token_name == "CLIENT_EXITED" and crash is not None:
            token = "CLIENT_DIED_AT_BOOT_WITH_CRASH_REPORT"
            evidence.append(crash)
        else:
            token = f"JOINER_ENDED_WITH_{token_name}"
        evidence.append((index, text_line))
        return Reading(source, token, evidence)
    if crash is not None:
        return Reading(source, "CLIENT_DIED_AT_BOOT_WITH_CRASH_REPORT", [crash])
    if launcher_running is not None:
        return Reading(source, "LAUNCHER_STILL_TRYING_AT_WINDOW_CLOSE", [launcher_running])
    if launcher_exited is not None:
        return Reading(source, "LAUNCHER_EXITED_WITH_NO_JOINER_CONCLUSION", [launcher_exited])
    if no_session is not None:
        return Reading(source, "JOINER_LEFT_NO_SESSION_DIRECTORY", [no_session])
    if silent_words is not None:
        return Reading(source, "JOINER_LEFT_AN_EMPTY_LAST_WORDS_FILE", [silent_words])
    if bare is not None:
        return Reading(source, "UNARRIVED_WITH_NO_JOINER_WORDS", [bare])
    return Reading(source, "ARRIVAL_NOT_REPORTED_IN_THIS_LOG", [])


def collect_logs(logs: list[str], directories: list[str], glob_pattern: str) -> list[Path]:
    paths = [Path(item) for item in logs]
    for directory in directories:
        paths.extend(Path(item) for item in sorted(glob.glob(str(Path(directory) / glob_pattern))))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Name the joiner-arrival outcome of each run log.")
    parser.add_argument("--log", action="append", default=[], help="one launcher log file")
    parser.add_argument("--dir", action="append", default=[], help="directory to read")
    parser.add_argument("--glob", default="*.log", help="pattern used with --dir")
    parser.add_argument("--only-unarrived", action="store_true", help="hide runs that arrived")
    parser.add_argument("--show-evidence", action="store_true", help="print the matched lines")
    args = parser.parse_args(argv)

    paths = collect_logs(args.log, args.dir, args.glob)
    if not paths:
        print("no logs given; use --log or --dir")
        return 2

    readings: list[Reading] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            print(f"UNREADABLE_LOG {path}: {error}")
            continue
        readings.append(classify(str(path), text))

    if not readings:
        print("no readable log; nothing counted")
        return 2

    shown = [r for r in readings if not (args.only_unarrived and r.token == "ARRIVED")]
    for reading in sorted(shown, key=lambda item: (item.token, item.source)):
        print(reading.line())
        if args.show_evidence:
            for number, evidence in reading.evidence:
                print(f"    line {number}: {evidence[:160]}")

    counts: dict[str, int] = {}
    for reading in readings:
        counts[reading.token] = counts.get(reading.token, 0) + 1

    print("")
    print(f"{'token':<38} count  runs")
    for token, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        sources = " ".join(Path(r.source).name for r in readings if r.token == token)
        print(f"{token:<38} {count:>5}  {sources}")
    print(f"{'TOTAL':<38} {len(readings):>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
