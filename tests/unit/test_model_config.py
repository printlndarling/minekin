"""Reading the model configuration, and the gate a decision has to pass.

`docs/s3-minimal-player-mind.md` §1 and §2 are both about things that must not be able to hurt
a run, so this file tests two properties rather than a table of values:

**Configuration cannot fail open or leak.** `off` is the shape a machine with no credentials
has and must never raise. A half-entered non-`off` provider refuses with `MODEL_NOT_CONFIGURED`
naming what is missing. And a refusal, a `repr()` or a logged config must not be able to carry
a credential — including when the operator put a credential in the wrong variable, which is the
case that would otherwise leak it through the very message meant to report the mistake.

**Choosing is bounded by what was offered.** A skill the local layer never named is
`DECISION_OUT_OF_BOUNDS`, an answer from another intent generation is stale and dropped, and
neither is an exception.

The decision gate is tested here with the configuration because the two share one contract:
nothing about a model may reach the game loop as a raised error.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterator, Mapping
from dataclasses import fields
from typing import Any, cast

import pytest

from minekin_core.domain import model_access
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.model_access import (
    DEFAULT_MODEL_MAX_ATTEMPTS,
    DEFAULT_MODEL_TIMEOUT_MS,
    DEFAULT_RUN_COST_CAP_MICRO,
    KNOWN_PROVIDERS,
    MAX_FEASIBLE_SKILLS,
    MAX_REASON_CHARS,
    MODEL_API_KEY_ENV_VARIABLE,
    MODEL_BASE_URL_VARIABLE,
    MODEL_MAX_ATTEMPTS_VARIABLE,
    MODEL_PROVIDER_VARIABLE,
    MODEL_REQUEST_RATE_VARIABLE,
    MODEL_RESPONSE_RATE_VARIABLE,
    MODEL_RUN_COST_CAP_VARIABLE,
    MODEL_TIMEOUT_MS_VARIABLE,
    MODEL_VARIABLE,
    PROVIDER_OFF,
    PROVIDER_OPENAI_COMPATIBLE,
    CallOutcome,
    Decision,
    DecisionRequest,
    ModelConfig,
    ModelUnavailable,
    UnavailableReason,
    compose_decision,
    key_for,
    model_config,
)

#: A distinctive value standing in for a real credential: recognizable, long enough to slice
#: into substrings, and never legitimate in any string this module produces.
FAKE_KEY: str = "sk-FAKE-9bQ2t7Lm4XwR8Kd3Zp6V"
FAKE_KEY_VARIABLE: str = "MINEKIN_MODEL_API_KEY"

CONFIG_VARIABLES = frozenset(
    {
        MODEL_PROVIDER_VARIABLE,
        MODEL_BASE_URL_VARIABLE,
        MODEL_VARIABLE,
        MODEL_API_KEY_ENV_VARIABLE,
        MODEL_MAX_ATTEMPTS_VARIABLE,
        MODEL_TIMEOUT_MS_VARIABLE,
        MODEL_RUN_COST_CAP_VARIABLE,
        MODEL_REQUEST_RATE_VARIABLE,
        MODEL_RESPONSE_RATE_VARIABLE,
    }
)

OPENAI_ENV: Mapping[str, str] = {
    MODEL_PROVIDER_VARIABLE: PROVIDER_OPENAI_COMPATIBLE,
    MODEL_BASE_URL_VARIABLE: "http://127.0.0.1:8321/v1",
    MODEL_VARIABLE: "kin-test-model",
}


class ReadLog(Mapping[str, str]):
    """An environment that records which names were read.

    This is how "the key is resolved only when a request is being sent" gets proved instead of
    asserted. `Mapping.get` routes through `__getitem__`, so a read of the credential shows up
    here whether the code asked directly or through a helper.
    """

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)
        self.read: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.read.append(key)
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def refusal(action: Callable[[], Any]) -> str:
    """Run something expected to refuse, and return the message an operator would read."""

    with pytest.raises(MinekinError) as caught:
        action()
    error = caught.value
    assert error.category is ErrorCategory.CONFIG
    return error.safe_message


# ---------------------------------------------------------------------------
# §1: what the environment says
# ---------------------------------------------------------------------------


def test_an_empty_environment_is_no_model_and_never_raises() -> None:
    """A machine without credentials is the common case, not a failure."""

    config = model_config({})

    assert config.provider == PROVIDER_OFF
    assert config.base_url == ""
    assert config.model == ""
    assert not config.enabled
    assert config.timeout_ms == DEFAULT_MODEL_TIMEOUT_MS
    assert config.run_cost_cap == DEFAULT_RUN_COST_CAP_MICRO


@pytest.mark.parametrize("raw", ["", "   ", PROVIDER_OFF])
def test_unset_blank_and_explicit_off_all_mean_the_same_provider(raw: str) -> None:
    config = model_config({MODEL_PROVIDER_VARIABLE: raw})

    assert config.provider == PROVIDER_OFF
    assert not config.enabled


def test_no_model_config_is_never_validated_because_it_is_never_contacted() -> None:
    """`off` with nonsense beside it must not raise: off means nothing is contacted.

    Validating an unused configuration would turn a stale variable in someone's shell profile
    into a stopped Kin, which is the failure mode §1 names specifically. Only the provider
    variable is even read.
    """

    environment = ReadLog(
        {
            MODEL_PROVIDER_VARIABLE: PROVIDER_OFF,
            MODEL_BASE_URL_VARIABLE: "http://api.example.com/v1",
            MODEL_TIMEOUT_MS_VARIABLE: "not a number",
            MODEL_RUN_COST_CAP_VARIABLE: "-1",
            MODEL_API_KEY_ENV_VARIABLE: FAKE_KEY,
        }
    )

    config = model_config(environment)

    assert not config.enabled
    assert environment.read == [MODEL_PROVIDER_VARIABLE]


def test_a_named_non_off_provider_needs_an_endpoint_and_a_model_name() -> None:
    """Half an entry is worse than none: it says an endpoint was meant to be reached."""

    message = refusal(lambda: model_config({MODEL_PROVIDER_VARIABLE: PROVIDER_OPENAI_COMPATIBLE}))

    assert "MODEL_NOT_CONFIGURED" in message
    assert MODEL_BASE_URL_VARIABLE in message
    assert MODEL_VARIABLE in message


def test_a_configured_endpoint_keeps_what_the_operator_named() -> None:
    config = model_config({**OPENAI_ENV, MODEL_API_KEY_ENV_VARIABLE: FAKE_KEY_VARIABLE})

    assert config.provider == PROVIDER_OPENAI_COMPATIBLE
    assert config.enabled
    assert config.base_url == "http://127.0.0.1:8321/v1"
    assert config.model == "kin-test-model"
    assert config.api_key_env == FAKE_KEY_VARIABLE


def test_a_trailing_slash_on_the_root_does_not_double_the_path() -> None:
    config = model_config({**OPENAI_ENV, MODEL_BASE_URL_VARIABLE: "http://localhost:9/v1/"})

    assert config.base_url == "http://localhost:9/v1"


def test_an_unknown_provider_is_a_named_refusal_not_a_silently_off_run() -> None:
    message = refusal(lambda: model_config({MODEL_PROVIDER_VARIABLE: "anthropic"}))

    assert "MODEL_PROVIDER_UNKNOWN" in message
    for name in KNOWN_PROVIDERS:
        assert name in message


def test_a_pasted_key_in_the_provider_slot_stays_out_of_the_refusal() -> None:
    """The mistake guarded against is pasting the credential into the wrong variable.

    The refusal says the value was not a provider name and how long it was, without repeating
    it — the message is logged, and no shape filter makes quoting safe, since a plain
    upper-case twenty-character string can be both a name and an AWS key.
    """

    message = refusal(lambda: model_config({MODEL_PROVIDER_VARIABLE: FAKE_KEY}))

    assert FAKE_KEY not in message
    assert "MODEL_PROVIDER_UNKNOWN" in message
    assert MODEL_PROVIDER_VARIABLE in message
    assert f"a {len(FAKE_KEY)}-character value" in message


def test_a_pasted_key_in_a_number_slot_stays_out_of_the_refusal() -> None:
    message = refusal(lambda: model_config({**OPENAI_ENV, MODEL_TIMEOUT_MS_VARIABLE: FAKE_KEY}))

    assert FAKE_KEY not in message
    assert "MODEL_NUMBER_INVALID" in message
    assert MODEL_TIMEOUT_MS_VARIABLE in message


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        (MODEL_TIMEOUT_MS_VARIABLE, "0"),
        (MODEL_TIMEOUT_MS_VARIABLE, "-1"),
        (MODEL_TIMEOUT_MS_VARIABLE, "eight seconds"),
        (MODEL_TIMEOUT_MS_VARIABLE, "8.5"),
        (MODEL_RUN_COST_CAP_VARIABLE, "0"),
        (MODEL_RUN_COST_CAP_VARIABLE, "-500"),
        (MODEL_RUN_COST_CAP_VARIABLE, "many"),
    ],
)
def test_the_two_numbers_must_be_positive_integers(variable: str, value: str) -> None:
    message = refusal(lambda: model_config({**OPENAI_ENV, variable: value}))

    assert "MODEL_NUMBER_INVALID" in message
    assert variable in message


def test_a_number_with_stray_spaces_is_still_the_number_it_names() -> None:
    config = model_config({**OPENAI_ENV, MODEL_TIMEOUT_MS_VARIABLE: " 250 "})

    assert config.timeout_ms == 250


# ---------------------------------------------------------------------------
# §1: the endpoint a key may travel to
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8321/v1",
        "http://localhost:8321/v1",
        "http://kin.localhost:8321/v1",
        "http://127.5.5.5/v1",
        "http://[::1]:8321/v1",
        "https://example.invalid/v1",
        "https://127.0.0.1/v1",
    ],
)
def test_an_endpoint_this_build_will_send_a_key_to(url: str) -> None:
    """Loopback in plain http, or anything over https: the key stays unreadable in transit."""

    config = model_config({**OPENAI_ENV, MODEL_BASE_URL_VARIABLE: url})

    assert config.base_url == url.rstrip("/")


@pytest.mark.parametrize(
    ("url", "why"),
    [
        ("ftp://127.0.0.1/v1", "got ftp"),
        ("127.0.0.1:8321", "no scheme"),
        ("http://", "no host"),
    ],
)
def test_a_base_url_that_is_not_an_http_root_is_refused(url: str, why: str) -> None:
    message = refusal(lambda: model_config({**OPENAI_ENV, MODEL_BASE_URL_VARIABLE: url}))

    assert "MODEL_URL_INVALID" in message
    assert why in message


def test_plain_http_to_another_machine_is_refused_because_it_would_carry_the_key_off() -> None:
    """The plaintext hop is the one risk a base URL carries, so it is a refusal not a warning.

    `http://api.example.com` would put the `Authorization` header on a link anything between
    this machine and there can read. §1 says the key must never leave Core's control, and a
    configuration that guarantees it does cannot be accepted.
    """

    message = refusal(
        lambda: model_config({**OPENAI_ENV, MODEL_BASE_URL_VARIABLE: "http://api.example.com/v1"})
    )

    assert "MODEL_URL_INVALID" in message
    assert "readable hop" in message


@pytest.mark.parametrize(
    "url",
    [
        "http://user:pass@127.0.0.1:8321/v1",
        "http://:secret@127.0.0.1:8321/v1",
        "http://127.0.0.1:8321/v1?key=abc",
        "http://127.0.0.1:8321/v1#frag",
    ],
)
def test_credentials_or_a_query_in_the_configured_root_are_refused(url: str) -> None:
    """A root arriving with userinfo or a query is a pasted URL, and a query is where a key
    would be pasted. The request path is this module's to build, so neither is honoured."""

    message = refusal(lambda: model_config({**OPENAI_ENV, MODEL_BASE_URL_VARIABLE: url}))

    assert "MODEL_URL_INVALID" in message


