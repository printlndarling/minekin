"""Who decides an ordinary step — the vocabulary every layer spells the same way.

The policy is one choice with one spelling, and it lives in the domain because three layers
own a piece of it: the operator config persists it, the launch environment carries it, and the
mind reads it. The application layer (`application.player_mind`) is a reader of this module,
not its home — the dependency direction forbids the domain from importing the application, and
the words have to mean the same thing on both sides of that seam.

`MODEL` is the product's autonomy: the answerer chooses every ordinary step and its key
parameters from the offer it is shown, and a refusal — timeout, missing credential, spent
budget, malformed or illegal answer — stops the run under that name rather than letting local
code take the decision over. `RULES` is the explicitly selected offline strategy: the rule
order decides, the provider is never consulted, and every step records `local_reflection`.

There is no implicit third mode. An absent field, an `off` provider or a missing key reads as
`MODEL`; nothing selects `RULES` on the operator's behalf.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class DecisionPolicy(StrEnum):
    """The two strategies the operator may choose between, and no default here."""

    MODEL = "model"
    RULES = "rules"


#: The environment variable (and, through `operator_config`, the persisted field) through which
#: the operator explicitly selects the strategy. Unset means `MODEL`.
DECISION_POLICY_VARIABLE: Final = "MINEKIN_DECISION_POLICY"

#: The names a persisted document or an environment may select, sorted by the callers that
#: project a vocabulary. A value outside this set is refused by the layer that reads it —
#: `operator_config` at save time, the CLI at launch time.
KNOWN_POLICIES: Final[frozenset[str]] = frozenset(policy.value for policy in DecisionPolicy)


def decision_policy_from_environment(
    environ: Mapping[str, str] | None = None,
) -> DecisionPolicy:
    """The strategy the operator selected, or `MODEL` when the environment is silent.

    An empty value means "not selected"; anything else must be one of the declared names, and
    a misspelling is refused by name rather than quietly degrading to a default nobody chose.
    """

    source = os.environ if environ is None else environ
    raw = source.get(DECISION_POLICY_VARIABLE, "").strip().lower()
    if not raw:
        return DecisionPolicy.MODEL
    try:
        return DecisionPolicy(raw)
    except ValueError as exc:
        declared = ", ".join(policy.value for policy in DecisionPolicy)
        raise ValueError(f"{DECISION_POLICY_VARIABLE} must be one of: {declared}") from exc
