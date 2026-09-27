# V3-1201-JOIN-LIVE-READOUT-AFTER-H1F — whole-run server+joiner live readout (1.20.1, new bytes)

- **Card (registered scope):** `V3-1201-JOIN-LIVE-READOUT-AFTER-H1F`
- **Lane / branch:** `codex/minekin-v3-1201-join-live-readout` (V lane)
- **Base SHA:** `5dbcc8a23821aa8c2840aa02f57b9e87f2264753` — contains the trunk merge `2ef64a8` (H1f "hands the joining client the version this run launched").
- **Bytes under test (load-bearing, verified identical):** `test-orchestrator/runner/domain.sh`
  - Real repo at base `5dbcc8a`: `f8624ac6713301460288b439ac9644a0b4b1026e218e19f107c9678758ffe0c5`
  - `.tmp/v3/src` copy used by every new-bytes run (d1/d3/d4/d5/d6): `f8624ac6713301460288b439ac9644a0b4b1026e218e19f107c9678758ffe0c5` (**match**)
  - `.tmp/v3/src-base` pre-H1f copy used by the reversal run (d2): `9883a788f5f39008b208998d2b3833e9ea6ad511bfd35f9b63693daf1b9671a0`
  - H1f site now reads `"minecraft_version": version` from `launched_version` with `exit 2` when the run holds no version (comment at `domain.sh:728-744` names the retired literal `"minecraft_version": "1.21.4"`).
- **Status of this card:** **PARTIAL — DELIVERED**. All four readings have byte-level evidence on disk. A successful, sealed JOIN end-to-end (client playable in-world) is **NOT** shown and is named as the single remaining gap.
- **Predecessor note:** this card was resumed with zero commits but a full measurement set on disk in `.tmp/v3/`. No card was re-designed; the four readings were read from those bytes, the reversal/control were confirmed on disk, and every load-bearing claim below is tied to a specific file the V lane opened. The predecessor's d6 empty-store run was **finished at the readout level** (its outcome is fully recorded below) rather than re-driven; a fresh 420s JOIN re-run does not change any reading that already has on-disk bytes.

---

## Drive commands (verbatim, for 主控 replay)

All runs are `docker run --rm` against image `minekin-runner:local`, host Git Bash with `export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"`. `/src` is a read-only tree bind, `/data` is a **V-private** volume (never `minekin-runner-data`), `/out` is a V-private bind so the `--rm` container's `/tmp` materials survive. The `00-header.txt` / `90-readouts.txt` are produced by `.tmp/v3/drive.sh` (gitignored).

- **d1 — main LIVE JOIN, new bytes, populated V volume `minekin-v3-join`, 420s window:**
  ```
  docker run --rm --entrypoint /bin/bash -w /src \
    -v .../minekin-wt-v3/.tmp/v3/src:/src:ro \
    -v minekin-v3-join:/data \
    -v .../minekin-wt-v3/.tmp/v3:/out:rw \
    -e MINEKIN_HOME=/data -e MINEKIN_USERNAME=Kin -e MINEKIN_KIN_ID=kin-v3-host \
    -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
    -e MINEKIN_DOMAIN_JOIN=kin-v3-join -e MINEKIN_DOMAIN_JOIN_USERNAME=Kin2 \
    -e MINEKIN_DOMAIN_OPEN_LAN=1 -e MINEKIN_DOMAIN_LAN_PORT=25570 -e MINEKIN_DOMAIN_SECONDS=420 \
    -e V3_OUT=/out/d1-live -e V3_SHAPE=d1-live-shipped \
    minekin-runner:local -lc 'bash /out/drive.sh "$@"' minekin-v3 \
    "session start --profile /src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json --world-save /src/tests/fixtures/saves/kinworld --world-name kinworld"
  ```
- **d2 — REVERSAL, pre-H1f base bytes `9883a78`, same 1.20.1-shaped run** (only `/src` tree swapped to `.tmp/v3/src-base`): same argv, `V3_OUT=/out/d2-base-bytes`.
- **d3 — POSITIVE CONTROL, new bytes + no-version bundle** (`--profile /out/no-version-bundle.json`).
- **d4 — CONTROL, new bytes, REAL repo tree mounted with no built bridge jar** (`-v .../minekin-wt-v3:/src:ro`, no `/src/bridge-1201/build/libs/`): same 1.20.1 profile argv, 90s.
- **d5 — BRIDGE/BUDGET FRONTIER, empty store `minekin-v3-empty`, auto-bundle shape:**
  ```
  ... -e MINEKIN_DOMAIN_JOIN= ... -v .../mc-1.20.1-server.jar:/server/server.jar:ro ... \
    "session start --auto-bundle /src/tests/fixtures/registry/reviewed-tested-bundles.json --server-profile /src/tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json"
  ```
