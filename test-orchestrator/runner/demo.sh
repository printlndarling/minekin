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
#   MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/demo.sh --skills
#   MINEKIN_SERVER_JAR=<path> bash test-orchestrator/runner/demo.sh --autonomous
#   bash test-orchestrator/runner/demo.sh --gateway
#   bash test-orchestrator/runner/demo.sh --browse
#
# `--again` is the repeat-start check: same volume, same Kin root, so the store is
# already filled and the run should go straight to the world. `--skills` runs the world-
# skill plan (`examples/skill-plan-gather-and-craft.json`) instead of the scripted walk
# and turn: it asks the world for a breakable trunk (`MINEKIN_DOMAIN_RESOURCE_TRUNK`,
# which stacks oak logs in the Kin's look because the flat fixed-seed world grows no
# trees) and hands the session `--skill-plan` rather than `--hold-forward-seconds`/
# `--look-yaw-degrees`, so the Kin acts only on what its own observation reported.
# `--autonomous` hands the session `--autonomous` instead of a plan, and that is the
# whole difference: nobody names the steps. The PlayerMind picks a goal from what the
# Kin can currently see and has, asks for one skill, and reads the next observation to
# decide whether the world agreed — so the sequence this run performs is a result of
# the run rather than an input to it, and an operator cannot say beforehand which skills
# it will attempt. It gets the same trunk ask, because a mind with nothing in view has
# nothing to choose. `MINEKIN_DEMO_AUTONOMOUS_STEPS` bounds how many skills it may try.
# `--gateway` serves
# the read-only Dashboard projection over whatever this demo's volume holds and
# publishes it on this machine's loopback, which is what lets a browser on the host
# read the session the demo just ran. `--browse` is that plus the panel: it brings up
# the read model, waits for it, and serves the Dashboard against it in one command, so
# the operator is not left assembling a second terminal's environment by hand.
#
# Environment (all but the jar have defaults):
#   MINEKIN_DEMO_VOLUME      named volume holding the Kin root      (minekin-local-demo)
#   MINEKIN_DEMO_KIN         Kin root this demo owns                (kin-local-demo)
#   MINEKIN_DEMO_USERNAME    the account the world admits           (Kin)
#   MINEKIN_DEMO_SERVER_PROFILE  in-container Server Profile path   (the 1.20.1 controlled one)
#   MINEKIN_DEMO_REGISTRY    in-container bundle registry path      (the reviewed tested bundles)
#   MINEKIN_DEMO_BUNDLE_PROFILE  name a bundle profile instead of a registry: the run admits
#                                exactly one bundle source, so setting this stops --auto-bundle
#                                from being passed and refuses the run if the registry was also
#                                named by hand. It exists for the shape where the bundle's bytes
#                                have moved and its sealed evidence has not been renewed yet: the
#                                registry is then a truthful refusal, not a bug to route around,
#                                and the local demo still has a reproducible entry.
#   MINEKIN_DEMO_MAX_BYTES   what an automatic bundle fill may fetch (2000000000)
#   MINEKIN_DEMO_WALK_SECONDS  how long the forward key is held     (8)
#   MINEKIN_DEMO_TURN_DEGREES  how far the run looks to the right   (45)
#   MINEKIN_DEMO_AUTONOMOUS_STEPS  how many skills --autonomous may attempt (12)
#   MINEKIN_DEMO_AUTONOMOUS_WAIT_SECONDS  how long the harness waits, after playable,
#                                  for --autonomous to write its own halt verdict before
#                                  it stops the client (300) — the cooperative key release
#                                  needs a live channel, not a mid-step SIGTERM
#   MINEKIN_DEMO_GOAL_PRODUCT  what --autonomous works toward, as an item id
#                                  (minecraft:wooden_pickaxe). Set it empty to ask for a Kin with
#                                  no standing craft target at all — Core reads no default item,
#                                  so an unset goal is a different run, not the pickaxe one.
#   MINEKIN_DEMO_GOAL_QUANTITY  how many of that item the run wants        (1)
#   MINEKIN_DEMO_GOAL_SOURCE_ITEM  the raw item the build starts from      (minecraft:oak_log)
#   MINEKIN_DEMO_GOAL_DIRECTION  a heading the run turns to before it works  (unset)
#                                  These four are where the demo's wooden-pickaxe chain lives.
#                                  Any item id the recipe table knows takes the pickaxe's place,
#                                  which is how one run shows the same craft code on something
#                                  else; only --autonomous is handed them, because a skill plan
#                                  names its own steps and a mind with no plan is the only thing
#                                  that reads a standing goal.
#   MINEKIN_DEMO_SECONDS     how long the session may take          (2700 clean / 600 repeat)
#   MINEKIN_DEMO_HANDSHAKE_SECONDS  how long the client's Bridge has to prove
#                                  its session once the JVM is launched     (90)
#   MINEKIN_DEMO_PROBE_SECONDS how often the run asks the world     (1)
#   MINEKIN_DEMO_STEP_SECONDS  how long one skill step may wait for a later reading
#                                  (unset = Core's own 5 s). It exists for the diagnosis of
#                                  a silent channel: with the default window a step that
#                                  gets no reading concludes UNKNOWN in 5 s and the harness
#                                  tears the world down, so the five seconds in which an
#                                  operator can look at the client are gone. Naming it
#                                  longer changes no verdict — the step still reports what
#                                  the readings said — it only keeps the world up while the
#                                  question is being asked.
#   MINEKIN_DEMO_KILL          the player the world kills mid-session (unset = nobody dies)
#   MINEKIN_DEMO_KILL_AFTER_SECONDS  how long after that player's join line the world kills
#                                  it  (30) — the death is the release's other cause, so it
#                                  has to land behind the walk, not in the middle of it
#   MINEKIN_DEMO_GATEWAY_PORT  the loopback port --gateway publishes (8787)
#   MINEKIN_DEMO_PANEL_PORT    the loopback port --browse serves the panel on (5175)
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
# Which bundle source the session is given. Only one may be named, and the CLI's own
# admission refuses a run that names both, so this decides it here rather than letting
# the argument list carry two sources to a process that will reject them.
BUNDLE_PROFILE="${MINEKIN_DEMO_BUNDLE_PROFILE:-}"
if [ -n "${BUNDLE_PROFILE}" ] && [ -n "${MINEKIN_DEMO_REGISTRY:-}" ]; then
    printf 'demo: MINEKIN_DEMO_BUNDLE_PROFILE names a bundle profile and MINEKIN_DEMO_REGISTRY names a registry; one run admits exactly one bundle source.\n' >&2
    printf '      Drop one of them -- the profile is the evidence-neutral read, the registry is the sealed-evidence one.\n' >&2
    exit 2
