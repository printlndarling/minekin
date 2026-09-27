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

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.server_profile import (
    MINECRAFT_VERSION,
    ManagedTargetProfile,
    ServerProfile,
    load_session_server_profile,
)
from minekin_core.domain.errors import MinekinError

RUNNER = Path(__file__).resolve().parents[2] / "test-orchestrator" / "runner"
SCRIPTS = sorted(RUNNER.glob("*.sh"))

# `local="${ENV:-default}"` — the one shape the runner forwards an environment
# variable into a shell local. `${BASH_SOURCE[0]}` and `$(...)` assignments are
# deliberately not matched: they read no caller input.
_FORWARDED = re.compile(r'^([a-z_][a-z0-9_]*)="\$\{([A-Z_][A-Z0-9_]*):-', re.MULTILINE)


#: The four names V1201-LAN-JOINER-BOUNDED-CONTROL-DRIVER-001 reads in `domain.sh` and
#: which `run.sh` does **not** deliver. Not a fix for this card to make: the wrapper is
#: outside its allowed paths, so a `run.sh domain` run cannot arm the joiner driver yet
#: and the joiner-control readings below are taken by driving the shipped shell region
#: directly. Pinned as an exact set by the parity check, so a fifth undelivered name —
#: or these four turning up in `run.sh` — goes red there instead of widening the hole.
JOINER_CONTROL_KNOBS = frozenset(
    {
        "MINEKIN_DOMAIN_JOIN_LOOK_YAW",
        "MINEKIN_DOMAIN_JOIN_LOOK_PITCH",
        "MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS",
        "MINEKIN_DOMAIN_JOIN_CONTROL_PRINT",
    }
)


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

    The one difference this check allows is named as an exact set, and it is allowed
    because the gap is the finding rather than a bug to paper over: the four
    joiner-control knobs are read on purpose, and `run.sh` cannot name them inside the
    card that added them. A live `run.sh domain` run therefore cannot arm the joiner
    driver yet — said in the validation record, and tested here by driving the shipped
    shell region rather than by a run that would arrive with the names empty.
    """

    harness = (RUNNER / "domain.sh").read_text(encoding="utf-8")
    wrapper = (RUNNER / "run.sh").read_text(encoding="utf-8")

    read = set(re.findall(r"\$\{(MINEKIN_DOMAIN_[A-Z_]+)", harness))
    delivered = set(re.findall(r"-e\s+(MINEKIN_DOMAIN_[A-Z_]+)", wrapper))

    # A parse that found nothing would make both comparisons below vacuous, and this
    # is the one check that would keep passing if the runner were renamed.
    assert read, "no domain knobs found in domain.sh; this check would pass vacuously"
    # The one registered exception is the set the check started from, and it is exact:
    # an empty difference would say the joiner-control knobs are delivered, and a wider
    # one would say nothing about how much wider. See `JOINER_CONTROL_KNOBS`.
    assert read - delivered == JOINER_CONTROL_KNOBS, (
        "domain.sh reads these and run.sh never delivers them (beyond the registered "
        f"joiner-control gap): {sorted(read - delivered - JOINER_CONTROL_KNOBS)}; "
        f"joiner-control gap as measured: {sorted(read & (read - delivered))}"
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


def test_a_killed_core_leaves_the_display_it_never_owned() -> None:
    """The runtime window's release line is written on the client's next tick.

    `bridge released N input(s) after IPC_LOST` comes out of the managed client JVM's
    tick loop, so it can only be written while that JVM still has a screen. Launching
    the session *inside* `xvfb-run` made the display die with the Core: `xvfb-run` owns
    the server and shuts it down from its own EXIT trap the moment its command child is
    SIGKILLed — measured at 6-7 ms — so that whole window was unwritable by construction,
    and a FAIL could not tell "the Bridge kept the key" from "the client never reached a
    tick." The harness therefore starts the server itself, hands the session only
    `DISPLAY`, and keeps the Core under a plain wrapper — the fault helper names the
    runtime controller by walking the descendants of `session_pid`, so the Core must stay
    one level below the held pid rather than becoming it.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The harness owns one server for the whole run and points the session at it.
    assert 'Xvfb "${session_display}" -screen 0 1280x720x24' in text
    assert 'export DISPLAY="${session_display}"' in text
    # It waits on the socket rather than trusting a sleep before anything connects.
    assert "/tmp/.X11-unix/X${display_no}" in text

    # The session is launched under a wrapper that cannot exec-replace itself into the
    # Core, so the runtime controller stays a descendant of the held pid.
    launch = '"${client_env[@]}" python -m minekin_core "$@" "${lan_args[@]}"'
    assert text.count(launch) == 1, "the session launch moved or doubled"
    head = text.index(launch)
    preceding = text[max(0, head - 80) : head]
    assert "minekin-session-supervisor" in preceding
    assert "xvfb-run" not in preceding, "the session went back inside its own X server"
    assert head < text.index("session_pid=$!")


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


def test_the_first_snapshot_refusal_is_asked_for_by_value_and_judged_by_core() -> None:
    """`ADMIT-070`'s injection knob is a boolean, and its success is Core's verdict.

    Two false positives this branch has to be unable to produce. The first is a run
    that was told `0` reading as a run that asked to be refused: a `[ -n ]` test
    makes an explicit `0` non-empty, so the harness waits for a refusal, records a
    request nobody made, and hands the operator a shape that looks like the scenario.
    The second is a run that ends its wait on what the client *printed*: a Bridge can
    say a sentence about a snapshot that never reached the IPC socket, and a log can
    rotate, while Core's own run document is the only record of what it refused. So
    the knob is cast with a `case`, the wait ends on this run's join row, and the
    outcome is judged from the run document and the ledger afterwards.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")
    wrapper = (RUNNER / "run.sh").read_text(encoding="utf-8")

    # The value is validated, and an unusable one stops the run rather than becoming
    # a default.
    assert 'refuse_first_snapshot="${MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT:-}"' in text
    assert '"" | 0 | false | 1 | true) : ;;' in text
    assert "MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT must be 1/true or 0/false" in text
    # And it is cast by name, not by emptiness.
    assert "refusal_asked=0" in text
    assert "    1 | true) refusal_asked=1 ;;\nesac" in text
    assert '[ -n "${refuse_first_snapshot}" ]' not in text
    # The wrapper hands the knob over, or the branch below is dead code.
    assert "-e MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT" in wrapper
    # The client only ever gets the name when the run asked for it.
    assert 'if [ "${refusal_asked}" -eq 1 ]; then\n    client_env=(' in text
    # One run, one record: a kill and a report request cannot share a bundle.
    assert 'if [ "${refusal_asked}" -eq 1 ] && [ "${faults}" -ge 1 ]; then' in text
    # The wait is the join, in this run's rows.
    assert 'elif [ "${refusal_asked}" -eq 1 ]; then' in text
    assert "position > ${baseline} and event_type='JoinObserved' limit 1;" in text
    assert "no join was recorded within" in text
    # The client's sentence is not the oracle, and its log is not guessed at.
    assert "first snapshot with authoritative=false" not in text
    # The request is recorded as a request, through the helper's own mode, and the
    # run fails unless the name was seen in the live client JVM's environment.
    assert "python /src/tools/inject_fault.py request \\" in text
    assert "--subject BRIDGE_FIRST_SNAPSHOT_AUTHORITY" in text
    assert 'json.load(open(sys.argv[1]))["effect"]["observed"]' in text
    # And the record is read back, in that same run, through the reader the sealer
    # uses — so the disclosure is shown to be judgeable rather than merely written.
    assert "import fault_injection" in text
    assert "fault_injection.read_record(Path(sys.argv[1])).document" in text
    # And what it is judged on is Core's refusal and the ledger's silence.
    assert '"NOT_AUTHORITATIVE" not in rejections' in text
    assert 'problems.append(f"SNAPSHOTS_ADMITTED:{admitted}")' in text
    assert 'if counted("PlayableEstablished") > 0' in text
    assert 'if counted("InputLeaseGranted") > 0' in text
    # The judgement also says when it is happy, so a transcript cannot be read as
    # "no problems" merely because the block never ran.
    assert 'print("domain: Core refused this run\'s first snapshot as asked")' in text
    assert 'elif [ -s "${request_path}" ]; then' in text


def test_a_run_whose_core_was_killed_is_still_named_by_the_ledger() -> None:
    """A killed Core prints nothing, and the wrapper's notice is not a run document.

    The seal branch used to ask "does the captured file have any bytes?" when the
    question is "did Core print its own document?". Those are different questions
    because the session runs inside `xvfb-run`, whose own command line is
    `"$@" 2>&1`: when the runtime controller — that wrapper's child — is SIGKILLed,
    the death notice arrives on the captured stream and leaves seven bytes that say
    nothing about what Core did. The guard then handed `Killed` to the sealer, which
    refused it, and the run could not be sealed at all. Measured in the container:
    killing only the inner python left the document file at exactly `Killed` and the
    wrapper's own stderr empty; killing the same child with no wrapper left both
    streams empty; and killing the wrapper together with the child — the shape the
    global `pkill -f` had before the identity binding — left the document file empty,
    which is why the fallback below had never been exercised since.

    The fix keeps the fault injection alone: the target is still named by identity,
    because naming it any other way would make `runtime_controller_sigkill_was_confirmed`
    assert a kill the harness never attributed.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # Emptiness is no longer the test the seal branch applies to that file.
    assert '[ ! -s "${subject_document}" ]' not in text
    # What it asks instead: is this Core's own run document, i.e. JSON that is an
    # object. A scalar or a notice parses as nothing, and "nothing" is the answer.
    assert "holds_run_document() {" in text
    assert 'if ! holds_run_document "${subject_document}"; then' in text
    assert "isinstance(document, dict)" in text
    # A file that is not a document leaves the run unnamed by document, named by the
    # id this run's own first ledger row carries.
    assert "named_run=(--run-id" in text
    # And the downgrade is said out loud: a bundle sealed without a document has to
    # be tellable, in the transcript, from a seal that quietly stopped looking.
    assert "holds no run document" in text
    # The kill itself is untouched: identity-bound, through the helper.
    assert 'inject_fault "${session_pid}" "runtime_controller"' in text
    assert 'pkill -KILL -f "minekin_core session start"' not in text


