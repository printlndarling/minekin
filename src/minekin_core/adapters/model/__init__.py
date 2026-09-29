"""Model provider adapters: the port the mind chooses through, and what fills it.

`ModelProvider` is the port §2 of `docs/s3-minimal-player-mind.md` names — one method, a
request the local layer built, and an answer that is either a structured decision or a
named unavailability. Nothing else crosses it: no keystroke, no item the request did not
mention, no claim that something happened.

Two implementations, and the smaller one matters more than it looks. `OffModelProvider` is
what a machine with no model credentials uses: it answers without a network, a key, a cost
or an exception, because `off` is a product capability rather than a missing dependency.
The real endpoint is in `openai_compatible.py`, and this package re-exports it so one import
is enough for a caller. That is safe because nothing in `openai_compatible.py` imports back
from here — the port is structural, so an implementation has no reason to know its name.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from minekin_core.adapters.model.openai_compatible import OpenAICompatibleProvider
from minekin_core.domain.model_access import (
    CostLedger,
    Decision,
    DecisionRequest,
    ModelConfig,
    ModelUnavailable,
    UnavailableReason,
    cost_ledger_for,
)

__all__ = [
    "ModelProvider",
    "OffModelProvider",
    "OpenAICompatibleProvider",
    "model_provider_for",
]


class ModelProvider(Protocol):
    """The only thing the mind may ask of a model.

    `decide` is total by contract: it returns a `Decision` it can name a reason for, or a
    `ModelUnavailable` that names why there is none. It does not raise for a model that
    timed out, answered wrongly, or is not configured, and it does not accept a choice
    outside the feasible set it was handed — the caller keeps its event and its goal and
    takes the same conservative path whatever arrived.
    """

    def decide(self, request: DecisionRequest) -> Decision | ModelUnavailable: ...


@dataclass(frozen=True, slots=True)
class OffModelProvider:
    """The provider used when there is no model: a named result, no cost, no network.

    Deliberately writes nothing to a ledger. The ledger accounts for calls (§4), and a run
    that never asked anything has nothing to account for; filling it with `off` refusals
    would make the dashboard read as though the model had been failing all session.
    """

    reason: UnavailableReason = UnavailableReason.MODEL_NOT_CONFIGURED

    def decide(self, request: DecisionRequest) -> Decision | ModelUnavailable:
        # `request` is unread on purpose: there is nothing here to weigh, and a provider
        # that could inspect it would be a provider someone might mistake for a model.
        return ModelUnavailable(self.reason)


def model_provider_for(
    config: ModelConfig,
    environ: Mapping[str, str] | None = None,
    ledger: CostLedger | None = None,
) -> ModelProvider:
    """The provider this operator configured, and the seam the session should call.

    `off` yields `OffModelProvider`; anything else `model_config` accepted yields the real
    endpoint. A ledger built here is the provider's own, so a caller that wants the spend
    projection passes one in — which is also how a run keeps a single account across more
    than one provider object.
    """

    if not config.enabled:
        return OffModelProvider()
    return OpenAICompatibleProvider(
        config, environ, ledger=ledger if ledger is not None else cost_ledger_for(config)
    )