fi
MAX_BYTES="${MINEKIN_DEMO_MAX_BYTES:-2000000000}"
WALK_SECONDS="${MINEKIN_DEMO_WALK_SECONDS:-8}"
TURN_DEGREES="${MINEKIN_DEMO_TURN_DEGREES:-45}"
# The skill plan `--skills` hands the session. The repository is mounted read-only at
# `/src` inside the runner, so the in-container path is what the CLI is given.
SKILL_PLAN="${MINEKIN_DEMO_SKILL_PLAN:-/src/examples/skill-plan-gather-and-craft.json}"
STEP_SECONDS="${MINEKIN_DEMO_STEP_SECONDS:-}"
if [ -n "${STEP_SECONDS}" ]; then
    case "${STEP_SECONDS}" in
        '' | *[!0-9]*)
            printf 'demo: MINEKIN_DEMO_STEP_SECONDS must be a whole number of seconds, got %q.\n' \
                "${STEP_SECONDS}" >&2
            exit 2
            ;;
    esac
    if [ "${STEP_SECONDS}" -le 0 ]; then
        printf 'demo: MINEKIN_DEMO_STEP_SECONDS=%s asks for a step that may not wait at all.\n' \
            "${STEP_SECONDS}" >&2
        exit 2
    fi
fi
# How many skills the autonomous run may attempt. Core's own budget default is 24; the
# demo asks for half of that because a step is a real action in a real world and a wrong
# one costs its timeout, so a bound the operator can read in the command line beats one
# that only appears in the run document.
AUTONOMOUS_STEPS="${MINEKIN_DEMO_AUTONOMOUS_STEPS:-12}"
# How long, once the session is playable, the harness waits for the mind to write its own
# `AutonomousRunHalted` before it stops the client. A real endpoint answers within its
# timeout and a step waits for the reading that will confirm it, so a bound the whole
# budget of steps fits inside lets the loop end on its own verdict — and the stop then
# lands on a live channel, where the key release is confirmed rather than SIGTERM-ed.
AUTONOMOUS_WAIT="${MINEKIN_DEMO_AUTONOMOUS_WAIT_SECONDS:-300}"
# The standing goal, which is the demo's, not Core's. `MINEKIN_GOAL_*` is the name the
# product reads and it carries no default item — a run that hands it nothing has no
# milestone to hold, which is the shape that proves the point — so the wooden-pickaxe
# chain this demo has always walked is stated here and nowhere below it. `${VAR-default}`
# rather than `${VAR:-default}` on purpose: setting `MINEKIN_DEMO_GOAL_PRODUCT=` empty is
# an ask, and a colon would silently answer it with the pickaxe.
GOAL_PRODUCT="${MINEKIN_DEMO_GOAL_PRODUCT-minecraft:wooden_pickaxe}"
GOAL_QUANTITY="${MINEKIN_DEMO_GOAL_QUANTITY-1}"
GOAL_SOURCE_ITEM="${MINEKIN_DEMO_GOAL_SOURCE_ITEM-minecraft:oak_log}"
GOAL_DIRECTION="${MINEKIN_DEMO_GOAL_DIRECTION-}"
if [ -n "${GOAL_QUANTITY}" ]; then
    case "${GOAL_QUANTITY}" in
        *[!0-9]*)
            printf 'demo: MINEKIN_DEMO_GOAL_QUANTITY must be a whole number of items, got %q.\n' \
                "${GOAL_QUANTITY}" >&2
            exit 2
            ;;
    esac
    if [ "${GOAL_QUANTITY}" -lt 1 ]; then
        printf 'demo: MINEKIN_DEMO_GOAL_QUANTITY=%s asks for a goal of none; the Kin cannot hold zero of an item.\n' \
            "${GOAL_QUANTITY}" >&2
        exit 2
    fi
