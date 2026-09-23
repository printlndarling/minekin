from __future__ import annotations

from pathlib import Path

import pytest

import minekin_core
from minekin_core.generated.minekin.v1 import (
    control_pb2,
    envelope_pb2,
    fault_pb2,
    observation_pb2,
    session_pb2,
)

GENERATED_PACKAGE = Path(minekin_core.__file__).resolve().parent / "generated" / "minekin" / "v1"
GENERATED_MODULES = (control_pb2, envelope_pb2, fault_pb2, observation_pb2, session_pb2)
GENERATED_STEMS = ("control", "envelope", "fault", "observation", "session")

# buf emits `from minekin.v1 import ...`, which resolves inside a buf workspace
# and nowhere else. Every checked-in module must import the product package.
FORBIDDEN_IMPORT_PREFIXES = ("from minekin.", "import minekin.")


def test_generated_envelope_round_trip_preserves_identity() -> None:
    envelope = envelope_pb2.Envelope(
        protocol=envelope_pb2.ProtocolVersion(major=1, minor=0),
        message_type="BridgeHello",
        channel=envelope_pb2.CHANNEL_CONTROL,
        sequence=1,
        kin_id="kin-1",
        client_instance_id="client-1",
        session_id="session-1",
        generation=7,
    )

    decoded = envelope_pb2.Envelope.FromString(envelope.SerializeToString(deterministic=True))

    assert decoded == envelope
    assert decoded.DESCRIPTOR.full_name == "minekin.v1.Envelope"


def test_generated_session_schema_links_envelope_types() -> None:
    descriptor = session_pb2.BridgeBootstrapDescriptor(
        protocol=envelope_pb2.ProtocolVersion(major=1, minor=0),
        kin_id="kin-1",
        session_id="session-1",
        generation=7,
        client_instance_id="client-1",
        launch_nonce=b"n" * 32,
        session_key=b"k" * 32,
        max_frame_bytes=1_048_576,
    )

    decoded = session_pb2.BridgeBootstrapDescriptor.FromString(
        descriptor.SerializeToString(deterministic=True)
    )

    assert decoded.protocol.major == 1
    assert decoded.DESCRIPTOR.file.name == "minekin/v1/session.proto"


def test_connect_world_schema_carries_only_pinned_profile_inputs() -> None:
    fields = control_pb2.ConnectWorld.DESCRIPTOR.fields_by_name

    assert {name: field.number for name, field in fields.items()} == {
        "request_id": 1,
        "generation": 2,
        "server_profile_id": 3,
        "server_profile_revision": 4,
        "original_host": 5,
        "port": 6,
        "resource_pack_policy": 7,
        "deadline_monotonic_ns": 8,
    }
    assert "password" not in fields
    assert "token" not in fields


def test_connection_lifecycle_has_stable_failure_reasons_but_no_server_text() -> None:
    fields = observation_pb2.ConnectionLifecycle.DESCRIPTOR.fields_by_name
    reasons = observation_pb2.AdmissionFailureReason.keys()

    assert {name: field.number for name, field in fields.items()} == {
        "generation": 1,
        "server_profile_id": 2,
        "server_profile_revision": 3,
        "phase": 4,
        "failure_reason": 5,
        "terminal": 6,
        "applied_resource_pack_policy": 7,
    }
    assert "ADMISSION_FAILURE_REASON_WHITELIST_REJECTED" in reasons
    assert "ADMISSION_FAILURE_REASON_RESOURCE_PACK_BLOCKED" in reasons
    assert not {"message", "server_text", "reason_text"} & set(fields)


def test_initial_observation_keeps_management_bindings_out_of_player_state() -> None:
    fields = observation_pb2.InitialObservation.DESCRIPTOR.fields_by_name

    assert not {"server_profile_id", "server_profile_revision", "world_context_id"} & set(fields)


def test_every_frozen_proto_is_importable() -> None:
    assert [module.DESCRIPTOR.name for module in GENERATED_MODULES] == [
        f"minekin/v1/{stem}.proto" for stem in GENERATED_STEMS
    ]


@pytest.mark.parametrize("stem", GENERATED_STEMS)
def test_checked_in_module_imports_only_the_product_package(stem: str) -> None:
    text = (GENERATED_PACKAGE / f"{stem}_pb2.py").read_text(encoding="utf-8")

    assert not [line for line in text.splitlines() if line.startswith(FORBIDDEN_IMPORT_PREFIXES)]


@pytest.mark.parametrize("stem", GENERATED_STEMS)
def test_checked_in_module_ships_a_stub(stem: str) -> None:
    """Without the `.pyi` stub Pyright cannot see the message classes at all."""

    assert (GENERATED_PACKAGE / f"{stem}_pb2.pyi").is_file()
