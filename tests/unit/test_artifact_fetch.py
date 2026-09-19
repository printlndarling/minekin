from __future__ import annotations

import hashlib
import http.server
import io
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from email.message import Message
from pathlib import Path
from typing import BinaryIO

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.fetch import ArtifactFetcher, UrlOpener, open_https
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.domain.errors import ErrorCategory, MinekinError

PAYLOAD = b"minecraft client bytes\n"


def artifact(payload: bytes = PAYLOAD, *, url: str = "https://example.invalid/a.jar") -> Artifact:
    return Artifact(
        coordinate="com.mojang:minecraft:1.21.4",
        path="versions/1.21.4/1.21.4.jar",
        url=url,
        size=len(payload),
        sha1=hashlib.sha1(payload).hexdigest(),
        kind="client",
    )


class FakeOpener:
    """Serves bytes from memory and counts calls, so tests never touch a socket."""

    def __init__(self, payload: bytes | BaseException = PAYLOAD) -> None:
        self.payload = payload
        self.calls: list[tuple[str, float]] = []

    def __call__(self, url: str, timeout: float) -> BinaryIO:
        self.calls.append((url, timeout))
        if isinstance(self.payload, BaseException):
            raise self.payload
        return io.BytesIO(self.payload)


class FlakyOpener:
    """Fails the first `failures` attempts, then serves the payload."""

    def __init__(
        self, payload: bytes = PAYLOAD, failures: int = 1, error: BaseException | None = None
    ) -> None:
        self.payload = payload
        self.failures = failures
        self.error = error or urllib.error.URLError(ConnectionResetError())
        self.calls = 0

    def __call__(self, url: str, timeout: float) -> BinaryIO:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return io.BytesIO(self.payload)


def fetcher(store: ArtifactStore, opener: UrlOpener, *, max_attempts: int = 3) -> ArtifactFetcher:
    return ArtifactFetcher(store, opener=opener, max_attempts=max_attempts)


