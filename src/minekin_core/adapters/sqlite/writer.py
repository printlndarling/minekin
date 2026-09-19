"""A bounded asyncio-to-SQLite writer-thread bridge."""

from __future__ import annotations

import asyncio
import queue
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, cast

from .connection import connect_writer

T = TypeVar("T")


class WriterQueueFull(RuntimeError):
    """The bounded persistence queue rejected a critical write."""


class WriterClosed(RuntimeError):
    """A write was submitted after shutdown began."""


class WriteDeadlineExceeded(TimeoutError):
    """A queued write did not begin before its monotonic deadline."""


@dataclass(slots=True)
class _Request[T]:
    operation: Callable[[sqlite3.Connection], T]
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[T]
    deadline_ns: int | None
    transactional: bool


_STOP = object()


class SQLiteWriter:
    """Own the only write connection and execute requests on one thread.

    ``submit`` never blocks the event-loop thread.  It either returns an
    ``asyncio.Future`` immediately or raises ``WriterQueueFull`` immediately.
    Completion is always delivered with ``loop.call_soon_threadsafe``.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        queue_capacity: int = 128,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        if queue_capacity <= 0:
            raise ValueError("queue_capacity must be positive")
        self.path = Path(path)
        self._busy_timeout_ms = busy_timeout_ms
        self._requests: queue.Queue[_Request[object] | object] = queue.Queue(queue_capacity)
        self._state_lock = threading.Lock()
        self._closed = False
        self._ready = threading.Event()
        self._initialization_error: BaseException | None = None
        self._thread_ident: int | None = None
        self._thread = threading.Thread(
            target=self._run,
            name=f"minekin-sqlite-writer-{self.path.name}",
            daemon=False,
        )
        self._thread.start()

    @property
    def thread_ident(self) -> int | None:
        return self._thread_ident

    @property
    def queue_capacity(self) -> int:
        return self._requests.maxsize

    async def start(self) -> None:
        await asyncio.to_thread(self._ready.wait)
        if self._initialization_error is not None:
            raise self._initialization_error

    def submit(
        self,
        operation: Callable[[sqlite3.Connection], T],
        *,
        deadline_ns: int | None = None,
        transactional: bool = True,
    ) -> asyncio.Future[T]:
        """Enqueue a request and return its loop-bound completion future."""

        loop = asyncio.get_running_loop()
        future: asyncio.Future[T] = loop.create_future()
        request = _Request(operation, loop, future, deadline_ns, transactional)
        with self._state_lock:
            if self._closed:
                raise WriterClosed("SQLite writer is closed")
            try:
                self._requests.put_nowait(cast("_Request[object]", request))
            except queue.Full as error:
                raise WriterQueueFull(
                    f"SQLite writer queue reached capacity {self.queue_capacity}"
                ) from error
        return future

    async def execute(
        self,
        operation: Callable[[sqlite3.Connection], T],
        *,
        deadline_ns: int | None = None,
        transactional: bool = True,
    ) -> T:
        return await self.submit(operation, deadline_ns=deadline_ns, transactional=transactional)

    async def checkpoint(self, mode: str = "PASSIVE") -> tuple[int, int, int]:
        normalized = mode.upper()
        if normalized not in {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}:
            raise ValueError("invalid WAL checkpoint mode")

        def run(connection: sqlite3.Connection) -> tuple[int, int, int]:
            row = connection.execute(f"PRAGMA wal_checkpoint({normalized})").fetchone()
            return int(row[0]), int(row[1]), int(row[2])

        return await self.execute(run, transactional=False)

    async def aclose(self) -> None:
        """Stop the thread, queueing the stop signal before anything can suspend.

        The signal is a synchronous `put_nowait` rather than an awaited one on
        purpose. A caller that is already unwinding from a cancellation never
        reaches its next `await` — the `CancelledError` is re-thrown at that point
        without running what is being awaited — so an awaited stop would simply
        not happen, and the thread would stay parked on an empty queue for the
        life of the process. A non-daemon thread that nothing will ever stop is
        an interpreter that never exits, and that is not a theoretical failure:
        it is what a ledger write cancelled as the session was torn down did.

        The join can still be abandoned by a cancellation, and that is fine: the
        thread it is waiting for has already been told to stop.
        """

        with self._state_lock:
            if not self._closed:
                self._closed = True
                try:
                    self._requests.put_nowait(_STOP)
                except queue.Full as error:
                    raise WriterQueueFull(
                        "SQLite writer queue is full, so it cannot be stopped"
                    ) from error
        await asyncio.to_thread(self._thread.join)

    async def __aenter__(self) -> SQLiteWriter:
        await self.start()
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    def _run(self) -> None:
        self._thread_ident = threading.get_ident()
        connection: sqlite3.Connection | None = None
        try:
            connection = connect_writer(self.path, busy_timeout_ms=self._busy_timeout_ms)
        except BaseException as error:
            self._initialization_error = error
        finally:
            self._ready.set()

        try:
            while True:
                queued = self._requests.get()
                if queued is _STOP:
                    self._requests.task_done()
                    break
                request = cast("_Request[object]", queued)
                try:
                    if self._initialization_error is not None:
                        raise self._initialization_error
                    if connection is None:
                        raise RuntimeError("SQLite writer connection was not initialized")
                    if (
                        request.deadline_ns is not None
                        and time.monotonic_ns() >= request.deadline_ns
                    ):
                        raise WriteDeadlineExceeded("write deadline elapsed before execution")
                    result = self._invoke(connection, request)
                except BaseException as error:
                    request.loop.call_soon_threadsafe(_set_exception, request.future, error)
                else:
                    request.loop.call_soon_threadsafe(_set_result, request.future, result)
                finally:
                    self._requests.task_done()
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _invoke(connection: sqlite3.Connection, request: _Request[object]) -> object:
        if not request.transactional:
            return request.operation(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            result = request.operation(connection)
        except BaseException:
            connection.rollback()
            raise
        connection.commit()
        return result


def _set_result(future: asyncio.Future[object], result: object) -> None:
    if not future.done():
        future.set_result(result)


def _set_exception(future: asyncio.Future[object], error: BaseException) -> None:
    if not future.done():
        future.set_exception(error)
