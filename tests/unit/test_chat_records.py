"""The ledger rows one reading's chat owes: event types, payloads and trust, as data.

`_chat_records` is the single place a heard line becomes ledger rows, so its
cells pin every row without a live session: one row per line under
`PLAYER_CHAT` (another account's words with attribution), and an omission as
its own row rather than a silently shorter conversation.
"""

from __future__ import annotations

from minekin_core.adapters.bridge.world_observation import decode_world_observation
from minekin_core.adapters.sqlite.session_log import PLAYER_CHAT_OBSERVED, PLAYER_CHAT_OMITTED
from minekin_core.cli.session import _chat_records  # pyright: ignore[reportPrivateUsage]
from minekin_core.domain.events import EventSource, TrustClass
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


def test_a_heard_line_becomes_one_row_under_the_players_own_class() -> None:
    message = wire()
    message.chat.extend(
        [observation_pb2.PlayerChatMessage(game_tick=99, sender="Alex", text="hello")]
    )

    assert _chat_records(decode_world_observation(message)) == [
        (
            PLAYER_CHAT_OBSERVED,
            {"sender": "Alex", "sender_id": "", "own": False, "text": "hello", "game_tick": 99},
            EventSource.BRIDGE,
            TrustClass.PLAYER_CHAT,
        )
    ]


def test_the_account_key_rides_the_row_when_the_client_reported_one() -> None:
    """The stable key is what later memory keys on — names change and repeat —
    so a line that carried one keeps it in the ledger, verbatim."""

    message = wire()
    message.chat.extend(
        [
            observation_pb2.PlayerChatMessage(
                game_tick=99,
                sender="Alex",
                text="hello",
                sender_id="f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2",
            )
        ]
    )

    rows = _chat_records(decode_world_observation(message))

    assert rows[0][1] == {
        "sender": "Alex",
        "sender_id": "f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2",
        "own": False,
        "text": "hello",
        "game_tick": 99,
    }


def test_a_line_from_the_runs_own_account_is_marked_own() -> None:
    """The server echoes words the Kin said; the row says which lines were its own
    voice, comparing canonically — the launcher's dashed spelling and the wire's
    dashless one are the same account."""

    message = wire()
    message.chat.extend(
        [
            observation_pb2.PlayerChatMessage(
                game_tick=99,
                sender="minekin",
                text="hello there",
                sender_id="f84c6a790a4e45e0879bcd49ebd4c4e2",
            ),
            observation_pb2.PlayerChatMessage(
                game_tick=100,
                sender="Alex",
                text="hi back",
                sender_id="11111111-2222-4333-8444-555555555555",
            ),
        ]
    )

    rows = _chat_records(
        decode_world_observation(message),
        "f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2",
    )

    assert [row[1]["own"] for row in rows] == [True, False]


def test_an_omission_becomes_its_own_row_rather_than_a_shorter_conversation() -> None:
    message = wire()
    message.chat_omitted = 5

    assert _chat_records(decode_world_observation(message)) == [
        (
            PLAYER_CHAT_OMITTED,
            {"omitted": 5, "game_tick": 100},
            EventSource.BRIDGE,
            TrustClass.BRIDGE_FILTERED,
        )
    ]


def test_lines_and_an_omission_keep_their_order_the_lines_first() -> None:
    message = wire()
    message.chat.extend(
        [
            observation_pb2.PlayerChatMessage(game_tick=98, sender="Alex", text="one"),
            observation_pb2.PlayerChatMessage(game_tick=99, sender="Steve", text="two"),
        ]
    )
    message.chat_omitted = 3

    rows = _chat_records(decode_world_observation(message))

    assert [row[0] for row in rows] == [
        PLAYER_CHAT_OBSERVED,
        PLAYER_CHAT_OBSERVED,
        PLAYER_CHAT_OMITTED,
    ]
    assert [row[1]["sender"] for row in rows[:-1]] == ["Alex", "Steve"]


def test_a_quiet_reading_owes_no_rows_at_all() -> None:
    assert _chat_records(decode_world_observation(wire())) == []
