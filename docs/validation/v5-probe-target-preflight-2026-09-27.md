# V5 探针目标前置活体量测（probe-target preflight）— 2026-09-27

- **Lane / 分支**：`codex/minekin-v5-probe-target-preflight`，base `8dfeac6`。
- **被测字节**：`test-orchestrator/runner/domain.sh` sha256 `ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4`（与本卡 base `8dfeac6` 的主干逐字相同，容器内 `00-header.txt` 复核）；桥产物 `bridge/build/libs/minekin-bridge-0.0.0.jar` = `0ee2070b97ba…`、`bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar` = `e50d61c209be…`（run A4 头两行逐字记录）。
  - **合入时的主干漂移（M 补，第四节修法同条）**：本卡入干时 `domain.sh` 已是 H1h 驱动区在位后的 `baad190aaa5ee1695a88b52e98cc270c8e1a4bc878a0bcd2d0c27f94b74ff6f3`（宿主侧 `sha256sum` 与容器内读数一致，`run.sh` 为 `70349060…`，H1j 的四个名字已在转发名单里）。H1h/H1j 只往加入者的 argv 里加**默认关闭**的限幅控制，不动「谁在答探针」与两条门的形状，故 §1、§2、§5、§6 的结论在新字节下逐条仍成立，M 已按字节复核（见 plan §2.13）；本卡量到的 `ff69c879…` 是它自己的历史事实，不追改。
- **本次不构成封证**：未跑 `seal_run_evidence.py`、未注册 case、未动 `tests/fixtures/**`、registry 与 `mandatory` 未动。**LAN 第二客户端控制封证仍为 0。**
- **任务问题**：在当前主干字节的 runner 上，把探针目标显式指向 LAN 加入者，服务端的回答行是否存在、可否按目标读数、「无控制时首末读数不变」是否成立。
- **一句话结论**：**该量测推翻 M 规划 §2.5 第 1 条的前提——主干的 LAN 第二客户端形状里根本不存在任何服务端位移读数（两个目标名都是 0 格）；探针回答只存在于专服形状，而专服形状在主干字节下无法容纳加入者。V5 本体在现状下不可行，第一真实失败层在 runner 的两形状互斥（见 §6）。**

---

## 0. 现场与挂载形状

驱动沿用 V4 的三件套形状（`.tmp/v5/{prep,launch,drive}.sh`，逐行改写自 `.tmp/v4/`）：

- 镜像 `minekin-runner:local`；`-e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib`；树挂 `:/src:ro`；`/out` 为本树 `.tmp/v5/out` 私有 bind（--rm 容器材料落盘）。
- **数据根**：私有命名卷 `minekin-v5-probe`（沿用 drive/launch 的既有做法：卷内 `cp -a` 播种，见下）。**规范卷 `minekin-runner-data` 全程未出现在任何 docker 命令里**（本树内的播种源是 V4 私有卷 `minekin-v4-join`，只读挂载）；此处与卡面「本树 .tmp/ 下的私有目录」措辞有出入，申报给 M：私有性成立、规范卷零接触，读物料在 `.tmp/v5/out/`。
- 播种：`prep.sh` 初始化 `kin-v5-host`（Kin）与 `kin-v5-join`（Kin2）两个新账本（baseline position 均为 0），各 `cp -a` 一份 7565-blob 的 1.20.1 artifact store（源 = V4 私有卷），避免 25 分钟取料。
- 专服形状另挂 `/.tmp/v5/mc-1.20.1-server.jar → /server/server.jar:ro`（sha1 `84194a2f286ef7c14ed7ce0090dba59902951553`，与 E6/V3 各树副本一致）。

### run 清单（全部为本树脚本 + `docker run -d`，逐条可复现）

| run | 形状 | `MINEKIN_DOMAIN_PROBE` | 结果 |
|---|---|---|---|
| a（`.tmp/v5/out/a-failed1*`） | LAN 双客户端 | `Kin2` | 加入者 `HANDSHAKE_TIMEOUT`，未 arrival |
| a2（`out/a2`） | LAN 双客户端 | `Kin2` | **主客户端** `HANDSHAKE_TIMEOUT`，未公布 |
| a3（`out/a3`） | LAN 双客户端 | `Kin2` | 加入者再次 `HANDSHAKE_TIMEOUT` |
| **a4（`out/a4`）** | LAN 双客户端 | `Kin2` | **全绿**：Kin2 arrival + PLAYABLE |
| **b（`out/b`）** | LAN 双客户端 | `Kin` | **全绿**：Kin2 arrival + PLAYABLE |
| c（`out/c`） | 专服单客户端 | `Kin` | 驱动读数路径缺陷（见 §1 注），原始日志留存卷内 |
| **c2（`out/c2`）** | 专服单客户端 | `Kin` | 回答行 6 条，全为 `Kin` |
| **d（`out/d`）** | 专服单客户端 | `Kin2` | 回答行 0 条，`No entity was found`×6 |
| **e（`out/e`）** | 专服+`--open-lan`+加入者 | **不设**（默认 `Kin`） | 「nothing was published on 25570」，加入者从未启动 |

