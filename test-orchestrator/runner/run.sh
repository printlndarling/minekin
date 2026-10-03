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
#         MINEKIN_RUNNER_PUBLISH=8787 bash test-orchestrator/runner/run.sh --shell \
#             python -m gateway.server --host 0.0.0.0 --port 8787
#         MINEKIN_RUNNER_PUBLISH=8787 MINEKIN_RUNNER_DETACH=1 \
#             MINEKIN_RUNNER_NAME=minekin-panel-gateway \
#             bash test-orchestrator/runner/run.sh --shell python -m gateway.server --kin kin-01
#         bash test-orchestrator/runner/run.sh server --accept-eula --allow-player Kin
#         MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/run.sh domain \
#             session start --profile <bundle> --server-profile <server profile>
#
# MINEKIN_RUNNER_FORWARD_ENV=<NAME,NAME> hands those host variables into a domain run by
# name — the shape an operator uses to get their model's key variable inside the container
# without this repository ever naming it or printing its value.
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

# Publishing one container port on the host, for the shapes where something outside
# the container has to reach a service inside it — today that is only the Dashboard's
# read model. It is off by default, and what it takes is a port number and nothing
# else: the host half of the binding is written here as 127.0.0.1, so the operator
# cannot name an interface with it and the demo cannot grow into a public listener by
# passing a different string. A service that is published this way is reachable from
# this machine's loopback and from no other address.
PUBLISH_ARGS=()
if [[ -n "${MINEKIN_RUNNER_PUBLISH:-}" ]]; then
    if [[ ! "${MINEKIN_RUNNER_PUBLISH}" =~ ^[1-9][0-9]{0,4}$ ]]; then
        echo "MINEKIN_RUNNER_PUBLISH must be one port number, and it is published on 127.0.0.1 only: ${MINEKIN_RUNNER_PUBLISH}" >&2
        exit 2
    fi
    PUBLISH_ARGS=(-p "127.0.0.1:${MINEKIN_RUNNER_PUBLISH}:${MINEKIN_RUNNER_PUBLISH}")
fi

# Start the container in the background under a name the caller can stop, for the
# one shape where a single command has to bring a service up, use it, and take it
# down again on the way out — the browsable Dashboard, which reads the published
# gateway while it serves the panel. `--rm` alone cannot answer that: a container
# nobody named cannot be stopped by whoever started it. So a detached run has to
# carry a name, and the name is checked here rather than left for docker to
# interpret, because a caller must not be able to pass a flag through it.
DETACH_ARGS=()
NAME_ARGS=()
if [[ -n "${MINEKIN_RUNNER_DETACH:-}" ]]; then
    if [[ "${MINEKIN_RUNNER_DETACH}" != "1" ]]; then
        echo "MINEKIN_RUNNER_DETACH takes 1 or nothing: ${MINEKIN_RUNNER_DETACH}" >&2
        exit 2
    fi
    if [[ -z "${MINEKIN_RUNNER_NAME:-}" ]]; then
        echo "MINEKIN_RUNNER_DETACH needs MINEKIN_RUNNER_NAME, so the caller can stop what it started." >&2
        exit 2
    fi
    if [[ ! "${MINEKIN_RUNNER_NAME}" =~ ^[A-Za-z][A-Za-z0-9_.-]*$ ]]; then
        echo "MINEKIN_RUNNER_NAME must start with a letter and hold only letters, digits, dot, dash, underscore: ${MINEKIN_RUNNER_NAME}" >&2
        exit 2
    fi
    DETACH_ARGS=(-d)
    NAME_ARGS=(--name "${MINEKIN_RUNNER_NAME}")
