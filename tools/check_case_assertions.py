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
from typing import Final

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

        if self.kind not in IMPLEMENTATION_KINDS:
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

#: The kinds an implementation may have, and which judge performs each.
#:
#: `tool` and `pytest` are performed by `tools/run_repo_case.py`: it runs a tool's
#: file with no arguments, or one test node. `runtime` is performed by the asserter
#: above, against material from a run this repository has to have made, so that
#: runner has nothing to run — and saying so is this kind's whole purpose. Before it
#: existed, a runtime assertion was registered as a `tool`, and the runner invoked
#: the asserter with no `--case` and no `--run`: it died on an argparse usage error
#: and four assertions of a case that had not failed were reported as failures.
IMPLEMENTATION_KINDS: Final[frozenset[str]] = frozenset({"tool", "pytest", "runtime"})


def _runtime(name: str) -> Implementation:
    return Implementation("runtime", RUNTIME_ASSERTER, symbol=name)


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
    # CORE-001: the fixed artifact/bundle manifest, and what tampering with it does.
    # Every one of the five is already performed by a check this repository had —
    # the recipe validator, the content-addressed bundle store, and the compiled
    # Bridge artifact gate — so the case names them rather than growing a second
    # implementation of any of the three. That is the whole of what a *repository*
    # case can be: the reviewed manifest is a file, and the negative mutations are
    # tests, because a mutation is something a check is driven into rather than
    # something a run of the product produces.
    "the_fixed_bundle_recipe_is_the_reviewed_one": Implementation(
        "pytest",
        "tests/unit/test_bundle_recipe.py::test_fixed_mod_recipe_validates_source_identity",
    ),
    "tampering_with_any_recipe_digest_is_rejected": Implementation(
        "pytest",
        "tests/unit/test_bundle_recipe.py::test_any_tampered_recipe_digest_is_rejected",
    ),
    "inserting_an_unknown_mod_is_rejected": Implementation(
        "pytest",
        "tests/unit/test_bundle_recipe.py::test_unknown_mod_is_rejected",
    ),
    "tampering_with_a_published_bundle_is_rejected": Implementation(
        "pytest",
        "tests/unit/test_artifact_store.py"
        "::test_bundle_verification_detects_tampering_and_undeclared_files",
    ),
    "a_bridge_artifact_under_an_unreviewed_dependency_digest_is_rejected": Implementation(
        "pytest",
        "tests/contract/test_bridge_artifact_gate.py"
        "::test_a_reviewed_dependency_under_another_digest_is_refused",
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
    # OFFLINE-090: the two halves of "logs, crashes and Dashboard show no authentication
    # body". Both are readings of sealed carriers, so both are the asserter's; the
    # Dashboard half names the carrier it cannot read rather than reporting a zero over
    # the bytes that happen to be there — see the reason recorded on the fixture.
    "auth_field_bodies_are_not_exposed_in_bundle_carriers": _runtime(
        "auth_field_bodies_are_not_exposed_in_bundle_carriers"
    ),
    "auth_field_bodies_are_not_exposed_on_the_dashboard": _runtime(
        "auth_field_bodies_are_not_exposed_on_the_dashboard"
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
    "the_bridge_released_the_input_when_the_session_was_stopped": _runtime(
        "the_bridge_released_the_input_when_the_session_was_stopped"
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
    # ADMIT-040: the four facts the admission contract names for an offline identity
    # that met a server demanding session verification. Each is its own runtime
    # assertion rather than a wider version of the whitelist pair above, because that
    # one compares against the category the whitelist scenario produced.
    "the_server_this_run_met_required_online_authentication": _runtime(
        "the_server_this_run_met_required_online_authentication"
    ),
    "the_offline_auth_policy_was_frozen_before_the_client_started": _runtime(
        "the_offline_auth_policy_was_frozen_before_the_client_started"
    ),
    "the_frozen_policy_names_the_profile_this_run_dialled": _runtime(
        "the_frozen_policy_names_the_profile_this_run_dialled"
    ),
    "the_auth_mode_mismatch_was_classified_in_the_ledger": _runtime(
        "the_auth_mode_mismatch_was_classified_in_the_ledger"
    ),
    "the_refusal_left_the_run_on_one_policy_and_one_process": _runtime(
        "the_refusal_left_the_run_on_one_policy_and_one_process"
    ),
    # OFFLINE-010/020/030: the five facts one real launch of one identity column has to
    # carry. The first four are about *which* column — the argv the harness handed Core,
    # Core's own record of what it compared, the comparison between them, and the account
    # type the client reported — so they belong to `OFFLINE-010`, `OFFLINE-020` and the
    # two children of `OFFLINE-030`, each of which names one candidate in its own id. The
    # fifth is the server's agreement, which holds whichever column ran and is what the
    # parent keeps.
    "this_run_started_the_identity_candidate_the_case_names": _runtime(
        "this_run_started_the_identity_candidate_the_case_names"
    ),
    "core_recorded_the_identity_it_compared": _runtime("core_recorded_the_identity_it_compared"),
    "the_reported_session_is_the_identity_this_run_launched_with": _runtime(
        "the_reported_session_is_the_identity_this_run_launched_with"
    ),
    "the_account_type_was_recorded_as_an_observation": _runtime(
        "the_account_type_was_recorded_as_an_observation"
    ),
    "the_offline_identity_joined_and_the_server_agrees": _runtime(
        "the_offline_identity_joined_and_the_server_agrees"
    ),
    # ADMIT-060: the four facts the contract names for a server that demands a pack
    # the profile refuses. The last of the four is where the case is decided: the
    # first three say the two sides disagreed, and only the client's own directory
    # says the disagreement ended with nothing downloaded.
    "the_server_this_run_required_a_resource_pack": _runtime(
        "the_server_this_run_required_a_resource_pack"
    ),
    "the_sealed_profile_refused_the_resource_pack": _runtime(
        "the_sealed_profile_refused_the_resource_pack"
    ),
    "the_resource_pack_policy_that_went_on_the_wire_is_the_frozen_one": _runtime(
        "the_resource_pack_policy_that_went_on_the_wire_is_the_frozen_one"
    ),
    "the_client_never_downloaded_the_pack": _runtime("the_client_never_downloaded_the_pack"),
    # ADMIT-070: the five facts a sealed first-snapshot refusal run has to carry. The
    # case used to name the five domain tests below, which is a different claim: those
    # check the filter in a test fixture, and a sealed bundle cannot be judged by them
    # because a run performs no pytest. Both sets stand — the domain tests keep
    # exercising the filter's semantics, and these read what one real refusal left.
    "this_run_joined_a_world_it_was_never_told_it_could_play": _runtime(
        "this_run_joined_a_world_it_was_never_told_it_could_play"
    ),
    "the_first_snapshot_was_refused_by_the_reason_the_case_names": _runtime(
        "the_first_snapshot_was_refused_by_the_reason_the_case_names"
    ),
    "a_refused_first_snapshot_became_no_lease_and_no_playable": _runtime(
        "a_refused_first_snapshot_became_no_lease_and_no_playable"
    ),
    "the_refused_generation_was_closed_and_never_reopened": _runtime(
        "the_refused_generation_was_closed_and_never_reopened"
    ),
    "the_refusal_was_asked_of_this_run": _runtime("the_refusal_was_asked_of_this_run"),
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
    # HOSTCTL-060: the control boundary's four injection surfaces, and the build
    # clause that makes them a gate rather than a report. Three of the four are the
    # artifact gate's own negative tests; the mixin one is there because a mixin is
    # the only class here written to run inside someone else's bytecode, so it is a
    # place to state separately rather than leave to the general rule. The fifth is
    # the scaffold gate, which pins that `check` depends on the artifact gate — the
    # sentence "the build must fail" is about that attachment and about nothing else.
    "a_server_reference_in_bridge_source_is_refused": Implementation(
        "pytest",
        "tests/contract/test_bridge_host_boundary.py"
        "::test_a_client_file_that_calls_get_server_is_refused",
    ),
    "a_server_type_in_a_compiled_class_is_refused": Implementation(
        "pytest",
        "tests/contract/test_bridge_artifact_gate.py"
        "::test_a_server_type_outside_the_adapter_is_refused",
    ),
    "a_server_reference_in_a_mixin_is_refused": Implementation(
        "pytest",
        "tests/contract/test_bridge_artifact_gate.py"
        "::test_a_server_reference_in_a_mixin_is_refused",
    ),
    "an_access_widener_naming_server_state_is_refused": Implementation(
        "pytest",
        "tests/contract/test_bridge_artifact_gate.py"
        "::test_an_access_widener_naming_server_state_is_refused",
    ),
    "the_build_runs_the_artifact_gate_so_a_violation_fails_it": Implementation(
        "tool", "tools/check_bridge_scaffold.py"
    ),
    # HOSTCTL-070: the third gate — only player-equivalent information reaches the
    # Kin's own mind. Two of the four are about the class table and one is about the
    # bytes it refuses; the fourth is the only one that goes through the real IPC
    # loopback, because "the gate exists" and "the runtime asks it" are different
    # claims and the case is about the second.
    "a_management_dto_is_refused_however_observation_shaped_its_bytes_are": Implementation(
        "pytest",
        "tests/unit/test_information_class.py"
        "::test_a_management_dto_is_refused_however_observation_shaped_its_bytes_are",
    ),
    "an_unclassified_server_side_dto_is_refused_rather_than_defaulted": Implementation(
        "pytest",
        "tests/unit/test_information_class.py"
        "::test_an_unclassified_server_side_dto_is_refused_rather_than_defaulted",
    ),
    "every_inbound_dto_carries_exactly_one_class": Implementation(
        "pytest",
        "tests/unit/test_information_class.py::test_every_inbound_dto_carries_exactly_one_class",
    ),
    "a_management_report_does_not_become_what_the_kin_knows": Implementation(
        "pytest",
        "tests/contract/test_session_runtime.py"
        "::test_a_management_report_does_not_become_what_the_kin_knows",
    ),
    # HOST-020: the save-path policy, one assertion per clause the contract names —
    # a symlinked save path, `..`, another Kin's path, and a path that leaves the
    # data root — plus the layout those clauses are about. The subject is a pure
    # path rule over a real directory tree, so none of them needs a client; what the
    # case cannot claim yet is the mounting strategy, which the contract leaves
    # unfrozen.
    "the_layout_is_the_one_the_contract_fixes": Implementation(
        "pytest",
        "tests/unit/test_hosted_store.py::test_the_layout_is_the_one_the_contract_fixes",
    ),
    "an_identifier_that_is_not_a_plain_directory_name_is_refused": Implementation(
        "pytest",
        "tests/unit/test_hosted_store.py"
        "::test_an_identifier_that_is_not_a_plain_directory_name_is_refused",
    ),
    "a_symlinked_save_directory_is_refused": Implementation(
        "pytest",
        "tests/unit/test_hosted_store.py::test_a_symlinked_save_directory_is_refused",
    ),
    "a_symlinked_ancestor_is_refused_however_canonical_the_result_is": Implementation(
        "pytest",
        "tests/unit/test_hosted_store.py"
        "::test_a_symlinked_ancestor_is_refused_however_canonical_the_result_is",
    ),
    "another_kins_area_is_refused": Implementation(
        "pytest",
        "tests/unit/test_hosted_store.py::test_another_kins_area_is_refused",
    ),
    "a_save_path_outside_the_data_root_is_refused": Implementation(
        "pytest",
        "tests/unit/test_hosted_store.py::test_a_save_path_outside_the_data_root_is_refused",
    ),
    # ADMIT-070 and ADMIT-080: the first snapshot's gate, and what a stale generation
    # may not do. Both were already closed in this repository's own notes — ADMIT-080's
    # entry names the five connection tests and the session-side one — and neither had
    # a case claiming them, which is the same gap W30 had.
    "test_a_refused_snapshot_is_never_the_basis_for_a_lease": Implementation(
        "pytest",
        "tests/contract/test_session_runtime.py::test_a_refused_snapshot_is_never_the_basis_for_a_lease",
    ),
    "test_join_and_authoritative_snapshot_are_both_required_for_playable": Implementation(
        "pytest",
        "tests/unit/test_connection_generation.py::test_join_and_authoritative_snapshot_are_both_required_for_playable",
    ),
    "test_failure_is_terminal_until_generation_is_explicitly_closed": Implementation(
        "pytest",
        "tests/unit/test_connection_generation.py::test_failure_is_terminal_until_generation_is_explicitly_closed",
    ),
    "test_a_non_authoritative_snapshot_is_not_admitted": Implementation(
        "pytest",
        "tests/unit/test_perception.py::test_a_non_authoritative_snapshot_is_not_admitted",
    ),
    "test_a_snapshot_for_another_identity_is_not_admitted": Implementation(
        "pytest",
        "tests/unit/test_perception.py::test_a_snapshot_for_another_identity_is_not_admitted",
    ),
    "test_stale_close_cannot_cancel_the_current_attempt": Implementation(
        "pytest",
        "tests/unit/test_connection_generation.py::test_stale_close_cannot_cancel_the_current_attempt",
    ),
    "test_reconnect_allocates_a_new_generation_and_old_callback_is_diagnostic_only": Implementation(
        "pytest",
        "tests/unit/test_connection_generation.py::test_reconnect_allocates_a_new_generation_and_old_callback_is_diagnostic_only",
    ),
    "test_a_disconnect_is_closed_explicitly_before_the_next_generation": Implementation(
        "pytest",
        "tests/unit/test_connection_generation.py::test_a_disconnect_is_closed_explicitly_before_the_next_generation",
    ),
    "test_close_invalidates_before_late_callbacks_arrive": Implementation(
        "pytest",
        "tests/unit/test_connection_generation.py::test_close_invalidates_before_late_callbacks_arrive",
    ),
    "test_a_late_report_cannot_turn_a_disconnect_into_a_failure": Implementation(
        "pytest",
        "tests/unit/test_connection_generation.py::test_a_late_report_cannot_turn_a_disconnect_into_a_failure",
    ),
    "test_a_report_that_speaks_for_another_generation_moves_nothing": Implementation(
        "pytest",
        "tests/unit/test_session_state.py::test_a_report_that_speaks_for_another_generation_moves_nothing",
    ),
    # HOST-050 and HOST-080: the recovery policy's no-replay half, and the world
    # switch's at-most-one-current half. Both criteria are the contract's own and
    # both are already implemented; what they lacked was a case claiming them.
    "test_only_the_idempotent_effects_are_replayable": Implementation(
        "pytest",
        "tests/unit/test_recovery.py::test_only_the_idempotent_effects_are_replayable",
    ),
    "test_an_effect_that_may_never_be_replayed_is_not_retried_later_either": Implementation(
        "pytest",
        "tests/unit/test_recovery.py::test_an_effect_that_may_never_be_replayed_is_not_retried_later_either",
    ),
    "test_the_fixtures_three_expectations_are_what_the_policy_does": Implementation(
        "pytest",
        "tests/unit/test_recovery.py::test_the_fixtures_three_expectations_are_what_the_policy_does",
    ),
    "test_switching_worlds_keeps_exactly_one_current_at_a_time": Implementation(
        "pytest",
        "tests/unit/test_world_activation.py::test_switching_worlds_keeps_exactly_one_current_at_a_time",
    ),
    "test_a_second_world_cannot_become_current_while_one_is": Implementation(
        "pytest",
        "tests/unit/test_world_activation.py::test_a_second_world_cannot_become_current_while_one_is",
    ),
    "test_a_switch_that_does_not_finish_leaves_nothing_current": Implementation(
        "pytest",
        "tests/unit/test_world_activation.py::test_a_switch_that_does_not_finish_leaves_nothing_current",
    ),
    "test_a_record_with_two_current_worlds_is_refused_rather_than_picked_between": Implementation(
        "pytest",
        "tests/unit/test_world_activation.py::test_a_record_with_two_current_worlds_is_refused_rather_than_picked_between",
    ),
    # W30's first three cases: the offline session's argv chain, the identity encoding
    # it has to match, and the shape of an empty credential. All three are pure
    # functions of the frozen candidate matrix, so every assertion is a test — and the
    # run-material halves of OFFLINE-010/020/030/060… are what the family still waits
    # for, which is why each case below is `mandatory: false`.
    "test_frozen_candidates_use_the_public_token_and_explicit_empty_options": Implementation(
        "pytest",
        "tests/unit/test_offline_session.py"
        "::test_frozen_candidates_use_the_public_token_and_explicit_empty_options",
    ),
    "test_offline_argv_keeps_the_empty_client_credentials_as_their_own_elements": Implementation(
        "pytest",
        "tests/unit/test_offline_session.py"
        "::test_offline_argv_keeps_the_empty_client_credentials_as_their_own_elements",
    ),
    "test_no_argument_survives_as_a_literal_placeholder": Implementation(
        "pytest",
        "tests/unit/test_offline_session.py::test_no_argument_survives_as_a_literal_placeholder",
    ),
    "test_every_frozen_candidate_resolves_the_full_reviewed_template": Implementation(
        "pytest",
        "tests/unit/test_offline_session.py"
        "::test_every_frozen_candidate_resolves_the_full_reviewed_template",
    ),
    "test_an_unknown_placeholder_is_rejected_rather_than_emptied": Implementation(
        "pytest",
        "tests/unit/test_offline_session.py::test_an_unknown_placeholder_is_rejected_rather_than_emptied",
    ),
    "test_canonical_uuid_encoding_is_available_for_the_off_c_comparison": Implementation(
        "pytest",
        "tests/unit/test_offline_session.py"
        "::test_canonical_uuid_encoding_is_available_for_the_off_c_comparison",
    ),
    "test_the_id128_argv_and_a_canonical_report_are_the_same_identity": Implementation(
        "pytest",
        "tests/unit/test_session_material.py"
        "::test_the_id128_argv_and_a_canonical_report_are_the_same_identity",
    ),
    "test_an_uppercase_report_uuid_is_still_the_same_identity": Implementation(
        "pytest",
        "tests/unit/test_session_material.py"
        "::test_an_uppercase_report_uuid_is_still_the_same_identity",
    ),
    "test_an_empty_value_must_stay_attached_to_an_option_flag": Implementation(
        "pytest",
        "tests/unit/test_offline_session.py::test_an_empty_value_must_stay_attached_to_an_option_flag",
    ),
    "test_an_empty_environment_value_is_refused_before_it_reaches_argv": Implementation(
        "pytest",
        "tests/unit/test_offline_session.py"
        "::test_an_empty_environment_value_is_refused_before_it_reaches_argv",
    ),
    "test_candidate_document_reports_presence_without_values": Implementation(
        "pytest",
        "tests/unit/test_offline_session.py::test_candidate_document_reports_presence_without_values",
    ),
    # HOST-010: the two locks one hosted world needs, and the race they settle. All
    # five are the rule about what an observation means; the real half — two actual
    # processes racing for one world — needs a run, so `mandatory` stays false.
    "a_second_run_is_refused_while_the_first_is_alive": Implementation(
        "pytest",
        "tests/unit/test_world_locking.py::test_a_second_run_is_refused_while_the_first_is_alive",
    ),
    "a_save_open_in_another_process_is_refused": Implementation(
        "pytest",
        "tests/unit/test_world_locking.py::test_a_save_open_in_another_process_is_refused",
    ),
    "a_lease_whose_owner_is_gone_is_reclaimed_rather_than_refused": Implementation(
        "pytest",
        "tests/unit/test_world_locking.py"
        "::test_a_lease_whose_owner_is_gone_is_reclaimed_rather_than_refused",
    ),
    "a_lease_whose_owner_could_not_be_checked_is_not_reclaimed": Implementation(
        "pytest",
        "tests/unit/test_world_locking.py"
        "::test_a_lease_whose_owner_could_not_be_checked_is_not_reclaimed",
    ),
    "a_lock_file_that_cannot_be_read_is_not_a_free_lock": Implementation(
        "pytest",
        "tests/unit/test_world_locking.py::test_a_lock_file_that_cannot_be_read_is_not_a_free_lock",
    ),
    # HOST-060 and HOST-070: the two clauses of the storage contract's backup
    # section that are about paths — a verified backup is not replaced, and a
    # restore writes a new copy rather than into the tree it is restoring from.
    # Both cases are half-covered on purpose: their other clauses (a disk that is
    # full, a restore that is actually entered and spot-checked) need a real client,
    # so `mandatory` stays false and the reason is on the contract's own entries.
    "a_backup_is_built_beside_its_target_and_published_by_a_rename": Implementation(
        "pytest",
        "tests/unit/test_hosted_backup.py"
        "::test_a_backup_is_built_beside_its_target_and_published_by_a_rename",
    ),
    "a_verified_backup_is_not_replaced": Implementation(
        "pytest",
        "tests/unit/test_hosted_backup.py::test_a_verified_backup_is_not_replaced",
    ),
    "an_unverified_leftover_may_be_replaced": Implementation(
        "pytest",
        "tests/unit/test_hosted_backup.py::test_an_unverified_leftover_may_be_replaced",
    ),
    "a_restore_into_a_new_world_is_admitted": Implementation(
        "pytest",
        "tests/unit/test_hosted_backup.py::test_a_restore_into_a_new_world_is_admitted",
    ),
    "restoring_inside_the_source_is_refused": Implementation(
        "pytest",
        "tests/unit/test_hosted_backup.py::test_restoring_inside_the_source_is_refused",
    ),
    "the_most_specific_refusal_is_the_one_reported": Implementation(
        "pytest",
        "tests/unit/test_hosted_backup.py::test_the_most_specific_refusal_is_the_one_reported",
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
    # HOSTCOMMIT-090: hosted A, remote B, hosted A, with at most one world current at
    # every step. The subject is the gate's own record, so the assertion is a test.
    "switching_worlds_keeps_exactly_one_current_at_a_time": Implementation(
        "pytest",
        "tests/unit/test_world_activation.py::test_switching_worlds_keeps_exactly_one_current_at_a_time",
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
