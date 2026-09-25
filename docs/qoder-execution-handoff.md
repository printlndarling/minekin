# Qoder 临时执行交接（2026-09-24）

> **用户优先级再确认（2026-09-25）**：现阶段主线是 **1.20.1 入服与最小控制**，不是继续开发
> 1.21.4。`BRIDGE-1214-RUNTIME-IDENTITY-001` 已作为必要的已建成版本身份/回归修复收口；
> 此后依主计划唯一 `NEXT` 做 1.20.1 松键证据、V08 前必要的安装故障门、V08–V10。
> 1.21.4 只做必要回归，不因 `.tmp/` 里有临时脚本、日志或镜像材料就另开其功能专题。
> `.tmp/` 被 Git 忽略，是构建、诊断和封证的临时工作区；它的内容不是已推送产品代码、
> 不是阶段状态，也不能替代主计划里的 run/bundle/attempt 与真实门禁记录。

> **最新交接点（2026-09-26，HOST 支线设计卡收口：问题读到底，留下三格所有权交主控；计划暂无 `NEXT`）**：
> 收卡提交是本文件所在的这一次提交（其 SHA、两条 ref 与 CI 读数在 push 后回填进主计划该卡的
> `completion_readings_2026-09-26` 第 7 格）；登记 **`51646d5`** → 提升 **`da43c98`** → 实现 = 收卡提交，
> 逐卡串行、一步一提交。交付形状：新文档 `docs/host-admission-session-coordinate-design.md`——
> 41 行锚点表（每行写"位置 + 该行必须含有的片段"，由 `.tmp/check_host_design_anchors.py` 逐条读盘核对、
> `exit 0`）、三条方案各带四要素（谁创建 `generation` 与 `WorldCapsule`、首快照由谁收集由谁判、失败与重启
> 语义、与既有契约的冲突点）、R1–R7 反例配一条 positive control、`HOST-001` 的真实 trace 验收设计，
> 结尾是**分歧矩阵而不是选择**。**读数**：六条变异各红在其命名理由上（改错一个行号 → `does not contain`、
> 删掉一个要素 → `is missing element`、加一句"本卡选定方案 B" → `chooses an option`、截掉锚点表 →
> `anchor rows parsed: 0 < 30`），原文按字节 digest `b0e30acb3afb…` 前后一致；全量门禁
> `2501 passed / 2 skipped` 与上一张卡**逐字相同**；容器内 `report_promotion.py` 里 `host-integrated`
> `promotable: false` + `blocks: [NO_MANDATORY_CASES, REQUIRED_CASE_NOT_REGISTERED]`、18 条 absent 含
> `HOST-001`，`HOST/W80+` 仍 `DEFERRED`、`tests/fixtures/cases/host-001.json` 仍不存在——
> **HOST 没有因此前进一格**，V08 仍未提升、用户的远程服仍未连接。
> **下一步归主控（执行者不代答）**：把设计文档 §5 那三格冻结——宿主世界的 `generation` 由谁分配
> （建档时的控制面 vs 下发时的 Core 会话运行时）、`WorldCapsule` 的权威来源与是否落盘、
> 规则 2 对一个没有 server profile 的宿主世界如何算一致性。冻结之前队列里没有可提升的卡，
> 也不该出现任何 HOST 实现卡。仍归主控：V08 提升、连接用户的远程服、
> `EXPLICIT-RELEASE-AT-STOP-001` / `OPERATIONS-RETENTION-001` / `PROCESS-RECOVERY-001` 的状态。
> 恢复现场时先核主计划 `current_next` 与本文件是否仍一致。
>
> **上一交接点（2026-09-26，1.20.1 的停止阶段松键缺口已从 `tested` 声明划出）**：
> 收卡提交是 **`b03863e`**（两条 ref 与远端 SHA 已核：`git ls-remote` 上 `main` 与
> `codex/core-state-transition` 同为 `b03863e2346ed559b6d33fe7482d7fa0619f82df`；GitHub Actions 对该 SHA 的
> 两个 `CI` run `36176584903`/`36176584988` 及其六个 job `python`/`protocol`/`bridge-static` 全
> `completed / success`，step 层除 `success` 只有 `skipped`），实现 **`4151664`**；（登记 `89ec146` →
> 提升 `822d7f0` → 实现 `4151664` → 收卡 `b03863e`，
> 逐卡串行、一步一提交，满足第 3、4、6 项）。交付形状：`tests/fixtures/registry/reviewed-tested-bundles.json`
> 的 entry[0]（`1.20.1-linux-x86_64-offline-java21`）`gaps` 9 → 8（**只**去掉
> `STOP_PHASE_EXPLICIT_KEY_RELEASE`）、`capabilities` 18 → 19（补
> `the_bridge_released_the_input_when_the_session_was_stopped`）、`evidence` 5 → 6（`V1201-080` /
> run `484675e4938b4134b788a971e195619b` / bundle `22fb57f3…` / attempt 3 / `PASS`，其 bridge 与 plan 摘要
> 与该 entry 自身相同）；`tests/fixtures/manifest.sha256:85` `69244c32…` → `6dd2f421…`，由门禁自己的
> 测量函数量出；`tests/unit/test_version_resolution.py` 只加一条用例，钉住"这一格已划出**且 1.21.4 那条仍在**"。
> **读数**：容器内 `verify_tested_provenance.py` 对新文件 `verified: true`、`exit 0`，六条引用逐条
> `present/readable/sealed/consistent` 为真；`report_promotion.py` 里 `V1201-080` attempt 3 那行
> `from_repository_build: true` + `re_judged: AGREES`，整体仍 `status: blocked`、
> `overall.promotable: false`、`repository_build.gates_promotion: false` ⇒ **V08 未提升、远程服未连**；
> registry 不在 49 个 case 的 `inputs` 里（同一检测逻辑对人为加输入的副本报 1）⇒ 无 `case_version` 移动、
> 无重封；四条反证各红在其命名理由上、positive control `exit 0`、变异后按字节还原；本地全量门禁
> `2501 passed / 2 skipped`（上一张卡 2500 + 本卡新增 1）。
> （**2026-09-26 更正**：这一段当时写的"下一步是把 `HOST-ADMISSION-DESIGN-001` 由 `BLOCKED_DECISION`
> 转 `QUEUED` 并按唯一 `NEXT` 提升"已经全部落实——登记 `51646d5`、提升 `da43c98`、设计文档由收卡提交落地，
> 见上面最新交接点。这里保持当时那句话原样不改写，只标注它已被执行。）
>
> **上一交接点（2026-09-26，`ADMIT-070-RECORD-SCHEMA-001` 收卡：冻结的 schema 说得出两类记录了；计划暂无 `NEXT`）**：
> 收卡提交是 **`cc9ced2`**（两条 ref 与远端 SHA 已核；GitHub Actions 对该 SHA 的两个 `CI` run
> `36170297867`/`36170297886` 及其六个 job `python`/`protocol`/`bridge-static` 全 `completed / success`），
> 实现 **`de8ed7d`**（登记 `ff63746` → 提升 `79cf8ce` → 实现 `de8ed7d`，三步分提交，
> 满足交接第 3、4、6 项）。交付形状：`schemas/fault-injection.schema.json` 根 `oneOf` 分
> `$defs.process_sigkill_record` / `$defs.client_report_request_record`，`category` 缺省仍是 kill 一类
> （卷内每张旧封存照读不变），reader `tools/fault_injection.py` **一字未动**（`forbidden_paths`，方向只能是
> 文件向 reader 对齐）。`$comment` 里那句"字段间比较归 reader"仍然成立，但两处"同一件事说两遍"的配对已写进
> 文件：`asked` 由 `value` 的拼写派生、`observed: true` 预设 `asked: true`（即 `EFFECT_WITHOUT_REQUEST`）。
> **读数**：23 件结构反例（10 kill + 13 request）两侧同时被拒、7 种合法形状两侧同时被接受；把 7 条新规则
> 逐一从盘上删掉，那 4 个具名测试作为一组 7/7 变红，未删时 positive control `exit 0`
> （`uv run --frozen python .tmp/schema_counterexamples.py`，读数 `.tmp/schema-counterexamples-final.log`）。
> 本地全量门禁在 `de8ed7d` 干净树上跑：`2500 passed / 2 skipped`、ruff check/format 干净、Pyright 0 errors、
> `check_case_assertions OK (140 registered)`、`verify_fixture_digests OK`、boundaries / workflow pins /
> `git diff --check` 全 0（`bash .tmp/run_local_gates.sh`）。
> **fixture 只动一行**：`tests/fixtures/manifest.sha256:7` `cc983bc8…` → `34e6d26c…`；
> `w00-contract-001.json` 一字未改、其 `case_version` 新旧同为 `c59b9636…`（`case_version` 是 case 文档自身的
> sha256）。**登记这张卡时那句"改 schema 等于给无关 case 重新定版"经测量不准确**——耦合点是
> `fixture_digests_match_manifest` 读那行 manifest。registry 与 `tested` 声明一字未动（旧 digest 全跟踪树无命中、
> registry 只钉 bridge/plan/recipe/bundle 四类摘要），因此没有触发任何重封。
> （**2026-09-26 更正**：下面这段"下一张归主控"是本卡收卡当时的状态，原样保留；主控随后给出答复，
> ①已落成 `TESTED-GAP-DRAW-STOP-PHASE-1201-001` 并收口（见上面最新交接点），③HOST 支线只做设计已授权，
> 队列计数随之从 55 张变为 56 张。V08 提升与远程服授权仍归主控。）
> **下一张归主控**：队列这次是**逐卡数过**的，不是 grep 状态行——`python .tmp/count_plan_cards.py` 报
> 55 张带 `status` 的卡里 `QUEUED` 与 `NEXT` 均为 `0`（同一套逻辑在非空转反证里数得到：临时副本把本卡状态
> 改回 `NEXT` 或 `QUEUED` 各报 `1`，副本已删），开放中的只剩 `REAL-P0-CAMPAIGN-001`
> （`BLOCKED_EVIDENCE`）、`EXPLICIT-RELEASE-AT-STOP-001`/`HOST-ADMISSION-DESIGN-001`/
> `OPERATIONS-RETENTION-001`/`PROCESS-RECOVERY-001`（`BLOCKED_DECISION`）与 `HOST/W80+`（`DEFERRED`）。
> 要往下走得先拍板：①1.20.1 的 `STOP_PHASE_EXPLICIT_KEY_RELEASE` 是否据现有工件从 `tested` 划出、V08 是否提升；
> ②`HOST`/`PERSIST`/远程服授权那几张的决策；③或明确一条新的自主路线。本执行者不自行猜编号、不新造主线卡。
> 恢复现场时先核主计划 `current_next` 与本文件是否仍一致。
>
> **上一交接点（2026-09-26，停止阶段工件到手；唯一 `NEXT` 是 `ADMIT-070-RECORD-SCHEMA-001`）**：
> `GRACEFUL-STOP-KEY-RELEASE-001` 已 **`DONE`**（收卡提交 `2253358`，两条 ref 与远端 SHA 已核，GitHub Actions
> 的两个 `CI` run 对该 SHA 均 `completed / success`）。1.20.1 那一格的读数：实现 `5c643c6`；
> `V1201-080` attempt 3 run `484675e4938b4134b788a971e195619b` / bundle `22fb57f3…` / `result PASS`，
> 封存的 `client/latest.log` 里有 **`bridge released 1 input(s) after CORE_REQUEST (EXPLICIT)`**；
> `V1201-040` attempt 3 run `6a86da0353e746829cc5966ac272ef9d` / bundle `554c467b…` / `PASS`（lease 到期的
> `(TIMEOUT)` N=1 与停止阶段的 `(EXPLICIT)` N=0 各写各的，旧那一格没被改坏）。两跑四读一致、
> `from_repository_build: true`，`input_release_failed` 由旧失败件的 `true` 变 `false`。逐格验收、反证与复跑命令
> 记在 main 计划该卡 `completion_readings_2026-09-26` 与 todo 的收卡现场。
> **registry 一字未动**：那一格现在有 Bridge 自己写的工件，**是否据此从 `tested` 声明里划出该缺口、是否提升 V08、
> 是否连接用户远程服仍归主控**（`HOST-ADMISSION-DESIGN-001`、`OPERATIONS-RETENTION-001`、
> `PROCESS-RECOVERY-001` 仍 `BLOCKED_DECISION`，HOST/W80+ `DEFERRED`）。
> 主线那一格既然归决策而不归执行，本提交依交接第 3 项把队列里唯一可执行的 `QUEUED` 提升为 `NEXT`：
> **`ADMIT-070-RECORD-SCHEMA-001`**（`ff63746` 登记）——`schemas/fault-injection.schema.json` 当时仍只描述
> SIGKILL 那一类记录，而 `tools/fault_injection.py` 已经读两类；缺口当时被
> `tests/unit/test_fault_injection.py::test_the_frozen_schema_still_describes_the_kill_record_only`
> 显式钉住（该测试随 `de8ed7d` 退役，换成双向一致的两条）。`LOCAL_ONLY`，不碰产品代码、不碰判据、不要求真实运行。
> （另需记一笔：本文件更早一版交接点写过"队列中没有可提升的 `QUEUED`"，那是错的——漏看这张自 9 月 24 日就挂在
> `QUEUED` 上的卡；当时的清点只数了 `BLOCKED_DECISION`/`DEFERRED` 三条。该说法已在主计划 checkpoint 里就地更正，
> 清点方式也换成了上面那条按卡头配对状态行的脚本。）
>
> **上一交接点（2026-09-26，停止阶段的显式松键：工件已到手，计划暂无 `NEXT`，下一张归主控）**：
> `GRACEFUL-STOP-KEY-RELEASE-001` 已 **`DONE`** 并由本提交收卡。实现是 **`5c643c6`**（新增
> `adapters/launcher/stop_request.py` 的请求/回执两份文档、`cli/session_runtime.py` 多一对 caller-owned
> `until_stop_request`/`on_stop_request` 分支、`cli/session.py` 的 `stop_session()` 改成"先问后杀 + 有界等待 +
> 超时如实报未确认"，`on_wind_down()` 只在本次已按请求送达 EXPLICIT 时跳过重发）。与设计稿的一处差异：文件名带
> **pid**（`<run_root>/stop-requests/<session_id>-generation-<n>-pid-<pid>.request.json` + 同名
> `.receipt.json`），因为本项目里 `generation` 恒为 1，不含 pid 会让一次未被应答的旧请求截断同会话新一跑的 lease。
> **真跑读数（判据一字未改）**：`V1201-080` attempt 3 = run `484675e4938b4134b788a971e195619b` /
> bundle `22fb57f34abb22ec9c217a06e3083c1e8ae0c7355b9ada1d205d3739221ffe1a` / `result PASS` / 13 件工件，
> 封存的 `client/latest.log:204-205` 是 `bridge released move.forward` +
> **`bridge released 1 input(s) after CORE_REQUEST (EXPLICIT)`**（N=1>0，之前末行仍 `holding [move.forward]`、
> `deathscreen` 计数 0），`session stop` 报 `released:[218] unconfirmed:[]` 且随后终止的就是 218，
> run document 的 `input_release_failed` 由两跑失败件的 `true` 变 `false`；`V1201-040` attempt 3 = run
> `6a86da0353e746829cc5966ac272ef9d` / bundle `554c467bdae9e0582d0b6b28517068899758065f533e2abd55674a611e6cc1e0`
> / `PASS`，同一份日志把 `(TIMEOUT)` N=1 与停止阶段新加的 `(EXPLICIT)` N=0 分开写出，旧那一格没被改坏。
> 两跑四读一致（`evidence verify` PASS/verified/sealed、`rejudge_evidence.py` `agrees`、两个 `replay` 同投
> 21 / 23 条事件到 `STOPPED`、`report_promotion` 那一行 `from_repository_build: true` + `AGREES`）。
> 门禁在 `5c643c6` 上全绿（`pytest tests/unit` = **2200 passed / 2 skipped**、ruff check/format、pyright 0、
> `check_case_assertions.py` `OK (140 registered)`、fixture digests、boundaries、`git diff --check`）。
> 反证：单元侧四条各红在其命名理由（超时当确认 / 先终止后询问 / 去掉"已确认就不重发" / 删掉 wind-down 安全网），
> 判据侧对**真实封存件**交叉跑本卡 token：`V1201-080` attempt 3 ⇒ observed、attempt 2 ⇒ `RELEASE_NOT_LOGGED`、
> `V1201-040` 那条真实的 `released 0 … (EXPLICIT)` ⇒ `HELD_NOTHING_WHEN_THE_SESSION_WAS_STOPPED`、
> `V1201-060` bundle ⇒ `RELEASED_FOR_ANOTHER_REASON:IPC_LOST,LEFT_PLAYABLE(PLAY_ENDED)`；positive control
> `exit 0`。脚本与转录（`.tmp/`，未入库）：`graceful-stop-counterexamples.sh`/`.log`、
> `graceful-stop-token-readings.sh`/`.log`、`graceful-stop-v1201-080-run3.log`、
> `graceful-stop-v1201-080-readers3.log`、`graceful-stop-v1201-040-regression.log`、
> `graceful-stop-v1201-040-readers.log`；旧的 `V1201-080` 两件 `FAIL` 封存件（`6d11ab7d…`、`ffdd54fc…`）原样留在卷内。
> **下一步不是本执行者可代决的**：1.20.1 的 `STOP_PHASE_EXPLICIT_KEY_RELEASE` 那一格现在有 Bridge 自己写的工件，
> **是否据此从 registry 的 `tested` 声明里划出该缺口、是否提升 V08、是否连接用户远程服**都归主控；
> registry 的 `status`/九条 `gaps`/摘要在本提交里一字未动。队列中没有可提升的 `QUEUED`
> （`HOST-ADMISSION-DESIGN-001`、`OPERATIONS-RETENTION-001`、`PROCESS-RECOVERY-001` 仍 `BLOCKED_DECISION`，
> HOST/W80+ `DEFERRED`），`cli/auto_session.py` 的版本切换停止仍是"直接终止"（那张卡明写留在范围外）。
> 恢复现场时先核主计划 `current_next` 应为**暂无 `NEXT`**，与本文件一致后再等其他指示。
>
> **上一交接点（2026-09-25，停止阶段显式松键：判据已交付、工件待产品实现）**：主计划唯一 `NEXT` 是
> **`GRACEFUL-STOP-KEY-RELEASE-001`**（本提交提升；恢复现场时先核 `current_next` 与本文件是否仍一致）。
> `EXPLICIT-RELEASE-AT-STOP-001`（`b22a262` 登记、紧随提交提升为唯一 `NEXT`、判官侧 `f38cf34` 已推两条 ref）
> 由本提交依其 `stop_conditions` **第①格**转为 **`BLOCKED_DECISION`**。机器读数（不是推断）：
> 判官侧新 token `the_bridge_released_the_input_when_the_session_was_stopped`（只收
> `released N input(s) after CORE_REQUEST (EXPLICIT)` 且 N>0）、case `V1201-080`、五条拒绝理由的非空转反证与
> positive control 全部就位，`check_case_assertions.py` 报 `OK (140 registered)`，
> `uv run --frozen pytest tests/unit -q` = `2184 passed, 2 skipped`。但两次受控 1.20.1 真跑都封在同一个命名理由上：
> attempt 1 run `6d11ab7d…`/bundle `6afda194…`（Kin 在停止前被 Slime 杀死，唯一 `released` 行是死亡界面自动松手）、
> attempt 2 run `ffdd54fc…`/bundle `931157fe…`（**去掉了死亡干扰**：客户端日志 `released` 计数 0、
> `deathscreen` 计数 0，末行仍 `holding [move.forward]`，停止落在 lease 到期前）。两跑里
> `move_input_was_leased` 与 `the_server_saw_the_kin_stop_after_the_move` **都 observed**，run document 都记
> `input_release_failed: true`、`outcome: BRIDGE_LOST`。结构性原因：`session stop` 终步对客户端进程
> `terminate(pid)`（`adapters/launcher/orphans.py:314-353`），而 Core 唯一的 `ReleaseAllInputs` 发送点在
> wind-down（`cli/session_runtime.py:423-438`，`connections.close()` 之后、`on_wind_down()` 失败置
> `release_failed`）——**命令发出时接收方已被这次停止终止**，Bridge 无从写下那行。
> **本提交未做的**（都属越界）：改两 root 松键路径或任何产品代码、改判据、动 registry（
> `STOP_PHASE_EXPLICIT_KEY_RELEASE` 仍在九条 `gaps` 里、摘要一字未动）、提升 V08、连接用户远程服、删失败材料。
> **用户 2026-09-25 已答该决策，选 (a)**：「修正产品的停止顺序，先让仍存活的 Bridge 确认松键，再终止客户端。」
> 承接它的是 **`GRACEFUL-STOP-KEY-RELEASE-001`**（`6bef249` 以 `QUEUED` 登记、本提交提升为唯一 `NEXT`；
> 机制、`allowed_paths`、
> 验收与停止条件全在那张卡里；判据与 case `V1201-080` 一字不改，正是它的验收形状）。
> 登记时另测得：Python 侧改动**不**移动 `from_repository_build`（`tools/report_promotion.py:204-222` 只比
> launch plan 摘要），因此被 registry 引用的 16 条 run 不需重封——先前"改产品代码会牵动 1.21.4 重封"的说法据此更正。
> 决策落地前不要另提任何一张卡；`EXPLICIT-RELEASE-AT-STOP-001` 自身的 `forbidden_paths` 不因该决策放宽。
>
> **上一交接点（2026-09-25，本卡领取时）**：主计划**暂无 `NEXT`**，`AUTO-PATH-INSTALL-RUN-001` 已 `DONE`
> 并推到两条 ref（本地 `HEAD`、`origin/main`、`origin/codex/core-state-transition` 均 `e890924`，工作树干净）。
> 队列逐条读过：没有任何 `QUEUED` 可提升——`HOST-ADMISSION-DESIGN-001`、`OPERATIONS-RETENTION-001`、
> `PROCESS-RECOVERY-001` 都是 `BLOCKED_DECISION`，`HOST/W80+` `DEFERRED`。**用户 2026-09-25 选定**下一步是补
> 1.20.1 那条 `STOP_PHASE_EXPLICIT_KEY_RELEASE`（**不是**开远程服），故登记 `EXPLICIT-RELEASE-AT-STOP-001`
> （`b22a262` 以 `QUEUED` 登记），并由紧随的独立提交提升为**当前唯一 `NEXT`**。要点：Core 的 wind-down 以 `ReleaseReason.EXPLICIT` 显式发
> `ReleaseAllInputs`（`cli/session.py:1433`、`:1360-1385`），Bridge 侧应写下
> `bridge released N input(s) after CORE_REQUEST (EXPLICIT)`（`bridge-1201/.../BridgeIpcWorker.java:233-237` +
> `:825-840`，1.21.4 root 同两处字节相同）；今天**没有**任何断言收这一形状——`_BRIDGE_RELEASE`
> （`tools/assert_case_evidence.py:161`）不捕获括号里的 reasonCode，所以 `CORE_REQUEST (EXPLICIT)` 与 V1201-040 的
> `CORE_REQUEST (TIMEOUT)` 不可分，本卡必须先加一个 runtime token（带 N>0，因为 `on_wind_down` 是无条件的），
> 再在受控 1.20.1 上真跑封证。**V08 仍未打开**：`STOP_PHASE_EXPLICIT_KEY_RELEASE` 是否从 `tested` 声明划出、
> V07 剩余缺口是否算收口、是否提升 V08 为 `NEXT` 都归主控；HOST/PERSIST 仍 `BLOCKED_DECISION`；本卡不连接用户
> 远程服、不改产品代码、不动 registry。
>
> **上一交接点（2026-09-25，跨版本路线执行中）**：主计划**暂无 `NEXT`**——**`AUTO-PATH-INSTALL-RUN-001`** 已 `DONE`
> （`94cb15b` 登记、提升提交 `298883e`、本提交收卡）。该卡的空 store 自动路径真跑**已做完并封存**：全新 Kin
> `kin-auto-inst-20260925T141055Z` 自己的 `run/artifact-store` 从 `0 files` 起步，由自动入口**自己**装齐（封存
> `run-document.json`：`fetch_set 3639 / installed 3639 / reused 0`，落盘 `3639 files / 738,432,269 bytes`，
> `quarantine`/`.staging` 各 0），并在**同一个 run** 的封存 `bridge-trace.jsonl` 里拿到 `PlayableEstablished`
> （ledger position 15，在 `JoinObserved` 与 `SessionIdentityCompared` 之后；`connection_state=PLAYABLE`、
> `snapshots_admitted=1`；封存 server 日志有 join 14:35:32 / leave 14:36:06）。身份：run `7236c53ef3ef4492ab2a6b18499f6699`、
> bundle `9a732edc057cebe9…`、case `V1201-020`、`case_version e7c3b722…`、attempt 序列 3（supersedes `ece5d0cb…`）、
> 12 件工件、`result PASS`。四读一致（`evidence verify` `verified:true/violations:[]`、`rejudge` `agrees`、
> 两个 `replay` 同投 19 条事件到 `STOPPED`、`report_promotion` 那一行 `re_judged: AGREES` +
> `from_repository_build: true`），三条非空转反证各红在其命名理由上（两条 `exit 2 unjudged` 的 case_version 漂移、
> 一条 `assert_case_evidence` 的 `stayed_observe_only:JOINED_A_WORLD`，同形状 positive control `exit 0`）。
> **门禁与边界**：`cli/auto_session.py` 的判据与顺序、runner 等待语义、产品代码、fixture、`manifest.sha256`、
> registry 全部一字未改（`status`、九条 `gaps`、`capabilities`、三组 digest 原样；不换 V1201-020 那条引用的理由记在
> 该卡 `completion_readings_auto_path` 第 6 格）。两条 `stop_conditions` 都没触发。V07 `not_tested_v07` 的头两格由
> `not_tested_v07_correction_2026-09-25` 更正为真跑证据，其余格未动。**V07 剩余缺口是否算收口、是否提升 V08 为
> `NEXT` 由主控决定**，本卡未代为登记，也未连接用户的远程测试服；HOST/PERSIST、在线认证仍 `BLOCKED_DECISION`。
> 失败材料保留：`.tmp/auto-inst-attempt1.log`（第一次跑到过 `PlayableEstablished` 但取文档方式错、未及封存，
> 第二跑另起新 Kin 而没有复用那个已装满的 store）。卷内遗留：两个 auto-inst Kin 各自的 738 MB store 未清理（属卷级运维）。
>
> **上一交接点（2026-09-25，本卡领取时的准备现场）**：主计划当时唯一 `NEXT` 是 **`AUTO-PATH-INSTALL-RUN-001`**
> （`94cb15b` 登记、提升提交 `298883e`）。它当时**尚未真跑**，卡里只有领取后的 `preparation_readings_auto_path`
> （`c14acff`、`825a511`），全是实测：自动路径的 store 根是 per-Kin（`cli/auto_session.py:331`），所以"空 store"
> 只指**新 Kin 自己的 `run/artifact-store` 为空**；该声称必须绕开 `test-orchestrator/runner/domain.sh:594-616`
> 对加入者执行的 host store `cp -a`，否则开局即满、只会得到 `installed 0 / reused 数千` 的假证据；容器内出站可达
> （`piston-data.minecraft.us` 200 / 4848 ms，`resources.download.minecraft.net` 解析到 `150.171.110.138` 且根路径
> 404、`launchermeta.mojang.com` 404），停止条件里"URL 不可达"那一支当前没触发；从头装齐的量级实测为
> **4121 个 blob / 523,911,981 字节**（`/data/kin/kin-02/run/artifact-store`），因此这一跑应按**后台长跑**准备而不是
> 交互式一次性命令。另两条必须守住的现场事实：`kin-01` 带 207 条陈旧进程 marker，本跑要在它之外的新 Kin 名上起，
> 并把该新 Kin 会话目录与 marker 的清理放进**同一脚本的 trap**；判定要求是同一 run 内 `installed > 0` 与封存
> `PlayableEstablished` 同时在场，再做四读（`evidence verify` / `rejudge_evidence` / `replay_evidence` /
> `report_promotion`）与至少一次非空转反证；若 harness 在 `PlayableEstablished` 之前结束会话，按卡的 `stop_conditions`
> 停在 `BLOCKED_DECISION` 并保留失败材料，不改 `cli/auto_session.py` 的判据与顺序、不改 runner 等待语义。
> V08 的门没有松动：V07 缺口是否算收口并据此提升 V08 由主控决定，registry 的 `status` 与九条 `gaps` 原样。
> **续跑指令（2026-09-25）**：上述读数只是准备，不是本卡交付。恢复 goal 后应直接进入新 Kin 的受控真跑，
> 不要再次以“脚本尚未写、长跑尚未启动”作为正常收尾；可以把下载/安装放进有日志与清理 `trap` 的后台作业，
> 然后持续检查该作业直至拿到本卡要求的证据或触发明确停止条件。使用正常自动会话，**不要沿用上一张
> `KEY-RELEASE-AT-STOP-001` 的 `MINEKIN_DOMAIN_KILL_CORE=1` 故障注入**。如果环境或 harness 使真跑无法继续，
> 保存失败现场、标明触发的 `stop_conditions`，再交回主控；预检完成本身不构成停机条件。
> **（这条指令已执行：真跑完成并封存，收卡读数见最上面那块。）**
>
> **上一交接点（2026-09-25，跨版本路线执行中）**：主计划当时**暂无 `NEXT`**——`STORE-FAILURE-EVIDENCE-001` 已由
> `cfbb87c` 提升、由 `4be3d55` 收卡，`94cb15b` 把 V07 `not_tested_v07` 的头两格承接为新卡
> `AUTO-PATH-INSTALL-RUN-001`（`QUEUED`），提升它是紧随其后的那一次独立提交。收卡读数：新增
> `tests/unit/test_install_fault_injection.py` 七条真文件系统断言，逐条诱发写失败、store 层 `os.replace` 失败、
> 并发同 digest 三类故障，并对 store 目标路径、`.staging`、`quarantine` 与**重开的 store 实例**实测；
> `ruff check`、`ruff format --check`、`pyright` 干净，`pytest tests/unit` → 2177 passed / 2 skipped（两条既有
> 平台 skip）。实现与安装判据一字未改。仍未测：真·磁盘满（`ENOSPC` 到达的是写调用）、真跨进程并发、
> `SIGKILL` 中途杀 installer 后的 `.staging` 残留清理（属 `OPERATIONS-RETENTION-001`）。本卡是纯单元证据卡，
> 不产出任何 Minecraft 验收证据，因此 CI 不是它的判据来源。V08（入你授权的 1.20.1 测试服）的门没有松动：
> V07 缺口是否算收口由主控决定，registry 的 `status`/`gaps` 原样。