fi

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
            echo "    --version <minecraft version> \\" >&2
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
    # --- recipe-archive-path begin ---
    # The version-knowledge archive is opened by the session inside this container, where
    # `/src` is this repository; a host path naming a file this repository carries is
    # exported under the in-container spelling, and anything readable from neither side is
    # refused here, before docker, instead of carried to the composition root as a worse
    # sentence. A value already in container form is passed through after a host-side check.
    if [[ -n "${MINEKIN_RECIPE_ARCHIVE:-}" ]]; then
        case "${MINEKIN_RECIPE_ARCHIVE}" in
            /src/*)
                if [[ ! -f "${REPOSITORY_ROOT}/${MINEKIN_RECIPE_ARCHIVE#/src/}" ]]; then
                    echo "MINEKIN_RECIPE_ARCHIVE is not a file this repository carries: ${MINEKIN_RECIPE_ARCHIVE}" >&2
                    exit 2
                fi
                ;;
            *)
                if [[ ! -f "${MINEKIN_RECIPE_ARCHIVE}" ]]; then
                    echo "MINEKIN_RECIPE_ARCHIVE is not a file: ${MINEKIN_RECIPE_ARCHIVE}" >&2
                    exit 2
                fi
                archive_absolute="$(cd "$(dirname "${MINEKIN_RECIPE_ARCHIVE}")" && pwd)/$(basename "${MINEKIN_RECIPE_ARCHIVE}")"
                if command -v cygpath >/dev/null 2>&1; then
                    archive_absolute="$(cygpath -m "${archive_absolute}")"
                fi
                case "${archive_absolute}" in
                    "${REPOSITORY_ROOT}"/*)
                        export MINEKIN_RECIPE_ARCHIVE="/src/${archive_absolute#"${REPOSITORY_ROOT}/"}"
                        ;;
                    *)
                        echo "MINEKIN_RECIPE_ARCHIVE is outside ${REPOSITORY_ROOT}: ${MINEKIN_RECIPE_ARCHIVE}" >&2
                        exit 2
                        ;;
                esac
                ;;
        esac
    fi
    # --- recipe-archive-path end ---
    # `-e NAME` without a value forwards the host's, and an unset one stays
    # unset: the runner does not invent a world for the operator.
    EXTRA_ARGS=(-e MINEKIN_DOMAIN_SUMMON
        -e MINEKIN_DOMAIN_PROBE -e MINEKIN_DOMAIN_PROBE_SECONDS -e MINEKIN_DOMAIN_LOOK
        -e MINEKIN_DOMAIN_KILL -e MINEKIN_DOMAIN_KICK -e MINEKIN_DOMAIN_KILL_CORE
        # When that death happens is a separate ask, and `domain.sh` reads it by name;
        # undelivered it would silently fall back to the launcher's own six seconds, which
        # is not behind a walk longer than six.
        -e MINEKIN_DOMAIN_KILL_AFTER_SECONDS
        -e MINEKIN_DOMAIN_DIFFICULTY
        -e MINEKIN_DOMAIN_KILL_SERVER
        -e MINEKIN_DOMAIN_KILL_CLIENT
        -e MINEKIN_DOMAIN_SOAK_SECONDS -e MINEKIN_DOMAIN_SOAK_INTERVAL
        -e MINEKIN_DOMAIN_AUTONOMOUS_WAIT_SECONDS
        -e MINEKIN_DOMAIN_SILENCE -e MINEKIN_DOMAIN_STILL -e MINEKIN_DOMAIN_NO_SERVER
        -e MINEKIN_DOMAIN_CASE
        -e MINEKIN_DOMAIN_BLACK_HOLE
        -e MINEKIN_DOMAIN_NOT_WHITELISTED
        # The other three refusal scenarios, and they belong here rather than appended
        # somewhere else: these are one set, and a wrapper that forwards some of them
        # is worse than one that forwards none. `domain.sh` reads a knob that
        # never arrives as empty and takes its "not asked for" branch, so the run
        # completes, seals a bundle, and is evidence for a scenario that never
        # happened — which is the one failure this project treats as worse than red.
        -e MINEKIN_DOMAIN_ONLINE_MODE
        -e MINEKIN_DOMAIN_RESOURCE_PACK
        -e MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT
        -e MINEKIN_DOMAIN_USE_TARGET -e MINEKIN_DOMAIN_OPEN_LAN -e MINEKIN_DOMAIN_LAN_PORT
        -e MINEKIN_DOMAIN_JOIN -e MINEKIN_DOMAIN_JOIN_USERNAME
        -e MINEKIN_DOMAIN_CASE_ON
        -e MINEKIN_DOMAIN_SECONDS
        # The four joiner-control knobs of the bounded control driver. Same pass-through
        # rule as every name above — `-e NAME` carries the host's value when the operator
        # set one and leaves the name unset when they did not — because the driver is
        # default-off and an unset knob reads as "not asked for". Forwarding them is the
        # whole of this wrapper's involvement: the bound and refusal logic lives in
        # `domain.sh`, and this line invents no default of its own.
        -e MINEKIN_DOMAIN_JOIN_LOOK_YAW
        -e MINEKIN_DOMAIN_JOIN_LOOK_PITCH
        -e MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS
        -e MINEKIN_DOMAIN_JOIN_CONTROL_PRINT
        # The joining client's controlled-server destination, forwarded by name at last.
        # `domain.sh` has read this knob since H1k and `run.sh` never delivered it: a run
        # started through this wrapper read the name as empty, took the "not asked for"
        # branch, completed, sealed — and was evidence for a different shape than the one
        # the operator asked for. That is the same defect H1j closed for the four names
        # above, so it is closed the same way: the bare declaration below forwards the
        # host's value when the operator set one and leaves the name unset when they did
        # not. This line casts no default of its own.
        -e MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER
        # The run's second named probe target, forwarded the same bare way: this is
        # the whole of the wrapper's involvement, the append and the two named
        # refusals live in `domain.sh`, and — like every name above — this line
        # casts no default of its own.
        -e MINEKIN_DOMAIN_PROBE_SECOND
        # The world-skill run's breakable resource, forwarded the same bare way. It is
        # a knob `domain.sh` reads, so it must be named here: undelivered it arrives
        # empty, `domain.sh` takes its "not asked for" branch, and the run completes on
        # the trunk-less flat world it was never meant to demonstrate — the exact defect
        # H1j, H1l and H1o closed for the names around it. The append and the three
        # named refusals live in `domain.sh`; this line casts no default of its own.
        -e MINEKIN_DOMAIN_RESOURCE_TRUNK
        # The world-skill run's meal and hunger fixture, forwarded the same bare way and
        # for the same reason the trunk is: a knob `domain.sh` reads and this wrapper
        # does not deliver arrives empty, takes the "not asked for" branch, and the run
        # completes on the full-bar flat world it was never meant to demonstrate. The
        # append and the two named refusals live in `domain.sh`; this line casts no
        # default of its own.
        -e MINEKIN_DOMAIN_HUNGRY_KIN
        # The two seal-handover switches of the probe-target carrier. Forwarding them
        # is the whole of this wrapper's involvement: the value casting, the triple
        # and pair of named refusals all live in `domain.sh`, and these lines invent
        # no default of their own. They have to be named here at all because a knob
        # `domain.sh` reads and this wrapper does not deliver arrives empty, takes the
        # "not asked for" branch, and the run then completes and seals — evidence for
        # a different shape than the one the operator asked for, which is the exact
        # defect H1j and H1l closed for the names above. The default-off face does not
        # move because of the pass-through: unset on the host, docker leaves the name
        # unset in the container, and the joiner's seal command stays byte-for-byte
        # the trunk one.
        -e MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG
        -e MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS
        # The PlayerMind's own configuration. These are the names `model_access.py`
        # reads, and none of them is a credential: `MINEKIN_MODEL_API_KEY_ENV` names the
        # variable that holds the key, and the key itself arrives by that name through
        # MINEKIN_RUNNER_FORWARD_ENV below. Forwarded by name for the same reason as
        # every knob above — undelivered a knob arrives empty, the mind takes its
        # "no model configured" branch, and the run then reports a decision it made
        # locally as though the operator's model had been asked. `MINEKIN_PERSONA_SEED`
        # belongs here for the same reason: an unseeded persona is a different Kin.
        -e MINEKIN_MODEL_PROVIDER -e MINEKIN_MODEL_BASE_URL -e MINEKIN_MODEL
        -e MINEKIN_MODEL_API_KEY_ENV -e MINEKIN_MODEL_TIMEOUT_MS
        -e MINEKIN_MODEL_RUN_COST_CAP
        # The standing milestone, which since this build's parameterization is an argument and not
        # a constant: `goal_spec.py` reads these four and holds no default item, so a name that is
        # not delivered is a Kin with no standing craft target rather than the pickaxe one. A demo
        # names its product here, an operator names another, and the run document prints whichever
        # arrived. Ids and a count — no credential, and no address.
        -e MINEKIN_GOAL_PRODUCT -e MINEKIN_GOAL_QUANTITY
        -e MINEKIN_GOAL_SOURCE_ITEM -e MINEKIN_GOAL_DIRECTION
        # Which port this container should host a fake completions endpoint on, for the run that
        # proves the wiring above end to end. It is a port number, not an address and not a
        # credential: the listener binds loopback inside the container, and unset means no
        # listener at all, so every other case is unaffected byte for byte.
        -e MINEKIN_DOMAIN_FAKE_MODEL_PORT
        -e MINEKIN_PERSONA_SEED
        # The version-knowledge archive, opened by the session this container runs: a path
        # and an optional trusted digest, never a credential. Unset leaves the composition
        # root on its curated fallback, and the path guard above runs before docker sees
        # either name.
        -e MINEKIN_RECIPE_ARCHIVE -e MINEKIN_RECIPE_ARCHIVE_SHA256)
    # The operator's own credential variable, named by them and never by this script.
    # A key must not be written into the repository or a log, so there is no flag for a
    # value here: `MINEKIN_RUNNER_FORWARD_ENV` carries comma-separated variable NAMES and
    # each is passed as `-e NAME`, which is docker's own "forward the host's value for
    # this name". Nothing prints a value, and the repo never learns what the name is.
    if [[ -n "${MINEKIN_RUNNER_FORWARD_ENV:-}" ]]; then
        IFS=',' read -r -a forward_names <<<"${MINEKIN_RUNNER_FORWARD_ENV}"
        for forward_name in "${forward_names[@]}"; do
            if [[ ! "${forward_name}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
                # Refused rather than passed: a name that is not an identifier would carry
                # a flag or a value into docker's argument list, and this wrapper has no
                # business interpreting what the operator typed.
                echo "MINEKIN_RUNNER_FORWARD_ENV must hold comma-separated variable names (letters, digits, underscore; not starting with a digit): ${forward_name}" >&2
                exit 2
            fi
            EXTRA_ARGS+=(-e "${forward_name}")
        done
    fi
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
        echo "    --version <minecraft version> \\" >&2
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
    "${PUBLISH_ARGS[@]}" \
    "${NAME_ARGS[@]}" \
    "${DETACH_ARGS[@]}" \
    -e MINEKIN_HOME=/data \
    -e MINEKIN_USERNAME="${USERNAME}" \
    -e MINEKIN_KIN_ID \
    -e PYTHONPATH=/src/src \
    -e LD_LIBRARY_PATH=/opt/sqlite/lib \
    -w /src \
    "${IMAGE}" "${COMMAND[@]}" "$@"
