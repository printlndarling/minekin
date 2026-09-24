"""Recording session lifecycle events in the append-only ledger.

The contract's rule is that an adapter appends success or failure once it has a
result, not before it acts. A launch that leaves no ledger entry is a launch
nothing can be reconciled against afterwards, and a failure that leaves none is
one nobody can explain.

The ledger owns the only write connection, so each record opens the writer,
appends, and closes it. That is a whole thread per event, which is the right
trade for a command that runs twice per launch.

`SQLiteWriter` starts its thread when it is *constructed*, so the bracket here is
`try:` immediately after the constructor with `await writer.start()` inside it.
Starting the writer outside the `try` left the thread behind whenever `start()`
raised or the caller was cancelled on that await, and a non-daemon thread with
nothing left to stop it hangs the interpreter at exit. That was not hypothetical:
it is what a join report arriving as the client exits did, because a report is
written from a task that the session cancels on its way out.

Reconciling a previous run's leftovers is the same shape and lives here for the
same reason: one writer lifetime, and no second writer racing an append.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from minekin_core.adapters.sqlite.event_store import SQLiteEventStore
from minekin_core.adapters.sqlite.writer import SQLiteWriter
from minekin_core.application.ports.clock import Clock
from minekin_core.application.ports.event_store import EventEnvelope, OutboxItem, payload_digest
from minekin_core.application.recovery_service import (
    RecoveryReport,
    reconcile_pending_outbox,
)
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.events import EventSource, TrustClass
from minekin_core.domain.ids import CorrelationId, EventId
from minekin_core.domain.recovery import RecoveryAction, recovery_action

PROCESS_STARTED = "SessionProcessStarted"
PROCESS_FAILED = "SessionProcessFailed"
AUTH_POLICY_FROZEN = "AuthPolicyFrozen"

# The facts a supervised session produces, by the names §5 of the internal
# architecture gives them. Closed set: a typo in an event name is otherwise
# invisible until someone queries for an event type that is never written.
HELLO_ACCEPTED = "BridgeHelloAccepted"
JOIN_OBSERVED = "JoinObserved"
PLAYABLE_ESTABLISHED = "PlayableEstablished"
INPUT_LEASE_GRANTED = "InputLeaseGranted"
INPUT_RELEASED = "InputReleased"
#: Core asked to drive the client and was told no, with the arbiter's reasons.
#: Its own event rather than one more string on the run document, because a run
#: may ask more than once — at the join and again once the world is real — and a
#: single field would keep only the last answer.
INPUT_REFUSED = "InputRefused"
SESSION_INTERRUPTED = "SessionInterrupted"
#: Which resource-pack policy the connection of one generation was actually created
#: with, as the Bridge read it off the record it handed to the client. Its own event
#: rather than a field on the run document, because the document keeps one answer per
#: name and this is a fact per attempt: every value a run reported is a row, so a
#: reader can see two of them rather than being shown only the last.
RESOURCE_PACK_POLICY_APPLIED = "ResourcePackPolicyApplied"
CLIENT_EXITED = "ClientProcessExited"
SESSION_STATE_TRANSITIONED = "SessionStateTransitioned"
#: What Core concluded when it compared the identity the Launcher encoded into argv
#: with the Session the Bridge reported. It is Core's own conclusion, in the same
#: sense `BridgeHelloAccepted` is: the Bridge is still the only side that reads the
#: live Session, so this row cannot see through a report that lies about itself —
#: what it can never be is an inference from the launch arguments, because no argv
#: text and no credential value reaches it.
SESSION_IDENTITY_COMPARED = "SessionIdentityCompared"

SESSION_EVENT_TYPES = frozenset(
    {
        PROCESS_STARTED,
        PROCESS_FAILED,
        AUTH_POLICY_FROZEN,
        HELLO_ACCEPTED,
        JOIN_OBSERVED,
        PLAYABLE_ESTABLISHED,
        INPUT_LEASE_GRANTED,
        INPUT_RELEASED,
        INPUT_REFUSED,
        SESSION_INTERRUPTED,
        RESOURCE_PACK_POLICY_APPLIED,
        CLIENT_EXITED,
        SESSION_STATE_TRANSITIONED,
        SESSION_IDENTITY_COMPARED,
    }
)

SESSION_EVENT_SCHEMA_VERSION = 1


class SessionEventLog:
    """Appends the events a session produces, one writer lifetime per event.

    Two entry points per event, because there are two callers with different
    shapes: the synchronous CLI path, and a supervised session that is already
    inside an event loop and cannot nest `asyncio.run` inside it. The sync
    method is the thin one; it exists so a command that is not running a loop
    does not have to start one to write a line.
    """

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
        return asyncio.run(
            self.record_process_started_async(
                kin_id=kin_id,
                run_id=run_id,
                session_id=session_id,
                generation=generation,
                client_instance_id=client_instance_id,
                argv_digest=argv_digest,
            )
        )

    async def record_process_started_async(
        self,
        *,
        kin_id: str,
        run_id: str,
        session_id: str,
        generation: int,
        client_instance_id: str,
        argv_digest: str,
    ) -> EventEnvelope:
        return await self._record_async(
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
        return asyncio.run(
            self.record_process_failed_async(
                kin_id=kin_id,
                run_id=run_id,
                session_id=session_id,
                generation=generation,
                error=error,
            )
        )

    async def record_process_failed_async(
        self,
        *,
        kin_id: str,
        run_id: str,
        session_id: str | None,
        generation: int | None,
        error: MinekinError,
    ) -> EventEnvelope:
        return await self._record_async(
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

    async def record_session_event(
        self,
        *,
        event_type: str,
        kin_id: str,
        run_id: str,
        session_id: str | None,
        generation: int | None,
        payload: dict[str, Any],
        source: EventSource,
        trust_class: TrustClass,
    ) -> EventEnvelope:
        """Append one fact about a running session, asynchronously.

        `source` and `trust_class` are required rather than defaulted: §6 says a
        trust class may not be declared by the input itself, so every caller
        states where the fact came from. A phase the Bridge reported is the
        Bridge's filtered word; the client's exit is Core's own observation.
        """

        if event_type not in SESSION_EVENT_TYPES:
            raise ValueError(f"{event_type} is not a reviewed session event type")
        return await self._record_async(
            event_type=event_type,
            kin_id=kin_id,
            run_id=run_id,
            session_id=session_id,
            generation=generation,
            client_instance_id=None,
            payload=payload,
            source=source,
            trust_class=trust_class,
        )

    async def open_effect(self, *, effect_type: str, idempotency_key: str) -> str:
        """Record the intent to perform an effect, before performing it.

        §8 commits the acceptance and the outbox item together and only then
        attempts the effect, so a crash in between leaves the intent on the
        ledger. That is the whole point: an effect nobody recorded is an effect
        nobody can reconcile.

        An effect type this build cannot recover is refused here rather than
        written, because a row that recovery would only refuse is a row that
        stops the next start for no reason.
        """

        if recovery_action(effect_type).action is RecoveryAction.FAIL_CLOSED:
            raise ValueError(f"{effect_type} is not an effect recovery can read")
        outbox_id = EventId.new().value
        item = OutboxItem(
            outbox_id=outbox_id,
            effect_type=effect_type,
            idempotency_key=idempotency_key,
            payload=None,
            created_at_utc=self._clock.utc_now().isoformat(),
        )
        writer = SQLiteWriter(self._database)
        try:
            await writer.start()
            await SQLiteEventStore(self._database, writer).append_with_outbox([], item)
        finally:
            await writer.aclose()
        return outbox_id

    async def settle_effect(self, outbox_id: str) -> None:
        """Mark an effect finished, once its result has been recorded."""

        writer = SQLiteWriter(self._database)
        try:
            await writer.start()
            await SQLiteEventStore(self._database, writer).mark_outbox_complete(
                outbox_id, self._clock.utc_now().isoformat()
            )
        finally:
            await writer.aclose()

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
        source: EventSource = EventSource.LAUNCHER,
        trust_class: TrustClass = TrustClass.LAUNCHER,
    ) -> EventEnvelope:
        """Read the run's next sequence and append, within one writer lifetime."""

        writer = SQLiteWriter(self._database)
        try:
            await writer.start()
            store = SQLiteEventStore(self._database, writer)
            existing = await store.read_all()
            if event_type == AUTH_POLICY_FROZEN:
                run_events = (event for event in existing if event.run_id == run_id)
                if any(
                    event.event_type in {AUTH_POLICY_FROZEN, PROCESS_STARTED, PROCESS_FAILED}
                    for event in run_events
                ):
                    raise ValueError("auth policy must be frozen once before this run starts")
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
                source=source,
                trust_class=trust_class,
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


async def reconcile_outbox_async(database: Path, *, clock: Clock) -> RecoveryReport:
    """Settle what an earlier run left pending, before this one starts anything.

    The ledger owns its only write connection, so this opens the writer, lets the
    application service decide, and closes it. Async because its caller inside a
    supervised start is already in a loop and cannot nest one.
    """

    writer = SQLiteWriter(database)
    try:
        await writer.start()
        return await reconcile_pending_outbox(SQLiteEventStore(database, writer), clock=clock)
    finally:
        await writer.aclose()


def reconcile_outbox(database: Path, *, clock: Clock) -> RecoveryReport:
    """The same reconciliation for a caller that is not already running a loop."""

    return asyncio.run(reconcile_outbox_async(database, clock=clock))
