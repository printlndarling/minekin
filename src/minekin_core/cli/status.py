"""Reporting what the managed session is doing, without changing anything.

The frozen command says "read the current projection". No projector writes one
yet, so reporting only the projection table would report nothing; what this
reports instead is the same picture derived from what does exist — the session
overlays, the recorded client processes and the ledger. When the projector
arrives this should read it.

It is read-only in the strict sense: it opens the database query-only and never
starts a writer, so asking what is happening cannot change what is happening.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from minekin_core.adapters.launcher.orphans import (
    Liveness,
    default_cmdline,
    default_probe,
    session_claims,
)
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.cli.init import run_root
from minekin_core.cli.session import database_for, select_kin
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.ids import KinId


class ObservedState(StrEnum):
    """What the host can see, which is not the session state machine's own state."""

    IDLE = "idle"
    RUNNING = "running"
    # A recorded client whose liveness the host cannot establish.
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class ClientSummary:
    session_id: str
    generation: int
    overlay: str
    pid: int
    liveness: Liveness

    def as_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "generation": self.generation,
            "overlay": self.overlay,
            "pid": self.pid,
            "liveness": self.liveness.value,
        }


@dataclass(frozen=True, slots=True)
class LedgerSummary:
    events_recorded: int
    last_event_type: str | None
    last_observed_at_utc: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "events_recorded": self.events_recorded,
            "last_event_type": self.last_event_type,
            "last_observed_at_utc": self.last_observed_at_utc,
        }


@dataclass(frozen=True, slots=True)
class StatusReport:
    kin_id: str
    state: ObservedState
    clients: tuple[ClientSummary, ...]
    ledger: LedgerSummary

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "session status",
            "status": "ok",
            "kin_id": self.kin_id,
            "state": self.state.value,
            "clients": [client.as_dict() for client in self.clients],
            "ledger": self.ledger.as_dict(),
        }


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "cli.status", "read", ErrorCategory.STORAGE, Retryability.OPERATOR_ACTION, message
    )


def _ledger_summary(database: Path) -> LedgerSummary:
    connection = connect_reader(database)
    try:
        return _read_ledger(connection)
    finally:
        connection.close()


def _read_ledger(connection: sqlite3.Connection) -> LedgerSummary:
    events = int(connection.execute("SELECT count(*) FROM event").fetchone()[0])
    row = connection.execute(
        "SELECT event_type, observed_at_utc FROM event ORDER BY position DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return LedgerSummary(events_recorded=0, last_event_type=None, last_observed_at_utc=None)
    return LedgerSummary(
        events_recorded=events,
        last_event_type=str(row["event_type"]),
        last_observed_at_utc=str(row["observed_at_utc"]),
    )


def observe_state(clients: tuple[ClientSummary, ...]) -> ObservedState:
    """A live client means running; an unanswerable one is unresolved, not idle."""

    if any(client.liveness is Liveness.ALIVE for client in clients):
        return ObservedState.RUNNING
    # A live PID whose command line proves it belongs to something else is GONE,
    # so it is neither running nor unresolved; it is simply not a client of ours.
    if any(client.liveness is Liveness.UNKNOWN for client in clients):
        return ObservedState.UNRESOLVED
    return ObservedState.IDLE


def read_status(
    root: Path,
    *,
    kin_selector: str | None = None,
    probe: Callable[[int], Liveness] = default_probe,
    cmdline: Callable[[int], bytes | None] = default_cmdline,
) -> StatusReport:
    """Read the session picture for one Kin, changing nothing."""

    kin_id: KinId = select_kin(root, kin_selector)
    runs = run_root(root, kin_id)
    database = database_for(root, kin_id)
    if not database.is_file():
        raise _reject(f"{database} is missing; run `minekin init` first")

    clients = tuple(
        ClientSummary(
            session_id=claim.session_id,
            generation=claim.generation,
            overlay=claim.overlay,
            pid=claim.identity.pid,
            liveness=claim.liveness,
        )
        for claim in session_claims(runs, probe=probe, cmdline=cmdline)
    )
    return StatusReport(
        kin_id=str(kin_id),
        state=observe_state(clients),
        clients=clients,
        ledger=_ledger_summary(database),
    )
