"""The initial persona is one person, derived the same way everywhere, and read back."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from minekin_core.adapters.filestore.persona_store import (
    persona_path,
    read_persona,
    write_persona,
)
from minekin_core.application.ports.clock import FakeClock
from minekin_core.bootstrap import main, run
from minekin_core.cli.init import initialise_identity
from minekin_core.config import (
    DATA_ROOT_VARIABLE,
    PERSONA_SEED_VARIABLE,
    USERNAME_VARIABLE,
    configured_persona_seed,
)
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError
from minekin_core.domain.ids import KinId
from minekin_core.domain.persona import (
    PERSONA_ALGORITHM,
    PERSONA_SCHEMA_VERSION,
    TRAIT_CEILING,
    TRAIT_FLOOR,
    TRAIT_NAMES,
    VALUE_NAMES,
    PersonaManifest,
    derive_persona,
    describe_for_backend,
)

KIN_ID = KinId("kin-01")
SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
#: The manifest `(kin-01, seed-abc)` has always had. These numbers are the contract:
#: changing the algorithm or the byte layout has to be a deliberate, versioned move
#: that says so, not something a refactor does on the way past.
GOLDEN_TRAITS = (
    ("social_initiative", 8),
    ("cooperation", 2),
    ("orderliness", 7),
    ("curiosity", 4),
    ("risk_tolerance", 5),
)
GOLDEN_PRIORITY = (
    "belonging",
    "resource_security",
    "creation",
    "exploration",
    "fairness",
    "autonomy",
)


def _kin_dir(root: Path) -> Path:
    return root / "kin" / str(KIN_ID)


def _good_payload() -> dict[str, object]:
    return derive_persona(str(KIN_ID), "seed-abc").as_dict()


def _add_a_trait(payload: dict[str, object]) -> None:
    traits = payload["traits"]
    assert isinstance(traits, dict)
    traits["inventiveness"] = 5


def _drop_a_trait(payload: dict[str, object]) -> None:
    traits = payload["traits"]
    assert isinstance(traits, dict)
    del traits["curiosity"]


def _set_curiosity(value: object) -> Callable[[dict[str, object]], None]:
    def mutate(payload: dict[str, object]) -> None:
        traits = payload["traits"]
        assert isinstance(traits, dict)
        traits["curiosity"] = value

    return mutate


def _duplicate_the_priority(payload: dict[str, object]) -> None:
    payload["value_priority"] = [*VALUE_NAMES, *VALUE_NAMES]


def _rename_the_kin_field(payload: dict[str, object]) -> None:
    del payload["kin_id"]


BAD_MANIFESTS: list[tuple[str, Callable[[dict[str, object]], None]]] = [
    ("an invented trait name", _add_a_trait),
    ("a missing trait", _drop_a_trait),
    ("a trait below the floor", _set_curiosity(TRAIT_FLOOR - 1)),
    ("a trait above the ceiling", _set_curiosity(TRAIT_CEILING + 1)),
    ("a trait that is not an integer", _set_curiosity(True)),
    ("a priority that is not a permutation", _duplicate_the_priority),
    ("a manifest that names no Kin", _rename_the_kin_field),
]


def test_the_same_inputs_always_derive_the_same_person() -> None:
    first = derive_persona("kin-01", "seed-abc")
    second = derive_persona("kin-01", "seed-abc")

    assert first == second
    assert first.traits == GOLDEN_TRAITS
    assert first.value_priority == GOLDEN_PRIORITY
    assert first.algorithm == PERSONA_ALGORITHM
    assert first.schema_version == PERSONA_SCHEMA_VERSION


def _derive_in_a_fresh_process(hash_seed: str) -> dict[str, object]:
    """Derive in another interpreter, with its own string-hash salt.

    The persistence promise is that a restart does not redraw the person, and the
    usual way to break that quietly is to derive from `hash()`, which Python salts
    per process. The salt is pinned to two different values on purpose.
    """

    script = (
        "import json,sys;"
        "from minekin_core.domain.persona import derive_persona;"
        "print(json.dumps(derive_persona(sys.argv[1], sys.argv[2]).as_dict()))"
    )
    environ = {**os.environ, "PYTHONPATH": str(SRC_ROOT), "PYTHONHASHSEED": hash_seed}
    completed = subprocess.run(
        [sys.executable, "-c", script, "kin-01", "seed-abc"],
        env=environ,
        capture_output=True,
        text=True,
        check=True,
    )
    payload: dict[str, object] = json.loads(completed.stdout)
    return payload


def test_a_restart_does_not_redraw_the_person() -> None:
    from_process = _derive_in_a_fresh_process("1")
    other_process = _derive_in_a_fresh_process("3")

    assert from_process == other_process
    assert from_process["traits"] == {name: value for name, value in GOLDEN_TRAITS}


def test_different_kins_and_different_seeds_are_different_people() -> None:
    base = derive_persona("kin-01", "seed-abc")

    assert derive_persona("kin-02", "seed-abc") != base
    assert derive_persona("kin-01", "seed-abd") != base


@pytest.mark.parametrize("seed", ["a", "b", "c", "d", "e", "f", "g", "h"])
def test_derivation_spreads_traits_and_orders_every_value(seed: str) -> None:
    manifest = derive_persona("kin-01", seed)

    assert [name for name, _ in manifest.traits] == list(TRAIT_NAMES)
    assert all(TRAIT_FLOOR <= value <= TRAIT_CEILING for _, value in manifest.traits)
    assert sorted(manifest.value_priority) == sorted(VALUE_NAMES)
    # A manifest whose five tendencies all read the same number is not a person.
    assert len({value for _, value in manifest.traits}) > 1


def test_a_manifest_survives_the_json_round_trip(tmp_path: Path) -> None:
    manifest = derive_persona(str(KIN_ID), "seed-abc")

    path = write_persona(tmp_path, manifest)

    assert path == persona_path(tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["algorithm"] == PERSONA_ALGORITHM
    assert read_persona(tmp_path) == manifest


def test_the_store_writes_only_the_reviewed_names(tmp_path: Path) -> None:
    payload = json.loads(
        write_persona(tmp_path, derive_persona(str(KIN_ID), "s")).read_text(encoding="utf-8")
    )

    assert sorted(payload) == [
        "algorithm",
        "kin_id",
        "persona_seed",
        "schema_version",
        "traits",
        "value_priority",
    ]


def test_a_missing_file_says_which_case_the_operator_is_in(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="PERSONA_NOT_INITIALISED") as raised:
        read_persona(tmp_path)

    assert raised.value.category is ErrorCategory.STORAGE


def test_a_persona_is_never_redrawn_in_place(tmp_path: Path) -> None:
    write_persona(tmp_path, derive_persona(str(KIN_ID), "seed-abc"))

    with pytest.raises(MinekinError, match="PERSONA_ALREADY_INITIALISED") as raised:
        write_persona(tmp_path, derive_persona(str(KIN_ID), "seed-xyz"))

    assert raised.value.category is ErrorCategory.STORAGE
    assert read_persona(tmp_path).persona_seed == "seed-abc"


def test_half_a_file_is_refused_rather_than_repaired(tmp_path: Path) -> None:
    persona_path(tmp_path).write_text("{", encoding="utf-8")

    with pytest.raises(MinekinError, match="not readable JSON"):
        read_persona(tmp_path)


def test_a_manifest_from_another_algorithm_is_not_a_slightly_wrong_person() -> None:
    payload = _good_payload()
    payload["algorithm"] = "persona-blake2b-v2"

    with pytest.raises(MinekinError, match="this build reads") as raised:
        PersonaManifest.from_dict(payload)

    assert raised.value.category is ErrorCategory.CONFIG


def test_a_manifest_from_another_schema_version_is_refused() -> None:
    payload = _good_payload()
    payload["schema_version"] = PERSONA_SCHEMA_VERSION + 1

    with pytest.raises(MinekinError, match="schema version"):
        PersonaManifest.from_dict(payload)


@pytest.mark.parametrize(
    ["_label", "mutate"],
    BAD_MANIFESTS,
    ids=[label for label, _ in BAD_MANIFESTS],
)
def test_a_handed_in_manifest_must_be_exactly_the_reviewed_shape(
    _label: str, mutate: Callable[[dict[str, object]], None]
) -> None:
    payload = _good_payload()
    mutate(payload)

    with pytest.raises(MinekinError):
        PersonaManifest.from_dict(payload)


def test_the_backend_read_carries_the_person_and_not_the_seed() -> None:
    described = describe_for_backend(derive_persona(str(KIN_ID), "seed-abc"))

    assert described["most_valued"] == GOLDEN_PRIORITY[0]
    assert "seed" not in json.dumps(described)


def test_init_persists_the_seed_the_operator_stated(tmp_path: Path) -> None:
    report = initialise_identity(
        KIN_ID, root=tmp_path, username="Kin", clock=FakeClock(), persona_seed="seed-abc"
    )

    assert Path(report.persona_file) == persona_path(_kin_dir(tmp_path))
    assert read_persona(_kin_dir(tmp_path)) == derive_persona("kin-01", "seed-abc")


def test_init_draws_a_seed_when_the_operator_stated_none(tmp_path: Path) -> None:
    initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())

    manifest = read_persona(_kin_dir(tmp_path))
    assert len(manifest.persona_seed) == 16
    assert all(char in "0123456789abcdef" for char in manifest.persona_seed)
    assert derive_persona("kin-01", manifest.persona_seed) == manifest


def test_two_kins_created_without_a_stated_seed_are_not_the_same_person(
    tmp_path: Path,
) -> None:
    first = initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())
    second = initialise_identity(
        KinId("kin-02"), root=tmp_path, username="Notch", clock=FakeClock()
    )

    left = read_persona(_kin_dir(tmp_path))
    right = read_persona(Path(second.persona_file).parent)

    assert left.persona_seed != right.persona_seed
    assert first.persona_file != second.persona_file


def test_init_refuses_a_root_that_has_a_person_but_no_identity(tmp_path: Path) -> None:
    directory = _kin_dir(tmp_path)
    directory.mkdir(parents=True)
    write_persona(directory, derive_persona(str(KIN_ID), "seed-abc"))

    with pytest.raises(MinekinError, match="half-created root"):
        initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())


def test_an_absent_seed_variable_is_not_a_refusal() -> None:
    assert configured_persona_seed({}) is None


def test_a_stated_but_empty_seed_is_refused_rather_than_drawn_over() -> None:
    with pytest.raises(MinekinError, match="is set but empty"):
        configured_persona_seed({PERSONA_SEED_VARIABLE: "   "})


def test_the_seed_is_used_verbatim_because_spaces_are_part_of_it() -> None:
    assert configured_persona_seed({PERSONA_SEED_VARIABLE: " two spaces "}) == " two spaces "


def test_the_command_line_creates_and_reads_the_same_person(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    monkeypatch.setenv(USERNAME_VARIABLE, "Kin")
    monkeypatch.setenv(PERSONA_SEED_VARIABLE, "seed-abc")
    stdout, stderr = io.StringIO(), io.StringIO()

    assert run(["init", "--kin-id", "kin-01"], stdout=stdout, stderr=stderr) == int(ExitCode.OK)

    read_back = io.StringIO()
    assert run(
        ["persona", "show", "--kin-id", "kin-01"], stdout=read_back, stderr=io.StringIO()
    ) == int(ExitCode.OK)
    payload = json.loads(read_back.getvalue())

    assert payload["command"] == "persona show"
    assert payload["persona_file"] == str(persona_path(_kin_dir(tmp_path)))
    assert payload["persona"]["traits"] == {name: value for name, value in GOLDEN_TRAITS}
    assert payload["persona"]["value_priority"] == list(GOLDEN_PRIORITY)
    assert payload["persona"]["algorithm"] == PERSONA_ALGORITHM
    assert "seed" not in json.dumps(payload["persona"])


def test_a_kin_created_before_personas_existed_gets_no_invented_person(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_VARIABLE, str(tmp_path))
    captured_stdout, captured_stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    monkeypatch.setattr(sys, "stderr", captured_stderr)
    initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())
    persona_path(_kin_dir(tmp_path)).unlink()

    code = main(["persona", "show", "--kin-id", "kin-01"])

    assert code == int(ExitCode.STORAGE)
    assert not captured_stdout.getvalue()
    assert "PERSONA_NOT_INITIALISED" in captured_stderr.getvalue()
