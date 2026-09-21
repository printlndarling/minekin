"""Which save paths a hosted world may actually use.

The storage contract's HOST-020 names the refusals — a symlinked save path, `..`,
another Kin's path, a bind that lands outside — and each one gets a test here.
They are written against the *rule* rather than against a spelling: the identifier
rule is the one level names already obey, and the containment refusals are checked
against a real directory tree, because a policy about where files may live is
worth nothing if it only passes on paths that do not exist.

Two tests are about the mechanism rather than the rule, and they are the reason
this module walks the path instead of resolving it once. A symlinked `save/` and a
symlinked `hosted-worlds/` both make the canonical path leave the world's root;
`Path.resolve()` alone would report the destination and never say how it got
there, and the client cannot tell the two apart either.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.hosted_store import (
    BACKUPS_DIRECTORY,
    HOSTED_WORLDS_DIRECTORY,
    MANIFEST_NAME,
    SAVE_DIRECTORY,
    HostedWorldPaths,
    SavePathRefusal,
    admit_save_root,
    hosted_world_paths,
)

KIN = "kin-1"
WORLD = "hosted-world-1"
OTHER_KIN = "kin-2"
OTHER_WORLD = "hosted-world-2"


def roots(tmp_path: Path, *, kin_id: str = KIN, hosted_world_id: str = WORLD) -> HostedWorldPaths:
    decision = hosted_world_paths(
        data_root=tmp_path, kin_id=kin_id, hosted_world_id=hosted_world_id
    )
    assert decision.admitted and decision.paths is not None, decision
    return decision.paths


def make_save(paths: HostedWorldPaths) -> Path:
    """The world's own save, on disk, as the store would have it."""

    (paths.world_root / SAVE_DIRECTORY).mkdir(parents=True)
    (paths.world_root / MANIFEST_NAME).write_text("schema: test\n", encoding="utf-8")
    return paths.save_root


# ---------------------------------------------------------------------------
# The layout
# ---------------------------------------------------------------------------


def test_the_layout_is_the_one_the_contract_fixes(tmp_path: Path) -> None:
    """Every root is derived, so the same world is always the same directory."""

    paths = roots(tmp_path)

    assert paths.data_root == tmp_path.resolve()
    assert paths.kin_root == tmp_path.resolve() / "kin" / KIN
    assert paths.world_root == paths.kin_root / HOSTED_WORLDS_DIRECTORY / WORLD
    assert paths.save_root == paths.world_root / SAVE_DIRECTORY
    assert paths.as_document()["save_root"] == str(paths.save_root)


def test_the_directories_the_world_owns_are_named_where_they_are_used() -> None:
    """The names are contract vocabulary, not string literals in a caller."""

    assert (HOSTED_WORLDS_DIRECTORY, SAVE_DIRECTORY, BACKUPS_DIRECTORY) == (
        "hosted-worlds",
        "save",
        "backups",
    )
    assert MANIFEST_NAME == "manifest.yaml"


def test_a_relative_data_root_is_refused_rather_than_made_absolute(tmp_path: Path) -> None:
    """A data root that depends on the working directory is not an address."""

    decision = hosted_world_paths(data_root=Path("data"), kin_id=KIN, hosted_world_id=WORLD)

    assert decision.admitted is False
    assert decision.refusal is SavePathRefusal.OUTSIDE_DATA_ROOT


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "identifier",
    [
        "..",
        ".",
        "",
        "a/b",
        "a\\b",
        "a:b",
        "C:foo",
        "nul\0",
        " padded ",
    ],
)
def test_an_identifier_that_is_not_a_plain_directory_name_is_refused(
    tmp_path: Path, identifier: str
) -> None:
    """Held to the level-name rule: refused by rule, not by looking for `..`.

    `a:b` and `C:foo` are the two that are not about traversal at all. On Windows a
    `:` in a segment is a drive, so joining `a:b` onto the data root does not put a
    directory under it — the data root is gone — and `C:foo` silently becomes
    `foo`, which would make two identifiers name one directory.
    """

    for label, kin_id, hosted_world_id in (
        ("kin_id", identifier, WORLD),
        ("hosted_world_id", KIN, identifier),
    ):
        decision = hosted_world_paths(
            data_root=tmp_path, kin_id=kin_id, hosted_world_id=hosted_world_id
        )

        assert decision.admitted is False, label
        assert decision.refusal is SavePathRefusal.UNSAFE_IDENTIFIER, label
        assert label in decision.detail


