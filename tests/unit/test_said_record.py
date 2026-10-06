"""The KinSaid row one step owes: only a confirmed speech act gets one.

`_said_record` is the single place a say step becomes a `KinSaid` ledger row, so
its cells pin the whole rule: the words come from the honoured ask, and a step
that did not speak — the wrong skill, a refused send, no words at all — owes
nothing rather than a row claiming a speech act that did not happen.
"""

from __future__ import annotations

from minekin_core.application.player_mind import MindDecisionKind, MindIntent
from minekin_core.application.skill_plan import SkillPlan
from minekin_core.application.world_skills import SkillCall
from minekin_core.cli.session import _said_record  # pyright: ignore[reportPrivateUsage]
from minekin_core.domain.world_actions import ActionResultClass, SkillOutcome


def intent(skill: str, **arguments: object) -> MindIntent:
    return MindIntent(
        kind=MindDecisionKind.INTENT,
        plan=SkillPlan((SkillCall(name=skill),)),
        reason="",
        arguments=arguments,
    )


def test_a_confirmed_send_with_words_owes_the_said_row() -> None:
    record = _said_record(
        intent("say", text="hello there"),
        SkillOutcome(result=ActionResultClass.CONFIRMED, reason="CLIENT_SENT", action_id="say-1"),
    )

    assert record == {"text": "hello there", "action_id": "say-1"}


def test_a_refused_or_unconfirmed_send_owes_nothing() -> None:
    """A line the client refused never reached anyone; a "said" row for it would be
    the ledger claiming a speech act that did not happen."""

    for result, reason in (
        (ActionResultClass.FAILED, "SAY_UNAVAILABLE"),
        (ActionResultClass.UNKNOWN, "SAY_NOT_CONFIRMED"),
        (ActionResultClass.INTERRUPTED, "SESSION_STOP_REQUESTED"),
    ):
        assert (
            _said_record(
                intent("say", text="hello"),
                SkillOutcome(result=result, reason=reason, action_id="say-1"),
            )
            is None
        ), result


def test_a_step_that_did_not_speak_owes_nothing() -> None:
    confirmed = SkillOutcome(result=ActionResultClass.CONFIRMED, reason="", action_id="a-1")

    assert _said_record(intent("turn_to"), confirmed) is None
    assert _said_record(intent("say"), confirmed) is None
    assert _said_record(intent("say", text=""), confirmed) is None
    assert _said_record(intent("say", text=7), confirmed) is None
