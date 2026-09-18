"""Creating one Kin's identity root under the operator's data root.

`init` is the only command that creates a Kin. Everything else refuses to, which
is the difference between resuming someone and replacing them, so this module is
deliberately unwilling to be convenient about an existing directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from minekin_core.adapters.sqlite.connection import connect_writer
from minekin_core.adapters.sqlite.identity_store import create_identity_root
from minekin_core.application.ports.clock import Clock
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.ids import KinId, OpaqueId
from minekin_core.domain.offline_identity import OfflineIdentityMaterial

KIN_DIRECTORY = "kin"
DATABASE_NAME = "kin.sqlite3"
RUN_DIRECTORY = "run"
INITIAL_IDENTITY_REVISION = 1


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "cli.init", "create", ErrorCategory.CONFIG, Retryability.OPERATOR_ACTION, message
    )


@dataclass(frozen=True, slots=True)
class InitReport:
    """What `init` created, in a shape an operator can read and paste into a ticket."""

    kin_id: str
    username: str
    identity_revision: int
    database: str
    run_root: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": "created",
            "kin_id": self.kin_id,
            "username": self.username,
            "identity_revision": self.identity_revision,
            "database": self.database,
            "run_root": self.run_root,
        }


def kin_directory(root: Path, kin_id: KinId) -> Path:
    return root / KIN_DIRECTORY / str(kin_id)


def run_root(root: Path, kin_id: KinId) -> Path:
    """The directory the launch plan's relative paths are resolved against."""

    return kin_directory(root, kin_id) / RUN_DIRECTORY


def initialise_identity(kin_id: KinId, *, root: Path, username: str, clock: Clock) -> InitReport:
    """Create the identity root for a new Kin, or refuse without touching anything."""

    directory = kin_directory(root, kin_id)
    database = directory / DATABASE_NAME
    if database.exists():
        # Not idempotent on purpose: re-running init against an existing Kin
        # would re-point it, and the operator can remove the directory if that
        # is genuinely what they want.
        raise _reject(f"{database} already exists; remove it deliberately to start over")

    material = OfflineIdentityMaterial(
        local_profile_id=OpaqueId(f"{kin_id}-r{INITIAL_IDENTITY_REVISION}"),
        identity_revision=INITIAL_IDENTITY_REVISION,
        username=username,
        created_at=clock.utc_now().isoformat(),
    )

    runs = run_root(root, kin_id)
    runs.mkdir(parents=True, exist_ok=True)
    connection = connect_writer(database)
    try:
        create_identity_root(connection, kin_id=kin_id, material=material)
    finally:
        connection.close()

    return InitReport(
        kin_id=str(kin_id),
        username=material.username,
        identity_revision=material.identity_revision,
        database=str(database),
        run_root=str(runs),
    )
