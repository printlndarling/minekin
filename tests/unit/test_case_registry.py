from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from minekin_core.adapters.evidence.bundle import unseal_bundle, verify_bundle, write_bundle
from minekin_core.adapters.evidence.promotion import (
    evaluate_case_promotion,
    load_case_manifest,
    load_case_registry,
)
from minekin_core.domain.cases import (
    REQUIRED_CASES,
    REQUIRED_GATES,
    WORK_PACKAGES,
    CaseEvidence,
    CaseManifest,
    CaseRegistry,
    CaseViolation,
    PromotionBlock,
    ReJudge,
    RequiredCase,
    RequiredCaseViolation,
    ValidationClass,
    evaluate_promotion,
    parse_case_manifest,
    required_case_violations,
    required_for_gates,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.evidence import Assertions, EvidenceManifest, EvidenceResult

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"
W00_CASE = CASES / "w00-contract-001.json"


class _Drop:
    """Sentinel so a test can remove a required field."""


_DROP = _Drop()


def document(**overrides: object) -> dict[str, object]:
    baseline: dict[str, object] = {
        "schema_version": 1,
        "case_id": "W50-SNAPSHOT-001",
        "work_package": "W50",
        "mandatory": True,
        "inputs": ["tests/fixtures/runtime-input/*.json"],
        "assertions": ["first_snapshot_is_authoritative"],
    }
    merged = dict(baseline)
    for key, value in overrides.items():
        if value is _DROP:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def case(**overrides: object) -> CaseManifest:
    parsed, violations = parse_case_manifest(document(**overrides))
    assert violations == (), violations
    assert parsed is not None
    return parsed


def test_the_reviewed_w00_case_loads() -> None:
    loaded = load_case_manifest(W00_CASE)

    assert loaded.case_id == "W00-CONTRACT-001"
    assert loaded.work_package == "W00"
    assert loaded.mandatory
    assert loaded.oracle_inputs == ("tests/oracle/canary.json",)
    assert loaded.reads_oracle
    assert "fixture_digests_match_manifest" in loaded.assertions


def test_a_case_digest_names_its_own_definition() -> None:
    first = case()
    second = case()

    assert first.digest == second.digest
    assert case(assertions=["something_else"]).digest != first.digest
    assert case(input_digests={"fixture.bin": "a" * 64}).digest != first.digest


def test_reviewed_input_digests_are_part_of_the_case_definition() -> None:
    parsed = case(input_digests={"fixture.bin": "a" * 64})

    assert parsed.input_digests == (("fixture.bin", "a" * 64),)
    assert parsed.as_document()["input_digests"] == {"fixture.bin": "a" * 64}


@pytest.mark.parametrize(
    "input_digests",
    [
        [],
        {"": "a" * 64},
        {"fixture.bin": "not-a-digest"},
        {"fixture.bin": 1},
    ],
)
def test_malformed_reviewed_input_digests_are_refused(input_digests: object) -> None:
    parsed, violations = parse_case_manifest(document(input_digests=input_digests))

    assert parsed is None
    assert CaseViolation.INVALID_INPUT_DIGESTS in violations


def test_recorded_assertion_digests_are_part_of_the_case_definition() -> None:
    """The whole point of recording them: the case version has to cover the criteria.

    A version that moved only when the list of assertion *names* changed is a version
    that can name two different checks, which is how a bundle sealed under one gets
    promoted as evidence for the other.
    """

    recorded = {"stayed_observe_only": "b" * 64}
    parsed = case(assertion_digests=recorded)

    assert parsed.assertion_digests == (("stayed_observe_only", "b" * 64),)
    assert parsed.as_document()["assertion_digests"] == recorded
    assert parsed.digest != case().digest
    assert parsed.digest != case(assertion_digests={"stayed_observe_only": "c" * 64}).digest


@pytest.mark.parametrize(
    "assertion_digests",
    [
        [],
        {"": "a" * 64},
        {"stayed_observe_only": "not-a-digest"},
        {"stayed_observe_only": 1},
    ],
)
def test_malformed_recorded_assertion_digests_are_refused(assertion_digests: object) -> None:
    parsed, violations = parse_case_manifest(document(assertion_digests=assertion_digests))

    assert parsed is None
    assert CaseViolation.INVALID_ASSERTION_DIGESTS in violations


def test_a_case_without_recorded_assertion_digests_still_parses() -> None:
    """Absence is the gate's business, not the parser's.

    A case that recorded nothing is refused by `check_case_assertions`, which can say
    *what* is missing; refusing it here as a malformed manifest would report a case
    that has simply not been recorded yet as one that is wrong.
    """

    parsed, violations = parse_case_manifest(document())

    assert violations == ()
    assert parsed is not None
    assert parsed.assertion_digests == ()


def test_independent_case_violations_are_reported_together() -> None:
    parsed, violations = parse_case_manifest(document(input_digests=[], assertions=[]))

    assert parsed is None
    assert violations == (
        CaseViolation.INVALID_INPUT_DIGESTS,
        CaseViolation.NO_ASSERTIONS,
    )


def test_the_work_package_vocabulary_is_closed() -> None:
    """`W90` named nothing: the roadmap stops at W80 and the host surface is elsewhere.

    A package that does not exist is worse than a missing one — a reader of a bundle
    could not tell what its evidence belonged to, and there was nothing to check the
    answer against — so a name outside the vocabulary is refused rather than shaped.
    """

    parsed, violations = parse_case_manifest(document(work_package="W90"))

    assert parsed is None
    assert violations == (CaseViolation.INVALID_WORK_PACKAGE,)


@pytest.mark.parametrize("package", WORK_PACKAGES)
def test_every_named_work_package_is_accepted(package: str) -> None:
    """The negative control: the vocabulary is closed, not merely narrow."""

    parsed, violations = parse_case_manifest(document(work_package=package))

    assert violations == (), violations
    assert parsed is not None
    assert parsed.work_package == package


def test_the_schema_and_the_domain_name_the_same_work_packages() -> None:
    """Two lists of one vocabulary are two vocabularies, and one of them would drift.

    The schema is what a fixture is validated against and the domain is what promotion
    groups by, so a package added to one and not the other would be a case that
    validates and then belongs to nothing.
    """

    schema = json.loads(
        (REPOSITORY_ROOT / "schemas" / "case-manifest.schema.json").read_text(encoding="utf-8")
    )

    assert schema["properties"]["work_package"]["enum"] == list(WORK_PACKAGES)


def test_every_reviewed_case_names_a_work_package_that_exists() -> None:
    """The reviewed cases are the reason the vocabulary exists, so they have to fit it."""

    registry = load_case_registry(CASES)

    assert {case.work_package for case in registry.cases} <= set(WORK_PACKAGES)
    assert "W90" not in {case.work_package for case in registry.cases}


def test_the_registry_reads_a_directory_of_cases() -> None:
    registry = load_case_registry(CASES)

    assert registry.by_id()["W00-CONTRACT-001"].mandatory
    assert registry.for_work_package("W00") != ()
    assert registry.duplicate_ids() == ()
    # Grouping is the property; "some package happens to be empty" is not. The line
    # here used to be `for_work_package("W50") == ()`, which was true when written and
    # became false the moment W50 got its first case — a test that pinned a transient
    # fact while reading as a test of the grouping.
    for case in registry.cases:
        assert case in registry.for_work_package(case.work_package), case.case_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("inputs", "not-a-list"),
        ("assertions", [1, 2]),
        ("oracle_inputs", "tests/oracle/canary.json"),
    ],
)
def test_a_malformed_list_field_is_refused_not_emptied(field: str, value: object) -> None:
    parsed, violations = parse_case_manifest(document(**{field: value}))

    assert parsed is None
    assert CaseViolation.INVALID_STRING_LIST in violations


