"""Reporting what cases this repository has, and which judge performs each.

The counts lived in prose, and prose does not notice when it expires: "three host
cases" was twelve, and the same inventory number was written, found wrong, and
corrected three times in one day. This answers the question the way
`report_promotion.py` answers its own — by reading the fixtures and the registry and
printing what is there — so the next number anyone wants is a command rather than a
memory.

It is more than a count because of *who judges a case*. An assertion whose
implementation is `pytest` or `tool` is performed by `tools/run_repo_case.py` and by
the test suite CI runs; one registered `runtime` is performed by the run-material
asserter against a run that has finished. A case is judged by exactly one judge, so a
case that mixes the two can be decided by neither — a shape worth seeing at a glance,
and one this repository has already been bitten by once.

An assertion nothing implements is reported rather than counted: the registry gate
refuses it, but the difference between "this case is covered" and "this case names
something nobody performs" is exactly what somebody reading the report needs.

What it read was still only ever the fixtures, and that is the same failure one level
up: a report over the cases that exist cannot show a case that does not, so "0
unimplemented" was true of a case set with holes in it. The second reading is the
inventory, read per gate — a hole in the host surface is not a hole in W40 — and it
keeps two vocabularies apart rather than merging them: `local-only` and
`runtime-required` are what a *required* case needs, `locally` and `run-material` are
who decides a *registered* one, and a case can be the first while looking like the
second.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

# The tools directory, so the registry can be imported whether this is run as
# `python tools/report_cases.py` or imported as `tools.report_cases`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_case_assertions import IMPLEMENTATIONS, Implementation
from minekin_core.adapters.evidence.promotion import load_case_registry
from minekin_core.domain.cases import (
    REQUIRED_CASES,
    REQUIRED_GATES,
    CaseManifest,
    CaseRegistry,
    RequiredCase,
    ValidationClass,
    required_case_inventory,
    required_case_violations,
    required_for_gates,
)
from run_repo_case import PERFORMABLE_KINDS

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"

#: What a case's judge is called in the report. `MIXED` is not a verdict: it means the
#: case names assertions from both judges, and neither can decide it alone.
LOCALLY = "locally"
RUN_MATERIAL = "run-material"
MIXED = "mixed"
UNIMPLEMENTED = "unimplemented"

EXIT_REPORTED = 0
EXIT_UNUSABLE = 2


class UnusableInventory(Exception):
    """The required-case inventory cannot be read, so no report can be about it."""


@dataclass(frozen=True, slots=True)
class CaseSummary:
    """One case, and who can decide it."""

    case_id: str
    work_package: str
    mandatory: bool
    assertions: tuple[str, ...]
    #: Assertions this case names that no registered implementation performs.
    unregistered: tuple[str, ...]
    #: `locally`, `run-material`, `mixed`, or `unimplemented` when every assertion is
    #: unregistered (a case nobody judges is not a case with a judge).
    judged_by: str

    def as_document(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "work_package": self.work_package,
            "mandatory": self.mandatory,
            "assertions": len(self.assertions),
            "judged_by": self.judged_by,
            "unregistered": list(self.unregistered),
        }


@dataclass(frozen=True, slots=True)
class RequiredSummary:
    """One case the contracts require, and what this repository has for it."""

    case_id: str
    expected_work_package: str
    #: The gates whose completion needs this case.
    required_for: tuple[str, ...]
    validation_class: str
    anchor: str
    present: bool
    #: The registered case's own declaration, or None when there is no case to read
    #: it from. None is not False: a case nobody wrote has no opinion about whether
    #: it should gate, and a report printing `false` there would answer for it.
    mandatory: bool | None
    #: Who decides the registered case, or None when there is nothing to decide.
    judged_by: str | None

    def as_document(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "expected_work_package": self.expected_work_package,
            "required_for": list(self.required_for),
            "validation_class": self.validation_class,
            "anchor": self.anchor,
            "present": self.present,
            "mandatory": self.mandatory,
            "judged_by": self.judged_by,
        }


@dataclass(frozen=True, slots=True)
class GateSummary:
    """One gate's requirement, counted.

    `satisfied` is about inventory completeness, not about evidence: every case the
    gate requires is registered under the work package it belongs to. Whether a
    present case is mandatory remains visible as `not_gating`; whether mandatory
    evidence passes is `report_promotion`'s question. The document does not repeat
    the gate's name, because the map it is keyed by is it.
    """

    gate: str
    required: int
    present: int
    missing: int
    misattributed: int
    not_gating: int
    satisfied: bool

    def as_document(self) -> dict[str, object]:
        return {
            "required": self.required,
            "present": self.present,
            "missing": self.missing,
            "misattributed": self.misattributed,
            "not_gating": self.not_gating,
            "satisfied": self.satisfied,
        }


def _judge(kinds: set[str]) -> str:
    """Which judge performs a case's assertions, given the kinds it names."""

    if not kinds:
        return UNIMPLEMENTED
    local = kinds & PERFORMABLE_KINDS
    if local and kinds - PERFORMABLE_KINDS:
        return MIXED
    return LOCALLY if local else RUN_MATERIAL


