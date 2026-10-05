"""Choosing which skills run, in what order, and what each one is allowed to need.

`WorldSkills` knows how to perform one action; this module knows how a *plan* of
them is expressed and run. The split is the one the S3 contract needs: the plan
below comes from a document an operator wrote, and tomorrow it comes from a
`PlayerMind` decision, and neither of those is the business of the code that
presses the keys. What stays here is the part that does not change with the
author: a skill name means a fixed set of capabilities, a skill without its
arguments is not executable, and a step that did not confirm ends the sequence
rather than being retried.

Why the sequence stops on anything but `CONFIRMED` is §4's own rule. A `UNKNOWN`
step means the readings could not say whether the world changed — the Kin does
not know whether it is holding planks — and the next step in a gather-and-craft
chain is written against exactly that ignorance. Auto-retrying the click is
forbidden; continuing past it would be the same mistake wearing a different name,
because a `craft` whose materials are not there has to be refused on the pre-state
and a run that cannot read its pre-state has no business asking for one.

The names and argument shapes are checked before a client exists. That ordering is
the whole point of parsing here rather than at each call site: a plan naming
`brake_seen_block` would otherwise be discovered twelve seconds into a run whose
Kin was already in a world, and the run document would record a Kin that simply
never acted.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from minekin_core.application.world_skills import (
    CLIENT_EXITED,
    ActionAuthority,
    ClientProcessExited,
    PlayerDied,
    SkillCall,
    WorldSkills,
)
from minekin_core.domain.recipe_catalog import PLAYER_GRID_SIDE, Recipe, resolve_craft
from minekin_core.domain.world_actions import (
    ActionResultClass,
    SkillOutcome,
    skill_capabilities,
)

#: The document shape this module reads. A plan document that names another
#: version is refused rather than interpreted: a plan is evidence about what an
#: operator asked for, and a reader that guessed across versions would be
#: rewriting that evidence.
SKILL_PLAN_SCHEMA_VERSION: Final = 1

#: The argument a skill may omit. `turn_to` at zero degrees is a real ask (face
#: south, look level), so an absent angle is not a missing one; what has to be
#: named is the thing a skill cannot invent — which item, which slot, which
#: recipe.
_DEFAULTED: Final[dict[str, tuple[str, ...]]] = {
    "turn_to": ("yaw_degrees", "pitch_degrees"),
    "break_seen_block": ("expected_drop_item",),
    "collect_dropped": ("walk_seconds",),
    "consume_item": (),
    "craft": ("craft_all",),
    "craft_take_result": (),
    "close_screen": (),
    "select_hotbar": ("expected_item_id",),
    "use_target": (),
    "respawn": (),
}

#: The argument each skill requires, by name. Empty for a skill that can run on
#: the world's own state. A craft may instead be spelled by product alone, which
#: is not a defaulted argument — it is a different question, "what should the Kin
#: be holding afterwards?" — and the recipe it resolves to comes from the catalog.
_REQUIRED: Final[dict[str, tuple[str, ...]]] = {
    "turn_to": (),
    "break_seen_block": (),
    "collect_dropped": ("item_id",),
    "consume_item": ("item_id",),
    "craft": ("recipe_id", "materials", "product_id"),
    "craft_take_result": ("recipe_id", "materials", "product_id"),
    "close_screen": (),
    "select_hotbar": ("slot",),
    "use_target": (),
    "respawn": (),
}

#: The keys that replace a skill's whole required set rather than defaulting one
#: of its arguments. Only a craft has such a spelling, and only because a recipe
#: is a fact about the game that a plan author is not obliged to know.
_ALTERNATIVES: Final[dict[str, tuple[str, ...]]] = {
    "craft": ("product",),
    "craft_take_result": ("product",),
    "close_screen": (),
    "turn_to": (),
    "break_seen_block": (),
    "collect_dropped": (),
    "consume_item": (),
    "select_hotbar": (),
    "use_target": (),
    "respawn": (),
}

#: Every key a plan may use, so a typo is refused by name instead of being
#: ignored and leaving a skill to run on defaults nobody chose.
_KNOWN_KEYS: Final[dict[str, frozenset[str]]] = {
    name: frozenset((*required, *_DEFAULTED[name], *_ALTERNATIVES[name]))
    for name, required in _REQUIRED.items()
}

#: The stable token for a plan that names something which is not a skill. One
#: word for both the parse-time refusal and the runtime outcome, so a search for
#: it finds the run whether the mistake was caught early or late.
SKILL_UNKNOWN: Final = "SKILL_UNKNOWN"

#: The stable token for a skill whose required arguments are not in the plan.
SKILL_ARGUMENT_MISSING: Final = "SKILL_ARGUMENT_MISSING"

#: The headroom one step's lease gets over its own waiting window. The window
#: bounds how long a skill waits for a reading; the lease also has to cover the
#: sends on either side of it and the store's own wake-up, and a lease that
#: lapsed between the last send and the release would be a Kin left holding a key
#: the Bridge refuses to be told about.
STEP_LEASE_HEADROOM_S: Final = 2.0


class SkillPlanError(ValueError):
    """A plan that cannot be read, in words naming which plan could not be read."""


@dataclass(frozen=True, slots=True)
class SkillStep:
    """One executed call, and the word the readings gave back."""

    name: str
    outcome: SkillOutcome

    def as_document(self) -> dict[str, object]:
        return {
            "skill": self.name,
            "result": self.outcome.result.value,
            "reason": self.outcome.reason,
            "action_id": self.outcome.action_id,
            "pre_tick": self.outcome.pre_tick,
            "post_tick": self.outcome.post_tick,
            "details": dict(self.outcome.details),
        }


@dataclass(frozen=True, slots=True)
class SkillSequence:
    """Every step a run took, and where it stopped.

    `stopped_at` is the name of the step that ended the sequence, empty when the
    plan ran to its end. It is kept because "the Kin crafted nothing" has two
    entirely different readings — the plan never got past breaking the log, and
    the plan was one skill long — and only the position says which happened.
    """

    steps: tuple[SkillStep, ...] = ()
    stopped_at: str = ""

    def as_document(self) -> dict[str, object]:
        return {
            "steps": [step.as_document() for step in self.steps],
            "stopped_at": self.stopped_at,
            "confirmed": sum(
                1 for step in self.steps if step.outcome.result is ActionResultClass.CONFIRMED
            ),
        }


@dataclass(frozen=True, slots=True)
class SkillPlan:
    """A parsed plan: the calls in order, and nothing else.

    A frozen value rather than a list, because it is the record of what an
    operator asked for, and the run document has to be able to say "this plan"
    without anyone re-deriving it from the commands that went out.
    """

    calls: tuple[SkillCall, ...] = ()
    source: str = ""

    def __len__(self) -> int:
        return len(self.calls)

    @property
    def capabilities(self) -> frozenset[str]:
        """Everything this plan would need authorising for, unioned.

        Empty for an empty plan, which is honest: a plan that asks for no skill
        claims no capability, and a caller that leases on the strength of this
        property would be asking the arbiter for nothing at all.
        """

        found: set[str] = set()
        for call in self.calls:
            found |= skill_capabilities(call.name) or frozenset()
        return frozenset(found)


def parse_skill_plan(document: object, *, source: str = "") -> SkillPlan:
    """Read a plan document into typed calls, refusing anything it is not.

    The refusals name the item and the field, because a plan is written by
    someone who is not looking at this source: "invalid document" would send them
    back to read the file, and `skills[2].craft is missing product_id` tells them
    which line and which word.
    """

    if not isinstance(document, Mapping):
        raise SkillPlanError("a skill plan must be an object of fields")
    fields = cast("Mapping[str, Any]", document)
    version = fields.get("schema_version")
    if version != SKILL_PLAN_SCHEMA_VERSION:
        raise SkillPlanError(
            f"a skill plan must declare schema_version {SKILL_PLAN_SCHEMA_VERSION}, not {version!r}"
        )
    raw = fields.get("skills")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise SkillPlanError("a skill plan needs a `skills` list")
    if not raw:
        raise SkillPlanError("a skill plan needs at least one entry in `skills`")
    calls: list[SkillCall] = []
    entries = cast("Sequence[Any]", raw)
    for index, item in enumerate(entries):
        if not isinstance(item, Mapping):
            raise SkillPlanError(f"skills[{index}] must be an object naming one skill")
        calls.append(_parse_call(cast("Mapping[str, Any]", item), index))
    return SkillPlan(tuple(calls), source)


def _parse_call(item: Mapping[str, Any], index: int) -> SkillCall:
    name = item.get("skill")
    if not isinstance(name, str) or not name:
        raise SkillPlanError(f"skills[{index}] has no `skill` name")
    if skill_capabilities(name) is None:
        raise SkillPlanError(
            f"skills[{index}] names {name!r}, which is not a skill this build has: "
            f"{', '.join(sorted(_REQUIRED))}"
        )
    known = _KNOWN_KEYS[name]
    unknown = sorted(str(key) for key in item if key != "skill" and key not in known)
    if unknown:
        raise SkillPlanError(f"skills[{index}] ({name}) has keys it does not take: {unknown}")
    by_product = _by_product(item, index, name)
    if not by_product:
        missing = [required for required in _REQUIRED[name] if item.get(required) is None]
        if missing:
            raise SkillPlanError(f"skills[{index}] ({name}) is missing {missing}")
    recipe_id, product_id, materials = _craft_arguments(item, index, name, by_product=by_product)
    return SkillCall(
        name=name,
        yaw_degrees=_number(item, index, name, "yaw_degrees", 0.0),
        pitch_degrees=_number(item, index, name, "pitch_degrees", 0.0),
        item_id=_text(item, index, name, "item_id"),
        slot=_int(item, index, name, "slot", -1),
        recipe_id=recipe_id,
        product_id=product_id,
        expected_drop_item=_text(item, index, name, "expected_drop_item"),
        expected_item_id=_text(item, index, name, "expected_item_id"),
        walk_seconds=_number(item, index, name, "walk_seconds", 1.0),
        materials=materials,
        craft_all=_flag(item, index, name, "craft_all", True),
    )


def _by_product(item: Mapping[str, Any], index: int, name: str) -> bool:
    """Whether this entry spells its craft by the item it wants to end up holding.

    The key's shape is checked here rather than at the read below so that a plan
    author who wrote `product: 4` is told which word is wrong, not which recipe is
    missing.
    """

    if item.get("product") is None:
        return False
    _text(item, index, name, "product")
    return True


def _craft_arguments(
    item: Mapping[str, Any], index: int, name: str, *, by_product: bool
) -> tuple[str, str, tuple[tuple[str, int], ...]]:
    """Which recipe a craft entry will run, from the catalog or from the plan's own words.

    A product-only entry is where the parameterised design pays for itself: the plan says what
    the Kin should be holding afterwards and the catalog answers with the recipe id, the
    ingredients and their counts. The unrunnable answers are refused here, in words, before a
    client exists — `CRAFT_RECIPE_UNAVAILABLE` for a product nobody has curated and
    `CRAFT_GRID_TOO_SMALL` for a shape the screen this skill opens cannot hold. An entry that
    names both the product and its own recipe is refused rather than adjudicated: two sources
    for one game fact is the mistake, whether or not they agree.

    The other branch is the plan that spells the trio itself, unchanged from before the
    catalog existed, because a committed plan is evidence of what an operator asked for and
    this layer's job is to read evidence, not to rewrite it. A skill that crafts nothing reads
    the same three fields as empty strings and an empty tuple, which is what they already were.
    """

    if not by_product:
        return (
            _text(item, index, name, "recipe_id"),
            _text(item, index, name, "product_id"),
            _materials(item, index, name),
        )
    product = _text(item, index, name, "product")
    spelled = [key for key in ("recipe_id", "materials", "product_id") if item.get(key) is not None]
    if spelled:
        raise SkillPlanError(
            f"skills[{index}] ({name}) names a product and also its own {spelled}: a "
            "product-only entry takes its recipe from the catalog, which is the one source of "
            "that fact"
        )
    resolved = resolve_craft(product, grid_side=PLAYER_GRID_SIDE)
    if not isinstance(resolved, Recipe):
        raise SkillPlanError(f"skills[{index}] ({name}) cannot craft {product!r}: {resolved}")
    return (resolved.recipe_id, resolved.product_id, resolved.ingredients)


def _flag(item: Mapping[str, Any], index: int, name: str, key: str, default: bool) -> bool:
    """A plan's yes-or-no, or the skill's own default.

    Only a real bool is accepted: `craft_all: "true"` is a plan whose author
    guessed at the shape, and a coercing reader would quietly agree with a
    different sentence than the one written.
    """

    value = item.get(key, default)
    if not isinstance(value, bool):
        raise SkillPlanError(f"skills[{index}] ({name}) needs {key} to be true or false")
    return bool(value)


def _text(item: Mapping[str, Any], index: int, name: str, key: str) -> str:
    value = item.get(key)
    if value is None:
        return ""
    if not isinstance(value, str) or not value:
        raise SkillPlanError(f"skills[{index}] ({name}) needs {key} to be a non-empty string")
    return value


def _number(item: Mapping[str, Any], index: int, name: str, key: str, default: float) -> float:
    value = item.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SkillPlanError(f"skills[{index}] ({name}) needs {key} to be a number")
    return float(value)


def _int(item: Mapping[str, Any], index: int, name: str, key: str, default: int) -> int:
    value = item.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SkillPlanError(f"skills[{index}] ({name}) needs {key} to be a whole number")
    return value


def _materials(item: Mapping[str, Any], index: int, name: str) -> tuple[tuple[str, int], ...]:
    value = item.get("materials")
    if value is None:
        return ()
    if not isinstance(value, Mapping) or not value:
        raise SkillPlanError(
            f"skills[{index}] ({name}) needs `materials` as an object of item id to count"
        )
    pairs: list[tuple[str, int]] = []
    counted = cast("Mapping[object, Any]", value)
    for item_id, count in counted.items():
        if not isinstance(item_id, str) or not item_id:
            raise SkillPlanError(f"skills[{index}] ({name}) has a material with no item id")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise SkillPlanError(
                f"skills[{index}] ({name}) needs the count of {item_id} to be a positive number"
            )
        pairs.append((item_id, count))
    return tuple(pairs)


def sequence_lease_seconds(calls: Sequence[SkillCall], timeout_s: float) -> float:
    """How long one lease has to last for this plan.

    A sum rather than the longest single step, because the steps run one after
    another under one lease and each owns its own waiting window.
    """

    return max(0.0, len(calls)) * (timeout_s + STEP_LEASE_HEADROOM_S)


async def run_skill_plan(
    skills: WorldSkills,
    plan: SkillPlan,
    *,
    authority: ActionAuthority,
    timeout_ns: int,
    on_step: Callable[[SkillStep], Awaitable[None]] | None = None,
) -> SkillSequence:
    """Run the plan under one lease, and stop at the first step the world did not confirm."""

    steps: list[SkillStep] = []
    for call in plan.calls:
        outcome = await perform_skill(skills, call, authority=authority, timeout_ns=timeout_ns)
        step = SkillStep(call.name, outcome)
        steps.append(step)
        if on_step is not None:
            # Each step is reported the moment the readings conclude it, so a reader of the
            # ledger sees the sequence in the order it lived rather than only the step that
            # ended it.
            await on_step(step)
        if outcome.result is not ActionResultClass.CONFIRMED:
            return SkillSequence(tuple(steps), stopped_at=call.name)
    return SkillSequence(tuple(steps))


async def perform_skill(
    skills: WorldSkills,
    call: SkillCall,
    *,
    authority: ActionAuthority,
    timeout_ns: int,
) -> SkillOutcome:
    """Ask one skill for one thing, refusing a call this build cannot express.

    Every refusal below happens before a command is built, so the reason a Kin did
    not act is never left to be inferred from a timeout it did not cause — which is
    also what makes a client that is already gone a named precondition rather than a
    step that timed out waiting for a JVM that will never read it.
    """

    if skill_capabilities(call.name) is None:
        return SkillOutcome(
            result=ActionResultClass.FAILED,
            reason=SKILL_UNKNOWN,
            action_id="",
            details={"skill": call.name},
        )
    missing = [key for key in _REQUIRED[call.name] if not _present(call, key)]
    if missing:
        return SkillOutcome(
            result=ActionResultClass.FAILED,
            reason=SKILL_ARGUMENT_MISSING,
            action_id="",
            details={"skill": call.name, "missing": ",".join(missing)},
        )
    gone = skills.client_exit_code()
    if gone is not None:
        # Nothing had been asked of this client yet, so there is no in-flight id to
        # carry — the emptiness is the fact, and the step below proves the row can
        # name one when there was.
        return _client_exited_outcome(gone, "")
    try:
        async with skills.body_attempt():
            outcome = await _dispatch(skills, call, authority=authority, timeout_ns=timeout_ns)
            skills.check_body_interruption(outcome.action_id)
            return outcome
    except ClientProcessExited as exit_error:
        # The wait gave up because the process that would have answered it is gone.
        # `UNKNOWN` rather than `FAILED`: the command went out and the world may have
        # changed by the time the JVM died, which is a fact this run cannot read.
        return _client_exited_outcome(exit_error.exit_code, exit_error.action_id)
    except PlayerDied as interrupted:
        return SkillOutcome(
            result=ActionResultClass.INTERRUPTED,
            reason="PLAYER_DEAD",
            action_id=interrupted.action_id,
            post_tick=interrupted.game_tick,
            details={"release_send_failed": "true"} if interrupted.release_failed else {},
        )


async def _dispatch(
    skills: WorldSkills,
    call: SkillCall,
    *,
    authority: ActionAuthority,
    timeout_ns: int,
) -> SkillOutcome:
    """Ask the one skill the call names, under the plan's lease.

    Nothing here decides a verdict: each skill concludes from its own readings, and
    this function only maps a call's name onto the method that carries it.
    """

    if call.name == "respawn":
        return await skills.respawn(authority=authority, timeout_ns=timeout_ns)
    if call.name == "retreat":
        return await skills.retreat(authority=authority, timeout_ns=timeout_ns)
    if call.name == "turn_to":
        return await skills.turn_to(
            yaw_degrees=call.yaw_degrees,
            pitch_degrees=call.pitch_degrees,
            authority=authority,
            timeout_ns=timeout_ns,
        )
    if call.name == "break_seen_block":
        return await skills.break_seen_block(
            authority=authority,
            expected_drop_item=call.expected_drop_item or None,
            timeout_ns=timeout_ns,
        )
    if call.name == "collect_dropped":
        return await skills.collect_dropped(
            item_id=call.item_id,
            authority=authority,
            walk_seconds=call.walk_seconds,
            timeout_ns=timeout_ns,
        )
    if call.name == "consume_item":
        return await skills.consume_item(
            item_id=call.item_id,
            authority=authority,
            timeout_ns=timeout_ns,
        )
    if call.name == "craft":
        return await skills.craft(
            recipe_id=call.recipe_id,
            materials=dict(call.materials),
            product_id=call.product_id,
            authority=authority,
            craft_all=call.craft_all,
            timeout_ns=timeout_ns,
        )
    if call.name == "craft_take_result":
        return await skills.craft_take_result(
            recipe_id=call.recipe_id,
            materials=dict(call.materials),
            product_id=call.product_id,
            authority=authority,
            timeout_ns=timeout_ns,
        )
    if call.name == "close_screen":
        return await skills.close_screen(authority=authority, timeout_ns=timeout_ns)
    if call.name == "use_target":
        return await skills.use_target(authority=authority, timeout_ns=timeout_ns)
    return await skills.select_hotbar(
        slot=call.slot,
        authority=authority,
        expected_item_id=call.expected_item_id or None,
        timeout_ns=timeout_ns,
    )


def _client_exited_outcome(exit_code: int, action_id: str) -> SkillOutcome:
    """The one shape a step takes when its client is the reason it cannot be settled.

    `action_id` is the ask that was in flight, which the step itself knows: empty when
    nothing had been sent yet, and the id of a command that had left for the client
    otherwise. Dropping it would report the exit as if no command had been asked.
    """

    return SkillOutcome(
        result=ActionResultClass.UNKNOWN,
        reason=CLIENT_EXITED,
        action_id=action_id,
        details={"exit_code": str(exit_code)},
    )


def _present(call: SkillCall, key: str) -> bool:
    """Whether a required argument is there. Strings and the materials tuple are
    the only two kinds that can be absent; a number is always present, because
    the skill owning that number has its own named refusal for a silly one — a
    slot outside the nine is refused by `HOTBAR_SLOT_OUT_OF_RANGE`, not here.
    """

    if key == "materials":
        return bool(call.materials)
    value = getattr(call, key)
    return True if not isinstance(value, str) else bool(value)
