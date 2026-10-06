"""What may be replayed after a crash, and what never may.

A committed outbox item is a promise that an external effect will happen. After
a crash the promise is still there but the world may already have moved: the
client may be running, the connection may be live, the keys may be held. The
answer is not "retry everything" — a replayed input lease is a second set of
keypresses the operator never asked for — and it is not "give up" either,
because a bundle download that never happened can simply be done again.

§8 of the internal architecture splits the effects by what is safe, and this is
that split as a table rather than as prose. The distinction that matters most:
an effect is retryable when repeating it is the *same* request (content-addressed
downloads), and it is not retryable when repeating it depends on state that has
since changed — which is every effect whose correctness was tied to a connection
generation or to a held lease.

An effect this build does not recognise is refused rather than guessed at: the
safe reading of "I do not know what this was going to do" is not "do it again".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Protocol

#: How many times an effect that is safe to repeat may be tried before the run
#: is stopped instead. Retrying forever is a way of never failing cleanly.
MAX_ATTEMPTS: Final[int] = 3

BUNDLE_FETCH: Final[str] = "BUNDLE_FETCH"
START_CLIENT: Final[str] = "START_CLIENT"
CONNECT_WORLD: Final[str] = "CONNECT_WORLD"
INPUT_LEASE: Final[str] = "INPUT_LEASE"


class RecoveryAction(StrEnum):
    """What recovery is allowed to do with one pending effect."""

    #: Repeating it is the same request, so repeating it is safe.
    RETRY = "RETRY"
    #: Look at what actually happened — process identity, recorded markers —
    #: and decide from that rather than from the intent.
    RECONCILE = "RECONCILE"
    #: Never repeat it. Drop it and record why, because the state it depended
    #: on is gone and the effect cannot be made correct again.
    INVALIDATE = "INVALIDATE"
    #: There is no safe action. Stop and let a person decide.
    FAIL_CLOSED = "FAIL_CLOSED"


_ACTIONS: Final[MappingProxyType[str, RecoveryAction]] = MappingProxyType(
    {
        # Content-addressed, so a repeat either finds the bytes or fetches the
        # same bytes again.
        BUNDLE_FETCH: RecoveryAction.RETRY,
        # Starting a JVM twice puts a second player in the world. Ask the
        # process identity whether the first one is still there.
        START_CLIENT: RecoveryAction.RECONCILE,
        # The generation this was meant for is over; a reconnect is a new
        # generation, not a resumed one.
        CONNECT_WORLD: RecoveryAction.INVALIDATE,
        # Leases are deliberately not persisted, so this item can only be a
        # stale intent to press keys. Replaying it is the failure mode.
        INPUT_LEASE: RecoveryAction.INVALIDATE,
        # Two effects are deliberately NOT reviewed here, and their absence is the
        # decision rather than an oversight: a release of all inputs and a stop of
        # the session. The release promise is the INPUT_LEASE row's own — it opens
        # before any key can be pressed and closes exactly when the release command
        # has gone out (`release_inputs` settles it) — so a second "release
        # everything" row would be the same promise twice, replayed to nobody
        # (reconcile runs before any channel exists). A stop's answer is owned by
        # the pair that asked for it: the request file and its receipt, with the
        # stopper's own deadline escalation; a next session was started by an
        # operator, and replaying a stop into it would stop a session nobody asked
        # to stop. Both names therefore read as ones this build does not know —
        # refused loudly — and a future build that opens either must teach this
        # table together with what replaying it would mean.
    }
)


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    effect_type: str
    action: RecoveryAction
    reason: str

    @property
    def replayable(self) -> bool:
        return self.action is RecoveryAction.RETRY


def recovery_action(effect_type: str, attempts: int = 0) -> RecoveryDecision:
    """What recovery may do with one pending effect, and why."""

    if attempts < 0:
        raise ValueError("attempts cannot be negative")
    action = _ACTIONS.get(effect_type)
    if action is None:
        return RecoveryDecision(
            effect_type,
            RecoveryAction.FAIL_CLOSED,
            "this build does not know what this effect was going to do",
        )
    if action is RecoveryAction.RETRY and attempts >= MAX_ATTEMPTS:
        return RecoveryDecision(
            effect_type,
            RecoveryAction.FAIL_CLOSED,
            f"it has already been attempted {attempts} times",
        )
    return RecoveryDecision(effect_type, action, _REASONS[action])


_REASONS: Final[MappingProxyType[RecoveryAction, str]] = MappingProxyType(
    {
        RecoveryAction.RETRY: "repeating it is the same request",
        RecoveryAction.RECONCILE: "ask what actually happened before deciding",
        RecoveryAction.INVALIDATE: "the state it depended on is gone",
        RecoveryAction.FAIL_CLOSED: "there is no safe action to take",
    }
)


class PendingEffect(Protocol):
    """What this module needs to know about a pending item, and nothing more.

    Structural on purpose: the store's own `OutboxItem` lives in a port, and a
    domain rule has no business importing one to read two fields.
    """

    @property
    def effect_type(self) -> str: ...

    @property
    def attempts(self) -> int: ...


def recover_plan(items: Iterable[PendingEffect]) -> tuple[RecoveryDecision, ...]:
    """Decide for every pending item, in the order the ledger holds them."""

    return tuple(recovery_action(item.effect_type, item.attempts) for item in items)
