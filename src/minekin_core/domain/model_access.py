"""Model access: what the operator configures, what the mind may choose, what it costs.

Three separate things live here, and keeping them separate is the point of the module.

**Configuration is names, never values.** `ModelConfig` is the whole of what this build
knows about a model endpoint, and no field of it can hold a secret — including the one
field that looks like it does. `api_key_env` is the *name* of the environment variable
holding the key, so a logged config, a run document, or a traceback prints
`MINEKIN_MODEL_API_KEY` and never what it points at. That is why the key is not a field at
all: `dataclass` generates `repr()`, so a key field would be printed by any debug log,
copied by any projection built from the config's fields, and be one forgotten `print` away
from the run directory. Instead the key is resolved at the one moment it has to exist
anywhere — while a request is actually being sent — by `key_for`, which is the only place
in this package that reads a secret from the environment.

**The provider only chooses.** `DecisionRequest` carries the feasible skill ids the local
layer already computed, and `compose_decision` refuses any choice outside them or from
another `intent_generation`. It also refuses an ask whose arguments the chosen skill does not
take, cannot do without, or cannot hold — the check is `domain.skill_parameters`'s, called here
so that no provider gets to decide what a parameter means. That enforcement is code rather than
prose because both failures it prevents are silent: an out-of-bounds id would be handed to a task
adapter that has no such skill, and a late reply would write an already-cancelled intent back onto
the keys.

**Money is not latency.** `docs/s3-minimal-player-mind.md` §4 says so explicitly:
`domain/budget.py` folds Bridge callback wall time into percentiles, and nothing in it can
be re-used to add up tokens. `CostLedger` is the second account and the two never meet. A
token count the provider did not report stays absent rather than becoming a zero, for the
same reason an unsampled series in `budget.py` has no median.

`model_config` follows the house rule from `config.py`: the environment is injected as a
`Mapping` so a test can state one, a missing value is a named refusal, and reading it
never creates a directory and never writes anything to disk.
"""

from __future__ import annotations

import ipaddress
import math
import os
import re
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final, Literal, cast

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability, redact_text
from minekin_core.domain.persona import PersonaManifest
from minekin_core.domain.skill_parameters import validate_arguments

#: The operator-facing names, kept together because §1 of the contract is a table: a
#: renamed variable must be renamed in the docs, in the refusal text, and in the tests.
MODEL_PROVIDER_VARIABLE: Final = "MINEKIN_MODEL_PROVIDER"
MODEL_BASE_URL_VARIABLE: Final = "MINEKIN_MODEL_BASE_URL"
MODEL_VARIABLE: Final = "MINEKIN_MODEL"
MODEL_API_KEY_ENV_VARIABLE: Final = "MINEKIN_MODEL_API_KEY_ENV"
MODEL_TIMEOUT_MS_VARIABLE: Final = "MINEKIN_MODEL_TIMEOUT_MS"
MODEL_MAX_ATTEMPTS_VARIABLE: Final = "MINEKIN_MODEL_MAX_ATTEMPTS"
MODEL_RUN_COST_CAP_VARIABLE: Final = "MINEKIN_MODEL_RUN_COST_CAP"
MODEL_REQUEST_RATE_VARIABLE: Final = "MINEKIN_MODEL_REQUEST_MICRO_PER_MILLION_TOKENS"
MODEL_RESPONSE_RATE_VARIABLE: Final = "MINEKIN_MODEL_RESPONSE_MICRO_PER_MILLION_TOKENS"

type ProviderName = Literal["off", "openai_compatible"]

#: How many attempts one decision call may make: the first, plus one bounded retry by
#: default. The total wall-clock bound is attempts x `timeout_ms`; the operator may set
#: `MINEKIN_MODEL_MAX_ATTEMPTS` to 1 to keep the single-attempt shape.
DEFAULT_MODEL_MAX_ATTEMPTS: Final = 2
MAX_MODEL_ATTEMPTS: Final = 5

#: `off` is a product capability and not a placeholder: with it the Kin reflects, runs
#: approved skills and takes conservative actions exactly as before, and every call site
#: that wanted model output gets a named `MODEL_NOT_CONFIGURED` result instead of an
#: exception path.
PROVIDER_OFF: Final[ProviderName] = "off"
PROVIDER_OPENAI_COMPATIBLE: Final[ProviderName] = "openai_compatible"
KNOWN_PROVIDERS: Final[tuple[ProviderName, ...]] = (PROVIDER_OFF, PROVIDER_OPENAI_COMPATIBLE)

#: One call's wall-clock limit, and one run's spend limit. Both are overridable by the
#: operator, and both are stated here rather than discovered: a default the operator
#: cannot read is a default they cannot reason about.
#:
#: The cap is in micro-currency of whatever unit the operator states prices in. This build
#: never converts to a real currency and never claims a price a provider quoted it.
DEFAULT_MODEL_TIMEOUT_MS: Final = 8_000
DEFAULT_RUN_COST_CAP_MICRO: Final = 500_000

#: The rates a ledger prices reported tokens with. There is no price source in the
#: contract, so defaults are estimates, not quotes. Operators may state their own rates;
#: every ledger records the actual rates used. Rounding is upwards: a fraction of a micro-unit
#: that was spent is not free.
TOKENS_PER_MILLION: Final = 1_000_000
DEFAULT_REQUEST_MICRO_PER_MILLION_TOKENS: Final = 2_500
DEFAULT_RESPONSE_MICRO_PER_MILLION_TOKENS: Final = 10_000

