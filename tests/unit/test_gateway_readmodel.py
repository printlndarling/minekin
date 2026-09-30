"""The Gateway's projection of Core's reads, against a ledger this test writes.

Nothing here is a stand-in value: every reading the panels get is one the ledger or the
session markers hold, and every gap is a field Core has no carrier for. The fixtures come
from `tests/gateway_support.py`, which the HTTP tests share.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

from gateway.readmodel import (
    SCHEMA_VERSION,
    STALE_AFTER_MS,
    TIMELINE_READING,
    EventRow,
    alerts_payload,
    bridge_link,
    build_snapshot,
    build_timeline,
    lease_held,
    read_ledger,
    server_link,
)
from gateway_support import (
    CANARY,
    JOINED_RUN_ROWS,
    KIN_ID,
    PID,
    PROFILE_ID,
    PROFILE_REVISION,
    RUN_ID,
    SESSION_ID,
    alive,
    command_line_with_credential,
    gone,
    joined_run,
    launch,
    our_command_line,
    policy_payload,
    record,
    seed_kin,
    started_at,
)
from minekin_core.adapters.launcher.orphans import Liveness
from minekin_core.adapters.sqlite.connection import connect_writer
from minekin_core.adapters.sqlite.session_log import (
    AUTH_POLICY_FROZEN,
    CLIENT_EXITED,
    HELLO_ACCEPTED,
    INPUT_LEASE_GRANTED,
    INPUT_RELEASED,
    JOIN_OBSERVED,
    PLAYABLE_ESTABLISHED,
    PROCESS_FAILED,
    PROCESS_STARTED,
    RESOURCE_PACK_POLICY_APPLIED,
    SESSION_EVENT_TYPES,
    SESSION_IDENTITY_COMPARED,
    SESSION_INTERRUPTED,
    SKILL_STEP_RECORDED,
)
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.session import database_for
from minekin_core.domain.session_material import (
    MISMATCH_UUID,
    MISMATCH_XUID_PRESENCE,
)

ENVELOPE_KEYS = ("status", "sourceRef", "observedAt", "staleAfterMs")
STATUSES = frozenset({"known", "unknown", "unavailable", "not_wired", "permission_denied"})

# A marker for the two members of Core's identity row that §4 rule 1 does not list.
CANDIDATE_MARKER = "candidate-value-that-must-stay-in-the-ledger"

# The seven fields §4 rule 1 names as allowed to appear for an identity comparison.
CONTRACT_NAMED_IDENTITY_FIELDS = frozenset(
    {
        "session_username",
        "session_uuid",
        "matched",
        "mismatches",
        "client_id_present",
        "xuid_present",
        "credential_values_exposed",
    }
)

# The two profile revisions the read-only census of the local volumes actually read (see the lane
# card's AuthPolicyFrozen shape listing), plus the prefix every one of those rows now opens with.
LOOPBACK_REVISION = "77a19c94c4467231e0431891939b09a94e3acd72c8e25edf3d28b24fb66f4df8"
LAN_HOST_REVISION = "9874a7e17928773b468a175a62e254e270ecbb83ad0363776b3089bbec83399b"
POLICY_PREFIX = "auth_mode=offline, online_adapter_enabled=False, "


def snapshot_of(tmp_path: Path, *, probe: Callable[[int], Liveness] = alive) -> dict[str, object]:
    return build_snapshot(tmp_path, clock=FakeClock(), probe=probe, cmdline=our_command_line)


def as_object(node: object, note: str) -> dict[str, object]:
    """A JSON object member, with the reading that says which one was expected."""

    assert isinstance(node, dict), note
    return cast(dict[str, object], node)


def signal(document: Mapping[str, object], key: str) -> dict[str, object]:
    return as_object(document[key], f"{key} is not a signal envelope")


def member(group: Mapping[str, object], key: str) -> dict[str, object]:
    """One `{value}` / `{gap}` member of a group that is itself `known`."""

    assert group["status"] == "known", f"the {key} group is a gap: {group.get('reason')}"
    value = as_object(group["value"], f"the {key} group carries no value object")
    return as_object(value[key], f"{key} is not a member object")


def reported(group: Mapping[str, object], key: str) -> object:
    entry = member(group, key)
    assert "value" in entry, f"{key} is a gap, not a reading: {entry}"
    return entry["value"]


def named_gap(group: Mapping[str, object], key: str) -> str:
    entry = member(group, key)
    gap = as_object(entry.get("gap"), f"{key} carries no gap: {entry}")
    assert gap["status"] in {"unknown", "unavailable", "not_wired"}, gap
    reason = str(gap["reason"])
    assert reason.strip(), f"{key} is a gap with no reason"
    return reason


def envelopes(node: object, path: str = "$") -> list[tuple[str, dict[str, object]]]:
    """Every signal-shaped object in a document, with the path it sits at."""

    found: list[tuple[str, dict[str, object]]] = []
    if isinstance(node, dict):
        document = cast(dict[str, object], node)
        if "status" in document and "sourceRef" in document:
            found.append((path, document))
        for key, value in document.items():
            found.extend(envelopes(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(cast(list[object], node)):
            found.extend(envelopes(value, f"{path}[{index}]"))
    return found


def row(position: int, event_type: str) -> EventRow:
    return EventRow(
        position=position,
        event_id=f"event-{position}",
        event_type=event_type,
        observed_at_utc=f"2026-01-01T00:00:{position:02d}Z",
        run_id=RUN_ID,
        session_id=SESSION_ID,
        generation=1,
        sequence=position,
        payload={},
    )


def test_a_kin_that_never_ran_answers_with_gaps_not_zeroes(tmp_path: Path) -> None:
    seed_kin(tmp_path, with_marker=False)

    document = snapshot_of(tmp_path)

    assert document["schemaVersion"] == SCHEMA_VERSION
    assert signal(document, "kinId")["value"] == "kin-01"
    # The runtime state has a carrier even when nothing runs. The session and the heartbeat
    # are claims about a run, so they answer as named gaps instead of as zeroes.
    assert signal(document, "runtimeState")["value"] == "idle"
    assert signal(document, "session")["status"] == "unknown"
    assert signal(document, "world")["status"] == "unknown"
    assert signal(document, "bridgeHeartbeat")["status"] == "unknown"
    assert signal(document, "evidence")["status"] == "unknown"
    assert signal(document, "versions")["status"] == "unavailable"
    assert signal(document, "liveView")["status"] == "not_wired"
    assert signal(document, "selfState")["status"] == "unavailable"
    for path, envelope in envelopes(document):
        assert all(key in envelope for key in ENVELOPE_KEYS), path
        assert envelope["status"] in STATUSES, path
        if envelope["status"] != "known":
            assert str(envelope.get("reason", "")).strip(), f"{path} is a gap with no reason"
        else:
            assert envelope.get("reason", "") == "", path


def test_a_running_kin_reports_the_state_the_links_and_the_session(tmp_path: Path) -> None:
    joined_run(tmp_path)

    document = snapshot_of(tmp_path)

    assert signal(document, "runtimeState")["value"] == "running"
    assert signal(document, "bridgeLink")["value"] == "connected"
    assert signal(document, "serverLink")["value"] == "connected"
    assert reported(signal(document, "world"), "profileId") == PROFILE_ID
    assert reported(signal(document, "world"), "joined") is True
    assert reported(signal(document, "session"), "sessionId") == SESSION_ID
    assert reported(signal(document, "session"), "generation") == 1
    assert reported(signal(document, "session"), "pid") == PID
    assert reported(signal(document, "session"), "startedAt") == started_at(tmp_path)
    assert reported(signal(document, "bridgeHeartbeat"), "inputLeaseHeld") is True
    assert reported(signal(document, "bridgeHeartbeat"), "intervalMs") == 500
    assert reported(signal(document, "bridgeHeartbeat"), "lastObservedAt") is not None


def test_the_fields_without_a_carrier_stay_named_gaps_beside_the_ones_that_answer(
    tmp_path: Path,
) -> None:
    """Contract §3's C tier. The assertions beside them are the non-vacuity control: a group
    that projected nothing at all would show gaps too."""

    joined_run(tmp_path)

    document = snapshot_of(tmp_path)

    assert named_gap(signal(document, "session"), "mode")
    assert named_gap(signal(document, "world"), "resolvedVersion")
    assert named_gap(signal(document, "world"), "worldContext")
    assert named_gap(signal(document, "world"), "epoch")
    assert named_gap(signal(document, "bridgeHeartbeat"), "lastSequence")
    # The version five and the evidence trio both read a sealed bundle, and this offline root
    # has none: the honest answer is a named group gap, not an empty object.
    assert signal(document, "versions")["status"] == "unavailable"
    assert signal(document, "evidence")["status"] == "unknown"
    assert reported(signal(document, "session"), "sessionId") == SESSION_ID
    assert reported(signal(document, "world"), "profileId") == PROFILE_ID


def test_a_launch_with_no_hello_is_connecting_not_connected(tmp_path: Path) -> None:
    seed_kin(tmp_path)
    record(tmp_path, AUTH_POLICY_FROZEN, policy_payload())
    launch(tmp_path)

    document = snapshot_of(tmp_path)

    assert signal(document, "bridgeLink")["value"] == "connecting"
    assert signal(document, "serverLink")["value"] == "disconnected"
    assert reported(signal(document, "bridgeHeartbeat"), "inputLeaseHeld") is False
    assert reported(signal(document, "world"), "joined") is False


@pytest.mark.parametrize(
    ("last_row", "bridge", "server", "joined", "lease"),
    [
        # Releasing input answers the lease, and nothing else.
        (INPUT_RELEASED, "connected", "connected", True, False),
        # The exit row is the newest fact, so no older hello may still read as connected.
        (CLIENT_EXITED, "disconnected", "disconnected", False, False),
        (SESSION_INTERRUPTED, "disconnected", "disconnected", False, False),
        (PROCESS_FAILED, "disconnected", "disconnected", False, False),
    ],
)
def test_a_newer_boundary_row_undoes_the_older_reading(
    tmp_path: Path, last_row: str, bridge: str, server: str, joined: bool, lease: bool
) -> None:
    seed_kin(tmp_path)
    record(tmp_path, AUTH_POLICY_FROZEN, policy_payload())
    launch(tmp_path)
    record(tmp_path, HELLO_ACCEPTED, {})
    record(tmp_path, JOIN_OBSERVED, {"phase": "CONNECTION_PHASE_JOIN_SEEN"})
    record(tmp_path, INPUT_LEASE_GRANTED, {"capability": "move.forward", "priority": "PLAYER"})
    record(tmp_path, last_row, {"reason": "the run ended"})

    document = snapshot_of(tmp_path)

    assert signal(document, "bridgeLink")["value"] == bridge
    assert signal(document, "serverLink")["value"] == server
    assert reported(signal(document, "world"), "joined") is joined
    assert reported(signal(document, "bridgeHeartbeat"), "inputLeaseHeld") is lease


def test_a_dead_client_holds_no_lease_though_its_last_grant_row_remains(tmp_path: Path) -> None:
    """A frozen position is not a valid endpoint, and a frozen grant is not held input.

    The two links are the other half of the reading, and they keep the ledger's answer:
    a hello and a join are recorded facts, and a probe that reports `GONE` cannot tell
    whether they happened — it can only say it cannot see that pid. `runtimeState` stays
    Core's own host-side read, and `inputLeaseHeld` stays fail-closed, so the panel reads
    "the ledger recorded a connection this host cannot confirm" rather than a clean cut.
    """

    joined_run(tmp_path)

    document = snapshot_of(tmp_path, probe=gone)

    assert signal(document, "runtimeState")["value"] == "idle"
    assert signal(document, "bridgeLink")["value"] == "connected"
    assert signal(document, "serverLink")["value"] == "connected"
    assert reported(signal(document, "bridgeHeartbeat"), "inputLeaseHeld") is False
    # `joined` is the ledger's own record that a run reached a world, so it survives the client
    # leaving it; the lease is a claim about now, so it does not.
    assert reported(signal(document, "world"), "joined") is True


@pytest.mark.parametrize(
    ("rows", "is_alive", "bridge", "server", "lease"),
    [
        ((), True, "disconnected", "disconnected", False),
        ((row(1, PROCESS_STARTED),), True, "connecting", "disconnected", False),
        ((row(1, PROCESS_STARTED), row(2, HELLO_ACCEPTED)), True, "connected", "connecting", False),
        (
            (row(1, PROCESS_STARTED), row(2, HELLO_ACCEPTED), row(3, PLAYABLE_ESTABLISHED)),
            True,
            "connected",
            "connected",
            False,
        ),
        # A hello for a newer generation postdates the join, so that world is not reached yet.
        (
            (row(1, PLAYABLE_ESTABLISHED), row(2, HELLO_ACCEPTED)),
            True,
            "connected",
            "connecting",
            False,
        ),
        ((row(1, INPUT_LEASE_GRANTED),), True, "disconnected", "disconnected", True),
        (
            (row(1, INPUT_LEASE_GRANTED), row(2, INPUT_RELEASED)),
            True,
            "disconnected",
            "disconnected",
            False,
        ),
        # A run that ended without writing a release row still holds nothing.
        (
            (row(1, INPUT_LEASE_GRANTED), row(2, PROCESS_FAILED)),
            True,
            "disconnected",
            "disconnected",
            False,
        ),
        (
            (row(1, INPUT_LEASE_GRANTED), row(2, SESSION_INTERRUPTED)),
            True,
            "disconnected",
            "disconnected",
            False,
        ),
        (
            (row(1, INPUT_LEASE_GRANTED), row(2, CLIENT_EXITED)),
            True,
            "disconnected",
            "disconnected",
            False,
        ),
        ((row(1, INPUT_LEASE_GRANTED),), False, "disconnected", "disconnected", False),
        # The reader-blind shape: a gateway container shares the Kin root but not the client's
        # PID namespace, so `alive` is False beside rows that record a proved hello and a join.
        # A recorded fact outranks a probe that cannot see the pid; only the live-authority
        # claim and the un-proved handshake yield to it.
        (
            (row(1, PROCESS_STARTED), row(2, HELLO_ACCEPTED)),
            False,
            "connected",
            "disconnected",
            False,
        ),
        (
            (row(1, PROCESS_STARTED), row(2, HELLO_ACCEPTED), row(3, JOIN_OBSERVED)),
            False,
            "connected",
            "connected",
            False,
        ),
        # The probe still decides the middle it is honest about: nothing proved a channel, so
        # a client nobody can see is not a handshake in progress.
        ((row(1, PROCESS_STARTED),), False, "disconnected", "disconnected", False),
        # And an end row closes the reading whichever way the probe answers.
        (
            (row(1, PROCESS_STARTED), row(2, JOIN_OBSERVED), row(3, CLIENT_EXITED)),
            False,
            "disconnected",
            "disconnected",
            False,
        ),
    ],
)
def test_the_projections_answer_from_row_order(
    rows: tuple[EventRow, ...], is_alive: bool, bridge: str, server: str, lease: bool
) -> None:
    assert bridge_link(rows, alive=is_alive) == bridge
    assert server_link(rows, alive=is_alive) == server
    assert lease_held(rows, alive=is_alive) is lease


def test_the_alerts_read_is_an_envelope_not_a_bare_array() -> None:
    document = alerts_payload("kin-01", "2026-01-01T00:00:00Z")

    assert document["status"] == "not_wired"
    assert document["alerts"] == []
    assert str(document["reason"]).strip()
    assert document["sourceRef"] == "core://status/kin-01/alerts"
    assert document["observedAt"] == "2026-01-01T00:00:00Z"


def test_the_timeline_reports_rows_newest_first_and_names_their_position(tmp_path: Path) -> None:
    joined_run(tmp_path)

    events = build_timeline(tmp_path, limit=10)
    positions = [int(str(event["sourceRef"]).rsplit("/", 1)[1]) for event in events]

    assert len(events) == JOINED_RUN_ROWS
    assert [event["title"] for event in events][:2] == [INPUT_LEASE_GRANTED, PLAYABLE_ESTABLISHED]
    assert positions == sorted(positions, reverse=True)
    assert all(str(event["sourceRef"]).startswith(f"ledger://{KIN_ID}/") for event in events)
    assert events[0]["kind"] == "input"
    assert events[0]["outcome"] == "applied"
    assert events[0]["detail"] == "capability=move.forward"
    assert events[0]["generation"] == 1
    assert events[0]["sequence"] == JOINED_RUN_ROWS
    assert events[0]["eventId"]
    # Core's monotonic clock is per-process, so a second process has no useful number here.
    assert events[0]["monotonicMs"] is None
    assert events[2]["title"] == JOIN_OBSERVED
    assert events[2]["detail"] == "phase=CONNECTION_PHASE_JOIN_SEEN"
    assert events[3]["title"] == HELLO_ACCEPTED
    assert events[3]["detail"] is None
    assert events[5]["title"] == AUTH_POLICY_FROZEN
    # The frozen policy row names which profile revision it committed to, as a reading of the
    # ledger rather than a re-derivation.
    assert events[5]["detail"] == (
        f"auth_mode=offline, online_adapter_enabled=False, "
        f"server_profile_id={PROFILE_ID}, server_profile_revision={PROFILE_REVISION}"
    )


def test_a_timeline_row_for_a_comparison_reports_it_as_an_observation(tmp_path: Path) -> None:
    """Core's identity row is neither an input nor a decision, and it is not dropped either."""

    seed_kin(tmp_path, with_marker=False)
    record(tmp_path, SESSION_IDENTITY_COMPARED, {"matched": True, "mismatches": []})

    events = build_timeline(tmp_path, limit=5)

    assert events[0]["kind"] == "observation"
    assert events[0]["outcome"] == "applied"
    assert events[0]["detail"] == "matched=True"


