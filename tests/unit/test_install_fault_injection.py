"""Install-time faults: a failed write must never become a visible artifact.

Every case asserts on the real filesystem — what exists under the store root,
in ``.staging`` and in ``quarantine`` after the fault, and what a *second*
store instance over the same root can see. The fault is injected in the test (a
read that dies, a write that answers ``ENOSPC``, an ``os.replace`` that fails);
no visibility or atomicity semantics in ``artifacts.py`` were changed to make
these cases reachable. A genuine disk-full filesystem is not reproduced here —
the ``ENOSPC`` arrives at the write call, which is recorded as untested scope.
"""

from __future__ import annotations

import errno
import hashlib
import io
import os
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any, BinaryIO

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.domain.errors import MinekinError

_CHUNK = 1024 * 1024
_REAL_PATH_OPEN = Path.open


def _payload() -> bytes:
    return (b"a" * _CHUNK) + (b"b" * _CHUNK) + b"c" * 4096


def _artifact(payload: bytes) -> Artifact:
    return Artifact(
        coordinate="example:demo:1",
        path="example/demo.jar",
        url="https://example.invalid/demo.jar",
        size=len(payload),
        sha1=hashlib.sha1(payload).hexdigest(),
    )


def _staging_state(store: ArtifactStore) -> tuple[list[Path], list[Path]]:
    return (
        sorted(store.staging.rglob("*")),
        sorted(store.quarantine.rglob("*")),
    )


class _DyingDownload(io.RawIOBase):
    """A download stream that fails after the first chunk has been written."""

    def __init__(self, payload: bytes, staging: Path) -> None:
        self._view = memoryview(payload)
        self._staging = staging
        self._chunks = 1
        self.observed: list[tuple[Path, int]] = []

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray | memoryview) -> int:  # type: ignore[override]
        if self._chunks <= 0:
            # Measured while the transaction is still open: the partial payload
            # has to really be on disk, or the cleanup below proves nothing.
            self.observed = [
                (path, path.stat().st_size)
                for path in sorted(self._staging.rglob("payload.part"))
                if path.is_file()
            ]
            raise OSError(errno.ENOSPC, "No space left on device (injected read)")
        self._chunks -= 1
        chunk = bytes(self._view[: len(buffer)])
        self._view = self._view[len(chunk) :]
        buffer[: len(chunk)] = chunk
        return len(chunk)


def _dying_download(payload: bytes, staging: Path) -> tuple[BinaryIO, _DyingDownload]:
    raw = _DyingDownload(payload, staging)
    return io.BufferedReader(raw), raw


class _PartialWriter:
    """Proxies the real staging file, then fails the next write with ``ENOSPC``."""

    def __init__(self, handle: IO[Any], path: Path) -> None:
        self._handle = handle
        self.path = path
        self.bytes_written = 0
        self.observed_size_at_failure = -1

    def write(self, data: bytes) -> int:
        if self.bytes_written:
            self._handle.flush()
            self.observed_size_at_failure = self.path.stat().st_size
            raise OSError(errno.ENOSPC, "No space left on device (injected write)")
        written = self._handle.write(data)
        self.bytes_written += written
        return written

    def flush(self) -> None:
        self._handle.flush()

    def fileno(self) -> int:
        return self._handle.fileno()

    def __enter__(self) -> _PartialWriter:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._handle.close()


