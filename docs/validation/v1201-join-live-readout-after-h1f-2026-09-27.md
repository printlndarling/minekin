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

---

# 补充读数（同卡续跑，2026-09-27 00:37–00:54Z）

上面的 §Reading/d6 已经落在一批 `.tmp/v3` 字节上；本节补三件它没有落到字面的东西：
**(b) 环境的逐字读数、(d) 终局家族的逐字读数、以及卡片点名的七道仓库门的真实输出**（含一节对
上面 `Local gates` 的更正）。字节身份没有变：续跑用的仍是
`domain.sh = f8624ac6713301460288b439ac9644a0b4b1026e218e19f107c9678758ffe0c5`（出厂）/
`9883a788f5f39008b208998d2b3833e9ea6ad511bfd35f9b63693daf1b9671a0`（base，
`git show ea97c5c:test-orchestrator/runner/domain.sh | sha256sum` 复核一致）。
`ea97c5c..HEAD` 里动过 `domain.sh` 的只有 `02a8b4b`（H1f 本体），所以 d1↔d2 只有一个因子。

## S-a 真实取料没有为省时间截断（可复核的时间跨度）

```text
{"artifacts": 3639, "failed": [], "installed": 3639, "jobs": 8, "missing": 3639, "missing_bytes": 738432269, "reused": 0, "schema_version": 1, "status": "complete", "store": "/data/kin/kin-v3-host/run/artifact-store"}
fetch rc=0 at 2026-09-27T00:25:54Z
```

store 内 blob 最旧/最新 mtime = `1790468084.63 → 1790468753.84`：**669 秒**取完 3639 件 / 738,432,269 字节，
`failed: []`，`reused: 0`。服务端 jar 也走仓库自带具名通道（制品 CDN 钉摘要，不是连任何 MC 服务器）：
`ok com.mojang:server:1.20.1 47791053 bytes` / `Supply chain: OK (7 pinned artifacts still match)`。

## S-b ④ (b) 格：joining 客户端被交到的环境，逐字

d1 的 `/tmp/domain-join-profile.json` 全文（这才是「活字节读出来的版本」，不是合同测试）：

```json
{
  "schema_version": 1,
  "profile_id": "p0-lan-host-fixture",
  "host": "127.0.0.1",
  "port": 25570,
  "auth_mode": "offline",
  "minecraft_version": "1.20.1",
  "visibility": "isolated_test_only",
  "resource_pack_policy": "deny"
}
```

d1 的 `client-environment.txt` 全文（两深度 × 三态命名）：

```text
harness DISPLAY=:77
harness XDG_RUNTIME_DIR=<unset>
harness XAUTHORITY=<unset>
harness XDG_RUNTIME_DIR_ORIGIN=<unset>
harness GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits)
harness GL_PROBE_RC=0
harness WRAPPER=direct
launch DISPLAY=:99
launch XDG_RUNTIME_DIR=/tmp/minekin-client-runtime/runtime.03hzcE
launch XAUTHORITY=/tmp/xvfb-run.Ynpqwm/Xauthority
launch XDG_RUNTIME_DIR_ORIGIN=provided-by-harness
launch GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits)
launch GL_PROBE_RC=0
launch WRAPPER=inside-wrapper
```

同轮 harness stderr 交叉核对（说明该文件是本轮写的，runtime 目录名逐字同轮）：

```text
domain: joiner client environment before its JVM: harness DISPLAY=:77 harness XDG_RUNTIME_DIR=<unset> harness XAUTHORITY=<unset> harness XDG_RUNTIME_DIR_ORIGIN=<unset> harness GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits) harness GL_PROBE_RC=0 harness WRAPPER=direct 
domain: joiner runtime directory: /tmp/minekin-client-runtime/runtime.03hzcE (provided by the harness at mode 0700; the name it would have inherited was unusable because it is not set in the environment this script holds)
```

d2（base 字节）同深度只有随机名不同（`launch XDG_RUNTIME_DIR=/tmp/minekin-client-runtime/runtime.RRaaRB`），
即 **H1e 的运行时目录补投在两侧字节上都真实发生**，与本卡问的版本字段无关。

