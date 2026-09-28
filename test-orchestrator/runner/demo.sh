#!/usr/bin/env bash
#
# One command for the end-to-end demo: bring up the isolated 1.20.1-class domain,
# let Core probe its version, resolve and prepare the matching client, join,
# turn and walk and release the key, then stop.
#
# This is a composition of `run.sh`, not a second harness. Every stage below is
# the product's own code path — `--auto-bundle` is what picks the recipe, and the
# store fill is what prepares the client — so nothing here has to be kept in step
# with the product except the arguments it passes.
#
# Usage:
#   MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/demo.sh
#   MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/demo.sh --again
#   bash test-orchestrator/runner/demo.sh --gateway
#
# `--again` is the repeat-start check: same volume, same Kin root, so the store is
# already filled and the run should go straight to the world. `--gateway` serves
# the read-only Dashboard projection over whatever this demo's volume holds and
# publishes it on this machine's loopback, which is what lets a browser on the host
# read the session the demo just ran.
#
# Environment (all but the jar have defaults):
#   MINEKIN_DEMO_VOLUME      named volume holding the Kin root      (minekin-local-demo)
#   MINEKIN_DEMO_KIN         Kin root this demo owns                (kin-local-demo)
#   MINEKIN_DEMO_USERNAME    the account the world admits           (Kin)
#   MINEKIN_DEMO_SERVER_PROFILE  in-container Server Profile path   (the 1.20.1 controlled one)
#   MINEKIN_DEMO_REGISTRY    in-container bundle registry path      (the reviewed tested bundles)
#   MINEKIN_DEMO_MAX_BYTES   what an automatic bundle fill may fetch (2000000000)
#   MINEKIN_DEMO_WALK_SECONDS  how long the forward key is held     (8)
#   MINEKIN_DEMO_TURN_DEGREES  how far the run looks to the right   (45)
#   MINEKIN_DEMO_SECONDS     how long the session may take          (2700 clean / 600 repeat)
#   MINEKIN_DEMO_HANDSHAKE_SECONDS  how long the client's Bridge has to prove
#                                  its session once the JVM is launched     (90)
#   MINEKIN_DEMO_PROBE_SECONDS how often the run asks the world     (1)
#   MINEKIN_DEMO_KILL          the player the world kills mid-session (unset = nobody dies)
#   MINEKIN_DEMO_KILL_AFTER_SECONDS  how long after that player's join line the world kills
#                                  it  (30) — the death is the release's other cause, so it
#                                  has to land behind the walk, not in the middle of it
#   MINEKIN_DEMO_GATEWAY_PORT  the loopback port --gateway publishes (8787)
#   MINEKIN_DEMO_CASE        name a registered case to seal this run against (unset)
#
set -euo pipefail

export MSYS_NO_PATHCONV=1

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${HERE}/../.." && pwd)"

IMAGE="${MINEKIN_RUNNER_IMAGE:-minekin-runner:local}"
VOLUME="${MINEKIN_DEMO_VOLUME:-minekin-local-demo}"
KIN="${MINEKIN_DEMO_KIN:-kin-local-demo}"
USERNAME="${MINEKIN_DEMO_USERNAME:-Kin}"
SERVER_PROFILE="${MINEKIN_DEMO_SERVER_PROFILE:-/src/tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json}"
REGISTRY="${MINEKIN_DEMO_REGISTRY:-/src/tests/fixtures/registry/reviewed-tested-bundles.json}"
MAX_BYTES="${MINEKIN_DEMO_MAX_BYTES:-2000000000}"
WALK_SECONDS="${MINEKIN_DEMO_WALK_SECONDS:-8}"
TURN_DEGREES="${MINEKIN_DEMO_TURN_DEGREES:-45}"
PROBE_SECONDS="${MINEKIN_DEMO_PROBE_SECONDS:-1}"
DEMO_CASE="${MINEKIN_DEMO_CASE:-}"
KILL_PLAYER="${MINEKIN_DEMO_KILL:-}"
KILL_AFTER_SECONDS="${MINEKIN_DEMO_KILL_AFTER_SECONDS:-30}"

# The death is a cause the world starts on its own, and the window reader's death control
# is about what a run looks like when the tail readings are a corpse's. For that to be a
# real reading the death has to come after the walk and its release, so an ask that places
# it inside the hold is refused here, before the volume work, rather than clamped.
death_env=()
if [ -n "${KILL_PLAYER}" ]; then
    case "${KILL_AFTER_SECONDS}" in
        '' | *[!0-9]*)
            printf 'demo: MINEKIN_DEMO_KILL_AFTER_SECONDS must be a whole number of seconds, got %q.\n' \
                "${MINEKIN_DEMO_KILL_AFTER_SECONDS}" >&2
            exit 2
            ;;
    esac
    if [ "${KILL_AFTER_SECONDS}" -le "${WALK_SECONDS}" ]; then
        printf 'demo: MINEKIN_DEMO_KILL_AFTER_SECONDS=%s places the death inside the %ss hold it is supposed to follow.\n' \
            "${KILL_AFTER_SECONDS}" "${WALK_SECONDS}" >&2
        exit 2
    fi
    if [ "${KILL_PLAYER}" != "${USERNAME}" ]; then
        printf 'demo: MINEKIN_DEMO_KILL names %s, which this run does not admit; the account is %s.\n' \
            "${KILL_PLAYER}" "${USERNAME}" >&2
        exit 2
    fi
    death_env=(MINEKIN_DOMAIN_KILL="${KILL_PLAYER}" MINEKIN_DOMAIN_KILL_AFTER_SECONDS="${KILL_AFTER_SECONDS}")
    printf 'demo: the world will kill %s %ss after its join line, so the walk has a corpse after it\n' \
        "${KILL_PLAYER}" "${KILL_AFTER_SECONDS}"
