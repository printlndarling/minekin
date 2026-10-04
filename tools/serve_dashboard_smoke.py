"""Isolated real Gateway for browser acceptance, no models or game sessions."""

from __future__ import annotations

import argparse
import os
import secrets
import tempfile
import threading
from pathlib import Path

from gateway.dashboard_assets import DashboardAssets
from gateway.server import GatewayServer, ReadRequestHandler, ReadService
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.cli.init import initialise_identity
from minekin_core.domain.ids import KinId


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--dashboard-dir", type=Path, default=Path("dashboard/dist"))
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    token = os.environ.get("MINEKIN_SMOKE_SHUTDOWN_TOKEN", "")
    if len(token) < 32:
        parser.error("test runner must supply its ephemeral shutdown token")
    # Never accept a user data root. Cleanup is limited to this newly allocated test root.
    with tempfile.TemporaryDirectory(prefix="minekin-dashboard-smoke-") as temporary:
        root = Path(temporary)
        initialise_identity(
            KinId("browser-smoke"),
            root=root,
            username="minekin",
            clock=SystemClock(),
            persona_seed="browser-smoke",
        )
        service = ReadService(root=root, kin_selector="browser-smoke", clock=SystemClock())

        class Handler(ReadRequestHandler):
            dashboard_assets = DashboardAssets(args.dashboard_dir)

            def do_POST(self) -> None:
                # Fixture-only lifecycle route. Never installed on the product handler.
                if self.path == "/__smoke_shutdown":
                    if not secrets.compare_digest(self.headers.get("X-Smoke-Token", ""), token):
                        self._respond(403, {"error": "test shutdown denied"})
                        return
                    self._respond(200, {"status": "stopping"})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                super().do_POST()

        Handler.service = service
        server = GatewayServer(("127.0.0.1", args.port), Handler)
        try:
            server.serve_forever()
        finally:
            server.server_close()
            service.jobs.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
