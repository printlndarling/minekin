"""Fail CI when P0 package imports violate the frozen dependency direction."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "minekin_core"

# These are package prefixes, not a complete third-party allowlist. The checks
# deliberately target architectural seams that ordinary linters cannot express.
FORBIDDEN_BY_LAYER = {
    "domain": ("minekin_core.application", "minekin_core.adapters", "minekin_core.cli"),
    "application": ("minekin_core.adapters", "minekin_core.cli"),
}
INFRASTRUCTURE_MODULES = ("sqlite3", "socket", "subprocess")


def imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def violations() -> list[str]:
    errors: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        relative = path.relative_to(PACKAGE_ROOT)
        layer = relative.parts[0] if len(relative.parts) > 1 else ""
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, module in imported_modules(tree):
            forbidden = FORBIDDEN_BY_LAYER.get(layer, ())
            if module.startswith(forbidden):
                errors.append(f"{relative}:{lineno}: {layer} must not import {module}")
            if layer == "application" and module.split(".", 1)[0] in INFRASTRUCTURE_MODULES:
                errors.append(f"{relative}:{lineno}: application must use a port, not {module}")
            if layer == "domain" and module.split(".", 1)[0] in INFRASTRUCTURE_MODULES:
                errors.append(f"{relative}:{lineno}: domain must remain pure, not import {module}")
    return errors


def main() -> int:
    errors = violations()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Minekin package dependency boundaries: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