def test_an_interrupted_row_reports_the_outcome_that_ended_it(tmp_path: Path) -> None:
    """Which of the two causes stopped the session is a reading, not a guess.

    The live LAN Kin holds six interruption rows carrying `BRIDGE_LOST` and one carrying
    `HANDSHAKE_TIMEOUT`. Before this projection named `outcome` the served detail was None
    for all seven, so the panel said 会话被中断 and left the operator to guess — the row's
    own `outcome` field only ever said `rejected`, which is the classification, not the cause.
    """

    seed_kin(tmp_path, with_marker=False)
    record(tmp_path, SESSION_INTERRUPTED, {"outcome": "BRIDGE_LOST"})
    record(tmp_path, SESSION_INTERRUPTED, {"outcome": "HANDSHAKE_TIMEOUT"})

    events = build_timeline(tmp_path, limit=5)

    assert [str(event["outcome"]) for event in events] == ["rejected", "rejected"]
    assert str(events[0]["detail"]) == "outcome=HANDSHAKE_TIMEOUT"
    assert str(events[1]["detail"]) == "outcome=BRIDGE_LOST"


def test_naming_the_outcome_does_not_open_the_payload_to_a_dump(tmp_path: Path) -> None:
    """The counterexample for the clause above: a credential riding the same row stays out."""

    seed_kin(tmp_path, with_marker=False)
    record(tmp_path, SESSION_INTERRUPTED, {"outcome": "BRIDGE_LOST", "auth_access_token": CANARY})

    events = build_timeline(tmp_path, limit=5)

    assert str(events[0]["detail"]) == "outcome=BRIDGE_LOST"
    assert CANARY not in json.dumps(events, ensure_ascii=False)


