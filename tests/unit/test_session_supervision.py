"""`session start` with a live Bridge: the wiring, not the pieces.

The runtime, the classifier, the session table and the descriptor all have their
own tests. This one starts a session the way the CLI does and checks the things
only the wiring can get wrong: that the descriptor exists *before* the client
is spawned, that it lands in the session's own directory, that it carries the
digests of the plan this launch came from, and that the command stays with the
session until the client leaves instead of returning the moment it spawns.

The client here is a loopback peer that reads the descriptor the way the real
Bridge does — from the file, with no shared state.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from bridge_peer import (  # type: ignore[import-not-found]
    close_writers,
    connect,
    envelope,
    hello,
    read_frame,
    write_frame,
)
from minekin_core.adapters.bridge.ipc import BRIDGE_HELLO_TYPE, BridgeSession
from minekin_core.adapters.launcher.supervisor import ProcessSupervisor
from minekin_core.adapters.sqlite.session_log import (
    CLIENT_EXITED,
    HELLO_ACCEPTED,
    PROCESS_STARTED,
    SESSION_INTERRUPTED,
)
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.session import (
    IPC_DIRECTORY,
    SessionLaunch,
    session_overlay_path,
    start_and_supervise,
)
from minekin_core.cli.session_runtime import SessionOutcome, SessionRun
from minekin_core.domain.session_state import SessionState
from minekin_core.generated.minekin.v1 import envelope_pb2, session_pb2
from session_support import (  # type: ignore[import-not-found]
    PROFILE,
    STUB_PID,
    fabricated,
    ready_data_root,
    run_root,
)

SESSION_ID = "session-01"
GENERATION = 1
JAVA = Path("/usr/lib/jvm/temurin-21/bin/java")


async def _wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise TimeoutError("the condition never held")
        await asyncio.sleep(0.005)


class LiveProcess:
    """A client that stays alive until the test retires it."""

    pid = STUB_PID

    def __init__(self) -> None:
        self.exited = False

    def poll(self) -> int | None:
        return 0 if self.exited else None


def descriptor_path(tmp_path: Path) -> Path:
    overlay = session_overlay_path(run_root(tmp_path), SESSION_ID, GENERATION)
    return overlay / IPC_DIRECTORY / "bridge-bootstrap.pb"


def live_supervisor(process: LiveProcess, descriptor: Path, seen: list[bool]) -> ProcessSupervisor:
    """A supervisor that records whether the descriptor existed when it spawned.

    That is the whole ordering claim: a client spawned before the descriptor is
    written starts, looks for it, and refuses to come up.
    """

    def spawn(*args: object, **kwargs: object) -> object:
        seen.append(descriptor.is_file())
        return process

    return ProcessSupervisor(clock=FakeClock(), spawn=cast(Any, spawn), log_directory=None)


def test_session_start_hosts_the_bridge_and_stays_until_the_client_leaves(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    path = descriptor_path(tmp_path)
    spawned_with_descriptor: list[bool] = []
    supervisor = live_supervisor(process, path, spawned_with_descriptor)
    reviewed = fabricated()[0]

    async def scenario() -> tuple[SessionLaunch, SessionRun, session_pb2.BridgeBootstrapDescriptor]:
        running = asyncio.create_task(
            start_and_supervise(
                root=root,
                profile=PROFILE,
                java_executable=JAVA,
                session_id=SESSION_ID,
                generation=GENERATION,
                supervisor_factory=lambda _logs: supervisor,
                handshake_timeout=5.0,
                exit_poll_s=0.01,
            )
        )

        # The client can only find its descriptor if it was written before the
        # spawn, which is the ordering this test exists to pin.
        await _wait_until(path.is_file)
        descriptor = session_pb2.BridgeBootstrapDescriptor.FromString(path.read_bytes())

        bridge = BridgeSession(
            kin_id=descriptor.kin_id,
            session_id=descriptor.session_id,
            generation=descriptor.generation,
            client_instance_id=descriptor.client_instance_id,
            bundle_digest=descriptor.bundle_digest,
            bridge_digest=descriptor.bridge_digest,
            launch_nonce=descriptor.launch_nonce,
            session_key=descriptor.session_key,
        )
        control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        await write_frame(
            control_writer,
            envelope(
                bridge,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                hello(bridge).SerializeToString(deterministic=True),
            ),
        )
        core_hello = await asyncio.wait_for(read_frame(control_reader), 5)
        assert core_hello.message_type == "minekin.v1.CoreHello"

        process.exited = True
        launch, run = await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)
        return launch, run, descriptor

    launch, run, descriptor = asyncio.run(scenario())

    assert run.outcome is SessionOutcome.CLIENT_EXITED
    assert run.session_state is SessionState.STOPPED
    assert launch.identity.pid == STUB_PID
    assert launch.session_id == SESSION_ID
    assert launch.overlay == str(path.parent.parent)
    assert spawned_with_descriptor == [True]

    assert descriptor.kin_id == "kin-01"
    assert descriptor.session_id == SESSION_ID
    assert descriptor.generation == GENERATION
    # The plan is what binds Core and the client; a descriptor that named any
    # other bundle would be proving a launch that never happened.
    assert descriptor.bundle_digest == reviewed["plan_sha256"]
    assert descriptor.bridge_digest == reviewed["bridge_source_sha256"]
    assert len(descriptor.launch_nonce) == 32


def _ledger_rows(database: Path) -> list[tuple[str, str, str]]:
    """Event type, source and trust class in the order the ledger holds them."""

    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            "SELECT event_type, source, trust_class FROM event ORDER BY position"
        ).fetchall()
    finally:
        connection.close()
    return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]


def test_session_start_records_what_the_run_observed(tmp_path: Path, monkeypatch: Any) -> None:
    """§7: the service that decides a transition is the one that persists it."""

    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    database = root / "kin" / "kin-01" / "kin.sqlite3"

    async def scenario() -> SessionRun:
        running = asyncio.create_task(
            start_and_supervise(
                root=root,
                profile=PROFILE,
                java_executable=JAVA,
                session_id=SESSION_ID,
                generation=GENERATION,
                supervisor_factory=lambda _logs: supervisor,
                handshake_timeout=5.0,
                exit_poll_s=0.01,
            )
        )
        path = descriptor_path(tmp_path)
        await _wait_until(path.is_file)
        descriptor = session_pb2.BridgeBootstrapDescriptor.FromString(path.read_bytes())
        bridge = BridgeSession(
            kin_id=descriptor.kin_id,
            session_id=descriptor.session_id,
            generation=descriptor.generation,
            client_instance_id=descriptor.client_instance_id,
            bundle_digest=descriptor.bundle_digest,
            bridge_digest=descriptor.bridge_digest,
            launch_nonce=descriptor.launch_nonce,
            session_key=descriptor.session_key,
        )
        control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        await write_frame(
            control_writer,
            envelope(
                bridge,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                hello(bridge).SerializeToString(deterministic=True),
            ),
        )
        await asyncio.wait_for(read_frame(control_reader), 5)

        # The handshake fact is written while the session is still running, not
        # reconstructed at the end: a timeline that only appears on exit is not
        # a timeline.
        await _wait_until(lambda: any(row[0] == HELLO_ACCEPTED for row in _ledger_rows(database)))
        process.exited = True
        _launch, run = await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)
        return run

    run = asyncio.run(scenario())

    assert run.outcome is SessionOutcome.CLIENT_EXITED
    assert _ledger_rows(database) == [
        (PROCESS_STARTED, "LAUNCHER", "LAUNCHER"),
        # Core verified the proof, so acceptance is Core's own conclusion.
        (HELLO_ACCEPTED, "CORE", "CORE"),
        (CLIENT_EXITED, "CORE", "CORE"),
    ]


def test_a_handshake_that_never_completes_is_recorded_as_an_interruption(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    database = root / "kin" / "kin-01" / "kin.sqlite3"

    async def scenario() -> SessionRun:
        _launch, run = await asyncio.wait_for(
            start_and_supervise(
                root=root,
                profile=PROFILE,
                java_executable=JAVA,
                session_id=SESSION_ID,
                generation=GENERATION,
                supervisor_factory=lambda _logs: supervisor,
                handshake_timeout=0.2,
                exit_poll_s=0.01,
            ),
            10,
        )
        return run

    run = asyncio.run(scenario())

    assert run.outcome is SessionOutcome.HANDSHAKE_TIMEOUT
    rows = _ledger_rows(database)
    assert [row[0] for row in rows] == [PROCESS_STARTED, SESSION_INTERRUPTED]
    # No hello was ever accepted, so none may be claimed.
    assert all(row[0] != HELLO_ACCEPTED for row in rows)


def test_a_client_that_never_proves_itself_ends_the_session(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])

    async def scenario() -> SessionRun:
        _launch, run = await asyncio.wait_for(
            start_and_supervise(
                root=root,
                profile=PROFILE,
                java_executable=JAVA,
                session_id=SESSION_ID,
                generation=GENERATION,
                supervisor_factory=lambda _logs: supervisor,
                handshake_timeout=0.2,
                exit_poll_s=0.01,
            ),
            10,
        )
        return run

    run = asyncio.run(scenario())

    assert run.outcome is SessionOutcome.HANDSHAKE_TIMEOUT
    assert run.session_state is SessionState.STOPPED
    # The client is still there; the session is not, which is what lets the
    # operator decide whether to stop it or look at its logs.
    assert process.exited is False
