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
#   domain.sh session start --auto-bundle /src/.../reviewed-tested-bundles.json --server-profile /src/.../server.json
#
# The auto-bundle form resolves its recipe during the run; the seal then names the
# recipe the run resolved to by reading it back from the run document, and a run
# whose document says nothing is reported unsealed rather than sealed against a
# guessed profile.
#
# Environment:
#   MINEKIN_USERNAME         the account to whitelist (default Kin)
#   MINEKIN_DOMAIN_SECONDS   how long the session may run (default 240)
set -euo pipefail

seconds="${MINEKIN_DOMAIN_SECONDS:-240}"
player="${MINEKIN_USERNAME:-minekin}"
summon="${MINEKIN_DOMAIN_SUMMON:-}"
# Where the summoned body goes, for a scene whose first step must already see it: at the
# world spawn it wanders for as long as the join takes and can end up outside the
# reading's view (measured: run `c50073f8…`'s `APPROACH_ENTITY_NOT_VISIBLE`), while this
# places it in the probed kin's look at the join. Default-off: unset adds nothing to the
# probe arguments.
summon_front="${MINEKIN_DOMAIN_SUMMON_FRONT:-}"
# Whether the controlled world keeps vanilla's own spawning. Default is vanilla's
# (on), which the measured join scans showed leaves a flat world that is not
# entity-empty; an entity probe that must be about the summoned body alone turns
# both switches off through this knob. Default-off: unset adds nothing.
no_ambient_spawns="${MINEKIN_DOMAIN_NO_AMBIENT_SPAWNS:-}"
# A `MINEKIN-DOMAIN-TIME-PHASE-001` schedule for the server's world clock: comma-separated
# `SECONDS:PHASE` entries, each a real `time set` this many seconds after the first join,
# so a bounded run can live several in-game days without spending an hour of wall clock.
# Default-off: unset, no `--time-phase` reaches the server tool and the world keeps the
# vanilla clock every earlier run had.
time_phase="${MINEKIN_DOMAIN_TIME_PHASE:-}"
# `MINEKIN-DOMAIN-CLEAR-HOSTILES-001`: kill every non-player entity once a player has
# joined, so a soak does not start on the standing population another soak left.
# Default-off: unset, no `--clear-hostiles` reaches the server tool and the world is
# carried over exactly as every earlier run left it.
clear_hostiles="${MINEKIN_DOMAIN_CLEAR_HOSTILES:-}"
probe="${MINEKIN_DOMAIN_PROBE:-}"
# The run's *second* probe target (V1201-LAN-SECOND-NAMED-PROBE-TARGET-001).
# Default-off: unset means the run asks one name, exactly what every run did
# before this knob existed. Set, it is taken up at the single probe
# construction below, where it is *appended* as a second `--probe-player` and
# never replaces the first — the first name is what the walk-and-turn judgement
# gates read. Two combinations the second name cannot carry are refused there,
# by name, before this run writes anything or starts anything.
probe_second="${MINEKIN_DOMAIN_PROBE_SECOND:-}"
kill="${MINEKIN_DOMAIN_KILL:-}"
# When, after its join, the world kills the player `MINEKIN_DOMAIN_KILL` names. Unset
# leaves the launcher's own six seconds, which is what every run before this knob used —
# and six seconds after a join is not always behind the walk: a run that holds the forward
# key for eight seconds dies in the middle of the hold, so the movement the authorised
# window was supposed to carry never happened and the only tail reading is a corpse's.
# Measured on the 2026-09-28 attempts: the ask with the default timing had nothing to
# kill, because the client it was aimed at had died in its own graphics initialisation.
kill_after_seconds="${MINEKIN_DOMAIN_KILL_AFTER_SECONDS:-}"
if [ -n "${kill_after_seconds}" ]; then
    case "${kill_after_seconds}" in
        *[!0-9]*)
            printf 'domain: MINEKIN_DOMAIN_KILL_AFTER_SECONDS must be a whole number of seconds, got %q\n' \
                "${kill_after_seconds}" >&2
            exit 2
            ;;
    esac
    if [ "${kill_after_seconds}" -le 0 ]; then
        printf 'domain: MINEKIN_DOMAIN_KILL_AFTER_SECONDS=%s asks for a death at or before the join; it has to be a positive number of seconds. Refused, never clamped.\n' \
            "${kill_after_seconds}" >&2
        exit 2
    fi
fi
# A death timing aimed at no death is a wrong ask, and it would read as a run that
# quietly did nothing rather than as a run that was told something impossible.
if [ -n "${kill_after_seconds}" ] && [ -z "${kill}" ]; then
    printf 'domain: MINEKIN_DOMAIN_KILL_AFTER_SECONDS=%s asks when to kill a player, but MINEKIN_DOMAIN_KILL names none -- there is no death for this timing to place. Refused here, before anything is written.\n' \
        "${kill_after_seconds}" >&2
    exit 2
fi
# And a death scheduled beyond the run's own ask ceiling never fires inside the run that
# asked for it, which would leave the release looking like it had no cause.
if [ -n "${kill_after_seconds}" ] && [ "${kill_after_seconds}" -ge "${seconds}" ]; then
    printf 'domain: MINEKIN_DOMAIN_KILL_AFTER_SECONDS=%s is at or beyond MINEKIN_DOMAIN_SECONDS=%s, the time this run may take; the death would fall outside the run. Refused, never clamped.\n' \
        "${kill_after_seconds}" "${seconds}" >&2
    exit 2
fi
kick="${MINEKIN_DOMAIN_KICK:-}"
silence="${MINEKIN_DOMAIN_SILENCE:-}"
look="${MINEKIN_DOMAIN_LOOK:-}"
kill_core="${MINEKIN_DOMAIN_KILL_CORE:-}"
# The world killed outright, while the Kin is in it. A different fault from a
# kick, which is the server *saying* goodbye: a killed server says nothing, and
# the client learns of it only because its socket stopped working.
kill_server="${MINEKIN_DOMAIN_KILL_SERVER:-}"
# The client killed rather than the runtime or the world. This is the boundary
# where the keys die with the process: the Bridge is a mod inside the client, so
# nothing in that JVM is left to release a key or to report a phase. What the run
# has to show is therefore a fact about the *runtime* noticing its own client is
# gone, and a fact about the world seeing the Kin leave.
kill_client="${MINEKIN_DOMAIN_KILL_CLIENT:-}"
no_server="${MINEKIN_DOMAIN_NO_SERVER:-}"
still="${MINEKIN_DOMAIN_STILL:-}"
# A bounded soak: how long the session is left running, and how often the two
# processes are sampled. Zero means no soak, which is what every run before this
# did — a soak is a thing a run asks for, not a thing every run pays for.
soak_seconds="${MINEKIN_DOMAIN_SOAK_SECONDS:-0}"
soak_interval="${MINEKIN_DOMAIN_SOAK_INTERVAL:-10}"
# How long to wait, after the session is playable, for the autonomous loop to write its
# own terminal `AutonomousRunHalted` before the harness stops the client. Zero — the
# default, and every run before this — keeps the old behaviour: the harness stops a few
# seconds after playable. A positive bound is what a `--autonomous` run asks for, because
# a mind that is still choosing has not finished, and stopping it mid-step SIGTERMs the
# client (exit 143) before the cooperative key release can be confirmed on a live channel.
autonomous_wait_seconds="${MINEKIN_DOMAIN_AUTONOMOUS_WAIT_SECONDS:-0}"
#: Where a soak's measurement and its request are written, named here rather than
#: inside the soak so the sealer can ask for them by the same names whether or not
#: this run soaked. Only a soak run leaves files here.
soak_file=/tmp/domain-soak.txt
soak_summary=/tmp/domain-soak.json
#: The joining client's JVM, when a run has one, is measured onto its own file. It is
#: not part of the judged baseline carrier above and is never sealed with it: a
#: two-client soak reported the host client and the world and said nothing about the
#: process that joined them, which left a whole JVM unwatched through the longest runs.
#: This is operator telemetry, so it adds no gate and no failing condition.
soak_joiner_file=/tmp/domain-soak-joiner.txt
case "${soak_seconds}" in
    ''|*[!0-9]*)
        printf 'domain: MINEKIN_DOMAIN_SOAK_SECONDS must be a non-negative integer, got %q\n' \
            "${soak_seconds}" >&2
        exit 2
        ;;
esac
case "${soak_interval}" in
    ''|*[!0-9]*|0)
        printf 'domain: MINEKIN_DOMAIN_SOAK_INTERVAL must be a positive integer, got %q\n' \
            "${soak_interval}" >&2
        exit 2
        ;;
esac
case "${autonomous_wait_seconds}" in
    ''|*[!0-9]*)
        printf 'domain: MINEKIN_DOMAIN_AUTONOMOUS_WAIT_SECONDS must be a non-negative integer, got %q\n' \
            "${autonomous_wait_seconds}" >&2
        exit 2
        ;;
esac
# The reviewed case this run is an execution of, if it is one. Naming it is what
# turns a run into evidence: the sealer attributes the bundle to a case
# definition and judges the case's assertions, and it does neither for a run
# nobody said was a case. Unset means nothing about this run changes.
case_id="${MINEKIN_DOMAIN_CASE:-}"
# A target that accepts a connection and never answers. The vanilla server cannot
# produce that — it answers — and nothing listening produces a refusal instead,
# which is a different path. This one exists to watch Core give up on its own
# deadline, and it is the only scenario where the client is expected to *hang*.
black_hole="${MINEKIN_DOMAIN_BLACK_HOLE:-}"
# A server that starts and then refuses the Kin: the whitelist stays empty, and
# `white-list=true` with `enforce-whitelist=true` does the rest. This is the one
# failure where the client gets all the way into the login handshake and the
# *server* is what says no.
not_whitelisted="${MINEKIN_DOMAIN_NOT_WHITELISTED:-}"
# A server that requires session verification while our client authenticates offline.
# The two disagree here on purpose: the tool derives the server's online-mode from
# the profile's auth_mode, so no other run can produce this, and the case exists to
# watch the refusal be classified as AUTH_MODE_MISMATCH rather than worked around.
online_mode="${MINEKIN_DOMAIN_ONLINE_MODE:-}"
# A server that requires a resource pack while the profile's policy is to refuse one.
# The pack is built and served by the harness itself, on loopback, and its sha1 goes
# into the server's settings — so the refusal is the client's policy meeting the
# server's requirement, and not a pack that could not be fetched.
resource_pack="${MINEKIN_DOMAIN_RESOURCE_PACK:-}"
# Ask the client to report this generation's first snapshot as not authoritative, so
# that Core's own boundary filter has a snapshot to refuse (`ADMIT-070`).
#
# The scenario cannot be produced any other way, and that is the measured fact this
# knob exists because of: across every run document the reviewed builds left behind,
# the field holding refusals was empty — the Bridge withholds a snapshot it cannot
# stand behind rather than sending a weaker one, so no real server, profile or timing
# makes a first snapshot arrive as `authoritative=false`.
#
# The refusal itself stays Core's decision. This harness only lends the client JVM a
# name; Core reads nothing out of its value, and unset means the run reports exactly
# what it reported before.
refuse_first_snapshot="${MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT:-}"
case "${refuse_first_snapshot}" in
    "" | 0 | false | 1 | true) : ;;
    *)
        printf 'domain: MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT must be 1/true or 0/false, got %q\n' \
            "${refuse_first_snapshot}" >&2
        exit 2
        ;;
esac
# Cast to a number, because a run explicitly told `0` and a run told nothing are
# the same request — and `[ -n ]` read them as two different ones. An operator who
# wrote `0` asked for the ordinary first snapshot; putting that run on the refusal
# path, waiting for a join that will not be refused and recording a request nobody
# made, would be the harness answering a question nobody asked.
refusal_asked=0
case "${refuse_first_snapshot}" in
    1 | true) refusal_asked=1 ;;
esac
# A block three in front of the Kin, and the server asked what state it is in. A
# use that changes nothing is a key held at nothing, so the scene puts something
# in front that can change and the reading is the server's own.
#
# It is a note block and not a lever, and three blocks out rather than two, for
# measured reasons given in full in the tool's own `use_target_command`: this run
# also measures a walk, a walk carries the look along itself, and what is wanted
# is a block the ray cannot miss at any distance — one the Kin walks into and
# stops against, which is also the walk-and-stop this harness waits for.
use_target="${MINEKIN_DOMAIN_USE_TARGET:-}"
# A breakable resource stacked in the Kin's look, for a world-skill run whose first
# step is `break_seen_block`. The controlled world is flat and fixed-seed, so it grows
# no trees and there is nothing for the Kin to see and break; this puts three oak logs
# there. `tools/run_controlled_server.py` writes them once, at the same moment the use
# target is owed, and the reasons it picks oak_log and three blocks out are given there.
# Default-off: unset adds nothing to the probe arguments, exactly what every run did
# before this knob existed.
resource_trunk="${MINEKIN_DOMAIN_RESOURCE_TRUNK:-}"
# A meal for the Kin and a reason to eat it, for a run whose world skill is `consume_item`.
# The consume precondition that matters here is the hunger bar itself — a full bar refuses
# the meal by name — and the flat controlled world drains no bar on any useful clock, so
# `tools/run_controlled_server.py` gives three apples and one short steep hunger effect at
# the join. Default-off: unset adds nothing to the probe arguments, exactly what every run
# did before this knob existed.
hungry_kin="${MINEKIN_DOMAIN_HUNGRY_KIN:-}"
# A weapon pair for the Kin, for a run whose world skill is `fight_back`. The flat
# controlled world hands out nothing, and the fight's named lever is *which* weapon the
# curated table brings to hand, so `tools/run_controlled_server.py` gives a wooden
# pickaxe and a stone axe at the join — deliberately unequal, so the reading can say the
# bigger number won rather than the only stack there was. Default-off: unset adds
# nothing to the probe arguments, exactly what every run did before this knob existed.
armed_kin="${MINEKIN_DOMAIN_ARMED_KIN:-}"
# A session that is meant to *host*: the client is put in a world it owns and asked to
# publish it to LAN. The port is named rather than chosen by the client, because the
# point of publishing is that something else can be pointed at it — and a client that
# chooses its own port reports it only in a run document that is printed at the end.
open_lan="${MINEKIN_DOMAIN_OPEN_LAN:-}"
lan_port="${MINEKIN_DOMAIN_LAN_PORT:-25570}"
# A second managed client that joins the world the first one published. It is a second
# *Kin* and not a second session of the same one, because the identity is the username:
# the same Kin arriving twice is a duplicate login the server kicks.
#
# The port has to be named for this to mean anything: the joining client is configured
# by a server profile whose port is a literal, and a port the hosting client chose for
# itself is only reported in a run document printed when that run has ended.
joiner="${MINEKIN_DOMAIN_JOIN:-}"
join_username="${MINEKIN_DOMAIN_JOIN_USERNAME:-Kin2}"
# Whether this run prints the joining client's command line and stops instead of
# starting it. The readback has to be read here, where the other joiner names are,
# because it is answered below the point the ask is composed and bounded — a print
# of an unvalidated ask would be a claim about a line the run might never start.
# `0` and unset both mean "run the run".
join_control_print="${MINEKIN_DOMAIN_JOIN_CONTROL_PRINT:-}"
# Which world a second client is sent into when this run *also* started a controlled
# dedicated server. Unset means every shape this file had before: a joiner still needs
# `MINEKIN_DOMAIN_OPEN_LAN`, and a `--server-profile` run still starts no second client
# at all (its wait chain waits for its own host Kin and nothing else). Set, it opens the
# one route V1201-LAN-JOINER-ON-CONTROLLED-SERVER-001 exists for — the joining client
# dials the world this run's own `run_controlled_server.py` started, so the server that
# answers `data get entity` probes is the server both clients stand in, and its log is
# the readout that can say the *joining* Kin turned or walked. It is default-off, it is
# refused by name for every combination that cannot hold exactly one world for two
# clients, and it names no address or port of its own: the endpoint is read out of this
# run's `server.properties` below. `0` and unset are the same request, cast here once so
# no branch downstream has to guess (the `refuse_first_snapshot` above set that pattern).
join_on_controlled_server="${MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER:-}"
join_on_controlled_server_asked=0
case "${join_on_controlled_server}" in
    "" | 0 | false) : ;;
    1 | true) join_on_controlled_server_asked=1 ;;
    *)
        printf 'domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER must be 1/true or 0/false, got %q\n' \
            "${join_on_controlled_server}" >&2
        exit 2
        ;;
esac
# Which of the two runs a joining run's case is about. The harness seals one run per
# bundle, and a run with a second client in it has two: the hosting session (whose
# document is what every other case is judged on) and the joining one. Named rather
# than guessed from the case id, because a case id is not a switch and a second
# spelling of one would be a silent wrong answer.
case_on="${MINEKIN_DOMAIN_CASE_ON:-host}"
case "${case_on}" in
    host|joiner) : ;;
    *)
        printf 'domain: MINEKIN_DOMAIN_CASE_ON must be host or joiner, got %q\n' "${case_on}" >&2
        exit 2
        ;;
esac
# The two seals this card hands over, each with its own switch and each default-off.
# They are deliberately *not* one knob: (a) and (b) of the card's counterexamples read
# the server-log carrier's presence, and a single switch that also moved the probe names
# would let the two hide each other's answer. Both are cast to a counted question the
# way `join_on_controlled_server_asked` above is — `0`, `false` and unset are the same
# request, and anything else is refused here rather than carried.
#
#   * MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG hands this run's own dedicated-server
#     profile and `--server-directory` back to the joining side's seal, so a bundle
#     sealed on the joiner names the world it actually stood in and can carry the
#     server's log at all. The profile names the very server *this* run started, so it
#     is not the "different kind of world" a directory-only carve-out guarded against:
#     with it the seal records `kind: dedicated`, the seed read from the directory names
#     it, and the two agree; the host run document is then dropped, because a profile and
#     a host document are two mutually exclusive sources for the one world block, and the
#     guard at the joiner branch below refuses that pairing. The jar is still not handed
#     over — this branch mounts none.
#   * MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS hands the names this run actually asked the
#     server about to the same seal as `--probed-player`, one per name.
seal_joiner_server_log="${MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG:-}"
seal_joiner_server_log_asked=0
case "${seal_joiner_server_log}" in
    "" | 0 | false) : ;;
    1 | true) seal_joiner_server_log_asked=1 ;;
    *)
        printf 'domain: MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG must be 1/true or 0/false, got %q\n' \
            "${seal_joiner_server_log}" >&2
        exit 2
        ;;
esac
seal_probed_players="${MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS:-}"
seal_probed_players_asked=0
case "${seal_probed_players}" in
    "" | 0 | false) : ;;
    1 | true) seal_probed_players_asked=1 ;;
    *)
        printf 'domain: MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS must be 1/true or 0/false, got %q\n' \
            "${seal_probed_players}" >&2
        exit 2
        ;;
esac
# How often the server is asked about the Kin. A look is over within a second
# of the join, so a run that wants a reading on both sides of it asks more
# often than the old default — the pair is what shows a heading changed.
#
# The cadence is a default of one now because the movement judgement reads the
# authorisation window rather than the whole log: it compares the last reading
# before the lease was granted against the last reading inside it, and that
# window is two seconds. At five seconds a window can hold no reading at all,
# and a run that moved is judged as one that did not; at four seconds it holds
# one, which is the start of the window wearing the endpoint's name. Asking
# every second puts at least two readings inside any two-second window
# whatever the phase, so the endpoint is a reading taken after the walk.
# Neither the distance threshold nor the window moved to meet the sampling.
probe_seconds="${MINEKIN_DOMAIN_PROBE_SECONDS:-1}"
silenced=0
#: Set when the harness itself failed to do what the run asked for — a fault
#: that was not injected, or a seal that did not happen. A run that did not do
#: what it says it does must not exit like one that did.
injection_failed=0
runs=/data/server-runs

# The reviewed case, as a file, named once here rather than at the point of
# sealing: the fault helper cross-checks the case it is told about against this
# file, so the two have to be the same file.
case_file=""
if [ -n "${case_id}" ]; then
    case_file="/src/tests/fixtures/cases/$(printf '%s' "${case_id}" | tr '[:upper:]' '[:lower:]').json"
fi

# The record of the fault this run injected. One run seals one record, so a run
# that asks for two faults at once is refused rather than allowed to report one
# of them: there would be no way to say later which of the two the record is.
fault_path=/tmp/domain-fault-injection.json
fault_role=""
# Counted rather than compared two at a time, because there are three boundaries
# now and a pairwise guard would let the third one pair up with neither.
faults=0
for requested in "${kill_core}" "${kill_server}" "${kill_client}"; do
    if [ -n "${requested}" ]; then
        faults=$((faults + 1))
    fi
done
if [ "${faults}" -gt 1 ]; then
    printf 'domain: this run asks for two faults at once; one run seals one record\n' >&2
    exit 2
