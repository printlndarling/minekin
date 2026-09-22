"""Reading a session state back out of a recorded timeline, and saying what that reading was.

Two kinds of stream are read here, and they are different records that happen to
share a machine.

A **fixture** states both a stream and the projection it should produce, and
`project_session` reads that dialect: every event carries a payload naming the state
the stream is in, and the stream is folded through the frozen table. That dialect
belongs to `tests/fixtures/replay/`, was frozen at W00, and is read by the one tool
that reads a fixture — it is not what a ledger writes, and nothing here reads a state
out of an event's name or out of a payload on the bundle path.

A **ledger** records one ordinary row per thing that happened, and — once Core's
ledger records transitions — payloads that state the move explicitly: `from` and `to`,
both named. `explicit_transitions` extracts exactly those payloads and refuses to guess
at the rest. Deriving a state from an event name would be a guess about the recorder
wearing the shape of a check, and the fact that `PlayableEstablished` reads like
`PLAYABLE` is the reason the guess would be tempting, not a reason to make it.

What this module is *not* is a filesystem reader. It takes rows that are already
parsed and answers what they amount to; reading bytes, holding them to a manifest and
keeping strict JSON happen in the adapter that calls it. The classification of a
reading — which failures are about the bytes and which are about what the bytes say —
is decided here, because that is a judgment about the session and not about the file.

Nothing here is narrow by accident. Every move goes through the frozen transition
table, so a recorded jump — a JOIN with no CONNECTING before it — is refused rather
than fast-forwarded, and a moved row that disagrees with the machine is a finding
rather than something to reconcile.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from minekin_core.domain.errors import ErrorCategory, ExitCode, exit_code_for
from minekin_core.domain.session_state import (
    IllegalSessionTransition,
    SessionState,
    SessionStateMachine,
)


class ReplayRefused(ValueError):
    """Why an event stream cannot be projected."""


#: The two names a ledger row carries when it records a move. The plan for the ledger
#: (`CORE-STATE-TRANSITION-001`) states the record as an explicit `from`/`to` fact, so
#: these are the names. A row that spells a move differently is an ordinary row, and
#: this reads no move out of it — which is the whole difference between reading a
#: record and interpreting one.
TRANSITION_FROM = "from"
TRANSITION_TO = "to"

#: Told apart from a JSON `null`: "this row does not name a source" and "this row names
#: a source that is not a state" are different rows and only one of them is a move.
_ABSENT: object = object()


@dataclass(frozen=True, slots=True)
class SessionProjection:
    """What a stream of events says the session's state is."""

    state: SessionState
    #: The 1-based position of the last event the projection consumed, or 0 for a
    #: stream with nothing in it. A cursor, not a count of moves: an event that
    #: carried a state and did not move the machine is not representable here
    #: (the frozen table refuses a self-transition), so the two readings coincide
    #: today and this says which one it means before they come apart.
    last_event_position: int

    def as_document(self) -> dict[str, object]:
        return {"state": self.state.value, "last_event_position": self.last_event_position}


@dataclass(frozen=True, slots=True)
class RecordedTransition:
    """One move a ledger row recorded, and where that row sits in the timeline."""

    position: int
    source: SessionState
    target: SessionState


class NoTransitionsRecorded(ReplayRefused):
    """The timeline holds no move, so there is nothing to fold.

    This is the ordinary shape of a bundle sealed before the ledger recorded
    transitions: Core's rows say what happened, not where the session went. It is a
    refusal and a stable one, not a failure — and it is deliberately not the seed of a
    mapping from event names to states.
    """