def test_a_non_boolean_mandatory_flag_is_refused_not_downgraded() -> None:
    """A truthy string must not quietly drop the case out of the promotion gate."""

    parsed, violations = parse_case_manifest(document(mandatory="true"))

    assert parsed is None
    assert violations == (CaseViolation.INVALID_MANDATORY,)


def test_a_case_that_asserts_nothing_is_refused() -> None:
    """The schema requires at least one assertion, and an empty case cannot gate."""

    parsed, violations = parse_case_manifest(document(assertions=[]))

    assert parsed is None
    assert violations == (CaseViolation.NO_ASSERTIONS,)


def test_a_case_that_declares_no_inputs_is_allowed() -> None:
    parsed, violations = parse_case_manifest(document(inputs=[]))

    assert violations == ()
    assert parsed is not None
    assert parsed.inputs == ()


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"schema_version": 2}, CaseViolation.SCHEMA_VERSION_UNSUPPORTED),
        ({"case_id": "w50-001"}, CaseViolation.INVALID_CASE_ID),
        ({"case_id": "W50-1"}, CaseViolation.INVALID_CASE_ID),
        ({"work_package": "W5"}, CaseViolation.INVALID_WORK_PACKAGE),
        ({"work_package": "w50"}, CaseViolation.INVALID_WORK_PACKAGE),
        ({"extra": "field"}, CaseViolation.UNKNOWN_FIELD),
        ({"case_id": _DROP}, CaseViolation.MISSING_FIELD),
        ({"assertions": _DROP}, CaseViolation.MISSING_FIELD),
    ],
)
def test_an_invalid_case_is_refused_with_a_specific_reason(
    overrides: dict[str, object], expected: CaseViolation
) -> None:
    parsed, violations = parse_case_manifest(document(**overrides))

    assert parsed is None
    assert expected in violations