fi
# The same rule covers the report request, because it travels through the same
# artifact: a run that both killed a process and asked the client to report a
# weaker snapshot would seal one of the two, and there is no way to say afterwards
# which. Refused here, while the run can still be told apart from its result.
request_path=/tmp/domain-injection-request.json
if [ "${refusal_asked}" -eq 1 ] && [ "${faults}" -ge 1 ]; then
    printf 'domain: this run asks for a refused snapshot and a killed process; one run seals one record\n' >&2
    exit 2
fi

# Capture a process identity when this runner still owns the pid it just
# started.  Passing only the pid later would let a dead wrapper's reused number
# become the trust root for an unrelated /proc subtree.
read_process_identity() {
    python - "$1" <<'PY'
import os
import sys
from pathlib import Path

pid = int(sys.argv[1])
raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="strict")
closing = raw.rfind(")")
if closing < 0:
    raise SystemExit(2)
fields = raw[closing + 2 :].split()
if len(fields) < 20:
    raise SystemExit(2)
print(fields[19], os.readlink(f"/proc/{pid}/ns/pid"))
PY
}

# Kill this run's own process, and keep the record that says so.
#
# The target is named, not searched for. Every way this used to be done here
# guessed: `pkill -f "minekin_core session start"` matched any Core in the
# container — including the `session stop` this script runs later — and
# `pgrep -P <tool> | head -1` assumed the tool's first child was the JVM. Neither
# could say which process it had killed, so neither could be evidence. The helper
# is given a pid this run already holds and refuses unless exactly one of that
# process's descendants is the role's own command line; it re-reads the identity
# before signalling, and it watches for that identity to leave /proc afterwards.
#
# Anything other than a confirmed kill fails the run. `set +e` around the call
# because the helper's own exit status is a result to read, not a crash to die on.
inject_fault() {
    local root_pid="$1"
    local role="$2"
    local root_starttime_ticks="$3"
    local root_pid_namespace_inode="$4"
    set +e
    python /src/tools/inject_fault.py inject \
        --root-pid "${root_pid}" \
        --root-starttime-ticks "${root_starttime_ticks}" \
        --root-pid-namespace-inode "${root_pid_namespace_inode}" \
        --role "${role}" \
        --case "${case_id}" \
        --case-file "${case_file}" \
        --ledger "${ledger}" \
        --kin-id "${kin_id}" \
        --run-id "${run_id}" \
        --session-id "${session_id}" \
        --generation "${generation}" \
        --record "${fault_path}" >/tmp/domain-fault-injection.log 2>&1
    local helper_status=$?
    set -e
    printf 'domain: the fault helper said ' >&2
    tr -d '\n' </tmp/domain-fault-injection.log >&2 || true
    printf '\n' >&2
    if [ "${helper_status}" -ne 0 ] || [ ! -s "${fault_path}" ]; then
        printf 'domain: the fault could not be recorded, so nothing here can be attributed\n' >&2
        return 1
    fi
    local outcome
    outcome=$(python -c 'import json,sys;print(json.load(open(sys.argv[1]))["outcome"])' \
        "${fault_path}" 2>/dev/null || true)
    if [ "${outcome}" != "INJECTED" ]; then
        printf 'domain: the fault was not injected (%s): ' "${outcome:-unreadable}" >&2
        python -c 'import json,sys;print(",".join(json.load(open(sys.argv[1]))["reasons"]))' \
            "${fault_path}" >&2 2>/dev/null || true
        printf '\n' >&2
        return 1
    fi
    fault_role="${role}"
    return 0
}

# Record that this run asked the client to report a weaker first snapshot, and
# whether the live client JVM actually carries that name.
#
# This is not `inject_fault` with a different role, and keeping it separate is the
# point: nothing here ends a process, so there is no signal, no disappearance and
# no supervisor exit status to attest. Filing the request as a kill record would be
# the harness claiming a strength it did not observe. What it *can* attest is the
# request itself and its effect, read from `/proc/<client JVM>/environ` — a fact
# about a process, not about a line in a log — which is why the call has to happen
# while the client is alive.
record_refusal_request() {
    local root_pid="$1"
    local root_starttime_ticks="$2"
    local root_pid_namespace_inode="$3"
    set +e
    python /src/tools/inject_fault.py request \
        --root-pid "${root_pid}" \
        --root-starttime-ticks "${root_starttime_ticks}" \
        --root-pid-namespace-inode "${root_pid_namespace_inode}" \
        --subject BRIDGE_FIRST_SNAPSHOT_AUTHORITY \
        --value "${refuse_first_snapshot}" \
        --case "${case_id}" \
        --case-file "${case_file}" \
        --ledger "${ledger}" \
        --kin-id "${kin_id}" \
        --run-id "${run_id}" \
        --session-id "${session_id}" \
        --generation "${generation}" \
        --record "${request_path}" >/tmp/domain-injection-request.log 2>&1
    local helper_status=$?
    set -e
    printf 'domain: the report request helper said ' >&2
    tr -d '\n' </tmp/domain-injection-request.log >&2 || true
    printf '\n' >&2
    if [ "${helper_status}" -ne 0 ] || [ ! -s "${request_path}" ]; then
        printf 'domain: the injection could not be recorded, so nothing here can be attributed\n' >&2
        return 1
    fi
    local observed
    observed=$(python -c 'import json,sys;print(json.load(open(sys.argv[1]))["effect"]["observed"])' \
        "${request_path}" 2>/dev/null || true)
    if [ "${observed}" != "True" ]; then
        printf 'domain: the name did not reach the client JVM (%s): ' "${observed:-unreadable}" >&2
        python -c 'import json,sys;print(",".join(json.load(open(sys.argv[1]))["reasons"]))' \
            "${request_path}" >&2 2>/dev/null || true
        printf '\n' >&2
        return 1
    fi
    # Read back through the reader the sealer itself uses, not merely parsed. A
    # record this harness could write but that channel could not read would be
    # evidence nobody can judge, and the run would only find that out when the
    # bundle was already sealed.
    if ! python - "${request_path}" <<'PY' >&2
import json
import sys
from pathlib import Path

sys.path.insert(0, "/src/tools")

import fault_injection

document = fault_injection.read_record(Path(sys.argv[1])).document
print("domain: the sealing channel reads this record back as")
print(
    json.dumps(
        {key: document[key] for key in ("category", "request", "effect", "attribution")},
        sort_keys=True,
    )
)
PY
    then
        printf 'domain: the injection record could not be read back as a record\n' >&2
        return 1
    fi
    return 0
}

# What this run was asked to do, read from the command that was given to it: the
# harness waits for what the session was told to do, not for what the operator
# happened to export as well. The two profiles come out the same way, because
# sealing needs to name the documents this run was actually given rather than
# the ones this script would have chosen.
hold_requested=0
# The phase the run asks at, read from its own arguments rather than from another
# switch: a run that asks at the join is *refused* (the world is not playable
# yet), so there is no walk to wait for and a harness that waited for one would
# spend its whole budget on a hold that was correctly never granted.
hold_at="playable"
profile=""
auto_bundle=""
server_profile=""
connection_timeout=""
previous=""
for argument in "$@"; do
    case "${argument}" in
        --hold-forward-seconds) hold_requested=1 ;;
    esac
    case "${previous}" in
        --profile) profile="${argument}" ;;
        --auto-bundle) auto_bundle="${argument}" ;;
        --server-profile) server_profile="${argument}" ;;
        --connection-timeout-seconds) connection_timeout="${argument}" ;;
        --hold-at) hold_at="${argument}" ;;
    esac
    previous="${argument}"
done

# The two bundle sources are mutually exclusive in the product's own parser, and
# this scan keeps that rule rather than inventing a second one: a run naming both
# would leave everything below choosing between two documents the session was
# never given. Said by name, because the scan that first missed `--auto-bundle`
# missed it silently — an empty profile carried all the way to the sealer.
if [[ -n "${profile}" && -n "${auto_bundle}" ]]; then
    printf 'domain: this run names both --profile and --auto-bundle; the session admits exactly one bundle source\n' >&2
    exit 2
fi
# The auto path is a single-session scenario: the joining second client below is
# started from a named bundle profile, and no auto resolution has been reviewed
# for it. Refused here by name rather than reaching the joiner block with the
# empty profile this scan carries for an auto run.
if [[ -n "${auto_bundle}" && -n "${joiner}" ]]; then
    printf 'domain: an auto-bundle run cannot also ask for a joining second client; the joiner is started from a named bundle profile\n' >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Asking for the *controlled dedicated server* as the joining client's world
# (V1201-LAN-JOINER-ON-CONTROLLED-SERVER-001).
#
# The name is read and cast near the top of this file, beside the other joiner names;
# what this block adds is only the refusal set, and it is placed at the first point
# where the run's own arguments have been scanned (`--server-profile` above) and before
# anything exists to be torn down: no server directory is made, no Kin created, no JVM
# started.
#
# Why refusals rather than a quietly-ignored request: the name selects a *destination*.
# Half the combinations that could be asked for have no single world for the second
# client, and a harness that accepted one of them would produce a run whose recorded
# target is a place nobody dialled — the same class of fault the version-at-the-joiner
# and baseline-per-Kin fixes above exist to kill. Each line below therefore says which
# combination it refuses and names the knob that asked.
#
# What this block does not do: it adds no product surface, no address an operator
# supplied, and no new allowance. `--allow-player` keeps its meaning (one name of a
# player this run starts itself), the whitelist and its enforcement are untouched, and
# the joining client's endpoint is read from this run's own server settings further
# down rather than written here.
# ---------------------------------------------------------------------------
# --- joiner-controlled-server-guard begin (the contract test extracts this region) ---
if [ "${join_on_controlled_server_asked}" -eq 1 ]; then
    if [ -z "${joiner}" ]; then
        printf 'domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER names where a joining client goes and this run has none (MINEKIN_DOMAIN_JOIN is unset); refused rather than carried as a knob that does nothing\n' >&2
        exit 2
    fi
    if [ -z "${server_profile}" ]; then
        printf 'domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER sends the joining client into the controlled dedicated server this run starts, and this run starts none (--server-profile is absent)\n' >&2
        exit 2
    fi
    if [ -n "${open_lan}" ]; then
        printf 'domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER and MINEKIN_DOMAIN_OPEN_LAN name two worlds for one joining client; this run has to pick the one it sends it into\n' >&2
        exit 2
    fi
    if [ -n "${black_hole}" ]; then
        printf 'domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER needs a world that answers, and this run puts a listener that never speaks on the port instead\n' >&2
        exit 2
    fi
    if [ -n "${no_server}" ]; then
        printf 'domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER needs this run to keep its server up and MINEKIN_DOMAIN_NO_SERVER stops it before any client starts\n' >&2
        exit 2
    fi
    if [ -n "${not_whitelisted}" ]; then
        printf 'domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER sends a second Kin into the dedicated world this run started and MINEKIN_DOMAIN_NOT_WHITELISTED empties the whitelist that world enforces; the two ask for opposite runs\n' >&2
        exit 2
    fi
    if [ "${refusal_asked}" -eq 1 ]; then
        printf 'domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER and MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT name two destinations for one wait; the chain answers the snapshot refusal before any joining client is sent, so the prepared joiner would never go -- refused rather than carried as a knob that does nothing\n' >&2
        exit 2
    fi
fi
# --- joiner-controlled-server-guard end ---

# ---------------------------------------------------------------------------
# The joiner's server-log carrier (V1201-PROBE-TARGET-HANDOVER-001, cell 1).
# --- joiner-server-log-seal-guard begin (the contract test extracts this region) ---
# Asked, and refused here rather than at the seal, because the seal is the last thing
# this run does: by then the world has been started, both clients have been through it,
# and a knob that cannot be honoured would have cost the whole run to say so. Each
# refusal below names the shape the carrier needs and the fact about this run that is
# missing from it.
if [ "${seal_joiner_server_log_asked}" -eq 1 ]; then
    if [ "${case_on}" != "joiner" ]; then
        printf 'domain: MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG hands the server log back to a case sealed on the joining run and this run seals its case on the host (MINEKIN_DOMAIN_CASE_ON is %q); the hosting branch already carries this directory, so the switch would do nothing here\n' \
            "${case_on}" >&2
        exit 2
    fi
    if [ -z "${server_profile}" ]; then
        printf 'domain: MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG names the log of the dedicated server this run starts, and this run starts none (--server-profile is absent); the world this joiner would be sealed into is somebody else'"'"'s, and naming a directory of this run for it would record a world that never ran\n' >&2
        exit 2
    fi
    if [ -n "${black_hole}" ]; then
        printf 'domain: MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG names a run directory holding a server log and this run answers its own profile with a silent listener instead; no such directory is ever created, so there is nothing to hand over\n' >&2
        exit 2
    fi
fi
# --- joiner-server-log-seal-guard end ---

# ---------------------------------------------------------------------------
# Asking the *joining* client to look and move
# (V1201-LAN-JOINER-BOUNDED-CONTROL-DRIVER-001).
#
# Every input ask this harness has carried so far belonged to the hosting
# session: the `--hold-*` and `--look-*` flags a run passes on its own command
# line drive the Kin that opened the world, and `MINEKIN_DOMAIN_LOOK` above is
# that host-side reading knob — it names the turn the *host* is checked for and
# has nothing to do with a second client. The joining client has been started
# observe-only since H1b: V4 measured it reaching `JOIN` and `PLAYABLE`, and
# nothing on its line ever asked it to turn or walk. That is why the 1.20.1
# second-client control evidence is zero rather than thin — not a measurement
# that came back negative, but an ask that has never existed.
#
# What this block adds is the ask, and only the ask: three default-off names
# that can hand the joining client at most one look (yaw and/or pitch) and one
# forward hold of at most two seconds, whose release is the lease lapsing. The
# bounds are enforced *here*, in the runner, before a JVM starts: an
# out-of-range value is refused by name — the message says which knob and which
# bound — and is never clamped into a smaller ask and never passed through. A
# driver that quietly narrowed an operator's request would produce a run whose
# recorded ask is not the ask anyone made, which is the same class of fault the
# version-at-the-joiner and baseline-per-Kin fixes above exist to kill.
#
# Three things it deliberately does not do.
#
# * It never reaches the hosting session's command line. The array composed
#   below is spliced into exactly one place: the `session start` line the joining
#   client is backgrounded with.
# * It never reaches an auto-bundle run, and that is structural rather than
#   policed: the refusal above this block is controller-reserved, untouched, and
#   fires first. The contract test pins the order by index; no branch here
#   pretends to catch a case that block has already stopped.
# * It adds no product surface. `session start` already takes
#   `--look-yaw-degrees`, `--look-pitch-degrees` and `--hold-forward-seconds`
#   (the last of those documented as needing `--server-profile`, which this line
#   already carries), and the lease it drives is already the joining Kin's own
#   because the launch line sets `MINEKIN_KIN_ID="${joiner}"`. Nothing about
#   admission, addressing, authentication or the bridge moves either: this is a
#   shorter hold and a smaller turn than a host run is already allowed to take,
#   aimed at a client that was already let in.
#
# What this block does *not* claim: that a real second client has honoured any
# of it. The numbers below are this driver's construction — the widest ask the
# card reviews — and the only thing measured here is the shape of the
# composition and the fact of a refusal. The live readout (a joining client
# actually turning and walking on a published 1.20.1 world) is the follow-on
# card's, and until it runs this stays unverified.
# ---------------------------------------------------------------------------
# --- joiner-control-driver begin (the contract test extracts this region) ---
# The bounds, in one place. A 45-degree yaw is well past what the server's
# `Rotation` reading needs to show a heading that changed; 30 degrees of pitch
# keeps the tilt inside the range vanilla reports without inverting the view;
# two seconds is the longest hold whose *end* this harness can still tell apart
# from a session that stopped, because its walk wait needs two settled readings
# after the release. Chosen, not measured — see the paragraph above.
joiner_control_max_yaw=45
joiner_control_max_pitch=30
joiner_control_max_forward_seconds=2

# A value this driver can compare at all: an optional sign in front of a decimal.
# Anything else — an empty string, a word, a list, `1.2.3` — is refused before it
# reaches an arithmetic comparison that would read it as something it is not.
joiner_control_is_number() {
    if [[ "$1" =~ ^-?([0-9]+(\.[0-9]+)?|\.[0-9]+)$ ]]; then
        return 0
    fi
    return 1
}

# Is the magnitude within the bound? Through awk, the way the host-side turn
# comparison already does it: bash has no decimal operator.
joiner_control_within() {
    awk -v value="$1" -v bound="$2" \
        'BEGIN { v = value + 0; if (v < 0) v = -v; exit !(v <= bound) }'
}

# Away from zero, in either direction. A look of no degrees is a request to do
# nothing dressed as a request — and a look *is* signed on purpose
# (`--look-yaw-degrees` positive is right, `--look-pitch-degrees` positive is
# up), so the sign is kept and only the nothing-asked case is refused.
joiner_control_is_nonzero() {
    awk -v value="$1" 'BEGIN { exit !(value + 0 != 0) }'
}

# Strictly above nothing, for the one ask that has no negative shape: a hold of
# zero or fewer seconds is a lease deadline already past. The product refuses both
# of these too, but only after a client has been started for them.
joiner_control_is_positive() {
    awk -v value="$1" 'BEGIN { exit !(value + 0 > 0) }'
}

# The whole ask, validated and composed. Sets `joiner_control_args`, which is
# empty when nothing was asked for — and an empty array spliced into the joining
# client's line leaves that line exactly the words it carried before this driver
# existed.
compose_joiner_control_args() {
    joiner_control_args=()
    local yaw="${MINEKIN_DOMAIN_JOIN_LOOK_YAW:-}"
    local pitch="${MINEKIN_DOMAIN_JOIN_LOOK_PITCH:-}"
    local forward="${MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS:-}"
    if [ -z "${yaw}" ] && [ -z "${pitch}" ] && [ -z "${forward}" ]; then
        return 0
    fi
    # Which names armed the driver, so the two structural refusals below can name
    # what they are refusing rather than only what is missing.
    local asked=""
    if [ -n "${yaw}" ]; then
        asked="MINEKIN_DOMAIN_JOIN_LOOK_YAW"
    fi
    if [ -n "${pitch}" ]; then
        asked="${asked:+${asked}, }MINEKIN_DOMAIN_JOIN_LOOK_PITCH"
    fi
    if [ -n "${forward}" ]; then
        asked="${asked:+${asked}, }MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS"
    fi
    # Joiner-only, and said by name. An ask with no joining client would
    # otherwise sit on this run's line doing nothing at all — the host session
    # takes its own input from its own arguments, not from these names — and a
    # knob that silently does nothing is the failure this file's first test
    # exists to catch.
    if [ -z "${joiner}" ]; then
        printf 'domain: the ask (%s) needs a joining client to drive and this run has none (MINEKIN_DOMAIN_JOIN is unset); refused rather than carried as a knob that does nothing\n' \
            "${asked}" >&2
        exit 2
    fi
    # The phase a hold is asked at is read from this run's own arguments above.
    # `join` is a refusal in the product by design — no lease before the world is
    # real — so a joining run asking at the join has nothing to drive, and this
    # driver refuses the combination instead of composing a line it knows is
    # answered `no`. The host-side scan that skips its walk wait for this phase
    # is untouched; that one waits, this one does not get asked.
    if [ "${hold_at}" = "join" ]; then
        printf 'domain: the ask (%s) needs a playable moment for the joining client, and this run asks for its hold at the join (--hold-at join); there is none to drive it from, so the ask is refused\n' \
            "${asked}" >&2
        exit 2
    fi
    if [ -n "${yaw}" ]; then
        if ! joiner_control_is_number "${yaw}" ||
            ! joiner_control_is_nonzero "${yaw}" ||
            ! joiner_control_within "${yaw}" "${joiner_control_max_yaw}"; then
            printf 'domain: MINEKIN_DOMAIN_JOIN_LOOK_YAW=%s is outside the bound this driver carries for it: one look of at most %s degrees in either direction, and never zero. Refused, never clamped.\n' \
                "${yaw}" "${joiner_control_max_yaw}" >&2
            exit 2
        fi
    fi
    if [ -n "${pitch}" ]; then
        if ! joiner_control_is_number "${pitch}" ||
            ! joiner_control_is_nonzero "${pitch}" ||
            ! joiner_control_within "${pitch}" "${joiner_control_max_pitch}"; then
            printf 'domain: MINEKIN_DOMAIN_JOIN_LOOK_PITCH=%s is outside the bound this driver carries for it: one look of at most %s degrees in either direction, and never zero. Refused, never clamped.\n' \
                "${pitch}" "${joiner_control_max_pitch}" >&2
            exit 2
        fi
    fi
    if [ -n "${forward}" ]; then
        if ! joiner_control_is_number "${forward}" ||
            ! joiner_control_is_positive "${forward}" ||
            ! joiner_control_within "${forward}" "${joiner_control_max_forward_seconds}"; then
            printf 'domain: MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS=%s is outside the bound this driver carries for it: one forward hold of more than 0 and at most %s seconds. Refused, never clamped.\n' \
                "${forward}" "${joiner_control_max_forward_seconds}" >&2
            exit 2
        fi
    fi
    # The whole width of what this driver may hand over, and nothing besides it:
    # no `--hold-strafe`, no `--hold-jump`, no `--hold-sneak`, no
    # `--hold-use-seconds`, no `--hold-at`. The release is not a flag either — it
    # is what the product does when the hold's lease lapses, which is why the
    # bound on the hold's length is the bound on the release.
    if [ -n "${yaw}" ]; then
        joiner_control_args+=(--look-yaw-degrees "${yaw}")
    fi
    if [ -n "${pitch}" ]; then
        joiner_control_args+=(--look-pitch-degrees "${pitch}")
    fi
    if [ -n "${forward}" ]; then
        joiner_control_args+=(--hold-forward-seconds "${forward}")
    fi
}

