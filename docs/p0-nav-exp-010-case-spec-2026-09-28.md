# `NAV-EXP-010` 的 oracle 与载体先行设计（2026-09-28）

- **卡片**：`P0-NAV-EXP-010-CASE-SPEC-001`
- **授权来源**：`docs/v1201-lan-control-next-2026-09-27.md` §3 第二类独立工作——该族第六张、也是**收尾一张** doc-only 设计卡。§3 列出的非 HOST 行（`ADMIT-010/020/030/050/090/120`、`CORE-080`、`OFFLINE-060`、`NAV-EXP-010`，见该文档 `:1840`）到本卡为止全部排过一张。
- **owner**：M。**allowed_paths**：本文件 + 三处主干登记（v1201 新小节、handoff 新轮次、执行计划表一行）。**本轮零代码改动**。
- **禁止**：不挂规范卷、不起 JVM、不读未跟踪的测试服地址文件、不连用户远程服、不动 `mandatory`/registry/判据集合、不新增 `NEXT`、不改 lane 材料一字节。
- **base 现场**：`535e033132576f4d5edf2087c06608d205f50e8c`（本轮开工前 `git ls-remote origin refs/heads/main` 回读值 = 本地 `main`）。
- **引用纪律**：下列行号一律按 base 字节本轮重测；只读脚本与原始输出留在 `.tmp/m-r85/`。
- **口径**：全文**不记** `NAV-EXP-010` 的任何通过结论，也不替它写断言。本轮取到的三笔 CI 步骤级读数（`d568048…`、`d18a199…`、`535e033…`）逐条列在 §5，其中最后一笔只是 `in_progress`，不作绿声明。

## 1. 契约原文与登记底数

- `docs/p0-validation-evidence-contract.md:195`（第 13 项，逐字）：`NAV-EXP-010`：只在 core tested 后运行，核 Baritone mixin、输入仲裁、取消尾部和隐藏真值越界；单独给 `candidate/tested/quarantine`。

| 读数 | 位置 | 值 |
| --- | --- | --- |
| 注册 | `src/minekin_core/domain/cases.py:306` | `*_surface_cases(_VALIDATION, ValidationClass.RUNTIME_REQUIRED, "p0-nav-exp", "NAV-EXP-010")` |
| 它是**面**不是阶段 | 同文件 `:39-46` | `W00`–`W80` 是核心切片的阶段；`p0-core`/`p0-nav-exp`/`host-integrated` 是契约**独立分级**的三个面，注释具名「一个 host 结果不得借去宣称 core 过了，反之亦然」 |
| `W80` 故意不在冻结门禁里 | 同文件 `:197-199`、`REQUIRED_GATES:200-212` | 「把 NAV 绑到阶段号会把一个实验的证据放到两个名字下」 |
| case 词汇表 | 同文件 `:36`、`:53-66` | `^[A-Z][A-Z0-9-]+-[0-9]{3}$`；`WORK_PACKAGES` 封闭 12 名 |
| fixture | `tests/fixtures/cases` | 目录列表按 `nav` 过滤 ⇒ **无输出（rc=1）**，即无 `nav-exp-010.json` |
| 该 gate 的 required case 数 | `tests/unit/test_report_cases.py:219-220` | `by_gate["p0-nav-exp"]["required"] == 1` 且 `satisfied is False`（**合成 registry 上的单测**，不是卷面读数） |
| 出现 `NAV-EXP-010` 的其它代码位 | `tests/unit/test_case_registry.py:896`、`tests/unit/test_report_promotion.py:398`、`:590` | 都在判「未登记时是否点名」与「总体报告把它列为 blocking case」，同样不是活体读数 |

## 2. 四个检查项的载体底数（本轮新量）

| 契约检查项 | 仓库字节里的现状 | 位置 |
| --- | --- | --- |
| Baritone mixin | `src/`、`tools/`、`tests/`、`test-orchestrator/` 内 **0 命中**（本轮亲 grep）；只有 4 份文档提到它：`docs/p0-bridge-bootstrap-contract.md`、`docs/p0-launch-plan-contract.md`、`docs/p0-prototype-execution-plan.md`、`docs/p0-validation-evidence-contract.md` | 缺口具名 `BARITONE_MIXIN_HAS_NO_BYTES_IN_REPO` |
| 输入仲裁 | 有相邻机制：`domain/input_control.py` 存在，租约与拒绝在账本里是具名事件（契约 `:188` 写出 `InputLeaseGranted` 与 `InputRefused{phase: …, refusals: [NOT_PLAYABLE]}`），`CORE-050` 一族的判法已经在读这两类行 | 可复用，但**没有** `arbitrat*` 具名（`events.py` 与 `input_control.py` 本轮按 Cancel、Arbitrat、arbitrat 三串 grep ⇒ 0 命中） |
| 取消尾部 | 同上：没有 `Cancel` 这一具名事件；`domain/lease_watchdog.py`、`domain/control_watchdog.py` 是时限侧，不是「取消之后那一段还剩什么」 | 缺口具名 `CANCELLATION_TAIL_HAS_NO_NAMED_EVENT` |
| 隐藏真值越界 | **载体最厚的一项**：`domain/perception.py` 有 `EntityReason:40`、`SnapshotReason:50`、`IntegrityViolation:60`、`VisibleWorld:120`、`EntityRejection:114`、`SnapshotAdmission:144` —— 即「哪些实体被拒出可见世界、快照按什么理由准入」今天已被结构化记录 | 可直接作为 oracle 的观测面 |

