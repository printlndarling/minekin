"""V07: the automatic start decides, and every disagreement ends before a client moves.

The pieces this path composes are each tested where they live — the probe in V02, the
resolver's categories in V05, the digest gate and the installer in V06. What is under test
here is the ordering and the refusals the composition owns: three version facts that have
to agree, a store that may not be filled by accident, a target that may not move between
the two times it is asked, and an old client that has to be *shown* stopped before a new
one is offered. No test here starts a JVM, and none reaches the network: a fake transport
cannot serve bytes matching a reviewed pin, so "an empty store fills, then the client
launches" is the controlled runner's reading, not a unit test's.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import minekin_core.cli.auto_session as auto_session
from minekin_core import bootstrap as bootstrap_module
from minekin_core.adapters.launcher.fetch import ArtifactFetcher, FetchFailure
from minekin_core.adapters.launcher.orphans import Liveness, write_marker
from minekin_core.adapters.launcher.process import argument_digest
from minekin_core.adapters.launcher.provision import ProvisionReport
from minekin_core.adapters.launcher.supervisor import ProcessIdentity
from minekin_core.bootstrap import main, run
from minekin_core.cli.auto_session import (
    AutoBundleDecision,
    host_os_arch,
    prepare_auto_bundle_start,
    require_agreeing_facts,
)
from minekin_core.cli.parser import parse_args
from minekin_core.cli.session import session_overlay_path
from minekin_core.domain.errors import ErrorCategory, ExitCode, MinekinError
from minekin_core.domain.version_probe import ProbeObservation, ProbeOutcome
from minekin_core.domain.version_resolution import (
    RegistryEntry,
    ReviewedBundleRegistry,
    load_reviewed_registry,
    resolve,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPOSITORY_ROOT / "tests" / "fixtures" / "registry" / "reviewed-tested-bundles.json"
ID_1201 = "1.20.1-linux-x86_64-offline-java21"
ID_1214 = "1.21.4-linux-x86_64-offline-java21"
PROTOCOL_1201 = 763
PROTOCOL_1214 = 769

#: The target this path admits from its saved document before it asks anything: an
#: automatic run now reads the profile's address and version policy, so a test's target
#: has to name the version its fake reading answers. `TARGET_1214` is the same rule for
#: the other reviewed bundle.
TARGET = REPOSITORY_ROOT / "tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json"
TARGET_1214 = REPOSITORY_ROOT / "tests/fixtures/runtime-input/controlled-offline-server.json"

OURS_ARGV = ("java", "-jar", "ours.jar")
OURS_DIGEST = argument_digest(OURS_ARGV)
OURS_CMDLINE = b"\x00".join(arg.encode() for arg in OURS_ARGV)


def managed_target(tmp_path: Path, **overrides: object) -> Path:
    """The loopback 1.20.1 target with only the named fields changed."""

    document = json.loads(TARGET.read_text(encoding="utf-8"))
    document.update(overrides)
    path = tmp_path / "target.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def asks_nothing(path: Path) -> ProbeObservation:
    """A probe that fails the test: some refusals must come before the target is asked."""

    raise AssertionError(f"the target was probed: {path}")


def observation(
    protocol: int | None,
    version_text: str | None,
    *,
    outcome: ProbeOutcome = ProbeOutcome.OBSERVED,
) -> ProbeObservation:
    return ProbeObservation(
        outcome=outcome,
        profile_id="target-unit-01",
        profile_revision="revision-a",
        endpoint="target.invalid",
        resolution_chain=("target.invalid",),
        protocol=protocol,
        version_text=version_text,
    )


def entry(bundle_id: str = ID_1201) -> RegistryEntry:
    registry = load_reviewed_registry(json.loads(REGISTRY.read_bytes()))
    return registry.by_id()[bundle_id]


def probe_that_answers(readings: Sequence[ProbeObservation]) -> Callable[[Path], ProbeObservation]:
    """A target that says what it is told to say, once per asking.

    The last reading repeats, so a test that only expects one probe does not have to
    know how many the path makes.
    """

    asked: list[ProbeObservation] = list(readings)

    def answer(_path: Path) -> ProbeObservation:
        return asked.pop(0) if len(asked) > 1 else asked[0]

    return answer


def never_sleeps(seconds: float) -> None:
    return None


def alive(_pid: int) -> Liveness:
    return Liveness.ALIVE


def gone(_pid: int) -> Liveness:
    return Liveness.GONE


def marked_run_root(tmp_path: Path, *, pid: int = 4242, argv_digest: str = OURS_DIGEST) -> Path:
    root = tmp_path / "run"
    overlay = session_overlay_path(root, "session-old", 1)
    overlay.mkdir(parents=True)
    write_marker(
        overlay,
        identity=ProcessIdentity(
            pid=pid, started_at="2026-01-01T00:00:00Z", argv_digest=argv_digest
        ),
        session_id="session-old",
        generation=1,
    )
    return root


def cmdline(text: bytes | None) -> Callable[[int], bytes | None]:
    def read(_pid: int) -> bytes | None:
        return text

    return read


def recording_terminate(sink: list[int]) -> Callable[[int], None]:
    def terminate(pid: int) -> None:
        sink.append(pid)

    return terminate


#: What a pid whose command line cannot be read looks like — the platform denied it.
UNREADABLE_CMDLINE = cmdline(None)


@pytest.fixture
def filled_store(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stand in for the fetcher so the orchestration is testable without the network.

    Only the fill is replaced. What the plan names and what the store lacks is still read
    from disk, so a test cannot accidentally pass while the real store is empty.
    """

    seen: list[str] = []

    def fake_provision(plan: Any, store: Any, **_kwargs: Any) -> ProvisionReport:
        seen.append(str(plan["plan_sha256"]))
        return ProvisionReport(installed=("f" * 64,), reused=("e" * 64,), failed=())

    monkeypatch.setattr(auto_session, "provision_bundle", fake_provision)
    return seen