# ---------------------------------------------------------------------------
# §1: the key, which is only ever resolved in order to be sent
# ---------------------------------------------------------------------------


def test_the_key_variable_is_named_by_another_variable_and_never_stored() -> None:
    """A value pasted into the name slot is refused before it can be `repr()`d."""

    message = refusal(lambda: model_config({**OPENAI_ENV, MODEL_API_KEY_ENV_VARIABLE: FAKE_KEY}))

    assert "MODEL_API_KEY_ENV_INVALID" in message
    assert FAKE_KEY not in message


def test_a_configuration_read_never_touches_the_credential_it_names() -> None:
    """Resolution is by name only; the value is read at send time or the isolation is moot."""

    environment = ReadLog(
        {
            **OPENAI_ENV,
            MODEL_API_KEY_ENV_VARIABLE: FAKE_KEY_VARIABLE,
            FAKE_KEY_VARIABLE: FAKE_KEY,
        }
    )
    config = model_config(environment)

    assert set(environment.read) <= CONFIG_VARIABLES
    assert FAKE_KEY_VARIABLE not in environment.read
    assert config.api_key_env == FAKE_KEY_VARIABLE


def test_the_key_resolves_only_when_asked_for_and_by_one_reader() -> None:
    environment = ReadLog(
        {
            **OPENAI_ENV,
            MODEL_API_KEY_ENV_VARIABLE: FAKE_KEY_VARIABLE,
            FAKE_KEY_VARIABLE: f"  {FAKE_KEY} ",
        }
    )
    config = model_config(environment)
    before = list(environment.read)

    key = key_for(config, environment)

    assert key == FAKE_KEY
    assert FAKE_KEY_VARIABLE not in before
    assert FAKE_KEY_VARIABLE in environment.read[len(before) :]


