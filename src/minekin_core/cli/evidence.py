"""Where one run's sealed evidence lives, and how it is checked afterwards.

`minekin evidence verify <run-id>` is the command that reads a bundle after the
fact, and the run id is the only thing it is given. So the bundle needs an
address a run id alone can produce, and it needs to be findable without being
told which Kin produced it: a bundle exists to be handed to someone else, and
the person checking it is usually not the person who ran it. The Kin directory
holds the identity, the ledger and the artifact cache; none of that is needed
to answer whether a bundle still holds up.

The address is therefore `run/evidence/<run-id>/`, under the run root the
launch plan's relative paths already resolve against (`cli.init.run_root`), and
the search walks every Kin under the data root rather than demanding a
selector. Two Kin holding one run id is refused instead of guessed at, because
a run id is a UUID: a collision means one of the two directories is not what it
says it is, and picking either would attribute one run's evidence to another.

A bundle is never written from here. Sealing is the run's own act, and a
verifier that could write is a verifier that could repair.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from minekin_core.adapters.evidence.bundle import verify_addressed_bundle
from minekin_core.cli.init import KIN_DIRECTORY, RUN_DIRECTORY
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.ids import RunId

EVIDENCE_DIRECTORY = "evidence"

#: Where the evidence of a check that belongs to no Kin lives: the repository's
#: own contracts are checked before there is any Kin, and by nothing that has an
#: identity or a world. It sits beside `kin/` rather than inside it, because
#: putting it under a Kin would mean naming one, and which Kin a repository check
#: belongs to is not a question that has an answer.
REPO_EVIDENCE_DIRECTORY = "repo-evidence"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "cli.evidence", "verify", ErrorCategory.CONFIG, Retryability.OPERATOR_ACTION, message
    )


def evidence_root(run_root: Path) -> Path:
    """Where this Kin's sealed bundles live, one directory per run."""

    return run_root / EVIDENCE_DIRECTORY


def bundle_directory(run_root: Path, run_id: str) -> Path:
    """The one address a run's bundle is sealed to, for the sealing side."""

    return evidence_root(run_root) / _checked_run_id(run_id)


def repository_root(root: Path) -> Path:
    """Where the repository's own checks seal their evidence."""

    return root / REPO_EVIDENCE_DIRECTORY


def repository_bundle_directory(root: Path, run_id: str) -> Path:
    """The one address a repository check's bundle is sealed to."""

    return repository_root(root) / _checked_run_id(run_id)


def candidate_roots(root: Path) -> tuple[Path, ...]:
    """Every evidence root under the data root, in a stable order.

    Both kinds are searched, and by the same rule: a run id is what names a
    bundle, so whoever is checking one — a Kin's run or a check of the repository
    itself — should not have to know which kind it was before looking.
    """

    kin_root = root / KIN_DIRECTORY
    from_kin = (
        sorted(path for path in kin_root.glob(f"*/{RUN_DIRECTORY}/{EVIDENCE_DIRECTORY}"))
        if kin_root.is_dir()
        else []
    )
    return tuple([*from_kin, repository_root(root)])


def locate_bundle(root: Path, run_id: str) -> Path:
    """The one bundle a run id names, refusing to guess between two."""

    identifier = _checked_run_id(run_id)
    found = [
        candidate / identifier
        for candidate in candidate_roots(root)
        if (candidate / identifier).is_dir()
    ]
    if not found:
        raise _reject(f"no evidence bundle for run {identifier} under {root}")
    if len(found) > 1:
        raise _reject(
            f"run {identifier} has {len(found)} bundles; a run id is unique, so this root is not"
        )
    return found[0]


def _checked_run_id(run_id: str) -> str:
    """Turn a run id into a path segment, or refuse to.

    The identifier rule is the one that produced the id in the first place, so
    this is a whitelist rather than a search for `..`: a run id is a UUID and a
    run id that is not one names no run.
    """

    try:
        return RunId(run_id).value
    except ValueError as error:
        raise _reject(f"{run_id!r} is not a usable run id") from error


@dataclass(frozen=True, slots=True)
class RunVerification:
    """What one run's evidence says about itself, re-derived rather than read."""

    run_id: str
    directory: str
    verified: bool
    sealed: bool
    bundle_digest: str | None
    result: str | None
    artifacts: int
    violations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "evidence verify",
            "status": "verified" if self.verified else "invalid",
            "run_id": self.run_id,
            "evidence_directory": self.directory,
            "verified": self.verified,
            # Reported apart from `verified` because they answer different
            # questions: the digest is the guarantee, the mode is a courtesy.
            "sealed": self.sealed,
            "bundle_digest": self.bundle_digest,
            "result": self.result,
            "artifacts": self.artifacts,
            "violations": list(self.violations),
        }


def verify_run(root: Path, run_id: str) -> RunVerification:
    """Check one run's bundle against itself, without trusting its manifest."""

    identifier = _checked_run_id(run_id)
    directory = locate_bundle(root, identifier)
    verification = verify_addressed_bundle(directory)
    manifest = verification.manifest
    return RunVerification(
        run_id=identifier,
        directory=str(directory),
        verified=verification.verified,
        sealed=verification.sealed,
        bundle_digest=verification.bundle_digest,
        result=None if manifest is None else manifest.result.value,
        artifacts=0 if manifest is None else len(manifest.artifacts),
        violations=verification.violations,
    )
