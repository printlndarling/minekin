# H1i `V1201-PROBE-TARGET-HANDOVER-001` — 两枚默认关闭的旋钮：四枚反证的活体读数、一处未闭合的载体缺口、门表

日期：2026-09-28。分支：`codex/minekin-h1i-probe-target-handover`，实现提交 `9e7e47d`。
工作树：`C:\Users\darling\Documents\agent_work\minekin-wt-h1i`。
本卡不 rebase、不 merge——合入复审归 M。

**口径来源**：卡面 §2.43（含补记）给出两格，§2.50 把它们钉成「两枚旋钮 + 四枚反证」，
本文按 §2.50 的原文口径逐枚交证据，不自行放宽。

**卷与边界**：活体一律走 lane 私有卷 `minekin-h1i-live` 与私有目录
`.tmp/h1i-live/ce-data-*`；规范卷 `minekin-runner-data` 全程只出现在门载荷的
`-v ...:/data:ro` **只读**挂载里，未建 attempt、未建 bundle；未连接任何远程服务器，
未读 `.tmp/local-test-server.txt`；未改判据、认证、地址、lease 口径；未翻 `mandatory`、
未动 registry（`check_case_assertions` 见 §4）。**本文所有「bundle」字样指的是私有卷上
的活体读数，不是晋级用的 sealed bundle，不构成 `tested` 证据。**

## 0. 现场（续任开工时逐项复量，非引用）

| 项 | 读数 | 校准值 |
| --- | --- | --- |
| `git status --porcelain` | 空（0 行） | 空 |
| `git rev-parse HEAD` | `9e7e47d3469459453a89844783d932689b323c88` | 前任唯一实现提交 |
| `test-orchestrator/runner/domain.sh` | `df86c258df126b2d9c208243397cd6f425faac8ab21af22d439e155c80d640a2` | 同 §卡面对齐值 |
| `tests/contract/test_runner_scripts.py` | `daecfa01a5827534fd6db6eb8c70e3a09659804748cbfe88dfd2b9f4af7da471` | 同上 |
| `test-orchestrator/runner/run.sh` | `323f521a3141fa3c613d02b93500612aa1ec943a2467a4da1d4a5080f1669126` | H1m 值，本卡未动 |
| 前任门日志 `.tmp/h1i-gates.log` | 全 rc=0；契约 `118 passed`；`150 registered`；全量 `2699 passed, 3 skipped`；PRE/POST `gate_payload_sha256=cfa0f118…63afd6` `EQUAL=YES` | 一致 |

允许面（`git diff --numstat b35bc37 HEAD`）：`domain.sh` +161/−0、契约 +600/−4，无其它文件。
两枚旋钮：`MINEKIN_DOMAIN_SEAL_JOINER_SERVER_LOG`（第①格，绑定 `domain.sh:213`、守门
`:546–:560`、forge `:3089–:3094`）与 `MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS`（第②格，绑定 `:224`、
守门+回读 `:905–:983`，名字取自 `:893–:898` 的 `probe_args`）。

## 1. 前置不满足的一格：桥产物未就位（失败材料保留，改名 `-FE1`）

`workspace:bridge-1201` 的加载路径是本树 `bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar`
（`mods.py:93–:97` 只判存在），而 `run.sh`/`drive.sh` 把钉值 jar 挂在 `/bridge` —— 那个路径
产品不读。前任的第一发活体因此在**任何世界动作之前**具名拒止：

```text
{"category": "SUPPLY_CHAIN", "component": "launcher.recipe",
 "message": "the Bridge jar has not been built: /src/bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar is missing",
 "retryability": "OPERATOR_ACTION"}
domain: Kin2 never arrived within 420s
H1i: domain.sh rc=1   /   "the run could not be sealed (exit 2): /tmp/domain-session.json is not a readable run document"
```

材料：`.tmp/h1i-live/out-host/a_d-FE1-bridge-jar-not-staged/`（未删）。处置：把钉值 jar 以
`sha256 = e50d61c209be98136216b34aadbb6d5a12db8def8aa63a536f32cda8e287006f` 放进
`bridge-1201/build/libs/`（`build/` 被 gitignore，且 `recipe.py:138–:145` 的
`source_tree_sha256` 具名剔除 `{.gradle, build}` ⇒ 不动 recipe 的 source 钉，口径同 §2.46），
并在外层驱动里加了「起跑前具名校验该路径」的闸（缺则 `exit 4`，不再静默跑废一发）。

## 2. 两式活体（同一 `domain.sh` 字节、同一钉值桥、私有卷 `minekin-h1i-live`）

