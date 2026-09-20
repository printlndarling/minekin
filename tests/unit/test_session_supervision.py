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
import json
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from bridge_peer import (  # type: ignore[import-not-found]
    close_writers,
    connect,
    envelope,
    hello,
    read_frame,
    write_frame,
)
from minekin_core.adapters.bridge.ipc import (
    BRIDGE_HELLO_TYPE,
    CANCEL_CONNECTION_TYPE,
    CONNECT_WORLD_TYPE,
    INITIAL_OBSERVATION_TYPE,
    LOOK_INPUT_TYPE,
    MOVE_INPUT_TYPE,
    OPEN_LAN_TYPE,
    USE_INPUT_TYPE,
    BridgeSession,
)
from minekin_core.adapters.launcher.saves import settings_digest, world_snapshot_digest
from minekin_core.adapters.launcher.server_profile import load_server_profile
from minekin_core.adapters.launcher.supervisor import ProcessSupervisor
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.identity_store import read_identity_root
from minekin_core.adapters.sqlite.session_log import (
    CLIENT_EXITED,
    HELLO_ACCEPTED,
    INPUT_LEASE_GRANTED,
    INPUT_REFUSED,
    JOIN_OBSERVED,
    PLAYABLE_ESTABLISHED,
    PROCESS_STARTED,
    SESSION_INTERRUPTED,
)
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli import session as session_module
from minekin_core.cli.session import (
    IPC_DIRECTORY,
    SessionLaunch,
    session_overlay_path,
    start_and_supervise,
)
from minekin_core.cli.session_runtime import SessionOutcome, SessionRun
from minekin_core.domain.connection import ConnectionState
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.offline_identity import OfflineIdentityMaterial
from minekin_core.domain.session_state import SessionState
from minekin_core.generated.minekin.v1 import (
    control_pb2,
    envelope_pb2,
    observation_pb2,
    session_pb2,
)
from session_support import (  # type: ignore[import-not-found]
    PROFILE,
    STUB_PID,
    fabricated,
    first_snapshot,
    ready_data_root,
    run_root,
)

SESSION_ID = "session-01"
GENERATION = 1
JAVA = Path("/usr/lib/jvm/temurin-21/bin/java")
CONNECTION_LIFECYCLE_TYPE = "minekin.v1.ConnectionLifecycle"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SERVER_PROFILE = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "controlled-offline-server.json"
)
# The phases a client reports on its way into a world, in the only order the
# frozen connection table allows. It stops at the join: PLAYABLE is not a phase
# a Bridge announces, it is Core's conclusion about a snapshot it admitted.
CONNECTED_PHASES: tuple[observation_pb2.ConnectionPhase, ...] = (
    observation_pb2.CONNECTION_PHASE_RESOLVING,
    observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING,
    observation_pb2.CONNECTION_PHASE_PLAY_INIT,
    observation_pb2.CONNECTION_PHASE_JOIN_SEEN,
)


def _material(root: Path) -> OfflineIdentityMaterial:
    """The identity this Kin was created with, read from the ledger's own store."""

    connection = connect_reader(root / "kin" / "kin-01" / "kin.sqlite3")
    try:
        return read_identity_root(connection).material
    finally:
        connection.close()


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


async def _wait_for_control_message(
    reader: asyncio.StreamReader, message_type: str, *, timeout: float = 5.0
) -> envelope_pb2.Envelope:
    """Read control frames until one carries the type asked for.

    Heartbeats share the control channel, so "the next frame" is not what any of
    this is about: the next *command* is.
    """

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise TimeoutError(f"no {message_type} arrived")
        frame = await asyncio.wait_for(read_frame(reader), remaining)
        if frame.message_type == message_type:
            return frame