def test_a_release_row_says_whether_a_lease_was_actually_held(tmp_path: Path) -> None:
    """A hand-back that released nothing is a different reading from one that did.

    The live LAN Kin holds 12 release rows: 6 with `had_lease=True reason=TIMEOUT` and 6 with
    `had_lease=False reason=EXPLICIT`. Projecting only `reason` served both as a plain release, so
    the panel's 释放 N 次 counted an empty hand-back (the deadline had already lapsed) as a real one
    and the operator could not see which key presses actually gave the lease back.
    """

    seed_kin(tmp_path, with_marker=False)
    record(tmp_path, INPUT_RELEASED, {"reason": "TIMEOUT", "had_lease": True})
    record(tmp_path, INPUT_RELEASED, {"reason": "EXPLICIT", "had_lease": False})

    events = build_timeline(tmp_path, limit=5)

    assert str(events[0]["detail"]) == "reason=EXPLICIT, had_lease=False"
    assert str(events[1]["detail"]) == "reason=TIMEOUT, had_lease=True"


def test_naming_the_lease_flag_does_not_leak_the_lease_internals(tmp_path: Path) -> None:
    """The counterexample for the clause above: identifiers and a deadline stay in the ledger."""

    seed_kin(tmp_path, with_marker=False)
    record(
        tmp_path,
        INPUT_RELEASED,
        {
            "reason": "EXPLICIT",
            "had_lease": False,
            "lease_id": "lease-9031",
            "action_id": CANARY,
            "deadline_monotonic_ns": 16605403739239,
        },
    )

    events = build_timeline(tmp_path, limit=5)

    assert str(events[0]["detail"]) == "reason=EXPLICIT, had_lease=False"
    document = json.dumps(events, ensure_ascii=False)
    assert CANARY not in document
    assert "lease-9031" not in document
    assert "deadline_monotonic_ns" not in document