**这格的适用边界**：它读的是「JVM 起来之前被交到的环境」。d1/d2 的 joining 客户端**都没起过 JVM**，
所以这一格证的是补投发生与 GL 探针 rc=0，不证「1.20.1 客户端拿着它能画出一帧」。

**陈旧读数警告（本卡踩到一次，必须写下）**：`/data/kin/<joiner>/run/client-environment.txt` 是**每 Kin**
而非**每 run**。d4 的 host 死在 bridge 取料之前、joiner 从未被起，但驱动仍从同一 V 私有卷抄到一份
`launch XDG_RUNTIME_DIR=…runtime.03hzcE`——那是 **d1 留下的**。**d4 的 (b) 段不作读数使用**；
重放本卡时，(b) 段必须与同轮 harness stderr 行逐字互验。

## S-c ④ (d) 格：终局与家族，逐字

d1 的结尾（完整跑到窗口关闭，未截断）：

```text
domain: Kin2 never arrived within 420s

domain: downstream reading — THE_JOINER_HAD_NOT_ARRIVED_IN_THE_WINDOW with a live world and a measurable screen (llvmpipe (LLVM 20.1.2, 256 bits)), so the client half rather than the world is where to look at the moment the window closed; a joiner arriving after the window would make this line about the window, not about the death
domain: Kin2 arrived but never became playable within 420s
domain: this run is 6b96145e0a5b4bcc9f167b1dcb9f1838
domain: session exited 14
V3: domain.sh rc=14 finished_utc=2026-09-27T00:35:31Z
```

d1 host 运行文档里承担读数的具名字段（同一轮，逐字取自 `/tmp/domain-session.json` 最后一行）：

```text
"lan_publication": {"phase": "LAN_OPENED", "port": 25570}
"outcome": "BRIDGE_LOST"
"session_state": "STOPPED"
"snapshots_admitted": 0, "entities_admitted": 0
"world_snapshot": {"digest": "5c14c5638566a8b3f3cdb330cf14c1b30738fa37f2281f8e4b0020bb4401819e", "level_name": "kinworld", "settings_digest": "3bdd4affd45b65b90dbb7cd25ae34581b6beaf42edcf2324f63f187b5023c00c"}
"run_id": "6b96145e0a5b4bcc9f167b1dcb9f1838"
```

以及 host 真的开放了世界的日志行（`/data/kin/kin-v3-host/run/session/ea7078d7…/generation-1/logs/latest.log:220`）：

```text
[00:27:36] [Render thread/INFO]: Started serving on 25570
```

终局家族定名：**BRIDGE_LOST / rc=14**（harness 在窗口关闭时停客户端，H1d 命名的那一族）。
d2 在同一形状给出同一个家族（`run_id 0d4326b6…`、`"outcome": "BRIDGE_LOST"`、同一个
`world_snapshot.digest 5c14c563…`、`V3: domain.sh rc=14`）——**世界半程两轮都是真的，join 半程两轮都没有发生。**

d4 / d5 各落在另一个具名家族：`rc=11`（SUPPLY_CHAIN 具名停，H1d 的 rc 传播在 1.20.1 通道上成立）；
d3 / d6 落在 `rc=2`（写手前的具名拒绝）。四个 rc 互不相同，说明读数不是恒绿也不是糊在一起。

## S-d ⑤ 家族四格的最终判定（把上面 §Reading ②③ 的判定按卡片要的三态重列）

