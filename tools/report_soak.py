"""Report the resource distribution one sealed soak measured.

The contract's L6 is a baseline that *reports* rather than one that passes: no
human baseline exists yet, so nothing here sets a threshold, and calling anything
"good" would be inventing the number that is supposed to be measured. What this
prints is the distribution itself — per process, how much resident memory was
observed and how many threads, with the percentiles the contract names — taken
from the samples a sealed bundle holds.

It reads only sealed bytes. A distribution quoted from a live file is a claim
about a measurement; one computed from the artifact the run sealed is the
measurement. The bundle is verified first for the same reason: numbers computed
from bytes that no longer match their digests are numbers about something else.

Percentiles are nearest-rank — the value at `ceil(p/100 * n)` in sorted order —
which is stated in the output rather than left to the reader, because "P95" is
not one number until a method says which.

Exit codes: 0 reported, 1 the bundle holds no soak, 2 the bundle is not readable
or does not verify.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from minekin_core.adapters.evidence.bundle import verify_bundle  # noqa: E402
from minekin_core.cli.evidence import locate_bundle  # noqa: E402

EXIT_REPORTED = 0
EXIT_NO_SOAK = 1
EXIT_UNREADABLE = 2

SAMPLES_NAME = "soak-samples.txt"
SUMMARY_NAME = "soak-summary.json"
PERCENTILE_METHOD = "nearest-rank"
KB_PER_MB = 1024.0


class NoSoak(Exception):
    """The bundle this run sealed holds no soak to report."""


def percentiles(values: Sequence[int]) -> dict[str, float]:
    """The named percentiles of one series, in the unit they were read in.

    Empty series are absent rather than zero: a process that was never sampled
    has no median, and reporting one would be reporting a measurement that was
    never taken.
    """

    ordered = sorted(values)
    if not ordered:
        return {}
    reported: dict[str, float] = {}
    for name, fraction in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99)):
        rank = max(1, math.ceil(fraction * len(ordered)))
        reported[name] = ordered[rank - 1] / KB_PER_MB
    return reported


def parse_samples(text: str) -> dict[str, list[tuple[int, int, int]]] | None:
    """The samples per label, as (rss_kb, threads, elapsed_seconds).

    None when a line is not one: a file that has stopped being the shape the
    sampler writes is not a file to compute a median from.
    """

    per_label: dict[str, list[tuple[int, int, int]]] = {"client": [], "server": []}
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 4 or fields[0] not in per_label:
            return None
        try:
            per_label[fields[0]].append((int(fields[1]), int(fields[2]), int(fields[3])))
        except ValueError:
            return None
    return per_label


def _read(directory: Path, name: str) -> bytes | None:
    path = directory / name
    return path.read_bytes() if path.is_file() else None


def report(data_root: Path, run_id: str) -> dict[str, object]:
    """The distribution this run's soak measured, or why there is none."""

    try:
        directory = locate_bundle(data_root, run_id)
    except Exception as error:  # the product's own refusal for an unlocatable run
        raise LookupError(str(error)) from error
    verification = verify_bundle(directory)
    if not verification.verified:
        raise LookupError("the bundle does not verify: " + ",".join(verification.violations))

    summary_bytes = _read(directory, SUMMARY_NAME)
    samples_bytes = _read(directory, SAMPLES_NAME)
    if summary_bytes is None or samples_bytes is None:
        raise NoSoak("this bundle holds no soak")
    summary = json.loads(summary_bytes)
    if not isinstance(summary, dict):
        raise NoSoak("the soak summary is not an object")
    asked = cast(Mapping[str, object], summary)
    per_label = parse_samples(samples_bytes.decode("utf-8"))
    if per_label is None:
        raise LookupError("the soak samples are not the shape the sampler writes")

    manifest = verification.manifest
    if manifest is None:
        # A bundle that verified always carries a manifest — it is what was
        # verified — so this is the shape of the type rather than a state a
        # sealed bundle can be in, and it is refused rather than assumed away.
        raise LookupError("the bundle has no readable manifest")
    processes: dict[str, object] = {}
    for label, samples in per_label.items():
        rss = [sample[0] for sample in samples]
        threads = [sample[1] for sample in samples]
        elapsed = [sample[2] for sample in samples]
        processes[label] = {
            "samples": len(samples),
            "rss_mb": {
                "first": (rss[0] / KB_PER_MB) if rss else None,
                "last": (rss[-1] / KB_PER_MB) if rss else None,
                "minimum": (min(rss) / KB_PER_MB) if rss else None,
                "maximum": (max(rss) / KB_PER_MB) if rss else None,
                **percentiles(rss),
            },
            "threads": {
                "minimum": min(threads) if threads else None,
                "maximum": max(threads) if threads else None,
            },
            "last_elapsed_seconds": max(elapsed) if elapsed else None,
        }

    return {
        "schema_version": 1,
        "command": "report soak",
        "status": "reported",
        "run_id": run_id,
        "case_id": manifest.case_id,
        "evidence_directory": str(directory),
        "verdict": manifest.result.value,
        "requested_seconds": asked.get("requested_seconds"),
        "interval_seconds": asked.get("interval_seconds"),
        "ended_early": asked.get("ended_early"),
        "percentile_method": PERCENTILE_METHOD,
        "processes": processes,
        # The environment travels with the numbers, because a baseline without the
        # machine it was taken on is a number nobody can compare anything to.
        "environment": {
            "os_kernel": manifest.os_kernel,
            "java_runtime": manifest.java_runtime,
            "cpu_memory": manifest.cpu_memory,
            "renderer_display": manifest.renderer_display,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report one sealed soak's resources.")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)

    try:
        document = report(args.data_root, args.run_id)
    except NoSoak as refusal:
        print(json.dumps({"command": "report soak", "status": "no-soak", "reason": str(refusal)}))
        return EXIT_NO_SOAK
    except (LookupError, OSError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps({"command": "report soak", "status": "unreadable", "reason": str(error)}),
            file=sys.stderr,
        )
        return EXIT_UNREADABLE

    print(json.dumps(document, sort_keys=True))
    return EXIT_REPORTED


if __name__ == "__main__":
    raise SystemExit(main())
