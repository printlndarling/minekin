"""Change every refusal's words, one at a time, and see whether any test objects.

`tools/trace_reason_branches.py` says which branches are *reached*. This asks the
next question: whose judgement is *checked*. A branch that fires inside a test that
never looks at its reason is a branch whose answer nobody has verified — and a
reason rewritten to something wrong would go unnoticed, which is a different fact
from the branch never running.

The mutation is deliberately not a control-flow change. Renaming the returned
reason cannot strand the code after a guard, so nothing can fail for a reason that
belongs to the harness rather than to a test: it touches the words, and only the
words. A test that asserts on that reason fails; a test that merely reaches the
branch does not.

Two phases, because running everything 154 times costs hours. Phase one runs the
file that reads `verdict.failures` — the only place a reason is asserted on, so it
is where nearly every observer lives. Whatever phase one does not see is re-checked
against every test file that touches the asserter, including the sealer's
subprocess.

**This tool rewrites a tracked source file in place, one line at a time.** It
refuses to start unless that file is committed as it stands, and it puts the
original back in a `finally` before reporting, checking byte for byte that the
restore took. The way back from a hard kill is `git checkout -- tools/assert_case_evidence.py`.

Usage:

    uv run --frozen python tools/verify_reason_assertions.py
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SRC = REPOSITORY_ROOT / "tools" / "assert_case_evidence.py"
#: The file that reads `verdict.failures`: where an assertion's reason is compared.
ASSERTING_TESTS = ["tests/unit/test_case_evidence_assertions.py"]
#: Every test file that touches the asserter or a tool that judges with it.
EVERY_OBSERVER = [
    "tests/contract/test_case_assertions.py",
    "tests/contract/test_case_coverage.py",
    "tests/unit/test_case_evidence_assertions.py",
    "tests/unit/test_report_promotion.py",
    "tests/unit/test_report_soak.py",
    "tests/unit/test_run_repo_case.py",
    "tests/unit/test_seal_repo_case.py",
    "tests/unit/test_seal_run_evidence.py",
]
#: Prepended to each reason. Nothing a test could plausibly assert, so it cannot be
#: confused with a real one, and keeping the original text after it means a reader
#: can still see which refusal was changed.
MUTANT = "MUTATED_REASON"


@dataclass(frozen=True, slots=True)
class Refusal:
    """One `return <reason>`, with the byte span of the literal that spells it."""

    line: int
    owner: str
    reason: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int


def refusals(text: str) -> list[Refusal]:
    """Every refusal in the asserter, in source order."""

    tree = ast.parse(text)
    found: list[Refusal] = []
    enclosing: list[ast.FunctionDef] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            enclosing.append(node)
            self.generic_visit(node)
            enclosing.pop()

        def visit_Return(self, node: ast.Return) -> None:
            value = node.value
            target: ast.Constant | None = None
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                target = value
            elif isinstance(value, ast.JoinedStr) and value.values:
                first = value.values[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    target = first
            literal = None if target is None else target.value
            if (
                isinstance(literal, str)
                and literal
                and target is not None
                and target.end_col_offset is not None
            ):
                found.append(
                    Refusal(
                        line=node.lineno,
                        owner=enclosing[-1].name if enclosing else "<module>",
                        reason=literal,
                        start_line=target.lineno,
                        start_col=target.col_offset,
                        end_line=target.end_lineno or target.lineno,
                        end_col=target.end_col_offset,
                    )
                )
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def line_starts(text: str) -> list[int]:
    """The byte offset each line starts at, indexed from one like `ast`'s lines."""

    starts = [0]
    for line in text.split("\n")[:-1]:
        starts.append(starts[-1] + len(line.encode("utf-8")) + 1)
    return starts


def corrupt(text: str, refusal: Refusal) -> str:
    """The same module with one refusal's words replaced."""

    data = text.encode("utf-8")
    starts = line_starts(text)
    start = starts[refusal.start_line - 1] + refusal.start_col
    end = starts[refusal.end_line - 1] + refusal.end_col
    written = f"{MUTANT}:{refusal.reason}"
    # Decided from the bytes rather than from the node's parent. A span that sits
    # inside a quote character is an f-string part; one that does not is a whole
    # literal. Implicit concatenation puts both kinds in one JoinedStr, so the
    # parent says nothing — `"A:" f"{b}"` begins with an ordinary literal.
    inside_quotes = data[start - 1 : start] in (b'"', b"'")
    replacement = written if inside_quotes else f'"{written}"'
    return (data[:start] + replacement.encode("utf-8") + data[end:]).decode("utf-8")


def run(files: list[str]) -> list[str]:
    """The tests this mutation made fail, by node id."""

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *files,
            "-q",
            "--no-header",
            "-rf",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPOSITORY_ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.startswith("FAILED")]


def require_clean() -> None:
    """Refuse to start unless the asserter is committed as it stands."""

    relative = SRC.relative_to(REPOSITORY_ROOT).as_posix()
    completed = subprocess.run(
        ["git", "diff", "--quiet", "--", relative],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"{relative} has uncommitted changes; commit or stash them first")


def main() -> int:
    require_clean()
    # Bytes, not text, on both ends. `write_text` translates every "\n" to the
    # platform's separator, so on Windows the file would come back as CRLF — and
    # reading it back through the same translation would hide that, which makes
    # "the restore took" a claim about what the file says and not about its bytes.
    original = SRC.read_bytes()
    text = original.decode("utf-8")
    unchecked: list[Refusal] = []
    checked = 0
    try:
        targets: list[Refusal] = []
        for refusal in refusals(text):
            try:
                compile(corrupt(text, refusal), str(SRC), "exec")
            except SyntaxError as error:
                # A mutation that will not parse says nothing about any test, so it
                # is reported rather than counted as "nothing objected".
                print(f"{refusal.line:5d} UNPARSEABLE {refusal.owner}: {error}", flush=True)
                continue
            targets.append(refusal)

        for phase, files in ((1, ASSERTING_TESTS), (2, EVERY_OBSERVER)):
            pending = targets if phase == 1 else list(unchecked)
            unchecked = []
            for refusal in pending:
                SRC.write_bytes(corrupt(text, refusal).encode("utf-8"))
                reds = run(files)
                if reds:
                    checked += 1
                    print(
                        f"{refusal.line:5d} checked   {refusal.owner}:{refusal.reason[:44]}",
                        flush=True,
                    )
                else:
                    unchecked.append(refusal)
                    print(
                        f"{refusal.line:5d} unchecked {refusal.owner}:{refusal.reason}",
                        flush=True,
                    )
            if phase == 1:
                print(f"\nphase 1: {checked} checked, {len(unchecked)} to re-check\n", flush=True)
    finally:
        SRC.write_bytes(original)
        if SRC.read_bytes() != original:
            raise SystemExit(
                "RESTORE FAILED: recover with `git checkout -- tools/assert_case_evidence.py`"
            )
        print(
            f"\n{checked} of {len(refusals(text))} refusals are asserted on by a test;"
            f" {len(unchecked)} are not."
        )
    return 0 if not unchecked else 1


if __name__ == "__main__":
    raise SystemExit(main())
