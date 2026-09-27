# E6 `V1201-LOCAL-JOIN-SEAL-001` — 1.20.1 本地加入的规范卷真跑封证（H1g+V4 之后）

- **卡片**：`docs/v1201-local-join-next-2026-09-27.md` §2「### E6」，逐字取其允许面 / 验收。
- **Lane / 分支**：`codex/minekin-v1201-join-seal`（E 证据 lane），基线 `7b99485`（= 当时的远端 `main`，含 H1g 与 V4 记录）。
- **本卡状态**：**DELIVERED — 1.20.1 本地加入在当前 build 上真跑并封存为规范卷 bundle**：
  run `73a52bfb8f24462794ff571c46267e2e`、bundle `b2b4133b3e3ce030542ddb99aa18c6dd48bff60a36a62a75da2d7330865da8d9`、
  attempt 序列 **4**（supersedes seq3 `7236c53e…`，`case_id V1201-020`、`case_version e7c3b72235d90766…`）、
  判据 `3/3` 全 held、四读齐（verify `rc=0` / 独立 rejudge `agrees rc=0` / replay 19 事件投影 `STOPPED rc=0`（工具侧与产品侧各一次）/ `report_promotion rc=1` 属预期阻塞形状）。
  V4 的活体读数自此**不再是唯一入口**：本卡不凭 V4 文档写 DONE，材料是本 run 自己的。
- **不点亮任何门**（量出来的，不是说的小）：`V1201-020` 是 `mandatory: false` 的已登记 case；封前后门载荷
  sha256 逐字相同（`cfa0f118…`），`promotable` 名单前后都是 `['W00','W10','W20','W60']`，`W40.promotable False`、
  `overall.blocks ['REQUIRED_CASE_NOT_REGISTERED']` 一字未动。registry / 判据 / case 文件 / 封存 schema 零改动。

---

## 1. case 解析（第 0 步：不靠猜数字）

1.20.1 已登记的 case 在 `tests/fixtures/cases/v1201-0*.json`。逐份读 `case_id`/`work_package`/`mandatory`/`assertions`：

| 文件 | id / W / mandatory | assertions 字段 | 结论 |
|---|---|---|---|
| `v1201-010.json` | V1201-010 / W20 / false | `handshake_accepted_by_core`, `stayed_observe_only` | 主菜单握手 + **仅观察**（明言不入服），不是 JOIN case |
| `v1201-020.json` | V1201-020 / W40 / false | `server_observed_join_identity`, `first_snapshot_admitted`, `leave_after_join_observed` | **本地加入 / JOIN / 首快照就是这一条**：服务端见到的入服身份 + 同代首快照 + 入服后离开 |
| `v1201-040.json` | V1201-040 / W60 / false | `move_input_was_leased`, `the_bridge_carried_the_input_out`, `the_lease_expired_and_was_released`, `the_server_saw_the_kin_move`, … | 移动/lease 家族，入服只是前提不是判据主体 |
| `v1201-060.json` | V1201-060 / W70 / false | `runtime_controller_sigkill_was_confirmed`, `the_bridge_released_the_input_when_the_ipc_was_lost`, … | 断连松键家族 |
| `v1201-070.json` | V1201-070 / W50 / false | `the_first_snapshot_was_refused_by_the_reason_the_case_names`, … | **拒收**首快照的反例形状，不是承认路径 |
| `v1201-080.json` | V1201-080 / W70 / false | `the_bridge_released_the_input_when_the_session_was_stopped`, … | 停止松键家族 |

判据字节也在场复核过：`first_snapshot_admitted` 要求 `snapshots_admitted >= 1` **且** `connection_state == "PLAYABLE"`
（`tools/assert_case_evidence.py:1444-1467`）；`server_observed_join_identity` 读服务端 join 行 + `usercache.json`
的离线 UUID 推导（`:1054-1071`）；`leave_after_join_observed` 要求服务端日志里 leave 行**在 join 行之后**
（`:1514-1537`）。⇒ 本卡只调用 **V1201-020** 这一条已登记 case 与现行判据，不改任何一条。

## 2. 输入落位（卡片与简报点名项逐条兑现）

