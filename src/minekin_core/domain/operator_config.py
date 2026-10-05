"""The operator's settings as a persisted document, separate from every secret.

Until now an operator stated everything through the environment: the model endpoint
through ``MINEKIN_MODEL_*``, the standing goal through ``MINEKIN_GOAL_*``. That is right for a
one-off shell run and wrong for a product a person configures once from a dashboard and then
restarts. This module is the seam that lets those same settings live in a file under the data
root and still be read by the *existing* resolvers (`model_access`, `goal_spec`) unchanged,
because it does not replace the environment — it fills the names the environment would have
held.

Three properties make this safe enough to be the dashboard's write target, and each is a line
the rest of the file has to keep true:

* **No field can hold a secret.** The document is a closed set of named fields, and none of
  them is the API key. The closest a field comes is `model_api_key_env`, which stores the *name*
  of the variable that holds the key (the shape `model_access` already documents and refuses to
  resolve here), never the key's value. A value is checked against a secret shape on the way in
  so a pasted key lands in a named refusal rather than on disk, and saving only ever writes the
  fields this dataclass has — a key cannot be added without adding a field, which a reviewer
  would see.

* **A write is atomic.** The new document goes to a sibling temporary file, is flushed, then
  ``os.replace`` moves it over the target. A crash mid-write leaves either the whole old
  document or the whole new one, so a restarted Kin never reads a half-written configuration it
  would then trust.

* **A read has a version policy.** Absent is an empty config, not an error — a fresh root is a
  supported shape. A document at this major version is read, and unknown keys in it are ignored
  so a newer writer can add a field without stranding an older reader. A document at another
  major is refused by name rather than guessed at, because a silently-mis-read setting is worse
  than an operator who is told the file is from another version.

This layer decides none of the values' meaning: which provider is real, whether an endpoint may
be contacted, whether an item id is a product the catalog knows. Those questions already have
owners in `model_access`, `admission` and `recipe_catalog`, and re-deciding them here would give
one setting two readers who could disagree. What lives here is persistence, the secret boundary,
and the one translation from a field to the environment name that owner reads.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from minekin_core.config import LOCAL_ENV_NAME_PATTERN
from minekin_core.domain.decision_policy import DECISION_POLICY_VARIABLE, KNOWN_POLICIES
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.goal_spec import (
    GOAL_DIRECTION_VARIABLE,
    GOAL_PRODUCT_VARIABLE,
    GOAL_QUANTITY_VARIABLE,
    GOAL_SOURCE_ITEM_VARIABLE,
)
from minekin_core.domain.model_access import (
    MODEL_API_KEY_ENV_VARIABLE,
    MODEL_BASE_URL_VARIABLE,
    MODEL_PROVIDER_VARIABLE,
    MODEL_REQUEST_RATE_VARIABLE,
    MODEL_RESPONSE_RATE_VARIABLE,
    MODEL_RUN_COST_CAP_VARIABLE,
    MODEL_TIMEOUT_MS_VARIABLE,
    MODEL_VARIABLE,
)
from minekin_core.domain.skill_parameters import MAX_QUANTITY, is_item_id

#: The document's own version, distinct from every schema the gateway projects. The major is
#: what the reader will not guess across; a minor merely means fields an older reader ignores.
SCHEMA_NAME: Final = "minekin-operator-config"
SCHEMA_MAJOR: Final = 1
SCHEMA_VERSION: Final = f"{SCHEMA_NAME}/{SCHEMA_MAJOR}.1"

CONFIG_FILE_NAME: Final = "operator-config.json"

#: The providers whose name this file will store. It is the vocabulary `model_access` already
#: accepts; a value outside it is refused here so a typo is caught at save time with a field
#: name attached, not much later as an unavailable model with no clue which setting caused it.
KNOWN_PROVIDERS: Final = frozenset({"off", "openai_compatible"})

#: A bare integer field's ceiling. `int` keeps a pathological value from a hand-edited file
#: costing a comparison walk; the semantic range is each reader's to enforce.
_MAX_INT: Final = 1_000_000_000

#: Something that reads like a pasted credential: long, unstructured, and the shape of a token
#: rather than a URL, an identifier or a count. Applied only to string fields, which hold names
#: and URLs and never a key — so a match here is a mistake to refuse, not a value to store.
_SECRET_SHAPED = re.compile(r"[A-Za-z0-9_\-]{32,}")


class ConfigRefusal(Exception):
    """A setting this layer will not persist, naming the field and why.

    Raised rather than returned as an error value so the caller that turns it into an HTTP
    response (or a CLI message) chooses the words; the reason is a stable token so a panel can
    say which field tripped without parsing prose.
    """

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


@dataclass(frozen=True, slots=True)
class OperatorConfig:
    """Every setting the dashboard may persist. Empty string / ``None`` means "unset".

    A field is stored only when it is set, so an empty config round-trips to a document whose
    `fields` map is empty and which fills nothing into the environment.
    """

    model_provider: str = ""
    model_base_url: str = ""
    model_name: str = ""
    model_api_key_env: str = ""
    model_timeout_ms: int | None = None
    model_run_cost_cap: int | None = None
    model_request_rate: int | None = None
    model_response_rate: int | None = None
    decision_policy: str = ""
    goal_product_id: str = ""
    goal_quantity: int | None = None
    goal_source_item_id: str = ""
    goal_direction: str = ""

    def is_empty(self) -> bool:
        return not _populated_fields(self)

    def to_environment(self) -> dict[str, str]:
        """The set fields, spelled as the environment names their readers already look for.

        One mapping, derived from the field list, so `model_access` and `goal_spec` stay the only
        code that interprets a value: this only decides which name a field writes and how a
        number is stringified.
        """

        out: dict[str, str] = {}
        for name, value in _populated_fields(self):
            out[_ENV_NAME[name]] = _as_env_value(value)
        return out

    def as_document(self) -> dict[str, object]:
        """The on-disk shape: a version and the populated fields only."""

        return {
            "schemaVersion": SCHEMA_VERSION,
            "fields": {name: value for name, value in _populated_fields(self)},
        }


#: Which environment name each field writes. The pairs are the contract with the readers above;
#: a field with no entry here is a bug caught by the save-time validation, not a silent no-op.
_ENV_NAME: Final[dict[str, str]] = {
    "model_provider": MODEL_PROVIDER_VARIABLE,
    "model_base_url": MODEL_BASE_URL_VARIABLE,
    "model_name": MODEL_VARIABLE,
    "model_api_key_env": MODEL_API_KEY_ENV_VARIABLE,
    "model_timeout_ms": MODEL_TIMEOUT_MS_VARIABLE,
    "model_run_cost_cap": MODEL_RUN_COST_CAP_VARIABLE,
    "model_request_rate": MODEL_REQUEST_RATE_VARIABLE,
    "model_response_rate": MODEL_RESPONSE_RATE_VARIABLE,
    "decision_policy": DECISION_POLICY_VARIABLE,
    "goal_product_id": GOAL_PRODUCT_VARIABLE,
    "goal_quantity": GOAL_QUANTITY_VARIABLE,
    "goal_source_item_id": GOAL_SOURCE_ITEM_VARIABLE,
    "goal_direction": GOAL_DIRECTION_VARIABLE,
}


def config_path(root: Path) -> Path:
    """Where the document lives under the operator's data root."""

    return root / CONFIG_FILE_NAME


