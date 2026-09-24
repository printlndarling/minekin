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
- `current_next`: 无（本提交把 `VERSION-REMOTE-PROFILE-001` 收为 `DONE`；下一张
  `VERSION-SERVER-PROBE-001` 须先在独立提交登记 `QUEUED`，再由下一次提交提升为唯一 `NEXT`）。
  用户在七场景总账后明确把“自动识别服务器版本 → 准备匹配客户端 → 入服并完成简单控制”排为优先路线；
  `VERSION-AUTO-DESIGN-001` 已交付[跨版本连续执行计划](version-auto-to-server-control-plan.md)，
  `VERSION-REMOTE-PROFILE-001` 已由 `2c4e600` 先登记 `QUEUED`、`36764e8` 单独提升为唯一 `NEXT`。
- `last_checkpoint`: **有界自主 P0 campaign 已走到需用户拍板的边界；用户现已选择跨版本路线**——上一轮把
  `REAL-P0-CAMPAIGN-001.order` 第 7 也是最后一个场景（阶段 F 晋级总账）的只读卡 `P0-PROMOTION-LEDGER-001`
  收为 `DONE`（`532446e` 登记 `QUEUED`、`28876e3` 提升 `NEXT`）。`scenario_progress 6/7→7/7`——七个 `order`
  场景全部走完。**但 campaign 总体如实为 `BLOCKED/INCOMPLETE`，不标 `DONE`**：机器
  `report_cases.py` 读出 `74 required / 43 present / 31 missing / 0 misattributed`（本文旧「72/36/36」快照
  已被此读数取代），`report_promotion.py` 不带 `--work-package` 时 `overall.promotable:false`、
  `blocks [CASE_VERSION_MISMATCH, CASE_WITHOUT_EVIDENCE, REQUIRED_CASE_NOT_REGISTERED]`、37 阻断案；
  逐 gate `promotable` 全 `false`。缺口全需产品决策或逐案证据设计：HOST/HOSTCTL/HOSTCOMMIT 整族（host-integrated）、
  未冻结的 ADMIT/OFFLINE 判据、`PERSIST` `UNFROZEN_CASE_IDS`、`NAV-EXP-010`——这些是
  `HOST-ADMISSION-DESIGN-001`/`OPERATIONS-RETENTION-001`/`PROCESS-RECOVERY-001` 的 `BLOCKED_DECISION` 与
  `HOST/W80+` 的 `DEFERRED`，**须用户先拍板，不自行猜编号或 PASS 语义**。
  **上一批交付**：第 6 场景（tick/render + L6 soak）真实封证卡 `TICK-RENDER-SOAK-RUN-001`（`9f3946d` 提升、
  `a26a51a` 收 `DONE`）在当前 build 封 `CORE-100` 新 attempt（run `8367f741…`、bundle `1b2a58e9…`、`PASS`、
  四读一致、`report_soak` 只报覆盖、旧 baseline `e3a99202…` 只量不改读作 `UNJUDGED`）。第 6 场景判据表由冻结卡
  `TICK-RENDER-SOAK-EVIDENCE-DESIGN-001`（`096bd68`/`26a7543`/`6717d2e`）写下。**再往前**：crash/outbox 第 5 场景由 `CRASH-OUTBOX-ALIVE-DISPLAY-001`（`f90abc8`）与前置
  `CRASH-OUTBOX-RESEAL-001`（`DONE` 5/5）收口，`scenario_progress 4/7→5/7`。`ALIVE-DISPLAY` 只做一件事——把
  X 显示与 Core 的生死脱钩（harness 自己起并持有 Xvfb、
  `session` 只继承 `DISPLAY`、Core 挪到普通 `sh -c` 包装之下仍是 `session_pid` 的后代），使客户端 tick 那句
  `bridge released N input(s) after IPC_LOST` 有机会真被写出来；`src/`/`bridge/`/`proto/`/`tools/`、故障注入、
  目标选择、`domain.sh:1250` 等待条件、任何 fixture/digest/`mandatory`、已封 bundle 全在禁地，一字未动。
  三条 `stop_conditions`（产品侧回归 / 需动 forbidden_paths / 落到进程接管）均未触发。
  **更早**：`CRASH-OUTBOX-SEALED-KIN-001` 收为 `DONE`（登记 `c75865b`、提升 `3427e43`、交付 `2160989`、
  收卡 `acb2572`）修的是「没有文档的一次 run 属于哪个 Kin」。冻结卡 `CRASH-OUTBOX-EVIDENCE-DESIGN-001`
  （交付 `72aec3e`、收卡 `a1be5fb`）给出六个窗口的逐格读数，那份表在契约的「crash / outbox / restart 窗口的
  可封边界」一节。`minekin-runner:local` 镜像 `fed4a143f2e4`、`minekin-runner-data` 卷原样保留。
  `ADMIT-070-RECORD-SCHEMA-001` 也还是 `QUEUED`，但它自己写明不是任何封证卡的下一张，因此不排进这条链。
  其余未闭合卡仍是 `HOST-ADMISSION-DESIGN-001`/`OPERATIONS-RETENTION-001`/`PROCESS-RECOVERY-001`
  三项 `BLOCKED_DECISION` 与 `HOST/W80+` 的 `DEFERRED`，都要用户先拍板。
- `temporary_executor_handoff`: [Qoder 执行交接](qoder-execution-handoff.md)；
  执行者只实现当前唯一 `NEXT` 并交付证据，主控独占任务状态与下一卡提升。
  2026-09-24：交接文档顶部已补最新停机点；其 ADMIT-070 起步卡与后续阶段正文作为历史路线保留，
  不得覆盖本文当前 `current_next` 的判定。

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

- **文档不得记录运行者自备基础设施的地址**（2026-09-24 用户指示）。公网测试服等目标在计划、
  TODO、契约与证据记录里一律用匿名描述（「运行者自备的公网 offline 测试服」）指代，字面值只记在
  本地未跟踪文件 `.tmp/local-test-server.txt`（已在 `.gitignore`）。理由：文档会 push 到远端，
  一次普通提交抹不掉 Git 历史里的地址。

- **先修订卡片范围，再动手**（2026-09-24 用户指示，起因是 `ADMIT-070` 在实现完成后才追认六个
  超出 `allowed_paths` 的测试文件）。需要越界的改动时，先在本计划里登记/修订卡片并推送，或另起
  前置卡（例如 `OFFLINE-IDENTITY-SEALED-ARGV-001`），再碰那些文件；不得事后追认，也不得为绕开
  范围而放宽判据。

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
- `blocked_by`: `OFFLINE-IDENTITY-LEDGER-FACT-001`（`DONE`，`ec8fb15`）→ `OFFLINE-IDENTITY-CASE-001`
  （`DONE`，`2a84bbd`）→ `OFFLINE-IDENTITY-SEALED-ARGV-001`（`DONE`，`d8348a3`）→
  `OFFLINE-IDENTITY-RUN-001`（`DONE`：`14784a1` 提升、本条 commit 收卡，链条到此走完）。这几张卡都由已
  `DONE` 的
  `OFFLINE-IDENTITY-EVIDENCE-DESIGN-001` 与 `OFFLINE-IDENTITY-CASE-001` 登记。`order` 的第 1 个场景
  （在线认证拒绝）、第 2 个场景（资源包拒绝）与第 3 个场景（JOIN 后首快照失败）已各自在当前
  build 上封出 `PASS`/`AGREES` 的正式 bundle 并四读一致。第 3 个场景的判据由
  `ADMIT-070-EVIDENCE-DESIGN-001` 冻结在专项契约里，冻结的结论是：**这一条停在 `BLOCKED_EVIDENCE`
  的原因不是读不出，而是发生不了**——被拒快照的理由确实会写进 run document 的
  `snapshot_rejections`（读数那一层在真实运行里会工作，`entities_rejected` 就写过），但五个
  `SnapshotReason` 在当前构建与当前 runner 下一个都触发不了，数据卷 36 份真实运行文档该字段
  全为空。缺的那件——让 Bridge 在该代第一份快照上按 `authoritative=false` 上报、默认关断、由
  runner 显式要求、由测试域记录——已由 `ADMIT-070-REFUSAL-INJECTION-001`（`DONE`）交付并在两次
  真实受控诊断上读出；封证由 `ADMIT-070-CASE-001`（`DONE`）完成，停在 `BLOCKED_EVIDENCE` 的
  理由自此消失。
  **第 4 个场景（OFF-A/OFF-B）的四个判据现在全部有了真实 bundle**：`OFFLINE-IDENTITY-RUN-001`
  已把 `OFFLINE-010`/`OFFLINE-020` 两列各封出一份 `PASS` bundle（判据 1/2/3/4 逐条在真字节上过），
  判据 5 落在 `OFFLINE-030-PRISM-PARITY-001`/`OFFLINE-030-ENUM-ALIGNED-001` 两个子 case 上，此前
  因 `domain.sh` 把 case id 直接小写当 fixture 文件名、`-001` 后缀不 round-trip 而**封不进 harness**；
  那个阻断由 `OFFLINE-030-CASE-FILENAME-001`（`DONE`）在 fixture 侧改名解掉，两列各封一份 `PASS`。
  战役本身仍停在 `BLOCKED_EVIDENCE`，但**挡住的不再是第 4、5 个场景**：第 6/7 个场景（tick/render 采样、
  promotion report）尚无卡。第 5 个场景（crash/outbox 窗口）现已封齐——判据由
  `CRASH-OUTBOX-EVIDENCE-DESIGN-001`（`DONE`）冻结，五个已定义窗口在 current build 上各封一份 `PASS`
  （`CRASH-OUTBOX-RESEAL-001` `DONE`，runtime 那一格最后由 `CRASH-OUTBOX-ALIVE-DISPLAY-001` 交付 `f90abc8`
  解掉显示与 Core 生死脱钩的硬阻断），四读一致；旧 build 上那五份 bundle 对今天的 `case_version` 读作
  `UNJUDGED`，连同两份 runtime `FAIL` 按冻结口径原样保留、不追认。启动窗口那一半（未 settle 的 effect
  intent）按冻结记为本地证据，不在真实 run 里插停顿。第 6/7 个场景在此之前没有任何卡。
- `scenario_progress`: 7/7 场景已走完（`order` 第 7 个即阶段 F 晋级总账，由 `P0-PROMOTION-LEDGER-001` 交付）。
  **campaign 总体如实为 `BLOCKED/INCOMPLETE`，不标 `DONE`**：`report_cases.py` 读出 `74 required / 43 present /
  31 missing / 0 misattributed`，`report_promotion.py` `overall.promotable:false`、逐 gate 全 `false`——缺口全需
  产品决策或逐案证据设计（见 `P0-PROMOTION-LEDGER-001` `completion_evidence`）。第 6 个（tick/render + L6
  bounded-soak）在当前 reviewed
  build 上封 `CORE-100`（run `8367f741124d4132835eeb3d85833d46`、bundle `1b2a58e9cc371d23…`、attempt 1、
  `case_version d6e94bbc93ff1666…`、`bridge_digest faeec4a9df83abb9…`、`result PASS`、四读一致；受控 600s/10s、
  `ended_early: false`、client/server 各 56 样本，`report_soak` 只报覆盖不设阈值；旧 `2026-09-20` baseline
  `e3a99202…` 只量不改、在当前 build 读作 `re_judged: UNJUDGED`）。第 5 个（crash/outbox 窗口）在 current reviewed build 上
  五案齐、`bridge_digest` 全为 `faeec4a9df83abb9…`：`CORE-060`（runtime，run `7fc0671eabca4430885017613977779c`、
  bundle `3876c335…`、attempt 3、`case_version` `d1ea32d8b705…`）、`CORE-060-CLIENT-001`（`c89f5d35…`）、
  `CORE-060-SERVER-001`（`f4365a50…`）、`CORE-090` 两连跑（`3e94d49a…`）、`CORE-020`（`8a72dcdf…`）。此前
  4/7 的四案读数与逐案 bundle 见各卡 `window_run_readings_2026-09-24` 与 `CRASH-OUTBOX-ALIVE-DISPLAY-001`
  `completion_evidence`。第 1 个：`ADMIT-040`，run
  `6b5856d57dee4052b2ffba3ff9e3459e`，bundle `46565ef2…`，attempt 1，PASS/AGREES。
  第 2 个：`ADMIT-060`，run `7bc740ea4cde4e1aaff074bb64850348`，bundle
  `ca61b64b86b13b0d55528f2f2604825f973c313ba7adaa91fcefe3a2cb29ddcc`，attempt 2
  （attempt 1 是 run `3c17aa78a838486391634e69d9f8ea98`，因判据 1 的读侧缺陷如实封存为
  `FAIL`，保留不覆盖），PASS/AGREES、`from_repository_build: true`。
  第 3 个：`ADMIT-070`，run `2a128d0dd30b4932b88ada6d0032d40c`，bundle
  `88ccc9dfc8202deef484eb00c5f45137f0a11f64f04a0597027887d47b5e537e`，attempt 2、
  `supersedes_run_id` 指向 `7ef8b5537c454e9fa6682102e5e288f5`（attempt 1 因判据在两轴自审后被
  收紧而 `case_version` 移动，现读作 `re_judged: UNJUDGED`，原样保留、不追认不覆盖），
  PASS/AGREES、`from_repository_build: true`。
  第 2 个场景另有三次**只作诊断**的受控运行，都不进 bundle、不追认 PASS：
  `a114949bf0204a2e8021ec5d02583b4b`（线缆策略事实落地前）、
  `b1ace69e610c4c04a942281add8bd69b`（拒绝侧，`run-114`）与
  `8516151dab664d8692c3bf7ab3288859`（默认离线正向，`run-115`，到达 `PLAYABLE`）。
  第 3 个场景在当前 build 上有两次**只作诊断**的运行：正向 `dc896480ac1c41d19094550b2f7161f4`
  （`run-124`，`PLAYABLE`/1 准入）与注入 `dfcfcc34c5ef4d4b9d6e83099c763dfc`（`run-125`，
  `NOT_AUTHORITATIVE`/0 准入），此外 `7ef8b553…` 是已封存的 attempt 1，不是诊断。
  第 4 个场景（OFF-A/OFF-B）两列各封一份，都在当前 reviewed build 上（`from_repository_build: true`、
  `bridge_digest faeec4a9df83abb9…`、`launch_plan_digest 9e0e0ccca9d0a589…`）、attempt 1、
  `supersedes_run_id: null`、PASS 且四读一致：`OFFLINE-010` run `f2ecb728df754826abf4a052be138a2d`
  （bundle `184d636cf028cd05eaf61ca36706ad8aa4576780c4c01e041f07c6f82728ed20`），
  `OFFLINE-020` run `3d5606ced37849e3b17a4c418fa33ab4`
  （bundle `ff68f67d51ba15afc35efafd89ca8781f31b0a02ed60ea9d9a10b9a2d7de45d8`）。
  两列的 `observed_account_type` 分别是空串与 `LEGACY`（如实记录，不预设，也不为对照好看而重跑）。
  这一行**现在也含判据 5**：`OFFLINE-030-PRISM-PARITY-001` run `ee9d5ad3d57344da8452069102e27216`
  （bundle `cdb8e53f67d54d5171b2d23741a20d5351bb59c1c7136ffa2f3a53c5d4734295`）与
  `OFFLINE-030-ENUM-ALIGNED-001` run `cb5e2119845e41868c28e5aeb1370ce3`
  （bundle `b90cb29b664a872133ffec208634723e37330c357f8876390b17eee2093ee90e`），attempt 各 1、
  `supersedes_run_id: null`、同一 `bridge_digest`/`launch_plan_digest`、四读一致（细节在
  `OFFLINE-030-CASE-FILENAME-001` 的 `completion_evidence`）。**一处如实保留的边界**：父
  `OFFLINE-030` 以自己的 id 仍然没有 bundle——它那一半（离线身份在 `online-mode=false` 专服入服、
  服务端身份与离线推导一致）已在两份子 bundle 内逐条判过，但没有一份材料以父 id 署名，
  `report_promotion.py` 里也查不到 `case_id: OFFLINE-030` 的条目。所以「4/7」读作**契约五条判据
  在真字节上全部有证据**，不读作「第 4 个场景的每个 case id 各自封过一份」。
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

- `status`: `DONE`
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
- `scope_amendment_2026-09-24`: 实现期间为改动的每一半各补了定向测试，落在 `allowed_paths` 之外的
  六个测试文件：`tests/contract/test_runner_scripts.py`（knob 按值生效、`run.sh` 转发它、oracle 不再
  读客户端日志、记录经同一封存通道读回）、`tests/contract/test_bridge_java_constants.py`（转发的变量名
  与 Java 常量钉在一起）、`tests/unit/test_inject_fault.py`（`request` 子命令的五种观察与往返）、
  `tests/unit/test_fault_injection.py`（第二类记录的形状规则与十条反例）、`tests/fault_support.py`
  （两种记录共用的样例）、`tests/unit/test_seal_run_evidence.py`（请求记录 byte-for-byte 进 bundle、
  且不能满足 sigkill 断言）。这些都不在 `forbidden_paths` 里（那里禁的是 case fixtures 与 assertions
  registry），但确实超出登记的 `allowed_paths`，故在此记名而不是默认无人在意。
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
- `completion_evidence`: 2026-09-24 实现与两次受控诊断完成，`status` 仍留 `NEXT` 等主控提升。
  - **门禁**：`pytest -q` 全量 **2017 passed / 2 skipped**（跳过项是 `test_orphans.py:686` 需要
    `/proc` 才能回答「已消失」、`test_silent_listener.py:123` 的 Windows terminate 不是信号，均为
    平台限制而非本卡缺口）；ruff check 与 format 干净；`git diff --check` 干净；
    `verify_fixture_digests`、`check_case_assertions`（129 条已登记）、`check_boundaries`、
    `check_workflow_pins`、`verify_supply_chain`、`bash -n`（两个 runner 脚本）全绿；
    `check_bridge_artifacts`/`host_boundary`/`protocol`/`proto_java`/`scaffold` 全绿；
    JDK 21 `./gradlew build check --rerun-tasks` 为 BUILD SUCCESSFUL、17 tasks executed（无
    `UP-TO-DATE`/`FROM-CACHE`）。交接文档记录的 33 红灯全部消失：32 条 digest 因果（未续期 pin +
    `run.sh` 未转发 knob）与其余同因失败一起由续期与转发解决。
  - **pyright 的既存红灯**：`tests/unit/test_report_soak.py:158,217` 的 3 条
    `Type of "approx" is partially unknown` 在本卡未触碰该文件的情况下仍然存在（该文件工作树与
    HEAD 一致），按既存问题记名，不在本卡顺手改。
  - **受审 pin 续期（旧 → 新）**：`recipe.py` 的 `BRIDGE_JAR_SHA256`
    `ecff5a598bda3a5055755cbbf04251d33c464b3764267b7b479917a2a8dce9c7` →
    `faeec4a9df83abb9ca0404863e04d20cfd87ac0f3afd5e74b6858e3e15372f55`，`BRIDGE_JAR_SIZE`
    `1_307_584` → `1_308_525`；bundle fixture 里 minekin-bridge 的 digest/size 同步，
    `source_digest` `1b1103dd8b747dca1db79fd19d9998e477f9a77d53bc2c8cbdcce4000ea19f27` →
    `507f708dc4e3028ab90b5503ed34aac66ba77f6657904eba4533525b53a4d229`；
    `tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json` 自身
    `c3a19927687bd00e749231e47e86b0d3c8cc0f801bcfb224e270c776d9166829` →
    `bb45606023cea201bf8cb66ee35dfcfa136c428a8eb8bfff90c864499d5dcf72`（CORE-001 的 input digest
    同值）；`tests/fixtures/cases/core-001.json` 自身
    `c26cb0b514c1f5b35cd46c7ad7af761813846626d6ce78f52e7332e442d624a3` →
    `4f2fc11f8c65de4861568d3b3b744d58c904010fa8284777586ef7f3f7457564`；`manifest.sha256` 两行随动。
    未放宽任何校验：digest 红灯是靠重建 + 续期消失的。
  - **正向诊断（未设开关，默认关断不回归）**：run `97fcfa1460d1407b9e94e34e12934ab5` /
    session `dd55afb9435840fdad93cea5e399671e` / generation 1 / 服务端目录
    `/data/server-runs/run-118`。run document：`connection_state: PLAYABLE`、
    `snapshots_admitted: 1`、`snapshot_rejections: []`、`entities_admitted: 16`、
    `outcome: BRIDGE_LOST`。同 run 的 ledger（position 951–968）有 `JoinObserved`（962，
    `BRIDGE`/`BRIDGE_FILTERED`）与 `PlayableEstablished`（964）。退出码 14＝harness 主动停掉承载
    Bridge 的客户端，按 `runner/README.md` 的既有语义，不是失败。
  - **注入诊断（`MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT=1`）**：run
    `db5671d970f943aa8540fd50191ecd92` / session `d623a3c135b544d4ac0c92a2756b8892` /
    generation 1 / 服务端目录 `/data/server-runs/run-120`（形状相同的第一次
    `785fcd4d9d3e4ac3bb7ed3e657708dcb` / `bb2f7da12b5d401db9b1a4dd1b983b48` / run-119，在判据块
    还没把「通过」说出来之前跑的，故重跑一次留可读数）。run document：`connection_state: JOIN_SEEN`、
    `snapshots_admitted: 0`、`snapshot_rejections: ["NOT_AUTHORITATIVE"]`、`entities_admitted: 0`、
    `outcome: BRIDGE_LOST`；同 run 的 ledger（position 985–1000）有 `JoinObserved`（996）而
    **无** `PlayableEstablished`、**无** `InputLeaseGranted`；runner 判据块打印
    `domain: Core refused this run's first snapshot as asked`；退出码同为 14。
  - **注入事实能被同一封存通道读回**：同一次 run 里 helper 写下
    `{"observed": true, "reasons": [], "status": "recorded"}` 之后，`domain.sh` 改用
    `fault_injection.read_record`（封存器唯一的那个读取入口）把记录读回来并打进转写：
    `category: CLIENT_REPORT_REQUEST`、`effect.method: PROC_CHILD_ENVIRON`、
    `effect.observed: true`、`effect.detail: the managed client JVM at pid 207 carries …=1`、
    `request.asked: true`，归因到同一 run/session/generation，而那个 pid 正是同一次
    `session stop` 终止的进程。byte-for-byte 进 bundle、以及请求记录不能满足 sigkill 断言，
    由 `tests/unit/test_seal_run_evidence.py` 那两条证明。
  - **一条 ledger 的诚实附注**：`InputLeaseGranted` 在正向 run 的 ledger 里也不存在——那一轮没人
    请求过输入，所以「拒绝轮没有 lease」这条判据靠的是它**与** `PlayableEstablished` 一起缺席，
    而不是单靠一条本来就不会出现的行。
  - **未测**：新的 jar 字节只在 Windows（JDK 21.0.12.1+1-LTS-4）上构建过；旧 pin 的「Windows 与
    Linux x86_64 构建出同一份 jar」那次复现验证没有对新字节重做，`recipe.py` 的注释已按此改写，
    不再替新字节声称两平台。`check_wheel_boundary.py` 需要一个 wheel 参数（CI 构建后才有），本地
    未跑。本卡按 non_goals 未封任何 bundle：两次注入诊断与一次正向诊断只留在数据根的 run 目录与
    ledger 里，`ADMIT-070` 的 PASS bundle 属于后续的 `ADMIT-070-CASE-001`。运行者自备的公网
    offline 测试服（地址只记在本地未跟踪文件 `.tmp/local-test-server.txt`，不入文档）未被使用
    （`AddressPolicy.p0_loopback()` 与本卡的判据需求都不允许它）。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `feat(bridge): allow an explicitly requested non-authoritative first snapshot`
- `stop_conditions`: 若开关只能靠 `control.proto` 的一条新命令到达 Bridge，或注入无法在同一 bundle
  里说出自己（`fault-injection.json` 装不下这类事实且没有别的测试域通道），停在该卡并把第 3 个
  场景继续留在 `BLOCKED_EVIDENCE`——不得为了跑得出证据而把一条产品事件写成客户端没有的样子。
  两支都没有触发：开关走的是既有的转发清单，注入走的是既有的记录通道。
- `completion_commit`: `eeac5b0bb1e597c4f8b1a0aa84f58ddee0d286b7`
  （`feat(bridge): allow an explicitly requested non-authoritative first snapshot`）与其后按下面
  `self_review` 修记录的 `8498084a836fadfe9f1ec56b36b579900987fc16`
  （`fix(tools): stop a request record from claiming more than it saw`）。两次都已推，本地 HEAD、
  `origin/codex/core-state-transition` 与 `origin/main` 三个 SHA 逐一核对相同（`git ls-remote`）。
- `self_review`: 两轴自审在 `eeac5b0` 之后做，结论与修复都落在 `8498084`。
  - **对专项契约（Spec）**：`acceptance` 五支逐条回到读数——默认关断（正向 run
    `97fcfa14…` 仍 `PLAYABLE`/1 准入/0 拒绝）、设开关那支（`db5671d9…` 的
    `NOT_AUTHORITATIVE`/0 准入/无 `PlayableEstablished`）、注入事实同一通道可读回（`domain.sh`
    里用封存器唯一的读取入口打印该类记录）、Java 定向测试 + 全量门禁 + pin 续期、两次真实受控
    运行只作诊断。`forbidden_paths` 逐条按提交的 21 个文件核对：`proto/` 与生成物、
    `domain/perception.py`、`RecordedSessionMaterial`、判官、case fixtures 与 assertions
    registry、CI 都不在其中；超出 `allowed_paths` 的六个测试文件已由
    `scope_amendment_2026-09-24` 记名，`src/minekin_core/config.py` 由 `scope_amendment` 记名。
  - **对设计（Standards）**：依赖方向没有新增边——`tools/` 不 import 产品包，产品侧只在
    `FORWARDED_VARIABLES` 加一个名字且 Core 从不读它的值（不新增概念，判定语义原样）；`/proc`
    的 environ 只有 `_environ()` 一处读，请求类与 kill 类共用同一 `validate()` 分派，没有第二份
    形状规则；判官与封存器一行未动，因此「请求记录不能满足 sigkill 断言」是由既有断言把守而不是
    由新写的分支把守。
  - **发现并修复的三处**：①`record_request` 在 environ 命中之后、身份读取之前遇到进程消失时，
    会写下 `observed: false` 却把 pid 留在 effect 里且 `reasons` 为空——那是该模块自己的
    `validate()` 会拒的形状（`NOT_OBSERVED` 要求 pid/starttime 皆空，且未观察必须给理由），真实
    撞上会让封存直接失败，现在报 `CLIENT_IDENTITY_UNREADABLE` 并清空 pid，配一条在两次读取之间
    抽走该进程的定向测试；②「请求没到」那条 detail 原文声称客户端环境里**该名的任何值**都不存在，
    而代码只查过被要求的那一对，等于多报一个没做过的检查，现改为只说被要求的那一对与查了几个
    JVM，并由测试钉住不再退回原措辞；③`PROC_CHILD_ENVIRON` 的注释把机制写成从被启动进程
    *继承*，实际是按命令行在后代里找到客户端 JVM 后读它**自己的** environ——这个区别正是这条记录
    的全部价值（宿主打算转发 ≠ 那个 JVM 收到了），注释与模块 docstring 一并改回准确。
  - **查过不是缺陷的**：记录里的 pid 确实是客户端 JVM 而非其宿主（`find_candidates` 只接受
    命令行匹配 java + 客户端主类的**严格后代**）；runner 判据块把「通过」说出来这件事本身由
    `tests/contract/test_runner_scripts.py` 钉住，避免以沉默充当证据。
  - **修复后的门禁**：全量 pytest **2018 passed / 2 skipped**（跳过项仍是两处平台限制）、
    定向 fault/judge/sealer 165 passed、ruff check 与 format 干净、被改四个文件 pyright 0 errors、
    `verify_fixture_digests`/`check_case_assertions`(129)/`check_boundaries`/`check_workflow_pins`
    干净、`git diff --check` 干净。该提交不含 `bridge/` 与 `test-orchestrator/` 改动，故 Gradle
    与 `bash -n` 沿用在 `eeac5b0` 上的绿色读数。
  - **仍未闭合**：冻结 schema 仍只描述 kill 一类（`ADMIT-070-RECORD-SCHEMA-001`）；本卡的两次
    运行是诊断，正式 bundle 属 `ADMIT-070-CASE-001`；新 jar 字节的 Linux 逐字节复现未做。
- `next_after_done`: `ADMIT-070-CASE-001`（`order` 第 3 个场景的封存与复判）。

### ADMIT-070-CASE-001 — 封存并复判首快照拒绝用例

- `status`: `DONE`（登记与提升写在同一次交付里，依据与理由见下面两条；完成记录在本节末尾）
- `baseline_sha`: `8498084a836fadfe9f1ec56b36b579900987fc16`
- `registered`: 2026-09-24。交接文档阶段 B 的原文顺序就是「先登记 `ADMIT-070-CASE-001` 为
  `QUEUED`，……再按条件授权提升为唯一 `NEXT`」，而它的前置 `ADMIT-070-REFUSAL-INJECTION-001`
  已在同一 build 上完成六项门禁与两次真实诊断并推送，所以本卡不是凭空提级：登记与提升之间
  没有插入任何未被授权的工作。