@pytest.mark.skipif(sys.platform != "win32", reason="a `:` is a drive only on Windows")
def test_the_reason_colons_are_refused_is_measurable_on_this_platform() -> None:
    """The refusal above is not caution: this is what the join actually does here.

    Kept as a test rather than as a sentence in a comment because the behaviour
    belongs to `pathlib`, not to this repository — if a future Python stops letting
    a segment replace the base path, this test is where that shows up.
    """

    base = Path("C:/data")

    assert base / "a:b" != base / "a:b".replace(":", "-")
    assert not (base / "a:b").is_relative_to(base), "the drive replaced the whole path"
    assert base / "C:foo" == Path("C:/data/foo"), "the drive was dropped and `foo` kept"


# ---------------------------------------------------------------------------
# HOST-020: what a declared save root may be
# ---------------------------------------------------------------------------


def test_the_worlds_own_save_is_admitted(tmp_path: Path) -> None:
    paths = roots(tmp_path)
    save = make_save(paths)

    decision = admit_save_root(declared=save, paths=paths)

    assert decision.admitted is True, decision
    assert decision.paths == paths
    assert decision.as_document()["refusal"] is None


def test_a_path_inside_the_save_is_not_the_save_but_is_still_the_worlds(tmp_path: Path) -> None:
    """`save/region` is inside the world; the world's save directory is `save/`.

    The refusal is the directory's business, not the caller's: an argument about a
    path *inside* the save is not a reason to call the save unusable.
    """

    paths = roots(tmp_path)
    save = make_save(paths)
    (save / "region").mkdir()

    assert admit_save_root(declared=save / "region", paths=paths).admitted is True


def test_a_save_path_outside_the_data_root_is_refused(tmp_path: Path) -> None:
    """The contract's "越界": the store is inside the data root, and only there."""

    paths = roots(tmp_path / "data")
    outside = tmp_path / "elsewhere"
    outside.mkdir()

    decision = admit_save_root(declared=outside, paths=paths)

    assert decision.admitted is False
    assert decision.refusal is SavePathRefusal.OUTSIDE_DATA_ROOT
    assert str(outside.resolve()) in decision.detail


def test_a_relative_save_path_is_refused(tmp_path: Path) -> None:
    """A path that depends on the working directory is not a canonical path."""

    paths = roots(tmp_path)

    decision = admit_save_root(declared=Path("kin/kin-1/save"), paths=paths)

    assert decision.refusal is SavePathRefusal.OUTSIDE_DATA_ROOT


def test_another_kins_area_is_refused(tmp_path: Path) -> None:
    """HOST-020's third refusal: one Kin's world is never reached through another."""

    paths = roots(tmp_path)
    other = roots(tmp_path, kin_id=OTHER_KIN)
    other_save = make_save(other)

    decision = admit_save_root(declared=other_save, paths=paths)

    assert decision.admitted is False
    assert decision.refusal is SavePathRefusal.ANOTHER_KIN
    assert str(other.kin_root) in decision.detail


def test_another_world_of_the_same_kin_is_refused(tmp_path: Path) -> None:
    """Sibling worlds are as separate as unrelated ones."""

    paths = roots(tmp_path)
    sibling = roots(tmp_path, hosted_world_id=OTHER_WORLD)
    sibling_save = make_save(sibling)

    decision = admit_save_root(declared=sibling_save, paths=paths)

    assert decision.admitted is False
    assert decision.refusal is SavePathRefusal.ANOTHER_WORLD
    assert str(sibling.world_root) in decision.detail


