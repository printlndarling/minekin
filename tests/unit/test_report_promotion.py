"""What the evidence on disk lets this repository claim about itself.

The bundles here are written directly rather than produced by a run: the question
is what the report does with a bundle once it exists, and producing one out of a
real session is a separate, slower check. The case identities and versions come
from the reviewed registry, so a test that passes here is one about a case that
exists.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from minekin_core.adapters.evidence.bundle import unseal_bundle, write_bundle
from minekin_core.adapters.evidence.promotion import load_case_registry
from minekin_core.cli.evidence import bundle_directory
from minekin_core.cli.init import run_root
from minekin_core.domain.evidence import Assertions, EvidenceManifest, EvidenceResult
from minekin_core.domain.ids import KinId

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPOSITORY_ROOT / "tools" / "report_promotion.py"
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"
KIN = KinId("kin-01")
DIGEST = "a" * 64
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"


def load_tool() -> ModuleType:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module("tools.report_promotion")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


PROMOTION = load_tool()


@pytest.fixture(autouse=True)
def _leave_bundles_writable(tmp_path: Path) -> Iterator[None]:
    yield
    for found in sorted(tmp_path.rglob("manifest.json")):
        unseal_bundle(found.parent)


def reviewed(case_id: str) -> Any:
    return load_case_registry(CASES).by_id()[case_id]


def manifest_for(case_id: str, *, result: EvidenceResult = EvidenceResult.PASS) -> EvidenceManifest:
    case = reviewed(case_id)
    assertions = Assertions(expected=("a",), observed=("a",), failures=())
    if result is EvidenceResult.FAIL:
        assertions = Assertions(expected=("a",), observed=(), failures=("a:NOT_SEEN",))
    return EvidenceManifest(
        test_run_id=RUN_ID,
        case_id=case.case_id,
        case_version=case.digest,
        result=result,
        launch_plan_digest=DIGEST,
        bridge_digest="c" * 64,
        protocol_schema_digest="d" * 64,
        server_config_digest="e" * 64,
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
    )


def seal(
    data_root: Path,
    run_id: str,
    *,
    case_id: str = "CORE-020",
    result: EvidenceResult = EvidenceResult.PASS,
    case_version: str | None = None,
) -> Path:
    directory = bundle_directory(run_root(data_root, KIN), run_id)
    manifest = manifest_for(case_id, result=result)
    if case_version is not None:
        manifest = replace(manifest, case_version=case_version)
    write_bundle(directory, manifest, {"server/server.log": b"Kin joined\n"})
    return directory


def test_a_verified_pass_is_what_promotes_a_work_package(tmp_path: Path) -> None:
    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path, gated="W40"))

    assert document["status"] == "promotable"
    assert document["work_packages"]["W40"]["promotable"] is True
    assert document["work_packages"]["W40"]["blocking_cases"] == []
    assert document["gated"] == "W40"


def test_everything_is_gated_on_by_default_and_the_missing_cases_are_named(
    tmp_path: Path,
) -> None:
    """One case in one package is not this repository being tested."""

    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path))

    assert document["status"] == "blocked"
    assert document["gated"] is None
    # Named in the registry's own order, which is the order of the files.
    assert sorted(document["overall"]["blocking_cases"]) == [
        "CORE-010",
        "CORE-040",
        "CORE-050",
        "CORE-070",
        "W00-CONTRACT-001",
    ]
    assert document["overall"]["blocks"] == ["CASE_WITHOUT_EVIDENCE"]
    # The package that does have evidence is still reported as promotable.
    assert document["work_packages"]["W40"]["promotable"] is True


def test_a_tampered_bundle_blocks_and_is_named_rather_than_dropped(tmp_path: Path) -> None:
    directory = seal(tmp_path, RUN_ID)
    unseal_bundle(directory)
    (directory / "server" / "server.log").write_bytes(b"Kin never joined\n")

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["evidence"]["unverified"] == [RUN_ID]
    assert document["work_packages"]["W40"]["blocking_cases"] == ["CORE-020"]
    assert "EVIDENCE_NOT_VERIFIED" in document["work_packages"]["W40"]["blocks"]


def test_evidence_from_a_stale_case_version_does_not_count(tmp_path: Path) -> None:
    """A case that changed is a new case: the old run is not evidence for it."""

    seal(tmp_path, RUN_ID, case_version="0" * 64)

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["work_packages"]["W40"]["blocks"] == ["CASE_VERSION_MISMATCH"]


def test_a_failed_run_does_not_block_a_later_pass(tmp_path: Path) -> None:
    """A failing run keeps its evidence, and the repair is a new run."""

    failed_run = "0" * 32
    seal(tmp_path, failed_run, result=EvidenceResult.FAIL)
    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path, gated="W40"))

    assert document["evidence"]["count"] == 2
    assert document["status"] == "promotable"
    # `blocks` is a set over every candidate for the case, so a package that is
    # promotable still lists the reason an earlier run gave. The listing is what
    # makes that readable: the reason has an owner, and the owner is named.
    assert document["work_packages"]["W40"]["promotable"] is True
    assert document["work_packages"]["W40"]["blocks"] == ["EVIDENCE_IS_NOT_A_PASS"]
    listed = {entry["run_id"]: entry for entry in document["evidence"]["bundles"]}
    assert listed[failed_run]["result"] == "FAIL"
    assert listed[RUN_ID]["result"] == "PASS"
    assert all(entry["verified"] for entry in listed.values())


def test_a_failure_alone_is_not_a_pass(tmp_path: Path) -> None:
    seal(tmp_path, RUN_ID, result=EvidenceResult.FAIL)

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["evidence"]["unverified"] == []
    assert document["work_packages"]["W40"]["blocks"] == ["EVIDENCE_IS_NOT_A_PASS"]


def test_a_bundle_that_cannot_be_read_is_named(tmp_path: Path) -> None:
    """It is read, it is not skipped, and it is not allowed to look like nothing."""

    directory = bundle_directory(run_root(tmp_path, KIN), RUN_ID)
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text("{ not json", encoding="utf-8")
    (directory / "bundle.sha256").write_text("0" * 64 + "\n", encoding="ascii")

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert len(document["evidence"]["unreadable"]) == 1
    assert document["evidence"]["unreadable"][0].startswith(f"{RUN_ID}: ")


def test_a_directory_that_is_not_a_bundle_is_not_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "kin" / str(KIN) / "run" / "evidence"
    (evidence / "scratch").mkdir(parents=True)
    (evidence / "scratch" / "notes.txt").write_text("not a bundle", encoding="utf-8")

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path, gated="W40"))

    assert document["evidence"]["count"] == 0
    assert document["evidence"]["bundles"] == []
    assert document["evidence"]["unreadable"] == []


def test_no_evidence_at_all_names_the_cases_that_are_missing(tmp_path: Path) -> None:
    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path))

    assert document["status"] == "blocked"
    assert document["evidence"]["count"] == 0
    assert sorted(document["overall"]["blocking_cases"]) == [
        "CORE-010",
        "CORE-020",
        "CORE-040",
        "CORE-050",
        "CORE-070",
        "W00-CONTRACT-001",
    ]


def test_gating_on_a_package_with_no_cases_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PROMOTION.Unusable, match="no mandatory case for W99"):
        PROMOTION.report(data_root=tmp_path, gated="W99")


def test_an_unsealed_bundle_is_reported_but_is_not_a_blocker_on_its_own(
    tmp_path: Path,
) -> None:
    """The digest is the guarantee; the mode is a courtesy."""

    directory = seal(tmp_path, RUN_ID)
    unseal_bundle(directory)

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path, gated="W40"))

    assert document["evidence"]["unsealed"] == [RUN_ID]
    assert document["status"] == "promotable"


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_the_command_exits_zero_only_when_the_gate_is_met(tmp_path: Path) -> None:
    seal(tmp_path, RUN_ID)

    promotable = run_cli("--data-root", str(tmp_path), "--work-package", "W40")
    blocked = run_cli("--data-root", str(tmp_path))

    assert promotable.returncode == PROMOTION.EXIT_PROMOTABLE
    assert json.loads(promotable.stdout)["status"] == "promotable"
    assert blocked.returncode == PROMOTION.EXIT_BLOCKED
    assert json.loads(blocked.stdout)["status"] == "blocked"


def test_the_command_refuses_a_package_it_cannot_gate(tmp_path: Path) -> None:
    result = run_cli("--data-root", str(tmp_path), "--work-package", "W99")

    assert result.returncode == PROMOTION.EXIT_UNUSABLE
    assert json.loads(result.stderr)["status"] == "unusable"
