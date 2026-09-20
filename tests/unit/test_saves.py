"""Placing a prepared world where the client will look for it.

A session that is meant to *host* needs the client to be in a world before
anything can join it: `IntegratedServer.openToLan` publishes the server a client
is already running, and a client at the title screen is running none. The tests
here are about the two things that step can get wrong — putting the world
somewhere the client will not look, and naming it after something other than the
bytes that were handed over.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.saves import (
    LEVEL_DAT,
    PLAYER_DATA_DIRECTORY,
    SAVES_DIRECTORY,
    level_name_is_usable,
    player_data_path,
    saves_directory,
    seed_world,
    settings_digest,
    world_snapshot_digest,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

#: The Kin this world is being seeded for. Which player it is does not matter; that
#: it is *this* player's state the world may not already hold is the rule.
PLAYER = uuid.UUID("8f40376b-c23f-3ef1-b553-5564eea75639")


def _world(tmp_path: Path, *, seed_level: bytes = b"a level.dat\n") -> Path:
    """A save that looks the way a copied world does: a level and a region file."""

    save = tmp_path / "prepared-world"
    (save / "region").mkdir(parents=True)
    (save / LEVEL_DAT).write_bytes(seed_level)
    (save / "region" / "r.0.0.mca").write_bytes(b"region bytes\n")
    return save


def test_the_saves_directory_is_inside_the_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / "session" / "generation-1"

    assert saves_directory(overlay) == overlay.resolve() / SAVES_DIRECTORY


def test_a_relative_overlay_is_refused(tmp_path: Path) -> None:
    """The overlay is the game directory; a relative one names no directory."""

    with pytest.raises(MinekinError, match="absolute") as raised:
        saves_directory(Path("session/generation-1"))

    assert raised.value.component == "launcher.saves"
    assert raised.value.operation == "seed"
    assert raised.value.category is ErrorCategory.CONFIG
    assert raised.value.retryability is Retryability.OPERATOR_ACTION


@pytest.mark.parametrize("name", ["world", "New World", "world-2026", "a.b", "Wörld"])
def test_a_plain_directory_name_is_usable(name: str) -> None:
    assert level_name_is_usable(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "../world",
        "world/elsewhere",
        "world\\elsewhere",
        "C:world",
        "world\0",
        " world",
        "world ",
    ],
)
def test_a_name_that_could_move_the_destination_is_not(name: str) -> None:
    """Refused by rule rather than by hunting for `..` in the string."""

    assert level_name_is_usable(name) is False


def test_the_digest_names_every_file_not_only_the_level(tmp_path: Path) -> None:
    """Two saves that differ only in terrain are two different worlds.

    The negative mutation is "hash `level.dat` alone": the seed and the generator
    settings live there, so that digest is stable while the world it names is
    not.
    """

    save = _world(tmp_path)
    before = world_snapshot_digest(save)
    (save / "region" / "r.0.0.mca").write_bytes(b"different region bytes\n")

    assert world_snapshot_digest(save) != before


def test_the_digest_does_not_depend_on_the_order_files_were_written(tmp_path: Path) -> None:
    """A world is a set of bytes, not a sequence of writes."""

    first = _world(tmp_path / "one")
    second = tmp_path / "two" / "prepared-world"
    (second / "region").mkdir(parents=True)
    (second / "region" / "r.0.0.mca").write_bytes(b"region bytes\n")
    (second / LEVEL_DAT).write_bytes(b"a level.dat\n")

    assert world_snapshot_digest(first) == world_snapshot_digest(second)


def test_a_directory_with_no_files_is_not_a_world(tmp_path: Path) -> None:
    """A digest over nothing would look like a world that happens to be empty."""

    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(MinekinError, match="holds no files"):
        world_snapshot_digest(empty)


def test_seeding_places_the_world_where_the_client_looks(tmp_path: Path) -> None:
    save = _world(tmp_path)
    overlay = tmp_path / "overlay"
    overlay.mkdir()

    destination, digest = seed_world(
        overlay=overlay, save=save, player=PLAYER, level_name="prepared-world"
    )

    assert destination == overlay / SAVES_DIRECTORY / "prepared-world"
    assert (destination / LEVEL_DAT).read_bytes() == b"a level.dat\n"
    assert (destination / "region" / "r.0.0.mca").read_bytes() == b"region bytes\n"
    assert digest == world_snapshot_digest(save)


def test_the_name_is_the_bytes_as_they_were_handed_over(tmp_path: Path) -> None:
    """A world the client has played in is a different world.

    What this run reports has to describe the world it was *given*, and the copy
    is the thing the client will write to. The subtle version of getting this
    wrong — hashing the destination after something has already written to it —
    needs a client to be running to reproduce; what can be pinned here is the
    end it would defeat: the name is not the name of the played-in world.
    """

    save = _world(tmp_path)
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    seeded = world_snapshot_digest(save)

    destination, digest = seed_world(
        overlay=overlay, save=save, player=PLAYER, level_name="prepared-world"
    )
    (destination / "region" / "r.0.0.mca").write_bytes(b"played in\n")
    (destination / LEVEL_DAT).write_bytes(b"rewritten\n")

    assert digest == seeded
    assert world_snapshot_digest(destination) != digest


def test_seeding_leaves_the_source_alone(tmp_path: Path) -> None:
    save = _world(tmp_path)
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    before = world_snapshot_digest(save)

    seed_world(overlay=overlay, save=save, player=PLAYER, level_name="prepared-world")

    assert world_snapshot_digest(save) == before


def test_nothing_is_left_staged_in_the_saves_directory(tmp_path: Path) -> None:
    """A reader that sees the directory must see all of it — and only it."""

    save = _world(tmp_path)
    overlay = tmp_path / "overlay"
    overlay.mkdir()

    seed_world(overlay=overlay, save=save, player=PLAYER, level_name="prepared-world")

    assert [path.name for path in saves_directory(overlay).iterdir()] == ["prepared-world"]


def test_a_save_without_a_level_is_not_a_world(tmp_path: Path) -> None:
    save = _world(tmp_path)
    (save / LEVEL_DAT).unlink()
    overlay = tmp_path / "overlay"
    overlay.mkdir()

    with pytest.raises(MinekinError, match=f"no {LEVEL_DAT}"):
        seed_world(overlay=overlay, save=save, player=PLAYER, level_name="prepared-world")


def test_a_source_that_is_not_a_directory_is_refused(tmp_path: Path) -> None:
    save = tmp_path / "world.zip"
    save.write_bytes(b"not a directory")
    overlay = tmp_path / "overlay"
    overlay.mkdir()

    with pytest.raises(MinekinError, match="not a directory to seed from"):
        seed_world(overlay=overlay, save=save, player=PLAYER, level_name="prepared-world")


def test_an_unusable_level_name_is_refused_before_anything_is_copied(tmp_path: Path) -> None:
    save = _world(tmp_path)
    overlay = tmp_path / "overlay"
    overlay.mkdir()

    with pytest.raises(MinekinError, match="not a usable level name"):
        seed_world(overlay=overlay, save=save, player=PLAYER, level_name="../elsewhere")

    assert not (overlay / SAVES_DIRECTORY).exists()


def test_a_saves_directory_that_already_holds_this_level_is_refused(tmp_path: Path) -> None:
    """Refused rather than merged: two worlds' regions in one directory is neither."""

    save = _world(tmp_path)
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    seed_world(overlay=overlay, save=save, player=PLAYER, level_name="prepared-world")

    with pytest.raises(MinekinError, match="already holds a world"):
        seed_world(overlay=overlay, save=save, player=PLAYER, level_name="prepared-world")

    # The world that was already there is untouched by the attempt.
    assert (overlay / SAVES_DIRECTORY / "prepared-world" / LEVEL_DAT).read_bytes() == (
        b"a level.dat\n"
    )


