"""Sealing and verifying an evidence bundle on disk.

Two properties drive this adapter. A run never overwrites a previous run's
bundle, because a corrected result is a new run and not an edit. And a bundle is
refused if any credential literal would be sealed into it, because a bundle is
handed to other people and a leaked token cannot be un-leaked.

Refusing is deliberate: redacting in place would seal a silently altered log,
which is worse evidence than a missing one.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.evidence import (
    EVIDENCE_SCHEMA,
    ArtifactRecord,
    Assertions,
    EvidenceManifest,
    EvidenceResult,
)

MANIFEST_NAME = "manifest.json"
DIGEST_NAME = "bundle.sha256"
BUNDLE_FILES = frozenset({MANIFEST_NAME, DIGEST_NAME})

#: The one violation added on top of a bundle's own account of itself. The
#: directory name is how a bundle is attributed to a run at all — it is the only
#: address a run id alone can produce — so a manifest naming a different run is
#: not evidence for the name it sits under, whatever it contains.
RUN_ID_MISMATCH = "RUN_ID_MISMATCH"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "evidence.bundle", "seal", ErrorCategory.STORAGE, Retryability.OPERATOR_ACTION, message
    )


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    directory: Path
    manifest: EvidenceManifest
    bundle_digest: str


@dataclass(frozen=True, slots=True)
class BundleVerification:
    verified: bool
    violations: tuple[str, ...]
    manifest: EvidenceManifest | None
    bundle_digest: str | None
    sealed: bool


def _canonical(document: object) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative_artifact_path(name: str) -> str:
    """Accept only a plain relative path built from safe segments.

    This is a whitelist on purpose. A blacklist of `..` and absolute markers
    misses platform-specific escapes: on Windows `/absolute.txt` is not absolute
    (it has no drive), and joining it onto the bundle directory replaces the
    bundle root, so a "relative" name can still write outside the bundle.
    """

    parts = name.split("/")
    if not name or any(not _SAFE_SEGMENT.fullmatch(part) for part in parts):
        raise _reject(f"artifact name {name!r} is not a plain relative path inside the bundle")
    return "/".join(parts)


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


def _find_secret(payload: bytes, secrets: Sequence[str]) -> str | None:
    for secret in secrets:
        if secret and secret.encode("utf-8") in payload:
            return secret
    return None


def write_bundle(
    directory: Path,
    manifest: EvidenceManifest,
    artifacts: Mapping[str, bytes],
    *,
    secrets: Sequence[str] = (),
    seal: bool = True,
) -> EvidenceBundle:
    """Seal one run's evidence, or refuse to write anything at all."""

    findings = manifest.violations()
    if findings:
        raise _reject(
            "evidence manifest is not sealable: " + ", ".join(item.value for item in findings)
        )

    if directory.exists() and any(directory.iterdir()):
        raise _reject(
            f"{directory} already holds a bundle; a corrected result is a new run, not an edit"
        )

    records: list[ArtifactRecord] = []
    prepared: list[tuple[str, bytes]] = []
    for name, payload in sorted(artifacts.items()):
        relative = _relative_artifact_path(name)
        if _find_secret(payload, secrets) is not None:
            raise _reject(
                f"artifact {relative!r} contains a credential literal and cannot be sealed"
            )
        prepared.append((relative, payload))
        records.append(ArtifactRecord(path=relative, sha256=_sha256(payload), size=len(payload)))

    sealed_manifest = replace(manifest, artifacts=tuple(records))
    manifest_bytes = _canonical(sealed_manifest.as_document())
    if _find_secret(manifest_bytes, secrets) is not None:
        raise _reject("evidence manifest contains a credential literal and cannot be sealed")
    bundle_digest = _sha256(manifest_bytes)

    directory.mkdir(parents=True, exist_ok=True)
    for relative, payload in prepared:
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (directory / MANIFEST_NAME).write_bytes(manifest_bytes)
    (directory / DIGEST_NAME).write_text(f"{bundle_digest}\n", encoding="ascii")

    if seal:
        _set_writable(directory, False)
    return EvidenceBundle(
        directory=directory, manifest=sealed_manifest, bundle_digest=bundle_digest
    )


def unseal_bundle(directory: Path) -> None:
    """Make a sealed bundle writable again, for retention and deletion."""

    _set_writable(directory, True)


def _set_writable(directory: Path, writable: bool) -> None:
    """Best-effort mode change; the bundled digest is the real guarantee."""

    targets = [path for path in sorted(directory.rglob("*")) if path.is_file()]
    targets.append(directory)
    for path in targets:
        try:
            current = path.stat().st_mode
        except OSError:
            continue
        if writable:
            path.chmod(current | stat.S_IWUSR)
        else:
            path.chmod(current & ~stat.S_IWUSR)
    if writable:
        return
    for path in targets:
        if path.is_file():
            try:
                path.chmod(stat.S_IREAD)
            except OSError:
                return


def _is_sealed(directory: Path) -> bool:
    """Whether every file in the bundle is marked read-only.

    Asked of the mode bits rather than of `os.access`, which answers a different
    question: permission bits do not apply to a process running as root, so
    `os.access` reports every file writable there and a genuinely sealed bundle
    would be reported as open. Measured in the runner container, where the seal
    is applied as uid 0: the files are mode 400 and `os.access` says writable.
    The modes are what the seal *is*; who is asking is a separate matter.
    """

    files = [path for path in directory.rglob("*") if path.is_file()]
    if not files:
        return False
    for path in files:
        try:
            mode = path.stat().st_mode
        except OSError:
            return False
        if mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
            return False
    return True


