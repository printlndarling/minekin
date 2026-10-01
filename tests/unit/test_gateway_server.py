"""The Gateway's HTTP surface: the frozen reads, the three authorized writes, and refusals.

This is the part the contract's acceptance is written against — the three reads are GET-only,
every other verb on a read path is a `405`, and the判别式 that a missing provenance field makes
the frontend fail closed rather than guess. The surface's three write holes — the identity
rename, the operator-config save, and stopping a session — are tested in their own files; here
they appear only as route-table entries, so the verb scan proves nothing else is writable.
"""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from gateway.config_write import CONFIG_PATH, CONFIG_SAVE_PATH
from gateway.identity import IDENTITY_PATH, RENAME_PATH
from gateway.readmodel import (
    ALERTS_PATH,
    MAX_TIMELINE_LIMIT,
    ROUTES,
    SCHEMA_VERSION,
    SNAPSHOT_PATH,
    TIMELINE_PATH,
)
from gateway.recipe_read import RECIPE_PATH
from gateway.server import (
    ROUTE_TABLE,
    GatewayServer,
    ReadRequestHandler,
    ReadService,
    build_parser,
    main,
)
from gateway.session_control import SESSION_PATH, SESSION_STOP_PATH
from gateway_support import joined_run
from minekin_core.application.ports.clock import FakeClock

REQUEST_TIMEOUT_SECONDS = 10

#: The statuses that answer without a value and must answer with a reason (§2.2 rules 2/3).
GAP_STATUSES = {"unknown", "unavailable", "not_wired"}


@pytest.fixture
def base_url(tmp_path: Path) -> Iterator[str]:
    joined_run(tmp_path)
    ReadRequestHandler.service = ReadService(root=tmp_path, kin_selector=None, clock=FakeClock())
    server = GatewayServer(("127.0.0.1", 0), ReadRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=REQUEST_TIMEOUT_SECONDS)


def request(url: str, *, method: str = "GET") -> tuple[int, Any]:
    """The status and the decoded body, for a failure response too."""

    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, method=method), timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        return int(error.code), json.loads(body) if body else None


def test_the_three_reads_answer_with_the_frozen_envelopes(base_url: str) -> None:
    status, snapshot = request(base_url + SNAPSHOT_PATH)

    assert status == 200
    assert snapshot["schemaVersion"] == SCHEMA_VERSION
    assert snapshot["kinId"]["status"] == "known"
    assert snapshot["kinId"]["value"] == "kin-01"
    for key in ("runtimeState", "bridgeLink", "serverLink", "session", "world", "bridgeHeartbeat"):
        assert snapshot[key]["status"] == "known", key
        assert snapshot[key]["sourceRef"], key
        assert "observedAt" in snapshot[key], key
        assert "staleAfterMs" in snapshot[key], key

    status, timeline = request(f"{base_url}{TIMELINE_PATH}?limit=3")
    assert status == 200
    rows = cast(list[dict[str, object]], timeline)
    assert len(rows) == 3
    assert {row["kind"] for row in rows} <= {
        "observation",
        "decision",
        "intent",
        "input",
        "server_feedback",
        "reflex",
        "fault",
        "session",
    }

    status, alerts = request(base_url + ALERTS_PATH)
    assert status == 200
    assert alerts["status"] == "not_wired"
    assert alerts["alerts"] == []
    assert str(alerts["reason"]).strip()


def test_the_reads_answer_the_same_way_twice(base_url: str) -> None:
    """The panels poll, so a second read is the normal case rather than an edge one."""

    first = request(base_url + SNAPSHOT_PATH)[1]
    second = request(base_url + SNAPSHOT_PATH)[1]

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_a_gap_never_reaches_a_panel_without_its_reason(base_url: str) -> None:
    """The decoder's rule 2, checked on the wire rather than in the builder.

    The control is the reason that does appear: without it the frontend fails the whole read.
    """

    document = cast(dict[str, object], request(base_url + SNAPSHOT_PATH)[1])
    signals = [
        (key, cast(dict[str, object], value))
        for key, value in document.items()
        if isinstance(value, dict)
    ]
    gap_found = [(key, signal) for key, signal in signals if signal.get("status") in GAP_STATUSES]

    assert gap_found, "this root should show at least the liveView and selfState gaps"
    for key, signal in gap_found:
        assert str(signal["reason"]).strip(), key


