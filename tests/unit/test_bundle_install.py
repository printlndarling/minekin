"""Installing what one reviewed registry entry pins, and everything that refuses first.

The fetch machinery itself is tested in `test_provision.py` and
`test_artifact_fetch.py` against a small fake plan. What is under test here is the
entry in front of it: the digests that have to agree before a byte is requested,
and the fact that a half-finished install still does not satisfy `session start`.

A fake transport can never serve bytes matching a reviewed pin, so "an empty store
fills" is not provable here — that is the controlled runner's real run, and the
refusals below are what a unit test can actually show.
"""

from __future__ import annotations

import io
import json
import urllib.error
from dataclasses import replace
from pathlib import Path
from typing import BinaryIO

import pytest

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.fetch import ArtifactFetcher
from minekin_core.adapters.launcher.provision import (
    ProvisionReport,
    provision_bundle,
    require_reviewed_plan,
    reviewed_entry,
)
from minekin_core.bootstrap import main, run
from minekin_core.cli.session import require_store_complete
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError
from minekin_core.domain.version_resolution import BundleStatus, RegistryEntry

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPOSITORY_ROOT / "tests" / "fixtures" / "registry" / "reviewed-tested-bundles.json"
BUNDLE_ID = "1.20.1-linux-x86_64-offline-java21"


def _entry() -> RegistryEntry:
    return reviewed_entry(REGISTRY, BUNDLE_ID)


def _install(
    entry: RegistryEntry, store: ArtifactStore, *, fetcher: ArtifactFetcher, max_bytes: int
) -> ProvisionReport:
    """The composition `bundle install` performs: gate, then fetch under the budget."""

    return provision_bundle(
        require_reviewed_plan(entry), store, fetcher=fetcher, max_bytes=max_bytes
    )


def test_the_pinned_recipe_builds_the_pinned_plan() -> None:
    entry = _entry()
    plan = require_reviewed_plan(entry)

    assert plan["plan_sha256"] == entry.launch_plan_digest
    assert plan["launchable"] is True


def test_an_entry_that_is_not_tested_is_refused_however_its_digests_look() -> None:
    """The recipe calls itself a candidate and the entry calls itself tested.

    Only the entry's status is read, because the review's word is the authority —
    but a `candidate` entry has nothing to install even when its files are real.
    """

    entry = replace(_entry(), status=BundleStatus.CANDIDATE)

    with pytest.raises(MinekinError, match="not `tested`") as raised:
        require_reviewed_plan(entry)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_a_bundle_id_the_registry_does_not_name_is_refused_rather_than_guessed() -> None:
    with pytest.raises(MinekinError, match="is not an entry of the reviewed registry"):
        reviewed_entry(REGISTRY, "1.20.1-linux-x86_64-offline-java17")


def test_a_registry_that_cannot_be_read_says_so(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="is not readable UTF-8 JSON"):
        reviewed_entry(tmp_path / "absent.json", BUNDLE_ID)


def test_a_recipe_that_is_not_the_reviewed_bytes_is_refused_by_digest() -> None:
    entry = replace(_entry(), recipe_digest="0" * 64)

    with pytest.raises(MinekinError, match=r"digests to .*, not the reviewed") as raised:
        require_reviewed_plan(entry)

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN


def test_a_recipe_the_entry_does_not_ship_is_refused(tmp_path: Path) -> None:
    entry = replace(_entry(), recipe_path="tests/fixtures/runtime-input/removed.json")

    with pytest.raises(MinekinError, match="is not readable"):
        require_reviewed_plan(entry, workspace_root=tmp_path)


def test_a_plan_that_no_longer_matches_the_reviewed_one_is_refused() -> None:
    """What catches a recipe whose pins moved after the entry was written."""

    entry = replace(_entry(), launch_plan_digest="1" * 64)

    with pytest.raises(MinekinError, match="the launch plan built from"):
        require_reviewed_plan(entry)


def test_an_entry_citing_a_bridge_its_plan_does_not_carry_is_refused() -> None:
    entry = replace(_entry(), bridge_digest="2" * 64)

    with pytest.raises(MinekinError, match="carries bridge"):
        require_reviewed_plan(entry)


def test_the_budget_refuses_the_reviewed_job_before_a_single_request(tmp_path: Path) -> None:
    """The gigabyte-scale job is refused as a whole, not downloaded until it stops.

    The reviewed 1.20.1 plan is 3,639 artifacts and 738,432,269 bytes; a budget
    under that has to end the call before the first connection, or the budget
    gate would only be able to report a partial download.
    """

    asked: list[str] = []

    def opener(url: str, timeout: float) -> BinaryIO:
        del timeout
        asked.append(url)
        return io.BytesIO(b"")

    store = ArtifactStore(tmp_path / "store")
    fetcher = ArtifactFetcher(store, opener=opener)

    with pytest.raises(MinekinError, match="over the 100 byte budget"):
        _install(_entry(), store, fetcher=fetcher, max_bytes=100)

    assert asked == []


def test_an_install_that_could_fetch_nothing_leaves_session_start_refusing(
    tmp_path: Path,
) -> None:
    """Every counterexample ends in the same place: a half-filled store launches nothing.

    `max_attempts=1` because the retry schedule is not what is being shown here —
    that an upstream serving nothing leaves the store gate refusing is.
    """

    def opener(url: str, timeout: float) -> BinaryIO:
        del url, timeout
        raise urllib.error.URLError("no route to host")

    entry = _entry()
    store = ArtifactStore(tmp_path / "store")
    fetcher = ArtifactFetcher(store, opener=opener, max_attempts=1, jobs=1)

    report = _install(entry, store, fetcher=fetcher, max_bytes=10**12)

    assert not report.complete
    assert report.failed
    plan = require_reviewed_plan(entry)
    with pytest.raises(MinekinError, match="fetch them before starting a session"):
        require_store_complete(plan, store)


def _argv(store: Path, *extra: str) -> list[str]:
    return [
        "bundle",
        "install",
        "--registry",
        str(REGISTRY),
        "--bundle-id",
        BUNDLE_ID,
        "--max-bytes",
        "1",
        "--store",
        str(store),
        *extra,
    ]


def test_a_refusal_becomes_the_supply_chain_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = _argv(tmp_path / "store")
    argv[argv.index(BUNDLE_ID)] = "no-such-bundle"

    with pytest.raises(MinekinError) as raised:
        run(argv, stdout=io.StringIO(), stderr=io.StringIO())

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert main(argv) == int(ExitCode.SUPPLY_CHAIN)
    # `main` writes its diagnostic to the real streams; the exit code is the assertion.
    capsys.readouterr()


def test_a_dry_run_reports_the_reviewed_job_without_touching_the_network(
    tmp_path: Path,
) -> None:
    stdout = io.StringIO()
    code = run([*_argv(tmp_path / "store"), "--dry-run"], stdout=stdout, stderr=io.StringIO())

    document = json.loads(stdout.getvalue())
    assert code == int(ExitCode.OK)
    assert document["status"] == "planned"
    assert document["artifacts"] == 3639
    assert document["missing_bytes"] == 738432269
    assert document["plan_sha256"] == _entry().launch_plan_digest


def test_install_requires_its_budget_to_be_said_out_loud() -> None:
    """No default budget: the number is the authorisation, not a tunable."""

    with pytest.raises(SystemExit) as raised:
        run(["bundle", "install", "--registry", str(REGISTRY), "--bundle-id", BUNDLE_ID])

    assert raised.value.code == int(ExitCode.USAGE)
