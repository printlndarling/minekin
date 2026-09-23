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

A third thing is deliberate too, and it is the one this report does that nothing
else can. Verifying a bundle proves its bytes did not move; it says nothing about
whether those bytes support the verdict written over them, and a manifest rewritten
to claim a pass — `failures` cleared, `observed` filled in from `expected`,
`result` set to PASS, and the digest file regenerated beside it — verifies clean.
So every bundle that verifies is re-judged here, and one whose second reading
disagrees does not promote its package (`EVIDENCE_DISAGREES_WITH_ITS_BYTES`). This
is the only caller that can do it: the assertions are test-domain code, which is
why reaching a verdict again is a separate tool and not a step inside
`minekin evidence verify`. A bundle no verdict could be reached from is reported
with its reason rather than treated as either agreement or disagreement — it is a
gap in the reading, not a fact about the bytes, and a bundle cannot be pushed into
that state by editing it, because removing an artifact a manifest declares, or
leaving one it does not, is already a verification failure.

A bundle is also held to the name of the directory it sits in, and one run id
found in two roots is refused rather than chosen between. The directory name is
the attribution — the one address a run id alone can produce — so a manifest
naming a different run is that run's evidence, and two directories under one name
mean one of them is not what it says it is. Both are answered the way
`evidence verify` answers them, from the same code and with the same violation
string, because two spellings of one rule are two answers to one question.

Every bundle in the data root is offered as evidence, not just the passing ones.
A failing run keeps its evidence and a repaired case is re-run rather than
edited. Sequenced runs are ordered by the durable attempt registry, so only the
latest attempt decides; a later failure cannot be hidden by an earlier PASS.
Unsequenced legacy bundles keep the former any-satisfying rule only until that
case receives its first sequenced attempt.

What this cannot see, and now says so, is a case that is not there. Every reading
above walks the registry, so the answer it gives is about the cases somebody wrote:
"every mandatory case passed" is a true sentence about an incomplete case set, and
it is the sentence that turns a promotion gate into a certificate for work nobody
did. So each gate is judged against what the inventory requires of it — required
cases that are missing or filed under the wrong work package block the inventory
half. A present non-mandatory case remains a diagnostic rather than being silently
rewritten as mandatory; a gate with no mandatory cases is still reported and is
refused by the existing `NO_MANDATORY_CASES` evidence rule.

There is a second thing it could not see, and it also now says so. Every rule above
compares a bundle against the *case* it claims — the case id, the case version, the
verdict — and none of them asks which *build* the run was made from. So a PASS sealed
before a fix satisfies a gate for the build on disk today, which is the opposite of
what the validation contract's re-run rule is for: a failure is kept and a repaired
case is run again, and "run again" only means something if the evidence says which
build it came from. This report now names, per bundle, the reviewed plan it launched
from and whether that is the plan this checkout would launch from.

**Build identity is diagnostic and does not gate.** Evidence ordering is now
determined by each case's attempt registry; `gates_promotion` remains false for the
repository-build comparison specifically.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from minekin_core.adapters.evidence.attempt_registry import Attempt, read_attempts
from minekin_core.adapters.evidence.bundle import (
    MANIFEST_NAME,
    BundleVerification,
    verify_addressed_bundle,
)
from minekin_core.adapters.evidence.promotion import (
    case_evidence,
    latest_attempt_evidence,
    load_case_registry,
)
from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.cli.evidence import attempt_registry_path, candidate_roots
from minekin_core.domain.cases import (
    REQUIRED_CASES,
    REQUIRED_GATES,
    CaseEvidence,
    CaseRegistry,
    PromotionVerdict,
    ReJudge,
    RequiredCase,
    evaluate_promotion,
    required_case_violations,
)
from minekin_core.domain.errors import MinekinError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"
#: The frozen bundle recipe. Its plan digest is the only honest answer to "which
#: build is this evidence from?", and building that plan is cheap: `build_launch_plan`
#: reads the Bridge *source tree*, not a built jar — whether the jar exists is a
#: question for start time, which is why a machine that has never run Gradle can
#: still say which build its evidence belongs to.
RECIPE = REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / "bundle-p0-core-1.21.4.json"

# The re-judge lives beside this file, and this is the only report that can run it:
# the assertions are test-domain code, so the product's own verification must not
# import them — which is why reaching a verdict again is a separate tool and not a
# step inside `minekin evidence verify`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from assert_case_evidence import Unreadable  # noqa: E402
from rejudge_evidence import Unresolvable, rejudge  # noqa: E402

