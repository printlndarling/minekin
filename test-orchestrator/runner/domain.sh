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
# The client killed rather than the runtime or the world. This is the boundary
# where the keys die with the process: the Bridge is a mod inside the client, so
# nothing in that JVM is left to release a key or to report a phase. What the run
# has to show is therefore a fact about the *runtime* noticing its own client is
# gone, and a fact about the world seeing the Kin leave.
kill_client="${MINEKIN_DOMAIN_KILL_CLIENT:-}"
no_server="${MINEKIN_DOMAIN_NO_SERVER:-}"
still="${MINEKIN_DOMAIN_STILL:-}"
# A bounded soak: how long the session is left running, and how often the two
# processes are sampled. Zero means no soak, which is what every run before this
# did — a soak is a thing a run asks for, not a thing every run pays for.
soak_seconds="${MINEKIN_DOMAIN_SOAK_SECONDS:-0}"
soak_interval="${MINEKIN_DOMAIN_SOAK_INTERVAL:-10}"
#: Where a soak's measurement and its request are written, named here rather than
#: inside the soak so the sealer can ask for them by the same names whether or not
#: this run soaked. Only a soak run leaves files here.
soak_file=/tmp/domain-soak.txt
soak_summary=/tmp/domain-soak.json
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
# A server that requires session verification while our client authenticates offline.
# The two disagree here on purpose: the tool derives the server's online-mode from
# the profile's auth_mode, so no other run can produce this, and the case exists to
# watch the refusal be classified as AUTH_MODE_MISMATCH rather than worked around.
online_mode="${MINEKIN_DOMAIN_ONLINE_MODE:-}"
# A server that requires a resource pack while the profile's policy is to refuse one.
# The pack is built and served by the harness itself, on loopback, and its sha1 goes
# into the server's settings — so the refusal is the client's policy meeting the
# server's requirement, and not a pack that could not be fetched.
resource_pack="${MINEKIN_DOMAIN_RESOURCE_PACK:-}"
# Ask the client to report this generation's first snapshot as not authoritative, so
# that Core's own boundary filter has a snapshot to refuse (`ADMIT-070`).
#
# The scenario cannot be produced any other way, and that is the measured fact this
# knob exists because of: across every run document the reviewed builds left behind,
# the field holding refusals was empty — the Bridge withholds a snapshot it cannot
# stand behind rather than sending a weaker one, so no real server, profile or timing
# makes a first snapshot arrive as `authoritative=false`.
#
# The refusal itself stays Core's decision. This harness only lends the client JVM a
# name; Core reads nothing out of its value, and unset means the run reports exactly
# what it reported before.
refuse_first_snapshot="${MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT:-}"
case "${refuse_first_snapshot}" in
    "" | 0 | false | 1 | true) : ;;
    *)
        printf 'domain: MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT must be 1/true or 0/false, got %q\n' \
            "${refuse_first_snapshot}" >&2
        exit 2
        ;;
esac
# Cast to a number, because a run explicitly told `0` and a run told nothing are
# the same request — and `[ -n ]` read them as two different ones. An operator who
# wrote `0` asked for the ordinary first snapshot; putting that run on the refusal
# path, waiting for a join that will not be refused and recording a request nobody
# made, would be the harness answering a question nobody asked.
refusal_asked=0
case "${refuse_first_snapshot}" in
    1 | true) refusal_asked=1 ;;
esac
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
# A session that is meant to *host*: the client is put in a world it owns and asked to
# publish it to LAN. The port is named rather than chosen by the client, because the
# point of publishing is that something else can be pointed at it — and a client that
# chooses its own port reports it only in a run document that is printed at the end.
open_lan="${MINEKIN_DOMAIN_OPEN_LAN:-}"
lan_port="${MINEKIN_DOMAIN_LAN_PORT:-25570}"
# A second managed client that joins the world the first one published. It is a second
# *Kin* and not a second session of the same one, because the identity is the username:
# the same Kin arriving twice is a duplicate login the server kicks.
#
# The port has to be named for this to mean anything: the joining client is configured
# by a server profile whose port is a literal, and a port the hosting client chose for
# itself is only reported in a run document printed when that run has ended.
joiner="${MINEKIN_DOMAIN_JOIN:-}"
join_username="${MINEKIN_DOMAIN_JOIN_USERNAME:-Kin2}"
# Which of the two runs a joining run's case is about. The harness seals one run per
# bundle, and a run with a second client in it has two: the hosting session (whose
# document is what every other case is judged on) and the joining one. Named rather
# than guessed from the case id, because a case id is not a switch and a second
# spelling of one would be a silent wrong answer.
case_on="${MINEKIN_DOMAIN_CASE_ON:-host}"
case "${case_on}" in
    host|joiner) : ;;
    *)
        printf 'domain: MINEKIN_DOMAIN_CASE_ON must be host or joiner, got %q\n' "${case_on}" >&2
        exit 2
        ;;
