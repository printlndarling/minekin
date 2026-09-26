# 1.20.1 tested 门禁只读复判（V1201-TESTED-GATE-READOUT-001）

> 只读复判记录，2026-09-26，baseline `818e2bd46492698679325b8b02076b0a62deb655`（in-image python 3.12.3）。
> 目的（执行计划 A3 卡面）：在**规范数据根**与**当前构建**上重读 registry/provenance、case 清单、四读和负向矩阵，
> 给出“1.20.1 本地可玩”到底断言到哪一步、以及它**不**代表远程/全版本的哪一步。
> 本记录**不改**产品代码、case 判据、registry 字节、`status/gaps` 或任何已封存证据；它只读数、判定、把边界写清楚。
> 挂载即证据：容器内 `os.access('/data', os.W_OK) = False`，`/src` 只读，全程未连接任何远程服务器。

## 0. 复现入口

两个脚本都是 `.tmp/` 未跟踪文件，都在同一镜像、同一只读挂载下跑：

```bash
export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"
# 读数
docker run --rm --entrypoint /bin/bash \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/data:ro -v minekin-v1201demo3:/demo:ro \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -w /src minekin-runner:local -lc 'bash /src/.tmp/a3-gate-readout.sh'
# 反证（证明读者能判红）
docker run --rm --entrypoint /bin/bash \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/data:ro \
  -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -w /src minekin-runner:local -lc 'bash /src/.tmp/a3-readout-reversal.sh'
```

日志：`.tmp/a3-gate-readout.log`（8 段）、`.tmp/a3-readout-reversal.log`（R0–R4）。
本记录里每个数字都出自这两份日志，不是 registry 或旧文档的自述。

## 1. 结论表：五个问题，五句读数

| # | 问题 | 当前 build 的机器读数 | 判定 |
| --- | --- | --- | --- |
| T1 | registry 的 `tested` 是否只写在文件里？ | `verify_tested_provenance.py --data-root /data` → `verified: true`、`rc=0`、两条条目 `findings: []`，逐条引用 `present/readable/consistent/sealed` 全真，1.20.1 六条引用全部 `result: PASS` | **成立**：`tested` 已被独立机器校验对照到磁盘真件（09-25 审计的 A3 缺口已由该工具闭合，见 §6 R1/R2 的反证） |
| T2 | 六条被引用的 1.20.1 封证今天还成立吗？ | 逐条四读：`evidence verify` 全 `status: verified / result: PASS`，`rejudge_evidence.py` 全 `status: agrees / PASS`，`replay_evidence.py` 全 `status: projected`，registry 侧 `re_judged: AGREES`、`from_repository_build: true`、`violations: []` | **成立**：正读、反判、投影、晋级读数四读一致，且都归属当前仓库构建（plan `83299ad5…`/bridge `e50d61c2…`） |
| T3 | “1.20.1 本地可玩”能声称到哪一步？ | registry 声明的 19 个 capability 与六条 case 的断言并集**双向差集为空**（`asserted but NOT claimed: []`、`claimed but asserted by no case: []`） | **成立且不过声称**：条目声称的能力恰是六 case 各自判出来的事实，一条不多一条不少 |
| T4 | 这些证据是否让某个门可晋级？ | `report_promotion.py`：W60 `promotable: false / CASE_VERSION_MISMATCH`（阻塞 `CORE-040`、`CORE-050`），W70 `false / NO_MANDATORY_CASES`，`p0-core` `false / CASE_VERSION_MISMATCH + REQUIRED_CASE_NOT_REGISTERED`，overall `false`；六条 V1201 case 全 `mandatory: false` | **不成立**：1.20.1 的封证支撑的是 `tested` bundle 条目，不支撑任何 gate 晋级；把 A3 读数当 V08 或 `p0-core tested` 是误读 |
| T5 | 规范卷上有没有被藏着的结果？ | 卷内 1.20.1 家族 15 次 attempt：6 条被引用（全为本 build PASS），规范卷上另有 2 条本 build 等强 PASS 未引用（`V1201-020` seq3 `7236c53e…`、`V1201-040` seq3 `6a86da03…`；A1 的等强 PASS `fc12d7d1…` 在独立卷 `minekin-v1201demo3`，不在这 15 行里），5 条属旧 build（plan `ac403160…`，`from_repository_build: false`），其中含旧 build 的 `V1201-010` seq1 `FAIL` + `UNJUDGED`（判据已从 `1f4c3663…` 移到 `d9446f64…`），2 条本 build sealed **FAIL**（`V1201-080` seq1/2）保留未删 | **记录**：引用哪一条是主控动作；本卡不翻 `status/gaps`、不改引用摘要，只把“还有等强 PASS 未被引用”和“失败材料仍在”写成读数 |