def test_the_run_named_by_the_ledger_also_names_the_kin_that_holds_it() -> None:
    """A run id says *which* run; it does not say *where*, and the volume no longer can.

    The seal branch that falls back to the ledger id used to leave the Kin for the
    sealer to work out, and the way it worked it out was to count the directories on
    the data root and accept the answer only when exactly one held a ledger. `kin-02`
    arrived with the join scenarios, so on a real volume that count is no longer one
    answer — and the harness, which reads the Kin out of this run's own rows for the
    fault attribution, had been holding the name all along without passing it.

    So the name is handed over on the branch that needs it, from the same reading the
    fault record is attributed by. The document branch is untouched: where Core left a
    document, its own word about its Kin is the one that counts.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The name comes from the ledger's rows, not from the path the database sits at.
    assert "read -r kin_id session_id generation" in text
    # And it travels with the fallback name, in the same array, so the two cannot be
    # handed over apart.
    assert 'named_run=(--run-id "${run_id}" --kin-id "${kin_id}")' in text
    # A run whose own rows say no Kin is said out loud rather than sealed blind.
    assert "has no Kin in its own rows" in text


def test_a_run_that_stops_at_a_named_supply_chain_refusal_exits_non_zero() -> None:
    """An auto run refused at a named frontier must not leave through rc 0.

    Measured red on the base bytes, in the controlled container with a lane volume
    that holds no store (`H1D: domain.sh rc=0`, `.tmp/h1d-red-live.log`): the session
    died at `BUDGET_UNDECLARED` — Core printed the named refusal on the run's stderr
    and its own process exited 17 — and `domain.sh` still exited 0, because the
    supervisor that holds the session was `sh -c '"$@"; :'`: the trailing `:` is the
    last command of the wrapper, so the wrapper exits with the no-op's status no
    matter what the Core it just waited on said. The `:` was written to keep the
    shell from exec-replacing itself into the Core (the fault helper walks
    `session_pid`'s descendants, so the Core must stay one level below), and it does
    that still — but it also swallowed the exit status, and that made "the run
    stopped early at a named supply-chain frontier" indistinguishable, by exit code
    alone, from "a client booted and the run rode out its bound". The V lane read
    this shape off a run; the same driver line run outside the supervisor answers
    non-zero (rc=17 measured above, and M's replay of the earlier early-stop shape
    gave rc=2), so the masking is the wrapper's and not the CLI's.

    The clauses below pin the shape of the fix and its two edges: the Core's status
    reaches `status`, the wrapper still cannot exec-collapse, and the harness learns
    nothing new — it propagates a number it was already holding, naming no refusal
    and judging nothing, so this is visibility and not a second verdict.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The swallowing form is gone, and its replacement ends in the Core's own status.
    assert "sh -c '\"$@\"; :' minekin-session-supervisor" not in text
    assert 'sh -c \'"$@"; session_rc=$?; exit "${session_rc}"\' minekin-session-supervisor' in text
    # The wrapper still runs statements after the Core, which is the only reason the
    # old form existed: without them `sh` exec-replaces itself and the fault helper
    # loses the descendant it names the runtime controller by.
    assert 'inject_fault "${session_pid}" "runtime_controller"' in text
    # And what `wait` collects is still the thing the script exits on — the seal
    # branch may override it for case runs by name, and nothing re-zeroes it elsewhere.
    assert 'wait "${session_pid}"\nstatus=$?' in text
    assert 'exit "${status}"' in text
    assert text.count("status=0") <= 1, "a second unconditional zero reappeared"
    # Visibility comes from the propagated number, not from a new classifier: the
    # harness still names no supply-chain refusal anywhere in its own text.
    assert "BUDGET_UNDECLARED" not in text
    assert "SUPPLY_CHAIN" not in text


#: The one command line that writes the joining client's LAN profile, with the two
#: lines that unpack its arguments. Pinned in full because the whole card is about
#: where line `minecraft_version` gets its value: a writer that still took two
#: arguments could not carry a run's version even if the dict entry were renamed.
JOINER_PROFILE_WRITER = (
    '    python - "${lan_port}" /tmp/domain-join-profile.json "${launched_version}" <<\'PY\'\n'
    "import json\n"
    "import sys\n"
    "\n"
    "port, path, version = int(sys.argv[1]), sys.argv[2], sys.argv[3]\n"
)

#: The named refusal immediately above that writer: the run stops when it cannot
#: name the version it launched, instead of handing the joiner a guessed one.
JOINER_VERSION_REFUSAL = (
    '    if [ -z "${launched_version}" ]; then\n'
    "        printf 'domain: the joining client must carry the version this run launched,"
    " and this run launched none it could name; refusing to write a joiner profile at a"
    " guessed version\\n' >&2\n"
    "        exit 2\n"
    "    fi\n"
)


def joiner_profile_version_comes_from_the_run(text: str) -> bool:
    """The joiner's profile carries the version this run launched, as an argument."""

    return (
        JOINER_PROFILE_WRITER in text
        and '"minecraft_version": version,' in text
        # The constant is banned script-wide as a dict entry, not just at the writer:
        # a second writer with the old default is the same defect one file later.
        # (A comment may still *name* the old constant — that is how the refusal
        # says what it refuses — but the byte with the trailing comma is a dict.)
        and '"minecraft_version": "1.21.4",' not in text
    )


def joiner_version_refusal_is_named(text: str) -> bool:
    """No version this run can name stops the run by name, before any profile exists."""

    gate = text.find(JOINER_VERSION_REFUSAL)
    writer = text.find(JOINER_PROFILE_WRITER)
    return (
        text.count(JOINER_VERSION_REFUSAL) == 1
        and text.count(JOINER_PROFILE_WRITER) == 1
        and -1 < gate < writer
    )


def test_the_joiner_profile_version_comes_from_the_run() -> None:
    """The second client's profile said 1.21.4 whatever the run had actually started.

    Measured on the base bytes in the controlled container, driving the block as the
    shipped script holds it (lines 728-745, extracted verbatim by `.tmp/h1f-joiner-probe.sh`
    and sourced with the run's own variables): with `launched_version=1.20.1` — the value
    the recipe read at the top of the same script would carry — the profile written to
    `/tmp/domain-join-profile.json` still said `"minecraft_version": "1.21.4"`, rc 0; and
    with `launched_version` empty (a bundle profile that names no readable recipe) it said
    the same. So a 1.20.1 server was joined by a client claiming 1.21.4, and the ⑤-family
    client endings (`GLFW 0x1000E`, `XDG_RUNTIME_DIR`) could be neither reproduced nor
    excluded on the 1.20.1 side — V's record of exactly that is what this replaces. After
    the change the same drives say: `1.20.1` in → `1.20.1` out, `1.21.4` in → `1.21.4` out,
    nothing in → the named refusal on stderr, rc 2, and no profile file written at all.

    The refusal shape is the one the script already uses for its other "this run cannot
    name it" frontiers (the auto+joiner refusal above the recipe read): said to stderr,
    `exit 2`, and — the part this card adds — with no constant left standing behind it to
    fall back to. A default would be the defect of the base bytes under a new name.

    The four profile fields that are not the version (`profile_id`, `host`, `port`,
    `auth_mode`) are pinned unchanged below, so "the version source moved" cannot be
    recorded as a quiet change to what the fixture dials. The auto+joiner refusal itself
    stays closed — this writer is reached only from the named-profile path, and the gate
    reads the same `launched_version` the server was started with.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The version reaches the profile as this run's value, through argv and nothing else.
    assert joiner_profile_version_comes_from_the_run(text)
    # And a run that cannot name its version says so by name and leaves no profile behind.
    assert joiner_version_refusal_is_named(text)

    # Same server, same claim: the value profiled is the value the controlled server was
    # started with. Both read the one variable the recipe produced at the top of the run.
    assert 'version_args=(--version "${launched_version}")' in text
    assert '"${version_args[@]}"' in text

    # The fields that are not the version, unchanged by this card, each exactly once
    # inside the joiner's own writer block (the script builds other documents too, and
    # this claim is about the one profile the joining client is handed).
    writer_head = text.index(JOINER_PROFILE_WRITER)
    writer_block = text[writer_head : text.index("\nPY\n", writer_head)]
    assert writer_block.count('"profile_id": "p0-lan-host-fixture",') == 1
    assert writer_block.count('"host": "127.0.0.1",') == 1
    assert writer_block.count('"auth_mode": "offline",') == 1
    assert writer_block.count('"port": port,') == 1
    assert writer_block.count('"schema_version": 1,') == 1
    assert writer_block.count('"visibility": "isolated_test_only",') == 1
    assert writer_block.count('"resource_pack_policy": "deny",') == 1

    # The profile is still written where the client's launch line reads it, and before
    # that line — the refusal can only stop a run that had not started a joiner yet.
    assert "/tmp/domain-join-profile.json" in text
    assert text.index(JOINER_VERSION_REFUSAL) < text.index(JOINER_LAUNCH_HEAD)

    # The refusal of an auto-bundle run with a joiner stays exactly as it was: this card
    # moved the version source under the named-profile path and did not open that door.
    assert "an auto-bundle run cannot also ask for a joining second client" in text
    assert text.count("cannot also ask for a joining second client") == 1


def test_the_joiner_version_contract_is_not_an_always_true_claim() -> None:
    """Reverse each half of the fix over the shipped bytes and its predicate goes false.

    `assert "launched_version" in text` would have passed on the base bytes too — the
    variable existed there, it just never reached the joiner's profile. So the two
    predicates the test above asserts are driven here over mutations, and RV-0 pins the
    shape difference against the base block itself: the base writer takes two arguments
    and its dict carries the comma-terminated constant, which is exactly what each
    predicate refuses.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")
    assert joiner_profile_version_comes_from_the_run(text)
    assert joiner_version_refusal_is_named(text)

    # RV-0: the base block, re-spliced in place of the shipped one — the red measurement
    # in predicate form. Both halves stop holding, and nothing else is deleted.
    base_writer = (
        "    python - \"${lan_port}\" /tmp/domain-join-profile.json <<'PY'\n"
        "import json\n"
        "import sys\n"
        "\n"
        "port, path = int(sys.argv[1]), sys.argv[2]\n"
    )
    back_to_base = text.replace(JOINER_PROFILE_WRITER, base_writer, 1).replace(
        '    "minecraft_version": version,\n', '    "minecraft_version": "1.21.4",\n', 1
    )
    assert back_to_base != text, "the shipped writer was not found to replace"
    assert not joiner_profile_version_comes_from_the_run(back_to_base)
    assert not joiner_version_refusal_is_named(back_to_base)

    # RV-1: the version is still passed, but the dict keeps a constant — the silent
    # fallback under a new name, which is the defect this card was written to kill.
    constant_kept = text.replace(
        '    "minecraft_version": version,\n',
        '    "minecraft_version": "1.21.4",\n',
        1,
    )
    assert constant_kept != text
    assert not joiner_profile_version_comes_from_the_run(constant_kept)

    # RV-2: the writer is fixed but the refusal is deleted — a run with no version now
    # writes a profile carrying the empty string, a claim about no world at all.
    without_gate = text.replace(JOINER_VERSION_REFUSAL, "", 1)
    assert without_gate != text
    assert not joiner_version_refusal_is_named(without_gate)
    assert joiner_profile_version_comes_from_the_run(without_gate), (
        "deleting the refusal also blinded the writer predicate: the two are supposed"
        " to be independent halves"
    )

    # RV-3: the refusal prints but falls through — `exit 2` gone, the named sentence
    # becomes a warning and the guessed profile is written right after it.
    warn_only = text.replace(
        JOINER_VERSION_REFUSAL,
        JOINER_VERSION_REFUSAL.replace("        exit 2\n", "", 1),
        1,
    )
    assert warn_only != text
    assert not joiner_version_refusal_is_named(warn_only)

    # RV-4: the gate stays but is moved below the writer — it can then only speak after
    # the profile it refuses to have written already exists.
    moved = text.replace(JOINER_VERSION_REFUSAL, "", 1).replace(
        JOINER_PROFILE_WRITER, JOINER_PROFILE_WRITER + JOINER_VERSION_REFUSAL, 1
    )
    assert moved != text
    assert not joiner_version_refusal_is_named(moved)
    assert joiner_profile_version_comes_from_the_run(moved)


# ---------------------------------------------------------------------------
# H1g — which reviewed shape the joining client is handed is decided by the version
# this run launched, and only by that.
# ---------------------------------------------------------------------------

#: The one branch the emitted shape turns on. v1 admission pins exactly one Minecraft
#: version (`server_profile.MINECRAFT_VERSION`), so a run whose client is not that
#: version cannot be served by a v1 document at all: its honest profile is refused at
#: `launcher.profile` before the joining client's JVM starts, which is the stop V's
#: readout named B1. The reviewed v2 managed target is the shape that carries a version
#: *policy* rather than a constant, and `load_session_server_profile` dispatches on the
#: saved `schema_version`. The literal is pinned against the constant it mirrors below,
#: because a dispatch that silently stopped matching it would hand the pinned route a
#: document its own admission refuses.
JOINER_V2_DISPATCH = 'if version != "1.21.4":\n'

#: The v1 document the pinned route has to keep emitting, byte for byte. Transcribed
#: from what the base bytes emit in the controlled image (sha256
#: 634abc28ac0c4652fd40f2e82867f632cf68b2354eccd7ba75c62c7f49148137); this test compares
#: the new bytes against it rather than recomputing it from the writer, so a control
#: that drifted would read red here and not "the same thing, differently written".
V1_JOINER_DOCUMENT = """{
  "schema_version": 1,
  "profile_id": "p0-lan-host-fixture",
  "host": "127.0.0.1",
  "port": 25570,
  "auth_mode": "offline",
  "minecraft_version": "1.21.4",
  "visibility": "isolated_test_only",
  "resource_pack_policy": "deny"
}
"""

#: That same frozen document, with only the version line carrying a run's version — the
#: base bytes' 1.20.1 profile (sha256 24eddf0a93521beadda25c6907841292493a94fdbbb5b12
#: 33fb32c6e9c51fc06), the one v1 admission refuses.
V1_JOINER_DOCUMENT_1201 = V1_JOINER_DOCUMENT.replace(
    '"minecraft_version": "1.21.4",', '"minecraft_version": "1.20.1",'
)

#: The v2 document a 1.20.1 run has to emit: the same loopback endpoint, port and
#: offline auth as the frozen fixture, the run's own version as the only entry of an
#: explicit allowlist, and an authorization whose basis attributes the target to this
#: controlled runner and to nothing else. Stated as a literal so the test names the
#: shape instead of trusting the writer's arithmetic.
V2_JOINER_DOCUMENT: dict[str, object] = {
    "schema_version": 2,
    "profile_id": "p0-lan-host-fixture",
    "host": "127.0.0.1",
    "port": 25570,
    "auth_mode": "offline",
    "version_policy": {"mode": "explicit_allowlist", "allowed_versions": ["1.20.1"]},
    "resource_pack_policy": "deny",
    "target_authorization": {
        "granted_by": "controlled-runner",
        "basis": (
            "the loopback world this controlled runner started for this very run; "
            "no address outside loopback and no operator-supplied target is named here"
        ),
    },
}


def with_change(document: dict[str, object], key: str, value: object) -> dict[str, object]:
    """One refused shape: the emitted target with a single field replaced."""

    mutated = dict(document)
    mutated[key] = value
    return mutated


def without_key(document: dict[str, object], key: str) -> dict[str, object]:
    """One refused shape: the emitted target with a required field absent."""

    mutated = dict(document)
    mutated.pop(key)
    return mutated


#: Each refused target document, the version its run launches, and the exact sentence
#: the loader says for it. Every one is raised inside `load_session_server_profile`,
#: which is the call `cli/session.py:1006` makes before anything is created, so each is
#: a refusal the joining client's JVM never gets past rather than a later fault. The
#: non-loopback entry is a TEST-NET-1 documentation address and is never contacted.
JOINER_V2_REFUSALS: dict[str, tuple[dict[str, object], str, str]] = {
    "empty-allowlist": (
        with_change(
            V2_JOINER_DOCUMENT,
            "version_policy",
            {"mode": "explicit_allowlist", "allowed_versions": []},
        ),
        "1.20.1",
        "server profile version_policy allowed_versions must not be empty",
    ),
    "version-mismatch": (
        dict(V2_JOINER_DOCUMENT),
        "1.21.4",
        "the session launches Minecraft 1.21.4, the target allows 1.20.1",
    ),
    "multi-entry-allowlist": (
        with_change(
            V2_JOINER_DOCUMENT,
            "version_policy",
            {"mode": "explicit_allowlist", "allowed_versions": ["1.20.1", "1.21.4"]},
        ),
        "1.20.1",
        "a managed session target must allow exactly one version, this one lists 1.20.1, 1.21.4",
    ),
    "non-loopback-host": (
        with_change(V2_JOINER_DOCUMENT, "host", "198.51.100.20"),
        "1.20.1",
        "a managed session may only join a loopback target; remote joining needs its "
        "own authorization card",
    ),
    "online-auth": (
        with_change(V2_JOINER_DOCUMENT, "auth_mode", "online"),
        "1.20.1",
        "v2 profiles have no online-mode admission path",
    ),
    "missing-target-authorization": (
        without_key(V2_JOINER_DOCUMENT, "target_authorization"),
        "1.20.1",
        "server profile is missing fields: target_authorization",
    ),
}


def joiner_profile_writer_source(text: str) -> str:
    """The joiner writer's Python, exactly as the shipped script holds it.

    The heredoc is extracted rather than retyped: what this test drives has to be the
    bytes the run executes, including the branch and the values it reads from the
    document above it.
    """

    head = text.index(JOINER_PROFILE_WRITER)
    body_end = text.index("\nPY\n", head)
    lines = text[head:body_end].splitlines(keepends=True)
    return "".join(lines[1:])


def run_joiner_profile_writer(
    source: str, tmp_path: Path, version: str, tag: str, port: int = 25570
) -> tuple[Path, bytes]:
    """Drive the shipped writer as its own process, the way the run's heredoc is driven."""

    work = tmp_path / tag
    work.mkdir(parents=True, exist_ok=True)
    script = work / "joiner-profile-writer.py"
    script.write_text(source, encoding="utf-8")
    emitted = work / "domain-join-profile.json"
    result = subprocess.run(
        [sys.executable, str(script), str(port), str(emitted), version],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"the writer exited {result.returncode}: {result.stderr}"
    assert emitted.exists(), "the writer produced no profile document"
    return emitted, emitted.read_bytes()


def as_document_text(data: bytes) -> str:
    """The writer's output as text, with the platform's line translation undone.

    The writer opens its output in the default text mode, so the newlines it writes are
    the host's — LF in the controlled image every real run uses, CRLF on a Windows
    checkout. The byte-for-byte control below is measured inside that image and quoted
    by digest in `docs/validation/`; here the same document is compared as content, so
    the claim stays checkable on either host instead of turning red on the separator.
    """

    return data.decode("utf-8").replace("\r\n", "\n")


def test_the_joiner_profile_shape_is_chosen_by_the_version_this_run_launched(
    tmp_path: Path,
) -> None:
    """A 1.20.1 run gets the reviewed v2 target; the 1.21.4 route keeps its v1 bytes.

    Measured in the controlled image against the real loader, on the base bytes
    (`domain.sh` = f8624ac6…): the joiner profile a 1.20.1 run wrote was a v1 document
    carrying `"minecraft_version": "1.20.1"` (sha256 24eddf0a…), and
    `load_session_server_profile(path, minecraft_version="1.20.1")` — the call
    `cli/session.py:1006` makes, with the version read from the very bundle the run was
    started from — refused it: `ADMISSION / launcher.profile / server profile
    minecraft_version is outside the pinned bundle`. The joining client's JVM never
    started, which is the only reason V's readout could not exclude the ⑤-family client
    endings for 1.20.1. The same drive over the new bytes loads the emitted document as
    a `ManagedTargetProfile` on 127.0.0.1, `offline`, with one allowed version equal to
    the launched one, and the real `session start` command line moves its first refusal
    off `launcher.profile` onto the artifact supply chain (rc 17 -> rc 11).

    The pinned route is a control, not a casualty: driving the same writer with
    `1.21.4` still emits the frozen v1 document byte for byte, and the version source
    H1f installed (`launched_version`, with the named refusal above the writer) is
    unchanged — this card moved which reviewed shape carries that version, never where
    the version comes from.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # One dispatch, and it sits under the refusal that guarantees a version to dispatch on.
    assert text.count(JOINER_V2_DISPATCH) == 1
    assert text.index(JOINER_VERSION_REFUSAL) < text.index(JOINER_V2_DISPATCH)
    # The branch mirrors the constant v1 admission enforces, rather than a copy of it.
    branch_at_the_product_constant = f'if version != "{MINECRAFT_VERSION}":\n'
    assert branch_at_the_product_constant == JOINER_V2_DISPATCH

    source = joiner_profile_writer_source(text)

    # Control group: the pinned version still gets the frozen v1 bytes, and still loads
    # through the v1 branch of the session loader.
    pinned_path, pinned_bytes = run_joiner_profile_writer(
        source, tmp_path, MINECRAFT_VERSION, "pinned"
    )
    assert as_document_text(pinned_bytes) == V1_JOINER_DOCUMENT
    pinned = load_session_server_profile(pinned_path, minecraft_version=MINECRAFT_VERSION)
    assert isinstance(pinned, ServerProfile)
    assert pinned.minecraft_version == MINECRAFT_VERSION

    # A run launched at anything else gets the reviewed v2 managed target instead.
    other_version = "1.20.1"
    managed_path, managed_bytes = run_joiner_profile_writer(
        source, tmp_path, other_version, "managed"
    )
    assert json.loads(managed_bytes) == V2_JOINER_DOCUMENT
    target = load_session_server_profile(managed_path, minecraft_version=other_version)
    assert isinstance(target, ManagedTargetProfile)
    assert target.host == "127.0.0.1"
    assert target.port == 25570
    assert target.is_loopback
    assert target.auth_mode == "offline"
    assert target.version_policy_mode == "explicit_allowlist"
    # The version the target names is the version this run launched, and it is the only
    # one it names: the document cannot carry a version the run did not start.
    assert target.allowed_versions == (other_version,)
    assert target.authorization_granted_by == "controlled-runner"

    # And the refusal this card answers still fires for the shape it was measured on: a
    # v1 document honestly saying 1.20.1 is not admitted, whatever the session loader
    # would make of a v2 one.
    legacy_path = tmp_path / "legacy"
    legacy_path.write_text(V1_JOINER_DOCUMENT_1201, encoding="utf-8")
    with pytest.raises(MinekinError) as legacy:
        load_session_server_profile(legacy_path, minecraft_version=other_version)
    assert legacy.value.component == "launcher.profile"
    assert (
        legacy.value.safe_message == "server profile minecraft_version is outside the pinned bundle"
    )

    # Neither shape is allowed to state a version the other does not: a v2 document
    # carries a version policy and no pinned field, so the v1 keys are not merely
    # unused, they are unreviewed and refused.
    mixed = with_change(dict(V2_JOINER_DOCUMENT), "minecraft_version", other_version)
    mixed_path = tmp_path / "mixed.json"
    mixed_path.write_text(json.dumps(mixed, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(MinekinError) as refused:
        load_session_server_profile(mixed_path, minecraft_version=other_version)
    assert refused.value.safe_message == "server profile has unreviewed fields: minecraft_version"


@pytest.mark.parametrize("case", sorted(JOINER_V2_REFUSALS))
def test_every_widened_joiner_target_is_refused_by_name(case: str, tmp_path: Path) -> None:
    """The six ways out of this card's narrow door each say which rule they broke.

    Loopback-only, offline-only and a single allowed version are the three rules that
    make the 1.20.1 door the same width as the old one, and each is read from the
    document rather than assumed: replacing the field it governs moves the refusal to
    that field's own sentence, at `launcher.profile`, before the joining client's JVM.
    The version-mismatch case is the honest-run case with a dishonest launch: a target
    naming 1.20.1 refused for a client launched at 1.21.4, which is the misjoin this
    module exists to make impossible.
    """

    document, launch_version, message = JOINER_V2_REFUSALS[case]
    path = tmp_path / f"{case}.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(MinekinError) as refusal:
        load_session_server_profile(path, minecraft_version=launch_version)

    assert refusal.value.component == "launcher.profile"
    assert refusal.value.safe_message == message


def test_the_joiner_version_dispatch_is_not_an_always_true_claim(tmp_path: Path) -> None:
    """Turn the dispatch off, invert it, or widen what it emits, and the readings go red.

    The green reading above is one branch and one field list, so it is worth exactly as
    much as these four mutations say it is: each keeps the writer, the heredoc and the
    version argument standing, and changes only the thing the claim is about.
    """

    source = joiner_profile_writer_source((RUNNER / "domain.sh").read_text(encoding="utf-8"))

    # RV-0: the dispatch never opens — every run gets a v1 document again, which is the
    # base bytes' behaviour and the base bytes' red.
    never = source.replace(JOINER_V2_DISPATCH, "if False:\n", 1)
    assert never != source
    never_path, never_bytes = run_joiner_profile_writer(never, tmp_path, "1.20.1", "rv-never")
    assert b'"schema_version": 1' in never_bytes
    with pytest.raises(MinekinError) as red:
        load_session_server_profile(never_path, minecraft_version="1.20.1")
    assert red.value.safe_message == "server profile minecraft_version is outside the pinned bundle"

    # RV-1: the branch inverted — the pinned route is the one handed a v2 document, so
    # the control group's frozen bytes are gone.
    inverted = source.replace(JOINER_V2_DISPATCH, 'if version == "1.21.4":\n', 1)
    assert inverted != source
    _, inverted_bytes = run_joiner_profile_writer(
        inverted, tmp_path, MINECRAFT_VERSION, "rv-invert"
    )
    assert b'"schema_version": 2' in inverted_bytes
    assert as_document_text(inverted_bytes) != V1_JOINER_DOCUMENT

    # RV-2: the allowlist widened to a second version — the loader refuses the run it
    # would otherwise have admitted, so the single-version rule is being read and not
    # decoration-written.
    widened = source.replace(
        '"allowed_versions": [version],',
        '"allowed_versions": [version, "1.21.4"],',
        1,
    )
    assert widened != source
    widened_path, _ = run_joiner_profile_writer(widened, tmp_path, "1.20.1", "rv-widen")
    with pytest.raises(MinekinError) as multi:
        load_session_server_profile(widened_path, minecraft_version="1.20.1")
    assert multi.value.safe_message == (
        "a managed session target must allow exactly one version, this one lists 1.20.1, 1.21.4"
    )

    # RV-3: the endpoint widened off loopback — refused by name, and refused before the
    # joining client exists.
    remote = source.replace('"host": profile["host"],', '"host": "198.51.100.20",', 1)
    assert remote != source
    remote_path, _ = run_joiner_profile_writer(remote, tmp_path, "1.20.1", "rv-remote")
    with pytest.raises(MinekinError) as loopback:
        load_session_server_profile(remote_path, minecraft_version="1.20.1")
    assert loopback.value.safe_message == (
        "a managed session may only join a loopback target; remote joining needs its own "
        "authorization card"
    )


def _pip_install_arguments(dockerfile: str) -> list[str]:
    """Each quoted argument handed to a `pip install`, across line continuations."""

    arguments: list[str] = []
    lines = dockerfile.splitlines()
    index = 0
    while index < len(lines):
        if "pip install" in lines[index]:
            block: list[str] = [lines[index]]
            while block[-1].rstrip().endswith("\\"):
                block.append(lines[index + len(block)])
            joined = " ".join(line.rstrip().removesuffix("\\").strip() for line in block)
            arguments.extend(argument for argument in re.findall(r'"([^"]+)"', joined))
            index += len(block)
        else:
            index += 1
    return arguments


def test_every_package_the_image_pip_installs_is_pinned_to_the_lock() -> None:
    """`/opt/minekin` carries only packages whose versions `uv.lock` resolves.

    The image hosts a test toolchain so repository-check cases can run inside
    the controlled environment (the Dockerfile comment says why). That is only
    honest while every pin here equals the lockfile the repository's own gates
    run against, and while nothing installs unpinned: a floating install on a
    sealing path is unreviewed code sealing evidence. This test reads both the
    Dockerfile and `uv.lock`, so the two drift apart only through a named edit.
    """

    dockerfile = (RUNNER / "Dockerfile").read_text(encoding="utf-8")
    arguments = _pip_install_arguments(dockerfile)
    assert arguments, "the Dockerfile installs nothing; did its shape change?"

    pinned: dict[str, str] = {}
    for argument in arguments:
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9._+!-]+)", argument)
        assert match is not None, f"pip argument {argument!r} is not an exact `name==version` pin"
        pinned[match.group(1).lower()] = match.group(2)

    lock = tomllib.loads((RUNNER.parents[1] / "uv.lock").read_text(encoding="utf-8"))
    locked = {str(package["name"]).lower(): str(package["version"]) for package in lock["package"]}

    for name, version in pinned.items():
        assert name in locked, f"{name} is installed by the image but resolved by no lock"
        assert version == locked[name], (
            f"the image pins {name}=={version} but uv.lock resolves {locked[name]}"
        )

    # The point of the layer: pytest is in the image, at the dev-group version.
    assert pinned.get("pytest") == locked["pytest"], "the image must carry a pinned pytest"

    # And pytest's own locked dependency closure is pinned here too, except the
    # ones that only exist on Windows: the image builds on Linux.
    pytest_package = next(
        package for package in lock["package"] if str(package["name"]) == "pytest"
    )
    for dependency in pytest_package.get("dependencies", []):
        if "win32" in str(dependency.get("marker", "")):
            continue
        name = str(dependency["name"]).lower()
        assert name in pinned, f"the image installs pytest but not its locked dependency {name}"


def test_an_auto_bundle_run_is_captured_named_and_otherwise_refused() -> None:
    """`session start --auto-bundle <registry>` used to scan as if it did not exist.

    The argument scan in `domain.sh` matched exactly four valued options, and an
    auto-bundle run fell through all of them: `profile` stayed empty, the derived
    server version stayed empty (so the server started at the tool's default
    version whatever the Server Profile allowed), and the seal branch handed the
    sealer `--profile ""`. Measured against the pre-change copy in the controlled
    container: the scan of an `--auto-bundle` argv yielded
    `profile=[] launched_version=[] version_args=[]`, and the sealer, called with
    the expansion that scan produces, refused with
    "is not a Server Profile the product accepts: the launcher profile is not
    readable UTF-8 JSON" (rc=2). Every clause below is measured red against that
    copy and green against the fixed script, and the positive control that the
    named recipe is accepted by the sealer reaches the same honest frontier as a
    hand-reviewed recipe (`no Kin is named for run ...`).
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The scan names the option, into a variable of its own.
    assert '--auto-bundle) auto_bundle="${argument}" ;;' in text
    # The two bundle sources cannot be mixed, and neither can an auto run borrow
    # the joiner block (which starts its second client from a named profile).
    assert "names both --profile and --auto-bundle" in text
    assert "cannot also ask for a joining second client" in text
    # An auto run's server version is read from the Server Profile it joins — the
    # single allowed version of a schema 2 profile or the pinned one of a schema 1
    # profile — and an ambiguous allow-list is refused by name rather than guessed.
    assert 'elif [[ -n "${auto_bundle}" && -n "${server_profile}" ]]; then' in text
    assert 'allowed = policy.get("allowed_versions") if isinstance(policy, dict) else None' in text
    assert "names no single version to start" in text
    # The seal names the required --profile from the run document's own recipe,
    # and a run whose document says nothing is reported unsealed rather than
    # sealed against a guessed profile.
    assert 'decision.get("recipe_path")' in text
    assert 'seal_profile_args=(--profile "${resolved_recipe}")' in text
    assert "names no readable recipe it resolved to" in text
    assert "seal_blocked=1" in text
    assert "no seal was attempted" in text
    # The sealer is no longer handed the bare scan variable at all: its call site
    # takes the named array (the joiner's own session start still names its
    # profile directly, and an auto run is refused before it can reach that).
    assert '"${seal_profile_args[@]}"' in text
    assert '--case "${case_file}" \\\n            "${seal_profile_args[@]}" \\' in text


def test_the_console_probe_is_a_default_and_the_status_switch_is_read() -> None:
    """Two readings a run could not have before, and no new verdicts.

    The first is the server-side account of where the Kin is. `data get entity`
    used to fire only in runs that had exported `MINEKIN_DOMAIN_PROBE` in advance,
    so a scenario that later wanted a reading had none: measured against the
    pre-change copy, the extracted construction yielded `PROBE ARGS: []` with no
    knob and `[--probe-player Kin --probe-every-seconds 5]` only with it. The
    asking is a default now, on the whitelisted account's name; what the knob
    still gates is every *judgement* that reads those lines, which is why the
    clause below pins both halves — the default and the untouched gate.

    The second is `enable-status`. The auto path resolves and observes its target
    through the vanilla status endpoint, and the controlled server tool writes
    `enable-status=false` into every run directory (measured: the product probe
    against such a server says `NO_RESPONSE`, rc 17, while the same bytes with
    only that one switch flipped say `OBSERVED`). `domain.sh` now prints the
    switch read back from the run directory's own settings file — measured to
    print `false` for the tool-written directory and `true` for the flipped
    positive control — and stops an auto-bundle run whose server cannot answer,
    by name, before a client is started into a join that can never be observed.
    Flipping the switch itself belongs to `tools/run_controlled_server.py`,
    outside this harness's surface, and is registered for its own card.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The probe is built unconditionally, defaulting to the whitelisted account.
    assert (
        'probe_args=(--probe-player "${probe:-${player}}" '
        '--probe-every-seconds "${probe_seconds}")' in text
    )
    assert 'probe_args=()\nif [[ -n "${probe}" ]]; then' not in text
    # And the judgement gate that reads those lines is still the knob, unchanged.
    assert '[[ -n "${probe}" && "${hold_requested}" -eq 1' in text
    # The status switch is read from the server's own settings and printed.
    assert "s/^enable-status=//p" in text
    assert "printf 'domain: the controlled server reports enable-status=%s\\n'" in text
    # An auto run whose server cannot answer stops by name, before the client.
    assert 'if [ -n "${auto_bundle}" ] && [ "${enable_status}" != "true" ]; then' in text
    assert "the auto path needs this server to answer status" in text


def test_the_auto_path_hands_the_status_opt_in_to_the_controlled_launcher() -> None:
    """The knob registered by the tools card is now asked for by the caller that needs it.

    `tools/run_controlled_server.py` stopped hard-coding `enable-status=false` and made
    answering a status ping a named opt-in (`--enable-status`), read back off the disk
    before it reports. The auto path is exactly the caller the switch names: resolving
    and observing the bundle target goes through the vanilla status endpoint. Until
    this wiring the end-to-end `--auto-bundle` run could not clear the harness's own
    readiness check by construction — measured on the base script inside the controlled
    container: a real 1.21.4 JVM came up ready, `domain.sh` read back
    `enable-status=false`, and the run stopped by name with rc=2 before a client was
    started (`/data/server-runs/run-1/server.properties` said the same off the disk).

    Every clause below is measured red against that base copy and green against the
    wired script, and each of the two ways the wiring could silently degrade — the
    switch handed to every run, the switch dropped again — names the assertion it
    breaks. The last two clauses are the surviving guard: the reading is taken from
    the run directory's file, not from the request, so a write reverted anywhere else
    still stops an auto run by name instead of joining a server that cannot answer.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The switch is asked for exactly once in the whole script, and by one name.
    # A run that dropped it again measures zero; a run that spread it unconditionally
    # to the black-hole branch or to a second call site measures more than one.
    assert text.count("--enable-status") == 1, (
        "domain.sh must name --enable-status exactly once, inside the auto-bundle guard"
    )
    # And that one naming sits under exactly the predicate the early-stop check is
    # asked under: non-empty `auto_bundle`, initialised empty so a non-auto run —
    # including the black-hole run that skips the early stop by design — hands the
    # launcher nothing and keeps the reviewed default.
    assert (
        "status_args=()\n"
        '    if [ -n "${auto_bundle}" ]; then\n'
        "        status_args=(--enable-status)\n"
        "    fi"
    ) in text
    # The call site that starts the controlled server expands the guarded array, so
    # the switch reaches the tool inside this run rather than somewhere else.
    call = text[
        text.index("python /src/tools/run_controlled_server.py") : text.index(
            "--keep-running >/tmp/domain-server.log"
        )
    ]
    assert '"${status_args[@]}"' in call
    # The black-hole branch starts a silent listener, never the controlled server,
    # and the opt-in never reaches it.
    listener = text[
        text.index('if [ -n "${server_profile}" ] && [ -n "${black_hole}" ]; then') : text.index(
            'elif [ -n "${server_profile}" ]; then'
        )
    ]
    assert "status_args" not in listener
    # The readiness guard survives the wiring: it reads the setting back off the
    # disk and stops an auto run by name when the file does not say true, whatever
    # the request said.
    assert 'if [ -n "${auto_bundle}" ] && [ "${enable_status}" != "true" ]; then' in text
    assert "so the run stops before the client starts" in text


#: The three items the joining client's failure turned on, and the names the readout
#: gives them when they are absent. Pinned as data because the same five strings are
#: what the reversal table below was measured against: removing any one of them makes
#: the readout unable to name a missing item, which is the difference between a reading
#: and a restatement of what the crash report already said.
CLIENT_ENVIRONMENT_ITEMS = ("DISPLAY", "XDG_RUNTIME_DIR", "XAUTHORITY")
CLIENT_ENVIRONMENT_ABSENT_NAMES = (
    '"<unset>"',
    '"<set-but-empty>"',
    "not-measured: this process was handed no DISPLAY at all",
    "unmeasurable: the DISPLAY named here is not being served",
)


def test_the_runner_names_the_joiner_environment_before_its_jvm() -> None:
    """The launcher says which screen, runtime directory and GL stack it is handing over.

    Six runs of one case — `CORE-030`, one byte-identical recipe, one image — answered
    differently on one machine: five of them left a `client/crash-reports` carrying
    `[0x1000E] Failed to detect any supported platform` and one joined the world. The
    evidence could not have answered *which* environment the dying process had been
    given, because the only display-shaped field in a bundle,
    `environment.renderer_display`, is measured by the sealer after the fact: it comes
    from this script's own seal branch (`xvfb-run -a … glxinfo -B`, then
    `--renderer-display`), and it reads `llvmpipe (LLVM 20.1.2, 256 bits)` in all six
    samples, the run whose client never opened a window included. A sealing-side reading
    cannot describe a client-side death.

    So the launcher takes the reading itself, at two depths — what this script holds, and
    what the wrapper hands its child — and writes both into
    `/data/kin/<joiner>/run/client-environment.txt` before the client starts. Measured in
    the controlled container: an unset name is written as `<unset>` and a screen nobody
    serves as `unmeasurable: … (glxinfo rc=255)`, while a run told
    `XDG_RUNTIME_DIR=/tmp/h1c-ctl-runtime` reads that exact value back at both depths.

    The clauses are measured red against the base bytes (no such reading exists there —
    `grep -c XDG_RUNTIME_DIR` over the whole runner returns nothing, and the base script's
    only `DISPLAY` lines are a comment and the harness's own `export`), and each way the
    readout could stop being a reading names the line it turns red. The last two clauses
    are the point of the shape: the *reading* adds a report and touches none of the three
    names inside this script, and it leaves the sealer's own measurement alone rather than
    passing itself off as it. (H1e added one handover on the client's own launch line, a
    runtime directory; it is not exported here either, and its own test below pins both
    the handover and the reading that names where it came from.)
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # One launcher array, and the client goes through it: a reading taken through a
    # second, hand-retyped command line could drift from the one the client got.
    assert 'joiner_launch_wrapper=(xvfb-run -a --server-args="-screen 0 1280x720x24")' in text
    # The array is used by exactly one command line — the client's own — and that line
    # writes the launch-depth reading before it execs. A second naming is a second
    # client whose environment was never read; none at all is a reading that no longer
    # shares a command line with what it describes.
    assert text.count('"${joiner_launch_wrapper[@]}"') == 1
    assert JOINER_LAUNCH_HEAD in text
    assert (
        'xvfb-run -a --server-args="-screen 0 1280x720x24" \\\n        env MINEKIN_KIN_ID'
        not in text
    )
    assert text.count("python -m minekin_core session start") == 1

    # The three items, each by its real name, and each of the ways one can be missing
    # named rather than left blank.
    assert "for item in DISPLAY XDG_RUNTIME_DIR XAUTHORITY; do" in text
    for name in CLIENT_ENVIRONMENT_ABSENT_NAMES:
        assert name in text, f"the readout lost the name for an absent item: {name}"
    assert "GL_BACKEND=" in text

    # Written where the run leaves it, in the joining Kin's own directory, and said once
    # on the run's own output.
    assert 'client_environment_readout="/data/kin/${joiner}/run/client-environment.txt"' in text
    assert text.count("joiner client environment before its JVM") == 1

    # The order is the card: baseline read, then the named environment, then the JVM.
    head = text.index("    name_the_joiner_client_environment\n")
    assert text.count("    name_the_joiner_client_environment\n") == 1
    assert text.index("baseline=${baseline:-0}") < head
    assert head < text.index(JOINER_LAUNCH_HEAD)
    # And the reading happens before the client is handed anything at all, not after it
    # dies: the launch site is the next thing the script does.
    assert head < text.index("joiner_pid=$!")

    # The reading is still a reading: it exports, unsets or defaults none of the three
    # names into this script, so the one `export DISPLAY` left in it is still the harness
    # pointing its own session at the screen it owns. What the harness now hands the
    # client — a runtime directory — is handed on the launch line and named as such in
    # the readout; `test_the_joiner_launch_line_is_handed_a_runtime_directory` pins that
    # half, and it is deliberately not an `export` here.
    assert text.count("export DISPLAY") == 1

    # The sealer keeps measuring its own renderer; this reading is a second, differently
    # placed thing and has not been substituted for it.
    assert text.count("--renderer-display") == 1
    assert 'measured=$(xvfb-run -a --server-args="-screen 0 1280x720x24" glxinfo -B' in text


def test_a_joiner_that_never_arrived_is_told_apart_from_an_unprobeable_world() -> None:
    """Downstream of a client that had not arrived, the two readings a reader can
    confuse are named apart — and neither reading claims more than the window shows.

    `NO_CONNECTION_WAS_DIALLED` and `THE_CLIENT_NEVER_DIALLED_A_PORT` are both facts about
    the client half, and "the server's status is not probeable" looks the same from
    downstream: nothing arrived, nothing answered. This run's material says which of the
    two it is evidence about, by reading two separate things — whether anything answers
    the published port *on loopback*, and whether the client had been handed a screen that
    could be measured — and naming the combination. Measured in the controlled container:
    with a real listener on the port the same script says
    `THE_JOINER_HAD_NOT_ARRIVED_IN_THE_WINDOW with a live world and a measurable screen
    (…)`, and with that listener gone it says `THE_WORLD_STATUS_IS_NOT_PROBEABLE …, so
    this run is evidence about the world and not about the client environment`. A reading
    that cannot flip when the world is the thing that is down would be a restatement of
    the FAIL.

    The two client-side endings used to be named `THE_RUN_DIED_ON_THE_CLIENT_SIDE` and
    `THE_RUN_DIED_IN_THE_CLIENT_ENVIRONMENT`. That overclaimed on measured material: this
    classifier is reached from the wait branch that prints `never arrived within`, and the
    H1c run whose readings produced the first of those sentences joined *after* its window
    closed (`snapshots_admitted 1`, ending `BRIDGE_LOST`) — the run did not die on the
    client side; the window closed before the client half had delivered. The endings now
    name what the branch can see (the window, the screen, the listener) and nothing more.
    Same five readings, same distinctions, no new criterion, no gate, no bundle field.

    It is reached only on the branch where the joiner had not arrived, it changes no
    criterion, no gate and no bundle field, and it feeds nothing to the sealer — the
    verdict is written next to the readings it was derived from and printed. A run it
    describes is still the same FAIL it was before, with one more thing said about it.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")
    assert "classify_the_joiner_downstream_readings() {" in text, (
        "the two downstream readings are no longer told apart at all"
    )
    body = text[
        text.index("classify_the_joiner_downstream_readings() {") : text.index(
            "# Start the second client against the world the first one published"
        )
    ]

    # Every outcome has its own name, including the one where nothing could be read.
    for name in (
        "THE_CLIENT_ENVIRONMENT_WAS_NEVER_READ",
        "THE_JOINER_SCREEN_WAS_UNMEASURABLE",
        "THE_JOINER_HAD_NOT_ARRIVED_IN_THE_WINDOW",
        "THE_WORLD_STATUS_IS_NOT_PROBEABLE",
        "BOTH_HALVES_NAMED_AND_BOTH_BAD",
    ):
        assert body.count(name) == 1, f"a downstream reading is missing or doubled: {name}"

    # The two death claims are gone from the whole script, not just renamed elsewhere:
    # this classifier is reached when the *window* closed, and a window cannot name a
    # death — the H1c material says so in one run's own readings.
    assert "THE_RUN_DIED" not in text
    # And the surviving client-side ending says the window in its own name.
    assert body.index("THE_JOINER_HAD_NOT_ARRIVED_IN_THE_WINDOW") < body.index(
        "THE_WORLD_STATUS_IS_NOT_PROBEABLE"
    )

    # The world side is asked a loopback question and nothing else. This project never
    # dials a remote address from here, so the only `/dev/tcp` in the script names
    # 127.0.0.1 — a target the harness itself published to.
    assert re.findall(r"/dev/tcp/([^/\"]+)/", text) == ["127.0.0.1"]

    # The client side is read from the launch-depth line the launcher wrote, not from the
    # harness's own screen, which is a different display by construction.
    assert "sed -n 's/^launch GL_BACKEND=//p'" in body
    assert "s/^harness GL_BACKEND=" not in body

    # It is a reading and not a second verdict: it writes to the readout file, prints, and
    # touches neither the sealer's inputs nor its field names.
    assert "--renderer-display" not in body
    assert "seal_run_evidence" not in body
    assert text.count("    classify_the_joiner_downstream_readings\n") == 1
    never_arrived = text.index("never arrived within")
    assert never_arrived < text.index("    classify_the_joiner_downstream_readings\n")
    assert text.index("    classify_the_joiner_downstream_readings\n") < text.index(
        "admitted its first snapshot of that world"
    )


def test_the_launch_depth_reading_travels_on_the_line_that_execs_the_client() -> None:
    """The `launch` depth is written by the wrapper that becomes the JVM, not a sibling.

    H1c measured the two depths into one file and its record asserted that the client JVM
    is handed the `launch` values. That claim was too strong as written: the launch-depth
    probe ran through `xvfb-run` as *its own* invocation, and the real client started in a
    *different* one — `xvfb-run -a` picks a display number per allocation and makes a
    fresh temporary `XAUTHORITY` each time, so the probe's screen could only resemble the
    client's. Measured in the controlled container with both shapes side by side
    (`.tmp/h1d-env-pair.log`): the separate probe's `XAUTHORITY` and the environment of
    the process exec'd on the launch line are different files under `/tmp`, and the
    readings now come from inside that exec'ing line — so the sentence in the record is
    true by construction: the probe runs, then `exec "$@"` hands *this* environment to
    whatever the line becomes.

    The clauses pin the shape of that claim and its two honest edges: a staged probe file
    that is missing names its absence instead of writing a silent `launch GL_BACKEND=`
    the classifier would read as a measured screen, and the readout itself still exports,
    unsets or defaults none of the three items — the runtime directory H1e hands over
    belongs to the launch line, where the client is actually standing, and never to this
    script's own environment.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The sibling allocation is gone: no command line runs the probe through the
    # wrapper except the one that execs the client.
    assert "minekin-runner launch \\" not in text
    assert 'bash -c "${client_environment_probe}" minekin-runner harness' in text
    # The launch line stages and runs the probe, then execs in the same environment.
    staging = (
        'printf \'%s\\n\' "${client_environment_probe}" > "${client_environment_probe_script}"'
    )
    assert staging in text
    assert 'CLIENT_ENVIRONMENT_PROBE_SCRIPT="${client_environment_probe_script' in text
    assert 'bash "${CLIENT_ENVIRONMENT_PROBE_SCRIPT}" launch \\' in text
    assert 'exec "$@"' in text
    # The probe runs before the exec, on that line — not after the JVM is up.
    head = text.index('bash "${CLIENT_ENVIRONMENT_PROBE_SCRIPT}" launch \\')
    assert head < text.index('exec "$@"')
    # A missing staged probe is a named absence, and it is not a `launch GL_BACKEND=`
    # line: the classifier's NEVER_READ ending has to stay reachable and honest.
    assert "launch GL_PROBE=not-staged" in text
    assert text.count("GL_BACKEND=%s") == 1, "a second writer of the launch-depth backend appeared"
    # The depth label the launch line carries is the inside-wrapper one, and exactly once.
    assert text.count("MINERUN_LAUNCH_DEPTH=inside-wrapper") == 1
    assert text.count("MINERUN_LAUNCH_DEPTH=direct") == 1


#: The two answers a run can give about where the runtime directory it handed the
#: joining client came from. Pinned as data because the third test below drives the same
#: two predicates over mutated bytes: a name that appears nowhere is a missing reading,
#: and a name that appears everywhere is a decoration.
RUNTIME_DIR_ORIGINS = ("inherited", "provided-by-harness")

#: The first two lines of the one command line that starts the joining client: the
#: wrapper array, then `env` with the runtime directory this run decided and the Kin the
#: session is for. Named once because three tests locate the client's launch site by it.
JOINER_LAUNCH_HEAD = (
    '"${joiner_launch_wrapper[@]}" \\\n'
    '        env "${joiner_runtime_dir_env[@]}" MINEKIN_KIN_ID="${joiner}"'
)

#: The launch-line clause the whole provision turns on. One predicate, shared by the
#: green case and the reversal, so the reversal cannot pass by testing something looser
#: than the implementation.
RUNTIME_DIR_HANDOVER = (
    "        joiner_runtime_dir_env=(\n"
    '            XDG_RUNTIME_DIR="${client_runtime_dir}"\n'
    '            CLIENT_RUNTIME_DIR_ORIGIN="${client_runtime_dir_origin}"\n'
    "        )\n"
)


def hands_the_joiner_a_runtime_directory(text: str) -> bool:
    """The launcher decides a runtime directory and puts it on the client's own line."""

    return (
        "provide_the_joiner_runtime_directory() {" in text
        and "    provide_the_joiner_runtime_directory\n" in text
        and RUNTIME_DIR_HANDOVER in text
        and 'env "${joiner_runtime_dir_env[@]}" MINEKIN_KIN_ID="${joiner}"' in text
    )


def names_the_runtime_directory_origin(text: str) -> bool:
    """The readout says which of the two ways this run has one produced that value."""

    return (
        'printf "%s XDG_RUNTIME_DIR_ORIGIN=%s\\n" "${depth}" \\\n'
        '            "$(read_one CLIENT_RUNTIME_DIR_ORIGIN)" >> "${out}"' in text
    )


def provider_body(text: str) -> str:
    """The bytes of `provide_the_joiner_runtime_directory`, and only those."""

    start = text.index("provide_the_joiner_runtime_directory() {")
    return text[start : text.index("\n# When the joining client never arrived")]


def keeps_the_runtime_directory_off_the_sealed_material(text: str) -> bool:
    """The directory is made where a run's sealable material is not.

    `/data` is the volume, and everything under a Kin's run directory is material a later
    seal may glob. A runtime directory is neither of those things, so the single place its
    path is decided has to name scratch space — and the mutation that moves it is the one
    this predicate exists to catch.
    """

    return "client_runtime_dir_base=/tmp/" in text and "client_runtime_dir_base=/data" not in text


def test_the_joiner_launch_line_is_handed_a_runtime_directory() -> None:
    """The joining client's launch line carries a usable `XDG_RUNTIME_DIR`, or nothing.

    H1c left the harness able to see the absence and unable to do anything with it: on
    the shipped bytes the whole of `domain.sh`'s relationship to the name was one line
    (`for item in DISPLAY XDG_RUNTIME_DIR XAUTHORITY; do`), and the readout it produces
    said `launch XDG_RUNTIME_DIR=<unset>` on every controlled run. Measured in the
    container this time rather than inferred: the image sets the name nowhere at all and
    has no `/run/user/0`, the joining client's own first stderr line is
    `error: XDG_RUNTIME_DIR is invalid or not set in the environment`, and that line sits
    in `run/session/<id>/generation-1/logs/stderr.log` and in the sealed
    `client/stderr.log` — it is written by the client, not by the shell that launched it.
    A launch line that hands over nothing is therefore the half this harness owns.

    The shape is deliberately small, and the clauses say which edges of it are load
    bearing:

    * An inherited value is kept when it is usable (absolute, present, a directory,
      writable). This harness does not swap out a directory somebody else made.
    * Otherwise it makes one, at mode 0700 — what the name itself requires — under `/tmp`,
      never under `/data`: the volume is a run's material, and a directory created there
      would sit beside the session overlay and become something a later seal would have
      to be taught to ignore.
    * It is carried on the client's own command line and never exported into this script,
      which has no window surface to register with one. A provision that could not
      provision leaves the array empty, so the client is handed exactly what it was
      handed before, rather than a name set to nothing — `<set-but-empty>` is worse than
      `<unset>` here, because it looks like a value.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The decision exists, is called exactly once, and is on the client's line.
    assert hands_the_joiner_a_runtime_directory(text)
    assert text.count("    provide_the_joiner_runtime_directory\n") == 1

    # Inheritance is checked rather than assumed, and the ways a value can be unusable
    # are asked separately: "nobody set it" and "it was set to nothing" are different
    # faults, and so are "not a path", "no such directory" and "not ours to write to".
    assert 'local candidate="${XDG_RUNTIME_DIR:-}"' in text
    # Asked of the environment, not of the local copy — an empty string is what both
    # "nobody set it" and "it was set to nothing" collapse into otherwise.
    assert 'if [ -z "${XDG_RUNTIME_DIR+set}" ]; then' in text
    assert "reason='it is not set in the environment this script holds'" in text
    assert "reason='it is set to nothing in the environment this script holds'" in text
    assert 'elif [ "${candidate#/}" = "${candidate}" ]; then' in text
    assert 'elif [ ! -d "${candidate}" ]; then' in text
    assert 'elif [ ! -w "${candidate}" ]; then' in text
    assert "        client_runtime_dir_origin=inherited" in text

    # A made directory is private at mode 0700, and only becomes the handed-over value
    # once it is verifiably one.
    assert "    client_runtime_dir_origin=provided-by-harness" in text
    assert 'chmod 700 "${made}"' in text
    assert 'made=$(mktemp -d "${client_runtime_dir_base}/runtime.XXXXXX"' in text

    # Under /tmp and out of the volume: the base the directory is made from is named once,
    # it is under the harness's scratch, and the provider body never names `/data`.
    assert text.count("client_runtime_dir_base=") == 1
    assert keeps_the_runtime_directory_off_the_sealed_material(text)
    body = provider_body(text)
    assert "/data" not in body, "the runtime directory moved onto the volume a run seals from"

    # Nothing is exported into this script: the value reaches the client through the one
    # command line that execs it, and the harness's own environment keeps the shape the
    # readout has always reported for it.
    assert "export XDG_RUNTIME_DIR" not in text
    assert text.count("export DISPLAY") == 1

    # A failed provision hands over nothing rather than an empty name.
    assert '    if [ -n "${client_runtime_dir}" ]; then' in text
    assert "    joiner_runtime_dir_env=()\n" in text

    # The order on the launch path: read what this script holds, decide the runtime
    # directory, then start the wrapper that execs the client.
    read = text.index("    name_the_joiner_client_environment\n")
    decided = text.index("    provide_the_joiner_runtime_directory\n")
    started = text.index('env "${joiner_runtime_dir_env[@]}" MINEKIN_KIN_ID="${joiner}"')
    assert read < decided < started
    assert started < text.index("joiner_pid=$!")


def test_the_client_environment_readout_names_where_the_runtime_directory_came_from() -> None:
    """`client-environment.txt` says whether the runtime directory is this harness's.

    A value in that file can now mean two different things, and the difference is exactly
    the thing H1c built the readout to keep visible: a container that had a usable
    directory, and a harness that made one because nothing had. Without the second name
    the file would report the same shape for both, and the harness would be grading its
    own work by a path it filled in — which is the failure mode the reading existed to
    avoid. So the origin is a separate line, and the three states H1c named for a missing
    item still apply to it: the harness depth is never told, and writes `<unset>` rather
    than dropping the line or inventing `inherited`.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # The origin is read out, once, in the same probe that reads out the three items —
    # not by a second writer that could drift from it.
    assert names_the_runtime_directory_origin(text)
    assert text.count("XDG_RUNTIME_DIR_ORIGIN=%s") == 1
    assert text.count("CLIENT_RUNTIME_DIR_ORIGIN=") == 1, (
        "the origin is handed over somewhere other than the client's own launch line"
    )

    # Both names the answer can take are in the shipped bytes.
    for origin in RUNTIME_DIR_ORIGINS:
        assert f"client_runtime_dir_origin={origin}" in text, f"an origin name is gone: {origin}"

    # The three-state shape survives: the origin goes through the same three-state reader
    # as the items, the items are still read by name, and neither collapses into the
    # value line.
    assert '"$(read_one CLIENT_RUNTIME_DIR_ORIGIN)"' in text
    assert "for item in DISPLAY XDG_RUNTIME_DIR XAUTHORITY; do" in text
    for name in CLIENT_ENVIRONMENT_ABSENT_NAMES:
        assert name in text, f"the readout lost a state name: {name}"

    # It is written into the same readout file, at both depths, in the joining Kin's run
    # directory — the reading moved nowhere, and the new line is on the same channel.
    probe = text[
        text.index("    client_environment_probe=") : text.index("    client_runtime_dir=")
    ]
    assert 'client_environment_readout="/data/kin/${joiner}/run/client-environment.txt"' in text
    assert probe.count('>> "${out}"') == 5, (
        "a depth no longer writes every line it claims to, or a second writer appeared"
    )


def test_the_runtime_directory_provision_is_not_an_always_true_claim() -> None:
    """Delete the handover or the origin line and the clauses above stop holding.

    A contract test written as `assert "XDG" in text` would pass on the bytes that shipped
    before this card and on the bytes that ship after it, which makes it worthless as
    evidence. So the two predicates the other two tests are built on are driven here over
    mutations of the *shipped* bytes: each mutation removes exactly one thing this card
    adds, and each is measured to turn its predicate false. The predicates are the same
    functions the green tests assert, so nothing looser is being checked on the way.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")

    # Green on the shipped bytes first: a predicate that is false on both sides of a
    # mutation would prove nothing about the mutation.
    assert hands_the_joiner_a_runtime_directory(text)
    assert names_the_runtime_directory_origin(text)
    assert keeps_the_runtime_directory_off_the_sealed_material(text)
    assert "/data" not in provider_body(text)

    # RV-1: the export itself is deleted from the launch line's array, leaving the
    # function, the call and the array in place. This is the half that decides whether the
    # client stands on a runtime directory at all.
    without_handover = text.replace(RUNTIME_DIR_HANDOVER, "", 1)
    assert without_handover != text, "the handover block was not found to delete"
    assert not hands_the_joiner_a_runtime_directory(without_handover)

    # RV-2: the value stays on the line but the origin reading is deleted — the shape
    # where the harness fills a blank and the record cannot tell a reader it did.
    without_origin = text.replace(
        'printf "%s XDG_RUNTIME_DIR_ORIGIN=%s\\n" "${depth}" \\\n'
        '            "$(read_one CLIENT_RUNTIME_DIR_ORIGIN)" >> "${out}"',
        "",
        1,
    )
    assert without_origin != text, "the origin reading was not found to delete"
    assert not names_the_runtime_directory_origin(without_origin)

    # RV-3: the origin is still written, but from the value rather than through the
    # three-state reader — one state where three were, which is what H1c existed to stop.
    collapsed = text.replace(
        '"$(read_one CLIENT_RUNTIME_DIR_ORIGIN)"', '"${CLIENT_RUNTIME_DIR_ORIGIN}"', 1
    )
    assert collapsed != text
    assert not names_the_runtime_directory_origin(collapsed)

    # RV-4: the directory moves from the harness's scratch onto the volume a run seals
    # from. Every other clause still holds — the function, the handover, the origin line —
    # and the one that stops holding is the one about where the directory lives.
    onto_volume = text.replace(
        "client_runtime_dir_base=/tmp/minekin-client-runtime",
        "client_runtime_dir_base=/data/kin/client-runtime",
        1,
    )
    assert onto_volume != text
    assert hands_the_joiner_a_runtime_directory(onto_volume)
    assert names_the_runtime_directory_origin(onto_volume)
    assert not keeps_the_runtime_directory_off_the_sealed_material(onto_volume)


# ---------------------------------------------------------------------------
# V1201-LAN-JOINER-BOUNDED-CONTROL-DRIVER-001 — the *joining* client can be asked
# to look and move, inside bounds the runner checks before it starts anything.
# ---------------------------------------------------------------------------

#: The shipped driver region and the wiring that calls it, marked in `domain.sh` and
#: extracted from it rather than retyped. Every reading below runs the bytes a run
#: would run — the same bound constants, the same comparisons, the same array — so a
#: change to any of them moves a measurement here before it moves a live run.
JOINER_CONTROL_DRIVER_BEGIN = "# --- joiner-control-driver begin"
JOINER_CONTROL_DRIVER_END = "# --- joiner-control-driver end ---"
JOINER_CONTROL_WIRING_END = "# --- joiner-control wiring end ---"

#: The three bounds, as literals a reader can see. The region's own assignments are
#: pinned against these, so widening one is a decision taken in the open.
JOINER_CONTROL_BOUNDS = {
    "joiner_control_max_yaw": "45",
    "joiner_control_max_pitch": "30",
    "joiner_control_max_forward_seconds": "2",
}

#: The only product flags this driver may hand over, and the name behind each.
JOINER_CONTROL_ASKS = {
    "MINEKIN_DOMAIN_JOIN_LOOK_YAW": "--look-yaw-degrees",
    "MINEKIN_DOMAIN_JOIN_LOOK_PITCH": "--look-pitch-degrees",
    "MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS": "--hold-forward-seconds",
}

#: What `session start` accepts beside those three and this driver never reaches for.
JOINER_CONTROL_FORBIDDEN_FLAGS = (
    "--hold-strafe",
    "--hold-jump",
    "--hold-sneak",
    "--hold-use-seconds",
    "--hold-at",
)

#: The joining client's product call at the card's base commit (`24ac6e0`, `domain.sh`
#: sha256 ff69c879…, the line at :1179-1184), before any control driver existed. This
#: is the observe-only line V4 measured reaching `JOIN` and `PLAYABLE`. Transcribed on
#: purpose: the identity check below has to be able to fail, and a baseline recomputed
#: from the current file could never say so.
JOINER_BUNDLE_PROFILE = "/src/tests/fixtures/launcher/1.20.1.json"
OBSERVE_ONLY_JOINER_ARGV = [
    "python",
    "-m",
    "minekin_core",
    "session",
    "start",
    "--profile",
    JOINER_BUNDLE_PROFILE,
    "--server-profile",
    "/tmp/domain-join-profile.json",
]


def joiner_control_region(text: str, end_marker: str) -> str:
    """The shipped driver bytes, from the begin marker to the marker named."""

    start = text.index(JOINER_CONTROL_DRIVER_BEGIN)
    end = text.index(end_marker, start)
    lines = text[start:end].splitlines(keepends=True)
    assert len(lines) > 20, "the joiner-control region came out empty; wrong markers"
    return "".join(lines[1:])


def drive_joiner_control(
    tmp_path: Path,
    *,
    env: dict[str, str] | None = None,
    joiner: str = "kin-2",
    hold_at: str = "playable",
    profile: str = JOINER_BUNDLE_PROFILE,
    region: str | None = None,
    wiring: bool = False,
    tag: str = "plain",
) -> tuple[subprocess.CompletedUnicode[str], list[str]]:
    """Drive the shipped driver as its own shell process, and read back what it says.

    `wiring=False` runs the composition and prints the argv it built, each word
    bracketed, *through the same `bash -c '… "$@"'` seam* the joining client is exec'd
    through — so a word that would split or merge on its way to the product reads wrong
    here before it reads wrong in a run. `wiring=True` runs the region *plus* the call
    and the printout block, so the readback surface itself — and the fact that a refusal
    precedes any print — is what is being driven. Nothing is launched on either path:
    this is the region, not the run.

    The four control names are stripped from the inherited environment first. A knob
    left over from a caller would arm a driver a reading meant to leave asleep, and the
    empty-knob case is the one this card is most careful about.

    The prelude stands in for the three reads the region sits below — `joiner` from its
    environment name, `hold_at` and `profile` from the run's own argument scan — and
    nothing else. What the region reads for itself, it reads from the environment
    exactly as a run hands it.
    """

    work = tmp_path / f"joiner-control-{tag}"
    work.mkdir(parents=True, exist_ok=True)
    if region is None:
        text = (RUNNER / "domain.sh").read_text(encoding="utf-8")
        region = joiner_control_region(
            text, JOINER_CONTROL_WIRING_END if wiring else JOINER_CONTROL_DRIVER_END
        )
    script = work / "driver.sh"
    prelude = (
        "set -euo pipefail\n"
        f"joiner={shlex.quote(joiner)}\n"
        f"hold_at={shlex.quote(hold_at)}\n"
        f"profile={shlex.quote(profile)}\n"
    )
    if wiring:
        # The wiring block reads one more name, at the top of the script rather than
        # inside the region; this line is the shipped read, byte for byte, and the shape
        # test below pins that it still is. Without it `set -u` would stop the driver on
        # an unset name and the printout would never be reached.
        prelude += 'join_control_print="${MINEKIN_DOMAIN_JOIN_CONTROL_PRINT:-}"\n'
    tail = (
        ""
        if wiring
        else "\n".join(
            (
                "joiner_control_args=()",
                "compose_joiner_control_args",
                "joiner_session_argv=()",
                "build_joiner_session_argv",
                # The same seam the joining client is started through: an outer shell
                # expands the array for a `bash -c '… "$@"'` that execs it. `printf`
                # stands in for `exec` so the reading never runs a product command, and
                # each word is bracketed so a split or a merge cannot pass unnoticed.
                "bash -c 'for w in \"$@\"; do printf \"<%s>\" \"$w\"; done;"
                " printf \"\\n\"' minekin-joiner-launch \"${joiner_session_argv[@]}\"",
            )
        )
        + "\n"
    )
    script.write_text(prelude + region + tail, encoding="utf-8")
    environment = dict(os.environ)
    for name in JOINER_CONTROL_KNOBS:
        environment.pop(name, None)
    environment.update(env or {})

    bash = shutil.which("bash")
    assert bash, "the joiner-control driver is shell code and there is no bash to drive it"
    result = subprocess.run(
        [bash, script.as_posix()],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        cwd=str(work),
    )
    return result, re.findall(r"<([^>]*)>", result.stdout)


def refused(result: subprocess.CompletedUnicode[str], argv: list[str]) -> None:
    """Refused, and said to be: no composed line, no exit 0, a message on stderr."""

    assert result.returncode != 0, (
        f"the driver answered rc=0 where it was expected to refuse: {argv}"
    )
    assert argv == [], f"a refusal still handed over a command line: {argv}"
    assert result.stderr.strip(), "a refusal with nothing to say"


def test_the_joiner_control_driver_keeps_its_bounds_and_reaches_one_line_only() -> None:
    """The bounds are literals a reader sees, the flags are three, the splice is one.

    Shape first, because the behaviour tests below are only worth what this pins: a
    driver whose bound lives in a variable nobody can read is a driver that can be
    widened without a diff saying so.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")
    region = joiner_control_region(text, JOINER_CONTROL_DRIVER_END)

    # Each bound is assigned exactly once, at the pinned number.
    for name, value in JOINER_CONTROL_BOUNDS.items():
        assert region.count(f"{name}={value}\n") == 1, f"{name} is not the bound it claims"
        assert f"{name}=" in region

    # Exactly three appends to the array, one per allowed flag, and no other flag name
    # is ever written to it. The comment block inside the region *names* the forbidden
    # flags to disclaim them, so the check is on the append lines and nowhere else.
    appended = re.findall(r"joiner_control_args\+=\((--[a-z-]+)", region)
    assert sorted(appended) == sorted(JOINER_CONTROL_ASKS.values()), appended
    for flag in JOINER_CONTROL_FORBIDDEN_FLAGS:
        assert f"joiner_control_args+=(--{flag.lstrip('-')}" not in region

    # One product command line in the whole file, and it belongs to the joining client.
    # It exists as an array — folded from the ask once, started once, printed once — so
    # the readback and the launch cannot drift into two claims about one line. That is
    # the same drift the joiner-environment test above guards by counting the literal.
    assert text.count("python -m minekin_core session start") == 1
    assert text.count('"${joiner_control_args[@]}"') == 1, (
        "the bounded ask reaches somewhere other than the joining client's array"
    )
    assert text.count('"${joiner_session_argv[@]}"') == 2
    function = text[text.index("join_the_published_world() {") : text.index("\nlogs_before=")]
    launch = function[
        function.index("' minekin-joiner-launch") : function.index("joiner_pid=$!")
    ]
    assert launch.count('"${joiner_session_argv[@]}" \\') == 1
    assert "python -m minekin_core session start" not in launch
    assert function.count('"${joiner_session_argv[@]}"') == 1
    # Nothing at all on the way to the hosting session's line, which is the run's own
    # arguments (`"$@"`) and untouched by this card.
    host_start = text.index("minekin-session-supervisor")
    host_launch = text[host_start : text.index("session_pid=$!", host_start)]
    assert '"$@"' in host_launch
    assert "joiner" not in host_launch

    # The controller-reserved auto-bundle refusal is untouched and answers first, so
    # there is no path from an auto run to this driver to guard against.
    assert (
        text.count(
            "domain: an auto-bundle run cannot also ask for a joining second client; "
            "the joiner is started from a named bundle profile"
        )
        == 1
    )
    assert text.index("an auto-bundle run cannot also ask") < text.index(
        "\ncompose_joiner_control_args\n"
    )


def test_the_unarmed_joining_client_is_still_handed_the_observe_only_line(
    tmp_path: Path,
) -> None:
    """Nothing set: the joining client's argv is the base commit's, word for word.

    This is the regression guard for every run measured before this card, the frozen
    1.21.4 v1 route included. A driver that armed itself by default would be invisible
    to every other test in this file and visible only here, which is why the check is
    an equality against a transcription of the old line rather than an absence of new
    flags.
    """

    result, argv = drive_joiner_control(tmp_path, tag="unarmed")
    assert result.returncode == 0, result.stderr
    assert argv == OBSERVE_ONLY_JOINER_ARGV

    # A name delivered and empty is the same ask as one never delivered — the shape
    # `run.sh` would produce for a knob it passes through unset.
    emptied = {name: "" for name in JOINER_CONTROL_KNOBS}
    result, argv = drive_joiner_control(tmp_path, env=emptied, tag="empty-knobs")
    assert result.returncode == 0, result.stderr
    assert argv == OBSERVE_ONLY_JOINER_ARGV

    # And no joining client at all is still not an ask: the line is the one that would
    # have been started, unchanged, whether or not anyone ever starts it.
    result, argv = drive_joiner_control(tmp_path, joiner="", tag="no-joiner-unarmed")
    assert result.returncode == 0, result.stderr
    assert argv == OBSERVE_ONLY_JOINER_ARGV


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "22.5"}, ["--look-yaw-degrees", "22.5"]),
        ({"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "45"}, ["--look-yaw-degrees", "45"]),
        ({"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "-22.5"}, ["--look-yaw-degrees", "-22.5"]),
        ({"MINEKIN_DOMAIN_JOIN_LOOK_PITCH": "-30"}, ["--look-pitch-degrees", "-30"]),
        ({"MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS": "2"}, ["--hold-forward-seconds", "2"]),
        (
            {"MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS": "0.25"},
            ["--hold-forward-seconds", "0.25"],
        ),
        (
            {
                "MINEKIN_DOMAIN_JOIN_LOOK_YAW": "22.5",
                "MINEKIN_DOMAIN_JOIN_LOOK_PITCH": "-10",
                "MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS": "1.5",
            },
            [
                "--look-yaw-degrees",
                "22.5",
                "--look-pitch-degrees",
                "-10",
                "--hold-forward-seconds",
                "1.5",
            ],
        ),
    ],
    ids=lambda value: "_".join(value) if isinstance(value, dict) else "+".join(value),
)
def test_an_armed_joining_client_is_handed_exactly_the_bounded_ask(
    tmp_path: Path, env: dict[str, str], expected: list[str]
) -> None:
    """In range: the bounded look and one hold of at most two seconds, and nothing else.

    The whole line is compared, not only the additions — an ask that also grew a
    `--hold-jump` or lost its `--server-profile` would satisfy an `in`-check and break
    the join.
    """

    result, argv = drive_joiner_control(tmp_path, env=env, tag="armed")
    assert result.returncode == 0, result.stderr
    assert argv == [*OBSERVE_ONLY_JOINER_ARGV, *expected]
    assert "--profile" in argv and "--server-profile" in argv
    assert argv[argv.index("--server-profile") + 1] == "/tmp/domain-join-profile.json"
    handed = " ".join(argv)
    for flag in JOINER_CONTROL_FORBIDDEN_FLAGS:
        assert flag not in handed, f"the driver reached beyond its ask: {flag}"
    # One look and one hold at most, however the ask was spelled.
    assert handed.count("--look-yaw-degrees") <= 1
    assert handed.count("--look-pitch-degrees") <= 1
    assert handed.count("--hold-forward-seconds") <= 1
    if "--hold-forward-seconds" in argv:
        assert float(argv[argv.index("--hold-forward-seconds") + 1]) <= 2.0


@pytest.mark.parametrize(
    ("name", "value", "bound"),
    [
        ("MINEKIN_DOMAIN_JOIN_LOOK_YAW", "90", "45"),
        ("MINEKIN_DOMAIN_JOIN_LOOK_YAW", "-46", "45"),
        ("MINEKIN_DOMAIN_JOIN_LOOK_YAW", "0", "45"),
        ("MINEKIN_DOMAIN_JOIN_LOOK_PITCH", "31", "30"),
        ("MINEKIN_DOMAIN_JOIN_LOOK_PITCH", "-30.5", "30"),
        ("MINEKIN_DOMAIN_JOIN_LOOK_PITCH", "0", "30"),
        ("MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS", "10", "2"),
        ("MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS", "2.5", "2"),
        ("MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS", "0", "2"),
        ("MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS", "-1", "2"),
        ("MINEKIN_DOMAIN_JOIN_LOOK_YAW", "45x", "45"),
        ("MINEKIN_DOMAIN_JOIN_LOOK_PITCH", "both", "30"),
        ("MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS", "1; touch /tmp/pwned", "2"),
    ],
)
def test_an_out_of_bounds_joiner_ask_is_refused_by_name(
    tmp_path: Path, name: str, value: str, bound: str
) -> None:
    """The ask is refused with its own name and its own bound, and never passed through.

    Three shapes are refused for three different reasons and all three arrive at the
    same place: too wide (`90` against a bound of `45`), nothing at all (`0`, which the
    product would accept as a look of no degrees only after a client had been started),
    and not a number (`both`, `45x`, and a value carrying a shell metacharacter — which
    is refused by the shape test before any comparison reads it as something else).
    """

    result, argv = drive_joiner_control(tmp_path, env={name: value}, tag=f"refused-{name}")
    refused(result, argv)
    assert name in result.stderr, f"the refusal did not say which knob: {result.stderr}"
    assert bound in result.stderr, f"the refusal did not say which bound: {result.stderr}"
    assert JOINER_CONTROL_ASKS[name] not in " ".join(argv)
    assert value not in " ".join(argv)


def test_arming_the_joiner_driver_without_a_joining_client_is_refused(
    tmp_path: Path,
) -> None:
    """Control with no second client is a knob that does nothing, and says so.

    The host session takes its input from its own arguments, never from these names, so
    an armed driver on a run with no joiner would leave the run reading observe-only
    while its environment claimed otherwise — the exact silent-absence failure this
    file's first test exists to catch.
    """

    for name in JOINER_CONTROL_ASKS:
        result, argv = drive_joiner_control(
            tmp_path, env={name: "10"}, joiner="", tag=f"no-joiner-{name}"
        )
        refused(result, argv)
        assert name in result.stderr
        assert "MINEKIN_DOMAIN_JOIN" in result.stderr

    # All three at once still names all three.
    result, argv = drive_joiner_control(
        tmp_path,
        env={name: "10" for name in JOINER_CONTROL_ASKS},
        joiner="",
        tag="no-joiner-all",
    )
    refused(result, argv)
    for name in JOINER_CONTROL_ASKS:
        assert name in result.stderr

    # And the refusal is about the combination: the same ask with a joining client named
    # is a composed line, not a stop. `10` is inside the yaw and pitch bounds and
    # outside the hold's, so the hold is asked at 1 second here.
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "10", "MINEKIN_DOMAIN_JOIN_LOOK_PITCH": "10"},
        joiner="kin-2",
        tag="joiner-present",
    )
    assert result.returncode == 0, result.stderr
    assert argv == [
        *OBSERVE_ONLY_JOINER_ARGV,
        "--look-yaw-degrees",
        "10",
        "--look-pitch-degrees",
        "10",
    ]


