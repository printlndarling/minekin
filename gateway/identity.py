"""The one authorized write on the Dashboard surface: renaming a stopped Kin.

`docs/gateway-dashboard-readonly-contract-2026-09-28.md` freezes the three reads as
read-only, and `docs/stable-player-name-2026-09-29.md` opens exactly one narrow
exception: an identity-settings write. Nothing here can start, stop, move or otherwise
control a session. It reads who a Kin currently is, and — only on an explicitly
confirmed submission while that Kin is stopped — commits a new name through Core's
identity service. The Gateway never opens `kin_identity` for writing itself; the
compare-and-swap lives in `minekin_core.cli.rename.rename_identity`, so a rename stays
one definition whether it arrives from the CLI or from a panel.

Local write protection is layered rather than assumed. Loopback binding alone does not
stop a cross-origin request from the operator's own browser, so this module also requires
the request to be same-origin (its `Origin` equals the `Host` it reached, and that host is
a loopback name — which is what turns a DNS-rebinding POST into a refusal), to carry the
per-process CSRF token that only a same-origin script could have read from the identity
GET, and to be `application/json` (a cross-site form post cannot set that content type
without a preflight this server does not answer). Each layer fails closed with its own
named reason.
"""

from __future__ import annotations

import hmac
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from gateway.readmodel import STALE_AFTER_MS
from gateway.signals import missing, present
from minekin_core.adapters.filestore.persona_store import persona_path, read_persona
from minekin_core.application.ports.clock import Clock
from minekin_core.cli.init import kin_directory
from minekin_core.cli.rename import RENAME_NOTICE, rename_identity, show_identity
from minekin_core.cli.session import select_kin
from minekin_core.cli.status import ObservedState, read_status
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.offline_identity import is_valid_username

#: The read the rename form reviews, and the one write the identity card authorizes.
IDENTITY_PATH: Final = "/api/v1/dashboard/identity"
RENAME_PATH: Final = "/api/v1/dashboard/identity/rename"

#: The header a same-origin panel must echo the CSRF token back in. A custom header is
#: itself part of the defense: a cross-site form post cannot set it without a preflight.
CSRF_HEADER: Final = "X-Minekin-CSRF-Token"

#: A rename body is a name, a confirmation and a revision; anything larger is noise.
MAX_RENAME_BODY_BYTES: Final = 4096

_IDENTITY_SCHEMA: Final = "kin-dashboard-identity/1.0.0"

#: The same schema under a public name, so the server's shared write handler can label a
#: rename refusal with the identity version instead of re-reading a private constant.
IDENTITY_SCHEMA: Final = _IDENTITY_SCHEMA

#: Four dot-separated digit groups, matched whole by `_is_loopback_host`. Deliberately
#: not `ipaddress`: that library's tolerance of odd address strings has changed between
#: CPython patch releases, and this is a security predicate that cannot ride on that.
_IPV4_LITERAL: Final = re.compile(r"(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})")


@dataclass(frozen=True, slots=True)
class RenameRequest:
    """The validated pieces of a rename submission, or the reason it was refused."""

    username: str
    expected_revision: int


def new_csrf_token() -> str:
    """A fresh per-process token, handed out only over the same-origin identity read."""

    return secrets.token_urlsafe(24)


def _hostname_with_port(host_header: str) -> str:
    return host_header.strip().lower()


def _host_without_port(host_header: str) -> str:
    host = host_header.strip().lower()
    if host.startswith("["):  # bracketed IPv6 literal, e.g. [::1]:8787
        return host.partition("]")[0][1:] or host
    return host.rsplit(":", 1)[0] if ":" in host.rsplit("/", 1)[-1] else host