复现命令（Git Bash，宿主侧）：

```bash
# LAN 双客户端（a4 为例；b 把 R5_PROBE 换成 Kin，a2/a3 换 R5_SECONDS/OUTNAME）
R5_SHAPE=runA4-probe-Kin2 R5_SECONDS=150 R5_OUTNAME=a4 R5_PROBE=Kin2 \
  bash .tmp/v5/launch.sh a4 session start \
  --profile /src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json \
  --world-save /src/tests/fixtures/saves/kinworld --world-name kinworld
# 专服（c2 为例；d 换 R5_PROBE=Kin2）
R5_SHAPE=runC2-dedicated-probe-Kin R5_SECONDS=120 R5_OUTNAME=c2 R5_PROBE=Kin \
  R5_JOINER= R5_OPEN_LAN= R5_SERVER_JAR=1 bash .tmp/v5/launch.sh c2 session start \
  --profile /src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json \
  --server-profile /src/tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json
# e：c2 的 argv 再加 --world-save/--world-name，恢复 R5_JOINER/R5_OPEN_LAN，不设 R5_PROBE
```

### 环境抖动申报（不是判据红，但烧掉了 3 次尝试）

加入者/主客户端的桥握手预算是 Core 的 `DEFAULT_HANDSHAKE_TIMEOUT_S = 30.0`（`src/minekin_core/cli/session.py:173`，主干无 CLI 旋钮）。本机今日受另一 lane 的容器争用 CPU（`cranky_rhodes` = `minekin-wt-h1h` 的 pytest，实测与本卡并发 28 分钟），客户端 JVM 冷启到 bridge 就绪实测 33–39s（a3 加入者：CLI `08:10:26.7` → `Setting user 08:11:00` → `08:11:01 bridge is failing closed (BRIDGE_FAULT)`），超预算即 `HANDSHAKE_TIMEOUT`；a4/b 两次同一形状在争用间隙成功（a4：`BridgeHelloAccepted` 于 started_at+32.1s 内到达）。V5 本体排程需要把这条 30 秒竞态当作已知环境约束。

---

## 1. 读数一 — 探针回答行存在性

**判读**：回答行 `has the following entity data:` 在**主干字节下只存在于专服形状**；**LAN 第二客户端形状里不存在任何一格**——该形状没有专服进程（`domain.sh:579-591` 的 `run_controlled_server.py` 仅在给了 `--server-profile` 时启动），也没有别的通道向宿主客户端的内嵌服务端问 `data get entity`。

- LAN 形状（a4/b）：`90-readouts.txt` 逐字 —
  ```
  R5: server run directory: <none found>
  R5: server.log exists: NO
  R5: /tmp/domain-server.log exists: NO
  R5: [probe-answers] server.log: ABSENT
  ```
  兜底全卷复核（卷内 7 份客户端/服务端 latest.log 逐文件计数）：
  ```
  checked 7 logs, total hits: see HIT lines above (none printed = zero)
  ls: cannot access '/data/server-runs': No such file or directory   ← LAN run 期间卷内根本没有 server-runs
  ```
  首末值：**不存在**（0 条，无从取首末）；**按名归属**：不适用。
- 专服形状（c2，作为「回答行确实存在」的正对照）：`/data/server-runs/run-2/server.log` 计数 6，首末逐字 —
  ```
  [08:28:11] [Server thread/INFO]: Kin has the following entity data: [-2.5d, -60.0d, 6.5d]
  [08:28:21] [Server thread/INFO]: Kin has the following entity data: [-2.5d, -60.0d, 6.5d]
  ```
- **卡面「这些行不带玩家名」不实（就主干字节而言）**：成功回答行**内嵌被问名字**（上面逐字行的 `Kin`）；不带名字的是**失败行**——专服 run d 里对被问缺席的名字，服务端只答 `No entity was found`（`run-3/server.log:68-75`，共 6 条，无名字）。M-C0 要解决的是「封进 bundle 后读不出被问过谁」，与这里的裸日志形状是两回事，别混。

