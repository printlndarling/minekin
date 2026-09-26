"""What the evidence on disk lets this repository claim about itself.

The bundles here are written directly rather than produced by a run: the question
is what the report does with a bundle once it exists, and producing one out of a
real session is a separate, slower check. The case identities and versions come
from the reviewed registry, so a test that passes here is one about a case that
exists.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from minekin_core.adapters.evidence.attempt_registry import mark_sealed, reserve_attempt
from minekin_core.adapters.evidence.bundle import unseal_bundle, write_bundle
from minekin_core.adapters.evidence.promotion import load_case_registry
from minekin_core.cli.evidence import (
    attempt_registry_path,
    bundle_directory,
    repository_bundle_directory,
)
from minekin_core.cli.init import run_root
from minekin_core.domain.cases import (
    REQUIRED_CASES,
    REQUIRED_GATES,
    RequiredCase,
    ValidationClass,
)
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.evidence import Assertions, EvidenceManifest, EvidenceResult
from minekin_core.domain.ids import KinId

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPOSITORY_ROOT / "tools" / "report_promotion.py"
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"
KIN = KinId("kin-01")
DIGEST = "a" * 64
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
#: The case every bundle below is sealed for, and so the case the gate requires.
CASE_ID = "CORE-020"


def load_tool() -> ModuleType:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module("tools.report_promotion")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


PROMOTION = load_tool()


def gate_inventory(*case_ids: str) -> tuple[RequiredCase, ...]:
    """An inventory whose gates require exactly these cases and nothing else."""

    entries: list[RequiredCase] = []
    for case_id in case_ids:
        case = reviewed(case_id)
        entries.append(
            RequiredCase(
                case_id,
                case.work_package,
                (case.work_package,),
                ValidationClass.RUNTIME_REQUIRED,
                "docs/nowhere.md",
            )
        )
    return tuple(entries)


def bundle_report(case_id: str, **arguments: Any) -> Any:
    """The report, asked about one bundle rather than about a repository-wide case set.

    A gate is judged against what the inventory requires of it, so a test about what
    the report does with a bundle states the gate too: the case it seals, and nothing
    else. Whether the rest of the contract's case set exists is a separate question,
    and the section at the end of this file is where it is asked.
    """

    return PROMOTION._report_with_inventory(required=gate_inventory(case_id), **arguments)


@pytest.fixture(autouse=True)
def _leave_bundles_writable(tmp_path: Path) -> Iterator[None]:
    yield
    for found in sorted(tmp_path.rglob("manifest.json")):
        unseal_bundle(found.parent)


def reviewed(case_id: str) -> Any:
    return load_case_registry(CASES).by_id()[case_id]


def manifest_for(
    case_id: str,
    *,
    result: EvidenceResult = EvidenceResult.PASS,
    run_id: str = RUN_ID,
    launch_plan_digest: str = DIGEST,
    minecraft: str = "1.21.4",
) -> EvidenceManifest:
    case = reviewed(case_id)
    assertions = Assertions(expected=("a",), observed=("a",), failures=())
    if result is EvidenceResult.FAIL:
        assertions = Assertions(expected=("a",), observed=(), failures=("a:NOT_SEEN",))
    return EvidenceManifest(
        test_run_id=run_id,
        case_id=case.case_id,
        case_version=case.digest,
        result=result,
        launch_plan_digest=launch_plan_digest,
        bridge_digest="c" * 64,
        protocol_schema_digest="d" * 64,
        server_config_digest="e" * 64,
        minecraft=minecraft,
        loader="0.16.9" if minecraft == "1.21.4" else "0.19.5",
        fabric_api="0.119.4+1.21.4" if minecraft == "1.21.4" else "0.92.12+1.20.1",
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


def seal_at(
    directory: Path,
    *,
    case_id: str = CASE_ID,
    run_id: str = RUN_ID,
    result: EvidenceResult = EvidenceResult.PASS,
    case_version: str | None = None,
    launch_plan_digest: str = DIGEST,
    minecraft: str = "1.21.4",
) -> Path:
    """Seal a bundle at an address the caller chooses.

    `run_id` is what the manifest claims, which is deliberately not the
    directory name in the tests about a bundle that names a different run.
    `launch_plan_digest` is which build the run was made from, and the default is
    a digest no build produces so that the tests which do not care about the build
    diagnostic say the same thing as before it existed.
    """

    manifest = manifest_for(
        case_id,
        result=result,
        run_id=run_id,
        launch_plan_digest=launch_plan_digest,
        minecraft=minecraft,
    )
    if case_version is not None:
        manifest = replace(manifest, case_version=case_version)
    write_bundle(directory, manifest, {"server/server.log": b"Kin joined\n"})
    return directory


def seal(
    data_root: Path,
    run_id: str,
    *,
    case_id: str = CASE_ID,
    result: EvidenceResult = EvidenceResult.PASS,
    case_version: str | None = None,
    launch_plan_digest: str = DIGEST,
    minecraft: str = "1.21.4",
) -> Path:
    return seal_at(
        bundle_directory(run_root(data_root, KIN), run_id),
        case_id=case_id,
        run_id=run_id,
        result=result,
        case_version=case_version,
        launch_plan_digest=launch_plan_digest,
        minecraft=minecraft,
    )


def seal_sequenced(
    data_root: Path,
    run_id: str,
    *,
    result: EvidenceResult = EvidenceResult.PASS,
) -> Path:
    attempt = reserve_attempt(attempt_registry_path(data_root), case_id=CASE_ID, run_id=run_id)
    manifest = replace(
        manifest_for(CASE_ID, result=result, run_id=run_id),
        attempt_sequence=attempt.sequence,
        supersedes_run_id=attempt.supersedes_run_id,
    )
    directory = bundle_directory(run_root(data_root, KIN), run_id)
    write_bundle(directory, manifest, {"server/server.log": b"Kin joined\n"})
    mark_sealed(attempt_registry_path(data_root), attempt)
    return directory


def test_a_verified_pass_is_what_promotes_a_work_package(tmp_path: Path) -> None:
    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "promotable"
    assert document["work_packages"]["W40"]["promotable"] is True
    assert document["work_packages"]["W40"]["blocking_cases"] == []
    assert document["gated"] == "W40"


def test_newer_sequenced_fail_blocks_older_sequenced_pass(tmp_path: Path) -> None:
    seal_sequenced(tmp_path, RUN_ID)
    seal_sequenced(tmp_path, "6c1f9a7b2d3e4f6089abcdef01234567", result=EvidenceResult.FAIL)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["work_packages"]["W40"]["blocking_cases"] == [CASE_ID]
    assert "EVIDENCE_IS_NOT_A_PASS" in document["work_packages"]["W40"]["blocks"]


def test_latest_sequenced_pass_promotes_after_older_failure(tmp_path: Path) -> None:
    seal_sequenced(tmp_path, RUN_ID, result=EvidenceResult.FAIL)
    seal_sequenced(tmp_path, "ac1f9a7b2d3e4f6089abcdef01234567")

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "promotable"
    assert document["work_packages"]["W40"]["blocking_cases"] == []


def test_pending_attempt_blocks_legacy_pass_instead_of_falling_back(tmp_path: Path) -> None:
    seal(tmp_path, RUN_ID)
    reserve_attempt(
        attempt_registry_path(tmp_path),
        case_id=CASE_ID,
        run_id="7c1f9a7b2d3e4f6089abcdef01234567",
    )

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["work_packages"]["W40"]["blocking_cases"] == [CASE_ID]


def test_corrupt_latest_bundle_blocks_older_pass(tmp_path: Path) -> None:
    seal_sequenced(tmp_path, RUN_ID)
    latest = seal_sequenced(tmp_path, "8c1f9a7b2d3e4f6089abcdef01234567")
    unseal_bundle(latest)
    (latest / "manifest.json").write_text("not json", encoding="utf-8")

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["work_packages"]["W40"]["blocking_cases"] == [CASE_ID]


def test_missing_latest_bundle_blocks_older_pass(tmp_path: Path) -> None:
    seal_sequenced(tmp_path, RUN_ID)
    latest = seal_sequenced(tmp_path, "ed1f9a7b2d3e4f6089abcdef01234567")
    # Moving a bundle out of its address is a retention operation, and renaming a
    # directory needs write permission on that directory itself — so the seal has
    # to come off first. Windows ignores that (a read-only directory still
    # renames), which is why this only showed up on Linux.
    unseal_bundle(latest)
    latest.rename(tmp_path / "missing-latest")

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["work_packages"]["W40"]["blocking_cases"] == [CASE_ID]


def test_a_lost_latest_attempt_is_named_as_attested_evidence(tmp_path: Path) -> None:
    """The case blocks *and* the report says which attested bundle is not there."""

    seal_sequenced(tmp_path, RUN_ID)
    latest = seal_sequenced(tmp_path, "ed1f9a7b2d3e4f6089abcdef01234567")
    unseal_bundle(latest)
    shutil.rmtree(latest)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["evidence"]["sealed_without_bundle"] == [
        {"case_id": CASE_ID, "run_id": "ed1f9a7b2d3e4f6089abcdef01234567", "sequence": 2}
    ]


def test_a_lost_earlier_attempt_is_named_rather_than_absorbed(tmp_path: Path) -> None:
    """The verdict is the latest attempt's; the retained failure that vanished is not."""

    earlier = seal_sequenced(tmp_path, RUN_ID, result=EvidenceResult.FAIL)
    seal_sequenced(tmp_path, "fd1f9a7b2d3e4f6089abcdef01234567")
    unseal_bundle(earlier)
    shutil.rmtree(earlier)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "promotable"
    assert document["evidence"]["sealed_without_bundle"] == [
        {"case_id": CASE_ID, "run_id": RUN_ID, "sequence": 1}
    ]


