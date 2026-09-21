"""Where a hosted world's authoritative save lives, and which paths may be used.

The storage contract fixes the layout under the data root, and this module owns
it:

    kin/<kin_id>/hosted-worlds/<hosted_world_id>/
        manifest.yaml
        save/
        checkpoints/
        backups/

Two things are deliberately *not* decided here, because the contract has not
frozen them: how the save is made visible inside the session's game directory (a
managed run directory whose `saves/<slot>` is the persistent save, or a
controlled bind mount), and on which platforms each strategy is used. What both
strategies need is this half — whether a path may be used at all — and that rule
is frozen in as many words: whatever the strategy, the canonical path has to stay
inside that `kin_id/hosted_world_id` root.

Vanilla offers to skip the check (`LevelStorage.createSessionWithoutSymlinkCheck`)
and the contract forbids it, so the refusal below walks the path instead of
resolving it once. `Path.resolve()` on a symlinked ancestor returns the real
location and says nothing about how it got there, which is the same directory the
client would then write into — the client cannot tell the two apart, and neither
could anybody reading the run afterwards.

Identifiers are held to the same rule as level names, and for a measured reason.
`OpaqueId` allows `:`, and on Windows a `:` in a path segment is a drive: joining
`'a:b'` onto `C:/data` does not produce `C:/data/a:b`, it produces `a:b` — the
data root is gone. The same join with `'C:foo'` produces `foo`, so two different
identifiers would name one directory. Both are refused here rather than left to
whichever platform happens to be running.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePath
from typing import Final

from minekin_core.adapters.launcher.saves import level_name_is_usable

#: The directory family a Kin's own worlds live in, under the data root.
HOSTED_WORLDS_DIRECTORY: Final[str] = "hosted-worlds"
#: The authoritative save inside one hosted world. Never a copy: a second copy is
#: a second world, and the client writes to whichever one it was given.
SAVE_DIRECTORY: Final[str] = "save"
CHECKPOINTS_DIRECTORY: Final[str] = "checkpoints"
BACKUPS_DIRECTORY: Final[str] = "backups"
MANIFEST_NAME: Final[str] = "manifest.yaml"


class SavePathRefusal(StrEnum):
    """Why a path was not usable, one reason each."""

    #: An identifier that is not a plain single directory name. On Windows a `:`
    #: makes it a drive, which moves the whole path; the rule is the same one level
    #: names are held to.
    UNSAFE_IDENTIFIER = "UNSAFE_IDENTIFIER"
    #: A declared path that is not under the data root at all.
    OUTSIDE_DATA_ROOT = "OUTSIDE_DATA_ROOT"
    #: A declared path that resolves into another Kin's area. One Kin's world is
    #: never reachable through another's, whatever the manifest says.
    ANOTHER_KIN = "ANOTHER_KIN"
    #: A declared path that resolves into a different hosted world of this Kin.
    ANOTHER_WORLD = "ANOTHER_WORLD"
    #: Inside this world, but not its `save/`. A checkpoint or a backup is not the
    #: world, and starting a client against one would fork the world silently.
    NOT_THE_WORLDS_SAVE = "NOT_THE_WORLDS_SAVE"
    #: A symlink anywhere between the data root and the path. Named first because
    #: it is the mechanism: an escape is what a symlink would have caused.
    SYMLINK_IN_PATH = "SYMLINK_IN_PATH"


@dataclass(frozen=True, slots=True)
class HostedWorldPaths:
    """The three roots a hosted world is defined by, all absolute."""

    data_root: Path
    kin_root: Path
    world_root: Path
    save_root: Path

    def as_document(self) -> dict[str, object]:
        return {
            "data_root": str(self.data_root),
            "kin_root": str(self.kin_root),
            "world_root": str(self.world_root),
            "save_root": str(self.save_root),
        }


@dataclass(frozen=True, slots=True)
class SavePathDecision:
    """The answer about one path, and the reason it was answered that way."""

    admitted: bool
    paths: HostedWorldPaths | None
    refusal: SavePathRefusal | None
    #: What was wrong, in enough detail for the operator to act: which identifier,
    #: or which path was reached instead of the expected one.
    detail: str = ""

    def __str__(self) -> str:
        if self.admitted:
            return "ADMITTED"
        return f"{self.refusal}: {self.detail}" if self.detail else str(self.refusal)

    def as_document(self) -> dict[str, object]:
        return {
            "admitted": self.admitted,
            "refusal": None if self.refusal is None else self.refusal.value,
            "detail": self.detail,
            "paths": None if self.paths is None else self.paths.as_document(),
        }


def _refuse(refusal: SavePathRefusal, detail: str) -> SavePathDecision:
    return SavePathDecision(False, None, refusal, detail)


def _usable_identifier(value: str) -> bool:
    """Whether an identifier may be a path segment of the managed layout.

    The rule and the reason are `saves.level_name_is_usable`'s: a name that could
    move the destination elsewhere is refused by rule rather than by looking for
    `..`, because there is no list of spellings to enumerate. Held here as well
    because an identifier reaches this module from a directory name and from a
    manifest, neither of which is a validated `OpaqueId` by the time it arrives.
    """

    return level_name_is_usable(value)


def hosted_world_paths(*, data_root: Path, kin_id: str, hosted_world_id: str) -> SavePathDecision:
    """The layout's roots for one hosted world, or why they cannot be derived.

    Derivation only: nothing here needs the filesystem, so a caller can ask what a
    world's save *would* be before any of it exists.
    """

    if not data_root.is_absolute():
        return _refuse(SavePathRefusal.OUTSIDE_DATA_ROOT, f"{data_root} is not absolute")
    for label, value in (("kin_id", kin_id), ("hosted_world_id", hosted_world_id)):
        if not _usable_identifier(value):
            return _refuse(
                SavePathRefusal.UNSAFE_IDENTIFIER,
                f"{label} {value!r} is not a plain directory name",
            )

    root = data_root.resolve()
    kin_root = root / "kin" / kin_id
    world_root = kin_root / HOSTED_WORLDS_DIRECTORY / hosted_world_id
    return SavePathDecision(
        True,
        HostedWorldPaths(
            data_root=root,
            kin_root=kin_root,
            world_root=world_root,
            save_root=world_root / SAVE_DIRECTORY,
        ),
        None,
    )


def _symlinked_between(path: Path, stop: Path) -> Path | None:
    """The first symlink between `path` and `stop`, walking upwards, if any."""

    current = path
    while True:
        if current.is_symlink():
            return current
        if current == stop or current.parent == current:
            return None
        current = current.parent


def _resolved_below(path: Path, root: Path) -> Path | None:
    """`path` resolved, if the result is `root` or under it; otherwise None."""

    resolved = path.resolve()
    return resolved if resolved == root or resolved.is_relative_to(root) else None


def admit_save_root(*, declared: Path | PurePath, paths: HostedWorldPaths) -> SavePathDecision:
    """Whether a declared save root may be used as this world's authoritative save.

    The declared value comes from the world's manifest, which makes it data rather
    than a programmer's expression, so every refusal below is reachable by writing a
    different manifest. The symlink walk runs first and reports what it found:
    "the canonical path is outside the root" is the consequence, and naming the
    mechanism is what makes the refusal actionable.
    """

    if not declared.is_absolute():
        return _refuse(SavePathRefusal.OUTSIDE_DATA_ROOT, f"{declared} is not absolute")

    symlink = _symlinked_between(Path(declared), paths.data_root)
    if symlink is not None:
        return _refuse(
            SavePathRefusal.SYMLINK_IN_PATH,
            f"{symlink} is a symlink, and no part of a managed storage path may be one",
        )

    reached = _resolved_below(Path(declared), paths.data_root)
    if reached is None:
        return _refuse(
            SavePathRefusal.OUTSIDE_DATA_ROOT,
            f"{declared} resolves to {Path(declared).resolve()}, which is not under "
            f"{paths.data_root}",
        )

    if reached == paths.save_root or reached.is_relative_to(paths.save_root):
        # Its own save directory, or something inside it. The second is a path
        # inside the world rather than the world, which is the caller's business
        # and not a reason to refuse the directory itself.
        return SavePathDecision(True, paths, None)

    if reached.is_relative_to(paths.world_root):
        return _refuse(
            SavePathRefusal.NOT_THE_WORLDS_SAVE,
            f"{reached} is inside this world but is not its {SAVE_DIRECTORY}/",
        )
    if reached.is_relative_to(paths.world_root.parent):
        return _refuse(
            SavePathRefusal.ANOTHER_WORLD,
            f"{reached} is another hosted world of this Kin, not {paths.world_root}",
        )
    if reached.is_relative_to(paths.kin_root.parent):
        return _refuse(
            SavePathRefusal.ANOTHER_KIN,
            f"{reached} is another Kin's area, not {paths.kin_root}",
        )
    return _refuse(
        SavePathRefusal.OUTSIDE_DATA_ROOT,
        f"{reached} is under the data root but is not a hosted world of this Kin",
    )
