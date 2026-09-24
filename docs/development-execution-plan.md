# 开发执行控制计划

> 这份文件是当前开发队列的单一入口。`development-todo.md` 保留调查记录、
> 实测日志与历史结论，但不得再从其中自由挑选任务。任何执行者（包括 Claude）
> 只能处理本文唯一标为 `NEXT` 的任务；完成、验证、commit 并 push 后，主控才可
> 把下一张卡提升为 `NEXT`。

## 计划元数据

- `plan_version`: 1
- `baseline_commit`: `59e425d2b7cc1793427a88cb6c75597f26c6dbb7`
- `baseline_date`: 2026-09-22
- `baseline_branch`: `main`
- `baseline_remote`: `origin/main`
- `current_next`: `ADMIT-070-REFUSAL-INJECTION-001`（本 commit 提升，见该卡 `promotion_reason`）。
  其余未闭合卡仍是 `HOST-ADMISSION-DESIGN-001`/`OPERATIONS-RETENTION-001`/`PROCESS-RECOVERY-001`
  三项 `BLOCKED_DECISION` 与 `HOST/W80+` 的 `DEFERRED`，都要用户先拍板。
- `temporary_executor_handoff`: [Qoder 执行交接](qoder-execution-handoff.md)；
  执行者只实现当前唯一 `NEXT` 并交付证据，主控独占任务状态与下一卡提升。

权威顺序：

1. 用户当前明确指令；
2. 更具体的专项 contract 与 ADR；
3. [P0 核心原型执行计划](p0-prototype-execution-plan.md)；
4. 本执行控制计划；
5. [开发 TODO 与执行门禁](development-todo.md)中的历史记录。

若较低层与较高层冲突，停止执行并记录冲突，不自行改写目标。

## 不可变边界

- P0 core 仍按 `W00 → W10 → W20 → W30 → W40 → W50 → W60 → W70`
  收口；在 P0 core 晋级证据齐备之前，不展开 W80、PlayerMind、Dashboard、
  社会系统或多 Kin 产品化。
- P0 产品边界仍是一个 Python `minekin-core` 进程与一个 Java 21
  Minecraft/Fabric JVM。测试域工具、oracle 与 runner 不得进入产品 wheel/JAR。
- 失败运行只追加、不覆盖；没有真实 evidence 不得写成 `PASS`、`tested` 或
  `P0_CORE_TESTED`。本地单测不能替代真实客户端、真实线程、真实故障或真实
  Minecraft 生命周期证据。
- Mojang EULA 已由用户确认接受（2026-09-23）；执行者不得替用户代选接受，但只可在唯一 `NEXT` 卡明确要求时运行相应受控场景，不把该确认外推到其他服务器/用途。
- **CI 在跑，而且它不是走过场；但它仍不是本阶段的完成证据。**（2026-09-23 更正：这一条原文写的是「CI 当前没有额度」，那已经过期了。实测最近 12 次 run 全绿，最新一次 3 个 job `bridge-static`/`python`/`protocol` 共 37 步全部执行——包括 `buf lint`、`buf format --diff` 与「Verify checked-in Python protobufs」，也就是说 protobuf 与提交进仓库的生成物有一道**独立于本地门禁**的核对。）保留的仍是那条政策：完成证据来自本地与 Docker，因为 CI 同样跑不了 Minecraft，而上面那条「本地单测不能替代真实客户端证据」不会因为 CI 绿了而改变。反向也成立——CI 红是真信号，不是噪声，不要按它没额度处理。**这条在 2026-09-23 被自己用了一次**：一个纯文档提交红在 `uv sync --locked` 上，查下去发现是 `uv.lock` 把 92 个包钉在一台机器用户级配置里的第三方镜像上，而那个镜像会瞬时 403——信号指向的是一条仓库里没写、CI 却每次依赖的供应链，不是噪声。细节与两条候选修法见 `development-todo.md`。

- HOST 与 W80+ 默认冻结。只有当前 `NEXT` 明确允许，或修复主干回归时，才可
  修改其生产代码。

## 当前已验证状态

以下事实必须从命令重新生成，不手工维护漂移数字：

```text
git rev-parse HEAD
git rev-list --left-right --count main...origin/main
uv run --frozen python tools/report_cases.py
uv run --frozen python tools/check_case_assertions.py
```

在基线 commit 上的读数：

- `main == origin/main == 59e425d2b7cc1793427a88cb6c75597f26c6dbb7`；
- 33 cases / 121 assertion references / 6 mandatory；
- 19 cases 由本地 judge 执行，14 cases 由 run material judge 执行；
- 0 mixed、0 unimplemented、0 unregistered assertion；
- 本次规划基线的本地验证为 1722 passed / 2 skipped，加 Ruff、Pyright、
  boundaries、case assertions、fixture digests、workflow pins 与 Bridge scaffold。

这些数字只描述“已经登记的 case”，不证明 contract 要求的 case 已登记完整——
规划时工具正缺少这一层，那也是 `PLAN-COVERAGE-001` 的来源。

该卡实现之后，同一层有了自己的读数，同样从命令重新生成：

```text
uv run --frozen python tools/report_cases.py
```

- required-case inventory v1：**72 required / 36 present / 36 missing**，按 gate 读出：
  `W00` 1、`W10` 1、`W20` 1、`W30` 11、`W40` 12、`W50` 3、`W60` 3、`W70` 5、
  `p0-core` 38、`p0-nav-exp` 1、`host-integrated` 33（present 15 / missing 18）、`W40` 12
  （present 5 / missing 7）；按证据
  种类 `local-only` 7、`runtime-required` 65；已登记但不 gating 的 27 条；
- **九条 ADMIT 里只有一条能靠既有判据关掉**（2026-09-23，`ADMIT-001` 登记之后；这
  一条与前一条是同一个做法：契约的行只给场景与「必须证明」，能关的是那些**判据已经以断言
  形式存在**的）。`ADMIT-001` 的「走正常客户端路径，JOIN+首快照后才 PLAYABLE」正好就是
  `first_snapshot_admitted`（JOIN 行存在 + `snapshots_admitted >= 1` + `connection_state ==
  PLAYABLE`）加 `server_observed_join_identity`（服务端自己的那份记录），两条都已在
  `CORE-020` 上验过，所以它只是**认领**既有判据。**其余八条都要先把判据写成断言**：最典型的是
  `the_refusal_was_classified_in_the_ledger` **把 `WHITELIST_REJECTED` 写死在函数里**，因此
  `ADMIT-040`（要 `AUTH_MODE_MISMATCH`）与 `ADMIT-050`（封禁/重名）用不了它；`ADMIT-010`（不
  扫描局域网）、`ADMIT-020`（SRV 原始地址与 endpoint）、`ADMIT-060`（资源包未授权）、
  `ADMIT-120`（canary 不回流）今天**没有任何断言**对应。**这是一件要不要做、由谁做的决定，
  不是缺几行代码**——每写一条新断言就是给一个运行定义一个 PASS 的含义。
- **`local-only` 那一类已经没有缺口了**（2026-09-23，`HOSTCTL-060` 登记之后）。这条值得
  单独写出来，因为本文先前说错过它：`CASE-CORE-001` 完成时这里写过一句「剩下 38 条
  全是 `runtime-required`」——**那是错的**，机器读数里当时就有 1 条 `local-only`
  （`HOSTCTL-060`），而 inventory 的 `validation_class` 一直是判据，本文那句是以表代
  读数。**今天 missing 的 37 条全部是 `runtime-required`，这是命令读出来的**，不是推的。
- 这份 missing 与本文下方“已知缺失 case（规划视图）”那张表逐族一致，但由机器读出；
- 尚未冻结编号的族按缺口报出：`PERSIST`（`PlanningGap`，不拦任何门）；
- 每道 gate 只按**自己**的 required set 判证据与前置条件，所以 HOST/NAV 的洞不阻塞
  `W40`；promotion 对不完整的 required set fail closed
  （`REQUIRED_CASE_NOT_REGISTERED`、`REQUIRED_CASE_MISATTRIBUTED`）。
  `mandatory: false` 仍作为独立诊断维度报告，不被 inventory 偷偷改写；因此今天
  `W00`、`W10`、`W20`、`W60`、`W70` 五道的 case set 是齐的，其中 W70 仍因没有
  mandatory case 而由既有 `NO_MANDATORY_CASES` 规则阻断——这是准确读数，不是回归。

## 最近完成

### OFFLINE-CANDIDATE-001 — 第二个离线候选跑不起来

- `status`: `DONE`
- `completion_commit`: `34bef0cd8d715d691fa65d79296081f16436d3c3`
- `decision`（**执行者自行拍下的一条，理由如下**）：本卡要动的是产品 CLI 表面，而本文的
  「不可变边界」写着生产代码只在**当前 `NEXT` 明确允许**或**修复主干回归**时可改。这一条
  两者都不是——它是**新增表面**。**拍板的依据是用户反复给出的明确指令**（「自动选择最佳
  方案就行」「不要询问我打断任务」），而本文的权威顺序第一条正是「用户当前明确指令」，
  它高于本文自己的规则。**改动是一个开关，可选、默认逐字节不变、一次 revert 即可撤销**，
  所以代价有界；相对地，不做的代价是 campaign 的第 4 个场景**永远跑不起来而没有任何东西
  会说**。若主控不同意这次越权，撤销的方式就是 revert 这一个 commit。
- `finding`: `adapters/launcher/offline_session.py` 声明了两个候选，而产品里唯一的选点是
  `cli/session.py` 的 `OFFLINE_SESSION_CANDIDATES[0]`——永远 OFF-A。没有 CLI 开关、没有
  环境变量、没有 harness 旋钮；`enum-aligned` 在全仓只出现在契约枚举与一个 Java 自检夹具里。
- `scope`（已实现）：`session start` 新增 `--identity-candidate`，可选值**从候选清单读出**；
  `candidate_by_id()` 负责解析，**不给就是第一个**，**点名不存在的候选拒绝并列出已知的**。
- `non_goals`: 不新增候选；不改候选的 argv 语义；不碰 `OFFLINE-040/050/060` 那几半；
  不动 `p0-core` 的评级。
- `completion_evidence`: 本地、`origin/main` 与远端 `refs/heads/main` 已核对为同一 SHA；
  **全量 pytest 结果见 `development-todo.md` 本轮记录**，Ruff check/format、Pyright（strict，
  0 errors）、boundaries、case assertions、fixture digests、workflow pins 与 `git diff --check`
  全绿。**三处变异各自驱动到红**：默认改成第二个候选 → 默认那条用例红；未知 id 改成静默回退
  → 拒绝那条红；**在候选清单里加第三个候选而完全不动 `parser.py` → 命令行接受了它**，这条
  正是「可选值只有一个来源」的证明。`docs/p0-core-internal-architecture.md` §15 已同步。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `still_open`: **真实运行仍需要一次客户端**——本卡只做到「选得出来」。

### PLAN-COVERAGE-001 — 契约要求的 case 清单必须可机器核对

- `status`: `DONE`
- `completion_commit`: `6863be919ba0b80756091cf4d15952c64142710f`
- `completion_evidence`: 本地、`origin/main` 与远端 `refs/heads/main` 已核对为同一 SHA；
  1762 passed / 2 skipped，Ruff、Pyright、boundaries、case assertions、fixture
  digests、workflow pins 与 `git diff --check` 全绿。
- `why_now`: 当前 `report_cases.py` 与 `check_case_assertions.py` 只遍历已有 fixture。
  如果 contract 要求的 case 完全缺失，报告仍会显示 0 unimplemented，promotion
  也可能在残缺 case 集上给出假阳性。继续补 case 前必须先堵住这个缺口。
- `contract_anchors`:
  - `docs/p0-validation-evidence-contract.md`
  - `docs/p0-remote-admission-contract.md`
  - `docs/p0-offline-session-compatibility-contract.md`
  - `docs/hosted-world-storage-lifecycle-contract.md`
  - `docs/hosted-world-control-boundary-contract.md`
  - `docs/hosted-world-commit-recovery-contract.md`
- `dependencies`: 无真实 Minecraft、无网络、无 EULA；只依赖当前 case schema、
  registry 与 promotion 规则。
- `allowed_paths`:
  - `src/minekin_core/domain/cases.py`
  - `src/minekin_core/adapters/evidence/promotion.py`
  - `schemas/case-manifest.schema.json`（仅在确有必要时）
  - `tools/report_cases.py`
  - `tools/report_promotion.py`
  - 对应 `tests/unit/`、`tests/contract/` 测试
  - 本计划与 `development-todo.md` 的状态记录
- `forbidden_paths`:
  - `bridge/`、`proto/`、`generated/`
  - `src/minekin_core/cli/session.py` 与 `session_runtime.py`
  - `test-orchestrator/runner/`
  - HOST/W80 生产实现
- `non_goals`:
  - 不补齐所有缺失 case；
  - 不把任何现有 `mandatory: false` 直接翻为 true；
  - 不依据文件名、时间戳或文档 prose 猜 contract 完成度；
  - 不运行 Minecraft，不生成 evidence bundle。
- `acceptance_evidence`:
  1. 有一份机器可读、版本化的 required-case inventory，覆盖 CORE、ADMIT、
     OFFLINE、HOST、HOSTCTL、HOSTCOMMIT、NAV；若 PERSIST 尚未冻结编号，应明确
     报为计划缺口而不是编造编号。
  2. `report_cases.py` 同时报告 required / present / missing，并区分 local-only、
     runtime-required 与 mandatory；现有 33 case 的 judge 分类保持不变。
  3. promotion 对 required set 不完整 fail closed；“已有的 mandatory 都 PASS”
     不能掩盖 required case 缺失。
  4. 负向变异：删掉任一 required fixture，报告必须点名 missing，promotion 必须
     拒绝；新增未知/重复 required ID 也必须拒绝。
  5. 全量本地门禁通过，且没有修改真实运行路径。
- `validation_class`: `LOCAL`
- `stop_conditions`:
  - contract 对某个 ID 的存在性或 work package 相互矛盾；
  - inventory 需要凭空决定尚未冻结的 PERSIST 编号；
  - 实现要求改变 promotion 的“证据通过”语义而不仅是补全 required-set 前置门。
- `commit_intent`: `feat(cases): make required coverage explicit`

### CORE-REPLAY-CLI-001 — 接通冻结的产品 CLI

- `status`: `DONE`
- `completion_commit`: `de79a2bb09cca57dc70267495b108a1655a90e35`
- `completion_evidence`: 本地、`origin/main` 与远端 `refs/heads/main` 已核对为同一 SHA；
  1807 passed / 2 skipped，Ruff、Pyright、boundaries、case assertions、fixture
  digests、workflow pins 与 `git diff --check` 全绿；规格与工程双审查最终无发现。
