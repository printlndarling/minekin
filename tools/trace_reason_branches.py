"""Which refusal branches the test suite actually fires.

Not a text search: the process traces its own line execution and reports the
`return <reason>` statements that never ran. A line that never ran is a branch no
test provoked, whichever file the name does or does not appear in.

A name appearing somewhere is not a branch being observed, and a reason name can be
returned by several functions at once — `LEDGER_UNREADABLE` is returned by eleven, so
a search that finds it has found nothing about any particular one of them.

Scope: the tests run in this process are traced. A test that invokes the asserter as
a subprocess is invisible to a trace, so "never ran" here is a **nomination** to be
confirmed by mutation — replace the line with `pass` and see whether any test goes
red — and never a verdict on its own.

Usage:

    uv run --frozen python tools/trace_reason_branches.py
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Callable
from pathlib import Path
from types import FrameType

import pytest

TARGET = Path(__file__).with_name("assert_case_evidence.py")
#: Case-folded, because the frame's filename comes from `compile` and Windows does
#: not keep the case the path was written with.
KEY = str(TARGET.resolve()).lower()

#: What `sys.settrace` takes and returns: the frame, the event's name, the event's
#: own argument, and — for the global hook — the hook that traces the lines inside.
TraceHook = Callable[[FrameType, str, object], "TraceHook | None"]


def reason_returns() -> dict[int, tuple[str, str]]:
    """Every `return <reason>` in the asserter, by line number.

    A reason is a string literal or the literal head of an f-string; a `return` of
    anything else is not one of the refusals this audit is about.
    """

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    found: dict[int, tuple[str, str]] = {}
    enclosing: list[ast.FunctionDef] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            enclosing.append(node)
            self.generic_visit(node)
            enclosing.pop()

        def visit_Return(self, node: ast.Return) -> None:
            literal = _reason_literal(node.value)
            if literal:
                owner = enclosing[-1].name if enclosing else "<module>"
                found[node.lineno] = (owner, literal)
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def _reason_literal(value: ast.expr | None) -> str:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.JoinedStr) and value.values:
        first = value.values[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return ""


ran: set[int] = set()


def line_tracer(frame: FrameType, event: str, arg: object) -> TraceHook:
    if event == "line":
        ran.add(frame.f_lineno)
    return line_tracer


def call_tracer(frame: FrameType, event: str, arg: object) -> TraceHook | None:
    """Trace the lines of the asserter, and nothing else's.

    Returning None for every other frame is what keeps this affordable: the hook is
    still called per call, but no line of the tests or of pytest itself is traced.
    """

    if frame.f_code.co_filename.lower() == KEY:
        return line_tracer
    return None


def main() -> int:
    returns = reason_returns()
    sys.settrace(call_tracer)
    try:
        code = pytest.main(["-q", "--tb=no", "-p", "no:cacheprovider"])
    finally:
        sys.settrace(None)

    never = {line: info for line, info in returns.items() if line not in ran}
    print()
    print(f"reason returns in the asserter : {len(returns)}")
    print(f"lines this run executed        : {len(returns) - len(never)}")
    print(f"reason returns that NEVER ran  : {len(never)}")
    for line in sorted(never):
        owner, literal = never[line]
        print(f"  {TARGET.name}:{line}  {owner}\n      {literal}")
    print()
    print("A reading of 0 is not proof of coverage: confirm each one by mutation.")
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
