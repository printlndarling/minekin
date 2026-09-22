"""Reading a sealed bundle's timeline: what it yields, and every way it refuses.

The module under test is the one both entry points read through, so what it refuses
matters as much as what it projects. The refusals come in two kinds and the tests keep
them apart on purpose: a bundle whose bytes are not the bytes that were sealed is a
`STORAGE` finding, and a bundle that holds up and records no session history is a
`SESSION` one. A report that merged them would be unreadable at the moment it mattered
— one says "fetch it again", the other says "this is what the record says".

Two of the claims here are about what a bundle's timeline is *not*. It is not the W00
fixture's dialect — a payload naming `state` is an ordinary record and folds into
nothing — and it is not a stream of event names to be interpreted: a move is read only
from a row that states `from`/`to`, and the state the record claims the move began in is
checked against the machine rather than believed.

The ordinary case today is the last one: a bundle sealed before the ledger recorded
transitions. It projects nothing, and that is a stable answer rather than a failure.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from bundle_support import (
    RUN_ID,
    declare_artifact_size,
    fixture_dialect,
    ledger_row,
    raw_payload_row,
    seal_bundle,
    transition_row,
    unseal_all,
    walk,
)
from minekin_core.adapters.evidence import trace
from minekin_core.adapters.evidence.bundle import (
    DIGEST_NAME,
    MANIFEST_NAME,
    BundleVerification,
    verify_addressed_bundle,
)
from minekin_core.adapters.evidence.trace import (
    LEDGER_TIMELINE_ARTIFACT,
    BundleReplay,
    replay_sealed_bundle,
)
from minekin_core.domain.errors import ErrorCategory, ExitCode
from minekin_core.domain.replay import ReplayReason, ReplayStatus, SessionProjection
from minekin_core.domain.session_state import SessionState


def bundle_with_timeline(
    root: Path,
    timeline: bytes,
    *,
    declare: bool = True,
    extra: Mapping[str, bytes] | None = None,
    sealed: bool = False,
) -> Path:
    """A sealed bundle holding this timeline, and whatever else a test needs beside it."""

    artifacts: dict[str, bytes] = {} if extra is None else dict(extra)
    if declare:
        artifacts[LEDGER_TIMELINE_ARTIFACT] = timeline
    return seal_bundle(root, artifacts, seal=sealed)


@pytest.fixture(autouse=True)
def _leave_bundles_writable(tmp_path: Path) -> Iterator[None]:
    """A sealed bundle is read-only, and the read-only bit stops cleanup."""

    yield
    unseal_all(tmp_path)


def test_a_declared_timeline_projects_and_the_report_names_the_bytes_it_read(
    tmp_path: Path,
) -> None:
    timeline = walk("STOPPED", "PREPARING", "STARTING_CLIENT")
    directory = bundle_with_timeline(tmp_path, timeline)

    replay = replay_sealed_bundle(directory)

    assert replay.status is ReplayStatus.PROJECTED
    assert replay.category is None
    assert replay.reason is None
    assert replay.exit_code is ExitCode.OK
    assert replay.projection is not None
    assert replay.projection.state is SessionState.STARTING_CLIENT
    assert replay.projection.last_event_position == 2
    assert replay.events == 2
    assert replay.run_id == RUN_ID
    assert replay.trace == LEDGER_TIMELINE_ARTIFACT
    assert replay.trace_size == len(timeline)
    assert replay.trace_sha256 == hashlib.sha256(timeline).hexdigest()
    assert replay.bundle_digest == (directory / DIGEST_NAME).read_text(encoding="ascii").strip()
    assert json.loads(json.dumps(replay.as_dict()))["projected"] == {
        "state": "STARTING_CLIENT",
        "last_event_position": 2,
    }


def test_a_directory_that_is_not_a_bundle_is_the_bundles_own_account(tmp_path: Path) -> None:
    """There is material here and it is not evidence, which is not a usage error."""

    directory = tmp_path / "run" / "evidence" / RUN_ID
    directory.mkdir(parents=True)

    replay = replay_sealed_bundle(directory)

    assert replay.reason is ReplayReason.NOT_A_BUNDLE
    assert replay.category is ErrorCategory.STORAGE
    assert replay.status is ReplayStatus.INVALID
    assert replay.exit_code is ExitCode.STORAGE
    assert str(directory) in replay.message


def test_a_digest_file_that_is_not_text_is_a_storage_finding_rather_than_a_crash(
    tmp_path: Path,
) -> None:
    """The seam is total: a bundle this cannot read is an answer about that bundle.

    `bundle.sha256` is read as ASCII, and a byte that is not ASCII raises out of the
    bundle's own verification. Reported as an internal fault that would be a claim about
    *this process*; what actually happened is that the bundle on disk is not the bundle
    that was sealed, which is storage — and it is the whole bundle, so nothing about the
    timeline is read at all.
    """

    directory = bundle_with_timeline(tmp_path, walk("STOPPED", "PREPARING"))
    (directory / DIGEST_NAME).write_bytes(b"\xff\xfe not a digest\n")

    replay = replay_sealed_bundle(directory)

    assert replay.status is ReplayStatus.INVALID
    assert replay.reason is ReplayReason.BUNDLE_CANNOT_BE_READ
    assert replay.category is ErrorCategory.STORAGE
    assert replay.exit_code is ExitCode.STORAGE
    assert replay.projection is None
    assert replay.events == 0
    assert "cannot be read" in replay.message


def test_an_unexpected_reader_bug_is_not_mislabeled_as_a_storage_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = bundle_with_timeline(tmp_path, walk("STOPPED", "PREPARING"))

    def broken(_: Path) -> BundleVerification:
        raise RuntimeError("programmer bug")

    monkeypatch.setattr(trace, "verify_addressed_bundle", broken)

    with pytest.raises(RuntimeError, match="programmer bug"):
        replay_sealed_bundle(directory)


def test_a_bundle_whose_manifest_cannot_be_read_is_storage_rather_than_a_crash(
    tmp_path: Path,
) -> None:
    directory = bundle_with_timeline(tmp_path, walk("STOPPED", "PREPARING"))
    (directory / MANIFEST_NAME).write_text("{not json", encoding="utf-8")

    replay = replay_sealed_bundle(directory)

    assert replay.reason is ReplayReason.NOT_A_BUNDLE
    assert replay.category is ErrorCategory.STORAGE


def test_a_manifest_that_declares_no_timeline_has_nothing_to_read(tmp_path: Path) -> None:
    """The bundle holds up and says nothing about the run's own timeline."""

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, b"", declare=False))

    assert replay.reason is ReplayReason.NO_TIMELINE_IS_DECLARED
    assert replay.category is ErrorCategory.STORAGE
    assert replay.events == 0


