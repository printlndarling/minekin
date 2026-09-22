"""What the Bridge's own callbacks cost, aggregated where the windows arrive.

The prototype contract asks the prototype to record callback wall time and its
P50/P95/P99, and separately forbids the IPC path from stalling the client thread.
The Bridge measures; this is where the measurement becomes evidence. Every window
that arrives is read here and folded into one bounded series per label, because the
run document is an artifact: a shape that grew with the length of the run would make
a long run unsealable for no reason beyond its length.

Three things are bounded and they are bounded in the same direction. The Bridge's
sampler keeps a fixed number of samples per window. The window's message carries at
most that many. What lands on the run document is a fixed set of aggregates per
label, plus one integer per window that did not arrive — so nothing in this chain
grows with how long a Kin ran.

**A window that did not arrive is a fact, and it is derived rather than counted.**
The Bridge numbers a window when it closes and not when it is published, so a
delivered 1, 2 and 4 say that 3 was built and dropped. Reading that from the numbers
themselves is why `missing_windows` exists instead of a skip counter: a counter
travels in a later message and is lost with the run that never got to send it.

**The percentiles are over retained samples, and the method is stated.** Nearest-rank
over what the pool holds — the same method `tools/report_soak.py` reports resources
with, so two distributions in one bundle are not silently two different statistics.
A series whose pool could not hold everything says how much it dropped rather than
answering as though it had seen it all.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Protocol

#: The series a window may name. Closed on this side on purpose: the Bridge's
#: `BridgeMetrics` spells them, a test binds the two spellings, and a label this
#: build cannot name is a report it counts rather than believes.
TICK_LABEL: Final = "tick"
INTERVAL_LABEL: Final = "tick_interval"
BUDGET_LABELS: Final[tuple[str, ...]] = (TICK_LABEL, INTERVAL_LABEL)

#: Nearest-rank: the value at `ceil(p/100 * n)` in sorted order. Named in the
#: document so "P95" is one number rather than a family.
PERCENTILE_METHOD: Final = "nearest-rank"

#: How many samples one series keeps for its run-level percentiles. A ten-second
#: window of a healthy client holds a couple of hundred ticks, so this is about an
#: hour of running; a series that outlasts it keeps the newest and says how many it
#: could not keep.
POOL_CAPACITY: Final = 65_536

_NAMED_PERCENTILES: Final[tuple[tuple[str, float], ...]] = (
    ("p50", 0.50),
    ("p95", 0.95),
    ("p99", 0.99),
)


class BudgetRefusal(StrEnum):
    """Why a reported window was not recorded."""

    #: A label this build does not know. The Bridge names which series it is
    #: reporting and this side decides whether that name means anything.
    UNKNOWN_LABEL = "UNKNOWN_LABEL"
    #: Window numbers are 1-based, so zero is not one: it is a report whose ordinal
    #: was never taken, which would make the holes in the sequence meaningless.
    ZERO_WINDOW = "ZERO_WINDOW"
    #: The window says more samples are retained than arrived. That is not a sampled
    #: series with a truncation, it is a report contradicting itself.
    RETENTION_EXCEEDS_RECORDED = "RETENTION_EXCEEDS_RECORDED"


class ReportedWindow(Protocol):
    """The wire message, as much of it as this module reads.

    A protocol rather than the generated class, so the rules below can be tested
    against a window built in a test without a socket — and so nothing here depends
    on generated code to state what a report means. Read-only, because that is also
    the truth about this module's use of it: it reads a report and never writes one.
    """

    @property
    def label(self) -> str: ...

    @property
    def window(self) -> int: ...

    @property
    def opened_at_nanos(self) -> int: ...

    @property
    def recorded(self) -> int: ...

    @property
    def micros(self) -> Sequence[int]: ...


def percentiles(values: Sequence[int]) -> dict[str, int]:
    """The named percentiles of one series, in the unit it was read in.

    Empty series are absent rather than zero: a series nobody sampled has no median,
    and reporting one would be reporting a measurement that was never taken.
    """

    ordered = sorted(values)
    if not ordered:
        return {}
    reported: dict[str, int] = {}
    for name, fraction in _NAMED_PERCENTILES:
        rank = max(1, math.ceil(fraction * len(ordered)))
        reported[name] = ordered[rank - 1]
    return reported


@dataclass(frozen=True, slots=True)
class BudgetWindow:
    """One window of one series, after the report was judged readable."""

    label: str
    window: int
    opened_at_nanos: int
    recorded: int
    micros: tuple[int, ...]

    @property
    def retained(self) -> int:
        return len(self.micros)

    @property
    def skipped(self) -> int:
        """Samples the Bridge's ring could not hold for this window."""

        return self.recorded - self.retained

    def as_document(self) -> dict[str, object]:
        return {
            "label": self.label,
            "window": self.window,
            "opened_at_nanos": self.opened_at_nanos,
            "recorded": self.recorded,
            "retained": self.retained,
            "skipped": self.skipped,
            "minimum_micros": min(self.micros) if self.micros else None,
            "maximum_micros": max(self.micros) if self.micros else None,
            **percentiles(self.micros),
        }


