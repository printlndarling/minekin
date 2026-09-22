"""What the Bridge's callback budget becomes once Core has it.

Three properties are the whole of what this layer promises, and each is one of the
ways a distribution can lie if it is not stated: the aggregate must not grow with
the length of the run, the samples a series could not keep must be counted rather
than averaged away, and a window that never arrived must be visible as the hole it
is rather than as a counter somebody has to trust.

None of this decides whether a budget is *good*. No threshold is set here and no
comparison is made against one — the contract says thresholds come after a
measurement, and the first measurement is the one this makes possible.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from minekin_core.domain.budget import (
    BUDGET_LABELS,
    INTERVAL_LABEL,
    PERCENTILE_METHOD,
    POOL_CAPACITY,
    TICK_LABEL,
    BudgetLedger,
    BudgetRefusal,
    percentiles,
    read_window,
)


@dataclass
class Wire:
    """A window as the wire reports one, built without a socket."""

    label: str = TICK_LABEL
    window: int = 1
    opened_at_nanos: int = 0
    recorded: int = 0
    micros: tuple[int, ...] = ()


def observed(ledger: BudgetLedger, **fields: object) -> None:
    window, refusal = read_window(Wire(**fields))  # type: ignore[arg-type]
    assert refusal is None, refusal
    assert window is not None
    ledger.observe(window)


def series(document: Mapping[str, object], label: str) -> Mapping[str, object]:
    return cast(Mapping[str, Mapping[str, object]], document["series"])[label]


# ---------------------------------------------------------------------------
# A report that cannot be read
# ---------------------------------------------------------------------------


def test_a_label_this_build_cannot_name_is_refused_rather_than_seriesed() -> None:
    """The Bridge says which series it is reporting; this side decides if it means anything."""

    window, refusal = read_window(Wire(label="tick_render", recorded=1, micros=(1,)))

    assert window is None
    assert refusal is BudgetRefusal.UNKNOWN_LABEL


def test_a_window_number_that_was_never_taken_is_refused() -> None:
    """Ordinals are 1-based, so zero would make every hole in the sequence meaningless."""

    window, refusal = read_window(Wire(window=0, recorded=1, micros=(1,)))

    assert window is None
    assert refusal is BudgetRefusal.ZERO_WINDOW


def test_a_report_holding_more_than_it_claims_arrived_is_refused() -> None:
    """Retention larger than the count is not a truncated series, it is a contradiction."""

    window, refusal = read_window(Wire(recorded=2, micros=(1, 2, 3)))

    assert window is None
    assert refusal is BudgetRefusal.RETENTION_EXCEEDS_RECORDED


def test_a_truncated_series_is_readable_and_says_what_it_lost() -> None:
    """The refusal above is about a contradiction, not about a series outrunning its ring."""

    window, refusal = read_window(Wire(recorded=9_000, micros=(1, 2, 3)))

    assert refusal is None
    assert window is not None
    assert (window.retained, window.skipped) == (3, 8_997)


def test_a_refused_report_is_counted_where_a_reader_can_see_it() -> None:
    """Silence about a refused report reads exactly like a Bridge that sent nothing."""

    ledger = BudgetLedger()
    _, refusal = read_window(Wire(label="nowhere"))
    assert refusal is not None
    ledger.refuse(refusal)

    document = ledger.as_document()

    assert document["received_windows"] == 0
    assert document["report_refusals"] == {"UNKNOWN_LABEL": 1}


# ---------------------------------------------------------------------------
# The series
# ---------------------------------------------------------------------------


def test_the_document_holds_every_label_this_build_knows() -> None:
    """A series nobody reported and a series that reported nothing are different facts."""

    ledger = BudgetLedger()
    observed(ledger, label=TICK_LABEL, window=1, recorded=3, micros=(10, 20, 30))

    document = ledger.as_document()

    assert set(cast(Mapping[str, object], document["series"])) == set(BUDGET_LABELS)
    assert series(document, TICK_LABEL)["windows"] == 1
    assert series(document, INTERVAL_LABEL)["windows"] == 0
    # Absent rather than zero: a series nobody sampled has no median to report.
    assert "p50" not in series(document, INTERVAL_LABEL)
    assert series(document, INTERVAL_LABEL)["minimum_micros"] is None
    assert "p50" in series(document, TICK_LABEL)


def test_the_percentiles_are_over_the_samples_the_run_kept() -> None:
    """Nearest-rank, and the method travels with the numbers it was used on."""

    ledger = BudgetLedger()
    for window in range(1, 4):
        observed(ledger, window=window, recorded=100, micros=tuple(range(100)))

    document = ledger.as_document()
    tick = series(document, TICK_LABEL)

    assert document["percentile_method"] == PERCENTILE_METHOD == "nearest-rank"
    assert tick["recorded_samples"] == 300
    assert tick["retained_samples"] == 300
    assert tick["skipped_samples"] == 0
    # Nearest-rank over 0..99: ceil(0.50*300)=150 -> 49, ceil(0.95*300)=285 -> 94,
    # ceil(0.99*300)=297 -> 98.
    assert (tick["p50"], tick["p95"], tick["p99"]) == (49, 94, 98)
    assert (tick["minimum_micros"], tick["maximum_micros"]) == (0, 99)


def test_an_empty_series_has_no_median_rather_than_a_zero_one() -> None:
    """A series nobody sampled has no P50, and reporting zero would be reporting a measurement."""

    assert percentiles([]) == {}


def test_the_pool_is_bounded_however_long_the_run_is() -> None:
    """The run document is an artifact: a long run must not make it unsealable."""

    ledger = BudgetLedger()
    observed(ledger, window=1, recorded=POOL_CAPACITY, micros=tuple(range(POOL_CAPACITY)))
    observed(ledger, window=2, recorded=1_000, micros=tuple(range(1_000)))

    tick = series(ledger.as_document(), TICK_LABEL)

    assert tick["pooled_samples"] == POOL_CAPACITY
    assert tick["unpooled_samples"] == 1_000
    # Counted as having happened even though the pool could not keep them.
    assert tick["recorded_samples"] == POOL_CAPACITY + 1_000


# ---------------------------------------------------------------------------
# The hole, which is the point
# ---------------------------------------------------------------------------


def test_a_window_that_never_arrived_is_a_missing_ordinal() -> None:
    """The one report the Bridge may drop is its own budget, and the evidence says so.

    Derived from the numbers that did arrive rather than carried as a counter: a
    counter would travel in a later window and would be lost with the run that never
    got to send one.
    """

    ledger = BudgetLedger()
    for window in (1, 2, 4):
        observed(ledger, window=window, recorded=1, micros=(5,))

    tick = series(ledger.as_document(), TICK_LABEL)

    assert tick["first_window"] == 1
    assert tick["last_window"] == 4
    assert tick["windows"] == 3
    assert tick["missing_windows"] == [3]


def test_a_run_whose_bridge_never_reported_has_no_sequence_to_have_holes_in() -> None:
    """A run with no windows and a run whose windows all dropped read the same here.

    Which is the honest answer and not a limitation: with nothing delivered there is
    no sequence, so there is nothing for a hole to be a hole in. What separates the
    two is `received_windows`, and in a real run the Bridge's own log says which it was.
    """

    document = BudgetLedger().as_document()

    assert series(document, TICK_LABEL)["missing_windows"] == []
    assert series(document, TICK_LABEL)["first_window"] is None
    assert series(document, TICK_LABEL)["last_window"] is None


def test_the_hole_is_an_ordinal_and_not_a_gap_in_a_count() -> None:
    """Two labels are numbered together, so a hole in one is a hole in both.

    The Bridge closes one window and reports both series under the same number, so a
    series that is missing window 3 is missing the same tick's worth of measurement
    as the other one — which is what lets a reader compare them.
    """

    ledger = BudgetLedger()
    for label in BUDGET_LABELS:
        for window in (1, 3):
            observed(ledger, label=label, window=window, recorded=1, micros=(5,))

    document = ledger.as_document()

    assert series(document, TICK_LABEL)["missing_windows"] == [2]
    assert series(document, INTERVAL_LABEL)["missing_windows"] == [2]


def test_a_window_with_repeated_ordinals_is_counted_not_merged() -> None:
    """A repeat is a report the Bridge should not have sent; the samples still happened.

    Silently folding it into the earlier window would lose the arithmetic, and the
    hole list is built from the set of ordinals, so a repeat cannot manufacture a
    hole either.
    """

    ledger = BudgetLedger()
    for _ in range(2):
        observed(ledger, window=1, recorded=2, micros=(1, 2))

    tick = series(ledger.as_document(), TICK_LABEL)

    assert tick["windows"] == 2
    assert tick["recorded_samples"] == 4
    assert tick["missing_windows"] == []
