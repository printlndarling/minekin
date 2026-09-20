"""The wire a host command arrives on, and what it is not allowed to carry.

The host boundary contract's policy for a Kin's own world is survival, non-hardcore,
normal difficulty and no commands, and publishing a world grants the last of those:
measured against 1.21.4, the client's own call raises the host player's permission
level and allows cheats. So the command has no field for either, and that absence is
asserted here rather than trusted — it is the same rule as the Bridge adapter passing
`false`, stated where a schema change would have to face it.
"""

from __future__ import annotations

import pytest

from minekin_core.adapters.bridge.ipc import (
    CONNECT_WORLD_TYPE,
    HOST_LAN_CAPABILITY,
    HOST_LIFECYCLE_TYPE,
    OPEN_LAN_TYPE,
    BridgeSession,
)
from minekin_core.generated.minekin.v1 import control_pb2, observation_pb2

DIGEST = "a" * 64


def _session() -> BridgeSession:
    return BridgeSession(
        kin_id="kin-1",
        session_id="session-1",
        generation=1,
        client_instance_id="client-1",
        bundle_digest=DIGEST,
        bridge_digest=DIGEST,
        launch_nonce=b"\x00" * 32,
        session_key=b"\x01" * 32,
    )


def test_the_message_type_names_are_the_generated_ones() -> None:
    """A type string is a wire name; a typo in one is a command that is never read."""

    assert control_pb2.OpenLan.DESCRIPTOR.full_name == OPEN_LAN_TYPE
    assert observation_pb2.HostLifecycle.DESCRIPTOR.full_name == HOST_LIFECYCLE_TYPE


def test_a_session_advertises_the_capability_by_default() -> None:
    assert HOST_LAN_CAPABILITY in _session().capabilities
    assert HOST_LAN_CAPABILITY == "host.lan.v1"


def test_the_command_cannot_ask_for_cheats_or_a_game_mode() -> None:
    """The rule is a missing field, not a value somebody has to remember to refuse.

    Publishing a world grants commands and a permission level. A field asking for
    either would move the decision from the adapter, where it is `false` by
    construction, to whoever builds the message.
    """

    fields = set(control_pb2.OpenLan.DESCRIPTOR.fields_by_name)

    assert fields == {"request_id", "generation", "port", "deadline_monotonic_ns"}
    assert not [name for name in fields if "cheat" in name or "command" in name]
    assert not [name for name in fields if "mode" in name]


def test_the_event_carries_the_contracts_two_phases_and_no_invented_third() -> None:
    """The contract's host event set is `LAN_OPENED` and `LAN_OPEN_FAILED`.

    A reason for a failure belongs in the Bridge's own log, where the contract puts
    it, so the wire carries the outcome and one address.
    """

    values = observation_pb2.HostPhase.keys()

    assert values == [
        "HOST_PHASE_UNSPECIFIED",
        "HOST_PHASE_LAN_OPENED",
        "HOST_PHASE_LAN_OPEN_FAILED",
    ]
    assert set(observation_pb2.HostLifecycle.DESCRIPTOR.fields_by_name) == {
        "request_id",
        "generation",
        "phase",
        "bound_port",
    }


def test_the_two_commands_that_can_reach_a_world_are_the_two_that_were_reviewed() -> None:
    """A guard on this file's own subject: the wire's world-facing commands.

    `OpenLan` publishes the world the Kin is already in and `ConnectWorld` asks for
    another one; nothing else on this channel may name a world, so a third message
    that did would have to be added here first.
    """

    world_facing = {
        name
        for name in control_pb2.DESCRIPTOR.message_types_by_name
        if "World" in name or "Lan" in name
    }

    assert world_facing == {"ConnectWorld", "OpenLan"}
    assert CONNECT_WORLD_TYPE == "minekin.v1.ConnectWorld"


@pytest.mark.parametrize("port", [0, 25565])
def test_the_requested_port_is_a_number_and_never_a_booleans_worth(port: int) -> None:
    """`0` means "let the system choose" and is therefore a value, not an absence."""

    command = control_pb2.OpenLan(request_id="r-1", generation=1, port=port)

    assert command.port == port
