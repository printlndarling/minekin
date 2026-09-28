"""Shared fixtures for the Gateway's reads: a Kin root, and the rows a run leaves in it.

`tests/conftest.py` puts this directory on the path, so both the projection tests and the
HTTP tests build the same scenario rather than agreeing about it in two places.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path

from minekin_core.adapters.launcher.orphans import Liveness, write_marker
from minekin_core.adapters.launcher.process import argument_digest
from minekin_core.adapters.launcher.supervisor import ProcessIdentity
from minekin_core.adapters.sqlite.session_log import (
    AUTH_POLICY_FROZEN,
    HELLO_ACCEPTED,
    INPUT_LEASE_GRANTED,
    JOIN_OBSERVED,
    PLAYABLE_ESTABLISHED,
    PROCESS_STARTED,
    SessionEventLog,
)
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.init import initialise_identity
from minekin_core.cli.session import database_for, session_overlay_path
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.ids import KinId

KIN_ID = KinId("kin-01")
RUN_ID = "0366d190e32f41baac1cf24c2dd6e6b6"
SESSION_ID = "e14d02e5f33e48ecb3b23bc6f17418d9"
PID = 4242
PROFILE_ID = "srv-profile-00000000000000000000"
#: A revision byte-for-byte in the shape Core requires: this literal is one a live LAN ledger
#: actually froze for `p0-lan-host-fixture`.
PROFILE_REVISION = "9874a7e17928773b468a175a62e254e270ecbb83ad0363776b3089bbec83399b"

OURS_ARGV = ("java", "-jar", "ours.jar")
#: A value that would be a credential if it ever reached a panel. Fixtures below carry one
#: on purpose, so the redaction assertions have something real to refuse.
CANARY = "2551900000000000000"
#: The rows a successful, driving join leaves, in the order a run writes them.
JOINED_RUN_ROWS = 6


def alive(_pid: int) -> Liveness:
    return Liveness.ALIVE


def gone(_pid: int) -> Liveness:
    return Liveness.GONE


def our_command_line(_pid: int) -> bytes | None:
    return b"\0".join(argument.encode() for argument in OURS_ARGV) + b"\0"


def command_line_with_credential(_pid: int) -> bytes | None:
    joined = (
        b"java",
        b"-jar",
        b"ours.jar",
        b"--xuid",
        CANARY.encode(),
        b"--clientId",
        CANARY.encode(),
    )
    return b"\0".join(joined) + b"\0"


def policy_payload() -> dict[str, object]:
    """What `AuthPolicy.as_event_payload()` writes, member for member.

    `auth_mode` is the dataclass default and the revision is the 64-hex form
    `AuthPolicy.__post_init__` requires, so a fixture cannot make a projection pass on a shape
    Core never emits.
    """

    return {
        "auth_mode": "offline",
        "online_adapter_enabled": False,
        "server_profile_id": PROFILE_ID,
        "server_profile_revision": PROFILE_REVISION,
    }


def log_for(root: Path) -> SessionEventLog:
    return SessionEventLog(database_for(root, KIN_ID), clock=FakeClock())


def seed_kin(root: Path, *, with_marker: bool = True) -> Path:
    """A Kin the way `minekin init` leaves one, plus the session marker a launch writes."""

    if not (root / "kin" / str(KIN_ID) / "kin.sqlite3").exists():
        initialise_identity(KIN_ID, root=root, username="Kin", clock=FakeClock())
    if with_marker:
        overlay = session_overlay_path(root / "kin" / str(KIN_ID) / "run", SESSION_ID, 1)
        overlay.mkdir(parents=True, exist_ok=True)
        write_marker(
            overlay,
            identity=ProcessIdentity(
                pid=PID, started_at="2026-01-01T00:00:00Z", argv_digest=argument_digest(OURS_ARGV)
            ),
            session_id=SESSION_ID,
            generation=1,
        )
    return root


def record(root: Path, event_type: str, payload: Mapping[str, object]) -> None:
    """Append one session row the way a supervised session does: through the log, not the table."""

    from_bridge = event_type == HELLO_ACCEPTED
    asyncio.run(
        log_for(root).record_session_event(
            event_type=event_type,
            kin_id=str(KIN_ID),
            run_id=RUN_ID,
            session_id=SESSION_ID,
            generation=1,
            payload=dict(payload),
            source=EventSource.BRIDGE if from_bridge else EventSource.CORE,
            trust_class=TrustClass.BRIDGE_FILTERED if from_bridge else TrustClass.CORE,
        )
    )


def launch(root: Path) -> None:
    log_for(root).record_process_started(
        kin_id=str(KIN_ID),
        run_id=RUN_ID,
        session_id=SESSION_ID,
        generation=1,
        client_instance_id="client-01",
        argv_digest="a" * 64,
    )


def joined_run(root: Path) -> None:
    """Policy frozen, client launched, hello accepted, world joined, playable, input granted."""

    seed_kin(root)
    record(root, AUTH_POLICY_FROZEN, policy_payload())
    launch(root)
    record(root, HELLO_ACCEPTED, {})
    record(root, JOIN_OBSERVED, {"phase": "CONNECTION_PHASE_JOIN_SEEN"})
    record(root, PLAYABLE_ESTABLISHED, {"phase": "CONNECTION_PHASE_PLAYABLE"})
    record(root, INPUT_LEASE_GRANTED, {"capability": "move.forward", "priority": "PLAYER"})


def started_at(root: Path) -> str:
    """What the ledger says the launch moment was, straight from its process row."""

    from gateway.readmodel import read_ledger

    for row in read_ledger(database_for(root, KIN_ID)):
        if row.event_type == PROCESS_STARTED:
            return row.observed_at_utc
    raise AssertionError("no SessionProcessStarted row was recorded")
