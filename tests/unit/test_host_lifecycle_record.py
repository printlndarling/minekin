"""What a host lifecycle report may become in the run document.

Publishing a world is the one thing a Kin does that another Kin acts on: the port in
the run document is an address somebody dials. So the document's vocabulary is closed
and its port has to agree with its phase, and the tests here are about what the
*writer* refuses — a phase this build cannot name, an opening that names no address,
and a failure that names one.

The Bridge refuses to produce the last two, and that is a different thing from Core
checking. The report arrives over the IPC boundary, which the contract treats as a
peer that can be wrong, and what it would end up in is the document a joiner reads:
"published on port 0" is worse than "the attempt failed", because it looks like
success.

The rule itself is `domain/host_publication.py`'s; what these exercise is the pair —
that the wire's phase numbers become those tokens, and that the rule is applied to
what comes off the wire rather than after something has already recorded it.
"""

from __future__ import annotations

import pytest

from minekin_core.cli.session_runtime import lan_publication
from minekin_core.domain.host_publication import (
    MAX_PORT,
    HostPublicationPhase,
    HostPublicationRefusal,
    host_publication,
)
from minekin_core.generated.minekin.v1 import observation_pb2


def report(phase: observation_pb2.HostPhase, *, port: int = 0) -> observation_pb2.HostLifecycle:
    return observation_pb2.HostLifecycle(
        request_id="lan-1", generation=1, phase=phase, bound_port=port
    )


OPENED = observation_pb2.HOST_PHASE_LAN_OPENED
FAILED = observation_pb2.HOST_PHASE_LAN_OPEN_FAILED


# ---------------------------------------------------------------------------
# HOST-030
# ---------------------------------------------------------------------------


def test_a_publication_is_recorded_by_its_phase_and_its_port() -> None:
    decision = lan_publication(report(OPENED, port=54321))

    assert decision.recorded is not None
    assert decision.recorded.as_document() == {"phase": "LAN_OPENED", "port": 54321}
    assert decision.refusal is None


def test_a_failure_is_recorded_without_a_port() -> None:
    """The port is absent rather than zero: zero is the value the wire says is never
    an address, and a document that carries one invites a reader to dial it."""

    decision = lan_publication(report(FAILED))

    assert decision.recorded is not None
    assert decision.recorded.as_document() == {"phase": "LAN_OPEN_FAILED", "port": None}


def test_a_phase_this_build_cannot_name_is_not_a_fact() -> None:
    """A phase the table does not hold yields a refusal, not a guessed token.

    The table is closed, so this covers everything outside it — including a phase a
    future Bridge might send, which protobuf would hand over as an unknown number.
    """

    decision = lan_publication(report(observation_pb2.HOST_PHASE_UNSPECIFIED))

    assert decision.recorded is None
    assert decision.refusal is HostPublicationRefusal.UNKNOWN_PHASE


@pytest.mark.parametrize("port", [0, MAX_PORT + 1])
def test_an_opening_that_names_no_address_is_not_recorded(port: int) -> None:
    """ "Published" without a port is the shape a joiner would act on and could not.

    The wire cannot carry a negative port (`uint32`), so that bound is the domain
    rule's own and is checked below rather than here.
    """

    decision = lan_publication(report(OPENED, port=port))

    assert decision.recorded is None
    assert decision.refusal is HostPublicationRefusal.PORT_NOT_AN_ADDRESS


def test_a_failure_that_names_a_port_is_not_recorded() -> None:
    """Saying nothing is listening and that something is are two claims, not one."""

    decision = lan_publication(report(FAILED, port=25565))

    assert decision.recorded is None
    assert decision.refusal is HostPublicationRefusal.FAILURE_NAMED_A_PORT


# ---------------------------------------------------------------------------
# The port rule's own boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("port", [1, 25565, MAX_PORT])
def test_the_whole_range_of_real_ports_is_admissible(port: int) -> None:
    """The rule is a range, not a plausibility check: whichever port it bound is the
    port it bound, and `openToLan` may be asked for any of them."""

    decision = host_publication(phase=HostPublicationPhase.LAN_OPENED, bound_port=port)

    assert decision.recorded is not None
    assert decision.recorded.port == port


def test_the_domain_rule_refuses_a_port_the_wire_could_not_carry() -> None:
    """A negative port is not a wire value, and the rule does not rely on that."""

    decision = host_publication(phase=HostPublicationPhase.LAN_OPENED, bound_port=-1)

    assert decision.refusal is HostPublicationRefusal.PORT_NOT_AN_ADDRESS
