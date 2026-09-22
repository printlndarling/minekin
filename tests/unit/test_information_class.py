"""What may reach the Kin's own mind, and the two ways the gate could be fooled.

The contract's third gate is one sentence — every DTO has an information class and
only `PLAYER_EQUIVALENT` enters the cognition path — and the tests below are the
three places it can be gotten wrong.

The first is the tempting one: decide the class from the payload's *shape*. It
cannot work, and not for a philosophical reason: protobuf bytes are not
self-describing, so a management DTO's own bytes decode as an observation and
`game_tick` comes back holding a generation. A router that recognised
observations by their shape would admit that. `HOSTCTL-070` is this case, and its
assertion is written against the bytes rather than against a description of them.

The second is defaulting. A message type the table has never seen is refused
rather than assumed harmless, and the test that covers it uses the name a
server-side DTO *would* have — so the failure it describes is the one that would
otherwise arrive silently, the day somebody adds one.

The third is the table disagreeing with the IPC layer that actually carries these
messages, which no amount of care prevents, so it is bound in both directions:
every inbound DTO has a class, and every class names an inbound DTO.
"""

from __future__ import annotations

import pytest

from minekin_core.adapters.bridge.ipc import INBOUND_EVENT_TYPES
from minekin_core.domain.information_class import (
    ACTION_RESULT,
    BUDGET_WINDOW,
    CONNECTION_LIFECYCLE,
    DTO_INFORMATION_CLASSES,
    HOST_LIFECYCLE,
    INITIAL_OBSERVATION,
    CognitionRefusal,
    InformationClass,
    admit_to_cognition,
    classify_dto,
)
from minekin_core.generated.minekin.v1 import observation_pb2

#: The classes this build decides, written out rather than derived from the table.
#: A change here is a decision about what the Kin may know, so it should have to be
#: made twice: once in the module and once in this list, where a reviewer sees it.
REVIEWED_CLASSES = {
    INITIAL_OBSERVATION: InformationClass.PLAYER_EQUIVALENT,
    CONNECTION_LIFECYCLE: InformationClass.PLAYER_EQUIVALENT,
    ACTION_RESULT: InformationClass.PLAYER_EQUIVALENT,
    HOST_LIFECYCLE: InformationClass.MANAGEMENT_ONLY,
    # The Bridge's own callback cost. Management-only for a different reason than
    # the hosting status is: nobody could have seen it by playing, and it is a
    # measurement of this repository's machinery rather than of anything in the
    # world. It belongs in evidence and not in the Kin's model of where it is.
    BUDGET_WINDOW: InformationClass.MANAGEMENT_ONLY,
}


# ---------------------------------------------------------------------------
# HOSTCTL-070
# ---------------------------------------------------------------------------


def test_a_management_dto_is_refused_however_observation_shaped_its_bytes_are() -> None:
    """HOSTCTL-070: host-control's output does not become the Kin's world.

    The lifecycle report carries a generation, and the first snapshot's second
    field is `game_tick` — both varints at field 2 — so the management DTO's own
    bytes decode as an observation and `game_tick` reads back the generation. That
    is what makes shape useless as a classifier and this gate necessary: the two
    payloads are indistinguishable from the inside, and the only thing that tells
    them apart is the type the sender declared, which the reader checks.

    The refusal is asserted in the same test as the decoding because the point is
    the pair: the bytes are admissible *and* the route is refused.
    """

    lifecycle = observation_pb2.HostLifecycle(
        request_id="open-lan-1",
        generation=4,
        phase=observation_pb2.HOST_PHASE_LAN_OPENED,
        bound_port=25565,
    )

    # The bytes a server-side DTO would arrive as, read as the message the Kin's
    # perception path accepts.
    as_observation = observation_pb2.InitialObservation.FromString(lifecycle.SerializeToString())
    assert as_observation.game_tick == 4, "the two messages share field 2, and this is why"

    # And the route: same bytes, declared as what they are, refused.
    decision = admit_to_cognition(HOST_LIFECYCLE)

    assert decision.admitted is False
    assert decision.refusal is CognitionRefusal.MANAGEMENT_ONLY_DTO
    assert decision.information_class is InformationClass.MANAGEMENT_ONLY


