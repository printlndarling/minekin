"""Renaming one Kin's offline identity by deliberate, confirmed operator action.

A new Kin gets a stable default name (`minekin`) and keeps it: nothing about
starting, stopping, dying or changing servers renames it. The only way a
persisted identity changes its name is this command, and it changes it the way
the offline UUID rule makes unavoidable — a different name resolves a different
offline player UUID, so an already-loaded server sees a different player and
does not migrate inventory, position or advancements. That consequence is the
reason rename lives behind an explicit, stopped-session confirmation rather than
a launch flag.

The rename commits a new identity revision atomically against the revision the
caller reviewed, so it cannot clobber a concurrent change, and it never touches
an `event`/run row: past runs keep the identity they actually played under.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from minekin_core.adapters.sqlite.connection import connect_writer
from minekin_core.adapters.sqlite.identity_store import (
    IdentityRoot,
    read_identity_root,
    rename_identity_root,
)
from minekin_core.cli.session import database_for
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.ids import KinId, OpaqueId
from minekin_core.domain.offline_identity import (
    OfflineIdentityMaterial,
    is_valid_username,
)

RENAME_NOTICE = (
    "An offline player's UUID is derived from their exact name. Renaming this Kin "
    "will resolve a new offline UUID, so any server it already joined will treat it "
    "as a different player: inventory, position and advancements do not migrate. "
    "Rename only while the session is stopped, and only deliberately."
)


def _reject_config(message: str) -> MinekinError:
    return MinekinError(
        "cli.identity", "rename", ErrorCategory.CONFIG, Retryability.OPERATOR_ACTION, message
    )


@dataclass(frozen=True, slots=True)
class IdentityView:
    """The stored identity in the shape an operator or panel has to review."""

    kin_id: str
    username: str
    uuid_canonical: str
    identity_revision: int

    @staticmethod
    def of(root: IdentityRoot) -> IdentityView:
        return IdentityView(
            kin_id=str(root.kin_id),
            username=root.material.username,
            uuid_canonical=root.material.uuid_canonical,
            identity_revision=root.material.identity_revision,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "kin_id": self.kin_id,
            "username": self.username,
            "uuid_canonical": self.uuid_canonical,
            "identity_revision": self.identity_revision,
        }


@dataclass(frozen=True, slots=True)
class RenameReport:
    """What a rename did, naming both the old and new identity and the impact."""

    kin_id: str
    status: str
    before: IdentityView
    after: IdentityView
    database: str

    @property
    def uuid_changed(self) -> bool:
        return self.before.uuid_canonical != self.after.uuid_canonical

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "identity rename",
            "status": self.status,
            "kin_id": self.kin_id,
            "before": self.before.as_dict(),
            "after": self.after.as_dict(),
            "uuid_changed": self.uuid_changed,
            "notice": RENAME_NOTICE,
            "database": self.database,
        }


def show_identity(root: Path, kin_id: KinId) -> IdentityView:
    """Read one Kin's stored name and offline UUID, changing nothing."""

    database = database_for(root, kin_id)
    if not database.is_file():
        raise _reject_config(f"{database} is missing; run `minekin init` first")
    connection = connect_writer(database)
    try:
        return IdentityView.of(read_identity_root(connection))
    finally:
        connection.close()


def rename_identity(
    kin_id: KinId,
    *,
    root: Path,
    username: str,
    expected_revision: int | None = None,
) -> RenameReport:
    """Commit `username` as this Kin's new name, or refuse without mutating.

    `expected_revision` is the identity revision the caller reviewed. When it is
    given, a row that has moved past it is refused rather than overwritten. When
    it is omitted, the revision read moments ago is used — the write is still a
    compare-and-swap, so a rename concurrent with this one cannot both land.
    Renaming to the name a Kin already answers to is reported as unchanged and
    writes nothing.
    """

    if not is_valid_username(username):
        raise _reject_config(
            f"{username!r} is not a valid Minecraft name (3-16 letters, digits or underscore)"
        )

    database = database_for(root, kin_id)
    if not database.is_file():
        raise _reject_config(f"{database} is missing; run `minekin init` first")

    connection = connect_writer(database)
    try:
        current = read_identity_root(connection)
        before = IdentityView.of(current)
        if current.material.username == username:
            return RenameReport(
                kin_id=str(kin_id),
                status="unchanged",
                before=before,
                after=before,
                database=str(database),
            )

        reviewed = (
            current.material.identity_revision if expected_revision is None else expected_revision
        )
        new_revision = reviewed + 1
        material = OfflineIdentityMaterial(
            local_profile_id=OpaqueId(f"{kin_id}-r{new_revision}"),
            identity_revision=new_revision,
            username=username,
            created_at=current.material.created_at,
        )
        rename_identity_root(connection, material=material, expected_revision=reviewed)
    finally:
        connection.close()

    after = IdentityView(
        kin_id=str(kin_id),
        username=material.username,
        uuid_canonical=material.uuid_canonical,
        identity_revision=material.identity_revision,
    )
    return RenameReport(
        kin_id=str(kin_id), status="renamed", before=before, after=after, database=str(database)
    )
