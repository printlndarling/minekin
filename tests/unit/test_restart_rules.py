"""What a restart keeps, and what has to be true again before acting on it.

The persistence contract's table is a classification, and the sentence just after it
is the rule with teeth: a Kin may *remember* it was repairing a roof, and may not
keep placing blocks until the client has seen the inventory and the scene. So the
tests here are mostly about the second column — what re-establishment each kind of
remembered thing needs — and about the two ways a classification like this goes
wrong: a row nobody classified, and a row whose class drifts without anyone deciding
that it should.

The classes themselves are checked as a written-out list rather than read back from
the table. A change to what survives a restart is a decision about what a Kin is
after one, and it should have to be made twice: once in the module and once here,
where a reviewer sees it.
"""

from __future__ import annotations

import pytest

from minekin_core.domain.restart_rules import (
    RESTART_RULES,
    Durability,
    ResumptionPrecondition,
    admit_resumption,
    rule_for,
)

#: The contract's rows, in the contract's order, with the class this build gives
#: each. The order is part of the test: reading this beside the document should be a
#: comparison, not a search.
REVIEWED: tuple[tuple[str, Durability], ...] = (
    ("IDENTITY", Durability.KEPT),
    ("EXPERIENCE", Durability.KEPT),
    ("RELATIONSHIPS", Durability.KEPT_AND_REEVALUATED),
    ("GOALS", Durability.KEPT_AND_REVERIFIED),
    ("PLACES_AND_ASSETS", Durability.HISTORICAL_ONLY),
    ("KNOWLEDGE", Durability.KEPT),
    ("SKILLS", Durability.KEPT_AND_REVERIFIED),
    ("MOOD", Durability.RECOMPUTED),
    ("LAST_KNOWN_STATE", Durability.HISTORICAL_ONLY),
    ("INPUT_CONTROL", Durability.INVALIDATED),
    ("GUI_HANDLES", Durability.INVALIDATED),
    ("ENTITY_TOKENS", Durability.INVALIDATED),
    ("IN_FLIGHT_REQUESTS", Durability.EXPIRED),
)


def test_the_table_is_the_contracts_table_row_for_row() -> None:
    """Thirteen rows, the contract's own names, in the contract's own order."""

    assert tuple(rule.kind for rule in RESTART_RULES) == tuple(kind for kind, _ in REVIEWED)
    assert tuple(rule.durability for rule in RESTART_RULES) == tuple(
        durability for _, durability in REVIEWED
    )
    assert len(RESTART_RULES) == len({rule.kind for rule in RESTART_RULES}), "no two rows alike"


def test_every_row_says_what_it_is_and_why() -> None:
    """A row without a reason is an opinion; the contract gives each one a reason."""

    for rule in RESTART_RULES:
        assert rule.what, rule.kind
        assert rule.reason, rule.kind
        assert rule.as_document()["kind"] == rule.kind


# ---------------------------------------------------------------------------
# The rule with teeth
# ---------------------------------------------------------------------------


def test_a_remembered_position_may_not_be_acted_on_before_the_world_is_seen_again() -> None:
    """The contract's own example: remembering the roof is not permission to build.

    Nothing established is the state a restart starts in, and it must be the state in
    which the last known inventory is a memory rather than a fact.
    """

    nothing_established = admit_resumption("LAST_KNOWN_STATE", established=frozenset())
    still_remembered = admit_resumption(
        "LAST_KNOWN_STATE", established=frozenset({ResumptionPrecondition.REEVALUATED})
    )
    seen_again = admit_resumption(
        "LAST_KNOWN_STATE", established=frozenset({ResumptionPrecondition.WORLD_RE_OBSERVED})
    )

    assert nothing_established.admitted is False
    assert nothing_established.missing is ResumptionPrecondition.WORLD_RE_OBSERVED
    assert still_remembered.admitted is False, "the wrong precondition was satisfied"
    assert seen_again.admitted is True


def test_an_input_lease_is_not_resumed_by_remembering_it() -> None:
    """The row whose reason is that replaying it hurts or kills the Kin."""

    remembered = admit_resumption(
        "INPUT_CONTROL", established=frozenset({ResumptionPrecondition.WORLD_RE_OBSERVED})
    )
    taken_again = admit_resumption(
        "INPUT_CONTROL", established=frozenset({ResumptionPrecondition.RE_ACQUIRED})
    )

    assert remembered.admitted is False
    assert remembered.missing is ResumptionPrecondition.RE_ACQUIRED
    assert taken_again.admitted is True
    assert str(remembered) == "NOT_RESUMED:RE_ACQUIRED"


