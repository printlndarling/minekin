#!/usr/bin/env bash
#
# Run one command inside the controlled client runner.
#
# The repository is mounted read-only and the CLI runs from the source tree,
# because `find_workspace_root` needs to see `bridge/` and `proto/` together and
# an installed wheel does not carry them. The data root is a named volume, so a
# session's overlay, ledger and artifact store outlive the container.
#
# `LD_LIBRARY_PATH` names the vendored SQLite explicitly. Baking it into the
# image would hide which library is in use; putting it on the command that runs
# keeps the answer visible where the command is read.
#
# Usage:  bash test-orchestrator/runner/run.sh doctor
#         bash test-orchestrator/runner/run.sh init --kin-id kin-01
#         bash test-orchestrator/runner/run.sh --shell glxinfo -B
#         bash test-orchestrator/runner/run.sh server --accept-eula --allow-player Kin
#         MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/run.sh domain \
#             session start --profile <bundle> --server-profile <server profile>
#
set -euo pipefail

# On MSYS the shell rewrites anything that looks like a path before docker sees
# it, which mangles `-v C:/...:/src:ro`.
export MSYS_NO_PATHCONV=1

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${HERE}/../.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then
    REPOSITORY_ROOT="$(cygpath -m "${REPOSITORY_ROOT}")"
fi

IMAGE="${MINEKIN_RUNNER_IMAGE:-minekin-runner:local}"
DATA_VOLUME="${MINEKIN_RUNNER_DATA:-minekin-runner-data}"
USERNAME="${MINEKIN_USERNAME:-Kin}"

# The base image's entrypoint execs its arguments as a program, so it has to be
# replaced: the thing to run here is the CLI module, not a binary called
# `doctor`.
ENDPOINT=(--entrypoint /opt/minekin/bin/python)
COMMAND=(-m minekin_core)
EXTRA_ARGS=()

# The server half. It reads the pinned jar from a host path the operator names,
# because the jar is not in the repository (it is 54 MB of Mojang's artifact, not
# ours) and not in the data volume either, and mounting it read-only is what
# keeps "which jar did this run use" answerable from the command.
#
# The EULA is not passed here. `run_controlled_server.py` refuses to write
# `eula=true` unless the operator asked for it, and this script does not decide
# that on their behalf — `--accept-eula` travels through with everything else.
if [[ "${1:-}" == "domain" ]]; then
    shift
    # A run that names no server profile joins no world: there is nothing to
    # start, so there is no jar to name either. Read from the session's own
    # arguments rather than from another switch, because those already say what
    # the run is.
    world=0
    for argument in "$@"; do
        case "${argument}" in
            --server-profile) world=1 ;;
        esac
    done
    # A black-hole run names a target and needs no server jar: the thing on the
    # other end is a listener that never speaks, not a world.
    if [[ -n "${MINEKIN_DOMAIN_BLACK_HOLE:-}" ]]; then
        world=0
    fi
    if [[ "${world}" -eq 1 ]]; then
        SERVER_JAR="${MINEKIN_SERVER_JAR:-}"
        if [[ -z "${SERVER_JAR}" ]]; then
            echo "MINEKIN_SERVER_JAR must name the pinned server jar." >&2
            echo "Get one with: uv run python tools/verify_supply_chain.py \\" >&2
            echo "    --save-server <path> --max-bytes 60000000" >&2
            exit 2
        fi
        if [[ ! -f "${SERVER_JAR}" ]]; then
            echo "MINEKIN_SERVER_JAR is not a file: ${SERVER_JAR}" >&2
            exit 2
        fi
        if command -v cygpath >/dev/null 2>&1; then
            SERVER_JAR="$(cygpath -m "${SERVER_JAR}")"
        fi
    fi
    # `-e NAME` without a value forwards the host's, and an unset one stays
    # unset: the runner does not invent a world for the operator.
    EXTRA_ARGS=(-e MINEKIN_DOMAIN_SUMMON
        -e MINEKIN_DOMAIN_PROBE -e MINEKIN_DOMAIN_PROBE_SECONDS -e MINEKIN_DOMAIN_LOOK
        -e MINEKIN_DOMAIN_KILL -e MINEKIN_DOMAIN_KICK -e MINEKIN_DOMAIN_KILL_CORE
        -e MINEKIN_DOMAIN_SILENCE -e MINEKIN_DOMAIN_STILL -e MINEKIN_DOMAIN_NO_SERVER
        -e MINEKIN_DOMAIN_CASE
        -e MINEKIN_DOMAIN_BLACK_HOLE
        -e MINEKIN_DOMAIN_NOT_WHITELISTED
        -e MINEKIN_DOMAIN_SECONDS)
    if [[ "${world}" -eq 1 ]]; then
        EXTRA_ARGS+=(-v "${SERVER_JAR}:/server/server.jar:ro")
    fi
    ENDPOINT=(--entrypoint /bin/bash)
    # The server and the client are both in this one container, which is the only
    # shape the loopback-only profile schema allows. The session's arguments are
    # passed straight through to the CLI.
    COMMAND=(-lc '/src/test-orchestrator/runner/domain.sh "$@"' minekin-runner)
elif [[ "${1:-}" == "server" ]]; then
    shift
    SERVER_JAR="${MINEKIN_SERVER_JAR:-}"
    if [[ -z "${SERVER_JAR}" ]]; then
        echo "MINEKIN_SERVER_JAR must name the pinned server jar." >&2
        echo "Get one with: uv run python tools/verify_supply_chain.py \\" >&2
        echo "    --save-server <path> --max-bytes 60000000" >&2
        exit 2
    fi
    if [[ ! -f "${SERVER_JAR}" ]]; then
        echo "MINEKIN_SERVER_JAR is not a file: ${SERVER_JAR}" >&2
        exit 2
    fi
    if command -v cygpath >/dev/null 2>&1; then
        SERVER_JAR="$(cygpath -m "${SERVER_JAR}")"
    fi
    EXTRA_ARGS=(-v "${SERVER_JAR}:/server/server.jar:ro")
    ENDPOINT=(--entrypoint /bin/bash)
    # Numbered under the data volume so a run's evidence outlives the container,
    # and never reused: a server run is a directory that only ever gets appended
    # to, so numbering has to skip everything that is already there. The tool
    # refuses a non-empty directory as well, so this is the cheap check in front
    # of the real one rather than the only one.
    read -r -d '' SERVER_COMMAND <<'INNER' || true
set -euo pipefail
n=1
while [ -e "/data/server-runs/run-${n}" ]; do n=$((n + 1)); done
directory="/data/server-runs/run-${n}"
printf 'server run directory: %s\n' "${directory}" >&2
exec python /src/tools/run_controlled_server.py \
    --directory "${directory}" --jar /server/server.jar "$@"
INNER
    COMMAND=(-lc "${SERVER_COMMAND}" minekin-runner)
elif [[ "${1:-}" == "--shell" ]]; then
    shift
    ENDPOINT=(--entrypoint /bin/bash)
    COMMAND=(-lc "$*")
fi

exec docker run --rm \
    "${ENDPOINT[@]}" \
    -v "${REPOSITORY_ROOT}:/src:ro" \
    -v "${DATA_VOLUME}:/data" \
    "${EXTRA_ARGS[@]}" \
    -e MINEKIN_HOME=/data \
    -e MINEKIN_USERNAME="${USERNAME}" \
    -e PYTHONPATH=/src/src \
    -e LD_LIBRARY_PATH=/opt/sqlite/lib \
    -w /src \
    "${IMAGE}" "${COMMAND[@]}" "$@"