def test_key_for_is_the_only_reader_of_a_secret_in_the_domain_module() -> None:
    """Grep-able on purpose: the marker exists exactly once, inside the one function that reads.

    A second read of a credential would be a second place to audit, which is what §1's whole
    design exists to avoid.
    """

    source = inspect.getsource(model_access)

    assert source.count("# the only secret read") == 1
    assert source.count("THE ONE PLACE") == 1


@pytest.mark.parametrize("config", [ModelConfig(), ModelConfig(provider=PROVIDER_OFF)])
def test_no_provider_needs_no_key(config: ModelConfig) -> None:
    """`off` has nowhere to send a credential, so asking is answered with nothing."""

    assert key_for(config, {FAKE_KEY_VARIABLE: FAKE_KEY}) is None


def test_an_endpoint_named_without_a_key_variable_is_asked_unauthenticated() -> None:
    """A local endpoint that needs no auth is a supported shape, not a misconfiguration."""

    config = model_config(OPENAI_ENV)

    assert config.api_key_env == ""
    assert key_for(config, {FAKE_KEY_VARIABLE: FAKE_KEY}) is None


def test_a_named_but_absent_key_refuses_naming_only_the_variable() -> None:
    config = ModelConfig(
        provider=PROVIDER_OPENAI_COMPATIBLE,
        base_url="https://example.invalid/v1",
        model="kin-test-model",
        api_key_env=FAKE_KEY_VARIABLE,
    )

    with pytest.raises(MinekinError) as caught:
        key_for(config, {})

    message = caught.value.safe_message
    assert "MODEL_NOT_CONFIGURED" in message
    assert FAKE_KEY_VARIABLE in message
    assert FAKE_KEY not in message
    assert caught.value.diagnostic()["context"] == {"api_key_env": FAKE_KEY_VARIABLE}


