"""Starting a managed session from a reviewed profile.

The command refuses far more often than it starts, and that is the point: a run
that begins with a missing artifact or a half-downloaded store produces evidence
nobody can trust, so readiness is checked before anything is created.

This is the composition root for a launch. Every step it uses is built and tested
on its own, so what is left here is the order and the refusal rules.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.artifacts import ArtifactStore, SessionOverlayStore
from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.offline_session import OFFLINE_SESSION_CANDIDATES
from minekin_core.adapters.launcher.process import build_process_spec
from minekin_core.adapters.launcher.supervisor import ProcessIdentity, ProcessSupervisor
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.identity_store import read_identity_root
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.cli.init import DATABASE_NAME, KIN_DIRECTORY, kin_directory, run_root
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.ids import KinId

SupervisorFactory = Callable[[Path], ProcessSupervisor]


def _reject(message: str, category: ErrorCategory = ErrorCategory.CONFIG) -> MinekinError:
    return MinekinError("cli.session", "start", category, Retryability.OPERATOR_ACTION, message)


def default_supervisor_factory(log_directory: Path) -> ProcessSupervisor:
    return ProcessSupervisor(clock=SystemClock(), log_directory=log_directory)


@dataclass(frozen=True, slots=True)
class SessionLaunch:
    session_id: str
    generation: int
    kin_id: str
    overlay: str
    identity: ProcessIdentity
    argv_digest: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": "started",
            "kin_id": self.kin_id,
            "session_id": self.session_id,
            "generation": self.generation,
            "overlay": self.overlay,
            "pid": self.identity.pid,
            "started_at": self.identity.started_at,
            "argv_digest": self.argv_digest,
        }


def select_kin(root: Path, selector: str | None) -> KinId:
    """Which Kin this root belongs to.

    A root holding exactly one Kin needs no selector; anything else is ambiguous
    and must be stated rather than guessed, because starting the wrong Kin is not
    something a later step can undo.
    """

    base = root / KIN_DIRECTORY
    candidates = (
        sorted(path.name for path in base.iterdir() if path.is_dir()) if base.is_dir() else []
    )
    if selector:
        if selector not in candidates:
            raise _reject(f"this root holds no Kin named {selector!r}")
        return KinId(selector)
    if not candidates:
        raise _reject(f"no Kin exists under {base}; run `minekin init` first")
    if len(candidates) > 1:
        raise _reject(
            f"this root holds more than one Kin ({', '.join(candidates)}); select one explicitly"
        )
    return KinId(candidates[0])


def database_for(root: Path, kin_id: KinId) -> Path:
    return kin_directory(root, kin_id) / DATABASE_NAME


def session_overlay_path(run_root: Path, session_id: str, generation: int) -> Path:
    """Where the overlay for one session generation lives.

    The path is a function of its inputs rather than something to be discovered,
    so the supervisor's log directory can be named before the overlay exists.
    """

    return run_root / "session" / session_id / f"generation-{generation}"


def require_launchable(plan: Mapping[str, Any]) -> None:
    """Refuse before creating anything when the plan already knows it cannot run."""

    if plan.get("launchable") is not True:
        blockers = cast(list[object], plan.get("blockers", []))
        listed = ", ".join(str(item) for item in blockers) or "unspecified"
        raise _reject(
            f"the bundle profile is not launchable yet: {listed}", ErrorCategory.SUPPLY_CHAIN
        )


def _artifact_from(entry: Mapping[str, Any]) -> Artifact:
    """Read one plan artifact, refusing a malformed entry rather than coercing it."""

    try:
        size = entry["size"]
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("size")
        return Artifact(
            coordinate=str(entry["coordinate"]),
            path=str(entry["path"]),
            url=str(entry["url"]),
            size=size,
            sha1=str(entry["sha1"]),
            kind=str(entry.get("kind", "library")),
        )
    except (KeyError, TypeError) as error:
        raise _reject(
            f"launch plan artifact entry is malformed: {error}", ErrorCategory.SUPPLY_CHAIN
        ) from error


def require_store_complete(plan: Mapping[str, Any], store: ArtifactStore) -> None:
    """Every artifact the plan names must already be in the store, verified.

    All of them, not only the ones in argv: a missing asset makes the client fail
    in ways that look like a rendering bug rather than a missing download.
    """

    entries = cast(list[Mapping[str, Any]], plan.get("artifacts", []))
    if not entries:
        raise _reject("launch plan names no artifacts", ErrorCategory.SUPPLY_CHAIN)
    missing: list[str] = []
    for entry in entries:
        artifact = _artifact_from(entry)
        try:
            store.verify(artifact)
        except MinekinError:
            missing.append(artifact.coordinate)
    if missing:
        raise _reject(
            f"{len(missing)} of {len(entries)} artifacts are not in the store yet, "
            f"starting with {missing[0]}; fetch them before starting a session",
            ErrorCategory.SUPPLY_CHAIN,
        )


def start_session(
    *,
    root: Path,
    profile: Path,
    java_executable: Path,
    session_id: str,
    generation: int,
    kin_selector: str | None = None,
    supervisor_factory: SupervisorFactory = default_supervisor_factory,
    forward_environment: Mapping[str, str] | None = None,
) -> SessionLaunch:
    """Read the identity, prove readiness, then create the overlay and start."""

    kin_id = select_kin(root, kin_selector)
    database = database_for(root, kin_id)
    connection = connect_reader(database)
    try:
        identity = read_identity_root(connection)
    finally:
        connection.close()

    runs = run_root(root, kin_id)
    plan = build_launch_plan(profile)
    require_launchable(plan)
    require_store_complete(plan, ArtifactStore(runs / "artifact-store"))

    overlays = SessionOverlayStore(runs / "session")
    overlay = overlays.create(session_id, generation)
    if overlay != session_overlay_path(runs, session_id, generation):
        # The supervisor's log directory was named from this path already.
        raise _reject("the session overlay was created somewhere unexpected")

    supervisor = supervisor_factory(overlay / "logs")
    spec = build_process_spec(
        plan,
        run_root=runs,
        material=identity.material,
        candidate=OFFLINE_SESSION_CANDIDATES[0],
        java_executable=java_executable,
        forward_environment=forward_environment,
    )
    process = supervisor.start(spec)
    return SessionLaunch(
        session_id=session_id,
        generation=generation,
        kin_id=str(identity.kin_id),
        overlay=str(overlay),
        identity=process,
        argv_digest=process.argv_digest,
    )
