"""Sealing a repository check: the bundle, and that it promotes its case.

The verdict here is a document rather than a freshly run check, because what is
under test is what the sealer does with one. Running the checks is
`test_run_repo_case.py`'s job, and the container check is the one that does both
against the real repository.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from minekin_core.adapters.evidence.bundle import unseal_bundle, verify_bundle
from minekin_core.cli.evidence import repository_bundle_directory
from minekin_core.domain.evidence import EMPTY_DOCUMENT_SHA256, NO_WORLD

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROFILE = REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"
CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "w00-contract-001.json"
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
ASSERTIONS = (
    "schemas_are_versioned",
    "fixture_digests_match_manifest",
    "runtime_input_does_not_reference_oracle",
    "product_package_does_not_import_test_orchestrator",
)


def load(name: str) -> ModuleType:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module(f"tools.{name}")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


SEALER = load("seal_repo_case")
PROMOTION = load("report_promotion")


@pytest.fixture(autouse=True)
def _leave_bundles_writable(tmp_path: Path) -> Iterator[None]:
    yield
    for found in sorted(tmp_path.rglob("manifest.json")):
        unseal_bundle(found.parent)


def verdict_document(
    *, result: str = "PASS", failures: tuple[str, ...] = (), run_id: str = RUN_ID
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "command": "run repo case",
        "case_id": "W00-CONTRACT-001",
        "run_id": run_id,
        "result": result,
        "expected": list(ASSERTIONS),
        "observed": [] if failures else list(ASSERTIONS),
        "failures": list(failures),
        "unimplemented": [],
        "checks": [
            {
                "name": name,
                "kind": "pytest",
                "target": f"tests/contract/test_fixture_boundaries.py::{name}",
                "command": ["python", "-m", "pytest", name],
                "exit_code": 1 if name in " ".join(failures) else 0,
                "held": name not in " ".join(failures),
                "detail": "",
                "output": None,
            }
            for name in ASSERTIONS
        ],
    }


@pytest.fixture
def checked(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A data root, a verdict, and the directory the check's outputs went to."""

    data_root = tmp_path / "data"
    path = tmp_path / "verdict.json"
    path.write_text(json.dumps(verdict_document()), encoding="utf-8")
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "schemas_are_versioned.log").write_text("4 passed\n", encoding="utf-8")
    return data_root, path, outputs


def seal_it(
    data_root: Path, verdict: Path, outputs: Path | None, **overrides: object
) -> dict[str, object]:
    arguments: dict[str, object] = {
        "data_root": data_root,
        "case": CASE,
        "profile": PROFILE,
        "verdict_path": verdict,
        "output_directory": outputs,
        "workspace_root": REPOSITORY_ROOT,
        "renderer_display": "llvmpipe (LLVM 20.1.2, 256 bits)",
    }
    arguments.update(overrides)
    return cast(dict[str, object], SEALER.seal(**arguments))


def test_a_repository_check_seals_beside_the_kins_and_verifies(
    checked: tuple[Path, Path, Path],
) -> None:
    data_root, verdict, outputs = checked

    report = seal_it(data_root, verdict, outputs)

    directory = repository_bundle_directory(data_root, RUN_ID)
    assert report["status"] == "sealed"
    assert report["result"] == "PASS"
    assert report["evidence_directory"] == str(directory)
    verification = verify_bundle(directory)
    assert verification.verified
    assert verification.sealed


def test_the_manifest_records_that_no_world_was_involved(
    checked: tuple[Path, Path, Path],
) -> None:
    """The same "none" record a run with no world writes, for the same reason."""

    data_root, verdict, outputs = checked

    seal_it(data_root, verdict, outputs)

    manifest = json.loads(
        (repository_bundle_directory(data_root, RUN_ID) / "manifest.json").read_bytes()
    )
    assert manifest["world"] == {
        "kind": NO_WORLD,
        "server_config_digest": EMPTY_DOCUMENT_SHA256,
        "seed_or_snapshot_id": NO_WORLD,
    }
    assert manifest["bundle"]["server_jar_sha1"] == ""
    assert manifest["identity"]["server_observed_name_uuid"] == ""
    # Which reviewed bundle was checked, in the manifest's own terms.
    assert manifest["bundle"]["minecraft"] == "1.21.4"
    assert manifest["identity"]["configured_profile"].startswith("bundle-p0-core-1.21.4.json#")