@pytest.mark.parametrize(
    "tampered",
    [
        # The same length, so only the digest can catch it.
        walk("STOPPED", "PREPARING").replace(b"PREPARING", b"PREPAREDX"),
        # A different length, which the declared size catches alongside it.
        walk("STOPPED", "PREPARING") + walk("STOPPED", "PLAYABLE"),
    ],
)
def test_a_tampered_timeline_is_refused_by_the_bundles_own_account(
    tmp_path: Path, tampered: bytes
) -> None:
    """The whole-bundle pass reads every declared artifact, so this is where it lands."""

    directory = bundle_with_timeline(tmp_path, walk("STOPPED", "PREPARING"))
    (directory / LEDGER_TIMELINE_ARTIFACT).write_bytes(tampered)

    replay = replay_sealed_bundle(directory)

    assert replay.reason is ReplayReason.BUNDLE_DOES_NOT_HOLD_UP
    assert replay.category is ErrorCategory.STORAGE
    assert f"ARTIFACT_DIGEST_MISMATCH:{LEDGER_TIMELINE_ARTIFACT}" in replay.violations


def test_a_timeline_that_changed_after_verification_is_never_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bytes that are parsed are the bytes that were checked.

    The window is narrow and real: the whole-bundle pass reads the artifact to hash it,
    and the reading reads it again to parse it. It is simulated here rather than raced,
    because a test that has to win a race passes for the wrong reason on the days it
    does not win it — and what is under test is what happens when the two reads
    disagree, not how likely they are to.
    """

    directory = bundle_with_timeline(tmp_path, walk("STOPPED", "PREPARING"))
    verified = verify_addressed_bundle(directory)
    (directory / LEDGER_TIMELINE_ARTIFACT).write_bytes(walk("STOPPED", "PLAYABLE"))

    def _as_verified(_: Path) -> BundleVerification:
        return verified

    monkeypatch.setattr(trace, "verify_addressed_bundle", _as_verified)

    replay = replay_sealed_bundle(directory)

    assert replay.reason is ReplayReason.TIMELINE_IS_NOT_THE_BYTES_THAT_WERE_SEALED
    assert replay.category is ErrorCategory.STORAGE
    assert replay.projection is None


def test_a_size_the_manifest_declares_wrongly_is_caught_before_anything_is_parsed(
    tmp_path: Path,
) -> None:
    """The bundle holds up against itself, and its own record of the timeline is wrong.

    Every digest in this bundle is real and `bundle.sha256` matches the manifest that
    carries them, so the whole-bundle pass is right to call it verified — it treats an
    artifact's digest as subsuming its recorded size, and identical bytes cannot differ
    in length. A manifest that disagrees with itself about a *length* is therefore only
    ever caught by the reading that checks both fields of the one artifact it is about,
    and caught before parsing: `events` is 0 because no row was ever read.
    """

    timeline = walk("STOPPED", "PREPARING", "STARTING_CLIENT")
    directory = bundle_with_timeline(tmp_path, timeline)
    declare_artifact_size(directory, LEDGER_TIMELINE_ARTIFACT, len(timeline) + 5)

    assert verify_addressed_bundle(directory).verified, "the wrong size is this bundle's own shape"

    replay = replay_sealed_bundle(directory)

    assert replay.reason is ReplayReason.TIMELINE_IS_NOT_THE_BYTES_THAT_WERE_SEALED
    assert replay.category is ErrorCategory.STORAGE
    assert replay.trace_size == len(timeline)
    assert replay.events == 0
    assert f"declares {len(timeline) + 5} bytes" in replay.message


def test_a_trace_the_manifest_never_declared_is_refused(tmp_path: Path) -> None:
    """Undeclared material beside the declared timeline is material nobody sealed."""

    directory = bundle_with_timeline(tmp_path, walk("STOPPED", "PREPARING"))
    (directory / f"{LEDGER_TIMELINE_ARTIFACT}.bak").write_bytes(walk("STOPPED", "PLAYABLE"))

    replay = replay_sealed_bundle(directory)

    assert replay.reason is ReplayReason.BUNDLE_DOES_NOT_HOLD_UP
    assert replay.category is ErrorCategory.STORAGE
    assert f"UNDECLARED_FILE:{LEDGER_TIMELINE_ARTIFACT}.bak" in replay.violations


def test_a_timeline_that_is_not_utf8_is_refused(tmp_path: Path) -> None:
    """The bytes are the declared bytes, so this is what they say, not what they are."""

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, b'{"event_type": "\xff\xfe"}\n'))

    assert replay.reason is ReplayReason.TIMELINE_IS_NOT_UTF8
    assert replay.category is ErrorCategory.SESSION


def test_a_line_that_is_not_json_is_refused(tmp_path: Path) -> None:
    truncated = b'{"event_type": "SessionPreparing"\n'

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, truncated))

    assert replay.reason is ReplayReason.TIMELINE_LINE_IS_NOT_JSON
    assert replay.category is ErrorCategory.SESSION
    assert "line 1" in replay.message


def test_a_ledger_payload_that_is_not_json_is_refused(tmp_path: Path) -> None:
    replay = replay_sealed_bundle(
        bundle_with_timeline(tmp_path, raw_payload_row('{"from":"STOPPED"'))
    )

    assert replay.reason is ReplayReason.TIMELINE_LINE_IS_NOT_JSON
    assert replay.category is ErrorCategory.SESSION
    assert "payload_json" in replay.message


def test_a_ledger_payload_whose_stored_hash_disagrees_is_refused(tmp_path: Path) -> None:
    timeline = raw_payload_row('{"from":"STOPPED","to":"PREPARING"}', payload_hash="f" * 64)

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, timeline))

    assert replay.reason is ReplayReason.TIMELINE_PAYLOAD_HASH_MISMATCH
    assert replay.category is ErrorCategory.STORAGE
    assert replay.exit_code is ExitCode.STORAGE
    assert replay.projection is None


def test_an_unpaired_surrogate_in_payload_json_is_a_semantic_refusal(tmp_path: Path) -> None:
    timeline = raw_payload_row('{"from":"STOPPED","to":"PREPARING","label":"\\ud800"}')

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, timeline))

    assert replay.reason is ReplayReason.TIMELINE_LINE_IS_NOT_JSON
    assert replay.category is ErrorCategory.SESSION
    assert "unpaired Unicode surrogate" in replay.message


def test_a_blank_line_is_refused_rather_than_skipped(tmp_path: Path) -> None:
    """The sealer writes one row per line, so a blank one is a line nobody wrote."""

    timeline = walk("STOPPED", "PREPARING") + b"\n" + walk("PREPARING", "STARTING_CLIENT")

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, timeline))

    assert replay.reason is ReplayReason.TIMELINE_LINE_IS_BLANK
    assert replay.category is ErrorCategory.SESSION
    assert "line 2" in replay.message


def test_a_key_named_twice_in_one_event_is_refused(tmp_path: Path) -> None:
    """Last-one-wins would read a different record from the one that was sealed."""

    timeline = raw_payload_row('{"from":"STOPPED","to":"PREPARING","to":"STARTING_CLIENT"}')

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, timeline))

    assert replay.reason is ReplayReason.TIMELINE_LINE_HAS_A_DUPLICATE_KEY
    assert replay.category is ErrorCategory.SESSION
    assert "'to'" in replay.message


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity"])
def test_a_number_json_does_not_have_is_refused(tmp_path: Path, number: str) -> None:
    """`json` reads these happily; a record whose numbers are not numbers compares with nothing."""

    timeline = raw_payload_row(f'{{"from":"STOPPED","to":"PREPARING","n":{number}}}')

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, timeline))

    assert replay.reason is ReplayReason.TIMELINE_LINE_HAS_A_NON_FINITE_NUMBER
    assert replay.category is ErrorCategory.SESSION


@pytest.mark.parametrize(
    "line",
    [
        # Well-formed JSON, and a number no float can hold: `json` reads every one of
        # these as infinity without a single one of the literals above appearing.
        raw_payload_row('{"from":"STOPPED","to":"PREPARING","elapsed_ms":1e400}'),
        raw_payload_row('{"from":"STOPPED","to":"PREPARING","readings":[1e400]}'),
        raw_payload_row('{"from":"STOPPED","to":"PREPARING","probe":{"at":{"x":-1e999}}}'),
    ],
)
def test_a_number_that_overflows_to_infinity_is_refused_wherever_it_is_nested(
    tmp_path: Path, line: bytes
) -> None:
    """A finite literal JSON allows and a float cannot hold is still a number with no value.

    The check is over the whole decoded record rather than its top level, because a
    number inside a payload is exactly as unreadable as one beside it.
    """

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, line))

    assert replay.reason is ReplayReason.TIMELINE_LINE_HAS_A_NON_FINITE_NUMBER
    assert replay.category is ErrorCategory.SESSION
    assert replay.projection is None
    assert "inf" in replay.message


def test_a_line_that_is_not_an_event_object_is_refused(tmp_path: Path) -> None:
    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, b"[1, 2, 3]\n"))

    assert replay.reason is ReplayReason.TIMELINE_LINE_IS_NOT_AN_EVENT
    assert replay.category is ErrorCategory.SESSION


def test_ordinary_rows_beside_a_move_are_not_refused_for_lacking_a_move(
    tmp_path: Path,
) -> None:
    """A timeline is a mixed ledger, and the ordinary rows in it are not failures.

    The move is the third row, so the projection's cursor is the row the move was
    recorded in rather than the number of moves — an ordinary row is read and is not a
    state, which is a different thing from being unreadable.
    """

    timeline = (
        ledger_row(event_type="SessionProcessStarted", payload={})
        + ledger_row(event_type="BridgeHelloAccepted", payload={"generation": 1})
        + transition_row("STOPPED", "PREPARING")
        + ledger_row(event_type="JoinObserved", payload={})
    )

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, timeline))

    assert replay.status is ReplayStatus.PROJECTED
    assert replay.events == 4
    assert replay.projection is not None
    assert replay.projection.state is SessionState.PREPARING
    assert replay.projection.last_event_position == 3


def test_the_fixtures_state_in_the_payload_is_not_read_as_a_ledger_move(tmp_path: Path) -> None:
    """The W00 dialect is a fixture's, and a bundle holding it folds into nothing.

    Reading `payload.state` as a move is what a bundle sealed before the ledger recorded
    transitions would do to look replayable: the states are there, the event types read
    like they mean them, and none of it is a record of a move. The stable answer is that
    this timeline records no transition.
    """

    replay = replay_sealed_bundle(
        bundle_with_timeline(tmp_path, fixture_dialect("PREPARING", "STARTING_CLIENT"))
    )

    assert replay.status is ReplayStatus.SEMANTIC_INCOMPLETE
    assert replay.reason is ReplayReason.NO_STATE_TRANSITIONS
    assert replay.category is ErrorCategory.SESSION
    assert replay.projection is None
    assert replay.events == 2


def test_a_bundle_that_records_no_transitions_is_stably_incomplete(tmp_path: Path) -> None:
    """The finding: Core's ledger says what happened, not where the session went.

    Stable is the whole of the claim, so it is read twice: the same bundle produces the
    same status, category and reason, and no mapping from event names to states is
    derived to make a projection out of it.
    """

    timeline = ledger_row(event_type="SessionProcessStarted", payload={}) + ledger_row(
        event_type="PlayableEstablished", payload={}
    )
    directory = bundle_with_timeline(tmp_path, timeline)

    first = replay_sealed_bundle(directory)
    second = replay_sealed_bundle(directory)

    assert first == second
    assert first.status is ReplayStatus.SEMANTIC_INCOMPLETE
    assert first.category is ErrorCategory.SESSION
    assert first.reason is ReplayReason.NO_STATE_TRANSITIONS
    assert first.exit_code is ExitCode.SESSION
    assert first.projection is None
    assert first.events == 2
    assert first.as_dict()["category"] == "SESSION"
    assert "records no transition" in first.message


def test_a_row_that_names_half_a_move_is_refused_rather_than_completed(tmp_path: Path) -> None:
    """Half a move is not a move, and reading it as one would invent the other half."""

    timeline = ledger_row(event_type="SessionStateTransitioned", payload={"from": "STOPPED"})

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, timeline))

    assert replay.reason is ReplayReason.TIMELINE_IS_NOT_A_REPLAY
    assert replay.category is ErrorCategory.SESSION
    assert "'to'" in replay.message


def test_a_move_that_names_something_that_is_not_a_state_is_refused(tmp_path: Path) -> None:
    timeline = transition_row("STOPPED", "PRETENDING")

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, timeline))

    assert replay.reason is ReplayReason.TIMELINE_IS_NOT_A_REPLAY
    assert replay.category is ErrorCategory.SESSION
    assert "'PRETENDING'" in replay.message


def test_a_recorded_move_that_began_somewhere_else_is_refused(tmp_path: Path) -> None:
    """The recorded `from` is checked against the machine rather than believed.

    A ledger whose own account of where a move began disagrees with every move before it
    is a record that does not add up, and the disagreement is reported instead of being
    played back over. The move here is legal *from* where it says it started, which is
    why the refusal has to be about the recorded source and not about the table.
    """

    timeline = transition_row("READY_MENU", "CONNECTING")

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, timeline))

    assert replay.reason is ReplayReason.TIMELINE_JUMPED
    assert replay.category is ErrorCategory.SESSION
    assert "records a move from READY_MENU" in replay.message
    assert "the session was at STOPPED" in replay.message


def test_a_timeline_that_jumps_is_refused_rather_than_fast_forwarded(tmp_path: Path) -> None:
    """The frozen table enumerates every legal move, so a jump is a disagreement."""

    replay = replay_sealed_bundle(bundle_with_timeline(tmp_path, walk("STOPPED", "PLAYABLE")))

    assert replay.reason is ReplayReason.TIMELINE_JUMPED
    assert replay.category is ErrorCategory.SESSION
    assert "STOPPED -> PLAYABLE" in replay.message


def test_reading_a_bundle_writes_nothing_and_leaves_it_sealed(tmp_path: Path) -> None:
    """A reader that could repair would be a reader whose verdict is about nobody's bundle."""

    directory = bundle_with_timeline(tmp_path, walk("STOPPED", "PREPARING"), sealed=True)
    before = _fingerprint(directory)

    replay = replay_sealed_bundle(directory)

    assert replay.status is ReplayStatus.PROJECTED
    assert _fingerprint(directory) == before
    assert all(mode & 0o222 == 0 for _, _, _, mode in before), "the seal is what was checked"