def test_a_case_without_mandatory_oracle_inputs_is_valid() -> None:
    parsed, violations = parse_case_manifest(document(oracle_inputs=[]))

    assert violations == ()
    assert parsed is not None
    assert not parsed.reads_oracle


def test_duplicate_case_identifiers_are_refused(tmp_path: Path) -> None:
    payload = json.dumps(document())
    (tmp_path / "a.json").write_text(payload, encoding="utf-8")
    (tmp_path / "b.json").write_text(payload, encoding="utf-8")

    with pytest.raises(MinekinError, match="not unique") as raised:
        load_case_registry(tmp_path)

    assert raised.value.category is ErrorCategory.CONFIG


def test_a_directory_without_cases_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="no case manifests"):
        load_case_registry(tmp_path)


def test_unreadable_case_json_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")

    with pytest.raises(MinekinError, match="not readable UTF-8 JSON"):
        load_case_manifest(broken)


def evidence(
    case_id: str = "W50-SNAPSHOT-001",
    case_version: str = "",
    *,
    verified: bool = True,
    passed: bool = True,
    re_judged: ReJudge = ReJudge.AGREES,
) -> CaseEvidence:
    return CaseEvidence(
        case_id=case_id,
        case_version=case_version,
        verified=verified,
        passed=passed,
        re_judged=re_judged,
    )


def test_evidence_whose_bytes_contradict_its_verdict_does_not_promote() -> None:
    """A digest proves the bytes did not move; it says nothing about what they mean.

    A manifest rewritten to claim a pass, with the digest file regenerated beside it,
    verifies clean — so `verified`, `passed` and the version all hold and the only
    thing that can refuse it is reaching the verdict again from the sealed bytes.
    """

    definition = case()

    verdict = evaluate_promotion(
        [definition],
        [evidence(case_version=definition.digest, re_judged=ReJudge.DISAGREES)],
    )

    assert not verdict.promotable
    assert verdict.blocks == (PromotionBlock.EVIDENCE_DISAGREES_WITH_ITS_BYTES,)
    assert verdict.blocking_cases == (definition.case_id,)


