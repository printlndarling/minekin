"""The CI gates must run tools whose versions this repository pins.

A gate that runs "whatever is newest" can turn red — or, worse, keep passing
while checking something different — without any change to this repository. Each
tool the workflow installs is therefore asserted to be pinned by version, in the
same spirit as the dependency locks and fixture digests.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from minekin_core.adapters.sqlite.connection import supports_multi_connection_wal

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"

# Tools the workflow installs itself and must therefore pin.
PINNED_ACTIONS = ("bufbuild/buf-action@",)


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def step_block(uses_prefix: str) -> list[str]:
    """The lines of the step that references `uses_prefix`, up to the next step."""

    lines = workflow_text().splitlines()
    for index, line in enumerate(lines):
        if uses_prefix in line:
            block: list[str] = []
            for following in lines[index + 1 :]:
                if following.strip().startswith("- ") or following.strip().startswith("- uses"):
                    break
                block.append(following)
            return block
    raise AssertionError(f"{uses_prefix} is not referenced in {WORKFLOW.name}")


def job_block(name: str) -> list[str]:
    """The lines of one job, from its key to the next job at the same level."""

    lines = workflow_text().splitlines()
    marker = f"  {name}:"
    for index, line in enumerate(lines):
        if line.rstrip() != marker:
            continue
        block: list[str] = []
        for following in lines[index + 1 :]:
            if following.startswith("  ") and not following.startswith("   "):
                break
            block.append(following)
        return block
    raise AssertionError(f"the {name} job is not in {WORKFLOW.name}")


def test_every_installed_action_pins_the_version_it_installs() -> None:
    """The `uses:` reference is pinned by tag; that does not pin what it downloads."""

    for prefix in PINNED_ACTIONS:
        block = step_block(prefix)

        assert any(line.strip().startswith("version:") for line in block), (
            f"{prefix} does not pin the version of the tool it installs; "
            "an unpinned tool can change this gate's behaviour on its own schedule"
        )


def test_every_installed_action_verifies_the_download() -> None:
    """A version names what to fetch; a digest is what proves it arrived intact."""

    for prefix in PINNED_ACTIONS:
        block = step_block(prefix)

        checksums = [
            line.strip().removeprefix("checksum:").strip()
            for line in block
            if line.strip().startswith("checksum:")
        ]
        assert len(checksums) == 1, f"{prefix} must supply exactly one checksum"
        assert len(checksums[0]) == 64, f"{prefix} checksum is not a sha256: {checksums[0]!r}"
        assert all(character in "0123456789abcdef" for character in checksums[0]), checksums[0]


def test_the_buf_cli_version_is_the_reviewed_one() -> None:
    """Lint and format rules move between releases, and their output is a gate.

    The bare version is the reviewed one, and the missing `v` is the part of this
    that was measured: the action builds its download URL as
    `.../download/v${version}/...`, so `v1.50.0` asks GitHub for a release named
    `vv1.50.0` and the job dies on a 404 before `buf` runs at all.
    """

    pinned = [line.strip() for line in step_block("bufbuild/buf-action@") if "version:" in line]

    assert pinned == ["version: 1.50.0"], pinned
    assert not pinned[0].removeprefix("version:").strip().startswith("v"), (
        "the buf action prefixes the version with `v` itself; a `v` here is a "
        "request for a release whose name has two of them"
    )


def test_the_interpreter_that_runs_the_tests_is_a_pinned_one() -> None:
    """Its SQLite is the reason, so the interpreter is pinned like any other tool.

    `connect_writer` refuses a runtime outside the validated multi-connection WAL
    safety set. A distribution's `python3` links the distribution's SQLite, which is
    outside that set, so a gate that runs under it fails — on the runner, for a
    reason no commit chose. uv's managed builds carry their own SQLite, which is
    inside the set, and that is the interpreter the venv is made from here.
    """

    env = [line.strip() for line in job_block("python") if line.strip().startswith("UV_PYTHON")]

    assert env == ["UV_PYTHON_PREFERENCE: only-managed", 'UV_PYTHON: "3.12"'], env


def test_the_interpreter_running_these_tests_is_one_the_ledger_accepts() -> None:
    """The same rule, applied to whoever is running them right now.

    Worth stating separately from the workflow: the constraint is about the SQLite
    inside the interpreter, so someone whose `uv sync` picked a system Python should
    find out here, in one line, rather than from a screen of storage failures that
    each look like a different bug.
    """

    assert supports_multi_connection_wal(sqlite3.sqlite_version_info), (
        f"SQLite {sqlite3.sqlite_version} is outside the validated WAL safety set; "
        "run the tests on an interpreter whose SQLite is in it, which is what a "
        "managed one carries"
    )