def _fingerprint(directory: Path) -> list[tuple[str, int, int, int]]:
    """Every file's name, size, mtime *and* permission bits, as they are now.

    The modes are part of it rather than decoration: a reader that opened what it read
    for writing would be a reader whose second reading is of different bytes, and a
    reader that quietly unsealed a bundle to look inside it would be one whose verdict is
    about a bundle nobody else has. Neither shows up in a size or a timestamp.
    """

    return [
        (
            path.relative_to(directory).as_posix(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
            path.stat().st_mode,
        )
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]


def test_every_reason_has_a_bucket_in_the_taxonomy() -> None:
    """A reason added without deciding whether it is about bytes or about meaning turns red."""

    for reason in ReplayReason:
        replay = BundleReplay(
            directory=Path("bundle"), trace=LEDGER_TIMELINE_ARTIFACT, events=0, reason=reason
        )

        assert replay.category in {ErrorCategory.STORAGE, ErrorCategory.SESSION}


def test_a_replay_either_projects_or_refuses() -> None:
    """The invariant behind `status`: half an answer is not an answer."""

    with pytest.raises(ValueError, match="either projects or refuses"):
        BundleReplay(directory=Path("bundle"), trace=LEDGER_TIMELINE_ARTIFACT, events=0)

    with pytest.raises(ValueError, match="either projects or refuses"):
        BundleReplay(
            directory=Path("bundle"),
            trace=LEDGER_TIMELINE_ARTIFACT,
            events=1,
            projection=SessionProjection(state=SessionState.PREPARING, last_event_position=1),
            reason=ReplayReason.TIMELINE_JUMPED,
        )