def _kinds(case: CaseManifest, registry: Mapping[str, Implementation]) -> set[str]:
    return {registry[item].kind for item in case.assertions if item in registry}


def summarise(
    cases: CaseRegistry, registry: Mapping[str, Implementation] = IMPLEMENTATIONS
) -> tuple[CaseSummary, ...]:
    """One summary per case the registry holds, in the order it names them."""

    return tuple(
        CaseSummary(
            case_id=case.case_id,
            work_package=case.work_package,
            mandatory=case.mandatory,
            assertions=case.assertions,
            unregistered=tuple(item for item in case.assertions if item not in registry),
            judged_by=_judge(_kinds(case, registry)),
        )
        for case in cases.cases
    )


def requirements_report(
    cases: CaseRegistry,
    registry: Mapping[str, Implementation] = IMPLEMENTATIONS,
    required: Sequence[RequiredCase] = REQUIRED_CASES,
) -> dict[str, object]:
    """The inventory read against a registry: present, missing, misfiled, not gating.

    An inventory that cannot be read is refused rather than reported on. They are not
    the same kind of answer: a missing case is what this reading exists to say, while
    an inventory holding a malformed, repeated or out-of-vocabulary entry is a
    question that cannot be asked — and rows computed from it would look exactly as
    authoritative as correct ones.

    `present_wanting_a_run` is the number the two vocabularies are kept apart for: a
    case whose contract names a run and whose fixture is decided wholly by the test
    suite has its repository half and not its run half.
    """

    violations = required_case_violations(required)
    if violations:
        raise UnusableInventory(
            "the required-case inventory is not usable: "
            + ", ".join(f"{reason.value} ({subject})" for reason, subject in violations)
        )

    held = cases.by_id()
    readings = tuple(
        RequiredSummary(
            case_id=entry.case_id,
            expected_work_package=entry.expected_work_package,
            required_for=entry.required_for,
            validation_class=entry.validation_class.value,
            anchor=entry.anchor,
            present=entry.case_id in held,
            mandatory=None if entry.case_id not in held else held[entry.case_id].mandatory,
            judged_by=(
                None if entry.case_id not in held else _judge(_kinds(held[entry.case_id], registry))
            ),
        )
        for entry in required
    )
    present = tuple(reading for reading in readings if reading.present)
    misfiled = tuple(
        reading
        for reading in present
        if held[reading.case_id].work_package != reading.expected_work_package
    )
    inventory = required_case_inventory(required)
    totals = cast(dict[str, object], inventory["totals"])
    return {
        **inventory,
        "totals": {
            **totals,
            "present": len(present),
            "missing": len(readings) - len(present),
            "misattributed": len(misfiled),
            "not_gating": sum(1 for reading in present if not reading.mandatory),
            "present_wanting_a_run": sum(
                1
                for reading in present
                if reading.validation_class == ValidationClass.RUNTIME_REQUIRED.value
                and reading.judged_by == LOCALLY
            ),
        },
        "by_gate": {
            gate: GateSummary(
                gate=gate,
                required=len(required_for_gates((gate,), required)),
                present=sum(1 for reading in present if gate in reading.required_for),
                missing=sum(
                    1
                    for reading in readings
                    if not reading.present and gate in reading.required_for
                ),
                misattributed=sum(1 for reading in misfiled if gate in reading.required_for),
                not_gating=sum(
                    1
                    for reading in present
                    if gate in reading.required_for and not reading.mandatory
                ),
                satisfied=cases.requirement(gate, required=required).satisfied,
            ).as_document()
            for gate in REQUIRED_GATES
        },
        "present": [reading.case_id for reading in present],
        "missing": [reading.case_id for reading in readings if not reading.present],
        "misattributed": [
            {
                "case_id": reading.case_id,
                "expected_work_package": reading.expected_work_package,
                "registered_work_package": held[reading.case_id].work_package,
            }
            for reading in misfiled
        ],
        "cases": [reading.as_document() for reading in readings],
    }


