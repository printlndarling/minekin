"""What the case inventory is, and which judge decides each case.

The report exists because the same number was written into prose, found wrong, and
corrected three times in one day. So the tests are about the two things a bare count
gets wrong: a case whose assertions two judges split between them — and neither can
decide it alone — and an assertion nothing implements at all, which a count reads as
coverage.

The repository's own cases are checked too, but only for the properties that must hold
whatever they contain: every case reported once, and the totals equal to what was
reported. Pinning the count itself here would reintroduce exactly the staleness the
tool was written to remove.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from minekin_core.adapters.evidence.promotion import load_case_registry

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPOSITORY_ROOT / "tools" / "report_cases.py"
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"


def load_tool() -> ModuleType:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module("tools.report_cases")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


RUNNER = load_tool()


def registry(*kinds: str) -> dict[str, Any]:
    return {
        f"assertion_{index}": RUNNER.Implementation(kind, "tools/run_repo_case.py")
        for index, kind in enumerate(kinds, start=1)
    }


def write_case(directory: Path, case_id: str, assertions: tuple[str, ...]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{case_id.lower()}.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": case_id,
                "work_package": "W40",
                "mandatory": False,
                "inputs": [],
                "assertion_digests": {},
                "assertions": list(assertions),
            }
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Who judges a case
# ---------------------------------------------------------------------------


def test_a_case_whose_assertions_are_all_local_is_judged_locally(tmp_path: Path) -> None:
    write_case(tmp_path, "TEST-001", ("assertion_1", "assertion_2"))

    document = RUNNER.report(cases_dir=tmp_path, registry=registry("pytest", "tool"))

    assert [case["judged_by"] for case in document["cases"]] == [RUNNER.LOCALLY]


def test_a_case_whose_assertions_are_all_run_material_is_judged_by_the_asserter(
    tmp_path: Path,
) -> None:
    write_case(tmp_path, "TEST-001", ("assertion_1",))

    document = RUNNER.report(cases_dir=tmp_path, registry=registry("runtime"))

    assert [case["judged_by"] for case in document["cases"]] == [RUNNER.RUN_MATERIAL]


def test_a_case_that_splits_its_assertions_between_judges_is_named_as_mixed(
    tmp_path: Path,
) -> None:
    """Neither judge can decide it, which is the shape worth seeing at a glance."""

    write_case(tmp_path, "TEST-001", ("assertion_1", "assertion_2"))

    document = RUNNER.report(cases_dir=tmp_path, registry=registry("pytest", "runtime"))

    assert [case["judged_by"] for case in document["cases"]] == [RUNNER.MIXED]


def test_an_assertion_nothing_implements_is_reported_rather_than_counted(
    tmp_path: Path,
) -> None:
    """A count reads an unperformed assertion as coverage; the report says so."""

    write_case(tmp_path, "TEST-001", ("assertion_1", "assertion_nobody_performs"))

    document = RUNNER.report(cases_dir=tmp_path, registry=registry("pytest"))

    assert document["cases"][0]["unregistered"] == ["assertion_nobody_performs"]
    assert document["totals"]["unregistered_assertions"] == 1
    assert document["cases"][0]["judged_by"] == RUNNER.LOCALLY, "the rest is still judged"


def test_a_case_nobody_performs_is_unimplemented_rather_than_local(tmp_path: Path) -> None:
    """Nothing to judge is its own answer, not a kind of judging."""

    write_case(tmp_path, "TEST-001", ("assertion_nobody_performs",))

    document = RUNNER.report(cases_dir=tmp_path, registry={})

    assert [case["judged_by"] for case in document["cases"]] == [RUNNER.UNIMPLEMENTED]


# ---------------------------------------------------------------------------
# The repository's own inventory
# ---------------------------------------------------------------------------


def test_every_case_the_registry_holds_is_reported_once() -> None:
    """Read from the same place the registry is, so the two cannot disagree."""

    document = RUNNER.report()
    reported = [case["case_id"] for case in document["cases"]]

    assert reported == [case.case_id for case in load_case_registry(CASES).cases]
    assert len(reported) == len(set(reported)), "a case reported twice is two numbers"


def test_the_totals_are_the_cases_it_reports() -> None:
    """The arithmetic is the report's own, so a wrong total cannot hide in prose."""

    document = RUNNER.report()
    cases = document["cases"]
    totals = document["totals"]

    assert totals["cases"] == len(cases)
    assert totals["mandatory"] == sum(1 for case in cases if case["mandatory"])
    assert totals["assertions"] == sum(case["assertions"] for case in cases)
    assert sum(totals["by_judge"].values()) == len(cases)
    assert sum(entry["cases"] for entry in document["packages"].values()) == len(cases)


def test_the_report_reads_the_directory_it_is_pointed_at(tmp_path: Path) -> None:
    """It answers about what it was given, not about what it remembers."""

    write_case(tmp_path, "TEST-001", ("assertion_1",))

    document = RUNNER.report(cases_dir=tmp_path, registry=registry("pytest"))

    assert [case["case_id"] for case in document["cases"]] == ["TEST-001"]
    assert document["packages"] == {"W40": {"cases": 1, "mandatory": 0}}