def test_retained_earlier_attempt_keeps_the_report_readable(tmp_path: Path) -> None:
    """One setup changed from the refusal above: the bytes are still there."""

    seal_sequenced(tmp_path, RUN_ID, result=EvidenceResult.FAIL)
    seal_sequenced(tmp_path, "fd1f9a7b2d3e4f6089abcdef01234567")

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "promotable"
    assert document["evidence"]["sealed_without_bundle"] == []


def test_unverified_latest_attempt_blocks_older_pass(tmp_path: Path) -> None:
    seal_sequenced(tmp_path, RUN_ID)
    latest = seal_sequenced(tmp_path, "9c1f9a7b2d3e4f6089abcdef01234567")
    unseal_bundle(latest)
    (latest / "server" / "server.log").write_text("tampered\n", encoding="utf-8")

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert "EVIDENCE_NOT_VERIFIED" in document["work_packages"]["W40"]["blocks"]


def test_corrupt_registry_chain_fails_closed(tmp_path: Path) -> None:
    seal_sequenced(tmp_path, RUN_ID)
    database = attempt_registry_path(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE attempts SET supersedes_run_id = 'forged'")

    with pytest.raises(MinekinError, match="supersession chain is corrupt"):
        bundle_report(CASE_ID, data_root=tmp_path, gated="W40")


def test_bundle_registry_supersession_mismatch_fails_closed(tmp_path: Path) -> None:
    seal_sequenced(tmp_path, RUN_ID)
    latest = seal_sequenced(tmp_path, "bc1f9a7b2d3e4f6089abcdef01234567")
    unseal_bundle(latest)
    manifest_path = latest / "manifest.json"
    document = json.loads(manifest_path.read_bytes())
    document["attempt"]["supersedes_run_id"] = "forged-run"
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    manifest_path.write_bytes(payload)
    (latest / "bundle.sha256").write_text(hashlib.sha256(payload).hexdigest() + "\n")

    with pytest.raises(PROMOTION.Unusable, match="disagrees with the attempt registry"):
        bundle_report(CASE_ID, data_root=tmp_path, gated="W40")


def test_sequenced_bundle_without_its_registry_is_unusable(tmp_path: Path) -> None:
    directory = bundle_directory(run_root(tmp_path, KIN), RUN_ID)
    write_bundle(
        directory,
        replace(manifest_for(CASE_ID), attempt_sequence=1),
        {"server/server.log": b"Kin joined\n"},
    )

    with pytest.raises(PROMOTION.Unusable, match="without its attempt registry"):
        bundle_report(CASE_ID, data_root=tmp_path, gated="W40")


def test_the_default_gate_is_every_gate_and_it_names_what_is_missing(tmp_path: Path) -> None:
    """One case in one package is not this repository being tested."""

    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path))
    overall = cast(dict[str, Any], document["overall"])

    assert document["status"] == "blocked"
    assert document["gated"] is None
    assert overall["requirement"]["gates"] == list(REQUIRED_GATES)
    assert overall["requirement"]["satisfied"] is False
    assert {"CORE-001", "HOST-001", "NAV-EXP-010"} <= set(overall["blocking_cases"])
    assert "CASE_WITHOUT_EVIDENCE" in overall["blocks"]
    # The gate that does have evidence is still reported on its own.
    assert set(document["work_packages"]["W40"]["requirement"]["absent"]) < set(
        overall["requirement"]["absent"]
    )