def _is_loopback_host(host_header: str) -> bool:
    """Whether the `Host` the client thinks it reached is a literal loopback address.

    The check is on the header, not the socket: a DNS-rebinding page connects to
    127.0.0.1 but sends `Host: evil.example`, and that mismatch is exactly the signal.
    This is deliberately a whole-literal test rather than a `startswith("127.")`, because
    an attacker-controlled `127.0.0.1.attacker.example` also begins that way but is not
    loopback. `ipaddress` is avoided on purpose: its parsing of these strings has shifted
    between CPython patch releases, and a security predicate may not depend on that.
    """

    host = _host_without_port(host_header)
    if host in {"localhost", "::1"}:
        return True
    octets = _IPV4_LITERAL.fullmatch(host)
    if octets is None:
        return False
    values = [int(group) for group in octets.groups()]
    return values[0] == 127 and all(value <= 255 for value in values)


def _same_origin(origin: str | None, host_header: str | None) -> bool:
    """Whether a browser's own `Origin` is the loopback host this request reached."""

    if not origin or not host_header:
        return False
    if origin in {"null", "none"}:  # opaque / sandboxed contexts are never same-origin here
        return False
    expected = f"http://{_hostname_with_port(host_header)}"
    return origin.rstrip("/").lower() == expected.rstrip("/")


def identity_read(
    root: Path, *, kin_selector: str | None, clock: Clock, csrf_token: str
) -> dict[str, Any]:
    """The stored identity plus whether a rename is currently allowed, changing nothing.

    `renameAllowed` mirrors the exact predicate the write enforces — a stopped session —
    so the panel disables the button for the same reason the server would refuse, rather
    than guessing from a poll that raced a launch.
    """

    kin_id = select_kin(root, kin_selector)
    view = show_identity(root, kin_id)
    state = read_status(root, kin_selector=kin_selector).state
    return {
        "schemaVersion": _IDENTITY_SCHEMA,
        "kinId": view.kin_id,
        "username": view.username,
        "uuidCanonical": view.uuid_canonical,
        "identityRevision": view.identity_revision,
        "state": state.value,
        "renameAllowed": state is ObservedState.IDLE,
        "notice": RENAME_NOTICE,
        "csrfToken": csrf_token,
        "observedAt": clock.utc_now().isoformat(),
        "staleAfterMs": STALE_AFTER_MS,
        "persona": saved_persona_read(kin_directory(root, kin_id), str(kin_id)),
    }


def saved_persona_read(kin_dir: Path, kin_id: str) -> dict[str, Any]:
    """Read the saved manifest, never redraw it or expose its creation seed."""
    if not persona_path(kin_dir).exists():
        return missing("unavailable", "PERSONA_NOT_INITIALISED: 该角色没有已保存人格, 不自动生成。")
    try:
        persona = read_persona(kin_dir)
        if persona.kin_id != kin_id:
            return missing("unavailable", "PERSONA_KIN_MISMATCH: 人格不属于当前角色, 拒绝展示。")
        return present(persona.decision_context())
    except (MinekinError, OSError, UnicodeError):
        # A validation error may quote malformed input. Do not return it to the browser.
        return missing("unavailable", "PERSONA_UNREADABLE: 已保存人格损坏、不受支持或无法读取。")


def refusal(
    status: int, code: str, message: str, schema: str = _IDENTITY_SCHEMA
) -> tuple[int, dict[str, Any]]:
    """One refusal, in the shape a panel's decoder already expects for that surface.

    Public because the server's own pre-body guards (an oversized or absent body) answer
    through it too, so a refused write reads the same however far it got. `schema` lets the
    config surface label its refusals with its own version while sharing this one predicate;
    the identity rename keeps the default.
    """

    return status, {"schemaVersion": schema, "error": code, "message": message}


