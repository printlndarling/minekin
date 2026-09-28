# P0-OFFLINE-080-CASE-SPEC-001 — OFFLINE-080 案例定义 / oracle 与载体设计

- 卡片：`P0-OFFLINE-080-CASE-SPEC-001`（只定义 `OFFLINE-080` 一条）。
- 授权来源：[本地 LAN 控制队列](v1201-lan-control-next-2026-09-27.md) §3 的第二类独立工作 —— 「把 B2 尚无 fixture 的非 HOST case 按『先设计 oracle/载体、后真跑』的顺序逐张排卡」，并「先写 owner/allowed_paths/验收」。
- owner：**M 主控**（设计面）。下游若走登记，是另一张 M 独占面卡（`tools/assert_case_evidence.py` + `tools/check_case_assertions.py` 的 `IMPLEMENTATIONS` + `tests/fixtures/cases/offline-080.json` + `manifest.sha256`），本卡不实施、不预约。
- allowed_paths（本卡）：`docs/p0-offline-080-case-spec-2026-09-28.md`（本文件）、`docs/v1201-lan-control-next-2026-09-27.md`、`docs/qoder-execution-handoff.md`。
- 禁止（本卡全程遵守）：不写断言函数、不加 fixture、不改 `manifest.sha256`、不改 registry / `mandatory` / 任何门、不改 `src/**`、`tools/**`、`bridge*/**`、`test-orchestrator/**`；**不挂载任何数据卷**（连 `:ro` 都不需要，下文全部读数取仓库字节）；不连任何远端 / 公网服务器。主干唯一的 integration `NEXT` 仍是 `PARALLEL-INTEGRATION-GATE-001`，本卡不提升为 `NEXT`、不占任何 lane 的 `lane_next`。
- base 与现场：主干 `efe8c66e0760004e3747b613a5c4e5324a32dc5c`（`git rev-parse HEAD`；`git ls-remote origin refs/heads/main` 同值；写本文件前 `git status --porcelain` 0 行）。
- 引用纪律：下文每个行号都是本轮在 base 字节上重测的（脚本与日志在 `.tmp/m-r80/`，该目录**未入版本控制**，故每条都另给一条仓库内等价命令）。旧文档与先前会话的原话一律不作证据；未在本轮跑过的判法一律标「本卡未测」，由字节推出的判断标「（推断）」。全文**不出现**任何把 080 记作通过的结论。

## 1. 受测契约文本（逐字 + 仓库字节出处）

契约行（`docs/p0-offline-session-compatibility-contract.md:154`）：

> `| OFFLINE-080 | online-mode、白名单和封禁 | 分类分别为认证/准入失败，不循环换身份 |`

这一行有**三格场景**（online-mode / 白名单 / 封禁）与**两格判据**（分类分别为认证/准入失败；不循环换身份）。本卡按「三场景 × 两判据」的六格逐格给 oracle、载体、反例与阳性对照（§3），不合并、不用其中一格的绿去替另一格。

隔离服约束（同一契约 `:158`，逐字）：

> 所有case只在运行者控制的隔离服执行。不得用第三方公网offline服务器做身份探测。

在册状态：`OFFLINE-080` 已在 `src/minekin_core/domain/cases.py:353`，处在 `_phase_cases(_OFFLINE, ValidationClass.RUNTIME_REQUIRED, "W30", …)` 块（`cases.py:341-356`）内 ⇒ 它缺的不是 registry 行，而是**fixture 与判据**。

底数（本轮实测）：`tests/fixtures/cases/` 共 **53** 份，`offline-*` 系为 `001/010/020/030/030-enum-aligned-001/030-prism-parity-001/040/050/070/090/100` 共 11 份 ⇒ **`offline-080.json` 不存在**（同族 `070/090/100` 都在）。`docs/development-execution-plan.md:256` 记的 `W30.absent` 在 070 登记后为 2 条（`OFFLINE-060`、`OFFLINE-080`），本卡不动这个读数。

混合载体口径（`docs/p0-evidence-inventory-2026-09-26.md:170`， dated 原文照引不改）：白名单与 `AUTH_MODE_MISMATCH` 两类属**甲**（事实已记、只缺断言），封禁那半句属**乙**（无产品载体）。该行的两处具体引用本轮已按当前字节更正：函数体是 `ClientAdmissionController.java:426-449` 而非 `:426-447`（旧行号少两行），1.20.1 孪生面在 `bridge-1201/…/ClientAdmissionController.java:441-464`；「16 个具名分类 + `UNSPECIFIED`」这句成立（枚举块 `proto/minekin/v1/observation.proto:24-49`，成员 17 个、值 0..16）。

