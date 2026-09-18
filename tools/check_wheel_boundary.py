"""Reject product wheels containing test/oracle material."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

FORBIDDEN = (
    "tests/oracle",
    "tests.oracle",
    "test-orchestrator",
    "test_orchestrator",
    "minekin_test_oracle",
)


def violations(wheel: Path) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            name = info.filename.casefold()
            if not (name.startswith("minekin_core/") or ".dist-info/" in name):
                errors.append(f"unexpected wheel member: {info.filename}")
            if any(marker in name for marker in FORBIDDEN):
                errors.append(f"oracle marker in wheel path: {info.filename}")
            if info.file_size <= 1_000_000 and Path(name).suffix in {
                ".py",
                ".json",
                ".sql",
                ".txt",
            }:
                text = archive.read(info).decode("utf-8", errors="replace").casefold()
                if any(marker in text for marker in FORBIDDEN):
                    errors.append(f"oracle marker in wheel content: {info.filename}")
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