@pytest.mark.parametrize("directory", [BACKUPS_DIRECTORY, "checkpoints"])
def test_a_checkpoint_or_a_backup_is_not_the_world(tmp_path: Path, directory: str) -> None:
    """A backup is a copy of a world at a time, and a client started on one forks it."""

    paths = roots(tmp_path)
    make_save(paths)
    (paths.world_root / directory).mkdir()

    decision = admit_save_root(declared=paths.world_root / directory, paths=paths)

    assert decision.admitted is False
    assert decision.refusal is SavePathRefusal.NOT_THE_WORLDS_SAVE


def test_a_directory_under_the_data_root_that_is_not_a_hosted_world_is_refused(
    tmp_path: Path,
) -> None:
    """The artifacts and bundles stores are not worlds, however canonical they look."""

    paths = roots(tmp_path)
    (paths.data_root / "artifacts").mkdir()

    decision = admit_save_root(declared=paths.data_root / "artifacts", paths=paths)

    assert decision.refusal is SavePathRefusal.OUTSIDE_DATA_ROOT


# ---------------------------------------------------------------------------
# HOST-020: symlinks
# ---------------------------------------------------------------------------


def symlink(target: Path, link: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as error:  # pragma: no cover - platform dependent
        pytest.skip(f"this platform cannot create a symlink: {error}")


def test_a_symlinked_save_directory_is_refused(tmp_path: Path) -> None:
    """The leaf itself: the client would write through it into the real location."""

    paths = roots(tmp_path)
    paths.world_root.mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    symlink(elsewhere, paths.save_root)

    decision = admit_save_root(declared=paths.save_root, paths=paths)

    assert decision.admitted is False
    assert decision.refusal is SavePathRefusal.SYMLINK_IN_PATH
    assert str(paths.save_root) in decision.detail


def test_a_symlinked_ancestor_is_refused_however_canonical_the_result_is(tmp_path: Path) -> None:
    """The escape this rule exists for: `hosted-worlds/` pointing outside the root.

    Every part of the declared path is spelled correctly, and the world it names is
    a real directory with a real save in it — the only thing wrong is how the path
    got there. `Path.resolve()` returns a path outside the data root, and a check
    that only looked at that would have to decide whether the *result* or the
    *path* was the thing being validated. This refuses both.
    """

    data_root = tmp_path / "data"
    paths = roots(data_root)
    decoy = tmp_path / "decoy" / WORLD
    (decoy / SAVE_DIRECTORY).mkdir(parents=True)
    paths.kin_root.mkdir(parents=True)
    symlink(tmp_path / "decoy", paths.world_root.parent)

    decision = admit_save_root(declared=paths.save_root, paths=paths)

    assert decision.admitted is False
    assert decision.refusal is SavePathRefusal.SYMLINK_IN_PATH
    assert str(paths.world_root.parent) in decision.detail
    # And the escape was real: the path resolves to the decoy, outside the store.
    assert not paths.save_root.resolve().is_relative_to(paths.data_root)


def test_the_symlink_is_reported_before_what_it_would_have_caused(tmp_path: Path) -> None:
    """Which reason fires is part of the answer: the mechanism, not the consequence.

    A symlinked ancestor also resolves outside the root, so a check that ran the
    containment test first would report `OUTSIDE_DATA_ROOT` and leave an operator
    looking for a path that was spelled wrong.
    """

    data_root = tmp_path / "data"
    paths = roots(data_root)
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / WORLD / SAVE_DIRECTORY).mkdir(parents=True)
    paths.kin_root.mkdir(parents=True)
    symlink(elsewhere, paths.world_root.parent)

    decision = admit_save_root(declared=paths.save_root, paths=paths)

    assert not paths.save_root.resolve().is_relative_to(paths.data_root), "the escape is real"
    assert decision.refusal is SavePathRefusal.SYMLINK_IN_PATH
    assert decision.refusal is not SavePathRefusal.OUTSIDE_DATA_ROOT