- `promotion_reason`: campaign `order` 第 3 个场景今天只缺封证。注入点已落地且被两次真实
  受控运行验证（正向 `97fcfa14…` 到 `PLAYABLE`/1 准入，注入 `db5671d9…` 到
  `NOT_AUTHORITATIVE`/0 准入/无 `PlayableEstablished`），记录通道能在同一 run 里被封存器
  读回；判据已由 `ADMIT-070-EVIDENCE-DESIGN-001` 冻结在专项契约「ADMIT-070 的可复判证据边界」
  五项里。`ADMIT-070-RECORD-SCHEMA-001` 不是本位的下一张：封存与复判都不读那份 schema
  （只有 `tests/unit/test_fault_injection.py` 读它），它是被测试钉住的结构缺口，留在 `QUEUED`。
- `question`: 一份真实拒绝运行要封哪些工件、`ADMIT-070` 的五条既有断言（全是 `pytest` 域内
  断言）如何与运行材料对应而不被同名冒充，以及「注入说过」这件事在 bundle 里由哪条断言把守。
- `allowed_paths`:
  - `tools/assert_case_evidence.py`（新增运行材料断言；不改 `ADMIT-040`/`ADMIT-060` 既有判据语义）
  - `tools/seal_run_evidence.py`（仅当本场景需要的工件尚未进通道时）
  - `tools/check_case_assertions.py`（`--record` 登记新断言）
  - `tests/fixtures/cases/admit-070.json`（`W50`、`mandatory: false` 不变；断言集与
    `assertion_digests`、`inputs` 随真实材料更新）
  - `tests/fixtures/manifest.sha256`
  - `tests/unit/test_case_evidence_assertions.py`、`tests/unit/test_seal_run_evidence.py`
  - `tests/contract/test_runner_scripts.py`、`tests/contract/test_case_coverage.py`
  - `test-orchestrator/runner/domain.sh`（`ADMIT-070` 场景的等待/封存分支）与
    `test-orchestrator/runner/run.sh`（仅当需要转发既有 knob）
  - `docs/development-execution-plan.md`、`docs/development-todo.md`
- `forbidden_paths`: 产品代码与 `proto/`/Bridge（注入点已由上一卡交付，本卡不为跑通封存而
  再改产品语义）、`domain/perception.py` 判定语义、`RecordedSessionMaterial` 构造、case registry
  编号与 `mandatory` 翻转、`schemas/fault-injection.schema.json` 与 `w00-contract-001.json`
  （那是 `ADMIT-070-RECORD-SCHEMA-001` 的范围）、CI。
- `scope`: 专项契约五项逐条落到「可信来源 → sealed artifact → 判官字段 → 反例」——
  ①确实进了世界：同 run ledger 的 `JoinObserved`（`BRIDGE`/`BRIDGE_FILTERED`）+ run document
  `connection_state != PLAYABLE` 且 `snapshots_admitted == 0`；②被拒是有判决的被拒：
  `run-document.json` 的 `snapshot_rejections` **含 `NOT_AUTHORITATIVE` 这一个枚举名**
  （非空即可不算）且 0 准入；③无 lease 无 PLAYABLE：复用 `no_lease_was_granted` 与
  `PlayableEstablished` 缺席，且必须写在①②在场之上（缺失不单独成事实）；④本代终止：
  `connection_cancelled`/`outcome` 说这一代已放弃，其后同 run 不再出现 JOIN/PLAYABLE 迁移；
  ⑤注入在 bundle 里说得出自己：`fault-injection.json` 的 `CLIENT_REPORT_REQUEST` 记录归因到
  同一 run/session/generation、`request.asked` 为真、`effect.observed` 为真——没有它这份
  PASS 分不清「Core 拒了一份被要求谎报的快照」与「客户端真的自发谎报」。
- `non_goals`: 不认领另外四个 `SnapshotReason` 的运行时形状、不要求 proto 里从未被发出的
  `FIRST_SNAPSHOT_TIMEOUT`/`WORLD_BINDING_MISMATCH`、不把客户端日志那行 warn 当被拒事实、
  不把「45 秒没 PLAYABLE」当拒绝、不改 `ADMIT-070` 的域内 pytest 断言来迁就运行材料、
  不把上一卡的两次诊断运行追认为 PASS。
- `acceptance`: 断言与反例逐条红（只有超时、`snapshot_rejections` 非空但已有准入、
  仅 `entities_rejected` 非零、login 前就失败无 `JoinObserved`、出现过 lease 或 PLAYABLE、
  同 run 之后新代到 PLAYABLE、`snapshot_rejections` 字段缺失或类型不对、没有注入归因记录）；
  `check_case_assertions --record` 与 fixture digest 更新且不改既有 case version；全量本地门禁绿；
  在当前 build 上先各重跑一次正向与注入诊断，再封正式 run（新 attempt，失败件原样保留），
  `evidence verify` / `rejudge_evidence.py` / 适用的 `replay` / `report_promotion.py` 四读一致，
  并记录 run ID、attempt、bundle digest、case version 与 promotion 读数后才可 `DONE`。
- `validation_class`: `LOCAL_THEN_REAL_RUN`
- `commit_intent`: `feat(evidence): seal first-snapshot refusal case`
- `stop_conditions`: 若封存通道里拿不出注入工件，本卡停在 `FAIL`/`BLOCKED_EVIDENCE` 并记名，
  不靠 Bridge 日志补判；若同一 build 的真实注入运行读不出 `NOT_AUTHORITATIVE`（即上一卡的
  读数在当前 build 上不可重现），停在该卡并如实封存失败运行，不换判据、不改产品语义凑绿。
  两条都没触发：注入工件在同一 run 的 bundle 里被读回，真实注入运行仍读出
  `NOT_AUTHORITATIVE`。

- `completion_commit`: `2a70c7b49e96bac49c09680dcb863012dfaa42e8`
  （`feat(evidence): judge a sealed first-snapshot refusal run`）与其后按两轴自审修掉判据缺陷的
  `ec082f3e749f14a21b7d7574252849bb929c6fbe`
  （`fix(evidence): make the closure criterion read the row that actually closes`）；登记与提升在
  `ff63746`。三个 commit 均已推送，本地 HEAD、`refs/heads/codex/core-state-transition` 与
  `refs/heads/main` 逐字节相同。
- `completion_evidence`:
  - **五条判据落进判官**（`tools/assert_case_evidence.py`，全部只读运行材料），反例逐条红：
    ① 确实进了世界却没被告知能玩 = 同 run ledger 恰好一条 `JoinObserved`
    （`BRIDGE`/`BRIDGE_FILTERED`）+ run document `snapshots_admitted == 0` 且
    `connection_state != PLAYABLE`（缺该字段判 `CONNECTION_STATE_UNREADABLE`；反例 7 条）；
    ② 被拒是有判决的被拒 = `snapshot_rejections` 含枚举名 `NOT_AUTHORITATIVE` 且 0 准入
    （反例 8 条，含「非空但已有准入」「字段缺失或类型不对」）；③ 无 lease 无 PLAYABLE 写在
    ①② 在场之上（反例 5 条）；④ 本代终止（见下面的偏离）反例 10 条；⑤ 注入在 bundle 里
    说得出自己 = `fault-injection.json` 的 `CLIENT_REPORT_REQUEST` 归因到同 run/session/generation、
    `request.asked` 与 `effect.observed` 均为真（反例 18 条）。客户端日志那行 warn 只做
    「删掉它判据仍然成立」的对照，不作为被拒事实。
  - **④ 的偏离（专项契约是本卡的 forbidden path，故记在这里）**：契约冻结文本给的候选字段是
    「`connection_cancelled`/`outcome` 说这一代已放弃」。实测这两者在当前 harness 下都不判别：
    每个封存的 run（健康运行的正向诊断同样）`outcome` 都是 `BRIDGE_LOST`，因为 harness 是 terminate
    客户端来停会话的；而拒绝场景下 `connection_cancelled` 为空，因为 Core 没有主动放弃任何尝试。
    判官因此改读 ledger 自己的那一行：`SessionStateTransitioned`、`from == JOINED_UNVERIFIED`、
    `to == FAILED`、`source == CORE` 且 `trust_class == CORE`、`position` 晚于本 run 唯一的
    `JoinObserved`、且属于同一 session；这一行之后不再出现 `PlayableEstablished`。这比冻结文本
    更强（正向对照也过不了它），不是替换成更容易的读数。真实 bundle 里读到的就是
    `pos=1096 JoinObserved BRIDGE/BRIDGE_FILTERED` 与 `pos=1097 JOINED_UNVERIFIED→FAILED CORE/CORE`。
    契约文本要按这次读数续期，需主控决定，本卡未改。
  - **两轴自审记录**（交接第 4 项）：并行两个子代理分别按「逐项对应专项契约」与「逐项核对
    允许路径/依赖方向/代码重复/测试假阳性」审 `2a70c7b` 的 diff，回报 5 条，其中 3 条为真并已
    修（④ 只看 `to == FAILED` 却在 docstring 里承诺了起始态与 Core 作者身份；① 接受没有
    `connection_state` 的文档；② docstring 把实体拒绝说成会进 `snapshot_rejections`，实际不会），
    2 条经核对不成立或不修：kill 记录形状本就由写侧 `fault_record()` 构造器产出，⑤ 与
    `_confirmed_sigkill` 重复的归因段保持现状——抽公共 helper 会移动其他 case 的判据，那是本卡
    禁止的。修完后判据变化必然移动 `case_version`，故只重录 `admit-070.json` 一个 fixture
    （`778f0541…` → `d829381d…`）、`manifest.sha256` 只动该行，其余 case version 未动。
  - **本地门禁**（在 `ec082f3` 上）：pytest **2071 passed / 2 skipped**（跳过项为
    `tests/unit/test_orphans.py:686`、`tests/unit/test_silent_listener.py:123` 两条平台不可答项）、
    Ruff check/format、Pyright 0 errors、boundaries OK、case assertions 134 条注册且 `--record`
    只动新 fixture、fixture digests OK、workflow pins OK、`git diff --check` 干净；
    `report_cases.py` → `ADMIT-070` 5 条断言、`judged_by: run-material`、`mandatory: false`、
    `W50`、unregistered 0，总计 38 cases / 145 assertions。
  - **当前 build 上的两次诊断**（都不封 bundle、不追认 PASS）：正向 run
    `dc896480ac1c41d19094550b2f7161f4` / session `b13916d4501648dba30f27eeff08dd4b` / 服务端
    `run-124` → `connection_state: PLAYABLE`、`snapshots_admitted: 1`、`snapshot_rejections: []`；
    注入 run `dfcfcc34c5ef4d4b9d6e83099c763dfc` / session `a1425ef1b0894817af61a79ee7569ff1` /
    服务端 `run-125` → `JOIN_SEEN`、0 准入、`["NOT_AUTHORITATIVE"]`，runner 自己判读
    「Core refused this run's first snapshot as asked」。
  - **正式封存**：run `2a128d0dd30b4932b88ada6d0032d40c` / session
    `8294c928c2564c0a93a41219ef30c84d` / generation 1 / 服务端 `run-126` /
    `attempt_sequence: 2` / `supersedes_run_id: 7ef8b5537c454e9fa6682102e5e288f5` /
    bundle `88ccc9dfc8202deef484eb00c5f45137f0a11f64f04a0597027887d47b5e537e` /
    `case_version d829381de953cfeb01a4f12858f10e6f9353153b23c04bc6980d109e18ddbaa3` /
    14 件工件 / `result: PASS` / `failures: []`。四读一致：① `evidence verify` →
    `verified: true, sealed: true, artifacts: 14, violations: []`；② `tools/rejudge_evidence.py` →
    `status: agrees`，`current` 与 `recorded` 两边 5/5 observed、`failures: []`；③
    `minekin_core replay` 与 `tools/replay_evidence.py` 读同一 bundle → 16 事件投影到 `STOPPED`、
    `violations: []`、`trace_sha256 cf724e39…`；④ `tools/report_promotion.py --data-root /data
    --work-package W50` → 该行 `PASS / verified: true / sealed: true / re_judged: AGREES /
    from_repository_build: true`，`bridge_digest faeec4a9…` 与配方 pin 相同、
    `launch_plan_digest 9e0e0ccc…` 与当前 build 相同。报告整体 `status: blocked` 且退出码 1
    是既有事实（41 条 mandatory case 尚未封存），`ADMIT-070` 以 `requirement.non_mandatory` 出现。
  - **第 1 次尝试保持原样**：run `7ef8b5537c454e9fa6682102e5e288f5`（bundle `e3e6ca36…`，
    `case_version 778f0541…`）不覆盖、不追认；判据收紧后它在 promotion 报告里读作
    `re_judged: UNJUDGED`，理由是「这份 bundle 是对着旧 case version 封的，判据移动了」。
  - **未验证项**：新 Bridge jar 字节的 Linux 逐字节复现（上一卡遗留）；`ADMIT-070` 其余四个
    `SnapshotReason` 的运行时形状；`mandatory` 仍为 `false`，故本 case 不 gates W50。
- `next_after_done`: `OFFLINE-IDENTITY-EVIDENCE-DESIGN-001`（`order` 第 4 个场景：OFF-A/OFF-B
  身份候选的可复判证据设计）。本卡 DONE 时它只登记为 `QUEUED`，提升为唯一 `NEXT` 写在紧随的
  下一个 commit 里，以满足交接第 1、6 项「新卡先 `QUEUED`，不得直接 `NEXT`」。


### ADMIT-070-RECORD-SCHEMA-001 — 让封存的 schema 也说得出报告请求记录

- `status`: `QUEUED`；不替换当前唯一 `NEXT`（本卡由 `ADMIT-070-REFUSAL-INJECTION-001` 的
  `completion_evidence` 登记，而 `order` 第 3 个场景的封证 `ADMIT-070-CASE-001` 排在它前面：
  封存与复判都不读这份 schema，只有 `tests/unit/test_fault_injection.py` 读它，所以它是被测试
  钉住的结构缺口而不是封证的前置）。
- `why_now`: 上一条卡给 `fault-injection.json` 加了第二类记录（`CLIENT_REPORT_REQUEST`），
  而 `schemas/fault-injection.schema.json` 仍只描述 SIGKILL 那一种。这不是遗漏而是被钉住的
  缺口：`tests/unit/test_fault_injection.py::test_the_frozen_schema_still_describes_the_kill_record_only`
  显式断言一条请求记录**会**被 schema 拒绝。之所以不当场改，是因为该文件在
  `tests/fixtures/cases/w00-contract-001.json` 的 `inputs`（`schemas/*.schema.json`）里，
  动它 = 给一张与本场景无关的 case 重新定版；而 case fixtures 是那张卡的 `forbidden_paths`。
- `allowed_paths`: `schemas/fault-injection.schema.json`、
  `tests/fixtures/cases/w00-contract-001.json`（只随 `case_version` 重签）、
  `tests/fixtures/manifest.sha256`（第 6 行随 schema 动）、
  `tests/unit/test_fault_injection.py`（把钉住缺口的那条改成两类的对齐断言）、
  `tests/unit/test_seal_run_evidence.py` 与 `tests/fault_support.py`（仅在需要样例时）、
  `docs/development-execution-plan.md`、`docs/development-todo.md`。
- `forbidden_paths`: 判官 `tools/assert_case_evidence.py`、`tools/fault_injection.py` 的读取规则
  （reader 是契约，schema 是它的书写形式，改的方向只能反过来）、产品 `src/minekin_core`、
  Bridge、runner、`proto/`、CI。
- `scope`: 让 schema 对两类记录分别给出 required/`oneOf`，并把
  `test_the_schema_refuses_everything_the_reader_refuses_structurally` 那套「reader 拒的 schema
  也拒」的覆盖扩到请求类（含 `EFFECT_WITHOUT_REQUEST`、`INVALID_CATEGORY`、`INVALID_ATTRIBUTION`
  与 `asked` 由 value 派生这几条 reader 已有的规则）。
- `non_goals`: 不新增第三类记录、不改 `CLIENT_REPORT_REQUEST` 已冻结的字段语义、不为让 schema
  通过而放宽 reader 的任何一条规则、不重新解释 SIGKILL 类的既有字段。
- `acceptance`: schema 与 reader 在两类记录的全部结构反例上一致；`check_workflow_pins` 与
  `verify_fixture_digests` 绿；`w00-contract-001` 的新旧 `case_version` 与 `manifest.sha256`
  新旧行在交付记录里列明；本地全量门禁绿（本卡无真实运行要求）。
- `validation_class`: `LOCAL_ONLY`
- `stop_conditions`: 若 `jsonschema`（测试期依赖，draft 2020-12）无法在不往 reader 里加规则的
  前提下表达两类的判别，停在该卡并报告：宁可让 schema 继续只描述一类、由测试记名缺口，也不能
  让写下来的契约与执行它的读取器各说各话。

### OFFLINE-IDENTITY-EVIDENCE-DESIGN-001 — 冻结 OFF-A/OFF-B 身份候选的可复判证据边界

- `status`: `DONE`（`e0d92c3` 登记为 `QUEUED`，本次交付按交接第 1、6 项提升；提升理由见
  `promotion_reason`）
- `baseline_sha`: `ec082f3e749f14a21b7d7574252849bb929c6fbe`
- `registered`: 2026-09-24，由 `ADMIT-070-CASE-001` 的 `DONE` 触发：`order` 的前三个场景
  （在线认证拒绝 → 资源包拒绝 → 首快照负向）已各自在当前 build 上封出 `PASS`/`AGREES`
  的正式 bundle 并四读一致，交接阶段 C 的入口条件「ADMIT-070 正式 case 可复判」自此成立。
- `promotion_reason`: 交接第 6 项要求的顺序——先登记 `QUEUED` 并推送，再在下一张交付里提升——
  已在 `e0d92c3` 满足；两次推送之间没有插入任何未被授权的工作。提升条件也齐：`order` 前三场景
  四读一致、本地门禁全绿、两轴自审已记录，且本卡是设计卡（`LOCAL_ONLY`），不要求新的真实运行，
  也就没有可被高估的运行读数。
- `question`: OFF-A（`prism-parity`）与 OFF-B（`enum-aligned`）各自要封哪些工件才算
  OFFLINE-010/020/030 被证明，OFFLINE-030 的「A/B 分别加入」在「一个 run 只启动一个候选」
  的事实下由什么结构承载（两份材料还是一个 case 两个子 case），以及哪些判据必须由两次
  独立 run 各自封证、不能由判官读活目录里的另一份 run。
- `depends_on`: `ADMIT-070-CASE-001`（同一受控离线服务端与同一封存通道，本卡的运行形状沿用它的
  `JoinObserved`/首快照/ledger 读数）；`CORE-STATE-TRANSITION-001`；`OFFLINE-CANDIDATE-001`
  （它交付了 `--identity-candidate` 且证明可选值只有一个来源，但其 `still_open` 写着「真实运行
  仍需要一次客户端」——本卡就是把那两次真实运行变成可复判判据的那一步）。
- `scope`: 重读 `docs/p0-offline-session-compatibility-contract.md` 的 OFFLINE-010/020/030/040/050
  与 `docs/p0-remote-admission-contract.md` 的身份边界，确认 CLI `--identity-candidate` 的可选值
  确实由 `OFFLINE_SESSION_CANDIDATES` 单一清单导出；把两候选写成两列比较——真实 Session
  `AccountType` 与客户端警告、Bridge 上报的身份材料、argv 边界（`clientId`/`xuid` 的显式空元素
  与 option/value 错位）、服务端观察到的身份与 UUID、JOIN 与首快照——并逐条标明可信来源、
  待封存工件、判官字段与反例。既有 `offline-040`/`offline-050` 只覆盖声明侧，运行侧一半要
  在这张表里指名。
- `allowed_paths`: `docs/p0-offline-session-compatibility-contract.md`（新增「可复判证据边界」
  冻结小节）、`docs/development-execution-plan.md`、`docs/development-todo.md`；若拆分结论要求
  登记新 case fixture 与 `tools/check_case_assertions.py` 注册项，只登记为后续实现卡，不在本卡落
  registry 改动。
- `forbidden_paths`: 产品代码（尤其 `adapters/launcher/offline_session.py` 的身份材料与
  `candidate_by_id` 语义）、Bridge/`proto/`、case registry 的编号与 `mandatory` 翻转、
  required inventory 的既有 case ID、CI。
- `non_goals`: 不改身份算法、不挑一个「比较好」的候选作为唯一支持方式、不封任何 evidence、
  不声称 OFFLINE-010/020/030 已通过、不在本卡决定非空 sentinel 对照是否要跑（契约规定只有
  真实启动产生可归因失败时才跑）。
- `acceptance`: 两列比较逐格有可信来源，且每格写明「由哪一次 run 的哪一份工件证明」；凡跨 run
  比较的判据都给出「两份已封存材料」或「父子 case 拆分」两种形状之一并按 `CORE-060` 先例说明
  拆分与兼容语义；如果结论要求改 required inventory 的既有 case ID，必须先写出拆分规则、
  迁移语义与假阳性测试，才允许后续实现卡动 registry；后续实现卡逐张登记为 `QUEUED`。
- `validation_class`: `LOCAL_ONLY`（本卡是设计卡；真实运行属其后的封存卡）。
- `stop_conditions`: 若 OFF-B 在当前 build 上无法启动或启动后身份不可归因，保留真实失败并记为
  `BLOCKED_EVIDENCE`，不回退 OFF-A 后声称两者都过；若发现必须改产品身份材料才能冻结判据，
  停在该处并向用户请求决策，不在设计卡里改产品。
- `completion_commit`: `308f38ac37ab8c6e8731924bcba12dd5cf31b2bd`（契约冻结小节 + Case set 三行注记，
  已推送并核对）；两轴自审补明的那句 `identity_candidate_id` 说明与本次收卡、登记三张后续实现卡同在
  这个 docs commit 里，推送后由 `git ls-remote` 核对当前分支与 `main`。
- `completion_evidence`:
  - **交付物**：`docs/p0-offline-session-compatibility-contract.md` 新增
    「OFFLINE-010 / 020 / 030 的可复判证据边界（2026-09-24 冻结）」——先列出现在读不出来的那一件，
    再给九行两列（OFF-A `prism-parity` / OFF-B `enum-aligned`）比较表、五条冻结判据（每条带反例）、
    两次独立 run 的规则与 `OFFLINE-030` 拆分（含迁移语义与四条假阳性测试）；`OFFLINE-010/020/030`
    三行 Case set 注记指向该节，两个子 case id 在其中逐字出现（`OFFLINE-030-PRISM-PARITY-001` /
    `OFFLINE-030-ENUM-ALIGNED-001`），以满足 `tests/contract/test_case_coverage.py` 对逐字引用的要求。
  - **「读不出来」不是推测，是本 build 逐条对物核对的结论**：`adapters/bridge/perception.py:76` 把
    `snapshot.session_identity` 喂进 `admit_first_snapshot`；`domain/session_material.py` 的
    `SessionMaterialVerdict.as_document()` 在全仓库**没有调用者**（`grep` 只命中 `bundle.py`/`trace.py`/
    `launcher/*` 等同名方法）；`cli/session.py` 的 `BridgeHelloAccepted` payload 是 `{}`，
    `SessionStateTransitioned` 只有 `{from,to}`；真实 bundle 的 `asserter-inputs.json` 只有
    `kin_id/run_id/username/previous_run_id`。所以正向一致不留痕迹，只有不一致以
    `snapshot_rejections` 里的 `SESSION_MATERIAL_MISMATCH`（`domain/perception.py:305`）出现。
  - **`acceptance` 逐条**：两列表每格都写了「来源 → 工件 → 判官字段」并注明由哪一次 run 的哪份工件证明；
    跨 run 的两格（除 `userType` 外材料相同、A/B 结果对照）明确排除在单份 bundle 判据之外，并按
    `CORE-060`/`CORE-060-CLIENT-001`/`CORE-060-SERVER-001` 先例给出父子 case 形状；结论确实要求新增
    required id，因此先写拆分规则、迁移语义（不改名/不删除/不重编号既有 id，只有 `offline-030` 的
    fixture 重新登记）与假阳性测试，registry 改动留给后续实现卡。
  - **两轴自审**：规范轴发现一处契约原文与已交付实现的真实张力并就地补明——「Bridge回报与成功判据」
    的清单把 `identity_candidate_id` 列为客户端上报字段，而客户端不可能看见策略名（`ClientSnapshot`
    传的正是空串，`compare_session_material` 也只在「报了不同名字」时拒绝）。冻结的解决方式不是要求
    Bridge 改报（那要改 `proto/` 与产品，`forbidden_paths` 明令禁止），而是把候选归因交给 Core 的
    argv 记录 + Core 自己的账本行，并在该节补一句 2026-09-24 说明，避免两处文本被后来的人读成矛盾。
    实现轴自审：本卡只动允许的三份文档，未触碰产品代码、`proto/`、Bridge Java、case registry、
    required inventory、CI；未封任何 evidence（`OFFLINE-010/020/030` 的 `mandatory` 仍为 `false`）。
  - **门禁（原始摘要）**：`uv run --frozen pytest -q` → 2071 passed / 2 skipped in 258.30s
    （两个 skip 是既有的平台跳过：`test_orphans.py:686`、`test_silent_listener.py:123`）；
    Ruff check 无输出、`ruff format --check` 304 files already formatted；Pyright
    0 errors / 0 warnings / 0 informations；`verify_fixture_digests.py` → W00 schema and fixture
    digests: OK；`check_case_assertions.py` → OK (134 registered)；`check_workflow_pins.py` → OK；
    `check_boundaries.py` → OK。本卡是 `LOCAL_ONLY` 设计卡，不含新的真实运行；OFF-B 的启动可行性
    尚未在受控运行上验证，那属 `OFFLINE-IDENTITY-RUN-001`。`check_wheel_boundary.py` 仍需 CI 构建
    出的 wheel，不在本地门禁内（既有事实）。
  - **已验证**：契约新增节内部自洽（每条判据的字段名都与 `SessionMaterialVerdict.as_document()`、
    `SESSION_EVENT_TYPES` 现有词汇对得上或明确标为待新增）；`tests/contract/test_case_coverage.py`、
    `verify_fixture_digests.py`、`check_case_assertions.py`、`check_workflow_pins.py`、
    `check_boundaries.py` 与全量 `pytest` 在冻结文本落地后保持绿。
  - **未验证 / 遗留**：`OFFLINE-030` 拆分所需的 registry 与 fixture 改动（本卡按 `allowed_paths` 只登记
    不落地）；新账本行的实际字段名与脱敏扫描行为；两次候选各自的真实运行；`offline-030` fixture 的
    `case_version` 将由实现卡移动，历史 bundle 不追认。
- `next_after_done`: `OFFLINE-IDENTITY-LEDGER-FACT-001`（三张后续实现卡的第一张：Core 记录身份事实）。
  本卡 DONE 时它们只登记为 `QUEUED`，提升为唯一 `NEXT` 写在紧随的下一个 commit 里，以满足交接
  第 1、6 项「新卡先 `QUEUED`，不得直接 `NEXT`」。

### OFFLINE-IDENTITY-LEDGER-FACT-001 — 让 Core 把身份比对结论记成自己的账本行

- `status`: `DONE`（`4d2beb7` 登记为 `QUEUED`，`1f85155` 提升为唯一 `NEXT`，2026-09-24 交付完成）
- `promotion_reason`: 交接第 1 项要求的顺序已满足——先 `QUEUED` 登记并推送，再在紧随的交付里提升，
  两次推送之间没有插入别的未授权工作。入口条件也齐：判据已由 `OFFLINE-IDENTITY-EVIDENCE-DESIGN-001`
  冻结在专项契约（payload 的最小字段集与反例都写死了），本地门禁全绿，且它是其后两张卡的前置
  ——判据要读的字段先存在，`OFFLINE-IDENTITY-CASE-001` 才写得出断言、`RUN-001` 才封得出证据。
- `baseline_sha`: `4d2beb7766e11adc79bedaf3896a542a6ee60c9d`
- `question`: 把 `compare_session_material` 已经得出的 `SessionMaterialVerdict`（连同 Bridge 上报的
  观测）写成 Core 自己的一条账本行，需要动哪几处、payload 字段的最终名字是什么、以及为什么不去
  改 `BridgeHelloAccepted` 的 payload。
- `depends_on`: `OFFLINE-IDENTITY-EVIDENCE-DESIGN-001`（判据 2 规定了 payload 的最小字段集）；
  `ADMIT-060-WIRE-POLICY-001`（先例：`ResourcePackPolicyApplied` 这条链就是「Core 把一个逐次发生的
  事实记成自己的行」，形状可整条沿用）。
- `scope`: 沿既有四段接缝走——`adapters/bridge/admission.py:128` 的读取/解码、
  `cli/session_runtime.py:241/338/465` 的逐次回调、`cli/session.py:1417-1420` 的
  `append_session_event(...)`、`adapters/sqlite/session_log.py:43-86` 的封闭事件名集合；新行 payload
  至少含契约冻结判据 2 的七个字段并带 `session_id` 与 `generation`；一行一代，值取自 Bridge 上报与
  Core 记录，不写 argv 文本、不写 credential 正文。
