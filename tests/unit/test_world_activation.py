"""Which world the Kin is in: the four rules of the switching gate.

The gate's ladder is STAGED, OBSERVING, RECONCILED, ACTIVE and most of what is worth
testing is the refusals — a JOIN that disagrees with what was expected, a jump up the
ladder, a second world becoming current, and a switch that fails leaving nothing
current rather than something the code had to invent.

One test is HOSTCOMMIT-090: the journey hosted A to remote B and back to hosted A,
with "at most one current" held at every step of it.
"""

from __future__ import annotations

import pytest

from minekin_core.domain.ids import Generation, OpaqueId, SessionId, WorldContextId
from minekin_core.domain.world_activation import (
    ActivationEvidence,
    ActivationOutcome,
    ActivationStage,
    WorldCapsule,
    activate,
    current,
    observe,
    reconcile,
    release,
    suspended,
)

A = OpaqueId("world-a")
B = OpaqueId("world-b")
CONTEXT = WorldContextId("context-a")
OTHER_CONTEXT = WorldContextId("context-b")
SESSION = SessionId("session-1")
BUNDLE = "p0-core-1.21.4"
PROFILE = "controlled-offline-server"


def capsule(world: OpaqueId, **overrides: object) -> WorldCapsule:
    baseline: dict[str, object] = {
        "world_context_id": CONTEXT,
        "hosted_world_id": world,
        "world_epoch": Generation(1),
        "storage_slot": f"slot-{world}",
        "server_profile_id": PROFILE,
        "bundle_id": BUNDLE,
        "session_id": SESSION,
        "generation": Generation(1),
    }
    baseline.update(overrides)
    return WorldCapsule(**baseline)  # type: ignore[arg-type]


def evidence(capsule_at: WorldCapsule, **overrides: object) -> ActivationEvidence:
    baseline: dict[str, object] = {
        "world_context_id": capsule_at.world_context_id,
        "world_epoch": capsule_at.world_epoch,
        "server_profile_id": capsule_at.server_profile_id,
        "bundle_id": capsule_at.bundle_id,
        "session_id": capsule_at.session_id,
        "generation": capsule_at.generation,
    }
    baseline.update(overrides)
    return ActivationEvidence(**baseline)  # type: ignore[arg-type]


def to_active(capsules: tuple[WorldCapsule, ...], world: OpaqueId) -> tuple[WorldCapsule, ...]:
    """Walk one capsule up the whole ladder, asserting each step is admitted."""

    target = next(item for item in capsules if item.hosted_world_id == world)
    moved, decision = observe(capsules, world, evidence(target))
    assert decision.outcome is ActivationOutcome.ADVANCED, decision
    moved, decision = reconcile(moved, world)
    assert decision.outcome is ActivationOutcome.ADVANCED, decision
    moved, decision = activate(moved, world)
    assert decision.outcome is ActivationOutcome.ADVANCED, decision
    return moved


# ---------------------------------------------------------------------------
# HOSTCOMMIT-090
# ---------------------------------------------------------------------------


def test_switching_worlds_keeps_exactly_one_current_at_a_time() -> None:
    """HOSTCOMMIT-090's assertion: hosted A, remote B, hosted A — one current throughout.

    Every step asserts the invariant rather than the end state, because the failure
    this rule prevents is not a wrong final answer: it is a moment in the middle where
    two worlds are both current, and a Kin whose inventory is in one of them while
    their plans are in the other.
    """

    capsules = (capsule(A), capsule(B, world_context_id=OTHER_CONTEXT))

    # Hosted A is the world the Kin is in.
    capsules = to_active(capsules, A)
    assert current(capsules) is not None
    assert current(capsules).hosted_world_id == A  # type: ignore[union-attr]

    # Switching away: A stops being current before B may become it (rule 1).
    capsules, decision = release(capsules, A)
    assert decision.outcome is ActivationOutcome.RELEASED
    assert suspended(capsules), "the Kin is between worlds while the switch is in flight"

    capsules = to_active(capsules, B)
    assert current(capsules).hosted_world_id == B  # type: ignore[union-attr]

    # And back, which is the direction a one-way rule would get wrong.
    capsules, _ = release(capsules, B)
    capsules = to_active(capsules, A)

    assert current(capsules).hosted_world_id == A  # type: ignore[union-attr]
    assert len([item for item in capsules if item.stage is ActivationStage.ACTIVE]) == 1


