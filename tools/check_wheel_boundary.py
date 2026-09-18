"""Reject product wheels containing test/oracle material."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANARY = REPOSITORY_ROOT / "tests" / "oracle" / "canary.json"

FORBIDDEN = (
    "tests/oracle",
    "tests.oracle",
    "test-orchestrator",
    "test_orchestrator",
    "minekin_test_oracle",
)


def canary_value() -> str:
    """The value only the offline asserter knows.

    Markers catch a file that names the oracle; the canary catches a value that
    escaped it without naming anything.
    """

    document = json.loads(CANARY.read_bytes())
    value = document["canary"]
    if not isinstance(value, str) or not value:
        raise SystemExit("oracle canary is missing its value")
    return value


def violations(wheel: Path) -> list[str]:
    errors: list[str] = []
    canary = canary_value().casefold()
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            name = info.filename.casefold()
            if not (name.startswith("minekin_core/") or ".dist-info/" in name):
                errors.append(f"unexpected wheel member: {info.filename}")
            if any(marker in name for marker in FORBIDDEN):
                errors.append(f"oracle marker in wheel path: {info.filename}")
            if canary in name:
                errors.append(f"oracle canary in wheel path: {info.filename}")
            if info.file_size <= 1_000_000 and Path(name).suffix in {
                ".py",
                ".json",
                ".sql",
                ".txt",
            }:
                text = archive.read(info).decode("utf-8", errors="replace").casefold()
                if any(marker in text for marker in FORBIDDEN):
                    errors.append(f"oracle marker in wheel content: {info.filename}")
                if canary in text:
                    errors.append(f"oracle canary in wheel content: {info.filename}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    errors = violations(args.wheel)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Wheel oracle boundary: OK ({args.wheel})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
