"""Which world is the one the Kin is in, and how a candidate earns that.

The commit-recovery contract's switching gate is four rules and a ladder:

    STAGED -> OBSERVING -> RECONCILED -> ACTIVE

1. until the old world is checkpointed or uncertain, the new one has only a candidate
   identity;
2. the new client's JOIN must agree with the expected server profile or hosted
   manifest, the bundle, and the session/generation;
3. the world and epoch are confirmed once the first player-equivalent snapshot has
   arrived;
4. only one Current World Capsule may be `ACTIVE`;
5. when a switch fails, neither world may be treated as the current reality and the
   old plan stays suspended.

Rule 4 is the reason this is a module. "At most one world is current" is the kind of
statement that is true right up until two code paths each believe they are the one
activating, and the failure is not a crash: it is a Kin whose inventory is in one world
and whose plans are in another. Two things are therefore structural rather than
checked — a capsule can only reach `ACTIVE` from `RECONCILED`, and only one call can
produce that move, so a record with two current worlds is not something this can build.
`current()` refuses one anyway, because a record that came from somewhere else — a file,
another version — is exactly where such a contradiction would arrive from.

Rule 5 is the other reason, and it is the one people get wrong by accident: a failed
switch leaves **no** world current, and that is a correct state rather than an error.
A Kin between worlds has plans that are suspended, and code that insisted on exactly
one current world would have to invent one.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from minekin_core.domain.ids import Generation, OpaqueId, SessionId, WorldContextId


class ActivationStage(StrEnum):
    """How far a candidate world has got towards being the one the Kin is in."""

    #: Only a candidate identity. Rule 1 keeps every new world here until the old one
    #: has been checkpointed, and a failed switch puts it back here.
    STAGED = "STAGED"
    #: Its JOIN was observed and agreed with what was expected.
    OBSERVING = "OBSERVING"
    #: Its world and epoch were confirmed, so it is a world — but not yet the current one.
    RECONCILED = "RECONCILED"
    #: The current reality. At most one capsule may say this (rule 4).
    ACTIVE = "ACTIVE"


class ActivationOutcome(StrEnum):
    """What became of one move, one reason each."""

    ADVANCED = "ADVANCED"
    #: No capsule for that world. A switch to a world nobody staged is not a switch.
    UNKNOWN_WORLD = "UNKNOWN_WORLD"
    #: The move belongs to another stage. The ladder is linear, so a jump is refused
    #: rather than fast-forwarded.
    WRONG_STAGE = "WRONG_STAGE"
    #: The JOIN did not agree with what was expected. The field that disagreed is named
    #: in the outcome, because "the evidence disagrees" is not actionable on its own.
    EVIDENCE_DISAGREES = "EVIDENCE_DISAGREES"
    #: Another world is current. Rule 4.
    ANOTHER_WORLD_IS_CURRENT = "ANOTHER_WORLD_IS_CURRENT"
    #: The capsule is back to being only a candidate.
    RELEASED = "RELEASED"


@dataclass(frozen=True, slots=True)
class WorldCapsule:
    """What is expected of a world, before anything has observed it.

    One capsule per world-epoch, holding the coordinates the next client's JOIN has to
    agree with: the server profile (empty for a world this Kin hosts), the bundle, the
    session and the generation, and the world identity the reconciler will confirm.
    """

    world_context_id: WorldContextId
    hosted_world_id: OpaqueId
    world_epoch: Generation
    storage_slot: str
    #: The remote server profile a remote world is reached by, empty for a hosted one.
    #: Rule 2 asks the JOIN to agree with it, so it has to be on the expectation.
    server_profile_id: str
    bundle_id: str
    session_id: SessionId
    generation: Generation
    stage: ActivationStage = ActivationStage.STAGED


@dataclass(frozen=True, slots=True)
class ActivationEvidence:
    """What a client's JOIN observed, to be held against the expectation."""

    world_context_id: WorldContextId
    world_epoch: Generation
    server_profile_id: str
    bundle_id: str
    session_id: SessionId
    generation: Generation


@dataclass(frozen=True, slots=True)
class ActivationDecision:
    outcome: ActivationOutcome
    #: The field that disagreed, when the outcome is `EVIDENCE_DISAGREES`.
    field: str = ""
    observed: object = None
    expected: object = None

    def __str__(self) -> str:
        if self.outcome is not ActivationOutcome.EVIDENCE_DISAGREES:
            return self.outcome.value
        return f"{self.outcome.value}:{self.field}={self.observed!r} (expected {self.expected!r})"


def _fields_of(capsule: WorldCapsule) -> dict[str, object]:
    """The coordinates rule 2 holds a JOIN against, by name."""

    return {
        "world_context_id": capsule.world_context_id,
        "world_epoch": capsule.world_epoch,
        "server_profile_id": capsule.server_profile_id,
        "bundle_id": capsule.bundle_id,
        "session_id": capsule.session_id,
        "generation": capsule.generation,
    }