@pytest.mark.parametrize("armed", [True, False], ids=["armed", "observe-only"])
def test_a_joining_ask_at_the_join_phase_is_refused_and_never_waited_for(
    tmp_path: Path, armed: bool
) -> None:
    """`--hold-at join` stays a designed refusal, and the driver does not join it.

    The phase is read from the run's own arguments, and the product refuses a hold
    asked before the first snapshot by design. This driver's half is narrower: it will
    not *compose* an ask whose moment cannot arrive. That is a refusal test rather than
    a wait, and the host-side scan that skips its walk wait for the same phase is
    untouched by this card — both halves are read here, because the pair is what says
    the phase still means "no".
    """

    env = {"MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS": "1"} if armed else {}
    result, argv = drive_joiner_control(tmp_path, env=env, hold_at="join", tag=f"at-join-{armed}")
    if armed:
        refused(result, argv)
        assert "MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS" in result.stderr
        assert "--hold-at join" in result.stderr
    else:
        # Not armed and asking early is a normal observe-only run: the refusal belongs
        # to the driver's own combination, not to the phase alone.
        assert result.returncode == 0, result.stderr
        assert argv == OBSERVE_ONLY_JOINER_ARGV

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")
    # The base commit's host-side handling of the phase, unchanged: it says the hold was
    # refused and that there is no walk to wait for, and the walk wait still reads the
    # phase out of its own condition.
    assert (
        "domain: this run asks for its hold at the join, so it is refused and there is"
        " no walk to wait for" in text
    )
    assert '&& "${hold_at}" != "join" ]]; then' in text
    # And the phase is still read from the run's own arguments rather than from a knob
    # this card could set.
    assert '--hold-at) hold_at="${argument}" ;;' in text
    # The driver never emits the phase flag, so a joining run cannot ask early through
    # it whatever its own arguments say.
    assert "--hold-at" not in " ".join(argv)