- `allowed_paths`: `src/minekin_core/adapters/sqlite/session_log.py`（新事件名进封闭集合）、
  `src/minekin_core/adapters/bridge/{admission,perception,session_report}.py`、
  `src/minekin_core/cli/session.py`、`src/minekin_core/cli/session_runtime.py`、
  `src/minekin_core/domain/session_material.py`（只允许把已有结论导出成稳定字段名，不改比较语义）、
  其单元测试与 ledger 契约测试、`docs/development-execution-plan.md`、`docs/development-todo.md`。
- `forbidden_paths`: `bridge/src/main/java/**`、`proto/**`（客户端上报字段一个都不加）、
  `adapters/launcher/offline_session.py` 的身份材料与 `candidate_by_id` 语义、case registry 的编号与
  `mandatory` 翻转、`tests/fixtures/cases/**` 与既有断言源（移动别人的 `case_version` 属封证卡）、
  CI。
- `non_goals`: 不新增 offline fixture、不封 evidence、不做跨 run 比较的判据、不改
  `BridgeHelloAccepted` 与 `SessionStateTransitioned` 的 payload（往既有行里塞字段会让旧 bundle 的
  读数含义漂移；新事实用新行承载）。
- `acceptance`: ① 新事件名在 `SESSION_EVENT_TYPES` 封闭集合内，`source`/`trust_class` 都是 `CORE`；
  ② payload 字段名与契约判据 2 逐字对得上，`mismatches` 与 `matched` 不自相矛盾（矛盾形状有测试）；
  ③ credential 正文键在任何路径上都不进 payload/工件（脱敏测试）；④ `compare_session_material`
  返回值语义不变，旧 bundle 仍能 `replay` 且 `violations: []`；⑤ 一次受控运行（诊断级，不作 case
  封证）读出该行确实出现，字段与本次启动的 argv 归因一致。
- `validation_class`: `LOCAL_GATES` + 一次受控诊断运行（交接第 2 项：新记录路径要有本 build 的受控
  运行读数）。
- `stop_conditions`: 若发现必须让 Bridge 上报候选名才能冻结判据，停在 `BLOCKED_DECISION`（那是
  `proto/` 与产品策略，不属本卡）；若新增行必然移动既有 case 的 `case_version`，停下如实登记，
  不靠重写 `manifest.sha256` 过关。
- `completion_commit`: `ec8fb1506d127f2dfde850bbcbab685471b264a2`（产品代码与三份测试全在这一条；
  本节与 TODO 记录是紧随的收卡 commit，提升下一卡再往后一条——写下本节时那两次推送尚未发生）。
  已推到 `refs/heads/codex/core-state-transition` 与 `refs/heads/main`，`git ls-remote` 读到两条都等于
  上面那个 sha。
- `completion_evidence`:
  - **实现形状（沿 `ResourcePackPolicyApplied` 那条链，四段各自落在一处）**：
    `domain/session_material.py` 末尾新增 `identity_ledger_record(recorded, reported, verdict)`，
    只把已有结论导出成稳定字段名，`compare_session_material` 一个字节没改；
    `cli/session_runtime.py` 新增可选回调 `on_session_identity(generation, record)`，在
    `_admit_first_snapshot` 里**算出 admission 之后、按 verdict 行动之前**触发，因此为一侧非身份原因
    被拒的快照同样交出比对；`cli/session.py` 的 `on_session_identity` 把它记成
    `SESSION_IDENTITY_COMPARED`，`source=EventSource.CORE` / `trust_class=TrustClass.CORE`；
    `adapters/sqlite/session_log.py` 新增事件名并进 `SESSION_EVENT_TYPES`（封闭集合现为 14 个名字）。
    没有改 `adapters/bridge/admission.py`：结论已在 `SnapshotAdmission.session` 里，多一跳是绕路。
  - **payload 字段（判据 2 的七个观测字段逐字沿用，另加两格结论与两格定位）**：
    `identity_candidate_id`、`session_username`、`session_uuid`、`observed_account_type`、
    `client_id_present`、`xuid_present`、`credential_values_exposed`、`matched`、`mismatches`，
    CLI 记录器再补 `session_id` 与 `generation`，共 11 个键。UUID 保留上报时的编码形式，因为
    「到达的是哪种形式」正是 `OFFLINE-040` 要问的问题。
  - **`acceptance` 逐条**：
    ① 名字在封闭集合内且两格都是 `CORE`——`tests/unit/test_session_supervision.py` 的全量账本断言把
    `(SESSION_IDENTITY_COMPARED, "CORE", "CORE")` 钉在 `JOIN_OBSERVED` 与 `PLAYABLE_ESTABLISHED` 之间。
    ② 字段名与判据 2 逐字对得上，且「矛盾形状有测试」——契约测试钉住一份 `matched=False` 的记录，其
    `mismatches` 恰为 `["report_incomplete","username","uuid"]`（漏报的字段与因此对不上的字段同时出现，
    不被归并成一个原因）；单元侧另有
    `test_a_refused_comparison_is_recorded_as_plainly_as_an_agreeing_one`。
    ③ credential 正文键在任何路径上都不出现——`test_the_record_has_no_field_that_could_hold_a_credential_body`
    把键集钉成**集合相等**而不是子串规则，将来一个新名字带进 token 也会红。
    ④ 比较语义不变、旧 bundle 仍能 `replay` 且 `violations: []`——本 build 下对 ADMIT-070 attempt 2
    bundle（run `2a128d0dd30b4932b88ada6d0032d40c`，digest `88ccc9dfc820…`）读数：
    `evidence verify` → `result: PASS` / `verified: true` / `violations: []`，
    `rejudge_evidence.py` → `status: agrees` / `result: PASS`，
    `python -m minekin_core replay` 与 `tools/replay_evidence.py` → 都 `status: projected`、
    `events: 16`、`trace_sha256 cf724e39aa69…`、`violations: []`。判官断言源未改，`case_version` 未移动。
    ⑤ 见下面「受控诊断读数」。
  - **受控诊断读数（交接第 2 项；两次都不作 case 封证，`MINEKIN_DOMAIN_CASE` 未设）**：
    run `6fbc61e47f4743cd9de10ee21f71f1f9` / session `e7a5a1feff45490685a7e75a4832f027`
    （服务端目录 `run-127`，命令行 `--identity-candidate enum-aligned`）与 run
    `c2dea6ce3bc14652b0f9f1bab98d3969` / session `f2b689e7c7ff44feba4f5ca3c81b02e2`
    （`run-128`，不带该参数即默认 `prism-parity`）。两次都到达 `PLAYABLE`、
    `snapshots_admitted: 1`、`snapshot_rejections: []`，各自主动停客户端后以 `BRIDGE_LOST` / 退出码 14
    收场（按既有政策，14 不是判据）。`/data/kin/kin-01/kin.sqlite3` 的 `event` 表里各有一行
    `SessionIdentityCompared`（`pos=1113` 与 `pos=1132`），两次都夹在 `JoinObserved` 与
    `PlayableEstablished` 之间，`source=CORE` / `trust_class=CORE`：
    `enum-aligned` 那次是 `{"identity_candidate_id":"enum-aligned","observed_account_type":"LEGACY",
    "session_username":"Kin","session_uuid":"8f40376b-c23f-3ef1-b553-5564eea75639","matched":true,
    "mismatches":[],"client_id_present":false,"xuid_present":false,"credential_values_exposed":false}`；
    `prism-parity` 那次除 `identity_candidate_id` 外材料相同，而 `observed_account_type` 是 `""`。
    归因跟着本次启动的 argv 走（默认与显式各读出自己的候选名），观测字段跟着客户端上报走（同一次
    差异里 `LEGACY` 与 `""` 不同名），两格不是互为抄写——这正是判据 1 反例「把 argv 里的词抄进观测字段」
    要排除的形状。argv 本身只以 `argv_digest` 落账（`8a01f2f0de7c…` 那次的 `SessionProcessStarted`），
    文本没进任何行。
  - **两轴自审**：规范轴发现一处必须写清的偏差——本卡 `scope` 原文写「一行一代」，实现是
    **一次首快照比对一行**（契约测试里同一 generation 出三行）。这不是放宽：同一代里先被拒后被接受
    正是要留两行的形状，压成一行会丢掉「第一次读到了什么」。判据落点因此继承 `ADMIT-070` 那条教训
    （`ec082f3` 的「closure criterion 要读真的那一行」），已写进下一卡的 `depends_on`。实现轴自审：
    只动了 `allowed_paths` 里的四份产品文件与三份测试；`proto/`、`bridge/src/main/java/**`、
    `adapters/launcher/offline_session.py`、case registry、`tests/fixtures/cases/**`、既有断言源与 CI
    一个字节未改（`git show --stat ec8fb15` 只有 7 个文件）；`BridgeHelloAccepted` 与
    `SessionStateTransitioned` 的 payload 保持原样，属本卡 `non_goals`；未封任何 evidence，
    `OFFLINE-010/020/030` 的 `mandatory` 仍为 `false`。
  - **门禁（原始摘要，最终树）**：`uv run --frozen pytest -q` → **2076 passed / 2 skipped in 227.32s**
    （较基线 +5：`test_session_material.py` 四条、`test_session_runtime.py` 一条；两个 skip 仍是既有的
    平台跳过 `test_orphans.py:686`、`test_silent_listener.py:123`）；Ruff check 无输出；
    `ruff format --check` → 304 files already formatted；Pyright 0 errors / 0 warnings / 0 informations；
    `verify_fixture_digests.py` → W00 schema and fixture digests: OK；`check_case_assertions.py` →
    OK (134 registered)；`check_workflow_pins.py` → OK；`check_boundaries.py` → OK。
    `check_wheel_boundary.py` 仍需 CI 构建的 wheel（既有本地缺口）。
  - **已验证**：新行在真实 Fabric 客户端 + 真实 Bridge + 真实 SQLite 账本里确实出现且只按本次启动归因；
    旧 bundle 的四种读数在新 build 下不改判；回调在拒绝路径上同样触发（契约层）；键集不含可容纳凭据
    正文的名字（单元层）。
  - **未验证 / 遗留**：契约判据作为**断言**去读这一行（属 `OFFLINE-IDENTITY-CASE-001`）；OFF-A/OFF-B
    各自在新 build 上的封证 bundle（属 `OFFLINE-IDENTITY-RUN-001`）；`OFFLINE-030` 父子拆分所需的
    registry/fixture 改动与随之移动的 `offline-030` `case_version`（本卡按 `forbidden_paths` 未动）；
    Linux 上逐字节复现 Bridge jar 仍欠。
- `next_after_done`: `OFFLINE-IDENTITY-CASE-001`（`order` 第 4 个场景的第二张：把判据写进判官与
  fixture）。本卡 DONE 时它已作为 `QUEUED` 登记在案，提升为唯一 `NEXT` 写在紧随的下一个 commit 里，
  以满足交接第 1、6 项「新卡先 `QUEUED`，不得直接 `NEXT`」。

### OFFLINE-IDENTITY-CASE-001 — 把 OFFLINE-010/020/030 的判据写进判官与 fixture

- `status`: `DONE`（`4d2beb7` 登记为 `QUEUED`，`ad8d482` 提升为唯一 `NEXT`，2026-09-24 交付完成）
- `promotion_reason`: 顺序已满足——先 `QUEUED` 登记并推送，再在紧随的 commit 提升，中间没有插入别的
  未授权工作。前置 `OFFLINE-IDENTITY-LEDGER-FACT-001` 已 `DONE`（`ec8fb15`）且判据 2/3/4 要读的字段
  已在真实账本里读出过；入口门禁全绿；它是 `OFFLINE-IDENTITY-RUN-001` 的前置，判据先落地才封得出证据。
- `baseline_sha`: `f897451470c01baf8b7c469fd8354ff0e85ec305`
- `question`: 契约冻结的五条判据在 `tools/assert_case_evidence.py` 里各由哪条断言承载，`OFFLINE-030`
  的父/子拆分在 registry、fixture、digest 与 `check_case_assertions.py` 注册项上具体怎么落地。
- `depends_on`: `OFFLINE-IDENTITY-LEDGER-FACT-001`（判据 2/3/4 要读的字段先存在。它交付的是
  **一次首快照比对一行**、不是一行一代，所以判据必须自己指定读哪一行——沿用 `ADMIT-070` 那条
  「closure criterion 要读真的那一行」的教训 `ec082f3`）；
  `OFFLINE-IDENTITY-EVIDENCE-DESIGN-001`（判据文本、反例、拆分与假阳性测试都在那一节）。
- `scope`: 先在 `tests/unit/test_case_evidence_assertions.py` 写出反例表（含契约列出的
  「把 argv 里的 `offline`/`legacy` 抄进观测字段冒充观测」「credential 正文键出现即失败」
  「只有 argv 没有 Core 的行」「只有 Core 的行」），再写四条拆分假阳性测试，最后才动 registry：
  `src/minekin_core/domain/cases.py` 新增两个 required id、`tests/fixtures/cases/offline-030.json`
  按收窄后的语义重新登记、`offline-030-prism-parity.json` 与 `offline-030-enum-aligned.json` 两份
  新 fixture 及各自的 `tests/fixtures/manifest.sha256` 行、`tools/check_case_assertions.py` 注册项。
- `allowed_paths`: `tools/assert_case_evidence.py`、`tests/unit/test_case_evidence_assertions.py`、
  `tests/fixtures/cases/offline-010.json`/`offline-020.json`/`offline-030*.json`（新建与重新登记）、
  `tests/fixtures/manifest.sha256`、`src/minekin_core/domain/cases.py`（只新增 id）、
  `tools/check_case_assertions.py`（注册项）、`tests/contract/test_case_coverage.py`（只读它，需要
  放宽时如实记录）、`docs/p0-offline-session-compatibility-contract.md`（Case set 行的状态注记）、
  `docs/development-execution-plan.md`、`docs/development-todo.md`。
- `forbidden_paths`: 产品代码、Bridge/`proto/`、runner 脚本与领域运行分支（属 `RUN-001`）、
  `tools/seal_run_evidence.py`（封存时把 `session_argv` 交给 live 判读那一行属
  `OFFLINE-IDENTITY-SEALED-ARGV-001`；本卡只实现从封存 bundle 读的判据一侧，并把 live 侧缺口如实
  记进证据，不越界改它）、
  既有 case id 的改名/删除/重编号、任何 `mandatory` 翻转为 `true`、旧 bundle 的 `manifest.sha256`
  与历史 digest。
- `non_goals`: 不封 evidence、不声称 `OFFLINE-010/020/030` 已通过、不在本卡跑真实客户端。
- `acceptance`: ① 五条判据各有域内实现与反例，`run_repo_case.py` 对每份新 fixture 都能跑出可判读的
  结果；② 四条拆分假阳性测试先红后绿，且证明一份 OFF-A bundle 逐条喂给 OFF-B 的归因判据必须失败；
  ③ `offline-030` 的 `case_version` 移动被如实记录，其历史 bundle（若存在）只读作 `UNJUDGED`，
  不回改；④ 两个子 id 在 required 清单里、在契约里逐字出现，只满足其一时另一条仍出现在
  `report_cases.py` 的 `missing`；⑤ 全量门禁绿。
- `validation_class`: `LOCAL_GATES`。
- `stop_conditions`: 若拆分与既有 inventory 测试的假设冲突到必须改别的 case，停下记录冲突；
  若某条判据在当前读数形状下无法写成不返工的断言，保留判据缺口并向主控请求决策，不放宽判据。
- `completion_commit`: `2a84bbdb8aee20ce93d3b4bf65371237e1097336`（五条断言、五份 fixture、两个 required
  id、`check_case_assertions.py` 注册项、`manifest.sha256` 五行与契约 Case set 注记全在这一条；本节与
  TODO 记录是紧随的收卡 commit，提升下一卡再往后一条——写下本节时那两次推送尚未发生）。已推到
  `refs/heads/codex/core-state-transition` 与 `refs/heads/main`，`git ls-remote` 读到两条都等于上面那个 sha。
- `completion_evidence`:
  - **五条判据 → 五条断言，一字对应**：判据 1 `this_run_started_the_identity_candidate_the_case_names`、
    2 `core_recorded_the_identity_it_compared`、3 `the_reported_session_is_the_identity_this_run_launched_with`、
    4 `the_account_type_was_recorded_as_an_observation`、5 `the_offline_identity_joined_and_the_server_agrees`。
    分发即拆分：`OFFLINE-010`/`OFFLINE-020` 各拿 1/2/3/4（候选无关的第 5 条不在这里，那要一次入服），
    `OFFLINE-030` 只拿 5，两个子 id 各拿 1/2/3/5。父 fixture 的断言集合里没有 1，所以「一份 bundle
    同时证明两列分别加入」在 registry 这一层就读不出来。
  - **判据 1 的两半**：argv 侧读 `orchestrator-trace.json` 里的 `session_argv`（新常量
    `ORCHESTRATOR_TRACE_ARTIFACT`），Core 侧读 `SessionIdentityCompared` 的 `identity_candidate_id`。
    四种「问不出是哪一列」各有自己的拒绝：整份 bundle 没封存 trace ⇒ `LAUNCH_ARGV_UNRECORDED`；
    argv 里没点名 ⇒ `CANDIDATE_NOT_NAMED_IN_ARGV`（`candidate_by_id(None)` 回退到第一列，所以没点名
    不等于不知道，而是等于默认值——归因必须拒它）；点名两次 ⇒ `CANDIDATE_NAMED_TWICE_IN_ARGV`；
    点了不存在的候选 ⇒ `CANDIDATE_NOT_REVIEWED`。trace 缺席与 argv 空是两回事，这一点由
    `test_a_bundle_that_sealed_no_trace_recorded_no_argv_rather_than_an_empty_one` 钉住。
  - **判据 2/3/4 共用同一个「读哪几行」的答案**（`_identity_comparisons`）：前置卡交付的是一行一次
    比对，所以读全部行并要求逐格一致（`ROWS_DISAGREE`）；`position/session_id/generation` 刻意不进
    比较元组——同一 session 的两次比对正是只在这三格上不同。单行内部 `matched` 与 `mismatches` 互证
    （`ROW_CONTRADICTS_ITSELF`），credential 正文键出现即 `CREDENTIAL_BODY_KEY:<key>`（键名取自产品的
    `SECRET_CLASSIFICATION`，值是什么都不影响拒绝）。
  - **判据 4 只问记录在不在**：`LEGACY` 与空串在这里同样绿，哪一列真会得到什么是那两次运行要回答的。
    它拒的是抄来的字——该行点名的候选的 `--userType` 原词出现在观测字段里判
    `ACCOUNT_TYPE_COPIED_FROM_THE_LAUNCH_ARGUMENT:<word>`，而另一列的原词仍是合法观测（OFF-A 上报
    `legacy` 是它在说实话）。整格缺失时它答 `ACCOUNT_TYPE_NOT_RECORDED` 而不是 `OBSERVATION_FIELD_MISSING`：
    缺口正是它的发现，2/3 那两条读同一形状时才仍按结构损坏拒绝。
  - **`acceptance` 逐条**：
    ① 五份 fixture 各跑得出一份可判读的 `run_repo_case.py` 结果：`INCOMPLETE` + 每条断言
    `NO_IMPLEMENTATION`，与 `ADMIT-070` 同形——运行材料判据在纯仓库运行下的正确读数就是「这里没有
    跑得动的东西」，不是判据缺失。
    ② 四条拆分假阳性测试先红后绿，且证明了一份 OFF-A bundle 逐条喂给 OFF-B 归因判据必须失败：
    `test_one_columns_bundle_cannot_answer_the_other_columns_attribution`、
    `test_the_parent_join_case_asserts_nothing_about_which_column_was_launched`、
    `test_both_children_are_required_and_one_of_them_is_still_missing_without_the_other`、
    `test_each_child_carries_a_case_version_of_its_own`。
    ③ `offline-030.json` 在本次登记之前**不存在**（交付前的 `9ffe980` 上
      `git log 9ffe980 -- tests/fixtures/cases/offline-030.json` 为空），所以这一行从来没有 bundle，它
      `case_version` 的移动没有历史证据要读作 `UNJUDGED`。这条
    验收因此是空转成立的，如实记下，不用它冒充防回归。
    ④ 两个子 id 现在同时在 `REQUIRED_CASES` 与契约里逐字出现（`CORE-060` 的先例照搬），
    `report_cases.py` 的 `present` 含两者、各自 `unregistered: []`，`missing` 里已无 OFFLINE-010/020/030；
    W30 的 inventory 现为 13 required / 8 present / 5 missing（缺的是 060-100）。
    ⑤ 全量门禁：`uv run --frozen pytest -q` 2140 passed / 2 skipped（两个既有平台性 skip）、
    ruff check 与 format --check 干净、pyright 0 errors、case assertions OK（139 registered）、
    fixture digests OK、boundaries OK、workflow pins OK、`git diff --check` 干净。本卡新增 19 个测试
    函数：五条判据各自的反例表、credential 正文键的参数化、跨列归因与父子 fixture 的防回归、
    外加读路与封存通道的两条；参数化展开后比上一卡基线多收 64 条用例（2076 → 2140）。收卡时重跑
    可复现的三件：`tools/check_case_assertions.py`（139 registered）、fixture digests 与五份
    fixture 的 `run_repo_case.py`——后者逐份返回 `INCOMPLETE` / 每条断言 `NO_IMPLEMENTATION`
    （没有真实 bundle 可读，正是预期的拒绝形状）。
  - **未闭合与限制**：
    - **live 侧仍缺那一格 argv**：`tools/seal_run_evidence.py:664` 把 run 交给 `read_run_material` 时
      不传 `session_argv`，所以判据 1 今天只在**复判**这条读路上成立，封存现场的 live 判读会读到
      `LAUNCH_ARGV_UNRECORDED`。本卡按 2026-09-24 确立的纪律没有顺手改它（那张卡把它列进
      `forbidden_paths`），而是登记成 `OFFLINE-IDENTITY-SEALED-ARGV-001`。
    - **一次已经避免的越界**：实现中一度让 `ADMIT-070` 的
      `the_first_snapshot_was_refused_by_the_reason_the_case_names` 改用新的共用 helper 读
      `snapshot_rejections`，`--record` 随即移动了 `tests/fixtures/cases/admit-070.json` 的
      `assertion_digests`——那会让已封的 ADMIT-070 `PASS` bundle 在 `rejudge` 下变成不可判
      （`tools/rejudge_evidence.py:130` 拿 `case_version` 比对）。断言本体已恢复原样，共享 helper
      只服务新判据，理由写进了 helper 的 docstring：**sealed 案例的断言函数体本身就是版本化的证据**。
      核对方式是收卡前 `git status` 里 `tests/fixtures/cases/admit-*.json` 一律无改动。
    - 五条判据从未见过真实 bundle（本卡 `non_goals`），`OFFLINE-010/020/030` 及两个子 id 的
      `mandatory` 全部仍为 `false`；`evidence/` 下没有新增、修改或重封任何 bundle。
- `next_after_done`: `OFFLINE-IDENTITY-SEALED-ARGV-001`（把那份 argv 交进 live 判读，判据 1 才在封存
  现场成立）→ `OFFLINE-IDENTITY-RUN-001`（OFF-A 与 OFF-B 各自封证并四读一致）。

### OFFLINE-IDENTITY-RUN-001 — 两次受控运行：OFF-A 与 OFF-B 各自封证并四读一致

- `status`: `DONE`（在 `9ffe980` 之前就已是 `QUEUED` 并推送；收卡 `OFFLINE-IDENTITY-SEALED-ARGV-001`
  的 `07cd0d7` 之后由 `14784a1` 提升为唯一 `NEXT`，2026-09-24 两列各封出一份 `PASS` bundle）。
  **这个 `DONE` 不含判据 5**：本卡验收 ① 里「各自满足契约判据 1/2/3/5」那句在写卡时把两列 case 的
  断言集与两个 `OFFLINE-030-*-001` 子 case 的混成了一回事——被本卡封的 `OFFLINE-010`/`OFFLINE-020`
  各自承载的是 1/2/3/4（`CASE-001` 的收卡证据就写着「本节前四条判据各有……一条断言承载」），
  1/2/3/5 是子 case 的形状，而子 case 目前**封不进 harness**（原因与新卡见 `unmet_acceptance`）。
  按 `stop_conditions` 的同一精神——不把没发生的事合并宣称完成——这里只宣称被真字节支持的那部分。
- `promotion_reason`: 顺序已满足——本卡先以 `QUEUED` 登记并推送，前置 `CASE-001`（`2a84bbd`）与
  `SEALED-ARGV-001`（`d8348a3`）都在提升之前交付并收卡，中间没有插入别的未授权工作。入口门禁全绿
  （`2144 passed / 2 skipped`、case assertions 139 registered、Pyright 0 errors）。
  `SEALED-ARGV-001` 收卡时欠下的那一半验收 ①——判据 ① 在一次真实受控运行上的 live 判读与 rejudge
  同结论——由本卡承接，已写进下面的 `acceptance`。
- `baseline_sha`: `07cd0d7dd8d5798af42f344e88eb4344235c3961`
- `why_now`: 这条链的最后一张：判据先存在（`CASE-001`）、那份 argv 先交进 live 判读
  （`SEALED-ARGV-001`），现在才谈得上封出「两个读者同读一份材料」的真实证据。
  **提升时同时记下本卡面对的一个阻碍**：`depends_on` 里那句「同一 runner、同一 domain 场景」在今天
  并不成立——`test-orchestrator/runner/domain.sh` 里没有任何 OFFLINE 场景分支（`identity-candidate`
  与 `offline-0` 两项 grep 均为空），而本卡 `forbidden_paths` 不许改 runner 的等待与封存逻辑。
  本卡第一步因此按 `allowed_paths` 允许的形状走：在受控 loopback 环境里直接起 Core
  （带上 `--identity-candidate <列>`），再用现成 CLI 封存——`tools/seal_run_evidence.py` 早就收
  `--session-argv`，`SEALED-ARGV-001` 之后它会把它一并交给判官——全程不改脚本。若这条直路走不通
  （例如没有 runner 的等待分支就读不到入服那一侧的事实），**不顺手改 runner**：按「先修订卡片范围
  再动手」那条纪律另起一张 runner 场景分支的前置卡、以 `QUEUED` 登记并推送，再回到本卡。
- `question`: 在同一个受控离线服务端、同一份封存通道上，`--identity-candidate prism-parity` 与
  `--identity-candidate enum-aligned` 各封出一份 `PASS`/`AGREES` 的 bundle，需要哪些运行形状与读数。
- `depends_on`: `OFFLINE-IDENTITY-CASE-001`（`DONE`，`2a84bbd`：判据与 fixture 先存在）；
  `OFFLINE-IDENTITY-SEALED-ARGV-001`（`DONE`，`d8348a3`：live 判读要把 argv 交给判官，见下）；
  `ADMIT-070-CASE-001`
  （同一 runner、同一 domain 场景与同一「两次独立 run 各自封证」的封存通道——OFFLINE 场景分支本身
  并不在这张已 `DONE` 的卡里，见 `why_now`）。
- `scope`: 两跑各领新 `run_id`/attempt，各自 `evidence verify` → `rejudge` → 两个 `replay` →
  `report_promotion`，并把 `observed_account_type` 的**实际值**如实记录（不预设、不为「A 与 B 应该
  不同/相同」而重跑挑数据）；OFF-B 无法启动或身份不可归因时保留真实失败。
- `allowed_paths`: 受控运行与只读判官、`docs/development-execution-plan.md`、
  `docs/development-todo.md`、`docs/p0-offline-session-compatibility-contract.md`（Case set 行的
  封证状态注记与 `OfflineSessionProfile.v1` 的候选字段填入）。
- `forbidden_paths`: 产品代码、Bridge/`proto/`、runner 的等待与封存逻辑（需要改则回到实现卡）、
  case registry 与 `mandatory` 翻转、旧 bundle、任何非受控目标（运行者自备的公网 offline 测试服
  ——地址记于 `.tmp/local-test-server.txt`——已被判为
  `REJECTED`，不得作为目标或 oracle，也不得向它发送任何凭据）。
- `non_goals`: 不挑「比较好」的候选、不决定 OFF-C/OFF-D/非空 sentinel 是否跑（契约规定只有真实启动
  产生可归因失败时才跑）、不宣布 OFFLINE 族整体完成（`060/070/080/090/100` 不在本卡）。
- `acceptance`: ① 两份 bundle 的 case 身份/version/`verified`/`passed`/re-judge/replay/promotion 四个
  读者一致，且各自满足契约判据 1/2/3/5；② 从 `SEALED-ARGV-001` 承接的那一半验收：头一次真实封证上，
  判据 ① 在**封存现场的 live 判读**与对该 bundle 的 **rejudge** 给出同一结论——既不是
  `LAUNCH_ARGV_UNRECORDED`（那说明 argv 没交进去），也不是两侧给出不同的拒绝理由（那说明两条读路
  又分叉了）；这一条要在两列上各自成立，缺一列就如实记一半；两列对照结果写回契约由人读，不做成单份
  bundle 的判据。
- `validation_class`: `REAL_RUN`。
- `stop_conditions`: 同一外部阻断连续三次重现则记 `BLOCKED_EVIDENCE` 并停在该分支；任一候选被封成
  `PASS` 而另一候选失败时，只报告一半通过，不合并宣称 `OFFLINE-030` 完成。
