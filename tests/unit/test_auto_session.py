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

import json
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import minekin_core.cli.auto_session as auto_session
from minekin_core.adapters.launcher.fetch import FetchFailure
from minekin_core.adapters.launcher.orphans import Liveness, write_marker
from minekin_core.adapters.launcher.process import argument_digest
from minekin_core.adapters.launcher.provision import ProvisionReport
from minekin_core.adapters.launcher.supervisor import ProcessIdentity
from minekin_core.bootstrap import main
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

#: A target of convenience. The automatic path never reads an address from here; it hands
#: this path to the probe, and the probe is the thing under test.
TARGET = Path("tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json")

OURS_ARGV = ("java", "-jar", "ours.jar")
OURS_DIGEST = argument_digest(OURS_ARGV)
OURS_CMDLINE = b"\x00".join(arg.encode() for arg in OURS_ARGV)


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
) -> AutoBundleDecision:
    asked: list[int] = []
    return prepare_auto_bundle_start(
        registry_path=REGISTRY,
        server_profile=TARGET,
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
    decision = prepare(tmp_path, [observation(PROTOCOL_1214, "1.21.4")])

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


def test_exactly_one_way_to_name_the_client_is_accepted() -> None:
    for argv in (
        ["session", "start"],
        ["session", "start", "--profile", "a.json", "--auto-bundle", "b.json"],
    ):
        with pytest.raises(SystemExit) as raised:
            parse_args(argv)
        assert raised.value.code == ExitCode.USAGE

    explicit = parse_args(["session", "start", "--profile", "a.json", "--server-profile", "s.json"])
    assert explicit.auto_bundle is None

    automatic = parse_args(["session", "start", "--auto-bundle", "b.json"])
    assert automatic.profile is None
    assert automatic.max_bytes is None


def test_an_automatic_start_with_no_target_refuses_before_touching_state(tmp_path: Path) -> None:
    # `main` rather than `run`, because the refusal is also an exit code: an operator
    # scripting a switch has to be able to tell "you did not say which server" apart
    # from a launch that failed.
    assert main(["session", "start", "--auto-bundle", str(REGISTRY)]) == int(ExitCode.CONFIG)
