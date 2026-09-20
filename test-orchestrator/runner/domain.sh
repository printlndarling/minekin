#!/usr/bin/env bash
#
# Bring up the isolated vanilla domain and run one session against it.
#
# Both halves have to run in *this* container. The frozen Server Profile schema
# admits only the two loopback literals, and loopback is per container, so a
# server started anywhere else is unreachable however correct its address is.
# That is why this is a mode of the runner rather than two runners.
#
# Usage (inside the runner image, started by `run.sh domain`):
#   domain.sh session start --profile /src/.../bundle.json --server-profile /src/.../server.json
#
# Environment:
#   MINEKIN_USERNAME         the account to whitelist (default Kin)
#   MINEKIN_DOMAIN_SECONDS   how long the session may run (default 240)
set -euo pipefail

seconds="${MINEKIN_DOMAIN_SECONDS:-240}"
player="${MINEKIN_USERNAME:-Kin}"
summon="${MINEKIN_DOMAIN_SUMMON:-}"
probe="${MINEKIN_DOMAIN_PROBE:-}"
kill="${MINEKIN_DOMAIN_KILL:-}"
kick="${MINEKIN_DOMAIN_KICK:-}"
silence="${MINEKIN_DOMAIN_SILENCE:-}"
look="${MINEKIN_DOMAIN_LOOK:-}"
kill_core="${MINEKIN_DOMAIN_KILL_CORE:-}"
# The world killed outright, while the Kin is in it. A different fault from a
# kick, which is the server *saying* goodbye: a killed server says nothing, and
# the client learns of it only because its socket stopped working.
kill_server="${MINEKIN_DOMAIN_KILL_SERVER:-}"
no_server="${MINEKIN_DOMAIN_NO_SERVER:-}"
still="${MINEKIN_DOMAIN_STILL:-}"
# A bounded soak: how long the session is left running, and how often the two
# processes are sampled. Zero means no soak, which is what every run before this
# did — a soak is a thing a run asks for, not a thing every run pays for.
soak_seconds="${MINEKIN_DOMAIN_SOAK_SECONDS:-0}"
soak_interval="${MINEKIN_DOMAIN_SOAK_INTERVAL:-10}"
case "${soak_seconds}" in
    ''|*[!0-9]*)
        printf 'domain: MINEKIN_DOMAIN_SOAK_SECONDS must be a non-negative integer, got %q\n' \
            "${soak_seconds}" >&2
        exit 2
        ;;
esac
case "${soak_interval}" in
    ''|*[!0-9]*|0)
        printf 'domain: MINEKIN_DOMAIN_SOAK_INTERVAL must be a positive integer, got %q\n' \
            "${soak_interval}" >&2
        exit 2
        ;;
esac
# The reviewed case this run is an execution of, if it is one. Naming it is what
# turns a run into evidence: the sealer attributes the bundle to a case
# definition and judges the case's assertions, and it does neither for a run
# nobody said was a case. Unset means nothing about this run changes.
case_id="${MINEKIN_DOMAIN_CASE:-}"
# A target that accepts a connection and never answers. The vanilla server cannot
# produce that — it answers — and nothing listening produces a refusal instead,
# which is a different path. This one exists to watch Core give up on its own
# deadline, and it is the only scenario where the client is expected to *hang*.
black_hole="${MINEKIN_DOMAIN_BLACK_HOLE:-}"
# A server that starts and then refuses the Kin: the whitelist stays empty, and
# `white-list=true` with `enforce-whitelist=true` does the rest. This is the one
# failure where the client gets all the way into the login handshake and the
# *server* is what says no.
not_whitelisted="${MINEKIN_DOMAIN_NOT_WHITELISTED:-}"
# A block three in front of the Kin, and the server asked what state it is in. A
# use that changes nothing is a key held at nothing, so the scene puts something
# in front that can change and the reading is the server's own.
#
# It is a note block and not a lever, and three blocks out rather than two, for
# measured reasons given in full in the tool's own `use_target_command`: this run
# also measures a walk, a walk carries the look along itself, and what is wanted
# is a block the ray cannot miss at any distance — one the Kin walks into and
# stops against, which is also the walk-and-stop this harness waits for.
use_target="${MINEKIN_DOMAIN_USE_TARGET:-}"
# How often the server is asked about the Kin. A look is over within a second
# of the join, so a run that wants a reading on both sides of it asks more
# often than the default — the pair is what shows a heading changed.
probe_seconds="${MINEKIN_DOMAIN_PROBE_SECONDS:-5}"
silenced=0
#: Set when the harness itself failed to do what the run asked for — a fault
#: that was not injected, or a seal that did not happen. A run that did not do
#: what it says it does must not exit like one that did.
injection_failed=0
runs=/data/server-runs

# The reviewed case, as a file, named once here rather than at the point of
# sealing: the fault helper cross-checks the case it is told about against this
# file, so the two have to be the same file.
case_file=""
if [ -n "${case_id}" ]; then
    case_file="/src/tests/fixtures/cases/$(printf '%s' "${case_id}" | tr '[:upper:]' '[:lower:]').json"
fi

# The record of the fault this run injected. One run seals one record, so a run
# that asks for two faults at once is refused rather than allowed to report one
# of them: there would be no way to say later which of the two the record is.
fault_path=/tmp/domain-fault-injection.json
fault_role=""
if [[ -n "${kill_core}" && -n "${kill_server}" ]]; then
    printf 'domain: this run asks for two faults at once; one run seals one record\n' >&2
    exit 2
fi

# Capture a process identity when this runner still owns the pid it just
# started.  Passing only the pid later would let a dead wrapper's reused number
# become the trust root for an unrelated /proc subtree.
read_process_identity() {
    python - "$1" <<'PY'
import os
import sys
from pathlib import Path

pid = int(sys.argv[1])
raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="strict")
closing = raw.rfind(")")
if closing < 0:
    raise SystemExit(2)
fields = raw[closing + 2 :].split()
if len(fields) < 20:
    raise SystemExit(2)
print(fields[19], os.readlink(f"/proc/{pid}/ns/pid"))
PY
}

