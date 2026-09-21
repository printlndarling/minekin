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

It also pins *which* implementation each name pointed at, because a name that
still resolves is not the same thing as the same check. That hole was found the
way these usually are: `leave_after_join_observed` was rewritten from "Core
reported a clean exit" to "the server's own line is what counts", and no manifest
digest moved — one case version, two different criteria, and a bundle sealed under
the first promoted as evidence for the second. So each case records the digest of
the source that performs each of its assertions, inside the manifest, which is
what makes `case_version` cover the criteria rather than only their names.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from minekin_core.adapters.evidence.promotion import load_case_registry
from minekin_core.domain.cases import CaseManifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"

#: The field each case records those digests in. The same shape as `input_digests`,
#: for the same reason: a case that names something outside itself says which bytes
#: outside itself it means.
DIGESTS_FIELD = "assertion_digests"


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

    def source(self, root: Path) -> str | None:
        """The reviewed text of what performs this assertion, or None when it is gone.

        The whole file when the target performs one assertion and nothing narrower can
        be named, the function otherwise. Taken verbatim, docstring included: a
        rewording of what an assertion means is a change to the thing a case version
        claims to cover, and a digest that skipped prose would be a digest that called
        two different statements of the same check equal.
        """

        file_name = self.target.partition("::")[0]
        path = root / file_name
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        symbol = self.symbol or (self.target.partition("::")[2] if self.kind == "pytest" else "")
        if not symbol:
            return text
        return _function_source(text, symbol)

    def missing_reason(self, root: Path) -> str | None:
        """Why this implementation cannot be found, or None when it is there."""

        if self.kind not in {"tool", "pytest"}:
            return f"unknown implementation kind {self.kind!r}"
        file_name, _, test_name = self.target.partition("::")
        if not (root / file_name).is_file():
            return f"{file_name} does not exist"
        if self.source(root) is None:
            return f"{file_name} has no {self.symbol or test_name}"
        return None


def _function_source(text: str, symbol: str) -> str | None:
    """One top-level function's source, from its decorators down to its last line."""

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or node.name != symbol:
            continue
        if node.end_lineno is None:  # pragma: no cover - every parsed node has one
            return None
        # From the first decorator rather than from `def`: a parametrisation is part
        # of what the test covers, so it is part of what the case version names.
        first = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
        return "\n".join(text.splitlines()[first - 1 : node.end_lineno])
    return None


