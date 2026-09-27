# V5′：1.20.1 LAN 加入者在私有本地世界上的有界控制活体读数（2026-09-28 00:21 +0800，M 主控）

> **这份记录是什么**：三式活体战役在**私有本地数据卷**上的读数（readout），不是 sealed bundle，不进 `mandatory`、不进 registry、不支撑任何 `tested` 晋级。
> **一句话结论**：控制词在专服形状下**确实改变了被探者的状态**（armed 与 control-off 在同一份 `server.log` 上可逐行对比），H1m 的第二具名探测目标在活体路径上**真的被答了**，而「问了一个从未到场的名」在日志面上与「没问」**不可分辨**——这正是 H1i 第②格（`--probed-player` 交回）的必要性证据。

## 承载字节与环境（先核摘要，再谈读数）

| 项 | 值 |
| --- | --- |
| runner 字节 | `012f56b`（H1m 合入笔）之上的 M 集成树工作副本；`test-orchestrator/runner/domain.sh` = `e04524d640adec2473f1137c46b6706b7a855753669c9e3b64af6264c4498954` |
| 桥 jar | `e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f`（§2.46 前置 ② 的钉值件，`:remapJar` 产物，经 `/server/server.jar:ro` 挂入） |
| recipe fixtures | `bundle-candidate-1.20.1.json` = `709a889977b10857ae623d83aca640321493224ba54e594ad1d09bd22aaef185`，`controlled-offline-server-1.20.1.json` = `3864eddae899c77a1f2c522fd02c3618b6601efd97f9e2fe8c4aff2354303aa2` |
| 镜像 / 挂载 | `minekin-runner:local`；`minekin-m-v5p-live:/data`（唯一可写数据面）、`minekin-v4-join:/ro:ro`（只读播种源）、`${WT}:/src:ro`、`${WT}/.tmp/v5p:/drv:ro`、`${WT}/.tmp/v5p/out-host:/out`、桥 jar `:ro` |
| 规范卷 | **未挂载**（`minekin-runner-data` 存在于 `docker volume ls`，本战役不引用它）；播种读的是 `minekin-v4-join` 的 `kin/kin-v4-host/run/artifact-store`（7565 个 blob，与宿主 store 同数） |
| 远程服 | 未连接；`.tmp/local-test-server.txt` 未读；服务端由本 run 自己起（`/data/server-runs/run-1..3`，`server-ip=127.0.0.1`） |
| 驱动 | `.tmp/v5p/run-shape.sh`（起前硬检：`docker ps` 非空 ⇒ `exit 3`）+ `.tmp/v5p/drive.sh`（readout (a)–(g)）+ `.tmp/m-r56-v5p-all.sh`（串行三式）；日志 `.tmp/m-r56-v5p-all.log`，材料 `.tmp/v5p/out-host/<shape>/`（未删） |

三式共用的形状：`MINEKIN_USERNAME=Kin`、`MINEKIN_DOMAIN_JOIN=kin-v5p-join`、`MINEKIN_DOMAIN_JOIN_USERNAME=Kin2`、`MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`、`MINEKIN_DOMAIN_PROBE_SECONDS=4`、`MINEKIN_DOMAIN_PROBE_SECOND=Kin2`、`MINEKIN_DOMAIN_SECONDS=420`、`MINEKIN_DOMAIN_SOAK_SECONDS=150`。**差异只在四个具名控制词与 `MINEKIN_DOMAIN_PROBE`**。

## 三式读数（同一判据面逐式并列）

| 式 | 差出的环境变量 | `domain.sh` rc | `server.log` sha256 / size | `Kin` 答题行 | `Kin2` 答题行 | `Kin2` 首→末位置 | `Kin2` 末朝向行 | 到达 / 首快照 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `armed` | 三名齐发：`JOIN_LOOK_YAW=45`、`JOIN_LOOK_PITCH=-20`、`JOIN_HOLD_FORWARD_SECONDS=2` | 14 | `c6052d384166c71abfae1fb7e0eb35aad5a4876f69eaff111067e4b8cc28adee` / 27569 | 84 | 82 | `[10.5d, -60.0d, -9.5d]` → `[4.399447156057091d, -60.0d, -3.399447156057091d]` | `[45.0f, -20.0f]` | 到达 + 首快照均有 |
| `control-off` | 三名**全部 unset** | 14 | `975ecd6da71caea7f3e7cd0d1654c7cfac103eca3bfc60eac71dc96dda9c27e0` / 25821 | 84 | 80 | `[10.5d, -60.0d, -8.5d]` → `[10.5d, -60.0d, -8.5d]`（**未动**） | `[0.0f, 0.0f]` | 到达 + 首快照均有 |
| `ghost` | `armed` + `MINEKIN_DOMAIN_PROBE=Ghostz`（一个从未到场的名） | 14 | `d7bfbcdc550d04943c9d16d60e39f176c372609394d06292e59ebf85126e7a09` / 24558 | **0** | 80 | `[4.5d, -60.0d, -4.5d]` → `[-1.6005528439429093d, -60.0d, 1.6005528439429093d]` | `[45.0f, -20.0f]` | 到达 + 首快照均有 |

