"""Identity reads show persisted tendencies, not seeds or a replacement persona."""

from __future__ import annotations

import json
from pathlib import Path

from gateway.identity import identity_read, saved_persona_read
from gateway_support import KIN_ID, seed_kin
from minekin_core.adapters.filestore.persona_store import persona_path, read_persona, write_persona
from minekin_core.application.ports.clock import FakeClock
from minekin_core.cli.init import kin_directory
from minekin_core.domain.persona import derive_persona


def test_identity_read_exposes_saved_context_without_seed_or_mutation(tmp_path: Path) -> None:
    seed_kin(tmp_path, with_marker=False)
    directory = kin_directory(tmp_path, KIN_ID)
    persona = read_persona(directory)
    path = persona_path(directory)
    before = path.read_bytes()
    first = identity_read(tmp_path, kin_selector=None, clock=FakeClock(), csrf_token="test")
    reread = identity_read(tmp_path, kin_selector=None, clock=FakeClock(), csrf_token="test")
    assert first["persona"] == reread["persona"] == {"value": persona.decision_context()}
    assert persona.persona_seed not in json.dumps(first)
    assert "persona_seed" not in json.dumps(first)
    assert path.read_bytes() == before


def test_missing_persona_does_not_create_it(tmp_path: Path) -> None:
    missing = tmp_path / "old-kin"
    packet = saved_persona_read(missing, "old-kin")
    assert "PERSONA_NOT_INITIALISED" in packet["gap"]["reason"]
    assert not missing.exists()


def test_foreign_or_corrupt_persona_is_named_and_never_echoed(tmp_path: Path) -> None:
    path = write_persona(tmp_path, derive_persona("other-kin", "seed"))
    assert "PERSONA_KIN_MISMATCH" in saved_persona_read(tmp_path, "current-kin")["gap"]["reason"]
    path.write_text('{"secret":"sensitive-canary"', encoding="utf-8")
    before = path.read_bytes()
    packet = saved_persona_read(tmp_path, "current-kin")
    assert "PERSONA_UNREADABLE" in packet["gap"]["reason"]
    assert "sensitive-canary" not in json.dumps(packet)
    assert path.read_bytes() == before
    assert persona_path(tmp_path) == path