def test_a_tampered_bundle_blocks_and_is_named_rather_than_dropped(tmp_path: Path) -> None:
    directory = seal(tmp_path, RUN_ID)
    unseal_bundle(directory)
    (directory / "server" / "server.log").write_bytes(b"Kin never joined\n")

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["evidence"]["unverified"] == [RUN_ID]
    assert document["work_packages"]["W40"]["blocking_cases"] == ["CORE-020"]
    assert "EVIDENCE_NOT_VERIFIED" in document["work_packages"]["W40"]["blocks"]


def test_evidence_from_a_stale_case_version_does_not_count(tmp_path: Path) -> None:
    """A case that changed is a new case: the old run is not evidence for it."""

    seal(tmp_path, RUN_ID, case_version="0" * 64)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["work_packages"]["W40"]["blocks"] == ["CASE_VERSION_MISMATCH"]


def test_a_failed_run_does_not_block_a_later_pass(tmp_path: Path) -> None:
    """A failing run keeps its evidence, and the repair is a new run."""

    failed_run = "0" * 32
    seal(tmp_path, failed_run, result=EvidenceResult.FAIL)
    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

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

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["evidence"]["unverified"] == []
    assert document["work_packages"]["W40"]["blocks"] == ["EVIDENCE_IS_NOT_A_PASS"]


def test_a_bundle_naming_another_run_is_not_evidence_for_the_name_it_sits_under(
    tmp_path: Path,
) -> None:
    """The directory name is the attribution, so a mismatch is a violation."""

    directory = bundle_directory(run_root(tmp_path, KIN), RUN_ID)
    seal_at(directory, run_id="0" * 32)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert document["evidence"]["unverified"] == [RUN_ID]
    listed = {entry["run_id"]: entry for entry in document["evidence"]["bundles"]}
    assert listed[RUN_ID]["verified"] is False
    assert listed[RUN_ID]["violations"] == ["RUN_ID_MISMATCH"]
    assert document["work_packages"]["W40"]["blocking_cases"] == ["CORE-020"]
    assert document["work_packages"]["W40"]["blocks"] == ["EVIDENCE_NOT_VERIFIED"]


def test_a_mismatch_neither_hides_a_matching_pass_nor_is_hidden_by_it(tmp_path: Path) -> None:
    """A mismatch stays visible without changing the satisfying-candidate rule."""

    stray = "0" * 32
    seal_at(bundle_directory(run_root(tmp_path, KIN), stray), run_id=RUN_ID)
    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["evidence"]["count"] == 2
    assert document["evidence"]["unverified"] == [stray]
    listed = {entry["run_id"]: entry for entry in document["evidence"]["bundles"]}
    assert listed[stray]["result"] == "PASS"
    assert listed[stray]["violations"] == ["RUN_ID_MISMATCH"]
    assert listed[RUN_ID]["verified"] is True
    assert document["work_packages"]["W40"]["promotable"] is True
    assert document["work_packages"]["W40"]["blocks"] == ["EVIDENCE_NOT_VERIFIED"]