def _populated_fields(config: OperatorConfig) -> list[tuple[str, object]]:
    fields: list[tuple[str, object]] = []
    for name, value in _raw_fields(config):
        if value is None or value == "":
            continue
        fields.append((name, value))
    return fields


def _raw_fields(config: OperatorConfig) -> list[tuple[str, object]]:
    return [
        ("model_provider", config.model_provider),
        ("model_base_url", config.model_base_url),
        ("model_name", config.model_name),
        ("model_api_key_env", config.model_api_key_env),
        ("model_timeout_ms", config.model_timeout_ms),
        ("model_run_cost_cap", config.model_run_cost_cap),
        ("model_request_rate", config.model_request_rate),
        ("model_response_rate", config.model_response_rate),
        ("decision_policy", config.decision_policy),
        ("goal_product_id", config.goal_product_id),
        ("goal_quantity", config.goal_quantity),
        ("goal_source_item_id", config.goal_source_item_id),
        ("goal_direction", config.goal_direction),
    ]


def _as_env_value(value: object) -> str:
    return value if isinstance(value, str) else str(value)


def _reject_secret(field: str, value: str) -> None:
    """Refuse a string that is shaped like a pasted credential.

    The identifier and item-id checks already reject most mistakes; this is the one that matters
    for the secret boundary, because a key is long and unstructured and otherwise passes a
    loose "non-empty string" test. It is deliberately not applied to `model_api_key_env`, which
    is validated as an identifier below.
    """

    if _SECRET_SHAPED.fullmatch(value):
        raise ConfigRefusal(
            field, "looks like a credential; store the key in the environment, not here"
        )