def _report_with_inventory(
    *,
    cases_dir: Path = CASES,
    registry: Mapping[str, Implementation] = IMPLEMENTATIONS,
    required: Sequence[RequiredCase] = REQUIRED_CASES,
) -> dict[str, object]:
    """The inventory, as a document somebody can read without re-deriving it."""

    cases = load_case_registry(cases_dir)
    summaries = summarise(cases, registry)
    requirements = requirements_report(cases, registry, required)
    requirements_totals = cast(dict[str, int], requirements["totals"])
    packages: dict[str, dict[str, int]] = {}
    for summary in summaries:
        entry = packages.setdefault(summary.work_package, {"cases": 0, "mandatory": 0})
        entry["cases"] += 1
        entry["mandatory"] += 1 if summary.mandatory else 0
    return {
        "schema_version": 1,
        "status": "reported",
        "totals": {
            "cases": len(summaries),
            "mandatory": sum(1 for summary in summaries if summary.mandatory),
            "assertions": sum(len(summary.assertions) for summary in summaries),
            "unregistered_assertions": sum(len(summary.unregistered) for summary in summaries),
            "required": requirements_totals["required"],
            "required_present": requirements_totals["present"],
            "required_missing": requirements_totals["missing"],
            "required_misattributed": requirements_totals["misattributed"],
            "required_not_gating": requirements_totals["not_gating"],
            "by_judge": {
                judge: sum(1 for summary in summaries if summary.judged_by == judge)
                for judge in (LOCALLY, RUN_MATERIAL, MIXED, UNIMPLEMENTED)
            },
        },
        "packages": {name: packages[name] for name in sorted(packages)},
        "requirements": requirements,
        "cases": [summary.as_document() for summary in summaries],
    }


def report(
    *, cases_dir: Path = CASES, registry: Mapping[str, Implementation] = IMPLEMENTATIONS
) -> dict[str, object]:
    """Report repository cases against the complete reviewed inventory."""

    return _report_with_inventory(
        cases_dir=cases_dir,
        registry=registry,
        required=REQUIRED_CASES,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report the cases this repository has, and which judge performs each."
    )
    parser.add_argument("--cases-dir", type=Path, default=CASES)
    args = parser.parse_args(argv)

    try:
        document = report(cases_dir=args.cases_dir)
    except UnusableInventory as error:
        print(
            json.dumps({"schema_version": 1, "status": "unusable", "message": str(error)}),
            file=sys.stderr,
        )
        return EXIT_UNUSABLE

    print(json.dumps(document, sort_keys=True))
    # A report does not gate: what a case is missing is the registry gate's business,
    # and this one exists to say what is there.
    return EXIT_REPORTED


if __name__ == "__main__":
    raise SystemExit(main())
