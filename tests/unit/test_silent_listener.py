"""The black hole: a target that accepts and never answers.

What the tool must do is small and exact — hold the connection open and say
nothing — so the tests are about exactly that, plus the two things a scenario
depends on: it announces that it is listening, and it says when something
connected. A black hole nobody dialled proves nothing about a client giving up.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPOSITORY_ROOT / "tools" / "run_silent_listener.py"
MINECRAFT_VERSION = "1.21.4"


def free_port() -> int:
    """A port nothing is listening on, asked of the operating system."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def profile_for(tmp_path: Path, port: int) -> Path:
    path = tmp_path / "black-hole.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profile_id": "p0-black-hole-loopback",
                "host": "127.0.0.1",
                "port": port,
                "auth_mode": "offline",
                "minecraft_version": MINECRAFT_VERSION,
                "visibility": "isolated_test_only",
                "resource_pack_policy": "deny",
            }
        ),
        encoding="utf-8",
    )
    return path


class Listener:
    """The tool, running, with a reader for the lines it announces itself with."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self.process = process
        self.lines: list[dict[str, object]] = []

    def wait_for(self, key: str, timeout: float = 10.0) -> dict[str, object]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.stderr is None:
                break
            line = self.process.stderr.readline()
            if not line:
                break
            try:
                document = json.loads(line)
            except json.JSONDecodeError:
                continue
            self.lines.append(document)
            if key in document:
                return document
        raise AssertionError(f"{key!r} never appeared; saw {self.lines}")


@pytest.fixture
def listener(tmp_path: Path) -> Iterator[Listener]:
    port = free_port()
    process = subprocess.Popen(
        [sys.executable, str(TOOL), "--server-profile", str(profile_for(tmp_path, port))],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    running = Listener(process)
    try:
        yield running
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_it_announces_the_address_it_took_from_the_profile(listener: Listener) -> None:
    listening = listener.wait_for("listening")

    assert str(listening["listening"]).startswith("127.0.0.1:")
    assert listening["profile"] == "p0-black-hole-loopback"


def test_a_client_that_connects_gets_nothing_back(listener: Listener) -> None:
    """The whole point: silence that stays silence, for as long as anyone waits."""

    listening = listener.wait_for("listening")
    _, _, raw_port = str(listening["listening"]).rpartition(":")

    with socket.create_connection(("127.0.0.1", int(raw_port)), timeout=5) as client:
        client.sendall(b"\x10\x00\xf8\x05\x09localhost\x00")
        # A read that returns nothing inside a bound is the observation, and the
        # bound is generous enough that a server which answered at all would be
        # caught here rather than by luck.
        client.settimeout(1.5)
        with pytest.raises(TimeoutError):
            client.recv(4096)

    accepted = listener.wait_for("accepted")

    assert accepted["held"] == 1


@pytest.mark.skipif(sys.platform == "win32", reason="a Windows terminate is not a signal")
def test_it_stops_on_a_signal_and_counts_what_it_held(listener: Listener) -> None:
    import signal

    listening = listener.wait_for("listening")
    _, _, raw_port = str(listening["listening"]).rpartition(":")
    with socket.create_connection(("127.0.0.1", int(raw_port)), timeout=5):
        listener.wait_for("accepted")
        listener.process.send_signal(signal.SIGTERM)
        stopped = listener.wait_for("stopped", timeout=5)

    assert stopped["connections"] == 1
    assert listener.process.wait(timeout=10) == 0


def test_an_address_it_cannot_take_is_refused(tmp_path: Path) -> None:
    """A black hole that could not listen would let a run pass for the wrong reason."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupant:
        occupant.bind(("127.0.0.1", 0))
        occupant.listen(1)
        port = int(occupant.getsockname()[1])

        process = subprocess.run(
            [sys.executable, str(TOOL), "--server-profile", str(profile_for(tmp_path, port))],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    assert process.returncode == 2
    assert "could not listen on" in process.stderr