形状取 §2.52 的**单名探测**面（`MINEKIN_DOMAIN_PROBE` 与 `PROBE_SECOND` 都不设），
`MINEKIN_DOMAIN_CASE=CORE-030`、`MINEKIN_DOMAIN_CASE_ON=joiner`、专服形状
`MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`，宿主 `Kin`／加入者 `Kin2`：

| 式 | 两枚旋钮 | run 目录 | 加入者到场 | `Kin` 答题行 | `Kin2` 答题行 | `domain.sh` rc | 封存结果 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `a_d` | ①=1 ②=1 | `/data/server-runs/run-2` | `the world heard Kin2 arrive` + `admitted its first snapshot` | 6 | 0 | 1 | **未封存**，具名拒止（见下） |
| `b_unset` | 都不设（`+x` 未定义） | `/data/server-runs/run-3` | 同上 | 6 | 0 | 1 | **未封存**，同一句具名拒止 |

两式的封存拒止逐字相同：

```text
domain: the run could not be sealed (exit 2): {"message": "the run that hosted this world did not record a world of its own", "schema_version": 1, "status": "unsealed"}
```

⇒ 这条与两枚旋钮**无关**：它是 `tools/seal_run_evidence.py:426–:434`，触发点是加入者支
无条件递出的 `--world-run-document /tmp/domain-session.json`（`domain.sh:3073`，本卡未碰该行），
而进了专服的客户端其宿主文档 `run.world_snapshot` 为 `null`。详见 §5。
材料：`.tmp/h1i-live/out-host/{a_d,b_unset}/`（`00-header.txt` 内有本式实际字节/摘要与旋钮取值，
含 `*_PRESENT=yes/no` 一格以区分「设为 0」与「根本不设」）。

## 3. 四枚反证

### (a) 打开第①格 ⇒ 加入者侧封出的 bundle 里确有 `server/server.log`，且内含按名答题行

1. **命令面取自盘上字节**（把 `domain.sh:3089–:3094` 原样抽出交给 bash）：

   ```text
   H1i-CE: world_args(switch off) = []
   H1i-CE: world_args(switch ON ) = ['--server-directory', '/data/server-runs/run-2']
   H1i-CE: the only difference is the directory, and no profile/jar rides with it = True
   ```

   （材料 `.tmp/h1i-live/out-host/ce_ab/10-argv.txt`）
2. **真 bundle 的内容面**（`.tmp/h1i-live/out-host/ce_ab2/70-reprint.txt`，
   bundle 副本 `ce_ab2/bundle-switch-on/`，私有卷 run `4cdf17f8…`）：

   ```text
   H1iR: 'server/server.log' EXACTLY in the seal report = True
   H1iR: BUNDLE server/server.log size=10633 sha256=628b36b5f1f4abb633d01a24fb9805c95132d364161cfd7e2d551663d3ba4b0f
   H1iR: BUNDLE answer-lines-by-name={"Kin": 6}
   H1iR:   Kin first | [17:29:13] [Server thread/INFO]: Kin has the following entity data: [7.5d, -60.0d, -7.5d]
   H1iR: MANIFEST 'server/server.log' record={"path": "server/server.log", "sha256": "628b36b5…4b0f", "size": 10633}
   H1iR: MANIFEST digest agrees with the stored bytes = True
   ```

   存的正是本 run 那台服务端自己写的日志（`run-2/server.log` 同摘要，见 §4 表下）。
   世界三元组没被这一格改动：`MANIFEST world fields={"seed_or_snapshot_id": null,
   "server_config_digest": null, "world_kind": null}` ⇒ §2.50「只加目录不改 `world` 字段」在活体上成立。
   该 bundle 的 `result=FAIL`（CORE-030 的位移判据在这一形状下不成立），本文**不**据此求绿，
   只取「载体在位 + 内含按名答题行」这一格。

### (b) 两枚旋钮都不设 ⇒ 该 artifact 不出现（否则 (a) 恒真）

同一份真实目录、同一份盘上的 `collect_artifacts`（`tools/seal_run_evidence.py:195`），
只差那个目录给不给（`.tmp/h1i-live/out-host/ce_ab/20-collect.txt`）：

```text
H1i-CE: real directory contents      = ['banned-ips.json', …, 'server.log', 'server.properties', 'usercache.json', 'whitelist.json']
H1i-CE: roster WITHOUT the directory = ['orchestrator-trace.json', 'run-document.json']
H1i-CE: roster WITH the directory    = ['orchestrator-trace.json', 'run-document.json', 'server/server.log', 'server/server.properties', 'server/usercache.json']
H1i-CE: added by the directory alone = ['server/server.log', 'server/server.properties', 'server/usercache.json']
H1i-CE: 'server/server.log' appears ONLY with the directory = True
```

