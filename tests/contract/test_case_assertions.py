"""Every assertion a case names must point at something that exists.

A case manifest lists assertion names as strings, and promotion accepts whatever a
bundle records under them, so a name nothing implements would look like coverage.
This checks the declaration rather than the behaviour: running the assertions is
the orchestrator's job and belongs with the runtime cases.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/check_case_assertions.py"


def run_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def case_document(assertions: list[str]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "case_id": "W00-CONTRACT-001",
        "work_package": "W00",
        "mandatory": True,
        "inputs": ["schemas/*.schema.json"],
        "assertions": assertions,
    }


def test_the_reviewed_cases_name_only_implemented_assertions() -> None:
    result = run_tool()

    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_a_case_naming_an_unimplemented_assertion_is_refused(tmp_path: Path) -> None:
    (tmp_path / "case.json").write_text(
        json.dumps(case_document(["schemas_are_versioned", "everything_is_fine"])),
        encoding="utf-8",
    )

    result = run_tool("--cases-dir", str(tmp_path))

    assert result.returncode == 1
    assert "everything_is_fine" in result.stderr
    assert "nothing implements" in result.stderr


def test_a_registered_assertion_whose_implementation_is_gone_is_refused(
    tmp_path: Path,
) -> None:
    """Renaming an implementation must break this, not silently orphan the name."""

    result = run_tool("--root", str(tmp_path))

    assert result.returncode == 1
    assert "does not exist" in result.stderr