esac
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
# Counted rather than compared two at a time, because there are three boundaries
# now and a pairwise guard would let the third one pair up with neither.
faults=0
for requested in "${kill_core}" "${kill_server}" "${kill_client}"; do
    if [ -n "${requested}" ]; then
        faults=$((faults + 1))
    fi
done
if [ "${faults}" -gt 1 ]; then
    printf 'domain: this run asks for two faults at once; one run seals one record\n' >&2
    exit 2
fi
# The same rule covers the report request, because it travels through the same
# artifact: a run that both killed a process and asked the client to report a
# weaker snapshot would seal one of the two, and there is no way to say afterwards
# which. Refused here, while the run can still be told apart from its result.
request_path=/tmp/domain-injection-request.json
if [ "${refusal_asked}" -eq 1 ] && [ "${faults}" -ge 1 ]; then
    printf 'domain: this run asks for a refused snapshot and a killed process; one run seals one record\n' >&2
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

# Record that this run asked the client to report a weaker first snapshot, and
# whether the live client JVM actually carries that name.
#
# This is not `inject_fault` with a different role, and keeping it separate is the
# point: nothing here ends a process, so there is no signal, no disappearance and
# no supervisor exit status to attest. Filing the request as a kill record would be
# the harness claiming a strength it did not observe. What it *can* attest is the
# request itself and its effect, read from `/proc/<client JVM>/environ` — a fact
# about a process, not about a line in a log — which is why the call has to happen
# while the client is alive.
record_refusal_request() {
    local root_pid="$1"
    local root_starttime_ticks="$2"
    local root_pid_namespace_inode="$3"
    set +e
    python /src/tools/inject_fault.py request \
        --root-pid "${root_pid}" \
        --root-starttime-ticks "${root_starttime_ticks}" \
        --root-pid-namespace-inode "${root_pid_namespace_inode}" \
        --subject BRIDGE_FIRST_SNAPSHOT_AUTHORITY \
        --value "${refuse_first_snapshot}" \
        --case "${case_id}" \
        --case-file "${case_file}" \
        --ledger "${ledger}" \
        --kin-id "${kin_id}" \
        --run-id "${run_id}" \
        --session-id "${session_id}" \
        --generation "${generation}" \
        --record "${request_path}" >/tmp/domain-injection-request.log 2>&1
    local helper_status=$?
    set -e
    printf 'domain: the report request helper said ' >&2
    tr -d '\n' </tmp/domain-injection-request.log >&2 || true
    printf '\n' >&2
    if [ "${helper_status}" -ne 0 ] || [ ! -s "${request_path}" ]; then
        printf 'domain: the injection could not be recorded, so nothing here can be attributed\n' >&2
        return 1
    fi
    local observed
    observed=$(python -c 'import json,sys;print(json.load(open(sys.argv[1]))["effect"]["observed"])' \
        "${request_path}" 2>/dev/null || true)
    if [ "${observed}" != "True" ]; then
        printf 'domain: the name did not reach the client JVM (%s): ' "${observed:-unreadable}" >&2
        python -c 'import json,sys;print(",".join(json.load(open(sys.argv[1]))["reasons"]))' \
            "${request_path}" >&2 2>/dev/null || true
        printf '\n' >&2
        return 1
    fi
    # Read back through the reader the sealer itself uses, not merely parsed. A
    # record this harness could write but that channel could not read would be
    # evidence nobody can judge, and the run would only find that out when the
    # bundle was already sealed.
    if ! python - "${request_path}" <<'PY' >&2
import json
import sys
from pathlib import Path

sys.path.insert(0, "/src/tools")

import fault_injection

document = fault_injection.read_record(Path(sys.argv[1])).document
print("domain: the sealing channel reads this record back as")
print(
    json.dumps(
        {key: document[key] for key in ("category", "request", "effect", "attribution")},
        sort_keys=True,
    )
)
PY
    then
        printf 'domain: the injection record could not be read back as a record\n' >&2
        return 1
    fi
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
    pack_args=()
    if [ -n "${resource_pack}" ]; then
        pack_args=(--resource-pack)
    fi
    online_args=()
    case "${online_mode}" in
        true) online_args=(--online-mode) ;;
        false) online_args=(--no-online-mode) ;;
        "") ;;
        *)
            printf 'domain: MINEKIN_DOMAIN_ONLINE_MODE must be true or false, not %s