def prepare(
    tmp_path: Path,
    readings: Sequence[ProbeObservation],
    *,
    max_bytes: int | None = 4_000_000_000,
    liveness: Callable[[int], Liveness] = gone,
    read_cmdline: Callable[[int], bytes | None] = UNREADABLE_CMDLINE,
    terminate: Callable[[int], None] | None = None,
    run_root: Path | None = None,
    server_profile: Path = TARGET,
) -> AutoBundleDecision:
    asked: list[int] = []
    return prepare_auto_bundle_start(
        registry_path=REGISTRY,
        server_profile=server_profile,
        run_root=run_root or (tmp_path / "run"),
        max_bytes=max_bytes,
        os_arch="linux-x86_64",
        probe_target=probe_that_answers(readings),
        liveness=liveness,
        read_cmdline=read_cmdline,
        terminate=recording_terminate(asked) if terminate is None else terminate,
        sleep=never_sleeps,
    )


def test_the_resolved_bundle_and_its_recipe_are_what_gets_handed_off(
    tmp_path: Path, filled_store: list[str]
) -> None:
    decision = prepare(tmp_path, [observation(PROTOCOL_1201, "1.20.1")])

    assert decision.bundle_id == ID_1201
    assert decision.version_text == "1.20.1"
    assert decision.protocol == PROTOCOL_1201
    assert decision.recipe == REPOSITORY_ROOT / entry().recipe_path
    assert decision.plan["plan_sha256"] == entry().launch_plan_digest
    assert decision.stopped_pids == ()
    assert filled_store == [entry().launch_plan_digest]

    document = decision.as_document()
    assert document["kind"] == "auto-bundle-decision"
    assert document["status"] == "ready"
    # The endpoint is the operator's business, not part of the decision record.
    assert "endpoint" not in document


def test_the_other_reviewed_bundle_resolves_to_the_other_recipe(
    tmp_path: Path, filled_store: list[str]
) -> None:
    decision = prepare(
        tmp_path,
        [observation(PROTOCOL_1214, "1.21.4")],
        server_profile=TARGET_1214,
    )

    assert decision.bundle_id == ID_1214
    assert decision.recipe.name == "bundle-p0-core-1.21.4.json"


def test_a_protocol_no_reviewed_entry_covers_is_a_supply_chain_refusal(tmp_path: Path) -> None:
    with pytest.raises(MinekinError) as raised:
        prepare(tmp_path, [observation(1234, "1.5.2")])

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert "PROTOCOL_UNREGISTERED" in str(raised.value)


