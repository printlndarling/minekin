"""Which arguments a behavior takes, what each one may be, and the words for an answer that isn't.

This is where the parameter half of a decision is decided, once, as data. A remote answerer may
name a behavior and fill in its arguments; it may not say what an argument means, what a legal
value is, which recipe a product stands for, whether the world can pay for it, how the GUI is
clicked, or whether the craft happened. All six of those belong to this side: the kinds and
bounds are here, the recipe comes from `recipe_catalog`, the precondition is read from the
inventory in the same call, the clicks are `application.world_skills`, and the verdict comes from
a later reading. A model that invents an item id gets a named refusal rather than a click.

Two vocabularies name the same behaviors, and the split is deliberate:

* **The ask vocabulary** — this module — is what a decision answerer is offered and asked to
  fill in. It is written in terms of what the asker means (`target_item` for the product it wants
  to end up holding), and it carries defaults only where this side can supply the value itself.
* **The plan-document vocabulary** — `application.skill_plan` — is evidence of what an operator
  wrote down (`product`, `recipe_id`, `materials`), and a committed plan is read, not rewritten.

`PlayerMind._call_for` is the one place where an ask becomes a call, so a parameter never has two
readers that could disagree about it.

The refusal words here are for a remote answer that cannot be honoured. They are not the
plan-document tokens: a plan that cannot be read is `SkillPlanError` raised at parse time, while
an answer that cannot be honoured leaves the Kin playing on its local reflection and is filed in
the cost ledger. Different things happened, and the run document says which.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from minekin_core.domain.perception import MAX_STACK_COUNT

#: The largest craft ask one intent may be for. Bounded by a stack, because the ask is a number
#: of items and the world's own count of one item in one slot is what caps it.
MAX_QUANTITY: Final = MAX_STACK_COUNT

#: The nine hotbar slots, and the reason `slot` is bounded rather than free: a call outside them
#: is refused by the contract's own `HOTBAR_SLOT_OUT_OF_RANGE` downstream, and an answerer that
#: never sees the bound has no reason to stay inside it.
HOTBAR_SLOT_COUNT: Final = 9

#: One item id, as the game writes it: a lowercase namespace, a colon, a lowercase path. Kept
#: strict because the value is a lookup key into curated knowledge — an answer of `Wooden
#: Pickaxe` is not a near miss to be normalised, it is an item nobody has a recipe for.
_ITEM_ID_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*$")

#: The answer cannot be honoured as written: it names an argument the behavior does not take.
MODEL_ARGUMENTS_UNKNOWN: Final = "MODEL_ARGUMENTS_UNKNOWN"
#: The answer cannot be honoured: an argument the behavior cannot run without is absent.
MODEL_ARGUMENTS_MISSING: Final = "MODEL_ARGUMENTS_MISSING"
#: The answer cannot be honoured: an argument is there but is not a value of the right kind or
#: inside the range the behavior means.
MODEL_ARGUMENTS_INVALID: Final = "MODEL_ARGUMENTS_INVALID"


def is_item_id(value: object) -> bool:
    """Whether a value is spelled like one of the game's item ids.

    Public because the same question is asked of a value that never came from an answerer: an
    operator's `MINEKIN_GOAL_PRODUCT` is a lookup key in exactly the same way, and a typo in it
    is worth naming at the moment it is read rather than as an uncurated recipe much later.
    """

    return isinstance(value, str) and _ITEM_ID_PATTERN.fullmatch(value) is not None


class ParameterKind(StrEnum):
    """The kinds an argument may be, and the only ones a check is written against."""

    ITEM_ID = "item_id"
    QUANTITY = "quantity"
    SLOT = "slot"
    ANGLE = "angle"
    SECONDS = "seconds"
    FLAG = "flag"


@dataclass(frozen=True, slots=True)
class Parameter:
    """One argument of one behavior: its kind, whether it must be given, and its bounds."""

    name: str
    kind: ParameterKind
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None

    def as_offer(self) -> dict[str, object]:
        """The field set an answerer is shown for this argument.

        The kind travels as a word rather than a type because the answer comes back as JSON, and
        the answerer's only handle on "what may I put here" is this list.
        """

        offer: dict[str, object] = {
            "name": self.name,
            "kind": self.kind.value,
            "required": self.required,
        }
        if self.minimum is not None:
            offer["minimum"] = self.minimum
        if self.maximum is not None:
            offer["maximum"] = self.maximum
        return offer


def _item(name: str, *, required: bool = False) -> Parameter:
    return Parameter(name=name, kind=ParameterKind.ITEM_ID, required=required)


def _number(name: str, kind: ParameterKind, minimum: float, maximum: float) -> Parameter:
    return Parameter(name=name, kind=kind, minimum=minimum, maximum=maximum)


#: Every behavior this build has, with the arguments it takes. Listed for all names rather than
#: only the ones currently offered so that adding one to the offer cannot silently mean "a
#: behavior whose parameters nobody stated": an offered skill with no row here can only ever be
#: answered with an empty ask, since there is no declaration that would say what a key means.
BEHAVIOR_PARAMETERS: Final[Mapping[str, tuple[Parameter, ...]]] = MappingProxyType(
    {
        "turn_to": (
            _number("yaw_degrees", ParameterKind.ANGLE, -180.0, 180.0),
            _number("pitch_degrees", ParameterKind.ANGLE, -90.0, 90.0),
        ),
        "break_seen_block": (_item("expected_drop_item"),),
        "collect_dropped": (
            _item("item_id"),
            _number("walk_seconds", ParameterKind.SECONDS, 0.1, 30.0),
        ),
        # Eating names the meal, not the method: the ask is an item id, the curated table
        # says whether this build can act on it at all, and the reading decides the rest.
        # A model's guess about what is edible is a candidate like any other — the row in
        # the table is the boundary, and the world's next reading is the verdict.
        "consume_item": (_item("target_item", required=True),),
        "craft": (
            _item("target_item", required=True),
            _number("quantity", ParameterKind.QUANTITY, 1, MAX_QUANTITY),
            Parameter(name="craft_all", kind=ParameterKind.FLAG),
        ),
        "craft_take_result": (
            _item("target_item", required=True),
            _number("quantity", ParameterKind.QUANTITY, 1, MAX_QUANTITY),
        ),
        "close_screen": (),
        "respawn": (),
        # A retreat takes its bearing from the reading's own hostile report, exactly as
        # close_screen takes the window and use_target the aim: the answer names the behavior
        # and fills in nothing, and a reading with no visible threat refuses it by name.
        "retreat": (),
        # A use takes the aim from the reading, exactly as close_screen takes the
        # window from it — the model names the behavior and fills in nothing.
        "use_target": (),
        "select_hotbar": (
            _number("slot", ParameterKind.SLOT, 0, HOTBAR_SLOT_COUNT - 1),
            _item("expected_item_id"),
        ),
    }
)


def parameters_for(behaviors: Sequence[str]) -> dict[str, list[dict[str, object]]]:
    """The declaration an answerer is offered, restricted to the behaviors it may choose.

    A list rather than the whole table because the offer is the same boundary everywhere else in
    this surface: what the local layer did not offer, the answerer has no business asking about.
    """

    return {
        name: [parameter.as_offer() for parameter in BEHAVIOR_PARAMETERS[name]]
        for name in behaviors
        if name in BEHAVIOR_PARAMETERS
    }


def validate_arguments(
    behavior: str, arguments: Mapping[str, object]
) -> Mapping[str, object] | str:
    """The arguments this side can honour, or the name of the reason it cannot.

    On success a mapping holding exactly the keys that were given (nothing defaulted here: a
    value the answerer did not state is supplied by the reading at the one place that builds the
    call, so the run document can tell "the answer said 1" from "nobody said"). On failure one of
    the three `MODEL_ARGUMENTS_*` tokens.

    A behavior with no row here is the one case the check cannot be strict about, and the rule is
    stated rather than left to chance: an empty ask is honoured, because there is nothing this
    side would have to know in order to run it, and a non-empty one is refused, because the
    answerer has claimed a parameter nobody declared. Skill names themselves are bounded by the
    offer, not by this table.

    Integers are checked for `bool` first because `True` is an `int` in Python and a quantity of
    `true` is a different sentence than a quantity of one.
    """

    parameters = BEHAVIOR_PARAMETERS.get(behavior)
    if parameters is None:
        return {} if not arguments else MODEL_ARGUMENTS_UNKNOWN
    declared = {parameter.name: parameter for parameter in parameters}
    for key in arguments:
        if key not in declared:
            return MODEL_ARGUMENTS_UNKNOWN
    for parameter in parameters:
        if parameter.required and arguments.get(parameter.name) is None:
            return MODEL_ARGUMENTS_MISSING
    canonical: dict[str, object] = {}
    for key, value in arguments.items():
        parameter = declared[key]
        if not _fits(parameter, value):
            return MODEL_ARGUMENTS_INVALID
        canonical[key] = value
    return canonical


def _fits(parameter: Parameter, value: object) -> bool:
    """Whether one value is a value of this argument's kind, inside its bounds."""

    if parameter.kind is ParameterKind.FLAG:
        return isinstance(value, bool)
    if parameter.kind is ParameterKind.ITEM_ID:
        return isinstance(value, str) and bool(_ITEM_ID_PATTERN.fullmatch(value))
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    if parameter.kind in (ParameterKind.QUANTITY, ParameterKind.SLOT):
        # A whole number of items or a slot index: `2.5` planks is not a thing to ask for.
        return float(value).is_integer() and _within(parameter, float(value))
    return _within(parameter, float(value))


def _within(parameter: Parameter, value: float) -> bool:
    if parameter.minimum is not None and value < parameter.minimum:
        return False
    return not (parameter.maximum is not None and value > parameter.maximum)
