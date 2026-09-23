"""Durable, concurrent-safe sequence assignment for sealed case attempts."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability


@dataclass(frozen=True, slots=True)
class Attempt:
    case_id: str
    run_id: str
    sequence: int
    supersedes_run_id: str | None
    status: str


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "evidence.attempt_registry",
        "access",
        ErrorCategory.STORAGE,
        Retryability.OPERATOR_ACTION,
        message,
    )


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def _connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve(strict=True).as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=30, isolation_level=None)


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS attempts (
            case_id TEXT NOT NULL,
            run_id TEXT NOT NULL UNIQUE,
            sequence INTEGER NOT NULL CHECK(sequence > 0),
            supersedes_run_id TEXT,
            status TEXT NOT NULL CHECK(status IN ('PENDING', 'SEALED')),
            PRIMARY KEY(case_id, sequence)
        )"""
    )


def reserve_attempt(path: Path, *, case_id: str, run_id: str) -> Attempt:
    """Persist a pending attempt before bundle bytes are written.

    SQLite's immediate write transaction serializes independent producer
    processes. A crash after this reservation intentionally leaves the latest
    attempt pending, which blocks promotion instead of reviving an older PASS.
    """

    try:
        connection = _connect(path)
    except (OSError, sqlite3.Error) as error:
        raise _reject(f"cannot open attempt registry: {error}") from error
    try:
        connection.execute("BEGIN IMMEDIATE")
        _ensure_schema(connection)
        previous = connection.execute(
            "SELECT run_id, sequence FROM attempts WHERE case_id = ? "
            "ORDER BY sequence DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        sequence = 1 if previous is None else int(previous[1]) + 1
        supersedes = None if previous is None else str(previous[0])
        connection.execute(
            "INSERT INTO attempts(case_id, run_id, sequence, supersedes_run_id, status) "
            "VALUES (?, ?, ?, ?, 'PENDING')",
            (case_id, run_id, sequence, supersedes),
        )
        connection.execute("COMMIT")
        return Attempt(case_id, run_id, sequence, supersedes, "PENDING")
    except sqlite3.Error as error:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        if isinstance(error, sqlite3.IntegrityError) and "attempts.run_id" in str(error):
            raise _reject(f"run id {run_id} already has an evidence attempt") from error
        raise _reject(f"cannot reserve evidence attempt: {error}") from error
    finally:
        connection.close()


def mark_sealed(path: Path, attempt: Attempt) -> None:
    try:
        connection = _connect(path)
    except (OSError, sqlite3.Error) as error:
        raise _reject(f"cannot open attempt registry: {error}") from error
    try:
        connection.execute("BEGIN IMMEDIATE")
        _ensure_schema(connection)
        cursor = connection.execute(
            "UPDATE attempts SET status = 'SEALED' WHERE case_id = ? AND run_id = ? "
            "AND sequence = ? AND status = 'PENDING'",
            (attempt.case_id, attempt.run_id, attempt.sequence),
        )
        if cursor.rowcount != 1:
            raise _reject("reserved evidence attempt is missing or no longer pending")
        connection.execute("COMMIT")
    except (sqlite3.Error, MinekinError) as error:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        if isinstance(error, MinekinError):
            raise
        raise _reject(f"cannot complete evidence attempt: {error}") from error
    finally:
        connection.close()


def read_attempts(path: Path) -> tuple[Attempt, ...]:
    if not path.exists():
        return ()
    try:
        connection = _connect_readonly(path)
    except (OSError, sqlite3.Error) as error:
        raise _reject(f"attempt registry is unreadable: {error}") from error
    try:
        rows = connection.execute(
            "SELECT case_id, run_id, sequence, supersedes_run_id, status "
            "FROM attempts ORDER BY case_id, sequence"
        ).fetchall()
        parsed: list[Attempt] = []
        for row in rows:
            case_id, run_id, sequence, supersedes, status = row
            if (
                not isinstance(case_id, str)
                or not case_id
                or not isinstance(run_id, str)
                or not run_id
                or isinstance(sequence, bool)
                or not isinstance(sequence, int)
                or sequence < 1
                or (supersedes is not None and not isinstance(supersedes, str))
                or status not in {"PENDING", "SEALED"}
            ):
                raise _reject("attempt registry contains a malformed row")
            parsed.append(Attempt(case_id, run_id, sequence, supersedes, str(status)))
        attempts = tuple(parsed)
    except (sqlite3.Error, TypeError, ValueError) as error:
        raise _reject(f"attempt registry is unreadable: {error}") from error
    finally:
        connection.close()

    last_by_case: dict[str, Attempt] = {}
    for attempt in attempts:
        previous = last_by_case.get(attempt.case_id)
        expected_sequence = 1 if previous is None else previous.sequence + 1
        expected_parent = None if previous is None else previous.run_id
        if attempt.sequence != expected_sequence or attempt.supersedes_run_id != expected_parent:
            raise _reject(
                f"attempt sequence or supersession chain is corrupt for {attempt.case_id}"
            )
        last_by_case[attempt.case_id] = attempt
    return attempts
