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
