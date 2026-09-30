"""A plan is read before a client exists, leased for its own length, and stopped by the
first step the world did not confirm.

The skills' own verdicts are tested where they are produced. What is tested here is the
layer that decides *which* run: the refusals that come before a JVM is started, the
capabilities a skill name carries, the lease a sequence needs to last as long as its
slowest honest reading, and the rule that a step the readings could not settle ends the
sequence rather than being retried or walked past. The committed example plan is read
too, because a plan an operator is pointed at has to stay parseable.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, cast

import pytest
from google.protobuf.message import Message

from minekin_core.application.skill_plan import (
    SKILL_ARGUMENT_MISSING,
    SKILL_UNKNOWN,
    STEP_LEASE_HEADROOM_S,
    SkillCall,
    SkillPlan,
    SkillPlanError,
    parse_skill_plan,
    perform_skill,
    run_skill_plan,
    sequence_lease_seconds,
)
from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.application.world_skills import (
    DEFAULT_STEP_TIMEOUT_NS,
    ActionAuthority,
    WorldSkills,
)
from minekin_core.domain.control_vocabulary import (
    AIM_CAPABILITY,
    GUI_CAPABILITY,
    HOTBAR_CAPABILITY,
    MINE_CAPABILITY,
    MOVE_CAPABILITY,
    SCREEN_CAPABILITY,
)
from minekin_core.domain.world_actions import ActionResultClass, SkillOutcome

EXAMPLES: Final = Path(__file__).resolve().parents[2] / "examples"
AUTHORITY: Final = ActionAuthority(
    lease_id="lease-1", generation=3, deadline_monotonic_ns=DEFAULT_STEP_TIMEOUT_NS * 2
)


def _outcome(result: ActionResultClass) -> SkillOutcome:
    return SkillOutcome(result=result, reason="", action_id="a-1")


class _RecordingSender:
    """The transport as a refusal needs it: it remembers, and never answers."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_control(self, message_type: str, message: Message) -> None:
        del message
        self.sent.append(message_type)