| 阻断 | 判定 | 决定性日志行（逐字） |
|---|---|---|
| `GLFW 0x1000E` | **未抵达**（就 1.20.1 JOIN 这条路而言不是致命因） | d1 全量扫描 `V3: files under /data or /tmp mentioning 0x1000E: (none)`；joiner 无 overlay 日志、`find /data -path '*crash-reports*'` 空；起 JVM 前已停在 `"message": "server profile minecraft_version is outside the pinned bundle"` |
| `XDG_RUNTIME_DIR` | **未抵达**（补投本身已发生，见 S-b） | d1 扫描只剩 harness 探针自身：`/tmp/domain-client-environment-probe.sh:31: for item in DISPLAY XDG_RUNTIME_DIR XAUTHORITY; do`；客户端亲笔的 `error: XDG_RUNTIME_DIR is invalid or not set…` 在 d1/d2 均无命中 |
| bridge 取料 | **复现**（JOIN 形状，d4） | `` {"category": "SUPPLY_CHAIN", "component": "launcher.recipe", … "message": "the Bridge jar has not been built: /src/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar is missing; run `./gradlew build` in the bridge-1201 directory", "operation": "verify"} `` → `domain: nothing was published on 25570 within 90s` → `rc=11` |
| 预算前沿 | **auto 形状复现（d5）；JOIN 形状结构上不可抵达（d6）** | d5：`"message": "3639 of 3639 artifacts are missing and would cost 738432269 bytes; … [BUDGET_UNDECLARED]"`，且同轮 `domain: server ready` / `domain: the controlled server reports enable-status=true` / `rc=11`；d6：`cp: cannot stat '/data/kin/kin-v3-d6/run/artifact-store': No such file or directory` + `domain: could not give the joining Kin an artifact store` + `rc=2` + `V3: /tmp/domain-join-profile.json WAS NOT WRITTEN` |

d6 那条是续跑新增的一条**结构读数**：JOIN 形状不预算、不自动取件，而是把 host Kin 的 store 整枚
`cp -a` 给 joiner（`domain.sh:720-727`），所以 `BUDGET_UNDECLARED` 在 JOIN 路上根本不可抵达，
JOIN 路上对应的那堵墙叫 `could not give the joining Kin an artifact store`，且它开火在 H1f 写手**之前**。
反过来也证掉一个可能的误读：d1/d2 的 joiner Kin 各有 727 MB store 副本
（`du -sh /data/kin/*` → `kin-v3-join 727M` / `kin-v3-join2 727M`），所以 d1 的早停**不是**缺件造成的。

## S-e 为什么 d1/d2/d3/d5 能把 host 客户端开起来：bridge 字节的来源（边界披露）

卡片边界要求「不许发明取料源头」，所以这里逐字交代：那几轮 `/src` 挂的是
`git archive HEAD` 的 V 私有克隆 `.tmp/v3/src`，其中我放了一枚
`bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar`，宿主侧实读：

```text
e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f  .tmp/v3/src/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar
-rw-r--r-- 1 root root 1310604 Sep 27 08:13 minekin-bridge-1201-0.0.0.jar   (容器内 ls -l)
```

它与 `tests/fixtures/runtime-input/bundle-candidate-1.20.1.json` 里 `minekin-bridge` 那条 pin
（`"digest": "e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f"`, `"size": 1310604`,
`"source": "workspace:bridge-1201"`）逐字同一枚。

它**不是**从网络取的（V1/V-c 记录的 1.20.1 bridge 无网可取这一阻断我没有绕过、也没有假装解决），
而是在**只读**挂载的 `minekin-runner-data` 上，从某轮已跑完的 `generation-1/mods/` 里读出来、
`cp` 进 V 私有克隆树；正本卷全程 `:ro`，正本根下没有新建任何 attempt/bundle，没有封存任何东西。
产品自己的 `_require_pin`（size + sha256）在每轮起跑时都过了，这是可复核的凭据。
**这不改变任何读数**——d4 正是把这枚 jar 拿掉之后同一驱动的样子。

## S-f 发现（只记录，不修；H/产品拥有）

- **F1 两行互相矛盾**：d1 与 d2 同轮都打 `Kin2 never arrived within 420s` **且**
  `Kin2 arrived but never became playable within 420s`。前句说没到，后句说到了但不可玩。
  根因在 `domain.sh:1148-1156`（第一窗因 `kill -0` 失败即 `break`）与 `:1170-1189`
  （第二窗不管第一窗结论，仍完整跑并署名 `arrived`）。下游分类器因此拿到一对矛盾名字。