## 2. 封证清单：规范卷上 1.20.1 家族的 15 次 attempt

`report_promotion.py --data-root /data` 的 `evidence.bundles` 读数（86 个 bundle 中 15 条属 `V1201-*`；`attempts: 50`，`unsealed/unverified/unreadable` 均空，`from_another_build` 全卷 61 条）：

| case | seq | run | 结果 | 当前 build | registry 引用 | re-judge |
| --- | --- | --- | --- | --- | --- | --- |
| V1201-010 | 1 | `e0f49710…` | FAIL | 否（`ac403160…`） | 否 | `UNJUDGED`（case 版本已从 `1f4c3663…` 移到 `d9446f64…`） |
| V1201-010 | 2 | `bc203c0e…` | PASS | 否 | 否 | AGREES |
| V1201-010 | 3 | `8665b021…` | PASS | **是** | **是**（`dc30bdaa…`） | AGREES |
| V1201-020 | 1 | `87229052…` | PASS | 否 | 否 | AGREES |
| V1201-020 | 2 | `ece5d0cb…` | PASS | **是** | **是**（`bc987a32…`） | AGREES |
| V1201-020 | 3 | `7236c53e…` | PASS | **是** | 否 | AGREES |
| V1201-040 | 1 | `f4cc67ae…` | PASS | 否 | 否 | AGREES |
| V1201-040 | 2 | `155dcb4a…` | PASS | **是** | **是**（`435ab159…`） | AGREES |
| V1201-040 | 3 | `6a86da03…` | PASS | **是** | 否 | AGREES |
| V1201-060 | 1 | `f71c56f0…` | PASS | **是** | **是**（`90d490ce…`） | AGREES |
| V1201-070 | 1 | `5b1cbef5…` | PASS | 否 | 否 | AGREES |
| V1201-070 | 2 | `ecebb080…` | PASS | **是** | **是**（`eb054c0a…`） | AGREES |
| V1201-080 | 1 | `6d11ab7d…` | **FAIL** | **是** | 否 | AGREES（判官同意它该红） |
| V1201-080 | 2 | `ffdd54fc…` | **FAIL** | **是** | 否 | AGREES |
| V1201-080 | 3 | `484675e4…` | PASS | **是** | **是**（`22fb57f3…`） | AGREES |

registry 引用摘要逐个被工具重算对照（`verified: true`，`rc: 0`，两条条目 `findings: []`）。六条被引用 run 的 `from_repository_build` 全为 `true`、`launch_plan_digest` 全为 `83299ad5…`（§2 表格逐行可查）⇒ 没有任何被引用的 1.20.1 run 落在旧 build 上；这是从表行推出的结论，不是某件工具的原样输出字段。
1.20.1 条目 `bridge_digest e50d61c2…`、`launch_plan_digest 83299ad5…`、`recipe_digest 8ce43e26…` 与仓库当前 recipe/bridge 实测一致（`measured.bridge.jar_sha256` 同值）。

## 3. 能力边界（正面）：`1.20.1 本地可玩` 只指这 19 件事

六条 case 一共 22 个断言槽位，去重后 19 个 token = registry 的 `capabilities`（工具读数 `{"capabilities": 19, "case_assertions": 19}`，双向差集为空，§1 T3）。`move_input_was_leased` 由 `V1201-040/060/080` 共享，`the_server_saw_the_kin_stop_after_the_move` 由 `V1201-060/080` 共享：

