"""What a restart must preserve, and what it must not carry over.

Restart is where persistence bugs live: the same Kin must come back, and nothing
transient may come back with them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.orphans import MARKER_NAME, Liveness, session_claims
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.identity_store import read_identity_root
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.session import database_for, session_overlay_path, start_session
from minekin_core.cli.status import read_status
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.ids import KinId
from session_support import (  # type: ignore[import-not-found]
    PROFILE,
    kin_root,
    ready_data_root,
    refusing_supervisor,
    run_root,
    stub_supervisor,
)

KIN_ID = KinId("kin-01")


def gone(_pid: int) -> Liveness:
    """The previous client finished, which is the ordinary restart case."""

    return Liveness.GONE


def started(tmp_path: Path, session_id: str, **overrides: object):
    arguments: dict[str, object] = {
        "root": tmp_path,
        "profile": PROFILE,
        "java_executable": Path("/usr/bin/java"),
        "session_id": session_id,
        "generation": 1,
        "supervisor_factory": stub_supervisor,
        "probe": gone,
    }
    arguments.update(overrides)
    return start_session(**arguments)  # type: ignore[arg-type]


def identity_document(tmp_path: Path) -> dict[str, object]:
    connection = connect_reader(database_for(tmp_path, KIN_ID))
    try:
        return read_identity_root(connection).material.as_document()
    finally:
        connection.close()


def ledger_rows(tmp_path: Path) -> list[dict[str, object]]:
    import sqlite3

    connection = sqlite3.connect(database_for(tmp_path, KIN_ID))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT event_type, run_id, session_id, sequence FROM event ORDER BY position"
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def test_a_restart_is_the_same_kin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ready_data_root(tmp_path, monkeypatch)
    first = started(tmp_path, "session-01")
    before = identity_document(tmp_path)

    second = started(tmp_path, "session-02")

    assert first.kin_id == second.kin_id == "kin-01"
    assert identity_document(tmp_path) == before
    assert before["identity_revision"] == 1
    assert before["credential_kind"] == "offline-sentinel"


def test_a_restart_is_a_new_session_with_a_new_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready_data_root(tmp_path, monkeypatch)
    first = started(tmp_path, "session-01")

    second = started(tmp_path, "session-02")

    assert first.session_id != second.session_id
    assert first.overlay != second.overlay
    # The earlier session is left where it was rather than reused or removed.
    assert Path(first.overlay).is_dir()
    assert Path(second.overlay).is_dir()
    assert Path(second.overlay) == session_overlay_path(run_root(tmp_path), "session-02", 1)


def test_a_restart_is_a_new_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each Core invocation is its own run, and a run's sequence starts at one."""

    ready_data_root(tmp_path, monkeypatch)
    first = started(tmp_path, "session-01")

    second = started(tmp_path, "session-02")

    assert first.run_id != second.run_id
    rows = ledger_rows(tmp_path)
    assert [row["event_type"] for row in rows] == [
        "AuthPolicyFrozen",
        "SessionProcessStarted",
        "AuthPolicyFrozen",
        "SessionProcessStarted",
    ]
    assert [row["run_id"] for row in rows] == [
        first.run_id,
        first.run_id,
        second.run_id,
        second.run_id,
    ]
    assert [row["sequence"] for row in rows] == ["1", "2", "1", "2"]


def test_each_restart_reads_a_fresh_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ready_data_root(tmp_path, monkeypatch)
    started(tmp_path, "session-01")

    started(tmp_path, "session-02")

    claims = session_claims(run_root(tmp_path), probe=gone)
    assert sorted(claim.session_id for claim in claims) == ["session-01", "session-02"]
    for session_id in ("session-01", "session-02"):
        overlay = session_overlay_path(run_root(tmp_path), session_id, 1)
        document = json.loads((overlay / MARKER_NAME).read_bytes())
        assert document["session_id"] == session_id


def test_a_failed_start_does_not_block_the_next_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure leaves no marker, so a retry is not treated as a double start."""

    ready_data_root(tmp_path, monkeypatch)

    with pytest.raises(MinekinError, match="could not be started"):
        started(tmp_path, "session-01", supervisor_factory=refusing_supervisor)

    assert session_claims(run_root(tmp_path)) == ()

    retried = started(tmp_path, "session-02")

    assert retried.session_id == "session-02"


def test_a_failed_start_leaves_its_own_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failed attempt is appended, not erased: the ledger keeps both runs."""

    ready_data_root(tmp_path, monkeypatch)

    with pytest.raises(MinekinError):
        started(tmp_path, "session-01", supervisor_factory=refusing_supervisor)
    started(tmp_path, "session-02")

    assert [row["event_type"] for row in ledger_rows(tmp_path)] == [
        "AuthPolicyFrozen",
        "SessionProcessFailed",
        "AuthPolicyFrozen",
        "SessionProcessStarted",
    ]


def test_a_restart_re_validates_the_identity_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is cached across runs: a corrupted Kin cannot be resumed silently."""

    ready_data_root(tmp_path, monkeypatch)
    started(tmp_path, "session-01")
    import sqlite3

    writer = sqlite3.connect(database_for(tmp_path, KIN_ID), isolation_level=None)
    try:
        writer.execute("UPDATE kin_identity SET uuid_algorithm = 'unknown-rule'")
    finally:
        writer.close()

    with pytest.raises(MinekinError, match="unknown offline UUID algorithm"):
        started(tmp_path, "session-02")


def test_a_restart_re_checks_readiness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Readiness is not remembered from the previous run either."""

    import os
    import stat

    ready_data_root(tmp_path, monkeypatch)
    started(tmp_path, "session-01")
    for path in (run_root(tmp_path) / "artifact-store" / "blobs").rglob("*.jar"):
        # The store seals what it publishes read-only, so a test that removes an
        # artifact has to unseal it first.
        os.chmod(path, stat.S_IWRITE)
        path.unlink()

    with pytest.raises(MinekinError, match="not in the store yet"):
        started(tmp_path, "session-02")


def test_status_reports_every_recorded_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready_data_root(tmp_path, monkeypatch)
    started(tmp_path, "session-01")
    started(tmp_path, "session-02")

    report = read_status(tmp_path, probe=gone)

    assert [client.session_id for client in report.clients] == ["session-01", "session-02"]
    assert report.ledger.events_recorded == 4
    assert report.ledger.last_event_type == "SessionProcessStarted"


def test_a_restart_on_a_host_that_cannot_ask_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The counterpart to the tests above: an unanswerable client blocks a restart.

    Which platforms can answer is covered where the probe lives; here it is
    injected so the rule is exercised regardless of the host.
    """

    def cannot_say(_pid: int) -> Liveness:
        return Liveness.UNKNOWN

    ready_data_root(tmp_path, monkeypatch)
    started(tmp_path, "session-01")

    with pytest.raises(MinekinError, match="confirm it is gone"):
        started(tmp_path, "session-02", probe=cannot_say)


def test_restarting_needs_no_fresh_initialisation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`init` is not part of a restart, and running it again is refused."""

    from minekin_core.cli.init import initialise_identity

    ready_data_root(tmp_path, monkeypatch)
    started(tmp_path, "session-01")

    with pytest.raises(MinekinError, match="already exists"):
        initialise_identity(KIN_ID, root=tmp_path, username="Kin", clock=FakeClock())

    assert kin_root(tmp_path) == tmp_path
    assert ArtifactStore(run_root(tmp_path) / "artifact-store").root.is_dir()
