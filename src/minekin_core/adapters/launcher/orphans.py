"""Detecting a client left behind by a previous run.

Starting a second client on top of a live one is worse than a failed start: two
JVMs share one session overlay and the server sees two players. So a start refuses
while a previous session's process is unresolved, and names it.

A live PID is not the end of the question. On a platform that can be asked, the
command line of a live PID says whether it is the client this run recorded or
something that inherited its number — the same evidence the stop path decides on.
A live PID whose command line is provably not ours is gone, so a start may
proceed; one whose command line cannot be read is unresolved, and then a start
refuses, because "probably gone" is not a reason to put a second player in a world.

Nothing clears a marker. A marker for a finished run is the trace that the run
happened, in keeping with the rule that failed runs are appended rather than
overwritten; only a session that never resolved needs an operator to look.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import cast

from minekin_core.adapters.launcher.supervisor import ProcessIdentity, parse_process_identity
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

MARKER_NAME = "process.json"
_MARKER_SCHEMA_VERSION = 1

# A PID probe is only trustworthy on POSIX. On Windows `os.kill(pid, 0)` reports a
# reaped process as still present, so it cannot answer the question at all.
_PROBE_IS_RELIABLE = os.name == "posix"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.orphans",
        "reconcile",
        ErrorCategory.PROCESS,
        Retryability.OPERATOR_ACTION,
        message,
    )


class Liveness(StrEnum):
    ALIVE = "ALIVE"
    GONE = "GONE"
    # The platform cannot answer, so the process is unresolved rather than gone.
    UNKNOWN = "UNKNOWN"


def default_probe(pid: int) -> Liveness:
    """Ask the operating system whether a PID exists, or admit that it cannot."""

    # An impossible PID is impossible everywhere, so this is answered before the
    # platform gate rather than being reported as an unknown.
    if pid < 1:
        return Liveness.GONE
    if not _PROBE_IS_RELIABLE:
        return Liveness.UNKNOWN
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return Liveness.GONE
    except PermissionError:
        # It exists; it just is not ours to signal.
        return Liveness.ALIVE
    except OSError:
        return Liveness.UNKNOWN
    return Liveness.ALIVE


@dataclass(frozen=True, slots=True)
class SessionClaim:
    """What a previous run recorded about the client it started."""

    session_id: str
    generation: int
    overlay: str
    identity: ProcessIdentity
    liveness: Liveness

    @property
    def resolved(self) -> bool:
        return self.liveness is Liveness.GONE

    def as_document(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "generation": self.generation,
            "overlay": self.overlay,
            "liveness": self.liveness.value,
            **self.identity.as_document(),
        }


def write_marker(
    overlay: Path, *, identity: ProcessIdentity, session_id: str, generation: int
) -> Path:
    """Record what was started in the session it belongs to."""

    marker = overlay / MARKER_NAME
    document = {
        "schema_version": _MARKER_SCHEMA_VERSION,
        "session_id": session_id,
        "generation": generation,
        "identity": identity.as_document(),
    }
    marker.write_bytes(json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return marker


def _markers(run_root: Path) -> Iterator[Path]:
    session_root = run_root / "session"
    if not session_root.is_dir():
        return
    yield from sorted(session_root.glob(f"*/generation-*/{MARKER_NAME}"))


def _read(path: Path) -> SessionClaim:
    try:
        document = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        # A marker nobody can read is an operator problem, not an empty one.
        raise _reject(f"{path} is not a readable process marker: {error}") from error
    if not isinstance(document, dict):
        raise _reject(f"{path} is not a process marker object")
    record = cast(dict[str, object], document)
    if record.get("schema_version") != _MARKER_SCHEMA_VERSION:
        raise _reject(f"{path} has an unreviewed marker schema")
    identity_value = record.get("identity")
    if not isinstance(identity_value, dict):
        raise _reject(f"{path} has no recorded process identity")
    session_id = record.get("session_id")
    generation = record.get("generation")
    if not isinstance(session_id, str) or not session_id:
        raise _reject(f"{path} has no session id")
    if isinstance(generation, bool) or not isinstance(generation, int):
        raise _reject(f"{path} has no generation")
    identity = parse_process_identity(cast(dict[str, object], identity_value))
    return SessionClaim(
        session_id=session_id,
        generation=generation,
        overlay=str(path.parent),
        identity=identity,
        # Filled in by the caller, which owns the probe.
        liveness=Liveness.UNKNOWN,
    )


class IdentityProof(StrEnum):
    """Whether a live process can be shown to be the client this run recorded."""

    PROVEN = "PROVEN"
    # It exists, but its command line is not the one we recorded, so the PID has
    # been reused by something else and is none of our business.
    NOT_OURS = "NOT_OURS"
    # This platform cannot be asked. Refusing beats guessing, because the guess
    # that is wrong here kills an unrelated process.
    UNVERIFIABLE = "UNVERIFIABLE"


def default_cmdline(pid: int) -> bytes | None:
    """The process's NUL-separated command line, or None when it cannot be read.

    Linux exposes exactly what the process was started with, which is precisely
    what was hashed into the marker.
    """

    if os.name != "posix":
        return None
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None


def prove_process_identity(
    pid: int,
    expected_digest: str,
    *,
    read_cmdline: Callable[[int], bytes | None] = default_cmdline,
) -> IdentityProof:
    """Decide whether a live `pid` is the client the marker recorded.

    The recorded digest is over the arguments joined with NUL, and `/proc` reports
    them separated by NUL with a trailing one, so the comparison is exact rather
    than a heuristic on a process name.
    """

    raw = read_cmdline(pid)
    if raw is None:
        return IdentityProof.UNVERIFIABLE
    command_line = raw.rstrip(b"\x00")
    if not command_line:
        return IdentityProof.NOT_OURS
    return (
        IdentityProof.PROVEN
        if hashlib.sha256(command_line).hexdigest() == expected_digest
        else IdentityProof.NOT_OURS
    )


def _probed(run_root: Path, probe: Callable[[int], Liveness]) -> Iterator[SessionClaim]:
    """Every marker, carrying only what the OS probe answers about its PID.

    Keeping the probe's raw answer here is what lets the stop path refuse a PID it
    cannot prove: reading a verdict that already collapsed a foreign PID into
    "gone" would lose the distinction before stop could report it.
    """

    for path in _markers(run_root):
        claim = _read(path)
        yield replace(claim, liveness=probe(claim.identity.pid))


def session_claims(
    run_root: Path,
    *,
    probe: Callable[[int], Liveness] = default_probe,
    cmdline: Callable[[int], bytes | None] = default_cmdline,
) -> tuple[SessionClaim, ...]:
    """Every recorded client, with what the platform can say about it.

    A live PID is only this run's client when its command line is the one the
    marker recorded. When the platform can read that line and it is not ours, the
    operating system reused the number and the client is gone; when the line
    cannot be read, the client is unresolved rather than assumed gone.
    """

    return tuple(_identified(claim, cmdline=cmdline) for claim in _probed(run_root, probe))


def _identified(claim: SessionClaim, *, cmdline: Callable[[int], bytes | None]) -> SessionClaim:
    """Turn a live PID into the answer its command line can prove."""

    if claim.liveness is not Liveness.ALIVE:
        return claim
    proof = prove_process_identity(
        claim.identity.pid, claim.identity.argv_digest, read_cmdline=cmdline
    )
    if proof is IdentityProof.PROVEN:
        return claim
    return replace(
        claim,
        liveness=Liveness.GONE if proof is IdentityProof.NOT_OURS else Liveness.UNKNOWN,
    )


def require_no_unresolved_client(
    run_root: Path,
    *,
    probe: Callable[[int], Liveness] = default_probe,
    cmdline: Callable[[int], bytes | None] = default_cmdline,
) -> None:
    """Refuse a new start while a previous session's client is unresolved."""

    unresolved = tuple(
        claim
        for claim in session_claims(run_root, probe=probe, cmdline=cmdline)
        if not claim.resolved
    )
    if not unresolved:
        return
    first = unresolved[0]
    others = f" (and {len(unresolved) - 1} more)" if len(unresolved) > 1 else ""
    raise _reject(
        f"session {first.session_id} generation {first.generation} recorded client pid "
        f"{first.identity.pid} and it is {first.liveness.value}{others}; confirm it is gone "
        f"and remove {Path(first.overlay) / MARKER_NAME}, or stop it deliberately"
    )


