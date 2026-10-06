"""A model-suggested commitment is judged against the contract, never stored on its word.

Slice B of the memory plan (`docs/memory-gateway-implementation-plan.md`): the
only writer of a commitment is a candidate the model suggested, and the gateway
accepts it only when it is well-shaped, bounded, and cites a reference the Kin
was actually shown. The matrix below is that sentence, one refusal per cell.
"""

from __future__ import annotations

from minekin_core.domain.commitment import (
    COMMITMENT_NO_EVIDENCE,
    COMMITMENT_SCHEMA,
    COMMITMENT_UNBOUNDED,
    COMMITMENT_UNKNOWN_EVIDENCE,
    MAX_COMMITMENT_CHARS,
    MAX_COMMITMENT_DUE_CHARS,
    Commitment,
    judge_commitment_candidate,
)

SHOWN = "tick=650;generation=3"


def test_a_complete_candidate_citing_a_shown_reference_is_accepted() -> None:
    judged = judge_commitment_candidate(
        {
            "text": "  come back to this cave before nightfall  ",
            "due": "before the next night",
            "evidence_ref": SHOWN,
        },
        witnesses=frozenset({SHOWN}),
    )

    assert judged == Commitment(
        text="come back to this cave before nightfall",
        due="before the next night",
        evidence_ref=SHOWN,
    )


def test_due_is_optional_and_reads_as_absent_not_empty_meaning() -> None:
    judged = judge_commitment_candidate(
        {"text": "keep the axe in the hotbar", "evidence_ref": SHOWN},
        witnesses=frozenset({SHOWN}),
    )

    assert isinstance(judged, Commitment)
    assert judged.due == ""


def test_a_candidate_without_evidence_is_refused_by_name() -> None:
    for raw in (
        {"text": "remember this"},
        {"text": "remember this", "evidence_ref": ""},
    ):
        assert (
            judge_commitment_candidate(raw, witnesses=frozenset({SHOWN})) == COMMITMENT_NO_EVIDENCE
        )


def test_evidence_that_was_never_shown_is_refused_by_name() -> None:
    # A near-miss is a miss: the reference must be one of the tokens the answer
    # was shown, character for character.
    for evidence in ("tick=999;generation=9", "tick=650;generation=4", SHOWN + " "):
        assert (
            judge_commitment_candidate(
                {"text": "remember this", "evidence_ref": evidence},
                witnesses=frozenset({SHOWN}),
            )
            == COMMITMENT_UNKNOWN_EVIDENCE
        )


def test_unknown_fields_are_refused_not_ignored() -> None:
    # The schema has no authority-bearing field, so a candidate that carries
    # one is trying to smuggle vocabulary this side would never honour.
    for raw in (
        {"text": "remember this", "evidence_ref": SHOWN, "permissions": ["move"]},
        {"text": "remember this", "evidence_ref": SHOWN, "text2": "x"},
    ):
        assert judge_commitment_candidate(raw, witnesses=frozenset({SHOWN})) == COMMITMENT_SCHEMA


def test_a_candidate_that_is_not_an_object_is_refused_by_name() -> None:
    for raw in ("remember this", 12, ["remember this"], True):
        assert judge_commitment_candidate(raw, witnesses=frozenset({SHOWN})) == COMMITMENT_SCHEMA


def test_fields_of_the_wrong_type_are_refused_by_name() -> None:
    for raw in (
        {"text": 12, "evidence_ref": SHOWN},
        {"text": "remember this", "due": 3, "evidence_ref": SHOWN},
        {"text": "remember this", "evidence_ref": ["tick=1"]},
    ):
        assert judge_commitment_candidate(raw, witnesses=frozenset({SHOWN})) == COMMITMENT_SCHEMA


def test_the_budgets_bind_and_name_themselves() -> None:
    assert (
        judge_commitment_candidate(
            {"text": "x" * (MAX_COMMITMENT_CHARS + 1), "evidence_ref": SHOWN},
            witnesses=frozenset({SHOWN}),
        )
        == COMMITMENT_UNBOUNDED
    )
    assert (
        judge_commitment_candidate(
            {"text": "   ", "evidence_ref": SHOWN},
            witnesses=frozenset({SHOWN}),
        )
        == COMMITMENT_UNBOUNDED
    )
    assert (
        judge_commitment_candidate(
            {
                "text": "remember this",
                "due": "y" * (MAX_COMMITMENT_DUE_CHARS + 1),
                "evidence_ref": SHOWN,
            },
            witnesses=frozenset({SHOWN}),
        )
        == COMMITMENT_UNBOUNDED
    )
