from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from minekin_core.adapters.bridge.session_report import (
    decode_session_identity,
    verify_session_identity,
)
from minekin_core.adapters.launcher.launch_plan import build_launch_plan, game_environment
from minekin_core.adapters.launcher.offline_session import (
    OFFLINE_SESSION_CANDIDATES,
    SessionCandidate,
    parse_game_argument_template,
    recorded_material,
    resolve_game_arguments,
)
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.ids import OpaqueId
from minekin_core.domain.offline_identity import OfflineIdentityMaterial
from minekin_core.domain.session_material import (
    MISMATCH_CLIENT_ID_PRESENCE,
    MISMATCH_CREDENTIALS_EXPOSED,
    MISMATCH_IDENTITY_CANDIDATE,
    MISMATCH_REPORT_INCOMPLETE,
    MISMATCH_USERNAME,
    MISMATCH_UUID,
    MISMATCH_XUID_PRESENCE,
    RecordedSessionMaterial,
    ReportedSessionIdentity,
    compare_session_material,
)
from minekin_core.generated.minekin.v1 import session_pb2

PROFILE = Path(__file__).resolve().parents[1] / "fixtures/runtime-input/bundle-p0-core-1.21.4.json"
OFF_A = OFFLINE_SESSION_CANDIDATES[0]


def material(username: str = "Kin") -> OfflineIdentityMaterial:
    return OfflineIdentityMaterial(
        local_profile_id=OpaqueId("kin-01"),
        identity_revision=1,
        username=username,
        created_at="2026-09-19T00:00:00Z",
    )


def resolved(candidate: SessionCandidate = OFF_A) -> list[str]:
    plan = build_launch_plan(PROFILE)
    return resolve_game_arguments(
        parse_game_argument_template(plan["runtime"]["game_arg_template"]),
        material=material(),
        candidate=candidate,
        environment=game_environment(plan),
    )


def recorded(candidate: SessionCandidate = OFF_A) -> RecordedSessionMaterial:
    return recorded_material(candidate, resolved(candidate))


def reported(
    *,
    identity_candidate_id: str = "prism-parity",
    username: str = "Kin",
    uuid: str = "8f40376bc23f3ef1b5535564eea75639",
    account_type: str = "offline",
    client_id_present: bool = False,
    xuid_present: bool = False,
    credential_values_exposed: bool = False,
) -> ReportedSessionIdentity:
    return ReportedSessionIdentity(
        identity_candidate_id=identity_candidate_id,
        username=username,
        uuid=uuid,
        account_type=account_type,
        client_id_present=client_id_present,
        xuid_present=xuid_present,
        credential_values_exposed=credential_values_exposed,
    )


def test_the_recorded_material_is_read_back_from_the_resolved_argv() -> None:
    record = recorded()

    assert record.identity_candidate_id == "prism-parity"
    assert record.username == "Kin"
    assert record.uuid_argv == "8f40376bc23f3ef1b5535564eea75639"
    assert not record.client_id_present
    assert not record.xuid_present


def test_a_matching_report_is_accepted() -> None:
    verdict = compare_session_material(recorded(), reported())

    assert verdict.matched
    assert verdict.mismatches == ()
    assert verdict.observed_account_type == "offline"


def test_the_id128_argv_and_a_canonical_report_are_the_same_identity() -> None:
    """The client reports canonical form; the frozen candidates encode id128."""

    verdict = compare_session_material(
        recorded(), reported(uuid="8f40376b-c23f-3ef1-b553-5564eea75639")
    )

    assert verdict.matched


def test_an_uppercase_report_uuid_is_still_the_same_identity() -> None:
    verdict = compare_session_material(
        recorded(), reported(uuid="8F40376BC23F3EF1B5535564EEA75639")
    )

    assert verdict.matched


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("username", "Notch", {MISMATCH_USERNAME}),
        ("uuid", "b50ad385-829d-3141-a216-7e7d7539ba7f", {MISMATCH_UUID}),
        ("uuid", "not-a-uuid", {MISMATCH_UUID}),
        ("identity_candidate_id", "enum-aligned", {MISMATCH_IDENTITY_CANDIDATE}),
        ("client_id_present", True, {MISMATCH_CLIENT_ID_PRESENCE}),
        ("xuid_present", True, {MISMATCH_XUID_PRESENCE}),
        ("credential_values_exposed", True, {MISMATCH_CREDENTIALS_EXPOSED}),
        (
            "username",
            "",
            {MISMATCH_REPORT_INCOMPLETE, MISMATCH_USERNAME},
        ),
        ("uuid", "", {MISMATCH_REPORT_INCOMPLETE, MISMATCH_UUID}),
    ],
)
def test_each_divergence_is_reported(field: str, value: object, expected: set[str]) -> None:
    verdict = compare_session_material(recorded(), replace(reported(), **{field: value}))

    assert not verdict.matched
    assert set(verdict.mismatches) == expected