## 2. 载体底数（本轮仓库字节实测）

复现命令都在 §6；这里只列读数与它锁住的判断。

| # | 量 | 读数（base 字节） | 对 080 的含义 |
| --- | --- | --- | --- |
| 1 | Bridge 分类器 | `classifyDisconnect` = `bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:426-449`；六个分支依次为 blank→`UNEXPECTED_DISCONNECT`（`:428-429`）、白名单→`WHITELIST_REJECTED`（`:431-432`）、重名→`DUPLICATE_LOGIN`（`:434-435`）、认证三句→`AUTH_MODE_MISMATCH`（`:437-440`）、版本→`PROTOCOL_MISMATCH`（`:442-443`）、资源包→`RESOURCE_PACK_BLOCKED`（`:445-446`），末尾回落 `UNEXPECTED_DISCONNECT`（`:448`） | 三场景里的**白名单、认证**两格有分类器；**封禁没有** —— 函数体与整份文件的 `ban` 词族命中 **0** ⇒ 一句封禁响应按 `:448` 的设计落 `UNEXPECTED_DISCONNECT` |
| 2 | 分类词汇表 | 枚举块 `proto/minekin/v1/observation.proto:24-49`：`UNSPECIFIED = 0` + 16 个具名（1..16，含 `CONNECTION_REFUSED = 16`），**无 ban 名** | 「封禁」今天**无法被说出口**：既没有分支也没有词。这是主控决策格（`docs/development-execution-plan.md:250` 的 `BLOCKED_DECISION` 行已点名「封禁是否成为独立准入分类」） |
| 3 | 已跑绿的兄弟判据 | `the_refusal_was_classified_in_the_ledger`（`tools/assert_case_evidence.py:2339-2355`，拒名 `NO_CLASSIFIED_REFUSAL`）、`the_bridge_classified_the_refusal`（`:2357`）＝白名单两记录；`the_auth_mode_mismatch_was_classified_in_the_ledger`（`:2702-2722`，要求 `phase=FAILED` + `reason=…AUTH_MODE_MISMATCH` + `source=BRIDGE` + `trust_class=BRIDGE_FILTERED` 四件事同行，拒名 `NO_CLASSIFIED_AUTH_MODE_MISMATCH`） | 两格的 oracle **形状已定**：读账本 `SessionInterrupted{phase, reason}` 这一**对**（常量 `SESSION_INTERRUPTED = "SessionInterrupted"` `:103`、`WHITELIST_REJECTED` `:186`、`AUTH_MODE_MISMATCH` `:195`），不读服务端原句 —— 契约把任意服务端文本挡在产品事件外，能旅行的只有分类 |
| 4 | 「不循环换身份」的现成读法 | `the_refusal_left_the_run_on_one_policy_and_one_process`（`:2725-2755`）：锚点**硬编码** `AUTH_MODE_MISMATCH`（`:2739`），无锚点即返回 `NO_AUTH_MODE_REFUSAL_TO_ORDER_AGAINST`（`:2742`）；三条红名 `POLICY_FROZEN_MORE_THAN_ONCE`（`:2748`）、`CLIENT_STARTED_MORE_THAN_ONCE`（`:2750`）、`PROCESS_OR_POLICY_ROW_AFTER_THE_REFUSAL:<event_type>`（`:2751-2754`）；docstring `:2728-2731` 明说「单看进程数只证明没重启，必须与唯一一次策略冻结配对」 | 第三格判据**只对认证场景存在**。同一函数交给白名单 run 会**具名拒答**而不是绿 —— 这是好事（沉默不被读成通过），但也意味着白名单/封禁两格各需一条自己的配对读法 |
| 5 | 身份旅行的载体 | `PROCESS_STARTED = "SessionProcessStarted"`（`:102`）、`AUTH_POLICY_FROZEN = "AuthPolicyFrozen"`（`:196`）、`SESSION_IDENTITY_COMPARED`（import `:56`）与 `identity_candidate_id`（`:3184`、`:3379`、`:3421`、`:3472`）；已有读法 `this_run_started_the_identity_candidate_the_case_names:3350`、`core_recorded_the_identity_it_compared:3385`、`the_reported_session_is_the_identity_this_run_launched_with:3398` | 「换没换身份」在材料里**看得见**（候选名 + 进程行 + 身份比对行）。但今天**没有一条断言**这样读它：现有那三条读的都是「本次 launch 的身份对不对」，不读「拒止之后是否又起过一个不同身份」 |
| 6 | 代码侧有没有重试换身份 | `candidate_by_id` 对未知 id 抛 `ValueError`（`src/minekin_core/adapters/launcher/offline_session.py:104-110`）、候选集封闭两条（`PRISM_PARITY:67-74`、`ENUM_ALIGNED:79-86`、`OFFLINE_SESSION_CANDIDATES:87`）、CLI 的 `choices` 取自同一集合（`cli/parser.py:238`）；`grep -rn "for candidate\|next_candidate\|rotate\|retry"` 在 launcher/cli 的命中逐条看过，两处 `for candidate` 是选择/校验循环（`offline_session.py:106`、`cli/session.py:334`），另三处是 `Retryability.OPERATOR_ACTION` 枚举值（`artifacts.py:37`、`metadata.py:105`、`recipe.py:123`）⇒ **没有「被拒后换身份重试」的分支** | 结构上没有换身份的回路，**不等于**判据可以省：契约问的是「这一次 run 记下了什么」，那要读材料。把 #6 当作绿是 category error（同 `:2728-2731` 拒绝「进程数单独即证」的口径） |

