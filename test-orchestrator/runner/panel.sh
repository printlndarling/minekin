#!/usr/bin/env bash
#
# One command to watch a demo session in the browser: start the read model over the
# Kin root a demo filled, wait until the published port actually answers, then serve
# the Dashboard against it — and take the gateway down again on the way out.
#
# Before this, `--gateway` printed the two commands the operator still had to assemble
# by hand in a second terminal, including the proxy target the panel has to be told.
# That is the difference between a demo a developer can run and an entry a user can
# run, so the assembly lives here instead.
#
# The gateway container is started detached under a name and stopped by this script
# alone: a container that was already here when the command started is reported and
# left untouched, because nothing under this entry stops a process it did not start.
#
# Usage:
#   MINEKIN_PANEL_VOLUME=<volume> MINEKIN_PANEL_KIN=<kin> \
#       bash test-orchestrator/runner/panel.sh
#
# Environment:
#   MINEKIN_PANEL_VOLUME          named volume holding the Kin root   (required)
#   MINEKIN_PANEL_KIN             which Kin root to project           (required)
#   MINEKIN_PANEL_GATEWAY_PORT    loopback port for the gateway       (8787)
#   MINEKIN_PANEL_PORT            loopback port for the panel         (5175)
#   MINEKIN_PANEL_CONTAINER       the gateway container this run owns (minekin-panel-gateway)
#   MINEKIN_PANEL_WAIT_SECONDS    how long to wait for the gateway    (60)
#   MINEKIN_PANEL_GATEWAY_ARGS    extra arguments for gateway.server  (none)
#   MINEKIN_PANEL_AGENT           the panel command                   (pnpm)
#
set -euo pipefail

export MSYS_NO_PATHCONV=1

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${HERE}/../.." && pwd)"

IMAGE="${MINEKIN_RUNNER_IMAGE:-minekin-runner:local}"
VOLUME="${MINEKIN_PANEL_VOLUME:-}"
KIN="${MINEKIN_PANEL_KIN:-}"
GATEWAY_PORT="${MINEKIN_PANEL_GATEWAY_PORT:-8787}"
PANEL_PORT="${MINEKIN_PANEL_PORT:-5175}"
CONTAINER="${MINEKIN_PANEL_CONTAINER:-minekin-panel-gateway}"
WAIT_SECONDS="${MINEKIN_PANEL_WAIT_SECONDS:-60}"
PANEL_AGENT="${MINEKIN_PANEL_AGENT:-pnpm}"

refuse() {
    printf 'panel: %s\n' "$1" >&2
    shift
    while [ "$#" -gt 0 ]; do
        printf '      %s\n' "$1" >&2
        shift
    done
    exit 2
}

# Ports and the wait are checked the way the demo entries check theirs: a typo in a
# listener number is a mistake about the machine, not a default this script may pick.
for pair in "MINEKIN_PANEL_GATEWAY_PORT=${GATEWAY_PORT}" \
    "MINEKIN_PANEL_PORT=${PANEL_PORT}" \
    "MINEKIN_PANEL_WAIT_SECONDS=${WAIT_SECONDS}"; do
    name="${pair%%=*}"
    value="${pair#*=}"
    case "${value}" in
        '' | *[!0-9]*) refuse "${name} must be a whole number, got ${value}." ;;
    esac
    if [ "${name}" != "MINEKIN_PANEL_WAIT_SECONDS" ] &&
        { [ "${value}" -le 0 ] || [ "${value}" -gt 65535 ]; }; then
        refuse "${name} must be a port between 1 and 65535, got ${value}."
    fi
done

[ -n "${VOLUME}" ] || refuse "MINEKIN_PANEL_VOLUME must name the volume the demo filled."
[ -n "${KIN}" ] || refuse "MINEKIN_PANEL_KIN must name the Kin root to project."

if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
    refuse "the runner image ${IMAGE} is not present." \
        "Build it with: docker build -f test-orchestrator/runner/Dockerfile -t ${IMAGE} ."