fi
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

# Where `--browse` serves the panel. The dev server forwards `/gateway/*` to the port
# above, so this number only has to differ when the machine already holds 5175.
PANEL_PORT="${MINEKIN_DEMO_PANEL_PORT:-5175}"

command="${1:-}"
case "${command}" in
    --again) command="again" ;;
    --skills) command="skills" ;;
    --autonomous) command="autonomous" ;;
    --gateway) command="gateway" ;;
    --browse) command="browse" ;;
    "") command="clean" ;;
    *)
        printf 'demo: unknown argument %q (expected --again, --skills, --autonomous, --gateway, --browse, or nothing)\n' "${command}" >&2
        exit 2
        ;;
esac

case "${AUTONOMOUS_STEPS}" in
    '' | *[!0-9]*)
        printf 'demo: MINEKIN_DEMO_AUTONOMOUS_STEPS must be a whole number of skills, got %q.\n' \
            "${AUTONOMOUS_STEPS}" >&2
        exit 2
        ;;
esac
case "${AUTONOMOUS_WAIT}" in
    '' | *[!0-9]* | 0)
        printf 'demo: MINEKIN_DEMO_AUTONOMOUS_WAIT_SECONDS must be a positive number of seconds, got %q.\n' \
            "${AUTONOMOUS_WAIT}" >&2
        exit 2
        ;;