## 3. 可判形状与缺口

### 3.1 三档分级 `candidate/tested/quarantine`：三档里只有一档有载体

- `tested` 这一档今天可由晋级判定回答：`cases.py:89-107` 的 `PromotionBlock` 文档句即「为什么一个 work package 还不能被称作 tested」，`PromotionVerdict:832` 给出 `promotable` 与 `blocks`；其中 `REQUIRED_CASE_NOT_REGISTERED`（`:98-102`）正是「要求的 case 在 registry 里根本没有条目」这一格的具名拒止——本卡不据此报出 `p0-nav-exp` 的实际 verdict（要读 registry ⇒ 需挂卷 ⇒ 本轮 0 次）。
- `candidate` 与 `quarantine` 两档在晋级词表里**没有名字**：仓库里的 `quarantine` 字节属于另一条轴——`adapters/launcher/artifacts.py:133-134,:169-170` 是产物库的隔离目录，`domain/version_resolution.py:44,:768-775` 的 `BundleStatus.QUARANTINED` 说的是取回来的 mod 包校验不过。缺口具名 `NAV_TRI_GRADE_HAS_ONLY_TESTED`。
- 于是本条不是「判据缺失」，而是**分级轴缺失**：写一条只判 `tested` 的断言会静默把契约的三档读成一档。本卡不替它选（§4 第 1 格）。

### 3.2 「只在 core tested 后运行」这句话今天没有承载者

- 代码刻意让 `p0-nav-exp` 独立分级（`:39-46`、`:197-199`），因此**不存在**一条把 core 晋级状态读进 NAV 判定的路径。后果可判：一份先于 core tested 封出的 NAV bundle，对着 `p0-nav-exp` 单独复算时**照样可能 `promotable=true`**，契约的前置只写在文档里。
- 三种可选承载点（本卡不选，只列形状）：
  1. 封存侧硬门——`tools/seal_run_evidence.py` 在 case id 为 `NAV-EXP-010` 时要求读到 core 的 tested 证据，缺则具名拒封（成本：封证生产端多一条轴）；
  2. 判定侧——`evaluate_case_promotion` 对 `p0-nav-exp` 附加一条前置 block（成本：与 `:197-199`「一个实验不放在两个名字下」的设计意图相冲，需要主控裁是否推翻）；
  3. 保持文档级前置，但把「前置未满足就封出」写成一条**可复判的拒止**（例如 run document 里记 `core_tested_at_seal`，验收器读它并如实拒），代价是要往载荷加一个新字段——与 `P0-ADMIT-090-120-CASE-SPEC-001` §4 第 3 格同一条警告：**加判据而不重封，等于宣布旧 run 从未被这条判据看过**。

### 3.3 恒真风险与反例（若将来只做「隐藏真值越界」这一格）

- 恒真形状：canary 由用例自己写进世界、再由同一个扫描器扫可见世界 ⇒ 「没扫到」是构造保证。阳性对照要照 `auth_field_bodies_are_not_exposed_in_bundle_carriers`（`tools/assert_case_evidence.py:3786-3813`）那三条经验：无可扫载体不等于干净（`:3805-3808`）、读不到的面要具名成缺口而不是计入 `0`（`:3816-3832`）、命中要报到哪个载体哪一处（`:3809-3812`）。
- 反例两格：（a）canary 被塞进 `VisibleWorld` 的实体名单 ⇒ 该 case 必须变红；（b）`EntityRejection` 名单为空且快照拒绝原因为空 ⇒ 应拒判为「没有观测」，而不是「什么都没越界」。
- 正对照一格：Kin 视野外一处具名实体被 `EntityReason` 拒出 ⇒ 断言「越界=0」的同时，必须能指出**拒出发生在哪一行**，否则「0」与「没读」不可分。

## 4. 交主控决定的格子（本卡不选）

1. 三档分级是否补轴（`candidate`/`quarantine` 进晋级词表），还是把契约 `:195` 末句改写成「`tested` 由晋级判定回答，另两档由产物隔离回答」——后者不改代码，但要删掉一句话的承诺。
2. `NAV-EXP-010` 是否**拆案**：`Baritone mixin` 一格在产品里没有字节，与本卡其余三格不同性质（那三格有相邻机制可读）。按 `CORE-060`/`OFFLINE-030` 的先例，一次运行只证一件事时应拆独立 case id。
3. 「只在 core tested 后运行」选 §3.2 三种承载点里的哪一种，或者明确保留为文档级前置并接受其不可判。
4. `取消尾部` 是否需要先造具名事件（`CANCELLATION_TAIL_HAS_NO_NAMED_EVENT`）——那是产品新增事实，不是验收器能补出来的。