- `depends_on`: `PLAN-COVERAGE-001`
- `scope`: 将 parser 已冻结的 `minekin replay <EVIDENCE_DIR>` 接入产品入口；
  产品 CLI 与 standalone tool 经同一个深模块读取 sealed/addressed bundle。
- `non_goals`: 不记录新状态迁移；不改 session 生命周期；不从事件名猜状态；
  fixture-only 比较仍留在测试工具。
- `acceptance`: 同一份 trace snapshot 完成摘要/大小校验与解析；严格拒绝 malformed
  UTF-8/JSON、空行、重复 key、非有限数、未声明/篡改 trace；旧 bundle 缺状态迁移
  时稳定返回语义不完整，integrity 错误为 STORAGE、语义不完整为 SESSION；只读。
- `validation_class`: `LOCAL`

### CASE-CORE-001 — 给已有供应链判据建立必需 case

- `status`: `DONE`
- `completion_commit`: `9b2d53913950d038213d4fbe9763ce31eaa44129`
- `completion_evidence`: 本地、`origin/main` 与远端 `refs/heads/main` 已核对为同一 SHA；
  1810 passed / 2 skipped，Ruff、Pyright、boundaries、115 条 case assertions、fixture
  digests、workflow pins 与 `git diff --check` 全绿。三条被点名的变异各自驱动到红：
  改坏 `validate_bundle_recipe` 的 Fabric API 摘要比较、把 Bridge artifact gate 的
  打包依赖摘要比较短路、把 `BundleStore.verify` 的工件摘要比较短路，三次都先让
  `run_repo_case` 对 CORE-001 判 FAIL，再原样还原。删掉 `core-001.json` 后报告点名
  `CORE-001` missing、`W10` 由 `satisfied: true` 变为 `false`，promotion 以
  `REQUIRED_CASE_NOT_REGISTERED` fail closed——同一次读数里 `W00` 与
  `host-integrated` 不变。**没有改 `src/`、没有跑 Minecraft、没有接受 EULA。**
- `depends_on`: `PLAN-COVERAGE-001`
- `scope`: 复用 bundle recipe、artifact store 与 Bridge artifact gate 的既有判据，
  新增 CORE-001 case 与 assertion digest，不重写已有检查。
- `acceptance`: repo case runner PASS；摘要篡改、未知 mod、artifact gate 变异各自失败；
  fixture digest 更新可复核。
- `validation_class`: `LOCAL`
- `commit_intent`: `feat(cases): give the supply chain its required case`

### CORE-METRICS-001 — W20 tick/render 可测量性

- `status`: `DONE`
- `completion_commit`: `1e43a9941787f27f96334515dd55c6fb657d7c09`
- `completion_evidence`: 本地、`origin/main` 与远端 `refs/heads/main` 已核对为同一 SHA；
  1829 passed / 2 skipped，Ruff、Pyright、boundaries、115 条 case assertions、fixture
  digests、workflow pins、四条 Bridge scaffold 门禁与 `git diff --check` 全绿；Bridge
  的 Gradle `build`（JDK 21）绿，并含产物门禁 `Bridge artifacts: OK`。**三处独立的
  变异各自驱动到红**：把窗口序号改成不再推进 → Java 自检在
  `aWindowThatWasNotDeliveredStillConsumesItsNumber` 报错；把 ring 的保留计数改成不
  封顶 → 在 `budgetsAreBoundedAndKeepTheNewest` 报错；把预算窗口的信息类别改成
  `PLAYER_EQUIVALENT` → 类别表与端到端用例双双变红；把 `publishBudgetWindow` 改成
  溢出即 `failClosed`（以及反向：让一个生命周期 publisher 不再 fail closed）→
  预算纪律用例两个方向各红一次。全部原样还原，`src/` 与 `tools/` 事后核对零残留。
- `depends_on`: `CORE-REPLAY-CLI-001`
- `scope`: 只增加预算采样所需的最小 Bridge/proto 字段、聚合与 evidence 形状。
- `non_goals`: 本地数据不得冒充真实 P50/P95/P99；不在本任务设阈值。
- `acceptance`: 本地/Java/Docker 门禁证明采样非阻塞、有界、可封存；真实 percentile
  仍由后续 runner campaign 验收。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `feat(bridge): make the callback budget measurable`

## 唯一 NEXT

### CASE-CORE-001-INPUT-PINS — 让供应链输入变化必然移动 case version

- `status`: `DONE`
- `why_now`: 对已完成的 `CASE-CORE-001` 做独立复核时发现：fixture 已声明 recipe、
  Gradle lock 与 host-boundary name table 为 `inputs`，却没有把其字节写入
  `input_digests`。因此三者与全局 pin 一起更新后，只要断言函数没改，case version
  就不动；旧供应链清单上的 sealed PASS 仍可能满足新的 mandatory W10。这与本仓库
  已在世界 fixture 上冻结的规则相反：外部输入变化必须先造成
  `CASE_VERSION_MISMATCH`，不能由新 checkout 重新解释旧证据。
- `depends_on`: `CASE-CORE-001`
- `scope`: 只给 `CORE-001` 已声明的三个输入记录 SHA-256，并更新该 case 的 fixture
  digest；loader 对 UTF-8 文本以 LF 规范化后摘要、对二进制保留原始字节，保证
  Windows/Linux checkout 对同一输入给出同一版本；不改供应链判据、不重封 PASS bundle。
- `allowed_paths`:
  - `tests/fixtures/cases/core-001.json`
  - `tests/fixtures/manifest.sha256`
  - `src/minekin_core/adapters/evidence/promotion.py`（仅 input digest 的跨平台规范化）
  - 针对 case input pin/version 行为的测试（仅在现有门禁不能证明验收项时）
  - 本计划与 `development-todo.md` 的状态记录
- `forbidden_paths`:
  - 除上方精确列出的 case loader 外，其余 `src/`；以及 `bridge/`、`proto/`、`generated/`
  - 现有供应链断言实现与 assertion registry
  - evidence bundle、runner 数据根与 promotion 语义
- `acceptance`:
  1. `CORE-001.input_digests` 精确覆盖它声明的三个非 glob 输入，按文本 LF 规范化后
     逐项匹配；二进制仍按原字节摘要；
  2. 分别变异任一输入而不更新 case JSON 时，`load_case_manifest` 以及使用它的封存/
     promotion registry load 在执行断言或采信证据前 fail closed；更新 pin 后 case
  version 必须不同，旧 bundle 因 `CASE_VERSION_MISMATCH` 不得满足 W10；同一文本
  输入仅改变 LF/CRLF 表示时摘要与 case version 保持一致；
  3. `run_repo_case` PASS，fixture、case assertion、boundary 与全量本地门禁通过；
  4. 不接受 EULA、不运行 Minecraft、不把旧 bundle 重写为新版本。
- `validation_class`: `LOCAL`
- `commit_intent`: `fix(cases): bind CORE-001 to its reviewed inputs`
- `stop_conditions`: 任一声明输入并非判据的一部分，或现有 case loader 无法在不改变
  promotion 语义的情况下验证 pin；遇到时停止并回到规格复核。
- `completion_commit`: `453d2fb93dd6612f5cdab003605f2f22e499d280` (pushed to `origin/main`; remote SHA verified)
- `completion_evidence`: full pytest 1884 passed / 2 skipped; CORE-001 repo case PASS (5/5); case assertions (120), fixture digests, boundaries, workflow pins, Ruff, Pyright and `git diff --check` passed. Three declared inputs are pinned; text pins normalize CRLF/LF; changed inputs fail closed; binary pin behavior preserved. No Minecraft execution on this card.

这张回归卡已完成并推送。主控已按用户授权冻结 `EVIDENCE-SEQUENCE-001` 的方案乙，
它是当前唯一 `NEXT`；Claude 不得从历史 TODO 自选别的任务。

**队列之外还有第二类，2026-09-23 才发现并做掉**：**证据生产也不是卡**。`local-only`
的 required case 只差一份**封存的 PASS bundle**，而 `tools/seal_repo_case.py` 不需要
Minecraft、不需要 runner、不需要任何决定——这正是 `CASE-CORE-001` 当时留给后人的
那一半。做了 `CORE-001` 与 `W00-CONTRACT-001` 两份之后，**`W00` 与 `W10` 两道门都
变成 `promotable`**（`blocks: []`、`requirement.satisfied: true`），而用机器读数问
一遍「哪些门的 required set 整组都是 `local-only`」，答案正好是这两道——其余的道
要么要真客户端（`W20`、`W60`），要么缺 1～18 条运行时用例，要么一条 mandatory case
都没有（`W70`）。**所以本地证据生产能关死的门只有这两道，已经关死了。**

**队列之外还有第三类，2026-09-23**：**判官自己的拒绝分支也不是卡**。`tools/assert_case_evidence.py`
里每一条 runtime 断言的每一个拒绝理由，都是某次真实运行的判决，而一个**从没响过的分支**
可以是写错的。**判据是这条分支有没有被执行过，不是它的名字有没有出现在哪个文件里**：
用标准库 `sys.settrace` 只对该文件装行级 tracer 跑**全量**，读「哪些 `return` 行从未执行」，
再把「从未执行」用变异确认一次（把那行换成 `pass`——控制流不变、只是不再拒绝，红了才算有
测试）。**文本搜索只用来提名**，它两个方向都错过：测试把 f-string 折行会让**已覆盖**的分支
看起来没覆盖，而这一个理由名被**多个函数**返回时，别的函数在响会让它**看起来**已覆盖。
2026-09-23 的读数是 **154 处 `return`，144 处执行过、10 处从未执行**，而这 10 处经变异确认
没有测试观察——其中 **7 处**正是文本搜索判成「已覆盖」的，**6 处是 `LEDGER_UNREADABLE`**
（同一个理由名被 11 个函数返回）。**这 10 处已于同日全部补上，读数变成 154/154、0 处从未
执行**，且这 10 处各自单独变异确认过（把那一行换成 `pass`，各自只红一条）。口径、方法与
文本搜索的两次方法错误都记在 `development-todo.md`；追踪的盲点是子进程追不到，所以
「从未执行」只算**提名**，判决一律靠变异。**审计已入库为 `tools/trace_reason_branches.py`**
（`uv run --frozen python tools/trace_reason_branches.py`，约 3 分钟），不必重写。
**完整 154 路变异已于同日做完，读数 154/154**：每一条拒绝的**原话**都被某个测试钉住。
两件工具把这件事说全——`tools/trace_reason_branches.py` 说「哪条分支被走到」，
`tools/verify_reason_assertions.py` 说「哪条理由的原话被断言」（后者只改理由的措辞、
不改控制流，所以「程序被改坏」不可能冒充成「没有测试反对」）。**就本地证据能关到的程度，
这个面已经关死**；口径、方法与这两件工具各自的自我更正都记在 `development-todo.md`。

这也说明本文先前那句「没有任何一张卡能提升」是对的、而**「没有本地能做的活」是错的**——
同一类错误（拿文档对状态的描述代替机器读数）在这个项目里已经出现两次，第八步那次
是 missing 集合的分类。**判断「还有没有可做的」，要看机器读数，不要看本文的措辞。**

这不是「没有工作可做」，而是**剩下的每一件都卡在被明确写下的门禁上**：要么需要
受控 runner 与用户对 EULA 的授权（`REAL-P0-CAMPAIGN-001` 的前置），要么需要用户
先对一个设计问题做决定。按「越权即停止」的规则，这里不自行发明新卡，也不把某个
真实运行缺口改写成本地任务来制造进度。

**这个「空」是查过的，不是没看。**（2026-09-23）`.claude/worktrees/` 下另有一个
执行者留下的 9 个 `worktree-*` 目录，逐条核过之后**没有一份是未落地的成果**：两个
有提交的分支与 main 上同名的落地提交**树完全相同**，其余七个的基点都是 main 的
祖先且 main 在同样的文件上有更晚的提交，其中若干文件（`orphans.py`、`status.py`、
`cli/replay.py`、`bundle.py`、`cli/evidence.py`）已经与 main **逐字节相同**。核对
方法与被证伪的那个判据都记在 `development-todo.md` 里，可以重推。

解除方式有三种，每一种都要用户或真实运行，不需要本文发明范围：

1. 对四张 `BLOCKED_DECISION` 卡中的任意一张给出决定，它随即变成 `QUEUED → NEXT`；
2. 提供受控 runner 与 EULA 授权，`CORE-STATE-TRANSITION-001` 与
   `REAL-P0-CAMPAIGN-001` 即可执行；
3. 另行指定一张新卡（先入 `QUEUED`，按本文规则提升）。

## 阶段队列

状态只允许：`QUEUED`、`BLOCKED_DECISION`、`WAITING_REAL_RUN`、`DEFERRED`、
`DONE`。只有上一张卡已 commit、push 且远端 SHA 可核对，主控才可提升下一张。

### CASE-CORE-001-INPUT-PINS — CORE-001 输入版本绑定回归

- `status`: `DONE`
- `depends_on`: `CASE-CORE-001`
- `scope`: 与上方唯一 NEXT 卡完全相同；本段只保留它在阶段队列中的位置。
- `completion_commit`: `453d2fb93dd6612f5cdab003605f2f22e499d280` (pushed to `origin/main`; remote SHA verified)
- `next_after_done`: `EVIDENCE-SEQUENCE-001`

### CORE-STATE-TRANSITION-001 — 账本显式记录状态迁移

- `status`: `DONE`
- `depends_on`: `CORE-REPLAY-CLI-001`
- `scope`: 每次合法 session transition 记录显式 from/to 事实，使新 bundle 可 replay。
- `stop_reason`: 该改动横跨真实客户端生命周期与异步账本；强杀时最后一条迁移是否
  落账不能由 mock 证明。
- `unblock_condition`: 可使用受控 runner，且能在变更后运行正常退出与强杀场景。
- `allowed_paths`:
  - `src/minekin_core/domain/session_state.py` (retain the frozen transition table; expose a validated transition seam only)
  - `src/minekin_core/cli/session.py` and `src/minekin_core/cli/session_runtime.py` (persist each applied move through the run ledger)
  - `src/minekin_core/adapters/sqlite/session_log.py` (register and validate the reviewed transition event)
  - `src/minekin_core/domain/replay.py` only if needed to consume the existing from/to payload contract
  - focused tests for legal/illegal transitions, append ordering, replay and controlled-run crash windows
  - this plan and `development-todo.md` status only
