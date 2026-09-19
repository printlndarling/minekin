"""The documented data-root layout and the one the code builds must agree.

`docs/run-directory-proposal.md` is what a reader consults before writing a
bundle or looking for one, and the layout block in it is the only written form
of that convention. A convention written down in one place and implemented in
another drifts silently, so the two are checked against each other here — the
same way the Bridge's Java constants are checked against the recipe that pins
them.

Only the evidence child is checked: it is the part `evidence verify` addresses
by name, and the part added last.
"""

from __future__ import annotations

import re
from pathlib import Path

from minekin_core.cli.evidence import EVIDENCE_DIRECTORY
from minekin_core.cli.init import KIN_DIRECTORY, RUN_DIRECTORY

PROPOSAL = Path(__file__).resolve().parents[2] / "docs" / "run-directory-proposal.md"


def _layout_block(text: str) -> str:
    """The fenced block that draws the data root, and no other block."""

    for block in re.findall(r"```\n(.*?)```", text, flags=re.DOTALL):
        if f"{KIN_DIRECTORY}/" in block and f"{RUN_DIRECTORY}/" in block:
            return block
    raise AssertionError(f"{PROPOSAL} no longer draws the data root layout")


def _children(block: str, parent: str) -> dict[str, int]:
    """Every entry indented under `parent`, as name -> indentation."""

    lines = block.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(f"{parent}/"):
            continue
        indent = len(line) - len(line.lstrip())
        found: dict[str, int] = {}
        for child in lines[index + 1 :]:
            if not child.strip():
                continue
            child_indent = len(child) - len(child.lstrip())
            if child_indent <= indent:
                break
            if child_indent == indent + 2:
                found[child.strip().split()[0].rstrip("/")] = child_indent
        return found
    raise AssertionError(f"the layout block no longer lists {parent}/")


def test_the_evidence_directory_is_a_sibling_of_the_other_run_root_children() -> None:
    """It sits in `run/`, not inside a session overlay, which is writable."""

    children = _children(_layout_block(PROPOSAL.read_text(encoding="utf-8")), RUN_DIRECTORY)

    assert EVIDENCE_DIRECTORY in children
    assert children[EVIDENCE_DIRECTORY] == children["session"]


def test_the_documented_kin_directory_is_the_one_the_code_names() -> None:
    block = _layout_block(PROPOSAL.read_text(encoding="utf-8"))

    assert f"{KIN_DIRECTORY}/" in block
    assert EVIDENCE_DIRECTORY == "evidence"
