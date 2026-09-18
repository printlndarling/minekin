"""Verify the frozen W00 schema and fixture digest manifest."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPOSITORY_ROOT / "tests" / "fixtures" / "manifest.sha256"


def violations() -> list[str]:
    errors: list[str] = []
    for line_number, line in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        try:
            expected, raw_path = line.split("  ", 1)
        except ValueError:
            errors.append(f"manifest.sha256:{line_number}: malformed line")
            continue
        logical_path = PurePosixPath(raw_path)
        if logical_path.is_absolute() or ".." in logical_path.parts:
            errors.append(f"manifest.sha256:{line_number}: unsafe path {raw_path!r}")
            continue
        path = REPOSITORY_ROOT.joinpath(*logical_path.parts)
        if not path.is_file():
            errors.append(f"manifest.sha256:{line_number}: missing {raw_path}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(
                f"manifest.sha256:{line_number}: digest mismatch for {raw_path}: "
                f"expected {expected}, got {actual}"
            )
    return errors


def main() -> int:
    errors = violations()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("W00 schema and fixture digests: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