# Kill this run's own process, and keep the record that says so.
#
# The target is named, not searched for. Every way this used to be done here
# guessed: `pkill -f "minekin_core session start"` matched any Core in the
# container — including the `session stop` this script runs later — and
# `pgrep -P <tool> | head -1` assumed the tool's first child was the JVM. Neither
# could say which process it had killed, so neither could be evidence. The helper
# is given a pid this run already holds and refuses unless exactly one of that
# process's descendants is the role's own command line; it re-reads the identity
# before signalling, and it watches for that identity to leave /proc afterwards.
#
# Anything other than a confirmed kill fails the run. `set +e` around the call
# because the helper's own exit status is a result to read, not a crash to die on.
inject_fault() {
    local root_pid="$1"
    local role="$2"
    local root_starttime_ticks="$3"
    local root_pid_namespace_inode="$4"
    set +e
    python /src/tools/inject_fault.py inject \
        --root-pid "${root_pid}" \
        --root-starttime-ticks "${root_starttime_ticks}" \
        --root-pid-namespace-inode "${root_pid_namespace_inode}" \
        --role "${role}" \
        --case "${case_id}" \
        --case-file "${case_file}" \
        --ledger "${ledger}" \
        --kin-id "${kin_id}" \
        --run-id "${run_id}" \
        --session-id "${session_id}" \
        --generation "${generation}" \
        --record "${fault_path}" >/tmp/domain-fault-injection.log 2>&1
    local helper_status=$?
    set -e
    printf 'domain: the fault helper said ' >&2
    tr -d '\n' </tmp/domain-fault-injection.log >&2 || true
    printf '\n' >&2
    if [ "${helper_status}" -ne 0 ] || [ ! -s "${fault_path}" ]; then
        printf 'domain: the fault could not be recorded, so nothing here can be attributed\n' >&2
        return 1
    fi
    local outcome
    outcome=$(python -c 'import json,sys;print(json.load(open(sys.argv[1]))["outcome"])' \
        "${fault_path}" 2>/dev/null || true)
    if [ "${outcome}" != "INJECTED" ]; then
        printf 'domain: the fault was not injected (%s): ' "${outcome:-unreadable}" >&2
        python -c 'import json,sys;print(",".join(json.load(open(sys.argv[1]))["reasons"]))' \
            "${fault_path}" >&2 2>/dev/null || true
        printf '\n' >&2
        return 1
    fi
    fault_role="${role}"
    return 0
}

# What this run was asked to do, read from the command that was given to it: the
# harness waits for what the session was told to do, not for what the operator
# happened to export as well. The two profiles come out the same way, because
# sealing needs to name the documents this run was actually given rather than
# the ones this script would have chosen.
hold_requested=0
# The phase the run asks at, read from its own arguments rather than from another
# switch: a run that asks at the join is *refused* (the world is not playable
# yet), so there is no walk to wait for and a harness that waited for one would
# spend its whole budget on a hold that was correctly never granted.
hold_at="playable"
profile=""
server_profile=""
connection_timeout=""
previous=""
for argument in "$@"; do
    case "${argument}" in
        --hold-forward-seconds) hold_requested=1 ;;
    esac
    case "${previous}" in
        --profile) profile="${argument}" ;;
        --server-profile) server_profile="${argument}" ;;
        --connection-timeout-seconds) connection_timeout="${argument}" ;;
        --hold-at) hold_at="${argument}" ;;
    esac
    previous="${argument}"
done


# Empty means "the world is as vanilla generated it", which is what every run
# did before this existed — so it stays optional rather than becoming a required
# argument with an empty value.
summon_args=()
if [[ -n "${summon}" ]]; then
    summon_args=(--summon "${summon}")
fi

# A run that is supposed to move the Kin has to be able to ask the server where
# the Kin is: the server does not log where anyone walks, and the acceptance for
# input is the server's own observation of the displacement.
probe_args=()
if [[ -n "${probe}" ]]; then
    probe_args=(--probe-player "${probe}" --probe-every-seconds "${probe_seconds}")
fi
if [[ -n "${use_target}" ]]; then
    probe_args+=(--use-target)
fi

# And a run that is verifying the release a death causes has to be able to kill the
# Kin, which only the server can do.
kill_args=()
if [[ -n "${kill}" ]]; then
    kill_args=(--kill-player "${kill}")
fi

# Same for the other ending a server can start: a kick, which ends the session
# while the client keeps running.
kick_args=()
if [[ -n "${kick}" ]]; then
    kick_args=(--kick-player "${kick}")
fi

# A run that names no server profile joins no world, and there is nothing for a
# server to do: starting one would add half a minute and a world to the data
# volume for a run that will never look at either. What it must not do is leave
# the harness unable to say which kind of run this was — the session's own
# arguments say it, and everything below reads them.
server_pid=""
server_starttime_ticks=""
server_pid_namespace_inode=""
server_directory=""
stop_the_server() {
    # SIGTERM, not SIGINT. A background job of a non-interactive shell inherits
    # SIGINT set to ignore, so `kill -INT` on this process did nothing at all and
    # the server ran on until the container was killed — eight minutes of a run
    # that had already finished. Measured in the runner image: `SIGINT SIG_IGN`,
    # `SIGTERM SIG_DFL`, and the tool installs a handler for both now, so either
    # one reaches the server's own `stop` command and the world is saved.
    if [ -n "${server_pid}" ]; then
        kill -TERM "${server_pid}" 2>/dev/null || true
        wait "${server_pid}" 2>/dev/null || true
    fi
}
trap stop_the_server EXIT

if [ -n "${server_profile}" ] && [ -n "${black_hole}" ]; then
    # Something is listening on the address the profile names and it will never
    # answer. Started before the client so the port is taken when the client
    # dials, and its log is kept because "nobody ever connected" is a fact this
    # scenario has to be able to see.
    python /src/tools/run_silent_listener.py --server-profile "${server_profile}" \
        >/tmp/domain-black-hole.log 2>&1 &
    server_pid=$!
    printf 'domain: a black hole is listening; nothing will answer\n' >&2
elif [ -n "${server_profile}" ]; then
    # One fresh directory per run, numbered past everything already there: a run
    # directory is evidence and is only ever appended to.
    n=1
    while [ -e "${runs}/run-${n}" ]; do n=$((n + 1)); done
    server_directory="${runs}/run-${n}"

    # The tool's own chatter goes to /tmp rather than into the run directory: it
    # creates that directory itself and refuses a non-empty one, which is the
    # check that keeps an earlier run's world and log from being written over.
    # The whitelist is what this run is about when the Kin is meant to be
    # refused: omitting the name leaves it empty, and the server's own
    # `usercache.json` and log are then the record of the refusal.
    allow_args=(--allow-player "${player}")
    if [ -n "${not_whitelisted}" ]; then
        allow_args=()
    fi
    python /src/tools/run_controlled_server.py \
        --directory "${server_directory}" \
        --jar /server/server.jar \
        --accept-eula \
        "${allow_args[@]}" \
        "${summon_args[@]}" \
        "${probe_args[@]}" \
        "${kill_args[@]}" \
        "${kick_args[@]}" \
        --keep-running >/tmp/domain-server.log 2>&1 &
    server_pid=$!

    printf 'domain: server run directory %s\n' "${server_directory}" >&2