esac
if [ -n "${BUNDLE_PROFILE}" ]; then
    # The value is an in-container path, and `/src` is this repository, so the file has
    # to be found under the name the container will read it by. Checked here rather than
    # left for the CLI because a profile that names nothing on disk would carry all the
    # way to the admission step and stop the run there: same refusal, worse sentence.
    host_path="${BUNDLE_PROFILE}"
    case "${BUNDLE_PROFILE}" in
        /src/*) host_path="${REPOSITORY_ROOT}/${BUNDLE_PROFILE#/src/}" ;;
    esac
    if [ ! -f "${host_path}" ] && [ ! -f "${BUNDLE_PROFILE}" ]; then
        printf 'demo: MINEKIN_DEMO_BUNDLE_PROFILE=%s names no file (%s is not readable from here).\n' \
            "${BUNDLE_PROFILE}" "${host_path}" >&2
        exit 2
    fi
fi

# One bound covers both waits the runner makes — becoming playable and the world
# seeing the walk — and only the first one is affected by whether the store has
# been filled. Measured on a fresh volume: a clean run spends most of its window
# fetching the bundle the registry names (about 740 MB), so 240 seconds is a
# window that expires while the download is still in flight and reports "never
# became playable" about a client that had not been launched yet. A repeat run
# resumes from a filled store and needs only the boot. `--skills` and `--autonomous`
# are first runs of the same kind, so they get the same window.
if [ "${command}" = "clean" ] || [ "${command}" = "skills" ] || [ "${command}" = "autonomous" ]; then
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

# The one-command reading of the same session: the entry that owns the volume and the
# Kin root names them here, and `panel.sh` brings up the read model, waits for the
# published port, and serves the Dashboard against it until the operator stops it.
if [ "${command}" = "browse" ]; then
    exec env MINEKIN_PANEL_VOLUME="${VOLUME}" MINEKIN_PANEL_KIN="${KIN}" \
        MINEKIN_PANEL_GATEWAY_PORT="${GATEWAY_PORT}" \
        MINEKIN_PANEL_PORT="${PANEL_PORT}" \
        MINEKIN_PANEL_CONTAINER="${MINEKIN_DEMO_PANEL_CONTAINER:-minekin-demo-panel-gateway}" \
        bash "${HERE}/panel.sh"
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

# ---------------------------------------------------------------------------
# Single data-root / single Kin exclusive guard.
#
# One volume holds one Kin root, and that root is a single-writer store: two demo
# sessions launched against it at once open the same save twice, and the second
# client tears the first (the losing session ends in the harness-stopped
# BRIDGE_LOST / exit 14, a harness artifact rather than a product verdict). Nothing
# on the store can tell a neighbour that another run is coming, so this takes an
# exclusive *host* lock keyed by volume + Kin root before any container touches it,
# and a losing run is refused by name rather than clobbering the holder.
#
# Why mkdir and not flock: there is no `flock` on a Windows/MSYS runner, and `mkdir`
# is atomic on every host this script runs on. A lock left by a wrapper killed
# before its EXIT trap ran must not wedge the store forever, so the lock is treated
# as fresh for one session window — a second run inside that window is refused, and
# past it the holder is presumed gone and the lock reclaimed. The window is the
# run's own SECONDS_LIMIT, so a live session never has its lock expire mid-flight;
# a lock whose owner line cannot be read fails closed (refused), never reclaimed.
# ---------------------------------------------------------------------------
lock_key="$(printf '%s' "${VOLUME}/${KIN}" | tr -c 'A-Za-z0-9._-' '_')"
LOCK_BASE="${MINEKIN_DEMO_LOCK_DIR:-${REPOSITORY_ROOT}/.tmp/demo-locks}"
mkdir -p "${LOCK_BASE}" 2>/dev/null
LOCK_DIR="${LOCK_BASE}/${lock_key}"

# The primitives live in a sibling file so a behavioral test can drive the real
# functions in isolation. Sourcing them into this shell keeps the acquire/refuse/
# reclaim block below — and the release trap `take_kin_lock_once` installs here —
# exactly as it read when the functions were inline.
# shellcheck source=./kin_lock.sh
source "${HERE}/kin_lock.sh"

# A reclaim of an expired lock re-takes it; if a racer wins that mkdir first it does
# not strip the winner's lock — the second `take` simply declines and this run refuses.
if ! take_kin_lock_once; then
    if held_lock_is_live; then
        printf 'demo: the Kin root %s on volume %s is already held by another demo run.\n' "${KIN}" "${VOLUME}" >&2
        printf '      One store is single-writer: this refuses to open it twice rather than\n' >&2
        printf '      launching a second client that would tear the first. Wait for that run,\n' >&2
        printf '      or — only once you are sure it is gone — remove its lock at %s.\n' "${LOCK_DIR}" >&2
        exit 6
    fi
    printf 'demo: reclaiming an expired Kin lock at %s (holder past its session window).\n' "${LOCK_DIR}"
    rm -rf "${LOCK_DIR}"
    if ! take_kin_lock_once; then
        printf 'demo: another run took the Kin root %s lock while this one was reclaiming; refusing.\n' "${KIN}" >&2
        exit 6
    fi
fi

# A clean run owns a Kin root nobody has used yet; a repeat run uses the one this
# demo filled. `--skills` and `--autonomous` are the same two cases asked with a
# different action on the end: the store is what decides, not the action, so a demo that
# has already filled one gets to run its skills on it instead of downloading 740 MB a
# second time. Probing from inside the container is what keeps the answer about the
# volume rather than about the host directory tree.
if [ "${command}" = "clean" ] || [ "${command}" = "skills" ] || [ "${command}" = "autonomous" ]; then
    if env MINEKIN_RUNNER_DATA="${VOLUME}" bash "${HERE}/run.sh" --shell \
        "[ -d /data/kin/${KIN} ]" >/dev/null 2>&1; then
        # The plain demo run refuses a filled root because its own point is the download;
        # the two skill runs have no such point, so they carry on under the repeat's words.
        if [ "${command}" = "clean" ]; then
            printf 'demo: the Kin root %s already has a store on %s; ask for --again, or point\n' "${KIN}" "${VOLUME}" >&2
            printf '      MINEKIN_DEMO_KIN at a name this demo has not used.\n' >&2
            exit 2
        fi
        printf 'demo: the Kin root %s already has a store on %s -- running on that filled store\n' \
            "${KIN}" "${VOLUME}"
    else
        printf 'demo: initialising the Kin root %s on volume %s\n' "${KIN}" "${VOLUME}"
        env MINEKIN_RUNNER_DATA="${VOLUME}" MINEKIN_KIN_ID="${KIN}" MINEKIN_USERNAME="${USERNAME}" \
            bash "${HERE}/run.sh" init --kin-id "${KIN}"
    fi
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
# says what it allows, Core resolves that against the bundle source this run names, and
# the store fill downloads whatever the resolved recipe needs — which is why a clean run
# on an empty store takes minutes and a repeat takes seconds.
if [ -n "${BUNDLE_PROFILE}" ]; then
    bundle_source="the bundle profile ${BUNDLE_PROFILE##*/}"
