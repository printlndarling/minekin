"""The supply-chain check must not be able to surprise anyone with a download.

Fetching the whole bundle is a gigabyte. The tool is therefore opt-in and bounded,
and the bound is refused *before* any request is made, which is the part that can
be checked without the network.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/verify_supply_chain.py"


def run_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_a_budget_below_the_planned_fetch_is_refused() -> None:
    result = run_tool("--max-bytes", "1000")

    assert result.returncode == 1
    assert "refused" in result.stderr
    assert "exceed the budget" in result.stderr


def test_the_planned_size_is_printed_before_anything_is_fetched() -> None:
    """So the cost is visible whether or not the run is allowed to proceed."""

    result = run_tool("--max-bytes", "1000")

    assert "budget" in result.stdout
    assert "would fetch" in result.stdout
