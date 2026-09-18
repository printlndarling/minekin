"""Offline player identity material.

Minecraft resolves an offline player's UUID with a fixed client-side rule rather
than a server lookup: `Uuids.getOfflinePlayerUuid` is
`UUID.nameUUIDFromBytes(("OfflinePlayer:" + name).getBytes(UTF_8))`, a name-based
version 3 UUID over MD5 with the IETF variant bits set.  Reproducing that rule
byte for byte is what keeps one Kin readable as the same player across restarts,
worlds and servers.

MD5 is mandated by that naming rule. It is not a security control here: nothing
authenticates against these values and the access token is a public sentinel.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

from minekin_core.domain.ids import OpaqueId

IDENTITY_SCHEMA = "minekin.offline-identity.v1"
UUID_ALGORITHM = "minecraft-offline-v3"
CREDENTIAL_KIND = "offline-sentinel"

# The offline sentinel is public by construction, but it is classified as a
# credential so an online adapter later cannot inherit a log schema that prints
# real tokens.
ACCESS_TOKEN_SENTINEL = "0"

_OFFLINE_PREFIX = "OfflinePlayer:"

# Vanilla's StringUtil.isValidPlayerName: a server rejects anything else, so a
# name outside it is a configuration error rather than an offline-only quirk.
_VANILLA_USERNAME = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def offline_player_uuid(username: str) -> uuid.UUID:
    """Return the UUID Minecraft 1.21.4 derives for `username` offline."""

    digest = hashlib.md5(f"{_OFFLINE_PREFIX}{username}".encode(), usedforsecurity=False).digest()
    return uuid.UUID(bytes=digest, version=3)


@dataclass(frozen=True, slots=True)
class OfflineIdentityMaterial:
    """Non-secret session material for one revision of a Kin's offline identity.

    Options and values are held as separate argv elements by the caller; this
    record only owns the values. Derived fields are computed rather than stored
    so a hand-built record cannot disagree with the UUID rule.
    """

    local_profile_id: OpaqueId
    identity_revision: int
    username: str
    created_at: str

    def __post_init__(self) -> None:
        if not _VANILLA_USERNAME.fullmatch(self.username):
            raise ValueError("username must follow the vanilla 3-16 [A-Za-z0-9_] rule")
        if self.identity_revision < 1:
            raise ValueError("identity_revision starts at one")
        if not self.created_at:
            raise ValueError("created_at is required")

    @property
    def uuid(self) -> uuid.UUID:
        return offline_player_uuid(self.username)

    @property
    def uuid_canonical(self) -> str:
        return str(self.uuid)

    @property
    def uuid_id128(self) -> str:
        return self.uuid.hex

    def as_document(self) -> dict[str, object]:
        """The frozen `minekin.offline-identity.v1` document."""

        return {
            "schema": IDENTITY_SCHEMA,
            "local_profile_id": str(self.local_profile_id),
            "identity_revision": self.identity_revision,
            "username": self.username,
            "uuid_algorithm": UUID_ALGORITHM,
            "uuid_canonical": self.uuid_canonical,
            "uuid_id128": self.uuid_id128,
            "credential_kind": CREDENTIAL_KIND,
            "access_token_sentinel": ACCESS_TOKEN_SENTINEL,
            "created_at": self.created_at,
        }