- **只读探测与握手**（`V1201-010`，W20）：`handshake_accepted_by_core`、`stayed_observe_only`。
- **入服与首快照**（`V1201-020`，W40）：`server_observed_join_identity`、`first_snapshot_admitted`、`leave_after_join_observed`。
- **限幅移动与转向**（`V1201-040`，W60）：`move_input_was_leased`、`the_bridge_carried_the_input_out`、`the_server_saw_the_kin_move`、`the_lease_expired_and_was_released`、`the_server_saw_the_kin_turn`。
- **断连后松键**（`V1201-060`，W70）：`runtime_controller_sigkill_was_confirmed`、`the_bridge_released_the_input_when_the_ipc_was_lost`、`the_server_saw_the_kin_stop_after_the_move`（+ 共享的 `move_input_was_leased`）。
- **拒止首快照**（`V1201-070`，W50）：`this_run_joined_a_world_it_was_never_told_it_could_play`、`the_first_snapshot_was_refused_by_the_reason_the_case_names`、`a_refused_first_snapshot_became_no_lease_and_no_playable`、`the_refused_generation_was_closed_and_never_reopened`、`the_refusal_was_asked_of_this_run`。
- **正常停止松键**（`V1201-080`，W70）：`the_bridge_released_the_input_when_the_session_was_stopped`（+ 共享的 `move_input_was_leased`、`the_server_saw_the_kin_stop_after_the_move`）。

再加上 A1 在同一 run 里量到的连续性（自动装机 `3639/3639` → JOIN → `PlayableEstablished` → 同 generation 的 lease+look+move → 到期释放 → 退出），“可玩”的完整说法是：

> **在受控本地 offline 1.20.1 服务器上，当前构建的 Kin 能自动选中该 bundle、装机、入服、看到首快照、被租约限住、完成一次有界移动/转向并在到期或正常停止时真正把键松开。**

## 4. 能力边界（反面）：这些都不是 1.20.1 已证明的

| 类别 | 机器/文档依据 | 边界 |
| --- | --- | --- |
| 远程目标 | registry `gaps: REMOTE_TARGET`；`session start` 对非 loopback 字面 IP 在装载期 `ADMISSION` 拒 | V08 未提升 ⇒ 一次都没连过用户服；本地 loopback 证据不外推到公网目标 |
| 版本/平台覆盖 | `gaps: WINDOWS_OS_ARCH`、`RUNNER_JDK_17_UNSEALED`；条目 `os_arch linux-x86_64`、`java_major 21`（recipe 自己写 17） | 只证 linux-x86_64 + Java 21；Windows 与 recipe 声明的 JDK 17 路径无封证 |
| 目标变更与恢复 | `gaps: USE_TARGET_BLOCK_CHANGE`、`CRASH_RECOVERY_CASES`、`RESTART_RECONCILIATION_CASES`、`SOAK_CASES`、`OFFLINE_IDENTITY_LEDGER_CASES` | 换目标、崩后恢复、重启对账、长 soak、离线身份账本都没有 1.20.1 封证 |
| 自动入口门序 | A2 §3：`--auto-bundle` 下同一 profile 在 `--profile` 2 秒拒、自动路径先下到 388 文件（空 store）或过完 3639 项（满 store）才拒，`java=0` | 授权没被绕过但顺序不对；已登记 `V1201-AUTO-ENTRY-GATE-ORDER-001`（`QUEUED`，N1） |
| 预算与磁盘输入 | A2 §4：`--max-bytes 0/-1` → `exit=70 INTERNAL_INVARIANT`；`--max-bytes` 与 `--profile` 同给被静默忽略；`src/minekin_core` 无磁盘预检实现 | 已登记 N2 `V1201-MAX-BYTES-VALIDATION-001`（`QUEUED`）与 N3 `V1201-DISK-PREFLIGHT-001`（`BLOCKED_DECISION`） |
| 目标解析 | 唯一实现 `SavedAddressResolver`（`server_probe.py:69`），profile host 必须字面 IP | 无 DNS/SRV 路径 ⇒ N4 `V1201-SRV-RESOLVER-001` 是产品选择，不是本卡能填的洞 |
| 封装配对通道 | A1 的 G1（`domain.sh` 不捕获 `--auto-bundle`）、G2（受控 launcher 写 `enable-status=false`）、G3（无一条 case 同时断言 JOIN+PLAYABLE+look/move+释放） | 登记为 `V1201-AUTO-PATH-RUNNER-001`（`QUEUED`）与 `V1201-DEMO-CASE-FREEZE-001`（`BLOCKED_DECISION`）；本卡不动判据 |
| 门与晋级 | §1 T4 的 `report_promotion` 读数 | 六条 V1201 case 全非 mandatory ⇒ 它们不会让任何 W 门变绿；“bundle tested” 与 “gate promotable” 是两个不同声称 |

