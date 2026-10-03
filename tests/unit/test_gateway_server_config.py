from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from gateway import server_config
from gateway.identity import CSRF_HEADER
from gateway.server import GatewayServer, ReadRequestHandler, ReadService
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.server_probe import load_profile_for_probe
from minekin_core.domain.version_probe import ProbeObservation, ProbeOutcome


def read(root: Path) -> dict[str, object]:
    return server_config.server_read(root, clock=FakeClock(), csrf_token="test-token")


def save(root: Path, *, revision: int = 0, host: str = "127.0.0.1", port: int = 25566) -> int:
    return server_config.save_from_request(
        root, body={"revision": revision, "fields": {"host": host, "port": port}}
    )[0]


def test_absent_read_does_not_create_settings_or_probe_a_target(tmp_path: Path) -> None:
    assert read(tmp_path)["fields"] is None
    assert read(tmp_path)["revision"] == 0
    assert list(tmp_path.iterdir()) == []


def test_save_survives_a_new_service_read_and_stale_edits_preserve_settings(tmp_path: Path) -> None:
    assert save(tmp_path) == 200
    assert read(tmp_path)["fields"] == {"host": "127.0.0.1", "port": 25566}
    assert save(tmp_path, port=25567) == 409
    assert read(tmp_path)["fields"] == {"host": "127.0.0.1", "port": 25566}
    assert save(tmp_path, revision=1, port=25567) == 200
    assert read(tmp_path)["revision"] == 2


def test_competing_writers_with_the_same_revision_have_one_winner(tmp_path: Path) -> None:
    def write(port: int) -> int:
        return save(tmp_path, port=port)

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(write, (25566, 25567)))
    assert sorted(outcomes) == [200, 409]
    assert read(tmp_path)["revision"] == 1


@pytest.mark.parametrize("path", [server_config.SERVER_SAVE_PATH, server_config.SERVER_PROBE_PATH])
def test_http_writes_require_csrf_and_never_mutate_on_refusal(tmp_path: Path, path: str) -> None:
    service = ReadService(root=tmp_path, kin_selector=None, clock=FakeClock())
    ReadRequestHandler.service = service
    server = GatewayServer(("127.0.0.1", 0), ReadRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    body = (
        {"revision": 0, "fields": {"host": "127.0.0.1", "port": 25566}}
        if path == server_config.SERVER_SAVE_PATH
        else {"revision": 0, "confirm": True, "allowRemote": False}
    )
    try:
        for token, expected in [
            ("wrong", 401),
            (service.csrf_token, 200 if "save" in path else 409),
        ]:
            request = urllib.request.Request(
                base + path,
                data=json.dumps(body).encode(),
                method="POST",
                headers={"Content-Type": "application/json", "Origin": base, CSRF_HEADER: token},
            )
            try:
                with urllib.request.urlopen(request, timeout=3) as response:
                    status = response.status
            except urllib.error.HTTPError as error:
                status = error.code
                error.close()
            assert status == expected
            if token == "wrong":
                assert list(tmp_path.iterdir()) == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize(
    "host,port",
    [
        ("localhost", 25565),
        ("http://127.0.0.1", 25565),
        ("0.0.0.0", 25565),
        ("169.254.169.254", 80),
        ("::ffff:127.0.0.1", 25565),
        ("127.0.0.1", True),
        ("127.0.0.1", 0),
        ("127.0.0.1", 65536),
    ],
)
def test_invalid_endpoint_is_rejected_before_storage(tmp_path: Path, host: str, port: int) -> None:
    assert save(tmp_path, host=host, port=port) == 400
    assert list(tmp_path.iterdir()) == []


def test_remote_probe_requires_explicit_consent_and_current_revision(tmp_path: Path) -> None:
    assert save(tmp_path, host="192.0.2.1") == 200
    assert (
        server_config.probe_from_request(
            tmp_path, body={"revision": 1, "confirm": True, "allowRemote": False}
        )[0]
        == 403
    )
    assert (
        server_config.probe_from_request(
            tmp_path, body={"revision": 0, "confirm": True, "allowRemote": True}
        )[0]
        == 409
    )
    assert not (tmp_path / "server-profiles").exists()


@pytest.mark.parametrize(
    "protocol,version,resolved", [(763, "1.20.1", True), (12345, "99.0", False)]
)
def test_probe_uses_frozen_endpoint_and_resolves_actual_protocol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    protocol: int,
    version: str,
    resolved: bool,
) -> None:
    assert save(tmp_path) == 200
    paths: list[Path] = []

    def probe(path: Path, *, timeout_s: float) -> ProbeObservation:
        paths.append(path)
        profile = load_profile_for_probe(path)
        assert profile.host == "127.0.0.1" and profile.port == 25566
        assert timeout_s == 5
        assert save(tmp_path, revision=1, port=25567) == 200
        assert load_profile_for_probe(path).revision == profile.revision
        return ProbeObservation(
            outcome=ProbeOutcome.OBSERVED,
            profile_id=profile.profile_id,
            profile_revision=profile.revision,
            endpoint=profile.endpoint(),
            resolution_chain=(profile.host,),
            protocol=protocol,
            version_text=version,
        )

    monkeypatch.setattr(server_config, "run_probe", probe)
    monkeypatch.setattr(server_config, "host_os_arch", lambda: "linux-x86_64")
    status, result = server_config.probe_from_request(
        tmp_path, body={"revision": 1, "confirm": True, "allowRemote": False}
    )
    assert status == 200
    assert result["revision"] == 1
    assert result["fields"]["port"] == 25566
    assert result["protocol"] == protocol
    assert (result["supportStatus"] == "RESOLVED") is resolved
    assert (result["bundleId"] is not None) is resolved
    assert read(tmp_path)["revision"] == 2
    assert len(paths) == 1


def test_corrupt_storage_is_named_without_claiming_a_configured_server(tmp_path: Path) -> None:
    (tmp_path / "dashboard-settings.sqlite3").write_bytes(b"broken sqlite")
    result = read(tmp_path)
    assert result["fields"] is None
    assert result["loadError"] is not None
