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
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from minekin_core.adapters.evidence.bundle import write_bundle
from minekin_core.adapters.evidence.promotion import load_case_manifest
from minekin_core.adapters.launcher.launch_plan import build_launch_plan, find_workspace_root
from minekin_core.adapters.launcher.recipe import BRIDGE_JAR_SHA256, source_tree_sha256
from minekin_core.adapters.launcher.server_profile import load_server_profile
from minekin_core.cli.evidence import bundle_directory
from minekin_core.cli.init import DATABASE_NAME, kin_directory, run_root
from minekin_core.domain.evidence import Assertions, EvidenceManifest, EvidenceResult
from minekin_core.domain.ids import KinId

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


@dataclass(frozen=True, slots=True)
class HostFacts:
    """What the host was, as the run's environment section reports it."""

    os_kernel: str
    java_runtime: str
    cpu_memory: str
    renderer_display: str


def _first_lines(text: str, count: int = 2) -> str:
    """The vendor's own words about its runtime, joined and bounded."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " / ".join(lines[:count])


def java_runtime(java: Path | None) -> str:
    """Which JVM the client ran under, read from that JVM rather than assumed."""

    executable = java or shutil.which("java")
    if executable is None:
        return "unmeasured"
    try:
        completed = subprocess.run(
            [str(executable), "-version"], capture_output=True, text=True, check=False
        )
    except OSError as error:
        return f"unmeasurable ({type(error).__name__})"
    # `java -version` writes to stderr, and has done since before anyone expected
    # otherwise. Both streams are read so the answer does not depend on the JDK.
    return _first_lines(f"{completed.stdout}\n{completed.stderr}") or "unmeasured"


def cpu_memory() -> str:
    """Processors and RAM, from the kernel's own accounting where it exists."""

    processors = os.cpu_count() or 0
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return f"{processors} vCPU / memory unmeasured"
    match = re.search(r"^MemTotal:\s+(\d+) kB$", meminfo.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        return f"{processors} vCPU / memory unmeasured"
    gib = int(match.group(1)) / (1024 * 1024)
    return f"{processors} vCPU / {gib:.1f} GiB"


def host_facts(java: Path | None, renderer_display: str) -> HostFacts:
    return HostFacts(
        os_kernel=f"{platform.system()} {platform.release()}",
        java_runtime=java_runtime(java),
        cpu_memory=cpu_memory(),
        renderer_display=renderer_display,
    )


def protocol_schema_digest(workspace_root: Path) -> str:
    """The reviewed protocol schema, as one digest.

    `proto/` is the schema; the generated code is downstream of it. The digest is
    the recipe's own tree rule rather than a second one, so "a tree digest" means
    one thing in this repository: paths and (CRLF-normalised) bytes in codepoint
    order, which is what makes it the same value on both platforms.
    """

    return source_tree_sha256(workspace_root / "proto")


def server_jar_sha1(jar: Path) -> str:
    """The server jar's SHA-1 as measured from the bytes that were mounted."""

    digest = hashlib.sha1(jar.read_bytes(), usedforsecurity=False)
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


def configured_profile(profile: Path) -> str:
    """A reference to the client profile that carries no path from this host.

    The profile is named by its file name and the digest of its bytes: enough to
    say which document was used, and nothing about where the operator keeps it —
    a bundle is handed to other people.
    """

    digest = hashlib.sha256(profile.read_bytes()).hexdigest()
    return f"{profile.name}#{digest[:16]}"


def ledger_timeline(database: Path, run_id: str) -> bytes:
    """This run's events, exported as they were recorded.

    The ledger is the only place the Bridge/Runtime timeline exists, and it is a
    live database, so what is sealed is an export of this run's rows rather than
    the file: a reader gets the fields the contract names, and the payload hash
    that the ledger's own integrity rests on is carried along with them.
    """

    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT position, event_id, event_type, schema_version, kin_id, run_id, "
            "client_instance_id, session_id, generation, world_context_id, sequence, "
            "correlation_id, causation_id, monotonic_ns, observed_at_utc, source, "
            "trust_class, payload_json, payload_hash "
            "FROM event WHERE run_id = ? ORDER BY position",
            (run_id,),
        ).fetchall()
    except sqlite3.Error as error:
        raise Unsealable(f"{database} cannot be read for this run: {error}") from error
    finally:
        connection.close()
    return "".join(json.dumps(dict(row), sort_keys=True) + "\n" for row in rows).encode("utf-8")


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
    overlay: Path,
    server_directory: Path,
    run_document: bytes,
    orchestrator: Mapping[str, object],
) -> dict[str, bytes]:
    """Every artifact this run left, under names a reader can recognise."""

    found: dict[str, bytes] = {
        "run-document.json": run_document,
        "orchestrator-trace.json": (
            json.dumps(orchestrator, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    }
    # The client's own output, where the Bridge's lines are: sealing the whole
    # stream rather than a filtered selection means a reader can check any
    # selection against it rather than having to trust one.
    _artifact(overlay / "logs" / "stdout.log", "client/stdout.log", found)
    _artifact(overlay / "logs" / "stderr.log", "client/stderr.log", found)
    _artifact(overlay / "logs" / "latest.log", "client/latest.log", found)
    for report in sorted((overlay / "crash-reports").glob("*")):
        if report.is_file():
            _artifact(report, f"client/crash-reports/{report.name}", found)
    _artifact(server_directory / "server.log", "server/server.log", found)
    _artifact(server_directory / "usercache.json", "server/usercache.json", found)
    _artifact(server_directory / "server.properties", "server/server.properties", found)
    return found


def run_asserter(
    *,
    case: Path,
    run_document: Path,
    server_directory: Path,
    username: str,
    python: str = sys.executable,
) -> dict[str, object]:
    """The case's verdict, from the one module that judges rather than writes."""

    completed = subprocess.run(
        [
            python,
            str(ASSERTER),
            "--case",
            str(case),
            "--run-document",
            str(run_document),
            "--server-directory",
            str(server_directory),
            "--username",
            username,
        ],
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
    server_profile: Path,
    run_document: Mapping[str, object],
    verdict: Mapping[str, object],
    server_directory: Path,
    server_jar: Path | None,
    username: str,
    renderer_display: str,
    java: Path | None,
    workspace_root: Path,
) -> EvidenceManifest:
    """Assemble the manifest from what was measured, refusing what was not."""

    definition = load_case_manifest(case)
    plan = build_launch_plan(profile, workspace_root=workspace_root)
    bundle = cast(Mapping[str, object], plan["bundle"])
    target = load_server_profile(server_profile)
    run_id = _text(run_document, "run_id")
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
        server_config_digest=target.revision,
        minecraft=str(bundle["minecraft"]),
        loader=str(bundle["fabric_loader"]),
        fabric_api=str(bundle["fabric_api"]),
        assertions=assertions_from(verdict),
        server_jar_sha1="" if server_jar is None else server_jar_sha1(server_jar),
        os_kernel=facts.os_kernel,
        java_runtime=facts.java_runtime,
        cpu_memory=facts.cpu_memory,
        renderer_display=facts.renderer_display,
        world_kind=DEDICATED,
        seed_or_snapshot_id=world_seed(server_directory),
        configured_profile=configured_profile(profile),
        server_observed_name_uuid=server_observed_identity(server_directory, username),
    )


def _text(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise Unsealable(f"the run document has no {key}")
    return value


def orchestrator_trace(
    *,
    case: Path,
    run_id: str,
    server_directory: Path,
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
    server_profile: Path,
    run_document_path: Path,
    server_directory: Path,
    username: str,
    server_jar: Path | None = None,
    java: Path | None = None,
    renderer_display: str = "unmeasured",
    session_argv: Sequence[str] = (),
    secrets: Sequence[str] = (),
    workspace_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Seal this run's evidence, or say what stopped it."""

    try:
        raw = run_document_path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Unsealable(f"{run_document_path} is not a readable run document: {error}") from error
    if not isinstance(document, dict):
        raise Unsealable(f"{run_document_path} is not a run document object")
    run_document = cast(dict[str, object], document)

    verdict = run_asserter(
        case=case,
        run_document=run_document_path,
        server_directory=server_directory,
        username=username,
    )
    kin_id = KinId(_text(run_document, "kin_id"))
    run_id = _text(run_document, "run_id")
    overlay = Path(_text(run_document, "overlay"))
    root = workspace_root if workspace_root is not None else find_workspace_root(REPOSITORY_ROOT)
    moment = now if now is not None else datetime.now(UTC)

    manifest = build_manifest(
        case=case,
        profile=profile,
        server_profile=server_profile,
        run_document=run_document,
        verdict=verdict,
        server_directory=server_directory,
        server_jar=server_jar,
        username=username,
        renderer_display=renderer_display,
        java=java,
        workspace_root=root,
    )
    artifacts = collect_artifacts(
        overlay=overlay,
        server_directory=server_directory,
        run_document=raw,
        orchestrator=orchestrator_trace(
            case=case,
            run_id=run_id,
            server_directory=server_directory,
            session_argv=session_argv,
            verdict=verdict,
            now=moment,
        ),
    )
    artifacts["bridge-trace.jsonl"] = ledger_timeline(
        kin_directory(data_root, kin_id) / DATABASE_NAME, run_id
    )

    directory = bundle_directory(run_root(data_root, kin_id), run_id)
    sealed = write_bundle(directory, manifest, artifacts, secrets=secrets)
    return {
        "schema_version": 1,
        "command": "seal run evidence",
        "status": "sealed",
        "run_id": run_id,
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
    parser.add_argument("--server-profile", type=Path, required=True)
    parser.add_argument("--run-document", type=Path, required=True)
    parser.add_argument("--server-directory", type=Path, required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--server-jar", type=Path, default=None)
    parser.add_argument("--java", type=Path, default=None)
    parser.add_argument("--renderer-display", default="unmeasured")
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
            server_directory=args.server_directory,
            username=args.username,
            server_jar=args.server_jar,
            java=args.java,
            renderer_display=args.renderer_display,
            session_argv=args.session_argv,
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