'                 "${online_mode}" >&2
            exit 2
            ;;
    esac
    python /src/tools/run_controlled_server.py \
        --directory "${server_directory}" \
        --jar /server/server.jar \
        --accept-eula \
        "${allow_args[@]}" \
        "${online_args[@]}"         "${pack_args[@]}" \
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
# The second client's environment, before anything starts: its Kin, its artifact store,
# and the profile it will dial. All three are preparation rather than the run — the
# second Kin exists so its identity differs from the host's, and the store is a *copy*
# because the store refuses to have its root be a symlink, so linking it is not an
# option the fixture gets to take.
join_ready=0
if [ -n "${joiner}" ]; then
    if [ -z "${open_lan}" ]; then
        printf 'domain: a joiner needs a world to join; set MINEKIN_DOMAIN_OPEN_LAN=1\n' >&2
        exit 2
    fi
    # Named rather than picked: with a second Kin in the root, "the first directory"
    # is a coin toss, and copying the wrong store would surface as a missing artifact
    # much later in the run.
    host_kin="${MINEKIN_KIN_ID:-}"
    if [ -z "${host_kin}" ]; then
        printf 'domain: a joining run must name the hosting Kin (MINEKIN_KIN_ID)\n' >&2
        exit 2
    fi
    if [ ! -d "/data/kin/${joiner}" ]; then
        if ! MINEKIN_USERNAME="${join_username}" python -m minekin_core init \
            --kin-id "${joiner}" >>/tmp/domain-join-setup.log 2>&1; then
            printf 'domain: could not create the joining Kin %s (see /tmp/domain-join-setup.log)\n' \
                "${joiner}" >&2
            exit 2
        fi
        printf 'domain: the joining Kin %s was created as %s\n' "${joiner}" "${join_username}" >&2
    fi
    mkdir -p "/data/kin/${joiner}/run"
    if [ -L "/data/kin/${joiner}/run/artifact-store" ]; then
        # Left by an attempt that linked it; `-d` follows a link, so the copy below
        # would be skipped and the refusal would come back looking like the same bug.
        rm -f "/data/kin/${joiner}/run/artifact-store"
    fi
    if [ ! -d "/data/kin/${joiner}/run/artifact-store" ]; then
        cp -a "/data/kin/${host_kin}/run/artifact-store" \
            "/data/kin/${joiner}/run/artifact-store" ||
            {
                printf 'domain: could not give the joining Kin an artifact store\n' >&2
                exit 2
            }
    fi
    python - "${lan_port}" /tmp/domain-join-profile.json <<'PY'
import json
import sys

port, path = int(sys.argv[1]), sys.argv[2]
profile = {
    "schema_version": 1,
    "profile_id": "p0-lan-host-fixture",
    "host": "127.0.0.1",
    "port": port,
    "auth_mode": "offline",
    "minecraft_version": "1.21.4",
    "visibility": "isolated_test_only",
    "resource_pack_policy": "deny",
}
with open(path, "w", encoding="utf-8") as document:
    document.write(json.dumps(profile, indent=2) + "\n")
PY
    join_ready=1
fi

