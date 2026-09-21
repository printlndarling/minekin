"""Refuse a workflow step that runs somebody else's code by a name that can move.

Every other thing this repository fetches is pinned by digest and renewed as a
reviewed act: the Gradle wrapper, the server jar, the Bridge jar, the buf CLI, the
fixtures, the case criteria. An action is the same kind of thing — code from outside,
run with this repository's token — and a release *tag* is a name its owner can move,
by accident or otherwise. A commit is not.

So a step's `uses:` must be `owner/repo@<40 hex>`, and it must carry the release it
came from in a comment beside it. The comment is not decoration: a bare commit is a
pin nobody can review, because there is no way to tell which release it was supposed
to be or whether a newer one exists. Both halves are required, and each is refused
with its own reason so a reader can tell which one is missing.

What this cannot check is that a commit exists — that needs the network, and a gate
that reaches out to check its own subject is a gate that fails for reasons that have
nothing to do with the commit under test. The workflow running is what checks that: a
step whose commit cannot be resolved fails before the action starts, which is why the
pins were resolved from the releases when they were written and why every push
re-checks them by running them.

This is a gate and not a parser. It reads lines, because this repository's workflows
are read by a YAML parser only in CI and nothing here should add a dependency to
check two dozen lines of them. The shape it looks for is a step's `uses:` — either
first after the list dash or on a line of its own — and the failure mode of reading
lines is that a line inside a `run:` block spelled exactly like one would be checked
too. That can only ever refuse something a person wrote on purpose.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPOSITORY_ROOT / ".github" / "workflows"

#: A step's `uses:`, with the release comment if there is one. The target is greedy up
#: to the comment rather than a run of non-space characters, because a computed action
#: is spelled with spaces in it (`${{ inputs.action }}`) and that is a case this has to
#: see in order to refuse it.
_USES = re.compile(r"^\s*-?\s*uses:\s*(?P<target>.*?)\s*(?P<comment>#.*)?$")

#: `owner/repo@<40 lowercase hex>`.
_PINNED = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

#: A local action, which is this repository's own code and moves with the checkout.
_LOCAL = "./"


@dataclass(frozen=True, slots=True)
class Finding:
    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}"


def violations(directory: Path) -> list[Finding]:
    """Every step in these workflows that runs an action by something that can move."""

    found: list[Finding] = []
    for workflow in sorted(directory.glob("*.y*ml")):
        text = workflow.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            match = _USES.match(line)
            if match is None:
                continue
            target = match.group("target")
            location = f"{workflow.name}:{number}"
            if target.startswith(_LOCAL):
                continue
            if "${{" in target:
                found.append(
                    Finding(location, f"{target} is computed at run time, so nothing can be pinned")
                )
                continue
            if not _PINNED.match(target):
                found.append(
                    Finding(
                        location,
                        f"{target} is not owner/repo@<40 hex commit> — a tag or a branch is a "
                        "name its owner can move, and this repository pins everything it runs",
                    )
                )
                continue
            if not match.group("comment"):
                found.append(
                    Finding(
                        location,
                        f"{target} records no release — say which one it is (`# v1.2.3`) so the "
                        "pin can be reviewed and renewed",
                    )
                )
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflows-dir",
        type=Path,
        default=WORKFLOWS,
        help="the workflows to scan (default: this repository's)",
    )
    arguments = parser.parse_args(argv)
    if not arguments.workflows_dir.is_dir():
        print(
            f"workflow pins: {arguments.workflows_dir} is not a directory — a gate that cannot "
            "find the workflows must not report them pinned",
            file=sys.stderr,
        )
        return 2
    found = violations(arguments.workflows_dir)
    if found:
        for finding in found:
            print(str(finding), file=sys.stderr)
        print(
            f"workflow pins: {len(found)} action(s) not pinned to a reviewed commit",
            file=sys.stderr,
        )
        return 1
    print("Workflow pins: OK (every action is a commit, and each names its release)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