fi

# Whether the panel can be served at all is knowable before anything is started, and
# the answer is worth giving up front: the dev server is the long-running half, and a
# missing tool is only discovered after the gateway has been left listening.
if ! command -v "${PANEL_AGENT}" >/dev/null 2>&1; then
    refuse "${PANEL_AGENT} is not on this machine's PATH, so the panel cannot be served." \
        "Install the dashboard's dependencies with: pnpm --dir dashboard install" \
        "Or name another command with MINEKIN_PANEL_AGENT."
fi
if [ ! -d "${REPOSITORY_ROOT}/dashboard/node_modules" ]; then
    refuse "dashboard/node_modules is missing, so the panel has nothing to serve from." \
        "Install it with: pnpm --dir dashboard install"
fi
# The readiness check is the only thing in this entry that talks to the published port,
# and it is a loopback request from this machine to it — the same address the panel's
# proxy will use. Without a prober the entry would start a container it cannot confirm
# and then block on a guess.
if ! command -v curl >/dev/null 2>&1; then
    refuse "curl is not on this machine's PATH, so this entry cannot confirm the read model." \
        "Use the two-terminal path instead: demo.sh --gateway, then serve the panel yourself."
fi

# A name docker already holds is either this script's own leftover or somebody else's
# container, and the two are not told apart from here. Refusing both ways is the safe
# reading: this entry never stops a container it did not start.
if [ -n "$(docker ps -a --filter "name=^/${CONTAINER}$" --quiet 2>/dev/null || true)" ]; then
    refuse "a container named ${CONTAINER} is already registered here." \
        "This command only stops the container it starts, so it will not take that one over." \
        "Remove it yourself if it is this command's own leftover, or name another with" \
        "MINEKIN_PANEL_CONTAINER."
fi

kin_exists() {
    env MINEKIN_RUNNER_DATA="${VOLUME}" bash "${HERE}/run.sh" --shell \
        "[ -d /data/kin/$1 ]" >/dev/null 2>&1
}

if ! kin_exists "${KIN}"; then
    refuse "Kin root ${KIN} is not on volume ${VOLUME}, so there is no session to show." \
        "Run the demo first, or name the root it filled with MINEKIN_PANEL_KIN."
fi

# The panel reads the gateway through its own dev-server proxy, so the browser never
# makes a cross-origin request and the gateway needs no CORS answer of its own. The
# proxy target defaults to 8787, which is why a run on another port has to name it:
# without it the panel reads a port nothing answered on and shows itself disconnected.
MINEKIN_RUNNER_DATA="${VOLUME}" MINEKIN_KIN_ID="${KIN}" \
    MINEKIN_RUNNER_PUBLISH="${GATEWAY_PORT}" \
    MINEKIN_RUNNER_DETACH=1 MINEKIN_RUNNER_NAME="${CONTAINER}" \
    bash "${HERE}/run.sh" --shell \
    "python -m gateway.server --data-root /data --kin ${KIN} \
--host 0.0.0.0 --port ${GATEWAY_PORT} ${MINEKIN_PANEL_GATEWAY_ARGS:-}" >/dev/null

started="${CONTAINER}"
cleanup() {
    if [ -n "${started}" ]; then
        docker stop "${started}" >/dev/null 2>&1 || true
        started=""
    fi
}
# Armed before the readiness wait, because every way out of it — a refusal, a container
# that died, a timeout — has to take the gateway down with it. The INT/TERM handling is
# installed where the panel is served, since that is when there is a child to forward to.
trap cleanup EXIT

