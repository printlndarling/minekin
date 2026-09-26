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
import tomllib
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
    are the point of the shape: it *adds* a reading and changes none of the three names,
    and it leaves the sealer's own measurement alone rather than passing itself off as it.
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
    assert '"${joiner_launch_wrapper[@]}" \\\n        env MINEKIN_KIN_ID="${joiner}"' in text
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
    assert head < text.index('"${joiner_launch_wrapper[@]}" \\\n        env MINEKIN_KIN_ID')
    # And the reading happens before the client is handed anything at all, not after it
    # dies: the launch site is the next thing the script does.
    assert head < text.index("joiner_pid=$!")

    # A reading, not a fix: nothing here exports, unsets or defaults any of the three, so
    # the one `export DISPLAY` left in the script is still the harness pointing its own
    # session at the screen it owns.
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
    the classifier would read as a measured screen, and nothing in the readout exports,
    unsets or defaults any of the three items.
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
