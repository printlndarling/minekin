"""What the run document says about publishing a Kin's world.

The port is the fact a joiner acts on, so the vocabulary that reaches the document is
closed: a phase this build cannot name is counted as ignored rather than recorded as
a fact, because "published on port X" is a claim somebody will act on.
"""

from __future__ import annotations

from minekin_core.cli.session_runtime import lan_publication
from minekin_core.generated.minekin.v1 import observation_pb2


def test_a_publicationIsRecordedByItsPhaseAndItsPort() -> None:
    lifecycle = observation_pb2.HostLifecycle(
        request_id="lan-1",
        generation=1,
        phase=observation_pb2.HOST_PHASE_LAN_OPENED,
        bound_port=54321,
    )

    assert lan_publication(lifecycle) == {"phase": "LAN_OPENED", "port": 54321}


def test_aFailureIsRecordedWithoutAPort() -> None:
    lifecycle = observation_pb2.HostLifecycle(
        request_id="lan-1",
        generation=1,
        phase=observation_pb2.HOST_PHASE_LAN_OPEN_FAILED,
        bound_port=0,
    )

    assert lan_publication(lifecycle) == {"phase": "LAN_OPEN_FAILED", "port": 0}


def test_aPhaseThisBuildCannotNameIsNotAFact() -> None:
    """A phase the table does not hold yields nothing, rather than a guessed token.

    The table is closed, so this covers everything outside it — including a phase a
    future Bridge might send, which protobuf would hand over as an unknown number and
    which this would then refuse to record.
    """

    lifecycle = observation_pb2.HostLifecycle(
        request_id="lan-1", generation=1, phase=observation_pb2.HOST_PHASE_UNSPECIFIED
    )

    assert lan_publication(lifecycle) is None
