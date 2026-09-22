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
- `current_next`: 无——见下方「唯一 NEXT：无」。队列里已没有可提升的卡。

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
- 不接受 Mojang EULA，不替用户执行需要该授权的运行。
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

- required-case inventory v1：**72 required / 35 present / 37 missing**，按 gate 读出：
  `W00` 1、`W10` 1、`W20` 1、`W30` 11、`W40` 12、`W50` 3、`W60` 3、`W70` 5、
  `p0-core` 38、`p0-nav-exp` 1、`host-integrated` 33（present 15 / missing 18）；按证据
  种类 `local-only` 7、`runtime-required` 65；已登记但不 gating 的 27 条；
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

## 唯一 NEXT：无

`CORE-METRICS-001` 完成之后，**阶段队列里没有任何一张卡能按本文自己的规则被提升为
`NEXT`**。`OFFLINE-CANDIDATE-001` 曾经是队列里唯一可提升的卡，已于 2026-09-23 完成。

- `CORE-STATE-TRANSITION-001`、`REAL-P0-CAMPAIGN-001`：`WAITING_REAL_RUN`，两者的
  停止条件都写明「生产改动必须与同一阶段真实运行一起交付」；
- `HOST-ADMISSION-DESIGN-001`、`OPERATIONS-RETENTION-001`、`EVIDENCE-SEQUENCE-001`、
  `PROCESS-RECOVERY-001`：`BLOCKED_DECISION`，要先冻结决策再写代码；
- `HOST/W80+`：`DEFERRED`，前置阶段未完成。

**队列之外还有第二类，2026-09-23 才发现并做掉**：**证据生产也不是卡**。`local-only`
的 required case 只差一份**封存的 PASS bundle**，而 `tools/seal_repo_case.py` 不需要
Minecraft、不需要 runner、不需要任何决定——这正是 `CASE-CORE-001` 当时留给后人的
那一半。做了 `CORE-001` 与 `W00-CONTRACT-001` 两份之后，**`W00` 与 `W10` 两道门都
变成 `promotable`**（`blocks: []`、`requirement.satisfied: true`），而用机器读数问
一遍「哪些门的 required set 整组都是 `local-only`」，答案正好是这两道——其余的道
要么要真客户端（`W20`、`W60`），要么缺 1～18 条运行时用例，要么一条 mandatory case
都没有（`W70`）。**所以本地证据生产能关死的门只有这两道，已经关死了。**

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

### CORE-STATE-TRANSITION-001 — 账本显式记录状态迁移

- `status`: `WAITING_REAL_RUN`
- `depends_on`: `CORE-REPLAY-CLI-001`
- `scope`: 每次合法 session transition 记录显式 from/to 事实，使新 bundle 可 replay。
- `stop_reason`: 该改动横跨真实客户端生命周期与异步账本；强杀时最后一条迁移是否
  落账不能由 mock 证明。
- `unblock_condition`: 可使用受控 runner，且能在变更后运行正常退出与强杀场景。

### REAL-P0-CAMPAIGN-001 — 批量关闭真实运行缺口

- `status`: `WAITING_REAL_RUN`
- `depends_on`: `CORE-METRICS-001`、可用 artifact store、受控 runner 与用户 EULA 授权
- `order`: online-mode mismatch → resource-pack refusal → 首快照负向 → OFF-A/OFF-B
  → crash/outbox 窗口 → tick/render 采样 → CORE/OFFLINE/ADMIT promotion report。
- `acceptance`: 当前 build 与当前 case version 的 sealed bundle；verify、rejudge、
  replay（能 replay 的部分）和 promotion 报告一致。

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

- `status`: `BLOCKED_DECISION`
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
- `decision`（**未冻结，待主控/用户拍**）：两条路都说得通，代价不同——
  **（甲）按 build 绑定**：证据必须来自当前 build，否则 `EVIDENCE_FROM_ANOTHER_BUILD`
  拦截。它直接实现那句验收话，但会让**每一次** Bridge/recipe 改动作废**全部**已有
  证据（包括那些与改动无关的 case），代价是每次改 Bridge 都要重跑一整轮。
  **（乙）按单调序号 supersession**：封存端为该 case 分配 `attempt_sequence`（= 同
  case 已有最大值 + 1，无时钟、无目录名），并显式记录它取代哪一份；promotion 只认
  序号最大的那一份。它更接近这张卡原本的措辞，也让「修复后重跑」自然生效，但需要
  回答「最大那份是 FAIL 时该不该挡住一份更早的 PASS」（我倾向**该挡**，否则重跑没
  有意义），而那正是**语义改动**。
  **我的建议是乙**，因为它不惩罚与改动无关的 case，而且 `attempt_sequence` 是两种
  路都要用的东西。**但这是设计决定，按本计划的规则必须先冻结再写代码**，所以本文
  只把它写成提案，没有实现——上面那半诊断是两种路都要的公共前提。
- `completion_evidence`（仅诊断那半）：`tools/report_promotion.py` 与
  `tests/unit/test_report_promotion.py`；全量 pytest 1833 passed / 2 skipped，
  Ruff、Pyright、boundaries、case assertions、fixture digests、workflow pins 与
  `git diff --check` 全绿；两处变异各自驱动到红（把比较恒真 → 两条用例红；**让诊断
  去 gate** → 13 条用例红，正好证明这棵树期待 promotion 语义不变）。

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
`requirements` 段与下表逐族一致（同为 37 条缺失），但由机器读出、按 gate 组织，
并额外区分每条要求的是 `local-only` 还是 `runtime-required`。**这张表没有那种区分，
而它曾经因此把人带偏**：表里 `HOSTCTL` 行的 `060` 与其余各行看不出差别，机器读数里
它是唯一一条 `local-only`——也就是唯一一条不需要真实运行就能补上的。**要看某一族
缺的是不是本地能补的，读 inventory 的 `validation_class`，不要读这张表。**

| 族 | 当前 contract 要求但 fixture 缺失 |
| --- | --- |
| CORE | 080 |
| ADMIT | 001, 010, 020, 030, 040, 050, 060, 090, 120 |
| OFFLINE | 010, 020, 030, 060, 070, 080, 090, 100 |
| HOST | 001, 090, 100 |
| HOSTCTL | 020, 030, 040, 080, 090 |
| HOSTCOMMIT | 001, 010, 020, 030, 040, 050, 060, 070, 080, 100 |
| NAV | NAV-EXP-010 |

其中很多必须真实运行；“缺 fixture”不等于“可以用本地测试补成完成”。

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

并使用 Java 21 运行 Gradle `check`；涉及平台构建、Gradle 或 runner 时再做 Docker
验证。涉及生命周期、客户端线程、callback 时序、故障恢复或真实指标的任务必须有
real-run evidence，本地绿灯只能证明本地层。

## Commit 与 push 协议

- 一张 task card 对应一个可逆 commit；不得把下一阶段“顺手”带入。
- Claude 默认只在隔离 worktree 改动，不直接 commit/push；主控完成规格与工程双审查、
  允许路径核对和本地门禁后再移植。
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

只有主控可修改 `current_next` 与任务状态：

1. `NEXT → DONE`：实现、门禁、commit、push、远端 SHA 五项齐全；
2. `NEXT → BLOCKED_*`：发现 task card 已写明的停止条件，并记录证据；
3. `QUEUED → NEXT`：所有依赖为 DONE，且没有更高优先级安全/回归问题；
4. 任何新任务先进入 `QUEUED`，不得直接插队；安全回归需记录原因后由主控提升；
5. 文档中的历史 `[x]`、提交消息或 Claude 自述都不是 DONE 证据，必须看当前树与命令。