# The joining client's product call, in one array: the fixed words it has always
# carried, then the bounded ask composed just above, in the order the client
# receives them. `join_the_published_world` starts the client from this array and
# the readback below prints it, so the two cannot become two claims about one
# line — which is the drift the joiner-environment contract test already guards
# by counting the literal `session start` command exactly once in this file.
build_joiner_session_argv() {
    joiner_session_argv=(
        python -m minekin_core session start
        --profile "${profile}"
        --server-profile /tmp/domain-join-profile.json
        "${joiner_control_args[@]}"
    )
}
# --- joiner-control-driver end ---

# Composed once, and before the server, the host client or the joining client
# exists: an ask outside a bound has to cost a run nothing but its own exit.
joiner_control_args=()
compose_joiner_control_args
joiner_session_argv=()
build_joiner_session_argv

# The readback an operator or a check can ask for with no world to join and no JVM
# to start. It prints the words and stops, which is the only honest thing a
# pre-launch readout can do: it says what *would* be handed over and never that it
# was. `0` and an empty value mean "not asked", so a delivered-but-empty name does
# not turn a normal run into a printout.
if [ -n "${join_control_print}" ] && [ "${join_control_print}" != "0" ]; then
    # A printout is a claim about the joining client's line, so it needs a joining
    # client: a run with none would otherwise be handed words it would never start
    # and a header that says it would.
    if [ -z "${joiner}" ]; then
        printf 'domain: a joiner-control printout describes a joining client and this run has none (MINEKIN_DOMAIN_JOIN is unset)\n' >&2
        exit 2
    fi
    if [ -z "${profile}" ]; then
        printf 'domain: a joiner-control printout names the bundle profile this run was given, and this run gave none\n' >&2
        exit 2
    fi
    printf 'domain: the joining client of this run would be started with:\n' >&2
    printf '%s\n' "${joiner_session_argv[@]}" | sed 's/^/domain:   /' >&2
    printf 'domain: a printout launches nothing; this run stops here\n' >&2
    exit 0
fi
# --- joiner-control wiring end ---

# The server a run starts has to be the server the client it launches may join, so
# the recipe is read from the bundle profile rather than named by the operator: a
# second switch here would be a switch that can be set to the wrong version, and
# the misjoin it produced would be the thing the run then reported as evidence.
launched_version=""
if [[ -n "${profile}" ]]; then
    launched_version="$(
        python -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))["minecraft"]["version"])' \
            "${profile}" 2>/dev/null
    )" || launched_version=""
elif [[ -n "${auto_bundle}" && -n "${server_profile}" ]]; then
    # An auto-bundle run hands this scan no bundle profile: the recipe is resolved
    # during the run, and only the run document says which one. The server still
    # has to start before the client, and the one document this run itself names
    # that carries a version is the Server Profile it joins, so the version is
    # read from there — the single allowed version of a schema 2 profile, or the
    # pinned one of a schema 0/1 profile. An allow-list of several is refused by
    # name rather than started at an arbitrary entry: starting the wrong server is
    # the misjoin this whole block exists to prevent. A black hole names a port
    # but starts no server, so nothing is decided here for it.
    launched_version="$(
        python - "${server_profile}" <<'PY' 2>/dev/null || true
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        document = json.loads(handle.read())
except (OSError, ValueError):
    raise SystemExit(0)
if not isinstance(document, dict):
    raise SystemExit(0)
policy = document.get("version_policy")
allowed = policy.get("allowed_versions") if isinstance(policy, dict) else None
if isinstance(allowed, list) and allowed:
    if len(allowed) == 1 and isinstance(allowed[0], str):
        print(allowed[0])
elif isinstance(document.get("minecraft_version"), str):
    print(document["minecraft_version"])
PY
    )"
    if [[ -z "${launched_version}" && -z "${black_hole}" ]]; then
        printf 'domain: an auto-bundle run has to start the server its Server Profile allows, and %s names no single version to start\n' \
            "${server_profile}" >&2
        exit 2
    fi
fi
version_args=()
if [[ -n "${launched_version}" ]]; then
    version_args=(--version "${launched_version}")
fi


# Empty means "the world is as vanilla generated it", which is what every run
# did before this existed — so it stays optional rather than becoming a required
# argument with an empty value.
summon_args=()
if [[ -n "${summon}" ]]; then
    summon_args=(--summon "${summon}")
fi
# --- summon-front-forge begin (the contract test extracts this region) ---
if [[ -n "${summon_front}" ]]; then
    summon_args+=(--summon-front)
fi
# --- summon-front-forge end ---

# A run that is supposed to move the Kin has to be able to ask the server where
# the Kin is: the server does not log where anyone walks, and the acceptance for
# input is the server's own observation of the displacement.
#
# The asking is a default now: every server run carries `data get entity <Kin> Pos`
# and `Rotation` on this cadence into the server's log, so a reading a scenario
# might want is already there rather than only present in runs that knew in advance
# to name the probe. What `MINEKIN_DOMAIN_PROBE` still gates is everything below
# that *judges* — the walk and turn waits read it before they wait — so the default
# adds readings, not verdicts, and the judgement set is exactly what it was. The
# default name is the account this run whitelists, which is the Kin those scenarios
# put in the world.
# --- second-probe-guard begin (the contract test extracts this region) ---
# Two asks the second name cannot answer, said here rather than downstream. This
# point is before the server's run directory is numbered, before the server JVM,
# and before any document this run could write, so a refusal leaves nothing behind.
# `tools/run_controlled_server.py` refuses both shapes as well, and that is only
# the backstop: a harness that carried a contradictory ask to the tool has already
# failed to answer it where the ask was made.
#
#   * the second name is the first name: asking one entity twice is not a reading
#     of two, and the second name exists precisely to ask another than the first;
#   * `MINEKIN_DOMAIN_USE_TARGET` places one block in one probed kin's look, and
#     two probed names do not say whose look the block is for.
if [[ -n "${probe_second}" ]]; then
    if [[ "${probe_second}" == "${probe:-${player}}" ]]; then
        printf 'domain: MINEKIN_DOMAIN_PROBE_SECOND names %s, and that is the name this run already asks as its first probe target (MINEKIN_DOMAIN_PROBE, or the whitelisted account when it is unset); one run asking the same name twice is not a reading of two kins -- refused here, before anything is written\n' \
            "${probe:-${player}}" >&2
        exit 2
    fi
    if [[ -n "${use_target}" ]]; then
        printf 'domain: MINEKIN_DOMAIN_USE_TARGET places one block in the look of one probed kin and MINEKIN_DOMAIN_PROBE_SECOND adds a second probed name (%s); the pair does not say whose look the block is placed in -- refused here, before anything is written\n' \
            "${probe_second}" >&2
        exit 2
    fi
fi
# --- second-probe-guard end ---
#
# The trunk's own two refusals, said at the same point the second name's are — before
# the server's run directory is numbered, before the JVM, before anything this run could
# leave on disk. `tools/run_controlled_server.py` refuses the same shapes as its backstop.
#
#   * `MINEKIN_DOMAIN_PROBE_SECOND` makes two probed names, and the trunk goes into one
#     kin's look, so the pair does not say whose look the logs are stacked in — the same
#     reason `MINEKIN_DOMAIN_USE_TARGET` is refused against the second name above;
#   * `MINEKIN_DOMAIN_USE_TARGET` already puts a block in that same look, and two blocks
#     in one look do not say which one the Kin is supposed to break.
# --- resource-trunk-guard begin (the contract test extracts this region) ---
if [[ -n "${resource_trunk}" ]]; then
    if [[ -n "${probe_second}" ]]; then
        printf 'domain: MINEKIN_DOMAIN_RESOURCE_TRUNK stacks oak logs in the look of one probed kin and MINEKIN_DOMAIN_PROBE_SECOND adds a second probed name (%s); the pair does not say whose look the trunk is placed in -- refused here, before anything is written\n' \
            "${probe_second}" >&2
        exit 2
    fi
    if [[ -n "${use_target}" ]]; then
        printf 'domain: MINEKIN_DOMAIN_RESOURCE_TRUNK and MINEKIN_DOMAIN_USE_TARGET both put a block in the look of one probed kin; two blocks in the same look do not say which one the Kin is supposed to break -- refused here, before anything is written\n' >&2
        exit 2
    fi
fi
# --- resource-trunk-guard end ---
#
# The hungry-kin fixture's own two refusals, said at the same point the trunk's are —
# before the server's run directory is numbered, before the JVM, before anything this
# run could leave on disk. `tools/run_controlled_server.py` refuses the same shapes as
# its backstop.
#
#   * `MINEKIN_DOMAIN_PROBE_SECOND` makes two probed names, and the meal is served to
#     one kin whose hunger bar the reading is meant to explain — the pair does not say
#     whose;
#   * `MINEKIN_DOMAIN_USE_TARGET` keeps a block where the Kin is looking, and the meal's
#     Core-side precondition needs the crosshair to land on nothing — the pair would
#     make every meal a refusal, which is a fixture guaranteeing its own failure.
# --- hungry-kin-guard begin (the contract test extracts this region) ---
if [[ -n "${hungry_kin}" ]]; then
    if [[ -n "${probe_second}" ]]; then
        printf 'domain: MINEKIN_DOMAIN_HUNGRY_KIN feeds one probed kin a meal and MINEKIN_DOMAIN_PROBE_SECOND adds a second probed name (%s); the pair does not say whose hunger bar the meal is for -- refused here, before anything is written\n' \
            "${probe_second}" >&2
        exit 2
    fi
    if [[ -n "${use_target}" ]]; then
        printf 'domain: MINEKIN_DOMAIN_HUNGRY_KIN needs the kin crosshair to land on nothing for the meal and MINEKIN_DOMAIN_USE_TARGET keeps a block where it is looking; the pair would make every meal a refusal -- refused here, before anything is written\n' >&2
        exit 2
    fi
fi
# --- hungry-kin-guard end ---
#
# The armed-kin fixture's own refusal, said at the same point the meal's are — before
# the server's run directory is numbered, before the JVM, before anything this run could
# leave on disk. `tools/run_controlled_server.py` refuses the same shape as its backstop.
#
#   * `MINEKIN_DOMAIN_PROBE_SECOND` makes two probed names, and the weapons are handed
#     to one kin whose hand the reading is meant to explain — the pair does not say
#     whose.
# --- armed-kin-guard begin (the contract test extracts this region) ---
if [[ -n "${armed_kin}" ]]; then
    if [[ -n "${probe_second}" ]]; then
        printf 'domain: MINEKIN_DOMAIN_ARMED_KIN hands its weapons to one probed kin and MINEKIN_DOMAIN_PROBE_SECOND adds a second probed name (%s); the pair does not say whose hand the reading is about -- refused here, before anything is written\n' \
            "${probe_second}" >&2
        exit 2
    fi
fi
# --- armed-kin-guard end ---
#
# The front-placed summon's own refusal, said at the same point the others are — before
# the server's run directory is numbered, before the JVM. It places *the* summoned body,
# so without `MINEKIN_DOMAIN_SUMMON` there is nothing to place;
# `tools/run_controlled_server.py` refuses the same shape as its backstop.
# --- summon-front-guard begin (the contract test extracts this region) ---
if [[ -n "${summon_front}" ]]; then
    if [[ -z "${summon}" ]]; then
        printf 'domain: MINEKIN_DOMAIN_SUMMON_FRONT places the summoned body in the kin look and MINEKIN_DOMAIN_SUMMON is empty; the pair does not say which entity -- refused here, before anything is written\n' >&2
        exit 2
    fi
fi
# --- summon-front-guard end ---
#
# The second name, when the run named one, is *appended* after the first and
# never put in its place: the first name is what the judgement gates above read.
# With the knob unset the branch below does not run, and `probe_args` stays
# byte-identical to what it was before the second name existed.
# --- second-probe-forge begin (the contract test extracts this region) ---
probe_args=(--probe-player "${probe:-${player}}" --probe-every-seconds "${probe_seconds}")
if [[ -n "${probe_second}" ]]; then
    probe_args+=(--probe-player "${probe_second}")
fi
# --- second-probe-forge end ---
if [[ -n "${use_target}" ]]; then
    probe_args+=(--use-target)
fi
# The trunk, when the run asked for one, appended the same default-off way the second
# name and the use target are: unset, this branch does not run and `probe_args` stays
# byte-identical to what it was before the knob existed.
# --- resource-trunk-forge begin (the contract test extracts this region) ---
if [[ -n "${resource_trunk}" ]]; then
    probe_args+=(--resource-trunk)
fi
# --- resource-trunk-forge end ---
# The world-clock schedule, when the run asked for one, appended the same default-off way
# the trunk's is: unset, this branch does not run and `probe_args` stays byte-identical to
# what it was before the knob existed. One `SECONDS:PHASE` per comma, each becoming its own
# `--time-phase`; the tool parses and refuses them, and an emptied entry is refused there
# too rather than dropped here.
# --- time-phase-forge begin (the contract test extracts this region) ---
if [[ -n "${time_phase}" ]]; then
    IFS=',' read -r -a time_phase_specs <<<"${time_phase}"
    for time_phase_spec in "${time_phase_specs[@]}"; do
        probe_args+=(--time-phase "${time_phase_spec}")
    done
fi
# --- time-phase-forge end ---
# Clearing hostiles, when the run asked for it, appended the same default-off way the
# other fixtures are: unset, this branch does not run and `probe_args` stays byte-identical.
# --- clear-hostiles-forge begin (the contract test extracts this region) ---
if [[ -n "${clear_hostiles}" ]]; then
    probe_args+=(--clear-hostiles)
fi
# --- clear-hostiles-forge end ---
# The meal, when the run asked for one, appended the same default-off way the trunk's is:
# unset, this branch does not run and `probe_args` stays byte-identical to what it was
# before the knob existed.
# --- hungry-kin-forge begin (the contract test extracts this region) ---
if [[ -n "${hungry_kin}" ]]; then
    probe_args+=(--hungry-kin)
fi
# --- hungry-kin-forge end ---
#
# The weapon pair, appended the same default-off way the meal's is: unset, this branch
# does not run and `probe_args` stays byte-identical to what it was before the knob
# existed.
# --- armed-kin-forge begin (the contract test extracts this region) ---
if [[ -n "${armed_kin}" ]]; then
    probe_args+=(--armed-kin)
fi
# --- armed-kin-forge end ---
#
# The empty-world switch, appended the same default-off way: unset, this branch
# does not run and `probe_args` stays byte-identical to what it was before the
# knob existed.
# --- no-ambient-spawns-forge begin (the contract test extracts this region) ---
if [[ -n "${no_ambient_spawns}" ]]; then
    probe_args+=(--no-ambient-spawns)
fi
# --- no-ambient-spawns-forge end ---
#
# Who this run asked the server about, for the bundle that has to say so
# (V1201-PROBE-TARGET-HANDOVER-001, cell 2).
# --- seal-probed-players-guard begin (the contract test extracts this region) ---
# The server's reply to `data get entity <name> Pos` is `[x, y, z]` and never says
# whose, so a bundle that carries a displacement without the names it was asked for
# cannot be attributed after the fact. `tools/seal_run_evidence.py` already takes the
# names one per `--probed-player` and `tools/assert_case_evidence.py` already reads
# them back; the harness was the only link missing, and it is wired here rather than
# at the seal because the seal is the last thing this run does.
#
# The names are read out of `probe_args` — the argv this run actually hands the server
# two lines above — and never out of the environment again. Re-reading the environment
# is the wrong source twice over: with `MINEKIN_DOMAIN_PROBE` unset the run probes the
# whitelisted account, which the raw knob does not hold, and a knob edited between the
# construction and the seal would seal a name this run never spoke.
#
# Default-off: unset, `seal_probed_player_args` stays empty and the seal command line
# is byte-for-byte what it was before this switch existed.
seal_probed_player_args=()
if [ "${seal_probed_players_asked}" -eq 1 ]; then
    asked_player_names=()
    argument_index=0
    while [ "${argument_index}" -lt "${#probe_args[@]}" ]; do
        if [ "${probe_args[${argument_index}]}" = "--probe-player" ]; then
            asked_player_names+=("${probe_args[$((argument_index + 1))]}")
        fi
        argument_index=$((argument_index + 1))
    done
    for asked_player in "${asked_player_names[@]}"; do
        if [ -z "${asked_player}" ]; then
            printf 'domain: MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS would seal an empty probe target, and an empty name is nobody -- refused here, before anything is written\n' >&2
            exit 2
        fi
        # The same shape `tools/run_controlled_server.py` refuses its probes at
        # (`minekin_core.domain.offline_identity.is_valid_username`), checked here so a
        # name that would never have reached the server cannot reach the bundle either.
        # An unquoted regex is bash's own rule; quoting it would ask for a literal.
        if [[ ! "${asked_player}" =~ ^[A-Za-z0-9_]{3,16}$ ]]; then
            printf 'domain: MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS would seal %q as a probed name and that is not a vanilla player name (3 to 16 characters of A-Z a-z 0-9 _); the server was never able to answer a probe for it -- refused here, before anything is written\n' \
                "${asked_player}" >&2
            exit 2
        fi
    done
    for asked_player in "${asked_player_names[@]}"; do
        seal_probed_player_args+=(--probed-player "${asked_player}")
    done
    # And the whole argv that is about to be handed over is read back the way the
    # server's arguments were, name by name. This is the check that keeps the handover
    # honest rather than merely derived: anything that puts a name into the sealed set
    # without putting it into `probe_args` — a future append, a re-read of an
    # environment value, a name copied from a sibling run — is refused here, and the
    # count is compared as well so a dropped name reads red instead of sealing a short
    # set that still looks plausible.
    sealed_player_names=()
    argument_index=0
    while [ "${argument_index}" -lt "${#seal_probed_player_args[@]}" ]; do
        if [ "${seal_probed_player_args[${argument_index}]}" = "--probed-player" ]; then
            sealed_player_names+=("${seal_probed_player_args[$((argument_index + 1))]}")
        fi
        argument_index=$((argument_index + 1))
    done
    if [ "${#sealed_player_names[@]}" -ne "${#asked_player_names[@]}" ]; then
        printf 'domain: the sealed probe set holds %s names and this run asked %s (%s); the two have to be the same set -- refused here, before anything is written\n' \
            "${#sealed_player_names[@]}" "${#asked_player_names[@]}" \
            "${sealed_player_names[*]-}" >&2
        exit 2
    fi
    for sealed_player in "${sealed_player_names[@]}"; do
        asked_again=0
        for asked_player in "${asked_player_names[@]}"; do
            if [ "${sealed_player}" = "${asked_player}" ]; then
                asked_again=1
            fi
        done
        if [ "${asked_again}" -eq 0 ]; then
            printf 'domain: the sealed probe set names %s, which this run never asked the server about (the probe arguments name %s) -- refused here, before anything is written\n' \
                "${sealed_player}" "${asked_player_names[*]-}" >&2
            exit 2
        fi
    done
fi
# --- seal-probed-players-guard end ---

# And a run that is verifying the release a death causes has to be able to kill the
# Kin, which only the server can do.
kill_args=()
if [[ -n "${kill}" ]]; then
    kill_args=(--kill-player "${kill}")
    if [[ -n "${kill_after_seconds}" ]]; then
        kill_args+=(--kill-after-join-seconds "${kill_after_seconds}")
        printf 'domain: the world will kill %s %ss after its join line, not at the launcher'"'"'s own six\n' \
            "${kill}" "${kill_after_seconds}" >&2
    fi
fi

# Same for the other ending a server can start: a kick, which ends the session
# while the client keeps running.
kick_args=()
if [[ -n "${kick}" ]]; then
    kick_args=(--kick-player "${kick}")
fi

# A run that names no server profile joins no world, and there is nothing for a
# server to do: starting one would add half a minute and a world to the data
# volume for a run that will never look at either. What it must not do is leave
# the harness unable to say which kind of run this was — the session's own
# arguments say it, and everything below reads them.
server_pid=""
server_starttime_ticks=""
server_pid_namespace_inode=""
server_directory=""
stop_the_server() {
    # SIGTERM, not SIGINT. A background job of a non-interactive shell inherits
    # SIGINT set to ignore, so `kill -INT` on this process did nothing at all and
    # the server ran on until the container was killed — eight minutes of a run
    # that had already finished. Measured in the runner image: `SIGINT SIG_IGN`,
    # `SIGTERM SIG_DFL`, and the tool installs a handler for both now, so either
    # one reaches the server's own `stop` command and the world is saved.
    if [ -n "${server_pid}" ]; then
        kill -TERM "${server_pid}" 2>/dev/null || true
        wait "${server_pid}" 2>/dev/null || true
    fi
}
trap stop_the_server EXIT