- `completion_commit`: 本卡不交付代码，仓库内唯一的改动是 `docs/p0-offline-session-compatibility-contract.md`
  的三条注记（`OFFLINE-010`/`OFFLINE-020`/`OFFLINE-030` 三行的封证状态）与本节、TODO 记录，都在
  这一条 docs commit 里；证据本体在 runner 数据卷 `minekin-runner-data:/data/kin/kin-01/run/evidence/`
  下的两个 bundle 目录，digest 逐条列在下面。
- `completion_evidence`:
  - **两跑都用现成通道，`why_now` 记下的阻碍没有触发**：`bash test-orchestrator/runner/run.sh domain
    session start --profile … --server-profile … --identity-candidate <列>`，`MINEKIN_DOMAIN_CASE`
    分别设为 `OFFLINE-010`/`OFFLINE-020`。Core 参数是 `domain.sh` 的 `REMAINDER`，封存时由
    `domain.sh:1923` 原样作为 `--session-argv` 交给 sealer——`SEALED-ARGV-001` 那条通道第一次在真实
    运行上走到。全程未改 runner、未改产品代码、未动 registry。
  - **OFF-A**：run `f2ecb728df754826abf4a052be138a2d`、server 目录 `/data/server-runs/run-129`、
    session `d852ccf0ffde42cba3edc25bd72d5766`、`argv_digest 0f4bff0d…`、ledger 里 `PLAYABLE`
    （run document：`snapshots_admitted 1`、`entities_admitted 6`、`snapshot_rejections []`；
    其自身 `status` 是 `started`、`recovery.status` 是 `reconciled`——`PLAYABLE` 不在 run document
    的状态字段里，别把它读成那回事）。封存的
    `orchestrator-trace.json` 里 `session_argv` 末尾两项是 `--identity-candidate prism-parity`。
    seal：`attempt.sequence 1`、`supersedes_run_id null`、13 件工件、`result PASS`、`failures []`、
    `case_version 78053e9e31bfba6c15b4a768db5fd22c50f70c11ebfb133d7202996fd95db02b`、
    bundle digest `184d636cf028cd05eaf61ca36706ad8aa4576780c4c01e041f07c6f82728ed20`；
    封存现场 `evidence verify` 为 `verified: true` / `violations []`。
  - **OFF-B**：run `3d5606ced37849e3b17a4c418fa33ab4`、server 目录 `/data/server-runs/run-130`、
    session `6e92b314ba0e4ec69ece37b5437cbc2f`、
    `argv_digest e26e5661…`、ledger 里 `PLAYABLE`（run document `snapshots_admitted 1`、
    `entities_admitted 10`、`snapshot_rejections []`）；
    seal：`PASS`、`failures []`、`attempt.sequence 1`、13 件工件、
    `case_version ff451ea358546639d8718485b9cec60dccc72cfce4e3eff2bd3055265c469cd0`、
    bundle digest `ff68f67d51ba15afc35efafd89ca8781f31b0a02ed60ea9d9a10b9a2d7de45d8`。
  - **四个读者一致（验收 ① 的前半）**：两份 bundle 各跑 `rejudge` → `disagreements: []`、重判
    `PASS` 且 4 条断言的 expected/observed 逐位相同；`python -m minekin_core replay` 与
    `tools/replay_evidence.py` 都退出 0、19 事件、投影 `STOPPED`；`tools/report_promotion.py` 里两行
    都是 `PASS` / `verified: true` / `sealed: true` / `re_judged: AGREES` /
    `from_repository_build: true`（该工具的整体结论仍是 `blocked`，因为 41 条 mandatory case 还没封完，
    与本卡无关）。两次的 `bundle.bridge_digest` 同为 `faeec4a9df83abb9ca0404863e04d20cfd87ac0f3afd5e74b6858e3e15372f55`、
    `launch_plan_digest` 同为 `9e0e0ccca9d0a589a38a3f3be40ddbf957f71a51cffe08caf5436153954bfea4`。
  - **验收 ②（承接 `SEALED-ARGV-001` 的那一半）在两列上都成立**：判据 ① 的 live 判读与同一 bundle 的
    rejudge 给同一结论（都是 `PASS`，都没有 `LAUNCH_ARGV_UNRECORDED`）。另在**真字节**上补了两次对照：
    反事实——同一份封存材料把 `session_argv` 换成 `None` 再判，得到
    `FAIL this_run_started_the_identity_candidate_the_case_names:LAUNCH_ARGV_UNRECORDED`，说明 PASS 真的
    来自那份 argv 而不是「什么都不读也算过」；跨列——`OFFLINE-020` 的 case 读 OFF-A 的 bundle →
    `FAIL ARGV_NAMES:prism-parity`，`OFFLINE-010` 读 OFF-B 的 bundle → `FAIL ARGV_NAMES:enum-aligned`。
  - **`observed_account_type` 的实测值（不预设，按 `scope` 如实记录）**：OFF-A 的
    `SessionIdentityCompared`（generation 1，一行）payload 是
    `{"identity_candidate_id":"prism-parity","observed_account_type":"","session_username":"Kin",
    "session_uuid":"8f40376b-c23f-3ef1-b553-5564eea75639","matched":true,"mismatches":[],
    "client_id_present":false,"xuid_present":false,"credential_values_exposed":false}`；
    OFF-B 同一形状、同一 username/uuid，只有 `identity_candidate_id` 是 `enum-aligned` 且
    `observed_account_type` 是 `LEGACY`。两列 manifest 的 `identity.server_observed_name_uuid` 都是
    `Kin/8f40376b-c23f-3ef1-b553-5564eea75639`、`identity.configured_profile` 都是
    `bundle-p0-core-1.21.4.json#bb45606023cea201`。**由此产生的一个决策留给主控**：契约晋级条件 2 写的是
    「AccountType 被明确记录」，而判据 4 只保证这个键被记录且是观测值——OFF-A 读到的是**存在但为空串**。
    空串算不算「明确记录」是人读，本卡不替它下结论，也没为此重跑或挑数据。
  - **退出码语义**：两次 `run.sh domain` 都以 14（`BRIDGE_LOST`）结束，那是 harness 主动停客户端造成的，
    不是任一 bundle 的 verdict；verdict 只来自 seal 报告与四个读者。
  - **本地门禁**：本卡没有代码改动，收卡时跑的是快门禁并按原样绿——
    `verify_fixture_digests.py`（`W00 schema and fixture digests: OK`）、
    `check_case_assertions.py`（`OK (139 registered)`，即移动过的 digest 数为 0）、
    `check_boundaries.py`、`check_workflow_pins.py`、`git diff --check`。
- `unmet_acceptance`: 验收 ① 的**判据 5 那一半没有发生**，而且不是「读了但没通过」：
  `OFFLINE-030` 的父 case 与两个 `OFFLINE-030-*-001` 子 case 目前**封不进 harness**。
  `domain.sh:172` 把 `MINEKIN_DOMAIN_CASE` 直接小写当 fixture 文件名，于是
  `OFFLINE-030-PRISM-PARITY-001` 会去找 `offline-030-prism-parity-001.json`，而 `CASE-001` 登记的
  真实文件叫 `offline-030-prism-parity.json`（`-001` 是 required-case id 的后缀，不是文件名的一部分）。
  两条出路都不在本卡边界内：改 `domain.sh` 撞上 `forbidden_paths`，改 fixture 名或 registry id 又是
  `CASE-001`/registry 的范围。**按「先修订任务卡范围再动手」的纪律，本卡不就地 hack**，把这件事记成
  一张新卡 `OFFLINE-030-CASE-FILENAME-001`（`QUEUED`，见本节下方登记），判据 5 的封证随它走。
  在下一张卡真封出 bundle 之前，`OFFLINE-030`（父与两子）在 `report_promotion.py` 那一侧仍读作
  「没有 bundle」——`report_cases.py` 只看 fixture 在不在 registry 里，那三个 id 早就 `present`，
  两张工具别混着读。
- `recorded_limits`: ① 两列的**跨列对照**（同一 username、同一 UUID、只有 `userType` 不同）仍是人读，
  没有任何单份 bundle 判它——那是契约写死的边界，本卡没有绕过；② 本卡只覆盖 OFF-A/OFF-B，
  OFF-C/OFF-D/非空 sentinel 与 `OFFLINE-060/070/080/090/100` 都不在此；③ Linux 上逐字节复现当前
  Bridge jar 仍欠（既有遗留，与本卡无关）。
- `next_after_done`: `OFFLINE-030-CASE-FILENAME-001`（判据 5 的封证入口）。本卡 DONE 时它只以 `QUEUED`
  登记并推送，提升为唯一 `NEXT` 写在紧随的 commit 里，以满足交接第 1、6 项。

### OFFLINE-030-CASE-FILENAME-001 — 让 `-001` 子 case 的 id 能被 harness 找回自己的 fixture

- `status`: `DONE`（`5267399` 以 `QUEUED` 登记并推送，由 `277e601` 提升为唯一 `NEXT`；范围修订在
  `2d56a07`，交付在 `cf9b387`，本 commit 收卡，2026-09-24）
- `promotion_reason`: 顺序已满足——登记它的那张卡（`OFFLINE-IDENTITY-RUN-001`）在 `5267399` 收卡并
  推到两条 ref，本 commit 之前计划里没有 `NEXT`，中间没有插入别的未授权工作。入口门禁全绿
  （`verify_fixture_digests.py`/`check_case_assertions.py` 139 registered/`check_boundaries.py`/
  `check_workflow_pins.py` 均 OK，`git diff --check` 干净），且阻断本身在提升前对物复核过
  （三份 fixture 文件名 vs `cases.py` 三个带 `-001` 的 id）。
- `baseline_sha`: `526739902c098223d0e7e840e8200c1b4b46bbb0`
- `question`: `MINEKIN_DOMAIN_CASE` → fixture 文件名这条派生规则要怎么改，才能让
  `OFFLINE-030-PRISM-PARITY-001` / `OFFLINE-030-ENUM-ALIGNED-001` 各自跑起来并封证——是 runner 侧改成
  「从 registry 查 fixture 路径」，还是 fixture 侧改用带 `-001` 的文件名？两条路各自的代价与对
  `tests/fixtures/manifest.sha256`、`check_case_assertions.py` 注册项、历史 `case_version` 的影响。
- `depends_on`: `OFFLINE-IDENTITY-CASE-001`（`DONE`，`2a84bbd`：两个子 id 与 fixture 都在那里登记）；
  `OFFLINE-IDENTITY-RUN-001`（`DONE`：阻断在它收尾时实测出来，且它没有就地 hack）。
- `why_now`: 契约判据 5 是 OFFLINE 族里唯一还缺真实 bundle 的一条，而它缺的原因不是读不出、也不是
  发生不了，是**名字对不上**——这是最便宜的一类阻断。名字对上以后，判据 5 的封证形状与
  `RUN-001` 完全相同（同一 runner、同一封存通道、`--identity-candidate` 已在 argv 里）。
- `allowed_paths`: **不再是待定卡**——动手前对两条路各自核了一遍，选定 **fixture 侧改名**，runner 侧解析
  划掉。翻转登记时倾向的依据是一条写错的前提：登记时以为「改名会移动已登记 fixture 的 `case_version`」，
  而 `src/minekin_core/domain/cases.py:731-733` 的 `digest` 是 `json.dumps(document, sort_keys=True)` 的
  sha256——只看 manifest 的内容，文件名不参与；两份子 fixture 的 `inputs` 为空，内容里也没有钉自身路径
  （`assertion_digests` 钉的是判官源码）。所以改名不动 `case_version`，也就不会事后作废任何已封 bundle
  的可判读性。真正会动的只有 `tests/fixtures/manifest.sha256` 里那两行的**路径**（digest 值不变），而那
  是一个门禁自证的评审文件：漏改一行，`verify_fixture_digests.py` 同时报 `unlisted frozen file` 与
  `stale entry`。
  允许改动：`tests/fixtures/cases/offline-030-prism-parity.json` →
  `offline-030-prism-parity-001.json`、`tests/fixtures/cases/offline-030-enum-aligned.json` →
  `offline-030-enum-aligned-001.json`（`git mv`，内容字节一字不改）、`tests/fixtures/manifest.sha256`
  （只换那两行的路径）、`tests/unit/test_case_registry.py`（验收 ③ 的约定测试写在这里——它已经是唯一
  拿真实 `tests/fixtures/cases/` 目录跑 `load_case_registry` 的测试文件）、
  `tests/unit/test_case_evidence_assertions.py`（`:5405-5406` 两个常量随文件名移动，别的不动）、
  `docs/development-execution-plan.md`、`docs/development-todo.md`、
  `docs/p0-offline-session-compatibility-contract.md`（Case set 行注记）。
  划掉的那条是 `test-orchestrator/runner/domain.sh` 的 case→fixture 解析：它要给一条**除这两个文件以外
  全都成立**的约定（`tests/fixtures/cases/` 下 43 份 fixture，41 份的文件名等于其 `case_id` 小写，另外
  两份就是本卡要改的）永久多加一套机制；而且 `domain.sh` 在 Windows 侧的 pytest 里不便单独执行，反例测试
  只能改成在 Python 里镜像一遍小写规则——那是第二份真相。改名反而是把约定补全，并用一条测试把它钉住。
- `forbidden_paths`: 产品代码、Bridge/`proto/`、既有 case id 的改名/删除/重编号、任何 `mandatory`
  翻转、旧 bundle 与其 digest、runner 的等待逻辑（`RUN-001` 已证明不需要它）。
- `non_goals`: 不在本卡顺手判 OFFLINE-060/070/080/090/100，不重跑 `RUN-001` 已封的两列证据。
- `acceptance`: ① 两个子 id 各封出一份 `PASS`/`AGREES` bundle 并四读一致；② 「改名不动证据」这条依据是
  实测而不是断言：两份子 fixture 在改名前后的 `load_case_manifest(...).digest`（即 `case_version`）逐字相同，
  `manifest.sha256` 只有两行的路径部分变化、其 digest 值不变；③ 一条把约定钉住的测试——`tests/fixtures/cases/`
  里每份 fixture 的文件名必须等于它自己声明的 `case_id` 小写，且 registry/required 的每个 id 至多找回一份
  fixture。今天的两份 `-030-*` 文件要让这条测试在改名**前**红、改名后绿；一个不存在于该目录的 id 读作
  「找不到」而**不是**静默指向一个空文件（正是 `domain.sh:172` 现在会做的事，本卡按选定的路不给它加机制）。
- `validation_class`: `REAL_RUN`。
- `stop_conditions`: 若两条路都要动 registry 语义（即 `cases.py` 里 id 与 fixture 的关系本身要说清），
  停下并向主控请求决策，不自行选一条。**未触发**：选定的路（fixture 改名）不碰 registry 语义，
  `cases.py` 一字未改，id 与 fixture 的关系仍由那份小写约定表达。
- `completion_commit`: `2d56a07`（动手前修订卡片范围：把 `allowed_paths` 从「二选一」写成
  选定的 fixture 侧改名，并记下翻转到时的依据为何不成立）+ `cf9b387`（交付）。
- `completion_evidence`:
  - **改动路径全在修订后的 `allowed_paths` 内**：`tests/fixtures/cases/offline-030-prism-parity.json` →
    `offline-030-prism-parity-001.json`、`tests/fixtures/cases/offline-030-enum-aligned.json` →
    `offline-030-enum-aligned-001.json`（两份都是 `git mv`，`similarity index 100%`，内容字节未改）、
    `tests/fixtures/manifest.sha256`（只有那两行的路径字段变了）、
    `tests/unit/test_case_registry.py`（两条新测试）、
    `tests/unit/test_case_evidence_assertions.py`（只换 `:5405-5406` 两个常量）、
    以及 `docs/development-execution-plan.md`/`docs/development-todo.md`/本契约。**未改**：
    `test-orchestrator/runner/domain.sh`、`src/minekin_core/`（含 `cases.py`）、任何 case id、
    任何 `mandatory` 字段、任何旧 bundle。
  - **验收 ②（改名不动证据，实测）**：改名前后分别用 `load_case_manifest(...).digest` 读同一份内容，
    得到的 `case_version` 逐字相同——OFF-A 子 case `229750d9f27555bc5c75065d504ee08e7c98c43ea22f403c2f4725a76688ece7`、
    OFF-B 子 case `377aa638e36a20cf3c81cd11b23eafebf70c4f61040a6be004a4d688b95db870`，与随后真跑封出的
    两份 bundle 里的 `case_version` 字段一致（见下）。`manifest.sha256` 那两行的 digest 值不变
    （`84ed4701d123d505…`/`2cda33aff35c6ad0…`），漏改即 `verify_fixture_digests.py` 会同时报
    `unlisted frozen file` 与 `stale entry`；它在本次收卡门禁里报 `OK`。
  - **验收 ③（把约定钉住的测试，红→绿）**：`test_every_reviewed_case_is_filed_under_the_name_its_id_derives`
    在改名**前**跑过一次，结果为 `1 failed, 2 passed`（失败项正是那两份 `offline-030-*` 文件）；改名后绿。
    `test_a_case_with_no_fixture_is_reported_absent_rather_than_judged_from_nothing` 把另一半年报清楚：
    把一个 required 子 id 的 fixture 从目录里搬走，registry 读作 `child not in registry.by_id()` 且它出现在
    `registry.requirement("W30").absent` 里——即「找不到」，不是静默指向一个空文件。
  - **验收 ①（两个子 id 各封一份 `PASS`，四读一致）**：都在当前 reviewed build 上真跑真封，
    attempt 均为 1、`supersedes_run_id: null`。
    OFF-A/`OFFLINE-030-PRISM-PARITY-001`：run `ee9d5ad3d57344da8452069102e27216`、
    session `7696999c3d1143ad80c4e154e7239f8f`、server 目录 `run-131`、
    `argv_digest 2c328d39ccbc8469…`、bundle `cdb8e53f67d54d5171b2d23741a20d5351bb59c1c7136ffa2f3a53c5d4734295`。
    OFF-B/`OFFLINE-030-ENUM-ALIGNED-001`：run `cb5e2119845e41868c28e5aeb1370ce3`、
    session `0f0850c198ed4e8ba3b6473c4a74e04c`、server 目录 `run-132`、
    `argv_digest 528c4981e6065c15…`、bundle `b90cb29b664a872133ffec208634723e37330c357f8876390b17eee2093ee90e`。
    两份都：封存现场 `result PASS`、`failures []`、四条断言 expected==observed、13 件工件、
    `verified: true`、`violations []`。四个读者：① 封存现场判读（上列）；② `tools/rejudge_evidence.py`
    `status: None`、`disagreements: []`，重判结果仍 `PASS` 且四条断言齐；③ replay 两路都 exit 0、
    各投影 19 个事件（`python -m minekin_core replay` 与 `tools/replay_evidence.py`，bundle digest 与封存一致）；
    ④ `tools/report_promotion.py --work-package W30` 里两条 case 各读作
    `result PASS`、`sealed: true`、`verified: true`、`re_judged: AGREES`（`re_judge_reason` 空）、
    `from_repository_build: true`、`attempt_sequence 1`，且 `bridge_digest faeec4a9df83abb9ca0404863e04d20cfd87ac0f3afd5e74b6858e3e15372f55`、
    `launch_plan_digest 9e0e0ccca9d0a589a38a3f3be40ddbf957f71a51cffe08caf5436153954bfea4` 与
    `OFFLINE-010`/`OFFLINE-020` 那两列同一。该报告对 W30 整体仍 exit 1，因为包里还有未封的 case，
    不是这两条的 verdict。
  - **判据 5 要的两端身份证据在同一份 bundle 内各自可读**（不是跨 run 拼出来的）：服务端侧
    `online-mode=false`、`Kin joined the game`、usercache `Kin/8f40376b-c23f-3ef1-b553-5564eea75639`；
    客户端侧 `connection_state PLAYABLE`、`snapshots_admitted 1`、`snapshot_rejections []`。
    封存材料里 `identity.configured_profile` 两列都是 `bundle-p0-core-1.21.4.json#bb45606023cea201`、
    `server_observed_name_uuid` 都是 `Kin/8f40376b-…`。
  - **退出码语义**：两次 `run.sh domain` 都以 14（`BRIDGE_LOST`，run document 里
    `outcome: BRIDGE_LOST`、`session_state: STOPPED`）结束，那是 harness 主动停客户端造成的，
    不是任一 bundle 的 verdict；verdict 只来自 seal 报告与四个读者。
  - **反例在真字节上跑过**（不是测试构造的假材料）：`OFFLINE-030-PRISM-PARITY-001` 的 case 判 OFF-B 那份
    bundle → `FAIL this_run_started_the_identity_candidate_the_case_names:ARGV_NAMES:enum-aligned`，
    反向 → `…:ARGV_NAMES:prism-parity`；把同一份材料的 `session_argv` 换成 `None` 再判 →
    `FAIL …:LAUNCH_ARGV_UNRECORDED`。这三条与 `RUN-001` 那两列的反例形状一致，说明改名没有把归因判据
    变成永真。
  - **本地门禁**（收卡时在当前工作树重跑，含本次文档改动）：`uv run --frozen pytest -q` →
    `2146 passed / 2 skipped in 316.19s`；`ruff check . -q` exit 0；`ruff format --check .` →
    `304 files already formatted`；`pyright` → `0 errors, 0 warnings, 0 informations`；
    `verify_fixture_digests.py` → `W00 schema and fixture digests: OK`；`check_case_assertions.py` →
    `OK (139 registered)`（改名移动过的 digest 数为 0）；`check_boundaries.py` OK；
    `check_workflow_pins.py` OK；`git diff --check` 干净。
  - **两轴自审**：规范轴——本次仅有 `git mv`、两行路径、两个常量与测试/文档，依赖方向未变
    （`check_boundaries.py` 绿），无新增抽象；规格轴——契约的迁移语义写着「没有既有 case id 被改名、
    被删除或被重新编号」，本次一个 id 都没动，动的只是承载它的文件名，因此 `OFFLINE-001/010/020/040/050`
    的 fixture 与 digest 行逐字未变。发现的唯一自审问题是登记卡片时那条「改名会移动 `case_version`」
    的前提本身读错（`cases.py:731-733` 的 digest 只看 manifest 内容），已在动手前以 `2d56a07` 显式
    纠正并记录，而不是静默换路。
- `recorded_limits`: ① 父 `OFFLINE-030` 以自己的 id **仍没有 bundle**：它唯一那条断言已在两份子 bundle
  里逐条判过，再封一份只是同一材料的子集，本卡因此没有为它跑第三次；`report_promotion.py` 里查不到
  `case_id: OFFLINE-030` 的条目，这是事实而不是工具缺陷。② `domain.sh` 的小写派生规则没有被 Python 侧
  镜像（那会造第二份真相）；约定测试钉的是 fixture 目录的命名，若将来 runner 的派生规则要变，仍需
  在 runner 自己的范围内做。③ 改名后 `offline-030-*` 两个子 case 的历史 bundle 本来就不存在，所以
  这次没有任何旧证据要读作 `UNJUDGED`；若将来某个已封 case 的文件名再动，这条前提不再成立，要重新核。
  ④ Linux 上逐字节复现当前 Bridge jar 仍欠（既有遗留，与本卡无关）。
- `next_after_done`: 本卡收完后，campaign `order` 的下一个场景是**第 5 个（crash/outbox 窗口）**，
  而计划里**没有**任何已登记的卡覆盖它。按交接第 1 项（新卡先 `QUEUED`、不得直接 `NEXT`），
  紧随的两个 commit 各做一件事：登记 `CRASH-OUTBOX-EVIDENCE-DESIGN-001`（`QUEUED`），然后把它
  提升为唯一 `NEXT`。该卡的产物是判据冻结，不是封证；先例是 `ADMIT-070-EVIDENCE-DESIGN-001` 与
  `OFFLINE-IDENTITY-EVIDENCE-DESIGN-001`。`ADMIT-070-RECORD-SCHEMA-001` 仍 `QUEUED` 且自述不在
  这条链上；`VERSION-AUTO-DESIGN-001` 与 HOST/PERSIST 一族仍需主控决策，未排入。

### CRASH-OUTBOX-EVIDENCE-DESIGN-001 — 冻结 crash / outbox / restart 窗口场景的完整判据

- `status`: `DONE`（`bd0448a` 以 `QUEUED` 登记，`d33c236` 提升为唯一 `NEXT`，交付在 `72aec3e`，
  本 commit 收卡并在同一 commit 以 `QUEUED` 登记它要求的封存卡）
- `promotion_reason`: 顺序已满足——登记它的那张 commit（`bd0448a`）在它之前已由 `7c8c412` 把
  `OFFLINE-030-CASE-FILENAME-001` 收为 `DONE` 并推到两条 ref，`bd0448a` 只做登记、没写 `NEXT`，
  本 commit 之前计划里没有 `NEXT`，中间没有插入别的未授权工作。入口门禁在收卡时全绿
  （`2146 passed / 2 skipped`、ruff check/format、Pyright 0 errors、case assertions 139 registered、
  fixture digests、boundaries、workflow pins、`git diff --check` 干净），本卡是纯文档设计卡，
  不需要新的真实运行入口。它是 campaign `order` 第 5 个场景当下唯一的入口：阶段 D 的入口条件
  （「OFF-A/B 证据闭合」）由 `OFFLINE-IDENTITY-RUN-001` 与 `OFFLINE-030-CASE-FILENAME-001` 满足。
- `registered`: `bd0448a`（`QUEUED`）
- `blocked_by`: 无（前置卡 `OFFLINE-030-CASE-FILENAME-001` 已 `DONE`：campaign `order` 的第 4 个场景
  五条判据都有真实 bundle，阶段 D 的入口条件——「OFF-A/B 证据闭合」——成立）
- `baseline_sha`: `7c8c412512b5d27e80e1b552733d820eaad95d99`
- `question`: `REAL-P0-CAMPAIGN-001.order` 的第 5 个场景（crash/outbox 窗口）**要封什么才算闭合**。
  逐项说清这几件事，各自落在哪个 case id、读哪件封存工件、以及能不能由**当前 harness** 真跑出来：
  ① 已被现有 bundle 覆盖的窗口（`CORE-060` 的 runtime/server/client 三个进程边界、`CORE-090` 的
  「先杀 Core 再重启」恢复对）各证到哪一半，本场景因此**不该**再重复跑什么；
  ② 仍缺的具体窗口按 [Qoder 交接](qoder-execution-handoff.md) 阶段 D 那份列表逐项核对：正常退出、
  已写 effect intent 但未 settle、客户端/服务端强杀、重启重验、未决 outbox；
  ③ 其中「崩溃落在启动窗口（`session start` 已记下 `START_CLIENT` 意图、还没 settle 效果）」这一半，
  `MINEKIN_DOMAIN_KILL_CORE` 是否**按构造**就打不中——`development-todo.md` 已记过一次尝试：
  加过 `KILL_CORE=early`，实测它从来不可能早于 playable，于是把开关删掉而不是留一个名字在说谎的选项
  （`domain.sh:26`、`:1233` 那一段是当前的读法，需复核）。如果确实打不中，本场景就**不**把它伪装成
  真实 Minecraft 运行：按阶段 D 那句话标为本地证据（真 SQLite + 故障注入单测），并把「真实运行未覆盖」
  写进契约与 promotion 读法；
  ④ 若要让它真能被驱动，需要的是 runner 侧的哪一种显式等待点（而不是产品代码的哪一种新策略），
  以及该改动应落在哪张后续卡的 `allowed_paths` 里——本卡只登记需要，不顺手改 runner。
- `depends_on`: `OFFLINE-IDENTITY-RUN-001`（`DONE`，`5267399`）与 `OFFLINE-030-CASE-FILENAME-001`
  （`DONE`，`cf9b387`）——阶段 D 的入口条件由这两张共同满足。判据要落的契约是
  `p0-validation-evidence-contract.md` 第 7/10 条（`CORE-060`、`CORE-090`）与 W70 那一段。
- `why_now`: campaign `order` 里它的下一个就是这一个，而它和第 4 个场景不同——**没有任何已登记的卡**
  覆盖它，计划因此在本卡登记前没有可执行的下一张。先冻结判据再跑真实故障，是第 3、4 个场景已经走过
  两遍的顺序（`ADMIT-070-EVIDENCE-DESIGN-001`、`OFFLINE-IDENTITY-EVIDENCE-DESIGN-001`）；反过来先跑
  会重演 `ADMIT-070` 那次的浪费：跑到一半才发现要封的东西读不出来。
- `allowed_paths`: 纯设计卡，只允许改 `docs/development-execution-plan.md`、
  `docs/p0-validation-evidence-contract.md`（第 7/10 条与 W70 段落的判据注记）、
  `docs/qoder-execution-handoff.md`（阶段 D 那一节的「仍缺哪些窗口」清单按实测更正；该文档此前多张卡
  都不在允许路径里，本卡明确把它写进来是因为要改的正是阶段 D 那一段）、
  `docs/development-todo.md`。**不改** `test-orchestrator/`、`src/`、`tools/`、`tests/`。
- `forbidden_paths`: 产品恢复策略（`application/recovery_service.py`、`domain/recovery.py`）、
  runner 的等待逻辑、任何 case fixture、任何旧 bundle；`Launcher` 不得当成第四个独立进程造虚假故障角色
  （阶段 D 原文）；任何自动接管/终止的选择——那属于 `PROCESS-RECOVERY-001` 的 `BLOCKED_DECISION`。
