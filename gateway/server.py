"""Serving the frozen reads over loopback HTTP, plus the one authorized identity write.

`docs/adr/0001-p0-modular-monolith.md` keeps P0 Core free of a web layer, so this is a
separate process that imports Core's reads rather than a module inside it. Being outside
the product is the point: there is no path from a request handled here to a lease, an
admission decision, or a client process, because nothing in this file is able to ask for
one. `docs/stable-player-name-2026-09-29.md` opens exactly one narrow exception to the
read-only Dashboard — the identity-settings rename in `gateway.identity` — and nothing
else: no start, stop, or move control.

The server owns no state and no cache. Every request re-derives its answer from the
ledger and the overlays, which is what lets a panel's `observedAt` mean the reading
rather than the moment someone last bothered to look.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar, cast
from urllib.parse import parse_qs, urlparse

from gateway.identity import (
    CSRF_HEADER,
    IDENTITY_PATH,
    MAX_RENAME_BODY_BYTES,
    RENAME_PATH,
    authorize_write,
    identity_read,
    new_csrf_token,
    refusal,
    rename_from_request,
)
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

#: The whole authorized surface, methods and all: the three frozen reads, the identity
#: read the rename form reviews, and the one rename write the identity card excepts.
#: `--routes` prints this so the verb scan sees a POST only where one is sanctioned.
ROUTE_TABLE: tuple[tuple[str, str], ...] = (
    *(("GET", path) for path in ROUTES),
    ("GET", IDENTITY_PATH),
    ("POST", RENAME_PATH),
)


class ReadService:
    """The Dashboard's reads, plus the one authorized identity write, as callables.

    The CSRF token is generated once per process and handed out only by the identity
    read; a rename must echo it back, so a page that could not read it (any origin but
    this one) cannot write either.
    """

    def __init__(self, *, root: Path, kin_selector: str | None, clock: Clock) -> None:
        self._root = root
        self._kin_selector = kin_selector
        self._clock = clock
        self.csrf_token = new_csrf_token()

    def snapshot(self) -> dict[str, Any]:
        return build_snapshot(self._root, kin_selector=self._kin_selector, clock=self._clock)

    def timeline(self, limit: int) -> list[dict[str, Any]]:
        return build_timeline(self._root, kin_selector=self._kin_selector, limit=limit)

    def alerts(self) -> dict[str, Any]:
        return alerts_payload(
            str(select_kin(self._root, self._kin_selector)), self._clock.utc_now().isoformat()
        )

    def identity(self) -> dict[str, Any]:
        return identity_read(
            self._root,
            kin_selector=self._kin_selector,
            clock=self._clock,
            csrf_token=self.csrf_token,
        )

    def rename(self, body: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        return rename_from_request(self._root, kin_selector=self._kin_selector, body=body)


class ReadRequestHandler(BaseHTTPRequestHandler):
    """GET on a read path, the one sanctioned rename POST, or a refusal.

    The refusal matters as much as the read: `404` is what makes the frontend's
    `contract_mismatch` branch ("Gateway 只读接口尚未实现") true rather than a guess, and
    `405` is the answer to a verb this surface does not have on a given path. A POST to
    anywhere but the rename route still gets that `405`, so the identity write is the
    only hole in an otherwise write-refusing surface.
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
        if parsed.path == IDENTITY_PATH:
            self._respond(HTTPStatus.OK, self.service.identity())
            return
        self._respond(HTTPStatus.NOT_FOUND, {"error": f"{parsed.path} is not a read model path"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != RENAME_PATH:
            self._refuse()
            return
        self._handle_rename()

    def _handle_rename(self) -> None:
        # Read the body first, then authorize, then parse: a request whose source or token
        # is wrong never has its JSON interpreted, and a keep-alive connection cannot be
        # left with an unread body to mis-read as the next request.
        raw, guard = self._read_body()
        if guard is not None:
            self._respond(*guard)
            return
        denial = authorize_write(
            origin=self.headers.get("Origin"),
            host=self.headers.get("Host"),
            content_type=self.headers.get("Content-Type"),
            supplied_token=self.headers.get(CSRF_HEADER),
            csrf_token=self.service.csrf_token,
        )
        if denial is not None:
            self._respond(*denial)
            return
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._respond(*refusal(400, "invalid_request", "the rename body is not valid JSON"))
            return
        if not isinstance(document, dict):
            self._respond(*refusal(400, "invalid_request", "the rename body must be a JSON object"))
            return
        # A decoded JSON object always has string keys; the `dict` check above is the runtime proof.
        self._respond(*self.service.rename(cast("dict[str, Any]", document)))

    def _read_body(self) -> tuple[bytes, tuple[int, dict[str, Any]] | None]:
        """The rename body, or the refusal that stopped before reading it."""

        declared = self.headers.get("Content-Length")
        if not declared or not declared.isdigit():
            return b"", refusal(400, "invalid_request", "a rename must declare a Content-Length")
        size = int(declared)
        if size > MAX_RENAME_BODY_BYTES:
            self.close_connection = True
            return b"", refusal(413, "invalid_request", "the rename body is too large")
        return self.rfile.read(size), None

    def _refuse(self) -> None:
        self._respond(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "the read model serves GET only"})

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

    def _respond(self, status: int, payload: Any) -> None:
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
        description=(
            "Serve the read-only Dashboard API over loopback, plus the one identity "
            "rename the stable-player-name card authorizes; it cannot start, stop or move."
        ),
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
    for method, path in ROUTE_TABLE:
        print(f"{method} {path}")
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
    for method, path in ROUTE_TABLE:
        print(f"{method} {path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
