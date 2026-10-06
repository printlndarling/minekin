"""What a model may commit the Kin to, and what the gateway refuses to keep.

Slice B of `docs/memory-gateway-implementation-plan.md`, under the retrieval
contract's rule 7: the LLM may suggest a reflection but never becomes the
authoritative writer — the model may suggest a durable intention, and this side
holds the schema, the budgets and the evidence check that decide whether it
becomes one. The candidate travels from the answer
(`Decision.commitment`, shaped but unjudged) to `judge_commitment_candidate`,
which is the single reader of what it may contain.

Four refusals, each by name, because "it did not become a commitment" is not one
kind of thing:

- `COMMITMENT_SCHEMA` — not an object, a field of the wrong type, or a field
  this schema does not declare. The last is the over-authority cell of the
  matrix: a commitment is an intention, not a permission, so the vocabulary
  contains no field that could round-trip as one — and a candidate carrying an
  undeclared key is refused rather than having it quietly dropped, because the
  writer is the one place that must never guess what an extra field was for.
- `COMMITMENT_NO_EVIDENCE` — nothing cited. The contract's "记起的是带出处的
  证据" is also a write rule: an intention with no reference behind it is a
  story, and stories are not stored as commitments.
- `COMMITMENT_UNBOUNDED` — empty text, or text/due past the budget. The same
  bound the reader carries with an ellipsis; a write past it is refused at the
  door instead of stored clipped, because this is remote text becoming a
  durable row.
- `COMMITMENT_UNKNOWN_EVIDENCE` — a reference that is not one of the tokens
  the answer was actually shown. Exact matching: near-misses are misses, which
  is what makes the citation checkable rather than decorative.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Final, cast

#: The longest a commitment's own text may be, aligned with the reason bound the
#: step ledger already carries (`goal_history.MAX_REASON_CHARS`): one sentence
#: of intention, not a paragraph.
MAX_COMMITMENT_CHARS: Final[int] = 240
#: "期限" is bounded but free-shaped for the first version: data the model wrote
#: down, carried to the next session as-is and never parsed as a schedule.
MAX_COMMITMENT_DUE_CHARS: Final[int] = 64

COMMITMENT_SCHEMA: Final = "COMMITMENT_SCHEMA"
COMMITMENT_NO_EVIDENCE: Final = "COMMITMENT_NO_EVIDENCE"
COMMITMENT_UNBOUNDED: Final = "COMMITMENT_UNBOUNDED"
COMMITMENT_UNKNOWN_EVIDENCE: Final = "COMMITMENT_UNKNOWN_EVIDENCE"

#: The whole vocabulary: a proposal, its optional when, and what it cites.
_CANDIDATE_KEYS: Final[frozenset[str]] = frozenset({"text", "due", "evidence_ref"})


@dataclass(frozen=True, slots=True)
class Commitment:
    """A judged candidate: an intention this side agreed to remember.

    `due` is `""` when the answer named none — absent stays absent rather than
    becoming a fabricated deadline.
    """

    text: str
    due: str
    evidence_ref: str


def judge_commitment_candidate(
    raw: object,
    *,
    witnesses: Collection[str],
    text_chars: int = MAX_COMMITMENT_CHARS,
    due_chars: int = MAX_COMMITMENT_DUE_CHARS,
) -> Commitment | str:
    """One candidate in, one `Commitment` or one refusal name out.

    `witnesses` is the set of references the answer was shown in its own offer
    (the observation handle, a shown event id): a citation outside it is an
    invention, and inventing evidence is the exact failure this gate exists for.
    """

    if not isinstance(raw, Mapping):
        return COMMITMENT_SCHEMA
    candidate = cast("Mapping[str, Any]", raw)
    if len(candidate) > len(_CANDIDATE_KEYS):
        return COMMITMENT_SCHEMA
    if any(key not in _CANDIDATE_KEYS for key in candidate):
        return COMMITMENT_SCHEMA
    text = candidate.get("text")
    due = candidate.get("due", "")
    evidence = candidate.get("evidence_ref", "")
    if not isinstance(text, str) or not isinstance(due, str) or not isinstance(evidence, str):
        return COMMITMENT_SCHEMA
    if not evidence:
        return COMMITMENT_NO_EVIDENCE
    stripped = text.strip()
    if not stripped or len(stripped) > text_chars or len(due) > due_chars:
        return COMMITMENT_UNBOUNDED
    if evidence not in witnesses:
        return COMMITMENT_UNKNOWN_EVIDENCE
    return Commitment(text=stripped, due=due, evidence_ref=evidence)
