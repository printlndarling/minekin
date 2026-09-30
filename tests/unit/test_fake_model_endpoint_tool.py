"""The harness's fake completions endpoint, answered by the real provider over a socket.

`tools/run_fake_model_endpoint.py` exists so one live run can show `decision_source: model`
without contacting a paid endpoint. This is the check that it says the thing the provider can
actually read: the same `OpenAICompatibleProvider` the session builds posts its offer to the
tool's handler on loopback and gets back a `Decision` naming a skill that was offered.

Two properties are the ones a live run would otherwise have to discover:

**The answer is one the endpoint was offered, and its generation is echoed.** A fake that
invented a skill id would make the run document claim a model chose something the local layer
never put in the feasible set — the exact shape `compose_decision` exists to refuse.

**The key stays on the wire.** The handler never reads `Authorization`, and the request the
provider sends carries a planted value; the corpus the tool could have written — its own stdout
line and the decision it produced — is searched for it.
"""

from __future__ import annotations

import importlib
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import cast

import pytest

from minekin_core.adapters.model.openai_compatible import OpenAICompatibleProvider
from minekin_core.domain.model_access import (
    PROVIDER_OPENAI_COMPATIBLE,
    Decision,
    DecisionRequest,
    ModelConfig,
)

FAKE_KEY = "sk-FAKE-4Hn7Qw2Zd8Ks3Vt6Bm9X"
KEY_VARIABLE = "MINEKIN_MODEL_API_KEY"
FEASIBLE = ("break_seen_block", "collect_dropped", "craft_take_result")
GENERATION = 11


@pytest.fixture(name="endpoint")
def fixture_endpoint() -> Iterator[str]:
    """Serve the harness tool's handler on this machine's loopback for one test."""

    module = importlib.import_module("tools.run_fake_model_endpoint")
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.FakeCompletionsHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host, port = cast("tuple[str, int]", server.server_address[:2])
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def request_for(offer: tuple[str, ...] = FEASIBLE) -> DecisionRequest:
    return DecisionRequest(
        observation_ref="tick=941;generation=1",
        needs={"resource_security": 7},
        active_goal="hold_a_wooden_pickaxe",
        feasible_skill_ids=offer,
        persona_seed="kin-local-demo:stubborn",
        budget_remaining_micro=400_000,
        intent_generation=GENERATION,
    )


def provider_for(base_url: str) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        ModelConfig(
            provider=PROVIDER_OPENAI_COMPATIBLE,
            base_url=base_url,
            model="fake-local",
            api_key_env=KEY_VARIABLE,
            timeout_ms=2_000,
            run_cost_cap=200_000,
        ),
        {KEY_VARIABLE: FAKE_KEY},
    )


def test_the_harness_endpoint_answers_the_provider_that_is_asking(endpoint: str) -> None:
    """A decision over a socket, from the offer the session would really send.

    The first offered id is the known answer, so the assertion is about the contract holding:
    the choice is inside the feasible set, the generation comes back echoed, and the reason is
    text rather than a keystroke.
    """

    decision = provider_for(endpoint).decide(request_for())

    assert isinstance(decision, Decision)
    assert decision.skill_id == FEASIBLE[0]
    assert decision.intent_generation == GENERATION
    assert decision.reason
    assert decision.skill_id in FEASIBLE


def test_an_offer_with_nothing_feasible_is_refused_before_an_answer(endpoint: str) -> None:
    """The endpoint answers a real offer; it does not invent one.

    A request that offers nothing never reaches the socket (the provider stops it locally), so
    the shape under test is an offer whose feasible list the endpoint cannot read as a choice.
    """

    decision = provider_for(endpoint).decide(request_for(offer=()))

    assert not isinstance(decision, Decision)
    assert getattr(decision, "reason", None) is not None


def test_the_endpoint_never_writes_the_key_it_was_shown(
    endpoint: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Whatever the tool prints, it does not print the credential or the offer's contents.

    The handler reads the body to find the feasible list, so the risk is a log line that
    repeats it; the run's stdout is collected in the container's `/tmp`, next to the run's own
    evidence, where a pasted key would be read back out by whoever projects the ledger.
    """

    decision = provider_for(endpoint).decide(request_for())
    printed = capsys.readouterr().out

    assert isinstance(decision, Decision)
    assert FAKE_KEY not in printed
    for fragment in (KEY_VARIABLE, "hold_a_wooden_pickaxe", "kin-local-demo"):
        assert fragment not in printed
