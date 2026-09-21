"""What a host lifecycle report is allowed to put in the run document.

Publishing a world is the one thing a Kin does that another Kin acts on: the port
in the run document is an address somebody dials. The contract's host event set has
two phases for it, and the rule that ties a phase to a port is the one this module
holds:

- `LAN_OPENED` must name a port. `0` is not one — the wire says so in as many words
  ("zero is never an address: a reader that joins it would be joining nothing"),
  and a record that says the world is published without saying where is worse than
  a record that says the attempt failed, because it looks like success.
- `LAN_OPEN_FAILED` must not name one. A failure that carries a port is claiming
  both that nothing is listening and that something is.

The Bridge already refuses to *produce* either shape (`LanPublication`, and its
three tests). That is not the same as a reader checking: the report arrives over
the IPC boundary, which the contract treats as a peer that can be wrong, and the
document it would end up in is the one a joiner reads. So the two refusals here are
about the reader's side of the same rule, which is why they are counted rather than
recorded — and why a refusal names *which* shape was wrong, so an operator can tell
"the Bridge and Core disagree about the protocol" from "the world really did not
publish".

The wire enum is deliberately not read here. Phase numbers are lifted to these
tokens in one place, next to the other wire decoding, so that a renamed or
renumbered enum value cannot silently become a different fact about a world.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

#: The highest port a TCP listener can be on. A report naming more than this is not
#: reporting a port, whatever it says the phase is.
MAX_PORT: Final[int] = 65535


class HostPublicationPhase(StrEnum):
    """The two things a host can report about publishing a world."""

    LAN_OPENED = "LAN_OPENED"
    LAN_OPEN_FAILED = "LAN_OPEN_FAILED"


class HostPublicationRefusal(StrEnum):
    """Why a report was not recorded, one reason each."""

    #: A phase this build cannot name. Refused rather than given a token: the
    #: document's vocabulary is closed because a joiner reads it.
    UNKNOWN_PHASE = "UNKNOWN_PHASE"
    #: `LAN_OPENED` without an address a joiner could dial.
    PORT_NOT_AN_ADDRESS = "PORT_NOT_AN_ADDRESS"
    #: `LAN_OPEN_FAILED` while naming a port.
    FAILURE_NAMED_A_PORT = "FAILURE_NAMED_A_PORT"


@dataclass(frozen=True, slots=True)
class PublicationRecord:
    """What the run document keeps: the phase, and the port or nothing."""

    phase: HostPublicationPhase
    #: The port a joiner dials, or None when there is nothing to dial — a failure
    #: record carries no port at all, rather than the zero the wire puts there.
    port: int | None

    def as_document(self) -> dict[str, object]:
        return {"phase": self.phase.value, "port": self.port}


@dataclass(frozen=True, slots=True)
class HostPublicationDecision:
    """The answer about one report: what to record, or why nothing was."""

    recorded: PublicationRecord | None
    refusal: HostPublicationRefusal | None

    def __str__(self) -> str:
        if self.recorded is not None:
            return (
                f"{self.recorded.phase.value}:{self.recorded.port}"
                if self.recorded.port is not None
                else self.recorded.phase.value
            )
        return str(self.refusal)

    def as_document(self) -> dict[str, object]:
        return {
            "recorded": None if self.recorded is None else self.recorded.as_document(),
            "refusal": None if self.refusal is None else self.refusal.value,
        }


def host_publication(
    *, phase: HostPublicationPhase | None, bound_port: int
) -> HostPublicationDecision:
    """Whether one host lifecycle report may become a fact about the world.

    `phase` is None for a phase this build cannot name, which the caller recognises
    by matching the wire number against its own table — a report whose phase is
    unknown is not evidence about a port either, because nothing here knows what the
    phase was supposed to mean.
    """

    if phase is None:
        return HostPublicationDecision(None, HostPublicationRefusal.UNKNOWN_PHASE)
    if phase is HostPublicationPhase.LAN_OPENED:
        if not 1 <= bound_port <= MAX_PORT:
            return HostPublicationDecision(None, HostPublicationRefusal.PORT_NOT_AN_ADDRESS)
        return HostPublicationDecision(PublicationRecord(phase, bound_port), None)
    if bound_port != 0:
        return HostPublicationDecision(None, HostPublicationRefusal.FAILURE_NAMED_A_PORT)
    return HostPublicationDecision(PublicationRecord(phase, None), None)
