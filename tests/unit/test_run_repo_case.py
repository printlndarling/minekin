"""Running a repository case's checks, without a client and without a world.

The registry here is injected rather than the real one for everything except the
last test: a case whose checks are tiny scripts is a case that can be made to
fail, and a case whose checks are this repository's own gates is a case about
this repository. Both are worth having, and they are not the same test.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPOSITORY_ROOT / "tools" / "run_repo_case.py"
REVIEWED_CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "w00-contract-001.json"
#: A case whose assertions are the run-material asserter's, not this runner's.
RUNTIME_CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "host-030.json"


def load_tool() -> ModuleType:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module("tools.run_repo_case")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


RUNNER = load_tool()


def script(root: Path, name: str, body: str) -> None:
    (root / name).write_text(body, encoding="utf-8")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A tiny repository: one script that holds, one that fails."""

    script(tmp_path, "ok.py", "raise SystemExit(0)\n")
    script(tmp_path, "bad.py", "print('the schema is not versioned')\nraise SystemExit(1)\n")
    return tmp_path


def registry(*names: str) -> dict[str, Any]:
    return {name: RUNNER.Implementation("tool", f"{name}.py") for name in names}


def case(assertions: tuple[str, ...], case_id: str = "W00-CONTRACT-001") -> dict[str, object]:
    return {"schema_version": 1, "case_id": case_id, "assertions": list(assertions)}


def test_a_repository_whose_checks_hold_passes(root: Path) -> None:
    verdict = RUNNER.run_case(case(("ok",)), registry=registry("ok"), root=root)

    assert verdict.result == "PASS"
    assert verdict.expected == ("ok",)
    assert verdict.observed == ("ok",)
    assert verdict.failures == ()
    assert verdict.checks[0].exit_code == 0


def test_a_check_that_fails_says_what_it_said(root: Path) -> None:
    """The verdict carries the last words, and the artifact carries the rest."""

    verdict = RUNNER.run_case(case(("bad",)), registry=registry("bad"), root=root)

    assert verdict.result == "FAIL"
    assert verdict.failures == ("bad:CHECK_FAILED:exit 1",)
    assert verdict.checks[0].detail == "the schema is not versioned"
    assert verdict.observed == ()


def test_one_failing_check_does_not_hide_the_others(root: Path) -> None:
    verdict = RUNNER.run_case(case(("ok", "bad")), registry=registry("ok", "bad"), root=root)

    assert verdict.result == "FAIL"
    assert verdict.observed == ("ok",)
    assert [check.held for check in verdict.checks] == [True, False]


def test_an_assertion_nothing_implements_is_not_a_failure(root: Path) -> None:
    """Absence of a check and a failed check are different answers."""

    verdict = RUNNER.run_case(case(("ok", "nobody")), registry=registry("ok"), root=root)

    assert verdict.result == "INCOMPLETE"
    assert verdict.unimplemented == ("nobody",)
    assert verdict.failures == ("nobody:NO_IMPLEMENTATION",)
    assert verdict.observed == ("ok",)


def test_an_assertion_another_judge_performs_is_not_run_here(root: Path) -> None:
    """A runtime assertion has no command here: it needs a finished run's material.

    Reported as unimplemented rather than failed, which is the difference between
    "this runner cannot judge this case" and "this case is broken". The registry
    says which judge performs it; before the kind existed, the asserter was invoked
    with the arguments it needs missing and its usage error was reported as a
    failure of a case that had not failed.
    """

    judges = {
        "hosted": RUNNER.Implementation("runtime", "tools/assert_case_evidence.py", symbol="hosted")
    }

    verdict = RUNNER.run_case(case(("hosted",)), registry=judges, root=root)

    assert verdict.result == "INCOMPLETE"
    assert verdict.unimplemented == ("hosted",)
    assert verdict.checks == (), "nothing was run, so nothing reported a failure"
    assert verdict.failures == ("hosted:NO_IMPLEMENTATION",)


def test_the_runner_refuses_to_build_a_command_for_another_judges_assertion(root: Path) -> None:
    """Asking for one is an error rather than an empty command line."""

    implementation = RUNNER.Implementation(
        "runtime", "tools/assert_case_evidence.py", symbol="hosted"
    )

    with pytest.raises(RUNNER.Unrunnable, match="not performed by this runner"):
        RUNNER.command_for(implementation, root=root)


def test_a_target_that_is_not_there_is_not_run_at_all(root: Path) -> None:
    """Running a missing file would report the shell's failure, not the repo's."""

    verdict = RUNNER.run_case(case(("gone",)), registry=registry("gone"), root=root)

    assert verdict.result == "INCOMPLETE"
    assert verdict.unimplemented == ("gone",)
    assert verdict.checks[0].command == ()
    assert verdict.checks[0].detail == "gone.py does not exist"


