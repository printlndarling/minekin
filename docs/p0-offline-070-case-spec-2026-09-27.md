# P0-OFFLINE-070-CASE-SPEC-001 — OFFLINE-070 案例定义 / 反例草稿

- 卡片：`P0-OFFLINE-070-CASE-SPEC-001`（仅定义 `OFFLINE-070` 一条；090/100 在各自卡与各自草稿里，见第 5 节）。
- 制作位置：worktree `../minekin-wt-o070`，分支 `codex/minekin-offline-070`，base `f5a7fdae65750cb76a3ddaa44709d4e0e1fdb541`（本会话核对：`git ls-remote origin refs/heads/main` 报该 SHA；`git rev-parse HEAD` 同为该 SHA；建文件前 `git status --porcelain` 为空）。
- 状态：**给主控复核 / cherry-pick 的草稿。本卡全程不登记、不封存、不改 registry；卷 `minekin-runner-data` 只以 `:ro` 挂载读取。** `OFFLINE-070` 判据状态一律记为「未闭合 / 缺载体」，全文**不出现**任何把 070 记作通过的结论。
- 引用纪律：下面每一处代码行号都是本会话在 base 字节上（或明确标注的 `:ro` 卷读数上）真实读到的；凡未在本会话重跑的读法都标「本卡未测」，推理得到的判断单独标「（推断）」。不复述任何先前会话的原话作为证据。
- 放置：本草稿落在 `docs/p0-offline-070-case-spec-2026-09-27.md`，沿用本仓库既有的「逐卡记录放 `docs/`」约定（同批格式样板：`docs/p0-offline-090-100-case-spec-2026-09-27.md`，本卡只借其形，不借其判）。本文件是本卡唯一新增文件。

## 1. 受测契约文本（逐字 + 仓库字节出处）

契约行（`docs/p0-offline-session-compatibility-contract.md:153`）：

> `| OFFLINE-070 | 同名双登录、改名、大小写变化 | 冲突/新revision分类正确，不合并人格根 |`

registry 在册状态（`src/minekin_core/domain/cases.py:352`，处在 `_phase_cases(_OFFLINE, ValidationClass.RUNTIME_REQUIRED, "W30", …)` 块 `cases.py:340-356` 内，id 逐行 `:344-355`）：`OFFLINE-070` 已是 `W30` / `p0-core` 的 `RUNTIME_REQUIRED` 行——所以登记只把门禁读数从「缺席」挪到「已登记」，本身闭合不了任何东西。

混合载体口径（`docs/p0-evidence-inventory-2026-09-26.md:169`）：

> `| `OFFLINE-070` | 同契约 `:153` | **混合**：「同名冲突分类」有载体（`ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN`，`bridge/.../ClientAdmissionController.java:435`）→ 甲；「新 revision」与「人格根不合并」**无载体**——`identity_revision` 只在 `cli/init.py:77` 写成常量 1，全仓库无自增/更新路径（schema 只约束 `>= 1`）→ 乙 | 本卡复核 |`

卡片行（`docs/development-execution-plan.md:248`，M 主干文档，本卡只引不改）把 070 记为混合载体行、E lane 单独一张、`卷上零 bundle`、「一律不得出现把 070 记作通过的结论」，与 `docs/qoder-execution-handoff.md:467` 的「单独排卡、不与 090/100 混单」一致。

隔离服约束（同一契约 `docs/p0-offline-session-compatibility-contract.md:158`，逐字）：

> 所有case只在运行者控制的隔离服执行。不得用第三方公网offline服务器做身份探测。

本卡不连任何远端 / 公网服务器；下文出现的「受控隔离服」一律匿名，不带任何地址端口。

## 2. 载体底数（本会话 `:ro` 实测，非假设）

bundle 布局为 `/data/kin/<kin_id>/run/evidence/<run_id>/manifest.json`（实测发现，见 §6 命令 A）。在该布局下整卷计数：