def test_a_target_that_could_not_be_read_does_not_become_a_launch(tmp_path: Path) -> None:
    for reading in (
        observation(None, None, outcome=ProbeOutcome.NO_RESPONSE),
        observation(None, None, outcome=ProbeOutcome.CACHE_EXPIRED),
        observation(None, None, outcome=ProbeOutcome.POLICY_REFUSAL),
        observation(None, None, outcome=ProbeOutcome.AMBIGUOUS),
    ):
        with pytest.raises(MinekinError) as raised:
            prepare(tmp_path, [reading])
        # None of these is a missing bundle: each is a target this run may not decide for.
        assert raised.value.category is ErrorCategory.ADMISSION, reading.outcome


def prepare_refusing(
    tmp_path: Path,
    filled_store: list[str],
    server_profile: Path,
    *,
    readings: Sequence[ProbeObservation],
) -> MinekinError:
    """Run the automatic start against one profile with the fill fenced off.

    How many times the read-only probe was reached is part of the reading: an unjoinable
    target has to be refused before a byte is sent to it, while a joinable one may be asked
    and still be refused for what its own document allows. Either way `filled_store` is the
    record of what the store saw, and the run root is where a store would have been built.
    """

    asked: list[Path] = []
    answer = probe_that_answers(readings)

    def count_and_answer(path: Path) -> ProbeObservation:
        asked.append(path)
        return answer(path)

    with pytest.raises(MinekinError) as raised:
        prepare_auto_bundle_start(
            registry_path=REGISTRY,
            server_profile=server_profile,
            run_root=tmp_path / "run",
            max_bytes=4_000_000_000,
            os_arch="linux-x86_64",
            # With no reading to give, the probe itself is the assertion: a row that must
            # be refused before a byte is sent has nothing to answer with.
            probe_target=count_and_answer if readings else asks_nothing,
            terminate=recording_terminate([]),
            sleep=never_sleeps,
        )
    assert len(asked) == len(readings)
    assert filled_store == []
    assert not (tmp_path / "run" / "artifact-store").exists()
    return raised.value


@pytest.mark.parametrize("host", ["198.51.100.20", "10.0.0.5"])
def test_a_target_this_run_may_not_join_is_refused_before_it_is_asked(
    tmp_path: Path, filled_store: list[str], host: str
) -> None:
    """A2 §3 X2 with the fix: the same profile the explicit path refuses in 2s (X1)."""

    error = prepare_refusing(
        tmp_path, filled_store, managed_target(tmp_path, host=host), readings=[]
    )
    assert error.category is ErrorCategory.ADMISSION
    assert error.exit_code == int(ExitCode.ADMISSION)
    assert "loopback" in str(error)


@pytest.mark.parametrize("host", ["0.0.0.0", "169.254.169.254", "224.0.0.1"])
def test_an_address_the_policy_blocks_is_refused_before_it_is_asked(
    tmp_path: Path, filled_store: list[str], host: str
) -> None:
    """A2 §1 F3: these three were already refused at profile loading, and still are."""

    error = prepare_refusing(
        tmp_path, filled_store, managed_target(tmp_path, host=host), readings=[]
    )
    assert error.category is ErrorCategory.ADMISSION
    assert "address policy" in str(error)


def test_a_target_that_lists_several_versions_is_refused_before_it_is_asked(
    tmp_path: Path, filled_store: list[str]
) -> None:
    """A2 §3 B2: the allowlist now decides, instead of the answer picking the bundle."""

    error = prepare_refusing(
        tmp_path,
        filled_store,
        managed_target(
            tmp_path,
            version_policy={
                "mode": "explicit_allowlist",
                "allowed_versions": ["1.20.1", "1.21.4"],
            },
        ),
        readings=[],
    )
    assert error.category is ErrorCategory.ADMISSION
    assert "exactly one version" in str(error)