三式的 `server.log` 都写着 `Kin joined the game` 与 `Kin2 joined the game`；三式在 (c)「probe targets this run named」一格**都是 `(no probe-target line)`**；`ghost` 式整份 `server.log`（289 行）里 `Ghostz` **出现 0 次**，`domain-stderr.log` 里也没有任何关于该名的句子。

## 逐条判读（每条都给反算式）

**1. 控制词生效，且效果落在被探者身上。** `armed` 的 `Kin2` 位置在 `16:10:23 → 16:12:59` 之间从 `[10.5,-60,-9.5]` 走到 `[4.399,-60,-3.399]`，朝向行末值 `[45.0f, -20.0f]` 与 `JOIN_LOOK_YAW/JOIN_LOOK_PITCH` 的两个赋值**逐字相等**；`control-off` 式同名末值仍是首值 `[10.5,-60,-8.5]`、朝向 `[0.0f, 0.0f]`。⇒ 该格非恒真：默认关闭时位移与朝向都不出现。

**2. 第二具名探测目标在活体路径上真被回答。** `armed` 里 `Kin` 84 行、`Kin2` 82 行，取自**同一份** `server.log`（`c6052d38…`），两名的答题行时间戳交错。H1m 之前只有契约与静态判定支撑这一格，本轮是活体读数。

**3. 「问一个不存在的名」在日志面上不可分辨（这是 M-C0 载体的必要性证据）。** `ghost` 式：`Ghostz` 0 次出现、无答题行、也**没有任何具名拒止/找不到实体的行**；同时宿主名 `Kin` 的答题行数从 84 掉到 **0**，因为 `MINEKIN_DOMAIN_PROBE=Ghostz` 顶掉了 `${probe:-${player}}` 的本人回退（`domain.sh:833`）。⇒ 光看 `server.log` 无法区分「探过 Ghostz 且它没答」与「根本没探」；唯一能把「本 run 问过谁」写进 bundle 的通道是 `--probed-player` 交回（H1i 第②格，`tools/seal_run_evidence.py:929/:337–:338/:721` 侧承担者已在）。
```bash
grep -c "Ghostz" .tmp/v5p/out-host/ghost/server.log        # 0
wc -l < .tmp/v5p/out-host/ghost/answer-lines-Kin.txt       # 0
grep -c "Kin2 has the following entity data" .tmp/v5p/out-host/ghost/server.log   # 80
```

**4. 封存/命令面上探针目标始终不说出**（三式 (c) 全 `(no probe-target line)`）⇒ §2.43 缺口二在活体路径复现，与 `grep -n "probed-player" test-orchestrator/runner/domain.sh` 回空一致。

**5. 三式 `domain.sh` rc 同为 14，且它是 `wait` 到的会话退出码（`domain.sh:2731` `status=$?` → `:3090` `exit "${status}"`）——三式一致 ⇒ 不作判别量。两处 M 侧工具缺陷具名申报（不改判据、不改材料）：** ① `.tmp/m-r56-v5p-all.sh` 记录的 `rc(live)=0` 是 `drive.sh` 末段 `… | tee` 管道的状态，**不是** `domain.sh` 的退出码；权威值取每式打印的 `V5P: domain.sh rc=14` 行。② `drive.sh` 的 (d) 名单写死 `[host_name, join_name, PROBE_SECOND]`，本形状下 `join_name == PROBE_SECOND == Kin2` ⇒ `Kin2` 那格**重复打印两遍**（数值一致，无第二次测量）。两处都只影响我自己的驱动，修不修不影响上面任何一条读数。

## 复算式（读者可在同一字节上重跑）

```bash
cd C:/Users/darling/Documents/agent_work/minekin-wt-integration
sha256sum test-orchestrator/runner/domain.sh bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar
grep -nE "^==== V5P|rc\(prep\)|rc\(live\)|domain.sh rc=" .tmp/m-r56-v5p-all.log
for s in armed control-off ghost; do echo "## $s"; sed -n '1,40p' .tmp/v5p/out-host/$s/00-header.txt; \
  awk '/--- \(a\)/,0' .tmp/v5p/out-host/$s/90-readouts.txt; done
sha256sum .tmp/v5p/out-host/*/server.log
```
私有卷 `minekin-m-v5p-live` 保留三式的 run 目录（`/data/server-runs/run-1..3`）与两个 Kin 的 store，未清理；`docker volume ls` 可见。卷内成功读数**不得**冒充 sealed bundle，也不得作为 E7 的替代。

## 交给下一格的东西

- **M-C1（#48）**：判据只能落在「同一份 `server.log` 上按名答题行的差分」这一类可复算形状（位置元组变化 + 朝向行等于赋值），且**必须是新登记的案**——本轮同时证明了三式都会改变 `server.log` 的总行数（探测节奏/时长差），所以行**数**不是判据，行**内容**才是。
- **H1i（#52）**：第①格只交 `--server-directory`（§2.50 已把它从推断升级为字节判定）；第②格的名字取 `probe_args` 的实际值。`ghost` 式给了它一条现成的第四枚反证：设 `MINEKIN_DOMAIN_PROBE` 为一个不存在的名 ⇒ 交回的名里必须含它，而日志里 0 行——「交回了问过谁」与「日志有没有答」由此可分。
- 本轮之后仍是：**真实封证 = 0**；未放宽认证/地址/lease/判据；未翻 `mandatory`/registry；材料与失败材料未删。
