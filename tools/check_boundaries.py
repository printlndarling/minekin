"""Fail CI when P0 package imports violate the frozen dependency direction."""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from pathlib import Path
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
    return errors


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
