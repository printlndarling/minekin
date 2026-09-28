#!/usr/bin/env bash
#
# One command for the two-client control demo: this run starts the controlled
# 1.20.1 world, brings a second Kin into it, and drives *that* Kin — look, one
# bounded forward hold, then the release the hold's lapse causes — and seals the
# registered control case against the joining run.
#
# Like demo.sh this is a composition of `run.sh`, not a second harness. Every
# stage is the product's own code path; what lives here is the argument list the
# campaign needs and nothing else.
#
# It exists because the control case cannot be judged from one client: with a
# single Kin in the world the host's own walk would satisfy a judgement written
# about the joiner. So the shape that proves the control chain is this one, and
# the reading has to be reachable without an operator's scratch script.
#
# Usage:
#   MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/demo-lan.sh
#   MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/demo-lan.sh --again
#
# `--again` repeats on the Kin roots this demo already filled, so neither client
# has to fetch the bundle a second time.
#
# Environment (all but the jar have defaults):
#   MINEKIN_DEMO_LAN_VOLUME       named volume holding both Kin roots   (minekin-lan-demo)
#   MINEKIN_DEMO_LAN_HOST_KIN     the Kin that owns the world           (kin-lan-host)
#   MINEKIN_DEMO_LAN_JOIN_KIN     the Kin that joins and is judged      (kin-lan-join)
#   MINEKIN_DEMO_LAN_HOST_USERNAME   the account the world admits first (Kin)
#   MINEKIN_DEMO_LAN_JOIN_USERNAME   the account the world admits second (Kin2)
#   MINEKIN_DEMO_LAN_SEED_VOLUME  optional: a private volume whose root already holds
#                                 a filled artifact store, so the run skips the fetch
#   MINEKIN_DEMO_LAN_SEED_KIN     the root inside it to take the store from
#   MINEKIN_DEMO_LAN_BUNDLE       the recipe both clients prepare from  (bundle-candidate-1.20.1)
#   MINEKIN_DEMO_LAN_SERVER_PROFILE  the world this run starts          (controlled-offline-server-1.20.1)
#   MINEKIN_DEMO_LAN_TURN_DEGREES one look of at most 45°               (45)
#   MINEKIN_DEMO_LAN_PITCH_DEGREES one look of at most 30°               (-20)
#   MINEKIN_DEMO_LAN_HOLD_SECONDS  one forward hold of at most 2 s       (2)
#   MINEKIN_DEMO_LAN_PROBE_SECONDS how often the run asks the world     (1)
#   MINEKIN_DEMO_LAN_SOAK_SECONDS  how long the world is watched        (150)
#   MINEKIN_DEMO_LAN_SECONDS       how long the session may take        (900)
#   MINEKIN_DEMO_LAN_CASE          the registered case to seal          (v1201-lan-joiner-control-case-001)
#
# The three control bounds are the driver's, not this script's: `domain.sh`
# refuses an ask outside them rather than clamping it, so widening one here is
# not possible. Nothing in this file lowers a distance threshold or an
# authorisation window.
#
# This script never writes the canonical runner volume. Point
# MINEKIN_DEMO_LAN_VOLUME at your own volume.
set -euo pipefail

export MSYS_NO_PATHCONV=1

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGE="${MINEKIN_RUNNER_IMAGE:-minekin-runner:local}"
VOLUME="${MINEKIN_DEMO_LAN_VOLUME:-minekin-lan-demo}"
HOST_KIN="${MINEKIN_DEMO_LAN_HOST_KIN:-kin-lan-host}"
JOIN_KIN="${MINEKIN_DEMO_LAN_JOIN_KIN:-kin-lan-join}"
HOST_USERNAME="${MINEKIN_DEMO_LAN_HOST_USERNAME:-Kin}"
JOIN_USERNAME="${MINEKIN_DEMO_LAN_JOIN_USERNAME:-Kin2}"
SEED_VOLUME="${MINEKIN_DEMO_LAN_SEED_VOLUME:-}"
SEED_KIN="${MINEKIN_DEMO_LAN_SEED_KIN:-}"
SERVER_PROFILE="${MINEKIN_DEMO_LAN_SERVER_PROFILE:-/src/tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json}"
BUNDLE="${MINEKIN_DEMO_LAN_BUNDLE:-/src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json}"
TURN_DEGREES="${MINEKIN_DEMO_LAN_TURN_DEGREES:-45}"
PITCH_DEGREES="${MINEKIN_DEMO_LAN_PITCH_DEGREES:--20}"
HOLD_SECONDS="${MINEKIN_DEMO_LAN_HOLD_SECONDS:-2}"
PROBE_SECONDS="${MINEKIN_DEMO_LAN_PROBE_SECONDS:-1}"
SOAK_SECONDS="${MINEKIN_DEMO_LAN_SOAK_SECONDS:-150}"
SECONDS_LIMIT="${MINEKIN_DEMO_LAN_SECONDS:-900}"
CASE="${MINEKIN_DEMO_LAN_CASE:-v1201-lan-joiner-control-case-001}"
HANDSHAKE_SECONDS="${MINEKIN_DEMO_LAN_HANDSHAKE_SECONDS:-90}"

