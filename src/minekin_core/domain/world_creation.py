"""Resolving a Kin's world-creation proposal into the immutable profile P0 builds.

The hosted-world control boundary contract splits world creation in three, and this
is the middle layer. A Kin submits a *proposal*: an intention, with a name it chose
and preferences it would like. The gateway resolves that against a fixed bundle and
the management policy into an *effective profile*: immutable, digestable, and the
only thing the Bridge is ever handed. The Bridge does not read the proposal; it reads
this.

The rule that gives this module its shape is the last line of the contract's policy
table: a combination that has not been tested may be refused with the reason named, or
sent to a dedicated experiment, but must never be quietly resolved into a different
world. (The contract says it in Chinese; the source here stays in one language.) So the
P0 archetype
is checked at *parse* time and anything outside it is refused with the field and the
value that was asked for. What comes out of the parser is a `Proposal`, and a
`Proposal` is by construction something the P0 archetype can honour — which is why
`synthesize` cannot fail and has nothing to refuse.

Two consequences worth stating because they are what the contract is buying:

- There is no field for cheats, for a game rule override, or for a data
  configuration, so a proposal that asks for one is refused as an unknown field.
  "The Bridge would refuse a value" is a weaker rule than "there is nothing to set",
  and the contract asks for the stronger one.
- The display name is the Kin's and the storage slot is the system's, and they are
  kept apart by construction: the slot is a function of the Kin and the proposal
  identifier, never of the name. The name is still pinned — the proposal's digest is
  part of the profile's provenance — so a rename changes the profile's digest without
  changing a single directory.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, cast

#: The contract's name for this shape, and the value the profile carries.
WORLD_CREATE_SCHEMA: Final = "minekin.world-create.v1"

#: The version a proposal document declares. Every document this repository keeps
#: carries one, and a proposal is a document: it is submitted, stored and quoted
#: back at the Kin, so it needs to be readable by a later version of this code.
PROPOSAL_SCHEMA_VERSION: Final = 1

#: The same for the profile this module produces. It is stored — committed as a
#: fixture and sealed into bundles — so it says which revision of the document
#: format it is. The contract's `schema` names the shape; this names the revision
#: of the document, and a reader needs both to decide whether it can parse it.
PROFILE_SCHEMA_VERSION: Final = 1

#: The reviewed bundle a P0 profile is resolved against. This repository has one, and
#: naming it here rather than passing it around means a profile built from some other
#: bundle is not something a caller can do by accident.
P0_BUNDLE_ID: Final = "p0-core-1.21.4"

#: The two revisions the profile's provenance records. The contract names them as
#: identifiers without fixing values; these are this repository's, and changing either
#: is a change to the archetype rather than to a run.
HOST_POLICY_REVISION: Final = "p0-host-policy.v1"
VANILLA_BASELINE_REVISION: Final = "vanilla-default-1.21.4"

#: The one style P0 resolves. The contract fixes survival as the only game mode the
#: project commits to, and a style is how a Kin asks for a different one.
P0_STYLE: Final = "ordinary_survival"

#: The P0 shape, exactly as the contract's policy table fixes it. Frozen here rather
#: than assembled at each use, so that "what P0 builds" is one value a reader can
#: check against the table rather than a sequence of assignments to follow.
_LEVEL: Final[dict[str, object]] = {
    "game_mode": "survival",
    "hardcore": False,
    "difficulty": "normal",
    "allow_commands": False,
    "game_rules_profile": "vanilla-default-1.21.4",
    "data_configuration": "vanilla-stable-1.21.4",
}
_GENERATOR: Final[dict[str, object]] = {
    "preset": "minecraft:normal",
    "seed_mode": "random",
    "seed_secret_ref": None,
    "generate_structures": True,
    "bonus_chest": False,
}

_PROPOSAL_KEYS = frozenset(
    {
        "schema_version",
        "proposal_id",
        "kin_id",
        "reason",
        "display_name",
        "desired_style",
        "preferences",
    }
)
_PROPOSAL_OPTIONAL_KEYS = frozenset({"evidence_refs"})
_PREFERENCE_KEYS = frozenset({"difficulty", "seed_mode"})


class WorldCreationRefusal(StrEnum):
    """Why a proposal is not one P0 can build, each naming its own condition."""

    NOT_AN_OBJECT = "NOT_AN_OBJECT"
    MISSING_FIELD = "MISSING_FIELD"
    #: A field P0 has no entry for. This is the refusal for cheats, a game-rule
    #: override and a data configuration, and it is stronger than a value check: the
    #: rule's strongest form is that there is nothing to set.
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    SCHEMA_VERSION_UNSUPPORTED = "SCHEMA_VERSION_UNSUPPORTED"
    INVALID_STRING = "INVALID_STRING"
    INVALID_PREFERENCES = "INVALID_PREFERENCES"
    STYLE_NOT_P0 = "STYLE_NOT_P0"
    DIFFICULTY_NOT_P0 = "DIFFICULTY_NOT_P0"
    SEED_MODE_NOT_P0 = "SEED_MODE_NOT_P0"


@dataclass(frozen=True, slots=True)
class Refusal:
    """One reason a proposal was refused, and what it asked for."""

    code: WorldCreationRefusal
    #: The field the refusal is about, empty when it is about the document itself.
    field: str = ""
    #: The value that was asked for, so the refusal explains rather than denies.
    requested: object = None

    def __str__(self) -> str:
        where = f":{self.field}" if self.field else ""
        asked = "" if self.requested is None else f" (asked for {self.requested!r})"
        return f"{self.code.value}{where}{asked}"


@dataclass(frozen=True, slots=True)
class Proposal:
    """A Kin's intention, checked against the P0 archetype.

    Everything here is what the Kin may decide: whether to create a world, when, what
    to call it, and why. The preferences are carried because the profile pins the
    proposal by digest — a reader can see what was asked for — and not because they
    can move the profile, which they cannot: a preference outside P0 is refused above.
    """

    proposal_id: str
    kin_id: str
    reason: str
    display_name: str
    desired_style: str
    difficulty: str
    seed_mode: str
    evidence_refs: tuple[str, ...]
    #: The proposal as it was given, so the profile can pin *these* bytes.
    digest: str


@dataclass(frozen=True, slots=True)
class EffectiveProfile:
    """What P0 will build, and what a Bridge may be handed."""

    proposal_id: str
    bundle_id: str
    storage_slot: str
    proposal_digest: str
    digest: str

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "schema": WORLD_CREATE_SCHEMA,
            "proposal_id": self.proposal_id,
            "bundle_id": self.bundle_id,
            "storage_slot": self.storage_slot,
            "level": dict(_LEVEL),
            "generator": dict(_GENERATOR),
            "provenance": {
                "kin_proposal_digest": self.proposal_digest,
                "host_policy_revision": HOST_POLICY_REVISION,
                "baseline_revision": VANILLA_BASELINE_REVISION,
            },
            "effective_digest": self.digest,
        }


def _canonical(document: Mapping[str, object]) -> str:
    return json.dumps(dict(document), sort_keys=True, separators=(",", ":"))


def _text(source: Mapping[str, object], key: str) -> str | None:
    value = source.get(key)
    return value if isinstance(value, str) and value else None


def _strings(source: Mapping[str, object], key: str) -> tuple[str, ...] | None:
    value = source.get(key, [])
    if not isinstance(value, list):
        return None
    items = cast(list[object], value)
    return (
        tuple(cast(str, item) for item in items) if all(isinstance(i, str) for i in items) else None
    )


def _preferences(document: Mapping[str, object], found: list[Refusal]) -> tuple[str, str]:
    """The two preferences P0 has, each with the one value it accepts.

    A preference that is absent and one that was given a value P0 does not build are
    different refusals: the first says the proposal was incomplete, the second says it
    asked for something. Reporting an omission as a wrong value would tell the Kin it
    chose something it never chose.
    """

    raw = document.get("preferences")
    if not isinstance(raw, Mapping):
        found.append(Refusal(WorldCreationRefusal.INVALID_PREFERENCES, "preferences", raw))
        return "", ""
    preferences = cast(Mapping[str, object], raw)
    for key in sorted(set(preferences) - _PREFERENCE_KEYS):
        found.append(
            Refusal(WorldCreationRefusal.UNKNOWN_FIELD, f"preferences.{key}", preferences[key])
        )
    accepted_values = {
        "difficulty": ("normal", WorldCreationRefusal.DIFFICULTY_NOT_P0),
        "seed_mode": ("random", WorldCreationRefusal.SEED_MODE_NOT_P0),
    }
    values: dict[str, str] = {}
    for key, (wanted, code) in accepted_values.items():
        field = f"preferences.{key}"
        if key not in preferences:
            found.append(Refusal(WorldCreationRefusal.MISSING_FIELD, field))
            values[key] = ""
            continue
        value = preferences[key]
        if not isinstance(value, str) or not value:
            found.append(Refusal(WorldCreationRefusal.INVALID_STRING, field, value))
            values[key] = ""
        elif value != wanted:
            found.append(Refusal(code, field, value))
            values[key] = value
        else:
            values[key] = value
    return values["difficulty"], values["seed_mode"]


def parse_proposal(
    document: object,
) -> tuple[Proposal | None, tuple[Refusal, ...]]:
    """Read a proposal, refusing anything the P0 archetype cannot honour.

    The refusals are returned rather than raised, and *all* of them: a proposal that
    asks for three untested things should say so once rather than one at a time, and a
    caller that wants to explain the refusal to the Kin needs the whole list.
    """

    found: list[Refusal] = []
    if not isinstance(document, Mapping):
        return None, (Refusal(WorldCreationRefusal.NOT_AN_OBJECT, requested=document),)
    document = cast(Mapping[str, object], document)

    for key in sorted(set(document) - _PROPOSAL_KEYS - _PROPOSAL_OPTIONAL_KEYS):
        found.append(Refusal(WorldCreationRefusal.UNKNOWN_FIELD, key, document[key]))
    for key in sorted(_PROPOSAL_KEYS - set(document)):
        found.append(Refusal(WorldCreationRefusal.MISSING_FIELD, key))
    if "schema_version" in document and document["schema_version"] != PROPOSAL_SCHEMA_VERSION:
        found.append(
            Refusal(
                WorldCreationRefusal.SCHEMA_VERSION_UNSUPPORTED,
                "schema_version",
                document["schema_version"],
            )
        )

    texts: dict[str, str] = {}
    for key in ("proposal_id", "kin_id", "reason", "display_name", "desired_style"):
        value = _text(document, key)
        if value is None and key in document:
            found.append(Refusal(WorldCreationRefusal.INVALID_STRING, key, document[key]))
        texts[key] = value or ""

    evidence_refs = _strings(document, "evidence_refs")
    if evidence_refs is None:
        found.append(
            Refusal(WorldCreationRefusal.INVALID_STRING, "evidence_refs", document["evidence_refs"])
        )

    difficulty, seed_mode = _preferences(document, found)
    if texts["desired_style"] and texts["desired_style"] != P0_STYLE:
        found.append(
            Refusal(WorldCreationRefusal.STYLE_NOT_P0, "desired_style", texts["desired_style"])
        )

    if found:
        return None, tuple(found)
    return (
        Proposal(
            proposal_id=texts["proposal_id"],
            kin_id=texts["kin_id"],
            reason=texts["reason"],
            display_name=texts["display_name"],
            desired_style=texts["desired_style"],
            difficulty=difficulty,
            seed_mode=seed_mode,
            evidence_refs=evidence_refs or (),
            digest=hashlib.sha256(_canonical(document).encode("utf-8")).hexdigest(),
        ),
        (),
    )


def storage_slot_for(proposal: Proposal) -> str:
    """The slot this proposal's world lives in, named by the system and not by the Kin.

    A function of the Kin and the proposal identifier, both of which the system issues,
    and of nothing the Kin writes. The display name is deliberately not an input: it is
    the one field a Kin can change after the fact, and a world's directory is not
    something a rename should be able to move.
    """

    return f"world-{proposal.kin_id}-{proposal.proposal_id}"


def synthesize(proposal: Proposal, *, bundle_id: str = P0_BUNDLE_ID) -> EffectiveProfile:
    """Resolve a checked proposal into the immutable profile.

    Total, and that is the point: everything the P0 archetype cannot honour was
    refused before a `Proposal` existed, so what is left is a proposal this can build.
    """

    document: dict[str, object] = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "schema": WORLD_CREATE_SCHEMA,
        "proposal_id": proposal.proposal_id,
        "bundle_id": bundle_id,
        "storage_slot": storage_slot_for(proposal),
        "level": dict(_LEVEL),
        "generator": dict(_GENERATOR),
        "provenance": {
            "kin_proposal_digest": proposal.digest,
            "host_policy_revision": HOST_POLICY_REVISION,
            "baseline_revision": VANILLA_BASELINE_REVISION,
        },
    }
    digest = hashlib.sha256(_canonical(document).encode("utf-8")).hexdigest()
    return EffectiveProfile(
        proposal_id=proposal.proposal_id,
        bundle_id=bundle_id,
        storage_slot=cast(str, document["storage_slot"]),
        proposal_digest=proposal.digest,
        digest=digest,
    )


def proposal_document(**overrides: object) -> dict[str, object]:
    """A P0-conforming proposal, for the tests and the cases to vary one field of."""

    baseline: dict[str, object] = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "proposal_id": "proposal-1",
        "kin_id": "kin-1",
        "reason": "wants a world to live in",
        "display_name": "Kinworld",
        "desired_style": P0_STYLE,
        "preferences": {"difficulty": "normal", "seed_mode": "random"},
    }
    merged = dict(baseline)
    merged.update(overrides)
    return merged


def refusals(proposal: Mapping[str, object]) -> Sequence[Refusal]:
    """The refusals a proposal draws, empty when it conforms."""

    _parsed, found = parse_proposal(proposal)
    return found