def test_a_refused_comparison_reports_itself_as_a_rejection_and_names_why(tmp_path: Path) -> None:
    """Core writes this row for a read it then refuses, in exactly the shape of a matched one.

    Before this reading the panels said `applied` to both, so the one ledger row that carries
    an offline-identity refusal was shown as a success — the opposite of what §5 asks the
    timeline to be. The mismatches are Core's own names, not a re-invented vocabulary.
    """

    seed_kin(tmp_path, with_marker=False)
    record(
        tmp_path,
        SESSION_IDENTITY_COMPARED,
        {
            "session_username": "Tester",
            "session_uuid": "25519000-0000-4000-8000-000000000000",
            "observed_account_type": "XBL",
            "client_id_present": True,
            "xuid_present": False,
            "credential_values_exposed": False,
            "matched": False,
            "mismatches": [MISMATCH_UUID, MISMATCH_XUID_PRESENCE],
        },
    )

    events = build_timeline(tmp_path, limit=5)

    assert events[0]["kind"] == "observation"
    assert events[0]["outcome"] == "rejected"
    assert "matched=False" in events[0]["detail"]
    assert f"mismatches={MISMATCH_UUID}|{MISMATCH_XUID_PRESENCE}" in events[0]["detail"]
    assert "session_username=Tester" in events[0]["detail"]
    assert "client_id_present=True" in events[0]["detail"]
    assert "xuid_present=False" in events[0]["detail"]
    assert "credential_values_exposed=False" in events[0]["detail"]


