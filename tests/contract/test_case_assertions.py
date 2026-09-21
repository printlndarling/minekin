"""Every assertion a case names must point at something that exists.

A case manifest lists assertion names as strings, and promotion accepts whatever a
bundle records under them, so a name nothing implements would look like coverage.
This checks the declaration rather than the behaviour: running the assertions is
the orchestrator's job and belongs with the runtime cases.

It checks a second thing as well, because the first one turned out not to be enough:
a name that still resolves is not the same check. `leave_after_join_observed` was
rewritten from "Core reported a clean exit" to "the server's own line is what counts"
and no manifest digest moved, so one case version meant two different criteria and a
bundle sealed under the first promoted as evidence for the second. Each case now
records the digest of the source that performs each of its assertions, and these
tests are about that record being required, scoped and current.
"""

from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/check_case_assertions.py"
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"
ASSERTER = "tools/assert_case_evidence.py"


def run_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def case_document(
    assertions: list[str], digests: dict[str, str] | None = None
) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": 1,
        "case_id": "W00-CONTRACT-001",
        "work_package": "W00",
        "mandatory": True,
        "inputs": ["schemas/*.schema.json"],
        "assertions": assertions,
    }
    if digests is not None:
        document["assertion_digests"] = digests
    return document


def write_case(directory: Path, assertions: list[str], digests: dict[str, str] | None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "case.json").write_text(
        json.dumps(case_document(assertions, digests)), encoding="utf-8"
    )


def gate() -> ModuleType:
    """The tool itself, imported the way its own tests reach it."""

    sys.path.insert(0, str(REPOSITORY_ROOT / "tools"))
    try:
        return importlib.import_module("check_case_assertions")
    finally:
        sys.path.pop(0)


def digests_of(*assertions: str) -> dict[str, str]:
    """What the tool currently resolves these assertion names to, asked of the tool."""

    tool = gate()
    return tool.recorded_digests(list(assertions), tool.IMPLEMENTATIONS, REPOSITORY_ROOT)


def mutated_root(tmp_path: Path, symbol: str) -> Path:
    """A tree like this repository's, with one assertion's source changed.

    Everything the registry names is copied in, because a root holding only the mutated
    file would leave every *other* implementation unresolvable and the gate would fail
    for reasons that have nothing to do with the mutation under test.
    """

    root = tmp_path / "root"
    for target in sorted(
        {item.target.partition("::")[0] for item in gate().IMPLEMENTATIONS.values()}
    ):
        destination = root / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY_ROOT / target, destination)
    source = (root / ASSERTER).read_text(encoding="utf-8")
    marker = f"def {symbol}("
    assert marker in source
    line_end = source.index("\n", source.index(marker)) + 1
    changed = (
        source[:line_end] + "    # a change the recorded digest has not seen\n" + source[line_end:]
    )
    (root / ASSERTER).write_text(changed, encoding="utf-8")
    return root


def test_the_reviewed_cases_name_only_implemented_assertions() -> None:
    result = run_tool()

    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_a_case_naming_an_unimplemented_assertion_is_refused(tmp_path: Path) -> None:
    write_case(tmp_path, ["schemas_are_versioned", "everything_is_fine"], digests=None)

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


def test_a_renamed_function_inside_a_tool_is_refused(tmp_path: Path) -> None:
    """A file that exists is not an assertion that is performed.

    One tool implements several assertions, one function each, so "the target
    exists" was enough to keep a name registered after the function performing it
    was renamed — the name would look covered by a file that no longer carries
    it. The registry therefore names the function too, and this is that check.
    """

    tool = tmp_path / "tools" / "assert_case_evidence.py"
    tool.parent.mkdir(parents=True)
    tool.write_text('"""Some other tool entirely."""\n', encoding="utf-8")

    result = run_tool("--root", str(tmp_path))

    assert result.returncode == 1
    assert "has no server_observed_join_identity" in result.stderr


# ---------------------------------------------------------------------------
# The record of what each name pointed at
# ---------------------------------------------------------------------------


