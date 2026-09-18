from datetime import UTC, datetime

import pytest

from minekin_core.application.ports.clock import FakeClock
from minekin_core.domain.ids import Generation, KinId, OpaqueId, Sequence, SessionId
from minekin_core.domain.time import Deadline, MonotonicInstant, UtcInstant


@pytest.mark.parametrize("identifier", [KinId("kin-1"), SessionId("session:abc")])
def test_opaque_ids_are_strict_and_stringify(identifier: OpaqueId) -> None:
    assert str(identifier) == identifier.value


@pytest.mark.parametrize("value", ["", " leading", "a/b", "x" * 129, "秘密"])
def test_invalid_or_path_like_ids_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        KinId(value)


def test_generation_and_sequence_are_positive_uint64_monotonic() -> None:
    assert Generation(1).next() == Generation(2)
    assert Sequence(9).next() == Sequence(10)
    with pytest.raises(ValueError):
        Generation(0)
    with pytest.raises(ValueError):
        Sequence(0)
    with pytest.raises(OverflowError):
        Generation((1 << 64) - 1).next()


def test_generation_only_accepts_exact_current_generation() -> None:
    current = Generation(4)
    assert current.accepts(Generation(4))
    assert not current.accepts(Generation(3))


def test_deadline_uses_monotonic_time_and_expires_at_boundary() -> None:
    deadline = Deadline.after(MonotonicInstant(100), 20)
    assert deadline.remaining_ns(MonotonicInstant(110)) == 10
    assert not deadline.is_expired(MonotonicInstant(119))
    assert deadline.is_expired(MonotonicInstant(120))


def test_wall_clock_jump_does_not_change_monotonic_deadline() -> None:
    clock = FakeClock(100, datetime(2026, 1, 1, tzinfo=UTC))
    deadline = Deadline.after(clock.monotonic(), 10)
    clock.set_utc(datetime(1999, 1, 1, tzinfo=UTC))
    assert not deadline.is_expired(clock.monotonic())
    clock.advance(10)
    assert deadline.is_expired(clock.monotonic())


def test_utc_instant_requires_aware_datetime() -> None:
    with pytest.raises(ValueError):
        UtcInstant(datetime(2026, 1, 1))