def test_a_comparison_row_that_says_nothing_about_the_verdict_reads_as_unknown(
    tmp_path: Path,
) -> None:
    """The table entry is a fallback, not a claim: no verdict in the row means no verdict shown.

    `matched` has to be Core's boolean. A lookalike `1` is a payload that was not written by
    `identity_ledger_record`, so the projection has no reading to report and says so.
    """

    seed_kin(tmp_path, with_marker=False)
    record(tmp_path, SESSION_IDENTITY_COMPARED, {"session_username": "Tester"})
    record(tmp_path, SESSION_IDENTITY_COMPARED, {"matched": 1, "mismatches": []})

    events = build_timeline(tmp_path, limit=5)

    assert events[1]["outcome"] == "unknown"
    assert events[1]["detail"] == "session_username=Tester"
    assert events[0]["outcome"] == "unknown"
    assert events[0]["detail"] is None
    assert TIMELINE_READING[SESSION_IDENTITY_COMPARED] == ("observation", "unknown")


def test_the_identity_projection_stays_inside_the_fields_the_contract_names(
    tmp_path: Path,
) -> None:
    """§4 rule 1 names seven fields; the other two members of Core's row stay in the ledger.

    `identity_candidate_id` and `observed_account_type` are real payload members of every
    row, so the markers here are the widening this projection must not do — a field is only
    listable because the contract lists it, not because Core wrote it.
    """

    seed_kin(tmp_path, with_marker=False)
    record(
        tmp_path,
        SESSION_IDENTITY_COMPARED,
        {
            "identity_candidate_id": CANDIDATE_MARKER,
            "session_username": "Tester",
            "session_uuid": "25519000-0000-4000-8000-000000000000",
            "observed_account_type": CANDIDATE_MARKER,
            "client_id_present": True,
            "xuid_present": True,
            "credential_values_exposed": False,
            "matched": False,
            "mismatches": [MISMATCH_UUID],
        },
    )

    events = build_timeline(tmp_path, limit=5)

    assert CANDIDATE_MARKER not in json.dumps(events, ensure_ascii=False)
    assert "observed_account_type" not in events[0]["detail"]
    assert "identity_candidate_id" not in events[0]["detail"]
    # The mismatch names do appear, which is what makes the two absences above a reading.
    assert f"mismatches={MISMATCH_UUID}" in events[0]["detail"]
    assert "session_uuid=25519000-0000-4000-8000-000000000000" in events[0]["detail"]

    # Read the emitted surface itself, not the list it was built from: this row carries all
    # seven named members, so a projection that adds a field or drops one shows up here.
    detail = str(events[0]["detail"])
    assert {part.split("=", 1)[0] for part in detail.split(", ")} == CONTRACT_NAMED_IDENTITY_FIELDS


