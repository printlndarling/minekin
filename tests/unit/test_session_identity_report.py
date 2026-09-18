"""The Bridge's session report must be structurally unable to carry a credential.

protobuf-javalite does not ship `Descriptors`, so the shape of the message is
asserted here against the descriptor the product actually ships.
"""

from __future__ import annotations

from google.protobuf.descriptor import FieldDescriptor

from minekin_core.generated.minekin.v1 import observation_pb2, session_pb2

REVIEWED_FIELDS = {
    "identity_candidate_id": FieldDescriptor.TYPE_STRING,
    "session_username": FieldDescriptor.TYPE_STRING,
    "session_uuid": FieldDescriptor.TYPE_STRING,
    "session_account_type": FieldDescriptor.TYPE_STRING,
    "session_xuid_present": FieldDescriptor.TYPE_BOOL,
    "session_client_id_present": FieldDescriptor.TYPE_BOOL,
    "credential_values_exposed": FieldDescriptor.TYPE_BOOL,
}


def test_the_session_report_has_exactly_the_reviewed_fields() -> None:
    descriptor = session_pb2.SessionIdentityReport.DESCRIPTOR

    assert {field.name: field.type for field in descriptor.fields} == REVIEWED_FIELDS


def test_the_session_report_has_no_place_to_put_a_credential_body() -> None:
    descriptor = session_pb2.SessionIdentityReport.DESCRIPTOR

    # A bytes field is the only way a token body could be embedded, and the
    # report has none by construction rather than by a filter.
    assert not [field for field in descriptor.fields if field.type == FieldDescriptor.TYPE_BYTES]


def test_the_report_is_reachable_from_the_hello_and_the_first_snapshot() -> None:
    report = session_pb2.SessionIdentityReport.DESCRIPTOR

    hello = session_pb2.BridgeHello.DESCRIPTOR.fields_by_name["session_identity"]
    snapshot = observation_pb2.InitialObservation.DESCRIPTOR.fields_by_name["session_identity"]

    assert hello.message_type is report
    assert snapshot.message_type is report


def test_the_report_round_trips_without_credential_values() -> None:
    report = session_pb2.SessionIdentityReport(
        identity_candidate_id="prism-parity",
        session_username="Kin",
        session_uuid="8f40376bc23f3ef1b5535564eea75639",
        session_account_type="offline",
        session_xuid_present=True,
        session_client_id_present=True,
        credential_values_exposed=False,
    )

    decoded = session_pb2.SessionIdentityReport.FromString(report.SerializeToString())

    assert decoded == report
    assert decoded.credential_values_exposed is False
    assert decoded.DESCRIPTOR.full_name == "minekin.v1.SessionIdentityReport"


def test_the_hello_keeps_its_w20_fields_when_the_report_is_added() -> None:
    """Adding field 14 must not renumber or drop anything the handshake already used."""

    fields = session_pb2.BridgeHello.DESCRIPTOR.fields_by_name

    assert fields["session_identity"].number == 14
    assert fields["phase"].number == 13
    assert fields["capabilities"].number == 12
    assert {name for name in fields} >= {
        "protocol",
        "launch_nonce",
        "proof",
        "kin_id",
        "session_id",
        "generation",
        "client_instance_id",
        "bundle_digest",
        "bridge_digest",
        "minecraft_version",
        "fabric_loader_version",
    }
