"""Reading and writing one Kin's persona manifest file.

`PERSONA_NOT_INITIALISED` is a named reason rather than an empty default: the
backend shows the persona panel, and a Kin created before personas existed has to be
able to say which case the operator is looking at instead of rendering a person made
up by the reader.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.persona import PersonaManifest

PERSONA_FILE_NAME = "persona.json"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "adapters.filestore.persona",
        "store",
        ErrorCategory.STORAGE,
        Retryability.OPERATOR_ACTION,
        message,
    )


def persona_path(kin_dir: Path) -> Path:
    return kin_dir / PERSONA_FILE_NAME


def write_persona(kin_dir: Path, manifest: PersonaManifest) -> Path:
    """Store the manifest once. A second write is a different Kin, not an update."""

    path = persona_path(kin_dir)
    if path.exists():
        raise _reject(
            f"{path} already exists; a persona is not redrawn in place "
            "(PERSONA_ALREADY_INITIALISED)"
        )
    kin_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    # Written through a temporary name in the same directory so an interrupted write
    # leaves either the old file or the new one, never half a person.
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
    return path


def read_persona(kin_dir: Path) -> PersonaManifest:
    path = persona_path(kin_dir)
    if not path.exists():
        raise _reject(f"{path} does not exist (PERSONA_NOT_INITIALISED)")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise _reject(f"{path} is not readable JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise _reject(f"{path} must hold one object")
    return PersonaManifest.from_dict(cast("dict[str, object]", payload))
