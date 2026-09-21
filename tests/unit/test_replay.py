"""The projector: what it reads, and the two ways a stream can fail it.

The frozen fixture states one thing exactly and the projector is built to know exactly
that. So these tests are mostly about what it *refuses*: a stream that names no state,
a stream that names a state that does not exist, and a stream that jumps somewhere the
frozen table forbids. The three are different findings and the assertions keep them
different — "this is not a replay" and "the machine and the stream disagree" are not the
same sentence, and a report that merged them would be unreadable at the moment it
mattered.
"""

from __future__ import annotations

import pytest

from minekin_core.domain.replay import (
    ReplayRefused,
    SessionProjection,
    project_session,
)
from minekin_core.domain.session_state import IllegalSessionTransition, SessionState


def event(state: object, *, payload: object = None) -> dict[str, object]:
    return {
        "event_type": "SessionPreparing",
        "payload": {"state": state} if payload is None else payload,
    }


def test_a_stream_projects_to_the_state_its_last_move_reached() -> None:
    stream = [event("PREPARING"), event("STARTING_CLIENT"), event("WAITING_BRIDGE")]

    projection = project_session(stream)

    assert projection.state is SessionState.WAITING_BRIDGE
    assert projection.last_event_position == 3


def test_an_empty_stream_is_the_initial_state_with_nothing_consumed() -> None:
    """`0` and `1` are different answers, and a stream with nothing in it is the first."""

    projection = project_session([])

    assert projection == SessionProjection(state=SessionState.STOPPED, last_event_position=0)


def test_an_event_that_names_no_state_is_refused() -> None:
    """Skipping it would report a partial replay in the shape of a whole one."""

    with pytest.raises(ReplayRefused, match="names no session state"):
        project_session([event("PREPARING"), event(None, payload={"note": "nothing here"})])


def test_an_event_whose_payload_is_not_an_object_is_refused() -> None:
    with pytest.raises(ReplayRefused, match="carries no payload object"):
        project_session([event("PREPARING", payload="PREPARING")])


def test_a_state_that_does_not_exist_is_refused() -> None:
    with pytest.raises(ReplayRefused, match="which is not a session state"):
        project_session([event("PREPARING"), event("PRETENDING")])


def test_a_stream_that_jumps_is_refused_rather_than_fast_forwarded() -> None:
    """The table enumerates every legal jump, so a jump means the two disagree.

    And the refusal is the table's own error, not the projector's: the distinction is
    kept because "this stream is unreadable" and "this stream moved somewhere the
    machine cannot go" are findings about different things.
    """

    with pytest.raises(IllegalSessionTransition) as raised:
        project_session([event("PLAYABLE")])

    assert raised.value.source is SessionState.STOPPED
    assert raised.value.target is SessionState.PLAYABLE


def test_a_move_back_through_the_table_is_projected_like_any_other() -> None:
    """The negative control for the rule above: legal is legal, in either direction."""

    stream = [
        event("PREPARING"),
        event("STARTING_CLIENT"),
        event("WAITING_BRIDGE"),
        event("HANDSHAKING"),
        event("READY_MENU"),
        event("CONNECTING"),
        event("JOINED_UNVERIFIED"),
        event("PLAYABLE"),
        event("READY_MENU"),
    ]

    projection = project_session(stream)

    assert projection.state is SessionState.READY_MENU
    assert projection.last_event_position == 9