else
    bundle_source="the bundle the registry names"
fi
case "${command}" in
    skills)
        printf 'demo: probing %s, preparing %s for it, joining, then running the skill plan %s (the world stacks an oak trunk in the Kin'"'"'s look to break)\n' \
            "${SERVER_PROFILE##*/}" "${bundle_source}" "${SKILL_PLAN##*/}"
        ;;
    autonomous)
        printf 'demo: probing %s, preparing %s for it, joining, then letting the PlayerMind choose up to %s skills from what the Kin sees (the world stacks an oak trunk in the Kin'"'"'s look to break)\n' \
            "${SERVER_PROFILE##*/}" "${bundle_source}" "${AUTONOMOUS_STEPS}"
        printf 'demo: nobody names the steps for this run -- which skills it attempts is what the readings decide,\n'
        printf 'demo: so this line cannot tell you the sequence, and neither can the log until the steps land\n'
        if [ -n "${GOAL_PRODUCT}" ]; then
            goal_facing=""
            [ -z "${GOAL_DIRECTION}" ] || goal_facing=", facing ${GOAL_DIRECTION}"
            printf 'demo: this demo hands the mind a standing goal: %s of %s, from %s%s\n' \
                "${GOAL_QUANTITY}" "${GOAL_PRODUCT}" "${GOAL_SOURCE_ITEM}" "${goal_facing}"
            printf 'demo: the item is named here and not in Core, so any recipe the table knows can stand in\n'
            printf 'demo:   for it, and a run that names a different one is the same code asked for that\n'
        else
            printf 'demo: no standing goal is handed to this run, so the mind holds nothing it was told to want\n'
            printf 'demo: and chooses from what the Kin sees -- this is the shape with no default item\n'
        fi
        ;;
    *)
        printf 'demo: probing %s, preparing %s for it, joining, then walking %ss and turning %s%s\n' \
            "${SERVER_PROFILE##*/}" "${bundle_source}" "${WALK_SECONDS}" "${TURN_DEGREES}" "°"
        ;;
esac
printf 'demo: this run may take up to %ss before the harness stops asking\n' "${SECONDS_LIMIT}"
printf 'demo: the client is given %ss to prove its session once its JVM starts\n' "${HANDSHAKE_SECONDS}"

session_args=(
    session start
    --server-profile "${SERVER_PROFILE}"
    --handshake-timeout-seconds "${HANDSHAKE_SECONDS}"
)
# Exactly one bundle source, and which one it is came from the environment above rather
# than from a switch: the CLI's own admission refuses a run that names both, and it also
# refuses `--max-bytes` under a profile — the budget bounds an automatic fill, and a named
# recipe is not an automatic fill. So the budget travels with the registry and no further.
if [ -n "${BUNDLE_PROFILE}" ]; then
    session_args+=(--profile "${BUNDLE_PROFILE}")
else
    session_args+=(--auto-bundle "${REGISTRY}" --max-bytes "${MAX_BYTES}")
