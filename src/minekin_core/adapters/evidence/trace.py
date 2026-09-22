"""Replaying a sealed bundle's own timeline, read once, held to what it declares.

Two entry points ask the same question of the same bytes: the frozen product command
`minekin replay <evidence-dir>`, and the standalone `tools/replay_evidence.py`. They
ask it here, in one place, because a second reading of a sealed record is a second
chance for the two to disagree about what it says — and a disagreement is exactly what
a reader of evidence is looking for.

The reading is ordered, and the order is the design:

1. the bundle is verified against itself (`verify_addressed_bundle`), so a manifest
   that does not match its own digest, an artifact that is not the bytes it was sealed
   as, and a file nobody declared are all refused before anything is parsed;
2. the timeline artifact is read and held to the size and digest *the manifest
   declares for it* — and the bytes that were checked are the bytes that are parsed,
   because checking one read and parsing another is a check of a file that could have
   changed in between;
3. only then is the timeline read, strictly: UTF-8, one JSON object per line, no blank
   lines, no repeated keys, and no numbers JSON does not have;
4. and only then are the moves it records folded through the frozen session table, by
   the domain — this layer decides nothing about what a session is.

Steps 1 and 2 are integrity, and they are `STORAGE`: the bytes on disk are not the
bytes that were sealed, or there are bytes nobody declared. Steps 3 and 4 are semantic,
and they are `SESSION`: the bundle is intact and the record inside it does not amount
to a session history. That classification is the domain's (`domain/replay.py`); what
lives here is the reading of files, and it is total — a bundle that cannot be read is
an answer about that bundle, never an exception that escapes as an internal fault.

The ordinary case today is worth naming on its own. A bundle sealed before Core's
ledger recorded *transitions* holds a timeline of things that happened and no move the
machine made. Nothing can be projected from it, and that is an answer rather than a
failure: the status is `semantic_incomplete`, the reason is `NO_STATE_TRANSITIONS`, and
no mapping from event names to states is derived to make it look as though something
had been checked.

Nothing here writes. A reader that could repair would be a reader whose verdict is
about a bundle nobody else has.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from minekin_core.adapters.evidence.bundle import BundleVerification, verify_addressed_bundle
from minekin_core.application.ports.event_store import JsonValue, payload_digest
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError
from minekin_core.domain.evidence import ArtifactRecord
from minekin_core.domain.replay import (
    IllegalSessionTransition,
    NoTransitionsRecorded,
    ReplayReason,
    ReplayRefused,
    ReplayStatus,
    SessionProjection,
    explicit_transitions,
    project_transitions,
    replay_category,
    replay_exit_code,
    replay_status,
)

#: The artifact a bundle seals its own timeline under. Declared here, where the reading
#: of that timeline lives, and imported from here by the sealer and the judge rather
#: than spelled again: a second spelling would not fail, it would read as "this run had
#: no timeline", which is a different and quieter answer.
LEDGER_TIMELINE_ARTIFACT = "bridge-trace.jsonl"


@dataclass(frozen=True, slots=True)
class BundleReplay:
    """What one sealed bundle's timeline yields, or the reason it yields nothing.

    The record is this layer's — the directory, the bytes it read, the bundle's own
    account of its violations. What the reading *means* is not: `category`, `status`
    and `exit_code` are the domain's classification of the reason, asked for here
    rather than decided here.
    """

    directory: Path
    #: The artifact this looked for, whether or not the manifest declared it.
    trace: str
    events: int
    #: What the bundle said about itself, as far as the reading got.
    run_id: str | None = None
    bundle_digest: str | None = None
    trace_sha256: str | None = None
    trace_size: int | None = None
    projection: SessionProjection | None = None
    reason: ReplayReason | None = None
    message: str = ""
    #: The bundle's own account of what is wrong with it, from `bundle.py`. Empty
    #: unless the bundle did not hold up.
    violations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (self.projection is None) == (self.reason is None):
            raise ValueError("a replay either projects or refuses, and never both or neither")

    @property
    def category(self) -> ErrorCategory | None:
        """Which bucket of the taxonomy this reading belongs to, if it refused."""

        return None if self.reason is None else replay_category(self.reason)

    @property
    def status(self) -> ReplayStatus:
        return replay_status(self.reason)

    @property
    def exit_code(self) -> ExitCode:
        return replay_exit_code(self.reason)

    def as_dict(self) -> dict[str, object]:
        category = self.category
        return {
            "schema_version": 1,
            "status": self.status.value,
            "category": None if category is None else category.value,
            "reason": None if self.reason is None else self.reason.value,
            "message": self.message,
            "run_id": self.run_id,
            "evidence_directory": str(self.directory),
            "bundle_digest": self.bundle_digest,
            "trace": self.trace,
            "trace_sha256": self.trace_sha256,
            "trace_size": self.trace_size,
            "events": self.events,
            "violations": list(self.violations),
            "projected": None if self.projection is None else self.projection.as_document(),
        }


class _Unreplayable(Exception):
    """An internal carrier: the reading stopped here, and this is why."""

    def __init__(self, reason: ReplayReason, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def replay_sealed_bundle(directory: Path) -> BundleReplay:
    """Read one sealed bundle's timeline, or say in which way it cannot be replayed.

    Never raises for a bundle it cannot replay: an operator asking whether a bundle can
    be replayed is owed an answer either way, and the answer carries the category that
    separates "these are not the bytes that were sealed" (`STORAGE`) from "these bytes
    are not a session history" (`SESSION`).

    The totality is deliberate. Everything this reads came off a disk and may have been
    written by anything — a digest file that is not ASCII, a manifest whose numbers are
    not numbers, a byte sequence that is not text at all — and an exception escaping
    from here would be reported as an internal fault, which is a claim about *this*
    process and not about the bundle. A bundle this cannot read is a storage finding
    about that bundle, so the last resort below says so instead.
    """

    reading = _Reading(directory=directory)
    try:
        return reading.replay()
    except _Unreplayable as stopped:
        return reading.refused(stopped)


def _unreadable(
    path: Path,
    error: Exception,
    reason: ReplayReason = ReplayReason.BUNDLE_CANNOT_BE_READ,
) -> _Unreplayable:
    """A read that failed the way reads fail, with the operating system's own words."""

    return _Unreplayable(reason, f"{path} cannot be read: {error}")


