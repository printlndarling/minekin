# V4 `V1201-LOCAL-JOIN-AFTER-V2-001` — 1.20.1 本地加入的受控活体读数（H1g 合入后）

- **卡片**：`docs/v1201-local-join-next-2026-09-27.md` §2「### V4」，逐字取其允许面 / 验收 / 派工前置。
- **Lane / 分支**：`codex/minekin-v4-local-join-after-v2`（V lane，活体验证）。
- **基线 SHA**：`8b357b6`（= 当时的远端 `main`，含 H1g；未 rebase、未 merge、不推 `main`）。
- **被驱动字节身份**（每一轮容器内首行打印，逐字相同）：
  `test-orchestrator/runner/domain.sh` = `ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4`（H1g 交付字节，已合主干）。
- **本卡状态**：**DELIVERED — 1.20.1 本地加入真实抵达 `JOIN` / 首快照 / `PLAYABLE`**。
  卡片点名七项读数全部 `PASS`，没有「未达到该阶段」的项；H1g 之后越过 `launcher.profile` 准入的第一停点
  **不是停点**——在同一次受控 run 里一路走到了加入者自己承认的 `PLAYABLE`。
  按卡片规定：这是 **V 私有活体读数，不是 sealed evidence**；V 不封存、不建 attempt/bundle、不碰规范卷写权限。

---

## 1. 输入落位（卡片「派工前置」逐条兑现）

### 1.1 桥 jar：复制已核字节，不重构建

- 源（M 具名的两枚之一）：`C:/Users/darling/Documents/agent_work/minekin/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar`。
- 复制前后宿主实测 `sha256sum` 一致：
  `e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f`，1310604 字节（另一枚
  `minekin-wt-evidence/` 同摘要，交叉核对过）。
- 落点（本工作树、`recipe.py:74` 写死的相对路径）：
  `C:/Users/darling/Documents/agent_work/minekin-wt-v4/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar`。
  该路径被 `.gitignore:22 build/` 覆盖，`git status --short` 全程不显示它——入库面零污染。
- 容器内复核（run a 的 `00-header.txt`，逐字）：
  `e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f  /src/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar`。
- **没有跑 gradle，没有从别处取件。**

### 1.1b 例外披露：1.21.4 控制组还需要第二枚桥 jar（卡片没有点名的落位）

1.21.4 正对照第一次跑（b1）死在同类供给具名上（§4 逐字）：`/src/bridge/build/libs/minekin-bridge-0.0.0.jar`
（`workspace:bridge`，另一枚未入库产物）。卡片只给 `bridge-1201` 那枚开了复制的口子。
**为让卡片自己要求的正对照可跑**，我把同名机制推广到这一枚：从 `minekin/bridge/build/libs/` 复制，
落位后宿主实测 `sha256` = `0ee2070b97ba6583ca004cc3f0e4a0e547697d0693dc635c3143c655cc2475f4`、1310646 字节，
与 `tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json` 里 `minekin-bridge` 那条 pin 的
`digest`/`size` 逐字相等；产品自己的 `_require_pin` 在 b2 起跑时复核通过。
这是**对卡片文字的一处具名超出**（不是构建、不是编造取料源，且被产品摘要钉兜底），在此如实申报，交 M 判。

### 1.2 播种私有 store：规范卷全程 `:ro`

- 私有数据根：docker 卷 `minekin-v4-join`（`/data`），**从未挂载 `minekin-runner-data` 为可写**；
  prep 容器以 `-v minekin-runner-data:/ro:ro` 只读挂了一次，用于播种。
- 播种源：`/ro/kin/kin-04/run/artifact-store`，容器内实测 7565 个 blob 文件，与卡片点名一致；
  `1.20.1.jar` blob 现场 `sha1sum` = `0c3ec587af28e5a785c0b4a7b8a30f9a8f78f838`（与卡片逐字同）。
- 方式：`python -m minekin_core init` 出 `kin-v4-host` / `kin-v4-host1214`（`status: created`），
  再 `cp -a /ro/kin/kin-04/run/artifact-store → /data/kin/<host>/run/artifact-store`，
  两枚 store 各自复核 7565 blob + 同名 sha1。joiner 的 store 由 `domain.sh:720-727` 自己在 run 内 `cp -a`。