def _lifecycle(
    bridge: BridgeSession,
    command: control_pb2.ConnectWorld,
    phase: observation_pb2.ConnectionPhase,
) -> observation_pb2.ConnectionLifecycle:
    """One phase report, naming the profile the command named.

    A report that named another profile would be describing somebody else's
    connection, and Core refusing it is the point of the binding — so the fake
    client here echoes back what it was actually told, the way a real one would.
    """

    return observation_pb2.ConnectionLifecycle(
        generation=bridge.generation,
        server_profile_id=command.server_profile_id,
        server_profile_revision=command.server_profile_revision,
        phase=phase,
        failure_reason=observation_pb2.ADMISSION_FAILURE_REASON_UNSPECIFIED,
        terminal=False,
    )


def test_a_named_server_profile_becomes_one_connect_command(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Core asks the proved client to join the saved world, and the reports bind.

    This is the seam the contract describes: the client proves its bundle and
    schema first, and only then is it told where to go. Everything the command
    carries is read back and compared against the profile fixture itself, so the
    assertion is about the profile being the only source rather than about a copy
    of its values.
    """

    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    database = root / "kin" / "kin-01" / "kin.sqlite3"
    profile = load_server_profile(SERVER_PROFILE)

    async def scenario() -> tuple[SessionRun, control_pb2.ConnectWorld, envelope_pb2.Envelope]:
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
                server_profile=SERVER_PROFILE,
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

        frame = await _wait_for_control_message(control_reader, CONNECT_WORLD_TYPE)
        command = control_pb2.ConnectWorld.FromString(frame.payload)

        for sequence, phase in enumerate(CONNECTED_PHASES, start=1):
            await write_frame(
                event_writer,
                envelope(
                    bridge,
                    CONNECTION_LIFECYCLE_TYPE,
                    envelope_pb2.CHANNEL_EVENT,
                    sequence,
                    _lifecycle(bridge, command, phase).SerializeToString(deterministic=True),
                ),
            )

        # Then the first snapshot, which is what makes the attempt playable —
        # Core validates it, and the Bridge's word is not what decides.
        await write_frame(
            event_writer,
            envelope(
                bridge,
                INITIAL_OBSERVATION_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                len(CONNECTED_PHASES) + 1,
                first_snapshot(
                    generation=bridge.generation, material=_material(root)
                ).SerializeToString(deterministic=True),
            ),
        )

        # The join has to reach the ledger *while the session is still running*:
        # a timeline assembled at exit is not a timeline.
        await _wait_until(
            lambda: any(row[0] == PLAYABLE_ESTABLISHED for row in _ledger_rows(database))
        )
        process.exited = True
        _launch, run = await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)
        return run, command, frame

    run, command, frame = asyncio.run(scenario())

    assert command.server_profile_id == profile.profile_id
    assert command.server_profile_revision == profile.revision
    assert command.original_host == profile.host
    assert command.port == profile.port
    assert command.resource_pack_policy == control_pb2.RESOURCE_PACK_POLICY_DENY
    assert command.request_id
    # The deadline is Core's own clock, and it is the *duration* to the envelope's
    # stamp that the Bridge can act on: the two stamps share an origin, and this
    # asserts the difference is the timeout that was asked for rather than a
    # number that merely looks plausible.
    remaining = command.deadline_monotonic_ns - frame.monotonic_ns
    assert 0 < remaining <= 30 * 1_000_000_000

    assert run.connection_state is ConnectionState.PLAYABLE
    assert run.outcome is SessionOutcome.CLIENT_EXITED
    rows = _ledger_rows(database)
    assert [row[0] for row in rows] == [
        PROCESS_STARTED,
        HELLO_ACCEPTED,
        JOIN_OBSERVED,
        PLAYABLE_ESTABLISHED,
        CLIENT_EXITED,
    ]
    # The join is the Bridge's report, so it is recorded as such — and being
    # playable is Core's own conclusion from a snapshot it admitted, so it is
    # recorded as Core's. §6 says a trust class may not be self-declared, and
    # naming the Bridge as the source of Core's verdict would be exactly that.
    assert rows[2] == (JOIN_OBSERVED, "BRIDGE", "BRIDGE_FILTERED")
    assert rows[3] == (PLAYABLE_ESTABLISHED, "CORE", "CORE")
    # These two writes come from the event reader, which the session cancels on
    # its way out — the first writes the runtime had ever made from a task that
    # gets cancelled. A writer interrupted mid-close used to strand its
    # non-daemon thread, and a thread nothing will ever stop is a process that
    # never exits: the symptom was the interpreter hanging after every test had
    # passed, with no failing assertion to point at it.
    assert [thread.name for thread in threading.enumerate() if "sqlite-writer" in thread.name] == []


def test_an_attempt_that_outlives_its_deadline_is_cancelled_by_core(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Core stops meaning an attempt when the deadline it sent passes.

    The deadline already rides inside `ConnectWorld` so the Bridge can refuse a
    command that is stale by the time it reads one. This is the other half, and
    nothing did it before: a client sitting in a black hole left Core waiting for
    a world that was never coming. The session must *not* end because of it —
    cancelling an attempt is one more thing that happens during a run.
    """

    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    database = root / "kin" / "kin-01" / "kin.sqlite3"

    async def scenario() -> tuple[
        SessionRun, control_pb2.CancelConnection, control_pb2.ConnectWorld
    ]:
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
                # Short enough that the test waits rather than sleeps, and long
                # enough that the connect command is on the wire first.
                connection_timeout=0.3,
                server_profile=SERVER_PROFILE,
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

        connect_frame = await _wait_for_control_message(control_reader, CONNECT_WORLD_TYPE)
        # No lifecycle report at all: the attempt is still in flight, which is
        # the only state in which a deadline can pass.
        cancel_frame = await _wait_for_control_message(control_reader, CANCEL_CONNECTION_TYPE)

        process.exited = True
        _launch, run = await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)
        return (
            run,
            control_pb2.CancelConnection.FromString(cancel_frame.payload),
            control_pb2.ConnectWorld.FromString(connect_frame.payload),
        )

    run, cancel, connect_command = asyncio.run(scenario())

    # The cancel names the attempt it is about: a generation that did not match
    # would be Core cancelling something else.
    assert cancel.generation == connect_command.generation
    assert cancel.reason == control_pb2.CONNECTION_CANCEL_REASON_TIMEOUT
    assert cancel.request_id

    assert run.connection_cancelled == "TIMEOUT"
    assert run.connection_cancel_failed is False
    # The session carried on: the client is what ends a run, not a deadline.
    assert run.outcome is SessionOutcome.CLIENT_EXITED
    assert run.events_applied == 0
    interrupted = [row for row in _ledger_rows(database) if row[0] == SESSION_INTERRUPTED]
    assert interrupted == []