## 5. 不回流的口径、CI 补记与本轮附带读数

- 真实封证仍为 **1**（bundle `5086ee42…64f6` / run `a224f6c3…`，出处 `docs/validation/v1201-lan-joiner-control-seal-2026-09-28.md:6-7`）；本卡不新增、不引用私有卷读数。
- `mandatory`、registry、判据集合、门载荷本轮**零位移**；门载荷未取卷复量（无位移预期，也未测）。
- **开工前取回上一笔**：`d568048…` 的 push run `36378797135` = `completed`/`success`，`protocol` 10 步 / `bridge-static` 9 步 / `python` 18 步，三 job `NON_SUCCESS_STEPS=[]`、`JOB_CONCLUSION_BREAKS=[]`（日志 `.tmp/m-r84/ci-d568048.log`）⇒ 第八十三轮那笔 CI 欠账与其后续一起闭合。日志正文仍不可得，故本节不写任何「CI 说了什么话」的结论。
- **同轮补记（清第八十三轮的欠账）**：`d18a199…` 的 push run `36378464126` = `completed`/`success`，`bridge-static` 9 / `python` 18 / `protocol` 10 步，三 job `NON_SUCCESS_STEPS=[]`、`JOB_CONCLUSION_BREAKS=[]`（日志 `.tmp/m-r84/ci-d18a199.log`）⇒ `P0-ADMIT-090-120-CASE-SPEC-001` §5 留下的「`d18a199` 自身的 run 仍未取」至此闭合；那两笔都是 doc-only 提交，步骤级全绿不改变任何封证或位移计数。
- **最后一笔如实登记**：`535e033…`（第八十四轮落盘笔）的 run `36379470293` 本轮取到的是 **`in_progress`**（`conclusion=None`，日志 `.tmp/m-r84/ci-535e033.log`）⇒ 本节不据此作任何绿声明，留下一轮复取。
- **第八十六轮复取（本节第 5 条最后一格的结局）**：`535e033…` 的 run `36379470293` 已是 `completed`/`success`（`protocol` 10 / `bridge-static` 9 / `python` 18 步，`NON_SUCCESS_STEPS=[]`、`JOB_CONCLUSION_BREAKS=[]`，日志 `.tmp/m-r86/ci-535e033.log`），本卡落盘笔 `0d080c0…` 自身的 run `36379827665` 也是 `completed`/`success`（日志 `.tmp/m-r86/ci-0d080c0.log`）⇒ 上面那句 `in_progress` 与「留下一轮复取」保留为当时读数，本行只补结局，不作任何封证或位移结论。

## 6. 复现命令（全部只读，工作树根目录）

```bash
A: sed -n '195p' docs/p0-validation-evidence-contract.md
B: sed -n '36,66p;193,212p;300,310p' src/minekin_core/domain/cases.py
C: ls tests/fixtures/cases | grep -i nav ; echo rc=$?          # rc=1
D: grep -rn "Baritone\|baritone" src tools tests test-orchestrator --include=* | head
E: grep -rln "Baritone" docs/p0-*.md                            # 4 份文档
F: sed -n '40,60p;114,145p' src/minekin_core/domain/perception.py
G: grep -rn "Cancel\|Arbitrat\|arbitrat" src/minekin_core/domain/events.py src/minekin_core/domain/input_control.py   # 0 命中
H: sed -n '86,112p;830,840p' src/minekin_core/domain/cases.py
I: sed -n '131,136p;165,172p' src/minekin_core/adapters/launcher/artifacts.py
J: sed -n '42,46p;765,778p' src/minekin_core/domain/version_resolution.py
K: sed -n '215,222p' tests/unit/test_report_cases.py
L: sed -n '395,400p;585,595p' tests/unit/test_report_promotion.py
M: sed -n '3786,3832p' tools/assert_case_evidence.py
N: uv run python .tmp/m-r82/read_ci_steps.py d5680489208c852272a9405d757de8f2fcb2ef1e
```

四态声明：**设计卡已入干 / 登记与真跑未开工 / 无 sealed bundle 新增（0 次挂卷）/ 无强制用例集位移。**

未测清单（不声称）：pyright、全量 pytest、`check_boundaries`、`check_workflow_pins`、`uv build --wheel` + wheel 边界、`minekin --help`、buf 三条、bridge 两条、门载荷前后对、`p0-nav-exp` 的真实 verdict 与 registry 行数（需挂卷，本轮 0 次）、`NAV-EXP-010` 的任何活体形状。
