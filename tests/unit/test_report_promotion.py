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
import shutil
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
from minekin_core.cli.evidence import bundle_directory, repository_bundle_directory
from minekin_core.cli.init import run_root
from minekin_core.domain.cases import (
    REQUIRED_CASES,
    REQUIRED_GATES,
    RequiredCase,
    ValidationClass,
)
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


def seal_at(
    directory: Path,
    *,
    case_id: str = CASE_ID,
    run_id: str = RUN_ID,
    result: EvidenceResult = EvidenceResult.PASS,
    case_version: str | None = None,
    launch_plan_digest: str = DIGEST,
) -> Path:
    """Seal a bundle at an address the caller chooses.

    `run_id` is what the manifest claims, which is deliberately not the
    directory name in the tests about a bundle that names a different run.
    `launch_plan_digest` is which build the run was made from, and the default is
    a digest no build produces so that the tests which do not care about the build
    diagnostic say the same thing as before it existed.
    """

    manifest = manifest_for(
        case_id, result=result, run_id=run_id, launch_plan_digest=launch_plan_digest
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
) -> Path:
    return seal_at(
        bundle_directory(run_root(data_root, KIN), run_id),
        case_id=case_id,
        run_id=run_id,
        result=result,
        case_version=case_version,
        launch_plan_digest=launch_plan_digest,
    )


def test_a_verified_pass_is_what_promotes_a_work_package(tmp_path: Path) -> None:
    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    assert document["status"] == "promotable"
    assert document["work_packages"]["W40"]["promotable"] is True
    assert document["work_packages"]["W40"]["blocking_cases"] == []
    assert document["gated"] == "W40"


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


def test_a_bundle_says_which_build_it_was_sealed_from(tmp_path: Path) -> None:
    """The comparison is against the plan this checkout would launch, measured."""

    build, reason = PROMOTION.repository_build()
    assert build is not None, reason
    seal(tmp_path, RUN_ID, launch_plan_digest=build)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    listed = cast(list[dict[str, Any]], document["evidence"]["bundles"])
    assert listed[0]["launch_plan_digest"] == build
    assert listed[0]["from_repository_build"] is True
    assert document["evidence"]["from_another_build"] == []
    assert document["repository_build"]["plan_sha256"] == build


def test_a_bundle_from_another_build_is_named_rather_than_counted(tmp_path: Path) -> None:
    """Evidence from a build that is not this one is the thing a reader has to see."""

    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path))

    listed = cast(list[dict[str, Any]], document["evidence"]["bundles"])
    assert listed[0]["from_repository_build"] is False
    assert document["evidence"]["from_another_build"] == [RUN_ID]


def test_the_build_diagnostic_does_not_decide_the_verdict(tmp_path: Path) -> None:
    """The whole point of calling it a diagnostic: same evidence, same verdict.

    Asserted as a comparison against the matching case rather than as a fixed
    expected status, so that if promotion ever does start gating on this, the failure
    is here and says which of the two readings changed.
    """

    build, reason = PROMOTION.repository_build()
    assert build is not None, reason
    seal(tmp_path / "same", RUN_ID, launch_plan_digest=build)
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


def test_a_report_that_cannot_build_the_plan_says_so_rather_than_mismatching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unanswerable question is not the answer "came from somewhere else".

    A checkout where the recipe cannot be read has no opinion about which build a
    bundle came from, and reporting a mismatch there would be inventing one. This is
    the same distinction `UNJUDGED` draws about a verdict a reader could not reach.
    """

    def refuse(_path: Path) -> dict[str, Any]:
        raise ValueError("the recipe is not readable in this checkout")

    monkeypatch.setattr(PROMOTION, "build_launch_plan", refuse)
    seal(tmp_path, RUN_ID)

    document = cast(dict[str, Any], bundle_report(CASE_ID, data_root=tmp_path, gated="W40"))

    listed = cast(list[dict[str, Any]], document["evidence"]["bundles"])
    assert document["repository_build"]["readable"] is False
    assert document["repository_build"]["plan_sha256"] is None
    assert "not readable" in cast(str, document["repository_build"]["reason"])
    assert listed[0]["from_repository_build"] is None
    # None is not False, so nothing is claimed to be from another build either.
    assert document["evidence"]["from_another_build"] == []
    assert document["work_packages"]["W40"]["promotable"] is True
