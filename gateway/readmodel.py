# ruff: noqa: RUF001
# The gap reasons here are Chinese sentences the Dashboard renders verbatim, so they
# carry fullwidth punctuation by design — the same reading `domain/restart_rules.py`
# states for its own prompts. RUF001 targets characters used to spoof identifiers.
"""Projecting Core's existing reads into the Dashboard's frozen read model.

Everything here answers from one of three places, and only these three:

* `minekin_core.cli.status.read_status` — the session overlays, the recorded client
  processes and the ledger counters, which is Core's own read-only projection.
* The append-only ledger, opened query-only, for the row order a run lived through.
* A sealed run's evidence bundle, for what a completed attempt recorded.

Nothing here reads a live Bridge, another process' memory, or argv. That is the
identity rule of `docs/gateway-dashboard-readonly-contract-2026-09-28.md` §4, and it is
also why several fields below are gaps rather than values: the honest answer to "what
does Core record about that?" is sometimes "nothing", and a gap says so while a default
value would lie.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, NamedTuple, cast

from gateway.signals import gap, known, missing, present
from minekin_core.adapters.bridge.ipc import DEFAULT_HEARTBEAT_INTERVAL_MS
from minekin_core.adapters.evidence.bundle import BundleVerification, verify_addressed_bundle
from minekin_core.adapters.launcher.orphans import Liveness, default_cmdline, default_probe
from minekin_core.adapters.sqlite.connection import connect_reader
from minekin_core.adapters.sqlite.session_log import (
    AUTH_POLICY_FROZEN,
    CLIENT_EXITED,
    HELLO_ACCEPTED,
    INPUT_LEASE_GRANTED,
    INPUT_REFUSED,
    INPUT_RELEASED,
    JOIN_OBSERVED,
    PLAYABLE_ESTABLISHED,
    PROCESS_FAILED,
    PROCESS_STARTED,
    RESOURCE_PACK_POLICY_APPLIED,
    SESSION_IDENTITY_COMPARED,
    SESSION_INTERRUPTED,
    SESSION_STATE_TRANSITIONED,
)
from minekin_core.application.ports.clock import Clock
from minekin_core.cli.evidence import locate_bundle
from minekin_core.cli.session import database_for, select_kin
from minekin_core.cli.status import ClientSummary, StatusReport, read_status
from minekin_core.domain.errors import MinekinError

SCHEMA_VERSION: Final = "kin-dashboard-readmodel/1.0.0"

#: The three reads the contract freezes. `server.py` routes exactly these, and a fourth
#: is a change to the record rather than a change to this tuple.
SNAPSHOT_PATH: Final = "/api/v1/dashboard/snapshot"
TIMELINE_PATH: Final = "/api/v1/dashboard/timeline"
ALERTS_PATH: Final = "/api/v1/dashboard/alerts"
ROUTES: Final = (SNAPSHOT_PATH, TIMELINE_PATH, ALERTS_PATH)

#: How long a reading stays trustworthy. The Dashboard polls, so this is a little more
#: than two round trips at the 3000 ms request timeout the frontend pins: past that, a
#: panel must show the value as stale instead of as what is happening now.
STALE_AFTER_MS: Final = 8_000

#: How many ledger rows one read consults. A launch writes a few dozen, and only the
#: newest row of a kind can move a projection, so this window cannot lose a fact it
#: needs while keeping the query bounded against a long-lived Kin.
LEDGER_WINDOW: Final = 400
DEFAULT_TIMELINE_LIMIT: Final = 50
MAX_TIMELINE_LIMIT: Final = 200

END_OF_RUN: Final = frozenset({SESSION_INTERRUPTED, CLIENT_EXITED, PROCESS_FAILED})
_JOIN_ROWS: Final = frozenset({JOIN_OBSERVED, PLAYABLE_ESTABLISHED})
_LEASE_ROWS: Final = frozenset({INPUT_LEASE_GRANTED, INPUT_RELEASED, INPUT_REFUSED})
_BRIDGE_ROWS: Final = frozenset({PROCESS_STARTED, HELLO_ACCEPTED}) | END_OF_RUN
_SERVER_ROWS: Final = frozenset({HELLO_ACCEPTED}) | _JOIN_ROWS | END_OF_RUN

_NO_CLIENTS: Final = "这个 Kin 没有记录的客户端进程：还没有启动过会话，或上一次已经收摊。"
_EMPTY_LEDGER: Final = "台账里没有任何事件行：这个 Kin 还没有启动过会话。"
_NO_BUNDLE: Final = "本 run 还没有已封的证据 bundle：封证只在 case 判定之后写入。"

# The identity rule applied to this module's own surface: only these named payload
# fields are ever projected out, so a field Core adds later cannot ride a generic dump.
# `outcome` joins it because it is the only carrier for *why* a session stopped: Core
# writes the SessionOutcome name into the interruption row, and without it the panel can
# only say 会话被中断 and the operator cannot tell a lost bridge from a timed-out handshake.
# `had_lease` joins it for the same reason on the other side of a control action: Core writes it
# into every release row, and only there does a hand-back say whether a lease was still held.
# With just `reason` an already-expired lease and a real one both read as 释放.
_DETAIL_FIELDS: Final = (
    "reason",
    "phase",
    "resource_pack_policy",
    "from",
    "to",
    "capability",
    "outcome",
    "had_lease",
)

# The identity comparison row carries the only refusal signal Core writes for an offline
# session, and the generic list above projects none of it. Contract §4 rule 1 names these
# fields as allowed to appear, so this one event type gets them appended to its detail.
_IDENTITY_DETAIL_FIELDS: Final = (
    "session_username",
    "session_uuid",
    "matched",
    "mismatches",
    "client_id_present",
    "xuid_present",
    "credential_values_exposed",
)

# The frozen-policy row is the only place Core says which Server Profile revision admitted this
# run, and the generic list above projects none of it: on live ledgers the panel could show that
# the decision happened but not what was committed to. Contract §3 puts `server_profile_id` and
# `server_profile_revision` in the tier Core already records — the projection takes that value
# instead of re-deriving it — and `docs/standalone-runtime-dashboard.md:186` gives the Dashboard
# the identity profile and the authentication status, which is these four members and nothing
# else. None of them is a credential value (§4 rule 2), and a row that froze no profile pair keeps
# both keys out rather than printing `None`: the world group already says 没有记下 in words.
_AUTH_DETAIL_FIELDS: Final = (
    "auth_mode",
    "online_adapter_enabled",
    "server_profile_id",
    "server_profile_revision",
)


class EventRow(NamedTuple):
    """One ledger row, in the shape the projections below need."""

    position: int
    event_id: str
    event_type: str
    observed_at_utc: str
    run_id: str | None
    session_id: str | None
    generation: int | None
    sequence: int | None
    payload: Mapping[str, Any]


def _payload_of(raw: str | None) -> Mapping[str, Any]:
    if not raw:
        return {}
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return cast("dict[str, Any]", document) if isinstance(document, dict) else {}


def read_ledger(database: Path, *, limit: int = LEDGER_WINDOW) -> tuple[EventRow, ...]:
    """The newest `limit` events, oldest first, over a connection that cannot write."""

    connection = connect_reader(database)
    try:
        cursor = connection.execute(
            "SELECT position, event_id, event_type, observed_at_utc, run_id, session_id,"
            " generation, sequence, payload_json"
            " FROM event ORDER BY position DESC LIMIT ?",
            (limit,),
        )
        fetched = cursor.fetchall()
    finally:
        connection.close()
    rows = [
        EventRow(
            position=int(row["position"]),
            event_id=str(row["event_id"]),
            event_type=str(row["event_type"]),
            observed_at_utc=str(row["observed_at_utc"]),
            run_id=None if row["run_id"] is None else str(row["run_id"]),
            session_id=None if row["session_id"] is None else str(row["session_id"]),
            generation=None if row["generation"] is None else int(row["generation"]),
            sequence=None if row["sequence"] is None else int(row["sequence"]),
            payload=_payload_of(None if row["payload_json"] is None else str(row["payload_json"])),
        )
        for row in fetched
    ]
    rows.reverse()
    return tuple(rows)


def _latest(rows: Sequence[EventRow], names: frozenset[str]) -> EventRow | None:
    for row in reversed(rows):
        if row.event_type in names:
            return row
    return None


def _observed_at(rows: Sequence[EventRow], names: frozenset[str]) -> str | None:
    last = _latest(rows, names)
    return None if last is None else last.observed_at_utc


def _follows(
    rows: Sequence[EventRow], candidates: frozenset[str], boundaries: frozenset[str]
) -> bool:
    """Whether the newest `candidates` row postdates the newest `boundaries` row.

    Both sides have to exist: a join that never happened is not a join that ended.
    """

    joined = _latest(rows, candidates)
    if joined is None:
        return False
    ended = _latest(rows, boundaries)
    return ended is None or joined.position > ended.position


def _alive(report: StatusReport) -> bool:
    """Whether a client this host can see is live.

    The probe asks the reading process' own PID namespace, and a Kin root can be shared
    with a reader that has none (the Demo mounts the store into a gateway container). Such
    a reader reports `GONE` for a client that is alive elsewhere, because `Liveness` has no
    carrier that names the namespace a pid belongs to. So this bool may only *withhold*
    confirmation; it is never evidence that a row the ledger already wrote did not happen.
    """

    return any(client.liveness is Liveness.ALIVE for client in report.clients)


def bridge_link(rows: Sequence[EventRow], *, alive: bool) -> str:
    """The Core-to-Bridge channel, read off row order rather than a state machine.

    `BridgeHelloAccepted` is the row Core writes once it has verified the client's proof,
    so it is a recorded fact, and only a newer end-of-run row can undo it — a probe that
    cannot see the pid says nothing about whether the hello happened. `connecting` is the
    one reading that is about *now* rather than about the ledger: a launch with no hello
    is still in progress only while a client is live, because a dead one cannot be about
    to finish, and that is where `alive` decides.
    """

    last = _latest(rows, _BRIDGE_ROWS)
    if last is None:
        return "disconnected"
    if last.event_type == HELLO_ACCEPTED:
        return "connected"
    if last.event_type == PROCESS_STARTED:
        return "connecting" if alive else "disconnected"
    return "disconnected"


def server_link(rows: Sequence[EventRow], *, alive: bool) -> str:
    """The client-to-server connection, from the same kind of row order.

    A hello says a client exists, not that it is in a world, so it reads as connecting;
    only a join or playable row says connected, and only a newer end row or hello undoes
    it. A hello *after* a join belongs to a new generation that has not joined yet, which
    is why the newest row decides.
    """

    last = _latest(rows, _SERVER_ROWS)
    if last is None:
        return "disconnected"
    if last.event_type in _JOIN_ROWS:
        return "connected"
    if last.event_type == HELLO_ACCEPTED:
        return "connecting" if alive else "disconnected"
    return "disconnected"


def lease_held(rows: Sequence[EventRow], *, alive: bool) -> bool:
    """Whether input is authorized *now*: the newest lease row, not a count of grants.

    A released or refused ask after a grant is the answer to it, and so is a run that ended
    without one — a client that failed or was interrupted holds nothing whatever its last
    grant row says. A client the reader cannot see holds nothing either, and that refusal
    is kept on purpose even though it can read false beside `server_link`: this is the one
    member the panels might act on, so an unconfirmable authority claim goes unanswered
    rather than optimistic.
    """

    if not alive:
        return False
    last = _latest(rows, _LEASE_ROWS | END_OF_RUN)
    return last is not None and last.event_type == INPUT_LEASE_GRANTED


def _identity_detail(payload: Mapping[str, Any]) -> list[str]:
    """The comparison's own reading: whose identity was asked about, and whether it held.

    These are the fields contract §4 rule 1 names, and nothing else: a member Core adds
    later stays in the ledger. An empty `mismatches` says nothing, so it is left out.
    """

    parts: list[str] = []
    for name in _IDENTITY_DETAIL_FIELDS:
        value = payload.get(name)
        if name == "mismatches":
            if isinstance(value, list | tuple):
                items = cast("Sequence[object]", value)
                names = [item for item in items if isinstance(item, str)]
                if names and len(names) == len(items):
                    parts.append(f"{name}={'|'.join(names)}")
        elif isinstance(value, bool | str):
            parts.append(f"{name}={value}")
    return parts


def _detail(row: EventRow) -> str | None:
    parts = [
        f"{name}={row.payload[name]}"
        for name in _DETAIL_FIELDS
        if isinstance(row.payload.get(name), str | int)
    ]
    if row.event_type == SESSION_IDENTITY_COMPARED:
        parts += _identity_detail(row.payload)
    if row.event_type == AUTH_POLICY_FROZEN:
        parts += [
            f"{name}={row.payload[name]}"
            for name in _AUTH_DETAIL_FIELDS
            if isinstance(row.payload.get(name), str | bool)
        ]
    return ", ".join(parts) if parts else None


def _identity_outcome(payload: Mapping[str, Any]) -> str:
    """An identity comparison is applied only when Core says the identity matched.

    Core writes this row for every read attempt, including the ones it then refuses, so a
    fixed reading would present a rejected session as an accepted one. `matched` has to be
    Core's own boolean: a lookalike `1` is not a match.
    """

    matched = payload.get("matched")
    if matched is True:
        return "applied"
    if matched is False:
        return "rejected"
    return "unknown"


def _current_client(report: StatusReport, rows: Sequence[EventRow]) -> ClientSummary | None:
    """The client the panels should describe: the one whose launch row is newest.

    A Kin can carry more than one session marker after an interrupted run, and reporting
    the first would present a stale attempt as the live one. The ledger's own order says
    which launch came last; a marker with no launch row loses to one that has a row.
    """

    if not report.clients:
        return None

    def launch_position(client: ClientSummary) -> int:
        for row in reversed(rows):
            if (
                row.event_type == PROCESS_STARTED
                and row.session_id == client.session_id
                and row.generation == client.generation
            ):
                return row.position
        return -1

    return max(report.clients, key=launch_position)


def _sealed_bundle(root: Path, rows: Sequence[EventRow]) -> BundleVerification | None:
    """The newest run's bundle, re-derived rather than trusted from its manifest."""

    run_id = None if not rows else rows[-1].run_id
    if run_id is None:
        return None
    try:
        verification = verify_addressed_bundle(locate_bundle(root, run_id))
    except MinekinError:
        # No bundle for this run is a reading, not a fault: the panels show a gap.
        return None
    return verification if verification.sealed and verification.manifest is not None else None


