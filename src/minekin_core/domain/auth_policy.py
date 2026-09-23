"""The immutable authentication choice for one managed client run.

P0 can launch a local offline identity only. The policy is constructed from a
validated Server Profile (or the default menu run), gates process preparation,
and is recorded from that same object before the client starts. Adding an online
adapter later must extend this boundary instead of silently changing a run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_REVISION = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class AuthPolicy:
    auth_mode: str = "offline"
    online_adapter_enabled: bool = False
    server_profile_id: str | None = None
    server_profile_revision: str | None = None

    def __post_init__(self) -> None:
        if self.auth_mode != "offline" or self.online_adapter_enabled:
            raise ValueError("P0 accepts only an offline auth policy without an online adapter")
        if (self.server_profile_id is None) != (self.server_profile_revision is None):
            raise ValueError("auth policy profile id and revision must be present together")
        if self.server_profile_id is not None and not self.server_profile_id:
            raise ValueError("auth policy profile id must not be empty")
        if self.server_profile_revision is not None and not _REVISION.fullmatch(
            self.server_profile_revision
        ):
            raise ValueError("auth policy profile revision must be a lowercase SHA-256")

    @classmethod
    def from_profile(cls, *, profile_id: str, revision: str) -> AuthPolicy:
        return cls(server_profile_id=profile_id, server_profile_revision=revision)

    def require_offline_launch(self) -> None:
        """The launch path has no authority to switch this run's strategy."""

        if self.auth_mode != "offline" or self.online_adapter_enabled:
            raise ValueError("an online strategy cannot launch through the P0 offline path")

    def as_event_payload(self) -> dict[str, object]:
        return {
            "auth_mode": self.auth_mode,
            "online_adapter_enabled": self.online_adapter_enabled,
            "server_profile_id": self.server_profile_id,
            "server_profile_revision": self.server_profile_revision,
        }