> **上一交接点（2026-09-25，跨版本路线执行中）**：主计划当时唯一 `NEXT` 是 **`STORE-FAILURE-EVIDENCE-001`**
> （提升提交 `cfbb87c`，与工作分支同步、远端 SHA 一致）。上一张 **`KEY-RELEASE-AT-STOP-001`** 已 `DONE`
> （case 登记 `bd8f6b7`、真跑与原子登记 `0fb7158`）：1.20.1 受控离线真服上 `MINEKIN_DOMAIN_CASE=V1201-060
> MINEKIN_DOMAIN_KILL_CORE=1`（默认 5 秒探针，未设 `MINEKIN_DOMAIN_PROBE_SECONDS`）一次真跑封证 PASS——
> run `f71c56f0…`、bundle `90d490ce…`、`case_version 2a1795b7…`、attempt 序列 1、13 件工件，Bridge 自己在
> `client/latest.log` 写下 `bridge released 1 input(s) after IPC_LOST`（`stderr.log` 0 字节），四条断言对
> **拷贝出来的工件**（`.tmp/<run_id>/`，用 `docker cp` 从 `minekin-runner-data` 取出）复判一致，溯源校验器
> `verified: true`、`findings: []`。移动过的摘要只有两行：新 case 的 manifest 行 `11fb2c02…`，与 registry 自身
> `82a54075…` → `69244c32…`（1.20.1 条目**新增**一条 `V1201-060` 证据引用与三个 capability 名）。**产品代码
> 一字未改**——两 root 的失联路径本就写对了，本卡交出的是一件独立工件，不是新实现。
> 仍然没测的：①"玩家主动停止/显式松键"那一格（本卡测的是 Core 被杀后的失联释放）；②`STOP_PHASE_EXPLICIT_KEY_RELEASE`
> 是否从 `tested` 声明里划出，属主控决策，registry 的 `status` 与九条 `gaps` 因此原样保留；③`V1201-040`
> 及其两份证据一字未动（它是 lease 到期那一格，写不进 `IPC_LOST`）。停机边界不变：V08、用户远程服、HOST/PERSIST、
> 在线认证都还没到；`.tmp/` 里的运行记录不是产品进度。

