# pyright: reportUnknownMemberType=false

"""The fault-injection record: its shape, and the reader that refuses a bad one.

The record is what makes "a fault was injected" a fact rather than a claim. It is
written by `tools/inject_fault.py` during a run and read back by the sealer, so
two things have to hold and neither is checkable from the record alone: the
record must be complete enough to be judged, and it must be *refused* rather than
read when it is not.

The shapes here are the ones the helper produces — a killed runtime, and a kill
that never landed — rather than invented ones, because the validator exists to
reject the second kind of document and a fixture that could not occur would test
nothing.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import stat
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPOSITORY_ROOT / "schemas" / "fault-injection.schema.json"

CASE_ID = "CORE-060"
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
KIN_ID = "kin-01"
SESSION_ID = "f030bbeadf464c188c2921ede35e4c9f"
DIGEST = "b" * 64


def load(name: str) -> ModuleType:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module(f"tools.{name}")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


RECORD = load("fault_injection")


def as_json(document: object) -> Any:
    """The one place a document becomes the loosely typed thing `jsonschema` wants.

    Its own annotations take a recursive union this codebase does not model, and
    `jsonschema` is a test-only dependency, so the conversion is made once here
    rather than by loosening every call site.
    """

    return json.loads(json.dumps(document))


#: A real client's command line, abbreviated to the parts that matter here: the
#: Fabric main class as its own element, and the empty option values the frozen
#: offline launch passes beside their options.
CLIENT_ARGV = [
    "/opt/java/openjdk/bin/java",
    "-Djava.library.path=/data/session/generation-1/natives",
    "-cp",
    "/data/artifact-store/blobs/sha1/aa/a.jar:/data/bundle/b.jar",
    "net.fabricmc.loader.impl.launch.knot.KnotClient",
    "--username",
    "Kin",
    "--uuid",
    "8f40376bc23f3ef1b5535564eea75639",
    "--accessToken",
    "0",
    "--clientId",
    "",
    "--xuid",
    "",
]


def target() -> dict[str, object]:
    executable = "/usr/bin/python3.12"
    argv = ["python", "-m", "minekin_core", "session", "start"]
    identity_digest = hashlib.sha256(
        (executable + "\0" + "\0".join(argv)).encode("utf-8")
    ).hexdigest()
    return {
        "role": "runtime_controller",
        "pid": 4242,
        "starttime_ticks": 5551212,
        "state": "R",
        "comm": "python3",
        "pid_namespace_inode": "pid:[4026531836]",
        "exe_path": executable,
        "cmdline": argv,
        "identity_digest": identity_digest,
        "parent": {"pid": 4200, "comm": "xvfb-run", "starttime_ticks": 5551000},
    }


def sample() -> dict[str, object]:
    """The document an injected runtime kill produces, as the helper writes it."""

    return {
        "schema_version": 1,
        "case": {"case_id": CASE_ID, "case_version": DIGEST},
        "attribution": {
            "kin_id": KIN_ID,
            "run_id": RUN_ID,
            "session_id": SESSION_ID,
            "generation": 1,
        },
        "target": target(),
        "signal": {"name": "SIGKILL", "number": 9, "result": "DELIVERED", "error": None},
        "outcome": "INJECTED",
        "reasons": [],
        "confirmation_strength": "IDENTITY_DISAPPEARED",
        "confirmation": {
            "method": "PROC_ENTRY_ABSENT",
            "observations": 3,
            "pid_reused": False,
            "wait_status_available": False,
        },
        "attempted_at_monotonic_ns": 1_700_000_000_123,
        "confirmed_at_monotonic_ns": 1_700_000_000_456,
        "recorded_at_monotonic_ns": 1_700_000_000_500,
        "supervisor": {
            "pid": 4200,
            "role": "runtime_controller_root",
            "starttime_ticks": 5551000,
            "pid_namespace_inode": "pid:[4026531836]",
            "exit_status": None,
            "observed": False,
        },
    }


def changed(**overrides: object) -> dict[str, object]:
    """The sample with top-level fields replaced."""

    document = copy.deepcopy(sample())
    document.update(overrides)
    return document


def not_injected(**overrides: object) -> dict[str, object]:
    """A kill that did not land: no candidate, so nothing was signalled."""

    document = copy.deepcopy(sample())
    document.update(
        {
            "target": None,
            "signal": None,
            "outcome": "AMBIGUOUS",
            "reasons": ["NO_CANDIDATE_FOR_ROLE:runtime_controller"],
            "confirmation_strength": "NONE",
            "confirmation": None,
            "confirmed_at_monotonic_ns": None,
        }
    )
    document.update(overrides)
    return document


def codes(document: object) -> tuple[str, ...]:
    return cast(tuple[str, ...], RECORD.validate(document))


def nested(document: dict[str, object], key: str, **fields: object) -> dict[str, object]:
    section = dict(cast(dict[str, object], document[key]))
    section.update(fields)
    document[key] = section
    return document


def test_the_record_a_kill_produces_is_the_record_the_reader_accepts() -> None:
    assert codes(sample()) == ()


def test_a_kill_that_never_landed_is_a_legal_document_too() -> None:
    """One that did not happen is still recorded: the absence is the evidence."""

    assert codes(not_injected()) == ()


def test_an_empty_argv_element_is_part_of_a_usable_identity() -> None:
    """Measured on a real client: an empty option value is its own argv element.

    The launcher's rule is that an empty value travels beside its option rather
    than as an absent one, so the managed client's command line really does hold
    empty elements. Requiring every element to be non-empty made that process —
    and every refusal that named it — impossible to record.
    """

    document = with_argv(CLIENT_ARGV)

    assert codes(document) == ()
    assert list(schema_validator().iter_errors(as_json(document))) == []


def test_a_refusal_that_names_a_target_is_a_record_like_any_other() -> None:
    """The reader asked for the reason for refusing, and it was being lost.

    A refusal that has already read the target's identity carries it — so the
    document is validated before it is written, and anything invalid in that
    identity turns "the identity changed before the signal" into a bare
    "INVALID_TARGET" that never reaches the harness's log. Measured: that is
    exactly what a client kill produced, so the reason never got out.
    """

    client = cast(dict[str, object], with_argv(CLIENT_ARGV)["target"])
    refused = not_injected(
        target=client,
        reasons=["ROOT_IDENTITY_CHANGED_BEFORE_SIGNAL"],
    )

    assert codes(refused) == ()
    assert list(schema_validator().iter_errors(as_json(refused))) == []


def with_argv(argv: list[str]) -> dict[str, object]:
    """The sample kill with another command line, its digest recomputed."""

    document = copy.deepcopy(sample())
    section = cast(dict[str, object], document["target"])
    section["cmdline"] = argv
    section["identity_digest"] = hashlib.sha256(
        (cast(str, section["exe_path"]) + "\0" + "\0".join(argv)).encode("utf-8")
    ).hexdigest()
    return document


def schema_validator() -> Draft202012Validator:
    """The frozen schema as a validator, built where it is used."""

    return Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_the_schema_file_describes_the_record_the_reader_accepts() -> None:
    """The frozen schema and the hand-written validator must not drift apart.

    The validator is the contract — `jsonschema` is a test-only dependency and
    the runner image does not have it — so the schema is the written form of the
    same rules, and a record the reader accepts has to be one it accepts.
    """

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    assert list(validator.iter_errors(as_json(sample()))) == []


@pytest.mark.parametrize(
    ("document", "code"),
    [
        (changed(schema_version=2), "SCHEMA_VERSION_UNSUPPORTED"),
        (changed(outcome="MAYBE"), "INVALID_OUTCOME"),
        (changed(reasons="TARGET_SURVIVED_SIGKILL"), "INVALID_REASONS"),
        (changed(confirmation_strength="PROBABLY"), "INVALID_CONFIRMATION_STRENGTH"),
        (changed(attempted_at_monotonic_ns="soon"), "INVALID_CLOCK"),
        ({**sample(), "extra": 1}, "UNKNOWN_FIELD"),
        ({key: value for key, value in sample().items() if key != "signal"}, "MISSING_FIELD"),
        # A case section that is present, names its case, and carries a version
        # that is not a digest. Well shaped, so this is once more a rule about the
        # value: a version nothing can be compared against is not a version.
        (nested(changed(), "case", case_version="not-a-digest"), "INVALID_CASE"),
        # The section is present and well shaped, so this is the reader's own rule
        # rather than the schema's: a generation starts at one, and attribution to
        # generation zero names a run that never existed.
        (nested(changed(), "attribution", generation=0), "INVALID_ATTRIBUTION"),
        # A signal that says it was delivered and also says why it failed. The two
        # fields are one claim — `_signal_is_usable` holds them together — and a
        # record carrying both contradicts itself about the same moment.
        (nested(changed(), "signal", error="EPERM"), "INVALID_SIGNAL"),
    ],
)
def test_a_malformed_record_is_refused_by_code(document: dict[str, object], code: str) -> None:
    assert code in codes(document)


def structural_mutations() -> list[dict[str, object]]:
    return [
        changed(schema_version=2),
        changed(outcome="MAYBE"),
        changed(reasons="TARGET_SURVIVED_SIGKILL"),
        changed(confirmation_strength="PROBABLY"),
        changed(attempted_at_monotonic_ns="soon"),
        {**sample(), "extra": 1},
        {key: value for key, value in sample().items() if key != "signal"},
        # These three carry rules the reader enforces on values rather than on
        # structure, and the schema can speak to them too — measured, it refuses
        # all three — so they belong in the agreement this test is about.
        nested(changed(), "case", case_version="not-a-digest"),
        nested(changed(), "attribution", generation=0),
        nested(changed(), "signal", error="EPERM"),
    ]


def test_the_schema_refuses_everything_the_reader_refuses_structurally() -> None:
    """Two descriptions of one shape: where the schema can speak, it must agree.

    The reader is the contract and the schema is its written form, so a document
    the reader rejects for a structural reason has to be one the schema rejects
    too — otherwise the file that readers consult has drifted.
    """

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    for document in structural_mutations():
        assert codes(document) != (), document
        assert list(validator.iter_errors(as_json(document))) != [], document


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("target", "role", "launcher"),
        ("target", "pid", 1),
        ("target", "pid", "4242"),
        ("target", "starttime_ticks", -1),
        ("target", "pid_namespace_inode", "4026531836"),
        ("target", "identity_digest", "short"),
        ("target", "cmdline", []),
        ("signal", "name", "SIGTERM"),
        ("signal", "number", 15),
        ("signal", "result", "MAYBE"),
        ("attribution", "generation", 0),
        ("attribution", "run_id", ""),
    ],
)
def test_a_malformed_field_is_refused(section: str, field: str, value: object) -> None:
    assert codes(nested(copy.deepcopy(sample()), section, **{field: value})) != ()


def test_the_clock_relation_is_enforced_rather_than_trusted() -> None:
    """A confirmation stamped before the attempt is not an ordering, it is noise."""

    backwards = changed(confirmed_at_monotonic_ns=1_700_000_000_000)

    assert codes(backwards) == ("CLOCK_ORDER_INVALID",)


def test_the_outcome_must_match_what_was_observed() -> None:
    """Three claims have to agree: the outcome, the signal, and the confirmation.

    Each of these is a document that says "injected" while its own fields say
    otherwise, which is exactly the failure the whole record exists to prevent.
    """

    assert "CONFIRMATION_NOT_FOR_THIS_OUTCOME" in codes(changed(confirmed_at_monotonic_ns=None))
    assert "CONFIRMATION_NOT_FOR_THIS_OUTCOME" in codes(
        nested(copy.deepcopy(sample()), "signal", result="FAILED", error="ESRCH")
    )
    assert "REASONS_NOT_FOR_THIS_OUTCOME" in codes(changed(reasons=["TARGET_SURVIVED_SIGKILL"]))
    assert "CONFIRMATION_NOT_FOR_THIS_OUTCOME" in codes(changed(confirmation_strength="NONE"))


def test_identity_digest_and_role_relationships_are_not_trusted_blindly() -> None:
    assert "INVALID_TARGET" in codes(
        nested(copy.deepcopy(sample()), "target", identity_digest="0" * 64)
    )
    assert "SUPERVISOR_ROLE_MISMATCH" in codes(
        nested(copy.deepcopy(sample()), "supervisor", role="server_jvm_root")
    )
    assert "INVALID_CONFIRMATION" in codes(
        nested(copy.deepcopy(sample()), "confirmation", method="PROC_PID_REUSED", pid_reused=False)
    )


def test_a_claim_that_did_not_land_must_say_why() -> None:
    assert "REASONS_MISSING" in codes(not_injected(reasons=[]))
    assert "CONFIRMATION_NOT_FOR_THIS_OUTCOME" in codes(
        not_injected(confirmation_strength="IDENTITY_DISAPPEARED")
    )


def test_an_ambiguous_document_may_not_carry_a_signal() -> None:
    """Ambiguity is decided before the signal, so a delivered one contradicts it."""

    assert "CONFIRMATION_NOT_FOR_THIS_OUTCOME" in codes(
        not_injected(signal={"name": "SIGKILL", "number": 9, "result": "DELIVERED", "error": None})
    )


def test_the_supervisor_exit_status_is_absent_or_recorded_but_never_implied() -> None:
    """The helper is not the supervisor's parent, so it says `not observed`."""

    assert "INVALID_SUPERVISOR" in codes(
        nested(copy.deepcopy(sample()), "supervisor", observed=True, exit_status=None)
    )
    assert "INVALID_SUPERVISOR" in codes(
        nested(copy.deepcopy(sample()), "supervisor", observed=False, exit_status=137)
    )
    assert (
        codes(nested(copy.deepcopy(sample()), "supervisor", observed=True, exit_status=137)) == ()
    )


