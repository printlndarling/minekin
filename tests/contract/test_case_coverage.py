"""The required-case inventory is a reading of six contracts, and this checks the reading.

Every rule in `domain.cases` reads the registry — the cases that exist — so none of
them can notice a case a contract requires and nobody wrote. The inventory is what
stands in for that, and it is the one artifact here that cannot be derived from
anything else: prose read by a person and written down. So the check that matters is
not "does the code agree with the inventory" but "does the inventory agree with the
contracts", and the part of that a machine can be sure of is the citation: every
identifier the inventory requires appears verbatim in the document its entry cites.
That catches an identifier invented, mistyped, or left behind by an edit to the
contract — which is how a list like this rots — without pretending a regex
understands what a requirement means. It deliberately does *not* extract the expected
identifiers from the prose and compare: a checker whose expectations came from the
same paragraphs it is checking would agree with any reading of them, including a
wrong one.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from minekin_core.domain.cases import (
    REQUIRED_CASES,
    REQUIRED_GATES,
    WORK_PACKAGES,
    required_case_violations,
    required_for_gates,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"

#: The six contracts the inventory is read out of. Listed here rather than derived
#: from the entries, so a citation added to a document outside this set has to be
#: justified here as well as in `cases.py`.
CONTRACT_ANCHORS = frozenset(
    {
        "docs/p0-validation-evidence-contract.md",
        "docs/p0-remote-admission-contract.md",
        "docs/p0-offline-session-compatibility-contract.md",
        "docs/hosted-world-storage-lifecycle-contract.md",
        "docs/hosted-world-control-boundary-contract.md",
        "docs/hosted-world-commit-recovery-contract.md",
    }
)


def run_tool(tool: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, f"tools/{tool}", *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_every_required_case_is_named_in_the_document_it_cites() -> None:
    """The check the whole inventory rests on: the contracts say these identifiers.

    One assertion per entry, so a failure names the entry whose citation does not hold
    rather than the inventory as a whole.
    """

    assert {entry.anchor for entry in REQUIRED_CASES} == CONTRACT_ANCHORS
    for entry in REQUIRED_CASES:
        anchor = REPOSITORY_ROOT / entry.anchor
        assert anchor.is_file(), f"{entry.case_id} cites {entry.anchor}, which does not exist"
        assert entry.case_id in anchor.read_text(encoding="utf-8"), (
            f"{entry.case_id} is required by {entry.anchor}, which does not name it"
        )


def test_the_gates_are_work_packages_and_none_of_them_is_empty() -> None:
    """Two vocabularies, each closed, and the one difference between them is W80.

    `W80` is a work package and not a gate: the navigation experiment is graded as
    `p0-nav-exp`, which is a surface of its own. Binding NAV to the phase number would
    put one experiment's evidence under two names.
    """

    assert required_case_violations() == ()
    assert set(REQUIRED_GATES) <= set(WORK_PACKAGES)
    assert "W80" in WORK_PACKAGES
    assert "W80" not in REQUIRED_GATES
    for gate in REQUIRED_GATES:
        assert required_for_gates((gate,)), gate
    assert not any("W80" in entry.required_for for entry in REQUIRED_CASES)


def test_both_reports_name_the_same_missing_cases(tmp_path: Path) -> None:
    """Two tools, one registry, one answer — checked from the commands, not the code.

    They read the inventory through different entry points and print different
    documents, so what keeps them from disagreeing about which cases exist is that the
    reading is one function. This is that, run the way a person would run it.
    """

    inventory = run_tool("report_cases.py")
    promotion = run_tool("report_promotion.py", "--data-root", str(tmp_path))
    document = cast(dict[str, Any], json.loads(inventory.stdout))
    requirements = cast(dict[str, Any], document["requirements"])
    missing = set(cast(list[str], requirements["missing"]))
    overall = cast(dict[str, Any], json.loads(promotion.stdout))["overall"]

    assert inventory.returncode == 0, inventory.stderr
    assert promotion.returncode == 1, promotion.stderr
    assert missing == set(cast(list[str], overall["requirement"]["absent"]))
    assert missing, "the repository does not hold every required case yet"
    for gate, reading in cast(dict[str, dict[str, int]], requirements["by_gate"]).items():
        assert reading["present"] + reading["missing"] == reading["required"], gate


def test_deleting_a_required_case_is_named_and_blocks_only_its_gates(tmp_path: Path) -> None:
    """The negative mutation, run the way a person would run it.

    `CORE-020` is removed from a copy of the registry. Everything else — the
    assertions, the digests, the fixtures — is untouched, so the only new thing the
    report can say is that a case is gone, and which gates it was answering for. The
    scoping is read as a difference against the same command on the untouched tree,
    so no count is written down here.
    """

    cases = tmp_path / "cases"
    shutil.copytree(CASES, cases)
    (cases / "core-020.json").unlink()

    pristine = cast(dict[str, Any], json.loads(run_tool("report_cases.py").stdout))["requirements"]
    mutated = cast(
        dict[str, Any], json.loads(run_tool("report_cases.py", "--cases-dir", str(cases)).stdout)
    )["requirements"]
    before = cast(dict[str, dict[str, int]], pristine["by_gate"])
    after = cast(dict[str, dict[str, int]], mutated["by_gate"])

    assert "CORE-020" in cast(list[str], mutated["missing"])
    assert "CORE-020" not in cast(list[str], pristine["missing"])
    assert after["W40"]["missing"] == before["W40"]["missing"] + 1
    assert after["W40"]["satisfied"] is False
    assert after["W60"] == before["W60"]
    assert after["host-integrated"] == before["host-integrated"]
