# V1201-CAMPAIGN-JOINER-ARRIVAL-001（#66 H66）交付记录

分支 `codex/minekin-h66-campaign-joiner-arrival`，起点笔 `527b6a75adeba6fd0bc0c13e40e1ce6838fec74f`
（= 卡面 #66 第六十八轮派工时记的远端 `main`）。本记录由**收尾轮**写：判据已由前一轮 lane 量完、
代码已写、活体材料已存盘，但交付字节留在未跟踪备份里、未提交未 push。本收尾轮做的只有四件事：
把字节种回 tracked 文件、补契约里缺的那一格、逐道读门、把读数写成文档并 push 自己的分支。
**没有重做设计、没有新增功能、没有放宽任何判据。**

## 0. 现场（接手时现读）

- 工作树 `C:/Users/darling/Documents/agent_work/minekin-wt-h66`，`git rev-parse HEAD` = `527b6a75`，
  `git status --porcelain` 空（tracked 干净）。
- 本地 remote-tracking 读数 `refs/remotes/origin/HEAD` = `af32e35d4ac109c8810fae8e381a83d84a6e14bd`
  （**旧值**：本收尾轮没有 `fetch`，不动工作树；远端真值只在 §7 的 `ls-remote` 回写里核自己那支）。
- 起点字节：`test-orchestrator/runner/domain.sh` = `65947145714373b7c38d1015026f1e5b9eacc4f08d5650f78007a58108b41386`
  / 3276 行（`.gitattributes` 对 `test-orchestrator/runner/*.sh` 强制 `eol=lf` ⇒ 工作树摘要 = blob 摘要 = 卡面值）。
  `tests/contract/test_runner_scripts.py` 工作树 = `a22528f7fc63359acca99dfd384bfe2d88d659126e721e5405b305e4f27ce396`
  / 4490 行 CRLF，对应 git blob `34a8f393e7c77b1759e2df4275e4777bcdee77fb263b32802e5e4469e2f30f37`
  （`*.py` 受 `core.autocrlf=true` 归一，故两种摘要不同、`git status` 仍干净）。
- 备份字节（本收尾轮的种回源，逐枚现读 `sha256sum`）：
  `.tmp/h66/backup/domain.sh.delivered` = `cbec5b85142d2168afcb46551d879dcd23159e62c89f21e422c7a69221ab8a82`（3292 行，LF），
  `.tmp/h66/backup/test_runner_scripts.py.delivered` = `604d271c5f4532fe7557af445840f60683b9916240b15b2f63c9b37b67316061`（4694 行 CRLF），
  另有 `domain.sh.origin` = `65947145…`（与起点同值）、`test_runner_scripts.py.origin` = `34a8f393…`（blob 面）、
  `test_runner_scripts.py.origin.working` = `a22528f7…`（工作树面）。
- `domain.sh` 的改动只有三个 hunk（`@@ -1613 / -1623 / -1639`，+28/−6）：加入者侧「下游读数」的探测端口
  从 `${lan_port}` 换成本 run 实际拨向的 `${joiner_target_port}`、四处 verdict 文案里的端口一起换、
  新增具名区域标记 `joiner-downstream-reading-target`，其余全是注释。允许面没有越界：
  本卡最终只动 `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py`、
  本记录、自己的 `.tmp/h66/**`；`tools/**`、`src/**`、`tests/fixtures/cases/**`、`run.sh`、镜像/Dockerfile、
  `.github/**` 零改动（`git diff --name-only` 只有前两枚）。

## 1. 本卡判出来的问题在哪一层（不是「`--case` 让加入者进不了场」）

**「专服形状 + `--case` ⇒ 加入者必不到场」不成立。** 三式都到场并封出 bundle，逐式原文见 §3。
本卡唯一的确定性缺陷是**加入者侧下游读数探错了端口**：分类器拿 LAN 端口（25570）去问「世界在不在」，
而这一形状真正拨的是它自己的受控专服绑上的端口（25566）。于是**一次客户端侧的崩溃被误报成
「证据在世界那一侧」**。盘上原文（M 自己在 `minekin-m-v5p-live` 上那一路 `--case` 式，同一份 stderr）：

- `.tmp/h66/material/domain-stderr.log:4`
  `domain: the joining client dials the controlled server this run started at 127.0.0.1:25566, read from /data/server-runs/run-4/server.properties`
