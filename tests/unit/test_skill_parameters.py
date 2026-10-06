"""What an argument means, what a legal value is, and the word for an answer that isn't.

`docs/s3-minimal-player-mind.md` §2 gives the model a choice of *behavior and parameters* and
keeps every consequence on this side. That only holds if the parameter half is decided as data, in
one place, before a call is built — which is what this table is. So these cells test the table
rather than a caller: the spellings, the kinds, the bounds, and the three words that name a refusal.

Two properties are worth stating because the whole interface leans on them:

**Nothing is defaulted here.** A value the answerer did not state is not this module's to invent —
it comes from the reading, at the one place that builds the call, so a run document can tell "the
answer said one" from "nobody said".

**A behavior nobody declared cannot be argued with.** An empty ask is honoured, because there is
nothing this side would have to know to run it; a non-empty one is refused, because the answerer has
claimed a parameter nobody stated. The alternative — silently accepting `{"hurry": true}` for a
skill that does not know the word — is how a remote answer starts meaning things the local layer
never agreed to.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from minekin_core.domain.model_access import UnavailableReason
from minekin_core.domain.skill_parameters import (
    BEHAVIOR_PARAMETERS,
    MAX_QUANTITY,
    MAX_SAY_CHARS,
    MODEL_ARGUMENTS_INVALID,
    MODEL_ARGUMENTS_MISSING,
    MODEL_ARGUMENTS_UNKNOWN,
    ParameterKind,
    is_item_id,
    parameters_for,
    text_parameter_names,
    validate_arguments,
)
from minekin_core.domain.world_actions import SKILL_CAPABILITIES

PLANKS = "minecraft:oak_planks"


# ------------------------------------------------------------------- the table and what it covers


def test_every_skill_this_build_has_declares_the_arguments_it_takes() -> None:
    """The parameter table and the capability table must cover the same eight names.

    A skill added to one and not the other is the failure this catches: an offered behavior whose
    parameters nobody stated can only ever be answered with an empty ask, which reads as a model
    that will not fill anything in rather than as a missing row.
    """

    assert set(BEHAVIOR_PARAMETERS) == set(SKILL_CAPABILITIES)


def test_an_offered_craft_ask_asks_for_a_product_and_nothing_it_could_get_wrong() -> None:
    """The offer's shape is the answerer's only handle on what to fill in, so `craft` must say the
    product is required and the quantity is a bounded number of items."""

    offer = parameters_for(["craft_take_result"])

    assert list(offer) == ["craft_take_result"]
    fields = {row["name"]: row for row in offer["craft_take_result"]}
    assert fields["target_item"] == {
        "name": "target_item",
        "kind": "item_id",
        "required": True,
    }
    assert fields["quantity"] == {
        "name": "quantity",
        "kind": "quantity",
        "required": False,
        "minimum": 1,
        "maximum": MAX_QUANTITY,
    }


def test_a_behavior_the_offer_does_not_name_is_not_shown_at_all() -> None:
    """`parameters_for` is restricted to the behaviors that were offered, exactly as the skill list
    is. A declaration the answerer was never offered a choice about is not information, it is a
    hint toward a skill this reading cannot run."""

    offer = parameters_for(["turn_to", "collect_dropped", "fly_to_the_moon"])

    assert set(offer) == {"turn_to", "collect_dropped"}


def test_an_empty_declaration_is_offered_as_an_empty_list() -> None:
    assert parameters_for(["close_screen"]) == {"close_screen": []}


# ------------------------------------------------------------------------- the spellings of an item


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (PLANKS, True),
        ("minecraft:wooden_pickaxe", True),
        ("minekin:custom_thing", True),
        ("minecraft:oak log", False),
        ("minecraft:Wooden_Pickaxe", False),
        ("Wooden Pickaxe", False),
        ("oak_planks", False),
        ("minecraft:", False),
        (":oak_planks", False),
        ("", False),
        (1, False),
        (None, False),
    ],
)
def test_an_item_id_is_the_games_spelling_or_it_is_not_one(value: object, expected: bool) -> None:
    """`Wooden Pickaxe` is not a near miss to be normalised: the value is a lookup key into curated
    knowledge, and a name that has to be guessed at is a name nothing downstream can honour."""

    assert is_item_id(value) is expected


# --------------------------------------------------------------------------- kinds, bounds, numbers


@pytest.mark.parametrize(
    ("skill", "arguments", "expected"),
    [
        ("craft", {"target_item": PLANKS, "quantity": 1}, None),
        ("craft", {"target_item": PLANKS, "quantity": MAX_QUANTITY}, None),
        ("craft", {"target_item": PLANKS, "quantity": 0}, MODEL_ARGUMENTS_INVALID),
        ("craft", {"target_item": PLANKS, "quantity": -1}, MODEL_ARGUMENTS_INVALID),
        ("craft", {"target_item": PLANKS, "quantity": MAX_QUANTITY + 1}, MODEL_ARGUMENTS_INVALID),
        ("craft", {"target_item": PLANKS, "quantity": True}, MODEL_ARGUMENTS_INVALID),
        ("craft", {"target_item": PLANKS, "quantity": 1.0}, None),
        ("craft", {"target_item": PLANKS, "quantity": "1"}, MODEL_ARGUMENTS_INVALID),
        ("craft", {"target_item": PLANKS, "craft_all": True}, None),
        ("craft", {"target_item": PLANKS, "craft_all": 1}, MODEL_ARGUMENTS_INVALID),
        ("craft", {"target_item": PLANKS, "craft_all": "yes"}, MODEL_ARGUMENTS_INVALID),
        ("select_hotbar", {"slot": 0}, None),
        ("select_hotbar", {"slot": 8}, None),
        ("select_hotbar", {"slot": 9}, MODEL_ARGUMENTS_INVALID),
        ("select_hotbar", {"slot": -1}, MODEL_ARGUMENTS_INVALID),
        # The slot is the choice: an answer that leaves it out is missing, not defaulted.
        ("select_hotbar", {}, MODEL_ARGUMENTS_MISSING),
        ("select_hotbar", {"expected_item_id": PLANKS}, MODEL_ARGUMENTS_MISSING),
        ("turn_to", {"yaw_degrees": -180.0, "pitch_degrees": 90.0}, None),
        ("turn_to", {"yaw_degrees": 181.5}, MODEL_ARGUMENTS_INVALID),
        ("turn_to", {"pitch_degrees": -91.0}, MODEL_ARGUMENTS_INVALID),
        ("collect_dropped", {"walk_seconds": 0.1}, None),
        ("collect_dropped", {"walk_seconds": 0.0}, MODEL_ARGUMENTS_INVALID),
        ("collect_dropped", {"walk_seconds": 31.0}, MODEL_ARGUMENTS_INVALID),
        ("break_seen_block", {"expected_drop_item": "minecraft:diamond"}, None),
    ],
)
def test_a_value_is_a_value_of_the_kind_the_argument_declares(
    skill: str, arguments: Mapping[str, object], expected: str | None
) -> None:
    """The nine hotbar slots, one stack's worth of items, the half-turn and the vertical limit:
    every bound is the game's own, restated here so that an answer outside it is refused by name
    instead of being clicked and then explained away by a later reading.

    `True` is rejected for a quantity because a boolean is not a number of items whatever Python
    says it is, and `2.5` because that is not a thing to ask for — while a JSON `1.0` is a whole
    number of items and is honoured as the answer said it, narrowed to an int by whoever builds the
    call.
    """

    honoured = validate_arguments(skill, arguments)

    if expected is None:
        assert honoured == arguments
    else:
        assert honoured == expected


def test_a_craft_ask_without_a_product_is_missing_not_defaulted() -> None:
    """There is no safe default product. With one, an answerer that says nothing gets a craft of
    whatever the table happened to put first, and the run reads as a decision nobody made."""

    assert validate_arguments("craft", {}) is MODEL_ARGUMENTS_MISSING
    assert validate_arguments("craft_take_result", {"quantity": 4}) is MODEL_ARGUMENTS_MISSING


def test_an_argument_nobody_declared_is_refused_rather_than_dropped() -> None:
    """A key the behavior does not take is an answer about a different behavior. Silently ignoring
    it would honour the part the answerer got right and lose the fact that it was wrong."""

    assert (
        validate_arguments("craft_take_result", {"target_item": PLANKS, "hurry": True})
        is MODEL_ARGUMENTS_UNKNOWN
    )


@pytest.mark.parametrize("skill", ["chop_tree", "fly_to_the_moon", "wait"])
def test_a_behavior_with_no_declaration_is_judged_only_on_whether_it_was_given_anything(
    skill: str,
) -> None:
    """The rule, stated rather than left to chance: an empty ask for a behavior nobody declared is
    honoured, and a non-empty one is refused. Skill names themselves are bounded by the offer, not
    by this table — which is why the second half matters."""

    assert validate_arguments(skill, {}) == {}
    assert validate_arguments(skill, {"target_item": PLANKS}) is MODEL_ARGUMENTS_UNKNOWN


def test_the_honoured_arguments_are_the_ones_that_were_given() -> None:
    """Nothing added, nothing dropped, nothing rewritten: a successful check returns the same keys
    it was handed, so a caller can tell a stated value from an implied one."""

    given = {"target_item": PLANKS, "quantity": 4}
    honoured = validate_arguments("craft", given)

    assert isinstance(honoured, Mapping)
    assert dict(honoured) == given
    assert "craft_all" not in honoured


def test_every_refusal_word_is_a_reason_the_port_can_file() -> None:
    """`UnavailableReason` and these tokens are the same words in two modules. The provider turns
    the string this side returned straight into the enum value the ledger records, so a token that
    is not a reason would raise at the moment a run is reporting a refusal."""

    for token in (
        MODEL_ARGUMENTS_UNKNOWN,
        MODEL_ARGUMENTS_MISSING,
        MODEL_ARGUMENTS_INVALID,
    ):
        assert UnavailableReason(token).value == token


def test_the_kinds_are_the_ones_the_table_uses() -> None:
    """A kind that no parameter declares is a kind no check was written for, and the check is the
    only thing standing between an answerer's JSON and a click."""

    used = {
        parameter.kind for parameters in BEHAVIOR_PARAMETERS.values() for parameter in parameters
    }
    assert used == set(ParameterKind)