## 3. 逐格 oracle / 载体 / 反例 / 阳性对照

命名仅为**设计文本**：本卡不写断言函数、不登记 `IMPLEMENTATIONS`、不加 fixture。断言名一律从契约那两格判据派生，不加填充式断言。

### 3.1 场景格 A（online-mode）× 判据「分类为认证失败」—— 甲，形状已钉死

- oracle：账本里存在一行 `SessionInterrupted{phase: FAILED, reason: …AUTH_MODE_MISMATCH, source: BRIDGE, trust_class: BRIDGE_FILTERED}`。
- 载体：#3 的 `the_auth_mode_mismatch_was_classified_in_the_ledger:2702-2722`。**复用允许**：070 的草稿与本卡共用既有兄弟判据的先例，仓库里也已有 `admit-040.json` 把它跑绿（6 条断言、`docs/p0-admit-five-run-2026-09-26.md:102`，当前构建 `case_version daeb4ed5150734e7…2be61545`）。
- 反例（须红，名字取自现码）：把该行 `reason` 伪造成 `…WHITELIST_REJECTED` 或 `…UNEXPECTED_DISCONNECT` ⇒ `NO_CLASSIFIED_AUTH_MODE_MISMATCH`；把 `trust_class` 从 `BRIDGE_FILTERED` 换成别处 ⇒ 同一名（四件事缺一即红，`:2715-2720` 是 AND）。
- 阳性对照（不得红）：认证不符真跑那份材料原样 ⇒ 判绿。**本卡未跑**（无 080 fixture、无 080 bundle），只由 `admit-040` 已登记的同一函数担保。

### 3.2 场景格 B（白名单）× 判据「分类为准入失败」—— 甲，两记录形状

- oracle：账本 `SessionInterrupted{phase: FAILED, reason: …WHITELIST_REJECTED}` **且** 客户端日志里 Bridge 自己那行分类（`REFUSAL_LINE = "bridge classified the login failure as …WHITELIST_REJECTED"`，`:187`）。两条各一条断言，理由写在 `the_bridge_classified_the_refusal` 的 docstring `:2360-2363`：只有账本 = Core 在猜，只有分类 = 没人能事后据它行动。
- 载体：`the_refusal_was_classified_in_the_ledger:2339-2355` + `the_bridge_classified_the_refusal:2357`；`admit-100.json` 三条里就有这两条（另加 `no_world_was_joined`）。
- 反例：账本留 `FAILED` 但删 `reason` ⇒ 该函数返回 `NO_CLASSIFIED_REFUSAL`（`:2355`，不是跳过）；把 Bridge 那行日志抹掉而账本不动 ⇒ 第二条红。
- 阳性对照：`admit-100` 当前构建那份材料的形状。同样**本卡未跑**。

### 3.3 场景格 C（封禁）× 判据「分类…」—— 乙，缺词也缺分支