fi

# Core's own reviewed wait is 30 s, and on this host that is not enough to boot a
# client JVM. Measured on the 1.20.1 bundles this project has kept: the three that got
# into the world printed the client's `Setting user` line 17.0, 17.4 and 21.8 s after
# Core recorded the launch, and the four that ended `HANDSHAKE_TIMEOUT` printed it at
# 30.7 s or later — each with the Bridge reporting `BRIDGE_FAULT` a second after that
# line, because by then Core had already closed the listener the Bridge dials. 90 s is
# the same measurement with room for a colder container: it buys time for the client
# to start and nothing else, since no lease, admission bound or distance threshold is
# involved in it.
HANDSHAKE_SECONDS="${MINEKIN_DEMO_HANDSHAKE_SECONDS:-90}"

# Where the read model is published for `--gateway`. 8787 is `gateway.server`'s own
# default port, named here because the host-side binding has to be the same number on
# both halves and because a machine already holding 8787 needs to say so once.
GATEWAY_PORT="${MINEKIN_DEMO_GATEWAY_PORT:-8787}"

command="${1:-}"
case "${command}" in
    --again) command="again" ;;
    --gateway) command="gateway" ;;
    "") command="clean" ;;
    *)
        printf 'demo: unknown argument %q (expected --again, --gateway, or nothing)\n' "${command}" >&2
        exit 2
        ;;
esac

# One bound covers both waits the runner makes — becoming playable and the world
# seeing the walk — and only the first one is affected by whether the store has
# been filled. Measured on a fresh volume: a clean run spends most of its window
# fetching the bundle the registry names (about 740 MB), so 240 seconds is a
# window that expires while the download is still in flight and reports "never
# became playable" about a client that had not been launched yet. A repeat run
# resumes from a filled store and needs only the boot.
if [ "${command}" = "clean" ]; then
    SECONDS_LIMIT="${MINEKIN_DEMO_SECONDS:-2700}"
else
    SECONDS_LIMIT="${MINEKIN_DEMO_SECONDS:-600}"
fi

# The gateway half reads this volume and needs nothing else: no jar, and no
# session still running, because it projects the ledger and the sealed evidence
# that are already on disk.
#
# `--host 0.0.0.0` is not this service reaching the network. Docker forwards a
# published port to the container's own address, so a process that listens only on
# the container's loopback cannot be reached through one; what decides who can
# connect is the host-side binding, and `run.sh` writes that as 127.0.0.1 and takes
# nothing but a port number from here. The read model answers GET on three paths and
# refuses every other verb, so publishing it opens no way to change anything.
if [ "${command}" = "gateway" ]; then
    printf 'demo: the read model will be reachable at http://127.0.0.1:%s -- from this machine only\n' \
        "${GATEWAY_PORT}"
    printf 'demo: then serve the panel, naming this port as its proxy target, and open\n'
    printf 'demo:   MINEKIN_GATEWAY_TARGET=http://127.0.0.1:%s pnpm --dir dashboard dev\n' "${GATEWAY_PORT}"
    printf 'demo:   http://127.0.0.1:5175/?adapter=gateway&gateway=/gateway\n'
    printf 'demo: (the panel reaches the published gateway through the dev-server proxy; the\n'
    printf 'demo:  target defaults to 8787, so a run on another port has to say so or the\n'
    printf 'demo:  panel reads a port nothing answered on and shows itself disconnected)\n'
    exec env MINEKIN_RUNNER_DATA="${VOLUME}" MINEKIN_KIN_ID="${KIN}" \
        MINEKIN_RUNNER_PUBLISH="${GATEWAY_PORT}" \
        bash "${HERE}/run.sh" --shell \
        "python -m gateway.server --data-root /data --kin ${KIN} \
--host 0.0.0.0 --port ${GATEWAY_PORT} ${GATEWAY_ARGS:-}"
fi

SERVER_JAR="${MINEKIN_SERVER_JAR:-}"
if [ -z "${SERVER_JAR}" ] || [ ! -f "${SERVER_JAR}" ]; then
    printf 'demo: MINEKIN_SERVER_JAR must name the server jar the world runs from.\n' >&2
    printf '      Get one with: uv run python tools/verify_supply_chain.py \\\n' >&2
    printf '          --version 1.20.1 --save-server .tmp/mc-1.20.1-server.jar --max-bytes 60000000\n' >&2
    printf '      (the version you save for is the version your Server Profile allows)\n' >&2
    exit 2
