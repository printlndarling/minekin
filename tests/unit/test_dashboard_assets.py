"""Built console and API share an origin; arbitrary files never become routes."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from gateway import dashboard_assets
from gateway.dashboard_assets import DashboardAssets
from gateway.server import GatewayServer, ReadRequestHandler, ReadService, main
from gateway_support import joined_run
from minekin_core.application.ports.clock import FakeClock


def build(root: Path) -> Path:
    folder = root / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text('<html><script src="/assets/app-123.js"></script></html>')
    (folder / "assets/app-123.js").write_text("console.log('built console');")
    (folder / "env.txt").write_text("DO_NOT_SERVE")
    (folder / "assets/app.js.map").write_text("DO_NOT_SERVE")
    return folder


@pytest.fixture
def console(tmp_path: Path) -> Iterator[str]:
    joined_run(tmp_path)
    service = ReadService(root=tmp_path, kin_selector=None, clock=FakeClock())

    class Handler(ReadRequestHandler):
        dashboard_assets = DashboardAssets(build(tmp_path))

    Handler.service = service
    server = GatewayServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        service.jobs.close()
        thread.join(timeout=5)


def test_root_redirects_to_real_same_origin_adapter_and_serves_built_bytes(console: str) -> None:
    with urllib.request.urlopen(console + "/", timeout=5) as response:
        assert response.url.endswith("/?adapter=gateway&gateway=.")
        assert response.headers["Content-Type"] == "text/html; charset=utf-8"
        assert b"/assets/app-123.js" in response.read()
    with urllib.request.urlopen(console + "/assets/app-123.js", timeout=5) as response:
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Cache-Control"] == "no-store"
        assert b"built console" in response.read()
    with urllib.request.urlopen(console + "/api/v1/dashboard/config", timeout=5) as response:
        document = json.loads(response.read())
        assert "csrfToken" in document  # Same-origin writes still use the existing guard.


@pytest.mark.parametrize(
    "path",
    [
        "/env.txt",
        "/assets/app.js.map",
        "/.git/config",
        "/assets/../env.txt",
        "/assets/%2e%2e/env.txt",
        "/api/v1/not-a-route",
        "/assets/app-123.js/extra",
    ],
)
def test_unknown_files_and_api_paths_are_not_spa_fallbacks(console: str, path: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(console + path, timeout=5)
    assert caught.value.code == 404
    assert b"DO_NOT_SERVE" not in caught.value.read()


def test_static_files_remain_get_only(console: str) -> None:
    request = urllib.request.Request(console + "/assets/app-123.js", method="POST", data=b"{}")
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request, timeout=5)
    assert caught.value.code == 405


def test_loaded_bytes_do_not_follow_later_filesystem_changes(tmp_path: Path) -> None:
    folder = build(tmp_path)
    assets = DashboardAssets(folder)
    (folder / "assets/app-123.js").write_text("DO_NOT_SERVE")
    asset = assets.get("/assets/app-123.js")
    assert asset is not None and b"DO_NOT_SERVE" not in asset.body


def test_missing_build_fails_before_runtime_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--dashboard-dir", str(tmp_path / "missing")]) == 1
    assert "cannot load dashboard build" in capsys.readouterr().err


def test_index_missing_referenced_asset_is_rejected(tmp_path: Path) -> None:
    folder = build(tmp_path)
    (folder / "assets/app-123.js").unlink()
    with pytest.raises(ValueError, match="missing build assets"):
        DashboardAssets(folder)


def test_asset_byte_budget_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = build(tmp_path)
    monkeypatch.setattr(dashboard_assets, "MAX_FILE_BYTES", 10)
    with pytest.raises(ValueError, match="budget"):
        DashboardAssets(folder)


def test_total_byte_budget_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = build(tmp_path)
    monkeypatch.setattr(dashboard_assets, "MAX_TOTAL_BYTES", 1)
    with pytest.raises(ValueError, match="budget"):
        DashboardAssets(folder)


def test_symlink_asset_rejected_when_platform_allows_creation(tmp_path: Path) -> None:
    folder = build(tmp_path)
    secret = tmp_path / "private.js"
    secret.write_text("DO_NOT_SERVE")
    asset = folder / "assets/private.js"
    try:
        asset.symlink_to(secret)
    except OSError:
        pytest.skip("platform does not permit symlink creation")
    with pytest.raises(ValueError, match="escape"):
        DashboardAssets(folder)