if [ -n "${server_profile}" ] && [ -n "${black_hole}" ]; then
    # Something is listening on the address the profile names and it will never
    # answer. Started before the client so the port is taken when the client
    # dials, and its log is kept because "nobody ever connected" is a fact this
    # scenario has to be able to see.
    python /src/tools/run_silent_listener.py --server-profile "${server_profile}" \
        >/tmp/domain-black-hole.log 2>&1 &
    server_pid=$!
    printf 'domain: a black hole is listening; nothing will answer\n' >&2
elif [ -n "${server_profile}" ]; then
    # One fresh directory per run, numbered past everything already there: a run
    # directory is evidence and is only ever appended to.
    n=1
    while [ -e "${runs}/run-${n}" ]; do n=$((n + 1)); done
    server_directory="${runs}/run-${n}"

    # The tool's own chatter goes to /tmp rather than into the run directory: it
    # creates that directory itself and refuses a non-empty one, which is the
    # check that keeps an earlier run's world and log from being written over.
    # The whitelist is what this run is about when the Kin is meant to be
    # refused: omitting the name leaves it empty, and the server's own
    # `usercache.json` and log are then the record of the refusal.
    allow_args=(--allow-player "${player}")
    if [ -n "${not_whitelisted}" ]; then
        allow_args=()
    fi
    # --- joiner-controlled-server-allowlist begin (the contract test extracts this region) ---
    # The shape this name opens puts a *second* Kin in this dedicated world, and that
    # world enforces its whitelist (`white-list=true`, `enforce-whitelist=true`, both
    # written by tools/run_controlled_server.py from the frozen profile) — so a joiner
    # whose own username is not in it is refused at the login handshake and the run
    # would report the shape as unreachable rather than as refused. The one name added
    # here is `${join_username}`: the value this run already launches the joining client
    # with, the value the arrival grep, the ledger baseline and the seal's
    # `subject_username` all read. It is a name of a player this run starts itself, which
    # is exactly what `--allow-player` has always meant; nothing is admitted that this
    # run did not create, no address, mode or count is widened, and no literal player
    # name is written here. With the name unset, the list is the one every run before
    # this card handed the server.
    if [ "${join_on_controlled_server_asked}" -eq 1 ]; then
        allow_args+=(--allow-player "${join_username}")
    fi
    # --- joiner-controlled-server-allowlist end ---
    pack_args=()
    if [ -n "${resource_pack}" ]; then
        pack_args=(--resource-pack)
    fi
    online_args=()
    case "${online_mode}" in
        true) online_args=(--online-mode) ;;
        false) online_args=(--no-online-mode) ;;
        "") ;;
        *)
            printf 'domain: MINEKIN_DOMAIN_ONLINE_MODE must be true or false, not %s
'                 "${online_mode}" >&2
            exit 2
            ;;
    esac
    # The one caller the status knob was registered for: the auto path resolves and
    # observes its target through the vanilla status endpoint, so an auto-bundle run
    # asks the controlled server to answer one. Asked under exactly the predicate the
    # readiness check below is asked under — `-n "${auto_bundle}"` — and no wider:
    # every other run keeps the tool's reviewed default (`enable-status=false`),
    # because a domain whose whole purpose is to be joined by one named Kin has no
    # reason to announce itself to whoever asks. The check that reads the setting
    # back off the disk still stands after this line: it reads the file, not the
    # request, and it stays as the harness's own guard if the write is ever reverted
    # elsewhere.
    status_args=()
    if [ -n "${auto_bundle}" ]; then
        status_args=(--enable-status)
    fi
    python /src/tools/run_controlled_server.py \
        --directory "${server_directory}" \
        --jar /server/server.jar \
        --accept-eula \
        --difficulty "${MINEKIN_DOMAIN_DIFFICULTY:-normal}" \
        "${version_args[@]}" \
        "${allow_args[@]}" \
        "${online_args[@]}"         "${pack_args[@]}" \
        "${status_args[@]}" \
        "${summon_args[@]}" \
        "${probe_args[@]}" \
        "${kill_args[@]}" \
        "${kick_args[@]}" \
        --keep-running >/tmp/domain-server.log 2>&1 &
    server_pid=$!

    printf 'domain: server run directory %s\n' "${server_directory}" >&2
else
    printf 'domain: no server profile; this run joins no world\n' >&2
fi

if [ -n "${server_pid}" ]; then
    if ! read -r server_starttime_ticks server_pid_namespace_inode \
            <<<"$(read_process_identity "${server_pid}" 2>/dev/null)" ||
            [ -z "${server_starttime_ticks}" ] || [ -z "${server_pid_namespace_inode}" ]; then
        printf 'domain: the server supervisor identity could not be captured\n' >&2
        exit 2
    fi
fi

# The client is not started until the server says it is ready. A refused
# connection is not a test of the admission path, it is a test of the clock. A
# run with no server has no clock to wait for.
if [ -n "${server_pid}" ]; then
    for _ in $(seq 1 480); do
        if [ -n "${black_hole}" ]; then
            if grep -q '"listening"' /tmp/domain-black-hole.log 2>/dev/null; then
                break
            fi
        elif grep -q 'Done (' "${server_directory}/server.log" 2>/dev/null; then
            break
        fi
        if ! kill -0 "${server_pid}" 2>/dev/null; then
            printf 'domain: the server exited before it reported ready\n' >&2
            tail -n 20 /tmp/domain-server.log >&2 || true
            exit 1
        fi
        sleep 1
    done
    if [ -n "${black_hole}" ]; then
        if ! grep -q '"listening"' /tmp/domain-black-hole.log 2>/dev/null; then
            printf 'domain: the black hole never reported that it was listening\n' >&2
            exit 1
        fi
        printf 'domain: the black hole is ready\n' >&2
    else
        if ! grep -q 'Done (' "${server_directory}/server.log" 2>/dev/null; then
            printf 'domain: the server never reported ready\n' >&2
            exit 1
        fi
        printf 'domain: server ready\n' >&2
        # A checkable reading of the one server setting the auto path depends on:
        # resolution and status observation of an auto-bundle target go through the
        # vanilla status endpoint, and whether this controlled server answers one
        # is written by the launcher tool into the run directory's own settings
        # file. It is printed for every server run — a run can then see the switch
        # it is relying on rather than assuming it — and an auto-bundle run whose
        # server will not answer stops here, by name, before a client is started
        # into a join that can never be observed. The flip itself belongs to
        # tools/run_controlled_server.py, outside this harness's surface, and is
        # registered for its own card; this reading is what makes that blocker
        # checkable from inside a run instead of inferred from a failed join.
        enable_status="$(sed -n 's/^enable-status=//p' \
            "${server_directory}/server.properties" 2>/dev/null | tail -1)"
        printf 'domain: the controlled server reports enable-status=%s\n' "${enable_status:-unreadable}" >&2
        if [ -n "${auto_bundle}" ] && [ "${enable_status}" != "true" ]; then
            printf 'domain: the auto path needs this server to answer status and it reports enable-status=%s; the controlled-server tool has to make it answer (registered separately), so the run stops before the client starts\n' \
                "${enable_status:-unreadable}" >&2
            exit 2
        fi
    fi
fi

# A run whose target is not listening. The server is stopped again as soon as it
# has proved it can start, which is the cheapest way to get a refused connection:
# the client still connects to the address in the frozen profile, and nothing is
# there. It is the one failure the Bridge used to say nothing about, because it
# never reaches a login handler.
if [[ -n "${no_server}" ]]; then
    stop_the_server
    printf 'domain: the server has been stopped; nothing is listening\n' >&2
fi

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
# The second client's environment, before anything starts: its Kin, its artifact store,
# and the profile it will dial. All three are preparation rather than the run — the
# second Kin exists so its identity differs from the host's, and the store is a *copy*
# because the store refuses to have its root be a symlink, so linking it is not an
# option the fixture gets to take.
join_ready=0
if [ -n "${joiner}" ]; then
    if [ -z "${open_lan}" ] && [ "${join_on_controlled_server_asked}" -eq 0 ]; then
        printf 'domain: a joiner needs a world to join; set MINEKIN_DOMAIN_OPEN_LAN=1\n' >&2
        exit 2
    fi
    # Named rather than picked: with a second Kin in the root, "the first directory"
    # is a coin toss, and copying the wrong store would surface as a missing artifact
    # much later in the run.
    host_kin="${MINEKIN_KIN_ID:-}"
    if [ -z "${host_kin}" ]; then
        printf 'domain: a joining run must name the hosting Kin (MINEKIN_KIN_ID)\n' >&2
        exit 2
    fi
    if [ ! -d "/data/kin/${joiner}" ]; then
        if ! MINEKIN_USERNAME="${join_username}" python -m minekin_core init \
            --kin-id "${joiner}" >>/tmp/domain-join-setup.log 2>&1; then
            printf 'domain: could not create the joining Kin %s (see /tmp/domain-join-setup.log)\n' \
                "${joiner}" >&2
            exit 2
        fi
        printf 'domain: the joining Kin %s was created as %s\n' "${joiner}" "${join_username}" >&2
    fi
    # `run/session/` is prepared with `run/`: a Kin that has never started a session
    # has no session directory, and the join baseline below is empty by design — an
    # earlier shape of this block left the directory away and the baseline read died
    # on it (see `before=` in `join_the_published_world`).
    mkdir -p "/data/kin/${joiner}/run/session"
    if [ -L "/data/kin/${joiner}/run/artifact-store" ]; then
        # Left by an attempt that linked it; `-d` follows a link, so the copy below
        # would be skipped and the refusal would come back looking like the same bug.
        rm -f "/data/kin/${joiner}/run/artifact-store"
    fi
    if [ ! -d "/data/kin/${joiner}/run/artifact-store" ]; then
        cp -a "/data/kin/${host_kin}/run/artifact-store" \
            "/data/kin/${joiner}/run/artifact-store" ||
            {
                printf 'domain: could not give the joining Kin an artifact store\n' >&2
                exit 2
            }
    fi
    # The joining client dials the world this run started, so the version its profile
    # claims has to be that world's version. The constant this writer used to carry
    # (`"minecraft_version": "1.21.4"`) paired any server with a joiner saying 1.21.4:
    # on a 1.20.1 run the ⑤-family client endings (`GLFW 0x1000E`, `XDG_RUNTIME_DIR`)
    # could then be neither reproduced nor excluded, because the profile the joiner
    # was handed described a different world than the one it dialed. The version is
    # therefore taken from `launched_version` — the recipe this run read at the top —
    # and said by name when the run holds none: falling back to any constant here
    # would be the very misjoin this block exists to prevent, so there is no default
    # to fall back to and the run stops before a profile is written.
    if [ -z "${launched_version}" ]; then
        printf 'domain: the joining client must carry the version this run launched, and this run launched none it could name; refusing to write a joiner profile at a guessed version\n' >&2
        exit 2
    fi
    # --- joiner-controlled-server-target begin (the contract test extracts this region) ---
    # The endpoint the joining client is pointed at. Two sources, and both of them this
    # run's own:
    #
    #   * every shape that existed before this card — the LAN world the hosting client is
    #     told to publish, on the port that run named for it (`${lan_port}`);
    #   * `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER` — what the dedicated server this run
    #     started actually bound, read out of `${server_directory}/server.properties`,
    #     the settings file the controlled launcher wrote for this run and no other.
    #
    # Read, never assumed, for the reason this whole file keeps running into: a port
    # taken from a fixture is a join to a different world, and the run would then report
    # probes answered about a server nobody joined. The address is read alongside it and
    # accepted only when it *is* the loopback literal the frozen profile schema admits
    # and the document below emits — a `server-ip` naming anything else is a named
    # refusal, never something to dial, so no run of this shape can reach a machine that
    # this container did not start. The value a refusal leaves behind is nothing: the run
    # stops before the profile exists.
    joiner_target_port="${lan_port}"
    if [ "${join_on_controlled_server_asked}" -eq 1 ]; then
        joiner_target_source="${server_directory}/server.properties"
        # `-r` before either read: under `set -euo pipefail` a `sed` that cannot open the
        # file would abort the run on a signal and leave the refusal unsaid, which is the
        # one outcome worse than naming the missing file.
        if [ -r "${joiner_target_source}" ]; then
            controlled_server_ip="$(sed -n 's/^server-ip=//p' "${joiner_target_source}" | tail -1)"
            controlled_server_port="$(sed -n 's/^server-port=//p' "${joiner_target_source}" | tail -1)"
        else
            controlled_server_ip=""
            controlled_server_port=""
        fi
        case "${controlled_server_port}" in
            '' | *[!0-9]*)
                printf 'domain: this run cannot read the port its own controlled server bound from %s (server-port=%s), so no target is written into the joining client profile\n' \
                    "${joiner_target_source}" "${controlled_server_port:-unreadable}" >&2
                exit 2
                ;;
        esac
        if [ "${controlled_server_ip}" != "127.0.0.1" ]; then
            printf 'domain: this run sends its joining client to its own controlled server, which reads server-ip=%s from %s; only the loopback literal the profile schema admits is dialled, so the run stops rather than naming a different address\n' \
                "${controlled_server_ip}" "${joiner_target_source}" >&2
            exit 2
        fi
        joiner_target_port="${controlled_server_port}"
        printf 'domain: the joining client dials the controlled server this run started at %s:%s, read from %s\n' \
            "${controlled_server_ip}" "${joiner_target_port}" "${joiner_target_source}" >&2
    fi
    # --- joiner-controlled-server-target end ---
    python - "${joiner_target_port}" /tmp/domain-join-profile.json "${launched_version}" <<'PY'
import json
import sys

port, path, version = int(sys.argv[1]), sys.argv[2], sys.argv[3]
profile = {
    "schema_version": 1,
    "profile_id": "p0-lan-host-fixture",
    "host": "127.0.0.1",
    "port": port,
    "auth_mode": "offline",
    "minecraft_version": version,
    "visibility": "isolated_test_only",
    "resource_pack_policy": "deny",
}
# The document above is the frozen *v1* shape, and v1 admission
# (`server_profile.MINECRAFT_VERSION`) pins exactly one Minecraft version: 1.21.4. So a
# run that launched any other version had its honest profile refused before the joining
# client's JVM started (`launcher.profile`, "server profile minecraft_version is outside
# the pinned bundle") — measured on these bytes, and named as V's blocker B1.
#
# The reviewed v2 managed-target shape is the one that already carries a version policy
# instead of a pinned constant, and `load_session_server_profile` dispatches on the saved
# `schema_version`. A run whose client is not 1.21.4 therefore hands the joiner a v2
# document for the very endpoint it started: the same loopback host and port taken from
# the profile above rather than restated here, still `offline`, and a version policy
# naming exactly the version this run launched. Nothing is widened to get there — a v2
# session target outside loopback, with online auth, or with an allowlist of more than
# the run's own version is refused by the same loader.
#
# 1.21.4 keeps the v1 bytes above, byte for byte and refusal for refusal: what moved is
# the version source, not the criteria V01 froze for the pinned route.
if version != "1.21.4":
    profile = {
        "schema_version": 2,
        "profile_id": profile["profile_id"],
        "host": profile["host"],
        "port": profile["port"],
        "auth_mode": profile["auth_mode"],
        "version_policy": {
            "mode": "explicit_allowlist",
            "allowed_versions": [version],
        },
        "resource_pack_policy": profile["resource_pack_policy"],
        "target_authorization": {
            "granted_by": "controlled-runner",
            "basis": (
                "the loopback world this controlled runner started for this very run; "
                "no address outside loopback and no operator-supplied target is named here"
            ),
        },
    }
with open(path, "w", encoding="utf-8") as document:
    document.write(json.dumps(profile, indent=2) + "\n")
PY
    # ---------------------------------------------------------------------------
    # The environment the joining client is *actually handed*, named before its JVM
    # starts rather than inferred from what it crashed with afterwards.
    #
    # Why this exists as a reading and not as a comment: three runs of one case were
    # judged on one byte-identical recipe and the machine answered differently — the
    # same `domain.sh`, the same image, the same pinned artifacts — two of them died in
    # the client with `[0x1000E] Failed to detect any supported platform` and one of
    # them passed. Nothing the bundle said about that run could tell a reader which
    # screen, which runtime directory or which GL stack the client process had been
    # given, because the only display-shaped field in the evidence
    # (`environment.renderer_display`) is measured by the *sealer*, by its own
    # `xvfb-run … glxinfo -B` below, and it therefore says nothing about a run whose
    # client never reached a window at all. Measured: it reads
    # `llvmpipe (LLVM 20.1.2, 256 bits)` in every one of those six samples, PASS and
    # FAIL alike.
    #
    # So the launcher names the three items itself, at both depths that matter, into
    # one file in the joining Kin's run directory:
    #   * `harness` — the environment this script holds at the moment it launches,
    #   * `launch`  — the environment the wrapper hands down to the client's child.
    # Two depths because the interesting thing is the *difference*: `xvfb-run` allocates
    # its own server, its own `XAUTHORITY` and its own `DISPLAY`, so the values the
    # client JVM sees are not the ones the harness exported.
    #
    # This is a reading, not a fix: it never exports, unset or defaults any of the three
    # names, so it cannot hide a FAIL by making the environment look like something else.
    # An item that is not set is written as `<unset>`, and a screen nobody serves is
    # written as `unmeasurable: …` — a missing reading is named as missing rather than
    # left as an empty string a later reader would call "the same as unset".
    #
    # The one thing this run *does* hand over — a runtime directory, see
    # `provide_the_joiner_runtime_directory` — is therefore read rather than assumed: the
    # line below the three items names where the runtime directory came from, so a value
    # the harness supplied is recorded as supplied and never reads as inherited.
    joiner_launch_wrapper=(xvfb-run -a --server-args="-screen 0 1280x720x24")
    client_environment_readout="/data/kin/${joiner}/run/client-environment.txt"
    client_environment_probe='
        depth="${1:?which environment is being named}"
        out="${2:?where the named environment is written}"
        # Three states, not two: a name that is absent and a name that is present but
        # blank answer different questions, and an empty string would let a reader
        # collapse them.
        read_one() {
            if [ -z "${!1+set}" ]; then
                printf "%s" "<unset>"
            elif [ -z "${!1}" ]; then
                printf "%s" "<set-but-empty>"
            else
                printf "%s" "${!1}"
            fi
        }
        probe=$(glxinfo -B 2>&1)
        probe_rc=$?
        backend=$(printf "%s\n" "${probe}" |
            sed -n "s/^OpenGL renderer string: //p" | head -1)
        if [ -z "${DISPLAY:-}" ]; then
            # Nothing to ask a renderer of, and that is said rather than measured.
            backend="not-measured: this process was handed no DISPLAY at all"
        elif [ -z "${backend}" ]; then
            case "${probe}" in
                *"unable to open display"*)
                    backend="unmeasurable: the DISPLAY named here is not being served (glxinfo rc=${probe_rc})" ;;
                *)
                    backend="unmeasurable: glxinfo rc=${probe_rc} said $(printf "%s" "${probe}" | tr "\n" " " | cut -c1-90)" ;;
            esac
        fi
        for item in DISPLAY XDG_RUNTIME_DIR XAUTHORITY; do
            printf "%s %s=%s\n" "${depth}" "${item}" "$(read_one "${item}")" >> "${out}"
        done
        # Where the runtime directory this depth holds came from, named apart from its
        # value. A path on the line above can be one the container already had or one
        # this harness made ready for the client, and a reader must not have to guess
        # which: a harness that fills in a blank and then reports only the filled-in
        # shape has graded its own work. Same three states as the three items above —
        # a depth that was never told says `<unset>` rather than dropping the line,
        # which is what the harness depth does while the launch line is the only one
        # this run hands a runtime directory to.
        printf "%s XDG_RUNTIME_DIR_ORIGIN=%s\n" "${depth}" \
            "$(read_one CLIENT_RUNTIME_DIR_ORIGIN)" >> "${out}"
        printf "%s GL_BACKEND=%s\n" "${depth}" "${backend}" >> "${out}"
        printf "%s GL_PROBE_RC=%s\n" "${depth}" "${probe_rc}" >> "${out}"
        # Which command line this reading came from, kept as a separate name rather than
        # folded into `depth`: a screen allocated *inside* the wrapper is a different
        # screen from the one the harness exported.
        printf "%s WRAPPER=%s\n" "${depth}" "${MINERUN_LAUNCH_DEPTH:-not-stated}" >> "${out}"
    '
    #: The runtime directory this run hands the joining client, and which of the two
    #: ways it has one that came from — `inherited` or `provided-by-harness`. Both are
    #: empty until `provide_the_joiner_runtime_directory` decides them, and the readout
    #: above carries whichever name it lands on rather than only the path.
    #:
    #: Under `/tmp`, and that choice is the load-bearing one:
    #:   * `/data` is a run's material. A directory made there would sit beside the
    #:     session overlay and the readout, and anything that later globs the Kin's run
    #:     directory would have to be taught to ignore it — a runtime directory is not
    #:     evidence and must never be sealable material. The canonical volume is not
    #:     written by this harness at all outside the material a run already produces.
    #:   * the XDG requirement on this directory is that it be private to its user
    #:     (mode 0700), so it is created per run and named, not shared out of an
    #:     existing world-writable location;
    #:   * `/tmp` is already where this harness keeps the unsealable scratch of a join
    #:     (`/tmp/domain-join-session.err`, the staged probe file), so nothing new is
    #:     left behind that the run has not already said where it is.
    client_runtime_dir=""
    client_runtime_dir_origin=""
    client_runtime_dir_base=/tmp/minekin-client-runtime
    join_ready=1
