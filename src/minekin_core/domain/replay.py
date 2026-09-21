"""Projecting a session state back out of an event stream.

The W00 replay fixture froze two things and until now nothing read either of them: a
stream of events, and the projection that stream is supposed to produce. This is that
reading — the projector the todo said was missing.

It is deliberately narrow, and the narrowness is the design. It knows exactly what the
fixture states and refuses everything the fixture does not: an event whose payload names
no session state is refused rather than skipped, because a replay that skips what it
cannot read is not a replay, it is a partial one that reports the same shape as a whole
one. Every move goes through the frozen transition table, so a stream that jumps —
a JOIN with no CONNECTING before it — is refused rather than fast-forwarded.

What this is *not* is a replay of a sealed run, and that is a finding rather than an
omission. A bundle's `bridge-trace.jsonl` carries Core's own ledger events, and none of
them records a session state: `SessionProcessStarted`, `BridgeHelloAccepted`,
`JoinObserved`, `PlayableEstablished` and the rest say what happened, not which state
the machine moved to. So there is nothing in a real run's timeline to fold. A mapping
from event names to states could be derived — `PlayableEstablished` does look like it
means `PLAYABLE` — but deriving it would be a guess about what the recorder meant
dressed up as a check, and the run document already records the state the machine
actually reached. When the ledger records transitions, this projects them; until then
it says what it cannot read.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from minekin_core.domain.session_state import (
    IllegalSessionTransition,
    SessionState,
    SessionStateMachine,
)


class ReplayRefused(ValueError):
    """Why an event stream cannot be projected."""


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
    """Fold an event stream through the frozen session state machine.

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


__all__ = [
    "IllegalSessionTransition",
    "ReplayRefused",
    "SessionProjection",
    "project_session",
]