- **d6 — JOIN-shape on the empty store, 60s** (`V3_JOINER=kin-v3-d6j`, `--profile bundle-candidate-1.20.1.json`).

---

## Reading ① — joiner profile version follows this run (H1f)

**PASS.** The joiner profile JSON each run actually wrote carries the version of the world it dialed.

- d1 (new bytes, 1.20.1 run) `/tmp/domain-join-profile.json`, quoted verbatim:
  ```
  "minecraft_version": "1.20.1",
  ```
  drive.sh readout: `V3:   minecraft_version = 1.20.1`
- d4 (new bytes mounted from the **real repo tree**, no built bridge jar) wrote the same: `"minecraft_version": "1.20.1"` — so ① holds on the actual base-`5dbcc8a` bytes, not only on a copy.
- A **1.20.1-shaped run yields a 1.20.1 joiner profile.** The retired hardcoded `1.21.4` no longer appears in any new-bytes profile.

## Reading ② — the ⑤ family (`GLFW error [0x1000E] Failed to detect any supported platform`, `error: XDG_RUNTIME_DIR is invalid or not set in the environment`): reproduced or excluded

**EXCLUDED — but the exclusion is BOUNDED (see blocker B1).** Not reproduced.

- Across d1/d2/d3/d4/d5/d6 the drive.sh grep `grep -rn "0x1000E" /data /tmp` returns `(none)`.
- The joiner client stderr `/tmp/domain-client-environment.err` is **0 bytes** (opened: `d1-live/tmp/domain-client-environment.err`, size 0). It contains **neither** `GLFW error [0x1000E] ...` **nor** `XDG_RUNTIME_DIR is invalid or not set in the environment`.
- The only `XDG_RUNTIME_DIR` hits are the harness's own probe source `/tmp/domain-client-environment-probe.sh:31,42` (script text, not a client error). The client launch env is healthy: `launch XDG_RUNTIME_DIR=/tmp/minekin-client-runtime/runtime.03hzcE`, `launch XDG_RUNTIME_DIR_ORIGIN=provided-by-harness`, `launch GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits)`, `launch DISPLAY=:99` (see `d1-live/client-environment.txt`).

**Why the exclusion is bounded:** the 1.20.1 joiner never reached the GLFW/JVM-graphics stage, so the ⑤ family could not *manifest* here — but neither did we observe a fully launched 1.20.1 client to rule the family out in the general case. The joiner stalls one gate *earlier*, at profile ADMISSION (d1 `domain-join-session.json`, verbatim):
```
{"category": "ADMISSION", "component": "launcher.profile", ... "message": "server profile minecraft_version is outside the pinned bundle", "operation": "load", "retryability": "OPERATOR_ACTION"}
```
This is the **post-H1f consequence**: now that the profile honestly says `1.20.1`, the launcher's pinned-bundle admission rejects it. Under pre-H1f bytes the same gate fired but blaming the mismatch (d2 `domain-join-session.json`: `"the session launches Minecraft 1.20.1, the profile pins 1.21.4"`). **Owner: `launcher.profile` pinned-bundle admission / the registry's pinned bundle (E / 主控 surface) — not V's to edit.** Recorded, not fixed.

## Reading ③ — bridge 取料 and budget frontier, raw readout

**PASS.** The named 1.20.1 supply-chain frontier is hit verbatim on the empty-store auto-bundle shape.

- d5 `/tmp/domain-session.err` (size 367), quoted verbatim:
  ```
  {"category": "SUPPLY_CHAIN", "component": "cli.auto_session", ... "message": "3639 of 3639 artifacts are missing and would cost 738432269 bytes; pass --max-bytes deliberately rather than let a session start download them by accident [BUDGET_UNDECLARED]", "operation": "session start --auto-bundle", "retryability": "OPERATOR_ACTION"}
  ```
  → **3639 files / 738,432,269 bytes, `BUDGET_UNDECLARED`.** This matches the card's named frontier exactly (1.20.1 shape; deliberately distinct from 1.21.4's 4120 / 523,788,383).
- d4 (profile shape, real repo tree, bridge jar not built) shows the *other* supply-chain refusal instead, verbatim from `/tmp/domain-session.err` (size 326):
  ```
  {"category": "SUPPLY_CHAIN", "component": "launcher.recipe", ... "message": "the Bridge jar has not been built: /src/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar is missing; run `./gradlew build` in the bridge-1201 directory", ...}
  ```
- On the populated volume (d1/d2, bridge jar present, world already fetched) neither budget nor bridge-jar lines fire; the run instead ends `outcome": "BRIDGE_LOST"` / `rc=14` (window closed on the client half), consistent with ②'s admission stall.

## Reading ④ — non-vacuity + positive control

**PASS.**