def test_no_field_of_a_config_can_hold_a_credential() -> None:
    """The `repr()` is safe because of the fields there are, not because of what was filtered."""

    config = model_config({**OPENAI_ENV, MODEL_API_KEY_ENV_VARIABLE: FAKE_KEY_VARIABLE})
    printed = repr(config)

    assert {field.name for field in fields(ModelConfig)} == {
        "provider",
        "base_url",
        "model",
        "api_key_env",
        "timeout_ms",
        "max_attempts",
        "run_cost_cap",
        "request_micro_per_million_tokens",
        "response_micro_per_million_tokens",
    }
    assert "api_key_env" in printed
    assert FAKE_KEY_VARIABLE in printed
    assert FAKE_KEY not in printed


# ---------------------------------------------------------------------------
# §2: the decision gate
# ---------------------------------------------------------------------------


def offer(
    *,
    feasible_skill_ids: tuple[str, ...] = ("chop_tree", "craft_workbench", "wait"),
    intent_generation: int = 7,
    budget_remaining_micro: int = 400_000,
) -> DecisionRequest:
    """A request as the local layer would build one: three feasible skills, generation 7."""

    return DecisionRequest(
        observation_ref="obs-1042",
        needs={"safety": 2, "resource_security": 7},
        active_goal="obtain-and-keep-basic-tools",
        feasible_skill_ids=feasible_skill_ids,
        persona_seed="kin-77:curious",
        budget_remaining_micro=budget_remaining_micro,
        intent_generation=intent_generation,
    )


