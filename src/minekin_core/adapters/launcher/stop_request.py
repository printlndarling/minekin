"""Asking a live session to let go of the client's inputs before it is stopped.

`session stop` ends a run, but the only process that can put a `ReleaseAllInputs`
on the Bridge's channel is the session holding that channel — and the Bridge lives
inside the client this command is about to terminate. So the stopper leaves a
request where the running session will look, and waits for the receipt that
session writes once the Bridge has taken the command. The waiting is the point: a
release sent after the client is gone is a release nobody receives, which is what
two sealed 1.20.1 runs recorded as `input_release_failed`.

Neither document claims the client stopped pressing a key. The Bridge's own log is
that claim. These two say only that Core asked in the one order that can reach a
live Bridge, and whether the send came back.

Both are addressed to a session, a generation and the pid that run started, because
a stop belongs to the client that is live now: it must never read as an instruction
to a later client that happens to reuse the session and the generation.
Nothing clears either file: an answered request is the trace that the operator
asked, in keeping with the rule that a run's records are appended rather than
erased.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, cast

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

REQUESTS_DIRECTORY: Final = "stop-requests"
_SCHEMA_VERSION: Final = 1


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.stop_request",
        "stop",
        ErrorCategory.PROCESS,
        Retryability.OPERATOR_ACTION,
        message,
    )


class StopRelease(StrEnum):
    """What the session did with the request it answered."""

    #: Core's `ReleaseAllInputs(EXPLICIT)` went out over a live channel.
    SENT = "SENT"
    #: This session was never granted a lease, so there was nothing to take back.
    #: Answered rather than left waiting, because the stopper still has to know the
    #: session saw the request and is not going to release anything.
    NOTHING_HELD = "NOTHING_HELD"


@dataclass(frozen=True, slots=True)
class StopRequest:
    """The operator's ask, addressed to one session's one live client."""

    session_id: str
    generation: int
    pid: int
    request_id: str
    requested_at: str


@dataclass(frozen=True, slots=True)
class StopReceipt:
    """The session's answer, naming the request it answers."""

    request_id: str
    released_at: str
    release: StopRelease


def requests_directory(run_root: Path) -> Path:
    return run_root / REQUESTS_DIRECTORY


def _stem(session_id: str, generation: int, pid: int) -> str:
    return f"{session_id}-generation-{generation}-pid-{pid}"


def _request_path(run_root: Path, session_id: str, generation: int, pid: int) -> Path:
    return requests_directory(run_root) / f"{_stem(session_id, generation, pid)}.request.json"


def _receipt_path(run_root: Path, session_id: str, generation: int, pid: int) -> Path:
    return requests_directory(run_root) / f"{_stem(session_id, generation, pid)}.receipt.json"


def _write(path: Path, document: dict[str, object]) -> None:
    """Put one document where a polling process will read it whole or not at all.

    A reader that caught a half-written file would answer a request it never saw,
    so the bytes land in a sibling and `os.replace` moves them into place.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.writing")
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _read(path: Path) -> dict[str, object] | None:
    try:
        document = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        # Nothing there yet, or a file another process is still arranging: both
        # mean "no message for this session", and neither is worth failing a
        # stop over — the stopper's own fallback is to terminate and say so.
        return None
    if not isinstance(document, dict):
        return None
    return cast(dict[str, object], document)


def write_request(
    run_root: Path,
    *,
    session_id: str,
    generation: int,
    pid: int,
    request_id: str,
    requested_at: str,
) -> StopRequest:
    if not session_id or not request_id:
        raise _reject("a stop request needs the session it addresses and its own id")
    if generation < 1:
        raise _reject(f"a stop request cannot address generation {generation}")
    if pid < 1:
        raise _reject(f"a stop request cannot address pid {pid}")
    request = StopRequest(
        session_id=session_id,
        generation=generation,
        pid=pid,
        request_id=request_id,
        requested_at=requested_at,
    )
    _write(
        _request_path(run_root, session_id, generation, pid),
        {
            "schema_version": _SCHEMA_VERSION,
            "session_id": session_id,
            "generation": generation,
            "pid": pid,
            "request_id": request_id,
            "requested_at": requested_at,
        },
    )
    return request


def read_request(
    run_root: Path, *, session_id: str, generation: int, pid: int
) -> StopRequest | None:
    record = _read(_request_path(run_root, session_id, generation, pid))
    if record is None or record.get("schema_version") != _SCHEMA_VERSION:
        return None
    if record.get("session_id") != session_id or record.get("generation") != generation:
        return None
    if record.get("pid") != pid:
        return None
    request_id = record.get("request_id")
    requested_at = record.get("requested_at")
    if not isinstance(request_id, str) or not request_id:
        return None
    if not isinstance(requested_at, str):
        return None
    return StopRequest(
        session_id=session_id,
        generation=generation,
        pid=pid,
        request_id=request_id,
        requested_at=requested_at,
    )


def write_receipt(
    run_root: Path,
    *,
    request: StopRequest,
    released_at: str,
    release: StopRelease,
) -> StopReceipt:
    """Answer one request by its id, so a stopper never mistakes an old answer."""

    receipt = StopReceipt(request_id=request.request_id, released_at=released_at, release=release)
    _write(
        _receipt_path(run_root, request.session_id, request.generation, request.pid),
        {
            "schema_version": _SCHEMA_VERSION,
            "session_id": request.session_id,
            "generation": request.generation,
            "pid": request.pid,
            "request_id": receipt.request_id,
            "released_at": receipt.released_at,
            "release": receipt.release.value,
        },
    )
    return receipt


def read_receipt(run_root: Path, *, request: StopRequest) -> StopReceipt | None:
    record = _read(_receipt_path(run_root, request.session_id, request.generation, request.pid))
    if record is None or record.get("schema_version") != _SCHEMA_VERSION:
        return None
    request_id = record.get("request_id")
    released_at = record.get("released_at")
    release = record.get("release")
    if not isinstance(request_id, str) or not isinstance(released_at, str):
        return None
    if request_id != request.request_id:
        # An answer to a different ask: this client was asked again, and the
        # answer the stopper may act on is the one naming its own request.
        return None
    try:
        answered = StopRelease(str(release))
    except ValueError:
        # An answer this build does not know is not an answer it may claim.
        return None
    return StopReceipt(request_id=request_id, released_at=released_at, release=answered)