fi
# The scripted run holds the forward key and turns; `--skills` runs the world-skill
# plan instead — every step acting only on what the client's own observation reported.
# The CLI is asked for the plan *alone*, with no `--hold-forward-seconds`/
# `--look-yaw-degrees`: the plan carries its own walk to the drop, and the two shapes
# are alternatives rather than a combined ask. `--autonomous` is the third alternative:
# it names no steps at all, and the mind asks for one skill at a time against the
# reading it has. All three need the same thing from the world — something in view that
# a skill can act on — so the trunk ask belongs to both skill shapes, not to one.
goal_env=()
case "${command}" in
    skills)
        session_args+=(--skill-plan "${SKILL_PLAN}")
        trunk_env=(MINEKIN_DOMAIN_RESOURCE_TRUNK=1)
        ;;
    autonomous)
        session_args+=(--autonomous --autonomous-steps "${AUTONOMOUS_STEPS}")
        trunk_env=(MINEKIN_DOMAIN_RESOURCE_TRUNK=1 \
            MINEKIN_DOMAIN_AUTONOMOUS_WAIT_SECONDS="${AUTONOMOUS_WAIT}")
        # Handed to the session by name, and only for this shape: a skill plan names its
        # own steps and the scripted hold/look run builds no mind at all, so a goal on
        # those two commands would be a knob nothing reads.
        goal_env=(
            MINEKIN_GOAL_PRODUCT="${GOAL_PRODUCT}"
            MINEKIN_GOAL_QUANTITY="${GOAL_QUANTITY}"
            MINEKIN_GOAL_SOURCE_ITEM="${GOAL_SOURCE_ITEM}"
            MINEKIN_GOAL_DIRECTION="${GOAL_DIRECTION}"
        )
        ;;
    *)
        session_args+=(
            --hold-forward-seconds "${WALK_SECONDS}"
            --look-yaw-degrees "${TURN_DEGREES}"
        )
        trunk_env=()
        ;;
esac
# Only the two shapes that run steps have a step to be patient about; the scripted
# hold/look run names its own seconds and a `--skill-step-seconds` ask there would
# be a knob for a number the run never reads.
if [ -n "${STEP_SECONDS}" ]; then
    case "${command}" in
        skills | autonomous)
            session_args+=(--skill-step-seconds "${STEP_SECONDS}")
            printf 'demo: each skill step is given %ss for the reading that will answer it\n' \
                "${STEP_SECONDS}"
            ;;
    esac
fi

env "${death_env[@]}" \
    "${trunk_env[@]}" \
    "${goal_env[@]}" \
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
if [ "${command}" = "skills" ]; then
    printf '                for the skill plan the verdict is in three fields: `skills` (the\n'
    printf '                skills that ran), `skill_stop` (where the sequence stopped and why),\n'
    printf '                and `skill_plan` (the steps this run was asked to carry)\n'
fi
if [ "${command}" = "autonomous" ]; then
    printf '                for the autonomous run the verdict is one field: `autonomous` — the goal\n'
    printf '                the mind held, each intent it formed on which reading, what the later\n'
    printf '                reading said about it, and the word in `stop_reason` that ended the run.\n'
    printf '                `steps` is the sequence, and it is the run'"'"'s own answer rather than\n'
    printf '                this script'"'"'s: nothing here knew it before the run started\n'
    printf '  per step      : the ledger carries one SkillStepRecorded row per step as it concluded,\n'
    printf '                so the panel can show the step that happened while the run was still\n'
    printf '                going. bash test-orchestrator/runner/demo.sh --browse reads them.\n'
fi
printf '  evidence      : bash test-orchestrator/runner/run.sh --shell "python -m minekin_core evidence verify <run_id>"\n'
printf '                  with MINEKIN_RUNNER_DATA=%s\n' "${VOLUME}"
printf '  dashboard     : bash test-orchestrator/runner/demo.sh --browse\n'
printf '                  one command: the read model, the wait for it, and the panel on\n'
printf '                  http://127.0.0.1:%s/?adapter=gateway&gateway=/gateway\n' "${PANEL_PORT}"
printf '                  Ctrl-C stops the panel and the read model with it; the Kin root on\n'
printf '                  volume %s keeps the run.\n' "${VOLUME}"
printf '                  To serve the two halves separately, use --gateway and then name that\n'
printf '                  port as the dev server'"'"'s proxy target.\n'