def test_every_reason_is_collected_in_a_stable_order() -> None:
    verdict = compare_session_material(
        recorded(),
        reported(username="Notch", uuid="not-a-uuid", xuid_present=True),
    )

    assert verdict.mismatches == tuple(sorted(verdict.mismatches))
    assert set(verdict.mismatches) == {
        MISMATCH_USERNAME,
        MISMATCH_UUID,
        MISMATCH_XUID_PRESENCE,
    }


def test_the_account_type_is_recorded_rather_than_compared() -> None:
    """`offline` is the launcher's word, `LEGACY` is the client's enum namespace.

    Requiring them to be equal would reject the OFF-A candidate by construction,
    so a difference is an observation for the evidence bundle.
    """

    verdict = compare_session_material(recorded(), reported(account_type="LEGACY"))

    assert verdict.matched
    assert verdict.observed_account_type == "LEGACY"


def test_an_unknown_account_type_is_recorded_rather_than_rejected() -> None:
    """OFF-N exists to prove an unknown type is detectable, not to be hidden."""

    verdict = compare_session_material(recorded(), reported(account_type="NOT_A_REAL_TYPE"))

    assert verdict.matched
    assert verdict.observed_account_type == "NOT_A_REAL_TYPE"


def test_the_verdict_document_is_evidence_ready() -> None:
    verdict = compare_session_material(recorded(), reported(username="Notch"))

    assert verdict.as_document() == {
        "matched": False,
        "mismatches": [MISMATCH_USERNAME],
        "observed_account_type": "offline",
    }


def test_the_wire_report_decodes_without_inventing_defaults() -> None:
    report = session_pb2.SessionIdentityReport(
        identity_candidate_id="enum-aligned",
        session_username="Kin",
        session_uuid="8f40376bc23f3ef1b5535564eea75639",
        session_account_type="LEGACY",
        session_xuid_present=True,
        session_client_id_present=True,
        credential_values_exposed=False,
    )

    assert decode_session_identity(report) == ReportedSessionIdentity(
        identity_candidate_id="enum-aligned",
        username="Kin",
        uuid="8f40376bc23f3ef1b5535564eea75639",
        account_type="LEGACY",
        client_id_present=True,
        xuid_present=True,
        credential_values_exposed=False,
    )


def test_an_empty_wire_report_fails_closed() -> None:
    verdict = verify_session_identity(recorded(), session_pb2.SessionIdentityReport())

    assert not verdict.matched
    assert MISMATCH_REPORT_INCOMPLETE in verdict.mismatches


def test_the_wire_round_trip_matches_the_launcher_record() -> None:
    report = session_pb2.SessionIdentityReport(
        identity_candidate_id="prism-parity",
        session_username="Kin",
        session_uuid="8f40376b-c23f-3ef1-b553-5564eea75639",
        session_account_type="offline",
        credential_values_exposed=False,
    )

    assert verify_session_identity(recorded(), report).matched


def test_a_mismatched_wire_report_is_not_playable() -> None:
    report = session_pb2.SessionIdentityReport(
        identity_candidate_id="prism-parity",
        session_username="Kin",
        session_uuid="8f40376b-c23f-3ef1-b553-5564eea75639",
        session_account_type="offline",
        session_client_id_present=True,
    )

    verdict = verify_session_identity(recorded(), report)

    assert not verdict.matched
    assert set(verdict.mismatches) == {MISMATCH_CLIENT_ID_PRESENCE}


def drop_uuid(argv: list[str]) -> list[str]:
    return argv[: argv.index("--uuid")]


def duplicate_xuid(argv: list[str]) -> list[str]:
    return [*argv, "--xuid"]


def drop_client_id_value(argv: list[str]) -> list[str]:
    return argv[: argv.index("--clientId") + 1]


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (drop_uuid, "exactly one --uuid"),
        (duplicate_xuid, "exactly one --xuid"),
        (drop_client_id_value, "no value element"),
    ],
)
def test_an_argv_that_does_not_carry_the_options_is_rejected(
    mutate: Callable[[list[str]], list[str]], expected: str
) -> None:
    with pytest.raises(MinekinError, match=expected):
        recorded_material(OFF_A, mutate(resolved()))