@pytest.mark.parametrize("duplicate_in", ["another-kin", "the-repository"])
def test_one_run_id_in_two_roots_is_refused_rather_than_picked_between(
    tmp_path: Path, duplicate_in: str
) -> None:
    """A duplicate run id is an ambiguity, never a last-writer-wins choice."""

    seal(tmp_path, RUN_ID)
    second = (
        bundle_directory(run_root(tmp_path, KinId("kin-02")), RUN_ID)
        if duplicate_in == "another-kin"
        else repository_bundle_directory(tmp_path, RUN_ID)
    )
    seal_at(second)

    with pytest.raises(PROMOTION.Unusable, match=f"{RUN_ID} has bundles in"):
        bundle_report(CASE_ID, data_root=tmp_path, gated="W40")


def test_the_command_refuses_a_run_id_that_appears_twice(tmp_path: Path) -> None:
    seal(tmp_path, RUN_ID)
    seal_at(bundle_directory(run_root(tmp_path, KinId("kin-02")), RUN_ID))

    result = run_cli("--data-root", str(tmp_path), "--work-package", "W40")

    assert result.returncode == PROMOTION.EXIT_UNUSABLE
    assert json.loads(result.stderr)["status"] == "unusable"


def test_an_incomplete_duplicate_run_directory_cannot_hide_beside_a_pass(tmp_path: Path) -> None:
    seal(tmp_path, RUN_ID)
    incomplete = bundle_directory(run_root(tmp_path, KinId("kin-02")), RUN_ID)
    incomplete.mkdir(parents=True)

    with pytest.raises(PROMOTION.Unusable, match=f"{RUN_ID} has bundles in"):
        bundle_report(CASE_ID, data_root=tmp_path, gated="W40")


def test_a_bundle_that_cannot_be_read_is_named(tmp_path: Path) -> None:
    """It is read, it is not skipped, and it is not allowed to look like nothing."""

    directory = bundle_directory(run_root(tmp_path, KIN), RUN_ID)
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text("{ not json", encoding="utf-8")
    (directory / "bundle.sha256").write_text("0" * 64 + "\n", encoding="ascii")

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "blocked"
    assert len(document["evidence"]["unreadable"]) == 1
    assert document["evidence"]["unreadable"][0].startswith(f"{RUN_ID}: ")


def test_unreadable_bundle_without_registry_cannot_hide_after_legacy_pass(tmp_path: Path) -> None:
    seal(tmp_path, RUN_ID)
    unreadable = bundle_directory(run_root(tmp_path, KIN), "dc1f9a7b2d3e4f6089abcdef01234567")
    unreadable.mkdir(parents=True)
    (unreadable / "manifest.json").write_text("not json", encoding="utf-8")
    (unreadable / "bundle.sha256").write_text("0" * 64, encoding="ascii")

    with pytest.raises(PROMOTION.Unusable, match="cannot establish whether unreadable evidence"):
        bundle_report(CASE_ID, data_root=tmp_path, gated="W40")


def test_a_directory_that_is_not_a_bundle_is_not_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "kin" / str(KIN) / "run" / "evidence"
    (evidence / "scratch").mkdir(parents=True)
    (evidence / "scratch" / "notes.txt").write_text("not a bundle", encoding="utf-8")

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["evidence"]["count"] == 0
    assert document["evidence"]["bundles"] == []
    assert document["evidence"]["unreadable"] == []


def test_no_evidence_at_all_still_names_every_missing_case(tmp_path: Path) -> None:
    """That a case has no bundle and that it does not exist are both named, together."""

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path))
    overall = cast(dict[str, Any], document["overall"])
    absent = set(cast(list[str], overall["requirement"]["absent"]))

    assert document["status"] == "blocked"
    assert document["evidence"]["count"] == 0
    assert absent
    assert absent <= set(cast(list[str], overall["blocking_cases"]))
    assert "CASE_WITHOUT_EVIDENCE" in cast(list[str], overall["blocks"])


def test_gating_on_a_name_no_gate_has_is_refused(tmp_path: Path) -> None:
    """`W80` is a work package and not a gate: NAV is graded as `p0-nav-exp`.

    Refused rather than answered as "nothing to gate on", because a gate that does
    not exist has no case set to be complete, and a report that returned one anyway
    would be reporting coverage over a name nothing is filed under.
    """

    with pytest.raises(PROMOTION.Unusable, match="not a gate"):
        bundle_report(CASE_ID, data_root=tmp_path, gated="W99")
    with pytest.raises(PROMOTION.Unusable, match="not a gate"):
        bundle_report(CASE_ID, data_root=tmp_path, gated="W80")


def test_an_unsealed_bundle_is_reported_but_is_not_a_blocker_on_its_own(
    tmp_path: Path,
) -> None:
    """The digest is the guarantee; the mode is a courtesy."""

    directory = seal(tmp_path, RUN_ID)
    unseal_bundle(directory)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

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


def test_the_command_gates_the_evidence_and_the_gate_together(tmp_path: Path) -> None:
    """One sealed, verified, passing bundle is not enough for exit zero any more.

    W40's own mandatory case is satisfied here — the evidence rule has nothing to say
    — and the command still exits blocked, which is what the requirement reading is
    for: the gate requires twelve cases, four of them exist, and "promotable" over
    that would be a sentence about a slice nobody has measured.
    """

    seal(tmp_path, RUN_ID)

    gated = run_cli("--data-root", str(tmp_path), "--work-package", "W40")
    everything = run_cli("--data-root", str(tmp_path))
    document = json.loads(gated.stdout)

    assert gated.returncode == PROMOTION.EXIT_BLOCKED
    assert everything.returncode == PROMOTION.EXIT_BLOCKED
    assert document["status"] == "blocked"
    assert document["work_packages"]["W40"]["promotable"] is False
    assert document["work_packages"]["W40"]["blocks"] == ["REQUIRED_CASE_NOT_REGISTERED"]