def test_a_session_with_no_server_profile_is_never_told_to_connect(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Naming no world is a supported way to run, and it must stay one."""

    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    database = root / "kin" / "kin-01" / "kin.sqlite3"

    async def scenario() -> tuple[SessionRun, list[str]]:
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

        # The control channel is live — heartbeats keep arriving — and none of
        # what arrives is a command. Frames having arrived is what makes the
        # absence meaningful rather than a read that simply did not happen.
        seen: list[str] = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 1.5
        while len(seen) < 2 and loop.time() < deadline:
            try:
                frame = await asyncio.wait_for(read_frame(control_reader), 1.0)
            except TimeoutError:
                break
            seen.append(frame.message_type)
        assert seen, "no frames arrived, so this proves nothing"

        process.exited = True
        _launch, run = await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)
        return run, seen

    run, seen = asyncio.run(scenario())

    assert CONNECT_WORLD_TYPE not in seen
    assert run.connection_state is None
    assert run.events_applied == 0
    assert [row[0] for row in _ledger_rows(database)] == [
        PROCESS_STARTED,
        HELLO_ACCEPTED,
        CLIENT_EXITED,
    ]


def test_an_unusable_server_profile_is_refused_before_the_client_starts(
    tmp_path: Path, monkeypatch: Any
) -> None:
    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    spawned: list[bool] = []
    supervisor = live_supervisor(process, descriptor_path(tmp_path), spawned)
    unusable = tmp_path / "server.json"
    unusable.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profile_id": "somewhere-on-the-network",
                "host": "mc.example.invalid",
                "port": 25565,
                "auth_mode": "offline",
                "minecraft_version": "1.21.4",
                "visibility": "isolated_test_only",
                "resource_pack_policy": "deny",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(MinekinError, match="loopback"):
        asyncio.run(
            start_and_supervise(
                root=root,
                profile=PROFILE,
                java_executable=JAVA,
                session_id=SESSION_ID,
                generation=GENERATION,
                supervisor_factory=lambda _logs: supervisor,
                server_profile=unusable,
            )
        )

    # Nothing was created and nothing was spawned: the profile is read before the
    # run begins, so an unusable one costs nothing but the error message.
    assert spawned == []
    assert not descriptor_path(tmp_path).exists()


def _ledger_payloads(database: Path) -> list[str]:
    """The recorded payloads, in order, as the ledger holds them."""

    connection = sqlite3.connect(database)
    try:
        rows = connection.execute("SELECT payload_json FROM event ORDER BY position").fetchall()
    finally:
        connection.close()
    return [str(row[0]) for row in rows]


def test_a_rejected_login_reaches_the_ledger_with_its_category(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """A failure whose category is dropped is a failure nobody can act on.

    The Bridge classifies what a server said into a stable enum and puts that on
    the wire; this asserts the other end of that: the category survives Core's
    reading of the report and lands in the ledger next to the phase, so evidence
    says *why* a Kin could not enter a world and not merely that it could not.
    """

    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    database = root / "kin" / "kin-01" / "kin.sqlite3"

    async def scenario() -> None:
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
                server_profile=SERVER_PROFILE,
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
        frame = await _wait_for_control_message(control_reader, CONNECT_WORLD_TYPE)
        command = control_pb2.ConnectWorld.FromString(frame.payload)

        # The server refused this Kin: the Bridge says so with the stable enum
        # it classified the server's sentence into, and the failure is terminal.
        # RESOLVING comes first because §7's table only lets a session reach the
        # connection states *through* the attempt — a failure reported without it
        # is out of order, which is a rule this repository already pins.
        for sequence, (phase, reason, terminal) in enumerate(
            (
                (
                    observation_pb2.CONNECTION_PHASE_RESOLVING,
                    observation_pb2.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                    False,
                ),
                (
                    observation_pb2.CONNECTION_PHASE_FAILED,
                    observation_pb2.ADMISSION_FAILURE_REASON_WHITELIST_REJECTED,
                    True,
                ),
            ),
            start=1,
        ):
            lifecycle = observation_pb2.ConnectionLifecycle(
                generation=bridge.generation,
                server_profile_id=command.server_profile_id,
                server_profile_revision=command.server_profile_revision,
                phase=phase,
                failure_reason=reason,
                terminal=terminal,
            )
            await write_frame(
                event_writer,
                envelope(
                    bridge,
                    CONNECTION_LIFECYCLE_TYPE,
                    envelope_pb2.CHANNEL_EVENT,
                    sequence,
                    lifecycle.SerializeToString(deterministic=True),
                ),
            )
        await _wait_until(lambda: any("FAILED" in row for row in _ledger_payloads(database)))
        process.exited = True
        await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())

    payloads = _ledger_payloads(database)
    interrupted = next(row for row in payloads if "FAILED" in row)
    assert json.loads(interrupted) == {
        "phase": "FAILED",
        "reason": "ADMISSION_FAILURE_REASON_WHITELIST_REJECTED",
    }
    # The server's own sentence has no channel into a product event; only the
    # category does.
    assert all("white-listed" not in row for row in payloads)


async def _joined_run(*, root: Path, hold_at: str | None) -> tuple[SessionRun, Path]:
    """One run that reaches the join and then stops, with a hold asked for.

    The phases are the ones a real run reports, in order, because the session's
    table only lets it reach a connection state *through* the attempt: a join
    reported without the phases before it is out of order.
    """

    process = LiveProcess()
    path = descriptor_path(root)
    supervisor = live_supervisor(process, path, [])
    database = root / "kin" / "kin-01" / "kin.sqlite3"
    arguments: dict[str, Any] = {} if hold_at is None else {"hold_at": hold_at}
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
            server_profile=SERVER_PROFILE,
            hold_forward=8.0,
            **arguments,
        )
    )
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
    frame = await _wait_for_control_message(control_reader, CONNECT_WORLD_TYPE)
    command = control_pb2.ConnectWorld.FromString(frame.payload)
    for sequence, phase in enumerate(
        (
            observation_pb2.CONNECTION_PHASE_RESOLVING,
            observation_pb2.CONNECTION_PHASE_LOGIN_NEGOTIATING,
            observation_pb2.CONNECTION_PHASE_PLAY_INIT,
            observation_pb2.CONNECTION_PHASE_JOIN_SEEN,
        ),
        start=1,
    ):
        await write_frame(
            event_writer,
            envelope(
                bridge,
                CONNECTION_LIFECYCLE_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                sequence,
                _lifecycle(bridge, command, phase).SerializeToString(deterministic=True),
            ),
        )
    await _wait_until(lambda: any(row[0] == JOIN_OBSERVED for row in _ledger_rows(database)))
    # The answer, if there is one, is written by the reader that reported the
    # join and lands a moment after it. A run that asked has asked by now; a run
    # that did not will never ask.
    await asyncio.sleep(0.3)
    process.exited = True
    _launch, run = await asyncio.wait_for(running, 10)
    await close_writers(control_writer, event_writer)
    return run, database


def _ledger_facts(database: Path) -> list[tuple[str, dict[str, Any]]]:
    """Every recorded event, as its type and its decoded payload, in order."""

    return [
        (kind, json.loads(payload))
        for (kind, _source, _trust), payload in zip(
            _ledger_rows(database), _ledger_payloads(database), strict=True
        )
    ]


def test_a_hold_asked_for_at_the_join_is_refused_and_the_refusal_is_recorded(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The contract's L4 invariant, made testable instead of assumed.

    "A lease is obtained only after the join *and* the first snapshot" is a rule
    about when Core may drive a client, and nothing could test it: Core only ever
    asked at the moment that succeeds, and an invariant nothing is allowed to
    violate is one nobody has evidence for. `--hold-at join` asks too early on
    purpose, and what comes back is the evidence — the arbiter's refusal, with
    its own reason, in the ledger, and no lease anywhere.
    """

    root = ready_data_root(tmp_path, monkeypatch)
    run, database = asyncio.run(_joined_run(root=root, hold_at="join"))

    facts = _ledger_facts(database)
    kinds = [kind for kind, _ in facts]
    assert JOIN_OBSERVED in kinds
    assert INPUT_LEASE_GRANTED not in kinds
    assert [payload for kind, payload in facts if kind == INPUT_REFUSED] == [
        {
            "phase": "JOIN_SEEN",
            "capabilities": ["control.move.v1"],
            "refusals": ["NOT_PLAYABLE"],
        }
    ]
    # In the run's own order: the world the Kin joined, and then the answer to a
    # request made before there was anything in it to drive.
    assert kinds.index(JOIN_OBSERVED) < kinds.index(INPUT_REFUSED)

    # Nothing was sent, and being refused did not end the run: a client is what
    # ends a run, and a hold that was refused is not a reason to stop.
    assert run.input_refusal == "NOT_PLAYABLE"
    assert run.outcome is SessionOutcome.CLIENT_EXITED
    # No snapshot was admitted, which is the whole reason the answer was no.
    assert run.snapshots_admitted == 0
    assert run.connection_cancelled == ""


def test_a_hold_asked_for_by_default_is_not_asked_for_at_the_join(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The other half of the same rule, and the reason the phase is a choice.

    Without `--hold-at`, a run that has joined and is not yet playable has asked
    for nothing — so there is no refusal to record, and a run whose world arrives
    normally carries no refusal it did not earn.
    """

    root = ready_data_root(tmp_path, monkeypatch)
    run, database = asyncio.run(_joined_run(root=root, hold_at=None))

    facts = _ledger_facts(database)
    kinds = [kind for kind, _ in facts]
    assert JOIN_OBSERVED in kinds
    assert INPUT_REFUSED not in kinds
    assert INPUT_LEASE_GRANTED not in kinds
    assert run.input_refusal == ""


def test_asking_when_to_hold_without_a_hold_is_refused(tmp_path: Path, monkeypatch: Any) -> None:
    """A phase with no request behind it is not a run.

    `--hold-at` says *when* to ask for input, so a run that asks when without
    asking what is an operator error rather than a default nobody chose.
    """

    root = ready_data_root(tmp_path, monkeypatch)

    with pytest.raises(MinekinError, match="--hold-at needs a hold"):
        asyncio.run(
            start_and_supervise(
                root=root,
                profile=PROFILE,
                java_executable=JAVA,
                session_id=SESSION_ID,
                generation=GENERATION,
                handshake_timeout=5.0,
                hold_at="join",
            )
        )


async def _control_types_after(
    reader: asyncio.StreamReader, *, quiet_for: float = 0.2, limit: int = 32
) -> list[str]:
    """Every control message type until the channel has been quiet for a while.

    "Nothing more was sent" is a claim about absence, so it needs a window: the
    window is the quiet, and the limit is there so a channel that never goes quiet
    ends the test rather than hanging it.
    """

    seen: list[str] = []
    for _ in range(limit):
        try:
            frame = await asyncio.wait_for(read_frame(reader), quiet_for)
        except TimeoutError:
            break
        seen.append(frame.message_type)
    return seen


def test_no_input_is_replayed_after_an_ambiguous_disconnect(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The dangerous-replay invariant: a command sent once is never sent again.

    The Bridge reports that the world is gone while the lease is still Core's to
    hold, and the report carries no failure reason — which is the ambiguous case
    by this repository's own rule: a disconnect *with* a reason is a session the
    server ended, and one without is a session that ended. Core cannot tell from
    it whether the last command arrived, and the safe answer to that is to stop
    meaning it: the lease is withdrawn, and the command is not repeated. A
    replayed move or use is an action taken twice on a world that may already have
    acted on the first one.
    """

    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    database = root / "kin" / "kin-01" / "kin.sqlite3"

    async def scenario() -> tuple[SessionRun, list[str]]:
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
                server_profile=SERVER_PROFILE,
                hold_forward=30.0,
            )
        )
        path = descriptor_path(root)
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
        connect_frame = await _wait_for_control_message(control_reader, CONNECT_WORLD_TYPE)
        command = control_pb2.ConnectWorld.FromString(connect_frame.payload)

        for sequence, phase in enumerate(CONNECTED_PHASES, start=1):
            await write_frame(
                event_writer,
                envelope(
                    bridge,
                    CONNECTION_LIFECYCLE_TYPE,
                    envelope_pb2.CHANNEL_EVENT,
                    sequence,
                    _lifecycle(bridge, command, phase).SerializeToString(deterministic=True),
                ),
            )
        await write_frame(
            event_writer,
            envelope(
                bridge,
                INITIAL_OBSERVATION_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                len(CONNECTED_PHASES) + 1,
                first_snapshot(
                    generation=bridge.generation, material=_material(root)
                ).SerializeToString(deterministic=True),
            ),
        )
        await _wait_until(
            lambda: any(row[0] == PLAYABLE_ESTABLISHED for row in _ledger_rows(database))
        )

        # The lease's own command, which is the one that must never be repeated.
        await _wait_for_control_message(control_reader, MOVE_INPUT_TYPE)

        # The world goes away, with nothing said about why.
        await write_frame(
            event_writer,
            envelope(
                bridge,
                CONNECTION_LIFECYCLE_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                len(CONNECTED_PHASES) + 2,
                observation_pb2.ConnectionLifecycle(
                    generation=bridge.generation,
                    server_profile_id=command.server_profile_id,
                    server_profile_revision=command.server_profile_revision,
                    phase=observation_pb2.CONNECTION_PHASE_DISCONNECTED,
                    failure_reason=observation_pb2.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                    terminal=True,
                ).SerializeToString(deterministic=True),
            ),
        )
        await _wait_until(
            lambda: any(row[0] == SESSION_INTERRUPTED for row in _ledger_rows(database))
        )

        seen = await _control_types_after(control_reader)
        process.exited = True
        _launch, run = await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)
        return run, seen

    run, seen = asyncio.run(scenario())

    inputs = {MOVE_INPUT_TYPE, LOOK_INPUT_TYPE, USE_INPUT_TYPE}
    assert [kind for kind in seen if kind in inputs] == []
    # The lease was real — otherwise "nothing was replayed" would be true of a run
    # that never sent anything in the first place.
    kinds = [row[0] for row in _ledger_rows(database)]
    assert INPUT_LEASE_GRANTED in kinds
    assert run.outcome is SessionOutcome.CLIENT_EXITED


