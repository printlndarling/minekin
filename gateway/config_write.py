"""The second authorized write on the Dashboard surface: persisting operator settings.

`docs/stable-player-name-2026-09-29.md` excepted the identity rename into an otherwise
read-only Dashboard; the whole-project goal extends that exception to exactly one more
write — persisting the operator's model and goal settings through a panel, which is the
point of Phase D. Nothing here can start, stop, move or otherwise control a session, and
nothing here can reach a lease or an admission decision. It reads what settings are
currently saved under the data root and, on an explicitly submitted save, writes them back
through `minekin_core.domain.operator_config`, whose atomic + secret-free + versioned
contract is what makes this safe to expose.

The security layers are not re-implemented here: the same-origin, loopback, content-type
and CSRF checks live once in :func:`gateway.identity.authorize_write`, and this module's
route hands the request through it with its own schema label. Reusing that predicate is
the point — two copies of a source check would drift, and this is the surface where drift
is a hole rather than a typo.

The secret boundary is inherited, not re-drawn: `operator_config` persists a closed field
set in which no field can hold an API key (the closest is `model_api_key_env`, a variable
*name*), and it refuses a credential-shaped value on the way in. This layer only maps the
HTTP body onto that field set and back, so a key can neither be stored through a panel nor
read out of one.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

from gateway.identity import refusal
from gateway.readmodel import STALE_AFTER_MS
from minekin_core.application.ports.clock import Clock
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.operator_config import (
    KNOWN_PROVIDERS,
    ConfigRefusal,
    OperatorConfig,
    load_operator_config,
    save_operator_config,
)

#: The read the config form reviews, and the write that saves it.
CONFIG_PATH: Final = "/api/v1/dashboard/config"
CONFIG_SAVE_PATH: Final = "/api/v1/dashboard/config/save"

#: A config body is a handful of names, URLs and counts; anything larger is noise. The
#: field validators cap each value far below this, so this only bounds the raw request.
MAX_CONFIG_BODY_BYTES: Final = 8192

SCHEMA: Final = "kin-dashboard-config/1.0.0"

#: The two shapes the closed field set comes in, spelled out here rather than imported
#: from the dataclass so the payload this layer projects is a deliberate whitelist: a field
#: `operator_config` adds later cannot ride onto the Dashboard surface until it is named
#: here, which is the same identity rule `readmodel.py` applies to its own projections.
_INT_FIELDS: Final = frozenset(
    {
        "model_timeout_ms",
        "model_run_cost_cap",
        "goal_quantity",
        "model_request_rate",
        "model_response_rate",
    }
)
_STR_FIELDS: Final = frozenset(
    {
        "model_provider",
        "model_base_url",
        "model_name",
        "model_api_key_env",
        "goal_product_id",
        "goal_source_item_id",
        "goal_direction",
    }
)
_KNOWN_FIELDS: Final = _INT_FIELDS | _STR_FIELDS


def config_read(root: Path, *, clock: Clock, csrf_token: str) -> dict[str, Any]:
    """The persisted settings, the vocabulary the form offers, and the write token.

    `csrfToken` is the same per-process token the identity read hands out, because the
    save route authorizes through the same predicate. A hand-edited document that will not
    parse is reported through `loadError` with an empty field set rather than raised: the
    panel stays usable, the operator is told the file is unreadable, and the field
    vocabulary still renders so they can save a clean document over it.
    """

    load_error: str | None = None
    try:
        config = load_operator_config(root)
    except MinekinError as error:
        config = OperatorConfig()
        load_error = error.safe_message
    fields = config.as_document()["fields"]
    assert isinstance(fields, dict)  # the document's own shape; narrowed for the projection
    return {
        "schemaVersion": SCHEMA,
        "fields": fields,
        "knownFields": sorted(_KNOWN_FIELDS),
        "intFields": sorted(_INT_FIELDS),
        "providers": sorted(KNOWN_PROVIDERS),
        "maxBodyBytes": MAX_CONFIG_BODY_BYTES,
        "loadError": load_error,
        "csrfToken": csrf_token,
        "observedAt": clock.utc_now().isoformat(),
        "staleAfterMs": STALE_AFTER_MS,
    }


def save_from_request(root: Path, *, body: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    """Persist a submitted config document, refusing anything the field set will not hold.

    The write itself is `save_operator_config`'s — atomic, validated, secret-rejecting — so
    no refused or failed save leaves a partial document behind. A save replaces the whole
    document: a field the panel omits is written as unset, which is why the read echoes the
    current fields for the form to send back in full. The origin/CSRF/content-type check has
    already run in :func:`gateway.identity.authorize_write` by the time this is reached.
    """

    config, reason = _config_from_body(body)
    if reason:
        return refusal(400, "invalid_config", reason, schema=SCHEMA)
    assert config is not None  # an empty reason means a parsed config

    try:
        saved = save_operator_config(root, config)
    except ConfigRefusal as error:
        return refusal(400, "invalid_config", f"{error.field}: {error.reason}", schema=SCHEMA)

    fields = saved.as_document()["fields"]
    assert isinstance(fields, dict)
    return 200, {"schemaVersion": SCHEMA, "status": "saved", "fields": fields}


def _config_from_body(body: Mapping[str, Any]) -> tuple[OperatorConfig | None, str]:
    """The config a valid body describes, or the reason it was refused, as one pass.

    A top-level shape error is returned as a message here; a per-field semantic error is
    left for `save_operator_config` to raise as a named :class:`ConfigRefusal`, so each
    layer reports the failures it is the authority on.
    """

    unknown = set(body) - {"fields"}
    if unknown:
        return None, f"unexpected field(s) at top level: {', '.join(sorted(unknown))}"

    raw_fields = body.get("fields")
    if raw_fields is None:
        return None, "a save must carry a `fields` object (omitted fields are written as unset)"
    if not isinstance(raw_fields, Mapping):
        return None, "the config `fields` must be an object"

    candidate: dict[str, Any] = {
        str(key): value for key, value in cast("Mapping[str, Any]", raw_fields).items()
    }
    stray = set(candidate) - _KNOWN_FIELDS
    if stray:
        return None, f"not a configurable field: {', '.join(sorted(stray))}"
    return OperatorConfig(**candidate), ""
