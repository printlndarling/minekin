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

The registry is read in that direction too. Every rule above starts from a bundle
and asks what it attests; the registry also attests bundles, and a row it marks
SEALED whose bytes no longer answer to that run id is a hole in the reading, not an
emptier root. For a case's latest attempt the behavior is the existing one: that run
id blocks the case and no earlier PASS is revived. For an earlier attempt nothing
would notice at all — fewer bundles listed, the same verdict, retained failure
material gone quietly — so every such row is named, whichever end of the chain it
sits at. Naming is where this stops, and it is a deliberate stop rather than a gap:
an intentional read-only slice of a root — some bundles copied beside the whole
ledger — has exactly the same shape as a loss, and refusing that state would take
away the one channel that lets a sealed root be re-read without the 19 GiB beside
it. Which cases a loss does change the answer for is therefore visible twice: the
named list, and the case-level block the latest-attempt rule already raises.

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
from and whether that is the plan this checkout would launch from *for that bundle's
own Minecraft version*. One recipe cannot answer that: with two reviewed versions on
disk, comparing every bundle against the 1.21.4 plan calls the honest 1.20.1 evidence
stale, and a diagnostic that is wrong in that direction is worse than none.

**Build identity is diagnostic and does not gate.** Evidence ordering is now
determined by each case's attempt registry; `gates_promotion` remains false for the
repository-build comparison specifically.