def test_a_bundle_nobody_could_re_judge_is_not_treated_as_disagreeing() -> None:
    """The negative control: silence is not contradiction, and it is not agreement.

    `UNJUDGED` is a fact about the reader — a bundle sealed before its inputs were
    recorded — and it is reported with its reason rather than blocking. What keeps
    this from being a road out of the gate is that removing a bundle's inputs is
    caught by verification, not by this: a declared artifact that is gone, or a file
    the manifest does not declare, are both already blockers.
    """

    definition = case()

    for outcome in (ReJudge.UNJUDGED, ReJudge.NOT_ATTEMPTED):
        verdict = evaluate_promotion(
            [definition], [evidence(case_version=definition.digest, re_judged=outcome)]
        )

        assert verdict.promotable, outcome
        assert PromotionBlock.EVIDENCE_DISAGREES_WITH_ITS_BYTES not in verdict.blocks


def test_every_mandatory_case_with_a_verified_pass_promotes() -> None:
    definition = case()

    verdict = evaluate_promotion([definition], [evidence(case_version=definition.digest)])

    assert verdict.promotable
    assert verdict.blocking_cases == ()
    assert verdict.blocks == ()


def test_a_mandatory_case_without_evidence_blocks() -> None:
    definition = case()

    verdict = evaluate_promotion([definition], [])

    assert not verdict.promotable
    assert verdict.blocking_cases == (definition.case_id,)
    assert verdict.blocks == (PromotionBlock.CASE_WITHOUT_EVIDENCE,)


def test_evidence_that_does_not_verify_is_not_evidence() -> None:
    definition = case()

    verdict = evaluate_promotion(
        [definition], [evidence(case_version=definition.digest, verified=False)]
    )

    assert not verdict.promotable
    assert verdict.blocks == (PromotionBlock.EVIDENCE_NOT_VERIFIED,)


def test_incomplete_evidence_is_not_a_pass() -> None:
    definition = case()

    verdict = evaluate_promotion(
        [definition], [evidence(case_version=definition.digest, passed=False)]
    )

    assert not verdict.promotable
    assert verdict.blocks == (PromotionBlock.EVIDENCE_IS_NOT_A_PASS,)


def test_evidence_against_an_older_case_definition_does_not_count() -> None:
    definition = case()

    verdict = evaluate_promotion([definition], [evidence(case_version="f" * 64)])

    assert not verdict.promotable
    assert verdict.blocks == (PromotionBlock.CASE_VERSION_MISMATCH,)


def test_a_non_mandatory_case_does_not_gate() -> None:
    definition = case(mandatory=False)

    verdict = evaluate_promotion([definition], [])

    assert verdict.blocks == (PromotionBlock.NO_MANDATORY_CASES,)
    assert verdict.blocking_cases == ()


def test_one_pass_does_not_cover_another_case() -> None:
    first = case(case_id="W50-SNAPSHOT-001")
    second = case(case_id="W50-BOUNDARY-002")

    verdict = evaluate_promotion([first, second], [evidence(case_version=first.digest)])

    assert not verdict.promotable
    assert verdict.blocking_cases == ("W50-BOUNDARY-002",)


def test_only_the_named_work_package_gates_promotion() -> None:
    registry = CaseRegistry(
        cases=(
            case(case_id="W50-ONLY-001", work_package="W50"),
            case(case_id="W60-ONLY-001", work_package="W60"),
        )
    )

    assert [item.case_id for item in registry.mandatory_cases("W50")] == ["W50-ONLY-001"]
    assert [item.case_id for item in registry.mandatory_cases()] == [
        "W50-ONLY-001",
        "W60-ONLY-001",
    ]


@pytest.fixture
def bundles(tmp_path: Path) -> Iterator[Path]:
    directory = tmp_path / "bundles"
    directory.mkdir()
    yield directory
    for child in directory.iterdir():
        unseal_bundle(child)


