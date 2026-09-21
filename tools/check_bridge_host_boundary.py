"""Fail the build when the Bridge's client core reaches for the server.

A rule that lives only in a document is a rule that holds until it is inconvenient;
this is the same rule as a gate. It reads the sources, which is one of the two ways
that rule can be broken — the other one, what the compiler leaves behind, is
`check_bridge_artifacts.py`. The vocabulary both of them enforce lives in
`bridge_host_rules.py` so the two cannot drift apart.

This gate only looks at production sources (`bridge/src/main/java`). Test probes *are*
allowed to touch server state — that is how the black-box canary gate checks that
nothing else does — and keeping them out of the shipped artifact is the build gate's
job, not this one's.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SOURCES = REPOSITORY_ROOT / "bridge" / "src" / "main" / "java"

# The vocabulary lives beside this file, and this is one of the two gates that
# enforces it. One declaration, so the names a person is allowed to write and the
# names a compiler is allowed to leave behind cannot become two rules.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bridge_host_rules import (  # noqa: E402
    DENIED_ALWAYS,
    DENIED_OUTSIDE_HOST,
    HOST_PACKAGE,
    WILDCARD_SERVER_IMPORT,
    is_identifier,
)

_LINE_COMMENT = re.compile(r"//.*$")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)


def _declared_package(text: str) -> str:
    match = _PACKAGE.search(text)
    return match.group(1) if match else ""


def _directory_package(path: Path, sources: Path) -> str:
    return ".".join(path.relative_to(sources).with_suffix("").parts[:-1])


def _without_comments(text: str) -> str:
    """Drop comments before scanning, so prose about a type is not a use of it.

    The adapter's own javadoc has to be able to explain what it calls and why, and
    the contract's rules are worth quoting next to the code they govern. Blanking a
    comment keeps the line count, so the reported line numbers still point at the
    file as it is read. This is a gate and not a compiler: a `//` inside a string
    literal is treated as a comment, which can only ever lose a violation, and one
    hidden behind a URL is not the one worth catching.
    """

    def blank(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return "\n".join(
        _LINE_COMMENT.sub("", line) for line in _BLOCK_COMMENT.sub(blank, text).splitlines()
    )


def _names(line: str, marker: str) -> bool:
    """Whether this line *names* the marker, rather than merely containing it.

    Identifier markers are matched as identifiers (`is_identifier` says which those
    are); everything else is matched as it is.
    """

    if not is_identifier(marker):
        return marker in line
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(marker)}(?![A-Za-z0-9_])", line) is not None


def violations(sources: Path) -> list[str]:
    """Every denied reference, as `path:line: marker — the rule that denies it`.

    Which module a file belongs to is the *declared package*, not the directory it
    sits in. `javac` does not require the two to agree — move a file one directory
    over, leave its `package` line alone, and it still compiles into the package it
    names — so a gate that read only the path could be walked around by a file that
    declares the adapter's package while living somewhere else. Where they disagree
    the file is a violation in its own right, whichever way round it is.
    """

    found: list[str] = []
    for path in sorted(sources.rglob("*.java")):
        text = _without_comments(path.read_text(encoding="utf-8"))
        relative = path.relative_to(sources)
        declared = _declared_package(text)
        expected = _directory_package(path, sources)
        if declared and declared != expected:
            found.append(
                f"{relative}: declares package {declared} and sits in {expected} — a "
                "file whose package and directory disagree is how code gets past a "
                "rule that reads one of them"
            )
        host = (declared or expected) == HOST_PACKAGE
        for number, line in enumerate(text.splitlines(), start=1):
            if WILDCARD_SERVER_IMPORT.match(line):
                found.append(
                    f"{relative}:{number}: wildcard import of the server package — "
                    "the allowlist names types, so wildcards are refused even "
                    "inside the adapter"
                )
                continue
            denied = dict(DENIED_ALWAYS)
            if not host:
                denied.update(DENIED_OUTSIDE_HOST)
            for marker, reason in denied.items():
                if _names(line, marker):
                    found.append(f"{relative}:{number}: {marker} — {reason}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources-dir",
        type=Path,
        default=BRIDGE_SOURCES,
        help="the production Java sources to scan (default: the Bridge's)",
    )
    arguments = parser.parse_args(argv)
    sources = arguments.sources_dir
    if not sources.is_dir():
        print(f"bridge host boundary: {sources} is not a directory", file=sys.stderr)
        return 2
    found = violations(sources)
    if found:
        for line in found:
            print(line, file=sys.stderr)
        print(
            f"bridge host boundary: {len(found)} reference(s) to server state outside the adapter",
            file=sys.stderr,
        )
        return 1
    print("Bridge host boundary: OK (no server state outside the lifecycle adapter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