# `--host 0.0.0.0` inside the container is not this service reaching the network: the
# host-side binding is written as 127.0.0.1 by run.sh and takes only a port number.
# What is being waited for is therefore the loopback address the panel will use, and
# the container being alive is checked alongside it, because a gateway that refused to
# start would otherwise show up as a timeout.
#
# The body is discarded by the shell, not by curl. `-o /dev/null` cannot be used here:
# this script exports MSYS_NO_PATHCONV=1, so on Windows the literal path /dev/null
# reaches curl unconverted and every probe comes back rc=23 about a service that is
# answering fine. Measured on the 1.20.1 session volume: the same request returned
# `curl: (23) client returned ERROR on write of 4252 bytes` with `-o /dev/null` and
# exit 0 with the redirect, against the same running container.
probe_url="http://127.0.0.1:${GATEWAY_PORT}/api/v1/dashboard/snapshot"
deadline=$((SECONDS + WAIT_SECONDS))
while true; do
    if curl -fsS --max-time 5 "${probe_url}" >/dev/null 2>&1; then
        break
    fi
    if [ -z "$(docker ps --filter "name=^/${CONTAINER}$" --quiet 2>/dev/null || true)" ]; then
        printf 'panel: the gateway container %s is not running any more; its last lines:\n' \
            "${CONTAINER}" >&2
        docker logs --tail 20 "${CONTAINER}" >&2 2>/dev/null || true
        exit 1
    fi
    if [ "${SECONDS}" -ge "${deadline}" ]; then
        # A port somebody else holds is one explanation, and it is not the only one, so
        # the container's own last lines go out with the refusal. Both failures this entry
        # first produced read as "nothing answered on 8792" while the gateway was serving
        # fine, and the lines that said so were already in `docker logs`.
        printf 'panel: the read model did not answer on %s within %ss.\n' \
            "${probe_url}" "${WAIT_SECONDS}" >&2
        printf '      the gateway container said:\n' >&2
        docker logs --tail 10 "${CONTAINER}" 2>&1 | sed 's/^/      | /' >&2 || true
        printf '      If this machine already holds port %s, name another with\n' "${GATEWAY_PORT}" >&2
        printf '      MINEKIN_PANEL_GATEWAY_PORT.\n' >&2
        exit 1
    fi
    sleep 1
done

printf 'panel: the read model answers on %s\n' "${probe_url}"
printf 'panel: open http://127.0.0.1:%s/?adapter=gateway&gateway=/gateway\n' "${PANEL_PORT}"
printf 'panel: Ctrl-C stops the panel and this command'\''s own gateway container\n'

# The panel is served from inside its own directory rather than with pnpm's `--dir`,
# because this script exports MSYS_NO_PATHCONV=1 and the dashboard path here is an MSYS
# one (/c/Users/...). Left unconverted, a Windows pnpm reads that as the literal path
# `C:\c` and fails with `ENOENT ... lstat 'C:\c'` before vite starts; `cd` is done by the
# shell, so the path never travels as an argument.
#
# The proxy target is named rather than left to its default: the dev server proxies
# `/gateway` to 8787 unless told, so a gateway published on another port would answer
# the readiness probe and still show the panel disconnected. Measured on the 8797 run —
# the panel's three reads came back HTTP 500 with the direct gateway returning 200 on
# the same paths, until the target was passed.
serve_panel() {
    cd "${REPOSITORY_ROOT}/dashboard"
    MINEKIN_GATEWAY_TARGET="http://127.0.0.1:${GATEWAY_PORT}" \
        "${PANEL_AGENT}" dev --port "${PANEL_PORT}" --strictPort
}

# The panel runs in the background so this script stays able to act on a signal. A
# foreground child would hold the wait: a TERM sent to this command's own pid reached
# bash, not the dev server, and the gateway container was left listening with nobody
# serving it — measured on the 8797/5179 run, where the container outlived the signal.
serve_panel &
panel_pid=$!

stop_panel() {
    kill -TERM "${panel_pid}" >/dev/null 2>&1 || true
    wait "${panel_pid}" 2>/dev/null || true
    cleanup
    exit 130
}
trap stop_panel INT TERM

rc=0
wait "${panel_pid}" || rc=$?
exit "${rc}"