def build_snapshot(
    root: Path,
    *,
    kin_selector: str | None = None,
    clock: Clock,
    probe: Callable[[int], Liveness] = default_probe,
    cmdline: Callable[[int], bytes | None] = default_cmdline,
) -> dict[str, Any]:
    """The one snapshot object the contract freezes, field by field."""

    kin_id = select_kin(root, kin_selector)
    report = read_status(root, kin_selector=kin_selector, probe=probe, cmdline=cmdline)
    rows = read_ledger(database_for(root, kin_id))
    now = clock.utc_now().isoformat()
    alive = _alive(report)
    ref = f"core://status/{kin_id}"

    def source(path: str) -> str:
        return f"{ref}/{path}"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kinId": known(
            str(kin_id), source_ref=source("kin_id"), observed_at=now, stale_after_ms=STALE_AFTER_MS
        ),
        # The three values `ObservedState` has. `paused` and `recovering` are not here
        # because Core has no carrier for either, and a UI that could show them would be
        # showing a state nothing produces.
        "runtimeState": known(
            report.state.value,
            source_ref=source("state"),
            observed_at=now,
            stale_after_ms=STALE_AFTER_MS,
        ),
        "bridgeLink": known(
            bridge_link(rows, alive=alive),
            source_ref=source("bridge_link"),
            observed_at=_observed_at(rows, _BRIDGE_ROWS),
            stale_after_ms=STALE_AFTER_MS,
        ),
        "serverLink": known(
            server_link(rows, alive=alive),
            source_ref=source("server_link"),
            observed_at=_observed_at(rows, _SERVER_ROWS),
            stale_after_ms=STALE_AFTER_MS,
        ),
        "session": _session_group(report, rows, now, source, alive),
        "world": _world_group(rows, now, source, alive),
        "versions": _versions_group(root, rows, now, source),
        "bridgeHeartbeat": _heartbeat_group(report, rows, source, alive),
        "selfState": gap(
            "unavailable",
            "Core 不落相干性快照行：health/food 只在会话内存里，只读投影取不到。",
            source_ref=source("selfState"),
            observed_at=None,
            stale_after_ms=None,
        ),
        "evidence": _evidence_group(root, rows, now, source),
        "liveView": gap(
            "not_wired",
            "没有 framebuffer 采集与媒体中继进程，画面这一面不存在。",
            source_ref=source("liveView"),
            observed_at=None,
            stale_after_ms=None,
        ),
    }