def _validated_fields(config: OperatorConfig) -> dict[str, object]:
    """The document's `fields` map, after every check that keeps secrets and junk out."""

    out: dict[str, object] = {}
    for name, value in _raw_fields(config):
        if name not in _ENV_NAME:
            raise ConfigRefusal(name, "not a configurable field")
        if value is None or value == "":
            continue
        out[name] = _validated_field(name, value)
    return out


def _validated_field(name: str, value: object) -> object:
    if name == "model_provider":
        provider = _checked_string(name, value)
        if provider not in KNOWN_PROVIDERS:
            raise ConfigRefusal(name, f"unknown provider; choose one of {sorted(KNOWN_PROVIDERS)}")
        return provider
    if name == "decision_policy":
        # The vocabulary `domain.decision_policy` owns; a value outside it is caught here with
        # the field name attached rather than read later as a licence nobody granted.
        policy = _checked_string(name, value)
        if policy not in KNOWN_POLICIES:
            raise ConfigRefusal(name, f"unknown policy; choose one of {sorted(KNOWN_POLICIES)}")
        return policy
    if name in {"model_base_url", "model_name", "goal_direction"}:
        return _checked_string(name, value)
    if name == "model_api_key_env":
        # A variable NAME, not a key: it must look like an identifier, which is also the check
        # `config.py` runs on `.env` names. A 40-char token here would be a pasted key.
        candidate = _checked_string(name, value)
        if not LOCAL_ENV_NAME_PATTERN.match(candidate):
            raise ConfigRefusal(name, "must be a bare environment-variable name, not a key")
        return candidate
    if name in {"goal_product_id", "goal_source_item_id"}:
        candidate = _checked_string(name, value)
        if not is_item_id(candidate):
            raise ConfigRefusal(
                name, "must be an item id the game spells (namespace:path, lowercase)"
            )
        return candidate
    if name in {"model_timeout_ms", "model_run_cost_cap", "goal_quantity"}:
        return _checked_positive_int(name, value)
    if name in {"model_request_rate", "model_response_rate"}:
        if type(value) is not int or not 0 <= value <= _MAX_INT:
            raise ConfigRefusal(name, f"must be an integer between 0 and {_MAX_INT}")
        return value
    raise ConfigRefusal(name, "has no validator, which is a programming mistake")


def _checked_string(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ConfigRefusal(name, "must be a string")
    trimmed = value.strip()
    if not trimmed:
        raise ConfigRefusal(name, "must not be blank")
    if len(trimmed) > 512:
        raise ConfigRefusal(name, "is too long to be a setting")
    _reject_secret(name, trimmed)
    return trimmed


def _checked_positive_int(name: str, value: object) -> int:
    # bool is an int subclass in Python; a JSON `true` must not read as a count.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigRefusal(name, "must be a whole number")
    if not 1 <= value <= _MAX_INT:
        raise ConfigRefusal(name, f"must be between 1 and {_MAX_INT}")
    if name == "goal_quantity" and value > MAX_QUANTITY:
        raise ConfigRefusal(name, f"a goal quantity above {MAX_QUANTITY} is not a single ask")
    return value


def save_operator_config(root: Path, config: OperatorConfig) -> OperatorConfig:
    """Validate, then write atomically, so a crash leaves the previous document whole.

    Returns the config it wrote (validated and trimmed) so the caller can echo back what is now
    live rather than what was requested before validation ran.
    """

    fields = _validated_fields(config)
    document = {"schemaVersion": SCHEMA_VERSION, "fields": fields}
    root.mkdir(parents=True, exist_ok=True)
    target = config_path(root)
    temp = target.with_name(f"{target.name}.tmp")
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, target)
    return _from_fields(fields)