class RecordedTransitionDisagrees(IllegalSessionTransition):
    """The recorded move began somewhere the session is not.

    A kind of `IllegalSessionTransition` because it is the same finding: the record and
    the machine disagree about what happened, which is not something to reconcile by
    preferring one of them. The frozen table may well allow the move *to* — what it
    cannot allow is a ledger's own account of where the move started being ignored.
    """

    def __init__(self, current: SessionState, recorded: RecordedTransition) -> None:
        # Not `IllegalSessionTransition.__init__`: it would name the pair the frozen
        # table forbids, and here the machine's state and the recorded target may well
        # be a legal pair. What disagrees is the recorded source.
        self.current = current
        self.recorded = recorded
        ValueError.__init__(
            self,
            f"row {recorded.position} records a move from {recorded.source.value} and the "
            f"session was at {current.value} — the record and the machine disagree about "
            "where the move began, so it is not played back over the difference",
        )


def _session_state(named: object, position: int, field: str) -> SessionState:
    if not isinstance(named, str) or not named:
        raise ReplayRefused(f"row {position} names {field}={named!r}, which is not a session state")
    try:
        return SessionState(named)
    except ValueError:
        raise ReplayRefused(
            f"row {position} names {field}={named!r}, which is not a session state"
        ) from None


def explicit_transition(payload: Mapping[str, object], position: int) -> RecordedTransition | None:
    """The move this payload records, or `None` when it records no move.

    A row is a move because it carries both names, and for no other reason: not its
    event type, not what its payload happens to hold. An ordinary row is not refused
    for lacking a state — it is simply not a move, and a timeline of them is a timeline
    with nothing to fold. A row that names half a move *is* refused, because reading it
    would mean inventing the half that was never written.
    """

    recorded_from = payload.get(TRANSITION_FROM, _ABSENT)
    recorded_to = payload.get(TRANSITION_TO, _ABSENT)
    if recorded_from is _ABSENT and recorded_to is _ABSENT:
        return None
    if recorded_from is _ABSENT or recorded_to is _ABSENT:
        named, missing = (
            (TRANSITION_FROM, TRANSITION_TO)
            if recorded_from is not _ABSENT
            else (TRANSITION_TO, TRANSITION_FROM)
        )
        raise ReplayRefused(
            f"row {position} names {named!r} and not {missing!r} — half a move is not a "
            "move, and reading it as one would be inventing what was never written"
        )
    return RecordedTransition(
        position=position,
        source=_session_state(recorded_from, position, TRANSITION_FROM),
        target=_session_state(recorded_to, position, TRANSITION_TO),
    )


def explicit_transitions(
    payloads: Sequence[Mapping[str, object]],
) -> tuple[RecordedTransition, ...]:
    """Every move these payloads record, in the order the timeline records them."""

    moves: list[RecordedTransition] = []
    for position, payload in enumerate(payloads, start=1):
        move = explicit_transition(payload, position)
        if move is not None:
            moves.append(move)
    return tuple(moves)


def project_transitions(moves: Sequence[RecordedTransition]) -> SessionProjection:
    """Fold the moves a ledger recorded through the frozen session state machine.

    Each move is checked twice over: the recorded `from` has to be where the machine
    actually is, and the frozen table has to allow the step to `to`. The first check is
    what makes a recorded `from` a fact that is *checked* rather than a fact that is
    believed — a ledger that says a move began somewhere the machine has never been is
    a ledger that disagrees with itself, and the disagreement survives into the report
    instead of being smoothed over by trusting the record.

    Raises `NoTransitionsRecorded` for a timeline that holds no move at all, and
    `IllegalSessionTransition` — including `RecordedTransitionDisagrees` — for one that
    reads and moves somewhere the machine cannot go.
    """

    if not moves:
        raise NoTransitionsRecorded(
            "the timeline records no transition — nothing in it says which state the "
            "session moved to, so there is no move to fold and no mapping from event "
            "names to states is derived to make it look as though there were one"
        )
    machine = SessionStateMachine()
    for move in moves:
        if machine.state is not move.source:
            raise RecordedTransitionDisagrees(machine.state, move)
        machine.advance(move.target)
    return SessionProjection(state=machine.state, last_event_position=moves[-1].position)


