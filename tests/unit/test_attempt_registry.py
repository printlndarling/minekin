from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from minekin_core.adapters.evidence.attempt_registry import (
    mark_sealed,
    read_attempts,
    reserve_attempt,
)
from minekin_core.domain.errors import MinekinError


def test_attempts_are_monotonic_and_explicitly_supersede(tmp_path: Path) -> None:
    path = tmp_path / "attempts.sqlite3"
    first = reserve_attempt(path, case_id="CORE-020", run_id="run-01")
    mark_sealed(path, first)
    second = reserve_attempt(path, case_id="CORE-020", run_id="run-02")
    other = reserve_attempt(path, case_id="CORE-030", run_id="run-03")

    assert (first.sequence, first.supersedes_run_id, first.status) == (1, None, "PENDING")
    assert (second.sequence, second.supersedes_run_id) == (2, "run-01")
    assert (other.sequence, other.supersedes_run_id) == (1, None)
    assert [(row.run_id, row.status) for row in read_attempts(path)] == [
        ("run-01", "SEALED"),
        ("run-02", "PENDING"),
        ("run-03", "PENDING"),
    ]


def test_concurrent_attempt_reservations_never_duplicate_sequences(tmp_path: Path) -> None:
    path = tmp_path / "attempts.sqlite3"
    run_ids = [f"run-{index:02}" for index in range(16)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(reserve_attempt, path, case_id="CORE-020", run_id=run_id)
            for run_id in run_ids
        ]
        attempts = [future.result() for future in futures]

    assert sorted(item.sequence for item in attempts) == list(range(1, 17))
    attempts_by_seq = sorted(attempts, key=lambda item: item.sequence)
    assert [item.supersedes_run_id for item in attempts_by_seq] == [
        None,
        *[item.run_id for item in attempts_by_seq[:-1]],
    ]


def test_reading_a_missing_registry_does_not_create_it(tmp_path: Path) -> None:
    path = tmp_path / "absent.sqlite3"

    assert read_attempts(path) == ()
    assert not path.exists()


def test_reading_a_corrupt_registry_does_not_repair_it(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"")

    with pytest.raises(MinekinError, match="attempt registry is unreadable"):
        read_attempts(path)

    assert path.read_bytes() == b""