#: A decision's reason is remote-authored text that a log line will carry, so it is both
#: bounded and redacted on the way in — see `compose_decision`.
MAX_REASON_CHARS: Final = 400

#: The shortlist bound. `docs/autonomous-goal-scheduler.md` step 4 hands the selector "a
#: small step" of what is currently feasible; a request listing the whole skill library is
#: not that, and it is also the prompt a remote endpoint gets.
MAX_FEASIBLE_SKILLS: Final = 64

#: Loopback spellings a plain-`http` base URL may use. A name ending in `.localhost` is
#: included because resolution there is the stub resolver's promise rather than a fact
#: checkable from here, and `127.0.0.0/8` is one block rather than one address.
_LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"localhost", "::1", "0:0:0:0:0:0:0:1"})
_LOOPBACK_SUFFIX: Final = ".localhost"

# The name slot holds a name: an environment variable's spelling, checked so a pasted
# credential is refused at resolve time instead of becoming part of every `repr()` later.
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigRefusal:
    """The named tokens that appear in resolve-time refusals.

    Named rather than free text so a test, the dashboard and the operator's grep all reach
    the same string. Each states the reason and nothing else: a message that quotes a
    configured value can quote a pasted key.
    """

    UNKNOWN_PROVIDER = "MODEL_PROVIDER_UNKNOWN"
    NOT_CONFIGURED = "MODEL_NOT_CONFIGURED"
    BAD_NUMBER = "MODEL_NUMBER_INVALID"
    BAD_URL = "MODEL_URL_INVALID"
    BAD_ENV_NAME = "MODEL_API_KEY_ENV_INVALID"


class UnavailableReason(StrEnum):
    """Why a call did not produce a usable decision.

    One vocabulary covering both halves of the port's return type, because the caller's
    conservative path is identical either way — keep the event, keep the goal, do not widen
    a retry budget — while the ledger still has to say which of the two happened.
    """

    #: The provider is `off`: there is no model for this build to ask.
    MODEL_NOT_CONFIGURED = "MODEL_NOT_CONFIGURED"
    #: The key's variable was named but is not set; the endpoint has no credential.
    KEY_UNRESOLVED = "KEY_UNRESOLVED"
    #: The spend already exceeds the run cap, so no call was started.
    RUN_COST_CAP_REACHED = "RUN_COST_CAP_REACHED"
    #: The local layer offered nothing feasible, so no answer was possible.
    NOTHING_FEASIBLE = "NOTHING_FEASIBLE"
    #: The call outlived `timeout_ms`.
    TIMEOUT = "TIMEOUT"
    #: The endpoint could not be reached at all, or did not speak HTTP.
    TRANSPORT_FAILURE = "TRANSPORT_FAILURE"
    #: The endpoint redirected. This build talks to the host the operator named, and to
    #: nothing else: a forwarded request is a second hop the configured checks never saw.
    REDIRECTED = "REDIRECTED"
    #: The endpoint answered, and the answer was not a success.
    PROVIDER_STATUS = "PROVIDER_STATUS"
    #: The completion's content was not parseable JSON.
    RESPONSE_MALFORMED_JSON = "RESPONSE_MALFORMED_JSON"
    #: The completion carried no content to read.
    RESPONSE_MISSING_CONTENT = "RESPONSE_MISSING_CONTENT"
    #: The content parsed, but not into the object the schema asks for.
    RESPONSE_NOT_OBJECT = "RESPONSE_NOT_OBJECT"
    #: The chosen skill was not one the local layer offered.
    DECISION_OUT_OF_BOUNDS = "DECISION_OUT_OF_BOUNDS"
    #: The answer belongs to another intent generation, so it is late.
    STALE_GENERATION = "STALE_GENERATION"
    #: The answer names an argument the chosen skill does not take, so nothing here knows what
    #: it was for. Refused rather than dropped: an answerer that invents a key is telling this
    #: side its picture of the interface is wrong, and that is worth a line in the ledger.
    MODEL_ARGUMENTS_UNKNOWN = "MODEL_ARGUMENTS_UNKNOWN"
    #: The answer chose a skill that cannot run without one of its arguments.
    MODEL_ARGUMENTS_MISSING = "MODEL_ARGUMENTS_MISSING"
    #: An argument is there but is not a value of the declared kind or inside its bounds — which
    #: includes the id spellings, since an invented item id is an invalid value, not a missing
    #: recipe. `recipe_catalog` never sees either of these.
    MODEL_ARGUMENTS_INVALID = "MODEL_ARGUMENTS_INVALID"


class CallOutcome(StrEnum):
    """The four results §4 of the contract lets the ledger record."""

    OK = "ok"
    TIMEOUT = "timeout"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


