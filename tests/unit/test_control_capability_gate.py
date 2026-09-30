"""The §1 capability registration and the named refusal, testable without a Bridge.

`CAPABILITY_NOT_GRANTED` is the word the S2 contract gives both gates — Core's
sender and the Bridge's receiver — and a shared word is only real if the same
string comes out of the same decision here that comes out of the client's
`HandshakeGate` there. So this file is the Python half of that pair: the table
that maps each control type to its capability, the pure check, and the exception
`send_control` raises from it. No transport, no loopback peer: the refusal is
testable precisely because `check_control_capability` was factored out to be
called before any frame is written.
"""

from __future__ import annotations

import pytest

from minekin_core.adapters.bridge.ipc import (
    ADMISSION_CAPABILITY,
    AIM_CAPABILITY,
    AIM_INPUT_TYPE,
    CAPABILITY_NOT_GRANTED,
    CONNECT_WORLD_TYPE,
    CORE_HELLO_TYPE,
    GUI_CAPABILITY,
    GUI_CLICK_INPUT_TYPE,
    HEARTBEAT_TYPE,
    HOTBAR_CAPABILITY,
    HOTBAR_SELECT_INPUT_TYPE,
    INBOUND_EVENT_TYPES,
    LOOK_CAPABILITY,
    MINE_CAPABILITY,
    MINE_INPUT_TYPE,
    MOVE_CAPABILITY,
    OBSERVE_WORLD_CAPABILITY,
    SCREEN_CAPABILITY,
    SCREEN_INPUT_TYPE,
    WORLD_OBSERVATION_TYPE,
    CapabilityNotGranted,
    check_control_capability,
)
from minekin_core.domain.information_class import (
    DTO_INFORMATION_CLASSES,
    InformationClass,
)

#: Each S2 control type with exactly the capability §1 names for it. Written out
#: rather than derived from the module's table, so a renamed or repointed
#: capability has to be changed twice and a reviewer sees both.
S2_CONTROL_GATE = {
    AIM_INPUT_TYPE: AIM_CAPABILITY,
    MINE_INPUT_TYPE: MINE_CAPABILITY,
    HOTBAR_SELECT_INPUT_TYPE: HOTBAR_CAPABILITY,
    SCREEN_INPUT_TYPE: SCREEN_CAPABILITY,
    GUI_CLICK_INPUT_TYPE: GUI_CAPABILITY,
}
S2_CAPABILITY_NAMES = {
    "control.aim.v1",
    "control.mine.v1",
    "control.hotbar.v1",
    "control.screen.v1",
    "control.gui.v1",
    "observe.world.v1",
}


@pytest.mark.parametrize(("message_type", "capability"), sorted(S2_CONTROL_GATE.items()))
def test_each_s2_control_refuses_without_its_capability(message_type: str, capability: str) -> None:
    """The named refusal per capability, with the old set as the granted side.

    The granted collection deliberately holds only what S1 negotiated: every S2
    verb must refuse against the same set, because a gate that opens for the
    message types someone remembered is the `KeyError`-shaped forgetting this
    table exists to end.
    """

    granted_s1 = frozenset({ADMISSION_CAPABILITY, MOVE_CAPABILITY, LOOK_CAPABILITY})

    assert check_control_capability(granted_s1, message_type) == capability


@pytest.mark.parametrize(("message_type", "capability"), sorted(S2_CONTROL_GATE.items()))
def test_each_s2_control_passes_once_its_capability_is_granted(
    message_type: str, capability: str
) -> None:
    assert check_control_capability(frozenset({capability}), message_type) is None


def test_the_refusal_is_named_and_testable_without_a_live_bridge() -> None:
    """The exception carries the word, the type and the capability.

    Asserted against the pure check rather than a socket because the contract's
    point is that a run can prove the gate refused, not that it happened to be
    mid-handshake when it did.
    """

    refused = check_control_capability(frozenset(), AIM_INPUT_TYPE)
    assert refused == AIM_CAPABILITY
    with pytest.raises(CapabilityNotGranted) as caught:
        raise CapabilityNotGranted(AIM_INPUT_TYPE, refused)

    assert caught.value.reason_code == CAPABILITY_NOT_GRANTED
    assert caught.value.message_type == AIM_INPUT_TYPE
    assert caught.value.capability == AIM_CAPABILITY
    assert CAPABILITY_NOT_GRANTED in str(caught.value)
    assert AIM_CAPABILITY in str(caught.value)


def test_the_s2_vocabulary_is_spelled_exactly_as_the_contract_names_it() -> None:
    """Stable strings, written out here a second time, because the Java gate is
    keyed on these exact spellings and a silent re-wording would negotiate two
    disjoint vocabularies that both type-check."""

    assert {
        AIM_CAPABILITY,
        MINE_CAPABILITY,
        HOTBAR_CAPABILITY,
        SCREEN_CAPABILITY,
        GUI_CAPABILITY,
        OBSERVE_WORLD_CAPABILITY,
    } == S2_CAPABILITY_NAMES


def test_the_recurring_observation_is_a_registered_inbound_event() -> None:
    assert WORLD_OBSERVATION_TYPE == "minekin.v1.WorldObservation"
    assert WORLD_OBSERVATION_TYPE in INBOUND_EVENT_TYPES
    assert DTO_INFORMATION_CLASSES[WORLD_OBSERVATION_TYPE] is InformationClass.PLAYER_EQUIVALENT


def test_types_without_a_capability_gate_are_not_refused() -> None:
    """Release, heartbeat and the hello are ungated by design: the release must
    work even after the grant lapses, and a table that refused it would be a Kin
    still holding the attack key."""

    everything: frozenset[str] = frozenset()
    assert check_control_capability(everything, HEARTBEAT_TYPE) is None
    assert check_control_capability(everything, CORE_HELLO_TYPE) is None
    # A connect command still gates on the admission capability even though S1
    # built it: the pair that must keep refusing is the new and the old alike.
    assert check_control_capability(everything, CONNECT_WORLD_TYPE) == ADMISSION_CAPABILITY
