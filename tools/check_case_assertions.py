"""Check that every assertion a case names is one this repository implements.

A case manifest lists assertion names as strings, and the promotion machinery
accepts whatever a bundle records under them. Nothing, until this check, tied
those names to code: a case could name an assertion nothing performs, or an
implementation could be renamed out from under a case, and either way the case
would still look covered.

This verifies the *declaration*, not the behaviour — it does not run the checks,
because running them is the orchestrator's job and belongs with the runtime cases
that need a client. What it guarantees is that the names a case relies on point at
something that exists, so a rename breaks this check instead of silently orphaning
an assertion.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"


@dataclass(frozen=True, slots=True)
class Implementation:
    """Where one assertion name is actually performed."""

    kind: str
    target: str

    def missing_reason(self, root: Path) -> str | None:
        """Why this implementation cannot be found, or None when it is there."""

        if self.kind == "tool":
            path = root / self.target
            return None if path.is_file() else f"{self.target} does not exist"
        if self.kind == "pytest":
            file_name, _, test_name = self.target.partition("::")
            path = root / file_name
            if not path.is_file():
                return f"{file_name} does not exist"
            if f"def {test_name}(" not in path.read_text(encoding="utf-8"):
                return f"{file_name} has no {test_name}"
            return None
        return f"unknown implementation kind {self.kind!r}"


# The names a case may rely on. A case naming anything else is a case whose
# evidence cannot be checked, so it fails here rather than at promotion time.
IMPLEMENTATIONS: dict[str, Implementation] = {
    "schemas_are_versioned": Implementation(
        "pytest",
        "tests/contract/test_fixture_boundaries.py"
        "::test_all_json_contracts_are_parseable_and_versioned",
    ),
    "fixture_digests_match_manifest": Implementation("tool", "tools/verify_fixture_digests.py"),
    "runtime_input_does_not_reference_oracle": Implementation(
        "pytest",
        "tests/contract/test_fixture_boundaries.py::test_runtime_inputs_do_not_reference_oracle",
    ),
    "product_package_does_not_import_test_orchestrator": Implementation(
        "pytest",
        "tests/contract/test_fixture_boundaries.py"
        "::test_product_build_and_import_boundaries_exclude_oracle",
    ),
}


def violations(
    cases_dir: Path, *, registry: dict[str, Implementation], root: Path = REPOSITORY_ROOT
) -> list[str]:
    from minekin_core.adapters.evidence.promotion import load_case_registry

    errors: list[str] = []
    registry_module = load_case_registry(cases_dir)
    for case in registry_module.cases:
        for assertion in case.assertions:
            if assertion not in registry:
                errors.append(f"{case.case_id}: names an assertion nothing implements: {assertion}")
    for name, implementation in sorted(registry.items()):
        reason = implementation.missing_reason(root)
        if reason is not None:
            errors.append(f"{name}: {reason}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-dir", type=Path, default=CASES)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="where the implementations are looked for; the repository by default",
    )
    args = parser.parse_args()
    errors = violations(args.cases_dir, registry=IMPLEMENTATIONS, root=args.root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Case assertion implementations: OK ({len(IMPLEMENTATIONS)} registered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
