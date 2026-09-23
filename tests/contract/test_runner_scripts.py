"""The runner's shell glue is evidence-bearing, so two silent failures are checked.

Both of these have already cost a verification run, and both fail in ways that
look like a conclusion about the code under test rather than a fault in the
harness:

* A CRLF line ending breaks `#!/usr/bin/env bash` into `bash\\r`, so the script
  dies before its first command with `No such file or directory` — while
  `bash -n script.sh` still reports it as syntactically fine, because a comment
  with a stray CR is a comment.
* An environment variable read into a local and then never used makes the
  feature it names silently absent. The entity collection run is the example:
  `MINEKIN_DOMAIN_SUMMON=minecraft:pig` was set, the variable was read, the tool
  was never told, and the client reported zero visible entities — which is
  exactly what a working entity path would report about an empty world.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[2] / "test-orchestrator" / "runner"
SCRIPTS = sorted(RUNNER.glob("*.sh"))

# `local="${ENV:-default}"` — the one shape the runner forwards an environment
# variable into a shell local. `${BASH_SOURCE[0]}` and `$(...)` assignments are
# deliberately not matched: they read no caller input.
_FORWARDED = re.compile(r'^([a-z_][a-z0-9_]*)="\$\{([A-Z_][A-Z0-9_]*):-', re.MULTILINE)


def test_the_runner_has_shell_scripts_to_check() -> None:
    assert SCRIPTS, f"no shell scripts under {RUNNER}"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_scripts_are_lf_and_keep_an_executable_shebang(script: Path) -> None:
    data = script.read_bytes()

    assert b"\r" not in data, f"{script.name} has CR; its shebang will not be found"
    assert data.startswith(b"#!/usr/bin/env "), f"{script.name} lost its shebang"
    assert data.split(b"\n", 1)[0].endswith(b"bash")


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_every_forwarded_environment_variable_is_actually_used(script: Path) -> None:
    text = script.read_text(encoding="utf-8")

    dead = [
        (local, env)
        for local, env in _FORWARDED.findall(text)
        if f'"${{{local}}}"' not in text and f'"${{{local}}}[@]"' not in text
    ]

    assert not dead, f"{script.name} reads and never passes on: {dead}"


def test_every_knob_the_harness_reads_is_one_the_wrapper_hands_it() -> None:
    """The other half of the same failure, one process boundary out.

    The test above catches a knob read inside a script and then dropped. This catches
    the one that never reaches the script at all: `docker run` passes an environment
    through only by naming it, so a knob `domain.sh` reads and `run.sh` does not name
    arrives **empty** — and `domain.sh` reads an absent knob as "not asked for", which
    is the same branch it takes when nobody asked for it.

    That failure is worse than the one above, because the run it produces is not red.
    It completes, seals a bundle and is evidence for a scenario that never happened:
    `MINEKIN_DOMAIN_ONLINE_MODE` is the only way to produce an online-mode mismatch
    (the tool derives the server's mode from the profile otherwise), so a dropped knob
    there is a bundle asserting a refusal the client was never able to make.

    Both directions, because they are different faults: a knob read and not delivered
    is a scenario that silently did not run, and one delivered and never read is a
    name the wrapper offers that nothing honours.
    """

    harness = (RUNNER / "domain.sh").read_text(encoding="utf-8")
    wrapper = (RUNNER / "run.sh").read_text(encoding="utf-8")

    read = set(re.findall(r"\$\{(MINEKIN_DOMAIN_[A-Z_]+)", harness))
    delivered = set(re.findall(r"-e\s+(MINEKIN_DOMAIN_[A-Z_]+)", wrapper))

    # A parse that found nothing would make both comparisons below vacuous, and this
    # is the one check that would keep passing if the runner were renamed.
    assert read, "no domain knobs found in domain.sh; this check would pass vacuously"
    assert read - delivered == set(), (
        f"domain.sh reads these and run.sh never delivers them: {sorted(read - delivered)}"
    )
    assert delivered - read == set(), (
        f"run.sh delivers these and nothing reads them: {sorted(delivered - read)}"
    )


def test_every_deadline_loop_gives_the_clock_a_chance_to_advance() -> None:
    """A budget measured in `SECONDS` around a body with no `sleep` is not a budget.

    Measured: the kill-core wait spun through its whole allowance in
    milliseconds, every iteration seeing nothing, and the wait after it then
    reported a fault injection that had never happened — because the hold
    expired on its own and the Kin stopped for that reason instead. `SECONDS`
    only advances while the shell is waiting for something.
    """

    domain = RUNNER / "domain.sh"
    lines = domain.read_text(encoding="utf-8").splitlines()
    checked = 0
    for index, line in enumerate(lines):
        if "for _ in $(seq 1" not in line:
            continue
        body: list[str] = []
        for following in lines[index + 1 :]:
            if following.strip() == "done":
                break
            body.append(following)
        # A `sleep` *statement*, not the word: the comment above the kill loop's
        # own sleep says the word, and a check that accepted it would pass with
        # the statement gone — which is how this test's first version was wrong.
        assert any(entry.strip().startswith("sleep") for entry in body), (
            f"the wait loop at {domain}:{index + 1} has no sleep, so its deadline never arrives"
        )
        checked += 1
    assert checked, "no wait loops found; this test is looking at the wrong file"


def test_the_domain_soak_is_bounded_and_fails_closed() -> None:
    """A requested baseline must measure both JVMs for the requested duration."""

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    assert 'case "${soak_seconds}" in' in text
    assert "MINEKIN_DOMAIN_SOAK_SECONDS must be a non-negative integer" in text
    assert 'case "${soak_interval}" in' in text
    assert "MINEKIN_DOMAIN_SOAK_INTERVAL must be a positive integer" in text
    assert "soak_interrupted=1" in text
    assert "final_client_process=" in text
    assert "final_world_process=" in text
    assert 'if [ "${sample_failed}" -eq 1 ] || \\' in text
    assert "the soak did not sample both JVMs on every pass" in text


def test_the_kill_paths_name_their_target_instead_of_guessing() -> None:
    """The two faults used to be aimed by a pattern match over the container.

    `pkill -f "minekin_core session start"` matched any Core in the container —
    including the `session stop` this script itself runs later — and
    `pgrep -P <tool> | head -1` named the tool's first child, which is not the
    JVM. Neither could say which process it had killed, so neither could be
    evidence that one had died.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    assert 'pkill -KILL -f "minekin_core session start"' not in text
    assert 'pgrep -P "${server_pid}"' not in text
    # The helper is what both faults go through, and its record is what the sealer
    # is given: a kill that is not recorded is not evidence of a kill.
    assert 'inject_fault "${session_pid}" "runtime_controller"' in text
    assert 'inject_fault "${server_pid}" "server_jvm"' in text
    assert "tools/inject_fault.py inject" in text
    assert "tools/inject_fault.py annotate" in text
    assert "--fault-injection" in text
    # A second fault in one run would leave two records and one sealable name.
    assert "this run asks for two faults at once" in text


def test_the_kill_paths_read_the_ledger_they_are_told_about() -> None:
    """One Kin's database must not be read as another's.

    The ledger is where the run id, the Kin and the session come from, and every
    answer downstream is about whichever one was read. Taking the first of a glob
    silently picks one of several; the count is checked instead.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    assert "ls -1 /data/kin/*/kin.sqlite3" not in text
    assert "ledgers=(/data/kin/*/kin.sqlite3)" in text
    assert 'if [ "${#ledgers[@]}" -ne 1 ]' in text
    assert "this run cannot name its ledger" in text
    # The run's own identity, read from the ledger rather than invented for the
    # record the helper writes.
    assert "SessionProcessStarted" in text
    assert "--kin-id" in text
    assert "--session-id" in text


def test_the_auth_mismatch_wait_reads_the_classification_and_not_the_exit() -> None:
    """`ADMIT-040` ends its wait on the fact the case is about, or it says so.

    The refusal is a ledger row the Bridge filtered, and nothing else the run leaves
    behind distinguishes it from a connection that dropped for a reason nobody
    classified: the client exits either way, and the server's log says nothing about
    the mode it demanded. So the wait asks for the phase, the category and the
    provenance together, within this run's own rows, and refuses to run at all when
    the harness did not start an online-mode server against an offline profile.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    assert 'if [ "${case_id}" = "ADMIT-040" ]; then' in text
    assert (
        "printf 'domain: ADMIT-040 requires an online-mode server and an offline Server "
        "Profile\\n'" in text
    )
    # The predicate: this run's rows only, and the classified refusal only.
    assert "position > ${baseline} and event_type='SessionInterrupted'" in text
    assert "source='BRIDGE' and trust_class='BRIDGE_FILTERED'" in text
    assert "json_extract(payload_json,'\\$.phase')='FAILED'" in text
    assert (
        "json_extract(payload_json,'\\$.reason')"
        "='ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH'" in text
    )
    # A generic `FAILED` is what the whitelist branch asks for, and the auth mismatch
    # branch may not fall back to it: that is the regression this case exists to catch.
    assert text.count("payload_json like '%FAILED%'") == 1
    assert "no classified auth mismatch was recorded within" in text


def test_the_resource_pack_wait_reads_the_policy_that_went_on_the_wire() -> None:
    """`ADMIT-060` ends its wait on the one line this case is about.

    A client that will not take a required pack says nothing: it sits in the login
    negotiation until Core's own deadline, which is the shape a dropped connection has
    too. The one thing that distinguishes the run is the row the Bridge reported about
    the policy the connection was made with, so the wait asks for that row — by its
    value, since a build that let the policy fall through to `prompt` would have written
    a row as well — and refuses to run at all when the harness served no pack.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    assert 'elif [ "${case_id}" = "ADMIT-060" ]; then' in text
    assert (
        "printf 'domain: ADMIT-060 requires a served resource pack and an offline Server "
        "Profile\\n'" in text
    )
    # The predicate is the one the case asserts: this run's rows only, the Bridge's own
    # filtered report, and the value the frozen profile named.
    assert "position > ${baseline} and event_type='ResourcePackPolicyApplied'" in text
    assert (
        "event_type='ResourcePackPolicyApplied' and source='BRIDGE' "
        "and trust_class='BRIDGE_FILTERED'" in text
    )
    assert "json_extract(payload_json,'\\$.resource_pack_policy')='deny'" in text
    assert "no denied resource pack policy was recorded within" in text
    # Existence is not the wait's question, so the row is not asked for unnamed.
    assert "json_extract(payload_json,'\\$.resource_pack_policy') is not null" not in text
