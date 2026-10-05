"""The cost ledger: what one run's model calls added up to, and what they were refused for.

§4 of `docs/s3-minimal-player-mind.md` is short and specific: `domain/budget.py` records
callback latency percentiles and cannot be re-used as a spend account, so the run keeps a second
ledger carrying provider, model, request and response counts, an estimated cost, the intent
generation the call was made for, and the result. These tests hold it to exactly that, plus the
one behaviour the projection depends on:

**The cap stops calls, and says so as a value.** `may_start_call` is a predicate, not an
exception — a run over its cap must still be able to answer "no" without unwinding anything, and
the refusal has to be recorded so an operator reading the dashboard can tell "the model got too
expensive" from "the Kin stopped playing".

**Money is stated with its rate.** A cost without the rate that produced it is a claim, so the
projection carries both, and a count the provider never reported stays absent rather than
becoming a convenient zero.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields
from typing import cast

import pytest

from minekin_core.domain import budget, model_access
from minekin_core.domain.model_access import (
    DEFAULT_REQUEST_MICRO_PER_MILLION_TOKENS,
    DEFAULT_RESPONSE_MICRO_PER_MILLION_TOKENS,
    DEFAULT_RUN_COST_CAP_MICRO,
    CallOutcome,
    CostLedger,
    CostRecord,
    ModelConfig,
    UnavailableReason,
    cost_ledger_for,
    estimate_cost_micro,
)

FAKE_KEY = "sk-FAKE-9bQ2t7Lm4XwR8Kd3Zp6V"


def ledger(cap: int = 1_000_000) -> CostLedger:
    return CostLedger(run_cost_cap=cap)


def ok(ledger: CostLedger, request_tokens: int, response_tokens: int, generation: int = 1) -> None:
    ledger.record_call(
        "openai_compatible",
        "kin-test-model",
        generation,
        CallOutcome.OK,
        request_tokens=request_tokens,
        response_tokens=response_tokens,
    )


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


def test_the_spend_ledger_does_not_reuse_the_latency_ledger() -> None:
    """§4 forbids it in as many words, and this is the check rather than the comment.

    `domain/budget.py` folds callback windows into percentiles and has no notion of a price; a
    model ledger that imported it would be reporting spend as a distribution of milliseconds.
    The docstring is allowed to name the neighbour; the import graph is not.
    """

    tree = ast.parse(inspect.getsource(model_access))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    assert not [name for name in imported if "budget" in name]
    assert not [name for name in dir(budget) if "cost" in name.lower()]
    assert not [name for name in dir(model_access) if "percentile" in name.lower()]


def test_reported_tokens_are_priced_at_the_stated_rate_rounded_up() -> None:
    """A fraction of a micro-unit that was spent is not free.

    1,000 request tokens at 2,500 micro per million is 2.5, and 500 response tokens at 10,000
    per million is exactly 5: eight micro-currency, because the half of the first was spent.
    """

    priced = estimate_cost_micro(1_000, 500, 2_500, 10_000)

    assert priced == 8


def test_a_single_token_still_costs_a_micro() -> None:
    assert estimate_cost_micro(1, None, 2_500, 10_000) == 1
    assert estimate_cost_micro(None, 1, 2_500, 10_000) == 1


def test_nothing_reported_is_priced_as_nothing_and_stays_absent() -> None:
    """Zero would be a measurement nobody took; the ledger says which counts it was given."""

    assert estimate_cost_micro(None, None, 2_500, 10_000) == 0

    account = ledger()
    ok(account, 0, 0)
    account.record_call(
        "openai_compatible",
        "kin-test-model",
        1,
        CallOutcome.TIMEOUT,
        reason=UnavailableReason.TIMEOUT,
    )

    timeout = account.records[1]
    assert (timeout.request_tokens, timeout.response_tokens) == (None, None)
    assert timeout.estimated_cost == 0


def test_zero_tokens_are_a_number_and_absence_is_not_the_same_fact() -> None:
    priced = ledger()
    ok(priced, 0, 0)
    unpriced = ledger()
    unpriced.record_call("openai_compatible", "kin-test-model", 1, CallOutcome.OK)

    assert priced.records[0].request_tokens == 0
    assert unpriced.records[0].request_tokens is None
    assert priced.records[0].as_document()["request_tokens"] == 0
    assert unpriced.records[0].as_document()["request_tokens"] is None


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_an_empty_ledger_is_willing_to_spend() -> None:
    account = ledger(cap=100)

    assert account.may_start_call()
    assert account.remaining() == 100
    assert account.spent == 0


def test_spend_up_to_the_cap_is_honoured_and_the_first_micro_past_it_is_not() -> None:
    """The contract's word is "exceeded", so the cap itself is spendable.

    Rounding is upwards, which means one reported token can be the one that passes the cap; the
    next call is what refuses, and nothing about that is an error.
    """

    account = ledger(cap=8)
    ok(account, 1_000, 500)

    assert account.spent == 8
    assert account.remaining() == 0
    assert account.may_start_call()

    account.record_call("openai_compatible", "kin-test-model", 2, CallOutcome.OK, request_tokens=1)

    assert account.spent == 9
    assert account.remaining() == 0
    assert not account.may_start_call()


def test_a_refusal_for_the_cap_costs_nothing_and_cannot_cascade() -> None:
    """Recording the refusal of a call must not change what is owed for calls that happened.

    A ledger that charged for its own refusals would turn a spend limit into a spiral.
    """

    account = ledger(cap=2)
    ok(account, 1_000, 0)
    before = account.spent

    account.record_call(
        "openai_compatible",
        "kin-test-model",
        3,
        CallOutcome.UNAVAILABLE,
        reason=UnavailableReason.RUN_COST_CAP_REACHED,
    )

    assert account.spent == before
    assert account.calls == 1
    assert account.cap_refusals == 1
    assert not account.may_start_call()


def test_the_refusal_is_a_predicate_and_never_an_exception() -> None:
    """A run over its cap answers "no" as a value, because the Kin keeps playing either way."""

    account = ledger(cap=1)
    ok(account, 1_000_000, 1_000_000)

    assert not account.may_start_call()
    assert account.remaining() == 0
    assert not account.may_start_call()


def test_a_refusal_still_belongs_to_the_generation_it_was_made_for() -> None:
    """The scheduler needs to know a generation went unanswered, whatever the reason was."""

    account = ledger(cap=1)
    ok(account, 1_000_000, 0)
    account.record_call(
        "openai_compatible",
        "kin-test-model",
        12,
        CallOutcome.UNAVAILABLE,
        reason=UnavailableReason.RUN_COST_CAP_REACHED,
    )

    assert len(account.by_generation(12)) == 1
    assert account.by_generation(11) == ()


def test_calls_and_refusals_are_counted_apart() -> None:
    account = ledger(cap=5_000)
    for generation in range(1, 4):
        ok(account, 100, 100, generation)
    for _ in range(3):
        account.record_call(
            "openai_compatible",
            "kin-test-model",
            9,
            CallOutcome.UNAVAILABLE,
            reason=UnavailableReason.RUN_COST_CAP_REACHED,
        )

    assert len(account.records) == 6
    assert account.calls == 3
    assert account.cap_refusals == 3


# ---------------------------------------------------------------------------
# The projection
# ---------------------------------------------------------------------------


def test_the_projection_states_the_cap_the_spend_the_rate_and_every_outcome() -> None:
    """§5 lets the dashboard show call count and spend; the rate travels with both.

    Every outcome key is present even when nothing landed there, because an absent key and a
    zero are different facts to a reader comparing runs.
    """

    account = ledger(cap=1_000)
    ok(account, 40_000, 8_000, 4)
    account.record_call(
        "openai_compatible",
        "kin-test-model",
        5,
        CallOutcome.REJECTED,
        reason=UnavailableReason.DECISION_OUT_OF_BOUNDS,
    )

    document = account.as_document()

    assert document["run_cost_cap"] == 1_000
    assert document["spent_estimate"] == account.spent
    assert document["remaining"] == account.remaining()
    assert document["cap_reached"] is False
    assert document["calls"] == 2
    assert document["cap_refusals"] == 0
    assert document["request_micro_per_million_tokens"] == DEFAULT_REQUEST_MICRO_PER_MILLION_TOKENS
    assert document["response_micro_per_million_tokens"] == (
        DEFAULT_RESPONSE_MICRO_PER_MILLION_TOKENS
    )
    counts = cast(dict[str, int], document["outcome_counts"])
    assert set(counts) == {outcome.value for outcome in CallOutcome}
    assert counts["ok"] == 1
    assert counts["rejected"] == 1
    assert document["reason_counts"] == {"DECISION_OUT_OF_BOUNDS": 1}
    assert isinstance(document["records"], list)


def test_the_projection_marks_a_run_that_stopped_calling_without_stopping_the_run() -> None:
    """`cap_reached` is the difference between an expensive model and a Kin that quit.

    A reader who sees no calls and no flag has to guess; the flag answers the question before it
    is asked.
    """

    account = ledger(cap=2)
    ok(account, 1_000_000, 0)
    account.record_call(
        "openai_compatible",
        "kin-test-model",
        1,
        CallOutcome.UNAVAILABLE,
        reason=UnavailableReason.RUN_COST_CAP_REACHED,
    )

    document = account.as_document()

    assert document["cap_reached"] is True
    assert document["calls"] == 1
    assert document["cap_refusals"] == 1


def test_a_record_names_the_call_not_the_credential() -> None:
    """A list of records is projected into documents and tracebacks, so it holds no text.

    `CostRecord`'s fields are enumerated or numeric by shape, not by discipline: there is no
    field a response body or a key could be put into.
    """

    account = ledger()
    ok(account, 1_000, 1_000)

    record = account.records[0]
    printed = repr(record) + str(record.as_document()) + str(account.as_document())

    assert {field.name for field in fields(CostRecord)} == {
        "provider",
        "model",
        "request_tokens",
        "response_tokens",
        "estimated_cost",
        "intent_generation",
        "outcome",
        "reason",
        "status_code",
        # Redacted diagnostics: our own numbers and phase tokens, never endpoint text.
        "attempts",
        "timeout_ms",
        "elapsed_ms",
        "phase",
    }
    assert FAKE_KEY not in printed
    assert record.outcome is CallOutcome.OK
    assert record.reason is None


def test_a_status_code_is_kept_because_which_status_arrived_is_the_whole_diagnosis() -> None:
    account = ledger()
    account.record_call(
        "openai_compatible",
        "kin-test-model",
        1,
        CallOutcome.UNAVAILABLE,
        reason=UnavailableReason.PROVIDER_STATUS,
        status_code=503,
    )

    assert account.records[0].as_document()["status_code"] == 503
    assert "503" in repr(account.records[0])


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_the_ledger_is_capped_the_way_the_operator_configured_it() -> None:
    config = ModelConfig(run_cost_cap=12_345)

    assert cost_ledger_for(config).run_cost_cap == 12_345
    assert cost_ledger_for(ModelConfig()).run_cost_cap == DEFAULT_RUN_COST_CAP_MICRO


@pytest.mark.parametrize(
    ("cap", "request_rate", "response_rate"),
    [(0, 1, 1), (-1, 1, 1), (10, -1, 1), (10, 1, -1)],
)
def test_an_unspellable_account_is_refused_at_construction(
    cap: int, request_rate: int, response_rate: int
) -> None:
    """A cap of zero is "never call", which is `off`; a negative rate is arithmetic nonsense.

    Both would otherwise show up as a spend account that silently refuses everything, which
    reads as a broken model rather than a broken configuration.
    """

    with pytest.raises(ValueError):
        CostLedger(
            run_cost_cap=cap,
            request_micro_per_million_tokens=request_rate,
            response_micro_per_million_tokens=response_rate,
        )