def test_a_late_result_is_expired_rather_than_waited_for() -> None:
    """An answer that arrives after a restart can hijack the session it lands in."""

    rule = rule_for("IN_FLIGHT_REQUESTS")

    assert rule is not None
    assert rule.durability is Durability.EXPIRED
    assert admit_resumption("IN_FLIGHT_REQUESTS", established=frozenset()).admitted is False


def test_a_relationship_comes_back_and_is_judged_again() -> None:
    """The reason on this row is about laundering, so the precondition is a judgement."""

    rule = rule_for("RELATIONSHIPS")

    assert rule is not None
    assert rule.durability is Durability.KEPT_AND_REEVALUATED
    assert rule.precondition is ResumptionPrecondition.REEVALUATED
    assert rule.reason == "防止重启洗白关系"


def test_a_goal_is_remembered_without_becoming_permission() -> None:
    """Remembering what I meant to do is not doing it, so the preconditions are checked."""

    decision = admit_resumption(
        "GOALS", established=frozenset({ResumptionPrecondition.WORLD_RE_OBSERVED})
    )

    assert decision.admitted is False
    assert decision.missing is ResumptionPrecondition.PRECONDITIONS_REVERIFIED


def test_a_mood_is_neither_frozen_nor_zeroed() -> None:
    """The two wrong answers, and the class that is neither of them."""

    rule = rule_for("MOOD")

    assert rule is not None
    assert rule.durability is Durability.RECOMPUTED
    assert rule.durability is not Durability.KEPT, "a crash does not freeze an emotion"
    assert rule.durability is not Durability.INVALIDATED, "nor does a restart calm it"


@pytest.mark.parametrize("kind", ["IDENTITY", "EXPERIENCE", "KNOWLEDGE"])
def test_what_the_kin_is_needs_nothing_re_established(kind: str) -> None:
    """The rows whose reason is that a model session ending changes nothing about them."""

    assert admit_resumption(kind, established=frozenset()).admitted is True


def test_a_kind_nobody_classified_is_refused_rather_than_allowed() -> None:
    """Not knowing what a thing is is not a reason to act on it.

    The same reading the recovery policy takes of an effect it cannot read: "I do not
    know what this was" is not "go ahead".
    """

    decision = admit_resumption("SOMETHING_NEW", established=frozenset(ResumptionPrecondition))

    assert decision.admitted is False
    assert rule_for("SOMETHING_NEW") is None


def test_the_preconditions_are_the_ones_this_build_decides() -> None:
    """Every class's precondition, spelled out, so a drift has to be deliberate."""

    assert {rule.kind: rule.precondition for rule in RESTART_RULES} == {
        "IDENTITY": ResumptionPrecondition.NONE,
        "EXPERIENCE": ResumptionPrecondition.NONE,
        "RELATIONSHIPS": ResumptionPrecondition.REEVALUATED,
        "GOALS": ResumptionPrecondition.PRECONDITIONS_REVERIFIED,
        "PLACES_AND_ASSETS": ResumptionPrecondition.WORLD_RE_OBSERVED,
        "KNOWLEDGE": ResumptionPrecondition.NONE,
        "SKILLS": ResumptionPrecondition.PRECONDITIONS_REVERIFIED,
        "MOOD": ResumptionPrecondition.RECOMPUTED,
        "LAST_KNOWN_STATE": ResumptionPrecondition.WORLD_RE_OBSERVED,
        "INPUT_CONTROL": ResumptionPrecondition.RE_ACQUIRED,
        "GUI_HANDLES": ResumptionPrecondition.RE_ACQUIRED,
        "ENTITY_TOKENS": ResumptionPrecondition.RE_ACQUIRED,
        "IN_FLIGHT_REQUESTS": ResumptionPrecondition.RE_ACQUIRED,
    }


def test_a_decision_is_evidence_ready() -> None:
    """Both answers serialize, because a refusal is a fact about a startup."""

    assert admit_resumption("IDENTITY", established=frozenset()).as_document() == {
        "admitted": True,
        "missing": None,
    }
    assert admit_resumption("INPUT_CONTROL", established=frozenset()).as_document() == {
        "admitted": False,
        "missing": "RE_ACQUIRED",
    }