- **边界兑现**：卡片说「blob 存在 ≠ launch set 完整」，判据是产品自己打印的缺失计数那一行——见 §3(b)：
  **备料 run 上该行根本没有出现**，`(no such line fired this run)` 就是它的逐字读数；
  1.20.1 launch set 完整性的正面证据是同 run 两侧客户端 JVM 真实启动并进了世界。
  H1g ②c 的 `3638 of 3638 artifacts are not in the store yet` 是空 store 形状产物，**本轮不再是 1.20.1 的停点**。

## 2. 驱动命令（Windows Git Bash，形状照 V3 的 `launch.sh`/`drive.sh`，输入换成本轮）

每轮一个 `docker run -d` 全新容器：`/src` = 本工作树 `:ro`，`/data` = `minekin-v4-join`，
`/out` = 工作树 `.tmp/v4/out`（未入库），镜像 `minekin-runner:local`，`PYTHONPATH=/src/src`、
`LD_LIBRARY_PATH=/opt/sqlite/lib`、`MINEKIN_HOME=/data` 与 V3 d1 同套 env；驱动器
`bash /src/.tmp/v4/drive.sh "$@"` 先打印 `domain.sh` sha256 与桥 jar 摘要再跑
`bash /src/test-orchestrator/runner/domain.sh "$@"`。

- **a（主读数）**：`MINEKIN_KIN_ID=kin-v4-host MINEKIN_DOMAIN_JOIN=kin-v4-join … -e MINEKIN_DOMAIN_SECONDS=420`，
  argv = `session start --profile /src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json --world-save /src/tests/fixtures/saves/kinworld --world-name kinworld`。
- **b（1.21.4 正对照）**：同形状，host=`kin-v4-host1214`、joiner=`kin-v4-join1214`、
  bundle=`bundle-p0-core-1.21.4.json`。跑了两次（b1 缺 1.21.4 桥 jar，b2 补齐后完整）。
- **c（版本错配反证）**：`bash /src/.tmp/v4/drive_mismatch.sh`，见 §5。
- 全程只连本次受控 runner 自己起的 loopback 世界；`.tmp/local-test-server.txt` 没有被打开过；
  没有任何 `--auto-bundle`×joiner 组合（`domain.sh:404-407` 的拒止原样尊重）。

## 3. 卡片点名的七项读数（run a，逐字 + 判定）

| # | 读数 | 判定 | 决定性证据（逐字） |
|---|---|---|---|
| 1 | 服务端**实际**版本 | **PASS** | host 客户端日志首行 `[04:54:18] [main/INFO]: Loading Minecraft 1.20.1 with Fabric Loader 0.19.5`；同 log `220:[04:54:44] [Render thread/INFO]: Started serving on 25570`。实际=配方声称（1.20.1），classpath 全指 `/data/kin/kin-v4-host/run/artifact-store/blobs/sha1/…`（含 `0c3ec…/1.20.1.jar`），不是别处的版本 |
| 2 | 加入者 profile 的 schema 与版本字段 | **PASS** | `/tmp/domain-join-profile.json` 全文抄入 `out/a/domain-join-profile.json`：`"schema_version": 2`，**无** `minecraft_version`，`"version_policy": {"mode": "explicit_allowlist", "allowed_versions": ["1.20.1"]}`，`target_authorization.granted_by = controlled-runner`，`127.0.0.1 25570 offline`；文档 sha256 `038dcf1e7331884a91a7c795d3b1ef8960d80405b049d1c5fc270df9fbb1f771` —— 与 H1g 读数②a 在活 run 上逐字节同一枚 |
| 3 | 客户端 JVM 真的启动 | **PASS** | joiner latest.log 首行 `[04:55:19] [main/INFO]: Loading Minecraft 1.20.1 with Fabric Loader 0.19.5`，全文件 201 行、31050 字节；`SessionProcessStarted` 入账 |
| 4 | Bridge 握手 | **PASS** | joiner log：`bridge asked vanilla to connect to 127.0.0.1:25570 for generation 1 (loaded=true, …)` → `CONNECTION_PHASE_LOGIN_NEGOTIATING` → `CONNECTION_PHASE_PLAY_INIT` → `CONNECTION_PHASE_JOIN_SEEN`；joiner 台账事件含 `BridgeHelloAccepted` |
| 5 | `JOIN` / 首快照 / `PLAYABLE` | **PASS** | host world log `222:[04:55:52] [Server thread/INFO]: Kin2 joined the game`；harness（stderr，`docker logs v4-a` 转写，见 §6 披露）：`domain: the world heard Kin2 arrive` 与 `domain: Kin2 admitted its first snapshot of that world`；joiner 运行文档（`out/a/domain-join-session.json`）：`"connection_state": "PLAYABLE", "snapshots_admitted": 1, "entities_admitted": 11, "entities_rejected": 3, "perceived_information_class": "PLAYER_EQUIVALENT"`；台账含 `JoinObserved`、`PlayableEstablished` |
| 6 | `GLFW … 0x1000E` 与 `XDG_RUNTIME_DIR is invalid` | **PASS（受控路径上不出现；字节口径见 §3(f)）**，且家族本身在裸驱动上**复现**（§5 反证半边） | 逐文件量，不以全树 grep 代答——下表 |
| 7 | 预算 / Bridge 取料停点 | **PASS（不出现）** | supply grep（`not in the store yet` / `has not been built` / `BUDGET_UNDECLARED` / `would cost`）扫 `domain-session.err`、`domain-join-session.err`、`domain-join-setup.log`、`domain-server.log`：逐字读数 `R4:   (no such line fired this run)`。JOIN 形状本就不走预算（V3 S-d 的结构读数维持）；本轮也没有 bridge 取料具名拒 |