注：run c 的 drive 抄录路径拼接有缺陷（`${server_directory}server.log` 少一个 `/`，读数记为 ABSENT，且 `R5_OPEN_LAN=` 空值被 `:-` 语义还原成 1），已在 c2 前修复（`.tmp/v5/{launch,drive}.sh` 两处 Edit）；c 的原始 `server.log` 留存卷内，事后直读复核（`.tmp/v5/inspect-run1.sh`）：回答行 36 条（Pos 18 对），全部为 `Kin`，首条逐字 `[08:23:12] [Server thread/INFO]: Kin has the following entity data: [2.5d, -60.0d, -7.5d]`。本条申报，不影响 c2/d 的读数。

## 2. 读数二 — 目标切换的正对照

**判读**：在 LAN 双客户端形状里，**两格都没有回答行**——`MINEKIN_DOMAIN_PROBE=Kin2`（a4）与 `=Kin`（b）读到的都是 0，两者不可区分，因为**根本无读数可言**（不是「读到的是主持有者的」，而是「谁都读不到」）。目标切换这个机制本身在**唯一存在服务端形状**上验证成立：

| run | 形状 | probe 目标 | 回答行计数 | 首/末值 |
|---|---|---|---|---|
| a4 | LAN 双客户端 | `Kin2`（加入者名） | **0**（server.log ABSENT，全卷 grep 0） | 无 |
| b | LAN 双客户端 | `Kin`（主持有者名） | **0**（同上） | 无 |
| c2 | 专服单客户端 | `Kin` | **6**（Pos 3 + Rotation 3），全为 `Kin` | Pos 首=末 `[-2.5d, -60.0d, 6.5d]`；Rotation 首=末 `[0.0f, 0.0f]` |
| d | 专服单客户端 | `Kin2`（世界里没有此人） | **0**，代之以 `No entity was found`×6 | 无 |
| e | 专服+LAN 门 | **不设 env**（默认 `${player}`=`Kin`） | 回答行 0、`No entity was found`×20（Kin 在 120s 窗口内未进服） | 无 |

c2 与 d 的差集（同一形状、同一字节，只换 `MINEKIN_DOMAIN_PROBE`）证明 **env→`--probe-player`→回答行的目标遵循是活的**；e 证明不设 env 时被问的是 `${player}`（`domain.sh:27/:482` 的 `${probe:-${player}}`，其命令侧后果由 run_controlled_server 每 5 秒的缺席应答节奏证实）。

## 3. 读数三 — 加入者 PLAYABLE（与「听到 arrival」分开报）

**判读**：主干字节下，LAN 加入者**可以到 PLAYABLE**（a4、b 两次），载体是加入者自己的账本；但**a/a2/a3 三次同一形状没到**（客户端桥握手竞态，见 §0 申报），这不是判据层，是环境层。

- a4（`out/a4/90-readouts.txt`、`domain-stderr.log` 逐字）：
  - arrival 侧（`:1195`）：`domain: the world heard Kin2 arrive`
  - PLAYABLE 侧（`:1221`）：`domain: Kin2 admitted its first snapshot of that world`
  - 账本（`/data/kin/kin-v5-join/kin.sqlite3`，本 run 前 baseline position=20）：
    ```
    35|PlayableEstablished|2026-09-27T08:17:52.767072Z
    R5: joiner PlayableEstablished rows above baseline (the ':1211-1213' carrier):
    1
    ```
  - 加入者 session 文档：`"connection_state": "PLAYABLE", "snapshots_admitted": 1, "entities_admitted": 26`（run_id `947e6f25…`，session `5fdc42d9…`）。
- b（`out/b/90-readouts.txt`）：同样两行都在（arrival + admitted），账本 baseline=39，`54|PlayableEstablished|2026-09-27T08:21:37.234920Z`。
- 失败格（a/a2/a3）：两条都没有——`Kin2 never arrived within Ns`，账本里只有到 `SessionInterrupted` 的序列，无 `PlayableEstablished`。**「服务端听到 arrival」与 PLAYABLE 按判据形状分别取证，本次两者同现或同缺，未见「听到而不到」格。**

## 4. 读数四 — 控制关闭的基线（V5 第二条非恒真对照的「关闭侧」）

