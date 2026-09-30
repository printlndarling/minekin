"""The provider contract, tested against a local fake endpoint and no real credentials.

§6 of `docs/s3-minimal-player-mind.md` names five shapes a provider must be covered against:
normal, timeout, malformed structure, an out-of-bounds choice, and `off`. They are all here,
served by a `ThreadingHTTPServer` bound to `127.0.0.1:0` — no network egress, no real key, and
nothing that could make the suite depend on somebody else's uptime.

Two properties carry more weight than the individual shapes:

**Every way a call can end returns a value.** A timeout, a 500 page, a completion that is HTML,
an answer from a cancelled intent and a run over its spend cap all produce a
`ModelUnavailable`, never an exception the game loop would have to survive. Where the cap is the
reason, no socket is opened at all: the limit stops calls, not the Kin.

**The key is on the wire and nowhere else.** The fake endpoint is deliberately adversarial: it
echoes the `Authorization` header it was given back inside the completion, and its error page
quotes the prompt. `FAKE_KEY` is planted, the call runs, and then everything the code could have
produced — every `repr()`, every projected document, every refusal message, every string the
logger was handed, and the request body we sent — is searched for the whole value and for each of
its eight-character windows. The check is proved to bite by running it against the one string
where the key legitimately appears.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

import pytest

from minekin_core.adapters.model import (
    OffModelProvider,
    OpenAICompatibleProvider,
    model_provider_for,
)
from minekin_core.adapters.model.openai_compatible import SYSTEM_PROMPT
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.model_access import (
    PROVIDER_OFF,
    PROVIDER_OPENAI_COMPATIBLE,
    CallOutcome,
    Decision,
    DecisionRequest,
    ModelConfig,
    ModelUnavailable,
    ProviderName,
    UnavailableReason,
    cost_ledger_for,
    key_for,
)

FAKE_KEY: str = "sk-FAKE-9bQ2t7Lm4XwR8Kd3Zp6V"
FAKE_KEY_VARIABLE: str = "MINEKIN_MODEL_API_KEY"
FEASIBLE: tuple[str, ...] = ("chop_tree", "craft_workbench", "wait")
GENERATION: int = 7

#: Every fragment of the key that a leak could plausibly leave behind: the whole value, and
#: each contiguous eight-character window of it. Eight is the length at which a truncated
#: credential stops being useless to an attacker who has the rest of the log.
WINDOW: int = 8
SECRET_FRAGMENTS: tuple[str, ...] = (
    FAKE_KEY,
    *(FAKE_KEY[index : index + WINDOW] for index in range(len(FAKE_KEY) - WINDOW + 1)),
)


@dataclass(frozen=True, slots=True)
class Arrival:
    """One request as the endpoint saw it — the wire, not Core's view of it."""

    method: str
    path: str
    authorization: str | None
    body: str


@dataclass(slots=True)
class Behavior:
    """What the fake endpoint does with an arrival.

    `echo` is the adversarial shape: a proxy that copies the credential it was handed into the
    completion it returns. That is what makes the isolation assertions worth running.
    """

    status: int = 200
    body: bytes = b""
    sleep_s: float = 0.0
    location: str | None = None
    echo: bool = False
    silent: bool = False

    def reply(self, arrival: Arrival, *, first: bool) -> tuple[int, bytes, str | None]:
        if self.echo:
            content = json.dumps(
                {
                    "skill_id": FEASIBLE[0],
                    "reason": f"you sent me {arrival.authorization}",
                    "intent_generation": GENERATION,
                }
            )
            return 200, envelope(content), None
        if self.location is not None and first:
            return 302, b"", self.location
        # A redirect target is answered plainly, so the client's own redirect loop guard is
        # not what this test is measuring.
        return self.status, self.body, None