- **被驱动字节**：`test-orchestrator/runner/domain.sh` sha256
  `ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4`（H1g 交付字节，已在 `7b99485`；
  每个容器首行打印，封前后逐字相同，见 §5）。
- **桥 jar（未入库构建产物，复制不重构建）**：从 M 点名的
  `C:/Users/darling/Documents/agent_work/minekin/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar` 复制到
  本工作树 `bridge-1201/build/libs/`（`recipe.py:74` 写死的相对路径；`.gitignore` 覆盖 `build/`）。
  复制前源件与复制后落点件宿主实测 sha256 一致：
  `e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f`、`1310604` 字节
  （`.tmp/e6/02-bridge-copy.log`）。容器内再量一次同值（`/out/live/00-header.txt`）。**没有跑 gradle。**
- **1.20.1 受控服务端 jar（专服形状所需，卡片未点名——具名申报见 §6-D1）**：
  从主仓未入库件 `minekin/.tmp/mc-1.20.1-server.jar` 复制到本工作树 `.tmp/e6/`（不入仓），实测
  sha1 `84194a2f286ef7c14ed7ce0090dba59902951553`、`47791053` 字节——与 `tools/run_controlled_server.py:97-98`
  对 1.20.1 recipe 的**具名 pin 逐字相等**；容器内挂 `/server/server.jar:ro` 后再量一次同值，工具起跑时自核。
- **物料播种（不跑约 25 分钟整店取件）**：规范卷只读普查确认 `kin-04/run/artifact-store` 7565 个 blob、
  `1.20.1.jar` blob sha1 `0c3ec587af28e5a785c0b4a7b8a30f9a8f78f838`（`.tmp/e6-00-volume-census.log`、
  `.tmp/e6-04-prep.log`）。`python -m minekin_core init` 新建 **`kin-e6-j020`**（真跑）与 **`kin-e6-ctr`**
  （反证控制半边），两枚 store 各自 `cp -a` 自 `kin-04`（只读该既有 Kin，一字未动），播种后各复核 7565 blob + 同名 sha1。
  **缺失计数判据**：产品那句 `N of M artifacts are not in the store yet`（连同 `has not been built`/`BUDGET_UNDECLARED`/
  `would cost`）扫本次全部 stderr 与 server 日志，逐字读数 `(no such line fired this run)`（`/out/live/90-readouts.txt`）。
- **卷边界（第 0 步普查 vs 收工差值）**：封前：Kin 根 14 → 16（+我的两枚新 Kin）、manifest 文件 126 → 127
  （+1 = 本 bundle 的 `manifest.json`；其中 durable registry 口径 bundles 112 → 113、attempts 76 → 77，见 §5）、
  `server-runs` 目录 184 → 185（+1 = 本 run 的 `run-185`，append-only）。**卷上没有一份既有 bundle 被改动、删除或重封**：
  旧 attempt 1–3 的 bundle 在收工后逐一 `evidence verify` 复验，摘要逐字原值且仍 `verified/PASS`
  （`6dd17bd6…`、`bc987a32…`、`9a732edc…`，`.tmp/e6-08-old-bundles-intact.log`）。旧 FAIL 同样原样在场。
  全卡 `find /data -iname '*v4*'` 命中 0（V4 材料不在规范卷，与本卡一致）。
- **远程边界**：全程只连本次受控 runner 自己在容器 loopback 起的 `127.0.0.1:25566`（`bridge asked vanilla to
  connect to 127.0.0.1:25566 for generation 1`，逐字在封进 bundle 的 `client/latest.log` 里）。
  主仓 `.tmp/local-test-server.txt` 没有被打开、读取或打印过；本文不出现任何远程 IP:端口。

## 3. 真跑（当前 build 的同一 run：真客户端 + Bridge + JOIN + 首快照 + 释放/停止）

驱动方式：`domain.sh`（`MINEKIN_DOMAIN_CASE=V1201-020`，`case_on` 默认 host——专服形状里判据主体就是这个入服会话）：

