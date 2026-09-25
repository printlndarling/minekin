"""`session stop` asks before it terminates, and reports what came back.

The stopper and the session are separate processes whose only shared thing is the
run's own directory, so these tests stand in for the session with a thread that
watches for the ask. What they pin down is the order and the honesty of the report:
the ask goes out while the client is still alive, the wait is bounded, and a stop
that nobody answered says nobody answered it.

The client in these tests is a marker plus two injected answers — "is this pid
there", "what was it started with" — so nothing here touches a real process. The
rules about which pid may be signalled are `test_orphans.py`'s and are unchanged.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from minekin_core.adapters.launcher.orphans import (
    Liveness,
    write_marker,
)
from minekin_core.adapters.launcher.process import argument_digest
from minekin_core.adapters.launcher.stop_request import (
    REQUESTS_DIRECTORY,
    StopRelease,
    read_receipt,
    read_request,
    write_receipt,
)
from minekin_core.adapters.launcher.supervisor import ProcessIdentity
from minekin_core.cli.session import session_overlay_path, stop_session
from session_support import kin_root, run_root  # type: ignore[import-not-found]

SESSION_ID = "session-01"
GENERATION = 1
PID = 4242
OURS_ARGV = ("java", "-jar", "ours.jar")
OURS_DIGEST = argument_digest(OURS_ARGV)


def probe(answer: Liveness) -> Callable[[int], Liveness]:
    def answer_with(_pid: int) -> Liveness:
        return answer

    return answer_with


def reads_our_command_line(_pid: int) -> bytes | None:
    return b"\0".join(argument.encode() for argument in OURS_ARGV) + b"\0"


def reads_a_foreign_command_line(_pid: int) -> bytes | None:
    return b"/usr/bin/something-else\0--totally\0"


def marked(tmp_path: Path) -> Path:
    """Record a client for this Kin's run, as a real launch would have."""

    root = run_root(kin_root(tmp_path))
    overlay = session_overlay_path(root, SESSION_ID, GENERATION)
    overlay.mkdir(parents=True)
    return write_marker(
        overlay,
        identity=ProcessIdentity(
            pid=PID, started_at="2026-09-25T12:00:00Z", argv_digest=OURS_DIGEST
        ),
        session_id=SESSION_ID,
        generation=GENERATION,
    )


class Recorder:
    """The pids the stop was allowed to signal, in the order it signalled them."""

    def __init__(self) -> None:
        self.pids: list[int] = []

    def __call__(self, pid: int) -> None:
        self.pids.append(pid)