# Start the second client against the world the first one published, and wait for the
# *world* to say somebody arrived. The joiner's own document is what that client
# believes happened; the hosting client's server thread is the side that cannot be
# talked into it, and that is the fact L3 is about — one real client joining another's
# published world.
join_the_published_world() {
    local host_log="$1"
    local before
    local overlay
    local joined=0
    local deadline
    local baseline
    local recorded
    local playable
    before=$(ls "/data/kin/${joiner}/run/session/" 2>/dev/null | sort)
    # Where the joining Kin's ledger stood before this client started. Every wait in
    # this harness reads only its own run, and this one learned why the hard way: an
    # unscoped query found the `PlayableEstablished` of an *earlier* run of the same
    # Kin, so the harness announced a first snapshot the joining client's own document
    # said it had never admitted.
    baseline=$(/opt/sqlite/bin/sqlite3 "/data/kin/${joiner}/kin.sqlite3" \
        "select coalesce(max(position), 0) from event;" 2>/dev/null || echo 0)
    baseline=${baseline:-0}
    xvfb-run -a --server-args="-screen 0 1280x720x24" \
        env MINEKIN_KIN_ID="${joiner}" python -m minekin_core session start \
        --profile "${profile}" \
        --server-profile /tmp/domain-join-profile.json \
        >/tmp/domain-join-session.json 2>/tmp/domain-join-session.err &
    joiner_pid=$!
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${joiner_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        if grep -q "${join_username} joined the game" "${host_log}" 2>/dev/null; then
            joined=1
            break
        fi
        sleep 1
    done
    if [ "${joined}" -eq 1 ]; then
        printf 'domain: the world heard %s arrive\n' "${join_username}" >&2
    else
        printf 'domain: %s never arrived within %ss\n' "${join_username}" "${seconds}" >&2
        tr -d '\n' </tmp/domain-join-session.err >&2 || true
        printf '\n' >&2
    fi
    # Being *playable* is the joining client's own conclusion about the first snapshot
    # it admitted, and the ledger is where this harness reads conclusions. Measured:
    # stopping as soon as the world heard the arrival ended one run at `PLAY_INIT` with
    # no snapshot admitted at all, which is the difference between arriving somewhere
    # and being able to see it.
    deadline=$((SECONDS + seconds))
    playable=0
    for _ in $(seq 1 "${seconds}"); do
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "/data/kin/${joiner}/kin.sqlite3" \
            "select 1 from event where position > ${baseline} and \
event_type='PlayableEstablished' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: %s admitted its first snapshot of that world\n' "${join_username}" >&2
    else
        printf 'domain: %s arrived but never became playable within %ss\n' \
            "${join_username}" "${seconds}" >&2
    fi
    # What the joining client itself reports, read from the overlay this run created
    # rather than from the newest one on disk.
    overlay=""
    for _ in $(seq 1 30); do
        fresh=$(comm -13 <(printf '%s\n' "${before}") \
            <(ls "/data/kin/${joiner}/run/session/" 2>/dev/null | sort) | head -1)
        if [ -n "${fresh}" ]; then
            candidate="/data/kin/${joiner}/run/session/${fresh}/generation-1"
            [ -f "${candidate}/logs/latest.log" ] && { overlay="${candidate}"; break; }
        fi
        sleep 1
    done
    if [ -n "${overlay}" ]; then
        printf 'domain: the joining client reports:\n' >&2
        grep -E "CONNECTION_PHASE_JOIN_SEEN|knows of [0-9]+ entity candidate" \
            "${overlay}/logs/latest.log" 2>/dev/null | tail -3 |
            sed 's/^/domain:   /' >&2 || true
    fi
}

# The logs that exist before this session starts. A host run has to watch the client's
# own log (see the wait below), and the newest log on disk is the one the *last* run
# wrote — which is a mistake this harness has already made once in another form.
logs_before=$(ls /data/kin/*/run/session/*/generation-*/logs/latest.log 2>/dev/null | sort)
lan_args=()
if [ -n "${open_lan}" ]; then
    lan_args=(--open-lan --open-lan-port "${lan_port}")
fi
# Lent to the session supervisor's environment, which is the only route the managed
# client JVM has to a name the host set: Core hands the client nothing it has not
# been given in `config.FORWARDED_VARIABLES`, and this is the one such name whose
# value Core never looks at.
client_env=()
if [ "${refusal_asked}" -eq 1 ]; then
    client_env=(env MINEKIN_BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT="${refuse_first_snapshot}")
fi
xvfb-run -a --server-args="-screen 0 1280x720x24" \
    "${client_env[@]}" python -m minekin_core "$@" "${lan_args[@]}" >/tmp/domain-session.json &
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
# A root with several Kin needs one named, and the selector is the same one the CLI
# reads — a scenario with a second Kin in it (the one that joins a hosted world) has
# two ledgers by construction.
kin_selector="${MINEKIN_KIN_ID:-}"
if [ -n "${kin_selector}" ]; then
    ledgers=("/data/kin/${kin_selector}/kin.sqlite3")
else
    ledgers=(/data/kin/*/kin.sqlite3)
fi
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
if [ "${case_id}" = "ADMIT-040" ]; then
    # This case is a refusal, not a world-entry test. Only the classified
    # Bridge-filtered fact from this run ends the wait; a generic disconnect
    # would hide the exact regression this case exists to detect.
    if [ "${online_mode}" != "true" ] || [ -z "${server_profile}" ]; then
        printf 'domain: ADMIT-040 requires an online-mode server and an offline Server Profile\n' >&2
        exit 2
    fi
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='SessionInterrupted' and source='BRIDGE' and trust_class='BRIDGE_FILTERED' and json_extract(payload_json,'\$.phase')='FAILED' and json_extract(payload_json,'\$.reason')='ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the session recorded the expected auth mismatch\n' >&2
    else
        printf 'domain: no classified auth mismatch was recorded within %ss\n' "${seconds}" >&2
    fi
elif [ "${case_id}" = "ADMIT-060" ]; then
    # What this run exists to say is one line: the policy the connection was actually
    # made with. The client then sits in the login negotiation — a required pack it
    # will not take is not a refusal anybody announces — so waiting for the world, or
    # for the 45 seconds to run out, would end this run with a timeout on its face and
    # the fact itself unread.
    #
    # Asked for by value rather than by existence, because the value is the whole
    # question: a build that let `resource_pack_policy` fall through to `prompt` would
    # record a row, and the wait would be wrong to call that the run saying what this
    # case asks it to say.
    if [ -z "${resource_pack}" ] || [ -z "${server_profile}" ]; then
        printf 'domain: ADMIT-060 requires a served resource pack and an offline Server Profile\n' >&2
        exit 2
    fi
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='ResourcePackPolicyApplied' and source='BRIDGE' and trust_class='BRIDGE_FILTERED' and json_extract(payload_json,'\$.resource_pack_policy')='deny' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the session recorded the denied resource pack policy it put on the wire\n' >&2
    else
        printf 'domain: no denied resource pack policy was recorded within %ss\n' "${seconds}" >&2
    fi
elif [ "${refusal_asked}" -eq 1 ]; then
    # The wait ends on the join, and the verdict comes later from Core's own record.
    # The client's log line was the first version's oracle here, and it is the wrong
    # kind: a Bridge that said the sentence about a snapshot that never reached IPC
    # satisfied it, and a run whose Core really refused a snapshot could miss it to a
    # log rotation. It was also read by taking `head -1` over *every* Kin's newest
    # log, which is the same mistake this harness has already made once on the ledger
    # — a second client in the container could answer for the first one.
    #
    # What has to happen before anything can be refused is the join, and that is a
    # ledger row: `JoinObserved`. Waiting for it keeps the run's timing honest
    # without making the log load-bearing, and the refusal itself is judged below,
    # once the run document exists.
    deadline=$((SECONDS + seconds))
    refusal_join_seen=0
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='JoinObserved' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            refusal_join_seen=1
            break
        fi
        sleep 1
    done
    if [ "${refusal_join_seen}" -eq 1 ]; then
        printf 'domain: the Kin joined; Core now has a first snapshot to accept or refuse\n' >&2
    else
        # The run asked for something that never got as far as being refused, and it
        # must not exit like one that was: a bare timeout here reads as "Core refused
        # a snapshot", which is a conclusion nobody reached.
        printf 'domain: no join was recorded within %ss, so no first snapshot could be refused\n' "${seconds}" >&2
        injection_failed=1
    fi
elif [ -n "${not_whitelisted}" ]; then
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
elif [ -n "${open_lan}" ]; then
    # A run that publishes a world waits for the world to be published, and it has to
    # read the *client's* log to do it. That is not a shortcut: publishing is not one of
    # §5's session events, so Core records it on the run document rather than in the
    # ledger, and the run document is printed when the session ends. While the session is
    # running, the client's own log is the only place the fact exists — and the only
    # overlays looked at are the ones that were not there before this run started.
    deadline=$((SECONDS + seconds))
    published=0
    latest=""
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        candidate=$(comm -13 <(printf '%s\n' "${logs_before}") \
            <(ls /data/kin/*/run/session/*/generation-*/logs/latest.log 2>/dev/null | sort) |
            head -1)
        if [ -n "${candidate}" ] &&
            grep -q "Started serving on ${lan_port}" "${candidate}" 2>/dev/null; then
            latest="${candidate}"
            published=1
            break
        fi
        sleep 1
    done
    if [ "${published}" -eq 1 ]; then
        printf 'domain: the world is published on %s (%s)\n' "${lan_port}" "${latest}" >&2
        if [ "${join_ready}" -eq 1 ]; then
            join_the_published_world "${latest}"
        fi
    else
        printf 'domain: nothing was published on %s within %ss\n' "${lan_port}" "${seconds}" >&2
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
# The first event may be Core's pre-spawn authentication policy fact.
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