#: How each refusal is filed. `rejected` means the request this side made or the answer it
#: got was unusable here; `unavailable` means there was nothing to file against. The split
#: matters downstream: repeated rejections say the shortlist or the schema is wrong, while
#: repeated unavailability says the endpoint is.
_OUTCOME_BY_REASON: Final[Mapping[UnavailableReason, CallOutcome]] = {
    UnavailableReason.MODEL_NOT_CONFIGURED: CallOutcome.UNAVAILABLE,
    UnavailableReason.KEY_UNRESOLVED: CallOutcome.UNAVAILABLE,
    UnavailableReason.RUN_COST_CAP_REACHED: CallOutcome.UNAVAILABLE,
    UnavailableReason.NOTHING_FEASIBLE: CallOutcome.UNAVAILABLE,
    UnavailableReason.TIMEOUT: CallOutcome.TIMEOUT,
    UnavailableReason.TRANSPORT_FAILURE: CallOutcome.UNAVAILABLE,
    UnavailableReason.REDIRECTED: CallOutcome.UNAVAILABLE,
    UnavailableReason.PROVIDER_STATUS: CallOutcome.UNAVAILABLE,
    UnavailableReason.RESPONSE_MALFORMED_JSON: CallOutcome.REJECTED,
    UnavailableReason.RESPONSE_MISSING_CONTENT: CallOutcome.REJECTED,
    UnavailableReason.RESPONSE_NOT_OBJECT: CallOutcome.REJECTED,
    UnavailableReason.DECISION_OUT_OF_BOUNDS: CallOutcome.REJECTED,
    UnavailableReason.STALE_GENERATION: CallOutcome.REJECTED,
    UnavailableReason.MODEL_ARGUMENTS_UNKNOWN: CallOutcome.REJECTED,
    UnavailableReason.MODEL_ARGUMENTS_MISSING: CallOutcome.REJECTED,
    UnavailableReason.MODEL_ARGUMENTS_INVALID: CallOutcome.REJECTED,
}


def _reject(operation: str, message: str) -> MinekinError:
    """A resolve-time refusal: the operator's configuration, not the Kin's problem.

    Nothing about a model call should reach the game loop as an exception, so these are
    raised only while reading configuration — before a run starts choosing.
    """

    return MinekinError(
        component="model.config",
        operation=operation,
        category=ErrorCategory.CONFIG,
        retryability=Retryability.OPERATOR_ACTION,
        safe_message=message,
    )


def _shown(value: str) -> str:
    """Describe a configured value by its length, and never by what it says.

    A refusal is logged, and it is tempting to quote the offending value. That is the one
    thing this module must not do, and no filter on the value makes it safe: an AWS-style key
    is twenty characters of plain upper-case alphanumerics, which passes for a name on any
    shape test short of an allow-list. So the operator is told how long what they set was and
    which variable it was set in, which is enough to find the mistake, and nothing more.
    """

    return f"a {len(value)}-character value"


def _positive_int(variable: str, raw: str, operation: str) -> int:
    try:
        parsed = int(raw.strip())
    except ValueError:
        raise _reject(
            operation,
            f"{ConfigRefusal.BAD_NUMBER}: {variable} must be a positive integer, not "
            f"{_shown(raw.strip())}",
        ) from None
    if parsed <= 0:
        raise _reject(
            operation, f"{ConfigRefusal.BAD_NUMBER}: {variable} must be a positive integer"
        )
    return parsed


def is_loopback_host(host: str) -> bool:
    """Recognize actual loopback addresses and the reserved localhost namespace."""

    lowered = host.strip("[]").lower()
    if lowered in _LOOPBACK_HOSTS or lowered.endswith(_LOOPBACK_SUFFIX):
        return True
    try:
        return ipaddress.ip_address(lowered).is_loopback
    except ValueError:
        return False


def _checked_base_url(variable: str, raw: str, operation: str) -> str:
    """Judge the endpoint a key may travel to, refusing before it can be sent.

    Everything checked here is about the one risk a base URL carries: that the operator's
    credential leaves the machine in a form anyone between here and there can read. A
    userinfo component is a credential written into the URL itself. Plain `http` to any
    host but this machine is a plaintext hop across a network, which would carry the key off
    the machine in the `Authorization` header where anything on the path can read it — the
    reason this refusal exists and the reason it is not a warning. `https` to a remote host
    is allowed because the TLS record is what makes that hop unreadable. A query or fragment
    on a *configured root* is refused because the request path is this module's to build:
    a root arriving with one is a pasted URL rather than a configured endpoint, and a query
    is exactly where a key would be pasted.
    """

    url = raw.strip()
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        raise _reject(
            operation, f"{ConfigRefusal.BAD_URL}: {variable} could not be parsed"
        ) from None
    if parsed.scheme not in ("http", "https"):
        raise _reject(
            operation,
            f"{ConfigRefusal.BAD_URL}: {variable} must be an http or https URL, "
            f"got {parsed.scheme or 'no scheme'}",
        )
    if not parsed.netloc:
        raise _reject(operation, f"{ConfigRefusal.BAD_URL}: {variable} names no host")
    if parsed.username or parsed.password:
        raise _reject(operation, f"{ConfigRefusal.BAD_URL}: {variable} must not carry credentials")
    if parsed.query or parsed.fragment:
        raise _reject(
            operation, f"{ConfigRefusal.BAD_URL}: {variable} must not carry a query or fragment"
        )
    if parsed.scheme == "http" and not is_loopback_host(parsed.hostname or ""):
        raise _reject(
            operation,
            f"{ConfigRefusal.BAD_URL}: {variable} is plain http to a host that is not this "
            "machine; the call would carry the key across a readable hop",
        )
    return url.rstrip("/")


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """What the operator says about models — and every field is safe to log.

    These named settings and numeric budget/rate values are the surface this build holds about a
    model endpoint. No field is a secret and none can become one: `api_key_env` is the
    *name* of the variable holding the key, so `repr()` of a config, of anything embedding
    one, and of any refusal raised while reading one all print the name. The key itself is
    deliberately not a field, because `dataclass` synthesises `repr()` from the fields — a
    key field would appear in every debug log and in any run document that projected the
    config, which is precisely the leak §1 forbids. `key_for` reads it at the moment a
    request is being sent instead, and nothing holds it afterwards.
    """

    #: `off` or `openai_compatible` (`KNOWN_PROVIDERS`); `off` is the default.
    provider: ProviderName = PROVIDER_OFF
    #: The endpoint root; the provider appends `/chat/completions` to it.
    base_url: str = ""
    #: The model name the endpoint is asked for.
    model: str = ""
    #: The NAME of the environment variable holding the key, never the key.
    api_key_env: str = ""
    #: One call's wall-clock limit.
    timeout_ms: int = DEFAULT_MODEL_TIMEOUT_MS
    #: How many attempts one decision call may make (1..`MAX_MODEL_ATTEMPTS`); a retry only
    #: ever re-asks the endpoint for a decision, never re-runs a skill.
    max_attempts: int = DEFAULT_MODEL_MAX_ATTEMPTS
    #: One run's spend limit, in micro-currency; see `DEFAULT_RUN_COST_CAP_MICRO`.
    run_cost_cap: int = DEFAULT_RUN_COST_CAP_MICRO
    request_micro_per_million_tokens: int = DEFAULT_REQUEST_MICRO_PER_MILLION_TOKENS
    response_micro_per_million_tokens: int = DEFAULT_RESPONSE_MICRO_PER_MILLION_TOKENS

    @property
    def enabled(self) -> bool:
        """Whether a model exists for this build to ask anything of."""

        return self.provider != PROVIDER_OFF


