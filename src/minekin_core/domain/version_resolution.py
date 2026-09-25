"""Choose one reviewed tested bundle from a probe observation, and never try a login.

A resolution answers one question: which bundle in a *reviewed* registry may this
target be run against. Its only inputs are a V02 observation and a registry whose
`tested` entries each carry independently sealed evidence, so the categories below
are the whole vocabulary — an unresolvable target comes back as a stable reason for
an operator to pin, never as a guess. Nothing here connects, authenticates, or
iterates candidate versions waiting for one to answer: a probe that has already
spoken is the only thing this module is allowed to reason about.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn, cast

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.version_probe import MAX_DISPLAY_TEXT_CHARS, ProbeObservation, ProbeOutcome

REGISTRY_KIND: Final = "reviewed-bundle-registry"
REGISTRY_SCHEMA_VERSION: Final = 1
DECISION_KIND: Final = "version-resolution-decision"
DECISION_SCHEMA_VERSION: Final = 1
MULTI_VERSION_TOKEN: Final = "MULTI_VERSION_PROXY"

_DIGEST: Final = re.compile(r"[0-9a-f]{64}\Z")
_RUN_ID: Final = re.compile(r"[0-9a-f]{32}\Z")
_TOKEN: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

#: The only auth mode a registry entry may declare. Online authentication is an open
#: product decision, so a data file must not be able to opt into it by itself.
SUPPORTED_AUTH_MODES: Final = frozenset({"offline"})


class BundleStatus(StrEnum):
    """Where one registry entry stands in the review."""

    TESTED = "tested"
    QUARANTINED = "quarantined"
    CANDIDATE = "candidate"
    RECIPE = "recipe"


class ResolutionStatus(StrEnum):
    """The four shapes a resolution may take, as a stable evidence token."""

    RESOLVED = "RESOLVED"
    NEEDS_PIN = "NEEDS_PIN"
    UNSUPPORTED = "UNSUPPORTED"
    STALE_PROBE = "STALE_PROBE"


class ResolutionReason(StrEnum):
    """Why a resolution stopped where it did, beside its status."""

    PROBE_STALE = "PROBE_STALE"
    PROBE_NOT_OBSERVED = "PROBE_NOT_OBSERVED"
    PROBE_REFUSED_BY_POLICY = "PROBE_REFUSED_BY_POLICY"
    TARGET_AMBIGUOUS = "TARGET_AMBIGUOUS"
    MULTI_VERSION_PROXY = "MULTI_VERSION_PROXY"
    PROTOCOL_UNOBSERVED = "PROTOCOL_UNOBSERVED"
    PROTOCOL_UNREGISTERED = "PROTOCOL_UNREGISTERED"
    ENTRY_NOT_TESTED = "ENTRY_NOT_TESTED"
    ENTRY_QUARANTINED = "ENTRY_QUARANTINED"
    OS_ARCH_UNAVAILABLE = "OS_ARCH_UNAVAILABLE"
    DISPLAY_TEXT_CONTRADICTS = "DISPLAY_TEXT_CONTRADICTS"
    CANDIDATES_AMBIGUOUS = "CANDIDATES_AMBIGUOUS"
    PIN_UNKNOWN = "PIN_UNKNOWN"
    PIN_NOT_TESTED = "PIN_NOT_TESTED"
    PIN_CONTRADICTS_TARGET = "PIN_CONTRADICTS_TARGET"
    PIN_ARCH_UNAVAILABLE = "PIN_ARCH_UNAVAILABLE"


class RegistryViolation(StrEnum):
    """A registry document that cannot be loaded, one token per rule."""

    MALFORMED_DOCUMENT = "MALFORMED_DOCUMENT"
    NO_ENTRIES = "NO_ENTRIES"
    DUPLICATE_BUNDLE_ID = "DUPLICATE_BUNDLE_ID"
    MALFORMED_BUNDLE_ID = "MALFORMED_BUNDLE_ID"
    UNKNOWN_STATUS = "UNKNOWN_STATUS"
    INVALID_PROTOCOL = "INVALID_PROTOCOL"
    INVALID_JAVA_MAJOR = "INVALID_JAVA_MAJOR"
    INVALID_VERSION_TEXT = "INVALID_VERSION_TEXT"
    INVALID_OS_ARCH = "INVALID_OS_ARCH"
    INVALID_DIGEST = "INVALID_DIGEST"
    UNSAFE_RECIPE_PATH = "UNSAFE_RECIPE_PATH"
    UNSUPPORTED_AUTH_MODE = "UNSUPPORTED_AUTH_MODE"
    INVALID_TOKEN_LIST = "INVALID_TOKEN_LIST"
    DUPLICATE_CAPABILITY = "DUPLICATE_CAPABILITY"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    UNEVIDENCED_RESULT = "UNEVIDENCED_RESULT"
    EVIDENCE_BUILD_MISMATCH = "EVIDENCE_BUILD_MISMATCH"
    TESTED_WITHOUT_EVIDENCE = "TESTED_WITHOUT_EVIDENCE"


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """One sealed run cited as support for a registry entry."""

    case_id: str
    run_id: str
    bundle_digest: str
    bridge_digest: str
    launch_plan_digest: str
    result: str
    attempt: int

    def as_document(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "run_id": self.run_id,
            "bundle_digest": self.bundle_digest,
            "bridge_digest": self.bridge_digest,
            "launch_plan_digest": self.launch_plan_digest,
            "result": self.result,
            "attempt": self.attempt,
        }


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """One reviewed bundle combination, pinned by its build digests."""

    bundle_id: str
    status: BundleStatus
    version_text: str
    protocol: int
    os_arch: str
    java_major: int
    bridge_digest: str
    launch_plan_digest: str
    recipe_path: str
    recipe_digest: str
    auth_mode: str
    capabilities: tuple[str, ...]
    gaps: tuple[str, ...]
    evidence: tuple[EvidenceRef, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "bundle_id": self.bundle_id,
            "status": self.status.value,
            "version_text": self.version_text,
            "protocol": self.protocol,
            "os_arch": self.os_arch,
            "java_major": self.java_major,
            "bridge_digest": self.bridge_digest,
            "launch_plan_digest": self.launch_plan_digest,
            "recipe_path": self.recipe_path,
            "recipe_digest": self.recipe_digest,
            "auth_mode": self.auth_mode,
            "capabilities": list(self.capabilities),
            "gaps": list(self.gaps),
            "evidence": [item.as_document() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class ReviewedBundleRegistry:
    """The reviewed entries, and the digest of the exact bytes they were read from."""

    entries: tuple[RegistryEntry, ...]
    revision: str

    def by_id(self) -> dict[str, RegistryEntry]:
        return {entry.bundle_id: entry for entry in self.entries}


@dataclass(frozen=True, slots=True)
class ResolutionDecision:
    """One attributable resolution: what was observed, and what may run because of it."""

    status: ResolutionStatus
    reasons: tuple[ResolutionReason, ...]
    registry_revision: str
    profile_id: str
    profile_revision: str
    observed_protocol: int | None
    observed_version_text: str | None
    os_arch: str
    operator_pin: str | None
    pin_applied: bool
    candidates: tuple[str, ...]
    bundle: RegistryEntry | None
    detail: str | None = None

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": DECISION_SCHEMA_VERSION,
            "kind": DECISION_KIND,
            "status": self.status.value,
            "reasons": [reason.value for reason in self.reasons],
            "registry_revision": self.registry_revision,
            "profile_id": self.profile_id,
            "profile_revision": self.profile_revision,
            "observed_protocol": self.observed_protocol,
            "observed_version_text": self.observed_version_text,
            "os_arch": self.os_arch,
            "operator_pin": self.operator_pin,
            "pin_applied": self.pin_applied,
            "candidates": list(self.candidates),
            "bundle_id": None if self.bundle is None else self.bundle.bundle_id,
            "bundle": None if self.bundle is None else self.bundle.as_document(),
            "detail": self.detail,
        }


def _rejected(operation: str, detail: str, *, context: Mapping[str, object] = {}) -> NoReturn:
    raise MinekinError(
        component="domain.version_resolution",
        operation=operation,
        category=ErrorCategory.CONFIG,
        retryability=Retryability.OPERATOR_ACTION,
        safe_message=detail,
        context=context,
    )


def _text(document: Mapping[str, object], key: str, found: set[RegistryViolation]) -> str | None:
    value = document.get(key)
    if isinstance(value, str) and value:
        return value
    found.add(RegistryViolation.MALFORMED_DOCUMENT)
    return None


def _bounded_text(
    document: Mapping[str, object], key: str, found: set[RegistryViolation], *, limit: int
) -> str | None:
    value = _text(document, key, found)
    if value is None:
        return None
    if len(value) > limit:
        found.add(RegistryViolation.INVALID_VERSION_TEXT)
        return None
    return value


def _positive_int(
    document: Mapping[str, object],
    key: str,
    found: set[RegistryViolation],
    violation: RegistryViolation,
) -> int | None:
    value = document.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    found.add(violation)
    return None


def _digest(document: Mapping[str, object], key: str, found: set[RegistryViolation]) -> str | None:
    value = document.get(key)
    if isinstance(value, str) and _DIGEST.match(value):
        return value
    found.add(RegistryViolation.INVALID_DIGEST)
    return None


def _token(
    document: Mapping[str, object],
    key: str,
    found: set[RegistryViolation],
    violation: RegistryViolation = RegistryViolation.MALFORMED_BUNDLE_ID,
) -> str | None:
    value = document.get(key)
    if isinstance(value, str) and _TOKEN.match(value):
        return value
    found.add(violation)
    return None


def _token_list(
    document: Mapping[str, object], key: str, found: set[RegistryViolation], *, distinct: bool
) -> tuple[str, ...] | None:
    raw = document.get(key, [])
    if not isinstance(raw, list):
        found.add(RegistryViolation.INVALID_TOKEN_LIST)
        return None
    values: list[str] = []
    for item in cast(list[object], raw):
        if not isinstance(item, str) or not _TOKEN.match(item):
            found.add(RegistryViolation.INVALID_TOKEN_LIST)
            return None
        values.append(item)
    if distinct and len(set(values)) != len(values):
        found.add(RegistryViolation.DUPLICATE_CAPABILITY)
        return None
    return tuple(values)


def _safe_relative_path(
    document: Mapping[str, object], key: str, found: set[RegistryViolation]
) -> str | None:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        found.add(RegistryViolation.UNSAFE_RECIPE_PATH)
        return None
    if (
        "\\" in value
        or ":" in value
        or value.startswith("/")
        or value.startswith("../")
        or "/../" in value
        or value.endswith("/")
    ):
        found.add(RegistryViolation.UNSAFE_RECIPE_PATH)
        return None
    return value


def _as_fields(item: object) -> Mapping[str, object] | None:
    if not isinstance(item, Mapping):
        return None
    mapping = cast(Mapping[object, object], item)
    if any(not isinstance(key, str) for key in mapping):
        return None
    return cast(Mapping[str, object], mapping)


def _evidence_refs(
    document: Mapping[str, object],
    found: set[RegistryViolation],
    *,
    bridge_digest: str | None,
    launch_plan_digest: str | None,
) -> tuple[EvidenceRef, ...]:
    raw = document.get("evidence")
    if not isinstance(raw, list):
        found.add(RegistryViolation.INVALID_EVIDENCE)
        return ()
    refs: list[EvidenceRef] = []
    for item in cast(list[object], raw):
        fields = _as_fields(item)
        if fields is None:
            found.add(RegistryViolation.INVALID_EVIDENCE)
            continue
        local: set[RegistryViolation] = set()
        case_id = _text(fields, "case_id", local)
        run_id = _token(fields, "run_id", local, violation=RegistryViolation.INVALID_EVIDENCE)
        bundle_digest = _digest(fields, "bundle_digest", local)
        evidence_bridge = _digest(fields, "bridge_digest", local)
        evidence_plan = _digest(fields, "launch_plan_digest", local)
        result = _text(fields, "result", local)
        attempt = _positive_int(fields, "attempt", local, RegistryViolation.INVALID_EVIDENCE)
        if run_id is not None and not _RUN_ID.match(run_id):
            local.add(RegistryViolation.INVALID_EVIDENCE)
        if result != "PASS":
            local.add(RegistryViolation.UNEVIDENCED_RESULT)
        if set(fields) - {
            "case_id",
            "run_id",
            "bundle_digest",
            "bridge_digest",
            "launch_plan_digest",
            "result",
            "attempt",
        }:
            local.add(RegistryViolation.INVALID_EVIDENCE)
        if local:
            found.update(local)
            continue
        assert case_id is not None
        assert run_id is not None
        assert bundle_digest is not None
        assert evidence_bridge is not None
        assert evidence_plan is not None
        assert attempt is not None
        if bridge_digest != evidence_bridge or launch_plan_digest != evidence_plan:
            # A citation only supports the build it names. An older sealed run is
            # evidence about *that* build, and reading it as support for this one is
            # the "旧 build 证据称为 tested" mistake the registry exists to refuse.
            found.add(RegistryViolation.EVIDENCE_BUILD_MISMATCH)
            continue
        refs.append(
            EvidenceRef(
                case_id=case_id,
                run_id=run_id,
                bundle_digest=bundle_digest,
                bridge_digest=evidence_bridge,
                launch_plan_digest=evidence_plan,
                result=cast(str, result),
                attempt=attempt,
            )
        )
    return tuple(refs)


def _load_entry(
    document: Mapping[str, object], found: set[RegistryViolation]
) -> RegistryEntry | None:
    if set(document) - {
        "bundle_id",
        "status",
        "version_text",
        "protocol",
        "os_arch",
        "java_major",
        "bridge_digest",
        "launch_plan_digest",
        "recipe_path",
        "recipe_digest",
        "auth_mode",
        "capabilities",
        "gaps",
        "evidence",
    }:
        found.add(RegistryViolation.MALFORMED_DOCUMENT)
    bundle_id = _token(document, "bundle_id", found)
    raw_status = _text(document, "status", found)
    status: BundleStatus | None = None
    if raw_status is not None:
        try:
            status = BundleStatus(raw_status)
        except ValueError:
            found.add(RegistryViolation.UNKNOWN_STATUS)
    version_text = _bounded_text(document, "version_text", found, limit=MAX_DISPLAY_TEXT_CHARS)
    protocol = _positive_int(document, "protocol", found, RegistryViolation.INVALID_PROTOCOL)
    os_arch = _token(document, "os_arch", found)
    java_major = _positive_int(document, "java_major", found, RegistryViolation.INVALID_JAVA_MAJOR)
    bridge_digest = _digest(document, "bridge_digest", found)
    launch_plan_digest = _digest(document, "launch_plan_digest", found)
    recipe_path = _safe_relative_path(document, "recipe_path", found)
    recipe_digest = _digest(document, "recipe_digest", found)
    auth_mode = _text(document, "auth_mode", found)
    if auth_mode is not None and auth_mode not in SUPPORTED_AUTH_MODES:
        found.add(RegistryViolation.UNSUPPORTED_AUTH_MODE)
    capabilities = _token_list(document, "capabilities", found, distinct=True)
    gaps = _token_list(document, "gaps", found, distinct=True)
    if None in (
        bundle_id,
        status,
        version_text,
        protocol,
        os_arch,
        java_major,
        bridge_digest,
        launch_plan_digest,
        recipe_path,
        recipe_digest,
        auth_mode,
        capabilities,
        gaps,
    ):
        return None
    evidence = _evidence_refs(
        document,
        found,
        bridge_digest=bridge_digest,
        launch_plan_digest=launch_plan_digest,
    )
    if status is BundleStatus.TESTED and not evidence:
        found.add(RegistryViolation.TESTED_WITHOUT_EVIDENCE)
        return None
    return RegistryEntry(
        bundle_id=cast(str, bundle_id),
        status=cast(BundleStatus, status),
        version_text=cast(str, version_text),
        protocol=cast(int, protocol),
        os_arch=cast(str, os_arch),
        java_major=cast(int, java_major),
        bridge_digest=cast(str, bridge_digest),
        launch_plan_digest=cast(str, launch_plan_digest),
        recipe_path=cast(str, recipe_path),
        recipe_digest=cast(str, recipe_digest),
        auth_mode=cast(str, auth_mode),
        capabilities=cast(tuple[str, ...], capabilities),
        gaps=cast(tuple[str, ...], gaps),
        evidence=evidence,
    )


def registry_revision(document: object) -> str:
    """The digest of the registry as read: its bytes are what an operator reviewed."""

    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_reviewed_registry(document: object) -> ReviewedBundleRegistry:
    """Read a reviewed bundle registry, or refuse it with the rules it broke.

    Loading is strict on purpose. This document is the resolver's only authority, so
    a half-readable registry has to fail closed rather than resolve against whatever
    entries it happened to parse.
    """

    fields = _as_fields(document)
    if fields is None:
        _rejected("load_reviewed_registry", "a registry document must be an object of fields")
    found: set[RegistryViolation] = set()
    if fields.get("kind") != REGISTRY_KIND:
        found.add(RegistryViolation.MALFORMED_DOCUMENT)
    if fields.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        found.add(RegistryViolation.MALFORMED_DOCUMENT)
    if set(fields) - {"kind", "schema_version", "entries", "notes"}:
        found.add(RegistryViolation.MALFORMED_DOCUMENT)
    raw_entries = fields.get("entries")
    entries: list[RegistryEntry] = []
    if not isinstance(raw_entries, list) or not raw_entries:
        found.add(RegistryViolation.NO_ENTRIES)
    else:
        for item in cast(list[object], raw_entries):
            entry_fields = _as_fields(item)
            if entry_fields is None:
                found.add(RegistryViolation.MALFORMED_DOCUMENT)
                continue
            entry = _load_entry(entry_fields, found)
            if entry is not None:
                entries.append(entry)
    seen: set[str] = set()
    for entry in entries:
        if entry.bundle_id in seen:
            found.add(RegistryViolation.DUPLICATE_BUNDLE_ID)
        seen.add(entry.bundle_id)
    if found:
        _rejected(
            "load_reviewed_registry",
            "the reviewed bundle registry is not loadable",
            context={"violations": sorted(violation.value for violation in found)},
        )
    return ReviewedBundleRegistry(entries=tuple(entries), revision=registry_revision(document))


def _decision(
    registry: ReviewedBundleRegistry,
    observation: ProbeObservation,
    *,
    status: ResolutionStatus,
    reasons: Sequence[ResolutionReason] = (),
    os_arch: str,
    operator_pin: str | None = None,
    pin_applied: bool = False,
    candidates: Iterable[str] = (),
    bundle: RegistryEntry | None = None,
    detail: str | None = None,
) -> ResolutionDecision:
    return ResolutionDecision(
        status=status,
        reasons=tuple(sorted(set(reasons), key=lambda reason: reason.value)),
        registry_revision=registry.revision,
        profile_id=observation.profile_id,
        profile_revision=observation.profile_revision,
        observed_protocol=observation.protocol,
        observed_version_text=observation.version_text,
        os_arch=os_arch,
        operator_pin=operator_pin,
        pin_applied=pin_applied,
        candidates=tuple(sorted(candidates)),
        bundle=bundle,
        detail=detail,
    )


def _pin_decision(
    registry: ReviewedBundleRegistry,
    observation: ProbeObservation,
    *,
    os_arch: str,
    operator_pin: str,
) -> ResolutionDecision:
    entry = registry.by_id().get(operator_pin)
    if entry is None:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.NEEDS_PIN,
            reasons=(ResolutionReason.PIN_UNKNOWN,),
            os_arch=os_arch,
            operator_pin=operator_pin,
            detail="the pin names no entry in this registry; a stale pin is not a fallback",
        )
    if entry.status is not BundleStatus.TESTED:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.NEEDS_PIN,
            reasons=(ResolutionReason.PIN_NOT_TESTED,),
            os_arch=os_arch,
            operator_pin=operator_pin,
            detail=f"a pin cannot carry an entry past its review state ({entry.status.value})",
        )
    contradicted = entry.protocol != observation.protocol or (
        observation.version_text is not None and entry.version_text != observation.version_text
    )
    if contradicted:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.NEEDS_PIN,
            reasons=(ResolutionReason.PIN_CONTRADICTS_TARGET,),
            os_arch=os_arch,
            operator_pin=operator_pin,
            candidates=(entry.bundle_id,),
            detail="the pinned bundle is not the version the target was observed as",
        )
    if entry.os_arch != os_arch:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.UNSUPPORTED,
            reasons=(ResolutionReason.PIN_ARCH_UNAVAILABLE,),
            os_arch=os_arch,
            operator_pin=operator_pin,
            candidates=(entry.bundle_id,),
            detail=f"the pinned bundle has no build for {os_arch}",
        )
    return _decision(
        registry,
        observation,
        status=ResolutionStatus.RESOLVED,
        os_arch=os_arch,
        operator_pin=operator_pin,
        pin_applied=True,
        candidates=(entry.bundle_id,),
        bundle=entry,
    )


def _text_agrees(entry: RegistryEntry, observed_text: str | None) -> bool:
    if observed_text is None:
        return True
    return entry.version_text == observed_text


def _pin_settles(observation: ProbeObservation) -> bool:
    """Whether a bundle pin is the kind of answer this observation is asking for.

    A multi-version proxy did report a protocol; what is unresolved is which of the
    versions it fronts the operator means. An expired cache, a refused address, or a
    connection that said nothing has no reading for a pin to settle, and a pin must
    not become a way of launching against an endpoint the policy already refused.
    """

    return (
        observation.outcome is ProbeOutcome.AMBIGUOUS
        and observation.protocol is not None
        and MULTI_VERSION_TOKEN in observation.refusal_reasons
    )


def _unobserved(
    registry: ReviewedBundleRegistry,
    observation: ProbeObservation,
    *,
    os_arch: str,
    operator_pin: str | None,
) -> ResolutionDecision | None:
    """Classify every outcome that did not read a version, or None if it did."""

    outcome = observation.outcome
    if outcome is ProbeOutcome.OBSERVED:
        return None
    if outcome is ProbeOutcome.AMBIGUOUS:
        # These two are the only unrelied-upon readings a pin can still settle: the
        # probe did see a protocol, and it is the target's shape that is unresolved.
        multi_version = MULTI_VERSION_TOKEN in observation.refusal_reasons
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.NEEDS_PIN,
            reasons=(
                ResolutionReason.MULTI_VERSION_PROXY
                if multi_version
                else ResolutionReason.TARGET_AMBIGUOUS,
            ),
            os_arch=os_arch,
            operator_pin=operator_pin,
            detail=(
                "a proxy listing several versions needs an operator pin, not a pick"
                if multi_version
                else "the target resolved to more than one endpoint; nothing was chosen"
            ),
        )
    if outcome is ProbeOutcome.CACHE_EXPIRED:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.STALE_PROBE,
            reasons=(ResolutionReason.PROBE_STALE,),
            os_arch=os_arch,
            operator_pin=operator_pin,
            detail="the probe's resolution had expired; re-probe before choosing",
        )
    if outcome is ProbeOutcome.POLICY_REFUSAL:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.NEEDS_PIN,
            reasons=(ResolutionReason.PROBE_REFUSED_BY_POLICY,),
            os_arch=os_arch,
            operator_pin=operator_pin,
            detail=(
                "the address policy refused the endpoint before it was read; a bundle pin "
                "does not re-authorize an address"
            ),
        )
    return _decision(
        registry,
        observation,
        status=ResolutionStatus.STALE_PROBE,
        reasons=(ResolutionReason.PROBE_NOT_OBSERVED,),
        os_arch=os_arch,
        operator_pin=operator_pin,
        detail="the probe reached the target and learned nothing usable from it",
    )


def resolve(
    registry: ReviewedBundleRegistry,
    observation: ProbeObservation,
    *,
    os_arch: str,
    operator_pin: str | None = None,
) -> ResolutionDecision:
    """Pick the one reviewed bundle a target was observed as, or say why none can be picked.

    The observed protocol id is the index and the status text is corroboration only:
    a display string that disagrees with the protocol it arrived on is a reason to
    stop, not a reason to prefer one candidate. Where several tested bundles share a
    protocol there is no ranking to fall back on either — they are listed and the
    decision waits for a pin.
    """

    refusal = _unobserved(registry, observation, os_arch=os_arch, operator_pin=operator_pin)
    if refusal is not None:
        if operator_pin is not None and _pin_settles(observation):
            return _pin_decision(registry, observation, os_arch=os_arch, operator_pin=operator_pin)
        return refusal

    if observation.protocol is None:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.STALE_PROBE,
            reasons=(ResolutionReason.PROTOCOL_UNOBSERVED,),
            os_arch=os_arch,
            operator_pin=operator_pin,
            detail="an observation with no protocol id cannot index a registry",
        )

    if operator_pin is not None:
        return _pin_decision(registry, observation, os_arch=os_arch, operator_pin=operator_pin)

    sharing = [entry for entry in registry.entries if entry.protocol == observation.protocol]
    if not sharing:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.UNSUPPORTED,
            reasons=(ResolutionReason.PROTOCOL_UNREGISTERED,),
            os_arch=os_arch,
            detail=(
                f"protocol {observation.protocol} is in no reviewed entry; the version is not "
                "refused, only unreviewed"
            ),
        )

    reviewed = [entry for entry in sharing if entry.status is BundleStatus.TESTED]
    if not reviewed:
        quarantined = any(entry.status is BundleStatus.QUARANTINED for entry in sharing)
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.NEEDS_PIN,
            reasons=(
                ResolutionReason.ENTRY_QUARANTINED
                if quarantined
                else ResolutionReason.ENTRY_NOT_TESTED,
            ),
            os_arch=os_arch,
            candidates=(entry.bundle_id for entry in sharing),
            detail=(
                "every bundle sharing this protocol is unreviewed or withdrawn; running one of "
                "them would be a trial login by another name"
            ),
        )

    for_os_arch = [entry for entry in reviewed if entry.os_arch == os_arch]
    if not for_os_arch:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.UNSUPPORTED,
            reasons=(ResolutionReason.OS_ARCH_UNAVAILABLE,),
            os_arch=os_arch,
            candidates=(entry.bundle_id for entry in reviewed),
            detail=(
                f"no tested bundle for protocol {observation.protocol} has a {os_arch} build; "
                "available: " + ", ".join(sorted({entry.os_arch for entry in reviewed}))
            ),
        )

    agreeing = [entry for entry in for_os_arch if _text_agrees(entry, observation.version_text)]
    if not agreeing:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.NEEDS_PIN,
            reasons=(ResolutionReason.DISPLAY_TEXT_CONTRADICTS,),
            os_arch=os_arch,
            candidates=(entry.bundle_id for entry in for_os_arch),
            detail=(
                f"the target announced {observation.version_text!r} on protocol "
                f"{observation.protocol}; the reviewed text disagrees, so the announcement "
                "is not believed"
            ),
        )
    if len(agreeing) > 1:
        return _decision(
            registry,
            observation,
            status=ResolutionStatus.NEEDS_PIN,
            reasons=(ResolutionReason.CANDIDATES_AMBIGUOUS,),
            os_arch=os_arch,
            candidates=(entry.bundle_id for entry in agreeing),
            detail=(
                "several tested bundles cover this observation and no reviewed contract ranks "
                "them; an operator pin decides"
            ),
        )
    return _decision(
        registry,
        observation,
        status=ResolutionStatus.RESOLVED,
        os_arch=os_arch,
        candidates=(agreeing[0].bundle_id,),
        bundle=agreeing[0],
    )


class ProvenanceViolation(StrEnum):
    """One way an entry's claim to `tested` fails to be a fact about real artifacts.

    Loading a registry only proves the document agrees with itself. These tokens
    name the ways the sealed bytes the entry cites can still disagree with it, so
    that a check against the artifacts themselves has a vocabulary to report in —
    every one of them is a refusal, and none of them is a softer default.
    """

    ENTRY_NOT_MEASURED = "ENTRY_NOT_MEASURED"
    RECIPE_UNREADABLE = "RECIPE_UNREADABLE"
    RECIPE_DIGEST_MISMATCH = "RECIPE_DIGEST_MISMATCH"
    SOURCE_TREE_MISSING = "SOURCE_TREE_MISSING"
    SOURCE_DIGEST_MISMATCH = "SOURCE_DIGEST_MISMATCH"
    BRIDGE_JAR_MISSING = "BRIDGE_JAR_MISSING"
    BRIDGE_JAR_DIGEST_MISMATCH = "BRIDGE_JAR_DIGEST_MISMATCH"
    PLAN_UNBUILDABLE = "PLAN_UNBUILDABLE"
    PLAN_DIGEST_MISMATCH = "PLAN_DIGEST_MISMATCH"
    CITATION_UNMEASURED = "CITATION_UNMEASURED"
    CITATION_BUNDLE_MISSING = "CITATION_BUNDLE_MISSING"
    CITATION_BUNDLE_UNREADABLE = "CITATION_BUNDLE_UNREADABLE"
    CITATION_BUNDLE_INCONSISTENT = "CITATION_BUNDLE_INCONSISTENT"
    CITATION_DIGEST_MISMATCH = "CITATION_DIGEST_MISMATCH"
    CITATION_IDENTITY_MISMATCH = "CITATION_IDENTITY_MISMATCH"
    CITATION_NOT_PASS = "CITATION_NOT_PASS"
    CITATION_BUILD_DISAGREES = "CITATION_BUILD_DISAGREES"


@dataclass(frozen=True, slots=True)
class BridgeMeasurement:
    """What the build host holds for the Bridge one entry names.

    Measured, not recalled: `jar_sha256` is the hash of the bytes that are there
    now, and None means there were no bytes to hash. The pin stays where it is —
    in the entry, and in `recipe.py` as the expectation — because this is the half
    that answers "and what is actually on this machine?".
    """

    source_root: str
    jar_path: str
    jar_sha256: str | None
    jar_size: int | None
    source_digest: str | None
    detail: str | None = None
    source_detail: str | None = None

    def as_document(self) -> dict[str, object]:
        return {
            "source_root": self.source_root,
            "jar_path": self.jar_path,
            "jar_sha256": self.jar_sha256,
            "jar_size": self.jar_size,
            "source_digest": self.source_digest,
            "detail": self.detail,
            "source_detail": self.source_detail,
        }


@dataclass(frozen=True, slots=True)
class CitationMeasurement:
    """One sealed evidence bundle, re-read from the store rather than trusted by name.

    `bundle_digest` is the digest recomputed from the manifest bytes; `case_id`,
    `result`, `bridge_digest` and `launch_plan_digest` are what that manifest
    itself says. A citation is only support if all of it lines up with the
    registry's claim, so the fields are kept apart from the findings on purpose.

    `sealed` is read-only mode bits, reported and never refused: the digest is the
    guarantee and the mode is a courtesy, which is the position
    `tools/report_promotion.py` already takes. Editing the bytes of a writable
    bundle cannot hide itself here anyway — the manifest digest is what the
    registry cites, and it moves with them.
    """

    run_id: str
    present: bool
    readable: bool
    sealed: bool
    consistent: bool
    bundle_digest: str | None
    case_id: str | None = None
    result: str | None = None
    bridge_digest: str | None = None
    launch_plan_digest: str | None = None
    detail: str | None = None

    def as_document(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "present": self.present,
            "readable": self.readable,
            "sealed": self.sealed,
            "consistent": self.consistent,
            "bundle_digest": self.bundle_digest,
            "case_id": self.case_id,
            "result": self.result,
            "bridge_digest": self.bridge_digest,
            "launch_plan_digest": self.launch_plan_digest,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class EntryMeasurements:
    """Everything one host could measure about one registry entry."""

    recipe_digest: str | None
    recipe_source_digest: str | None
    plan_sha256: str | None
    bridge: BridgeMeasurement | None
    citations: tuple[CitationMeasurement, ...]
    detail: str | None = None

    def as_document(self) -> dict[str, object]:
        return {
            "recipe_digest": self.recipe_digest,
            "recipe_source_digest": self.recipe_source_digest,
            "plan_sha256": self.plan_sha256,
            "bridge": None if self.bridge is None else self.bridge.as_document(),
            "citations": [item.as_document() for item in self.citations],
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ProvenanceFinding:
    """One refusal, and the artifact it was about."""

    violation: ProvenanceViolation
    subject: str
    detail: str

    def as_document(self) -> dict[str, object]:
        return {"violation": self.violation.value, "subject": self.subject, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class EntryProvenance:
    """What one entry's `tested` claim is worth on the machine that measured it."""

    bundle_id: str
    verified: bool
    findings: tuple[ProvenanceFinding, ...]
    measured: EntryMeasurements | None

    def as_document(self) -> dict[str, object]:
        return {
            "bundle_id": self.bundle_id,
            "verified": self.verified,
            "findings": [item.as_document() for item in self.findings],
            "measured": None if self.measured is None else self.measured.as_document(),
        }