class _TapeSkills(WorldSkills):
    """The skills as a tape, so the plan's ordering rule is read apart from the readings.

    Only the names a tested plan uses are scripted. A call that reaches a name this
    tape does not carry raises rather than answering `UNKNOWN`, because that would let
    a test's own mistake look like the behaviour it is checking for.
    """

    def __init__(self, outcomes: Mapping[str, SkillOutcome], sender: _RecordingSender) -> None:
        super().__init__(
            sender=sender,
            observations=WorldObservationStore(),
            capabilities=frozenset(
                {
                    AIM_CAPABILITY,
                    MINE_CAPABILITY,
                    MOVE_CAPABILITY,
                    SCREEN_CAPABILITY,
                    GUI_CAPABILITY,
                    HOTBAR_CAPABILITY,
                }
            ),
        )
        self._outcomes = outcomes
        self.ran: list[str] = []

    async def _answer(self, name: str) -> SkillOutcome:
        if name not in self._outcomes:
            raise AssertionError(f"the tape has no outcome for {name}")
        self.ran.append(name)
        return self._outcomes[name]

    async def turn_to(
        self,
        *,
        yaw_degrees: float,
        pitch_degrees: float,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del yaw_degrees, pitch_degrees, authority, timeout_ns
        return await self._answer("turn_to")

    async def break_seen_block(
        self,
        *,
        authority: ActionAuthority,
        expected_drop_item: str | None = None,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, expected_drop_item, timeout_ns
        return await self._answer("break_seen_block")

    async def craft(
        self,
        *,
        recipe_id: str,
        materials: Mapping[str, int],
        product_id: str,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del recipe_id, materials, product_id, authority, timeout_ns
        return await self._answer("craft")


def _plan(*skills: str) -> SkillPlan:
    """A plan of the named skills, each with the arguments that skill requires."""

    document = {
        "schema_version": 1,
        "skills": [{"skill": name, **_ARGUMENTS[name]} for name in skills],
    }
    return parse_skill_plan(document, source="test")


_ARGUMENTS: Final[dict[str, dict[str, object]]] = {
    "turn_to": {},
    "break_seen_block": {},
    "collect_dropped": {"item_id": "minecraft:oak_log"},
    "craft": {
        "recipe_id": "minecraft:oak_planks",
        "materials": {"minecraft:oak_log": 1},
        "product_id": "minecraft:oak_planks",
    },
    "select_hotbar": {"slot": 0},
}


def test_a_plan_is_read_in_order_with_typed_arguments() -> None:
    plan = _plan("turn_to", "craft", "select_hotbar")

    assert [call.name for call in plan.calls] == ["turn_to", "craft", "select_hotbar"]
    assert plan.calls[1].materials == (("minecraft:oak_log", 1),)
    assert plan.calls[2].slot == 0
    assert len(plan) == 3


#: Every shape a plan document can have that an operator should not have to debug
#: from a stack trace. Each is refused by name, with the entry's position.
_UNREADABLE: Final[list[tuple[object, str]]] = [
    ([{"skill": "turn_to"}], "must be an object"),
    ({"skills": [{"skill": "turn_to"}]}, "schema_version 1"),
    ({"schema_version": 2, "skills": []}, "schema_version 1"),
    ({"schema_version": 1}, "needs a `skills` list"),
    ({"schema_version": 1, "skills": []}, "at least one entry"),
    ({"schema_version": 1, "skills": ["turn_to"]}, "must be an object naming one skill"),
    (
        {"schema_version": 1, "skills": [{"skill": "brake_seen_block"}]},
        "is not a skill this build has",
    ),
    ({"schema_version": 1, "skills": [{}]}, "has no `skill` name"),
    (
        {"schema_version": 1, "skills": [{"skill": "turn_to", "yaw": 90}]},
        "keys it does not take",
    ),
    (
        {"schema_version": 1, "skills": [{"skill": "craft", "recipe_id": "r"}]},
        "is missing",
    ),
    (
        {
            "schema_version": 1,
            "skills": [
                {
                    "skill": "craft",
                    "recipe_id": "r",
                    "product_id": "p",
                    "materials": {"minecraft:oak_log": 0},
                }
            ],
        },
        "positive number",
    ),
]


@pytest.mark.parametrize(("document", "words"), _UNREADABLE)
def test_an_unreadable_plan_is_refused_by_name_and_position(document: object, words: str) -> None:
    with pytest.raises(SkillPlanError) as raised:
        parse_skill_plan(document, source="test")

    assert words in str(raised.value)


def test_a_refusal_names_which_entry_it_is_so_the_author_can_find_it() -> None:
    with pytest.raises(SkillPlanError) as raised:
        parse_skill_plan(
            {
                "schema_version": 1,
                "skills": [{"skill": "turn_to"}, {"skill": "collect_dropped"}],
            }
        )

    assert "skills[1] (collect_dropped) is missing ['item_id']" in str(raised.value)


def test_a_skill_name_carries_the_capabilities_it_will_ask_for() -> None:
    assert _plan("turn_to").capabilities == frozenset({AIM_CAPABILITY})
    assert _plan("break_seen_block").capabilities == frozenset({MINE_CAPABILITY})
    assert _plan("collect_dropped").capabilities == frozenset({MOVE_CAPABILITY, AIM_CAPABILITY})
    assert _plan("craft").capabilities == frozenset({SCREEN_CAPABILITY, GUI_CAPABILITY})
    # One lease for the whole plan, and no more than the plan asks for.
    assert _plan("turn_to", "select_hotbar").capabilities == frozenset(
        {AIM_CAPABILITY, HOTBAR_CAPABILITY}
    )


def test_the_lease_last_as_long_as_the_whole_sequence_may_wait() -> None:
    calls: Sequence[SkillCall] = _plan("turn_to", "craft", "collect_dropped").calls
    step_seconds = DEFAULT_STEP_TIMEOUT_NS / 1_000_000_000

    assert sequence_lease_seconds(calls, step_seconds) == 3 * (step_seconds + STEP_LEASE_HEADROOM_S)
    # An empty plan needs no window of its own; a caller that leases on this one
    # gets the look-only default rather than a zero-length authorisation.
    assert sequence_lease_seconds((), step_seconds) == 0.0


def test_the_sequence_stops_at_the_first_step_the_world_did_not_confirm() -> None:
    sender = _RecordingSender()
    skills = _TapeSkills(
        {
            "turn_to": _outcome(ActionResultClass.CONFIRMED),
            "craft": _outcome(ActionResultClass.UNKNOWN),
        },
        sender,
    )

    sequence = asyncio.run(
        run_skill_plan(
            skills,
            _plan("turn_to", "craft", "turn_to"),
            authority=AUTHORITY,
            timeout_ns=DEFAULT_STEP_TIMEOUT_NS,
        )
    )

    assert skills.ran == ["turn_to", "craft"]
    assert [step.name for step in sequence.steps] == ["turn_to", "craft"]
    assert sequence.stopped_at == "craft"
    document = sequence.as_document()
    assert document["confirmed"] == 1
    # The words a step concluded with are on the document with the step, so the
    # operator reads the reason rather than inferring it from a missing row.
    steps = cast("list[Mapping[str, object]]", document["steps"])
    assert steps[1]["reason"] == ""
    assert steps[1]["result"] == "UNKNOWN"


def test_a_plan_that_confirms_every_step_has_no_stop_marker() -> None:
    skills = _TapeSkills(
        {
            "turn_to": _outcome(ActionResultClass.CONFIRMED),
            "break_seen_block": _outcome(ActionResultClass.CONFIRMED),
            "craft": _outcome(ActionResultClass.CONFIRMED),
        },
        _RecordingSender(),
    )

    sequence = asyncio.run(
        run_skill_plan(
            skills,
            _plan("turn_to", "break_seen_block", "craft"),
            authority=AUTHORITY,
            timeout_ns=DEFAULT_STEP_TIMEOUT_NS,
        )
    )

    assert sequence.stopped_at == ""
    assert len(sequence.steps) == 3


def test_a_call_this_build_cannot_express_is_refused_before_the_wire() -> None:
    sender = _RecordingSender()
    skills = WorldSkills(
        sender=sender, observations=WorldObservationStore(), capabilities=frozenset()
    )

    unknown = asyncio.run(
        perform_skill(
            skills,
            SkillCall(name="mine_everything"),
            authority=AUTHORITY,
            timeout_ns=DEFAULT_STEP_TIMEOUT_NS,
        )
    )
    missing = asyncio.run(
        perform_skill(
            skills,
            SkillCall(name="craft", recipe_id="r", product_id="p"),
            authority=AUTHORITY,
            timeout_ns=DEFAULT_STEP_TIMEOUT_NS,
        )
    )

    assert (unknown.result, unknown.reason) == (ActionResultClass.FAILED, SKILL_UNKNOWN)
    assert (missing.result, missing.reason) == (
        ActionResultClass.FAILED,
        SKILL_ARGUMENT_MISSING,
    )
    assert missing.details["missing"] == "materials"
    assert sender.sent == []


def test_the_committed_example_plans_all_parse_and_ask_for_no_more_than_they_name() -> None:
    documents = sorted(EXAMPLES.glob("skill-plan-*.json"))

    assert documents, "an example plan is the entry point the README promises"
    for path in documents:
        plan = parse_skill_plan(json.loads(path.read_text(encoding="utf-8")), source=path.name)
        assert plan.calls
        assert plan.source == path.name
        # Every step's arguments are present, and the capabilities are only ever
        # the ones the named skills carry — a plan cannot ask for a door it did not
        # name a skill to open.
        assert plan.capabilities <= frozenset(
            {
                AIM_CAPABILITY,
                MINE_CAPABILITY,
                MOVE_CAPABILITY,
                SCREEN_CAPABILITY,
                GUI_CAPABILITY,
                HOTBAR_CAPABILITY,
            }
        )