def seal(
    directory: Path,
    name: str,
    definition: CaseManifest,
    result: EvidenceResult,
) -> None:
    failures = () if result is EvidenceResult.PASS else ("did_not_join",)
    assertions = Assertions(expected=("join_seen",), observed=("join_seen",), failures=failures)
    write_bundle(
        directory / name,
        EvidenceManifest(
            test_run_id=name,
            case_id=definition.case_id,
            case_version=definition.digest,
            result=result,
            launch_plan_digest="a" * 64,
            bridge_digest="b" * 64,
            protocol_schema_digest="c" * 64,
            server_config_digest="d" * 64,
            minecraft="1.21.4",
            loader="0.16.9",
            fabric_api="0.119.4+1.21.4",
            assertions=assertions,
            server_jar_sha1="4707d00eb834b446575d89a61a11b5d548d8c001",
            os_kernel="Linux 6.8",
            java_runtime="Temurin 21.0.12.1",
            cpu_memory="8 vCPU / 16 GiB",
            renderer_display="llvmpipe / Xvfb",
            world_kind="dedicated",
            seed_or_snapshot_id="snapshot-01",
            configured_profile="kin-01/profile-r1",
            server_observed_name_uuid="Kin/8f40376b",
        ),
        {"bridge-trace.jsonl": b'{"event":"join"}\n'},
        seal=False,
    )


def test_a_sealed_pass_bundle_promotes_its_case(bundles: Path) -> None:
    definition = load_case_manifest(W00_CASE)
    seal(bundles, "run-01", definition, EvidenceResult.PASS)

    verdict = evaluate_case_promotion(
        CaseRegistry(cases=(definition,)), [bundles / "run-01"], work_package="W00"
    )

    assert verdict.promotable, verdict.as_document()


def test_changing_a_reviewed_input_pin_makes_old_evidence_stale(bundles: Path) -> None:
    """Fixture bytes are part of the case version, not mutable ambient state."""

    previous = case(
        case_id="W00-CONTRACT-001",
        work_package="W00",
        input_digests={"fixture.bin": "a" * 64},
    )
    current = case(
        case_id="W00-CONTRACT-001",
        work_package="W00",
        input_digests={"fixture.bin": "b" * 64},
    )
    seal(bundles, "run-01", previous, EvidenceResult.PASS)

    verdict = evaluate_case_promotion(
        CaseRegistry(cases=(current,)),
        [bundles / "run-01"],
        work_package="W00",
    )

    assert not verdict.promotable
    assert verdict.blocks == (PromotionBlock.CASE_VERSION_MISMATCH,)


def test_registry_loading_rejects_changed_input_bytes_when_the_case_pin_was_forgotten(
    tmp_path: Path,
) -> None:
    """Updating ambient fixture state cannot preserve an old case version."""

    fixture = tmp_path / "tests" / "fixtures" / "saves" / "world" / "level.dat"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"world-b")
    definition = document(
        inputs=["tests/fixtures/saves/world"],
        input_digests={
            "tests/fixtures/saves/world/level.dat": hashlib.sha256(b"world-a").hexdigest()
        },
    )
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(definition), encoding="utf-8")

    with pytest.raises(MinekinError, match="input digest mismatch"):
        load_case_manifest(case_path, input_root=tmp_path)


def test_a_bundle_that_names_another_run_does_not_promote_its_case(bundles: Path) -> None:
    """The directory name is the attribution in this path too, not only in verify."""

    definition = load_case_manifest(W00_CASE)
    seal(bundles, "run-01", definition, EvidenceResult.PASS)
    (bundles / "run-01").rename(bundles / "run-02")

    verdict = evaluate_case_promotion(
        CaseRegistry(cases=(definition,)), [bundles / "run-02"], work_package="W00"
    )

    assert not verdict.promotable
    assert verdict.blocks == (PromotionBlock.EVIDENCE_NOT_VERIFIED,)