fi

# Name the three items at the depth this script can name them, say them on the run's
# own output once, and stage the probe for the depth it cannot. Called by the launcher
# itself — see `join_the_published_world` — and never on a path a normal run takes, so
# a run with no joiner pays nothing for it.
#
# The `launch` depth is deliberately NOT read here. An earlier form ran a second
# command line through the same wrapper array to take it, and wrote those values as the
# environment the client was handed; that was too strong — `xvfb-run` allocates its
# screen, `XAUTHORITY` and display number per invocation, so a probe run *through* the
# wrapper is a sibling of the client, not its ancestor, and can only claim to be like
# it. The reading now happens on the launch line itself (see `join_the_published_world`),
# inside the wrapper process that `exec`s into the client, so what it writes is what
# the client's JVM is handed, by construction. This function's job is the `harness`
# depth and staging the probe file that line runs.
#
# It returns rather than exits whatever it could not do: a reading that cannot be taken
# is a named gap in the record, not a reason to destroy a run that was about to produce
# evidence. `set -e` is back on by the time this is called.
name_the_joiner_client_environment() {
    local rc=0
    rm -f /tmp/domain-client-environment.err
    if ! : > "${client_environment_readout}" 2>/dev/null; then
        printf 'domain: the joining client environment could not be written because %s is not writable\n' \
            "${client_environment_readout}" >&2
        return 0
    fi
    # Stage the probe as a file the launch line can run: the alternative — embedding the
    # whole probe in the launch command line — would put a second copy of it beside the
    # one this function runs, and the two could drift apart from each other.
    client_environment_probe_script=/tmp/domain-client-environment-probe.sh
    if ! printf '%s\n' "${client_environment_probe}" > "${client_environment_probe_script}" 2>/dev/null; then
        printf 'domain: the environment probe could not be staged at %s, so the launch-depth reading will name its own absence\n' \
            "${client_environment_probe_script}" >&2
    fi
    # Depth 1 — what this script holds. The harness owns the X server for the whole run
    # (see `Xvfb "${session_display}"`), so its own DISPLAY is the harness screen, not
    # the one the joiner is about to be handed.
    MINERUN_LAUNCH_DEPTH=direct \
        bash -c "${client_environment_probe}" minekin-runner harness \
        "${client_environment_readout}" 2>>/tmp/domain-client-environment.err ||
        rc=$?
    [ "${rc}" -eq 0 ] ||
        printf 'domain: harness=unmeasurable: the probe process itself failed rc=%s (see /tmp/domain-client-environment.err)\n' \
            "${rc}" >&2
    # The greppable line: the harness-depth items as one line, exactly as the file
    # holds them so far. The `launch` lines land in the same file a moment later,
    # written by the wrapper that execs the client, and the classifier below reads
    # them from there.
    printf 'domain: joiner client environment before its JVM: %s\n' \
        "$(grep '^harness ' "${client_environment_readout}" 2>/dev/null |
            tr '\n' ' ')" >&2
    return 0
}

# Hand the joining client's launch line a runtime directory it can use, and say which
# of the two ways this run has one it came from.
#
# Why now, and why this is the whole of it: the reading above has named
# `launch XDG_RUNTIME_DIR=<unset>` on every controlled run since it landed, and naming
# is where it stopped — deliberately so, because a reading that fills in its own blanks
# can no longer report a blank. The blank is a fact about the container, measured: the
# controlled image sets no `XDG_RUNTIME_DIR` and has no `/run/user/<uid>` at all, and
# the joining client's own stderr answers with
# `error: XDG_RUNTIME_DIR is invalid or not set in the environment`. This harness is the
# side that decides what the launch line is handed, so this is the side that can put a
# usable directory there.
#
# Two rules keep the change on that one path and nowhere else:
#   * A value already in the environment is left alone when it is usable — absolute,
#     present, a directory, writable. The harness does not swap out a directory the
#     operator or the container made, and the readout then says `inherited`.
#   * A value that is missing or unusable becomes a private directory of this run at
#     mode 0700, which is what the XDG requirement for the name states, and the readout
#     says `provided-by-harness`. Why the inherited value was not used is named too
#     ("unset" and "set to a path that is not a directory" are facts about different
#     things), because a provision that cannot say what it replaced is a guess.
#
# It does NOT export into this script. The harness has no window surface of its own to
# register with a runtime directory — its display is the X server it started itself —
# and exporting here would widen the change past the one line that needs it. The value
# travels in `joiner_runtime_dir_env`, below, which is expanded on the client's own
# command line and nowhere else. If the directory cannot be made, that array stays
# empty, the client is handed exactly what it would have been handed before this
# function existed, and the failure is named on stderr: a run is not destroyed by a
# provision that could not provide.
provide_the_joiner_runtime_directory() {
    local candidate="${XDG_RUNTIME_DIR:-}"
    local reason=""
    client_runtime_dir=""
    client_runtime_dir_origin=""
    # Asked of the environment itself, not of the local copy above: a name nobody set
    # and a name set to nothing arrive here through the same empty string, and they are
    # different faults about different halves.
    if [ -z "${XDG_RUNTIME_DIR+set}" ]; then
        reason='it is not set in the environment this script holds'
    elif [ -z "${candidate}" ]; then
        reason='it is set to nothing in the environment this script holds'
    elif [ "${candidate#/}" = "${candidate}" ]; then
        reason="it is not an absolute path (${candidate})"
    elif [ ! -d "${candidate}" ]; then
        reason="it names no directory that is there (${candidate})"
    elif [ ! -w "${candidate}" ]; then
        reason="it is not writable (${candidate})"
    fi
    if [ -z "${reason}" ]; then
        client_runtime_dir="${candidate}"
        client_runtime_dir_origin=inherited
        printf 'domain: joiner runtime directory: %s (inherited, left as the environment had it)\n' \
            "${client_runtime_dir}" >&2
        return 0
    fi
    local made
    if ! mkdir -p "${client_runtime_dir_base}" 2>/dev/null; then
        printf 'domain: joiner runtime directory: not provided, %s cannot be created; the client keeps what it had, which was unusable because %s\n' \
            "${client_runtime_dir_base}" "${reason}" >&2
        return 0
    fi
    if ! made=$(mktemp -d "${client_runtime_dir_base}/runtime.XXXXXX" 2>/dev/null); then
        printf 'domain: joiner runtime directory: not provided, no directory could be made under %s; the client keeps what it had, which was unusable because %s\n' \
            "${client_runtime_dir_base}" "${reason}" >&2
        return 0
    fi
    if ! chmod 700 "${made}" 2>/dev/null || [ ! -d "${made}" ] || [ ! -w "${made}" ]; then
        printf 'domain: joiner runtime directory: not provided, %s could not be made private at mode 0700; the client keeps what it had, which was unusable because %s\n' \
            "${made}" "${reason}" >&2
        rmdir "${made}" 2>/dev/null || true
        return 0
    fi
    client_runtime_dir="${made}"
    client_runtime_dir_origin=provided-by-harness
    printf 'domain: joiner runtime directory: %s (provided by the harness at mode 0700; the name it would have inherited was unusable because %s)\n' \
        "${client_runtime_dir}" "${reason}" >&2
    return 0
}

# When the joining client never arrived, *which* downstream reading the run is evidence
# about. The criteria say `NO_CONNECTION_WAS_DIALLED` / `THE_CLIENT_NEVER_DIALLED_A_PORT`,
# and both are facts about the client half — but a reader who only sees them cannot tell
# whether the world was even there, and "the server status is not probeable" has the same
# shape as "the client never dialled" from downstream. So the two are read separately here:
# whether anything answers the port on loopback (nothing else — never a remote address),
# and whether the client was handed a screen that could be measured.
#
# The port probed is `${joiner_target_port}`, the one this run wrote into the joining
# client's profile, and never `${lan_port}` read raw. The two are the same number on every
# shape that predates `MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER` — that block sets the
# target to the LAN port when no controlled server was asked for — but they diverge on
# the dedicated-server shape, which dials the port its own server bound (25566 in the
# 1.20.1 runs) while the LAN port is never published at all. Probing the LAN port there
# answers "nothing listens on 25570", which is a fact about a world this shape never
# tried to publish, and the verdict then reads as evidence *about the world* while the
# joining client was dying somewhere else. Measured: an H66 campaign run whose joiner JVM
# crashed in `RenderSystem.initBackendSystem` (`GLFW 0x1000E`, screen measured at both
# depths, `GL_PROBE_RC=0`) was called `THE_WORLD_STATUS_IS_NOT_PROBEABLE … evidence about
# the world and not about the client environment`, and that line is what pointed the card
# at the world side. The target is read from the run, exactly as the dialled address is.
#
# This names readings, on the branch where the joiner had not arrived when the wait
# window closed — a reading about that moment, which a later arrival does not undo.
# The verdict names say the window for exactly that reason: an H1c run whose joiner
# arrived after its window (`snapshots_admitted 1`, ending `BRIDGE_LOST`) had been
# called a run that died on the client side, and this shape cannot know that much.
# It changes no criterion, no gate and no bundle field, and a run it
# describes is still the same FAIL it was before.
# --- joiner-downstream-reading-target begin (the contract test extracts this region) ---
classify_the_joiner_downstream_readings() {
    local listening=0
    local probe_rc=0
    timeout 5 bash -c "exec 3<>/dev/tcp/127.0.0.1/${joiner_target_port}" 2>/dev/null || probe_rc=$?
    if [ "${probe_rc}" -eq 0 ]; then
        listening=1
    fi
    local backend
    backend=$(sed -n 's/^launch GL_BACKEND=//p' "${client_environment_readout}" 2>/dev/null |
        head -1) || true
    local verdict
    if [ -z "${backend}" ]; then
        verdict='THE_CLIENT_ENVIRONMENT_WAS_NEVER_READ (no launch-depth line in '"${client_environment_readout}"'); this run cannot say which half died'
    elif [ "${listening}" -eq 1 ]; then
        case "${backend}" in
            unmeasurable* | not-measured*)
                verdict='THE_JOINER_SCREEN_WAS_UNMEASURABLE while the world was listening on 127.0.0.1:'"${joiner_target_port}"' at the window close (screen: '"${backend}"'), so the environment the joiner was handed is what this run measures' ;;
            *)
                verdict='THE_JOINER_HAD_NOT_ARRIVED_IN_THE_WINDOW with a live world and a measurable screen ('"${backend}"'), so the client half rather than the world is where to look at the moment the window closed; a joiner arriving after the window would make this line about the window, not about the death' ;;
        esac
    else
        case "${backend}" in
            unmeasurable* | not-measured*)
                verdict='BOTH_HALVES_NAMED_AND_BOTH_BAD: nothing answers 127.0.0.1:'"${joiner_target_port}"' and the client was handed no measurable screen ('"${backend}"')' ;;
            *)
                verdict='THE_WORLD_STATUS_IS_NOT_PROBEABLE: nothing answers 127.0.0.1:'"${joiner_target_port}"' while the client screen measured ('"${backend}"'), so this run is evidence about the world and not about the client environment' ;;
        esac
    fi
    printf 'domain: downstream reading — %s\n' "${verdict}" >&2
    printf 'downstream %s\n' "${verdict}" >> "${client_environment_readout}" 2>/dev/null || true
    return 0
}
# --- joiner-downstream-reading-target end ---

# What the joining client itself said before it stopped. This is a reading on the branch
# that reports a joiner which never arrived, and it changes no criterion, no gate and no
# bundle field.
name_the_joiner_client_last_words() {
    # The joining client's own text does not go to the launcher's stderr. Measured on a
    # private volume: a client that crashed at its GL init left its whole boot log under
    # /data/kin/${joiner}/run/session/ <session>/generation-1/logs/stdout.log, with the
    # crash report beside it, while the launcher's stderr held 65 bytes about an
    # unrelated directory. A branch that reads only that stderr reports a death it cannot
    # see, and the silence invites a conclusion the run never measured. The newest
    # session is the one this launch made, because a repeated run reuses the Kin root, and
    # the file is named with its path so the attribution can be checked rather than
    # trusted. Nothing here can end the run it is reporting on.
    local session_root newest generation log crash
    session_root="/data/kin/${joiner}/run/session/"
    newest=$(ls -t "${session_root}" 2>/dev/null | head -n 1) || true
    if [ -z "${newest}" ]; then
        printf 'domain: no session directory under %s, so the joining client left no words to read\n' \
            "${session_root}" >&2
        return 0
    fi
    generation="${session_root}${newest}/generation-1"
    log="${generation}/logs/stdout.log"
    if [ -s "${log}" ]; then
        printf "domain: the joining client's own last words, from %s:\n" "${log}" >&2
        tail -n 20 "${log}" >&2 2>/dev/null || true
    else
        printf "domain: the joining client's own last words, from %s: nothing there\n" "${log}" >&2
    fi
    crash=$(ls -t "${generation}/crash-reports/" 2>/dev/null | head -n 1) || true
    if [ -n "${crash}" ]; then
        printf 'domain: it left a crash report: %s\n' "${generation}/crash-reports/${crash}" >&2
    fi
    return 0
}

