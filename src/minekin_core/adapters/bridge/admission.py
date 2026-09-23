"""Turn Bridge lifecycle reports into generation-gated connection progress.

The Bridge reports *phases*. The domain owns what a phase is allowed to mean.
This module is the only place that reads the wire enum, so the translation from
"the client says it reached X" to "the attempt advances to Y" exists once, and
every rule about untrustworthy reports stays next to it.

A report is never trusted to be about the connection Core thinks is current.
The generation is checked by the state machine, and the server profile is
checked here: a report that names a different profile revision is describing
somebody else's connection, and letting it advance this attempt would let a
stale Bridge process make a new connection look playable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from minekin_core.domain.connection import (
    CallbackDecision,
    ConnectionGenerations,
    ConnectionSignal,
)
from minekin_core.domain.ids import Generation
from minekin_core.generated.minekin.v1 import control_pb2, observation_pb2

# Cancellation is not a phase that advances anything: the Bridge has already
# invalidated that generation, so Core closes its own copy of the attempt.
CANCELLED_PHASE: Final[int] = observation_pb2.CONNECTION_PHASE_CANCELLED

# Deliberately absent from `_PHASE_SIGNALS`. The contract puts the acceptance
# with the Runtime: the Bridge sends the first authoritative snapshot and the
# Runtime validates it before anything is marked PLAYABLE. So a Bridge saying it
# is playable is not evidence that a snapshot was ever checked, and honouring it
# would let a Bridge admit a session on its own word — the one thing the
# snapshot boundary exists to prevent.
PLAYABLE_PHASE: Final[int] = observation_pb2.CONNECTION_PHASE_PLAYABLE

_PHASE_SIGNALS: Final[MappingProxyType[int, ConnectionSignal]] = MappingProxyType(
    {
        observation_pb2.CONNECTION_PHASE_RESOLVING: ConnectionSignal.RESOLUTION_STARTED,
        observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING: ConnectionSignal.ENDPOINT_ALLOWED,
        observation_pb2.CONNECTION_PHASE_PLAY_INIT: ConnectionSignal.LOGIN_ACCEPTED,
        observation_pb2.CONNECTION_PHASE_JOIN_SEEN: ConnectionSignal.JOIN_OBSERVED,
        observation_pb2.CONNECTION_PHASE_DISCONNECTED: ConnectionSignal.DISCONNECTED,
        observation_pb2.CONNECTION_PHASE_FAILED: ConnectionSignal.FAILURE,
    }
)

_NO_REASON: Final[int] = observation_pb2.ADMISSION_FAILURE_REASON_UNSPECIFIED
_CANCELLED: Final[int] = observation_pb2.ADMISSION_FAILURE_REASON_CANCELLED
#: A report that names no resource-pack policy. It is the absent case rather than
#: a value: an older Bridge, or a phase that did not create a connection, says
#: nothing here and must not be read as "deny".
_NO_POLICY: Final[int] = control_pb2.RESOURCE_PACK_POLICY_UNSPECIFIED
#: The policies this build can say on the wire, as the ledger spells them — the same
#: two lowercase tokens a trusted Server Profile uses, so the judge compares the
#: record it sealed with the fact this run reported and needs no third vocabulary.
_POLICY_TOKENS: Final[MappingProxyType[int, str]] = MappingProxyType(
    {
        control_pb2.RESOURCE_PACK_POLICY_DENY: "deny",
        control_pb2.RESOURCE_PACK_POLICY_PROMPT: "prompt",
    }
)
_KNOWN_PHASES: Final[frozenset[int]] = frozenset(observation_pb2.ConnectionPhase.values())
_KNOWN_REASONS: Final[frozenset[int]] = frozenset(observation_pb2.AdmissionFailureReason.values())
_TERMINAL_PHASES: Final[frozenset[int]] = frozenset(
    {
        observation_pb2.CONNECTION_PHASE_DISCONNECTED,
        observation_pb2.CONNECTION_PHASE_FAILED,
        CANCELLED_PHASE,
    }
)


class LifecycleDisposition(StrEnum):
    """What Core did with one report, as a stable token for evidence."""

    APPLIED = "APPLIED"
    CLOSED = "CLOSED"
    WITHHELD = "WITHHELD"
    UNBOUND = "UNBOUND"
    FOREIGN_PROFILE = "FOREIGN_PROFILE"
    UNKNOWN_PHASE = "UNKNOWN_PHASE"
    UNKNOWN_REASON = "UNKNOWN_REASON"
    #: The report named a resource-pack policy this build cannot say. Its phase
    #: may be perfectly readable, but a report that cannot be read in one part is
    #: not a report whose other parts are known good.
    UNKNOWN_POLICY = "UNKNOWN_POLICY"
    MISPAIRED_REASON = "MISPAIRED_REASON"
    INVALID_GENERATION = "INVALID_GENERATION"


@dataclass(frozen=True, slots=True)
class AdmissionOutcome:
    disposition: LifecycleDisposition
    decision: CallbackDecision | None = None
    failure_reason: str = ""
    #: The resource-pack policy the report named, as the ledger spells it. Empty
    #: when the report named none, which is the ordinary case: only the report
    #: that created a connection carries one.
    resource_pack_policy: str = ""

    @property
    def accepted(self) -> bool:
        return self.disposition in {LifecycleDisposition.APPLIED, LifecycleDisposition.CLOSED}


def apply_lifecycle(
    connections: ConnectionGenerations,
    lifecycle: observation_pb2.ConnectionLifecycle,
) -> AdmissionOutcome:
    """Gate one Bridge report against the attempt Core currently believes in."""

    phase = lifecycle.phase
    reason = lifecycle.failure_reason
    if phase not in _KNOWN_PHASES or (
        phase not in {CANCELLED_PHASE, PLAYABLE_PHASE} and phase not in _PHASE_SIGNALS
    ):
        return AdmissionOutcome(LifecycleDisposition.UNKNOWN_PHASE)
    if reason not in _KNOWN_REASONS:
        return AdmissionOutcome(LifecycleDisposition.UNKNOWN_REASON)
    if not _reason_belongs_to_phase(phase, reason, lifecycle.terminal):
        return AdmissionOutcome(LifecycleDisposition.MISPAIRED_REASON)
    policy = _policy_token(lifecycle.applied_resource_pack_policy)
    if policy is None:
        return AdmissionOutcome(LifecycleDisposition.UNKNOWN_POLICY)
    try:
        # The report's own generation, never the active one: a late report from
        # a closed generation is expected, and reading it as current is how a
        # stale Bridge process would make a new connection look playable.
        generation = Generation(lifecycle.generation)
    except ValueError:
        return AdmissionOutcome(LifecycleDisposition.INVALID_GENERATION)

    attempt = connections.active
    if attempt is None:
        return AdmissionOutcome(LifecycleDisposition.UNBOUND)
    if (
        lifecycle.server_profile_id != str(attempt.server_profile_id)
        or lifecycle.server_profile_revision != attempt.server_profile_revision
    ):
        return AdmissionOutcome(LifecycleDisposition.FOREIGN_PROFILE)

    if phase == CANCELLED_PHASE:
        return AdmissionOutcome(
            LifecycleDisposition.CLOSED,
            connections.close(generation),
            _reason_token(reason),
            policy,
        )

    if phase == PLAYABLE_PHASE:
        # Known, checked, and deliberately not acted on: see `PLAYABLE_PHASE`.
        return AdmissionOutcome(LifecycleDisposition.WITHHELD, None, _reason_token(reason), policy)

    decision = connections.apply(generation, _PHASE_SIGNALS[phase])
    return AdmissionOutcome(
        LifecycleDisposition.APPLIED,
        decision,
        _reason_token(reason),
        policy,
    )


def accept_snapshot(connections: ConnectionGenerations, generation: Generation) -> CallbackDecision:
    """The one signal only Core may produce, and only after admitting a snapshot.

    `SNAPSHOT_ACCEPTED` is not a phase a Bridge reports; it is Core's own
    conclusion about a snapshot it has validated. This is the only place it is
    applied, so a reader can find every path to `PLAYABLE` in one search.
    """

    return connections.apply(generation, ConnectionSignal.SNAPSHOT_ACCEPTED)


def _reason_belongs_to_phase(phase: int, reason: int, terminal: bool) -> bool:
    """Reject a report whose parts describe different outcomes.

    Core classifies on the phase and the reason together, so a cancellation
    carrying a whitelist rejection would be recorded as a whitelist rejection.
    The Bridge applies the same rule before sending, and this is not a second
    copy of that filter: it is Core refusing to classify a report it cannot
    read.
    """

    if terminal != (phase in _TERMINAL_PHASES):
        return False
    if phase == observation_pb2.CONNECTION_PHASE_FAILED:
        return reason not in {_NO_REASON, _CANCELLED}
    if phase == CANCELLED_PHASE:
        return reason in {_NO_REASON, _CANCELLED}
    return reason == _NO_REASON


def _reason_token(reason: int) -> str:
    if reason == _NO_REASON:
        return ""
    return observation_pb2.AdmissionFailureReason.Name(reason)


def _policy_token(policy: int) -> str | None:
    """The report's resource-pack policy as a ledger token, or why it has none.

    `None` is a refusal: a value this build cannot name is not a policy to guess
    at, and recording a guess would put a fact about the client's connection in
    the ledger that nobody reported.
    """

    if policy == _NO_POLICY:
        return ""
    return _POLICY_TOKENS.get(policy)