command="${1:-}"
case "${command}" in
    --again) command="again" ;;
    "") command="clean" ;;
    *)
        printf 'demo-lan: unknown argument %q (expected --again or nothing)\n' "${command}" >&2
        exit 2
        ;;
esac
if [ -n "${2:-}" ]; then
    printf 'demo-lan: takes at most one argument, got %q and %q\n' "${command}" "$2" >&2
    exit 2
fi

SERVER_JAR="${MINEKIN_SERVER_JAR:-}"
if [ -z "${SERVER_JAR}" ] || [ ! -f "${SERVER_JAR}" ]; then
    printf 'demo-lan: MINEKIN_SERVER_JAR must name the server jar the world runs from.\n' >&2
    printf '      Get one with: uv run python tools/verify_supply_chain.py \\\n' >&2
    printf '          --version 1.20.1 --save-server .tmp/mc-1.20.1-server.jar --max-bytes 60000000\n' >&2
    exit 2
fi
if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
    printf 'demo-lan: the runner image %s is not present. Build it with:\n' "${IMAGE}" >&2
    printf '      docker build -f test-orchestrator/runner/Dockerfile -t %s .\n' "${IMAGE}" >&2
    exit 2
fi
docker volume create "${VOLUME}" >/dev/null

kin_exists() {
    env MINEKIN_RUNNER_DATA="${VOLUME}" bash "${HERE}/run.sh" --shell \
        "[ -d /data/kin/$1 ]" >/dev/null 2>&1
}

if [ "${command}" = "clean" ]; then
    if kin_exists "${HOST_KIN}"; then
        printf 'demo-lan: the hosting Kin root %s already exists on %s; ask for --again, or point\n' "${HOST_KIN}" "${VOLUME}" >&2
        printf '      MINEKIN_DEMO_LAN_HOST_KIN at a name this demo has not used.\n' >&2
        exit 2
    fi
    # Only the hosting root is created here. The joining root is created by the
    # driver itself, with the joining account, because the root's ledger identity
    # row has to carry the directory's name — and a copied seed root carries the
    # seed's name instead.
    printf 'demo-lan: initialising the hosting Kin root %s on volume %s\n' "${HOST_KIN}" "${VOLUME}"
    env MINEKIN_RUNNER_DATA="${VOLUME}" MINEKIN_KIN_ID="${HOST_KIN}" MINEKIN_USERNAME="${HOST_USERNAME}" \
        bash "${HERE}/run.sh" init --kin-id "${HOST_KIN}"
    if kin_exists "${JOIN_KIN}"; then
        printf 'demo-lan: the joining root %s is left on this volume by an earlier attempt; the driver\n' "${JOIN_KIN}" >&2
        printf '      reuses its store, so the run still judges this run. Use a fresh\n' >&2
        printf '      MINEKIN_DEMO_LAN_JOIN_KIN if you want a clean joiner ledger.\n' >&2
    fi
else
    if ! kin_exists "${HOST_KIN}"; then
        printf 'demo-lan: --again asked for a repeat but volume %s has no hosting root %s.\n' "${VOLUME}" "${HOST_KIN}" >&2
        printf '      Run demo-lan.sh without --again first.\n' >&2
        exit 2
    fi
    printf 'demo-lan: repeating on the Kin roots already on volume %s\n' "${VOLUME}"
fi

# A store copied from a volume this project already filled is the same artifact
# set the automatic path would fetch — the named profile pins the recipe, and the
# run verifies the plan it launches against the store. It is offered because a
# cold fetch of the 1.20.1 bundle is about 740 MB and twenty-five minutes of
# network, and the control judgement does not depend on which of the two filled
# the store. The seed volume is mounted read-only: nothing here writes it.
if [ -n "${SEED_VOLUME}" ]; then
    if [ -z "${SEED_KIN}" ]; then
        printf 'demo-lan: MINEKIN_DEMO_LAN_SEED_VOLUME needs MINEKIN_DEMO_LAN_SEED_KIN too.\n' >&2
        exit 2
    fi
    printf 'demo-lan: seeding the artifact store from volume %s, root %s (read-only)\n' "${SEED_VOLUME}" "${SEED_KIN}"
    REPOSITORY_ROOT="$(cd "${HERE}/../.." && pwd)"
    if command -v cygpath >/dev/null 2>&1; then
        REPOSITORY_ROOT="$(cygpath -m "${REPOSITORY_ROOT}")"
    fi
    docker run --rm \
        --entrypoint /bin/bash \
        -v "${REPOSITORY_ROOT}:/src:ro" \
        -v "${VOLUME}:/data" \
        -v "${SEED_VOLUME}:/seed:ro" \
        -e LD_LIBRARY_PATH=/opt/sqlite/lib \
        "${IMAGE}" -c "
            set -euo pipefail
            [ -d /seed/kin/${SEED_KIN}/run/artifact-store ] || {
                printf 'seed root %s has no artifact store to copy\n' '${SEED_KIN}' >&2; exit 2; }
            mkdir -p /data/kin/${HOST_KIN}/run
            if [ -d /data/kin/${HOST_KIN}/run/artifact-store ]; then
                printf 'the hosting root already has a store; leaving it as it is\n'
            else
                cp -a /seed/kin/${SEED_KIN}/run/artifact-store /data/kin/${HOST_KIN}/run/artifact-store
            fi
        "
