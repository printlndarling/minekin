# `CORE-080` / `OFFLINE-060` 的 oracle 与载体先行设计（2026-09-28）

- **卡片**：`P0-CORE-080-OFFLINE-060-CASE-SPEC-001`
- **授权来源**：`docs/v1201-lan-control-next-2026-09-27.md` §3 第二类独立工作——该族第五张 doc-only 设计卡（前三张＝`P0-ADMIT-030-050`、`P0-ADMIT-010-020`、`P0-ADMIT-090-120`）。
- **owner**：M。**allowed_paths**：本文件 + 三处主干登记（v1201 新小节、handoff 新轮次、执行计划表一行）。**本轮零代码改动**。
- **禁止**：不挂规范卷、不起 JVM、不读未跟踪的测试服地址文件、不连用户远程服、不动 `mandatory`/registry/判据集合、不新增 `NEXT`、不改 lane 材料一字节。
- **base 现场**：`d5680489208c852272a9405d757de8f2fcb2ef1e`（= 本轮开工前 `git ls-remote origin refs/heads/main` 的回读值；本地 `main` 同值）。
- **引用纪律**：下列行号一律按 base 字节本轮重测；只读脚本与原始输出留在 `.tmp/m-r84/`。
- **口径**：全文**不记** `CORE-080` 或 `OFFLINE-060` 的任何通过结论，也不替它们写断言。

## 1. 契约原文与底数

- `docs/p0-validation-evidence-contract.md:191`（第 9 项，逐字）：`CORE-080`：故意向 oracle 放置 Kin 未看见的事实；检查所有 Runtime/Memory/模型输入均不存在该事实。
- `docs/p0-offline-session-compatibility-contract.md:103`：`OFF-D Diagnostic default`｜删除整个 `--userType value` 对｜与胜者相同｜`"0"`｜与胜者相同｜判断客户端默认值；只作诊断，不能悄悄偏离元数据。
- 同文件 `:104`：`OFF-N Negative`｜明确无效字符串｜固定正确值｜`"0"`｜固定值｜证明日志与验收能识别未知类型，不能成为发布候选。
- 同文件 `:152`：`OFFLINE-060`｜`OFF-D/OFF-N`｜默认/未知类型行为可检测，不误晋级。

登记侧底数（本轮亲量）：

| 读数 | 位置 | 值 |
| --- | --- | --- |
| `CORE-080` 的注册 | `src/minekin_core/domain/cases.py:284` | `W50`、`ValidationClass.RUNTIME_REQUIRED` |
| `W50` 的另一半 | 同文件 `:328` | `ADMIT-070`、`ADMIT-120` |
| `OFFLINE-060` 的注册 | 同文件 `:340-355`（`:351`） | `W30`、**`RUNTIME_REQUIRED`** |
| `core-*` fixture 份数 | `tests/fixtures/cases` | 12 份，**无 `core-080.json`** |
| `offline-*` fixture 份数 | 同目录 | 11 份，**无 `offline-060.json`**（`offline-080` 同样缺） |
| `admit-*` fixture 份数 | 同目录 | 7 份（`001/040/060/070/080/100/110`），无 `admit-120` |
| `W30.absent` 的历史读数 | `docs/validation/v1201-probe-target-carrier-2026-09-27.md:170`、`:174` | `['OFFLINE-060','OFFLINE-080']` |

一处**不得误读**：`tests/unit/test_case_registry.py:1012` 的 `verdict.requirement.absent == ("ADMIT-070", "ADMIT-120", "CORE-080")` 判的是该测试自己造的**合成 registry**（只放了一条 `case()`，见 `:1004-1008`），它证的是「缺具名 case 时 fail closed 并点名」，**不是**真 registry 的逐案读数。本卡不据此声称任何卷面状态。

## 2. 载体底数（`CORE-080` 侧，本轮新量）