# The report request is recorded here — after the attribution, because a record
# naming no run is refused by both the helper and the sealer, and before anything
# ends the client, because the fact it cites is that process's live environment.
# There is nothing to wait for beyond this: a run that could not say it asked is
# not a refusal, it is a harness failure, and it is failed as one.
if [ "${refusal_asked}" -eq 1 ]; then
    if ! record_refusal_request "${session_pid}" "${session_starttime_ticks}" \
            "${session_pid_namespace_inode}"; then
        injection_failed=1
    fi
fi

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

# The client killed, which is the one boundary where nothing inside the killed
# process can report anything: the Bridge is a mod in that JVM, so the release
# log the other two boundaries read cannot exist here. The target is the JVM the
# runtime started, found from the same root the runtime is found from — both are
# descendants of this script's session pid, and the role's own command line is
# what tells them apart.
if [[ -n "${kill_client}" ]]; then
    deadline=$((SECONDS + seconds))
    killed=0
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        # While the Kin is in the world and walking, and for the same measured
        # reason as the other waits: `SECONDS` does not advance while the loop
        # spins through commands that take no time.
        if [ "$(horizontal_positions | sort -u | wc -l)" -lt 2 ]; then
            sleep 1
            continue
        fi
        if inject_fault "${session_pid}" "client_jvm" \
                "${session_starttime_ticks}" "${session_pid_namespace_inode}"; then
            killed=1
            printf 'domain: the client has been killed; the keys died with the process\n' >&2
        fi
        break
    done
    if [ "${killed}" -eq 0 ]; then
        printf 'domain: the client was never killed, so this run proves nothing about a client that died\n' >&2
        injection_failed=1
    else
        # Which of Core's two records this run produced is measured rather than
        # assumed: the runtime can conclude its client exited, or it can find the
        # transport gone first and call that a lost Bridge. Both are the runtime
        # reacting to a client that is no longer there, and which one happened is
        # what the case is written against — so it is read and said out loud.
        recorded=""
        for _ in $(seq 1 "${seconds}"); do
            [ "${SECONDS}" -lt "${deadline}" ] || break
            recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
                "select event_type from event where position > ${baseline} and event_type in ('ClientProcessExited','SessionInterrupted') order by position limit 1;" \
                2>/dev/null || true)
            if [ -n "${recorded}" ]; then
                break
            fi
            sleep 1
        done
        if [ -n "${recorded}" ]; then
            printf 'domain: Core recorded %s after its client was killed\n' "${recorded}" >&2
        else
            printf 'domain: the runtime recorded nothing after its client was killed\n' >&2
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
    : > "${soak_file}"
    sample() {
        # One line per process per round: the label, the resident size in KB, the
        # thread count and how far into the soak this look happened, all as the
        # kernel holds them. The elapsed second is what makes the sample a
        # *timeline* rather than a bag of numbers: a set of readings with no
        # times cannot say whether they span the interval that was asked for.
        [ -n "$1" ] && [ -r "/proc/$1/status" ] || return 1
        awk -v label="$2" -v elapsed="$3" '/^VmRSS:/ { rss = $2 } /^Threads:/ { threads = $2 }
             END {
                 if (rss == "" || threads == "") exit 1
                 printf "%s %s %s %s\n", label, rss, threads, elapsed
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
    soak_started=${SECONDS}
    deadline=$((SECONDS + soak_seconds))
    while [ "${SECONDS}" -lt "${deadline}" ]; do
        if ! kill -0 "${session_pid}" 2>/dev/null; then
            soak_interrupted=1
            break
        fi
        elapsed=$((SECONDS - soak_started))
        client_process=$(find_java_descendant "${session_pid}")
        world_process=$(find_java_descendant "${server_pid}")
        if sample "${client_process}" client "${elapsed}"; then
            client_samples=$((client_samples + 1))
        else
            sample_failed=1
        fi
        if sample "${world_process}" server "${elapsed}"; then
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
    # What the harness was asked for and what it did, written where the sealer can
    # read it. The samples above are the measurement; this is the request, and the
    # two are checked against each other rather than one standing in for the other.
    python - "${soak_summary}" "${soak_seconds}" "${soak_interval}" \
        "${client_samples}" "${server_samples}" "${soak_interrupted}" "${sample_failed}" <<'PY'
import json
import sys

path, seconds, interval, client, server, interrupted, failed = sys.argv[1:8]
document = {
    "schema_version": 1,
    "requested_seconds": int(seconds),
    "interval_seconds": int(interval),
    "passes": min(int(client), int(server)),
    "samples": {"client": int(client), "server": int(server)},
    "ended_early": interrupted == "1",
    "failed_samples": failed == "1",
}
with open(path, "w", encoding="utf-8") as stream:
    json.dump(document, stream, sort_keys=True)
    stream.write("\n")
PY
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
# The joining client is stopped first, so the world that hosted it has something to say
# about its leaving: a visitor still connected when the host goes is a different fact
# from one that left.
if [ -n "${joiner_pid:-}" ]; then
    MINEKIN_KIN_ID="${joiner}" python -m minekin_core session stop \
        >/tmp/domain-join-stop.json 2>&1 || true
    for _ in $(seq 1 60); do
        kill -0 "${joiner_pid}" 2>/dev/null || break
        sleep 1
    done
    kill -0 "${joiner_pid}" 2>/dev/null && kill -TERM "${joiner_pid}" 2>/dev/null || true
    wait "${joiner_pid}" 2>/dev/null || true
    printf 'domain: the joining session has stopped\n' >&2
    # What that client's own run document says, printed here because the document is
    # written when its session ends and it lives in this container's /tmp: the harness
    # seals one run per bundle, and which of the two runs a case is about is a
    # question for the case rather than for this script.
    if [ -s /tmp/domain-join-session.json ]; then
        python - /tmp/domain-join-session.json <<'PY' >&2 || true
import json
import sys

document = json.load(open(sys.argv[1], encoding="utf-8"))
run = document["run"]
facts = {
    key: run.get(key)
    for key in ("outcome", "connection_state", "snapshots_admitted", "entities_admitted")
}
print(f"domain: the joining client ended with {facts}")
PY
    fi
fi

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

# What a refusal run has to end up saying, judged from the two records the run
# leaves behind rather than from anything the client printed about itself. The
# distinction it exists to make is the one a log line cannot make: a snapshot the
# Bridge handed over and Core refused, versus a run where nothing was refused at
# all. Core's own run document holds the refusal, and the ledger holds whether the
# Kin was ever told it could play.
if [ "${refusal_asked}" -eq 1 ]; then
    set +e
    python - /tmp/domain-session.json "${ledger}" "${baseline}" <<'PY' >&2
import json
import sqlite3
import sys

document_path, ledger_path, baseline = sys.argv[1], sys.argv[2], int(sys.argv[3])
try:
    with open(document_path, encoding="utf-8") as handle:
        document = json.load(handle)
except (OSError, ValueError) as error:
    print(f"domain: the run document cannot be read ({error})")
    raise SystemExit(1)
run = document.get("run")
if not isinstance(run, dict):
    print("domain: the run document has no run section")
    raise SystemExit(1)

problems = []
rejections = run.get("snapshot_rejections")
if not isinstance(rejections, list):
    # Absent or malformed is not "nothing was refused" — it is unreadable, and the
    # difference is what the run's exit code would otherwise paper over.
    problems.append("SNAPSHOT_REJECTIONS_UNREADABLE")
elif "NOT_AUTHORITATIVE" not in rejections:
    problems.append(f"NOT_AUTHORITATIVE_NOT_RECORDED:{rejections}")
admitted = run.get("snapshots_admitted")
if admitted != 0:
    problems.append(f"SNAPSHOTS_ADMITTED:{admitted}")

connection = sqlite3.connect(ledger_path)
try:
    def counted(event_type: str) -> int:
        row = connection.execute(
            "select count(*) from event where position > ? and event_type = ?",
            (baseline, event_type),
        ).fetchone()
        return int(row[0])

    if counted("JoinObserved") == 0:
        problems.append("NO_JOIN_RECORDED")
    if counted("PlayableEstablished") > 0:
        problems.append("PLAYABLEESTABLISHED_WITH_A_REFUSAL")
    if counted("InputLeaseGranted") > 0:
        problems.append("INPUTLEASEGRANTED_WITH_A_REFUSAL")
finally:
    connection.close()

for problem in problems:
    print(f"domain: the first snapshot was not refused as asked ({problem})")
if not problems:
    # Said out loud rather than left as silence: a judgement block that only
    # speaks when it is unhappy cannot be told apart, in a transcript, from a
    # block that never ran.
    print("domain: Core refused this run's first snapshot as asked")
raise SystemExit(1 if problems else 0)
PY
    judged=$?
    set -e
    if [ "${judged}" -ne 0 ]; then
        injection_failed=1
    fi
fi

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
    subject_document=/tmp/domain-session.json
    subject_username="${player}"
    world_run_args=()
    if [ "${case_on}" = "joiner" ]; then
        # The case is about the client that joined, so its document is the run's own
        # record — and the world it joined is named by the run that hosted it, which is
        # the only place a hosted world's identity was measured. A joining client has no
        # snapshot of its own to report.
        if [ "${join_ready}" -ne 1 ]; then
            printf 'domain: this case is about a joining run, and this run had no joiner\n' >&2
            exit 2
        fi
        subject_document=/tmp/domain-join-session.json
        subject_username="${join_username}"
        world_run_args=(--world-run-document /tmp/domain-session.json)
        # And this run's own world inputs are dropped, deliberately: a dedicated server
        # profile is a *different* kind of world, and leaving it named would let a join
        # with an unreadable host document fall back to recording one that never ran
        # rather than being refused.
        world_args=()
    fi
    named_run=(--run-document "${subject_document}")
    if [ ! -s "${subject_document}" ]; then
        named_run=(--run-id "${run_id}")
    fi
    # The record of the fault this run injected, when it injected one. It is named
    # by its path and read once by the sealer, which seals the same bytes it judged.
    #
    # A report request travels through the same channel and the same artifact name,
    # because it is the same kind of fact — what the harness did to this run — and
    # the guard above makes sure only one of the two can be here at a time. It is
    # sealed as its own bytes: the sealer validates the record it is about to seal,
    # so a PASS bundle cannot be read as "Core refused a snapshot the client only
    # claimed to have sent" once the request is in it.
    fault_args=()
    if [ -s "${fault_path}" ]; then
        fault_args=(--fault-injection "${fault_path}")
    elif [ -s "${request_path}" ]; then
        fault_args=(--fault-injection "${request_path}")
    fi
    # The soak's own measurement and the request it answers, when this run soaked.
    # Same rule as the fault record: named by path, read once, and the bytes that
    # were judged are the bytes that are sealed.
    soak_args=()
    if [ -s "${soak_summary}" ]; then
        soak_args=(--soak-samples "${soak_file}" --soak-summary "${soak_summary}")
    fi
    python /src/tools/seal_run_evidence.py \
        --data-root /data \
        --case "${case_file}" \
        --profile "${profile}" \
        "${world_args[@]}" \
        "${named_run[@]}" \
        "${world_run_args[@]}" \
        "${fault_args[@]}" \
        "${soak_args[@]}" \
        --username "${subject_username}" \
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
