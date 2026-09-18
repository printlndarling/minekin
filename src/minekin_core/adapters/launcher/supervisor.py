"""Starting, watching and stopping the managed client process.

The client is spawned directly, never through a shell, with the argv the plan
produced and the environment the spec named. Stopping is bounded: the process is
asked to exit, then killed if it does not, because a client that outlives its run
still holds the session overlay and still looks like a player to a server.

The wait for a process to die uses the operating system's clock, not the clock
port. The port exists to make domain deadlines testable, and a `FakeClock` that
never advances would turn this into an unbounded loop.

Reconciling a process left behind by a previous run is deliberately not here.
Deciding whether a surviving PID is ours to adopt, terminate or escalate needs a
controlled runner to test against, and guessing would be worse than a gap.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from minekin_core.adapters.launcher.process import ClientProcessSpec, argument_digest
from minekin_core.application.ports.clock import Clock
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

DEFAULT_STOP_TIMEOUT_S = 20.0
_POLL_INTERVAL_S = 0.05

Spawner = Callable[..., "subprocess.Popen[bytes]"]


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.process",
        "supervise",
        ErrorCategory.PROCESS,
        Retryability.OPERATOR_ACTION,
        message,
    )


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    """Who the run believes it started, which is more than a PID.

    A PID alone is reused by the operating system, so it cannot identify a
    process across runs on its own.
    """

    pid: int
    started_at: str
    argv_digest: str

    def as_document(self) -> dict[str, object]:
        return {
            "pid": self.pid,
            "started_at": self.started_at,
            "argv_digest": self.argv_digest,
        }


@dataclass(frozen=True, slots=True)
class ProcessOutcome:
    identity: ProcessIdentity
    exit_code: int


def parse_process_identity(document: dict[str, object]) -> ProcessIdentity:
    """Read back a recorded identity, refusing one that is not shaped as recorded."""

    pid = document.get("pid")
    started_at = document.get("started_at")
    digest = document.get("argv_digest")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
        raise _reject("recorded process identity has no usable pid")
    if not isinstance(started_at, str) or not started_at:
        raise _reject("recorded process identity has no start time")
    if not isinstance(digest, str) or len(digest) != 64:
        raise _reject("recorded process identity has no argument digest")
    return ProcessIdentity(pid=pid, started_at=started_at, argv_digest=digest)


class ProcessSupervisor:
    """One managed client process at a time."""

    def __init__(
        self,
        *,
        clock: Clock,
        spawn: Spawner = subprocess.Popen,
        log_directory: Path | None = None,
    ) -> None:
        self._clock = clock
        self._spawn = spawn
        self._log_directory = log_directory
        self._process: subprocess.Popen[bytes] | None = None
        self._identity: ProcessIdentity | None = None
        self._handles: list[IO[bytes]] = []

    def start(self, spec: ClientProcessSpec) -> ProcessIdentity:
        """Spawn the client, or raise without leaving a half-started run."""

        if self._process is not None:
            raise _reject("a client process is already managed by this supervisor")

        # The environment points at session directories; a process handed a
        # TMPDIR that is not there warns and can fail to write its own temp files.
        for directory in spec.session_directories:
            directory.mkdir(parents=True, exist_ok=True)

        argv = [str(spec.java_executable), *spec.argv]
        try:
            # `shell=False` with a list: nothing can be re-parsed by a shell.
            process = self._spawn(
                argv,
                cwd=str(spec.working_directory),
                env=dict(spec.environment),
                stdin=subprocess.DEVNULL,
                stdout=self._stream("stdout"),
                stderr=self._stream("stderr"),
                shell=False,
            )
        except OSError as error:
            self._close_handles()
            raise _reject(
                f"the client process could not be started: {type(error).__name__}"
            ) from error

        self._identity = ProcessIdentity(
            pid=int(process.pid),
            started_at=self._clock.utc_now().isoformat(),
            argv_digest=argument_digest(tuple(argv)),
        )
        self._process = process
        return self._identity

    def _stream(self, name: str) -> IO[bytes] | int:
        if self._log_directory is None:
            return subprocess.DEVNULL
        self._log_directory.mkdir(parents=True, exist_ok=True)
        handle = (self._log_directory / f"{name}.log").open("wb")
        self._handles.append(handle)
        return handle

    @property
    def identity(self) -> ProcessIdentity | None:
        return self._identity

    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def poll(self) -> int | None:
        """The exit code once the process has finished, otherwise None."""

        if self._process is None:
            return None
        return self._process.poll()

    def stop(self, *, timeout_s: float = DEFAULT_STOP_TIMEOUT_S) -> ProcessOutcome:
        """Ask the client to exit, then insist. Returns the recorded identity."""

        if self._process is None or self._identity is None:
            raise _reject("no client process is managed by this supervisor")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")

        process = self._process
        if process.poll() is None:
            process.terminate()
            deadline = time.monotonic() + timeout_s
            while process.poll() is None and time.monotonic() < deadline:
                time.sleep(_POLL_INTERVAL_S)
            if process.poll() is None:
                # Still alive after being asked: it still holds the session, so
                # it does not get to keep running.
                process.kill()
                process.wait()

        code = process.poll()
        self._close_handles()
        self._process = None
        return ProcessOutcome(identity=self._identity, exit_code=0 if code is None else int(code))

    def _close_handles(self) -> None:
        for handle in self._handles:
            handle.close()
        self._handles = []