def test_the_timeline_limit_bounds_the_rows_it_returns(tmp_path: Path) -> None:
    joined_run(tmp_path)

    assert [event["title"] for event in build_timeline(tmp_path, limit=2)] == [
        INPUT_LEASE_GRANTED,
        PLAYABLE_ESTABLISHED,
    ]


def test_every_ledger_event_type_has_a_timeline_reading() -> None:
    """Core's closed set against this projection's table: a fifteenth row type must not be able
    to land in the gap between them unnoticed."""

    missing = SESSION_EVENT_TYPES - set(TIMELINE_READING)
    assert not missing, f"timeline readings are missing for {sorted(missing)}"
    assert TIMELINE_READING[PROCESS_FAILED] == ("fault", "rejected")
    assert TIMELINE_READING[INPUT_RELEASED] == ("input", "released")


def test_the_projection_never_echoes_a_credential_held_by_a_ledger_row(tmp_path: Path) -> None:
    """The named fields are the whole surface, so an extra payload member stays in the ledger.

    The control is in the same document: that row's `reason` does reach the panel, so the
    detail path is live and the canary's absence is the projection refusing.
    """

    seed_kin(tmp_path, with_marker=False)
    record(
        tmp_path,
        SESSION_IDENTITY_COMPARED,
        {
            "reason": "identity matched",
            "access_token": CANARY,
            "Authorization": f"Bearer {CANARY}",
            "clientId": CANARY,
        },
    )

    document = json.dumps(build_timeline(tmp_path, limit=5), ensure_ascii=False)

    assert "reason=identity matched" in document
    assert CANARY not in document
    assert "access_token" not in document.lower()
    assert "authorization" not in document.lower()
    assert "clientid" not in document.lower()


def test_the_frozen_policy_row_names_what_it_committed_to(tmp_path: Path) -> None:
    """The projection has discriminative power, so three live shapes read three different ways.

    The census in the lane card found four distinct (`server_profile_id`, `server_profile_revision`)
    pairs and one row with neither, all of them `auth_mode=offline`. Those rows reached the panel as
    `detail=None`: the operator could see a policy had been frozen but not which profile revision
    admitted the run. These payloads are copied from those readings.
    """

    shapes = [
        ("p0-controlled-offline-loopback-1201", LOOPBACK_REVISION),
        ("p0-lan-host-fixture", LAN_HOST_REVISION),
        (None, None),
    ]
    details: list[str] = []
    for index, (profile_id, revision) in enumerate(shapes):
        root = tmp_path / f"kin{index}"
        seed_kin(root, with_marker=False)
        record(
            root,
            AUTH_POLICY_FROZEN,
            {
                "auth_mode": "offline",
                "online_adapter_enabled": False,
                "server_profile_id": profile_id,
                "server_profile_revision": revision,
            },
        )
        details.append(str(build_timeline(root, limit=5)[0]["detail"]))

    assert details[0].startswith(POLICY_PREFIX)
    assert "server_profile_id=p0-controlled-offline-loopback-1201" in details[0]
    assert f"server_profile_revision={LOOPBACK_REVISION}" in details[0]
    assert details[1].startswith(POLICY_PREFIX)
    assert "server_profile_id=p0-lan-host-fixture" in details[1]
    assert f"server_profile_revision={LAN_HOST_REVISION}" in details[1]
    # Absent rather than `None`: the world group already says 没有记下 in words.
    assert details[2] == "auth_mode=offline, online_adapter_enabled=False"
    assert len(set(details)) == len(details)


