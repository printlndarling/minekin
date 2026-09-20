"""Reporting one sealed soak's resources — the numbers, and only the numbers.

The contract's L6 is a baseline that reports rather than one that passes, so what
these tests pin is the reporting itself: that the distribution comes from the
sealed bytes, that it is computed the way the tool says it is, and that a bundle
which holds no soak is answered with "no soak" rather than with zeroes.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from minekin_core.adapters.evidence.bundle import unseal_bundle

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROFILE = REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"
SERVER_PROFILE = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "controlled-offline-server.json"
)
SOAK_CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "core-100.json"
OTHER_CASE = REPOSITORY_ROOT / "tests" / "fixtures" / "cases" / "core-020.json"
RUN_ID = "9f2c1d4e5a6b7c8d9e0f1a2b3c4d5e6f"
SESSION_ID = "3b7c9d1e2f4a5b6c7d8e9f0a1b2c3d4e"
KIN = "kin-01"
USERNAME = "Kin"


def tool(name: str) -> ModuleType:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module(f"tools.{name}")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


REPORTER = tool("report_soak")
SEALER = tool("seal_run_evidence")


@pytest.fixture(autouse=True)
def _leave_bundles_writable(tmp_path: Path) -> Iterator[None]:
    yield
    for found in sorted(tmp_path.rglob("manifest.json")):
        unseal_bundle(found.parent)


def run_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "started",
        "kin_id": KIN,
        "run_id": RUN_ID,
        "session_id": SESSION_ID,
        "generation": 1,
        "pid": 184,
        "started_at": "2026-09-20T10:32:00Z",
        "argv_digest": "a" * 64,
        "recovery": {"invalidated": [], "waiting": [], "status": "reconciled"},
        "run": {
            "schema_version": 1,
            "status": "ended",
            "outcome": "BRIDGE_LOST",
            "session_state": "STOPPED",
            "connection_state": "PLAYABLE",
            "events_applied": 5,
            "events_ignored": 0,
            "snapshots_admitted": 1,
            "snapshot_rejections": [],
            "entities_admitted": 0,
            "entities_rejected": 0,
            "actions_applied": 0,
            "actions_refused": 0,
            "input_release_failed": False,
            "input_refusal": "",
        },
    }


def soak_files(tmp_path: Path, samples: str, summary: Mapping[str, object]) -> tuple[Path, Path]:
    samples_path = tmp_path / "soak-samples.txt"
    summary_path = tmp_path / "soak-summary.json"
    samples_path.write_text(samples, encoding="utf-8", newline="\n")
    summary_path.write_text(json.dumps(summary), encoding="utf-8", newline="\n")
    return samples_path, summary_path


def a_summary(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": 1,
        "requested_seconds": 600,
        "interval_seconds": 10,
        "passes": 3,
        "samples": {"client": 3, "server": 3},
        "ended_early": False,
        "failed_samples": False,
    }
    document.update(overrides)
    return document


MEASURED = (
    "client 512000 40 0\n"
    "client 514048 41 300\n"
    "client 516096 42 600\n"
    "server 921600 30 0\n"
    "server 921600 30 300\n"
    "server 923648 31 600\n"
)


def sealed_soak(tmp_path: Path, samples: str = MEASURED, **summary: object) -> Path:
    """A real bundle, sealed by the real sealer, with a soak in it."""

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    server = tmp_path / "server-runs" / "run-97"
    server.mkdir(parents=True, exist_ok=True)
    (server / "server.log").write_text("", encoding="utf-8")
    document = tmp_path / "session.json"
    document.write_text(json.dumps(run_document()), encoding="utf-8")
    samples_path, summary_path = soak_files(tmp_path, samples, a_summary(**summary))
    SEALER.seal(
        data_root=data_root,
        case=SOAK_CASE,
        profile=PROFILE,
        server_profile=SERVER_PROFILE,
        run_document_path=document,
        server_directory=server,
        username=USERNAME,
        renderer_display="llvmpipe (LLVM 20.1.2, 256 bits)",
        soak_samples_path=samples_path,
        soak_summary_path=summary_path,
    )
    return data_root


def test_the_report_is_computed_from_the_bytes_the_bundle_sealed(tmp_path: Path) -> None:
    data_root = sealed_soak(tmp_path)

    report = REPORTER.report(data_root, RUN_ID)

    assert report["status"] == "reported"
    assert report["case_id"] == "CORE-100"
    assert report["requested_seconds"] == 600
    assert report["percentile_method"] == "nearest-rank"
    assert report["processes"]["client"]["samples"] == 3
    # 512000 KiB is 500 MiB; the median of the three client readings is the
    # middle one, and the maximum is the last.
    assert report["processes"]["client"]["rss_mb"]["p50"] == pytest.approx(502.0)
    assert report["processes"]["client"]["rss_mb"]["maximum"] == pytest.approx(504.0)
    assert report["processes"]["client"]["threads"]["maximum"] == 42
    assert report["processes"]["server"]["threads"]["maximum"] == 31
    assert report["processes"]["client"]["last_elapsed_seconds"] == 600


def test_the_report_carries_the_machine_it_was_measured_on(tmp_path: Path) -> None:
    """A baseline without its environment is a number nobody can compare to."""

    data_root = sealed_soak(tmp_path)

    report = REPORTER.report(data_root, RUN_ID)

    environment = cast(Mapping[str, object], report["environment"])
    assert environment["renderer_display"] == "llvmpipe (LLVM 20.1.2, 256 bits)"
    assert environment["os_kernel"]
    assert environment["java_runtime"]


def test_a_bundle_without_a_soak_is_answered_with_no_soak(tmp_path: Path) -> None:
    """Absent is not zero: a run that never soaked has no distribution at all."""

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    server = tmp_path / "server-runs" / "run-98"
    server.mkdir(parents=True, exist_ok=True)
    (server / "server.log").write_text("", encoding="utf-8")
    document = tmp_path / "session.json"
    document.write_text(json.dumps(run_document()), encoding="utf-8")
    SEALER.seal(
        data_root=data_root,
        case=OTHER_CASE,
        profile=PROFILE,
        server_profile=SERVER_PROFILE,
        run_document_path=document,
        server_directory=server,
        username=USERNAME,
        renderer_display="llvmpipe (LLVM 20.1.2, 256 bits)",
    )

    with pytest.raises(REPORTER.NoSoak):
        REPORTER.report(data_root, RUN_ID)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([100], {"p50": 100 / 1024, "p95": 100 / 1024, "p99": 100 / 1024}),
        (
            list(range(1, 101)),
            {"p50": 50 / 1024, "p95": 95 / 1024, "p99": 99 / 1024},
        ),
    ],
)
def test_the_percentiles_are_the_nearest_rank_ones(
    values: list[int], expected: dict[str, float]
) -> None:
    """One sample has one value at every percentile, and rank is what the tool says."""

    assert REPORTER.percentiles(values) == pytest.approx(expected)


def test_samples_that_are_not_the_samplers_shape_are_not_a_distribution() -> None:
    assert REPORTER.parse_samples("client 1 2 3\nwhat is this\n") is None
    assert REPORTER.parse_samples("client 1 2 3\nclient 1 2\n") is None
    assert REPORTER.parse_samples("client 1 2 3\nclient 1 2 4\n") == {
        "client": [(1, 2, 3), (1, 2, 4)],
        "server": [],
    }


def test_the_sealer_seals_what_the_report_computes_from(tmp_path: Path) -> None:
    """The two halves are one reading: the artifact is the bytes that were judged."""

    data_root = sealed_soak(tmp_path)
    bundle = data_root / "kin" / KIN / "run" / "evidence" / RUN_ID

    assert (bundle / "soak-samples.txt").read_text(encoding="utf-8") == MEASURED
    summary = json.loads((bundle / "soak-summary.json").read_text(encoding="utf-8"))
    assert summary["requested_seconds"] == 600
    report = cast(dict[str, Any], REPORTER.report(data_root, RUN_ID))
    assert report["ended_early"] is False