def test_an_answer_inside_the_offer_is_a_decision_stamped_with_this_generation() -> None:
    chosen = compose_decision(offer(), "craft_workbench", "wood first, then the bench")

    assert isinstance(chosen, Decision)
    assert chosen.skill_id == "craft_workbench"
    assert chosen.intent_generation == 7


def test_a_skill_that_was_never_offered_is_refused_not_rewritten() -> None:
    """The provider cannot invent a skill, and a refusal says so instead of acting.

    A task adapter has nothing behind `mine_diamonds`, and handing it the name would be a
    silent no-op at best.
    """

    refused = compose_decision(offer(), "mine_diamonds", "diamonds would be nice")

    assert isinstance(refused, ModelUnavailable)
    assert refused.reason is UnavailableReason.DECISION_OUT_OF_BOUNDS
    assert refused.outcome is CallOutcome.REJECTED
    assert "mine_diamonds" not in repr(refused)


def test_no_choice_is_in_bounds_against_an_empty_offer() -> None:
    """An offer with nothing in it has no answer, whatever the endpoint claims."""

    refused = compose_decision(offer(feasible_skill_ids=()), "chop_tree", "why not")

    assert isinstance(refused, ModelUnavailable)
    assert refused.reason is UnavailableReason.DECISION_OUT_OF_BOUNDS


def test_an_answer_from_another_intent_generation_is_stale_and_dropped() -> None:
    """A late reply must not write a cancelled intent back onto the keys."""

    stale = compose_decision(offer(), "chop_tree", "the tree is still there", 6)

    assert isinstance(stale, ModelUnavailable)
    assert stale.reason is UnavailableReason.STALE_GENERATION
    assert stale.outcome is CallOutcome.REJECTED

    fresh = compose_decision(offer(), "chop_tree", "the tree is still there", 7)
    assert isinstance(fresh, Decision)


def test_a_reply_that_says_no_generation_is_answered_for_this_one() -> None:
    """The port stamps the generation, so an endpoint that omits it cannot forge staleness."""

    chosen = compose_decision(offer(), "wait", "nothing safe to do yet", None)

    assert isinstance(chosen, Decision)
    assert chosen.intent_generation == 7


def test_a_reason_is_remote_text_so_it_is_redacted_and_bounded_on_the_way_in() -> None:
    """Providers echo what they were sent, and a proxy can append a header to the echo.

    Redaction runs before the cut: a credential named in `secrets` is removed from the whole
    string first, so no slice of it can survive as a fragment too short to recognise.
    """

    long_reason = f"authorization: Bearer {FAKE_KEY} attached, " + "and so " * 400
    chosen = compose_decision(offer(), "chop_tree", long_reason, secrets=(FAKE_KEY,))

    assert isinstance(chosen, Decision)
    assert len(chosen.reason) <= MAX_REASON_CHARS
    assert FAKE_KEY not in chosen.reason
    assert FAKE_KEY not in repr(chosen)
    assert FAKE_KEY not in str(chosen.as_document())