def test_the_policy_projection_stops_at_the_four_named_members(tmp_path: Path) -> None:
    """A member Core adds later, or a credential on the same row, stays in the ledger.

    The same row's `auth_mode` is the in-document control: the detail path is live, so an absent
    name is the projection refusing rather than the row being unread.
    """

    seed_kin(tmp_path, with_marker=False)
    record(
        tmp_path,
        AUTH_POLICY_FROZEN,
        {
            "auth_mode": "offline",
            "access_token": CANARY,
            "identity_candidate_id": CANDIDATE_MARKER,
            "server_profile_name": CANDIDATE_MARKER,
        },
    )

    document = json.dumps(build_timeline(tmp_path, limit=5), ensure_ascii=False)

    assert "auth_mode=offline" in document
    assert CANARY not in document
    assert CANDIDATE_MARKER not in document
    assert "access_token" not in document.lower()
    assert "server_profile_name" not in document
    # Present-but-null members are not rendered as a value the operator could mistake for one.
    assert "online_adapter_enabled" not in document


def test_the_projection_never_builds_a_field_from_a_command_line(tmp_path: Path) -> None:
    """`read_status` does read the command line, to match the recorded digest. What it says must
    not reach a panel — the structural half of contract §4's rule."""

    seed_kin(tmp_path)
    record(tmp_path, AUTH_POLICY_FROZEN, policy_payload())
    launch(tmp_path)

    document = json.dumps(
        build_snapshot(
            tmp_path, clock=FakeClock(), probe=alive, cmdline=command_line_with_credential
        ),
        ensure_ascii=False,
    )

    assert CANARY not in document
    assert "--xuid" not in document
    assert "--clientId" not in document
    assert str(PID) in document
    # `liveness` is Core's own projection field and §3 names overlay/pid as the extras allowed;
    # the read model uses liveness to decide the links instead of shipping it as a panel field.
    assert '"liveness"' not in document


def test_a_payload_that_is_not_a_document_still_reads_as_a_row(tmp_path: Path) -> None:
    """Blanking one row's payload column is the defective-blob case: the read survives it."""

    seed_kin(tmp_path, with_marker=False)
    record(tmp_path, RESOURCE_PACK_POLICY_APPLIED, {"resource_pack_policy": "ENFORCED"})
    connection = connect_writer(database_for(tmp_path, KIN_ID))
    try:
        connection.execute("UPDATE event SET payload_json = 'not json'")
    finally:
        connection.close()

    events = build_timeline(tmp_path, limit=5)

    assert events[0]["title"] == RESOURCE_PACK_POLICY_APPLIED
    assert events[0]["detail"] is None
    assert events[0]["outcome"] == "applied"


def test_reading_the_snapshot_and_the_timeline_writes_nothing(tmp_path: Path) -> None:
    joined_run(tmp_path)
    before = read_ledger(database_for(tmp_path, KIN_ID))

    build_snapshot(tmp_path, clock=FakeClock(), probe=alive, cmdline=our_command_line)
    build_timeline(tmp_path)

    assert read_ledger(database_for(tmp_path, KIN_ID)) == before


def test_every_envelope_keeps_the_provenance_triple_across_the_whole_document(
    tmp_path: Path,
) -> None:
    joined_run(tmp_path)

    found = envelopes(snapshot_of(tmp_path))

    assert len(found) >= 9
    for path, envelope in found:
        assert isinstance(envelope["sourceRef"], str), path
        assert envelope["sourceRef"].startswith(("ledger://", "bundle://", "core://")), path
        assert "observedAt" in envelope, path
        assert envelope["staleAfterMs"] in (None, STALE_AFTER_MS), path


def test_a_snapshot_answers_the_same_twice(tmp_path: Path) -> None:
    """Two reads cannot disagree about the past, which is what read-only means here."""

    joined_run(tmp_path)

    first = json.dumps(snapshot_of(tmp_path), sort_keys=True)
    second = json.dumps(snapshot_of(tmp_path), sort_keys=True)

    assert first == second


# The payload shape `cli/session.py::on_run_skills` writes: one row per concluded step,
# all-JSON scalars, and every empty member written as the empty string rather than omitted.
SKILL_GOAL = "先挖到木头，再合成木镐"  # noqa: RUF001 -- the fullwidth comma is Chinese prose, not a typo


def skill_step(
    index: int,
    skill: str,
    result: str,
    reason: str,
    attribution: str,
    decision_source: str,
    goal: str = SKILL_GOAL,
    action_id: str | None = None,
) -> dict[str, object]:
    return {
        "step_index": index,
        "skill": skill,
        "result": result,
        "reason": reason,
        "action_id": action_id if action_id is not None else f"act-{index}",
        "attribution": attribution,
        "decision_source": decision_source,
        "model_refusal": "",
        "goal": goal,
    }