def _fail_staging_writes_after_first(monkeypatch: pytest.MonkeyPatch) -> list[_PartialWriter]:
    writers: list[_PartialWriter] = []

    def open_(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> IO[Any] | _PartialWriter:
        handle: IO[Any] = _REAL_PATH_OPEN(self, mode, *args, **kwargs)
        if (
            ("w" in mode or "x" in mode)
            and self.name == "payload.part"
            and ".staging" in self.parts
        ):
            writer = _PartialWriter(handle, self)
            writers.append(writer)
            return writer
        return handle

    monkeypatch.setattr(Path, "open", open_)
    return writers


def _replace_only_the_publish(
    monkeypatch: pytest.MonkeyPatch,
    target: Path,
    on_rename: Callable[[Path], None],
) -> None:
    real_replace = os.replace

    def replace(source: Any, destination: Any) -> None:
        if Path(str(destination)) == target:
            on_rename(Path(str(source)))
            return
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", replace)


def test_the_same_install_with_no_injected_fault_publishes_once(tmp_path: Path) -> None:
    """Positive control: the fixture below is not what makes these runs fail."""

    payload = _payload()
    artifact = _artifact(payload)
    store = ArtifactStore(tmp_path / "artifacts")

    assert store.install(artifact, io.BytesIO(payload)) == store.path_for(artifact)
    assert store.path_for(artifact).read_bytes() == payload
    assert _staging_state(store) == ([], [])


def test_a_download_that_dies_midway_leaves_no_transaction_and_no_object(
    tmp_path: Path,
) -> None:
    payload = _payload()
    artifact = _artifact(payload)
    store = ArtifactStore(tmp_path / "artifacts")

    reader, raw = _dying_download(payload, store.staging)
    with pytest.raises(OSError, match="No space left"):
        store.install(artifact, reader)

    assert len(raw.observed) == 1, "the transaction never got as far as a partial write"
    _, partial_size = raw.observed[0]
    assert 0 < partial_size < len(payload)
    assert not store.path_for(artifact).exists()
    assert _staging_state(store) == ([], [])
    with pytest.raises(MinekinError, match="missing"):
        store.verify(artifact)


def test_a_reopened_store_sees_nothing_from_the_failed_install(tmp_path: Path) -> None:
    """A leaked transaction is the counterexample: the next session must not
    be able to read a fault as a fact."""

    payload = _payload()
    artifact = _artifact(payload)
    store = ArtifactStore(tmp_path / "artifacts")
    reader, _ = _dying_download(payload, store.staging)
    with pytest.raises(OSError):
        store.install(artifact, reader)

    reopened = ArtifactStore(tmp_path / "artifacts")

    assert _staging_state(reopened) == ([], [])
    assert not reopened.path_for(artifact).exists()
    with pytest.raises(MinekinError, match="missing"):
        reopened.verify(artifact)
    assert reopened.install(artifact, io.BytesIO(payload)).read_bytes() == payload


def test_a_write_that_answers_enospc_publishes_no_partial_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _payload()
    artifact = _artifact(payload)
    store = ArtifactStore(tmp_path / "artifacts")

    writers = _fail_staging_writes_after_first(monkeypatch)
    with pytest.raises(OSError, match="No space left"):
        store.install(artifact, io.BytesIO(payload))

    assert len(writers) == 1, "the injection never met the staging write"
    assert 0 < writers[0].observed_size_at_failure < len(payload)
    assert not store.path_for(artifact).exists()
    assert _staging_state(store) == ([], [])
    with pytest.raises(MinekinError, match="missing"):
        store.verify(artifact)

    monkeypatch.undo()
    assert store.install(artifact, io.BytesIO(payload)).read_bytes() == payload


def test_a_failing_publish_rename_leaves_no_half_visible_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _payload()
    artifact = _artifact(payload)
    store = ArtifactStore(tmp_path / "artifacts")
    target = store.path_for(artifact)
    seen: list[tuple[bool, int]] = []

    def fail(source: Path) -> None:
        seen.append((source.is_file(), source.stat().st_size))
        raise OSError(errno.EIO, "Input/output error (injected rename)")

    _replace_only_the_publish(monkeypatch, target, fail)
    with pytest.raises(OSError, match="Input/output error"):
        store.install(artifact, io.BytesIO(payload))

    assert seen == [(True, len(payload))], "the payload was not complete before the rename"
    assert not target.exists()
    assert _staging_state(store) == ([], [])
    with pytest.raises(MinekinError, match="missing"):
        store.verify(artifact)

    monkeypatch.undo()
    assert store.install(artifact, io.BytesIO(payload)) == target


def test_a_concurrent_writer_that_published_the_same_digest_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two installers, one object: the loser verifies the winner's bytes.

    ``os.replace`` answers ``FileExistsError`` only after the winner has
    published, so the branch under test has to return the *verified* object
    rather than the half-written transaction it was holding.
    """

    payload = _payload()
    artifact = _artifact(payload)
    store = ArtifactStore(tmp_path / "artifacts")
    target = store.path_for(artifact)

    def win_then_lose(source: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as stream:
            stream.write(payload)
        target.chmod(0o444)
        raise FileExistsError(errno.EEXIST, "target exists (injected race)")

    _replace_only_the_publish(monkeypatch, target, win_then_lose)

    assert store.install(artifact, io.BytesIO(payload)) == target
    assert target.read_bytes() == payload
    assert _staging_state(store) == ([], [])


def test_a_concurrent_writer_that_published_other_bytes_is_still_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The digest gate is not relaxed to make the race pass."""

    payload = _payload()
    artifact = _artifact(payload)
    store = ArtifactStore(tmp_path / "artifacts")
    target = store.path_for(artifact)

    def poison_then_lose(source: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"tampered by the other writer")
        raise FileExistsError(errno.EEXIST, "target exists (injected race)")

    _replace_only_the_publish(monkeypatch, target, poison_then_lose)

    with pytest.raises(MinekinError, match="digest"):
        store.install(artifact, io.BytesIO(payload))
    assert target.read_bytes() == b"tampered by the other writer"
    assert _staging_state(store) == ([], [])