即：不开第①格 ⇒ 三件 `server/*` 一件都不出现，与 M 在 tools 侧独立量过的对照结论逐字同向。
默认关闭的命令面等值另有两格兜底：`world_args(switch off) = []`（上面 (a) 的第 1 条）与
两式活体的同一句封存拒止（§2 表），说明第①格关着时封存调用没有多看见任何东西。

### (c) 递出一个本 run 从未问过的名 ⇒ 具名拒止，且 `exit 2` 早于任何落盘

第②格的名字只从 `probe_args` 读出，因此「本 run 没问过的名进得去」这一形状只能在
**/tmp 的一次性副本**上种出来（`/src` 全程 `:ro`，盘上字节未动）。数据根换成**全新空私有目录**
⇒ 「什么都没写」是绝对读数而非比较读数。
材料 `.tmp/h1i-live/out-host/ce_c_planted/`（驱动 `.tmp/h1i-live/ce-c-drive.sh`）：

```text
domain: the sealed probe set holds 2 names and this run asked 1 (Kin NeverAsked); the two have to be the same set -- refused here, before anything is written
H1i-CE: domain.sh rc=2
H1i-CE: /data entries after = 0     RUNDIRS-ABSENT     PROFILE-ABSENT     NO-JVM     /tmp seal channels = 0
df86c258…domain.sh   （跑完仍是这个值）
```

种桩是桩，所以另配一枚**零改动**的同族具名拒止（`ce_c_badname`）：把探针目标写成一个服务端
永远答不出的名，盘上字节直接应答：

```text
domain: MINEKIN_DOMAIN_SEAL_PROBED_PLAYERS would seal Not\ A\ Vanilla\ Name as a probed name and that is not a vanilla player name (3 to 16 characters of A-Z a-z 0-9 _); the server was never able to answer a probe for it -- refused here, before anything is written
H1i-CE: domain.sh rc=2   /   entries after = 0   RUNDIRS-ABSENT   NO-JVM
```

守门位置可判：`:213/:224` 铸旋钮、`:546–:560` 第①格守门、`:905–:983` 第②格守门+回读，
本 run 的第一次落盘（run 目录编号）在 `:1036`、服务端起程在 `:1097` ⇒ 「早于任何落盘」是行序事实。

### (d) `MINEKIN_DOMAIN_PROBE` 未设时被封的名是白名单账号本人

同一方法：把盘上的 `:893–:898` 与 `:905–:983` 两段原样抽出交给 bash，环境只喂一次
（`player` 即 `domain.sh:25` 的 `MINEKIN_USERNAME` 绑定），看回读后的 `seal_probed_player_args`
（材料 `.tmp/h1i-live/out-host/ce_d/10-derived.txt`）：

```text
(d) PROBE unset / SECOND unset / switch ON   probe_args names=['Kin']            handover=[--probed-player Kin]                                   sealed names=['Kin'] (count=1)
    PROBE unset / SECOND=Kin2 / switch ON    probe_args names=['Kin','Kin2']     handover=[--probed-player Kin --probed-player Kin2]             sealed names=['Kin', 'Kin2'] (count=2)
    PROBE=Ghostz  / SECOND=Kin2 / switch ON  probe_args names=['Ghostz','Kin2']  handover=[--probed-player Ghostz --probed-player Kin2]          sealed names=['Ghostz', 'Kin2'] (count=2)
    PROBE unset / SECOND unset / switch OFF  probe_args names=['Kin']            handover=[]                                                      sealed names=[] (count=0)
H1i-CE: (d) the unset-PROBE shape hands out the whitelisted account's own name, and exactly one name (['Kin'] == ['Kin'], not the empty string, not the joiner's Kin2) = True
```

活体侧同格：`a_d` 式（`MINEKIN_DOMAIN_PROBE=<unset>`、`PROBE_SECOND=<unset>`、②=1）封出的
bundle 里 `asserter-inputs.json` 记的是——

```text
H1iR: BUNDLE probed_players=['Kin'] username='Kin2' kin_id='kin-h1i-join' run_id=4cdf17f8…
H1i-CE:   the name is MINEKIN_USERNAME's account, not the empty string and not the joiner's name = True
```

⇒ 非空、不是 env 里的裸名（env 本无值）、也不是加入者 `Kin2`；未设 `PROBE_SECOND` 时**只递一名**。

## 4. 门（逐条单独跑、先取退出码）

`9e7e47d` 上前任的 PRE/POST 见 `.tmp/h1i-gates-pre.log` / `-post.log` / 摘要 `.tmp/h1i-gates.log`；
本续任在带本记录的树上重跑一遍（`.tmp/h1i-gates-post2.sh` → `.tmp/h1i-gates-post2.log`）：