def test_a_verified_artifact_is_installed_into_the_store(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    item = artifact()

    outcome = fetcher(store, FakeOpener()).fetch([item])

    assert outcome.complete
    assert outcome.installed == (item.coordinate,)
    assert outcome.reused == ()
    assert store.verify(item).read_bytes() == PAYLOAD


def test_an_artifact_already_in_the_store_is_not_downloaded_again(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    item = artifact()
    opener = FakeOpener()
    fetcher(store, opener).fetch([item])

    second = fetcher(store, opener).fetch([item])

    assert second.reused == (item.coordinate,)
    assert second.installed == ()
    assert len(opener.calls) == 1


def test_a_digest_mismatch_is_not_installed_and_is_not_retried(tmp_path: Path) -> None:
    """Re-downloading the same wrong bytes would fail the same check."""

    store = ArtifactStore(tmp_path / "store")
    item = artifact()
    opener = FakeOpener(b"tampered\n")

    outcome = fetcher(store, opener).fetch([item])

    assert not outcome.complete
    assert outcome.failed[0].category is ErrorCategory.SUPPLY_CHAIN
    assert len(opener.calls) == 1
    with pytest.raises(MinekinError):
        store.verify(item)


def test_a_mismatched_download_is_quarantined_rather_than_discarded(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")

    fetcher(store, FakeOpener(b"tampered\n")).fetch([artifact()])

    assert list(store.quarantine.iterdir()) != []


def test_a_transient_transport_failure_is_retried_then_recorded(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    opener = FlakyOpener(failures=99)

    outcome = fetcher(store, opener, max_attempts=3).fetch([artifact()])

    assert opener.calls == 3
    assert not outcome.complete
    assert outcome.failed[0].category is ErrorCategory.SUPPLY_CHAIN


def test_a_retry_that_succeeds_later_installs_the_artifact(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    item = artifact()
    opener = FlakyOpener(failures=1)

    outcome = fetcher(store, opener, max_attempts=3).fetch([item])

    assert outcome.complete
    assert outcome.installed == (item.coordinate,)
    assert store.verify(item).read_bytes() == PAYLOAD


def test_a_timeout_is_classified_as_a_timeout(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    opener = FakeOpener(TimeoutError("too slow"))

    outcome = fetcher(store, opener).fetch([artifact()])

    assert outcome.failed[0].category is ErrorCategory.TIMEOUT


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (urllib.error.HTTPError("u", 404, "not found", Message(), None), "HTTP 404"),
        (urllib.error.URLError(ConnectionRefusedError()), "connection failed"),
    ],
)
def test_a_transport_failure_is_reported_without_leaking_the_exception(
    tmp_path: Path, error: BaseException, reason: str
) -> None:
    store = ArtifactStore(tmp_path / "store")

    outcome = fetcher(store, FlakyOpener(failures=99, error=error), max_attempts=1).fetch(
        [artifact()]
    )

    assert reason in outcome.failed[0].reason


def test_one_failure_does_not_stop_the_rest_of_the_pass(tmp_path: Path) -> None:
    """Knowing everything that is missing is worth more than stopping at the first gap."""

    store = ArtifactStore(tmp_path / "store")
    good = artifact()
    bad = Artifact(
        coordinate="com.mojang:assets:missing",
        path="assets/missing",
        url="https://example.invalid/missing",
        size=4,
        sha1="0" * 40,
    )

    outcome = fetcher(store, FakeOpener()).fetch([bad, good])

    assert outcome.installed == (good.coordinate,)
    assert [failure.coordinate for failure in outcome.failed] == [bad.coordinate]


def test_the_outcome_document_is_evidence_ready(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")

    document = fetcher(store, FakeOpener()).fetch([artifact()]).as_document()

    assert document == {"complete": True, "installed": 1, "reused": 0, "failures": []}


def test_an_empty_pass_is_complete(tmp_path: Path) -> None:
    outcome = fetcher(ArtifactStore(tmp_path / "store"), FakeOpener()).fetch([])

    assert outcome.complete
    assert outcome.installed == ()


@pytest.mark.parametrize(
    "url",
    [
        "http://example.invalid/a.jar",
        "ftp://example.invalid/a.jar",
        "/relative/a.jar",
        "file:///etc/passwd",
    ],
)
def test_a_non_https_url_is_refused(url: str) -> None:
    with pytest.raises(MinekinError, match="not https") as raised:
        open_https(url, 1.0)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_a_url_carrying_credentials_is_refused() -> None:
    with pytest.raises(MinekinError, match="must not carry credentials"):
        open_https("https://user:secret@example.invalid/a.jar", 1.0)


def test_a_refused_url_never_reaches_the_network(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")
    item = artifact(url="http://example.invalid/a.jar")

    outcome = ArtifactFetcher(store, timeout_s=1.0).fetch([item])

    assert not outcome.complete
    assert outcome.failed[0].category is ErrorCategory.SUPPLY_CHAIN
    assert "not https" in outcome.failed[0].reason


def test_a_non_positive_timeout_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        ArtifactFetcher(ArtifactStore(tmp_path / "store"), timeout_s=0.0)


def test_zero_attempts_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        ArtifactFetcher(ArtifactStore(tmp_path / "store"), max_attempts=0)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        """Keep the test output clean."""


@pytest.fixture
def loopback_server(tmp_path: Path) -> Iterator[tuple[str, bytes]]:
    """A loopback HTTP server, to prove the real urllib transport works."""

    directory = tmp_path / "served"
    directory.mkdir()
    payload = b"served over loopback\n"
    (directory / "asset.bin").write_bytes(payload)

    def handler(*args: object, **kwargs: object) -> _QuietHandler:
        return _QuietHandler(*args, directory=str(directory), **kwargs)  # type: ignore[arg-type]

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/asset.bin", payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_the_real_opener_refuses_a_plain_http_endpoint(
    loopback_server: tuple[str, bytes],
) -> None:
    """The digest would still protect content, but a downgrade is refused outright."""

    url, _ = loopback_server

    with pytest.raises(MinekinError, match="not https"):
        open_https(url, 5.0)


def test_an_artifact_is_installed_from_a_real_http_response(
    tmp_path: Path, loopback_server: tuple[str, bytes]
) -> None:
    """The injected opener is the test seam; this exercises urllib itself."""

    url, payload = loopback_server
    store = ArtifactStore(tmp_path / "store")
    item = Artifact(
        coordinate="loopback:asset",
        path="asset.bin",
        url=url,
        size=len(payload),
        sha1=hashlib.sha1(payload).hexdigest(),
    )

    def loopback_opener(url: str, timeout: float) -> BinaryIO:
        # Same transport with the https policy relaxed, for a loopback fixture only.
        return urllib.request.urlopen(url, timeout=timeout)

    outcome = ArtifactFetcher(store, opener=loopback_opener, timeout_s=5.0).fetch([item])

    assert outcome.complete, outcome.as_document()
    assert store.verify(item).read_bytes() == payload


def _bundle(count: int) -> list[Artifact]:
    """`count` artifacts with distinct content, so no two share a store path."""

    items: list[Artifact] = []
    for index in range(count):
        payload = f"payload {index}".encode()
        items.append(
            Artifact(
                coordinate=f"asset:{index}",
                path=f"{index}.bin",
                url=f"https://example.invalid/{index}",
                size=len(payload),
                sha1=hashlib.sha1(payload).hexdigest(),
                kind="asset",
            )
        )
    return items


def _payloads(items: list[Artifact]) -> dict[str, bytes]:
    return {item.url: f"payload {item.url.rsplit('/', 1)[-1]}".encode() for item in items}


def test_a_pass_keeps_several_downloads_in_flight(tmp_path: Path) -> None:
    """A sequential pass over the reviewed bundle was measured in hours.

    The opener only returns once `jobs` of them are inside it at the same time,
    so a pass that fetches one artifact at a time cannot finish at all — which
    is what makes this a test of concurrency rather than of speed.
    """

    jobs = 4
    items = _bundle(12)
    payloads = _payloads(items)
    barrier = threading.Barrier(jobs, timeout=5.0)

    def opener(url: str, timeout: float) -> BinaryIO:
        del timeout
        barrier.wait()
        return io.BytesIO(payloads[url])

    store = ArtifactStore(tmp_path / "store")

    outcome = ArtifactFetcher(store, opener=opener, jobs=jobs).fetch(items)

    assert outcome.complete, outcome.as_document()
    assert len(outcome.installed) == 12
    assert store.verify(items[7]).read_bytes() == payloads[items[7].url]


def test_the_report_keeps_the_plans_order_however_the_workers_finish(tmp_path: Path) -> None:
    """Which artifacts failed must not depend on which worker happened to win."""

    items = _bundle(6)
    payloads = _payloads(items)

    def opener(url: str, timeout: float) -> BinaryIO:
        del timeout
        # The first artifact is the slowest, so completion order is not plan order.
        time.sleep(0.02 * (len(items) - int(url.rsplit("/", 1)[-1])))
        return io.BytesIO(payloads[url])

    store = ArtifactStore(tmp_path / "store")

    outcome = ArtifactFetcher(store, opener=opener, jobs=len(items)).fetch(items)

    assert outcome.installed == tuple(item.coordinate for item in items)
    assert outcome.reused == ()


def test_a_failure_is_reported_against_its_own_coordinate_in_plan_order(tmp_path: Path) -> None:
    items = _bundle(4)
    payloads = _payloads(items)
    broken = items[1].url

    def opener(url: str, timeout: float) -> BinaryIO:
        del timeout
        if url == broken:
            raise urllib.error.HTTPError(url, 404, "Not Found", Message(), None)  # type: ignore[arg-type]
        return io.BytesIO(payloads[url])

    store = ArtifactStore(tmp_path / "store")

    outcome = ArtifactFetcher(store, opener=opener, jobs=4).fetch(items)

    assert [failure.coordinate for failure in outcome.failed] == [items[1].coordinate]
    assert outcome.failed[0].reason == "HTTP 404"
    assert outcome.installed == (items[0].coordinate, items[2].coordinate, items[3].coordinate)


def test_one_worker_fetches_everything_and_still_reports_progress(tmp_path: Path) -> None:
    """The sequential path stays, because a bound of one is a legitimate bound."""

    items = _bundle(3)
    payloads = _payloads(items)
    seen: list[tuple[int, int]] = []
    store = ArtifactStore(tmp_path / "store")

    outcome = ArtifactFetcher(
        store, opener=lambda url, timeout: io.BytesIO(payloads[url]), jobs=1
    ).fetch(items, on_progress=lambda done, total: seen.append((done, total)))

    assert outcome.complete
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_progress_counts_each_artifact_once_and_calls_back_from_the_calling_thread(
    tmp_path: Path,
) -> None:
    """Workers fetch; this thread reports, so a caller may print from the callback."""

    items = _bundle(12)
    payloads = _payloads(items)
    seen: list[tuple[int, int]] = []
    callers: list[threading.Thread] = []
    store = ArtifactStore(tmp_path / "store")

    def progress(done: int, total: int) -> None:
        seen.append((done, total))
        callers.append(threading.current_thread())

    ArtifactFetcher(store, opener=lambda url, timeout: io.BytesIO(payloads[url]), jobs=4).fetch(
        items, on_progress=progress
    )

    assert [done for done, _ in seen] == list(range(1, 13))
    assert {total for _, total in seen} == {12}
    assert set(callers) == {threading.current_thread()}


def test_a_job_count_below_one_is_refused(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "store")

    with pytest.raises(ValueError, match="jobs"):
        ArtifactFetcher(store, jobs=0)
