"""Reach a sealed bundle's verdict again, from the bytes it was sealed with.

`seal_run_evidence.py` asks the asserter for a verdict and seals the answer. The
bundle therefore records *that* a run passed; what it did not have, until now, was
everything needed to ask the same question a second time. A reader could check the
bytes held up — `minekin evidence verify` does exactly that — but could not check
that the bytes actually produce the verdict written over them. A bundle whose
`observed` list was edited to look like a pass, with the manifest and the digest
file regenerated to match, verified clean.

This is that second reading, and it is deliberately a tool rather than part of
`evidence verify`. The judgement lives in the test domain — the assertions read a
run's material and belong to no shipped product — and product code that imported
them would be a wheel that depends on `tools/`. So `evidence verify` keeps saying
what it can say, and this says the stronger thing where the judgement already lives.

Three things have to agree, and each is a different claim:

- the bytes are the bytes (`verify_addressed_bundle`, which `evidence verify` also
  runs), because a judgement about a bundle that does not hold up is nothing;
- the case this bundle names is the case in this repository, at the version it was
  sealed against — otherwise the criteria have moved and the old verdict is an
  answer to a question nobody is asking any more;
- the verdict those bytes produce now is the verdict recorded then, in every part:
  the result, which assertions were expected, which were observed, and why the rest
  failed.

A disagreement is reported the way everything else here is: as a stable reason and
the two values, so the reader can see which part moved rather than being told that
something did.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CASES = REPOSITORY_ROOT / "tests" / "fixtures" / "cases"

# The judgement and the reading of a sealed bundle both live beside this file, which
# is the whole reason this is a tool: the product must not import them.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from assert_case_evidence import (  # noqa: E402
    Unreadable,
    Verdict,
    evaluate,
    read_sealed_material,
)
from minekin_core.adapters.evidence.bundle import verify_addressed_bundle  # noqa: E402
from minekin_core.domain.cases import parse_case_manifest  # noqa: E402

EXIT_AGREES = 0
EXIT_DISAGREES = 1
EXIT_UNJUDGED = 2


class Unresolvable(Exception):
    """This bundle names a case this repository cannot judge it by."""


def load_case_document(cases_dir: Path, case_id: str) -> Mapping[str, object]:
    """The case manifest this bundle names, as the document the judge takes.

    Looked up by the identifier the bundle recorded rather than by a file name, so a
    fixture renamed on disk still resolves: what a bundle points at is a case, not a
    path in this repository.
    """

    matches: list[Mapping[str, object]] = []
    for path in sorted(cases_dir.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # `json.loads` answers `Any`, which under this repository's strict typing is a
        # value nothing can be said about; the shape is asked for once here.
        if (
            isinstance(document, dict)
            and cast("dict[str, object]", document).get("case_id") == case_id
        ):
            matches.append(cast("dict[str, object]", document))
    if not matches:
        raise Unresolvable(f"no case manifest in {cases_dir} declares {case_id}")
    if len(matches) > 1:
        raise Unresolvable(f"{len(matches)} case manifests declare {case_id}")
    return matches[0]


def _as_list(value: object) -> list[str]:
    return [str(item) for item in cast(list[object], value)] if isinstance(value, list) else []


def disagreements(recorded: Mapping[str, object], verdict: Verdict) -> list[str]:
    """Every part of the sealed verdict that these bytes do not reproduce."""

    found: list[str] = []
    if recorded.get("result") != verdict.result:
        found.append(f"RESULT:recorded={recorded.get('result')},re-judged={verdict.result}")
    for part, current in (
        ("expected", verdict.expected),
        ("observed", verdict.observed),
        ("failures", verdict.failures),
    ):
        sealed = _as_list(recorded.get(part))
        if sealed != list(current):
            found.append(f"{part.upper()}:recorded={sealed},re-judged={list(current)}")
    return found


def rejudge(bundle: Path, cases_dir: Path) -> dict[str, object]:
    """Re-judge one sealed bundle, or say why it cannot be re-judged."""

    verification = verify_addressed_bundle(bundle)
    if not verification.verified or verification.manifest is None:
        raise Unresolvable(
            "the bundle does not hold up, so there is nothing to re-judge: "
            + ", ".join(verification.violations)
        )
    manifest = verification.manifest
    document = load_case_document(cases_dir, manifest.case_id)
    definition, violations = parse_case_manifest(dict(document))
    if definition is None:
        raise Unresolvable(f"{manifest.case_id} is not a usable case: {violations}")
    if definition.digest != manifest.case_version:
        raise Unresolvable(
            f"this bundle was sealed against case version {manifest.case_version} and "
            f"{manifest.case_id} is now {definition.digest} — the criteria moved, so the "
            "recorded verdict answers a question this repository no longer asks"
        )

    material = read_sealed_material(bundle)
    verdict = evaluate(dict(document), material)
    recorded: dict[str, object] = {
        "result": manifest.result.value,
        "expected": list(manifest.assertions.expected),
        "observed": list(manifest.assertions.observed),
        "failures": list(manifest.assertions.failures),
    }
    return {
        "schema_version": 1,
        "command": "rejudge evidence",
        "run_id": manifest.test_run_id,
        "case_id": manifest.case_id,
        "case_version": manifest.case_version,
        "recorded": recorded,
        "re_judged": {
            "result": verdict.result,
            "expected": list(verdict.expected),
            "observed": list(verdict.observed),
            "failures": list(verdict.failures),
            "unimplemented": list(verdict.unimplemented),
        },
        "disagreements": disagreements(recorded, verdict),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("bundle", type=Path, help="the sealed bundle directory to re-judge")
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=CASES,
        help="where the reviewed case manifests are (default: this repository's)",
    )
    arguments = parser.parse_args(argv)
    try:
        report = rejudge(arguments.bundle, arguments.cases_dir)
    except Unresolvable as error:
        print(
            json.dumps({"schema_version": 1, "status": "unjudged", "message": str(error)}),
            file=sys.stderr,
        )
        return EXIT_UNJUDGED
    except Unreadable as error:
        print(
            json.dumps({"schema_version": 1, "status": "unreadable", "message": str(error)}),
            file=sys.stderr,
        )
        return EXIT_UNJUDGED
    disagreements_found = cast(list[str], report["disagreements"])
    if disagreements_found:
        report["status"] = "disagrees"
        print(json.dumps(report, sort_keys=True, indent=2))
        for item in disagreements_found:
            print(item, file=sys.stderr)
        print(
            f"rejudge evidence: the sealed verdict is not what these bytes produce "
            f"({len(disagreements_found)} part(s))",
            file=sys.stderr,
        )
        return EXIT_DISAGREES
    report["status"] = "agrees"
    print(json.dumps(report, sort_keys=True, indent=2))
    print(
        f"Rejudge evidence: OK ({report['case_id']} at {report['case_version']} — these bytes "
        "produce the verdict the bundle records)",
        file=sys.stderr,
    )
    return EXIT_AGREES


if __name__ == "__main__":
    raise SystemExit(main())