def test_the_case_definition_is_sealed_and_its_digest_is_the_case_version(
    checked: tuple[Path, Path, Path],
) -> None:
    """`case_version` is the definition's digest, so a reader can check it."""

    data_root, verdict, outputs = checked

    seal_it(data_root, verdict, outputs)

    directory = repository_bundle_directory(data_root, RUN_ID)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    definition = json.loads((directory / "case-definition.json").read_bytes())
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == manifest["case_version"]
    assert definition["case_id"] == manifest["case_id"]


def test_the_artifacts_are_the_checks_and_what_they_were_compared_against(
    checked: tuple[Path, Path, Path],
) -> None:
    data_root, verdict, outputs = checked

    report = seal_it(data_root, verdict, outputs)

    assert set(cast(list[str], report["artifacts"])) == {
        "case-definition.json",
        "check-verdict.json",
        "checks/schemas_are_versioned.log",
        "contracts/manifest.sha256",
        "orchestrator-trace.json",
    }


def test_a_check_that_did_not_hold_is_still_sealed(
    checked: tuple[Path, Path, Path],
) -> None:
    """A repository whose contracts do not hold keeps the evidence that says so."""

    data_root, verdict, outputs = checked
    failed = verdict_document(
        result="FAIL", failures=("schemas_are_versioned:CHECK_FAILED:exit 1",)
    )
    verdict.write_text(json.dumps(failed), encoding="utf-8")

    report = seal_it(data_root, verdict, outputs)

    assert report["status"] == "sealed"
    assert report["result"] == "FAIL"
    assert report["failures"] == ["schemas_are_versioned:CHECK_FAILED:exit 1"]
    assert verify_bundle(repository_bundle_directory(data_root, RUN_ID)).verified


def test_the_promotion_report_counts_a_repository_check(
    checked: tuple[Path, Path, Path],
) -> None:
    """The point of the whole exercise: W00's case has evidence it can be judged on."""

    data_root, verdict, outputs = checked
    seal_it(data_root, verdict, outputs)

    document = cast(dict[str, Any], PROMOTION.report(data_root=data_root, gated="W00"))

    assert document["status"] == "promotable"
    assert document["work_packages"]["W00"]["blocking_cases"] == []
    assert document["evidence"]["count"] == 1


def test_a_verdict_naming_no_check_run_is_refused(checked: tuple[Path, Path, Path]) -> None:
    data_root, verdict, outputs = checked
    verdict.write_text(json.dumps(verdict_document(run_id="not a run id")), encoding="utf-8")

    with pytest.raises(SEALER.Unsealable, match="names no check run"):
        seal_it(data_root, verdict, outputs)


def test_a_verdict_with_an_unknown_result_is_refused(checked: tuple[Path, Path, Path]) -> None:
    data_root, verdict, outputs = checked
    verdict.write_text(json.dumps(verdict_document(result="FINE")), encoding="utf-8")

    with pytest.raises(SEALER.Unsealable, match="not a known outcome"):
        seal_it(data_root, verdict, outputs)


def test_an_unreadable_verdict_is_refused(checked: tuple[Path, Path, Path]) -> None:
    data_root, verdict, outputs = checked
    verdict.unlink()

    with pytest.raises(SEALER.Unsealable, match="not readable verdict JSON"):
        seal_it(data_root, verdict, outputs)


def test_a_check_with_no_kept_output_still_seals(checked: tuple[Path, Path, Path]) -> None:
    """Keeping the output is the caller's choice; the verdict is not."""

    data_root, verdict, _ = checked

    report = seal_it(data_root, verdict, None)

    assert "checks/schemas_are_versioned.log" not in cast(list[str], report["artifacts"])
    assert "check-verdict.json" in cast(list[str], report["artifacts"])