def test_the_digest_is_over_bytes_a_reader_could_reproduce(tmp_path: Path) -> None:
    """Not over mtimes or inode order: a copy of the same bytes names the same world."""

    save = _world(tmp_path)
    overlay_one = tmp_path / "overlay-one"
    overlay_two = tmp_path / "overlay-two"
    overlay_one.mkdir()
    overlay_two.mkdir()

    _, first = seed_world(overlay=overlay_one, save=save, player=PLAYER, level_name="world")
    # A second copy, written later, of a source whose mtimes have moved on.
    for path in sorted(save.rglob("*")):
        if path.is_file():
            os.utime(path, (1_700_000_000, 1_700_000_000))
    _, second = seed_world(overlay=overlay_two, save=save, player=PLAYER, level_name="world")

    assert first == second


def test_the_player_state_of_one_kin_is_where_vanilla_keeps_it(tmp_path: Path) -> None:
    save = tmp_path / "prepared-world"

    assert player_data_path(save, PLAYER) == save / PLAYER_DATA_DIRECTORY / f"{PLAYER}.dat"


def test_a_world_that_already_holds_this_kin_is_not_a_clean_start(tmp_path: Path) -> None:
    """Measured: the client loads such a Kin *as that run left them*.

    A world taken from an earlier run carried `Health 0` and a non-zero
    `DeathTime`; the client went straight to the death screen, and its log had no
    death in it because no death happened. Nothing else about the run looked
    wrong, which is the whole difficulty.
    """

    save = _world(tmp_path)
    player_data_path(save, PLAYER).parent.mkdir()
    player_data_path(save, PLAYER).write_bytes(b"health zero\n")
    overlay = tmp_path / "overlay"
    overlay.mkdir()

    with pytest.raises(MinekinError, match="already holds this Kin") as raised:
        seed_world(overlay=overlay, save=save, player=PLAYER, level_name="prepared-world")

    # The message names the very file, so the operator can find what to take out
    # of the world rather than being told that something about it is wrong.
    assert f"{PLAYER}.dat" in raised.value.safe_message
    # Refused before the copy, so the overlay is not left holding half a world.
    assert not (overlay / SAVES_DIRECTORY).exists()