@dataclass(slots=True)
class _Reading:
    """The facts gathered on the way, so a reading that stopped can still report them."""

    directory: Path
    run_id: str | None = None
    bundle_digest: str | None = None
    trace_sha256: str | None = None
    trace_size: int | None = None
    events: int = 0
    violations: tuple[str, ...] = ()

    def replay(self) -> BundleReplay:
        verification = _verified(self.directory)
        manifest = verification.manifest
        self.run_id = None if manifest is None else manifest.test_run_id
        self.bundle_digest = verification.bundle_digest
        self.violations = verification.violations
        if not verification.verified:
            raise _Unreplayable(
                ReplayReason.BUNDLE_DOES_NOT_HOLD_UP,
                "the bundle does not hold up, so there is nothing to replay: "
                + ", ".join(self.violations),
            )

        declared = _declared_timeline(verification)
        payload = _read_timeline(self.directory / declared.path)
        self.trace_size = len(payload)
        self.trace_sha256 = _sha256(payload)
        # Both fields, and of the bytes that are about to be parsed rather than of the
        # ones the whole-bundle pass read a moment ago. The declared size is checked
        # here and not there: identical bytes cannot differ in length, so the bundle's
        # own pass is right to treat the digest as subsuming it — which is exactly why
        # a manifest whose size is wrong is only ever caught by this reading, and is
        # caught before a byte of it is parsed.
        if self.trace_size != declared.size or self.trace_sha256 != declared.sha256:
            raise _Unreplayable(
                ReplayReason.TIMELINE_IS_NOT_THE_BYTES_THAT_WERE_SEALED,
                f"{LEDGER_TIMELINE_ARTIFACT} is not the timeline that was sealed: the "
                f"manifest declares {declared.size} bytes hashing to {declared.sha256} and "
                f"the file is {self.trace_size} bytes hashing to {self.trace_sha256}",
            )

        rows = _rows(_decode(payload))
        self.events = len(rows)
        return self.projected(_project(rows))

    def refused(self, stopped: _Unreplayable) -> BundleReplay:
        return self._reported(reason=stopped.reason, message=stopped.message)

    def projected(self, projection: SessionProjection) -> BundleReplay:
        return self._reported(projection=projection)

    def _reported(
        self,
        *,
        projection: SessionProjection | None = None,
        reason: ReplayReason | None = None,
        message: str = "",
    ) -> BundleReplay:
        return BundleReplay(
            directory=self.directory,
            trace=LEDGER_TIMELINE_ARTIFACT,
            events=self.events,
            run_id=self.run_id,
            bundle_digest=self.bundle_digest,
            trace_sha256=self.trace_sha256,
            trace_size=self.trace_size,
            projection=projection,
            reason=reason,
            message=message,
            violations=self.violations,
        )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _verified(directory: Path) -> BundleVerification:
    """The bundle's own account of itself, or why it cannot be asked for one."""

    try:
        return verify_addressed_bundle(directory)
    except MinekinError as error:
        # `bundle.py` raises rather than returning a violation for material that is
        # not a bundle at all — a missing manifest, a manifest that is not JSON, a
        # schema that is not this one. Those are all one answer here.
        raise _Unreplayable(ReplayReason.NOT_A_BUNDLE, error.safe_message) from error
    except (OSError, UnicodeError) as error:
        raise _unreadable(directory, error) from error