class Endpoint:
    """A local HTTP endpoint on a port the kernel picked, and the requests it received."""

    def __init__(self, behavior: Behavior) -> None:
        self.behavior = behavior
        self.arrivals: list[Arrival] = []

        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:
                self._answer()

            def do_GET(self) -> None:
                self._answer()

            def _answer(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                arrival = Arrival(self.command, self.path, self.headers.get("Authorization"), raw)
                outer.arrivals.append(arrival)
                if outer.behavior.silent:
                    # Hang up without a status line: the client learns there is no endpoint here.
                    self.close_connection = True
                    return
                if outer.behavior.sleep_s:
                    time.sleep(outer.behavior.sleep_s)
                status, body, location = outer.behavior.reply(
                    arrival, first=len(outer.arrivals) == 1
                )
                try:
                    self.send_response(status)
                    if location is not None:
                        self.send_header("Location", location)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    # The client gave up (that is the timeout shape). Nothing to say, and
                    # least of all about what it had just been sent.
                    pass

            def log_message(self, format: str, *args: object) -> None:
                """Silence the access log: its default line is the request line, our URL.

                The real check is the corpus scan in `test_nothing_the_code_produces...`, and a
                handler that wrote the request line to stderr would only make that scan noisier
                while teaching nothing.
                """

                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._port = cast("tuple[str, int]", self._server.server_address)[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self._port

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._port}/v1"

    @property
    def completions_path(self) -> str:
        return "/v1/chat/completions"

    def redirect_target(self) -> str:
        return f"http://127.0.0.1:{self._port}/v1/somewhere-else"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def serve() -> Iterator[Callable[[Behavior], Endpoint]]:
    """Start endpoints for one test and shut them all down afterwards."""

    started: list[Endpoint] = []

    def start(behavior: Behavior) -> Endpoint:
        endpoint = Endpoint(behavior)
        started.append(endpoint)
        return endpoint

    yield start

    for endpoint in started:
        endpoint.close()


def envelope(content: str, *, prompt_tokens: int = 1_234, completion_tokens: int = 210) -> bytes:
    """A completion envelope in the shape the endpoint returns, usage and all."""

    return json.dumps(
        {
            "id": "chatcmpl-fake",
            "object": "chat.completion",
            "model": "kin-test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
    ).encode("utf-8")


def decision_content(
    skill_id: str,
    reason: str,
    generation: int | None = GENERATION,
    arguments: Mapping[str, object] | None = None,
) -> bytes:
    payload: dict[str, object] = {"skill_id": skill_id, "reason": reason}
    if arguments is not None:
        payload["arguments"] = arguments
    if generation is not None:
        payload["intent_generation"] = generation
    return envelope(json.dumps(payload))


def config_for(
    endpoint: Endpoint,
    *,
    provider: ProviderName = PROVIDER_OPENAI_COMPATIBLE,
    timeout_ms: int = 2_000,
    cap: int = 500_000,
    api_key_env: str = FAKE_KEY_VARIABLE,
) -> ModelConfig:
    return ModelConfig(
        provider=provider,
        base_url=endpoint.base_url,
        model="kin-test-model",
        api_key_env=api_key_env,
        timeout_ms=timeout_ms,
        run_cost_cap=cap,
    )


def environment(*, with_key: bool = True) -> dict[str, str]:
    return {FAKE_KEY_VARIABLE: FAKE_KEY} if with_key else {}


def offer(
    *,
    feasible_skill_ids: tuple[str, ...] = FEASIBLE,
    intent_generation: int = GENERATION,
    observation_summary: Mapping[str, object] | None = None,
) -> DecisionRequest:
    return DecisionRequest(
        observation_ref="obs-1042",
        needs={"safety": 2, "resource_security": 7},
        active_goal="obtain-and-keep-basic-tools",
        feasible_skill_ids=feasible_skill_ids,
        observation_summary={} if observation_summary is None else dict(observation_summary),
        persona_seed="kin-77:curious",
        budget_remaining_micro=400_000,
        intent_generation=intent_generation,
    )


def body_field(arrival: Arrival, name: str) -> object:
    """One top-level field of the JSON body the endpoint was handed."""

    document = cast(dict[str, object], json.loads(arrival.body))
    return document.get(name)


def shown_offer(arrival: Arrival) -> dict[str, object]:
    """The `user` message as the endpoint read it: the offer, restated as data."""

    document = cast(dict[str, object], json.loads(arrival.body))
    messages = cast(list[object], document["messages"])
    user = cast(dict[str, object], messages[1])
    return cast(dict[str, object], json.loads(cast(str, user["content"])))


def offered_skills(arrival: Arrival) -> list[str]:
    """The feasible set as the endpoint saw it, read back out of the body it received."""

    return cast(list[str], shown_offer(arrival)["feasible_skill_ids"])


def leak_in(texts: list[str]) -> str | None:
    """The first secret fragment found in any of `texts`, or `None`.

    Split out from an assertion so the same scan can be run on the corpus that must be clean and
    on the one string that is allowed to carry the key — a check that has never been shown to
    fire is not a check.
    """

    for text in texts:
        for fragment in SECRET_FRAGMENTS:
            if fragment in text:
                return fragment
    return None


def assert_clean(texts: list[str], *, label: str) -> None:
    found = leak_in(texts)
    assert found is None, f"{label} carries a fragment of the key: {found!r}"


# ---------------------------------------------------------------------------
# The five shapes §6 names
# ---------------------------------------------------------------------------


def test_the_normal_shape_answers_with_a_decision_inside_the_offer(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    endpoint = serve(
        Behavior(body=decision_content("craft_workbench", "wood first, then the bench"))
    )
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer())

    assert isinstance(answered, Decision)
    assert answered.skill_id == "craft_workbench"
    assert answered.intent_generation == GENERATION
    assert len(endpoint.arrivals) == 1
    assert endpoint.arrivals[0].path == endpoint.completions_path
    assert endpoint.arrivals[0].authorization == f"Bearer {FAKE_KEY}"


def test_the_call_is_accounted_for_with_the_usage_the_endpoint_reported(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    endpoint = serve(Behavior(body=decision_content("wait", "the light is going")))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    provider.decide(offer())

    record = provider.ledger.records[0]
    assert len(provider.ledger.records) == 1
    assert (record.request_tokens, record.response_tokens) == (1_234, 210)
    # 1,234 x 2,500 per million rounds up to 4 and 210 x 10,000 per million to 3.
    assert record.estimated_cost == 7
    assert record.outcome is CallOutcome.OK
    assert record.intent_generation == GENERATION
    assert record.reason is None


def test_the_request_asks_for_one_json_object_and_offers_only_what_is_feasible(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """The body is the model's whole world, so what it holds is part of the contract."""

    endpoint = serve(Behavior(body=decision_content("chop_tree", "there is a tree")))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    provider.decide(offer())

    arrival = endpoint.arrivals[0]
    assert body_field(arrival, "model") == "kin-test-model"
    assert body_field(arrival, "response_format") == {"type": "json_object"}
    assert body_field(arrival, "stream") is False
    assert offered_skills(arrival) == list(FEASIBLE)


def test_the_timeout_shape_is_named_and_the_caller_still_gets_a_value(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """A small budget against a handler that outlasts it: the call dies, the run does not."""

    endpoint = serve(Behavior(body=decision_content("chop_tree", "late"), sleep_s=0.6))
    provider = OpenAICompatibleProvider(config_for(endpoint, timeout_ms=80), environment())

    answered = provider.decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.TIMEOUT
    assert answered.outcome is CallOutcome.TIMEOUT
    record = provider.ledger.records[-1]
    assert record.outcome is CallOutcome.TIMEOUT
    assert record.reason is UnavailableReason.TIMEOUT
    # Nothing was reported, so nothing is priced: a timeout is not a free completion either.
    assert (record.request_tokens, record.response_tokens) == (None, None)


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b"<html>502 bad gateway</html>", UnavailableReason.RESPONSE_MALFORMED_JSON),
        (b"", UnavailableReason.RESPONSE_MALFORMED_JSON),
        (b'{"choices": ', UnavailableReason.RESPONSE_MALFORMED_JSON),
        (b"[1, 2, 3]", UnavailableReason.RESPONSE_MALFORMED_JSON),
        (
            b'{"choices": [], "usage": {"prompt_tokens": 5}}',
            UnavailableReason.RESPONSE_MISSING_CONTENT,
        ),
        (
            envelope(json.dumps(["chop_tree"])),
            UnavailableReason.RESPONSE_NOT_OBJECT,
        ),
        (envelope("I shall chop the tree shortly"), UnavailableReason.RESPONSE_MALFORMED_JSON),
    ],
)
def test_the_malformed_structure_shape_refuses_without_reading_it(
    serve: Callable[[Behavior], Endpoint],
    body: bytes,
    reason: UnavailableReason,
) -> None:
    """Whatever the endpoint sent is not a decision, and is not quoted either.

    The last case is the one that would otherwise sneak through: content that arrives as a
    perfectly readable string, which is exactly what a completion looks like when the endpoint
    ignored the structured-output request.
    """

    endpoint = serve(Behavior(body=body))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is reason
    assert provider.ledger.records[-1].outcome is CallOutcome.REJECTED
    quoted = body.decode("utf-8", "replace")[:16].strip()
    if quoted:
        assert quoted not in repr(answered)


def test_an_out_of_bounds_choice_is_refused_and_never_handed_down(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """The offer is the boundary: a skill the local layer never computed does not exist.

    `smelt_iron` needs a furnace the Kin does not have, and no task adapter would be able to run
    it — so it is refused by name rather than passed on to fail quietly.
    """

    endpoint = serve(Behavior(body=decision_content("smelt_iron", "iron is what I want")))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.DECISION_OUT_OF_BOUNDS
    assert "smelt_iron" not in repr(answered)
    record = provider.ledger.records[-1]
    assert record.outcome is CallOutcome.REJECTED
    assert record.reason is UnavailableReason.DECISION_OUT_OF_BOUNDS
    # The usage still arrived, so the call still cost something.
    assert record.estimated_cost == 7


def test_an_answer_from_a_cancelled_intent_is_dropped_as_stale(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """A reply carrying another generation is late, and late means it must not act.

    The intent it was chosen for has been cancelled; writing it back would put a key down for a
    decision the Kin stopped making.
    """

    endpoint = serve(Behavior(body=decision_content("chop_tree", "still chopping", 6)))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.STALE_GENERATION
    assert provider.ledger.records[-1].outcome is CallOutcome.REJECTED


def test_the_off_shape_answers_without_a_request_a_cost_or_an_exception(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """`off` is a product capability: the caller gets a value and the game carries on.

    The endpoint is live and reachable, which is the point — an `off` provider must not ask it
    anything, must not spend, and must not raise.
    """

    endpoint = serve(Behavior(body=decision_content("chop_tree", "unused")))
    provider = model_provider_for(ModelConfig(provider=PROVIDER_OFF), environment())

    answered = provider.decide(offer())

    assert isinstance(provider, OffModelProvider)
    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.MODEL_NOT_CONFIGURED
    assert answered.outcome is CallOutcome.UNAVAILABLE
    assert endpoint.arrivals == []


# ---------------------------------------------------------------------------
# The ask, in both directions: parameters out, arguments back
# ---------------------------------------------------------------------------


#: A feasible set of behaviors the ask vocabulary declares parameters for, so the body the
#: endpoint receives is the declaration and not only the names.
DECLARED: tuple[str, ...] = ("craft_take_result", "collect_dropped", "turn_to")
PLANKS = "minecraft:oak_planks"
SUMMARY: dict[str, object] = {
    "game_tick": 1042,
    "inventory": {PLANKS: 5},
    "craft_options": ["minecraft:stick"],
    "goal": {"product_id": PLANKS, "quantity": 8, "held": 5},
}


def test_the_ask_shows_the_parameter_declaration_for_the_behaviors_it_may_choose(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """An answerer that is offered `craft_take_result` and nothing else can only guess what to put
    in `target_item`. The declaration travels with the offer: kinds, requiredness and bounds, for
    the offered behaviors alone.

    The endpoint is a stranger, so this is a courtesy and not a contract — the values that come
    back are re-checked at the gate either way.
    """

    endpoint = serve(Behavior(body=decision_content("turn_to", "look around")))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    provider.decide(offer(feasible_skill_ids=DECLARED))

    shown = shown_offer(endpoint.arrivals[0])
    skills = cast(dict[str, object], shown["skill_parameters"])
    assert set(skills) == set(DECLARED)
    craft = cast(list[dict[str, object]], skills["craft_take_result"])
    assert {row["name"] for row in craft} == {"target_item", "quantity"}
    assert {"name": "target_item", "kind": "item_id", "required": True} in craft
    assert cast(list[str], shown["feasible_skill_ids"]) == list(DECLARED)


def test_the_observation_the_answerer_sees_is_the_summary_and_not_the_world(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """§2 promises a pointer to the reading plus a summary, and the summary is what makes an
    argument checkable afterwards: counts, the held item, what the bag could become.

    What is deliberately not sent is the geometry. The request already carries `observation_ref`,
    and a body that held coordinates would say more about the world than the local layer decided to
    show — while adding nothing an answerer can use, because it has no map and no keys.
    """

    endpoint = serve(Behavior(body=decision_content("turn_to", "look around")))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    provider.decide(offer(feasible_skill_ids=DECLARED, observation_summary=SUMMARY))

    shown = shown_offer(endpoint.arrivals[0])
    assert shown["observation"] == SUMMARY
    assert shown["observation_ref"] == "obs-1042"
    for absent in ("x", "y", "z", "coordinates", "entities"):
        assert absent not in cast(dict[str, object], shown["observation"])


def test_a_request_that_shows_nothing_sends_an_empty_summary(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """A session that has nothing to show says so with `{}` rather than with an invented world."""

    endpoint = serve(Behavior(body=decision_content("wait", "nothing safe yet")))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    provider.decide(offer())

    assert shown_offer(endpoint.arrivals[0])["observation"] == {}


def test_an_answer_that_fills_in_the_ask_comes_back_with_it(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """The round trip the interface is: the endpoint names a product and a count, and the `Decision`
    the port returns carries exactly those values for whoever builds the call.

    Nothing is interpreted here. `minecraft:iron_sword` is a well-spelled item id, so it is honoured
    as an argument; whether any recipe exists for it is a question the local layer answers later.
    """

    endpoint = serve(
        Behavior(
            body=decision_content(
                "craft_take_result",
                "make four planks",
                arguments={"target_item": PLANKS, "quantity": 4},
            )
        )
    )
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer(feasible_skill_ids=DECLARED))

    assert isinstance(answered, Decision)
    assert answered.skill_id == "craft_take_result"
    assert answered.arguments == {"target_item": PLANKS, "quantity": 4}


def test_an_answer_that_leaves_a_required_argument_out_is_refused_by_that_name(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """A skill name with nothing filled in is not a craft of some default item, and the provider
    does not supply the missing half out of the reading it was not asked to judge."""

    endpoint = serve(
        Behavior(body=decision_content("craft_take_result", "make something", arguments={}))
    )
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    refused = provider.decide(offer(feasible_skill_ids=DECLARED))

    assert isinstance(refused, ModelUnavailable)
    assert refused.reason is UnavailableReason.MODEL_ARGUMENTS_MISSING
    assert refused.outcome is CallOutcome.REJECTED


def test_an_answer_whose_arguments_are_not_an_object_is_read_as_an_empty_ask(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """`arguments` arrives as free text from a stranger, and `"hurry"` is not a map. It becomes the
    ask nobody filled in rather than a parse error, because the difference between those two is
    which side of the contract failed — and a string is a choice, not a transport fault."""

    payload = json.dumps(
        {
            "skill_id": FEASIBLE[0],
            "reason": "chop it",
            "arguments": "hurry",
            "intent_generation": GENERATION,
        }
    )
    endpoint = serve(Behavior(body=envelope(payload)))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer())

    assert isinstance(answered, Decision)
    assert answered.arguments == {}


def test_the_instruction_asks_for_arguments_and_forbids_inventing_a_name() -> None:
    """The system prompt is the only place the expected shape is stated to the endpoint, and a
    model that invents an item, a recipe or a slot has to be told not to before it answers."""

    assert '"arguments"' in SYSTEM_PROMPT
    for forbidden in ("no item the request did not name", "the feasible list"):
        assert forbidden in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# The shapes around the five: status, transport, cap, and the key itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "outcome"),
    [(500, CallOutcome.UNAVAILABLE), (400, CallOutcome.REJECTED)],
)
def test_a_non_2xx_is_named_by_its_status_and_nothing_else(
    serve: Callable[[Behavior], Endpoint], status: int, outcome: CallOutcome
) -> None:
    """The body of an error page quotes prompts, so only the number is kept.

    4xx and 5xx take the same path in the game loop and mean different things to fix, which is
    why they are filed apart in the ledger.
    """

    quoted = b'{"error": {"message": "you sent: ' + FAKE_KEY.encode() + b'"}}'
    endpoint = serve(Behavior(status=status, body=quoted))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.PROVIDER_STATUS
    assert answered.status_code == status
    assert answered.outcome is outcome
    record = provider.ledger.records[-1]
    assert (record.outcome, record.status_code) == (outcome, status)


def test_an_endpoint_that_says_nothing_at_all_is_named_not_raised(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """A connection the other side hangs up on without a status line.

    This is the deterministic shape of "unreachable": the stack is not involved in whether a
    closed port refuses or merely goes silent, so the unreachable case is tested as a server that
    accepts and then says nothing.
    """

    endpoint = serve(Behavior(silent=True))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.TRANSPORT_FAILURE
    assert provider.ledger.records[-1].outcome is CallOutcome.UNAVAILABLE


def test_a_port_nobody_is_listening_on_stops_the_call_without_stopping_the_run() -> None:
    """Nothing here raises, whichever of the two answers the network stack gives.

    A closed loopback port either refuses the connection or ignores it, and that is the stack's
    choice rather than this build's: `Windows` tends to go silent, which the configured
    `timeout_ms` turns into the timeout shape. Both names mean "no decision arrived", both are
    values, and the Kin keeps playing either way.
    """

    endpoint = Endpoint(Behavior())
    port = endpoint.port
    endpoint.close()
    dead = ModelConfig(
        provider=PROVIDER_OPENAI_COMPATIBLE,
        base_url=f"http://127.0.0.1:{port}/v1",
        model="kin-test-model",
        timeout_ms=400,
    )

    answered = OpenAICompatibleProvider(dead, environment()).decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason in (UnavailableReason.TRANSPORT_FAILURE, UnavailableReason.TIMEOUT)
    assert answered.outcome in (CallOutcome.UNAVAILABLE, CallOutcome.TIMEOUT)


def test_a_redirect_is_refused_and_the_key_does_not_ride_it(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """A forwarded request is a second hop the configured checks never saw.

    urllib copies a request's headers across a redirect, including to another host and scheme,
    so the credential is sent as an unredirected header and the redirect itself is refused. The
    second arrival is the proof: it carries no `Authorization` at all.
    """

    endpoint = serve(Behavior(body=b'{"choices": []}', location=None))
    behavior = endpoint.behavior
    behavior.location = endpoint.redirect_target()
    behavior.body = b'{"choices": []}'
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.REDIRECTED
    assert len(endpoint.arrivals) >= 2
    assert endpoint.arrivals[0].authorization == f"Bearer {FAKE_KEY}"
    assert endpoint.arrivals[1].authorization is None


def test_an_empty_offer_costs_nothing_because_no_answer_was_possible(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    endpoint = serve(Behavior(body=decision_content("chop_tree", "unused")))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment())

    answered = provider.decide(offer(feasible_skill_ids=()))

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.NOTHING_FEASIBLE
    assert endpoint.arrivals == []
    assert provider.ledger.records == []


def test_the_spend_cap_stops_the_call_before_the_socket_opens(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """Over the cap returns a value, writes a record, and asks the endpoint nothing.

    This is the difference between an operator's money limit and a stopped Kin: the game keeps
    running, so nothing may raise here, and the ledger says out loud that calls stopped rather
    than leaving it to look like the model was never wanted.
    """

    endpoint = serve(Behavior(body=decision_content("chop_tree", "unused")))
    config = config_for(endpoint, cap=2)
    spent = cost_ledger_for(config)
    spent.record_call(
        PROVIDER_OPENAI_COMPATIBLE, "kin-test-model", 1, CallOutcome.OK, request_tokens=1_000_000
    )
    provider = OpenAICompatibleProvider(config, environment(), ledger=spent)

    answered = provider.decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.RUN_COST_CAP_REACHED
    assert endpoint.arrivals == []
    record = provider.ledger.records[-1]
    assert record.reason is UnavailableReason.RUN_COST_CAP_REACHED
    assert record.estimated_cost == 0
    assert provider.ledger.calls == 1
    assert provider.ledger.cap_refusals == 1


def test_a_named_but_absent_key_is_never_asked_for_over_the_wire(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    """The endpoint expects a credential this machine does not have, so nothing is sent.

    An unauthenticated request to an authenticated endpoint would be a second failure on top of
    the first one, and it would put the prompt on a link the operator named as private.
    """

    endpoint = serve(Behavior(body=decision_content("chop_tree", "unused")))
    provider = OpenAICompatibleProvider(config_for(endpoint), environment(with_key=False))

    answered = provider.decide(offer())

    assert isinstance(answered, ModelUnavailable)
    assert answered.reason is UnavailableReason.KEY_UNRESOLVED
    assert endpoint.arrivals == []


def test_an_endpoint_that_needs_no_key_is_asked_without_one(
    serve: Callable[[Behavior], Endpoint],
) -> None:
    endpoint = serve(Behavior(body=decision_content("wait", "no credentials here")))
    provider = OpenAICompatibleProvider(
        config_for(endpoint, api_key_env=""), environment(with_key=False)
    )

    answered = provider.decide(offer())

    assert isinstance(answered, Decision)
    assert endpoint.arrivals[0].authorization is None


# ---------------------------------------------------------------------------
# The isolation proof
# ---------------------------------------------------------------------------


def test_nothing_the_code_produces_carries_the_key(
    serve: Callable[[Behavior], Endpoint], caplog: pytest.LogCaptureFixture
) -> None:
    """Plant a distinctive key, run every shape, then search everything that came out.

    The corpus is what the code could have written: the `repr()` of the config, of the decision,
    of every ledger record and of every projected document, every string the logger was handed,
    every refusal message, and the request bodies we ourselves sent. The `Authorization` header
    the endpoint recorded is deliberately the one string excluded — it is where the key belongs.
    """

    caplog.set_level(logging.DEBUG)
    corpus: list[str] = []

    def gather(label: str, value: object) -> None:
        corpus.extend([repr(value), str(value), json.dumps(_renderable(value))])
        assert label  # every probe is named, so a failure says which shape leaked

    # The adversarial endpoint: it echoes the credential it was handed into the completion.
    echoing = serve(Behavior(echo=True))
    provider = OpenAICompatibleProvider(config_for(echoing), environment())
    with caplog.at_level(logging.DEBUG, logger="minekin_core.adapters.model.openai_compatible"):
        answered = provider.decide(offer())
    gather("decision", answered)
    for record in provider.ledger.records:
        gather("record", record)
    gather("ledger document", provider.ledger.as_document())
    gather("config", provider.config)
    if isinstance(answered, Decision):
        gather("decision document", answered.as_document())
        assert FAKE_KEY not in answered.reason, "the echo reached the reason"
    assert echoing.arrivals, "the adversarial endpoint was never asked"
    for arrival in echoing.arrivals:
        corpus.append(arrival.body)

    # The other shapes, each with its own message and record.
    failures: list[tuple[Behavior, Mapping[str, str]]] = [
        (Behavior(status=500, body=b"boom " + FAKE_KEY.encode()), environment()),
        (Behavior(body=b"not json at all"), environment()),
        (Behavior(body=decision_content("smelt_iron", "out of bounds")), environment()),
        (Behavior(body=decision_content("chop_tree", "late", 1)), environment()),
        (Behavior(body=decision_content("chop_tree", "slow"), sleep_s=0.5), environment()),
        (Behavior(body=b'{"choices": []}'), environment(with_key=False)),
    ]
    for behavior, environ in failures:
        endpoint = serve(behavior)
        falling = OpenAICompatibleProvider(config_for(endpoint, timeout_ms=120), environ)
        outcome = falling.decide(offer())
        gather("unavailable", outcome)
        gather("config", falling.config)
        gather("ledger document", falling.ledger.as_document())
        corpus.extend(_messages(caplog))

    # A refusal raised from the one place that reads the key, and its diagnostic.
    with pytest.raises(MinekinError) as caught:
        key_for(provider.config, {})
    gather("minekin error", caught.value)
    corpus.append(caught.value.safe_message)
    corpus.append(repr(caught.value.diagnostic()))
    corpus.append(str(caught.value.diagnostic()))

    corpus.extend(_messages(caplog))
    assert_clean(corpus, label="everything the code produced")


def _messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Every string the logger was handed, formatted as a handler would render it."""

    rendered = [record.getMessage() for record in caplog.records]
    return [*rendered, *(repr(record) for record in caplog.records)]


def _renderable(value: object) -> object:
    """Best effort at a JSON view of a value, so projections get searched too.

    The casts are about the containers, not the contents: a `dict` reached through `object` has
    unknown key and value types, and an unknown type is one pyright cannot follow into the
    search below. Nothing here changes what is searched — every string still gets searched.
    """

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        items = cast(Sequence[object], value)
        return [_renderable(item) for item in items]
    if isinstance(value, Mapping):
        entries = cast(Mapping[object, object], value)
        return {str(key): _renderable(item) for key, item in entries.items()}
    document = getattr(value, "as_document", None)
    if callable(document):
        return _renderable(cast(Callable[[], object], document)())
    return repr(value)


def test_the_isolation_check_would_have_caught_a_leak() -> None:
    """The positive control: the same scan run on a string that does carry the key.

    A check nobody has seen fire is not a check. Both the whole credential and a bare interior
    window are found, which is what makes the `off`/echo/500 assertions above worth reading.
    """

    with pytest.raises(AssertionError):
        assert_clean([f"Bearer {FAKE_KEY}"], label="control: the wire header")
    with pytest.raises(AssertionError):
        assert_clean([FAKE_KEY[9:17]], label="control: an eight-character window")
    with pytest.raises(AssertionError):
        buried = ["nothing here", "nor here", FAKE_KEY[:8]]
        assert_clean(buried, label="control: buried in a corpus")

    clean = ["off", "chop_tree", "MODEL_NOT_CONFIGURED", "503"]
    assert_clean(clean, label="control: a clean corpus")
