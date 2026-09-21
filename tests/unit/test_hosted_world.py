"""The hosted-world lifecycle: every edge the contract draws, and every refusal.

The diagram is the authority, so the first tests walk it — forward through the happy
path, and out through the two edges that end a clean run. The rest are about who may
move the world, because that is what the control-boundary contract puts around every
completion and what HOSTCTL-050 checks: an expired callback may not advance the state
and may not create a second world.

Two of these tests are that case's assertions, which is why they are named as
sentences: `check_case_assertions` points the case at the function.
"""

from __future__ import annotations

import pytest

from minekin_core.domain.hosted_world import (
    HostCompletion,
    HostDisposition,
    HostedWorld,
    HostedWorldState,
    WorldSignal,
    admit,
)
from minekin_core.domain.ids import Generation, KinId, OpaqueId, SessionId

PROFILE = "a" * 64

#: The creation diagram's path to a world the Kin is standing in.
TO_PLAYABLE = (
    WorldSignal.MANIFEST_AND_QUOTA,
    WorldSignal.SUPERVISOR_AND_LOCK,
    WorldSignal.CREATE_STARTED,
    WorldSignal.LOCAL_JOIN_AND_SNAPSHOT,
)


def world(**overrides: object) -> HostedWorld:
    baseline: dict[str, object] = {
        "kin_id": KinId("kin-01"),
        "hosted_world_id": OpaqueId("world-1"),
        "storage_slot": "world-kin-01-proposal-p0-0001",
        "profile_digest": PROFILE,
        "session_id": SessionId("session-1"),
        "generation": Generation(1),
        "world_epoch": Generation(1),
    }
    baseline.update(overrides)
    return HostedWorld(**baseline)  # type: ignore[arg-type]


def completion(world_at: HostedWorld, signal: WorldSignal, **overrides: object) -> HostCompletion:
    baseline: dict[str, object] = {
        "session_id": world_at.session_id,
        "generation": world_at.generation,
        "world_epoch": world_at.world_epoch,
        "expected_state": world_at.state,
        "signal": signal,
    }
    baseline.update(overrides)
    return HostCompletion(**baseline)  # type: ignore[arg-type]


def walk(current: HostedWorld, *signals: WorldSignal) -> HostedWorld:
    """Take these signals in order, asserting each one is admitted."""

    for signal in signals:
        moved, decision = admit(current, completion(current, signal))

        assert decision.disposition is HostDisposition.ADVANCED, (signal, decision)
        assert decision.previous_state is current.state
        assert moved.state is decision.current_state
        current = moved
    return current


# ---------------------------------------------------------------------------
# The diagram
# ---------------------------------------------------------------------------


def test_the_whole_creation_and_close_path_walks() -> None:
    """REQUESTED to CLOSED, one edge at a time, exactly as the contract draws it."""

    current = walk(
        world(),
        *TO_PLAYABLE,
        WorldSignal.LAN_OPENED,
        WorldSignal.CLOSE_REQUESTED,
        WorldSignal.INPUTS_REVOKED,
        WorldSignal.FLUSH_AND_STOP,
    )

    assert current.state is HostedWorldState.CLOSED


def test_a_failed_creation_is_quarantined() -> None:
    """The load/create edge: not a world that is lost, but not one to run in either."""

    quarantined = walk(world(), *TO_PLAYABLE[:-1], WorldSignal.LOAD_OR_CREATE_FAILED)

    assert quarantined.state is HostedWorldState.QUARANTINED
    assert quarantined.settled


def test_a_save_that_did_not_finish_needs_recovery() -> None:
    """And it is a different state from QUARANTINED: what is on disk is unknown."""

    saving = walk(world(), *TO_PLAYABLE, WorldSignal.LOCAL_ONLY_OR_STOP, WorldSignal.INPUTS_REVOKED)
    recovered = walk(saving, WorldSignal.CRASH_OR_ERROR)

    assert saving.state is HostedWorldState.SAVING
    assert recovered.state is HostedWorldState.RECOVERY_REQUIRED
    assert recovered.settled, "recovery is a decision somebody outside the machine makes"
    assert recovered.has_a_world, "the world was created before the save went wrong"


def test_only_the_states_the_diagram_names_are_reachable() -> None:
    """`MISSING_SAVE` is not on this diagram, and asserting it is the point.

    It is what *loading* finds — a manifest whose save is gone — so a creation can
    never reach it. If a creation could, the two ways into a world would be one.

    The walk goes through `admit` rather than through its table: a test that read the
    table would pass whatever the table said, which is the one thing worth checking.
    """

    reachable: set[HostedWorldState] = set()
    frontier = [HostedWorldState.REQUESTED]
    while frontier:
        here = world(state=frontier.pop())
        for signal in WorldSignal:
            _moved, decision = admit(here, completion(here, signal))
            if (
                decision.disposition is HostDisposition.ADVANCED
                and decision.current_state not in reachable
            ):
                reachable.add(decision.current_state)
                frontier.append(decision.current_state)

    assert reachable == set(HostedWorldState) - {
        HostedWorldState.REQUESTED,
        HostedWorldState.MISSING_SAVE,
    }


