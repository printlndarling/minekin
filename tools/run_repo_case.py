"""Running the checks a repository case declares, and reporting what they said.

A case whose assertions are all repository checks — versioned schemas, fixture
digests, no oracle references, no boundary violations — never starts a client,
so none of what a runtime case leaves behind exists for it: no run document, no
ledger, no world. What it has is the checks themselves, and this is the module
that performs them and says which held.

The names a case may use are the registry `check_case_assertions.py` maintains,
and that is not a coincidence: the file that guarantees a declared assertion has
an implementation is the same list this runs. A case cannot name a command here
that the registry does not already point at, which is what keeps a manifest from
being a way to run something.

It runs and does not seal. The verdict has the same shape as the one the runtime
asserter produces, so whatever seals a bundle records either kind of case
without having to know which it came from.

Exit codes: 0 every declared check held, 1 one of them did not, 2 could not run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

# The tools directory, so the registry can be imported whether this is run as
# `python tools/run_repo_case.py` or imported as `tools.run_repo_case`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_case_assertions import IMPLEMENTATIONS, Implementation
from minekin_core.domain.ids import RunId

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

EXIT_HELD = 0
EXIT_FAILED = 1
EXIT_UNRUNNABLE = 2

#: How much of a failing check's output travels with the verdict. Enough to say
#: what went wrong, and not the whole log: an artifact carries the whole thing.
DETAIL_LIMIT = 400
DEFAULT_TIMEOUT_SECONDS = 900


class Unrunnable(Exception):
    """The case cannot be run, and saying why is more useful than a traceback."""


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    """One declared assertion, the command that performs it, and what it said."""

    name: str
    kind: str
    target: str
    command: tuple[str, ...]
    exit_code: int | None
    held: bool
    detail: str
    #: The check's whole output, when the caller asked for it to be kept. None
    #: when nobody asked: the verdict carries the last words either way.
    output_path: Path | None = None

    def as_document(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "target": self.target,
            "command": list(self.command),
            "exit_code": self.exit_code,
            "held": self.held,
            "detail": self.detail,
            "output": None if self.output_path is None else str(self.output_path),
        }


@dataclass(frozen=True, slots=True)
class RepoVerdict:
    """Which assertions were expected, which held, and why the rest did not."""

    case_id: str
    #: The identity of this check run. Nothing else produces one — a repository
    #: check is not a managed run — so the thing that performs it names it, and
    #: the bundle is sealed at the address that name gives.
    run_id: str
    checks: tuple[CheckOutcome, ...]
    unimplemented: tuple[str, ...]

    @property
    def expected(self) -> tuple[str, ...]:
        return tuple(check.name for check in self.checks) + self.unimplemented

    @property
    def observed(self) -> tuple[str, ...]:
        return tuple(check.name for check in self.checks if check.held)

    @property
    def failures(self) -> tuple[str, ...]:
        failed = [
            f"{check.name}:CHECK_FAILED:exit {check.exit_code}"
            for check in self.checks
            if not check.held
        ]
        failed.extend(f"{name}:NO_IMPLEMENTATION" for name in self.unimplemented)
        return tuple(sorted(failed))

    @property
    def result(self) -> str:
        # An assertion nothing implements is not a failure of the case, it is the
        # absence of a check — and the same distinction the runtime verdict draws.
        if self.unimplemented or not self.checks:
            return "INCOMPLETE"
        return "FAIL" if self.failures else "PASS"

    def as_document(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "run repo case",
            "case_id": self.case_id,
            "run_id": self.run_id,
            "result": self.result,
            "expected": list(self.expected),
            "observed": list(self.observed),
            "failures": list(self.failures),
            "unimplemented": list(self.unimplemented),
            "checks": [check.as_document() for check in self.checks],
        }


def command_for(
    implementation: Implementation, *, root: Path, python: str = sys.executable
) -> tuple[str, ...]:
    """The command that performs one registered assertion."""

    if implementation.kind == "tool":
        return (python, str(root / implementation.target))
    file_name, _, test_name = implementation.target.partition("::")
    return (python, "-m", "pytest", "-q", "--no-header", f"{file_name}::{test_name}")


def _last_words(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:DETAIL_LIMIT]


def _keep(output: str, directory: Path | None, name: str) -> Path | None:
    """Keep one check's whole output, when a directory was named for it.

    The verdict carries the last words and the exit code; the whole output is an
    artifact, because a bundle is what someone else has to check later and a
    failing check's first line is often the one that says why.
    """

    if directory is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.log"
    path.write_text(output, encoding="utf-8")
    return path


def run_check(
    name: str,
    implementation: Implementation,
    *,
    root: Path,
    python: str = sys.executable,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    output_directory: Path | None = None,
) -> CheckOutcome:
    """Run one assertion's implementation, from the repository root."""

    command = command_for(implementation, root=root, python=python)
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CheckOutcome(
            name=name,
            kind=implementation.kind,
            target=implementation.target,
            command=command,
            exit_code=None,
            held=False,
            detail=f"the check did not finish within {timeout:g}s",
        )
    except OSError as error:
        return CheckOutcome(
            name=name,
            kind=implementation.kind,
            target=implementation.target,
            command=command,
            exit_code=None,
            held=False,
            detail=f"the check could not be started: {type(error).__name__}",
        )
    return CheckOutcome(
        name=name,
        kind=implementation.kind,
        target=implementation.target,
        command=command,
        exit_code=completed.returncode,
        held=completed.returncode == 0,
        detail=""
        if completed.returncode == 0
        else _last_words(f"{completed.stdout}\n{completed.stderr}"),
        output_path=_keep(f"{completed.stdout}\n{completed.stderr}", output_directory, name),
    )