```bash
# Git Bash；规范卷此窗口唯一可写挂载（同一时间只有这一个容器）
docker run --rm --entrypoint /bin/bash -w /src \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/data \
  -v "${REPO}/.tmp/e6/mc-1.20.1-server.jar:/server/server.jar:ro" \
  -v "${REPO}/.tmp/e6/out:/out:rw" \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -e MINEKIN_USERNAME=Kin -e MINEKIN_KIN_ID=kin-e6-j020 \
  -e MINEKIN_DOMAIN_CASE=V1201-020 -e MINEKIN_DOMAIN_SECONDS=420 \
  minekin-runner:local -lc 'bash /src/.tmp/e6/e6-drive.sh session start \
    --profile /src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json \
    --server-profile /src/tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json'
# → .tmp/e6-06-live-run.log（97 行全量转写）；/out/live/{00-header.txt,90-readouts.txt,server/,domain-*.json,err}
```

同 run 的阶段读数（全部逐字在 `.tmp/e6-06-live-run.log`）：

| 阶段 | 逐字读数 |
|---|---|
| 受控专服起 | `domain: server run directory /data/server-runs/run-185` → `domain: server ready`；server.log `46:[05:47:23] … Preparing level "world"`、`55:… Done (3.673s)!` |
| 客户端 JVM 真起 | `client/latest.log` 首行 `[05:48:03] [main/INFO]: Loading Minecraft 1.20.1 with Fabric Loader 0.19.5`（实际版本=配方版本，mod 清单含 `- minekin_bridge 0.0.0`） |
| Bridge 握手 | `86:[05:48:13] Setting user: Kin` → `192:[05:48:20] bridge asked vanilla to connect to 127.0.0.1:25566 for generation 1 (loaded=true, …)` → `194: CONNECTION_PHASE_LOGIN_NEGOTIATING` → `195: …PLAY_INIT` → `196: …JOIN_SEEN` |
| JOIN（服务端侧） | server.log `79:[05:48:24] [Server thread/INFO]: Kin joined the game` |
| 首快照（承认侧） | run document：`connection_state "PLAYABLE"`、`snapshots_admitted 1`、`snapshot_rejections []`、`entities_admitted 14`、`perceived_information_class "PLAYER_EQUIVALENT"`；harness `domain: the session is playable` |
| 离场（服务端侧） | server.log `87:[05:48:40] [Server thread/INFO]: Kin left the game`（在 join 行**之后**，判据读的是行序） |
| 停止/释放 | `domain: stopping the session`、run document `input_release_failed false`、`outcome "BRIDGE_LOST"`（harness 终止客户端的既有收尾家族，H1d/H1c 具名，不是新失败层）、`outcome` 时 `session_state "STOPPED"` |
| 封存 | `domain: sealing run evidence for case V1201-020` → seal 报告 `"attempt_sequence": 4, "result": "PASS", "status": "sealed"`、12 件 artifact（含 `bridge-trace.jsonl`、`server/usercache.json`、`trusted/server-profile.json`） |
| 收尾 rc | `domain: the case verdict is PASS`、`domain: evidence verify said {…"verified": true, "violations": []}`、`E6-live: domain.sh rc=0`。case run 的 rc 是案件的答复而非会话的（`domain.sh` 内注）；本卡 PASS ⇒ rc=0，V4 的 14 是**非 case** 会话形状 |

**首快照的载体真相（措辞边界）**：per-Kin 台账（`/data/kin/kin-e6-j020/kin.sqlite3`，WAL，`:ro` 打不开需先 cp）
的事件家族是 `SessionProcessStarted / BridgeHelloAccepted / JoinObserved / SessionIdentityCompared /
PlayableEstablished / SessionInterrupted`，**没有任何快照事件**；本 run 的「首快照」判据载体是 run document 的
`snapshots_admitted=1` + `connection_state=PLAYABLE` 双条件（判据 `first_snapshot_admitted` 正是这么写的），
时间线以 `bridge-trace.jsonl` 封进 bundle（`trace.py:73` 常量路径）。加入者 run document 的
`world_snapshot` 是 `null`——**本记录不写「加入者产出了快照摘要」**；世界本体字节在 `server-runs/run-185/`
（卷上、bundle 未含）。给 bundle 扩快照字段属主控保留决策，本卡只申报现状，不扩。

## 4. 四读（同一份封存字节，`/src:ro` + 规范卷 `:ro`；`.tmp/e6-07-four-reads.log`）

容器首行逐字：`E6-reads: … /src writable: False | /data writable: False` + `ff69c879…domain.sh`。