def load_operator_config(root: Path) -> OperatorConfig:
    """Read the persisted settings, tolerating absence and newer minors, refusing other majors.

    No file is an empty config. Malformed JSON or an unrecognised major version raises a
    :class:`MinekinError` so the caller stops rather than running a Kin on a half-understood
    file — an operator who hand-edited the JSON deserves to be told it did not parse.
    """

    target = config_path(root)
    if not target.is_file():
        return OperatorConfig()
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _config_error(f"{target.name} is not valid JSON: {error}") from None
    if not isinstance(document, dict):
        raise _config_error(f"{target.name} must hold an object")
    # A decoded JSON object always has string keys; the `isinstance` check above is the runtime
    # proof, so narrowing to a typed mapping lets the readers below see `object` not `Unknown`.
    fields_document = cast("dict[str, object]", document)
    _check_schema(fields_document.get("schemaVersion"))
    raw_fields = fields_document.get("fields")
    if raw_fields is None:
        raw_fields = {}
    if not isinstance(raw_fields, dict):
        raise _config_error(f"{target.name} has a `fields` map that is not an object")
    # Unknown keys are dropped, not refused: forward compatibility is the point of the minor.
    known = {
        name: value
        for name, value in cast("dict[str, object]", raw_fields).items()
        if name in _ENV_NAME
    }
    return _from_fields(known)


def _check_schema(version: object) -> None:
    # Same name and same major is readable whatever the minor: a newer writer adding a field is
    # exactly the minor change whose unknown keys `load` already drops. Only a different major is
    # refused, because the field meaning could have moved and a silently-mis-read setting is the
    # outcome the whole version policy exists to avoid.
    if version == SCHEMA_VERSION:
        return
    if not isinstance(version, str):
        raise _config_error(
            f"{CONFIG_FILE_NAME} must name schemaVersion as a string, not {version!r}"
        )
    name, _, release = version.partition("/")
    major = release.partition(".")[0]
    if name == SCHEMA_NAME and major.isdigit():
        if int(major) == SCHEMA_MAJOR:
            return
        raise _config_error(
            f"{CONFIG_FILE_NAME} is version {version!r}, which this build cannot read; "
            f"it understands major {SCHEMA_MAJOR}"
        )
    raise _config_error(f"{CONFIG_FILE_NAME} has an unrecognised schemaVersion {version!r}")


def _config_error(message: str) -> MinekinError:
    return MinekinError(
        component="config",
        operation="load",
        category=ErrorCategory.CONFIG,
        retryability=Retryability.OPERATOR_ACTION,
        safe_message=f"OPERATOR_CONFIG_UNREADABLE: {message}",
    )


def _from_fields(fields: dict[str, object]) -> OperatorConfig:
    """Build a config from an already-validated `fields` map, trusting the shape it was saved with.

    Load uses this on the file's contents without re-running validators, because a value written
    by this same build has already passed them; a value that a newer build wrote into a *known*
    field is read as stored rather than rejected for failing a check that did not exist when it
    was saved.
    """

    def text(name: str) -> str:
        value = fields.get(name)
        return value if isinstance(value, str) else ""

    def number(name: str) -> int | None:
        value = fields.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    return OperatorConfig(
        model_provider=text("model_provider"),
        model_base_url=text("model_base_url"),
        model_name=text("model_name"),
        model_api_key_env=text("model_api_key_env"),
        model_timeout_ms=number("model_timeout_ms"),
        model_run_cost_cap=number("model_run_cost_cap"),
        model_request_rate=number("model_request_rate"),
        model_response_rate=number("model_response_rate"),
        decision_policy=text("decision_policy"),
        goal_product_id=text("goal_product_id"),
        goal_quantity=number("goal_quantity"),
        goal_source_item_id=text("goal_source_item_id"),
        goal_direction=text("goal_direction"),
    )


def apply_operator_config(
    config: OperatorConfig, environ: MutableMapping[str, str] | None = None
) -> tuple[str, ...]:
    """Fill the config's names into the environment, leaving any name the operator exported alone.

    This is the reason the file has any effect: after it runs, `model_access` and `goal_spec`
    read a configured provider and goal as if they had been in the shell all along. The
    precedence rule is copied from `config.load_local_environment` on purpose — a name already in
    the environment outranks the file, because an explicit statement made later (in the shell)
    should win over one made earlier (a saved document). Only the applied *names* are returned,
    never their values: a value that comes back from this function is a value that could end up
    in a log, and this layer has no business handing that to a caller.
    """

    source = os.environ if environ is None else environ
    applied: list[str] = []
    for name, value in config.to_environment().items():
        if name in source:
            continue
        source[name] = value
        applied.append(name)
    return tuple(applied)