# Start the second client against the world the first one published, and wait for the
# *world* to say somebody arrived. The joiner's own document is what that client
# believes happened; the hosting client's server thread is the side that cannot be
# talked into it, and that is the fact L3 is about — one real client joining another's
# published world.
join_the_published_world() {
    local host_log="$1"
    local before
    local overlay
    local joined=0
    local deadline
    local baseline
    local recorded
    local playable
    # A joiner that has never started a session has no `run/session/` yet, and the
    # honest baseline for that is an empty one — but that has to be *said*, not left
    # to `ls`'s exit code. This read used to be `ls … 2>/dev/null | sort`, which
    # under `pipefail` turned a fresh joiner Kin into a silent `rc=2` (the first
    # CORE-030 attempt died on exactly that, with nothing on stderr). Either branch
    # is named now: a missing directory continues from an empty baseline with one
    # line saying what is absent and where, and a directory that exists but cannot
    # be listed is a failure with a name, a path and a non-zero exit.
    before=""
    if [ -d "/data/kin/${joiner}/run/session" ]; then
        before=$(ls "/data/kin/${joiner}/run/session/" | sort) ||
            {
                printf 'domain: the joining Kin %s has a session directory at /data/kin/%s/run/session that cannot be listed\n' \
                    "${joiner}" "${joiner}" >&2
                exit 2
            }
    else
        printf 'domain: the joining Kin %s has no session directory yet at /data/kin/%s/run/session; the join baseline is empty\n' \
            "${joiner}" "${joiner}" >&2
    fi
    # Where the joining Kin's ledger stood before this client started. Every wait in
    # this harness reads only its own run, and this one learned why the hard way: an
    # unscoped query found the `PlayableEstablished` of an *earlier* run of the same
    # Kin, so the harness announced a first snapshot the joining client's own document
    # said it had never admitted.
    baseline=$(/opt/sqlite/bin/sqlite3 "/data/kin/${joiner}/kin.sqlite3" \
        "select coalesce(max(position), 0) from event;" 2>/dev/null || echo 0)
    baseline=${baseline:-0}
    name_the_joiner_client_environment
    # The runtime directory is decided after that reading and before the wrapper runs:
    # the reading is about the environment this script holds, and this is a decision
    # about what the client's line is handed. Carried on the line itself rather than
    # exported here — see `provide_the_joiner_runtime_directory`.
    #
    # How far that reaches, measured rather than assumed: this line ends in the Core CLI,
    # and the client JVM that command supervises is not given this environment. Core
    # builds the client's from a closed list
    # (`config.FORWARDED_VARIABLES` plus the session's own redirects) and inherits
    # nothing implicitly, so `XDG_RUNTIME_DIR` stops at that door while `DISPLAY` and
    # `XAUTHORITY` cross it. This handover is therefore the harness's half of the
    # blocker and not all of it: what it fixes here is the absence on the line this
    # harness controls and the record of what was handed over, and the last step — the
    # name reaching the JVM that prints the libwayland line — is a decision on Core's
    # side of the boundary, registered as such rather than taken here.
    provide_the_joiner_runtime_directory
    joiner_runtime_dir_env=()
    if [ -n "${client_runtime_dir}" ]; then
        joiner_runtime_dir_env=(
            XDG_RUNTIME_DIR="${client_runtime_dir}"
            CLIENT_RUNTIME_DIR_ORIGIN="${client_runtime_dir_origin}"
        )
    fi
    # The launch-depth reading goes on this very command line, in the wrapper process
    # that becomes the client: the probe runs first, `exec` follows with the client as
    # its argument, and `exec` hands its environment to what it becomes — so the values
    # written are the ones the client's JVM is handed, and not those of a sibling
    # allocation taken through the wrapper earlier. A staged probe file that is missing
    # names its own absence in the readout rather than going silently quiet, and cannot
    # stop the client from starting either way.
    #
    # The one input ask this joining client can be handed rides on the same line, in
    # the same array the readback prints: `joiner_session_argv` is empty of control
    # words unless a `MINEKIN_DOMAIN_JOIN_*` name was set and passed the bounds
    # composed for it above, and then the words on this line are the words it carried
    # before that driver existed. This is the only place the array is started at all —
    # the hosting session's line is the run's own arguments, and never sees it.
    "${joiner_launch_wrapper[@]}" \
        env "${joiner_runtime_dir_env[@]}" MINEKIN_KIN_ID="${joiner}" \
            MINERUN_LAUNCH_DEPTH=inside-wrapper \
            CLIENT_ENVIRONMENT_PROBE_SCRIPT="${client_environment_probe_script:-/tmp/domain-client-environment-probe.sh}" \
            CLIENT_ENVIRONMENT_READOUT="${client_environment_readout}" \
        bash -c '
            if [ -f "${CLIENT_ENVIRONMENT_PROBE_SCRIPT}" ]; then
                bash "${CLIENT_ENVIRONMENT_PROBE_SCRIPT}" launch \
                    "${CLIENT_ENVIRONMENT_READOUT}" \
                    2>>/tmp/domain-client-environment.err || true
            else
                printf "launch GL_PROBE=not-staged: %s is absent\n" \
                    "${CLIENT_ENVIRONMENT_PROBE_SCRIPT}" >> "${CLIENT_ENVIRONMENT_READOUT}" 2>/dev/null || true
            fi
            exec "$@"
        ' minekin-joiner-launch \
            "${joiner_session_argv[@]}" \
            >/tmp/domain-join-session.json 2>/tmp/domain-join-session.err &
    joiner_pid=$!
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${joiner_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        if grep -q "${join_username} joined the game" "${host_log}" 2>/dev/null; then
            joined=1
            break
        fi
        sleep 1
    done
    if [ "${joined}" -eq 1 ]; then
        printf 'domain: the world heard %s arrive\n' "${join_username}" >&2
    else
        # The wait ends two different ways — the launcher walked out, or the window ran
        # out with it still trying — and one bare line stood for both. Measured cost: a
        # joining JVM that had exited on its own five minutes in was read as a display
        # limit of the container, because nothing else in the output said the process
        # had left at all (the client's own stderr, printed on the next line, was empty).
        if kill -0 "${joiner_pid}" 2>/dev/null; then
            printf 'domain: %s never arrived within %ss, and its launcher was still running when the window closed\n' \
                "${join_username}" "${seconds}" >&2
        else
            printf 'domain: %s never arrived: its own launcher had already exited, %ss into the %ss window\n' \
                "${join_username}" "$((SECONDS - deadline + seconds))" "${seconds}" >&2
        fi
        tr -d '\n' </tmp/domain-join-session.err >&2 || true
        printf '\n' >&2
        name_the_joiner_client_last_words
        classify_the_joiner_downstream_readings
    fi
    # Being *playable* is the joining client's own conclusion about the first snapshot
    # it admitted, and the ledger is where this harness reads conclusions. Measured:
    # stopping as soon as the world heard the arrival ended one run at `PLAY_INIT` with
    # no snapshot admitted at all, which is the difference between arriving somewhere
    # and being able to see it.
    if [ "${joined}" -eq 1 ]; then
        deadline=$((SECONDS + seconds))
        playable=0
        for _ in $(seq 1 "${seconds}"); do
            [ "${SECONDS}" -lt "${deadline}" ] || break
            recorded=$(/opt/sqlite/bin/sqlite3 "/data/kin/${joiner}/kin.sqlite3" \
                "select 1 from event where position > ${baseline} and \
event_type='PlayableEstablished' limit 1;" \
                2>/dev/null || true)
            if [ -n "${recorded}" ]; then
                playable=1
                break
            fi
            sleep 1
        done
        if [ "${playable}" -eq 1 ]; then
            printf 'domain: %s admitted its first snapshot of that world\n' "${join_username}" >&2
        else
            printf 'domain: %s arrived but never became playable within %ss\n' \
                "${join_username}" "${seconds}" >&2
        fi
    else
        # Asking a client to become playable is a question about the world it admitted, and
        # a client that never got into a server admitted none. Measured on three recorded
        # runs: the arrival branch said the non-arrival, named the downstream readings, and
        # then this window still ran its full length (420s on a JVM that had crashed 32s in,
        # 150s in the auth-mode shape) before printing a sentence that opens by claiming the
        # client had arrived. The host side of this script already refuses to wait for a
        # playability its own run shape cannot produce.
        printf 'domain: %s never arrived, so this run asks it no second %ss window to become playable\n' \
            "${join_username}" "${seconds}" >&2
    fi
    # What the joining client itself reports, read from the overlay this run created
    # rather than from the newest one on disk.
    overlay=""
    for _ in $(seq 1 30); do
        fresh=$(comm -13 <(printf '%s\n' "${before}") \
            <(ls "/data/kin/${joiner}/run/session/" 2>/dev/null | sort) | head -1)
        if [ -n "${fresh}" ]; then
            candidate="/data/kin/${joiner}/run/session/${fresh}/generation-1"
            [ -f "${candidate}/logs/latest.log" ] && { overlay="${candidate}"; break; }
        fi
        sleep 1
    done
    if [ -n "${overlay}" ]; then
        printf 'domain: the joining client reports:\n' >&2
        grep -E "CONNECTION_PHASE_JOIN_SEEN|knows of [0-9]+ entity candidate" \
            "${overlay}/logs/latest.log" 2>/dev/null | tail -3 |
            sed 's/^/domain:   /' >&2 || true
    fi
}

# The logs that exist before this session starts. A host run has to watch the client's
# own log (see the wait below), and the newest log on disk is the one the *last* run
# wrote — which is a mistake this harness has already made once in another form.
logs_before=$(ls /data/kin/*/run/session/*/generation-*/logs/latest.log 2>/dev/null | sort)
lan_args=()
if [ -n "${open_lan}" ]; then
    lan_args=(--open-lan --open-lan-port "${lan_port}")
fi
# Lent to the session supervisor's environment, which is the only route the managed
# client JVM has to a name the host set: Core hands the client nothing it has not
# been given in `config.FORWARDED_VARIABLES`, and this is the one such name whose
# value Core never looks at.
client_env=()
if [ "${refusal_asked}" -eq 1 ]; then
    client_env=(env MINEKIN_BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT="${refuse_first_snapshot}")
fi
# The display belongs to the harness, not to the session. `xvfb-run` starts an X
# server and shuts it down from its own `trap clean_up EXIT`: when the Core — that
# wrapper's command child — is SIGKILLed, the wrapper walks to its end within
# milliseconds and takes the server with it (measured: the client's `stderr.log`
# carried nothing but `X connection to :NN broken`). The input release this window
# reads is written on the client's *next tick*, which cannot arrive once its screen
# is gone. So start the server here, hold it for the whole run, and hand the session
# only `DISPLAY`. The managed client JVM reaches the same screen exactly as before —
# Core forwards `DISPLAY` (`config.FORWARDED_VARIABLES`) to the client — except now
# killing the Core has no route to the server behind it.
#
# The session stays under a plain `sh -c` wrapper, not run directly: the fault helper
# resolves the runtime controller by walking the descendants of the pid this run holds
# (`inject_fault.py`), so the Core must remain one level below `session_pid`. What the
# wrapper ends with is the Core's own status: an earlier form ended in a bare `:`, which
# kept the no-exec property but made the wrapper exit 0 whatever the Core said — an auto
# run refused at a named supply-chain frontier (measured: Core's own rc 17, the refusal
# printed on the run's stderr) left this harness through rc 0, indistinguishable by exit code from a run whose
# client booted and rode out its bound. Statements after `"$@"` are what prevent the
# exec-replacement, and `session_rc=$?; exit` are statements, so the guard survives; the
# capture is the first thing after the Core precisely so nothing else can set `$?`.
# Killing the Core lets this wrapper exit on its own; it holds no server, so
# nothing here shuts the display down.
for display_no in $(seq 77 99); do
    [ -e "/tmp/.X${display_no}-lock" ] || {
        session_display=":${display_no}"
        break
    }
done
if [ -z "${session_display:-}" ]; then
    printf 'domain: no free display in :77-:99 for the harness-owned X server\n' >&2
    exit 2
fi
Xvfb "${session_display}" -screen 0 1280x720x24 >/tmp/domain-xvfb.log 2>&1 &
harness_xvfb_pid=$!
# Wait on the socket rather than a fixed sleep: the session's first connect fails if
# the server has not taken the display yet.
for _ in $(seq 1 100); do
    [ -e "/tmp/.X11-unix/X${display_no}" ] && break
    sleep 0.1
done
if [ ! -e "/tmp/.X11-unix/X${display_no}" ]; then
    printf 'domain: the harness X server never came up on %s\n' "${session_display}" >&2
    exit 2
fi
export DISPLAY="${session_display}"

# The model wiring's own half of this run. `domain/model_access.py` refuses plain http to any
# host but loopback, so the only fake endpoint a live run can be pointed at is one inside this
# container, answering on this container's 127.0.0.1. Unset means no listener is started and no
# call is made — the run keeps reporting `local_reflection`, which is what every other case in
# this harness depends on. Nothing here names a credential: the operator's own variable names
# arrive by name through MINEKIN_RUNNER_FORWARD_ENV, as they always have.
if [ -n "${MINEKIN_DOMAIN_FAKE_MODEL_PORT:-}" ]; then
    if ! [[ "${MINEKIN_DOMAIN_FAKE_MODEL_PORT}" =~ ^[0-9]+$ ]]; then
        printf 'domain: MINEKIN_DOMAIN_FAKE_MODEL_PORT must be one port number: %s\n' \
            "${MINEKIN_DOMAIN_FAKE_MODEL_PORT}" >&2
        exit 2
    fi
    python /src/tools/run_fake_model_endpoint.py "${MINEKIN_DOMAIN_FAKE_MODEL_PORT}" \
        >/tmp/domain-fake-model.log 2>&1 &
    fake_model_pid=$!
    # Wait on the line the server prints after it has the port, not on a fixed sleep: a call
    # that arrives before the bind is a refused connection, and that would read as the provider
    # being broken rather than as the harness starting too fast.
    for _ in $(seq 1 100); do
        grep -q 'serving /chat/completions' /tmp/domain-fake-model.log && break
        kill -0 "${fake_model_pid}" 2>/dev/null || break
        sleep 0.1
    done
    if ! grep -q 'serving /chat/completions' /tmp/domain-fake-model.log; then
        printf 'domain: the fake model endpoint never came up on port %s\n' \
            "${MINEKIN_DOMAIN_FAKE_MODEL_PORT}" >&2
        exit 2
    fi
    printf 'domain: the fake model endpoint is serving on 127.0.0.1:%s for this container\n' \
        "${MINEKIN_DOMAIN_FAKE_MODEL_PORT}"
fi

# Named rather than spelled at the redirect, because the branch that reports this client
# never got there reads the same file back out (see `name_the_session_launch_last_words`),
# and a path copied twice is a path one of the two can drift from.
# --- hungry-kin-preparation begin ---
if [[ -n "${hungry_kin}" ]]; then
    if ! "${client_env[@]}" python /src/tools/prepare_hungry_kin.py \
            --server-directory "${server_directory}" --player "${probe:-${player}}" -- "$@"; then
        printf 'domain: hungry fixture preparation failed; action session was not started\n' >&2
        exit 2
    fi
    # The observation-only preparation has its own overlay. It must not become
    # this action session's evidence or be selected as its fresh client log.
    logs_before=$(ls /data/kin/*/run/session/*/generation-*/logs/latest.log 2>/dev/null | sort)
fi
# --- hungry-kin-preparation end ---
session_error_file=/tmp/domain-session.err
sh -c '"$@"; session_rc=$?; exit "${session_rc}"' minekin-session-supervisor \
    "${client_env[@]}" python -m minekin_core "$@" "${lan_args[@]}" \
    >/tmp/domain-session.json 2>"${session_error_file}" &
session_pid=$!
if ! read -r session_starttime_ticks session_pid_namespace_inode \
        <<<"$(read_process_identity "${session_pid}" 2>/dev/null)" ||
        [ -z "${session_starttime_ticks}" ] || [ -z "${session_pid_namespace_inode}" ]; then
    printf 'domain: the session supervisor identity could not be captured\n' >&2
    exit 2
fi
set -e

# What this run's own launcher wrote while it was failing to become a session. A reading
# on the two branches that report a client that never got there; it changes no criterion,
# no gate and no bundle field, and it cannot end the run it is reporting on.
#
# That file is the only place a launch-time refusal is written, and `run.sh` runs this
# container with `--rm`, so it is gone before anyone outside can open it. Measured on a
# CORE-040 attempt whose Bridge jar had not been built: Core wrote its own named frontier
# refusal there — the category such an unbuilt jar is refused under, and the message
# saying the jar had not been built — while the run's output could only report a generic
# bound, and that reason had to be recovered afterwards from the exited container with
# `docker cp`. A named frontier refusal and a generic bound are
# answered by reading different things, so the branch that says the second one has to
# quote the first. The size travels with the words so a reader can tell a short launch from
# a truncated one; the tail is bounded because a client that boots and then hangs has a
# whole Minecraft log on this file.
name_the_session_launch_last_words() {
    local size
    size=''
    if [ -s "${session_error_file}" ]; then
        size=$(wc -c <"${session_error_file}" 2>/dev/null | tr -d ' \r') || size=''
    fi
    if [ -z "${size}" ]; then
        printf 'domain: the session launcher wrote nothing to %s, so this run has no words to read\n' \
            "${session_error_file}" >&2
        return 0
    fi
    printf "domain: the session launcher's own last words, from %s (%s byte(s)):\n" \
        "${session_error_file}" "${size}" >&2
    tail -n 20 "${session_error_file}" >&2 2>/dev/null || true
    return 0
}

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
# The ledger is where every fact below comes from, so a run may only ever read its
# own. Taking the first of a glob was how one Kin's database could be read as
# another's: `head -1` over several candidates silently picks one, and everything
# downstream — the run id, the fault record's attribution, the seal — would then be
# about a different run. So the number of candidates is checked, and anything other
# than exactly one fails closed rather than guessing.
# A root with several Kin needs one named, and the selector is the same one the CLI
# reads — a scenario with a second Kin in it (the one that joins a hosted world) has
# two ledgers by construction.
kin_selector="${MINEKIN_KIN_ID:-}"
if [ -n "${kin_selector}" ]; then
    ledgers=("/data/kin/${kin_selector}/kin.sqlite3")
else
    ledgers=(/data/kin/*/kin.sqlite3)
fi
if [ "${#ledgers[@]}" -ne 1 ] || [ ! -f "${ledgers[0]}" ]; then
    printf 'domain: this run cannot name its ledger (found %s), so nothing here can be attributed\n' \
        "${#ledgers[@]}" >&2
    exit 2
fi
ledger="${ledgers[0]}"
# The run's own attribution — the Kin, the session and the generation — comes from
# the ledger's *rows* below, once the run id is known, and is empty until then. It
# is deliberately not read from the path the database sits at: the helper compares
# the two, and a ledger filed under one Kin whose rows say another is not evidence
# for either.
kin_id=""
session_id=""
generation=""
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

# The height the server has reported, one per line. A jump is the only thing that
# shows up here and nowhere else: the Kin leaves the ground and comes back, at the
# same place.
reported_heights() {
    { grep -o 'has the following entity data: \[[^]]*\]' \
        "${server_directory}/server.log" 2>/dev/null || true; } |
        sed 's/.*\[//; s/\]//; s/[df]//g' |
        awk -F', *' 'NF == 3 {print $2}'
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
if [ "${case_id}" = "ADMIT-040" ]; then
    # This case is a refusal, not a world-entry test. Only the classified
    # Bridge-filtered fact from this run ends the wait; a generic disconnect
    # would hide the exact regression this case exists to detect.
    if [ "${online_mode}" != "true" ] || [ -z "${server_profile}" ]; then
        printf 'domain: ADMIT-040 requires an online-mode server and an offline Server Profile\n' >&2
        exit 2
    fi
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='SessionInterrupted' and source='BRIDGE' and trust_class='BRIDGE_FILTERED' and json_extract(payload_json,'\$.phase')='FAILED' and json_extract(payload_json,'\$.reason')='ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the session recorded the expected auth mismatch\n' >&2
    else
        printf 'domain: no classified auth mismatch was recorded within %ss\n' "${seconds}" >&2
    fi
elif [ "${case_id}" = "ADMIT-060" ]; then
    # What this run exists to say is one line: the policy the connection was actually
    # made with. The client then sits in the login negotiation — a required pack it
    # will not take is not a refusal anybody announces — so waiting for the world, or
    # for the 45 seconds to run out, would end this run with a timeout on its face and
    # the fact itself unread.
    #
    # Asked for by value rather than by existence, because the value is the whole
    # question: a build that let `resource_pack_policy` fall through to `prompt` would
    # record a row, and the wait would be wrong to call that the run saying what this
    # case asks it to say.
    if [ -z "${resource_pack}" ] || [ -z "${server_profile}" ]; then
        printf 'domain: ADMIT-060 requires a served resource pack and an offline Server Profile\n' >&2
        exit 2
    fi
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='ResourcePackPolicyApplied' and source='BRIDGE' and trust_class='BRIDGE_FILTERED' and json_extract(payload_json,'\$.resource_pack_policy')='deny' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the session recorded the denied resource pack policy it put on the wire\n' >&2
    else
        printf 'domain: no denied resource pack policy was recorded within %ss\n' "${seconds}" >&2
    fi
elif [ "${refusal_asked}" -eq 1 ]; then
    # The wait ends on the join, and the verdict comes later from Core's own record.
    # The client's log line was the first version's oracle here, and it is the wrong
    # kind: a Bridge that said the sentence about a snapshot that never reached IPC
    # satisfied it, and a run whose Core really refused a snapshot could miss it to a
    # log rotation. It was also read by taking `head -1` over *every* Kin's newest
    # log, which is the same mistake this harness has already made once on the ledger
    # — a second client in the container could answer for the first one.
    #
    # What has to happen before anything can be refused is the join, and that is a
    # ledger row: `JoinObserved`. Waiting for it keeps the run's timing honest
    # without making the log load-bearing, and the refusal itself is judged below,
    # once the run document exists.
    deadline=$((SECONDS + seconds))
    refusal_join_seen=0
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='JoinObserved' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            refusal_join_seen=1
            break
        fi
        sleep 1
    done
    if [ "${refusal_join_seen}" -eq 1 ]; then
        printf 'domain: the Kin joined; Core now has a first snapshot to accept or refuse\n' >&2
    else
        # The run asked for something that never got as far as being refused, and it
        # must not exit like one that was: a bare timeout here reads as "Core refused
        # a snapshot", which is a conclusion nobody reached.
        printf 'domain: no join was recorded within %ss, so no first snapshot could be refused\n' "${seconds}" >&2
        injection_failed=1
    fi
elif [ -n "${not_whitelisted}" ]; then
    # What this run is about is a refusal, and the refusal is a ledger fact: the
    # Bridge classifies the login failure and Core records the phase and the
    # reason together. Waiting for a world this run will never join would spend
    # the budget on something that cannot happen.
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='SessionInterrupted' and payload_json like '%FAILED%' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the session was interrupted, as this run expected\n' >&2
    else
        printf 'domain: the session was never interrupted within %ss\n' "${seconds}" >&2
    fi
elif [ -n "${black_hole}" ]; then
    # Two waits, because two things have to happen before this run has anything
    # to say. First the client has to boot and handshake — that takes as long as
    # it takes, and it is the same wait a run with no world uses. Then Core's own
    # deadline has to pass, and that is a duration the operator named on the
    # command line: waiting a little longer than it is deliberate, because the
    # give-up being watched has to happen while the harness is still watching.
    handshake_by=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${handshake_by}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='BridgeHelloAccepted' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the handshake was recorded; the client is about to dial\n' >&2
        answer_by=$((SECONDS + ${connection_timeout:-30} + 15))
        if [ "${answer_by}" -gt $((SECONDS + seconds)) ]; then
            answer_by=$((SECONDS + seconds))
        fi
        while [ "${SECONDS}" -lt "${answer_by}" ]; do
            kill -0 "${session_pid}" 2>/dev/null || break
            sleep 1
        done
    else
        printf 'domain: no handshake was recorded within %ss\n' "${seconds}" >&2
    fi
    if grep -q '"accepted"' /tmp/domain-black-hole.log 2>/dev/null; then
        printf 'domain: the client dialled the black hole and got nothing\n' >&2
    else
        printf 'domain: nothing ever connected to the black hole\n' >&2
    fi
elif [ -n "${open_lan}" ]; then
    # A run that publishes a world waits for the world to be published, and it has to
    # read the *client's* log to do it. That is not a shortcut: publishing is not one of
    # §5's session events, so Core records it on the run document rather than in the
    # ledger, and the run document is printed when the session ends. While the session is
    # running, the client's own log is the only place the fact exists — and the only
    # overlays looked at are the ones that were not there before this run started.
    deadline=$((SECONDS + seconds))
    published=0
    latest=""
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        candidate=$(comm -13 <(printf '%s\n' "${logs_before}") \
            <(ls /data/kin/*/run/session/*/generation-*/logs/latest.log 2>/dev/null | sort) |
            head -1)
        if [ -n "${candidate}" ] &&
            grep -q "Started serving on ${lan_port}" "${candidate}" 2>/dev/null; then
            latest="${candidate}"
            published=1
            break
        fi
        sleep 1
    done
    if [ "${published}" -eq 1 ]; then
        printf 'domain: the world is published on %s (%s)\n' "${lan_port}" "${latest}" >&2
        if [ "${join_ready}" -eq 1 ]; then
            join_the_published_world "${latest}"
        fi
    else
        printf 'domain: nothing was published on %s within %ss\n' "${lan_port}" "${seconds}" >&2
    fi
elif [ "${join_on_controlled_server_asked}" -eq 1 ]; then
    # --- joiner-controlled-server-wait begin (the contract test extracts this region) ---
    # Nothing in this branch reads a client log. The world already exists and already
    # answered: the dedicated server this run started was waited for above on its own
    # `Done (`, so what is still missing is the *joining* client arriving in it, and the
    # dedicated server says that in the same words the LAN shape reads out of its
    # publisher. The oracle here is therefore `${server_directory}/server.log` — this
    # run's own server log, at a path this run made when it numbered its run directory,
    # never a log a reader has to guess the owner of — and it is the same file the
    # `data get entity` answers land in. That identity is the whole point of the card:
    # the server that is asked where the Kin is, and the server that says the Kin
    # arrived, are one server, so "the server saw the joining Kin turn" becomes a
    # reading instead of an inference from a client that believes it moved.
    printf 'domain: the joining client is sent into the controlled server world this run started, %s\n' \
        "${server_directory}/server.log" >&2
    if [ "${join_ready}" -eq 1 ]; then
        join_the_published_world "${server_directory}/server.log"
    else
        printf 'domain: this run asked for its joiner in the controlled server world and prepared no joining client; nothing was sent\n' >&2
    fi
    # --- joiner-controlled-server-wait end ---
elif [ -z "${server_profile}" ]; then
    # A run with no world to join never becomes playable, and waiting for it
    # would spend the whole budget on a state that cannot happen. What it does do
    # is handshake — and that is what waited for here, on Core's own ledger,
    # because the Bridge writes nothing at all to the client's log in a session
    # that never joins (measured).
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='BridgeHelloAccepted' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        sleep 1
    done
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the handshake was recorded by Core\n' >&2
    else
        printf 'domain: no handshake was recorded within %ss\n' "${seconds}" >&2
        name_the_session_launch_last_words
    fi
else
    deadline=$((SECONDS + seconds))
    ended='the bound expired'
    for _ in $(seq 1 "${seconds}"); do
        [ "${SECONDS}" -lt "${deadline}" ] || break
        # The ledger is read before the session is asked whether it is alive, and
        # that order is the point: a session that died is exactly a session whose
        # last ledger rows are the ones worth reading, and asking `kill -0` first
        # reports "never became playable" about a run whose ledger says otherwise.
        recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='PlayableEstablished' limit 1;" \
            2>/dev/null || true)
        if [ -n "${recorded}" ]; then
            playable=1
            break
        fi
        if ! kill -0 "${session_pid}" 2>/dev/null; then
            ended='the session exited first'
            break
        fi
        sleep 1
    done
    # Said out loud either way. A bound that expires quietly turns "the Kin never
    # joined" into "the harness moved on", and the two need different answers: this
    # one has already done it once, on a run whose client took three minutes to
    # boot because the asset materialisation was cold. Which of the two happened
    # is said too, because "it exited" and "it was still starting" are answered by
    # reading different things.
    if [ "${playable}" -eq 1 ]; then
        printf 'domain: the session is playable\n' >&2
    else
        printf 'domain: the session never became playable within %ss (%s)\n' \
            "${seconds}" "${ended}" >&2
        name_the_session_launch_last_words
    fi