- `forbidden_paths`: Bridge/proto/generated; transition-table semantics; unrelated session/admission/input behavior; case IDs/contracts; evidence attempt sequencing; CI workflows.
- `acceptance`: each transition actually applied by Core has exactly one durable ledger fact containing `from` and `to`; illegal transitions write none; replay returns the last persisted state and rejects illegal/inconsistent moves; normal-exit and forced-stop controlled Docker runs prove committed transition rows survive client termination; all local repository gates pass.
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `feat(session): persist explicit state transitions`
- `stop_conditions`: if durable-write ordering changes runtime behavior or the forced-stop run cannot distinguish a persisted transition from an inferred one, stop and refine this card before broadening scope.
- `completion_commit`: `14acde7f63bb7a9584a63e7c163780d2cbd84dea` (pushed to `origin/main`; local, tracking and remote SHA verified)
- `completion_evidence`: 1903 passed / 2 skipped; Ruff check/format, Pyright (0 errors), boundaries, case assertions (120), fixture digests, workflow pins, four Bridge static/protocol gates, and `./gradlew check --rerun-tasks` on JDK 21.0.12.1 (15 tasks, BUILD SUCCESSFUL). Docker runner doctor passed all five checks. Two final-build domain runs completed: graceful `session stop` run `f1db5741c9d049f7872c72d1872ac458` and forced client JVM kill run `dd872210b53c4da1ab834ac539dd2aa0`; after both containers exited, SQLite showed exactly 11 `SessionStateTransitioned` rows per run, all `CORE/CORE`, with each `from` matching the prior `to` and both ending at `STOPPED`. The forced run's fault helper recorded `INJECTED` with no reasons and Core recorded `SessionInterrupted`. Both runner commands reported `BRIDGE_LOST` (exit 14), the existing controlled-runner teardown outcome after the Bridge process disappears; neither is represented as `CLIENT_EXITED`. Unit wiring replay projected a real session ledger to its persisted final state; illegal transition and append-order tests passed. CI was not run.

### REAL-P0-CAMPAIGN-001 — 批量关闭真实运行缺口

- `status`: `BLOCKED_EVIDENCE`
- `blocked_by`: `ADMIT-070-REFUSAL-INJECTION-001`（`NEXT`）。`order` 的第 1 个场景（在线认证拒绝）
  与第 2 个场景（资源包拒绝）已各自封出当前 build 上 `PASS`/`AGREES` 的正式 bundle 并四读一致。
  第 3 个场景（JOIN 后首快照失败）的判据已由 `ADMIT-070-EVIDENCE-DESIGN-001` 冻结在专项契约里，
  冻结的结论是：**这一条停在 `BLOCKED_EVIDENCE` 的原因不是读不出，而是发生不了**——被拒快照的
  理由确实会写进 run document 的 `snapshot_rejections`（读数那一层在真实运行里会工作，
  `entities_rejected` 就写过），但五个 `SnapshotReason` 在当前构建与当前 runner 下一个都触发
  不了，数据卷 36 份真实运行文档该字段全为空。缺的是让 Bridge 在该代第一份快照上按
  `authoritative=false` 上报的一个**默认关断的产品侧开关**（由 runner 显式要求、由测试域记录），
  即本 `blocked_by` 那张卡。
- `scenario_progress`: 2/7 场景已封为正式 case。第 1 个：`ADMIT-040`，run
  `6b5856d57dee4052b2ffba3ff9e3459e`，bundle `46565ef2…`，attempt 1，PASS/AGREES。
  第 2 个：`ADMIT-060`，run `7bc740ea4cde4e1aaff074bb64850348`，bundle
  `ca61b64b86b13b0d55528f2f2604825f973c313ba7adaa91fcefe3a2cb29ddcc`，attempt 2
  （attempt 1 是 run `3c17aa78a838486391634e69d9f8ea98`，因判据 1 的读侧缺陷如实封存为
  `FAIL`，保留不覆盖），PASS/AGREES、`from_repository_build: true`。
  第 2 个场景另有三次**只作诊断**的受控运行，都不进 bundle、不追认 PASS：
  `a114949bf0204a2e8021ec5d02583b4b`（线缆策略事实落地前）、
  `b1ace69e610c4c04a942281add8bd69b`（拒绝侧，`run-114`）与
  `8516151dab664d8692c3bf7ab3288859`（默认离线正向，`run-115`，到达 `PLAYABLE`）。
- `regression_history`: `ADMIT-040-CLASSIFICATION-001` 曾阻断首场景；受控 Docker 诊断运行
  `fdef1d7192dd480db6aed1c5e7e493dd` 在离线身份连接 `online-mode=true`
  原版服务器时，客户端日志出现 `Failed to log in: Invalid session (Try restarting your game and the launcher)`，
  但 Core 的 `SessionInterrupted` 记录了 `ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT`；
  专项契约要求 `AUTH_MODE_MISMATCH`。修复 commit `dd992b1fb2a85d8220e9345cfd7844a8f6c2f255`
  已推送；复跑 `fbb9d4787a3743afa868a804c3c586ec` 的 ledger 确认为
  `AUTH_MODE_MISMATCH`。两次均只作诊断，未封为 ADMIT-040 PASS。
- `depends_on`: `CORE-METRICS-001`、可用 artifact store、受控 runner 与用户 EULA 授权
- `order`: online-mode mismatch → resource-pack refusal → 首快照负向 → OFF-A/OFF-B
  → crash/outbox 窗口 → tick/render 采样 → CORE/OFFLINE/ADMIT promotion report。
- `acceptance`: 当前 build 与当前 case version 的 sealed bundle；verify、rejudge、
  replay（能 replay 的部分）和 promotion 报告一致。
- `execution_steps`:
  1. 每个 scenario 开始前保存当前 required-case inventory、build/artifact 身份与
     case version；只从机器报告读取 `runtime-required` 缺口，不把 `not-gating` case
     或本地结果算作 campaign PASS。
  2. 严格按 `order` 单场景执行；每次运行写入独立 run/attempt，不覆盖失败运行，也不
     把既有 PASS 当成当前 build 的证据。先补足 scenario 所需的 runner knob、profile
     或判据映射；映射未由 contract/fixture 明确时先停在计划更新，不猜 case ID。
  3. 每一份 bundle 都用产品命令 `evidence verify`、测试域 `rejudge_evidence.py`，
     以及适用的 `minekin replay` / `replay_evidence.py` 检查；将结果与
     `report_promotion.py` 按当前 build、case version 和最新 attempt 交叉核对。
  4. 每完成一个场景立即登记 run ID、attempt sequence、bundle digest、case verdict、
     promotion 变化与失败原因，再进入下一个场景；只在 required inventory 和 promotion
     均满足 acceptance 后将 campaign 标为 DONE。
- `current_inventory_snapshot` (2026-09-23，`ADMIT-040` 登记之后重推)：`report_cases.py`
  reports 72 required, 37 present and 35 missing over 37 cases / 139 assertion
  references (125 registered implementations); W00/W10/W20/W60/W70 are satisfied, W30
  misses 8, W40 misses 6, W50 misses 2, host-integrated misses 18, and p0-core misses 16
  (overlap across gates is intentional). The remaining missing requirements are
  `runtime-required`; PERSIST case IDs remain explicitly unfrozen. Do not infer that
  this campaign can close HOST or PERSIST while their separate design decisions remain
  blocked.
- `unblock_evidence`: controlled runner image built locally; Docker `doctor` all five
  checks passed; pinned Minecraft 1.21.4 server jar is available and SHA-1 verified;
  user-confirmed Mojang EULA acceptance is recorded above. The prerequisite is satisfied.

### ADMIT-040-EVIDENCE-DESIGN-001 — 冻结离线身份遇在线认证拒绝的完整判据

- `status`: `DONE`
- `baseline_sha`: `03132e6c1ea7978a9c35798130fce8b3531802cd`
- `promotion_reason`: 新卡已先以 `QUEUED` 登记并推送；它是当前 campaign
  首场景不能正式封证的直接阻断项，现提升为唯一 `NEXT`。
- `why_now`: 当前 build 的受控负向运行 `fbb9d4787a3743afa868a804c3c586ec`
  在 Core ledger 中正确记录 `AUTH_MODE_MISMATCH`，但库存仍报 `ADMIT-040`
  missing。现有 assertion 只覆盖“没进世界”或写死白名单分类；“没有自动启用账号
  适配器”没有同一 run 可复判的材料，不能借单次进程数补成 PASS。
- `allowed_paths`:
  - `docs/p0-remote-admission-contract.md`
  - `docs/p0-launch-plan-contract.md`
  - `docs/development-execution-plan.md`
  - `docs/development-todo.md`
- `forbidden_paths`: 产品代码、测试域判官、case fixtures/registry、runner、proto、CI。
- `non_goals`: 本卡不封 evidence、不改账号认证行为、不声称 ADMIT-040 PASS，
  不把 `online-mode=true` 变成离线身份可入服的目标。
- `acceptance`: 文档明确区分 Core ledger 中的 `AUTH_MODE_MISMATCH`、服务端确实
  要求在线认证、启动身份确实是离线策略，以及拒绝后不自动启用在线适配器；给每一项
  指定可信来源、sealed artifact、可复判断言和至少一个能揭露假阳性的反例。
  若其中一项现有材料不可证，写明需要增加的最小产品/测试域观测点，并生成下一张
  有精确范围的实现卡；不得把“只启动一个进程”或“没进世界”当作替代证据。
- `validation_class`: `LOCAL`
- `commit_intent`: `docs(admission): freeze auth mismatch evidence criteria`
- `stop_conditions`: 如果无法指定不泄露令牌且可归属同一 run 的认证策略观测点，
  停在设计缺口，不创建容易误报 PASS 的 fixture。
- `design_decision` (2026-09-23): 同一 run 的可信 Core 策略对象从经验证的
  `ServerProfile` 构建，P0 只允许 `offline`，没有在线适配器或策略重绑定 API；
  在启动/连接之前写 `AuthPolicyFrozen`（CORE/CORE，run/session/generation，
  `auth_mode=offline`、`online_adapter_enabled=false`、profile id/revision）。
  这是一个由不可变策略对象执行的正向约束，不拿“没有第二个进程”单独冒充
  未切换认证。Sealer 另封经验证的 Server Profile 与服务器自己写的
  `server.properties`；ADMIT-040 同一 bundle 必须交叉核对服务端在线认证、
  Profile 离线、冻结事件、Bridge 过滤后的失败原因、未入服及未重绑定/重启。
  缺事件、revision 不同、服务端实际离线、额外在线策略选择或第二次启动均
  应 FAIL。旧 run 无冻结事件，不追认 PASS。细节已写入专项契约。
- `completion_commit`: `103b9bc94b01da81f9d7c0dc6061275ba227262d`，已推送
  到 `origin/main` 和当前分支，远端 SHA 已核对。
- `completion_evidence`: 两份专项契约写明四项同 run 判据、可信来源、sealed
  artifacts、不可变策略约束及五类假阳性反例；两张精确范围实现卡已排队。
  文档阶段本地 pytest 1903 passed / 2 skipped，Ruff check/format、Pyright 0、
  boundaries、case assertions 120、fixture digest、workflow pins 与 diff check
  通过。没有运行 CI 或新的 Minecraft 场景，也没有把旧诊断 run 宣称 PASS。

### AUTH-POLICY-EVENT-001 — 让 P0 离线认证策略成为可信账本事实

- `status`: `DONE`
- `baseline_sha`: `103b9bc94b01da81f9d7c0dc6061275ba227262d`
- `promotion_reason`: 设计卡 DONE 且已推送，当前 campaign 首场景缺少的第一份
  产品可信事实就是不可变认证策略事件，故提升为唯一 `NEXT`。
- `depends_on`: `ADMIT-040-EVIDENCE-DESIGN-001`
- `allowed_paths`:
  - `src/minekin_core/domain/auth_policy.py` (new immutable policy)
  - `src/minekin_core/adapters/sqlite/session_log.py`
  - `src/minekin_core/cli/session.py`
  - `tests/unit/test_session_start.py`
  - `tests/unit/test_session_supervision.py`
  - `tests/unit/test_session_log.py`
  - `tests/unit/test_auth_policy.py` (new)
  - `tests/unit/test_replay_trace.py`
  - `tests/unit/test_restart_semantics.py` (existing exact event-count/order assertions affected by the new pre-spawn fact)
  - `docs/development-execution-plan.md`
  - `docs/development-todo.md`
- `forbidden_paths`: Bridge/proto、测试域判官/runner/fixture、在线账号适配器、CI。
- `non_goals`: 不实现 Microsoft 认证，不修改受控服务器开关，不称 ADMIT-040 PASS。
- `acceptance`: 受验证 Server Profile 生成不可变离线策略，无目标 run 取默认
  离线策略；实际离线进程规格与账本事件必须使用同一个策略对象；同一 run 中 Core
  在启动客户端前持久写唯一 `AuthPolicyFrozen`（CORE/CORE，profile id/revision、
  generation、offline、adapter disabled），拒绝策略变更或在线 profile；
  旧事件 replay 兼容，单测覆盖重复/越序与不泄露凭据；本地全量门禁通过；
  受控在线认证负向诊断的新 run 真实 ledger 包含上述事件且仍分类
  `AUTH_MODE_MISMATCH`，默认离线正向入服不退化。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `feat(session): freeze offline auth policy in ledger`
- `stop_conditions`: 若同一 run 的策略无法由可信 Profile 与实际启动路径共同
  约束，停止并修正专项契约，不能只写一个自报字段。
- `completion_commit`: `0d7b41e9e7c92400f8bcae303e1c2f2f755a739f`，已推送
  到 `origin/main` 与当前分支，远端 SHA 已核对。
- `completion_evidence`: Core 在进程启动前从同一个不可变 `AuthPolicy` 写唯一
  `AuthPolicyFrozen`（CORE/CORE）；Profile id/revision 与离线策略同源，无在线
  适配器或重绑定路径。全量本地 pytest 1912 passed / 2 skipped，Ruff check/format、
  Pyright、边界、case assertions、fixture digest、workflow pins 与 diff check 通过。
  受控负向 run `f136163a648246f6af0f899f0a71e181` 的服务端 `online-mode=true`，
  ledger 先冻结 offline 策略，后记录 `AUTH_MODE_MISMATCH`，无 JOIN/PLAYABLE；
  正向 run `c3b7d7a3fa684c279627f394613adadb` 的服务端 `online-mode=false`，
  ledger 先冻结策略，后有 JOIN、PLAYABLE 与 1 份准入快照。两次 runner 由停止
  客户端产生退出码 14；未据此宣称正式 case PASS。

### ADMIT-040-CASE-001 — 封存并复判在线认证拒绝用例

- `status`: `DONE`
- `baseline_sha`: `0d7b41e9e7c92400f8bcae303e1c2f2f755a739f`
- `promotion_reason`: 产品可信策略事件已在负/正两条真实运行中核对并推送；
  当前 campaign 的下一阻断项是把同 run 交叉证据封成可复判的正式 case。
