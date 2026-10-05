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
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final, cast

import pytest
from google.protobuf.message import Message

from minekin_core.application.skill_plan import (
    CLIENT_EXITED,
    SKILL_ARGUMENT_MISSING,
    SKILL_UNKNOWN,
    STEP_LEASE_HEADROOM_S,
    SkillCall,
    SkillPlan,
    SkillPlanError,
    SkillStep,
    parse_skill_plan,
    perform_skill,
    run_skill_plan,
    sequence_lease_seconds,
)
from minekin_core.application.world_observation import WorldObservationStore
from minekin_core.application.world_skills import (
    DEFAULT_STEP_TIMEOUT_NS,
    ActionAuthority,
    ClientProcessExited,
    WorldSkills,
)
from minekin_core.domain.control_vocabulary import (
    AIM_CAPABILITY,
    GUI_CAPABILITY,
    HOTBAR_CAPABILITY,
    MINE_CAPABILITY,
    MOVE_CAPABILITY,
    RESPAWN_CAPABILITY,
    SCREEN_CAPABILITY,
    USE_CAPABILITY,
)
from minekin_core.domain.recipe_catalog import CRAFT_GRID_TOO_SMALL, CRAFT_RECIPE_UNAVAILABLE
from minekin_core.domain.world_actions import ActionResultClass, SkillOutcome

EXAMPLES: Final = Path(__file__).resolve().parents[2] / "examples"
AUTHORITY: Final = ActionAuthority(
    lease_id="lease-1", generation=3, deadline_monotonic_ns=DEFAULT_STEP_TIMEOUT_NS * 2
)