def current(capsules: tuple[WorldCapsule, ...]) -> WorldCapsule | None:
    """The world the Kin is in, or None when none is (which a failed switch makes).

    Two current worlds is refused rather than picked between: this module cannot build
    such a record, so one that exists came from somewhere else, and choosing either
    would attribute one world's facts to another.
    """

    found = [capsule for capsule in capsules if capsule.stage is ActivationStage.ACTIVE]

    if len(found) > 1:
        raise ValueError(
            "more than one world is ACTIVE: "
            + ", ".join(str(capsule.hosted_world_id) for capsule in found)
        )
    return found[0] if found else None


def suspended(capsules: tuple[WorldCapsule, ...]) -> bool:
    """Whether the Kin is between worlds, which is what rule 5 leaves behind."""

    return current(capsules) is None


def _with(
    capsules: tuple[WorldCapsule, ...], world_id: OpaqueId, stage: ActivationStage
) -> tuple[WorldCapsule, ...]:
    return tuple(
        replace(capsule, stage=stage) if capsule.hosted_world_id == world_id else capsule
        for capsule in capsules
    )


def _find(capsules: tuple[WorldCapsule, ...], world_id: OpaqueId) -> WorldCapsule | None:
    for capsule in capsules:
        if capsule.hosted_world_id == world_id:
            return capsule
    return None


#: The refusal every operation makes when there is no capsule for the world named.
_UNKNOWN = ActivationDecision(ActivationOutcome.UNKNOWN_WORLD)


def observe(
    capsules: tuple[WorldCapsule, ...], world_id: OpaqueId, evidence: ActivationEvidence
) -> tuple[tuple[WorldCapsule, ...], ActivationDecision]:
    """Rule 2: a JOIN is observed, and it has to agree with what was expected.

    This is where a wrong world would otherwise walk in: a client that joined some
    other world, or this one under another session, is not evidence that the switch
    happened. Refusing names the field, because a switch that stops for a reason nobody
    can act on stops forever.
    """

    capsule = _find(capsules, world_id)
    if capsule is None:
        return capsules, _UNKNOWN
    if capsule.stage is not ActivationStage.STAGED:
        return capsules, ActivationDecision(ActivationOutcome.WRONG_STAGE)
    for field, expected in _fields_of(capsule).items():
        observed = getattr(evidence, field)
        if observed != expected:
            return capsules, ActivationDecision(
                ActivationOutcome.EVIDENCE_DISAGREES, field, observed, expected
            )
    return _with(capsules, world_id, ActivationStage.OBSERVING), ActivationDecision(
        ActivationOutcome.ADVANCED
    )


def reconcile(
    capsules: tuple[WorldCapsule, ...], world_id: OpaqueId
) -> tuple[tuple[WorldCapsule, ...], ActivationDecision]:
    """Rule 3: the first player-equivalent snapshot confirmed the world and its epoch."""

    capsule = _find(capsules, world_id)
    if capsule is None:
        return capsules, _UNKNOWN
    if capsule.stage is not ActivationStage.OBSERVING:
        return capsules, ActivationDecision(ActivationOutcome.WRONG_STAGE)
    return _with(capsules, world_id, ActivationStage.RECONCILED), ActivationDecision(
        ActivationOutcome.ADVANCED
    )


def activate(
    capsules: tuple[WorldCapsule, ...], world_id: OpaqueId
) -> tuple[tuple[WorldCapsule, ...], ActivationDecision]:
    """Rule 4: this world becomes the current one, and only if no other is.

    A candidate can only get here through `reconcile`, so a world nobody confirmed
    cannot become the reality the Kin's facts are bound to.
    """

    capsule = _find(capsules, world_id)
    if capsule is None:
        return capsules, _UNKNOWN
    if capsule.stage is not ActivationStage.RECONCILED:
        return capsules, ActivationDecision(ActivationOutcome.WRONG_STAGE)
    existing = current(capsules)
    if existing is not None and existing.hosted_world_id != world_id:
        return capsules, ActivationDecision(ActivationOutcome.ANOTHER_WORLD_IS_CURRENT)
    return _with(capsules, world_id, ActivationStage.ACTIVE), ActivationDecision(
        ActivationOutcome.ADVANCED
    )


def release(
    capsules: tuple[WorldCapsule, ...], world_id: OpaqueId
) -> tuple[tuple[WorldCapsule, ...], ActivationDecision]:
    """Rules 1 and 5: a world is no longer current, and is only a candidate again.

    One operation for both uses, because they are one statement: nothing is current
    without having passed the gate, and a world that has stopped being current has to
    pass it again. The same call takes the old world out when a switch begins and takes
    a failed candidate back when it does not finish.
    """

    capsule = _find(capsules, world_id)
    if capsule is None:
        return capsules, _UNKNOWN
    return _with(capsules, world_id, ActivationStage.STAGED), ActivationDecision(
        ActivationOutcome.RELEASED
    )