- **F2 崩溃噪声**：d1/d2 停止阶段有 `Traceback … File "<stdin>", line 5 … KeyError: 'run'`
  ——某段 heredoc 读**缺失的 joiner 运行文档**的 `["run"]`。不改 rc，但污染 stderr。
- **F3 窗口署名不诚实**：循环在 joiner 进程退出时立刻 `break`，句子却仍以 `420s` 署名
  （d2 里 joiner 约 62 秒即没了；`never arrived within 420s` 读起来像「等满 420 秒」）。与 F1 同根。
- **F4（产品面，本卡的落点）**：`src/minekin_core/adapters/launcher/server_profile.py:32`
  `MINECRAFT_VERSION = "1.21.4"` 与 `:200-201`
  `raise _reject("server profile minecraft_version is outside the pinned bundle")`。
  H1f 之后，这一句是 1.20.1 JOIN 的**唯一上游拒绝**：profile 诚实说 1.20.1 → 被「outside the pinned bundle」拒绝；
  profile 撒谎说 1.21.4（d2）→ 被「the session launches Minecraft 1.20.1, the profile pins 1.21.4」拒绝。
  两句互为镜像，合起来把「版本混淆」与「版本准入」分得很干净。
  本卡在全仓 grep：**没有任何测试引用 `outside the pinned bundle` 这条消息**——这个钉目前只有产品代码里的名字，
  没有测试里的名字。只记录，不修。

## S-g 仓库门复量（在 `bbf0daf` 之后的分支树上跑，逐字真实输出）

> **更正上面 `Local gates` 那一节**：它把 ruff 记成 `127 — not run`，那是直接叫 bare `ruff` 的结果；
> 卡片点名的门形是 `uv run ruff …`，在本机可用且**全绿**。同样，`bash -n` 与两枚 pytest 门在那一节没有记录。
> 下面七道（卡片逐条点名的）全部真跑，无一道用「另一道门的结论」代替。

```text
$ bash -n test-orchestrator/runner/domain.sh
bash -n rc=0

$ uv run --frozen pytest tests/contract/test_runner_scripts.py -q
.............................                                            [100%]
29 passed in 0.09s

$ uv run --frozen pytest -q
=========================== short test summary info ===========================
SKIPPED [1] tests\unit\test_orphans.py:686: this platform cannot answer the question, so it can never say gone
SKIPPED [1] tests\unit\test_silent_listener.py:123: a Windows terminate is not a signal
SKIPPED [1] tests\unit\test_tested_provenance.py:354: bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar is not built on this host, and the reviewed Bridge bytes are one of the things this check measures
2596 passed, 3 skipped in 380.55s (0:06:20)

$ uv run --frozen pytest "tests/unit/test_session_supervision.py::test_a_deadline_does_not_cancel_a_world_the_kin_is_already_in" -q
.                                                                        [100%]
1 passed in 5.34s

$ uv run ruff format --check .
355 files already formatted          rc=0

$ uv run ruff check .
All checks passed!                   rc=0

$ uv run python tools/check_case_assertions.py
Case assertion implementations: OK (150 registered)          rc=0

$ uv run python tools/verify_fixture_digests.py
W00 schema and fixture digests: OK                            rc=0
```

卡片点名的已知易抖节点 `test_a_deadline_does_not_cancel_a_world_the_kin_is_already_in` 在全量里**没有失败**；
仍按其要求单跑一次并两值并记（全量 1 处通过 + 单跑 `1 passed in 5.34s`）。
全量 3 条 SKIPPED 均为平台性跳过，其中第 3 条正是本卡 S-e 交代的 bridge jar 未在宿主建树——
它跳过而不是失败，与「我把 jar 只放进 V 私有克隆、没放进 worktree」是一致的（worktree 里至今没有 `build/libs`）。
跑全量期间容器全部已退出，没有并发 JVM 可被拿来当抖动借口。

顺带把卫生门也实测一次，并且**不为让它变绿而改动逐字日志**：