| 量 | 实测读数 | 复现 |
|---|---|---|
| 卷上 bundle（含 `manifest.json` 的 run 目录） | **107** | §6 命令 C |
| `evidence-attempts.sqlite3` 的 `attempts` 表行数 | **71** | §6 命令 B |
| `case_id` 前缀为 `OFFLINE-070` 的 bundle | **0** | §6 命令 B/C |
| OFFLINE 系在册 bundle 分布 | OFFLINE-010:2、020:2、030:1、030-ENUM-ALIGNED-001:2、030-PRISM-PARITY-001:2 | §6 命令 B |

结论：`OFFLINE-070` 卷上**零 bundle**（107 份里一份都不是），与卡片底数（第八轮 + B1-b-0）同读。**零 bundle ⇒ 070 记为「未闭合 / 缺载体」**——两半句里，即便「同名冲突分类」那半有码级载体，也没有任何运行材料可判；「新 revision / 人格根」那半连码级运行载体都缺。

## 3. 逐句断言集（两半都拆；每条：载体 / 今天是否存在（实测） / 反例 / 阳性对照）

命名仅为**设计文本**：本卡不写断言函数、不登记 `IMPLEMENTATIONS`、不加 fixture。asserter 与 `IMPLEMENTATIONS`、`manifest.sha256` 登记是 M 独占面（`docs/qoder-execution-handoff.md:467`）。断言名一律按契约判据列原句派生，不加填充式断言。

### 3.1 半句甲 ——「同名冲突分类正确」

判据读的是**账本分类**：Bridge 把服务端那句话归类为某个具名 `AdmissionFailureReason`，Core 把「相位 + 分类」一起写进账本事件 `SessionInterrupted`（常量名 `SESSION_INTERRUPTED = "SessionInterrupted"`，`tools/assert_case_evidence.py:102`）。这一读法在兄弟分类上已被现成判官钉死（白名单 `tools/assert_case_evidence.py:2237-2252` 的 `the_refusal_was_classified_in_the_ledger`，认证 `…:2600` 起的 auth_mode 读法），因此甲半句属「事实有载体、只差把它写成 070 的断言」。

**① 同名双登录 ⇒ 归类为 `ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN`**

- 证据载体（具名）：
  - proto 枚举 `ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN = 8`（`proto/minekin/v1/observation.proto:33`；枚举块 `observation.proto:24-40` 为 `UNSPECIFIED = 0` 加 15 个具名分类，实测完整）。
  - Bridge 归类码：`ClientAdmissionController.classifyDisconnect` 把 `"already connected"` / `"logged in from another location"` 映射到该枚举（`bridge/src/main/java/org/minekin/bridge/runtime/ClientAdmissionController.java:434-435`，函数体 `:426-448`）。
  - Java 侧阳性对照测试：`aServerReasonBecomesTheStableCategoryForIt` 用真实 vanilla 句 `"You are already connected to this server!"` 断言得到 `…DUPLICATE_LOGIN`（`bridge/src/test/java/org/minekin/bridge/runtime/ClientAdmissionControllerTest.java:267-274`；注释 `:265-266` 言明该句「在受控域里量得、非此处臆造」）。
- 今天是否存在（实测）：
  - 载体在（枚举 + 归类码 + Java 单测三处均实读到）。
  - **但** `tools/assert_case_evidence.py` 的已登记断言（`ASSERTIONS` 块 `:3446`，实测 81 条命名）里**没有** DUPLICATE_LOGIN 专属读法——只有 `WHITELIST_REJECTED`（`:185`）与 `AUTH_MODE_MISMATCH`（`:194`）两条 ledger 读法；`server_profile_revision` 那组（`:2555-2596`、`:2721-2731`）读的是**服务器 profile 修订**，与 `identity_revision` 无关，不可混用。
  - **且** 卷上 0 份 OFFLINE-070 bundle（§2），因此没有任何一份 `SessionInterrupted{phase:FAILED, reason:…DUPLICATE_LOGIN}` 的真字节可判。⇒ **本条未闭合**。