def model_config(environ: Mapping[str, str] | None = None) -> ModelConfig:
    """Read the model configuration, defaulting to no model at all.

    Permissive about the shape a machine without credentials has, refusing about an
    operator's mistakes. Under `off` the other six variables are not read at all: nothing is
    contacted, so a stale `MINEKIN_MODEL_TIMEOUT_MS` left in a shell profile or a CI image
    cannot stop a run that was never going to use it. That is what makes `off` a capability
    rather than a missing dependency. A non-`off` provider with no endpoint or no model name
    is a half-entered configuration and refuses with `MODEL_NOT_CONFIGURED` naming the
    variables that are missing.

    Reading this creates nothing: no directory, no file, no connection — and it never
    resolves the key.
    """

    source = os.environ if environ is None else environ
    raw_provider = source.get(MODEL_PROVIDER_VARIABLE, "").strip()
    provider: ProviderName = PROVIDER_OFF if not raw_provider else cast(ProviderName, raw_provider)
    if provider not in KNOWN_PROVIDERS:
        raise _reject(
            "resolve",
            f"{ConfigRefusal.UNKNOWN_PROVIDER}: {MODEL_PROVIDER_VARIABLE} is "
            f"{_shown(raw_provider)}, not one of {' or '.join(KNOWN_PROVIDERS)}",
        )
    if provider == PROVIDER_OFF:
        # The whole of the `off` path: one variable read, no validation of anything an unused
        # endpoint would have needed, and no way for it to raise.
        return ModelConfig(provider=PROVIDER_OFF)

    base_url = source.get(MODEL_BASE_URL_VARIABLE, "").strip()
    model = source.get(MODEL_VARIABLE, "").strip()
    missing = [
        name
        for name, value in ((MODEL_BASE_URL_VARIABLE, base_url), (MODEL_VARIABLE, model))
        if not value
    ]
    if missing:
        raise _reject(
            "resolve",
            f"{ConfigRefusal.NOT_CONFIGURED}: provider {provider} requires {', '.join(missing)}",
        )
    base_url = _checked_base_url(MODEL_BASE_URL_VARIABLE, base_url, "resolve")

    api_key_env = source.get(MODEL_API_KEY_ENV_VARIABLE, "").strip()
    if api_key_env and not _ENV_NAME.fullmatch(api_key_env):
        # Judged as a name, not as a value: an operator who pasted the key itself here would
        # otherwise put it into every `repr()` this module exists to keep clean — and it
        # would not work anyway, since the variable holding it does not have that shape.
        raise _reject(
            "resolve",
            f"{ConfigRefusal.BAD_ENV_NAME}: {MODEL_API_KEY_ENV_VARIABLE} must name an "
            "environment variable (a leading letter or underscore, then letters, digits "
            "and underscores); it holds a name, not the key",
        )

    raw_timeout = source.get(MODEL_TIMEOUT_MS_VARIABLE, "").strip()
    timeout_ms = (
        _positive_int(MODEL_TIMEOUT_MS_VARIABLE, raw_timeout, "resolve")
        if raw_timeout
        else DEFAULT_MODEL_TIMEOUT_MS
    )
    raw_attempts = source.get(MODEL_MAX_ATTEMPTS_VARIABLE, "").strip()
    max_attempts = (
        _positive_int(MODEL_MAX_ATTEMPTS_VARIABLE, raw_attempts, "resolve")
        if raw_attempts
        else DEFAULT_MODEL_MAX_ATTEMPTS
    )
    if max_attempts > MAX_MODEL_ATTEMPTS:
        raise _reject(
            "resolve",
            f"{ConfigRefusal.BAD_NUMBER}: {MODEL_MAX_ATTEMPTS_VARIABLE} must be between 1 "
            f"and {MAX_MODEL_ATTEMPTS}",
        )
    raw_cap = source.get(MODEL_RUN_COST_CAP_VARIABLE, "").strip()
    run_cost_cap = (
        _positive_int(MODEL_RUN_COST_CAP_VARIABLE, raw_cap, "resolve")
        if raw_cap
        else DEFAULT_RUN_COST_CAP_MICRO
    )

    return ModelConfig(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key_env=api_key_env,
        timeout_ms=timeout_ms,
        max_attempts=max_attempts,
        run_cost_cap=run_cost_cap,
        request_micro_per_million_tokens=_configured_rate(
            source, MODEL_REQUEST_RATE_VARIABLE, DEFAULT_REQUEST_MICRO_PER_MILLION_TOKENS
        ),
        response_micro_per_million_tokens=_configured_rate(
            source, MODEL_RESPONSE_RATE_VARIABLE, DEFAULT_RESPONSE_MICRO_PER_MILLION_TOKENS
        ),
    )