fi

printf 'demo-lan: world %s, hosting Kin %s (%s), joining Kin %s (%s)\n' \
    "${SERVER_PROFILE##*/}" "${HOST_KIN}" "${HOST_USERNAME}" "${JOIN_KIN}" "${JOIN_USERNAME}"
printf 'demo-lan: the joiner is asked to look %s°/%s° and hold forward %ss, then release\n' \
    "${TURN_DEGREES}" "${PITCH_DEGREES}" "${HOLD_SECONDS}"
printf 'demo-lan: the world is asked for the joiner'"'"'s position every %ss for %ss\n' \
    "${PROBE_SECONDS}" "${SOAK_SECONDS}"
printf 'demo-lan: the case sealed against the joining run is %s\n' "${CASE}"
printf 'demo-lan: this run may take up to %ss before the harness stops asking\n' "${SECONDS_LIMIT}"

# `--server-profile` is what makes this run own its world; the joiner goes into
# the dedicated server this very run starts, not into somebody else's. The probe
# target is the joiner's account, and the two seal switches are what let the
# bundle say which world and which name its readings came from.
#
# The bundle source is a named profile, not `--auto-bundle`. `domain.sh` refuses
# an auto run that also asks for a joining second client — "the joiner is started
# from a named bundle profile" — because an auto resolution picks a recipe mid-run
# and the joiner would be prepared from whatever it landed on. The default profile
# here is the recipe that same auto path resolves 1.20.1 to, so the shape is the
# reviewed one with its resolution made explicit.
session_args=(
    session start
    --profile "${BUNDLE}"
    --server-profile "${SERVER_PROFILE}"
    --handshake-timeout-seconds "${HANDSHAKE_SECONDS}"
)

env MINEKIN_RUNNER_DATA="${VOLUME}" \
    MINEKIN_SERVER_JAR="${SERVER_JAR}" \
    MINEKIN_KIN_ID="${HOST_KIN}" \
    MINEKIN_USERNAME="${HOST_USERNAME}" \
    MINEKIN_DOMAIN_JOIN="${JOIN_KIN}" \
    MINEKIN_DOMAIN_JOIN_USERNAME="${JOIN_USERNAME}" \
    MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1 \
    MINEKIN_DOMAIN_PROBE="${JOIN_USERNAME}" \
    MINEKIN_DOMAIN_PROBE_SECONDS="${PROBE_SECONDS}" \
    MINEKIN_DOMAIN_SECONDS="${SECONDS_LIMIT}" \
    MINEKIN_DOMAIN_SOAK_SECONDS="${SOAK_SECONDS}" \
    MINEKIN_DOMAIN_JOIN_LOOK_YAW="${TURN_DEGREES}" \
    MINEKIN_DOMAIN_JOIN_LOOK_PITCH="${PITCH_DEGREES}" \
    MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS="${HOLD_SECONDS}" \
    MINEKIN_DOMAIN_CASE="${CASE}" \
    MINEKIN_DOMAIN_CASE_ON=joiner \
    MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG=1 \
    MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS=1 \
    bash "${HERE}/run.sh" domain "${session_args[@]}"

printf '\ndemo-lan: readback\n'
printf '  Kin roots     : volume %s, /data/kin/%s and /data/kin/%s\n' "${VOLUME}" "${HOST_KIN}" "${JOIN_KIN}"
printf '  run document  : the last JSON line above (Core'"'"'s own counts)\n'
printf '  the window    : uv run python tools/read_move_window.py --kin %s \\\n' "${JOIN_KIN}"
printf '                      --data-root-volume %s\n' "${VOLUME}"
printf '  evidence      : bash test-orchestrator/runner/run.sh --shell "python -m minekin_core evidence verify <run_id>"\n'
printf '                  with MINEKIN_RUNNER_DATA=%s\n' "${VOLUME}"