A repository check has a second axis of provenance that no rule above reads. Its
verdict records the command that performed each assertion, and the first word of
that command is the interpreter which ran it — so a check sealed inside the
controlled image and the same check sealed from a developer's own virtualenv are
two different claims about the same case, and the manifest's `environment` block
cannot tell them apart because it describes the launcher, not the check. One of
those shapes has already been measured producing five false FAILs at once from a
missing module. So the report names, per repository-check bundle, the interpreters
its own verdict records, and lists the bundles that do not record the interpreter
the runner's image contract pins. The comparison is deliberately *not* against
whatever is reading: the same interpreter answers under two spellings inside one
venv (`python` and `python3`), so a reader-relative answer would name every bundle
in the image and call that a finding. **Like the build comparison this is
diagnostic and does not gate**, and for the same reason: which interpreter ran a
check is a claim the bundle makes about where it was made, and one an operator can
answer without this report agreeing with it.
"""

from __future__ import annotations

import argparse
import json
import os
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
#: The artifact `seal_repo_case.py` writes: the repository check runner's own
#: verdict, command included. A session bundle has no such file.
CHECK_VERDICT_NAME = "check-verdict.json"
#: The interpreter a repository check records when it ran inside the controlled
#: image: the venv `test-orchestrator/runner/Dockerfile` builds and pins its test
#: toolchain into. A unit test reads that file for this exact string, so the two
#: cannot drift apart quietly.
CONTROLLED_CHECK_INTERPRETER = "/opt/minekin/bin/python3"

#: A visibility gap in the seal format itself, named on the report surface so a
#: reader no longer has to infer it. `orchestrator-trace.json` records the
#: orchestrator as the fixed path string `test-orchestrator/runner/domain.sh`
#: (`orchestrator_trace()` in `tools/seal_run_evidence.py`), with no version or
#: digest beside it, and the artifact set is collected entry by entry under
#: named constants — the script's own bytes are in no artifact a bundle holds.
#: So "did these two runs use the same revision of that script?" cannot be read
#: from a bundle by construction. This is a statement beside the gate payload,
#: never a block: it is a property of the seal format, not a finding about the
#: evidence on disk, and it decides no verdict — which the entry itself says,
#: in the document.
ORCHESTRATOR_REVISION_GAP: dict[str, object] = {
    "id": "ORCHESTRATOR_REVISION_NOT_PINNED",
    "artifact": "orchestrator-trace.json",
    "field": "orchestrator",
    "statement": (
        "sealed bundles do not pin the revision of the orchestrator script: "
        "orchestrator-trace.json records field `orchestrator` as the fixed path "
        "string test-orchestrator/runner/domain.sh with no version or digest, "
        "and no other bundle artifact carries the script's bytes, so whether two "
        "runs used the same revision of it cannot be read from the bundles by "
        "construction"
    ),
    "gates_promotion": False,
}

VISIBILITY_GAPS: tuple[dict[str, object], ...] = (ORCHESTRATOR_REVISION_GAP,)

# The re-judge lives beside this file, and this is the only report that can run it:
# the assertions are test-domain code, so the product's own verification must not
# import them — which is why reaching a verdict again is a separate tool and not a
# step inside `minekin evidence verify`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from assert_case_evidence import Unreadable  # noqa: E402
from rejudge_evidence import Unresolvable, rejudge  # noqa: E402
from verify_supply_chain import reviewed_stacks  # noqa: E402

EXIT_PROMOTABLE = 0
EXIT_BLOCKED = 1
EXIT_UNUSABLE = 2


class Unusable(Exception):
    """The question cannot be asked of what was given."""


@dataclass(frozen=True, slots=True)
class RecipeBuild:
    """Which build this checkout would launch for one reviewed Minecraft version.

    A plan digest is the honest answer to "which build is this evidence from?", and
    building that plan is cheap: `build_launch_plan` reads the Bridge *source tree*,
    not a built jar — whether the jar exists is a question for start time, which is
    why a machine that has never run Gradle can still say which build its evidence
    belongs to. The digest is path-independent, which is what makes the comparison
    mean anything across the machines this project runs on: it is over the plan's own
    relative paths and the Bridge source tree's *contents*, so the same source
    produces it from the repository, from a copy of it, and from inside the
    container. Measured, not assumed.

    `plan_sha256` is None when the plan could not be built, and None is not a digest
    and not a mismatch either — see `_build_agrees`.
    """

    minecraft: str
    recipe: Path
    plan_sha256: str | None
    reason: str

    def as_document(self) -> dict[str, object]:
        return {
            "minecraft": self.minecraft,
            "recipe": self.recipe.relative_to(REPOSITORY_ROOT).as_posix(),
            "plan_sha256": self.plan_sha256,
            "readable": self.plan_sha256 is not None,
            "reason": self.reason,
        }


def repository_builds() -> tuple[RecipeBuild, ...]:
    """One entry per Minecraft version this checkout has a reviewed recipe for.

    The versions come from `verify_supply_chain.reviewed_stacks()` rather than from a
    table here: that tool is the one place that says which bundle recipe is reviewed
    for which version, and a second list would be a claim that can disagree with it.
    """

    builds: list[RecipeBuild] = []
    for minecraft, stack in sorted(reviewed_stacks().items()):
        try:
            plan = build_launch_plan(stack.bundle_profile)
        except (MinekinError, OSError, ValueError, KeyError, ArithmeticError) as error:
            builds.append(
                RecipeBuild(
                    minecraft=minecraft,
                    recipe=stack.bundle_profile,
                    plan_sha256=None,
                    reason=f"{type(error).__name__}: {error}",
                )
            )
            continue
        digest = plan.get("plan_sha256")
        usable = isinstance(digest, str) and bool(digest)
        builds.append(
            RecipeBuild(
                minecraft=minecraft,
                recipe=stack.bundle_profile,
                plan_sha256=digest if usable else None,
                reason="" if usable else "the plan carries no digest",
            )
        )
    return tuple(builds)


def _build_agrees(
    plans: Mapping[str, str], claimed_version: str | None, sealed_from: str | None
) -> bool | None:
    """Whether a bundle came from the build this checkout would launch for its version.

    `None` whenever either side cannot answer: this checkout could not build that
    version's plan, the bundle records no plan digest, or the bundle names a version
    nothing here has a recipe for. A report that could not ask the question has no
    opinion about the answer, and reporting "does not match" there would be
    inventing a mismatch — the same distinction `ReJudge.UNJUDGED` draws about a
    verdict a reader could not reach.
    """

    if sealed_from is None or claimed_version is None:
        return None
    matching = plans.get(claimed_version)
    if matching is None:
        return None
    return sealed_from == matching


def no_outcomes() -> dict[str, ReJudge]:
    """Typed empties, so a default and a missing answer are the same shape."""

    return {}


def no_reasons() -> dict[str, str]:
    return {}


def no_interpreters() -> dict[str, tuple[str, ...]]:
    return {}


def recorded_check_interpreters(directory: Path) -> tuple[str, ...]:
    """Which interpreter a repository check's own verdict says ran it.

    Empty is the answer "this bundle says nothing about an interpreter", and three
    shapes reach it: a session bundle, which has no check verdict at all; a verdict
    that cannot be read; and a verdict whose checks carry no command. None of them
    is "ran somewhere else", which is why the naming list below skips empties rather
    than treating them as mismatches.
    """

    path = directory / CHECK_VERDICT_NAME
    if not path.is_file():
        return ()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    if not isinstance(document, dict):
        return ()
    checks = cast("dict[str, object]", document).get("checks")
    if not isinstance(checks, list):
        return ()
    interpreters: set[str] = set()
    for check in cast("list[object]", checks):
        if not isinstance(check, dict):
            continue
        command = cast("dict[str, object]", check).get("command")
        if not isinstance(command, list) or not command:
            continue
        launched_by = cast("list[object]", command)[0]
        if isinstance(launched_by, str) and launched_by:
            interpreters.add(launched_by)
    return tuple(sorted(interpreters, key=os.path.normcase))


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
    #: Ledger rows the registry attests as SEALED whose bytes are not at that run id.
    #: Named for both halves of the question: the latest one is why a case blocks,
    #: an earlier one is retained failure material that has gone missing.
    sealed_without_bundle: tuple[Attempt, ...] = ()
    #: Which interpreter each repository check recorded as having run it, for the
    #: bundles that recorded one. The controlled image and a developer's virtualenv
    #: are two claims about one case, and the manifest's `environment` block cannot
    #: tell them apart because it describes the launcher rather than the check.
    check_interpreters: Mapping[str, tuple[str, ...]] = field(default_factory=no_interpreters)

    @property
    def outside_controlled_checks(self) -> tuple[str, ...]:
        """Repository-check bundles whose verdict records another interpreter.

        Compared against the interpreter the image contract pins, not against the
        one asking: inside one venv `/opt/minekin/bin/python` and its `python3`
        target are the same toolchain under two spellings, so a reader-relative
        comparison names every bundle in the image and reports that as a finding.
        A bundle that recorded no interpreter is absent from this rather than in it
        — an unanswerable question is not the answer "another one", which is how
        `from_another_build` treats a version this checkout has no recipe for.
        """

        pinned = os.path.normcase(CONTROLLED_CHECK_INTERPRETER)
        return tuple(
            sorted(
                run_id
                for run_id, interpreters in self.check_interpreters.items()
                if [os.path.normcase(item) for item in interpreters] != [pinned]
            )
        )

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

    def as_documents(
        self, *, repository_builds: Sequence[RecipeBuild] = ()
    ) -> list[dict[str, object]]:
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

        readable_plans = {
            build.minecraft: build.plan_sha256
            for build in repository_builds
            if build.plan_sha256 is not None
        }
        entries: list[dict[str, object]] = []
        for run_id, item in sorted(self.verifications.items()):
            manifest = item.manifest
            sealed_from = None if manifest is None else manifest.launch_plan_digest
            claimed_version = None if manifest is None else manifest.minecraft
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
                    # source it carried. Both are the bundle's own claim about itself,
                    # and the version claim is what selects the plan to compare it to.
                    "launch_plan_digest": sealed_from,
                    "bridge_digest": None if manifest is None else manifest.bridge_digest,
                    "minecraft": claimed_version,
                    # None when either side cannot answer: this checkout could not
                    # build a plan for that version, the bundle records no plan
                    # digest, or nothing here has a recipe for the version the bundle
                    # names. None of those is "came from somewhere else".
                    "from_repository_build": _build_agrees(
                        readable_plans, claimed_version, sealed_from
                    ),
                    # Reported per bundle for the reason the blocks are named per
                    # package: "this one disagreed" is only actionable if the reader
                    # can see which one, and what it disagreed about.
                    "re_judged": self.re_judged.get(run_id, ReJudge.NOT_ATTEMPTED).value,
                    "re_judge_reason": self.re_judge_reasons.get(run_id, ""),
                    # Which interpreter this bundle's own check verdict names as
                    # having run it. Empty for a bundle that records no such thing —
                    # every session bundle, and a check verdict that could not be read.
                    "check_interpreters": list(self.check_interpreters.get(run_id, ())),
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
    interpreters: dict[str, tuple[str, ...]] = {}
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
                recorded = recorded_check_interpreters(directory)
                if recorded:
                    interpreters[directory.name] = recorded
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
    has_bundle = set(verifications) | unreadable_run_ids
    sealed_without_bundle = tuple(
        attempt
        for attempt in attempts
        if attempt.status == "SEALED" and attempt.run_id not in has_bundle
    )
    return EvidenceOnDisk(
        verifications=verifications,
        unreadable=tuple(sorted(unreadable)),
        re_judged=outcomes,
        re_judge_reasons=reasons,
        attempts=attempts,
        sealed_without_bundle=sealed_without_bundle,
        check_interpreters=interpreters,
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
    builds = repository_builds()
    bundles = evidence.as_documents(repository_builds=builds)
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
            # The registry's own claims about bytes that are not there: which
            # attempts it attests as sealed while no bundle answers to that run id.
            "sealed_without_bundle": [
                {
                    "case_id": item.case_id,
                    "run_id": item.run_id,
                    "sequence": item.sequence,
                }
                for item in evidence.sealed_without_bundle
            ],
            # Which of the bundles were sealed from the build this checkout would
            # launch. Named rather than counted, for the same reason the blocks are:
            # "one of these is stale" is only actionable with the ids.
            "from_another_build": [
                cast(str, entry["run_id"])
                for entry in bundles
                if entry["from_repository_build"] is False
            ],
            # Which interpreter is answering the questions above: the one running
            # this report. Reported so a reader can tell where a reading was taken,
            # which is not the same fact as the two below.
            "reading_interpreter": sys.executable,
            # The interpreter a repository check has to record for this report to
            # believe it ran inside the controlled image.
            "controlled_check_interpreter": CONTROLLED_CHECK_INTERPRETER,
            # Repository-check bundles whose own verdict names some other
            # interpreter as having run the checks — the difference between a check
            # that ran inside the controlled image and one that ran from whoever's
            # virtualenv happened to be first on the path. Diagnostic, like the build
            # comparison, and for the same reason: where a bundle was made is a claim
            # it carries, and a reader can check it without this report agreeing.
            "repo_checks_not_from_the_controlled_interpreter": list(
                evidence.outside_controlled_checks
            ),
        },
        # The build this report is comparing against: one entry per reviewed version,
        # because a bundle is only comparable to the plan its own version launches
        # from. `unreadable` names the versions whose plan could not be built here —
        # for those the comparison says nothing, and an empty list is the answer
        # "every version was asked about", not "nothing disagreed". An explicit
        # statement that build identity is diagnostic only travels with it; per-case
        # attempt ordering is reported separately from this build comparison.
        "repository_build": {
            "builds": [build.as_document() for build in builds],
            "unreadable": [build.minecraft for build in builds if build.plan_sha256 is None],
            "gates_promotion": False,
        },
        "work_packages": packages,
        "overall": overall,
        # Named beside the two structures the gate is read from, never inside them:
        # what the seal format cannot answer, so a reader does not have to infer
        # that it cannot be answered. These statements block nothing — see each
        # entry's own `gates_promotion`.
        "visibility_gaps": [dict(gap) for gap in VISIBILITY_GAPS],
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
