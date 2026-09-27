"""Whom a sealed run asked the server about, and what that answer is good for.

The server's answer to a position probe is `has the following entity data: [x, y, z]`.
It never says whose position that is: the name is in the command typed at the console,
and the console does not log what it was typed with. One name per run hides that — a
trajectory in the log can belong to only one Kin — and two clients in one world
removes the hiding, because the host's walk then satisfies a judgement written about
the joiner and the bundle carries a pass for the wrong Kin. Nothing downstream can
un-make that, since the bytes the judgement rests on cannot be re-read with a name
added later.

So the name has to be written down at the seal, and read back as the narrow thing it
is: a set. These tests hold the carrier together — what the sealer writes, what the
judge reads out of it, and the refusals a reader has to be able to tell apart. The run
is fabricated; the document shapes are the ones the sealer writes.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: The artifact is named here rather than read off the asserter's constant on purpose:
#: the failure this document exists to prevent is the sealer and the reader disagreeing
#: about the spelling, and a test that took the spelling from one of them could not see
#: that disagreement.
ASSERTER_INPUTS = "asserter-inputs.json"

USERNAME = "Kin"
OTHER = "Kin2"
NOT_RECORDED = "PROBE_ATTRIBUTION_NOT_RECORDED"
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
#: The keys `asserter-inputs.json` held before any run named a probe. A run that names
#: nothing has to go on holding exactly these, or every bundle sealed so far would
#: change its bytes under the re-judges that read them.
LONG_STANDING_KEYS = ["kin_id", "previous_run_id", "run_id", "schema_version", "username"]


class _Asserter(Protocol):
    """The parts of the judgement this file reads, and the one command it drives."""

    EXIT_UNJUDGED: int

    def asserter_inputs_bytes(
        self, material: Any, *, username: str, probed_players: Sequence[str] | None = ...
    ) -> bytes: ...

    def read_sealed_material(self, directory: Path) -> Any: ...

    def the_probed_player_is_this_run_s_kin(self, material: Any) -> str | None: ...

    def main(self, argv: Sequence[str]) -> int: ...


class _Sealer(Protocol):
    """The sealer's side of the hand-over, and the module it hands it through."""

    subprocess: Any

    def run_asserter(
        self,
        *,
        case: Path,
        run_document: Path | None,
        data_root: Path,
        server_directory: Path | None,
        username: str,
        run_id: str | None = ...,
        probed_players: Sequence[str] | None = ...,
    ) -> dict[str, object]: ...


def load(name: str) -> Any:
    """One `tools/` module, by the same route `python tools/x.py` would take."""

    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module(f"tools.{name}")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


ASSERTER = cast(_Asserter, load("assert_case_evidence"))
SEALER = cast(_Sealer, load("seal_run_evidence"))


def bundle_holding(directory: Path, *, username: str = USERNAME, probed: object = ...) -> Path:
    """A scratch bundle whose only artifact is the document the judge is handed.

    `probed` left at `...` writes no `probed_players` key at all, which is what every
    bundle sealed before this field existed looks like. A value is written verbatim,
    because the shapes that are not a list of names are ones only a hand can make.
    """

    document: dict[str, object] = {
        "schema_version": 1,
        "kin_id": "kin-01",
        "run_id": RUN_ID,
        "username": username,
        "previous_run_id": "",
    }
    if probed is not ...:
        document["probed_players"] = probed
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ASSERTER_INPUTS).write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return directory


def judgement(directory: Path) -> str | None:
    """The attribution, reached the only way a sealed bundle can reach it."""

    return ASSERTER.the_probed_player_is_this_run_s_kin(ASSERTER.read_sealed_material(directory))


def test_the_run_s_own_name_is_the_one_answer_that_holds(tmp_path: Path) -> None:
    """One name, and it is this Kin: the trajectory can belong to nobody else.

    The positive control of the four, and the reason the refusals below are named
    rather than one answer: this pass has to be reachable from sealed bytes alone.
    """

    assert judgement(bundle_holding(tmp_path / "own", probed=[USERNAME])) is None


def test_two_names_refuse_by_naming_both(tmp_path: Path) -> None:
    """A run that probed the host and the joiner has one log and no way to split it.

    Refusing is the only honest answer: either trajectory could be the one the case is
    about, and taking the first would be a guess written up as a judgement.
    """

    assert judgement(bundle_holding(tmp_path / "two", probed=[USERNAME, OTHER])) == (
        f"MORE_THAN_ONE_PLAYER_PROBED:{USERNAME},{OTHER}"
    )


def test_the_other_player_s_name_refuses_by_naming_it(tmp_path: Path) -> None:
    """The shape a two-client run takes when the harness names the wrong client.

    One name, and not this run's — a different fact from having two, and a different
    reader's action: one says the harness was told too little, the other that it was
    told the wrong thing.
    """

    assert judgement(bundle_holding(tmp_path / "wrong", probed=[OTHER])) == (
        f"PROBED_PLAYER_IS_NOT_THIS_RUN_S_KIN:{OTHER}"
    )


def test_a_bundle_that_named_nobody_refuses_rather_than_passing(tmp_path: Path) -> None:
    """The field's absence is not a clean answer, and not nothing-happened either.

    Every bundle on the volume today is this bundle: sealed before any run named a
    probe. A case resting on the attribution has to refuse on all of them by name, or
    the field would be a way to pass by sealing less.
    """

    assert judgement(bundle_holding(tmp_path / "absent")) == NOT_RECORDED


