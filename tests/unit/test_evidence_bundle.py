from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from minekin_core.adapters.evidence.bundle import (
    DIGEST_NAME,
    MANIFEST_NAME,
    unseal_bundle,
    verify_bundle,
    write_bundle,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.evidence import (
    EMPTY_DOCUMENT_SHA256,
    NO_WORLD,
    ArtifactRecord,
    Assertions,
    EvidenceManifest,
    EvidenceResult,
    EvidenceViolation,
)

DIGEST = "a" * 64


def base_manifest() -> EvidenceManifest:
    return EvidenceManifest(
        test_run_id="run-01",
        case_id="P0-CORE-001",
        case_version="b" * 64,
        result=EvidenceResult.PASS,
        launch_plan_digest=DIGEST,
        bridge_digest="c" * 64,
        protocol_schema_digest="d" * 64,
        server_config_digest="e" * 64,
        minecraft="1.21.4",
        loader="0.16.9",
        fabric_api="0.119.4+1.21.4",
        assertions=Assertions(expected=("join_seen",), observed=("join_seen",), failures=()),
        server_jar_sha1="4707d00eb834b446575d89a61a11b5d548d8c001",
        os_kernel="Linux 6.8",
        java_runtime="Temurin 21.0.12.1",
        cpu_memory="8 vCPU / 16 GiB",
        renderer_display="llvmpipe / Xvfb",
        world_kind="dedicated",
        seed_or_snapshot_id="snapshot-01",
        configured_profile="kin-01/profile-r1",
        server_observed_name_uuid="Kin/8f40376b",
    )


def manifest(**overrides: object) -> EvidenceManifest:
    return replace(base_manifest(), **overrides)


def artifacts() -> dict[str, bytes]:
    return {
        "bridge-trace.jsonl": b'{"event":"join"}\n',
        "server-truth.txt": b"Kin joined\n",
    }


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Iterator[Path]:
    """Keep bundle directories writable so pytest can clean them up."""

    directory = tmp_path / "bundle"
    yield directory
    if directory.exists():
        unseal_bundle(directory)


def test_a_complete_pass_bundle_is_sealed_and_verifies(bundle_dir: Path) -> None:
    written = write_bundle(bundle_dir, manifest(), artifacts())

    verification = verify_bundle(bundle_dir)

    assert verification.verified
    assert verification.violations == ()
    assert verification.manifest == written.manifest
    assert verification.bundle_digest == written.bundle_digest


def test_every_artifact_is_recorded_with_its_digest_and_size(bundle_dir: Path) -> None:
    written = write_bundle(bundle_dir, manifest(), artifacts())

    records = {record.path: record for record in written.manifest.artifacts}

    assert sorted(records) == ["bridge-trace.jsonl", "server-truth.txt"]
    assert records["server-truth.txt"].sha256 == hashlib.sha256(b"Kin joined\n").hexdigest()
    assert records["server-truth.txt"].size == len(b"Kin joined\n")


def test_the_bundle_digest_covers_the_manifest_bytes(bundle_dir: Path) -> None:
    written = write_bundle(bundle_dir, manifest(), artifacts())

    on_disk = (bundle_dir / DIGEST_NAME).read_text(encoding="ascii").strip()
    recomputed = hashlib.sha256((bundle_dir / MANIFEST_NAME).read_bytes()).hexdigest()

    assert on_disk == written.bundle_digest
    assert recomputed == written.bundle_digest


def test_a_tampered_artifact_is_caught(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts(), seal=False)

    (bundle_dir / "server-truth.txt").write_bytes(b"Kin joined twice\n")

    verification = verify_bundle(bundle_dir)

    assert not verification.verified
    assert verification.violations == ("ARTIFACT_DIGEST_MISMATCH:server-truth.txt",)


def test_a_tampered_manifest_is_caught_by_its_own_digest(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts(), seal=False)
    document = json.loads((bundle_dir / MANIFEST_NAME).read_bytes())
    document["result"] = "FAIL"
    (bundle_dir / MANIFEST_NAME).write_text(json.dumps(document))

    verification = verify_bundle(bundle_dir)

    assert "BUNDLE_DIGEST_MISMATCH" in verification.violations


def test_an_undeclared_file_is_caught(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts(), seal=False)

    (bundle_dir / "extra.txt").write_bytes(b"smuggled\n")

    verification = verify_bundle(bundle_dir)

    assert not verification.verified
    assert verification.violations == ("UNDECLARED_FILE:extra.txt",)


def test_a_missing_artifact_is_caught(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts(), seal=False)

    (bundle_dir / "server-truth.txt").unlink()

    assert verify_bundle(bundle_dir).violations == ("ARTIFACT_MISSING:server-truth.txt",)


def test_a_sealed_bundle_is_read_only(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts())

    assert verify_bundle(bundle_dir).sealed


def test_unsealing_makes_the_bundle_writable_again(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts())

    unseal_bundle(bundle_dir)

    assert not verify_bundle(bundle_dir).sealed


def test_the_read_only_answer_does_not_depend_on_who_is_asking(
    bundle_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Permission bits do not apply to root, and `os.access` says so.

    Measured in the runner container: the seal is applied as uid 0, the files are
    mode 400, and `os.access(.., W_OK)` reports them writable — so asking whether
    a bundle is sealed through it reported every genuinely sealed bundle as open.
    The modes are what the seal is; who is asking is a separate matter.
    """

    write_bundle(bundle_dir, manifest(), artifacts())

    def root_may_write(_path: object, _mode: int) -> bool:
        return True

    monkeypatch.setattr("os.access", root_may_write)

    assert verify_bundle(bundle_dir).sealed


def test_a_bundle_is_never_written_over(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts(), seal=False)

    with pytest.raises(MinekinError, match="already holds a bundle") as raised:
        write_bundle(bundle_dir, manifest(case_id="P0-CORE-002"), artifacts())

    assert raised.value.category is ErrorCategory.STORAGE


def test_a_credential_literal_stops_the_whole_bundle(bundle_dir: Path) -> None:
    """A token must never be sealed, and a silently redacted log is worse than none."""

    with pytest.raises(MinekinError, match="credential literal") as raised:
        write_bundle(
            bundle_dir,
            manifest(),
            {"stdout.txt": b"accessToken=SECRET-TOKEN-9f3a\n"},
            secrets=("SECRET-TOKEN-9f3a",),
        )

    assert raised.value.category is ErrorCategory.STORAGE
    assert not bundle_dir.exists()


def test_a_credential_literal_in_the_manifest_is_refused_too(bundle_dir: Path) -> None:
    with pytest.raises(MinekinError, match="manifest contains a credential literal"):
        write_bundle(
            bundle_dir,
            manifest(configured_profile="profile SECRET-TOKEN-9f3a"),
            artifacts(),
            secrets=("SECRET-TOKEN-9f3a",),
        )


def test_a_clean_bundle_with_the_same_secrets_still_seals(bundle_dir: Path) -> None:
    written = write_bundle(bundle_dir, manifest(), artifacts(), secrets=("SECRET-TOKEN-9f3a",))

    assert verify_bundle(bundle_dir).verified
    assert written.bundle_digest


def test_an_artifact_may_not_escape_the_bundle(tmp_path: Path) -> None:
    """The guard is a whitelist: Windows does not treat `/x` as absolute."""

    for name in ("../escape.txt", "/absolute.txt", "C:/escape.txt", "a/../b.txt", ""):
        with pytest.raises(MinekinError, match="plain relative path"):
            write_bundle(tmp_path / "bundle", manifest(), {name: b"x"})


def test_a_nested_artifact_name_is_still_accepted(bundle_dir: Path) -> None:
    written = write_bundle(bundle_dir, manifest(), {"screenshots/first-frame.png": b"\x89PNG"})

    assert [record.path for record in written.manifest.artifacts] == ["screenshots/first-frame.png"]
    assert verify_bundle(bundle_dir).verified


def test_a_pass_without_a_comparison_is_not_sealable(bundle_dir: Path) -> None:
    """A bundle that asserts nothing has proven nothing and cannot claim a pass."""

    empty = Assertions(expected=(), observed=(), failures=())

    assert EvidenceViolation.RESULT_NEEDS_ASSERTIONS in manifest(assertions=empty).violations()
    with pytest.raises(MinekinError, match="RESULT_NEEDS_ASSERTIONS"):
        write_bundle(bundle_dir, manifest(assertions=empty), artifacts())


def test_a_failure_that_observed_nothing_is_the_evidence_that_must_survive(
    bundle_dir: Path,
) -> None:
    """Measured: a run that failed every assertion of CORE-020 could not be sealed.

    `FAIL` is not a claim about how a run went — it is a claim that it did not
    meet its case, and its reasons are what carry it. Requiring a non-empty
    `observed` list of it refused to seal exactly the runs whose evidence matters
    most.
    """

    nothing_seen = Assertions(
        expected=("server_observed_join_identity",),
        observed=(),
        failures=("server_observed_join_identity:JOIN_NOT_LOGGED",),
    )

    written = write_bundle(
        bundle_dir, manifest(result=EvidenceResult.FAIL, assertions=nothing_seen), artifacts()
    )

    assert written.manifest.result is EvidenceResult.FAIL
    assert verify_bundle(bundle_dir).verified


def test_a_pass_that_observed_nothing_is_still_not_sealable() -> None:
    """The guard the rule exists for: nothing seen cannot be a pass."""

    nothing_seen = Assertions(expected=("server_observed_join_identity",), observed=(), failures=())

    assert (
        EvidenceViolation.RESULT_NEEDS_ASSERTIONS in manifest(assertions=nothing_seen).violations()
    )


def test_a_run_that_joined_no_world_records_the_absence_and_seals(bundle_dir: Path) -> None:
    """The contract's third kind: what a run with no server at all leaves behind."""

    without_a_world = manifest(world_kind=NO_WORLD, server_config_digest=EMPTY_DOCUMENT_SHA256)

    written = write_bundle(bundle_dir, without_a_world, artifacts())

    assert written.manifest.world_kind == NO_WORLD
    assert written.manifest.violations() == ()
    assert verify_bundle(bundle_dir).verified


def test_a_world_record_that_contradicts_itself_is_refused() -> None:
    """Both directions, because one of them would be an escape hatch.

    A kind that could be paired with any digest would let a bundle say "no world"
    to avoid having a server configuration at all, which is not the same claim as
    "this run had no server".
    """

    # Saying no world while carrying a server's configuration.
    assert EvidenceViolation.WORLD_RECORD_INCONSISTENT in manifest(world_kind=NO_WORLD).violations()
    # Saying a world while carrying the digest of nothing.
    assert (
        EvidenceViolation.WORLD_RECORD_INCONSISTENT
        in manifest(server_config_digest=EMPTY_DOCUMENT_SHA256).violations()
    )
    # And the plain case is not a violation.
    assert EvidenceViolation.WORLD_RECORD_INCONSISTENT not in manifest().violations()


def test_an_incomplete_bundle_without_a_comparison_is_sealable(bundle_dir: Path) -> None:
    empty = Assertions(expected=(), observed=(), failures=("missing_evidence",))

    written = write_bundle(
        bundle_dir, manifest(result=EvidenceResult.INCOMPLETE, assertions=empty), artifacts()
    )

    assert written.manifest.result is EvidenceResult.INCOMPLETE


def test_a_pass_that_records_failures_is_contradictory() -> None:
    contradictory = Assertions(expected=("a",), observed=("b",), failures=("join_missing",))

    assert EvidenceViolation.PASS_WITH_FAILURES in manifest(assertions=contradictory).violations()


def test_a_failure_without_a_reason_code_is_not_diagnosable() -> None:
    silent = Assertions(expected=("a",), observed=("b",), failures=())

    assert (
        EvidenceViolation.FAILURE_WITHOUT_REASON
        in manifest(result=EvidenceResult.FAIL, assertions=silent).violations()
    )


def test_an_ambiguous_result_is_available_for_undecidable_ordering() -> None:
    ambiguous = Assertions(expected=("a_before_b",), observed=("unknown",), failures=("clock",))

    assert manifest(result=EvidenceResult.AMBIGUOUS, assertions=ambiguous).violations() == ()


@pytest.mark.parametrize("field", ["launch_plan_digest", "bridge_digest", "protocol_schema_digest"])
def test_a_malformed_digest_is_not_sealable(field: str) -> None:
    assert EvidenceViolation.INVALID_DIGEST in manifest(**{field: "not-a-digest"}).violations()


def test_a_missing_required_field_is_not_sealable() -> None:
    assert EvidenceViolation.MISSING_FIELD in manifest(case_id="  ").violations()


def test_an_empty_directory_is_not_a_bundle(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="not an evidence bundle"):
        verify_bundle(tmp_path)


def test_an_unreadable_manifest_is_refused(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts(), seal=False)
    (bundle_dir / MANIFEST_NAME).write_bytes(b"{ not json")

    with pytest.raises(MinekinError, match="unreadable manifest"):
        verify_bundle(bundle_dir)


def test_a_foreign_schema_is_refused(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts(), seal=False)
    document = json.loads((bundle_dir / MANIFEST_NAME).read_bytes())
    document["schema"] = "minekin.p0.evidence.v2"
    (bundle_dir / MANIFEST_NAME).write_text(json.dumps(document))

    with pytest.raises(MinekinError, match="schema is not"):
        verify_bundle(bundle_dir)


def test_an_unknown_result_token_is_refused(bundle_dir: Path) -> None:
    write_bundle(bundle_dir, manifest(), artifacts(), seal=False)
    document = json.loads((bundle_dir / MANIFEST_NAME).read_bytes())
    document["result"] = "PROBABLY_FINE"
    (bundle_dir / MANIFEST_NAME).write_text(json.dumps(document))

    with pytest.raises(MinekinError, match="not a known outcome"):
        verify_bundle(bundle_dir)


def test_the_manifest_document_matches_the_frozen_shape(bundle_dir: Path) -> None:
    written = write_bundle(bundle_dir, manifest(), artifacts())
    document = written.manifest.as_document()

    assert set(document) == {
        "schema",
        "test_run_id",
        "case_id",
        "case_version",
        "result",
        "bundle",
        "environment",
        "world",
        "identity",
        "artifacts",
        "assertions",
    }
    assert set(document["bundle"]) == {  # type: ignore[arg-type]
        "launch_plan_digest",
        "minecraft",
        "server_jar_sha1",
        "loader",
        "fabric_api",
        "bridge_digest",
        "protocol_schema_digest",
    }
    assert document["artifacts"] == [
        ArtifactRecord(path=record.path, sha256=record.sha256, size=record.size).as_document()
        for record in written.manifest.artifacts
    ]
