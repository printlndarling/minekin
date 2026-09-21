"""Where a backup goes and where a restore may write, both as path rules.

Two clauses of the storage contract are about paths, and each of them is the
difference between a bad afternoon and an unrecoverable one:

- HOST-060: a verified backup is not replaced. The failure it prevents is the one a
  schedule produces on its own — the same target name every time — where a re-run
  overwrites the last good copy with a copy of a save that has since gone bad.
- HOST-070: a restore writes a new copy and leaves the original alone. A destination
  inside the tree being restored from is how "restore from the backup" becomes
  "write the backup over itself".

The tests are written against those harms rather than against the functions: each
one names what would have happened, and the refusals are checked by reason so that
"the destination is the source" and "the destination is inside the source" stay
distinguishable answers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from minekin_core.adapters.launcher.hosted_backup import (
    STAGING_PREFIX,
    BackupRecord,
    BackupRefusal,
    RestoreRefusal,
    admit_backup,
    admit_restore,
    backup_targets,
)
from minekin_core.adapters.launcher.hosted_store import (
    BACKUPS_DIRECTORY,
    SAVE_DIRECTORY,
    HostedWorldPaths,
    hosted_world_paths,
)
from minekin_core.domain.ids import Generation

KIN = "kin-1"
WORLD = "hosted-world-1"
OTHER_WORLD = "hosted-world-2"


def paths_for(root: Path, world: str = WORLD) -> HostedWorldPaths:
    decision = hosted_world_paths(data_root=root, kin_id=KIN, hosted_world_id=world)
    assert decision.admitted and decision.paths is not None, decision
    return decision.paths


def record(*, verified: bool = True, world: str = WORLD, epoch: int = 1) -> BackupRecord:
    return BackupRecord(
        hosted_world_id=world,
        world_epoch=Generation(epoch),
        bundle_id="p0-core-1.21.4",
        checkpoint_ref="checkpoint-1",
        manifest_digest="a" * 64,
        size_bytes=4096,
        reason="before an upgrade",
        verified=verified,
    )


# ---------------------------------------------------------------------------
# HOST-060: the backup
# ---------------------------------------------------------------------------


def test_a_backup_is_built_beside_its_target_and_published_by_a_rename(tmp_path: Path) -> None:
    """The staging name is in the same directory, so publishing moves no bytes.

    A rename within one filesystem is the only publish that cannot leave a reader
    looking at half a backup, and the digest is taken from what was published
    rather than from what was staged.
    """

    paths = paths_for(tmp_path)

    decision = backup_targets(paths=paths, name="2026-09-22-before-upgrade")

    assert decision.admitted is True, decision
    assert decision.staging is not None
    assert decision.published is not None
    assert decision.staging.parent == decision.published.parent
    assert decision.published == paths.world_root / BACKUPS_DIRECTORY / "2026-09-22-before-upgrade"
    assert decision.staging.name == f"{STAGING_PREFIX}2026-09-22-before-upgrade"


def test_a_verified_backup_is_not_replaced(tmp_path: Path) -> None:
    """HOST-060: the last good copy of a world is not something a re-run replaces."""

    paths = paths_for(tmp_path)

    decision = admit_backup(paths=paths, name="nightly", existing=record(verified=True))

    assert decision.admitted is False
    assert decision.refusal is BackupRefusal.ALREADY_VERIFIED
    assert WORLD in decision.detail and "epoch 1" in decision.detail


def test_an_unverified_leftover_may_be_replaced(tmp_path: Path) -> None:
    """A backup interrupted halfway is exactly what a retry is for.

    Refusing this would make every interrupted backup need a person, and the rule
    the contract states is about *good* backups rather than about names in use.
    """

    paths = paths_for(tmp_path)

    for existing in (None, record(verified=False)):
        decision = admit_backup(paths=paths, name="nightly", existing=existing)

        assert decision.admitted is True, existing


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "a/b", "a\\b", "a:b", " padded ", f"{STAGING_PREFIX}nightly"],
)
def test_a_backup_name_that_is_not_a_plain_name_is_refused(tmp_path: Path, name: str) -> None:
    """Held to the level-name rule, plus the staging prefix itself.

    The prefix is refused because a backup named like a staging directory would be
    swept up by whatever cleans a failed publish, and because two backups could
    then name the same bytes.
    """

    decision = backup_targets(paths=paths_for(tmp_path), name=name)

    assert decision.admitted is False
    assert decision.refusal is BackupRefusal.UNSAFE_NAME


def test_a_backup_can_never_be_written_outside_the_worlds_own_backups(tmp_path: Path) -> None:
    """Deleting a backup and deleting a world are different authorities.

    The target is derived rather than accepted, so the distinction has one place to
    hold: whatever a caller writes in the name, the two paths are under this world.
    """

    paths = paths_for(tmp_path)

    decision = backup_targets(paths=paths, name="nightly")

    assert decision.published is not None and decision.staging is not None
    for path in (decision.published, decision.staging):
        assert path.is_relative_to(paths.world_root / BACKUPS_DIRECTORY)
    assert not (paths.world_root / BACKUPS_DIRECTORY).is_relative_to(paths.save_root)


def test_a_record_says_what_was_kept_and_whether_it_verified(tmp_path: Path) -> None:
    """The contract lists the fields; the record is that list and not a paraphrase."""

    document = record(verified=False, epoch=3).as_document()

    assert document == {
        "hosted_world_id": WORLD,
        "world_epoch": 3,
        "bundle_id": "p0-core-1.21.4",
        "checkpoint_ref": "checkpoint-1",
        "manifest_digest": "a" * 64,
        "size_bytes": 4096,
        "reason": "before an upgrade",
        "verified": False,
    }


# ---------------------------------------------------------------------------
# HOST-070: the restore
# ---------------------------------------------------------------------------


def source_backup(tmp_path: Path) -> Path:
    """A backup on disk, as the store would have it."""

    backup = paths_for(tmp_path).world_root / BACKUPS_DIRECTORY / "nightly" / SAVE_DIRECTORY
    backup.mkdir(parents=True)
    return backup


def test_a_restore_into_a_new_world_is_admitted(tmp_path: Path) -> None:
    """The restore the contract asks for: a new copy, in a world of its own."""

    source = source_backup(tmp_path)
    # A restore into a world that did not exist before: the backup came from one
    # world and the copy is another, which is what a fork is.
    destination_world = paths_for(tmp_path, OTHER_WORLD)

    decision = admit_restore(
        destination_world=destination_world,
        source=source,
        destination=destination_world.save_root,
        destination_exists=False,
    )

    assert decision.admitted is True, decision
    assert decision.destination == destination_world.save_root


def test_restoring_onto_the_source_itself_is_refused(tmp_path: Path) -> None:
    """Writing over the copy being read is the shape that loses both."""

    source = source_backup(tmp_path)

    decision = admit_restore(
        destination_world=paths_for(tmp_path),
        source=source,
        destination=source,
        destination_exists=True,
    )

    assert decision.admitted is False
    assert decision.refusal is RestoreRefusal.DESTINATION_IS_THE_SOURCE


def test_restoring_inside_the_source_is_refused(tmp_path: Path) -> None:
    """HOST-070: the original survives a failed restore, so nothing writes in it.

    The destination below is inside the backup being read — a plausible thing to
    type, and the one that would make the restore modify its own input.
    """

    source = source_backup(tmp_path)

    decision = admit_restore(
        destination_world=paths_for(tmp_path),
        source=source,
        destination=source / "restored",
        destination_exists=False,
    )

    assert decision.admitted is False
    assert decision.refusal is RestoreRefusal.DESTINATION_INSIDE_SOURCE
    assert str(source) in decision.detail


def test_a_destination_that_is_not_a_world_is_refused(tmp_path: Path) -> None:
    """A copy into the artifacts directory is a world nothing would find again."""

    source = source_backup(tmp_path)
    paths = paths_for(tmp_path)

    decision = admit_restore(
        destination_world=paths,
        source=source,
        destination=paths.data_root / "artifacts",
        destination_exists=False,
    )

    assert decision.admitted is False
    assert decision.refusal is RestoreRefusal.DESTINATION_NOT_A_WORLD


def test_a_destination_that_already_holds_something_is_refused(tmp_path: Path) -> None:
    """A restore produces a new copy; a copy onto a world merges two of them."""

    source = source_backup(tmp_path)
    destination_world = paths_for(tmp_path, OTHER_WORLD)

    decision = admit_restore(
        destination_world=destination_world,
        source=source,
        destination=destination_world.save_root,
        destination_exists=True,
    )

    assert decision.admitted is False
    assert decision.refusal is RestoreRefusal.DESTINATION_EXISTS


def test_the_most_specific_refusal_is_the_one_reported(tmp_path: Path) -> None:
    """A destination that is the source *and* exists is reported as the source.

    Both are true, and only one of them tells an operator what to fix: an existing
    directory is expected when a restore is attempted twice, while a destination
    that is its own source is a mistake that has to be pointed at.
    """

    source = source_backup(tmp_path)

    decision = admit_restore(
        destination_world=paths_for(tmp_path),
        source=source,
        destination=source,
        destination_exists=True,
    )

    assert decision.refusal is RestoreRefusal.DESTINATION_IS_THE_SOURCE
    assert decision.refusal is not RestoreRefusal.DESTINATION_EXISTS