def test_a_wait_status_strength_is_not_something_this_helper_may_claim() -> None:
    """`IDENTITY_DISAPPEARED` is the honest strength when there is no `waitpid`."""

    claimed = changed(
        confirmation_strength="WAIT_STATUS",
        confirmation={
            "method": "PROC_ENTRY_ABSENT",
            "observations": 1,
            "pid_reused": False,
            "wait_status_available": True,
        },
    )

    assert "WAIT_STATUS_UNAVAILABLE" in codes(claimed)


class _Link:
    """A `lstat` answer that says "symlink", whatever the filesystem can do.

    Windows will not always let a test create a real symlink, and the point of
    the check is the reader's behaviour rather than the host's privileges.
    """

    st_mode = stat.S_IFLNK | 0o777


def _symlink_lstat(self: Path) -> _Link:
    return _Link()


def test_a_symlinked_record_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "fault-injection.json"
    path.write_bytes(RECORD.dump_record(sample()))
    monkeypatch.setattr("pathlib.Path.lstat", _symlink_lstat)

    with pytest.raises(RECORD.FaultInjectionError, match="SYMLINK"):
        RECORD.read_record(path)


def test_a_record_swapped_between_lstat_and_open_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "fault-injection.json"
    path.write_bytes(RECORD.dump_record(sample()))
    original = path.stat()
    real_fstat = RECORD.os.fstat

    def changed_fstat(descriptor: int) -> object:
        opened = real_fstat(descriptor)

        class Changed:
            st_mode = opened.st_mode
            st_dev = original.st_dev
            st_ino = original.st_ino + 1

        return Changed()

    monkeypatch.setattr(RECORD.os, "fstat", changed_fstat)

    with pytest.raises(RECORD.FaultInjectionError, match="CHANGED"):
        RECORD.read_record(path)


