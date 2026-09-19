"""Sealing the evidence of a check that belongs to the repository, not to a Kin.

A repository check never starts a client, so its bundle holds different things
from a run's: the verdict the case's declared checks produced, each check's whole
output, the case definition that declared them, and the fixture digest manifest
they were compared against. What it holds *in common* with a run's bundle is
everything that says which reviewed bundle was under test and where the check
ran — and that is computed by `evidence_provenance.py`, one implementation, so
the two kinds of bundle cannot disagree about it.

The world section says the same thing a run with no world says: `kind: "none"`
and the digest of nothing. A repository check has no server, no seed, no jar and
nobody observed its identity, and the contract has a way to record exactly that
rather than borrowing the closest word that fits.

The address is `repo-evidence/<run-id>/` beside `kin/`, because naming a Kin for
a check of the repository would be naming something the check has nothing to do
with. `evidence verify` searches both places by the same rule.

Exit codes: 0 sealed and held, 1 sealed and failed, 2 could not seal. A failing
check is still sealed: a run that failed keeps its evidence, and so does a
repository whose contracts do not hold.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from minekin_core.adapters.evidence.bundle import write_bundle
from minekin_core.adapters.evidence.promotion import load_case_manifest
from minekin_core.adapters.launcher.launch_plan import build_launch_plan, find_workspace_root
from minekin_core.adapters.launcher.recipe import BRIDGE_JAR_SHA256
from minekin_core.cli.evidence import repository_bundle_directory
from minekin_core.domain.evidence import (
    EMPTY_DOCUMENT_SHA256,
    NO_WORLD,
    Assertions,
    EvidenceManifest,
    EvidenceResult,
)
from minekin_core.domain.ids import RunId

# The tools directory, so the provenance module can be imported whether this is
# run as `python tools/seal_repo_case.py` or imported as `tools.seal_repo_case`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence_provenance import host_facts, profile_reference, protocol_schema_digest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

EXIT_HELD = 0
EXIT_FAILED = 1
EXIT_UNSEALED = 2

#: The reviewed fixture digests the digest check compares against, sealed with
#: the bundle so the comparison can be repeated from the bundle alone.
FIXTURE_MANIFEST = Path("tests") / "fixtures" / "manifest.sha256"

_RESULTS = {item.value for item in EvidenceResult}


class Unsealable(Exception):
    """The check cannot be sealed, and saying why is more useful than a traceback."""


@dataclass(frozen=True, slots=True)
class Verdict:
    """What the checks said, as the runner reported it."""

    run_id: str
    result: EvidenceResult
    assertions: Assertions
    checks: tuple[Mapping[str, object], ...]


def read_verdict(path: Path) -> Verdict:
    """Read the runner's verdict, refusing one that cannot be recorded."""

    try:
        document = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Unsealable(f"{path} is not readable verdict JSON: {error}") from error
    if not isinstance(document, dict):
        raise Unsealable(f"{path} is not a verdict object")
    verdict = cast(dict[str, object], document)

    run_id = verdict.get("run_id")
    try:
        identifier = RunId(str(run_id)).value
    except ValueError as error:
        raise Unsealable(f"the verdict names no check run: {run_id!r}") from error

    raw_result = verdict.get("result")
    if str(raw_result) not in _RESULTS:
        raise Unsealable(f"the verdict's result {raw_result!r} is not a known outcome")

    def strings(key: str) -> tuple[str, ...]:
        value = verdict.get(key)
        return (
            tuple(str(item) for item in cast(list[object], value))
            if isinstance(value, list)
            else ()
        )

    checks = verdict.get("checks")
    return Verdict(
        run_id=identifier,
        result=EvidenceResult(str(raw_result)),
        assertions=Assertions(
            expected=strings("expected"),
            observed=strings("observed"),
            failures=strings("failures"),
        ),
        checks=tuple(cast(list[Mapping[str, object]], checks) if isinstance(checks, list) else []),
    )


def build_manifest(
    *,
    case: Path,
    profile: Path,
    verdict: Verdict,
    workspace_root: Path,
    java: Path | None,
    renderer_display: str,
) -> EvidenceManifest:
    """The bundle's own account of which reviewed bundle was checked, and where."""

    definition = load_case_manifest(case)
    plan = build_launch_plan(profile, workspace_root=workspace_root)
    bundle = cast(Mapping[str, object], plan["bundle"])
    facts = host_facts(java, renderer_display)
    return EvidenceManifest(
        test_run_id=verdict.run_id,
        case_id=definition.case_id,
        case_version=definition.digest,
        result=verdict.result,
        launch_plan_digest=str(plan["plan_sha256"]),
        bridge_digest=BRIDGE_JAR_SHA256,
        protocol_schema_digest=protocol_schema_digest(workspace_root),
        server_config_digest=EMPTY_DOCUMENT_SHA256,
        minecraft=str(bundle["minecraft"]),
        loader=str(bundle["fabric_loader"]),
        fabric_api=str(bundle["fabric_api"]),
        assertions=verdict.assertions,
        # No server, no seed, no jar, and nobody observed an identity: the
        # contract's "none" record, the same one a run with no world writes.
        server_jar_sha1="",
        os_kernel=facts.os_kernel,
        java_runtime=facts.java_runtime,
        cpu_memory=facts.cpu_memory,
        renderer_display=facts.renderer_display,
        world_kind=NO_WORLD,
        seed_or_snapshot_id=NO_WORLD,
        configured_profile=profile_reference(profile),
        server_observed_name_uuid="",
    )


