from __future__ import annotations

import hashlib
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
    WORK_PACKAGES,
    CaseEvidence,
    CaseManifest,
    CaseRegistry,
    CaseViolation,
    PromotionBlock,
    ReJudge,
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

    previous = case(input_digests={"fixture.bin": "a" * 64})
    current = case(input_digests={"fixture.bin": "b" * 64})
    seal(bundles, "run-01", previous, EvidenceResult.PASS)

    verdict = evaluate_case_promotion(
        CaseRegistry(cases=(current,)), [bundles / "run-01"], work_package="W50"
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