EXIT_PROMOTABLE = 0
EXIT_BLOCKED = 1
EXIT_UNUSABLE = 2


class Unusable(Exception):
    """The question cannot be asked of what was given."""


def repository_build() -> tuple[str | None, str]:
    """The plan digest this checkout would launch, or why it could not be built.

    `None` is not a digest and it is not a mismatch. A report that could not build
    the plan has no opinion about which build a bundle came from, and reporting
    "does not match" there would be answering a question nobody asked — the same
    distinction `ReJudge.UNJUDGED` draws about a verdict a reader could not reach.

    The digest is path-independent, which is what makes the comparison mean
    anything across the machines this project runs on: it is over the plan's own
    relative paths and the Bridge source tree's *contents*, so the same source
    produces it from the repository, from a copy of it, and from inside the
    container. Measured, not assumed.
    """

    try:
        plan = build_launch_plan(RECIPE)
    except (MinekinError, OSError, ValueError, KeyError, ArithmeticError) as error:
        return None, f"{type(error).__name__}: {error}"
    digest = plan.get("plan_sha256")
    if not isinstance(digest, str) or not digest:
        return None, "the plan carries no digest"
    return digest, ""


def no_outcomes() -> dict[str, ReJudge]:
    """Typed empties, so a default and a missing answer are the same shape."""

    return {}


def no_reasons() -> dict[str, str]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceOnDisk:
    """Every bundle found, with what verifying each one said about it."""

    verifications: Mapping[str, BundleVerification]
    #: Bundles that could not be read at all, as `run id: why`. Named rather
    #: than dropped: a report that hides what it could not read is worse than one
    #: that says it could not read something.
    unreadable: tuple[str, ...]
    #: What reaching each bundle's verdict a second time came to, and why when it
    #: came to nothing. A digest proves the bytes did not move; it does not prove
    #: those bytes support the verdict written over them, so a rewritten manifest
    #: with a regenerated digest checks out. This is that second reading, done here
    #: because this is the only place that can do it: the assertions are test-domain
    #: code, and the product's own verification must not import them.
    re_judged: Mapping[str, ReJudge] = field(default_factory=no_outcomes)
    re_judge_reasons: Mapping[str, str] = field(default_factory=no_reasons)
    attempts: tuple[Attempt, ...] = ()

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

    def as_documents(self, *, repository_build: str | None = None) -> list[dict[str, object]]:
        """Every bundle, as the report lists them.

        Listed one by one rather than only counted, because the verdict's blocks
        are a set over *all* the candidates for a case: a package can be
        promotable while its blocks list still names a reason, and that reason
        belongs to some earlier run. Saying which bundle contributed what is the
        difference between reading that and guessing at it.

        Each entry also carries the build it was sealed from. Promotion does not
        gate on that yet — the decision about how evidence is superseded is still
        open — but a report that never says it leaves a reader unable to tell
        whether a PASS means anything about the code on disk today, which is the
        one thing the validation contract's re-run rule is about.
        """

        entries: list[dict[str, object]] = []
        for run_id, item in sorted(self.verifications.items()):
            manifest = item.manifest
            sealed_from = None if manifest is None else manifest.launch_plan_digest
            entries.append(
                {
                    "run_id": run_id,
                    "case_id": None if manifest is None else manifest.case_id,
                    "case_version": None if manifest is None else manifest.case_version,
                    "attempt_sequence": None if manifest is None else manifest.attempt_sequence,
                    "supersedes_run_id": None if manifest is None else manifest.supersedes_run_id,
                    "result": None if manifest is None else manifest.result.value,
                    "verified": item.verified,
                    "sealed": item.sealed,
                    "violations": list(item.violations),
                    # Which reviewed plan this run launched from, and which Bridge
                    # source it carried. Both are the bundle's own claim about itself.
                    "launch_plan_digest": sealed_from,
                    "bridge_digest": None if manifest is None else manifest.bridge_digest,
                    # None when either side cannot answer: this checkout could not
                    # build a plan, or the bundle records no plan digest. Neither is
                    # "came from somewhere else".
                    "from_repository_build": (
                        None
                        if repository_build is None or sealed_from is None
                        else sealed_from == repository_build
                    ),
                    # Reported per bundle for the reason the blocks are named per
                    # package: "this one disagreed" is only actionable if the reader
                    # can see which one, and what it disagreed about.
                    "re_judged": self.re_judged.get(run_id, ReJudge.NOT_ATTEMPTED).value,
                    "re_judge_reason": self.re_judge_reasons.get(run_id, ""),
                }
            )
        return entries


