"""Persisting the identity root.

The identity root is the one row that makes a Kin the same Kin across restarts.
It is created only by an explicit init: a normal start that finds no identity
root must fail rather than quietly begin a new life, which is the difference
between resuming someone and replacing them.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.ids import KinId, OpaqueId
from minekin_core.domain.offline_identity import UUID_ALGORITHM, OfflineIdentityMaterial

_SELECT = (
    "SELECT kin_id, local_profile_id, identity_revision, username, uuid_algorithm, "
    "created_at_utc FROM kin_identity WHERE singleton = 1"
)


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "sqlite.identity", "read", ErrorCategory.STORAGE, Retryability.OPERATOR_ACTION, message
    )


@dataclass(frozen=True, slots=True)
class IdentityRoot:
    kin_id: KinId
    material: OfflineIdentityMaterial


def create_identity_root(
    connection: sqlite3.Connection, *, kin_id: KinId, material: OfflineIdentityMaterial
) -> IdentityRoot:
    """Create the identity root for a brand new Kin, or refuse.

    Refusing on a second call is what stops an operator mistake from silently
    re-pointing an existing Kin at a different identity.
    """

    if connection.execute("SELECT count(*) FROM kin_identity").fetchone()[0]:
        raise _reject("this database already has an identity root; a Kin is not created twice")
    connection.execute(
        "INSERT INTO kin_identity("
        "singleton, kin_id, local_profile_id, identity_revision, username, "
        "uuid_algorithm, created_at_utc"
        ") VALUES (1, ?, ?, ?, ?, ?, ?)",
        (
            str(kin_id),
            str(material.local_profile_id),
            material.identity_revision,
            material.username,
            UUID_ALGORITHM,
            material.created_at,
        ),
    )
    return IdentityRoot(kin_id=kin_id, material=material)


def read_identity_root(connection: sqlite3.Connection) -> IdentityRoot:
    """Read the identity root, or refuse; this never creates one."""

    row = connection.execute(_SELECT).fetchone()
    if row is None:
        raise _reject("identity root is missing; only an explicit init may create one")
    if row["uuid_algorithm"] != UUID_ALGORITHM:
        raise _reject(
            f"identity root was written by an unknown offline UUID algorithm "
            f"{row['uuid_algorithm']!r}"
        )
    try:
        kin_id = KinId(str(row["kin_id"]))
        material = OfflineIdentityMaterial(
            local_profile_id=OpaqueId(str(row["local_profile_id"])),
            identity_revision=int(row["identity_revision"]),
            username=str(row["username"]),
            created_at=str(row["created_at_utc"]),
        )
    except ValueError as error:
        raise _reject(f"identity root is not readable as an offline identity: {error}") from error
    return IdentityRoot(kin_id=kin_id, material=material)