| 事实 | 位置 | 今天的形状 |
| --- | --- | --- |
| 三类信息等级，含 `TEST_ORACLE` | `src/minekin_core/domain/information_class.py:55-61` | 注释即写明「没有产品消息类型会是这一类」 |
| 只有 `PLAYER_EQUIVALENT` 进认知 | 同文件 `:63-67` | `enters_cognition` 单条谓词 |
| 类别表共 5 条 | 同文件 `:81-87` | 3 条 `PLAYER_EQUIVALENT` + 2 条 `MANAGEMENT_ONLY`；**无一条 `TEST_ORACLE`** |
| 未分类者拒而不默认 | 同文件 `:90-98`、`:134-136` | `CognitionRefusal.UNCLASSIFIED_DTO` |
| `TEST_ORACLE` 的拒止支 | 同文件 `:139-140` | 存在，且今天只能被 monkeypatch 走到 |
| 该现状被钉住 | `tests/unit/test_information_class.py:139` | `assert InformationClass.TEST_ORACLE not in DTO_INFORMATION_CLASSES.values()`；`:148` 用 `monkeypatch.setitem(...)` 才让 `:153` 断到 `TEST_ORACLE_DTO` |
| 运行期确实问过这道门 | `src/minekin_core/cli/session_runtime.py:511` | 在处理任何载荷之前；`:512-514` 把拒止**按原因计数**而非丢弃 |
| 认知类别只在快照被准入时记 | 同文件 `:534-535` | `perceived_information_class` |
| 两枚读数进 run document | 同文件 `:177-178`、`:756-757` | `perceived_information_class` + `cognition_refusals`（字典） |
| 该对读数被断言过 | `tests/contract/test_session_runtime.py:773-774`、`:857-858` | 精确到 `{"MANAGEMENT_ONLY_DTO": 1}` / `: 9` |
| 缺席扫描的现成先例 | `tools/assert_case_evidence.py:3786-3813` | 见下三条经验 |
| 载体集合由 manifest 决定 | 同文件 `:3692-3719`（封存侧）、`:3722`（run 侧）、`:449`（字段） | 自取子集会「对没打开的文件报没暴露」 |
| `HOSTCTL-070` 已登记四道仓库级实现 | `tools/check_case_assertions.py:504-522` | 含一条走真实 IPC 回环（`tests/contract/test_session_runtime.py::test_a_management_report_does_not_become_what_the_kin_knows`） |

先例的三条经验（照抄即可判，不必再造）：无可扫载体**不等于**干净扫描（`:3805-3808` `NO_EXPOSURE_CARRIERS_READABLE`）；读不到的面要**具名成缺口**而不是计入 `0`（`:3816-3832` `DASHBOARD_CARRIER_NOT_SEALED`）；命中要能报到「哪个载体的哪一处」（`:3809-3812`）。

## 3. 可判形状与缺口

### 3.1 `CORE-080`：门禁与载体都在，缺的是**放置端**

- 甲：**旧清单的这一格按新字节作废一半**。`docs/p0-evidence-inventory-2026-09-26.md:167` 说本条「运行期那半今天无断言亦无材料」——判据侧并非无断言（`HOSTCTL-070` 四条已登记，其中一条穿过真实 IPC 回环），材料侧 run document 里 `cognition_refusals` 与 `perceived_information_class` 就是可封读数。仍成立的是：**没有任何 DTO 是 `TEST_ORACLE`**，所以「向 oracle 放置 Kin 未看见的事实」在生产端无入口。
- 乙：放置有**两种互相排斥的形状**，本卡不替主控选。
  - （走线）新增一个 `TEST_ORACLE` 类别的入站 DTO ⇒ 必动 `DTO_INFORMATION_CLASSES`（`:81-87`）⇒ `tests/unit/test_information_class.py:139` 那条「今天无此类」的断言**按构造变红**，缺口具名 `TEST_ORACLE_PLACEMENT_BREAKS_THE_TOTALITY_PIN`。好处是运行期读数免费到手：`:512-514` 会自动写下 `{"TEST_ORACLE_DTO": n}`。
  - （世界侧）把事实放进世界（Kin 不在附近的一块内容）⇒ 它根本不经过 `information_class` 这道门，只可能经 `domain/perception.py` 的过滤进认知；这道门帮不上忙，判定只能落回**载体扫描**那半。
