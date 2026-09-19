"""The fetch tool must be safe to run without the network, which is what CI is.

Everything that reaches the network is checked at the library level with an
injected opener. What is checked here is the part an operator reads before
running it for real: the resolved store, the size of the job, and the refusal
when a budget is given and exceeded — all of which must happen before a request.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/fetch_bundle.py"
PROFILE = REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"


def run_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_dry_run_reports_the_job_without_fetching(tmp_path: Path) -> None:
    result = run_tool("--profile", str(PROFILE), "--store", str(tmp_path), "--dry-run")

    assert result.returncode == 0
    planned = json.loads(result.stdout)
    assert planned["status"] == "planned"
    # 4,120 artifacts from the Minecraft metadata plus the one fixed mod that is
    # fetched rather than built here: fabric-api is loaded from the game
    # directory, not the classpath, so it is not in the artifact list — but
    # nothing else would put it in the store either.
    assert planned["artifacts"] == 4120
    assert planned["missing"] == 4120
    assert planned["missing_bytes"] > 0
    # Naming the store is what makes a fetch into the wrong one visible.
    assert planned["store"] == str(tmp_path.resolve())


def test_a_budget_below_the_job_is_refused_before_any_request(tmp_path: Path) -> None:
    result = run_tool("--profile", str(PROFILE), "--store", str(tmp_path), "--max-bytes", "1024")

    assert result.returncode == 2
    refused = json.loads(result.stdout)
    assert refused["status"] == "refused"
    assert "1024 byte budget" in refused["reason"]


def test_a_dry_run_is_not_bounded_by_the_budget(tmp_path: Path) -> None:
    """A dry run fetches nothing, so a budget that would refuse the real run still
    lets the operator see what it would cost."""

    result = run_tool(
        "--profile", str(PROFILE), "--store", str(tmp_path), "--max-bytes", "1", "--dry-run"
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["missing"] == 4120
