"""Serving the three frozen reads over loopback HTTP, and nothing else.

`docs/adr/0001-p0-modular-monolith.md` keeps P0 Core free of a web layer, so this is a
separate process that imports Core's reads rather than a module inside it. Being outside
the product is the point: there is no path from a request handled here to a lease, an
admission decision, or a client process, because nothing in this file is able to ask for
one.

The server owns no state and no cache. Every request re-derives its answer from the
ledger and the overlays, which is what lets a panel's `observedAt` mean the reading
rather than the moment someone last bothered to look.
"""

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse

from gateway.readmodel import (
    ALERTS_PATH,
    DEFAULT_TIMELINE_LIMIT,
    MAX_TIMELINE_LIMIT,
    ROUTES,
    SNAPSHOT_PATH,
    TIMELINE_PATH,
    alerts_payload,
    build_snapshot,
    build_timeline,
)
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.application.ports.clock import Clock
from minekin_core.cli.session import select_kin
from minekin_core.domain.errors import MinekinError

DEFAULT_PORT = 8787
#: A number the operator can raise, and a ceiling so one query cannot ask the ledger to
#: sort the whole table for a panel that shows fifty rows.
TIMELINE_PARAMETER = "limit"


class ReadService:
    """The three reads, as callables the handler can reach without knowing Core."""

    def __init__(self, *, root: Path, kin_selector: str | None, clock: Clock) -> None:
        self._root = root
        self._kin_selector = kin_selector
        self._clock = clock

    def snapshot(self) -> dict[str, Any]:
        return build_snapshot(self._root, kin_selector=self._kin_selector, clock=self._clock)

    def timeline(self, limit: int) -> list[dict[str, Any]]:
        return build_timeline(self._root, kin_selector=self._kin_selector, limit=limit)

    def alerts(self) -> dict[str, Any]:
        return alerts_payload(
            str(select_kin(self._root, self._kin_selector)), self._clock.utc_now().isoformat()
        )


class ReadRequestHandler(BaseHTTPRequestHandler):
    """GET on one of three paths, or a refusal.

    The refusal matters as much as the read: `404` is what makes the frontend's
    `contract_mismatch` branch ("Gateway 只读接口尚未实现") true rather than a guess, and
    `405` is the answer to a verb this contract does not have.
    """

    protocol_version = "HTTP/1.1"
    server_version = "MinekinGateway/1"
    service: ClassVar[ReadService]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == SNAPSHOT_PATH:
            self._respond(HTTPStatus.OK, self.service.snapshot())
            return
        if parsed.path == TIMELINE_PATH:
            limit = _timeline_limit(parse_qs(parsed.query).get(TIMELINE_PARAMETER))
            if isinstance(limit, str):
                self._respond(HTTPStatus.BAD_REQUEST, {"error": limit})
                return
            self._respond(HTTPStatus.OK, self.service.timeline(limit))
            return
        if parsed.path == ALERTS_PATH:
            self._respond(HTTPStatus.OK, self.service.alerts())
            return
        self._respond(HTTPStatus.NOT_FOUND, {"error": f"{parsed.path} is not a read model path"})

    def _refuse(self) -> None:
        self._respond(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "the read model serves GET only"})

    def do_POST(self) -> None:
        self._refuse()

    def do_PUT(self) -> None:
        self._refuse()

    def do_PATCH(self) -> None:
        self._refuse()

    def do_DELETE(self) -> None:
        self._refuse()

    def do_HEAD(self) -> None:
        # `BaseHTTPRequestHandler` would not send a body for HEAD anyway; refusing the
        # verb keeps the answer the same one the other four get.
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _respond(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        # One JSON document per line on stdout would be the audit trail of a service that
        # keeps state; this one answers a poll every few seconds, so the request log is
        # noise a reader has to scroll past to find the start-up line.
        del format, args


def _timeline_limit(raw: list[str] | None) -> int | str:
    """The requested limit, or the message that says why it was refused."""

    if raw is None or not raw:
        return DEFAULT_TIMELINE_LIMIT
    try:
        limit = int(raw[0])
    except ValueError:
        return f"{TIMELINE_PARAMETER}={raw[0]!r} is not an integer"
    if not 1 <= limit <= MAX_TIMELINE_LIMIT:
        return f"{TIMELINE_PARAMETER} must be between 1 and {MAX_TIMELINE_LIMIT}"
    return limit


class GatewayServer(ThreadingHTTPServer):
    """The loopback socket. `allow_reuse_address` so a restart does not wait a minute."""

    allow_reuse_address = True
    daemon_threads = True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gateway.server",
        description="Serve the read-only Dashboard API over loopback; it cannot change anything.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path.home() / ".minekin",
        help="the same root `minekin init` writes to (MINEKIN_HOME)",
    )
    parser.add_argument(
        "--kin",
        default=None,
        help="which Kin to report; required once the root holds more than one",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="bind address; loopback unless you mean otherwise"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--routes",
        action="store_true",
        help="print the route table with its methods and exit (the verb scan reads it)",
    )
    return parser


def print_routes() -> int:
    for path in ROUTES:
        print(f"GET {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.routes:
        return print_routes()

    clock: Clock = SystemClock()
    service = ReadService(root=args.data_root, kin_selector=args.kin, clock=clock)
    ReadRequestHandler.service = service
    try:
        # One read up front: a root that is missing or holds two Kins is an operator
        # mistake, and it is cheaper to say so before a browser starts polling.
        service.snapshot()
    except MinekinError as error:
        print(f"gateway cannot read {args.data_root}: {error.safe_message}", file=sys.stderr)
        return 1

    server = GatewayServer((args.host, args.port), ReadRequestHandler)
    print(
        f"gateway reading {args.data_root} on http://{args.host}:{server.server_port}", flush=True
    )
    for path in ROUTES:
        print(f"GET {path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