1. **`python -m minekin_core evidence verify 73a52bfb8f24462794ff571c46267e2e`** — `rc=0`：
   `{"artifacts": 12, "bundle_digest": "b2b4133b…5da8d9", "result": "PASS", "sealed": true, "status": "verified", "verified": true, "violations": []}`
2. **`python /src/tools/rejudge_evidence.py /data/kin/kin-e6-j020/run/evidence/73a52bfb…`**（独立重判，只看封住字节）— `rc=0`：
   `Rejudge evidence: OK (V1201-020 at e7c3b72235d907664b38494de7ad273922f4ac13b316d188339f39fe7b79e794 — these bytes produce the verdict the bundle records)`；
   `re_judged.observed` 三条判据全中、`failures []`、`status "agrees"`。
3. **replay（适用；本 run 有台账时间线工件）**——工具侧 `python /src/tools/replay_evidence.py <bundle>` 与产品侧
   `python -m minekin_core replay <bundle>` 各一次，均 `rc=0`，逐字同值：
   `Replay evidence: OK (… projects 19 event(s))`，`"events": 19, "projected": {"last_event_position": 18, "state": "STOPPED"}, "trace": "bridge-trace.jsonl", "trace_sha256": "b803bce5cbbaf4749325dd74bfcb129172e8b71bb06214e329c1f41625abb742", "violations": []`
4. **`python /src/tools/report_promotion.py --data-root /data`** — `rc=1`（预期阻塞形状，不是读坏了）：
   `POST overall: blocked blocks: ['REQUIRED_CASE_NOT_REGISTERED']`；`POST W40 promotable: False blocks: ['REQUIRED_CASE_NOT_REGISTERED']`；
   `promotable ['W00','W10','W20','W60']`（与恒常读数逐字同）；本 bundle 行：
   `V1201-020 seq 4 73a52bfb8f24462794ff571c46267e2e PASS build: True re_judged: AGREES case_version: e7c3b72235d90766 bridge: e50d61c209be violations: []`；
   attempt 行 `{"case_id": "V1201-020", "run_id": "73a52bfb…", "sequence": 4, "status": "SEALED", "supersedes_run_id": "7236c53e…"}`；
   计数 `attempts 77 / bundles 113 / unsealed 0 / unreadable [] / unverified [] / from_another_build 61`（61 名单一字未变）。

## 5. 前后差（build 与门载荷，各在封存前后量一次）

| 量 | 封前（`.tmp/e6-04-prep.log` + `.tmp/e6-05-pre-gatepayload.log`） | 封后（`.tmp/e6-06`/`.tmp/e6-07`） | 差 |
|---|---|---|---|
| `domain.sh` sha256 | `ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4` | 同值 | **无** |
| 桥 jar sha256 | `e50d61c209be…006f`（1310604 B） | 同值 | 无 |
| 服务端 jar sha1 | `84194a2f286e…1553`（47791053 B） | 同值 | 无 |
| recipe plan（report 自述） | 1.20.1 `83299ad5e224959d…` / 1.21.4 `bcc0c10d46ab5c0b…` | 同值 | 无 |
| **门载荷** `sha256({"work_packages","overall"})` | **`cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`** | **`cfa0f1184bee…`** | **空差集**（runner 字节变更不搬门，与 `_build_agrees` 只比 recipe 派生 plan 摘要的结构一致） |
| attempts / bundles / manifests / Kin 根 / server-runs | 76 / 112 / 126 / 14(普查) / 184 | 77 / 113 / 127 / 16 / 185 | 全部 +1、+2 只落在**我新建**的对象上；既有项零变动（§2 末行复验） |

## 6. 非恒转反证（`.tmp/e6-09-counter.log`；母文档与错配件留在 `.tmp/e6/out/counter/`，不入库）

- **母文档** = 登记的 `tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json` 原字节拷入容器 `/tmp`，
  sha256 `3864eddae899c77a1f2c522fd02c3618b6601efd97f9e2fe8c4aff2354303aa2`。
- **错配文档** = 母文档**语义上只动一个字段** `version_policy.allowed_versions → ["1.21.4"]`
  （`json.dump(sort_keys=True, indent=2)` 重排了字节序与缩进——字段集合的差只有那一格，diff 逐字在日志里），
  sha256 `eb5958e89df3dc1e59801b19e0b1d9a2a23989b4dfed8b69d0118ee96239484e`。