def test_a_bare_echoed_key_is_removed_by_the_secret_the_caller_sent() -> None:
    """The shape `redact_text`'s patterns cannot see: a credential with no `Bearer` in front.

    This is why the provider hands the gate the key it put on the wire: an echo of it is then
    removed as a literal rather than hoped to match a pattern.
    """

    chosen = compose_decision(
        offer(),
        "chop_tree",
        f"my notes: {FAKE_KEY} were in the request",
        secrets=(FAKE_KEY,),
    )

    assert isinstance(chosen, Decision)
    assert FAKE_KEY not in chosen.reason


# ---------------------------------------------------------------------------
# §2.5: the commitment candidate an answer may attach
# ---------------------------------------------------------------------------


def test_a_well_shaped_commitment_rides_into_the_decision_redacted_and_bounded() -> None:
    """The candidate is remote text headed for a durable row, so the gate redacts it here
    and judges it nowhere: what it may contain is `domain.commitment`'s question, and the
    answered decision stays a decision with a suggestion beside it, not a stored intent.
    """

    chosen = compose_decision(
        offer(),
        "chop_tree",
        "the cave is worth coming back to",
        commitment={
            "text": f"return to the cave ({FAKE_KEY})",
            "due": "before the next night",
            "evidence_ref": "obs-1042",
        },
        secrets=(FAKE_KEY,),
    )

    assert isinstance(chosen, Decision)
    carried = chosen.commitment
    assert isinstance(carried, dict)
    fields = cast("Mapping[str, object]", carried)
    assert FAKE_KEY not in str(fields)
    assert fields["due"] == "before the next night"
    assert fields["evidence_ref"] == "obs-1042"
    # The judged verdict is what gets recorded — by the session layer's own event — so
    # the raw candidate never rides inside a decision document.
    assert "commitment" not in chosen.as_document()


def test_a_malformed_commitment_is_carried_for_the_gate_not_silently_dropped() -> None:
    """A field of the wrong shape is a refusal the gate must be able to name; a field
    that vanished on the way would leave the answer looking like it never suggested one.
    """

    chosen = compose_decision(offer(), "chop_tree", "why not", commitment="remember this")

    assert isinstance(chosen, Decision)
    assert chosen.commitment == "remember this"

    absent = compose_decision(offer(), "chop_tree", "why not")
    assert isinstance(absent, Decision)
    assert absent.commitment is None


# ---------------------------------------------------------------------------
# §2.6: the one ask whose values leave toward other people
# ---------------------------------------------------------------------------


def test_a_well_shaped_line_passes_even_though_secrets_are_in_scope() -> None:
    chosen = compose_decision(
        offer(feasible_skill_ids=("say",)),
        "say",
        "say hello",
        arguments={"text": "hello everyone"},
        secrets=(FAKE_KEY,),
    )

    assert isinstance(chosen, Decision)
    assert chosen.arguments == {"text": "hello everyone"}


def test_a_line_the_secret_rule_would_touch_is_refused_not_spoken_as_a_placeholder() -> None:
    """Redaction swaps a secret for `<redacted>`; a reason keeps that placeholder, but
    speech must not — `<redacted>` on other people's screens is not something the Kin
    said, and silently word-swapping its speech would put words in its mouth. A line
    that trips the rule is refused by name, and the model may say it differently."""

    for text in (FAKE_KEY, f"ask about {FAKE_KEY} later"):
        refused = compose_decision(
            offer(feasible_skill_ids=("say",)),
            "say",
            "say something",
            arguments={"text": text},
            secrets=(FAKE_KEY,),
        )

        assert isinstance(refused, ModelUnavailable), text
        assert refused.reason is UnavailableReason.MODEL_ARGUMENTS_INVALID


# ---------------------------------------------------------------------------
# §2: the arguments an answer fills in
# ---------------------------------------------------------------------------


#: An offer of behaviors the ask vocabulary declares parameters for, so a filled-in answer is
#: judged by the same table the adapter shows the endpoint. `close_screen` is one of them because
#: its declaration is empty, which is a statement about the behavior and not an omission.
DECLARED_OFFER: tuple[str, ...] = (
    "craft_take_result",
    "collect_dropped",
    "turn_to",
    "close_screen",
)
PLANKS = "minecraft:oak_planks"


def declared_offer() -> DecisionRequest:
    return offer(feasible_skill_ids=DECLARED_OFFER)