def _session_group(
    report: StatusReport,
    rows: Sequence[EventRow],
    now: str,
    source: Callable[[str], str],
    alive: bool,
) -> dict[str, Any]:
    client = _current_client(report, rows)
    if client is None:
        return gap(
            "unknown",
            _NO_CLIENTS,
            source_ref=source("session"),
            observed_at=None,
            stale_after_ms=None,
        )
    started = next(
        (
            row.observed_at_utc
            for row in reversed(rows)
            if row.event_type == PROCESS_STARTED
            and row.session_id == client.session_id
            and row.generation == client.generation
        ),
        None,
    )
    value = {
        "sessionId": present(client.session_id),
        "generation": present(client.generation),
        "startedAt": present(started)
        if started is not None
        else missing("unknown", "台账里没有这个会话世代的 SessionProcessStarted 行。"),
        "overlay": present(client.overlay),
        "pid": present(client.pid),
        "mode": missing(
            "not_wired", "Core 尚无会话模式枚举（A_companion/B_standalone 属产品决定）。"
        ),
    }
    return known(
        value,
        source_ref=source("session"),
        observed_at=now if started is None else started,
        stale_after_ms=STALE_AFTER_MS if alive else None,
    )


def _world_group(
    rows: Sequence[EventRow], now: str, source: Callable[[str], str], alive: bool
) -> dict[str, Any]:
    frozen = _latest(rows, frozenset({AUTH_POLICY_FROZEN}))
    if frozen is None:
        return gap(
            "unknown",
            _EMPTY_LEDGER,
            source_ref=source("world"),
            observed_at=None,
            stale_after_ms=None,
        )
    profile_id = frozen.payload.get("server_profile_id")
    value = {
        "profileId": present(profile_id)
        if isinstance(profile_id, str)
        else missing("unknown", "这条 AuthPolicyFrozen 行没有记下 server_profile_id。"),
        "profileName": missing(
            "not_wired", "Core 只记 profile 的 id 与 revision，没有具名显示名载体。"
        ),
        "worldContext": missing(
            "not_wired",
            "world_context_id 的可见性属主控/产品决定（契约 §8），只读面不替它作答。",
        ),
        "epoch": missing("not_wired", "同 worldContext：世界坐标类信息的可见性未裁决。"),
        "joined": present(_follows(rows, _JOIN_ROWS, END_OF_RUN)),
        "resolvedVersion": missing("not_wired", "Core 无 resolvedVersion 具名载体。"),
    }
    return known(
        value,
        source_ref=source("world"),
        observed_at=now if frozen.observed_at_utc == "" else frozen.observed_at_utc,
        stale_after_ms=STALE_AFTER_MS if alive else None,
    )


