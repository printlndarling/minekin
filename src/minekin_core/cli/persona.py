"""Reading one Kin's persona, with no way to change it from here.

The persona answers a question the operator asks about a live Kin — "which person
did this one get, and how was it decided" — so the read is its own command rather
than a field of `identity show`, whose shape is the stored player name and UUID. A
Kin created before personas existed is not shown an invented one: the store names
that case and this command lets it through.
"""

from __future__ import annotations

from pathlib import Path

from minekin_core.adapters.filestore.persona_store import persona_path, read_persona
from minekin_core.cli.init import kin_directory
from minekin_core.domain.ids import KinId
from minekin_core.domain.persona import describe_for_backend


def persona_report(root: Path, kin_id: KinId) -> dict[str, object]:
    """The persisted manifest for one Kin, or the named reason there is none."""

    directory = kin_directory(root, kin_id)
    manifest = read_persona(directory)
    return {
        "schema_version": 1,
        "command": "persona show",
        "status": "ok",
        "kin_id": str(kin_id),
        "persona_file": str(persona_path(directory)),
        "persona": describe_for_backend(manifest),
    }
