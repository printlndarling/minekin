"""Naming the ways a joining client failed to arrive, and proving each name is read.

`tools/tally_joiner_arrival.py` reads back statements the launcher stderr already
carried and turns "never arrived" into one named token per run. Two things have to be
true for that to be worth reading. First, the tokens are the run's own: the client's
ending comes from the members of `SessionOutcome`, and nothing here may invent a
diagnosis the build cannot produce. Second, each token is decided by the line it names
— a classifier that returned a fixed string whatever it read would look identical in a
report to one that actually looked. So every shape below is tested twice where it
matters: once with the line present, once with it deleted, and the token has to move.

The lines are transcribed from the real private-volume readouts rather than invented:
the bare `never arrived within 900s` of a run whose window ran out, the two-branch
sentences the wait added so that a walked-out launcher stopped reading as a display
limit, the last-words block, and the client's own conclusion line carrying
`'outcome': 'HANDSHAKE_TIMEOUT'` and four counters.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

ARRIVED = "domain: the world heard Kin2 arrive"
NEVER_PLAYABLE = "domain: Kin2 arrived but never became playable within 420s"
BARE = "domain: Kin2 never arrived within 900s"
LAUNCHER_STILL_RUNNING = (
    "domain: Kin2 never arrived within 420s, and its launcher was still running "
    "when the window closed"
)
LAUNCHER_EXITED = (
    "domain: Kin2 never arrived: its own launcher had already exited, 300s into the 420s window"
)
LAST_WORDS = (
    "domain: the joining client's own last words, from /data/kin/kin2/run/session/abc/"
    "generation-1/logs/stdout.log:"
)
LAST_WORDS_EMPTY = (
    "domain: the joining client's own last words, from /data/kin/kin2/run/session/abc/"
    "generation-1/logs/stdout.log: nothing there"
)
CRASH_REPORT = (
    "domain: it left a crash report: /data/kin/kin2/run/session/abc/generation-1/"
    "crash-reports/crash-2026-09-27_21.36.07-client.txt"
)
NO_SESSION_DIR = (
    "domain: no session directory under /data/kin/kin2/run/session/, "
    "so the joining client left no words to read"
)
DOWNSTREAM = (
    "domain: downstream reading — THE_WORLD_STATUS_IS_NOT_PROBEABLE: nothing answers "
    "127.0.0.1:25570 while the client screen measured (llvmpipe), so this run is evidence "
    "about the world and not about the client environment"
)


def outcome_line(token: str) -> str:
    return (
        "domain: the joining client ended with "
        f"{{'outcome': '{token}', 'connection_state': None, 'snapshots_admitted': 0, "
        "'entities_admitted': 0}}"
    )


def load(name: str) -> Any:
    """One `tools/` module, by the same route `python tools/x.py` would take."""

    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module(f"tools.{name}")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


TALLY: Any = load("tally_joiner_arrival")


def token_of(*lines: str) -> str:
    return TALLY.classify("synthetic-launcher.log", "\n".join(lines)).token


def test_each_way_the_joiner_failed_to_arrive_gets_its_own_name() -> None:
    assert (
        token_of(BARE, LAST_WORDS, CRASH_REPORT, DOWNSTREAM)
        == "CLIENT_DIED_AT_BOOT_WITH_CRASH_REPORT"
    )
    assert token_of(BARE, LAUNCHER_STILL_RUNNING, outcome_line("HANDSHAKE_TIMEOUT")) == (
        "JOINER_ENDED_WITH_HANDSHAKE_TIMEOUT"
    )
    assert token_of(LAUNCHER_EXITED, outcome_line("BRIDGE_LOST")) == "JOINER_ENDED_WITH_BRIDGE_LOST"
    assert (
        token_of(LAUNCHER_EXITED, outcome_line("HANDSHAKE_FAILED"))
        == "JOINER_ENDED_WITH_HANDSHAKE_FAILED"
    )
    assert token_of(NO_SESSION_DIR) == "JOINER_LEFT_NO_SESSION_DIRECTORY"
    assert token_of(BARE, LAST_WORDS_EMPTY) == "JOINER_LEFT_AN_EMPTY_LAST_WORDS_FILE"


def test_the_wait_two_endings_apart_when_the_client_wrote_nothing_down() -> None:
    """The launcher-still-running and launcher-exited branches must not collapse.

    Both leave the client without a conclusion, so the only difference between "the
    window ran out on a client still trying" and "the client had already walked out" is
    this pair of sentences — the pair that exists because a JVM that had exited five
    minutes in was read as a container display limit.
    """

    assert (
        token_of(LAUNCHER_STILL_RUNNING, LAST_WORDS_EMPTY)
        == "LAUNCHER_STILL_TRYING_AT_WINDOW_CLOSE"
    )
    assert (
        token_of(LAUNCHER_EXITED, LAST_WORDS_EMPTY) == "LAUNCHER_EXITED_WITH_NO_JOINER_CONCLUSION"
    )


def test_the_joiners_own_conclusion_outranks_what_the_host_inferred() -> None:
    """The host's downstream reading describes the world, not the client's death.

    Left to itself the host line names a world-side verdict for the same run whose
    client had already written down a handshake timeout, and a report that printed the
    inference while the client sat there naming its own ending would be the misattribution
    this card exists to remove.
    """

    classified = TALLY.classify(
        "synthetic-launcher.log", "\n".join([BARE, DOWNSTREAM, outcome_line("HANDSHAKE_TIMEOUT")])
    )
    assert classified.token == "JOINER_ENDED_WITH_HANDSHAKE_TIMEOUT"
    assert any("outcome" in text for _, text in classified.evidence)
    assert not any("downstream" in text for _, text in classified.evidence)


def test_a_run_that_arrived_is_never_counted_as_a_death() -> None:
    """A successful join also prints its own ending, and that must not leak.

    The client concludes with `CLIENT_EXITED` on a healthy session too, so arrival has
    to be checked before any conclusion line. Deleting the arrival sentence here is the
    control: the same log then reports the boot death it would otherwise hide.
    """

    body = "\n".join([ARRIVED, LAST_WORDS, outcome_line("CLIENT_EXITED")])
    assert TALLY.classify("synthetic-launcher.log", body).token == "ARRIVED"
    without_arrival = "\n".join(body.splitlines()[1:])
    assert TALLY.classify("synthetic-launcher.log", without_arrival).token == (
        "JOINER_ENDED_WITH_CLIENT_EXITED"
    )


def test_arrived_but_stopped_before_a_snapshot_keeps_its_own_name() -> None:
    assert token_of(ARRIVED, NEVER_PLAYABLE) == "ARRIVED_BUT_NEVER_PLAYABLE"


def test_a_crash_report_is_what_separates_a_boot_death_from_a_walkout() -> None:
    """Same ending token, two different fixes, told apart only by the report."""

    with_report = token_of(LAUNCHER_EXITED, outcome_line("CLIENT_EXITED"), CRASH_REPORT)
    without_report = token_of(LAUNCHER_EXITED, outcome_line("CLIENT_EXITED"))
    assert with_report == "CLIENT_DIED_AT_BOOT_WITH_CRASH_REPORT"
    assert without_report == "JOINER_ENDED_WITH_CLIENT_EXITED"


def test_an_outcome_the_build_cannot_produce_is_read_as_no_conclusion() -> None:
    """The closed enum is a closed set, not a prefix to echo into a report.

    A token from a different build or a corrupted line has to fall through to whatever
    the launcher-side sentences say, instead of becoming a new diagnosis nobody declared.
    """

    assert "MYSTERY_ENDING" not in TALLY.JOINER_OUTCOMES
    assert token_of(LAUNCHER_EXITED, outcome_line("MYSTERY_ENDING")) == (
        "LAUNCHER_EXITED_WITH_NO_JOINER_CONCLUSION"
    )


def test_a_log_that_never_mentioned_the_joiner_says_that_instead_of_counting_as_dead() -> None:
    assert token_of("domain: preparing version 1.20.1", "domain: lease handed to Kin1") == (
        "ARRIVAL_NOT_REPORTED_IN_THIS_LOG"
    )


def test_the_token_for_an_unarrived_run_moves_when_its_evidence_line_moves() -> None:
    """Non-vacuity for the whole read: deleting the conclusion line changes the name.

    A classifier that keyed off the bare `never arrived` sentence alone would report the
    same token for both halves of this pair, and the distribution would be a restatement
    of one sentence rather than a reading of what the client said.
    """

    with_conclusion = token_of(BARE, LAST_WORDS, outcome_line("HANDSHAKE_TIMEOUT"))
    without_conclusion = token_of(BARE, LAST_WORDS)
    assert with_conclusion == "JOINER_ENDED_WITH_HANDSHAKE_TIMEOUT"
    assert without_conclusion == "UNARRIVED_WITH_NO_JOINER_WORDS"


def test_the_report_counts_the_distribution_and_can_hide_the_arrived(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arrived = tmp_path / "lan-run-1.log"
    arrived.write_text("\n".join([ARRIVED, outcome_line("CLIENT_EXITED")]), encoding="utf-8")
    dead_at_boot = tmp_path / "lan-run-2.log"
    dead_at_boot.write_text(
        "\n".join([LAUNCHER_EXITED, LAST_WORDS, CRASH_REPORT]), encoding="utf-8"
    )
    timed_out = tmp_path / "lan-run-3.log"
    timed_out.write_text(
        "\n".join([BARE, LAST_WORDS_EMPTY, outcome_line("HANDSHAKE_TIMEOUT")]), encoding="utf-8"
    )

    assert TALLY.main(["--dir", str(tmp_path)]) == 0
    report = capsys.readouterr().out
    assert "JOINER_ENDED_WITH_HANDSHAKE_TIMEOUT" in report
    assert "CLIENT_DIED_AT_BOOT_WITH_CRASH_REPORT" in report
    assert "ARRIVED" in report
    assert report.strip().splitlines()[-1].split()[-1] == "3"

    capsys.readouterr()
    assert TALLY.main(["--dir", str(tmp_path), "--only-unarrived"]) == 0
    filtered = capsys.readouterr().out
    listing = filtered.split("\n\n")[0]
    assert any(
        line.startswith("CLIENT_DIED_AT_BOOT_WITH_CRASH_REPORT") and line.endswith("lan-run-2.log")
        for line in listing.splitlines()
    )
    assert "lan-run-1.log" not in listing

    capsys.readouterr()
    assert TALLY.main(["--log", str(dead_at_boot), "--show-evidence"]) == 0
    shown = capsys.readouterr().out
    assert "line 3: domain: it left a crash report:" in shown


def test_no_logs_given_is_a_named_refusal_rather_than_an_empty_distribution() -> None:
    assert TALLY.main(["--dir", "definitely-not-here"]) == 2