run a 的收尾：`domain: the joining client ended with {'outcome': 'BRIDGE_LOST', 'connection_state': 'PLAYABLE', 'snapshots_admitted': 1, 'entities_admitted': 11}`、
`domain: session exited 14`、容器退出码 14（`docker ps -a` 回读 `Exited (14)`；drive.sh 的 rc 行属 §6 披露 1 那批未落盘转写）。
**这个 rc=14 不是新失败层**：它是 H1d 具名的收尾家族——playable 落账后 harness 主动停会话、host 客户端先死、
Core 把这场停记成 `BRIDGE_LOST`（V3 d1 的 host 半边同一形状收尾）。世界半边 `world_snapshot.digest` 仍是
`5c14c5638566a8b3f3cdb330cf14c1b30738fa37f2281f8e4b0020bb4401819e`，与 V3 两轮一致。
joiner 半边 `225:[04:56:10] [Server thread/INFO]: Kin2 left the game` —— 是走后散场，不是到不了。

### 3(f) ⑤ 家族的字节口径（run a，逐文件；「没有该文件」具名为没有该文件）

| 被检文件（run a 期间存在/产生者） | size | `0x1000E` | `XDG_RUNTIME_DIR is invalid` |
|---|---|---|---|
| `/tmp/domain-join-session.err`（已存 `out/a/tmp/`） | 0 | 0 | 0 |
| `/tmp/domain-client-environment.err`（已存 `out/a/tmp/`） | 0 | 0 | 0 |
| `/tmp/domain-session.err`（已存 `out/a/tmp/`） | 0 | 0 | 0 |
| `/data/kin/kin-v4-join/run/session/3629bff1c1894a8292b024ebfe878bf3/generation-1/logs/stderr.log` | 0 | 0 | 0 |
| 同 overlay `logs/latest.log` | 31050 | 0 | 0 |
| `/data/kin/kin-v4-host/run/session/bb8cfb121f27420e9797ac3a07728ecf/generation-1/logs/stderr.log` | 0 | 0 | 0 |
| joiner `crash-reports/` | — | **该阶段根本没产生任何 crash 文件**（find 无输出） | 同左 |

加入者被交到的环境同轮为健康（`out/a/client-environment.txt`，逐字节选）：
`launch XDG_RUNTIME_DIR=/tmp/minekin-client-runtime/runtime.lns2qs`、
`launch XDG_RUNTIME_DIR_ORIGIN=provided-by-harness`、`launch DISPLAY=:99`、
`launch GL_BACKEND=llvmpipe (LLVM 20.1.2, 256 bits)`、`launch WRAPPER=inside-wrapper`。
**V3 的 bounded-exclusion 从此升级为实量排除**：那不再只是「JVM 没起所以没脸复现」——1.20.1 客户端
真起了、真渲染了（`Backend library: LWJGL version 3.3.1 SNAPSHOT` 一类行在 log 里）、真进世界并 `PLAYABLE`，
两个具名串在它自己的每个stderr/crash 候选文件里都是 0 命中。