@pytest.mark.parametrize("verb", ["POST", "PUT", "PATCH", "DELETE", "HEAD"])
def test_a_write_verb_has_no_handler_but_a_refusal(base_url: str, verb: str) -> None:
    for path in ROUTES:
        status, _body = request(base_url + path, method=verb)
        assert status == 405, f"{verb} {path} answered {status}"


def test_a_fourth_read_is_a_404_not_a_maybe(base_url: str) -> None:
    """`404` is what makes the frontend's `contract_mismatch` branch true: a path this service
    does not have answers as one, rather than as an empty or partial document."""

    for path in (
        "/api/v1/dashboard/sessions",
        "/api/v1/dashboard/state",
        "/api/v1/dashboard/alerts/dismiss",
        "/",
        "/snapshot",
    ):
        status, body = request(base_url + path)
        assert status == 404, path
        assert str(body["error"]).startswith(path), path


def test_an_unusable_timeline_limit_is_refused_with_a_reason(base_url: str) -> None:
    for raw, needle in (
        ("abc", "not an integer"),
        ("0", "between 1 and"),
        ("9999", "between 1 and"),
    ):
        status, body = request(f"{base_url}{TIMELINE_PATH}?limit={raw}")
        assert status == 400, raw
        assert needle in str(body["error"]), raw

    status, timeline = request(f"{base_url}{TIMELINE_PATH}?limit={MAX_TIMELINE_LIMIT}")
    assert status == 200
    assert len(timeline) <= MAX_TIMELINE_LIMIT


def test_an_omitted_limit_falls_back_to_the_default_read(base_url: str) -> None:
    status, timeline = request(base_url + TIMELINE_PATH)

    assert status == 200
    assert len(timeline) == 6


def test_responses_are_json_with_a_declared_charset(base_url: str) -> None:
    with urllib.request.urlopen(
        base_url + SNAPSHOT_PATH, timeout=REQUEST_TIMEOUT_SECONDS
    ) as response:
        assert response.headers["Content-Type"] == "application/json; charset=utf-8"
        assert int(response.headers["Content-Length"]) > 0


def test_the_route_table_lists_the_reads_and_the_three_writes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The recalculation contract §5.2 asks for, widened for the two settings writes plus stop.

    The three frozen reads stay GET-only; the table gains exactly three POSTs — the identity
    rename, the operator-config save, and stopping a session — and no start/pause/resume/move
    verb creeps in under those exceptions.
    """

    assert main(["--routes"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]

    assert lines == [f"{method} {path}" for method, path in ROUTE_TABLE]
    assert [f"GET {path}" for path in ROUTES] == lines[: len(ROUTES)]
    posts = [line for line in lines if line.startswith("POST ")]
    assert posts == [
        f"POST {RENAME_PATH}",
        f"POST {CONFIG_SAVE_PATH}",
        f"POST {SESSION_STOP_PATH}",
    ]
    assert f"GET {IDENTITY_PATH}" in lines
    assert f"GET {CONFIG_PATH}" in lines
    assert f"GET {SESSION_PATH}" in lines
    assert f"GET {RECIPE_PATH}" in lines
    assert not [line for line in lines if re.search(r"\b(PUT|PATCH|DELETE)\b", line)]


def test_the_default_bind_is_loopback(tmp_path: Path) -> None:
    """No public exposure without the operator saying so in as many words."""

    parser = build_parser()

    assert parser.get_default("host") == "127.0.0.1"
    assert parser.parse_args([]).data_root == Path.home() / ".minekin"


def test_a_root_with_no_kin_refuses_at_startup_rather_than_serving_gaps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--data-root", str(tmp_path), "--host", "127.0.0.1", "--port", "0"]) == 1
    assert "cannot read" in capsys.readouterr().err
