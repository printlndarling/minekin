"""Fail CI when P0 package imports violate the frozen dependency direction.

Three things, and they are all seams a linter cannot see: which layer may import
which, that product code and the Bridge carry no reference to the test oracle, and
that a case manifest's declarations are about something real — the oracle on its own
side of the line, and every declared input resolving to a file. The last of those is
the one that was missing: a declaration nothing checks is a promise, and this
repository's answer to that has always been to check the declaration instead.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "minekin_core"
BRIDGE_ROOT = REPOSITORY_ROOT / "bridge"
CASE_FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"
ORACLE_DIRECTORY = "tests/oracle/"

# These are package prefixes, not a complete third-party allowlist. The checks
# deliberately target architectural seams that ordinary linters cannot express.
FORBIDDEN_BY_LAYER = {
    "domain": ("minekin_core.application", "minekin_core.adapters", "minekin_core.cli"),
    "application": ("minekin_core.adapters", "minekin_core.cli"),
}
INFRASTRUCTURE_MODULES = ("sqlite3", "socket", "subprocess")
PRODUCT_ORACLE_REFERENCES = (
    "tests/oracle",
    "tests\\oracle",
    "tests.oracle",
    "test-orchestrator",
    "test_orchestrator",
    "minekin_test_oracle",
)


def _module_name(path: Path) -> tuple[str, ...]:
    relative = path.relative_to(PACKAGE_ROOT).with_suffix("")
    parts = ("minekin_core", *relative.parts)
    return parts[:-1] if parts[-1] == "__init__" else parts


def imported_modules(tree: ast.AST, path: Path) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    current = _module_name(path)
    package = current if path.stem == "__init__" else current[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(package) - (node.level - 1)
                base = package[: max(0, keep)]
                suffix = tuple(node.module.split(".")) if node.module else ()
                imports.append((node.lineno, ".".join((*base, *suffix))))
            elif node.module:
                imports.append((node.lineno, node.module))
    return imports


def violations(cases_dir: Path = CASE_FIXTURES) -> list[str]:
    errors: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        relative = path.relative_to(PACKAGE_ROOT)
        layer = relative.parts[0] if len(relative.parts) > 1 else ""
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, module in imported_modules(tree, path):
            forbidden = FORBIDDEN_BY_LAYER.get(layer, ())
            if module.startswith(forbidden):
                errors.append(f"{relative}:{lineno}: {layer} must not import {module}")
            if layer == "application" and module.split(".", 1)[0] in INFRASTRUCTURE_MODULES:
                errors.append(f"{relative}:{lineno}: application must use a port, not {module}")
            if layer == "domain" and module.split(".", 1)[0] in INFRASTRUCTURE_MODULES:
                errors.append(f"{relative}:{lineno}: domain must remain pure, not import {module}")
            if module == "tests" or module.startswith(("tests.", "test_orchestrator")):
                errors.append(
                    f"{relative}:{lineno}: product code must not import test code: {module}"
                )

        text = path.read_text(encoding="utf-8").casefold()
        for marker in PRODUCT_ORACLE_REFERENCES:
            if marker in text:
                errors.append(f"{relative}: product code references test oracle marker {marker!r}")

        if any(part.casefold() == "oracle" for part in relative.parts):
            errors.append(f"{relative}: oracle files must not exist in the product package")

    for path in sorted(BRIDGE_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in {".java", ".json", ".kts", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8").casefold()
        relative = path.relative_to(REPOSITORY_ROOT)
        for marker in PRODUCT_ORACLE_REFERENCES:
            if marker in text:
                errors.append(
                    f"{relative}: Bridge product references test oracle marker {marker!r}"
                )

    pyproject = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = (
        pyproject.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
    )
    if wheel.get("packages") != ["src/minekin_core"]:
        errors.append("pyproject.toml: wheel must contain only src/minekin_core")
    if "force-include" in wheel:
        errors.append("pyproject.toml: wheel force-include could bypass the oracle boundary")
    errors.extend(_case_manifest_errors(cases_dir))
    return errors


def _case_manifest_errors(cases_dir: Path) -> list[str]:
    """A case declares its oracle inputs separately, so the declaration is checked.

    The product validates a case manifest's shape; only this side is allowed to
    know that an oracle exists at all, so the boundary rule lives here.

    Three rules, and they are all about the same thing: what a case *declares* it
    depends on has to mean something. The first two keep the oracle on its own side
    of the line — an ordinary input may not name it, and an oracle input may not be
    anything else. The third is the one that was missing, and it is the oldest hole
    of the three: a declared input is a name, and nothing checked that the name
    resolves. A case could name a fixture that was renamed, moved or deleted and
    still read as covered — the same failure `check_case_assertions.py` was written
    for one field over, where the names a case relies on are tied to something that
    exists. Pathed the way the promotion loader paths `input_digests`, because two
    readers of one manifest disagreeing about what a relative path is would be a
    third hole rather than a fix.
    """

    errors: list[str] = []
    for path in sorted(cases_dir.glob("*.json")):
        relative = path.relative_to(cases_dir).name
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            errors.append(f"{relative}: case manifest is unreadable: {error}")
            continue
        if not isinstance(case, dict):
            errors.append(f"{relative}: case manifest must be an object")
            continue
        document = cast(dict[str, object], case)
        inputs = document.get("inputs", [])
        oracle_inputs = document.get("oracle_inputs", [])
        if not isinstance(inputs, list) or not isinstance(oracle_inputs, list):
            errors.append(f"{relative}: inputs and oracle_inputs must be arrays")
            continue
        for entry in cast(list[object], inputs):
            folded = str(entry).casefold()
            if any(marker in folded for marker in PRODUCT_ORACLE_REFERENCES):
                errors.append(f"{relative}: a declared input references the oracle: {entry!r}")
        for entry in cast(list[object], oracle_inputs):
            if not str(entry).startswith(ORACLE_DIRECTORY):
                errors.append(
                    f"{relative}: an oracle input is outside {ORACLE_DIRECTORY}: {entry!r}"
                )
        for entry in (*cast(list[object], inputs), *cast(list[object], oracle_inputs)):
            errors.extend(_declared_input_errors(relative, str(entry)))
    return errors


def _declared_input_errors(relative: str, declared: str) -> list[str]:
    """Why one declared input is not something a case can depend on.

    A glob is allowed, because a case about every schema is a real case and
    `schemas/*.schema.json` says that better than a list that goes stale. What is
    not allowed is one that matches nothing: the declaration would then be about no
    file at all, and the case would keep passing while its subject was gone.
    """

    logical = PurePosixPath(declared)
    if (
        logical.is_absolute()
        or ".." in logical.parts
        or "\\" in declared
        or logical.as_posix() != declared
    ):
        return [f"{relative}: a declared input is not a repository-relative path: {declared!r}"]
    if not any(REPOSITORY_ROOT.glob(declared)):
        return [f"{relative}: a declared input matches nothing: {declared!r}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-dir", type=Path, default=CASE_FIXTURES)
    args = parser.parse_args()
    errors = violations(args.cases_dir)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Minekin package dependency boundaries: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