def test_an_unclassified_server_side_dto_is_refused_rather_than_defaulted() -> None:
    """The DTO this protocol refuses to have, named as it would be named.

    A gate that defaulted an unknown type to admitted would pass this, and would go
    on passing it after somebody added a DTO carrying server truth into the
    protocol. The refusal distinguishes the two cases a reader cares about: a
    message type this build does not know is not the same finding as a management
    DTO doing its job.
    """

    decision = admit_to_cognition("minekin.v1.ServerEntitySnapshot")

    assert decision.admitted is False
    assert decision.refusal is CognitionRefusal.UNCLASSIFIED_DTO
    assert decision.information_class is None
    assert classify_dto("minekin.v1.ServerEntitySnapshot") is None


def test_a_command_is_not_a_dto_and_is_refused_at_the_dto_seam() -> None:
    """The table is inbound DTOs, not "every message in the protocol".

    `ConnectWorld` is real, generated and correctly spelled — and it is a command
    Core sends, not something the Bridge reports. Routing it through the DTO gate
    must refuse rather than find a class for it, or the table would slowly become a
    list of types somebody recognised.
    """

    decision = admit_to_cognition("minekin.v1.ConnectWorld")

    assert decision.refusal is CognitionRefusal.UNCLASSIFIED_DTO


def test_no_product_message_type_is_a_test_oracle() -> None:
    """The oracle class exists for the vocabulary and for evidence, not for the wire.

    Ground truth about a synthetic world has no message type in this protocol, and
    the refusal branch is still exercised — by the table, below — because the day a
    type is classified `TEST_ORACLE` by mistake is the day that branch is the only
    thing standing between it and the Kin.
    """

    assert InformationClass.TEST_ORACLE not in DTO_INFORMATION_CLASSES.values()
    assert InformationClass.TEST_ORACLE.enters_cognition is False


def test_an_oracle_classified_type_is_refused_rather_than_routed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The branch above, exercised: a table mistake is refused, not obeyed."""

    monkeypatch.setitem(DTO_INFORMATION_CLASSES, INITIAL_OBSERVATION, InformationClass.TEST_ORACLE)

    decision = admit_to_cognition(INITIAL_OBSERVATION)

    assert decision.admitted is False
    assert decision.refusal is CognitionRefusal.TEST_ORACLE_DTO


# ---------------------------------------------------------------------------
# The table against the layer that carries these messages
# ---------------------------------------------------------------------------


def test_every_inbound_dto_carries_exactly_one_class() -> None:
    """The contract's "every DTO", checked against the IPC layer's own event set.

    Both directions, because the two failures are different: a type with no class
    is one nobody decided about, and a class with no type is a decision left behind
    by a message that was removed. The second is the one that rots quietly.
    """

    inbound = set(INBOUND_EVENT_TYPES)

    assert inbound - set(DTO_INFORMATION_CLASSES) == set(), "an inbound DTO has no class"
    assert set(DTO_INFORMATION_CLASSES) - inbound == set(), "a class outlived its message"
    assert set(DTO_INFORMATION_CLASSES) == set(REVIEWED_CLASSES)
    for message_type, information_class in DTO_INFORMATION_CLASSES.items():
        assert classify_dto(message_type) is information_class


def test_the_reviewed_classes_are_the_ones_this_build_decides() -> None:
    """The decisions themselves, spelled out, one assertion per message type.

    Derived from the same table the module publishes, so the failure this catches
    is a *change* to a class rather than a discrepancy — which is the thing a
    reviewer needs to see, because reclassifying a DTO is how server truth would
    enter the Kin's world without a single line of routing code changing.
    """

    assert {message_type: classify_dto(message_type) for message_type in REVIEWED_CLASSES} == (
        REVIEWED_CLASSES
    )


def test_admission_follows_the_class_and_nothing_else() -> None:
    """The property the module exists for, over every message type it knows.

    Written as a comparison against `enters_cognition` rather than as a list of
    expected answers, so that it keeps testing the rule when the table changes
    rather than testing the table against itself.
    """

    for message_type, information_class in DTO_INFORMATION_CLASSES.items():
        decision = admit_to_cognition(message_type)

        assert decision.admitted is information_class.enters_cognition, message_type
        assert decision.information_class is information_class
        assert (decision.refusal is None) is decision.admitted


def test_a_decision_is_evidence_ready() -> None:
    """Every refusal is a reason code in the run, so it has to serialize."""

    admitted = admit_to_cognition(INITIAL_OBSERVATION).as_document()
    refused = admit_to_cognition(HOST_LIFECYCLE).as_document()

    assert admitted == {
        "admitted": True,
        "information_class": "PLAYER_EQUIVALENT",
        "refusal": None,
    }
    assert refused == {
        "admitted": False,
        "information_class": "MANAGEMENT_ONLY",
        "refusal": "MANAGEMENT_ONLY_DTO",
    }