## 5. 与 09-25 审计的对照：哪几格已被机器填上

[tested 晋级门复判记录](tested-gate-audit-2026-09-25.md) 登记了四张后续卡。今天的读数：

- A3（`tested` 缺独立机器校验）→ 已有 `verify_tested_provenance.py`，本卡 §1 T1 用它读出 `verified: true / rc=0`，且 §6 R1/R2 证明它能判红。**该格已由工具填上，不需要再建卡。**
- A5（BridgeHello 谎报版本）→ registry 条目 notes 与 `measured.bridge` 读数表明 1.20.1/1.21.4 两条目都已按真实 runtime 重封；本卡不重开该问题，只记录“引用摘要与当前 build 一致”。
- A2（停止阶段显式松键）→ 1.20.1 的 `gaps` 里已无 `STOP_PHASE_EXPLICIT_KEY_RELEASE`，且 `V1201-080` seq3 在本 build `PASS / AGREES`；该 token 现在只在 1.21.4 条目上。
- A6（store 故障注入证据）与 `KEY-RELEASE-AT-STOP`/`STORE-FAILURE-EVIDENCE` 的原始诉求：本卡没有对应机器读数（规范卷里没有这类 case 的 bundle），仍属未闭，交由各自卡处理，本记录不宣布它们完成。

## 6. 非空转：读者能不能判红

一条只读记录最容易空转（“什么都没查，全绿”）。四个反转都在 `/tmp` 里做，规范卷只读：

| 反转 | 做法 | 读数 |
| --- | --- | --- |
| R1 | 同一 registry 指向一个没有任何证据的空数据根 | `rc=1`，逐条 `CITATION_BUNDLE_MISSING`（“no bundle directory is named 8665b021… under the evidence roots”），共 379 行输出 ⇒ 与对照 R0（`verified: true`）不同 |
| R2 | 把一条被引用的 `bundle_digest` 改一个十六进制位 | `rc=1`，`CITATION_DIGEST_MISMATCH`：`"the bundle there digests to dc30bdaa…, not the cited 0c30bdaa…"` ⇒ 摘要真是被算出来的，不是被比字符串前缀 |
| R3 | `report_promotion.py` 分别指向空根与规范根 | 空根 `evidence.count = 0`、规范根 `= 86`，两份输出不同 ⇒ 晋级读数确实由磁盘证据驱动（两边都 `promotable: false`，所以只有比字节才知道它在读什么） |
| R4 | 把一个 bundle 复制到假根，删掉 `bridge-trace.jsonl`、给 `run-document.json` 追加一个空格 | 未改副本：`evidence verify` `rc=0 status verified`；改后：`rc=12 status: invalid, verified: false`，`rejudge` `rc=2 status: unjudged — ARTIFACT_DIGEST_MISMATCH:run-document.json, ARTIFACT_MISSING:bridge-trace.jsonl` ⇒ 工件级完整性与判官都吃这一改 |

正对照即 §1 T2 的六条真件：同一套读者在真件上全绿，在 R1–R4 的破坏上全红。

## 7. 本卡不声称

- 不是 V08 晋级，不是对任何远程目标的许可；本卡一次网络出站都没有（假端点只出现在 A2 的 loopback 记录里）。
- 不翻 registry 的 `status`/`gaps`，不改任何 case 判据或摘要；§1 T5 的“等强 PASS 未被引用”是读数，不是更换引用的建议。
- 不声称 `p0-core`、W60/W70 或任何 W 门可晋级（§1 T4 恰好相反），也不声称 1.21.4、Windows、JDK 17、HOST、PERSIST、在线认证。
- 不重封任何证据：本卡只读，两次运行都以只读挂载完成（容器内 `data writable False` 为凭）。
- 未测并保留：F4 后半句“部分装机后旧 blob 仍可整店复验”今天仍无 store 级读数（`bundle verify` 判 recipe 可启动性）；A2 已登记该空白，本卡不猜。