> **上一交接点（2026-09-25，跨版本路线执行中）**：主计划当时唯一 `NEXT` 仍是 **`KEY-RELEASE-AT-STOP-001`**
> （`14d85a0` 提升），领取后**没有停在 `BLOCKED_DECISION`**：第一批读数（该卡 `preparation_readings_key_release`）
> 里更正了一次我自己的初判——草稿曾把 `CRASH-OUTBOX-ALIVE-DISPLAY-001` 读成 `QUEUED`，据
> `docs/p0-validation-evidence-contract.md:265-276` 的"`xvfb-run` EXIT trap 6–7 ms 关 X vs 50 ms tick"判定
> `after IPC_LOST` 在 1.20.1 **按构造打不中**。那份读数是 **2026-09-24 修复之前**的现场：那张 runner 卡早已 `DONE`
> （登记 `94c3af0`、提升 `9a283ac`、交付 `f90abc8`），harness 现在自持 Xvfb、把主 session 搬到 `xvfb-run` 之外，
> 而 `f90abc8` 的验收 ① 正是 1.21.4 `CORE-060` run `7fc0671e…` 真封出的
> `[Render thread/INFO]: bridge released 1 input(s) after IPC_LOST`（`stderr.log` 为空）。
> ⇒ 1.20.1 缺的是**一次尚未做过的"带断连的停止"真跑**（`V1201-040` + `MINEKIN_DOMAIN_KILL_CORE=1`，默认 5 秒探针），
> 不是窗口；两 root 该路径字节相同，也**不需要**把松键搬到失联检测点同步做（那会撞 `VanillaKeySink` 的客户端线程
> 不变量，属改失联策略）。真卷对照读数：1.20.1 的两份 `V1201-040`（`155dcb4a…`、`f4cc67ae…`）只有
> `bridge released 1 input(s) after CORE_REQUEST (TIMEOUT)`——reason 是 Core 的请求，正是本卡不接受的形状。
> （那块写于领取时，当时确实未改产品代码、未移动摘要；收卡读数见上面那块。）