def _configured_rate(source: Mapping[str, str], variable: str, default: int) -> int:
    raw = source.get(variable, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if not 0 <= value <= 1_000_000_000:
        raise _reject(
            "resolve",
            f"{ConfigRefusal.BAD_NUMBER}: {variable} must be an integer between 0 and 1000000000",
        )
    return value


def key_for(config: ModelConfig, environ: Mapping[str, str] | None = None) -> str | None:
    """Resolve the key at the one moment a request is about to be sent.

    `None` means "ask this endpoint without a credential": an empty `api_key_env`, or a
    provider that is `off` and so has no hop the key could travel over. A *named* variable
    that is absent is operator misconfiguration and refuses with a `MinekinError` — the
    caller turns that into `ModelUnavailable` and keeps playing, but it must not silently
    send an unauthenticated request to an endpoint that expects one.

    THE ONE PLACE. This is the only read of a secret from the environment in this package,
    and the refusal raised from it is assembled from the variable's name alone, so the value
    cannot reach its message even by an accident of string interpolation.
    """

    source = os.environ if environ is None else environ
    if not config.enabled or not config.api_key_env:
        return None
    name = config.api_key_env
    value = source.get(name)  # the only secret read in the model surface
    if value is None or not value.strip():
        raise MinekinError(
            component="model.key",
            operation="resolve",
            category=ErrorCategory.CONFIG,
            retryability=Retryability.OPERATOR_ACTION,
            safe_message=(
                f"{ConfigRefusal.NOT_CONFIGURED}: {MODEL_API_KEY_ENV_VARIABLE} names {name}, "
                "which is not set in this environment"
            ),
            context={"api_key_env": name},
        )
    return value.strip()


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    """Everything the model is shown, and everything it is allowed to choose between.

    The request is the whole of the model's world for one call, so it is worth naming what
    is *not* in it: no coordinates, no skill the local layer has not already found feasible,
    and no credential. What it does carry is the `observation_summary` — the counts and names
    this side read off the newest player-equivalent reading — because an answerer asked to
    choose a craft cannot be asked to guess what the bag holds. A summary of facts the Kin
    actually has is the difference between a decision and a hallucination, and it is also the
    reason the answer's arguments can be checked rather than merely shaped: the same reading
    that produced the numbers is the one the local layer checks them against.

    The invariants are internal ones and raise `ValueError` in the style of `domain/ids.py`:
    a request that cannot be judged is a caller bug, and it is caught before any money is
    spent answering it.
    """

    #: A reference to the observation summary this was built from, as well as the summary itself.
    observation_ref: str
    #: Need name to urgency. An ordering signal and nothing else — the numbers never
    #: become dialogue (§3).
    needs: Mapping[str, int] = field(default_factory=dict[str, int])
    #: The long-running direction this intent is meant to advance, as the scheduler holds it.
    active_goal: str = ""
    #: The feasible skill ids, computed locally. The provider may only choose inside these.
    feasible_skill_ids: tuple[str, ...] = ()
    #: What this side read, in the fields an answerer needs to fill an argument in: item counts,
    #: which of them a craft could turn into, what is aimed at, what is in hand. Built by
    #: `application.player_mind`, which is the only layer holding the reading.
    observation_summary: Mapping[str, object] = field(default_factory=dict[str, object])
    #: The persisted persona seed, so the same Kin answers differently.
    persona_seed: str = ""
    #: What is left of the run cap when the request was built. Advisory: it informs the
    #: model, while `CostLedger` is what actually stops a call.
    budget_remaining_micro: int = 0
    #: The generation these keys would be issued for; an answer from another is late.
    intent_generation: int = 1
    #: Trusted persisted tendencies, not a model-authored personality or a fresh seed draw.
    persona: PersonaManifest | None = None
    #: Historical software lifecycle only; never current inventory, locations or permissions.
    session_history: Mapping[str, object] = field(default_factory=dict[str, object])

    def __post_init__(self) -> None:
        if not self.observation_ref:
            raise ValueError("a decision request must name the observation it came from")
        if self.intent_generation < 1:
            raise ValueError("intent_generation starts at one; zero means not supplied")
        if self.budget_remaining_micro < 0:
            raise ValueError("the remaining budget cannot be negative")
        if len(self.feasible_skill_ids) > MAX_FEASIBLE_SKILLS:
            raise ValueError(f"the feasible set is bounded at {MAX_FEASIBLE_SKILLS} skills")
        if any(not skill_id for skill_id in self.feasible_skill_ids):
            raise ValueError("the feasible set cannot contain an unnamed skill")
        if any(urgency < 0 for urgency in self.needs.values()):
            raise ValueError("need urgency cannot be negative")


@dataclass(frozen=True, slots=True)
class Decision:
    """A structured intent — never a keystroke.

    `skill_id` is a request to the task adapter, which re-checks its own preconditions and
    reports what actually happened; a decision's existence does not mean the action will.

    `arguments` is the ask, in the vocabulary `domain.skill_parameters` declares for the chosen
    skill — `{"target_item": "minecraft:stick", "quantity": 2}` says what the answerer wants to
    end up holding and how much of it, and says nothing about which recipe that is, which items
    it eats, or which slot gets clicked. Those four are this side's job: the catalog resolves the
    recipe, the newest reading decides whether the bag can pay, the skill layer opens the screen,
    and a later reading decides whether it happened. An answer that has no arguments is a
    complete sentence for the skills that take none and is honoured as such.
    """

    skill_id: str
    reason: str
    intent_generation: int
    arguments: Mapping[str, object] = field(default_factory=dict[str, object])
    #: The commitment candidate the answer attached, as it read: bounded and redacted on
    #: the way in, and judged by nobody — `domain.commitment` is the one reader of what it
    #: may contain, and the session layer is the only recorder of the verdict. `None` means
    #: the answer proposed none.
    commitment: object | None = None

    def as_document(self) -> dict[str, object]:
        return {
            "skill_id": self.skill_id,
            "reason": self.reason,
            "intent_generation": self.intent_generation,
            "arguments": dict(self.arguments),
        }


@dataclass(frozen=True, slots=True)
class ModelUnavailable:
    """No decision, with the name of why.

    There is no free-text field on this type at all. The reason is one of
    `UnavailableReason` and the status is an integer, so `repr()` of it — and of anything
    holding it — cannot reproduce a response body, an echoed prompt, or a credential.
    Providers do echo requests back inside their errors, which is why this shape is a rule
    rather than a preference.
    """

    reason: UnavailableReason
    #: Kept for the non-2xx case, where which status it was is the whole of the diagnosis.
    status_code: int | None = None

    @property
    def outcome(self) -> CallOutcome:
        """How this is filed in the ledger.

        A non-2xx splits on its own: 4xx says this side asked wrongly (rejected), 5xx says
        the endpoint could not answer (unavailable). Both take the same conservative path in
        the game loop and are different things to fix.
        """

        if self.reason is UnavailableReason.PROVIDER_STATUS:
            code = self.status_code or 0
            return CallOutcome.REJECTED if 400 <= code < 500 else CallOutcome.UNAVAILABLE
        return _OUTCOME_BY_REASON[self.reason]

    def as_document(self) -> dict[str, object]:
        return {
            "reason": self.reason.value,
            "status_code": self.status_code,
            "outcome": self.outcome.value,
        }


#: How much of an attached commitment candidate is even carried toward the gate, and how
#: many of its fields. The candidate is remote text headed for a durable row, so it is
#: redacted and shrunk here; whether it may BECOME a commitment is `domain.commitment`'s
#: decision, and every refusal it names is recorded by the caller rather than swallowed.
_COMMITMENT_ECHO_CHARS: Final = 512
_COMMITMENT_ECHO_KEYS: Final = 8


def _bounded_commitment(value: object, *, secrets: tuple[str, ...]) -> object | None:
    """The answer's commitment field, redacted and shrunk for the road — never judged here.

    A non-object value is carried as it read rather than collapsed to nothing: "the answer
    attached a commitment field of the wrong shape" is a refusal the gate must be able to
    name, and a field that vanished here could never be refused by name at all.
    """

    if value is None:
        return None
    if isinstance(value, str):
        return redact_text(value, secrets=secrets)[:_COMMITMENT_ECHO_CHARS]
    if not isinstance(value, Mapping):
        return value
    fields = cast("Mapping[str, Any]", value)
    echo: dict[str, object] = {}
    for key, item in list(fields.items())[:_COMMITMENT_ECHO_KEYS]:
        # Key names are remote text too, and one of them could be an echoed credential;
        # they are redacted on the same rule as the values before anything holds them.
        name = redact_text(key, secrets=secrets)[:64]
        if isinstance(item, str):
            echo[name] = redact_text(item, secrets=secrets)[:_COMMITMENT_ECHO_CHARS]
        else:
            echo[name] = item
    return echo


def compose_decision(
    request: DecisionRequest,
    skill_id: str,
    reason: str,
    intent_generation: int | None = None,
    *,
    arguments: Mapping[str, object] | None = None,
    commitment: object | None = None,
    secrets: tuple[str, ...] = (),
) -> Decision | ModelUnavailable:
    """Judge one proposed choice, and the ask that came with it, against the offer.

    Five refusals, all enforced here instead of left to the caller's discipline:
    `DECISION_OUT_OF_BOUNDS` for a skill the local layer never offered, `STALE_GENERATION` for
    an answer belonging to another intent, and the three `MODEL_ARGUMENTS_*` names for an ask
    whose keys, required arguments or value ranges this side cannot honour. A `None` generation
    means this call's own — the port stamps the number, so a provider that never saw one cannot
    quietly answer for a cancelled intent, while an answer that does carry one is checked
    against the request rather than trusted.

    The argument check is the reason the port and not the mind owns this. `craft(target_item)`
    is only a request to look a recipe up, and a lookup on a value that arrived as remote text
    is the one place an invented item id could turn into a click; refusing it here means no
    caller — present or future — has to remember to sanitise. A skill this build does not
    declare parameters for is checked as far as it can be: an empty ask passes, a non-empty one
    is `MODEL_ARGUMENTS_UNKNOWN`, because this side has no declaration that would say what the
    extra key means.

    The reason is remote text headed for a log line, so it is redacted and then bounded before
    anything holds it. A provider sits behind a proxy that may echo a request header back
    inside a completion, so `redact_text` runs on the whole string with the secrets the caller
    sent (`secrets`, which the provider fills with the key it just put on the wire) and only
    afterwards is it cut to length — cutting first would let a slice of a credential survive
    as a fragment too short for any pattern to recognise.

    The commitment a decision may carry rides under the same rule — redacted and bounded
    here, and unjudged on purpose: the schema, budgets and evidence check for commitments
    live in `domain.commitment`, so the answer's suggestion never bypasses a gate by
    arriving through this one.
    """

    supplied = request.intent_generation if intent_generation is None else intent_generation
    if supplied != request.intent_generation:
        return ModelUnavailable(UnavailableReason.STALE_GENERATION)
    if skill_id not in request.feasible_skill_ids:
        return ModelUnavailable(UnavailableReason.DECISION_OUT_OF_BOUNDS)
    given = {} if arguments is None else dict(arguments)
    honoured = validate_arguments(skill_id, given)
    if isinstance(honoured, str):
        return ModelUnavailable(UnavailableReason(honoured))
    return Decision(
        skill_id=skill_id,
        reason=redact_text(reason, secrets=secrets)[:MAX_REASON_CHARS],
        intent_generation=request.intent_generation,
        arguments=honoured,
        commitment=_bounded_commitment(commitment, secrets=secrets),
    )


def estimate_cost_micro(
    request_tokens: int | None,
    response_tokens: int | None,
    request_micro_per_million_tokens: int,
    response_micro_per_million_tokens: int,
) -> int:
    """What the reported tokens cost, rounded up into micro-currency.

    A count the provider did not report contributes nothing, and the ledger says separately
    which counts it was given: an unpriced call then reads as unpriced instead of reading as
    a free one.
    """

    request_part = math.ceil(
        (request_tokens or 0) * request_micro_per_million_tokens / TOKENS_PER_MILLION
    )
    response_part = math.ceil(
        (response_tokens or 0) * response_micro_per_million_tokens / TOKENS_PER_MILLION
    )
    return request_part + response_part


@dataclass(frozen=True, slots=True)
class CostRecord:
    """One call, remembered in the shape §4 of the contract asks for.

    None of it is provider text: token counts are integers or absent, the cost is
    arithmetic over this side's own stated rates, the generation and outcome are ours, and
    the reason is enumerated. That is what lets a list of records be projected into the
    dashboard, the run document and a traceback without a second review of each.
    """

    provider: ProviderName
    model: str
    request_tokens: int | None
    response_tokens: int | None
    estimated_cost: int
    intent_generation: int
    outcome: CallOutcome
    reason: UnavailableReason | None = None
    status_code: int | None = None
    #: The redacted diagnostics of the call: numbers and this side's own tokens only. How many
    #: attempts it took, the per-attempt wall-clock budget, the whole call's elapsed time, and
    #: the phase of the last failed attempt ("open" while awaiting the response head, "read"
    #: while reading the body, "status" for a refused status). None when a reader never ran.
    attempts: int | None = None
    timeout_ms: int | None = None
    elapsed_ms: int | None = None
    phase: str | None = None
    #: How many bytes this side put on the wire for the call. Recorded even when the
    #: call timed out, because that is the fact a stall window is argued about with:
    #: the ask's size, this side's own number, no provider text.
    request_bytes: int | None = None

    def as_document(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "request_tokens": self.request_tokens,
            "response_tokens": self.response_tokens,
            "estimated_cost": self.estimated_cost,
            "intent_generation": self.intent_generation,
            "outcome": self.outcome.value,
            "reason": self.reason.value if self.reason is not None else None,
            "status_code": self.status_code,
            "attempts": self.attempts,
            "timeout_ms": self.timeout_ms,
            "elapsed_ms": self.elapsed_ms,
            "phase": self.phase,
            "request_bytes": self.request_bytes,
        }


@dataclass(slots=True)
class CostLedger:
    """One run's model spend, and the gate that stops paying for more.

    `may_start_call` is consulted before a request is built, so the cap stops *calls*.
    When it says no the caller gets `ModelUnavailable(RUN_COST_CAP_REACHED)` and a record
    costing nothing: the Kin keeps reflecting, keeps its approved skills, keeps its
    conservative actions and keeps playing. **This refuses calls, not the game** — it must
    never read as though the Kin had stopped, which is why the refusal is recorded, counted
    and projected rather than swallowed.
    """

    run_cost_cap: int
    request_micro_per_million_tokens: int = DEFAULT_REQUEST_MICRO_PER_MILLION_TOKENS
    response_micro_per_million_tokens: int = DEFAULT_RESPONSE_MICRO_PER_MILLION_TOKENS
    records: list[CostRecord] = field(default_factory=list[CostRecord])

    def __post_init__(self) -> None:
        if self.run_cost_cap <= 0:
            raise ValueError("the run cost cap must be a positive integer")
        if self.request_micro_per_million_tokens < 0:
            raise ValueError("the request token rate cannot be negative")
        if self.response_micro_per_million_tokens < 0:
            raise ValueError("the response token rate cannot be negative")

    @property
    def spent(self) -> int:
        return sum(record.estimated_cost for record in self.records)

    def remaining(self) -> int:
        """What is left of the cap, floored at zero; feeds `budget_remaining_micro`."""

        return max(0, self.run_cost_cap - self.spent)

    def may_start_call(self) -> bool:
        """Whether a call may be started at all.

        The contract's word is "exceeded", so spend up to and including the cap is honoured
        and the state that first goes past it is what refuses. A run that spent exactly its
        cap has nothing left to spend and says so by name.
        """

        return self.spent <= self.run_cost_cap

    def estimate(self, request_tokens: int | None, response_tokens: int | None) -> int:
        return estimate_cost_micro(
            request_tokens,
            response_tokens,
            self.request_micro_per_million_tokens,
            self.response_micro_per_million_tokens,
        )

    def record(self, record: CostRecord) -> CostRecord:
        """Append one call's outcome, whatever it was, and hand it back.

        Appending is not validation: a caller that reports a token count it invented gets it
        into the projection. What the type guarantees is that no record can carry remote
        text, because `CostRecord` has no field for it.
        """

        self.records.append(record)
        return record

    def record_call(
        self,
        provider: ProviderName,
        model: str,
        intent_generation: int,
        outcome: CallOutcome,
        *,
        request_tokens: int | None = None,
        response_tokens: int | None = None,
        reason: UnavailableReason | None = None,
        status_code: int | None = None,
        attempts: int | None = None,
        timeout_ms: int | None = None,
        elapsed_ms: int | None = None,
        phase: str | None = None,
        request_bytes: int | None = None,
    ) -> CostRecord:
        """Price what the provider reported and append it, in one step.

        Every call the provider makes ends here, including the ones that produced nothing:
        a timeout that spent nothing still belongs in the run's account, because a dashboard
        that shows no calls while the model was being asked is showing a false peace.
        """

        return self.record(
            CostRecord(
                provider=provider,
                model=model,
                request_tokens=request_tokens,
                response_tokens=response_tokens,
                estimated_cost=self.estimate(request_tokens, response_tokens),
                attempts=attempts,
                timeout_ms=timeout_ms,
                elapsed_ms=elapsed_ms,
                phase=phase,
                request_bytes=request_bytes,
                intent_generation=intent_generation,
                outcome=outcome,
                reason=reason,
                status_code=status_code,
            )
        )

    @property
    def calls(self) -> int:
        """Calls that actually left for an endpoint; cap refusals are not among them."""

        return len(self.records) - self.cap_refusals

    @property
    def cap_refusals(self) -> int:
        return sum(
            1 for record in self.records if record.reason is UnavailableReason.RUN_COST_CAP_REACHED
        )

    def by_generation(self, intent_generation: int) -> tuple[CostRecord, ...]:
        return tuple(
            record for record in self.records if record.intent_generation == intent_generation
        )

    def as_document(self) -> Mapping[str, object]:
        """The read-only projection the dashboard is allowed to show (§4 and §5).

        The rates travel with the numbers, because a cost without its rate is a claim.
        `cap_reached` is stated so that a run which stopped paying for calls says so itself
        rather than looking like a run that stopped playing.
        """

        outcomes: dict[str, int] = {outcome.value: 0 for outcome in CallOutcome}
        reasons: dict[str, int] = {}
        for record in self.records:
            outcomes[record.outcome.value] += 1
            if record.reason is not None:
                reasons[record.reason.value] = reasons.get(record.reason.value, 0) + 1
        return {
            "unit": "micro-currency, in the unit the operator states the cap in",
            "run_cost_cap": self.run_cost_cap,
            "spent_estimate": self.spent,
            "remaining": self.remaining(),
            "cap_reached": not self.may_start_call(),
            "calls": self.calls,
            "cap_refusals": self.cap_refusals,
            "request_micro_per_million_tokens": self.request_micro_per_million_tokens,
            "response_micro_per_million_tokens": self.response_micro_per_million_tokens,
            "outcome_counts": outcomes,
            "reason_counts": reasons,
            "records": [record.as_document() for record in self.records],
        }


def cost_ledger_for(config: ModelConfig) -> CostLedger:
    """A ledger using this run's configured cap and operator-supplied estimate rates."""

    return CostLedger(
        run_cost_cap=config.run_cost_cap,
        request_micro_per_million_tokens=config.request_micro_per_million_tokens,
        response_micro_per_million_tokens=config.response_micro_per_million_tokens,
    )
