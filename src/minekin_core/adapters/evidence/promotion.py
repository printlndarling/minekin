"""Reading case manifests and turning verified bundles into a promotion verdict."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

from minekin_core.adapters.evidence.bundle import BundleVerification, verify_addressed_bundle
from minekin_core.domain.cases import (
    CaseEvidence,
    CaseManifest,
    CaseRegistry,
    PromotionVerdict,
    evaluate_promotion,
    parse_case_manifest,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.evidence import EvidenceResult


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "evidence.cases", "load", ErrorCategory.CONFIG, Retryability.OPERATOR_ACTION, message
    )


def load_case_manifest(path: Path) -> CaseManifest:
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


def case_evidence(verifications: Mapping[str, BundleVerification]) -> tuple[CaseEvidence, ...]:
    """Read what each verified bundle claims, without deciding anything yet."""

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