- `non_goals`: 不封本场景任何证据（封证随后续卡走）、不重跑第 4 个场景已封的 OFF-A/OFF-B、不动
  `CORE-090`/`CORE-060` 现有 case 的 `mandatory`（改判据是后续卡的事，且点亮门禁要契约先说清）、
  不做第 6/7 个场景（tick/render 采样、promotion report）的设计。
- `acceptance`: ① 冻结结论写进上述契约与计划，逐窗口给出：由哪个 case id 承载（现有或新登记）、
  读哪些**已封存工件**、当前 harness 能否真跑出来、不能时它属于本地证据还是完全未覆盖；
  ② 每个「需要新登记卡」的窗口当场登记成卡（先 `QUEUED`），并写清各自 `allowed_paths` 边界，
  尤其 runner 侧与产品侧不得混在同一张；③ 一条诚实的结论必须能被读出来：如果本场景在当前
  harness 下**没有**任何新的真实运行可封（全部落在已有 bundle 或本地证据里），就直接写出来并把
  campaign 该场景改判为「按构造受限于 harness」，同时登记解它的卡或向主控请求决策——不允许为了
  推进而虚构一个窗口；④ 冻结前先读当前 `domain.sh` 的 kill/held 路径并给出行号依据，不引用过期描述。
- `validation_class`: `LOCAL_ONLY`（本卡是设计卡，只产文档与判据；真实运行属其后登记的封存卡）。
- `stop_conditions`: ① 若冻结判据要求**新增或改写产品恢复策略**（重放/失效/接管语义），立即停下并
  请求主控决策，不自行定；② 若需要改 `forbidden_paths` 里任何文件，先修订本卡范围再动手（2026-09-24
  纪律），不得事后追认；③ 若同一窗口在现有 `CORE-060`/`CORE-090` 与其子 case 里已经封过、
  而契约与 fixture 对「是否重复」说法不一致，停下并记录冲突，不自行选一种读法。
- `completion_commit`: `72aec3e5852782627a6e563edf6b4ba7957c7dee`（`docs(contract): freeze which crash
  windows the harness can reach`——冻结本体落在那一份契约文档；本 commit 只收卡并登记紧随的封存卡）
- `completion_evidence`:
  - ①逐窗口的四件事写进了 `docs/p0-validation-evidence-contract.md:198-246` 那张六行表：五个**已定义**
    窗口各自落在现有 case id 上（`CORE-060` 的 runtime 边界、`CORE-060-CLIENT-001`、
    `CORE-060-SERVER-001`、`CORE-090` 的崩溃后重启、正常退出那半在 `CORE-020` 的
    `leave_after_join_observed`），每行给出判据读哪些**已封存工件**、当前 harness 靠哪个开关跑得出来
    （`MINEKIN_DOMAIN_KILL_CORE` 在 `domain.sh:26/1233`、`MINEKIN_DOMAIN_KILL_SERVER` 在 `:30/1316`、
    `MINEKIN_DOMAIN_KILL_CLIENT` 在 `:36/1389`；`CORE-090` 是 `development-todo.md:529` 记过的那副
    两连跑形状），以及**当前 build 上有没有证据**——答案是五行全为「无」。第六行是启动窗口那个
    pending outbox：它**没有 case id，按契约也不该有**，承载读法只有本地证据那一列。
  - ②需要新登记卡的窗口当场登记：`CRASH-OUTBOX-RESEAL-001` 在本 commit 以 `QUEUED` 登记，
    `allowed_paths` 只有文档（计划/契约/TODO/交接），因为重封**不需要改任何代码**——case id、断言、
    runner 开关、封存通道都已存在。runner 侧与产品侧没有混进同一张：那张卡显式禁止改
    `test-orchestrator/`、`src/`、`tools/`、`tests/`。启动窗口那一半**没有**登记卡，理由记在契约里
    （阶段 D 本来就授权把它标为本地证据；要把它变成真实运行的两条路，一条是在产品代码里插停顿——
    为封证改被测物，冻结时拒绝；另一条是从外部把被 spawn 的客户端拖慢（`MINEKIN_JAVA`，
    `src/minekin_core/config.py:21`，在 `bootstrap.py:113` 解析）——未实测，将来要走须另起一张
    `allowed_paths` 含 `test-orchestrator/` 的卡先测）。
  - ③诚实结论按验收要求写成两句，而不是一句含糊的「已覆盖」：本场景缺的**不是定义**（六行都读得出
    来），也**不是**「当前 harness 什么真实运行都封不了」——五个已定义窗口都能在今天的 runner 上真跑，
    只是没有一份 bundle 在当前 reviewed build 上；所以缺的是「重封」，归 `CRASH-OUTBOX-RESEAL-001`。
    加上启动窗口那一半按构造打不中、只归本地证据。campaign 第 5 个场景因此仍不计为已封，
    `scenario_progress` 保持 4/7。
  - ④冻结前逐行重读过当前文件，没用旧描述：`domain.sh:24-28`（三个 kill 开关）、`:363-380`
    （`--hold-at` 只是被解析成 `hold_at`，`domain.sh:365/378`，不暂停任何进程）、`:1233-1266`
    （kill 块，等待条件在 `:1250`——要的是**不同横坐标数 ≥ 2**，不是「到 playable」）、
    `src/minekin_core/cli/session.py:719-721`（`open_effect(START_CLIENT)`）先于 `:723`
    （`supervisor.start`），settle 在成功路径 `:750`、失败路径 `:734`；本地证据那两个坐标
    `tests/unit/test_recovery_service.py:236`（真 `sqlite3.connect`）与 `:339`（真
    `SessionEventLog(...).open_effect(...)`）；`KILL_CORE=early` 在代码里零残留。
  - 旧 bundle 一律不追认，且这条读法是**量出来的**：五案各有一份旧 `PASS`（`CORE-060`
    `6b6dcdf7…`、`CORE-060-SERVER-001` `652043a6…`、`CORE-060-CLIENT-001` `e00f2851…`、`CORE-090`
    `c993c801…`、`CORE-020` `79ac9a14…`）加一份保留的旧 `CORE-060` `FAIL` `6d4bf5eb…`，
    `tools/report_promotion.py` 对它们全给 `from_repository_build: false`，`bridge_digest` 是
    `580daa9332e9f9b9…` 或 `f02741f58b0b20d0…`，而本 build 是 `faeec4a9df83abb9…`；五案的
    `case_version` 全部移动过（表里五对短 digest），因此对今天的 case version 读作
    `re_judged: UNJUDGED`，reason 逐字为「the criteria moved, so the recorded verdict answers a
    question this repository no longer asks」——原样留着，不重判、不改写、不充当闭合。
  - 门禁（纯文档，未跑 Minecraft）：full pytest `2146 passed / 2 skipped in 518.56s`、
    `ruff check . -q` exit 0、`ruff format --check .` `304 files already formatted`、
    `pyright` `0 errors, 0 warnings, 0 informations`、`check_boundaries` OK、
    `check_case_assertions` OK（139 registered）、`verify_fixture_digests` OK、`check_workflow_pins` OK、
    `git diff --check` 干净。
  - 收卡前把写进契约的那串 digest **又量了一遍**（这次不靠容器里的报告工具，直接对着卷与 registry）：
    五份旧 bundle 的 `manifest.json` 里 `case_version` 逐字为
    `30ac59a0641b…`/`d4850165e578…`/`e8d03e1b4a26…`/`4b0ba8550622…`/`090c8253e6b8…`，
    `bridge_digest` 为 `f02741f58b0b20d0…`（`CORE-060`、`CORE-020`）或 `580daa9332e9f9b9…`
    （三份 `CORE-060-*`/`CORE-090`）；当前 fixture 经 `load_case_manifest` 算出的五个 digest 逐字为
    `d1ea32d8b705…`/`50ca1ae2e22d…`/`dc85eb043861…`/`88fa467d8896…`/`7c01d11ed1e9…`，
    与表里那五对完全一致，也确认了「`from_repository_build: false`」这条不是工具脾气而是 bridge digest
    真的不同（本 build 是 `faeec4a9df83abb9…`）。六份里五份 `result: PASS`、保留的那份旧 `CORE-060`
    `FAIL` 仍是 `FAIL`。
- `recorded_limits`: ① 本卡没封任何证据，第 5 个场景在当前 build 上仍**零** bundle——冻结的产出是
  一张待办卡和一份读数，不是闭合。② 「从外部拖慢被 spawn 的客户端能否打开启动窗口」未实测：
  `MINEKIN_JAVA` 是否只作用于客户端那一侧、慢 spawn 会不会同时改掉这轮所观察的东西，都没有读数。
  ③ `CORE-090`/`CORE-020` 的 `mandatory` 未动——契约第 10 条要的是「正常退出 + 崩溃恢复」两半齐才点亮
  门禁，而翻 `mandatory` 属 promotion 场景（第 7 个）的判据，不在本卡范围。④ 数据卷上那五份旧 bundle
  的 `case_version` 差集是从当前 registry 反推的（fixture 钉判官源码 digest），没去逐一复算历史
  build 的判官；⑤ Linux 上逐字节复现当前 Bridge jar 仍欠（既有遗留）。
- `next_after_done`: `CRASH-OUTBOX-RESEAL-001`（本 commit 以 `QUEUED` 登记，由紧随的 commit 提升为
  唯一 `NEXT`）——它是 campaign `order` 第 5 个场景当下唯一的入口。其后的第 6/7 个场景（tick/render
  采样、CORE/OFFLINE/ADMIT promotion report）各自还需要设计卡，未排入本链。`ADMIT-070-RECORD-SCHEMA-001`
  仍 `QUEUED` 且自述不在封证链上；`VERSION-AUTO-DESIGN-001` 与 HOST/PERSIST/retention/process-recovery
  一族仍需主控决策。

### CRASH-OUTBOX-SEALED-KIN-001 — 让「没有文档的一次 run」也能说出它属于哪个 Kin

- `status`: `DONE`（`c75865b` 以 `QUEUED` 登记并推送、`3427e43` 提升为唯一 `NEXT`；交付 `2160989`
  `fix(tools): name the Kin of a run that left no document`，已推送 `codex/core-state-transition` 与
  `main` 两条 ref，`git ls-remote` 核对均为 `2160989a3dc882292bbd76ff8a9d2e10832a5ca5`。出口门禁全绿：
  full pytest `2158 passed / 2 skipped in 266.18s`（登记时 2147，本卡新增 11 条）、`ruff check` exit 0、
  `ruff format --check` `304 files already formatted`、Pyright `0 errors, 0 warnings, 0 informations`、
  boundaries OK、case assertions `OK (139 registered)`、fixture digests OK、workflow pins OK、
  `git diff --check` 干净（只有 Windows checkout 的 CRLF 提示，diff 里无换行符改写）。
  登记 commit 纯文档，入口门禁全绿：full pytest
  `2147 passed / 2 skipped in 323.89s`、`ruff check` exit 0、`ruff format --check` `304 files already
  formatted`、Pyright `0 errors, 0 warnings, 0 informations`、boundaries OK、case assertions
  `OK (139 registered)`、fixture digests OK、workflow pins OK、`git diff --check` 干净）
- `acceptance_readings`: ① **真实被杀 Core 的运行封得下来**——`CORE-060`，run id
  `08f206bfaed94e4f9a22aed82c1c24d6`，`MINEKIN_DOMAIN_KILL_CORE=1 MINEKIN_DOMAIN_PROBE=Kin
  MINEKIN_DOMAIN_PROBE_SECONDS=1 --hold-forward-seconds 60`（`MINEKIN_KIN_ID=kin-01` 显式给出，卷上有
  两个 Kin）。transcript 走到那条回落并只说了该说的：`session exited 137` →
  `the run document said Killed` → `domain: /tmp/domain-session.json holds no run document, so this run
  is named by its ledger id`（**没有**「没有 Kin」那句，因为名字传到了）。封存结果
  `status: sealed`、`attempt_sequence: 1`、bundle 落在
  `/data/kin/kin-01/run/evidence/08f206bf…`；只读探针数出 15 件工件、其中**没有**任何 run-document
  工件（`orchestrator-trace.json` 是 harness 自己的），`asserter-inputs.json` 说出
  `kin_id: kin-01` / `run_id: 08f206bf…` / `previous_run_id: 082e0f04…`。判据给出
  `result: FAIL`（`RELEASE_NOT_LOGGED`、`NEVER_MOVED:0.10`）——本卡不要求 PASS，两读数原样交 RESEAL。
  另外三读：`evidence verify` → `verified: true, sealed: true, violations: []`；
  `rejudge_evidence.py` → `status: agrees`（**从 `asserter-inputs.json` 取回 Kin**，不去问卷）；
  `report_promotion.py` → 这一份是当前 build 上第一份 `from_repository_build: true` 且
  `bridge_digest: faeec4a9df83abb9…` 的 `CORE-060`，`re_judged: AGREES`。
  ② 文档与传入名字同时存在且不一致时按文档为准：`test_the_document_s_own_kin_is_the_one_that_is_read_when_both_are_given`
  与 `test_the_document_s_own_kin_is_the_name_a_handed_one_cannot_overrule`（判官侧与封存侧各一条）。
  ③ 两句话各有测试：`test_a_run_that_nothing_names_is_still_refused_for_the_run`（缺 run）与
  `test_an_ambiguous_volume_with_no_name_anywhere_refuses_by_naming_the_kin` /
  `test_the_command_refuses_an_unnamed_kin_and_says_which_name_is_missing`（缺 Kin，且断言报错里
  **不再**出现「run id」）。④ `case_version` 一个没动：`check_case_assertions.py` 仍
  `OK (139 registered)`、`verify_fixture_digests.py` 仍 OK，`CORE-060` 的 `d1ea32d8b705…` 与真跑封出的
  manifest 一致。⑤ 门禁见上。卷上那份单 Kin 回落也没被撤：
  `test_one_kin_on_the_volume_is_still_read_without_anyone_naming_it` 钉着它。
- `stop_conditions_outcome`: 三条都没触发——没有要求更新任何 `case_version`（①）；Kin 只有**一份**记载：
  runner 从账本读，判官解析一次，`asserter-inputs.json` 封存那一次的结果，rejudge 读回它
  （②，`tools/rejudge_evidence.py` 因此一字未改，故不在本卡范围内也没去改）；`kin-02` 目录与它两份
  bundle 没被触碰，也没需要触碰（③）。
- `promotion_reason`: 顺序已满足——登记它的 `c75865b` 只写 `QUEUED`、没写 `NEXT`，本 commit 之前计划里
  没有 `NEXT`，中间没有插入别的未授权工作。它挡在 campaign 第 5 个场景上：`CORE-060` 的第二次真实
  attempt（run id `082e0f0420fc426ca8156bc9d5c91d11`）已经把 `--run-id` 那条回落走到，剩下的就是这一格。
- `registered`: `c75865b`（`QUEUED`）
- `baseline_sha`: `431ba840e74390e50b823f9fe6e5bc912949e54c`
- `blocked_by`: 无
- `question`: 一次被杀掉 Core 的 run 只剩账本里那个 `run_id` 可命名，而封存面**从数据卷的目录结构**
  去猜它属于哪个 Kin——`tools/assert_case_evidence.py:551-557` 在文档没说出 `kin_id` 时，取
  `<data-root>/kin/*` 下**恰好一个**持有 `kin.sqlite3` 的目录。这个前提在 2026-09-20 那次
  （`07e68af`）成立，在 `kin-02` 出现之后就不成立了：卷上现在有 `kin-01` 与 `kin-02` 两个
  （`kin-02` 是 join 场景留下的，它下面还有两份封存 bundle，`35fa702d…`/`8280d880…`，不得触碰）。
  于是 `read_run_material` 走到 `:558` 抛出
  「no run is named: neither a run document nor a run id」——那句话说的两件事都没缺（run id 就在参数里），
  真正缺的是 Kin 的名字，而它被同一句话盖住了。这张卡要回答的是：**要让封存现场怎样被明白地告知
  这次 run 属于哪个 Kin，才既不猜目录、也不让 runner 编一个名字出来？**
- `why_now`: 它是 campaign 第 5 个场景当下唯一的硬阻断。守卫那半（`domain.sh` 认文档）已由
  `431ba84` 修好，第一次真跑已经把那条分支走到（`domain: /tmp/domain-session.json holds no run
  document, so this run is named by its ledger id`），停在下一格的就是本卡这一格。
- `scope`: 一条读路，不做第二份真相——`domain.sh:1086-1092` 已经从**账本里这次 run 的行**读出
  `kin_id`（并且脚本在 `:764-767` 写明它的归因「刻意不从数据库所在的路径读」，因为 helper 要拿两边
  对比）。
  把那份已经测出来的 `kin_id` 交给封存面：`read_run_material` 与 `seal()` 各接一个可选的
  `kin_id`（沿用 `OFFLINE-IDENTITY-SEALED-ARGV-001` 给 `session_argv` 的同一形状：入参可选、
  由 sealer 单点传下去），只在文档没有说出 Kin 时用它；文档说出了 Kin 时以文档为准。同时把
  `:558` 那句合并报错拆成两件事：run 没被命名，与 Kin 没被命名。runner 侧只在**确实没有文档**
  的那条分支上把名字传下去。
- `allowed_paths`: `tools/assert_case_evidence.py`（`read_run_material` 的入参与那句报错，
  **不动任何断言实现**）、`tools/seal_run_evidence.py`（`seal()` 与 CLI `--kin-id`，以及把它交给
  `run_asserter` 的那一行）、`test-orchestrator/runner/domain.sh`（只在 `named_run` 那条分支上多传
  一个已测出的名字）、`tests/unit/test_seal_run_evidence.py`、
  `tests/unit/test_case_evidence_assertions.py`（或这两个模块现有归属的测试文件）、
  `tests/contract/test_runner_scripts.py`、`docs/development-execution-plan.md`、
  `docs/development-todo.md`、`docs/p0-validation-evidence-contract.md`。
- `forbidden_paths`: 产品代码（`src/`）、Bridge/`proto/`、case fixture 与 digest 登记表、任何旧
  bundle、`mandatory` 翻转、`kin-02` 目录（那是别人的证据）、runner 里的故障注入与目标选择。
- `non_goals`: 不改判据语义、不为「有文档」那半数路改变任何读数、不引入「按目录猜 Kin」的第二处、
  不在本卡封第 5 个场景的任何 bundle。
- `acceptance`: ① 一次真实的被杀 Core 运行封得下来：bundle 里 **没有** run-document 工件，
  `identity` 说出 `kin-01`，`result` 由判据给出（本卡不要求 `PASS`，那属 RESEAL）；② 文档与传入的
  名字同时存在且不一致时按文档为准，且这条选择有一条测试钉住；③「没有 Kin」与「没有 run」现在是
  两句话，各有测试；④ `case_version` 一律不动：`check_case_assertions.py` 的 digest 是按**断言实现
  那个函数**的源码算的（`_function_source`，`:94-124`），`read_run_material` 不是任何断言的实现，
  故本卡改完 139 条登记与 `verify_fixture_digests.py` 都该原样绿——如果它们不绿，说明动到了判据面，
  停下按 `stop_conditions` 处理；⑤ 全量门禁绿（pytest / ruff check+format / Pyright / boundaries /
  case assertions / fixture digests / workflow pins / `git diff --check`）。
- `validation_class`: `LOCAL_THEN_REAL_RUN`（先单测与契约断言，再一次真实被杀 Core 运行）。
- `stop_conditions`: ① 若 `check_case_assertions.py` 或 `verify_fixture_digests.py` 因这次改动而要求
  更新任何 `case_version`：停下——那意味着碰到的是判据实现而不是命名入参，需要先回文档面处理；
  ② 若要做到「只在没有文档时用这个名字」必须让 sealer 与 asserter 各存一份 Kin 的记载：停下，
  不做第二份真相；③ 若要清掉 `kin-02` 才能让旧读路通过：拒绝，那是证据不是缓存。
- `next_after_done`: `CRASH-OUTBOX-RESEAL-001` 回到唯一 `NEXT`（**已由收卡后的这条 `docs(plan): advance`
  commit 执行**；campaign 第 5 个场景的真实重封。其后的第 6/7 个场景各自还需要设计卡，未排入本链）。

### CRASH-OUTBOX-RESEAL-001 — 把五个故障窗口在 current build 上重封

- `status`: `DONE`（5/5——五案在 current reviewed build 上各封一份 `PASS`、四读一致；最后一格（runtime
  `CORE-060`）由前置卡 `CRASH-OUTBOX-ALIVE-DISPLAY-001`（交付 `f90abc8`）的一次真实 attempt 封成
  run `7fc0671eabca4430885017613977779c`、bundle `3876c335…`、`attempt_sequence: 3`、`case_version`
  `d1ea32d8b705…` 与 `bridge_digest` `faeec4a9df83abb9…` 均未变。本卡 `acceptance` ⑤ 达成 ⇒ campaign 第 5
  个场景 `scenario_progress` 5/7。历史：曾 `BLOCKED_EVIDENCE`（4/5）——由 `94c3af0`「seal the four unblocked
  crash windows」那条 commit 写下
  的 `window_run_decision_2026-09-24` 收口，紧随的 commit 把本条 `status` 与 `current_next` 对齐到那条已提交的
  判决；本卡未引入新判断）（历史：`a1be5fb` 登记 `QUEUED`、`b158d59` 提升为唯一 `NEXT`；执行到第一次
  真实运行时依 `stop_conditions` ② 两次停下并记 `BLOCKED_EVIDENCE`——第一次是 runner 认文档的守卫，已由
  `431ba84` 修好（与登记本卡的 commit 一同推送），范围修订 `ad51045` 先落在文档面；第二次是封存面命名 Kin
  的前提，另起前置卡 `CRASH-OUTBOX-SEALED-KIN-001`。**那张前置卡已交付 `2160989`、收卡 `acb2572`，本卡的
  阻断已清，由紧随的本 commit 提升回唯一 `NEXT`。** 五个窗口现在有 **6 份**当前-build bundle：
  `CORE-060` 两份 `FAIL`（run `08f206bfaed94e4f9a22aed82c1c24d6` `attempt 1` 两条失败；run
  `412b874b2aa049838c2e11e5f0df4770` `attempt 2` 只剩 `RELEASE_NOT_LOGGED` 一条），
  `CORE-060-CLIENT-001`（run `c89f5d3582e74250b27cf4a034314c0a`）、`CORE-060-SERVER-001`
  （run `f4365a50077647babda76cec90164093`）与 `CORE-090`（两连跑，封存的是重启那次
  run `3e94d49aace44b00924efeb1bb83c1da`）各一份 `PASS`，四读一致，逐字读数见下面
  `window_run_readings_2026-09-24`。
  两条失败已按工件定位，见下面 `attempt_readings_2026-09-24`；runtime 这一窗口由此登记的前置卡
  `CRASH-OUTBOX-ALIVE-DISPLAY-001`（`QUEUED`）接走，其余四案的真运行仍在本卡上。）
- `promotion_reason`: 顺序已满足——登记它的那张 commit（`a1be5fb`）同时把 `CRASH-OUTBOX-EVIDENCE-DESIGN-001`
  收为 `DONE` 并推到两条 ref，`a1be5fb` 只写 `QUEUED`、没写 `NEXT`，本 commit 之前计划里没有 `NEXT`，
  中间没有插入别的未授权工作。入口门禁在登记时全绿（full pytest `2146 passed / 2 skipped in 518.56s`、
  ruff check/format、Pyright 0 errors、boundaries、case assertions 139 registered、fixture digests、
  workflow pins、`git diff --check` 干净）。它是 campaign `order` 第 5 个场景当下唯一的入口：冻结卡
  已给出该场景的逐窗口读数，五个窗口都只缺当前 build 上的 attempt。本机需要先从 Dockerfile 重建
  `minekin-runner:local` 镜像（数据卷 `minekin-runner-data` 仍在，不动它），这是交付步骤，不是决策点。
- `registered`: `a1be5fb`（`QUEUED`）
- `blocked_by`: **无**（曾记 `CRASH-OUTBOX-SEALED-KIN-001`：本卡第一次真跑当场发现的封存面阻断；那张卡
  自己 `blocked_by: 无`，前置是 `431ba84` 已经修好的那条 runner 守卫，现 `DONE`、交付 `2160989`、收卡
  `acb2572`）。2026-09-24 另起 `CRASH-OUTBOX-ALIVE-DISPLAY-001`（`QUEUED`）——它挡的是**五个窗口里的
  runtime 那一格**（`CORE-060` 的松键日志在当前 run 形状下按构造写不出来，见 `attempt_readings_2026-09-24`），
  不挡另外四案，因此本卡保持 `NEXT`、先把那四案跑成真实 bundle，五窗齐不了就按 `BLOCKED_EVIDENCE` 记下。
  原先记的
  `CRASH-OUTBOX-EVIDENCE-DESIGN-001` 已 `DONE`（交付 `72aec3e`、收卡 `a1be5fb`：六个窗口的承载 case、
  读的工件、harness 开关与「旧 bundle 不追认」的口径都已冻结）
- `handover_from_CRASH-OUTBOX-SEALED-KIN-001`: 前置卡当场量到三件事，本卡直接用，不必再撞一遍。
  ① **封存通道在两个 Kin 的卷上真的通了**，形状见那张卡的 `acceptance_readings`；重封 `CORE-060` 时
  `MINEKIN_KIN_ID` 必须显式给（`domain.sh` 只把它读进账本那一步的名字传下去，不会替你猜）。
  ② **一份没有 run document 的 bundle 判得了什么，是有上限的**：`RunMaterial.run()`
  （`tools/assert_case_evidence.py:433-436`）在没有文档时抛
  `Unreadable("the run document carries no run section")`，所以**任何读文档的断言在被杀的这次 run 上都
  拿不到读数**。用 AST 逐条量过 `CORE-060` 的四条断言，**没有一条**读 `run` / `run_document`，所以这一
  个窗口是可判的；反过来说，别把读文档的 case（例如 `CORE-020` 那类）挂到被杀的 run 上，那会判成
  `UNJUDGED` 而不是 FAIL。
  ③ **`CORE-060` 第一份当前-build bundle 的两条 `FAIL` 是真读数**：`move_input_was_leased` 与
  `runtime_controller_sigkill_was_confirmed` 两条 `observed`，`the_bridge_released_the_input_when_the_ipc_was_lost`
  报 `RELEASE_NOT_LOGGED`、`the_server_saw_the_kin_stop_after_the_move` 报 `NEVER_MOVED:0.10`——而
  harness 自己那两句是 `the runtime is gone; the Bridge should let go` 和
  `the Kin left the game after the Core was killed`（注入确实发生在「动过」之后，因为它的等待条件是
  不同横坐标数 ≥2）。也就是说：判据读的两样东西（客户端松键日志、服务端横坐标跨度）与 harness 读的
  不是同一份字节，本卡要先弄清它们各自落在哪个工件里，再决定是取新一轮 attempt 还是按
  `stop_conditions` 停下——**不许改判据、不许改杀法去凑 `PASS`**。旧的那份 `PASS`（`6b6dcdf7…`，旧
  build）不追认，也不动。