def _heartbeat_group(
    report: StatusReport, rows: Sequence[EventRow], source: Callable[[str], str], alive: bool
) -> dict[str, Any]:
    observed_at = report.ledger.last_observed_at_utc
    if observed_at is None:
        return gap(
            "unknown",
            _EMPTY_LEDGER,
            source_ref=source("bridgeHeartbeat"),
            observed_at=None,
            stale_after_ms=None,
        )
    value = {
        "lastSequence": missing(
            "not_wired",
            "ControlHeartbeat 只有 generation 与 monotonic_ns；台账 position 是记账顺序，"
            "不是桥的计数器。",
        ),
        # The ledger's clock, not the Bridge's: Core's only read of "last we heard" is
        # the newest recorded row. The sourceRef says so on the envelope.
        "lastObservedAt": present(observed_at),
        "intervalMs": present(DEFAULT_HEARTBEAT_INTERVAL_MS),
        "inputLeaseHeld": present(lease_held(rows, alive=alive)),
    }
    return known(
        value,
        source_ref=source("bridgeHeartbeat"),
        observed_at=observed_at,
        stale_after_ms=STALE_AFTER_MS if alive else None,
    )


def _versions_group(
    root: Path, rows: Sequence[EventRow], now: str, source: Callable[[str], str]
) -> dict[str, Any]:
    verification = _sealed_bundle(root, rows)
    manifest = None if verification is None else verification.manifest
    if manifest is None:
        return gap(
            "unavailable",
            _NO_BUNDLE + " 版本五件套没有统一读接口，只有已封 bundle 的清单能答其中三个。",
            source_ref=source("versions"),
            observed_at=None,
            stale_after_ms=None,
        )
    value = {
        "runtime": present(manifest.minecraft),
        "bridge": missing("not_wired", "清单只钉 bridge_digest（一枚摘要），没有桥版本串载体。"),
        "clientBundle": missing(
            "not_wired", "清单记 minecraft/loader/java 版本，没有 bundle 名或 bundle 版本字段。"
        ),
        "java": present(manifest.java_runtime),
        "fabricLoader": present(manifest.loader),
    }
    return known(value, source_ref=source("versions"), observed_at=now, stale_after_ms=None)