- `.tmp/h66/material/domain-stderr.log:10`
  `domain: downstream reading — THE_WORLD_STATUS_IS_NOT_PROBEABLE: nothing answers 127.0.0.1:25570 while the client screen measured (llvmpipe (LLVM 20.1.2, 256 bits)), so this run is evidence about the world and not about the client environment`

同一个 run、同一个循环回环地址、两行不同的端口：拨的是 25566，问的是 25570。那句
`evidence about the world and not about the client environment` 说的不是它自己的世界——这一形状
根本不发布 LAN 端口（`MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`）。这就是把 #66 指向世界侧的那一格。

同时，M 那一路带回来的 `Failed to initialize GLFW … [0x1000E]`（`Description: Initializing game`，
栈在 `RenderSystem.initBackendSystem`，崩溃报告摘要 `9f2db49e…`）在本环境**没被复现成 `--case` 的确定性属性**：
三式到场路径都写出 `no NEW crash report`（§3 倒数第二列）。本卡如实把它记成**单发的客户端初始化崩溃**，
并且**未量到它为什么单发**（§8）。

## 2. 交付字节的两面证据（`file:line` + 原文）

### 2.1 端口是从本 run 读出来的，不是假设的

`test-orchestrator/runner/domain.sh:1263–:1310` 是既有具名区域 `joiner-controlled-server-target`（H1k/H1q 面，本卡未动其判定）：

- `:1281` `    joiner_target_port="${lan_port}"` — 没有受控专服请求时，目标就是 LAN 端口（⇒ 关闭态/旧形状两数同一）。
- `:1306` `        joiner_target_port="${controlled_server_port}"` — 有受控专服时，端口从
  `${server_directory}/server.properties` 现读（`:1289–:1301` 读不到数字或 `server-ip` 不是 `127.0.0.1` 字面量就
  `exit 2` 具名拒止），并打印 `:1307–:1308`
  `domain: the joining client dials the controlled server this run started at %s:%s, read from %s`。
- `:1311` `    python - "${joiner_target_port}" /tmp/domain-join-profile.json "${launched_version}" <<'PY'` —
  写进加入者 profile 的也是这一枚。

### 2.2 分类器现在问的是同一枚端口

- 起点字节 `:1629`：`    timeout 5 bash -c "exec 3<>/dev/tcp/127.0.0.1/${lan_port}" 2>/dev/null || probe_rc=$?`
- 交付字节 `:1644`：`    timeout 5 bash -c "exec 3<>/dev/tcp/127.0.0.1/${joiner_target_port}" 2>/dev/null || probe_rc=$?`
- 新增具名区域 `:1640` `# --- joiner-downstream-reading-target begin (the contract test extracts this region) ---`
  ／ `:1673` `# --- joiner-downstream-reading-target end ---`（契约按名提取的就是这一对）。
- 三处 verdict 文案里的端口同步换掉（交付 `:1657` / `:1664` / `:1666`）：
  `THE_JOINER_SCREEN_WAS_UNMEASURABLE while the world was listening on 127.0.0.1:'"${joiner_target_port}"' …`、
  `BOTH_HALVES_NAMED_AND_BOTH_BAD: nothing answers 127.0.0.1:'"${joiner_target_port}"' …`、
  `THE_WORLD_STATUS_IS_NOT_PROBEABLE: nothing answers 127.0.0.1:'"${joiner_target_port}"' while the client screen measured …`。
- 全仓仍只问一发循环回环、且问的是本 run 的目标：契约 `:2670`
  `assert re.findall(r"/dev/tcp/([^/\"]+)/", text) == ["127.0.0.1"]`。地址口径没有放宽（不是远程地址、不是常量端口）。

`joiner-server-log-seal-guard`（`:545–:566`）本卡**未改一个字节**：`:553` 那句
`MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG hands the server log back to a case sealed on the joining run and this run seals its case on the host (MINEKIN_DOMAIN_CASE_ON is %q); …`
连同另外两枚拒止与三处 `exit 2` 全保留（活体负对照见 §3 的 `nocase-literal` 一行）。

### 2.3 契约新增／补的那一格（本收尾轮的申报）

`tests/contract/test_runner_scripts.py`（交付字节 `604d271c…`，本轮补一格后为 `e3a68c74…`）：

- `:2473` `DOWNSTREAM_READING_REGION = "joiner-downstream-reading-target"`；`:2476` `downstream_reading_region()`
  按名取区（`text.index(begin)` 取不到即抛 ⇒ 见 §5 的 M2 反证）。