else
    printf 'domain: no server profile; this run joins no world\n' >&2
fi

if [ -n "${server_pid}" ]; then
    if ! read -r server_starttime_ticks server_pid_namespace_inode \
            <<<"$(read_process_identity "${server_pid}" 2>/dev/null)" ||
            [ -z "${server_starttime_ticks}" ] || [ -z "${server_pid_namespace_inode}" ]; then
        printf 'domain: the server supervisor identity could not be captured\n' >&2
        exit 2
    fi
fi

# The client is not started until the server says it is ready. A refused
# connection is not a test of the admission path, it is a test of the clock. A
# run with no server has no clock to wait for.
if [ -n "${server_pid}" ]; then
    for _ in $(seq 1 480); do
        if [ -n "${black_hole}" ]; then
            if grep -q '"listening"' /tmp/domain-black-hole.log 2>/dev/null; then
                break
            fi
        elif grep -q 'Done (' "${server_directory}/server.log" 2>/dev/null; then
            break
        fi
        if ! kill -0 "${server_pid}" 2>/dev/null; then
            printf 'domain: the server exited before it reported ready\n' >&2
            tail -n 20 /tmp/domain-server.log >&2 || true
            exit 1
        fi
        sleep 1
    done
    if [ -n "${black_hole}" ]; then
        if ! grep -q '"listening"' /tmp/domain-black-hole.log 2>/dev/null; then
            printf 'domain: the black hole never reported that it was listening\n' >&2
            exit 1
        fi
        printf 'domain: the black hole is ready\n' >&2
    else
        if ! grep -q 'Done (' "${server_directory}/server.log" 2>/dev/null; then
            printf 'domain: the server never reported ready\n' >&2
            exit 1
        fi
        printf 'domain: server ready\n' >&2
    fi
fi

# A run whose target is not listening. The server is stopped again as soon as it
# has proved it can start, which is the cheapest way to get a refused connection:
# the client still connects to the address in the frozen profile, and nothing is
# there. It is the one failure the Bridge used to say nothing about, because it
# never reaches a login handler.
if [[ -n "${no_server}" ]]; then
    stop_the_server
    printf 'domain: the server has been stopped; nothing is listening\n' >&2
fi

# The session is stopped rather than timed out. A killed CLI never prints the run
# document, and the document is the only place Core's own verdict on the first
# snapshot exists — how many entities it admitted and how many it refused. Ending
# the run with a window threw those numbers away, so a run could show what the
# Bridge sent and never what Core made of it.
#
# It goes *inside* `xvfb-run`, not outside: signal it from the outside and the
# signal lands on the X server, which takes the client's display away and kills
# the client through a path that has nothing to do with the session. Measured —
# the client's stderr said `X connection to :99 broken`.
set +e
xvfb-run -a --server-args="-screen 0 1280x720x24" \
    python -m minekin_core "$@" >/tmp/domain-session.json &
session_pid=$!
if ! read -r session_starttime_ticks session_pid_namespace_inode \
        <<<"$(read_process_identity "${session_pid}" 2>/dev/null)" ||
        [ -z "${session_starttime_ticks}" ] || [ -z "${session_pid_namespace_inode}" ]; then
    printf 'domain: the session supervisor identity could not be captured\n' >&2
    exit 2
fi
set -e

