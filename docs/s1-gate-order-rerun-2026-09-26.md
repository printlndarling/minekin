# S1「先拒后装」规范卷重跑读数（N1 收口，2026-09-26）

> 执行侧 E 证据 lane，2026-09-26。卡片：[执行计划 §3.2 N1 行](development-execution-plan.md#32-a2-交出的四格缺口同样按-12-单独登记不由-a2-顺手修)。
> 卡面要求：「判据取复判记录 §3 的 X1 vs X2/Y2 与 B1/B2；实现不得改本记录的期望，收卡要能重跑那三组行并给出
> '先拒后装'的新读数。**不改 case 判据、不翻 registry。**」本记录就是那三组行的新读数。
> 基线：[负向矩阵复判记录 §3](version-negative-matrix-2026-09-26.md)，其 baseline `11538c4`，读数是**修复前**的形状。
> 本记录的被测构建：主干 `ed37260`，其中含 S1 实现 `b88e36f`；反向对照用 `b88e36f` 的父提交 `300ed07` 同一套脚本重跑。
> 全程受控本地：真 1.20.1 dedicated 服务端跑在容器内 loopback，假 status 端点 bind 容器自身接口。
> **未连接任何远程服务器，未使用私有目标地址**；地址由脚本在容器内现取（`hostname -I`），本文不落基础设施地址。

## 0. 一句话读数

修复前那三组行的缺陷（自动入口把整店下载放在 join 授权与版本准入之前）在主干当前构建上**已经消失**：
X2 由 `exit=124 / store 388 文件` 变成 `exit=17 / store 0 / 0 条 fetching`；Y2 由「`fetching 3639/3639` 之后才拒」
变成「一个字节的 store 复核都没走就拒」；B1/B2 由「60 秒界内已在下架 738 MB」变成「3–4 秒具名 `ADMISSION` 拒，
store 全程 0」。十三行拒止跑完后的 store 从 **290 文件** 变成 **0 文件**，而未改动的正对照 C1 仍然进入装机。

## 1. 复现入口（本轮真实用过的命令）

Windows 侧前置：`export MSYS_NO_PATHCONV=1`，`REPO="$(cygpath -m "$PWD")"`。被测源码一律 `:ro` 挂载。

```bash
# X 组（可达非 loopback 目标：显式 X1 vs 自动 X2）
docker run --rm --name e-s1x --entrypoint /bin/bash \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/dataref:ro -v minekin-e-s1x:/data \
  -e MINEKIN_HOME=/data -w /src minekin-runner:local \
  -lc 'bash /src/.tmp/v1201-boundary-address.sh'

# Y 组（满 store 下的门序：loopback Y1 vs 非 loopback Y2）
docker run --rm --name e-s1y --entrypoint /bin/bash \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/dataref:ro -v minekin-v1201demo3:/datasrc:ro \
  -v minekin-e-s1y:/data -e MINEKIN_HOME=/data -w /src minekin-runner:local \
  -lc 'bash /src/.tmp/v1201-boundary-stored.sh'

# B 组（真 1.20.1 服 + 自动入口的十三行 + 正对照 C1）
docker run --rm --name e-s1b --entrypoint /bin/bash \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/dataref:ro -v minekin-e-s1b:/data \
  -e MINEKIN_HOME=/data -e MINEKIN_SERVER_JAR=/dataref/v07-jars/server-1.20.1.jar \
  -w /src minekin-runner:local -lc 'bash /src/.tmp/v1201-negative-matrix.sh'

# 反向对照（把 b88e36f 的父提交导出成 /src，只跑 X 组）
git archive 300ed07 | tar -x -C <临时目录>   # 该目录无 .tmp，需把脚本复制进去
```

三个 `.tmp/` 脚本与 A2 记录用的是**同一份文件、未经修改**（判据、期望、超时界、行标签都是 A2 写下的那些）。
本轮只改了两处 plumbing，且都不在三组行的判据上：B 组的 jar 路径经 `MINEKIN_SERVER_JAR=/dataref/v07-jars/server-1.20.1.jar`
注入（脚本本来就支持这个环境变量）。

环境事实（都是量出来的，不是引用的）：

- 镜像 `minekin-runner:local`，image id `7730fc480365`，容器内 python `3.12.3`。**该镜像在 2026-09-26 一轮 Docker
  本地镜像存储被清空后由仓库内 `test-orchestrator/runner/Dockerfile` 重建**（钉住的 base 镜像与 vendored SQLite
  摘要未变），重建后只读的 B2 第一刀读数与 checkpoint 逐字节相同（见 §5）。
- 服务端 jar：`/dataref/v07-jars/server-1.20.1.jar`，实测 `47,791,053` 字节、sha1 `84194a2f286ef7c14ed7ce0090dba59902951553`。
- Y 组的满 store 来源：卷 `minekin-v1201demo3` 内 `kin/kin-demo-rhs3-20260926T052929Z/run/artifact-store`，
  `cp -a` 后实测 3639 文件（源 3639），与 A2 的 Y 组同源同字节。
- 本轮三组各自新建可写卷 `minekin-e-s1x` / `minekin-e-s1y` / `minekin-e-s1b`；
  规范卷 `minekin-runner-data` 全程只挂 `:ro`（B2 的封证材料未动，E 仍是它唯一的写入者）。

## 2. 三组行的读数（基线 = 修复前，读数 = 主干 `ed37260`）

### X 组：可达的非 loopback 目标，同一份字节，只差入口

| 行 | 输入 | 基线读数（A2，`11538c4`） | 本轮读数（`ed37260`） |
| --- | --- | --- | --- |
| X1 | 显式 `--profile` | `exit=17 ADMISSION launcher.profile …loopback target…`，<2 秒，store 0 | **同一读数**：`exit=17`，具名 `a managed session may only join a loopback target; remote joining needs its own authorization card`，store 0 |
| X2 | 自动 `--auto-bundle`，空 store | `exit=124`（120 秒界），store 已到 **388 文件**，`fetching` 3 行 | **`exit=17`，store 0，`fetching` 0 行**，同一条具名 `ADMISSION` 消息 |

X2 的假端点本轮接受连接数 `1` —— 那是脚本自己先行的 `server probe`（可达性正对照，必须先发生才有意义），
`--auto-bundle` 那一次没有发出任何字节。脚本自带的分诊行给出 `READING: GAP ABSENT - the automatic entry refused
before any download`（基线同一脚本给出的是 `GAP PRESENT`）。

### Y 组：store 已经满，只差 host 字面量

| 行 | 输入 | 基线读数 | 本轮读数 |
| --- | --- | --- | --- |
| Y1 | `127.0.0.1` + 满 store（3639） | 走完 `fetching 3639/3639`，150 秒界内**未被 join 授权拒**（输出停在最后一行 fetching） | 同样走完 **37 条 `fetching`**、`reused=0`、`java=0`、**0 条 `loopback target` 拒止**；store 复核之后撞上下一段：`exit=11 SUPPLY_CHAIN`「the Bridge jar has not been built: /src/bridge-1201/build/libs/…jar is missing」 |
| Y2 | 容器自身可路由地址 + 同一份满 store | `fetching 3639/3639` **之后**才 `exit=17 ADMISSION …loopback target…`，`java=0`（`remote.out` 共 38 行，其中 37 行 fetching） | **`exit=17` 且整份输出只有 1 行**：0 条 `fetching`、1 条具名 `ADMISSION …loopback target…`、store 仍是 3639 未被触碰、`java=0` |

Y1/Y2 这一对是本卡的非空转对：两侧 store 字节完全相同、只差 host 字面量，loopback 那行照旧穿过授权（停在下一段
的 Bridge 缺失上），非 loopback 那行在装机之前就被拒。若门只是"走到哪算哪"，两行应当停在同一处；它们没有。

Y1 结尾与基线的差别是**位置不同而不是结论不同**：基线在 150 秒界上被截断，本轮在界内跑完 store 复核后撞上
Bridge 未构建（`/src` 只读、该 worktree 没跑过 `./gradlew build`）。两行的 `refused=0 / fetching=37 / java=0` 一致，
所以「join 授权不是 Y1 的阻断者」这条控制结论在两侧都成立。

### B 组：真 1.20.1 dedicated 服 + 自动入口十三行 + 正对照

| 行 | 基线（A2 `neg-20260926T062430Z/matrix.tsv`） | 本轮（`neg-20260926T112736Z/matrix.tsv`） |
| --- | --- | --- |
| B1 profile allowlist 只写 `1.21.4`，真服答 `1.20.1` | `exit=124`，`fetching 100/3639`（**没有任何准入拒绝先发生**） | **`exit=17`，4 秒**，`ADMISSION launcher.profile`「the session launches Minecraft 1.20.1, the target allows 1.21.4」 |
| B2 allowlist 写 `1.20.1,1.21.4` | `exit=124`，`fetching 100/3639`（矩阵表首行；复判记录 §3 正文记的是 200/3639，两处都是同一轮的下载进度） | **`exit=17`，3 秒**，`ADMISSION`「a managed session target must allow exactly one version, this one lists 1.20.1, 1.21.4」 |
| B3 `deny_all` | `17 ADMISSION` | 同形状：`17`，4 秒 |
| B4 online-mode | `17 ADMISSION` | 同形状：`17`，3 秒 |
| B5 非 loopback 地址 | `17 ADMISSION` | 同形状：`17`，4 秒 |
| B6 预算 1 字节 | `11 SUPPLY_CHAIN` | 同形状：`11`，6 秒 |
| B7/B8 预算 0 / -1 | `70 INTERNAL_INVARIANT` | 同形状：`70`（缺口仍在 N2，本卡不动） |
| B9 registry 引用非评审 recipe 字节 | `11 SUPPLY_CHAIN` | 同形状：`11` |
| B10 预算配 `--profile` | `11 SUPPLY_CHAIN` | 同形状：`11` |
| B11 同时给两种入口 | `2 usage` | 同形状：`2` |
| B12/B13 伪造显示文本 / 多版本代理 | `10 CONFIG` | `17 ADMISSION`「server profile is not readable UTF-8 JSON」——**两侧都没有真正测到该场景**，见 §3 第 4 条 |
| 十三行跑完后的 store | **290 文件** | **0 文件** |
| C1 未改动的自动运行 | store 已 290（被 B1/B2 填过），进程仍在跑 | store 从 0 起，5 秒内 **3 文件、进程仍在跑** ⇒ 正对照成立 |

`FAIL=0`、`matrix rows: 13`。本轮 C1 之后被脚本主动终止，留下的半包 store 18 文件、`.staging` 残留 4，
是这一次运行自己的中断样本，未清理。

## 3. 读数的边界（不把话说满）

1. **本记录不封任何证据、不动任何门。** 三组行都是**可重跑拒止读数**，产出的是 run 目录与日志，
   不是 sealed bundle；`report_promotion` 的 W60 / `p0-core` / overall 读数与 §5 的 checkpoint 完全一致，
   一个门的 `blocks` 都没有因此改变。
2. **不改 case 判据、不翻 registry、不删失败材料。** 基线与本轮的原始 `.out`/`.tsv` 都留在各自卷里
   （`minekin-v1201neg2/10/11` 属 A2，`minekin-e-s1x/y/b` 属本轮）。
3. **反向对照只覆盖 X 组。** `300ed07`（`b88e36f` 的父提交）以同一份未改脚本重跑：X1 仍 `exit=17 store=0`
   （显式路径不受影响），X2 回到 `exit=124 / store 354 文件 / fetching 3 行`，脚本分诊给出 `GAP PRESENT`。
   Y、B 两组的修复前读数取自 A2 当天同一脚本的原始材料，没有重放旧构建——因为那需要把只读卷里的满 store
   与真服再跑一遍，而 §2 的 Y 组非空转对已经由「只差 host 字面量」承担了同一职责。
4. **B12/B13 在两处都不可采用。** 脚本读取假端点端口表的 python 片段缺 `import sys`（`NameError`），
   端口表为空 ⇒ A 族 18 行探针整段跳过 ⇒ 这两个场景的 profile 从未生成。基线卷 `minekin-v1201neg2` 的
   `a2-matrix.log` 里有**一模一样的 `NameError` 与 `scenario ports: `（空）**，
   其 `matrix.tsv` 的 A 行数为 0 —— 所以两侧都是 13 行、形状可比，但 B12/B13 的 `10` vs `17` 只差在
   "读不到 profile 文件时谁先报错"（修复后自动入口先装载 profile），**不构成产品结论**。
   该脚本缺陷属 runner 侧未跟踪脚本，修它不在 N1 的判据里，本卡不顺手改；18 行真实 socket 读数的权威来源
   仍是复判记录 §2（`v1201-negative-status.sh` / `minekin-v1201neg5`），本轮未重跑。
5. **N1 只关掉它自己那半的缺陷面。** §1 F3 的「命中禁区地址」、§3 第 2 点的装机顺序、第 3 点的 allowlist
   失效三件事，本轮给出的是当前构建上的"已不发生"读数。N2（`--max-bytes 0/-1` 得 `exit=70`）与 N3/N4
   仍是打开的缺口；契约里 SRV/DNS 那一行今天仍无法作为真实行为产生。
6. **本记录不声称**：V08 或任何远程入服可用；任何 `tested` 提升；W60 / `p0-core` 已满足；
   自动路径的**真装机 + 真入服**已被这三组行覆盖（C1 只到"开始下载"就被主动终止）。

## 4. 与 N1 卡面的对应关系（收口判据逐条回勾）

| 卡面要求 | 本轮交付 |
| --- | --- |
| 判据取复判记录 §3 的 X1 vs X2/Y2 与 B1/B2 | §2 三张表逐行给出基线与本轮，不改期望 |
| 实现不得改本记录的期望 | 三个脚本未改（B12/B13 的缺陷也保持原样，见 §3 第 4 条） |
| 收卡要能重跑那三组行 | §0 与 §2 的 Kin / 卷 / 证据目录可复现，命令在 §1 |
| 给出"先拒后装"的新读数 | X2 `store 0 / fetching 0`、Y2 `1 行输出`、B 组 `store after the refusals: 0` + C1 仍进入装机 |
| 不改 case 判据、不翻 registry | 未改；本轮没有新的 sealed bundle |

## 5. 顺带核实的两件基础设施事实（记录，不改主控文本）

- **Docker 本地镜像存储被清空过一次**：`docker system df` 一度给出 Images 0 / Containers 0 / Build Cache 0，
  而 24 个数据卷完好。由 `test-orchestrator/runner/Dockerfile` 重建 `minekin-runner:local` 后，只读运行 B2
  第一刀的读数脚本（`.tmp/b2-readout.sh`，规范卷 `:ro`）产出与 checkpoint
  `.tmp/e-checkpoint-0926/postmerge-core-readout.log` **逐字节相同**的 47 行：`attempts 54 / bundles 90 /
  from_another_build 61 / unreadable 0 / unsealed 0 / unverified 0`，W60 `promotable true / blocks []`，
  `p0-core` 只剩 `REQUIRED_CASE_NOT_REGISTERED`，`CORE-040` 复判 `observed=6/6`、`CORE-050` `4/4`、
  `disagreements=[]`。**镜像重建没有改变任何门读数。**
- **E 早前"规范卷疑似丢数据"的警报是我自己的读数错误，撤回。** 我一次探针只数了 `/data/kin/*/run/evidence`
  下的目录（85），而 `candidate_roots` 实际是四个证据根：`kin-01 82 + kin-02 2 +
  kin-auto-inst-20260925T141055Z 1 + repo-evidence 5 = 90`，与门禁读数一致；A1 的 sealed PASS bundle
  在独立卷 `minekin-v1201demo3`（`kin-demo-rhs3-20260926T052929Z`，store 3639 文件、manifest 重读
  `V1201-040 / PASS` 仍在），A2 的 X/Y/B 原始材料在 `minekin-v1201neg10 / neg11 / neg2`，也都还在。
  规范卷上 `kin/` 只有 7 个 Kin 目录本来就是这样，不是丢失。**另：attempt 登记库在卷根
  `/data/evidence-attempts.sqlite3`（16,384 字节），不在 `kin/kin-01/…` 之下**，
  交棒文档 §边界段那句路径写法请主控按此读。