def terminate_process(pid: int) -> None:
    """Ask one process to stop. Only ever called for a proven identity."""

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError as error:
        raise _reject(
            f"process {pid} could not be asked to stop: {type(error).__name__}"
        ) from error


@dataclass(frozen=True, slots=True)
class StopOutcome:
    """What stopping asked for, and what it declined to do."""

    terminated: tuple[int, ...]
    left_alone: tuple[int, ...]
    unresolved: tuple[int, ...]

    @property
    def complete(self) -> bool:
        return not self.unresolved

    def as_document(self) -> dict[str, object]:
        return {
            "terminated": list(self.terminated),
            "left_alone": list(self.left_alone),
            "unresolved": list(self.unresolved),
        }


def stop_recorded_clients(
    run_root: Path,
    *,
    probe: Callable[[int], Liveness] = default_probe,
    read_cmdline: Callable[[int], bytes | None] = default_cmdline,
    terminate: Callable[[int], None] = terminate_process,
) -> StopOutcome:
    """Stop the clients this run recorded, and only the ones it can prove are its own.

    The operator asking is the authorisation to stop; what still has to be earned
    is the right to signal a particular PID, and a command line that matches the
    marker is what earns it.
    """

    terminated: list[int] = []
    left_alone: list[int] = []
    unresolved: list[int] = []
    for claim in _probed(run_root, probe):
        pid = claim.identity.pid
        if claim.resolved:
            # The probe says the recorded PID is gone, so there is nothing to stop.
            continue
        if claim.liveness is Liveness.UNKNOWN:
            # The platform cannot say whether it still exists, so it cannot earn a
            # signal; the operator is told instead.
            unresolved.append(pid)
            continue
        # Alive: only a command line that matches the marker earns a signal, and
        # one that is provably not ours is reported rather than acted on.
        proof = prove_process_identity(pid, claim.identity.argv_digest, read_cmdline=read_cmdline)
        if proof is IdentityProof.PROVEN:
            terminate(pid)
            terminated.append(pid)
        elif proof is IdentityProof.NOT_OURS:
            left_alone.append(pid)
        else:
            unresolved.append(pid)
    return StopOutcome(
        terminated=tuple(terminated),
        left_alone=tuple(left_alone),
        unresolved=tuple(unresolved),
    )
