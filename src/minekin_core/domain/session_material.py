"""Comparing what the Launcher encoded into argv with what the client reported.

The Launcher records the material it put into `--username`, `--uuid`,
`--accessToken`, `--clientId` and `--xuid`; the Bridge independently reads the
live Session. The two are compared before the session is allowed to become
`PLAYABLE`, because a mismatch means the client is not running as the identity
the rest of the run believes it is.

One comparison is deliberately *not* an equality check. `--userType` carries the
launcher's own word (`offline`) while the client reports its `AccountType` enum
(`LEGACY`, `MOJANG`, `MSA`). Those names live in different namespaces, so a
difference is recorded as an observation rather than treated as a mismatch;
requiring equality would reject the OFF-A candidate by construction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

MISMATCH_IDENTITY_CANDIDATE = "identity_candidate_id"
MISMATCH_USERNAME = "username"
MISMATCH_UUID = "uuid"
MISMATCH_CLIENT_ID_PRESENCE = "client_id_presence"
MISMATCH_XUID_PRESENCE = "xuid_presence"
MISMATCH_CREDENTIALS_EXPOSED = "credentials_exposed"
MISMATCH_REPORT_INCOMPLETE = "report_incomplete"


def _canonical_uuid(value: str) -> str | None:
    """Normalize either accepted UUID encoding, or None when it is not a UUID."""

    candidate = value.strip()
    if not candidate:
        return None
    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        try:
            return str(uuid.UUID(hex=candidate))
        except ValueError:
            return None


@dataclass(frozen=True, slots=True)
class RecordedSessionMaterial:
    """The session material the Launcher encoded into the launch arguments."""

    identity_candidate_id: str
    username: str
    uuid_argv: str
    client_id_present: bool
    xuid_present: bool


@dataclass(frozen=True, slots=True)
class ReportedSessionIdentity:
    """What the Bridge read from the live client Session."""

    identity_candidate_id: str
    username: str
    uuid: str
    account_type: str
    client_id_present: bool
    xuid_present: bool
    credential_values_exposed: bool


@dataclass(frozen=True, slots=True)
class SessionMaterialVerdict:
    """A stable, order-independent result that evidence can record as-is."""

    matched: bool
    mismatches: tuple[str, ...]
    observed_account_type: str

    def as_document(self) -> dict[str, object]:
        return {
            "matched": self.matched,
            "mismatches": list(self.mismatches),
            "observed_account_type": self.observed_account_type,
        }


def compare_session_material(
    recorded: RecordedSessionMaterial, reported: ReportedSessionIdentity
) -> SessionMaterialVerdict:
    """Decide whether the client is running as the recorded identity.

    Every reason is collected rather than short-circuiting, so one failure run
    explains the whole difference instead of the first field examined.
    """

    mismatches: set[str] = set()

    if reported.credential_values_exposed:
        mismatches.add(MISMATCH_CREDENTIALS_EXPOSED)

    if not reported.username.strip() or not reported.uuid.strip():
        mismatches.add(MISMATCH_REPORT_INCOMPLETE)

    if reported.identity_candidate_id != recorded.identity_candidate_id:
        mismatches.add(MISMATCH_IDENTITY_CANDIDATE)

    if reported.username != recorded.username:
        mismatches.add(MISMATCH_USERNAME)

    recorded_uuid = _canonical_uuid(recorded.uuid_argv)
    reported_uuid = _canonical_uuid(reported.uuid)
    if recorded_uuid is None or reported_uuid is None or recorded_uuid != reported_uuid:
        mismatches.add(MISMATCH_UUID)

    if reported.client_id_present != recorded.client_id_present:
        mismatches.add(MISMATCH_CLIENT_ID_PRESENCE)

    if reported.xuid_present != recorded.xuid_present:
        mismatches.add(MISMATCH_XUID_PRESENCE)

    return SessionMaterialVerdict(
        matched=not mismatches,
        mismatches=tuple(sorted(mismatches)),
        observed_account_type=reported.account_type,
    )