def _event_state(event: Mapping[str, object], position: int) -> SessionState:
    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        raise ReplayRefused(f"event {position} carries no payload object")
    named = cast(Mapping[str, object], payload).get("state")
    if not isinstance(named, str) or not named:
        raise ReplayRefused(
            f"event {position} ({event.get('event_type')!r}) names no session state — "
            "the stream is not replayable, and skipping it would report a partial "
            "replay in the shape of a whole one"
        )
    try:
        return SessionState(named)
    except ValueError:
        raise ReplayRefused(
            f"event {position} names {named!r}, which is not a session state"
        ) from None


def project_session(events: Sequence[Mapping[str, object]]) -> SessionProjection:
    """Fold a *fixture* stream through the frozen session state machine.

    This is the W00 fixture's dialect — a payload naming `state` on every event — and
    it is not what a ledger writes. It is kept for the one tool that replays a fixture,
    whose expectation travels inside the fixture itself, and it is not reachable from
    the bundle path: a sealed timeline read with this would be reading a record that
    does not exist in this shape.

    Raises `ReplayRefused` for a stream that cannot be read at all, and lets
    `IllegalSessionTransition` out for one that reads and moves somewhere the table
    forbids. The two are different findings and stay different: the first says the
    stream is not a replay, the second says the machine and the stream disagree about
    what happened.
    """

    machine = SessionStateMachine()
    for position, event in enumerate(events, start=1):
        target = _event_state(event, position)
        machine.advance(target)
    return SessionProjection(state=machine.state, last_event_position=len(events))


class ReplayReason(StrEnum):
    """Every way a sealed bundle's timeline fails to be a projection.

    The names are the words a report carries, so this is a closed vocabulary: a reader
    branches on them without matching prose, and a message can be reworded without a
    downstream check changing what it means.

    The vocabulary lives here rather than beside the reading because what each name
    *means for the operator* is a judgment about the session — is this material that was
    tampered with, or a record that says something other than a session history? — and a
    judgment is not the filesystem layer's to make. Which of the two a name belongs to
    is decided by the one table below it.
    """

    # The bundle is not the bundle it says it is.
    NOT_A_BUNDLE = "NOT_A_BUNDLE"
    BUNDLE_DOES_NOT_HOLD_UP = "BUNDLE_DOES_NOT_HOLD_UP"
    NO_TIMELINE_IS_DECLARED = "NO_TIMELINE_IS_DECLARED"
    TIMELINE_IS_NOT_THE_BYTES_THAT_WERE_SEALED = "TIMELINE_IS_NOT_THE_BYTES_THAT_WERE_SEALED"
    BUNDLE_CANNOT_BE_READ = "BUNDLE_CANNOT_BE_READ"
    TIMELINE_CANNOT_BE_READ = "TIMELINE_CANNOT_BE_READ"

    # The bundle holds up, and what it holds is not a session history.
    TIMELINE_IS_NOT_UTF8 = "TIMELINE_IS_NOT_UTF8"
    TIMELINE_LINE_IS_BLANK = "TIMELINE_LINE_IS_BLANK"
    TIMELINE_LINE_IS_NOT_JSON = "TIMELINE_LINE_IS_NOT_JSON"
    TIMELINE_LINE_HAS_A_DUPLICATE_KEY = "TIMELINE_LINE_HAS_A_DUPLICATE_KEY"
    TIMELINE_LINE_HAS_A_NON_FINITE_NUMBER = "TIMELINE_LINE_HAS_A_NON_FINITE_NUMBER"
    TIMELINE_LINE_IS_NOT_AN_EVENT = "TIMELINE_LINE_IS_NOT_AN_EVENT"
    TIMELINE_PAYLOAD_HASH_MISMATCH = "TIMELINE_PAYLOAD_HASH_MISMATCH"
    NO_STATE_TRANSITIONS = "NO_STATE_TRANSITIONS"
    TIMELINE_IS_NOT_A_REPLAY = "TIMELINE_IS_NOT_A_REPLAY"
    TIMELINE_JUMPED = "TIMELINE_JUMPED"