- 反例（注入形状，须把判定打红）：设计读法 `the_conflict_was_classified_as_duplicate_login`（在一份 `/tmp` 内存副本的账本上跑，绝不碰卷）——
  - 把某条 `SessionInterrupted` 的 `reason` 伪造成 `…AUTH_MODE_MISMATCH`（或 `…UNEXPECTED_DISCONNECT`）冒充重名 ⇒ 该条判红 `NO_DUPLICATE_LOGIN_CLASSIFICATION`；
  - 或整条 `SessionInterrupted` 缺 `reason` 字段 ⇒ 判红，绝不回落到「沉默即通过」（对齐 `the_refusal_was_classified_in_the_ledger` 对空名单不作通过的写法 `tools/assert_case_evidence.py:2246-2252`）。
- 阳性对照（不得红）：把真字节里那条 `reason` 原样保留为 `…DUPLICATE_LOGIN`、`phase` 为 `FAILED` ⇒ 判绿。**本会话未跑**（无 070 bundle，无 DUPLICATE 判官；见 §6 未测清单），仅由 Java 单测 `:267-274` 与 ledger 读法形状担保。

**② 改名 / 大小写变化的归因（与 ① 可区分，且不误判）**

- 事实基线（实读字节）：offline UUID 是对 `("OfflinePlayer:" + name)` 的**大小写敏感** MD5 v3（`src/minekin_core/domain/offline_identity.py:39-43`；用户名规则 `[A-Za-z0-9_]{3,16}` 允许大小写并存 `:36`）⇒ 改名或仅变大小写会导出**不同**的 UUID。
- 载体缺口（记为 gap，不臆造）：`AdmissionFailureReason` 枚举里**没有**「改名」或「大小写变化」这一独立具名分类（实测枚举 `observation.proto:24-40` 全部 15 具名分类无此类）；vanilla 那句 `"logged in from another location"` 与重名同落到 `…DUPLICATE_LOGIN`（`ClientAdmissionController.java:434`）。故「改名/大小写」要**与重名区分**这半句，今天的分类词汇表承载不下——属**缺具名分类**，登记为 gap，是否新增该分类是主控决策（`docs/development-execution-plan.md:243` 把 070 半句列入 `BLOCKED_DECISION`）。
- 反例（设计，须红）：若一份材料把一句大小写变化的断开直接归为 `…DUPLICATE_LOGIN`，而 070 的判据要求「重名 ≠ 改名」二者可分，则该归类应判红 `CONFLICT_CATEGORY_AMBIGUOUS`。（本卡未测：既无该分类、也无 bundle。）
- 阳性对照（设计，不得红）：确为同一 name 的二次登录，仍归 `…DUPLICATE_LOGIN` 判绿——即 070 的判据不得把普通重名误伤。

### 3.2 半句乙 ——「新 revision 分类正确，不合并人格根」

**③ 「新 revision」分类正确**

- 今天载体（实测为**无**）：`identity_revision` 全仓库只在 init 写成常量 1（`src/minekin_core/cli/init.py:23` `INITIAL_IDENTITY_REVISION = 1`，写于 `:76-77`），数据模型仅在 `__post_init__` 校验 `>= 1`（`src/minekin_core/domain/offline_identity.py:62, 69-70`）、序列化读回（`…:92`、`as_dict` `…` 无关自增）；持久层 `identity_store.py` 只有 INSERT（`:47-60`）与 SELECT（`:19`、`:64-69`）；schema 只有 `CHECK (identity_revision >= 1)`（`src/minekin_core/adapters/sqlite/schema.sql:93`、`…/migrations/0002_identity_root.sql:14`）。
  - 实测证据：`grep -rniE "set +identity_revision|UPDATE.*identity_revision|identity_revision *[+*]=|identity_revision +1" src` **无命中（退出码 1）**，见 §6 命令 D。⇒ 全仓库**无 `identity_revision` 自增 / 更新 / 变更事件路径**（此为 inventory `:169` 的复核，本会话独立重跑确认）。