# --------------------------------------------------------------------------- the one text kind


def test_say_declares_the_one_free_text_argument_and_its_cap() -> None:
    declared = BEHAVIOR_PARAMETERS["say"]

    assert [parameter.name for parameter in declared] == ["text"]
    assert declared[0].kind is ParameterKind.TEXT
    assert declared[0].required is True
    assert declared[0].maximum == MAX_SAY_CHARS


def test_a_well_shaped_line_is_honoured_verbatim() -> None:
    # Taken as spoken: nothing here trims, rewrites or completes the words.
    assert validate_arguments("say", {"text": "  hello there  "}) == {"text": "  hello there  "}


def test_a_line_that_is_not_speech_is_refused_by_the_arguments_gate() -> None:
    """Blank is nothing said, a leading slash is a command the server would execute,
    and past the cap the line is refused rather than clipped — the words are the Kin's
    to mean (the assertion is parametrised over the strings below for that reason)."""

    for text in ("", "   ", "x" * (MAX_SAY_CHARS + 1), "/kill", "  /tp 0 0", 12):
        assert validate_arguments("say", {"text": text}) == MODEL_ARGUMENTS_INVALID, text


def test_the_cap_is_a_boundary_not_a_margin() -> None:
    at_cap = "x" * MAX_SAY_CHARS
    assert validate_arguments("say", {"text": at_cap}) == {"text": at_cap}


def test_say_takes_no_other_key() -> None:
    assert (
        validate_arguments("say", {"text": "hello", "target_item": "minecraft:stick"})
        == MODEL_ARGUMENTS_UNKNOWN
    )


def test_text_is_the_only_kind_whose_values_leave_toward_people() -> None:
    """`text_parameter_names` is what the secret rule hangs off, so the set it names
    has to be exactly the free-text arguments — a kind added later without a caller
    is fine; a text argument that this helper misses would be words sent unredacted."""

    assert text_parameter_names("say") == ("text",)
    assert text_parameter_names("craft") == ()
    assert text_parameter_names("not_a_skill") == ()
