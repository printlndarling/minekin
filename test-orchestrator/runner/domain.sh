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
runs=/data/server-runs

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
    --keep-running >/tmp/domain-server.log 2>&1 &
server_pid=$!

stop_the_server() {
    # SIGINT is what the tool treats as "stop cleanly"; it turns that into the
    # server's own `stop` command and waits for the world to be saved.
    kill -INT "${server_pid}" 2>/dev/null || true
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

# The session ends when the client does, and a client that has joined sits in
# the world, so the window is what ends it. `timeout` therefore exits 124 on a
# run that worked, which is why the session's ledger is read afterwards rather
# than judged by this exit code.
#
# It goes *inside* `xvfb-run`, not outside: signal it from the outside and the
# signal lands on the X server, which takes the client's display away and kills
# the client through a path that has nothing to do with the session. Measured —
# the client's stderr said `X connection to :99 broken`.
set +e
xvfb-run -a --server-args="-screen 0 1280x720x24" \
    timeout -s INT "${seconds}" \
    python -m minekin_core "$@"
status=$?
set -e
printf 'domain: session exited %s\n' "${status}" >&2
exit "${status}"
