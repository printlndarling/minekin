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
silence="${MINEKIN_DOMAIN_SILENCE:-}"
look="${MINEKIN_DOMAIN_LOOK:-}"
# How often the server is asked about the Kin. A look is over within a second
# of the join, so a run that wants a reading on both sides of it asks more
# often than the default — the pair is what shows a heading changed.
probe_seconds="${MINEKIN_DOMAIN_PROBE_SECONDS:-5}"
silenced=0
runs=/data/server-runs

# What this run was asked to do, read from the command that was given to it: the
# harness waits for what the session was told to do, not for what the operator
# happened to export as well.
hold_requested=0
for argument in "$@"; do
    case "${argument}" in
        --hold-forward-seconds) hold_requested=1 ;;
    esac
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

# And a run that is verifying the release a death causes has to be able to kill the
# Kin, which only the server can do.
kill_args=()
if [[ -n "${kill}" ]]; then
    kill_args=(--kill-player "${kill}")
fi

# One fresh directory per run, numbered past everything already there: a run
# directory is evidence and is only ever appended to.
n=1
while [ -e "${runs}/run-${n}" ]; do n=$((n + 1)); done
server_directory="${runs}/run-${n}"

# The tool's own chatter goes to /tmp rather than into the run directory: it
# creates that directory itself and refuses a non-empty one, which is the check
# that keeps an earlier run's world and log from being written over.
python /src/tools/run_controlled_server.py \
    --directory "${server_directory}" \
    --jar /server/server.jar \
    --accept-eula \
    --allow-player "${player}" \
    "${summon_args[@]}" \
    "${probe_args[@]}" \
    "${kill_args[@]}" \
    --keep-running >/tmp/domain-server.log 2>&1 &
server_pid=$!

stop_the_server() {
    # SIGTERM, not SIGINT. A background job of a non-interactive shell inherits
    # SIGINT set to ignore, so `kill -INT` on this process did nothing at all and
    # the server ran on until the container was killed — eight minutes of a run
    # that had already finished. Measured in the runner image: `SIGINT SIG_IGN`,
    # `SIGTERM SIG_DFL`, and the tool installs a handler for both now, so either
    # one reaches the server's own `stop` command and the world is saved.
    kill -TERM "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
}
trap stop_the_server EXIT

printf 'domain: server run directory %s\n' "${server_directory}" >&2

# The client is not started until the server says it is ready. A refused
# connection is not a test of the admission path, it is a test of the clock.
for _ in $(seq 1 480); do
    if grep -q 'Done (' "${server_directory}/server.log" 2>/dev/null; then
        break
    fi
    if ! kill -0 "${server_pid}" 2>/dev/null; then
        printf 'domain: the server exited before it reported ready\n' >&2
        tail -n 20 /tmp/domain-server.log >&2 || true
        exit 1
    fi
    sleep 1
done
if ! grep -q 'Done (' "${server_directory}/server.log" 2>/dev/null; then
    printf 'domain: the server never reported ready\n' >&2
    exit 1
fi
printf 'domain: server ready\n' >&2

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
    python -m minekin_core "$@" &
session_pid=$!
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
ledger=$(ls -1 /data/kin/*/kin.sqlite3 2>/dev/null | head -1)
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
deadline=$((SECONDS + seconds))
for _ in $(seq 1 "${seconds}"); do
    kill -0 "${session_pid}" 2>/dev/null || break
    [ "${SECONDS}" -lt "${deadline}" ] || break
    recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
        "select 1 from event where position > ${baseline} and event_type='PlayableEstablished' limit 1;" \
        2>/dev/null || true)
    if [ -n "${recorded}" ]; then
        playable=1
        break
    fi
    sleep 1
done
# Said out loud either way. A bound that expires quietly turns "the Kin never
# joined" into "the harness moved on", and the two need different answers: this
# one has already done it once, on a run whose client took three minutes to
# boot because the asset materialisation was cold.
if [ "${playable}" -eq 1 ]; then
    printf 'domain: the session is playable\n' >&2
else
    printf 'domain: the session never became playable within %ss\n' "${seconds}" >&2
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
if [[ -n "${probe}" && "${hold_requested}" -eq 1 ]]; then
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
        printf 'domain: the server saw the Kin walk and then stop\n' >&2
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

printf 'domain: stopping the session
' >&2

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
exit "${status}"
