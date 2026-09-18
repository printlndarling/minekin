"""Regenerate the checked-in Python protobuf package deterministically.

The generated modules live in the product wheel, so they are committed and CI
re-runs this script to prove the committed bytes match the frozen schemas. buf
emits absolute ``minekin.v1`` imports; the product package is
``minekin_core.generated.minekin.v1``, so the imports are rewritten here and the
rewrite is verified rather than assumed.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from typing import Final

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GENERATED_ROOT = REPOSITORY_ROOT / "src" / "minekin_core" / "generated"
PROTO_PACKAGE = GENERATED_ROOT / "minekin" / "v1"
PROTO_STEMS: Final[tuple[str, ...]] = (
    "control",
    "envelope",
    "fault",
    "observation",
    "session",
)
EXPECTED_MODULES: Final[set[str]] = {
    f"{stem}_pb2{suffix}" for stem in PROTO_STEMS for suffix in (".py", ".pyi")
}
ABSOLUTE_IMPORT: Final[re.Pattern[str]] = re.compile(
    r"^from minekin\.v1 import ", flags=re.MULTILINE
)
UNNORMALIZED_IMPORT: Final[re.Pattern[str]] = re.compile(r"^from minekin\.v1", flags=re.MULTILINE)
PACKAGE_IMPORT: Final[str] = "from minekin_core.generated.minekin.v1 import "
PACKAGE_DOCSTRING: Final[str] = (
    '"""Generated protobuf package; regenerate with tools/generate_protos.py."""\n'
)


def _find_buf(explicit: str | None) -> str:
    executable = explicit or shutil.which("buf")
    if executable is None:
        raise SystemExit("buf is required; pass --buf or add it to PATH")
    return executable


def _generated_files() -> list[Path]:
    """Every file buf owns in the package; ``__init__.py`` is written by this tool."""

    return sorted(
        path for path in PROTO_PACKAGE.iterdir() if path.is_file() and path.name != "__init__.py"
    )


def _normalize_generated_package() -> None:
    generated = _generated_files()
    actual = {path.name for path in generated}
    if actual != EXPECTED_MODULES:
        missing = sorted(EXPECTED_MODULES - actual)
        extra = sorted(actual - EXPECTED_MODULES)
        raise SystemExit(f"unexpected generated modules; missing={missing}, extra={extra}")

    for path in generated:
        source = path.read_text(encoding="utf-8")
        rewritten = ABSOLUTE_IMPORT.sub(PACKAGE_IMPORT, source)
        if UNNORMALIZED_IMPORT.search(rewritten):
            raise SystemExit(f"{path.name} still imports from the unrewritten package minekin.v1")
        if rewritten != source:
            path.write_text(rewritten, encoding="utf-8", newline="\n")

    for package in (GENERATED_ROOT, GENERATED_ROOT / "minekin", PROTO_PACKAGE):
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text(PACKAGE_DOCSTRING, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--buf", help="path to the pinned Buf executable")
    args = parser.parse_args()
    subprocess.run(
        [_find_buf(args.buf), "generate"],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    _normalize_generated_package()
    print("Minekin Python protobuf generation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