- `depends_on`: `AUTH-POLICY-EVENT-001`
- `allowed_paths`:
  - `tools/seal_run_evidence.py`
  - `tools/assert_case_evidence.py`
  - `tools/check_case_assertions.py`
  - `test-orchestrator/runner/domain.sh`
  - `tests/fixtures/cases/admit-040.json` (new)
  - `tests/fixtures/manifest.sha256`
  - `tests/unit/test_case_evidence_assertions.py`
  - `tests/unit/test_seal_run_evidence.py`
  - `tests/contract/test_runner_scripts.py`
  - `docs/development-execution-plan.md`
  - `docs/development-todo.md`
- `forbidden_paths`: 产品认证/连接代码、Bridge/proto、其他 case 的判据、CI。
- `non_goals`: 不把旧诊断 run 升格为正式证据，不以进程数替代策略不可变性，
  不把离线身份接入 `online-mode=true` 服务器。
- `acceptance`: case fixture 只认契约的四项事实；服务端配置与经验证 Profile
  原样作为 sealed artifacts，判官本地及 hermetic rejudge 读同一材料；
  反例变异（服务端实际离线、Profile/revision 不同、缺/改策略事件、在线重绑定、
  额外启动、缺分类）逐个 FAIL；runner 在该拒绝场景等待失败事件而非 PLAYABLE；
  当前 build 真实运行 seal 后 evidence verify、rejudge、适用 replay 与 promotion
  一致，并记录 attempt sequence、bundle digest 和 verdict。完整本地门禁通过。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `feat(evidence): seal ADMIT-040 auth mismatch case`
- `stop_conditions`: 如果 sealed 材料不足以区分上述反例，停止在判据/材料层，
  不用空值或日志字串猜一个 PASS。
- `completion_commit`: `0f9a3fdc49de02ab7ab6da1f7a0132633bad5b26`（判官、封存端、
  fixture 与用例本体），已推送到 `origin/codex/core-state-transition`；本文档的
  状态提交与其后的提升提交一起 fast-forward `origin/main`。
- `completion_evidence`: 判官新增五条同 run 交叉断言并在 `check_case_assertions.py`
  注册（125 条）；封存端读一次经验证 Server Profile 并把原样字节封为
  `trusted/server-profile.json`，与服务端自己写的 `server.properties` 同 bundle 核对。
  反例覆盖：服务端实际离线/没写 online-mode、端口与 motd 不指向该 Profile、缺/双份/
  晚于进程启动的策略事件、非 CORE 归属、`auth_mode` 非 offline、在线适配器未记为禁用、
  profile id/revision 不同或缺摘要、缺分类行、分类归属错、拒绝后再启动、准入快照或
  `PLAYABLE` 冒充本用例，逐条 FAIL（`tests/unit/test_case_evidence_assertions.py`）；
  产品拒收的 Profile 与伪造判决分别由 `test_seal_run_evidence.py` 与 runner 契约钉住。
  **当前 build 的真实受控运行**（kin-01、`online-mode=true`、离线身份）：
  run `6b5856d57dee4052b2ffba3ff9e3459e` / session `fc6fa5cd564b4864b0ee8bcf158aabf4`，
  runner 在 ledger 上等 `AUTH_MODE_MISMATCH` 分类而非 `PLAYABLE`
  （`domain: the session recorded the expected auth mismatch`），随后 `seal` 报
  `result: PASS`、`failures: []`、12 件工件、`attempt_sequence: 1`、
  bundle digest `46565ef26d78106215d996f64870b95bb9a3fb97d653f3d1e7cf0e9c9ef2e736`、
  case version `ec49f61caf2d351969f8ebc61718fa8c64a6af86eb3f238101b06b3bed56c73b`；
  该 run 的文档读数是 `connection_state: FAILED`、`snapshots_admitted: 0`、
  `entities_admitted: 0`、`actions_applied: 0`、`world_snapshot: null`，退出码 14
  仍只是 harness 终止客户端的既有结果。三份独立读数：`minekin evidence verify`
  → `verified: true, sealed: true, artifacts: 12, violations: []`；
  `tools/rejudge_evidence.py` → `status: agrees`（expected/observed/failures/result
  逐项与封存记录相同）；`minekin replay` 与 `tools/replay_evidence.py` → 同一 bundle
  的 14 条事件投影为 `STOPPED`（`last_event_position: 13`，
  trace sha256 `05289911d17d822bb24554aae082b0a844569957410bf95e9312921b81c538dd`）。
  `tools/report_promotion.py --data-root /data` 里这份 bundle 是
  `verified: true, sealed: true, re_judged: AGREES, result: PASS, attempt_sequence: 1,
  from_repository_build: true`，其 `launch_plan_digest` 等于当前 build 的
  `repository_build.plan_sha256`（`7d494810…`）、`bridge_digest` 等于配方 pin 的
  `9a30cdb7…`；整体仍是 `blocked`，W40 的阻塞项只有其余 6 条未登记的 required case 与
  `CORE-020` 的旧 case version，**没有** `EVIDENCE_DISAGREES_WITH_ITS_BYTES`。
  正向回归：同镜像同 build 的 `ADMIT-001` 真实运行 `68b232492bc1474fba1816705164a4d3`
  达到 `PLAYABLE`、首快照准入 1 次，并同样封出 12 件工件（含
  `trusted/server-profile.json`）、verdict `PASS`、bundle digest
  `26da2ed17c3d4c5c5295c4642136c65d437213059f5dddd22874428685625abb`、
  `re_judged: AGREES`——新的封存步骤没有让入服路径退化。
  本地全量门禁：pytest 1948 passed / 2 skipped，Ruff check/format、Pyright 0 errors、
  boundaries、case assertions（125 条注册）、fixture digests、workflow pins 与
  `git diff --check` 通过。未跑 CI。`ADMIT-040` 的
  `mandatory` 仍为 `false`：契约那一层的其余 ADMIT 场景未齐，这一条不点亮任何 gate。
- `next_after_done`: `ADMIT-060-EVIDENCE-DESIGN-001`（campaign `order` 的第 2 个场景）。

### ADMIT-060-EVIDENCE-DESIGN-001 — 冻结资源包拒绝场景的完整判据

- `status`: `DONE`
- `baseline_sha`: `d0a5d9e`（登记本卡的提交；实现判据前以此为准）
- `promotion_reason`: 新卡已先以 `QUEUED` 登记并推送（`d0a5d9e`）。它是
  `REAL-P0-CAMPAIGN-001` 按 `order` 的下一个场景的直接阻断项，且阶段队列里
  其余未闭合的卡都要先由用户拍板（`HOST-ADMISSION-DESIGN-001`、
  `OPERATIONS-RETENTION-001`、`PROCESS-RECOVERY-001` 是 `BLOCKED_DECISION`，
  `HOST/W80+` 是 `DEFERRED`），所以提升它不是插队。
- `depends_on`: `ADMIT-040-CASE-001`（首场景的判据与封存形状在此复用）。
- `why_now`: campaign 首场景现已正式封证。下一项按 `order` 是资源包拒绝
  （`ADMIT-060`），而本文「剩下八条 ADMIT」一节量过它的缺法：**判据只写了一半**。
  「未授权时不 PLAYABLE」有运行材料；「不由聊天同意」在现有 sealed 材料里
  **没有任何承载事实**——`no_lease_was_granted` 说的是「没授 lease」，与
  「授权不是从聊天应答里来的」不是同一句话。harness 那半边已具备
  （`MINEKIN_DOMAIN_RESOURCE_PACK=1`、服务端自造并自发包）。
- `question`: 这一条要证明的两件事各自的**可信来源**是什么，第二件是否需要一个
  最小观测点（客户端对资源包请求的应答及其来源），以及该观测点属产品账本事实
  还是测试域运行材料。
- `allowed_paths`:
  - `docs/p0-remote-admission-contract.md`
  - `docs/development-execution-plan.md`
  - `docs/development-todo.md`
- `forbidden_paths`: 产品代码、测试域判官、case fixtures/registry、runner、proto、CI。
- `non_goals`: 本卡不封 evidence、不改资源包语义、不声称 `ADMIT-060` PASS，
  不把「没进世界」或「没授 lease」当作「不是由聊天同意」的替代证据。
- `acceptance`: 文档把两件事分别写成可观测事实，给每一项指定可信来源、sealed
  artifact、可复判断言与至少一个能揭露假阳性的反例；若某一项现有材料不可证，
  写明需要增加的最小产品/测试域观测点，并生成下一张有精确范围的实现卡。
- `validation_class`: `LOCAL`
- `commit_intent`: `docs(admission): freeze resource pack refusal evidence criteria`
- `stop_conditions`: 如果「授权来源」无法在不泄露资源包内容、不引入在线准入路径的
  前提下归属于同一 run，停在设计缺口并记录，不做容易误报 PASS 的 fixture。
- `design_decision` (2026-09-23): 本用例的拒绝在 login 阶段，判据不要求
  `RESOURCE_PACK_BLOCKED`——受控诊断 run `a114949bf0204a2e8021ec5d02583b4b` 实测两侧
  都没有把这件事说成资源包（run document 停在 `LOGIN_NEGOTIATING`，ledger 只有 Core
  自报的 `SessionInterrupted{outcome:BRIDGE_LOST}`，无 Bridge 过滤后的 `phase=FAILED`
  分类），把一条从未被任何真实运行产生过的事实写进判据等于替产品编答案；是否分类
  另列为产品侧决定。「不由聊天同意」改写为**同意只有一个来源**：profile 的规范化
  `revision` 已含 `resource_pack_policy`，且已由 `AuthPolicyFrozen` 绑定到本 run，
  缺的只有「本 generation 实际放上线缆的那个值」——因此补的观测点必须取自 Bridge
  交付给原版连接路径的 `ServerInfo`（读回），不接受命令回显，否则一个忽略
  `resource_pack_policy` 的构建会产出形状相同的 bundle 并通过。四项同 run 判据、
  sealed 工件、逐一反例与「超时不算拒绝」已写入专项契约；两张精确范围实现卡排队。
- `completion_commit`: `49466dc`（`docs(admission): freeze resource pack refusal evidence
  criteria`），已推送到当前分支与 `origin/main`，远端 SHA 已核对。
- `completion_evidence`: 专项契约新增「ADMIT-060 的可复判证据边界（2026-09-23 冻结）」
  一节：四项同 run 判据各自的来源与 sealed 工件、逐条反例、「超时不算拒绝」、诊断 run
  不追认 PASS 的处置；本文登记两张实现卡并就地更正 ADMIT-060 的缺法一行。文档阶段全量
  本地门禁：pytest 1948 passed / 2 skipped、Ruff check/format、Pyright 0 errors、
  boundaries、case assertions 125 条注册、fixture digests、workflow pins、
  `git diff --check` 通过。未跑 CI，未封存 bundle，除那次诊断运行外没有新的 Minecraft
  场景。
- `next_after_done`: `ADMIT-060-WIRE-POLICY-001`（同一场景缺的那一份产品事实）。

### ADMIT-060-WIRE-POLICY-001 — 让本代连接实际应用的资源包策略成为可信产品事实

- `status`: `DONE`
- `baseline_sha`: `49466dc`（判据冻结的提交；实现以此为准）
- `promotion_reason`: 设计卡 DONE 且已推送，两张实现卡先以 `QUEUED` 登记。产品观测点
  是测试域封存（`ADMIT-060-CASE-001`）的直接前置，也是 campaign 第 2 个场景缺的唯一
  一份产品事实；阶段队列里其余未闭合卡仍需用户先拍板。
- `depends_on`: `ADMIT-060-EVIDENCE-DESIGN-001`
- `shape_decision` (2026-09-23，实施前定): 不新增 observation 消息，在既有
  `ConnectionLifecycle` 上加一个具名字段；Bridge 只在本代**建立连接的那一条**上报
  （`CONNECTION_PHASE_RESOLVING`）里命名它，值取自交付给原版连接路径的 `ServerInfo`
  读回，不是命令回显。Core 对**每一条具名的、且被门接受的**报告写一行账本事实
  （Bridge / BRIDGE_FILTERED），不去重也不聚合——具名两次就是两行，那正是契约
  「同一 run 没有第二个策略值」要读的形状。未具名的报告不写行，因此旧 Bridge 不会
  凭空造出事实。
- `design_decision`（实施时定，回答本卡 `question`）: 取「每条 lifecycle 报告都带一个
  字段」这一支，不新增每 generation 的专门事件。判据两问都成立：一次 run 里同一个策略值
  只出现一次，因为 Bridge 只在 `CONNECTION_PHASE_RESOLVING` 那一具名，两行账本在同一
  `position` 区间里可数；断言按 generation 读到，因为 `ResourcePackPolicyApplied` 的
  payload 就是 `{"generation": N, "resource_pack_policy": "deny"}`，与报告自带的
  generation 同源。专门事件被否掉的实质理由是它承载的信息与「本代那条报告具名与否」完全
  相同，却要多一个消息类型、一道独立的门和一处新的 replay 兼容面。
- `why_now`: 契约第 3 项判据要求「放上线缆的策略」是产品事实，而今天账本里没有任何
  一行承载它。`ConnectWorld.resource_pack_policy` 只存在于 Core→Bridge 的命令方向，
  Bridge 侧唯一使用点是 `ClientAdmissionController` 里 `server.setResourcePackPolicy(...)`
  那一行（写进 `ServerInfo`，没人读回），报回来的 `ConnectionLifecycle` 只有
  `phase`/`failure_reason`/`terminal`。
- `question`: 该事实落在**每条 lifecycle 报告都带一个字段**还是**每 generation 一条
  专门事件**上；本卡实施时二选一并记入 `design_decision`，判据是「一条 run 里同一个
  策略值只出现一次，且能被 `ADMIT-060` 的断言按 generation 读到」。
