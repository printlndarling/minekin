"""Every way the Bridge can let go has to be a way something actually takes.

A `ReleaseReason` that nothing produces is not a harmless spare: it means the
trigger it names arrives under a different name, so the log says the wrong thing
about why the keys came up. That has happened three times in this repository —
`GUI_CONFLICT` was declared and never produced, `IPC_LOST` was declared and
produced as `BRIDGE_FAULT`, and `LEFT_PLAYABLE` was declared and left to vanilla's
title screen to cover by accident. Each was found by reading a run's log, which
is a slow and unreliable way to find a missing call site.

So this is the cheap check that would have found all three: read the enum, and
require each constant to appear somewhere outside its own declaration.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "bridge" / "src" / "main" / "java"
ENUM_FILE = SOURCE_ROOT / "org" / "minekin" / "bridge" / "input" / "BridgeInputController.java"


def _release_reasons() -> list[str]:
    text = ENUM_FILE.read_text(encoding="utf-8")
    body = re.search(r"enum ReleaseReason \{(.*?)\n    \}", text, re.DOTALL)
    assert body is not None, "the release reasons are no longer where this expects them"
    found = re.findall(r"^\s*([A-Z][A-Z_]*),?$", body.group(1), re.MULTILINE)
    return [str(name) for name in found]


def _sources_without_the_declaration() -> list[str]:
    """Every Java source, with the enum's own body removed.

    The declaration is where a constant is *named*, not where it is used, and the
    controller that declares these reasons also produces several of them — so the
    whole file cannot be skipped, only the block that lists the names.
    """

    sources: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.java")):
        text = path.read_text(encoding="utf-8")
        if path == ENUM_FILE:
            text = re.sub(r"enum ReleaseReason \{.*?\n    \}", "", text, flags=re.DOTALL)
        sources.append(text)
    return sources


def test_the_enum_was_found_and_is_not_empty() -> None:
    reasons = _release_reasons()

    assert "IPC_LOST" in reasons and "GUI_CONFLICT" in reasons
    assert len(reasons) >= 5, reasons


@pytest.mark.parametrize("reason", _release_reasons())
def test_every_release_reason_is_produced_somewhere(reason: str) -> None:
    for source in _sources_without_the_declaration():
        if f"ReleaseReason.{reason}" in source:
            return
    pytest.fail(
        f"nothing produces ReleaseReason.{reason}: a release under this name can "
        "never be reported, so the trigger it documents arrives under another one"
    )
