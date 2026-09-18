"""Helpers shared by the session-level tests.

Kept as plain functions rather than fixtures so a test can call them with
different arguments, and so a failure points at the call rather than at fixture
setup.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.metadata import Artifact
from minekin_core.adapters.launcher.supervisor import ProcessSupervisor
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli import session as session_module
from minekin_core.cli.init import initialise_identity
from minekin_core.domain.ids import KinId

PROFILE = Path(__file__).resolve().parents[1] / "fixtures/runtime-input/bundle-p0-core-1.21.4.json"
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
    store_path = f"artifact-store/sha1/{artifact.sha1[:2]}/{artifact.sha1}/client.jar"
    plan: dict[str, Any] = {
        "launchable": True,
        "blockers": [],
        "bundle": {"main_class": "example.Main", "minecraft": "1.21.4"},
        "runtime": {
            "jvm_args": ["-cp", store_path, "-Djava.library.path=session/natives"],
            "classpath": [store_path],
            "natives_dir": "session/natives",
            "game_dir": "session/game",
            "assets_dir": "bundle/assets",
            "assets_index_name": "19",
            "version_type": "release",
            "game_arg_template": [
                entry
                for pair in (("--username", "auth_player_name"), ("--uuid", "auth_uuid"))
                for entry in (
                    {"kind": "literal", "value": pair[0]},
                    {"kind": "placeholder", "name": pair[1]},
                )
            ],
        },
        "artifacts": [asdict(artifact)],
    }
    return plan, artifact


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
    ArtifactStore(run_root(tmp_path) / "artifact-store").install(artifact, io.BytesIO(PAYLOAD))
    return root