def discover(data_root: Path, cases_dir: Path = CASES) -> EvidenceOnDisk:
    """Every evidence bundle under the data root, verified as it is found.

    One run id names one bundle, so two roots holding a directory of the same
    name is the collision `evidence verify` already refuses to guess between: a
    run id is a UUID, and a collision means one of the two is not what it says it
    is. Keeping whichever root was walked last would attribute one run's evidence
    to another, so the question is not asked at all rather than answered wrongly.

    A bundle that verified is then re-judged, here, because this is the last place
    that can: `minekin evidence verify` deliberately cannot, and a rewritten verdict
    with a regenerated digest passes it. A bundle that does not verify is not
    re-judged — there are no bytes to be right or wrong about — and it is already
    reported as a blocker for the reason it failed.
    """

    verifications: dict[str, BundleVerification] = {}
    unreadable: list[str] = []
    addressed: dict[str, Path] = {}
    outcomes: dict[str, ReJudge] = {}
    reasons: dict[str, str] = {}
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
                continue
            if verifications[directory.name].verified:
                outcome, reason = _re_judge(directory, cases_dir)
                outcomes[directory.name] = outcome
                if reason:
                    reasons[directory.name] = reason
    registry_path = attempt_registry_path(data_root)
    attempts = read_attempts(registry_path) if registry_path.exists() else ()
    attempt_by_run = {attempt.run_id: attempt for attempt in attempts}
    if not registry_path.exists() and any(
        item.manifest is not None and item.manifest.attempt_sequence is not None
        for item in verifications.values()
    ):
        raise Unusable("sequenced evidence exists without its attempt registry")
    unreadable_run_ids = {item.partition(":")[0] for item in unreadable}
    if attempts and unreadable_run_ids - set(attempt_by_run):
        raise Unusable("unreadable bundle is not attributable to the attempt registry")
    if (
        not attempts
        and unreadable
        and any(
            item.manifest is not None and item.manifest.result.value == "PASS"
            for item in verifications.values()
        )
    ):
        raise Unusable(
            "cannot establish whether unreadable evidence supersedes a legacy PASS "
            "without its registry"
        )
    for run_id, verification in verifications.items():
        manifest = verification.manifest
        if manifest is None or manifest.attempt_sequence is None:
            continue
        attempt = attempt_by_run.get(run_id)
        if attempt is None or (
            attempt.case_id != manifest.case_id
            or attempt.sequence != manifest.attempt_sequence
            or attempt.supersedes_run_id != manifest.supersedes_run_id
        ):
            raise Unusable(f"{run_id}: bundle attempt metadata disagrees with the attempt registry")
    return EvidenceOnDisk(
        verifications=verifications,
        unreadable=tuple(sorted(unreadable)),
        re_judged=outcomes,
        re_judge_reasons=reasons,
        attempts=attempts,
    )


def _promotion_evidence(evidence: EvidenceOnDisk) -> tuple[CaseEvidence, ...]:
    """Use only each case's latest durable attempt; legacy is pre-sequence only."""

    return latest_attempt_evidence(
        case_evidence(evidence.verifications, evidence.re_judged), evidence.attempts
    )


def _re_judge(directory: Path, cases_dir: Path) -> tuple[ReJudge, str]:
    """Reach one verified bundle's verdict again, and say why when it cannot."""

    try:
        report = rejudge(directory, cases_dir)
    except (Unresolvable, Unreadable) as error:
        return ReJudge.UNJUDGED, str(error)
    if report["disagreements"]:
        return ReJudge.DISAGREES, "; ".join(cast(list[str], report["disagreements"]))
    return ReJudge.AGREES, ""


def _verdict_document(verdict: PromotionVerdict) -> dict[str, object]:
    return verdict.as_document()