def _declared_timeline(verification: BundleVerification) -> ArtifactRecord:
    """The record the manifest holds for the timeline, or why there is none to read."""

    manifest = verification.manifest
    for record in () if manifest is None else manifest.artifacts:
        if record.path == LEDGER_TIMELINE_ARTIFACT:
            return record
    raise _Unreplayable(
        ReplayReason.NO_TIMELINE_IS_DECLARED,
        f"the manifest declares no {LEDGER_TIMELINE_ARTIFACT} — this bundle holds nothing "
        "about the run's own timeline, so there is no event stream here to replay",
    )


def _read_timeline(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise _unreadable(path, error, ReplayReason.TIMELINE_CANNOT_BE_READ) from error


def _decode(payload: bytes) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _Unreplayable(
            ReplayReason.TIMELINE_IS_NOT_UTF8,
            f"{LEDGER_TIMELINE_ARTIFACT} is not UTF-8: {error}",
        ) from error


def _rows(text: str) -> tuple[Mapping[str, object], ...]:
    """The timeline, one event per line, read strictly.

    Split on `\\n` rather than with `str.splitlines` on purpose: the latter also breaks
    on U+2028 and its neighbours, which are legal *inside* a JSON string and would turn
    one event into two. `json.dumps` writes one row and a newline, so the last segment
    of a well-formed timeline is the file's terminator rather than a line — anything
    else that is empty is a line the sealer never wrote.
    """

    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    rows: list[Mapping[str, object]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            raise _Unreplayable(
                ReplayReason.TIMELINE_LINE_IS_BLANK,
                f"{LEDGER_TIMELINE_ARTIFACT} line {number} is blank, and a line the sealer "
                "never wrote is not one this can read past",
            )
        rows.append(_event(line, number))
    return tuple(rows)


def _event(line: str, number: int) -> Mapping[str, object]:
    what = f"{LEDGER_TIMELINE_ARTIFACT} line {number}"
    row = _strict_json(line, what)
    if not isinstance(row, Mapping):
        raise _Unreplayable(
            ReplayReason.TIMELINE_LINE_IS_NOT_AN_EVENT, f"{what} is not an event object"
        )
    return cast(Mapping[str, object], row)


def _strict_json(text: str, what: str) -> object:
    """Decode one JSON value without Python's duplicate or non-finite extensions."""

    try:
        row = json.loads(
            text, object_pairs_hook=_without_duplicate_keys, parse_constant=_json_constant
        )
        _reject_non_finite(row, what)
        _reject_unpaired_surrogates(row, what)
    except _Unreplayable as stopped:
        raise _Unreplayable(stopped.reason, f"{what}: {stopped.message}") from stopped
    except json.JSONDecodeError as error:
        raise _Unreplayable(
            ReplayReason.TIMELINE_LINE_IS_NOT_JSON, f"{what} is not JSON: {error}"
        ) from error
    return row


def _without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """A JSON object, refusing a name that appears twice.

    `json.loads` keeps the last of a repeated key, which reads a *different* record
    from the one that was sealed while reporting the same shape. There is no way to
    tell those apart afterwards, so the reading stops here.
    """

    found: dict[str, object] = {}
    for key, value in pairs:
        if key in found:
            raise _Unreplayable(
                ReplayReason.TIMELINE_LINE_HAS_A_DUPLICATE_KEY,
                f"{key!r} is named twice in one object, and last-one-wins would read a "
                "record the sealer never wrote",
            )
        found[key] = value
    return found


def _json_constant(name: str) -> object:
    """`parse_constant`, which the scanner calls for `NaN`, `Infinity` and `-Infinity`.

    Strict JSON has none of the three. A trace is a record, and a record whose numbers
    are not numbers is one no comparison can be made against afterwards.
    """

    raise _Unreplayable(
        ReplayReason.TIMELINE_LINE_HAS_A_NON_FINITE_NUMBER,
        f"{name} is not a JSON number",
    )


def _reject_non_finite(value: object, what: str) -> None:
    """Refuse any non-finite number, anywhere in a decoded event.

    `parse_constant` covers the three literals strict JSON does not have, and not the
    ordinary ones that overflow: `1e400` is well-formed JSON and `float` reads it as
    infinity, so a timeline could carry a number with no value and pass every check
    above this one. The walk is over the whole decoded value rather than its top level,
    because a number nested in a payload is exactly as unreadable as one that is not.
    """

    if isinstance(value, bool):
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise _Unreplayable(
            ReplayReason.TIMELINE_LINE_HAS_A_NON_FINITE_NUMBER,
            f"{what} holds {value!r}, which is not a number a record can be compared against",
        )
    if isinstance(value, Mapping):
        for item in cast(Mapping[str, object], value).values():
            _reject_non_finite(item, what)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in cast(Sequence[object], value):
            _reject_non_finite(item, what)


def _reject_unpaired_surrogates(value: object, what: str) -> None:
    """Reject strings that are not Unicode scalar values after JSON decoding."""

    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise _Unreplayable(
                ReplayReason.TIMELINE_LINE_IS_NOT_JSON,
                f"{what} contains an unpaired Unicode surrogate",
            )
        return
    if isinstance(value, Mapping):
        for key, item in cast(Mapping[object, object], value).items():
            _reject_unpaired_surrogates(key, what)
            _reject_unpaired_surrogates(item, what)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in cast(Sequence[object], value):
            _reject_unpaired_surrogates(item, what)


def _payload(row: Mapping[str, object], position: int) -> Mapping[str, object]:
    """Read and authenticate the payload stored in one real ledger row.

    `bridge-trace.jsonl` seals SQLite rows directly, so the payload is the canonical
    JSON string in `payload_json`, beside the digest the event store recorded for it.
    Reading synthetic top-level transition fields would leave this blind to every
    trace the sealer actually writes.
    """

    what = f"{LEDGER_TIMELINE_ARTIFACT} line {position}"
    encoded = row.get("payload_json")
    stored_hash = row.get("payload_hash")
    if not isinstance(encoded, str) or not isinstance(stored_hash, str):
        raise _Unreplayable(
            ReplayReason.TIMELINE_LINE_IS_NOT_AN_EVENT,
            f"{what} does not carry textual payload_json and payload_hash fields",
        )
    value = _strict_json(encoded, f"{what} payload_json")
    if not isinstance(value, Mapping):
        raise _Unreplayable(
            ReplayReason.TIMELINE_LINE_IS_NOT_AN_EVENT,
            f"{what} payload_json is not an event payload object",
        )
    actual_hash = payload_digest(cast(JsonValue, value))
    if actual_hash != stored_hash:
        raise _Unreplayable(
            ReplayReason.TIMELINE_PAYLOAD_HASH_MISMATCH,
            f"{what} payload_hash does not describe payload_json",
        )
    return cast(Mapping[str, object], value)


def _project(rows: Sequence[Mapping[str, object]]) -> SessionProjection:
    """Fold the moves the timeline records, as one classified outcome.

    The domain keeps its refusals apart — "this stream is not a replay", "the timeline
    records no move", "the machine and the timeline disagree" — and they stay apart
    here too, as separate reasons in one category rather than as one merged sentence.
    """

    try:
        payloads = tuple(_payload(row, position) for position, row in enumerate(rows, start=1))
        return project_transitions(explicit_transitions(payloads))
    except NoTransitionsRecorded as error:
        raise _Unreplayable(ReplayReason.NO_STATE_TRANSITIONS, str(error)) from error
    except ReplayRefused as error:
        raise _Unreplayable(ReplayReason.TIMELINE_IS_NOT_A_REPLAY, str(error)) from error
    except IllegalSessionTransition as error:
        raise _Unreplayable(
            ReplayReason.TIMELINE_JUMPED,
            f"{error} — the frozen table enumerates every legal move, so a jump means the "
            "record and the machine disagree and is not fast-forwarded over",
        ) from error


__all__ = [
    "LEDGER_TIMELINE_ARTIFACT",
    "BundleReplay",
    "ReplayReason",
    "ReplayStatus",
    "replay_sealed_bundle",
]
