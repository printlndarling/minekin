"""The HurtObserved row one reading owes: the client's own record, as it read it.

`_hurt_record` is the single place a hurt reading becomes a ledger row, so its
cells pin the whole rule: the payload is the reading verbatim plus the tick,
a record that was no entity still owes a row (the honest damage kind), and an
absent/fresh-less record owes nothing rather than a zeroed attacker.
"""

from __future__ import annotations

from minekin_core.adapters.bridge.world_observation import decode_world_observation
from minekin_core.cli.session import _hurt_record  # pyright: ignore[reportPrivateUsage]
from minekin_core.generated.minekin.v1 import observation_pb2


def wire() -> observation_pb2.WorldObservation:
    return observation_pb2.WorldObservation(
        generation=1,
        game_tick=100,
        self=observation_pb2.SelfState(
            health=20.0, max_health=20.0, food=20, saturation=5.0, alive=True
        ),
        inventory=observation_pb2.InventorySummary(revision=100),
    )


def test_a_fresh_hurt_record_becomes_the_rows_payload_verbatim() -> None:
    message = wire()
    message.hurt.CopyFrom(
        observation_pb2.HurtSource(
            attacker_observation_id="f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2",
            attacker_type="minecraft:player",
            source_type="player_attack",
        )
    )

    assert _hurt_record(decode_world_observation(message)) == {
        "attacker_observation_id": "f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2",
        "attacker_type": "minecraft:player",
        "source_type": "player_attack",
        "game_tick": 100,
    }


def test_no_record_owes_no_row_and_a_non_entity_hurt_still_owes_one() -> None:
    assert _hurt_record(decode_world_observation(wire())) is None

    body = wire()
    body.hurt.CopyFrom(observation_pb2.HurtSource(source_type="fall"))
    record = _hurt_record(decode_world_observation(body))

    assert record is not None
    assert record["source_type"] == "fall"
    assert record["attacker_type"] == ""