| 门 | rc | 末行读数 |
| --- | --- | --- |
| `git status --porcelain` | 空（tracked 字节未动；只有本记录与其 `.tmp` 材料未跟踪） | `porcelain lines=0`（跑门时本记录尚未 `git add`） |
| 三件被量测字节 | — | `domain.sh df86c258…640a2`、`run.sh 323f521a…69126`、契约 `daecfa01…a471`（与 §0 一致） |
| `bash -n domain.sh` | 0 | — |
| `bash -n run.sh` | 0 | — |
| 契约 pytest | 0 | `118 passed in 13.94s` |
| `check_case_assertions` | 0 | `Case assertion implementations: OK (150 registered)` |
| `check_boundaries` | 0 | `Minekin package dependency boundaries: OK` |
| `verify_fixture_digests` | 0 | `W00 schema and fixture digests: OK` |
| `check_workflow_pins` | 0 | `Workflow pins: OK (every action is a commit, and each names its release)` |
| `ruff check` | 0 | `All checks passed!` |
| `ruff format --check` | 0 | `369 files already formatted` |
| `pyright` | 0 | `0 errors, 0 warnings, 0 informations` |
| 全量 pytest | 0 | `2700 passed, 2 skipped in 246.28s (0:04:06)` |
| `git diff --check` | 0 | — |
| 门载荷（规范卷 `:ro`，`report_promotion.py --data-root /data`） | 产品侧 `rc=1`（阻断清单非空，与前任同值） | `size=103921`，`gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6` |
| PRE / POST / POST-2 三向比较 | — | 三份 `gate_payload_sha256` **同为** `cfa0f118…63afd6` ⇒ `EQUAL=YES`，两格默认关闭不改载荷 |

**全量计数的 2699/3 → 2700/2 一格差异（不掩盖）**：tracked 字节完全一致，差异来自本机环境。
`tests/unit/test_tested_provenance.py:353–:358` 在 `bridge-1201/build/libs/minekin-bridge-
1201-0.0.0.jar` 未构建时 `pytest.skip`；本续任为跑活体按钉值把该 jar 放进了这个被 gitignore 的
路径（§1），于是那一格从 skip 变成真实运行并通过。单跑该族的读数：
`151 passed, 1 skipped in 36.52s`，唯一 skip 是 `tests/unit/test_orphans.py:686`（平台不回答此问），
另一 skip 来自 `tests/unit/test_silent_listener.py:123`（win32 不做 signal 语义）。⇒ 计数变化与本卡
字节无关，两次运行都全绿；本记录不据此声称任何晋级。

## 5. 未闭合项（如实）

1. **战役路径封不出加入者 bundle**：专服形状下 `--world-run-document` 递的是宿主自己的文档，
   而它 `run.world_snapshot = null` ⇒ `seal_run_evidence.py:426–:434` 具名拒止；把该参数去掉，
   又落到 `:735–:754`（「no server profile was given, but the record shows a world」，实测两式同句，
   材料 `ce_ab/30-campaign-switch-{off,on}.err`）。⇒ (a) 的 bundle 级证据因此来自一处**具名申报的
   偏差**（`ce_ab2`：两侧都补 `--server-profile`、都不递 `--world-run-document`，其余逐字同，
   只差第①格那一枚 flag）；OFF 侧连这种偏差也封不出（`WORLD_RECORD_INCONSISTENT`，
   `ce_ab2/50-switch-off.err`），故 (b) 只交到**决定花名册的那一处调用**（§3(b)）为止。
   这不是本卡两枚旋钮造成的，也不在本卡允许面里能修：要么让宿主文档记下世界，要么重开
   sealer 的世界命名支——**都属改判据/改封存面，留 M 裁决**，本卡未动。
2. **`run.sh` 未转发两枚旋钮**：转发面在本卡允许面之外（前任已在契约里把两个名字登记为
   `SEAL_HANDOVER_KNOBS` 精确缺口并断言「在 `domain.sh` 有、在 `run.sh` 无」），因此经 `run.sh`
   起跑的 run 两格必关——这是 shipped default，不是泄漏；补转发需另开一格卡。
3. `mandatory`/registry/判据/认证/地址/lease 零改动；`CORE-030` 在本形状下 `result=FAIL`，
   未据此求绿，也未回指旧案。

**四态**：真实封证 **0**（本文全部为私有卷/私有目录活体读数）；仅在分支 =
`codex/minekin-h1i-probe-target-handover`（本笔与其上的 `9e7e47d`）；未验证 = 合入复审（归 M）。
失败材料 `-FE1` 与全部 CE 材料未删。
