"""The test server runner must preserve the frozen isolation boundary."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import signal
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest

from minekin_core.adapters.launcher.server_profile import (
    SessionServerProfile,
    load_managed_target_profile,
    load_session_server_profile,
)
from minekin_core.domain.offline_identity import offline_player_uuid

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/run_controlled_server.py"


class _ServedPack(Protocol):
    url: str
    sha1: str


class _PackServer(Protocol):
    # Declared so the tests can construct one through the module: a protocol with no
    # constructor would type the call as taking no arguments.
    def __init__(self, payload: bytes) -> None: ...

    @property
    def served(self) -> _ServedPack: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...


class _Recipe(Protocol):
    version: str
    profile: Path
    jar_sha1: str
    jar_size: int
    resource_pack_format: int | None


class _Runner(Protocol):
    SERVER_RECIPES: dict[str, _Recipe]
    DEFAULT_SERVER_VERSION: str
    DEFAULT_ENABLE_STATUS: bool
    ResourcePackServer: type[_PackServer]

    def properties_for(
        self,
        profile: SessionServerProfile,
        *,
        level_seed: str,
        online_mode: bool | None = None,
        resource_pack: _ServedPack | None = None,
        enable_status: bool = False,
    ) -> dict[str, str]: ...

    def resource_pack_zip(self, pack_format: int) -> bytes: ...

    def write_configuration(
        self,
        directory: Path,
        properties: dict[str, str],
        *,
        allowed_players: tuple[str, ...],
    ) -> None: ...

    def verify_jar(self, path: Path, recipe: _Recipe) -> None: ...

    def status_switch_refusal(
        self,
        profile: SessionServerProfile,
        *,
        online_mode: bool | None,
        enable_status: bool,
    ) -> str | None: ...

    def read_back_enable_status(self, directory: Path) -> str: ...

    def summon_command(self, entity_type: str) -> str: ...
    def position_probe_command(self, player: str) -> str: ...
    def kill_command(self, player: str) -> str: ...

    def main(self) -> int: ...

    def request_clean_stop(self, signum: int, frame: object) -> None: ...


def _load_runner() -> _Runner:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        module: ModuleType = importlib.import_module("tools.run_controlled_server")
    finally:
        sys.path.pop(0)
    return cast(_Runner, module)


RUNNER = _load_runner()

#: The default recipe is the one every existing case names.
RECIPE = RUNNER.SERVER_RECIPES[RUNNER.DEFAULT_SERVER_VERSION]
#: Reviewed for this recipe alone; the other recipe has no reviewed pack format, which
#: is what `test_a_recipe_without_a_reviewed_pack_format_refuses_a_pack` holds.
PACK_FORMAT = cast("int", RECIPE.resource_pack_format)


def reviewed_profile() -> SessionServerProfile:
    """The default recipe's server, read through the door a session joins through."""

    return load_session_server_profile(RECIPE.profile, minecraft_version=RECIPE.version)


#: The anonymous stand-in for a join target outside the controlled domain: a
#: documentation-prefix address that stands for the operator's private server, whose
#: real endpoint lives only in an untracked profile and never in this repository.
NON_LOOPBACK_PROFILE = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "launcher" / "managed-remote-target-example.json"
)


class _StubServerProcess:
    """A JVM that is already gone by the time anything looks at it.

    The launch is the part of `main()` that needs a 54 MB artifact and a Java runtime,
    and it is not the part the status switch touches. Everything else — argument
    parsing, the refusal, the settings file, the reading back of it — runs for real.
    """

    pid = 0
    stdin = None
    returncode = 1

    def poll(self) -> int | None:
        return 1

    def wait(self, timeout: float | None = None) -> int:
        return 1

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None


