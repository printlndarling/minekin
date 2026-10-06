"""The judging site's verdict: which event, which payload, which trust label.

`_commitment_verdict` is the single place a carried candidate becomes a ledger
row, so its cells pin the whole outcome matrix without a live session: an
accepted intention cites what it was shown, a refusal names itself with bounded
diagnostics and no text, and the witnesses are exactly the tokens the offer
carried — nothing more.
"""

from __future__ import annotations

from typing import cast

from minekin_core.adapters.sqlite.session_log import COMMITMENT_RECORDED, COMMITMENT_REJECTED
from minekin_core.cli.session import (
    _candidate_diagnostics,  # pyright: ignore[reportPrivateUsage]
    _commitment_verdict,  # pyright: ignore[reportPrivateUsage]
    _shown_commitment_references,  # pyright: ignore[reportPrivateUsage]
)
from minekin_core.domain.commitment import COMMITMENT_SCHEMA
from minekin_core.domain.events import TrustClass

OBSERVATION = "tick=650;generation=3"
RECORD_EVENT = "event-from-last-session"


def test_an_accepted_candidate_becomes_a_recorded_row_with_its_citation() -> None:
    event_type, payload, trust = _commitment_verdict(
        {
            "text": "  come back to the cave  ",
            "due": "before the next night",
            "evidence_ref": OBSERVATION,
        },
        observation_ref=OBSERVATION,
        session_history={"record": {"event_id": RECORD_EVENT}},
    )

    assert event_type == COMMITMENT_RECORDED
    assert payload == {
        "text": "come back to the cave",
        "due": "before the next night",
        "evidence_ref": OBSERVATION,
        "observation_ref": OBSERVATION,
    }
    assert trust is TrustClass.MODEL_SUGGESTED


def test_the_last_sessions_recorded_event_id_is_a_witness_the_answer_can_cite() -> None:
    event_type, payload, _ = _commitment_verdict(
        {"text": "finish the pickaxe next time", "evidence_ref": RECORD_EVENT},
        observation_ref=OBSERVATION,
        session_history={"record": {"event_id": RECORD_EVENT}},
    )

    assert event_type == COMMITMENT_RECORDED
    assert payload["evidence_ref"] == RECORD_EVENT


def test_a_refusal_names_itself_and_echoes_no_text() -> None:
    event_type, payload, trust = _commitment_verdict(
        {
            "text": "x" * 300,
            "due": 7,
            "permissions": ["move"],
            "evidence_ref": "tick=999;generation=9",
        },
        observation_ref=OBSERVATION,
        session_history={},
    )

    assert event_type == COMMITMENT_REJECTED
    assert payload["reason_code"] == COMMITMENT_SCHEMA
    # Diagnostics are numbers and names; the refused text has no second home here.
    assert payload["text_chars"] == 300
    assert payload["due_chars"] == 0
    assert payload["evidence_ref"] == "tick=999;generation=9"
    assert payload["keys"] == ["due", "evidence_ref", "permissions", "text"]
    assert "xxx" not in str(payload)
    assert trust is TrustClass.MODEL_SUGGESTED


def test_the_witness_set_is_exactly_what_the_offer_showed() -> None:
    assert _shown_commitment_references(OBSERVATION, {}) == frozenset({OBSERVATION})
    assert _shown_commitment_references("", {"record": {"event_id": RECORD_EVENT}}) == frozenset(
        {RECORD_EVENT}
    )
    assert _shown_commitment_references(OBSERVATION, {"record": {"event_id": 7}}) == frozenset(
        {OBSERVATION}
    )
    assert _shown_commitment_references("", {"record": None}) == frozenset()


def test_field_names_in_diagnostics_are_sanitised_and_bounded() -> None:
    hostile: dict[str, object] = {"k0": "v", "bad key\nwith breaks": "v"}
    hostile.update({f"k{index}": "v" for index in range(1, 11)})
    diagnostics = _candidate_diagnostics(hostile)

    keys = cast("list[str]", diagnostics["keys"])
    assert len(keys) <= 8
    assert "badkeywithbreaks" in keys
    assert all(" " not in key and "\n" not in key for key in keys)
