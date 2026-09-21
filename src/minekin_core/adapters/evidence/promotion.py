"""Reading case manifests and turning verified bundles into a promotion verdict."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import cast

from minekin_core.adapters.evidence.bundle import BundleVerification, verify_addressed_bundle
from minekin_core.domain.cases import (
    CaseEvidence,
    CaseManifest,
    CaseRegistry,
    PromotionVerdict,
    ReJudge,
    evaluate_promotion,
    parse_case_manifest,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.evidence import EvidenceResult

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "evidence.cases", "load", ErrorCategory.CONFIG, Retryability.OPERATOR_ACTION, message
    )


def _validate_input_digests(case: CaseManifest, *, input_root: Path) -> None:
    """Keep reviewed input bytes and their case-version pins inseparable.

    Promotion loads the case registry before comparing bundle versions. Verifying
    pins here means changing an input while forgetting its case JSON cannot leave
    an old PASS promotable merely because a separate fixture gate was not run.
    """

    root = input_root.resolve(strict=True)
    declared_inputs = tuple(PurePosixPath(item) for item in case.inputs)
    for raw_path, expected in case.input_digests:
        logical = PurePosixPath(raw_path)
        if (
            logical.is_absolute()
            or ".." in logical.parts
            or "\\" in raw_path
            or logical.as_posix() != raw_path
        ):
            raise _reject(f"case {case.case_id} has unsafe input digest path {raw_path!r}")
        if not any(
            logical == declared or logical.is_relative_to(declared) for declared in declared_inputs
        ):
            raise _reject(
                f"case {case.case_id} pins {raw_path}, which is not inside a declared input"
            )
        candidate = root.joinpath(*logical.parts)
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as error:
            raise _reject(f"case {case.case_id} pinned input is unavailable: {raw_path}") from error
        if not resolved.is_file():
            raise _reject(f"case {case.case_id} pinned input is not a file: {raw_path}")
        actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual != expected:
            raise _reject(
                f"case {case.case_id} input digest mismatch for {raw_path}: "
                f"expected {expected}, got {actual}"
            )


def load_case_manifest(path: Path, *, input_root: Path = REPOSITORY_ROOT) -> CaseManifest:
    """Load and validate one case manifest, reporting every violation at once."""

    try:
        document = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _reject(f"{path} is not readable UTF-8 JSON") from error
    if not isinstance(document, dict):
        raise _reject(f"{path} is not a case manifest object")
    case, violations = parse_case_manifest(cast(dict[str, object], document))
    if case is None:
        raise _reject(
            f"{path} is not a usable case: " + ", ".join(item.value for item in violations)
        )
    _validate_input_digests(case, input_root=input_root)
    return case


def load_case_registry(directory: Path) -> CaseRegistry:
    """Load every case manifest in a directory, refusing duplicates outright."""

    paths = sorted(path for path in directory.glob("*.json") if path.is_file())
    if not paths:
        raise _reject(f"{directory} holds no case manifests")
    cases = tuple(load_case_manifest(path) for path in paths)
    registry = CaseRegistry(cases=cases)
    duplicates = registry.duplicate_ids()
    if duplicates:
        # Two definitions of one case would make "the case passed" ambiguous.
        raise _reject("case identifiers are not unique: " + ", ".join(duplicates))
    return registry


def case_evidence(
    verifications: Mapping[str, BundleVerification],
    re_judged: Mapping[str, ReJudge] | None = None,
) -> tuple[CaseEvidence, ...]:
    """Read what each verified bundle claims, without deciding anything yet.

    `re_judged` is what a caller that reached these bundles' verdicts a second time
    found. It is a parameter with no default answer of its own, because this module
    cannot re-judge: the assertions are test-domain code and importing them here
    would put them in the shipped package. A bundle nobody names is reported as
    `NOT_ATTEMPTED`, which the promotion rule does not treat as agreement.
    """

    outcomes = re_judged or {}
    collected: list[CaseEvidence] = []
    for run_id, verification in sorted(verifications.items()):
        manifest = verification.manifest
        if manifest is None:
            raise _reject(f"bundle {run_id} has no readable manifest")
        collected.append(
            CaseEvidence(
                case_id=manifest.case_id,
                case_version=manifest.case_version,
                verified=verification.verified,
                passed=manifest.result is EvidenceResult.PASS,
                re_judged=outcomes.get(run_id, ReJudge.NOT_ATTEMPTED),
            )
        )
    return tuple(collected)


def evaluate_case_promotion(
    registry: CaseRegistry,
    bundle_directories: Iterable[Path],
    *,
    work_package: str,
) -> PromotionVerdict:
    """The promotion check: verified bundles against a work package's mandatory cases."""

    verifications: dict[str, BundleVerification] = {}
    for directory in bundle_directories:
        if directory.name in verifications:
            raise _reject(
                f"run id {directory.name} names more than one evidence bundle; "
                "promotion cannot choose between them"
            )
        verifications[directory.name] = verify_addressed_bundle(directory)
    return evaluate_promotion(registry.for_work_package(work_package), case_evidence(verifications))