def _artifact(path: Path, name: str, found: dict[str, bytes]) -> None:
    """Seal one file under `name`, if it is there at all."""

    if path.is_file():
        found[name] = path.read_bytes()


def collect_artifacts(
    *,
    verdict_path: Path,
    case: Path,
    output_directory: Path | None,
    workspace_root: Path,
    orchestrator: Mapping[str, object],
) -> dict[str, bytes]:
    """Everything a repository check leaves behind, under names a reader knows."""

    found: dict[str, bytes] = {
        "check-verdict.json": verdict_path.read_bytes(),
        "case-definition.json": case.read_bytes(),
        "orchestrator-trace.json": (
            json.dumps(orchestrator, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    }
    if output_directory is not None:
        for output in sorted(output_directory.glob("*.log")):
            _artifact(output, f"checks/{output.name}", found)
    _artifact(workspace_root / FIXTURE_MANIFEST, "contracts/manifest.sha256", found)
    return found


def orchestrator_trace(*, verdict: Verdict, now: datetime) -> dict[str, object]:
    """What ran the checks, and what each of them was."""

    return {
        "schema_version": 1,
        "run_id": verdict.run_id,
        "orchestrator": "tools/run_repo_case.py",
        "sealed_at_utc": now.isoformat(),
        "checks": [dict(check) for check in verdict.checks],
    }


def seal(
    *,
    data_root: Path,
    case: Path,
    profile: Path,
    verdict_path: Path,
    output_directory: Path | None = None,
    workspace_root: Path | None = None,
    java: Path | None = None,
    renderer_display: str = "unmeasured",
    secrets: Sequence[str] = (),
    now: datetime | None = None,
) -> dict[str, object]:
    """Seal this check's evidence, or say what stopped it."""

    verdict = read_verdict(verdict_path)
    root = workspace_root if workspace_root is not None else find_workspace_root(REPOSITORY_ROOT)
    moment = now if now is not None else datetime.now(UTC)
    manifest = build_manifest(
        case=case,
        profile=profile,
        verdict=verdict,
        workspace_root=root,
        java=java,
        renderer_display=renderer_display,
    )
    artifacts = collect_artifacts(
        verdict_path=verdict_path,
        case=case,
        output_directory=output_directory,
        workspace_root=root,
        orchestrator=orchestrator_trace(verdict=verdict, now=moment),
    )
    directory = repository_bundle_directory(data_root, verdict.run_id)
    sealed = write_bundle(directory, manifest, artifacts, secrets=secrets)
    return {
        "schema_version": 1,
        "command": "seal repo case evidence",
        "status": "sealed",
        "run_id": verdict.run_id,
        "case_id": manifest.case_id,
        "case_version": manifest.case_version,
        "result": manifest.result.value,
        "evidence_directory": str(sealed.directory),
        "bundle_digest": sealed.bundle_digest,
        "artifacts": sorted(artifacts),
        "failures": list(manifest.assertions.failures),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seal a repository check's evidence at the address its run id names."
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--verdict", type=Path, required=True)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=None,
        help="where the runner kept each check's whole output",
    )
    parser.add_argument("--root", type=Path, default=None, help="the repository that was checked")
    parser.add_argument("--java", type=Path, default=None)
    parser.add_argument("--renderer-display", default="unmeasured")
    parser.add_argument(
        "--secret-env",
        action="append",
        default=[],
        metavar="NAME",
        help="an environment variable whose value must never be sealed",
    )
    args = parser.parse_args(argv)

    secrets = [os.environ[name] for name in args.secret_env if os.environ.get(name)]
    try:
        report = seal(
            data_root=args.data_root,
            case=args.case,
            profile=args.profile,
            verdict_path=args.verdict,
            output_directory=args.output_directory,
            workspace_root=args.root,
            java=args.java,
            renderer_display=args.renderer_display,
            secrets=secrets,
        )
    except Unsealable as error:
        failure = {"schema_version": 1, "status": "unsealed", "message": str(error)}
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return EXIT_UNSEALED

    print(json.dumps(report, sort_keys=True))
    return EXIT_HELD if report["result"] == EvidenceResult.PASS.value else EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
