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
if [[ "${1:-}" == "--shell" ]]; then
    shift
    ENDPOINT=(--entrypoint /bin/bash)
    COMMAND=(-lc "$*")
fi

exec docker run --rm \
    "${ENDPOINT[@]}" \
    -v "${REPOSITORY_ROOT}:/src:ro" \
    -v "${DATA_VOLUME}:/data" \
    -e MINEKIN_HOME=/data \
    -e MINEKIN_USERNAME="${USERNAME}" \
    -e PYTHONPATH=/src/src \
    -e LD_LIBRARY_PATH=/opt/sqlite/lib \
    -w /src \
    "${IMAGE}" "${COMMAND[@]}" "$@"