> **更早交接点（2026-09-25，跨版本路线执行中）**：主计划当时唯一 `NEXT` 是 **`KEY-RELEASE-AT-STOP-001`**
> （本提交提升）。上一张 **`BRIDGE-1214-RUNTIME-IDENTITY-001`** 已 `DONE`（实现与重封 `16dbb42`、收卡 `2464901`）：
> 1.21.4 root 现在像 1.20.1 一样从 Fabric 自己的 mod container 读 `minecraft` / `fabricloader` 送进 `Expected`，
> 读不到 container 就失败关闭而非回落常量；随之移动的四组摘要（source tree `a4a53cac…` / jar `0ee2070b…` /
> recipe `e3bfbae8…` / plan `bcc0c10d…`，黄金证明 `3f89c8d4…`）全部由**重跑重封**支撑——被引用的 12 条 case 各在
> 新 build 上四读一致，registry 的 `status`/`capabilities`/`gaps` 一字未动，换代后 `verify_tested_provenance.py`
> 与 `bundle install --dry-run` 仍对真件通过。再上一张 `TESTED-PROVENANCE-VERIFY-001` 已 `DONE`（实现 `c93cfa4`、
> 收卡 `49d6d01`），更早 `VERSION-BRIDGE-IDENTITY-001`（实现 `801f9ba`、CI 门修复 `391cc2b`、收卡
> `bebcf5d`、CI 补记 `f00daeb`）。**本卡要做的事**：让 1.20.1 在**停止/断连**阶段由 Bridge 自己产出"IPC 丢失后
> 释放了 N 个输入"的独立工件并由 case 断言核对，使"松键真的送达"不再依赖 Core 侧记账与服务端推断。其后是
> `STORE-FAILURE-EVIDENCE-001`；这两卡与 V07 的
> `not_tested_v07` 缺口收口前**不得提升 V08、不得连接用户远程服**。也**不是**下文 ADMIT-070 起步卡，
> 更不是 V01–V07（均已 `DONE`；V07 交付 `5e53429`+`b0d08b6`、收卡 `17e81ea`+`96fb520`）。
> **审查卡的四条硬事实**（决定 V08 为什么还不能领）：① ~~1.20.1 的 `tested` 没有被任何代码对真实封存构件校验过~~
> ——**已由 `c93cfa4` 关闭为"可核对"**：`tools/verify_tested_provenance.py` 独立重算四层摘要并逐条比对引用 bundle
> 真件，缺件/不符即按类别拒绝。但它**不在** `resolve()` 或安装门的调用链上（本卡禁改生产门判据），"把核对变成
> 启动前置门"仍是一次产品决策；② V06 安装门里 recipe/plan 两层是真算，**bridge 那层仍是 `recipe.py` 的常量搬运**
> （本卡不动它），变化在于审计侧现在真哈希 jar 与 source tree——"读到了常量"不再被当成"已校验"；
> ③ ~~两个 Bridge root 的 hello 都写死 `1.21.4`/`0.16.9`~~ ——**已由 `801f9ba` 修掉一半**：Core 现在按**本次会话**
> 的 plan 校验两个版本字段，`bridge-1201` 改为声明它真实运行的 `1.20.1`/`0.19.5`；~~1.21.4 root 仍写死常量~~
> ——**已由 `16dbb42` 关闭另一半**：1.21.4 root 同样从 mod container 读，读不到即失败关闭，该事实两侧都不再成立；
> ④ 1.20.1 **停止阶段显式松键无独立工件**（只有 Core 的 `INPUT_RELEASED(TIMEOUT)` 记账，registry 自己也标了
> `STOP_PHASE_EXPLICIT_KEY_RELEASE`）。
> 因此 `tested` **可用于本地受控运行**（V07 就这么用的），**不可当作远程入服的充分证据**。
> 同批更正：V06 收卡里"三类故障反例沿用既有 store 契约覆盖"不实——写失败注入与 store 层 `os.replace` 失败
> 都没有测试，`artifacts.py:176-177` 的同 digest 并发分支无测试；登记为 `STORE-FAILURE-EVIDENCE-001` 补证。
> **`801f9ba` 交付了什么**：`BridgeSession` 增必填 `minecraft_version`/`fabric_loader_version`（形状门 `VERSION_TEXT`
> 守住"NUL 拼接即证明上下文"），`_validate_bridge_hello`/`_bridge_proof` 读会话字段而非字面量；bootstrap 从已审
> plan 取版本、钉不住即拒；`bridge-1201` 新增 `ClientRuntimeIdentity`（从 Fabric mod container 读，读不到即失败关闭）
> 并把它送进 `Expected`/`HandshakeGate`。1.20.1 candidate 重建为 jar `e50d61c209be…` / 1,310,604（Windows 两次 +
> Linux 容器冷构建三次同一摘要），`V1201-010/020/040/070` 与 1.21.4 的 `CORE-010` 在受控 runner 上各重跑一次、
> 逐个四读一致，registry 引用按实测换代（`status`/`capabilities`/`gaps` 一字未动）。**1.21.4 的
> `faeec4a9…` / `bb456060…` / `9e0e0ccc…` 未动**，其黄金证明 `dd1e49ce…` 仍是正例、任一版本字段动一格即被同一
> seam 拒。**（2026-09-25 `16dbb42` 更正：那三件摘要与其黄金证明已经随 1.21.4 root 改为运行时读取而换代为
> `0ee2070b…` / `e3bfbae8…` / `bcc0c10d…` 与 `3f89c8d4…`，1.21.4 的 12 条引用随之在新 build 上重跑重封；上面这句
> 写的是 `801f9ba` 当时的现场。旧→新对账见主计划 `moved_digests_identity`。）**
> 逐格账与移动的摘要清单见主计划 `moved_digests_hello`…`next_after_done`。
> **CI 读数**：`801f9ba` 的 run #526/#527 红在 `bridge-static` 的 dependency-free 检查（已由 `391cc2b` 修好），
> `391cc2b` 的 #528/#529 与收卡提交 `bebcf5d` 的 #530/#531 三 job 全 `success`；取自 Actions REST 的 step 级结果，
> 浏览器截图工具超时未能肉眼看页（见主计划 `ci_reading_hello`）。
> **V07 交付了什么**：`session start --auto-bundle <被审 registry> --server-profile <目标> --max-bytes N`
> ——一条 fail-closed 自动路径（**新增** `cli/auto_session.py`，`bootstrap.py` 只加分派段，`cli/parser.py` 加入口
> 形状），顺序为 两次观测必须一致 → 三处版本事实核对 → `resolve()` → **摘要门先于抓取** → `stop_recorded_clients`
> 停旧并取证 → 以新 `session_id` + `generation=1` 起新。显式路径 `cli/session.py` 字节未变；markers 从不清除，
> 旧进程"证不来"就停在 `PROCESS`，接管/强杀仍属 `PROCESS-RECOVERY-001`。**Bridge 握手常量的修复不属 V07**（属
> `VERSION-BRIDGE-IDENTITY-001`）；1.20.1 客户端当时能过握手只是因为 `bridge-1201` 的 root 声明了 1.21.4
> ——这一句在 `801f9ba` 之后不再成立，见上面最新交接点。
> **V07 的真实读数**（受控 runner，两次 1.21.4 → 1.20.1 **顺序**切换）：目标侧探测 `OBSERVED protocol 763 /
> version_text "1.20.1"`，旧侧 `NO_RESPONSE "the endpoint closed before any frame"`；自动路径自报
> `bundle_id 1.20.1-linux-x86_64-offline-java21`、`launch_plan_digest ac403160…`、
> `fetch_set 3639 / installed 0 / reused 3639`、`status ready`、`stopped [328]`，旧会话以 `SessionInterrupted` 收，
> 新会话 `JoinObserved`/`PlayableEstablished` 各 1、两服日志各 1 条 `Kin joined the game`、两跑合计 314 次快照
> 0 次并发。本地门禁：2432 passed / 2 skipped，ruff / format / pyright / boundaries 全绿。
> **V07 没有证明的事**：自动路径的**下载分支**只有单元证据（两跑均 `reused 3639 / installed 0`）；自动起的新会话
> 在自己的 `PlayableEstablished` 之前被 SIGINT 结束；跨 Kin 缓存共享、残留 marker 清理、进程接管未动；1.20.1 的
> `BridgeHello` 仍自报 1.21.4；用户真实远程服**未访问**。
> 跑切换前还要知道两条环境事实：`kin-01` 运行根带 **207** 个残留 `process.json` marker（自动切换须用 `init
> --kin-id` 新建的 Kin，`artifact-store`/`bundle` 以 `cp -al` 硬链接复用），harness 写的 `enable-status=false` 会让
> 产品探测恒得 `NO_RESPONSE`（沿用 V02/V05 先例：启动前把 loopback 那一行改成 `true`，不改 harness 也不改探测判据）。
> **本机 `git push` 的坑**：仓库配置是 `credential.helper=helper-selector` 且 `credential.helperselector.selected`
> 为空，`git push` 会**一声不响地挂死**（`git ls-remote` 走匿名读路径照样成功，所以它不能证明推送凭据可用）。
> 能走通的写法是 `GIT_TERMINAL_PROMPT=0 git -c credential.helper= -c credential.helper=wincred push origin <ref>`。
> **CI 已在浏览器里逐 job 读过**：`b0d08b6` 的 run **#515** 与收卡提交 `17e81ea` 的 run **#517** 均 `Success`
> （`python` 2m39s / 2m24s，步骤含 `ruff check`、`ruff format --check`、`pyright`、`pytest`、`check_boundaries`、
> `check_case_assertions`、`verify_fixture_digests`、`check_workflow_pins`、wheel 构建与 `check_wheel_boundary`、
> `minekin --help`），注解只有平台公告。**CI 不是 Minecraft 验收证据**，真实运行只在受控 runner 里。
> **V06 交付了什么**：产品侧第一个安装入口
> `minekin bundle install --registry ... --bundle-id ... --max-bytes N [--store ...] [--dry-run] [--jobs N] [--quiet]`，
> 它把"先核对被审摘要，再装"两层显式组合起来——`require_reviewed_plan` 按 `tested` 状态 → recipe 摘要 →
> launch plan 摘要 → bridge 摘要四步拒绝，`reviewed_entry` 拒绝猜近邻 id。**没有**新增 ready 标记、
> **没有**改 store 根、**没有**重写下载器（暂存+`os.replace`+隔离、请求前预算拒绝、逐构件 `verify` 都是既有的）。
> 清单的 `bridge_digest` 是 **bridge jar** 的 sha256（plan `fixed_mods` 里那条），不是
> `bridge_source_sha256`；bridge jar 由 workspace 提供、**不经 fetch**，所以 bridge/asset 的放置仍属 V07。
> 真实读数（受控 runner，收卡时重量过；**两套**各自受审组合各从一个空 store 装齐）：1.20.1 的
> **3,639 个构件 / 738,432,269 字节**，中途 SIGKILL 在 384 件、续跑报 `installed 3255 / reused 384 /
> failed []`；1.21.4 的 **4,120 / 523,788,383 字节**一趟未中断（`installed 4120 / reused 0 / failed []`）。
> 两套随后各自 `require_launchable` + `require_store_complete` **通过**（`missing 0`、`quarantine 0`；
> store `du` 分别 727M / 525M），满 store 以 `--max-bytes 1` 分别全量复用 3,639 / 4,120 件、exit 0；
> 预算不足与缺 `--max-bytes` 分别以 exit 11 / exit 2 拒。
> **V06 没有证明的事**：安装未接进 `session start` 自动路径（V07）、没起过任何 Minecraft 进程、
> 跨进程续抓只在 1.20.1 上有读数、
> 磁盘满的写失败分支/原子 `rename` 失败/并发同 digest 三类未主动诱发（既有 store 契约覆盖）、
> `.staging` 里 5 个残留事务无 GC API、每 Kin 一份副本的代价仍成立、`RUNNER_JDK_17_UNSEALED` 不变。
> **CI 已按规矩在浏览器里读过**：`main` run **#501**（`06acbf1`）三 job 全绿，`python` 2m59s 逐步骤读过
> （`ruff check`/`ruff format --check`/`pyright`/`pytest 2m6s`/`check_boundaries`），`protocol` 9s、
> `bridge-static` 12s；收卡提交 `d7a91f9` 的 run **#503** 读到 `Success` 2m36s（`python` 2m33s、
> `protocol` 10s、`bridge-static` 13s）；文档提交 `f15f6b7` 的 run **#499** 在列表页读到
> `completed successfully`；
> 注解全是 GitHub 平台公告（Node 20 弃用、runner-images #14748），不是本仓库红灯。**CI 不是 Minecraft
> 验收证据**——真实运行只发生在受控 runner 里。
> 以下 ADMIT-070 起步任务和阶段说明是
> 当时的历史执行路线，**不是当前领取任务的授权**。七个已排定的 P0 campaign 场景
> 已走完（`scenario_progress 7/7`），但 [`development-execution-plan.md`](development-execution-plan.md)
> 的晋级总账仍把整体判为 `BLOCKED/INCOMPLETE`：74 个 required case 中 31 个尚未登记，
> 且已有证据中有旧 build 与版本不匹配项。用户随后明确把跨版本路线排为优先项；
> 设计卡 `VERSION-AUTO-DESIGN-001` 已交付
> [跨版本连续执行计划](version-auto-to-server-control-plan.md)。
> Qoder 应按下文恢复步骤核对 Git、机器报告和
> 封存证据；不得从本文件的旧阶段标题或历史 TODO 自行挑选其它 `NEXT`，也不得
> 把“七个场景完成”写成 P0 晋级完成。最新读数与待决项以主执行计划顶部及
> `P0-PROMOTION-LEDGER-001` 为准。