这一格今天**不可判**，且不可判的原因有两层，本卡分开放：

1. **词汇层**：`AdmissionFailureReason` 17 个成员里没有 ban（#2）⇒ 就算分类器想标，也没有可标的名。
2. **分支层**：`classifyDisconnect` 六支无 ban（#1），一句 vanilla「你被封禁」会走 `:448` 回落 `UNEXPECTED_DISCONNECT`。

因此契约这半句有两个**互斥**的可判形状，选择权在主控：

- 形状 (i)「封禁成为独立准入分类」：新增枚举值 + classifier 分支 + 孪生面（`bridge-1201/…:441-464`）同步 ⇒ oracle 与 3.1/3.2 同形（读那一对 `phase/reason`）。代价：动 `proto/**` 与两份 Java，且会重封全卷（memory 口径：构建变更使每一份被引 bundle 失效）。
- 形状 (ii)「只判不误判」：不加词，断言**否定式**读法 —— 一次封禁拒止**不得**被折进 `WHITELIST_REJECTED` / `AUTH_MODE_MISMATCH` / `PROTOCOL_MISMATCH` 三个具名拒绝类（允许落 `UNEXPECTED_DISCONNECT`，因为 `:420-424` 的注释就把「诚实的未分类」排在「错误的分类」之前）。代价：这等于承认契约里的「分类分别为…」对封禁只能答「未被误分类」，**这是契约语义的收窄**，须主控明写而不是由测试卡顺手决定。
- 具名拒答（本卡建议的登记形状，沿用 070 先例 `:4013-4018` 的常量清单写法）：`BAN_CLASSIFICATION_HAS_NO_NAMED_CATEGORY` —— 若主控选 (ii) 之前仍要 080 可登记，这一格恒答该具名缺口而不是计数空读数为绿。**先例可查**：`CONFLICT_CATEGORY_HAS_NO_RENAME_ENTRY`（`:4016`，函数 `:4056-4070` 直接 `return` 该常量）、`IDENTITY_REVISION_HAS_NO_CHANGE_CARRIER`（`:4017`，`:4073-4088`）、`IDENTITY_ROOT_MERGE_HAS_NO_SEALED_CARRIER`（`:4018`，`:4091-4107`）；`offline-070.json` 里四条断言的 fixture 形状就是「可判的写判据、缺载体的写具名缺口」，登记后整条按构造不能 PASS ⇒ 非 mandatory 登记不会被读成闭合。
- 反例（两形状共用的非恒真判据）：对**分类完美**的白名单 run，形状 (ii) 也判绿（它没被误分类）——所以必须补一条**判别式对照**：把同一行的 `reason` 改成 `…WHITELIST_REJECTED` 而场景声明为封禁 ⇒ 该条必须红。少了这条，形状 (ii) 是一句恒真话。
- 真跑前置：三格的场景都要在受控隔离服上把服务端形状摆出来（`server.properties` 的 `online-mode` / `white-list`，以及 banned 名单）。封禁那一格的摆法本卡不设计（属 `test-orchestrator/**` 与产品面），只登记它是前置。

### 3.4 第二格判据「不循环换身份」× 三场景 —— 载体在，读法只对一格存在

- oracle（设计）：以该场景那次拒止的 `position` 为锚，锚之后不得再出现 (a) 第二次 `AuthPolicyFrozen`、(b) 第二次 `SessionProcessStarted`、(c) 与拒止前不同的 `identity_candidate_id`。(a)(b) 已有实现（`:2747-2754`），(c) **没有**——它需要的字节全在（#5），只是没人这样读。
- 为什么不读 argv 补字段：`RunMaterial` 的密封输入键集恰为 `schema_version/kin_id/run_id/username/previous_run_id`（`tools/assert_case_evidence.py` 的 `asserter_inputs_bytes`，本轮按字节重读为 `:813-836`，键集未变），**不含 candidate id**；身份候选的可见出口是账本 `SessionIdentityCompared` 与 `SessionProcessStarted` 的行 ⇒ (c) 只能从账本读。
- 反例（设计，须红）：在 `/tmp` 内存副本账本里，于拒止行之后追加一条 `SessionProcessStarted`（同候选）⇒ 现有名 `CLIENT_STARTED_MORE_THAN_ONCE`；追加一条 `identity_candidate_id` 不同的 `SessionIdentityCompared` 而**不**加进程行 ⇒ 今天的读法**不会红**（这就是缺口本身，须具名 `IDENTITY_CHANGED_AFTER_REFUSAL` 才收得住）。
- 阳性对照（设计，不得红）：3.1/3.2 各自那份真实拒止材料 —— 一次冻结、一次进程、拒止后无行 ⇒ 判绿。
- 成本申报（重要，不申报就是偷偷重封）：把 `:2725-2755` 的锚点 reason 参数化（让它同时服务白名单/封禁场景）会改动**已注册函数字节** ⇒ `ADMIT-040` 的 `case_version`（当前构建 `daeb4ed5150734e7…2be61545`，`docs/p0-admit-five-run-2026-09-26.md:102`）漂移，那份当前构建 bundle 会掉回「别的构建」，要重封才能补上。替代形状是**新写一条只服务 080 的读法**（复用常量、不动既有函数，零摘要漂移，先例是 070 那笔「另写而非加宽」：`the_auth_mode_mismatch…` 的 docstring `:2705-2708` 就写明白名单那条不能顶替它）。本卡只把两条摆出来，选哪条属主控。