def test_a_world_that_holds_someone_else_is_still_a_world_to_seed(tmp_path: Path) -> None:
    """The negative control: the rule is about *this* Kin, not about the directory.

    A world other players have been in is exactly what a shared snapshot looks
    like, and refusing it would turn a rule about one Kin's state into a rule
    about worlds.
    """

    save = _world(tmp_path)
    other = uuid.UUID("11111111-2222-3333-4444-555555555555")
    player_data_path(save, other).parent.mkdir()
    player_data_path(save, other).write_bytes(b"someone else\n")
    overlay = tmp_path / "overlay"
    overlay.mkdir()

    destination, _ = seed_world(
        overlay=overlay, save=save, player=PLAYER, level_name="prepared-world"
    )

    assert player_data_path(destination, other).is_file()
    assert not player_data_path(destination, PLAYER).exists()


def test_the_settings_digest_names_the_settings_and_not_the_terrain(tmp_path: Path) -> None:
    """Two saves that differ only in terrain have the same settings.

    Which is the whole reason this is hashed apart from the snapshot: a bundle says
    what a run started from, and the part of that which a case wants reproduced is
    the difficulty, the game rules and the generator — not the blocks.
    """

    save = _world(tmp_path)
    before = settings_digest(save)
    (save / "region" / "r.0.0.mca").write_bytes(b"different region bytes\n")

    assert settings_digest(save) == before

    (save / LEVEL_DAT).write_bytes(b"a different level.dat\n")

    assert settings_digest(save) != before


def test_a_directory_with_no_level_has_no_settings(tmp_path: Path) -> None:
    (tmp_path / "not-a-world").mkdir()

    with pytest.raises(MinekinError, match=f"no {LEVEL_DAT}"):
        settings_digest(tmp_path / "not-a-world")