def verify_bundle(directory: Path) -> BundleVerification:
    """Re-check a sealed bundle against itself, without trusting its manifest."""

    violations: list[str] = []
    manifest_path = directory / MANIFEST_NAME
    digest_path = directory / DIGEST_NAME
    if not manifest_path.is_file() or not digest_path.is_file():
        raise _reject(f"{directory} is not an evidence bundle")

    manifest_bytes = manifest_path.read_bytes()
    bundle_digest = _sha256(manifest_bytes)
    if digest_path.read_text(encoding="ascii").strip() != bundle_digest:
        violations.append("BUNDLE_DIGEST_MISMATCH")

    try:
        document = json.loads(manifest_bytes)
    except json.JSONDecodeError:
        raise _reject(f"{directory} has an unreadable manifest") from None
    if not isinstance(document, dict):
        raise _reject(f"{directory} has an unreadable manifest")
    manifest = _parse_manifest(cast(dict[str, object], document))
    violations.extend(item.value for item in manifest.violations())

    declared: set[str] = set()
    for record in manifest.artifacts:
        declared.add(record.path)
        target = directory / record.path
        if not target.is_file():
            violations.append(f"ARTIFACT_MISSING:{record.path}")
            continue
        payload = target.read_bytes()
        # The digest subsumes the recorded size: identical bytes cannot differ in
        # length, so a separate size check would only ever duplicate this one.
        if _sha256(payload) != record.sha256:
            violations.append(f"ARTIFACT_DIGEST_MISMATCH:{record.path}")

    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        if relative not in declared and relative not in BUNDLE_FILES:
            violations.append(f"UNDECLARED_FILE:{relative}")

    ordered = tuple(sorted(set(violations)))
    return BundleVerification(
        verified=not ordered,
        violations=ordered,
        manifest=manifest,
        bundle_digest=bundle_digest,
        sealed=_is_sealed(directory),
    )


def verify_addressed_bundle(directory: Path) -> BundleVerification:
    """Verify a bundle and hold it to the name of the directory it sits in.

    Asking for the mismatch here rather than once per caller is what keeps
    `evidence verify` and the promotion report from disagreeing about the same
    bundle, and keeps the violation a single string instead of two that drift.
    """

    verification = verify_bundle(directory)
    manifest = verification.manifest
    if manifest is None or manifest.test_run_id == directory.name:
        return verification
    return replace(
        verification,
        verified=False,
        violations=tuple(sorted({*verification.violations, RUN_ID_MISMATCH})),
    )


def _section(document: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = document.get(key)
    if not isinstance(value, Mapping):
        raise _reject(f"evidence manifest is missing {key}")
    return cast(Mapping[str, object], value)


def _text(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise _reject(f"evidence manifest is missing {key}")
    return value


def _strings(document: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = document.get(key)
    if not isinstance(value, list):
        raise _reject(f"evidence manifest is missing {key}")
    return tuple(str(item) for item in cast(list[object], value))


def _parse_manifest(document: dict[str, object]) -> EvidenceManifest:
    if document.get("schema") != EVIDENCE_SCHEMA:
        raise _reject(f"evidence manifest schema is not {EVIDENCE_SCHEMA}")
    raw_result = document.get("result")
    try:
        result = EvidenceResult(str(raw_result))
    except ValueError:
        raise _reject(f"evidence manifest result {raw_result!r} is not a known outcome") from None

    bundle = _section(document, "bundle")
    environment = _section(document, "environment")
    world = _section(document, "world")
    identity = _section(document, "identity")
    assertions = _section(document, "assertions")

    artifacts_value = document.get("artifacts")
    if not isinstance(artifacts_value, list):
        raise _reject("evidence manifest is missing artifacts")
    records: list[ArtifactRecord] = []
    for entry in cast(list[object], artifacts_value):
        if not isinstance(entry, dict):
            raise _reject("evidence manifest artifact must be an object")
        item = cast(dict[str, object], entry)
        size = item.get("size")
        if isinstance(size, bool) or not isinstance(size, int):
            raise _reject("evidence manifest artifact size must be an integer")
        records.append(
            ArtifactRecord(path=_text(item, "path"), sha256=_text(item, "sha256"), size=size)
        )

    return EvidenceManifest(
        test_run_id=_text(document, "test_run_id"),
        case_id=_text(document, "case_id"),
        case_version=_text(document, "case_version"),
        result=result,
        launch_plan_digest=_text(bundle, "launch_plan_digest"),
        bridge_digest=_text(bundle, "bridge_digest"),
        protocol_schema_digest=_text(bundle, "protocol_schema_digest"),
        server_config_digest=_text(world, "server_config_digest"),
        minecraft=_text(bundle, "minecraft"),
        loader=_text(bundle, "loader"),
        fabric_api=_text(bundle, "fabric_api"),
        assertions=Assertions(
            expected=_strings(assertions, "expected"),
            observed=_strings(assertions, "observed"),
            failures=_strings(assertions, "failures"),
        ),
        server_jar_sha1=_text(bundle, "server_jar_sha1"),
        os_kernel=_text(environment, "os_kernel"),
        java_runtime=_text(environment, "java_runtime"),
        cpu_memory=_text(environment, "cpu_memory"),
        renderer_display=_text(environment, "renderer_display"),
        world_kind=_text(world, "kind"),
        seed_or_snapshot_id=_text(world, "seed_or_snapshot_id"),
        configured_profile=_text(identity, "configured_profile"),
        server_observed_name_uuid=_text(identity, "server_observed_name_uuid"),
        artifacts=tuple(records),
    )