- 丙：恒真风险与对策。canary 字面量若只由用例自己写进 fixture、再由同一个扫描器扫，则「扫不到」是构造保证而非证据。阳性对照要照 `P0-ADMIT-090-120` 那张卡的写法：**先把 canary 塞进某个被封载体、判它必须命中**，再判真 run 不命中；反例两格（a：载体可读但无 canary ⇒ 应过；b：载体全部不可读 ⇒ 应拒而不算干净）。
- 丁：扫描域要先排除 **oracle 自己的载体**（放置清单与交叉核对件必然含 canary），否则一放就假阳。这与 `P0-ADMIT-090-120-CASE-SPEC-001` 的 `ORACLE_CANARY_HAS_NO_PLACEMENT_MECHANISM` 是**同一处真空**——两卡在此汇合，交主控一次决定而不是两张各猜。

### 3.2 `OFFLINE-060`：`OFF-D`/`OFF-N` 三重锁，且本条是 `RUNTIME_REQUIRED`

1. **CLI 层**：`src/minekin_core/cli/parser.py:236-242` 的 `--identity-candidate` 用 `choices=sorted(...)`（从候选表导出，注释具名了「不写第二份词表」）。未知串在**解析期**即被 argparse 拒（`rc=2` + usage 文本），**不产生任何 run** ⇒ 没有 `session_argv`、没有 bundle、没有可判材料。
2. **数据层**：`src/minekin_core/adapters/launcher/offline_session.py:56-62` 的 `__post_init__` 禁止空 `user_type_argv`（`:59-60`），候选集在 `:87` 封闭为两条。要表达 `OFF-D`「删掉整个 `--userType value` 对」，先得造一条不合法的候选。
3. **解析层**：同文件 `:115` `EMPTY_CAPABLE_PLACEHOLDERS` 只含 `clientid`/`auth_xuid`，`:197-199` 对空环境值直接 `_reject` ⇒ `user_type` 占位符（`:167` 只从候选取值）不可能解析成空。

附带读数四条：

- 代码里那条「未知候选」的具名拒止 `candidate_by_id:104-110`（报 `unknown identity candidate …；known candidates: …`）**从 CLI 不可达**——被 `choices` 先挡。它是给程序内调用者的，不是给操作者的。
- 验收侧其实**已有**「识别未知类型」的判法：`tools/assert_case_evidence.py:3345-3346` 的 `CANDIDATE_NOT_REVIEWED:{candidate}`（读 `:3324-3343` 的 run 自记 argv）。但未知候选的 run 从未发生 ⇒ **判据在、载体不可能出现**，缺口具名 `OFF_N_HAS_JUDGE_BUT_NO_RUN`。
- 于是本条有一个结构性错位：`cases.py:340-355` 把 `OFFLINE-060` 登记为 `RUNTIME_REQUIRED`，而契约 `:104` 要的「未知类型可检测」今天**只可能以仓库级断言成立**（argparse 的 choices 表 + `candidate_by_id` 的拒止），那是 `LOCAL_ONLY` 的形状。把 `OFF-N` 改判为仓库级并不等于点亮本条——点亮它需要 `OFF-D` 那条 run，而 `OFF-D` 被第 2、3 两锁挡死。
- `--identity-candidate` 在整个 `test-orchestrator/` 里 **0 命中**（本轮 `grep -rn -- "--identity-candidate\|IDENTITY_CANDIDATE" test-orchestrator` ⇒ 无输出）⇒ 战役路径今天不转发的不是「未知值」，而是**这个旋钮本身**；`OFF-A/OFF-B` 两列的归因判据（`:3350-3382`）要由真跑满足时，得先有把该旗传进 run 的形状。本卡只登记这一读数，不判它算不算缺口——`OFFLINE-010/020/030-*` 的封证面属 registry/卷侧，本轮未取卷（0 次挂载）。

