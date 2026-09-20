"""Reporting whether the evidence on disk lets a work package be called tested.

The promotion rule has been a library since W70 and had nothing to read: there
was no bundle anywhere to promote from. There are now, and this is the command
that reads them.

It reads, it judges, and it writes nothing. The validation contract says only the
registry's promotion job may change a bundle's status, and there is no registry
here — what this produces is the answer that job would need, with the blocking
cases named, so "we think P0 is tested" is a statement someone can check rather
than one this repository asserts about itself.

Two things are deliberately not the same answer. A bundle that does not verify
is evidence that *blocks*: it is read, and it is reported as
`EVIDENCE_NOT_VERIFIED` against the case it names rather than skipped, because a
bundle that quietly disappears from the report would make a data root look
emptier than it is. And a bundle whose read-only bits were restored is reported
as unsealed but is not a blocker on its own: the digest is the guarantee and the
mode is a courtesy, which is the position `evidence verify` already takes.

A bundle is also held to the name of the directory it sits in, and one run id
found in two roots is refused rather than chosen between. The directory name is
the attribution — the one address a run id alone can produce — so a manifest
naming a different run is that run's evidence, and two directories under one name
mean one of them is not what it says it is. Both are answered the way
`evidence verify` answers them, from the same code and with the same violation
string, because two spellings of one rule are two answers to one question.

Every bundle in the data root is offered as evidence, not just the passing ones.
A failing run keeps its evidence and a repaired case is re-run rather than
edited, so a case that failed once and passed later has both bundles on disk —
and the rule that decides takes the satisfying one.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from minekin_core.adapters.evidence.bundle import (
    MANIFEST_NAME,
    BundleVerification,
    verify_addressed_bundle,
)
from minekin_core.adapters.evidence.promotion import case_evidence, load_case_registry
from minekin_core.cli.evidence import candidate_roots
from minekin_core.domain.cases import CaseRegistry, PromotionVerdict, evaluate_promotion
from minekin_core.domain.errors import MinekinError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"

EXIT_PROMOTABLE = 0
EXIT_BLOCKED = 1
EXIT_UNUSABLE = 2


class Unusable(Exception):
    """The question cannot be asked of what was given."""


@dataclass(frozen=True, slots=True)
class EvidenceOnDisk:
    """Every bundle found, with what verifying each one said about it."""

    verifications: Mapping[str, BundleVerification]
    #: Bundles that could not be read at all, as `run id: why`. Named rather
    #: than dropped: a report that hides what it could not read is worse than one
    #: that says it could not read something.
    unreadable: tuple[str, ...]

    @property
    def unverified(self) -> tuple[str, ...]:
        return tuple(
            sorted(run_id for run_id, item in self.verifications.items() if not item.verified)
        )

    @property
    def unsealed(self) -> tuple[str, ...]:
        return tuple(
            sorted(run_id for run_id, item in self.verifications.items() if not item.sealed)
        )

    def as_documents(self) -> list[dict[str, object]]:
        """Every bundle, as the report lists them.

        Listed one by one rather than only counted, because the verdict's blocks
        are a set over *all* the candidates for a case: a package can be
        promotable while its blocks list still names a reason, and that reason
        belongs to some earlier run. Saying which bundle contributed what is the
        difference between reading that and guessing at it.
        """

        entries: list[dict[str, object]] = []
        for run_id, item in sorted(self.verifications.items()):
            manifest = item.manifest
            entries.append(
                {
                    "run_id": run_id,
                    "case_id": None if manifest is None else manifest.case_id,
                    "case_version": None if manifest is None else manifest.case_version,
                    "result": None if manifest is None else manifest.result.value,
                    "verified": item.verified,
                    "sealed": item.sealed,
                    "violations": list(item.violations),
                }
            )
        return entries


def discover(data_root: Path) -> EvidenceOnDisk:
    """Every evidence bundle under the data root, verified as it is found.

    One run id names one bundle, so two roots holding a directory of the same
    name is the collision `evidence verify` already refuses to guess between: a
    run id is a UUID, and a collision means one of the two is not what it says it
    is. Keeping whichever root was walked last would attribute one run's evidence
    to another, so the question is not asked at all rather than answered wrongly.
    """

    verifications: dict[str, BundleVerification] = {}
    unreadable: list[str] = []
    addressed: dict[str, Path] = {}
    for root in candidate_roots(data_root):
        # An evidence root that is not there holds nothing: the repository's is
        # absent on a host that has only ever run sessions, and a Kin's is absent
        # before `init`.
        if not root.is_dir():
            continue
        for directory in sorted(path for path in root.iterdir() if path.is_dir()):
            first = addressed.get(directory.name)
            first_is_bundle = first is not None and (first / MANIFEST_NAME).is_file()
            this_is_bundle = (directory / MANIFEST_NAME).is_file()
            if first is not None and (first_is_bundle or this_is_bundle):
                raise Unusable(
                    f"{directory.name} has bundles in {first} and {directory}; "
                    "a run id names one bundle, so no report can be read from this root"
                )
            addressed.setdefault(directory.name, directory)
            # A directory that is not a bundle is not this command's business —
            # the evidence root is a plain directory and anything may live in it.
            # It is still remembered above, because the same run-id name beside
            # a real bundle is an attribution collision even when this copy is
            # incomplete.
            if not this_is_bundle:
                continue
            try:
                verifications[directory.name] = verify_addressed_bundle(directory)
            except MinekinError as error:
                unreadable.append(f"{directory.name}: {error.safe_message}")
    return EvidenceOnDisk(verifications=verifications, unreadable=tuple(sorted(unreadable)))


def _verdict_document(verdict: PromotionVerdict) -> dict[str, object]:
    return verdict.as_document()


def report_work_packages(
    registry: CaseRegistry, evidence: EvidenceOnDisk
) -> dict[str, dict[str, object]]:
    """One verdict per work package the registry has mandatory cases for.

    The bundles are verified once, here, and the verdicts are computed from that
    reading. `adapters.evidence.promotion.evaluate_case_promotion` takes
    directories and verifies them itself, which is the right shape for a caller
    that has nothing else to say about a bundle — but it raises on one it cannot
    read, and a report that stops at the first unreadable directory cannot name
    it as the reason a package is blocked.
    """

    packages = sorted({case.work_package for case in registry.mandatory_cases()})
    claims = case_evidence(evidence.verifications)
    return {
        package: _verdict_document(evaluate_promotion(registry.mandatory_cases(package), claims))
        for package in packages
    }


def report(
    *,
    data_root: Path,
    cases_dir: Path = CASES,
    gated: str | None = None,
) -> dict[str, object]:
    """Whether the evidence on disk promotes the named package, or everything."""

    registry = load_case_registry(cases_dir)
    if gated is not None and not registry.mandatory_cases(gated):
        raise Unusable(f"{cases_dir} holds no mandatory case for {gated}")

    evidence = discover(data_root)
    packages = report_work_packages(registry, evidence)
    overall = _verdict_document(
        evaluate_promotion(list(registry.mandatory_cases()), case_evidence(evidence.verifications))
    )
    gate = packages.get(gated, {}) if gated is not None else overall
    return {
        "schema_version": 1,
        "command": "report promotion",
        "data_root": str(data_root),
        "evidence": {
            "count": len(evidence.verifications),
            "bundles": evidence.as_documents(),
            "unverified": list(evidence.unverified),
            "unsealed": list(evidence.unsealed),
            "unreadable": list(evidence.unreadable),
        },
        "work_packages": packages,
        "overall": overall,
        "gated": gated,
        "status": "promotable" if gate.get("promotable") else "blocked",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report whether the evidence on disk lets a work package be called tested."
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--cases-dir", type=Path, default=CASES)
    parser.add_argument(
        "--work-package",
        default=None,
        metavar="W40",
        help="gate on this package; without it the exit status gates on everything",
    )
    args = parser.parse_args(argv)

    try:
        document = report(
            data_root=args.data_root, cases_dir=args.cases_dir, gated=args.work_package
        )
    except (Unusable, MinekinError) as error:
        reason = error.safe_message if isinstance(error, MinekinError) else str(error)
        failure = {"schema_version": 1, "status": "unusable", "message": reason}
        print(json.dumps(failure), file=sys.stderr)
        return EXIT_UNUSABLE

    print(json.dumps(document, sort_keys=True))
    return EXIT_PROMOTABLE if document["status"] == "promotable" else EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
