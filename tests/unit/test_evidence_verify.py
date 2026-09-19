"""Naming one run's evidence, and checking it without being the one who ran it.

The layout is written out literally in this file rather than built from the
module's own helpers. A test that asked the helper where a bundle lives would
agree with whatever address the helper produced, including a wrong one; the
point of pinning a convention is that it is written down twice, in two places
that have to be changed together.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from minekin_core.adapters.evidence.bundle import (
    DIGEST_NAME,
    MANIFEST_NAME,
    unseal_bundle,
    write_bundle,
)
from minekin_core.bootstrap import run
from minekin_core.cli.evidence import (
    RUN_ID_MISMATCH,
    bundle_directory,
    locate_bundle,
    repository_bundle_directory,
    verify_run,
)
from minekin_core.cli.init import run_root
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError
from minekin_core.domain.evidence import Assertions, EvidenceManifest, EvidenceResult
from minekin_core.domain.ids import KinId

RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
KIN = KinId("kin-01")
OTHER_KIN = KinId("kin-02")
DIGEST = "a" * 64


def manifest(run_id: str = RUN_ID) -> EvidenceManifest:
    return EvidenceManifest(
        test_run_id=run_id,
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


def artifacts() -> dict[str, bytes]:
    return {
        "bridge-trace.jsonl": b'{"event":"join"}\n',
        "server-truth.txt": b"Kin joined\n",
    }


def literal_bundle(root: Path, kin: KinId, run_id: str) -> Path:
    """The address, spelled out: `kin/<kin>/run/evidence/<run-id>/`."""

    return root / "kin" / str(kin) / "run" / "evidence" / run_id


def seal(root: Path, kin: KinId, run_id: str = RUN_ID, **overrides: object) -> Path:
    directory = literal_bundle(root, kin, run_id)
    write_bundle(directory, replace(manifest(run_id), **overrides), artifacts())
    return directory


@pytest.fixture(autouse=True)
def _leave_bundles_writable(tmp_path: Path) -> Iterator[None]:
    """A sealed bundle is read-only, and the read-only bit stops cleanup."""

    yield
    for found in sorted(tmp_path.rglob(MANIFEST_NAME)):
        unseal_bundle(found.parent)


def test_the_sealing_address_and_the_searching_address_are_the_same(tmp_path: Path) -> None:
    assert bundle_directory(run_root(tmp_path, KIN), RUN_ID) == literal_bundle(
        tmp_path, KIN, RUN_ID
    )


def test_a_repository_check_seals_beside_the_kins_and_not_inside_one(tmp_path: Path) -> None:
    """A check of the repository belongs to no Kin, and naming one would be a lie."""

    assert repository_bundle_directory(tmp_path, RUN_ID) == (tmp_path / "repo-evidence" / RUN_ID)


def test_a_repository_check_is_found_by_the_same_search_as_a_run(tmp_path: Path) -> None:
    directory = repository_bundle_directory(tmp_path, RUN_ID)
    write_bundle(directory, manifest(), artifacts())

    assert verify_run(tmp_path, RUN_ID).verified
    assert locate_bundle(tmp_path, RUN_ID) == directory


def test_the_same_run_id_in_both_places_is_still_refused(tmp_path: Path) -> None:
    """The rule is about the name, not about who wrote the bundle."""

    seal(tmp_path, KIN)
    write_bundle(repository_bundle_directory(tmp_path, RUN_ID), manifest(), artifacts())

    with pytest.raises(MinekinError) as raised:
        locate_bundle(tmp_path, RUN_ID)

    assert "2 bundles" in raised.value.safe_message


def test_a_sealed_bundle_is_found_by_its_run_id_and_verifies(tmp_path: Path) -> None:
    directory = seal(tmp_path, KIN)

    verification = verify_run(tmp_path, RUN_ID)

    assert verification.verified
    assert verification.violations == ()
    assert verification.run_id == RUN_ID
    assert verification.directory == str(directory)
    assert verification.result == EvidenceResult.PASS.value
    assert verification.artifacts == len(artifacts())
    assert verification.sealed
    assert verification.bundle_digest == _manifest_digest(directory)


def _manifest_digest(directory: Path) -> str:
    """What the bundle says its digest is, read from the bundle itself."""

    return (directory / DIGEST_NAME).read_text(encoding="ascii").strip()


def test_the_directory_name_is_the_attribution_so_a_mismatch_is_a_violation(
    tmp_path: Path,
) -> None:
    """A bundle that names a different run is that run's evidence, not this one's."""

    seal(tmp_path, KIN, test_run_id="0" * 32)

    verification = verify_run(tmp_path, RUN_ID)

    assert not verification.verified
    assert verification.violations == (RUN_ID_MISMATCH,)


def test_a_tampered_artifact_is_caught(tmp_path: Path) -> None:
    directory = seal(tmp_path, KIN)
    unseal_bundle(directory)
    (directory / "server-truth.txt").write_bytes(b"Kin never joined\n")

    verification = verify_run(tmp_path, RUN_ID)

    assert not verification.verified
    assert verification.violations == ("ARTIFACT_DIGEST_MISMATCH:server-truth.txt",)


def test_a_file_the_manifest_never_declared_is_caught(tmp_path: Path) -> None:
    directory = seal(tmp_path, KIN)
    unseal_bundle(directory)
    (directory / "extra.txt").write_bytes(b"")
    (directory / "sub").mkdir()
    (directory / "sub" / "deeper.txt").write_bytes(b"")

    verification = verify_run(tmp_path, RUN_ID)

    assert not verification.verified
    assert verification.violations == (
        "UNDECLARED_FILE:extra.txt",
        "UNDECLARED_FILE:sub/deeper.txt",
    )


def test_a_run_id_that_answers_to_nothing_refuses_by_name(tmp_path: Path) -> None:
    with pytest.raises(MinekinError) as raised:
        locate_bundle(tmp_path, RUN_ID)

    assert raised.value.category is ErrorCategory.CONFIG
    assert RUN_ID in raised.value.safe_message
    assert str(tmp_path) in raised.value.safe_message


def test_a_directory_that_is_not_a_bundle_is_a_failed_verification(tmp_path: Path) -> None:
    """There is evidence here and it is not evidence, which is not a usage error."""

    literal_bundle(tmp_path, KIN, RUN_ID).mkdir(parents=True)

    with pytest.raises(MinekinError) as raised:
        verify_run(tmp_path, RUN_ID)

    assert raised.value.category is ErrorCategory.STORAGE


@pytest.mark.parametrize("run_id", ["../escape", "a/b", ".hidden", "", "run id"])
def test_a_run_id_that_is_not_an_identifier_never_becomes_a_path(
    tmp_path: Path, run_id: str
) -> None:
    with pytest.raises(MinekinError) as raised:
        verify_run(tmp_path, run_id)

    assert raised.value.category is ErrorCategory.CONFIG
    assert raised.value.safe_message.endswith("is not a usable run id")


def test_a_bundle_under_any_kin_is_found_without_being_told_which(tmp_path: Path) -> None:
    """The person checking a bundle is usually not the person who ran it."""

    seal(tmp_path, OTHER_KIN)

    assert verify_run(tmp_path, RUN_ID).verified
    assert locate_bundle(tmp_path, RUN_ID) == literal_bundle(tmp_path, OTHER_KIN, RUN_ID)


def test_two_bundles_for_one_run_id_refuse_to_be_guessed_between(tmp_path: Path) -> None:
    seal(tmp_path, KIN)
    seal(tmp_path, OTHER_KIN)

    with pytest.raises(MinekinError) as raised:
        locate_bundle(tmp_path, RUN_ID)

    assert raised.value.category is ErrorCategory.CONFIG
    assert "2 bundles" in raised.value.safe_message


def test_a_kin_directory_that_never_existed_is_not_a_bundle_location(tmp_path: Path) -> None:
    """A data root with no Kin is empty evidence, not an error about the root."""

    with pytest.raises(MinekinError) as raised:
        locate_bundle(tmp_path, RUN_ID)

    assert raised.value.category is ErrorCategory.CONFIG


def _verify_via_cli(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, dict[str, object], str]:
    monkeypatch.setenv("MINEKIN_HOME", str(root))
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run(["evidence", "verify", RUN_ID], stdout=stdout, stderr=stderr)
    return code, json.loads(stdout.getvalue()), stderr.getvalue()


def test_the_command_prints_the_bundle_and_the_digest_it_holds_up_against(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = seal(tmp_path, KIN)

    code, report, stderr = _verify_via_cli(tmp_path, monkeypatch)

    assert code == int(ExitCode.OK)
    assert stderr == ""
    assert report["command"] == "evidence verify"
    assert report["status"] == "verified"
    assert report["verified"] is True
    assert report["evidence_directory"] == str(directory)
    assert report["bundle_digest"] == _manifest_digest(directory)
    assert report["violations"] == []


def test_the_command_exits_storage_when_the_bundle_does_not_hold_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = seal(tmp_path, KIN)
    unseal_bundle(directory)
    (directory / "server-truth.txt").write_bytes(b"Kin never joined\n")

    code, report, _ = _verify_via_cli(tmp_path, monkeypatch)

    assert code == int(ExitCode.STORAGE)
    assert report["status"] == "invalid"
    assert report["verified"] is False
    assert report["violations"] == ["ARTIFACT_DIGEST_MISMATCH:server-truth.txt"]


def _fingerprint(directory: Path) -> list[tuple[str, int, int]]:
    return [
        (
            path.relative_to(directory).as_posix(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]


@pytest.mark.parametrize("tamper", [False, True])
def test_verifying_writes_nothing_and_leaves_the_bundle_sealed(
    tmp_path: Path, tamper: bool
) -> None:
    """A verifier that could write is a verifier that could repair."""

    directory = seal(tmp_path, KIN)
    if tamper:
        unseal_bundle(directory)
        (directory / "server-truth.txt").write_bytes(b"Kin never joined\n")

    before = _fingerprint(directory)
    verification = verify_run(tmp_path, RUN_ID)
    after = _fingerprint(directory)

    assert after == before
    assert verification.sealed is not tamper
