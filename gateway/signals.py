"""Building the signal envelopes the Dashboard's decoder was written against.

The decoder is the contract: `dashboard/src/adapters/gatewayAdapter.ts` rejects a
whole read when an envelope is missing provenance, when a gap carries no reason, or
when a `known` value is the wrong type. It does not repair anything, so the shape has
to be right on the way out rather than guessed at on the way in.

Two levels of gap, because a field set frozen by
`docs/gateway-dashboard-readonly-contract-2026-09-28.md` contains groups whose
individual members differ in how honest they can be:

* The **envelope** is the level the decoder reads: `status`, `value`, `reason`, and
  the provenance trio `sourceRef` / `observedAt` / `staleAfterMs`.
* A **nested gap** is the level inside a group whose envelope is `known`, where one
  member has a carrier and its neighbour does not. Rendering such a member as a
  plausible default would be exactly the invention the contract forbids, so it
  travels as `{"gap": {"status", "reason"}}` and the UI shows it as a gap.
"""

from __future__ import annotations

from typing import Any, Literal

GapStatus = Literal["unknown", "unavailable", "not_wired", "permission_denied"]


def _provenance(
    source_ref: str, observed_at: str | None, stale_after_ms: int | None
) -> dict[str, Any]:
    return {"sourceRef": source_ref, "observedAt": observed_at, "staleAfterMs": stale_after_ms}


def _checked(reason: str, path: str) -> str:
    # The decoder judges every field on the envelope against a non-empty reason, so an
    # empty one is not a quieter gap: it turns the entire read red. Failing here names
    # the field that was left unwritten instead of leaving that to a browser.
    if not reason.strip():
        raise ValueError(f"{path} has a gap with no reason")
    return reason


def known(
    value: Any, *, source_ref: str, observed_at: str | None, stale_after_ms: int | None
) -> dict[str, Any]:
    """A reading Core actually answered, with the address it came from."""

    return {
        "status": "known",
        "value": value,
        **_provenance(source_ref, observed_at, stale_after_ms),
    }


def gap(
    status: GapStatus,
    reason: str,
    *,
    source_ref: str,
    observed_at: str | None,
    stale_after_ms: int | None,
) -> dict[str, Any]:
    """A field the read model cannot answer, named as one so it cannot render as a value."""

    return {
        "status": status,
        "reason": _checked(reason, source_ref),
        "value": None,
        **_provenance(source_ref, observed_at, stale_after_ms),
    }


def present(value: Any) -> dict[str, Any]:
    """One member of a `known` group that has a carrier."""

    return {"value": value}


def missing(status: GapStatus, reason: str) -> dict[str, Any]:
    """One member of a `known` group that does not."""

    return {"gap": {"status": status, "reason": _checked(reason, status)}}