def test_a_target_whose_allowlist_disagrees_with_the_answer_is_refused_before_the_fill(
    tmp_path: Path, filled_store: list[str]
) -> None:
    """A2 §3 B1: a 1.20.1 answer against a target that allows only 1.21.4.

    The probe does run here — the target is joinable and read-only to ask — but the
    profile's rule is what decides, and it decides before a single artifact is fetched.
    `test_the_resolved_bundle_and_its_recipe_are_what_gets_handed_off` is the paired
    reading: the same answer with a matching allowlist reaches the fill.
    """

    error = prepare_refusing(
        tmp_path,
        filled_store,
        managed_target(
            tmp_path,
            version_policy={"mode": "explicit_allowlist", "allowed_versions": ["1.21.4"]},
        ),
        readings=[observation(PROTOCOL_1201, "1.20.1")],
    )
    assert error.category is ErrorCategory.ADMISSION
    assert "allows 1.21.4" in str(error)


def test_a_store_that_is_short_without_a_declared_budget_refuses_before_fetching(
    tmp_path: Path,
) -> None:
    # Deliberately without the `filled_store` fixture: this is the real provision path,
    # and the refusal has to come from the budget rule rather than from a stub.
    with pytest.raises(MinekinError) as raised:
        prepare_auto_bundle_start(
            registry_path=REGISTRY,
            server_profile=TARGET,
            run_root=tmp_path / "run",
            max_bytes=None,
            os_arch="linux-x86_64",
            probe_target=probe_that_answers([observation(PROTOCOL_1201, "1.20.1")]),
            sleep=never_sleeps,
        )

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert "BUDGET_UNDECLARED" in str(raised.value)


def test_a_nonpositive_budget_is_a_named_refusal_before_anything_is_asked(
    tmp_path: Path, filled_store: list[str]
) -> None:
    """A2 §3.2 N2: `--max-bytes 0` and `-1` used to escape as a bare `ValueError`.

    The installer guarded it with an invariant, so the CLI answered `INTERNAL_INVARIANT`
    after the digest gate and the store scan. A non-positive budget is an operator
    mistake at the entry, so it must be named there: before the profile is read, before
    the target is asked (`asks_nothing` is the proof), and before the store is touched.
    """

    for budget in (0, -1):
        with pytest.raises(MinekinError) as raised:
            prepare_auto_bundle_start(
                registry_path=REGISTRY,
                server_profile=TARGET,
                run_root=tmp_path / "run",
                max_bytes=budget,
                os_arch="linux-x86_64",
                probe_target=asks_nothing,
                sleep=never_sleeps,
            )
        assert raised.value.category is ErrorCategory.CONFIG, budget
        assert str(raised.value).endswith("[BUDGET_NOT_POSITIVE]"), budget
        assert raised.value.exit_code == int(ExitCode.CONFIG)
    assert filled_store == []
    assert not (tmp_path / "run" / "artifact-store").exists()


def test_a_positive_budget_still_refuses_by_name_when_the_fill_outgrows_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The paired positive reading: `--max-bytes 1` was and stays a named refusal.

    A small positive budget is not a usage mistake — it is a deliberate authorisation
    the fill does not fit inside, so it ends where it always did: at the supply-chain
    budget rule, before the fetcher moves a byte.
    """

    def never_fetch(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the fetcher was reached")

    monkeypatch.setattr(ArtifactFetcher, "fetch", never_fetch)

    with pytest.raises(MinekinError) as raised:
        prepare_auto_bundle_start(
            registry_path=REGISTRY,
            server_profile=TARGET,
            run_root=tmp_path / "run",
            max_bytes=1,
            os_arch="linux-x86_64",
            probe_target=probe_that_answers([observation(PROTOCOL_1201, "1.20.1")]),
            sleep=never_sleeps,
        )

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert "over the 1 byte budget" in str(raised.value)
    # The store's empty skeleton may exist — the constructor creates it — but the
    # fetcher was never reached, so not one artifact was written into it.
    assert [path for path in (tmp_path / "run").rglob("*") if path.is_file()] == []


def test_the_command_refuses_a_nonpositive_budget_before_it_probes_or_installs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The same refusal through the real entry point, ordered before the probe.

    Nothing here answers a probe, so the exit code is what tells the two refusals
    apart: without the budget check this run would ask 127.0.0.1:25566 first and end
    `ADMISSION`, and only with it checked first does it end named `CONFIG` — with no
    artifact store created either way.
    """

    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv("MINEKIN_USERNAME", "kin_test")
    assert main(["init", "--kin-id", "kin-01"]) == int(ExitCode.OK)
    capsys.readouterr()

    code = main(
        [
            "session",
            "start",
            "--auto-bundle",
            str(REGISTRY),
            "--server-profile",
            str(TARGET),
            "--max-bytes",
            "0",
        ]
    )

    assert code == int(ExitCode.CONFIG)
    diagnostic = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert diagnostic["category"] == "CONFIG"
    assert diagnostic["message"].endswith("[BUDGET_NOT_POSITIVE]")
    assert [path for path in tmp_path.rglob("artifact-store") if path.is_dir()] == []


