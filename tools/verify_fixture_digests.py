"""Verify the frozen W00 schema and fixture digest manifest."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPOSITORY_ROOT / "tests" / "fixtures" / "manifest.sha256"
FROZEN_PATTERNS = (
    "buf.yaml",
    "buf.gen.yaml",
    "proto/**/*.proto",
    "schemas/*.json",
    "src/minekin_core/adapters/sqlite/**/*.sql",
    "tests/fixtures/**/*.json",
    "tests/oracle/canary.json",
)


def _normalized_bytes(path: Path) -> bytes:
    """Hash repository text canonically so Windows and Linux agree."""

    return path.read_bytes().replace(b"\r\n", b"\n")


def _expected_paths() -> set[str]:
    return {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for pattern in FROZEN_PATTERNS
        for path in REPOSITORY_ROOT.glob(pattern)
        if path.is_file()
    }


def violations() -> list[str]:
    errors: list[str] = []
    listed: set[str] = set()
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
        listed.add(logical_path.as_posix())
        path = REPOSITORY_ROOT.joinpath(*logical_path.parts)
        if not path.is_file():
            errors.append(f"manifest.sha256:{line_number}: missing {raw_path}")
            continue
        actual = hashlib.sha256(_normalized_bytes(path)).hexdigest()
        if actual != expected:
            errors.append(
                f"manifest.sha256:{line_number}: digest mismatch for {raw_path}: "
                f"expected {expected}, got {actual}"
            )
    missing = _expected_paths() - listed
    extra = listed - _expected_paths()
    errors.extend(f"manifest.sha256: unlisted frozen file {path}" for path in sorted(missing))
    errors.extend(f"manifest.sha256: stale entry {path}" for path in sorted(extra))
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