- `allowed_paths`:
  - `proto/minekin/v1/observation.proto` (one field naming the resource-pack policy the
    Bridge actually applied for this generation)
  - `src/minekin_core/generated/minekin/v1/observation_pb2.py` and
    `observation_pb2.pyi` (regenerated by `tools/generate_protos.py` only)
  - `bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java`
    (read the policy back off the `ServerInfo` handed to the vanilla connection path)
  - `bridge/src/main/java/org/minekin/bridge/runtime/BridgeIpcWorker.java` (lifecycle
    report assembly only)
  - `bridge/src/test/java/org/minekin/bridge/runtime/ClientAdmissionControllerTest.java`
  - `src/minekin_core/adapters/bridge/admission.py`
  - `src/minekin_core/cli/session_runtime.py`
  - `src/minekin_core/cli/session.py` (the recorder that turns one accepted report into
    one ledger row, and the `record_session_event` call site that names its source)
  - `src/minekin_core/adapters/sqlite/session_log.py`
  - `tests/unit/test_bridge_admission.py`
  - `tests/unit/test_generated_protocol.py`
  - `tests/unit/test_schema_golden.py`
  - `tests/unit/test_session_log.py`
  - `tests/unit/test_session_supervision.py`
  - `tests/unit/test_replay.py`
  - `tests/unit/test_replay_trace.py`
  - `tests/unit/test_restart_semantics.py` (existing exact event-count/order assertions
    affected by a new per-generation fact)
  - `tests/unit/test_auth_policy.py` (only if the frozen-policy payload is shared)
  - `tools/check_bridge_proto_java.py` (compile-stub signatures for the changed message)
  - `src/minekin_core/adapters/launcher/recipe.py` (reviewed Bridge JAR/source pins,
    digest and byte size only)
  - `tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json` (Bridge artifact pins only)
  - `tests/fixtures/cases/core-001.json` (bundle recipe input digest only)
  - `tests/fixtures/manifest.sha256` (digest entries for files this card changes)
  - `docs/development-execution-plan.md`
  - `docs/development-todo.md`
- `forbidden_paths`: 测试域判官/封存器/case fixture/runner、账号在线认证路径、资源包
  下载与缓存语义、`AdmissionFailureReason` 枚举扩张、CI。
- `non_goals`: 不把 login 停顿分类成 `RESOURCE_PACK_BLOCKED`（那是契约里记下的单独产品
  决定），不实现 `prompt` 的聊天同意，不改受控服务端的配置生成，不封 `ADMIT-060`
  bundle，也不声称该用例 PASS。
- `acceptance`: Bridge 为一个 generation 建立 `ServerInfo` 后，把**它自己读回的那个**
  资源包策略随该 generation 的连接生命周期报给 Core；Core 以带 Bridge 来源的账本事实
  持久化，同一 run 内该值不出现第二个，payload 只有策略枚举名（无 URL、无摘要、无包
  内容、无服务器文案）；未知/未指定值按现有 admission 门的形状被拒而不是被猜；
  旧 run 的 replay 与 trace 兼容；Bridge Java 针对性测试证明「命令被忽略成另一个值」
  与「命令回显」两种构建给出不同读数；全量本地门禁通过；受控 `deny` 资源包运行的真实
  ledger 出现该事实且值等于冻结 profile 的 `resource_pack_policy`，默认离线正向入服
  不退化。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `feat(session): report the applied resource pack policy`
- `stop_conditions`: 若该值只能靠把 Core 自己发出的命令原样回显得到（Bridge 读不回
  实际应用的值），停止并把结论写回专项契约——自报字段正是本观测点要排除的假阳性，
  不以它冒充线缆事实；若需要新增 `AdmissionFailureReason` 或改动 `prompt` 语义才能
  报出该值，也停止。
- `completion_commit`: `e75b011665a7090dc1c4ac00ede682367c1aae24`（已推送；本地
  HEAD、`origin/codex/core-state-transition` 与 `origin/main` 核对为同一 SHA）
- `completion_evidence`: 两条停止条件都没触发——该值确实由 Bridge 从交给原版连接路径的
  `ServerInfo.getResourcePackPolicy()` 读回（定向 JUnit `thePolicyVanillaConnectsWithIsReportedInItsOwnWireWords`
  钉住 `DISABLED→deny`、`PROMPT→prompt`，即「命令被忽略成另一个值」会报出另一个读数，
  回显则不可能），且没有新增 `AdmissionFailureReason` 成员、没有改 `prompt` 语义。
  全部门禁：1953 passed / 2 skipped（本卡 +5 条），Ruff check+format、Pyright 0 errors、
  boundaries、case assertions 125、fixture digests、workflow pins、`git diff --check`
  与五道 Bridge 静态/协议门全绿；Java 针对性套件在 Linux 容器与本机 JDK 21 各 88 条全绿，
  jar `ecff5a598bda3a5055755cbbf04251d33c464b3764267b7b479917a2a8dce9c7` / 1307584 字节
  两平台逐字节相同，pin 链（`recipe.py` → bundle fixture → `core-001.json` 的
  `input_digests` → `manifest.sha256`）按门逐级 renewal。
  真实受控读数（两条都是**未封存的诊断 run**，不追认 PASS）：
  拒绝侧 run `b1ace69e610c4c04a942281add8bd69b` / session `4a0543d748da41eb8db421eb8455daf3`
  / 服务端 `run-114`（`require-resource-pack=true`、loopback URL、
  `resource-pack-sha1=a351bd3668e6fc47c0c9bb8da95ca6e1fb64638f`），账本 position 899 恰好
  一行 `ResourcePackPolicyApplied`、`BRIDGE`/`BRIDGE_FILTERED`、
  `{"generation":1,"resource_pack_policy":"deny"}`，落在 `READY_MENU→CONNECTING` 之间，
  其后 `CONNECTING→FAILED`；正向侧 run `8516151dab664d8692c3bf7ab3288859` / session
  `9569a9afd046415e84f7d9ff878d9a1c` / `run-115`（`require-resource-pack=false`）同样
  恰好一行（position 913）且值等于冻结 profile 的 `deny`，随后 `JoinObserved` →
  `PlayableEstablished`，`connection_state: PLAYABLE`、`snapshots_admitted: 1`——入服没有
  退化。两条 run 各只有一行该事实，旧诊断 run `a114949bf0204a2e8021ec5d02583b4b`（本卡
  之前的 build）仍是 0 行，没有被凭空补出。旧封存件的兼容用真数据量过：ADMIT-040 的
  bundle `46565ef26d78106215d996f64870b95bb9a3fb97d653f3d1e7cf0e9c9ef2e736` 在新 build 上
  `rejudge` 仍 `agrees`/`PASS`（6/6 观测），`replay evidence` 仍投影出 14 事件、
  末态 `STOPPED`、0 violations。CI 未作为完成证据（本卡只以本地 + Docker 读数收口）。
- `scope_notes`: allowed 路径里 `test_schema_golden.py`、`test_session_log.py`、
  `test_replay.py`、`test_replay_trace.py`、`test_restart_semantics.py`、
  `test_auth_policy.py`、`tools/check_bridge_proto_java.py` 最终无需改动即通过——新事实
  是纯追加，既没动 schema 也没动重启后的事件计数断言；记录于此是因为「允许改」不等于
  「改了」，事后核对范围要看这里。
- `next_after_done`: `ADMIT-060-CASE-001`（拿本卡这份产品事实去封存并复判该场景）。

### ADMIT-060-CASE-001 — 封存并复判资源包拒绝用例

- `status`: `DONE`
- `baseline_sha`: `e75b011`（线缆策略事实落地的提交；封存与断言以此为准）
- `depends_on`: `ADMIT-060-WIRE-POLICY-001`
- `promotion_reason`: 依赖已 DONE 并推送（同一 `ResourcePackPolicyApplied` 事实在两条
  真实受控 run 里各出现一行、值等于冻结 profile，旧封存件 rejudge/replay 读数不变），
  campaign 第 2 个场景自此只缺测试域那半边：`server-resource-packs/` 工件与 `ADMIT-060`
  fixture。停止条件里「产品侧无承载事实」那一支已经不再成立。
- `why_now`: 契约的四项同 run 判据已全部指到具体来源，其中第 1、2、4 项只缺测试域
  的封存与断言：`server.properties` 与 sealed Server Profile 在 `ADMIT-040-CASE-001`
  已经封好并可复用，缺的是客户端 `server-resource-packs/` 目录列表这件新工件，以及
  runner 在资源包场景下不再干等 45 秒的那一条等待分支。
- `allowed_paths`:
  - `tools/assert_case_evidence.py`
  - `tools/seal_run_evidence.py`
  - `tools/check_case_assertions.py`
  - `tests/fixtures/cases/admit-060.json` (new)
  - `tests/fixtures/manifest.sha256`
  - `tests/unit/test_case_evidence_assertions.py`
  - `tests/unit/test_seal_run_evidence.py`
  - `tests/contract/test_runner_scripts.py`
  - `test-orchestrator/runner/domain.sh` (resource-pack scenario wait branch only)
  - `docs/development-execution-plan.md`
  - `docs/development-todo.md`
- `forbidden_paths`: 产品代码、Bridge/proto、case registry 编号、`ADMIT-040` 已有判据
  的语义、CI。
- `non_goals`: 不要求 `RESOURCE_PACK_BLOCKED` 分类，不引入在线准入路径，不把
  `no_lease_was_granted` 或「45 秒没 PLAYABLE」当作拒绝证据，不改资源包语义。
- `acceptance`: sealer 另封本代客户端的 `server-resource-packs/` 目录列表（读一次、
  判与封同字节）；`ADMIT-060` fixture 的断言逐条覆盖契约四项——服务端
  `server.properties` 且 profile 对应、sealed profile 的 `resource_pack_policy` 是本用例
  要求的值且其规范化摘要等于早于进程启动的那条 `AuthPolicyFrozen` 的
  `server_profile_revision`、同一 run 的线缆策略事实与它一致且无第二个值、目录为空
  且无 JOIN/PLAYABLE/快照/lease；每项至少一个反例测试（服务端不要求包、profile 与事件
  不符、线缆值被忽略成 `prompt`、目录里已有包、真的进了世界）必须失败；
  `check_case_assertions --record` 登记新增断言、fixture digest 更新；本地全量门禁通过；
  受控 Docker `deny` 运行产出正式 bundle，`evidence verify`/`rejudge`/`replay`/
  `report_promotion` 四读一致后才写 DONE。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `feat(evidence): seal resource pack refusal case`
- `stop_conditions`: 如果第 3 项在产品侧仍无承载事实（`ADMIT-060-WIRE-POLICY-001` 未
  DONE），不写这条断言、不用「只连过一次」替代；若受控运行只在超时上区分得出，
  停在 `BLOCKED_EVIDENCE` 并记录，不封一个只证明超时的 bundle。

- `completion_commit`: `420bb88277064a5f42b63fa2c1dced70f428204d`
  （`feat(evidence): seal resource pack refusal case`），与其后修掉读侧缺陷的
  `e906e92bcd81c4858224024c07bcdddbde4d58b8`
  （`fix(evidence): read a properties value the way the server wrote it`）。两者均已推送，
  本地 HEAD、跟踪分支与远端 SHA 逐一核对相同。
- `completion_evidence`: sealer 把本代客户端的 `server-resource-packs/` 读一次、封为
  `client/server-resource-packs.json`（name/bytes/sha256，不含包内容），并且**「目录不存在」
  与「目录为空」保持为两个不同答案**（`present:false` → 判官读不出列表 → `NO_CLIENT_PACK_LISTING`；
  `present:true` + `entries:[]` → 判据成立）。四条判据入判官并登记为 `ADMIT-060`（`W40`、
  `mandatory: false`）：服务端自己的 `server.properties` 要求包且 URL 落在
  `AddressPolicy.p0_loopback()`（复用产品的地址策略，不再自造一份 loopback 定义）、sealed
  Server Profile 的 `resource_pack_policy` 等于本用例的 `deny` 且其规范化 `revision` 等于
  进程启动前那条 `AuthPolicyFrozen` 的 `server_profile_revision`、同 run 线缆上的
  `ResourcePackPolicyApplied`（`BRIDGE`/`BRIDGE_FILTERED`）与它相同且**只有一个值**、目录为空
  且无 JOIN/PLAYABLE/快照/lease。反例逐条 FAIL：包需求侧 9 条（不要求包、没提包、无来源、
  无 URL、URL 非 loopback、loopback 只作为他主机 userinfo 出现、sha1 非摘要、端口与 profile
  不符、motd 不点名 profile、在线服冒充），profile 侧 6 条，线缆侧 5 条（含被忽略成 `prompt`
  与出现 `deny,prompt` 两个值），客户端侧 2 条，另加「超时只满足两条否定断言、四项判据全红」
  与 symlink 目录令封存停止。runner 新增 `ADMIT-060` 等待分支：等的是账本里那条 `deny` 策略
  事实，不是 `PLAYABLE`，且没同时给资源包场景与 profile 时直接退出 2。
  本地门禁：pytest **1991 passed / 2 skipped**（本卡 +37 条、读侧修复再 +1 条）、Ruff check/format、
  Pyright 在被改文件 0 errors、boundaries、case assertions 129 条注册且 `--record` 只动新
  fixture、fixture digests、workflow pins、wheel oracle 边界、`bash -n`。
  **真实受控 Docker `deny` 运行**（同镜像、当前 build）：run
  `7bc740ea4cde4e1aaff074bb64850348` / session `79eec2b3078e43f782f7b5ff00defe58` /
  服务端 `run-117`（`require-resource-pack=true`、escaped loopback URL）→ 13 件工件、
  `result: PASS`、`failures: []`、`attempt_sequence: 2`、bundle
  `ca61b64b86b13b0d55528f2f2604825f973c313ba7adaa91fcefe3a2cb29ddcc`。四读一致：
  ① `evidence verify` → `verified: true, sealed: true, artifacts: 13, violations: []`；
  ② `tools/rejudge_evidence.py` → `status: agrees`（6/6 observed）；③ `minekin replay` 与
  `tools/replay_evidence.py` 同一 bundle → 14 事件投影到 `STOPPED`、`violations: []`；
  ④ `tools/report_promotion.py --data-root /data --work-package W40` → 这份是
  `PASS/verified/sealed/re_judged: AGREES/from_repository_build: true`，
  `bridge_digest ecff5a59…` 与配方 pin 相同、`launch_plan_digest 6b81fa7d…` 与当前 build 相同。
  第 1 次尝试 run `3c17aa78a838486391634e69d9f8ea98`（bundle `259cc93d…`）**如实封存为
  `FAIL`**：判据 1 被读侧缺陷误拒（`Properties.store` 把值里的冒号写成 `\:`，本地 fixture
  写的是未转义形状所以从未撞上），该 bundle 在 promotion 报告里仍列 `FAIL` +
  `re_judged: DISAGREES`，`supersedes_run_id` 指向它——不追认、不覆盖。
- `next_after_done`: `ADMIT-070-EVIDENCE-DESIGN-001`（`order` 的第 3 个场景）。

### ADMIT-070-EVIDENCE-DESIGN-001 — 冻结 JOIN 后首快照失败场景的完整判据

- `status`: `DONE`
- `registered`: 2026-09-24（campaign `order` 的第 3 个场景；本卡只排队，判据尚未冻结）
- `promotion_reason`: 依赖 `ADMIT-060-CASE-001` 已 DONE 并推送（真实 `deny` 运行封出
  `PASS`/`AGREES` 的 bundle，四读一致），且它是 `order` 上唯一下一项——其余未闭合的卡都要
  先由用户拍板（`HOST-ADMISSION-DESIGN-001`、`OPERATIONS-RETENTION-001`、
  `PROCESS-RECOVERY-001` 是 `BLOCKED_DECISION`，`HOST/W80+` 是 `DEFERRED`），所以提升它不是插队。