fi

# Which run this is, from the ledger rather than from the document: a run whose
# Core is killed never prints one, and the ledger is the record that survives it.
# The first event may be Core's pre-spawn authentication policy fact.
run_id=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
    "select run_id from event where position > ${baseline} order by position limit 1;" \
    2>/dev/null || true)
printf 'domain: this run is %s\n' "${run_id}" >&2

# The Kin, session and generation this run is in, from the same record and read the
# same way. A fault record has to name the run it is about, and both the helper and
# the sealer cross-check that attribution — so a value invented here would be caught
# rather than quietly accepted. A value that cannot be read is left empty (or zero,
# for the generation), which the helper refuses to record: the run still ends with a
# reason rather than a record naming a Kin or a session that never existed.
attribution=$(/opt/sqlite/bin/sqlite3 -separator ' ' "${ledger}" \
    "select coalesce(kin_id,''), coalesce(json_extract(payload_json,'\$.session_id'),''), \
            coalesce(json_extract(payload_json,'\$.generation'),'') \
     from event where run_id='${run_id}' and event_type='SessionProcessStarted' \
     order by position limit 1;" 2>/dev/null || true)
read -r kin_id session_id generation <<<"${attribution}" || true
case "${generation}" in
    ''|*[!0-9]*) generation=0 ;;
esac

# The report request is recorded here — after the attribution, because a record
# naming no run is refused by both the helper and the sealer, and before anything
# ends the client, because the fact it cites is that process's live environment.
# There is nothing to wait for beyond this: a run that could not say it asked is
# not a refusal, it is a harness failure, and it is failed as one.
if [ "${refusal_asked}" -eq 1 ]; then
    if ! record_refusal_request "${session_pid}" "${session_starttime_ticks}" \
            "${session_pid_namespace_inode}"; then
        injection_failed=1
    fi
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
#
# A run that asks for its hold at the join is left out of this entirely, and the
# reason is the case it exists for: the answer is *no*, so there is nothing to
# wait for. Said out loud rather than passed over, because a harness that skipped
# a wait silently is one whose reader cannot tell a walk that did not happen from
# one it stopped looking for.
if [ "${hold_at}" = "join" ]; then
    printf 'domain: this run asks for its hold at the join, so it is refused and there is no walk to wait for\n' >&2
fi
if [[ -n "${probe}" && "${hold_requested}" -eq 1 && -z "${kill_core}" && -z "${kill_server}" && "${hold_at}" != "join" ]]; then
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
        heights=$(reported_heights)
        span=$(printf '%s\n' "${heights}" | sort -n |
            awk 'NR == 1 { lo = $1 } { hi = $1 } END { printf "%.2f", hi - lo }')
        printf 'domain: the server saw the Kin walk and stop; its height moved through %s blocks\n' \
            "${span}" >&2
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

# Core killed outright rather than paused: the sockets really close, and the
# Bridge has to let go without being told anything. Unlike the silence case,
# `session start` dies with it — so this block does its own waiting, and there is
# no run document at the end of the run, which is the honest shape of it: the
# evidence is the client's own log and the server's readings.
if [[ -n "${kill_core}" ]]; then
    deadline=$((SECONDS + seconds))
    killed=0
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        # While the Kin is walking, which this block can see because the walk
        # wait is skipped for exactly this run.
        #
        # `sleep 1`, and not only for politeness: `SECONDS` does not advance
        # while a loop spins through commands that take no time, so a budget
        # measured in `SECONDS` around a body with no `sleep` is not a budget —
        # the whole loop runs in milliseconds and gives up before the first
        # probe reading has been written. Measured: ninety iterations at
        # `SECONDS=32`, every one of them seeing no movement at all, after which
        # the wait below found the Kin stopped — because the hold had expired on
        # its own — and reported a fault injection that never happened.
        if [ "$(horizontal_positions | sort -u | wc -l)" -lt 2 ]; then
            sleep 1
            continue
        fi
        # The runtime is a child of the pid this script holds — the plain `sh -c`
        # supervisor is between them — so it is named by its command line within
        # that subtree rather than by being the wrapper's own exec'd program. The
        # X server is no longer in this subtree at all: the harness holds it, so
        # killing the runtime cannot take the client's display with it.
        if inject_fault "${session_pid}" "runtime_controller" \
                "${session_starttime_ticks}" "${session_pid_namespace_inode}"; then
            killed=1
            printf 'domain: the runtime is gone; the Bridge should let go\n' >&2
        else
            printf 'domain: the runtime was not killed, so this run proves nothing about a lost runtime\n' >&2
            injection_failed=1
        fi
        break
    done
    # A run that was asked to inject a fault and did not inject it proves nothing
    # about a lost runtime, and the wait below would happily report the Kin
    # stopping for the reason it would have stopped anyway. Said out loud, and
    # the run is failed rather than left looking like the others.
    if [ "${killed}" -eq 0 ]; then
        printf 'domain: the Core was never killed, so this run proves nothing about a lost runtime\n' >&2
        injection_failed=1
    fi
    # The release is what this is about, and the server can see its effect two
    # ways: a Kin that stopped walking, or a Kin whose client exited — a socket
    # that closed is not a peer that went quiet, so the Bridge also stops the
    # client, and nothing can be held by a process that is gone. Both are
    # accepted, and which one happened is said out loud.
    stopped=0
    left=0
    deadline=$((SECONDS + seconds))
    if [ "${killed}" -eq 1 ]; then
        for _ in $(seq 1 "${seconds}"); do
            [ "${SECONDS}" -lt "${deadline}" ] || break
            positions=$(horizontal_positions)
            distinct=$(printf '%s\n' "${positions}" | sort -u | wc -l)
            settled=$(printf '%s\n' "${positions}" | tail -n 2 | sort -u | wc -l)
            if grep -q "${player} left the game" "${server_directory}/server.log" 2>/dev/null; then
                left=1
            fi
            if [ "${distinct}" -ge 2 ] && { [ "${settled}" -eq 1 ] || [ "${left}" -eq 1 ]; }; then
                stopped=1
                break
            fi
            sleep 1
        done
    fi
    if [ "${killed}" -eq 0 ]; then
        : # already said, above, along with why the run proves nothing
    elif [ "${stopped}" -eq 0 ]; then
        printf 'domain: the Kin never stopped after the Core was killed\n' >&2
    elif [ "${left}" -eq 1 ]; then
        printf 'domain: the Kin left the game after the Core was killed\n' >&2
    else
        printf 'domain: the server saw the Kin stop after the Core was killed\n' >&2
    fi
fi

# The world killed rather than ended. A kick is the server *saying* goodbye; this
# is the server saying nothing at all, and the client learning of it from a socket
# that stopped working. What the Bridge must do is the same either way — let go of
# what it holds — but the run has to be able to show that the world really died
# rather than stopped: a server that was killed never writes its own shutdown, and
# a server that stopped does.
if [[ -n "${kill_server}" ]]; then
    deadline=$((SECONDS + seconds))
    killed=0
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        # While the Kin is in the world and walking — the same `sleep 1` the other
        # waits need, for the same measured reason: `SECONDS` does not advance
        # while a loop spins through commands that take no time.
        if [ "$(horizontal_positions | sort -u | wc -l)" -lt 2 ]; then
            sleep 1
            continue
        fi
        # The JVM, not the tool that started it. `server_pid` is the tool, and the
        # first version of this killed *that* — which the tool's own signal
        # handling turned into the clean stop it performs on SIGTERM, so the world
        # was saved and rewritten while the harness printed "the world is gone".
        # Measured twice: the server log ended with `All dimensions are saved`, in
        # a run that claimed to have killed it.
        #
        # The JVM is the one `java` process under the tool, and the helper refuses
        # unless that is exactly one process: `pgrep -P <tool> | head -1` named the
        # tool's first child, which is not the same claim.
        if inject_fault "${server_pid}" "server_jvm" \
                "${server_starttime_ticks}" "${server_pid_namespace_inode}"; then
            killed=1
            if grep -q "Stopping the server" "${server_directory}/server.log" 2>/dev/null; then
                # A killed server gets no chance to write its own shutdown, so this
                # line in its log means it stopped rather than died — whatever the
                # signal did. A second opinion on the helper's own confirmation.
                printf 'domain: the server wrote its own shutdown, so it stopped rather than died\n' >&2
                killed=0
            else
                printf 'domain: the server has been killed; the world is gone\n' >&2
            fi
        fi
        break
    done
    if [ "${killed}" -eq 0 ]; then
        # Same rule as the other fault injections: one that did not happen proves
        # nothing, and the run is failed rather than left looking like the rest.
        printf 'domain: the server was never killed, so this run proves nothing about a world that died\n' >&2
        injection_failed=1
    else
        # Core's own record of the world going away. Waited for rather than
        # assumed, because "the session ended" is the fact this run exists to
        # produce and a run that never reaches it has not produced it.
        ended=0
        for _ in $(seq 1 "${seconds}"); do
            [ "${SECONDS}" -lt "${deadline}" ] || break
            recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
                "select 1 from event where position > ${baseline} and event_type='SessionInterrupted' limit 1;" \
                2>/dev/null || true)
            if [ -n "${recorded}" ]; then
                ended=1
                break
            fi
            sleep 1
        done
        if [ "${ended}" -eq 1 ]; then
            printf 'domain: Core recorded the session ending when the world went away\n' >&2
        else
            printf 'domain: the session never recorded an interruption after the server died\n' >&2
        fi
    fi
fi

# The client killed, which is the one boundary where nothing inside the killed
# process can report anything: the Bridge is a mod in that JVM, so the release
# log the other two boundaries read cannot exist here. The target is the JVM the
# runtime started, found from the same root the runtime is found from — both are
# descendants of this script's session pid, and the role's own command line is
# what tells them apart.
if [[ -n "${kill_client}" ]]; then
    deadline=$((SECONDS + seconds))
    killed=0
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        # While the Kin is in the world and walking, and for the same measured
        # reason as the other waits: `SECONDS` does not advance while the loop
        # spins through commands that take no time.
        if [ "$(horizontal_positions | sort -u | wc -l)" -lt 2 ]; then
            sleep 1
            continue
        fi
        if inject_fault "${session_pid}" "client_jvm" \
                "${session_starttime_ticks}" "${session_pid_namespace_inode}"; then
            killed=1
            printf 'domain: the client has been killed; the keys died with the process\n' >&2
        fi
        break
    done
    if [ "${killed}" -eq 0 ]; then
        printf 'domain: the client was never killed, so this run proves nothing about a client that died\n' >&2
        injection_failed=1
    else
        # Which of Core's two records this run produced is measured rather than
        # assumed: the runtime can conclude its client exited, or it can find the
        # transport gone first and call that a lost Bridge. Both are the runtime
        # reacting to a client that is no longer there, and which one happened is
        # what the case is written against — so it is read and said out loud.
        recorded=""
        for _ in $(seq 1 "${seconds}"); do
            [ "${SECONDS}" -lt "${deadline}" ] || break
            recorded=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
                "select event_type from event where position > ${baseline} and event_type in ('ClientProcessExited','SessionInterrupted') order by position limit 1;" \
                2>/dev/null || true)
            if [ -n "${recorded}" ]; then
                break
            fi
            sleep 1
        done
        if [ -n "${recorded}" ]; then
            printf 'domain: Core recorded %s after its client was killed\n' "${recorded}" >&2
        else
            printf 'domain: the runtime recorded nothing after its client was killed\n' >&2
        fi
    fi
fi

# Kicked rather than killed: the server ends the session and the client keeps
# running, which is the trigger §12 calls leaving playable. The kick itself is
# fired by the server tool on its own clock; what is waited for here is the
# server's own account of the session ending.
if [[ -n "${kick}" ]]; then
    kicked=0
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        if grep -qE "${kick} (lost connection|left the game)" \
            "${server_directory}/server.log" 2>/dev/null; then
            kicked=1
            break
        fi
        sleep 1
    done
    if [ "${kicked}" -eq 1 ]; then
        printf 'domain: the server ended the session while the client kept running\n' >&2
    else
        printf 'domain: the server never ended the session within %ss\n' "${seconds}" >&2
    fi
fi