- 判定：契约要「新 revision」，即改名/大小写后应**升一次 revision** 且这一升变是**可归因、可被 bundle 承载**的事件。今天**无任何载体**承载 revision 变更事件——既无码级自增路径，也无账本列，更无 070 bundle。⇒ 本条为**缺载体（乙）**，记 gap；「`identity_revision` 是否应设计一个变更事件」是产品决策（`docs/development-execution-plan.md:243`、`:248`），本卡**不自造断言、不改候选集**。
- 未来 fixture 所需的最小反例 / 验收（设计，本卡未测）：一份能表达 revision 迁移的事件，其验收应含——
  - 反例 a：改名 / 大小写变化之后 `identity_revision` 仍等于旧值 ⇒ 断言 `the_conflict_opened_a_new_revision` 判红 `REVISION_NOT_ADVANCED`；
  - 反例 b：注入一次**回退**（新值 < 旧值）或 < 1 的 revision ⇒ 被模型/ schema 拒（可复用 `offline_identity.py:69-70` 的 `>= 1` 与 `schema.sql:93` 的 CHECK 作为既有钉），断言判红；
  - 阳性对照：改名产生 `revision = 旧+1` 且 `kin_id` 不变 ⇒ 判绿（此为「新 revision 但同一人格根」的正面形状，本卡无载体、**未测**）。

**④ 「不合并人格根」**

- 今天载体（**部分，且仅码级**）：人格根「不重建 / 不第二条」的守卫是有的——`create_identity_root` 在已有一行时直接拒（`src/minekin_core/adapters/sqlite/identity_store.py:45-46`，注释「a Kin is not created twice」）、init 对已存在库拒重跑（`src/minekin_core/cli/init.py:70-73`「Not idempotent on purpose」）、`read_identity_root` 永不创建（`identity_store.py:64-69`）；`tests/unit/test_restart_semantics.py:86` 读到重启前后 `identity_revision == 1`。
- 判定：这些守卫防的是「静默新建第二条根」，**不等于**契约「不合并人格根」要求的、在**改名 / 大小写 / 重名**这类运行场景下可被 bundle 观测到的「两根未被并成一根」的事件级证据；加上 0 份 070 bundle（§2）⇒ 作为运行判据本条**未闭合**。
- 反例（设计，本卡未跑）：若把 `identity_store.py:45-46` 的「已有一行即拒」删掉，第二次 `create_identity_root` 会静默改写根指向 ⇒ 一份声称「合并/替换了人格根」的材料应判红 `IDENTITY_ROOT_MERGED`（此反例只在 `/tmp` 标签副本上验，绝不碰卷）。
- 阳性对照：当前守卫下第二次 create 抛错（`identity_store.py:45-46`）、read 不建（`:64-69`）⇒ 判绿；仍属设计层，**本卡未测**。

## 4. 缺载体条款的最小反例 / 验收（供未来 fixture）

- ②「改名/大小写」缺具名分类：未来要么在 `AdmissionFailureReason`（`observation.proto:24-40`）新增可与 `…DUPLICATE_LOGIN` 区分的分类，要么在 070 判据里以「同一 name 的二次登录 vs 名字本身变化」做二级区分；二者都是主控决策，本卡不实现。验收：一份能把「大小写变化的断开」与「同名的二次登录」喂进同一判据、要求前不红后不绿混淆的材料。
- ③「新 revision」缺载体：见 §3.2③ 的最小反例 a/b + 阳性对照——前提是产品先设计一条 `identity_revision` 变更事件并可被封进 bundle。当前该事件不存在（§6 命令 D 实测），故本卡只能把 070 记为「未闭合 / 缺载体」，不能记通过。
- ④「不合并人格根」缺运行材料：需一份真实经过改名/大小写/重名的受控运行、把根未并的证据封进 bundle。定义断言不等于闭合。

## 5. 不属于本卡