def test_the_command_exits_zero_for_a_promotable_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exit-zero path itself, which no gate in this repository reaches yet.

    Left to the day a gate's case set closes, the mapping from a promotable verdict to
    status 0 would be a line nothing had ever run. Pinned against the command's own
    reading of the document instead.
    """

    def promotable(**_arguments: object) -> dict[str, object]:
        return {"schema_version": 1, "status": "promotable"}

    monkeypatch.setattr(PROMOTION, "report", promotable)

    assert PROMOTION.main(["--data-root", "."]) == PROMOTION.EXIT_PROMOTABLE
    assert json.loads(capsys.readouterr().out)["status"] == "promotable"


def test_the_command_refuses_a_package_it_cannot_gate(tmp_path: Path) -> None:
    """`W99` is not a work package and `W80` is not a gate; neither can be asked."""

    result = run_cli("--data-root", str(tmp_path), "--work-package", "W99")

    assert result.returncode == PROMOTION.EXIT_UNUSABLE
    assert json.loads(result.stderr)["status"] == "unusable"


# ---------------------------------------------------------------------------
# The case set a gate is judged against
# ---------------------------------------------------------------------------
#
# Everything above asks what a bundle has to be. These ask the other question, and
# the one the report could not previously answer at all: what each gate requires,
# read against the registry it is judged with.


def test_a_hole_in_another_surface_does_not_block_a_phase(tmp_path: Path) -> None:
    """A gate is judged against its own cases, not against the repository's.

    The host surface and the navigation experiment are far from complete and neither
    is a phase of the core slice. Judged against everything at once, every gate would
    be blocked by whichever surface is least finished, and a per-gate answer would
    stop saying anything about the gate.

    Which case stands for "a hole in W40" is derived rather than named. It was named,
    and the day that case was written this test failed — a pinned example is the same
    staleness the case report was written to stop maintaining by hand, one file over.
    """

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path))
    w40 = cast(dict[str, Any], document["work_packages"]["W40"])
    host = cast(dict[str, Any], document["work_packages"]["host-integrated"])

    missing_from_w40 = set(cast(list[str], w40["requirement"]["absent"]))
    assert missing_from_w40, "this test needs a W40 case the repository does not hold"
    assert {case for case in missing_from_w40 if case.startswith(("HOST", "NAV"))} == set()
    assert "HOST-001" in host["requirement"]["absent"]
    assert "CORE-020" not in host["requirement"]["absent"]


def test_a_gate_whose_cases_are_all_declared_not_to_gate_is_reported_separately(
    tmp_path: Path,
) -> None:
    """Everything present, nothing gating: what an existence check reads as coverage.

    W70 requires five cases and the repository holds all five, so a reading that
    stopped at "is it there" would call this gate satisfied. Every one of them is
    `mandatory: false`, so no evidence rule has anything to ask about — and the gate
    is blocked rather than reported as having nothing to gate on.
    """

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path))
    w70 = cast(dict[str, Any], document["work_packages"]["W70"])

    assert w70["requirement"]["absent"] == []
    assert w70["requirement"]["misattributed"] == []
    assert w70["requirement"]["satisfied"] is True
    assert w70["requirement"]["non_mandatory"] == [
        "CORE-060",
        "CORE-060-CLIENT-001",
        "CORE-060-SERVER-001",
        "CORE-090",
        "CORE-100",
    ]
    assert w70["blocks"] == ["NO_MANDATORY_CASES"]
    assert w70["promotable"] is False


def test_deleting_a_required_case_blocks_only_the_gates_that_require_it(
    tmp_path: Path,
) -> None:
    """The negative mutation, at the report's own level: `W40` and not `W60`."""

    cases = tmp_path / "cases"
    shutil.copytree(CASES, cases)
    (cases / "core-020.json").unlink()
    seal(tmp_path / "data", RUN_ID)

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path / "data", cases_dir=cases))
    packages = cast(dict[str, dict[str, Any]], document["work_packages"])

    assert "CORE-020" in packages["W40"]["requirement"]["absent"]
    assert "CORE-020" not in packages["W60"]["requirement"]["absent"]
    assert packages["W60"]["requirement"]["satisfied"] is True


def test_a_required_case_filed_under_another_work_package_blocks_its_gate(
    tmp_path: Path,
) -> None:
    """A case that moved between gates passes the wrong question, so it blocks."""

    cases = tmp_path / "cases"
    shutil.copytree(CASES, cases)
    fixture = cases / "core-020.json"
    moved = json.loads(fixture.read_text(encoding="utf-8"))
    moved["work_package"] = "W60"
    fixture.write_text(json.dumps(moved, indent=2) + "\n", encoding="utf-8")

    document = cast(dict[str, Any], PROMOTION.report(data_root=tmp_path, cases_dir=cases))
    w40 = cast(dict[str, Any], document["work_packages"]["W40"])

    assert w40["requirement"]["misattributed"] == ["CORE-020"]
    assert "CORE-020" not in w40["requirement"]["absent"]
    assert "REQUIRED_CASE_MISATTRIBUTED" in w40["blocks"]
    assert "CORE-020" in w40["blocking_cases"]


def test_an_inventory_that_cannot_be_read_refuses_rather_than_answering(tmp_path: Path) -> None:
    """Two entries for one case is two answers about what that case requires."""

    with pytest.raises(PROMOTION.Unusable, match="DUPLICATE_CASE_ID"):
        PROMOTION._report_with_inventory(
            data_root=tmp_path, required=(*REQUIRED_CASES, REQUIRED_CASES[0])
        )