- `depends_on`: `ADMIT-060-CASE-001`（「profile 冻结 + 线缆事实 + 同 run 运行材料」这一
  封存形状在此复用）。
- `why_now`: `order` 的前两个场景（在线认证拒绝、资源包拒绝）已各自正式封证。第三个
  「首快照负向」在契约里点名的是 `ADMIT-070`（「JOIN 后首快照失败 ｜ 不授 lease；
  generation 终止」），其 fixture `tests/fixtures/cases/admit-070.json`（`W50`，契约注记
  写明五条断言）已经存在，且那句注记自己写着「JOIN 后」那一半属运行材料。缺的不是编号
  也不是断言名字，是把那五条逐条指到**一次真实拒绝运行**的可信来源。
- `question`: 一次「JOIN 之后、首个权威快照被拒」的运行在现有材料里说得出什么——run
  document 已有的 `snapshot_rejections` 与 `entities_rejected`、账本的
  `SessionInterrupted`，是否足以把「不授 lease」与「generation 终止」说成同一 run 的
  事实；要让**首**快照真的失败，需要的是服务端工具的一个新 knob、Bridge 的一个新上报，
  还是两者都不必（现有 `MINEKIN_DOMAIN_SILENCE` 与 probe 那两条形状够不够）；若不必，
  这条判据与 `ADMIT-110` 的有界放弃之间怎么分界。
- `allowed_paths`:
  - `docs/p0-remote-admission-contract.md`
  - `docs/development-execution-plan.md`
  - `docs/development-todo.md`
- `forbidden_paths`: 产品代码、测试域判官、case fixtures/registry、runner、proto、CI。
- `non_goals`: 不封 evidence、不改快照语义、不声称 `ADMIT-070` PASS，不把「45 秒没
  PLAYABLE」或「没进世界」当作「首快照被拒」的替代证据。
- `acceptance`: 五条断言逐条写成可观测事实，各指定可信来源与 sealed 工件，每项至少一个
  能揭露假阳性的反例；明确该场景是否需要新的产品观测点或 runner knob——需要则生成精确
  范围的实现卡，不需要则写明现有材料为什么足够。
- `validation_class`: `LOCAL`
- `commit_intent`: `docs(admission): freeze first-snapshot refusal evidence criteria`
- `stop_conditions`: 如果「首快照被拒」在现有运行材料里只能由超时读出（没有任何一层记下
  被拒的那一份快照），停在 `BLOCKED_EVIDENCE` 并记录，不把 `snapshot_rejections` 那个空
  数组读成拒绝。

- `completion_commit`: `a7983c39599852c1a1c59423ce9eb67db07d417c`
  （`docs(admission): freeze first-snapshot refusal evidence criteria`），已推送，本地 HEAD、
  跟踪分支与远端 SHA 核对相同。
- `completion_evidence`: 专项契约新增「ADMIT-070 的可复判证据边界（2026-09-24 冻结）」一节，
  把 `tests/fixtures/cases/admit-070.json` 那五条断言（**全部登记为 `pytest` 类**，
  `tools/check_case_assertions.py:476-495`）逐条写成一次真实拒绝运行里的五项事实，各指名来源与
  sealed 工件：`JoinObserved`（BRIDGE/BRIDGE_FILTERED，`cli/session.py:135`）在场而
  `connection_state` 非 `PLAYABLE`；`run-document.json` 的 `snapshot_rejections` 里出现**本用例
  点名的那一个** `SnapshotReason`（不接受「非空即可」）且 `snapshots_admitted: 0`；无
  `InputLeaseGranted`（复用 `no_lease_was_granted`）与无 `PlayableEstablished`；本代终止且其后
  不再进 `JOIN_SEEN`/`PLAYABLE`；判官不得要求文档里没有的正文（`IntegrityViolation` 不落文档），
  也不得把客户端那行 warn 当被拒事实。反例逐条指名了要判红的判据：只有超时
  （`connection_cancelled: "TIMEOUT"`，即 `ADMIT-110` 已在读的那次运行）、并集字段说得出「拒过
  一份」而说不出「首份被拒」（`snapshots_admitted ≥ 1`）、`entities_rejected` 非零（实体闸门不是
  快照闸门）、没有 `JoinObserved`、出现过 lease 或 PLAYABLE、之后又起新 generation 进了世界、
  以及字段缺失/类型不对时读作不可判定而不当空数组。
  **需要新观测点这一问有确定答案**：需要，且在 Bridge 上报侧。五个理由逐条量过来源——
  `authoritative` 写死 `true`（`ClientSnapshot.java:80`）、`generation` 回的就是 Core 发给
  `ConnectWorld` 的那个值（`ClientAdmissionController.java:250`）、session 身份两端同源
  （`ClientSnapshot.java:56-59,84` 对 `offline_session.py:247,255-275`，比较只看 username 与
  规范化 uuid）、self/inventory 全取活客户端状态且 revision 为
  `Math.max(1, world.getTime())`（`ClientSnapshot.java:66,119`）；关键是 Bridge 说不出自己是谁时
  **不发**而不是发一份残缺的（`ClientSnapshot.java:52-60` +
  `ClientAdmissionController.java:249-253` 的一行 warn），所以本地靠伪造 IPC 钉住的那两条在真实
  客户端上没有对应形状。现存 knob 逐条排除（`domain.sh:18-129` 的 `MINEKIN_DOMAIN_*`、
  `run_controlled_server.py` 的世界/白名单/线缆 flag、`MINEKIN_DOMAIN_SILENCE` 停的是 Core、
  `tools/fault_injection.py:46-49` 只会让一个进程消失）。实测读数：数据卷 36 份真实运行文档
  `snapshot_rejections` 全为 `[]`，同批里 `connection_cancelled: "TIMEOUT"` 3 次、
  `entities_rejected` 非零 1 次——写理由的那一层会工作，没发生过的是被拒本身。
  顺带量到 `FIRST_SNAPSHOT_TIMEOUT` 与 `WORLD_BINDING_MISMATCH` 在 proto 里有枚举值
  （`observation.proto:35-36`）而**没有任何一层发出**，故判据不要求它们，与 `ADMIT-060` 拒绝
  `RESOURCE_PACK_BLOCKED` 同形。`tests/contract/test_case_coverage.py` 4 passed；
  `git diff --check` clean。本卡未跑全量门禁（只改文档，未动码、夹具或判官）。
- `next_after_done`: `ADMIT-070-REFUSAL-INJECTION-001`（本卡判据所要求的注入点；登记为
  `QUEUED`，提升与否由主控决定）。第 3 个场景在其落地并跑出一条真实拒绝运行之前停在
  `BLOCKED_EVIDENCE`。封那条 bundle 时还需补一件本卡只记名的要求：**注入必须在 bundle 里说得出来**
  （现有 `fault-injection.json` 通道是唯一合适的地方），否则一份 PASS 分不清「Core 拒了一份自称
  非权威的快照」与「客户端真的发了这么一份」。

### ADMIT-070-REFUSAL-INJECTION-001 — 让首快照能被报成 Core 会拒的样子

- `status`: `NEXT`
- `baseline_sha`: `a9448ecf8d7345e54d04b3f9218db7b327c3b9a1`
- `registered`: 2026-09-24（由 `ADMIT-070-EVIDENCE-DESIGN-001` 冻结的判据指名需要；登记时为 `QUEUED`）
- `promotion_reason`: 运行者 2026-09-24 明确选择「实现注入点（Bridge 改动）」，并在提升前量过本卡
  `question` 的前半：客户端环境是封闭的，`bootstrap.py:121` 把 `config.forwarded_environment()` 交给
  `client_environment(forward=…)`，而那份清单就是 `config.py:37` 的 `FORWARDED_VARIABLES`；Bridge 侧
  已有 `System.getenv` 读 `MINEKIN_BRIDGE_DESCRIPTOR` 的先例（`MinekinBridgeClient.java:30,41`）。
  因此开关能走环境变量，`stop_conditions` 里「只能靠 `control.proto` 新命令」那一支不成立，本卡
  可执行。
- `scope_amendment`: 由上面那次读数得出——env 继承**不需要**改
  `src/minekin_core/adapters/launcher/process.py`（它原样转发清单里的名字），需要的是把变量名放进
  `src/minekin_core/config.py` 的 `FORWARDED_VARIABLES`。该文件因此进入 `allowed_paths`，而
  `process.py` 那一条按自身条件（「仅当需要显式放行时」）保持不动。
- `depends_on`: `ADMIT-070-EVIDENCE-DESIGN-001`（判据、反例与「只有 `NOT_AUTHORITATIVE` 在范围内」
  的取舍都在那一节里）。
- `question`: 一个默认关断的开关怎么从 runner 走到 Bridge——客户端 JVM 的环境变量能否由受控
  runner 设、被 `adapters/launcher/process.py` 原样继承给子进程、再由 Bridge 读到（这样 Core 不必
  新增任何概念）；还是必须走 `control.proto` 的一条命令（那是协议扩张，本卡不承担）。以及这份
  注入怎么在 bundle 里说得出自己：`fault-injection.json` 现在的记录形状容不容得下一类
  「Bridge 被要求这样上报」的事实。
- `why_now`: campaign `order` 第 3 个场景的唯一阻塞项。`execution_steps` 第 2 条本来就要求「先补足
  scenario 所需的 runner knob」，而这一个 knob 现有材料里一个都不够（判据卡的读数记录逐条排除了）。
- `allowed_paths`:
  - `bridge/src/main/java/org/minekin/bridge/runtime/ClientSnapshot.java`（`authoritative` 由
    入参决定，默认仍为 `true`）
  - `bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java`（读那个开关，
    且只在被明确要求时对**本代第一份**快照生效）
  - `bridge/src/test/java/org/minekin/bridge/runtime/ClientAdmissionControllerTest.java`
  - `src/minekin_core/adapters/launcher/process.py`（仅当环境变量继承需要显式放行时）
  - `src/minekin_core/config.py`（`FORWARDED_VARIABLES` 是宿主 → 客户端 JVM 的唯一清单；见
    `scope_amendment`）
  - `tests/unit/test_init.py`（只为该清单补一条定向断言，不动其他 config 语义）
  - `tools/fault_injection.py` 与 `tools/inject_fault.py`（记录类别，不改既有三种进程角色语义）
  - `test-orchestrator/runner/domain.sh` 与 `test-orchestrator/runner/run.sh`（把开关传给一个场景）
  - `src/minekin_core/adapters/launcher/recipe.py`、
    `tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json`、`tests/fixtures/cases/core-001.json`、
    `tests/fixtures/manifest.sha256`（Bridge 变更后重算并续期这些 pin）
  - `tools/check_bridge_proto_java.py`（只同步编译桩的方法签名）
  - `docs/development-execution-plan.md`、`docs/development-todo.md`
- `forbidden_paths`: `proto/` 与生成物、`src/minekin_core/domain/perception.py` 的判定语义、
  `RecordedSessionMaterial` 的构造（不许让记录说谎）、case fixtures 与 assertions registry、
  判官、CI 配置。
- `non_goals`: 不封 `ADMIT-070` 的 evidence（那是后续的 `ADMIT-070-CASE-001`）、不注入
  `SESSION_MATERIAL_MISMATCH`/`SELF_STATE_INCOHERENT`/`INVENTORY_INVALID`/`GENERATION_MISMATCH`
  四个理由、不引入新的 `SnapshotReason`、不声称任何真实客户端会自发非权威快照。
- `acceptance`: 开关默认关；未设开关时一次真实受控运行的第一份快照仍 `authoritative=true` 并照常
  放行（正向不回归）；设了开关时 Core 的 `snapshot_rejections` 里出现 `NOT_AUTHORITATIVE` 且
  `snapshots_admitted: 0`、账本无 `PlayableEstablished`/`InputLeaseGranted`；注入这一事实能从同一
  bundle 的 `fault-injection.json` 读出来；Java 定向测试 + 全量本地门禁 + 受审 pin 续期全绿；
  一次真实受控 Docker 运行产出上述两份材料（正向与注入）并只作诊断，不封 bundle。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `feat(bridge): allow an explicitly requested non-authoritative first snapshot`
- `stop_conditions`: 若开关只能靠 `control.proto` 的一条新命令到达 Bridge，或注入无法在同一 bundle
  里说出自己（`fault-injection.json` 装不下这类事实且没有别的测试域通道），停在该卡并把第 3 个
  场景继续留在 `BLOCKED_EVIDENCE`——不得为了跑得出证据而把一条产品事件写成客户端没有的样子。

### ADMIT-040-CLASSIFICATION-001 — 识别原版在线认证拒绝的真实文案

- `status`: `DONE`
- `baseline_sha`: `63bf428e4d78dbb38c9bbf38be2f8fc5c55054dd`
- `promotion_reason`: 新卡已先以 `QUEUED` 登记并推送；这是阻断当前唯一
  campaign 首个场景的真实分类回归，按“更高优先级回归”规则提升为 `NEXT`。
- `why_now`: 上述真实诊断已证明 Bridge 把 `Invalid session` 错报为普通断线，
  直接阻断 `REAL-P0-CAMPAIGN-001` 的第一个场景。此卡作为回归修复插队；
  先登记为 `QUEUED`，由主控在基线与范围核对后提升为唯一 `NEXT`。
- `allowed_paths`:
  - `bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java`
  - `bridge/src/test/java/org/minekin/bridge/runtime/ClientAdmissionControllerTest.java`
  - `bridge/src/main/java/org/minekin/bridge/mixin/LoginDisconnectMixin.java`
  - `bridge/src/main/java/org/minekin/bridge/MinekinBridgeClient.java` (login disconnect
    event wiring and client tick only)
  - `tools/check_bridge_proto_java.py` (ClientAdmissionController compile stub
    method signatures only)
  - `src/minekin_core/adapters/launcher/recipe.py` (Bridge JAR SHA-256 and byte size only)
  - `tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json` (Bridge artifact SHA-256,
    byte size and source tree digest only)
  - `tests/fixtures/cases/core-001.json` (bundle recipe input digest only)
  - `tests/fixtures/manifest.sha256` (changed fixture digest entries only)
  - `docs/development-execution-plan.md`
  - `docs/development-todo.md`
- `forbidden_paths`: protobuf/枚举及生成物、其他 mixin、runner、
  case registry/assertions、CI 配置及无关生产代码。
- `non_goals`: 不改变默认离线身份策略，不绕过在线认证，不自动启用账号适配器，
  不伪造 ADMIT-040 的正式 PASS；该 case 的后半判据与 fixture 仍需单独冻结。