def test_the_printout_reads_the_same_ask_back_and_launches_nothing(
    tmp_path: Path,
) -> None:
    """`MINEKIN_DOMAIN_JOIN_CONTROL_PRINT` prints the line and stops, after the bounds.

    The readback has to sit below the composition or it would be a claim about a line
    the run might never start, and it has to stop rather than fall through: an operator
    asking what a joining client would be handed is not asking for a JVM.
    """

    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_CONTROL_PRINT": "1"},
        wiring=True,
        tag="print-observe-only",
    )
    assert result.returncode == 0, result.stderr
    assert argv == [], f"a printout printed on stdout as well: {argv}"
    prefix = "domain:   "
    printed = [
        line[len(prefix) :]
        for line in result.stderr.splitlines()
        if line.startswith(prefix)
    ]
    assert printed == OBSERVE_ONLY_JOINER_ARGV
    assert "a printout launches nothing" in result.stderr

    # Armed and in range, the printout carries the ask; unset, it carries none.
    result, _ = drive_joiner_control(
        tmp_path,
        env={
            "MINEKIN_DOMAIN_JOIN_CONTROL_PRINT": "1",
            "MINEKIN_DOMAIN_JOIN_LOOK_YAW": "22.5",
            "MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS": "2",
        },
        wiring=True,
        tag="print-armed",
    )
    assert result.returncode == 0, result.stderr
    assert "--look-yaw-degrees" in result.stderr
    assert "--hold-forward-seconds" in result.stderr

    # A refusal comes first: an out-of-bounds ask is never printed as though it were the
    # line a run would start.
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_CONTROL_PRINT": "1", "MINEKIN_DOMAIN_JOIN_LOOK_YAW": "90"},
        wiring=True,
        tag="print-out-of-bounds",
    )
    assert result.returncode != 0
    assert argv == []
    assert "would be started with" not in result.stderr

    # `0` and empty mean "not asked", so a delivered-but-empty name cannot turn a
    # normal run into a printout that exits before the world is started.
    for spelling in ("", "0"):
        result, argv = drive_joiner_control(
            tmp_path,
            env={
                "MINEKIN_DOMAIN_JOIN_CONTROL_PRINT": spelling,
                "MINEKIN_DOMAIN_JOIN_LOOK_YAW": "22.5",
            },
            wiring=True,
            tag=f"print-{spelling or 'empty'}",
        )
        assert result.returncode == 0, result.stderr
        assert argv == []
        assert "a printout launches nothing" not in result.stderr
        # The ask is still composed and still bounded on a run that does not print.
        assert result.stderr == ""

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")
    # The printout is answered below the composition and above anything that starts,
    # and it reads the one name its own top-of-file read hands it.
    assert 'join_control_print="${MINEKIN_DOMAIN_JOIN_CONTROL_PRINT:-}"' in text
    assert text.index("\ncompose_joiner_control_args\n") < text.index(
        "a printout launches nothing"
    )
    assert text.index("a printout launches nothing") < text.index("trap stop_the_server EXIT")