def test_an_unknown_required_id_refuses_promotion(tmp_path: Path) -> None:
    unknown = replace(REQUIRED_CASES[0], case_id="CORE-999")

    with pytest.raises(PROMOTION.Unusable, match="UNKNOWN_CASE_ID"):
        PROMOTION._report_with_inventory(data_root=tmp_path, required=(*REQUIRED_CASES, unknown))


def test_the_public_report_does_not_allow_callers_to_replace_the_inventory(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument 'required'"):
        PROMOTION.report(data_root=tmp_path, required=REQUIRED_CASES)


# ---------------------------------------------------------------------------
# Which build the evidence came from
# ---------------------------------------------------------------------------
#
# Every rule above compares a bundle against the *case* it claims and none of them
# asks which *build* the run was made from, so a PASS sealed before a fix satisfies a
# gate for the build on disk today. The report now says which build each bundle came
# from. It does not gate on it: how an earlier build's evidence is superseded is an
# open decision, and a report that enforced one of the answers would be making that
# decision by accident.
#
# And it asks per Minecraft version, because with two reviewed versions on disk one
# plan cannot be the yardstick for both: measuring a 1.20.1 bundle against the
# 1.21.4 plan calls honest evidence stale, and a diagnostic that is confidently wrong
# is worse than one that is missing. That is not hypothetical — the first real 1.20.1
# bundle (run `87229052d24f4772a512dee497bab29c`) was listed under
# `from_another_build` by the single-recipe report.


#: A case that exists on disk for the second reviewed version. Which case is beside
#: the point; what matters is that the report reads the version off the bundle.
CASE_1201 = "V1201-020"
RUN_ID_1201 = "7c1f9a7b2d3e4f6089abcdef01234567"


def plan_of(minecraft: str) -> str:
    """The plan digest this checkout builds for one reviewed version, measured.

    Asserted rather than defaulted: a hardcoded digest here would keep passing after
    the plan moved, which is the very drift this comparison exists to catch.
    """

    for build in PROMOTION.repository_builds():
        if build.minecraft == minecraft:
            assert build.plan_sha256 is not None, build.reason
            return build.plan_sha256
    raise AssertionError(f"no reviewed recipe names Minecraft {minecraft}")


def listed_by_run(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {cast(str, entry["run_id"]): entry for entry in document["evidence"]["bundles"]}


def test_two_versions_are_each_compared_to_their_own_plan(tmp_path: Path) -> None:
    """One bundle per reviewed version, both from the build they name.

    The digests come from this checkout, so this is a comparison against a measured
    plan rather than against a number written into a test.
    """

    build_1214 = plan_of("1.21.4")
    build_1201 = plan_of("1.20.1")
    assert build_1201 != build_1214, "the two versions build one plan, so nothing is compared"
    seal(tmp_path, RUN_ID, launch_plan_digest=build_1214)
    seal(
        tmp_path,
        RUN_ID_1201,
        case_id=CASE_1201,
        minecraft="1.20.1",
        launch_plan_digest=build_1201,
    )

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    listed = listed_by_run(document)
    assert listed[RUN_ID]["minecraft"] == "1.21.4"
    assert listed[RUN_ID]["from_repository_build"] is True
    assert listed[RUN_ID_1201]["minecraft"] == "1.20.1"
    assert listed[RUN_ID_1201]["from_repository_build"] is True
    assert document["evidence"]["from_another_build"] == []
    # And the report says which recipe it measured each version against.
    recipes = cast(list[dict[str, Any]], document["repository_build"]["builds"])
    assert {entry["minecraft"]: entry["plan_sha256"] for entry in recipes} == {
        "1.21.4": build_1214,
        "1.20.1": build_1201,
    }


def test_a_bundle_carries_the_other_version_s_plan_is_called_out(tmp_path: Path) -> None:
    """The forgery direction the per-version comparison makes visible.

    A 1.20.1 bundle that records the 1.21.4 plan digest is not evidence about a
    1.20.1 build, and under the old single-recipe report it read as a perfect match.
    """

    seal(
        tmp_path,
        RUN_ID_1201,
        case_id=CASE_1201,
        minecraft="1.20.1",
        launch_plan_digest=plan_of("1.21.4"),
    )

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    assert listed_by_run(document)[RUN_ID_1201]["from_repository_build"] is False
    assert document["evidence"]["from_another_build"] == [RUN_ID_1201]


def test_a_bundle_from_another_build_is_named_rather_than_counted(tmp_path: Path) -> None:
    """Evidence from a build that is not this one is the thing a reader has to see."""

    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    listed = cast(list[dict[str, Any]], document["evidence"]["bundles"])
    assert listed[0]["from_repository_build"] is False
    assert document["evidence"]["from_another_build"] == [RUN_ID]


def test_a_version_with_no_recipe_here_is_not_called_foreign(tmp_path: Path) -> None:
    """A question this checkout cannot ask is not the answer "came from elsewhere".

    Nothing here has a reviewed recipe for 1.19.2, so the report has no plan to
    compare such a bundle against — and `None`, unlike `False`, keeps it out of the
    stale list.
    """

    seal(tmp_path, RUN_ID, minecraft="1.19.2")

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    assert listed_by_run(document)[RUN_ID]["from_repository_build"] is None
    assert document["evidence"]["from_another_build"] == []


def test_the_build_diagnostic_does_not_decide_the_verdict(tmp_path: Path) -> None:
    """The whole point of calling it a diagnostic: same evidence, same verdict.

    Asserted as a comparison against the matching case rather than as a fixed
    expected status, so that if promotion ever does start gating on this, the failure
    is here and says which of the two readings changed.
    """

    seal(tmp_path / "same", RUN_ID, launch_plan_digest=plan_of("1.21.4"))
    seal(tmp_path / "other", RUN_ID)

    matching = cast(
        dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path / "same", gated="W40")
    )
    stale = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path / "other", gated="W40"))

    assert matching["status"] == stale["status"] == "promotable"
    assert matching["work_packages"]["W40"]["promotable"] is True
    assert stale["work_packages"]["W40"]["promotable"] is True
    assert stale["evidence"]["from_another_build"] == [RUN_ID]
    # And the report says, in the document, that this reading decided none of it.
    assert stale["repository_build"]["gates_promotion"] is False