def test_skill_step_rows_project_the_newest_step_and_the_count(tmp_path: Path) -> None:
    """The autonomous readings the operator asked the ledger to carry reach the snapshot.

    The two rows are the two verdicts the later world readings can give: a confirmed step,
    whose failure members are empty by construction, and a failed one, whose reason token
    and FailureCode come straight from Core rather than from anything this projection
    guesses. The count is the run's own rows, not a zero padded to look like a reading.
    """

    joined_run(tmp_path)
    record(
        tmp_path,
        SKILL_STEP_RECORDED,
        skill_step(1, "break_seen_block", "CONFIRMED", "", "", "DECISION_FROM_MODEL"),
    )
    record(
        tmp_path,
        SKILL_STEP_RECORDED,
        skill_step(
            2,
            "craft",
            "FAILED",
            "SCREEN_NOT_CONFIRMED",
            "ACTION_NOT_EFFECTIVE",
            "DECISION_FROM_MODEL",
        ),
    )

    group = signal(snapshot_of(tmp_path), "skillSteps")
    assert reported(group, "goal") == SKILL_GOAL
    assert reported(group, "stepIndex") == 2
    assert reported(group, "skill") == "craft"
    assert reported(group, "result") == "FAILED"
    assert reported(group, "reason") == "SCREEN_NOT_CONFIRMED"
    assert reported(group, "attribution") == "ACTION_NOT_EFFECTIVE"
    assert reported(group, "decisionSource") == "DECISION_FROM_MODEL"
    assert named_gap(group, "modelRefusal")
    assert reported(group, "stepCount") == 2
    # Cost and model config are not ledger readings: named gaps that say where they live.
    assert "run document" in named_gap(group, "modelCost")
    assert "run document" in named_gap(group, "modelConfig")


def test_the_skill_step_timeline_row_reads_the_step_own_verdict(tmp_path: Path) -> None:
    """CONFIRMED applies, FAILED rejects, and neither leaks its action identifier.

    The table entry alone would call every step `unknown`; this pins that the outcome is a
    reading of `result`, and the canary in `action_id` pins the field allowlist — the detail
    shows the named step fields and nothing else from the payload.
    """

    seed_kin(tmp_path, with_marker=False)
    record(
        tmp_path,
        SKILL_STEP_RECORDED,
        skill_step(
            1, "break_seen_block", "CONFIRMED", "", "", "DECISION_FROM_MODEL", action_id=CANARY
        ),
    )

    events = build_timeline(tmp_path, limit=5)

    assert events[0]["title"] == SKILL_STEP_RECORDED
    assert events[0]["kind"] == "intent"
    assert events[0]["outcome"] == "applied"
    assert events[0]["detail"] == (
        f"step_index=1, skill=break_seen_block, result=CONFIRMED, "
        f"decision_source=DECISION_FROM_MODEL, goal={SKILL_GOAL}"
    )
    document = json.dumps(events, ensure_ascii=False)
    assert CANARY not in document
    assert "action_id" not in document


def test_a_scripted_run_names_the_goal_gap_instead_of_an_empty_value(tmp_path: Path) -> None:
    """`--skill-plan` writes `goal=""` by construction; the panel reads that as a named gap.

    The same shape answers the other two by-construction empties here: a local decision was
    never refused by a model, and an UNKNOWN step whose mind gave no attribution says so in
    words rather than rendering as a blank or a zero.
    """

    joined_run(tmp_path)
    record(
        tmp_path,
        SKILL_STEP_RECORDED,
        skill_step(
            1,
            "collect_dropped",
            "UNKNOWN",
            "NO_CONFIRMING_OBSERVATION",
            "",
            "OPERATOR_PLAN",
            goal="",
        ),
    )

    group = signal(snapshot_of(tmp_path), "skillSteps")
    goal_gap = named_gap(group, "goal")
    assert "--skill-plan" in goal_gap
    goal_member = member(group, "goal")
    gap = as_object(goal_member["gap"], "the goal row is a reading, not a gap")
    assert gap["status"] == "unavailable"
    assert reported(group, "decisionSource") == "OPERATOR_PLAN"
    refusal_gap = named_gap(group, "modelRefusal")
    assert "不经过模型" in refusal_gap
    assert reported(group, "result") == "UNKNOWN"
    assert reported(group, "reason") == "NO_CONFIRMING_OBSERVATION"
    assert "attribution" in named_gap(group, "attribution").lower()

    events = build_timeline(tmp_path, limit=2)
    assert events[0]["outcome"] == "unknown"
    # The empty goal is omitted from the timeline detail, the way a null profile pair is.
    assert events[0]["detail"] == (
        "step_index=1, skill=collect_dropped, result=UNKNOWN, reason=NO_CONFIRMING_OBSERVATION, "
        "decision_source=OPERATOR_PLAN"
    )


def test_a_kin_that_never_drove_skills_shows_the_gap_not_a_zero_count(tmp_path: Path) -> None:
    """Steps that were never run have no count: the group answers as a whole named gap.

    A `{stepCount: 0}` beside a known group would read as "this run chose to do nothing",
    which is a fact nothing recorded. The joined run is the non-vacuity control beside the
    never-ran kin: both answer the same way because both have no such rows.
    """

    joined_run(tmp_path)
    document = snapshot_of(tmp_path)
    group = signal(document, "skillSteps")
    assert group["status"] == "unknown"
    assert "SkillStepRecorded" in str(group["reason"])
    assert group["value"] is None

    seed_kin(tmp_path / "fresh", with_marker=False)
    never = signal(snapshot_of(tmp_path / "fresh"), "skillSteps")
    assert never["status"] == "unknown"
    assert never["value"] is None