def test_two_bundle_directories_with_one_run_id_are_refused(tmp_path: Path) -> None:
    definition = load_case_manifest(W00_CASE)
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    seal(left, "run-01", definition, EvidenceResult.PASS)
    seal(right, "run-01", definition, EvidenceResult.PASS)

    with pytest.raises(MinekinError, match="run-01 names more than one evidence bundle"):
        evaluate_case_promotion(
            CaseRegistry(cases=(definition,)),
            [left / "run-01", right / "run-01"],
            work_package="W00",
        )


def test_a_tampered_bundle_stops_its_case_from_promoting(bundles: Path) -> None:
    definition = load_case_manifest(W00_CASE)
    seal(bundles, "run-01", definition, EvidenceResult.PASS)
    (bundles / "run-01" / "bridge-trace.jsonl").write_bytes(b'{"event":"tampered"}\n')

    assert not verify_bundle(bundles / "run-01").verified
    verdict = evaluate_case_promotion(
        CaseRegistry(cases=(definition,)), [bundles / "run-01"], work_package="W00"
    )

    assert not verdict.promotable
    assert verdict.blocks == (PromotionBlock.EVIDENCE_NOT_VERIFIED,)


def test_an_incomplete_bundle_leaves_its_case_blocking(bundles: Path) -> None:
    definition = load_case_manifest(W00_CASE)
    seal(bundles, "run-01", definition, EvidenceResult.INCOMPLETE)

    verdict = evaluate_case_promotion(
        CaseRegistry(cases=(definition,)), [bundles / "run-01"], work_package="W00"
    )

    assert not verdict.promotable
    assert verdict.blocks == (PromotionBlock.EVIDENCE_IS_NOT_A_PASS,)
    assert verdict.blocking_cases == ("W00-CONTRACT-001",)


# ---------------------------------------------------------------------------
# What the contracts require, and what a gate reads out of it
# ---------------------------------------------------------------------------
#
# Every rule above reads the registry, so every one of them is silent about a case
# nobody wrote. These are about the other reading — the inventory — and about the one
# property that makes a gate's requirement a view over it rather than a list of files.


def test_the_reviewed_inventory_is_usable_as_written() -> None:
    identifiers = [entry.case_id for entry in REQUIRED_CASES]

    assert required_case_violations() == ()
    assert len(identifiers) == len(set(identifiers))


def inventory_for(*cases: CaseManifest) -> tuple[RequiredCase, ...]:
    """An inventory whose gates require exactly these cases and nothing else.

    A gate is judged against what the inventory requires of it, so a test about what a
    bundle has to be still has to state the gate. An empty inventory would not be a
    narrower question — it would be a gate that requires no cases, which is a different
    registry entirely.
    """

    return tuple(
        RequiredCase(
            case.case_id,
            case.work_package,
            (case.work_package,),
            ValidationClass.LOCAL_ONLY,
            "docs/nowhere.md",
        )
        for case in cases
    )