def test_an_answer_that_fills_in_the_ask_carries_it_into_the_decision() -> None:
    """The gate is the one judge of an argument, and what it returns is the canonical map.

    `quantity` arrives as the number the endpoint wrote and leaves as the same number this side
    checked — which is what lets a run document be read afterwards as "the ask said four planks"
    rather than as whatever the plan happened to do.
    """

    chosen = compose_decision(
        declared_offer(),
        "craft_take_result",
        "four planks from what the bag holds",
        arguments={"target_item": PLANKS, "quantity": 4},
    )

    assert isinstance(chosen, Decision)
    assert chosen.arguments == {"target_item": PLANKS, "quantity": 4}
    assert chosen.as_document()["arguments"] == {"target_item": PLANKS, "quantity": 4}


def test_an_answer_that_omits_a_required_argument_is_refused_by_name() -> None:
    """`craft` without a product is not a craft of a default item. This side does not guess:
    the refusal is the answer, and the Kin plays on its local reflection."""

    refused = compose_decision(
        declared_offer(), "craft_take_result", "make something", arguments={"quantity": 2}
    )

    assert isinstance(refused, ModelUnavailable)
    assert refused.reason is UnavailableReason.MODEL_ARGUMENTS_MISSING
    assert refused.outcome is CallOutcome.REJECTED


@pytest.mark.parametrize(
    ("skill_id", "arguments", "expected"),
    [
        ("craft_take_result", {"target_item": PLANKS, "quantity": 4, "slot": 3}, "unknown"),
        ("craft_take_result", {"item": PLANKS}, "unknown"),
        ("craft_take_result", {"target_item": "Wooden Pickaxe"}, "invalid"),
        ("craft_take_result", {"target_item": PLANKS, "quantity": 0}, "invalid"),
        ("craft_take_result", {"target_item": PLANKS, "quantity": 999}, "invalid"),
        ("craft_take_result", {"target_item": PLANKS, "quantity": True}, "invalid"),
        ("craft_take_result", {"target_item": PLANKS, "quantity": 2.5}, "invalid"),
        ("collect_dropped", {"item_id": "minecraft:coal", "walk_seconds": "12"}, "invalid"),
        ("collect_dropped", {"item_id": "coal"}, "invalid"),
        ("turn_to", {"yaw_degrees": 1000.0}, "invalid"),
        ("close_screen", {"look_at": "the log"}, "unknown"),
    ],
)
def test_an_argument_that_is_not_a_value_the_behavior_means_is_refused_by_which_one(
    skill_id: str, arguments: Mapping[str, object], expected: str
) -> None:
    """A key nobody declared and a value of the wrong kind or outside the bound are two different
    sentences, and the run document says which was said.

    `True` is the case only a check written against Python can miss: it is an `int`, and a
    quantity of `true` is not a request for one item. `close_screen` has no parameters at all, so
    the only thing an answerer can get wrong about it is to claim one.
    """

    reason = (
        UnavailableReason.MODEL_ARGUMENTS_UNKNOWN
        if expected == "unknown"
        else UnavailableReason.MODEL_ARGUMENTS_INVALID
    )
    refused = compose_decision(declared_offer(), skill_id, "an argument", arguments=arguments)

    assert isinstance(refused, ModelUnavailable)
    assert refused.reason is reason
    assert refused.outcome is CallOutcome.REJECTED


def test_a_stale_or_out_of_bounds_answer_is_refused_before_its_arguments_are_read() -> None:
    """The order is the boundary: an invented skill and an answer from another intent are the
    older, more serious refusals, and a bad argument never gets to be the reason instead."""

    stale = compose_decision(
        declared_offer(),
        "craft_take_result",
        "late",
        6,
        arguments={"target_item": PLANKS},
    )
    assert isinstance(stale, ModelUnavailable)
    assert stale.reason is UnavailableReason.STALE_GENERATION

    invented = compose_decision(
        declared_offer(), "fly_to_the_log", "sure", arguments={"target_item": PLANKS}
    )
    assert isinstance(invented, ModelUnavailable)
    assert invented.reason is UnavailableReason.DECISION_OUT_OF_BOUNDS


