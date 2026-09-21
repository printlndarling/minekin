"""The action pins: what counts as pinned, and the two halves of it.

A commit with no release beside it is refused, and that is the half worth testing
separately — it is the one a hurried renewal drops, and the result would be a pin
nobody can review rather than an unpinned action nobody can miss.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/check_workflow_pins.py"

CHECKOUT = "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"


def workflow(tmp_path: Path, text: str) -> Path:
    directory = tmp_path / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ci.yml").write_text(text, encoding="utf-8")
    return directory


def run_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_the_reviewed_workflows_are_pinned() -> None:
    result = run_tool()

    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_a_tag_is_refused(tmp_path: Path) -> None:
    """A tag is a name its owner can move; that is the whole reason for this."""

    directory = workflow(tmp_path, "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v5\n")

    result = run_tool("--workflows-dir", str(directory))

    assert result.returncode == 1
    assert "is not owner/repo@<40 hex commit>" in result.stderr
    assert "actions/checkout@v5" in result.stderr


def test_a_commit_without_its_release_is_refused(tmp_path: Path) -> None:
    """The half a hurried renewal drops, and the one that makes the other unreviewable."""

    directory = workflow(tmp_path, f"jobs:\n  a:\n    steps:\n      - uses: {CHECKOUT}\n")

    result = run_tool("--workflows-dir", str(directory))

    assert result.returncode == 1
    assert "records no release" in result.stderr


def test_a_pinned_action_that_names_its_release_is_accepted(tmp_path: Path) -> None:
    """The negative control, both halves at once."""

    directory = workflow(tmp_path, f"jobs:\n  a:\n    steps:\n      - uses: {CHECKOUT} # v5\n")

    result = run_tool("--workflows-dir", str(directory))

    assert result.returncode == 0, result.stderr


def test_a_commit_that_is_not_a_whole_commit_is_refused(tmp_path: Path) -> None:
    """An abbreviation is a name too: it can collide, and it is not what a reviewer read."""

    directory = workflow(
        tmp_path, "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@fbc6f399 # v5\n"
    )

    result = run_tool("--workflows-dir", str(directory))

    assert result.returncode == 1
    assert "is not owner/repo@<40 hex commit>" in result.stderr


def test_a_local_action_is_allowed(tmp_path: Path) -> None:
    """It is this repository's own code: it moves with the checkout, so nothing to pin."""

    directory = workflow(
        tmp_path, "jobs:\n  a:\n    steps:\n      - uses: ./.github/actions/thing\n"
    )

    result = run_tool("--workflows-dir", str(directory))

    assert result.returncode == 0, result.stderr


def test_an_action_computed_at_run_time_is_refused(tmp_path: Path) -> None:
    directory = workflow(
        tmp_path, "jobs:\n  a:\n    steps:\n      - uses: ${{ inputs.action }} # v5\n"
    )

    result = run_tool("--workflows-dir", str(directory))

    assert result.returncode == 1
    assert "computed at run time" in result.stderr


def test_a_missing_workflows_directory_is_not_reported_as_a_pass(tmp_path: Path) -> None:
    result = run_tool("--workflows-dir", str(tmp_path / "nowhere"))

    assert result.returncode == 2
    assert "is not a directory" in result.stderr
