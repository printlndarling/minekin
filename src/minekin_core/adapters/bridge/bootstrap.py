"""Deriving the one-time Bridge bootstrap descriptor for a launch.

The Bridge reads exactly one file when the client starts: a protobuf descriptor
holding the loopback endpoints, a 256-bit launch nonce and session key, and the
identity and bundle digests the Bridge must prove back before Core will talk to
it. Core writes that file once, exclusively, inside the session overlay, and
tells the client where it is through one environment variable.

This module decides *what goes in it*. It writes nothing: the exclusive create,
its permissions and its one-time delivery belong to the host that also owns the
sockets, so there is one place that can say where the secret went.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from minekin_core.adapters.bridge.ipc import BridgeSession
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.ids import KinId

DESCRIPTOR_FILENAME: Final[str] = "bridge-bootstrap.pb"

_SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_KEY_BYTES: Final[int] = 32


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "bridge.bootstrap",
        "build",
        ErrorCategory.IPC_PROTOCOL,
        Retryability.OPERATOR_ACTION,
        message,
    )


def descriptor_path(overlay: Path) -> Path:
    """Where one session generation's bootstrap descriptor goes.

    The path is a function of the overlay rather than a caller's choice: the
    descriptor carries the session key, so it must land in the session's own
    directory, and a path that escaped the overlay would put a credential
    somewhere its owner does not clean up.
    """

    if not overlay.is_absolute():
        raise _reject("the session overlay must be an absolute path")
    resolved = overlay.resolve()
    candidate = resolved / DESCRIPTOR_FILENAME
    if candidate.parent != resolved:
        raise _reject("the bootstrap descriptor escaped the session overlay")
    return candidate


def _digest(plan: Mapping[str, Any], key: str) -> str:
    value = plan.get(key)
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise _reject(f"the launch plan has no usable {key}")
    return value


def bridge_session_for(
    plan: Mapping[str, Any],
    *,
    kin_id: KinId,
    session_id: str,
    generation: int,
    client_instance_id: str,
    nonce: bytes | None = None,
    session_key: bytes | None = None,
) -> BridgeSession:
    """The identifiers and secrets one managed client is launched with.

    `bundle_digest` is the reviewed plan's own digest: it is the one value that
    says which reviewed launch this client came from, and it is what Core
    compares the Bridge's echoed copy against.

    `bridge_digest` is the Bridge *source tree* digest, not a JAR digest. The
    Bridge JAR cannot be pinned yet — the recipe still says `build_required`
    until Loom's output is shown to be reproducible on a second platform — so
    recording a source digest is the honest value available. It binds Core and
    the client to the same source; it is not a claim about the shipped bytes.
    """

    return BridgeSession(
        kin_id=str(kin_id),
        session_id=session_id,
        generation=generation,
        client_instance_id=client_instance_id,
        bundle_digest=_digest(plan, "plan_sha256"),
        bridge_digest=_digest(plan, "bridge_source_sha256"),
        launch_nonce=_secret(nonce),
        session_key=_secret(session_key),
    )


def _secret(value: bytes | None) -> bytes:
    if value is None:
        return os.urandom(_KEY_BYTES)
    if len(value) != _KEY_BYTES:
        raise _reject(f"bridge session secrets must be {_KEY_BYTES} bytes")
    return value
