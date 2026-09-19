"""Fetching reviewed artifacts into the content-addressed store.

The upstream host is trusted only to be the place the pinned URL points at. Its
bytes are checked against the pinned size and SHA-1 by the store before anything
is published, and a mismatch is quarantined rather than stored, so a hostile or
merely broken mirror cannot put content into the cache.

Downloads run a few at a time, and the number is a parameter rather than a
property of the loop. Measured against the reviewed p0-core bundle, a sequential
pass over its 3,970 missing artifacts took about 2.9 seconds each — nearly three
hours — while moving roughly 35 KB/s, which is to say it was waiting on round
trips and not on the link. Concurrency is still bounded: every artifact is
verified by the store before it is published, a failure is still reported against
the coordinate that caused it, and an interrupted pass still resumes by finding
what is already present.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import BinaryIO, Protocol, cast

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_JOBS = 8


class UrlOpener(Protocol):
    """Opens a URL for reading. Injected so tests never touch the network."""

    def __call__(self, url: str, timeout: float) -> BinaryIO: ...


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.fetch",
        "download",
        ErrorCategory.SUPPLY_CHAIN,
        Retryability.OPERATOR_ACTION,
        message,
    )


def open_https(url: str, timeout: float) -> BinaryIO:
    """The real opener: HTTPS only, and no scheme downgrade behind a redirect."""

    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        raise _reject(f"artifact URL is not https: {parsed.scheme or 'no scheme'}")
    if parsed.username or parsed.password:
        raise _reject("artifact URL must not carry credentials")
    response = urllib.request.urlopen(url, timeout=timeout)
    final_url: str = str(response.geturl())
    final = urllib.parse.urlsplit(final_url)
    if final.scheme != "https":
        response.close()
        raise _reject(f"artifact URL was redirected away from https: {final.scheme}")
    return cast(BinaryIO, response)


@dataclass(frozen=True, slots=True)
class FetchFailure:
    coordinate: str
    url: str
    category: ErrorCategory
    reason: str


@dataclass(frozen=True, slots=True)
class _Outcome:
    """What one artifact did, kept per artifact so the report can stay ordered."""

    coordinate: str
    reused: bool
    failure: FetchFailure | None


@dataclass(frozen=True, slots=True)
class FetchOutcome:
    """What a fetch pass installed, reused, or could not obtain."""

    installed: tuple[str, ...]
    reused: tuple[str, ...]
    failed: tuple[FetchFailure, ...]

    @property
    def complete(self) -> bool:
        return not self.failed

    def as_document(self) -> dict[str, object]:
        return {
            "complete": self.complete,
            "installed": len(self.installed),
            "reused": len(self.reused),
            "failures": [
                {
                    "coordinate": failure.coordinate,
                    "url": failure.url,
                    "category": failure.category.value,
                    "reason": failure.reason,
                }
                for failure in self.failed
            ],
        }


def _classify(error: BaseException) -> ErrorCategory:
    if isinstance(error, MinekinError):
        return error.category
    if isinstance(error, TimeoutError):
        return ErrorCategory.TIMEOUT
    return ErrorCategory.SUPPLY_CHAIN


def _reason(error: BaseException) -> str:
    if isinstance(error, MinekinError):
        return error.safe_message
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, urllib.error.URLError):
        return f"connection failed: {type(error.reason).__name__}"
    return type(error).__name__


class ArtifactFetcher:
    """One verified pass over a plan's artifacts."""

    def __init__(
        self,
        store: ArtifactStore,
        *,
        opener: UrlOpener = open_https,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        jobs: int = DEFAULT_JOBS,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if jobs < 1:
            raise ValueError("jobs must be at least one")
        self._store = store
        self._opener = opener
        self._timeout_s = timeout_s
        self._max_attempts = max_attempts
        self._jobs = jobs

    def fetch(
        self,
        artifacts: Sequence[Artifact],
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> FetchOutcome:
        """Install every artifact that is not already verified, collecting failures.

        A failure does not stop the pass: knowing all of what is missing is worth
        more than stopping at the first gap, and the caller refuses to launch
        unless the outcome is complete. The report keeps the plan's order, so
        which artifacts failed does not depend on which worker finished first.

        `on_progress` is called after each artifact with (done, total). Filling
        the reviewed bundle is thousands of requests and hours of them, so a
        caller that can show its own progress should be able to; nothing here
        prints.
        """

        if self._jobs == 1:
            outcomes: list[_Outcome] = []
            for artifact in artifacts:
                outcomes.append(self._one(artifact))
                if on_progress is not None:
                    on_progress(len(outcomes), len(artifacts))
        else:
            # Workers never contend for a path: the store publishes each blob
            # under a name only that artifact's content can produce. What is
            # shared here is the progress callback, and it is called from this
            # thread as futures complete, not from the workers themselves.
            ordered: list[_Outcome | None] = [None] * len(artifacts)
            with ThreadPoolExecutor(max_workers=self._jobs) as pool:
                futures = {
                    pool.submit(self._one, artifact): index
                    for index, artifact in enumerate(artifacts)
                }
                for completed, future in enumerate(as_completed(futures), start=1):
                    ordered[futures[future]] = future.result()
                    if on_progress is not None:
                        on_progress(completed, len(artifacts))
            outcomes = [outcome for outcome in ordered if outcome is not None]

        installed = [
            outcome.coordinate
            for outcome in outcomes
            if outcome.failure is None and not outcome.reused
        ]
        reused = [outcome.coordinate for outcome in outcomes if outcome.reused]
        failed = [outcome.failure for outcome in outcomes if outcome.failure is not None]
        return FetchOutcome(installed=tuple(installed), reused=tuple(reused), failed=tuple(failed))

    def _one(self, artifact: Artifact) -> _Outcome:
        """Fetch one artifact if it is not already here, and say what happened."""

        try:
            self._store.verify(artifact)
        except MinekinError:
            error = self._attempt(artifact)
            if error is None:
                return _Outcome(artifact.coordinate, reused=False, failure=None)
            return _Outcome(
                artifact.coordinate,
                reused=False,
                failure=FetchFailure(
                    coordinate=artifact.coordinate,
                    url=artifact.url,
                    category=_classify(error),
                    reason=_reason(error),
                ),
            )
        return _Outcome(artifact.coordinate, reused=True, failure=None)

    def _attempt(self, artifact: Artifact) -> BaseException | None:
        """Return the failure, or None when the artifact was installed.

        Only transport errors are retried. A policy refusal or a digest mismatch
        is returned on the first attempt, because the same bytes would fail the
        same check and re-downloading them three times only wastes the mirror.
        """

        last: BaseException | None = None
        for _ in range(self._max_attempts):
            try:
                with self._opener(artifact.url, self._timeout_s) as source:
                    self._store.install(artifact, source)
            except MinekinError as error:
                return error
            except BaseException as error:
                last = error
                continue
            return None
        return last