- **Reversal (turns the ① reading red on the single load-bearing input):** d1 (H1f bytes `f8624ac`) → profile `minecraft_version = "1.20.1"`; d2 (pre-H1f base bytes `9883a78`, everything else identical) → profile `minecraft_version = "1.21.4"` (the retired literal). Removing H1f flips the reading from run-following to constant → the reading tracks exactly the one input H1f governs, it is not vacuous.
- **Positive control (proves the reading is not constant-green):** d3 feeds a bundle with **no version** (`/out/no-version-bundle.json` = `{"schema_version":1,"profile_id":"v3-no-version-positive-control"}`). H1f then **refuses to invent one**, verbatim:
  ```
  domain: the joining client must carry the version this run launched, and this run launched none it could name; refusing to write a joiner profile at a guessed version
  ```
  rc=2, `/tmp/domain-join-profile.json WAS NOT WRITTEN`. This proves the writer is genuinely reading the run's version rather than emitting a fixed string — with no version to read it produces *nothing*, not a green-looking constant.
- **Second control (supply chain is live, not frozen green):** d4 removes the built bridge jar and the reading correctly goes red with the `launcher.recipe` "Bridge jar has not been built" refusal above.

---

## d6 outcome (empty-store JOIN shape) — recorded as measured

**N/A for ① / ②** (never reached the profile writer). d6 stalls before the join-profile block because an empty content-addressed store has no host artifact-store to hand the joiner. Verbatim from `d6-join-empty.log`:
```
cp: cannot stat '/data/kin/kin-v3-d6/run/artifact-store': No such file or directory
domain: could not give the joining Kin an artifact store
V3: domain.sh rc=2
```
This is a valid empty-store bootstrap refusal, not a H1f regression; the successful JOIN-shaped ① readout is carried by d1 and d4 instead.

---

## 未测 / BLOCKED

- **B1 — sealed JOIN end-to-end (client playable in-world) NOT shown.** BLOCKED_HARNESS / owner=`launcher.profile`. After H1f the joiner profile honestly carries `1.20.1`, but the launcher's pinned-bundle admission rejects it (`"server profile minecraft_version is outside the pinned bundle"`), so the 1.20.1 joiner JVM never launches and in-world play cannot be observed. Unblocking: 主控/E decide whether the pinned bundle for the joiner should admit `1.20.1` for this run (a registry/admission-surface change — outside V's readout boundary). Until then ②'s exclusion stays bounded: the ⑤ family is *not present in these bytes* but was *not* tested against a launched 1.20.1 client either.
- **B2 — no fresh 420s JOIN re-run driven this session.** Time-discipline decision, not a failure: readings ①②③④ already have on-disk bytes and re-driving them would not change the readings. If 主控 wants an independently fresh JOIN trace, replay the d1 command verbatim.
- **Sealing:** the readout is **not** sealable by V. If 主控 judges any reading sealable, that is E's job under schema `minekin.p0.evidence.v1`; **V does not seal.** Handed to 主控.

## Local gates (run on host Git Bash, cwd = worktree at base `5dbcc8a`, `PYTHONPATH=$PWD/src`)

| Gate | Command | rc |
|---|---|---|
| ruff check | `ruff check .` | **127 — not run** (`ruff: command not found`; also absent as `python -m ruff` on host and inside `minekin-runner:local`) |
| ruff format | `ruff format --check .` | **127 — not run** (same: ruff not installed on host PATH, host python, or in the image) |
| fixture digests | `python tools/verify_fixture_digests.py` | **0** — `W00 schema and fixture digests: OK` |
| case assertions | `python tools/check_case_assertions.py` | **0** — `Case assertion implementations: OK (150 registered)` |
| boundaries | `python tools/check_boundaries.py` | **0** — `Minekin package dependency boundaries: OK` |
| diff hygiene | `git diff --check` | **0** |

ruff is genuinely unavailable in this environment; recorded as `not run` rather than as passing.

## Four-state split

- **已合入 main / in base:** `5dbcc8a` and its ancestor `2ef64a8` (H1f) are in this branch's base; `domain.sh = f8624ac` is the H1f-landed bytes.
- **仅在分支 / branch-only:** this record document (the only committed file).
- **真实封证 / actually sealed:** **none.** V seals nothing. The `1.20.1` joiner-profile bytes, the `BUDGET_UNDECLARED 3639/738432269` frontier, the ⑤-family grep/`err=0` exclusion, and the d1↔d2 reversal are *measured* but not sealed.
- **未验证 / not verified:** a 1.20.1 joiner reaching a playable in-world state (B1); the ⑤ family against a *launched* 1.20.1 client; any ruff result.

No case is claimed closed, no gate is claimed lit, and JOIN is **not** claimed verified end-to-end — the on-disk bytes show the joiner stalls at profile admission before its JVM launches.