## 4. 交主控决定的格子（本卡不选）

1. `CORE-080` 的放置走（走线）还是（世界侧）：前者要撤 `test_information_class.py:139` 那条 totality 钉，后者要承认认知门禁帮不上、只剩扫描。
2. `CORE-080` 的「Runtime/Memory/模型输入」清单到底枚举哪些载体：今天可读的只有 manifest 声明的文本件（`:3692-3719`）；「模型输入」在产品里没有独立封存面，是否按 `perception` 过滤后的快照代表它。
3. `OFFLINE-060` 是否**从 `RUNTIME_REQUIRED` 拆成两半**：`OFF-N` 走仓库级具名拒止（可判、不需 run），`OFF-D` 保留为需候选集扩容的一格；还是整条继续等候选集裁决（`docs/development-execution-plan.md:250` 那一格）。
4. `--identity-candidate` 是否接进战役转发名单（与 `#68`、`H1j/H1o/H1l` 同族那条转发名单一起裁），否则 `OFFLINE-060` 的任何真跑形状都无法归因。

## 5. 不回流的口径与本轮附带读数

- 真实封证仍为 **1**（bundle `5086ee42…64f6` / run `a224f6c3…`，出处 `docs/validation/v1201-lan-joiner-control-seal-2026-09-28.md:6-7`）；本卡不新增、不引用私有卷读数。
- `mandatory`、registry、判据集合、门载荷本轮**零位移**；门载荷未取卷复量（无位移预期，也未测）。
- 本卡**不改** `docs/p0-evidence-inventory-2026-09-26.md:167` 那一格（历史读数留在原文件），只在 §3.1 甲具名它已被新字节推翻的部分——与 `P0-ADMIT-090-120` 卡对 `:165` 的处理同一口径。
- `base` 之后新晋 main（`d568048…`）与本卡落盘笔自身的 CI 步骤级读数：本轮未取，留下一轮；本卡不写任何 CI 结论。

## 6. 复现命令（全部只读，工作树根目录）

```bash
A: sed -n '191p' docs/p0-validation-evidence-contract.md
B: sed -n '103,104p;152p' docs/p0-offline-session-compatibility-contract.md
C: sed -n '280,284p;328,330p;340,356p' src/minekin_core/domain/cases.py
D: ls tests/fixtures/cases | grep -c '^core-'      # 12
E: ls tests/fixtures/cases | grep -c '^offline-'   # 11
F: ls tests/fixtures/cases | grep -E 'core-080|offline-060' ; echo rc=$?   # rc=1
G: sed -n '55,87p;90,142p' src/minekin_core/domain/information_class.py
H: sed -n '137,153p' tests/unit/test_information_class.py
I: sed -n '505,540p;170,180p;750,760p' src/minekin_core/cli/session_runtime.py
J: sed -n '770,776p;855,860p' tests/contract/test_session_runtime.py
K: sed -n '56,62p;87,115p;156,178p;195,200p' src/minekin_core/adapters/launcher/offline_session.py
L: sed -n '230,242p' src/minekin_core/cli/parser.py
M: sed -n '3312,3347p;3350,3382p;3692,3719p;3786,3832p' tools/assert_case_evidence.py
N: grep -rn -- "--identity-candidate\|IDENTITY_CANDIDATE" test-orchestrator   # 无输出
O: sed -n '499,522p' tools/check_case_assertions.py
```

四态声明：**设计卡已入干 / 登记与真跑未开工 / 无 sealed bundle 新增（0 次挂卷）/ 无强制用例集位移。**

未测清单（不声称）：pyright、全量 pytest、`check_boundaries`、`check_workflow_pins`、`uv build --wheel` + wheel 边界、`minekin --help`、buf 三条、bridge 两条、门载荷前后对、`CORE-080`/`OFFLINE-060` 的任何活体形状、registry 逐案行数（本轮 0 次挂载，未取）。
