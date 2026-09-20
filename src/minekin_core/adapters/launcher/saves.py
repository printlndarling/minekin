"""Placing a prepared world where the client will look for it.

A managed client that is meant to *host* — the LAN half of the contract, where
one real client opens an integrated world and another joins it — has to be in a
world first. `IntegratedServer.openToLan` publishes the server the client is
already running, and a client at the title screen has none. Vanilla looks for its
worlds under `saves/<level>` inside the game directory, and the game directory is
the session overlay, so this is the step that puts one there.

The world is an operator-supplied save rather than one this launcher generates,
and that is a decision rather than an omission: a generated world would be a
different world every run, while the contract wants the world a host opened to be
*named* — by its seed or by a snapshot identity. A save directory that was
produced once and copied in is exactly that; the digest below is the name.

The digest is taken over the bytes as they were seeded, before the client can
write to them. A world the client has played in is a different world (it has new
region files and a rewritten `level.dat`), so a digest taken afterwards would
name something other than what was handed over.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

#: The file that makes a directory a world. Vanilla reads it to decide what to
#: generate and where the player was; without it a save is a pile of files.
LEVEL_DAT = "level.dat"

#: Where vanilla keeps its worlds inside the game directory.
SAVES_DIRECTORY = "saves"

#: Where vanilla keeps each player's own state inside a world — position, health,
#: inventory, whether they are dead. A world that has one for a player is a world
#: that player has been in, and loading it puts them back where they left.
PLAYER_DATA_DIRECTORY = "playerdata"

_WORKING = ".seeding"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.saves",
        "seed",
        ErrorCategory.CONFIG,
        Retryability.OPERATOR_ACTION,
        message,
    )


def saves_directory(overlay: Path) -> Path:
    """Where vanilla looks for worlds, given that the overlay is the game dir."""

    if not overlay.is_absolute():
        raise _reject("the session overlay must be an absolute path")
    return overlay.resolve() / SAVES_DIRECTORY


def level_name_is_usable(name: str) -> bool:
    """Whether a level name is a plain single directory name.

    The name becomes a path segment under `saves/`, so anything that could move
    the destination elsewhere is refused by *rule* rather than by looking for
    `..`: an absolute path, a separator, a drive letter, a NUL, or the two names
    that mean "here" and "up" are all simply not names of a world.
    """

    if not name or name in (".", ".."):
        return False
    if any(character in name for character in ("/", "\\", "\0", ":")):
        return False
    return name == name.strip()


def world_snapshot_digest(save: Path) -> str:
    """A name for the world's bytes: every file, its size, and its own digest.

    Deliberately not a hash of `level.dat` alone: the seed and the generator
    settings live there, but the world the host opened is the region files too,
    and two saves that differ only in terrain are two different worlds.
    """

    lines: list[str] = []
    for path in sorted(save.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(save).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{relative}\0{path.stat().st_size}\0{digest}\n")
    if not lines:
        # An empty directory is not a world, and a digest over nothing would make
        # it look like one that happens to have no files.
        raise _reject(f"{save} holds no files, so it is not a world to seed")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def player_data_path(save: Path, player: uuid.UUID) -> Path:
    """Where vanilla keeps one player's state inside this world.

    Existence is the whole signal, and it is enough: a world holding this file for
    a player is a world that player has been in, whatever the file then says.
    """

    return save / PLAYER_DATA_DIRECTORY / f"{player}.dat"


def settings_digest(save: Path) -> str:
    """A name for the world's own configuration, as it was handed over.

    `level.dat` holds what a world *is* rather than what is in it — difficulty, game
    rules, the generator settings, whether commands are allowed — and for a world with
    no server profile behind it that is the closest thing there is to a server
    configuration. It is hashed apart from the snapshot so a bundle can name the
    settings without the terrain: a case that wants the same starting conditions wants
    both, and only one of them changes when a run walks around.
    """

    path = save / LEVEL_DAT
    if not path.is_file():
        raise _reject(f"{save} is not a world: it has no {LEVEL_DAT}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed_world(
    *, overlay: Path, save: Path, level_name: str, player: uuid.UUID
) -> tuple[Path, str]:
    """Copy one prepared save into the overlay's `saves/`, and name its bytes.

    Placed through a staging directory inside `saves/` and renamed into position,
    for the same reason the artifact store stages: a reader that sees the
    directory must see all of it, and vanilla checks for `level.dat` the moment
    it looks at a level.

    `player` is the Kin this world is being seeded for, and a world that already
    holds their state is refused. That is measured rather than cautious: a world
    taken from an earlier run carried `Health 0` and a non-zero `DeathTime`, and
    the client loaded the Kin *dead* — it went straight to the death screen with
    no death in its log, because no death happened. The run looked like a run. A
    world a Kin has been in is not the "clean snapshot" every case is required to
    start from, and what it would silently load is the Kin as they were left.
    """

    if not level_name_is_usable(level_name):
        raise _reject(f"{level_name!r} is not a usable level name")
    source = save.resolve()
    if not source.is_dir():
        raise _reject(f"{save} is not a directory to seed from")
    if not (source / LEVEL_DAT).is_file():
        raise _reject(f"{save} is not a world: it has no {LEVEL_DAT}")
    history = player_data_path(source, player)
    if history.is_file():
        raise _reject(
            f"{save} already holds this Kin ({history.name}), so it is not a clean "
            f"world to start from: the client would load this Kin exactly as that "
            f"run left them — left dead, loaded dead — instead of at the start of "
            f"this one"
        )

    saves = saves_directory(overlay)
    saves.mkdir(parents=True, exist_ok=True)
    destination = (saves / level_name).resolve()
    if destination.parent != saves.resolve():
        # A name that survived the rule above cannot get here, and a copy that
        # lands outside `saves/` is not a world the client could ever find.
        raise _reject(f"{level_name!r} does not resolve to a level inside {SAVES_DIRECTORY}/")
    if destination.exists():
        # Overlays are per generation, so this means somebody has already put a
        # world here. Refused rather than merged: two worlds' region files in one
        # directory is a world neither of them describes.
        raise _reject(f"{destination} already holds a world")

    digest = world_snapshot_digest(source)
    staging = saves / f"{_WORKING}-{level_name}"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(source, staging)
    staging.rename(destination)
    return destination, digest
