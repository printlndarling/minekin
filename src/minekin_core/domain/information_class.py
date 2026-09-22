"""Which information may reach the Kin's own mind, and which may not.

The hosted-world control boundary contract's third gate: every DTO carries an
`information_class` of `PLAYER_EQUIVALENT`, `MANAGEMENT_ONLY` or `TEST_ORACLE`,
and only the first may enter the cognition path. This module is that gate.

It is a third axis, and not a reuse of the two the envelope already carries.
`EventSource` says who produced a payload and `TrustClass` says how much of it is
admissible; neither answers the question this gate asks, which is what a payload
*lets its reader know*. A management-only DTO from the most trusted producer in
the system is still management-only — that is the whole point of the case the
contract names for it (`HOSTCTL-070`): host-control may read server truth in order
to manage the world, so its output must not become the Kin's own model of the
world no matter how trustworthy the sender is.

**The class belongs to the message type and is decided by the reader.** The
contract's sentence is that a DTO "carries" the class, and the obvious reading is
a field — but a field is set by the sender, and the sender is the side the case
says must not be trusted with this decision. A class the management side grades
its own output with is not a control; it is a comment. So the class lives here, in
a table keyed by message type, and a message whose type is not in it is refused
rather than defaulted. Adding an inbound DTO therefore forces a decision here —
which is the property the contract is after, and the reason
`tests/unit/test_information_class.py` binds this table to the IPC layer's own
`_EVENT_TYPES` in both directions.

If the wire ever does need to carry the class — for a consumer outside this
repository, or for the Dashboard — the field must be *checked against this table*
and never believed, the same rule the envelope's `trust_class` already lives under.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

#: The message types the Bridge may report to Core, spelled as the wire spells
#: them. The IPC layer names the same types; the test that binds the two is what
#: keeps the two spellings from drifting apart, rather than one importing the
#: other, because the domain does not import the wire's generated modules.
CONNECTION_LIFECYCLE: Final = "minekin.v1.ConnectionLifecycle"
INITIAL_OBSERVATION: Final = "minekin.v1.InitialObservation"
HOST_LIFECYCLE: Final = "minekin.v1.HostLifecycle"
ACTION_RESULT: Final = "minekin.v1.ActionResult"
BUDGET_WINDOW: Final = "minekin.v1.CallbackBudgetWindow"


class InformationClass(StrEnum):
    """What a payload lets its reader know."""

    #: What the Kin could have learned by playing: its own client's view of the
    #: world, its own connection, the disposition of its own actions. The only
    #: class that may reach the Kin's own mind.
    PLAYER_EQUIVALENT = "PLAYER_EQUIVALENT"
    #: What the control side knows because it manages the world — hosting
    #: machinery, lifecycle and publication. Not the Kin's model of the world.
    MANAGEMENT_ONLY = "MANAGEMENT_ONLY"
    #: Ground truth about a synthetic world. Valid in isolated test evidence and
    #: nowhere else, which is why no product message type is ever this class.
    TEST_ORACLE = "TEST_ORACLE"

    @property
    def enters_cognition(self) -> bool:
        """Whether information of this class may reach the Kin's own mind."""

        return self is InformationClass.PLAYER_EQUIVALENT


#: The class of every DTO the Bridge may report, decided one message type at a
#: time and deliberately not derived from anything. A new inbound type is a new
#: decision, and the totality test is what turns forgetting to make it into a
#: failing test rather than a quiet default.
#:
#: The three player-equivalent entries carry no world state: a connection phase,
#: a snapshot already filtered by `domain/perception.py`, and the disposition of
#: the Kin's own action. The two management-only entries are the control side's
#: reports about the machinery — the hosting status of a world, and how long the
#: Bridge's own callbacks took. The Kin meets the world it hosts by being in it, and
#: it meets its own client's cost by the client being fast, not by reading either.
DTO_INFORMATION_CLASSES: Final[dict[str, InformationClass]] = {
    CONNECTION_LIFECYCLE: InformationClass.PLAYER_EQUIVALENT,
    INITIAL_OBSERVATION: InformationClass.PLAYER_EQUIVALENT,
    ACTION_RESULT: InformationClass.PLAYER_EQUIVALENT,
    HOST_LIFECYCLE: InformationClass.MANAGEMENT_ONLY,
    BUDGET_WINDOW: InformationClass.MANAGEMENT_ONLY,
}


class CognitionRefusal(StrEnum):
    """Why something that arrived was not admitted to the Kin's cognition path."""

    #: A message type this gate has no class for. Refused rather than assumed to
    #: be harmless: the failure mode of defaulting is a management DTO entering
    #: the mind the day somebody adds one, and nothing would report it.
    UNCLASSIFIED_DTO = "UNCLASSIFIED_DTO"
    MANAGEMENT_ONLY_DTO = "MANAGEMENT_ONLY_DTO"
    TEST_ORACLE_DTO = "TEST_ORACLE_DTO"


@dataclass(frozen=True, slots=True)
class CognitionDecision:
    """The gate's answer about one payload, and the class it was answered from."""

    admitted: bool
    information_class: InformationClass | None
    refusal: CognitionRefusal | None

    def as_document(self) -> dict[str, object]:
        return {
            "admitted": self.admitted,
            "information_class": (
                None if self.information_class is None else self.information_class.value
            ),
            "refusal": None if self.refusal is None else self.refusal.value,
        }


def classify_dto(message_type: str) -> InformationClass | None:
    """The class of a DTO, or `None` when this gate has never heard of it."""

    return DTO_INFORMATION_CLASSES.get(message_type)


def admit_to_cognition(message_type: str) -> CognitionDecision:
    """Decide whether a payload of this type may enter the Kin's cognition path.

    The refusal names the class rather than saying "not admitted", because the two
    refusals mean different things to whoever reads the run: a management-only DTO
    arriving is the control side doing its job, while an unclassified one arriving
    means something is speaking a protocol this build does not know.
    """

    information_class = classify_dto(message_type)
    if information_class is None:
        return CognitionDecision(False, None, CognitionRefusal.UNCLASSIFIED_DTO)
    if information_class is InformationClass.MANAGEMENT_ONLY:
        return CognitionDecision(False, information_class, CognitionRefusal.MANAGEMENT_ONLY_DTO)
    if information_class is InformationClass.TEST_ORACLE:
        return CognitionDecision(False, information_class, CognitionRefusal.TEST_ORACLE_DTO)
    return CognitionDecision(True, information_class, None)
