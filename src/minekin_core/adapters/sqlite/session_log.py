"""Recording session lifecycle events in the append-only ledger.

The contract's rule is that an adapter appends success or failure once it has a
result, not before it acts. A launch that leaves no ledger entry is a launch
nothing can be reconciled against afterwards, and a failure that leaves none is
one nobody can explain.

The ledger owns the only write connection, so each record opens the writer,
appends, and closes it. That is a whole thread per event, which is the right
trade for a command that runs twice per launch.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from minekin_core.adapters.sqlite.event_store import SQLiteEventStore, payload_digest
from minekin_core.adapters.sqlite.writer import SQLiteWriter
from minekin_core.application.ports.clock import Clock
from minekin_core.application.ports.event_store import EventEnvelope
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.ids import CorrelationId, EventId

PROCESS_STARTED = "SessionProcessStarted"
PROCESS_FAILED = "SessionProcessFailed"
SESSION_EVENT_SCHEMA_VERSION = 1


class SessionEventLog:
    """Appends the events a launch produces, one writer lifetime per event."""

    def __init__(self, database: Path, *, clock: Clock) -> None:
        self._database = database
        self._clock = clock

    def record_process_started(
        self,
        *,
        kin_id: str,
        run_id: str,
        session_id: str,
        generation: int,
        client_instance_id: str,
        argv_digest: str,
    ) -> EventEnvelope:
        return self._record(
            event_type=PROCESS_STARTED,
            kin_id=kin_id,
            run_id=run_id,
            session_id=session_id,
            generation=generation,
            client_instance_id=client_instance_id,
            payload={
                "session_id": session_id,
                "generation": generation,
                "client_instance_id": client_instance_id,
                "argv_digest": argv_digest,
            },
        )

    def record_process_failed(
        self,
        *,
        kin_id: str,
        run_id: str,
        session_id: str | None,
        generation: int | None,
        error: MinekinError,
    ) -> EventEnvelope:
        return self._record(
            event_type=PROCESS_FAILED,
            kin_id=kin_id,
            run_id=run_id,
            session_id=session_id,
            generation=generation,
            client_instance_id=None,
            payload={
                "category": error.category.value,
                "retryability": error.retryability.value,
                "operation": error.operation,
                # The safe message is already redacted; the raw exception text is
                # never recorded.
                "reason": error.safe_message,
            },
        )

    def _record(
        self,
        *,
        event_type: str,
        kin_id: str,
        run_id: str,
        session_id: str | None,
        generation: int | None,
        client_instance_id: str | None,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        return asyncio.run(
            self._record_async(
                event_type=event_type,
                kin_id=kin_id,
                run_id=run_id,
                session_id=session_id,
                generation=generation,
                client_instance_id=client_instance_id,
                payload=payload,
            )
        )

    async def _record_async(
        self,
        *,
        event_type: str,
        kin_id: str,
        run_id: str,
        session_id: str | None,
        generation: int | None,
        client_instance_id: str | None,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        """Read the run's next sequence and append, within one writer lifetime."""

        writer = SQLiteWriter(self._database)
        await writer.start()
        try:
            store = SQLiteEventStore(self._database, writer)
            existing = await store.read_all()
            envelope = EventEnvelope(
                event_id=EventId.new().value,
                event_type=event_type,
                schema_version=SESSION_EVENT_SCHEMA_VERSION,
                kin_id=kin_id,
                run_id=run_id,
                sequence=1
                + max(
                    (event.sequence for event in existing if event.run_id == run_id),
                    default=0,
                ),
                correlation_id=CorrelationId.new().value,
                monotonic_ns=self._clock.monotonic().nanoseconds,
                observed_at_utc=self._clock.utc_now().isoformat(),
                source=EventSource.LAUNCHER,
                trust_class=TrustClass.LAUNCHER,
                payload=payload,
                payload_hash=payload_digest(payload),
                client_instance_id=client_instance_id,
                session_id=session_id,
                generation=generation,
            )
            await store.append([envelope])
            return envelope
        finally:
            await writer.aclose()