## 4. 1.21.4 正对照（run b）

- **b1**（缺 1.21.4 桥 jar 的第一次）：host 死在供给具名、420s 无发布，`domain: session exited 11`。
  `/tmp/domain-session.err` 逐字：
  `{"category": "SUPPLY_CHAIN", "component": "launcher.recipe", … "message": "the Bridge jar has not been built: /src/bridge/build/libs/minekin-bridge-0.0.0.jar is missing; run \`./gradlew build\` in the bridge directory", …}`
  ——供给链是活的，不是恒绿；也直接促成了 §1.1b 的例外申报。
- **b2**（补齐 pin 相等的那枚 jar 后同 argv 重跑，host=`kin-v4-host1214`、窗口 420s）：
  `R4: domain.sh rc=14 finished_utc=2026-09-27T05:08:51Z`。
  两侧 `Loading Minecraft 1.21.4 with Fabric Loader 0.16.9`；`Kin2 joined the game`；
  `domain: the world heard Kin2 arrive` + `domain: Kin2 admitted its first snapshot of that world`；
  joiner 文档 `connection_state: PLAYABLE, snapshots_admitted: 1, entities_admitted: 73`；
  ⑤ 家族同样逐文件 0 命中，无 crash 文件。
  **加入者拿到的文档回到冻结 v1 形状且逐字节不变**：`out/b/domain-join-profile.json`
  = `"schema_version": 1, … "minecraft_version": "1.21.4"`，sha256 `634abc28ac0c4652fd40f2e82867f632cf68b2354eccd7ba75c62c7f49148137`
  ——与 H1g 读数③ 在主干上量的那份**同一枚摘要**。驱动方式本身能出可读结果，1.21.4 路由没漂。

## 5. 版本错配反证（run c）——准入真在读字段，而且 ⑤ 家族是真的

在已备料的私有根上（`kin-v4-c` 的 store 由 `cp -al` 自 `kin-v4-host` 播种），用加入者自己的命令行形状
`session start --profile bundle-candidate-1.20.1.json --server-profile <文档> --connection-timeout-seconds 20`
驱动两份文档；唯一的本地目标是 `127.0.0.1:25570`，该容器里没有任何东西在听（loopback 只在容器内，
未连接任何远程服；这一点也解释了下面 match 的收尾）。

- **母文档 = run a 现场写出的那份 v2**（`/out/a/domain-join-profile.json` 原样拷入，sha `038dcf1e…`）。
- **错配文档** = 母文档只改一个字段：`allowed_versions: ["1.20.1"] → ["1.21.4"]`（sha `7f92e7fd…`，其余一字未动）。

```text
----- session start --server-profile /tmp/r4c/match.json
R4c: rc=14 (124 would mean the timeout fired)
R4c: match first stderr diagnostic:
R4c:   (no diagnostic line)
R4c: match launcher.profile named on stderr: 0
----- session start --server-profile /tmp/r4c/mismatch.json
R4c: rc=17 (124 would mean the timeout fired)
R4c: mismatch first stderr diagnostic:
{"category": "ADMISSION", "component": "launcher.profile", "context": {}, "evidence_ref": null, "message": "the session launches Minecraft 1.20.1, the target allows 1.21.4", "operation": "load", "retryability": "OPERATOR_ACTION"}
R4c: mismatch launcher.profile named on stderr: 1
```

- **错配半边**：JVM 之前、`launcher.profile` 具名拒用，rc 17 —— 准入读的就是 `allowed_versions` 这一个字段，不是恒绿。
- **匹配半边**：越过准入（stderr 无 diagnostic、`launcher.profile` 命中 0），客户端 JVM 真起
  （overlay `latest.log` 首行 `Loading Minecraft 1.20.1 with Fabric Loader 0.19.5`，台账 `BridgeHelloAccepted`），
  因为没有世界可连，20s 连接期限后以 `connection_state: REQUEST_ACCEPTED` / `BRIDGE_LOST` / rc 14 收掉
  （`out/c/match.session.json`）。
