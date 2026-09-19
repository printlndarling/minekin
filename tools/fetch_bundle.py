"""Fill the content-addressed store from a reviewed launch plan.

`session start` refuses when an artifact it needs is not in the store yet, and
says "fetch them before starting a session" — this is the command that does the
fetching. Nothing in the product CLI can, because the frozen command surface has
no verb for it and the read-only ones must stay read-only; the same reasoning
that makes the supply-chain check a tool rather than a command applies here.

It writes into the store `session start` will read, by resolving the data root
and the Kin the same way that command does, and it prints the path so a
mismatch is visible rather than mysterious.

Pass --dry-run first. Filling p0-core is about a gigabyte, and the plan is worth
reading before paying for it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.launch_plan import artifacts_from_plan, build_launch_plan
from minekin_core.adapters.launcher.provision import missing_artifacts, provision_bundle
from minekin_core.cli.session import run_root, select_kin
from minekin_core.config import data_root, kin_selector
from minekin_core.domain.errors import MinekinError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / ("bundle-p0-core-1.21.4.json")
)


def _resolve_store(explicit: str | None) -> Path:
    """The store `session start` will read, unless one is named outright."""

    if explicit is not None:
        return Path(explicit).resolve()
    root = data_root()
    kin_id = select_kin(root, kin_selector())
    return run_root(root, kin_id) / "artifact-store"


def _emit(value: object) -> None:
    print(json.dumps(value, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fill the content-addressed store from a reviewed launch plan."
    )
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE), metavar="PATH")
    parser.add_argument("--store", default=None, metavar="PATH")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=None,
        metavar="N",
        help="refuse to fetch more than this many bytes; none means no limit",
    )
    parser.add_argument("--dry-run", action="store_true", help="report the plan without fetching")
    arguments = parser.parse_args(argv)

    store = _resolve_store(arguments.store)
    plan = build_launch_plan(Path(arguments.profile))
    artifacts = artifacts_from_plan(plan)
    store_object = ArtifactStore(store)
    missing = missing_artifacts(plan, store_object)

    # One document per run, the way the CLI reports: the plan summary is always
    # there, so whoever reads a refusal can see the job it was refusing.
    summary: dict[str, object] = {
        "schema_version": 1,
        "store": str(store),
        "artifacts": len(artifacts),
        "missing": len(missing),
        "missing_bytes": sum(artifact.size for artifact in missing),
    }
    if arguments.dry_run:
        _emit({**summary, "status": "planned"})
        return 0

    try:
        report = provision_bundle(plan, store_object, max_bytes=arguments.max_bytes)
    except MinekinError as error:
        _emit({**summary, "status": "refused", "reason": error.safe_message})
        return 2

    _emit({**summary, **report.as_dict()})
    return 0 if report.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
