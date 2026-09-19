"""The immutable evidence bundle: what a run leaves behind.

A bundle is the only thing that lets someone else check a claim later, so the
rules here are mostly about refusing to seal something that cannot be checked.
The important one is reporting honesty: if the expected/observed comparison is
missing, the result cannot be a pass, because a bundle that asserts nothing has
proven nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

EVIDENCE_SCHEMA: Final[str] = "minekin.p0.evidence.v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    # Used when the ordering of two events cannot be decided inside the measured
    # clock error window, so neither pass nor fail is claimable.
    AMBIGUOUS = "AMBIGUOUS"


class EvidenceViolation(StrEnum):
    """Why a bundle is not sealable or not trustworthy."""

    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_DIGEST = "INVALID_DIGEST"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"
    RESULT_NEEDS_ASSERTIONS = "RESULT_NEEDS_ASSERTIONS"
    PASS_WITH_FAILURES = "PASS_WITH_FAILURES"
    FAILURE_WITHOUT_REASON = "FAILURE_WITHOUT_REASON"


@dataclass(frozen=True, slots=True)
class Assertions:
    expected: tuple[str, ...]
    observed: tuple[str, ...]
    failures: tuple[str, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "expected": list(self.expected),
            "observed": list(self.observed),
            "failures": list(self.failures),
        }


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """One sealed artifact: where it is and what it must hash to."""

    path: str
    sha256: str
    size: int

    def as_document(self) -> dict[str, object]:
        return {"path": self.path, "sha256": self.sha256, "size": self.size}


@dataclass(frozen=True, slots=True)
class EvidenceManifest:
    """The rule-bearing content of `manifest.json`.

    Descriptive sections are carried verbatim so the sealed document stays
    faithful to the reviewed shape; only the fields a rule depends on are typed
    beyond that.
    """

    test_run_id: str
    case_id: str
    case_version: str
    result: EvidenceResult
    launch_plan_digest: str
    bridge_digest: str
    protocol_schema_digest: str
    server_config_digest: str
    minecraft: str
    loader: str
    fabric_api: str
    assertions: Assertions
    server_jar_sha1: str
    os_kernel: str
    java_runtime: str
    cpu_memory: str
    renderer_display: str
    world_kind: str
    seed_or_snapshot_id: str
    configured_profile: str
    server_observed_name_uuid: str
    artifacts: tuple[ArtifactRecord, ...] = ()

    def violations(self) -> tuple[EvidenceViolation, ...]:
        """Everything that stops this manifest from being sealed or trusted."""

        found: set[EvidenceViolation] = set()
        text_fields = {
            "test_run_id": self.test_run_id,
            "case_id": self.case_id,
            "case_version": self.case_version,
            "minecraft": self.minecraft,
            "loader": self.loader,
            "fabric_api": self.fabric_api,
            "world_kind": self.world_kind,
            "java_runtime": self.java_runtime,
        }
        if not all(value.strip() for value in text_fields.values()):
            found.add(EvidenceViolation.MISSING_FIELD)

        digests = {
            "launch_plan_digest": self.launch_plan_digest,
            "bridge_digest": self.bridge_digest,
            "protocol_schema_digest": self.protocol_schema_digest,
            "server_config_digest": self.server_config_digest,
        }
        if not all(_SHA256.fullmatch(value) for value in digests.values()):
            found.add(EvidenceViolation.INVALID_DIGEST)
        if not all(_SHA256.fullmatch(record.sha256) for record in self.artifacts):
            found.add(EvidenceViolation.INVALID_DIGEST)

        # A result that claims something needs a comparison behind it: `PASS` and
        # `AMBIGUOUS` say how a run went, and a bundle that lists nothing it
        # expected and nothing it saw has not established that. `FAIL` and
        # `INCOMPLETE` are not claims of that kind — a failure is justified by its
        # reasons, and "incomplete" is the answer that asserts nothing. Asking for
        # a non-empty `observed` list from a failure was the difference between
        # sealing a run whose every assertion failed and sealing none of it, and
        # measured: the run that failed all three of CORE-020's assertions could
        # not be sealed at all, which is exactly the evidence that must survive.
        claims = self.result in {EvidenceResult.PASS, EvidenceResult.AMBIGUOUS}
        has_comparison = bool(self.assertions.expected) and bool(self.assertions.observed)
        if claims and not has_comparison:
            found.add(EvidenceViolation.RESULT_NEEDS_ASSERTIONS)
        if self.result is EvidenceResult.PASS and self.assertions.failures:
            found.add(EvidenceViolation.PASS_WITH_FAILURES)
        if self.result is EvidenceResult.FAIL and not self.assertions.failures:
            found.add(EvidenceViolation.FAILURE_WITHOUT_REASON)
        return tuple(sorted(found))

    def as_document(self) -> dict[str, object]:
        return {
            "schema": EVIDENCE_SCHEMA,
            "test_run_id": self.test_run_id,
            "case_id": self.case_id,
            "case_version": self.case_version,
            "result": self.result.value,
            "bundle": {
                "launch_plan_digest": self.launch_plan_digest,
                "minecraft": self.minecraft,
                "server_jar_sha1": self.server_jar_sha1,
                "loader": self.loader,
                "fabric_api": self.fabric_api,
                "bridge_digest": self.bridge_digest,
                "protocol_schema_digest": self.protocol_schema_digest,
            },
            "environment": {
                "os_kernel": self.os_kernel,
                "java_runtime": self.java_runtime,
                "cpu_memory": self.cpu_memory,
                "renderer_display": self.renderer_display,
            },
            "world": {
                "kind": self.world_kind,
                "server_config_digest": self.server_config_digest,
                "seed_or_snapshot_id": self.seed_or_snapshot_id,
            },
            "identity": {
                "configured_profile": self.configured_profile,
                "server_observed_name_uuid": self.server_observed_name_uuid,
            },
            "artifacts": [record.as_document() for record in self.artifacts],
            "assertions": self.assertions.as_document(),
        }
