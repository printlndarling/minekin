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
runs=/data/server-runs

# Empty means "the world is as vanilla generated it", which is what every run
# did before this existed — so it stays optional rather than becoming a required
# argument with an empty value.
summon_args=()
if [[ -n "${summon}" ]]; then
    summon_args=(--summon "${summon}")
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
# machine is a clock that is wrong on a slower one. The bound only decides how
# long a run that never joins is given before it is stopped anyway, and a run
# stopped before it joins still ends with a document.
#
# `last_event_type` alone is not this run's playable, it is the Kin's: the ledger
# is one per Kin and every domain run before this one ended at
# PlayableEstablished, so the question is already true when the session starts and
# waits for nothing. Measured — the first version of this stopped the session a
# second in, before the client had been recorded, and `session stop` had nothing
# to terminate. What makes it this run's is the ledger having *grown* since before
# the session started.
read_events() {
    grep -o '"events_recorded": [0-9]*' | grep -o '[0-9]*' | head -1
}
baseline=$(python -m minekin_core session status 2>/dev/null | { read_events || true; } || true)
baseline=${baseline:-0}
deadline=$((SECONDS + seconds))
for _ in $(seq 1 "${seconds}"); do
    kill -0 "${session_pid}" 2>/dev/null || break
    [ "${SECONDS}" -lt "${deadline}" ] || break
    status=$(python -m minekin_core session status 2>/dev/null || true)
    recorded=$(printf '%s' "$status" | { read_events || true; } || true)
    if [ "${recorded:-0}" -gt "${baseline}" ] &&
        printf '%s' "$status" | grep -q '"last_event_type": "PlayableEstablished"'; then
        printf 'domain: the session is playable; stopping it\n' >&2
        break
    fi
    sleep 1
done

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