本文件是主控对临时执行者的**连续执行手册**，不替代
[`development-execution-plan.md`](development-execution-plan.md) 的唯一 `NEXT`、
[`p0-remote-admission-contract.md`](p0-remote-admission-contract.md) 的判据或用户指令。
以下 SHA 和数字是 **2026-09-24 的审查快照，不是运行时真相**：审查固定点
`d3a4064d53bf3cc79ed4b2540c41c697a17049a2`，当时已提交实现 HEAD
`18219c6ad5db7a4af106bc1e95675aeac7ca14d1`，本交接提交前 HEAD
`77b345f7d872ade67d703e6e0f414fbb216f7bd6`。执行者每次恢复工作必须先读
当前 Git、case inventory、计划状态和证据 registry；不得把本页快照当成最新状态。
当时尚未提交的 `ADMIT-070-REFUSAL-INJECTION-001` 改动属于进行中，不是 DONE。

## 主控审查结论

- 固定点之后已提交的 `ADMIT-040`、`ADMIT-060` 两场景按 campaign 顺序推进；
  未发现已提交代码明显越过专项设计。计划记录两场景各有 sealed PASS/AGREES，
  但本次审查没有把当前脏工作树的测试结果当成这两个提交的独立复验。
- 当前工作树的注入实现位于任务卡允许路径内，但至少有两处假阳性风险：
  `domain.sh` 把显式 `0`/`false` 当成需等待拒绝的场景；Bridge 在
  `ClientSnapshot.collect` 可能返回 `null` 之前就写“已上报非权威快照”，runner
  又以该日志作为成功条件。只有 Core 真正记录 `NOT_AUTHORITATIVE` 拒绝，才能
  证明注入达到了验收边界。
