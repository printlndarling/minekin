"""What a run asks for, as a lease and a set of commands.

The plan is where "which input" and "what authorises it" meet, so these are the
rules that decide what a run sends and what it is allowed to send it under.
"""

from __future__ import annotations

from typing import cast

from minekin_core.adapters.bridge.ipc import (
    LOOK_CAPABILITY,
    LOOK_INPUT_TYPE,
    MOVE_CAPABILITY,
    MOVE_INPUT_TYPE,
    USE_CAPABILITY,
    USE_INPUT_TYPE,
)
from minekin_core.cli.session import DEFAULT_LOOK_LEASE_S, InputPlan
from minekin_core.domain.ids import Generation
from minekin_core.domain.input_control import InputLease, InputPriority
from minekin_core.generated.minekin.v1 import control_pb2

GENERATION = Generation(1)
DEADLINE = 5_000_000_000


def lease() -> InputLease:
    return InputLease(
        lease_id="lease-1",
        generation=GENERATION,
        client_instance_id="client-1",
        issued_monotonic_ns=1,
        deadline_monotonic_ns=DEADLINE,
        priority=InputPriority.NORMAL,
        capabilities=frozenset({MOVE_CAPABILITY, LOOK_CAPABILITY, USE_CAPABILITY}),
    )


def test_a_hold_needs_the_movement_capability_and_owns_its_duration() -> None:
    plan = InputPlan(hold_seconds=8.0)

    assert plan.capabilities == frozenset({MOVE_CAPABILITY})
    assert plan.lease_seconds == 8.0


def test_a_look_needs_its_own_capability_and_only_a_moment() -> None:
    plan = InputPlan(look=True, yaw_degrees=90.0)

    # A look is its own capability: a client can be steerable without being
    # turnable, which is the whole reason the negotiation carries both.
    assert plan.capabilities == frozenset({LOOK_CAPABILITY})
    assert plan.lease_seconds == DEFAULT_LOOK_LEASE_S


def test_a_plan_that_asks_for_both_holds_one_lease_covering_both() -> None:
    plan = InputPlan(hold_seconds=3.0, look=True, yaw_degrees=-45.0, pitch_degrees=10.0)

    assert plan.capabilities == frozenset({MOVE_CAPABILITY, LOOK_CAPABILITY})
    assert plan.lease_seconds == 3.0


def test_a_plan_that_asks_for_nothing_sends_nothing() -> None:
    assert InputPlan().capabilities == frozenset()
    assert InputPlan().commands(lease(), DEADLINE) == []


def test_a_hold_becomes_one_movement_command_carrying_the_lease() -> None:
    plan = InputPlan(hold_seconds=8.0)
    plan.action_id = "action-1"

    commands = plan.commands(lease(), DEADLINE)

    assert [name for _, name, _ in commands] == [MOVE_INPUT_TYPE]
    capability, _, raw = commands[0]
    # Cast because the plan carries protobuf messages generically; the test is
    # the place that knows which kind it asked for.
    message = cast(control_pb2.MoveInput, raw)
    assert capability == MOVE_CAPABILITY
    assert message.action_id == "action-1"
    assert message.lease_id == "lease-1"
    assert message.generation == 1
    assert message.forward == 1.0
    assert message.deadline_monotonic_ns == DEADLINE


def test_a_look_becomes_one_look_command_with_the_degrees_it_was_given() -> None:
    plan = InputPlan(look=True, yaw_degrees=90.0, pitch_degrees=-15.0)
    plan.action_id = "action-2"

    commands = plan.commands(lease(), DEADLINE)

    assert [name for _, name, _ in commands] == [LOOK_INPUT_TYPE]
    capability, _, raw = commands[0]
    message = cast(control_pb2.LookInput, raw)
    assert capability == LOOK_CAPABILITY
    assert message.action_id == "action-2"
    assert message.delta_yaw_degrees == 90.0
    assert message.delta_pitch_degrees == -15.0


def test_both_kinds_are_two_commands_under_one_lease_in_a_stable_order() -> None:
    plan = InputPlan(hold_seconds=8.0, look=True, yaw_degrees=90.0)
    plan.action_id = "action-3"

    commands = plan.commands(lease(), DEADLINE)

    assert [name for _, name, _ in commands] == [MOVE_INPUT_TYPE, LOOK_INPUT_TYPE]
    move = cast(control_pb2.MoveInput, commands[0][2])
    look = cast(control_pb2.LookInput, commands[1][2])
    assert move.lease_id == look.lease_id == "lease-1"


def test_the_axes_a_hold_asks_for_travel_on_the_command() -> None:
    """Each name is a field of MoveInput, so what a run holds is what it sends."""

    plan = InputPlan(hold_seconds=4.0, strafe=-1.0, jump=True, sneak=False)
    plan.action_id = "action-4"

    commands = plan.commands(lease(), DEADLINE)

    move = cast(control_pb2.MoveInput, commands[0][2])
    assert move.forward == 1.0
    assert move.strafe == -1.0
    assert move.jump is True
    assert move.sneak is False


def test_a_use_needs_its_own_capability_and_is_a_hold_like_the_others() -> None:
    """Using something is holding a key, so what ends it is the lease."""
    plan = InputPlan(use_seconds=4.0)

    assert plan.capabilities == frozenset({USE_CAPABILITY})
    assert plan.lease_seconds == 4.0


def test_a_use_becomes_one_use_command_carrying_the_lease() -> None:
    plan = InputPlan(use_seconds=4.0)
    plan.action_id = "action-1"

    commands = plan.commands(lease(), DEADLINE)

    assert [name for _, name, _ in commands] == [USE_INPUT_TYPE]
    capability, _, raw = commands[0]
    message = cast(control_pb2.UseInput, raw)
    assert capability == USE_CAPABILITY
    assert message.action_id == "action-1"
    assert message.lease_id == "lease-1"
    assert message.generation == 1
    assert message.use is True
    assert message.deadline_monotonic_ns == DEADLINE


def test_one_lease_covers_every_ask_and_lasts_as_long_as_the_longest() -> None:
    """A lease that lapsed before the use did would take back a wanted key."""
    plan = InputPlan(hold_seconds=2.0, use_seconds=6.0)

    assert plan.capabilities == frozenset({MOVE_CAPABILITY, USE_CAPABILITY})
    assert plan.lease_seconds == 6.0
    assert [name for _, name, _ in plan.commands(lease(), DEADLINE)] == [
        MOVE_INPUT_TYPE,
        USE_INPUT_TYPE,
    ]


def test_a_run_may_ask_to_use_its_hands_without_going_anywhere() -> None:
    plan = InputPlan(use_seconds=1.0)

    assert plan.hold_seconds is None
    assert plan.capabilities == frozenset({USE_CAPABILITY})