class AnsweringSession:
    """Stands in for the managed session running in the other process.

    It watches for the ask and answers it the way the product answers — by writing a
    receipt that names the request — and it records, at the moment it answers, which
    pids the stopper had already terminated. That single reading is the card's claim:
    a release the Bridge could not have received is worth nothing, so the answer must
    come before the kill.

    `answer_delay_s` is what makes that reading mean something. A session that
    answers the instant the ask lands would let a stopper that never waits pass its
    own ordering test by timing luck; one that takes a moment is answered only by a
    stopper that actually waited for it.
    """

    def __init__(self, runs: Path, terminate: Recorder, *, answer_delay_s: float = 0.0) -> None:
        self._runs = runs
        self._terminate = terminate
        self._delay = answer_delay_s
        self._stop = threading.Event()
        #: What `terminate` had already been called with, when each ask was answered.
        self.terminated_when_answered: list[list[int]] = []
        self._thread = threading.Thread(target=self._watch, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def finish(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _watch(self) -> None:
        while not self._stop.is_set():
            request = read_request(
                self._runs, session_id=SESSION_ID, generation=GENERATION, pid=PID
            )
            if request is not None and read_receipt(self._runs, request=request) is None:
                if self._stop.wait(self._delay):
                    return
                self.terminated_when_answered.append(list(self._terminate.pids))
                write_receipt(
                    self._runs,
                    request=request,
                    released_at="2026-09-25T12:00:01Z",
                    release=StopRelease.SENT,
                )
                return
            time.sleep(0.005)


def test_the_stop_asks_the_live_client_and_waits_for_its_answer(tmp_path: Path) -> None:
    """The order the whole card exists for, read as a fact rather than an intent.

    `released` would be non-empty even if the stopper terminated first and asked
    afterwards — the ask would simply arrive too late for the Bridge. The assertion
    that catches that is the one made at the moment of answering: no pid had been
    signalled yet, for a session that only answers a third of a second after being
    asked.
    """

    marked(tmp_path)
    runs = run_root(tmp_path)
    terminate = Recorder()
    session = AnsweringSession(runs, terminate, answer_delay_s=0.3)
    session.start()
    try:
        report = stop_session(
            tmp_path,
            probe=probe(Liveness.ALIVE),
            read_cmdline=reads_our_command_line,
            terminate=terminate,
        )
    finally:
        session.finish()

    assert report.release.asked == (PID,)
    assert report.release.released == (PID,)
    assert report.release.unconfirmed == ()
    assert terminate.pids == [PID]
    assert session.terminated_when_answered == [[]]
    assert report.as_dict()["release"] == {
        "asked": [PID],
        "released": [PID],
        "nothing_held": [],
        "unconfirmed": [],
    }


def test_a_stop_that_gets_no_answer_still_stops_and_says_nobody_answered(
    tmp_path: Path,
) -> None:
    """The wait is bounded, and an unanswered ask is reported rather than assumed.

    A client whose session is not listening — wedged, or already on its way out —
    must not turn `session stop` into a command that hangs. Stopping it is still the
    operator's decision honoured, and the only thing that changes is what the report
    is allowed to claim.
    """

    marked(tmp_path)
    runs = run_root(tmp_path)
    terminate = Recorder()

    report = stop_session(
        tmp_path,
        probe=probe(Liveness.ALIVE),
        read_cmdline=reads_our_command_line,
        terminate=terminate,
        release_timeout_s=0.05,
    )

    assert terminate.pids == [PID]
    assert report.release.asked == (PID,)
    assert report.release.released == ()
    assert report.release.unconfirmed == (PID,)
    # The ask itself survives as the trace that the operator asked, in order.
    assert (
        runs / REQUESTS_DIRECTORY / f"{SESSION_ID}-generation-{GENERATION}-pid-{PID}.request.json"
    ).is_file()
    assert report.as_dict()["status"] == "stopped"


def test_a_client_that_is_not_ours_is_never_asked(tmp_path: Path) -> None:
    """The identity rule reaches the ask, not only the signal.

    A live pid whose command line is not the recorded one has been reused by
    somebody else. Asking *its* session to release inputs would be an instruction to
    a stranger, and an answer to it would be a lie about this Kin's client.
    """

    marked(tmp_path)
    runs = run_root(tmp_path)
    terminate = Recorder()

    report = stop_session(
        tmp_path,
        probe=probe(Liveness.ALIVE),
        read_cmdline=reads_a_foreign_command_line,
        terminate=terminate,
    )

    assert report.release.asked == ()
    assert report.outcome.left_alone == (PID,)
    assert terminate.pids == []
    assert not (runs / REQUESTS_DIRECTORY).exists()


def test_a_kin_with_nothing_running_is_stopped_without_a_wait(tmp_path: Path) -> None:
    """Idempotence is preserved: no live client, no ask, no waiting, no directory.

    The deadline only means something when there is somebody to wait for. A Kin with
    nothing recorded is already stopped, and the release block says so by being empty
    rather than by being missing.
    """

    kin_root(tmp_path)
    runs = run_root(tmp_path)
    terminate = Recorder()

    report = stop_session(tmp_path, probe=probe(Liveness.GONE), terminate=terminate)

    assert report.release.asked == ()
    assert report.release.unconfirmed == ()
    assert terminate.pids == []
    assert report.as_dict()["status"] == "stopped"
    assert not (runs / REQUESTS_DIRECTORY).exists()
