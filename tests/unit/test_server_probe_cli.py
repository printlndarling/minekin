from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from minekin_core.bootstrap import run
from minekin_core.cli.parser import parse_args
from minekin_core.cli.server_probe import load_profile_for_probe, probe_exit_ok
from minekin_core.domain.errors import ExitCode, MinekinError
from minekin_core.domain.version_probe import ProbeObservation, ProbeOutcome

V1_FIXTURE = Path("tests/fixtures/runtime-input/controlled-offline-server.json")
V2_FIXTURE = Path("tests/fixtures/launcher/managed-remote-target-example.json")


def test_server_probe_parses_with_a_profile_and_a_default_timeout() -> None:
    parsed = parse_args(["server", "probe", "--server-profile", "s.json"])

    assert parsed.command == "server"
    assert parsed.server_command == "probe"
    assert parsed.server_profile == "s.json"
    assert parsed.timeout_seconds == 5.0


def test_server_probe_requires_a_profile() -> None:
    with pytest.raises(SystemExit) as raised:
        parse_args(["server", "probe"])
    assert raised.value.code == ExitCode.USAGE


def test_the_probe_loader_dispatches_on_the_saved_schema_version() -> None:
    assert load_profile_for_probe(V1_FIXTURE).host == "127.0.0.1"
    assert load_profile_for_probe(V2_FIXTURE).host == "198.51.100.20"


def test_an_unversioned_profile_is_refused_before_any_socket(tmp_path: Path) -> None:
    path = tmp_path / "junk.json"
    path.write_text(json.dumps({"host": "127.0.0.1"}), encoding="utf-8")

    with pytest.raises(MinekinError, match="schema_version"):
        load_profile_for_probe(path)


def test_an_unknown_schema_version_names_the_version(tmp_path: Path) -> None:
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")

    with pytest.raises(MinekinError, match="99"):
        load_profile_for_probe(path)


def _observation(outcome: ProbeOutcome) -> ProbeObservation:
    return ProbeObservation(
        outcome=outcome,
        profile_id="p",
        profile_revision="r",
        endpoint="127.0.0.1:25565",
        resolution_chain=("saved:127.0.0.1:25565",),
    )


@pytest.mark.parametrize(
    ("outcome", "ok"),
    [
        (ProbeOutcome.OBSERVED, True),
        (ProbeOutcome.NO_RESPONSE, False),
        (ProbeOutcome.AMBIGUOUS, False),
    ],
)
def test_only_an_observed_version_exits_ok(outcome: ProbeOutcome, ok: bool) -> None:
    assert probe_exit_ok(_observation(outcome)) is ok


@pytest.mark.parametrize(
    ("outcome", "code"),
    [(ProbeOutcome.OBSERVED, ExitCode.OK), (ProbeOutcome.POLICY_REFUSAL, ExitCode.ADMISSION)],
)
def test_the_command_reports_the_observation_and_exits_by_it(
    monkeypatch: pytest.MonkeyPatch, outcome: ProbeOutcome, code: ExitCode
) -> None:
    def fake_run_probe(*_args: object, **_kwargs: object) -> ProbeObservation:
        return _observation(outcome)

    monkeypatch.setattr("minekin_core.bootstrap.run_probe", fake_run_probe)

    stdout = io.StringIO()
    result = run(
        ["server", "probe", "--server-profile", "s.json"],
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert result == int(code)
    document = json.loads(stdout.getvalue())
    assert document["command"] == "server probe"
    assert document["outcome"] == outcome.value
