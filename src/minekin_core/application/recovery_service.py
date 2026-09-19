"""Reconciling what a previous run left pending, before starting another.

§13 puts this before anything is started: mark what did not end cleanly, and
invalidate the leases and generations that cannot survive. The policy for *what
may be replayed* is `domain.recovery`; this is the service that reads the ledger
and acts on it.

Two of the four outcomes are actions and two are not, on purpose. An effect that
must never be replayed is closed here, with the reason, so a later start cannot
pick it up by accident. An effect that is safe to repeat, or that needs to know
what actually happened, is left exactly as it is and reported: deciding whether
the recorded client is still running belongs to the launcher, which owns the
process identity, and quietly closing that item here would hide a live process
from the check that exists to find it.

An effect this build cannot read, and one that has already been retried to the
cap, stop the start rather than being resolved by guesswork.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from minekin_core.application.ports.clock import Clock
from minekin_core.application.ports.event_store import EventStore
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.recovery import (
    RecoveryAction,
    RecoveryDecision,
    recover_plan,
)


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """What the reconciliation found and did, with everything named."""

    #: Closed without being replayed, because replaying them is never right.
    invalidated: tuple[str, ...]
    #: Left pending: either safe to repeat, or waiting on a look at the world.
    waiting: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": "reconciled",
            "invalidated": list(self.invalidated),
            "waiting": list(self.waiting),
        }


def _refuse(effect_type: str, reason: str, category: ErrorCategory) -> MinekinError:
    return MinekinError(
        "application.recovery",
        "reconcile",
        category,
        Retryability.OPERATOR_ACTION,
        f"a pending {effect_type} effect cannot be reconciled: {reason}",
    )


def _refuse_unreadable(decisions: Sequence[RecoveryDecision]) -> None:
    """Refuse the outcomes that must not be resolved by guessing.

    Every decision is checked before anything is closed, so a refusal leaves the
    ledger exactly as it was instead of half-reconciled.
    """

    for decision in decisions:
        if decision.action is not RecoveryAction.FAIL_CLOSED:
            continue
        unknown = decision.reason.startswith("this build does not know")
        raise _refuse(
            decision.effect_type,
            decision.reason,
            ErrorCategory.INTERNAL_INVARIANT if unknown else ErrorCategory.SESSION,
        )


async def reconcile_pending_outbox(
    store: EventStore, *, clock: Clock, limit: int = 100
) -> RecoveryReport:
    """Close what must never be replayed; report the rest; refuse the unreadable."""

    pending = await store.pending_outbox(limit=limit)
    decisions = recover_plan(pending)
    _refuse_unreadable(decisions)

    invalidated: list[str] = []
    waiting: list[str] = []
    for item, decision in zip(pending, decisions, strict=True):
        if decision.action is RecoveryAction.INVALIDATE:
            await store.mark_outbox_complete(item.outbox_id, clock.utc_now().isoformat())
            invalidated.append(item.outbox_id)
        else:
            waiting.append(item.outbox_id)
    return RecoveryReport(invalidated=tuple(invalidated), waiting=tuple(waiting))


def reconcile_pending_outbox_sync(
    store: EventStore, *, clock: Clock, limit: int = 100
) -> RecoveryReport:
    """The same reconciliation for a caller that is not already running a loop."""

    return asyncio.run(reconcile_pending_outbox(store, clock=clock, limit=limit))
