"""Address admission rules for the trusted connect pipeline.

A connection target is never chosen by untrusted text. The profile supplies an
address, and the endpoint that resolution actually produced is checked again
afterwards, because a name or an SRV record can point somewhere the profile did
not intend.

Two kinds of rule live here. A *policy* is what a given bundle admits, and it can
be narrowed freely. The *unconditional blocks* are separate: link-local
(including the cloud metadata address), unspecified and multicast ranges are
never admissible no matter how broad a policy becomes, so a future policy cannot
be widened into them by accident.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

Address = ipaddress.IPv4Address | ipaddress.IPv6Address
Network = ipaddress.IPv4Network | ipaddress.IPv6Network

MIN_PORT: Final[int] = 1
MAX_PORT: Final[int] = 65535


class AddressReason(StrEnum):
    """Why an endpoint was refused, as a stable, evidence-safe token."""

    PORT_OUT_OF_RANGE = "PORT_OUT_OF_RANGE"
    NOT_A_LITERAL = "NOT_A_LITERAL"
    LINK_LOCAL = "LINK_LOCAL"
    UNSPECIFIED = "UNSPECIFIED"
    MULTICAST = "MULTICAST"
    OUTSIDE_POLICY = "OUTSIDE_POLICY"


# Ranges that no policy may ever admit. The link-local entries matter most: the
# IPv4 one is the cloud metadata address space, which an SRV redirect would
# otherwise be able to reach.
_UNCONDITIONAL_BLOCKS: Final[tuple[tuple[AddressReason, tuple[Network, ...]], ...]] = (
    (
        AddressReason.LINK_LOCAL,
        (ipaddress.ip_network("169.254.0.0/16"), ipaddress.ip_network("fe80::/10")),
    ),
    (
        AddressReason.UNSPECIFIED,
        (ipaddress.ip_network("0.0.0.0/32"), ipaddress.ip_network("::/128")),
    ),
    (
        AddressReason.MULTICAST,
        (ipaddress.ip_network("224.0.0.0/4"), ipaddress.ip_network("ff00::/8")),
    ),
)


@dataclass(frozen=True, slots=True)
class AddressPolicy:
    """The networks a saved profile is allowed to reach."""

    allowed_networks: tuple[Network, ...]

    def __post_init__(self) -> None:
        if not self.allowed_networks:
            raise ValueError("an address policy must allow at least one network")

    @classmethod
    def p0_loopback(cls) -> AddressPolicy:
        """The frozen P0 policy: exactly the two loopback literals the schema names."""

        return cls((ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("::1/128")))


@dataclass(frozen=True, slots=True)
class EndpointDecision:
    """A stable decision that evidence can record without carrying a hostname."""

    allowed: bool
    reasons: tuple[AddressReason, ...]
    address: str | None

    def as_document(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reasons": [reason.value for reason in self.reasons],
            "address": self.address,
        }


def _parse_literal(host: str) -> Address | None:
    """Parse only an IP literal; a name is not resolvable here and can rebind."""

    candidate = host.strip()
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    if not candidate:
        return None
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def decide_endpoint(policy: AddressPolicy, host: str, port: object) -> EndpointDecision:
    """Decide whether a resolved endpoint may be connected to.

    Every applicable reason is collected, so one blocked attempt explains the
    whole decision instead of only the first rule that matched. `port` is taken
    as an object because this is a boundary: a value from a document or a socket
    may not be the integer it is supposed to be.
    """

    reasons: set[AddressReason] = set()
    if isinstance(port, bool) or not isinstance(port, int) or not MIN_PORT <= port <= MAX_PORT:
        reasons.add(AddressReason.PORT_OUT_OF_RANGE)

    address = _parse_literal(host)
    if address is None:
        reasons.add(AddressReason.NOT_A_LITERAL)
        return EndpointDecision(allowed=False, reasons=tuple(sorted(reasons)), address=None)

    for reason, networks in _UNCONDITIONAL_BLOCKS:
        if any(address in network for network in networks):
            reasons.add(reason)

    if not any(address in network for network in policy.allowed_networks):
        reasons.add(AddressReason.OUTSIDE_POLICY)

    return EndpointDecision(
        allowed=not reasons,
        reasons=tuple(sorted(reasons)),
        address=str(address),
    )
