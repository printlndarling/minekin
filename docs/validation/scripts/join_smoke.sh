#!/usr/bin/env bash
#
# V1201-PARTIAL-STORE-AND-JOIN-SMOKE-001 — local current-build JOIN smoke.
#
# Runs entirely on this lane's own data volume and its own directly-launched
# offline 1.20.1 server. It does NOT use the harness's run_controlled_server.py
# (which hard-writes enable-status=false, gap G2) — the vanilla 1.20.1 jar
# defaults enable-status to true, so this lane can observe its own server's
# status on loopback and drive the real `session start --auto-bundle` path
# (probe -> auto-select -> digest gate -> provision -> launch -> JOIN -> exit).
#
# STAGES (STAGE env):
#   probe    Start the server, prove the read-only `server probe` observes it.
#   gate     init a Kin, run `session start --auto-bundle` with NO --max-bytes:
#            must clear probe+resolve+digest-gate, then refuse to silently
#            download the store (BUDGET_UNDECLARED). This is the safe default.
#   dryrun   `bundle install --dry-run` to report the fill job (incl. whether the
#            bridge artifact is network-fetchable or must be built and installed).
#   full     Provision under --max-bytes and attempt a real JOIN: poll `session
#            status` for PLAYABLE, then `session stop` for a safe exit. Long.
#
# Usage (host):
#   STAGE=gate JAR=/abs/mc-1.20.1-server.jar \
#     bash test-orchestrator/... no — this is a V-lane script; run via:
#   docker run --rm -v <worktree>:/src:ro -v <this>... see docs/validation report.
set -uo pipefail

JAR="${JAR:?set JAR to the pinned 1.20.1 server jar host path mounted at /server/server.jar}"
PROFILE="${PROFILE:-/src/tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json}"
REGISTRY="${REGISTRY:-/src/tests/fixtures/registry/reviewed-tested-bundles.json}"
BUNDLE_ID="${BUNDLE_ID:-1.20.1-linux-x86_64-offline-java21}"
KIN="${KIN:-kin-v1smoke}"
STAGE="${STAGE:-gate}"
MAXBYTES="${MAXBYTES:-4000000000}"

export MINEKIN_HOME=/data PYTHONPATH=/src/src LD_LIBRARY_PATH=/opt/sqlite/lib

RUNDIR=/data/v1-server-run
LOG=/data/v1-server.log
mkdir -p "$RUNDIR"
cd "$RUNDIR"
[ -f eula.txt ] || printf 'eula=true\n' > eula.txt
# enable-status is left at the vanilla default (true) on purpose — that is the
# whole point of not using run_controlled_server.py here.
cat > server.properties <<PROP
online-mode=false
server-port=25566
motd=v1201-smoke
max-players=4
view-distance=4
simulation-distance=4
generate-structures=false
PROP

echo "== starting offline 1.20.1 server (enable-status default=true) =="
java -Xms512m -Xmx1024m -jar "$JAR" nogui >"$LOG" 2>&1 &
SRV=$!
trap 'kill "$SRV" 2>/dev/null || true' EXIT

echo "== STATUS step: poll read-only server probe =="
PROBED=0
for i in $(seq 1 90); do
  if python -m minekin_core server probe --server-profile "$PROFILE" >/data/v1-probe.json 2>/data/v1-probe.err; then
    if grep -qi '"outcome": *"observed"' /data/v1-probe.json 2>/dev/null; then PROBED=1; echo "probe OBSERVED after ${i}s"; break; fi
  fi
  sleep 1
done
echo "---- probe stdout ----"; cat /data/v1-probe.json 2>/dev/null
echo "---- probe stderr ----"; cat /data/v1-probe.err 2>/dev/null
echo "PROBED=$PROBED"
[ "$STAGE" = probe ] && { echo "== STAGE=probe done =="; exit 0; }

echo "== init Kin $KIN =="
python -m minekin_core init --kin-id "$KIN" 2>&1 | tail -3

if [ "$STAGE" = dryrun ]; then
  echo "== DRYRUN step: bundle install --dry-run =="
  python -m minekin_core bundle install --registry "$REGISTRY" --bundle-id "$BUNDLE_ID" \
    --max-bytes "$MAXBYTES" --dry-run 2>&1 | tail -40
  exit 0
fi

echo "== AUTO-SELECT -> gate: session start --auto-bundle (no --max-bytes) =="
python -m minekin_core session start --auto-bundle "$REGISTRY" --server-profile "$PROFILE"
GATE_RC=$?
echo "gate session-start rc=$GATE_RC"

if [ "$STAGE" != full ]; then
  echo "== STAGE=gate done (refusal expected before any download) =="
  exit 0
fi

echo "== FULL step: session start --auto-bundle --max-bytes $MAXBYTES =="
python -m minekin_core session start --auto-bundle "$REGISTRY" --server-profile "$PROFILE" \
  --max-bytes "$MAXBYTES" --connection-timeout-seconds 180
FULL_RC=$?
echo "full session-start rc=$FULL_RC"
echo "== PLAYABLE poll =="
for i in $(seq 1 60); do
  python -m minekin_core session status >/data/v1-status.json 2>&1
  if grep -qi 'PLAYABLE' /data/v1-status.json; then echo "PLAYABLE after ${i} polls"; break; fi
  sleep 2
done
cat /data/v1-status.json
echo "== safe exit =="
python -m minekin_core session stop 2>&1 | tail -5
echo "DONE full rc=$FULL_RC"