- `attempt_readings_2026-09-24`: 上面那条 ③ 要的定位已经做完，两条失败各自落在哪件工件上、各自的成因是
  什么，现在都有读数。
  - **attempt 1（run `08f206bfaed94e4f9a22aed82c1c24d6`）的 `NEVER_MOVED:0.10` 是本卡自己造出来的**：
    那一轮沿用了 `CORE-060-SERVER-001` 的 `MINEKIN_DOMAIN_PROBE_SECONDS=1`（手册明令不许只改 case 名就复用
    上一条命令）。`horizontal_positions`（`domain.sh:795-800`）用 `awk -F', *' 'NF == 3 {print $1","$3}'`
    同时吐出 **x 和 z**，所以「不同横坐标数 ≥ 2」那个等待条件被 settle 期间的 z 抖动单独满足——探针只读到
    3 次、x 恒为 `2.5`、跨度 `0.098 < MINIMUM_STEP_BLOCKS(2.0)`，也就是说强杀在 Kin 开始走之前 ~3 秒就落了。
    **改回默认 5 秒间隔重跑即消失**：这一条是取法错误，不是判据问题，也不是产品读数。
  - **attempt 2（run `412b874b2aa049838c2e11e5f0df4770`，`attempt_sequence: 2`、`supersedes_run_id` 指向
    attempt 1）只剩一条 `FAIL`**：`move_input_was_leased`、`runtime_controller_sigkill_was_confirmed`、
    `the_server_saw_the_kin_stop_after_the_move` 三条都 `observed`（`case_version`
    `d1ea32d8b705…` 与 attempt 1 逐字相同，判据面没碰），失败仍是
    `the_bridge_released_the_input_when_the_ipc_was_lost:RELEASE_NOT_LOGGED`。这一轮 Kin 确实带着键在走——
    客户端日志里有 `bridge pressed move.forward` 与
    `bridge applied 726bdc4374084be192875fe2f62ab303: holding [move.forward]`。
  - **那条断言读的是哪件工件**（`.tmp/kin060_failure_readers.sh`，用判官自己的 `read_sealed_material`）：
    `_BRIDGE_RELEASE`（`tools/assert_case_evidence.py:161`）对 `client/latest.log`（65776 字符）
    `findall → []`——`RELEASE_NOT_LOGGED` 说的是**客户端日志里一行都不存在**，不是行没被读出来。
  - **旧 PASS 与两轮新的逐字对比**（`.tmp/core060_log_tail_compare.sh`、`.tmp/core060_display_death_probe.sh`）：
    旧 build 那份 `6b6dcdf7…` 的 `client/latest.log` 里，`bridge is failing closed (IPC_LOST)` 之后同一秒
    依次是 `bridge released move.forward`、`bridge released 1 input(s) after IPC_LOST`、
    `bridge is cancelling the client's connection`、`released 0 input(s) after LEFT_PLAYABLE (PLAY_ENDED)`
    （`client/stdout.log` 的 log4j 毫秒戳把松键钉在 failing-closed 之后 1–47 ms），而它的
    **`client/stderr.log` 是 0 字节**。当前 build 两轮（`08f206bf…`、`412b874b…`）的整份 `latest.log`
    **止于** failing-closed 那一行，且 `stderr.log` 整份只有一行
    `X connection to :99 broken (explicit kill or server shutdown).`。
  - **为什么这就够把「按构造打不中」说出口**（读源码 + 容器内两次只读探针，不改任何脚本）：松键在
    当前 Bridge 源码里是**客户端 tick 上的动作**——`failClosed()`（`BridgeIpcWorker.java:1038-1056`）只写下
    `clientInbox.replaceWith(Notice.SAFE_STOP)`，真正打那行日志的 `releaseInputs`（`:822-837`）由
    `handleInputMessage` 在 tick 里调到（`:249-254`，注释原话是「Faults arrive here through the terminal
    inbox notice」）。而 Core 是 `xvfb-run` 的内层孩子（`domain.sh:733-734`），`/usr/bin/xvfb-run:143` 是
    `trap clean_up EXIT`、`:90-91` 在 `clean_up` 里 `kill "$XVFBPID"`：孩子被 SIGKILL 后包装器照常规走到
    结尾并**自己关掉 X 服务**。容器内探针（`.tmp/xvfb_display_survival_probe.sh`，两次）量到：只杀
    `xvfb-run` 的命令孩子（不碰 Xvfb）→ **6 ms / 7 ms 之后 Xvfb 进程消失、显示不再应答**，
    即客户端的渲染循环在松键可能发生的下一个 tick 之前就没有了显示。旧那份 PASS 之所以有那一行，
    正好对上 `a818a62` 之前 `pkill -f` 会连包装器一起杀掉、EXIT trap 来不及跑、Xvfb 被留成孤儿还在服务
    （与它 stderr 0 字节一致）。
  - **因此本卡的口径**：这一条**不写成产品侧回归**（`stop_conditions` ① 的「Bridge 未松键」没有被证实：
    当前形状下无论 Bridge 对不对都拿不到那行日志），也**不写成松键已修复**（同样没有证据）。两者能靠
    「显示活得比 Core 久」的一次真实运行分开，而那要改 runner 怎么给出显示——不在本卡 `allowed_paths`
    点名的那一条守卫里，按 2026-09-24 纪律另起前置卡 `CRASH-OUTBOX-ALIVE-DISPLAY-001`。两份 `FAIL` bundle
    原样留在卷上，不重判、不修补；本卡继续跑其余四案。
- `window_run_readings_2026-09-24`: 其余四案「不读那行松键日志」的真运行逐案记录，一窗一条；各一份新
  attempt，卷上旧 bundle 一份不动。
  - **`CORE-060-CLIENT-001` 已封成 `PASS`**（本卡在当前 build 上的第一份 `PASS`）。run
    `c89f5d3582e74250b27cf4a034314c0a`、`attempt_sequence: 1`、`supersedes_run_id: null`、bundle digest
    `8b0691b7919ad5f3ea21c3e43e612fe50a40c1e14784aa14e410d82cab026ab0`、14 件工件（含
    `run-document.json` 与 `previous-run-trace.jsonl`——这一窗 Core 活着，所以文档在），`case_version`
    `dc85eb0438612888947308f2284386d2c87f4d73e6c504b05aa193ba71bf64d7`、`bridge_digest`
    `faeec4a9df83abb9…`。命令按本案那行开关取（不是复用上一条改 case 名）：
    `MINEKIN_KIN_ID=kin-01 MINEKIN_DOMAIN_CASE=CORE-060-CLIENT-001 MINEKIN_DOMAIN_KILL_CLIENT=1`
    （`domain.sh:36/1389`）`MINEKIN_DOMAIN_PROBE=Kin` + `--hold-forward-seconds 60`，**探针间隔用默认值**。
    harness 那几句：`the client has been killed; the keys died with the process` →
    `Core recorded SessionInterrupted after its client was killed` → `session exited 14` →
    `the case verdict is PASS`。退出码 14 是 `BRIDGE_LOST` 拆解、不是判决，同 run 的 run document 逐字记
    `outcome: BRIDGE_LOST`、`input_release_failed: true`、`actions_applied: 1`、`session_state: STOPPED`、
    `recovery.status: reconciled` —— 「客户端里什么都不可能报」这一条被文档如实记下，而本案第四条断言读的是
    **服务端自己**记的 joined→left，所以它与 `CRASH-OUTBOX-ALIVE-DISPLAY-001` 无关。
    **四读一致**（`.tmp/four_readers.sh`，全部只读）：① `evidence verify` →
    `verified: true / sealed: true / violations: [] / result: PASS`；② `tools/rejudge_evidence.py` →
    `status: agrees`，四条 `move_input_was_leased`、`client_jvm_sigkill_was_confirmed`、
    `the_ledger_recorded_the_session_ending`、`leave_after_join_observed` 同时出现在 `expected` 与
    `observed`、`failures: []`；③ 两条重放路径（`python -m minekin_core replay`、
    `tools/replay_evidence.py`）都 `status: projected`、`events: 21`、`projected.state: STOPPED`、
    `trace_sha256 6c236465cce5f4436f3385d70f3fa52b1bf0849a754a0709289af997a8773390`、`violations: []`；
    ④ `tools/report_promotion.py` 给这一份 `result: PASS`、`re_judged: AGREES`、
    `from_repository_build: true`，并把旧的 `e00f2851…` 仍记为 `UNJUDGED`（reason 逐字为 criteria moved），
    整体 `status` 仍 `blocked`——第 5 个场景还差三案，`report_promotion` 的 `evidence["bundles"]` 是**列表**
    而不是以 run id 为键的字典（本卡的读者别再按字典去walk它）。
  - **`CORE-060-SERVER-001` 已封成 `PASS`**。run `f4365a50077647babda76cec90164093`、`attempt_sequence: 1`、
    `supersedes_run_id: null`、bundle digest
    `75a15ccc3a8d17dbe591e876d7687d2323136810ff8f247713d5dac8bf254fc1`、14 件工件、`case_version`
    `50ca1ae2e22d6185949475e3bc8456bc30ad8254eaf0301ac0ffe4eeb9071677`、`bridge_digest`
    `faeec4a9df83abb9…`。命令按本案那行开关取：`MINEKIN_KIN_ID=kin-01`
    `MINEKIN_DOMAIN_CASE=CORE-060-SERVER-001 MINEKIN_DOMAIN_KILL_SERVER=1`（`domain.sh:30/1316`）
    `MINEKIN_DOMAIN_PROBE=Kin` + `--hold-forward-seconds 60`，探针间隔仍用默认值。harness 那几句：
    `the fault helper said {"outcome": "INJECTED", …}` → `the server has been killed; the world is gone`
    （即日志里没有 `Stopping the server`，服务端是被杀而不是停的）→
    `Core recorded the session ending when the world went away` → `session exited 14` →
    `the case verdict is PASS`。**这一窗的松键真的写出来了**：客户端仍活着、X 显示仍在，所以
    `LEFT_PLAYABLE (PLAY_ENDED)` 那条 tick 路径走得通——与 `CORE-060`（Core 自己没了、显示跟着没了）
    正好是两件事，也印证了 `attempt_readings_2026-09-24` 那条机制读法。四读一致：`evidence verify`
    `verified/sealed: true`、`violations: []`；`rejudge_evidence.py` `status: agrees` 且五条
    `move_input_was_leased`、`server_jvm_sigkill_was_confirmed`、`the_server_log_has_no_graceful_shutdown`、
    `the_ledger_recorded_world_loss`、`the_bridge_released_input_when_play_ended` 全在 `observed`；
    两条重放路径都 `projected`、`events: 21`、`projected.state: STOPPED`、`violations: []`
    （`trace_sha256 0ecef024dda1afd8…`）；`report_promotion.py` 给 `re_judged: AGREES`、
    `from_repository_build: true`，旧的 `652043a6…` 仍 `UNJUDGED` 原样留着。
  - **`CORE-090` 已封成 `PASS`（两连跑）**。**A（崩溃）**：`MINEKIN_KIN_ID=kin-01`
    `MINEKIN_DOMAIN_KILL_CORE=1 MINEKIN_DOMAIN_PROBE=Kin` + `--hold-forward-seconds 60`，
    **不给 `MINEKIN_DOMAIN_CASE`**（所以这次不封存任何东西，它是被 B 的材料读的那一次），run id
    `0237e24c846f487ea84e8689c24a0528`，harness 四句 `the runtime is gone; the Bridge should let go` →
    `the Kin left the game after the Core was killed` → `session exited 137` →
    `the run document said Killed`。**B（重启）**：同一条命令去掉 kill 开关与 `--hold-*`，加
    `MINEKIN_DOMAIN_CASE=CORE-090 MINEKIN_DOMAIN_STILL=1`（`domain.sh:38/1464`，转发在 `run.sh:93`），run
    `3e94d49aace44b00924efeb1bb83c1da`、`attempt_sequence: 1`、bundle digest
    `8bda01b52ae2bbfec5b83fb978f931cb28a7bf78668ef4b88e81235e3d077739`、13 件工件（其中
    `previous-run-trace.jsonl` 存在，且封进去的 `asserter-inputs.json` 逐字写
    `previous_run_id: 0237e24c846f487ea84e8689c24a0528`——「上一条 run 就是刚才崩掉的那一次」是 bundle
    自己说的，不是复述者的记忆）、`case_version`
    `88fa467d8896e37492bed1fe3dc74f19106c4c7e7bddaff2896bd82ea5c4d9cc`、`bridge_digest`
    `faeec4a9df83abb9…`。B 自己的 run document：`session_id` `8e17c528937c404080d8d867ae0d95fe`（与 A 不同
    ⇒ 瞬时状态没跨 run）、`actions_applied: 0`（这次什么都没要求）、`snapshots_admitted: 1` +
    `connection_state: PLAYABLE`（世界状态是重新观察的，不是沿用的）、
    `recovery: {"invalidated": [], "waiting": [], "status": "reconciled"}`；harness 那句
    `the Kin moved 0.000 blocks across 2 readings and did not walk` 是世界那边的读数。四读一致：
    `evidence verify` `verified/sealed: true`、`violations: []`；`rejudge_evidence.py` `status: agrees`、
    五条含 `the_restart_runs_as_a_new_session`、`the_restart_reconciled_before_it_started` 全在 `observed`；
    两条重放路径 `status: projected`、`events: 19`、`projected.state: STOPPED`、`violations: []`；
    `report_promotion.py` `re_judged: AGREES` + `from_repository_build: true`，旧的 `c993c801…`
    仍 `UNJUDGED`。**注意这次只有 2 次服务端读数**（上一批记的是 5 次以上）：那条评论判据是
    `the_server_saw_the_kin_arrive_and_never_move`，按**距离**判（>2 格才算走了），读数个数不是它的判据，
    本案也没有任何一条要求「同一条上跨过 `MINIMUM_STEP_BLOCKS`」——那类跨步读数是 `CORE-060`/`CORE-020`
    的断言在读，别把两案的取数要求混为一谈。
  - **`CORE-020`（正常退出那半，`mandatory: true`）已封成 `PASS`**。run
    `8a72dcdf9e9c4fd190860d16a5d1bf1f`、`attempt_sequence: 1`、bundle digest
    `3c4b04894069df5bf99afb17afd68a5acd80812282c82b2ba07e1b7539e89d8e`、13 件工件、`case_version`
    `7c01d11ed1e9df0eab56725e123cc4a04e59c30c77c58957fee82ad613ce38fa`（与冻结表登记的当前 fixture digest
    逐位相同）、`bridge_digest` `faeec4a9df83abb9…`。命令就是不带任何 kill 开关、不带 `--hold-*`、
    不带探针的正常退出：`MINEKIN_KIN_ID=kin-01 MINEKIN_DOMAIN_CASE=CORE-020` + 同一对
    `--profile/--server-profile`（本案的三条断言只读服务端 `server.log`/`usercache.json`、run document
    与账本，没有一条读探针读数）。harness `session exited 14` 同样只是收尾，封存时判读
    `result: PASS`、`failures: []`。四读一致：`evidence verify` `verified/sealed: true` + `violations: []`；
    `rejudge_evidence.py` `status: agrees`、三条 `server_observed_join_identity`、`first_snapshot_admitted`、
    `leave_after_join_observed` 全在 `observed`；两条重放路径 `projected`、`events: 19`、
    `projected.state: STOPPED`、`violations: []`；`report_promotion.py` `re_judged: AGREES` +
    `from_repository_build: true`（同一 case id 名下卷上另有五份旧 build 的 bundle
    `24bbae7d…`/`2cab1052…`/`79ac9a14…`/`bad4e962…`/`e1cba67d…`，其中 `2cab1052…` 本来就是 `FAIL`，
    五份对今天的 criteria 全部仍 `UNJUDGED`，不动不撤）。
- `window_run_decision_2026-09-24`: **四案齐了，第五案（runtime 那一格）在本卡的形状下封不到。**
  按本卡 `acceptance` ⑤ 的口径：campaign 第 5 个场景**不记为已封**，`scenario_progress` 保持 `4/7`；
  本卡改记 `BLOCKED_EVIDENCE`（4/5），阻断项逐字就是 `CRASH-OUTBOX-ALIVE-DISPLAY-001` 那张卡——
  它挡的是 `CORE-060` 那行 `LEFT_PLAYABLE`/`IPC_LOST` 松键日志在当前 run 形状下写不出来这件事，
  不是产品判决（见 `attempt_readings_2026-09-24` 最后那条口径）。两份 `CORE-060` `FAIL` bundle 原样留着。
- `window_run_completion_2026-09-24`: 前置卡 `CRASH-OUTBOX-ALIVE-DISPLAY-001` 交付 `f90abc8` 后，把显示与
  Core 的生死脱钩，第五案（runtime `CORE-060`）在同一条 current-build 通道上封成 `PASS`——run
  `7fc0671eabca4430885017613977779c`、bundle `3876c335…`、`attempt_sequence: 3`、`case_version`
  `d1ea32d8b705…`、`bridge_digest` `faeec4a9df83abb9…`、四读一致（逐字读数在那张卡的 `completion_evidence`）。
  五个窗口至此五案齐 ⇒ 本卡 `acceptance` ⑤ 达成，`status` 升为 `DONE`，campaign 第 5 个场景
  `scenario_progress` 记 5/7。那两份 runtime `FAIL`（`08f206bfaed9…`、`412b874b2aa0…`）与旧 build 的
  `PASS/FAIL` 原样保留、不追认。启动窗口那一半（「已写 effect intent 但未 settle」）仍按冻结口径记为
  **本地证据**，不在真实 run 里为封证插停顿——那是 `CRASH-OUTBOX-EVIDENCE-DESIGN-001` 已冻结的判断，本卡不改。
- `baseline_sha`: `a1be5fbb55d870f7f5d98a3450cf0364b9318712`
- `question`: campaign `order` 第 5 个场景（crash/outbox 窗口）**在当前 reviewed build 上封齐**。
  冻结已经给出：五个已定义窗口都有 case id、断言与 runner 开关，缺的只是 attempt——所以本卡的问题不是
  「怎么证」，而是「把这五个窗口各跑成真 bundle，四读一致」。逐案各一次真实受控运行：
  `CORE-060`（杀 runtime controller）、`CORE-060-CLIENT-001`（杀 client JVM）、
  `CORE-060-SERVER-001`（杀 server JVM）、`CORE-090`（先杀 Core 再重启的两连跑）、
  `CORE-020`（正常退出那半，`leave_after_join_observed`）。
- `depends_on`: `CRASH-OUTBOX-EVIDENCE-DESIGN-001`（`DONE`）提供读数；`RUN-001`/`OFFLINE-010`/
  `OFFLINE-020`/`OFFLINE-030-*` 提供同一条封存通道已在当前 build 上走过四遍的先例。
- `environment_note`: 登记时的环境读数——本机 Docker 引擎里 `minekin-runner:local` 这个镜像**已不在**
  （`docker images` 无命中，`run.sh:33` 默认就是它），但 `minekin-runner-data` 卷**还在**：
  `/data/kin/kin-01/run/evidence` 下 42 份目录，上面那五份旧 bundle 的 `manifest.json` 逐字段仍读得出来
  （本卡登记前以此复核了一遍五对 `case_version` 与两个旧 `bridge_digest`）。所以开跑第一步是重建 runner
  镜像（`MINEKIN_RUNNER_IMAGE`/`MINEKIN_RUNNER_DATA`，`run.sh:33-34`），不是清卷——卷上那些旧 PASS/FAIL
  按契约是**要留着**的。
- `why_now`: 它是 `order` 第 5 个场景当下唯一的入口，且前一张卡已经把「要不要重封」这个判断从猜测
  换成了读数（五案 `from_repository_build: false`、五对 `case_version` 全移动）。
- `allowed_paths`: `docs/development-execution-plan.md`、
  `docs/p0-validation-evidence-contract.md`（第 7/10 条与那份冻结表里的状态注记）、
  `docs/development-todo.md`、`docs/qoder-execution-handoff.md`（阶段 D 的完成状态），
  以及 `scope_amendment_2026-09-24` 依 `stop_conditions` ② 放开的两个测试域文件：
  `test-orchestrator/runner/domain.sh`（只改「怎样认出封存现场那份 run document」这一条守卫，
  不动故障注入、目标选择、等待条件与判据读取）与 `tests/contract/test_runner_scripts.py`
  （为那条守卫加一条契约断言）。真实 bundle 落在
  数据卷 `/data/kin/kin-01/run/evidence/<run_id>/`，不进仓库。
- `forbidden_paths`: `src/`、`tools/`、`tests/` 内除上面点名的那一份契约测试以外的任何文件
  （含任何 case fixture 与 digest 登记表）——判据面改了就说明冻结的读数不成立，要先回到文档面处理；
  `domain.sh` 内的故障注入与目标选择（`inject_fault`、`read_process_identity`、`:1250` 那条等待条件）
  不得改动：那是 `a818a62` 用身份绑定换掉全局 `pkill` 的成果，也是
  `tests/contract/test_runner_scripts.py:156` 钉住的断言；任何旧 bundle
  （上面那五份 PASS 与那份保留的 FAIL）不得改写、重判或删除；`CORE-090`/`CORE-020`/`CORE-060*` 的
  `mandatory` 不得翻转；产品恢复策略（`application/recovery_service.py`、`domain/recovery.py`）不得触碰；
  `Launcher` 不得当成第四个独立进程。
- `scope_amendment_2026-09-24`: 开跑后第一次 `CORE-060` 真实运行（run id
  `3e7ac6124d3549598ad85259d2b8b54f`，服务端目录 `run-133`）**注入成功而封存失败**：故障记录
  `{"outcome": "INJECTED"…}`、「domain: the runtime is gone; the Bridge should let go」、session 退出 137
  都在，随后是 `domain: the run document said Killed` 与
  `domain: the run could not be sealed (exit 2): {"message": "/tmp/domain-session.json is not a readable
  run document: Expecting value: line 1 column 1 (char 0)", "status": "unsealed"}`。
  这次 attempt **没有留下 bundle**（`evidence/<run_id>/` 下没有该目录），所以卷上既无要保留的 FAIL、
  也无需撤回的东西；它是诊断，不是证据。
  - **缺口在哪**（`domain.sh:1886-1889`）：封存时「这次 run 有没有 Core 自己打出的文档」是按
    `[ ! -s "${subject_document}" ]` 判的——文件有字节就算有文档。而 session 是包在 `xvfb-run` 里跑的
    （`domain.sh:733-734`），`/usr/bin/xvfb-run:184` 是 `"$@" 2>&1`：Core 的 stderr 与它的 stdout 汇进
    同一个文件。runtime controller 被 SIGKILL 时，写进那个文件的不是 Core 的话，而是包装器报告孩子死讯
    的那一行。于是守卫把「一行死讯」当成「一份文档」交给 sealer，sealer 照实拒绝。
  - **三次读数**（`.tmp/killed_stdout_probe.sh`，容器内，只读）：① 只杀内层 python（当前 helper 的做法）
    → 文档文件 7 字节 `Killed`、`xvfb-run` 自己的 stderr 0 字节；② 同一个孩子不过包装器直接杀 →
    stdout/stderr 各 0 字节，死讯根本不出现在数据流里；③ 按命令行模式同时杀包装器与孩子（`a818a62` 之前
    那句 `pkill -KILL -f "minekin_core session start"` 的形状）→ 文档文件 0 字节，守卫如期回落到
    `--run-id`。**结论**：死讯要落到文档流里，前提是**包装器活得比孩子久**；`a818a62` 把全局 `pkill`
    （连 `xvfb-run` 一起杀，命令行里带着同一串参数）换成按身份只杀孙进程，这一步做对了归因，副作用是
    从此没有一份被杀 Core 的 run 封得上——`07e68af` 那条「Core 被杀也能封存」的回落通道自那以后再没被
    走到过，因为那是它唯一的服务对象。
  - **为什么不是回到 `pkill`**：那会撤掉 `a818a62` 的身份绑定，并且直接撞上
    `tests/contract/test_runner_scripts.py:156` 钉着的那条「不得用全局 `pkill` 猜目标」的断言。也是
    同一理由不把 kill 改回打包装器：那证的就不是 runtime controller 这个身份死了。
  - **修法（一次一条规则）**：守卫从「文件有没有字节」改成「文件里是不是一份能解析成对象的 JSON」；
    不是文档时按 `--run-id` 命名这次 run（`run_id` 从账本第一手事件读出，`domain.sh:1075`——正是
    `07e68af` 设计的那条回落），并把这件事**说出来**而不是静默降级。同一规则也用于 joiner 分支那份
    host 文档吗？不：那一份的失败方式是「拒绝封存」而非回落（`domain.sh:1880-1883` 的理由仍然成立），
    且五个窗口没有一个是 joiner 承载的，本卡不动它，遗留记在下面。
  - **对判据无影响**：`CORE-060` 那四条断言读的是故障记录、账本、bridge trace 与服务端日志
    （`runtime_controller_sigkill_was_confirmed` → `_confirmed_sigkill(..., require_session=False)`，
    `tools/assert_case_evidence.py:1789-1797`），run document 缺席时封存工件里就不写它
    （`07e68af`：absent 不等于 empty），rejudge 侧读不到该工件时以 `{}` 进材料
    （`tools/assert_case_evidence.py:910/930`）。判官源码没动 ⇒ `case_version` 不动。
  - **对本卡的核心比对无影响**：`from_repository_build` 比的是 `launch_plan_digest`，而它盖的是启动计划
    的相对路径与 Bridge 源码树内容（`tools/report_promotion.py:138-160`、`:242-246`），不含
    `test-orchestrator/`。改这条守卫不会让已封的 bundle 变成「另一个 build」，也不会让本卡要求的
    `faeec4a9df83abb9…` 变成两个值。
  - **修订之后仍然留下的**：`domain.sh:1879` 那份 `--world-run-document` 仍按字节无条件交给 sealer，
    所以「host 的 Core 被杀 + joiner 承载 case」这一形状依旧封不上（本卡五窗不落在它上面，且它属于
    `CORE-030` 的场景）；另起卡时才动。
- `non_goals`: 不为「崩溃落在启动窗口」的 pending outbox 造真实运行（冻结已归本地证据）；不做第 6/7
  个场景；不改判据、不加断言；不为了多份报告重复已封的 OFF-A/OFF-B。
- `acceptance`: ① 五个 case id 各有一份**本 build** 的真实 bundle：`bridge_digest`
  `faeec4a9df83abb9…`、`from_repository_build: true`、`verified: true`、`violations: []`，
  `expected` 全部出现在 `observed` 且 `result: PASS`；② 四读一致（封存时判读、`tools/rejudge_evidence.py`、
  `python -m minekin_core replay` 与 `tools/replay_evidence.py`、`tools/report_promotion.py`），
  且 `report_promotion.py` 对每个 case id 都报 `AGREES`；③ 每次都是**新的 attempt**（`sequence` 递增或
  `supersedes_run_id` 如实指向本场景内被取代的那次），旧 PASS/FAIL 原样留在卷上，冻结表里那五行
  「当前 build 上的证据」逐行改成实际 run/bundle digest；④ 若某一窗口真跑失败：保留 FAIL bundle、
  分类、如实写进契约与计划，不重判、不在旧 bundle 上修补，退出码 14（`BRIDGE_LOST` 收尾）不充当判决；
  ⑤ 五案齐后 campaign 第 5 个场景记为已封（`scenario_progress` 5/7），启动窗口那一半继续按
  「本地证据 + 按构造打不中」表述；⑥ 那条守卫的修法以**真实封存**为准：契约断言先红后绿只是不让它
  再被无声改回去，`CORE-060` 那份 `PASS` bundle（`--run-id` 命名、无 run-document 工件、四读一致）
  才是「通道又通了」的证据。冻结表 runtime 那一行的「当前 harness 可否真跑」据此从「开关在、通道断」
  改回「可」，并把 `a818a62` 之后没有一份被杀 Core 的 run 封得上这件事留在表下。
- `validation_class`: `LOCAL_THEN_REAL_RUN`（修订后：先一条契约断言与一次本地门禁，再五份真实运行）。
- `stop_conditions`: ① 若某窗口在真跑时暴露出**产品侧**回归（例如 Bridge 未松键、账本没有
  `SessionInterrupted`、重启后世界没重新观察），停下：保留 FAIL、分类、报告主控，不靠重试换一个颜色；
  ② 若需要改 `forbidden_paths` 里任何文件才能封上（例如某件工件在当前 build 上根本读不出来），
  先停下修订范围或另起前置卡（2026-09-24 纪律：先修订任务卡范围再动手）；③ 若某一窗口的处理方案落到
  自动接管/终止残留进程，那属 `PROCESS-RECOVERY-001` 的 `BLOCKED_DECISION`，立即停下请求主控决策。

### CRASH-OUTBOX-ALIVE-DISPLAY-001 — 让 Core 的死不再带走客户端的显示

- `status`: `DONE`（`94c3af0` 以 `QUEUED` 登记、`9a283ac` 提升为唯一 `NEXT`，2026-09-24 交付完成；
  前置卡 `CRASH-OUTBOX-RESEAL-001` 随本卡收口升为 `DONE`（5/5）。
  历史：登记时不写 `NEXT`——依 2026-09-24 纪律由 `CRASH-OUTBOX-RESEAL-001` 的 `attempt_readings_2026-09-24`
  当场另起，登记那次 commit 之后唯一 `NEXT` 仍是 `CRASH-OUTBOX-RESEAL-001`）
