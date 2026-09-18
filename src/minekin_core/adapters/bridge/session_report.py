"""Decode the Bridge's wire report into the domain's session-material value."""

from __future__ import annotations

from minekin_core.domain.session_material import (
    RecordedSessionMaterial,
    ReportedSessionIdentity,
    SessionMaterialVerdict,
    compare_session_material,
)
from minekin_core.generated.minekin.v1 import session_pb2


def decode_session_identity(
    report: session_pb2.SessionIdentityReport,
) -> ReportedSessionIdentity:
    """Read one report without inventing defaults for fields the Bridge omitted."""

    return ReportedSessionIdentity(
        identity_candidate_id=report.identity_candidate_id,
        username=report.session_username,
        uuid=report.session_uuid,
        account_type=report.session_account_type,
        client_id_present=report.session_client_id_present,
        xuid_present=report.session_xuid_present,
        credential_values_exposed=report.credential_values_exposed,
    )


def verify_session_identity(
    recorded: RecordedSessionMaterial, report: session_pb2.SessionIdentityReport
) -> SessionMaterialVerdict:
    return compare_session_material(recorded, decode_session_identity(report))
