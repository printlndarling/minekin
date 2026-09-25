"""Ask whether a `tested` registry entry is backed by the artifacts it names.

The reviewed bundle registry is a document, and loading it proves one thing: that
the document agrees with itself. Every digest in it — the recipe's, the launch
plan's, the Bridge jar's, each sealed evidence bundle's — is a claim until someone
hashes the bytes it stands for. Nothing in the repository did that for the
document as a whole: `require_reviewed_plan` re-hashes a recipe and rebuilds a
plan for the one entry a launch is already committed to, and
`tools/report_promotion.py` re-reads bundles for the cases a gate lists. Both are
right where they stand. Neither answers the question this one asks, which is
"could an operator trust the word `tested` in this file without opening it by
hand?".

So this reads the registry, measures the machine, and reports where the two
disagree:

- the recipe file the entry cites, hashed by the rule the fixture manifest uses;
- the Bridge jar of the version that recipe names, hashed from the bytes that are
  there now, together with the digest of its source tree;
- the launch plan this checkout builds from that recipe;
- every evidence bundle the entry cites, re-verified against its own manifest in
  the data root, by run id.

A missing artifact is a refusal with the path in it, not a silent pass, and so is
an unmeasured one: the question is "did someone hash the real thing", and "nobody
did" is not a yes.

**This command writes nothing.** It prints one JSON document on stdout and exits
0 (verified), 1 (refused) or 2 (the reading was impossible). The `tested` status
belongs to a human review and to the commit that records it — an entry point that
could raise its own certificates would make this check the thing it checks. The
registry, the sealed recipes and the sealed bundles are inputs here and are opened
read-only; the same is true of the bundles' mode bits, which are reported and
never refused, because the digest the registry cites is the guarantee and the mode
is a courtesy (`tools/report_promotion.py` takes the same position).

What this cannot see, and says in its own document, is a bundle that is genuine
evidence for the wrong claim: verifying bytes proves they did not move, not that
they support the verdict written over them. Re-judging a verdict from the run
material is `tools/rejudge_evidence.py`'s job, and the promotion report is where
the two readings are required to agree.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.evidence.bundle import verify_addressed_bundle
from minekin_core.adapters.launcher.launch_plan import build_launch_plan

# The recipe digest is defined by the gate that enforces it, and the rule for
# checking out text on two platforms is spelled nowhere else. Restating it here
# would give one question two answers, which is the mistake this command exists to
# catch in other people's documents.
from minekin_core.adapters.launcher.provision import (
    _reviewed_digest,  # pyright: ignore[reportPrivateUsage]
)
from minekin_core.adapters.launcher.recipe import measure_bridge
from minekin_core.cli.evidence import candidate_roots
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.version_resolution import (
    BridgeMeasurement,
    CitationMeasurement,
    EntryMeasurements,
    RegistryEntry,
    load_reviewed_registry,
    verify_registry_provenance,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "registry" / "reviewed-tested-bundles.json"
)

EXIT_VERIFIED = 0
EXIT_REFUSED = 1
EXIT_UNUSABLE = 2


class Unusable(Exception):
    """The reading could not be taken at all, which is not the same as a refusal."""


def bundle_directories(data_root: Path) -> dict[str, Path]:
    """Every sealed bundle under the data root, keyed by the run id that names it.

    One run id names one bundle, so the same name under two roots is refused rather
    than chosen between — picking a root by walk order would attribute one run's
    evidence to another, which is the failure `report_promotion.py` also refuses.
    """

    found: dict[str, Path] = {}
    for root in candidate_roots(data_root):
        if not root.is_dir():
            continue
        for directory in sorted(path for path in root.iterdir() if path.is_dir()):
            known = found.get(directory.name)
            if known is not None and known != directory:
                raise Unusable(
                    f"{directory.name} has bundles in {known} and {directory}; a run id names "
                    "one bundle, so no provenance can be read from this root"
                )
            found.setdefault(directory.name, directory)
    return found


def _recipe_document(path: Path) -> dict[str, Any] | None:
    """The recipe as an object, or None when it cannot be read as one.

    Read tolerantly on purpose: the strict reading is `validate_bundle_recipe`'s,
    reached through the plan below, and an audit that stops at the first unreadable
    file reports one gap where the machine holds several.
    """

    try:
        document = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    return cast(dict[str, Any], document)


def _recipe_bridge_digest(recipe: Mapping[str, object]) -> str | None:
    """The source digest the recipe seals for its own Bridge artifact."""

    raw_artifacts = recipe.get("artifacts")
    if not isinstance(raw_artifacts, list):
        return None
    for value in cast(list[object], raw_artifacts):
        if not isinstance(value, Mapping):
            continue
        artifact = cast(Mapping[str, object], value)
        if artifact.get("kind") != "bridge":
            continue
        digest = artifact.get("source_digest")
        return digest if isinstance(digest, str) else None
    return None


def _recipe_version(recipe: Mapping[str, object]) -> str | None:
    """The Minecraft version the recipe itself says it builds.

    Taken from the recipe rather than from the entry's `version_text`, because the
    entry's text is what a target announced and this command is checking the entry:
    the version that decides which Bridge root to hash has to come from the bytes
    the entry cites.
    """

    raw = recipe.get("minecraft")
    if not isinstance(raw, Mapping):
        return None
    version = cast(Mapping[str, object], raw).get("version")
    return version if isinstance(version, str) else None


def _citation(run_id: str, bundles: Mapping[str, Path]) -> CitationMeasurement:
    """One cited bundle, re-read from the root that holds it."""

    directory = bundles.get(run_id)
    if directory is None:
        return CitationMeasurement(
            run_id=run_id,
            present=False,
            readable=False,
            sealed=False,
            consistent=False,
            bundle_digest=None,
            detail=f"no bundle directory is named {run_id} under the evidence roots",
        )
    try:
        verification = verify_addressed_bundle(directory)
    except MinekinError as error:
        return CitationMeasurement(
            run_id=run_id,
            present=True,
            readable=False,
            sealed=False,
            consistent=False,
            bundle_digest=None,
            detail=f"{directory}: {error.safe_message}",
        )
    manifest = verification.manifest
    return CitationMeasurement(
        run_id=run_id,
        present=True,
        readable=True,
        sealed=verification.sealed,
        consistent=verification.verified,
        bundle_digest=verification.bundle_digest,
        case_id=None if manifest is None else manifest.case_id,
        result=None if manifest is None else manifest.result.value,
        bridge_digest=None if manifest is None else manifest.bridge_digest,
        launch_plan_digest=None if manifest is None else manifest.launch_plan_digest,
        detail=None
        if verification.verified
        else f"{directory}: {', '.join(verification.violations)}",
    )


def measure_entry(
    entry: RegistryEntry, *, workspace_root: Path, bundles: Mapping[str, Path]
) -> EntryMeasurements:
    """Everything this host can measure about one registry entry.

    Nothing here compares anything to anything: the readings are handed to
    `verify_entry_provenance`, which is where a gap becomes a named refusal. A
    measurement that could not be taken stays None rather than becoming the
    expectation, because reporting the pin as the reading is how a check that
    measures nothing comes to look like one that measured everything.
    """

    recipe_path = workspace_root / entry.recipe_path
    recipe_digest: str | None = None
    detail: str | None = None
    try:
        recipe_digest = _reviewed_digest(recipe_path)
    except OSError as error:
        detail = f"recipe {entry.recipe_path} is not readable: {type(error).__name__}"
    recipe = _recipe_document(recipe_path)

    version = _recipe_version(recipe) if recipe is not None else None
    bridge = None
    if version is None:
        detail = detail or f"recipe {entry.recipe_path} does not name a Minecraft version"
    else:
        try:
            readings = measure_bridge(workspace_root, version)
        except MinekinError as error:
            # A version nothing pins is not a measurement of a Bridge, and the
            # refusal belongs in the report rather than in a stack trace.
            detail = detail or error.safe_message
        else:
            bridge = BridgeMeasurement(
                source_root=readings.source_root,
                jar_path=readings.jar_path,
                jar_sha256=readings.jar_sha256,
                jar_size=readings.jar_size,
                source_digest=readings.source_digest,
                detail=readings.detail,
                source_detail=readings.source_detail,
            )

    plan_sha256 = None
    try:
        plan = build_launch_plan(recipe_path.resolve(), workspace_root=workspace_root)
    except (MinekinError, OSError) as error:
        detail = detail or (error.safe_message if isinstance(error, MinekinError) else str(error))
    else:
        value = plan.get("plan_sha256")
        plan_sha256 = value if isinstance(value, str) else None

    return EntryMeasurements(
        recipe_digest=recipe_digest,
        recipe_source_digest=None if recipe is None else _recipe_bridge_digest(recipe),
        plan_sha256=plan_sha256,
        bridge=bridge,
        citations=tuple(_citation(ref.run_id, bundles) for ref in entry.evidence),
        detail=detail,
    )


def report(*, registry_path: Path, data_root: Path, workspace_root: Path) -> dict[str, object]:
    """The provenance of every `tested` entry in one registry document."""

    try:
        document = json.loads(registry_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Unusable(
            f"{registry_path} is not readable UTF-8 JSON: {type(error).__name__}"
        ) from error
    registry = load_reviewed_registry(document)
    bundles = bundle_directories(data_root)
    measurements = {
        entry.bundle_id: measure_entry(entry, workspace_root=workspace_root, bundles=bundles)
        for entry in registry.entries
    }
    return verify_registry_provenance(registry, measurements).as_document()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a reviewed `tested` registry against the artifacts it cites."
    )
    parser.add_argument(
        "--registry", type=Path, default=DEFAULT_REGISTRY, help="the reviewed registry to read"
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="the data root holding the sealed evidence bundles",
    )
    parser.add_argument(
        "--workspace-root", type=Path, default=REPOSITORY_ROOT, help="the checkout to measure"
    )
    args = parser.parse_args(argv)

    try:
        document = report(
            registry_path=args.registry,
            data_root=args.data_root,
            workspace_root=args.workspace_root,
        )
    except (Unusable, MinekinError) as error:
        reason = error.safe_message if isinstance(error, MinekinError) else str(error)
        print(json.dumps({"kind": "unusable", "message": reason}, sort_keys=True), file=sys.stderr)
        return EXIT_UNUSABLE

    print(json.dumps(document, indent=2, sort_keys=True))
    return EXIT_VERIFIED if document["verified"] else EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