- `completion_commit`: `f90abc8`（`fix(runner): let the harness own the display so a killed Core leaves it standing`）
- `completion_evidence`:
  - **改了什么（仅 `allowed_paths`）**：`domain.sh` 把主 session 从 `xvfb-run` 内层搬到 harness 自持的
    Xvfb——在 `:77-:99` 里挑一块空闲显示、`Xvfb :NN -screen 0 1280x720x24 &`、等 `/tmp/.X11-unix/XNN`
    socket 出现、`export DISPLAY`，session 改由 `sh -c '"$@"; :' minekin-session-supervisor` 这一层普通
    包装承载（保留 `session_pid` 之下的 runtime controller 后代，供 `inject_fault` 逐名，`:` 阻止 shell
    exec-replace 折叠成同一 pid）。joiner（`:649`）与 glxinfo（`:1878`）两处 `xvfb-run` 原样不动，
    kill 块 1297 的注释随之更正。`src/`、`bridge/`、`proto/`、`tools/`、故障注入、目标选择、`domain.sh:1250`
    等待条件、任何 fixture/digest/`mandatory`、已封 bundle 一字未动。契约测试 `test_runner_scripts.py`
    新增 `test_a_killed_core_leaves_the_display_it_never_owned`（先红后绿：钉住 harness 起 Xvfb、
    `export DISPLAY`、等 socket、session 在普通包装器之下且不在 `xvfb-run` 之内）。
  - **本地门禁全绿**：`uv run --frozen pytest -q` `2159 passed / 2 skipped`；`ruff check`/`ruff format --check`
    （304 files already formatted）；`pyright` 0 errors；`check_boundaries` OK；`check_case_assertions`
    `139 registered`；`verify_fixture_digests` OK；`check_workflow_pins` OK；`git diff --check` 干净；
    容器内 `bash -n domain.sh` OK；`tests/contract/test_runner_scripts.py:156` 那条「不得用全局 pkill 猜目标」原样绿。
  - **一次真实 `CORE-060` runtime-kill（验收 ①②，默认 5 秒探针、显式 `MINEKIN_KIN_ID=kin-01`）**：run
    `7fc0671eabca4430885017613977779c`、服务端目录 `run-142`、`attempt_sequence: 3`、bundle digest
    `3876c335306f21e154ea20dfa09340dc5a542c0d19c8acefd93f4c94dff8ed80`、13 件工件。命令
    `MINEKIN_KIN_ID=kin-01 MINEKIN_DOMAIN_CASE=CORE-060 MINEKIN_DOMAIN_KILL_CORE=1 MINEKIN_DOMAIN_PROBE=Kin
    MINEKIN_DOMAIN_SECONDS=240 bash test-orchestrator/runner/run.sh domain session start --profile
    tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json --server-profile
    tests/fixtures/runtime-input/controlled-offline-server.json --hold-forward-seconds 60`
    （**未设** `MINEKIN_DOMAIN_PROBE_SECONDS` ⇒ 默认 5 秒）。harness 读数：`the runtime is gone; the Bridge
    should let go` → `the Kin left the game after the Core was killed` → `session exited 0` → 封存 `PASS`。
    - **验收 ① 现场**：被封存的 `client/latest.log` 第 180–182 行是
      `bridge is failing closed (IPC_LOST); the client will be stopped by its next tick` →
      `[Render thread/INFO]: bridge released 1 input(s) after IPC_LOST`（**N=1>0，且由客户端 tick 线程写出**），
      随后 `released 0 input(s) after LEFT_PLAYABLE (PLAY_ENDED)`；`client/stderr.log` **为空**——旧 build 那两份
      `FAIL` 的整份 stderr 只有 `X connection to :99 broken`，现在显示活过了 Core，那行松键日志真的写出来了。
      这把「Bridge 真没松键」与「客户端没机会写这行」第一次干净地分开，`stop_conditions` ① 未触发。
    - **验收 ② 字段**：`result: PASS`、`failures: []`、`verified: true`、`sealed: true`、`violations: []`；
      `case_version` 仍 `d1ea32d8b7055a47fdeb8a1f4315aab2d3795e90390c5b27984e13fd7e0b72b1`（判据面没动）、
      `bridge_digest` 仍 `faeec4a9df83abb9ca0404863e04d20cfd87ac0f3afd5e74b6858e3e15372f55`；四条断言全
      `observed`（`move_input_was_leased`、`runtime_controller_sigkill_was_confirmed`、
      `the_bridge_released_the_input_when_the_ipc_was_lost`、`the_server_saw_the_kin_stop_after_the_move`）。
  - **验收 ③ 四读一致**：`evidence verify` `PASS`/`verified`/`sealed`/`violations: []`；
    `rejudge_evidence.py` `status: agrees`（四条 observed、`result: PASS`、同 `case_version`）；
    `python -m minekin_core replay` 与 `tools/replay_evidence.py` 皆 `projected`、`events: 16`、
    `projected.state: PLAYABLE`、`violations: []`；`report_promotion.py` 该份
    `from_repository_build: true`、`re_judged: AGREES`、`attempt_sequence: 3`、`result: PASS`。
  - **旧 bundle 原样保留（`forbidden` / 交接「旧 PASS 与新 FAIL 不动」）**：同 case id 名下两份 `CORE-060`
    `FAIL`（`08f206bfaed9…`、`412b874b2aa0…`）与旧 build 的 `PASS 6b6dcdf7…`/`FAIL 6d4bf5eb…` 在
    `report_promotion.py` 里仍 `from_repository_build: false` + `re_judged: UNJUDGED`，一字未改、未撤。
  - **未测 / 边界**：本卡只碰显示生命周期，未改任何判据/杀法/目标选择；`PROCESS-RECOVERY-001` 的自动接管
    未触碰（解耦靠 harness 自持 Xvfb，没有替客户端重启或接管残留进程，`stop_conditions` ③ 未触发）；
    不需要 `forbidden_paths` 变更即可解耦（`stop_conditions` ② 未触发）。真实 bundle 落在数据卷，不进仓库。
- `next_after_done`: 本卡交出 runtime 那一格后，前置卡 `CRASH-OUTBOX-RESEAL-001` 的五个窗口在 current build 上
  五案齐、`scenario_progress` 升为 5/7，本卡与那张前置卡同批收 `DONE`。
- `question`: runtime-controller 强杀这一窗口要读的松键日志由**客户端的 tick** 写，而当前 run 形状里
  Core 是 `xvfb-run` 的内层孩子——杀掉它就 6–7 毫秒内关掉 X 服务，客户端渲染循环先没了。要怎样让
  **X 显示与 Core 的生死脱钩**（显示归 harness 拥有、活过这次注入），使那行
  `bridge released N input(s) after IPC_LOST` 有机会被真实写出来，同时一字不动故障注入、目标选择、
  `domain.sh:1250` 的等待条件与任何判据？
- `depends_on`: `CRASH-OUTBOX-RESEAL-001`（本卡由它两轮真实 attempt 的读数发现；读数与探针在那张卡的
  `attempt_readings_2026-09-24` 里，本卡直接引用，不另测一遍）。
- `why_now`: 它是五个窗口里 runtime 那一格的唯一硬阻断——封存通道（`431ba84`）、Kin 命名（`2160989`）
  都已在真实 bundle 上证过，而现在封到 `FAIL` 也**分不开**「Bridge 真没松键」与「客户端没机会写这行」。
  其余四案不读那行日志，因此本卡不挡它们；登记它而不是就地改 `domain.sh`，是因为本卡 `allowed_paths`
  放开的只有「怎样认出封存现场那份 run document」那一条守卫。
- `readings_so_far`: ① 旧 build 的 `PASS`（`6b6dcdf7…`）`client/stderr.log` 为 0 字节、松键在
  failing-closed 后 1–47 ms 出现；② 当前 build 两轮（`08f206bf…`、`412b874b…`）整份客户端日志止于
  `bridge is failing closed (IPC_LOST)`，`stderr.log` 整份只有 `X connection to :99 broken
  (explicit kill or server shutdown).`；③ 容器内只读探针两次：只杀 `xvfb-run` 的命令孩子 → Xvfb 在
  6 ms / 7 ms 后消失、显示不应答；④ 源码：`BridgeIpcWorker.java:1038-1056`（`failClosed` 只投
  `Notice.SAFE_STOP`）→ `:249-254`（tick 里才 `releaseInputs`）→ `:822-837`（那行日志）。
- `scope_candidates`: (a) 首选——harness 自己起一次 Xvfb（或等价显示）并在整个 run 期间持有它，
  `session` 不再包在 `xvfb-run` 里，只继承 `DISPLAY`；被杀的 Core 与它自己的 EXIT trap 都关不掉这个服务。
  (b) 备选——保留 `xvfb-run`，在注入前让包装器不被这次死讯触发（**评估过：做不到**，`clean_up` 是
  `/usr/bin/xvfb-run:143` 的 EXIT trap，除非把杀法退回连包装器一起杀，而那正是 `a818a62` 换掉、
  `tests/contract/test_runner_scripts.py:156` 钉住不许回退的形状）。动手前先在 (a) 上量一遍
  `domain.sh:733-734` 与 `:649` 两处包装点各自的下游依赖（`stderr` 合并、glxinfo 测量 `:1878`、
  客户端 `DISPLAY` 的来源），并把结论写回本节，不要留下第二份显示来源。
- `allowed_paths`: `test-orchestrator/runner/domain.sh`（**只**改显示怎样起、怎样交给 session）、
  `tests/contract/test_runner_scripts.py`（钉住「Core 的死不得关掉 harness 的显示」这一条）、
  `test-orchestrator/runner/README.md`（那两处包装点的说明）、
  `docs/development-execution-plan.md`、`docs/p0-validation-evidence-contract.md`、
  `docs/development-todo.md`。真实 bundle 仍落在数据卷，不进仓库。
- `forbidden_paths`: `src/`、`bridge/`、`proto/`、`tools/`（产品与封存面一字不动——若封不上是因为
  封存面，那按 `stop_conditions` ② 另起卡）；`inject_fault`、`read_process_identity`、
  `domain.sh:1250` 的等待条件（身份绑定是 `a818a62` 的成果）；任何 case fixture、digest 登记表与
  `mandatory`；已封的 bundle（含那两份 `CORE-060` `FAIL` 与旧 build 的 PASS/FAIL）。
- `non_goals`: 不改判据去迁就读不到；不为让 `CORE-090`/joiner 分支变绿而改显示以外的形状；不引入
  残留进程的自动接管或终止（那是 `PROCESS-RECOVERY-001` 的 `BLOCKED_DECISION`）；不在本卡封
  `CORE-060` 之外的任何窗口。
- `acceptance`: ① 一次**新的**真实 `CORE-060` attempt（默认 5 秒探针间隔、显式 `MINEKIN_KIN_ID=kin-01`）
  里 `client/latest.log` **真的出现**那行 `bridge released N input(s) after IPC_LOST`，且 `N > 0`；
  ② 同一轮封成 `PASS`：四条断言全 `observed`、`violations: []`、`verified: true`、
  `from_repository_build: true`、`case_version` 仍是 `d1ea32d8b705…`（判据面没动）、
  `bridge_digest` 仍是 `faeec4a9df83abb9…`；③ 四读一致，其中 replay 那一读要同时跑
  `python -m minekin_core replay <dir>` 与 `tools/replay_evidence.py <dir>`；④ 契约断言先红后绿，
  且 `test_runner_scripts.py:156` 那条「不得用全局 `pkill` 猜目标」原样绿；⑤ 全量门禁绿。
- `validation_class`: `LOCAL_THEN_REAL_RUN`（一条契约断言 + 一次本地门禁，再一次真实运行）。
- `stop_conditions`: ① 若在显示确实活过 Core 的一轮里那行松键日志**仍然不出现**，那就是
  `CRASH-OUTBOX-RESEAL-001` `stop_conditions` ① 点名的**产品侧回归**：保留 `FAIL`、分类、停下报告主控，
  不许改判据或杀法换一个颜色；② 若需要动 `forbidden_paths` 里任何文件才能把显示解耦（例如必须改
  `tools/` 或产品代码），先停下修订范围或另起前置卡；③ 若解耦显示的办法落到「harness 替客户端重启/
  接管残留进程」，属 `PROCESS-RECOVERY-001` 的 `BLOCKED_DECISION`，立即停下请求主控决策。

### TICK-RENDER-SOAK-EVIDENCE-DESIGN-001 — 冻结 tick/render 采样与 L6 soak 场景的可复判证据边界

- `status`: `DONE`（`096bd68` 以 `QUEUED` 登记、`26a7543` 提升为唯一 `NEXT`、本 commit 交付其冻结：
  判据表已写下、下游真实 soak 实现卡 `TICK-RENDER-SOAK-RUN-001` 以 `QUEUED` 登记。冻结是本卡的交付，
  **真实 600 秒运行与封证不在本卡**，见 `next_after_done`）
- `promotion_reason`: 顺序已满足——登记它的 `096bd68` 同时把 `CRASH-OUTBOX-ALIVE-DISPLAY-001` 与
  `CRASH-OUTBOX-RESEAL-001` 收为 `DONE`、`scenario_progress` 记 5/7，登记那次 commit 之后计划里无 `NEXT`，
  中间没插入别的未授权工作；`order` 第 6 场景此前没有任何卡，本卡是其唯一入口。提升前门禁全绿
  （`2159 passed / 2 skipped`、case assertions `139 registered`、fixture digests、workflow pins 原样绿）。
- `registered`: 2026-09-24，由 campaign `order` 第 5 个场景（crash/outbox 窗口）封齐 5/7 触发；它是 `order`
  第 6 个场景（tick/render 采样）当下唯一的入口，因为该场景此前没有任何卡（冻结卡
  `CRASH-OUTBOX-EVIDENCE-DESIGN-001` 明确「不做第 6/7 个场景的设计」）。
- `depends_on`: `REAL-P0-CAMPAIGN-001` 第 5 场景（`DONE`，本 commit）提供同一条 current-build 封存通道；
  `CORE-METRICS-001`（`DONE`，`1e43a99`，callback 预算采样的字段/聚合/evidence 形状）与用例
  `CORE-100`（`tests/fixtures/cases/core-100.json`，L6 有界 soak baseline，三条断言，`mandatory: false`）
  提供已登记的判据；`tools/report_soak.py` 从封存字节算 P50/P95/P99 与线程峰值。
- `why_now`: `order` 的前五个场景已按冻结判据逐个封证；第 6 个是唯一还没被任何卡认领、又不需产品新决策的
  下一项（tick/render + soak 的采样面已在 current build 上被 scenario 5 复用过多遍）。它是**证据设计卡**，
  不引入新的产品行为。
- `question`（提升后已冻结，见 `freeze`）：campaign 第 6 个场景（tick/render 采样 + L6 soak）在当前 reviewed
  build 上**要封什么才算闭合**——原三问的逐条结论落在下面 `freeze` 表里。
- `freeze`（本卡交付；**只冻结判据与读数归属，不封任何 bundle、不跑 600 秒**）：

  第 6 场景在契约（`p0-validation-evidence-contract.md` L6 行 + 用例清单第 14 条）里是「有界持续运行并报告
  资源与延迟分布，阈值先测后定」。它在当前 build 上要闭合的**真实读数只有一处：`CORE-100`（L6 有界 soak，
  三条断言，`mandatory: false`）**；tick/render callback 预算**机制**已在 `CORE-METRICS-001`（`1e43a99`，
  `LOCAL_THEN_REAL_RUN`）的域内落地，其 `acceptance` 明写「真实 percentile 仍由后续 runner campaign 验收」，
  故真实侧只作**报告**，不设 case、不设阈值。

  | 读数 | 可信来源 | sealed artifact | 判官字段（`tools/assert_case_evidence.py`） | 反例（须各自驱动到 FAIL） |
  | --- | --- | --- | --- | --- |
  | 首快照被准入（`CORE-100` 断言①） | Core run document 的准入快照 + `BRIDGE_FILTERED` 的 join 行 | bundle 里既有的 run document / ledger 工件 | `first_snapshot_admitted`：join 与「快照被准入」两半都要，缺任一即拒 | 无 join 的快照；join 了但快照未准入；用超时推断冒充准入 |
  | soak 覆盖被要求的时长（断言②） | runner 写的 summary（`requested_seconds`/`interval_seconds`/`ended_early`）+ samples 的实际 `elapsed` | `soak-summary.json` + `soak-samples.txt` | `the_soak_held_for_the_duration_it_was_asked_for`：summary 完整、`ended_early≠true`、`max(elapsed)+interval≥requested` | 没有 summary；summary 不完整；`ended_early=true`；样本提前停（`SOAK_SHORTER_THAN_REQUESTED`） |
  | 两个 JVM 各自从头到尾被采（断言③） | samples 每行 `(label,rss_kb,threads,elapsed)` | `soak-samples.txt` | `both_jvms_were_sampled_throughout_the_soak`：client/server 各 ≥2 样本、各自末次 `elapsed` 达 `reached-2*interval` | 某一 JVM 从未被采；某 JVM 仅 1 样本；某 JVM 中途停采（`*_STOPPED_BEING_SAMPLED`） |
  | tick/render callback 预算窗口 | `publishBudgetWindow` 的窗口序号/ring 聚合（`CORE-METRICS-001` 落地的字段/聚合/evidence 形状）；真实侧只在同一受控 soak run 里观察窗口是否推进、覆盖与缺口 | 本轮已封的 core/client 工件；**不新增 case fixture、不新增判据** | **无判官字段**（不新增、不设阈值）；只由 `tools/report_soak.py` 从**已验摘要的封存 bundle** 算 per-process min/first/last/**P50/P95/P99**/max RSS 与线程峰值（nearest-rank），并注明窗口/采样覆盖/缺口 | 报告把 P50/P95/P99 说成「性能合格」；对 FPS/TPS/GC/队列深度/GPU 造读数（契约无来源）；为「多一份报告」重复跑 600 秒以外的空 soak |

  **当前-build 判定（原问①）**：`2026-09-20` 那轮 L6 baseline **早于**当前 reviewed build——自 2026-09-20 起
  `bridge/` 大量变动（含 `1e43a99` 预算、显示/IPC、`dd992b1`/`e75b011`/`eeac5b0` 认证与快照分类），且
  case-version 绑定已改为「覆盖 criteria 而非仅名字」（`13967fa`）。使 5 份旧 crash bundle 读作 `UNJUDGED`
  的**同一条每-build 四读规则** ⇒ 预期该 baseline 对当前 build 亦读 `UNJUDGED`。**此为预期，非本卡实测**：
  `CORE-100` 的 `mandatory: false`，它不 gate promotion，但 campaign `order` 第 6 场景要一份当前-build 的 L6
  baseline 读数。故闭合方式是**在当前 build 上跑一次新 attempt 封 `CORE-100`**，旧 baseline bundle 原样保留、
  不重写；实现卡须先在当前 build 上量一次旧 baseline 的实际读数（记 `UNJUDGED`/或仍 `AGREES`），再封新 attempt。

  **冻结的三条 stop_conditions 细化**：① 冻结**不要求**改 `src/`/`bridge/`/`tools/` 的采样实现——预算机制
  `CORE-METRICS-001` 已域内落地，本场景只消费；若真实 soak run 连预算窗口都无法暴露到可报告，记
  `BLOCKED_EVIDENCE` 并报告，**不新增产品代码**。② 真实 600 秒 soak 连续三次同一不可消除外部阻断 ⇒
  `BLOCKED_EVIDENCE` 报告。③ 契约无来源的指标（FPS/TPS/GC/队列深度/GPU）只报「该轮测量不完整」，
  不造读数、不自行设阈值。**未触发任何停卡条件**（冻结本身是判据工作）。
- `acceptance`: ① 上面 `freeze` 表把三种真实读数各自的「可信来源 → sealed artifact → 判官字段 → 反例」逐条
  写清，且不引入新判据/新 case；② 明确 tick/render 预算在真实侧只报告不设阈值；③ 下游真实 soak 封证以
  `TICK-RENDER-SOAK-RUN-001` 一张 `QUEUED` 卡登记，本卡不跑 600 秒；④ 只动计划与本 TODO，全量门禁相对
  上一绿基线无变化。
- `validation_class`: `LOCAL`（纯证据设计冻结；真实运行在下一张卡）。
- `completion_commit`: 本 commit（只改 `docs/development-execution-plan.md`、`docs/development-todo.md`）。
- `next_after_done`: `TICK-RENDER-SOAK-RUN-001`（当前 build 上受控 bounded-soak 真实运行 + 量旧 baseline 的
  当前-build 读数 + 封 `CORE-100` 新 attempt + 四读一致 + `report_soak` 报告预算/RSS 覆盖）。它交付后按
  `order` 进入第 7 个场景（CORE/OFFLINE/ADMIT promotion 总账）。

### TICK-RENDER-SOAK-RUN-001 — 在当前 build 上封一次 L6 有界 soak 并报告预算/RSS 覆盖

- `status`: `DONE`（`9f3946d` 提升为唯一 `NEXT`，2026-09-24 真实封证交付完成；四读一致、全量门禁绿）
- `promotion_reason`: 顺序已满足——登记它的 commit（冻结卡 `TICK-RENDER-SOAK-EVIDENCE-DESIGN-001` 交付，
  `6717d2e`）同时把该冻结卡收为 `DONE`，登记那次 commit 之后计划里无 `NEXT`，中间没插入别的未授权工作；它是
  `order` 第 6 场景冻结表点名的唯一真实封证实现卡。提升前静态门禁全绿（case assertions 139 registered、fixture
  digests、boundaries、workflow pins、`git diff --check` 干净；`6717d2e` 为纯文档 commit，全量 `2159 passed /
  2 skipped` 相对 `26a7543` 无代码变化）。
- `registered`: 2026-09-24，由 `TICK-RENDER-SOAK-EVIDENCE-DESIGN-001` 冻结触发；它是 `order` 第 6 场景的
  真实封证实现卡。
- `depends_on`: `TICK-RENDER-SOAK-EVIDENCE-DESIGN-001`（判据先冻结，本卡才有对象）；`CORE-100`
  （`tests/fixtures/cases/core-100.json`，三条断言）；`CRASH-OUTBOX-RESEAL-001`（同一条 current-build 封存通道，
  `f90abc8`）。
- `question`: 在当前 reviewed build 上跑一次受控 bounded-soak（`MINEKIN_DOMAIN_SOAK_SECONDS` /
  `MINEKIN_DOMAIN_SOAK_INTERVAL` 已存在的 knob），封 `CORE-100`，并把 tick/render 预算窗口的覆盖/RSS 分布
  如实报告，四读一致——怎样做到**不新增判据、不设阈值、不重写旧 baseline**？
- `scope`: ① 先对 `2026-09-20` 旧 baseline bundle 在当前 build 上量一次读数（`evidence verify` /
  `report_promotion`），如实记 `UNJUDGED` 或仍 `AGREES`，**不重写**；② 在当前 build 上跑一次受控 soak
  （建议沿用 baseline 的 600 秒 / 间隔 10 秒档，`llvmpipe` 软件渲染，两个 JVM），分配**新 attempt**，封
  `CORE-100`；③ `tools/report_soak.py` 从**已验摘要的封存 bundle**算 per-process min/first/last/P50/P95/P99/
  max RSS 与线程峰值（nearest-rank），报告里写要求时长、间隔、样本数、是否提前终止、失败样本，并对
  FPS/TPS/GC/队列深度/GPU 标「未测/该轮不完整」；④ tick/render 预算窗口只报覆盖与缺口，不设阈值。
- `allowed_paths`: `test-orchestrator/runner/domain.sh`（仅当 soak 分支需要读同一 current-build 通道的小修，
  冻结表未要求改采样语义）、封存/报告读路（`tools/report_soak.py`、`tools/seal_run_evidence.py`、
  `tools/assert_case_evidence.py`）**若**发现真实 run 无法把 `soak-samples.txt`/`soak-summary.json` 封进 bundle 才允许动，
  且须先按 `stop_conditions` 修订范围；`docs/development-execution-plan.md`、`docs/development-todo.md`。
- `forbidden_paths`: `src/`/`bridge/`/`proto/`/`tools/` 的采样实现语义、case registry 与 `mandatory` 翻转、
  `CORE-100` 三条断言的判据字节、旧 baseline bundle 与任何既有 sealed bundle。
- `non_goals`: 不设性能阈值、不测 GPU 档、不为 FPS/TPS/GC/队列深度造来源、不重复 600 秒「多一份报告」、
  不封第 7 场景的 promotion 总账。
- `acceptance`: ① `CORE-100` 在当前 build 上有一份新 attempt 的 `PASS` bundle，三条断言逐条来自封存字节；
  ② verify / rejudge / 适用 replay / promotion 四读一致；③ 旧 baseline 读数已如实量并保留、未被改写；
  ④ `report_soak` 输出标明窗口、采样覆盖与缺口，未测指标如实标不完整；⑤ 全量门禁绿。
- `validation_class`: `LOCAL_THEN_REAL_RUN`。
- `stop_conditions`: ① 若封存通道今天根本不能把 soak 两份工件写进 bundle，需动 `tools/`/`bridge/` 采样面 ⇒ 先停下
  修订本卡范围或另起卡（不在本卡偷偷扩范围）；② 真实 soak 连续三次同一不可消除外部阻断 ⇒ `BLOCKED_EVIDENCE`
  并报告；③ 某判官字段要求而契约无来源 ⇒ 只报「该轮测量不完整」，不造读数。
- `next_after_done`: 判据冻结的真实封证完成后，按 `order` 登记/提升第 7 场景（`CORE/OFFLINE/ADMIT` promotion
  总账，阶段 F）的卡。
- `completion_evidence`:
  - **旧 baseline 只量不改（验收 ③）**：`2026-09-20` 那份 baseline bundle（`e3a99202…`）在当前 build 上经
    `report_promotion` 读到 `re_judged: UNJUDGED`（判据字节随 case_version 移动），旧 PASS 字节原样保留、未重写、
    未追加新 attempt。
  - **当前 build 真实 soak 封证（验收 ①）**：受控 bounded-soak 600 秒 / 间隔 10 秒、`llvmpipe` 软件渲染、两个
    JVM、分配新 attempt，封 `CORE-100`。run id `8367f741124d4132835eeb3d85833d46`，
    `evidence_directory /data/kin/kin-01/run/evidence/8367f741124d4132835eeb3d85833d46`，`attempt_sequence 1`，
    `status sealed`，15 件工件（含 `soak-samples.txt`、`soak-summary.json`），`bundle_digest
    1b2a58e9cc371d236b959b7e3507678d04506b6c32b875a5ce7ebd9f20c749e2`，`case_version
    d6e94bbc93ff1666eb1a9d631dcc94d08d0f9c4ff3d02ca8b503ab39090af451`，`result PASS`，三条断言逐条来自封存字节。
  - **四读一致（验收 ②）**：① `evidence verify` → `verified: true / sealed: true / violations: []`；②
    `rejudge_evidence` → `status: agrees`，三条 expected==observed、`failures: []`；③ `replay`（`python -m
    minekin_core replay` 与 `tools/replay_evidence.py`）→ `status: projected / violations: []`，终态 STOPPED，
    `trace_sha256 a6e4dee0…`；④ `report_promotion` → 该 bundle `PASS/verified/sealed`、`from_repository_build:
    true`、`re_judged: AGREES`，bridge_digest `faeec4a9df83abb9ca0404863e04d20cfd87ac0f3afd5e74b6858e3e15372f55`，
    attempt `SEALED`。
  - **report_soak 覆盖与缺口（验收 ④）**：`status: reported`、`verdict: PASS`、600s/10s、`ended_early: false`。
    client 56 样本、`last_elapsed 594`，RSS P50 1550.8 / P95 1553.2 / P99 1553.2 / max 1553.2 MB，线程 94–113；
    server 56 样本、`last_elapsed 594`，RSS P50 870.6 / P95 871.3 / P99 871.4 / max 871.4 MB，线程 53–74
    （nearest-rank）。tick/render 预算窗口只报覆盖不设阈值：run 文档捕获 tick 窗口 56（p50 2µs / p95 13 / p99 22 /
    max 20929µs，`missing_windows: []`）、tick_interval 窗口 56（p50 50662µs / p95 67029 / p99 67406，`missing:
    []`）、`received_windows 112`、`connection_state PLAYABLE`、`snapshots_admitted 1`；FPS/TPS/GC/队列深度/GPU
    无来源，如实标「未测/该轮不完整」，未声称性能合格。
  - **全量门禁绿（验收 ⑤）**：本轮无代码改动，全量 pytest `2159 passed / 2 skipped`（相对 `9f3946d`/`26a7543`
    无变化），case assertions 139 registered、fixture digests、boundaries、workflow pins、`git diff --check` 干净。
  - **三条 `stop_conditions` 均未触发**：封存通道把 soak 两份工件写进了 bundle（未动 `tools/`/`bridge/` 采样面）；
    一次真跑即封上（无连续三次外部阻断）；预算字段有 run 文档来源（未出现「契约无来源」）。
- `completion_commit`: 本次收卡 commit（纯文档）。

### P0-PROMOTION-LEDGER-001 — 封一次 campaign 的 CORE/OFFLINE/ADMIT 晋级总账

- `status`: `DONE`（`532446e` 登记 `QUEUED`、`28876e3` 提升 `NEXT`，本 commit 交付只读晋级总账）
- `promotion_reason`: 顺序已满足——登记它的 commit（`532446e`）之后计划里无 `NEXT`，中间没插入别的未授权工作；
  它是 `REAL-P0-CAMPAIGN-001.order` 的第 7 个也是最后一个场景（阶段 F 晋级总账）。上一张真实封证卡
  `TICK-RENDER-SOAK-RUN-001` 已在 `a26a51a` 收 `DONE`（`scenario_progress 6/7`）。提升前为纯文档改动，
  `git diff --check` 干净，代码 registries 未变。
- `registered`: 2026-09-24，由第 6 场景真实封证卡 `TICK-RENDER-SOAK-RUN-001` 收 `DONE` 触发；它是
  `REAL-P0-CAMPAIGN-001.order` 的最后一个场景。
- `depends_on`: 前六个场景各自封好的 bundle——`ADMIT-040`/`ADMIT-060`/`ADMIT-070`、
  `OFFLINE-010`/`OFFLINE-020`/`OFFLINE-030`（两子）、crash 窗口的 `CORE-020`/`CORE-060`（含两子）/`CORE-090`、
  第 6 场景的 `CORE-100`；读路工具 `tools/report_cases.py`、`tools/report_promotion.py`。
- `question`: 把七个 `order` 场景已封的 bundle 与机器 required-case inventory 汇成一张晋级总账——每个 gate 的
  present/missing、最新 attempt、PASS/FAIL/INCOMPLETE、case version/摘要、与当前 build 的关系、阻断原因，
  并把 `AGREES`/`UNJUDGED`/`DISAGREES` 分清楚——怎样做到**不新增判据/case/阈值、不再封任何 bundle、不重写任何
  既有 bundle**，并且**在 72 required 仍有 `runtime-required` 缺口时不把 `REAL-P0-CAMPAIGN-001` 宣布为 `DONE`**？