def test_an_answer_about_a_behavior_nobody_declared_is_judged_only_by_the_offer() -> None:
    """A behavior with no row in the parameter table is not a behavior with no parameters — but
    an empty ask for it is honourable, because there is nothing this side would have to know to
    run it. A non-empty one is a parameter nobody declared, and that is a refusal."""

    empty = compose_decision(offer(), "wait", "nothing safe yet")
    assert isinstance(empty, Decision)
    assert empty.arguments == {}

    claimed = compose_decision(
        offer(), "wait", "nothing safe yet", arguments={"target_item": PLANKS}
    )
    assert isinstance(claimed, ModelUnavailable)
    assert claimed.reason is UnavailableReason.MODEL_ARGUMENTS_UNKNOWN


def test_a_request_must_be_judgable_before_it_is_paid_for() -> None:
    """An unjudged request is a caller bug, caught while it still costs nothing."""

    with pytest.raises(ValueError, match="observation"):
        DecisionRequest(observation_ref="")
    with pytest.raises(ValueError, match="intent_generation"):
        DecisionRequest(observation_ref="obs-1", intent_generation=0)
    with pytest.raises(ValueError, match="feasible set"):
        DecisionRequest(observation_ref="obs-1", feasible_skill_ids=("chop_tree", ""))
    with pytest.raises(ValueError, match="bounded"):
        DecisionRequest(
            observation_ref="obs-1",
            feasible_skill_ids=tuple(f"skill-{index}" for index in range(MAX_FEASIBLE_SKILLS + 1)),
        )
    with pytest.raises(ValueError, match="negative"):
        DecisionRequest(observation_ref="obs-1", needs={"safety": -1})
    with pytest.raises(ValueError, match="negative"):
        DecisionRequest(observation_ref="obs-1", budget_remaining_micro=-1)


def test_a_model_unavailable_value_has_no_place_to_put_the_other_sides_text() -> None:
    """The shape of the negative half of the port is the isolation guarantee.

    There is no free-text field, so a future change that wants one has to edit this type and
    answer for what it might carry.
    """

    refused = ModelUnavailable(UnavailableReason.RESPONSE_MALFORMED_JSON, 503)

    assert {field.name for field in fields(ModelUnavailable)} == {"reason", "status_code"}
    assert "503" in repr(refused)
    assert FAKE_KEY not in repr(refused)
    assert refused.as_document() == {
        "reason": "RESPONSE_MALFORMED_JSON",
        "status_code": 503,
        "outcome": "rejected",
    }


@pytest.mark.parametrize("host", ["127.example.com", "127.0.0.1.example.com"])
def test_ipv4_looking_external_hostname_cannot_receive_plaintext_credentials(host: str) -> None:
    with pytest.raises(MinekinError, match="http"):
        model_config({**OPENAI_ENV, MODEL_BASE_URL_VARIABLE: f"http://{host}/v1"})


def test_the_attempt_count_defaults_to_two_and_is_bounded() -> None:
    """The retry the provider runs is an operator-visible number: two attempts by default,
    1..5 when named, read only when a model is actually configured."""

    assert model_config(OPENAI_ENV).max_attempts == DEFAULT_MODEL_MAX_ATTEMPTS
    assert model_config({**OPENAI_ENV, MODEL_MAX_ATTEMPTS_VARIABLE: "3"}).max_attempts == 3
    assert model_config({**OPENAI_ENV, MODEL_MAX_ATTEMPTS_VARIABLE: " 1 "}).max_attempts == 1

    for bad in ("0", "-1", "six", "2.5", "9", "true"):
        message = refusal(
            lambda bad=bad: model_config({**OPENAI_ENV, MODEL_MAX_ATTEMPTS_VARIABLE: bad})
        )
        assert MODEL_MAX_ATTEMPTS_VARIABLE in message

    # `off` never reads it, like every other variable a run that contacts nothing does not use.
    assert (
        model_config({MODEL_MAX_ATTEMPTS_VARIABLE: "9"}).max_attempts == DEFAULT_MODEL_MAX_ATTEMPTS
    )
