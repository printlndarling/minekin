"""The two documents a stop is made of: the ask, and the answer to it.

`session stop` asks a live session to release the client's inputs and waits for the
receipt before it terminates, so the pair has to survive being read by a process
that did not write it — from another process, at another moment, with no shared
memory. These tests are about that survival: what a reader may conclude from a file,
and what it must refuse to conclude.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from minekin_core.adapters.launcher.stop_request import (
    REQUESTS_DIRECTORY,
    StopRelease,
    StopRequest,
    read_receipt,
    read_request,
    write_receipt,
    write_request,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError

SESSION_ID = "session-01"
GENERATION = 1
PID = 4242


def ask(runs: Path, *, request_id: str = "ask-1", pid: int = PID) -> StopRequest:
    return write_request(
        runs,
        session_id=SESSION_ID,
        generation=GENERATION,
        pid=pid,
        request_id=request_id,
        requested_at="2026-09-25T12:00:00Z",
    )


def receipt_path(runs: Path, *, pid: int = PID) -> Path:
    return (
        runs / REQUESTS_DIRECTORY / f"{SESSION_ID}-generation-{GENERATION}-pid-{pid}.receipt.json"
    )


def test_an_ask_survives_the_trip_to_the_session_that_answers_it(tmp_path: Path) -> None:
    runs = tmp_path / "run"
    request = ask(runs)

    assert read_request(runs, session_id=SESSION_ID, generation=GENERATION, pid=PID) == request

    answer = write_receipt(
        runs,
        request=request,
        released_at="2026-09-25T12:00:01Z",
        release=StopRelease.SENT,
    )

    assert read_receipt(runs, request=request) == answer


def test_an_ask_worthless_to_nobody_but_its_client(tmp_path: Path) -> None:
    """The pid is part of the address, and a later client is a different one.

    A Kin can be stopped and started again under the same session and generation,
    and the request the previous stop left behind must not read as an instruction to
    the client that came after it. Without the pid in the address, it would.
    """

    runs = tmp_path / "run"
    ask(runs, pid=PID)

    assert read_request(runs, session_id=SESSION_ID, generation=GENERATION, pid=PID) is not None
    assert read_request(runs, session_id=SESSION_ID, generation=GENERATION, pid=PID + 1) is None


def test_an_answer_to_a_different_ask_is_no_answer(tmp_path: Path) -> None:
    """The stopper may act only on the receipt that names its own request.

    Two asks for the same client are possible — one that was never answered and one
    the operator made after it — and an old answer arriving would let the stopper
    believe the Bridge had been told when the only thing it read was a stale file.
    """

    runs = tmp_path / "run"
    first = ask(runs, request_id="ask-1")
    write_receipt(runs, request=first, released_at="2026-09-25T12:00:01Z", release=StopRelease.SENT)

    second = ask(runs, request_id="ask-2")

    assert read_receipt(runs, request=second) is None


def test_an_answer_this_build_cannot_read_is_not_claimed_as_one(tmp_path: Path) -> None:
    """A release value from a newer build is not a licence to terminate.

    The stopper's fallback is to stop anyway and say nobody answered; reading a
    value it does not know as "close enough" would turn an unknown into a
    confirmation, which is the one thing this document exists to avoid.
    """

    runs = tmp_path / "run"
    request = ask(runs)
    receipt_path(runs).parent.mkdir(parents=True, exist_ok=True)
    receipt_path(runs).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "session_id": SESSION_ID,
                "generation": GENERATION,
                "pid": PID,
                "request_id": request.request_id,
                "released_at": "2026-09-25T12:00:01Z",
                "release": "PROBABLY_RELEASED",
            }
        ),
        encoding="utf-8",
    )

    assert read_receipt(runs, request=request) is None


def test_a_file_that_is_not_a_document_is_no_message(tmp_path: Path) -> None:
    """A half-arranged file is read as "nothing here yet", never as an instruction."""

    runs = tmp_path / "run"
    request = ask(runs)
    path = (
        runs / REQUESTS_DIRECTORY / (f"{SESSION_ID}-generation-{GENERATION}-pid-{PID}.request.json")
    )
    path.write_text('{"schema_version": 1, "session', encoding="utf-8")

    assert read_request(runs, session_id=SESSION_ID, generation=GENERATION, pid=PID) is None
    assert read_receipt(runs, request=request) is None


def test_an_ask_names_the_client_it_addresses_and_nothing_impossible(tmp_path: Path) -> None:
    """Every part of the address is checked before a file exists.

    A request with no session, no id, generation 0 or pid 0 would be an ask no
    client can recognise as its own — and the stopper would then wait for an answer
    to a message nobody could receive.
    """

    runs = tmp_path / "run"

    for kwargs in (
        {"session_id": "", "generation": GENERATION, "pid": PID, "request_id": "ask-1"},
        {"session_id": SESSION_ID, "generation": GENERATION, "pid": PID, "request_id": ""},
        {"session_id": SESSION_ID, "generation": 0, "pid": PID, "request_id": "ask-1"},
        {"session_id": SESSION_ID, "generation": GENERATION, "pid": 0, "request_id": "ask-1"},
    ):
        arguments = cast(dict[str, Any], kwargs)
        with pytest.raises(MinekinError) as caught:
            write_request(runs, requested_at="2026-09-25T12:00:00Z", **arguments)
        assert caught.value.category is ErrorCategory.PROCESS

    assert not (runs / REQUESTS_DIRECTORY).exists()


def test_an_answered_ask_stays_where_it_was(tmp_path: Path) -> None:
    """Neither document is cleared: the pair is the trace that the operator asked.

    A run's records are appended rather than erased, and here the rule earns its
    keep twice over — a later reader can see that this client was stopped on
    purpose, and a stopper can tell an answered ask from one nobody saw.
    """

    runs = tmp_path / "run"
    request = ask(runs)
    write_receipt(
        runs, request=request, released_at="2026-09-25T12:00:01Z", release=StopRelease.SENT
    )

    assert read_request(runs, session_id=SESSION_ID, generation=GENERATION, pid=PID) == request
    assert receipt_path(runs).is_file()


def test_a_session_that_holds_nothing_answers_that_instead_of_sending(tmp_path: Path) -> None:
    """`NOTHING_HELD` is a receipt, not an absence of one.

    The stopper cannot tell "this session never had a lease" from "this session is
    not listening" by looking at the client, and the two call for different words in
    its report: one is an answer, the other is a wait that ran out.
    """

    runs = tmp_path / "run"
    request = ask(runs)

    answer = write_receipt(
        runs,
        request=request,
        released_at="2026-09-25T12:00:01Z",
        release=StopRelease.NOTHING_HELD,
    )

    assert answer.release is StopRelease.NOTHING_HELD
    assert read_receipt(runs, request=request) == answer