def test_a_budget_without_the_auto_bundle_entry_is_a_named_usage_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A2 §3.2 N2: `--max-bytes` beside `--profile` used to be accepted and ignored.

    The help text says the budget belongs to `--auto-bundle`, and the explicit path
    never read it. That is a request naming two entries at once, so it ends the way
    the missing-target case ends: one usage document, exit `USAGE`, nothing under the
    data root opened and no launch attempted.
    """

    stderr = io.StringIO()
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    code = run(
        [
            "session",
            "start",
            "--profile",
            str(tmp_path / "recipe.json"),
            "--max-bytes",
            "100",
        ],
        stderr=stderr,
    )

    assert code == int(ExitCode.USAGE)
    document = json.loads(stderr.getvalue())
    assert document["status"] == "usage"
    assert document["reason"] == "MAX_BYTES_WITHOUT_AUTO_BUNDLE"
    assert "--auto-bundle" in document["message"]
    assert list(tmp_path.iterdir()) == []


def test_the_explicit_entry_without_a_budget_still_reaches_the_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The paired positive control: `--profile` alone keeps its original meaning.

    The usage refusal must not swallow the explicit path it polices — a start that
    names its recipe and no budget still hands off to `start_and_supervise`.
    """

    handed: list[Path] = []

    def fake_start(**kwargs: Any) -> Any:
        handed.append(kwargs["profile"])
        raise AssertionError("the hand-off reached the supervisor")

    monkeypatch.setattr(bootstrap_module, "start_and_supervise", fake_start)
    monkeypatch.setattr(bootstrap_module, "data_root", lambda: tmp_path)
    monkeypatch.setattr(bootstrap_module, "java_executable", lambda: tmp_path / "java")

    with pytest.raises(AssertionError, match="supervisor"):
        bootstrap_module.run(
            ["session", "start", "--profile", str(tmp_path / "recipe.json")],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    assert handed == [tmp_path / "recipe.json"]


def test_an_incomplete_fill_is_a_supply_chain_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(*_args: Any, **_kwargs: Any) -> ProvisionReport:
        return ProvisionReport(
            installed=(),
            reused=(),
            failed=(
                FetchFailure(
                    coordinate="a:1",
                    url="https://example.invalid/a",
                    category=ErrorCategory.STORAGE,
                    reason="short read",
                ),
            ),
        )

    monkeypatch.setattr(auto_session, "provision_bundle", failing)

    with pytest.raises(MinekinError) as raised:
        prepare(tmp_path, [observation(PROTOCOL_1201, "1.20.1")])

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    assert "PROVISION_STORAGE" in str(raised.value)


def test_a_target_that_moves_between_the_two_asks_stops_the_start(
    tmp_path: Path, filled_store: list[str]
) -> None:
    killed: list[int] = []
    root = marked_run_root(tmp_path)

    with pytest.raises(MinekinError) as raised:
        prepare(
            tmp_path,
            [observation(PROTOCOL_1201, "1.20.1"), observation(PROTOCOL_1214, "1.21.4")],
            run_root=root,
            terminate=recording_terminate(killed),
        )

    assert raised.value.category is ErrorCategory.ADMISSION
    assert "TARGET_MOVED" in str(raised.value)
    # The old client is still the only one, because it was never asked to leave.
    assert killed == []


def test_a_recorded_client_that_cannot_be_proven_blocks_the_start(
    tmp_path: Path, filled_store: list[str]
) -> None:
    killed: list[int] = []
    for name, reader in (
        ("unreadable", cmdline(None)),
        ("reused-number", cmdline(b"someone-else\x00")),
    ):
        with pytest.raises(MinekinError) as raised:
            prepare(
                tmp_path,
                [observation(PROTOCOL_1201, "1.20.1")],
                run_root=marked_run_root(tmp_path / name),
                liveness=alive,
                read_cmdline=reader,
                terminate=recording_terminate(killed),
            )

        assert raised.value.category is ErrorCategory.PROCESS, name
        assert "OLD_CLIENT_UNPROVEN" in str(raised.value)
    # Unprovable is not a licence to signal anything.
    assert killed == []


def test_a_client_that_never_exits_within_the_window_blocks_the_start(
    tmp_path: Path, filled_store: list[str]
) -> None:
    killed: list[int] = []

    with pytest.raises(MinekinError) as raised:
        prepare(
            tmp_path,
            [observation(PROTOCOL_1201, "1.20.1")],
            run_root=marked_run_root(tmp_path),
            liveness=alive,
            read_cmdline=cmdline(OURS_CMDLINE),
            terminate=recording_terminate(killed),
        )

    assert raised.value.category is ErrorCategory.PROCESS
    assert "OLD_CLIENT_ALIVE" in str(raised.value)
    # It was ours and it was asked, once: this path does not escalate to a stronger signal.
    assert killed == [4242]


def test_the_switch_stops_the_proven_client_before_it_hands_off_a_recipe(
    tmp_path: Path, filled_store: list[str]
) -> None:
    killed: list[int] = []
    alive_once = iter([Liveness.ALIVE])

    def liveness(_pid: int) -> Liveness:
        return next(alive_once, Liveness.GONE)

    decision = prepare(
        tmp_path,
        [observation(PROTOCOL_1201, "1.20.1")],
        run_root=marked_run_root(tmp_path),
        liveness=liveness,
        read_cmdline=cmdline(OURS_CMDLINE),
        terminate=recording_terminate(killed),
    )

    assert killed == [4242]
    assert decision.stopped_pids == (4242,)
    assert decision.bundle_id == ID_1201


def test_the_digest_gate_runs_before_anything_is_fetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recipe that moved on disk is refused even though the store is empty.

    The budget question is only asked about a plan the entry actually vouches for.
    """

    called: list[str] = []

    def never_fetched(*_args: Any, **_kwargs: Any) -> None:
        called.append("fetch")

    monkeypatch.setattr(auto_session, "provision_bundle", never_fetched)

    registry = load_reviewed_registry(json.loads(REGISTRY.read_bytes()))
    broken = tuple(
        replace(item, recipe_digest="0" * 64) if item.bundle_id == ID_1201 else item
        for item in registry.entries
    )

    def vouches_wrongly(_path: Path) -> ReviewedBundleRegistry:
        return replace(registry, entries=broken)

    monkeypatch.setattr(auto_session, "load_registry", vouches_wrongly)

    with pytest.raises(MinekinError) as raised:
        prepare_auto_bundle_start(
            registry_path=REGISTRY,
            server_profile=TARGET,
            run_root=tmp_path / "run",
            max_bytes=4_000_000_000,
            os_arch="linux-x86_64",
            probe_target=probe_that_answers([observation(PROTOCOL_1201, "1.20.1")]),
            sleep=never_sleeps,
        )

    assert raised.value.category is ErrorCategory.SUPPLY_CHAIN
    # Naming the citation that moved, not a generic supply-chain stop.
    assert "not the reviewed" in str(raised.value)
    assert called == []


def test_three_version_facts_that_disagree_are_two_stable_refusals(tmp_path: Path) -> None:
    reviewed = entry()
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps({"minecraft": {"version": "1.21.4"}}), encoding="utf-8")

    with pytest.raises(MinekinError) as launched:
        require_agreeing_facts(
            observation=observation(PROTOCOL_1201, "1.20.1"),
            entry=reviewed,
            recipe=recipe,
        )
    assert launched.value.category is ErrorCategory.SUPPLY_CHAIN
    assert "LAUNCHED_VERSION_DISAGREES" in str(launched.value)

    with pytest.raises(MinekinError) as observed:
        require_agreeing_facts(
            observation=observation(PROTOCOL_1201, "1.19.4"),
            entry=reviewed,
            recipe=recipe,
        )
    assert observed.value.category is ErrorCategory.ADMISSION
    assert "RESOLVED_TEXT_DISAGREES" in str(observed.value)


def test_a_target_that_names_no_version_is_not_treated_as_a_disagreement(tmp_path: Path) -> None:
    """The resolver indexes on the protocol; this path does not tighten that judgement."""

    reviewed = replace(entry(), version_text="1.20.1")
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps({"minecraft": {"version": "1.20.1"}}), encoding="utf-8")

    require_agreeing_facts(
        observation=observation(PROTOCOL_1201, None), entry=reviewed, recipe=recipe
    )


def test_the_host_architecture_is_spelled_the_way_the_registry_spells_it() -> None:
    assert host_os_arch(system="Linux", machine="x86_64") == "linux-x86_64"
    # An arch with no tested bundle is the resolver's refusal to make, and it makes it:
    decision = resolve(
        load_reviewed_registry(json.loads(REGISTRY.read_bytes())),
        observation(PROTOCOL_1201, "1.20.1"),
        os_arch=host_os_arch(system="Darwin", machine="arm64"),
    )
    assert decision.status.value == "UNSUPPORTED"


def test_exactly_one_way_to_name_the_client_is_accepted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for argv in (
        ["session", "start"],
        ["session", "start", "--profile", "a.json", "--auto-bundle", "b.json"],
    ):
        with pytest.raises(SystemExit) as raised:
            parse_args(argv)
        assert raised.value.code == ExitCode.USAGE
    # The both case is refused by name at the parse boundary: the error says the two
    # entries exclude each other, so neither can win by precedence in silence.
    assert "not allowed with argument" in capsys.readouterr().err

    explicit = parse_args(["session", "start", "--profile", "a.json", "--server-profile", "s.json"])
    assert explicit.auto_bundle is None

    automatic = parse_args(["session", "start", "--auto-bundle", "b.json"])
    assert automatic.profile is None
    assert automatic.max_bytes is None

    # A positive budget beside the entry it bounds is legal and stays unperturbed.
    budgeted = parse_args(["session", "start", "--auto-bundle", "b.json", "--max-bytes", "4096"])
    assert budgeted.max_bytes == 4096


def test_an_automatic_start_with_no_target_is_a_usage_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The refusal is an exit code plus one document: an operator scripting a switch
    # has to be able to tell "you did not say which server" apart from a launch that
    # failed. `USAGE` rather than `CONFIG`, because no input document is wrong — the
    # freeze names the missing target a shape-of-request mistake, and nothing under
    # the data root is opened to find that out.
    stderr = io.StringIO()
    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    code = run(["session", "start", "--auto-bundle", str(REGISTRY)], stderr=stderr)
    assert code == int(ExitCode.USAGE)
    assert json.loads(stderr.getvalue())["status"] == "usage"
    assert list(tmp_path.iterdir()) == []


def test_the_command_refuses_an_unjoinable_target_before_it_installs_anything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A2 §3 X2 through the real entry point: named admission, and the store stayed 0.

    Nothing is injected here, so the reading is the operator's: the refusal is an exit code
    and one document, no artifact store was created under the data root, and the JVM hand-off
    below it was never reached.
    """

    monkeypatch.setenv("MINEKIN_HOME", str(tmp_path))
    monkeypatch.setenv("MINEKIN_USERNAME", "kin_test")
    assert main(["init", "--kin-id", "kin-01"]) == int(ExitCode.OK)
    capsys.readouterr()

    profile = managed_target(tmp_path, host="198.51.100.20")
    code = main(
        [
            "session",
            "start",
            "--auto-bundle",
            str(REGISTRY),
            "--server-profile",
            str(profile),
        ]
    )

    assert code == int(ExitCode.ADMISSION)
    diagnostic = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert diagnostic["category"] == "ADMISSION"
    assert "loopback" in diagnostic["message"]
    assert [path for path in tmp_path.rglob("artifact-store") if path.is_dir()] == []
