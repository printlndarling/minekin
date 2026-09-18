from __future__ import annotations

import hashlib
import uuid

import pytest

from minekin_core.domain.ids import OpaqueId
from minekin_core.domain.offline_identity import (
    CREDENTIAL_KIND,
    IDENTITY_SCHEMA,
    UUID_ALGORITHM,
    OfflineIdentityMaterial,
    offline_player_uuid,
)

# Ground truth printed by a JDK 17 `UUID.nameUUIDFromBytes(("OfflinePlayer:" +
# name).getBytes(UTF_8))`, which is the call 1.21.4 Uuids.getOfflinePlayerUuid
# makes. These are the values a server will therefore see.
JAVA_OFFLINE_UUIDS = {
    "Kin": ("8f40376b-c23f-3ef1-b553-5564eea75639", "8f40376bc23f3ef1b5535564eea75639"),
    "Notch": ("b50ad385-829d-3141-a216-7e7d7539ba7f", "b50ad385829d3141a2167e7d7539ba7f"),
    "kin": ("4cb8d514-fcbf-3052-a646-495046c5be21", "4cb8d514fcbf3052a646495046c5be21"),
    "player_1": ("6c3d9295-0473-3ed5-ab9c-cb5aa7c56f4d", "6c3d929504733ed5ab9ccb5aa7c56f4d"),
    "ABCDEFGHIJKLMNOP": (
        "2b74a1cc-0832-35db-8638-abf7e029466d",
        "2b74a1cc083235db8638abf7e029466d",
    ),
}


@pytest.mark.parametrize(("username", "expected"), JAVA_OFFLINE_UUIDS.items())
def test_offline_uuid_reproduces_the_java_name_uuid(
    username: str, expected: tuple[str, str]
) -> None:
    assert str(offline_player_uuid(username)) == expected[0]
    assert offline_player_uuid(username).hex == expected[1]


def test_offline_uuid_is_the_ietf_name_variant() -> None:
    value = offline_player_uuid("Kin")

    assert value.version == 3
    assert value.variant == uuid.RFC_4122


def test_offline_uuid_only_differs_by_case_when_the_name_does() -> None:
    assert offline_player_uuid("Kin") != offline_player_uuid("kin")


def _name_uuid(payload: bytes) -> uuid.UUID:
    """Java's UUID.nameUUIDFromBytes, to cross-check how Python sets the bits."""

    return uuid.UUID(bytes=hashlib.md5(payload, usedforsecurity=False).digest(), version=3)


def test_offline_uuid_agrees_with_the_standard_name_uuid() -> None:
    # uuid3(namespace, name) is nameUUIDFromBytes(namespace.bytes + name), so both
    # constructions must agree on identical bytes.
    payload = uuid.NAMESPACE_OID.bytes + b"minekin"

    assert _name_uuid(payload) == uuid.uuid3(uuid.NAMESPACE_OID, "minekin")


def material(username: str = "Kin") -> OfflineIdentityMaterial:
    return OfflineIdentityMaterial(
        local_profile_id=OpaqueId("kin-01"),
        identity_revision=1,
        username=username,
        created_at="2026-09-19T00:00:00Z",
    )


def test_material_document_matches_the_frozen_offline_identity_schema() -> None:
    document = material().as_document()

    assert document == {
        "schema": IDENTITY_SCHEMA,
        "local_profile_id": "kin-01",
        "identity_revision": 1,
        "username": "Kin",
        "uuid_algorithm": UUID_ALGORITHM,
        "uuid_canonical": "8f40376b-c23f-3ef1-b553-5564eea75639",
        "uuid_id128": "8f40376bc23f3ef1b5535564eea75639",
        "credential_kind": CREDENTIAL_KIND,
        "access_token_sentinel": "0",
        "created_at": "2026-09-19T00:00:00Z",
    }


def test_material_document_carries_no_credential_body() -> None:
    document = material().as_document()

    assert document["credential_kind"] == "offline-sentinel"
    assert document["access_token_sentinel"] == "0"
    assert "access_token" not in document


@pytest.mark.parametrize("username", ["ab", "waytoolongforvanilla", "with-dash", "with space", ""])
def test_material_rejects_usernames_the_vanilla_server_would_refuse(username: str) -> None:
    with pytest.raises(ValueError, match="vanilla"):
        material(username)


def test_material_rejects_a_non_positive_identity_revision() -> None:
    with pytest.raises(ValueError, match="identity_revision"):
        OfflineIdentityMaterial(
            local_profile_id=OpaqueId("kin-01"),
            identity_revision=0,
            username="Kin",
            created_at="2026-09-19T00:00:00Z",
        )