class ReplayStatus(StrEnum):
    """What a reading of one bundle produced."""

    PROJECTED = "projected"
    #: The bundle holds up and its timeline cannot be folded into a session state.
    SEMANTIC_INCOMPLETE = "semantic_incomplete"
    #: The bundle is not the bundle it says it is, so there is nothing to fold.
    INVALID = "invalid"


#: Which of the two buckets each reason belongs to. One table, so a reason cannot be
#: added without deciding whether it is a fact about the bytes or a fact about what
#: they say — which is the only question the classification answers.
_REASON_CATEGORY: dict[ReplayReason, ErrorCategory] = {
    ReplayReason.NOT_A_BUNDLE: ErrorCategory.STORAGE,
    ReplayReason.BUNDLE_DOES_NOT_HOLD_UP: ErrorCategory.STORAGE,
    ReplayReason.NO_TIMELINE_IS_DECLARED: ErrorCategory.STORAGE,
    ReplayReason.TIMELINE_IS_NOT_THE_BYTES_THAT_WERE_SEALED: ErrorCategory.STORAGE,
    ReplayReason.BUNDLE_CANNOT_BE_READ: ErrorCategory.STORAGE,
    ReplayReason.TIMELINE_CANNOT_BE_READ: ErrorCategory.STORAGE,
    ReplayReason.TIMELINE_PAYLOAD_HASH_MISMATCH: ErrorCategory.STORAGE,
    ReplayReason.TIMELINE_IS_NOT_UTF8: ErrorCategory.SESSION,
    ReplayReason.TIMELINE_LINE_IS_BLANK: ErrorCategory.SESSION,
    ReplayReason.TIMELINE_LINE_IS_NOT_JSON: ErrorCategory.SESSION,
    ReplayReason.TIMELINE_LINE_HAS_A_DUPLICATE_KEY: ErrorCategory.SESSION,
    ReplayReason.TIMELINE_LINE_HAS_A_NON_FINITE_NUMBER: ErrorCategory.SESSION,
    ReplayReason.TIMELINE_LINE_IS_NOT_AN_EVENT: ErrorCategory.SESSION,
    ReplayReason.NO_STATE_TRANSITIONS: ErrorCategory.SESSION,
    ReplayReason.TIMELINE_IS_NOT_A_REPLAY: ErrorCategory.SESSION,
    ReplayReason.TIMELINE_JUMPED: ErrorCategory.SESSION,
}


def replay_category(reason: ReplayReason) -> ErrorCategory:
    """Which bucket a refusal belongs to: the bytes, or what the bytes say."""

    return _REASON_CATEGORY[reason]


def replay_status(reason: ReplayReason | None) -> ReplayStatus:
    """How a reading reads to a person, given the reason it stopped for.

    Derived from the bucket rather than tabled beside it: a second table would be one
    more thing to keep in step, and the bucket is what is actually decided.
    """

    if reason is None:
        return ReplayStatus.PROJECTED
    if replay_category(reason) is ErrorCategory.STORAGE:
        return ReplayStatus.INVALID
    return ReplayStatus.SEMANTIC_INCOMPLETE


def replay_exit_code(reason: ReplayReason | None) -> ExitCode:
    """The process exit code a reading of this kind is worth."""

    return ExitCode.OK if reason is None else exit_code_for(replay_category(reason))


__all__ = [
    "TRANSITION_FROM",
    "TRANSITION_TO",
    "IllegalSessionTransition",
    "NoTransitionsRecorded",
    "RecordedTransition",
    "RecordedTransitionDisagrees",
    "ReplayReason",
    "ReplayRefused",
    "ReplayStatus",
    "SessionProjection",
    "explicit_transition",
    "explicit_transitions",
    "project_session",
    "project_transitions",
    "replay_category",
    "replay_exit_code",
    "replay_status",
]
