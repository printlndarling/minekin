"""Reconciling a previous run's leftovers, against the fake store and the real one."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Any

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.sqlite.event_store import SQLiteEventStore, payload_digest
from minekin_core.adapters.sqlite.session_log import reconcile_outbox
from minekin_core.adapters.sqlite.writer import SQLiteWriter
from minekin_core.application.ports.clock import FakeClock
from minekin_core.application.ports.event_store import EventEnvelope, OutboxItem
from minekin_core.application.recovery_service import reconcile_pending_outbox
from minekin_core.cli import session as session_module
from minekin_core.cli.session import database_for, start_session
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.ids import KinId
from session_support import (  # type: ignore[import-not-found]
    PROFILE,
    fabricated,
    kin_root,
    run_root,
    stand_in_for_the_built_workspace,
    stub_supervisor,
)

KIN_ID = KinId("kin-01")


class _Store:
    """Only what reconciliation uses: pending items and closing them."""

    def __init__(self, *items: OutboxItem) -> None:
        self.items = list(items)
        self.closed: list[tuple[str, str]] = []

    async def pending_outbox(self, *, limit: int = 100) -> tuple[OutboxItem, ...]:
        return tuple(item for item in self.items if item.status == "pending")[:limit]

    async def mark_outbox_complete(self, outbox_id: str, completed_at_utc: str) -> None:
        self.closed.append((outbox_id, completed_at_utc))
        self.items = [
            item if item.outbox_id != outbox_id else _completed(item) for item in self.items
        ]


def _completed(item: OutboxItem) -> OutboxItem:
    return OutboxItem(
        outbox_id=item.outbox_id,
        effect_type=item.effect_type,
        idempotency_key=item.idempotency_key,
        payload=item.payload,
        created_at_utc=item.created_at_utc,
        status="completed",
        attempts=item.attempts,
    )


def _item(effect_type: str, *, attempts: int = 0, name: str = "outbox-1") -> OutboxItem:
    return OutboxItem(
        outbox_id=name,
        effect_type=effect_type,
        idempotency_key=f"key-{name}",
        payload=None,
        created_at_utc="2026-01-01T00:00:00Z",
        attempts=attempts,
    )


def test_an_effect_that_may_never_be_replayed_is_closed_with_a_reason() -> None:
    store = _Store(_item("INPUT_LEASE"))

    report = _run(store)

    assert report.invalidated == ("outbox-1",)
    assert report.waiting == ()
    assert [outbox_id for outbox_id, _ in store.closed] == ["outbox-1"]


def test_an_effect_that_waits_on_the_world_is_left_alone() -> None:
    """Closing it here would hide a live client from the check that finds them."""

    store = _Store(_item("START_CLIENT"))

    report = _run(store)

    assert report.waiting == ("outbox-1",)
    assert store.closed == []


def test_a_retryable_effect_stays_pending() -> None:
    store = _Store(_item("RELEASE_ALL"))

    report = _run(store)

    assert report.waiting == ("outbox-1",)
    assert store.closed == []


def test_an_effect_this_build_cannot_read_stops_the_start() -> None:
    store = _Store(_item("SOMETHING_FROM_A_LATER_VERSION"))

    with pytest.raises(MinekinError, match="cannot be reconciled") as raised:
        _run(store)

    assert raised.value.category is ErrorCategory.INTERNAL_INVARIANT


@pytest.mark.parametrize("effect_type", ["INPUT_LEASE", "RELEASE_ALL"])
def test_a_refusal_leaves_the_ledger_exactly_as_it_was(effect_type: str) -> None:
    """Nothing is closed before every decision has been read."""

    store = _Store(
        _item(effect_type, name="first"),
        _item("SOMETHING_FROM_A_LATER_VERSION", name="second"),
    )

    with pytest.raises(MinekinError):
        _run(store)

    assert store.closed == []


def test_an_effect_past_the_retry_cap_stops_the_start() -> None:
    store = _Store(_item("RELEASE_ALL", attempts=3))

    with pytest.raises(MinekinError, match="cannot be reconciled") as raised:
        _run(store)

    assert raised.value.category is ErrorCategory.SESSION
    assert store.closed == []


def _run(store: _Store):
    return asyncio.run(reconcile_pending_outbox(store, clock=FakeClock()))  # type: ignore[arg-type]


def _envelope() -> EventEnvelope:
    return EventEnvelope(
        event_id="event-1",
        event_type="SessionProcessStarted",
        schema_version=1,
        kin_id="kin-01",
        run_id="run-1",
        sequence=1,
        correlation_id="correlation-1",
        monotonic_ns=1,
        observed_at_utc="2026-01-01T00:00:00Z",
        source=EventSource.LAUNCHER,
        trust_class=TrustClass.LAUNCHER,
        payload={},
        payload_hash=payload_digest({}),
    )


def test_reconciliation_against_the_real_ledger(tmp_path: Path) -> None:
    """Same behaviour through the real store, which is where it will actually run."""

    root = kin_root(tmp_path)
    database = database_for(root, KIN_ID)

    async def leave_a_lease_pending() -> None:
        writer = SQLiteWriter(database)
        await writer.start()
        try:
            await SQLiteEventStore(database, writer).append_with_outbox(
                [_envelope()], _item("INPUT_LEASE")
            )
        finally:
            await writer.aclose()

    asyncio.run(leave_a_lease_pending())
    report = reconcile_outbox(database, clock=FakeClock())

    assert report.invalidated == ("outbox-1",)

    async def still_pending() -> tuple[OutboxItem, ...]:
        writer = SQLiteWriter(database)
        await writer.start()
        try:
            return await SQLiteEventStore(database, writer).pending_outbox()
        finally:
            await writer.aclose()

    assert asyncio.run(still_pending()) == ()


def test_a_started_session_reports_what_reconciliation_did(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = kin_root(tmp_path)
    plan, artifact = fabricated()
    stand_in_for_the_built_workspace(monkeypatch)
    def this_plan(_profile: Path, *, workspace_root: Path | None = None) -> dict[str, Any]:
        return plan

    monkeypatch.setattr(session_module, "build_launch_plan", this_plan)
    ArtifactStore(run_root(tmp_path) / "artifact-store").install(
        artifact, io.BytesIO(fabricated()[0]["artifacts"][0]["url"] and b"client jar bytes\n")
    )

    launch = start_session(
        root=root,
        profile=PROFILE,
        java_executable=Path("/usr/bin/java"),
        session_id="session-01",
        generation=1,
        supervisor_factory=stub_supervisor,
    )

    assert launch.recovery.as_dict() == {
        "schema_version": 1,
        "status": "reconciled",
        "invalidated": [],
        "waiting": [],
    }
    assert launch.as_dict()["recovery"] == launch.recovery.as_dict()
