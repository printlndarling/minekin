"""Keeping the verified server jar must not overwrite whatever is already there.

`--save-server` is the only step that turns a verified payload into a file on
disk, and the file it writes is the server a test domain will run. A different
file at that path is a partial download, another version, or somebody's own jar;
letting it be replaced by "the pinned server" is the one outcome that must not
happen quietly.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = b"the pinned server, as verified\n"


class _Tool(Protocol):
    def keep(self, payload: bytes, destination: Path) -> str: ...


def _load_tool() -> _Tool:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        module: ModuleType = importlib.import_module("tools.verify_supply_chain")
    finally:
        sys.path.pop(0)
    return cast(_Tool, module)


TOOL = _load_tool()


def test_the_payload_lands_where_it_was_asked_for(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "server.jar"

    assert TOOL.keep(PAYLOAD, destination) == "saved"

    assert destination.read_bytes() == PAYLOAD
    # No half-written name left behind for the next reader to find.
    assert list(tmp_path.rglob("*.staging")) == []


def test_saving_the_same_bytes_again_is_not_an_error(tmp_path: Path) -> None:
    destination = tmp_path / "server.jar"
    TOOL.keep(PAYLOAD, destination)
    before = destination.stat().st_mtime_ns

    assert TOOL.keep(PAYLOAD, destination) == "already present"

    assert destination.read_bytes() == PAYLOAD
    assert destination.stat().st_mtime_ns == before


def test_a_different_file_at_that_path_is_never_replaced(tmp_path: Path) -> None:
    destination = tmp_path / "server.jar"
    destination.write_bytes(b"somebody else's server")

    with pytest.raises(ValueError, match="refusing to replace"):
        TOOL.keep(PAYLOAD, destination)

    assert destination.read_bytes() == b"somebody else's server"
    assert list(tmp_path.rglob("*.staging")) == []