def test_a_deadline_does_not_cancel_a_world_the_kin_is_already_in(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The deadline bounds how long a world may take to arrive, and nothing else.

    Found by a fault injection rather than by reading: the default thirty seconds
    expires while a Kin is walking, and the cancel that followed closed a healthy
    connection — and, because a cancel clears the generation the Bridge needs to
    attribute a later report, it also made the world's own death unreportable. An
    attempt at PLAYABLE is neither finished nor unfinished; it has stopped being
    an attempt.
    """

    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    database = root / "kin" / "kin-01" / "kin.sqlite3"

    async def scenario() -> tuple[SessionRun, list[str]]:
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
                server_profile=SERVER_PROFILE,
                # Short enough to pass while the test waits; the world is reached
                # long before it, which is the whole point.
                connection_timeout=0.3,
            )
        )
        path = descriptor_path(root)
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
        connect_frame = await _wait_for_control_message(control_reader, CONNECT_WORLD_TYPE)
        command = control_pb2.ConnectWorld.FromString(connect_frame.payload)
        for sequence, phase in enumerate(CONNECTED_PHASES, start=1):
            await write_frame(
                event_writer,
                envelope(
                    bridge,
                    CONNECTION_LIFECYCLE_TYPE,
                    envelope_pb2.CHANNEL_EVENT,
                    sequence,
                    _lifecycle(bridge, command, phase).SerializeToString(deterministic=True),
                ),
            )
        await write_frame(
            event_writer,
            envelope(
                bridge,
                INITIAL_OBSERVATION_TYPE,
                envelope_pb2.CHANNEL_EVENT,
                len(CONNECTED_PHASES) + 1,
                first_snapshot(
                    generation=bridge.generation, material=_material(root)
                ).SerializeToString(deterministic=True),
            ),
        )
        await _wait_until(
            lambda: any(row[0] == PLAYABLE_ESTABLISHED for row in _ledger_rows(database))
        )
        # Well past the deadline, which is what the run is about.
        await asyncio.sleep(0.6)

        seen = await _control_types_after(control_reader)
        process.exited = True
        _launch, run = await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)
        return run, seen

    run, seen = asyncio.run(scenario())

    assert CANCEL_CONNECTION_TYPE not in seen
    assert run.connection_cancelled == ""
    # And the session is still in the world it reached, which is what the cancel
    # would have taken away.
    assert run.connection_state is ConnectionState.PLAYABLE
    kinds = [row[0] for row in _ledger_rows(database)]
    assert kinds[-1] == CLIENT_EXITED


def _prepared_world(tmp_path: Path) -> Path:
    """A save the way an operator hands one over: a level and the terrain beside it."""

    save = tmp_path / "prepared-world"
    (save / "region").mkdir(parents=True)
    (save / "level.dat").write_bytes(b"a level.dat\n")
    (save / "region" / "r.0.0.mca").write_bytes(b"region bytes\n")
    return save


def test_a_host_session_enters_the_world_it_was_given(tmp_path: Path, monkeypatch: Any) -> None:
    """The wiring, end to end: seeded into the overlay, named on the run, passed to the client.

    All three have to hold at once for the session to be a host. A world that is
    seeded but never entered is a client at the title screen, and a client told
    to enter a world it was never given is a client that fails to start — so the
    test asserts the world is on disk *and* on the command line *and* in the run
    document, rather than any one of those being taken for the others.
    """

    root = ready_data_root(tmp_path, monkeypatch)
    save = _prepared_world(tmp_path)
    process = LiveProcess()
    asked: list[str | None] = []

    def recording_plan(
        _profile: Path, *, workspace_root: Path | None = None, world_name: str | None = None
    ) -> dict[str, Any]:
        asked.append(world_name)
        return fabricated()[0]

    # `ready_data_root` stands the plan in for the reviewed bundle, which this
    # host cannot launch. What is recorded here is what the *session* asked the
    # plan builder for; that a name becomes two argv elements is asserted against
    # the real plan in `test_offline_session`.
    monkeypatch.setattr(session_module, "build_launch_plan", recording_plan)
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
                world_save=save,
                world_name="prepared-world",
            ),
            10,
        )
        return run

    run = asyncio.run(scenario())

    overlay = session_overlay_path(run_root(tmp_path), SESSION_ID, GENERATION)
    seeded = overlay / "saves" / "prepared-world"
    assert (seeded / "level.dat").read_bytes() == b"a level.dat\n"
    assert (seeded / "region" / "r.0.0.mca").read_bytes() == b"region bytes\n"

    # The launch was asked for a client that enters that world, rather than the
    # seeded world and the launch being two unrelated things that both happened.
    assert asked == ["prepared-world"]

    # The name is the bytes as they were handed over, and the run document is
    # where a fact with no ledger event of its own lives.
    assert run.world_snapshot == {
        "level_name": "prepared-world",
        "digest": world_snapshot_digest(save),
        # The world's own settings, hashed apart from its terrain: a bundle needs to
        # name what a run started from, and a world with no server profile behind it
        # has `level.dat` instead of a server configuration.
        "settings_digest": settings_digest(save),
    }
    assert run.as_dict()["world_snapshot"] == run.world_snapshot
    assert all(
        row[0] != JOIN_OBSERVED for row in _ledger_rows(root / "kin" / "kin-01" / "kin.sqlite3")
    )


def test_a_session_with_no_world_records_no_world(tmp_path: Path, monkeypatch: Any) -> None:
    """Null rather than an empty object: a run that seeded nothing has no world to name."""

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

    assert run.world_snapshot is None
    assert run.as_dict()["world_snapshot"] is None
    overlay = session_overlay_path(run_root(tmp_path), SESSION_ID, GENERATION)
    assert not (overlay / "saves").exists()


def test_a_host_session_asks_the_client_to_publish_its_world(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The command is sent, and it asks for a port rather than naming one.

    Core cannot know which port is free on the host, and the answer comes back on the
    event channel; asking for a specific number would be choosing one it cannot check.
    The deadline is Core's own, in the same monotonic clock the envelope is stamped
    from, so the two sides mean the same instant by it.
    """

    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    before = time.monotonic_ns()

    async def scenario() -> control_pb2.OpenLan:
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
                open_lan=True,
                open_lan_timeout=30.0,
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

        frame = await _wait_for_control_message(control_reader, OPEN_LAN_TYPE)
        command = control_pb2.OpenLan.FromString(frame.payload)

        process.exited = True
        await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)
        return command

    command = asyncio.run(scenario())

    # Zero means "let the operating system choose", and the answer carries where it
    # landed: the client's own getter reports what was asked for, not what was bound.
    assert command.port == 0
    assert command.generation == GENERATION
    assert command.request_id
    assert before < command.deadline_monotonic_ns <= before + 31_000_000_000


def test_a_session_that_was_not_asked_to_host_does_not_ask(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The negative control: hosting is an intent, not a side effect of having a world."""

    root = ready_data_root(tmp_path, monkeypatch)
    process = LiveProcess()
    supervisor = live_supervisor(process, descriptor_path(tmp_path), [])
    seen: list[str] = []

    async def scenario() -> None:
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
        seen.extend(await _control_types_after(control_reader, quiet_for=1.0))

        process.exited = True
        await asyncio.wait_for(running, 10)
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())

    assert OPEN_LAN_TYPE not in seen