### 3.5 一张 fixture 还是三张：登记形状的选择权不在本卡

契约一行有三格场景，而**一次 run 只启动一个候选身份、也只摆一种服务端形状** —— 这个互斥在本仓库已被两次承认：`cases.py:336-339` 的注释（`OFFLINE-030` 因「一次运行只起一个候选」按身份列拆父案 + 两个非门禁子案，`OFFLINE-030-PRISM-PARITY-001` / `OFFLINE-030-ENUM-ALIGNED-001` 在 `:347-348`），以及 `docs/p0-validation-evidence-contract.md:189` 第 7 条对 `CORE-060` 的同类拆分（「一次运行只能注入一种故障，而 promotion 对一个 case id 采用 any-satisfying-bundle 语义」）。

于是 080 的登记有三条路，本卡**不选**：

- (1) 单 case id + 三条场景各自的 bundle：promotion 的 any-satisfying-bundle 语义下，任一 bundle 绿就点亮该行 ⇒ 三个场景里只跑了一个也会算过。这是**语义稀释**，与 `ADMIT-030/050` 那份「一个 case id 塞三个互斥场景」的旧账同形（`docs/p0-evidence-inventory-2026-09-26.md:164`）。
- (2) 父案持「 whichever 场景都成立」的那句 + 每场景一个非门禁子案：与 `OFFLINE-030` 完全同形，代价是新 case id 要动 `src/minekin_core/domain/cases.py`（`offline-090-100` 草稿为此明确写过「新 id 要动 cases.py，出本卡面」，`docs/development-execution-plan.md:254`）。
- (3) 只登记其中一格能诚实判的半句、其余按具名缺口登记（`offline-070.json` 的形状）。

三条都需要主控先回答 §3.3 的分类问题（封禁有没有词）——那决定了第几格可判。

## 4. 缺载体条款的最小反例 / 验收（供未来 fixture）

- 封禁格：要么 (i) 加词加分支（含孪生面），要么 (ii) 契约明写收窄为「不误判」。验收 = §3.3 的判别式对照（把封禁行改成白名单行必须红），缺它这条判据是恒真的。
- 「不循环换身份」对第 (c) 项：验收 = 一条只加「不同候选的身份比对行」、不加进程行的注入必须红；同 run 的拒止前身份保持不变必须绿。
- 白名单 / 封禁两格的「一次策略一次进程」：验收 = 锚点之后多一条 `SessionProcessStarted` ⇒ 红，多一条 `AuthPolicyFrozen` ⇒ 红，无锚点 ⇒ 具名拒答而非绿。
- 以上都不是「写测试」能闭合的：前两条等词汇/契约决定，后两条等登记函数（M 独占面）。定义断言不等于闭合。

## 5. 不属于本卡

- 不替 `OFFLINE-060/070/090/100`、`ADMIT-010/020/030/050/090/120`、`CORE-080`、`NAV-EXP-010` 打补丁，也不把它们的缺口挪进本卡；`HOST*` / `HOSTCTL*` / `HOSTCOMMIT*` 整族属 `host-integrated` deferred，本卡不判。
- 不登记、不翻 `mandatory`、不动 registry / 任何门 / 门载荷：因此本卡**不产生**门载荷前后读数（不是遗漏，是没动）。
- 不实施 `tools/**`、`src/**`、`bridge*/**`、`test-orchestrator/**` 的任何改动，包括 §3.4 那条「只服务 080 的新读法」——那属 M 的登记卡，且必须先有 §3.5 的拆分决定。
- 不开 `NEXT`：`GATEWAY-READONLY-PROJECTION-001` / `DASHBOARD-GATEWAY-WIRING-001`（上一张卡 §6.2/§6.3）与本卡的下游一律是 `QUEUED`。