- 本卡**只定义 `OFFLINE-070`**。第 3.2 节里 `identity_revision` / 人格根那半句的缺口、以及任何「为让 070 可读而动的产品改动」，都**不得挪去给 `OFFLINE-090` / `OFFLINE-100` 打补丁**；反之，090（日志/崩溃/Dashboard 脱敏）与 100（重启与 A→B→A 世界切换、`kin_id` 连续、外部身份/world context 不串线）的修法也**不得回流来填 070 的 revision / 人格根缺口**。
- 090/100 各有自己的卡与自己的草稿（`docs/p0-offline-090-100-case-spec-2026-09-27.md`，仅存在于其分支，非 main），本文件不复述其判、不改其文。
- 登记与否、`mandatory` 翻转、门禁推进、asserter + `IMPLEMENTATIONS` + `manifest.sha256` 落地，均为 M 独占面（`docs/qoder-execution-handoff.md:467`）；本卡不预约任何登记为闭合。

## 6. 复现命令与实测读数 · 四态声明 · 未验证清单

命令（均在 base `f5a7fda` 或明确标注的 `:ro` 卷上跑；`minekin-runner:local` = `b67a4d917306`，`minekin-runner-data` 只 `:ro`）：

- 命令 A（布局发现）：容器内 `find /data -maxdepth 6 -name manifest.json` ⇒ 命中 `/data/kin/<kin>/run/evidence/<run>/manifest.json` 形态。
- 命令 B（case 普查 + attempts）：容器内 python 读 `/data/kin/**/manifest.json` 的 `case_id` 计数，并 `SELECT count(*) FROM attempts`（`/data/evidence-attempts.sqlite3`，`mode=ro`）⇒ OFFLINE 系计数见 §2 表，`attempts = 71`，`OFFLINE-070 = 0`。
- 命令 C（全卷 bundle）：`glob("/data/**/manifest.json", recursive=True)` 去重 ⇒ **107 份 / 107 个 bundle 目录**；其中 `case_id` 以 `OFFLINE-07` 开头者为 **0**（命令 B/C 互证 94 是漏了非 `kin` 根的 13 份，107 为全量）。
- 命令 D（无自增路径）：`grep -rniE "set +identity_revision|UPDATE.*identity_revision|identity_revision *[+*]=|identity_revision +1" src` ⇒ **无命中，退出码 1**；`grep -rn "identity_revision" src --include=*.py` 仅出 `init.py:23/77/93`、`offline_identity.py:62/69/70/92`、`identity_store.py:19/49/55/79`（读 + init 写常量），无 UPDATE。
- 命令 E（枚举/归类/判官在册性）：读 `observation.proto:24-40`（15 具名 + `UNSPECIFIED`，`…DUPLICATE_LOGIN = 8`）、`ClientAdmissionController.java:426-448`、`ClientAdmissionControllerTest.java:267-274`、`tools/assert_case_evidence.py:102/185/194/2237-2252/2600/3446` ⇒ ASSERTIONS 实测 81 条命名，无 DUPLICATE_LOGIN 专属读法。

四态声明：**未合并 main / 仅在本分支 `codex/minekin-offline-070` / 无真封存证据新增（全程 `:ro`，未建 attempt、未封 bundle）/ 断言运行读法尚未量。**

本卡未测（明确列出）：

1. §3 所有断言名的**运行判定**（反例注入 / 阳性对照）——既无 OFFLINE-070 bundle，也无对应 Python 判官登记；**本卡未测**。
2. `identity_revision` 变更事件的承载——产品事实**无载体**（命令 D 实测），要它先存在是主控决策（`docs/development-execution-plan.md:243/248`），**本卡未测**。
3. 「改名 / 大小写」与「重名」的可区分分类——枚举无独立分类（命令 E 实测），**本卡未测**。
4. 门禁载荷前后差（登记后 `requirement.absent → non_mandatory` 的位移）——登记是 M 面，**M 侧未复量**。
5. 任何受控隔离服上的真跑真封——超出本卡（卷写），**本卡未测**。