- `acceptance`: `Invalid session` 的真实客户端拒绝文案归入 `AUTH_MODE_MISMATCH`；
  未知文案仍归入 `UNEXPECTED_DISCONNECT`；Java 针对性测试与本地全量门禁通过；
  更新源码和 JAR 的受审 pin（只取当前重建产物），保持配方验证通过；
  重新构建的受控 Docker 在线认证负向运行在 Core ledger 中记录 `AUTH_MODE_MISMATCH`；
  正常离线身份对离线服仍可 JOIN、产生首快照。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `fix(admission): classify vanilla invalid-session refusal`
- `stop_conditions`: 若真实断线理由不再包含可辨识的认证文案，或修复需要协议/策略
  扩张，则停止并更新契约，不作宽泛的字符串猜测。
- `scope_amendment` (2026-09-23): 首次 Bridge 全量 Java 门禁通过后，Python 全量
  pytest 有 140 个失败，首个 trace 为 `Bridge source tree digest differs from the
  bundle recipe`。这些测试共用受审配方；Bridge 源码变更必须重算源码/JAR pin，原卡
  漏列了两个 pin 文件。更新配方后，`pytest -x` 又准确显示 `CORE-001` 的配方输入
  digest 不匹配；冻结 fixture 清单也绑定配方和 CORE-001。新增两个精确 pin 路径；
  只开放上述字段，不扩大认证行为或 case 判据。
- `runtime_root_cause` (2026-09-23): 重建的 overlay JAR SHA-256 与新 pin 一致，
  但受控复跑 `5fdf18637dd2482f95b031f94d52c4c7` 仍报 `UNEXPECTED_DISCONNECT`。
  同一客户端日志中，网络线程先写 `bridge classified the login failure as
  ...UNEXPECTED_DISCONNECT`，渲染线程随后写 `bridge observed a login disconnect:
  Failed to log in: Invalid session ...`；没有 `onDisconnect ... from the server`
  的 packet-hook 记录。故分类器已有文案也来不及使用。开放上述两个精确 wiring
  文件，须把 Fabric login DISCONNECT 与 vanilla `onDisconnected` 的同一 handler
  关联后再报终态；旧 handler 晚到不得污染新 generation。重新构建后重算全部 pin。
- `compile_stub_amendment` (2026-09-23): Gradle 15/15 门禁和真实 Docker 正/负
  场景已通过；独立的 `check_bridge_proto_java.py` 因其手写 Controller API stub
  缺少三个新方法而编译失败。只同步该 stub 的方法签名，保持独立编译门禁有效。
- `completion_commit`: `dd992b1fb2a85d8220e9345cfd7844a8f6c2f255`，已推送到
  `origin/main` 与当前分支，远端 SHA 已核对。
- `completion_evidence`: 定向 JUnit 先因缺少 handler 交接方法编译失败，修复后通过；
  Gradle `check --rerun-tasks` 使用 JDK 21.0.12.1，15/15 执行、`BUILD SUCCESSFUL`；
  全量 pytest 1903 passed / 2 skipped，Ruff check/format、Pyright 0、boundaries、
  120 条 case assertions、fixture digest、workflow pins、四道 Bridge 独立门禁均通过。
  真实 Docker 负向 run `fbb9d4787a3743afa868a804c3c586ec` 的 Core ledger 记录
  `AUTH_MODE_MISMATCH`；默认离线正向 run `5507cb8b92e848a6a3b36aece7872840`
  的受控服务端 `online-mode=false`，服务端记录 Kin JOIN，Core 记录
  `PlayableEstablished` 且首快照准入 1 次；白名单负向 run
  `cc2cfb7f69554f0989dbea695938a194` 保持 `WHITELIST_REJECTED`。
  三次 runner 均在停掉承载 Bridge 的客户端时以既有 `BRIDGE_LOST`/exit 14 结束；
  分类证据来自退出后的持久 ledger。未运行 CI，未把诊断运行写作正式 ADMIT-040 PASS。

### HOST-ADMISSION-DESIGN-001 — 宿主世界会话坐标来源

- `status`: `BLOCKED_DECISION`
- `question`: host generation / `WorldCapsule` 由谁创建，Bridge 与 Core 如何绑定
  一个不是 `ConnectWorld` 发起的世界。
- `constraint`: 不得给运行时凭空造 capsule，也不得让 Bridge 自报可信管理事实。
- `unblock_condition`: 冻结决策，并准备 HOST-001 的真实 trace 验收方案。

### OPERATIONS-RETENTION-001 — marker 与 run 目录清理

- `status`: `BLOCKED_DECISION`
- `question`: 保留期、容量上限、审计价值、活跃/未决 run 保护与恢复方式。
- `constraint`: 自动清理不得删除无法证明已终止或仍参与恢复/证据链的记录。

### EVIDENCE-SEQUENCE-001 — 最新 evidence 与 supersession

- `status`: `DONE`
- `question`: Registry 如何分配单调 `attempt_sequence`，如何记录 supersession，
  旧 bundle 如何兼容。
- `constraint`: 不得按 mtime、目录名或 wall clock 猜“最新”。
- `finding`（2026-09-23，读代码量出来的，不是设计）：**晋级今天完全不问证据出自哪个
  build。** `evaluate_promotion` 逐份候选只比 case 身份、case version、是否
  verified、是否 PASS、re-judge 是否同意——`launch_plan_digest` / `bridge_digest`
  只在**一次运行内部**被比较（`BridgeHello` 对 descriptor），**没有任何地方**把它
  与「当前 build」比。后果：一次**修复之前**封的 PASS，会满足**今天磁盘上这个
  build** 的门禁；这与验证契约自己的重跑规则（失败保留、修复后用新 build 重跑）和
  `REAL-P0-CAMPAIGN-001` 的验收句（「**当前 build** 与当前 case version 的 sealed
  bundle」）都相反。**已经做掉的那一半**：`tools/report_promotion.py` 现在逐份
  bundle 报出 `launch_plan_digest`、`bridge_digest` 与 `from_repository_build`，并
  列出 `from_another_build` 的 run id——**这是诊断，不是门禁**，文档里明写
  `gates_promotion: false`，而且有一条用例断言「同一次读数下，来自另一个 build 的
  PASS 与来自当前 build 的 PASS 得到**同一份判决**」。（`plan_sha256` 与路径无关，
  这一点是**量过**的：仓库里与一份拷贝到别处的树算出来同一个 digest。）
- `decision`（主控按执行者授权冻结；后续可由用户明确推翻）：选择**乙，按单调序号 supersession**。两条路都说得通，代价不同——
  **（甲）按 build 绑定**：证据必须来自当前 build，否则 `EVIDENCE_FROM_ANOTHER_BUILD`
  拦截。它直接实现那句验收话，但会让**每一次** Bridge/recipe 改动作废**全部**已有
  证据（包括那些与改动无关的 case），代价是每次改 Bridge 都要重跑一整轮。
  **（乙）按单调序号 supersession**：封存端为该 case 分配 `attempt_sequence`（= 同
  case 已有最大值 + 1，无时钟、无目录名），并显式记录它取代哪一份；promotion 只认
  序号最大的那一份。它更接近这张卡原本的措辞，也让「修复后重跑」自然生效，但需要
  回答「最大那份是 FAIL 时该不该挡住一份更早的 PASS」（我倾向**该挡**，否则重跑没
  有意义），而那正是**语义改动**。
  **冻结语义**：封存端基于同 case 现有最大序号分配 `attempt_sequence = max + 1`
  （首份为 1），写入被新 bundle 取代的先前 bundle 标识；promotion 只评估当前最高序号。
  若最新 attempt 是 FAIL、unverified、缺失或结构损坏，旧 PASS 不得回退满足门禁；这保留
  “修复后重跑”的意义。序号按 case 独立、在同一个封存原子操作中分配并写入；并发封存
  必须冲突失败/重试，不能分配重复序号。attempt registry 先持久化 `PENDING` reservation，
  bundle 完整原子发布后才标为 `SEALED`；中间崩溃让 pending attempt 保持最高并阻断旧 PASS，
  后续 retry 另领更高序号。旧 bundle 无序号时，仅在该 case 尚无 sequenced attempt 时按
  既有 any-satisfying 规则兼容；一旦有新 attempt，legacy 证据即被 supersede。不得用 mtime、
  目录名或 wall clock 推导先后。
  **为何冻结乙**：它不因不相关 Bridge/recipe 改动废弃全部 case 证据，并且直接支持
  “失败后重跑，最新失败阻断旧 PASS”这一既有验收意图。
- `scope`: implement the frozen sequencing decision above; do not add build binding or infer ordering from timestamps/paths.
- `implementation_scope`: add one SQLite attempt registry at the supplied evidence data root, shared by repository and Kin bundle producers; use `BEGIN IMMEDIATE` to assign per-case monotonic sequence and explicit `supersedes_run_id`; persist a `PENDING` reservation before touching bundle output, then mark `SEALED` only after a complete bundle is atomically published. A pending latest row is a blocking attempt (never fall back); later retry receives a higher sequence and explicitly supersedes it. Promotion cross-checks registry rows against addressed bundle manifests, and any missing registry for sequenced bundles, duplicate/gapped/conflicting chain, path collision, unreadable/corrupt latest attempt, or registry/bundle disagreement fails closed for that case. Legacy manifests with no sequence retain the existing any-satisfying-bundle behavior only until a sequenced attempt exists for that case; after that, legacy bundles cannot satisfy it. No timestamp/path ordering and no in-place rewrite of sealed legacy bundles.
- `allowed_paths`:
  - `src/minekin_core/domain/evidence.py` (typed optional attempt fields and validation)
  - `src/minekin_core/adapters/evidence/attempt_registry.py` (new SQLite state machine)
  - `src/minekin_core/adapters/evidence/bundle.py` (atomic publication support)
  - `src/minekin_core/adapters/evidence/promotion.py`
  - `src/minekin_core/cli/evidence.py` (data-root registry location)
  - `tools/seal_run_evidence.py`, `tools/seal_repo_case.py`, `tools/report_promotion.py`
  - focused evidence, registry, promotion, sealing and report tests
  - this plan and `development-todo.md` status only
- `forbidden_paths`: Bridge/proto/generated/runtime lifecycle; changes to assertion meaning, case versions, build-binding policy, EULA/runtime execution; migration or rewrite of existing sealed bundles; unrelated retention/recovery/host decisions.
- `acceptance`:
  1. sequential and concurrent sealers on the same case receive unique monotonic sequences; different cases sequence independently; explicit supersession chain is validated;
  2. crash/failure injection at reservation, bundle staging/publication, and registry completion never allows an older PASS to satisfy behind a newer pending/failed/corrupt attempt; retry gets a new higher sequence;
  3. promotion only evaluates the highest registered attempt per mandatory case; wrong case/run/sequence, duplicate sequence, missing bundle, unreadable latest, or manifest/index mismatch blocks; legacy bundles preserve prior behavior only when no sequenced attempt exists;
  4. verified latest PASS promotes; latest FAIL, INCOMPLETE, unverified, or corrupt latest blocks even if an older PASS exists. `UNJUDGED` remains diagnostic only, matching the existing evidence contract (it is a reader limitation, not contradictory evidence); old bundles are byte-for-byte unchanged;
  5. existing evidence verify/rejudge/replay and all local gates pass; add no runtime requirement.
- `validation_class`: `LOCAL`
- `commit_intent`: `feat(evidence): sequence and supersede case attempts`
- `stop_conditions`: if safe atomic bundle publication or an unambiguous shared data-root registry cannot be implemented without broad changes to evidence-root layout, stop and report before editing outside this allowlist.
- `completion_evidence`（仅诊断那半）：`tools/report_promotion.py` 与
  `tests/unit/test_report_promotion.py`；全量 pytest 1833 passed / 2 skipped，
  Ruff、Pyright、boundaries、case assertions、fixture digests、workflow pins 与
  `git diff --check` 全绿；两处变异各自驱动到红（把比较恒真 → 两条用例红；**让诊断
  去 gate** → 13 条用例红，正好证明这棵树期待 promotion 语义不变）。
- `completion_commit`: `488f0ba1ff256024134b3410caa6a58bbf3e68fa` (pushed to `origin/main`; remote SHA verified)
- `completion_evidence`: full pytest 1901 passed / 2 skipped; latest targeted suite 83 passed after final read-only registry hardening; Ruff check/format, Pyright, boundaries, 120 case assertions, fixture digests, workflow pins, CORE-001 runner case 5/5 and `git diff --check` passed. No CI or Minecraft run.
- `next_after_done`: `CORE-STATE-TRANSITION-001`

### PROCESS-RECOVERY-001 — 残留进程的自动处置

- `status`: `BLOCKED_DECISION`
- `question`: 自动接管、自动终止还是继续人工阻断。
- `constraint`: 只有能证明 pid/start-time/argv 身份与本 run 归属时才允许自动动作。
- `unblock_condition`: 受控 runner 上取得真实残留事件流，并冻结策略。

### HOST/W80+

- `status`: `DEFERRED`
- `scope`: HOST 专题真实运行、`p0-nav-exp`、生存底座、PlayerMind、P2–P4 与扩展。
- `unblock_condition`: P0 core promotion 有完整证据，且主控显式提升对应任务卡。

## 已知缺失 case（规划视图）

这张表是规划输入，不是 required-case inventory 的实现；`PLAN-COVERAGE-001`
完成后以机器报告为准。**当前实现候选**的 `tools/report_cases.py` 的
`requirements` 段与下表逐族一致（同为 35 条缺失），但由机器读出、按 gate 组织，
并额外区分每条要求的是 `local-only` 还是 `runtime-required`。**这张表没有那种区分，
而它曾经因此把人带偏**：表里 `HOSTCTL` 行的 `060` 与其余各行看不出差别，机器读数里
它是唯一一条 `local-only`——也就是唯一一条不需要真实运行就能补上的。**要看某一族
缺的是不是本地能补的，读 inventory 的 `validation_class`，不要读这张表。**

| 族 | 当前 contract 要求但 fixture 缺失 |
| --- | --- |
| CORE | 080 |
| ADMIT | 010, 020, 030, 050, 060, 090, 120 |
| OFFLINE | 010, 020, 030, 060, 070, 080, 090, 100 |
| HOST | 001, 090, 100 |
| HOSTCTL | 020, 030, 040, 080, 090 |
| HOSTCOMMIT | 001, 010, 020, 030, 040, 050, 060, 070, 080, 100 |
| NAV | NAV-EXP-010 |

其中很多必须真实运行；“缺 fixture”不等于“可以用本地测试补成完成”。

### 剩下八条 ADMIT：逐条缺什么（2026-09-23 的读数，可重推）