def run_the_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *flags: str
) -> tuple[int, Path]:
    """Drive the tool's own `main()` to the point it would start a server.

    Two things are stood in for, both of them covered by their own tests elsewhere in
    this file: the pinned-jar digest check, which otherwise needs Mojang's artifact on
    disk, and the JVM. The stop-signal handlers are the tool's real ones and are put
    back afterwards, because the tool installs them into whatever process runs it.
    """

    directory = tmp_path / "run"

    def skips_the_jar_pin(path: Path, recipe: _Recipe) -> None:
        return None

    def starts_nothing(*args: object, **kwargs: object) -> _StubServerProcess:
        return _StubServerProcess()

    monkeypatch.setattr(RUNNER, "verify_jar", skips_the_jar_pin)
    monkeypatch.setattr(subprocess, "Popen", starts_nothing)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            TOOL,
            "--directory",
            str(directory),
            "--jar",
            str(tmp_path / "server.jar"),
            "--java",
            str(tmp_path / "java"),
            "--accept-eula",
            *flags,
        ],
    )
    saved_term = signal.getsignal(signal.SIGTERM)
    saved_int = signal.getsignal(signal.SIGINT)
    try:
        code = RUNNER.main()
    finally:
        signal.signal(signal.SIGTERM, saved_term)
        signal.signal(signal.SIGINT, saved_int)
    return code, directory


def written_status_line(directory: Path) -> str:
    """The `enable-status` line of the file the tool wrote, read by the test itself.

    Deliberately not through the tool's own reader: a report that checked the thing it
    reported would say nothing about whether the reader reads.
    """

    lines = (directory / "server.properties").read_text(encoding="utf-8").splitlines()
    found = [line.split("=", 1)[1] for line in lines if line.startswith("enable-status=")]
    assert len(found) == 1, f"one enable-status line, saw {found}"
    return found[0]


def test_server_properties_are_private_vanilla_survival() -> None:
    properties = RUNNER.properties_for(reviewed_profile(), level_seed="fixed-seed")

    assert properties["server-ip"] == "127.0.0.1"
    assert properties["online-mode"] == "false"
    assert properties["white-list"] == "true"
    assert properties["enforce-whitelist"] == "true"
    assert properties["gamemode"] == "survival"
    assert properties["force-gamemode"] == "true"
    assert properties["difficulty"] == "normal"
    assert properties["pvp"] == "true"
    assert properties["enable-rcon"] == "false"
    assert properties["enable-query"] == "false"
    assert properties["enable-command-block"] == "false"
    assert properties["broadcast-console-to-ops"] == "false"
    assert properties["level-seed"] == "fixed-seed"
    # A domain exists to be connected to, and vanilla's default of 60 seconds
    # pauses it while it waits — a paused server stops processing connections.
    assert properties["pause-when-empty-seconds"] == "0"


def test_the_served_pack_is_the_same_bytes_every_time() -> None:
    """Two runs must be one scenario.

    The URL handed to the server carries the pack's SHA-1, so a pack built with the
    time of the build would make every run a slightly different one, and the digest
    the client is asked to verify would move with the clock. That is the lesson the
    Bridge jar already taught about zip entries.
    """

    first = RUNNER.resource_pack_zip(PACK_FORMAT)
    second = RUNNER.resource_pack_zip(PACK_FORMAT)

    assert first == second
    # And the property that makes it true, rather than the symptom: two builds in the
    # same second are equal even when the timestamp is "now", so equality alone would
    # pass a pack that moved with the clock between two runs a second apart.
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert [entry.date_time for entry in archive.infolist()] == [(1980, 1, 1, 0, 0, 0)]


def test_the_served_pack_is_one_a_client_can_read() -> None:
    """A pack a client cannot parse would be refused for the wrong reason."""

    with zipfile.ZipFile(io.BytesIO(RUNNER.resource_pack_zip(PACK_FORMAT))) as archive:
        assert archive.namelist() == ["pack.mcmeta"]
        document = json.loads(archive.read("pack.mcmeta"))

    assert document["pack"]["pack_format"] == PACK_FORMAT