**判读**：**本卡测量时的主干字节（base `8dfeac6`）还没有任何加入者控制驱动**（H1h 当时未合入；入干时它已在，但驱动只往加入者 argv 里加默认关闭的限幅控制，不改「谁在答探针」），且如读数一所证，LAN 形状连加入者的位移读数载体都没有——所以「加入者首末读数不变」这条对照在现状下**无载体可言**（既谈不上成立也谈不上被破坏）。最接近的活体证据是专服形状里**被探目标无控制**时的首末一致性（c2，Kin 在世界里约 10 秒、3 个采样点）：

```
Pos    首 [-2.5d, -60.0d, 6.5d] 末 [-2.5d, -60.0d, 6.5d]  |first-last| = [0.0, 0.0, 0.0]
Rotation 首 [0.0f, 0.0f] 末 [0.0f, 0.0f]                   |first-last| = [0.0, 0.0]
```

即：探针自身的节奏不制造漂移、世界加载噪声在 10 秒窗口内为 0。样本窗口短（专服形状里 host 进服到 run 收尾只有 ~10s），V5 本体若拿到可行形状，应把这条对照在加入者侧、更长窗口重量。

## 5. 对 `docs/v1201-lan-control-next-2026-09-27.md` §2.5 第 1 条的裁决

该断言分两半，结论分别是：

1. **管线的半句为真（活体）**：`domain.sh:27/:165/:482` 的 `MINEKIN_DOMAIN_PROBE`→`--probe-player "${probe:-${player}}"` 逐字生效——c2（Kin：6 条按名回答）对 d（Kin2：0 条回答、6 条 `No entity was found`）、e（不设 env：被问的是 `Kin`）为证。
2. **推论的半句不成立（活体）**：「（在 LAN run 里）不设 env 时读到的位移读数不是加入者的」——**LAN 第二客户端形状里不存在任何服务端位移读数**（a4/b 两格皆 0，卷内无 `server-runs`，回答载体 `run_controlled_server.py` 在该形状从未启动）。设不设 `MINEKIN_DOMAIN_PROBE` 在 LAN 形状下都不产出读数。因此「显式指向加入者就能读到加入者位移」这个 V5 前提**不成立**：不是名字选错，是这个形状没有答题人。

## 6. 第一真实失败层（本卡就地停手的层，未改 runner）

- **层**：主干 `domain.sh` 里「有探针答题人的形状」与「有第二客户端的形状」**互斥**——
  - 加入者的闸门在**客户端侧公布**：`domain.sh:1558-1586` 要求宿主客户端 latest.log 出现 `Started serving on ${lan_port}`（内嵌服务端开 LAN），才会调 `join_the_published_world`；加入者拨的是 `lan_port`（`/tmp/domain-join-profile.json`，`:742-756`）。
  - 回答行的载体在**专服侧**：`domain.sh:579-591` 的 `--probe-player` 只随 `--server-profile` 形状存在；`run c/d/e` 的 server.log 与 `run a/b` 卷内无 `server-runs` 各证一头。
  - 试图合体（run e：专服 + `--open-lan` + joiner + world-save，主干未拒 argv，也未改任何文件）：宿主连专服后**永远不会** print `Started serving on 25570`，120s 后 `domain: nothing was published on 25570 within 120s`，加入者分支根本不被调用；无 stderr 崩溃可贴，失败是**门永不打开**这一具名读数本身。
- **以为需要什么的决策留给 M（本卡未动）**：要么让加入者以专服端口为目标（公布门改读专服侧 `joined the game` 或让 join-profile 指向专服端口并放开 `:1558` 的客户端公布门），要么给内嵌服务端形状加一条等价的 console 通道。二者都属 `test-orchestrator/**` 面的新卡，不属 V。

## 7. 边界与物料

- 未挂载/写入规范卷（本卡所有 docker 命令见 §0；唯一只读挂载的私有卷是 V4 的 `minekin-v4-join`，作播种源）；未封存、未注册 case、未动 `tests/fixtures/**`、registry、`mandatory`、`test-orchestrator/**`、`tools/**`、`src/**`、`config.py`。
- 未连接任何远程测试服务器；全部为容器 loopback（`127.0.0.1:25566/25570`，受控 fixture 端口）。
- 原始材料：本树 `.tmp/v5/out/{a-failed1,a-failed1-console,a2,a3,a4,b,c,c2,d,e}/`（`00-header.txt`、`domain-stderr.log`、`90-readouts.txt`、`tmp/domain-*`）；卷 `minekin-v5-probe` 内 `/data/kin/kin-v5-{host,join}/run/session/*/generation-1/logs/`、`/data/server-runs/run-{1,2,3,4}/server.log`。V4 的 `.tmp/v4/` 原样未动。
- 本文不构成封证；**LAN 第二客户端控制封证仍为 0**。
