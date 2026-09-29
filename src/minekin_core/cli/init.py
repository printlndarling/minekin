"""Creating one Kin's identity root under the operator's data root.

`init` is the only command that creates a Kin. Everything else refuses to, which
is the difference between resuming someone and replacing them, so this module is
deliberately unwilling to be convenient about an existing directory.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from minekin_core.adapters.filestore.persona_store import persona_path, write_persona
from minekin_core.adapters.sqlite.connection import connect_writer
from minekin_core.adapters.sqlite.identity_store import create_identity_root
from minekin_core.application.ports.clock import Clock
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.ids import KinId, OpaqueId
from minekin_core.domain.offline_identity import OfflineIdentityMaterial
from minekin_core.domain.persona import derive_persona

KIN_DIRECTORY = "kin"
DATABASE_NAME = "kin.sqlite3"
RUN_DIRECTORY = "run"
INITIAL_IDENTITY_REVISION = 1
#: How long a drawn seed is, when the operator did not state one. It is not a
#: credential — it names a person, it does not authorise anything — but it is
#: long enough that two Kins drawn in the same second are not the same person.
DRAWN_SEED_BYTES = 8


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
    persona_file: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "status": "created",
            "kin_id": self.kin_id,
            "username": self.username,
            "identity_revision": self.identity_revision,
            "database": self.database,
            "run_root": self.run_root,
            "persona_file": self.persona_file,
        }


def kin_directory(root: Path, kin_id: KinId) -> Path:
    return root / KIN_DIRECTORY / str(kin_id)


def run_root(root: Path, kin_id: KinId) -> Path:
    """The directory the launch plan's relative paths are resolved against."""

    return kin_directory(root, kin_id) / RUN_DIRECTORY


def initialise_identity(
    kin_id: KinId,
    *,
    root: Path,
    username: str,
    clock: Clock,
    persona_seed: str | None = None,
) -> InitReport:
    """Create a new Kin's identity root and initial persona, or refuse without touching anything.

    The persona is created here and nowhere else, because the seed is drawn once:
    a later command that found no manifest would otherwise be free to invent one,
    and `docs/persona-generation-contract.md` forbids redrawing a person on
    restart. A stated seed is used verbatim; an absent one is drawn and then
    persisted like any other, so the person this Kin got stays reproducible from
    its own directory.
    """

    directory = kin_directory(root, kin_id)
    database = directory / DATABASE_NAME
    if database.exists():
        # Not idempotent on purpose: re-running init against an existing Kin
        # would re-point it, and the operator can remove the directory if that
        # is genuinely what they want.
        raise _reject(f"{database} already exists; remove it deliberately to start over")
    if persona_path(directory).exists():
        raise _reject(
            f"{persona_path(directory)} already exists while {database} does not; "
            "a half-created root is not repaired by init"
        )

    seed = persona_seed if persona_seed is not None else secrets.token_hex(DRAWN_SEED_BYTES)
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
    manifest = derive_persona(str(kin_id), seed)
    persona_file = write_persona(directory, manifest)

    return InitReport(
        kin_id=str(kin_id),
        username=material.username,
        identity_revision=material.identity_revision,
        database=str(database),
        run_root=str(runs),
        persona_file=str(persona_file),
    )
