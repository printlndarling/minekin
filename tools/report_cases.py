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
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# The tools directory, so the registry can be imported whether this is run as
# `python tools/report_cases.py` or imported as `tools.report_cases`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_case_assertions import IMPLEMENTATIONS, Implementation
from minekin_core.adapters.evidence.promotion import load_case_registry
from run_repo_case import PERFORMABLE_KINDS

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"

#: What a case's judge is called in the report. `MIXED` is not a verdict: it means the
#: case names assertions from both judges, and neither can decide it alone.
LOCALLY = "locally"
RUN_MATERIAL = "run-material"
MIXED = "mixed"
UNIMPLEMENTED = "unimplemented"


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


def _judge(kinds: set[str]) -> str:
    """Which judge performs a case's assertions, given the kinds it names."""

    if not kinds:
        return UNIMPLEMENTED
    local = kinds & PERFORMABLE_KINDS
    if local and kinds - PERFORMABLE_KINDS:
        return MIXED
    return LOCALLY if local else RUN_MATERIAL


def summarise(
    *, cases_dir: Path = CASES, registry: Mapping[str, Implementation] = IMPLEMENTATIONS
) -> tuple[CaseSummary, ...]:
    """One summary per case the directory holds, in the order it names them."""

    summaries: list[CaseSummary] = []
    for case in load_case_registry(cases_dir).cases:
        unregistered = tuple(item for item in case.assertions if item not in registry)
        kinds = {registry[item].kind for item in case.assertions if item in registry}
        summaries.append(
            CaseSummary(
                case_id=case.case_id,
                work_package=case.work_package,
                mandatory=case.mandatory,
                assertions=case.assertions,
                unregistered=unregistered,
                judged_by=_judge(kinds),
            )
        )
    return tuple(summaries)


def report(
    *, cases_dir: Path = CASES, registry: Mapping[str, Implementation] = IMPLEMENTATIONS
) -> dict[str, object]:
    """The inventory, as a document somebody can read without re-deriving it."""

    summaries = summarise(cases_dir=cases_dir, registry=registry)
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
            "by_judge": {
                judge: sum(1 for summary in summaries if summary.judged_by == judge)
                for judge in (LOCALLY, RUN_MATERIAL, MIXED, UNIMPLEMENTED)
            },
        },
        "packages": {name: packages[name] for name in sorted(packages)},
        "cases": [summary.as_document() for summary in summaries],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report the cases this repository has, and which judge performs each."
    )
    parser.add_argument("--cases-dir", type=Path, default=CASES)
    args = parser.parse_args(argv)

    document = report(cases_dir=args.cases_dir)
    print(json.dumps(document, sort_keys=True))
    # A report does not gate: what a case is missing is the registry gate's business,
    # and this one exists to say what is there.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