def _evidence_group(
    root: Path, rows: Sequence[EventRow], now: str, source: Callable[[str], str]
) -> dict[str, Any]:
    verification = _sealed_bundle(root, rows)
    if verification is None or verification.manifest is None or verification.bundle_digest is None:
        return gap(
            "unknown",
            _NO_BUNDLE,
            source_ref=source("evidence"),
            observed_at=None,
            stale_after_ms=None,
        )
    manifest = verification.manifest
    attempt = manifest.attempt_sequence
    value = {
        "runId": present(manifest.test_run_id),
        "attempt": present(attempt)
        if attempt is not None
        else missing("unknown", "这枚 bundle 的清单没有 attempt_sequence（旧形状封的证）。"),
        "bundleDigest": present(verification.bundle_digest),
        "sealedAt": missing(
            "not_wired", "manifest.json 没有具名密封时间字段；sealed_at_utc 只在封证工具的报告里。"
        ),
    }
    return known(
        value,
        source_ref=f"bundle://{manifest.test_run_id}/manifest.json",
        observed_at=now,
        stale_after_ms=None,
    )


def alerts_payload(kin_id: str, now: str) -> dict[str, Any]:
    """The envelope §5.3 freezes.

    A bare empty array would read as "nothing is wrong", when the truth is that nothing
    decides what wrong would be: Core has no alert source, only ledger events and a run
    document's refusal counts, and no rule says which of those is an alert.
    """

    return {
        "status": "not_wired",
        "reason": "Core 无告警源：只有台账事件与 run document 的拒止计数，哪些算告警属产品决定。",
        "observedAt": now,
        "sourceRef": f"core://status/{kin_id}/alerts",
        "alerts": [],
    }


