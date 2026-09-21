"""Case registry and the candidate-to-tested promotion rule.

A case manifest declares what a test needs, what it asserts, and which oracle
inputs it is allowed to read. Two things are enforced here rather than trusted.

Oracle isolation is one: a case may read the oracle, and its ordinary inputs may
not, so the declaration itself is checked instead of being taken as a promise.
Promotion is the other: a work package may only be called tested when every
mandatory case has evidence that is both intact and actually a pass, and that was
produced against this version of the case definition.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

CASE_SCHEMA_VERSION = 1

_CASE_ID = re.compile(r"^[A-Z][A-Z0-9-]+-[0-9]{3}$")
_WORK_PACKAGE = re.compile(r"^W[0-9]{2}$")
_REQUIRED_KEYS = frozenset(
    {"schema_version", "case_id", "work_package", "mandatory", "inputs", "assertions"}
)
_OPTIONAL_KEYS = frozenset({"input_digests", "oracle_inputs"})


class CaseViolation(StrEnum):
    """Why a case manifest is not usable."""

    SCHEMA_VERSION_UNSUPPORTED = "SCHEMA_VERSION_UNSUPPORTED"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_CASE_ID = "INVALID_CASE_ID"
    INVALID_WORK_PACKAGE = "INVALID_WORK_PACKAGE"
    INVALID_MANDATORY = "INVALID_MANDATORY"
    INVALID_STRING_LIST = "INVALID_STRING_LIST"
    INVALID_INPUT_DIGESTS = "INVALID_INPUT_DIGESTS"
    NO_ASSERTIONS = "NO_ASSERTIONS"
    NOT_AN_OBJECT = "NOT_AN_OBJECT"


class PromotionBlock(StrEnum):
    """Why a work package cannot be called tested yet."""

    CASE_WITHOUT_EVIDENCE = "CASE_WITHOUT_EVIDENCE"
    EVIDENCE_NOT_VERIFIED = "EVIDENCE_NOT_VERIFIED"
    EVIDENCE_IS_NOT_A_PASS = "EVIDENCE_IS_NOT_A_PASS"
    CASE_VERSION_MISMATCH = "CASE_VERSION_MISMATCH"
    NO_MANDATORY_CASES = "NO_MANDATORY_CASES"


@dataclass(frozen=True, slots=True)
class CaseManifest:
    """One reviewed case definition, with the digest that names its version."""

    case_id: str
    work_package: str
    mandatory: bool
    inputs: tuple[str, ...]
    input_digests: tuple[tuple[str, str], ...]
    assertions: tuple[str, ...]
    oracle_inputs: tuple[str, ...]
    digest: str

    @property
    def reads_oracle(self) -> bool:
        return bool(self.oracle_inputs)

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": CASE_SCHEMA_VERSION,
            "case_id": self.case_id,
            "work_package": self.work_package,
            "mandatory": self.mandatory,
            "inputs": list(self.inputs),
            "input_digests": dict(self.input_digests),
            "assertions": list(self.assertions),
            "oracle_inputs": list(self.oracle_inputs),
            "digest": self.digest,
        }


def _strings(document: Mapping[str, object], key: str) -> tuple[str, ...] | None:
    """Return a string list, or None when the field is not one.

    Returning None rather than an empty tuple matters: an empty tuple would let a
    malformed `assertions` list read as "a case that asserts nothing", and an
    empty `inputs` list as "a case with no inputs", instead of failing closed.
    """

    value = document.get(key)
    if not isinstance(value, list):
        return None
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        return None
    return tuple(cast(str, item) for item in items)


def _input_digests(document: Mapping[str, object]) -> tuple[tuple[str, str], ...] | None:
    """Return the reviewed input pins, or None when the optional map is malformed."""

    value = document.get("input_digests", {})
    if not isinstance(value, Mapping):
        return None
    items = cast(Mapping[object, object], value)
    if not all(
        isinstance(path, str)
        and bool(path)
        and isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
        for path, digest in items.items()
    ):
        return None
    return tuple(sorted(cast(Mapping[str, str], value).items()))


def parse_case_manifest(
    document: Mapping[str, object],
) -> tuple[CaseManifest | None, tuple[CaseViolation, ...]]:
    """Validate one parsed case document, returning the case or its violations."""

    found: set[CaseViolation] = set()
    if document.get("schema_version") != CASE_SCHEMA_VERSION:
        found.add(CaseViolation.SCHEMA_VERSION_UNSUPPORTED)

    unknown = sorted(set(document) - _REQUIRED_KEYS - _OPTIONAL_KEYS)
    if unknown:
        found.add(CaseViolation.UNKNOWN_FIELD)
    missing = sorted(_REQUIRED_KEYS - set(document))
    if missing:
        found.add(CaseViolation.MISSING_FIELD)

    case_id = document.get("case_id")
    if not isinstance(case_id, str) or not _CASE_ID.fullmatch(case_id):
        found.add(CaseViolation.INVALID_CASE_ID)

    work_package = document.get("work_package")
    if not isinstance(work_package, str) or not _WORK_PACKAGE.fullmatch(work_package):
        found.add(CaseViolation.INVALID_WORK_PACKAGE)

    mandatory = document.get("mandatory")
    if not isinstance(mandatory, bool):
        # A truthy string would otherwise read as "not mandatory" and drop the
        # case out of the promotion gate entirely.
        found.add(CaseViolation.INVALID_MANDATORY)

    inputs = _strings(document, "inputs")
    input_digests = _input_digests(document)
    assertions = _strings(document, "assertions")
    # `oracle_inputs` is optional, so absence means "reads no oracle"; only a
    # present-but-malformed value is an error.
    oracle_inputs = () if "oracle_inputs" not in document else _strings(document, "oracle_inputs")
    if inputs is None or oracle_inputs is None or assertions is None:
        found.add(CaseViolation.INVALID_STRING_LIST)
        inputs = inputs or ()
        oracle_inputs = oracle_inputs or ()
        assertions = assertions or ()
    if input_digests is None:
        found.add(CaseViolation.INVALID_INPUT_DIGESTS)
        input_digests = ()
    if not assertions:
        # The schema requires at least one assertion; a case that asserts nothing
        # cannot pass or fail and so cannot gate anything.
        found.add(CaseViolation.NO_ASSERTIONS)

    if found:
        return None, tuple(sorted(found))

    return (
        CaseManifest(
            case_id=cast(str, case_id),
            work_package=cast(str, work_package),
            mandatory=cast(bool, mandatory),
            inputs=inputs,
            input_digests=input_digests,
            assertions=assertions,
            oracle_inputs=oracle_inputs,
            digest=hashlib.sha256(
                json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        ),
        (),
    )


@dataclass(frozen=True, slots=True)
class CaseRegistry:
    """Every reviewed case, keyed by identifier."""

    cases: tuple[CaseManifest, ...]

    def by_id(self) -> dict[str, CaseManifest]:
        return {case.case_id: case for case in self.cases}

    def for_work_package(self, work_package: str) -> tuple[CaseManifest, ...]:
        return tuple(case for case in self.cases if case.work_package == work_package)

    def mandatory_cases(self, work_package: str | None = None) -> tuple[CaseManifest, ...]:
        return tuple(
            case
            for case in self.cases
            if case.mandatory and (work_package is None or case.work_package == work_package)
        )

    def duplicate_ids(self) -> tuple[str, ...]:
        seen: set[str] = set()
        repeated: set[str] = set()
        for case in self.cases:
            if case.case_id in seen:
                repeated.add(case.case_id)
            seen.add(case.case_id)
        return tuple(sorted(repeated))


@dataclass(frozen=True, slots=True)
class CaseEvidence:
    """What one bundle says about one case, after the bundle was verified."""

    case_id: str
    case_version: str
    verified: bool
    passed: bool


@dataclass(frozen=True, slots=True)
class PromotionVerdict:
    promotable: bool
    blocking_cases: tuple[str, ...]
    blocks: tuple[PromotionBlock, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "promotable": self.promotable,
            "blocking_cases": list(self.blocking_cases),
            "blocks": [block.value for block in self.blocks],
        }


def evaluate_promotion(
    cases: Sequence[CaseManifest], evidence: Sequence[CaseEvidence]
) -> PromotionVerdict:
    """Decide whether a work package may be called tested.

    Only mandatory cases gate. A bundle has to have verified, have recorded a
    pass, name this case, and have been produced against this version of the case
    definition; anything less leaves the case blocking.
    """

    mandatory = [case for case in cases if case.mandatory]
    if not mandatory:
        return PromotionVerdict(
            promotable=False, blocking_cases=(), blocks=(PromotionBlock.NO_MANDATORY_CASES,)
        )

    by_case: dict[str, list[CaseEvidence]] = {}
    for item in evidence:
        by_case.setdefault(item.case_id, []).append(item)

    blocking: list[str] = []
    blocks: set[PromotionBlock] = set()
    for case in mandatory:
        candidates = by_case.get(case.case_id, [])
        if not candidates:
            blocking.append(case.case_id)
            blocks.add(PromotionBlock.CASE_WITHOUT_EVIDENCE)
            continue
        satisfied = False
        for item in candidates:
            if item.case_version != case.digest:
                blocks.add(PromotionBlock.CASE_VERSION_MISMATCH)
                continue
            if not item.verified:
                blocks.add(PromotionBlock.EVIDENCE_NOT_VERIFIED)
                continue
            if not item.passed:
                blocks.add(PromotionBlock.EVIDENCE_IS_NOT_A_PASS)
                continue
            satisfied = True
        if not satisfied:
            blocking.append(case.case_id)

    ordered_blocking = tuple(sorted(blocking))
    return PromotionVerdict(
        promotable=not ordered_blocking,
        blocking_cases=ordered_blocking,
        blocks=tuple(sorted(blocks)),
    )
