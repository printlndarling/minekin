"""What was checked, and where the check ran.

Two things a sealed bundle claims must not be computed in two places, because a
disagreement between them is a disagreement between two bundles that are supposed
to be comparable. The provenance of the bundle under test — the plan digest, the
version identity, the protocol schema, the profile reference — is one of them.
The host the check ran on — kernel, JVM, memory, display — is the other.

Both kinds of case need both: a run of the client and a check of the repository
are sealed into the same manifest shape, and the fields they fill with the same
values are these. Everything else about them differs, which is why only this much
is shared.

Nothing here starts anything. The JVM is asked its version, the kernel is asked
what it is, and the workspace is hashed — all read-only.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from minekin_core.adapters.launcher.recipe import source_tree_sha256


@dataclass(frozen=True, slots=True)
class HostFacts:
    """What the host was, as the manifest's environment section reports it."""

    os_kernel: str
    java_runtime: str
    cpu_memory: str
    renderer_display: str


def _first_lines(text: str, count: int = 2) -> str:
    """The vendor's own words about its runtime, joined and bounded."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " / ".join(lines[:count])


def java_runtime(java: Path | None) -> str:
    """Which JVM ran, read from that JVM rather than assumed."""

    executable = java or shutil.which("java")
    if executable is None:
        return "unmeasured"
    try:
        completed = subprocess.run(
            [str(executable), "-version"], capture_output=True, text=True, check=False
        )
    except OSError as error:
        return f"unmeasurable ({type(error).__name__})"
    # `java -version` writes to stderr, and has done since before anyone expected
    # otherwise. Both streams are read so the answer does not depend on the JDK.
    return _first_lines(f"{completed.stdout}\n{completed.stderr}") or "unmeasured"


def cpu_memory() -> str:
    """Processors and RAM, from the kernel's own accounting where it exists."""

    processors = os.cpu_count() or 0
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return f"{processors} vCPU / memory unmeasured"
    match = re.search(r"^MemTotal:\s+(\d+) kB$", meminfo.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        return f"{processors} vCPU / memory unmeasured"
    gib = int(match.group(1)) / (1024 * 1024)
    return f"{processors} vCPU / {gib:.1f} GiB"


def host_facts(java: Path | None, renderer_display: str) -> HostFacts:
    return HostFacts(
        os_kernel=f"{platform.system()} {platform.release()}",
        java_runtime=java_runtime(java),
        cpu_memory=cpu_memory(),
        renderer_display=renderer_display,
    )


def protocol_schema_digest(workspace_root: Path) -> str:
    """The reviewed protocol schema, as one digest.

    `proto/` is the schema; the generated code is downstream of it. The digest is
    the recipe's own tree rule rather than a second one, so "a tree digest" means
    one thing in this repository: paths and (CRLF-normalised) bytes in codepoint
    order, which is what makes it the same value on both platforms.
    """

    return source_tree_sha256(workspace_root / "proto")


def profile_reference(profile: Path) -> str:
    """A reference to a reviewed document that carries no path from this host.

    Named by its file name and the digest of its bytes: enough to say which
    document was used, and nothing about where the operator keeps it — a bundle
    is handed to other people.
    """

    digest = hashlib.sha256(profile.read_bytes()).hexdigest()
    return f"{profile.name}#{digest[:16]}"