def declared_assertions(case: Mapping[str, object]) -> tuple[str, ...]:
    value = case.get("assertions")
    if not isinstance(value, list):
        raise Unrunnable("the case manifest declares no assertions")
    return tuple(str(item) for item in cast(list[object], value))


def run_case(
    case: Mapping[str, object],
    *,
    registry: Mapping[str, Implementation] = IMPLEMENTATIONS,
    root: Path = REPOSITORY_ROOT,
    python: str = sys.executable,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    output_directory: Path | None = None,
    run_id: str | None = None,
) -> RepoVerdict:
    """Run every assertion the case declares, in the order it declares them."""

    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise Unrunnable("the case manifest names no case")

    outcomes: list[CheckOutcome] = []
    unimplemented: list[str] = []
    for name in declared_assertions(case):
        implementation = registry.get(name)
        if implementation is None:
            unimplemented.append(name)
            continue
        missing = implementation.missing_reason(root)
        if missing is not None:
            # Not run at all: a target that is not there would produce a failure
            # of the shell rather than a verdict about the repository.
            unimplemented.append(name)
            outcomes.append(
                CheckOutcome(
                    name=name,
                    kind=implementation.kind,
                    target=implementation.target,
                    command=(),
                    exit_code=None,
                    held=False,
                    detail=missing,
                )
            )
            continue
        outcomes.append(
            run_check(
                name,
                implementation,
                root=root,
                python=python,
                timeout=timeout,
                output_directory=output_directory,
            )
        )
    return RepoVerdict(
        case_id=case_id,
        run_id=run_id if run_id is not None else RunId.new().value,
        checks=tuple(outcomes),
        unimplemented=tuple(unimplemented),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the repository checks one case declares and report what they said."
    )
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=None,
        help="where to keep each check's whole output, one file per check",
    )
    args = parser.parse_args(argv)

    try:
        document = json.loads(args.case.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        failure = {"schema_version": 1, "status": "unrunnable", "message": str(error)}
        print(json.dumps(failure), file=sys.stderr)
        return EXIT_UNRUNNABLE
    if not isinstance(document, dict):
        print(
            json.dumps({"schema_version": 1, "status": "unrunnable", "message": "not an object"}),
            file=sys.stderr,
        )
        return EXIT_UNRUNNABLE

    try:
        verdict = run_case(
            cast(Mapping[str, object], document),
            root=args.root,
            timeout=args.timeout,
            output_directory=args.output_directory,
        )
    except Unrunnable as error:
        failure = {"schema_version": 1, "status": "unrunnable", "message": str(error)}
        print(json.dumps(failure), file=sys.stderr)
        return EXIT_UNRUNNABLE

    print(json.dumps(verdict.as_document(), sort_keys=True))
    if verdict.result == "PASS":
        return EXIT_HELD
    return EXIT_FAILED if verdict.result == "FAIL" else EXIT_UNRUNNABLE


if __name__ == "__main__":
    raise SystemExit(main())