def test_every_reviewed_case_records_what_implements_it() -> None:
    """The gate being green over the real cases has to mean they are recorded.

    Without this, a case whose field was deleted would take the "nothing to compare"
    path, and the whole repository could pass while none of its cases recorded the
    criteria their versions claim to cover.
    """

    for path in sorted(CASES.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        recorded = document.get("assertion_digests", {})

        assert set(recorded) == set(document["assertions"]), path.name


def test_a_case_that_records_nothing_is_refused(tmp_path: Path) -> None:
    write_case(tmp_path, ["stayed_observe_only"], digests=None)

    result = run_tool("--cases-dir", str(tmp_path))

    assert result.returncode == 1
    assert "has no entry for stayed_observe_only" in result.stderr


def test_a_stale_record_is_refused_and_names_the_assertion(tmp_path: Path) -> None:
    """Same words, different implementation: the case version must move."""

    root = mutated_root(tmp_path, "stayed_observe_only")
    write_case(tmp_path, ["stayed_observe_only"], digests=digests_of("stayed_observe_only"))

    result = run_tool("--cases-dir", str(tmp_path), "--root", str(root))

    assert result.returncode == 1
    assert "stayed_observe_only is implemented by" in result.stderr
    assert "re-record with --record" in result.stderr


def test_a_case_is_unaffected_by_an_assertion_it_does_not_name(tmp_path: Path) -> None:
    """The record is per case, so a change elsewhere is not this case's business.

    The negative control for the test above: the same mutation, and a case that names
    a different assertion, stays green. A version that moved whenever any assertion
    anywhere changed would be a version that means nothing in particular.
    """

    root = mutated_root(tmp_path, "stayed_observe_only")
    write_case(tmp_path, ["no_lease_was_granted"], digests=digests_of("no_lease_was_granted"))

    result = run_tool("--cases-dir", str(tmp_path), "--root", str(root))

    assert result.returncode == 0, result.stderr


def test_a_record_for_an_assertion_the_case_does_not_name_is_refused(tmp_path: Path) -> None:
    """An entry nothing asserts is an entry nobody reviewed."""

    digests = digests_of("stayed_observe_only")
    digests["no_lease_was_granted"] = digests["stayed_observe_only"]
    write_case(tmp_path, ["stayed_observe_only"], digests=digests)

    result = run_tool("--cases-dir", str(tmp_path))

    assert result.returncode == 1
    assert "which this case does not name" in result.stderr


def test_recording_writes_what_the_check_then_accepts(tmp_path: Path) -> None:
    """`--record` is the way out of a refusal, and it must be idempotent."""

    cases = tmp_path / "cases"
    shutil.copytree(CASES, cases)
    stale = cases / "core-030.json"
    document = json.loads(stale.read_text(encoding="utf-8"))
    document["assertion_digests"] = dict.fromkeys(document["assertions"], "0" * 64)
    stale.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    assert run_tool("--cases-dir", str(cases)).returncode == 1

    recorded = run_tool("--record", "--cases-dir", str(cases))

    assert recorded.returncode == 0, recorded.stderr
    assert "recorded 16 case(s)" in recorded.stdout
    assert run_tool("--cases-dir", str(cases)).returncode == 0
    # And recording again changes nothing, so a renew is a no-op when nothing moved.
    before = stale.read_bytes()
    assert run_tool("--record", "--cases-dir", str(cases)).returncode == 0
    assert stale.read_bytes() == before


def test_recording_leaves_the_rest_of_the_case_file_alone(tmp_path: Path) -> None:
    """Re-rendering would reflow every case and bury the change that matters."""

    cases = tmp_path / "cases"
    shutil.copytree(CASES, cases)

    def without_the_record(lines: list[str]) -> list[str]:
        row = re.compile(r'^    "[a-z_]+": "[0-9a-f]{64}",?$')
        return [line for line in lines if '"assertion_digests"' not in line and not row.match(line)]

    before = without_the_record((cases / "core-030.json").read_text(encoding="utf-8").splitlines())

    assert run_tool("--record", "--cases-dir", str(cases)).returncode == 0

    after = without_the_record((cases / "core-030.json").read_text(encoding="utf-8").splitlines())

    assert after == before


def test_an_implementation_digest_does_not_depend_on_the_line_endings(tmp_path: Path) -> None:
    """One function checked out on Windows and on Linux is one function.

    The digest is taken over the source with CRLF normalised away, so the answer is
    "is this the implementation that was reviewed" rather than "which platform
    recorded it". This repository has already paid for that mistake once, on the
    Bridge source tree.
    """

    source = (REPOSITORY_ROOT / ASSERTER).read_text(encoding="utf-8")
    roots: list[Path] = []
    for name, newline in (("lf", "\n"), ("crlf", "\r\n")):
        root = tmp_path / name
        (root / "tools").mkdir(parents=True)
        (root / ASSERTER).write_bytes(source.replace("\n", newline).encode("utf-8"))
        roots.append(root)

    sys.path.insert(0, str(REPOSITORY_ROOT / "tools"))
    try:
        tool = gate()
        implementation = tool.IMPLEMENTATIONS["stayed_observe_only"]
        digests = [tool.implementation_digest(implementation, root) for root in roots]
    finally:
        sys.path.pop(0)

    assert digests[0] is not None
    assert digests[0] == digests[1]