- 注入的可信归因尚未落入同一 run 可封存的 `fault-injection.json`；现有
  `fault_injection.py` 是进程故障的严格记录格式，不得把“要求 Bridge 改字段”
  伪装成 `SIGKILL` 或进程消失。先验证能否诚实扩展其记录/读取形状；不能则
  按任务卡 stop condition 停止，向主控报告所需的最小契约调整。
- 本次本地定向检查是 **33 failed / 365 passed**。其中 32 个失败共因是未提交
  Bridge 源码使 recipe source digest 与已封 pin 不匹配；另 1 个失败是
  `run.sh` 没转发 `MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT`。这是进行中状态的门禁红灯，
  不可解释成已提交的 ADMIT-040/060 实现回归，也不能带红提交。
- 审查时远端 `codex/core-state-transition` 为 `18219c6`、远端 `main` 为
  `25a9868`，两者差 7 个已提交阶段；主控随后把两端 fast-forward 到
  `77b345f` 并核对远端 SHA。这段是已修复的流程故障，不是今日还应重复推送的指令。

## 历史起步卡（已完成）：ADMIT-070-REFUSAL-INJECTION-001

下列步骤记录当时 Qoder 只处理该卡 `allowed_paths` 的起步约束，**现已执行完毕，
不得据此重新领取 ADMIT-070**。当时不允许同时做 `ADMIT-070-CASE-001`、
HOST/PERSIST、CI 或认证方式扩展。保留其他人的改动，不要 reset、stash、覆盖或
改写既有 sealed bundle；这些工作树与证据保护规则仍然有效。

1. **收紧开关语义。** `unset`、`0`、`false` 均保持原有首快照流程，且 runner
   不进入拒绝等待；只有 `1`/`true` 进入注入路径。`run.sh` 显式转发该 knob，
   契约测试覆盖正、反和非法值；不要靠非空字符串判断布尔值。
2. **消除“日志即成功”的假阳性。** Bridge 只有在快照确已构造并向 IPC 上报后
   才能记录“已上报”；如果 `collect` 返回 `null` 或发送失败，不可打印成功文案。
   runner 的最终成功判据是本 run 的 Core 文档出现
   `snapshot_rejections: [NOT_AUTHORITATIVE]` 且 `snapshots_admitted=0`，同时账本
   有 `JoinObserved`、无 `PlayableEstablished`/`InputLeaseGranted`。客户端日志只能
   作为注入动作的旁证，不代替 Core 的拒绝结果。日志查询必须定位本次 session
   的 overlay，不能在所有 Kin 的新日志里取 `head -1` 猜目标。
3. **把注入请求与实际效果分开记录。** 检查现有 `fault-injection.json` 的 schema、
   reader、sealer 一次读取规则；为“请求 Bridge 非权威上报”建立可验证的记录，
   包含 case、kin/run/session/generation 归因、请求值、是否执行、可信观察来源，
   不冒用进程故障的 target/signal/confirmation 字段。测试缺记录、错 run、
   `0/false` 却宣称注入、只有请求而无 Core 拒绝等反例。若必须突破当前卡的
   `forbidden_paths` 或无法诚实承载，立即停止并报告，不自行扩范围。
4. **先过静态和本地门禁，再做真实诊断。** Java 定向测试与 JDK 21
   `./gradlew check --rerun-tasks`；`uv run --frozen pytest -q`、Ruff check/format、
   Pyright、boundaries、case assertions、fixture digests、workflow pins、
   `git diff --check`。Bridge 构建后只按任务卡续期 recipe/JAR/source digest、
   CORE-001 输入 digest 与 fixture manifest；所有变更列明旧/新摘要。当前
   source digest 红灯不得靠放宽校验消除。
5. **两条受控 Docker 诊断。** 不设注入开关的离线服 run 必须 JOIN、
   `PLAYABLE`、至少 1 份快照准入；设 `1` 的 run 必须 JOIN 后由 Core 记录
   `NOT_AUTHORITATIVE`、0 份准入、无 PLAYABLE/lease，且记录的注入事实能被
   同一 run 的封存通道读回。记录 run ID、generation、服务端目录、相关 ledger
   行、run document 字段和退出语义。此卡仅作诊断，**不封 ADMIT-070 PASS bundle**。
6. **交付与推送。** 提交前列出完整 diff 与未验证项；commit message 写明
   Constraint、Confidence、Scope-risk、Not-tested。每个完成的实现环节立即推送
   当前分支与 `main`，核对两个远端 SHA。状态流转遵守下文“条件授权”：
   没有完整门禁与真实诊断，不得改 `current_next`、标 DONE 或打开下一卡。

## 连续推进的授权边界

用户希望同一份文档支持多阶段连续开发，故本节是对执行计划“只有主控改状态”的
**窄范围、条件式委托**。主控预授权 Qoder 在 `REAL-P0-CAMPAIGN-001` 已冻结的
`order` 内机械推进；不授权更改项目目标、补造证据、解决 `BLOCKED_DECISION`，
也不授权把完成一个 case 当成整个 P0 完成。若本页与专项契约冲突，专项契约优先。

一阶段到下一阶段，必须同时具备：

1. 本阶段允许路径、禁止路径、non-goals 和反例在实现前写成独立 task card；
   已有卡优先，不重造一张同名卡。新卡先 `QUEUED`，不得直接 `NEXT`。
2. 该卡要求的本地门禁**全部绿**；真实 Minecraft/故障/时序要求有本 build
   的受控运行，且读数能精确归属同一 run/session/generation。平台跳过项需注明。
3. 需要正式 case 时，有最新 attempt 的 sealed bundle；verify、rejudge、
   适用 replay、promotion 四个读者一致。失败 bundle 原样保留，重试领新序号。
4. 对实现 diff 做两轴自审：逐项对应专项契约；逐项核对允许路径、依赖方向、
   代码重复与测试假阳性。记录发现与修复，不把“测试通过”当作设计审查。
5. 每个可逆阶段独立 commit，立即 push 到当前分支和 `main`，`git ls-remote`
   核对两个远端 SHA 与本地 HEAD 一致；push 失败不能标 DONE。
6. 在执行计划记 `completion_commit`、原始门禁摘要、run/bundle/attempt/digest、
   已验证与未验证项后，才把本卡 `NEXT → DONE`。再把顺序表的下一张已登记
   `QUEUED → NEXT`，更新 `current_next`；不得同时有两个 `NEXT`。

这六项允许 Qoder **不必每完成一小卡就回来问主控**。如果出现专项契约没有
决定的产品策略、相互矛盾的 case 身份、必须改 `forbidden_paths`、证据来源不足、
需要用户 EULA/账号/硬件/服务授权、或真实运行连续三次重现同一个不可消除的外部阻断，
只记录 `BLOCKED_*`、尝试过的安全替代与待决问题，然后停止该分支；不要为维持
进度而自行换目标。能并行推进的**别的已授权本地诊断**可继续，但不能跨过
campaign 的场景顺序宣布后面的封证完成。

## 每次启动与上下文丢失后的恢复步骤

先把当前执行环境当成未知，而不是相信这份交接在写下后仍然新鲜。

1. `git status --short`、`git log -8 --oneline --decorate`、
   `git ls-remote origin refs/heads/main refs/heads/codex/core-state-transition`；
   工作树已有改动归原作者，先判断与当前卡重叠，不 reset/stash/覆盖。
2. 读本页、执行计划的 `current_next` 与该 task card、专项契约原文、
   `tests/fixtures/cases/` 中相关 fixture，以及 `docs/development-todo.md`
   的最新实测记录。卡的 `baseline_sha` 是登记时基线，不必等于当前 HEAD。
3. `uv run --frozen python tools/report_cases.py`，从 JSON 的 `requirements`
   与 `totals` 读当前缺口；本页快照是 72 required / 38 present / 34 missing、
   38 cases / 145 assertion references（2026-09-24）。`not-gating` 与
   `present_wanting_a_run` 不能偷换成 satisfied。
4. 对当前数据根运行 `tools/report_promotion.py --help` 后按 CLI 指定 data root
   读取最新 attempt、case version、build 诊断与 blocking cases。必须区分
   registry 的最新失败和旧 PASS；不能按 mtime、目录名挑“看上去最新”的 bundle。