def test_every_gate_is_a_work_package_and_none_of_them_is_empty() -> None:
    """A gate that required nothing would be a name that reads as coverage."""

    assert set(REQUIRED_GATES) <= set(WORK_PACKAGES)
    for gate in REQUIRED_GATES:
        assert required_for_gates((gate,)), gate
    for entry in REQUIRED_CASES:
        assert entry.expected_work_package in REQUIRED_GATES, entry.case_id


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        (
            RequiredCase(
                "core-001", "W40", ("W40",), ValidationClass.RUNTIME_REQUIRED, "docs/nowhere.md"
            ),
            RequiredCaseViolation.INVALID_CASE_ID,
        ),
        (
            RequiredCase(
                "CORE-999", "W40", ("W40",), ValidationClass.RUNTIME_REQUIRED, "docs/nowhere.md"
            ),
            RequiredCaseViolation.UNKNOWN_CASE_ID,
        ),
        (
            RequiredCase(
                "CORE-999", "W40", ("W99",), ValidationClass.RUNTIME_REQUIRED, "docs/nowhere.md"
            ),
            RequiredCaseViolation.UNKNOWN_GATE,
        ),
        (
            RequiredCase(
                "CORE-999", "W99", ("W40",), ValidationClass.RUNTIME_REQUIRED, "docs/nowhere.md"
            ),
            RequiredCaseViolation.UNKNOWN_PACKAGE,
        ),
        (
            RequiredCase(
                "CORE-999", "W40", (), ValidationClass.RUNTIME_REQUIRED, "docs/nowhere.md"
            ),
            RequiredCaseViolation.EMPTY_REQUIRED_FOR,
        ),
    ],
)
def test_an_entry_the_inventory_cannot_hold_is_refused_and_named(
    entry: RequiredCase, expected: RequiredCaseViolation
) -> None:
    """Well-formed is not the same as holdable, which is why the two vocabularies close.

    `CORE-999` is a perfectly shaped identifier, so nothing but the closed lists
    refuses the entries that name `W99` — and a name outside them is what a typo in
    this table looks like.
    """

    violations = required_case_violations((*REQUIRED_CASES, entry))

    assert expected in [reason for reason, _ in violations]
    assert any(entry.case_id in subject for _, subject in violations)


def test_a_required_case_named_twice_is_refused_and_named() -> None:
    """One case with two answers about what it needs is not an inventory."""

    assert required_case_violations((*REQUIRED_CASES, REQUIRED_CASES[0])) == (
        (RequiredCaseViolation.DUPLICATE_CASE_ID, REQUIRED_CASES[0].case_id),
    )


def test_a_gate_is_read_from_membership_and_not_from_a_work_package() -> None:
    """The membership side of the same property: what each gate asks for.

    `p0-core` is every phase's cases plus `CORE-030`; a phase requires its own cases
    and the slice's, and nothing else. `CORE-030` names no single phase, so it is
    required by the slice and by no phase at all.
    """

    registry = load_case_registry(CASES)
    w40 = registry.requirement("W40")
    w40_names = {*w40.absent, *w40.misattributed, *w40.non_mandatory}
    by_slice = {entry.case_id for entry in required_for_gates(("p0-core",))}
    by_phases = {
        entry.case_id
        for entry in required_for_gates(
            tuple(gate for gate in REQUIRED_GATES if gate.startswith("W"))
        )
    }

    assert "HOST-001" in registry.requirement("host-integrated").absent
    assert "NAV-EXP-010" in registry.requirement("p0-nav-exp").absent
    assert not any(name.startswith(("HOST", "NAV")) for name in w40_names)
    assert registry.requirement("W60").absent == ()
    assert "CORE-030" in by_slice
    assert "CORE-030" not in by_phases
    assert len(by_slice) > len(by_phases)


def test_deleting_a_required_case_blocks_only_the_gates_that_require_it(
    tmp_path: Path,
) -> None:
    """The negative mutation and the scoping, in one reading.

    `CORE-020` is required by `W40` and by `p0-core`, and not by W60 — whose gate is
    still satisfied afterwards, which is the difference between a gate and "the
    repository at once".
    """

    cases = tmp_path / "cases"
    shutil.copytree(CASES, cases)
    (cases / "core-020.json").unlink()
    registry = load_case_registry(cases)

    assert "CORE-020" in registry.requirement("W40").absent
    assert "CORE-020" in registry.requirement("p0-core").absent
    assert registry.requirement("W60").satisfied is True
    assert "CORE-020" in {entry.case_id for entry in required_for_gates(("p0-core",))}
    assert "CORE-020" not in {entry.case_id for entry in required_for_gates(("W60",))}