- `:2487` `a_loopback_listener()`（真在 `127.0.0.1` 上 `bind+listen` 一枚临时端口，socket 与数字同行返回）、
  `:2503` `a_closed_loopback_port()`（绑完即关，给出「没人答」的端口）、`:2513` `drive_downstream_reading()`
  把区域字节经 `run_shelled` **真过 bash** 跑一遍，喂两枚不同号（`lan_port` / `joiner_target_port`），
  读回 `client_environment_readout` 里那一行 `downstream …`，并要求恰好一行。
- `:2556` `test_the_downstream_reading_probes_the_port_this_run_dialled`：
  - `:2592` `lan_shaped = region.replace("${joiner_target_port}", "${lan_port}")` = 改回前的形状（一处变量名、四处）；
  - `:2593` `assert lan_shaped != region, "the planted mutation changed nothing; nothing was measured"`
    ⇒ **删掉判据必红**的那一格：字节没变就说明什么都没量；
  - `:2618/:2619` 分歧读数：拨向端口有人听、LAN 端口没人听时，交付字节说
    `THE_JOINER_HAD_NOT_ARRIVED_IN_THE_WINDOW`，改回的字节说 `THE_WORLD_STATUS_IS_NOT_PROBEABLE`
    ——绿不是恒真，是靠一次真实分歧量出来的；
  - `:2631` 两数都无人答时，句子必须点名**本 run 拨向**的那枚（`:2632–:2633` 断言出现 `127.0.0.1:<dialled>`、
    不出现 `127.0.0.1:<lan>`）；
  - `:2664` 默认关闭态逐字节等值：两数同一（`joiner_target_port == lan_port`，旋钮之前的每一个形状）时，
    改前／改后打印出的句子 `after == before` 字符级相同，两个点名端口的分支各测一遍；
  - `:2671` `assert "/dev/tcp/127.0.0.1/${lan_port}" not in region`。
- **本轮补的一格（唯一一处由收尾轮写的判据面改动）** `:2675` `assert "lan_port" not in region`——
  卡面要求「`${lan_port}` 不再出现在该区域」，原字节只对**探测那一行**作了要求。补后整区零命中
  （`sed -n '1640,1673p' … | grep -n lan_port` 无输出），并把这条写死：LAN 端口可以被 run 设置（`:1281` 就是），
  但分类器**一次都不读**它。补格后重跑：契约 124 格全绿（§6）。
- 既有的 `joiner-server-log-seal-guard` 格（`:1607` 按名取区、`:1633/:1643` 区界与三处 `exit 2` 普查、
  含「删守卫 ⇒ rc≠2」的非恒真变异与「先拒后写」的行号证明）**本卡未动**，仍在 123→124 的绿里。

## 3. 四式活体读数（含作废那式）

私有卷 `minekin-h66-live`、Kin 根 `kin-h66-host` / `kin-h66-join`、桥产物 `e50d61c2…`（1,310,604 B）、
服务端 jar `3af73a9d…`、配方 fixture `709a8899…` / `3864edda…`（逐式 `00-header.txt` 现读记录）。
生效 `domain.sh` 摘要取自各式 `00-header.txt` 的 `domain.sh in use (/src, read-only mount)` 那一行。
串行跑（一轮战役墙钟 9–10 分钟，两式不得抢同一台引擎）；`../minekin` 与 `../minekin-wt-integration` 只读；
规范卷 `minekin-runner-data` 全程不挂（只出现在 §6.3 那条 `:ro` 复算里）。