5. 先跑最窄的相关测试确认红灯与代码状态，再动产品代码；改 Bridge 时 source
   digest 红灯是 pin 尚未续期的症状，不能用跳过 recipe 校验治它。
6. 在 `docs/development-todo.md` 写一条恢复记录：HEAD、远端 SHA、工作树归属、
   机器 inventory、当前 case/attempt、下一步及 stop condition。禁止仅凭旧 `[x]`
   宣告完成。

## 长程路线：一阶段通过才进入下一阶段

以下是**执行序列**而非一次性改动清单。各段的“设计冻结 → 实现 → 真实诊断/封证
→ 四读复核 → commit/push → 状态流转”是独立可逆阶段。已在仓库存在的 case 与
工具不重复实现；先确认能否复用。对尚未冻结的任务，下面写的是如何取得
**可证明的下一步**，不是允许从表格里凭空补一个 PASS。

### 阶段 A：ADMIT-070 首快照拒绝注入（当前 `NEXT`）

入口是当前脏工作树与执行计划 `ADMIT-070-REFUSAL-INJECTION-001`。按前文六项
完成开关/归因/门禁、正反 Docker 诊断。特别检查默认离线运行仍能 PLAYABLE；
注入运行必须 JOIN、Core 明确拒绝 `NOT_AUTHORITATIVE`、0 准入、无 lease；
一条客户端日志不构成拒绝事实。若 `fault-injection.json` 现有严格结构无法
诚实容纳非进程故障，先写一页最小方案与失败样例，按卡的 stop condition
停下，不绕过校验。此阶段不封 ADMIT-070 case。

### 阶段 B：ADMIT-070 正式 case 与受控证据

入口是阶段 A 的两个真实诊断都达到其接受条件、实现 commit/push 完成。
先登记 `ADMIT-070-CASE-001` 为 `QUEUED`，从专项契约“ADMIT-070 的可复判
证据边界”五项逐条列出 `可信来源 → sealed artifact → 判官字段 → 反例`，
再按条件授权提升为唯一 `NEXT`。现有
`tests/fixtures/cases/admit-070.json` 的五条是 **pytest 域内断言**；
不得因为名称相同就把它们当真实运行判据。检查 case schema 与 registry 后，
给真实材料新增或映射断言，更新 assertion digests、fixture manifest，
不削弱原有域内测试。

正式 bundle 至少要同 run 核对：Bridge-filtered JOIN；Core run document 的
`NOT_AUTHORITATIVE`（非超时推断）与 0 准入；账本无 PLAYABLE、lease；generation
确实关闭；注入请求及结果来自可复判测试域记录。反例逐个故意造成 FAIL：
缺 JOIN、只有日志没有 Core 拒绝、错误 run/代、没有注入归因、已有 PLAYABLE
或 lease、快照其实被准入、generation 未关闭。判官不得用“45 秒没 PLAYABLE”
代替拒绝。封正式 run 前先在当前 build 上重复一次正向与注入诊断；正式 seal
分配新 attempt，并保留诊断和失败 bundle。verify/rejudge/replay/promotion
一致后记录完整 run ID、bundle digest、attempt、case version 和读数，再提交
与推送。若封存通道缺少注入工件，此阶段 FAIL，不凭 Bridge 日志补判。

### 阶段 C：OFF-A / OFF-B 身份候选与受控离线入服

入口是 ADMIT-070 正式 case 可复判。重新阅读
`p0-offline-session-compatibility-contract.md` 的 OFFLINE-010/020/030/040/050
和 `p0-remote-admission-contract.md` 的身份边界；确认 CLI
`--identity-candidate` 的当前可选值由同一候选清单导出。先做**证据设计卡**，
把 OFF-A、OFF-B 各自的真实 Session AccountType、Bridge 身份材料、argv
边界、服务端观察身份与 JOIN/首快照写成两列比较，并说明哪些必须由两次独立
run 证明。OFFLINE-030 文句是“A/B 分别加入”，而一个 run 只会启动一个候选；
不得让一份 bundle 冒充两次运行。优先沿用 CORE-060 的独立子 case 先例；
如果这要求改 required inventory 的既有 case ID，先冻结明确的拆分规则、
迁移/兼容语义与假阳性测试，再改 registry。此处允许 Qoder按已冻结的拆分
先例做**证据结构决策**，不允许改变身份算法或选择一个“比较好”的候选作为
唯一支持方式。

两次受控离线服务器运行只改变 `--identity-candidate`，其它 bundle、Profile、
服务端设置、用户名策略尽量固定；记录候选 id、实际 argv 摘要、Bridge 的
Session 观察、服务端 JOIN 与 UUID、首快照及最终分类。对齐比较 `id128`/
canonical UUID、空 clientId/xuid 的 option/value 边界。只有空值产生可归因
真实失败时，才按 OFFLINE-050 的原文跑非空 sentinel 对照；不得无限试值。
每次 run 独立 seal；需要跨 run 比较的判据使用被封存的两份材料或两个子 case，
不能让判官读取活目录里的另一份 run。完成相关 case 后四读复核并提交推送。
若 OFF-B 不可启动，保留真实失败并分类，不悄悄回退 OFF-A 后说“两者都过”。

### 阶段 D：crash / outbox / restart 窗口

入口是 OFF-A/B 证据闭合，或阶段 C 明确证明某个候选被设计性拒绝且该失败
有独立封证、不影响本阶段测试前提。先核对现有 `CORE-060` 的 runtime/server/
client 三个进程边界与 `CORE-090` 的恢复 bundle，避免重复跑同一窗口；
`Launcher` 在本仓库不是第四个独立进程，不造虚假的故障角色。按
`p0-validation-evidence-contract.md` 与已有 fixture 列出仍缺的**具体窗口**：
正常退出、已写 effect intent 但未 settle、客户端/服务端强杀、重启重验、
未决 outbox。每一种不能在同一 run 发生的故障要独立 case/attempt。

真实故障只用现有受控 runner 对**本 run 已识别**的 pid/start-time/argv
执行，严格使用 `fault-injection.json` 的角色与确认强度；helper 非父进程
不能宣称 `WAIT_STATUS`。保留旧 PASS 与新 FAIL，不在原 bundle 上修补。
每个窗口核对 Core ledger、Bridge input release、服务端日志和恢复后的新
generation；“进程消失”本身不证明 lease 已松开，也不证明 world 重新观察。
pending outbox 若只能用真 SQLite + 故障注入单测构造，应如实标为本地证据，
不伪装成真实 Minecraft run。新增产品恢复策略如果触及计划中
`PROCESS-RECOVERY-001` 的自动接管/终止选择，立即停下请求产品决策。

2026-09-24 实测状态（`CRASH-OUTBOX-EVIDENCE-DESIGN-001` 的冻结，读数在
`p0-validation-evidence-contract.md` 那份「crash / outbox / restart 窗口的可封边界」表里）：本节要的
「仍缺哪些具体窗口」已经逐行量过——五个窗口（正常退出、client 强杀、server 强杀、runtime 强杀、
重启重验）**都有 case id、断言与 runner 开关**，一个都不缺定义；缺的是当前 reviewed build 上的
attempt，那五份旧 bundle 对今天的 `case_version` 全读作 `UNJUDGED`，按上面那句「保留旧 PASS」原样留着。
「已写 effect intent 但未 settle」这一半**按构造打不中**：`domain.sh` 的 kill 块要等到 Kin 真的走过
（不同横坐标数 ≥2）才动手，而那段区间在 Core 自己的 `session start` 代码里，所以它落在上面那句
「如实标为本地证据」里，不在真实运行里——本阶段**不**为封证在产品代码插停顿。执行入口是
`CRASH-OUTBOX-RESEAL-001`。

### 阶段 E：tick / render 与 L6 soak

入口是故障窗口的结论已封证或阻断已显式记录。先复查 `CORE-METRICS-001`
和 `CORE-100` 的现有真实 soak；不要为了“多一份报告”重复 600 秒运行。
若本 build 的 Bridge/采样路径改变，重新跑受控 Linux 软件渲染档；按
`CORE-100` 的三个已登记断言封 `soak-samples.txt`、`soak-summary.json`、
client/server 两 JVM 的完整时序，记录要求时长、间隔、样本数、提前终止和
失败样本。`tools/report_soak.py` 只从**已验摘要的封存 bundle**算 min/first/
last/P50/P95/P99/max RSS 与线程峰值，标明 nearest-rank；不能从活文件算。
tick/render callback 的预算读数应注明窗口、采样覆盖与缺口。

契约尚无 GPU 档、FPS/TPS/GC/队列深度的可信来源和性能阈值；只报告
“该轮测量完整/不完整”及实测值，不宣称“性能合格”或自行设阈值。
若用户没有 GPU 运行环境，记录未测并继续可完成的软件渲染部分。

### 阶段 F：CORE / OFFLINE / ADMIT 证据与晋级总账

入口是前面各阶段的 case 与 run ledger 已登记。重新跑
`tools/report_cases.py` 与 `tools/report_promotion.py`，按 required case、
`mandatory`、`validation_class`、case version、最新 attempt 列一张总账。
对这轮新封的每份 bundle 单独跑 `minekin evidence verify`、
`tools/rejudge_evidence.py`、适用的 `minekin replay`/`tools/replay_evidence.py`；
把 `AGREES`/`UNJUDGED`/`DISAGREES` 区分清楚。`from_repository_build` 是
诊断值，不是 promotion 门禁；若它为 false，不能用旧 build 的 PASS
冒充“当前 build 已复测”，要按最新 attempt 规则重跑相关 case。