@dataclass(frozen=True, slots=True)
class ProvenanceSummary:
    """The verification of every tested entry in one registry document."""

    registry_revision: str
    verified: bool
    entries: tuple[EntryProvenance, ...]
    skipped: tuple[str, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "tested-provenance-report",
            "registry_revision": self.registry_revision,
            "verified": self.verified,
            "entries": [item.as_document() for item in self.entries],
            "skipped_not_tested": list(self.skipped),
        }


def _finding(
    found: list[ProvenanceFinding], violation: ProvenanceViolation, subject: str, detail: str
) -> None:
    found.append(ProvenanceFinding(violation=violation, subject=subject, detail=detail))


def _citation_findings(
    entry: RegistryEntry,
    citation: CitationMeasurement | None,
    ref: EvidenceRef,
    found: list[ProvenanceFinding],
) -> None:
    subject = f"{ref.case_id}@{ref.run_id}"
    if citation is None or citation.run_id != ref.run_id:
        _finding(
            found,
            ProvenanceViolation.CITATION_UNMEASURED,
            subject,
            "no bundle was measured for this run id; an unmeasured citation is not verified",
        )
        return
    if not citation.present:
        _finding(
            found,
            ProvenanceViolation.CITATION_BUNDLE_MISSING,
            subject,
            citation.detail or f"no sealed bundle is stored under {ref.run_id}",
        )
        return
    if not citation.readable:
        _finding(
            found,
            ProvenanceViolation.CITATION_BUNDLE_UNREADABLE,
            subject,
            citation.detail or f"the bundle stored under {ref.run_id} cannot be read",
        )
        return
    if not citation.consistent:
        _finding(
            found,
            ProvenanceViolation.CITATION_BUNDLE_INCONSISTENT,
            subject,
            citation.detail
            or f"the bundle stored under {ref.run_id} does not verify against its own manifest",
        )
        return
    if citation.bundle_digest != ref.bundle_digest:
        _finding(
            found,
            ProvenanceViolation.CITATION_DIGEST_MISMATCH,
            subject,
            f"the bundle there digests to {citation.bundle_digest}, not the cited "
            f"{ref.bundle_digest}",
        )
    if citation.case_id != ref.case_id:
        _finding(
            found,
            ProvenanceViolation.CITATION_IDENTITY_MISMATCH,
            subject,
            f"the bundle under {ref.run_id} describes case {citation.case_id}",
        )
    if citation.result != "PASS":
        _finding(
            found,
            ProvenanceViolation.CITATION_NOT_PASS,
            subject,
            f"the bundle's own manifest records {citation.result}, not PASS",
        )
    if (
        citation.bridge_digest != entry.bridge_digest
        or citation.launch_plan_digest != entry.launch_plan_digest
    ):
        # The registry loader already refuses a citation that names another build, so
        # reaching here means the document was loaded by something that skipped that
        # rule. It is still a refusal, because this check is the one that reads the
        # sealed bytes.
        _finding(
            found,
            ProvenanceViolation.CITATION_BUILD_DISAGREES,
            subject,
            f"the bundle was sealed against bridge {citation.bridge_digest} and plan "
            f"{citation.launch_plan_digest}, not the entry's {entry.bridge_digest} and "
            f"{entry.launch_plan_digest}",
        )