def test_an_empty_or_unreadable_record_refuses_as_nothing_recorded(tmp_path: Path) -> None:
    """Writing the key down is not the same as naming a player.

    An empty set names nobody, and a value that is not a list of names is a document
    that did not answer — the reading rule `_trace_argv` already gives a malformed
    argv, so a hand-written document cannot be greener than a run that named nothing.
    """

    for position, value in enumerate(([], [USERNAME, 7], "Kin", {"a": 1}, None)):
        directory = bundle_holding(tmp_path / f"empty-{position}", probed=value)
        assert judgement(directory) == NOT_RECORDED, value


def test_the_asserter_reads_a_name_from_its_own_command_line(tmp_path: Path) -> None:
    """The argument exists on the judge's side too, and is spelled as the sealer says.

    Driven as a command because the spelling is where the two would diverge: a name the
    judge never received reads as `nothing was recorded` while the bundle the same seal
    writes says exactly whom the server was asked about. The case file is deliberately
    missing, so nothing but the case can be refused here.
    """

    held = ASSERTER.main(
        [
            "--case",
            str(tmp_path / "no-such-case.json"),
            "--data-root",
            str(tmp_path),
            "--username",
            USERNAME,
            "--probed-player",
            USERNAME,
        ]
    )

    assert held == ASSERTER.EXIT_UNJUDGED


def test_the_names_seal_as_a_set_whatever_order_they_came_in(tmp_path: Path) -> None:
    """The same two probes, handed over twice, seal to one document.

    They travel one per argument on a command line, so two orders of one set are one
    run described twice. A seal that recorded the order would give a run two possible
    bundles, and a re-judge could reproduce only one of them.
    """

    material = ASSERTER.read_sealed_material(bundle_holding(tmp_path / "canonical"))
    once = ASSERTER.asserter_inputs_bytes(
        material, username=USERNAME, probed_players=[OTHER, USERNAME]
    )
    again = ASSERTER.asserter_inputs_bytes(
        material, username=USERNAME, probed_players=[USERNAME, OTHER, OTHER]
    )

    assert json.loads(once)["probed_players"] == [USERNAME, OTHER]
    assert once == again


def test_the_round_trip_through_the_document_holds_the_same_answer(tmp_path: Path) -> None:
    """What the sealer wrote, judged as a sealed bundle, says what the sealer said.

    The carrier's own positive control: the bytes come from the sealer's writer rather
    than from this file's idea of the shape, and the pass still arrives. A key the
    reader did not know would read back as `nothing was recorded`, which is the quiet
    failure this document exists to prevent.
    """

    material = ASSERTER.read_sealed_material(bundle_holding(tmp_path / "trip-in"))
    sealed = ASSERTER.asserter_inputs_bytes(material, username=USERNAME, probed_players=[USERNAME])
    written = tmp_path / "trip-out"
    written.mkdir()
    (written / ASSERTER_INPUTS).write_bytes(sealed)

    assert judgement(written) is None
    assert json.loads(sealed)["probed_players"] == [USERNAME]
    assert sorted(json.loads(sealed)) == [
        "kin_id",
        "previous_run_id",
        "probed_players",
        "run_id",
        "schema_version",
        "username",
    ]


def test_a_run_that_named_no_player_seals_the_document_it_always_sealed(
    tmp_path: Path,
) -> None:
    """Nothing a bundle already holds moves because this field became possible.

    The key is written when there is a name to write and not otherwise, so a run whose
    harness named nobody seals the bytes it sealed yesterday, and every verdict
    recorded against those bytes keeps its meaning.
    """

    material = ASSERTER.read_sealed_material(bundle_holding(tmp_path / "unchanged"))

    named: list[Sequence[str] | None] = [None, []]
    for probed in named:
        document = json.loads(
            ASSERTER.asserter_inputs_bytes(material, username=USERNAME, probed_players=probed)
        )
        assert sorted(document) == LONG_STANDING_KEYS, probed


def test_the_sealer_hands_every_name_to_the_judge_it_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One argument per name, in the order the operator gave them.

    Asserted on the argument vector rather than on a verdict, because what this covers
    up is the seal's own judgement: the judge is a subprocess, and an argument the
    sealer drops is a question the judge was never asked.
    """

    asked: list[list[str]] = []

    def pretend(command: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        asked.append([str(item) for item in command])
        return subprocess.CompletedProcess(
            list(command),
            returncode=0,
            stdout=json.dumps(
                {"expected": [], "observed": [], "failures": [], "unimplemented": []}
            ),
            stderr="",
        )

    monkeypatch.setattr(SEALER.subprocess, "run", pretend)
    SEALER.run_asserter(
        case=tmp_path / "case.json",
        run_document=None,
        data_root=tmp_path,
        server_directory=None,
        username=USERNAME,
        run_id=RUN_ID,
        probed_players=[USERNAME, OTHER],
    )

    argv = asked[0]
    handed = [argv[position + 1] for position, item in enumerate(argv) if item == "--probed-player"]
    assert handed == [USERNAME, OTHER]