def test_a_required_case_that_is_not_mandatory_is_reported_separately() -> None:
    """Required presence and mandatory evidence remain different questions.

    Every case is registered here and every one of them is declared not to gate, so
    the evidence rule has nothing to ask about at all: there are no mandatory cases.
    The requirement reports the distinction; the existing no-mandatory rule is what
    blocks the evidence verdict, without silently rewriting every required case.
    """

    held = load_case_registry(CASES)
    registry = CaseRegistry(
        cases=tuple(replace(case, mandatory=False) for case in held.required_cases("W60"))
    )
    requirement = registry.requirement("W60")

    assert requirement.absent == ()
    assert requirement.satisfied is True
    assert set(requirement.non_mandatory) == {case.case_id for case in registry.cases}

    verdict = evaluate_promotion(registry.cases, [], requirement=requirement)

    assert not verdict.promotable
    assert verdict.blocks == (PromotionBlock.NO_MANDATORY_CASES,)
    assert verdict.blocking_cases == ()


def test_an_unknown_gate_is_refused_at_the_domain_seam() -> None:
    with pytest.raises(ValueError, match="unknown required-case gate"):
        CaseRegistry(cases=()).requirement("W99")


def test_a_required_case_filed_under_another_work_package_blocks_its_gate() -> None:
    """A case filed elsewhere has moved between gates and passes a question nobody asked."""

    held = load_case_registry(CASES)
    moved = CaseRegistry(
        cases=tuple(
            replace(case, work_package="W60") if case.case_id == "CORE-020" else case
            for case in held.required_cases("W40")
        )
    )
    requirement = moved.requirement("W40")

    assert requirement.misattributed == ("CORE-020",)
    assert "CORE-020" not in requirement.absent

    verdict = evaluate_promotion(moved.cases, [], requirement=requirement)

    assert PromotionBlock.REQUIRED_CASE_MISATTRIBUTED in verdict.blocks
    assert "CORE-020" in verdict.blocking_cases


def test_the_evidence_rule_stands_alone_when_no_requirement_is_given() -> None:
    """What every test above this section asks, and what makes that an answer.

    The requirement is a separate question from the evidence rule, and a verdict that
    carries `None` says it was never asked — rather than inheriting "the case set is
    complete" from a default.
    """

    definition = case()

    verdict = evaluate_promotion([definition], [evidence(case_version=definition.digest)])

    assert verdict.promotable
    assert verdict.blocks == ()
    assert verdict.requirement is None
    assert verdict.as_document()["requirement"] is None


def test_the_adapter_reads_both_halves_of_the_question_from_the_gate(bundles: Path) -> None:
    """Fail closed without the caller asking for anything.

    A bundle that satisfies everything the evidence rule checks, judged against a gate
    whose required cases nobody wrote: the verdict refuses, and names what is missing
    rather than only that something is.
    """

    definition = case()
    seal(bundles, "run-01", definition, EvidenceResult.PASS)
    registry = CaseRegistry(cases=(definition,))

    verdict = evaluate_case_promotion(registry, [bundles / "run-01"], work_package="W50")

    assert not verdict.promotable
    assert verdict.requirement is not None
    assert verdict.requirement.absent == ("ADMIT-070", "ADMIT-120", "CORE-080")
    assert PromotionBlock.REQUIRED_CASE_NOT_REGISTERED in verdict.blocks


def test_the_adapter_refuses_a_name_outside_the_frozen_gate_domain() -> None:
    with pytest.raises(MinekinError, match="unknown required-case gate"):
        evaluate_case_promotion(CaseRegistry(cases=()), [], work_package="W99")


@pytest.mark.parametrize(
    "required",
    [
        (*REQUIRED_CASES, REQUIRED_CASES[0]),
        (*REQUIRED_CASES, replace(REQUIRED_CASES[0], case_id="CORE-999")),
    ],
)
def test_an_unusable_inventory_is_refused_before_a_gate_can_read_it(
    required: tuple[RequiredCase, ...],
) -> None:
    with pytest.raises(ValueError, match="required-case inventory is not usable"):
        CaseRegistry(cases=()).requirement("W40", required=required)
