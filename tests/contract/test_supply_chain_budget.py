"""The supply-chain check must not be able to surprise anyone with a download.

Fetching the whole bundle is a gigabyte. The tool is therefore opt-in and bounded,
and the bound is refused *before* any request is made, which is the part that can
be checked without the network.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/verify_supply_chain.py"
PLANNED_BYTES = re.compile(r"this run would fetch (\d+) bytes")


def run_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def planned_bytes(*arguments: str) -> int:
    """The number the tool prints before it is allowed to fetch anything."""

    result = run_tool("--max-bytes", "1000", *arguments)
    match = PLANNED_BYTES.search(result.stdout)

    assert match is not None, result.stdout
    return int(match.group(1))


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


def test_saving_the_server_jar_fetches_what_it_says_it_will() -> None:
    """`--save-server` is opt-in for the server jar too, and must say so up front.

    Saving is only ever offered bytes that were checked against the pin, which
    means the server jar has to be fetched — so the flag implies the 54 MB, and
    the budget line the operator reads before any request has to show it.
    """

    with_server = planned_bytes("--include-server")
    saving = planned_bytes("--save-server", "unused.jar")

    assert planned_bytes() < with_server
    assert saving == with_server