- **直接准入调用（成对）**：control `{"admission": "accepted", "host": "127.0.0.1", "port": 25566, "auth_mode": "offline"}`；
  mismatch `{"admission": "refused", "category": "ADMISSION", "message": "the session launches Minecraft 1.20.1, the target allows 1.21.4"}`。
- **整动词半边（客户端 JVM 之前具名拒用）**：
  `session start --profile bundle-candidate-1.20.1.json --server-profile /tmp/e6c/mismatch.json` ⇒
  **`rc=17`（5 秒返回）**，stderr 逐字：
  `{"category": "ADMISSION", "component": "launcher.profile", … "message": "the session launches Minecraft 1.20.1, the target allows 1.21.4", "operation": "load", "retryability": "OPERATOR_ACTION"}`；
  `launcher.profile` 具名命中 1。
- **匹配控制半边（证明拒用不是恒真）**：同 argv 换母文档 + `--connection-timeout-seconds 20` ⇒
  `rc=14`（37 秒；124 才是超时截断）、stderr 无 diagnostic、`launcher.profile` 命中 0、
  客户端 JVM 真起（`latest.log` 首行 `Loading Minecraft 1.20.1 with Fabric Loader 0.19.5`）。
  该容器里没有任何世界在听 25566，20s 连接期限后按 `BRIDGE_LOST` 收掉。
  **披露**：这条裸驱动线没有 `domain.sh` 的 Xvfb/XDG wrapper，控制半边在 `kin-e6-ctr` 留下
  一份 crash 报告（`crash-2026-09-27_05.52.23-client.txt`，已拷回 `.tmp/e6/out/counter/`）——
  复现的是「环境没给够时 ⑤ 家族会开火」（与 V4 §5 同形），不构成对受控路径（§3）的任何指控。
- **D1 具名申报（卡片文字之外的一步）**：专服入服形状需要一个 `/server/server.jar`，卡面只给桥 jar 开了复制口子。
  处置：只用 `run_controlled_server.py` 自己 pin 的那组字节（sha1/size 双测逐字相等），不重构建、不另下载、
  复制件留在 `.tmp/`（不入库）。若 M 判这超出允许面，撤本卡即可，无连带。

## 7. 交付面与卫生

- `git status --short` 交付前只有本文件一项（`bridge-1201/build/`、`.tmp/` 全被 `.gitignore` 覆盖，实测不显示）。
- `src/**`、`test-orchestrator/**`、`tools/**`、`tests/**`（含 case/registry/manifest）、封存 schema **一字未改**；
  没有任何 case 被改成 `mandatory`、没有新 case id、没有任何门被本卡推动（§5 空差集）。
- 未连接任何远程/公网目标；`.tmp/local-test-server.txt` 全程未打开。

## 8. 四态

- **已合主干**：无——本卡一切产出只在分支上，等 M 审。
- **仅在分支**：本记录一份 + 分支 `codex/minekin-v1201-join-seal`（基线 `7b99485`）。
- **真实封证**：`V1201-020` attempt seq4 / run `73a52bfb8f24462794ff571c46267e2e` / bundle
  `b2b4133b3e3ce030542ddb99aa18c6dd48bff60a36a62a75da2d7330865da8d9`，当前 build（`ff69c879…` 字节 +
  `83299ad5…` plan + `e50d61c2…` 桥）真跑、PASS、四读一致、`from_repository_build: True`。
- **未验证**：跨 bundle 三段链载体与 `world_context_id`（`A_B_A_TRIPLE_NOT_SEALED` 不动，属主控保留）；
  bundle 内加「首快照摘要」字段（不扩，schema 一动全卷重封，属主控保留）；`::1` IPv6 loopback 形状；
  `--auto-bundle`×joiner（按拒止原样尊重）；PLAYABLE 之后的动作/输入半边（`V1201-040/060/080` 的家族，不是本卡）；
  1.21.4 路由（H1g/V4 已各自量过，本卡未复量）；反证控制半边的 ⑤ 家族只在裸驱动线上复现，受控路径的 0 命中判定以 §3 表为准。
