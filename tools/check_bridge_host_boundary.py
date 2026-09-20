"""Fail the build when the Bridge's client core reaches for the server.

The host boundary contract splits the Bridge into a client core and a narrow
host-control adapter, and gives the reason: the integrated server runs in this same
JVM, so the only thing between a Kin's perception and the server's own truth is
which types the code is allowed to name. A rule that lives only in a document is a
rule that holds until it is inconvenient; this is the same rule as a gate.

Two tiers, because the two modules are not asking for the same thing:

- `DENIED_ALWAYS` — what is *in* the world (worlds, entities, players, chunks,
  inventories), the save files, and the reflection escapes that would turn any of
  those rules into a formality. Forbidden everywhere, adapter included: an adapter
  that can read a player's inventory is a second road for server truth into the
  product, which is the thing the boundary exists to prevent.
- `DENIED_OUTSIDE_HOST` — the door to the server and the server type itself.
  Opening a world to LAN is a lifecycle call and the contract gives the adapter
  that job; any other file naming `IntegratedServer` or calling `getServer()` is
  reaching past the boundary, and that is what this catches.

Wildcard imports of the server package are refused even inside the adapter: the
contract asks for a precise allowlist rather than the whole package, and "which
types does this actually need" is a question a wildcard never has to answer.

Only production sources are scanned (`bridge/src/main/java`). Test probes *are*
allowed to touch server state — that is how the black-box canary gate checks that
nothing else does — and keeping them out of the shipped artifact is the build
gate's job, not this one's.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SOURCES = REPOSITORY_ROOT / "bridge" / "src" / "main" / "java"

#: The package the contract allows to hold the lifecycle adapter. Nothing else may
#: name the server. Written as a package rather than a path because that is what a
#: file declares and what the allowance is keyed on.
HOST_PACKAGE = "org.minekin.bridge.host"

#: Forbidden in every file, with the reason each one is on the list.
DENIED_ALWAYS: dict[str, str] = {
    "ServerWorld": "a server world is what is in the world, not what happened to the client",
    "ServerLevel": "a server level is what is in the world, not what happened to the client",
    "ServerPlayerEntity": "server-side player state is the oracle's truth, not the Kin's",
    "PlayerManager": "the player list is server truth the Kin cannot see",
    "ServerChunkManager": "chunk state behind the client's view is hidden truth",
    "ServerEntityManager": "entities the client cannot see are hidden truth",
    "NbtIo": "reading save files is reading the world from behind the client",
    "LevelStorage": "the save's own storage is not something the client may open",
    "java.lang.reflect": "reflection makes every rule above a formality",
    "java.lang.invoke.MethodHandles": "method handles make every rule above a formality",
    "Class.forName": "looking a class up by name is reflection with a string",
    "setAccessible": "opening a member for access is how reflection gets around this list",
    "sun.misc.Unsafe": "unsafe access makes every rule above a formality",
}

#: Forbidden everywhere except the host adapter.
DENIED_OUTSIDE_HOST: dict[str, str] = {
    "getServer()": "the door to the integrated server belongs to the lifecycle adapter",
    "MinecraftServer": "the server type belongs to the lifecycle adapter",
    "IntegratedServer": "the integrated server type belongs to the lifecycle adapter",
    "net.minecraft.server.": "the server package belongs to the lifecycle adapter, by allowlist",
}

#: Refused in every file, adapter included: a precise allowlist is not a wildcard.
WILDCARD_SERVER_IMPORT = re.compile(
    r"^\s*import\s+(static\s+)?net\.minecraft\.server\.[\w.]*\*\s*;"
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
                if marker in line:
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