def _parse_rename_body(raw: Mapping[str, Any]) -> tuple[RenameRequest | None, str]:
    """The validated request, or the reason it was refused, as one pass over the fields."""

    unknown = set(raw) - {"username", "confirm", "expectedRevision"}
    if unknown:
        return None, f"unexpected field(s): {', '.join(sorted(unknown))}"

    username = raw.get("username")
    if not isinstance(username, str):
        return None, "username must be a string"
    if not is_valid_username(username):
        return None, "username is not a valid Minecraft name (3-16 letters, digits or underscore)"

    confirm = raw.get("confirm")
    if confirm is not True:
        return None, "renaming requires an explicit confirmation (confirm must be true)"

    revision = raw.get("expectedRevision")
    # bool is a subclass of int in Python; a confirmation flag must not read as a revision.
    if isinstance(revision, bool) or not isinstance(revision, int):
        return None, "expectedRevision must be an integer identity revision"
    if revision < 1:
        return None, "expectedRevision starts at one"

    return RenameRequest(username=username, expected_revision=revision), ""


def rename_from_request(
    root: Path,
    *,
    kin_selector: str | None,
    body: Mapping[str, Any],
) -> tuple[int, dict[str, Any]]:
    """Commit a confirmed rename while the Kin is stopped, refusing everything else.

    Every guard runs before Core is asked to write, and the write itself is Core's
    compare-and-swap, so no refused request — and no failed one — leaves a partial
    identity behind. The refused reasons are named rather than folded into one 4xx so a
    panel can say which check tripped. The CSRF/origin check has already run in
    :func:`authorize_write` by the time this is reached.
    """

    kin_id = select_kin(root, kin_selector)
    state = read_status(root, kin_selector=kin_selector).state
    if state is not ObservedState.IDLE:
        return refusal(
            409,
            "session_not_stopped",
            f"this Kin's session is {state.value}; rename only while it is stopped",
        )

    request, reason = _parse_rename_body(body)
    if request is None:
        return refusal(400, "invalid_request", reason)

    try:
        report = rename_identity(
            kin_id,
            root=root,
            username=request.username,
            expected_revision=request.expected_revision,
        )
    except MinekinError as error:
        if error.category is ErrorCategory.STORAGE:
            return refusal(409, "stale_revision", error.safe_message)
        return refusal(400, "invalid_request", error.safe_message)

    return 200, _rename_payload(report)


def _rename_payload(report: Any) -> dict[str, Any]:
    return {
        "schemaVersion": _IDENTITY_SCHEMA,
        "status": report.status,
        "kinId": report.kin_id,
        "before": _view_payload(report.before),
        "after": _view_payload(report.after),
        "uuidChanged": report.uuid_changed,
        "notice": report.as_dict()["notice"],
    }


def _view_payload(view: Any) -> dict[str, Any]:
    return {
        "username": view.username,
        "uuidCanonical": view.uuid_canonical,
        "identityRevision": view.identity_revision,
    }


def authorize_write(
    *,
    origin: str | None,
    host: str | None,
    content_type: str | None,
    supplied_token: str | None,
    csrf_token: str,
    schema: str = _IDENTITY_SCHEMA,
) -> tuple[int, dict[str, Any]] | None:
    """Return a refusal for a request that fails a source/auth check, or None to proceed.

    Runs before the body is even parsed: an unauthenticated or cross-origin request should
    not reach the write logic at all, and a request with no `Host` cannot be proven
    same-origin, so it is refused rather than assumed local. `schema` labels the refusals
    with the calling surface's version, so the rename and the config save share one
    predicate yet each answer in the shape its own panel decoder expects.
    """

    if not host or not _is_loopback_host(host):
        return refusal(403, "forbidden_host", "the write surface is loopback-only", schema=schema)
    if not _same_origin(origin, host):
        return refusal(
            403, "cross_origin", "the write must come from this panel's own origin", schema=schema
        )
    if not content_type or not content_type.lower().startswith("application/json"):
        return refusal(
            415, "unsupported_media_type", "the write body must be application/json", schema=schema
        )
    if supplied_token is None or not hmac.compare_digest(supplied_token, csrf_token):
        return refusal(
            401,
            "missing_or_bad_csrf_token",
            f"a valid {CSRF_HEADER} is required to write",
            schema=schema,
        )
    return None