def _report_work_packages(
    registry: CaseRegistry,
    evidence: EvidenceOnDisk,
    *,
    required: Sequence[RequiredCase] = REQUIRED_CASES,
) -> dict[str, dict[str, object]]:
    """One verdict per gate, in the order the gates are frozen.

    Every gate is reported, not only the ones with mandatory cases: a gate whose
    cases are all present and declared not to gate has no mandatory case to evaluate,
    and "nothing to gate on" is a state a report most needs to show rather than skip.

    The bundles are verified once, here, and the verdicts are computed from that
    reading. `adapters.evidence.promotion.evaluate_case_promotion` takes directories
    and verifies them itself, which is the right shape for a caller that has nothing
    else to say about a bundle — but it raises on one it cannot read, and a report
    that stops at the first unreadable directory cannot name it as the reason a gate
    is blocked.

    Which cases a gate is judged on comes from the gate, not from a work-package
    grouping of the registry: that is what keeps a hole in the host surface from
    blocking a phase of the core slice, and the other way round.
    """

    claims = _promotion_evidence(evidence)
    return {
        gate: _verdict_document(
            evaluate_promotion(
                registry.required_cases(gate, required=required),
                claims,
                requirement=registry.requirement(gate, required=required),
            )
        )
        for gate in REQUIRED_GATES
    }


def _report_with_inventory(
    *,
    data_root: Path,
    cases_dir: Path = CASES,
    gated: str | None = None,
    required: Sequence[RequiredCase] = REQUIRED_CASES,
) -> dict[str, object]:
    """Whether the evidence on disk promotes the named gate, or every gate at once.

    An inventory that cannot be read is refused rather than gated with. Both answers
    are fail-closed and they are not the same answer: a missing case is a fact this
    report exists to state, while an inventory holding a repeated or out-of-vocabulary
    identifier is a question that cannot be asked — and either way the verdict that
    came out of it would look exactly like one that had been checked.
    """

    violations = required_case_violations(required)
    if violations:
        raise Unusable(
            "the required-case inventory is not usable: "
            + ", ".join(f"{reason.value} ({subject})" for reason, subject in violations)
        )
    if gated is not None and gated not in REQUIRED_GATES:
        raise Unusable(f"{gated} is not a gate this repository requires cases for")

    registry = load_case_registry(cases_dir)
    evidence = discover(data_root, cases_dir)
    build, build_reason = repository_build()
    bundles = evidence.as_documents(repository_build=build)
    packages = _report_work_packages(registry, evidence, required=required)
    overall = _verdict_document(
        evaluate_promotion(
            registry.required_cases(*REQUIRED_GATES, required=required),
            _promotion_evidence(evidence),
            requirement=registry.requirement(*REQUIRED_GATES, required=required),
        )
    )
    gate = packages.get(gated, {}) if gated is not None else overall
    return {
        "schema_version": 1,
        "command": "report promotion",
        "data_root": str(data_root),
        "evidence": {
            "count": len(evidence.verifications),
            "bundles": bundles,
            "attempts": [
                {
                    "case_id": item.case_id,
                    "run_id": item.run_id,
                    "sequence": item.sequence,
                    "supersedes_run_id": item.supersedes_run_id,
                    "status": item.status,
                }
                for item in evidence.attempts
            ],
            "unverified": list(evidence.unverified),
            "unsealed": list(evidence.unsealed),
            "unreadable": list(evidence.unreadable),
            # Which of the bundles were sealed from the build this checkout would
            # launch. Named rather than counted, for the same reason the blocks are:
            # "one of these is stale" is only actionable with the ids.
            "from_another_build": [
                cast(str, entry["run_id"])
                for entry in bundles
                if entry["from_repository_build"] is False
            ],
        },
        # The build this report is comparing against, and an explicit statement that
        # build identity is diagnostic only. Per-case attempt ordering is reported
        # separately from this build comparison.
        "repository_build": {
            "recipe": str(RECIPE.relative_to(REPOSITORY_ROOT).as_posix()),
            "plan_sha256": build,
            "readable": build is not None,
            "reason": build_reason,
            "gates_promotion": False,
        },
        "work_packages": packages,
        "overall": overall,
        "gated": gated,
        "status": "promotable" if gate.get("promotable") else "blocked",
    }


def report(
    *, data_root: Path, cases_dir: Path = CASES, gated: str | None = None
) -> dict[str, object]:
    """Gate evidence against the repository's complete reviewed inventory.

    The inventory is intentionally not a public override: a production caller may
    choose a gate, not redefine what that gate requires. Focused tests use the
    private inventory-aware seam above to isolate evidence behavior.
    """

    return _report_with_inventory(
        data_root=data_root,
        cases_dir=cases_dir,
        gated=gated,
        required=REQUIRED_CASES,
    )


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
