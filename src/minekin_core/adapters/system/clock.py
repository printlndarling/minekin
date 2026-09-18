"""The real clock.

Only this module is allowed to ask the operating system what time it is, which
is what keeps every other clock-dependent decision testable with `FakeClock`.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from minekin_core.domain.time import MonotonicInstant, UtcInstant


class SystemClock:
    """Monotonic time for deadlines, wall time for human audit only."""

    def monotonic(self) -> MonotonicInstant:
        return MonotonicInstant(time.monotonic_ns())

    def utc_now(self) -> UtcInstant:
        return UtcInstant(datetime.now(UTC))
