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
    #: The function inside the target that performs this assertion, when the
    #: target implements several. Without it a `tool` target can only say the
    #: file is there, and a rename inside the file would leave the name
    #: registered and unperformed.
    symbol: str = ""

    def missing_reason(self, root: Path) -> str | None:
        """Why this implementation cannot be found, or None when it is there."""

        if self.kind == "tool":
            path = root / self.target
            if not path.is_file():
                return f"{self.target} does not exist"
            if self.symbol and f"def {self.symbol}(" not in path.read_text(encoding="utf-8"):
                return f"{self.target} has no {self.symbol}"
            return None
        if self.kind == "pytest":
            file_name, _, test_name = self.target.partition("::")
            path = root / file_name
            if not path.is_file():
                return f"{file_name} does not exist"
            if f"def {test_name}(" not in path.read_text(encoding="utf-8"):
                return f"{file_name} has no {test_name}"
            return None
        return f"unknown implementation kind {self.kind!r}"


#: The tool that judges a finished run's evidence. Every assertion a *runtime*
#: case declares is performed by one function in it, named after the assertion.
RUNTIME_ASSERTER = "tools/assert_case_evidence.py"


def _runtime(name: str) -> Implementation:
    return Implementation("tool", RUNTIME_ASSERTER, symbol=name)


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
    "server_observed_join_identity": _runtime("server_observed_join_identity"),
    "first_snapshot_admitted": _runtime("first_snapshot_admitted"),
    "leave_after_join_observed": _runtime("leave_after_join_observed"),
    "handshake_accepted_by_core": _runtime("handshake_accepted_by_core"),
    "stayed_observe_only": _runtime("stayed_observe_only"),
    "move_input_was_leased": _runtime("move_input_was_leased"),
    "the_bridge_carried_the_input_out": _runtime("the_bridge_carried_the_input_out"),
    "the_server_saw_the_kin_move": _runtime("the_server_saw_the_kin_move"),
    "the_lease_expired_and_was_released": _runtime("the_lease_expired_and_was_released"),
    "the_bridge_released_the_input_when_the_ipc_was_lost": _runtime(
        "the_bridge_released_the_input_when_the_ipc_was_lost"
    ),
    "the_server_saw_the_kin_stop_after_the_move": _runtime(
        "the_server_saw_the_kin_stop_after_the_move"
    ),
    "the_attempt_was_abandoned_at_its_deadline": _runtime(
        "the_attempt_was_abandoned_at_its_deadline"
    ),
    "no_world_was_joined": _runtime("no_world_was_joined"),
    "the_cancel_reached_the_client_and_was_acted_on": _runtime(
        "the_cancel_reached_the_client_and_was_acted_on"
    ),
    "the_refusal_was_classified_in_the_ledger": _runtime(
        "the_refusal_was_classified_in_the_ledger"
    ),
    "the_bridge_classified_the_refusal": _runtime("the_bridge_classified_the_refusal"),
    "the_server_saw_the_kin_turn": _runtime("the_server_saw_the_kin_turn"),
    "the_server_saw_the_block_change": _runtime("the_server_saw_the_block_change"),
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