def test_a_record_that_is_not_json_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "fault-injection.json"
    path.write_bytes(b"not json")

    with pytest.raises(RECORD.FaultInjectionError, match="NOT_JSON"):
        RECORD.read_record(path)


def test_a_record_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "fault-injection.json"
    path.write_bytes(b"[1, 2, 3]")

    with pytest.raises(RECORD.FaultInjectionError, match="NOT_AN_OBJECT"):
        RECORD.read_record(path)


def test_a_missing_record_is_refused_rather_than_read_as_empty(tmp_path: Path) -> None:
    with pytest.raises(RECORD.FaultInjectionError, match="UNREADABLE"):
        RECORD.read_record(tmp_path / "nothing-here.json")


def test_the_reader_hands_back_the_bytes_it_validated(tmp_path: Path) -> None:
    """The sealer seals this snapshot; nothing downstream re-reads the file."""

    path = tmp_path / "fault-injection.json"
    written = RECORD.dump_record(sample())
    path.write_bytes(written)

    record = RECORD.read_record(path)

    assert record.raw == written
    assert record.document["outcome"] == "INJECTED"


def test_a_record_is_written_whole_and_reads_back_the_same(tmp_path: Path) -> None:
    path = tmp_path / "fault-injection.json"

    RECORD.write_record(path, sample())

    assert RECORD.read_record(path).document == sample()
    # Nothing half-written is left behind for the sealer to find.
    assert [entry.name for entry in tmp_path.iterdir()] == [path.name]


def test_a_reader_that_does_not_answer_is_not_an_empty_record() -> None:
    assert "NOT_AN_OBJECT" in codes(None)
    assert "NOT_AN_OBJECT" in codes([sample()])


def test_the_validator_is_total_over_arbitrary_json() -> None:
    """Every value in a JSON document either validates or is named as wrong."""

    empty_array: list[object] = []
    empty_object: dict[str, object] = {}
    values: tuple[object, ...] = (
        0,
        1.5,
        True,
        "x",
        None,
        empty_array,
        empty_object,
        {"schema_version": 1},
    )
    for value in values:
        assert isinstance(codes(value), tuple)


def test_a_run_that_names_no_case_records_that_rather_than_borrowing_one() -> None:
    """A kill run nobody attributed to a case has no case version to claim."""

    assert codes(changed(case=None)) == ()