## 6. 复现命令、四态声明、未验证清单

命令（全部只在仓库字节上跑，base `efe8c66`；`.tmp/m-r80/carrier_census.py` 未入库，故每条都给仓库内等价式）：

- 契约与 registry：`sed -n '154p;158p' docs/p0-offline-session-compatibility-contract.md`；`sed -n '341,356p' src/minekin_core/domain/cases.py`。
- fixture 底数：`ls tests/fixtures/cases | grep '^offline'` ⇒ 11 份、无 `offline-080.json`；`ls tests/fixtures/cases | wc -l` ⇒ 53。
- 分类器与 ban 缺席：`sed -n '426,449p' bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java`（孪生面 `sed -n '441,464p' bridge-1201/…`）；`grep -niE "(^|[^a-z])ban(ned|ning)?" bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java` ⇒ 无命中（脚本量得 `ban_in_file = 0`，两面对称）。
- 枚举词汇表：`awk '/enum AdmissionFailureReason/,/^}/' proto/minekin/v1/observation.proto` ⇒ 17 成员（`UNSPECIFIED=0` + 16 具名，末位 `CONNECTION_REFUSED = 16`），无 ban 名。
- 判官在册性：`grep -n "def the_refusal_was_classified_in_the_ledger\|def the_bridge_classified_the_refusal\|def the_auth_mode_mismatch_was_classified_in_the_ledger\|def the_refusal_left_the_run_on_one_policy_and_one_process" tools/assert_case_evidence.py` ⇒ `:2339 / :2357 / :2702 / :2725`；`sed -n '2725,2755p'` 读锚点硬编码与三条红名。
- 无换身份回路：`grep -rn "for candidate\|next_candidate\|rotate\|retry" src/minekin_core/adapters/launcher src/minekin_core/cli`（命中逐条归类，见 §2 #6）。
- 具名缺口先例：`sed -n '4013,4018p;4056,4107p' tools/assert_case_evidence.py`；`cat tests/fixtures/cases/offline-070.json`。

四态声明：**已合主干（本文件与两处队列/交接文档登记）／ 分支上无在途实现（本卡零代码改动）／ 真实封证未新增（全程未挂卷；规范卷 sealed bundle 仍只 1 份：`5086ee42…64f6` / run `a224f6c3…`，出处 [`docs/validation/v1201-lan-joiner-control-seal-2026-09-28.md`](validation/v1201-lan-joiner-control-seal-2026-09-28.md)）／ OFFLINE-080 的运行时判法尚未量。**

本卡未测（明确列出）：

1. §3 全部反例与阳性对照的**运行判定** —— 无 080 fixture、无 080 bundle；兄弟格（3.1/3.2）的绿只由 `admit-040/100` 的既有登记担保，本卡未重跑。
2. 封禁场景在受控隔离服上的摆法与其服务端文案 —— 未测，且 §3.3 的两形状任一被选中前不设计。
3. `identity_candidate_id` 在真实拒止 run 的账本里是否总有值（`SessionIdentityCompared` 只在身份比对发生时写）—— 未测，影响 §3.4 (c) 的可判性。
4. 门载荷前后差 —— 本卡零登记 ⇒ 预期一字不动；不主张具体 sha256，登记时由那张卡自己量。
5. 「三格场景拆几张 case」的后果量化（(2) 路线要动 `cases.py` 因而移门载荷）—— 本卡未测。

## 7. 下一格欠账（交回队列，不在本卡做）

- §3.5 的拆分选择 + §3.3 的封禁分类选择：两问都在主控手上，答案决定 080 能否登记、登记成几条。
- §3.4 的两条形成本比较（参数化既有函数 vs 新写一条）：择一后才有登记卡。
- `ADMIT-030/050` 的同类拆分问题与本卡 §3.5 是**同一族**（一个 case id 塞互斥场景）：主控可考虑一次裁决、两卡共享结论，但不得由测试卡先做决定。