def test_the_world_exists_exactly_where_a_second_creation_would_be_a_duplicate() -> None:
    """One definition rather than two, and this is what "one" means.

    `has_a_world` and the duplicate rule are the same question asked twice, so they
    have to give the same answer in every state. Two sets that agree today would drift
    the moment one of them gained a state.
    """

    for state in HostedWorldState:
        here = world(state=state)
        refusals = {
            signal: admit(here, completion(here, signal))[1].disposition
            for signal in (
                WorldSignal.CREATE_STARTED,
                WorldSignal.LOCAL_JOIN_AND_SNAPSHOT,
                WorldSignal.LOAD_OR_CREATE_FAILED,
            )
        }

        assert here.has_a_world == all(
            disposition is HostDisposition.DUPLICATE_CREATION for disposition in refusals.values()
        ), (state, refusals)


def test_settled_means_nothing_moves_out_of_here() -> None:
    """Named for the property it is, and checked as that property."""

    for state in HostedWorldState:
        here = world(state=state)
        moves = [admit(here, completion(here, signal))[1].disposition for signal in WorldSignal]

        assert here.settled == (HostDisposition.ADVANCED not in moves), (state, moves)


# ---------------------------------------------------------------------------
# Who may move it
# ---------------------------------------------------------------------------


def test_a_completion_from_the_previous_generation_cannot_move_the_world() -> None:
    """HOSTCTL-050's first assertion, and the normal case rather than the exotic one.

    The launcher is faster than the client, so a completion from the attempt before
    this one arriving after this one started is what a real run looks like. The
    contract's word for it is that it may not forge a success, and the way that is
    made true here is that the world comes back untouched — not half-applied.
    """

    playing = walk(world(), *TO_PLAYABLE)
    # The world moved on to a second generation while this completion was in flight.
    moved_on = world(state=HostedWorldState.HOST_PLAYABLE, generation=Generation(2))
    late = completion(moved_on, WorldSignal.CLOSE_REQUESTED, generation=Generation(1))

    same, decision = admit(moved_on, late)

    assert playing.state is HostedWorldState.HOST_PLAYABLE
    assert decision.disposition is HostDisposition.STALE_COMPLETION
    assert decision.changed_state is False
    assert same is moved_on, "a refused completion may not leave a half-applied world"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"world_epoch": Generation(2)}, HostDisposition.FUTURE_EPOCH),
        ({"generation": Generation(2)}, HostDisposition.FUTURE_EPOCH),
        ({"session_id": SessionId("another-session")}, HostDisposition.WRONG_SESSION),
        ({"expected_state": HostedWorldState.LOCKED}, HostDisposition.UNEXPECTED_STATE),
    ],
)
def test_a_completion_that_does_not_match_the_world_is_refused_with_its_own_reason(
    overrides: dict[str, object], expected: HostDisposition
) -> None:
    """The four coordinates the contract re-verifies, each with its own answer.

    "Why was this refused" is the question an operator asks, so a single `REJECTED`
    would not answer it: another session, an older attempt, a newer reality and a
    stale expectation are four different things.
    """

    playing = world(state=HostedWorldState.HOST_PLAYABLE)

    same, decision = admit(playing, completion(playing, WorldSignal.LAN_OPENED, **overrides))

    assert decision.disposition is expected
    assert same is playing


def test_a_second_creation_in_one_epoch_is_refused() -> None:
    """HOSTCTL-050's second assertion: 不得重复建档, named rather than generic.

    The table would refuse it as an illegal jump, and that would be the right outcome
    and the wrong report: "you may not jump from LAN_OPEN to CREATING" is not the same
    statement as "this world already exists". A world created twice under one epoch is
    something a Kin would have to be told about.
    """

    for state in HostedWorldState:
        existing = world(state=state)
        if not existing.has_a_world:
            continue
        for signal in (
            WorldSignal.CREATE_STARTED,
            WorldSignal.LOCAL_JOIN_AND_SNAPSHOT,
            WorldSignal.LOAD_OR_CREATE_FAILED,
        ):
            same, decision = admit(existing, completion(existing, signal))

            assert decision.disposition is HostDisposition.DUPLICATE_CREATION, (state, signal)
            assert same is existing


def test_a_signal_the_diagram_has_no_edge_for_is_refused_and_the_world_stays() -> None:
    """The negative control for the duplicate rule: an ordinary jump is not a duplicate."""

    requested = world()

    for signal in (WorldSignal.LAN_OPENED, WorldSignal.FLUSH_AND_STOP, WorldSignal.CLOSE_REQUESTED):
        same, decision = admit(requested, completion(requested, signal))

        assert decision.disposition is HostDisposition.ILLEGAL_SIGNAL, signal
        assert same is requested


def test_a_move_carries_the_whole_record_with_it() -> None:
    """A transition changes the state and nothing else.

    The slot, the profile and the identities are what a world *is*; a move that lost
    one of them would leave a record nobody could rebuild the world from.
    """

    before = world()
    after = walk(before, WorldSignal.MANIFEST_AND_QUOTA)

    assert after.storage_slot == before.storage_slot
    assert after.profile_digest == before.profile_digest
    assert after.kin_id == before.kin_id
    assert after.hosted_world_id == before.hosted_world_id
    assert after.session_id == before.session_id
    assert after.world_epoch == before.world_epoch
    assert after.state is not before.state
