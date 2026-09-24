"""Observation shapes for the read-only version probe.

A probe report is an observation, never a decision: it records what one saved
profile revision answered, and the categories below are the only shapes a
failure may take. Nothing here logs in, guesses a version by trial, or reaches
an endpoint the profile did not already save.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

# A status response is a document, not a stream: anything past these caps is
# treated as hostile input rather than as data to display.
MAX_STATUS_PAYLOAD_BYTES: Final = 1_048_576
MAX_DISPLAY_TEXT_CHARS: Final = 64

# Addresses that are safe to echo into logs and reports: loopback and the
# RFC 5737 documentation ranges the public fixtures use. Everything else is a
# runner's private target and is referenced only by its profile id.
_ECHO_ALLOWED_NETWORKS: Final = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)


class ProbeOutcome(StrEnum):
    """Why a probe ended where it did, as a stable evidence token."""

    OBSERVED = "OBSERVED"
    NO_RESPONSE = "NO_RESPONSE"
    TIMEOUT = "TIMEOUT"
    MALFORMED = "MALFORMED"
    OVERSIZE = "OVERSIZE"
    AMBIGUOUS = "AMBIGUOUS"
    CACHE_EXPIRED = "CACHE_EXPIRED"
    POLICY_REFUSAL = "POLICY_REFUSAL"


def may_echo_endpoint(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in _ECHO_ALLOWED_NETWORKS)


def endpoint_ref(host: str, port: int, profile_id: str) -> str:
    """A log-safe reference: echo what is already public, name the rest only by profile."""

    if may_echo_endpoint(host):
        return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    return f"profile:{profile_id}"


@dataclass(frozen=True, slots=True)
class ProbeObservation:
    """One attributable probe reading against one profile revision."""

    outcome: ProbeOutcome
    profile_id: str
    profile_revision: str
    endpoint: str
    resolution_chain: tuple[str, ...]
    protocol: int | None = None
    version_text: str | None = None
    refusal_reasons: tuple[str, ...] = ()
    received_bytes: int = 0
    detail: str | None = None

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "version-probe-observation",
            "outcome": self.outcome.value,
            "profile_id": self.profile_id,
            "profile_revision": self.profile_revision,
            "endpoint": self.endpoint,
            "resolution_chain": list(self.resolution_chain),
            "protocol": self.protocol,
            "version_text": self.version_text,
            "refusal_reasons": list(self.refusal_reasons),
            "received_bytes": self.received_bytes,
            "detail": self.detail,
        }
