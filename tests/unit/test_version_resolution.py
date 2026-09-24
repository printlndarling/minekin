"""V05: a resolution may only pick a reviewed tested bundle, or name why it cannot.

The counterexamples below are the card's own list — unknown protocol, one-to-many,
a proxy, forged display text, a missing build for this OS/arch, an entry that is not
tested or was withdrawn — and each one has to end in a stable category instead of a
second attempt. "Never try a login" is checked as behaviour, not just by review.
"""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path
from typing import Any, cast

import pytest

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.version_probe import ProbeObservation, ProbeOutcome
from minekin_core.domain.version_resolution import (
    BundleStatus,
    RegistryViolation,
    ResolutionReason,
    ResolutionStatus,
    load_reviewed_registry,
    registry_revision,
    resolve,
)

REGISTRY_PATH = Path("tests/fixtures/registry/reviewed-tested-bundles.json")
MANIFEST_PATH = Path("tests/fixtures/manifest.sha256")
OS_ARCH = "linux-x86_64"

BRIDGE_1201 = "9e162d8359a886394ddd80db87477d9196ef3d2972e7a4d942df54a2f1e349bc"
PLAN_1201 = "ac40316094dda001c2333bdaea00f886609a58982153b085f276d91d750db8bc"
BRIDGE_1214 = "faeec4a9df83abb9ca0404863e04d20cfd87ac0f3afd5e74b6858e3e15372f55"
PLAN_1214 = "9e0e0ccca9d0a589a38a3f3be40ddbf957f71a51cffe08caf5436153954bfea4"
ID_1201 = "1.20.1-linux-x86_64-offline-java21"
ID_1214 = "1.21.4-linux-x86_64-offline-java21"


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _run_id(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def evidence(
    case_id: str = "CORE-010",
    *,
    bridge: str = BRIDGE_1214,
    plan: str = PLAN_1214,
    result: str = "PASS",
    **overrides: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case_id": case_id,
        "run_id": _run_id(case_id),
        "bundle_digest": _digest(f"bundle:{case_id}"),
        "bridge_digest": bridge,
        "launch_plan_digest": plan,
        "result": result,
        "attempt": 1,
    }
    row.update(overrides)
    return row


def entry(
    bundle_id: str = "test-bundle",
    *,
    version_text: str = "1.99.0",
    protocol: int = 999,
    status: str = BundleStatus.TESTED.value,
    os_arch: str = OS_ARCH,
    bridge: str = BRIDGE_1214,
    plan: str = PLAN_1214,
    evidence_rows: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "bundle_id": bundle_id,
        "status": status,
        "version_text": version_text,
        "protocol": protocol,
        "os_arch": os_arch,
        "java_major": 21,
        "bridge_digest": bridge,
        "launch_plan_digest": plan,
        "recipe_path": "tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json",
        "recipe_digest": _digest("recipe"),
        "auth_mode": "offline",
        "capabilities": ["handshake_accepted_by_core"],
        "gaps": ["USE_TARGET_BLOCK_CHANGE"],
        "evidence": (
            [evidence(bridge=bridge, plan=plan)] if evidence_rows is None else evidence_rows
        ),
    }
    item.update(overrides)
    return item


def registry(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "kind": "reviewed-bundle-registry", "entries": list(entries)}


def observation(
    *,
    outcome: ProbeOutcome = ProbeOutcome.OBSERVED,
    protocol: int | None = 999,
    version_text: str | None = "1.99.0",
    reasons: tuple[str, ...] = (),
    detail: str | None = None,
) -> ProbeObservation:
    return ProbeObservation(
        outcome=outcome,
        profile_id="p0-test-profile",
        profile_revision=_digest("profile"),
        endpoint="192.0.2.10:25565",
        resolution_chain=("saved:192.0.2.10:25565", "as-saved:192.0.2.10:25565"),
        protocol=protocol,
        version_text=version_text,
        refusal_reasons=reasons,
        detail=detail,
    )


def reviewed() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


# --- the two positive resolutions, against the reviewed file -----------------------


def test_the_reviewed_registry_loads_both_versions_as_tested() -> None:
    loaded = load_reviewed_registry(reviewed())
    by_id = {item.bundle_id: item for item in loaded.entries}
    assert set(by_id) == {ID_1201, ID_1214}
    assert by_id[ID_1201].protocol == 763
    assert by_id[ID_1214].protocol == 769
    assert all(item.status is BundleStatus.TESTED for item in loaded.entries)


def test_a_1201_observation_resolves_to_exactly_one_bundle() -> None:
    loaded = load_reviewed_registry(reviewed())
    decision = resolve(
        loaded,
        observation(protocol=763, version_text="1.20.1"),
        os_arch=OS_ARCH,
    )
    assert decision.status is ResolutionStatus.RESOLVED
    assert decision.reasons == ()
    assert decision.bundle is not None
    assert decision.bundle.bundle_id == ID_1201
    assert decision.bundle.bridge_digest == BRIDGE_1201
    assert decision.bundle.launch_plan_digest == PLAN_1201
    assert decision.candidates == (ID_1201,)


def test_a_1214_observation_resolves_to_exactly_one_bundle() -> None:
    loaded = load_reviewed_registry(reviewed())
    decision = resolve(
        loaded,
        observation(protocol=769, version_text="1.21.4"),
        os_arch=OS_ARCH,
    )
    assert decision.status is ResolutionStatus.RESOLVED
    assert decision.bundle is not None
    assert decision.bundle.bundle_id == ID_1214
    assert decision.observed_protocol == 769


def test_a_resolution_carries_the_attribution_a_report_needs() -> None:
    loaded = load_reviewed_registry(reviewed())
    probe = observation(protocol=763, version_text="1.20.1")
    document = resolve(loaded, probe, os_arch=OS_ARCH).as_document()
    assert document["kind"] == "version-resolution-decision"
    assert document["schema_version"] == 1
    assert document["status"] == "RESOLVED"
    assert document["profile_id"] == probe.profile_id
    assert document["profile_revision"] == probe.profile_revision
    assert document["registry_revision"] == loaded.revision
    assert document["pin_applied"] is False
    bundle = document["bundle"]
    assert isinstance(bundle, dict)
    assert bundle["recipe_digest"] == _digest_of_reviewed_recipe_line(
        "tests/fixtures/runtime-input/bundle-candidate-1.20.1.json"
    )


def _digest_of_reviewed_recipe_line(recipe_path: str) -> str:
    for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        expected, _, path = line.partition("  ")
        if path == recipe_path:
            return expected
    raise AssertionError(f"{recipe_path} is not in the reviewed manifest")


def test_resolving_never_opens_a_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a resolution may not reach the network")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    loaded = load_reviewed_registry(reviewed())
    for protocol, version_text in ((763, "1.20.1"), (769, "1.21.4"), (999, "1.5.2")):
        resolve(loaded, observation(protocol=protocol, version_text=version_text), os_arch=OS_ARCH)


# --- the card's counterexamples ---------------------------------------------------


def test_an_unregistered_protocol_is_unsupported_not_guessed() -> None:
    loaded = load_reviewed_registry(registry(entry()))
    decision = resolve(loaded, observation(protocol=1234, version_text="1.5.2"), os_arch=OS_ARCH)
    assert decision.status is ResolutionStatus.UNSUPPORTED
    assert decision.reasons == (ResolutionReason.PROTOCOL_UNREGISTERED,)
    assert decision.bundle is None
    assert decision.candidates == ()


def test_two_tested_bundles_on_one_protocol_need_a_pin_and_no_ranking() -> None:
    first = entry("bundle-a", protocol=763, version_text="1.20.1")
    second = entry("bundle-b", protocol=763, version_text="1.20.1", plan=_digest("other plan"))
    loaded = load_reviewed_registry(registry(first, second))
    decision = resolve(loaded, observation(protocol=763, version_text="1.20.1"), os_arch=OS_ARCH)
    assert decision.status is ResolutionStatus.NEEDS_PIN
    assert decision.reasons == (ResolutionReason.CANDIDATES_AMBIGUOUS,)
    assert decision.bundle is None
    assert decision.candidates == ("bundle-a", "bundle-b")

    reversed_load = load_reviewed_registry(registry(second, first))
    mirrored = resolve(
        reversed_load, observation(protocol=763, version_text="1.20.1"), os_arch=OS_ARCH
    )
    assert mirrored.reasons == decision.reasons
    assert mirrored.candidates == decision.candidates
    assert mirrored.bundle is None


def test_a_multi_version_proxy_waits_for_a_pin_instead_of_choosing() -> None:
    loaded = load_reviewed_registry(registry(entry(protocol=763, version_text="1.20.1")))
    proxy = observation(
        outcome=ProbeOutcome.AMBIGUOUS,
        protocol=763,
        version_text=None,
        reasons=("MULTI_VERSION_PROXY",),
    )
    decision = resolve(loaded, proxy, os_arch=OS_ARCH)
    assert decision.status is ResolutionStatus.NEEDS_PIN
    assert decision.reasons == (ResolutionReason.MULTI_VERSION_PROXY,)
    assert decision.bundle is None


def test_a_pin_settles_a_proxy_listing_it_agrees_with() -> None:
    loaded = load_reviewed_registry(
        registry(entry("one-twenty-one", protocol=763, version_text="1.20.1"))
    )
    proxy = observation(
        outcome=ProbeOutcome.AMBIGUOUS,
        protocol=763,
        version_text=None,
        reasons=("MULTI_VERSION_PROXY",),
    )
    decision = resolve(loaded, proxy, os_arch=OS_ARCH, operator_pin="one-twenty-one")
    assert decision.status is ResolutionStatus.RESOLVED
    assert decision.pin_applied is True
    assert decision.bundle is not None
    assert decision.bundle.bundle_id == "one-twenty-one"


def test_an_ambiguous_target_is_not_a_bundle_question() -> None:
    loaded = load_reviewed_registry(registry(entry(protocol=763, version_text="1.20.1")))
    ambiguous = observation(outcome=ProbeOutcome.AMBIGUOUS, protocol=763, version_text="1.20.1")
    decision = resolve(loaded, ambiguous, os_arch=OS_ARCH)
    assert decision.reasons == (ResolutionReason.TARGET_AMBIGUOUS,)
    assert decision.status is ResolutionStatus.NEEDS_PIN
    # Even a pin cannot say which endpoint the operator meant.
    pinned = resolve(loaded, ambiguous, os_arch=OS_ARCH, operator_pin="test-bundle")
    assert pinned.status is ResolutionStatus.NEEDS_PIN
    assert pinned.reasons == (ResolutionReason.TARGET_AMBIGUOUS,)


def test_a_display_text_that_disagrees_with_the_protocol_is_not_believed() -> None:
    loaded = load_reviewed_registry(reviewed())
    forged = observation(protocol=763, version_text="1.21.4")
    decision = resolve(loaded, forged, os_arch=OS_ARCH)
    assert decision.status is ResolutionStatus.NEEDS_PIN
    assert decision.reasons == (ResolutionReason.DISPLAY_TEXT_CONTRADICTS,)
    assert decision.bundle is None
    assert decision.candidates == (ID_1201,)


def test_a_missing_build_for_the_current_os_arch_is_unsupported() -> None:
    loaded = load_reviewed_registry(reviewed())
    decision = resolve(loaded, observation(protocol=763, version_text="1.20.1"), os_arch="win-10")
    assert decision.status is ResolutionStatus.UNSUPPORTED
    assert decision.reasons == (ResolutionReason.OS_ARCH_UNAVAILABLE,)
    assert decision.candidates == (ID_1201,)
    assert "linux-x86_64" in (decision.detail or "")


def test_an_entry_that_is_only_a_candidate_is_not_launchable() -> None:
    loaded = load_reviewed_registry(
        registry(
            entry(
                "someday",
                protocol=763,
                version_text="1.20.1",
                status=BundleStatus.CANDIDATE.value,
            )
        )
    )
    decision = resolve(loaded, observation(protocol=763, version_text="1.20.1"), os_arch=OS_ARCH)
    assert decision.status is ResolutionStatus.NEEDS_PIN
    assert decision.reasons == (ResolutionReason.ENTRY_NOT_TESTED,)
    assert decision.candidates == ("someday",)


def test_a_quarantined_entry_stays_quarantined() -> None:
    loaded = load_reviewed_registry(
        registry(
            entry(
                "withdrawn",
                protocol=763,
                version_text="1.20.1",
                status=BundleStatus.QUARANTINED.value,
            )
        )
    )
    decision = resolve(loaded, observation(protocol=763, version_text="1.20.1"), os_arch=OS_ARCH)
    assert decision.reasons == (ResolutionReason.ENTRY_QUARANTINED,)
    pinned = resolve(
        loaded,
        observation(protocol=763, version_text="1.20.1"),
        os_arch=OS_ARCH,
        operator_pin="withdrawn",
    )
    assert pinned.status is ResolutionStatus.NEEDS_PIN
    assert pinned.reasons == (ResolutionReason.PIN_NOT_TESTED,)


def test_a_probe_that_learned_nothing_is_a_stale_probe_not_a_miss() -> None:
    loaded = load_reviewed_registry(reviewed())
    for outcome in (
        ProbeOutcome.NO_RESPONSE,
        ProbeOutcome.TIMEOUT,
        ProbeOutcome.MALFORMED,
        ProbeOutcome.OVERSIZE,
    ):
        decision = resolve(loaded, observation(outcome=outcome), os_arch=OS_ARCH)
        assert decision.status is ResolutionStatus.STALE_PROBE, outcome
        assert decision.reasons == (ResolutionReason.PROBE_NOT_OBSERVED,), outcome
        assert decision.bundle is None


def test_an_expired_resolution_asks_for_a_fresh_probe() -> None:
    loaded = load_reviewed_registry(reviewed())
    decision = resolve(
        loaded,
        observation(outcome=ProbeOutcome.CACHE_EXPIRED, protocol=None, version_text=None),
        os_arch=OS_ARCH,
    )
    assert decision.status is ResolutionStatus.STALE_PROBE
    assert decision.reasons == (ResolutionReason.PROBE_STALE,)
    pinned = resolve(
        loaded,
        observation(outcome=ProbeOutcome.CACHE_EXPIRED, protocol=None, version_text=None),
        os_arch=OS_ARCH,
        operator_pin=ID_1201,
    )
    assert pinned.reasons == (ResolutionReason.PROBE_STALE,)
    assert pinned.pin_applied is False


def test_a_bundle_pin_does_not_re_authorize_a_refused_address() -> None:
    loaded = load_reviewed_registry(reviewed())
    refused = observation(
        outcome=ProbeOutcome.POLICY_REFUSAL,
        protocol=None,
        version_text=None,
        reasons=("OUTSIDE_ALLOWLIST",),
    )
    decision = resolve(loaded, refused, os_arch=OS_ARCH, operator_pin=ID_1201)
    assert decision.status is ResolutionStatus.NEEDS_PIN
    assert decision.reasons == (ResolutionReason.PROBE_REFUSED_BY_POLICY,)
    assert decision.bundle is None


def test_an_observation_without_a_protocol_cannot_index_anything() -> None:
    loaded = load_reviewed_registry(reviewed())
    decision = resolve(loaded, observation(protocol=None, version_text="1.20.1"), os_arch=OS_ARCH)
    assert decision.status is ResolutionStatus.STALE_PROBE
    assert decision.reasons == (ResolutionReason.PROTOCOL_UNOBSERVED,)


# --- the pin rules ----------------------------------------------------------------


def test_a_pin_must_name_a_bundle_in_this_registry() -> None:
    loaded = load_reviewed_registry(registry(entry(protocol=763, version_text="1.20.1")))
    decision = resolve(
        loaded,
        observation(protocol=763, version_text="1.20.1"),
        os_arch=OS_ARCH,
        operator_pin="an-old-pin-from-an-older-file",
    )
    assert decision.reasons == (ResolutionReason.PIN_UNKNOWN,)
    assert decision.status is ResolutionStatus.NEEDS_PIN


def test_a_pin_cannot_override_what_the_target_was_observed_as() -> None:
    loaded = load_reviewed_registry(reviewed())
    decision = resolve(
        loaded,
        observation(protocol=769, version_text="1.21.4"),
        os_arch=OS_ARCH,
        operator_pin=ID_1201,
    )
    assert decision.status is ResolutionStatus.NEEDS_PIN
    assert decision.reasons == (ResolutionReason.PIN_CONTRADICTS_TARGET,)
    assert decision.bundle is None
    text_conflict = resolve(
        loaded,
        observation(protocol=763, version_text="1.20.1 (Paper)"),
        os_arch=OS_ARCH,
        operator_pin=ID_1201,
    )
    assert text_conflict.reasons == (ResolutionReason.PIN_CONTRADICTS_TARGET,)


def test_a_pin_to_a_bundle_without_a_build_for_this_os_arch_is_unsupported() -> None:
    loaded = load_reviewed_registry(reviewed())
    decision = resolve(
        loaded,
        observation(protocol=763, version_text="1.20.1"),
        os_arch="win-10",
        operator_pin=ID_1201,
    )
    assert decision.status is ResolutionStatus.UNSUPPORTED
    assert decision.reasons == (ResolutionReason.PIN_ARCH_UNAVAILABLE,)


def test_a_matching_pin_resolves_even_when_several_bundles_share_a_protocol() -> None:
    first = entry("bundle-a", protocol=763, version_text="1.20.1")
    second = entry(
        "bundle-b",
        protocol=763,
        version_text="1.20.1",
        plan=_digest("other plan"),
    )
    loaded = load_reviewed_registry(registry(first, second))
    decision = resolve(
        loaded,
        observation(protocol=763, version_text="1.20.1"),
        os_arch=OS_ARCH,
        operator_pin="bundle-b",
    )
    assert decision.status is ResolutionStatus.RESOLVED
    assert decision.bundle is not None and decision.bundle.bundle_id == "bundle-b"


# --- the loader refuses a registry it cannot fully trust --------------------------


def violations_for(item: dict[str, Any]) -> set[str]:
    with pytest.raises(MinekinError) as raised:
        load_reviewed_registry(item)
    violations = cast("list[str]", raised.value.context["violations"])
    return set(violations)


def test_a_registry_that_moved_one_citation_onto_another_build_is_refused() -> None:
    item = registry(
        entry(
            protocol=763,
            version_text="1.20.1",
            bridge=BRIDGE_1201,
            plan=PLAN_1201,
            evidence_rows=[evidence("V1201-010", bridge=BRIDGE_1214, plan=PLAN_1214)],
        )
    )
    assert violations_for(item) == {
        RegistryViolation.EVIDENCE_BUILD_MISMATCH.value,
        RegistryViolation.TESTED_WITHOUT_EVIDENCE.value,
    }


def test_a_tested_entry_with_no_citation_is_refused() -> None:
    item = registry(entry(evidence_rows=[]))
    assert violations_for(item) == {RegistryViolation.TESTED_WITHOUT_EVIDENCE.value}


def test_a_failing_run_is_not_evidence_of_a_tested_bundle() -> None:
    item = registry(entry(evidence_rows=[evidence(result="FAIL")]))
    assert violations_for(item) == {
        RegistryViolation.UNEVIDENCED_RESULT.value,
        RegistryViolation.TESTED_WITHOUT_EVIDENCE.value,
    }


def test_a_duplicate_bundle_id_is_refused() -> None:
    item = registry(entry("same"), entry("same"))
    assert violations_for(item) == {RegistryViolation.DUPLICATE_BUNDLE_ID.value}


def test_an_unknown_status_word_is_refused() -> None:
    item = registry(entry(status="probably-fine"))
    assert RegistryViolation.UNKNOWN_STATUS.value in violations_for(item)


def test_a_registry_entry_cannot_opt_into_online_auth() -> None:
    item = registry(entry(auth_mode="online"))
    assert violations_for(item) == {RegistryViolation.UNSUPPORTED_AUTH_MODE.value}


@pytest.mark.parametrize(
    "recipe_path",
    [
        "/etc/passwd",
        "../outside.json",
        "tests/../fixtures/x.json",
        "C:/Users/darling/recipe.json",
        "tests\\fixtures\\x.json",
        "tests/fixtures/x.json/",
    ],
)
def test_a_recipe_path_has_to_stay_inside_the_repository(recipe_path: str) -> None:
    item = registry(entry(recipe_path=recipe_path))
    assert violations_for(item) == {RegistryViolation.UNSAFE_RECIPE_PATH.value}


def test_a_digest_that_is_not_lowercase_hex_is_refused() -> None:
    item = registry(entry(bridge_digest="ZZ" + "0" * 62))
    assert violations_for(item) == {RegistryViolation.INVALID_DIGEST.value}


def test_a_registry_that_is_only_half_readable_is_refused() -> None:
    item = registry(entry(), {"bundle_id": "sparse"})
    found = violations_for(item)
    assert RegistryViolation.MALFORMED_DOCUMENT.value in found


def test_a_rejected_registry_is_an_operator_action_not_a_retry() -> None:
    with pytest.raises(MinekinError) as raised:
        load_reviewed_registry({"kind": "wrong", "schema_version": 1, "entries": []})
    error = raised.value
    assert error.category is ErrorCategory.CONFIG
    assert error.retryability is Retryability.OPERATOR_ACTION
    assert error.component == "domain.version_resolution"


# --- the reviewed file's own claims -----------------------------------------------


def test_every_reviewed_citation_names_the_build_it_supports() -> None:
    loaded = load_reviewed_registry(reviewed())
    assert loaded.entries
    for item in loaded.entries:
        assert item.evidence, item.bundle_id
        for reference in item.evidence:
            assert reference.result == "PASS"
            assert reference.bridge_digest == item.bridge_digest
            assert reference.launch_plan_digest == item.launch_plan_digest
            assert reference.attempt >= 1
            case_path = Path("tests/fixtures/cases") / f"{reference.case_id.lower()}.json"
            assert case_path.is_file(), reference.case_id
            case = json.loads(case_path.read_text(encoding="utf-8"))
            assert case["case_id"] == reference.case_id


def test_declared_capabilities_are_exactly_the_cited_assertions() -> None:
    loaded = load_reviewed_registry(reviewed())
    for item in loaded.entries:
        proven = {
            token
            for reference in item.evidence
            for token in json.loads(
                (Path("tests/fixtures/cases") / f"{reference.case_id.lower()}.json").read_text(
                    encoding="utf-8"
                )
            )["assertions"]
        }
        assert set(item.capabilities) == proven, item.bundle_id


def test_gaps_name_holes_the_cited_runs_did_not_close() -> None:
    loaded = load_reviewed_registry(reviewed())
    for item in loaded.entries:
        assert set(item.gaps).isdisjoint(item.capabilities), item.bundle_id
        assert all(gap == gap.upper() for gap in item.gaps)


def test_the_registry_is_not_derived_from_a_recipes_own_status_word() -> None:
    # The recipes still call themselves `candidate` and `recipe`. If a future edit
    # ever moves one to `tested`, this fixture's digests change and the citations
    # stop matching — which is the point of keeping them separate.
    loaded = load_reviewed_registry(reviewed())
    for item in loaded.entries:
        recipe = json.loads(Path(item.recipe_path).read_text(encoding="utf-8"))
        assert recipe["status"] in {"candidate", "recipe"}
        assert recipe["minecraft"]["version"] == item.version_text
        assert recipe["runtime"]["os_arch"] == item.os_arch


def test_the_reviewed_registry_records_no_target_address() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    keys = ('"host"', '"port"', '"srv"', '"address"', '"hostname"')
    for forbidden in ("127.0.0.1", "localhost", ".tmp/local-test-server", *keys):
        assert forbidden not in text, forbidden


def test_changing_registry_bytes_moves_the_decision_version() -> None:
    document = reviewed()
    loaded = load_reviewed_registry(document)
    resolved = resolve(loaded, observation(protocol=763, version_text="1.20.1"), os_arch=OS_ARCH)
    assert resolved.registry_revision == registry_revision(document)

    edited = json.loads(json.dumps(document))
    edited["entries"][0]["protocol"] = 764
    edited_load = load_reviewed_registry(edited)
    assert edited_load.revision != loaded.revision
    after = resolve(edited_load, observation(protocol=763, version_text="1.20.1"), os_arch=OS_ARCH)
    assert after.registry_revision == edited_load.revision
    assert after.status is ResolutionStatus.UNSUPPORTED

    same_load = load_reviewed_registry(reviewed())
    assert same_load.revision == loaded.revision


def test_the_protocol_ids_are_the_measured_ones() -> None:
    loaded = load_reviewed_registry(reviewed())
    protocols = {item.version_text: item.protocol for item in loaded.entries}
    assert protocols == {"1.20.1": 763, "1.21.4": 769}
