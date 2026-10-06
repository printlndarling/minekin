"""The newest reported outcome per action id, for skills that must read their own press.

Found by reading the wire: the Bridge answers every input command with an
`ActionResult` (a status and a reason code), and Core counted those only in
aggregate -- so the refused swing measured on runV (`bridge refused mine …:
MINE_TARGET_NOT_AIMED` at the press frame, the slop of a hop the client saw a
frame earlier) was invisible to the skill that sent it, which then believed its
press had landed and never swung again. This is the per-action copy.

Bounded on purpose: the newest outcome for the most recent ids and nothing
older than the capacity. A skill asks about one id it just sent; a registry
that grew forever would be a second ledger with no retention rule.
"""

from __future__ import annotations

from typing import Final

#: The status vocabulary the runtime already derives from the wire, so this
#: module never renames anything: the strings the run documents already carry.
ACCEPTED: Final = "ACCEPTED"
STARTED: Final = "STARTED"
SUCCEEDED: Final = "SUCCEEDED"
FAILED: Final = "FAILED"
CANCELLED: Final = "CANCELLED"


class ActionOutcomeRegistry:
    """[action_id] -> newest (status, reason_code), at most `CAPACITY` entries."""

    CAPACITY: Final[int] = 64

    def __init__(self) -> None:
        self._outcomes: dict[str, tuple[str, str]] = {}

    def record(self, action_id: str, *, status: str, reason_code: str = "") -> None:
        if not action_id or not status:
            return
        # Reinsert so the newest outcome is also the most-recently-touched entry,
        # which is what makes the capacity prune the oldest id rather than a
        # random one.
        self._outcomes.pop(action_id, None)
        self._outcomes[action_id] = (status, reason_code)
        while len(self._outcomes) > self.CAPACITY:
            oldest = next(iter(self._outcomes))
            del self._outcomes[oldest]

    def latest(self, action_id: str) -> tuple[str, str] | None:
        return self._outcomes.get(action_id)

    def refused(self, action_id: str, reason_code: str) -> bool:
        """Whether this id's newest outcome is a failure under exactly this name.

        Exact matching is the point: one action id carries every input a step
        sent under it, and `MINE_TARGET_NOT_AIMED` is the mine handler's own
        word -- a walk's refusal can never be mistaken for a swing's.
        """

        return self._outcomes.get(action_id) == (FAILED, reason_code)
