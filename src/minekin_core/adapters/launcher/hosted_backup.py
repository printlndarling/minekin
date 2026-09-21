"""Where a cold backup goes, and where a restore is allowed to write.

The storage contract's backup section as rules rather than as prose. Two of them
are about paths, and they are the two that decide whether a bad afternoon stays
recoverable:

- **A verified backup is never overwritten** (HOST-060). The habit this refuses is
  a reasonable-looking one: re-run the backup for a world, and the target — the
  same name every time, because that is what a schedule produces — clobbers the
  last good copy with a copy of a save that has since gone bad. An *unverified*
  leftover may be replaced, because that is what a backup interrupted halfway
  leaves behind and refusing to retry it would need a person every time.
- **A restore produces a new copy and leaves the original alone** (HOST-070). A
  destination inside the tree being restored from is the shape that turns "restore
  from the backup" into "write the backup over itself", and the contract asks for
  the original to survive a failed restore and for the attempt to be recorded.

The contract's other two sentences about backups are not rules this module can
hold. A backup is made after the integrated server has flushed and closed, which
is a fact about a run; and rotation and quota are named and not specified, so
nothing here invents a retention policy. What *is* fixed is the record: world and
epoch, bundle, checkpoint, a manifest digest over the files, the size, why it was
made, and whether it verified — so that record is a value here rather than a shape
each caller spells again.

Staging is the same idea `saves.py` uses for seeding: a backup is written to a
temporary name beside its target and published by a rename, so a reader either
finds no backup or finds a whole one, and the digest is taken from the bytes that
were actually published.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePath

from minekin_core.adapters.launcher.hosted_store import (
    BACKUPS_DIRECTORY,
    HostedWorldPaths,
    admit_save_root,
)
from minekin_core.adapters.launcher.saves import level_name_is_usable
from minekin_core.domain.ids import Generation

#: The name a backup is built under before it is published, beside its target and
#: therefore inside the same directory: publishing is a rename, which is atomic
#: within one filesystem and moves nothing across one.
STAGING_PREFIX = ".publishing-"


class BackupRefusal(StrEnum):
    """Why a backup may not be written where it was going."""

    #: Not a plain single directory name. The same rule level names and world ids
    #: are held to, and for the same reason: a name that can move the destination
    #: is refused by rule rather than by looking for a particular spelling.
    UNSAFE_NAME = "UNSAFE_NAME"
    #: HOST-060. A verified backup is the last good copy of a world until another
    #: one has been verified, so replacing it is refused rather than reported.
    ALREADY_VERIFIED = "ALREADY_VERIFIED"


class RestoreRefusal(StrEnum):
    """Why a restore may not write where it was going."""

    #: The destination is inside the tree being restored from. This is the rule that
    #: keeps the original able to survive a failed restore.
    DESTINATION_INSIDE_SOURCE = "DESTINATION_INSIDE_SOURCE"
    #: The destination *is* the source.
    DESTINATION_IS_THE_SOURCE = "DESTINATION_IS_THE_SOURCE"
    #: The destination is not a hosted world's own save root, so a restore there
    #: would not produce a world this Kin's store could find again.
    DESTINATION_NOT_A_WORLD = "DESTINATION_NOT_A_WORLD"
    #: Something is already there. A restore produces a new copy, and a copy onto an
    #: existing directory is a merge of two worlds' region files.
    DESTINATION_EXISTS = "DESTINATION_EXISTS"


@dataclass(frozen=True, slots=True)
class BackupRecord:
    """What a backup records, as the contract lists it.

    `verified` is on the record rather than inferred, because it is the field the
    overwrite rule reads: a backup nobody has checked is the one it is safe to
    replace, and a backup that verified is the one it is not.
    """

    hosted_world_id: str
    world_epoch: Generation
    bundle_id: str
    checkpoint_ref: str
    #: A digest over the files a backup holds, so the record names what it kept
    #: rather than how much of it there was.
    manifest_digest: str
    size_bytes: int
    #: Why this backup was made, in the words of whoever asked for it. Recorded
    #: rather than enumerated: the contract names the field and not its vocabulary.
    reason: str
    verified: bool

    def as_document(self) -> dict[str, object]:
        return {
            "hosted_world_id": self.hosted_world_id,
            "world_epoch": int(self.world_epoch),
            "bundle_id": self.bundle_id,
            "checkpoint_ref": self.checkpoint_ref,
            "manifest_digest": self.manifest_digest,
            "size_bytes": self.size_bytes,
            "reason": self.reason,
            "verified": self.verified,
        }


@dataclass(frozen=True, slots=True)
class BackupDecision:
    """Where a backup would be built and published, or why it may not be."""

    admitted: bool
    staging: Path | None = None
    published: Path | None = None
    refusal: BackupRefusal | None = None
    detail: str = ""

    def __str__(self) -> str:
        if self.admitted:
            return f"BACKUP:{self.published}"
        return f"{self.refusal}: {self.detail}" if self.detail else str(self.refusal)

    def as_document(self) -> dict[str, object]:
        return {
            "admitted": self.admitted,
            "staging": None if self.staging is None else str(self.staging),
            "published": None if self.published is None else str(self.published),
            "refusal": None if self.refusal is None else self.refusal.value,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class RestoreDecision:
    """Where a restore would write, or why it may not."""

    admitted: bool
    destination: Path | None = None
    refusal: RestoreRefusal | None = None
    detail: str = ""

    def __str__(self) -> str:
        if self.admitted:
            return f"RESTORE:{self.destination}"
        return f"{self.refusal}: {self.detail}" if self.detail else str(self.refusal)

    def as_document(self) -> dict[str, object]:
        return {
            "admitted": self.admitted,
            "destination": None if self.destination is None else str(self.destination),
            "refusal": None if self.refusal is None else self.refusal.value,
            "detail": self.detail,
        }


def backup_targets(*, paths: HostedWorldPaths, name: str) -> BackupDecision:
    """The two names one backup uses, or why the name cannot be one.

    Both are derived from the world's own `backups/`, so a backup can never be
    written outside it: deleting a backup and deleting a world are different
    authorities in the contract, and a path rule that only checked the caller's
    string would be the place that distinction leaks.
    """

    if not level_name_is_usable(name) or name.startswith(STAGING_PREFIX):
        return BackupDecision(
            False,
            refusal=BackupRefusal.UNSAFE_NAME,
            detail=f"{name!r} is not a plain backup name",
        )

    published = paths.world_root / BACKUPS_DIRECTORY / name
    return BackupDecision(
        True, staging=published.parent / f"{STAGING_PREFIX}{name}", published=published
    )


def admit_backup(
    *, paths: HostedWorldPaths, name: str, existing: BackupRecord | None
) -> BackupDecision:
    """Whether a backup may be published under this name (HOST-060).

    Publishing onto an existing name is a rename that replaces what is there, so
    this is the rule that decides whether that is allowed at all. `existing` is the
    record for whatever already holds that name, or None when no record does — an
    unrecorded leftover is not a good backup, and refusing it would make an
    interrupted run need a person.
    """

    decision = backup_targets(paths=paths, name=name)
    if not decision.admitted:
        return decision
    if existing is not None and existing.verified:
        return BackupDecision(
            False,
            staging=decision.staging,
            published=decision.published,
            refusal=BackupRefusal.ALREADY_VERIFIED,
            detail=(
                f"{decision.published} holds a verified backup of "
                f"{existing.hosted_world_id} epoch {int(existing.world_epoch)}; "
                f"a backup that verified is not replaced"
            ),
        )
    return decision


def admit_restore(
    *,
    destination_world: HostedWorldPaths,
    source: Path | PurePath,
    destination: Path | PurePath,
    destination_exists: bool,
) -> RestoreDecision:
    """Whether a restore may write to `destination` (HOST-070).

    `destination_world` is the world being written into, which is not always the
    one the backup came from: a rollback restores a world into itself under a new
    epoch, and a fork restores it into a world that did not exist — so the caller
    resolves the destination world and this asks whether the path really is that
    world's save root, using the same admission the store uses for every other
    world path, and the same refusals.

    The refusals are checked most-specific first so the answer names the actual
    mistake: a destination that *is* the source is a different finding from one
    inside it, and both differ from one that is not a world at all.
    """

    restored_from = Path(source)
    target = Path(destination)
    if target == restored_from:
        return RestoreDecision(
            False,
            refusal=RestoreRefusal.DESTINATION_IS_THE_SOURCE,
            detail=f"{target} is what is being restored from",
        )
    if target.is_relative_to(restored_from):
        return RestoreDecision(
            False,
            refusal=RestoreRefusal.DESTINATION_INSIDE_SOURCE,
            detail=(
                f"{target} is inside {restored_from}, and a restore that writes there "
                f"would be modifying the copy it is restoring from"
            ),
        )
    admission = admit_save_root(declared=target, paths=destination_world)
    if not admission.admitted:
        # The store's own reason travels in the detail: "another Kin's area",
        # "outside the data root" and "a symlink" are different mistakes, and this
        # module is not the place that has to spell them again.
        return RestoreDecision(
            False,
            refusal=RestoreRefusal.DESTINATION_NOT_A_WORLD,
            detail=f"{target} is not {destination_world.world_root}: {admission}",
        )
    if destination_exists:
        return RestoreDecision(
            False,
            refusal=RestoreRefusal.DESTINATION_EXISTS,
            detail=f"{target} already holds something; a restore produces a new copy",
        )
    return RestoreDecision(True, destination=target)
