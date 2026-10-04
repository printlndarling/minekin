"""A synthetic reviewed entry that vouches for the fixture this checkout carries.

The shipped `reviewed-tested-bundles.json` is historical on purpose: each entry cites
runs sealed on the exact build it names, so rebuilding the Bridge moves the candidate
fixture without moving the registry. Composition tests that need a registry vouching
for today's fixture — the ordering, budgets and refusals *behind* the digest gate —
derive one here instead of editing the shipped file. Nothing in this module is
evidence about a real run, and nothing here may be written back to the registry: the
real one moves only when a candidate build has been run, sealed and re-judged.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.adapters.launcher.provision import (
    _plan_bridge_digest,  # pyright: ignore[reportPrivateUsage]
    _reviewed_digest,  # pyright: ignore[reportPrivateUsage]
)
from minekin_core.domain.version_resolution import RegistryEntry, load_reviewed_registry

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def current_candidate_entry(entry: RegistryEntry, *, root: Path = REPOSITORY_ROOT) -> RegistryEntry:
    """The entry's build identity re-derived from the fixture on disk.

    The citations (`evidence`, `capabilities`, `gaps`) are carried across untouched:
    what changes is only what the entry claims about *these bytes*, so a test cannot
    be passing because the entry is stale.
    """

    recipe = root / entry.recipe_path
    plan = build_launch_plan(recipe)
    bridge = _plan_bridge_digest(plan)
    if bridge is None:
        raise AssertionError(f"{entry.recipe_path} names no bridge artifact")
    return replace(
        entry,
        recipe_digest=_reviewed_digest(recipe),
        launch_plan_digest=cast(str, plan["plan_sha256"]),
        bridge_digest=bridge,
    )


def current_candidate_registry_document(
    document: object, *, root: Path = REPOSITORY_ROOT
) -> dict[str, Any]:
    """The registry document with every entry's build identity re-derived.

    Built by loading through the shipped parser, so an entry this helper cannot read
    is the same refusal the product makes; the raw fields it does not own are left
    exactly as they were read. Each citation is re-attributed to the re-derived
    identity because the loader refuses a citation naming another build (an older
    sealed run is evidence about *that* build) — the re-attribution is what makes
    this a synthetic fixture, and it is not a claim that those runs sealed these
    bytes.
    """

    if not isinstance(document, dict):
        raise AssertionError("the registry document is not an object")
    copied = cast(dict[str, Any], json.loads(json.dumps(document)))
    registry = load_reviewed_registry(copied)
    by_id = registry.by_id()
    raw_entries = copied.get("entries")
    if not isinstance(raw_entries, list):
        raise AssertionError("the registry document names no entries")
    for raw in cast(list[object], raw_entries):
        if not isinstance(raw, dict):
            raise AssertionError("a registry entry is not an object")
        item = cast(dict[str, Any], raw)
        bundle_id = item.get("bundle_id")
        if not isinstance(bundle_id, str) or bundle_id not in by_id:
            raise AssertionError("a registry entry names no loadable bundle")
        current = current_candidate_entry(by_id[bundle_id], root=root)
        item["recipe_digest"] = current.recipe_digest
        item["launch_plan_digest"] = current.launch_plan_digest
        item["bridge_digest"] = current.bridge_digest
        raw_evidence = item.get("evidence")
        if isinstance(raw_evidence, list):
            for raw_ref in cast(list[object], raw_evidence):
                if not isinstance(raw_ref, dict):
                    raise AssertionError("a registry citation is not an object")
                ref = cast(dict[str, Any], raw_ref)
                ref["bridge_digest"] = current.bridge_digest
                ref["launch_plan_digest"] = current.launch_plan_digest
    return copied


def current_candidate_registry(
    registry_path: Path, destination: Path, *, root: Path = REPOSITORY_ROOT
) -> Path:
    """Write `current_candidate_registry_document` next to a test, and return the path."""

    document = json.loads(registry_path.read_bytes())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(current_candidate_registry_document(document, root=root), indent=2) + "\n",
        encoding="utf-8",
    )
    return destination
