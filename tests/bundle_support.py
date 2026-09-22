"""Sealing a bundle in a test, once, and building the timeline it holds.

Three test modules had grown their own `manifest()` and their own way of writing one
into a temporary directory, and the replay CLI adds a fourth and a fifth: the same
bundle now has to be readable from the product CLI and from the standalone tool, so
the same fixture gets built in two places by design. Building it here keeps those two
about what they check rather than about the manifest's twenty fields — and keeps the
address, which is the one thing a bundle's own rules turn on, spelled once.

`seal_bundle` writes the address a run id alone produces, because that is what
`verify_addressed_bundle` holds a manifest to: a bundle whose directory name is not
the run it names is one that does not hold up, whatever it contains.

The timelines built here are the two dialects that exist, kept apart on purpose. A
`walk` is what a ledger writes once it records transitions: a real SQLite-shaped row
whose authenticated payload states the move `from`/`to`. `fixture_dialect` is the W00
fixture's shape — the state in the payload and no move stated — and it is built here so
a test can prove that a *bundle* holding it projects nothing rather than being read as
a ledger.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from minekin_core.adapters.evidence.bundle import (
    DIGEST_NAME,
    MANIFEST_NAME,
    unseal_bundle,
    write_bundle,
)
from minekin_core.application.ports.event_store import JsonValue, canonical_json, payload_digest
from minekin_core.domain.evidence import Assertions, EvidenceManifest, EvidenceResult

#: A run id in the shape `RunId` produces. It is the directory name too, which is the
#: attribution rule rather than a coincidence.
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"
DIGEST = "a" * 64


def ledger_row(*, event_type: str, payload: JsonValue, **fields: object) -> bytes:
    """One line in the SQLite-row shape that `timeline_bytes` seals."""

    row = {
        "event_type": event_type,
        "payload_json": canonical_json(payload),
        "payload_hash": payload_digest(payload),
        **fields,
    }
    return (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")


def raw_payload_row(
    payload_json: str,
    *,
    event_type: str = "SessionStateTransitioned",
    payload_hash: str = "0" * 64,
) -> bytes:
    """A real-shape ledger row whose payload text is intentionally not normalised."""

    return (
        json.dumps(
            {
                "event_type": event_type,
                "payload_json": payload_json,
                "payload_hash": payload_hash,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def transition_row(source: str, target: str, **fields: object) -> bytes:
    """One ledger row whose authenticated payload states the recorded move."""

    return ledger_row(
        event_type="SessionStateTransitioned",
        payload={"from": source, "to": target},
        **fields,
    )


def walk(*states: str) -> bytes:
    """A timeline that walks the session through these states, one row per step.

    `walk("STOPPED", "PREPARING", "STARTING_CLIENT")` is two recorded moves and no
    ordinary events between them.
    """

    return b"".join(transition_row(source, target) for source, target in itertools.pairwise(states))


def fixture_dialect(*names: str) -> bytes:
    """The frozen fixture's own shape: the state in the payload and no move stated.

    Its event type is built from the state the way the fixture's is — a `PREPARING`
    row is a `SessionPreparing` — so what this proves is about the *shape* of the
    record rather than about a name no test would recognise.
    """

    return b"".join(
        ledger_row(
            event_type="Session" + "".join(part.title() for part in name.split("_")),
            payload={"state": name},
        )
        for name in names
    )


def manifest(run_id: str = RUN_ID) -> EvidenceManifest:
    """A manifest that is sealable as it stands: no violation, and one real world."""

    return EvidenceManifest(
        test_run_id=run_id,
        case_id="P0-CORE-001",
        case_version="b" * 64,
        result=EvidenceResult.PASS,
        launch_plan_digest=DIGEST,
        bridge_digest="c" * 64,
        protocol_schema_digest="d" * 64,
        server_config_digest="e" * 64,
        minecraft="1.21.4",
        loader="0.16.9",
        fabric_api="0.119.4+1.21.4",
        assertions=Assertions(expected=("join_seen",), observed=("join_seen",), failures=()),
        server_jar_sha1="4707d00eb834b446575d89a61a11b5d548d8c001",
        os_kernel="Linux 6.8",
        java_runtime="Temurin 21.0.12.1",
        cpu_memory="8 vCPU / 16 GiB",
        renderer_display="llvmpipe / Xvfb",
        world_kind="dedicated",
        seed_or_snapshot_id="snapshot-01",
        configured_profile="kin-01/profile-r1",
        server_observed_name_uuid="Kin/8f40376b",
    )


def seal_bundle(
    root: Path,
    artifacts: Mapping[str, bytes],
    *,
    run_id: str = RUN_ID,
    seal: bool = False,
) -> Path:
    """Seal one bundle under `root`, at the address a run id alone produces.

    Unsealed by default: a read-only tree is the sealer's business and is checked where
    that is the claim, while most tests need to tamper with what they just wrote.
    """

    directory = root / "run" / "evidence" / run_id
    write_bundle(directory, manifest(run_id), dict(artifacts), seal=seal)
    return directory


def declare_artifact_size(directory: Path, name: str, size: int) -> None:
    """Re-address a sealed bundle with a different declared size for one artifact.

    The new manifest is hashed into `bundle.sha256` like any other, so the bundle holds
    up against itself: identical bytes cannot differ in length, which is why the
    whole-bundle pass is right to treat an artifact's digest as subsuming its recorded
    size. A disagreement here is therefore invisible to that pass and visible only to a
    reader that holds the timeline to both fields of its own record.
    """

    document = cast(dict[str, object], json.loads((directory / MANIFEST_NAME).read_bytes()))
    records = cast(list[dict[str, object]], document["artifacts"])
    for record in records:
        if record["path"] == name:
            record["size"] = size
    manifest_bytes = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    (directory / MANIFEST_NAME).write_bytes(manifest_bytes)
    (directory / DIGEST_NAME).write_text(
        f"{hashlib.sha256(manifest_bytes).hexdigest()}\n", encoding="ascii"
    )


def unseal_all(root: Path) -> None:
    """Undo every seal under a temporary directory, so cleanup can remove it."""

    for found in sorted(root.rglob(MANIFEST_NAME)):
        unseal_bundle(found.parent)
