"""Sealing one finished run's evidence at the address its run id names.

Three things happen here, in this order, and the order is the point.

The case's assertions are judged first, by `assert_case_evidence.py`, and its
answer is what the bundle records. Nothing in this tool decides whether a run
passed: it asks, and it seals the answer it was given, so a sealed bundle and
the verdict it came from cannot disagree.

Then the run's material is collected: Core's own run document, the ledger export
that is the Bridge/Runtime timeline, the server's log and the server's user cache
that are the server's own account, the client's output where the Bridge's lines
live, and the orchestrator's trace, which is authored here because the harness's
own account of what it did exists nowhere else.

Then it is sealed, read-only, at `run/evidence/<run-id>/` — the one address a
run id can produce, which is how `evidence verify` finds it afterwards.

Nothing is invented to fill a field. Where a value cannot be measured the field
says so or the seal is refused by the bundle library, which is the behaviour the
contract asks for: a bundle missing a digest is not evidence.

Exit codes: 0 sealed and held, 1 sealed and failed, 2 could not seal. A failed
case is still sealed — a failing run keeps its evidence, and a bundle that was
never written is a result nobody can check later.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from minekin_core.adapters.evidence.bundle import write_bundle
from minekin_core.adapters.evidence.promotion import load_case_manifest
from minekin_core.adapters.launcher.launch_plan import build_launch_plan, find_workspace_root
from minekin_core.adapters.launcher.recipe import BRIDGE_JAR_SHA256
from minekin_core.adapters.launcher.server_profile import load_server_profile
from minekin_core.cli.evidence import bundle_directory
from minekin_core.cli.init import run_root
from minekin_core.domain.evidence import (
    EMPTY_DOCUMENT_SHA256,
    NO_WORLD,
    Assertions,
    EvidenceManifest,
    EvidenceResult,
)
from minekin_core.domain.ids import KinId

# The tools directory, so the asserter can be imported by name. One module owns
# the reading of a finished run's material, and this seals what it read instead
# of keeping a second copy of how to read it — a second copy is a second place
# for the two to disagree about which events belong to this run.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fault_injection
from assert_case_evidence import (
    PLAYABLE_ESTABLISHED,
    RUN_DOCUMENT_KEY,
    read_run_material,
    timeline_bytes,
)
from evidence_provenance import host_facts, profile_reference, protocol_schema_digest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

EXIT_HELD = 0
EXIT_FAILED = 1
EXIT_UNSEALED = 2

ASSERTER = Path(__file__).with_name("assert_case_evidence.py")

#: The world a dedicated server run creates. A LAN run would have to say so; the
#: contract admits exactly these two, and "dedicated" is what the harness this
#: seals for starts.
DEDICATED = "dedicated"

_SEED = re.compile(r"^level-seed=(.*)$", re.MULTILINE)

#: The same rule the bundle library applies to an artifact name, so the refusal
#: happens where the name can still be reported rather than after the fact.
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


class Unsealable(Exception):
    """The run cannot be sealed, and saying why is more useful than a traceback."""


def server_jar_sha1(jar: Path) -> str:
    """The server jar's SHA-1 as measured from the bytes that were mounted.

    A jar that is not there is a caller mistake rather than a crash: naming one
    this run never used would be a claim about bytes nobody has.
    """

    try:
        digest = hashlib.sha1(jar.read_bytes(), usedforsecurity=False)
    except OSError as error:
        raise Unsealable(f"the server jar named for this run cannot be read: {error}") from error
    return digest.hexdigest()


def world_seed(server_directory: Path) -> str:
    """The seed the world was actually generated from, read from the server.

    Vanilla rewrites `server.properties`; the file in the run directory is the
    one it settled on, not the one anything handed it. A world whose seed is not
    written down cannot be replayed, so an absent seed is recorded as such rather
    than replaced by the configured value.
    """

    properties = server_directory / "server.properties"
    if not properties.is_file():
        return "unrecorded"
    match = _SEED.search(properties.read_text(encoding="utf-8", errors="replace"))
    if match is None or not match.group(1).strip():
        return "unrecorded"
    return match.group(1).strip()


def server_observed_identity(server_directory: Path, username: str) -> str:
    """Name and UUID as the server's own user cache recorded them."""

    cache = server_directory / "usercache.json"
    if not cache.is_file():
        return ""
    try:
        entries = json.loads(cache.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(entries, list):
        return ""
    for entry in cast(list[object], entries):
        if not isinstance(entry, Mapping):
            continue
        item = cast(Mapping[str, object], entry)
        if item.get("name") == username and isinstance(item.get("uuid"), str):
            return f"{username}/{item['uuid']}"
    return ""


def _artifact(path: Path, name: str, found: dict[str, bytes]) -> None:
    """Seal one file under `name`, if it is there at all.

    The name is checked here rather than left to the bundle library, which would
    refuse the whole seal with a message about a path. A crash report is named by
    the game, and a name that cannot be a path inside the bundle is a name this
    has to say out loud instead of dropping the report and sealing the rest.
    """

    if any(not _SAFE_SEGMENT.fullmatch(part) for part in name.split("/")):
        raise Unsealable(f"the artifact name {name!r} cannot be a path inside a bundle")
    if path.is_file():
        found[name] = path.read_bytes()


def collect_artifacts(
    *,
    overlay: Path | None,
    server_directory: Path | None,
    run_document: bytes,
    fault_injection: bytes,
    orchestrator: Mapping[str, object],
) -> dict[str, bytes]:
    """Every artifact this run left, under names a reader can recognise."""

    found: dict[str, bytes] = {
        "orchestrator-trace.json": (
            json.dumps(orchestrator, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    }
    if run_document:
        # Absent rather than empty when there was none: a run whose Core was
        # killed leaves no document, and an empty file would read as one that
        # said nothing rather than as one that never existed.
        found["run-document.json"] = run_document
    if fault_injection:
        # The bytes the asserter was given, not a second reading of the file: the
        # verdict and the artifact have to be the same snapshot of the record.
        found["fault-injection.json"] = fault_injection
    # The client's own output, where the Bridge's lines are: sealing the whole
    # stream rather than a filtered selection means a reader can check any
    # selection against it rather than having to trust one.
    if overlay is not None:
        _artifact(overlay / "logs" / "stdout.log", "client/stdout.log", found)
        _artifact(overlay / "logs" / "stderr.log", "client/stderr.log", found)
        _artifact(overlay / "logs" / "latest.log", "client/latest.log", found)
        for report in sorted((overlay / "crash-reports").glob("*")):
            if report.is_file():
                _artifact(report, f"client/crash-reports/{report.name}", found)
    if server_directory is not None:
        _artifact(server_directory / "server.log", "server/server.log", found)
        _artifact(server_directory / "usercache.json", "server/usercache.json", found)
        _artifact(server_directory / "server.properties", "server/server.properties", found)
    return found


def run_asserter(
    *,
    case: Path,
    run_document: Path | None,
    data_root: Path,
    server_directory: Path | None,
    username: str,
    run_id: str | None = None,
    fault_injection: str | None = None,
    python: str = sys.executable,
) -> dict[str, object]:
    """The case's verdict, from the one module that judges rather than writes.

    The fault record travels as text rather than as a path, because this side has
    already read it once: the same bytes are sealed as an artifact, so the verdict
    and the bundle cannot be about two different readings of one file.
    """

    arguments = [
        python,
        str(ASSERTER),
        "--case",
        str(case),
        "--data-root",
        str(data_root),
        "--username",
        username,
    ]
    if run_document is None:
        arguments += ["--run-id", str(run_id)]
    else:
        arguments += ["--run-document", str(run_document)]
    if server_directory is not None:
        arguments += ["--server-directory", str(server_directory)]
    if fault_injection is not None:
        arguments += ["--fault-injection-json", fault_injection]
    completed = subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode not in (EXIT_HELD, EXIT_FAILED):
        said = completed.stderr.strip().splitlines()
        raise Unsealable(f"the case could not be judged: {said[-1] if said else 'no reason given'}")
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Unsealable(f"the asserter produced no verdict: {error}") from error
    if not isinstance(report, dict):
        raise Unsealable("the asserter produced no verdict object")
    return cast(dict[str, object], report)


def _strings(report: Mapping[str, object], key: str) -> list[str]:
    value = report.get(key)
    return [str(item) for item in cast(list[object], value)] if isinstance(value, list) else []


def assertions_from(report: Mapping[str, object]) -> Assertions:
    """The verdict turned into the bundle's own comparison.

    An assertion the asserter cannot perform is recorded as a failure of a
    distinct kind rather than dropped: a case that named a check nothing runs has
    to look different from one whose checks all held.
    """

    failures = _strings(report, "failures")
    failures.extend(f"{name}:NO_IMPLEMENTATION" for name in _strings(report, "unimplemented"))
    return Assertions(
        expected=tuple(_strings(report, "expected")),
        observed=tuple(_strings(report, "observed")),
        failures=tuple(sorted(failures)),
    )


def build_manifest(
    *,
    case: Path,
    profile: Path,
    server_profile: Path | None,
    run_id: str,
    verdict: Mapping[str, object],
    server_directory: Path | None,
    server_jar: Path | None,
    username: str,
    renderer_display: str,
    java: Path | None,
    workspace_root: Path,
) -> EvidenceManifest:
    """Assemble the manifest from what was measured, refusing what was not.

    A run with no server profile is a run that joined no world, and it records
    that rather than borrowing the closest word that fits: the contract's third
    kind, with the digest of nothing where a server configuration would go. What
    it must never do is say `dedicated` because the field is required — a bundle
    that describes a world nobody visited is worse than one that describes none.
    """

    definition = load_case_manifest(case)
    plan = build_launch_plan(profile, workspace_root=workspace_root)
    bundle = cast(Mapping[str, object], plan["bundle"])
    target = None if server_profile is None else load_server_profile(server_profile)
    facts = host_facts(java, renderer_display)
    result = str(verdict.get("result", ""))
    if result not in {item.value for item in EvidenceResult}:
        raise Unsealable(f"the verdict {result!r} is not one of the contract's results")
    return EvidenceManifest(
        test_run_id=run_id,
        case_id=definition.case_id,
        case_version=definition.digest,
        result=EvidenceResult(result),
        launch_plan_digest=str(plan["plan_sha256"]),
        bridge_digest=BRIDGE_JAR_SHA256,
        protocol_schema_digest=protocol_schema_digest(workspace_root),
        server_config_digest=EMPTY_DOCUMENT_SHA256 if target is None else target.revision,
        minecraft=str(bundle["minecraft"]),
        loader=str(bundle["fabric_loader"]),
        fabric_api=str(bundle["fabric_api"]),
        assertions=assertions_from(verdict),
        server_jar_sha1="" if server_jar is None else server_jar_sha1(server_jar),
        os_kernel=facts.os_kernel,
        java_runtime=facts.java_runtime,
        cpu_memory=facts.cpu_memory,
        renderer_display=facts.renderer_display,
        world_kind=NO_WORLD if target is None else DEDICATED,
        seed_or_snapshot_id=(
            NO_WORLD if server_directory is None else world_seed(server_directory)
        ),
        configured_profile=profile_reference(profile),
        server_observed_name_uuid=(
            "" if server_directory is None else server_observed_identity(server_directory, username)
        ),
    )


def orchestrator_trace(
    *,
    case: Path,
    run_id: str,
    server_directory: Path | None,
    session_argv: Sequence[str],
    verdict: Mapping[str, object],
    now: datetime,
) -> dict[str, object]:
    """The harness's own account of what it did, which nothing else records."""

    return {
        "schema_version": 1,
        "case_id": load_case_manifest(case).case_id,
        "run_id": run_id,
        "orchestrator": "test-orchestrator/runner/domain.sh",
        "server_directory": str(server_directory),
        "session_argv": list(session_argv),
        "sealed_at_utc": now.isoformat(),
        "verdict": dict(verdict),
    }


def seal(
    *,
    data_root: Path,
    case: Path,
    profile: Path,
    server_profile: Path | None,
    run_document_path: Path | None,
    server_directory: Path | None,
    username: str,
    run_id: str | None = None,
    server_jar: Path | None = None,
    java: Path | None = None,
    renderer_display: str = "unmeasured",
    session_argv: Sequence[str] = (),
    secrets: Sequence[str] = (),
    fault_injection_path: Path | None = None,
    workspace_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Seal this run's evidence, or say what stopped it.

    A run is named by the document Core printed at its end, or by its run id when
    there is no document — which is the case for a run whose Core was killed, and
    the reason the second way exists at all. Everything the document would have
    said about the run's identity is then taken from the ledger, the record that
    survived the kill.

    A run that injected a fault names the record of it here. The record is read
    once, refused if it is not one, and then used twice — as the text the judge is
    given and as the bytes sealed — so the two are the same snapshot rather than
    two readings of a file that may have changed in between.
    """

    if (run_document_path is None) == (run_id is None):
        raise Unsealable("name the run either by its document or by its run id, not both")

    fault_injection_bytes = b""
    fault_injection_text: str | None = None
    if fault_injection_path is not None:
        try:
            record = fault_injection.read_record(fault_injection_path)
        except fault_injection.FaultInjectionError as error:
            raise Unsealable(f"the fault record cannot be sealed: {error}") from error
        fault_injection_bytes = record.raw
        fault_injection_text = record.raw.decode("utf-8")

    raw = b""
    run_document: dict[str, object] = {}
    if run_document_path is not None:
        try:
            raw = run_document_path.read_bytes()
            document = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise Unsealable(
                f"{run_document_path} is not a readable run document: {error}"
            ) from error
        if not isinstance(document, dict):
            raise Unsealable(f"{run_document_path} is not a run document object")
        run_document = cast(dict[str, object], document)

    verdict = run_asserter(
        case=case,
        run_document=run_document_path,
        run_id=run_id,
        data_root=data_root,
        server_directory=server_directory,
        username=username,
        fault_injection=fault_injection_text,
    )
    material = read_run_material(
        run_document=run_document_path,
        run_id=run_id,
        data_root=data_root,
        server_directory=server_directory,
        username=username,
    )

    if server_profile is None:
        # A manifest that says "no world" while the record shows a world would be
        # a lie about the run. The document says so when there is one, and the
        # ledger — the record that survives a killed Core — says so otherwise.
        section = run_document.get(RUN_DOCUMENT_KEY)
        run: Mapping[str, object] = (
            cast(Mapping[str, object], section) if isinstance(section, Mapping) else {}
        )
        state, admitted = run.get("connection_state"), run.get("snapshots_admitted")
        if state is not None or admitted or material.has(PLAYABLE_ESTABLISHED):
            raise Unsealable(
                "no server profile was given, but the record shows a world: "
                f"connection_state={state!r}, snapshots_admitted={admitted!r}"
            )

    kin_id = KinId(material.kin_id)
    identifier = material.run_id
    root = workspace_root if workspace_root is not None else find_workspace_root(REPOSITORY_ROOT)
    moment = now if now is not None else datetime.now(UTC)

    manifest = build_manifest(
        case=case,
        profile=profile,
        server_profile=server_profile,
        run_id=identifier,
        verdict=verdict,
        server_directory=server_directory,
        server_jar=server_jar,
        username=username,
        renderer_display=renderer_display,
        java=java,
        workspace_root=root,
    )
    artifacts = collect_artifacts(
        overlay=material.overlay,
        server_directory=server_directory,
        run_document=raw,
        fault_injection=fault_injection_bytes,
        orchestrator=orchestrator_trace(
            case=case,
            run_id=identifier,
            server_directory=server_directory,
            session_argv=session_argv,
            verdict=verdict,
            now=moment,
        ),
    )
    # The timeline sealed here is literally what the judge read: this is the same
    # reading, serialised, so the bundle cannot hold a different set of events
    # from the one the verdict was reached on.
    artifacts["bridge-trace.jsonl"] = timeline_bytes(material.ledger_events)

    directory = bundle_directory(run_root(data_root, kin_id), identifier)
    sealed = write_bundle(directory, manifest, artifacts, secrets=secrets)
    return {
        "schema_version": 1,
        "command": "seal run evidence",
        "status": "sealed",
        "run_id": identifier,
        "case_id": manifest.case_id,
        "case_version": manifest.case_version,
        "result": manifest.result.value,
        "evidence_directory": str(sealed.directory),
        "bundle_digest": sealed.bundle_digest,
        "artifacts": sorted(artifacts),
        "failures": list(manifest.assertions.failures),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seal one finished run's evidence at the address its run id names."
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument(
        "--server-profile",
        type=Path,
        default=None,
        help="absent for a run that joined no world; the bundle records that",
    )
    parser.add_argument(
        "--run-document",
        type=Path,
        default=None,
        help="what Core printed at the end; absent for a run that never printed one",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="names the run when there is no document, as a killed Core leaves none",
    )
    parser.add_argument(
        "--server-directory",
        type=Path,
        default=None,
        help="the server run's directory; absent when there was no server",
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--server-jar", type=Path, default=None)
    parser.add_argument("--java", type=Path, default=None)
    parser.add_argument("--renderer-display", default="unmeasured")
    parser.add_argument(
        "--fault-injection",
        type=Path,
        default=None,
        help=(
            "the harness's record of the fault it injected; read once, judged and "
            "sealed as one snapshot"
        ),
    )
    parser.add_argument(
        "--secret-env",
        action="append",
        default=[],
        metavar="NAME",
        help="an environment variable whose value must never be sealed",
    )
    parser.add_argument(
        "--session-argv",
        nargs=argparse.REMAINDER,
        default=[],
        help="the session command line this run was started with; must be last",
    )
    args = parser.parse_args(argv)

    secrets = [os.environ[name] for name in args.secret_env if os.environ.get(name)]
    try:
        report = seal(
            data_root=args.data_root,
            case=args.case,
            profile=args.profile,
            server_profile=args.server_profile,
            run_document_path=args.run_document,
            run_id=args.run_id,
            server_directory=args.server_directory,
            username=args.username,
            server_jar=args.server_jar,
            java=args.java,
            renderer_display=args.renderer_display,
            session_argv=args.session_argv,
            fault_injection_path=args.fault_injection,
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