```text
$ git diff --check
warning: in the working copy of 'docs/validation/v1201-join-live-readout-after-h1f-2026-09-27.md', LF will be replaced by CRLF the next time Git touches it
docs/validation/v1201-join-live-readout-after-h1f-2026-09-27.md:203: trailing whitespace.
+domain: joiner client environment before its JVM: ... harness GL_PROBE_RC=0 harness WRAPPER=direct
diff --check rc=2
```

命中的那一行是 S-b 里逐字抄的 harness 输出——它本身就以 `WRAPPER=direct `（尾随一个空格）结尾。
本卡选择保留字面、把 rc=2 如实记下，而不是抹掉那个空格把门做绿；上一条文档的
`diff hygiene → 0` 是在没有这段逐字抄录时得到的，两者不冲突，但**以本节这条为准**。

## S-h 未测（续跑之后仍然没有证到的）

1. 1.20.1 客户端**真的起 JVM 之后**是否复现 `GLFW 0x1000E` / llvmpipe 起帧失败——
   出厂准入让进程起不来，不改 `server_profile.py` 就测不到（不在本卡修复权内）。
2. 1.20.1 客户端的 `XDG_RUNTIME_DIR is invalid or not set` 是否已被 H1e 消掉——同上，没有进程就没有那行。
3. 真实 `JOIN SUCCEEDED` / `PlayableEstablished` 落账（1.20.1）：仍未验证。
4. 1.21.4 侧同形状驱动（只把版本换回 1.21.4，看 joiner 能否起 JVM 并抵达 ⑤ 家族）：**未做**。
   它读的是 1.21.4 的路，而且 V 私有卷里没有 1.21.4 取件集（再取一轮 ≈ 11 分钟 + ~700 MB）。
   这是 S-f/F4 之外唯一还能把 ⑤ 家族往「复现/排除」推一格的做法，留给主控点名。
5. `--auto-bundle` × joiner 的组合：`domain.sh:404-407` 直接拒绝该形状（原样尊重，未改）。
6. 并发 / 多 joiner、非 offline 认证、任何远端或公网服务器：一律未测，且按边界声明一律不去。
7. 驱动侧一次排练失败（非产品读数）：`.tmp/v3/d0-rehearsal.log` 里
   `domain: this run cannot name its ledger (found 1), so nothing here can be attributed` rc=2，
   起因是那次 prep 容器没带 `PYTHONPATH`，`init` 报 `No module named minekin_core`，
   于是被点名的 Kin 没有 `kin.sqlite3`。正式六组全部用真 init 过的 kin（`kin-v3-host` / `kin-v3-d5` / `kin-v3-d6`）。

## S-i 四态（与上文不冲突的增量部分）

- **已合入 main**：无新增。H1f 本体（`02a8b4b`，经 `2ef64a8` 入 main）是本卡的前置。
- **仅在分支**：`bbf0daf`（上一节的读数）+ 本续跑节的补充。等主控合并，V 不合。
- **真实封证**（活字节 + 活进程 + 逐字输出；**V 不封存任何东西**，此处的「封证」= 已在磁盘上被逐字量到）：
  ①joiner profile 真带 `minecraft_version = 1.20.1`（d1，含全文）；
  ②base 字节下同轮真带 `1.21.4` 且两句准入消息互为镜像（d1↔d2）；
  ③H1f 无名版本分支真开红、profile 确实不写（d3，`run.sh domain` 通道复走同句）；
  ④`BUDGET_UNDECLARED 3639/738432269` 在 auto 形状上逐行复现且服务端真起报 `enable-status=true`，rc=11（d5）；
  ⑤bridge 取料在 JOIN 形状上逐行复现并卡在 LAN 开放之前，rc=11（d4）；
  ⑥JOIN 形状走 store 复制而非预算，空 store 时改名开火且 profile 未写，rc=2（d6）；
  ⑦终局家族具名：BRIDGE_LOST/rc=14（d1/d2，含 `Started serving on 25570` 与快照 digest）；
  ⑧七道仓库门全绿（S-g），含全量 2596 passed。
- **未验证项**：S-h 全部；尤其 **1.20.1 的 JOIN 从未抵达，本卡不宣布它绿**。