输出必须明确：每个 gate 的 present/missing、最新 attempt、PASS/FAIL/INCOMPLETE、
版本与摘要、当前 build 关系、阻断原因；同时列出尚未定义/未封的
`OFFLINE-060/070/080/090/100`、`ADMIT-010/020/030/050/090/120` 等缺口，
只以机器 inventory 为准，不凭本页例举的编号做计数。如果 72 required 中
仍有缺失或 promotion 阻断，`REAL-P0-CAMPAIGN-001` 只能记成**已完成若干场景、
总体仍 BLOCKED/INCOMPLETE**，不能因为七个场景都运行了就标 DONE。

### 阶段 G：campaign 之后的有界自主工作

若 F 显示仍有 P0 CORE/OFFLINE/ADMIT 的、专项契约已经定义且无需产品新决策的
缺口，Qoder 可以按同一模板继续逐 case 做“证据设计卡 → 可观测事实 →
反例 → 本地/真实验证 → seal → 四读 → commit/push”，仍保持一个 `NEXT`。
优先处理 `runtime-required` 且阻挡 W30/W40/W50/p0-core 的项目；已经
`local-only` 或 `not-gating` 的条目不能伪装成同一种进度。若一个编号混合
互斥场景，先按 CORE-060 先例拆 case，不能用任何一个 PASS 代表全组。

`HOST-ADMISSION-DESIGN-001`、`OPERATIONS-RETENTION-001`、
`PROCESS-RECOVERY-001` 仍为 `BLOCKED_DECISION`；HOST/W80+ 为 `DEFERRED`；
PERSIST 的 case ID 未冻结。Qoder 可以写“待决问题与备选/代价”文档、运行
只读探针，但**不可替用户决定**宿主世界 capsule 的可信来源、自动清理保留期、
自动接管/终止残留进程，也不可为 PERSIST 猜编号。若可执行的 P0 工作已经
耗尽，交付一份阻断清单和现有 demo/门禁状态，停止在明确边界；这是诚实的
阶段终点，不是擅自宣布整个项目完成。

### 阶段 H：受管理客户端跨版本路线（已排队，不能误作当前功能）

用户确认另有一台 **Minecraft 1.20.1、离线认证测试服**，并明确重申产品目标
是自动探测服务器、选择并按需准备合适的受管理客户端版本。当前唯一受审
运行包仍是 1.21.4；`ServerProfile` 目前只接受 loopback/1.21.4，代码没有
接进会话启动路径的 Server Probe、Version Resolver、多版本 Bundle Registry。
因此不能把那台服务器用于当前 ADMIT-070 的 1.21.4 JOIN/快照验收，也不能
让用户自己下载 1.20.1 客户端来掩盖产品缺口。测试端点由用户在私有运行
配置中提供，**不要把公网 IP/端口提交到公开仓库**。

此项先前以 `VERSION-AUTO-DESIGN-001`（`QUEUED`）登记；用户在七场景总账后
明确把它提升并完成设计。详细的 V01–V10 卡在
[跨版本连续执行计划](version-auto-to-server-control-plan.md)；下列五项只保留为原始路线摘要，
不得越过主计划唯一 `NEXT` 提前实施：

1. **Probe**：规范 host/port，按策略解析 SRV，做只读 Server List Ping；
   记录协议号、版本文本、来源、解析时间线、TTL、置信度。ping 关闭、伪造、
   ViaVersion/代理多版本要得到 `NEEDS_PIN`/可解释阻断，不轮番登录猜版本。
2. **第二 bundle**：以 1.20.1 为真实候选，审查 Mojang/Fabric/Bridge/Java/
   OS-arch 组合和许可；从受信上游获取、核大小/散列，隔离构建与测试。
   能下载不等于 tested，1.21.4 的 pin/Bridge JAR 不得直接改名复用。
3. **Resolver/installer**：仅从已验证 Bundle Registry 选择；缺缓存时内容
   寻址下载、临时文件校验后原子发布；中断/hash 错/磁盘满不留下可启动
   半成品。多版本代理与协议歧义需要 pin，而不是循环试登。
4. **Remote Profile**：将现有 loopback-only P0 白名单扩展为显式保存的
   远程地址策略；仍不扫描局域网、不让聊天/网页内容改连接目标。
   状态 ping 不证明 offline/online auth，身份模式只来自可信 Profile；
   首次和重连都核对服务端观察的名字/UUID。
5. **E2E**：同一 `kin_id` 从 1.21.4 受控服切到 1.20.1 测试服须停止旧
   客户端、失效旧 generation/lease、启动新 tested bundle 并重验世界；
   Soul/Memory 不换人。正确版本 JOIN+首快照；错误/未知/伪造版本可解释
   阻断；默认不自动启用在线账号适配器。真实远程测试先做非破坏性连接，
   不在用户服上强杀、重置、资源包注入或改世界设置。

上述是**任务顺序与验收边界**，不是宣称任何一步已经实现。每小卡仍要按
本页六项连续推进门槛单独设计、测试、commit/push。若没有通过完整认证
链与会话证据，不要因为用户关了正版验证就推断所有 1.20.1 服都会放行。

## 阶段交付模板（每次都填，不用回来索取新格式）

在 `development-todo.md` 的新条目或该 task card 的 `completion_evidence`
写下下列字段，缺项必须写“未测/为何”而不是留空：

```text
task_id / status / previous_next / next_after_done
baseline SHA / implementation SHA / local HEAD / remote main SHA / remote work-branch SHA
exact changed paths / allowed_paths check / rejected alternatives / unresolved assumptions
local commands, exit codes, pass-fail-skip totals / Java JDK version / Docker image+jar pins
real run IDs, kin/session/generation, server directory, mode and expected event order
case id+version, attempt_sequence, supersedes_run_id, bundle digest and artifact list
evidence verify / hermetic rejudge / replay (or not applicable) / promotion outcome
counterexamples actually driven to FAIL / known limits / whether an old FAIL is retained
```

不要把 user confirmation、诊断 run、未封材料、封存 PASS、promotion satisfied
混为一种状态。任何新代理接手时只需从“恢复步骤”重新读一次机器状态，再从唯一
`NEXT` 继续，无需让用户每完成一小节就重新索取计划。

## 可复制的本地命令模板

命令从仓库根执行；运行前核对当前平台、工作目录与工具 `--help`，不要把
Windows 的路径直接塞给 Linux 容器。下面是门禁模板，不表示每一步都应该在
每张纯文档卡里重跑 Minecraft。每条命令保留原始输出和退出码；不要用管道
尾端的退出码冒充被测试工具的退出码。

```powershell
git status --short
git diff --check
uv run --frozen pytest -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen python tools/check_boundaries.py
uv run --frozen python tools/check_case_assertions.py
uv run --frozen python tools/verify_fixture_digests.py
uv run --frozen python tools/check_workflow_pins.py
uv run --frozen python tools/report_cases.py
```

Bridge/proto 发生改动时还运行以下独立边界门禁，并用用户已有的
`D:\env\jdk-21.0.12.1\bin` 的 Java 21 运行 Gradle（系统 PATH 上的 Java
17/27 不能代替它）。`check --rerun-tasks` 必须显示测试任务实际执行；
`UP-TO-DATE`/`FROM-CACHE` 不是本卡的 Java 测试证据。

```powershell
uv run --no-project python tools/check_bridge_scaffold.py
uv run --no-project python tools/check_bridge_host_boundary.py
uv run --no-project python tools/check_bridge_protocol.py
uv run --no-project python tools/check_bridge_proto_java.py
```

受控 runner 已使用本地 Docker image `minekin-runner:local`、volume
`minekin-runner-data` 和经 SHA-1 核对的 `.tmp/vanilla/server.jar`；用户已接受
此受控场景的 Mojang EULA，不需要再次下载 Java。下面只示意**正向离线**
诊断的启动形状，不能作为 ADMIT-070 注入场景的完成证明：

```powershell
wsl bash -lc 'MINEKIN_KIN_ID=kin-01 MINEKIN_SERVER_JAR="$PWD/.tmp/vanilla/server.jar" MINEKIN_DOMAIN_SECONDS=90 bash test-orchestrator/runner/run.sh domain session start --profile tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json --server-profile tests/fixtures/runtime-input/controlled-offline-server.json'
```

正式 case 的 knob、`MINEKIN_DOMAIN_CASE`、session 参数必须从那张 case 的
任务卡与 `domain.sh` 验证，不能复制上一条命令后只改 case 名。受控拒绝场景
的 runner 可能因主动停止客户端而返回 14；判断只能来自同 run 的 ledger、
run document、server artifacts 与 sealed verdict，不能把退出码 14 自动当
失败或 PASS。容器里有两个 Kin 时必须显式指定 `MINEKIN_KIN_ID`，不能让
runner 猜第一份 ledger。

证据读者的真实 CLI 形状已用 `--help` 核对（`evidence verify` 的数据根从
环境读取，**没有** `--data-root` 参数）：

```text
python -m minekin_core evidence verify <run-id>
python tools/rejudge_evidence.py <absolute-bundle-directory>
python -m minekin_core replay <absolute-bundle-directory>
python tools/replay_evidence.py <absolute-bundle-directory>
python tools/report_promotion.py --data-root <absolute-data-root> --work-package W40
python tools/report_soak.py --data-root <absolute-data-root> --run-id <run-id>
```

`report_promotion.py` 不带 `--work-package` 时回答全部门禁，非零退出码
可能是**按设计被阻断**而非命令坏了；读 JSON 的 `blocking_cases`、`blocks`
与 latest attempt。旧 PASS 后的新 FAIL 必须按 supersession 阻断，不能
删 FAIL 或重排目录来恢复绿灯。

## 最后停机检查

离开一个阶段前再问四件事：本次改动是否还在唯一 `NEXT` 的范围里？有无
真实观察被写成推断？是否所有红灯、跳过与未测都写明？最新可逆 commit
是否已在两个远端 refs 上核对？四个答案有任一不确定，就维持进行中状态；
不要靠改文档措辞把它变成 DONE。