| 式 | 生效字节 | `--case` 侧 | 加入者到场 | 会话 outcome（加入者侧原文） | 是否封出 | bundle 摘要 / 封存 run_id | 新 crash report | `domain.sh` rc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `nocase` | 起点 `65947145…` | 三枚全未设 | **是**：`domain: the world heard Kin2 arrive`、`Kin2 admitted its first snapshot of that world`；`server-runs/run-2/server.log` 有 `[22:25:06] Kin joined the game` / `[22:25:07] Kin2 joined the game`（`server.log` sha `b6546d56…`，18,912 B） | `{'outcome': 'BRIDGE_LOST', 'connection_state': 'PLAYABLE', 'snapshots_admitted': 1, 'entities_admitted': 16}` | 否（该式不问） | — | `no NEW crash report`（基线携带 1 枚） | 14（会话按 soak 到点自停，`session exited 14`） |
| `case` | 起点 `65947145…` | `MINEKIN_DOMAIN_CASE=v1201-lan-joiner-control-case-001`、`_CASE_ON=joiner`、`_SEAL_JOINER_SERVER_LOG=1` | **是**：`out/case/domain-stderr.log:8` `domain: the world heard Kin2 arrive`、`:9` `Kin2 admitted its first snapshot of that world`、`:14` `domain: this run is 4edcfd71195f432cab85e26a5dd14ef3`（`server-runs/run-1`） | `{'outcome': 'BRIDGE_LOST', 'connection_state': 'PLAYABLE', 'snapshots_admitted': 1, 'entities_admitted': 21}` | **是**（`status=sealed`、14 枚 artifacts、`evidence verify` ⇒ `sealed:true verified:true violations:[]`） | `7e0e1b9cc136b7f84b21029480a7d093b351d19dc153ef9a60d577d42b8fc33b` / `697eadafb95d4793a1e094f72dda3d18`，`attempt_sequence=1`，`result=FAIL` | `no NEW crash report`（基线携带 1 枚） | 未打印（读数助手在第 69 行撞 `rc: unbound variable`，见 §4） |
| `case2` | **交付 `cbec5b85…`** | 同 `case` 三枚 | **是**：`server-runs/run-4`；`domain-stderr.log:8` `the world heard Kin2 arrive`、`:9` `Kin2 admitted its first snapshot…`、`:13` `this run is dccfd344c4954530a1ab99739b755db8`；`server.log`（sha `2c6904c1…`）里 `[22:33:29] Kin joined the game` + `[22:33:29] Kin2 joined the game` | `{'outcome': 'BRIDGE_LOST', 'connection_state': 'PLAYABLE', 'snapshots_admitted': 1, 'entities_admitted': 23}` | **是**（`status=sealed`、14 枚 artifacts、无 crash report） | `2124da30fb3f3cb7f2e067f3e13434f23fcf8afee1ee72112276de53e38a0d6b` / `aa5524bc4e1d4b38a8f7213e7ced1e0c`，`attempt_sequence=2`，`result=FAIL`，`the case verdict is FAIL` | `no NEW crash report`（基线携带 1 枚） | 1（案未 hold） |
| `nocase-literal` | 起点 `65947145…` | `--case` 缺席、`_SEAL_JOINER_SERVER_LOG=1` | 未到（**按构造不该到**：run 在开局守卫处停） | — | 否 | — | 卷上原有基线崩溃报告 `9f2db49e…`（`Description: Initializing game` / `Failed to initialize GLFW … [0x1000E]`）仍在那一 generation 目录里，**不是本式写的** | 2 —— `domain: MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG hands the server log back to a case sealed on the joining run and this run seals its case on the host (MINEKIN_DOMAIN_CASE_ON is host); …`（默认关闭态的形状守门，逐字来自 `out/nocase-literal/domain-stderr.log:1`） |
| `case2-aborted-by-mid-run-edit` | 起点 `65947145…`（开跑时），中途 `/src` 里的 `domain.sh` 被改 | 同 `case` | 到场过（`server-runs/run-3`，`[22:31:18] Kin joined the game`、`[22:31:32] Kin2 joined the game`）**但此式作废** | — | 不作读数 | — | 不读数 | 127 —— `/src/test-orchestrator/runner/domain.sh: line 2244: at: command not found`；容器按执行时读文件，跑一半改字节 ⇒ 材料保留、不用于任何结论 |

两式差集（卡面 §2.1 要的 A/B）因此是空的：`--case` 与不带 `--case` 在这一形状上**加入者都到场**，
所以 §1 的靶面不在编排那一侧，而在读数那一侧的端口号上。

## 4. 具名更正：`out/case/90-readouts.txt` 与自己打出来的原文相反

该式（起点字节、`--case`）的读数块打出：