def implementation_digest(implementation: Implementation, root: Path) -> str | None:
    """The digest a case records for one assertion's implementation.

    Normalised to LF, because one function checked out on Windows and on Linux is one
    function: hashing the bytes as they lie would make the digest answer "which
    platform recorded this" instead of "is this the implementation that was reviewed".
    """

    source = implementation.source(root)
    if source is None:
        return None
    return hashlib.sha256(source.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def recorded_digests(
    assertions: Sequence[str], registry: Mapping[str, Implementation], root: Path
) -> dict[str, str]:
    """What each of these assertion names currently resolves to, by name.

    A name this registry does not know, or one whose implementation cannot be read,
    is left out rather than given a placeholder: the caller reports those separately,
    and a placeholder in the map would be a digest that matches nothing on purpose.
    """

    found: dict[str, str] = {}
    for name in assertions:
        implementation = registry.get(name)
        if implementation is None:
            continue
        digest = implementation_digest(implementation, root)
        if digest is not None:
            found[name] = digest
    return found


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
    # CORE-070's channel-level claims. They are performed by tests rather than by
    # the runtime asserter because that is where the subject is: a half frame, an
    # oversize frame and a flood are things a *channel* does, and the one side
    # that can be driven into them on demand is a test peer rather than a real
    # Bridge. The disconnect half of the same case is a run, and is evidenced by
    # runs: ADMIT-110 and CORE-060 both end a session from the other side.
    "a_frame_that_stops_halfway_is_refused": Implementation(
        "pytest",
        "tests/contract/test_bridge_ipc_host.py::test_a_frame_that_stops_halfway_is_refused",
    ),
    "an_oversize_frame_is_rejected_before_it_is_allocated": Implementation(
        "pytest",
        "tests/contract/test_bridge_ipc_host.py"
        "::test_oversize_frame_header_is_rejected_before_allocation",
    ),
    "a_flood_of_events_fails_closed_rather_than_dropping_them": Implementation(
        "pytest",
        "tests/contract/test_bridge_ipc_host.py"
        "::test_a_flood_of_events_fails_closed_rather_than_dropping_them",
    ),
    "no_input_is_replayed_after_an_ambiguous_disconnect": Implementation(
        "pytest",
        "tests/unit/test_session_supervision.py"
        "::test_no_input_is_replayed_after_an_ambiguous_disconnect",
    ),
    "server_observed_join_identity": _runtime("server_observed_join_identity"),
    "first_snapshot_admitted": _runtime("first_snapshot_admitted"),
    "the_run_says_which_world_it_hosted": _runtime("the_run_says_which_world_it_hosted"),
    "the_world_this_run_had_is_the_one_the_case_names": _runtime(
        "the_world_this_run_had_is_the_one_the_case_names"
    ),
    "the_world_this_run_joined_is_the_one_the_case_names": _runtime(
        "the_world_this_run_joined_is_the_one_the_case_names"
    ),
    "the_first_snapshot_of_the_world_it_dialled_was_admitted": _runtime(
        "the_first_snapshot_of_the_world_it_dialled_was_admitted"
    ),
    "another_kin_joined_the_world_this_run_hosted": _runtime(
        "another_kin_joined_the_world_this_run_hosted"
    ),
    "the_world_saw_that_kin_leave_again": _runtime("the_world_saw_that_kin_leave_again"),
    "core_was_told_the_world_was_published": _runtime("core_was_told_the_world_was_published"),
    "the_client_published_the_world_on_the_port_it_was_given": _runtime(
        "the_client_published_the_world_on_the_port_it_was_given"
    ),
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
    # CORE-060's own half: the fault the harness injected, evidenced by the record
    # the helper writes rather than by the harness saying it happened.
    "runtime_controller_sigkill_was_confirmed": _runtime(
        "runtime_controller_sigkill_was_confirmed"
    ),
    "server_jvm_sigkill_was_confirmed": _runtime("server_jvm_sigkill_was_confirmed"),
    "client_jvm_sigkill_was_confirmed": _runtime("client_jvm_sigkill_was_confirmed"),
    "the_ledger_recorded_the_session_ending": _runtime("the_ledger_recorded_the_session_ending"),
    "the_previous_run_left_the_kin_holding_input": _runtime(
        "the_previous_run_left_the_kin_holding_input"
    ),
    # L6's baseline: the measurement's own integrity, and the world it was taken in.
    "the_soak_held_for_the_duration_it_was_asked_for": _runtime(
        "the_soak_held_for_the_duration_it_was_asked_for"
    ),
    "both_jvms_were_sampled_throughout_the_soak": _runtime(
        "both_jvms_were_sampled_throughout_the_soak"
    ),
    "the_restart_runs_as_a_new_session": _runtime("the_restart_runs_as_a_new_session"),
    "the_restart_reconciled_before_it_started": _runtime(
        "the_restart_reconciled_before_it_started"
    ),
    "the_server_log_has_no_graceful_shutdown": _runtime("the_server_log_has_no_graceful_shutdown"),
    "the_ledger_recorded_world_loss": _runtime("the_ledger_recorded_world_loss"),
    "the_bridge_released_input_when_play_ended": _runtime(
        "the_bridge_released_input_when_play_ended"
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
    "input_was_refused_before_the_world_was_playable": _runtime(
        "input_was_refused_before_the_world_was_playable"
    ),
    "no_lease_was_granted": _runtime("no_lease_was_granted"),
    "the_bridge_never_pressed_a_key": _runtime("the_bridge_never_pressed_a_key"),
    "the_server_saw_the_kin_arrive_and_never_move": _runtime(
        "the_server_saw_the_kin_arrive_and_never_move"
    ),
    # HOSTCTL-001/010: the world-creation profile. Their subject is a pure function of
    # a proposal and the policy, so the subject of each claim is a test — the same
    # arrangement CORE-070 uses, and for the same reason: a client would add nothing
    # to a claim about what a digest covers or what a refusal says.
    "a_second_synthesis_produces_the_same_effective_profile": Implementation(
        "pytest",
        "tests/unit/test_world_creation.py::test_a_second_synthesis_produces_the_same_effective_profile",
    ),
    "the_display_name_does_not_name_the_storage_slot": Implementation(
        "pytest",
        "tests/unit/test_world_creation.py::test_the_display_name_does_not_name_the_storage_slot",
    ),
    "a_proposal_outside_the_p0_archetype_is_refused": Implementation(
        "pytest",
        "tests/unit/test_world_creation.py::test_a_proposal_outside_the_p0_archetype_is_refused",
    ),
    "the_refusal_names_what_the_proposal_asked_for": Implementation(
        "pytest",
        "tests/unit/test_world_creation.py::test_the_refusal_names_what_the_proposal_asked_for",
    ),
    # HOSTCTL-050: what a host command's completion may move. The subject is the
    # admission rule, which is a pure function of the world and the completion — the
    # real late callback is the Bridge's half and is not what these two claim.
    "a_completion_from_the_previous_generation_cannot_move_the_world": Implementation(
        "pytest",
        "tests/unit/test_hosted_world.py::test_a_completion_from_the_previous_generation_cannot_move_the_world",
    ),
    "a_second_creation_in_one_epoch_is_refused": Implementation(
        "pytest",
        "tests/unit/test_hosted_world.py::test_a_second_creation_in_one_epoch_is_refused",
    ),
    # HOSTCOMMIT-110: the three ways a world's identity is decided. Each assertion is
    # the rule the commit-recovery contract states for one observed change, and the
    # subject of all three is a pure function of a record and an observation.
    "rebuilding_a_name_makes_a_new_world": Implementation(
        "pytest",
        "tests/unit/test_world_identity.py::test_rebuilding_a_name_makes_a_new_world",
    ),
    "an_address_that_holds_another_save_is_not_decided_here": Implementation(
        "pytest",
        "tests/unit/test_world_identity.py::test_an_address_that_holds_another_save_is_not_decided_here",
    ),
    "a_lan_port_change_does_not_move_the_identity": Implementation(
        "pytest",
        "tests/unit/test_world_identity.py::test_a_lan_port_change_does_not_move_the_identity",
    ),
}


def violations(
    cases_dir: Path, *, registry: dict[str, Implementation], root: Path = REPOSITORY_ROOT
) -> list[str]:
    errors: list[str] = []
    for case in load_case_registry(cases_dir).cases:
        for assertion in case.assertions:
            if assertion not in registry:
                errors.append(f"{case.case_id}: names an assertion nothing implements: {assertion}")
        errors.extend(_digest_violations(case, registry, root))
    for name, implementation in sorted(registry.items()):
        reason = implementation.missing_reason(root)
        if reason is not None:
            errors.append(f"{name}: {reason}")
    return errors


def _digest_violations(
    case: CaseManifest, registry: Mapping[str, Implementation], root: Path
) -> list[str]:
    """Whether this case's version covers the implementations it says it relies on.

    Every case currently resolves, so a missing map entry and a moved digest are both
    errors rather than one being excused by the other: a case that recorded nothing is
    a case whose version says nothing about its criteria, and that is the hole this
    field exists to close, not a state to tolerate.
    """

    recorded = dict(case.assertion_digests)
    current = recorded_digests(case.assertions, registry, root)
    if len(current) != len(case.assertions):
        # The unresolvable names are already reported by name above; a digest
        # comparison against them would be a second report of the same thing.
        return []
    errors: list[str] = []
    for name in sorted(set(recorded) - set(current)):
        errors.append(
            f"{case.case_id}: {DIGESTS_FIELD} carries {name}, which this case does not name — "
            "an entry nothing asserts is an entry nobody reviewed"
        )
    for name in sorted(current):
        if name not in recorded:
            errors.append(
                f"{case.case_id}: {DIGESTS_FIELD} has no entry for {name} — a case whose version "
                "does not cover the implementation it names can mean two things"
            )
        elif recorded[name] != current[name]:
            errors.append(
                f"{case.case_id}: {name} is implemented by {current[name]} and recorded as "
                f"{recorded[name]} — the criteria moved under a version that did not; "
                "re-record with --record once the change has been reviewed"
            )
    return errors


def _record(cases_dir: Path, registry: Mapping[str, Implementation], root: Path) -> int:
    """Write each case's current implementation digests back into its manifest.

    The fixtures are edited in place, one inserted key each, rather than re-rendered
    from the parsed document: re-rendering would reflow every case in the repository
    and bury a one-line change to the criteria inside a whole-file diff. What the
    insertion keeps is everything the file already said, including its own spacing.
    """

    written = 0
    for case in load_case_registry(cases_dir).cases:
        current = recorded_digests(case.assertions, registry, root)
        if len(current) != len(case.assertions):
            print(
                f"{case.case_id}: an assertion does not resolve; nothing recorded", file=sys.stderr
            )
            return 1
        path = _case_path(cases_dir, case.case_id)
        if path is None:
            print(f"{case.case_id}: no case file to record into", file=sys.stderr)
            return 1
        path.write_bytes(_with_recorded_digests(path.read_bytes(), current).encode("utf-8"))
        written += 1
    print(f"Case assertion implementations: recorded {written} case(s)")
    return 0


def _case_path(cases_dir: Path, case_id: str) -> Path | None:
    for path in sorted(cases_dir.glob("*.json")):
        if f'"{case_id}"' in path.read_text(encoding="utf-8"):
            return path
    return None


def _with_recorded_digests(raw: bytes, digests: Mapping[str, str]) -> str:
    """The file's own text with its `assertion_digests` block replaced or inserted.

    The leading whitespace is part of what is matched rather than part of what is
    written. Writing it while matching from the quote leaves the file's own indent in
    place and adds another, so each renew would shift the key two spaces to the right —
    a mistake that is invisible on the first record and wrong on the second.
    """

    text = raw.decode("utf-8")
    # The file's own convention. A block recorded with `\\n` into a CRLF file would be
    # the one mixed-ending region in it, which is a diff nobody asked for.
    newline = "\r\n" if "\r\n" in text else "\n"
    existing = re.compile(
        rf'^(?P<indent>[ \t]*)"{DIGESTS_FIELD}"\s*:\s*\{{[^}}]*\}}', re.MULTILINE | re.DOTALL
    )
    match = existing.search(text)
    inserting = match is None
    if match is None:
        match = re.compile(r'^(?P<indent>[ \t]*)"assertions"\s*:', re.MULTILINE).search(text)
    if match is None:
        raise SystemExit(f"cannot find where to record {DIGESTS_FIELD}")
    indent = match.group("indent")
    rows = f",{newline}".join(f'{indent}  "{name}": "{digests[name]}"' for name in sorted(digests))
    block = f'{indent}"{DIGESTS_FIELD}": {{{newline}{rows}{newline}{indent}}}'
    if inserting:
        return f"{text[: match.start()]}{block},{newline}{text[match.start() :]}"
    return f"{text[: match.start()]}{block}{text[match.end() :]}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-dir", type=Path, default=CASES)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="where the implementations are looked for; the repository by default",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="write each case's current implementation digests into its manifest",
    )
    args = parser.parse_args()
    if args.record:
        return _record(args.cases_dir, IMPLEMENTATIONS, args.root)
    errors = violations(args.cases_dir, registry=IMPLEMENTATIONS, root=args.root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Case assertion implementations: OK ({len(IMPLEMENTATIONS)} registered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