#: Item ids the product-only plan tests ask the catalog about. The values are the game's, and
#: the tests below name them rather than spelling them out so a change to the catalog shows up
#: as a refused plan instead of a passing test about a renamed item.
LOG: Final = "minecraft:oak_log"
PLANKS: Final = "minecraft:oak_planks"
STICK: Final = "minecraft:stick"
TABLE: Final = "minecraft:crafting_table"
PICKAXE: Final = "minecraft:wooden_pickaxe"


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

    def __init__(
        self,
        outcomes: Mapping[str, SkillOutcome],
        sender: _RecordingSender,
        client_exit: Callable[[], int | None] = lambda: None,
    ) -> None:
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
                    USE_CAPABILITY,
                }
            ),
            client_exit=client_exit,
        )
        self._outcomes = outcomes
        self.ran: list[str] = []
        self.craft_alls: list[bool] = []

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
        craft_all: bool = True,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del recipe_id, materials, product_id, authority, timeout_ns
        self.craft_alls.append(craft_all)
        return await self._answer("craft")

    async def craft_take_result(
        self,
        *,
        recipe_id: str,
        materials: Mapping[str, int],
        product_id: str,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del recipe_id, materials, product_id, authority, timeout_ns
        return await self._answer("craft_take_result")

    async def close_screen(
        self,
        *,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, timeout_ns
        return await self._answer("close_screen")

    async def use_target(
        self,
        *,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del authority, timeout_ns
        return await self._answer("use_target")

    async def consume_item(
        self,
        *,
        item_id: str,
        authority: ActionAuthority,
        timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS,
    ) -> SkillOutcome:
        del item_id, authority, timeout_ns
        return await self._answer("consume_item")


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
    "consume_item": {"item_id": "minecraft:apple"},
    "craft": {
        "recipe_id": "minecraft:oak_planks",
        "materials": {"minecraft:oak_log": 1},
        "product_id": "minecraft:oak_planks",
    },
    "craft_take_result": {
        "recipe_id": "minecraft:oak_planks",
        "materials": {"minecraft:oak_log": 1},
        "product_id": "minecraft:oak_planks",
    },
    "close_screen": {},
    "use_target": {},
    "select_hotbar": {"slot": 0},
}


def test_a_plan_is_read_in_order_with_typed_arguments() -> None:
    plan = _plan("turn_to", "craft", "select_hotbar")

    assert [call.name for call in plan.calls] == ["turn_to", "craft", "select_hotbar"]
    assert plan.calls[1].materials == (("minecraft:oak_log", 1),)
    assert plan.calls[2].slot == 0
    assert len(plan) == 3


def test_a_plan_can_name_which_craft_transaction_and_the_skill_receives_it() -> None:
    """A plan is the only place an author says which of the two recipe clicks they want,
    so the word has to survive both the reading and the dispatch. The plain click leaves
    the result on the cursor rather than in the synced inventory, which is why the choice
    is a plan argument and not something the skill layer infers."""

    def craft_entry(**extra: object) -> dict[str, object]:
        return {
            "skill": "craft",
            "recipe_id": "minecraft:oak_planks",
            "materials": {"minecraft:oak_log": 1},
            "product_id": "minecraft:oak_planks",
            **extra,
        }

    plan = parse_skill_plan(
        {"schema_version": 1, "skills": [craft_entry(), craft_entry(craft_all=False)]},
        source="test",
    )

    assert [call.craft_all for call in plan.calls] == [True, False]

    skills = _TapeSkills({"craft": _outcome(ActionResultClass.CONFIRMED)}, _RecordingSender())
    asyncio.run(
        run_skill_plan(skills, plan, authority=AUTHORITY, timeout_ns=DEFAULT_STEP_TIMEOUT_NS)
    )
    assert skills.craft_alls == [True, False]


def test_a_plan_can_name_the_take_result_craft_and_the_skill_receives_it() -> None:
    plan = _plan("craft_take_result")
    skills = _TapeSkills(
        {"craft_take_result": _outcome(ActionResultClass.CONFIRMED)}, _RecordingSender()
    )
    asyncio.run(
        run_skill_plan(skills, plan, authority=AUTHORITY, timeout_ns=DEFAULT_STEP_TIMEOUT_NS)
    )

    assert skills.ran == ["craft_take_result"]


def test_a_craft_all_on_the_take_result_craft_is_refused_by_name() -> None:
    """The take-result transaction does not choose between the two recipe clicks:
    it is the click that fills the grid followed by the one that takes the result.
    A plan that still writes `craft_all` is agreeing to a sentence this skill
    cannot say, so it is refused instead of being quietly ignored."""

    entry: dict[str, object] = {"skill": "craft_take_result", **_ARGUMENTS["craft_take_result"]}
    entry["craft_all"] = True

    with pytest.raises(SkillPlanError, match="craft_all"):
        parse_skill_plan({"schema_version": 1, "skills": [entry]}, source="test")


# ----------------------------------------------------------------------- a craft named by product


def test_a_craft_entry_named_only_by_product_carries_the_catalog_recipe() -> None:
    """The parameterised spelling of a craft: the plan says which item the Kin wants to hold
    afterwards, and the recipe id, the ingredients and their counts come from the catalog. A
    plan author who does not know Minecraft cannot be wrong about Minecraft."""

    plan = parse_skill_plan(
        {"schema_version": 1, "skills": [{"skill": "craft_take_result", "product": STICK}]},
        source="test",
    )

    call = plan.calls[0]
    assert (call.name, call.recipe_id, call.product_id) == (
        "craft_take_result",
        STICK,
        STICK,
    )
    assert call.materials == ((PLANKS, 2),)


def test_a_product_only_entry_reaches_the_skill_with_the_resolved_arguments() -> None:
    """Resolution is a parse-time act, so the dispatch that follows needs no knowledge of it:
    the call it hands over is the same shape an explicit trio would have produced."""

    plan = parse_skill_plan(
        {"schema_version": 1, "skills": [{"skill": "craft", "product": TABLE}]},
        source="test",
    )
    skills = _TapeSkills({"craft": _outcome(ActionResultClass.CONFIRMED)}, _RecordingSender())

    asyncio.run(
        run_skill_plan(skills, plan, authority=AUTHORITY, timeout_ns=DEFAULT_STEP_TIMEOUT_NS)
    )

    assert skills.ran == ["craft"]


def test_a_product_the_catalog_does_not_have_refuses_the_plan_by_name() -> None:
    entry: dict[str, object] = {"skill": "craft", "product": "minecraft:diamond_pickaxe"}

    with pytest.raises(SkillPlanError, match=CRAFT_RECIPE_UNAVAILABLE):
        parse_skill_plan({"schema_version": 1, "skills": [entry]}, source="test")


def test_a_product_needing_more_grid_than_the_inventory_screen_opens_refuses_by_name() -> None:
    """`craft_take_result` opens the inventory, whose grid is two by two. A plan asking for a
    three-by-three shape through it is refused here, in words, rather than sent into a world
    that will not answer."""

    entry: dict[str, object] = {"skill": "craft_take_result", "product": PICKAXE}

    with pytest.raises(SkillPlanError, match=CRAFT_GRID_TOO_SMALL):
        parse_skill_plan({"schema_version": 1, "skills": [entry]}, source="test")


def test_a_product_entry_that_also_spells_its_own_recipe_is_refused() -> None:
    """Two sources of one game fact is the mistake, even when they happen to agree: the entry
    says which it means by naming only the product, and a redundant trio is refused rather
    than silently preferred."""

    entry: dict[str, object] = {"skill": "craft", "product": STICK, "materials": {PLANKS: 2}}

    with pytest.raises(SkillPlanError, match="materials"):
        parse_skill_plan({"schema_version": 1, "skills": [entry]}, source="test")


def test_a_product_key_on_a_skill_that_crafts_nothing_is_refused_as_an_unknown_key() -> None:
    entry: dict[str, object] = {"skill": "collect_dropped", "item_id": LOG, "product": STICK}

    with pytest.raises(SkillPlanError, match="product"):
        parse_skill_plan({"schema_version": 1, "skills": [entry]}, source="test")


def test_a_product_that_is_not_a_string_is_refused_as_the_argument_it_is() -> None:
    entry: dict[str, object] = {"skill": "craft", "product": 4}

    with pytest.raises(SkillPlanError, match="product"):
        parse_skill_plan({"schema_version": 1, "skills": [entry]}, source="test")


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
    (
        {
            "schema_version": 1,
            "skills": [
                {
                    "skill": "craft",
                    "recipe_id": "r",
                    "product_id": "p",
                    "materials": {"minecraft:oak_log": 1},
                    "craft_all": "false",
                }
            ],
        },
        "needs craft_all to be true or false",
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
    # Leaving the window is not a click, so it asks for less than the craft that
    # opened it, and a plan ending in the close gets a lease that says so.
    assert _plan("close_screen").capabilities == frozenset({SCREEN_CAPABILITY})
    # A use is the right-click primitive the baseline Bridge already negotiates, so
    # it asks for the use capability alone — not the screen or gui a craft needs.
    assert _plan("use_target").capabilities == frozenset({USE_CAPABILITY})
    assert _plan("craft_take_result", "close_screen").capabilities == frozenset(
        {SCREEN_CAPABILITY, GUI_CAPABILITY}
    )
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


def test_the_close_is_a_plan_step_of_its_own_and_runs_after_the_craft() -> None:
    """A plan is the only place an author says the chain ends by leaving the
    window, and the step has no arguments of its own — the world says which
    window, if any, is standing."""

    skills = _TapeSkills(
        {
            "craft_take_result": _outcome(ActionResultClass.CONFIRMED),
            "close_screen": _outcome(ActionResultClass.CONFIRMED),
        },
        _RecordingSender(),
    )

    sequence = asyncio.run(
        run_skill_plan(
            skills,
            _plan("craft_take_result", "close_screen"),
            authority=AUTHORITY,
            timeout_ns=DEFAULT_STEP_TIMEOUT_NS,
        )
    )

    assert skills.ran == ["craft_take_result", "close_screen"]
    assert sequence.stopped_at == ""


def test_a_use_step_routes_to_the_use_skill() -> None:
    """A plan step named `use_target` dispatches to the skill of that name and to
    nothing else — the right-click is its own step, not an argument some other
    skill happens to carry."""

    skills = _TapeSkills(
        {"use_target": _outcome(ActionResultClass.CONFIRMED)},
        _RecordingSender(),
    )

    sequence = asyncio.run(
        run_skill_plan(
            skills,
            _plan("use_target"),
            authority=AUTHORITY,
            timeout_ns=DEFAULT_STEP_TIMEOUT_NS,
        )
    )

    assert skills.ran == ["use_target"]
    assert sequence.stopped_at == ""


def test_a_consume_step_routes_to_the_consume_skill() -> None:
    """A plan step named `consume_item` dispatches to the eating skill — a meal is
    its own step that names the item, not a flag some other skill carries."""

    skills = _TapeSkills(
        {"consume_item": _outcome(ActionResultClass.CONFIRMED)},
        _RecordingSender(),
    )

    sequence = asyncio.run(
        run_skill_plan(
            skills,
            _plan("consume_item"),
            authority=AUTHORITY,
            timeout_ns=DEFAULT_STEP_TIMEOUT_NS,
        )
    )

    assert skills.ran == ["consume_item"]
    assert sequence.stopped_at == ""


def test_a_meal_with_no_item_named_is_refused_as_the_missing_argument() -> None:
    sender = _RecordingSender()
    skills = WorldSkills(
        sender=sender, observations=WorldObservationStore(), capabilities=frozenset()
    )

    missing = asyncio.run(
        perform_skill(
            skills,
            SkillCall(name="consume_item"),
            authority=AUTHORITY,
            timeout_ns=DEFAULT_STEP_TIMEOUT_NS,
        )
    )

    assert (missing.result, missing.reason) == (ActionResultClass.FAILED, SKILL_ARGUMENT_MISSING)
    assert missing.details["missing"] == "item_id"
    assert sender.sent == []


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


def test_the_committed_product_only_plan_resolves_to_the_catalog_recipes() -> None:
    """The example an operator is pointed at for the parameterised spelling is checked against
    the catalog it reads, so a plan that promises "just name the product" cannot silently
    drift from the recipes the build actually knows."""

    path = EXAMPLES / "skill-plan-craft-by-product.json"

    plan = parse_skill_plan(json.loads(path.read_text(encoding="utf-8")), source=path.name)

    crafts = [call for call in plan.calls if call.name == "craft_take_result"]
    assert [call.product_id for call in crafts] == [PLANKS, TABLE]
    assert [call.recipe_id for call in crafts] == [PLANKS, TABLE]
    assert [call.materials for call in crafts] == [((LOG, 1),), ((PLANKS, 4),)]


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
                RESPAWN_CAPABILITY,
                SCREEN_CAPABILITY,
                GUI_CAPABILITY,
                HOTBAR_CAPABILITY,
                USE_CAPABILITY,
            }
        )


# ----------------------------------------------------------------------- the client's own exit


GONE_ACTION_ID = "a" * 32


class _ClientGoneTape(_TapeSkills):
    """A tape whose client dies while a step is waiting, as the wait reports it."""

    async def close_screen(
        self, *, authority: ActionAuthority, timeout_ns: int = DEFAULT_STEP_TIMEOUT_NS
    ) -> SkillOutcome:
        del authority, timeout_ns
        self.ran.append("close_screen")
        raise ClientProcessExited(143, action_id=GONE_ACTION_ID)


def test_a_step_is_refused_by_name_when_the_client_is_already_gone() -> None:
    """A dead client is a precondition, not a timeout.

    The plan's own argument refusals come first, because those are mistakes in the
    document; once the call is expressible, the one thing that can settle it is a
    reading, and a JVM the operating system has already finished makes none.
    """

    async def scenario() -> None:
        sender = _RecordingSender()
        skills = _TapeSkills({}, sender, client_exit=lambda: 1)

        outcome = await perform_skill(
            skills, _plan("close_screen").calls[0], authority=AUTHORITY, timeout_ns=1
        )

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == CLIENT_EXITED
        assert outcome.details["exit_code"] == "1"
        # Empty here on purpose, and the other test asks for the opposite: nothing
        # was sent, so there is no ask in flight to name.
        assert outcome.action_id == ""
        assert skills.ran == []
        assert sender.sent == []

    asyncio.run(scenario())


def test_a_step_names_the_client_that_went_while_it_was_waiting() -> None:
    async def scenario() -> None:
        skills = _ClientGoneTape(
            {"close_screen": _outcome(ActionResultClass.CONFIRMED)}, _RecordingSender()
        )

        outcome = await perform_skill(
            skills, _plan("close_screen").calls[0], authority=AUTHORITY, timeout_ns=1
        )

        assert outcome.result is ActionResultClass.UNKNOWN
        assert outcome.reason == CLIENT_EXITED
        assert outcome.details["exit_code"] == "143"
        # The ask went out under this id and the client may have acted on it before it
        # died; the row that names the exit without it loses the one command this run
        # can still point at.
        assert outcome.action_id == GONE_ACTION_ID
        assert skills.ran == ["close_screen"]

    asyncio.run(scenario())


def test_a_plan_stops_at_the_step_that_lost_its_client() -> None:
    """No later step can be settled either, so the sequence ends where the process did."""

    async def scenario() -> None:
        skills = _ClientGoneTape(
            {"craft": _outcome(ActionResultClass.CONFIRMED)}, _RecordingSender()
        )
        steps: list[SkillStep] = []

        async def record(step: SkillStep) -> None:
            steps.append(step)

        sequence = await run_skill_plan(
            skills,
            _plan("craft", "close_screen", "craft"),
            authority=AUTHORITY,
            timeout_ns=1,
            on_step=record,
        )

        assert [step.name for step in steps] == ["craft", "close_screen"]
        assert sequence.stopped_at == "close_screen"
        assert steps[1].outcome.reason == CLIENT_EXITED

    asyncio.run(scenario())


def test_the_committed_meal_plan_is_the_two_steps_the_probe_runs() -> None:
    """The probe's plan is pinned where it ships: one turn away from whatever is in front
    (the meal's Core-side precondition needs a crosshair on nothing, and the flat world
    stacks its resource trunk three blocks ahead of the join), then the meal itself —
    named as an item id, so the step exercises select-then-eat rather than assuming a
    hand the run never checked."""

    path = EXAMPLES / "skill-plan-eat.json"

    plan = parse_skill_plan(json.loads(path.read_text(encoding="utf-8")), source=path.name)

    assert [call.name for call in plan.calls] == ["turn_to", "consume_item"]
    assert plan.calls[0].pitch_degrees == -55.0
    assert plan.calls[1].item_id == "minecraft:apple"


def test_the_respawn_example_is_one_parameterless_bounded_skill() -> None:
    from minekin_core.domain.control_vocabulary import RESPAWN_CAPABILITY
    from minekin_core.domain.world_actions import skill_capabilities

    plan = parse_skill_plan(json.loads((EXAMPLES / "skill-plan-respawn.json").read_bytes()))
    assert len(plan.calls) == 1
    assert plan.calls[0].name == "respawn"
    assert skill_capabilities("respawn") == frozenset({RESPAWN_CAPABILITY})


def test_dispatch_maps_a_retreat_call_onto_the_retreat_skill() -> None:
    """The name the mind emits is the name the dispatcher must route -- not whichever branch
    happens to fall last. Shipping retreat without this branch crashed a live run with
    INTERNAL_INVARIANT: the call fell through to `select_hotbar` with no slot. The fake
    refuses every attribute but `retreat`, so any other route fails the test by name."""

    import asyncio

    from minekin_core.application import skill_plan as skill_plan_module
    from minekin_core.application.skill_plan import SkillCall
    from minekin_core.application.world_skills import ActionAuthority
    from minekin_core.domain.ids import OpaqueId

    class OnlyRetreat:
        def __init__(self) -> None:
            self.seen: tuple[object, int] | None = None

        async def retreat(self, *, authority: object, timeout_ns: int) -> str:
            self.seen = (authority, timeout_ns)
            return "outcome"

        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"dispatch reached an unexpected skill: {name}")

    authority = ActionAuthority(
        lease_id=OpaqueId.new().value,
        generation=1,
        deadline_monotonic_ns=1_000_000_000,
    )
    skills = OnlyRetreat()
    outcome = asyncio.run(
        skill_plan_module._dispatch(
            skills,  # type: ignore[arg-type]
            SkillCall(name="retreat"),
            authority=authority,
            timeout_ns=5_000_000_000,
        )
    )
    assert outcome == "outcome"
    assert skills.seen == (authority, 5_000_000_000)