def joiner_control_region_mutated(region: str, needle: str, substitute: str) -> str:
    """The shipped region with the `exit 2` after `needle` replaced, in the real bytes.

    Located rather than transcribed: the anchor is searched for in the bytes the run
    executes, so a refusal that moved, changed wording or lost its `exit 2` between
    commits fails here with a `ValueError` instead of quietly reversing nothing.
    """

    anchor = region.index(needle) + len(needle)
    stop = region.index("exit 2", anchor)
    mutated = region[:stop] + substitute + region[stop + len("exit 2") :]
    assert mutated != region, f"the mutation at {needle!r} changed nothing"
    return mutated


def test_the_joiner_control_driver_is_not_an_always_true_claim(tmp_path: Path) -> None:
    """Delete a guard from a copy of the shipped bytes and its refusal stops happening.

    Every reading above is taken from the shipped region, so each of them would also
    pass on a region that had lost the guard it is meant to prove — a test that reads
    `rc=2` cannot tell a refusal from a crash. The reversals below are therefore
    measured the same way as the greens: a copy of the shipped bytes with exactly one
    deletion or substitution, driven through the same bash path, with the outcome the
    shipped bytes refuse printed next to the outcome the copy produces.
    """

    text = (RUNNER / "domain.sh").read_text(encoding="utf-8")
    region = joiner_control_region(text, JOINER_CONTROL_DRIVER_END)

    # Green on the shipped bytes first: a reading that is false on both sides of a
    # mutation says nothing about the mutation.
    result, argv = drive_joiner_control(tmp_path, region=region, tag="rv-shipped-unarmed")
    assert (result.returncode, argv) == (0, OBSERVE_ONLY_JOINER_ARGV)
    for ask, value in (
        ("MINEKIN_DOMAIN_JOIN_LOOK_YAW", "90"),
        ("MINEKIN_DOMAIN_JOIN_LOOK_PITCH", "31"),
        ("MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS", "10"),
    ):
        result, argv = drive_joiner_control(
            tmp_path, env={ask: value}, region=region, tag=f"rv-shipped-{ask}"
        )
        refused(result, argv)
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "10"},
        joiner="",
        region=region,
        tag="rv-shipped-no-joiner",
    )
    refused(result, argv)
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS": "1"},
        hold_at="join",
        region=region,
        tag="rv-shipped-at-join",
    )
    refused(result, argv)

    # RV-1: the bound's `exit 2` turned into a bare `:`. The message still prints, so a
    # check that only looked for a name on stderr would stay green; what the copy says is
    # that a yaw of 90 went out on the joining client's line.
    reported_only = joiner_control_region_mutated(
        region, "MINEKIN_DOMAIN_JOIN_LOOK_YAW=%s is outside the bound", ":"
    )
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "90"},
        region=reported_only,
        tag="rv-1-warning",
    )
    assert result.returncode == 0, result.stderr
    assert "outside the bound" in result.stderr
    assert argv[-2:] == ["--look-yaw-degrees", "90"]

    # RV-2: the same refusal turned into the clamp this card refused. Nothing is
    # refused, nothing is printed as a failure, and the ask that reaches the line is not
    # the ask that was made — a run that reads as a 45-degree turn nobody asked for.
    clamped = joiner_control_region_mutated(
        region,
        "MINEKIN_DOMAIN_JOIN_LOOK_YAW=%s is outside the bound",
        'yaw="${joiner_control_max_yaw}"',
    )
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "90"},
        region=clamped,
        tag="rv-2-clamp",
    )
    assert result.returncode == 0, result.stderr
    assert argv[-2:] == ["--look-yaw-degrees", "45"]

    # RV-3: the joiner-only guard turned into a report. The armed ask now composes a
    # line for a joining client this run does not have, which is the shape of a knob
    # that silently does nothing.
    no_joiner_guard_off = joiner_control_region_mutated(
        region, "refused rather than carried as a knob that does nothing", ":"
    )
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "10"},
        joiner="",
        region=no_joiner_guard_off,
        tag="rv-3-no-joiner",
    )
    assert result.returncode == 0, result.stderr
    assert argv[-2:] == ["--look-yaw-degrees", "10"]

    # RV-4: the phase guard off. A joining ask whose moment is refused by design now
    # goes out anyway, and the run would wait on a walk that was never granted.
    phase_guard_off = joiner_control_region_mutated(
        region, "there is none to drive it from, so the ask is refused", ":"
    )
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS": "1"},
        hold_at="join",
        region=phase_guard_off,
        tag="rv-4-at-join",
    )
    assert result.returncode == 0, result.stderr
    assert argv[-2:] == ["--hold-forward-seconds", "1"]

    # RV-5: the default-off half. Taking out only the early return changes nothing —
    # measured below, and worth saying: the per-flag conditions guard the same door, so
    # the property is held twice and an unarmed run still composes the old line. It takes
    # both gone before a control flag reaches a run that asked for nothing, and the
    # identity reading above is what would catch it.
    never_off = region.replace(
        '    if [ -z "${yaw}" ] && [ -z "${pitch}" ] && [ -z "${forward}" ]; then\n'
        "        return 0\n"
        "    fi\n",
        "",
        1,
    )
    assert never_off != region
    result, argv = drive_joiner_control(tmp_path, region=never_off, tag="rv-5a-early-return")
    assert result.returncode == 0, result.stderr
    assert argv == OBSERVE_ONLY_JOINER_ARGV, (
        "the early return turned out to be the only guard; the comment above is wrong"
    )

    always_on = never_off.replace(
        '    if [ -n "${yaw}" ]; then\n'
        '        joiner_control_args+=(--look-yaw-degrees "${yaw}")\n'
        "    fi\n",
        '    joiner_control_args+=(--look-yaw-degrees "${yaw}")\n',
        1,
    )
    assert always_on != never_off
    result, argv = drive_joiner_control(tmp_path, region=always_on, tag="rv-5b-always-on")
    assert result.returncode == 0, result.stderr
    assert argv != OBSERVE_ONLY_JOINER_ARGV
    assert "--look-yaw-degrees" in argv

    # And the two refusals that are not mutations of a guard: the same ask with the
    # driver's own bound kept is refused on the shipped bytes and accepted at the bound,
    # so the number is what the message says it is.
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "45"},
        region=region,
        tag="rv-bound-inclusive",
    )
    assert result.returncode == 0, result.stderr
    assert argv[-2:] == ["--look-yaw-degrees", "45"]
    result, argv = drive_joiner_control(
        tmp_path,
        env={"MINEKIN_DOMAIN_JOIN_LOOK_YAW": "45.0001"},
        region=region,
        tag="rv-bound-exclusive",
    )
    refused(result, argv)
