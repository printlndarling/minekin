"""The initial persona: a versioned manifest derived once, then read back.

`docs/persona-generation-contract.md` settles that a persona is structured
configuration and not a paragraph of prompt text, and that restarting, dying or
switching models must never redraw it. This module is the drawing: given the same
`kin_id` and seed it produces the same manifest in any process, and the manifest
carries the algorithm and schema version that produced it so a later build can tell
whether it is reading the same person or a different one.

Derivation is `blake2b` over the three names, not Python's `hash()`, which is
salted per process and would therefore give a Kin a different personality on every
boot while claiming to persist one.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, cast

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

PERSONA_ALGORITHM: Final = "persona-blake2b-v1"
PERSONA_SCHEMA_VERSION: Final = 1

#: The five broad tendencies the S3 loop lets influence what a Kin notices and how
#: long it tolerates. They are the `广义倾向` row of the manifest, nothing more: no
#: trait here maps to an action, and a label never scripts behaviour.
TRAIT_NAMES: Final = (
    "social_initiative",
    "cooperation",
    "orderliness",
    "curiosity",
    "risk_tolerance",
)
#: The values the scheduler may weigh against each other. The order is the persona;
#: the names are fixed so a manifest from another build cannot invent one.
VALUE_NAMES: Final = (
    "autonomy",
    "fairness",
    "resource_security",
    "belonging",
    "exploration",
    "creation",
)
TRAIT_FLOOR: Final = 1
TRAIT_CEILING: Final = 9


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "domain.persona", "derive", ErrorCategory.CONFIG, Retryability.OPERATOR_ACTION, message
    )


@dataclass(frozen=True, slots=True)
class PersonaManifest:
    """One Kin's initial persona, plus the words for how it came to be this one."""

    kin_id: str
    persona_seed: str
    algorithm: str
    schema_version: int
    traits: tuple[tuple[str, int], ...]
    value_priority: tuple[str, ...]

    def trait(self, name: str) -> int:
        for key, value in self.traits:
            if key == name:
                return value
        raise _reject(f"persona has no trait named {name!r}")

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "algorithm": self.algorithm,
            "kin_id": self.kin_id,
            "persona_seed": self.persona_seed,
            "traits": {name: value for name, value in self.traits},
            "value_priority": list(self.value_priority),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PersonaManifest:
        """Read back what `as_dict` wrote, refusing anything it cannot name.

        A manifest from another algorithm or schema version is not a slightly wrong
        person: its numbers mean something else. Reading it anyway would let a build
        change quietly redraw a Kin, which is the one thing the persistence contract
        forbids.
        """

        algorithm = payload.get("algorithm")
        if algorithm != PERSONA_ALGORITHM:
            raise _reject(
                f"persona written by algorithm {algorithm!r}, this build reads "
                f"{PERSONA_ALGORITHM!r}"
            )
        version = payload.get("schema_version")
        if version != PERSONA_SCHEMA_VERSION:
            raise _reject(
                f"persona schema version {version!r}; this build reads {PERSONA_SCHEMA_VERSION}"
            )
        kin_id = payload.get("kin_id")
        seed = payload.get("persona_seed")
        if not isinstance(kin_id, str) or not kin_id:
            raise _reject("persona has no kin_id")
        if not isinstance(seed, str) or not seed:
            raise _reject("persona has no persona_seed")

        raw_traits = payload.get("traits")
        if not isinstance(raw_traits, dict):
            raise _reject("persona traits are not a mapping")
        trait_values = cast("dict[str, object]", raw_traits)
        if sorted(trait_values) != sorted(TRAIT_NAMES):
            raise _reject(
                f"persona traits must be exactly {TRAIT_NAMES}, got {sorted(trait_values)}"
            )
        traits: list[tuple[str, int]] = []
        for name in TRAIT_NAMES:
            value = trait_values[name]
            if not isinstance(value, int) or isinstance(value, bool):
                raise _reject(f"persona trait {name} is not an integer: {value!r}")
            if not TRAIT_FLOOR <= value <= TRAIT_CEILING:
                raise _reject(
                    f"persona trait {name} is {value}, outside {TRAIT_FLOOR}..{TRAIT_CEILING}"
                )
            traits.append((name, value))

        raw_priority = payload.get("value_priority")
        if not isinstance(raw_priority, list):
            raise _reject("persona value_priority is not a list of names")
        priority_items = cast("list[object]", raw_priority)
        names = [item for item in priority_items if isinstance(item, str)]
        if len(names) != len(priority_items):
            raise _reject("persona value_priority holds an entry that is not a name")
        if sorted(names) != sorted(VALUE_NAMES):
            raise _reject(f"persona value_priority must order {VALUE_NAMES}, got {names}")

        return cls(
            kin_id=kin_id,
            persona_seed=seed,
            algorithm=PERSONA_ALGORITHM,
            schema_version=PERSONA_SCHEMA_VERSION,
            traits=tuple(traits),
            value_priority=tuple(names),
        )


def _digest(kin_id: str, persona_seed: str) -> bytes:
    material = f"{PERSONA_ALGORITHM}\0{kin_id}\0{persona_seed}".encode()
    return hashlib.blake2b(material, digest_size=32).digest()


def derive_persona(kin_id: str, persona_seed: str) -> PersonaManifest:
    """The persona this `(kin_id, seed)` pair has always had.

    Values sit in `1..9` rather than around a neutral middle: a Kin whose traits all
    read the same is a Kin with no persona, and a distribution that flat would make
    the scheduler's tie-breaking the only thing that looks like character.
    """

    if not kin_id:
        raise _reject("derive_persona needs a kin_id")
    if not persona_seed:
        raise _reject("derive_persona needs a persona_seed")

    bytes_ = _digest(kin_id, persona_seed)
    span = TRAIT_CEILING - TRAIT_FLOOR + 1
    traits = tuple(
        (name, TRAIT_FLOOR + bytes_[index] % span) for index, name in enumerate(TRAIT_NAMES)
    )

    # Deterministic Fisher-Yates over the fixed value names, driven by the tail of
    # the same digest. The indices are taken from bytes the traits do not use.
    remaining = list(VALUE_NAMES)
    order: list[str] = []
    for offset in range(len(VALUE_NAMES)):
        source = len(TRAIT_NAMES) + offset
        order.append(remaining.pop(bytes_[source] % len(remaining)))

    return PersonaManifest(
        kin_id=kin_id,
        persona_seed=persona_seed,
        algorithm=PERSONA_ALGORITHM,
        schema_version=PERSONA_SCHEMA_VERSION,
        traits=traits,
        value_priority=tuple(order),
    )


def describe_for_backend(manifest: PersonaManifest) -> dict[str, object]:
    """The persona as the backend may show it: the person, not the operator's seed.

    The seed is the input that reproduces this manifest elsewhere, so it is not
    something a dashboard read model carries.
    """

    return {
        "algorithm": manifest.algorithm,
        "schema_version": manifest.schema_version,
        "traits": {name: value for name, value in manifest.traits},
        "value_priority": list(manifest.value_priority),
        "most_valued": manifest.value_priority[0],
    }