# ---------------------------------------------------------------------------
# The four rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "world_context_id",
        "world_epoch",
        "server_profile_id",
        "bundle_id",
        "session_id",
        "generation",
    ],
)
def test_a_join_that_disagrees_with_what_was_expected_is_refused_and_names_the_field(
    field: str,
) -> None:
    """Rule 2, and the refusal names which coordinate was wrong.

    A switch that stops for a reason nobody can act on stops forever, so "the evidence
    disagrees" is not enough on its own — the field and both values are.
    """

    staged = capsule(A)
    wrong: dict[str, object] = {
        "world_context_id": OTHER_CONTEXT,
        "world_epoch": Generation(2),
        "server_profile_id": "some-other-server",
        "bundle_id": "p0-core-0.0.0",
        "session_id": SessionId("session-2"),
        "generation": Generation(2),
    }

    moved, decision = observe((staged,), A, evidence(staged, **{field: wrong[field]}))

    assert decision.outcome is ActivationOutcome.EVIDENCE_DISAGREES
    assert decision.field == field
    assert decision.observed == wrong[field]
    assert moved == (staged,), "a refused JOIN may not move the capsule"


def test_a_switch_that_does_not_finish_leaves_nothing_current() -> None:
    """Rule 5, and the half that gets done wrong by accident.

    A Kin between worlds has suspended plans. Code that insisted on exactly one current
    world would have to invent one, so this asserts the absence rather than tolerating it.
    """

    capsules = to_active((capsule(A),), A)
    capsules, _ = release(capsules, A)
    # B's JOIN disagrees, so it never gets past STAGED.
    b = capsule(B, world_context_id=OTHER_CONTEXT)
    capsules = (*capsules, b)
    moved, decision = observe(capsules, B, evidence(b, generation=Generation(9)))

    assert decision.outcome is ActivationOutcome.EVIDENCE_DISAGREES
    assert suspended(moved)
    assert current(moved) is None


def test_a_second_world_cannot_become_current_while_one_is() -> None:
    """Rule 4, and it is refused rather than resolved by taking the newer one."""

    capsules = to_active((capsule(A), capsule(B, world_context_id=OTHER_CONTEXT)), A)
    b = next(item for item in capsules if item.hosted_world_id == B)
    moved, _ = observe(capsules, B, evidence(b))
    moved, _ = reconcile(moved, B)

    same, decision = activate(moved, B)

    assert decision.outcome is ActivationOutcome.ANOTHER_WORLD_IS_CURRENT
    assert same == moved
    assert current(same).hosted_world_id == A  # type: ignore[union-attr]


def test_the_ladder_is_linear_so_a_jump_is_refused_rather_than_fast_forwarded() -> None:
    """Rule 3: nothing is current without having been confirmed.

    A world that skipped reconciliation would become the reality the Kin's facts are
    bound to on the strength of a JOIN alone.
    """

    staged = (capsule(A),)

    for operation in (reconcile, activate):
        moved, decision = operation(staged, A)

        assert decision.outcome is ActivationOutcome.WRONG_STAGE, operation.__name__
        assert moved == staged

    observing, _ = observe(staged, A, evidence(staged[0]))
    _moved, decision = activate(observing, A)

    assert decision.outcome is ActivationOutcome.WRONG_STAGE


def test_a_world_nobody_staged_cannot_be_switched_to() -> None:
    moved, decision = observe((capsule(A),), B, evidence(capsule(B)))

    assert decision.outcome is ActivationOutcome.UNKNOWN_WORLD
    assert moved == (capsule(A),)


def test_a_record_with_two_current_worlds_is_refused_rather_than_picked_between() -> None:
    """A record this module cannot build came from somewhere else.

    That is exactly where the contradiction would arrive from — a file, another
    version — and choosing either world would attribute one world's facts to another.
    """

    both = (capsule(A, stage=ActivationStage.ACTIVE), capsule(B, stage=ActivationStage.ACTIVE))

    with pytest.raises(ValueError, match="more than one world is ACTIVE"):
        current(both)