# Each §5-named event type in the frontend's own vocabulary. A row this table does not
# know is reported as an `observation` with an `unknown` outcome rather than dropped:
# Core wrote it, so the honest reading is that this projection has no meaning for it yet
# — not that it never happened.
TIMELINE_READING: Final[Mapping[str, tuple[str, str]]] = {
    PROCESS_STARTED: ("session", "applied"),
    PROCESS_FAILED: ("fault", "rejected"),
    AUTH_POLICY_FROZEN: ("decision", "applied"),
    HELLO_ACCEPTED: ("session", "applied"),
    JOIN_OBSERVED: ("server_feedback", "applied"),
    PLAYABLE_ESTABLISHED: ("session", "applied"),
    INPUT_LEASE_GRANTED: ("input", "applied"),
    INPUT_RELEASED: ("input", "released"),
    INPUT_REFUSED: ("input", "rejected"),
    SESSION_INTERRUPTED: ("fault", "rejected"),
    RESOURCE_PACK_POLICY_APPLIED: ("decision", "applied"),
    CLIENT_EXITED: ("session", "unknown"),
    SESSION_STATE_TRANSITIONED: ("session", "applied"),
    # The one row whose outcome this table cannot carry: whether it was applied is a reading
    # of its own payload, so the entry below is only the fallback when that reading fails.
    SESSION_IDENTITY_COMPARED: ("observation", "unknown"),
}


def build_timeline(
    root: Path,
    *,
    kin_selector: str | None = None,
    limit: int = DEFAULT_TIMELINE_LIMIT,
) -> list[dict[str, Any]]:
    """The newest ledger rows, newest first, in the frozen timeline shape.

    A timeline row is a record of what Core wrote, so it carries no live facts and needs
    no process probe — unlike the snapshot, whose link states depend on who is alive.
    """

    kin_id = select_kin(root, kin_selector)
    rows = read_ledger(database_for(root, kin_id), limit=min(limit, LEDGER_WINDOW))
    events: list[dict[str, Any]] = []
    for row in reversed(rows):
        kind, outcome = TIMELINE_READING.get(row.event_type, ("observation", "unknown"))
        if row.event_type == SESSION_IDENTITY_COMPARED:
            outcome = _identity_outcome(row.payload)
        events.append(
            {
                "eventId": row.event_id,
                "kind": kind,
                "at": row.observed_at_utc,
                # Core's monotonic clock is per-process, so a second process cannot put a
                # useful number here; the timestamp above is the reading that carries.
                "monotonicMs": None,
                "generation": row.generation,
                "sequence": row.sequence,
                "title": row.event_type,
                "detail": _detail(row),
                "outcome": outcome,
                "sourceRef": f"ledger://{kin_id}/{row.position}",
            }
        )
    return events[:limit]