def read_window(message: ReportedWindow) -> tuple[BudgetWindow | None, BudgetRefusal | None]:
    """Judge one reported window, returning it or the reason it was refused.

    The three refusals are the ways a report can fail to be about anything: a series
    nobody named, an ordinal that was never taken, and a retention larger than what
    arrived. Everything else is recorded as it was sent — this gate decides whether a
    report is readable, not whether the numbers in it are good.
    """

    if message.label not in BUDGET_LABELS:
        return None, BudgetRefusal.UNKNOWN_LABEL
    if message.window <= 0:
        return None, BudgetRefusal.ZERO_WINDOW
    if len(message.micros) > message.recorded:
        return None, BudgetRefusal.RETENTION_EXCEEDS_RECORDED
    return (
        BudgetWindow(
            label=message.label,
            window=message.window,
            opened_at_nanos=message.opened_at_nanos,
            recorded=message.recorded,
            micros=tuple(message.micros),
        ),
        None,
    )


@dataclass(slots=True)
class _Series:
    """One label's running aggregate, bounded whatever the run does."""

    first_window: int = 0
    last_window: int = 0
    windows: int = 0
    recorded: int = 0
    retained: int = 0
    numbers: set[int] = field(default_factory=set[int])
    pool: list[int] = field(default_factory=list[int])
    dropped: int = 0

    def observe(self, window: BudgetWindow) -> None:
        if self.windows == 0:
            self.first_window = window.window
        self.last_window = window.window
        self.windows += 1
        self.recorded += window.recorded
        self.retained += window.retained
        self.numbers.add(window.window)
        for sample in window.micros:
            if len(self.pool) == POOL_CAPACITY:
                # The newest, for the same reason the Bridge keeps the newest: the
                # tail is what a stall shows up in. What it cost is counted.
                self.pool.pop(0)
                self.dropped += 1
            self.pool.append(sample)

    def missing(self) -> tuple[int, ...]:
        """The ordinals in this series' range that no window claimed.

        Empty when nothing was ever reported: a run whose Bridge never published has
        no sequence to have holes in, which is not the same fact as a run whose
        windows were all dropped.
        """

        if self.windows == 0:
            return ()
        return tuple(
            number
            for number in range(self.first_window, self.last_window + 1)
            if number not in self.numbers
        )

    def as_document(self) -> dict[str, object]:
        return {
            "windows": self.windows,
            "first_window": self.first_window if self.windows else None,
            "last_window": self.last_window if self.windows else None,
            # One integer per window the Bridge built and could not deliver. Derived
            # from the ordinals rather than carried as a counter, so it survives the
            # full outbox it is reporting on.
            "missing_windows": list(self.missing()),
            "recorded_samples": self.recorded,
            "retained_samples": self.retained,
            "skipped_samples": self.recorded - self.retained,
            "pooled_samples": len(self.pool),
            "unpooled_samples": self.dropped,
            "minimum_micros": min(self.pool) if self.pool else None,
            "maximum_micros": max(self.pool) if self.pool else None,
            **percentiles(self.pool),
        }


@dataclass(slots=True)
class BudgetLedger:
    """Every budget window one run received, folded into one series per label."""

    series: dict[str, _Series] = field(default_factory=dict[str, _Series])
    refusals: dict[str, int] = field(default_factory=dict[str, int])

    def observe(self, window: BudgetWindow) -> None:
        self.series.setdefault(window.label, _Series()).observe(window)

    def refuse(self, reason: BudgetRefusal) -> None:
        """Count a report this build could not record, by reason.

        Counted rather than dropped, for the reason every other refusal in the run
        document is: a report that arrived and was not recorded is a fact about the
        run, and silence about it reads exactly like a Bridge that reported nothing.
        """

        self.refusals[reason.value] = self.refusals.get(reason.value, 0) + 1

    @property
    def received(self) -> int:
        return sum(series.windows for series in self.series.values())

    def as_document(self) -> Mapping[str, object]:
        return {
            "percentile_method": PERCENTILE_METHOD,
            "pool_capacity": POOL_CAPACITY,
            "received_windows": self.received,
            "report_refusals": dict(self.refusals),
            # One entry per label this build knows, whether or not the run ever
            # reported it: a series with no windows and a series that was never
            # named are different, and only the first is a zero here.
            "series": {
                label: self.series[label].as_document()
                if label in self.series
                else _Series().as_document()
                for label in BUDGET_LABELS
            },
        }