def test_the_pack_is_served_at_one_path_and_nothing_else_is() -> None:
    """One pack, one path: otherwise "the client fetched the pack" and "the client
    fetched something" are the same observation, and the case cannot say which of the
    two happened."""

    server = RUNNER.ResourcePackServer(RUNNER.resource_pack_zip(PACK_FORMAT))
    server.start()
    try:
        served = server.served
        with urllib.request.urlopen(served.url, timeout=5) as response:
            fetched = response.read()

        assert fetched == RUNNER.resource_pack_zip(PACK_FORMAT)
        assert hashlib.sha1(fetched).hexdigest() == served.sha1

        with pytest.raises(urllib.error.HTTPError) as refused:
            urllib.request.urlopen(served.url.replace("pack.zip", "other.zip"), timeout=5)
        assert refused.value.code == 404
    finally:
        server.stop()


def test_requiring_a_pack_changes_exactly_the_three_settings() -> None:
    """The scenario is three settings, not a different server."""

    profile = reviewed_profile()
    archive = RUNNER.resource_pack_zip(PACK_FORMAT)
    server = RUNNER.ResourcePackServer(archive)
    server.start()
    try:
        served = server.served
        without = RUNNER.properties_for(profile, level_seed="fixed-seed")
        with_pack = RUNNER.properties_for(profile, level_seed="fixed-seed", resource_pack=served)
    finally:
        server.stop()

    assert without["require-resource-pack"] == "false"
    assert without["resource-pack"] == "" and without["resource-pack-sha1"] == ""
    assert with_pack["require-resource-pack"] == "true"
    assert with_pack["resource-pack"] == served.url
    assert with_pack["resource-pack-sha1"] == hashlib.sha1(archive).hexdigest()
    assert {key for key in without if without[key] != with_pack[key]} == {
        "require-resource-pack",
        "resource-pack",
        "resource-pack-sha1",
    }


def test_an_offline_profile_can_meet_a_server_that_requires_sessions() -> None:
    """The one case where the two must disagree, and the switch that allows it.

    `online-mode` is derived from the profile's `auth_mode` so that every other run
    has the two agreeing — and that is also why no other run can produce the mismatch
    the contract asks to be classified as `AUTH_MODE_MISMATCH`. The product
    deliberately has no online-mode admission path, so the override belongs here, on
    the server the case starts, rather than in anything a profile can say.
    """

    profile = reviewed_profile()

    derived = RUNNER.properties_for(profile, level_seed="fixed-seed")
    forced = RUNNER.properties_for(profile, level_seed="fixed-seed", online_mode=True)
    refused = RUNNER.properties_for(profile, level_seed="fixed-seed", online_mode=False)

    assert derived["online-mode"] == "false", "this profile authenticates offline"
    assert forced["online-mode"] == "true"
    assert refused["online-mode"] == "false"
    # One setting, not a different server: everything else is what the profile implies.
    assert {key for key in derived if derived[key] != forced[key]} == {"online-mode"}


def test_configuration_whitelists_only_named_offline_players(tmp_path: Path) -> None:
    directory = tmp_path / "run"

    RUNNER.write_configuration(
        directory,
        RUNNER.properties_for(reviewed_profile(), level_seed="fixed-seed"),
        allowed_players=("Kin_One", "Fixture2", "Kin_One"),
    )

    whitelist = json.loads((directory / "whitelist.json").read_text(encoding="utf-8"))
    assert whitelist == [
        {"uuid": str(offline_player_uuid("Fixture2")), "name": "Fixture2"},
        {"uuid": str(offline_player_uuid("Kin_One")), "name": "Kin_One"},
    ]
    assert (directory / "eula.txt").read_text(encoding="utf-8").endswith("eula=true\n")
    assert json.loads((directory / "ops.json").read_text(encoding="utf-8")) == []