**2026-09-23 第二次更新：这一节写下后，`ADMIT-040` 已经按它自己的路径闭合**
（判据设计 → 产品可信事件 → 正式 case），所以「八条」今天读作**七条**；下表那一行
已就地更正，其余七行的缺法未变。**这一节仍有价值的地方是它把「缺断言」与「缺事实」
分成两类**——`ADMIT-060` 卡过的正是后一类，而第三次更新（判据冻结）已把那条缺的事实
点名到具体线缆字段，见下表该行与 `ADMIT-060-WIRE-POLICY-001`。

登记 `ADMIT-001` 时把「其余八条能不能照做」逐条查了一遍。判据来源是两处：契约
`docs/p0-remote-admission-contract.md` 的「必须证明」列，以及本仓库**现有 42 条 `runtime`
断言**（`check_case_assertions.IMPLEMENTATIONS` 里 kind 为 `runtime` 的那些，用一条命令可列全）。

**2026-09-23 更正：这八条不是同一种缺法，而分成两类，代价差一个数量级。**
**（甲）事实记了、只是没人断言**——只要在测试域写断言，不需要动产品：`ADMIT-030`/`040`/`050`
要的分类住在账本行的 **`reason`** 字段里（`on_connection` 写的 payload 是
`{"phase": …, "reason": …}`，注释写明那 `reason` 就是「Bridge 的稳定分类」），
`the_refusal_was_classified_in_the_ledger` 正是读它，只是**把值写死成了 `WHITELIST_REJECTED`**——但其中两条按现编号写不出来，见本节末尾；
`ADMIT-060` 的「没授 lease」由 `no_lease_was_granted` 承担。
**（乙）事实根本没记**——那就不是写断言，而是要决定**一次运行必须多记什么**，属产品改动：
`ADMIT-010`/`020` 要的「连了哪个 profile / 解析到什么 endpoint」**在线缆上是有的**
（`session.py` 把 `server_profile_id` 与 `revision` 放进 `ConnectionLifecycle`），
**但 Core 写进账本的那一行只剩 `phase` 与 `reason`**，profile 在这一步被丢掉了；
`ADMIT-090` 要的「人格没被重建」在账本**现有的十个事件类型**里没有任何一个承载；
`ADMIT-120` 要的 canary containment 在运行材料里没有来源。
**2026-09-23 第二次更正：（甲）那三条里，两条按现在的编号写不出来。** `ADMIT-030` 的
「必须证明」是「**三类**失败分类不同且无无限重试」（无 DNS、拒绝连接、超时），`ADMIT-050` 是
「白名单/封禁/**重名**」——**两条各自把三个互斥场景塞进一个 case id**。而 promotion 对一个
case id 是 **any-satisfying-bundle**：读 `evaluate_promotion` 可见，第一份满足的候选就把该 case
判为满足。后果与契约自己为 `CORE-060` 写下的一模一样：**「既不可能由一份 bundle 满足，也不能
保证每种故障各有一份」**——一份只跑了「连接被拒」的 bundle 会让整条用例读起来是覆盖的，而
「三类分类不同」从来没被证明过。契约对 `CORE-060` 的处置是**按边界拆成独立 case id**
（`CORE-060` / `-CLIENT-001` / `-SERVER-001`），而**那个拆法是契约自己的注记授权的**。
`ADMIT-030`/`050` **没有任何这样的注记**，所以拆它们等于**改契约的编号**——这是 inventory 的
编号从哪来决定的：`domain/cases.py` 的清单逐条引用契约，凭空加号就是它一直拒绝做的事。
**因此这两条今天的状态不是「可以开工」，而是「先要有契约层面的拆分决定」。**
`ADMIT-040` 是这三条里**唯一单场景**的（online-mode 目标 + offline 身份），前半是转写
（契约点名 `AUTH_MODE_MISMATCH`）；**后半「不自动启用账号适配器」仍缺判据**——「只尝试了一次」
是个**代理**（账本里 `SessionInterrupted` 的条数可以数），而代理正是这里不该悄悄选的东西。

**这个区分是一次差点写错的更正的产物**：我一度以为 (乙) 里的 profile 是「记了没断言」，
因为线缆上确实有它——查到 `on_connection` 的 payload 才发现它止步于账本那一行。

| case | 契约的「必须证明」 | 现有断言 | 缺什么 |
| --- | --- | --- | --- |
| ADMIT-010 | 不扫描局域网；只连已保存 profile | 无 | **（乙）**线缆上每个 `ConnectionLifecycle` 都带 `server_profile_id`，但账本那一行只剩 `phase`/`reason`——profile 在写账本时被丢掉 |
| ADMIT-020 | 保存原始地址与实际 endpoint；重定向仍过策略 | 无 | **（乙）**同上，且 SRV 解析结果在任何一层都没有记录 |
| ADMIT-030 | 三类失败分类不同且无无限重试 | **部分**：`the_attempt_was_abandoned_at_its_deadline` 管「有界」（由 `ADMIT-110` 认领） | **（甲）**三个分类**都在账本的 `reason` 里**，缺的是断言——现有那条把值写死了 |
| ADMIT-040 | 明确 AUTH_MODE_MISMATCH；不自动启用账号适配器 | ~~一半：`no_world_was_joined` 能说「没进世界」~~ **2026-09-23 已闭合**：前半是 `the_auth_mode_mismatch_was_classified_in_the_ledger`，后半由 `AuthPolicyFrozen`（CORE/CORE，进程启动前）+ 两条「拒绝后只有一份策略、一次启动」的断言承担 | 无——见 `ADMIT-040-CASE-001` 的 `completion_evidence`。「只启动一个进程」仍然不是证据，它只是同 bundle 里的一个附带事实 |
| ADMIT-050 | 白名单/封禁/重复名；保留原因，不误判版本或认证 | **一半但已被认领**：白名单那一对（`the_refusal_was_classified_in_the_ledger` + `the_bridge_classified_the_refusal`）**已由 `ADMIT-100` 拿着** | 封禁与重名两类各自的分类；以及「不误判成版本/认证」这条**否定**判据 |
| ADMIT-060 | 资源包未授权时不 PLAYABLE、不由聊天同意 | **一半**：`no_lease_was_granted` 能说「没授 lease」（它现在由 `CORE-050` 认领；共用是允许的，但用它之后这一条自己的判据仍然只剩一半） | **2026-09-23 判据已冻结**（专项契约「ADMIT-060 的可复判证据边界」）：缺的两件都已指名——**（乙）**本 generation 实际放上线缆的资源包策略没有产品事实承载，**(甲/测试域)** 客户端 `server-resource-packs/` 目录列表没有被 sealer 封进 bundle。「聊天不是授权来源」改写为「同意只有一个来源」，由 profile revision + 冻结事件承担，不再要求聊天侧的否定观察。**2026-09-24（乙）已闭合**：`ResourcePackPolicyApplied`（BRIDGE / BRIDGE_FILTERED，payload 只有 generation 与策略枚举名）在两条真实受控 run 里各读到恰好一行、值等于冻结 profile 的 `deny`，见 `ADMIT-060-WIRE-POLICY-001` 的 `completion_evidence`；该场景自此只缺（甲）那一份测试域工件 **2026-09-24（甲）也已闭合**：目录列表封为 `client/server-resource-packs.json`、四项判据入判官，真实 `deny` 运行 run `7bc740ea4cde4e1aaff074bb64850348` 封出 `PASS`/`AGREES` 的正式 bundle（见 `ADMIT-060-CASE-001` 的 `completion_evidence`）。这一行今天读作「已闭合」 |
| ADMIT-090 | 新 generation；世界状态重验；人格不重建 | **三分之二**：`the_restart_runs_as_a_new_session`、`the_restart_reconciled_before_it_started` 都在（两者为 `CORE-090` 写的，共用是允许的） | **（乙）**账本现有的十个事件类型里**没有一个承载身份/人格**，所以「没有重建」今天无从观测 |
| ADMIT-120 | oracle 身份/坐标 canary 不进入 Runtime/Memory/prompt/行动路径 | 无运行时断言（`runtime_input_does_not_reference_oracle` 是**仓库自检**类，不是运行材料类） | 运行期那半**整条缺失** |

**一条顺带查出来的契约冲突，已经影响上面 `ADMIT-050` 那一行**：`ADMIT-100` 在
**两份契约里是两件事**——`p0-remote-admission-contract.md` 说它是「同名/改名/代理改写 ｜
同时记录本地候选与服务端观察身份，不错误合并 actor」（身份），而
`p0-validation-evidence-contract.md` 说它是「**服务端拒绝**……白名单上说不」（拒绝分类）。
`domain/cases.py` 的注记早就记着这两份契约对 `ADMIT-100`/`ADMIT-110`「disagree about what
those two scenarios *are*」，而**现有 fixture 跟的是后者**。所以 `ADMIT-050` 想复用那对断言时
会撞上「同一个判据被两个 case 认领、而两个 case 的场景不同」。**这不是新问题，是那个已记录的
冲突第一次产生实际影响**；谁写 `ADMIT-050` 之前得先把它解掉。

## 阻塞分类

- `LOCAL`: 可在当前机器完整实现并验证。
- `LOCAL_THEN_REAL_RUN`: 可先实现可测量性/结构，但最终验收必须真实运行。
- `WAITING_REAL_RUN`: 任何生产改动都必须与同一阶段真实运行一起交付。
- `BLOCKED_DECISION`: 先冻结决策，再写代码。
- `DEFERRED`: 前置阶段未完成，不得领取。

当前顶层未完成项中，没有“只差几行本地代码即可完整关闭”的条目；主要是 12 个
真实运行缺口、4 个决策与 8 个 W80+ 未来阶段。本文额外识别出的本地任务，是为了
补执行入口与 fail-closed 门禁，而不是把真实运行缺口改写成本地完成。

## 门禁矩阵

所有 Python/文档阶段至少运行：

```text
uv run --frozen pytest -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen python tools/check_boundaries.py
uv run --frozen python tools/check_case_assertions.py
uv run --frozen python tools/verify_fixture_digests.py
uv run --frozen python tools/check_workflow_pins.py
git diff --check
```

Bridge/proto 变更另加：

```text
uv run --no-project python tools/check_bridge_scaffold.py
uv run --no-project python tools/check_bridge_host_boundary.py
uv run --no-project python tools/check_bridge_protocol.py
uv run --no-project python tools/check_bridge_proto_java.py
```

并使用 Java 21 运行 Gradle `check --rerun-tasks`。**`--rerun-tasks` 不是可选项**，
2026-09-23 在同一棵源码上量过三条命令，**三条都打印 `BUILD SUCCESSFUL`**：

```text
./gradlew check                    -> 15 actionable tasks: 1 executed, 14 up-to-date
./gradlew clean check              -> 16 actionable tasks: 12 executed, 4 from cache
./gradlew check --rerun-tasks      -> 15 actionable tasks: 15 executed
```

第一条里 `:compileJava`、`:test`、`:remapJar` 全在 up-to-date 中；第二条把 4 个任务交给
**build cache**（`bridge/gradle.properties` 里 `org.gradle.caching=true`），而 **`:test`
正是那 4 个 FROM-CACHE 之一**。**只有第三条能说「Java 测试跑过并通过」**——所以读到
`UP-TO-DATE` 就当绿，在这条门禁上不是保守，是没验。本仓库已经吃过一次增量判断错的亏：
删掉探针源码后 `jar`/`remapJar` 仍报 UP-TO-DATE，`build/libs` 里留着带 `LeakProbe.class`
的旧 jar，是产物门禁把它挡下的（见 `development-todo.md`）。
冷构建复现 pin 的读数：`clean check` 后 jar 为 `49af3b6f…` / 1,305,495，与 `BRIDGE_JAR_SHA256`
逐字节相同。涉及平台构建、Gradle 或 runner 时再做 Docker 验证。涉及生命周期、客户端线程、
callback 时序、故障恢复或真实指标的任务必须有 real-run evidence，本地绿灯只能证明本地层。

## Commit 与 push 协议

- 一张 task card 对应一个可逆 commit；不得把下一阶段“顺手”带入。
- Claude 默认只在隔离 worktree 改动，不直接 commit/push；主控完成规格与工程双审查、
  允许路径核对和本地门禁后再移植。2026-09-24 的 Qoder 临时连续执行是
  [条件式例外](qoder-execution-handoff.md#连续推进的授权边界)：每卡必须自行完成同等
  两轴审查与门禁、按卡 commit/push，不能把旧 Claude 流程的权限假定带进来。
- commit message 除主题外必须记录：

```text
Constraint: ...
Rejected: ...
Confidence: ...
Scope-risk: ...
Not-tested: ...
```

- commit 后立即 `git push origin main`，再核对本地 `HEAD`、本地 `origin/main` 与
  远端 SHA 一致；未 push 的阶段不得标为 `DONE`，不得领取下一张卡。
- push 失败时保留当前任务状态并修复 push，不创建“本地已完成”的下一阶段分支。

## Claude 调度包

每次调度必须从唯一 `NEXT` 机械生成 prompt，至少包含：

- baseline SHA 与目标 task id；
- 精确 `allowed_paths` / `forbidden_paths`；
- `non_goals` 与 stop conditions；
- 必跑命令与验收证据；
- “发现规格缺口时停止并报告，不自行设计新范围”；
- “你不是唯一在代码库工作的代理，不得回退他人改动”。

Claude 调用固定使用：

```text
claude --dangerously-skip-permissions
```

Claude 的交付必须含 diff stat、逐项改动理由、原始测试结果与未验证项。主控另做
spec/standards 双审查；越过允许路径的改动拒收，不以“顺便修复”为理由放宽。

## 任务状态变更规则

默认只有主控可修改 `current_next` 与任务状态。用户 2026-09-24 要求 Qoder
依照一份长程文档连续推进、避免每完成一小节重新请求编写计划，因此将
[`qoder-execution-handoff.md`](qoder-execution-handoff.md) 的 campaign 顺序内
**六项同时满足的机械流转**条件式委托给 Qoder；专项契约冲突、新产品策略、
`BLOCKED_DECISION`、HOST/W80+、PERSIST、扩大禁止路径均不在委托内。
委托流转仍须逐条满足下列规则：

1. `NEXT → DONE`：实现、门禁、commit、push、远端 SHA 五项齐全；
2. `NEXT → BLOCKED_*`：发现 task card 已写明的停止条件，并记录证据；
3. `QUEUED → NEXT`：所有依赖为 DONE，且没有更高优先级安全/回归问题；
4. 任何新任务先进入 `QUEUED`，不得直接插队；安全回归需记录原因后由主控提升；
5. 文档中的历史 `[x]`、提交消息或 Claude 自述都不是 DONE 证据，必须看当前树与命令。