# A run that is checking what a *previous* run left behind: the Kin must not be
# moving. Nothing in the new session asks it to, and nothing the dead one asked
# for may still be in force — which is a fact about the world, so the world is
# where it is read.
if [[ -n "${still}" ]]; then
    # Measured by distance rather than by equality, because the world is not
    # empty: a summoned pig that wanders into the Kin pushes it, and a Kin that
    # was shoved 1.5 blocks in three seconds has not walked anywhere. Walking is
    # 4.3 blocks per second, so the two are two orders of magnitude apart given
    # any sensible probe interval — the threshold is the gap between a shove and
    # a step, not a tuned number.
    walked=0
    moved=0
    readings=0
    deadline=$((SECONDS + seconds))
    for _ in $(seq 1 "${seconds}"); do
        kill -0 "${session_pid}" 2>/dev/null || break
        [ "${SECONDS}" -lt "${deadline}" ] || break
        positions=$(horizontal_positions)
        readings=$(printf '%s\n' "${positions}" | grep -c . || true)
        if [ "${readings}" -ge 2 ]; then
            drift=$(printf '%s\n' "${positions}" |
                awk -F, 'NR == 1 { x = $1; z = $2 } { lx = $1; lz = $2 }
                         END { dx = lx - x; dz = lz - z; printf "%.3f", sqrt(dx * dx + dz * dz) }')
            if awk -v drift="${drift}" 'BEGIN { exit !(drift > 2.0) }'; then
                moved=1
            fi
            break
        fi
        sleep 1
    done
    if [ "${moved}" -eq 1 ]; then
        printf 'domain: the Kin moved %s blocks without being asked to\n' "${drift}" >&2
    elif [ "${readings}" -ge 2 ]; then
        printf 'domain: the Kin moved %s blocks across %s readings and did not walk\n'             "${drift}" "${readings}" >&2
    else
        printf 'domain: the Kin was never seen in the world\n' >&2
    fi
fi

# A bounded soak: the session is left running for a stated length of time, and the
# two processes it is made of are sampled while it runs. What this is for is the
# contract's L6 baseline — sustained operation with resources *reported* rather
# than promised — and it is a run rather than a case because the contract says so
# in as many words: no human baseline exists yet, so nothing here sets a
# threshold, and the numbers are reported as measurements.
#
# Sampled from /proc rather than asked of the JVM. A process asked about its own
# memory is a process reporting its own opinion, and this has to be readable even
# from a client that is too unhealthy to answer.
if [ "${soak_seconds}" -gt 0 ]; then
    : > "${soak_file}"
    if [ -n "${joiner_pid:-}" ]; then : > "${soak_joiner_file}"; fi
    sample() {
        # One line per process per round: the label, the resident size in KB, the
        # thread count and how far into the soak this look happened, all as the
        # kernel holds them. The elapsed second is what makes the sample a
        # *timeline* rather than a bag of numbers: a set of readings with no
        # times cannot say whether they span the interval that was asked for. An
        # explicit fourth argument redirects the line onto another file, which is how
        # the joining client's samples land on their own telemetry rather than the
        # judged carrier; without it they join the soak file like every other label.
        [ -n "$1" ] && [ -r "/proc/$1/status" ] || return 1
        awk -v label="$2" -v elapsed="$3" '/^VmRSS:/ { rss = $2 } /^Threads:/ { threads = $2 }
             END {
                 if (rss == "" || threads == "") exit 1
                 printf "%s %s %s %s\n", label, rss, threads, elapsed
             }' "/proc/$1/status" 2>/dev/null >> "${4:-${soak_file}}"
    }
    # Name the JVM, not a launcher's first child. Both halves can have wrappers,
    # and a JVM may start after the soak begins, so discovery is repeated until
    # each sample rather than turning an early empty lookup into a whole empty
    # baseline.
    find_java_descendant() {
        local root="$1"
        local found=""
        local child
        local candidate
        if [ "$(cat "/proc/${root}/comm" 2>/dev/null || true)" = "java" ]; then
            found="${root}"
        fi
        for child in $(pgrep -P "${root}" 2>/dev/null || true); do
            candidate=$(find_java_descendant "${child}")
            if [ -n "${candidate}" ]; then
                found="${candidate}"
            fi
        done
        printf '%s' "${found}"
    }

    printf 'domain: soaking for %ss at %ss intervals\n' \
        "${soak_seconds}" "${soak_interval}" >&2
    client_samples=0
    server_samples=0
    soak_interrupted=0
    sample_failed=0
    soak_started=${SECONDS}
    deadline=$((SECONDS + soak_seconds))
    while [ "${SECONDS}" -lt "${deadline}" ]; do
        if ! kill -0 "${session_pid}" 2>/dev/null; then
            soak_interrupted=1
            break
        fi
        elapsed=$((SECONDS - soak_started))
        client_process=$(find_java_descendant "${session_pid}")
        world_process=$(find_java_descendant "${server_pid}")
        if sample "${client_process}" client "${elapsed}"; then
            client_samples=$((client_samples + 1))
        else
            sample_failed=1
        fi
        if sample "${world_process}" server "${elapsed}"; then
            server_samples=$((server_samples + 1))
        else
            sample_failed=1
        fi
        # The joining client is read on the same clock as the two judged JVMs but sent
        # to its own file, and folded into neither the client/server counts nor
        # `sample_failed`: it is telemetry, not a gate condition, so a run cannot begin
        # failing because a joiner appeared late or left partway. Under `set -e` the
        # failed sample of a process that has already gone is swallowed by `|| true`.
        if [ -n "${joiner_pid:-}" ]; then
            joiner_process=$(find_java_descendant "${joiner_pid}")
            sample "${joiner_process}" joiner "${elapsed}" "${soak_joiner_file}" || true
        fi
        remaining=$((deadline - SECONDS))
        nap="${soak_interval}"
        if [ "${nap}" -gt "${remaining}" ]; then
            nap="${remaining}"
        fi
        if [ "${nap}" -gt 0 ]; then
            sleep "${nap}"
        fi
    done
    # A process can disappear during the final sleep, after the last sample but
    # before the deadline. It still did not survive the requested baseline.
    final_client_process=$(find_java_descendant "${session_pid}")
    final_world_process=$(find_java_descendant "${server_pid}")
    if ! kill -0 "${session_pid}" 2>/dev/null || \
            [ -z "${final_client_process}" ] || [ -z "${final_world_process}" ]; then
        soak_interrupted=1
    fi
    if [ "${soak_interrupted}" -eq 1 ]; then
        printf 'domain: the session ended before the requested soak duration elapsed\n' >&2
        injection_failed=1
    fi
    if [ "${sample_failed}" -eq 1 ] || \
            [ "${client_samples}" -eq 0 ] || [ "${server_samples}" -eq 0 ]; then
        printf 'domain: the soak did not sample both JVMs on every pass (client=%s, server=%s)\n' \
            "${client_samples}" "${server_samples}" >&2
        injection_failed=1
    fi
    for label in client server; do
        awk -v label="${label}" '
            $1 == label {
                n += 1; rss[n] = $2
                if (n == 1 || $2 < low) low = $2
                if (n == 1 || $2 > high) high = $2
                if ($3 > threads) threads = $3
            }
            END {
                if (n == 0) {
                    printf "domain: %s was never sampled\n", label
                    exit 1
                }
                printf "domain: %s RSS %.0f MB at first, %.0f MB at last, %.0f..%.0f MB over %d samples, %d threads at most\n",
                       label, rss[1] / 1024, rss[n] / 1024, low / 1024, high / 1024, n, threads
            }' "${soak_file}" >&2 || true
    done
    if [ -n "${joiner_pid:-}" ]; then
        # The joining client's resources, reported for the operator and nothing else.
        # This block sets no threshold, never touches `injection_failed`, and reads a
        # different file than the judged one above: it closes the blind spot where a
        # two-client soak watched the host client and the world but said nothing about
        # the JVM that joined them. A joiner that arrived late or left on its own just
        # shows fewer samples here, which the count states instead of hiding.
        awk '
            { n += 1; rss[n] = $2
                if (n == 1 || $2 < low) low = $2
                if (n == 1 || $2 > high) high = $2
                if ($3 > threads) threads = $3
            }
            END {
                if (n == 0) {
                    printf "domain: the joining client was never sampled during the soak\n"
                    exit 0
                }
                printf "domain: joiner RSS %.0f MB at first, %.0f MB at last, %.0f..%.0f MB over %d samples, %d threads at most\n",
                       rss[1] / 1024, rss[n] / 1024, low / 1024, high / 1024, n, threads
            }' "${soak_joiner_file}" >&2 || true
    fi
    # What the harness was asked for and what it did, written where the sealer can
    # read it. The samples above are the measurement; this is the request, and the
    # two are checked against each other rather than one standing in for the other.
    python - "${soak_summary}" "${soak_seconds}" "${soak_interval}" \
        "${client_samples}" "${server_samples}" "${soak_interrupted}" "${sample_failed}" <<'PY'
import json
import sys

path, seconds, interval, client, server, interrupted, failed = sys.argv[1:8]
document = {
    "schema_version": 1,
    "requested_seconds": int(seconds),
    "interval_seconds": int(interval),
    "passes": min(int(client), int(server)),
    "samples": {"client": int(client), "server": int(server)},
    "ended_early": interrupted == "1",
    "failed_samples": failed == "1",
}
with open(path, "w", encoding="utf-8") as stream:
    json.dump(document, stream, sort_keys=True)
    stream.write("\n")
PY
fi

# Before the harness takes the client away, an autonomous run is let to finish its own
# thinking. The mind writes `AutonomousRunHalted` when it reaches a terminal verdict —
# goal met, budget spent, or a stopped world — and stopping before that line SIGTERMs a
# client mid-step (exit 143), which is the release the earlier runs could never confirm.
# Waiting for the verdict means the stop lands on a still-live channel, where the
# cooperative key release runs and reports back. A non-autonomous run never writes the
# event, so a bound of zero — the default — skips this entirely and behaves as before.
if [ "${autonomous_wait_seconds}" -gt 0 ]; then
    deadline=$((SECONDS + autonomous_wait_seconds))
    halted=''
    for _ in $(seq 1 "${autonomous_wait_seconds}"); do
        halted=$(/opt/sqlite/bin/sqlite3 "${ledger}" \
            "select 1 from event where position > ${baseline} and event_type='AutonomousRunHalted' limit 1;" \
            2>/dev/null || true)
        [ -z "${halted}" ] || break
        kill -0 "${session_pid}" 2>/dev/null || break
        sleep 1
    done
    if [ -n "${halted}" ]; then
        printf 'domain: the autonomous loop reached its own verdict; stopping on a live channel\n' >&2
    elif ! kill -0 "${session_pid}" 2>/dev/null; then
        printf 'domain: the session ended before the loop wrote its verdict\n' >&2
        # The Core process's own last words, from the file its stderr was redirected to:
        # a session that died mid-loop leaves its traceback there and nowhere else, and
        # the --rm container takes the file away the moment this script stops asking.
        name_the_session_launch_last_words
    else
        printf 'domain: the loop had not halted within %ss; stopping it\n' \
            "${autonomous_wait_seconds}" >&2
    fi
fi

printf 'domain: stopping the session\n' >&2

# Idempotent, and it identifies the client by its recorded pid and command line
# rather than by name, so a session that has already ended is reported as stopped
# and one that never joined is ended where it stands. Either way the CLI returns
# normally and prints the run document.
#
# Its answer is kept in the log rather than discarded. A stop that did nothing is
# the difference between "the session ended by itself" and "the harness failed to
# end it", and those two look identical from the outside.
# The joining client is stopped first, so the world that hosted it has something to say
# about its leaving: a visitor still connected when the host goes is a different fact
# from one that left.
if [ -n "${joiner_pid:-}" ]; then
    MINEKIN_KIN_ID="${joiner}" python -m minekin_core session stop \
        >/tmp/domain-join-stop.json 2>&1 || true
    for _ in $(seq 1 60); do
        kill -0 "${joiner_pid}" 2>/dev/null || break
        sleep 1
    done
    kill -0 "${joiner_pid}" 2>/dev/null && kill -TERM "${joiner_pid}" 2>/dev/null || true
    wait "${joiner_pid}" 2>/dev/null || true
    printf 'domain: the joining session has stopped\n' >&2
    # What that client's own run document says, printed here because the document is
    # written when its session ends and it lives in this container's /tmp: the harness
    # seals one run per bundle, and which of the two runs a case is about is a
    # question for the case rather than for this script.
    if [ -s /tmp/domain-join-session.json ]; then
        python - /tmp/domain-join-session.json <<'PY' >&2 || true
import json
import sys

document = json.load(open(sys.argv[1], encoding="utf-8"))
run = document["run"]
facts = {
    key: run.get(key)
    for key in ("outcome", "connection_state", "snapshots_admitted", "entities_admitted")
}
print(f"domain: the joining client ended with {facts}")
PY
    fi
fi

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

# What the supervisor the runtime was found under exited with, now that this script
# — which is the one that waited for it — can say. The helper cannot: it is not the
# supervisor's parent, so it has no `waitpid` to read a status from, and its record
# says the status was not observed until this fills it in. The server half is not
# annotated here because its supervisor is still running when the seal happens, and
# a status nobody waited for would be an invented number rather than an absent one.
if [ "${fault_role}" = "runtime_controller" ] && [ -s "${fault_path}" ]; then
    set +e
    python /src/tools/inject_fault.py annotate \
        --record "${fault_path}" \
        --supervisor-pid "${session_pid}" \
        --supervisor-exit-status "${status}" >/tmp/domain-fault-annotate.log 2>&1
    annotated=$?
    set -e
    printf 'domain: the fault record was annotated ' >&2
    tr -d '\n' </tmp/domain-fault-annotate.log >&2 || true
    printf '\n' >&2
    if [ "${annotated}" -ne 0 ]; then
        printf 'domain: the fault record annotation failed, so the run cannot claim complete fault evidence\n' >&2
        injection_failed=1
    fi
fi

# The run document is what Core says it did, and it is the only place Core's own
# verdict on the first snapshot exists. It was captured to a file so that it can
# be judged and sealed; it is printed here so that reading the container's output
# still shows it, which is what the operator had before it was captured.
printf 'domain: the run document said ' >&2
tr -d '\n' </tmp/domain-session.json >&2 || true
printf '\n' >&2

# What a refusal run has to end up saying, judged from the two records the run
# leaves behind rather than from anything the client printed about itself. The
# distinction it exists to make is the one a log line cannot make: a snapshot the
# Bridge handed over and Core refused, versus a run where nothing was refused at
# all. Core's own run document holds the refusal, and the ledger holds whether the
# Kin was ever told it could play.
if [ "${refusal_asked}" -eq 1 ]; then
    set +e
    python - /tmp/domain-session.json "${ledger}" "${baseline}" <<'PY' >&2
import json
import sqlite3
import sys

document_path, ledger_path, baseline = sys.argv[1], sys.argv[2], int(sys.argv[3])
try:
    with open(document_path, encoding="utf-8") as handle:
        document = json.load(handle)
except (OSError, ValueError) as error:
    print(f"domain: the run document cannot be read ({error})")
    raise SystemExit(1)
run = document.get("run")
if not isinstance(run, dict):
    print("domain: the run document has no run section")
    raise SystemExit(1)

problems = []
rejections = run.get("snapshot_rejections")
if not isinstance(rejections, list):
    # Absent or malformed is not "nothing was refused" — it is unreadable, and the
    # difference is what the run's exit code would otherwise paper over.
    problems.append("SNAPSHOT_REJECTIONS_UNREADABLE")
elif "NOT_AUTHORITATIVE" not in rejections:
    problems.append(f"NOT_AUTHORITATIVE_NOT_RECORDED:{rejections}")
admitted = run.get("snapshots_admitted")
if admitted != 0:
    problems.append(f"SNAPSHOTS_ADMITTED:{admitted}")

connection = sqlite3.connect(ledger_path)
try:
    def counted(event_type: str) -> int:
        row = connection.execute(
            "select count(*) from event where position > ? and event_type = ?",
            (baseline, event_type),
        ).fetchone()
        return int(row[0])

    if counted("JoinObserved") == 0:
        problems.append("NO_JOIN_RECORDED")
    if counted("PlayableEstablished") > 0:
        problems.append("PLAYABLEESTABLISHED_WITH_A_REFUSAL")
    if counted("InputLeaseGranted") > 0:
        problems.append("INPUTLEASEGRANTED_WITH_A_REFUSAL")
finally:
    connection.close()

for problem in problems:
    print(f"domain: the first snapshot was not refused as asked ({problem})")
if not problems:
    # Said out loud rather than left as silence: a judgement block that only
    # speaks when it is unhappy cannot be told apart, in a transcript, from a
    # block that never ran.
    print("domain: Core refused this run's first snapshot as asked")
raise SystemExit(1 if problems else 0)
PY
    judged=$?
    set -e
    if [ "${judged}" -ne 0 ]; then
        injection_failed=1
    fi
fi

# Whether a captured stdout file holds Core's own run document.
#
# Having bytes is not the same question, and confusing the two cost a run: the
# session is launched inside `xvfb-run`, whose own last command is `"$@" 2>&1`, so
# when this harness kills the runtime controller — that wrapper's child — the death
# notice arrives on the stream the document is captured from and leaves seven bytes
# that say nothing about what Core did. Handing such a file to the sealer as a
# document makes it refuse the whole run, and a killed Core is exactly the run whose
# absence of a document is the point. An unparseable file is therefore reported as
# *no document*, which is the branch `--run-id` below was written for.
holds_run_document() {
    python - "$1" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        document = json.loads(handle.read())
except (OSError, ValueError):
    raise SystemExit(1)
raise SystemExit(0 if isinstance(document, dict) else 1)
PY
}

# Sealing, which is what makes this a case run rather than a run.
#
# The leave has to be in the server's log before the case can be judged, and the
# server writes it a moment after the client's socket goes: waited for rather
# than assumed, because a seal that fails on a race would report the run as
# unproven. Bounded, and the seal happens either way — a run the server never saw
# leave is a fact the verdict should carry, not a reason to stop.
if [[ -n "${case_id}" ]]; then
    world_args=()
    if [ -n "${server_profile}" ]; then
        # The leave has to be in the server's log before the case can be judged,
        # and the server writes it a moment after the client's socket goes:
        # waited for rather than assumed, because a seal that failed on a race
        # would report the run as unproven. Bounded, and the seal happens either
        # way — a run the server never saw leave is a fact the verdict should
        # carry, not a reason to stop.
        if [ -z "${black_hole}" ]; then
            # A run that ended against a real server waits for that server's own
            # account of leaving. A black hole never had anything to say, and
            # waiting thirty seconds for a sentence it cannot write is thirty
            # seconds this scenario would spend proving nothing.
            for _ in $(seq 1 30); do
                if grep -q "${player} left the game" "${server_directory}/server.log" 2>/dev/null; then
                    break
                fi
                sleep 1
            done
        fi
        world_args=(--server-profile "${server_profile}"
            --server-directory "${server_directory}")
        if [ -z "${black_hole}" ]; then
            # A black hole is not a server: there is no jar behind it, and naming
            # one that was never mounted would be a claim about bytes that were
            # never there.
            world_args+=(--server-jar /server/server.jar)
        fi
    fi

    # The renderer is measured rather than assumed, and it is measured under the
    # same wrapper the session ran under: this is the software rasteriser the
    # container actually has, not the one its documentation mentions.
    renderer="unmeasured"
    if command -v glxinfo >/dev/null 2>&1; then
        measured=$(xvfb-run -a --server-args="-screen 0 1280x720x24" glxinfo -B 2>/dev/null |
            sed -n 's/^OpenGL renderer string: //p' | head -1 || true)
        if [ -n "${measured}" ]; then
            renderer="${measured}"
        fi
    fi

    printf 'domain: sealing run evidence for case %s\n' "${case_id}" >&2
    set +e
    # Named by the document Core printed, or by its run id when there is none —
    # which is exactly the killed-Core case, where the absence is the point.
    subject_document=/tmp/domain-session.json
    subject_username="${player}"
    world_run_args=()
    if [ "${case_on}" = "joiner" ]; then
        # The case is about the client that joined, so its document is the run's own
        # record — and the world it joined is named by the run that hosted it, which is
        # the only place a hosted world's identity was measured. A joining client has no
        # snapshot of its own to report.
        if [ "${join_ready}" -ne 1 ]; then
            printf 'domain: this case is about a joining run, and this run had no joiner\n' >&2
            exit 2
        fi
        subject_document=/tmp/domain-join-session.json
        subject_username="${join_username}"
        # --- joiner-server-log-seal-forge begin (the contract test extracts this region) ---
        # Two inputs can name the joiner's world and only one of them is ever right, so
        # both are built inside this one region, where the guard at the bottom can read the
        # argv it produced.
        #
        # Closed (the default): a joining client has no snapshot of its own, so the world it
        # joined is named by the run that hosted it — the host's run document is the only
        # place a hosted world's identity was measured — and this run's own server inputs
        # stay dropped.
        world_run_args=(--world-run-document /tmp/domain-session.json)
        world_args=()
        # Open: the dedicated server answering this joiner's probes is the one *this* run
        # started, so the world it stood in is named by that server's own profile — the
        # configuration it booted, `kind: dedicated` on the sealer's route 3 — together with
        # its directory, which carries the seed and the `server.log`. The profile names that
        # world outright, so the host document is dropped rather than handed: keeping both
        # would be two mutually exclusive sources for the one world block, and the guard
        # below refuses that pairing. The jar is still not handed over — this branch mounts
        # none — while `server.log`, `usercache.json` and `server.properties` are collected
        # from the directory this run's own server wrote.
        if [ "${seal_joiner_server_log_asked}" -eq 1 ]; then
            world_args=(--server-profile "${server_profile}"
                --server-directory "${server_directory}")
            world_run_args=()
        fi
        # Named refusal, read off the argv this region just built. `--world-run-document`
        # and `--server-profile` together describe the same world block from two sources
        # that cannot both be true — the host document of a world this run did not record,
        # and this run's own dedicated-server profile — so the seal could not be told which
        # world the joiner stood in. It is refused here, before the sealer is invoked at the
        # foot of this block, so nothing has reached `/tmp/domain-seal.json`,
        # `/tmp/domain-seal.err` or the bundle directory by the time this exits.
        has_world_document=0
        has_server_profile=0
        case " ${world_run_args[*]} " in *" --world-run-document "*) has_world_document=1 ;; esac
        case " ${world_args[*]} " in *" --server-profile "*) has_server_profile=1 ;; esac
        if [ "${has_world_document}" -eq 1 ] && [ "${has_server_profile}" -eq 1 ]; then
            printf 'domain: the joining run'"'"'s seal was handed both --world-run-document and --server-profile; those name the same world block from two sources that cannot both be true -- the host document of a world this run did not record, and this run'"'"'s own dedicated-server profile -- so the seal cannot be told which world the joiner stood in; refused here, before the sealer runs and writes anything\n' >&2
            exit 2
        fi
        # --- joiner-server-log-seal-forge end ---
    fi
    named_run=(--run-document "${subject_document}")
    if ! holds_run_document "${subject_document}"; then
        # Said out loud, because a bundle sealed from a run with no document has to be
        # tellable in the transcript from a seal that quietly stopped looking for one.
        printf 'domain: %s holds no run document, so this run is named by its ledger id\n' \
            "${subject_document}" >&2
        # And the Kin that holds that ledger travels with it, from the same rows the
        # fault attribution is read by. The sealer's other way of answering this is to
        # count the Kins on the data root and accept the answer when exactly one holds
        # a database — true while this volume had one Kin, and a guess ever since the
        # join scenarios left a second one. A name read here is measured; a name
        # counted there is not, and the two are not tellable apart in a bundle.
        named_run=(--run-id "${run_id}" --kin-id "${kin_id}")
        if [ -z "${kin_id}" ]; then
            printf 'domain: this run has no Kin in its own rows, so the seal cannot be told which one it is\n' >&2
            named_run=(--run-id "${run_id}")
        fi
    fi
    # The sealer's --profile is required and names the bundle profile the session
    # launched from. A manual run was handed one on its own command line, and this
    # seals exactly that file. An auto-bundle run launched from exactly one recipe
    # too — but which one the resolution picked is said in only one place, the run
    # document Core printed, at `auto_bundle.recipe_path`. Guessing it here (the
    # registry, the first reviewed entry, or the empty string the argv scan carries
    # for an auto run) would seal a launch plan that never ran; the defect this
    # branch had was passing that empty string and watching the sealer refuse. A
    # document that says nothing is therefore reported unsealed, by name.
    seal_profile_args=(--profile "${profile}")
    seal_blocked=0
    if [[ -n "${auto_bundle}" ]]; then
        resolved_recipe="$(
            python - "${subject_document}" <<'PY' 2>/dev/null || true
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        document = json.loads(handle.read())
except (OSError, ValueError):
    raise SystemExit(0)
if not isinstance(document, dict):
    raise SystemExit(0)
decision = document.get("auto_bundle")
if isinstance(decision, dict):
    recipe = decision.get("recipe_path")
    if isinstance(recipe, str) and recipe:
        print(recipe)
PY
        )"
        if [[ -n "${resolved_recipe}" && -f "${resolved_recipe}" ]]; then
            seal_profile_args=(--profile "${resolved_recipe}")
            printf 'domain: this is an auto-bundle run; the seal names the recipe the run resolved to: %s\n' \
                "${resolved_recipe}" >&2
        else
            printf 'domain: this is an auto-bundle run and %s names no readable recipe it resolved to; the run is reported unsealed rather than sealed against a guessed profile\n' \
                "${subject_document}" >&2
            seal_blocked=1
        fi
    fi
    # The record of the fault this run injected, when it injected one. It is named
    # by its path and read once by the sealer, which seals the same bytes it judged.
    #
    # A report request travels through the same channel and the same artifact name,
    # because it is the same kind of fact — what the harness did to this run — and
    # the guard above makes sure only one of the two can be here at a time. It is
    # sealed as its own bytes: the sealer validates the record it is about to seal,
    # so a PASS bundle cannot be read as "Core refused a snapshot the client only
    # claimed to have sent" once the request is in it.
    fault_args=()
    if [ -s "${fault_path}" ]; then
        fault_args=(--fault-injection "${fault_path}")
    elif [ -s "${request_path}" ]; then
        fault_args=(--fault-injection "${request_path}")
    fi
    # The soak's own measurement and the request it answers, when this run soaked.
    # Same rule as the fault record: named by path, read once, and the bytes that
    # were judged are the bytes that are sealed.
    soak_args=()
    if [ -s "${soak_summary}" ]; then
        soak_args=(--soak-samples "${soak_file}" --soak-summary "${soak_summary}")
    fi
    sealed=2
    if [ "${seal_blocked}" -eq 1 ]; then
        # Not a sealer that fell over: one that was deliberately not called,
        # because the profile it requires could not be named from this run's own
        # document. Said through the same channel the sealer's stderr uses, so
        # the transcript tells "unsealed, and why" apart from "judged".
        : > /tmp/domain-seal.json
        printf 'the auto-bundle run resolved to no recipe this harness can name from its run document; no seal was attempted\n' \
            >/tmp/domain-seal.err
    else
        python /src/tools/seal_run_evidence.py \
            --data-root /data \
            --case "${case_file}" \
            "${seal_profile_args[@]}" \
            "${world_args[@]}" \
            "${named_run[@]}" \
            "${world_run_args[@]}" \
            "${seal_probed_player_args[@]}" \
            "${fault_args[@]}" \
            "${soak_args[@]}" \
            --username "${subject_username}" \
            --renderer-display "${renderer}" \
            --session-argv "$@" >/tmp/domain-seal.json 2>/tmp/domain-seal.err
        sealed=$?
    fi
    set -e
    if [ "${sealed}" -eq 2 ] || [ ! -s /tmp/domain-seal.json ]; then
        # A sealer that said nothing and exited zero-ish did not seal: the codes
        # are 0 for held, 1 for sealed-and-failed, 2 for could-not-seal, and an
        # empty report is none of those. Printing its stderr either way is the
        # difference between "the case failed" and "the tool fell over".
        printf 'domain: the run could not be sealed (exit %s): ' "${sealed}" >&2
        tr -d '\n' </tmp/domain-seal.err >&2 || true
        printf '\n' >&2
        status=1
    else
        tr -d '\n' </tmp/domain-seal.json >&2 || true
        printf '\n' >&2
        verdict=$(python -c 'import json;print(json.load(open("/tmp/domain-seal.json"))["result"])' 2>/dev/null || true)
        run_id=$(python -c 'import json;print(json.load(open("/tmp/domain-seal.json"))["run_id"])' 2>/dev/null || true)
        printf 'domain: the case verdict is %s\n' "${verdict}" >&2

        # And the bundle is read back through the command that exists to read it,
        # so what this prints is the answer an operator would get later rather
        # than a restatement of what the sealer just did.
        set +e
        python -m minekin_core evidence verify "${run_id}" >/tmp/domain-verify.json 2>&1
        verified=$?
        set -e
        printf 'domain: evidence verify said ' >&2
        tr -d '\n' </tmp/domain-verify.json >&2 || true
        printf '\n' >&2
        if [ "${verified}" -ne 0 ]; then
            printf 'domain: the sealed bundle does not verify\n' >&2
            status=1
        fi
        if [ "${verdict}" != "PASS" ]; then
            printf 'domain: case %s did not hold for this run\n' "${case_id}" >&2
            status=1
        elif [ "${verified}" -eq 0 ]; then
            # A case run's exit status is the case's answer rather than the
            # session's, because that is the question that was asked. The
            # session's own status is 14 here and always has been: the harness
            # ends a session by terminating the client, so Core records
            # `BRIDGE_LOST`, which maps to IPC_PROTOCOL. Printing it and exiting
            # on it are two different things, and only one of them is useful.
            status=0
        fi
    fi
fi

if [ "${injection_failed}" -eq 1 ]; then
    status=1
fi
exit "${status}"
