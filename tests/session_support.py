"""Helpers shared by the session-level tests.

Kept as plain functions rather than fixtures so a test can call them with
different arguments, and so a failure points at the call rather than at fixture
setup.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.artifacts import (
    ArtifactStore,
    store_relative_path,
)
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.offline_session import (
    EMPTY_ARGV,
    OFFLINE_SESSION_CANDIDATES,
)
from minekin_core.adapters.launcher.supervisor import ProcessSupervisor
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli import session as session_module
from minekin_core.cli.init import initialise_identity
from minekin_core.domain.ids import KinId
from minekin_core.domain.offline_identity import OfflineIdentityMaterial
from minekin_core.generated.minekin.v1 import observation_pb2, session_pb2

PROFILE = (
    Path(__file__).resolve().parent / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"
)
KIN_ID = KinId("kin-01")
PAYLOAD = b"client jar bytes\n"
STUB_PID = 4242


def fabricated() -> tuple[dict[str, Any], Artifact]:
    """A minimal but structurally real launch plan, so the ready path can be walked.

    The reviewed bundle cannot be used for this: its Bridge is not built and no
    artifact has been fetched, so every start would refuse before reaching the
    behaviour under test.
    """

    artifact = Artifact(
        coordinate="example:client:1.21.4",
        path="versions/1.21.4/client.jar",
        url="https://example.invalid/client.jar",
        size=len(PAYLOAD),
        sha1=hashlib.sha1(PAYLOAD).hexdigest(),
        kind="client",
    )
    store_path = store_relative_path(artifact)
    plan: dict[str, Any] = {
        "launchable": True,
        "blockers": [],
        "bundle": {"main_class": "example.Main", "minecraft": "1.21.4"},
        "runtime": {
            "jvm_args": ["-cp", store_path, "-Djava.library.path=session/natives"],
            "classpath": [store_path],
            "natives_dir": "session/natives",
            "game_dir": "session/",
            "assets_dir": "bundle/assets",
            "assets_index_name": "19",
            "version_type": "release",
            # All four options the Launcher encodes, not just the two that name
            # the player: the recorded session material is read back out of the
            # resolved argv, and a fixture that carries only half of it would
            # test a launch shape that cannot happen.
            "game_arg_template": [
                entry
                for pair in (
                    ("--username", "auth_player_name"),
                    ("--uuid", "auth_uuid"),
                    ("--clientId", "clientid"),
                    ("--xuid", "auth_xuid"),
                )
                for entry in (
                    {"kind": "literal", "value": pair[0]},
                    {"kind": "placeholder", "name": pair[1]},
                )
            ],
        },
        "artifacts": [asdict(artifact)],
    }
    # Computed the way `build_launch_plan` computes it, so a fabricated plan is
    # structurally the same thing the Bridge session material is derived from.
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    plan["plan_sha256"] = hashlib.sha256(canonical).hexdigest()
    plan["bridge_source_sha256"] = "d" * 64
    return plan, artifact


def stand_in_for_the_built_workspace(monkeypatch: Any) -> None:
    """Stand in for the two steps that need a real build behind them.

    A fabricated plan has no Bridge build and no mod jars to place. Those steps
    have their own tests; if they ran in every session test, those tests would
    depend on whether this checkout happens to have been built.
    """

    def built_bridge(_root: Path) -> Path:
        return Path("/dev/null")

    def mods(*_args: object, **_kwargs: object) -> tuple[Path, ...]:
        return ()

    def natives(*_args: object, **_kwargs: object) -> tuple[Path, ...]:
        return ()

    def assets(*_args: object, **_kwargs: object) -> tuple[Path, ...]:
        return ()

    monkeypatch.setattr(session_module, "require_built_bridge", built_bridge)
    monkeypatch.setattr(session_module, "install_fixed_mods", mods)
    monkeypatch.setattr(session_module, "materialise_natives", natives)
    monkeypatch.setattr(session_module, "materialise_assets", assets)


def fake_plan(_profile: Path, *, workspace_root: Path | None = None) -> dict[str, Any]:
    """Stand in for the reviewed profile, whose bundle is not launchable yet."""

    return fabricated()[0]


class StubProcess:
    """A process object that is already finished, so nothing has to be waited on."""

    pid = STUB_PID

    def poll(self) -> int:
        return 0


def stub_supervisor(log_directory: Path) -> ProcessSupervisor:
    def spawn(*args: object, **kwargs: object) -> object:
        return StubProcess()

    return ProcessSupervisor(clock=FakeClock(), spawn=cast(Any, spawn), log_directory=log_directory)


def refusing_supervisor(log_directory: Path) -> ProcessSupervisor:
    """A supervisor whose spawn fails, for the failure paths."""

    def spawn(*args: object, **kwargs: object) -> object:
        raise OSError("no such file")

    return ProcessSupervisor(clock=FakeClock(), spawn=cast(Any, spawn), log_directory=log_directory)


def kin_root(tmp_path: Path) -> Path:
    """The data root with one Kin, created once however many times this is called."""

    if not (tmp_path / "kin" / "kin-01" / "kin.sqlite3").exists():
        initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())
    return tmp_path


def run_root(tmp_path: Path) -> Path:
    return tmp_path / "kin" / "kin-01" / "run"


def ready_data_root(tmp_path: Path, monkeypatch: Any) -> Path:
    """The data root for a Kin whose store is complete, so a start can get past readiness.

    Returns the data root, which is what `start_session(root=...)` takes; the run
    root is a different thing and a different call.
    """

    root = kin_root(tmp_path)
    _, artifact = fabricated()
    monkeypatch.setattr(session_module, "build_launch_plan", fake_plan)
    stand_in_for_the_built_workspace(monkeypatch)
    ArtifactStore(run_root(tmp_path) / "artifact-store").install(artifact, io.BytesIO(PAYLOAD))
    return root


def first_snapshot(
    *,
    generation: int,
    material: OfflineIdentityMaterial,
    game_tick: int = 1,
    authoritative: bool = True,
) -> observation_pb2.InitialObservation:
    """A first snapshot Core should admit for a fabricated launch.

    Every value comes from the same sources the launch itself used — the identity
    the data root was created with, and the one reviewed candidate the plan
    selects — rather than from anything the code under test produced, because a
    helper that copied what it was checking would agree with anything.
    """

    candidate = OFFLINE_SESSION_CANDIDATES[0]
    return observation_pb2.InitialObservation(
        generation=generation,
        game_tick=game_tick,
        authoritative=authoritative,
        self=observation_pb2.SelfState(
            health=20.0,
            max_health=20.0,
            food=20,
            saturation=5.0,
            on_ground=True,
            alive=True,
            current_screen="GameMenuScreen",
        ),
        inventory=observation_pb2.InventorySummary(revision=1),
        session_identity=session_pb2.SessionIdentityReport(
            identity_candidate_id=candidate.candidate_id,
            session_username=material.username,
            session_uuid=material.uuid_canonical,
            session_account_type="LEGACY",
            session_client_id_present=candidate.client_id_argv != EMPTY_ARGV,
            session_xuid_present=candidate.xuid_argv != EMPTY_ARGV,
            credential_values_exposed=False,
        ),
    )