- **⑤ 家族在这条裸驱动线上当场复现**（这正是它「是真实故障家族」的最强证据，也反证 §3(f) 的 0 命中不是检查失效）：
  overlay `logs/stderr.log`（65 字节，全文）逐字：`error: XDG_RUNTIME_DIR is invalid or not set in the environment.`；
  `crash-reports/crash-2026-09-27_05.15.11-client.txt` 第 7 行逐字：
  `java.lang.IllegalStateException: Failed to initialize GLFW, errors: GLFW error during init: [0x1000E]135947197726096`。
  两个串都量在**产生它们的文件自己身上**（`out/c/match-stderr.log`、`out/c/match-crash-client.txt`，
  sha256 见 §6）。**边界**：这条线没有 domain.sh 的 wrapper 补投（无 Xvfb、无 harness 提供的
  `XDG_RUNTIME_DIR`）——它复现的是「环境没给够时家族会开火」，不构成对受控路径（a/b）的任何指控；
  受控路径的 0 命中判定仍以 §3(f) 的逐文件表为准。

## 6. 材料、路径与诚实披露

- 运行材料保留在 V 私有根（不入仓）：宿主 `C:/Users/darling/Documents/agent_work/minekin-wt-v4/.tmp/v4/out/{a,b,c}/`
  （`00-header.txt`、`90-readouts.txt`、两份 run 文档、profile 文档、`client-environment.txt`、`tmp/domain-*`、
  c 的 crash/stderr/latest/match/mismatch 原件），以及 docker 卷 `minekin-v4-join` 里
  `/data/kin/{kin-v4-host,kin-v4-join,kin-v4-host1214,kin-v4-join1214,kin-v4-c}/run/session/<id>/generation-1/` 的
  全部 overlay 日志与 crash-reports。c 材料 sha256（容器内实测）：
  `match-crash-client.txt=1917cd55c98d4ad4c66a4d584896101738e12daf6ebe537af20fbebb699b9c4a`、
  `match-stderr.log=f88c93af9ad8a41bd8c0c285e21ecc1cf7a68437dce4c86ced84e35276eac5c8`。
- **披露 1（转写来源）**：a、b 的 `docker run -d` 容器在我抽取 `docker logs` 之前被我 `docker rm`，
  所以 `domain: the world heard Kin2 arrive` 一类 harness stderr 行是**轮询时从 `docker logs` 逐字转写**，
  不在 out/ 文件里；所有文件型证据（run 文档、profile、日志、crash）仍在盘上可复核。
  b1 的 `90-readouts.txt` 被 b2 同目录覆盖，b1 只剩本节转写的两行。
- **披露 2（超出卡片文字一步）**：§1.1b 的 1.21.4 桥 jar 复制。
- **披露 3**：b1 在 host 供给死掉前已创建 `kin-v4-join1214` 并 `cp -a` 了它的 store；b2 复用之，
  故 b2 的 joiner store 不来自 b2 当轮的复制动作——读数不受影响（b2 joiner 真实起 JVM、真实进世界）。
- 本轮**未**跑任何仓内测试/门禁（卡片没要求 V 跑，且 `src/**`、`tests/**`、`tools/**` 零改动）；
  `git status --short` 交付前只有本记录一项。

## 7. 判定与四态

- **最先失败层**：**没有**。卡片七项全部到达并 `PASS`；两个受控 run 的 rc=14 是 H1d 具名的「harness 停活会话」
  收尾家族，不是准入/供给/握手/JOIN 任何一层失败。E6 的前置（真 JOIN + 首快照 + 同 run 可封材料）在
  **V 私有意义上已经成立**，是否派 E6 由 M 决定。
- **已合主干**：无 V 产出；本卡输入 H1g（`ff69c879…` 字节）已在 `8b357b6`。
- **仅在分支**：本记录一份文件。
- **真实封证**：**零**——V 不封存。本节所有「量到」= 活进程 + 活字节 + 在盘原件，不是 sealed evidence。
- **未验证（按边界不去、不测）**：任何远程/公网目标（未连接，`.tmp/local-test-server.txt` 未打开）；
  `::1` IPv6 loopback 形状（runner 仍写 `127.0.0.1`）；`--auto-bundle`×joiner（按 `domain.sh:404-407` 原样被拒）；
  多 joiner/并发；`session start` 在**完全空 store**上的形状（H1g ②c 已量，本轮刻意不再需要）；
  在线认证、判据/registry/封存 schema 的任何变化（一律未触碰）；
  PLAYABLE 之后的输入/动作半边（本卡问的是加入，不是操作世界）。
