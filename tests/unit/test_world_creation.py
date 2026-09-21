"""Resolving a proposal into the P0 profile, and everything that is refused instead.

The contract's rule for this layer is that a combination nobody has tested may be
refused, with the reason named, but may not be quietly resolved into some other world.
So most of what is worth testing here is the refusing: creative, cheats, a game-rule
override, a fixed seed, a data configuration. Each has to come back as a refusal that
says which field and what was asked for, and — the part that is easy to get wrong —
must not come back as a profile that silently differs from what the proposal asked.

Four of these tests are the implementations of two cases' assertions, which is why
they are named as sentences: `check_case_assertions` points the case at the function,
and `run_repo_case` runs it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from minekin_core.domain.world_creation import (
    P0_BUNDLE_ID,
    P0_STYLE,
    EffectiveProfile,
    Proposal,
    WorldCreationRefusal,
    parse_proposal,
    proposal_document,
    synthesize,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "world-create-proposal-p0.json"
)
PROFILE = REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "world-create-p0.json"


def accepted(document: dict[str, object] | None = None) -> Proposal:
    parsed, found = parse_proposal(document if document is not None else proposal_document())
    assert found == (), found
    assert parsed is not None
    return parsed


def refused(document: dict[str, object]) -> tuple[WorldCreationRefusal, ...]:
    parsed, found = parse_proposal(document)

    assert parsed is None, "a proposal that should have been refused was accepted"
    return tuple(refusal.code for refusal in found)


# ---------------------------------------------------------------------------
# The profile
# ---------------------------------------------------------------------------


def test_the_generated_profile_is_the_reviewed_one() -> None:
    """The synthesis, pinned to reviewed bytes rather than to a schema plus my own idea.

    A schema says a shape is allowed; this says the document is the one that was read.
    They are checked in two places on purpose: the schema against this fixture in
    `test_fixture_boundaries`, and the fixture against this module here. Either alone
    would pass while the other drifted.
    """

    proposal = accepted(json.loads(PROPOSAL.read_text(encoding="utf-8")))
    reviewed = json.loads(PROFILE.read_text(encoding="utf-8"))

    assert synthesize(proposal).as_document() == reviewed


def test_the_profile_says_what_it_was_built_from() -> None:
    """A profile nobody can trace back to its proposal is a profile nobody can review."""

    proposal = accepted()
    document = synthesize(proposal).as_document()

    provenance = document["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["kin_proposal_digest"] == proposal.digest
    assert document["bundle_id"] == P0_BUNDLE_ID


def test_a_second_synthesis_produces_the_same_effective_profile() -> None:
    """HOSTCTL-001's first assertion: the profile is a digest of its inputs, not a draw."""

    first = synthesize(accepted())
    second = synthesize(accepted())

    assert isinstance(first, EffectiveProfile)
    assert first.digest == second.digest
    assert first.as_document() == second.as_document()


def test_the_effective_digest_covers_the_profile_and_not_the_digest_itself() -> None:
    """So a reader can recompute it: the digest is over the document without its own field."""

    profile = synthesize(accepted())
    document = dict(profile.as_document())
    del document["effective_digest"]

    recomputed = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    import hashlib

    assert hashlib.sha256(recomputed).hexdigest() == profile.digest


def test_the_display_name_does_not_name_the_storage_slot() -> None:
    """HOSTCTL-001's second assertion, and the contract's own sentence.

    Two proposals identical except for the name produce one slot. The name is still
    pinned — the proposal digest moves — so a rename is recorded without moving a
    directory, which are two different things and have to stay different.
    """

    named = accepted(proposal_document(display_name="Kinworld"))
    renamed = accepted(proposal_document(display_name="Somewhere Else Entirely"))

    assert synthesize(named).storage_slot == synthesize(renamed).storage_slot
    assert synthesize(named).proposal_digest != synthesize(renamed).proposal_digest
    assert synthesize(named).digest != synthesize(renamed).digest


def test_the_slot_is_the_kins_and_the_systems_and_nothing_the_kin_writes() -> None:
    """The negative control for the rule above: the slot still moves when it should."""

    first = accepted(proposal_document(proposal_id="proposal-1"))
    second = accepted(proposal_document(proposal_id="proposal-2"))

    assert synthesize(first).storage_slot != synthesize(second).storage_slot


# ---------------------------------------------------------------------------
# What is refused instead
# ---------------------------------------------------------------------------