# The wait is for the join, not for a duration: a clock long enough for this
# machine is a clock that is wrong on a slower one.
#
# Asked of the ledger rather than of `session status`, and asked as "was a
# playable recorded after this run started" rather than "is it the last thing
# recorded". The status projection only shows the last event type, and once a
# run holds the input, `InputLeaseGranted` follows `PlayableEstablished` within
# milliseconds — so the last-event test is true for a window too small to poll,
# and the first version of this spent its whole budget waiting for a state the
# ledger had already recorded. Measured.
# The ledger is where every fact below comes from, so a run may only ever read its
# own. Taking the first of a glob was how one Kin's database could be read as
# another's: `head -1` over several candidates silently picks one, and everything
# downstream — the run id, the fault record's attribution, the seal — would then be
# about a different run. So the number of candidates is checked, and anything other
# than exactly one fails closed rather than guessing.
ledgers=(/data/kin/*/kin.sqlite3)
if [ "${#ledgers[@]}" -ne 1 ] || [ ! -f "${ledgers[0]}" ]; then
    printf 'domain: this run cannot name its ledger (found %s), so nothing here can be attributed\n' \
        "${#ledgers[@]}" >&2
    exit 2
fi
ledger="${ledgers[0]}"
# The run's own attribution — the Kin, the session and the generation — comes from
# the ledger's *rows* below, once the run id is known, and is empty until then. It
# is deliberately not read from the path the database sits at: the helper compares
# the two, and a ledger filed under one Kin whose rows say another is not evidence
# for either.
kin_id=""
session_id=""
generation=""
read_position() {
    /opt/sqlite/bin/sqlite3 "${ledger}" 'select coalesce(max(position), 0) from event;' 2>/dev/null ||
        true
}
# The horizontal positions the server has reported, one per line, newest last.
# Y is dropped deliberately: a Kin standing still at spawn can be reported twice
# with different Y, so counting any two positions would accept a fall for a walk.
#
# A log with no positions in it yet is the normal state of a run whose Kin has
# not been asked, not a failure: grep exits 1 for "no match" and `pipefail` is
# set, so an unguarded pipeline here ends the run the moment the probe has
# nothing to report.
horizontal_positions() {
    { grep -o 'has the following entity data: \[[^]]*\]' \
        "${server_directory}/server.log" 2>/dev/null || true; } |
        sed 's/.*\[//; s/\]//; s/[df]//g' |
        awk -F', *' 'NF == 3 {print $1","$3}'
}

# The height the server has reported, one per line. A jump is the only thing that
# shows up here and nowhere else: the Kin leaves the ground and comes back, at the
# same place.
reported_heights() {
    { grep -o 'has the following entity data: \[[^]]*\]' \
        "${server_directory}/server.log" 2>/dev/null || true; } |
        sed 's/.*\[//; s/\]//; s/[df]//g' |
        awk -F', *' 'NF == 3 {print $2}'
}

# The rotation the server has reported, one yaw per line. Two components rather
# than three is what tells a rotation reading from a position reading: the server
# answers both with the same words and only the shape differs.
reported_yaws() {
    { grep -o 'has the following entity data: \[[^]]*\]' \
        "${server_directory}/server.log" 2>/dev/null || true; } |
        sed 's/.*\[//; s/\]//; s/[df]//g' |
        awk -F', *' 'NF == 2 {print $1}'
}
baseline=$(read_position)
baseline=${baseline:-0}
playable=0
if [ -n "${not_whitelisted}" ]; then
    # What this run is about is a refusal, and the refusal is a ledger fact: the
    # Bridge classifies the login failure and Core records the phase and the
    # reason together. Waiting for a world this run will never join would spend
    # the budget on something that cannot happen.
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='SessionInterrupted' and payload_json like '%FAILED%' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the session was interrupted, as this run expected\n' >&2
    else
        printf 'domain: the session was never interrupted within %ss\n' "${seconds}" >&2
    fi
elif [ -n "${black_hole}" ]; then
    # Two waits, because two things have to happen before this run has anything
    # to say. First the client has to boot and handshake — that takes as long as
    # it takes, and it is the same wait a run with no world uses. Then Core's own
    # deadline has to pass, and that is a duration the operator named on the
    # command line: waiting a little longer than it is deliberate, because the
    # give-up being watched has to happen while the harness is still watching.
    handshake_by=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${handshake_by}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='BridgeHelloAccepted' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the handshake was recorded; the client is about to dial\n' >&2
        answer_by=$((SECONDS + ${connection_timeout:-30} + 15))
        if [ "${answer_by}" -gt $((SECONDS + seconds)) ]; then
            answer_by=$((SECONDS + seconds))
        fi
        while [ "${SECONDS}" -lt "${answer_by}" ]; do
            kill -0 "${session_pid}" 2>/dev/null || break
            sleep 1
        done
    else
        printf 'domain: no handshake was recorded within %ss\n' "${seconds}" >&2
    fi
    if grep -q '"accepted"' /tmp/domain-black-hole.log 2>/dev/null; then
        printf 'domain: the client dialled the black hole and got nothing\n' >&2
    else
        printf 'domain: nothing ever connected to the black hole\n' >&2
    fi
elif [ -z "${server_profile}" ]; then
    # A run with no world to join never becomes playable, and waiting for it
    # would spend the whole budget on a state that cannot happen. What it does do
    # is handshake — and that is what waited for here, on Core's own ledger,
    # because the Bridge writes nothing at all to the client's log in a session
    # that never joins (measured).
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='BridgeHelloAccepted' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the handshake was recorded by Core\n' >&2
    else
        printf 'domain: no handshake was recorded within %ss\n' "${seconds}" >&2
    fi
else
    deadline=$((SECONDS + seconds))
    ended='the bound expired'
    for _ in $(seq 1 "${seconds}"); do
        [ "${SECONDS}" -lt "${deadline}" ] || break
        # The ledger is read before the session is asked whether it is alive, and
        # that order is the point: a session that died is exactly a session whose
        # last ledger rows are the ones worth reading, and asking `kill -0` first
        # reports "never became playable" about a run whose ledger says otherwise.
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='PlayableEstablished' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        if ! kill -0 "${session_pid}" 2>/dev/null; then
            ended='the session exited first'
            break
        fi
        sleep 1
    done
    # Said out loud either way. A bound that expires quietly turns "the Kin never
    # joined" into "the harness moved on", and the two need different answers: this
    # one has already done it once, on a run whose client took three minutes to
    # boot because the asset materialisation was cold. Which of the two happened
    # is said too, because "it exited" and "it was still starting" are answered by
    # reading different things.
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the session is playable\n' >&2
    else
        printf 'domain: the session never became playable within %ss (%s)\n' \
            "${seconds}" "${ended}" >&2
    fi
fi

# Which run this is, from the ledger rather than from the document: a run whose
# Core is killed never prints one, and the ledger is the record that survives it.
# The first event this run recorded is the launcher's own account of starting it.
run_id=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
    "select run_id from event where position > ${baseline} order by position limit 1;" \
    2>/dev/null || true)
printf 'domain: this run is %s\n' "${run_id}" >&2

# The Kin, session and generation this run is in, from the same record and read the
# same way. A fault record has to name the run it is about, and both the helper and
# the sealer cross-check that attribution — so a value invented here would be caught
# rather than quietly accepted. A value that cannot be read is left empty (or zero,
# for the generation), which the helper refuses to record: the run still ends with a
# reason rather than a record naming a Kin or a session that never existed.
attribution=$(/opt/sqlite/bin/sqlite3 -separator ' ' "${ledger}" \
    "select coalesce(kin_id,''), coalesce(json_extract(payload_json,'\$.session_id'),''), \
            coalesce(json_extract(payload_json,'\$.generation'),'') \
     from event where run_id='${run_id}' and event_type='SessionProcessStarted' \
     order by position limit 1;" 2>/dev/null || true)
read -r kin_id session_id generation <<<"${attribution}" || true
case "${generation}" in
    ''|*[!0-9]*) generation=0 ;;
esac

# The Bridge's own watchdog, which is the guarantee that keys come up even when
# nobody is left to ask. §12 puts it in the process holding the keys, and it needs
# nobody's permission; the Core-side watchdog is the second layer. So the run
# takes Core away — SIGSTOP rather than a kill, because the session has to survive
# to be stopped afterwards — once the Kin is walking, and lets the walk wait below
# decide whether the server saw it stop.
if [[ -n "${silence}" ]]; then
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        if [ "$(horizontal_positions | sort -u | wc -l)" -ge 2 ]; then
            # -f with the command, not the wrapper: xvfb-run is between this
            # script and the CLI, and stopping the wrapper would stop nothing.
            if pkill -STOP -f "minekin_core session start"; then
                silenced=1
                printf 'domain: Core has gone quiet; the Bridge should let go\n' >&2
            else
                printf 'domain: could not find Core to make it quiet\n' >&2
            fi
            break
        fi
        sleep 1
    done
fi

# A run that was asked to hold a key waits for the movement itself, because
# the acceptance for input is the server's own observation of it. What counts as
# movement is *horizontal*: a Kin standing still at spawn can still be reported
# twice with different Y, so counting any two positions would accept a fall at
# spawn as a walk.
#
# And what it waits for is the walk *ending*: the last two reports have to agree,
# with two different places before them. That is the difference between "the hold
# was released and the session carried on" and "the session ended", which look
# identical in a log that stops — and it is the whole point of a lease deadline,
# so a run that never sees it has not verified one.
#
# Its own budget rather than what is left of the join's: a slow boot must not
# spend the walk's allowance, which is how the first version of this reported a
# Kin that had walked seventeen blocks as one that never moved.
#
# A run that asks for its hold at the join is left out of this entirely, and the
# reason is the case it exists for: the answer is *no*, so there is nothing to
# wait for. Said out loud rather than passed over, because a harness that skipped
# a wait silently is one whose reader cannot tell a walk that did not happen from
# one it stopped looking for.
if [ "${hold_at}" = "join" ]; then
    printf 'domain: this run asks for its hold at the join, so it is refused and there is no walk to wait for\n' >&2
fi
if [[ -n "${probe}" && "${hold_requested}" -eq 1 && -z "${kill_core}" && -z "${kill_server}" && "${hold_at}" != "join" ]]; then
    walked=0
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        positions=$(horizontal_positions)
        distinct=$(printf '%s\n' "${positions}" | sort -u | wc -l)
        settled=$(printf '%s\n' "${positions}" | tail -n 2 | sort -u | wc -l)
        if [ "${distinct}" -ge 2 ] && [ "${settled}" -eq 1 ]; then
            # When the run is testing the Bridge's own watchdog, a stop only
            # counts if Core had actually gone quiet first: a Kin that stopped for
            # any other reason would otherwise be read as a watchdog release.
            if [ -z "${silence}" ] || [ "${silenced}" -eq 1 ]; then
                walked=1
                break
            fi
        fi
        sleep 1
    done
    if [ "${walked}" -eq 1 ]; then
        heights=$(reported_heights)
        span=$(printf '%s\n' "${heights}" | sort -n |
            awk 'NR == 1 { lo = $1 } { hi = $1 } END { printf "%.2f", hi - lo }')
        printf 'domain: the server saw the Kin walk and stop; its height moved through %s blocks\n' \
            "${span}" >&2
    else
        printf 'domain: the server never saw the Kin walk and stop within %ss\n' "${seconds}" >&2
    fi
fi

# Core comes back before anything else is asked of it: a stopped CLI cannot notice
# the client leaving, and `session stop` would have nothing that reads its answer.
if [ "${silenced}" -eq 1 ]; then
    pkill -CONT -f "minekin_core session start" || true
    printf 'domain: Core is running again\n' >&2
fi

if [[ -n "${look}" ]]; then
    looked=0
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        yaws=$(reported_yaws)
        distinct=$(printf '%s\n' "${yaws}" | sort -u | wc -l)
        places=$(horizontal_positions | sort -u | wc -l)
        # Two different headings and still one place: the turn happened and it was
        # a turn. A look is not a movement, so a Kin that also teleported would
        # show up here as a second place.
        if [ "${distinct}" -ge 2 ] && [ "${places}" -le 1 ]; then
            turned=$(printf '%s\n' "${yaws}" |
                awk 'NR == 1 { first = $1 } { last = $1 } END { d = last - first; if (d < 0) d = -d; printf "%.3f", d }')
            printf 'domain: the server saw the Kin turn by %s degrees (asked for %s)\n' \
                "${turned}" "${look}" >&2
            if awk -v turned="${turned}" -v asked="${look}" \
                'BEGIN { d = turned - asked; if (d < 0) d = -d; exit !(d <= 1.0) }'; then
                looked=1
            fi
            break
        fi
        sleep 1
    done
    if [ "${looked}" -eq 1 ]; then
        printf 'domain: the turn is the one that was asked for, and the Kin stayed put\n' >&2
    else
        printf 'domain: the Kin never turned as asked within %ss\n' "${seconds}" >&2
    fi
fi

# Core killed outright rather than paused: the sockets really close, and the
# Bridge has to let go without being told anything. Unlike the silence case,
# `session start` dies with it — so this block does its own waiting, and there is
# no run document at the end of the run, which is the honest shape of it: the
# evidence is the client's own log and the server's readings.
if [[ -n "${kill_core}" ]]; then
    deadline=$((SECONDS + seconds))
    killed=0
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        # While the Kin is walking, which this block can see because the walk
        # wait is skipped for exactly this run.
        #
        # `sleep 1`, and not only for politeness: `SECONDS` does not advance
        # while a loop spins through commands that take no time, so a budget
        # measured in `SECONDS` around a body with no `sleep` is not a budget —
        # the whole loop runs in milliseconds and gives up before the first
        # probe reading has been written. Measured: ninety iterations at
        # `SECONDS=32`, every one of them seeing no movement at all, after which
        # the wait below found the Kin stopped — because the hold had expired on
        # its own — and reported a fault injection that never happened.
        if [ "$(horizontal_positions | sort -u | wc -l)" -lt 2 ]; then
            sleep 1
            continue
        fi
        # The runtime is a grandchild of the pid this script holds — `xvfb-run`
        # and the X server are between them — so it is named by its command line
        # within that subtree rather than by being the wrapper's first child.
        if inject_fault "${session_pid}" "runtime_controller" \
                "${session_starttime_ticks}" "${session_pid_namespace_inode}"; then
            killed=1
            printf 'domain: the runtime is gone; the Bridge should let go\n' >&2
        else
            printf 'domain: the runtime was not killed, so this run proves nothing about a lost runtime\n' >&2
            injection_failed=1
        fi
        break
    done
    # A run that was asked to inject a fault and did not inject it proves nothing
    # about a lost runtime, and the wait below would happily report the Kin
    # stopping for the reason it would have stopped anyway. Said out loud, and
    # the run is failed rather than left looking like the others.
    if [ "${killed}" -eq 0 ]; then
        printf 'domain: the Core was never killed, so this run proves nothing about a lost runtime\n' >&2
        injection_failed=1
    fi
    # The release is what this is about, and the server can see its effect two
    # ways: a Kin that stopped walking, or a Kin whose client exited — a socket
    # that closed is not a peer that went quiet, so the Bridge also stops the
    # client, and nothing can be held by a process that is gone. Both are
    # accepted, and which one happened is said out loud.
    stopped=0
    left=0
    deadline=$((SECONDS + seconds))
    if [ "${killed}" -eq 1 ]; then
        for _ in $(seq 1 "${seconds}"); do
            [ "${SECONDS}" -lt "${deadline}" ] || break
            positions=$(horizontal_positions)
            distinct=$(printf '%s\n' "${positions}" | sort -u | wc -l)
            settled=$(printf '%s\n' "${positions}" | tail -n 2 | sort -u | wc -l)
            if grep -q "${player} left the game" "${server_directory}/server.log" 2>/dev/null; then
                left=1
            fi
            if [ "${distinct}" -ge 2 ] && { [ "${settled}" -eq 1 ] || [ "${left}" -eq 1 ]; }; then
                stopped=1
                break
            fi
            sleep 1
        done
    fi
    if [ "${killed}" -eq 0 ]; then
        : # already said, above, along with why the run proves nothing
    elif [ "${stopped}" -eq 0 ]; then
        printf 'domain: the Kin never stopped after the Core was killed\n' >&2
    elif [ "${left}" -eq 1 ]; then
        printf 'domain: the Kin left the game after the Core was killed\n' >&2
    else
        printf 'domain: the server saw the Kin stop after the Core was killed\n' >&2
    fi
fi

# The world killed rather than ended. A kick is the server *saying* goodbye; this
# is the server saying nothing at all, and the client learning of it from a socket
# that stopped working. What the Bridge must do is the same either way — let go of
# what it holds — but the run has to be able to show that the world really died
# rather than stopped: a server that was killed never writes its own shutdown, and
# a server that stopped does.
if [[ -n "${kill_server}" ]]; then
    deadline=$((SECONDS + seconds))
    killed=0
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        # While the Kin is in the world and walking — the same `sleep 1` the other
        # waits need, for the same measured reason: `SECONDS` does not advance
        # while a loop spins through commands that take no time.
        if [ "$(horizontal_positions | sort -u | wc -l)" -lt 2 ]; then
            sleep 1
            continue
        fi
        # The JVM, not the tool that started it. `server_pid` is the tool, and the
        # first version of this killed *that* — which the tool's own signal
        # handling turned into the clean stop it performs on SIGTERM, so the world
        # was saved and rewritten while the harness printed "the world is gone".
        # Measured twice: the server log ended with `All dimensions are saved`, in
        # a run that claimed to have killed it.
        #
        # The JVM is the one `java` process under the tool, and the helper refuses
        # unless that is exactly one process: `pgrep -P <tool> | head -1` named the
        # tool's first child, which is not the same claim.
        if inject_fault "${server_pid}" "server_jvm" \
                "${server_starttime_ticks}" "${server_pid_namespace_inode}"; then
            killed=1
            if grep -q "Stopping the server" "${server_directory}/server.log" 2>/dev/null; then
                # A killed server gets no chance to write its own shutdown, so this
                # line in its log means it stopped rather than died — whatever the
                # signal did. A second opinion on the helper's own confirmation.
                printf 'domain: the server wrote its own shutdown, so it stopped rather than died\n' >&2
                killed=0
            else
                printf 'domain: the server has been killed; the world is gone\n' >&2
            fi
        fi
        break
    done
    if [ "${killed}" -eq 0 ]; then
        # Same rule as the other fault injections: one that did not happen proves
        # nothing, and the run is failed rather than left looking like the rest.
        printf 'domain: the server was never killed, so this run proves nothing about a world that died\n' >&2
        injection_failed=1
    else
        # Core's own record of the world going away. Waited for rather than
        # assumed, because "the session ended" is the fact this run exists to
        # produce and a run that never reaches it has not produced it.
        ended=0
        for _ in $(seq 1 "${seconds}"); do
            [ "${SECONDS}" -lt "${deadline}" ] || break
            recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
                "select 1 from event where position > ${baseline} and event_type='SessionInterrupted' limit 1;" \
                2>/dev/null || true)
            if [ -n "${recorded}" ]; then
                ended=1
                break
            fi
            sleep 1
        done
        if [ "${ended}" -eq 1 ]; then
            printf 'domain: Core recorded the session ending when the world went away\n' >&2
        else
            printf 'domain: the session never recorded an interruption after the server died\n' >&2
        fi
    fi
fi

# Kicked rather than killed: the server ends the session and the client keeps
# running, which is the trigger §12 calls leaving playable. The kick itself is
# fired by the server tool on its own clock; what is waited for here is the
# server's own account of the session ending.
if [[ -n "${kick}" ]]; then
    kicked=0
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        if grep -qE "${kick} (lost connection|left the game)" \n            "${server_directory}/server.log" 2>/dev/null; then
            kicked=1
            break
        fi
        sleep 1
    done
    if [ "${kicked}" -eq 1 ]; then
        printf 'domain: the server ended the session while the client kept running\n' >&2
    else
        printf 'domain: the server never ended the session within %ss\n' "${seconds}" >&2
    fi
fi

# A run that is checking what a *previous* run left behind: the Kin must not be
# moving. Nothing in the new session asks it to, and nothing the dead one asked
# for may still be in force — which is a fact about the world, so the world is
# where it is read.
if [[ -n "${still}" ]]; then
    # Measured by distance rather than by equality, because the world is not
    # empty: a summoned pig that wanders into the Kin pushes it, and a Kin that
    # was shoved 1.5 blocks in three seconds has not walked anywhere. Walking is
    # 4.3 blocks per second, so the two are two orders of magnitude apart given
    # any sensible probe interval — the threshold is the gap between a shove and
    # a step, not a tuned number.
    walked=0
    moved=0
    readings=0
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        positions=$(horizontal_positions)
        readings=$(printf '%s\n' "${positions}" | grep -c . || true)
        if [ "${readings}" -ge 2 ]; then
            drift=$(printf '%s\n' "${positions}" |
                awk -F, 'NR == 1 { x = $1; z = $2 } { lx = $1; lz = $2 }
                         END { dx = lx - x; dz = lz - z; printf "%.3f", sqrt(dx * dx + dz * dz) }')
            if awk -v drift="${drift}" 'BEGIN { exit !(drift > 2.0) }'; then
                moved=1
            fi
            break
        fi
        sleep 1
    done
    if [ "${moved}" -eq 1 ]; then
        printf 'domain: the Kin moved %s blocks without being asked to\n' "${drift}" >&2
    elif [ "${readings}" -ge 2 ]; then
        printf 'domain: the Kin moved %s blocks across %s readings and did not walk\n'             "${drift}" "${readings}" >&2
    else
        printf 'domain: the Kin was never seen in the world\n' >&2
    fi
fi

# A bounded soak: the session is left running for a stated length of time, and the
# two processes it is made of are sampled while it runs. What this is for is the
# contract's L6 baseline — sustained operation with resources *reported* rather
# than promised — and it is a run rather than a case because the contract says so
# in as many words: no human baseline exists yet, so nothing here sets a
# threshold, and the numbers are reported as measurements.
#
# Sampled from /proc rather than asked of the JVM. A process asked about its own
# memory is a process reporting its own opinion, and this has to be readable even
# from a client that is too unhealthy to answer.
if [ "${soak_seconds}" -gt 0 ]; then
    soak_file=/tmp/domain-soak.txt
    : > "${soak_file}"
    sample() {
        # One line per process per round: the label, the resident size in KB and
        # the thread count, as the kernel holds them.
        [ -n "$1" ] && [ -r "/proc/$1/status" ] || return 1
        awk -v label="$2" '/^VmRSS:/ { rss = $2 } /^Threads:/ { threads = $2 }
             END {
                 if (rss == "" || threads == "") exit 1
                 printf "%s %s %s\n", label, rss, threads
             }' "/proc/$1/status" 2>/dev/null >> "${soak_file}"
    }
    # Name the JVM, not a launcher's first child. Both halves can have wrappers,
    # and a JVM may start after the soak begins, so discovery is repeated until
    # each sample rather than turning an early empty lookup into a whole empty
    # baseline.
    find_java_descendant() {
        local root="$1"
        local found=""
        local child
        local candidate
        if [ "$(cat "/proc/${root}/comm" 2>/dev/null || true)" = "java" ]; then
            found="${root}"
        fi
        for child in $(pgrep -P "${root}" 2>/dev/null || true); do
            candidate=$(find_java_descendant "${child}")
            if [ -n "${candidate}" ]; then
                found="${candidate}"
            fi
        done
        printf '%s' "${found}"
    }

    printf 'domain: soaking for %ss at %ss intervals\n' \
        "${soak_seconds}" "${soak_interval}" >&2
    client_samples=0
    server_samples=0
    soak_interrupted=0
    sample_failed=0
    deadline=$((SECONDS + soak_seconds))
    while [ "${SECONDS}" -lt "${deadline}" ]; do
        if ! kill -0 "${session_pid}" 2>/dev/null; then
            soak_interrupted=1
            break
        fi
        client_process=$(find_java_descendant "${session_pid}")
        world_process=$(find_java_descendant "${server_pid}")
        if sample "${client_process}" client; then
            client_samples=$((client_samples + 1))
        else
            sample_failed=1
        fi
        if sample "${world_process}" server; then
            server_samples=$((server_samples + 1))
        else
            sample_failed=1
        fi
        remaining=$((deadline - SECONDS))
        nap="${soak_interval}"
        if [ "${nap}" -gt "${remaining}" ]; then
            nap="${remaining}"
        fi
        if [ "${nap}" -gt 0 ]; then
            sleep "${nap}"
        fi
    done
    # A process can disappear during the final sleep, after the last sample but
    # before the deadline. It still did not survive the requested baseline.
    final_client_process=$(find_java_descendant "${session_pid}")
    final_world_process=$(find_java_descendant "${server_pid}")
    if ! kill -0 "${session_pid}" 2>/dev/null || \
            [ -z "${final_client_process}" ] || [ -z "${final_world_process}" ]; then
        soak_interrupted=1
    fi
    if [ "${soak_interrupted}" -eq 1 ]; then
        printf 'domain: the session ended before the requested soak duration elapsed\n' >&2
        injection_failed=1
    fi
    if [ "${sample_failed}" -eq 1 ] || \
            [ "${client_samples}" -eq 0 ] || [ "${server_samples}" -eq 0 ]; then
        printf 'domain: the soak did not sample both JVMs on every pass (client=%s, server=%s)\n' \
            "${client_samples}" "${server_samples}" >&2
        injection_failed=1
    fi
    for label in client server; do
        awk -v label="${label}" '
            $1 == label {
                n += 1; rss[n] = $2
                if (n == 1 || $2 < low) low = $2
                if (n == 1 || $2 > high) high = $2
                if ($3 > threads) threads = $3
            }
            END {
                if (n == 0) {
                    printf "domain: %s was never sampled\n", label
                    exit 1
                }
                printf "domain: %s RSS %.0f MB at first, %.0f MB at last, %.0f..%.0f MB over %d samples, %d threads at most\n",
                       label, rss[1] / 1024, rss[n] / 1024, low / 1024, high / 1024, n, threads
            }' "${soak_file}" >&2 || true
    done
fi

printf 'domain: stopping the session\n' >&2

# Idempotent, and it identifies the client by its recorded pid and command line
# rather than by name, so a session that has already ended is reported as stopped
# and one that never joined is ended where it stands. Either way the CLI returns
# normally and prints the run document.
#
# Its answer is kept in the log rather than discarded. A stop that did nothing is
# the difference between "the session ended by itself" and "the harness failed to
# end it", and those two look identical from the outside.
python -m minekin_core session stop >/tmp/domain-stop.log 2>&1 || true
printf 'domain: session stop said ' >&2
tr -d '\n' </tmp/domain-stop.log >&2 || true
printf '\n' >&2

# Bounded, because a client that will not die must not wedge the harness: the
# document matters less than the run ending.
set +e
for _ in $(seq 1 120); do
    kill -0 "${session_pid}" 2>/dev/null || break
    sleep 1
done
if kill -0 "${session_pid}" 2>/dev/null; then
    # Should not be reachable: the loop above only stops a session whose own
    # ledger already holds the playable event, and `session stop` ends such a
    # session by terminating the client it recorded. Named rather than silent,
    # because killing what could not be stopped ends the run in a way that has
    # nothing to do with the run.
    printf 'domain: the session did not stop; killing it, so this run proves nothing\n' >&2
    kill -TERM "${session_pid}" 2>/dev/null || true
fi
wait "${session_pid}"
status=$?
set -e
printf 'domain: session exited %s\n' "${status}" >&2

# What the supervisor the runtime was found under exited with, now that this script
# — which is the one that waited for it — can say. The helper cannot: it is not the
# supervisor's parent, so it has no `waitpid` to read a status from, and its record
# says the status was not observed until this fills it in. The server half is not
# annotated here because its supervisor is still running when the seal happens, and
# a status nobody waited for would be an invented number rather than an absent one.
if [ "${fault_role}" = "runtime_controller" ] && [ -s "${fault_path}" ]; then
    set +e
    python /src/tools/inject_fault.py annotate \
        --record "${fault_path}" \
        --supervisor-pid "${session_pid}" \
        --supervisor-exit-status "${status}" >/tmp/domain-fault-annotate.log 2>&1
    annotated=$?
    set -e
    printf 'domain: the fault record was annotated ' >&2
    tr -d '\n' </tmp/domain-fault-annotate.log >&2 || true
    printf '\n' >&2
    if [ "${annotated}" -ne 0 ]; then
        printf 'domain: the fault record annotation failed, so the run cannot claim complete fault evidence\n' >&2
        injection_failed=1
    fi
fi

# The run document is what Core says it did, and it is the only place Core's own
# verdict on the first snapshot exists. It was captured to a file so that it can
# be judged and sealed; it is printed here so that reading the container's output
# still shows it, which is what the operator had before it was captured.
printf 'domain: the run document said ' >&2
tr -d '\n' </tmp/domain-session.json >&2 || true
printf '\n' >&2

# Sealing, which is what makes this a case run rather than a run.
#
# The leave has to be in the server's log before the case can be judged, and the
# server writes it a moment after the client's socket goes: waited for rather
# than assumed, because a seal that fails on a race would report the run as
# unproven. Bounded, and the seal happens either way — a run the server never saw
# leave is a fact the verdict should carry, not a reason to stop.
if [[ -n "${case_id}" ]]; then
    world_args=()
    if [ -n "${server_profile}" ]; then
        # The leave has to be in the server's log before the case can be judged,
        # and the server writes it a moment after the client's socket goes:
        # waited for rather than assumed, because a seal that failed on a race
        # would report the run as unproven. Bounded, and the seal happens either
        # way — a run the server never saw leave is a fact the verdict should
        # carry, not a reason to stop.
        if [ -z "${black_hole}" ]; then
            # A run that ended against a real server waits for that server's own
            # account of leaving. A black hole never had anything to say, and
            # waiting thirty seconds for a sentence it cannot write is thirty
            # seconds this scenario would spend proving nothing.
            for _ in $(seq 1 30); do
                if grep -q "${player} left the game" "${server_directory}/server.log" 2>/dev/null; then
                    break
                fi
                sleep 1
            done
        fi
        world_args=(--server-profile "${server_profile}"
            --server-directory "${server_directory}")
        if [ -z "${black_hole}" ]; then
            # A black hole is not a server: there is no jar behind it, and naming
            # one that was never mounted would be a claim about bytes that were
            # never there.
            world_args+=(--server-jar /server/server.jar)
        fi
    fi

    # The renderer is measured rather than assumed, and it is measured under the
    # same wrapper the session ran under: this is the software rasteriser the
    # container actually has, not the one its documentation mentions.
    renderer="unmeasured"
    if command -v glxinfo >/dev/null 2>&1; then
        measured=$(xvfb-run -a --server-args="-screen 0 1280x720x24" glxinfo -B 2>/dev/null |
            sed -n 's/^OpenGL renderer string: //p' | head -1 || true)
        if [ -n "${measured}" ]; then
            renderer="${measured}"
        fi
    fi

    printf 'domain: sealing run evidence for case %s\n' "${case_id}" >&2
    set +e
    # Named by the document Core printed, or by its run id when there is none —
    # which is exactly the killed-Core case, where the absence is the point.
    named_run=(--run-document /tmp/domain-session.json)
    if [ ! -s /tmp/domain-session.json ]; then
        named_run=(--run-id "${run_id}")
    fi
    # The record of the fault this run injected, when it injected one. It is named
    # by its path and read once by the sealer, which seals the same bytes it judged.
    fault_args=()
    if [ -s "${fault_path}" ]; then
        fault_args=(--fault-injection "${fault_path}")
    fi
    python /src/tools/seal_run_evidence.py \
        --data-root /data \
        --case "${case_file}" \
        --profile "${profile}" \
        "${world_args[@]}" \
        "${named_run[@]}" \
        "${fault_args[@]}" \
        --username "${player}" \
        --renderer-display "${renderer}" \
        --session-argv "$@" >/tmp/domain-seal.json 2>/tmp/domain-seal.err
    sealed=$?
    set -e
    if [ "${sealed}" -eq 2 ] || [ ! -s /tmp/domain-seal.json ]; then
        # A sealer that said nothing and exited zero-ish did not seal: the codes
        # are 0 for held, 1 for sealed-and-failed, 2 for could-not-seal, and an
        # empty report is none of those. Printing its stderr either way is the
        # difference between "the case failed" and "the tool fell over".
        printf 'domain: the run could not be sealed (exit %s): ' "${sealed}" >&2
        tr -d '\n' </tmp/domain-seal.err >&2 || true
        printf '\n' >&2
        status=1
    else
        tr -d '\n' </tmp/domain-seal.json >&2 || true
        printf '\n' >&2
        verdict=$(python -c 'import json;print(json.load(open("/tmp/domain-seal.json"))["result"])' 2>/dev/null || true)
        run_id=$(python -c 'import json;print(json.load(open("/tmp/domain-seal.json"))["run_id"])' 2>/dev/null || true)
        printf 'domain: the case verdict is %s\n' "${verdict}" >&2

        # And the bundle is read back through the command that exists to read it,
        # so what this prints is the answer an operator would get later rather
        # than a restatement of what the sealer just did.
        set +e
        python -m minekin_core evidence verify "${run_id}" >/tmp/domain-verify.json 2>&1
        verified=$?
        set -e
        printf 'domain: evidence verify said ' >&2
        tr -d '\n' </tmp/domain-verify.json >&2 || true
        printf '\n' >&2
        if [ "${verified}" -ne 0 ]; then
            printf 'domain: the sealed bundle does not verify\n' >&2
            status=1
        fi
        if [ "${verdict}" != "PASS" ]; then
            printf 'domain: case %s did not hold for this run\n' "${case_id}" >&2
            status=1
        elif [ "${verified}" -eq 0 ]; then
            # A case run's exit status is the case's answer rather than the
            # session's, because that is the question that was asked. The
            # session's own status is 14 here and always has been: the harness
            # ends a session by terminating the client, so Core records
            # `BRIDGE_LOST`, which maps to IPC_PROTOCOL. Printing it and exiting
            # on it are two different things, and only one of them is useful.
            status=0
        fi
    fi
fi

if [ "${injection_failed}" -eq 1 ]; then
    status=1
fi
exit "${status}"