def test_configuration_never_overwrites_an_existing_run(tmp_path: Path) -> None:
    directory = tmp_path / "run"
    directory.mkdir()
    evidence = directory / "server.log"
    evidence.write_text("old evidence", encoding="utf-8")

    with pytest.raises(SystemExit, match="not empty"):
        RUNNER.write_configuration(directory, {}, allowed_players=())

    assert evidence.read_text(encoding="utf-8") == "old evidence"


def test_case_colliding_player_names_leave_no_run_directory(tmp_path: Path) -> None:
    directory = tmp_path / "run"

    with pytest.raises(SystemExit, match="differ only by case"):
        RUNNER.write_configuration(directory, {}, allowed_players=("Kin_One", "kin_one"))

    assert not directory.exists()


def test_unpinned_server_jar_is_rejected_before_launch(tmp_path: Path) -> None:
    jar = tmp_path / "server.jar"
    jar.write_bytes(b"not minecraft")

    with pytest.raises(SystemExit, match="not the pinned artifact"):
        RUNNER.verify_jar(jar, RECIPE)


def test_eula_must_be_explicit_before_the_directory_is_created(tmp_path: Path) -> None:
    directory = tmp_path / "run"
    result = subprocess.run(
        [
            sys.executable,
            TOOL,
            "--directory",
            str(directory),
            "--jar",
            str(tmp_path / "missing.jar"),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "must be accepted by the operator" in result.stderr
    assert not directory.exists()


def test_a_summon_is_a_console_line_and_never_a_second_command() -> None:
    """The console is a channel where an unchecked string is another command."""

    assert RUNNER.summon_command("minecraft:pig") == "summon minecraft:pig ~ ~ ~"
    assert RUNNER.summon_command("pig") == "summon pig ~ ~ ~"

    for injection in (
        "pig\nstop",
        "pig; stop",
        "pig `stop`",
        "pig\n",
        "Pig",
        "",
        "pig pig",
    ):
        with pytest.raises(SystemExit, match="not a vanilla entity id"):
            RUNNER.summon_command(injection)


def test_a_position_probe_is_a_console_line_and_never_a_second_command() -> None:
    """Same channel, same rule: the name is checked, not escaped."""

    assert RUNNER.position_probe_command("Kin") == "data get entity Kin Pos"
    assert RUNNER.position_probe_command("Kin_One") == "data get entity Kin_One Pos"

    # `1Kin` is deliberately not in this list: a leading digit is a perfectly
    # legal vanilla name, and a check that refused it would refuse real players.
    for injection in ("Kin\nstop", "Kin; stop", "Kin`stop`", "Ki n", "", "Kin\n", "ab"):
        with pytest.raises(SystemExit, match="not a vanilla player name"):
            RUNNER.position_probe_command(injection)


def test_a_kill_is_a_console_line_and_never_a_second_command() -> None:
    """The one release trigger a server can cause, and the same console rule."""

    assert RUNNER.kill_command("Kin") == "kill Kin"
    assert RUNNER.kill_command("Kin_One") == "kill Kin_One"

    for injection in ("Kin\nstop", "Kin; stop", "Kin`stop`", "Ki n", "", "Kin\n", "ab"):
        with pytest.raises(SystemExit, match="not a vanilla player name"):
            RUNNER.kill_command(injection)


def test_the_tool_takes_a_clean_stop_from_sigterm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SIGTERM, because the SIGINT this used to rely on never arrived.

    A background job of a non-interactive shell inherits SIGINT set to ignore —
    measured in the runner image — so `kill -INT` on the tool was a no-op and a
    domain run's server kept running until the container was killed. SIGTERM's
    default kills without saving. Both are now the clean stop.
    """

    saved = signal.getsignal(signal.SIGTERM)
    saved_int = signal.getsignal(signal.SIGINT)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            TOOL,
            "--directory",
            str(tmp_path / "run"),
            "--jar",
            str(tmp_path / "missing.jar"),
            "--accept-eula",
        ],
    )
    try:
        # The jar check is what fails, and it fails after the handlers are
        # installed: a tool that is killed while still starting up has to save
        # the world too.
        with pytest.raises(SystemExit, match="is missing"):
            RUNNER.main()
        assert signal.getsignal(signal.SIGTERM) is RUNNER.request_clean_stop
        assert signal.getsignal(signal.SIGINT) is RUNNER.request_clean_stop
    finally:
        signal.signal(signal.SIGTERM, saved)
        signal.signal(signal.SIGINT, saved_int)

    with pytest.raises(KeyboardInterrupt):
        RUNNER.request_clean_stop(signal.SIGTERM, None)


def test_each_reviewed_version_has_its_own_recipe() -> None:
    """A second version is a second review, not a reused constant."""

    assert set(RUNNER.SERVER_RECIPES) == {"1.21.4", "1.20.1"}
    assert RUNNER.DEFAULT_SERVER_VERSION == "1.21.4"

    recipes = [RUNNER.SERVER_RECIPES[version] for version in sorted(RUNNER.SERVER_RECIPES)]
    assert {recipe.jar_sha1 for recipe in recipes} == {recipe.jar_sha1 for recipe in recipes}, (
        "each recipe names its own digest"
    )
    assert len({recipe.jar_sha1 for recipe in recipes}) == len(recipes)
    assert len({recipe.profile for recipe in recipes}) == len(recipes)


def test_the_1201_recipe_is_a_loopback_offline_target_for_its_own_version() -> None:
    recipe = RUNNER.SERVER_RECIPES["1.20.1"]
    profile = load_session_server_profile(recipe.profile, minecraft_version=recipe.version)

    assert profile.auth_mode == "offline"
    assert profile.is_loopback
    assert profile.host == "127.0.0.1"
    other = RUNNER.SERVER_RECIPES["1.21.4"]
    frozen = load_session_server_profile(other.profile, minecraft_version=other.version)
    # A separate run, not the same server under a new name: two recipes that share a
    # port cannot both be up, and a shared profile would have left one version's
    # pin driving the other's launch.
    assert profile.port != frozen.port
    assert (profile.profile_id, frozen.profile_id) == (
        "p0-controlled-offline-loopback-1201",
        "p0-controlled-offline-loopback",
    )
    properties = RUNNER.properties_for(profile, level_seed="fixed-seed")
    assert properties["online-mode"] == "false"
    assert properties["server-ip"] == "127.0.0.1"
    assert properties["server-port"] == str(profile.port)


def test_a_recipe_without_a_reviewed_pack_format_refuses_a_pack() -> None:
    """No number is borrowed across versions: an unreviewed format is a refusal."""

    assert RUNNER.SERVER_RECIPES["1.20.1"].resource_pack_format is None


def test_the_reviewed_default_leaves_the_server_answering_no_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard that a sealed run's meaning rests on, asserted three ways.

    Every bundle this harness has started was started by a server that answered no
    status ping, so the default is not a style choice: move it and the settings file
    of a run replayed tomorrow stops being the file that run was sealed with. The
    named constant, the settings the builder returns when it is asked nothing, and
    the line a real run of `main()` puts on disk are checked separately, because any
    one of the three can move without the other two noticing.
    """

    assert RUNNER.DEFAULT_ENABLE_STATUS is False
    assert (
        RUNNER.properties_for(reviewed_profile(), level_seed="fixed-seed")["enable-status"]
        == "false"
    )

    code, directory = run_the_launcher(tmp_path, monkeypatch)
    assert code == 1, "the run reaches the launch rather than stopping early"
    assert written_status_line(directory) == "false"


def test_an_opt_in_run_answers_status_and_changes_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One named switch, one setting: the rest of the domain is what it always was."""

    profile = reviewed_profile()
    closed = RUNNER.properties_for(profile, level_seed="fixed-seed")
    opened = RUNNER.properties_for(profile, level_seed="fixed-seed", enable_status=True)

    assert opened["enable-status"] == "true"
    assert {key for key in closed if closed[key] != opened[key]} == {"enable-status"}

    code, directory = run_the_launcher(tmp_path, monkeypatch, "--enable-status")
    assert code == 1
    assert written_status_line(directory) == "true"


def test_the_status_reading_reported_is_the_file_s_own_and_not_the_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The report reads the settings file back, so it can disagree with the run.

    A tool that printed the argument it was handed would print the right word for a
    server that answers nothing and call it a reading. So the writer is stood in for
    one that leaves a different line on disk — which is exactly the shape of every way
    this could go wrong, from a stale directory to a switch that never reached the
    dict — and what the tool says is what the file says, not what was asked.
    """

    def writes_a_different_line(
        directory: Path, properties: dict[str, str], *, allowed_players: tuple[str, ...]
    ) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "server.properties").write_text("enable-status=true\n", encoding="utf-8")

    monkeypatch.setattr(RUNNER, "write_configuration", writes_a_different_line)

    code, directory = run_the_launcher(tmp_path, monkeypatch)
    reported = capsys.readouterr().out

    assert code == 1
    assert "asked for false" in reported
    assert "the settings written say true" in reported
    assert written_status_line(directory) == "true"


def test_the_reader_names_an_absent_line_as_unreadable(tmp_path: Path) -> None:
    """A missing setting is its own answer, and the same word the domain runner uses.

    Silently reading an absent line as `false` would make the one case a harness most
    needs to see — nobody wrote the switch at all — indistinguishable from the case it
    deliberately chose, and the domain runner already prints `unreadable` for it.
    """

    directory = tmp_path / "run"
    directory.mkdir()

    assert RUNNER.read_back_enable_status(directory) == "unreadable"
    (directory / "server.properties").write_text("gamemode=survival\n", encoding="utf-8")
    assert RUNNER.read_back_enable_status(directory) == "unreadable"
    (directory / "server.properties").write_text(
        "enable-status=false\nenable-status=true\n", encoding="utf-8"
    )
    # The last line is the one a starting server reads, so it is the one reported.
    assert RUNNER.read_back_enable_status(directory) == "true"


def test_opening_the_status_port_on_a_verifying_server_is_refused_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The refusal is a refusal to write, and it is reached from the real command line.

    `--online-mode` is the tool's own door to a server its client must never enter,
    and a status reply from that server advertises the join the case exists to refuse.
    So the two together stop with nothing on disk — a run directory is evidence, and a
    directory holding a setting nobody approved is the worst kind of it.
    """

    code, directory = run_the_launcher(tmp_path, monkeypatch, "--enable-status", "--online-mode")
    refused = capsys.readouterr().err

    assert code == 2
    assert "--enable-status asks the controlled server to answer a status ping" in refused
    assert "AUTH_MODE_MISMATCH" in refused
    assert not directory.exists()


def test_the_status_switch_is_gated_only_on_the_channel_it_would_widen(
    tmp_path: Path,
) -> None:
    """The address rule is the one the file already enforces, and only for the opt-in.

    Both profiles are read through the loaders that already stand between a run and
    its target, so this says nothing new about which address may be joined: it holds
    the loopback profile open — that is the whole point of the switch — and the
    non-loopback one shut against *widening*, while leaving a default run exactly as
    it was for both.
    """

    loopback = reviewed_profile()
    outside = load_managed_target_profile(NON_LOOPBACK_PROFILE)

    assert loopback.is_loopback
    assert not outside.is_loopback

    assert RUNNER.status_switch_refusal(loopback, online_mode=None, enable_status=True) is None
    for enable_status in (False, True):
        refused = RUNNER.status_switch_refusal(
            outside, online_mode=None, enable_status=enable_status
        )
        if enable_status:
            assert refused is not None
            assert "loopback-only" in refused
            assert "no LAN scan or DNS name" in refused
            # The address of the target itself is not repeated into the refusal: the
            # text lands in run logs, and a real target's endpoint belongs in the
            # operator's private profile, not in harness output.
            assert outside.host not in refused
        else:
            assert refused is None