def test_a_proposal_outside_the_p0_archetype_is_refused() -> None:
    """HOSTCTL-010's first assertion, over everything the contract names.

    Creative, hardcore, a non-normal difficulty, a fixed seed and a style other than
    ordinary survival each come back refused. The point is that none of them comes
    back as a profile: the contract forbids resolving an untested combination into a
    different world, so the only two outcomes are this and a dedicated experiment.
    """

    assert WorldCreationRefusal.STYLE_NOT_P0 in refused(
        proposal_document(desired_style="creative_builder")
    )
    assert WorldCreationRefusal.DIFFICULTY_NOT_P0 in refused(
        proposal_document(preferences={"difficulty": "hard", "seed_mode": "random"})
    )
    assert WorldCreationRefusal.SEED_MODE_NOT_P0 in refused(
        proposal_document(preferences={"difficulty": "normal", "seed_mode": "explicit"})
    )


def test_there_is_no_field_for_the_things_p0_does_not_allow_at_all() -> None:
    """Cheats, a game rule and a data configuration are refused by not existing.

    This is the contract's strongest form of the rule and worth its own test: "the
    Bridge would refuse a value" is weaker than "there is nothing to set", because a
    field that exists is a field somebody eventually fills in.
    """

    for extra in (
        {"cheats": True},
        {"allow_commands": True},
        {"game_rules": {"keepInventory": True}},
        {"data_configuration": "custom"},
    ):
        assert WorldCreationRefusal.UNKNOWN_FIELD in refused(proposal_document(**extra)), extra
    assert WorldCreationRefusal.UNKNOWN_FIELD in refused(
        proposal_document(
            preferences={"difficulty": "normal", "seed_mode": "random", "keep_inventory": True}
        )
    )


def test_the_refusal_names_what_the_proposal_asked_for() -> None:
    """HOSTCTL-010's second assertion: a refusal that denies cannot be acted on.

    The Kin is told which field and which value, so "no" can be turned into a
    different proposal rather than into a guess about what was wrong.
    """

    parsed, found = parse_proposal(proposal_document(desired_style="creative_builder"))

    assert parsed is None
    assert [refusal.field for refusal in found] == ["desired_style"]
    assert found[0].requested == "creative_builder"
    assert "creative_builder" in str(found[0])


def test_every_refusal_a_proposal_draws_is_reported_at_once() -> None:
    """Three untested things should be three refusals, not one at a time."""

    codes = refused(
        proposal_document(
            desired_style="hardcore_speedrun",
            preferences={"difficulty": "hard", "seed_mode": "explicit"},
        )
    )

    assert set(codes) == {
        WorldCreationRefusal.STYLE_NOT_P0,
        WorldCreationRefusal.DIFFICULTY_NOT_P0,
        WorldCreationRefusal.SEED_MODE_NOT_P0,
    }


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"proposal_id": 1}, WorldCreationRefusal.INVALID_STRING),
        ({"preferences": "normal"}, WorldCreationRefusal.INVALID_PREFERENCES),
        ({"evidence_refs": "x"}, WorldCreationRefusal.INVALID_STRING),
    ],
)
def test_a_malformed_proposal_is_refused_rather_than_defaulted(
    overrides: dict[str, object], expected: WorldCreationRefusal
) -> None:
    """A malformed field must not read as "the default", which is how a proposal
    becomes a profile nobody asked for."""

    assert expected in refused(proposal_document(**overrides))


def test_a_missing_field_is_refused_as_missing_and_not_as_a_wrong_value() -> None:
    """An omission has to say it is an omission.

    Reporting one as a value P0 does not build would tell the Kin it chose something
    it never chose, and a proposal that is only incomplete would look like one that
    was rejected for what it wanted.
    """

    for field in ("proposal_id", "kin_id", "reason", "display_name", "desired_style"):
        document = proposal_document()
        del document[field]

        assert refused(document) == (WorldCreationRefusal.MISSING_FIELD,), field

    incomplete = proposal_document(preferences={"difficulty": "normal"})

    assert refused(incomplete) == (WorldCreationRefusal.MISSING_FIELD,)


def test_the_style_is_only_checked_when_it_was_given() -> None:
    """A missing style is a missing field, not a style that failed the archetype.

    Two refusals for one omission would make the count of what is wrong wrong.
    """

    codes = refused(proposal_document(desired_style=""))

    assert WorldCreationRefusal.STYLE_NOT_P0 not in codes
    assert codes == (WorldCreationRefusal.INVALID_STRING,)


def test_the_p0_style_is_the_one_the_contract_names() -> None:
    """A constant a caller could get wrong is worth pinning to the contract's word."""

    assert P0_STYLE == "ordinary_survival"