def verify_entry_provenance(
    entry: RegistryEntry, measurements: EntryMeasurements | None
) -> EntryProvenance:
    """Say what an entry's `tested` claim is worth, given what a host could measure.

    Every check here compares a claim against a measurement, and a missing
    measurement is its own refusal rather than a pass: the question this answers is
    "did someone hash the real thing?", and "nobody did" is not a yes.

    Nothing about `resolve()` changes. This cannot make an entry resolvable,
    quotable, or installable — it only reports whether the artifacts back the word
    `tested`, and a `False` here is strictly more caution than no measurement.
    """

    found: list[ProvenanceFinding] = []
    if measurements is None:
        _finding(
            found,
            ProvenanceViolation.ENTRY_NOT_MEASURED,
            entry.bundle_id,
            "nothing was measured for this entry",
        )
        return EntryProvenance(entry.bundle_id, False, tuple(found), None)

    if measurements.recipe_digest is None:
        _finding(
            found,
            ProvenanceViolation.RECIPE_UNREADABLE,
            entry.recipe_path,
            measurements.detail or f"recipe {entry.recipe_path} could not be read",
        )
    elif measurements.recipe_digest != entry.recipe_digest:
        _finding(
            found,
            ProvenanceViolation.RECIPE_DIGEST_MISMATCH,
            entry.recipe_path,
            f"{entry.recipe_path} digests to {measurements.recipe_digest}, not the reviewed "
            f"{entry.recipe_digest}",
        )

    bridge = measurements.bridge
    if bridge is None:
        _finding(
            found,
            ProvenanceViolation.BRIDGE_JAR_MISSING,
            entry.bundle_id,
            # A consequence, not a claim about the jar: the version the Bridge is
            # named by never reached the disk, so say which reading stopped.
            "no Bridge bytes were measured for this entry's version"
            if measurements.detail is None
            else f"no Bridge bytes were measured: {measurements.detail}",
        )
    else:
        if bridge.jar_sha256 is None:
            _finding(
                found,
                ProvenanceViolation.BRIDGE_JAR_MISSING,
                bridge.jar_path,
                bridge.detail or f"{bridge.jar_path} is not there to be hashed",
            )
        elif bridge.jar_sha256 != entry.bridge_digest:
            _finding(
                found,
                ProvenanceViolation.BRIDGE_JAR_DIGEST_MISMATCH,
                bridge.jar_path,
                f"{bridge.jar_path} digests to {bridge.jar_sha256}, not the reviewed "
                f"{entry.bridge_digest}",
            )
        if measurements.recipe_source_digest is None:
            _finding(
                found,
                ProvenanceViolation.SOURCE_TREE_MISSING,
                bridge.source_root,
                "the recipe names no source digest for its Bridge artifact",
            )
        elif bridge.source_digest is None:
            _finding(
                found,
                ProvenanceViolation.SOURCE_TREE_MISSING,
                bridge.source_root,
                # `bridge.detail` is the jar's story; a source tree that cannot be
                # hashed has its own, or a reader is told the jar went missing twice.
                bridge.source_detail
                or f"the source tree {bridge.source_root} cannot be hashed on this host",
            )
        elif bridge.source_digest != measurements.recipe_source_digest:
            _finding(
                found,
                ProvenanceViolation.SOURCE_DIGEST_MISMATCH,
                bridge.source_root,
                f"{bridge.source_root} hashes to {bridge.source_digest}, but the reviewed recipe "
                f"seals {measurements.recipe_source_digest}",
            )

    if measurements.plan_sha256 is None:
        _finding(
            found,
            ProvenanceViolation.PLAN_UNBUILDABLE,
            entry.recipe_path,
            measurements.detail or "no launch plan could be built from the recipe on this host",
        )
    elif measurements.plan_sha256 != entry.launch_plan_digest:
        _finding(
            found,
            ProvenanceViolation.PLAN_DIGEST_MISMATCH,
            entry.recipe_path,
            f"the plan built from {entry.recipe_path} digests to {measurements.plan_sha256}, "
            f"not the reviewed {entry.launch_plan_digest}",
        )

    measured = {item.run_id: item for item in measurements.citations}
    for ref in entry.evidence:
        _citation_findings(entry, measured.get(ref.run_id), ref, found)

    ordered = tuple(sorted(found, key=lambda item: (item.violation.value, item.subject)))
    return EntryProvenance(entry.bundle_id, not ordered, ordered, measurements)


def verify_registry_provenance(
    registry: ReviewedBundleRegistry,
    measurements: Mapping[str, EntryMeasurements | None],
) -> ProvenanceSummary:
    """Verify every `tested` entry the registry carries, and name what it skipped."""

    entries = tuple(
        verify_entry_provenance(entry, measurements.get(entry.bundle_id))
        for entry in registry.entries
        if entry.status is BundleStatus.TESTED
    )
    return ProvenanceSummary(
        registry_revision=registry.revision,
        verified=bool(entries) and all(entry.verified for entry in entries),
        entries=entries,
        skipped=tuple(
            sorted(
                entry.bundle_id
                for entry in registry.entries
                if entry.status is not BundleStatus.TESTED
            )
        ),
    )
