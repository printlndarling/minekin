"""The observation schema must have nowhere for server truth to live.

A filter can only be bypassed by a field it forgets to check, so these tests
assert the *shape* of the messages rather than the behaviour of any function.
"""

from __future__ import annotations

import json
from pathlib import Path

from minekin_core.generated.minekin.v1 import observation_pb2

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANARY = REPOSITORY_ROOT / "tests" / "oracle" / "canary.json"
PRODUCT_PACKAGE = REPOSITORY_ROOT / "src" / "minekin_core"
PRODUCT_INPUT = REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input"

OBSERVATION_MESSAGES = (
    observation_pb2.SelfState,
    observation_pb2.InventoryStack,
    observation_pb2.InventorySummary,
    observation_pb2.VisibleEntity,
    observation_pb2.InitialObservation,
)

# Concepts a player cannot read off the screen. A field whose name mentions one
# of these is a boundary regression whether or not anything writes to it yet.
FORBIDDEN_FIELD_MARKERS = (
    "seed",
    "container",
    "chest",
    "shulker",
    "server",
    "save",
    "chunk",
    "ore",
    "block_state",
    "blockstate",
    "absolute",
    "world_pos",
    "other_player",
)

REVIEWED_OBSERVATION_FIELDS = {
    "generation",
    "game_tick",
    "self",
    "inventory",
    "visible_entities",
    "authoritative",
    "session_identity",
}

REVIEWED_ENTITY_FIELDS = {
    "observation_id",
    "entity_type",
    "relative_x",
    "relative_y",
    "relative_z",
    "line_of_sight",
}


def canary_value() -> str:
    document = json.loads(CANARY.read_bytes())
    value = document["canary"]
    assert isinstance(value, str) and value
    return value


def test_the_first_snapshot_has_exactly_the_reviewed_fields() -> None:
    descriptor = observation_pb2.InitialObservation.DESCRIPTOR

    assert {field.name for field in descriptor.fields} == REVIEWED_OBSERVATION_FIELDS


def test_a_visible_entity_has_exactly_the_reviewed_fields() -> None:
    descriptor = observation_pb2.VisibleEntity.DESCRIPTOR

    assert {field.name for field in descriptor.fields} == REVIEWED_ENTITY_FIELDS


def test_no_observation_field_names_a_concept_a_player_cannot_see() -> None:
    offenders = [
        f"{message.DESCRIPTOR.name}.{field.name}"
        for message in OBSERVATION_MESSAGES
        for field in message.DESCRIPTOR.fields
        if any(marker in field.name for marker in FORBIDDEN_FIELD_MARKERS)
    ]

    assert offenders == []


def test_entity_positions_are_only_ever_relative() -> None:
    """A world coordinate would locate every entity against server truth."""

    names = {field.name for field in observation_pb2.VisibleEntity.DESCRIPTOR.fields}

    assert {name for name in names if name.endswith(("_x", "_y", "_z"))} == {
        "relative_x",
        "relative_y",
        "relative_z",
    }


def test_the_oracle_canary_is_absent_from_product_source() -> None:
    canary = canary_value()

    leaks = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in PRODUCT_PACKAGE.rglob("*")
        if path.is_file()
        and not path.name.endswith(".pyc")
        and canary in path.read_text(encoding="utf-8", errors="replace")
    ]

    assert leaks == []


def test_the_oracle_canary_is_absent_from_product_input() -> None:
    """Runtime inputs are product input; the oracle is not one of them."""

    canary = canary_value()

    leaks = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in PRODUCT_INPUT.rglob("*")
        if path.is_file() and canary in path.read_text(encoding="utf-8", errors="replace")
    ]

    assert leaks == []