def test_a_report_that_cannot_build_one_version_s_plan_says_so_rather_than_mismatching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unanswerable question is not the answer "came from somewhere else".

    Only the 1.20.1 recipe is unreadable here, and that shape is the point: the
    per-version reading survives the failure, so the 1.21.4 bundle is still compared
    and the 1.20.1 bundle is answered with `None`. This is the same distinction
    `UNJUDGED` draws about a verdict a reader could not reach.
    """

    real = PROMOTION.build_launch_plan

    def refuse_one_version(path: Path, **arguments: Any) -> dict[str, Any]:
        if "1.20.1" in str(path):
            raise ValueError("the recipe is not readable in this checkout")
        return real(path, **arguments)

    # Both digests are measured before the refusal is in place: sealing a bundle
    # with a digest is the point, and a bundle cannot be sealed with an answer the
    # report is no longer able to give.
    build_1214 = plan_of("1.21.4")
    build_1201 = plan_of("1.20.1")
    monkeypatch.setattr(PROMOTION, "build_launch_plan", refuse_one_version)
    seal(tmp_path, RUN_ID, launch_plan_digest=build_1214)
    seal(
        tmp_path,
        RUN_ID_1201,
        case_id=CASE_1201,
        minecraft="1.20.1",
        launch_plan_digest=build_1201,
    )

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    recipes = cast(list[dict[str, Any]], document["repository_build"]["builds"])
    by_version = {cast(str, entry["minecraft"]): entry for entry in recipes}
    assert by_version["1.20.1"]["readable"] is False
    assert by_version["1.20.1"]["plan_sha256"] is None
    assert "not readable" in cast(str, by_version["1.20.1"]["reason"])
    assert by_version["1.21.4"]["readable"] is True
    assert document["repository_build"]["unreadable"] == ["1.20.1"]

    listed = listed_by_run(document)
    assert listed[RUN_ID]["from_repository_build"] is True
    assert listed[RUN_ID_1201]["from_repository_build"] is None
    # None is not False, so the bundle with no answer is not claimed stale either.
    assert document["evidence"]["from_another_build"] == []
    assert document["work_packages"]["W40"]["promotable"] is True


#: ---------------------------------------------------------------------------
#: Which interpreter a repository check recorded as having run it.
#: ---------------------------------------------------------------------------

CONTROLLED = "/opt/minekin/bin/python3"
#: One developer's virtualenv on a Windows host — the shape that produced five
#: false FAILs from a missing module before the image carried a pinned pytest.
HOST_VENV = r"C:\Users\darling\Documents\agent_work\minekin\.venv\Scripts\python.exe"


def seal_repo_check(
    data_root: Path,
    run_id: str,
    *,
    case_id: str = CASE_ID,
    interpreters: tuple[str, ...] = (CONTROLLED,),
    verdict_bytes: bytes | None = None,
) -> Path:
    """Seal a repository-check bundle, naming who each check says ran it.

    The recorded command is the runner's own `argv` for one assertion, so the
    interpreter is `command[0]`; `verdict_bytes` replaces the whole document to ask
    about one that cannot be read.
    """

    verdict = {
        "schema_version": 1,
        "command": "run repo case",
        "run_id": run_id,
        "case_id": case_id,
        "result": "PASS",
        "checks": [
            {"name": f"check-{index}", "command": [python, "-m", "pytest", "-q", "t.py::x"]}
            for index, python in enumerate(interpreters)
        ],
    }
    directory = repository_bundle_directory(data_root, run_id)
    write_bundle(
        directory,
        manifest_for(case_id, run_id=run_id, launch_plan_digest=plan_of("1.21.4")),
        {
            "check-verdict.json": (
                json.dumps(verdict).encode("utf-8") if verdict_bytes is None else verdict_bytes
            )
        },
    )
    return directory


def named_runs(document: dict[str, Any]) -> list[str]:
    return cast(
        "list[str]", document["evidence"]["repo_checks_not_from_the_controlled_interpreter"]
    )


def test_the_controlled_interpreter_is_the_one_the_image_builds(tmp_path: Path) -> None:
    """The constant this report compares against comes from the runner's contract.

    Read from `test-orchestrator/runner/Dockerfile` rather than restated: if the
    image moves its venv, every sealed bundle's provenance reading moves with it, and
    this is where that has to fail loudly instead of quietly mislabelling evidence.
    """

    dockerfile = (REPOSITORY_ROOT / "test-orchestrator" / "runner" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "python3 -m venv /opt/minekin" in dockerfile
    assert PROMOTION.CONTROLLED_CHECK_INTERPRETER == CONTROLLED
    assert CONTROLLED.startswith("/opt/minekin/bin/")


def test_a_check_recorded_by_the_controlled_interpreter_is_not_named(tmp_path: Path) -> None:
    seal_repo_check(tmp_path, RUN_ID, interpreters=(CONTROLLED,))

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    assert document["evidence"]["controlled_check_interpreter"] == CONTROLLED
    assert listed_by_run(document)[RUN_ID]["check_interpreters"] == [CONTROLLED]
    assert named_runs(document) == []


def test_a_check_recorded_by_a_host_virtualenv_is_named(tmp_path: Path) -> None:
    seal_repo_check(tmp_path, RUN_ID, interpreters=(HOST_VENV,))

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    assert listed_by_run(document)[RUN_ID]["check_interpreters"] == [HOST_VENV]
    assert named_runs(document) == [RUN_ID]


def test_an_alias_of_the_controlled_interpreter_is_named(tmp_path: Path) -> None:
    """A spelling that is not the pinned one is named, and that direction is chosen.

    Inside one venv `python` and `python3` are the same toolchain under two names, so
    this cannot be both reader-independent and silent about aliases. Naming is the
    safe half: the reader sees a question and the bundle's own record answers it.
    """

    seal_repo_check(tmp_path, RUN_ID, interpreters=("/opt/minekin/bin/python",))

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    assert named_runs(document) == [RUN_ID]


def test_a_run_bundle_records_no_check_interpreter(tmp_path: Path) -> None:
    """A session bundle has no `check-verdict.json`, so it cannot be named for one.

    Without this the list is just "every bundle", and a reader cannot tell the field
    apart from an accident of the loop that fills it.
    """

    seal(tmp_path, RUN_ID, launch_plan_digest=plan_of("1.21.4"))

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    assert listed_by_run(document)[RUN_ID]["check_interpreters"] == []
    assert named_runs(document) == []


def test_two_checks_recorded_under_two_interpreters_are_both_named(tmp_path: Path) -> None:
    seal_repo_check(tmp_path, RUN_ID, interpreters=(CONTROLLED, HOST_VENV))

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    assert listed_by_run(document)[RUN_ID]["check_interpreters"] == sorted(
        [CONTROLLED, HOST_VENV],
        key=os.path.normcase,
    )
    assert named_runs(document) == [RUN_ID]


def test_a_check_verdict_that_cannot_be_read_records_nothing(tmp_path: Path) -> None:
    """An artifact this reading cannot parse is a gap in the reading, not a finding.

    It is not the answer "ran somewhere else" either, so the bundle stays out of the
    list — the same distinction `None` draws for a version with no recipe here.
    """

    seal_repo_check(
        tmp_path,
        RUN_ID,
        verdict_bytes=b'{"result": "PASS"}',
    )

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    assert listed_by_run(document)[RUN_ID]["check_interpreters"] == []
    assert named_runs(document) == []
    assert document["status"] == "promotable"


def test_the_interpreter_diagnostic_does_not_decide_the_verdict(tmp_path: Path) -> None:
    """One bundle, two recorded interpreters, one verdict — and the difference named.

    Compared rather than asserted against a fixed status, as the build diagnostic
    is: if this reading ever starts gating, that failure is here.
    """

    here = seal_repo_check(tmp_path / "here", RUN_ID, interpreters=(CONTROLLED,))
    there = seal_repo_check(tmp_path / "there", RUN_ID, interpreters=(HOST_VENV,))
    assert here.name == there.name

    here_report = cast(
        dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path / "here", gated="W40")
    )
    there_report = cast(
        dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path / "there", gated="W40")
    )

    assert here_report["status"] == there_report["status"] == "promotable"
    assert named_runs(here_report) == []
    assert named_runs(there_report) == [RUN_ID]


# ---------------------------------------------------------------------------
# What no bundle can say about the script that ran it
# ---------------------------------------------------------------------------
#
# `orchestrator-trace.json` records its `orchestrator` field as the fixed path
# string `test-orchestrator/runner/domain.sh` — `orchestrator_trace()` in
# tools/seal_run_evidence.py — with no version or digest beside it, and the
# artifact set is collected entry by entry, so nothing else in a bundle holds
# that script's bytes. Whether two runs used the same revision of it is not
# readable from a bundle by construction. The report now says so on its own
# surface, as a statement beside the gate payload and never as a block inside
# it: nothing about the evidence on disk moved, and a known limit of the seal
# format is not a finding about a bundle.


def test_the_report_names_the_orchestrator_revision_visibility_gap(tmp_path: Path) -> None:
    """The gap is a named sibling of `work_packages`/`overall`, not a blocker."""

    seal(tmp_path, RUN_ID, launch_plan_digest=plan_of("1.21.4"))

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    gaps = cast(list[dict[str, Any]], document["visibility_gaps"])
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap["artifact"] == "orchestrator-trace.json"
    assert gap["field"] == "orchestrator"
    assert "domain.sh" in cast(str, gap["statement"])
    assert gap["gates_promotion"] is False

    # A statement, not a block: it never enters the payload the gate is read from.
    payload = json.dumps(
        {"work_packages": document["work_packages"], "overall": document["overall"]},
        sort_keys=True,
    )
    assert cast(str, gap["id"]) not in payload
    assert "domain.sh" not in payload
    assert "orchestrator" not in payload
    assert document["work_packages"]["W40"]["blocks"] == []
    assert document["work_packages"]["W40"]["promotable"] is True
    assert document["status"] == "promotable"