def test_a_check_that_never_finishes_is_not_a_pass(root: Path) -> None:
    script(root, "slow.py", "import time\ntime.sleep(30)\n")

    verdict = RUNNER.run_case(case(("slow",)), registry=registry("slow"), root=root, timeout=0.5)

    assert verdict.result == "FAIL"
    assert verdict.checks[0].exit_code is None
    assert "did not finish within" in verdict.checks[0].detail


def test_a_case_that_asserts_nothing_cannot_pass(root: Path) -> None:
    verdict = RUNNER.run_case(case(()), registry=registry("ok"), root=root)

    assert verdict.result == "INCOMPLETE"
    assert verdict.observed == ()


def test_a_case_with_no_identifier_is_unrunnable(root: Path) -> None:
    with pytest.raises(RUNNER.Unrunnable, match="names no case"):
        RUNNER.run_case({"assertions": ["ok"]}, registry=registry("ok"), root=root)


def test_a_case_with_no_assertion_list_is_unrunnable(root: Path) -> None:
    with pytest.raises(RUNNER.Unrunnable, match="declares no assertions"):
        RUNNER.run_case({"case_id": "W00-CONTRACT-001"}, registry=registry("ok"), root=root)


def test_the_verdict_has_the_shape_the_sealer_records(root: Path) -> None:
    """One verdict shape for both kinds of case, so the sealer need not care."""

    document = RUNNER.run_case(case(("ok",)), registry=registry("ok"), root=root).as_document()

    assert {"expected", "observed", "failures", "unimplemented"} <= set(document)
    assert document["result"] == "PASS"


def test_the_verdict_names_the_check_run_so_its_bundle_has_an_address(root: Path) -> None:
    """Nothing else produces an id for a check of the repository, so this does."""

    first = RUNNER.run_case(case(("ok",)), registry=registry("ok"), root=root)
    second = RUNNER.run_case(case(("ok",)), registry=registry("ok"), root=root)

    assert first.run_id != second.run_id
    assert first.run_id.isalnum() and len(first.run_id) == 32
    assert first.as_document()["run_id"] == first.run_id


def test_kept_output_is_written_where_the_caller_asked(root: Path, tmp_path: Path) -> None:
    """The verdict carries the last words; a bundle needs the whole log."""

    outputs = tmp_path / "outputs"

    verdict = RUNNER.run_case(
        case(("ok", "bad")), registry=registry("ok", "bad"), root=root, output_directory=outputs
    )

    assert (outputs / "bad.log").is_file()
    assert "the schema is not versioned" in (outputs / "bad.log").read_text(encoding="utf-8")
    assert verdict.as_document()["checks"][1]["output"] == str(outputs / "bad.log")
    # Not asked for, not written: the field says so rather than naming a path.
    assert verdict.as_document()["checks"][0]["output"] == str(outputs / "ok.log")


def test_without_a_directory_no_output_is_kept(root: Path) -> None:
    verdict = RUNNER.run_case(case(("ok",)), registry=registry("ok"), root=root)

    assert verdict.checks[0].output_path is None
    assert verdict.as_document()["checks"][0]["output"] is None


def test_the_command_exits_by_what_it_found(root: Path) -> None:
    held = subprocess.run(
        [sys.executable, str(TOOL), "--case", str(REVIEWED_CASE)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    missing = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--case",
            str(REVIEWED_CASE),
            "--root",
            str(root),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert held.returncode == RUNNER.EXIT_HELD, held.stderr
    assert json.loads(held.stdout)["case_id"] == "W00-CONTRACT-001"
    # Against a root that holds none of the targets, nothing can be judged.
    assert missing.returncode == RUNNER.EXIT_UNRUNNABLE
    assert set(cast(list[str], json.loads(missing.stdout)["unimplemented"])) == {
        "schemas_are_versioned",
        "fixture_digests_match_manifest",
        "runtime_input_does_not_reference_oracle",
        "product_package_does_not_import_test_orchestrator",
    }


def test_a_runtime_case_is_unrunnable_here_rather_than_failing() -> None:
    """The real registry and a real case: HOST-030 is judged by the other judge.

    End to end through the command line, because *which* judge performs an
    assertion is a property of the registry rather than of the runner — a registry
    that drifted back to calling these `tool` would invoke the asserter with no
    `--case` and no `--run`, and this case would be reported as failed again with an
    argparse usage error for a detail.
    """

    result = subprocess.run(
        [sys.executable, str(TOOL), "--case", str(RUNTIME_CASE)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == RUNNER.EXIT_UNRUNNABLE, result.stderr
    document = json.loads(result.stdout)
    assert document["result"] == "INCOMPLETE"
    assert document["checks"] == [], "nothing here can perform a run-material assertion"
    assert set(cast(list[str], document["unimplemented"])) == {
        "the_run_says_which_world_it_hosted",
        "the_world_this_run_had_is_the_one_the_case_names",
        "core_was_told_the_world_was_published",
        "the_client_published_the_world_on_the_port_it_was_given",
    }