- `scope`: ① 只读重跑 `uv run --frozen python tools/report_cases.py` 与
  `uv run --frozen python tools/report_promotion.py --data-root <绝对 data-root>`，以**机器读数**为准记录
  required/present/missing（不抄本文陈旧计数）；② 汇总七场景各自已录的四读结果（verify / rejudge / 适用 replay /
  promotion），逐案标最新 attempt、`case_version`、`bridge_digest`、`from_repository_build` 与 PASS/AGREES；
  ③ 把仍缺的 required-case 族按机器 inventory 逐条列出并标各自阻断原因（需新断言 / 需产品决策 / 未冻结编号 /
  host-integrated / `PERSIST` `PlanningGap`），不凭例举编号计数、不静默丢弃；④ 明确写出 campaign 总体状态。
- `allowed_paths`: 仅 `docs/development-execution-plan.md`、`docs/development-todo.md`（记录总账）；
  `tools/report_cases.py`、`tools/report_promotion.py` 的**只读调用**。
- `forbidden_paths`: `src/`/`bridge/`/`proto/`/`tools/` 的任何代码改动；新增 case fixture/断言/registry/
  `mandatory` 翻转；封任何新 bundle；改写/删除/追加任何既有 sealed bundle 或旧 baseline；替用户决定
  HOST/PERSIST/未冻结 ADMIT 的缺口。
- `non_goals`: 不关闭 72 required 清单、不补任何新断言、不做 HOST/PERSIST/`ADMIT-010/020/…` 的产品决策、
  不设性能阈值、不把 campaign 标 `DONE`。
- `acceptance`: ① 计划里有一份完整总账表：每场景列 run id / bundle digest / attempt / verdict / `case_version` /
  build 关系 / 四读状态；② `report_cases.py` 的 required/present/missing 以当前机器读数重录（非本文旧值）；
  ③ 每一个仍缺的 required-case 族都按机器 inventory 列出并附阻断原因，无遗漏；④ `REAL-P0-CAMPAIGN-001`
  总体如实记为「第 7 场景（总账）已交付，但 campaign 仍 `BLOCKED/INCOMPLETE`」——因 `runtime-required` 缺口未封，
  **不**记 `DONE`；⑤ 全量门禁绿，且未触碰任何既有 sealed bundle。
- `validation_class`: `LOCAL`（对已封证据 + 机器 inventory 的只读汇总；不跑新的真实 run、不再封证）。
- `stop_conditions`: ① 若总账要求新增断言/case 或再封 bundle ⇒ 停下修订范围或另起逐案卡（不在本卡扩范围）；
  ② 若要求对 HOST/PERSIST/未冻结 ADMIT 拍板 ⇒ `BLOCKED_DECISION`，不猜编号；③ 若 `report_cases.py` inventory
  与各卡已录证据不一致 ⇒ 如实记录冲突，不改写封存证据来「对齐」。
- `next_after_done`: 总账交付后，`REAL-P0-CAMPAIGN-001` 剩下的只有需产品决策的 `runtime-required` 逐案缺口
  （HOST / PERSIST / 未冻结 ADMIT），全部为 `BLOCKED_DECISION`/`DEFERRED`；有界自主 P0 工作到此耗尽——交付
  阻断清单与门禁现状即诚实的阶段终点（阶段 G/H），不擅自宣布整个项目完成。
- `completion_evidence`（只读晋级总账，本轮不新增判据、不再封证、不重写任何 bundle）：
  - **机器 required-case inventory（`report_cases.py`，2026-09-24，验收 ②）**：`totals.required 74`、
    `present 43`、`missing 31`、`misattributed 0`、`not_gating 36`、`present_wanting_a_run 13`；按
    `validation_class` `local-only 7 / runtime-required 67`；`assertions 162`。本文旧的「72 required /
    36 present / 36 missing」快照已被此读数取代（保留不抹，仅记其已陈旧）。gate 满足度：
    `W00/W10/W20/W60/W70 satisfied:true`；`W30/W40/W50/host-integrated/p0-core/p0-nav-exp satisfied:false`。
    `planning_gaps`：`PERSIST` = `UNFROZEN_CASE_IDS`（不 gate 任何门）。
  - **七场景最新 PASS/AGREES bundle（`report_promotion.py --data-root /data`，验收 ①）**：当前 reviewed build 的
    `bridge_digest faeec4a9`。
    - 场景 1 `ADMIT-040` run `6b5856d5…` att 1 `PASS/AGREES` `cv ec49f61c` — **`from_repository_build:false`**
      （sealed 于旧 build `bridge 9a30cdb7`，非当前 build）。
    - 场景 2 `ADMIT-060` run `7bc740ea…` att 2 `PASS/AGREES` `cv 8ee31d23` — **`from_repository_build:false`**
      （旧 build `bridge ecff5a59`；其 att 1 是判据读侧缺陷那次的 `FAIL/DISAGREES`，保留不覆盖）。
    - 场景 3 `ADMIT-070` run `2a128d0d…` att 2 `PASS/AGREES` `cv d829381d` `frb:true` `bd faeec4a9`。
    - 场景 4 `OFFLINE-010` `f2ecb728…`/`OFFLINE-020` `3d5606ce…`/`OFFLINE-030-PRISM-PARITY-001` `ee9d5ad3…`/
      `OFFLINE-030-ENUM-ALIGNED-001` `cb5e2119…`——四份均 att 1 `PASS/AGREES` `frb:true` `bd faeec4a9`。
    - 场景 5 crash `CORE-020` `8a72dcdf…`/`CORE-060` `7fc0671e…`(att 3)/`CORE-060-CLIENT-001` `c89f5d35…`/
      `CORE-060-SERVER-001` `f4365a50…`/`CORE-090` `3e94d49a…`——均 `PASS/AGREES` `frb:true` `bd faeec4a9`。
    - 场景 6 soak `CORE-100` run `8367f741…` att 1 `PASS/AGREES` `cv d6e94bbc` `frb:true` `bd faeec4a9`。
    - `evidence`：`unsealed/unverified/unreadable` 皆 `[]`；`from_another_build` 非空（含场景 1、2 及历次诊断/
      旧 build 封存）；总 bundle 计数以机器为准。
  - **仍缺的 required-case 族与阻断原因（验收 ③，全部按机器 inventory，不凭例举计数）**：31 条 `runtime-required`
    `missing`（`report_cases.py`）——`CORE-080`、`NAV-EXP-010`、`ADMIT-010/020/030/050/090/120`、
    `OFFLINE-060/070/080/090/100`、`HOST-001/090/100`、`HOSTCTL-020/030/040/080/090`、
    `HOSTCOMMIT-001/010/020/030/040/050/060/070/080/100`。阻断原因分类：`ADMIT-010/020/030/050/090/120`、
    `OFFLINE-060/070/080/090/100`、`CORE-080` 需**先把判据写成断言**（每写一条即定义一次 PASS，属逐案证据设计，
    非本卡范围）；`HOST-*`/`HOSTCTL-*`/`HOSTCOMMIT-*` 整族属 **host-integrated、需产品决策**；`NAV-EXP-010`
    属 `p0-nav-exp` 缺口；`PERSIST` 族 `UNFROZEN_CASE_IDS` 不 gate。
  - **promotion 总体（验收 ④）**：`report_promotion.py` 不带 `--work-package` 时 `status: blocked`、
    `overall.promotable:false`、`blocks [CASE_VERSION_MISMATCH, CASE_WITHOUT_EVIDENCE,
    REQUIRED_CASE_NOT_REGISTERED]`、`blocking_cases 37`；`repository_build.gates_promotion:false`。逐 gate
    `promotable` 全 `false`。**如实记：七个 `order` 场景全部走完（`scenario_progress 7/7`），但
    `REAL-P0-CAMPAIGN-001` 总体 `BLOCKED/INCOMPLETE`——74 required 中 31 条 runtime-required 未登记、多条
    present 的 runtime/local case 因 case_version 移动或缺当前 build 证据而 `CASE_VERSION_MISMATCH`/
    `CASE_WITHOUT_EVIDENCE`，且场景 1/2 的 PASS 在 `from_repository_build:false` 的旧 build 上——
    **绝不因七场景齐了就标 campaign `DONE`**。
  - **未触碰封存证据 + 全量门禁（验收 ⑤）**：本轮零代码、零封存改动，未改写/追加/删除任何 sealed bundle 或旧
    baseline；`report_cases.py`/`report_promotion.py` 均只读。全量 pytest `2159 passed / 2 skipped`（无代码变化）。
  - **三条 `stop_conditions` 均未触发**：总账不要求新断言/新封（只如实列缺口）；HOST/PERSIST/未冻结 ADMIT 一律
    记为需产品决策、未替用户拍板（`BLOCKED_DECISION` 边界保留）；inventory 与各卡已录证据一致（差异仅为
    「旧 build 封存」这一如实事实，未改写封存来对齐）。

### OFFLINE-IDENTITY-SEALED-ARGV-001 — 让封存时的 live 判读也拿到那份 argv

- `status`: `DONE`（`9ffe980` 登记为 `QUEUED`，收卡 `OFFLINE-IDENTITY-CASE-001` 的 `1a77d40` 之后
  由 `58c9d8f` 提升为唯一 `NEXT`，2026-09-24 交付完成）
- `promotion_reason`: 顺序已满足——本卡在 `9ffe980`（当时唯一 `NEXT` 是 `CASE-001`）以 `QUEUED`
  登记并推送，随后 `CASE-001` 交付（`2a84bbd`）与收卡（`1a77d40`）都在提升之前，中间没有插入别的
  未授权工作。它是 `OFFLINE-IDENTITY-RUN-001` 的前置：不补上 live 侧那一格 argv，两次真实封证里
  判据 ① 在封存现场会读到 `LAUNCH_ARGV_UNRECORDED`，只有 rejudge 那条读路成立。
  入口门禁全绿（`2140 passed / 2 skipped`、case assertions 139 registered、Pyright 0）。
- `baseline_sha`: `1a77d40fa56e4c6bbc76a4a6cab408f35e3ab46a`
- `question`: `tools/seal_run_evidence.py:664` 把 run 交给 `read_run_material` 时没有传
  `session_argv`，而判据 ① 需要它。封存现场要怎样把这份 argv 交进 live 判读，才与 rejudge 从
  `orchestrator-trace.json` 读出的完全是同一份？
- `depends_on`: `OFFLINE-IDENTITY-CASE-001`（判据先存在，这张卡才有对象）。
- `why_now`: `CASE-001` 的判据 ① 在**封存后**的读路上已经闭合——`collect_artifacts` 早就把
  `orchestrator-trace.json` 写进 bundle，判官从 bundle 目录读得到。缺口只在**封存当时**那一次判读：
  `read_run_material` 的签名没有 `session_argv` 参数，sealer 也没有传。补齐要动
  `tools/seal_run_evidence.py`，它在 `CASE-001` 的 `allowed_paths` 之外，故另立此卡。缺口按
  `stop_conditions` 如实记在 `CASE-001` 的证据里，不放宽判据、也不事后追认越界文件。
- `scope`: `read_run_material` 增 `session_argv: tuple[str, ...] | None = None` 参数，sealer 在
  已有 `orchestrator_trace(...)` 结果处把它传入（一行读数，不做第二份真相）；`run_asserter` 若也要
  在 live 侧判读归因，则同样把这份文本带过去。附一条测试：同一 run 的 live 判读与对同一 bundle 的
  rejudge 读出**逐字相同**的 argv。
- `allowed_paths`: `tools/seal_run_evidence.py`、`tools/assert_case_evidence.py`（只加
  `read_run_material` 的入参，不改判据实现）、`tests/unit/test_seal_run_evidence.py`
  （或该模块现有归属的测试文件）、`docs/development-execution-plan.md`、`docs/development-todo.md`。
- `forbidden_paths`: 产品代码、Bridge/`proto/`、runner 脚本与领域运行分支、case registry 与
  `mandatory` 翻转、旧 bundle。
- `non_goals`: 不改写任何判据语义、不新增封存工件、不在本卡封 OFF-A/OFF-B 证据。
- `acceptance`: ① 一次真实受控运行的 live 判读与 rejudge 对判据 ① 给出同一结论；② argv 缺失
  （没有 trace 工件）时两条读路都判「未记录」而不是空 argv；③ 全量门禁绿。
- `validation_class`: `LOCAL_THEN_REAL_RUN`。
- `stop_conditions`: 若 `orchestrator-trace.json` 在 live 侧根本不可读（写入发生在判读之后），停在
  该卡并把顺序问题记为 `BLOCKED_EVIDENCE`，不得改为让 sealer 凭记忆重造 argv。
- `completion_commit`: `d8348a37addc6f75f726e7f473080d1037e96a8c`（只改三份文件：
  `tools/seal_run_evidence.py`、`tools/assert_case_evidence.py`、`tests/unit/test_seal_run_evidence.py`；
  已推到 `refs/heads/codex/core-state-transition` 与 `refs/heads/main`，`git ls-remote` 读到两条都等于
  上面那个 sha。本节与 TODO 记录是紧随的收卡 commit，提升下一卡再往后一条）。
- `completion_evidence`:
  - **交接的形状**：`seal()` 的 `session_argv` 只有一个来源——它就是 `orchestrator_trace(...)`
    往 `session_argv` 字段里写的那一份（`tools/seal_run_evidence.py:745`）。本卡把同一个变量在
    `:678` 交给 `run_asserter`、在 `:688` 交给 `read_run_material`，因此 live 判读拿到的与 bundle
    里封存的不是两份需要保持同步的记载，而是同一份 list 的两个去向：没有做第二份真相，也没有让
    sealer 凭记忆重造 argv。
  - **顺序问题的实际形状**：判读发生在 trace 写出**之前**，所以「live 侧读不到那份 JSON」这条阻断
    从一开始就不是靠改顺序解决的——判官不需要那个文件，sealer 手上已经有它要装进去的内容。
    `stop_conditions` 因此未触发，也没有记 `BLOCKED_EVIDENCE`。
  - **一份 argv，一条归一规则**：新增 `recorded_argv`（`tools/assert_case_evidence.py:479`），
    `read_run_material` 的入参与 `_trace_argv` 读出封存 trace 时都走它。规则是「空 ⇒ `None`」，
    于是 `seal()` 的默认 `()`、封存下来的 `session_argv: []`、以及根本没有 trace 三种情形，在两条
    读路上都读成「什么都没记下来」⇒ `LAUNCH_ARGV_UNRECORDED`，而不是一侧 `None`、一侧空元组。
    `_trace_argv` 的 docstring 原本就写着这层意思，代码此前没做到；本卡把它做到。
  - **交接通道**：判官 CLI 新增 `--session-argv-json`（不是 `REMAINDER`，因此不要求放在最后），
    非 JSON / 非字符串列表一律 `_reject`，判不出就不封。`run_asserter` 只在 `session_argv` 不为
    `None` 时带上这一面旗。
  - **验收 ②（本地即终态）**：`test_a_seal_that_never_saw_an_argv_says_so_the_same_way_twice` ——
    封下来的 trace 里 `session_argv` 是 `[]`，live 的 `read_run_material(..., session_argv=())`
    与 `read_sealed_material(bundle)` 都读出 `None`，判据 ① 两侧同为
    `{ATTRIBUTION}:LAUNCH_ARGV_UNRECORDED`。
  - **验收 ① 的本地那一半**：`test_the_argv_the_seal_writes_is_the_argv_the_live_judgement_reads`
    钉住三处逐字相同（live 字段 = 封存读路 = trace 工件）；
    `test_the_live_judge_can_refuse_a_launch_on_the_argv_it_was_handed` 用**真的**
    `SEALER.run_asserter`（子进程，走那条 JSON 旗）对同一个 run 拿三种命令行判出三种答案：
    对的一列 ⇒ `CORE_NAMED_NO_CANDIDATE`（这个 run 没记身份行，点名对了也仍要拒）、
    另一列 ⇒ `ARGV_NAMES:enum-aligned`、没点名 ⇒ `CANDIDATE_NOT_NAMED_IN_ARGV`；
    `test_an_offline_launch_judged_live_and_re_judged_disagrees_about_nothing` 封 OFFLINE-010 后
    用 `REJUDGE.rejudge` 读出 `disagreements == []`，并逐条（不是按集合）比 for failures。
  - **顺手挖出的第二个缺陷**：`assertions_from` 把 failures 排了序，而 `rejudge_evidence.disagreements`
    是**按位置**比 `expected`/`observed`/`failures` 的。单条失败两种写法一样，所以这个缺陷一直藏着；
    一次判据 ① 的封证有两条以上同时拒绝，才露出 `FAILURES:recorded=<字母序>,re-judged=<声明序>`——
    一 bundle 的封存 verdict 用它自己的字节复现不出来。修法是去掉那次 `sorted()`（`observed` 从来
    就没排过序）。已核对影响面：`.tmp/data` 下现存 bundle 里**没有任何一份**记录了 2 条以上失败
    （脚本扫过全部 `manifest.json`），PASS bundle 的 failures 为空，因此没有旧证据被这次改动改变读数；
    需要改的期望只有一处——`tests/unit/test_seal_run_evidence.py` 里钉住 core-020 三条失败的那张，
    按 `offline`/`core-020` 的实际声明顺序
    （`server_observed_join_identity` → `first_snapshot_admitted` → `leave_after_join_observed`）重写。
    判据字节未动：`tools/check_case_assertions.py` 仍是 139 registered，`verify_fixture_digests.py` 全绿。
  - **验收 ③**：`uv run --frozen pytest -q` = `2144 passed, 2 skipped in 276.75s`（本卡新增 4 个测试
    函数，2140 → 2144；两处 platform skip 与既有基线同因）；`ruff check . -q`、`ruff format --check .`
    （304 份文件）全清；`pyright` 0 errors / 0 warnings；`check_case_assertions.py` OK（139 registered）、
    `verify_fixture_digests.py` `W00 schema and fixture digests: OK`、`check_boundaries.py` OK、
    `check_workflow_pins.py` OK、`git diff --check` 干净。
  - **未验证 / 留下的限制**：
    1. 验收 ① 的**真实受控运行**那一半不在本卡兑现——本卡 `non_goals` 就写明「不在本卡封
       OFF-A/OFF-B 证据」，且 `test-orchestrator/runner/domain.sh` 里今天没有任何 OFFLINE 场景分支
       （grep `identity-candidate` / `offline-0` 为空）。这条检查随 `OFFLINE-IDENTITY-RUN-001` 的头一次
       真实封证执行，提升该卡时写进它的 `acceptance`，不在这里当作已完成。
    2. runner 早已在 `domain.sh:1923` 用 `--session-argv "$@"` 把命令行交给 sealer，所以本卡没碰
       runner。但同一份脚本在 `:734` 以 `python -m minekin_core "$@" "${lan_args[@]}"` 启动 Core：
       脚本自己追加的 LAN 连接参数不在这份 argv 里。封进去的是「操作者那一段命令行」，不是进程的
       完整 argv。判据 ① 问的恰是「操作者点名了哪一列」，因此这个形状够用；如实记下，留待真实封证
       时对照。
- `next_after_done`: `OFFLINE-IDENTITY-RUN-001`（OFF-A 与 OFF-B 各自封证并四读一致；它同时承接本卡
  验收 ① 的真实运行那一半）。

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

### VERSION-AUTO-DESIGN-001 — 恢复跨版本自动探测与受管安装的产品路线

- `status`: `DONE`（先前已作为 `QUEUED` 登记；用户在 `ed0db6d` 的七场景总账后明确选择此路线，
  `94ad677` 单独提升为 `NEXT`；本提交交付设计，后继实现卡先只登记 `QUEUED`）。
  当前 P0 受控原型的 1.21.4
  pin 是阶段基线，不是产品最终只支持这一版的决定。
- `promotion_reason`: 用户要求把从自动探测到目标服最小控制的整条路线写为可连续执行文档，
  明确优先于仍需决策的 HOST/PERSIST；此卡的输出是规划与任务拆分，不是运行证据。
- `baseline_sha`: `17e74b88404c3cf3237cb0f34ff00da224feb807`
- `why_now`: 用户明确指出已有一台 1.20.1、关闭正版验证的测试服，并重申
  Minekin 应自动探测服务器版本、选择/下载适配的本地客户端。此前一次答复
  错把 1.21.4 原型边界说成产品目标。当前代码的 `server_profile.py` 同时
  强制 `P0` loopback 与 `minecraft_version == 1.21.4`；`src/minekin_core`
  尚无接入 session start 的 Server Probe、Version Resolver 或多版本 Bundle
  Registry。`tests/unit/test_server_profile.py::test_unreviewed_values_are_rejected`
  目前刻意拒绝其它版本。这些事实说明“自动选择多个已验证版本”尚未实现，
  不是用户需要手动下载正确版本。
- `contract_anchors`: `docs/managed-client-runtime.md` 的“固定产品结论”第
  3–6 项及“服务器版本自动识别”；`docs/launcher-supply-chain-contract.md` 的
  Server Probe、不可变 Client Bundle 与原子安装；`docs/version-license-matrix.md`
  的“probe-only/第二 bundle”；`docs/roadmap.md` 第 40 项。
- `activation`: 当前受控 campaign 的关键路径未被擅自中断；当用户明确要求
  把多版本提前，或当前 `NEXT` 完成后按授权队列重新评估优先级。无论先后，
  声称支持用户 1.20.1 服之前必须先完成本卡及后继实现/真实验收。
- `allowed_paths`: 上述专项契约、`docs/development-execution-plan.md`、
  `docs/qoder-execution-handoff.md` 与进度记录；只读探针可以访问用户明确给出的
  测试端点，但不得将公网地址写入仓库或连接协议游戏会话。
- `forbidden_paths`: 产品/Bridge/runner 实现、版本 fixture、artifact pin、
  对外服务器的世界数据与管理配置、CI。
- `scope`: 冻结最小跨版本竖切和任务拆分：①状态 ping 及 DNS/SRV/protocol
  取证，②以协议号为主的 catalog/歧义规则，③每个 Minecraft/Fabric/Bridge/
  Java/平台组合的 candidate→tested 验收，④缺失工件的受信上游下载、哈希验证、
  内容寻址缓存与原子安装，⑤停止旧客户端/失效 generation 后选择新 bundle，
  ⑥远程 Server Profile 的显式地址策略与服务端身份交叉验证。对 1.20.1
  建第二 bundle 的可构建性清单，不假定 1.21.4 Bridge 可直接复用。
- `non_goals`: 不把状态 ping 当作认证模式证明；不承诺任意版本都可自动
  下载后立即入服；不在已有 JVM 热换版本；不循环试遍版本；不把可下载的
  candidate 冒称 tested；不修改当前 ADMIT-070 判据。
- `acceptance`: 形成可独立执行的 probe、bundle-1.20.1、resolver/installer、
  remote-profile、end-to-end 五张小卡，每张有输入输出、精确允许路径、失败
  分类、反例、门禁与 stop condition；说明 1.20.1 探测结果与可用 bundle
  分离，低置信度/伪造 ping/代理多版本时 `NEEDS_PIN` 或明确阻断；缓存未命中
  时只自动安装已有受审 `tested` 清单的工件；任何新增版本通过独立构建、
  Bridge 握手、JOIN/首快照、服务端身份与回归门禁后才进入 tested。
- `validation_class`: `DOCS_THEN_LOCAL_THEN_REAL_RUN`（本设计卡仅 DOCS）。
- `stop_conditions`: 若产品是否支持 1.20.1、该版本 Bridge 移植范围、协议
  共享版本优先级或公网地址信任策略需要新的产品选择，列选项与证据交用户
  决定；不得把测试服在线可达等同于已验证兼容。
- `completion_evidence`: [跨版本自动入服与最小控制连续执行计划](version-auto-to-server-control-plan.md)
  从受信 Server Profile、只读探测、1.20.1 独立 candidate 与受控验收、tested registry、
  安全安装、切服、目标服入服到 look/move/release 分成 V01–V10 十张依赖明确的卡；
  原卡要求的 probe、bundle、resolver/installer、remote-profile、E2E 五类均有对应卡。
  每张含输入输出、允许路径、反例/失败分类、门禁、停止条件；没有产品代码改动、没有连接用户服，
  未把 1.20.1、任意公网目标或 overall P0 晋级标为 tested/PASS。全量本地门禁
  `2159 passed / 2 skipped`、Ruff/Pyright/boundaries/case assertions/fixture digests/workflow pins/
  `git diff --check` 全绿。
- `completion_commit`: `2c4e600`（已推送并核对远端两个分支）。
- `next_after_done`: `VERSION-REMOTE-PROFILE-001`（此时仅 `QUEUED`；下一提交单独提升）。

### VERSION-REMOTE-PROFILE-001 — 让运行者保存一个明确授权的远程目标

- `status`: `DONE`（`2c4e600` 登记 `QUEUED`、`36764e8` 提升 `NEXT`；本提交收卡）。
- `promotion_reason`: 用户已明确 1.20.1 私有测试目标与跨版本优先级；探测必须先有可信
  Server Profile，而本卡仅改 schema/地址策略，不发送游戏连接。
- `baseline_sha`: `94ad677`（设计卡提升时的已推送基线；领取本卡时另记实际 checkout SHA）。
  领取时实际 checkout = `36764e8`（本地与两远端一致，工作树干净）。
- `depends_on`: `VERSION-AUTO-DESIGN-001`；下游 `VERSION-SERVER-PROBE-001` 必须先有受信目标。
- `question`: 如何在 v1 loopback/1.21.4 原样回归的同时，用 v2 profile 表达用户明确批准的
  单一远端目标和版本策略，并在 DNS/SRV 解析后仍执行地址策略？
- `scope`、`allowed_paths`、`forbidden_paths`、负向矩阵与本卡逐项验收：见
  [连续执行计划的 V01 卡](version-auto-to-server-control-plan.md)；
  主计划唯一 `NEXT` 与更具体专项契约优先。
- `non_goals`: 不探测/连接游戏服、不下载工件、不放行任意公网、不做在线认证；
  用户目标地址仅在私有 profile，不写 repo。
- `validation_class`: `LOCAL`（含地址策略与 schema 反例）；如触及真实解析/连接，按 V02 另取证。
- `stop_conditions`: 需要扩大无条件禁区或默认开放任意公网时停下请用户决策，不自行改策略。
  —— 未触发：v2 只能保存文档里逐字段声明过的**单一显式目标**，任意公网/网段放行仍是禁区。
- `implementation_record`: v1 加载器语义与字节不变（只抽出共用的读取/路径守卫助手，
  fail-closed 消息与 revision 算法原样；v1 冻结 schema 与 fixture 一字未动）。新增
  `schemas/server-profile-v2.schema.json`（管理者写入：显式、规范化的 IP 字面量 host/port、
  `auth_mode: offline`、`version_policy{mode: explicit_allowlist, allowed_versions}`、
  可选 `pinned_bundle_id`、`resource_pack_policy`、`target_authorization{granted_by, basis}`，
  `additionalProperties:false`）与产品入口 `load_managed_target_profile`——逐字段 fail-closed、
  revision 用与 v1 相同的 canonical-JSON digest；**会话启动路径仍只消费 v1**，本卡不产生
  任何网络或游戏协议动作。`AddressPolicy.for_explicit_target` 把保存的目标固化为 /32 或
  /128 单地址策略，供 V02 在 DNS/SRV 解析后重验；IPv4-mapped IPv6 字面量显式拒绝，
  堵住内嵌 v4 绕过无条件禁区的形状。匿名 fixture 用 TEST-NET-1 文档保留地址，
  运行者的真实端点不进 repo。
- `counterexamples_driven`: 非字面量/未规范化/前导零/mapped 主机、`169.254.169.254`、
  `fe80::1`、`0.0.0.0`、`::`、`224.0.0.1`、`ff02::1` 作为保存目标、v1 文档喂 v2 加载器、
  v2 文档喂 v1 加载器、缺字段/未知字段/残留 `visibility`、在线 auth、空/畸形/重复/
  非 reviewed mode 的 version_policy、短 basis、大写 `granted_by`、`.minecraft` 内路径、
  端口溢出（0/65536/字符串/浮点/bool）——各自作为参数化用例断言拒绝；契约测试把 v2
  加载器逐案对表冻结的 v2 JSON Schema，产品更严处显式列成 `KNOWN_STRICTER_V2` 清单，
  新增分叉会让契约测试变红而不是静默放行。
- `gates`: 全量 `uv run --frozen pytest -q` **2274 passed / 2 skipped**（skip 为既有
  Windows 信号语义项）；定向三件（`test_admission_address`/`test_server_profile`/
  `test_server_profile_schema`）203 passed；Ruff check、Ruff format --check、Pyright
  0 errors、boundaries、139 case assertions、fixture digests、workflow pins、
  `git diff --check` 全绿。`tools/report_cases.py` 读数不变：74 required / 43 present /
  31 missing（本卡 `LOCAL`，不新增正式 case，不封 bundle）。无 CI 依赖、无 Minecraft
  真实运行：本卡不声称观察到任何真实解析或连接。
- `not_tested`: DNS/SRV 实际解析、对任何真实端点的探测与入服、1.20.1 bundle 可用性——
  分属 V02/V03/V04 及以后，本卡不预支其证据。
- `next_after_done`: `VERSION-SERVER-PROBE-001`，必须先 `QUEUED` 登记并独立提升。

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
