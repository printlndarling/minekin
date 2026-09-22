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
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from minekin_core.adapters.evidence.promotion import load_case_registry
from minekin_core.domain.cases import (
    REQUIRED_CASE_INVENTORY_VERSION,
    REQUIRED_CASES,
    REQUIRED_GATES,
)

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


# ---------------------------------------------------------------------------
# The other reading: what each gate requires
# ---------------------------------------------------------------------------
#
# The readings above are about the cases that exist, and every assertion they can
# make is silent about the ones that do not. These are about the inventory, and
# about a gate's requirement being a view over it rather than a work-package
# grouping: that is what keeps a hole in one surface out of another surface's gate.


def registered_ids() -> set[str]:
    return set(load_case_registry(CASES).by_id())


def test_the_report_reads_the_inventory_against_the_registry() -> None:
    document = RUNNER.report()
    requirements = document["requirements"]
    readings = requirements["cases"]
    present = requirements["present"]
    missing = requirements["missing"]

    assert requirements["schema_version"] == REQUIRED_CASE_INVENTORY_VERSION
    assert requirements["gates"] == list(REQUIRED_GATES)
    assert requirements["totals"]["required"] == len(readings)
    assert len(present) + len(missing) == len(readings)
    assert not set(present) & set(missing)
    # Against the registry rather than against a number: a pinned number is the thing
    # this report was written to stop maintaining by hand.
    assert set(missing) == {
        entry["case_id"] for entry in readings if entry["case_id"] not in registered_ids()
    }


def test_the_reading_is_per_gate_and_not_over_the_whole_repository() -> None:
    """A gate answers for its own cases, which is what makes the answer about it."""

    by_gate = RUNNER.report()["requirements"]["by_gate"]
    w40 = by_gate["W40"]

    assert set(by_gate) == set(REQUIRED_GATES)
    assert w40["required"] == 12
    assert w40["present"] + w40["missing"] == w40["required"]
    assert w40["satisfied"] is False
    assert by_gate["host-integrated"]["required"] == 33
    assert by_gate["p0-nav-exp"]["required"] == 1
    assert by_gate["p0-nav-exp"]["satisfied"] is False


def test_the_registered_cases_reading_is_unchanged() -> None:
    """The old keys and the old totals, because everything reading them still is."""

    document = RUNNER.report()
    cases = document["cases"]
    totals = document["totals"]

    assert document["status"] == "reported"
    assert totals["cases"] == len(cases)
    assert totals["assertions"] == sum(case["assertions"] for case in cases)
    assert sum(totals["by_judge"].values()) == len(cases)
    assert sum(entry["cases"] for entry in document["packages"].values()) == len(cases)
    assert totals["required"] == len(document["requirements"]["cases"])


def test_a_required_case_that_is_present_without_gating_is_counted() -> None:
    """Present and not gating is its own count: a gate that looks closed and is not."""

    document = RUNNER.report()
    readings = cast(list[dict[str, object]], document["requirements"]["cases"])
    not_gating = [
        entry["case_id"] for entry in readings if entry["present"] and not entry["mandatory"]
    ]

    assert not_gating
    assert document["requirements"]["totals"]["not_gating"] == len(not_gating)
    assert set(not_gating) <= set(document["requirements"]["present"])
    assert "CORE-060" in not_gating
    assert "HOST-001" not in not_gating


def test_a_required_case_filed_elsewhere_is_reported_misattributed(tmp_path: Path) -> None:
    """A case that moved between gates is named with both work packages, not guessed at."""

    cases = tmp_path / "cases"
    shutil.copytree(CASES, cases)
    fixture = cases / "core-020.json"
    moved = json.loads(fixture.read_text(encoding="utf-8"))
    moved["work_package"] = "W60"
    fixture.write_text(json.dumps(moved, indent=2) + "\n", encoding="utf-8")

    document = RUNNER.report(cases_dir=cases)
    misattributed = document["requirements"]["misattributed"]

    assert misattributed == [
        {
            "case_id": "CORE-020",
            "expected_work_package": "W40",
            "registered_work_package": "W60",
        }
    ]
    assert document["requirements"]["by_gate"]["W40"]["misattributed"] == 1
    assert document["requirements"]["by_gate"]["W40"]["satisfied"] is False
    assert "CORE-020" not in document["requirements"]["missing"]


def test_a_surface_that_cannot_be_numbered_is_reported_and_gates_nothing() -> None:
    """`PERSIST` has a contract and no case ids; a gap is not a requirement."""

    requirements = RUNNER.report()["requirements"]
    gaps = requirements["planning_gaps"]

    assert [gap["surface"] for gap in gaps] == ["PERSIST"]
    assert gaps[0]["status"] == "UNFROZEN_CASE_IDS"
    assert gaps[0]["required_for"] == []
    assert gaps[0]["anchor"] == "docs/persistence-recovery-contract.md"
    assert "PERSIST" not in {entry["expected_work_package"] for entry in requirements["cases"]}
    assert not any(name.startswith("PERSIST") for name in requirements["missing"])


def test_an_inventory_that_cannot_be_read_is_refused_rather_than_reported_on() -> None:
    """A table of present and missing rows computed from a bad inventory lies well."""

    with pytest.raises(RUNNER.UnusableInventory, match="DUPLICATE_CASE_ID"):
        RUNNER._report_with_inventory(required=(*REQUIRED_CASES, REQUIRED_CASES[0]))


def test_an_unknown_required_id_is_refused_rather_than_reported() -> None:
    unknown = replace(REQUIRED_CASES[0], case_id="CORE-999")

    with pytest.raises(RUNNER.UnusableInventory, match="UNKNOWN_CASE_ID"):
        RUNNER._report_with_inventory(required=(*REQUIRED_CASES, unknown))


def test_the_public_report_does_not_allow_callers_to_replace_the_inventory() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument 'required'"):
        RUNNER.report(required=REQUIRED_CASES)


def test_the_command_refuses_an_inventory_it_cannot_read(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command's answer to a question it cannot ask is to refuse it."""

    def refuse(**_arguments: object) -> dict[str, object]:
        raise RUNNER.UnusableInventory("the required-case inventory is not usable")

    monkeypatch.setattr(RUNNER, "report", refuse)

    assert RUNNER.main([]) == RUNNER.EXIT_UNUSABLE
    assert json.loads(capsys.readouterr().err)["status"] == "unusable"