- `:3` `H66:   the env line WAS NOT PRINTED (the run never reached the joiner launch)`（`out/case/90-readouts.txt:3``
- `:37` `H66: server_directory=UNREAD`
- §(2)（是否到场）、§(4) 的 outcome 行、§(5) 的 verdict 行均为空，末尾 `:39` 是
  `H66: every stderr line, verbatim:`，之后一行也没有（全文件就到 39 行）。

而同一目录的 `out/case/domain-stderr.log`（5,568 B，mtime `2026-09-28 06:20:19 +0800` = 该式战役结束那一刻）
第 6 行就是 `domain: joiner client environment before its JVM: harness DISPLAY=:77 … GL_PROBE_RC=0 harness WRAPPER=direct`，
第 8/9/14 行是到场与 `this run is 4edcfd71…`，第 26/28 行是 `the case verdict is FAIL` 与 `did not hold for this run`。

**这是读数脚本的缺陷，不是 run 的性质**，不得把它的摘要当结论：

- 成因（盘上可查的部分）：`.tmp/h66/out/case.run.log:31` 记
  `/drv/h66-drive.sh: line 69: rc: unbound variable` —— 当时部署的读数助手摘要是 `3539c357ffdfea28098f9f6cc09f004342d4bf6b226253dbbcacab2b69e27826`，
  **不等于**在库副本 `.tmp/h66/h66-drive.sh` 的 `271048dc9b55b46ceedd2a93a26be5f9b2d40ba5ea85dfe0a0e31ea8c939e248`（后者是修好的版本，
  `rc=$?` 在 `:68` 之后、`:70` 才用 `${rc}`）。该块里凡是从 `${out}/domain-stderr.log` 做 `grep` 的格子（§1/§2/§4 outcome/§5 verdict/§6 server_directory）
  全部打印为空，而凡是直接读卷或读 `/tmp` 文件的格子（§3 崩溃基线差分、§4 `:25` 的 `domain-join-session.json bytes=1852`、
  §5 `:34` 起的 `seal report verbatim`、§6 `server-runs after: run-1`）有读数。此式也没有 `H66: domain.sh rc=` 那一行。
  部署副本的字节没留在盘上，所以只能定位到「哪一格、按什么方式坏」，不能给出改前改后的逐字节差分——这一格按未量清处理（§8）。
- 处置：`out/case/**` 材料不删不改；结论一律以 `out/case/domain-stderr.log` 原文为准。后续三式（`nocase` / `case2` /
  `nocase-literal` / `case2-aborted-by-mid-run-edit`）用的是修好的助手，§1/§2/§5/§6 都有读数（`case2` 的
  `server_directory=/data/server-runs/run-4` 可作对照）。
- 顺带记一处同源的小缺陷（不影响任何结论）：§(6) 的按名计数 `Kin 0` 后面又跟一行裸 `0`——
  `h66-drive.sh:163` 的 `grep -c … || echo 0` 在计数为 0 时既打印 `0` 又触发回退。名字盲（`Kin` 也匹配 `Kin2`）
  是主干 §2.51 已记过的口径，本卡不改。

## 5. 反证普查（判据不是恒真）

`.tmp/h66/mutation-census.sh` ⇒ `.tmp/h66/mutation/census.log`。每次变异前先把 tracked 字节
`cp` 到 `.tmp/h66/mutation/domain.sh.delivered.copy` 并记摘要，做完按摘要复验；全程没有
`git checkout --` / `restore` / `reset --hard` / `stash`。

| 变异 | 变异后 `domain.sh` 摘要 | 跑的格 | rc | 末行 |
| --- | --- | --- | --- | --- |
| 改前 | `cbec5b85…`（3292 行） | — | — | 起点 |
| M1：区域内 4 处 `${joiner_target_port}` → `${lan_port}`（即改回前的字节形状） | `dc0a7ac40491a5b9011acd3d4f024291d125793d934137c0a920d99a62759ad3` | `-k downstream_reading_probes_the_port` | **1** | `1 failed, 123 deselected in 2.33s`；`AssertionError: the planted mutation changed nothing; nothing was measured`（`test_runner_scripts.py:2593`） |
| 复验 | `cbec5b85…` | — | 0 | `restored sha256=cbec5b85… expected=cbec5b85…` |
| M2：删掉区域的 begin/end 两行标记（判据无法被按名提取） | `51f18ee629a949aa6122c3e3500e978345856af3ce35293dd7496cced67deac5` | 同格 | **1** | `1 failed, 123 deselected in 0.29s`；`ValueError: substring not found`（`test_runner_scripts.py:2481`） |
| 复验 | `cbec5b85…` | — | 0 | 同上 |
| M3：交付字节复跑同格 | `cbec5b85…` | 同格 | **0** | `1 passed, 123 deselected in 12.74s` |

M1 说明「把判据撤掉就红」，M2 说明「判据不被按名提取就红」，M3 说明红不是脚本自己坏了。
另外普查助手自己有一处无害缺陷，如实记：`census.log` 里出现三次
`.tmp/h66/mutation-census.sh: line 22: $1: unbound variable`——`say` 被空参调用（我自己写的这轮脚本，
`set -u` 下报警后继续），不影响任何 rc 读数与复验。

## 6. 门表（步骤取自 `.github/workflows/ci.yml` 自己的 `- run:` 行，逐道单跑、先落盘再读 rc）

门名单来自 `.github/workflows/ci.yml` 的 `python` job `:44–:55` 十二行，另加本仓惯例的
`bash -n test-orchestrator/runner/domain.sh`、`bash -n test-orchestrator/runner/run.sh` 与 `git diff --check`，
再加本卡的契约单文件格 ⇒ 16 道。harness：`.tmp/h66/gates.sh <pre|post>`（两遍**同一支脚本、同一串命令行**）；
PRE 字节 = 起点 `65947145…` / `a22528f7…`，POST 字节 = 交付 `cbec5b85…` / 最终契约 `e3a68c74…`。
逐道完整输出在 `.tmp/h66/gates-pre/`、`.tmp/h66/gates-post/`，整表 stderr 在
`.tmp/h66/out/gates-pre.run.log`、`.tmp/h66/out/gates-post.run.log`。

**引擎与 interpreter（两条读数面，配对用同一套）**：宿主 `uv 0.11.21` + `Windows` 上锁死的 `.venv`；
容器 `minekin-runner:local` = 引擎 `29.5.3 linux/amd64`、CPython 3.12.3、pytest 9.1.1。
镜像里**没有 `uv`**（实测 `command -v uv` ⇒ MISSING；把上一轮 lane 的 `.tmp/h66/run-gates.sh` 原样再在容器里跑一遍，
13 道 `uv` 前缀的门全部 `rc=127` `timeout: failed to run command 'uv': No such file or directory`，只有两道 `bash -n` 是 0 ——
日志 `.tmp/h66/gates-image-probe/summary.log`、`.tmp/h66/out/gates-image-probe.run.log`），
镜像解释器也**没有 dev 额外包 `jsonschema`**（实测：全量在容器里 `3 errors in 6.96s`、rc=2，
`E ModuleNotFoundError: No module named 'jsonschema'`，撞 `tests/contract/test_fixture_boundaries.py`、
`tests/contract/test_server_profile_schema.py`、`tests/unit/test_fault_injection.py` 三枚收集期；日志
`.tmp/h66/gates-image-probe/pytest-full-in-image.log`。本表第一次 PRE 试跑也量到过同一形状（`3 errors in 12.94s`，
该日志随后被同源 harness 的正式 PRE 覆写），所以本轮把它在探针目录里重量了一遍、把字节留在盘上。
所以 `uv` 前缀的 CI 道走宿主、全量走宿主锁死 venv，纯 pytest／纯 `python tools/*.py` 里跑得动的四道走容器。

| 道（log 名） | 引擎 | PRE rc | PRE 末行 | POST rc | POST 末行 |
| --- | --- | --- | --- | --- | --- |
| `bash-n-domain.log` | 宿主 bash | 0 | （空） | 0 | （空） |
| `bash-n-run.log` | 宿主 bash | 0 | （空） | 0 | （空） |
| `uv-sync.log`（`uv sync --locked --dev`） | 宿主 uv | 0 | `Checked 18 packages in 3ms` | 0 | `Checked 18 packages in 3ms` |
| `ruff-check.log`（`uv run ruff check .`） | 宿主 uv | 0 | `All checks passed!` | 0 | `All checks passed!` |
| `ruff-format.log`（`uv run ruff format --check .`） | 宿主 uv | 0 | `374 files already formatted` | 0 | `374 files already formatted` |
| `pyright.log`（`uv run pyright`） | 宿主 uv | 0 | `0 errors, 0 warnings, 0 informations` | 0 | `0 errors, 0 warnings, 0 informations` |
| `pytest-full.log`（`uv run pytest`） | 宿主 uv | 0 | `2711 passed, 2 skipped in 311.90s` | 0 | `2712 passed, 2 skipped in 315.34s` |
| `wheel.log`（`uv build --wheel`） | 宿主 uv | 0 | `Successfully built dist\minekin_core-0.0.0-py3-none-any.whl` | 0 | 同 PRE |
| `wheel-boundary.log` | 宿主 uv | 0 | `Wheel oracle boundary: OK (…whl)` | 0 | 同 PRE |
| `cli-help.log`（`uv run minekin --help`） | 宿主 uv | 0 | `-h, --help            show this help message and exit` | 0 | 同 PRE |
| `diff-check.log`（`git diff --check`） | 宿主 git | 0 | （空） | 0 | （空） |
| `contract.log`（`python -m pytest -q tests/contract/test_runner_scripts.py`） | 容器 CPython | 0 | `123 passed in 2.20s` | 0 | `124 passed in 2.20s` |
| `boundaries.log` | 容器 CPython | 0 | `Minekin package dependency boundaries: OK` | 0 | 同 PRE |
| `case-assertions.log` | 容器 CPython | 0 | `Case assertion implementations: OK (151 registered)` | 0 | 同 PRE |
| `fixture-digests.log` | 容器 CPython | 0 | `W00 schema and fixture digests: OK` | 0 | 同 PRE |
| `workflow-pins.log` | 容器 CPython | 0 | `Workflow pins: OK (every action is a commit, and each names its release)` | 0 | 同 PRE |

PRE 与卡面基线**逐字同源**：起点 `domain.sh 65947145…`/3276 行 ✓、契约 `123 passed` ✓、
全量 `2711 passed, 2 skipped` ✓、`374 files already formatted` ✓、pyright `0 errors` ✓、
`OK (151 registered)` ✓。16 道两遍全部 rc=0（`rc0_count=16`）。
POST 契约 `124`、全量 `2712` ⇒ **净增恰好 1 枚**（本卡新增的下游读数格；`+1` 之外没有别的量移）。
两遍都比上一轮 lane 那次多做的准备：`MINEKIN_HOME=/tmp/minekin-home-h66`（不落 `/data`），
每次起容器前先 `docker ps` 安静检查（`engine.log` 记 `server=29.5.3 os=linux/amd64`）。

`ruff format --check` 的 374 files 是在**本记录尚未落盘**时量的（PRE/POST 配对必须同口径）。
本记录落盘后再单跑两道（`.tmp/h66/gates-post/ruff-check-with-record.log`、
`.tmp/h66/gates-post/ruff-format-with-record.log`）：`All checks passed!` rc=0、`375 files already formatted` rc=0
——多出的一枚就是这条 md 本身，口径与主干 §2.56/§2.58、`v1201-h1q-…md` §3 那条注记同一。

### 6.3 门载荷（唯一一条规范卷 `:ro` 只读复算）

`.tmp/h66/gate-payload.sh <pre|post>`，命令面逐字沿用 `docs/validation/v1201-h1o-forward-seal-knobs-2026-09-28.md` §7：
容器内 `python /src/tools/report_promotion.py --data-root /data`，`-v minekin-runner-data:/data:ro`
（**只读**；不建 attempt、不写 `/data`、零 JVM），`/src` 也只 `:ro`；摘要子集算法
`sha256(json.dumps({"work_packages","overall"}, sort_keys=True))`（`.tmp/h66/trunk_digest.py`，只读复用）。

| | 生效字节 | rc | 文档字节 | `gate_payload_sha256` |
| --- | --- | --- | --- | --- |
| PRE | `65947145…` / `a22528f7…` | 1（按构造 blocked：无 mandatory 可晋级） | 103,921 | `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` |
| POST | `cbec5b85…` / `e3a68c74…` | 1（同上） | 103,921 | `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` |

两份 stdout 逐字节相同（`cmp -s` ⇒ IDENTICAL；文件摘要同值
`b09cc1966ade4764224f8a218bcaf0598e52c513210852756cb03fdcaeecbb41`，与 `v1201-h1q-…md` §5 记的同一枚）。
**PRE == POST == 基线 `cfa0f118…63afd6`**：本卡不注册案、不动判据/registry/mandatory ⇒ 载荷必须同值，实测同值。
`rc=1` 是 blocked 的常态读数，不是门失败；日志 `.tmp/h66/out/gate-payload-{pre,post}.run.log`、
stderr 两遍都是 0 字节。

## 7. 提交与 push

- commit #1（实现 + 契约）`859ab1dcaa5c6863dbeb35f48acacf31609f6df3`：
  `test-orchestrator/runner/domain.sh`（`cbec5b85…`，3292 行）+
  `tests/contract/test_runner_scripts.py`（最终 `e3a68c74…`）。基线 `527b6a75adeba6fd0bc0c13e40e1ce6838fec74f`
  （H1q 合并后的干，即本卡起点）。
- commit #2（`docs(validation): …`）：本记录，只含本文件。
- push 只推自己那支：`git -c credential.helper= -c credential.helper=wincred push origin HEAD:refs/heads/codex/minekin-h66-campaign-joiner-arrival`；
  回写核对 `git ls-remote origin "refs/heads/codex/minekin-h66*"`。没有 push `main`、没有 merge、没有 `--amend`、没有 `--no-verify`。

## 8. 如实分开：量到了什么、没量到什么

**量到的**

- 加入者在专服形状 + `--case` 下**确实到场并封出 bundle**（`case`／`case2` 两式原文，§3）⇒ 卡面 §1 的
  「根本没进场」在这一层被证否；§2 的 A/B 差集为空。
- 端口判据的字节面（`:1629`→`:1644` 与三处 verdict）+ 驱动面（§2.3 那格的真 loopback 监听／真关闭端口）
  + 活体面（`material/domain-stderr.log:4` vs `:10` 的 25566/25570 互相矛盾）三条各自成立。
- 门 16 道逐道 rc=0 两遍配对；载荷 PRE==POST==基线；卷与资产摘要逐式记录在 `00-header.txt`。

**没量到的（不写成结论）**

1. **交付后的分类器新读数在活体面上一次都没被走到**：`classify_the_joiner_downstream_readings` 只在
   「等待窗口关闭时加入者未到场」那支被调（`domain.sh:1790`），本环境三式到场 ⇒ 五个 `out/*/domain-stderr.log`
   里 `grep "downstream reading"` 全部无命中。它的正确性目前只有契约驱动格 + M 留在卷上的旧误报两支撑，
   「专服形状 + `--case` + 加入者真的没到场时新句子点名 25566」这一格**在活体上未量**。
2. **GLFW `[0x1000E]` 崩溃为什么单发**：本环境未复现（三式都 `no NEW crash report`），既没量到它发生的条件，
   也没量到它不发生的原因；`Backend library: LWJGL 3.3.1 SNAPSHOT`、`GL_PROBE_RC=0`、两层屏深都可读
   （`client-environment.txt` 1–14 行）只排除了「屏一定没起来」这一种解释。不得据本记录断言它是 `--case` 的属性，
   也不得断言它永不再现。
3. **规范卷上的真实封证仍为 0**：§3 两枚 bundle（`7e0e1b9c…`、`2124da30…`）都是**私有卷 `minekin-h66-live` 的活体读数**，
   只证明形状，**不是** E7 要的「规范卷、同一 run 的加入者侧真实封证」；两者 `result=FAIL`
   （`move_input_was_leased:LEDGER_UNREADABLE`、`the_probed_player_is_this_run_s_kin:PROBE_ATTRIBUTION_NOT_RECORDED`），
   本记录不引它作任何求绿证据。
4. **这两枚 bundle 的身份不能当成「新 kin id 的同 run 封证」**：封存报告里的 `evidence_directory` 都落在
   `/data/kin/kin-v5p-join/run/evidence/…`，`run_id`（`697eadaf…`／`aa5524bc…`）是**加入者自己文档**里的 id，
   与该式打印的宿主 `this run is …`（`4edcfd71…`／`dccfd344…`）不同名；`out/case2/domain-join-session.json` 的
   `kin_id` 读 `kin-v5p-join`、宿主 run 文档的 `kin_id` 读 `kin-v5p-host`，而 `session stop` 与 overlay 路径用的是
   `kin-h66-*`。也就是说这一路的客户端身份是从只读资产根里带出来的 v5p 名字，卡面 §4 要求的「用新 kin id 起 run」
   在**加入者侧没有成立**。根因落在 `.github`／`tools`／客户端资产那一层之外，本卡不改、只具名登记。
   顺带记：`case2` 的 `attempt_sequence=2`（同案第二次尝试），`case` 是 1。
5. `out/case/90-readouts.txt` 的部署字节（`3539c357…`）没留在盘上 ⇒ §4 只能定位到格与失败方式，给不出逐字节差分。
6. 全量 suite 在本机 Linux runner 镜像里**量不到**（缺 dev 额外包，见 §6 的 rc=2 实测）；本文的全量读数来自宿主
   锁死 `.venv`（win32），两枚 skip 是 `tests/unit/test_orphans.py:686`（本平台答不出这个问题）与
   `tests/unit/test_silent_listener.py:123`（Windows 的 terminate 不是信号）。可比总量按
   `passed + skipped` 读：PRE 2713、POST 2714，与主干 §2.61 的 `2711 passed, 2 skipped ⇒ 2713` 同值后再 +1。
7. 卷与失败材料一件没删：`kin-v5p-*`、`server-runs/run-1..run-4`、`out/case2-aborted-by-mid-run-edit/`（作废那式）
   全部原样保留；`.tmp/h66/material/`（M 的副本）未改。
