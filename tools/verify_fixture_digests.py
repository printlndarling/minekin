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
    "tests/fixtures/saves/**/*.dat",
    "tests/oracle/canary.json",
)


class ManifestError(ValueError):
    """The frozen-fixture manifest cannot be interpreted unambiguously."""


def _normalized_bytes(path: Path) -> bytes:
    """Hash repository text canonically so Windows and Linux agree.

    Text only. A fixture that is not text is hashed as it lies: normalising a gzipped
    world would make the digest answer "was this checkout done on Windows?" instead of
    "is this the world the case started from?", which is the mistake the Bridge source
    tree made once with a suffix whitelist.
    """

    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    return raw.replace(b"\r\n", b"\n")


def _expected_paths() -> set[str]:
    return {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for pattern in FROZEN_PATTERNS
        for path in REPOSITORY_ROOT.glob(pattern)
        if path.is_file()
    }


def parse_manifest(manifest: Path | None = None) -> tuple[dict[str, tuple[int, str]], list[str]]:
    """The manifest's usable entries, by logical path, and the lines that are not.

    One reader for one file. The digest a caller gets is the one that was
    *reviewed* rather than one recomputed from the file on disk: asking a fixture
    whether it still matches itself is not a question worth answering, and a
    comparison against the reviewed value is the only kind that can fail.
    """

    manifest = MANIFEST if manifest is None else manifest
    entries: dict[str, tuple[int, str]] = {}
    errors: list[str] = []
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        try:
            expected, raw_path = line.split("  ", 1)
        except ValueError:
            errors.append(f"manifest.sha256:{line_number}: malformed line")
            continue
        if len(expected) != 64 or any(
            character not in "0123456789abcdef" for character in expected
        ):
            errors.append(f"manifest.sha256:{line_number}: malformed digest {expected!r}")
            continue
        logical_path = PurePosixPath(raw_path)
        canonical_path = logical_path.as_posix()
        if (
            logical_path.is_absolute()
            or ".." in logical_path.parts
            or "\\" in raw_path
            or raw_path != canonical_path
        ):
            errors.append(f"manifest.sha256:{line_number}: unsafe path {raw_path!r}")
            continue
        previous = entries.get(canonical_path)
        if previous is not None:
            errors.append(
                f"manifest.sha256:{line_number}: duplicate path {canonical_path!r} "
                f"(first listed on line {previous[0]})"
            )
            continue
        entries[canonical_path] = (line_number, expected)
    return entries, errors


def frozen_digests() -> dict[str, str]:
    """Every path the manifest freezes, and the digest it records for it.

    Public because "is this file still the one that was reviewed" is a question more
    than this gate asks: evidence that names a fixture has to be able to compare
    against the reviewed digest, and it must not keep its own copy of how to read
    the manifest to do it.
    """

    entries, errors = parse_manifest()
    if errors:
        raise ManifestError("; ".join(errors))
    return {path: digest for path, (_line, digest) in entries.items()}


def violations() -> list[str]:
    entries, errors = parse_manifest()
    for raw_path, (line_number, expected) in entries.items():
        path = REPOSITORY_ROOT.joinpath(*PurePosixPath(raw_path).parts)
        if not path.is_file():
            errors.append(f"manifest.sha256:{line_number}: missing {raw_path}")
            continue
        actual = hashlib.sha256(_normalized_bytes(path)).hexdigest()
        if actual != expected:
            errors.append(
                f"manifest.sha256:{line_number}: digest mismatch for {raw_path}: "
                f"expected {expected}, got {actual}"
            )
    listed = set(entries)
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
