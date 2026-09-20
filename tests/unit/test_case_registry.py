from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from minekin_core.adapters.evidence.bundle import unseal_bundle, verify_bundle, write_bundle
from minekin_core.adapters.evidence.promotion import (
    evaluate_case_promotion,
    load_case_manifest,
    load_case_registry,
)
from minekin_core.domain.cases import (
    CaseEvidence,
    CaseManifest,
    CaseRegistry,
    CaseViolation,
    PromotionBlock,
    evaluate_promotion,
    parse_case_manifest,
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


def test_the_registry_reads_a_directory_of_cases() -> None:
    registry = load_case_registry(CASES)

    assert registry.by_id()["W00-CONTRACT-001"].mandatory
    assert registry.for_work_package("W00") != ()
    assert registry.for_work_package("W50") == ()
    assert registry.duplicate_ids() == ()


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
) -> CaseEvidence:
    return CaseEvidence(
        case_id=case_id,
        case_version=case_version,
        verified=verified,
        passed=passed,
    )


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