fi
if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
    printf 'demo: the runner image %s is not present. Build it with:\n' "${IMAGE}" >&2
    printf '      docker build -f test-orchestrator/runner/Dockerfile -t %s .\n' "${IMAGE}" >&2
    exit 2
fi
docker volume create "${VOLUME}" >/dev/null

# A clean run owns a Kin root nobody has used yet; a repeat run uses the one this
# demo filled. Probing it from inside the container is what keeps the answer about
# the volume rather than about the host directory tree.
if [ "${command}" = "clean" ]; then
    if env MINEKIN_RUNNER_DATA="${VOLUME}" bash "${HERE}/run.sh" --shell \
        "[ -d /data/kin/${KIN} ]" >/dev/null 2>&1; then
        printf 'demo: the Kin root %s already has a store on %s; ask for --again, or point\n' "${KIN}" "${VOLUME}" >&2
        printf '      MINEKIN_DEMO_KIN at a name this demo has not used.\n' >&2
        exit 2
    fi
    printf 'demo: initialising the Kin root %s on volume %s\n' "${KIN}" "${VOLUME}"
    env MINEKIN_RUNNER_DATA="${VOLUME}" MINEKIN_KIN_ID="${KIN}" MINEKIN_USERNAME="${USERNAME}" \
        bash "${HERE}/run.sh" init --kin-id "${KIN}"
else
    if ! env MINEKIN_RUNNER_DATA="${VOLUME}" bash "${HERE}/run.sh" --shell \
        "[ -d /data/kin/${KIN} ]" >/dev/null 2>&1; then
        printf 'demo: --again asked for a repeat but volume %s has no Kin root %s.\n' "${VOLUME}" "${KIN}" >&2
        printf '      Run the demo without --again first.\n' >&2
        exit 2
    fi
    printf 'demo: repeating on the Kin root %s already on volume %s\n' "${KIN}" "${VOLUME}"
fi

# The version is asked of the world, not read from this script: the Server Profile
# says what it allows, Core resolves that against the registry, and the store fill
# downloads whatever the resolved recipe needs — which is why a clean run on an
# empty store takes minutes and a repeat takes seconds.
printf 'demo: probing %s, preparing the bundle the registry names for it, joining, then walking %ss and turning %s%s\n' \
    "${SERVER_PROFILE##*/}" "${WALK_SECONDS}" "${TURN_DEGREES}" "°"
printf 'demo: this run may take up to %ss before the harness stops asking\n' "${SECONDS_LIMIT}"
printf 'demo: the client is given %ss to prove its session once its JVM starts\n' "${HANDSHAKE_SECONDS}"

session_args=(
    session start
    --auto-bundle "${REGISTRY}"
    --server-profile "${SERVER_PROFILE}"
    --max-bytes "${MAX_BYTES}"
    --handshake-timeout-seconds "${HANDSHAKE_SECONDS}"
    --hold-forward-seconds "${WALK_SECONDS}"
    --look-yaw-degrees "${TURN_DEGREES}"
)

env "${death_env[@]}" \
    MINEKIN_RUNNER_DATA="${VOLUME}" \
    MINEKIN_SERVER_JAR="${SERVER_JAR}" \
    MINEKIN_KIN_ID="${KIN}" \
    MINEKIN_USERNAME="${USERNAME}" \
    MINEKIN_DOMAIN_PROBE="${USERNAME}" \
    MINEKIN_DOMAIN_PROBE_SECONDS="${PROBE_SECONDS}" \
    MINEKIN_DOMAIN_SECONDS="${SECONDS_LIMIT}" \
    MINEKIN_DOMAIN_CASE="${DEMO_CASE}" \
    bash "${HERE}/run.sh" domain "${session_args[@]}"

# `session start` ends non-zero on its own terms: the harness stopped the client,
# so the Bridge went with it (BRIDGE_LOST, exit 14). The run document is the
# verdict, so this script does not translate that exit into a failure of the demo.
printf '\ndemo: readback\n'
printf '  Kin root      : volume %s, /data/kin/%s\n' "${VOLUME}" "${KIN}"
printf '  run document  : the last JSON line above (Core'"'"'s own counts)\n'
printf '  evidence      : bash test-orchestrator/runner/run.sh --shell "python -m minekin_core evidence verify <run_id>"\n'
printf '                  with MINEKIN_RUNNER_DATA=%s\n' "${VOLUME}"
printf '  dashboard     : bash test-orchestrator/runner/demo.sh --gateway\n'
printf '                  then in another shell, naming the same port as the proxy target:\n'
printf '                  MINEKIN_GATEWAY_TARGET=http://127.0.0.1:%s pnpm --dir dashboard dev, and open\n' "${GATEWAY_PORT}"
printf '                  http://127.0.0.1:5175/?adapter=gateway&gateway=/gateway\n'
printf '                  Ctrl-C stops the read model; the Kin root on volume %s keeps the run.\n' "${VOLUME}"
