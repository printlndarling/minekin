"""Content-addressed artifact, immutable bundle, and session overlay storage."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, cast

from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


def _reject(message: str, *, category: ErrorCategory = ErrorCategory.SUPPLY_CHAIN) -> MinekinError:
    return MinekinError(
        component="launcher.artifacts",
        operation="materialize",
        category=category,
        retryability=Retryability.OPERATOR_ACTION,
        safe_message=message,
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _safe_component(value: str, field: str) -> str:
    if not _SAFE_ID.fullmatch(value) or value in {".", ".."}:
        raise _reject(f"{field} is not a safe path component", category=ErrorCategory.CONFIG)
    return value


def _sha1_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha1()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise _reject("bundle view path is unsafe")
    if any(part.lower() == ".minecraft" for part in path.parts):
        raise _reject("host .minecraft paths are forbidden")
    return path


def _assert_no_symlink(path: Path, stop: Path) -> None:
    current = path
    while current != stop:
        if current.is_symlink():
            raise _reject("managed storage path contains a symlink", category=ErrorCategory.CONFIG)
        current = current.parent
    if stop.is_symlink():
        raise _reject("managed storage root cannot be a symlink", category=ErrorCategory.CONFIG)


def _readonly(path: Path) -> None:
    path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for child in path.rglob("*"):
        child.chmod(child.stat().st_mode | stat.S_IWUSR)
    shutil.rmtree(path)


@dataclass(frozen=True, slots=True)
class BundleEntry:
    view_path: str
    artifact: Artifact


class ArtifactStore:
    """Transactional content-addressed store rooted under Minekin-managed data."""

    def __init__(self, root: Path) -> None:
        requested_root = root.absolute()
        if requested_root.is_symlink():
            raise _reject("artifact store root cannot be a symlink", category=ErrorCategory.CONFIG)
        self.root = requested_root.resolve()
        if any(part.lower() == ".minecraft" for part in self.root.parts):
            raise _reject(
                "artifact store cannot live inside .minecraft", category=ErrorCategory.CONFIG
            )
        self.blobs = self.root / "blobs" / "sha1"
        self.staging = self.root / ".staging"
        self.quarantine = self.root / "quarantine"
        for path in (self.blobs, self.staging, self.quarantine):
            path.mkdir(parents=True, exist_ok=True)
            _assert_no_symlink(path, self.root)

    def path_for(self, artifact: Artifact) -> Path:
        filename = Path(artifact.path).name
        if not filename or filename in {".", ".."}:
            raise _reject("artifact filename is unsafe")
        return self.blobs / artifact.sha1[:2] / artifact.sha1 / filename

    def verify(self, artifact: Artifact) -> Path:
        path = self.path_for(artifact)
        _assert_no_symlink(path.parent, self.root)
        if not path.is_file() or path.is_symlink():
            raise _reject("artifact is missing from the content-addressed store")
        size, digest = _sha1_file(path)
        if size != artifact.size or digest != artifact.sha1:
            raise _reject("stored artifact failed size or digest verification")
        return path

    def install(self, artifact: Artifact, source: BinaryIO) -> Path:
        target = self.path_for(artifact)
        if target.exists():
            return self.verify(artifact)
        transaction = self.staging / uuid.uuid4().hex
        transaction.mkdir(parents=False)
        temporary = transaction / "payload.part"
        digest = hashlib.sha1()
        size = 0
        try:
            with temporary.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if size != artifact.size or digest.hexdigest() != artifact.sha1:
                quarantine = self.quarantine / transaction.name
                os.replace(transaction, quarantine)
                raise _reject("downloaded artifact failed size or digest verification")
            target.parent.mkdir(parents=True, exist_ok=True)
            _assert_no_symlink(target.parent, self.root)
            try:
                os.replace(temporary, target)
            except FileExistsError:
                return self.verify(artifact)
            _readonly(target)
            return self.verify(artifact)
        finally:
            if transaction.exists():
                _remove_tree(transaction)


class BundleStore:
    """Publish immutable bundle views from already verified store objects."""

    def __init__(self, root: Path, artifact_store: ArtifactStore) -> None:
        requested_root = root.absolute()
        if requested_root.is_symlink():
            raise _reject("bundle store root cannot be a symlink", category=ErrorCategory.CONFIG)
        self.root = requested_root.resolve()
        self.artifact_store = artifact_store
        if self.root == artifact_store.root or self.root.is_relative_to(artifact_store.root):
            raise _reject("bundle store and artifact store must have separate roots")
        self.staging = self.root / ".staging"
        self.staging.mkdir(parents=True, exist_ok=True)
        _assert_no_symlink(self.staging, self.root)

    def publish(
        self,
        bundle_id: str,
        plan: Mapping[str, object],
        entries: Iterable[BundleEntry],
    ) -> Path:
        materialized_entries = tuple(entries)
        entry_records = self._entry_records(materialized_entries)
        expected_bundle_id = self.bundle_id_for(plan, materialized_entries)
        if bundle_id != expected_bundle_id:
            raise _reject("bundle_id does not match the plan and artifact set")
        bundle_id = _safe_component(bundle_id, "bundle_id")
        target = self.root / bundle_id
        if target.exists():
            self.verify(bundle_id)
            return target
        transaction = self.staging / uuid.uuid4().hex
        transaction.mkdir()
        seen: set[Path] = set()
        try:
            for entry in materialized_entries:
                relative = _safe_relative(entry.view_path)
                if relative in seen:
                    raise _reject("bundle contains a duplicate view path")
                seen.add(relative)
                source = self.artifact_store.verify(entry.artifact)
                destination = transaction / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                _readonly(destination)
            manifest = transaction / "bundle-manifest.json"
            with manifest.open("xb") as stream:
                stream.write(
                    _canonical_json(
                        {"bundle_id": bundle_id, "plan": plan, "entries": entry_records}
                    )
                )
                stream.flush()
                os.fsync(stream.fileno())
            _readonly(manifest)
            os.replace(transaction, target)
            return self.verify(bundle_id)
        finally:
            if transaction.exists():
                _remove_tree(transaction)

    @staticmethod
    def _entry_records(entries: Iterable[BundleEntry]) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for entry in entries:
            records.append(
                {
                    "view_path": _safe_relative(entry.view_path).as_posix(),
                    "size": entry.artifact.size,
                    "sha1": entry.artifact.sha1,
                    "coordinate": entry.artifact.coordinate,
                }
            )
        return sorted(records, key=lambda item: str(item["view_path"]))

    @classmethod
    def bundle_id_for(cls, plan: Mapping[str, object], entries: Iterable[BundleEntry]) -> str:
        identity = {"plan": plan, "entries": cls._entry_records(entries)}
        return hashlib.sha256(_canonical_json(identity)).hexdigest()

    def verify(self, bundle_id: str) -> Path:
        bundle_id = _safe_component(bundle_id, "bundle_id")
        target = self.root / bundle_id
        manifest = target / "bundle-manifest.json"
        _assert_no_symlink(target, self.root)
        if not target.is_dir() or target.is_symlink() or not manifest.is_file():
            raise _reject("bundle is missing or incomplete")
        try:
            value = json.loads(manifest.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _reject("bundle manifest is unreadable") from error
        if not isinstance(value, dict):
            raise _reject("bundle manifest identity mismatch")
        manifest_value = cast(dict[str, Any], value)
        if manifest_value.get("bundle_id") != bundle_id:
            raise _reject("bundle manifest identity mismatch")
        plan = manifest_value.get("plan")
        entries_value = manifest_value.get("entries")
        if not isinstance(plan, dict) or not isinstance(entries_value, list):
            raise _reject("bundle manifest contents are incomplete")
        expected_files: set[Path] = {Path("bundle-manifest.json")}
        identity_entries: list[dict[str, object]] = []
        for raw_entry in cast(list[object], entries_value):
            if not isinstance(raw_entry, dict):
                raise _reject("bundle manifest entry is invalid")
            entry = cast(dict[str, object], raw_entry)
            raw_path, raw_size, raw_digest, coordinate = (
                entry.get("view_path"),
                entry.get("size"),
                entry.get("sha1"),
                entry.get("coordinate"),
            )
            if (
                not isinstance(raw_path, str)
                or not isinstance(raw_size, int)
                or not isinstance(raw_digest, str)
                or not isinstance(coordinate, str)
            ):
                raise _reject("bundle manifest entry fields are invalid")
            relative = _safe_relative(raw_path)
            expected_files.add(relative)
            installed = target / relative
            if not installed.is_file() or installed.is_symlink():
                raise _reject("bundle artifact is missing or is a symlink")
            size, digest = _sha1_file(installed)
            if size != raw_size or digest != raw_digest:
                raise _reject("bundle artifact failed size or digest verification")
            identity_entries.append(
                {
                    "view_path": relative.as_posix(),
                    "size": raw_size,
                    "sha1": raw_digest,
                    "coordinate": coordinate,
                }
            )
        actual_files = {
            path.relative_to(target)
            for path in target.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        if actual_files != expected_files:
            raise _reject("bundle contains an undeclared file")
        identity = {"plan": cast(dict[str, object], plan), "entries": identity_entries}
        if hashlib.sha256(_canonical_json(identity)).hexdigest() != bundle_id:
            raise _reject("bundle identity does not match its manifest contents")
        return target


class SessionOverlayStore:
    """Create a writable directory owned by exactly one session generation."""

    _DIRECTORIES = ("logs", "crash-reports", "server-resource-packs", "cache", "ipc", "mods")

    def __init__(self, root: Path) -> None:
        requested_root = root.absolute()
        if requested_root.is_symlink():
            raise _reject("session root cannot be a symlink", category=ErrorCategory.CONFIG)
        self.root = requested_root.resolve()
        if any(part.lower() == ".minecraft" for part in self.root.parts):
            raise _reject(
                "session root cannot live inside .minecraft", category=ErrorCategory.CONFIG
            )
        self.root.mkdir(parents=True, exist_ok=True)
        _assert_no_symlink(self.root, self.root)

    def create(self, session_id: str, generation: int) -> Path:
        session_id = _safe_component(session_id, "session_id")
        if generation < 1:
            raise _reject("generation must be positive", category=ErrorCategory.CONFIG)
        target = self.root / session_id / f"generation-{generation}"
        if target.exists():
            raise _reject("session overlay already exists", category=ErrorCategory.SESSION)
        _assert_no_symlink(target.parent, self.root)
        target.mkdir(parents=True)
        for name in self._DIRECTORIES:
            (target / name).mkdir()
        descriptor = target / "session.json"
        descriptor.write_bytes(
            _canonical_json(
                {"schema_version": 1, "session_id": session_id, "generation": generation}
            )
        )
        return target
