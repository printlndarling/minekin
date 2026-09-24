"""Case registry and the candidate-to-tested promotion rule.

A case manifest declares what a test needs, what it asserts, and which oracle
inputs it is allowed to read. Two things are enforced here rather than trusted.

Oracle isolation is one: a case may read the oracle, and its ordinary inputs may
not, so the declaration itself is checked instead of being taken as a promise.
Promotion is the other: a work package may only be called tested when every
mandatory case has evidence that is both intact and actually a pass, and that was
produced against this version of the case definition.

There is a third, and it is the one this module could not previously state. Both
rules above read the registry, so both are silent about a case nobody wrote:
"every mandatory case passed" is a true sentence about a case set with holes in it,
and it is the sentence that turns a promotion gate into a certificate for work
nobody did. `REQUIRED_CASES` is the reviewed answer to *what the contracts require*
— which gates need which cases, each entry citing the document it was read out of —
and `CaseRegistry.requirement` reads it against a registry to say what is missing,
what is filed under the wrong work package, and what is present without gating.
The first two are inventory failures and block promotion; the last remains visible
without silently turning every contract case into a mandatory evidence case.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, cast

CASE_SCHEMA_VERSION = 1

_CASE_ID = re.compile(r"^[A-Z][A-Z0-9-]+-[0-9]{3}$")
#: Every work package a case may name, and nothing else.
#:
#: Two kinds of name. `W00`-`W80` are the phases of the core slice, which is what the
#: roadmap numbers. The other three are the surfaces the validation contract grades
#: *independently*: `p0-core` for the slice itself, `p0-nav-exp` for the navigation
#: experiment, `host-integrated` for the world a Kin hosts. They are separate grades on
#: purpose — the contract is explicit that a host result must not be borrowed to claim
#: the core passed, or the other way round — so a case says which grade it is evidence
#: for, and a case that evidences a level spanning phases (L3's LAN join is built on no
#: single phase) names the surface rather than a phase number that is not its own.
#:
#: This replaced a placeholder. Those cases said `W90`, which named nothing: the
#: roadmap stops at W80 and the host work is graded as `host-integrated`, so a reader
#: of a bundle could not tell what package its evidence belonged to — or check that
#: against anything. A closed list is what makes "which package is this?" answerable,
#: and it is why `W90` now fails rather than being accepted as a shape.
WORK_PACKAGES: Final[tuple[str, ...]] = (
    "W00",
    "W10",
    "W20",
    "W30",
    "W40",
    "W50",
    "W60",
    "W70",
    "W80",
    "p0-core",
    "p0-nav-exp",
    "host-integrated",
)
_REQUIRED_KEYS = frozenset(
    {"schema_version", "case_id", "work_package", "mandatory", "inputs", "assertions"}
)
_OPTIONAL_KEYS = frozenset({"input_digests", "assertion_digests", "oracle_inputs"})


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
    INVALID_ASSERTION_DIGESTS = "INVALID_ASSERTION_DIGESTS"
    NO_ASSERTIONS = "NO_ASSERTIONS"
    NOT_AN_OBJECT = "NOT_AN_OBJECT"


class PromotionBlock(StrEnum):
    """Why a work package cannot be called tested yet."""

    CASE_WITHOUT_EVIDENCE = "CASE_WITHOUT_EVIDENCE"
    EVIDENCE_NOT_VERIFIED = "EVIDENCE_NOT_VERIFIED"
    EVIDENCE_IS_NOT_A_PASS = "EVIDENCE_IS_NOT_A_PASS"
    CASE_VERSION_MISMATCH = "CASE_VERSION_MISMATCH"
    EVIDENCE_DISAGREES_WITH_ITS_BYTES = "EVIDENCE_DISAGREES_WITH_ITS_BYTES"
    NO_MANDATORY_CASES = "NO_MANDATORY_CASES"
    #: A case a contract requires has no manifest in the registry at all. Separate
    #: from every reason above it, which are about a case that exists and whose
    #: evidence falls short: this one says there was never anything to fall short,
    #: and a verdict that could not say so was a verdict that read clean over a hole.
    REQUIRED_CASE_NOT_REGISTERED = "REQUIRED_CASE_NOT_REGISTERED"
    #: A required case is registered under a work package the inventory does not
    #: expect. It has moved between gates, so which gate its evidence answers for is
    #: no longer something a reader can tell — and a case judged against the wrong
    #: gate is a case that passes the wrong question.
    REQUIRED_CASE_MISATTRIBUTED = "REQUIRED_CASE_MISATTRIBUTED"


class ReJudge(StrEnum):
    """What came of reaching a sealed bundle's verdict a second time.

    A digest proves the bytes did not move. It does not prove that those bytes
    support the verdict written over them, so a bundle whose manifest was rewritten
    — `failures` cleared, `observed` filled in from `expected`, `result` set to PASS,
    and the digest file regenerated — verifies clean. This is that second reading.

    Only `DISAGREES` blocks, and the distinction is deliberate: it is a positive
    finding that the bytes contradict the verdict, which is a fact about the bundle.
    `UNJUDGED` is a fact about the reader — a bundle sealed before its inputs were
    recorded, or one damaged in a way the assertions cannot read — and is reported
    with its reason rather than treated as agreement. Removing the inputs from a
    bundle does not reach this state: dropping a declared artifact, or leaving one
    undeclared, is caught by verification, so this is not a road out of the gate.
    """

    AGREES = "AGREES"
    DISAGREES = "DISAGREES"
    #: Attempted and no verdict could be reached. Not the same as agreeing, and not
    #: the same as disagreeing: the bundle is silent rather than contradicted.
    UNJUDGED = "UNJUDGED"
    #: Nobody asked. Stated rather than defaulted, because the producers are not
    #: equivalent: the adapter that verifies a bundle cannot re-judge it — the
    #: assertions are test-domain code — and the report that can says so by naming
    #: this value per bundle.
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


# ---------------------------------------------------------------------------
# What the contracts require
# ---------------------------------------------------------------------------
#
# Every rule above reads the registry, so every one of them is silent about a case
# nobody wrote: `mandatory`, evidence, version and re-judgement are all questions
# asked of a case that is present. This is the list the registry is read *against*,
# and it is the one thing here that is not derived from anything — a reviewed
# reading of six contracts, each entry carrying the document it was read out of.
#
# A case belongs to the gates that need it (`required_for`) and to one work package
# it is expected to be registered under (`expected_work_package`). Those are two
# different fields because they answer two different questions: a phase of the core
# slice is graded on its own *and* as part of `p0-core`, and a case whose phase is
# not a gate of its own is required by the slice alone. What a *gate* requires is
# therefore a view over this list, not a work-package grouping of it — which is what
# keeps a HOST hole from blocking W40.
#
# The list is not scraped from the contracts. Contracts are prose, and a list
# extracted from prose changes meaning when a paragraph is reworded; what is checked
# mechanically is the weaker, checkable thing — that every identifier below appears
# verbatim in the document it cites (`tests/contract/test_case_coverage.py`). And a
# surface with a contract and no frozen numbering is reported as a planning gap
# rather than numbered: inventing `PERSIST-001` would be this inventory fabricating
# the thing it exists to check.

#: The inventory's own version. A shape change to `RequiredCase` changes what every
#: consumer reads, so a document that does not say which shape it is in is a
#: document whose reader is guessing.
REQUIRED_CASE_INVENTORY_VERSION: Final[int] = 1


class ValidationClass(StrEnum):
    """What it takes to satisfy a required case.

    Not which judge decides the fixture registered for it. A case can require a real
    run and have a fixture whose assertions are all performed locally: that is a case
    with its repository half and not its run half, which is the ordinary state here
    and one a report should be able to show.
    """

    #: Closed by this repository's own material — the test suite, the tools, the
    #: fixtures — with no Minecraft process, no real network, no real fault.
    LOCAL_ONLY = "local-only"
    #: Needs something local material cannot produce: a real client or server, a real
    #: thread or callback ordering, a real fault, a real mount, a built artifact.
    RUNTIME_REQUIRED = "runtime-required"


VALIDATION_CLASSES: Final[tuple[ValidationClass, ...]] = (
    ValidationClass.LOCAL_ONLY,
    ValidationClass.RUNTIME_REQUIRED,
)

#: The frozen gates: the surfaces this inventory is read against, and the only names
#: `required_for` may use. Every one of them is a work package, and every one has at
#: least one required case — a gate that required nothing would read as coverage.
#:
#: `W80` is deliberately absent. It is a work package, but the navigation experiment
#: is graded as `p0-nav-exp`, which is its own surface in this list; binding NAV to
#: the phase number would put one experiment's evidence under two names.
REQUIRED_GATES: Final[tuple[str, ...]] = (
    "W00",
    "W10",
    "W20",
    "W30",
    "W40",
    "W50",
    "W60",
    "W70",
    "p0-core",
    "p0-nav-exp",
    "host-integrated",
)

_VALIDATION = "docs/p0-validation-evidence-contract.md"
_ADMISSION = "docs/p0-remote-admission-contract.md"
_OFFLINE = "docs/p0-offline-session-compatibility-contract.md"
_STORAGE = "docs/hosted-world-storage-lifecycle-contract.md"
_CONTROL = "docs/hosted-world-control-boundary-contract.md"
_COMMIT = "docs/hosted-world-commit-recovery-contract.md"


@dataclass(frozen=True, slots=True)
class RequiredCase:
    """One case a contract requires, and where that requirement is written.

    `anchor` is a repository-relative document path rather than a section: a citation
    a machine can check is a path, and the section is in the comment beside the entry.
    """

    case_id: str
    #: The work package a manifest for this case is expected to name. A case filed
    #: under another one has moved between gates, which is a fact about the registry
    #: this inventory can name.
    expected_work_package: str
    #: The gates whose completion needs this case. Never empty.
    required_for: tuple[str, ...]
    validation_class: ValidationClass
    anchor: str

    def as_document(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "expected_work_package": self.expected_work_package,
            "required_for": list(self.required_for),
            "validation_class": self.validation_class.value,
            "anchor": self.anchor,
        }


def _phase_cases(
    anchor: str, validation_class: ValidationClass, phase: str, *case_ids: str
) -> tuple[RequiredCase, ...]:
    """Cases of one phase of the core slice: required by the phase and by the slice."""

    return tuple(
        RequiredCase(case_id, phase, (phase, "p0-core"), validation_class, anchor)
        for case_id in case_ids
    )


def _surface_cases(
    anchor: str, validation_class: ValidationClass, surface: str, *case_ids: str
) -> tuple[RequiredCase, ...]:
    """Cases graded on one surface: required by that surface and by nothing else."""

    return tuple(
        RequiredCase(case_id, surface, (surface,), validation_class, anchor) for case_id in case_ids
    )


#: Every case the six contracts require, grouped by the document it was read from.
#:
#: Reviewing this list means reading the cited section, not the entries: the entries
#: are transcribed from it. Where a contract's own note says which half of a
#: criterion is closed locally, that is what decides the validation class.
REQUIRED_CASES: Final[tuple[RequiredCase, ...]] = (
    # `p0-validation-evidence-contract.md` § "P0 mandatory case set" — items 1-10, 13
    # and 14, plus the L0 repository check the same document records as measured.
    *_phase_cases(_VALIDATION, ValidationClass.LOCAL_ONLY, "W00", "W00-CONTRACT-001"),
    *_phase_cases(_VALIDATION, ValidationClass.LOCAL_ONLY, "W10", "CORE-001"),
    *_phase_cases(_VALIDATION, ValidationClass.RUNTIME_REQUIRED, "W20", "CORE-010"),
    *_surface_cases(_VALIDATION, ValidationClass.RUNTIME_REQUIRED, "p0-core", "CORE-030"),
    *_phase_cases(_VALIDATION, ValidationClass.RUNTIME_REQUIRED, "W40", "CORE-020"),
    *_phase_cases(_VALIDATION, ValidationClass.RUNTIME_REQUIRED, "W50", "CORE-080"),
    *_phase_cases(
        _VALIDATION,
        ValidationClass.RUNTIME_REQUIRED,
        "W60",
        "CORE-040",
        "CORE-050",
        "CORE-070",
    ),
    # `CORE-060` is the case the contract splits by process boundary: one run injects
    # one fault, and a case id takes any satisfying bundle, so the kill targets are
    # separate ids rather than one id no single bundle could satisfy.
    *_phase_cases(
        _VALIDATION,
        ValidationClass.RUNTIME_REQUIRED,
        "W70",
        "CORE-060",
        "CORE-060-CLIENT-001",
        "CORE-060-SERVER-001",
        "CORE-090",
        "CORE-100",
    ),
    *_surface_cases(_VALIDATION, ValidationClass.RUNTIME_REQUIRED, "p0-nav-exp", "NAV-EXP-010"),
    # `p0-remote-admission-contract.md` § "P0 证据用例": thirteen rows, none of which
    # is settled by this repository's own material — each begins with a connection to
    # a controlled server. Both contracts name `ADMIT-100` and `ADMIT-110`; what they
    # disagree about is what those two scenarios *are*, which is a contract question
    # and not a field of this list, whose entries carry no scenario at all.
    *_phase_cases(
        _ADMISSION,
        ValidationClass.RUNTIME_REQUIRED,
        "W40",
        "ADMIT-001",
        "ADMIT-010",
        "ADMIT-020",
        "ADMIT-030",
        "ADMIT-040",
        "ADMIT-050",
        "ADMIT-060",
        "ADMIT-080",
        "ADMIT-090",
        "ADMIT-100",
        "ADMIT-110",
    ),
    *_phase_cases(_ADMISSION, ValidationClass.RUNTIME_REQUIRED, "W50", "ADMIT-070", "ADMIT-120"),
    # `p0-offline-session-compatibility-contract.md` § "Case set": eleven contract rows,
    # all of them gating W30, carried here as thirteen ids because one of those rows is
    # one-run-per-identity-column. `OFFLINE-001` is the one the contract's own note says
    # the existing unit tests already perform; 040 and 050 have their declaration half
    # closed and their real-Session half explicitly still open.
    *_phase_cases(_OFFLINE, ValidationClass.LOCAL_ONLY, "W30", "OFFLINE-001"),
    # `OFFLINE-030` is the row the contract splits by identity column, for the same
    # reason `CORE-060` splits by kill target: one run starts one candidate, so no
    # single bundle can satisfy "OFF-A and OFF-B joined separately". The parent keeps
    # the one criterion that holds whichever column ran, and each child carries the
    # attribution that can only be true of one.
    *_phase_cases(
        _OFFLINE,
        ValidationClass.RUNTIME_REQUIRED,
        "W30",
        "OFFLINE-010",
        "OFFLINE-020",
        "OFFLINE-030",
        "OFFLINE-030-PRISM-PARITY-001",
        "OFFLINE-030-ENUM-ALIGNED-001",
        "OFFLINE-040",
        "OFFLINE-050",
        "OFFLINE-060",
        "OFFLINE-070",
        "OFFLINE-080",
        "OFFLINE-090",
        "OFFLINE-100",
    ),
    # The three host contracts, graded as one independent surface. Even the cases
    # whose decision half is implemented say so in their own notes.
    *_surface_cases(
        _STORAGE,
        ValidationClass.RUNTIME_REQUIRED,
        "host-integrated",
        "HOST-001",
        "HOST-010",
        "HOST-020",
        "HOST-030",
        "HOST-040",
        "HOST-050",
        "HOST-060",
        "HOST-070",
        "HOST-080",
        "HOST-090",
        "HOST-100",
    ),
    *_surface_cases(
        _CONTROL,
        ValidationClass.LOCAL_ONLY,
        "host-integrated",
        "HOSTCTL-001",
        "HOSTCTL-010",
        "HOSTCTL-060",
    ),
    *_surface_cases(
        _CONTROL,
        ValidationClass.RUNTIME_REQUIRED,
        "host-integrated",
        "HOSTCTL-020",
        "HOSTCTL-030",
        "HOSTCTL-040",
        "HOSTCTL-050",
        "HOSTCTL-070",
        "HOSTCTL-080",
        "HOSTCTL-090",
    ),
    *_surface_cases(
        _COMMIT,
        ValidationClass.RUNTIME_REQUIRED,
        "host-integrated",
        "HOSTCOMMIT-001",
        "HOSTCOMMIT-010",
        "HOSTCOMMIT-020",
        "HOSTCOMMIT-030",
        "HOSTCOMMIT-040",
        "HOSTCOMMIT-050",
        "HOSTCOMMIT-060",
        "HOSTCOMMIT-070",
        "HOSTCOMMIT-080",
        "HOSTCOMMIT-090",
        "HOSTCOMMIT-100",
    ),
    *_surface_cases(_COMMIT, ValidationClass.LOCAL_ONLY, "host-integrated", "HOSTCOMMIT-110"),
)

#: The reviewed v1 identifiers form a closed vocabulary for injected/subset views.
#: The canonical inventory remains the source of truth; callers may ask about a
#: subset of it, but may not introduce a case the reviewed inventory does not name.
_REQUIRED_CASE_IDS: Final[frozenset[str]] = frozenset(entry.case_id for entry in REQUIRED_CASES)


class PlanningGapStatus(StrEnum):
    """Why a surface has requirements and no case identifiers to check."""

    #: Its contract states requirements and numbers no cases.
    UNFROZEN_CASE_IDS = "UNFROZEN_CASE_IDS"


@dataclass(frozen=True, slots=True)
class PlanningGap:
    """A surface the plan expects cases for, with no numbering to require yet.

    Reported and never gating: `required_for` is empty, so no gate can be blocked by
    one. Stated rather than omitted because "no required cases here" and "this
    surface has not been numbered yet" are different facts, and a report showing only
    the first would read as a complete inventory.
    """

    surface: str
    status: PlanningGapStatus
    #: Empty, and that is what makes it a gap rather than a requirement.
    required_for: tuple[str, ...]
    anchor: str
    reason: str

    def as_document(self) -> dict[str, object]:
        return {
            "surface": self.surface,
            "status": self.status.value,
            "required_for": list(self.required_for),
            "anchor": self.anchor,
            "reason": self.reason,
        }


PLANNING_GAPS: Final[tuple[PlanningGap, ...]] = (
    PlanningGap(
        surface="PERSIST",
        status=PlanningGapStatus.UNFROZEN_CASE_IDS,
        required_for=(),
        anchor="docs/persistence-recovery-contract.md",
        reason=(
            "the persistence and recovery contract states requirements and numbers no "
            "cases, so there is nothing this inventory could check against. Numbering "
            "one here would be the inventory inventing the cases it exists to verify."
        ),
    ),
)


class RequiredCaseViolation(StrEnum):
    """Why the required-case inventory cannot be read as written."""

    INVALID_CASE_ID = "INVALID_CASE_ID"
    UNKNOWN_CASE_ID = "UNKNOWN_CASE_ID"
    UNKNOWN_GATE = "UNKNOWN_GATE"
    UNKNOWN_PACKAGE = "UNKNOWN_PACKAGE"
    EMPTY_REQUIRED_FOR = "EMPTY_REQUIRED_FOR"
    DUPLICATE_CASE_ID = "DUPLICATE_CASE_ID"


def required_case_violations(
    required: Sequence[RequiredCase] = REQUIRED_CASES,
) -> tuple[tuple[RequiredCaseViolation, str], ...]:
    """Every reason the inventory cannot be read, each naming the entry it is about.

    The subject is the offending case id, with the name that is wrong after a colon
    when the reason is about one of its fields — so a violation sends its reader to
    one entry and one field rather than back through all seventy-two.
    """

    found: set[tuple[RequiredCaseViolation, str]] = set()
    seen: set[str] = set()
    for entry in required:
        if _CASE_ID.fullmatch(entry.case_id) is None:
            found.add((RequiredCaseViolation.INVALID_CASE_ID, entry.case_id))
        elif entry.case_id not in _REQUIRED_CASE_IDS:
            found.add((RequiredCaseViolation.UNKNOWN_CASE_ID, entry.case_id))
        for gate in sorted(set(entry.required_for) - set(REQUIRED_GATES)):
            found.add((RequiredCaseViolation.UNKNOWN_GATE, f"{entry.case_id}:{gate}"))
        if not entry.required_for:
            found.add((RequiredCaseViolation.EMPTY_REQUIRED_FOR, entry.case_id))
        if entry.expected_work_package not in REQUIRED_GATES:
            found.add(
                (
                    RequiredCaseViolation.UNKNOWN_PACKAGE,
                    f"{entry.case_id}:{entry.expected_work_package}",
                )
            )
        if entry.case_id in seen:
            found.add((RequiredCaseViolation.DUPLICATE_CASE_ID, entry.case_id))
        seen.add(entry.case_id)
    return tuple(sorted(found))


def required_for_gates(
    gates: Sequence[str], required: Sequence[RequiredCase] = REQUIRED_CASES
) -> tuple[RequiredCase, ...]:
    """The inventory entries these gates require, in the inventory's own order.

    Membership, not grouping: a case required by both a phase and the slice appears
    once here and answers to both, which is why this is a filter over `required_for`
    and not a lookup by work package.
    """

    unknown = tuple(sorted(set(gates) - set(REQUIRED_GATES)))
    if unknown:
        raise ValueError("unknown required-case gate(s): " + ", ".join(unknown))
    violations = required_case_violations(required)
    if violations:
        rendered = ", ".join(f"{reason.value} ({subject})" for reason, subject in violations)
        raise ValueError("the required-case inventory is not usable: " + rendered)

    wanted = set(gates)
    return tuple(entry for entry in required if wanted & set(entry.required_for))


def required_case_inventory(
    required: Sequence[RequiredCase] = REQUIRED_CASES,
) -> dict[str, object]:
    """The inventory as a versioned document, so a consumer reads one shape."""

    return {
        "schema_version": REQUIRED_CASE_INVENTORY_VERSION,
        "gates": list(REQUIRED_GATES),
        "totals": {
            "required": len(required),
            "by_validation_class": {
                item.value: sum(1 for entry in required if entry.validation_class is item)
                for item in VALIDATION_CLASSES
            },
        },
        "cases": [entry.as_document() for entry in required],
        "planning_gaps": [gap.as_document() for gap in PLANNING_GAPS],
    }


@dataclass(frozen=True, slots=True)
class Requirement:
    """What a gate requires of the registry it is being judged with.

    Two completeness failures block before evidence is considered: a case nobody
    wrote, and a case written under a work package it does not belong to.
    `non_mandatory` is diagnostic rather than a third completeness failure: required
    presence and mandatory evidence are deliberately separate contract concepts.
    """

    gates: tuple[str, ...]
    absent: tuple[str, ...] = ()
    misattributed: tuple[str, ...] = ()
    non_mandatory: tuple[str, ...] = ()

    @property
    def satisfied(self) -> bool:
        return not (self.absent or self.misattributed)

    def as_document(self) -> dict[str, object]:
        return {
            "gates": list(self.gates),
            "absent": list(self.absent),
            "misattributed": list(self.misattributed),
            "non_mandatory": list(self.non_mandatory),
            "satisfied": self.satisfied,
        }


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
    #: Assertion name -> the digest of the source that performs it, recorded by the
    #: case rather than derived here. It sits in the manifest because the manifest is
    #: what `digest` — the case version a bundle is checked against — is taken over:
    #: a case version that covered only the *names* of its assertions was a version
    #: that could mean two different checks. Empty when a case has not recorded any,
    #: which the case-assertion gate reports rather than this parser refusing.
    assertion_digests: tuple[tuple[str, str], ...] = ()

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
            "assertion_digests": dict(self.assertion_digests),
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


def _digest_map(document: Mapping[str, object], key: str) -> tuple[tuple[str, str], ...] | None:
    """Return a reviewed map of name -> digest, or None when the optional field is malformed.

    One reader for both maps rather than two that agree today: `input_digests` pins the
    bytes outside the case that it means, and `assertion_digests` pins the source that
    performs it. They are the same shape with the same requirement — a name and a
    lowercase sha256 — and a rule copied for the second one is a rule that is already
    drifting from the first.
    """

    value = document.get(key, {})
    if not isinstance(value, Mapping):
        return None
    items = cast(Mapping[object, object], value)
    if not all(
        isinstance(name, str)
        and bool(name)
        and isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
        for name, digest in items.items()
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
    if not isinstance(work_package, str) or work_package not in WORK_PACKAGES:
        found.add(CaseViolation.INVALID_WORK_PACKAGE)

    mandatory = document.get("mandatory")
    if not isinstance(mandatory, bool):
        # A truthy string would otherwise read as "not mandatory" and drop the
        # case out of the promotion gate entirely.
        found.add(CaseViolation.INVALID_MANDATORY)

    inputs = _strings(document, "inputs")
    input_digests = _digest_map(document, "input_digests")
    assertion_digests = _digest_map(document, "assertion_digests")
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
    if assertion_digests is None:
        found.add(CaseViolation.INVALID_ASSERTION_DIGESTS)
        assertion_digests = ()
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
            assertion_digests=assertion_digests,
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

    def required_cases(
        self, *gates: str, required: Sequence[RequiredCase] = REQUIRED_CASES
    ) -> tuple[CaseManifest, ...]:
        """The registered cases these gates require, in the registry's own order.

        The set to judge, and not "the cases of some work package": a gate's cases
        are what the inventory says they are, so a case filed elsewhere cannot make a
        gate pass and a case belonging to another gate cannot make it fail.
        """

        wanted = {entry.case_id for entry in required_for_gates(gates, required)}
        return tuple(case for case in self.cases if case.case_id in wanted)

    def requirement(
        self, *gates: str, required: Sequence[RequiredCase] = REQUIRED_CASES
    ) -> Requirement:
        """What these gates require of this registry.

        The reading the fixture walk cannot do. Every other question this module
        answers is asked of a case that is present — is it mandatory, has it evidence,
        is that evidence current — and a case nobody wrote answers all of them by not
        being asked. This one has an answer either way. It also reports which present
        cases are non-mandatory without treating that diagnostic as an inventory
        failure or silently rewriting the contract's mandatory subset.
        """

        held = self.by_id()
        absent: list[str] = []
        misattributed: list[str] = []
        non_mandatory: list[str] = []
        for entry in required_for_gates(gates, required):
            case = held.get(entry.case_id)
            if case is None:
                absent.append(entry.case_id)
            elif case.work_package != entry.expected_work_package:
                misattributed.append(entry.case_id)
            elif not case.mandatory:
                non_mandatory.append(entry.case_id)
        return Requirement(
            gates=tuple(gates),
            absent=tuple(sorted(absent)),
            misattributed=tuple(sorted(misattributed)),
            non_mandatory=tuple(sorted(non_mandatory)),
        )


@dataclass(frozen=True, slots=True)
class CaseEvidence:
    """What one bundle says about one case, after the bundle was verified."""

    case_id: str
    case_version: str
    verified: bool
    passed: bool
    #: Required, so that every producer says what it did rather than inheriting an
    #: answer. `NOT_ATTEMPTED` is what a caller that cannot re-judge reports, and it
    #: is why the rule below can only be enforced by a caller that can.
    re_judged: ReJudge
    run_id: str = ""
    attempt_sequence: int | None = None
    supersedes_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class PromotionVerdict:
    promotable: bool
    blocking_cases: tuple[str, ...]
    blocks: tuple[PromotionBlock, ...]
    #: The gate requirement the verdict was judged against, or None when the caller
    #: asked only the evidence question. Carried rather than recomputed, so a reader
    #: of a refusal does not have to re-derive which cases the gate wanted.
    requirement: Requirement | None = None

    def as_document(self) -> dict[str, object]:
        return {
            "promotable": self.promotable,
            "blocking_cases": list(self.blocking_cases),
            "blocks": [block.value for block in self.blocks],
            "requirement": None if self.requirement is None else self.requirement.as_document(),
        }


def evaluate_promotion(
    cases: Sequence[CaseManifest],
    evidence: Sequence[CaseEvidence],
    *,
    requirement: Requirement | None = None,
) -> PromotionVerdict:
    """Decide whether a work package may be called tested.

    Only mandatory cases gate on evidence. A bundle has to have verified, have
    recorded a pass, name this case, have been produced against this version of the
    case definition, and — when the caller was able to reach its verdict a second
    time — have that second reading agree. Anything less leaves the case blocking.

    The last of those is the one this rule cannot enforce on its own: reaching a
    verdict again needs the assertions, which are test-domain code, so a caller that
    cannot do it reports `NOT_ATTEMPTED` and is not blocked by it. That is a real
    limit and it is stated here rather than hidden behind a default — the report a
    person acts on does re-judge, and `NOT_ATTEMPTED` in it would be a caller that
    skipped a step, not a bundle that failed one.

    `requirement` is the gate's precondition. Omitting it asks the narrower question
    — is *this* evidence what *this* case requires — which is what the evidence
    rule's own callers ask; `adapters.evidence.promotion` and the promotion report
    pass `CaseRegistry.requirement` for the gate they are judging, and that is what
    makes a verdict about whether a work package may be called tested rather than
    only about the bundles somebody happened to present.

    An unsatisfied requirement blocks whatever else is true, including when there are
    no mandatory cases: a case set with holes in it is exactly the state that
    produces no mandatory cases, and a verdict reporting only "nothing to gate on"
    there would be reporting the gap as a non-event.
    """

    mandatory = [case for case in cases if case.mandatory]
    blocking: list[str] = []
    blocks: set[PromotionBlock] = set()
    if requirement is not None:
        for names, block in (
            (requirement.absent, PromotionBlock.REQUIRED_CASE_NOT_REGISTERED),
            (requirement.misattributed, PromotionBlock.REQUIRED_CASE_MISATTRIBUTED),
        ):
            if names:
                blocks.add(block)
                blocking.extend(names)

    if not mandatory:
        blocks.add(PromotionBlock.NO_MANDATORY_CASES)
        return PromotionVerdict(
            promotable=False,
            blocking_cases=tuple(sorted(blocking)),
            blocks=tuple(sorted(blocks)),
            requirement=requirement,
        )

    by_case: dict[str, list[CaseEvidence]] = {}
    for item in evidence:
        by_case.setdefault(item.case_id, []).append(item)

    for case in mandatory:
        candidates = by_case.get(case.case_id, [])
        if not candidates:
            blocking.append(case.case_id)
            blocks.add(PromotionBlock.CASE_WITHOUT_EVIDENCE)
            continue
        sequenced = [item for item in candidates if item.attempt_sequence is not None]
        if sequenced:
            highest = max(cast(int, item.attempt_sequence) for item in sequenced)
            candidates = [item for item in sequenced if item.attempt_sequence == highest]
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
            if item.re_judged is ReJudge.DISAGREES:
                blocks.add(PromotionBlock.EVIDENCE_DISAGREES_WITH_ITS_BYTES)
                continue
            satisfied = True
        if not satisfied:
            blocking.append(case.case_id)

    ordered_blocking = tuple(sorted(blocking))
    return PromotionVerdict(
        promotable=not ordered_blocking,
        blocking_cases=ordered_blocking,
        blocks=tuple(sorted(blocks)),
        requirement=requirement,
    )
